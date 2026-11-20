// «● ● ● ○ ○  prevention 3/5» (DESIGN.md §5 TODAY): filled = a prevention nudge done today.

import SwiftUI

struct PreventionDots: View {
    var done: Int
    var total: Int
    var label: String          // "prevention" / «πρόληψη»
    var a11y: String           // "Prevention: 3 of 5 done"

    var body: some View {
        HStack(spacing: Palette.s8) {
            HStack(spacing: 6) {
                ForEach(0..<max(total, 1), id: \.self) { i in
                    Circle()
                        .fill(i < done ? Palette.ok : Palette.textOnField.opacity(0.55))
                        .frame(width: 8, height: 8)
                }
            }
            Text("\(label) \(done)/\(total)")
                .font(.footnote.weight(.semibold).monospacedDigit())
                .foregroundStyle(Palette.textOnField)
                .contentTransition(.numericText())
                .padding(.leading, 4)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(a11y)
    }
}
