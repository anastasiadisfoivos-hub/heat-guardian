// THE TOWER engine: band input -> SMSRouter -> SMSText -> Outbox -> transport (Twilio or DRY-RUN), with retry timing
// and persistence. Pure Foundation: AppModel+Tower feeds it from BLE and drives `pump()` on a timer; TowerTests drive it
// with a fake clock and a fake HTTP client.
//
// Live vs DRY-RUN: complete Twilio credentials in the Keychain = live; none = DRY-RUN (the outbox shows the exact SMS,
// nothing leaves the phone). Demo / SIMULATION events are dry-run, whatever the credentials, unless the owner turned on
// «Αποστολή SMS και στην προσομοίωση» (prefs.smsInSimulation): then they go like live ones, the text ending « (δοκιμή)».
//
// [SMS-SHORTCUT] Sender: Twilio, or the iPhone Shortcut (default when no Twilio credentials are set). A Shortcut
// message is ONE outbox item per event (the recipient is chosen inside the Shortcut), always live (same dry-run rule
// for SIMULATION), sent one at a time: `runShortcut` (the app) opens the run-shortcut URL and `shortcutFinished`
// (the x-success / x-error callback) completes it. No callback within ShortcutAPI.timeout -> failed.

import Foundation

final class TowerEngine {
    enum Mode: Equatable { case live, dryRun }

    var prefs: TowerPrefs { didSet { if prefs != oldValue { persistPrefs(prefs) } } }
    var contacts: [FamilyContact] { didSet { if contacts != oldValue { save() } } }
    private(set) var outbox = Outbox()
    private(set) var memory = TowerMemory()
    private var demoMemory = TowerMemory()
    /// The last decision per input (diagnostics / History "SMS sent" marks).
    private(set) var lastDecision: TowerDecision?
    /// Input that wanted an SMS while no contact had a usable number.
    private(set) var noContactsAt: Date?

    let credentials: CredentialStore
    var makeHTTP: () -> HTTPClient
    var now: () -> Date
    /// false = no network path (NWPathMonitor in the app): live items wait without spending an attempt.
    var isOnline: () -> Bool = { true }
    /// Hop for transport completions (main queue in the app; inline in tests).
    var deliver: (@escaping () -> Void) -> Void = { $0() }
    var onChange: (() -> Void)?
    /// Called around a live send so the app can ask iOS for background time (beginBackgroundTask).
    var willSend: (() -> Void)?
    var didFinishSending: (() -> Void)?
    /// Opens the Shortcut for one outbox item (the app: UIApplication.open in the foreground, a notification to tap in
    /// the background). nil = Shortcut items wait in the queue.
    var runShortcut: ((_ id: String, _ url: URL) -> Void)?
    /// The Shortcut item launched and not yet called back (only one at a time: opening Shortcuts leaves the app).
    private(set) var shortcutInFlight: (id: String, at: Date)?

    private let fileURL: URL?
    private let persistPrefs: (TowerPrefs) -> Void
    private var inFlight = Set<String>()

    init(credentials: CredentialStore, fileURL: URL?, prefs: TowerPrefs = TowerPrefs(),
         persistPrefs: @escaping (TowerPrefs) -> Void = { _ in },
         makeHTTP: @escaping () -> HTTPClient = { URLSessionHTTP() }, now: @escaping () -> Date = { Date() }) {
        self.credentials = credentials
        self.fileURL = fileURL
        self.prefs = prefs
        self.persistPrefs = persistPrefs
        self.makeHTTP = makeHTTP
        self.now = now
        contacts = []
        load()
        outbox.recoverSending(now: now())
    }

    private var hasTwilio: Bool { credentials.load()?.isComplete == true }
    /// The sender in use: the owner's choice, else Twilio when its credentials are set, else the iPhone Shortcut.
    var sender: SMSSender { prefs.sender ?? (hasTwilio ? .twilio : .shortcut) }
    /// Live = messages really leave the phone (Twilio with credentials, or the Shortcut); else DRY-RUN.
    var mode: Mode { sender == .shortcut || hasTwilio ? .live : .dryRun }

    /// Contacts that can get an SMS (a number that normalises to E.164).
    var smsContacts: [(FamilyContact, String)] {
        contacts.compactMap { c in c.e164(defaultCountryCode: prefs.countryCode).map { (c, $0) } }
    }

    // MARK: input

    /// One band input. Returns the router's decision (SMS or in-app); SMS go to every contact through the outbox.
    @discardableResult
    func handle(_ input: TowerInput, wearerName: String, simulated: Bool = false) -> TowerDecision {
        let d: TowerDecision
        if simulated { d = SMSRouter.decide(input, prefs: prefs, memory: &demoMemory) }
        else { d = SMSRouter.decide(input, prefs: prefs, memory: &memory, now: now()) }
        lastDecision = d
        if case .sms(let kind, let prio, let key) = d {
            let simSend = simulated && prefs.smsInSimulation
            let body = SMSText.body(kind, name: wearerName, lang: prefs.smsLang) + (simSend ? SMSText.simulationMarker(prefs.smsLang) : "")
            let dry = (simulated && !simSend) || mode == .dryRun
            if sender == .shortcut {
                outbox.enqueue(body: body, to: ShortcutAPI.recipient, contactName: shortcutLabel, dedupeKey: key, priority: prio,
                               dryRun: dry, simulated: simulated, sender: .shortcut, now: now())
            } else {
                let to = smsContacts
                if to.isEmpty { noContactsAt = now() }
                for (c, n) in to {
                    outbox.enqueue(body: body, to: n, contactName: c.name, dedupeKey: key, priority: prio, dryRun: dry,
                                   simulated: simulated, now: now())
                }
            }
        }
        save()
        onChange?()
        pump()
        return d
    }

    /// «Test SMS» (Settings › Tower): one message to every contact, live or dry-run like the real ones.
    func sendTest(wearerName: String) { handle(.test, wearerName: wearerName) }

    /// «Test the Shortcut»: one live message «Heat Guardian: δοκιμή αποστολής» through the Shortcut, whatever the sender.
    func sendShortcutTest() {
        outbox.enqueue(body: ShortcutAPI.testBody(prefs.smsLang), to: ShortcutAPI.recipient, contactName: shortcutLabel,
                       dedupeKey: "shortcut-test-" + UUID().uuidString, priority: .followUp, dryRun: false, sender: .shortcut, now: now())
        save()
        onChange?()
        pump()
    }

    var shortcutLabel: String { "Shortcut «\(ShortcutAPI.name(prefs.shortcutName))»" }

    /// The x-success / x-error / x-cancel callback (or the app could not open Shortcuts). `id` nil = the one in flight.
    func shortcutFinished(_ id: String?, _ r: SendResult) {
        guard let id = id ?? shortcutInFlight?.id else { return }
        if shortcutInFlight?.id == id { shortcutInFlight = nil }
        inFlight.remove(id)
        outbox.complete(id, r, now: now())
        save()
        onChange?()
        pump()
    }

    /// A note on the item in flight (outbox screen), e.g. "waiting for a tap on the notification".
    func noteShortcut(_ id: String, _ text: String?) { outbox.note(id, text); save(); onChange?() }

    // MARK: sending

    /// Sends whatever is due. Safe to call often (timer, connectivity change, app foreground).
    func pump() {
        let t = now()
        if let f = shortcutInFlight, t.timeIntervalSince(f.at) > ShortcutAPI.timeout {
            shortcutInFlight = nil
            inFlight.remove(f.id)
            outbox.complete(f.id, .permanent("no answer from Shortcuts (is the Shortcut «\(ShortcutAPI.name(prefs.shortcutName))» there?)"), now: t)
        }
        let due = outbox.due(now: t)
        let creds = credentials.load()
        for it in due where !inFlight.contains(it.id) {
            if it.sender == .shortcut && !it.dryRun {
                // one at a time; the next one goes when this one calls back (the app is in front again by then)
                guard shortcutInFlight == nil, let run = runShortcut,
                      let url = ShortcutAPI.runURL(name: prefs.shortcutName, text: it.body, id: it.id) else { continue }
                outbox.markSending(it.id)
                inFlight.insert(it.id)
                shortcutInFlight = (it.id, t)
                run(it.id, url)
                continue
            }
            let transport: SMSTransport
            if it.dryRun {
                transport = DryRunTransport()
            } else {
                guard isOnline() else { continue }          // offline: wait, no attempt spent
                guard let c = creds, c.isComplete else {
                    outbox.markSending(it.id)
                    outbox.complete(it.id, .permanent("no Twilio credentials (Settings › Tower)"), now: t)
                    continue
                }
                transport = TwilioTransport(credentials: c, http: makeHTTP())
            }
            outbox.markSending(it.id)
            inFlight.insert(it.id)
            if !it.dryRun { willSend?() }
            let id = it.id, live = !it.dryRun
            transport.send(to: it.to, body: it.body) { [weak self] r in
                self?.deliver {
                    guard let self = self else { return }
                    self.inFlight.remove(id)
                    self.outbox.complete(id, r, now: self.now())
                    self.save()
                    self.onChange?()
                    if live { self.didFinishSending?() }
                }
            }
        }
        save()
        onChange?()
    }

    func retry(_ id: String) { outbox.retry(id, now: now()); save(); pump() }
    func clearOutbox() { outbox.clear(); inFlight.removeAll(); shortcutInFlight = nil; save(); onChange?() }
    /// The demo's dry-run SMS go when the demo stops (the live outbox is untouched).
    func clearSimulated() {
        outbox.removeSimulated(); demoMemory = TowerMemory()
        if let f = shortcutInFlight, !outbox.items.contains(where: { $0.id == f.id }) { shortcutInFlight = nil; inFlight.remove(f.id) }
        save(); onChange?()
    }
    var nextWake: Date? { outbox.nextWake }

    // MARK: persistence (Application Support/tower.json: contacts, outbox, router memory; no credentials)

    private struct File: Codable { var contacts: [FamilyContact]; var outbox: Outbox; var memory: TowerMemory }

    private func load() {
        guard let u = fileURL, let d = try? Data(contentsOf: u), let f = try? JSONDecoder().decode(File.self, from: d) else { return }
        contacts = f.contacts
        outbox = f.outbox
        memory = f.memory
    }

    func save() {
        guard let u = fileURL else { return }
        try? FileManager.default.createDirectory(at: u.deletingLastPathComponent(), withIntermediateDirectories: true)
        // Until first unlock (not "complete"): the Tower writes while the phone is locked in the background.
        if let d = try? JSONEncoder().encode(File(contacts: contacts, outbox: outbox, memory: memory)) {
            try? d.write(to: u, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
        }
    }

    static var defaultURL: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("tower.json")
    }
}
