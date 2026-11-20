// XCTest for Frames.swift on the same vectors as dashboard/tests/run_tests.js (status_vectors.json = frames packed by
// the frozen C build + B5 edge frames; forecast_vectors.json = tomorrow/tests/ble_vectors.json).
// Run in Xcode: Product › Test (⌘U). ios/tools/mirror_frames.py runs the same checks in Python.

import XCTest
@testable import HeatGuardian

final class FramesTests: XCTestCase {
    private func json(_ name: String) throws -> [String: Any] {
        let url = try XCTUnwrap(Bundle(for: FramesTests.self).url(forResource: name, withExtension: "json"), "missing \(name).json")
        return try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
    }

    func testCRC() {
        XCTAssertEqual(Frames.crc8(Array("123456789".utf8)), 0xF4)
    }

    func testStatusVectors() throws {
        let sv = try json("status_vectors")
        let list = try XCTUnwrap(sv["status"] as? [[String: Any]])
        XCTAssertGreaterThan(list.count, 20)
        for v in list {
            let hex = try XCTUnwrap(v["hex"] as? String)
            let e = try XCTUnwrap(v["expect"] as? [String: Any])
            let d = try Frames.decodeStatus(hex: hex)
            func num(_ k: String) -> Double? { (e[k] as? NSNumber)?.doubleValue }
            func bool(_ k: String) -> Bool? { (e[k] as? NSNumber)?.boolValue }
            XCTAssertEqual(d.version, Int(num("version") ?? -1), hex)
            XCTAssertEqual(d.familyPending, bool("family_pending"), hex)
            XCTAssertEqual(d.notWorn, bool("not_worn"), hex)
            XCTAssertEqual(d.stateCode, Int(num("state_code") ?? -1), hex)
            XCTAssertEqual(d.contactOK, bool("contact_ok"), hex)
            XCTAssertEqual(d.timeSynced, bool("time_synced"), hex)
            XCTAssertEqual(d.charging, bool("charging"), hex)
            XCTAssertEqual(d.home, bool("home"), hex)
            XCTAssertEqual(d.ppgValid, bool("ppg_valid"), hex)
            XCTAssertEqual(d.coreC, num("core_c") ?? -1, accuracy: 1e-9, hex)
            XCTAssertEqual(d.halfRangeC, num("half_range_c") ?? -1, accuracy: 1e-9, hex)
            XCTAssertEqual(d.hrBpm, Int(num("hr_bpm") ?? -1), hex)
            XCTAssertEqual(d.hrQ, Int(num("hr_q") ?? -1), hex)
            for (k, got) in [("t1_c", d.t1C), ("t2_c", d.t2C), ("tair_c", d.tairC)] {
                if e[k] is NSNull { XCTAssertNil(got, "\(hex) \(k)") } else { XCTAssertEqual(got ?? -999, num(k) ?? 999, accuracy: 1e-9, "\(hex) \(k)") }
            }
            if e["rh_pct"] is NSNull { XCTAssertNil(d.rhPct, hex) } else { XCTAssertEqual(d.rhPct, num("rh_pct").map { Int($0) }, hex) }
            XCTAssertEqual(d.batteryPct, Int(num("battery_pct") ?? -1), hex)
            XCTAssertEqual(d.minuteCounter, Int(num("minute_counter") ?? -1), hex)
            if d.familyPending {
                XCTAssertEqual(d.alarmId16, num("alarm_id16").map { Int($0) }, hex)
                XCTAssertNil(d.routineScore); XCTAssertNil(d.activity)
            } else {
                XCTAssertEqual(d.routineScore, num("routine_score").map { Int($0) }, hex)
                XCTAssertEqual(d.activity, num("activity").map { Int($0) }, hex)
                XCTAssertNil(d.alarmId16)
            }
        }
    }

    func testCorruptAndShortRejected() throws {
        let sv = try json("status_vectors")
        for h in try XCTUnwrap(sv["status_corrupt"] as? [String]) {
            XCTAssertThrowsError(try Frames.decodeStatus(hex: h), h)
        }
        let first = try XCTUnwrap((sv["status"] as? [[String: Any]])?.first?["hex"] as? String)
        XCTAssertThrowsError(try Frames.decodeStatus(hex: String(first.prefix(38))))
        // The firmware's seed value (20 zero bytes) passes CRC-8 but is version 0: not a reading.
        let zero = [UInt8](repeating: 0, count: 20)
        XCTAssertTrue(Frames.isEmptyStatus(zero))
        XCTAssertThrowsError(try Frames.decodeStatus(zero))
        XCTAssertEqual(Frames.bcdVersion(0x0094), "0.9.4")
        XCTAssertEqual(Frames.bcdVersion(0x0096), "0.9.6")
    }

    func testCommandVectors() throws {
        let cmd = try XCTUnwrap(try json("status_vectors")["cmd"] as? [String: Any])
        for v in try XCTUnwrap(cmd["time"] as? [[String: Any]]) {
            let f = Frames.cmdTime(unixS: UInt32((v["unix_s"] as! NSNumber).int64Value), tzQ: (v["tz_q"] as! NSNumber).intValue)
            XCTAssertEqual(Frames.toHex(f), v["hex"] as? String)
        }
        for v in try XCTUnwrap(cmd["family_ack"] as? [[String: Any]]) {
            let f = Frames.cmdFamilyAck(type: UInt8((v["ack_type"] as! NSNumber).intValue), alarmId: UInt32((v["alarm_id"] as! NSNumber).int64Value))
            XCTAssertEqual(Frames.toHex(f), v["hex"] as? String)
        }
        for v in try XCTUnwrap(cmd["profile"] as? [[String: Any]]) {
            let f = Frames.cmdProfile(field: UInt8((v["field"] as! NSNumber).intValue), value: (v["value"] as! NSNumber).floatValue)
            XCTAssertEqual(Frames.toHex(f), v["hex"] as? String)
        }
        XCTAssertEqual(Frames.toHex(Frames.cmdConsent(bits: 3)), "15031f")   // fw/09_guardian README (b7-ble-sec) example
    }

    func testForecastVectors() throws {
        let url = try XCTUnwrap(Bundle(for: FramesTests.self).url(forResource: "forecast_vectors", withExtension: "json"))
        let data = try Data(contentsOf: url)
        let bv = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let planObj = try XCTUnwrap(bv["plan"])
        let plan = try Plan.load(from: JSONSerialization.data(withJSONObject: planObj))
        XCTAssertEqual(try Frames.forecastChunks(plan).map(Frames.toHex), bv["forecast_chunks_hex"] as? [String])
        XCTAssertEqual(Frames.toHex(Frames.safeHoursFrame(plan)), bv["safe_hours_hex"] as? String)
        XCTAssertEqual(Int(Frames.safeBitmap(plan)), (bv["safe_hours_bitmap"] as? NSNumber)?.intValue)
        XCTAssertEqual(Int(Frames.planId(plan.date)), (bv["plan_id"] as? NSNumber)?.intValue)
    }

    func testBundledPlanMatchesItsOwnBleField() throws {
        let plan = try XCTUnwrap(Plan.bundled(), "plan.json in the app bundle")
        XCTAssertEqual(try Frames.forecastChunks(plan).map(Frames.toHex), plan.ble?.forecastChunksHex)
        XCTAssertEqual(Frames.toHex(Frames.safeHoursFrame(plan)), plan.ble?.safeHoursHex)
    }

    func testEveryReplayFrameDecodes() throws {
        for name in ["sim_heatwave", "htt_chamber"] {
            let r = try XCTUnwrap(Replay.bundled(name), name)
            for h in r.status { XCTAssertNoThrow(try Frames.decodeStatus(hex: h)) }
            if let fi = r.firstFamilyIndex { XCTAssertTrue(try Frames.decodeStatus(hex: r.status[fi]).familyPending) }
        }
    }

    func testPyRoundIsHalfToEven() {
        XCTAssertEqual(Frames.pyRound(0.5), 0)
        XCTAssertEqual(Frames.pyRound(1.5), 2)
        XCTAssertEqual(Frames.pyRound(2.5), 2)
        XCTAssertEqual(Frames.pyRound(-0.5), 0)
        XCTAssertEqual(Frames.pyRound(30.6), 31)
    }
}
