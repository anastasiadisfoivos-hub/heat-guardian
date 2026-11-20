// The one "Next" card (DESIGN.md §5 TODAY): icon, title, small origin line, time — regular glass, radius 26.
// HELP turns it into a solid accent card with white text («Call her now»), see HelpNextCard.

import SwiftUI

struct NextItem: Equatable {
    var symbol: String
    var title: String
    var origin: String
    var time: String
    var tone: Tone
}

struct NextCard: View {
    var item: NextItem

    var body: some View {
        HStack(spacing: Palette.s16) {
            Image(systemName: item.symbol)
                .font(.title3)
                .foregroundStyle(item.tone.color)
                .frame(width: 28)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(item.title)
                    .font(.body.weight(.semibold))
                    .foregroundStyle(Palette.textPrimary)
                    .fixedSize(horizontal: false, vertical: true)
                Text(item.origin)
                    .font(.footnote)
                    .foregroundStyle(Palette.textOnField)
            }
            Spacer(minLength: Palette.s8)
            Text(item.time)
                .font(.body.weight(.semibold).monospacedDigit())
                .foregroundStyle(Palette.textPrimary)
                .contentTransition(.numericText())
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .hgCard()
        .accessibilityElement(children: .combine)
    }
}

/// HELP: solid accent card «Call her now · Tap to call · she is waiting · Call». White on #C62828 = 5.6:1.
struct HelpNextCard: View {
    var title: String
    var subtitle: String
    var action: String
    var onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: Palette.s16) {
                Image(systemName: "phone.fill")
                    .font(.title3)
                    .frame(width: 28)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.body.weight(.bold))
                    Text(subtitle).font(.footnote)
                }
                Spacer(minLength: Palette.s8)
                Text(action).font(.body.weight(.bold))
            }
            .foregroundStyle(Color.white)
            .padding(.horizontal, 20)
            .padding(.vertical, 18)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Palette.helpSolid, in: RoundedRectangle(cornerRadius: Palette.cardRadius, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
    }
}
