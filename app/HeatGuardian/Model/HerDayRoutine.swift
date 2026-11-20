// Her routine learned from visits (HERDAY_SPEC.md §3, §6), the home rule and the POI -> place-type mapping.
// Pure Swift: the same code runs on her phone (visits from iOS Core Location) and on the family phone (the band's
// VISIT events: place type + time only, never coordinates). Mirrored in tools/mirror_frames.py (routine core).

import Foundation

/// One visit as the routine model sees it: a place type and times, nothing else.
struct VisitSample: Equatable, Codable {
    var place: PlaceType
    var arrive: Date
    var leave: Date?
}

/// The routine model's input after the calendar step (so the core is calendar-free and mirrorable).
struct RoutineSample: Equatable {
    var place: PlaceType
    var weekday: Int             // 1 = Sunday ... 7 = Saturday (Calendar)
    var start: Int               // minute of day
    var duration: Int?           // minutes, nil = leave unknown
}

enum RoutineModel {
    static let lookbackDays = 28
    static let minOccurrences = 2
    static let dailyWeekdays = 4
    static let clusterGap = 180          // starts more than 3 h apart are different outings of the same type
    static let defaultDuration = 60
    static let minDuration = 15, maxDuration = 240

    /// Median of ints; even count = mean of the two middle values, rounded down.
    static func median(_ xs: [Int]) -> Int {
        let s = xs.sorted()
        guard !s.isEmpty else { return 0 }
        let n = s.count
        if n % 2 == 1 { return s[n / 2] }
        let a = s[n / 2 - 1] + s[n / 2]
        return a >= 0 ? a / 2 : -((-a + 1) / 2)
    }

    /// Calendar step: visits of the last 4 weeks (before `now`), not home, as samples.
    static func samples(_ visits: [VisitSample], now: Date, calendar cal: Calendar = .current) -> [RoutineSample] {
        let from = now.addingTimeInterval(-Double(lookbackDays) * 86400)
        return visits.compactMap { v in
            guard v.place != .home, v.arrive >= from, v.arrive < now else { return nil }
            let wd = cal.component(.weekday, from: v.arrive)
            let c = cal.dateComponents([.hour, .minute], from: v.arrive)
            let start = (c.hour ?? 0) * 60 + (c.minute ?? 0)
            let dur = v.leave.map { Int($0.timeIntervalSince(v.arrive) / 60) }
            return RoutineSample(place: v.place, weekday: wd, start: start, duration: dur.flatMap { $0 > 0 ? $0 : nil })
        }
    }

    /// The expected outings on `weekday` (sorted by start). Per place type, starts are grouped into clusters
    /// (gap > 3 h = a different outing). A cluster seen on >= 4 different weekdays is a daily habit and applies to
    /// every day (median start / duration of the whole cluster); otherwise it applies on `weekday` only when that
    /// weekday has >= 2 of its visits (median of those).
    static func outings(_ ss: [RoutineSample], weekday: Int) -> [Outing] {
        var out: [Outing] = []
        for place in PlaceType.allCases where place != .home {
            let xs = ss.filter { $0.place == place }.sorted { ($0.start, $0.weekday) < ($1.start, $1.weekday) }
            guard !xs.isEmpty else { continue }
            var clusters: [[RoutineSample]] = [[xs[0]]]
            for s in xs.dropFirst() {
                if s.start - clusters[clusters.count - 1].last!.start > clusterGap { clusters.append([s]) }
                else { clusters[clusters.count - 1].append(s) }
            }
            for c in clusters {
                let daily = Set(c.map { $0.weekday }).count >= dailyWeekdays
                let use = daily ? c : c.filter { $0.weekday == weekday }
                guard use.count >= minOccurrences else { continue }
                let durs = use.compactMap { $0.duration }
                let dur = durs.isEmpty ? defaultDuration : max(minDuration, min(maxDuration, median(durs)))
                out.append(Outing(place: place, start: median(use.map { $0.start }), duration: dur, daily: daily, count: use.count))
            }
        }
        return out.sorted { ($0.start, $0.place.rawValue) < ($1.start, $1.place.rawValue) }
    }

    /// Convenience: the expected outings on the day of `date`, learned from visits before `now`.
    static func outings(_ visits: [VisitSample], on date: Date, now: Date, calendar cal: Calendar = .current) -> [Outing] {
        outings(samples(visits, now: now, calendar: cal), weekday: cal.component(.weekday, from: date))
    }
}

/// Home = the place with the most overnight dwell (00:00-06:00) over the last 14 days (spec §3).
enum HomeRule {
    static let days = 14
    static let nightFrom = 0, nightTo = 6 * 60

    struct Stay: Equatable {
        var placeID: String
        var arrive: Date
        var leave: Date?             // nil = still there (counts until `now`)
    }

    /// Minutes of [a, b) that fall in 00:00-06:00 of any night.
    static func overnightMinutes(_ a: Date, _ b: Date, calendar cal: Calendar = .current) -> Int {
        guard b > a else { return 0 }
        var total = 0.0
        var day = cal.startOfDay(for: a)
        while day < b {
            let n0 = day.addingTimeInterval(Double(nightFrom * 60)), n1 = day.addingTimeInterval(Double(nightTo * 60))
            let s = max(a, n0), e = min(b, n1)
            if e > s { total += e.timeIntervalSince(s) }
            guard let next = cal.date(byAdding: .day, value: 1, to: day) else { break }
            day = next
        }
        return Int(total / 60)
    }

    /// The place id with the most overnight minutes in the last 14 days; nil when no stay covers a night.
    static func detect(_ stays: [Stay], now: Date, calendar cal: Calendar = .current) -> String? {
        let from = now.addingTimeInterval(-Double(days) * 86400)
        var mins: [String: Int] = [:]
        for s in stays {
            let a = max(s.arrive, from), b = min(s.leave ?? now, now)
            let m = overnightMinutes(a, b, calendar: cal)
            if m > 0 { mins[s.placeID, default: 0] += m }
        }
        return mins.max { ($0.value, $1.key) < ($1.value, $0.key) }?.key
    }
}

/// MapKit point-of-interest category -> place type (spec §3). The location code turns MKPointOfInterestCategory
/// into the keys below; the name is a fallback (there is no "church" category in MapKit).
enum PlaceMapping {
    static func type(category key: String?, name: String?) -> PlaceType {
        switch key {
        case "foodMarket", "store", "bakery": return .market
        case "park", "beach", "nationalPark": return .walk
        case "pharmacy": return .pharmacy
        case "cafe", "restaurant": return .cafe
        case "hospital": return .doctor
        default: break
        }
        return fromName(name) ?? .other
    }

    /// Accent- and case-free keyword match on the POI name (Greek + English).
    static func fromName(_ name: String?) -> PlaceType? {
        guard let n = name?.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: Locale(identifier: "el_GR")),
              !n.isEmpty else { return nil }
        let rules: [(PlaceType, [String])] = [
            (.church, ["εκκλησια", "ιερος ναος", "ι.ν.", "ναος", "παναγια", "αγιος ", "αγια ", "αγιου ", "αγιας ", "μοναστηρι", "church", "chapel", "cathedral"]),
            (.pharmacy, ["φαρμακει", "pharmacy"]),
            (.market, ["λαικη", "αγορα", "σουπερ μαρκετ", "super market", "supermarket", "μαναβ", "φουρνος", "αρτοποιει", "market", "bakery"]),
            (.cafe, ["καφενει", "καφε", "cafe", "coffee"]),
            (.doctor, ["ιατρει", "κλινικη", "νοσοκομει", "γιατρ", "κεντρο υγειας", "clinic", "hospital", "doctor"]),
            (.walk, ["παρκο", "πλατεια", "αλσος", "park", "square"]),
        ]
        for (t, keys) in rules where keys.contains(where: { n.contains($0) }) { return t }
        return nil
    }
}
