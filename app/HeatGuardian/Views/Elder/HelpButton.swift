// «ΒΟΗΘΕΙΑ» (DESIGN.md §6): one huge red capsule (min 80 pt), long press 1.5 s with a filling ring and a strong
// haptic at the start; release early = nothing happens. A short tap only shows how to use it (no accidental HELP).
// VoiceOver: the default action triggers it (a deliberate double-tap), per HIG "offer alternatives to gestures".

import SwiftUI

struct HelpButton: View {
    var title: String               // «ΒΟΗΘΕΙΑ»
    var hint: String                // «Κρατήστε πατημένο» / «Κρατήστε πατημένο για ακύρωση»
    var tapHint: String             // shown after a short tap
    var onTrigger: () -> Void

    static let holdSeconds = 1.5

    @State private var progress: CGFloat = 0
    @State private var pressing = false
    @State private var fired = 0
    @State private var showTapHint = false
    @State private var firedAt = Date.distantPast

    var body: some View {
        VStack(spacing: Palette.s8) {
            HStack(spacing: Palette.s16) {
                ring
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.system(size: 30, weight: .heavy))
                        .tracking(1.5)
                    Text(hint)
                        .font(.body.weight(.semibold))
                        .opacity(0.95)
                }
                Spacer(minLength: 0)
            }
            .foregroundStyle(Color.white)
            .padding(.horizontal, 28)
            .frame(maxWidth: .infinity, minHeight: 88)
            .background(Palette.helpSolid, in: Capsule())
            .scaleEffect(pressing ? 0.98 : 1)
            .animation(.easeOut(duration: 0.15), value: pressing)
            .contentShape(Capsule())
            .onLongPressGesture(minimumDuration: HelpButton.holdSeconds, maximumDistance: 60) {
                fired += 1
                firedAt = Date()
                progress = 0
                onTrigger()
            } onPressingChanged: { isPressing in
                pressing = isPressing
                if isPressing {
                    showTapHint = false
                    withAnimation(.linear(duration: HelpButton.holdSeconds)) { progress = 1 }
                } else {
                    // released (early, or after firing): the ring empties. (`progress` is already 1 as a model
                    // value during the fill animation, so it cannot tell an early release apart.)
                    withAnimation(.easeOut(duration: 0.2)) { progress = 0 }
                }
            }
            .simultaneousGesture(TapGesture().onEnded {
                if Date().timeIntervalSince(firedAt) > 1 { showTapHint = true }   // not the end of a completed hold
            })
            .sensoryFeedback(.impact(weight: .heavy), trigger: pressing) { _, new in new }
            .sensoryFeedback(.error, trigger: fired)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(title)
            .accessibilityHint(hint)
            .accessibilityAddTraits(.isButton)
            .accessibilityAction { fired += 1; onTrigger() }

            if showTapHint {
                Text(tapHint)
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(Palette.textPrimary)
                    .multilineTextAlignment(.center)
                    .transition(.opacity)
            }
        }
        .animation(.easeInOut(duration: 0.2), value: showTapHint)
    }

    /// The filling ring around the SOS glyph.
    private var ring: some View {
        ZStack {
            Circle().stroke(Color.white.opacity(0.35), lineWidth: 5)
            Circle()
                .trim(from: 0, to: progress)
                .stroke(Color.white, style: StrokeStyle(lineWidth: 5, lineCap: .round))
                .rotationEffect(.degrees(-90))
            Image(systemName: "sos")
                .font(.system(size: 18, weight: .bold))
        }
        .frame(width: 52, height: 52)
        .accessibilityHidden(true)
    }
}
