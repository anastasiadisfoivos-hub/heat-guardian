// The background IS the status (DESIGN.md §2.3, §4): vertical gradient (top -> mid -> near-white) + two blurred
// blobs, top-left and top-right. A state change crossfades the whole field (1.0 s ease). Reduce Motion: crossfade
// only, no drift. Reduce Transparency: the blobs go, the gradient stays (no translucent layers).

import SwiftUI

struct StateField: View {
    var state: FieldState

    var body: some View {
        ZStack {
            FieldLayer(state: state)
                .id(state)
                .transition(.opacity)
        }
        .animation(.easeInOut(duration: 1.0), value: state)
        .ignoresSafeArea()
        .accessibilityHidden(true)
    }
}

/// One state's field. Kept separate so the crossfade swaps whole layers.
private struct FieldLayer: View {
    var state: FieldState
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.accessibilityReduceTransparency) private var reduceTransparency
    @State private var drift = false

    var body: some View {
        let c = state.colors(dark: scheme == .dark)
        GeometryReader { g in
            ZStack(alignment: .top) {
                LinearGradient(stops: [.init(color: c.top, location: 0),
                                       .init(color: c.mid, location: 0.45),
                                       .init(color: c.bottom, location: 1)],
                               startPoint: .top, endPoint: .bottom)
                if !reduceTransparency {
                    blob(c.blob1, opacity: c.blob1Opacity, size: 420)
                        .position(x: g.size.width * 0.12 + (drift ? 18 : 0), y: g.size.height * 0.12 + (drift ? 10 : 0))
                    blob(c.blob2, opacity: c.blob2Opacity, size: 320)
                        .position(x: g.size.width * 0.95 - (drift ? 14 : 0), y: g.size.height * 0.04 + (drift ? 16 : 0))
                }
            }
        }
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 14).repeatForever(autoreverses: true)) { drift = true }
        }
    }

    private func blob(_ color: Color, opacity: Double, size: CGFloat) -> some View {
        Circle()
            .fill(color)
            .frame(width: size, height: size)
            .blur(radius: 120)
            .opacity(opacity)
    }
}
