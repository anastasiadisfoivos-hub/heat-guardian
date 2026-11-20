// SETUP (owner decision Nov 19, job 1): first launch on HER phone. One question per screen, Greek by default,
// elderly-friendly: text >= 22 pt, every target >= 64 pt, one big «Συνέχεια» at the bottom, «Πίσω» top-left.
// Language -> pair the band -> her name -> age -> sex -> medicines (optional) -> wake / bed time -> family contacts
// (1-3: name + mobile + optional email) -> done. Everything stays on this phone; the profile goes to the band as before.

import SwiftUI

struct SetupView: View {
    @EnvironmentObject var m: AppModel
    var onDone: () -> Void

    enum Step: Int, CaseIterable { case language, pair, name, age, sex, meds, wake, bed, contact, another, done }
    @State private var step: Step = .language
    @State private var name = ""
    @State private var age = 75
    @State private var male = false
    @State private var wake = Date().at(minute: 7 * 60 + 30)
    @State private var bed = Date().at(minute: 23 * 60)
    @State private var contacts: [FamilyContact] = []
    @State private var draft = FamilyContact(name: "", phone: "")

    var body: some View {
        let L = m.L
        ZStack {
            StateField(state: .ok)
            VStack(spacing: Palette.s24) {
                header(L)
                ScrollView {
                    VStack(alignment: .leading, spacing: Palette.s24) { content(L) }
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .scrollIndicators(.hidden)
                footer(L)
            }
            .padding(Palette.s24)
        }
        .animation(.easeInOut(duration: 0.3), value: step)
        .onAppear {
            name = m.wearerName == "Μαρία" ? "" : m.wearerName   // the old demo default is not her name
            age = m.age; male = m.sexMale
            contacts = m.tower.contacts
        }
    }

    // MARK: frame

    private func header(_ L: Strings) -> some View {
        HStack {
            if step != .language && step != .done {
                Button { back() } label: {
                    Label(L.suBack, systemImage: "chevron.left").font(.system(size: 22, weight: .semibold))
                        .frame(minWidth: 64, minHeight: 64)
                }
                .buttonStyle(.glass)
            }
            Spacer(minLength: 0)
            Text(L.suStepOf(step.rawValue + 1, Step.allCases.count))
                .font(.system(size: 20, weight: .medium)).foregroundStyle(Palette.textOnField)
        }
    }

    @ViewBuilder
    private func footer(_ L: Strings) -> some View {
        switch step {
        case .another:
            VStack(spacing: Palette.s16) {
                big(L.suYesAnother, prominent: false) { draft = FamilyContact(name: "", phone: ""); step = .contact }
                big(L.suNoFinish, prominent: true) { step = .done }
            }
        case .done:
            big(L.suDone, prominent: true) { finish() }
        case .contact:
            VStack(spacing: Palette.s12) {
                big(L.suNext, prominent: true) { saveContact() }
                    .disabled(draft.e164(defaultCountryCode: m.tower.prefs.countryCode) == nil || draft.name.trimmingCharacters(in: .whitespaces).isEmpty)
                if !contacts.isEmpty { big(L.suSkip, prominent: false) { step = .done } }
            }
        default:
            VStack(spacing: Palette.s12) {
                big(L.suNext, prominent: true) { next() }
                    .disabled(step == .name && name.trimmingCharacters(in: .whitespaces).isEmpty)
                if step == .pair || step == .meds { big(L.suSkip, prominent: false) { next() } }
            }
        }
    }

    private func big(_ title: String, prominent: Bool, _ action: @escaping () -> Void) -> some View {
        BigGlassButton(title: title, systemImage: nil, prominent: prominent, action: action)
    }

    private func question(_ q: String, _ note: String? = nil) -> some View {
        VStack(alignment: .leading, spacing: Palette.s12) {
            Text(q).font(.system(size: 34, weight: .bold)).foregroundStyle(Palette.textPrimary)
                .fixedSize(horizontal: false, vertical: true).accessibilityAddTraits(.isHeader)
            if let n = note {
                Text(n).font(.system(size: 22)).foregroundStyle(Palette.textOnField).fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    // MARK: the questions

    @ViewBuilder
    private func content(_ L: Strings) -> some View {
        switch step {
        case .language:
            question("Heat Guardian", L.suWelcome)
            ForEach(Lang.allCases) { l in
                choice(l.native, selected: m.lang == l) { m.lang = l }
            }
        case .pair:
            question(L.suPairQ, L.suPairNote)
            let c = m.phase == .connected
            HStack(spacing: Palette.s16) {
                Image(systemName: c ? "checkmark.circle.fill" : "antenna.radiowaves.left.and.right")
                    .font(.system(size: 34)).foregroundStyle(c ? Palette.ok : Palette.primary)
                    .symbolEffect(.pulse, isActive: !c && m.phase != .idle)
                Text(c ? L.suConnected : SettingsViewModel.phase(m, L).0)
                    .font(.system(size: 24, weight: .semibold)).foregroundStyle(Palette.textPrimary)
            }
            .padding(Palette.s16).frame(maxWidth: .infinity, minHeight: 72, alignment: .leading).hgCard()
            if !c { big(L.suConnect, prominent: false) { m.link.connect() } }
        case .name:
            question(L.suNameQ, L.suNameNote)
            field(L.name, text: $name).textContentType(.givenName)
        case .age:
            question(L.suAgeQ)
            HStack(spacing: Palette.s24) {
                round("minus") { age = max(50, age - 1) }
                Text("\(age)").font(.system(size: 64, weight: .bold).monospacedDigit())
                    .contentTransition(.numericText()).frame(minWidth: 110)
                    .accessibilityLabel(L.suAgeQ).accessibilityValue("\(age)")
                round("plus") { age = min(110, age + 1) }
            }
            .frame(maxWidth: .infinity)
        case .sex:
            question(L.suSexQ)
            choice(L.female, selected: !male) { male = false }
            choice(L.male, selected: male) { male = true }
        case .meds:
            question(L.suMedsQ, L.suMedsNote)
            ForEach(SettingsViewModel.medBits, id: \.bit) { mb in
                medToggle(L, bit: mb.bit)
            }
        case .wake:
            question(L.suWakeQ)
            DatePicker(L.wakeTime, selection: $wake, displayedComponents: .hourAndMinute)
                .datePickerStyle(.wheel).labelsHidden().frame(maxWidth: .infinity)
        case .bed:
            question(L.suBedQ)
            DatePicker(L.bedTime, selection: $bed, displayedComponents: .hourAndMinute)
                .datePickerStyle(.wheel).labelsHidden().frame(maxWidth: .infinity)
        case .contact:
            question(L.suContactQ, L.suContactN(contacts.count + 1) + ". " + L.twContactsNote)
            field(L.twContactName, text: $draft.name).textContentType(.name)
            field(L.twContactPhone, text: $draft.phone).keyboardType(.phonePad).textContentType(.telephoneNumber)
            if !draft.phone.isEmpty && draft.e164(defaultCountryCode: m.tower.prefs.countryCode) == nil {
                Text(L.twBadPhone).font(.system(size: 22)).foregroundStyle(FieldState.danger.wordColor)
            }
            field(L.twContactEmail, text: $draft.email).keyboardType(.emailAddress).textContentType(.emailAddress)
        case .another:
            question(L.suAnotherQ, contacts.map { $0.name }.joined(separator: ", "))
        case .done:
            question(L.suAllSet, L.suAllSetNote)
            Text(L.twMode(m.tower))
                .font(.system(size: 22)).foregroundStyle(Palette.textPrimary).padding(Palette.s16)
                .frame(maxWidth: .infinity, alignment: .leading).hgCard()
        }
    }

    private func field(_ title: String, text: Binding<String>) -> some View {
        TextField(title, text: text)
            .font(.system(size: 26))
            .padding(.horizontal, Palette.s16)
            .frame(minHeight: 64)
            .hgGlass(.regular, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private func choice(_ title: String, selected: Bool, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Text(title).font(.system(size: 26, weight: .semibold))
                Spacer(minLength: 0)
                Image(systemName: selected ? "checkmark.circle.fill" : "circle").font(.system(size: 28))
                    .foregroundStyle(selected ? Palette.ok : Palette.textOnField)
            }
            .foregroundStyle(Palette.textPrimary)
            .padding(.horizontal, Palette.s8)
            .frame(maxWidth: .infinity, minHeight: 64)
        }
        .buttonStyle(.glass)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private func medToggle(_ L: Strings, bit: Int) -> some View {
        let on = (m.medFlags & bit) != 0
        let title: String = [1: L.medBeta, 2: L.medDiuretic, 4: L.medLowSweat, 8: L.medAce, 16: L.medOther][bit] ?? ""
        return choice(title, selected: on) { if on { m.medFlags &= ~bit } else { m.medFlags |= bit } }
    }

    private func round(_ symbol: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol).font(.system(size: 30, weight: .bold)).frame(width: 72, height: 72)
        }
        .buttonStyle(.glass).buttonBorderShape(.circle)
    }

    // MARK: flow

    private func next() {
        switch step {
        case .name: m.wearerName = name.trimmingCharacters(in: .whitespaces)
        case .age: m.age = age
        case .sex: m.sexMale = male
        case .wake: m.routine.wake = wake.minuteOfDay
        case .bed: m.routine.bed = bed.minuteOfDay
        default: break
        }
        if step == .bed && !contacts.isEmpty { step = .another; return }
        step = Step(rawValue: step.rawValue + 1) ?? .done
    }

    private func back() {
        if step == .done || step == .another { step = .contact; return }
        step = Step(rawValue: max(0, step.rawValue - 1)) ?? .language
    }

    private func saveContact() {
        var c = draft
        c.name = c.name.trimmingCharacters(in: .whitespaces)
        c.email = c.email.trimmingCharacters(in: .whitespaces)
        if let i = contacts.firstIndex(where: { $0.id == c.id }) { contacts[i] = c } else { contacts.append(c) }
        m.tower.contacts = contacts
        draft = FamilyContact(name: "", phone: "")
        step = contacts.count >= 3 ? .done : .another
    }

    private func finish() {
        m.tower.contacts = contacts
        if m.link.isConnected { m.sendProfile(thermometer: nil); _ = m.sendRoutine() }
        onDone()
    }
}

#Preview("Setup") { SetupView(onDone: {}).environmentObject(AppModel.shared) }
