// Her Day demo (HERDAY_SPEC.md §6, labelled SIMULATION / ΠΡΟΣΟΜΟΙΩΣΗ): a scripted two weeks of her visits and
// two constructed Athens heat-wave days — today = heat-wave day 1, tomorrow = heat-wave day 2 — so the timeline shows
// collisions with no Bluetooth and no location (iOS Simulator). Pure Swift; HerDayTests checks what it produces.
//
// Her scripted routine: market most mornings ~10:20 (30 min), the café ~18:00 (1 h) four days a week, an evening
// walk ~21:15 (40 min) every day, church once a week ~08:30 (75 min) — on tomorrow's weekday, so it is in tomorrow's
// routine whatever day the demo runs. Tomorrow (day 2: hot 10:00-21:00) the market and the café collide ("go before");
// church 08:30 and the 21:15 walk do not.
// «Hotter tomorrow» (Demo controls, Foivos Nov 18: show "go after" too) swaps tomorrow for heat-wave day 3 after a hot
// night (hot 08:00-19:00): church 08:30-09:45 cannot end before 08:00 when it starts >= 07:00, so it moves AFTER (19:30);
// the market (07:30) and the café (07:00) still go before — both directions on one screen. Today (day 1: hot 11:00-20:00) only the café collides — and in the script she
// follows the suggestion: café 09:35, market 10:40, home from 11:25, walk at 21:15.

import Foundation

enum HerDayDemo {
    /// (days before today, minute of day, place, duration) — the scripted past; today's visits are separate.
    static func pastVisits(today: Date, calendar cal: Calendar = .current) -> [VisitSample] {
        let d0 = cal.startOfDay(for: today)
        let churchDay = cal.date(byAdding: .day, value: 1, to: d0).map { cal.component(.weekday, from: $0) } ?? 1
        var out: [VisitSample] = []
        func add(_ back: Int, _ m: Int, _ p: PlaceType, _ dur: Int) {
            guard let d = cal.date(byAdding: .day, value: -back, to: d0) else { return }
            let a = d.addingTimeInterval(Double(m * 60))
            out.append(VisitSample(place: p, arrive: a, leave: a.addingTimeInterval(Double(dur * 60))))
        }
        let jitter = [0, 7, -5, 12, -8, 4, -3, 9, -6, 2, 10, -4, 5, -9]
        for back in 1...14 {
            guard let d = cal.date(byAdding: .day, value: -back, to: d0) else { continue }
            let wd = cal.component(.weekday, from: d)       // 1 Sunday
            let j = jitter[(back - 1) % jitter.count]
            if wd == churchDay {
                add(back, 8 * 60 + 30 + j / 2, .church, 75)
            } else {
                add(back, 10 * 60 + 20 + j, .market, 30)
            }
            if [3, 5, 6, 7].contains(wd) { add(back, 18 * 60 + j, .cafe, 60) }
            add(back, 21 * 60 + 15 + j, .walk, 40)
            // home: the nights in between (so the home rule has overnight dwell)
            add(back, 0, .home, 8 * 60)
        }
        return out.sorted { $0.arrive < $1.arrive }
    }

    /// Today's scripted visits (minute of arrival, place, minutes there) — emitted as the demo clock passes them.
    static let todayScript: [(Int, PlaceType, Int)] = [
        (9 * 60 + 35, .cafe, 45), (10 * 60 + 40, .market, 40), (21 * 60 + 15, .walk, 40),
    ]

    /// Outdoor °C by hour for heat-wave day 1 / day 2 (constructed, Athens-like; not a measured record).
    static let tOutDay1: [Double] = [27.5, 27.0, 26.6, 26.2, 26.0, 26.0, 26.5, 27.4, 28.3, 29.0, 29.6, 30.4,
                                     31.6, 32.8, 33.6, 34.0, 33.6, 32.6, 31.4, 30.2, 29.1, 28.4, 28.0, 27.7]
    static let tOutDay2: [Double] = [28.6, 28.2, 27.9, 27.6, 27.4, 27.5, 27.9, 28.4, 28.9, 29.5, 30.6, 32.0,
                                     33.4, 34.8, 35.9, 36.4, 36.0, 35.0, 33.6, 32.1, 30.7, 29.4, 28.9, 28.6]

    /// Heat-wave day 3 after a hot night (the «hotter tomorrow» demo switch): hot 08:00-19:00.
    static let tOutDay3: [Double] = [29.8, 29.4, 29.0, 28.7, 28.5, 28.6, 29.1, 29.7, 30.5, 31.6, 32.9, 34.1,
                                     35.3, 36.4, 37.1, 37.3, 36.4, 34.2, 31.3, 29.8, 29.0, 28.6, 28.3, 28.0]

    /// A constructed plan (format of Plan) for `date`: indoor from Indoor.simulate (class B, old middle floor).
    static func plan(date: Date, waveDay: Int, calendar cal: Calendar = .current) -> Plan {
        let outs = waveDay >= 3 ? tOutDay3 : (waveDay == 2 ? tOutDay2 : tOutDay1)
        // two days of the same weather so the slow node settles, keep the second day
        let ins = Array(Indoor.simulate(outs + outs, cls: "B").suffix(24))
        var hours: [Plan.Hour] = []
        for h in 0..<24 {
            let o = outs[h], i = (ins[h] * 10).rounded() / 10
            let advice = o >= 32 ? "AVOID" : (o >= 30 ? "SHORT" : "OK")
            hours.append(Plan.Hour(h: h, tOut: o, rhOut: 35, tIn: i, rhIn: 40, advice: advice,
                                   safe: advice == "OK" && h >= 7 && h < 21))
        }
        let c = cal.dateComponents([.year, .month, .day], from: date)
        let ds = String(format: "%04d-%02d-%02d", c.year ?? 0, c.month ?? 0, c.day ?? 0)
        return Plan(date: ds, heatDay: true, nightHeat: (ins.max() ?? 0) >= 28, waveDay: waveDay, hours: hours,
                    adviceGr: nil, labels: ["SIMULATION", "CONSTRUCTED DEMO DAY (not a measured record)"],
                    source: "CONSTRUCTED DEMO DAY", attribution: nil, homeClass: "B", staleForecast: false, ble: nil)
    }

    /// Her routine in the demo: wake 07:00, bed 23:30.
    static let bed = 23 * 60 + 30
}
