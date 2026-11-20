// ELDER mode (DESIGN.md §6): Greek, designed for 75+ — one screen, no tab bar, nothing to configure.
// Big clock + date (a hidden 2-s long press opens Settings for the family), orb + state word (40 pt) + one sentence,
// «Έγινε ✓» for an open nudge, «Είμαι καλά» for an open CHECK, the family's message as a large card, and the
// long-press «ΒΟΗΘΕΙΑ». Every press goes to the band as CMD 0x1A ELDER_ACTION (AppModel.sendElderAction).

import SwiftUI

struct ElderView: View {
    @EnvironmentObject var m: AppModel
    @Environment(\.hgOverride) private var override
    @State private var local = ElderLocal()
    @State private var confirmCancel = false
    @State private var showSettings = false
    @State private var doneCount = 0

    var body: some View {
        let L = m.L
        let now = m.isDemo ? (m.currentAt ?? Date()) : m.now
        let s = ElderSnapshot.make(m: m, local: local, override: override, now: now)
        let hd = s.field == .help || s.checkOpen ? nil : ElderHerDay.make(m: m, now: now, dismissed: local.herDayDismissed)
        ZStack {
            StateField(state: s.field)
            GeometryReader { g in
                ScrollView {
                    VStack(spacing: Palette.s24) {
                        ElderClock(demoTime: m.isDemo ? m.currentAt : nil, sim: m.isDemo ? L.sim : nil)
                            .onLongPressGesture(minimumDuration: 2) { showSettings = true }
                            .accessibilityAction(named: Text(L.tabSettings)) { showSettings = true }
                        Spacer(minLength: 0)
                        ElderHero(s: s)
                        Spacer(minLength: 0)
                        actions(s, hd, L)
                    }
                    .padding(.horizontal, Palette.s24)
                    .padding(.vertical, Palette.s16)
                    .frame(minHeight: g.size.height)
                }
                .scrollIndicators(.hidden)
            }
            if confirmCancel { cancelOverlay(L) }
        }
        .sensoryFeedback(.success, trigger: doneCount)
        .sensoryFeedback(.warning, trigger: s.field) { old, new in new.severity > old.severity && new.severity >= 3 }
        .sheet(isPresented: $showSettings) {
            SettingsView(onDone: { showSettings = false }).environmentObject(m)
        }
    }

    @ViewBuilder
    private func actions(_ s: ElderSnapshot, _ hd: ElderHerDay?, _ L: Strings) -> some View {
        VStack(spacing: Palette.s16) {
            if let c = hd {
                HerDayCard(card: c, okTitle: L.hdOK) {
                    local.herDayDismissed.insert(c.key)
                    doneCount += 1
                    if c.nudgeOpen { m.sendElderAction(.nudgeDone, nudge: c.nudge) }
                }
            }
            // the brief the Her Day card already answers gets no second «Έγινε ✓»
            if let n = s.openNudge, !(hd != nil && (n.nudge == .brief || n.nudge == .eveningBrief)) {
                BigGlassButton(title: L.uiDone, systemImage: nil, prominent: false) {
                    local.doneNudgeIDs.insert(n.rowID)
                    doneCount += 1
                    m.sendElderAction(.nudgeDone, nudge: n.nudge)
                }
            }
            if s.checkOpen {
                BigGlassButton(title: L.uiImOK, systemImage: "checkmark", prominent: true) {
                    local.imOKAt = Date()
                    doneCount += 1
                    m.sendElderAction(.imOK)
                }
            }
            if local.linkFailed && s.helpActive {
                Text(L.uiNoLink)
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(Palette.textPrimary)
                    .multilineTextAlignment(.center)
                    .padding(Palette.s16)
                    .frame(maxWidth: .infinity)
                    .hgCard()
            }
            HelpButton(title: L.uiHelp, hint: s.helpActive ? L.uiHoldToCancel : L.uiHoldHint, tapHint: L.uiHoldHintLong) {
                if s.helpActive {
                    confirmCancel = true
                } else {
                    local.helpAt = Date()
                    local.linkFailed = !m.sendElderAction(.help) && !m.isDemo
                }
            }
            // DESIGN.md §6: below the HELP button
            if let msg = s.message {
                FamilyMessageCard(text: msg.text) { _ = local.dismissedMsgIDs.insert(msg.rowID) }
            }
        }
    }

    /// «Ακύρωση;» — two huge answers, never time-boxed (HIG: minimise time-boxed elements).
    private func cancelOverlay(_ L: Strings) -> some View {
        ZStack {
            Color.black.opacity(0.35).ignoresSafeArea()
                .accessibilityHidden(true)
            VStack(spacing: Palette.s24) {
                Text(L.uiCancelQ)
                    .font(.system(size: 40, weight: .bold))
                    .foregroundStyle(Palette.textPrimary)
                    .accessibilityAddTraits(.isHeader)
                BigGlassButton(title: L.uiCancelYes, systemImage: "xmark", prominent: false) {
                    local.helpCancelledAt = Date()
                    local.helpAt = nil
                    confirmCancel = false
                    m.sendElderAction(.helpCancel)
                }
                Button { confirmCancel = false } label: {
                    Text(L.uiCancelNo)
                        .font(.title2.weight(.bold))
                        .foregroundStyle(Color.white)
                        .multilineTextAlignment(.center)
                        .frame(maxWidth: .infinity, minHeight: 80)
                        .background(Palette.helpSolid, in: Capsule())
                }
                .buttonStyle(.plain)
            }
            .padding(Palette.s24)
            .background(Palette.surface, in: RoundedRectangle(cornerRadius: Palette.cardRadius + 8, style: .continuous))
            .padding(Palette.s24)
        }
        .transition(.opacity)
    }
}

/// 60 pt clock + date. Demo: the recording's clock (+ SIMULATION).
struct ElderClock: View {
    var demoTime: Date?
    var sim: String?

    var body: some View {
        TimelineView(.everyMinute) { ctx in
            let t = demoTime ?? ctx.date
            VStack(spacing: 2) {
                Text(t, format: .dateTime.hour(.twoDigits(amPM: .omitted)).minute(.twoDigits))
                    .font(.system(size: 60, weight: .semibold).monospacedDigit())
                    .foregroundStyle(Palette.textPrimary)
                    .contentTransition(.numericText())
                Text(t, format: .dateTime.weekday(.wide).day().month(.wide))
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(Palette.textOnField)
                if let s = sim { SimBadge(text: s).padding(.top, 4) }
            }
            .frame(maxWidth: .infinity)
            .accessibilityElement(children: .combine)
        }
    }
}

/// Orb + state word (40 pt bold) + one sentence of guidance.
struct ElderHero: View {
    var s: ElderSnapshot

    var body: some View {
        VStack(spacing: Palette.s16) {
            GlassOrb(symbol: s.symbol, tint: s.field.accent, size: 148, pulse: s.field.urgent)
            Text(s.title)
                .font(.system(size: 40, weight: .bold))
                .foregroundStyle(s.field.wordColor)
                .multilineTextAlignment(.center)
                .minimumScaleFactor(0.7)
                .contentTransition(.opacity)
                .accessibilityAddTraits(.isHeader)
            Text(s.guidance)
                .font(.system(size: 26, weight: .regular))
                .foregroundStyle(Palette.textPrimary)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity)
        .animation(.easeInOut(duration: 0.8), value: s.field)
    }
}

/// A huge glass button (min 72 pt tall) — «Έγινε ✓», «Είμαι καλά», «Ναι, ακύρωση».
struct BigGlassButton: View {
    var title: String
    var systemImage: String?
    var prominent: Bool
    var action: () -> Void

    var body: some View {
        if prominent {
            Button(action: action) { label }
                .buttonStyle(.glassProminent)
                .tint(Color(hex: 0x0E7C74))      // teal darkened: white text 5.0:1
        } else {
            Button(action: action) { label }
                .buttonStyle(.glass)
        }
    }

    private var label: some View {
        HStack(spacing: Palette.s12) {
            if let s = systemImage { Image(systemName: s).accessibilityHidden(true) }
            Text(title)
        }
        .font(.system(size: 30, weight: .bold))
        .foregroundStyle(prominent ? Color.white : Palette.textPrimary)
        .frame(maxWidth: .infinity, minHeight: 72)
    }
}

/// «Μαρία: σας καλεί» — large card; tap to put it away.
struct FamilyMessageCard: View {
    var text: String
    var onDismiss: () -> Void

    var body: some View {
        Button(action: onDismiss) {
            HStack(spacing: Palette.s16) {
                Image(systemName: "phone.fill")
                    .font(.title)
                    .foregroundStyle(Palette.primary)
                    .accessibilityHidden(true)
                Text(text)
                    .font(.system(size: 28, weight: .semibold))
                    .foregroundStyle(Palette.textPrimary)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
            }
            .padding(Palette.s24)
            .frame(maxWidth: .infinity, alignment: .leading)
            .hgCard()
        }
        .buttonStyle(.plain)
    }
}

#Preview("Elder · ok") { ElderPreview(state: .ok) }
#Preview("Elder · water + Έγινε") { ElderPreview(state: .water) }
#Preview("Elder · check + Είμαι καλά") { ElderPreview(state: .check) }
#Preview("Elder · danger") { ElderPreview(state: .danger) }
#Preview("Elder · help") { ElderPreview(state: .help) }
#Preview("Elder · offline") { ElderPreview(state: .offline) }
#Preview("Elder · family message") { ElderPreview(state: .ok, familyMsg: 1) }
#Preview("Elder · heat · dark") { ElderPreview(state: .heat).preferredColorScheme(.dark) }

struct ElderPreview: View {
    var state: OverrideState?
    var familyMsg: Int?

    var body: some View {
        ElderView()
            .environmentObject(AppModel.shared)
            .environment(\.hgOverride, UIOverride(state: state, familyMsg: familyMsg))
            .environment(\.locale, Lang.el.locale)
            .onAppear { AppModel.shared.lang = .el }
    }
}
