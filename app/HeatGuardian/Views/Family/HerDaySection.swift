// Family · "Her Day" (HERDAY_SPEC.md §6, DESIGN.md §5 minimal glass): on Tomorrow (her usual day over tomorrow's
// heat, collisions, the band's suggestions) and on Today (the status line «At the market since 10:52» and whether
// she followed the suggestions). One glass card: heat strip (outside / house by hour, her outings as markers), then
// quiet rows (no boxes, no dividers), then one line on what her band holds. Everything comes from HerDayDisplay.

import SwiftUI

struct HerDaySection: View {
    var d: HerDayDisplay
    var L: Strings
    var showStatus = false

    var body: some View {
        VStack(alignment: .leading, spacing: Palette.s8) {
            Text(L.hdCaption)
                .font(.footnote.weight(.semibold))
                .tracking(0.6)
                .foregroundStyle(Palette.textOnField)
                .accessibilityAddTraits(.isHeader)
            if showStatus, let s = d.status {
                Label {
                    Text(s)
                        .font(.title3.weight(.semibold))
                        .foregroundStyle(Palette.textPrimary)
                        .contentTransition(.opacity)
                } icon: {
                    Image(systemName: d.statusSymbol ?? "mappin.and.ellipse")
                        .foregroundStyle(Palette.primary)
                }
                .padding(.bottom, Palette.s4)
                .accessibilityElement(children: .combine)
            }
            VStack(alignment: .leading, spacing: Palette.s12) {
                if !d.cells.isEmpty {
                    HeatStrip(cells: d.cells, outings: d.rows.filter { $0.kind != .air }, L: L)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(L.hdStripA11y)
                        .accessibilityValue(d.stripA11y)
                    Text(d.hotText)
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(Palette.textOnField)
                }
                if d.rows.isEmpty && !d.hasRoutine {
                    Text(L.hdNoRoutine)
                        .font(.footnote)
                        .foregroundStyle(Palette.textOnField)
                }
                ForEach(d.rows) { HerDayRowView(row: $0, L: L) }
                Text(d.bandLine)
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(Palette.textOnField)
                    .padding(.top, Palette.s4)
            }
            .padding(Palette.s16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .hgCard()
        }
    }
}

/// Two rows of hour cells (outside, house) from 06:00 to 24:00, her outings as small markers above.
struct HeatStrip: View {
    var cells: [HeatCell]
    var outings: [HerDayRow]
    var L: Strings

    private func color(_ level: Int) -> Color {
        switch level {
        case 2: return Palette.danger.opacity(0.75)
        case 1: return Palette.warm.opacity(0.85)
        default: return Palette.health.opacity(0.30)
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            GeometryReader { g in
                ForEach(outings) { o in
                    let x = (Double(o.minute) / 60 - Double(HerDayDisplay.firstHour)) / Double(24 - HerDayDisplay.firstHour)
                    Image(systemName: o.symbol)
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(o.kind == .collision ? Palette.heat : Palette.primary)
                        .padding(3)
                        .background(Palette.surface, in: Circle())
                        .position(x: max(10, min(g.size.width - 10, g.size.width * x)), y: g.size.height / 2)
                }
            }
            .frame(height: 22)
            row(L.hdOutside, cells.map { $0.outLevel })
            row(L.hdHouse, cells.map { $0.inLevel })
            HStack {
                ForEach([6, 12, 18, 24], id: \.self) { h in
                    Text(String(format: "%02d", h))
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(Palette.textOnField)
                    if h != 24 { Spacer(minLength: 0) }
                }
            }
            .padding(.leading, 52)
        }
    }

    private func row(_ title: String, _ levels: [Int]) -> some View {
        HStack(spacing: 6) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(Palette.textOnField)
                .frame(width: 46, alignment: .leading)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
            HStack(spacing: 2) {
                ForEach(Array(levels.enumerated()), id: \.offset) { _, lv in
                    RoundedRectangle(cornerRadius: 3, style: .continuous)
                        .fill(color(lv))
                        .frame(maxWidth: .infinity)
                        .frame(height: 14)
                }
            }
        }
    }
}

/// One quiet row: time · place symbol · place (+ detail) · the band's suggestion · what she did.
struct HerDayRowView: View {
    var row: HerDayRow
    var L: Strings

    var body: some View {
        HStack(alignment: .top, spacing: Palette.s12) {
            Text(row.time)
                .font(.body.weight(.semibold).monospacedDigit())
                .foregroundStyle(Palette.textPrimary)
                .frame(width: 56, alignment: .leading)
            Image(systemName: row.symbol)
                .foregroundStyle(row.kind == .collision ? Palette.heat : (row.kind == .air ? Palette.water : Palette.primary))
                .frame(width: 24)
                .overlay(alignment: .topTrailing) {
                    if row.kind == .collision {
                        Image(systemName: "exclamationmark.circle.fill")
                            .font(.caption2)
                            .foregroundStyle(Palette.danger)
                            .offset(x: 6, y: -6)
                    }
                }
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(row.title)
                    .font(.body.weight(row.kind == .collision ? .semibold : .regular))
                    .foregroundStyle(Palette.textPrimary)
                if let d = row.detail {
                    Text(d).font(.footnote).foregroundStyle(Palette.textOnField)
                }
                if let s = row.suggestion {
                    Text(s).font(.footnote.weight(.semibold)).foregroundStyle(Palette.primary)
                }
                if let o = row.outcome {
                    // icon in the tone colour, text in primary (text never uses the tone colours: contrast)
                    HStack(spacing: 4) {
                        Image(systemName: row.outcomeTone == .ok ? "checkmark.circle.fill" : (row.outcomeTone == .heat ? "sun.max.fill" : "circle"))
                            .foregroundStyle(row.outcomeTone.color)
                        Text(o).foregroundStyle(Palette.textPrimary)
                    }
                    .font(.footnote.weight(.semibold))
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
        .accessibilityHint(row.kind == .collision ? L.hdCollisionA11y : "")
    }
}

#Preview("Tomorrow · Her Day") { FamilyPreview(state: nil, tab: .tomorrow).onAppear { AppModel.shared.startDemo() } }
