// Screenshot / preview overrides. Every screen reads `\.hgOverride`; the app fills it from launch arguments
// (-HGState ok|heat|water|danger|check|help|offline, -HGFamilyMsg 1|2|3, -HGAlert help|danger|family,
// -HGFit checking|ok|loose|off|charging|noLink = the fit check open in that fixed state, -HGFitMock YES = the scripted
// fit-check filming mock without starting the demo) and
// #Preview blocks set it directly. With no override the screens show the live (or demo) data.

import SwiftUI

enum OverrideState: String, CaseIterable {
    case ok, heat, water, danger, check, help, offline

    var field: FieldState {
        switch self {
        case .ok: return .ok
        case .heat: return .heat
        case .water: return .water
        case .danger, .check: return .danger
        case .help: return .help
        case .offline: return .offline
        }
    }
    /// The band view-state this override stands for.
    var viewState: String {
        switch self {
        case .ok: return "OK"
        case .heat: return "COOL"
        case .water: return "DRINK"
        case .danger: return "DANGER"
        case .check: return "CHECK"
        case .help: return "HELP"
        case .offline: return "OFFLINE"
        }
    }
}

struct UIOverride: Equatable {
    var state: OverrideState?
    var familyMsg: Int?
    var alert: AlertInfo.Kind?
    /// Fit check shown in this fixed state (screenshots); nil = the band's (or the mock's) verdict.
    var fit: FitState?
    /// The fit check's FILMING MOCK even outside demo mode (still never while a real band is connected).
    var fitMock = false

    static let none = UIOverride()

    /// From launch arguments (they land in UserDefaults' argument domain).
    static func fromLaunchArguments() -> UIOverride {
        let ud = UserDefaults.standard
        var o = UIOverride()
        o.state = OverrideState(rawValue: ud.string(forKey: "HGState") ?? "")
        let fm = ud.integer(forKey: "HGFamilyMsg")
        o.familyMsg = (1...3).contains(fm) ? fm : nil
        switch ud.string(forKey: "HGAlert") {
        case "help": o.alert = .help
        case "danger": o.alert = .danger
        case "family": o.alert = .family
        default: o.alert = nil
        }
        o.fit = FitState(rawValue: ud.string(forKey: "HGFit") ?? "")
        o.fitMock = ud.bool(forKey: "HGFitMock")
        return o
    }
}

private struct UIOverrideKey: EnvironmentKey {
    static let defaultValue = UIOverride.none
}

extension EnvironmentValues {
    var hgOverride: UIOverride {
        get { self[UIOverrideKey.self] }
        set { self[UIOverrideKey.self] = newValue }
    }
}

enum SampleData {
    /// A plausible STATUS frame for screenshots of the alert (also used by previews).
    static func status(_ vs: String) -> StatusFrame {
        let code: Int = HG.stateNames.firstIndex(of: vs) ?? 0
        let ok: Bool = vs == "OK"
        let core: Double = ok ? 37.1 : 38.4
        let hr: Int = ok ? 72 : 96
        let room: Double = ok ? 26.0 : 31.0
        let alarm: Int? = vs == "CHECK" ? 900 : nil
        return StatusFrame(version: 1, familyPending: vs == "CHECK", notWorn: false, stateCode: code, contactOK: true,
                           timeSynced: true, charging: false, home: true, ppgValid: true, coreC: core,
                           halfRangeC: 0.4, hrBpm: hr, hrQ: 4, t1C: 34.0, t2C: 33.0,
                           tairC: room, rhPct: 45, batteryPct: 80, minuteCounter: 900,
                           alarmId16: alarm, routineScore: nil, activity: nil)
    }

    static func alert(_ kind: AlertInfo.Kind) -> AlertInfo {
        let vs = kind == .help ? "HELP" : (kind == .danger ? "DANGER" : "CHECK")
        return AlertInfo(kind: kind, alarmId: kind == .family ? 900 : nil, source: .demo, at: Date(), frame: status(vs))
    }
}
