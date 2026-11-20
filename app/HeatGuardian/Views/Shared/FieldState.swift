// The six state tones of the background colour field (DESIGN.md §4): colours, title, SF Symbol, severity,
// and the mapping from the band's view-state (AppModel.viewState) to a tone.

import SwiftUI

enum FieldState: String, CaseIterable, Identifiable, Equatable {
    case ok, heat, water, danger, help, offline
    var id: String { rawValue }

    /// The table of DESIGN.md §4 (light). Dark mode deepens it (see `colors(dark:)`).
    struct Tones {
        var top: UInt32
        var mid: UInt32
        var blob1: UInt32
        var blob2: UInt32
        var accent: UInt32
    }

    var tones: Tones {
        switch self {
        case .ok: return Tones(top: 0xCCF0EB, mid: 0xDBEBFA, blob1: 0x13A89E, blob2: 0x003F88, accent: 0x13A89E)
        case .heat: return Tones(top: 0xFFF1DC, mid: 0xFDF3E6, blob1: 0xF9C74F, blob2: 0xF08A24, accent: 0xE07B12)
        case .water: return Tones(top: 0xFFE6CF, mid: 0xFCEBDD, blob1: 0xF08A24, blob2: 0x2F80ED, accent: 0x2F80ED)
        case .danger: return Tones(top: 0xFFD9CC, mid: 0xFBE1DA, blob1: 0xF0612A, blob2: 0xE5484D, accent: 0xD9480F)
        case .help: return Tones(top: 0xFFD1D3, mid: 0xFCDDDE, blob1: 0xE5484D, blob2: 0xB4232A, accent: 0xC62828)
        case .offline: return Tones(top: 0xE7EBEF, mid: 0xEEF1F4, blob1: 0x9AA5B1, blob2: 0xC3CBD3, accent: 0x6B7785)
        }
    }

    /// Resolved field colours for the current appearance. Bottom = near-white page (light) / deep page (dark).
    struct Colors {
        var top: Color
        var mid: Color
        var bottom: Color
        var blob1: Color
        var blob2: Color
        var blob1Opacity: Double
        var blob2Opacity: Double
    }

    func colors(dark: Bool) -> Colors {
        let t = tones
        if dark {
            let deep: UInt32 = 0x0A141E
            return Colors(top: Color(hex: mixHex(t.top, deep, 0.80)), mid: Color(hex: mixHex(t.mid, deep, 0.88)),
                          bottom: Color(hex: deep), blob1: Color(hex: mixHex(t.blob1, deep, 0.35)),
                          blob2: Color(hex: mixHex(t.blob2, deep, 0.35)), blob1Opacity: 0.40, blob2Opacity: 0.30)
        }
        return Colors(top: Color(hex: t.top), mid: Color(hex: t.mid), bottom: Color(hex: 0xF8FAFC),
                      blob1: Color(hex: t.blob1), blob2: Color(hex: t.blob2), blob1Opacity: 0.45, blob2Opacity: 0.35)
    }

    /// Icon accent (the orb symbol, the dots).
    var accent: Color { Color(hex: tones.accent) }

    /// The state word's colour: accent for danger / help (darkened to >= 4.5:1 on the field top), else primary text.
    var wordColor: Color {
        switch self {
        case .danger: return Color.dynamic(0xA83A0A, 0xFF9B73)
        case .help: return Color.dynamic(0xA61F1F, 0xFF8A8E)
        default: return Palette.textPrimary
        }
    }

    var symbol: String {
        switch self {
        case .ok: return "shield.checkmark"
        case .heat: return "sun.max"
        case .water: return "drop"
        case .danger, .help: return "exclamationmark.triangle"
        case .offline: return "antenna.radiowaves.left.and.right.slash"
        }
    }

    /// For the "warning" haptic when the state worsens.
    var severity: Int {
        switch self {
        case .offline: return 0
        case .ok: return 1
        case .heat: return 2
        case .water: return 3
        case .danger: return 4
        case .help: return 5
        }
    }

    var urgent: Bool { self == .danger || self == .help }

    /// DESIGN.md §4 title (EN / GR).
    func title(_ L: Strings, male: Bool = false) -> String {
        switch self {
        case .ok: return L.t("Όλα καλά", "All good")
        case .heat: return L.t("Ζεστή μέρα", "Hot day")
        case .water: return L.t("Ώρα για νερό", "Drink water")
        case .danger: return L.t("Πολλή ζέστη", "Too hot")
        case .help: return L.t("Βοήθεια", male ? "He needs help" : "She needs help")
        case .offline: return L.t("Χωρίς σύνδεση", "No connection")
        }
    }

    /// Band view-state -> tone. OK on a hot day (room >= 28 °C or a heat-wave plan for today) is the "heat" watch tone.
    static func from(viewState vs: String, hotDay: Bool) -> FieldState {
        switch vs {
        case "OK", "IMOK", "BATTERY": return hotDay ? .heat : .ok
        case "DRINK": return .water
        case "COOL": return .heat
        case "DANGER", "CHECK": return .danger
        case "HELP": return .help
        default: return .offline          // OFFLINE, NOT_WORN, WAIT
        }
    }

    /// The band states whose word is the band's own, not one of the six titles.
    static func ownTitle(_ vs: String) -> Bool { ["NOT_WORN", "WAIT", "BATTERY"].contains(vs) }
}
