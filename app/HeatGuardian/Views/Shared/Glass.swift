// Liquid Glass with the Reduce Transparency fallback DESIGN.md §2.5 asks for (solid surface + hairline).
// Only for custom floating elements (orb, cards, pills): system bars, tab bar, toolbar items and glass button styles
// get their glass from the system and must not be wrapped again (no glass on glass).

import SwiftUI

struct HGGlass<S: Shape>: ViewModifier {
    var glass: Glass
    var shape: S
    @Environment(\.accessibilityReduceTransparency) private var reduceTransparency

    @ViewBuilder
    func body(content: Content) -> some View {
        if reduceTransparency {
            content
                .background(Palette.surface, in: shape)
                .overlay(shape.stroke(Palette.hairline, lineWidth: 1))
        } else {
            content.glassEffect(glass, in: shape)
        }
    }
}

extension View {
    /// `.glassEffect(glass, in: shape)`, or a solid surface when Reduce Transparency is on.
    func hgGlass<S: Shape>(_ glass: Glass = .regular, in shape: S) -> some View {
        modifier(HGGlass(glass: glass, shape: shape))
    }

    /// The standard card: regular glass, 26 pt continuous corners.
    func hgCard() -> some View {
        hgGlass(.regular, in: RoundedRectangle(cornerRadius: Palette.cardRadius, style: .continuous))
    }
}
