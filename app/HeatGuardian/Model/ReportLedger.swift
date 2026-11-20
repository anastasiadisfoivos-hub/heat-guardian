// Per-day aggregates for the doctor's report, built ON THE PHONE from every live STATUS minute the band sent
// (no extra data from the band, no server). Kept 31 days in Application Support/report_days.json, protected "complete
// until first user authentication" like the Tower's file: the band's minute frames wake the app while the phone is
// LOCKED, and a "complete" file can be neither read nor written then (every save in the pocket failed, and a launch
// while locked started from an empty ledger that the next unlocked save wrote over the month). A file that exists but
// cannot be read is never overwritten: save() first reads it again and merges (`pendingReload`). The band's Body Twin core estimate is kept apart (`est5`) and reaches the report ONLY when
// HeatReportBuilder.SHOW_TWIN_ESTIMATE is switched on (default off), labelled "model estimate, not measured".
//
// 5-minute means (288 slots a day) of pulse, wrist skin temperature, air at home / out and humidity: the 24 h profile,
// heart response to heat and recovery after an episode are computed from them.
//
// Per day: minutes received; air around her (band air sensor) by temperature band, split home / out by the STATUS
// home bit; the night (00:00-06:00) at home; pulse while still (histogram -> resting pulse = 10th percentile);
// movement; wrist skin temperature (context only); minutes per band state word (Όλα καλά / Ζεστή μέρα / Πολλή ζέστη);
// the longest still stretch that ended that morning (= estimated sleep).

import Foundation

/// 288 five-minute slots of a day: running sums and counts (mean = sum / n).
struct Series5: Codable, Equatable {
    static let slots = 288
    var sum = [Double](repeating: 0, count: Series5.slots)
    var n = [Int](repeating: 0, count: Series5.slots)
    mutating func add(_ slot: Int, _ x: Double) {
        guard slot >= 0, slot < Series5.slots else { return }
        sum[slot] += x; n[slot] += 1
    }
    func mean(_ slot: Int) -> Double? { slot >= 0 && slot < Series5.slots && n[slot] > 0 ? sum[slot] / Double(n[slot]) : nil }
    /// Mean of hour h (12 slots).
    func hour(_ h: Int) -> Double? {
        let r = (h * 12)..<(h * 12 + 12)
        let c = r.map { n[$0] }.reduce(0, +)
        return c > 0 ? r.map { sum[$0] }.reduce(0, +) / Double(c) : nil
    }
    var isEmpty: Bool { !n.contains { $0 > 0 } }
    var values: [Double] { (0..<Series5.slots).compactMap { mean($0) } }
}

struct DayRecord: Codable, Equatable {
    static let bands: [Double] = [26, 28, 30, 32]          // air bands: <26, 26-28, 28-30, 30-32, >=32 °C
    var day: String                       // yyyy-mm-dd, local
    var minutes = 0                       // STATUS minutes received
    var worn = 0
    var home = [0, 0, 0, 0, 0]            // worn minutes per air band at home
    var out = [0, 0, 0, 0, 0]             // … away from home
    var nightMin = 0                      // worn minutes 00:00-06:00 at home with an air reading
    var nightWarm = 0                     // of those, air >= 26 °C
    var stillHR: [String: Int] = [:]      // bpm -> minutes (valid pulse while still); String keys = plain JSON object
    var activeMin = 0                     // worn minutes with movement (accel std > 20 mg)
    var skinSum = 0.0, skinN = 0, skinMin: Double? = nil, skinMax: Double? = nil
    var airHomeSum = 0.0, airHomeN = 0
    var stateMin = [0, 0, 0]              // Όλα καλά / Ζεστή μέρα / Πολλή ζέστη
    var sleepStart: Int? = nil            // minutes from this day's midnight (negative = the evening before)
    var sleepEnd: Int? = nil
    // 5-minute means
    var hr5 = Series5()                   // pulse (valid readings)
    var skin5 = Series5()                 // wrist skin temperature (plausible 28-40.5 °C)
    var airHome5 = Series5()              // band air sensor, at home
    var airOut5 = Series5()               // band air sensor, away from home
    var rh5 = Series5()                   // humidity at the band
    var act5 = Series5()                  // movement (accel std, mg)
    var est5 = Series5()                  // Body Twin core ESTIMATE (model, not measured; report only behind a switch)

    static func band(_ t: Double) -> Int { bands.firstIndex { t < $0 } ?? bands.count }

    /// Hours with the air around her >= `c` °C (c in 26 / 28 / 30 / 32), at home or out.
    func hoursAtOrAbove(_ c: Double, home h: Bool) -> Double {
        let i = DayRecord.bands.firstIndex(of: c).map { $0 + 1 } ?? 5
        return Double((h ? home : out)[i...].reduce(0, +)) / 60.0
    }

    /// A hot night: at least 2 h of night data at home and the air stayed >= 26 °C for most of it. nil = not enough data.
    var hotNight: Bool? { nightMin >= 120 ? nightWarm * 2 >= nightMin : nil }

    /// Resting pulse: 10th percentile of her pulse while still (>= 60 still minutes), nil otherwise.
    var restingHR: Int? {
        let pts = stillHR.compactMap { k, v in Int(k).map { ($0, v) } }.sorted { $0.0 < $1.0 }
        let n = pts.map { $0.1 }.reduce(0, +)
        guard n >= 60 else { return nil }
        var acc = 0
        for (bpm, c) in pts { acc += c; if acc * 10 >= n { return bpm } }
        return pts.last?.0
    }

    var skinMean: Double? { skinN > 0 ? skinSum / Double(skinN) : nil }
    var airHomeMean: Double? { airHomeN > 0 ? airHomeSum / Double(airHomeN) : nil }
    /// The day's most strained band state word (0 Όλα καλά, 1 Ζεστή μέρα, 2 Πολλή ζέστη); nil without data.
    var worstState: Int? { minutes == 0 ? nil : (stateMin[2] > 0 ? 2 : (stateMin[1] > 0 ? 1 : 0)) }
}

extension StatusFrame {
    /// Same as AppModel.viewState for a decoded frame: NOT_WORN wins over the state.
    var viewState: String { notWorn ? "NOT_WORN" : state }
}

/// Builds DayRecords minute by minute. `fileName` nil = in memory (tests, demo).
final class ReportLedger {
    static let keepDays = 31
    static let stillMax = Week.restActivityMax           // accel std <= 3 mg = still (same as Her week)
    static let activeMin = 20                             // accel std > 20 mg = moving
    static let sleepMinRun = 180                          // a still stretch of >= 3 h …
    static let sleepBreak = 15                            // … broken only by > 15 min of movement / no data

    private(set) var days: [String: DayRecord] = [:]
    // the running still stretch (not persisted: a restart starts a new one)
    private var runStart: Date?
    private var lastStill: Date?
    private let url: URL?
    let calendar: Calendar
    /// The file exists but could not be READ (data protection while locked): do not write over it until it is read.
    private(set) var pendingReload = false
    private let read: (URL) throws -> Data

    /// Background writes while the phone is locked must succeed (NOT .completeFileProtection; same class as tower.json).
    static let writeOptions: Data.WritingOptions = [.atomic, .completeFileProtectionUntilFirstUserAuthentication]

    convenience init(fileName: String? = "report_days.json", calendar: Calendar = .current) {
        self.init(url: fileName.map {
            FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent($0)
        }, calendar: calendar)
    }

    init(url: URL?, calendar: Calendar = .current, read: @escaping (URL) throws -> Data = { try Data(contentsOf: $0) }) {
        self.calendar = calendar
        self.url = url
        self.read = read
        reload()
    }

    /// Reads the file and merges it in (a day in both keeps the record with more minutes).
    private func reload() {
        guard let u = url else { pendingReload = false; return }
        guard FileManager.default.fileExists(atPath: u.path) else { pendingReload = false; return }
        guard let d = try? read(u) else { pendingReload = true; return }   // locked: try again before writing
        pendingReload = false
        guard let r = try? JSONDecoder().decode([DayRecord].self, from: d) else { return }   // corrupt: start again
        for x in r where (days[x.day]?.minutes ?? -1) < x.minutes { days[x.day] = x }
    }

    func key(_ d: Date) -> String {
        let c = calendar.dateComponents([.year, .month, .day], from: d)
        return String(format: "%04d-%02d-%02d", c.year ?? 0, c.month ?? 0, c.day ?? 0)
    }

    /// The state word index of a STATUS view state.
    static func stateWord(_ vs: String) -> Int? {
        switch vs {
        case "OK", "IMOK": return 0
        case "DRINK", "COOL": return 1
        case "CHECK", "DANGER", "HELP": return 2
        default: return nil                               // NOT_WORN, BATTERY, WAIT
        }
    }

    /// One STATUS minute.
    func add(_ d: StatusFrame, at: Date) {
        let k = key(at)
        var r = days[k] ?? DayRecord(day: k)
        r.minutes += 1
        let vs = d.viewState
        if let w = ReportLedger.stateWord(vs) { r.stateMin[w] += 1 }
        let worn = !d.notWorn
        var still = false
        let mod = calendar.component(.hour, from: at) * 60 + calendar.component(.minute, from: at)
        let slot = mod / 5
        if worn {
            r.worn += 1
            if let t = d.tairC { if d.home { r.airHome5.add(slot, t) } else { r.airOut5.add(slot, t) } }
            if let h = d.rhPct { r.rh5.add(slot, Double(h)) }
            if d.hrBpm > 0 && d.ppgValid { r.hr5.add(slot, Double(d.hrBpm)) }
            if let s = d.t1C, s >= 28, s <= 40.5 { r.skin5.add(slot, s) }
            if d.hasEstimate { r.est5.add(slot, d.coreC) }
            if let a = d.activity { r.act5.add(slot, Double(a)) }
            if let t = d.tairC {
                let b = DayRecord.band(t)
                if d.home { r.home[b] += 1 } else { r.out[b] += 1 }
                if d.home {
                    r.airHomeSum += t; r.airHomeN += 1
                    if mod < 6 * 60 { r.nightMin += 1; if t >= 26 { r.nightWarm += 1 } }
                }
            }
            if let a = d.activity {
                still = a <= ReportLedger.stillMax
                if a > ReportLedger.activeMin { r.activeMin += 1 }
            }
            if still && d.hrBpm > 0 && d.ppgValid { r.stillHR[String(d.hrBpm), default: 0] += 1 }
            if let s = d.t1C, s >= 28, s <= 40.5 {
                r.skinSum += s; r.skinN += 1
                r.skinMin = min(r.skinMin ?? s, s); r.skinMax = max(r.skinMax ?? s, s)
            }
        }
        days[k] = r
        trackSleep(still: still, at: at)
    }

    /// The longest still stretch (>= 3 h, starting 19:00-04:00) is that night's estimated sleep, filed on the day it
    /// ended. Movement or missing data longer than 15 min ends a stretch.
    private func trackSleep(still: Bool, at: Date) {
        if let ls = lastStill, at.timeIntervalSince(ls) > Double(ReportLedger.sleepBreak * 60) { closeRun() }
        if still {
            if runStart == nil { runStart = at }
            lastStill = at
        }
    }

    func closeRun() {
        defer { runStart = nil; lastStill = nil }
        guard let s = runStart, let e = lastStill, e.timeIntervalSince(s) >= Double(ReportLedger.sleepMinRun * 60) else { return }
        let h = calendar.component(.hour, from: s)
        guard h >= 19 || h < 4 else { return }
        let k = key(e)
        var r = days[k] ?? DayRecord(day: k)
        let d0 = calendar.startOfDay(for: e)
        let st = Int(s.timeIntervalSince(d0) / 60), en = Int(e.timeIntervalSince(d0) / 60)
        if r.sleepStart == nil || (en - st) > ((r.sleepEnd ?? 0) - (r.sleepStart ?? 0)) { r.sleepStart = st; r.sleepEnd = en }
        days[k] = r
    }

    /// The records of the `n` days ending `today` (missing days = empty records), oldest first.
    func records(last n: Int, today: Date) -> [DayRecord] {
        let d0 = calendar.startOfDay(for: today)
        return (0..<n).reversed().compactMap { back in
            calendar.date(byAdding: .day, value: -back, to: d0).map { days[key($0)] ?? DayRecord(day: key($0)) }
        }
    }

    func prune(today: Date = Date()) {
        guard let cut = calendar.date(byAdding: .day, value: -ReportLedger.keepDays, to: calendar.startOfDay(for: today)) else { return }
        let ck = key(cut)
        days = days.filter { $0.key >= ck }
    }

    func save() {
        guard let u = url else { return }
        if pendingReload { reload() }
        guard !pendingReload else { return }               // still unreadable: keep it in memory, write later
        prune()
        try? FileManager.default.createDirectory(at: u.deletingLastPathComponent(), withIntermediateDirectories: true)
        let arr = days.values.sorted { $0.day < $1.day }
        if let d = try? JSONEncoder().encode(arr) { try? d.write(to: u, options: ReportLedger.writeOptions) }
    }

    func clear() {
        days = [:]; runStart = nil; lastStill = nil; pendingReload = false
        if let u = url { try? FileManager.default.removeItem(at: u) }
    }
}
