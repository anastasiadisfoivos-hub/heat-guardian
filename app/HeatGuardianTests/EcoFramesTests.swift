// XCTest for EcoFrames.swift / Indoor.swift / NudgePlanner.swift / EventLog.swift on eco_vectors_app.json
// (the same file ios/tools/mirror_frames.py checks in Python).

import XCTest
@testable import HeatGuardian

final class EcoFramesTests: XCTestCase {
    private func vectors() throws -> [String: Any] {
        let url = try XCTUnwrap(Bundle(for: EcoFramesTests.self).url(forResource: "eco_vectors_app", withExtension: "json"))
        return try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
    }
    private func int(_ v: Any?) -> Int? { (v as? NSNumber)?.intValue }

    func testEvents() throws {
        let v = try vectors()
        for e in try XCTUnwrap(v["events"] as? [[String: Any]]) {
            let hex = try XCTUnwrap(e["hex"] as? String)
            let d = try Frames.decodeEvent(try XCTUnwrap(Frames.fromHex(hex)))
            XCTAssertEqual(d.seq, int(e["seq"]), hex)
            XCTAssertEqual(d.boot, int(e["boot"]), hex)
            XCTAssertEqual(Int(d.unix), int(e["unix"]), hex)
            XCTAssertEqual(d.kindRaw, int(e["kind"]), hex)
            XCTAssertEqual(d.arg, int(e["arg"]), hex)
            XCTAssertEqual(Frames.toHex(Frames.encodeEvent(d)), hex)
        }
        for h in try XCTUnwrap(v["events_bad"] as? [String]) {
            XCTAssertThrowsError(try Frames.decodeEvent(Frames.fromHex(h) ?? []), h)
        }
    }

    func testCommands() throws {
        let v = try vectors()
        for e in try XCTUnwrap(v["sync_events"] as? [[String: Any]]) {
            XCTAssertEqual(Frames.toHex(Frames.cmdSyncEvents(sinceSeq: int(e["since_seq"])!, boot: int(e["boot"])!)), e["hex"] as? String)
        }
        for e in try XCTUnwrap(v["family_msg"] as? [[String: Any]]) {
            XCTAssertEqual(Frames.toHex(Frames.cmdFamilyMsg(UInt8(int(e["msg"])!))), e["hex"] as? String)
        }
        for e in try XCTUnwrap(v["family_name"] as? [[String: Any]]) {
            let n = try XCTUnwrap(e["name"] as? String)
            XCTAssertEqual(Frames.toHex(Frames.cmdFamilyName(n)), e["hex"] as? String, n)
            XCTAssertEqual(Frames.familyNameBytes(n).count, int(e["bytes"]), n)
        }
        for e in try XCTUnwrap(v["routine_seed"] as? [[String: Any]]) {
            let a = try XCTUnwrap(e["args"] as? [String: Any])
            let f = Frames.cmdRoutineSeed(wake: int(a["wake"]), bed: int(a["bed"]), napFrom: int(a["nap_from"]), napTo: int(a["nap_to"]),
                                          out1From: int(a["out1_from"]), out1To: int(a["out1_to"]),
                                          out2From: int(a["out2_from"]), out2To: int(a["out2_to"]),
                                          ac: (a["ac"] as? NSNumber)?.boolValue)
            XCTAssertEqual(Frames.toHex(f), e["hex"] as? String)
            XCTAssertEqual(f.count, 20)
        }
    }

    /// The firmware's own vectors (fw/09_guardian/eco_vectors.json, band 0.9.7): the band is the source of truth.
    func testFirmwareVectors() throws {
        let url = try XCTUnwrap(Bundle(for: EcoFramesTests.self).url(forResource: "eco_vectors_fw", withExtension: "json"))
        let f = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        var events = try XCTUnwrap(f["events"] as? [[String: Any]])
        events.append(try XCTUnwrap(f["event_clock_not_set"] as? [String: Any]))
        for e in events {
            let hex = try XCTUnwrap(e["hex"] as? String)
            let d = try Frames.decodeEvent(try XCTUnwrap(Frames.fromHex(hex)))
            XCTAssertEqual(d.seq, int(e["seq"]), hex)
            XCTAssertEqual(d.boot, int(e["boot_count"]), hex)
            XCTAssertEqual(Int(d.unix), int(e["unix"]), hex)
            XCTAssertEqual(d.kindRaw, int(e["type"]), hex)
            XCTAssertEqual(d.arg, int(e["arg"]), hex)
            XCTAssertEqual(Frames.toHex(Frames.encodeEvent(d)), hex)
        }
        // WARN_SHOWN arg 3 = HG_ST_CHECK (not the STATUS code 3 = DANGER)
        let warn = LogEntry(id: "w", at: Date(), kind: .warnShown, arg: 3, origin: .band)
        XCTAssertEqual(warn.warnState, "CHECK")
        func hm(_ s: Any?) -> Int? {
            guard let s = s as? String else { return nil }
            let p = s.split(separator: ":").compactMap { Int($0) }
            return p.count == 2 ? p[0] * 60 + p[1] : nil
        }
        func win(_ s: Any?) -> (Int?, Int?) {
            guard let s = s as? String else { return (nil, nil) }
            let p = s.split(separator: "-").map(String.init)
            return p.count == 2 ? (hm(p[0]), hm(p[1])) : (nil, nil)
        }
        for c in try XCTUnwrap(f["commands"] as? [[String: Any]]) {
            let hex = try XCTUnwrap(c["hex"] as? String)
            switch c["op"] as? String {
            case "0x16": XCTAssertEqual(Frames.toHex(Frames.cmdSyncEvents(sinceSeq: int(c["since_seq"])!, boot: int(c["boot_count"])!)), hex)
            case "0x17": XCTAssertEqual(Frames.toHex(Frames.cmdFamilyMsg(UInt8(int(c["msg"])!))), hex)
            case "0x18": XCTAssertEqual(Frames.toHex(Frames.cmdFamilyName(c["utf8"] as? String ?? "")), hex)
            case "0x19":
                let n = win(c["nap"]), o1 = win(c["out1"]), o2 = win(c["out2"])
                let got = Frames.cmdRoutineSeed(wake: hm(c["wake"]), bed: hm(c["bed"]), napFrom: n.0, napTo: n.1,
                                                out1From: o1.0, out1To: o1.1, out2From: o2.0, out2To: o2.1,
                                                ac: (c["ac_at_home"] as? NSNumber)?.boolValue)
                XCTAssertEqual(Frames.toHex(got), hex)
            case "0x1A":
                let a = try XCTUnwrap(HG.ElderAction(rawValue: UInt8(int(c["action"])!)))
                XCTAssertEqual(Frames.toHex(Frames.cmdElderAction(a, nudge: int(c["nudge_id"]) ?? 0)), hex)
            default: break
            }
        }
    }

    func testElderAction() throws {
        let v = try vectors()
        for e in try XCTUnwrap(v["elder_action"] as? [[String: Any]]) {
            let action = try XCTUnwrap(HG.ElderAction(rawValue: UInt8(try XCTUnwrap(int(e["action"])))))
            let f = Frames.cmdElderAction(action, nudge: try XCTUnwrap(int(e["nudge"])))
            XCTAssertEqual(Frames.toHex(f), e["hex"] as? String)
            XCTAssertEqual(f.count, 20)
            XCTAssertEqual(f[0], 0x1A)
            XCTAssertEqual(Frames.crc8(f, count: 19), f[19])
        }
    }

    func testIndoorAdjust() throws {
        let v = try vectors()
        let plan = try XCTUnwrap(Plan.bundled())
        for e in try XCTUnwrap(v["indoor_adjust"] as? [[String: Any]]) {
            let cls = try XCTUnwrap(e["cls"] as? String)
            let want = try XCTUnwrap(e["t_in"] as? [NSNumber]).map { $0.doubleValue }
            let got = Indoor.adjust(plan, to: cls)
            XCTAssertEqual(got.homeClass, cls)
            for (g, w) in zip(got.hours.map { $0.tIn }, want) { XCTAssertEqual(g, w, accuracy: 1e-9, cls) }
        }
        XCTAssertEqual(Indoor.adjust(plan, to: plan.homeClass), plan)
    }

    func testStoreDeduplicatesAndAdvancesCursor() {
        let s = EventStore(fileName: nil)
        let e1 = BandEvent(seq: 5, boot: 3, unix: 1_789_400_000, kindRaw: 1, arg: 4)
        XCTAssertNotNil(s.addBand(e1, receivedAt: Date()))
        XCTAssertNil(s.addBand(e1, receivedAt: Date()))           // re-notified after SYNC: no second row
        XCTAssertEqual(s.entries.count, 1)
        _ = s.addBand(BandEvent(seq: 6, boot: 3, unix: 1_789_400_060, kindRaw: 2, arg: 4), receivedAt: Date())
        _ = s.addBand(BandEvent(seq: 2, boot: 3, unix: 1_789_399_000, kindRaw: 4, arg: 0), receivedAt: Date())
        XCTAssertEqual(s.cursorSeq, 6)                             // an older replayed event does not move it back
        XCTAssertEqual(s.entries.map { $0.kind }, [.imOK, .nudgeShown, .nudgeDone])
        _ = s.addBand(BandEvent(seq: 1, boot: 4, unix: 0, kindRaw: 8, arg: 1), receivedAt: Date())
        XCTAssertEqual(s.cursorBoot, 4)
        XCTAssertEqual(s.cursorSeq, 1)
        XCTAssertFalse(s.entries.last!.clockKnown)
    }

    func testTimelineCollapsesNudges() {
        let day = Calendar.current.startOfDay(for: Date())
        let s = EventStore(fileName: nil)
        let t0 = UInt32(day.addingTimeInterval(10 * 3600).timeIntervalSince1970)
        _ = s.addBand(BandEvent(seq: 1, boot: 1, unix: t0, kindRaw: 1, arg: 4), receivedAt: Date())
        _ = s.addBand(BandEvent(seq: 2, boot: 1, unix: t0 + 120, kindRaw: 2, arg: 4), receivedAt: Date())
        _ = s.addBand(BandEvent(seq: 3, boot: 1, unix: t0 + 6000, kindRaw: 1, arg: 3), receivedAt: Date())
        _ = s.addBand(BandEvent(seq: 4, boot: 1, unix: t0 + 6600, kindRaw: 3, arg: 3), receivedAt: Date())
        let items = Timeline.items(s.entries(on: day), day: day)
        XCTAssertEqual(items.count, 2)
        let sum = Timeline.summary(s.entries(on: day), day: day)
        XCTAssertEqual([sum.nudgesDone, sum.nudgesShown, sum.water, sum.warnings], [1, 2, 1, 0])
    }

    func testNudgePlannerCaps() throws {
        var plan = try XCTUnwrap(Plan.bundled())
        plan.nightHeat = true
        let r = Routine(wake: 7 * 60, bed: 23 * 60, nap: TimeWindow(from: 14 * 60, to: 16 * 60), ac: true)
        let ns = NudgePlanner.plan(plan, routine: r)
        XCTAssertLessThanOrEqual(ns.count, NudgePlanner.maxPerDay)
        for (a, b) in zip(ns, ns.dropFirst()) { XCTAssertGreaterThanOrEqual(b.minute - a.minute, NudgePlanner.minGap) }
        XCTAssertFalse(ns.contains { r.asleep($0.minute) })
    }
}
