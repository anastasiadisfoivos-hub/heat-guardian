// "Alert quality" (ECOSYSTEM_SPEC 5e, band 0.9.9; research report rank 3): this week, how many alerts the band SENT,
// how many it HELD BACK and why (in plain words), how many she ACKNOWLEDGED and how many were MISSED. Pure Swift.
//
// Two sources, best first:
//  1. the band's scorecard (EVENTS 13 SCORE, pages 0-2, counters since boot, sent at local midnight and on `score`):
//     per boot, the newest snapshot in the week minus the newest snapshot of that boot before the week (0 when none;
//     a snapshot from the first 5 min after midnight counts for the day before),
//     so a restart never subtracts across boots; saturating u8 counters are clamped at 0.
//  2. the log (always for the time after the newest snapshot): NUDGE_SHOWN + WARN_SHOWN (DRINK / COOL / CHECK /
//     DANGER) = sent, ALERT_HELD = held back (the band sends at most 16 a day), NUDGE_DONE + IM_OK = acknowledged,
//     NUDGE_MISSED = missed.

import Foundation

struct AlertQualityWeek: Equatable {
    enum Source: Equatable { case scorecard, log, none }
    var from: Date
    var sent: Int
    var held: [HeldReason: Int]
    var acknowledged: Int
    var missed: Int
    var avgAckSeconds: Int?
    var source: Source

    var heldTotal: Int { held.values.reduce(0, +) }
    /// Reasons with a count, biggest first (ties in reason order).
    var heldSorted: [(HeldReason, Int)] {
        held.filter { $0.value > 0 }.sorted { ($0.value, -$0.key.rawValue) > ($1.value, -$1.key.rawValue) }.map { ($0.key, $0.value) }
    }
}

/// One scorecard snapshot (pages 0-2 of one SCORE burst).
struct ScoreSnapshot: Equatable {
    var at: Date
    var boot: Int
    var sent: [Int] = Array(repeating: 0, count: 8)    // NUDGE, DRINK, COOL, COOL_SOFT, CHECK, FAMILY, ALL_CLEAR, BEDTIME
    var held: [Int] = Array(repeating: 0, count: 10)   // [reason 1...9], [0] unused
    var ack = 0
    var missed = 0
    var checkOneEvidence = 0
    var avgAckSeconds = 0
    var maxAckSeconds = 0
    var pages = Set<Int>()

    /// What the scorecard counts as "sent": every kind except ALL_CLEAR (index 6).
    var sentTotal: Int { sent.enumerated().filter { $0.offset != 6 }.map { $0.element }.reduce(0, +) }

    mutating func apply(_ p: ScorePage) {
        pages.insert(p.page)
        switch p.page {
        case 0: sent = p.values
        case 1: for i in 0..<8 { held[i + 1] = p.values[i] }
        default:
            held[9] = p.values[0]; ack = p.values[1]; missed = p.values[2]; checkOneEvidence = p.values[3]
            avgAckSeconds = p.values[4] | (p.values[5] << 8); maxAckSeconds = p.values[6] | (p.values[7] << 8)
        }
    }
}

enum AlertQuality {
    static let burst: TimeInterval = 120
    static let midnightGrace: TimeInterval = 300

    /// SCORE entries -> snapshots (one per boot and burst), oldest first.
    static func snapshots(_ entries: [LogEntry]) -> [ScoreSnapshot] {
        var out: [ScoreSnapshot] = []
        for e in entries.sorted(by: { $0.at < $1.at }) {
            guard let p = e.scorePage else { continue }
            let boot = e.boot ?? 0
            if let i = out.lastIndex(where: { $0.boot == boot && e.at.timeIntervalSince($0.at) <= burst && !$0.pages.contains(p.page) }) {
                out[i].apply(p)
            } else {
                var s = ScoreSnapshot(at: e.at, boot: boot)
                s.apply(p)
                out.append(s)
            }
        }
        return out
    }

    static func weekStart(_ now: Date, days: Int = 7, calendar cal: Calendar = .current) -> Date {
        cal.date(byAdding: .day, value: -(days - 1), to: cal.startOfDay(for: now)) ?? now
    }

    static func week(_ entries: [LogEntry], now: Date, days: Int = 7, calendar cal: Calendar = .current) -> AlertQualityWeek {
        let start = weekStart(now, days: days, calendar: cal)
        var w = AlertQualityWeek(from: start, sent: 0, held: [:], acknowledged: 0, missed: 0, avgAckSeconds: nil, source: .none)
        let snaps = snapshots(entries).filter { $0.at <= now }
        // a snapshot sent in the first minutes after midnight closes the day before (the band sends one at local midnight)
        func eff(_ x: ScoreSnapshot) -> Date { x.at.addingTimeInterval(-midnightGrace) }
        let inWeek = snaps.filter { eff($0) >= start }
        var logFrom = start
        if !inWeek.isEmpty {
            w.source = .scorecard
            var avg: [(Int, Int)] = []
            for boot in Set(inWeek.map { $0.boot }).sorted() {
                guard let last = inWeek.last(where: { $0.boot == boot }) else { continue }
                let base = snaps.last { $0.boot == boot && eff($0) < start } ?? ScoreSnapshot(at: start, boot: boot)
                w.sent += max(0, last.sentTotal - base.sentTotal)
                for r in HeldReason.allCases {
                    let d = max(0, last.held[r.rawValue] - base.held[r.rawValue])
                    if d > 0 { w.held[r, default: 0] += d }
                }
                let ack = max(0, last.ack - base.ack)
                w.acknowledged += ack
                w.missed += max(0, last.missed - base.missed)
                if ack > 0 && last.avgAckSeconds > 0 { avg.append((last.avgAckSeconds, ack)) }
            }
            let n = avg.map { $0.1 }.reduce(0, +)
            if n > 0 { w.avgAckSeconds = avg.map { $0.0 * $0.1 }.reduce(0, +) / n }
            logFrom = inWeek.map { $0.at }.max() ?? start
        }
        // the log for whatever the newest snapshot does not cover yet (all of the week without a scorecard)
        let covered = w.source == .scorecard
        let tail = entries.filter { $0.at <= now && (covered ? $0.at > logFrom : $0.at >= start) }
        var any = false
        for e in tail {
            switch e.kind {
            case .nudgeShown: w.sent += 1; any = true
            case .warnShown where ["DRINK", "COOL", "CHECK", "DANGER"].contains(e.warnState ?? ""): w.sent += 1; any = true
            case .alertHeld:
                if let h = e.alertHeld, h.what != .check { w.held[h.reason, default: 0] += 1; any = true }
            case .nudgeDone, .imOK: w.acknowledged += 1; any = true
            case .nudgeMissed: w.missed += 1; any = true
            default: break
            }
        }
        if w.source == .none && any { w.source = .log }
        return w
    }

    /// The newest ALL_CLEAR at or before `now` that came after the last warning / HELP: the quiet "Back to normal"
    /// status (Family Today subtitle, Elder guidance) for `window` seconds.
    static func backToNormal(_ entries: [LogEntry], now: Date, window: TimeInterval = 2 * 3600) -> (at: Date, clear: AllClear)? {
        guard let c = entries.last(where: { $0.kind == .allClear && $0.at <= now }), let ac = c.allClear,
              now.timeIntervalSince(c.at) <= window else { return nil }
        let later = entries.contains { e in
            e.at > c.at && e.at <= now && (e.kind == .help || (e.kind == .warnShown && ["DRINK", "COOL", "CHECK", "DANGER"].contains(e.warnState ?? "")))
        }
        return later ? nil : (c.at, ac)
    }
}
