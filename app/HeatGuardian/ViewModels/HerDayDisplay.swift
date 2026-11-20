// What the family's "Her Day" timeline shows (HERDAY_SPEC.md §6) for today (0) or tomorrow (1):
//  - the heat strip: outside / house by hour (from the forecast plan this phone has),
//  - her usual day: outings learned from the band's VISIT events (place type + time only),
//  - collisions with the hot window, and the band's suggestions as the band holds them (PLAN_ITEM events),
//  - today: whether she followed each suggestion (VISIT events vs the suggestion) and the status line.

import Foundation

struct HeatCell: Equatable, Identifiable {
    var hour: Int
    var outLevel: Int            // 0 fine, 1 warm (28-30 °C), 2 hot (>= 30 °C or AVOID)
    var inLevel: Int
    var id: Int { hour }
}

struct HerDayRow: Equatable, Identifiable {
    enum Kind: Equatable { case outing, collision, air }
    var id: String
    var minute: Int
    var time: String
    var symbol: String
    var title: String
    var detail: String?
    var suggestion: String?
    var outcome: String?
    var outcomeTone: Tone
    var kind: Kind
}

struct HerDayDisplay: Equatable {
    var status: String?
    var statusSymbol: String?
    var cells: [HeatCell]
    var hot: [HotWindow]
    var hotText: String
    var stripA11y: String
    var rows: [HerDayRow]
    var bandLine: String
    var onBand: Bool
    var hasRoutine: Bool
    var simulated: Bool

    static let firstHour = 6

    static func level(_ c: Double?, advice: String? = nil) -> Int {
        if let c = c { return c >= HerDay.hotC ? 2 : (c >= HerDay.warmIndoorC ? 1 : 0) }
        return advice == "AVOID" ? 2 : (advice == "SHORT" ? 1 : 0)
    }

    /// Pure: everything comes in as values (AppModel.herDayDisplay(_:) gathers them), so it runs in the Linux XCTest.
    static func make(L: Strings, offset: Int, now: Date, plan: Plan?, local: HerDayResult?, entries: [LogEntry],
                     simulated: Bool) -> HerDayDisplay? {
        let cal = Calendar.current
        guard let date = cal.date(byAdding: .day, value: offset, to: now) else { return nil }
        let d0 = cal.startOfDay(for: date)
        let band = BandHerDay.planItems(entries, for: date)
        let todays = offset == 0 ? BandHerDay.visits(entries, on: date) : []
        let hhmm: (Date) -> String = { Routine.hhmm($0.minuteOfDay) }

        // status line (today)
        var status: String?
        var statusSymbol: String?
        if offset == 0, let (v, t) = BandHerDay.latest(entries, on: date, before: now) {
            status = v.edge == .arrive ? L.hdAtSince(v.place, hhmm(t)) : L.hdLeftSince(v.place, hhmm(t))
            statusSymbol = v.edge == .arrive ? v.place.symbol : "figure.walk.departure"
        }

        // heat strip
        var cells: [HeatCell] = []
        if let p = plan {
            for h in firstHour..<24 where h < p.hours.count {
                cells.append(HeatCell(hour: h, outLevel: level(p.hours[h].tOut, advice: p.hours[h].advice), inLevel: level(p.hours[h].tIn)))
            }
        }
        let hot = local?.hot ?? []
        let hotText = hot.isEmpty ? L.hdNoHot : hot.map { L.hdHotWindow($0.from, $0.to) }.joined(separator: " · ")
        let peakOut = plan?.hours.compactMap { $0.tOut }.max().map(HerDay.roundC)
        let peakIn = plan?.hours.map { $0.tIn }.max().map(HerDay.roundC)

        // rows: her usual outings (+ collisions), then band items with no learned outing, then airing
        var rows: [HerDayRow] = []
        var usedBand = Set<Int>()
        let bandShifts = band.items.enumerated().filter { $0.element.kind == .outingShift }
        for o in local?.outings ?? [] {
            let col = local?.collisions.first { $0.outing == o }
            let bi = bandShifts.first { b in
                !usedBand.contains(b.offset) && b.element.place == o.place && abs((b.element.usual ?? -999) - o.start) <= 60
            }
            if let b = bi { usedBand.insert(b.offset) }
            var row = HerDayRow(id: "o\(o.id)", minute: o.start, time: Routine.hhmm(o.start), symbol: o.place.symbol,
                                title: L.placeName(o.place), detail: L.hdUsual(o.duration), suggestion: nil, outcome: nil,
                                outcomeTone: .neutral, kind: .outing)
            if col != nil || bi != nil {
                row.kind = .collision
                row.detail = L.hdHotThen(col?.peakC)
                if let b = bi?.element, let s = b.suggested, let d = b.direction {
                    row.suggestion = L.hdBandSuggests(d, Routine.hhmm(s))
                } else if let c = col, let s = c.suggested, let d = c.direction {
                    row.suggestion = L.hdWillSuggest(d, Routine.hhmm(s))
                } else {
                    row.suggestion = L.hdNoSlot
                }
                if offset == 0 {
                    let it = bi?.element ?? col.flatMap { c in
                        c.suggested.map { DayPlanItem(day: 0, kind: .outingShift, place: o.place, usual: o.start, suggested: $0,
                                                      direction: c.direction, hotFrom: c.window.from, hotTo: c.window.to) }
                    }
                    if let it = it { (row.outcome, row.outcomeTone) = outcomeText(L, BandHerDay.outcome(it, visits: todays, day: d0, now: now), hhmm) }
                }
            }
            rows.append(row)
        }
        for b in bandShifts where !usedBand.contains(b.offset) {
            let it = b.element
            guard let u = it.usual ?? it.suggested else { continue }
            var row = HerDayRow(id: "b\(b.offset)", minute: u, time: Routine.hhmm(u), symbol: it.place.symbol,
                                title: L.placeName(it.place), detail: L.hdHotThen(nil),
                                suggestion: it.suggested.flatMap { s in it.direction.map { L.hdBandSuggests($0, Routine.hhmm(s)) } },
                                outcome: nil, outcomeTone: .neutral, kind: .collision)
            if offset == 0 { (row.outcome, row.outcomeTone) = outcomeText(L, BandHerDay.outcome(it, visits: todays, day: d0, now: now), hhmm) }
            rows.append(row)
        }
        if let a = band.items.first(where: { $0.kind == .airOpen })?.suggested ?? local?.airOpen {
            rows.append(HerDayRow(id: "air", minute: a, time: Routine.hhmm(a), symbol: "wind", title: L.hdAir(Routine.hhmm(a)),
                                  detail: L.hdAirWhy, suggestion: nil, outcome: nil, outcomeTone: .neutral, kind: .air))
        }
        rows.sort { ($0.minute, $0.id) < ($1.minute, $1.id) }

        let onBand = !band.items.isEmpty
        let bandLine: String
        if let at = band.at, onBand { bandLine = L.hdOnBand(hhmm(at)) }
        else if offset == 1 && now.minuteOfDay < HerDay.eveningSendMinute { bandLine = L.hdGoesEvening }
        else { bandLine = L.hdNotOnBand }

        let hasRoutine = !(local?.outings.isEmpty ?? true)
        guard plan != nil || !rows.isEmpty || status != nil else { return nil }
        return HerDayDisplay(status: status, statusSymbol: statusSymbol, cells: cells, hot: hot, hotText: hotText,
                             stripA11y: L.hdStripValue(hotText, peakOut, peakIn), rows: rows, bandLine: bandLine,
                             onBand: onBand, hasRoutine: hasRoutine, simulated: simulated || (plan?.isSimulation ?? false))
    }

    static func outcomeText(_ L: Strings, _ o: BandHerDay.Outcome, _ f: (Date) -> String) -> (String?, Tone) {
        switch o {
        case .pending: return (nil, .neutral)
        case .followed(let t): return (L.hdFollowed(f(t)), .ok)
        case .inHeat(let t): return (L.hdInHeat(f(t)), .heat)
        case .went(let t): return (L.hdWent(f(t)), .neutral)
        case .notGone: return (L.hdNotGone, .neutral)
        }
    }
}
