// XCTest for [APP-FINISH] (band 0.9.17-demo-b7, fw commit 430c58b): the INFO fw_version text of the two-byte BCD
// scheme (0x0917 = 0.9.17, read as "9.1.7" before), INFO frames made by the band's own packer (frozen hg_info_pack),
// the BLE write priority (HELP / family replies / SYNC ahead of the on-connect writes), the "replayed ring is History
// only" Tower rule, and that no EVENTS / STATUS / INFO bytes from a newer or broken band can crash the decoders.

import XCTest
@testable import HeatGuardian

final class AppFinishTests: XCTestCase {
    func testFirmwareVersionText() {
        XCTAssertEqual(Frames.bcdVersion(0x0094), "0.9.4")
        XCTAssertEqual(Frames.bcdVersion(0x0099), "0.9.9")
        XCTAssertEqual(Frames.bcdVersion(0x0910), "0.9.10")
        XCTAssertEqual(Frames.bcdVersion(0x0916), "0.9.16")
        XCTAssertEqual(Frames.bcdVersion(0x0917), "0.9.17")
        XCTAssertEqual(Frames.bcdVersion(0x0918), "0.9.18")
    }

    /// Bytes from the firmware's own hg_info_pack (fw/09_guardian/frozen/hg_frames.c @430c58b): fw 0x0917 / 0x0910,
    /// nn_crc 0xCA75CE41, boot 42, reset 2, twin saves 3, tag "ca75ce4".
    func testInfoFromFirmwarePacker() throws {
        let v17 = try XCTUnwrap(Frames.fromHex("02170941ce75ca2a000203006361373563653481"))
        let i = try Frames.decodeInfo(v17)
        XCTAssertEqual(i.fwVersion, 0x0917)
        XCTAssertEqual(i.fwText, "0.9.17")
        XCTAssertEqual(i.nnCRC, 0xCA75CE41)
        XCTAssertEqual(i.bootCount, 42)
        XCTAssertEqual(i.resetReason, 2)
        XCTAssertEqual(i.twinSaves, 3)
        XCTAssertEqual(i.hg2Tag, "ca75ce4")
        let v10 = try XCTUnwrap(Frames.fromHex("02100941ce75ca2a000203006361373563653457"))
        XCTAssertEqual(try Frames.decodeInfo(v10).fwText, "0.9.10")
        var bad = v17; bad[19] ^= 1
        XCTAssertThrowsError(try Frames.decodeInfo(bad))
        XCTAssertThrowsError(try Frames.decodeInfo(Array(v17.prefix(19))))
        XCTAssertThrowsError(try Frames.decodeInfo([]))
        // the connect help names the version the way the band does
        XCTAssertTrue(Strings(lang: .en).connectBody(0x0917).contains("fw 0.9.17"))
    }

    func testUrgentWritesJumpTheQueue() throws {
        XCTAssertTrue(Frames.isUrgentCommand(Frames.cmdTimeNow()))
        XCTAssertTrue(Frames.isUrgentCommand(Frames.cmdElderAction(.help)))
        XCTAssertTrue(Frames.isUrgentCommand(Frames.cmdElderAction(.helpCancel)))
        XCTAssertTrue(Frames.isUrgentCommand(Frames.cmdFamilyAck(type: 1, alarmId: 7)))
        XCTAssertTrue(Frames.isUrgentCommand(Frames.cmdFamilyMsg(2)))
        XCTAssertTrue(Frames.isUrgentCommand(Frames.cmdSyncEvents(sinceSeq: 3, boot: 4)))
        XCTAssertFalse(Frames.isUrgentCommand(Frames.cmdFamilyName("Ελένη")))
        XCTAssertFalse(Frames.isUrgentCommand(Frames.cmdVisit(.leave, place: .market, unix: 1_800_000_000)))
        XCTAssertFalse(Frames.isUrgentCommand(Frames.cmdDayPlanClear(day: 1)))
        XCTAssertFalse(Frames.isUrgentCommand(Frames.cmdProfile(field: 2, value: 70)))
        XCTAssertFalse(Frames.isUrgentCommand([]))
    }

    func testReplayedRingBeforeTheTowerIsHistoryOnly() {
        let since = Date(timeIntervalSince1970: 1_800_000_000)
        // no Tower yet: nothing is "before" it
        XCTAssertFalse(SMSRouter.predatesTower(eventAt: since.addingTimeInterval(-7200), clockKnown: true, towerSince: nil, firstLink: true))
        // a HELP from a bench test 2 h before the first connection: History only
        XCTAssertTrue(SMSRouter.predatesTower(eventAt: since.addingTimeInterval(-7200), clockKnown: true, towerSince: since, firstLink: true))
        // within a minute of the connection, or after it (also late, after an outage): routed as usual
        XCTAssertFalse(SMSRouter.predatesTower(eventAt: since.addingTimeInterval(-30), clockKnown: true, towerSince: since, firstLink: true))
        XCTAssertFalse(SMSRouter.predatesTower(eventAt: since.addingTimeInterval(86400), clockKnown: true, towerSince: since, firstLink: false))
        // no band clock: old only on the very first link
        XCTAssertTrue(SMSRouter.predatesTower(eventAt: since, clockKnown: false, towerSince: since, firstLink: true))
        XCTAssertFalse(SMSRouter.predatesTower(eventAt: since, clockKnown: false, towerSince: since, firstLink: false))
    }

    /// A newer band (unknown types, unknown args, a new version byte, trailing bytes) or radio garbage never crashes
    /// the parsers; unknown types never become rows but still move the SYNC cursor.
    func testNewerOrBrokenFramesNeverCrash() {
        var rng = SystemRandomNumberGenerator()
        for n in [0, 1, 7, 19, 20, 21, 40] {
            for _ in 0..<300 {
                var b = (0..<n).map { _ in UInt8.random(in: 0...255, using: &rng) }
                if n >= 20 { b[19] = Frames.crc8(b, count: 19) }        // CRC-valid garbage too
                _ = try? Frames.decodeStatus(b)
                _ = try? Frames.decodeInfo(b)
                if let e = try? Frames.decodeEvent(b) {
                    _ = LogEntry.fromBand(e, receivedAt: Date())
                    _ = e.ladder; _ = e.gauge; _ = e.visit; _ = e.planItem; _ = e.alertHeld; _ = e.allClear; _ = e.scorePage
                }
            }
        }
        // every type 0-255 with every arg in a CRC-valid frame
        let store = EventStore(fileName: nil)
        var seq = 0
        for t in 0...255 {
            for a in [0, 1, 2, 3, 4, 9, 0x7F, 0xFF] {
                seq += 1
                let ev = BandEvent(seq: seq, boot: 9, unix: 1_800_000_000, kindRaw: t, arg: a,
                                   ext: [0xFF, 0x7F, 0x00, 0x80, 0xFF, 0xFF, 0x01, 0xFE])
                guard let back = try? Frames.decodeEvent(Frames.encodeEvent(ev)) else { return XCTFail("round trip \(t)") }
                if let e = store.addBand(back, receivedAt: Date()) {
                    _ = e.ladder; _ = e.visit; _ = e.planItem; _ = e.alertHeld; _ = e.allClear; _ = e.scorePage; _ = e.warnState
                }
            }
        }
        XCTAssertEqual(store.cursorBoot, 9)
        XCTAssertEqual(store.cursorSeq, seq)
        _ = Timeline.items(store.entries, day: Date(timeIntervalSince1970: 1_800_000_000))
        // a future frame version is rejected, not misread
        var v4 = Frames.encodeEvent(BandEvent(seq: 1, boot: 1, unix: 0, kindRaw: 5, arg: 1))
        v4[0] = 0x04; v4[19] = Frames.crc8(v4, count: 19)
        XCTAssertThrowsError(try Frames.decodeEvent(v4))
    }

    /// 0.9.17 types the band sends in this build, in its own byte layout, end up as History entries the Tower reads.
    func testBand0917EventsReachHistoryAndTower() throws {
        let store = EventStore(fileName: nil)
        // POWER_OFF by the wearer (double press + confirm) and over USB: x = 0
        for (seq, arg) in [(1, 1), (2, 2)] {
            let f = Frames.encodeEvent(BandEvent(seq: seq, boot: 3, unix: 1_800_000_000, kindRaw: 14, arg: arg, ext: [UInt8](repeating: 0, count: 8)))
            let e = try XCTUnwrap(store.addBand(try Frames.decodeEvent(f), receivedAt: Date()))
            XCTAssertEqual(e.kind, .powerOff)
            XCTAssertEqual(e.ladder, .powerOff(byWearer: arg == 1))
        }
        // HAPTIC_LOST pattern 5
        let h = Frames.encodeEvent(BandEvent(seq: 3, boot: 3, unix: 1_800_000_060, kindRaw: 16, arg: 5, ext: [UInt8](repeating: 0, count: 8)))
        XCTAssertEqual(try XCTUnwrap(store.addBand(try Frames.decodeEvent(h), receivedAt: Date())).ladder, .hapticLost(pattern: 5))
        // HELP from the band button (arg 1) and from the phone (arg 2)
        for (seq, arg) in [(4, 1), (5, 2)] {
            let f = Frames.encodeEvent(BandEvent(seq: seq, boot: 3, unix: 1_800_000_120, kindRaw: 5, arg: arg))
            XCTAssertEqual(try XCTUnwrap(store.addBand(try Frames.decodeEvent(f), receivedAt: Date())).kind, .help)
        }
        // a band reboot (boot 4) starts the cursor again
        let r = Frames.encodeEvent(BandEvent(seq: 1, boot: 4, unix: 0, kindRaw: 4, arg: 1))
        let e = try XCTUnwrap(store.addBand(try Frames.decodeEvent(r), receivedAt: Date(timeIntervalSince1970: 1_800_000_500)))
        XCTAssertFalse(e.clockKnown)
        XCTAssertEqual(e.at, Date(timeIntervalSince1970: 1_800_000_500))
        XCTAssertEqual(store.cursorBoot, 4)
        XCTAssertEqual(store.cursorSeq, 1)
        XCTAssertEqual(Frames.toHex(Frames.cmdSyncEvents(sinceSeq: store.cursorSeq, boot: store.cursorBoot ?? 0xFFFF)).prefix(10), "1601000400")
    }
}
