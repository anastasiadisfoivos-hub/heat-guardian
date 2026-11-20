// Strings of the visual UI (APP-UI). Family mode is English by default, Elder mode Greek by default; both
// languages for every line so one screen never mixes them (DESIGN.md §8). `she` = the wearer's pronoun.

import Foundation

extension Strings {
    private func she(_ male: Bool) -> String { male ? "he" : "she" }
    private func her(_ male: Bool) -> String { male ? "his" : "her" }
    private func herObj(_ male: Bool) -> String { male ? "him" : "her" }

    // MARK: onboarding
    var uiWhoUses: String { t("Ποιος χρησιμοποιεί αυτό το iPhone;", "Who uses this iPhone?") }
    var uiIWear: String { t("Φοράω το βραχιόλι", "I wear the band") }
    var uiIWearNote: String { t("Μία απλή οθόνη, με μεγάλα γράμματα", "One simple screen with big letters") }
    var uiImFamily: String { t("Είμαι από την οικογένεια", "I'm family") }
    var uiImFamilyNote: String { t("Δείτε πώς είναι και λάβετε ειδοποιήσεις", "See how they are and get alerts") }
    var uiChangeLater: String { t("Αλλάζει αργότερα στις Ρυθμίσεις.", "You can change this later in Settings.") }

    // MARK: family · today
    var uiPrevention: String { t("πρόληψη", "prevention") }
    func uiPreventionA11y(_ done: Int, _ total: Int) -> String {
        t("Πρόληψη: \(done) από \(total) έγιναν", "Prevention: \(done) of \(total) done")
    }
    var uiTodayCaption: String { t("ΣΗΜΕΡΑ", "TODAY") }
    var uiSeeAll: String { t("Όλα", "See all") }
    func uiNextOnBand(_ male: Bool) -> String { t("Επόμενο στο βραχιόλι", "Next on \(her(male)) band") }
    var uiFromBand: String { t("Από το βραχιόλι", "From the band") }
    func uiAskedOK(_ male: Bool) -> String { t("Ρώτησε «Είστε καλά;»", "Asked \(herObj(male)) \"Are you OK?\"") }
    func uiReminded(_ male: Bool) -> String { t("Το βραχιόλι θύμισε νερό", "\(she(male).capitalized) was reminded to drink") }
    var uiMoveCloser: String { t("Φέρτε το κινητό πιο κοντά", "Move the phone closer") }
    var uiBandAlone: String { t("Το βραχιόλι συνεχίζει και μόνο του", "The band keeps working alone") }
    func uiCallNow(_ male: Bool) -> String { t("Τηλεφωνήστε τώρα", "Call \(herObj(male)) now") }
    func uiCallSub(_ male: Bool) -> String { t("Πατήστε για κλήση · περιμένει", "Tap to call · \(she(male)) is waiting") }
    var uiCallAction: String { t("Κλήση", "Call") }
    func uiHome(_ c: Int) -> String { t("Σπίτι \(c)°", "Home \(c)°") }
    func uiPulse(_ b: Int) -> String { t("παλμοί \(b)", "pulse \(b)") }
    func uiBodyEst(_ s: String) -> String { t("Σώμα \(s)° εκτ.", "Body \(s)° est.") }
    func uiLastSeen(_ at: String, _ state: String) -> String { t("Τελευταία φορά \(at) · \(state)", "Last seen \(at) · \(state)") }
    var uiNothingYet: String { t("Τίποτα ακόμη σήμερα", "Nothing yet today") }
    func uiCallA11y(_ name: String) -> String { t("Κλήση \(name)", "Call \(name)") }
    var uiAddNumber: String { t("Προσθέστε τον αριθμό στις Ρυθμίσεις", "Add the number in Settings") }
    var uiLinkUp: String { t("βραχιόλι συνδεδεμένο", "band connected") }
    var uiLinkDown: String { t("βραχιόλι χωρίς σύνδεση", "band not connected") }
    var uiConnectHint: String { t("Συνδέστε το βραχιόλι στις Ρυθμίσεις", "Connect the band in Settings") }
    var uiWearer: String { t("Ο άνθρωπός σας", "Your person") }

    // MARK: family · tomorrow
    var uiMildDay: String { t("Ήπια μέρα", "Mild day") }
    func uiSafeOut(_ r: String) -> String { t("έξοδος \(r)", "safe out \(r)") }
    var uiStayIn: String { t("καλύτερα μέσα", "best stay in") }
    func uiOnBand(_ male: Bool, _ at: String) -> String { t("Στο βραχιόλι ✓ \(at)", "On \(her(male)) band ✓ \(at)") }
    var uiSendsItself: String { t("Πηγαίνει στο βραχιόλι μόνο του όταν είναι κοντά", "Goes to the band by itself when it is near") }
    var uiPlanned: String { t("ΥΠΕΝΘΥΜΙΣΕΙΣ", "REMINDERS") }
    var uiIndoorA11y: String { t("Θερμοκρασία μέσα στο σπίτι ανά ώρα", "Indoor temperature by hour") }
    var uiHourAxis: String { t("Ώρα", "Hour") }
    var uiNoPlan: String { t("Δεν υπάρχει ακόμη σχέδιο για αύριο.", "No plan for tomorrow yet.") }
    var uiSafeBand: String { t("ασφαλείς ώρες", "safe hours") }

    // MARK: family · history
    var uiDayLog: String { t("Η μέρα", "The day") }

    // MARK: family · settings
    var uiHerProfile: String { t("Το προφίλ", "Profile") }
    var uiHomeType: String { t("Σπίτι", "Home") }
    func uiHomeClass(_ c: String) -> String { t("Κατηγορία σπιτιού \(c)", "Home class \(c)") }
    var uiRoutine: String { t("Η μέρα του/της", "Daily routine") }
    var uiAdvanced: String { t("Για προχωρημένους", "Advanced") }
    var uiModeTitle: String { t("Αυτό το iPhone το χρησιμοποιεί", "This iPhone is used by") }
    var uiModeFamily: String { t("Η οικογένεια", "Family") }
    var uiModeElder: String { t("Όποιος φοράει το βραχιόλι", "The person wearing the band") }
    var uiAboutRelay: String {
        t("Οι ειδοποιήσεις φτάνουν όταν το κινητό σας είναι κοντά στο βραχιόλι· η ειδοποίηση μέσω internet είναι στα επόμενα βήματα.",
          "Alerts reach you when your phone is near the band; alerts over the internet are on the roadmap.")
    }
    var uiDemoSection: String { t("Επίδειξη", "Demo") }

    // MARK: family · alert
    func uiAlertLine(_ kind: AlertInfo.Kind, name: String, at: String, male: Bool) -> String {
        let n = name.isEmpty ? t("Το βραχιόλι", "The band") : name
        switch kind {
        case .help: return t("\(n): πάτησε ΒΟΗΘΕΙΑ · \(at)", "\(n) pressed HELP · \(at)")
        case .danger: return t("\(n): πολύ υψηλή θερμική καταπόνηση · \(at)", "\(n): very high heat strain · \(at)")
        case .family: return t("\(n): δεν απάντησε στο «Είστε καλά;» · \(at)", "\(n) didn't answer \"Are you OK?\" · \(at)")
        }
    }
    func uiCallHer(_ male: Bool) -> String { t("Τηλεφωνήστε", "Call \(herObj(male))") }
    var uiMuteA11y: String { t("Σίγαση ήχου", "Mute the sound") }

    // MARK: elder
    func uiGuidance(_ f: FieldState) -> String {
        switch f {
        case .ok: return t("Όλα είναι εντάξει.", "Everything is fine.")
        case .heat: return t("Μείνετε στη δροσιά, μέσα στο σπίτι.", "Stay somewhere cool, indoors.")
        case .water: return t("Πιείτε ένα ποτήρι νερό.", "Drink a glass of water.")
        case .danger: return t("Καθίστε σε δροσερό μέρος και πιείτε νερό.", "Sit somewhere cool and drink water.")
        case .help: return t("Ζητήσατε βοήθεια. Η οικογένεια ειδοποιείται.", "You asked for help. Your family is being told.")
        case .offline: return t("Το βραχιόλι δουλεύει και μόνο του.", "The band keeps working by itself.")
        }
    }
    var uiAreYouOK: String { t("Είστε καλά;", "Are you OK?") }
    var uiDone: String { t("Έγινε ✓", "Done ✓") }
    var uiImOK: String { t("Είμαι καλά", "I'm OK") }
    var uiHelp: String { t("ΒΟΗΘΕΙΑ", "HELP") }
    var uiHoldHint: String { t("Κρατήστε πατημένο", "Press and hold") }
    var uiHoldHintLong: String { t("Κρατήστε το πατημένο μέχρι να γεμίσει ο κύκλος.", "Keep it pressed until the circle is full.") }
    var uiHoldToCancel: String { t("Κρατήστε πατημένο για ακύρωση", "Press and hold to cancel") }
    var uiCancelQ: String { t("Ακύρωση;", "Cancel?") }
    var uiCancelYes: String { t("Ναι, ακύρωση", "Yes, cancel") }
    var uiCancelNo: String { t("Όχι, χρειάζομαι βοήθεια", "No, I need help") }
    var uiNoLink: String {
        t("Δεν υπάρχει σύνδεση με το βραχιόλι. Κρατήστε πατημένο το κουμπί του βραχιολιού.",
          "No connection to the band. Press and hold the button on the band.")
    }
    var uiFamilyMessage: String { t("Μήνυμα", "Message") }
    var uiSettingsHint: String { t("Ρυθμίσεις: κρατήστε πατημένη την ώρα", "Settings: press and hold the clock") }
    /// FAMILY_MSG 1/2/3 as the elder sees it, in the elder's language.
    func uiFamilyMsg(_ k: Int, name: String) -> String {
        if el { return familyMsgBand(k, name: name) }
        let n = name.isEmpty ? "Your family" : name
        switch k {
        case 1: return "\(n) is calling you"
        case 2: return "\(n) is coming"
        default: return "\(n) saw the message ✓"
        }
    }
}
