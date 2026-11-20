// THE TOWER routing table (owner decision Nov 19): which band event becomes an SMS to the family, and which stays
// in the app. One pure function (SMSRouter.decide) + the table as data (SMSRouter.table, shown in Settings › Tower and
// tested row by row in TowerTests).
//
//   band event                                     -> what the family gets
//   HELP held (EVENTS 5, or STATUS HELP rising)     -> SMS at once (urgent)
//   HELP cancelled (EVENTS 6) after a HELP SMS      -> SMS follow-up "cancelled" (else in-app only)
//   LD_ESCALATED 1 Danger line (EVENTS 20)          -> SMS at once (urgent)
//   LD_ESCALATED 2 still heating after cooling down -> SMS at once (urgent; "water did not help, moved somewhere cooler…")
//   family alert in STATUS without a ladder event   -> SMS at once (urgent; older bands / the frozen CHECK path)
//   LD_NOTE 1 water did not help                    -> SMS if "notes by SMS" is on (default on), else in-app
//   LD_NOTE 2 no response to a reminder             -> SMS if "notes by SMS" is on (default on), else in-app
//   LD_NOTE 3 responsive during an escalation       -> SMS follow-up "she is responsive" (the alert stays)
//   LD_WORKED 3 after an escalation SMS             -> SMS follow-up "stopped heating up" (else in-app)
//   LD_REMIND / LD_DONE / LD_WORKED 1-2             -> in-app (History) only
//   band disconnected                               -> in-app only; SMS after 60 min if the owner turned it on
//   BATT_CRITICAL (EVENTS 15) / POWER_OFF 3          -> ONE SMS (note; key "battery", so the POWER_OFF that follows
//                                                      a second later is a duplicate); in-app only when it reaches
//                                                      the phone > 30 min late (a SYNC after she recharged)
//   BATT_LOW (EVENTS 23)                            -> in-app (History) only
//   POWER_OFF 1-2 / HAPTIC_LOST                     -> in-app only

import Foundation

/// Inputs the Tower reacts to (built by AppModel+Tower from EVENTS, STATUS and the link state).
enum TowerInput: Equatable {
    case help(at: Date)
    case helpCancel(at: Date)
    case ladder(LadderEvent, at: Date)
    case familyAlertNoAnswer(at: Date)
    case bandDisconnected(since: Date, now: Date)
    case test
}

enum SMSPriority: Int, Codable, Comparable {
    case followUp = 0, note = 1, urgent = 2
    static func < (a: SMSPriority, b: SMSPriority) -> Bool { a.rawValue < b.rawValue }
}

enum TowerDecision: Equatable {
    /// Send `kind` to every contact. `dedupeKey`: one SMS per key and recipient inside the dedupe window.
    case sms(SMSKind, priority: SMSPriority, dedupeKey: String)
    /// Stays in the app (History); `reason` says why, for the outbox / diagnostics.
    case inApp(reason: String)
}

/// What the router remembers between events (episode context for follow-ups; kept by TowerEngine).
struct TowerMemory: Codable, Equatable {
    var lastHelpSMSAt: Date?
    var lastUrgentSMSAt: Date?
    var waterFailedAt: Date?
    var disconnectNotified: Date?        // the `since` of the outage an SMS was already sent for
}

enum SMSRouter {
    static let followUpWindow: TimeInterval = 2 * 3600   // a follow-up only makes sense after an urgent SMS this recent
    static let waterContext: TimeInterval = 90 * 60      // "water did not help" belongs to the same episode
    /// A battery-ended event that reaches the phone later than this (SYNC after a recharge) is history, not news.
    static let batteryNews: TimeInterval = 30 * 60

    /// `now`: when the phone handles it (nil = the event's own time; only the battery SMS looks at it).
    static func decide(_ input: TowerInput, prefs: TowerPrefs, memory m: inout TowerMemory, now: Date? = nil) -> TowerDecision {
        func recent(_ d: Date?, _ now: Date, _ w: TimeInterval) -> Bool { d.map { now.timeIntervalSince($0) <= w && now >= $0.addingTimeInterval(-60) } ?? false }
        switch input {
        case .test:
            return .sms(.test, priority: .followUp, dedupeKey: "test-" + UUID().uuidString)
        case .help(let at):
            m.lastHelpSMSAt = at; m.lastUrgentSMSAt = at
            return .sms(.help(at: at), priority: .urgent, dedupeKey: "help")
        case .helpCancel(let at):
            guard recent(m.lastHelpSMSAt, at, followUpWindow) else { return .inApp(reason: "help-cancel-no-help-sms") }
            m.lastHelpSMSAt = nil
            return .sms(.helpCancelled(at: at), priority: .followUp, dedupeKey: "help-cancel")
        case .familyAlertNoAnswer(let at):
            m.lastUrgentSMSAt = at
            return .sms(.noAnswer(at: at), priority: .urgent, dedupeKey: "escalation")
        case .bandDisconnected(let since, let now):
            let minutes = Int(now.timeIntervalSince(since) / 60)
            guard prefs.disconnectSMS else { return .inApp(reason: "disconnect-sms-off") }
            guard minutes >= prefs.disconnectMinutes else { return .inApp(reason: "disconnect-too-short") }
            guard m.disconnectNotified != since else { return .inApp(reason: "disconnect-already-sent") }
            m.disconnectNotified = since
            return .sms(.bandDisconnected(minutes: minutes), priority: .note, dedupeKey: "disconnected")
        case .ladder(let e, let at):
            switch e {
            case .escalated(.dangerLine, _, _):
                m.lastUrgentSMSAt = at
                return .sms(.escalatedDanger(at: at), priority: .urgent, dedupeKey: "escalation")
            case .escalated(.stillHeating, _, _):
                m.lastUrgentSMSAt = at
                return .sms(.escalatedStillHeating(at: at, afterWater: recent(m.waterFailedAt, at, waterContext)),
                            priority: .urgent, dedupeKey: "escalation")
            case .note(.waterDidNotHelp, _, _, _):
                m.waterFailedAt = at
                return prefs.notesBySMS ? .sms(.waterDidNotHelp(at: at), priority: .note, dedupeKey: "note-water")
                                        : .inApp(reason: "notes-by-sms-off")
            case .note(.noResponse, let step, _, _):
                return prefs.notesBySMS ? .sms(.noResponse(step: step ?? .water, at: at), priority: .note, dedupeKey: "note-noresponse")
                                        : .inApp(reason: "notes-by-sms-off")
            case .note(.responsive, _, _, _):
                return .sms(.responsive(at: at), priority: .followUp, dedupeKey: "responsive")
            case .worked(.escalation, _, _):
                guard recent(m.lastUrgentSMSAt, at, followUpWindow) else { return .inApp(reason: "worked") }
                m.lastUrgentSMSAt = nil
                return .sms(.settled(at: at), priority: .followUp, dedupeKey: "settled")
            case .reminder: return .inApp(reason: "reminder")
            case .done: return .inApp(reason: "done")
            case .worked: return .inApp(reason: "worked")
            case .batteryCritical, .powerOffBattery:
                if let n = now, n.timeIntervalSince(at) > batteryNews { return .inApp(reason: "battery-old") }
                return .sms(.batteryEnded(at: at), priority: .note, dedupeKey: "battery")
            case .powerOff, .batteryLow, .hapticLost: return .inApp(reason: "band-status")
            }
        }
    }

    /// The table as the owner reads it (Settings › Tower): (event, Greek rule, English rule).
    static let table: [(event: String, el: String, en: String)] = [
        ("HELP", "Κράτησε το κουμπί ΒΟΗΘΕΙΑ → SMS αμέσως", "HELP held → SMS at once"),
        ("HELP_CANCEL", "Ακύρωσε τη βοήθεια → SMS (μόνο αν στάλθηκε SMS βοήθειας)", "HELP cancelled → SMS (only after a HELP SMS)"),
        ("LD_ESCALATED 1", "Γραμμή κινδύνου → SMS αμέσως", "Danger line → SMS at once"),
        ("LD_ESCALATED 2", "Ζεσταίνεται ακόμα σε δροσερό μέρος → SMS αμέσως", "Still heating after cooling down → SMS at once"),
        ("STATUS family", "Δεν απάντησε στο βραχιόλι → SMS αμέσως", "Did not answer the band → SMS at once"),
        ("LD_NOTE 1", "Το νερό δεν βοήθησε → SMS αν «Σημειώσεις με SMS»", "Water did not help → SMS if \"Notes by SMS\""),
        ("LD_NOTE 2", "Δεν απάντησε στην υπενθύμιση → SMS αν «Σημειώσεις με SMS»", "No response to a reminder → SMS if \"Notes by SMS\""),
        ("LD_NOTE 3", "Πάτησε το κουμπί στον κίνδυνο → SMS «σας βλέπει»", "Pressed during an escalation → SMS \"responsive\""),
        ("LD_WORKED 3", "Σταμάτησε να ζεσταίνεται μετά από SMS κινδύνου → SMS", "Stopped heating after a danger SMS → SMS"),
        ("LD_REMIND / LD_DONE / LD_WORKED", "Υπενθύμιση, «έγινε», «δούλεψε» → μόνο στο ιστορικό", "Reminder, done, worked → History only"),
        ("disconnected", "Χωρίς σύνδεση → μόνο στην εφαρμογή (SMS μετά από 60 λεπτά αν το ανοίξετε)", "Band disconnected → in-app only (SMS after 60 min if turned on)"),
        ("BATT_CRITICAL", "Η μπαταρία τελείωσε, το βραχιόλι έκλεισε → ένα SMS", "Battery ran out, the band switched off → one SMS"),
        ("BATT_LOW / POWER_OFF / HAPTIC", "Χαμηλή μπαταρία, κλείσιμο, μοτέρ → μόνο στο ιστορικό", "Low battery, power off, motor → History only"),
    ]
}

extension SMSRouter {
    /// A band event from BEFORE this phone became the Tower: the band's RAM ring (64 events since its boot) is replayed
    /// on the very first SYNC_EVENTS (fresh install / first pairing), so HELPs and escalations from bench tests hours
    /// earlier would otherwise all go out as SMS at once. Those stay in History only. `towerSince` = the first live
    /// connection of this phone to a band; an event without a band clock counts as old only on that first link
    /// (`firstLink`), because its time is the phone's receive time. Events after `towerSince` (also late ones from a
    /// SYNC after an outage) are routed as usual: the SMS carries the band's time.
    static func predatesTower(eventAt: Date, clockKnown: Bool, towerSince: Date?, firstLink: Bool) -> Bool {
        guard let since = towerSince else { return false }
        return clockKnown ? eventAt < since.addingTimeInterval(-60) : firstLink
    }
}
