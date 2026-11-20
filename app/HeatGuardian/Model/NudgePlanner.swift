// App-side PREDICTION of the band's prevention nudges (ECOSYSTEM_SPEC §2 + §5b) for one plan day and her routine.
// The band decides for real (it also sees the room and its own warnings); this list is what the app shows as
// "planned" on Tomorrow and as "upcoming" on Today until the band's EVENTS say shown / done / missed.

import Foundation

enum NudgeID: Int, Codable, CaseIterable {
    case brief = 1, lastCool = 2, shutters = 3, water = 4, air = 5, ac = 6
    case eveningBrief = 7, leaveHot = 8          // Her Day (HERDAY_SPEC §4, band 0.9.8)
}

struct PlannedNudge: Identifiable, Equatable {
    var id: String { "\(nudge.rawValue)@\(minute)" }
    var nudge: NudgeID
    var minute: Int          // minute of day
    var hour: Int { minute / 60 }
}

enum NudgePlanner {
    static let maxPerDay = 6
    static let minGap = 60
    static let waterEvery = 90
    static let waterMax = 4
    static let warm = 28.0, hot = 30.0

    static func plan(_ p: Plan, routine r: Routine) -> [PlannedNudge] {
        guard p.hours.count == 24 else { return [] }
        let tIn = p.hours.map { $0.tIn }
        var c: [PlannedNudge] = []
        let wake = r.wakeOrDefault

        if p.heatDay {
            // N1 BRIEF: at her wake press after 07:00, at the latest 08:30.
            c.append(PlannedNudge(nudge: .brief, minute: min(max(wake, 7 * 60), 8 * 60 + 30)))
            // N2 LAST_COOL: 30 min before the morning safe window ends.
            if let end = morningSafeEnd(p) { c.append(PlannedNudge(nudge: .lastCool, minute: max(0, end * 60 - 30))) }
        }
        // N3 SHUTTERS: 09:00–13:00, first hour whose next 2 h reach >= 28 °C indoors.
        if let h = (9...12).first(where: { h in (h...min(23, h + 2)).contains { tIn[$0] >= warm } }) {
            c.append(PlannedNudge(nudge: .shutters, minute: h * 60))
        }
        // N6 A/C (§5b, ac = yes): the first hot hour (>= 28 °C indoors) after waking (fw 0.9.7 planner).
        if r.ac == true, let h = (0..<24).first(where: { tIn[$0] >= warm && $0 * 60 >= wake }) {
            c.append(PlannedNudge(nudge: .ac, minute: h * 60))
        }
        // N4 WATER: warm hours, every 90 min awake, max 4.
        var w = 0
        var m = wake
        while m < 24 * 60 && w < waterMax {
            if tIn[m / 60] >= warm && !r.asleep(m) {
                c.append(PlannedNudge(nudge: .water, minute: m))
                w += 1
                m += waterEvery
            } else {
                m += 30
            }
        }
        // N5 AIR: 21:30 on a night-heat day.
        if p.nightHeat { c.append(PlannedNudge(nudge: .air, minute: 21 * 60 + 30)) }

        // Caps: none in sleep / nap, >= 60 min apart (a later one waits), max 6. Fixed-time nudges first.
        let prio: [NudgeID: Int] = [.brief: 0, .lastCool: 1, .shutters: 2, .ac: 3, .air: 4, .water: 5]   // fw 0.9.7 order
        var out: [PlannedNudge] = []
        for n in c.sorted(by: { ($0.minute, prio[$0.nudge] ?? 9) < ($1.minute, prio[$1.nudge] ?? 9) }) {
            var t = n.minute
            if let last = out.last, t - last.minute < minGap {
                if n.nudge != .water { t = last.minute + minGap } else { continue }
            }
            guard t < 24 * 60, !r.asleep(t), out.count < maxPerDay else { continue }
            out.append(PlannedNudge(nudge: n.nudge, minute: t))
        }
        return out
    }

    /// End hour of the first safe window that starts before noon.
    static func morningSafeEnd(_ p: Plan) -> Int? {
        guard let s = (0..<12).first(where: { p.hours[$0].safe }) else { return nil }
        var e = s
        while e < 24 && p.hours[e].safe { e += 1 }
        return e
    }

    /// The first safe window's end as "HH:00" for the brief text, nil = no safe hours.
    static func briefHour(_ p: Plan) -> Int? {
        guard p.hours.count == 24, let s = (0..<24).first(where: { p.hours[$0].safe }) else { return nil }
        var e = s
        while e < 24 && p.hours[e].safe { e += 1 }
        return e
    }
}
