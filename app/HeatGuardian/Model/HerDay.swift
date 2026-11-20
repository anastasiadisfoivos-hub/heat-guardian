// "Her Day" engine (HERDAY_SPEC.md §1, §6): her learned routine laid over one day's hourly forecast. Pure Swift,
// no UI / location imports: unit-tested by HeatGuardianTests/HerDayTests.swift, run on Linux by tools/LinuxCheck.swift
// and mirrored line by line in tools/mirror_frames.py (herday_* functions) on the same cases.
//
// Rules (spec §6):
//  - hot hour = forecast outdoor T >= 30 °C, or the plan marks the hour AVOID; a hot window = consecutive hot hours
//    [from, to) (to exclusive).
//  - an expected outing collides when ANY part of it, [start, start + typical duration), overlaps a hot window
//    (Foivos, Nov 18: not only when it starts inside one). The window is the first one it overlaps.
//    Suggestion: the latest slot >= 07:00 that ends before that window (direction 1, «πριν τις»), else the first slot >= 30 min after the window ends that
//    ends before her bedtime - 60 (direction 2, «μετά τις»). Slots move in 15-min steps and never touch a hot hour.
//    No slot -> the collision is still kept for the UI, but no OUTING_SHIFT item is sent.
//  - AIR_OPEN = the first hour >= 18:00 where outdoor T < predicted indoor T - 1 °C, only on a day where heat at
//    home matters (heat day, hot night, or indoor >= 28 °C) — the band only says what she could not know herself.
//  - HEATWAVE_DAY from the forecast flags (heat_day + wave_day).
//  - at most 6 items: OUTING_SHIFTs by usual time first, then AIR_OPEN, then HEATWAVE_DAY (the last two are kept).

import Foundation

/// One expected outing of her usual day (from RoutineModel).
struct Outing: Equatable, Codable, Identifiable {
    var place: PlaceType
    var start: Int               // minute of day (typical start)
    var duration: Int            // minutes (typical)
    var daily: Bool              // a daily habit (seen on >= 4 weekdays) rather than a weekday one
    var count: Int               // how many visits it was learned from
    var id: String { "\(place.rawValue)@\(start)" }
}

/// Consecutive hot hours [from, to), to exclusive (to may be 24).
struct HotWindow: Equatable, Codable {
    var from: Int
    var to: Int
    func contains(minute m: Int) -> Bool { m >= from * 60 && m < to * 60 }
    /// True when [start, start + duration) shares at least one minute with the window (duration < 1 counts as 1).
    func overlaps(start: Int, duration: Int) -> Bool { start < to * 60 && start + max(1, duration) > from * 60 }
}

struct Collision: Equatable, Identifiable {
    var outing: Outing
    var window: HotWindow
    var peakC: Int?              // peak outdoor °C over her usual outing
    var suggested: Int?          // minute of day; nil = no safe slot that day
    var direction: ShiftDirection?
    var id: String { outing.id }
}

struct HerDayResult: Equatable {
    var day: Int                 // 0 today, 1 tomorrow
    var date: String             // the plan's date
    var hot: [HotWindow]
    var outings: [Outing]
    var collisions: [Collision]
    var airOpen: Int?            // minute of day
    var heatwaveDay: Int?
    var items: [DayPlanItem]
}

enum HerDay {
    static let hotC = 30.0
    static let warmIndoorC = 28.0
    static let earliest = 7 * 60
    static let gapAfter = 30
    static let step = 15
    static let airFromHour = 18
    /// Tomorrow's DAY_PLAN goes to the band from this minute of the day on ("every evening").
    static let eveningSendMinute = 18 * 60

    /// Per hour: hot (outdoor >= 30 °C or AVOID).
    static func hotHours(_ p: Plan) -> [Bool] {
        p.hours.map { h in (h.tOut.map { $0 >= hotC } ?? false) || h.advice == "AVOID" }
    }

    static func hotWindows(_ hot: [Bool]) -> [HotWindow] {
        var out: [HotWindow] = []
        var s: Int? = nil
        for i in 0...hot.count {
            let on = i < hot.count && hot[i]
            if on && s == nil { s = i }
            if !on, let st = s { out.append(HotWindow(from: st, to: i)); s = nil }
        }
        return out
    }

    /// True when no minute of [start, start + dur) falls in a hot hour (or past midnight).
    static func slotIsCool(_ start: Int, _ dur: Int, _ hot: [Bool]) -> Bool {
        guard start >= 0, start + dur <= 24 * 60 else { return false }
        let last = (start + max(1, dur) - 1) / 60
        for h in (start / 60)...last where h < hot.count && hot[h] { return false }
        return true
    }

    static func floorStep(_ m: Int) -> Int { m >= 0 ? (m / step) * step : -(((-m) + step - 1) / step) * step }
    static func ceilStep(_ m: Int) -> Int { ((m + step - 1) / step) * step }

    /// Her bedtime as a minute on the same day's axis (a bedtime after midnight counts as the next day).
    static func bedOnAxis(_ bed: Int) -> Int { bed < 12 * 60 ? bed + 24 * 60 : bed }

    /// The suggestion for an outing that starts inside `w` (nil = no safe slot).
    static func suggest(_ o: Outing, _ w: HotWindow, _ hot: [Bool], bed: Int) -> (Int, ShiftDirection)? {
        let dur = max(1, o.duration)
        var t = floorStep(w.from * 60 - dur)
        while t >= earliest {
            if slotIsCool(t, dur, hot) { return (t, .before) }
            t -= step
        }
        let limit = min(bedOnAxis(bed) - 60, 24 * 60)
        t = ceilStep(w.to * 60 + gapAfter)
        while t + dur <= limit {
            if slotIsCool(t, dur, hot) { return (t, .after) }
            t += step
        }
        return nil
    }

    /// Half-up rounding for a positive temperature (the Python mirror uses floor(x + 0.5)).
    static func roundC(_ x: Double) -> Int { Int((x + 0.5).rounded(.down)) }

    /// Peak outdoor °C over [start, start + dur).
    static func peak(_ p: Plan, _ start: Int, _ dur: Int) -> Int? {
        let a = start / 60, b = min(23, (start + max(1, dur) - 1) / 60)
        guard a <= b, a < p.hours.count else { return nil }
        let ts = (a...b).compactMap { $0 < p.hours.count ? p.hours[$0].tOut : nil }
        return ts.max().map(roundC)
    }

    /// AIR_OPEN: the first hour >= 18:00 where outdoor < indoor - 1 °C, on a day where heat at home matters.
    static func airOpen(_ p: Plan) -> Int? {
        let matters = p.heatDay || p.nightHeat || (p.hours.map { $0.tIn }.max() ?? 0) >= warmIndoorC
        guard matters, p.hours.count == 24 else { return nil }
        for h in airFromHour..<24 {
            if let o = p.hours[h].tOut, o < p.hours[h].tIn - 1.0 { return h * 60 }
        }
        return nil
    }

    static func compute(plan p: Plan, outings: [Outing], bed: Int, day: Int) -> HerDayResult {
        let hot = hotHours(p)
        let wins = hotWindows(hot)
        let outs = outings.filter { $0.place != .home }.sorted { ($0.start, $0.place.rawValue) < ($1.start, $1.place.rawValue) }
        var cols: [Collision] = []
        for o in outs {
            guard let w = wins.first(where: { $0.overlaps(start: o.start, duration: o.duration) }) else { continue }
            let s = suggest(o, w, hot, bed: bed)
            cols.append(Collision(outing: o, window: w, peakC: peak(p, o.start, o.duration), suggested: s?.0, direction: s?.1))
        }
        let air = airOpen(p)
        let wave: Int? = p.heatDay ? min(31, max(1, p.waveDay ?? 1)) : nil

        var tail: [DayPlanItem] = []
        if let a = air { tail.append(DayPlanItem(day: day, kind: .airOpen, suggested: a)) }
        if let n = wave { tail.append(DayPlanItem(day: day, kind: .heatwaveDay, heatwaveDay: n)) }
        let shifts = cols.compactMap { c -> DayPlanItem? in
            guard let s = c.suggested, let d = c.direction else { return nil }
            return DayPlanItem(day: day, kind: .outingShift, place: c.outing.place, usual: c.outing.start, suggested: s,
                               direction: d, hotFrom: c.window.from, hotTo: c.window.to, peakC: c.peakC)
        }
        let items = Array(shifts.prefix(HG.dayPlanMaxItems - tail.count)) + tail
        return HerDayResult(day: day, date: p.date, hot: wins, outings: outs, collisions: cols, airOpen: air,
                            heatwaveDay: wave, items: items)
    }

    /// The band's evening / morning sentence for a plan (spec §5): first OUTING_SHIFT by usual time, else heat-wave.
    /// tomorrow = «Αύριο: …», today = «Σήμερα: …». nil = the band would not brief.
    static func briefSentence(_ items: [DayPlanItem], tomorrow: Bool) -> String? {
        let head = tomorrow ? "Αύριο: " : "Σήμερα: "
        if let k = items.filter({ $0.kind == .outingShift }).min(by: { ($0.usual ?? 9999) < ($1.usual ?? 9999) }),
           let s = k.suggested, let d = k.direction {
            return head + k.place.bandWord + (d == .before ? " πριν τις " : " μετά τις ") + Routine.hhmm(s)
        }
        if tomorrow, let w = items.first(where: { $0.kind == .heatwaveDay }) {
            return "Αύριο: καύσωνας, μέρα \(w.heatwaveDay)"
        }
        return nil
    }
}
