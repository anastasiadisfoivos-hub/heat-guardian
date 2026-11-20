// The glass orb with the state's SF Symbol (DESIGN.md §5 TODAY: 132 pt). The symbol swaps with
// .contentTransition(.symbolEffect(.replace)); danger / help pulse gently (not with Reduce Motion).

import SwiftUI

struct GlassOrb: View {
    var symbol: String
    var tint: Color
    var size: CGFloat = 132
    var pulse = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        Image(systemName: symbol)
            .font(.system(size: size * 0.34, weight: .light))
            .foregroundStyle(tint)
            .contentTransition(.symbolEffect(.replace))
            .symbolEffect(.pulse, options: .repeating, isActive: pulse && !reduceMotion)
            .frame(width: size, height: size)
            .hgGlass(.regular, in: Circle())
            .accessibilityHidden(true)      // the state word next to it says the same thing
    }
}
