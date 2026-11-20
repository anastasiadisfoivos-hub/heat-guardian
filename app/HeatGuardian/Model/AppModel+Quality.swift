// Band 0.9.9 alert quality in AppModel (ECOSYSTEM_SPEC 5e): the Alert quality card's week, the quiet «Back to normal»
// status, and the demo's simulated ALERT_HELD / ALL_CLEAR / SCORE events (labelled SIMULATION), which go through the
// same encoder + decoder as a real band's.

import Foundation

extension AppModel {
    /// This week's alert quality (Family › History card).
    func alertQualityWeek() -> AlertQualityWeek {
        AlertQuality.week(activeStore.entries, now: isDemo ? (currentAt ?? Date()) : Date())
    }

    /// The quiet «Back to normal» status (nil = none in the last 2 h, or a warning came after it).
    func backToNormal(now: Date) -> (at: Date, clear: AllClear)? {
        AlertQuality.backToNormal(activeStore.entries, now: now)
    }

    // MARK: demo (ΠΡΟΣΟΜΟΙΩΣΗ)

    private func addDemoQualityEvent(_ ev: BandEvent, at: Date) {
        guard let back = try? Frames.decodeEvent(Frames.encodeEvent(ev)),
              let e = LogEntry.fromBand(back, receivedAt: at, simulated: true) else { return }
        demoStore.add(e)
    }

    static let demoBoot = 3

    /// Today's scripted hold-backs (minute, what, reason, arg) — emitted as the demo clock passes them.
    static let demoHeldScript: [(Int, HeldWhat, HeldReason, Int)] = [
        (7 * 60 + 40, .nudge, .shower, NudgeID.water.rawValue),
        (10 * 60 + 15, .drink, .persist, 1),
        (11 * 60 + 30, .cool, .oneEvidence, 2),
        (12 * 60 + 20, .drink, .ppg, 1),
    ]

    /// The band's scorecard at the last 8 midnights (one boot), so the card has a week before the demo day.
    func seedQualityDemo() {
        guard isDemo else { return }
        let cal = Calendar.current
        let d0 = cal.startOfDay(for: currentAt ?? Date())
        // per-day increments for the 7 days before today (oldest first)
        let nudges = [3, 4, 3, 5, 6, 6, 5], drink = [0, 1, 0, 1, 2, 1, 1], cool = [0, 0, 0, 0, 1, 1, 0], soft = [0, 0, 0, 1, 0, 1, 0]
        let check = [0, 0, 0, 0, 1, 0, 0], clear = [0, 1, 0, 1, 2, 2, 1], bedtime = [1, 1, 1, 1, 1, 1, 1], missed = [1, 1, 0, 1, 2, 1, 1]
        let held: [HeldReason: [Int]] = [.notWorn: [1, 0, 0, 1, 0, 0, 1], .loose: [0, 1, 0, 0, 0, 0, 0], .ppg: [0, 1, 0, 1, 1, 0, 1],
                                         .shower: [1, 1, 1, 1, 1, 1, 1], .sun: [0, 0, 1, 0, 1, 0, 0], .persist: [1, 2, 1, 2, 3, 2, 2],
                                         .repeated: [0, 0, 0, 1, 1, 1, 0], .oneEvidence: [0, 0, 0, 1, 0, 1, 0]]
        var s = ScoreSnapshot(at: d0, boot: AppModel.demoBoot)
        // counts from before the week (the boot started earlier)
        s.sent = [9, 2, 0, 0, 0, 0, 1, 3]; s.held[7] = 2; s.held[5] = 2; s.ack = 8; s.missed = 1; s.avgAckSeconds = 88; s.maxAckSeconds = 240
        for k in stride(from: 7, through: 0, by: -1) {
            guard let t = cal.date(byAdding: .day, value: -k, to: d0)?.addingTimeInterval(20) else { continue }
            if k < 7 {
                let i = 6 - k
                s.sent[0] += nudges[i]; s.sent[1] += drink[i]; s.sent[2] += cool[i]; s.sent[3] += soft[i]; s.sent[4] += check[i]
                s.sent[6] += clear[i]; s.sent[7] += bedtime[i]
                for (r, v) in held { s.held[r.rawValue] += v[i] }
                s.missed += missed[i]
                s.ack += nudges[i] - missed[i] + check[i]
                s.avgAckSeconds = 95 + i
                s.maxAckSeconds = max(s.maxAckSeconds, 300 + 10 * i)
            }
            let p2 = [s.held[9], s.ack, s.missed, 0, s.avgAckSeconds & 255, s.avgAckSeconds >> 8, s.maxAckSeconds & 255, s.maxAckSeconds >> 8]
            for (pg, vals) in [(0, s.sent), (1, Array(s.held[1...8])), (2, p2)] {
                demoSeq += 1
                addDemoQualityEvent(Frames.scoreEvent(seq: demoSeq, boot: AppModel.demoBoot, unix: UInt32(max(0, t.timeIntervalSince1970)),
                                                      ScorePage(page: pg, values: vals)), at: t)
            }
        }
    }

    /// Every demo minute: the scripted hold-backs, and one ALL_CLEAR when a shown episode (DRINK / COOL / CHECK /
    /// DANGER) returns to OK — with its length and whether the family was called. Returns true when it added.
    func synthQualityDemo(vs: String, fam: Bool, at: Date) -> Bool {
        guard isDemo else { return false }
        var added = false
        let d0 = Calendar.current.startOfDay(for: at)
        let m = at.minuteOfDay
        for (minute, what, reason, arg) in AppModel.demoHeldScript where m >= minute && demoNudgesFired.insert("q\(minute)").inserted {
            demoSeq += 1
            let t = d0.at(minute: minute)
            addDemoQualityEvent(Frames.alertHeldEvent(seq: demoSeq, boot: AppModel.demoBoot, unix: UInt32(max(0, t.timeIntervalSince1970)),
                                                      AlertHeld(what: what, reason: reason, arg: arg)), at: t)
            added = true
        }
        let level: Int = vs == "DRINK" ? 1 : (vs == "COOL" ? 2 : (vs == "CHECK" || vs == "DANGER" ? 3 : 0))
        if level > 0 {
            if var ep = demoEpisode {
                ep.peak = max(ep.peak, level)
                ep.family = ep.family || fam
                demoEpisode = ep
            } else {
                demoEpisode = (at, level, fam)
            }
        } else if vs == "OK", let ep = demoEpisode {
            demoEpisode = nil
            demoSeq += 1
            let mins = max(1, Int(at.timeIntervalSince(ep.start) / 60))
            addDemoQualityEvent(Frames.allClearEvent(seq: demoSeq, boot: AppModel.demoBoot, unix: UInt32(max(0, at.timeIntervalSince1970)),
                                                     AllClear(peak: ep.peak, minutes: mins, familyCalled: ep.family, softTick: ep.peak >= 2 || ep.family)), at: at)
            closeAlertOnAllClear(source: .demo)
            added = true
        }
        return added
    }
}
