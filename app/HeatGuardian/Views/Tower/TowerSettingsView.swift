// Settings › Tower (hidden: Settings itself opens with a 2-s press on her screen). Twilio credentials -> Keychain,
// live / DRY-RUN state, the SMS rules (notes by SMS, disconnect SMS after 60 min, SMS language), «Send a test SMS»,
// the outbox (queued / sent / failed, retry), and the routing table in plain words. The token is never shown again.
// [SMS-SHORTCUT] Sender picker (Twilio | iPhone Shortcut), the Shortcut's name + how to make it, «Test the Shortcut»,
// and «Clear the list» here too, so a filmed retake sends again (the outbox dedupes one message per event / 30 min).

import SwiftUI

struct TowerSettingsView: View {
    @EnvironmentObject var m: AppModel
    @State private var sid = ""
    @State private var token = ""
    @State private var from = ""
    @State private var result: String?
    @State private var confirmDelete = false
    @State private var confirmClear = false

    var body: some View {
        let L = m.L
        let _ = m.towerVersion
        let t = m.tower
        let stored = t.credentials.load()
        let draft = TwilioCredentials(accountSID: sid, authToken: token.isEmpty ? (stored?.authToken ?? "") : token, fromNumber: from)
        Form {
            Section {
                Label(L.twMode(t),
                      systemImage: t.mode == .live ? "antenna.radiowaves.left.and.right" : "eye")
                    .font(.body.weight(.semibold))
                if t.sender == .twilio && t.smsContacts.isEmpty { Text(L.twNoContacts).foregroundStyle(Palette.danger) }
                Button { m.tower.sendTest(wearerName: m.wearerName) } label: { Label(L.twTest, systemImage: "paperplane") }
                    .disabled(t.sender == .twilio && t.smsContacts.isEmpty)
                NavigationLink { OutboxView() } label: {
                    LabeledContent(L.twOutbox, value: "\(t.outbox.items.filter { $0.status == .queued || $0.status == .sending }.count) / \(t.outbox.items.count)")
                }
                Button(L.twClearOutbox, role: .destructive) { confirmClear = true }.disabled(t.outbox.items.isEmpty)
            } header: { Text(L.twTower) } footer: { Text(L.twBackgroundNote) }

            Section {
                Picker(L.twSender, selection: Binding(get: { t.sender }, set: { t.prefs.sender = $0; m.towerVersion += 1; t.pump() })) {
                    Text(L.twSenderTwilio).tag(SMSSender.twilio)
                    Text(L.twSenderShortcut).tag(SMSSender.shortcut)
                }
                .pickerStyle(.segmented)
                if t.sender == .shortcut {
                    LabeledContent(L.twShortcutName) {
                        TextField(ShortcutAPI.defaultName, text: Binding(get: { t.prefs.shortcutName },
                                                                          set: { t.prefs.shortcutName = $0; m.towerVersion += 1 }))
                            .multilineTextAlignment(.trailing).autocorrectionDisabled()
                    }
                    Text(L.twShortcutHowTo(ShortcutAPI.name(t.prefs.shortcutName))).font(.footnote).foregroundStyle(.secondary)
                    Button { m.tower.sendShortcutTest() } label: { Label(L.twShortcutTest, systemImage: "bolt.horizontal.circle") }
                }
            } header: { Text(L.twSender) }

            Section {
                TextField(L.twSID, text: $sid).textContentType(.username).monospaced()
                SecureField(stored == nil ? L.twToken : L.twTokenStored, text: $token)
                TextField(L.twFrom, text: $from).keyboardType(.phonePad)
                Button {
                    let ok = draft.isComplete && t.credentials.save(draft)
                    result = ok ? L.twSaved : (draft.isComplete ? L.twSaveFailed : L.twCredProblems(draft.problems))
                    token = ""
                    m.towerVersion += 1
                    if ok { t.pump() }
                } label: { Label(L.twSave, systemImage: "key.fill") }
                if stored != nil {
                    Button(L.twDelete, role: .destructive) { confirmDelete = true }
                }
                if let r = result { Text(r).font(.footnote) }
            } header: { Text(L.twCreds) } footer: { Text(L.twCredsNote) }

            Section {
                Toggle(L.twNotesBySMS, isOn: Binding(get: { t.prefs.notesBySMS }, set: { t.prefs.notesBySMS = $0; m.towerVersion += 1 }))
                Toggle(L.twDisconnectSMS, isOn: Binding(get: { t.prefs.disconnectSMS }, set: { t.prefs.disconnectSMS = $0; m.towerVersion += 1 }))
                Toggle(isOn: Binding(get: { t.prefs.smsInSimulation }, set: { t.prefs.smsInSimulation = $0; m.towerVersion += 1 })) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(L.twSimSMS)
                        Text(L.twSimSMSNote).font(.caption).foregroundStyle(.secondary)
                    }
                }
                Picker(L.twSMSLang, selection: Binding(get: { t.prefs.smsLang }, set: { t.prefs.smsLang = $0; m.towerVersion += 1 })) {
                    ForEach(Lang.allCases) { Text($0.native).tag($0) }
                }
                .pickerStyle(.segmented)
                LabeledContent(L.twCountry) {
                    TextField("30", text: Binding(get: { t.prefs.countryCode }, set: { t.prefs.countryCode = $0.filter { $0.isNumber }; m.towerVersion += 1 }))
                        .keyboardType(.numberPad).multilineTextAlignment(.trailing).frame(maxWidth: 80)
                }
                ForEach(SMSRouter.table, id: \.event) { row in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(m.lang == .el ? row.el : row.en).font(.subheadline)
                        Text(row.event).font(.caption.monospaced()).foregroundStyle(.secondary)
                    }
                }
            } header: { Text(L.twRules) } footer: { Text(L.twLimitsNote) }

            Section {
                Button { m.playLadderDemo() } label: { Label(L.twDemoSMS, systemImage: "play.circle") }
            } footer: { Text(L.twDemoNote) }
        }
        .navigationTitle(L.twTowerShort)
        .onAppear {
            sid = stored?.accountSID ?? ""
            from = stored?.fromNumber ?? ""
        }
        .confirmationDialog(L.twClearOutbox, isPresented: $confirmClear, titleVisibility: .visible) {
            Button(L.twClearOutbox, role: .destructive) { m.tower.clearOutbox() }
        }
        .confirmationDialog(L.twDelete, isPresented: $confirmDelete, titleVisibility: .visible) {
            Button(L.twDelete, role: .destructive) {
                t.credentials.delete(); sid = ""; from = ""; token = ""; result = nil; m.towerVersion += 1
            }
        }
    }
}

/// Every SMS, newest first, with its status. Numbers are masked; «Retry» on failed / skipped / waiting items.
struct OutboxView: View {
    @EnvironmentObject var m: AppModel
    @State private var confirmClear = false

    var body: some View {
        let L = m.L
        let _ = m.towerVersion
        let items = m.tower.outbox.items.reversed()
        List {
            if items.isEmpty { Text(L.twOutboxEmpty).foregroundStyle(.secondary) }
            ForEach(Array(items)) { it in
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text(it.contactName).font(.body.weight(.semibold))
                        Text(PhoneNumber.masked(it.to)).font(.footnote.monospaced()).foregroundStyle(.secondary)
                        Spacer(minLength: 4)
                        Text(L.twTime(it.createdAt)).font(.footnote.monospacedDigit()).foregroundStyle(.secondary)
                    }
                    Text(it.body).font(.body).textSelection(.enabled)
                    HStack(spacing: Palette.s8) {
                        Text(L.twStatus(it.status, dry: it.dryRun)).font(.footnote.weight(.semibold)).foregroundStyle(colour(it))
                        Text(L.twSegments(SMSText.segments(it.body).count)).font(.footnote).foregroundStyle(.secondary)
                        if it.attempts > 1 { Text(L.twAttempts(it.attempts)).font(.footnote).foregroundStyle(.secondary) }
                        if it.status == .queued, let n = it.nextAttemptAt, n > Date() { Text(L.twNextTry(n)).font(.footnote).foregroundStyle(.secondary) }
                    }
                    if let e = it.lastError, it.status != .sent { Text(e).font(.footnote).foregroundStyle(.secondary) }
                    if it.simulated { SimBadge(text: L.sim) }
                }
                .padding(.vertical, 4)
                .swipeActions {
                    if it.status == .failed || it.status == .skipped || it.status == .queued {
                        Button(L.twRetry) { m.tower.retry(it.id) }.tint(Palette.primary)
                    }
                }
            }
        }
        .navigationTitle(L.twOutbox)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button(L.twClearOutbox, role: .destructive) { confirmClear = true }.disabled(items.isEmpty)
            }
        }
        .confirmationDialog(L.twClearOutbox, isPresented: $confirmClear, titleVisibility: .visible) {
            Button(L.twClearOutbox, role: .destructive) { m.tower.clearOutbox() }
        }
    }

    private func colour(_ it: OutboxItem) -> Color {
        switch it.status {
        case .sent: return it.dryRun ? Palette.primary : Color(hex: 0x0E7C74)
        case .failed, .skipped: return Color.dynamic(0xA83A0A, 0xFF9B73)
        case .queued, .sending: return Palette.textSecondary
        }
    }
}

/// Settings › Family (SMS): 1-3 contacts, name + mobile + optional email.
struct ContactsSection: View {
    @EnvironmentObject var m: AppModel
    var L: Strings

    var body: some View {
        _ = m.towerVersion
        let cc = m.tower.prefs.countryCode
        return Section {
            ForEach(m.tower.contacts) { c in
                VStack(alignment: .leading, spacing: 6) {
                    TextField(L.twContactName, text: contactBinding(c.id, \.name)).textContentType(.name)
                    TextField(L.twContactPhone, text: contactBinding(c.id, \.phone)).keyboardType(.phonePad).textContentType(.telephoneNumber)
                    if !c.phone.isEmpty && c.e164(defaultCountryCode: cc) == nil {
                        Text(L.twBadPhone).font(.footnote).foregroundStyle(Palette.danger)
                    }
                    TextField(L.twContactEmail, text: contactBinding(c.id, \.email)).keyboardType(.emailAddress).textContentType(.emailAddress)
                }
            }
            .onDelete { m.tower.contacts.remove(atOffsets: $0); m.towerVersion += 1 }
            if m.tower.contacts.count < 3 {
                Button { m.tower.contacts.append(FamilyContact(name: "", phone: "")); m.towerVersion += 1 } label: {
                    Label(L.twAddContact, systemImage: "person.badge.plus")
                }
            }
            NavigationLink { TowerSettingsView() } label: { Label(L.twTower, systemImage: "antenna.radiowaves.left.and.right") }
        } header: { Text(L.twFamily) } footer: { Text(L.twContactsNote) }
    }

    private func contactBinding(_ id: String, _ kp: WritableKeyPath<FamilyContact, String>) -> Binding<String> {
        Binding<String>(get: { m.tower.contacts.first(where: { $0.id == id })?[keyPath: kp] ?? "" },
                set: { (v: String) in
                    guard let i = m.tower.contacts.firstIndex(where: { $0.id == id }) else { return }
                    m.tower.contacts[i][keyPath: kp] = v
                    m.towerVersion += 1
                })
    }
}
