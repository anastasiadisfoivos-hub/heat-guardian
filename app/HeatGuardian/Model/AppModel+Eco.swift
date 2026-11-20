// Ecosystem logic of AppModel (ECOSYSTEM_SPEC §5 / §5b): EVENTS ingest + SYNC, on-connect writes (name, routine,
// plan), family replies (FAMILY_ACK 2 + FAMILY_MSG), notification actions, the "2 missed nudges" and evening-summary
// notifications, the home-class Tomorrow plan, and the demo's simulated events.

import Foundation
import UIKit

extension AppModel {
    // MARK: log access

    /// The log the screens show: the demo's while a demo runs, else the band's.
    var activeStore: EventStore { isDemo ? demoStore : store }

    static func dayString(_ d: Date) -> String {
        let c = Calendar.current.dateComponents([.year, .month, .day], from: d)
        return String(format: "%04d-%02d-%02d", c.year ?? 0, c.month ?? 0, c.day ?? 0)
    }

    // MARK: Tomorrow plan for HER home

    /// The loaded plan with its indoor curve moved to her home class (Indoor.adjust); the one that is sent and shown.
    var herPlan: Plan? {
        guard let p = plan else { return nil }
        var a = Indoor.adjust(p, to: routine.homeClass)
        if a.homeClass != p.homeClass { a.ble = nil }   // the plan's precomputed frames no longer apply
        return a
    }

    func planKey(_ p: Plan) -> String { p.date + " " + (p.homeClass ?? "") }

    /// Nudges the band is expected to show on `day` (from the plan for that day; the demo plays the plan "today").
    func plannedNudges(on day: Date) -> [PlannedNudge] {
        // OWNER DECISION Nov 19 18:04: the clock-driven generic nudges (shutters, windows / air, A/C, clock-based water,
        // morning brief / last-cool) are removed, like on band 0.9.17. Her Day timing (N7 / N8) comes from the band's
        // own PLAN_ITEM / nudge EVENTS, not from this prediction. NudgePlanner stays only for its tests.
        _ = day
        return []
    }

    // MARK: EVENTS

    func ingestEvent(_ bytes: [UInt8], at: Date) {
        guard let ev = try? Frames.decodeEvent(bytes) else { return }
        lastSyncAt = at
        // band 0.9.18 GAUGE: a live frame for her screen only — never stored, never moves the SYNC cursor
        if ev.kindRaw == BandGauge.eventType { towerGauge(ev, at: at); return }
        guard let e = store.addBand(ev, receivedAt: at) else { store.save(); return }
        store.save()
        logChanged()
        onNewEntry(e, live: true)
        towerHandle(e)
    }

    /// 0x16 after EVENTS notify is on: everything after the last event seen (all of them after a band restart).
    func sendSync() {
        guard !isDemo || link.isConnected else { return }
        link.send(Frames.cmdSyncEvents(sinceSeq: store.cursorSeq, boot: store.cursorBoot ?? 0xFFFF), label: "SYNC_EVENTS")
    }

    func logChanged() {
        logVersion += 1
        rescheduleSummary()
    }

    private func onNewEntry(_ e: LogEntry, live: Bool) {
        if live && (e.kind == .nudgeMissed || e.kind == .nudgeDone) { checkMissedPair(e) }
        if e.kind == .allClear { closeAlertOnAllClear(source: live ? .live : .demo) }
    }

    /// ALL_CLEAR (0.9.9): the episode is over, so a DANGER / unanswered-CHECK takeover closes quietly (no chime, no
    /// notification; the «Back to normal» row stays in the log). A HELP she pressed is not a heat episode: it stays.
    func closeAlertOnAllClear(source: Source) {
        guard let a = alert, a.source == source, a.kind != .help else { return }
        dismissAlert()
    }

    /// Two prevention nudges missed in a row today -> one gentle notification, at most once a day.
    private func checkMissedPair(_ e: LogEntry) {
        let cal = Calendar.current
        guard e.kind == .nudgeMissed, cal.isDateInToday(e.at), AppMode.current != .elder else { return }
        let today = cal.startOfDay(for: Date())
        if let d = missedNotifiedDay, cal.isDate(d, inSameDayAs: today) { return }
        let outcomes = store.entries(on: today).filter { $0.kind == .nudgeDone || $0.kind == .nudgeMissed }
        guard outcomes.count >= 2 else { return }
        let last2 = outcomes.suffix(2)
        guard last2.allSatisfy({ $0.kind == .nudgeMissed }) else { return }
        let names = last2.map { L.nudgeName($0.nudge ?? .water) }
        AlertFX.shared.postGentle(title: L.notifMissedTitle, body: L.notifMissedBody(names[0], names[1]),
                                  id: "hg.missed." + AppModel.dayString(today))
        missedNotifiedDay = today
    }

    // MARK: on-connect writes (live band, after TIME)

    func onConnectedWrites() {
        guard !isDemo else { return }
        let ud = UserDefaults.standard
        if !familyName.isEmpty {
            let f = Frames.cmdFamilyName(familyName)
            if ud.string(forKey: "hg.sentname") != Frames.toHex(f) {
                link.send(f, label: "FAMILY_NAME")
                ud.set(Frames.toHex(f), forKey: "hg.sentname")
            }
        }
        if !routine.isEmpty {
            let f = routine.seedFrame
            if ud.string(forKey: "hg.sentroutine") != Frames.toHex(f) {
                link.send(f, label: "ROUTINE_SEED")
                ud.set(Frames.toHex(f), forKey: "hg.sentroutine")
            }
        }
        autoSendPlan()
        flushVisits()
        sendDayPlansIfNeeded()
    }

    /// Tomorrow's plan goes to the band by itself on connect. Never the constructed demo plan, never a past day.
    func autoSendPlan() {
        guard !isDemo, link.isConnected, let p = herPlan, !p.isConstructedDemo,
              p.date >= AppModel.dayString(Date()), let chunks = try? Frames.forecastChunks(p) else { return }
        for (i, c) in chunks.enumerated() { link.send(c, label: "FORECAST \(i)") }
        link.send(Frames.safeHoursFrame(p), label: "SAFE_HOURS")
        planOnBand = (planKey(p), Date())
        lastSendResult = "\(L.sent): 0x11 ×4, 0x14 (\(p.date) \(p.homeClass ?? ""))"
    }

    /// Settings «Αποστολή»: FAMILY_NAME. Returns false when nothing could be sent (not connected).
    @discardableResult
    func sendFamilyName() -> Bool {
        let f = Frames.cmdFamilyName(familyName)
        let ok = sendUser([(f, "FAMILY_NAME")])
        if ok && !isDemo { UserDefaults.standard.set(Frames.toHex(f), forKey: "hg.sentname") }
        lastSendResult = ok ? "\(L.sent): FAMILY_NAME" : L.needLink
        return ok
    }

    @discardableResult
    func sendRoutine() -> Bool {
        let f = routine.seedFrame
        let ok = sendUser([(f, "ROUTINE_SEED")])
        if ok && !isDemo { UserDefaults.standard.set(Frames.toHex(f), forKey: "hg.sentroutine") }
        lastSendResult = ok ? "\(L.sent): ROUTINE_SEED" : L.needLink
        return ok
    }

    // MARK: family replies

    /// msg 1 «Σας καλώ» (+ FAMILY_ACK 2 when there is an alarm id), 2 «Έρχομαι», 3 «Το είδα»; logged as "you".
    func familyReply(msg: Int, alarmId: Int?, source: Source) {
        if msg == 1, let id = alarmId {
            sendCommand(Frames.cmdFamilyAck(type: 2, alarmId: UInt32(id)), label: "FAMILY_ACK 2", source: source)
        }
        sendCommand(Frames.cmdFamilyMsg(UInt8(msg)), label: "FAMILY_MSG \(msg)", source: source)
        let st = source == .demo ? demoStore : store
        st.add(LogEntry(id: "you-" + UUID().uuidString, at: Date(), kind: .familyMsgSent, arg: msg, origin: .you,
                        simulated: source == .demo))
        if source == .live { st.save() }
        logChanged()
    }

    /// A lock-screen / banner action on an alert notification.
    func handleNotificationAction(_ id: String, info: [AnyHashable: Any], done: @escaping () -> Void) {
        let source = Source(rawValue: info["source"] as? String ?? "live") ?? .live
        let alarmId = (info["alarmId"] as? NSNumber)?.intValue
        let msg = id == AlertFX.actionCall ? 1 : (id == AlertFX.actionComing ? 2 : 3)
        familyReply(msg: msg, alarmId: alarmId, source: source)
        if let a = alert, a.id.uuidString == (info["alert"] as? String) {
            alert = nil
            AlertFX.shared.stop()
        }
        AlertFX.shared.clearDelivered()
        if msg == 1 {
            // «Σας καλώ» opens the app (foreground action): dial when a number is saved.
            let digits = wearerPhone.filter { "+0123456789".contains($0) }
            if source == .live, !digits.isEmpty, let url = URL(string: "tel://" + digits) { UIApplication.shared.open(url) }
        }
        if source == .live && link.isConnected { link.whenFlushed(done) } else { done() }
    }

    // MARK: evening summary

    /// One pending request at the next 20:30 with the latest summary of that day (rescheduled on every log change).
    func rescheduleSummary() {
        guard summaryOn, AppMode.current != .elder else { AlertFX.shared.cancelSummary(); return }
        let now = Date()
        var target = now.at(minute: 20 * 60 + 30)
        if target <= now { target = Calendar.current.date(byAdding: .day, value: 1, to: target) ?? target }
        let entries = store.entries(on: target)
        let who = wearerName.isEmpty ? "" : " · " + wearerName
        let body = entries.isEmpty ? L.noEventsToday : L.summaryLine(Timeline.summary(entries, day: target))
        AlertFX.shared.scheduleSummary(title: L.notifSummaryTitle + who, body: body, at: target)
    }

    // MARK: reason line (§4)

    /// The band's reason line, worked out from STATUS (the frame does not carry the band's `why` bits):
    /// family pending -> no answer; body estimate high -> body; room >= 28 °C -> heat at home. nil = no line.
    func reasonLine(_ d: StatusFrame?) -> String? {
        guard let d = d else { return nil }
        let vs = AppModel.viewState(d)
        guard ["DRINK", "COOL", "CHECK", "DANGER", "HELP"].contains(vs) else { return nil }
        if d.familyPending && vs != "HELP" { return L.reasonNoAnswer }
        if d.hasEstimate && d.coreC >= 37.8 { return L.reasonBody }
        if let t = d.tairC, t >= 28 { return L.reasonHeat(Int(t.rounded())) }
        return nil
    }

    // MARK: demo events (ΠΡΟΣΟΜΟΙΩΣΗ)

    func resetDemoLog() {
        demoStore.clear()
        demoNudgesFired = []
        demoSynthVS = nil
        demoSeq = 0
        demoHerDayFired = []
        demoEpisode = nil
        seedHerDayDemo()
        seedQualityDemo()
        logVersion += 1
    }

    /// The demo has no EVENTS: build them from the replay's states and the planned nudges, as EVENTS frames that
    /// go through the same decoder (Frames.decodeEvent) as a real band's.
    func synthDemoEvents(_ d: StatusFrame, vs: String, at: Date, bump: Bool = true) {
        func emit(_ kind: BandEvent.Kind, _ arg: Int, _ t: Date) {
            demoSeq += 1
            let ev = BandEvent(seq: demoSeq, boot: 0, unix: UInt32(max(0, t.timeIntervalSince1970)), kindRaw: kind.rawValue, arg: arg)
            guard let back = try? Frames.decodeEvent(Frames.encodeEvent(ev)),
                  let e = LogEntry.fromBand(back, receivedAt: t, simulated: true) else { return }
            demoStore.add(e)
        }
        var changed = false
        if synthQualityDemo(vs: vs, fam: d.familyPending, at: at) { changed = true }
        if vs != demoSynthVS {
            if let code = HG.guardianStateNames.firstIndex(of: vs), ["DRINK", "COOL", "DANGER", "CHECK"].contains(vs) {
                emit(.warnShown, code, at); changed = true
            } else if vs == "HELP" {
                emit(.help, 1, at); changed = true          // arg 1 = band button
            } else if vs == "IMOK" {
                emit(.imOK, 1, at); changed = true
            } else if vs == "NOT_WORN" {
                emit(.warnShown, 6, at); changed = true          // HG_ST_NOT_WORN
            }
            demoSynthVS = vs
        }
        let day = Calendar.current.startOfDay(for: at)
        let m = at.minuteOfDay
        for (i, p) in plannedNudges(on: day).enumerated() {
            let shown = "s" + p.id, closed = "c" + p.id
            if m >= p.minute && !demoNudgesFired.contains(shown) {
                demoNudgesFired.insert(shown)
                emit(.nudgeShown, p.nudge.rawValue, day.at(minute: p.minute)); changed = true
            }
            // every third nudge is missed (10 min), the others done after 4 min
            let missed = i % 3 == 2
            let closeAt = p.minute + (missed ? 10 : 4)
            if m >= closeAt && !demoNudgesFired.contains(closed) {
                demoNudgesFired.insert(closed)
                emit(missed ? .nudgeMissed : .nudgeDone, p.nudge.rawValue, day.at(minute: closeAt)); changed = true
            }
        }
        if synthHerDayDemo(at: at) { changed = true }
        if changed && bump { logVersion += 1 }
    }
}
