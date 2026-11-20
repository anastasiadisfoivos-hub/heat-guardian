// HER HOME SCREEN (owner decision Nov 19): three things only — is the band connected, today's balance colour
// (green … red, the band's own colours and meaning) with its reason, and ΒΟΗΘΕΙΑ. Below, one quiet button to the
// history + report, and «Έλεγχος εφαρμογής» (the fit check, FitCheckView: also opens by itself when a real band connects
// without good contact yet). Settings (for the family) open with a 2-s press on the connection pill.
// The colour field behind follows DESIGN.md §4 state tones; the balance gauge uses the BAND's 5 colours so the
// phone and the wrist read the same (owner decision Nov 19 18:31 wins on meaning; DESIGN.md wins on everything else).

import SwiftUI

struct TowerHomeView: View {
    @EnvironmentObject var m: AppModel
    @Environment(\.hgOverride) private var override
    @State private var local = ElderLocal()
    @State private var confirmCancel = false
    @State private var showSettings = false
    @State private var showHistory = false
    @State private var helpCount = 0
    @State private var showFit = false
    /// A real band just connected: decide on its first fresh STATUS whether the fit check opens by itself.
    @State private var fitPending = false

    var body: some View {
        let L = m.L
        let now = m.isDemo ? (m.currentAt ?? Date()) : m.now
        let s = ElderSnapshot.make(m: m, local: local, override: override, now: now)
        let connected = m.isDemo || m.phase == .connected || override.state != nil && override.state != .offline
        let vs = s.helpActive ? "HELP" : (override.state?.viewState ?? AppModel.viewState(m.current))
        let tier = Balance.step(viewState: vs, connected: connected, settling: m.ladderSettling(now: now))
        // band 0.9.18+: exactly the band's step + dot (GAUGE frame); older bands / no frame for 3 min: the STATUS tier.
        // A preview override or HELP on screen keeps the tier.
        let shown = override.state != nil || s.helpActive ? (step: tier, dot: Balance.dot(tier))
                                                           : m.balanceDisplay(now: now, connected: connected, fallbackStep: tier)
        let step = shown.step
        let toast = m.ladderToast(now: now)
        ZStack {
            StateField(state: s.field)
            GeometryReader { g in
                ScrollView {
                    VStack(spacing: Palette.s24) {
                        ConnectionPill(connected: connected, L: L, since: m.bandDisconnectedSince, sim: m.isDemo ? L.sim : nil)
                            .onLongPressGesture(minimumDuration: 2) { showSettings = true }
                            .accessibilityAction(named: Text(L.tabSettings)) { showSettings = true }
                        Spacer(minLength: 0)
                        BalanceGauge(step: step, dot: shown.dot, L: L)
                        VStack(spacing: Palette.s12) {
                            Text(s.helpActive ? L.state("HELP").0 : L.twBalanceTitle(step))
                                .font(.system(size: 40, weight: .bold))
                                .foregroundStyle(s.field.wordColor)
                                .multilineTextAlignment(.center)
                                .minimumScaleFactor(0.7)
                                .contentTransition(.opacity)
                                .accessibilityAddTraits(.isHeader)
                            Text(s.helpActive ? (m.tower.mode == .live ? L.twHelpSent : L.twHelpSentDry) : (toast ?? L.twBalanceReason(step)))
                                .font(.system(size: 24))
                                .foregroundStyle(Palette.textPrimary)
                                .multilineTextAlignment(.center)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .animation(.easeInOut(duration: 0.8), value: step)
                        Spacer(minLength: 0)
                        HelpButton(title: L.uiHelp, hint: s.helpActive ? L.uiHoldToCancel : L.uiHoldHint, tapHint: L.uiHoldHintLong) {
                            if s.helpActive { confirmCancel = true } else {
                                local.helpAt = Date()
                                helpCount += 1
                                local.linkFailed = !m.sendElderAction(.help) && !m.isDemo
                            }
                        }
                        Button { showHistory = true } label: {
                            Label(L.twHistoryButton, systemImage: "clock.arrow.circlepath")
                                .font(.system(size: 22, weight: .semibold))
                                .foregroundStyle(Palette.textPrimary)
                                .frame(maxWidth: .infinity, minHeight: 64)
                        }
                        .buttonStyle(.glass)
                        Button { showFit = true } label: {
                            Label(L.fitButton, systemImage: "applewatch.side.right")
                                .font(.system(size: 24, weight: .semibold))
                                .foregroundStyle(Palette.textPrimary)
                                .frame(maxWidth: .infinity, minHeight: 64)
                        }
                        .buttonStyle(.glass)
                    }
                    .padding(.horizontal, Palette.s24)
                    .padding(.vertical, Palette.s16)
                    .frame(minHeight: g.size.height)
                }
                .scrollIndicators(.hidden)
            }
            if confirmCancel { cancelOverlay(L) }
        }
        .sensoryFeedback(.error, trigger: helpCount)
        .sensoryFeedback(.warning, trigger: step ?? -1) { old, new in new > old && new >= 3 }
        .sheet(isPresented: $showSettings) { SettingsView(onDone: { showSettings = false }).environmentObject(m) }
        .sheet(isPresented: $showHistory) { NavigationStack { TowerHistoryView() }.environmentObject(m) }
        .fullScreenCover(isPresented: $showFit) { FitCheckView(onClose: { showFit = false }).environmentObject(m) }
        .onAppear { if override.fit != nil || override.fitMock { showFit = true } }
        .onChange(of: m.phase) { _, p in fitPending = p == .connected }
        .onChange(of: m.liveLastAt) { _, _ in
            guard fitPending, m.liveLast != nil else { return }   // a just-booted band's empty seed frame: wait for a reading
            fitPending = false
            // Only for a REAL band, only on her screen, never over HELP, Settings or History, and not again for 12 h
            // after an OK (FitCheck.shouldAutoShow).
            guard override.state == nil, !showFit, !showSettings, !showHistory, m.liveLast?.state != "HELP",
                  FitCheck.shouldAutoShow(frame: m.liveLast, okShownAt: FitCheck.okShownAt, now: Date()) else { return }
            showFit = true
        }
    }

    private func cancelOverlay(_ L: Strings) -> some View {
        ZStack {
            Color.black.opacity(0.35).ignoresSafeArea().accessibilityHidden(true)
            VStack(spacing: Palette.s24) {
                Text(L.uiCancelQ).font(.system(size: 40, weight: .bold)).foregroundStyle(Palette.textPrimary)
                    .accessibilityAddTraits(.isHeader)
                BigGlassButton(title: L.uiCancelYes, systemImage: "xmark", prominent: false) {
                    local.helpCancelledAt = Date(); local.helpAt = nil; confirmCancel = false
                    m.sendElderAction(.helpCancel)
                }
                Button { confirmCancel = false } label: {
                    Text(L.uiCancelNo).font(.title2.weight(.bold)).foregroundStyle(Color.white)
                        .multilineTextAlignment(.center).frame(maxWidth: .infinity, minHeight: 80)
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

/// «● Βραχιόλι συνδεδεμένο» / «○ Χωρίς σύνδεση με το βραχιόλι · από τις 14:10». Long press = Settings.
struct ConnectionPill: View {
    var connected: Bool
    var L: Strings
    var since: Date?
    var sim: String?

    var body: some View {
        VStack(spacing: Palette.s8) {
            HStack(spacing: Palette.s12) {
                Image(systemName: connected ? "dot.radiowaves.left.and.right" : "antenna.radiowaves.left.and.right.slash")
                    .font(.system(size: 24, weight: .semibold))
                    .foregroundStyle(connected ? Palette.ok : FieldState.offline.accent)
                    .symbolEffect(.pulse, isActive: connected)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text(connected ? L.twBandOn : L.twBandOff).font(.system(size: 22, weight: .semibold))
                    if !connected, let s = since { Text(L.twBandOffSince(s)).font(.system(size: 18)).foregroundStyle(Palette.textOnField) }
                }
                .foregroundStyle(Palette.textPrimary)
            }
            .padding(.horizontal, Palette.s24)
            .frame(minHeight: 64)
            .hgGlass(.regular, in: Capsule())
            .accessibilityElement(children: .combine)
            .accessibilityHint(L.twSettingsHint)
            if let s = sim { SimBadge(text: s) }
        }
        .frame(maxWidth: .infinity)
    }
}

/// The band's "keep it green" gauge: a curved scale of the band's 5 colours (they also differ in lightness) with a dot
/// (centre = balanced, right = getting hot), so it reads without colour. Grey and no dot = no reading.
struct BalanceGauge: View {
    var step: Int?
    /// -10 … +10 (nil = grey, no dot): the band's own dot from GAUGE, or the step's centre (Balance.dot).
    var dot: Double?
    var L: Strings

    private func colour(_ i: Int) -> Color {
        let c = Balance.colours[i]
        return Color(red: Double(c.r) / 255, green: Double(c.g) / 255, blue: Double(c.b) / 255)
    }

    var body: some View {
        GeometryReader { g in
            let w = min(g.size.width, 320.0)
            let r = w / 2 - 18
            let centre = CGPoint(x: g.size.width / 2, y: r + 18)
            ZStack {
                // 5 arc segments over 180° (left = cool, right = Danger line)
                ForEach(0..<5, id: \.self) { i in
                    ArcSegment(from: Double(i) / 5, to: Double(i + 1) / 5, gap: 0.006)
                        .stroke(step == nil ? Color.gray.opacity(0.35) : colour(i),
                                style: StrokeStyle(lineWidth: step == i ? 30 : 20, lineCap: .butt))
                        .frame(width: 2 * r, height: 2 * r)
                        .position(centre)
                }
                if let d = dot {
                    let a = Double.pi * (1 - (d + 10) / 20)          // -10 -> 180° (left), +10 -> 0° (right)
                    Circle()
                        .fill(Palette.surface)
                        .overlay(Circle().strokeBorder(Palette.textPrimary, lineWidth: 5))
                        .frame(width: 40, height: 40)
                        .position(x: centre.x + r * cos(a), y: centre.y - r * sin(a))
                        .animation(.easeInOut(duration: 1.0), value: d)
                }
            }
        }
        .frame(height: 190)
        .accessibilityElement()
        .accessibilityLabel(L.twGaugeA11y)
        .accessibilityValue(L.twGaugeA11yValue(step))
    }
}

/// An arc of the upper half circle, `from`/`to` in 0…1 left to right.
struct ArcSegment: Shape {
    var from: Double
    var to: Double
    var gap: Double

    func path(in rect: CGRect) -> Path {
        var p = Path()
        let c = CGPoint(x: rect.midX, y: rect.midY)
        let a0: Double = 180 + 180 * (from + gap)
        let a1: Double = 180 + 180 * (to - gap)
        p.addArc(center: c, radius: rect.width / 2, startAngle: Angle.degrees(a0), endAngle: Angle.degrees(a1), clockwise: false)
        return p
    }
}

extension AppModel {
    /// The ladder said "worked" in the last 20 min (band back to OK): show yellow-green, «Μπράβο».
    func ladderSettling(now: Date) -> Bool {
        if case .worked? = lastLadder(within: 20 * 60, now: now)?.ladder { return true }
        return false
    }
    /// «Μπράβο, δροσίζεστε» / «Ακόμα ζεσταίνεστε» for 10 min after the band said it.
    func ladderToast(now: Date) -> String? {
        switch lastLadder(within: 10 * 60, now: now)?.ladder {
        case .worked?: return L.twWorkedToast
        case .note(.waterDidNotHelp, _, _, _)?: return L.twStillToast
        default: return nil
        }
    }
    private func lastLadder(within: TimeInterval, now: Date) -> LogEntry? {
        let kinds: Set<LogKind> = [.ldWorked, .ldNote, .ldRemind, .ldEscalated]
        let from = now.addingTimeInterval(-within), to = now.addingTimeInterval(60)
        return activeStore.entries.last { (e: LogEntry) -> Bool in kinds.contains(e.kind) && e.at > from && e.at <= to }
    }
}

#Preview("Her screen · ok") { TowerPreview(state: .ok) }
#Preview("Her screen · water") { TowerPreview(state: .water) }
#Preview("Her screen · danger") { TowerPreview(state: .danger) }
#Preview("Her screen · help") { TowerPreview(state: .help) }
#Preview("Her screen · offline") { TowerPreview(state: .offline) }

struct TowerPreview: View {
    var state: OverrideState?
    var body: some View {
        TowerHomeView()
            .environmentObject(AppModel.shared)
            .environment(\.hgOverride, UIOverride(state: state))
            .environment(\.locale, Lang.el.locale)
            .onAppear { AppModel.shared.lang = .el }
    }
}
