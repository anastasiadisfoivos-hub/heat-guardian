// FIT CHECK («Έλεγχος εφαρμογής»), full screen over her home: one message per screen, 40 pt bold title, 24 pt line,
// icon always next to words, buttons >= 72 pt (BigGlassButton), no swipes (a full-screen cover has no swipe-to-dismiss; it closes only with its button). The message sits on a solid surface
// card so text contrast is >= 7:1 whatever the colour field does behind it (values in Model/FitCheck.swift's header
// and ios/PROGRESS.md [APP-FIT]). The verdict is the band's own bits (FitCheck.state); see FitCheck.swift for what
// over BLE can and cannot be told apart.
//
// Sources, in this order: a preview / -HGFit override (fixed state, screenshots) -> a REAL connected band (always,
// even in demo mode) -> the filming mock (demo mode or -HGFitMock, no real band connected; ΠΡΟΣΟΜΟΙΩΣΗ badge).

import SwiftUI

struct FitCheckView: View {
    @EnvironmentObject var m: AppModel
    @Environment(\.hgOverride) private var override
    var onClose: () -> Void

    @State private var startedAt = Date()
    @State private var round = 0
    @State private var wasCharging = false

    /// The filming mock runs only without a real band.
    private var useMock: Bool { m.phase != .connected && (m.isDemo || override.fitMock) }

    private func state(_ now: Date) -> FitState {
        if let f = override.fit { return f }
        if useMock { return FitCheckMock.state(round: round, elapsed: now.timeIntervalSince(startedAt)) }
        let s = FitCheck.state(frame: m.liveLast, frameAt: m.liveLastAt, connected: m.phase == .connected,
                               startedAt: startedAt, now: now)
        // Just unplugged: the band needs its 2 minutes again (its NOT_WORN bit is still up from the charger).
        if wasCharging && s != .charging && s != .ok { return .checking }
        return s
    }

    var body: some View {
        TimelineView(.periodic(from: Date(), by: 1)) { ctx in
            screen(state(ctx.date), now: ctx.date)
        }
    }

    private func screen(_ s: FitState, now: Date) -> some View {
        let L = m.L
        return ZStack {
            StateField(state: field(s))
            VStack(spacing: Palette.s24) {
                if useMock && override.fit == nil { SimBadge(text: L.sim) }
                Spacer(minLength: 0)
                icon(s, now: now)
                VStack(spacing: Palette.s16) {
                    Text(L.fitTitle(s))
                        .font(.system(size: 40, weight: .bold))
                        .foregroundStyle(wordColor(s))
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                        .contentTransition(.opacity)
                        .accessibilityAddTraits(.isHeader)
                    Text(L.fitLine(s))
                        .font(.system(size: 26))
                        .foregroundStyle(Palette.textPrimary)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(Palette.s24)
                .frame(maxWidth: .infinity)
                .background(Palette.surface, in: RoundedRectangle(cornerRadius: Palette.cardRadius, style: .continuous))
                .accessibilityElement(children: .combine)
                Spacer(minLength: 0)
                buttons(s, L)
            }
            .padding(.horizontal, Palette.s24)
            .padding(.vertical, Palette.s16)
            .animation(.easeInOut(duration: 0.8), value: s)
        }
        .sensoryFeedback(.success, trigger: s) { _, new in new == .ok }
        .onChange(of: s) { old, new in changed(from: old, to: new) }
    }

    @ViewBuilder
    private func buttons(_ s: FitState, _ L: Strings) -> some View {
        VStack(spacing: Palette.s16) {
            if s == .loose || s == .off {
                BigGlassButton(title: L.fitAgain, systemImage: "arrow.clockwise", prominent: false) {
                    round += 1
                    startedAt = Date()
                }
            }
            BigGlassButton(title: s == .ok ? L.fitDone : L.fitClose, systemImage: s == .ok ? "checkmark" : "xmark",
                           prominent: false, action: onClose)
        }
    }

    @ViewBuilder
    private func icon(_ s: FitState, now: Date) -> some View {
        if s == .checking {
            let p = useMock ? FitCheck.progress(elapsed: now.timeIntervalSince(startedAt), mock: true)
                            : FitCheck.progress(elapsed: now.timeIntervalSince(startedAt), mock: false)
            ZStack {
                Circle().stroke(Palette.hairline, lineWidth: 12)
                Circle().trim(from: 0, to: CGFloat(p))
                    .stroke(Palette.primary, style: StrokeStyle(lineWidth: 12, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                    .animation(.linear(duration: 1), value: p)
                Image(systemName: "applewatch.side.right")
                    .font(.system(size: 48, weight: .regular))
                    .foregroundStyle(Palette.primary)
            }
            .frame(width: 132, height: 132)
            .accessibilityHidden(true)
        } else {
            GlassOrb(symbol: symbol(s), tint: field(s).accent)
        }
    }

    private func changed(from old: FitState, to new: FitState) {
        if new == .charging { wasCharging = true }
        if old == .charging && new != .charging { wasCharging = false; startedAt = Date() }
        guard new == .ok, override.fit == nil else { return }
        // Real band only: remember the OK so the screen does not open by itself again today.
        if !useMock { FitCheck.okShownAt = Date() }
        // Settle back to her home a few seconds after the OK.
        DispatchQueue.main.asyncAfter(deadline: .now() + 4) {
            if state(Date()) == .ok { onClose() }
        }
    }

    private func field(_ s: FitState) -> FieldState {
        switch s {
        case .ok: return .ok
        case .loose: return .heat
        default: return .offline
        }
    }

    private func symbol(_ s: FitState) -> String {
        switch s {
        case .ok: return "checkmark.circle.fill"
        case .loose: return "arrow.down.right.and.arrow.up.left"
        case .off: return "hand.raised.slash"
        case .charging: return "battery.100percent.bolt"
        case .noLink: return "antenna.radiowaves.left.and.right.slash"
        case .checking: return "applewatch.side.right"
        }
    }

    /// Key word colour on the white / dark surface card: >= 9:1 (green / amber), text primary 17:1.
    private func wordColor(_ s: FitState) -> Color {
        switch s {
        case .ok: return Color.dynamic(0x05524A, 0x9AF0E0)
        case .loose: return Color.dynamic(0x6B3500, 0xFFD199)
        default: return Palette.textPrimary
        }
    }
}

#Preview("Fit · checking") { FitPreview(fit: .checking) }
#Preview("Fit · ok") { FitPreview(fit: .ok) }
#Preview("Fit · loose") { FitPreview(fit: .loose) }
#Preview("Fit · off") { FitPreview(fit: .off) }
#Preview("Fit · charging") { FitPreview(fit: .charging) }

struct FitPreview: View {
    var fit: FitState
    var body: some View {
        FitCheckView(onClose: {})
            .environmentObject(AppModel.shared)
            .environment(\.hgOverride, UIOverride(fit: fit))
            .environment(\.locale, Lang.el.locale)
            .onAppear { AppModel.shared.lang = .el }
    }
}
