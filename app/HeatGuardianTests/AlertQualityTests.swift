// XCTest for band 0.9.9 alert quality (ECOSYSTEM_SPEC 5e): EVENTS 11 ALERT_HELD / 12 ALL_CLEAR / 13 SCORE against
// the firmware's own packers (alert_vectors_fw.json, made by tools/fw_alert_vectors.c), unknown types ignored, the
// «Back to normal» row and status, and the Alert quality week (scorecard per boot + log tail).
// ios/tools/linux_xctest/run.sh runs this file on Linux.

import XCTest
@testable import HeatGuardian

final class AlertQualityTests: XCTestCase {
    private func int(_ v: Any?) -> Int? { (v as? NSNumber)?.intValue }

    func testFirmwareVectors() throws {
        let url = try XCTUnwrap(Bundle(for: AlertQualityTests.self).url(forResource: "alert_vectors_fw", withExtension: "json"))
        let f = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        var n = 0
        for v in try XCTUnwrap(f["events"] as? [[String: Any]]) {
            let hex = try XCTUnwrap(v["hex"] as? String)
            let e = try Frames.decodeEvent(try XCTUnwrap(Frames.fromHex(hex)))
            XCTAssertEqual(e.seq, int(v["seq"])); XCTAssertEqual(e.boot, int(v["boot"])); XCTAssertEqual(e.arg, int(v["arg"]))
            XCTAssertEqual(Frames.toHex(Frames.encodeEvent(e)), hex)
            let entry = try XCTUnwrap(LogEntry.fromBand(e, receivedAt: Date()))
            XCTAssertEqual(entry.boot, int(v["boot"]))
            switch int(v["type"]) {
            case 11:
                let h = try XCTUnwrap(e.alertHeld, hex)
                XCTAssertEqual(h.what.rawValue, int(v["what"])); XCTAssertEqual(h.reason.rawValue, int(v["reason"])); XCTAssertEqual(h.arg, int(v["held_arg"]))
                XCTAssertEqual(entry.kind, .alertHeld); XCTAssertEqual(entry.alertHeld, h)
                XCTAssertEqual(Frames.toHex(Frames.encodeEvent(Frames.alertHeldEvent(seq: e.seq, boot: e.boot, unix: e.unix, h))), hex)
            case 12:
                let c = try XCTUnwrap(e.allClear, hex)
                XCTAssertEqual(c.peak, int(v["peak"])); XCTAssertEqual(c.minutes, int(v["minutes"]))
                XCTAssertEqual(c.familyCalled, int(v["family"]) == 1); XCTAssertEqual(c.softTick, int(v["tick"]) == 1)
                XCTAssertEqual(entry.kind, .allClear); XCTAssertEqual(entry.allClear, c)
                XCTAssertEqual(Frames.toHex(Frames.encodeEvent(Frames.allClearEvent(seq: e.seq, boot: e.boot, unix: e.unix, c))), hex)
            default:
                let p = try XCTUnwrap(e.scorePage, hex)
                XCTAssertEqual(p.page, int(v["page"])); XCTAssertEqual(p.values, v["x"] as? [Int])
                XCTAssertEqual(entry.kind, .score)
                XCTAssertEqual(Frames.toHex(Frames.encodeEvent(Frames.scoreEvent(seq: e.seq, boot: e.boot, unix: e.unix, p))), hex)
            }
            n += 1
        }
        XCTAssertEqual(n, 18)
        // the three SCORE pages of the vector file make one snapshot
        let entries = try (f["events"] as! [[String: Any]]).compactMap { v -> LogEntry? in
            LogEntry.fromBand(try Frames.decodeEvent(Frames.fromHex(v["hex"] as! String)!), receivedAt: Date())
        }
        let s = try XCTUnwrap(AlertQuality.snapshots(entries).first)
        XCTAssertEqual(s.pages, [0, 1, 2])
        XCTAssertEqual(s.sent, [14, 3, 1, 2, 1, 0, 2, 255])      // BEDTIME 300 saturates at 255 on the band
        XCTAssertEqual(s.held[9], 18); XCTAssertEqual(s.held[1], 2); XCTAssertEqual(s.held[8], 16)
        XCTAssertEqual(s.ack, 12); XCTAssertEqual(s.missed, 3); XCTAssertEqual(s.avgAckSeconds, 97); XCTAssertEqual(s.maxAckSeconds, 412)
    }

    func testUnknownTypesIgnored() throws {
        for t in [24, 99, 255] {                                 // 14-23 are band 0.9.17-0.9.18 types now (TowerTests)
            let ev = BandEvent(seq: 5, boot: 1, unix: 1789460000, kindRaw: t, arg: 1, ext: [1, 2, 3, 4, 5, 6, 7, 8])
            let back = try Frames.decodeEvent(Frames.encodeEvent(ev))
            XCTAssertNil(back.kind)
            XCTAssertNil(LogEntry.fromBand(back, receivedAt: Date()))
            let st = EventStore(fileName: nil)
            XCTAssertNil(st.addBand(back, receivedAt: Date()))
            XCTAssertEqual(st.cursorSeq, 5)                       // the cursor still moves past it
        }
        // known types with values the app does not know decode to nil fields, never a crash
        let odd = BandEvent(seq: 1, boot: 1, unix: 1, kindRaw: 11, arg: 9, ext: [42, 0, 0, 0, 0, 0, 0, 0])
        XCTAssertNil(odd.alertHeld)
        XCTAssertNil(BandEvent(seq: 1, boot: 1, unix: 1, kindRaw: 13, arg: 3, ext: []).scorePage)
    }

    private func entry(_ ev: BandEvent) -> LogEntry {
        LogEntry.fromBand(try! Frames.decodeEvent(Frames.encodeEvent(ev)), receivedAt: Date())!
    }

    func testBackToNormalRowAndStatus() {
        let d0 = Calendar.current.startOfDay(for: Date())
        func u(_ m: Int) -> UInt32 { UInt32(d0.timeIntervalSince1970) + UInt32(m * 60) }
        let warn = entry(BandEvent(seq: 1, boot: 2, unix: u(14 * 60), kindRaw: 8, arg: 2))
        let clear = entry(Frames.allClearEvent(seq: 2, boot: 2, unix: u(14 * 60 + 42), AllClear(peak: 2, minutes: 42, familyCalled: false, softTick: true)))
        let held = entry(Frames.alertHeldEvent(seq: 3, boot: 2, unix: u(15 * 60), AlertHeld(what: .drink, reason: .persist, arg: 1)))
        let es = [warn, clear, held]
        let items = Timeline.items(es, day: d0)
        XCTAssertEqual(items.count, 2)                             // ALERT_HELD is not a log row
        XCTAssertEqual(items.last?.kind, .allClear(minutes: 42, familyCalled: false))
        let rows = LogRows.rows(items, L: Strings(lang: .en), familyName: "", briefHour: nil, locale: Locale(identifier: "en_GB"))
        XCTAssertEqual(rows.last?.title, "Back to normal")
        XCTAssertEqual(rows.last?.tone, .ok)
        XCTAssertEqual(LogRows.rows(items, L: Strings(lang: .el), familyName: "", briefHour: nil, locale: Locale(identifier: "el_GR")).last?.title, "Πάλι όλα καλά")
        // quiet status for 2 h, gone after a new warning
        XCTAssertEqual(AlertQuality.backToNormal(es, now: d0.addingTimeInterval(15.5 * 3600))?.clear.minutes, 42)
        XCTAssertNil(AlertQuality.backToNormal(es, now: d0.addingTimeInterval(17 * 3600)))
        let again = entry(BandEvent(seq: 4, boot: 2, unix: u(15 * 60 + 10), kindRaw: 8, arg: 1))
        XCTAssertNil(AlertQuality.backToNormal(es + [again], now: d0.addingTimeInterval(15.5 * 3600)))
        // ALERT_HELD / SCORE alone do not make a History day
        let st = EventStore(fileName: nil)
        st.add(held)
        st.add(entry(Frames.scoreEvent(seq: 9, boot: 2, unix: u(1), ScorePage(page: 0, values: [1, 0, 0, 0, 0, 0, 0, 0]))))
        XCTAssertTrue(st.days.isEmpty)
        st.add(clear)
        XCTAssertEqual(st.days.count, 1)
    }

    func testWeekFromScorecardAndLog() {
        let cal = Calendar.current
        let now = cal.startOfDay(for: Date()).addingTimeInterval(13 * 3600)
        let d0 = cal.startOfDay(for: now)
        var seq = 0
        var es: [LogEntry] = []
        func snap(_ day: Int, boot: Int, sent: [Int], held: [Int], ack: Int, missed: Int, oneEv: Int = 0) {
            let t = cal.date(byAdding: .day, value: day, to: d0)!.addingTimeInterval(15)    // just after midnight
            let u = UInt32(t.timeIntervalSince1970)
            for (pg, v) in [(0, sent), (1, held), (2, [oneEv, ack, missed, 0, 90, 0, 200, 0])] {
                seq += 1
                es.append(entry(Frames.scoreEvent(seq: seq, boot: boot, unix: u, ScorePage(page: pg, values: v))))
            }
        }
        // boot 4: before the week (the midnight that opens day -6 closes day -7), then two days later
        snap(-6, boot: 4, sent: [5, 1, 0, 0, 0, 0, 1, 1], held: [1, 0, 0, 0, 1, 0, 2, 0], ack: 4, missed: 1)
        snap(-4, boot: 4, sent: [9, 2, 1, 0, 0, 0, 2, 3], held: [1, 0, 0, 1, 2, 0, 4, 1], ack: 8, missed: 2, oneEv: 1)
        // the band restarted: boot 5 counts from 0
        snap(-1, boot: 5, sent: [3, 0, 0, 0, 1, 0, 0, 1], held: [0, 0, 0, 0, 1, 1, 1, 0], ack: 3, missed: 1)
        snap(0, boot: 5, sent: [6, 1, 0, 0, 1, 0, 1, 2], held: [0, 0, 0, 0, 2, 1, 2, 0], ack: 6, missed: 2)
        // today after the midnight snapshot: from the log
        func u(_ m: Int) -> UInt32 { UInt32(d0.timeIntervalSince1970) + UInt32(m * 60) }
        es.append(entry(BandEvent(seq: 100, boot: 5, unix: u(600), kindRaw: 1, arg: 4)))
        es.append(entry(BandEvent(seq: 101, boot: 5, unix: u(604), kindRaw: 2, arg: 4)))
        es.append(entry(Frames.alertHeldEvent(seq: 102, boot: 5, unix: u(650), AlertHeld(what: .drink, reason: .shower, arg: 1))))
        es.append(entry(BandEvent(seq: 103, boot: 5, unix: u(700), kindRaw: 8, arg: 1)))
        es.append(entry(BandEvent(seq: 104, boot: 5, unix: u(14 * 60), kindRaw: 1, arg: 4)))    // after `now`: not counted
        let w = AlertQuality.week(es, now: now)
        XCTAssertEqual(w.source, .scorecard)
        // boot 4: (9+2+1+0+0+0+3) - (5+1+0+0+0+0+1) = 15 - 7 = 8; boot 5: 6+1+0+0+1+0+2 = 10; log: 2
        XCTAssertEqual(w.sent, 8 + 10 + 2)
        XCTAssertEqual(w.held[.ppg], 1)
        XCTAssertEqual(w.held[.shower], 1 + 2 + 1)
        XCTAssertEqual(w.held[.sun], 1)
        XCTAssertEqual(w.held[.persist], 2 + 2)
        XCTAssertEqual(w.held[.repeated], 1)
        XCTAssertEqual(w.held[.oneEvidence], 1)
        XCTAssertEqual(w.acknowledged, 4 + 6 + 1)
        XCTAssertEqual(w.missed, 1 + 2)
        XCTAssertEqual(w.heldSorted.first?.0, .shower)
        // no scorecard (band 0.9.8): the log alone
        let logOnly = es.filter { $0.kind != .score }
        let w2 = AlertQuality.week(logOnly, now: now)
        XCTAssertEqual(w2.source, .log)
        XCTAssertEqual(w2.sent, 2); XCTAssertEqual(w2.heldTotal, 1); XCTAssertEqual(w2.acknowledged, 1)
        XCTAssertEqual(AlertQuality.week([], now: now).source, .none)
        // plain words exist for every reason, in both languages
        for r in HeldReason.allCases {
            XCTAssertFalse(Strings(lang: .en).heldReason(r).isEmpty)
            XCTAssertNotEqual(Strings(lang: .el).heldReason(r), Strings(lang: .en).heldReason(r))
        }
    }
}
