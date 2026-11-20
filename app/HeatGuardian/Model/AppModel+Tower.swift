// THE TOWER glue (owner decision Nov 19): her phone keeps the BLE link (bluetooth-central background mode + state
// restoration + pending reconnect, BandLink) and turns band events into SMS through TowerEngine.
//   EVENTS 5 HELP / 6 HELP_CANCEL / 14-21 (0.9.17 ladder)  -> ingestEvent -> towerHandle
//   STATUS family alert (CHECK unanswered, older bands) / HELP rising -> checkAlert -> towerStatus
//   HELP / cancel pressed on THIS phone                     -> towerPhoneHelp (SMS even when the band is out of reach)
//   link state                                              -> disconnected-since + the 60-min rule
//   EVENTS 22 GAUGE (0.9.18 live frame)                     -> towerGauge -> her balance gauge (never stored)
// Demo (SIMULATION) events go through the same path but are dry-run unless «Αποστολή SMS και στην προσομοίωση» is on.
// The band's replays (`replay`, `replay noresp`; 0.9.17-demo-b7n) mark their ladder EVENTS (LogEntry.isBandReplay): SIMULATION too.
// [SMS-SHORTCUT] iPhone Shortcut sender: in the foreground the run-shortcut URL opens at once; in the background iOS
// does not let an app open another app, so a notification «tap to send» is posted and the URL opens when the app
// comes to the front (tap, or simply opening it). Shortcuts calls back heatguardian://shortcut-done|error|cancel/<id>.

import Foundation
import UIKit

/// Holds the engine and the Tower's timers (AppModel extensions cannot add stored properties).
final class TowerHub {
    static let shared = TowerHub()
    let engine: TowerEngine
    var disconnectedSince: Date?
    var timer: Timer?
    var bgTask: UIBackgroundTaskIdentifier = .invalid
    var sendingLive = 0
    /// The newest GAUGE frame from the band (0.9.18+) and when the phone received it. In memory only.
    var gauge: BandGauge?
    var gaugeAt: Date?
    /// This connection is the phone's first link to a band (no SYNC cursor yet): its replayed ring is history.
    var firstLink = false
    /// [SMS-SHORTCUT] A Shortcut run that could not open in the background: opened when the app is active again.
    var pendingShortcut: (id: String, url: URL)?
    var pendingNotified = false

    private init() {
        let ud = UserDefaults.standard
        engine = TowerEngine(credentials: KeychainCredentialStore(), fileURL: TowerEngine.defaultURL,
                             prefs: TowerPrefs.load(ud), persistPrefs: { $0.save(ud) })
        engine.deliver = { f in DispatchQueue.main.async(execute: f) }
    }
}

extension AppModel {
    var tower: TowerEngine { TowerHub.shared.engine }
    var bandDisconnectedSince: Date? { TowerHub.shared.disconnectedSince }
    /// The first live connection of this phone to a band (SMSRouter.predatesTower). Persisted.
    var towerSince: Date? {
        get { UserDefaults.standard.object(forKey: "hg.tower.since") as? Date }
        set { UserDefaults.standard.set(newValue, forKey: "hg.tower.since") }
    }

    /// Called once from init.
    func wireTower() {
        let hub = TowerHub.shared
        hub.engine.onChange = { [weak self] in self?.towerVersion += 1 }
        // iOS gives a backgrounded app ~30 s per BLE wake-up: ask for a little more while a live SMS is in flight.
        hub.engine.willSend = {
            hub.sendingLive += 1
            if hub.bgTask == .invalid {
                hub.bgTask = UIApplication.shared.beginBackgroundTask(withName: "tower-sms") {
                    UIApplication.shared.endBackgroundTask(hub.bgTask); hub.bgTask = .invalid
                }
            }
        }
        hub.engine.didFinishSending = {
            hub.sendingLive = max(0, hub.sendingLive - 1)
            if hub.sendingLive == 0, hub.bgTask != .invalid { UIApplication.shared.endBackgroundTask(hub.bgTask); hub.bgTask = .invalid }
        }
        hub.engine.runShortcut = { [weak self] id, url in self?.towerOpenShortcut(id: id, url: url) }
        if BandLink.hasSavedBand && phase != .connected { hub.disconnectedSince = lastSyncAt ?? Date() }
        hub.timer = Timer.scheduledTimer(withTimeInterval: 20, repeats: true) { [weak self] _ in self?.towerTick() }
        hub.engine.pump()
    }

    /// Link phase changes (BandLink.onPhase): when the band went away, and when it came back.
    func towerPhase(_ p: BandLink.Phase) {
        let hub = TowerHub.shared
        if p == .connected {
            hub.disconnectedSince = nil
            hub.firstLink = store.cursorBoot == nil
            if towerSince == nil { towerSince = Date() }
        }
        else if hub.disconnectedSince == nil && BandLink.hasSavedBand { hub.disconnectedSince = Date() }
    }

    /// Every 20 s: retries that are due, and the band-disconnected rule.
    func towerTick() {
        let hub = TowerHub.shared
        if let since = hub.disconnectedSince, !isDemo, tower.prefs.disconnectSMS,
           Date().timeIntervalSince(since) >= Double(tower.prefs.disconnectMinutes * 60) {
            tower.handle(.bandDisconnected(since: since, now: Date()), wearerName: wearerName)
        }
        tower.pump()
    }

    /// Each live STATUS frame (once a minute): a backgrounded app gets no timers, but the band's notifications wake it,
    /// so due retries go out from here.
    func towerOnLiveFrame(_ at: Date) {
        if let w = tower.nextWake, w <= at { tower.pump() }
    }

    /// EVENTS 22 GAUGE (band 0.9.18): the band's own gauge step + dot for her screen (Balance.display).
    func towerGauge(_ ev: BandEvent, at: Date) {
        guard let g = ev.gauge else { return }
        let hub = TowerHub.shared
        hub.gauge = g
        hub.gaugeAt = at
        towerVersion += 1
        towerOnLiveFrame(at)
    }

    /// What her balance gauge shows now: the band's GAUGE when fresh, else `fallbackStep` (the STATUS tier).
    func balanceDisplay(now: Date, connected: Bool, fallbackStep: Int?) -> (step: Int?, dot: Double?) {
        let hub = TowerHub.shared
        let d = Balance.display(gauge: isDemo ? nil : hub.gauge, gaugeAt: hub.gaugeAt, now: now, connected: connected,
                                fallbackStep: fallbackStep)
        return (d.step, d.dot)
    }

    /// A new band log entry (live or demo).
    func towerHandle(_ e: LogEntry) {
        let input: TowerInput?
        switch e.kind {
        case .help: input = .help(at: e.at)
        case .helpCancel: input = .helpCancel(at: e.at)
        default: input = e.ladder.map { .ladder($0, at: e.at) }
        }
        guard let i = input else { return }
        // The first SYNC replays the band's ring from before this phone was the Tower: History only, no SMS.
        if !e.simulated, SMSRouter.predatesTower(eventAt: e.at, clockKnown: e.clockKnown, towerSince: towerSince,
                                                  firstLink: TowerHub.shared.firstLink) { return }
        tower.handle(i, wearerName: wearerName, simulated: e.simulated || e.isBandReplay)
    }

    /// STATUS side (checkAlert): a new family alarm / HELP rising. Dedupes with the EVENTS path (same keys).
    func towerStatus(help: Bool, source: Source, at: Date) {
        tower.handle(help ? .help(at: at) : .familyAlertNoAnswer(at: at), wearerName: wearerName, simulated: source == .demo)
    }

    /// HELP / cancel pressed on her phone: the SMS goes from here at once, even if the band is out of reach.
    func towerPhoneHelp(cancel: Bool) {
        let at = isDemo ? (currentAt ?? Date()) : Date()
        tower.handle(cancel ? .helpCancel(at: at) : .help(at: at), wearerName: wearerName, simulated: isDemo)
    }

    func towerDemoStopped() { tower.clearSimulated() }

    // MARK: iPhone Shortcut sender

    /// Opens the Shortcut for one outbox item (TowerEngine.runShortcut). Only an app in the foreground can open another.
    func towerOpenShortcut(id: String, url: URL) {
        let hub = TowerHub.shared
        switch UIApplication.shared.applicationState {
        case .active:
            hub.pendingShortcut = nil
            UIApplication.shared.open(url, options: [:]) { ok in
                if !ok { hub.engine.shortcutFinished(id, .permanent("could not open the Shortcuts app")) }
            }
        case .inactive:
            // in transition (coming back from Shortcuts, a system sheet over the app): opens on .active
            hub.pendingShortcut = (id, url); hub.pendingNotified = false
        default:
            hub.pendingShortcut = (id, url); hub.pendingNotified = false
            towerNotifyPendingShortcut()
        }
    }

    /// The app is (or went) to the background with a Shortcut run waiting: one «tap to send» notification, logged.
    func towerNotifyPendingShortcut() {
        let hub = TowerHub.shared
        guard let p = hub.pendingShortcut, !hub.pendingNotified else { return }
        hub.pendingNotified = true
        print("[HG] Tower: app in the background, the Shortcut waits for a tap on the notification (\(p.id))")
        tower.noteShortcut(p.id, L.twShortcutWaiting)
        AlertFX.shared.postShortcutTap(title: L.twShortcutTapTitle, body: L.twShortcutTapBody, id: "hg.shortcut." + p.id)
    }

    /// The app came to the front (scenePhase .active): a Shortcut run that waited for it opens now.
    func towerBecameActive() {
        let hub = TowerHub.shared
        guard let p = hub.pendingShortcut else { tower.pump(); return }
        hub.pendingShortcut = nil
        guard tower.outbox.items.contains(where: { $0.id == p.id && $0.status == .sending }) else { tower.pump(); return }
        if hub.pendingNotified { tower.noteShortcut(p.id, nil) }
        hub.pendingNotified = false
        UIApplication.shared.open(p.url, options: [:]) { ok in
            if !ok { hub.engine.shortcutFinished(p.id, .permanent("could not open the Shortcuts app")) }
        }
    }

    /// heatguardian://shortcut-done|error|cancel/<id> from Shortcuts (any other URL is ignored).
    func towerHandleURL(_ url: URL) {
        guard let cb = ShortcutAPI.parseCallback(url) else { return }
        tower.shortcutFinished(cb.id, cb.result)
    }

    /// Settings › Tower demo: water did not help -> cooler place -> still heating -> she presses -> settled, as band
    /// EVENTS frames (the band's own byte layout) through the normal decoder, labelled SIMULATION, always dry-run.
    func playLadderDemo() {
        if !isDemo { startDemo() }
        let base = currentAt ?? Date()
        let script: [(Int, LadderEvent)] = [
            (0, .reminder(step: .water, isRepeat: false, forecastC: 37.90)),
            (2, .done(step: .water, minutesAfterReminder: 2, forecastC: 37.92)),
            (22, .note(.waterDidNotHelp, about: .water, forecastC: 38.12, referenceC: 37.92)),
            (22, .reminder(step: .coolerPlace, isRepeat: false, forecastC: 38.12)),
            (24, .done(step: .coolerPlace, minutesAfterReminder: 2, forecastC: 38.13)),
            (44, .escalated(reason: .stillHeating, forecastC: 38.23, referenceC: 38.13)),
            (46, .note(.responsive, about: .escalation, forecastC: 38.23, referenceC: nil)),
            (70, .worked(step: .escalation, forecastC: 38.20, referenceC: 38.23)),
        ]
        let t0 = base.addingTimeInterval(-70 * 60)
        for (i, (min, ev)) in script.enumerated() {
            demoSeq += 1
            let enc = ev.encoded
            let at = t0.addingTimeInterval(Double(min * 60))
            let be = BandEvent(seq: 60000 + demoSeq, boot: 0, unix: UInt32(max(0, at.timeIntervalSince1970)), kindRaw: enc.type, arg: enc.arg, ext: enc.x)
            guard let back = try? Frames.decodeEvent(Frames.encodeEvent(be)),
                  var e = LogEntry.fromBand(back, receivedAt: at, simulated: true) else { continue }
            e.id = "sim-ladder-\(Int(base.timeIntervalSince1970))-\(i)"
            demoStore.add(e)
            towerHandle(e)
        }
        logChanged()
    }
}
