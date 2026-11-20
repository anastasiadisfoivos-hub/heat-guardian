// Heat Guardian BLE frames, phone side. A line-by-line port of dashboard/js/hgframes.js
// (layout: guardian/c/hg_frames.h, frozen; 0x11 / 0x14: tomorrow/ble_frame.py).
// CRC-8/SMBUS: poly 0x07, init 0x00, no reflection, no final xor; check("123456789") = 0xF4. All little-endian.
// ios/tools/mirror_frames.py is a Python mirror of THIS file, run against the same vectors.

import Foundation

enum HG {
    // Service and characteristics frozen with uuidgen on Nov 12 (fw/09_guardian/README.md "BLE details").
    static let service = "0C760000-038B-46D5-8532-954DD1C5E01D"
    static let status  = "0C760001-038B-46D5-8532-954DD1C5E01D"
    static let cmd     = "0C760002-038B-46D5-8532-954DD1C5E01D"
    static let info    = "0C760003-038B-46D5-8532-954DD1C5E01D"
    // Nordic UART console of fw 08/09 (used only for the `profile <age> <sex> <bmi> <meds>` line).
    static let nusService = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
    static let nusRX      = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
    static let namePrefix = "HeatGuardian"

    // STATUS byte 1 bits 0-2 (hg_frames.h): 0 OK 1 DRINK 2 COOL 3 DANGER 4 IMOK 5 BATTERY 6 CHECK 7 HELP
    static let stateNames = ["OK", "DRINK", "COOL", "DANGER", "IMOK", "BATTERY", "CHECK", "HELP"]

    enum Op: UInt8 {
        case time = 0x10, forecast = 0x11, familyAck = 0x12, profile = 0x13, safeHours = 0x14, consent = 0x15, debug = 0x1F
    }
}

struct FrameError: Error, Equatable, CustomStringConvertible {
    let message: String
    var description: String { message }
}

/// Same fields as B5's guardian/py status_unpack() and the dashboard's decodeStatus().
struct StatusFrame: Equatable, Codable {
    var version: Int
    var familyPending: Bool
    var notWorn: Bool
    var stateCode: Int
    var contactOK: Bool
    var timeSynced: Bool
    var charging: Bool
    var home: Bool
    var ppgValid: Bool
    var coreC: Double
    var halfRangeC: Double
    var hrBpm: Int
    var hrQ: Int
    var t1C: Double?
    var t2C: Double?
    var tairC: Double?
    var rhPct: Int?
    var batteryPct: Int
    var minuteCounter: Int
    var alarmId16: Int?      // only while familyPending (bytes 15-16)
    var routineScore: Int?   // only while NOT familyPending (byte 15; 255 = not learnt yet)
    var activity: Int?       // only while NOT familyPending (byte 16; accel std x 1000, capped 255)

    var state: String { HG.stateNames[stateCode] }
    /// A core estimate exists (the band sends 0 while warming up) and the band is worn.
    var hasEstimate: Bool { coreC > 0 && !notWorn }
}

enum Frames {
    static func crc8(_ bytes: [UInt8], count: Int? = nil) -> UInt8 {
        let n = count ?? bytes.count
        var c: UInt8 = 0
        for i in 0..<n {
            c ^= bytes[i]
            for _ in 0..<8 {
                c = (c & 0x80) != 0 ? ((c << 1) ^ 0x07) : (c << 1)
            }
        }
        return c
    }

    // MARK: STATUS (20 B)

    /// The band seeds its STATUS characteristic with 20 zero bytes until the guardian's first minute. That frame passes
    /// CRC-8 (crc of zeros = 0) but is not a reading: the app shows "waiting" and does not log it.
    static func isEmptyStatus(_ b: [UInt8]) -> Bool { b.count == 20 && b.allSatisfy { $0 == 0 } }

    static func decodeStatus(_ b: [UInt8]) throws -> StatusFrame {
        guard b.count == 20 else { throw FrameError(message: "STATUS length \(b.count) (expected 20)") }
        guard crc8(b, count: 19) == b[19] else { throw FrameError(message: "STATUS CRC mismatch") }
        guard (b[0] & 0x0F) == 1 else { throw FrameError(message: "STATUS version \(b[0] & 0x0F) (expected 1)") }
        func u16(_ o: Int) -> Int { Int(b[o]) | (Int(b[o + 1]) << 8) }
        func i16(_ o: Int) -> Int { let v = u16(o); return v >= 0x8000 ? v - 0x10000 : v }
        func t(_ o: Int) -> Double? { let v = i16(o); return v == -32768 ? nil : Double(v) / 100.0 }
        let fam = (b[0] & 0x10) != 0
        var d = StatusFrame(
            version: Int(b[0] & 0x0F), familyPending: fam, notWorn: (b[0] & 0x20) != 0,
            stateCode: Int(b[1] & 7), contactOK: (b[1] & 8) != 0, timeSynced: (b[1] & 16) != 0,
            charging: (b[1] & 32) != 0, home: (b[1] & 64) != 0, ppgValid: (b[1] & 128) != 0,
            coreC: Double(u16(2)) / 100.0, halfRangeC: Double(b[4]) / 100.0, hrBpm: Int(b[5]), hrQ: Int(b[6]),
            t1C: t(7), t2C: t(9), tairC: t(11), rhPct: b[13] == 255 ? nil : Int(b[13]), batteryPct: Int(b[14]),
            minuteCounter: u16(17), alarmId16: nil, routineScore: nil, activity: nil)
        if fam { d.alarmId16 = u16(15) } else { d.routineScore = Int(b[15]); d.activity = Int(b[16]) }
        return d
    }

    static func decodeStatus(hex: String) throws -> StatusFrame {
        guard let b = fromHex(hex) else { throw FrameError(message: "STATUS hex") }
        return try decodeStatus(b)
    }

    // MARK: INFO (20 B): [0]=0x02 [1-2]fw [3-6]nn crc [7-8]boots [9]reset [10-11]twin saves [12-18]tag [19]crc8

    struct Info: Equatable {
        var fwVersion: Int, nnCRC: UInt32, bootCount: Int, resetReason: Int, twinSaves: Int, hg2Tag: String
        /// fw_version is BCD: 0x0094 -> "0.9.4", 0x0096 -> "0.9.6"; from 0.9.10 on two BCD bytes: 0x0910 -> "0.9.10",
        /// 0x0917 -> "0.9.17" (fw 09_guardian.ino HG_FW_NUM).
        var fwText: String { Frames.bcdVersion(fwVersion) }
    }

    /// Band firmware version text. Up to 0.9.9 one BCD byte "0.<minor>.<patch>" (0x0099); from 0.9.10 the high byte is
    /// the minor and the low byte the patch, each BCD (0x0910 = 0.9.10, 0x0917 = 0.9.17). The old nibble formula read
    /// 0x0917 as "9.1.7".
    static func bcdVersion(_ v: Int) -> String {
        func bcd(_ b: Int) -> Int { ((b >> 4) & 0xF) * 10 + (b & 0xF) }
        let hi = (v >> 8) & 0xFF, lo = v & 0xFF
        if hi == 0 { return "0.\((lo >> 4) & 0xF).\(lo & 0xF)" }
        return "0.\(bcd(hi)).\(bcd(lo))"
    }

    static func decodeInfo(_ b: [UInt8]) throws -> Info {
        guard b.count == 20, crc8(b, count: 19) == b[19] else { throw FrameError(message: "INFO CRC/length") }
        func u16(_ o: Int) -> Int { Int(b[o]) | (Int(b[o + 1]) << 8) }
        let crc = UInt32(b[3]) | (UInt32(b[4]) << 8) | (UInt32(b[5]) << 16) | (UInt32(b[6]) << 24)
        let tagBytes = Array(b[12..<19]).filter { $0 != 0 }
        let tag = String(decoding: tagBytes, as: UTF8.self)
        return Info(fwVersion: u16(1), nnCRC: crc, bootCount: u16(7), resetReason: Int(b[9]), twinSaves: u16(10), hg2Tag: tag)
    }

    // MARK: phone -> band commands

    static func seal(_ arr: [UInt8]) -> [UInt8] { arr + [crc8(arr)] }
    static func le32(_ v: UInt32) -> [UInt8] {
        [UInt8(v & 255), UInt8((v >> 8) & 255), UInt8((v >> 16) & 255), UInt8((v >> 24) & 255)]
    }

    /// 0x10 TIME: u32 unix seconds, i8 time zone in quarter hours (7 B).
    static func cmdTime(unixS: UInt32, tzQ: Int) -> [UInt8] {
        seal([HG.Op.time.rawValue] + le32(unixS) + [UInt8(truncatingIfNeeded: tzQ)])
    }
    static func tzQuarterHours(_ date: Date = Date(), tz: TimeZone = .current) -> Int {
        Int((Double(tz.secondsFromGMT(for: date)) / 900.0).rounded())
    }
    static func cmdTimeNow() -> [UInt8] {
        cmdTime(unixS: UInt32(clamping: Int64(Date().timeIntervalSince1970)), tzQ: tzQuarterHours())
    }

    /// 0x12 FAMILY_ACK: u8 type (1 family notified, 2 family replied "I'll call", 3 cancelled), u32 alarm id (7 B).
    static func cmdFamilyAck(type: UInt8, alarmId: UInt32) -> [UInt8] {
        seal([HG.Op.familyAck.rawValue, type] + le32(alarmId))
    }

    /// 0x13 PROFILE: u8 field, f32 value (7 B). Fields: 0 thermometer reading °C (display only), 2 resting HR,
    /// 4 skin-ref gain, 5 medication flags 0..31 sent as a float (1 beta-blocker, 2 diuretic, 4 low-sweat,
    /// 8 ACE/ARB, 16 other HR-limiting drug / pacemaker; B5-v7). Older bands answer unknown fields 0.
    static func cmdProfile(field: UInt8, value: Float) -> [UInt8] {
        seal([HG.Op.profile.rawValue, field] + le32(value.bitPattern))
    }

    /// 0x15 CONSENT (fw 0.9.5, branch b7-ble-sec): u8 bits 1 family alerts, 2 forecast, 4 data logging (3 B).
    static func cmdConsent(bits: UInt8) -> [UInt8] { seal([HG.Op.consent.rawValue, bits & 7]) }

    // MARK: Tomorrow plan -> 0x11 x4 + 0x14

    /// Python round() is half-to-even; Swift's .toNearestOrEven is the same rule.
    static func pyRound(_ x: Double) -> Int { Int(x.rounded(.toNearestOrEven)) }

    static func hourFlags(_ plan: Plan, _ h: Int) -> UInt8 {
        let hr = plan.hours[h]
        var f: Int = 0
        if plan.heatDay { f |= 1 }
        if plan.nightHeat { f |= 2 }
        if hr.safe { f |= 4 }
        f |= (h / 6) << 3
        return UInt8(f)
    }

    /// 0x11 FORECAST: 4 chunks x [0x11][6 x (i8 T_in, u8 RH_in, u8 flags)][crc]
    static func forecastChunks(_ plan: Plan) throws -> [[UInt8]] {
        guard plan.hours.count == 24 else { throw FrameError(message: "plan needs 24 hours") }
        var out: [[UInt8]] = []
        for k in 0..<4 {
            var body: [UInt8] = [HG.Op.forecast.rawValue]
            for h in (6 * k)..<(6 * k + 6) {
                let t = max(-128, min(127, pyRound(plan.hours[h].tIn)))
                let rh = max(0, min(100, pyRound(plan.hours[h].rhIn)))
                body.append(UInt8(truncatingIfNeeded: t))
                body.append(UInt8(rh))
                body.append(hourFlags(plan, h))
            }
            out.append(seal(body))
        }
        return out
    }

    static func safeBitmap(_ plan: Plan) -> UInt32 {
        var b: UInt32 = 0
        for (i, h) in plan.hours.enumerated() where h.safe && i < 32 { b |= (UInt32(1) << UInt32(i)) }
        return b
    }

    /// Day-of-year of the plan date ("YYYY-MM-DD"), mod 256 (tomorrow/ble_frame.py plan_id).
    static func planId(_ dateStr: String) -> UInt8 {
        let p = dateStr.split(separator: "-").compactMap { Int($0) }
        guard p.count == 3 else { return 0 }
        let (y, m, d) = (p[0], p[1], p[2])
        let leap = (y % 4 == 0 && y % 100 != 0) || y % 400 == 0
        let monthDays = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        var doy = d
        if m > 1 { for i in 0..<(m - 1) { doy += monthDays[i] } }
        return UInt8(doy & 255)
    }

    /// 0x14 SAFE_HOURS: [0x14][u24 bitmap][u8 plan id][14 B ASCII tag, NUL padded][crc]
    static func safeHoursFrame(_ plan: Plan, tag: String? = nil) -> [UInt8] {
        let tg = tag ?? (plan.date + " " + (plan.homeClass ?? "") + ((plan.staleForecast ?? false) ? " C" : ""))
        let bm = safeBitmap(plan)
        var body: [UInt8] = [HG.Op.safeHours.rawValue, UInt8(bm & 255), UInt8((bm >> 8) & 255), UInt8((bm >> 16) & 255), planId(plan.date)]
        let units = Array(tg.utf16)
        for i in 0..<14 {
            let c: UInt16 = i < units.count ? units[i] : 0
            body.append(c > 127 ? 63 : UInt8(c))
        }
        return seal(body)
    }

    // MARK: hex helpers

    static func fromHex(_ h: String) -> [UInt8]? {
        let chars = Array(h.utf8)
        guard chars.count % 2 == 0 else { return nil }
        var out: [UInt8] = []
        out.reserveCapacity(chars.count / 2)
        var i = 0
        while i < chars.count {
            guard let hi = nibble(chars[i]), let lo = nibble(chars[i + 1]) else { return nil }
            out.append(hi << 4 | lo)
            i += 2
        }
        return out
    }
    private static func nibble(_ c: UInt8) -> UInt8? {
        switch c {
        case 48...57: return c - 48
        case 97...102: return c - 87
        case 65...70: return c - 55
        default: return nil
        }
    }
    static func toHex(_ b: [UInt8]) -> String { b.map { String(format: "%02x", $0) }.joined() }
}
