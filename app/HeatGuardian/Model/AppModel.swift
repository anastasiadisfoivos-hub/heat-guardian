// App state. Live band frames and demo frames go through the SAME ingest(): Frames.decodeStatus -> history ->
// alert rule (port of dashboard/js/app.js handlers().status + onFamily). All mutation happens on the main thread
// (CoreBluetooth queue = main, Timers on the main run loop).

import Foundation
import SwiftUI
import UIKit

enum Source: String, Codable { case live, demo }

struct AlertInfo: Identifiable, Equatable {
    enum Kind { case family, help, danger }
    let id = UUID()
    var kind: Kind
    var alarmId: Int?
    var source: Source
    var at: Date
    var frame: StatusFrame
    var acked1 = false          // 0x12 type 1 ("family notified") sent / recorded
    var calling = false         // 0x12 type 2 sent
    static func == (a: AlertInfo, b: AlertInfo) -> Bool { a.id == b.id && a.calling == b.calling && a.acked1 == b.acked1 }
}

struct WriteLog: Identifiable {
    let id = UUID()
    var at: Date
    var label: String
    var hex: String
    var simulated: Bool
}

final class AppModel: ObservableObject {
    /// One model for the app, the notification delegate and the view-models.
    static let shared = AppModel()

    // settings (persisted)
    @Published var lang: Lang { didSet { ud.set(lang.rawValue, forKey: "hg.lang"); AlertFX.shared.registerCategories(L) } }
    /// The family member's name the band shows («…: σας καλεί»), CMD 0x18. Empty = band default «οικογένεια».
    @Published var familyName: String { didSet { ud.set(familyName, forKey: "hg.famname") } }
    /// Her stated routine + home type (§5b), CMD 0x19 and the Tomorrow simulation.
    @Published var routine: Routine { didSet { routine.save(); rescheduleSummary() } }
    /// Evening summary notification at 20:30 (on by default).
    @Published var summaryOn: Bool { didSet { ud.set(summaryOn, forKey: "hg.summary"); rescheduleSummary() } }
    @Published var wearerName: String { didSet { ud.set(wearerName, forKey: "hg.name") } }
    @Published var wearerPhone: String { didSet { ud.set(wearerPhone, forKey: "hg.phone") } }
    @Published var age: Int { didSet { ud.set(age, forKey: "hg.age") } }
    @Published var sexMale: Bool { didSet { ud.set(sexMale, forKey: "hg.sexm") } }
    @Published var bmi: Double { didSet { ud.set(bmi, forKey: "hg.bmi") } }
    @Published var medFlags: Int { didSet { ud.set(medFlags, forKey: "hg.meds") } }
    @Published var restHR: Int { didSet { ud.set(restHR, forKey: "hg.resthr") } }
    /// Her medicines for the doctor's report (free text + optional class), on this phone only.
    @Published var meds: [Medication] { didSet { medStore.set(meds) } }
    /// Elder mode can turn the doctor's report off on this phone (on by default; nothing is made until asked).
    @Published var reportOn: Bool { didSet { ud.set(reportOn, forKey: "hg.report.on") } }
    /// When she (Elder mode) / the family (confirming her consent) accepted the report's consent screen.
    @Published var reportConsentAt: Date? { didSet { ud.set(reportConsentAt, forKey: "hg.report.consent") } }

    // live
    @Published private(set) var phase: BandLink.Phase = .idle
    @Published private(set) var liveLast: StatusFrame?
    @Published private(set) var liveLastAt: Date?
    @Published private(set) var liveHist: [HistPoint] = []
    @Published private(set) var info: Frames.Info?
    @Published private(set) var stats = (frames: 0, crcErrors: 0, gaps: 0)
    @Published private(set) var writes: [WriteLog] = []
    @Published var lastSendResult: String?

    // demo
    @Published private(set) var demo: DemoPlayer?
    @Published private(set) var demoLast: StatusFrame?
    @Published private(set) var demoLastAt: Date?
    @Published private(set) var demoHist: [HistPoint] = []
    @Published private(set) var demoTick = 0

    // alert + plan
    @Published var alert: AlertInfo?
    @Published var muted = false
    @Published var plan: Plan?
    @Published var now = Date()

    // ecosystem: the day log
    let store = EventStore()                       // live, persisted
    let demoStore = EventStore(fileName: nil)      // demo, in memory, cleared with the demo
    /// Bumped on every log change (the stores are plain classes).
    @Published var logVersion = 0
    /// Bumped when the Tower (contacts, outbox, settings) changes.
    @Published var towerVersion = 0
    /// Last time the phone heard from a live band (STATUS or EVENTS); persisted for the offline hero.
    @Published var lastSyncAt: Date? { didSet { ud.set(lastSyncAt, forKey: "hg.lastsync") } }
    /// The last plan written to a live band (date + home class), and when.
    @Published var planOnBand: (key: String, at: Date)?
    var demoNudgesFired = Set<String>()
    /// Her Day demo: plan sends / today's scripted visits already emitted.
    var demoHerDayFired = Set<String>()

    // Her Day (HERDAY_SPEC.md): her phone's visits (Elder mode, on-device only) + the Core Location monitor.
    let visits = VisitStore()
    let visitMonitor = VisitMonitor()
    /// Elder mode: learn her places with iOS Visits (on by default; nothing is asked until Elder mode is chosen).
    @Published var locationOn: Bool { didSet { ud.set(locationOn, forKey: "hg.location"); updateLocation() } }
    @Published var locationAuth: LocationAuth = .notDetermined
    /// Bumped when her visits / places change (the store is a plain class).
    @Published var herDayVersion = 0
    @Published var homeSetResult: String?
    /// Her Day demo: tomorrow = heat-wave day 3 (hot from 08:00) to show a "go after" suggestion.
    @Published var demoHotterTomorrow = false
    var demoSynthVS: String?
    /// Demo alert quality: the open episode (start, peak 1 DRINK / 2 COOL / 3 CHECK-DANGER, family called).
    var demoEpisode: (start: Date, peak: Int, family: Bool)?
    var demoSeq = 0
    /// Day (start of day) on which the "2 missed nudges" notification was last posted (max once a day).
    var missedNotifiedDay: Date? {
        get { UserDefaults.standard.object(forKey: "hg.missedday") as? Date }
        set { UserDefaults.standard.set(newValue, forKey: "hg.missedday") }
    }

    /// Per-day aggregates for the doctor's report (live STATUS minutes; never the core estimate).
    let ledger = ReportLedger()
    let medStore = MedStore()

    let link = BandLink()
    private let ud = UserDefaults.standard
    private var lastFamilyKey: [Source: String] = [:]
    private var lastVS: [Source: String] = [:]
    private var lastCounter: Int?
    private var ack1Key: String?        // live: the alarm whose FAMILY_ACK 1 was last written to the band…
    private var ack1At: Date?           // …and when (re-sent at most every 30 s while the band still shows it pending)
    private var saveCountdown = 0
    private var clockTimer: Timer?

    var L: Strings { Strings(lang: lang) }
    var isDemo: Bool { demo != nil }
    var source: Source { isDemo ? .demo : .live }
    var current: StatusFrame? { isDemo ? demoLast : liveLast }
    var currentAt: Date? { isDemo ? demoLastAt : liveLastAt }
    var history: [HistPoint] { isDemo ? demoHist : liveHist }

    init() {
        let ud = UserDefaults.standard
        lang = Lang(rawValue: ud.string(forKey: "hg.lang") ?? "el") ?? .el
        familyName = ud.string(forKey: "hg.famname") ?? ""
        routine = Routine.load()
        summaryOn = ud.object(forKey: "hg.summary") as? Bool ?? true
        wearerName = ud.string(forKey: "hg.name") ?? "Μαρία"
        wearerPhone = ud.string(forKey: "hg.phone") ?? ""
        age = ud.object(forKey: "hg.age") as? Int ?? 78
        sexMale = ud.object(forKey: "hg.sexm") as? Bool ?? false
        bmi = ud.object(forKey: "hg.bmi") as? Double ?? 26.0
        medFlags = ud.object(forKey: "hg.meds") as? Int ?? 0
        restHR = ud.object(forKey: "hg.resthr") as? Int ?? 70
        locationOn = ud.object(forKey: "hg.location") as? Bool ?? true
        meds = medStore.meds
        reportOn = ud.object(forKey: "hg.report.on") as? Bool ?? true
        reportConsentAt = ud.object(forKey: "hg.report.consent") as? Date
        plan = Plan.bundled()
        liveHist = AppModel.loadHistory()
        lastSyncAt = ud.object(forKey: "hg.lastsync") as? Date   // after every stored property is initialised

        link.onPhase = { [weak self] p in self?.phase = p; self?.towerPhase(p) }
        link.onStatusBytes = { [weak self] b in self?.ingest(b, source: .live, at: Date()) }
        link.onInfo = { [weak self] i in self?.ingestInfo(i) }
        link.onWrite = { [weak self] label, hex in self?.logWrite(label, hex, simulated: false) }
        link.onEventBytes = { [weak self] b in self?.ingestEvent(b, at: Date()) }
        link.onReady = { [weak self] in self?.onConnectedWrites() }
        link.onEventsReady = { [weak self] in self?.sendSync() }
        AlertFX.shared.onAction = { [weak self] id, info, done in
            guard let self = self else { done(); return }
            self.handleNotificationAction(id, info: info, done: done)
        }
        AlertFX.shared.registerCategories(Strings(lang: lang))
        // A band was paired before: create the central now so iOS can restore / reconnect it in the background.
        if BandLink.hasSavedBand { link.connect() }

        clockTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            self?.now = Date()
            self?.herDayTick()
        }
        rescheduleSummary()
        wireHerDay()
        wireTower()
    }

    // MARK: the one decoder path

    static func viewState(_ d: StatusFrame?) -> String {
        guard let d = d else { return "WAIT" }
        if d.notWorn { return "NOT_WORN" }
        return d.state
    }

    /// INFO is read on every connection. A changed boot count = the band restarted: its minute counter (and so the
    /// low 16 bits of its alarm ids) started again from 0, so forget the per-boot keys.
    private func ingestInfo(_ i: Frames.Info) {
        if let old = info, old.bootCount != i.bootCount {
            lastFamilyKey[.live] = nil
            lastCounter = nil
            ack1Key = nil
            ack1At = nil
        }
        info = i
    }

    func ingest(_ bytes: [UInt8], source: Source, at: Date, raiseAlerts: Bool = true) {
        // The band's seed value before its first guardian minute (20 zero bytes, CRC-valid): "waiting", no state,
        // nothing written to history. It also means the band has just started, so its counters restarted.
        if Frames.isEmptyStatus(bytes) {
            switch source {
            case .live:
                liveLast = nil
                liveLastAt = nil
                lastCounter = nil
            case .demo:
                demoLast = nil
                demoLastAt = nil
            }
            lastFamilyKey[source] = nil
            lastVS[source] = "WAIT"
            return
        }
        let d: StatusFrame
        do { d = try Frames.decodeStatus(bytes) } catch {
            if source == .live { stats.crcErrors += 1 }
            return
        }
        let vs = AppModel.viewState(d)
        let pt = HistPoint(t: at, vs: vs, core: d.hasEstimate ? d.coreC : nil, half: d.halfRangeC, fam: d.familyPending,
                           hr: d.hrBpm > 0 ? d.hrBpm : nil, activity: d.activity, routine: d.routineScore)
        switch source {
        case .live:
            stats.frames += 1
            if let lc = lastCounter {
                // A band restart sets the counter back to 0: a backward jump is not ~65k missed minutes.
                let step = (d.minuteCounter - lc + 65536) % 65536
                if step > 1 && step < 32768 { stats.gaps += step - 1 }
            }
            lastCounter = d.minuteCounter
            liveLast = d
            liveLastAt = at
            lastSyncAt = at
            liveHist.append(pt)
            ledger.add(d, at: at)
            let cut = at.addingTimeInterval(-8 * 86400)
            if let f = liveHist.first, f.t < cut { liveHist.removeAll { $0.t < cut } }
            saveCountdown -= 1
            if saveCountdown <= 0 { saveHistory(); ledger.save(); saveCountdown = 10 }
            towerOnLiveFrame(at)      // in the background, the band's minute frames are what wakes the Tower
        case .demo:
            demoLast = d
            demoLastAt = at
            demoHist.append(pt)
            synthDemoEvents(d, vs: vs, at: at)
        }
        // The band clears «family pending» once the alarm is acked or over. Forget the key then: the alarm id's low
        // 16 bits are the band's minute counter, so a later alarm can reuse the same id and must still alert.
        if !d.familyPending { lastFamilyKey[source] = nil }
        if raiseAlerts { checkAlert(d, vs: vs, source: source, at: at) }
        lastVS[source] = vs
    }

    // MARK: alert rule

    /// Port of onFamily(): a family alert is keyed by (source, alarm id) and raised once. On top of the dashboard,
    /// a rising DANGER or HELP state also takes over the screen (no alarm id yet, so no ack is sent for it).
    private func checkAlert(_ d: StatusFrame, vs: String, source: Source, at: Date) {
        if d.familyPending, let id = d.alarmId16 {
            let key = "\(source.rawValue):\(id)"
            guard lastFamilyKey[source] != key else {
                // Same alarm still pending on the band: the ack may have been lost (e.g. a disconnect). Re-send it.
                sendAck1(id: id, key: key, source: source, at: at, retry: true)
                return
            }
            lastFamilyKey[source] = key
            towerStatus(help: d.state == "HELP", source: source, at: at)   // THE TOWER: SMS to the family
            var a = AlertInfo(kind: d.state == "HELP" ? .help : .family, alarmId: id, source: source, at: at, frame: d)
            // The phone is the relay: tell the band the family was notified (0x12 type 1) so it can show
            // «Ειδοποιήσαμε την οικογένεια». Demo acks are recorded only, never sent to a real band.
            sendAck1(id: id, key: key, source: source, at: at, retry: false)
            a.acked1 = true
            raiseAlert(a)
        } else if (vs == "HELP" || vs == "DANGER"), lastVS[source] != vs {
            // lastVS nil (app just opened while the band is already in DANGER / HELP) also takes over the screen.
            if vs == "HELP" { towerStatus(help: true, source: source, at: at) }   // THE TOWER (dedupes with EVENTS 5)
            if let cur = alert, cur.source == source, cur.kind != .danger { return }   // a family alert is already up
            raiseAlert(AlertInfo(kind: vs == "HELP" ? .help : .danger, alarmId: nil, source: source, at: at, frame: d))
        }
    }

    /// FAMILY_ACK 1 for alarm `key`. A retry goes only to a connected live band, at most once every 30 s.
    private func sendAck1(id: Int, key: String, source: Source, at: Date, retry: Bool) {
        if retry {
            guard source == .live, link.isConnected else { return }
            if ack1Key == key, let t = ack1At, at.timeIntervalSince(t) < 30 { return }
        }
        sendCommand(Frames.cmdFamilyAck(type: 1, alarmId: UInt32(id)), label: retry ? "FAMILY_ACK 1 (again)" : "FAMILY_ACK 1",
                    source: source)
        if source == .live && link.isConnected {
            ack1Key = key
            ack1At = at
        }
    }

    private func raiseAlert(_ a: AlertInfo) {
        // Elder mode (the wearer's own phone): no family takeover, chime or notification about herself.
        if AppMode.current == .elder { return }
        // A live alert always wins over a demo one; a demo alert never hides a live one.
        if let cur = alert, cur.source == .live, a.source == .demo { return }
        alert = a
        muted = false
        AlertFX.shared.start()
        let l = L
        let prefix = a.source == .demo ? l.sim + " · " : ""
        // CHECK not answered (family pending without HELP) = the urgent "did not answer" notification.
        let title = prefix + (a.kind == .family ? l.notifCheckTitle : l.notifTitleFamily)
        let body = a.kind == .family ? l.notifCheckBody : alertTitle(a) + " — " + alertReason(a)
        var info: [AnyHashable: Any] = ["source": a.source.rawValue, "alert": a.id.uuidString]
        if let id = a.alarmId { info["alarmId"] = id }
        AlertFX.shared.post(title: title, body: body, id: a.id.uuidString, userInfo: info)
    }

    func alertTitle(_ a: AlertInfo) -> String {
        switch a.kind {
        case .help: return L.state("HELP").0
        case .danger: return L.state("DANGER").0
        case .family: return L.alertTitle
        }
    }
    func alertReason(_ a: AlertInfo) -> String {
        switch a.kind {
        case .help: return L.alertHelp
        case .danger: return L.alertDanger
        case .family: return L.alertNoPress
        }
    }

    /// «Σας καλώ»: FAMILY_ACK 2 (family replied, when there is an alarm id) + FAMILY_MSG 1, then the dialler.
    func ackCall() {
        guard let a = alert else { return }
        familyReply(msg: 1, alarmId: a.alarmId, source: a.source)
        alert = nil
        AlertFX.shared.stop()
        AlertFX.shared.clearDelivered()
        let digits = wearerPhone.filter { "+0123456789".contains($0) }
        if a.source == .live, !digits.isEmpty, let url = URL(string: "tel://" + digits) {
            UIApplication.shared.open(url)
        }
    }

    /// «Έρχομαι»: FAMILY_MSG 2, closes the alert.
    func ackComing() {
        guard let a = alert else { return }
        familyReply(msg: 2, alarmId: nil, source: a.source)
        dismissAlert()
    }

    /// «Το είδα»: FAMILY_MSG 3 («Η … είδε το μήνυμα ✓»), closes the alert.
    func ackSeen() {
        guard let a = alert else { return }
        familyReply(msg: 3, alarmId: nil, source: a.source)
        dismissAlert()
    }

    /// Closes the alert on this phone only; nothing is sent to the band
    /// (a HELP pressed by mistake is cancelled on the band itself: hold the button 2 s again).
    func dismissAlert() {
        alert = nil
        AlertFX.shared.stop()
        AlertFX.shared.clearDelivered()
    }

    func muteAlert() {
        muted = true
        AlertFX.shared.stop()
    }

    // MARK: commands

    /// Live alerts / live sends go to the band. Demo-sourced commands are only logged (labelled), like the
    /// dashboard's mock device that records every CMD write.
    func sendCommand(_ bytes: [UInt8], label: String, source: Source) {
        if source == .live && link.isConnected {
            link.send(bytes, label: label)
        } else {
            logWrite(label, Frames.toHex(bytes), simulated: true)
        }
    }

    /// User-initiated sends (plan, profile). In demo mode they are only logged (labelled SIMULATION), never written
    /// to a real band, even one that is connected; otherwise they go to the band when connected.
    @discardableResult
    func sendUser(_ frames: [([UInt8], String)]) -> Bool {
        if isDemo {
            for (b, l) in frames { logWrite(l, Frames.toHex(b), simulated: true) }
            return true
        }
        if link.isConnected {
            for (b, l) in frames { link.send(b, label: l) }
            return true
        }
        return false
    }

    func sendPlan() {
        guard let p = herPlan else { return }
        // The bundled CONSTRUCTED DEMO plan is not a forecast: it never goes to a real band.
        if p.isConstructedDemo && !isDemo {
            lastSendResult = L.notSentDemoPlan
            return
        }
        do {
            var fr: [([UInt8], String)] = try Frames.forecastChunks(p).enumerated().map { ($0.element, "FORECAST \($0.offset)") }
            fr.append((Frames.safeHoursFrame(p), "SAFE_HOURS"))
            if sendUser(fr) {
                if !isDemo { planOnBand = (planKey(p), Date()) }
                lastSendResult = isDemo ? "\(L.sim): 0x11 ×4, 0x14 (\(p.date)) — \(L.notSentDemo)"
                                        : "\(L.sent): 0x11 ×4, 0x14 (\(p.date))"
            } else {
                lastSendResult = L.needLink
            }
        } catch {
            lastSendResult = "\(error)"
        }
    }

    var profileLine: String {
        String(format: "profile %ld %ld %.1f %ld", age, sexMale ? 1 : 0, bmi, medFlags & 15)
    }

    func sendProfile(thermometer: Double?) {
        // Ranges = fw 0.9.5 hg_fw_sec.c: field 2 40..100, field 0 34..42 (HG_READING_MIN/MAX_C). Field 5 (meds, B5-v7)
        // is sent last: the b7-ble-sec command check rejects field 5 as "range" (one harmless rejection), so on 0.9.5
        // the medicines reach the band through the console `profile` line below.
        var fr: [([UInt8], String)] = [(Frames.cmdProfile(field: 2, value: Float(min(100, max(40, restHR)))), "PROFILE 2 rest HR")]
        if let t = thermometer, t >= 34, t <= 42 { fr.append((Frames.cmdProfile(field: 0, value: Float(t)), "PROFILE 0 thermometer")) }
        fr.append((Frames.cmdProfile(field: 5, value: Float(medFlags & 31)), "PROFILE 5 meds"))
        guard sendUser(fr) else { lastSendResult = L.needLink; return }
        var msg = "\(L.sent): " + fr.map { $0.1 }.joined(separator: ", ")
        if !isDemo && link.isConnected {
            if link.sendConsoleLine(profileLine) { msg += ", «\(profileLine)»" }
        } else {
            logWrite("UART " + profileLine, Frames.toHex(Array((profileLine + "\n").utf8)), simulated: true)
            msg = "\(L.sim): " + fr.map { $0.1 }.joined(separator: ", ") + " — " + L.notSentDemo
        }
        lastSendResult = msg
    }

    func logWrite(_ label: String, _ hex: String, simulated: Bool) {
        writes.insert(WriteLog(at: Date(), label: label, hex: hex, simulated: simulated), at: 0)
        if writes.count > 30 { writes.removeLast(writes.count - 30) }
    }

    // MARK: demo

    func startDemo(file: String = "sim_heatwave", from: Int? = nil, speed: Int = 60) {
        stopDemo()
        guard let r = Replay.bundled(file) else { return }
        let p = DemoPlayer(replay: r, file: file)
        p.speed = speed
        p.onFrame = { [weak self] b, t, _ in self?.ingest(b, source: .demo, at: t) }
        p.onTick = { [weak self] in self?.demoTick += 1 }
        demo = p
        // default start 13:00 on the heat-wave day: COOL from 13:30, family alert 14:03 (dashboard ?mock=1 uses 780)
        let start = from ?? (r.startMod != nil ? 780 : 0)
        seekDemo(start)
        p.play()
    }

    func stopDemo() {
        demo?.pause()
        demo = nil
        demoHist = []
        demoLast = nil
        demoLastAt = nil
        lastFamilyKey[.demo] = nil
        lastVS[.demo] = nil
        demoHotterTomorrow = false
        resetDemoLog()
        towerDemoStopped()
        if alert?.source == .demo { dismissAlert() }
    }

    func seekDemo(_ i: Int) {
        guard let p = demo else { return }
        demoHist = []
        lastFamilyKey[.demo] = nil
        lastVS[.demo] = nil
        resetDemoLog()
        if alert?.source == .demo { dismissAlert() }
        // Frames before the target become history in one assignment (no alerts); the target frame then goes
        // through ingest() like any other frame (a family-pending target raises the alert).
        var pts: [HistPoint] = []
        pts.reserveCapacity(i)
        p.seek(to: i) { b, t, _ in
            if let d = try? Frames.decodeStatus(b) {
                self.synthDemoEvents(d, vs: AppModel.viewState(d), at: t, bump: false)
                pts.append(HistPoint(t: t, vs: AppModel.viewState(d), core: d.hasEstimate ? d.coreC : nil, half: d.halfRangeC,
                                     fam: d.familyPending, hr: d.hrBpm > 0 ? d.hrBpm : nil, activity: d.activity, routine: d.routineScore))
            }
        }
        demoHist = pts + demoHist
    }

    /// For filming: jump to the recording's first family-alert minute; its real frame raises the alert through
    /// the normal decoder path.
    func triggerDemoAlert() {
        if demo == nil { startDemo() }
        guard let p = demo else { return }
        let wasPlaying = p.playing
        p.pause()
        seekDemo(p.replay.firstFamilyIndex ?? max(0, p.count - 1))
        if wasPlaying { p.play() }
    }

    func setDemoSpeed(_ s: Int) { demo?.speed = s; demoTick += 1 }
    func toggleDemoPlay() {
        guard let p = demo else { return }
        if p.playing { p.pause() } else {
            if p.index >= p.count - 1 { seekDemo(0) }
            p.play()
        }
    }

    // MARK: persistence (live history only)

    private static var historyURL: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("history.json")
    }
    private static func loadHistory() -> [HistPoint] {
        guard let d = try? Data(contentsOf: historyURL), let h = try? JSONDecoder().decode([HistPoint].self, from: d) else { return [] }
        let cut = Date().addingTimeInterval(-8 * 86400)
        return h.filter { $0.t >= cut }
    }
    func saveHistory() {
        let url = AppModel.historyURL
        try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        if let d = try? JSONEncoder().encode(liveHist) { try? d.write(to: url, options: .atomic) }
    }
}
