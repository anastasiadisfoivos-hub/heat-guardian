// Linux / command-line check of the non-UI Swift (Frames, Plan, Replay + DemoPlayer, Week, Strings/AdviceEN)
// against the same vectors as HeatGuardianTests/FramesTests.swift. Build + run (from ios/):
//
//   swiftc -o /tmp/hgcheck tools/LinuxCheck.swift HeatGuardian/BLE/Frames.swift HeatGuardian/Model/Plan.swift HeatGuardian/Model/Replay.swift HeatGuardian/Model/Week.swift HeatGuardian/Model/Strings.swift && /tmp/hgcheck .
//
// (The file is named LinuxCheck.swift, so it uses an explicit @main type instead of top-level code.)

import Foundation

@main
struct LinuxCheck {
    static var pass = 0, fail = 0
    static func check(_ ok: Bool, _ msg: @autoclosure () -> String) { if ok { pass += 1 } else { fail += 1; print("FAIL", msg()) } }

    static func main() throws {
        let ios = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "."
        func json(_ rel: String) throws -> [String: Any] {
            let d = try Data(contentsOf: URL(fileURLWithPath: ios + "/" + rel))
            return try JSONSerialization.jsonObject(with: d) as! [String: Any]
        }
        check(Frames.crc8(Array("123456789".utf8)) == 0xF4, "crc")

        let sv = try json("HeatGuardianTests/status_vectors.json")
        for v in sv["status"] as! [[String: Any]] {
            let hex = v["hex"] as! String, e = v["expect"] as! [String: Any]
            let d = try Frames.decodeStatus(hex: hex)
            func num(_ k: String) -> Double? { (e[k] as? NSNumber)?.doubleValue }
            func b(_ k: String) -> Bool? { (e[k] as? NSNumber)?.boolValue }
            func opt(_ got: Double?, _ k: String) -> Bool { e[k] is NSNull ? got == nil : (got != nil && abs(got! - num(k)!) < 1e-9) }
            check(d.version == Int(num("version")!) && d.familyPending == b("family_pending") && d.notWorn == b("not_worn")
                  && d.stateCode == Int(num("state_code")!) && d.contactOK == b("contact_ok") && d.timeSynced == b("time_synced")
                  && d.charging == b("charging") && d.home == b("home") && d.ppgValid == b("ppg_valid"), "flags " + hex)
            check(abs(d.coreC - num("core_c")!) < 1e-9 && abs(d.halfRangeC - num("half_range_c")!) < 1e-9, "core " + hex)
            check(d.hrBpm == Int(num("hr_bpm")!) && d.hrQ == Int(num("hr_q")!), "hr " + hex)
            check(opt(d.t1C, "t1_c") && opt(d.t2C, "t2_c") && opt(d.tairC, "tair_c"), "temps " + hex)
            check(e["rh_pct"] is NSNull ? d.rhPct == nil : d.rhPct == Int(num("rh_pct")!), "rh " + hex)
            check(d.batteryPct == Int(num("battery_pct")!) && d.minuteCounter == Int(num("minute_counter")!), "bat/min " + hex)
            if d.familyPending {
                check(d.alarmId16 == Int(num("alarm_id16")!) && d.routineScore == nil && d.activity == nil, "fam " + hex)
            } else {
                check(d.routineScore == Int(num("routine_score")!) && d.activity == Int(num("activity")!) && d.alarmId16 == nil, "routine " + hex)
            }
        }
        for h in sv["status_corrupt"] as! [String] { check((try? Frames.decodeStatus(hex: h)) == nil, "corrupt accepted " + h) }

        let cmd = sv["cmd"] as! [String: Any]
        for v in cmd["time"] as! [[String: Any]] {
            check(Frames.toHex(Frames.cmdTime(unixS: UInt32((v["unix_s"] as! NSNumber).int64Value), tzQ: (v["tz_q"] as! NSNumber).intValue)) == v["hex"] as! String, "TIME")
        }
        for v in cmd["family_ack"] as! [[String: Any]] {
            check(Frames.toHex(Frames.cmdFamilyAck(type: UInt8((v["ack_type"] as! NSNumber).intValue), alarmId: UInt32((v["alarm_id"] as! NSNumber).int64Value))) == v["hex"] as! String, "ACK")
        }
        for v in cmd["profile"] as! [[String: Any]] {
            check(Frames.toHex(Frames.cmdProfile(field: UInt8((v["field"] as! NSNumber).intValue), value: (v["value"] as! NSNumber).floatValue)) == v["hex"] as! String, "PROFILE \(v)")
        }
        check(Frames.toHex(Frames.cmdConsent(bits: 3)) == "15031f", "CONSENT")
        check(Frames.tzQuarterHours(Date(timeIntervalSince1970: 1784016000), tz: TimeZone(identifier: "Europe/Athens")!) == 12, "tz summer Athens = +3 h = 12 q")
        check(Frames.tzQuarterHours(Date(timeIntervalSince1970: 1763287200), tz: TimeZone(identifier: "Europe/Athens")!) == 8, "tz winter Athens = +2 h = 8 q")

        let bv = try json("HeatGuardianTests/forecast_vectors.json")
        let vplan = try Plan.load(from: JSONSerialization.data(withJSONObject: bv["plan"]!))
        check(try Frames.forecastChunks(vplan).map(Frames.toHex) == bv["forecast_chunks_hex"] as! [String], "0x11 vectors")
        check(Frames.toHex(Frames.safeHoursFrame(vplan)) == bv["safe_hours_hex"] as! String, "0x14 vectors")
        check(Int(Frames.safeBitmap(vplan)) == (bv["safe_hours_bitmap"] as! NSNumber).intValue && Int(Frames.planId(vplan.date)) == (bv["plan_id"] as! NSNumber).intValue, "bitmap/id")

        let plan = try Plan.load(from: Data(contentsOf: URL(fileURLWithPath: ios + "/HeatGuardian/Resources/plan.json")))
        check(try Frames.forecastChunks(plan).map(Frames.toHex) == plan.ble!.forecastChunksHex!, "0x11 bundled plan")
        check(Frames.toHex(Frames.safeHoursFrame(plan)) == plan.ble!.safeHoursHex!, "0x14 bundled plan")
        check(plan.safeRanges().isEmpty && plan.hours.map { plan.slot($0) }.contains(.avoid), "demo plan: no safe hours, AVOID present")
        check(AdviceEN.translate("Μην βγείτε στις 10:00") == "Do not go out at 10:00", "advice EN")
        check(AdviceEN.translate("Ανοίξτε στις 22:00") == "Open the windows at 22:00", "advice EN 2")

        // Replay + DemoPlayer (step() without the Timer) feeding the same decoder; Week over the result.
        let rd = try Data(contentsOf: URL(fileURLWithPath: ios + "/HeatGuardian/Resources/sim_heatwave.json"))
        let r = try JSONDecoder().decode(Replay.self, from: rd)
        check(r.status.count == 1440 && r.isSim && r.firstFamilyIndex == 843, "replay meta")
        let p = DemoPlayer(replay: r, file: "sim_heatwave")
        var hist: [HistPoint] = []
        var familyEdges: [Int] = []
        var lastFam = false
        let ingest: ([UInt8], Date, Int) -> Void = { bytes, t, i in
            guard let d = try? Frames.decodeStatus(bytes) else { fail += 1; return }
            hist.append(HistPoint(t: t, vs: d.notWorn ? "NOT_WORN" : d.state, core: d.hasEstimate ? d.coreC : nil, half: d.halfRangeC,
                                  fam: d.familyPending, hr: d.hrBpm > 0 ? d.hrBpm : nil, activity: d.activity, routine: d.routineScore))
            if d.familyPending && !lastFam { familyEdges.append(i) }
            lastFam = d.familyPending
        }
        p.onFrame = ingest
        p.seek(to: 0) { _, _, _ in }
        while p.index < p.count - 1 { p.step(60) }
        check(hist.count == 1440, "demo fed every minute (\(hist.count))")
        check(familyEdges == [843, 1229], "family alert edges \(familyEdges)")
        let frame843 = try Frames.decodeStatus(hex: r.status[843])
        check(frame843.familyPending && frame843.alarmId16 == 200332 & 0xFFFF, "frame 843 alarm id16 == events alarm_id & 0xFFFF")
        let days = Week.days(hist, today: p.clock(1439))
        let today = days.last!
        check(days.count == 7 && today.minutes == 1440 && days.dropLast().allSatisfy { $0.minutes == 0 }, "week: one day of data")
        check(today.alerts == 2 && today.tierMin > 0 && today.hrMean != nil, "week stats \(today)")
        print("week today: rest \(today.restMin) min, HR \(today.hrMean ?? -1), routine \(String(describing: today.routine)), tier \(today.tierMin) min, alerts \(today.alerts)")

        print("LinuxCheck: \(pass) passed, \(fail) failed")
        exit(fail == 0 ? 0 : 1)
    }
}
