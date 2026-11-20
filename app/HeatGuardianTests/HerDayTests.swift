// XCTest for Her Day (HERDAY_SPEC.md): DAY_PLAN / VISIT frames, EVENTS types 9 / 10, the engine, the routine model,
// the home rule, the POI mapping, the band-plan rebuild and the demo — on herday_vectors_app.json, the same file
// ios/tools/mirror_frames.py checks in Python. ios/tools/linux_xctest/run.sh runs this file on Linux.

import XCTest
@testable import HeatGuardian

final class HerDayTests: XCTestCase {
    private func vectors() throws -> [String: Any] {
        let url = try XCTUnwrap(Bundle(for: HerDayTests.self).url(forResource: "herday_vectors_app", withExtension: "json"))
        return try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
    }
    private func int(_ v: Any?) -> Int? { (v as? NSNumber)?.intValue }

    /// JSON item -> DayPlanItem (nil when the kind / place cannot exist in Swift's types).
    private func item(_ j: [String: Any]) -> DayPlanItem? {
        guard let k = DayPlanKind(rawValue: int(j["kind"]) ?? -1), let p = PlaceType(rawValue: int(j["place"]) ?? -1) else { return nil }
        return DayPlanItem(day: int(j["day"]) ?? 0, kind: k, place: p, usual: int(j["usual"]), suggested: int(j["suggested"]),
                           direction: int(j["direction"]).flatMap(ShiftDirection.init(rawValue:)),
                           hotFrom: int(j["hot_from"]) ?? 0, hotTo: int(j["hot_to"]) ?? 0, peakC: int(j["peak_c"]),
                           heatwaveDay: int(j["heatwave_day"]) ?? 0)
    }

    private func plan(_ j: [String: Any]) throws -> Plan {
        try Plan.load(from: JSONSerialization.data(withJSONObject: j))
    }

    func testDayPlanFrames() throws {
        let v = try vectors()
        for e in try XCTUnwrap(v["day_plan"] as? [[String: Any]]) {
            let it = try XCTUnwrap(item(try XCTUnwrap(e["item"] as? [String: Any])))
            XCTAssertEqual(Frames.toHex(try Frames.cmdDayPlan(it, index: int(e["index"])!, of: int(e["n"])!)), e["hex"] as? String)
        }
        for e in try XCTUnwrap(v["day_plan_clear"] as? [[String: Any]]) {
            XCTAssertEqual(Frames.toHex(Frames.cmdDayPlanClear(day: int(e["day"])!)), e["hex"] as? String)
        }
        for e in try XCTUnwrap(v["day_plan_bad"] as? [[String: Any]]) where (e["swift"] as? Bool) == true {
            let it = try XCTUnwrap(item(try XCTUnwrap(e["item"] as? [String: Any])))
            XCTAssertThrowsError(try Frames.cmdDayPlan(it, index: int(e["index"])!, of: int(e["n"])!), e["why"] as? String ?? "")
        }
        for e in try XCTUnwrap(v["visit"] as? [[String: Any]]) {
            let f = Frames.cmdVisit(VisitEdge(rawValue: int(e["edge"])!)!, place: PlaceType(rawValue: int(e["place"])!)!,
                                    unix: UInt32((e["unix"] as! NSNumber).int64Value))
            XCTAssertEqual(Frames.toHex(f), e["hex"] as? String)
            XCTAssertEqual(f.count, 20)
        }
        XCTAssertEqual(try Frames.dayPlanFrames([], day: 1).map(Frames.toHex), [Frames.toHex(Frames.cmdDayPlanClear(day: 1))])
    }

    func testEvents() throws {
        let v = try vectors()
        for e in try XCTUnwrap(v["events_visit"] as? [[String: Any]]) {
            let hex = try XCTUnwrap(e["hex"] as? String)
            let ev = try Frames.decodeEvent(try XCTUnwrap(Frames.fromHex(hex)))
            XCTAssertEqual(ev.kind, .visit)
            let vis = try XCTUnwrap(ev.visit)
            XCTAssertEqual(vis.edge.rawValue, int(e["edge"]))
            XCTAssertEqual(vis.place.rawValue, int(e["place"]))
            XCTAssertEqual(Int64(vis.unix), (e["visit_unix"] as! NSNumber).int64Value)
            XCTAssertEqual(Frames.toHex(Frames.encodeEvent(ev)), hex)
            let built = Frames.visitEvent(seq: int(e["seq"])!, boot: int(e["boot"])!, unix: UInt32((e["unix"] as! NSNumber).int64Value), vis)
            XCTAssertEqual(Frames.toHex(Frames.encodeEvent(built)), hex)
            XCTAssertNil(ev.planItem)
        }
        for e in try XCTUnwrap(v["events_plan_item"] as? [[String: Any]]) {
            let hex = try XCTUnwrap(e["hex"] as? String)
            let ev = try Frames.decodeEvent(try XCTUnwrap(Frames.fromHex(hex)))
            var want = try XCTUnwrap(item(try XCTUnwrap(e["item"] as? [String: Any])))
            want.peakC = nil
            XCTAssertEqual(ev.planItem, want, hex)
            let built = Frames.planItemEvent(seq: int(e["seq"])!, boot: int(e["boot"])!, unix: UInt32((e["unix"] as! NSNumber).int64Value), want)
            XCTAssertEqual(Frames.toHex(Frames.encodeEvent(built)), hex)
        }
    }

    func testEngine() throws {
        let v = try vectors()
        for c in try XCTUnwrap(v["engine"] as? [[String: Any]]) {
            let name = c["name"] as? String ?? ""
            let p = try plan(try XCTUnwrap(c["plan"] as? [String: Any]))
            let outs = try XCTUnwrap(c["outings"] as? [[String: Any]]).map {
                Outing(place: PlaceType(rawValue: int($0["place"])!)!, start: int($0["start"])!, duration: int($0["duration"])!, daily: true, count: 2)
            }
            let day = int(c["day"])!
            let r = HerDay.compute(plan: p, outings: outs, bed: int(c["bed"])!, day: day)
            let x = try XCTUnwrap(c["expect"] as? [String: Any])
            XCTAssertEqual(r.hot.map { [$0.from, $0.to] }, (x["hot"] as? [[Int]]) ?? [], name)
            XCTAssertEqual(r.airOpen, int(x["air_open"]), name)
            XCTAssertEqual(r.heatwaveDay, int(x["heatwave_day"]), name)
            let xc = try XCTUnwrap(x["collisions"] as? [[String: Any]])
            XCTAssertEqual(r.collisions.count, xc.count, name)
            for (a, b) in zip(r.collisions, xc) {
                XCTAssertEqual(a.outing.place.rawValue, int(b["place"]), name)
                XCTAssertEqual(a.suggested, int(b["suggested"]), name)
                XCTAssertEqual(a.direction?.rawValue, int(b["direction"]), name)
                XCTAssertEqual(a.peakC, int(b["peak_c"]), name)
            }
            let xi = try XCTUnwrap(x["items"] as? [[String: Any]]).compactMap(item)
            XCTAssertEqual(r.items, xi, name)
            XCTAssertEqual(try Frames.dayPlanFrames(r.items, day: day).map(Frames.toHex), x["frames_hex"] as? [String], name)
            XCTAssertEqual(HerDay.briefSentence(r.items, tomorrow: day == 1), x["brief"] as? String, name)
        }
    }

    func testRoutineModel() throws {
        let v = try vectors()
        for c in try XCTUnwrap(v["routine"] as? [[String: Any]]) {
            let ss = try XCTUnwrap(c["samples"] as? [[String: Any]]).map {
                RoutineSample(place: PlaceType(rawValue: int($0["place"])!)!, weekday: int($0["weekday"])!, start: int($0["start"])!, duration: int($0["duration"]))
            }
            let got = RoutineModel.outings(ss, weekday: int(c["weekday"])!)
            let want = try XCTUnwrap(c["expect"] as? [[String: Any]]).map {
                Outing(place: PlaceType(rawValue: int($0["place"])!)!, start: int($0["start"])!, duration: int($0["duration"])!,
                       daily: ($0["daily"] as? Bool) ?? false, count: int($0["count"])!)
            }
            XCTAssertEqual(got, want, c["name"] as? String ?? "")
        }
    }

    func testHomeRuleAndMapping() {
        let cal = Calendar.current
        let now = cal.startOfDay(for: Date()).addingTimeInterval(12 * 3600)
        var stays: [HomeRule.Stay] = []
        for d in 1...5 {
            let night = cal.startOfDay(for: now).addingTimeInterval(Double(-d) * 86400)
            stays.append(HomeRule.Stay(placeID: "home", arrive: night.addingTimeInterval(-2 * 3600), leave: night.addingTimeInterval(8 * 3600)))
            stays.append(HomeRule.Stay(placeID: "market", arrive: night.addingTimeInterval(10 * 3600), leave: night.addingTimeInterval(11 * 3600)))
        }
        XCTAssertEqual(HomeRule.detect(stays, now: now), "home")
        XCTAssertEqual(HomeRule.overnightMinutes(now.addingTimeInterval(-14 * 3600), now.addingTimeInterval(-4 * 3600)), 360)
        XCTAssertNil(HomeRule.detect([HomeRule.Stay(placeID: "x", arrive: now.addingTimeInterval(-3600), leave: now)], now: now))
        XCTAssertEqual(PlaceMapping.type(category: "foodMarket", name: nil), .market)
        XCTAssertEqual(PlaceMapping.type(category: "bakery", name: nil), .market)
        XCTAssertEqual(PlaceMapping.type(category: "cafe", name: nil), .cafe)
        XCTAssertEqual(PlaceMapping.type(category: "nationalPark", name: nil), .walk)
        XCTAssertEqual(PlaceMapping.type(category: "hospital", name: nil), .doctor)
        XCTAssertEqual(PlaceMapping.type(category: nil, name: "Ιερός Ναός Αγίου Νικολάου"), .church)
        XCTAssertEqual(PlaceMapping.type(category: nil, name: "ΦΑΡΜΑΚΕΙΟ Παπαδοπούλου"), .pharmacy)
        XCTAssertEqual(PlaceMapping.type(category: nil, name: "Λαϊκή Αγορά Παγκρατίου"), .market)
        XCTAssertEqual(PlaceMapping.type(category: "store", name: "Παναγία"), .market)
        XCTAssertEqual(PlaceMapping.type(category: nil, name: "Unknown spot"), .other)
    }

    func testVisitStoreQueueAndHome() {
        let s = VisitStore(fileName: nil)
        let t0 = Date(timeIntervalSince1970: 1_789_460_000)
        let (p, isNew) = s.record(lat: 37.9715, lon: 23.7257, arrive: t0, leave: nil, now: t0)
        XCTAssertTrue(isNew)
        let (p2, isNew2) = s.record(lat: 37.9716, lon: 23.7258, arrive: t0, leave: t0.addingTimeInterval(1800), now: t0)
        XCTAssertFalse(isNew2)
        XCTAssertEqual(p.id, p2.id)
        XCTAssertEqual(s.visits.count, 1)
        XCTAssertEqual(s.pending.map { $0.edge }, [.arrive, .leave])
        s.setType(p.id, .market, name: "Λαϊκή", byUser: false)
        s.setHome(lat: 37.9800, lon: 23.7300)                       // home set by hand (else the overnight rule decides)
        XCTAssertEqual(s.places.count, 2)
        let fr = s.pendingFrames(now: t0)
        XCTAssertEqual(fr.map { Frames.toHex($0.1) }, [Frames.toHex(Frames.cmdVisit(.arrive, place: .market, unix: 1_789_460_000)),
                                                      Frames.toHex(Frames.cmdVisit(.leave, place: .market, unix: 1_789_461_800))])
        s.markSent(fr.map { $0.0 })
        XCTAssertTrue(s.pending.isEmpty)
        XCTAssertEqual(s.samples(now: t0).map { $0.place }, [.market])
        s.setType(p.id, .cafe, byUser: false)
        XCTAssertEqual(s.places.first { $0.id == p.id }?.type, .cafe)
        s.setType(p.id, .pharmacy, byUser: true)
        s.setType(p.id, .cafe, byUser: false)                       // a lookup never overrides the family's choice
        XCTAssertEqual(s.places.first { $0.id == p.id }?.type, .pharmacy)
        XCTAssertGreaterThan(VisitStore.distance(37.9715, 23.7257, 37.9800, 23.7300), 120)
    }

    func testBandPlanRebuild() throws {
        let cal = Calendar.current
        let today = cal.startOfDay(for: Date())
        let evening = today.addingTimeInterval(-3 * 3600)              // yesterday 21:00
        let a = DayPlanItem(day: 1, kind: .outingShift, place: .market, usual: 620, suggested: 570, direction: .before, hotFrom: 10, hotTo: 21)
        let b = DayPlanItem(day: 1, kind: .heatwaveDay, heatwaveDay: 2)
        var entries: [LogEntry] = []
        for (i, it) in [a, b].enumerated() {
            let ev = Frames.planItemEvent(seq: 10 + i, boot: 1, unix: UInt32(evening.timeIntervalSince1970), it)
            entries.append(try XCTUnwrap(LogEntry.fromBand(try Frames.decodeEvent(Frames.encodeEvent(ev)), receivedAt: evening)))
        }
        let got = BandHerDay.planItems(entries, for: today.addingTimeInterval(9 * 3600))
        XCTAssertEqual(got.items.count, 2)
        XCTAssertEqual(got.items.first?.suggested, 570)
        XCTAssertTrue(BandHerDay.planItems(entries, for: evening).items.isEmpty)
        // VISIT: she went at 09:12 -> followed
        let arrive = today.addingTimeInterval(9 * 3600 + 12 * 60)
        let vev = Frames.visitEvent(seq: 20, boot: 1, unix: UInt32(arrive.timeIntervalSince1970),
                                    VisitEvent(edge: .arrive, place: .market, unix: UInt32(arrive.timeIntervalSince1970)))
        entries.append(try XCTUnwrap(LogEntry.fromBand(try Frames.decodeEvent(Frames.encodeEvent(vev)), receivedAt: arrive)))
        let vs = BandHerDay.visits(entries, on: today)
        XCTAssertEqual(vs.count, 1)
        XCTAssertEqual(BandHerDay.outcome(a, visits: vs, day: today, now: arrive), .followed(arrive))
        XCTAssertEqual(BandHerDay.samples(entries).count, 1)
        // the timeline never shows them as log rows
        XCTAssertTrue(Timeline.items(entries, day: today).isEmpty)
        // ... and they alone do not make a History day
        let st = EventStore(fileName: nil)
        for e in entries { st.add(e) }
        XCTAssertTrue(st.days.isEmpty)
    }

    func testDemo() {
        let today = Date()
        let past = HerDayDemo.pastVisits(today: today)
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: today)!
        let outs = RoutineModel.outings(past, on: tomorrow, now: today)
        XCTAssertTrue(outs.contains { $0.place == .market && $0.daily })
        XCTAssertTrue(outs.contains { $0.place == .cafe })
        let r = HerDay.compute(plan: HerDayDemo.plan(date: tomorrow, waveDay: 2), outings: outs, bed: HerDayDemo.bed, day: 1)
        XCTAssertEqual(r.hot, [HotWindow(from: 10, to: 21)])
        XCTAssertEqual(HerDay.briefSentence(r.items, tomorrow: true), "Αύριο: αγορά πριν τις 09:30")
        XCTAssertTrue(r.collisions.contains { $0.outing.place == .cafe })
        XCTAssertFalse(r.collisions.contains { $0.outing.place == .walk })
        // church is on tomorrow's weekday (any day the demo runs), 08:30-09:45: before the 10:00 heat, no collision
        XCTAssertTrue(outs.contains { $0.place == .church && !$0.daily })
        XCTAssertFalse(r.collisions.contains { $0.outing.place == .church })
        XCTAssertTrue(r.collisions.allSatisfy { $0.direction == .before })
    }

    /// Demo «hotter tomorrow» (heat-wave day 3, hot 08:00-19:00): both directions on one screen (Foivos, Nov 18).
    func testDemoGoAfter() {
        let today = Date()
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: today)!
        let outs = RoutineModel.outings(HerDayDemo.pastVisits(today: today), on: tomorrow, now: today)
        let r = HerDay.compute(plan: HerDayDemo.plan(date: tomorrow, waveDay: 3), outings: outs, bed: HerDayDemo.bed, day: 1)
        XCTAssertEqual(r.hot, [HotWindow(from: 8, to: 19)])
        let church = r.collisions.first { $0.outing.place == .church }
        XCTAssertEqual(church?.direction, .after)
        XCTAssertEqual(church?.suggested, 19 * 60 + 30)
        XCTAssertEqual(r.collisions.first { $0.outing.place == .market }?.direction, .before)
        XCTAssertEqual(HerDay.briefSentence(r.items, tomorrow: true), "Αύριο: εκκλησία μετά τις 19:30")
        XCTAssertEqual(Strings(lang: .en).hdCard(r.items, tomorrow: true), "Tomorrow: church after 19:30")
    }

    /// Overlap rule (Foivos, Nov 18): any part of [start, start + duration) inside a hot window collides.
    func testOverlapRule() {
        let w = HotWindow(from: 10, to: 21)
        XCTAssertTrue(w.overlaps(start: 9 * 60 + 40, duration: 30))      // 09:40-10:10 reaches into 10:00
        XCTAssertFalse(w.overlaps(start: 9 * 60 + 30, duration: 30))     // 09:30-10:00 ends as it starts
        XCTAssertTrue(w.overlaps(start: 20 * 60 + 50, duration: 30))     // starts in its last hour
        XCTAssertFalse(w.overlaps(start: 21 * 60, duration: 40))         // starts at its end
        XCTAssertTrue(w.overlaps(start: 8 * 60, duration: 12 * 60))      // spans it
        XCTAssertTrue(w.overlaps(start: 10 * 60, duration: 0))           // no length = one minute
        var hot = [Bool](repeating: false, count: 24)
        for h in 10..<21 { hot[h] = true }
        let o = Outing(place: .market, start: 9 * 60 + 40, duration: 30, daily: true, count: 5)
        let p = HerDayDemo.plan(date: Date(), waveDay: 2)
        let r = HerDay.compute(plan: p, outings: [o], bed: 23 * 60, day: 1)
        XCTAssertEqual(r.collisions.first?.suggested, 9 * 60 + 30)
        XCTAssertEqual(HerDay.briefSentence(r.items, tomorrow: true), "Αύριο: αγορά πριν τις 09:30")
    }

    /// The demo pipeline as the family phone sees it: two weeks of VISIT events, today's scripted visits up to 13:00,
    /// tomorrow's plan echoed by the band at 20:00 -> the Today status line, "followed", and Tomorrow's collisions.
    func testDisplayFromBandEvents() throws {
        let cal = Calendar.current
        let d0 = cal.startOfDay(for: Date())
        var seq = 0
        var entries: [LogEntry] = []
        func add(_ ev: BandEvent, _ at: Date) throws {
            entries.append(try XCTUnwrap(LogEntry.fromBand(try Frames.decodeEvent(Frames.encodeEvent(ev)), receivedAt: at, simulated: true)))
        }
        func visit(_ e: VisitEdge, _ p: PlaceType, _ t: Date) throws {
            seq += 1
            let u = UInt32(t.timeIntervalSince1970)
            try add(Frames.visitEvent(seq: seq, boot: 0, unix: u, VisitEvent(edge: e, place: p, unix: u)), t)
        }
        for v in HerDayDemo.pastVisits(today: d0) {
            try visit(.arrive, v.place, v.arrive)
            if let l = v.leave { try visit(.leave, v.place, l) }
        }
        // today 13:00: café 09:35-10:20 (the suggestion was "before 10:00"), market 10:40-11:20, home 11:28
        try visit(.arrive, .cafe, d0.addingTimeInterval(575 * 60)); try visit(.leave, .cafe, d0.addingTimeInterval(620 * 60))
        try visit(.arrive, .market, d0.addingTimeInterval(640 * 60)); try visit(.leave, .market, d0.addingTimeInterval(680 * 60))
        try visit(.arrive, .home, d0.addingTimeInterval(688 * 60))
        let samples = BandHerDay.samples(entries)
        let now = d0.addingTimeInterval(13 * 3600)
        let L = Strings(lang: .en)

        // today: the plan the band got after midnight (echo at 00:05)
        let p0 = HerDayDemo.plan(date: d0, waveDay: 1)
        let r0 = HerDay.compute(plan: p0, outings: RoutineModel.outings(samples, on: d0, now: now), bed: HerDayDemo.bed, day: 0)
        XCTAssertEqual(r0.items.first { $0.kind == .outingShift }?.place, .cafe)
        for it in r0.items { seq += 1; try add(Frames.planItemEvent(seq: seq, boot: 0, unix: UInt32(d0.timeIntervalSince1970 + 300), it), d0.addingTimeInterval(300)) }
        let today = try XCTUnwrap(HerDayDisplay.make(L: L, offset: 0, now: now, plan: p0, local: r0, entries: entries, simulated: true))
        XCTAssertEqual(today.status, "Home since 11:28")
        let cafe = try XCTUnwrap(today.rows.first { $0.title == "Café" })
        XCTAssertEqual(cafe.kind, .collision)
        XCTAssertEqual(cafe.suggestion, "Band suggests: before 10:00")
        XCTAssertEqual(cafe.outcome, "Went 09:35 ✓ followed")
        XCTAssertTrue(today.onBand)

        // tomorrow at 13:00: collisions known, suggestions not on the band yet
        let d1 = cal.date(byAdding: .day, value: 1, to: d0)!
        let p1 = HerDayDemo.plan(date: d1, waveDay: 2)
        let r1 = HerDay.compute(plan: p1, outings: RoutineModel.outings(samples, on: d1, now: now), bed: HerDayDemo.bed, day: 1)
        let t13 = try XCTUnwrap(HerDayDisplay.make(L: L, offset: 1, now: now, plan: p1, local: r1, entries: entries, simulated: true))
        XCTAssertEqual(t13.bandLine, L.hdGoesEvening)
        XCTAssertEqual(t13.rows.first { $0.title == "Market" }?.suggestion, "Will suggest: before 09:30")
        XCTAssertEqual(t13.hot, [HotWindow(from: 10, to: 21)])
        XCTAssertEqual(t13.cells.count, 18)
        // 20:00: the band echoed tomorrow's plan
        let t20 = d0.addingTimeInterval(20 * 3600)
        for it in r1.items { seq += 1; try add(Frames.planItemEvent(seq: seq, boot: 0, unix: UInt32(t20.timeIntervalSince1970), it), t20) }
        let tm = try XCTUnwrap(HerDayDisplay.make(L: L, offset: 1, now: t20, plan: p1, local: r1, entries: entries, simulated: true))
        XCTAssertEqual(tm.bandLine, "Suggestions on her band ✓ 20:00")
        XCTAssertEqual(tm.rows.first { $0.title == "Market" }?.suggestion, "Band suggests: before 09:30")
        XCTAssertEqual(tm.rows.first { $0.title == "Walk" }?.kind, .outing)
        XCTAssertTrue(tm.rows.contains { $0.kind == .air })
        // the family phone with no routine at all still shows exactly what the band holds
        let bare = try XCTUnwrap(HerDayDisplay.make(L: L, offset: 1, now: t20, plan: nil, local: nil, entries: entries.filter { $0.kind == .planItem }, simulated: false))
        XCTAssertEqual(bare.rows.filter { $0.kind == .collision }.count, r1.items.filter { $0.kind == .outingShift }.count)
        // Greek card sentence on her phone
        XCTAssertEqual(Strings(lang: .el).hdCard(r1.items, tomorrow: true), "Αύριο: αγορά πριν τις 09:30")
        XCTAssertEqual(L.hdCard(r1.items, tomorrow: true), "Tomorrow: market before 09:30")
    }

    /// The band's own vectors (fw/09_guardian/herday_vectors.json, band 0.9.8, copied to herday_vectors_fw.json):
    /// the band is the source of truth for every byte.
    func testFirmwareVectors() throws {
        let url = try XCTUnwrap(Bundle(for: HerDayTests.self).url(forResource: "herday_vectors_fw", withExtension: "json"))
        let f = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        func hm(_ v: Any?) -> Int? {
            guard let a = v as? [Int], a.count == 2, a != [255, 255] else { return nil }
            return a[0] * 60 + a[1]
        }
        for v in try XCTUnwrap(f["day_plan"] as? [[String: Any]]) {
            let hex = try XCTUnwrap(v["hex"] as? String)
            if int(v["n"]) == 0 { XCTAssertEqual(Frames.toHex(Frames.cmdDayPlanClear(day: int(v["day"])!)), hex); continue }
            let k = try XCTUnwrap(DayPlanKind(rawValue: int(v["kind"])!))
            let hot = try XCTUnwrap(v["hot"] as? [Int])
            let peak = int(v["peak_c"])
            let it = DayPlanItem(day: int(v["day"])!, kind: k, place: PlaceType(rawValue: int(v["place"])!)!,
                                 usual: k == .outingShift ? hm(v["usual"]) : nil, suggested: k == .heatwaveDay ? nil : hm(v["suggested"]),
                                 direction: ShiftDirection(rawValue: int(v["direction"]) ?? 0), hotFrom: hot[0], hotTo: hot[1],
                                 peakC: k == .outingShift && peak != 255 ? peak : nil, heatwaveDay: int(v["heatwave_day"]) ?? 0)
            XCTAssertEqual(Frames.toHex(try Frames.cmdDayPlan(it, index: int(v["index"])!, of: int(v["n"])!)), hex)
        }
        for v in try XCTUnwrap(f["day_plan_field_errors"] as? [[String: Any]]) {
            let b = try XCTUnwrap(Frames.fromHex(try XCTUnwrap(v["hex"] as? String)))
            // the app's types cannot even express kind 0/4, place 8, a half-set pair or minute 60: nothing to send
            guard let k = DayPlanKind(rawValue: Int(b[4])), let p = PlaceType(rawValue: Int(b[5])),
                  (b[6] == 0xFF) == (b[7] == 0xFF), b[7] <= 59 || b[7] == 0xFF, b[9] <= 59 else { continue }
            let it = DayPlanItem(day: Int(b[1]), kind: k, place: p, usual: b[6] == 0xFF ? nil : Int(b[6]) * 60 + Int(b[7]),
                                 suggested: Int(b[8]) * 60 + Int(b[9]), direction: ShiftDirection(rawValue: Int(b[10])),
                                 hotFrom: Int(b[11]), hotTo: Int(b[12]), peakC: Int(b[13]), heatwaveDay: Int(b[14]))
            XCTAssertThrowsError(try Frames.cmdDayPlan(it, index: Int(b[2]), of: Int(b[3])), v["error"] as? String ?? "")
        }
        for v in try XCTUnwrap(f["visit"] as? [[String: Any]]) {
            let fr = Frames.cmdVisit(VisitEdge(rawValue: int(v["event"])!)!, place: PlaceType(rawValue: int(v["place"])!)!,
                                     unix: UInt32((v["unix"] as! NSNumber).int64Value))
            XCTAssertEqual(Frames.toHex(fr), v["hex"] as? String)
        }
        for v in try XCTUnwrap(f["events"] as? [[String: Any]]) {
            let hex = try XCTUnwrap(v["hex"] as? String)
            let e = try Frames.decodeEvent(try XCTUnwrap(Frames.fromHex(hex)))
            XCTAssertEqual(e.seq, int(v["seq"]))
            XCTAssertEqual(Frames.toHex(Frames.encodeEvent(e)), hex)
            switch int(v["type"]) {
            case 9:
                let x = try XCTUnwrap(e.visit, hex)
                XCTAssertEqual(x.place.rawValue, int(v["arg_place"]))
                XCTAssertEqual(x.edge.rawValue, int(v["byte11_event"]))
                XCTAssertEqual(Int64(x.unix), (v["bytes12_15_visit_unix"] as! NSNumber).int64Value)
            case 10:
                let it = try XCTUnwrap(e.planItem, hex)
                XCTAssertEqual(it.kind.rawValue, int(v["arg_kind"]))
                XCTAssertEqual(it.day, int(v["byte18_day"]))
                XCTAssertEqual(it.direction?.rawValue ?? 0, int(v["byte18_direction"]))
                XCTAssertEqual(it.heatwaveDay, int(v["byte18_heatwave_day"]))
                if it.kind == .outingShift { XCTAssertEqual(it.usual, hm(v["usual"])); XCTAssertEqual(it.place.rawValue, int(v["place"])) }
                if it.kind != .heatwaveDay { XCTAssertEqual(it.suggested, hm(v["suggested"])) }
                XCTAssertEqual(Frames.toHex(Frames.encodeEvent(Frames.planItemEvent(seq: e.seq, boot: e.boot, unix: e.unix, it))), hex)
            default:
                XCTAssertEqual(e.arg, int(v["nudge_id"]))
                XCTAssertNotNil(NudgeID(rawValue: e.arg))
            }
        }
        for v in try XCTUnwrap(f["elder_action_new_ids"] as? [[String: Any]]) {
            XCTAssertEqual(Frames.toHex(Frames.cmdElderAction(.nudgeDone, nudge: int(v["nudge_id"])!)), v["hex"] as? String)
        }
        let t = try XCTUnwrap(f["band_texts"] as? [String: Any])
        func k1(_ p: PlaceType, _ s: Int, _ d: ShiftDirection, day: Int = 1) -> DayPlanItem {
            DayPlanItem(day: day, kind: .outingShift, place: p, usual: 600, suggested: s, direction: d, hotFrom: 10, hotTo: 20)
        }
        XCTAssertEqual(HerDay.briefSentence([k1(.market, 570, .before)], tomorrow: true), t["N7_kind1_before"] as? String)
        XCTAssertEqual(HerDay.briefSentence([k1(.cafe, 1260, .after)], tomorrow: true), t["N7_kind1_after"] as? String)
        XCTAssertEqual(HerDay.briefSentence([DayPlanItem(day: 1, kind: .heatwaveDay, heatwaveDay: 2)], tomorrow: true), t["N7_kind3_only"] as? String)
        XCTAssertEqual(HerDay.briefSentence([k1(.walk, 1260, .after, day: 0)], tomorrow: false), t["N1_kind1"] as? String)
        XCTAssertEqual(PlaceType.allCases.map { $0.bandWord }, t["place_words"] as? [String])
        XCTAssertEqual(Strings(lang: .el).nudgeBandText(.leaveHot, briefHour: nil), t["N8"] as? String)
    }
}
