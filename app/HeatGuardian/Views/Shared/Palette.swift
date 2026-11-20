// Palette F "Santorini guard" (DESIGN.md §3): tokens with light + dark variants, spacing and radii.
// Dark mode deepens the colour and keeps the hue. Text that sits on the colour field is darkened (never lightened)
// until it reaches 4.5:1 (DESIGN.md §2.5); the measured values are listed in ios/RESEARCH_UI.md.

import SwiftUI
import UIKit

extension UIColor {
    /// 0xRRGGBB.
    convenience init(hex: UInt32, alpha: CGFloat = 1) {
        self.init(red: CGFloat((hex >> 16) & 0xFF) / 255, green: CGFloat((hex >> 8) & 0xFF) / 255,
                  blue: CGFloat(hex & 0xFF) / 255, alpha: alpha)
    }
}

extension Color {
    init(hex: UInt32) { self.init(uiColor: UIColor(hex: hex)) }

    /// A colour that follows light / dark mode.
    static func dynamic(_ light: UInt32, _ dark: UInt32) -> Color {
        Color(uiColor: UIColor { tc in UIColor(hex: tc.userInterfaceStyle == .dark ? dark : light) })
    }
}

/// Mixes two 0xRRGGBB colours: t = 0 -> a, t = 1 -> b.
func mixHex(_ a: UInt32, _ b: UInt32, _ t: Double) -> UInt32 {
    func ch(_ v: UInt32, _ s: UInt32) -> Double { Double((v >> s) & 0xFF) }
    func mix(_ s: UInt32) -> UInt32 {
        let v = ch(a, s) * (1 - t) + ch(b, s) * t
        return UInt32(max(0, min(255, v.rounded()))) << s
    }
    return mix(16) | mix(8) | mix(0)
}

enum Palette {
    // brand
    static let primary = Color.dynamic(0x003F88, 0x8DB8F0)
    static let health = Color(hex: 0x13A89E)
    static let soft = Color.dynamic(0xE3F1F8, 0x16303F)
    static let warm = Color(hex: 0xF9C74F)
    // surfaces + text
    static let page = Color.dynamic(0xF2F6FA, 0x0A141E)
    static let surface = Color.dynamic(0xFFFFFF, 0x16222E)
    static let textPrimary = Color.dynamic(0x0B1B2B, 0xF2F6FA)
    static let textSecondary = Color.dynamic(0x5B6B7B, 0xA9B6C2)
    /// Secondary text ON the colour field: #5B6B7B is only ~4.0:1 on the help / danger tops, so it is darkened.
    static let textOnField = Color.dynamic(0x4A5764, 0xB8C4CF)
    static let hairline = Color.dynamic(0xDCE4EC, 0x2A3846)
    // states
    static let ok = Color(hex: 0x13A89E)
    static let water = Color(hex: 0x2F80ED)
    static let heat = Color(hex: 0xF08A24)
    static let danger = Color(hex: 0xE5484D)
    static let offline = Color(hex: 0x9AA5B1)
    /// Solid HELP surfaces (white text 5.6:1).
    static let helpSolid = Color(hex: 0xC62828)
    /// SIMULATION tag (indigo), kept from the backend placeholder UI.
    static let sim = Color.dynamic(0x5B4FD6, 0xA59CFF)

    // spacing / radii (DESIGN.md §3)
    static let s4: CGFloat = 4, s8: CGFloat = 8, s12: CGFloat = 12, s16: CGFloat = 16, s24: CGFloat = 24, s32: CGFloat = 32
    static let cardRadius: CGFloat = 26
}

extension Tone {
    /// Row / icon accent for a semantic tone (icons only; text never uses these on the field).
    var color: Color {
        switch self {
        case .ok: return Palette.ok
        case .water: return Palette.water
        case .heat: return Palette.heat
        case .danger: return Palette.danger
        case .offline: return Color.dynamic(0x6B7785, 0x9AA5B1)
        case .family: return Palette.primary
        case .neutral: return Palette.textSecondary
        }
    }
}
