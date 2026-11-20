// Ecosystem strings (ECOSYSTEM_SPEC §2–§5b), Greek first. Lines that quote the band keep its exact words.
// Family-facing lines describe the wearer in the third person. §6: all «…» band strings await Foivos's OK.

import Foundation

extension Strings {
    // tabs
    var tabToday: String { t("Σήμερα", "Today") }
    var tabHistory: String { t("Ιστορικό", "History") }

    // notification actions
    var actCall: String { t("Σας καλώ", "I'm calling") }
    var actComing: String { t("Έρχομαι", "I'm coming") }
    var actSeen: String { t("Το είδα", "Seen") }

    // origin
    func origin(_ o: Origin) -> String { o == .band ? t("βραχιόλι", "band") : t("εσείς", "you") }

    /// The band's nudge screen text (§2), exactly as on the band (Greek in both languages for the quote).
    func nudgeBandText(_ n: NudgeID, briefHour: Int?) -> String {
        switch n {
        case .brief: return briefHour.map { String(format: "Σήμερα ζέστη. Βγείτε πριν τις %02d:00", $0) } ?? "Σήμερα ζέστη. Μείνετε μέσα"
        case .lastCool: return "Τελευταία δροσερή ώρα για έξοδο"
        case .shutters: return "Κλείστε τα παντζούρια"
        case .water: return "Ώρα για ένα ποτήρι νερό"
        case .air: return "Ανοίξτε τα παράθυρα να δροσίσει"
        case .ac: return "Ανάψτε το κλιματιστικό"
        case .eveningBrief: return "Το σχέδιο για αύριο"
        case .leaveHot: return "Έξω κάνει ζέστη. Πάρτε νερό."
        }
    }
    /// Short family-facing name of a nudge.
    func nudgeName(_ n: NudgeID) -> String {
        switch n {
        case .brief: return t("Πρωινή ενημέρωση", "Morning brief")
        case .lastCool: return t("Τελευταία δροσερή ώρα", "Last cool hour")
        case .shutters: return t("Παντζούρια", "Shutters")
        case .water: return t("Νερό", "Water")
        case .air: return t("Αερισμός", "Air the home")
        case .ac: return t("Κλιματιστικό", "Air conditioning")
        case .eveningBrief: return t("Βραδινή ενημέρωση", "Evening brief")
        case .leaveHot: return t("Έξοδος στη ζέστη", "Leaving in the heat")
        }
    }
    func nudgeStatus(_ s: TimelineItem.NudgeStatus, _ fmt: (Date) -> String) -> String {
        switch s {
        case .upcoming: return t("Αναμένεται", "Upcoming")
        case .shown: return t("Στην οθόνη του βραχιολιού", "On the band now")
        case .done(let d): return t("Έγινε ✓ ", "Done ✓ ") + fmt(d)
        case .missed: return t("Δεν έγινε", "Missed")
        }
    }

    func warnLog(_ state: String) -> String {
        switch state {
        case "DRINK": return t("Προειδοποίηση: νερό", "Warning: drink water")
        case "COOL": return t("Προειδοποίηση: δροσιά", "Warning: move somewhere cool")
        case "DANGER": return t("Κίνδυνος", "Danger")
        case "CHECK": return t("Ρώτησε «Είστε καλά;»", "Asked \"Are you OK?\"")
        case "HELP": return t("Ζήτησε βοήθεια", "Asked for help")
        case "BATTERY": return t("Χαμηλή μπαταρία", "Battery low")
        case "NOT_WORN": return t("Δεν φοριέται", "Not worn")
        default: return state
        }
    }
    var logImOK: String { t("Πάτησε «Είμαι καλά»", "Pressed \"I'm OK\"") }
    var logHelp: String { t("Ζήτησε βοήθεια (κράτησε το κουμπί)", "Asked for help (held the button)") }
    var logHelpCancel: String { t("Ακύρωσε τη βοήθεια", "Cancelled the help request") }
    /// FAMILY_MSG 1/2/3 as the band shows it (§5).
    func familyMsgBand(_ msg: Int, name: String) -> String {
        let n = name.isEmpty ? "οικογένεια" : name
        switch msg {
        case 1: return "\(n): σας καλεί"            // exactly as band 0.9.7 shows it (ECOSYSTEM_SPEC 5c)
        case 2: return "\(n): έρχεται"
        default: return "\(n): είδε το μήνυμα ✓"
        }
    }
    func logFamilyMsgShown(_ msg: Int, name: String) -> String {
        if el { return "Το βραχιόλι έδειξε: «\(familyMsgBand(msg, name: name))»" }
        let n = name.isEmpty ? "family" : name
        let en = msg == 1 ? "\(n) is calling" : (msg == 2 ? "\(n) is coming" : "\(n) saw the message")
        return "The band showed: \"\(en)\""
    }
    func logFamilyMsgSent(_ msg: Int) -> String {
        switch msg {
        case 1: return t("Στείλατε «Σας καλώ»", "You sent \"I'm calling\"")
        case 2: return t("Στείλατε «Έρχομαι»", "You sent \"I'm coming\"")
        default: return t("Στείλατε «Το είδα»", "You sent \"Seen\"")
        }
    }
    func logAck(_ type: Int) -> String {
        type == 1 ? t("Η ειδοποίηση έφτασε σε εσάς", "The alert reached you") : t("Απαντήσατε στην ειδοποίηση", "You answered the alert")
    }
    var clockUnknown: String { t("ώρα λήψης", "time received") }

    /// «4/5 ✓ · 3 νερό · 0 προειδοποιήσεις»
    func summaryLine(_ s: DaySummary) -> String {
        el ? "\(s.nudgesDone)/\(s.nudgesShown) ✓ · \(s.water) νερό · \(s.warnings) προειδοποιήσεις"
           : "\(s.nudgesDone)/\(s.nudgesShown) ✓ · \(s.water) water · \(s.warnings) warnings"
    }
    var noEventsToday: String { t("Τίποτα ακόμη σήμερα.", "Nothing yet today.") }
    var noHistory: String { t("Δεν υπάρχουν ακόμη προηγούμενες μέρες.", "No past days yet.") }
    func lastSync(_ at: String) -> String { t("Τελευταίος συγχρονισμός ", "Last sync ") + at }

    // reason lines (§4); family-facing
    // (APP-UI: English added — DESIGN.md §8 forbids Greek and English on one screen; the band itself stays Greek.)
    func reasonHeat(_ c: Int) -> String { t("Πολλή ζέστη στο σπίτι \(c)°", "Very hot at home \(c)°") }
    var reasonLongHeat: String { t("Πολλές ώρες στη ζέστη", "Many hours in the heat") }
    var reasonBody: String { t("Το σώμα ζεσταίνεται", "Body warming") }
    var reasonNoAnswer: String { t("Δεν απάντησε στο «Είστε καλά;»", "Did not answer \"Are you OK?\"") }

    // notifications
    var notifCheckTitle: String { t("Δεν απάντησε στο «Είστε καλά;»", "No answer to \"Are you OK?\"") }
    var notifCheckBody: String { t("Το βραχιόλι ρώτησε και δεν πατήθηκε το κουμπί. Τηλεφωνήστε της.", "The band asked and the button was not pressed. Please call.") }
    var notifMissedTitle: String { t("Δύο υπενθυμίσεις δεν έγιναν", "Two reminders were missed") }
    func notifMissedBody(_ a: String, _ b: String) -> String { t("Χάθηκαν: \(a), \(b). Ίσως αξίζει ένα τηλεφώνημα.", "Missed: \(a), \(b). A call may help.") }
    var notifSummaryTitle: String { t("Η μέρα της", "Her day") }
    var summaryToggle: String { t("Βραδινή σύνοψη στις 20:30", "Evening summary at 20:30") }

    // settings
    var familySection: String { t("Εσείς", "You") }
    var familyName: String { t("Το όνομά σας στο βραχιόλι", "Your name on the band") }
    func familyNameNote(_ used: Int) -> String {
        t("Θα δει «…: σας καλεί». Έως 14 bytes (\(used)/14· ένα ελληνικό γράμμα = 2).", "The band shows it when you call or reply. Up to 14 bytes (\(used)/14; a Greek letter = 2).")
    }
    var routineSection: String { t("Η μέρα της (προαιρετικό)", "Her day (optional)") }
    var routineSeedNote: String { t("Κενό = το βραχιόλι μαθαίνει μόνο του. Όπου έχει μάθει ≥ 3 μέρες, κερδίζει ό,τι έμαθε.", "Empty = the band learns by itself. Where it has learned ≥ 3 days, what it learned wins.") }
    var wakeTime: String { t("Ξυπνά", "Wakes up") }
    var bedTime: String { t("Κοιμάται", "Goes to bed") }
    var napTime: String { t("Μεσημεριανός ύπνος", "Afternoon nap") }
    var outTime: String { t("Συνήθως έξω", "Usually out") }
    var hasAC: String { t("Κλιματιστικό στο σπίτι", "Air conditioning at home") }
    var floorLabel: String { t("Όροφος", "Floor") }
    var buildLabel: String { t("Σπίτι", "Home") }
    func floorName(_ f: Floor) -> String {
        switch f { case .ground: return t("Ισόγειο", "Ground floor"); case .middle: return t("Ενδιάμεσος", "Middle floor"); case .top: return t("Τελευταίος", "Top floor") }
    }
    func buildName(_ b: Build) -> String { b == .old ? t("Παλιό", "Old") : t("Με μόνωση", "Insulated") }
    var sendRoutine: String { t("Αποστολή στο βραχιόλι", "Send to the band") }
}
