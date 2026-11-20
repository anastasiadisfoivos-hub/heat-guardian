// Visual language: one calm accent per state (same mapping as dashboard COLOR / SEVERITY), SF Symbols,
// grouped backgrounds, large rounded numerals.

import SwiftUI

enum Theme {
    static let ok = Color(red: 0.16, green: 0.66, blue: 0.52)       // calm green-teal
    static let drink = Color(red: 0.95, green: 0.65, blue: 0.15)    // amber
    static let cool = Color(red: 0.95, green: 0.45, blue: 0.16)     // orange
    static let danger = Color(red: 0.88, green: 0.20, blue: 0.23)   // red
    static let neutral = Color(red: 0.55, green: 0.58, blue: 0.63)
    static let wait = Color(red: 0.36, green: 0.52, blue: 0.80)     // quiet blue
    static let est = Color(red: 0.33, green: 0.55, blue: 0.95)      // the estimate band in charts
    static let sim = Color(red: 0.42, green: 0.36, blue: 0.90)      // SIMULATION tag (indigo)
    static let alertTop = Color(red: 0.86, green: 0.17, blue: 0.21)
    static let alertBottom = Color(red: 0.50, green: 0.05, blue: 0.11)

    static func color(_ vs: String) -> Color {
        switch vs {
        case "OK", "IMOK": return ok
        case "DRINK": return drink
        case "COOL": return cool
        case "DANGER", "CHECK", "HELP": return danger
        case "WAIT": return wait
        default: return neutral   // BATTERY, NOT_WORN, OFFLINE (no connection: the last state is greyed out)
        }
    }

    static func symbol(_ vs: String) -> String {
        switch vs {
        case "OK": return "checkmark"
        case "IMOK": return "checkmark.circle"
        case "DRINK": return "drop.fill"
        case "COOL": return "house.fill"
        case "DANGER": return "exclamationmark.triangle.fill"
        case "CHECK": return "questionmark"
        case "HELP": return "sos"
        case "BATTERY": return "battery.25"
        case "NOT_WORN": return "hand.raised.slash"
        case "OFFLINE": return "antenna.radiowaves.left.and.right.slash"
        default: return "antenna.radiowaves.left.and.right"
        }
    }

    /// 1 calm … 4 urgent (dashboard SEVERITY); also sets the chart staircase height (colour is never the only cue).
    static func severity(_ vs: String) -> Int {
        switch vs {
        case "DRINK": return 2
        case "COOL": return 3
        case "CHECK", "DANGER", "HELP": return 4
        case "WAIT": return 0
        default: return 1
        }
    }
}

struct Card<Content: View>: View {
    var padding: CGFloat = 20
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 12) { content }
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 26, style: .continuous).fill(Color(.secondarySystemGroupedBackground)))
    }
}

/// «ΠΡΟΣΟΜΟΙΩΣΗ / SIMULATION» — on every screen that shows replayed or demo data.
struct SimBadge: View {
    var text: String
    var onDark = false
    var body: some View {
        Label(text, systemImage: "play.rectangle.fill")
            .font(.caption.weight(.bold))
            .tracking(0.8)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .foregroundStyle(onDark ? Color.white : Theme.sim)
            .background(Capsule().fill(onDark ? Color.white.opacity(0.22) : Theme.sim.opacity(0.14)))
            .accessibilityLabel(text)
    }
}

extension Double {
    func f1(_ lang: Lang) -> String {
        formatted(.number.precision(.fractionLength(1)).locale(lang.locale))
    }
}

struct SectionTitle: View {
    var text: String
    var body: some View {
        Text(text).font(.subheadline.weight(.semibold)).foregroundStyle(.secondary)
    }
}
