// The band's closed-loop ACTION LADDER events (FW-WORLDCLASS plan, OWNER DECISIONS Nov 19 18:22 + 18:23; band 0.9.17
// FW-UI): EVENTS 17 LD_REMIND, 18 LD_DONE, 19 LD_WORKED, 20 LD_ESCALATED, 21 LD_NOTE, plus the other 0.9.17 types
// 14 POWER_OFF, 15 BATT_CRITICAL (reserved for 0.9.18), 16 HAPTIC_LOST. Names follow the firmware (hg_fw_eco.h).
//
// FINAL (band 0.9.17, commit a486805, ECOSYSTEM_SPEC.md §5f). HeatGuardianTests/ladder_vectors_fw.json is made by the
// band's own ladder + packer (ios/tools/fw_ladder_vectors.c) from that commit; re-run the tool on any later firmware and
// diff the JSON. Type 20 arg 2 ("still heating after cooling down") is a glue-only escalation with NO frozen Danger state
// in STATUS: only this decoder sees it, so it MUST reach the Tower (SMSRouter) for that family SMS.
//   frame  [0]=0x03 [1-2] u16 seq [3-4] u16 boot [5-8] u32 unix [9] type [10] arg [11-18] x [19] crc8   (little-endian)
//   x      [11-12] i16  f20 x 100  = the band's 20-30 min core FORECAST in °C (0x8000 = unknown)
//          [13-14] i16  reference x 100 (f20 at her press; after an escalation f20 20 min earlier; 0x8000 = none)
//          [15-16] u16  extra: type 17 -> 0 first / 1 the 10-min repeat; 18 -> minutes from the reminder to her press;
//                       21 -> the step the note is about (1 water, 2 cooler place, 3 escalation)
//          [17-18] 0
//   type 17 LD_REMIND     arg 1 water, 2 cooler place
//   type 18 LD_DONE       arg = step (1 water, 2 cooler place): she pressed "done", the 20-min check starts
//   type 19 LD_WORKED     arg 1 water, 2 cooler place, 3 after an escalation: the forecast stopped rising
//   type 20 LD_ESCALATED  arg 1 the Danger line, 2 still heating after cooling down   (= the family alert)
//   type 21 LD_NOTE       arg 1 water did not help, 2 no response to a reminder, 3 responsive (pressed during escalation)
//   type 14 POWER_OFF     arg 1 the wearer (double press + confirm), 2 USB power-off command, 3 critical battery
//                         (0.9.18; x[0-1] u16 battery mV)
//   type 15 BATT_CRITICAL arg 1, x[0-1] u16 battery mV (0.9.18: the band switches itself off right after, POWER_OFF 3)
//   type 23 BATT_LOW      arg 1, x[0-1] u16 battery mV (0.9.18: «Χαμηλή μπαταρία. Φορτίστε απόψε.»)
// Type 22 GAUGE (0.9.18) is a live frame, not a ladder event: BandGauge in Balance.swift. Battery vectors:
// HeatGuardianTests/gauge_vectors_fw.json (copy of fw/09_guardian/gauge_vectors.json, fw commit 106b751).
//   type 16 HAPTIC_LOST   arg = the pattern the motor could not play (the screen flashed instead)
// Unknown types and unknown args are IGNORED and counted / logged (BandEventDiagnostics), never a crash.

import Foundation

enum LadderStep: Int, Codable, Equatable {
    case water = 1, coolerPlace = 2, escalation = 3
}

enum EscalationReason: Int, Codable, Equatable {
    case dangerLine = 1, stillHeating = 2
}

enum LadderNoteKind: Int, Codable, Equatable {
    case waterDidNotHelp = 1, noResponse = 2, responsive = 3
}

/// One 0.9.17 band event, decoded. Temperatures are the band's FORECAST (°C), shown only as context, never as a measurement.
enum LadderEvent: Equatable {
    case reminder(step: LadderStep, isRepeat: Bool, forecastC: Double?)
    case done(step: LadderStep, minutesAfterReminder: Int, forecastC: Double?)
    case worked(step: LadderStep, forecastC: Double?, referenceC: Double?)
    case escalated(reason: EscalationReason, forecastC: Double?, referenceC: Double?)
    case note(LadderNoteKind, about: LadderStep?, forecastC: Double?, referenceC: Double?)
    case powerOff(byWearer: Bool)
    /// POWER_OFF arg 3 (0.9.18): the band switched itself off at critical battery (mV nil = not reported).
    case powerOffBattery(mV: Int?)
    case batteryCritical(mV: Int?)
    /// BATT_LOW (type 23, 0.9.18): the band asked her to charge tonight.
    case batteryLow(mV: Int?)
    case hapticLost(pattern: Int)

    /// 0.9.17 types 14-21 + 0.9.18 type 23 (type 22 GAUGE is a live frame: BandGauge).
    static let ladderTypes: Set<Int> = Set(14...21).union([23])

    /// nil = not a 0.9.17 type, or an arg this app does not know (logged).
    static func decode(_ e: BandEvent) -> LadderEvent? {
        guard ladderTypes.contains(e.kindRaw) else { return nil }
        let x = e.ext.count >= 8 ? e.ext : e.ext + [UInt8](repeating: 0, count: 8 - e.ext.count)
        let f20 = c100(x[0], x[1]), ref = c100(x[2], x[3])
        let extra = Int(x[4]) | (Int(x[5]) << 8)
        let u16 = Int(x[0]) | (Int(x[1]) << 8)
        let mV: Int? = u16 == 0 ? nil : u16
        func bad() -> LadderEvent? {
            BandEventDiagnostics.shared.unknownArg(type: e.kindRaw, arg: e.arg)
            return nil
        }
        switch e.kindRaw {
        case 14:
            if e.arg == 3 { return .powerOffBattery(mV: mV) }
            return e.arg == 1 || e.arg == 2 ? .powerOff(byWearer: e.arg == 1) : bad()
        case 15: return .batteryCritical(mV: mV)            // any arg: a dead battery is never dropped
        case 23: return .batteryLow(mV: mV)
        case 16: return .hapticLost(pattern: e.arg)
        case 17:
            guard let s = LadderStep(rawValue: e.arg), s != .escalation else { return bad() }
            return .reminder(step: s, isRepeat: extra != 0, forecastC: f20)
        case 18:
            guard let s = LadderStep(rawValue: e.arg), s != .escalation else { return bad() }
            return .done(step: s, minutesAfterReminder: extra, forecastC: f20)
        case 19:
            guard let s = LadderStep(rawValue: e.arg) else { return bad() }
            return .worked(step: s, forecastC: f20, referenceC: ref)
        case 20:
            guard let r = EscalationReason(rawValue: e.arg) else { return bad() }
            return .escalated(reason: r, forecastC: f20, referenceC: ref)
        case 21:
            guard let n = LadderNoteKind(rawValue: e.arg) else { return bad() }
            return .note(n, about: LadderStep(rawValue: extra), forecastC: f20, referenceC: ref)
        default: return nil
        }
    }

    /// (type, arg, x) of this event, laid out exactly like the band (demo + tests; checked against the fw vectors).
    var encoded: (type: Int, arg: Int, x: [UInt8]) {
        func pack(_ a: Double?, _ b: Double?, _ u: Int) -> [UInt8] {
            let ca = LadderEvent.i16(a), cb = LadderEvent.i16(b)
            return [UInt8(ca & 255), UInt8(ca >> 8), UInt8(cb & 255), UInt8(cb >> 8), UInt8(u & 255), UInt8((u >> 8) & 255), 0, 0]
        }
        func mv(_ v: Int?) -> [UInt8] {
            let u = max(0, min(65535, v ?? 0))
            return [UInt8(u & 255), UInt8(u >> 8), 0, 0, 0, 0, 0, 0]
        }
        switch self {
        case .reminder(let s, let r, let f): return (17, s.rawValue, pack(f, nil, r ? 1 : 0))
        case .done(let s, let m, let f): return (18, s.rawValue, pack(f, nil, m))
        case .worked(let s, let f, let r): return (19, s.rawValue, pack(f, r, 0))
        case .escalated(let w, let f, let r): return (20, w.rawValue, pack(f, r, 0))
        case .note(let n, let a, let f, let r): return (21, n.rawValue, pack(f, r, a?.rawValue ?? 0))
        case .powerOff(let w): return (14, w ? 1 : 2, [UInt8](repeating: 0, count: 8))
        case .powerOffBattery(let v): return (14, 3, mv(v))
        case .batteryCritical(let v): return (15, 1, mv(v))
        case .batteryLow(let v): return (23, 1, mv(v))
        case .hapticLost(let p): return (16, p, [UInt8](repeating: 0, count: 8))
        }
    }

    /// i16 little-endian x100 -> °C (0x8000 = unknown).
    static func c100(_ lo: UInt8, _ hi: UInt8) -> Double? {
        let u = UInt16(lo) | (UInt16(hi) << 8)
        guard u != 0x8000 else { return nil }
        return Double(Int16(bitPattern: u)) / 100
    }
    /// °C -> i16 x100 as its UInt16 bit pattern (nil -> 0x8000).
    static func i16(_ c: Double?) -> Int {
        guard let c = c, c.isFinite else { return 0x8000 }
        return Int(UInt16(bitPattern: Int16(max(-32767, min(32767, (c * 100).rounded())))))
    }
}

/// Band 0.9.17-demo-b7n, ANY replay (`replay` and `replay noresp`): ladder EVENTS (17-21) of the band's SIMULATED episode carry
/// this in frame byte 18 (x[7]; 0 in a real event). The Tower treats them as SIMULATION (dry-run unless «Αποστολή SMS και στην
/// προσομοίωση»); History shows them with the SIM badge (DayStory).
enum BandReplay {
    static let marker: UInt8 = 0xD5
    static let kinds: Set<LogKind> = [.ldRemind, .ldDone, .ldWorked, .ldEscalated, .ldNote]
}

extension LogEntry {
    /// A ladder event from the band's own simulated replay (`replay` / `replay noresp`), not from her body.
    var isBandReplay: Bool {
        guard origin == .band, BandReplay.kinds.contains(kind), let x = ext, x.count >= 8 else { return false }
        return x[7] == BandReplay.marker
    }
}

extension BandEvent {
    /// The 0.9.17 ladder / power / haptic event or a 0.9.18 battery event (nil for other types).
    var ladder: LadderEvent? { LadderEvent.decode(self) }
}

/// Unknown EVENTS types / args: ignored, counted and logged (Settings › Diagnostics shows them). Never stored as rows.
final class BandEventDiagnostics {
    static let shared = BandEventDiagnostics()
    private(set) var unknownTypes: [Int: Int] = [:]
    private(set) var unknownArgs: [String: Int] = [:]
    /// Where the log line goes (print by default; tests replace it).
    var log: (String) -> Void = { print("[HG] " + $0) }

    func unknownType(_ t: Int) {
        unknownTypes[t, default: 0] += 1
        if unknownTypes[t] == 1 { log("EVENTS type \(t) unknown to this app: ignored") }
    }
    func unknownArg(type: Int, arg: Int) {
        let k = "\(type)/\(arg)"
        unknownArgs[k, default: 0] += 1
        if unknownArgs[k] == 1 { log("EVENTS type \(type) arg \(arg) unknown to this app: ignored") }
    }
    var summary: String? {
        let a = unknownTypes.sorted { $0.key < $1.key }.map { "type \($0.key) ×\($0.value)" }
        let b = unknownArgs.sorted { $0.key < $1.key }.map { "\($0.key) ×\($0.value)" }
        let all = a + b
        return all.isEmpty ? nil : "ignored EVENTS: " + all.joined(separator: ", ")
    }
    func reset() { unknownTypes = [:]; unknownArgs = [:] }
}
