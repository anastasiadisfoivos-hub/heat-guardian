// Ecosystem frames (ECOSYSTEM_SPEC.md §5 / §5b, band fw 0.9.7). EVENTS decoder + the new CMD encoders.
// All new CMDs are 20-byte frames: [0] opcode, payload, zero padding, [19] CRC-8/SMBUS over bytes 0..18
// (same CRC as every other frame). Little-endian. ios/tools/mirror_frames.py mirrors this file line by line.

import Foundation

extension HG {
    /// EVENTS characteristic (read + notify), HG_UUID("0004").
    static let events = "0C760004-038B-46D5-8532-954DD1C5E01D"

    enum EcoOp: UInt8 {
        case syncEvents = 0x16, familyMsg = 0x17, familyName = 0x18, routineSeed = 0x19, elderAction = 0x1A
        case dayPlan = 0x1B, visit = 0x1C          // Her Day (HERDAY_SPEC.md §4, band 0.9.8)
    }

    /// Max UTF-8 bytes of the family member's name in FAMILY_NAME (spec: 14, NUL padded).
    static let familyNameMaxBytes = 14
    /// CMD 0x1A ELDER_ACTION [1]: what the wearer did on the Elder-mode phone (the band acts as if pressed on it).
    enum ElderAction: UInt8 {
        case help = 1, nudgeDone = 2, helpCancel = 3, imOK = 4
    }

    /// WARN_SHOWN arg = the guardian's HG_ST_* code (fw frozen/hg_guardian.h; ECOSYSTEM_SPEC 5c), which is NOT the
    /// STATUS state code (HG.stateNames): 0 OK 1 DRINK 2 COOL 3 CHECK 4 DANGER 5 IMOK 6 NOT_WORN 7 BATTERY 8 HELP.
    static let guardianStateNames = ["OK", "DRINK", "COOL", "CHECK", "DANGER", "IMOK", "NOT_WORN", "BATTERY", "HELP"]

    /// "Not set" marker for an hour / minute byte in ROUTINE_SEED.
    static let unsetTime: UInt8 = 0xFF
}

/// One band event (EVENTS notify, 20 B):
/// [0]=0x03 | [1-2] u16 seq | [3-4] u16 boot_count | [5-8] u32 unix (0 = clock not set) | [9] type | [10] id/arg |
/// [11-18] reserved 0 | [19] crc8.
struct BandEvent: Equatable, Codable {
    enum Kind: Int, Codable {
        case nudgeShown = 1, nudgeDone = 2, nudgeMissed = 3, imOK = 4, help = 5, helpCancel = 6
        case familyMsgShown = 7, warnShown = 8
        case visit = 9, planItem = 10              // Her Day (HERDAY_SPEC.md §4); older apps ignore them
        case alertHeld = 11, allClear = 12, score = 13   // alert quality (ECOSYSTEM_SPEC 5e, band 0.9.9)
        // band 0.9.17 (FW-UI): power / haptic + the closed-loop action ladder (Model/Tower/LadderEvents.swift)
        case powerOff = 14, battCritical = 15, hapticLost = 16
        case ldRemind = 17, ldDone = 18, ldWorked = 19, ldEscalated = 20, ldNote = 21
        // band 0.9.18 (FW-POWER): low battery warning. Type 22 GAUGE is a LIVE frame (seq 0, never in the ring, never
        // a log row): it is not a Kind on purpose — AppModel.ingestEvent takes it before the store (Balance.swift).
        case battLow = 23
    }
    var seq: Int
    var boot: Int
    var unix: UInt32
    var kindRaw: Int
    var arg: Int
    /// Bytes 11..18 (8 bytes; all 0 for types 1-8). Types 9-13 carry their fields here.
    var ext: [UInt8] = []

    var kind: Kind? { Kind(rawValue: kindRaw) }
    /// The band's clock was set when it logged this event.
    var hasClock: Bool { unix != 0 }
}

extension Frames {
    static let eventsTag: UInt8 = 0x03

    static func decodeEvent(_ b: [UInt8]) throws -> BandEvent {
        guard b.count == 20 else { throw FrameError(message: "EVENTS length \(b.count) (expected 20)") }
        guard crc8(b, count: 19) == b[19] else { throw FrameError(message: "EVENTS CRC mismatch") }
        guard b[0] == eventsTag else { throw FrameError(message: "EVENTS tag 0x\(String(format: "%02x", b[0])) (expected 0x03)") }
        let seq = Int(b[1]) | (Int(b[2]) << 8)
        let boot = Int(b[3]) | (Int(b[4]) << 8)
        let unix = UInt32(b[5]) | (UInt32(b[6]) << 8) | (UInt32(b[7]) << 16) | (UInt32(b[8]) << 24)
        return BandEvent(seq: seq, boot: boot, unix: unix, kindRaw: Int(b[9]), arg: Int(b[10]), ext: Array(b[11..<19]))
    }

    /// Builds an EVENTS frame (tests, demo).
    static func encodeEvent(_ e: BandEvent) -> [UInt8] {
        var b = [UInt8](repeating: 0, count: 19)
        b[0] = eventsTag
        b[1] = UInt8(e.seq & 255); b[2] = UInt8((e.seq >> 8) & 255)
        b[3] = UInt8(e.boot & 255); b[4] = UInt8((e.boot >> 8) & 255)
        let u = le32(e.unix)
        b[5] = u[0]; b[6] = u[1]; b[7] = u[2]; b[8] = u[3]
        b[9] = UInt8(truncatingIfNeeded: e.kindRaw)
        b[10] = UInt8(truncatingIfNeeded: e.arg)
        for (i, x) in e.ext.prefix(8).enumerated() { b[11 + i] = x }
        return seal(b)
    }

    /// Phone -> band writes that go ahead of the on-connect writes in BandLink's queue (after other urgent ones, in
    /// order): TIME, FAMILY_ACK, SYNC_EVENTS, FAMILY_MSG, ELDER_ACTION (HELP from her phone).
    static func isUrgentCommand(_ b: [UInt8]) -> Bool {
        guard let op = b.first else { return false }
        return [HG.Op.time.rawValue, HG.Op.familyAck.rawValue, HG.EcoOp.syncEvents.rawValue, HG.EcoOp.familyMsg.rawValue,
                HG.EcoOp.elderAction.rawValue].contains(op)
    }

    /// [op] + payload, zero padded to 19 bytes, + CRC = 20 bytes.
    static func frame20(_ op: UInt8, _ payload: [UInt8]) -> [UInt8] {
        var b: [UInt8] = [op]
        b.append(contentsOf: payload.prefix(18))
        while b.count < 19 { b.append(0) }
        return seal(b)
    }

    /// 0x16 SYNC_EVENTS: [1-2] u16 since_seq, [3-4] u16 boot_count.
    static func cmdSyncEvents(sinceSeq: Int, boot: Int) -> [UInt8] {
        frame20(HG.EcoOp.syncEvents.rawValue, [UInt8(sinceSeq & 255), UInt8((sinceSeq >> 8) & 255),
                                               UInt8(boot & 255), UInt8((boot >> 8) & 255)])
    }

    /// 0x17 FAMILY_MSG: [1] msg (1 «…: σας καλεί», 2 «…: έρχεται», 3 «…: είδε το μήνυμα ✓»).
    static func cmdFamilyMsg(_ msg: UInt8) -> [UInt8] {
        frame20(HG.EcoOp.familyMsg.rawValue, [msg])
    }

    /// The name cut to at most 14 UTF-8 bytes on a character boundary (never half a Greek letter).
    static func familyNameBytes(_ name: String) -> [UInt8] {
        var out: [UInt8] = []
        for ch in name.trimmingCharacters(in: .whitespacesAndNewlines)
            where !ch.unicodeScalars.contains(where: { $0.properties.generalCategory == .control }) {
            let u = Array(String(ch).utf8)
            if out.count + u.count > HG.familyNameMaxBytes { break }
            out += u
        }
        return out
    }

    /// 0x18 FAMILY_NAME: [1..14] UTF-8 name, NUL padded.
    static func cmdFamilyName(_ name: String) -> [UInt8] {
        frame20(HG.EcoOp.familyName.rawValue, familyNameBytes(name))
    }

    /// 0x19 ROUTINE_SEED: [1-2] wake hh,mm [3-4] bed hh,mm [5-8] nap from hh,mm to hh,mm [9-12] out1 from/to
    /// [13-16] out2 from/to [17] flags (bit0 A/C at home; 0xFF = not stated) [18] 0. A time that is not set is 0xFF,0xFF.
    static func cmdRoutineSeed(wake: Int?, bed: Int?, napFrom: Int?, napTo: Int?,
                               out1From: Int?, out1To: Int?, out2From: Int?, out2To: Int?, ac: Bool?) -> [UInt8] {
        func hm(_ minuteOfDay: Int?) -> [UInt8] {
            guard let m = minuteOfDay, m >= 0, m < 1440 else { return [HG.unsetTime, HG.unsetTime] }
            return [UInt8(m / 60), UInt8(m % 60)]
        }
        var p: [UInt8] = []
        for t in [wake, bed, napFrom, napTo, out1From, out1To, out2From, out2To] { p += hm(t) }
        p.append(ac.map { $0 ? 1 : 0 } ?? 0xFF)
        return frame20(HG.EcoOp.routineSeed.rawValue, p)
    }

    /// 0x1A ELDER_ACTION: [1] action (1 HELP, 2 NUDGE_DONE, 3 HELP_CANCEL, 4 IM_OK), [2] nudge id (NUDGE_DONE only,
    /// else 0), [3..18] 0, [19] CRC-8.
    static func cmdElderAction(_ action: HG.ElderAction, nudge: Int = 0) -> [UInt8] {
        let id: UInt8 = action == .nudgeDone ? UInt8(truncatingIfNeeded: nudge) : 0
        return frame20(HG.EcoOp.elderAction.rawValue, [action.rawValue, id])
    }
}

// MARK: - Her Day (HERDAY_SPEC.md §3-§4, band 0.9.8)
// CMD 0x1B DAY_PLAN (phone -> band, one frame per item, up to 6 per day), CMD 0x1C VISIT (her phone -> band),
// EVENTS type 9 VISIT and type 10 PLAN_ITEM (band -> every phone). ios/tools/mirror_frames.py mirrors this section.

/// Shared place-type ids (HERDAY_SPEC §3). Coordinates never leave her phone: only this id goes to the band.
enum PlaceType: Int, Codable, CaseIterable, Identifiable {
    case home = 0, market = 1, church = 2, walk = 3, pharmacy = 4, cafe = 5, doctor = 6, other = 7
    var id: Int { rawValue }

    /// The Greek word the band uses inside its sentences («Αύριο: αγορά πριν τις 09:30»).
    var bandWord: String {
        switch self {
        case .home: return "έξοδο"          // the band's place_words[0] (home never appears in a suggestion)
        case .market: return "αγορά"
        case .church: return "εκκλησία"
        case .walk: return "βόλτα"
        case .pharmacy: return "φαρμακείο"
        case .cafe: return "καφενείο"
        case .doctor: return "γιατρό"
        case .other: return "έξοδο"
        }
    }

    var symbol: String {
        switch self {
        case .home: return "house.fill"
        case .market: return "basket.fill"
        case .church: return "building.columns.fill"
        case .walk: return "figure.walk"
        case .pharmacy: return "cross.case.fill"
        case .cafe: return "cup.and.saucer.fill"
        case .doctor: return "stethoscope"
        case .other: return "mappin.and.ellipse"
        }
    }
}

/// DAY_PLAN [4] kind / PLAN_ITEM arg.
enum DayPlanKind: Int, Codable {
    case outingShift = 1, airOpen = 2, heatwaveDay = 3
}

/// DAY_PLAN [10] (kind 1): 1 = go BEFORE the suggested time, 2 = go AFTER it.
enum ShiftDirection: Int, Codable {
    case before = 1, after = 2
}

/// CMD 0x1C [1] / EVENTS type 9 byte 11.
enum VisitEdge: Int, Codable {
    case arrive = 1, leave = 2
}

/// One Her Day plan item. Times are minutes of day (nil = n/a, 0xFF 0xFF on the wire); hours are 0-23.
/// Unused fields of kind 2 / 3 go out as 0 (band 0.9.8 stores and echoes them as 0; ECOSYSTEM_SPEC 5d).
struct DayPlanItem: Equatable, Codable {
    var day: Int                         // 0 today, 1 tomorrow
    var kind: DayPlanKind
    var place: PlaceType = .home         // kind 1
    var usual: Int? = nil                // kind 1: her usual start (minute of day)
    var suggested: Int? = nil            // kind 1 and 2 (minute of day)
    var direction: ShiftDirection? = nil // kind 1
    var hotFrom: Int = 0                 // kind 1: hot window, hours, to exclusive
    var hotTo: Int = 0
    var peakC: Int? = nil                // kind 1: peak outdoor °C at her usual time (0xFF = unknown). Not in PLAN_ITEM.
    var heatwaveDay: Int = 0             // kind 3
}

/// A decoded EVENTS type 9.
struct VisitEvent: Equatable {
    var edge: VisitEdge
    var place: PlaceType
    var unix: UInt32
}

extension HG {
    static let dayPlanMaxItems = 6
}

extension Frames {
    private static func hmBytes(_ m: Int?) -> [UInt8] {
        guard let m = m else { return [HG.unsetTime, HG.unsetTime] }
        return [UInt8(m / 60), UInt8(m % 60)]
    }
    private static func validHM(_ m: Int?) -> Bool { m.map { $0 >= 0 && $0 < 1440 } ?? true }

    /// The band's own field rules (HERDAY_SPEC §4), so the app never sends a frame the band answers with a field
    /// error: day <= 1, kind 1..3, place <= 7, h <= 23, m <= 59 (or 0xFF 0xFF), 1 <= index <= n <= 6.
    /// Band 0.9.8 (ECOSYSTEM_SPEC 5d): hot to_h is exclusive and may be 24 (until midnight); kind 1 needs from <= to;
    /// heat-wave day 0-31.
    static func cmdDayPlan(_ it: DayPlanItem, index: Int, of n: Int) throws -> [UInt8] {
        guard it.day == 0 || it.day == 1 else { throw FrameError(message: "DAY_PLAN day \(it.day)") }
        guard n >= 1, n <= HG.dayPlanMaxItems, index >= 1, index <= n else { throw FrameError(message: "DAY_PLAN index \(index)/\(n)") }
        guard validHM(it.usual), validHM(it.suggested) else { throw FrameError(message: "DAY_PLAN time") }
        var p = [UInt8](repeating: 0, count: 18)          // bytes 1..18
        p[0] = UInt8(it.day)
        p[1] = UInt8(index)
        p[2] = UInt8(n)
        p[3] = UInt8(it.kind.rawValue)
        switch it.kind {
        case .outingShift:
            guard let s = it.suggested, let dir = it.direction else { throw FrameError(message: "DAY_PLAN kind 1 needs a suggestion") }
            guard it.hotFrom >= 0, it.hotFrom <= 23, it.hotTo <= 24, it.hotFrom <= it.hotTo else { throw FrameError(message: "DAY_PLAN hot window") }
            p[4] = UInt8(it.place.rawValue)
            let u = hmBytes(it.usual), g = hmBytes(s)
            p[5] = u[0]; p[6] = u[1]
            p[7] = g[0]; p[8] = g[1]
            p[9] = UInt8(dir.rawValue)
            p[10] = UInt8(it.hotFrom)
            p[11] = UInt8(it.hotTo)
            p[12] = it.peakC.map { UInt8(max(0, min(254, $0))) } ?? 0xFF
        case .airOpen:
            guard let s = it.suggested else { throw FrameError(message: "DAY_PLAN kind 2 needs a time") }
            let g = hmBytes(s)
            p[7] = g[0]; p[8] = g[1]
        case .heatwaveDay:
            guard it.heatwaveDay >= 0, it.heatwaveDay <= 31 else { throw FrameError(message: "DAY_PLAN heat-wave day") }
            p[13] = UInt8(it.heatwaveDay)
        }
        return frame20(HG.EcoOp.dayPlan.rawValue, p)
    }

    /// DAY_PLAN with index 0 and n 0: "clear this day's plan".
    static func cmdDayPlanClear(day: Int) -> [UInt8] {
        frame20(HG.EcoOp.dayPlan.rawValue, [UInt8(day & 1), 0, 0])
    }

    /// All frames of one day's plan (index 1..n), or the clear frame when there are no items. Max 6 items.
    static func dayPlanFrames(_ items: [DayPlanItem], day: Int) throws -> [[UInt8]] {
        let its = Array(items.prefix(HG.dayPlanMaxItems))
        if its.isEmpty { return [cmdDayPlanClear(day: day)] }
        return try its.enumerated().map { i, it in
            var x = it
            x.day = day
            return try cmdDayPlan(x, index: i + 1, of: its.count)
        }
    }

    /// 0x1C VISIT: [1] 1 ARRIVE / 2 LEAVE, [2] place type, [3-6] u32 unix UTC, [7-18] 0.
    static func cmdVisit(_ edge: VisitEdge, place: PlaceType, unix: UInt32) -> [UInt8] {
        frame20(HG.EcoOp.visit.rawValue, [UInt8(edge.rawValue), UInt8(place.rawValue)] + le32(unix))
    }

    /// EVENTS type 9 (tests, demo): arg = place; byte 11 = edge; bytes 12-15 = u32 unix of the visit.
    static func visitEvent(seq: Int, boot: Int, unix: UInt32, _ v: VisitEvent) -> BandEvent {
        var x = [UInt8](repeating: 0, count: 8)
        x[0] = UInt8(v.edge.rawValue)
        let u = le32(v.unix)
        x[1] = u[0]; x[2] = u[1]; x[3] = u[2]; x[4] = u[3]
        return BandEvent(seq: seq, boot: boot, unix: unix, kindRaw: BandEvent.Kind.visit.rawValue, arg: v.place.rawValue, ext: x)
    }

    /// EVENTS type 10 (tests, demo = what the band echoes for a stored item): arg = kind; 11 place; 12 usual_h;
    /// 13 usual_m; 14 sugg_h; 15 sugg_m; 16 hot_from_h; 17 hot_to_h; 18 = day | direction << 1 | heatwave_day << 3.
    static func planItemEvent(seq: Int, boot: Int, unix: UInt32, _ it: DayPlanItem) -> BandEvent {
        var x = [UInt8](repeating: 0, count: 8)
        if it.kind == .outingShift {
            x[0] = UInt8(it.place.rawValue)
            let u = hmBytes(it.usual)
            x[1] = u[0]; x[2] = u[1]
            x[5] = UInt8(it.hotFrom); x[6] = UInt8(min(24, it.hotTo))
        }
        if it.kind != .heatwaveDay {
            let g = hmBytes(it.suggested)
            x[3] = g[0]; x[4] = g[1]
        }
        let dir = it.kind == .outingShift ? (it.direction?.rawValue ?? 0) : 0
        let hw = it.kind == .heatwaveDay ? min(31, it.heatwaveDay) : 0
        x[7] = UInt8((it.day & 1) | ((dir & 3) << 1) | ((hw & 31) << 3))
        return BandEvent(seq: seq, boot: boot, unix: unix, kindRaw: BandEvent.Kind.planItem.rawValue, arg: it.kind.rawValue, ext: x)
    }
}

extension BandEvent {
    private var x: [UInt8] { ext.count == 8 ? ext : ext + [UInt8](repeating: 0, count: max(0, 8 - ext.count)) }

    /// EVENTS type 9 fields; nil for other types or out-of-range values.
    var visit: VisitEvent? {
        guard kindRaw == Kind.visit.rawValue, let p = PlaceType(rawValue: arg), let e = VisitEdge(rawValue: Int(x[0])) else { return nil }
        let u = UInt32(x[1]) | (UInt32(x[2]) << 8) | (UInt32(x[3]) << 16) | (UInt32(x[4]) << 24)
        return VisitEvent(edge: e, place: p, unix: u)
    }

    /// EVENTS type 10 fields as a plan item (peakC is not in the event: nil). nil for other types / bad values.
    var planItem: DayPlanItem? {
        guard kindRaw == Kind.planItem.rawValue, let k = DayPlanKind(rawValue: arg) else { return nil }
        let b = x
        func hm(_ h: UInt8, _ m: UInt8) -> Int?? {
            if h == 0xFF && m == 0xFF { return .some(nil) }
            guard h <= 23, m <= 59 else { return nil }
            return .some(Int(h) * 60 + Int(m))
        }
        let packed = Int(b[7])
        var it = DayPlanItem(day: packed & 1, kind: k)
        switch k {
        case .outingShift:
            guard let p = PlaceType(rawValue: Int(b[0])), let u = hm(b[1], b[2]), let s = hm(b[3], b[4]), s != nil,
                  let d = ShiftDirection(rawValue: (packed >> 1) & 3), b[5] <= 23, b[6] <= 24 else { return nil }
            it.place = p; it.usual = u; it.suggested = s; it.direction = d
            it.hotFrom = Int(b[5]); it.hotTo = Int(b[6])
        case .airOpen:
            guard let s = hm(b[3], b[4]), s != nil else { return nil }
            it.suggested = s
        case .heatwaveDay:
            it.heatwaveDay = packed >> 3
        }
        return it
    }
}

// MARK: - Alert quality (ECOSYSTEM_SPEC 5e, band 0.9.9)
// EVENTS type 11 ALERT_HELD (the band held an alert back, and why), 12 ALL_CLEAR (a shown episode ended: «Πάλι όλα
// καλά»), 13 SCORE (the band's scorecard, 3 pages, counters since boot, saturating u8). STATUS and types 1-10 are
// unchanged; an app that does not know a type ignores it. ios/tools/mirror_frames.py mirrors this section.

/// ALERT_HELD [10]: what was held.
enum HeldWhat: Int, Codable, CaseIterable {
    case drink = 1, cool = 2, nudge = 3, bedtime = 4, check = 5   // 5 = CHECK audit (passed through, NOT held; not sent as an event by 0.9.9)
}

/// ALERT_HELD [11]: why (hg_fw_alert.h HG_AL_R_*).
enum HeldReason: Int, Codable, CaseIterable {
    case notWorn = 1, loose = 2, skin = 3, ppg = 4, shower = 5, sun = 6, persist = 7, repeated = 8, oneEvidence = 9
}

struct AlertHeld: Equatable {
    var what: HeldWhat
    var reason: HeldReason
    var arg: Int                 // [12] nudge id (what 3) or HG_ST_* state (what 1 / 2)
}

struct AllClear: Equatable {
    var peak: Int                // [10] 1 DRINK, 2 COOL, 3 CHECK / DANGER
    var minutes: Int             // [11-12] episode length, u16
    var familyCalled: Bool       // [13]
    var softTick: Bool           // [14]
}

/// SCORE page 0: sent per kind; page 1: held back per reason 1-8; page 2: see `ScoreCard`.
struct ScorePage: Equatable {
    var page: Int
    var values: [Int]            // bytes 11-18 as 8 u8
}

extension Frames {
    /// EVENTS type 11 (tests, demo).
    static func alertHeldEvent(seq: Int, boot: Int, unix: UInt32, _ h: AlertHeld) -> BandEvent {
        var x = [UInt8](repeating: 0, count: 8)
        x[0] = UInt8(h.reason.rawValue); x[1] = UInt8(truncatingIfNeeded: h.arg)
        return BandEvent(seq: seq, boot: boot, unix: unix, kindRaw: BandEvent.Kind.alertHeld.rawValue, arg: h.what.rawValue, ext: x)
    }

    /// EVENTS type 12 (tests, demo).
    static func allClearEvent(seq: Int, boot: Int, unix: UInt32, _ c: AllClear) -> BandEvent {
        var x = [UInt8](repeating: 0, count: 8)
        let mn = max(0, min(65535, c.minutes))
        x[0] = UInt8(mn & 255); x[1] = UInt8(mn >> 8); x[2] = c.familyCalled ? 1 : 0; x[3] = c.softTick ? 1 : 0
        return BandEvent(seq: seq, boot: boot, unix: unix, kindRaw: BandEvent.Kind.allClear.rawValue, arg: c.peak, ext: x)
    }

    /// EVENTS type 13 (tests, demo).
    static func scoreEvent(seq: Int, boot: Int, unix: UInt32, _ p: ScorePage) -> BandEvent {
        var x = [UInt8](repeating: 0, count: 8)
        for (i, v) in p.values.prefix(8).enumerated() { x[i] = UInt8(max(0, min(255, v))) }
        return BandEvent(seq: seq, boot: boot, unix: unix, kindRaw: BandEvent.Kind.score.rawValue, arg: p.page, ext: x)
    }
}

extension BandEvent {
    private var x8: [UInt8] { ext.count >= 8 ? Array(ext.prefix(8)) : ext + [UInt8](repeating: 0, count: 8 - ext.count) }

    /// EVENTS type 11 fields; nil for other types or unknown what / reason values.
    var alertHeld: AlertHeld? {
        guard kindRaw == Kind.alertHeld.rawValue, let w = HeldWhat(rawValue: arg), let r = HeldReason(rawValue: Int(x8[0])) else { return nil }
        return AlertHeld(what: w, reason: r, arg: Int(x8[1]))
    }

    /// EVENTS type 12 fields; nil for other types.
    var allClear: AllClear? {
        guard kindRaw == Kind.allClear.rawValue else { return nil }
        let b = x8
        return AllClear(peak: arg, minutes: Int(b[0]) | (Int(b[1]) << 8), familyCalled: b[2] != 0, softTick: b[3] != 0)
    }

    /// EVENTS type 13 fields; nil for other types or a page > 2.
    var scorePage: ScorePage? {
        guard kindRaw == Kind.score.rawValue, arg >= 0, arg <= 2 else { return nil }
        return ScorePage(page: arg, values: x8.map { Int($0) })
    }
}
