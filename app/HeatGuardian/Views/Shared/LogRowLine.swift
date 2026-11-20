// A quiet log row (DESIGN.md §5 TODAY / HISTORY): icon, text, time — no boxes, no dividers.
// Planned (upcoming) nudges are shown hollow (lower opacity).

import SwiftUI

struct LogRowLine: View {
    let row: LogRow

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: Palette.s12) {
            Image(systemName: row.symbol)
                .font(.body)
                .foregroundStyle(row.tone.color)
                .frame(width: 24)
                .accessibilityHidden(true)
            Text(row.title)
                .font(.body)
                .foregroundStyle(Palette.textPrimary)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: Palette.s8)
            Text(row.timeText)
                .font(.subheadline.monospacedDigit())
                .foregroundStyle(Palette.textOnField)
        }
        .padding(.vertical, 6)
        .opacity(row.isUpcoming ? 0.6 : 1)
        .accessibilityElement(children: .combine)
    }
}
