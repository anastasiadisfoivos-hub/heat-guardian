// Demo data for the doctor's report (labelled SIMULATION on every page): 30 constructed days ending today — an
// ordinary summer fortnight, then a heat wave over the last 7 days (hot nights from day 25). Every minute is a
// constructed STATUS frame fed through the real ReportLedger, and the EVENTS log matches it (same episode times).
// Deterministic (no randomness), so the Linux sample PDF and the app's demo report show the same numbers.
// NOT a measured record.

import Foundation

enum HeatReportDemo {
    /// Heat level of day i (0 = 29 days ago … 29 = today): 0 ordinary, rising to 1 at the heat wave's peak.
    static func heat(_ i: Int) -> Double {
        let wave: [Double] = [0.35, 0.55, 0.7, 0.85, 1.0, 0.95, 0.8]       // days 23…29
        if i >= 23 { return wave[i - 23] }
        return [0.0, 0.1, 0.2, 0.1, 0.0, 0.15, 0.25][i % 7]
    }

    static func lerp(_ a: Double, _ b: Double, _ h: Double) -> Int { Int((a + (b - a) * h).rounded()) }
    static func lerpD(_ a: Double, _ b: Double, _ h: Double) -> Double { a + (b - a) * h }

    /// A heat episode of day i (the same times as `entries`): start, peak and all-clear minute of day.
    struct Ep { var start: Int; var peak: Int; var end: Int; var check: (Int, Int)?; var cool: Bool }
    static func episode(_ i: Int) -> Ep? {
        let h = heat(i)
        guard h >= 0.55 else { return nil }
        let st = 14 * 60 + 5
        let en = i == 27 ? 17 * 60 + 25 : (i == 28 ? 17 * 60 + 50 : (h >= 0.85 ? 16 * 60 + 45 : 15 * 60 + 10))
        let ck: (Int, Int)? = i == 27 ? (16 * 60 + 20, 16 * 60 + 23) : (i == 28 ? (16 * 60 + 10, 16 * 60 + 24) : nil)
        return Ep(start: st, peak: st + Int(Double(en - st) * 0.55), end: en, check: ck, cool: h >= 0.85)
    }

    /// Sleep that ended on the morning of day i: (start from that day's midnight, negative = the evening before; end).
    static func sleep(_ i: Int) -> (Int, Int) {
        let h = heat(i), hot = h >= 0.5
        return (hot ? lerp(-40, 35, h) : -60 + [0, -10, 5, -15, 10, 0, -5][i % 7],
                hot ? lerp(400, 360, h) : 410 + [0, 10, -5, 15, 0, -10, 5][i % 7])
    }

    /// Where she is at minute m of day i: nil = home, else the place (the routine of the Her Day demo).
    static func outing(_ i: Int, _ m: Int) -> Bool {
        let market = i >= 24 ? (i == 26 ? 11 * 60 + 5 : 9 * 60 + 5 + (i % 3) * 7) : 10 * 60 + 20
        if m >= market && m < market + 30 { return true }
        if [2, 4, 5, 6].contains(i % 7) && heat(i) < 0.85 && m >= 18 * 60 && m < 19 * 60 { return true }
        return m >= 21 * 60 + 15 && m < 21 * 60 + 55
    }

    /// One constructed STATUS minute of day i (0 = 29 days ago … 29 = today), nil = no frame (today after 13:00).
    /// Built so the analysis has something real to find: her daytime pulse rises ~1.6 bpm per °C of air above 26 °C,
    /// episodes add a bump that decays more slowly on hotter days, the skin follows the room.
    static func frame(_ i: Int, _ m: Int) -> StatusFrame? {
        if i == 29 && m >= 13 * 60 { return nil }
        let h = heat(i)
        let jit = Double([0, 1, -1, 2, 0, -2, 1][i % 7]) * 0.3
        // outdoor air (min 05:30, max 15:30) and her flat (slower, peak ~17:00, warm nights in the heat wave)
        let tmax = 30 + 9 * h + jit, tmin = 21 + 7 * h
        func shape(_ peakMin: Int) -> Double { 0.5 + 0.5 * cos(2 * Double.pi * Double(m - peakMin) / 1440) }
        let tOut = tmin + (tmax - tmin) * shape(15 * 60 + 30)
        let tHome = 23.6 + 6 * h + (1.5 + 2.5 * h) * shape(17 * 60) + jit * 0.5
        let out = outing(i, m)
        let air = out ? tOut + 1.5 : tHome
        let rh = Int((out ? 50 - 1.5 * (tOut - 25) : 55 - 1.2 * (tHome - 24)).rounded())
        // asleep?
        let (s0, e0) = sleep(i), next = i < 29 ? sleep(i + 1).0 : 99999
        let asleep = (m < e0 && (s0 < 0 || m >= s0)) || (next < 0 && m >= 1440 + next)
        let charging = m >= 19 * 60 + 30 && m < 20 * 60 + 30
        let chores = !asleep && !out && (m % 180) < Int(lerpD(25, 10, h))
        let act = asleep ? 2 : (out ? 35 : (chores ? 26 : 8))
        // pulse and skin, + the episode bump (rise to the peak, then decay; slower on hotter days)
        let rest = 64.0 + (h >= 0.7 ? Double(Int((h - 0.5) * 20)) : 0) + Double([0, 1, 0, 2, 1, 0, 1][i % 7])
        var hr = asleep ? rest + 2 + Double((m * 7 + i * 13) % 5 - 2)
                        : rest + 10 + (act >= 25 ? 14 : 0) + 1.6 * max(0, air - 26) + Double((m * 3 + i) % 5 - 2)
        var skin = asleep ? 34.2 + 0.25 * (tHome - 25) : (out ? min(36.2, 32.4 + 0.4 * (tOut - 24)) : 32.4 + 0.35 * (tHome - 24))
        var est = 36.7 + 0.04 * max(0, air - 26)
        var state = 0
        if let e = episode(i), m >= e.start {
            let bumpHR = 6 + 8 * h + (e.check != nil ? 5 : 0), bumpSkin = 0.4 + 0.4 * h
            let tauHR = 18 + 30 * h, tauSkin = 30 + 40 * h
            let f: (Double) -> Double = { tau in
                m <= e.peak ? Double(m - e.start) / Double(max(1, e.peak - e.start)) : exp(-Double(m - e.peak) / tau)
            }
            hr += bumpHR * f(tauHR); skin += bumpSkin * f(tauSkin); est += 0.35 * f(tauHR)
            if m < e.end {
                state = 1
                if e.cool && m >= e.start + 55 { state = 2 }
                if let c = e.check, m >= c.0 && m < c.1 { state = 6 }
            }
        }
        return StatusFrame(version: 1, familyPending: false, notWorn: charging, stateCode: state, contactOK: true, timeSynced: true,
                           charging: charging, home: !out, ppgValid: !charging, coreC: charging ? 0 : est, halfRangeC: 0.4,
                           hrBpm: charging ? 0 : Int(hr.rounded()), hrQ: 2, t1C: charging ? nil : (skin * 10).rounded() / 10,
                           t2C: nil, tairC: (air * 10).rounded() / 10, rhPct: max(15, min(90, rh)), batteryPct: 70,
                           minuteCounter: m, alarmId16: nil, routineScore: 200, activity: charging ? 0 : act)
    }

    private static var cache: (String, [DayRecord])?

    /// The 30 constructed days through the REAL ledger (ReportLedger.add, minute by minute), `n` of them ending today.
    static func records(days n: Int = 30, today: Date, calendar cal: Calendar = .current) -> [DayRecord] {
        let led = ReportLedger(fileName: nil, calendar: cal)
        let d0 = cal.startOfDay(for: today)
        let key = led.key(d0)
        let all: [DayRecord]
        if let c = cache, c.0 == key {
            all = c.1
        } else {
            for i in 0..<30 {
                guard let day = cal.date(byAdding: .day, value: i - 29, to: d0) else { continue }
                for m in 0..<1440 {
                    guard let f = frame(i, m) else { break }
                    led.add(f, at: day.addingTimeInterval(Double(m * 60)))
                }
            }
            led.closeRun()
            all = led.records(last: 30, today: d0)
            cache = (key, all)
        }
        return Array(all.suffix(n))
    }

    /// The band's log for the same 30 days (simulated EVENTS through the real encoder + decoder).
    static func entries(today: Date, calendar cal: Calendar = .current) -> [LogEntry] {
        let d0 = cal.startOfDay(for: today)
        var seq = 0
        var out: [LogEntry] = []
        func at(_ i: Int, _ minute: Int) -> Date { cal.date(byAdding: .day, value: i - 29, to: d0)!.addingTimeInterval(Double(minute * 60)) }
        func add(_ ev: BandEvent, _ t: Date) {
            guard let back = try? Frames.decodeEvent(Frames.encodeEvent(ev)), let e = LogEntry.fromBand(back, receivedAt: t, simulated: true) else { return }
            out.append(e)
        }
        func ev(_ kind: BandEvent.Kind, _ arg: Int, _ t: Date) {
            seq += 1
            add(BandEvent(seq: seq, boot: 3, unix: UInt32(t.timeIntervalSince1970), kindRaw: kind.rawValue, arg: arg), t)
        }
        func held(_ t: Date, _ w: HeldWhat, _ r: HeldReason, _ a: Int) {
            seq += 1
            add(Frames.alertHeldEvent(seq: seq, boot: 3, unix: UInt32(t.timeIntervalSince1970), AlertHeld(what: w, reason: r, arg: a)), t)
        }
        func clear(_ t: Date, _ peak: Int, _ mins: Int, _ fam: Bool) {
            seq += 1
            add(Frames.allClearEvent(seq: seq, boot: 3, unix: UInt32(t.timeIntervalSince1970), AllClear(peak: peak, minutes: mins, familyCalled: fam, softTick: peak >= 2)), t)
        }
        func nudge(_ i: Int, _ id: NudgeID, _ minute: Int, missed: Bool) {
            ev(.nudgeShown, id.rawValue, at(i, minute))
            ev(missed ? .nudgeMissed : .nudgeDone, id.rawValue, at(i, minute + (missed ? 10 : 3)))
        }
        func visit(_ edge: VisitEdge, _ p: PlaceType, _ t: Date) {
            seq += 1
            let u = UInt32(t.timeIntervalSince1970)
            add(Frames.visitEvent(seq: seq, boot: 3, unix: u, VisitEvent(edge: edge, place: p, unix: u)), t)
        }
        for i in 0..<30 {
            let h = heat(i)
            let last = i == 29 ? 13 * 60 : 24 * 60
            // morning shower: the band holds its reminder (every day)
            if 7 * 60 + 35 < last { held(at(i, 7 * 60 + 35), .nudge, .shower, NudgeID.water.rawValue) }
            // reminders: water through the hot hours (more on hot days), every 4th one missed
            let waters = h >= 0.3 ? 4 : 2
            for k in 0..<waters where 11 * 60 + k * 100 < last { nudge(i, .water, 11 * 60 + k * 100, missed: (i + k) % 4 == 3) }
            if h >= 0.3 && 9 * 60 < last { nudge(i, .brief, 9 * 60, missed: false) }
            if i % 9 == 4 && 12 * 60 + 30 < last { held(at(i, 12 * 60 + 30), .drink, .persist, 1) }
            if i % 11 == 6 { held(at(i, 16 * 60 + 5), .drink, .notWorn, 1) }
            // heat-wave episodes
            if h >= 0.55 && 14 * 60 < last {
                ev(.warnShown, 1, at(i, 14 * 60 + 5))                                   // DRINK
                held(at(i, 14 * 60 + 40), .drink, .repeated, 1)
                if h >= 0.85 {
                    ev(.warnShown, 2, at(i, 15 * 60))                                    // COOL
                }
                if i == 27 {                                                             // a CHECK she answered
                    ev(.warnShown, 3, at(i, 16 * 60 + 20)); ev(.imOK, 1, at(i, 16 * 60 + 23))
                    clear(at(i, 17 * 60 + 25), 3, 200, false)
                } else if i == 28 {                                                      // a CHECK she missed: family called
                    ev(.warnShown, 3, at(i, 16 * 60 + 10))
                    seq += 1
                    add(BandEvent(seq: seq, boot: 3, unix: UInt32(at(i, 16 * 60 + 22).timeIntervalSince1970), kindRaw: 7, arg: 1), at(i, 16 * 60 + 22))
                    ev(.imOK, 1, at(i, 16 * 60 + 24))
                    clear(at(i, 17 * 60 + 50), 3, 225, true)
                } else {
                    clear(at(i, h >= 0.85 ? 16 * 60 + 45 : 15 * 60 + 10), h >= 0.85 ? 2 : 1, h >= 0.85 ? 160 : 65, false)
                }
            }
            if h >= 0.85 && i % 2 == 0 && 13 * 60 + 15 < last { held(at(i, 13 * 60 + 15), .cool, .oneEvidence, 2) }
            // Her Day on heat-wave days: the band held "market before 09:30" from the evening before
            if i >= 24 {
                seq += 1
                let echo = at(i - 1, 20 * 60)
                add(Frames.planItemEvent(seq: seq, boot: 3, unix: UInt32(echo.timeIntervalSince1970),
                                         DayPlanItem(day: 1, kind: .outingShift, place: .market, usual: 620, suggested: 570, direction: .before,
                                                     hotFrom: 10, hotTo: 20)), echo)
                let went = i == 26 ? 11 * 60 + 5 : 9 * 60 + 5 + (i % 3) * 7                 // one day she went in the heat
                if went < last {
                    visit(.arrive, .market, at(i, went)); visit(.leave, .market, at(i, went + 30))
                }
            }
        }
        return out.sorted { $0.at < $1.at }
    }

    static let meds: [Medication] = [
        Medication(name: "Furosemide 40 mg", cls: .diuretic),
        Medication(name: "Bisoprolol 2.5 mg", cls: nil),
        Medication(name: "Atorvastatin 20 mg", cls: .other),
    ]
}
