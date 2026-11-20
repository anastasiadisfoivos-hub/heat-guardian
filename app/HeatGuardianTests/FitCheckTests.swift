// XCTest for the FIT CHECK: STATUS bytes packed exactly as the band's frozen hg_status_pack() (fw/09_guardian/frozen/
// hg_frames.c: byte 0 bit 5 not_worn, byte 1 bit 3 contact_ok, byte 1 bit 5 charging, CRC-8 at 19) go through the
// app's real decoder and then FitCheck.state; plus the auto-show rule and the filming mock's script.

import XCTest
@testable import HeatGuardian

final class FitCheckTests: XCTestCase {
    let t0 = Date(timeIntervalSince1970: 1_795_421_520)

    /// hg_status_pack() for the bits that matter here (everything else 0, as memset there).
    func status(contactOK: Bool, notWorn: Bool, charging: Bool) throws -> StatusFrame {
        var b = [UInt8](repeating: 0, count: 20)
        b[0] = 0x01 | (notWorn ? 0x20 : 0)
        b[1] = (contactOK ? 8 : 0) | (charging ? 32 : 0)
        b[19] = Frames.crc8(b, count: 19)
        return try Frames.decodeStatus(b)
    }

    func testBitsDecode() throws {
        let d = try status(contactOK: true, notWorn: false, charging: false)
        XCTAssertTrue(d.contactOK); XCTAssertFalse(d.notWorn); XCTAssertFalse(d.charging)
        let c = try status(contactOK: false, notWorn: true, charging: true)
        XCTAssertFalse(c.contactOK); XCTAssertTrue(c.notWorn); XCTAssertTrue(c.charging)
    }

    func testVerdicts() throws {
        let start = t0, late = t0.addingTimeInterval(FitCheck.window + 5), early = t0.addingTimeInterval(60)
        func st(_ ok: Bool, _ nw: Bool, _ ch: Bool, now: Date, frameAt: Date? = nil, connected: Bool = true) throws -> FitState {
            FitCheck.state(frame: try status(contactOK: ok, notWorn: nw, charging: ch), frameAt: frameAt ?? now.addingTimeInterval(-5),
                           connected: connected, startedAt: start, now: now)
        }
        XCTAssertEqual(try st(true, false, false, now: early), .ok)            // OK shows at once
        XCTAssertEqual(try st(false, false, true, now: early), .charging)      // charging at once (always reads not worn)
        XCTAssertEqual(try st(false, true, true, now: late), .charging)        // charging wins over not_worn
        XCTAssertEqual(try st(false, false, false, now: early), .checking)     // band still deciding (2-min hysteresis)
        XCTAssertEqual(try st(false, true, false, now: early), .checking)
        XCTAssertEqual(try st(false, false, false, now: late), .loose)         // not good, not called off -> tighten
        XCTAssertEqual(try st(false, true, false, now: late), .off)            // band's NOT_WORN
        XCTAssertEqual(try st(true, false, false, now: late, connected: false), .noLink)
        // a frame from before the check started never gives the "not good" verdict
        XCTAssertEqual(try st(false, false, false, now: late, frameAt: start.addingTimeInterval(-10)), .checking)
        // a stale frame is not "now"
        XCTAssertEqual(try st(true, false, false, now: late, frameAt: late.addingTimeInterval(-FitCheck.fresh - 1)), .checking)
        XCTAssertEqual(FitCheck.state(frame: nil, frameAt: nil, connected: true, startedAt: start, now: late), .checking)
    }

    func testAutoShow() throws {
        let loose = try status(contactOK: false, notWorn: false, charging: false)
        XCTAssertTrue(FitCheck.shouldAutoShow(frame: loose, okShownAt: nil, now: t0))
        XCTAssertFalse(FitCheck.shouldAutoShow(frame: try status(contactOK: true, notWorn: false, charging: false), okShownAt: nil, now: t0))
        XCTAssertFalse(FitCheck.shouldAutoShow(frame: try status(contactOK: false, notWorn: true, charging: true), okShownAt: nil, now: t0))
        XCTAssertFalse(FitCheck.shouldAutoShow(frame: loose, okShownAt: t0.addingTimeInterval(-3600), now: t0))   // no nagging
        XCTAssertTrue(FitCheck.shouldAutoShow(frame: loose, okShownAt: t0.addingTimeInterval(-13 * 3600), now: t0))
        XCTAssertFalse(FitCheck.shouldAutoShow(frame: nil, okShownAt: nil, now: t0))
    }

    func testMockScript() {
        XCTAssertEqual(FitCheckMock.state(round: 0, elapsed: 2), .checking)
        XCTAssertEqual(FitCheckMock.state(round: 0, elapsed: 11), .loose)
        XCTAssertEqual(FitCheckMock.state(round: 1, elapsed: 3), .checking)
        XCTAssertEqual(FitCheckMock.state(round: 1, elapsed: 11), .ok)
        XCTAssertEqual(FitCheck.progress(elapsed: 5, mock: true), 0.5, accuracy: 1e-9)
        XCTAssertEqual(FitCheck.progress(elapsed: 999, mock: false), 1)
    }

    func testGreekTexts() {
        let L = Strings(lang: .el)
        XCTAssertEqual(L.fitTitle(.checking), "Ελέγχουμε την εφαρμογή…")
        XCTAssertEqual(L.fitTitle(.ok), "Εφαρμογή OK ✓")
        XCTAssertEqual(L.fitTitle(.loose), "Σφίξτε λίγο το λουράκι")
        XCTAssertEqual(L.fitTitle(.off), "Το βραχιόλι δεν φοριέται")
        XCTAssertEqual(L.fitTitle(.charging), "Φορτίζει — αποσυνδέστε για έλεγχο")
        for s in FitState.allCases { XCTAssertFalse(L.fitLine(s).isEmpty) }
    }
}
