// What the BAND holds of Her Day, rebuilt from its EVENTS (HERDAY_SPEC.md §4): PLAN_ITEM (type 10) echoes and
// VISIT (type 9) events. The family phone builds its timeline only from these, so it shows exactly what the band
// has — never her coordinates (the events carry a place type and a time). Pure Swift.

import Foundation

enum BandHerDay {
    /// A new item set for a day arrives as a burst of PLAN_ITEM events: items within 120 s of the newest one for
    /// that date are the band's current set (the band replaces a day's plan atomically).
    static let batchWindow: TimeInterval = 120

    /// The plan items the band holds for `date`. Each PLAN_ITEM targets (day of the event) + item.day, so
    /// yesterday's "tomorrow" echo and today's "today" echo both land on today. Returns the items (in band order)
    /// and when that set arrived.
    static func planItems(_ entries: [LogEntry], for date: Date, calendar cal: Calendar = .current) -> (items: [DayPlanItem], at: Date?) {
        let target = cal.startOfDay(for: date)
        var hits: [(LogEntry, DayPlanItem)] = []
        for e in entries where e.kind == .planItem && e.clockKnown {
            guard let it = e.planItem, let d = cal.date(byAdding: .day, value: it.day, to: cal.startOfDay(for: e.at)),
                  cal.isDate(d, inSameDayAs: target) else { continue }
            hits.append((e, it))
        }
        guard let newest = hits.map({ $0.0.at }).max() else { return ([], nil) }
        let batch = hits.filter { newest.timeIntervalSince($0.0.at) <= batchWindow }.sorted { $0.0.at < $1.0.at }
        // the same item echoed twice inside one burst (a re-notify) counts once
        var out: [DayPlanItem] = []
        for (_, it) in batch {
            var x = it
            x.day = 0
            if !out.contains(where: { var y = $0; y.day = 0; return y == x }) { out.append(it) }
        }
        return (out, newest)
    }

    /// VISIT events (with the visit's own time) on `date`, oldest first.
    static func visits(_ entries: [LogEntry], on date: Date, calendar cal: Calendar = .current) -> [(VisitEvent, Date)] {
        allVisits(entries).filter { cal.isDate($0.1, inSameDayAs: date) }
    }

    static func allVisits(_ entries: [LogEntry]) -> [(VisitEvent, Date)] {
        var seen = Set<String>()
        var out: [(VisitEvent, Date)] = []
        for e in entries where e.kind == .visit {
            guard let v = e.visit else { continue }
            let t = v.unix != 0 ? Date(timeIntervalSince1970: TimeInterval(v.unix)) : e.at
            let key = "\(v.edge.rawValue)-\(v.place.rawValue)-\(Int(t.timeIntervalSince1970))"
            if seen.insert(key).inserted { out.append((v, t)) }
        }
        return out.sorted { $0.1 < $1.1 }
    }

    /// VISIT events -> visits for the routine model: an ARRIVE paired with the next LEAVE of the same place type
    /// within 12 h (no LEAVE = unknown length). A LEAVE without its ARRIVE is skipped.
    static func samples(_ entries: [LogEntry]) -> [VisitSample] {
        let vs = allVisits(entries)
        var out: [VisitSample] = []
        for (i, (v, t)) in vs.enumerated() where v.edge == .arrive {
            let leave = vs[(i + 1)...].first { $0.0.edge == .leave && $0.0.place == v.place && $0.1 >= t && $0.1.timeIntervalSince(t) < 12 * 3600 }?.1
            out.append(VisitSample(place: v.place, arrive: t, leave: leave))
        }
        return out
    }

    /// Where she is now from today's VISIT events: (place, edge, time) of the latest one. nil = none today.
    static func latest(_ entries: [LogEntry], on date: Date, before now: Date, calendar cal: Calendar = .current) -> (VisitEvent, Date)? {
        visits(entries, on: date, calendar: cal).last { $0.1 <= now }
    }

    enum Outcome: Equatable { case pending, followed(Date), inHeat(Date), went(Date), notGone }

    /// Did she follow a suggestion? The first ARRIVE of that place type on that day (within 4 h of her usual time
    /// or the suggestion): direction 1 followed when she arrived by the suggested time (+10 min grace), direction 2
    /// when she arrived after it (-10 min); arriving inside the hot window = in the heat.
    static func outcome(_ it: DayPlanItem, visits: [(VisitEvent, Date)], day: Date, now: Date, calendar cal: Calendar = .current) -> Outcome {
        guard it.kind == .outingShift, let s = it.suggested, let d = it.direction else { return .pending }
        let d0 = cal.startOfDay(for: day)
        let anchors = [s, it.usual ?? s]
        let arrive = visits.first { v in
            guard v.0.edge == .arrive, v.0.place == it.place else { return false }
            let m = Int(v.1.timeIntervalSince(d0) / 60)
            return anchors.contains { abs(m - $0) <= 240 }
        }?.1
        if let a = arrive {
            let m = Int(a.timeIntervalSince(d0) / 60)
            if m >= it.hotFrom * 60 && m < max(it.hotTo, it.hotFrom + 1) * 60 { return .inHeat(a) }
            switch d {
            case .before: return m <= s + 10 ? .followed(a) : .went(a)
            case .after: return m >= s - 10 ? .followed(a) : .went(a)
            }
        }
        let endOfChance = d == .before ? max(s, it.hotTo * 60) : s + 4 * 60
        return Int(now.timeIntervalSince(d0) / 60) > endOfChance ? .notGone : .pending
    }
}
