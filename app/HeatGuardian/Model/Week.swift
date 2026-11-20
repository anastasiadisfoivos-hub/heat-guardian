// "Her week": per-day trends computed from the STATUS frames the phone received (no extra data from the band).
//  - routine regularity = mean of STATUS byte 15 (routine score, guardian/c/hg_routine.c: 255 - min(255, 64·max z) per hour)
//    shown as 0–100 %; 255 is skipped because the band also sends 255 while the routine is not learnt (ambiguous)
//  - rest = minutes with wrist movement byte 16 (accel std, mg) <= 3 while worn (a simple heuristic of this app)
//  - heart rate = mean of the valid pulse readings (byte 5 > 0)
//  - minutes on alert = minutes in DRINK / COOL / DANGER; alerts = family-alert rising edges
// It is a trend view for a conversation, not a diagnosis.

import Foundation

/// One minute of history (live: persisted on this iPhone for 8 days; demo: in memory, cleared on exit).
struct HistPoint: Codable, Identifiable {
    var t: Date
    var vs: String
    var core: Double?
    var half: Double
    var fam: Bool
    var hr: Int?
    var activity: Int?
    var routine: Int?
    var id: Date { t }
}

struct DayStats: Identifiable {
    var day: Date
    var minutes: Int
    var routine: Double?
    var restMin: Int
    var hrMean: Double?
    var tierMin: Int
    var alerts: Int
    var id: Date { day }
}

enum Week {
    static let restActivityMax = 3

    /// The last 7 calendar days ending today (days with no data have minutes == 0).
    static func days(_ hist: [HistPoint], today: Date = Date()) -> [DayStats] {
        let cal = Calendar.current
        let start = cal.startOfDay(for: today)
        var out: [DayStats] = []
        for k in stride(from: 6, through: 0, by: -1) {
            guard let d0 = cal.date(byAdding: .day, value: -k, to: start),
                  let d1 = cal.date(byAdding: .day, value: 1, to: d0) else { continue }
            let pts = hist.filter { $0.t >= d0 && $0.t < d1 }
            let rs = pts.compactMap { $0.routine }.filter { $0 != 255 }
            let hrs = pts.compactMap { $0.hr }
            let rest = pts.filter { $0.vs != "NOT_WORN" && ($0.activity ?? 255) <= restActivityMax }.count
            let tier = pts.filter { ["DRINK", "COOL", "DANGER"].contains($0.vs) }.count
            var alerts = 0
            for (i, p) in pts.enumerated() where p.fam && (i == 0 || !pts[i - 1].fam) { alerts += 1 }
            let routine: Double? = rs.isEmpty ? nil : Double(rs.reduce(0, +)) / Double(rs.count) / 255.0 * 100.0
            let hrMean: Double? = hrs.isEmpty ? nil : Double(hrs.reduce(0, +)) / Double(hrs.count)
            out.append(DayStats(day: d0, minutes: pts.count, routine: routine, restMin: rest,
                                hrMean: hrMean, tierMin: tier, alerts: alerts))
        }
        return out
    }
}
