// XCTest for the doctor's report model (HeatReport.swift, ReportLedger.swift, Medications.swift): the ledger's day
// aggregates from STATUS minutes, the builder on the demo month, the claim rules (no core temperature, state words
// only, medicine wording, questions are questions, SIMULATION), and the sample JSON the Linux PDF mirror draws.
// Set HG_REPORT_JSON=/path/to/file.json to write the 14-day demo model (tools/report_mirror.py renders it).

import XCTest
@testable import HeatGuardian

final class ReportTests: XCTestCase {
    private func status(state: Int = 0, notWorn: Bool = false, home: Bool = true, hr: Int = 68, air: Double? = 27.0,
                        skin: Double? = 33.5, activity: Int = 2, core: Double = 37.1) -> StatusFrame {
        StatusFrame(version: 1, familyPending: false, notWorn: notWorn, stateCode: state, contactOK: true, timeSynced: true,
                    charging: false, home: home, ppgValid: true, coreC: core, halfRangeC: 0.3, hrBpm: hr, hrQ: 2,
                    t1C: skin, t2C: nil, tairC: air, rhPct: 40, batteryPct: 80, minuteCounter: 1, alarmId16: nil,
                    routineScore: 200, activity: activity)
    }

    func testLedgerAggregates() throws {
        let cal = Calendar.current
        let led = ReportLedger(fileName: nil)
        let d0 = cal.startOfDay(for: Date())
        let yesterday = cal.date(byAdding: .day, value: -1, to: d0)!
        // 22:30 yesterday -> 06:30 today still at home, air 27 °C (a hot night), then a hot outing
        for k in 0..<(8 * 60) { led.add(status(hr: 60 + k % 12, air: 27.0), at: yesterday.addingTimeInterval(Double(22 * 3600 + 30 * 60 + k * 60))) }
        for k in 0..<60 { led.add(status(state: 2, home: false, hr: 95, air: 33.0, activity: 40), at: d0.addingTimeInterval(Double(10 * 3600 + k * 60))) }
        for k in 0..<30 { led.add(status(notWorn: true, air: 25.0), at: d0.addingTimeInterval(Double(12 * 3600 + k * 60))) }
        led.add(status(activity: 50), at: d0.addingTimeInterval(13 * 3600))
        led.closeRun()
        let r = try XCTUnwrap(led.records(last: 1, today: d0).first)
        XCTAssertEqual(r.minutes, 390 + 60 + 30 + 1)
        XCTAssertEqual(r.worn, 390 + 60 + 1)
        XCTAssertEqual(r.nightMin, 360); XCTAssertEqual(r.nightWarm, 360)
        XCTAssertEqual(r.hotNight, true)
        XCTAssertEqual(r.hoursAtOrAbove(28, home: false), 1.0)
        XCTAssertEqual(r.out[4], 60)                               // >= 32 °C
        XCTAssertEqual(r.worstState, 1)                            // COOL -> «Ζεστή μέρα»
        XCTAssertEqual(r.activeMin, 60 + 1)
        XCTAssertEqual(r.restingHR, 61)                            // 10th percentile of 60…71 while still
        XCTAssertEqual(r.sleepStart, -90)                          // 22:30 the evening before
        XCTAssertEqual(r.sleepEnd, 6 * 60 + 29)
        // the core estimate is kept apart (est5) and never under a "core" name
        let json = String(decoding: try JSONEncoder().encode(r), as: UTF8.self)
        XCTAssertFalse(json.lowercased().contains("core"))      // the estimate is only in est5
        XCTAssertFalse(r.est5.isEmpty)
        XCTAssertEqual(led.records(last: 3, today: d0).count, 3)
    }

    private func demoReport(_ lang: Lang, days: Int = 14, meds: [Medication] = HeatReportDemo.meds) -> HeatReport {
        let now = Calendar.current.startOfDay(for: Date()).addingTimeInterval(13 * 3600)
        let inp = ReportInput(records: HeatReportDemo.records(days: days, today: now), entries: HeatReportDemo.entries(today: now),
                              meds: meds, name: "Μαρία Π.", days: days, now: now, simulated: true)
        return HeatReportBuilder.build(inp, L: Strings(lang: lang))
    }

    func testDemoReport() throws {
        let r = demoReport(.en)
        XCTAssertEqual(r.daily.rows.count, 14)
        XCTAssertTrue(r.simulated)
        XCTAssertFalse(r.twin)
        XCTAssertEqual(r.daily.rows.filter { $0[5] == "yes" }.count, 6)                    // hot nights
        // the health track: every chart is there, built from data
        for id in ["skin_days", "rh_days", "skin_24h", "rh_24h", "hr_scatter", "hr_rest", "recovery", "sleep", "activity", "exposure"] {
            let c = try XCTUnwrap(r.chart(id), id)
            XCTAssertFalse(c.series.allSatisfy { $0.pts.isEmpty }, id)
        }
        XCTAssertNil(r.chart("twin"))
        XCTAssertTrue(r.chart("skin_days")!.title.contains("Wrist skin temperature"))
        // heart response: the demo adds +1.6 bpm per °C above 26 °C on top of a resting pulse that is itself higher on
        // the heat-wave days, so the fitted slope must be at least 1.6 and plausible (episodes and walking are left out)
        let f = try XCTUnwrap(r.fit)
        XCTAssertTrue(f.b >= 1.6 && f.b <= 5.5, "slope \(f.b)")
        XCTAssertNotEqual(HeatBody.confidence(f), .low)
        XCTAssertTrue(r.summary[0].text.contains("bpm for each °C of air above 26 °C"), r.summary[0].text)
        XCTAssertNotNil(r.summary[0].conf)
        // recovery: every demo episode in the period has one, slower on hotter days
        XCTAssertTrue(r.summary.contains { $0.text.contains("she recovers in about") })
        let rec = try XCTUnwrap(r.chart("recovery")).series[0].pts
        XCTAssertEqual(rec.count, 5)
        XCTAssertTrue(rec.allSatisfy { $0[1] > 0 && $0[1] < 360 })
        // the alerts table: sensors + what she did + recovery
        XCTAssertTrue(r.alerts.rows.count >= 8)
        XCTAssertTrue(r.alerts.rows.contains { $0[1] == "\"Are you OK?\"" && $0[6].contains("answered") })
        XCTAssertTrue(r.alerts.rows.allSatisfy { $0[4].hasSuffix("°") && $0[7].contains("/") })
        // Her Day outings followed / suggested
        XCTAssertEqual(r.daily.rows.map { $0[12] }.filter { $0 != "–" }, ["1/1", "1/1", "0/1", "1/1", "1/1", "1/1"])
        // medicines: chosen class flagged, guessed class flagged and marked, "other" not flagged
        XCTAssertEqual(r.meds.map { $0.flagged }, [true, true, false])
        XCTAssertEqual(r.meds[1].cls, "beta-blocker"); XCTAssertTrue(r.meds[1].guessed)
        XCTAssertEqual(r.t["meds_flag"], "ask your doctor whether this matters in heat")
        // questions: last page, questions only, the diuretic switches the drinking question to the doctor's plan
        XCTAssertEqual(r.blocks.last(where: { $0.kind == "questions" })?.items, r.questions)
        let qi = r.blocks.firstIndex { $0.kind == "questions" }!, ci = r.blocks.firstIndex { $0.kind == "chart" }!
        XCTAssertTrue(qi > ci)
        XCTAssertTrue(r.questions.count <= HeatReportBuilder.maxQuestions)
        for q in r.questions { XCTAssertTrue(q.hasSuffix("?"), q) }
        XCTAssertTrue(r.questions[0].contains("how much should she drink"), r.questions[0])
        XCTAssertEqual(r.t["disclaimer_el"], "Δημιουργήθηκε από το Heat Guardian. Δεν είναι ιατρική συσκευή. Δεν είναι διάγνωση.")
        XCTAssertEqual(r.t["disclaimer_en"], "Generated by Heat Guardian. Not a medical device. Not a diagnosis.")
        XCTAssertEqual(r.blocks.filter { $0.kind == "break" }.count, 6)                     // 7 pages
    }

    /// The Body Twin estimate only behind the switch, and then labelled.
    func testTwinSwitch() throws {
        XCTAssertFalse(HeatReportBuilder.SHOW_TWIN_ESTIMATE)
        let now = Calendar.current.startOfDay(for: Date()).addingTimeInterval(13 * 3600)
        let inp = ReportInput(records: HeatReportDemo.records(days: 14, today: now), entries: HeatReportDemo.entries(today: now),
                              meds: [], name: nil, days: 14, now: now, simulated: true)
        let on = HeatReportBuilder.build(inp, L: Strings(lang: .en), showTwin: true)
        let c = try XCTUnwrap(on.chart("twin"))
        XCTAssertTrue(c.title.contains("MODEL ESTIMATE") && c.title.contains("not measured"))
        XCTAssertTrue(on.blocks.contains { $0.kind == "twinwarn" })
        XCTAssertFalse(c.series[0].pts.isEmpty)
    }

    /// Claim rules: no body / core temperature number (twin off), skin always "wrist skin", strain only as band words.
    func testClaimRules() throws {
        let re = try NSRegularExpression(pattern: "(core|body temp|πυρήνα|θερμοκρασία σώματος)[^.;\\n]{0,25}[0-9]", options: [.caseInsensitive])
        for lang in Lang.allCases {
            let r = demoReport(lang, days: 30)
            XCTAssertNil(r.chart("twin"))
            let text = String(decoding: try HeatReportBuilder.json(r), as: UTF8.self)
            XCTAssertEqual(re.numberOfMatches(in: text, range: NSRange(text.startIndex..., in: text)), 0, "\(lang)")
            for banned in ["dehydrat", "αφυδατ", "you are safe", "είστε ασφαλ", "stop taking", "διακόψτε", "medical grade", "diagnosed", "\"est5\""] {
                XCTAssertFalse(text.lowercased().contains(banned.lowercased()), "\(lang) contains \(banned)")
            }
            // every skin series / chart says "wrist"
            for c in r.charts where c.id.hasPrefix("skin") {
                XCTAssertTrue(c.title.lowercased().contains(lang == .en ? "wrist skin" : "δέρμα") || c.series.contains { $0.name.contains(lang == .en ? "wrist skin" : "δέρμα") }, c.id)
            }
            let words = Set(r.daily.rows.map { $0[6] }).subtracting(["–"])
            XCTAssertTrue(words.isSubset(of: Set((0...2).map { Strings(lang: lang).rpStateShort($0) })), "\(words)")
            for q in r.questions { XCTAssertTrue(q.hasSuffix("?") || q.hasSuffix(";"), q) }   // Greek question mark is ';'
        }
        let none = demoReport(.en, meds: [])
        XCTAssertTrue(none.meds.isEmpty)
        XCTAssertFalse(none.questions.contains { $0.contains("She takes") })
        XCTAssertTrue(none.questions[0].contains("Was she drinking enough?"))
    }

    /// The analysis on hand-made data: a known slope and a known recovery.
    func testHeatBodyAnalysis() {
        var pts: [(air: Double, hr: Double, day: Int)] = []
        for k in 0..<100 { let a = 22 + Double(k) * 0.14; pts.append((a, 70 + 2.0 * max(0, a - 26) + Double(k % 3) - 1, 0)) }
        let f = HeatBody.fit(pts)!
        XCTAssertEqual(f.b, 2.0, accuracy: 0.1)
        XCTAssertEqual(f.a, 70, accuracy: 0.6)
        XCTAssertEqual(HeatBody.confidence(f), .high)
        XCTAssertNil(HeatBody.fit(Array(pts.prefix(10))))
        // recovery: pulse 100 at slot 170, back to <= 75 + 5 at slot 182 (60 min later)
        var r = DayRecord(day: "x")
        for s in 160..<230 { r.airHome5.add(s, 28) }
        for s in 160..<230 { r.hr5.add(s, s <= 170 ? 75 + Double(s - 160) * 2.5 : max(75, 100 - Double(s - 170) * 25 / 12)) }
        for s in 160..<230 { r.skin5.add(s, 33.0) }
        let rc = HeatBody.recovery(r, at: Date(), from: 160 * 5, to: 175 * 5, hrExpect: { _ in 75 }, skinExpect: { _ in 33.0 })
        XCTAssertEqual(rc.peakHR, 100)
        XCTAssertEqual(rc.hrMin, 50)                       // 100 - 25/12·k <= 80 first at k = 10 (two slots in a row)
        XCTAssertEqual(rc.skinMin, 0)                      // never above baseline + 0.3
        let none = HeatBody.recovery(r, at: Date(), from: 160 * 5, to: 175 * 5, hrExpect: { _ in 60 }, skinExpect: { _ in 30 })
        XCTAssertNil(none.hrMin)
    }

    func testMedGuess() {
        XCTAssertEqual(MedGuess.guess("Lasix 40"), .diuretic)
        XCTAssertEqual(MedGuess.guess("ΦΟΥΡΟΣΕΜΙΔΗ"), .diuretic)
        XCTAssertEqual(MedGuess.guess("Jardiance 10mg"), .sglt2)
        XCTAssertEqual(MedGuess.guess("Κουετιαπίνη 25"), .antipsychotic)
        XCTAssertNil(MedGuess.guess("Atorvastatin"))
        XCTAssertFalse(MedClass.other.heatRisk)
        XCTAssertTrue(MedClass.allCases.filter { $0.heatRisk }.count == 5)
    }

    /// Writes the sample model for tools/report_mirror.py when HG_REPORT_JSON is set.
    func testWriteSampleJSON() throws {
        let r = demoReport(.en)
        let d = try HeatReportBuilder.json(r)
        XCTAssertNoThrow(try JSONDecoder().decode(HeatReport.self, from: d))
        if let p = ProcessInfo.processInfo.environment["HG_REPORT_JSON"] {
            try d.write(to: URL(fileURLWithPath: p))
            try HeatReportBuilder.json(demoReport(.el)).write(to: URL(fileURLWithPath: p.replacingOccurrences(of: ".json", with: "_el.json")))
            // Foivos's switch on (SHOW_TWIN_ESTIMATE): the same report with the labelled Body Twin section
            let now = Calendar.current.startOfDay(for: Date()).addingTimeInterval(13 * 3600)
            let inp = ReportInput(records: HeatReportDemo.records(days: 14, today: now), entries: HeatReportDemo.entries(today: now),
                                  meds: HeatReportDemo.meds, name: "Μαρία Π.", days: 14, now: now, simulated: true)
            try HeatReportBuilder.json(HeatReportBuilder.build(inp, L: Strings(lang: .en), showTwin: true))
                .write(to: URL(fileURLWithPath: p.replacingOccurrences(of: ".json", with: "_twin.json")))
        }
    }

    /// The data-loss fix: the ledger is written while the phone is LOCKED (band frames wake the app), so its file uses
    /// "complete until first user authentication" (as tower.json), and a file it could not read is never overwritten.
    func testLedgerFileProtectionAndNoOverwriteWhenUnreadable() throws {
        let p = ReportLedger.writeOptions
        XCTAssertTrue(p.contains(.atomic))
        XCTAssertEqual(p.rawValue & ~Data.WritingOptions.atomic.rawValue,
                       Data.WritingOptions.completeFileProtectionUntilFirstUserAuthentication.rawValue)
        XCTAssertNotEqual(p.rawValue & ~Data.WritingOptions.atomic.rawValue, Data.WritingOptions.completeFileProtection.rawValue)

        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("hg-ledger-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: dir) }
        let url = dir.appendingPathComponent("report_days.json")
        let cal = Calendar.current
        let d0 = cal.startOfDay(for: Date())
        let a = ReportLedger(url: url)
        for k in 0..<30 { a.add(status(), at: d0.addingTimeInterval(Double(-86400 + 9 * 3600 + k * 60))) }   // yesterday
        a.save()
        XCTAssertTrue(FileManager.default.fileExists(atPath: url.path))

        // launched while locked: the file is there but cannot be read
        var locked = true
        let b = ReportLedger(url: url, read: { u in if locked { throw CocoaError(.fileReadNoPermission) }; return try Data(contentsOf: u) })
        XCTAssertTrue(b.pendingReload)
        for k in 0..<5 { b.add(status(), at: d0.addingTimeInterval(Double(9 * 3600 + k * 60))) }              // today
        b.save()                                                    // still locked: nothing written over yesterday
        XCTAssertEqual(ReportLedger(url: url).records(last: 2, today: d0).map { $0.minutes }, [30, 0])
        locked = false
        b.save()                                                    // unlocked: reads, merges, then writes both days
        XCTAssertFalse(b.pendingReload)
        XCTAssertEqual(ReportLedger(url: url).records(last: 2, today: d0).map { $0.minutes }, [30, 5])
    }
}
