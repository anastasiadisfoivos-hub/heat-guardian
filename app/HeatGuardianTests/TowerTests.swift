// XCTest for THE TOWER (owner decision Nov 19): the 0.9.17 ladder EVENTS decoder against the band's own bytes
// (ladder_vectors_fw.json, tools/fw_ladder_vectors.c), unknown-type tolerance, SMS texts (Greek / English), the
// event -> SMS routing table, the outbox state machine (queue, retry + backoff, dedupe, rate limit, expiry), the Twilio
// request (URL, form body, Basic auth) and the engine with a FAKE HTTP client. No network call anywhere.

import XCTest
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif
@testable import HeatGuardian

final class FakeHTTP: HTTPClient {
    var requests: [URLRequest] = []
    var replies: [(Int?, String?, Error?)] = []        // consumed in order; empty -> 201
    func perform(_ request: URLRequest, completion: @escaping (Int?, Data?, Error?) -> Void) {
        requests.append(request)
        let r = replies.isEmpty ? (201, "{\"sid\":\"SM00000000000000000000000000000001\",\"status\":\"queued\"}", nil) : replies.removeFirst()
        completion(r.0, r.1.map { Data($0.utf8) }, r.2)
    }
}

final class TowerTests: XCTestCase {
    let utc = TimeZone(identifier: "UTC")!
    let t0 = Date(timeIntervalSince1970: 1_784_293_200)       // 2026-07-17 13:00 UTC
    // test-only fake credentials (not a real account): AC + 32 hex, 32-char token, a reserved test number
    let creds = TwilioCredentials(accountSID: "AC" + String(repeating: "0", count: 31) + "1",
                                  authToken: String(repeating: "f", count: 32), fromNumber: "+15005550006")

    // MARK: ladder EVENTS vs the band's bytes

    struct Vec: Decodable { var scenario: String; var minute: Int; var type: Int; var seq: Int; var boot: Int; var unix: UInt32; var arg: Int; var x: [UInt8]; var hex: String }

    func vectors() throws -> [Vec] {
        let url = Bundle(for: TowerTests.self).url(forResource: "ladder_vectors_fw", withExtension: "json")
            ?? URL(fileURLWithPath: "ladder_vectors_fw.json")
        return try JSONDecoder().decode([Vec].self, from: Data(contentsOf: url))
    }
    func bytes(_ hex: String) -> [UInt8] {
        var out: [UInt8] = []; var i = hex.startIndex
        while i < hex.endIndex { let j = hex.index(i, offsetBy: 2); out.append(UInt8(hex[i..<j], radix: 16)!); i = j }
        return out
    }

    func testLadderVectorsDecodeAndReencodeByteForByte() throws {
        let vs = try vectors()
        XCTAssertGreaterThanOrEqual(vs.count, 15)
        for v in vs {
            let e = try Frames.decodeEvent(bytes(v.hex))
            XCTAssertEqual(e.kindRaw, v.type); XCTAssertEqual(e.arg, v.arg); XCTAssertEqual(e.seq, v.seq); XCTAssertEqual(e.boot, v.boot)
            XCTAssertEqual(e.ext, v.x)
            let l = try XCTUnwrap(e.ladder, "\(v.scenario) type \(v.type)")
            let enc = l.encoded
            XCTAssertEqual(enc.type, v.type); XCTAssertEqual(enc.arg, v.arg)
            XCTAssertEqual(enc.x, v.x, "\(v.scenario) type \(v.type) x")
            let back = Frames.encodeEvent(BandEvent(seq: v.seq, boot: v.boot, unix: v.unix, kindRaw: enc.type, arg: enc.arg, ext: enc.x))
            XCTAssertEqual(Frames.toHex(back).replacingOccurrences(of: " ", with: "").lowercased(), v.hex, "\(v.scenario) re-encode")
            XCTAssertNotNil(LogEntry.fromBand(e, receivedAt: t0)?.ladder)
        }
    }

    func testLadderScenarioMeaning() throws {
        let b = try vectors().filter { $0.scenario == "water_failed_cool_failed" }.map { try Frames.decodeEvent(bytes($0.hex)).ladder! }
        XCTAssertEqual(b[0], .reminder(step: .water, isRepeat: false, forecastC: 37.90))
        XCTAssertEqual(b[1], .done(step: .water, minutesAfterReminder: 1, forecastC: 37.92))
        guard case .note(.waterDidNotHelp, let about, _, let ref) = b[2] else { return XCTFail("\(b[2])") }
        XCTAssertEqual(about, .water); XCTAssertEqual(ref, 37.92)
        XCTAssertEqual(b[3], .reminder(step: .coolerPlace, isRepeat: false, forecastC: 38.12))
        guard case .escalated(.stillHeating, _, _) = b[5] else { return XCTFail("\(b[5])") }
        guard case .note(.responsive, .escalation?, _, _) = b[6] else { return XCTFail("\(b[6])") }
        guard case .worked(.escalation, _, _) = b[7] else { return XCTFail("\(b[7])") }
        let n = try vectors().filter { $0.scenario == "no_response" }.map { try Frames.decodeEvent(bytes($0.hex)).ladder! }
        XCTAssertEqual(n[1], .reminder(step: .coolerPlace, isRepeat: true, forecastC: 38.00))
        guard case .note(.noResponse, .coolerPlace?, _, nil) = n[2] else { return XCTFail("\(n[2])") }
        let d = try vectors().filter { $0.scenario == "danger" }.map { try Frames.decodeEvent(bytes($0.hex)).ladder! }
        guard case .escalated(.dangerLine, let f, nil) = d[0] else { return XCTFail("\(d[0])") }
        XCTAssertEqual(f, 38.50)
        let o = try vectors().filter { $0.scenario == "other" }.map { try Frames.decodeEvent(bytes($0.hex)).ladder! }
        XCTAssertEqual(o, [.powerOff(byWearer: true), .hapticLost(pattern: 3)])
    }

    func testUnknownTypesAndArgsAreIgnoredAndLogged() {
        let diag = BandEventDiagnostics.shared
        diag.reset()
        var lines: [String] = []
        diag.log = { lines.append($0) }
        defer { diag.log = { print("[HG] " + $0) }; diag.reset() }
        for (type, arg) in [(99, 1), (99, 2), (21, 9), (17, 3)] {
            let f = Frames.encodeEvent(BandEvent(seq: 5, boot: 1, unix: 1_784_293_200, kindRaw: type, arg: arg, ext: []))
            let e = try! Frames.decodeEvent(f)
            XCTAssertNil(LogEntry.fromBand(e, receivedAt: t0), "type \(type) arg \(arg)")
        }
        XCTAssertEqual(diag.unknownTypes[99], 2)
        XCTAssertEqual(diag.unknownArgs["21/9"], 1)
        XCTAssertEqual(diag.unknownArgs["17/3"], 1)
        XCTAssertEqual(lines.count, 3)                     // one line per new (type) / (type, arg), not per frame
        // a store fed an unknown type still advances its SYNC cursor and adds no row
        let st = EventStore(fileName: nil)
        XCTAssertNil(st.addBand(BandEvent(seq: 9, boot: 1, unix: 1_784_293_200, kindRaw: 77, arg: 0), receivedAt: t0))
        XCTAssertEqual(st.cursorSeq, 9); XCTAssertTrue(st.entries.isEmpty)
    }

    // MARK: SMS texts

    func testSMSTextsGreekAndEnglish() {
        let at = t0.addingTimeInterval(52 * 60)        // 13:52 UTC
        func el(_ k: SMSKind) -> String { SMSText.body(k, name: "Μαρία", lang: .el, timeZone: utc) }
        func en(_ k: SMSKind) -> String { SMSText.body(k, name: "Maria", lang: .en, timeZone: utc) }
        XCTAssertEqual(el(.escalatedStillHeating(at: at, afterWater: true)),
                       "Μαρία: το νερό δεν βοήθησε, πήγε σε πιο δροσερό μέρος. Συνεχίζει να ζεσταίνεται (13:52). Τηλεφωνήστε της τώρα.")
        XCTAssertEqual(el(.help(at: at)), "Μαρία: ΖΗΤΗΣΕ ΒΟΗΘΕΙΑ από το βραχιόλι στις 13:52. Τηλεφωνήστε της τώρα.")
        XCTAssertEqual(el(.escalatedDanger(at: at)), "Μαρία: ΚΙΝΔΥΝΟΣ από τη ζέστη στις 13:52. Το σώμα της ζεσταίνεται πολύ. Τηλεφωνήστε της τώρα.")
        XCTAssertEqual(el(.waterDidNotHelp(at: at)), "Μαρία: το νερό δεν βοήθησε (13:52). Το βραχιόλι της είπε να πάει σε πιο δροσερό μέρος.")
        XCTAssertEqual(el(.responsive(at: at)), "Μαρία: πάτησε το κουμπί στις 13:52, σας βλέπει. Η ζέστη συνεχίζεται: η ειδοποίηση μένει.")
        XCTAssertEqual(en(.help(at: at)), "Maria: ASKED FOR HELP on the band at 13:52. Call her now.")
        XCTAssertEqual(el(.batteryEnded(at: at)), "Μαρία: η μπαταρία του βραχιολιού τελείωσε (13:52). Δεν προστατεύεται μέχρι να φορτιστεί.")
        XCTAssertEqual(en(.batteryEnded(at: at)), "Maria: the band's battery ran out (13:52). She is not protected until it is charged.")
        XCTAssertEqual(en(.escalatedStillHeating(at: at, afterWater: true)),
                       "Maria: water did not help, she moved somewhere cooler. She is still heating up (13:52). Call her now.")
        XCTAssertEqual(en(.noResponse(step: .coolerPlace, at: at)),
                       "Maria: did not respond to the reminder to move somewhere cooler (13:52). Maybe give her a call.")
        // every Greek text has a reason and fits in 2 UCS-2 parts; English fits in 1 GSM-7 part
        let kinds: [SMSKind] = [.help(at: at), .helpCancelled(at: at), .escalatedDanger(at: at), .escalatedStillHeating(at: at, afterWater: true),
                                .escalatedStillHeating(at: at, afterWater: false), .noAnswer(at: at), .waterDidNotHelp(at: at),
                                .noResponse(step: .water, at: at), .responsive(at: at), .settled(at: at), .bandDisconnected(minutes: 60),
                                .batteryEnded(at: at), .test]
        for k in kinds {
            let g = SMSText.segments(el(k)), e = SMSText.segments(en(k))
            XCTAssertTrue(g.ucs2); XCTAssertLessThanOrEqual(g.count, 2, el(k))
            XCTAssertFalse(e.ucs2, en(k)); XCTAssertLessThanOrEqual(e.count, 1, en(k))
            XCTAssertTrue(el(k).hasPrefix("Μαρία:") || el(k).hasPrefix("Heat Guardian:"))
        }
        XCTAssertEqual(SMSText.segments(String(repeating: "α", count: 70)).count, 1)
        XCTAssertEqual(SMSText.segments(String(repeating: "α", count: 71)).count, 2)
        XCTAssertEqual(SMSText.segments(String(repeating: "a", count: 161)).count, 2)
    }

    func testPhoneNumbers() {
        XCTAssertEqual(PhoneNumber.e164("+30 691 234 5678", defaultCountryCode: "30"), "+306912345678")
        XCTAssertEqual(PhoneNumber.e164("0030 6912345678", defaultCountryCode: "30"), "+306912345678")
        XCTAssertEqual(PhoneNumber.e164("691-234-5678", defaultCountryCode: "30"), "+306912345678")
        XCTAssertEqual(PhoneNumber.e164("07700 900123", defaultCountryCode: "44"), "+447700900123")
        XCTAssertNil(PhoneNumber.e164("12345", defaultCountryCode: "30"))
        XCTAssertNil(PhoneNumber.e164("call me", defaultCountryCode: "30"))
        XCTAssertEqual(PhoneNumber.masked("+306912345678"), "+30 •••• 5678")
        XCTAssertTrue(PhoneNumber.looksLikeEmail("a@example.com")); XCTAssertFalse(PhoneNumber.looksLikeEmail("a@b"))
    }

    // MARK: routing table

    func testRoutingTable() {
        var p = TowerPrefs()
        var m = TowerMemory()
        let at = t0
        func d(_ i: TowerInput) -> TowerDecision { SMSRouter.decide(i, prefs: p, memory: &m) }
        func isSMS(_ x: TowerDecision, _ prio: SMSPriority, _ key: String) -> Bool {
            if case .sms(_, let pr, let k) = x { return pr == prio && k == key }; return false
        }
        XCTAssertTrue(isSMS(d(.help(at: at)), .urgent, "help"))
        XCTAssertTrue(isSMS(d(.helpCancel(at: at.addingTimeInterval(120))), .followUp, "help-cancel"))
        XCTAssertEqual(d(.helpCancel(at: at.addingTimeInterval(240))), .inApp(reason: "help-cancel-no-help-sms"))   // no second cancel SMS
        XCTAssertTrue(isSMS(d(.ladder(.escalated(reason: .dangerLine, forecastC: 38.5, referenceC: nil), at: at)), .urgent, "escalation"))
        XCTAssertTrue(isSMS(d(.familyAlertNoAnswer(at: at)), .urgent, "escalation"))
        // water note -> SMS (notes on by default) and the escalation that follows says "water did not help"
        XCTAssertTrue(isSMS(d(.ladder(.note(.waterDidNotHelp, about: .water, forecastC: nil, referenceC: nil), at: at)), .note, "note-water"))
        if case .sms(let k, _, _) = d(.ladder(.escalated(reason: .stillHeating, forecastC: nil, referenceC: nil), at: at.addingTimeInterval(25 * 60))) {
            XCTAssertEqual(k, .escalatedStillHeating(at: at.addingTimeInterval(25 * 60), afterWater: true))
        } else { XCTFail() }
        XCTAssertTrue(isSMS(d(.ladder(.note(.responsive, about: .escalation, forecastC: nil, referenceC: nil), at: at)), .followUp, "responsive"))
        XCTAssertTrue(isSMS(d(.ladder(.worked(step: .escalation, forecastC: nil, referenceC: nil), at: at.addingTimeInterval(1800))), .followUp, "settled"))
        XCTAssertTrue(isSMS(d(.ladder(.note(.noResponse, about: .water, forecastC: nil, referenceC: nil), at: at)), .note, "note-noresponse"))
        // in-app only
        XCTAssertEqual(d(.ladder(.reminder(step: .water, isRepeat: false, forecastC: nil), at: at)), .inApp(reason: "reminder"))
        XCTAssertEqual(d(.ladder(.done(step: .water, minutesAfterReminder: 3, forecastC: nil), at: at)), .inApp(reason: "done"))
        XCTAssertEqual(d(.ladder(.worked(step: .water, forecastC: nil, referenceC: nil), at: at)), .inApp(reason: "worked"))
        XCTAssertEqual(d(.ladder(.powerOff(byWearer: true), at: at)), .inApp(reason: "band-status"))
        XCTAssertEqual(d(.bandDisconnected(since: at, now: at.addingTimeInterval(3 * 3600))), .inApp(reason: "disconnect-sms-off"))
        // a worked-after-escalation long after any urgent SMS stays in the app
        var m2 = TowerMemory()
        XCTAssertEqual(SMSRouter.decide(.ladder(.worked(step: .escalation, forecastC: nil, referenceC: nil), at: at), prefs: p, memory: &m2), .inApp(reason: "worked"))
        // notes by SMS off
        p.notesBySMS = false
        XCTAssertEqual(d(.ladder(.note(.waterDidNotHelp, about: .water, forecastC: nil, referenceC: nil), at: at)), .inApp(reason: "notes-by-sms-off"))
        XCTAssertEqual(d(.ladder(.note(.noResponse, about: .water, forecastC: nil, referenceC: nil), at: at)), .inApp(reason: "notes-by-sms-off"))
        // disconnect SMS on: only after 60 min, once per outage
        p.disconnectSMS = true
        XCTAssertEqual(d(.bandDisconnected(since: at, now: at.addingTimeInterval(59 * 60))), .inApp(reason: "disconnect-too-short"))
        XCTAssertTrue(isSMS(d(.bandDisconnected(since: at, now: at.addingTimeInterval(61 * 60))), .note, "disconnected"))
        XCTAssertEqual(d(.bandDisconnected(since: at, now: at.addingTimeInterval(90 * 60))), .inApp(reason: "disconnect-already-sent"))
        XCTAssertEqual(SMSRouter.table.count, 13)                     // + BATT_CRITICAL (band 0.9.18)
    }

    // MARK: outbox state machine

    func testOutboxQueueSendDedupe() {
        var o = Outbox()
        guard case .queued(let id) = o.enqueue(body: "a", to: "+306900000001", contactName: "Νίκος", dedupeKey: "help", priority: .urgent, dryRun: false, now: t0) else { return XCTFail() }
        XCTAssertEqual(o.enqueue(body: "a", to: "+306900000001", contactName: "Νίκος", dedupeKey: "help", priority: .urgent, dryRun: false, now: t0.addingTimeInterval(300)), .duplicate)
        if case .queued = o.enqueue(body: "a", to: "+306900000002", contactName: "Ελένη", dedupeKey: "help", priority: .urgent, dryRun: false, now: t0) {} else { XCTFail("other number") }
        // urgent dedupe window is 10 min; after it a new HELP goes again
        if case .queued = o.enqueue(body: "a", to: "+306900000001", contactName: "Νίκος", dedupeKey: "help", priority: .urgent, dryRun: false, now: t0.addingTimeInterval(601)) {} else { XCTFail("after window") }
        XCTAssertEqual(o.droppedDuplicates, 1)
        let due = o.due(now: t0)
        XCTAssertEqual(due.map { $0.to }, ["+306900000001", "+306900000002"])
        o.markSending(id)
        o.complete(id, .sent(providerID: "SM1"), now: t0.addingTimeInterval(2))
        XCTAssertEqual(o.items.first { $0.id == id }?.status, .sent)
        XCTAssertEqual(o.items.first { $0.id == id }?.providerID, "SM1")
        // a simulated (demo) item never dedupes against a live one
        if case .queued = o.enqueue(body: "a", to: "+306900000002", contactName: "Ελένη", dedupeKey: "help", priority: .urgent, dryRun: true, simulated: true, now: t0) {} else { XCTFail("sim") }
    }

    func testOutboxRetryBackoffAndFailure() {
        var o = Outbox(); let p = OutboxPolicy()
        guard case .queued(let id) = o.enqueue(body: "b", to: "+306900000001", contactName: "N", dedupeKey: "escalation", priority: .urgent, dryRun: false, now: t0) else { return XCTFail() }
        var t = t0
        var waits: [TimeInterval] = []
        for _ in 1..<p.maxAttempts {
            XCTAssertEqual(o.due(now: t).map { $0.id }, [id])
            o.markSending(id)
            o.complete(id, .transient("network: offline"), now: t)
            let it = o.items[0]
            XCTAssertEqual(it.status, .queued)
            let next = it.nextAttemptAt!
            waits.append(next.timeIntervalSince(t))
            XCTAssertTrue(o.due(now: next.addingTimeInterval(-1)).isEmpty)   // not before its time
            t = next
        }
        XCTAssertEqual(waits, [30, 60, 120, 240, 480, 900, 900])
        o.markSending(id); o.complete(id, .transient("HTTP 503"), now: t)
        XCTAssertEqual(o.items[0].status, .failed)
        XCTAssertEqual(o.items[0].attempts, 8)
        // «Retry» puts it back at once
        o.retry(id, now: t)
        XCTAssertEqual(o.due(now: t).count, 1)
        // permanent error: failed at once
        o.markSending(id); o.complete(id, .permanent("HTTP 400 (Twilio 21211): invalid To"), now: t)
        XCTAssertEqual(o.items[0].status, .failed)
        XCTAssertEqual(o.items[0].lastError, "HTTP 400 (Twilio 21211): invalid To")
    }

    func testOutboxRateLimitExpiryAndRecovery() {
        var o = Outbox()
        for i in 0..<6 {
            if case .queued = o.enqueue(body: "n", to: "+306900000001", contactName: "N", dedupeKey: "note-\(i)", priority: .note, dryRun: true, now: t0.addingTimeInterval(Double(i))) {} else { XCTFail("\(i)") }
        }
        guard case .skipped(let sid) = o.enqueue(body: "n", to: "+306900000001", contactName: "N", dedupeKey: "note-7", priority: .note, dryRun: true, now: t0.addingTimeInterval(10)) else { return XCTFail("7th note") }
        XCTAssertEqual(o.items.first { $0.id == sid }?.status, .skipped)
        XCTAssertFalse(o.due(now: t0.addingTimeInterval(20)).contains { $0.id == sid })
        // urgent still goes past the per-hour limit
        if case .queued = o.enqueue(body: "h", to: "+306900000001", contactName: "N", dedupeKey: "help", priority: .urgent, dryRun: true, now: t0.addingTimeInterval(11)) {} else { XCTFail("urgent") }
        // an hour later notes go again
        if case .queued = o.enqueue(body: "n", to: "+306900000001", contactName: "N", dedupeKey: "note-8", priority: .note, dryRun: true, now: t0.addingTimeInterval(3601)) {} else { XCTFail("next hour") }
        // queued for over 3 h -> expired
        var e = Outbox()
        _ = e.enqueue(body: "x", to: "+306900000003", contactName: "X", dedupeKey: "help", priority: .urgent, dryRun: false, now: t0)
        XCTAssertTrue(e.due(now: t0.addingTimeInterval(3 * 3600 + 1)).isEmpty)
        XCTAssertEqual(e.items[0].status, .failed)
        XCTAssertTrue(e.items[0].lastError!.hasPrefix("expired"))
        // a "sending" item left by a crash goes back to the queue
        var r = Outbox()
        guard case .queued(let rid) = r.enqueue(body: "y", to: "+306900000004", contactName: "Y", dedupeKey: "help", priority: .urgent, dryRun: false, now: t0) else { return XCTFail() }
        r.markSending(rid)
        r.recoverSending(now: t0.addingTimeInterval(5))
        XCTAssertEqual(r.due(now: t0.addingTimeInterval(5)).map { $0.id }, [rid])
        // persisted and read back unchanged
        let back = try! JSONDecoder().decode(Outbox.self, from: JSONEncoder().encode(o))
        XCTAssertEqual(back, o)
    }

    // MARK: Twilio request

    func testTwilioRequestBuilding() throws {
        let r = try XCTUnwrap(TwilioAPI.request(creds, to: "+306912345678", body: "Μαρία: ΖΗΤΗΣΕ ΒΟΗΘΕΙΑ & όχι + ="))
        XCTAssertEqual(r.url?.absoluteString, "https://api.twilio.com/2010-04-01/Accounts/AC00000000000000000000000000000001/Messages.json")
        XCTAssertEqual(r.httpMethod, "POST")
        XCTAssertEqual(r.value(forHTTPHeaderField: "Content-Type"), "application/x-www-form-urlencoded; charset=utf-8")
        let expectAuth = "Basic " + Data("AC00000000000000000000000000000001:ffffffffffffffffffffffffffffffff".utf8).base64EncodedString()
        XCTAssertEqual(r.value(forHTTPHeaderField: "Authorization"), expectAuth)
        let body = String(data: try XCTUnwrap(r.httpBody), encoding: .utf8)!
        XCTAssertEqual(body, "To=%2B306912345678&From=%2B15005550006&Body=%CE%9C%CE%B1%CF%81%CE%AF%CE%B1%3A%20%CE%96%CE%97%CE%A4%CE%97%CE%A3%CE%95%20%CE%92%CE%9F%CE%97%CE%98%CE%95%CE%99%CE%91%20%26%20%CF%8C%CF%87%CE%B9%20%2B%20%3D")
        // the body decodes back to exactly the SMS text (what Twilio will deliver)
        let fields = Dictionary(uniqueKeysWithValues: body.split(separator: "&").map { kv -> (String, String) in
            let p = kv.split(separator: "=", maxSplits: 1).map(String.init); return (p[0], p[1].removingPercentEncoding!) })
        XCTAssertEqual(fields["Body"], "Μαρία: ΖΗΤΗΣΕ ΒΟΗΘΕΙΑ & όχι + =")
        XCTAssertEqual(fields["To"], "+306912345678")
        // the token never appears in a description
        XCTAssertFalse(String(describing: creds).contains(creds.authToken))
        XCTAssertTrue(creds.isComplete)
        XCTAssertEqual(TwilioCredentials(accountSID: "SK123", authToken: "short", fromNumber: "").problems, ["sid", "token", "from"])
    }

    func testTwilioClassify() {
        XCTAssertEqual(TwilioAPI.classify(status: 201, data: Data("{\"sid\":\"SMabc\"}".utf8), error: nil), .sent(providerID: "SMabc"))
        XCTAssertEqual(TwilioAPI.classify(status: 429, data: nil, error: nil), .transient("HTTP 429"))
        XCTAssertEqual(TwilioAPI.classify(status: 503, data: Data("{\"message\":\"busy\"}".utf8), error: nil), .transient("HTTP 503: busy"))
        if case .transient(let m) = TwilioAPI.classify(status: nil, data: nil, error: URLError(.notConnectedToInternet)) { XCTAssertTrue(m.hasPrefix("network")) } else { XCTFail() }
        if case .permanent(let m) = TwilioAPI.classify(status: 401, data: nil, error: nil) { XCTAssertTrue(m.contains("credentials")) } else { XCTFail() }
        XCTAssertEqual(TwilioAPI.classify(status: 400, data: Data("{\"code\":21211,\"message\":\"Invalid 'To' Phone Number\"}".utf8), error: nil),
                       .permanent("HTTP 400 (Twilio 21211): Invalid 'To' Phone Number"))
    }

    // MARK: engine (fake HTTP, fake clock)

    func engine(_ store: CredentialStore, http: FakeHTTP, clock: @escaping () -> Date) -> TowerEngine {
        let e = TowerEngine(credentials: store, fileURL: nil, makeHTTP: { http }, now: clock)
        e.contacts = [FamilyContact(name: "Νίκος", phone: "6912345678"), FamilyContact(name: "Ελένη", phone: "+44 7700 900123", email: "e@example.com"),
                      FamilyContact(name: "χωρίς αριθμό", phone: "")]
        return e
    }

    func testEngineDryRunWithoutCredentials() {
        let http = FakeHTTP()
        let e = engine(MemoryCredentialStore(), http: http, clock: { self.t0 })
        e.prefs.sender = .twilio                                         // [SMS-SHORTCUT] no credentials would pick the Shortcut
        XCTAssertEqual(e.mode, .dryRun)
        e.handle(.help(at: t0), wearerName: "Μαρία")
        XCTAssertTrue(http.requests.isEmpty)                             // nothing left the phone
        XCTAssertEqual(e.outbox.items.count, 2)                          // the contact without a number is skipped
        XCTAssertTrue(e.outbox.items.allSatisfy { $0.dryRun && $0.status == .sent })
        XCTAssertEqual(Set(e.outbox.items.map { $0.to }), ["+306912345678", "+447700900123"])
        XCTAssertTrue(e.outbox.items[0].body.hasPrefix("Μαρία: ΖΗΤΗΣΕ ΒΟΗΘΕΙΑ"))
        // in-app decisions add nothing
        e.handle(.ladder(.reminder(step: .water, isRepeat: false, forecastC: 37.8), at: t0), wearerName: "Μαρία")
        XCTAssertEqual(e.outbox.items.count, 2)
    }

    func testEngineLiveSendsThroughTwilioAndRetriesOffline() {
        let http = FakeHTTP()
        var now = t0
        var online = false
        let e = engine(MemoryCredentialStore(creds), http: http, clock: { now })
        e.isOnline = { online }
        XCTAssertEqual(e.mode, .live)
        e.handle(.ladder(.escalated(reason: .dangerLine, forecastC: 38.5, referenceC: nil), at: t0), wearerName: "Μαρία")
        XCTAssertTrue(http.requests.isEmpty)                             // offline: waits, no attempt spent
        XCTAssertTrue(e.outbox.items.allSatisfy { $0.status == .queued && $0.attempts == 0 })
        online = true
        http.replies = [(503, nil, nil), (201, "{\"sid\":\"SM2\"}", nil)]
        e.pump()
        XCTAssertEqual(http.requests.count, 2)
        XCTAssertEqual(http.requests[0].url?.path, "/2010-04-01/Accounts/AC00000000000000000000000000000001/Messages.json")
        let first = e.outbox.items.first { $0.status == .queued }!
        XCTAssertEqual(first.nextAttemptAt, t0.addingTimeInterval(30))
        e.pump()                                                         // too early: nothing
        XCTAssertEqual(http.requests.count, 2)
        now = t0.addingTimeInterval(31)
        e.pump()
        XCTAssertEqual(http.requests.count, 3)
        XCTAssertTrue(e.outbox.items.allSatisfy { $0.status == .sent && !$0.dryRun })
        // a SIMULATION (demo) event is dry-run even with credentials
        e.handle(.help(at: now), wearerName: "Μαρία", simulated: true)
        XCTAssertEqual(http.requests.count, 3)
        XCTAssertEqual(e.outbox.items.filter { $0.simulated }.count, 2)
        XCTAssertTrue(e.outbox.items.filter { $0.simulated }.allSatisfy { $0.dryRun })
        e.clearSimulated()
        XCTAssertTrue(e.outbox.items.allSatisfy { !$0.simulated })
        // the test SMS
        e.sendTest(wearerName: "Μαρία")
        XCTAssertEqual(http.requests.count, 5)
        XCTAssertEqual(e.outbox.items.last?.body, "Heat Guardian: δοκιμαστικό μήνυμα για Μαρία. Οι ειδοποιήσεις λειτουργούν.")
    }

    /// [DEMO-NORESP] «Αποστολή SMS και στην προσομοίωση»: off (default) = a SIMULATION event stays dry-run with credentials;
    /// on = it goes through Twilio and its text ends « (δοκιμή)». A real event never gets the marker.
    func testSimulationSMSToggle() throws {
        let http = FakeHTTP()
        let now = t0
        let e = engine(MemoryCredentialStore(creds), http: http, clock: { now })
        XCTAssertFalse(e.prefs.smsInSimulation)
        let noResp = TowerInput.ladder(.note(.noResponse, about: .water, forecastC: 37.9, referenceC: nil), at: t0)
        e.handle(noResp, wearerName: "Μαρία", simulated: true)
        XCTAssertTrue(http.requests.isEmpty)
        XCTAssertTrue(e.outbox.items.allSatisfy { $0.simulated && $0.dryRun && !$0.body.hasSuffix("(δοκιμή)") })
        e.clearSimulated()
        e.prefs.smsInSimulation = true
        http.replies = [(201, "{\"sid\":\"SM1\"}", nil), (201, "{\"sid\":\"SM2\"}", nil)]
        e.handle(noResp, wearerName: "Μαρία", simulated: true)
        XCTAssertEqual(http.requests.count, 2)
        let sim = e.outbox.items.filter { $0.simulated }
        XCTAssertEqual(sim.count, 2)
        XCTAssertTrue(sim.allSatisfy { !$0.dryRun && $0.status == .sent })
        XCTAssertEqual(sim.first?.body, SMSText.body(.noResponse(step: .water, at: t0), name: "Μαρία", lang: .el) + " (δοκιμή)")
        XCTAssertTrue(sim.first?.body.hasSuffix("Ίσως ένα τηλεφώνημα. (δοκιμή)") ?? false)
        e.prefs.smsLang = .en
        e.handle(.ladder(.escalated(reason: .dangerLine, forecastC: 38.6, referenceC: nil), at: t0), wearerName: "Maria", simulated: true)
        XCTAssertTrue(e.outbox.items.last?.body.hasSuffix(" (test)") ?? false)
        e.handle(.ladder(.escalated(reason: .dangerLine, forecastC: 38.6, referenceC: nil), at: t0), wearerName: "Maria")   // real
        XCTAssertFalse(e.outbox.items.last?.body.hasSuffix("(test)") ?? true)
        // an older saved prefs file (no smsInSimulation key) keeps its other settings
        let old = try JSONDecoder().decode(TowerPrefs.self, from: Data(#"{"notesBySMS":false,"disconnectSMS":true,"disconnectMinutes":90,"smsLang":"en","countryCode":"44"}"#.utf8))
        XCTAssertEqual(old.notesBySMS, false); XCTAssertEqual(old.disconnectMinutes, 90); XCTAssertEqual(old.countryCode, "44"); XCTAssertFalse(old.smsInSimulation)
        let back = try JSONDecoder().decode(TowerPrefs.self, from: JSONEncoder().encode(e.prefs))
        XCTAssertEqual(back, e.prefs)
    }

    /// [DEMO-NORESP] band 0.9.17-demo-b7n `replay noresp`: ladder frames with byte 18 = 0xD5 are SIMULATION; real ones are not.
    func testBandReplayMarker() throws {
        func entry(_ ev: LadderEvent, marked: Bool) throws -> LogEntry {
            let enc = ev.encoded
            var x = enc.x; if marked { x[7] = BandReplay.marker }
            let be = BandEvent(seq: 7, boot: 3, unix: UInt32(t0.timeIntervalSince1970), kindRaw: enc.type, arg: enc.arg, ext: x)
            return try XCTUnwrap(LogEntry.fromBand(try Frames.decodeEvent(Frames.encodeEvent(be)), receivedAt: t0))
        }
        let note = LadderEvent.note(.noResponse, about: .water, forecastC: 37.9, referenceC: nil)
        let sim = try entry(note, marked: true), real = try entry(note, marked: false)
        XCTAssertTrue(sim.isBandReplay); XCTAssertFalse(real.isBandReplay)
        XCTAssertEqual(sim.ladder, note)                                 // the marker does not change what it means
        XCTAssertFalse(try entry(.batteryLow(mV: 3500), marked: true).isBandReplay)   // ladder types 17-21 only
        // History: the replayed row carries the SIM badge, the real one does not
        let utcCal: Calendar = { var c = Calendar(identifier: .gregorian); c.timeZone = utc; return c }()
        let sr = DayStory.rows([sim], outbox: [], lang: .el, day: t0, calendar: utcCal)
        let rr = DayStory.rows([real], outbox: [], lang: .el, day: t0, calendar: utcCal)
        XCTAssertFalse(sr.isEmpty); XCTAssertFalse(rr.isEmpty)
        XCTAssertTrue(sr.allSatisfy { $0.simulated }); XCTAssertTrue(rr.allSatisfy { !$0.simulated })
    }

    // MARK: [SMS-SHORTCUT] iPhone Shortcut sender

    func testShortcutURLBuildingAndCallbacks() throws {
        let body = "Μαρία: δεν απάντησε & ζεσταίνεται; 38+ (δοκιμή)"
        let url = try XCTUnwrap(ShortcutAPI.runURL(name: "HG SOS", text: body, id: "ID-1"))
        let s = url.absoluteString
        XCTAssertTrue(s.hasPrefix("shortcuts://x-callback-url/run-shortcut?name=HG%20SOS&input=text&text=%CE%9C%CE%B1"), s)
        XCTAssertTrue(s.contains("&x-success=heatguardian%3A%2F%2Fshortcut-done%2FID-1&x-error=heatguardian%3A%2F%2Fshortcut-error%2FID-1"), s)
        XCTAssertFalse(s.contains(" ")); XCTAssertFalse(s.contains("+")); XCTAssertFalse(s.contains("Μ"))
        // what Shortcuts reads back (percent-decoding) is exactly our text
        let q = Dictionary(uniqueKeysWithValues: (URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []).map { ($0.name, $0.value ?? "") })
        XCTAssertEqual(q["name"], "HG SOS"); XCTAssertEqual(q["input"], "text"); XCTAssertEqual(q["text"], body)
        XCTAssertEqual(q["x-success"], "heatguardian://shortcut-done/ID-1")
        XCTAssertEqual(q["x-cancel"], "heatguardian://shortcut-cancel/ID-1")
        // an empty name falls back to «HG SOS»; a name with spaces and Greek is encoded
        XCTAssertTrue(ShortcutAPI.runURL(name: "  ", text: "x", id: "a")!.absoluteString.contains("name=HG%20SOS&"))
        XCTAssertTrue(ShortcutAPI.runURL(name: "Βοήθεια Μαρία", text: "x", id: "a")!.absoluteString.contains("name=%CE%92%CE%BF%CE%AE%CE%B8%CE%B5%CE%B9%CE%B1%20%CE%9C"))
        // callbacks (Shortcuts may append its own query)
        let done = try XCTUnwrap(ShortcutAPI.parseCallback(URL(string: "heatguardian://shortcut-done/ID-1?result=")!))
        XCTAssertEqual(done.id, "ID-1"); XCTAssertEqual(done.result, .sent(providerID: nil))
        let err = try XCTUnwrap(ShortcutAPI.parseCallback(URL(string: "heatguardian://shortcut-error/ID-2?errorMessage=No%20shortcut")!))
        XCTAssertEqual(err.id, "ID-2"); XCTAssertEqual(err.result, .permanent("Shortcuts: No shortcut"))
        XCTAssertEqual(ShortcutAPI.parseCallback(URL(string: "heatguardian://shortcut-cancel/ID-3")!)?.result, .permanent("Shortcuts: cancelled"))
        XCTAssertNil(ShortcutAPI.parseCallback(URL(string: "heatguardian://shortcut-done")!)?.id)
        XCTAssertNil(ShortcutAPI.parseCallback(URL(string: "https://example.com/shortcut-done/x")!))
        XCTAssertNil(ShortcutAPI.parseCallback(URL(string: "heatguardian://other/x")!))
    }

    func testShortcutSenderChoice() throws {
        let noCreds = engine(MemoryCredentialStore(), http: FakeHTTP(), clock: { self.t0 })
        XCTAssertNil(noCreds.prefs.sender)
        XCTAssertEqual(noCreds.sender, .shortcut); XCTAssertEqual(noCreds.mode, .live)       // default without Twilio
        let withCreds = engine(MemoryCredentialStore(creds), http: FakeHTTP(), clock: { self.t0 })
        XCTAssertEqual(withCreds.sender, .twilio); XCTAssertEqual(withCreds.mode, .live)
        withCreds.prefs.sender = .shortcut
        XCTAssertEqual(withCreds.sender, .shortcut)                                          // the owner's choice wins
        noCreds.prefs.sender = .twilio
        XCTAssertEqual(noCreds.sender, .twilio); XCTAssertEqual(noCreds.mode, .dryRun)
        // older prefs (no sender / name keys): automatic sender, «HG SOS»; the choice survives a save
        let old = try JSONDecoder().decode(TowerPrefs.self, from: Data(#"{"notesBySMS":true,"smsInSimulation":true}"#.utf8))
        XCTAssertNil(old.sender); XCTAssertEqual(old.shortcutName, "HG SOS"); XCTAssertTrue(old.smsInSimulation)
        var p = TowerPrefs(); p.sender = .shortcut; p.shortcutName = "SOS μαμά"
        XCTAssertEqual(try JSONDecoder().decode(TowerPrefs.self, from: JSONEncoder().encode(p)), p)
        // an outbox saved before the Shortcut sender (no "sender" key) still loads
        let it = OutboxItem(id: "x", createdAt: t0, dedupeKey: "help", priority: .urgent, to: "+306912345678", contactName: "Ν",
                            body: "b", nextAttemptAt: t0, dryRun: false)
        var json = try XCTUnwrap(JSONSerialization.jsonObject(with: JSONEncoder().encode(it)) as? [String: Any])
        json["sender"] = nil
        XCTAssertNil(try JSONDecoder().decode(OutboxItem.self, from: JSONSerialization.data(withJSONObject: json)).sender)
    }

    /// The demo path: the band's `replay noresp` LD_NOTE 2 (SIMULATION) with «Αποστολή SMS και στην προσομοίωση» on goes
    /// out as ONE Shortcut run (not one per contact), text ending « (δοκιμή)», deduped, completed by the callback.
    func testShortcutEngineFlow() throws {
        let http = FakeHTTP()
        var now = t0
        let e = engine(MemoryCredentialStore(), http: http, clock: { now })
        var opened: [(String, URL)] = []
        e.runShortcut = { opened.append(($0, $1)) }
        let noResp = TowerInput.ladder(.note(.noResponse, about: .water, forecastC: 37.9, referenceC: nil), at: t0)
        // toggle off: a SIMULATION event stays dry-run, Shortcuts is not opened
        e.handle(noResp, wearerName: "Μαρία", simulated: true)
        XCTAssertTrue(opened.isEmpty)
        XCTAssertEqual(e.outbox.items.count, 1)
        XCTAssertTrue(e.outbox.items[0].dryRun && e.outbox.items[0].status == .sent && e.outbox.items[0].sender == .shortcut)
        e.clearSimulated()
        // toggle on: one live item, the Shortcut opened with SMSText's text + « (δοκιμή)»
        e.prefs.smsInSimulation = true
        e.handle(noResp, wearerName: "Μαρία", simulated: true)
        XCTAssertEqual(opened.count, 1)
        XCTAssertTrue(http.requests.isEmpty)                                                 // never Twilio
        let it = try XCTUnwrap(e.outbox.items.last)
        XCTAssertEqual(it.to, ShortcutAPI.recipient); XCTAssertFalse(it.dryRun); XCTAssertEqual(it.status, .sending)
        let expected = SMSText.body(.noResponse(step: .water, at: t0), name: "Μαρία", lang: .el) + " (δοκιμή)"
        XCTAssertEqual(it.body, expected)
        let q = URLComponents(url: opened[0].1, resolvingAgainstBaseURL: false)?.queryItems ?? []
        XCTAssertEqual(q.first { $0.name == "text" }?.value, expected)
        XCTAssertEqual(opened[0].0, it.id)
        // the band re-sends it: deduped, Shortcuts not opened again
        e.handle(noResp, wearerName: "Μαρία", simulated: true)
        XCTAssertEqual(opened.count, 1); XCTAssertEqual(e.outbox.items.count, 1)
        // a second event while the first is in flight waits for its callback
        e.handle(.ladder(.escalated(reason: .dangerLine, forecastC: 38.6, referenceC: nil), at: t0), wearerName: "Μαρία", simulated: true)
        XCTAssertEqual(opened.count, 1)
        e.shortcutFinished(it.id, .sent(providerID: nil))                                    // x-success
        XCTAssertEqual(e.outbox.items.first { $0.id == it.id }?.status, .sent)
        XCTAssertEqual(opened.count, 2)                                                       // then the next one
        e.shortcutFinished(nil, .permanent("Shortcuts: No shortcut"))                        // x-error without an id = the one in flight
        XCTAssertEqual(e.outbox.items.first { $0.id == opened[1].0 }?.status, .failed)
        // retakes: the list cleared, the same event goes again
        e.clearOutbox()
        e.handle(noResp, wearerName: "Μαρία", simulated: true)
        XCTAssertEqual(opened.count, 3)
        // no callback at all: failed after the timeout, and the queue moves on
        now = t0.addingTimeInterval(ShortcutAPI.timeout + 1)
        e.pump()
        XCTAssertEqual(e.outbox.items.first { $0.id == opened[2].0 }?.status, .failed)
        XCTAssertNil(e.shortcutInFlight)
        // «Test the Shortcut»
        e.sendShortcutTest()
        XCTAssertEqual(opened.count, 4)
        XCTAssertEqual(URLComponents(url: opened[3].1, resolvingAgainstBaseURL: false)?.queryItems?.first { $0.name == "text" }?.value,
                       "Heat Guardian: δοκιμή αποστολής")
        // a real (not simulated) event never carries the marker
        e.shortcutFinished(opened[3].0, .sent(providerID: nil))
        e.handle(.help(at: now), wearerName: "Μαρία")
        XCTAssertEqual(opened.count, 5)
        XCTAssertFalse(e.outbox.items.last!.body.hasSuffix("(δοκιμή)"))
        XCTAssertFalse(e.outbox.items.last!.simulated)
    }

    func testEngineNoStormOnRepeatedEvents() {
        let http = FakeHTTP()
        var now = t0
        let e = engine(MemoryCredentialStore(creds), http: http, clock: { now })
        // the band re-notifies, the STATUS path and EVENTS both report the escalation, a SYNC replays it
        for i in 0..<5 {
            now = t0.addingTimeInterval(Double(i * 30))
            e.handle(.familyAlertNoAnswer(at: now), wearerName: "Μαρία")
            e.handle(.ladder(.escalated(reason: .stillHeating, forecastC: nil, referenceC: nil), at: now), wearerName: "Μαρία")
        }
        XCTAssertEqual(http.requests.count, 2)                           // one per contact
    }

    // MARK: history

    func testDayStoryFromBandScenario() throws {
        let vs = try vectors().filter { $0.scenario == "water_failed_cool_failed" }
        var entries: [LogEntry] = []
        for v in vs { entries.append(LogEntry.fromBand(try Frames.decodeEvent(bytes(v.hex)), receivedAt: t0)!) }
        let rows = DayStory.rows(entries, outbox: [], lang: .el, day: t0, calendar: { var c = Calendar(identifier: .gregorian); c.timeZone = utc; return c }())
        XCTAssertEqual(rows.map { $0.title }, ["Υπενθύμιση: νερό", "Υπενθύμιση: πιο δροσερό μέρος",
                                               "Ζεσταινόταν ακόμα στη δροσιά: ειδοποιήθηκε η οικογένεια",
                                               "Πάτησε το κουμπί: σας βλέπει", "Σταμάτησε να ζεσταίνεται"])
        XCTAssertEqual(rows[0].outcome, .notWorked)
        XCTAssertEqual(rows[1].outcome, .notWorked)
        let s = DayStory.summary(rows)
        XCTAssertEqual(s.reminders, 2); XCTAssertEqual(s.worked, 0); XCTAssertEqual(s.escalations, 1)
        let w = try vectors().filter { $0.scenario == "water_worked" }.map { LogEntry.fromBand(try Frames.decodeEvent(bytes($0.hex)), receivedAt: t0)! }
        let wr = DayStory.rows(w, outbox: [], lang: .en, day: t0)
        XCTAssertEqual(wr.count, 1)
        XCTAssertEqual(wr[0].outcome, .worked)
    }

    // MARK: her home screen balance

    func testBalanceSteps() {
        XCTAssertEqual(Balance.step(viewState: "OK", connected: true), 0)
        XCTAssertEqual(Balance.step(viewState: "OK", connected: true, settling: true), 1)
        XCTAssertEqual(Balance.step(viewState: "DRINK", connected: true), 2)
        XCTAssertEqual(Balance.step(viewState: "COOL", connected: true), 3)
        for s in ["CHECK", "DANGER", "HELP"] { XCTAssertEqual(Balance.step(viewState: s, connected: true), 4) }
        XCTAssertNil(Balance.step(viewState: "OK", connected: false))
        XCTAssertNil(Balance.step(viewState: "NOT_WORN", connected: true))
        XCTAssertNil(Balance.dot(nil))
        // the band's 5 colours also differ in lightness (colour-blind / ageing eyes): no two within 0.05 luminance
        func lum(_ c: (r: Int, g: Int, b: Int, whiteText: Bool)) -> Double {
            func l(_ v: Int) -> Double { let x = Double(v) / 255; return x <= 0.04045 ? x / 12.92 : pow((x + 0.055) / 1.055, 2.4) }
            return 0.2126 * l(c.r) + 0.7152 * l(c.g) + 0.0722 * l(c.b)
        }
        let ls = Balance.colours.map(lum)
        for i in ls.indices { for j in ls.indices where i < j { XCTAssertGreaterThan(abs(ls[i] - ls[j]), 0.05, "\(i) vs \(j)") } }
    }

    // MARK: band 0.9.18 — GAUGE live frame + battery events, vs the band's own bytes (gauge_vectors_fw.json)

    struct GaugeFile: Decodable {
        struct G: Decodable { var hex: String; var seq: Int; var boot_count: Int; var unix: UInt32; var type: Int
                              var step: Int; var dot: Int; var why: Int; var reminder: Int; var f20_c100: Int? }
        struct B: Decodable { var hex: String; var seq: Int; var boot_count: Int; var unix: UInt32; var type: Int; var arg: Int; var vbat_mv: Int }
        var gauge: [G]
        var battery: [B]
    }
    func gaugeVectors() throws -> GaugeFile {
        let url = Bundle(for: TowerTests.self).url(forResource: "gauge_vectors_fw", withExtension: "json")
            ?? URL(fileURLWithPath: "gauge_vectors_fw.json")
        return try JSONDecoder().decode(GaugeFile.self, from: Data(contentsOf: url))
    }
    func hex(_ b: [UInt8]) -> String { Frames.toHex(b).replacingOccurrences(of: " ", with: "").lowercased() }

    func testGaugeVectorsDecodeAndReencodeByteForByte() throws {
        let f = try gaugeVectors()
        XCTAssertEqual(f.gauge.count, 8)
        for v in f.gauge {
            let e = try Frames.decodeEvent(bytes(v.hex))
            XCTAssertEqual(e.kindRaw, 22); XCTAssertEqual(e.seq, 0); XCTAssertEqual(e.seq, v.seq)
            XCTAssertEqual(e.boot, v.boot_count); XCTAssertEqual(e.unix, v.unix)
            let g = try XCTUnwrap(e.gauge, v.hex)
            XCTAssertEqual(g.step, v.step == 255 ? nil : v.step, v.hex)
            XCTAssertEqual(g.dot, v.dot, v.hex); XCTAssertEqual(g.why, v.why); XCTAssertEqual(g.reminder, v.reminder)
            XCTAssertEqual(g.forecastC.map { Int(($0 * 100).rounded()) }, v.f20_c100, v.hex)
            let enc = g.encoded
            XCTAssertEqual(enc.arg, v.step)
            XCTAssertEqual(hex(Frames.encodeEvent(BandEvent(seq: v.seq, boot: v.boot_count, unix: v.unix, kindRaw: 22, arg: enc.arg, ext: enc.x))),
                           v.hex, "re-encode")
            // never a log row, never a ladder event
            XCTAssertNil(e.ladder); XCTAssertNil(LogEntry.fromBand(e, receivedAt: t0).flatMap { $0.ladder })
        }
        let first = try XCTUnwrap(try Frames.decodeEvent(bytes(f.gauge[2].hex)).gauge)
        XCTAssertEqual(first, BandGauge(step: 2, dot: 5, why: 2, reminder: 1, forecastC: 37.81))
        XCTAssertEqual(first.whyKind, .minuteRefresh); XCTAssertEqual(first.reminderStep, .water)
        // an unknown step is ignored (logged), not shown
        let diag = BandEventDiagnostics.shared
        diag.reset(); diag.log = { _ in }
        defer { diag.log = { print("[HG] " + $0) }; diag.reset() }
        XCTAssertNil(BandEvent(seq: 0, boot: 1, unix: 0, kindRaw: 22, arg: 7, ext: [0, 1, 0, 0, 0x80, 0, 0, 0]).gauge)
        XCTAssertEqual(diag.unknownArgs["22/7"], 1)
    }

    func testBatteryVectorsDecodeAndReencodeByteForByte() throws {
        let f = try gaugeVectors()
        XCTAssertEqual(f.battery.count, 3)
        var decoded: [LadderEvent] = []
        for v in f.battery {
            let e = try Frames.decodeEvent(bytes(v.hex))
            XCTAssertEqual(e.kindRaw, v.type); XCTAssertEqual(e.arg, v.arg); XCTAssertEqual(e.seq, v.seq)
            let l = try XCTUnwrap(e.ladder, v.hex)
            decoded.append(l)
            let enc = l.encoded
            XCTAssertEqual(enc.type, v.type); XCTAssertEqual(enc.arg, v.arg)
            XCTAssertEqual(hex(Frames.encodeEvent(BandEvent(seq: v.seq, boot: v.boot_count, unix: v.unix, kindRaw: enc.type, arg: enc.arg, ext: enc.x))),
                           v.hex, "re-encode")
            let row = try XCTUnwrap(LogEntry.fromBand(e, receivedAt: t0))
            XCTAssertEqual(row.ladder, l)                       // survives the log round trip (ext kept)
        }
        XCTAssertEqual(decoded, [.batteryLow(mV: 3540), .batteryCritical(mV: 3240), .powerOffBattery(mV: 3240)])
        XCTAssertEqual(try LogEntry.fromBand(Frames.decodeEvent(bytes(f.battery[0].hex)), receivedAt: t0)?.kind, .battLow)
    }

    func testGaugeNeverStoredAndNeverMovesTheCursor() throws {
        let f = try gaugeVectors()
        let st = EventStore(fileName: nil)
        XCTAssertNotNil(st.addBand(try Frames.decodeEvent(bytes(f.battery[0].hex)), receivedAt: t0))   // seq 41, boot 37
        XCTAssertEqual(st.cursorSeq, 41); XCTAssertEqual(st.cursorBoot, 37)
        for v in f.gauge { XCTAssertNil(st.addBand(try Frames.decodeEvent(bytes(v.hex)), receivedAt: t0)) }
        XCTAssertEqual(st.cursorSeq, 41); XCTAssertEqual(st.cursorBoot, 37); XCTAssertEqual(st.entries.count, 1)
        // a GAUGE "on connect" from a NEW boot must not reset the cursor either
        let g = try Frames.decodeEvent(bytes(f.gauge[0].hex))
        XCTAssertNil(st.addBand(BandEvent(seq: 0, boot: 38, unix: g.unix, kindRaw: 22, arg: g.arg, ext: g.ext), receivedAt: t0))
        XCTAssertEqual(st.cursorSeq, 41); XCTAssertEqual(st.cursorBoot, 37)
        let fresh = EventStore(fileName: nil)
        XCTAssertNil(fresh.addBand(g, receivedAt: t0))
        XCTAssertNil(fresh.cursorBoot)
    }

    func testBalanceShowsTheBandsGaugeThenFallsBack() throws {
        let g = BandGauge(step: 3, dot: 8, why: 1, reminder: 2, forecastC: 38.37)
        // fresh GAUGE: exactly the band's step and dot, whatever STATUS says
        var d = Balance.display(gauge: g, gaugeAt: t0, now: t0.addingTimeInterval(170), connected: true, fallbackStep: 2)
        XCTAssertEqual(d.step, 3); XCTAssertEqual(d.dot, 8); XCTAssertTrue(d.fromBand)
        // older than 3 min, disconnected, or no frame yet (band before 0.9.18): the STATUS tier, dot centred
        d = Balance.display(gauge: g, gaugeAt: t0, now: t0.addingTimeInterval(181), connected: true, fallbackStep: 2)
        XCTAssertEqual(d.step, 2); XCTAssertEqual(d.dot, Balance.dot(2)); XCTAssertFalse(d.fromBand)
        d = Balance.display(gauge: g, gaugeAt: t0, now: t0, connected: false, fallbackStep: nil)
        XCTAssertNil(d.step); XCTAssertNil(d.dot)
        d = Balance.display(gauge: nil, gaugeAt: nil, now: t0, connected: true, fallbackStep: 0)
        XCTAssertEqual(d.step, 0); XCTAssertEqual(d.dot, Balance.dot(0))
        // the band's grey (no forecast): grey and no dot, even though STATUS would give a tier
        let grey = try XCTUnwrap(try Frames.decodeEvent(bytes(gaugeVectors().gauge[5].hex)).gauge)
        d = Balance.display(gauge: grey, gaugeAt: t0, now: t0, connected: true, fallbackStep: 0)
        XCTAssertNil(d.step); XCTAssertNil(d.dot); XCTAssertTrue(d.fromBand)
    }

    func testBatteryRoutingOneSMSAndHistoryRows() throws {
        var m = TowerMemory()
        let p = TowerPrefs()
        let at = t0
        XCTAssertEqual(SMSRouter.decide(.ladder(.batteryCritical(mV: 3240), at: at), prefs: p, memory: &m, now: at.addingTimeInterval(5)),
                       .sms(.batteryEnded(at: at), priority: .note, dedupeKey: "battery"))
        XCTAssertEqual(SMSRouter.decide(.ladder(.batteryLow(mV: 3540), at: at), prefs: p, memory: &m), .inApp(reason: "band-status"))
        // reaching the phone > 30 min late (SYNC after she recharged): history, not an SMS
        XCTAssertEqual(SMSRouter.decide(.ladder(.batteryCritical(mV: 3240), at: at), prefs: p, memory: &m, now: at.addingTimeInterval(31 * 60)),
                       .inApp(reason: "battery-old"))
        // the engine: BATT_CRITICAL then POWER_OFF 3 a second later (and a SYNC replay) -> ONE SMS per contact
        let http = FakeHTTP()
        var now = t0
        let e = engine(MemoryCredentialStore(creds), http: http, clock: { now })
        let f = try gaugeVectors()
        let rows = try f.battery.map { try XCTUnwrap(LogEntry.fromBand(Frames.decodeEvent(bytes($0.hex)), receivedAt: t0)) }
        let bandAt = rows[1].at
        now = bandAt.addingTimeInterval(2)
        for r in rows + rows { e.handle(.ladder(r.ladder!, at: r.at), wearerName: "Μαρία") }
        XCTAssertEqual(http.requests.count, 2)                            // one per contact with a number
        XCTAssertEqual(e.outbox.items.count, 2)
        XCTAssertTrue(e.outbox.items.allSatisfy { $0.body.hasPrefix("Μαρία: η μπαταρία του βραχιολιού τελείωσε (") && $0.priority == .note })
        // History: «battery low» + ONE «battery ended» row (POWER_OFF 3 folds into it), with the SMS attached
        var low = rows[0]; low.at = bandAt.addingTimeInterval(-600)      // the vectors' BATT_LOW is 2.8 h earlier (other day in UTC)
        let story = DayStory.rows([low] + rows[1...], outbox: e.outbox.items, lang: .el, day: bandAt)
        XCTAssertEqual(story.map { $0.symbol }, ["battery.25percent", "battery.0percent"])
        XCTAssertEqual(story[0].title, "Χαμηλή μπαταρία: φορτίστε απόψε")
        XCTAssertEqual(story[1].title, "Η μπαταρία τελείωσε: το βραχιόλι έκλεισε")
        XCTAssertEqual(story[1].sms.count, 2)
    }
}
