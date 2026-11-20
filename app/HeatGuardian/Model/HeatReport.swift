// «Heat report for the doctor» — the document MODEL. After Foivos's rescope (Nov 18) it is a HEALTH TRACK of her body
// in heat (HeatBody.swift): wrist skin temperature next to the air, heart response to heat, recovery after each
// episode, each alert with what the sensors showed, sleep and movement on hot vs normal days, her heat reaction in
// plain words with how sure it is; the questions for the doctor move to the last page.
//
// The model is a list of BLOCKS (cover, summary, chart, chart pair, table, …) with explicit page breaks, plus generic
// chart specs (ChartSpec) and table specs (TableSpec). Three renderers draw the SAME model: the app screen
// (BodyInHeatView, Swift Charts), the on-phone PDF (HeatReportPDF, UIKit) and the Linux sample (tools/report_mirror.py,
// from this model's JSON). Nothing here leaves the phone except through the share sheet.
//
// Rules: no core / body-temperature number unless SHOW_TWIN_ESTIMATE is switched on (then labelled "model estimate,
// not measured"); skin is always "wrist skin temperature"; strain only as the band's words; medicines only with "ask
// your doctor whether this matters in heat"; questions are questions; SIMULATION on every page in demo.

import Foundation

struct ChartSpec: Codable, Equatable, Identifiable {
    struct Tick: Codable, Equatable { var v: Double; var label: String }
    /// kind: line, dashed, dots, bars, range ([x, lo, hi]), rule ([[y]] horizontal), stack ([x, v1…v4] on the band ramp).
    /// color: a token (primary, heat, heatdark, water, health, text2, skinband, danger).
    struct Series: Codable, Equatable { var name: String; var kind: String; var color: String; var pts: [[Double]] }
    var id: String
    var title: String
    var note: String?
    var h: Double                 // height in the PDF (points)
    var xMin: Double, xMax: Double, yMin: Double, yMax: Double
    var xTicks: [Tick], yTicks: [Tick]
    var series: [Series]
    var barWidth: Double = 0.6    // in x units
    var legend: Bool = true
}

struct TableSpec: Codable, Equatable {
    struct Col: Codable, Equatable { var label: String; var w: Double; var align: String }   // l, r, c
    var cols: [Col]
    var rows: [[String]]
    var dotCol: Int? = nil
    var dots: [String?] = []      // colour token per row for dotCol
    var boldCol: Int? = nil
    var bold: [Bool] = []
    var note: String? = nil
}

struct HeatReport: Codable, Equatable {
    struct Figure: Codable, Equatable { var value: String; var label: String }
    struct Med: Codable, Equatable { var name: String; var cls: String?; var guessed: Bool; var flagged: Bool }
    struct Line: Codable, Equatable { var text: String; var conf: String? }
    struct Block: Codable, Equatable {
        var kind: String          // cover, heading, para, note, summary, figures, chart, pair, table, questions, meds, privacy, twinwarn, break
        var text: String? = nil
        var lines: [Line]? = nil
        var items: [String]? = nil
        var figures: [Figure]? = nil
        var chart: ChartSpec? = nil
        var chart2: ChartSpec? = nil
        var table: TableSpec? = nil
        var meds: [Med]? = nil
    }

    var lang: String
    var simulated: Bool
    var twin: Bool
    var name: String?
    var days: Int
    var periodText: String
    var generatedText: String
    var summary: [Line]
    var figures: [Figure]
    var charts: [ChartSpec]
    var alerts: TableSpec
    var daily: TableSpec
    var fit: Fit?
    var baselineHR: Double?
    var restingHR: Int?
    var meds: [Med]
    var questions: [String]
    var blocks: [Block]
    var t: [String: String]

    func chart(_ id: String) -> ChartSpec? { charts.first { $0.id == id } }
}

struct ReportInput {
    var records: [DayRecord]              // oldest first, `days` of them ending today
    var entries: [LogEntry]               // the band's log (any range; the builder filters)
    var meds: [Medication]
    var name: String?
    var days: Int
    var now: Date
    var simulated: Bool
}

enum HeatReportBuilder {
    /// Foivos's switch: the Body Twin's core ESTIMATE section ("model estimate, not measured"). Off by default.
    static let SHOW_TWIN_ESTIMATE = false
    static let maxQuestions = 6
    static let restHRAbove = 10
    static let maxAlertRows = 14

    static func build(_ inp: ReportInput, L: Strings, calendar cal: Calendar = .current, showTwin: Bool = SHOW_TWIN_ESTIMATE) -> HeatReport {
        let loc = L.lang.locale
        let d0 = cal.startOfDay(for: inp.now)
        let start = cal.date(byAdding: .day, value: -(inp.days - 1), to: d0) ?? d0
        func df(_ f: String) -> DateFormatter { let x = DateFormatter(); x.locale = loc; x.calendar = cal; x.timeZone = cal.timeZone; x.dateFormat = f; return x }
        let fDay = df("EEE d/M"), fNum = df("d"), fLong = df("d MMMM yyyy"), fHM = df("HH:mm"), fShort = df("d/M")
        let entries = inp.entries.filter { $0.at >= start && $0.at <= inp.now }.sorted { $0.at < $1.at }
        let recs = inp.records
        let n = recs.count
        let dates = (0..<n).map { cal.date(byAdding: .day, value: $0, to: start) ?? start }
        let dayTicks = (0..<n).filter { n <= 16 || $0 % 2 == 0 }.map { ChartSpec.Tick(v: Double($0), label: fNum.string(from: dates[$0])) }
        func dayIndex(_ d: Date) -> Int? { let i = cal.dateComponents([.day], from: start, to: cal.startOfDay(for: d)).day ?? -1; return i >= 0 && i < n ? i : nil }
        func r1(_ x: Double) -> Double { (x * 10).rounded() / 10 }
        func range(_ vals: [Double], step: Double, pad: Double) -> (Double, Double) {
            guard let lo = vals.min(), let hi = vals.max() else { return (0, step) }
            let a = (floor((lo - pad) / step) * step), b = ceil((hi + pad) / step) * step
            return (a, max(b, a + step))
        }
        func yTicks(_ a: Double, _ b: Double, _ step: Double, _ unit: String) -> [ChartSpec.Tick] {
            stride(from: a, through: b + 1e-9, by: step).map { ChartSpec.Tick(v: $0, label: (step < 1 ? String(format: "%.1f", $0) : String(Int($0.rounded()))) + unit) }
        }

        // ---- 1. wrist skin temperature + air + humidity, per day
        var charts: [ChartSpec] = []
        var skinRange: [[Double]] = [], skinMean: [[Double]] = [], airHome: [[Double]] = [], airOut: [[Double]] = [], rhDay: [[Double]] = []
        for (i, r) in recs.enumerated() {
            let x = Double(i)
            if let a = r.skinMin, let b = r.skinMax { skinRange.append([x, a, b]) }
            if let m = r.skinMean { skinMean.append([x, r1(m)]) }
            if let a = r.airHomeMean { airHome.append([x, r1(a)]) }
            let outs = r.airOut5.values
            if !outs.isEmpty { airOut.append([x, r1(outs.reduce(0, +) / Double(outs.count))]) }
            let rh = r.rh5.values
            if !rh.isEmpty { rhDay.append([x, (rh.reduce(0, +) / Double(rh.count)).rounded()]) }
        }
        let skinAll = skinRange.flatMap { [$0[1], $0[2]] } + airHome.map { $0[1] } + airOut.map { $0[1] }
        let (sLo, sHi) = range(skinAll, step: 2, pad: 0.5)
        charts.append(ChartSpec(id: "skin_days", title: L.bhSkinDays, note: L.bhSkinNote, h: 200, xMin: -0.5, xMax: Double(n) - 0.5,
                                yMin: sLo, yMax: sHi, xTicks: dayTicks, yTicks: yTicks(sLo, sHi, 2, "°"),
                                series: [.init(name: L.bhSkinRange, kind: "range", color: "skinband", pts: skinRange),
                                         .init(name: L.bhSkinMean, kind: "line", color: "primary", pts: skinMean),
                                         .init(name: L.bhAirHome, kind: "line", color: "heat", pts: airHome),
                                         .init(name: L.bhAirOut, kind: "dashed", color: "heatdark", pts: airOut)], barWidth: 0.42))
        let (hLo, hHi) = range(rhDay.map { $0[1] }, step: 10, pad: 2)
        charts.append(ChartSpec(id: "rh_days", title: L.bhRhDays, note: nil, h: 105, xMin: -0.5, xMax: Double(n) - 0.5, yMin: hLo, yMax: hHi,
                                xTicks: dayTicks, yTicks: yTicks(hLo, hHi, 10, "%"),
                                series: [.init(name: L.bhRh, kind: "line", color: "water", pts: rhDay)], legend: false))

        // 24 h profile of the hottest day (most hours at home >= 28 °C, else the warmest air at home)
        let hottest = recs.indices.filter { recs[$0].minutes >= 600 }.max { a, b in
            (recs[a].hoursAtOrAbove(28, home: true), recs[a].airHomeMean ?? 0) < (recs[b].hoursAtOrAbove(28, home: true), recs[b].airHomeMean ?? 0)
        }
        if let hi = hottest {
            let r = recs[hi]
            var sk: [[Double]] = [], ah: [[Double]] = [], ao: [[Double]] = [], rh: [[Double]] = []
            for h in 0..<24 {
                let x = Double(h) + 0.5
                if let v = r.skin5.hour(h) { sk.append([x, r1(v)]) }
                if let v = r.airHome5.hour(h) { ah.append([x, r1(v)]) }
                if let v = r.airOut5.hour(h) { ao.append([x, r1(v)]) }
                if let v = r.rh5.hour(h) { rh.append([x, v.rounded()]) }
            }
            let xt = stride(from: 0, through: 24, by: 6).map { ChartSpec.Tick(v: Double($0), label: String(format: "%02d:00", $0 % 24)) }
            let (lo, hi2) = range((sk + ah + ao).map { $0[1] }, step: 2, pad: 0.5)
            let title = L.bhProfile(fDay.string(from: dates[hi]))
            charts.append(ChartSpec(id: "skin_24h", title: title, note: nil, h: 190, xMin: 0, xMax: 24, yMin: lo, yMax: hi2, xTicks: xt,
                                    yTicks: yTicks(lo, hi2, 2, "°"),
                                    series: [.init(name: L.bhSkinMean, kind: "line", color: "primary", pts: sk),
                                             .init(name: L.bhAirHome, kind: "line", color: "heat", pts: ah),
                                             .init(name: L.bhAirOut, kind: "dots", color: "heatdark", pts: ao)]))
            let (rlo, rhi) = range(rh.map { $0[1] }, step: 10, pad: 2)
            charts.append(ChartSpec(id: "rh_24h", title: L.bhRhProfile, note: nil, h: 190, xMin: 0, xMax: 24, yMin: rlo, yMax: rhi, xTicks: xt,
                                    yTicks: yTicks(rlo, rhi, 10, "%"), series: [.init(name: L.bhRh, kind: "line", color: "water", pts: rh)], legend: false))
        }

        // ---- 2. heart response to heat (episodes and moving slots left out)
        let spans = episodes(entries)
        let epSlots: [Int: [ClosedRange<Int>]] = Dictionary(grouping: spans.compactMap { sp -> (Int, ClosedRange<Int>)? in
            guard let i = dayIndex(sp.start) else { return nil }
            let d = cal.startOfDay(for: sp.start)
            let a = Int(sp.start.timeIntervalSince(d) / 300), b = Int((sp.end ?? sp.start.addingTimeInterval(3600)).timeIntervalSince(d) / 300) + 36
            return (i, a...max(a, b))                                   // + 3 h after the end: the recovery tail
        }, by: { $0.0 }).mapValues { $0.map { $0.1 } }
        let skip: (Int, Int) -> Bool = { i, s in epSlots[i]?.contains { $0.contains(s) } ?? false }
        let hourlyPts = HeatBody.hourly(recs, skip: skip)
        let pts = hourlyPts.compactMap { p in p.hr.map { (air: p.air, hr: $0, day: p.day) } }
        let fit = HeatBody.fit(pts)
        let base = HeatBody.baselines(hourlyPts)
        let skinLine = HeatBody.skinLine(hourlyPts.compactMap { p in p.skin.map { (air: p.air, skin: $0) } })
        let rests = recs.compactMap { $0.restingHR }
        let restMed = rests.count >= 5 ? Int(HeatBody.median(rests.map(Double.init))!.rounded()) : nil
        if !pts.isEmpty {
            let (xLo, xHi) = range(pts.map { $0.air }, step: 2, pad: 0.3)
            let (yLo, yHi) = range(pts.map { $0.hr } + [base.hr ?? pts[0].hr], step: 10, pad: 2)
            var ser: [ChartSpec.Series] = [.init(name: L.bhHourPoints, kind: "dots", color: "primary", pts: pts.map { [r1($0.air), $0.hr.rounded()] })]
            if let f = fit {
                let xs = [xLo, max(xLo, HeatBody.ref), xHi].filter { $0 >= xLo }
                ser.append(.init(name: L.bhFitLine(f.b), kind: "line", color: "heat",
                                 pts: xs.map { [$0, r1(f.a + f.b * max(0, $0 - HeatBody.ref))] }))
            }
            if let b = base.hr { ser.append(.init(name: L.bhNormal(Int(b.rounded())), kind: "rule", color: "text2", pts: [[b.rounded()]])) }
            charts.append(ChartSpec(id: "hr_scatter", title: L.bhHRTitle, note: fit.map { L.bhFitNote($0, L.bhConf(HeatBody.confidence($0))) } ?? L.bhFitNone,
                                    h: 250, xMin: xLo, xMax: xHi, yMin: yLo, yMax: yHi,
                                    xTicks: stride(from: xLo, through: xHi + 1e-9, by: 2).map { .init(v: $0, label: "\(Int($0))°") },
                                    yTicks: yTicks(yLo, yHi, 10, ""), series: ser, barWidth: 0.6))
        }
        let restPts = recs.enumerated().compactMap { i, r in r.restingHR.map { [Double(i), Double($0)] } }
        if !restPts.isEmpty {
            let (lo, hi) = range(restPts.map { $0[1] } + [Double(restMed ?? Int(restPts[0][1]))], step: 5, pad: 3)
            var ser: [ChartSpec.Series] = [.init(name: L.bhRest, kind: "line", color: "primary", pts: restPts)]
            if let b = restMed { ser.append(.init(name: L.bhUsual(b), kind: "rule", color: "text2", pts: [[Double(b)]])) }
            charts.append(ChartSpec(id: "hr_rest", title: L.bhRestTitle, note: L.bhRestNote, h: 210, xMin: -0.5, xMax: Double(n) - 0.5,
                                    yMin: lo, yMax: hi, xTicks: dayTicks, yTicks: yTicks(lo, hi, 5, ""), series: ser))
        }

        // ---- 3. episodes + recovery
        let hrExpect: (Double?) -> Double? = { air in
            if let f = fit, let a = air { return f.a + f.b * max(0, a - HeatBody.ref) }
            return base.hr
        }
        let skinExpect: (Double?) -> Double? = { air in
            if let l = skinLine, let a = air { return l.c + l.d * a }
            return base.skin
        }
        var recov: [(EpisodeSpan, Recovery)] = []
        for sp in spans.sorted(by: { $0.start < $1.start }) {
            guard let i = dayIndex(sp.start) else { continue }
            let d = cal.startOfDay(for: sp.start)
            let from = Int(sp.start.timeIntervalSince(d) / 60), to = Int((sp.end ?? sp.start.addingTimeInterval(3600)).timeIntervalSince(d) / 60)
            recov.append((sp, HeatBody.recovery(recs[i], at: sp.start, from: from, to: min(to, 1439), hrExpect: hrExpect, skinExpect: skinExpect)))
        }
        if !recov.isEmpty {
            let hrB = recov.enumerated().compactMap { i, x in x.1.hrMin.map { [Double(i) - 0.18, Double($0)] } }
            let skB = recov.enumerated().compactMap { i, x in x.1.skinMin.map { [Double(i) + 0.18, Double($0)] } }
            let top = max(60, (hrB + skB).map { $0[1] }.max() ?? 60)
            let yMax = ceil(top / 30) * 30
            charts.append(ChartSpec(id: "recovery", title: L.bhRecTitle, note: L.bhRecNote, h: 210, xMin: -0.6, xMax: Double(recov.count) - 0.4,
                                    yMin: 0, yMax: yMax, xTicks: recov.enumerated().map { .init(v: Double($0.offset), label: fShort.string(from: $0.element.1.at)) },
                                    yTicks: yTicks(0, yMax, yMax > 120 ? 60 : 30, ""),
                                    series: [.init(name: L.bhRecHR, kind: "bars", color: "primary", pts: hrB),
                                             .init(name: L.bhRecSkin, kind: "bars", color: "heat", pts: skB)], barWidth: 0.32))
        }

        // ---- 4. the alerts table
        let alertRows = alertTable(entries, recs: recs, start: start, recov: recov, L: L, fDay: fDay, fHM: fHM, cal: cal)

        // ---- 5. sleep and movement, hot vs normal days
        let hot = recs.map { HeatBody.isHot($0) }
        let clock: (Double) -> String = { v in String(format: "%02d:00", ((Int(-v) / 60) + 24) % 24) }
        let sleepHot = recs.enumerated().compactMap { i, r in hot[i] ? r.sleepStart.flatMap { s in r.sleepEnd.map { [Double(i), Double(-s), Double(-$0)] } } : nil }
        let sleepNorm = recs.enumerated().compactMap { i, r in !hot[i] ? r.sleepStart.flatMap { s in r.sleepEnd.map { [Double(i), Double(-s), Double(-$0)] } } : nil }
        charts.append(ChartSpec(id: "sleep", title: L.bhSleepTitle, note: nil, h: 250, xMin: -0.5, xMax: Double(n) - 0.5, yMin: -540, yMax: 180,
                                xTicks: dayTicks, yTicks: stride(from: -540.0, through: 180, by: 120).map { .init(v: $0, label: clock($0)) },
                                series: [.init(name: L.bhNormalDays, kind: "range", color: "primary", pts: sleepNorm),
                                         .init(name: L.bhHotDays, kind: "range", color: "heat", pts: sleepHot)], barWidth: 0.5))
        let actHot = recs.enumerated().compactMap { i, r in hot[i] && r.minutes >= 600 ? [Double(i), r1(Double(r.activeMin) / 60)] : nil }
        let actNorm = recs.enumerated().compactMap { i, r in !hot[i] && r.minutes >= 600 ? [Double(i), r1(Double(r.activeMin) / 60)] : nil }
        let aMax = max(1, ceil((actHot + actNorm).map { $0[1] }.max() ?? 1))
        charts.append(ChartSpec(id: "activity", title: L.bhActTitle, note: nil, h: 250, xMin: -0.5, xMax: Double(n) - 0.5, yMin: 0, yMax: aMax,
                                xTicks: dayTicks, yTicks: yTicks(0, aMax, 1, " h"),
                                series: [.init(name: L.bhNormalDays, kind: "bars", color: "health", pts: actNorm),
                                         .init(name: L.bhHotDays, kind: "bars", color: "heat", pts: actHot)]))
        func avgSleep(_ hotFlag: Bool) -> Double? {
            let v = recs.enumerated().compactMap { i, r -> Double? in hot[i] == hotFlag ? HeatReportBuilder.sleepLen(r) : nil }
            return v.count >= 2 ? v.reduce(0, +) / Double(v.count) : nil
        }
        func avgAct(_ hotFlag: Bool) -> Double? {
            let v = recs.enumerated().compactMap { i, r -> Double? in hot[i] == hotFlag && r.minutes >= 600 ? Double(r.activeMin) / 60 : nil }
            return v.count >= 2 ? v.reduce(0, +) / Double(v.count) : nil
        }

        // exposure (hours at home by air band) for the day-by-day page
        charts.append(ChartSpec(id: "exposure", title: L.t("Ώρες ζέστης στο σπίτι, ανά θερμοκρασία αέρα", "Hours of heat at home, by air temperature"),
                                note: nil, h: 170, xMin: -0.5, xMax: Double(n) - 0.5, yMin: 0,
                                yMax: Double(max(4, Int(ceil((recs.map { Double($0.home[1...].reduce(0, +)) / 60 }.max() ?? 4) / 6)) * 6)),
                                xTicks: dayTicks, yTicks: [], series: [.init(name: "26–28 °C|28–30 °C|30–32 °C|≥32 °C", kind: "stack", color: "band",
                                pts: recs.enumerated().map { i, r in [Double(i)] + (1...4).map { r1(Double(r.home[$0]) / 60) } })]))
        if let i = charts.indices.last {
            let ymax = charts[i].yMax
            charts[i].yTicks = yTicks(0, ymax, ymax > 12 ? 6 : 4, " h")
        }

        // ---- optional: the Body Twin estimate (model, not measured)
        if showTwin {
            let rng = recs.enumerated().compactMap { i, r -> [Double]? in let v = r.est5.values; return v.isEmpty ? nil : [Double(i), r1(v.min()!), r1(v.max()!)] }
            let (lo, hi) = range(rng.flatMap { [$0[1], $0[2]] }, step: 0.5, pad: 0.1)
            charts.append(ChartSpec(id: "twin", title: L.bhTwinTitle, note: L.bhTwinNote, h: 200, xMin: -0.5, xMax: Double(n) - 0.5, yMin: lo, yMax: hi,
                                    xTicks: dayTicks, yTicks: yTicks(lo, hi, 0.5, "°"),
                                    series: [.init(name: L.bhTwinRange, kind: "range", color: "twin", pts: rng)], barWidth: 0.42))
        }

        // ---- 6. her heat reaction in plain words
        var summary: [HeatReport.Line] = []
        if let f = fit, let b = base.hr {
            let at30 = f.a + f.b * 4
            summary.append(.init(text: L.bhSumHeart(f.b, Int(b.rounded()), Int(at30.rounded()), f.n), conf: L.bhConf(HeatBody.confidence(f))))
        } else {
            summary.append(.init(text: L.bhSumHeartNone, conf: nil))
        }
        let hrRec = recov.compactMap { $0.1.hrMin }.map(Double.init), skRec = recov.compactMap { $0.1.skinMin }.map(Double.init)
        if let m = HeatBody.median(hrRec) {
            summary.append(.init(text: L.bhSumRecovery(Int((m / 5).rounded()) * 5, HeatBody.median(skRec).map { Int(($0 / 5).rounded()) * 5 }, recov.count,
                                                      recov.count - hrRec.count),
                                 conf: L.bhConf(HeatBody.confidence(episodes: hrRec.count))))
            if hrRec.count >= 4 {
                let h1 = Array(hrRec.prefix(hrRec.count / 2)), h2 = Array(hrRec.suffix(hrRec.count - hrRec.count / 2))
                let a = h1.reduce(0, +) / Double(h1.count), c = h2.reduce(0, +) / Double(h2.count)
                if c - a >= 10 { summary.append(.init(text: L.bhSumSlower(Int(a.rounded()), Int(c.rounded())), conf: L.bhConf(HeatBody.confidence(episodes: hrRec.count)))) }
                else if a - c >= 10 { summary.append(.init(text: L.bhSumFaster(Int(a.rounded()), Int(c.rounded())), conf: L.bhConf(HeatBody.confidence(episodes: hrRec.count)))) }
            }
        } else if !spans.isEmpty {
            summary.append(.init(text: L.bhSumRecNone, conf: nil))
        }
        let skHot = recs.enumerated().compactMap { i, r in hot[i] ? r.skinMean : nil }, skNorm = recs.enumerated().compactMap { i, r in !hot[i] ? r.skinMean : nil }
        if skHot.count >= 2 && skNorm.count >= 2 {
            let a = skNorm.reduce(0, +) / Double(skNorm.count), c = skHot.reduce(0, +) / Double(skHot.count)
            summary.append(.init(text: L.bhSumSkin(r1(c - a), r1(a), r1(c)), conf: L.bhConf(min(skHot.count, skNorm.count) >= 4 ? .high : .medium)))
        }
        if let sh = avgSleep(true), let sn = avgSleep(false), let ah = avgAct(true), let an = avgAct(false) {
            summary.append(.init(text: L.bhSumSleepAct(sh, sn, ah, an), conf: L.bhConf(.medium)))
        }

        // ---- the day-by-day table and the old key figures
        var dailyRows: [[String]] = [], dots: [String?] = [], bolds: [Bool] = []
        var totals = (hotNights: 0, home28: 0.0, out28: 0.0, checks: 0, answered: 0, alerts: 0, held: 0, family: 0, sug: 0, fol: 0)
        for (i, r) in recs.enumerated() {
            let day = dates[i]
            let es = entries.filter { cal.isDate($0.at, inSameDayAs: day) }
            let shown = es.filter { $0.kind == .nudgeShown }.count, done = es.filter { $0.kind == .nudgeDone }.count
            let checks = es.filter { $0.kind == .warnShown && $0.warnState == "CHECK" }.count
            let answered = min(checks, es.filter { $0.kind == .imOK }.count)
            let alerts = es.filter { $0.kind == .warnShown && ["DRINK", "COOL", "DANGER"].contains($0.warnState ?? "") }.count + es.filter { $0.kind == .help }.count
            let fam = familyContacts(es)
            let held = es.filter { $0.kind == .alertHeld && $0.alertHeld?.what != .check }.count
            var sug = 0, fol = 0
            let plan = BandHerDay.planItems(inp.entries, for: day, calendar: cal).items.filter { $0.kind == .outingShift }
            if !plan.isEmpty {
                let vs = BandHerDay.visits(inp.entries, on: day, calendar: cal)
                sug = plan.count
                fol = plan.filter { if case .followed = BandHerDay.outcome($0, visits: vs, day: day, now: inp.now, calendar: cal) { return true }; return false }.count
            }
            let hn = r.hotNight
            totals.hotNights += hn == true ? 1 : 0; totals.home28 += r.hoursAtOrAbove(28, home: true); totals.out28 += r.hoursAtOrAbove(28, home: false)
            totals.checks += checks; totals.answered += answered; totals.alerts += alerts; totals.held += held; totals.family += fam
            totals.sug += sug; totals.fol += fol
            dailyRows.append([fDay.string(from: day), String(format: "%.0f", Double(r.minutes) / 60), hfmt(r.hoursAtOrAbove(26, home: true)),
                              hfmt(r.hoursAtOrAbove(28, home: true)), hfmt(r.hoursAtOrAbove(28, home: false)),
                              hn == nil ? "–" : (hn! ? L.t("ναι", "yes") : L.t("όχι", "no")), r.worstState.map { L.rpStateShort($0) } ?? "–",
                              frac(done, shown), frac(answered, checks), num(alerts), num(fam), num(held), frac(fol, sug)])
            dots.append(r.worstState.map { ["health", "heatdark", "danger"][$0] })
            bolds.append(hn == true)
        }
        let s = L.rpLabels
        let daily = TableSpec(cols: [.init(label: s["c_date"]!, w: 56, align: "l"), .init(label: s["c_data"]!, w: 34, align: "r"),
                                     .init(label: s["c_home26"]!, w: 42, align: "r"), .init(label: s["c_home28"]!, w: 42, align: "r"),
                                     .init(label: s["c_out28"]!, w: 38, align: "r"), .init(label: s["c_night"]!, w: 36, align: "c"),
                                     .init(label: s["c_state"]!, w: 54, align: "l"), .init(label: s["c_nudges"]!, w: 42, align: "r"),
                                     .init(label: s["c_checks"]!, w: 42, align: "r"), .init(label: s["c_alerts"]!, w: 30, align: "r"),
                                     .init(label: s["c_family"]!, w: 30, align: "r"), .init(label: s["c_held"]!, w: 26, align: "r"),
                                     .init(label: s["c_shift"]!, w: 43, align: "r")],
                              rows: dailyRows, dotCol: 6, dots: dots, boldCol: 5, bold: bolds, note: s["daily_note"])
        var figs: [HeatReport.Figure] = []
        if let f = fit { figs.append(.init(value: String(format: L.el ? "≈ %.1f" : "≈ %.1f", f.b).replacingOccurrences(of: ".", with: L.el ? "," : "."), label: L.bhFigSlope)) }
        if let m = HeatBody.median(hrRec) { figs.append(.init(value: "\(Int((m / 5).rounded()) * 5)′", label: L.bhFigRecovery)) }
        figs.append(.init(value: "\(totals.hotNights)", label: L.rpFigHotNights(totals.hotNights)))
        figs.append(.init(value: "\(Int(totals.home28.rounded()))", label: L.rpFigHome28))
        figs.append(.init(value: "\(totals.answered)/\(totals.checks)", label: L.rpFigChecks))
        figs.append(.init(value: "\(totals.alerts)/\(totals.held)", label: L.rpFigAlerts))
        figs.append(.init(value: "\(totals.family)", label: L.rpFigFamily))
        if totals.sug > 0 { figs.append(.init(value: "\(totals.fol)/\(totals.sug)", label: L.rpFigShift)) }

        // ---- medicines + questions (last page)
        let meds: [HeatReport.Med] = inp.meds.map { m in
            let g = m.cls == nil ? MedGuess.guess(m.name) : nil
            let c = m.cls ?? g
            return HeatReport.Med(name: m.name.trimmingCharacters(in: .whitespacesAndNewlines), cls: c.map { L.rpClass($0) }, guessed: g != nil, flagged: c?.heatRisk ?? false)
        }
        var qs: [String] = []
        let fluidPlan = inp.meds.contains { [MedClass.diuretic, .sglt2].contains($0.cls ?? MedGuess.guess($0.name)) }
        let hotDates = dailyRows.enumerated().filter { recs[$0.offset].hotNight == true }.map { $0.element[0] }
        if totals.hotNights >= 2 { qs.append(L.rqHotNights(totals.hotNights, list(hotDates, L), fluidPlan: fluidPlan)) }
        if let f = fit, HeatBody.confidence(f) != .low, f.b >= 1.0 { qs.append(L.rqHeart(f.b)) }
        if let m = HeatBody.median(hrRec), m >= 45 { qs.append(L.rqRecovery(Int(m.rounded()))) }
        if let b = restMed {
            let high = recs.enumerated().filter { ($0.element.restingHR ?? 0) >= b + restHRAbove }.map { dailyRows[$0.offset][0] }
            if high.count >= 2 { qs.append(L.rqRestHR(high.count, restHRAbove, list(high, L))) }
        }
        if totals.checks > 0 && totals.answered < totals.checks { qs.append(L.rqChecks(totals.checks - totals.answered, totals.checks)) }
        let flagged = meds.filter { $0.flagged }
        if !flagged.isEmpty { qs.append(L.rqMeds(flagged.map { $0.name + ($0.cls.map { " (\($0))" } ?? "") }.joined(separator: ", "))) }
        if Int(totals.home28.rounded()) >= 20 { qs.append(L.rqHome28(Int(totals.home28.rounded()))) }
        if qs.isEmpty { qs.append(L.rqNone) }
        qs = Array(qs.prefix(maxQuestions))

        // ---- pages (blocks)
        var B: [HeatReport.Block] = []
        func ch(_ id: String) -> ChartSpec? { charts.first { $0.id == id } }
        B.append(.init(kind: "cover"))
        B.append(.init(kind: "heading", text: L.bhSummaryTitle))
        B.append(.init(kind: "summary", lines: summary))
        B.append(.init(kind: "note", text: L.bhSummaryNote))
        B.append(.init(kind: "heading", text: s["key"]))
        B.append(.init(kind: "figures", figures: figs))
        B.append(.init(kind: "break"))
        B.append(.init(kind: "heading", text: L.bhPageSkin))
        if let c = ch("skin_days") { B.append(.init(kind: "chart", chart: c)) }
        if let c = ch("rh_days") { B.append(.init(kind: "chart", chart: c)) }
        if let c = ch("skin_24h") { B.append(.init(kind: "pair", chart: c, chart2: ch("rh_24h"))) }
        B.append(.init(kind: "break"))
        B.append(.init(kind: "heading", text: L.bhPageHeart))
        if let c = ch("hr_scatter") { B.append(.init(kind: "chart", chart: c)) }
        if let c = ch("hr_rest") { B.append(.init(kind: "pair", chart: c, chart2: ch("recovery"))) }
        else if let c = ch("recovery") { B.append(.init(kind: "chart", chart: c)) }
        B.append(.init(kind: "break"))
        B.append(.init(kind: "heading", text: L.bhPageAlerts))
        if alertRows.rows.isEmpty { B.append(.init(kind: "para", text: L.bhNoAlerts)) } else { B.append(.init(kind: "table", table: alertRows)) }
        B.append(.init(kind: "break"))
        B.append(.init(kind: "heading", text: s["daily"]))
        B.append(.init(kind: "table", table: daily))
        if let c = ch("exposure") { B.append(.init(kind: "chart", chart: c)) }
        B.append(.init(kind: "break"))
        B.append(.init(kind: "heading", text: L.bhPageSleep))
        if let c = ch("sleep") { B.append(.init(kind: "pair", chart: c, chart2: ch("activity"))) }
        if let sh = avgSleep(true), let sn = avgSleep(false), let ah = avgAct(true), let an = avgAct(false) {
            B.append(.init(kind: "para", text: L.bhSumSleepAct(sh, sn, ah, an)))
        }
        if let c = ch("twin") {
            B.append(.init(kind: "twinwarn", text: L.bhTwinWarn))
            B.append(.init(kind: "chart", chart: c))
        }
        B.append(.init(kind: "break"))
        B.append(.init(kind: "heading", text: s["questions"]))
        B.append(.init(kind: "questions", items: qs))
        B.append(.init(kind: "note", text: s["questions_note"]))
        B.append(.init(kind: "heading", text: s["meds"]))
        B.append(.init(kind: "meds", meds: meds))
        B.append(.init(kind: "privacy"))

        let period = L.rpDays(inp.days) + " · " + fShort.string(from: start) + "–" + fLong.string(from: d0)
        return HeatReport(lang: L.lang.rawValue, simulated: inp.simulated, twin: showTwin, name: inp.name, days: inp.days, periodText: period,
                          generatedText: fLong.string(from: inp.now) + " " + fHM.string(from: inp.now), summary: summary, figures: figs,
                          charts: charts, alerts: alertRows, daily: daily, fit: fit, baselineHR: base.hr.map { r1($0) }, restingHR: restMed,
                          meds: meds, questions: qs, blocks: B, t: s)
    }

    /// Each COOL / DRINK / CHECK / DANGER alert: when, what the band said, the sensors at that moment (5-min means),
    /// what she did in the next 30 min, and how fast she recovered after that episode.
    static func alertTable(_ es: [LogEntry], recs: [DayRecord], start: Date, recov: [(EpisodeSpan, Recovery)], L: Strings,
                           fDay: DateFormatter, fHM: DateFormatter, cal: Calendar) -> TableSpec {
        let alerts = es.filter { $0.kind == .warnShown && ["DRINK", "COOL", "CHECK", "DANGER"].contains($0.warnState ?? "") }
        var rows: [[String]] = []
        for a in alerts.suffix(maxAlertRows) {
            let d = cal.startOfDay(for: a.at)
            let i = cal.dateComponents([.day], from: start, to: d).day ?? -1
            let slot = Int(a.at.timeIntervalSince(d) / 60) / 5
            let r = i >= 0 && i < recs.count ? recs[i] : nil
            func f1(_ v: Double?) -> String { v.map { String(format: "%.1f", $0) } ?? "–" }
            let home = r.map { $0.airHome5.n[slot] >= $0.airOut5.n[slot] } ?? true
            let air = r.flatMap { HeatBody.airSlot($0, slot) }
            let airText = air.map { f1($0) + "° " + (home ? L.t("σπίτι", "home") : L.t("έξω", "out")) } ?? "–"
            let rh = r?.rh5.mean(slot).map { "\(Int($0.rounded()))%" } ?? "–"
            let skin = r?.skin5.mean(slot).map { f1($0) + "°" } ?? "–"
            let hr = r?.hr5.mean(slot).map { "\(Int($0.rounded()))" } ?? "–"
            // what she did in the next 30 min
            let next = es.filter { $0.at > a.at && $0.at <= a.at.addingTimeInterval(1800) }
            var did: [String] = []
            if a.warnState == "CHECK" {
                if let ok = next.first(where: { $0.kind == .imOK }) { did.append(L.rpDidImOK(Int(ok.at.timeIntervalSince(a.at) / 60))) }
                else { did.append(L.bhNoAnswer) }
                if next.contains(where: { $0.kind == .familyMsgShown || $0.kind == .familyMsgSent }) { did.append(L.rpDidFamily) }
            } else {
                let dn = next.filter { $0.kind == .nudgeDone }.count
                if dn > 0 { did.append(L.bhDidReminder(dn)) }
                if next.contains(where: { $0.kind == .visit && $0.visit?.edge == .arrive && $0.visit?.place == .home }) { did.append(L.bhWentHome) }
                if did.isEmpty { did.append(L.bhStayed(home)) }
            }
            let rc = recov.first { a.at >= $0.0.start.addingTimeInterval(-120) && a.at <= ($0.0.end ?? $0.0.start).addingTimeInterval(60) }?.1
            let recText = rc.map { L.bhRecCell($0.hrMin, $0.skinMin) } ?? "–"
            rows.append([fDay.string(from: a.at) + " " + fHM.string(from: a.at), L.bhAlertWord(a.warnState ?? ""), airText, rh, skin, hr,
                         did.joined(separator: "; "), recText])
        }
        return TableSpec(cols: [.init(label: L.t("Πότε", "When"), w: 70, align: "l"), .init(label: L.t("Ειδοποίηση", "Alert"), w: 70, align: "l"),
                                .init(label: L.t("Αέρας", "Air"), w: 54, align: "r"), .init(label: L.t("Υγρασία", "Humidity"), w: 40, align: "r"),
                                .init(label: L.t("Δέρμα καρπού", "Wrist skin"), w: 40, align: "r"), .init(label: L.t("Σφυγμός", "Pulse"), w: 34, align: "r"),
                                .init(label: L.t("Τι έκανε", "What she did"), w: 125, align: "l"),
                                .init(label: L.t("Επανήλθε (σφυγμός / δέρμα)", "Recovered (pulse / skin)"), w: 82, align: "l")],
                         rows: rows, note: L.bhAlertsNote)
    }

    /// Family contacts that day: the episodes in which the band called the family (ALL_CLEAR flag), or the family's
    /// replies (sent from the family phone / shown on her band), whichever is larger — one contact is not counted twice.
    static func familyContacts(_ es: [LogEntry]) -> Int {
        let replies = max(es.filter { $0.kind == .familyMsgSent }.count, es.filter { $0.kind == .familyMsgShown }.count)
        let called = es.filter { $0.kind == .allClear && ($0.allClear?.familyCalled ?? false) }.count
        return max(replies, called)
    }

    /// Heat episodes: each ALL_CLEAR closes one (start = its time - its minutes); warnings not inside one are grouped
    /// (gaps <= 90 min) into episodes without an all-clear.
    static func episodes(_ es: [LogEntry]) -> [EpisodeSpan] {
        var spans: [EpisodeSpan] = es.compactMap { e in
            guard let c = e.allClear else { return nil }
            return EpisodeSpan(start: e.at.addingTimeInterval(-Double(c.minutes) * 60), end: e.at, clear: c)
        }
        let isWarn: (LogEntry) -> Bool = { $0.kind == .help || ($0.kind == .warnShown && ["DRINK", "COOL", "CHECK", "DANGER"].contains($0.warnState ?? "")) }
        for w in es where isWarn(w) {
            if spans.contains(where: { w.at >= $0.start.addingTimeInterval(-120) && w.at <= ($0.end ?? $0.start).addingTimeInterval(60) }) { continue }
            if let i = spans.firstIndex(where: { $0.clear == nil && w.at.timeIntervalSince($0.end ?? $0.start) <= 90 * 60 && w.at >= $0.start }) {
                spans[i].end = w.at
            } else {
                spans.append(EpisodeSpan(start: w.at, end: nil, clear: nil))
            }
        }
        return spans.sorted { $0.start < $1.start }
    }

    static func sleepLen(_ r: DayRecord) -> Double? {
        guard let s = r.sleepStart, let e = r.sleepEnd, e > s else { return nil }
        return Double(e - s)
    }
    static func hfmt(_ v: Double) -> String { v < 0.05 ? "–" : (v < 10 ? String(format: "%.1f", v) : String(format: "%.0f", v)) }
    static func num(_ v: Int) -> String { v == 0 ? "–" : "\(v)" }
    static func frac(_ a: Int, _ b: Int) -> String { b == 0 ? "–" : "\(a)/\(b)" }
    /// "Mo 10/11, Tu 11/11 and 2 more"
    static func list(_ xs: [String], _ L: Strings) -> String {
        if xs.count <= 3 { return xs.joined(separator: ", ") }
        return xs.prefix(3).joined(separator: ", ") + (L.el ? " και \(xs.count - 3) ακόμα" : " and \(xs.count - 3) more")
    }

    /// The model as JSON (the Linux sample: tools/report_mirror.py draws it with the same layout).
    static func json(_ r: HeatReport) throws -> Data {
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        return try enc.encode(r)
    }
}
