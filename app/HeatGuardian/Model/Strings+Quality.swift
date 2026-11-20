// Strings for the band 0.9.9 alert-quality events (ECOSYSTEM_SPEC 5e): «Πάλι όλα καλά» and the Alert quality card.
// Plain words, no claims: "held back" says what the band saw, never that she was safe.

import Foundation

extension Strings {
    // ALL_CLEAR (EVENTS 12): the band's own words are «Πάλι όλα καλά»; a quiet row / status, never an alarm.
    var logAllClear: String { t("Πάλι όλα καλά", "Back to normal") }
    func logAllClearDetail(_ minutes: Int, familyCalled: Bool) -> String {
        let base = el ? "το επεισόδιο κράτησε \(minutes) λεπτά" : "the episode lasted \(minutes) min"
        return base + (familyCalled ? t(" · ειδοποιήθηκε η οικογένεια", " · family was alerted") : "")
    }
    /// Family Today subtitle: "Back to normal 15:20 · 42 min".
    func uiBackToNormal(_ time: String, _ minutes: Int) -> String {
        el ? "Πάλι όλα καλά \(time) · \(minutes) λεπτά" : "Back to normal \(time) · \(minutes) min"
    }
    /// Elder guidance line (Greek by default).
    func uiElderBackToNormal(_ time: String) -> String { t("Πάλι όλα καλά, από τις \(time).", "Back to normal since \(time).") }

    // Alert quality card
    var aqTitle: String { t("Ποιότητα ειδοποιήσεων", "Alert quality") }
    var aqWeek: String { t("Αυτή την εβδομάδα", "This week") }
    var aqSent: String { t("Στάλθηκαν", "Sent") }
    var aqHeld: String { t("Κρατήθηκαν", "Held back") }
    var aqAck: String { t("Απαντήθηκαν", "Acknowledged") }
    var aqMissed: String { t("Χάθηκαν", "Missed") }
    var aqNone: String { t("Καμία ειδοποίηση αυτή την εβδομάδα.", "No alerts this week.") }
    func aqSource(_ s: AlertQualityWeek.Source) -> String {
        switch s {
        case .scorecard: return t("Από τον πίνακα του βραχιολιού (0.9.9) και το ημερολόγιο.", "From the band's scorecard (0.9.9) and the log.")
        case .log: return t("Από το ημερολόγιο του βραχιολιού.", "From the band's log.")
        case .none: return t("Τα «κρατήθηκαν» χρειάζονται βραχιόλι 0.9.9.", "\"Held back\" needs band firmware 0.9.9.")
        }
    }
    func aqAvgAck(_ s: Int) -> String {
        let m = s / 60, r = s % 60
        let txt = m > 0 ? (el ? "\(m) λ. \(r) δ." : "\(m) min \(r) s") : (el ? "\(r) δ." : "\(r) s")
        return t("Μέσος χρόνος απάντησης ", "Average time to answer ") + txt
    }
    var aqHeldWhy: String { t("Γιατί κρατήθηκαν", "Why they were held back") }

    /// ALERT_HELD reasons in plain words.
    func heldReason(_ r: HeldReason) -> String {
        switch r {
        case .notWorn: return t("το βραχιόλι δεν φοριόταν", "band was not on the wrist")
        case .loose: return t("το βραχιόλι ήταν χαλαρό", "band was loose")
        case .skin: return t("η μέτρηση δέρματος δεν ήταν λογική", "skin reading was not plausible")
        case .ppg: return t("το σήμα παλμού ήταν αδύναμο", "pulse signal was too weak")
        case .shower: return t("ντους ή βρεγμένο δέρμα", "shower or wet skin")
        case .sun: return t("ήλιος πάνω στον αισθητήρα", "sun on the sensor")
        case .persist: return t("πέρασε μόνο του σε λίγα λεπτά", "settled by itself within minutes")
        case .repeated: return t("ίδιο επεισόδιο, δεν επαναλήφθηκε", "same episode, not repeated")
        case .oneEvidence: return t("μόνο ένα σημάδι (ζέστη ή σώμα), πιο ήπια", "only one sign (heat or body): softened")
        }
    }

    /// ALERT_HELD what.
    func heldWhat(_ w: HeldWhat) -> String {
        switch w {
        case .drink: return t("υπενθύμιση για νερό", "drink reminder")
        case .cool: return t("προειδοποίηση για δροσιά", "cool-down warning")
        case .nudge: return t("υπενθύμιση", "reminder")
        case .bedtime: return t("συμβουλή για τη νύχτα", "bedtime cooling tip")
        case .check: return t("ερώτηση «Είστε καλά;»", "\"Are you OK?\" check")
        }
    }
}
