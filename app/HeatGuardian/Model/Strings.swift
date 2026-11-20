// Family-view strings, Greek first, English second. Ported from dashboard/js/i18n.js (+ the b7-ble-sec pairing lines).
// Claims stay inside DECISIONS M1-M13 / ARCHITECTURE §2: the band ESTIMATES (never "measures") body temperature;
// no fall detection; no "prevents"; not a medical device.

import Foundation

enum Lang: String, CaseIterable, Identifiable {
    case el, en
    var id: String { rawValue }
    var locale: Locale { Locale(identifier: self == .el ? "el_GR" : "en_GB") }
    var native: String { self == .el ? "Ελληνικά" : "English" }
}

struct Strings {
    let lang: Lang
    var el: Bool { lang == .el }
    func t(_ g: String, _ e: String) -> String { el ? g : e }

    // tabs
    var tabNow: String { t("Τώρα", "Now") }
    var tabTomorrow: String { t("Αύριο", "Tomorrow") }
    var tabWeek: String { t("Εβδομάδα", "Her week") }
    var tabSettings: String { t("Ρυθμίσεις", "Settings") }

    // states: (word, why)
    func state(_ k: String) -> (String, String) {
        switch k {
        case "OK": return el ? ("Όλα καλά", "Δεν χρειάζεται να κάνετε κάτι.") : ("All good", "Nothing to do.")
        case "DRINK": return el ? ("Πιείτε νερό", "Το βραχιόλι υπενθύμισε να πιει νερό.") : ("Drink water", "The band reminded the wearer to drink water.")
        case "COOL": return el ? ("Πηγαίνετε σε δροσιά", "Το βραχιόλι ζήτησε να πάει σε πιο δροσερό χώρο. Ένα τηλεφώνημα βοηθά.")
                               : ("Move somewhere cool", "The band asked the wearer to move somewhere cooler. A phone call helps.")
        case "DANGER": return el ? ("Κίνδυνος", "Πολύ υψηλή θερμική καταπόνηση. Τηλεφωνήστε τώρα.") : ("Danger", "Very high heat strain. Call now.")
        case "CHECK": return el ? ("Είστε καλά;", "Το βραχιόλι ρωτά και περιμένει να πατηθεί το κουμπί.") : ("Are you OK?", "The band is asking and waiting for a button press.")
        case "IMOK": return el ? ("Εντάξει", "Πατήθηκε το κουμπί: απάντησε ότι είναι καλά.") : ("OK", "The button was pressed: the wearer says they are OK.")
        case "BATTERY": return el ? ("Χαμηλή μπαταρία", "Χρειάζεται φόρτιση σήμερα.") : ("Battery low", "Needs charging today.")
        case "HELP": return el ? ("Ζητά βοήθεια", "Κράτησε πατημένο το κουμπί. Τηλεφωνήστε τώρα.") : ("Asking for help", "The button was held down. Call now.")
        case "NOT_WORN": return el ? ("Δεν φοριέται", "Το βραχιόλι δεν είναι στο χέρι.") : ("Not worn", "The band is not on the wrist.")
        default: return el ? ("Αναμονή", "Δεν έχει έρθει ακόμη μέτρηση από το βραχιόλι.") : ("Waiting", "No reading from the band yet.")
        }
    }

    /// Short state names for chart legends.
    func legendState(_ k: String) -> String {
        switch k {
        case "OK": return t("Όλα καλά", "All good")
        case "DRINK": return t("Νερό", "Drink")
        case "COOL": return t("Δροσιά", "Cool")
        case "DANGER": return t("Κίνδυνος", "Danger")
        default: return state(k).0
        }
    }

    // core estimate
    var coreLabel: String { t("Εκτίμηση θερμοκρασίας σώματος", "Body temperature estimate") }
    var coreNote: String { t("Υπολογίζεται από τον καρπό και τον παλμό. Δεν είναι θερμόμετρο.", "Worked out from the wrist and the pulse. It is not a thermometer.") }
    var coreWarming: String { t("Σε προθέρμανση", "Warming up") }
    var coreWarmingNote: String { t("Τα πρώτα λεπτά μετά το φόρεμα δεν δίνεται εκτίμηση.", "No estimate in the first minutes after the band goes on.") }
    var coreMid: String { t("μέση τιμή", "middle") }
    var estimate: String { t("ΕΚΤΙΜΗΣΗ", "ESTIMATE") }

    // vitals
    var hr: String { t("Παλμοί", "Heart rate") }
    var skin: String { t("Δέρμα", "Skin") }
    var room: String { t("Χώρος", "Room") }
    var battery: String { t("Μπαταρία", "Battery") }
    var contact: String { t("Επαφή", "Contact") }
    var bpm: String { t("παλμοί/λεπτό", "bpm") }
    var charging: String { t("φορτίζει", "charging") }
    var contactOK: String { t("Εφαρμόζει καλά", "Fits well") }
    var loose: String { t("Σφίξτε το λουράκι", "Tighten the strap") }
    var off: String { t("Φορέστε το βραχιόλι", "Put the band on") }
    func hrq(_ q: Int) -> String {
        let a = el ? ["χωρίς επαφή", "χαλαρό", "κίνηση", "ακανόνιστο", ""] : ["no contact", "loose", "movement", "irregular", ""]
        return q >= 0 && q < a.count ? a[q] : ""
    }
    func updated(_ m: Int) -> String {
        if el { return m <= 0 ? "Ενημέρωση μόλις τώρα" : (m == 1 ? "Ενημέρωση πριν 1 λεπτό" : "Ενημέρωση πριν \(m) λεπτά") }
        return m <= 0 ? "Updated just now" : (m == 1 ? "Updated 1 minute ago" : "Updated \(m) minutes ago")
    }
    var stale: String { t("Χάθηκε η σύνδεση με το βραχιόλι", "Lost the connection to the band") }

    // timeline
    var last24: String { t("Το τελευταίο 24ωρο", "Last 24 hours") }
    var theDay: String { t("Η μέρα", "The day") }
    var theSession: String { t("Η συνεδρία", "The session") }
    var estWithRange: String { t("Εκτίμηση με το εύρος της", "Estimate with its range") }
    var familyAlertMark: String { t("Ειδοποίηση οικογένειας", "Family alert") }
    var chartEmpty: String { t("Το διάγραμμα γεμίζει όσο το βραχιόλι στέλνει μετρήσεις, μία κάθε λεπτό.", "The chart fills as the band sends readings, one a minute.") }
    var minutesShort: String { t("λεπτά", "min") }

    // family alert
    var alertTitle: String { t("Ειδοποίηση για την οικογένεια", "Family alert") }
    var alertNoPress: String { t("Δεν πατήθηκε το κουμπί στο «Είστε καλά;».", "The button was not pressed after \"Are you OK?\".") }
    var alertHelp: String { t("Ζήτησε βοήθεια από το βραχιόλι.", "Help was requested from the band.") }
    var alertDanger: String { t("Το βραχιόλι εκτιμά πολύ υψηλή θερμική καταπόνηση.", "The band estimates very high heat strain.") }
    var call: String { t("Θα τηλεφωνήσω", "I'll call") }
    var sheIsOK: String { t("Είναι καλά", "They're OK") }
    var mute: String { t("Σίγαση", "Mute") }
    var relayed: String { t("Το βραχιόλι ενημερώθηκε ότι ειδοποιηθήκατε.", "The band was told that you were alerted.") }
    var callSent: String { t("Το βραχιόλι θα δείξει ότι τηλεφωνείτε.", "The band will show that you are calling.") }
    var notifTitleFamily: String { t("Heat Guardian: ειδοποίηση", "Heat Guardian: alert") }

    // connection
    var connectTitle: String { t("Συνδέστε το βραχιόλι", "Connect the band") }
    /// Pairing help by the band's firmware (INFO fw_version, BCD; nil = not connected yet). Only fw 0.9.5 has the
    /// pairing code and the 5-press pairing window; on 0.9.4 / 0.9.6 there is no code and 5 presses during a CHECK
    /// would answer «I'm OK».
    func connectBody(_ fw: Int?) -> String {
        guard let fw = fw else {
            return t("Κρατήστε το βραχιόλι κοντά στο iPhone και πατήστε Σύνδεση. Συνήθως δεν χρειάζεται κωδικός. Μόνο αν το iPhone ζητήσει κωδικό σύζευξης: πατήστε 5 φορές γρήγορα το κουμπί του βραχιολιού και γράψτε τους 6 αριθμούς που δείχνει.",
                     "Keep the band near the iPhone and tap Connect. Usually no code is needed. Only if the iPhone asks for a pairing code: press the band's button 5 times quickly and type the 6 digits the band shows.")
        }
        if fw == 0x0095 {
            return t("Κρατήστε το βραχιόλι κοντά στο iPhone. Πρώτη φορά: πατήστε 5 φορές γρήγορα το κουμπί του βραχιολιού· όταν το iPhone ζητήσει κωδικό, γράψτε τους 6 αριθμούς που δείχνει το βραχιόλι.",
                     "Keep the band near the iPhone. First time: press the band's button 5 times quickly; when the iPhone asks for a code, type the 6 digits the band shows.")
        }
        let v = Frames.bcdVersion(fw)
        return t("Κρατήστε το βραχιόλι κοντά στο iPhone και πατήστε Σύνδεση. Αυτό το βραχιόλι (fw \(v)) συνδέεται χωρίς κωδικό· δεν χρειάζεται να πατήσετε το κουμπί του.",
                 "Keep the band near the iPhone and tap Connect. This band (fw \(v)) connects without a code; there is no need to press its button.")
    }
    var connect: String { t("Σύνδεση", "Connect") }
    var disconnect: String { t("Αποσύνδεση", "Disconnect") }
    var forget: String { t("Ξεχάστε το βραχιόλι", "Forget this band") }
    var scanning: String { t("Αναζήτηση…", "Searching…") }
    var connecting: String { t("Σύνδεση…", "Connecting…") }
    var pairing: String { t("Σύζευξη… αν ζητηθεί κωδικός, γράψτε αυτόν που δείχνει το βραχιόλι.", "Pairing… if a code is asked for, type the one on the band.") }
    var connected: String { t("Συνδεδεμένο", "Connected") }
    var disconnected: String { t("Αποσυνδεδεμένο", "Not connected") }
    var reconnecting: String { t("Επανασύνδεση όταν είναι κοντά", "Reconnects when nearby") }
    var pairFailed: String { t("Η σύζευξη απορρίφθηκε (λάθος κωδικός ή κλειστό παράθυρο). Πατήστε 5 φορές γρήγορα το κουμπί του βραχιολιού και ξαναδοκιμάστε.",
                               "Pairing was refused (wrong code or the band's pairing window is closed). Press the band's button 5 times quickly and try again.") }
    var pairRemoved: String { t("Το βραχιόλι ξέχασε αυτό το iPhone. Ρυθμίσεις iPhone › Bluetooth › HeatGuardian › Παράβλεψη συσκευής, μετά ξανά Σύνδεση.",
                                "The band forgot this iPhone. iPhone Settings › Bluetooth › HeatGuardian › Forget This Device, then Connect again.") }
    var btOff: String { t("Το Bluetooth είναι κλειστό.", "Bluetooth is off.") }
    var btDenied: String { t("Η εφαρμογή δεν έχει άδεια Bluetooth. Ρυθμίσεις › Heat Guardian › Bluetooth.", "The app has no Bluetooth permission. Settings › Heat Guardian › Bluetooth.") }
    var failed: String { t("Η σύνδεση απέτυχε: ", "Could not connect: ") }
    var noConnection: String { t("Χωρίς σύνδεση", "No connection") }
    func lastKnown(_ state: String, _ at: String) -> String {
        el ? "Τελευταία γνωστή κατάσταση: «\(state)» (\(at)). Το βραχιόλι ίσως είναι μακριά, κλειστό ή χωρίς μπαταρία."
           : "Last known state: \"\(state)\" (\(at)). The band may be out of range, off or out of battery."
    }
    var notSentDemo: String { t("δεν στάλθηκε στο βραχιόλι (λειτουργία επίδειξης).", "not sent to the band (demo mode).") }
    var notSentDemoPlan: String { t("Δεν στάλθηκε: αυτό είναι το κατασκευασμένο σχέδιο επίδειξης, όχι πραγματική πρόγνωση. Φορτώστε ένα plan.json από το Tomorrow Engine.",
                                    "Not sent: this is the constructed demo plan, not a real forecast. Load a plan.json from the Tomorrow Engine.") }
    var needLink: String { t("Πρώτα συνδέστε το βραχιόλι.", "Connect the band first.") }
    var sent: String { t("Στάλθηκε", "Sent") }

    // tomorrow
    var tomorrow: String { t("Αύριο", "Tomorrow") }
    var safeTitle: String { t("Ώρες για έξοδο", "Hours for going out") }
    var noneSafe: String { t("Καμία ώρα δεν είναι ασφαλής για έξοδο.", "No hour is safe for going out.") }
    var heatDay: String { t("Ημέρα καύσωνα", "Heat-wave day") }
    var hotNight: String { t("Ζεστή νύχτα", "Hot night") }
    func waveDay(_ n: Int) -> String { el ? "\(n)η μέρα καύσωνα" : "Heat-wave day \(n)" }
    var advice: String { t("Συμβουλές", "Advice") }
    var legendOK: String { t("Μπορεί να βγει", "Fine to go out") }
    var legendShort: String { t("Σύντομα μόνο", "Short trips only") }
    var legendNight: String { t("Νύχτα", "Night") }
    var legendAvoid: String { t("Να μείνει μέσα", "Stay in") }
    var tIn: String { t("Μέσα στο σπίτι", "Indoors") }
    var tOut: String { t("Έξω", "Outdoors") }
    var sendToBand: String { t("Στείλτε στο βραχιόλι", "Send to the band") }
    var loadPlan: String { t("Άλλο αρχείο plan.json", "Another plan.json") }
    var onBand: String { t("Στο βραχιόλι", "On the band") }
    var planNote: String { t("Σχέδιο από προσομοίωση φυσικής, όχι ιατρική πρόβλεψη.", "A plan from a physics simulation, not a medical prediction.") }
    func source(_ s: String?) -> String {
        switch s {
        case "CONSTRUCTED DEMO DAY": return t("Κατασκευασμένη μέρα επίδειξης", "Constructed demo day")
        case "open-meteo": return t("Πρόγνωση Open-Meteo", "Open-Meteo forecast")
        case "cache": return t("Χθεσινή πρόγνωση", "Last night's forecast")
        default: return s ?? ""
        }
    }
    var temps: String { t("Θερμοκρασία", "Temperature") }

    // week
    var weekTitle: String { t("Η εβδομάδα της", "Her week") }
    var routine: String { t("Σταθερότητα ρουτίνας", "Routine regularity") }
    var routineNote: String { t("Από τη μάθηση ρουτίνας του βραχιολιού (0–100). «—» όσο ακόμη μαθαίνει.", "From the band's routine learning (0–100). \"—\" while it is still learning.") }
    var rest: String { t("Ξεκούραση", "Rest") }
    var restNote: String { t("Λεπτά με πολύ λίγη κίνηση του χεριού (ύπνος ή ανάπαυση), από το επιταχυνσιόμετρο.", "Minutes with very little wrist movement (sleep or rest), from the accelerometer.") }
    var hrTrend: String { t("Παλμοί ηρεμίας", "Resting heart rate") }
    var hrTrendNote: String { t("Μέσος όρος των έγκυρων μετρήσεων παλμού της μέρας.", "Average of the day's valid pulse readings.") }
    var alertsWeek: String { t("Ειδοποιήσεις", "Alerts") }
    var heatMinutes: String { t("Λεπτά σε επιφυλακή", "Minutes on alert") }
    var heatMinutesNote: String { t("Λεπτά σε ΝΕΡΟ, ΔΡΟΣΙΑ ή ΚΙΝΔΥΝΟ.", "Minutes in DRINK, COOL or DANGER.") }
    var learning: String { t("μαθαίνει", "learning") }
    var hoursShort: String { t("ώ", "h") }
    var noWeekData: String { t("Δεν υπάρχουν ακόμη ημέρες. Η εβδομάδα γεμίζει από τα μηνύματα του βραχιολιού όσο είναι συνδεδεμένο.",
                               "No days yet. The week fills from the band's messages while it is connected.") }
    var weekFromBand: String { t("Από τα μηνύματα του βραχιολιού σε αυτό το iPhone.", "From the band's messages received on this iPhone.") }
    var weekFromDemo: String { t("Μία μέρα προσομοίωσης (εικονικό άτομο 398). Οι άλλες μέρες δεν υπάρχουν στην καταγραφή.",
                                 "One simulated day (virtual person 398). The other days are not in the recording.") }
    var notWellbeingClaim: String { t("Τάσεις για να τις συζητήσετε, όχι διάγνωση.", "Trends to talk about, not a diagnosis.") }

    // demo
    var sim: String { t("ΠΡΟΣΟΜΟΙΩΣΗ", "SIMULATION") }
    var realData: String { t("ΠΡΑΓΜΑΤΙΚΑ ΔΕΔΟΜΕΝΑ", "REAL DATA") }
    var demo: String { t("Λειτουργία επίδειξης", "Demo mode") }
    var demoNote: String { t("Παίζει καταγραφές από τον ίδιο αποκωδικοποιητή με το βραχιόλι. Κάθε οθόνη γράφει ΠΡΟΣΟΜΟΙΩΣΗ.",
                             "Plays recordings through the same decoder as the band. Every screen says SIMULATION.") }
    var demoStart: String { t("Έναρξη επίδειξης", "Start demo") }
    var demoStop: String { t("Τέλος επίδειξης", "Stop demo") }
    var speed: String { t("Ταχύτητα", "Speed") }
    var play: String { t("Αναπαραγωγή", "Play") }
    var pause: String { t("Παύση", "Pause") }
    var recording: String { t("Καταγραφή", "Recording") }
    var jumpBefore: String { t("Λίγο πριν την ειδοποίηση", "Just before the alert") }
    var jumpMorning: String { t("Πρωί", "Morning") }
    var triggerAlert: String { t("Ειδοποίηση τώρα (για γύρισμα)", "Trigger alert now (for filming)") }
    var bandScreen: String { t("Στην οθόνη του βραχιολιού", "On the band screen") }

    // settings
    var band: String { t("Βραχιόλι", "Band") }
    var wearer: String { t("Ο άνθρωπός σας", "The wearer") }
    var name: String { t("Όνομα", "Name") }
    var phone: String { t("Τηλέφωνο", "Phone") }
    var age: String { t("Ηλικία", "Age") }
    var sex: String { t("Φύλο", "Sex") }
    var female: String { t("Γυναίκα", "Female") }
    var male: String { t("Άνδρας", "Male") }
    var bmi: String { t("Δείκτης μάζας σώματος", "BMI") }
    var meds: String { t("Φάρμακα", "Medicines") }
    var medBeta: String { t("Χάπι για πίεση/καρδιά που κόβει τους παλμούς (β-αναστολέας)", "Blood-pressure/heart pill that slows the pulse (beta-blocker)") }
    var medDiuretic: String { t("Χάπι για το νερό (διουρητικό)", "Water pill (diuretic)") }
    var medLowSweat: String { t("Φάρμακο που κόβει τον ιδρώτα (π.χ. για αλλεργία, ύπνο, κύστη, ψυχιατρικό)", "Medicine that reduces sweating (e.g. allergy, sleep, bladder, psychiatric)") }
    var medAce: String { t("Χάπι για την πίεση (ACE ή σαρτάνη)", "Blood-pressure pill (ACE inhibitor or ARB)") }
    var medOther: String { t("Άλλο φάρμακο που κόβει τους παλμούς, ή βηματοδότης", "Another pulse-slowing medicine, or a pacemaker") }
    var restHR: String { t("Παλμοί ηρεμίας", "Resting heart rate") }
    var thermo: String { t("Μέτρηση θερμομέτρου σήμερα (°C)", "Today's thermometer reading (°C)") }
    var thermoNote: String { t("Μόνο για προβολή: στενεύει το εύρος, δεν αλλάζει τους συναγερμούς.", "Display only: narrows the range, does not change the alarms.") }
    var sendProfile: String { t("Αποστολή στο βραχιόλι", "Send to the band") }
    var profileHow: String { t("Φάρμακα και παλμοί ηρεμίας: μήνυμα PROFILE. Ηλικία, φύλο, ΔΜΣ: γραμμή «profile» στην κονσόλα του βραχιολιού (αν υπάρχει) — αλλιώς γράψτε την από USB:",
                               "Medicines and resting HR: PROFILE frame. Age, sex, BMI: a «profile» line on the band's console (when present) — otherwise type it over USB:") }
    var language: String { t("Γλώσσα", "Language") }
    var diagnostics: String { t("Διαγνωστικά", "Diagnostics") }
    var frames: String { t("μηνύματα", "messages") }
    var crcRejected: String { t("απορρίφθηκαν (CRC)", "rejected (CRC)") }
    var gaps: String { t("χαμένα λεπτά", "missed minutes") }
    var lastWrites: String { t("Τελευταίες εντολές", "Last commands") }
    var model: String { t("Μοντέλο", "Model") }
    var about: String { t("Σχετικά", "About") }
    var footer: String { t("Το Heat Guardian εκτιμά τη θερμική καταπόνηση. Δεν είναι ιατρική συσκευή και δεν αντικαθιστά τον γιατρό. Δεν ανιχνεύει πτώσεις.",
                           "Heat Guardian estimates heat strain. It is not a medical device and does not replace a doctor. It does not detect falls.") }
    var notifPermission: String { t("Ειδοποιήσεις", "Notifications") }
    var notifNote: String { t("Για να ακούτε την ειδοποίηση και με το iPhone κλειδωμένο, αφήστε τις ειδοποιήσεις ανοιχτές.", "Keep notifications on to hear an alert while the iPhone is locked.") }
    var done: String { t("Τέλος", "Done") }
    var years: String { t("ετών", "y") }
}

/// English for the Tomorrow Engine's Greek advice lines (tomorrow/strings_el.json ids) — same table as i18n.js ADVICE_EN.
enum AdviceEN {
    private static let table: [(String, ([String]) -> String)] = [
        ("^Αύριο καύσωνας$", { _ in "Heat wave tomorrow" }),
        ("^Έξοδος (.+)$", { m in "Go out " + m[1] }),
        ("^Ώρες για έξοδο$", { _ in "Hours for going out" }),
        ("^Όχι έξοδος αύριο$", { _ in "No going out tomorrow" }),
        ("^Πίνετε άφθονα υγρά$", { _ in "Drink plenty of fluids" }),
        ("^Πιείτε νερό τώρα$", { _ in "Drink water now" }),
        ("^Πάτε κάπου δροσερό$", { _ in "Go somewhere cool" }),
        ("^Χλιαρό ντους$", { _ in "Lukewarm shower" }),
        ("^Είστε καλά; Πατήστε$", { _ in "Are you OK? Press" }),
        ("^Ανοίξτε στις (\\d+):00$", { m in "Open the windows at \(m[1]):00" }),
        ("^Κλειστά παράθυρα$", { _ in "Keep the windows closed" }),
        ("^Μην βγείτε στις (.+)$", { m in "Do not go out at \(m[1])" }),
        ("^Χθεσινή πρόγνωση$", { _ in "Last night's forecast" }),
        ("^Ανοίξτε τα παράθυρα$", { _ in "Open the windows at bedtime" }),
        ("^Κλείστε παράθυρα$", { _ in "Close the windows in the morning" }),
    ]

    static func translate(_ gr: String) -> String {
        let ns = gr as NSString
        for (pattern, f) in table {
            guard let re = try? NSRegularExpression(pattern: pattern) else { continue }
            if let m = re.firstMatch(in: gr, range: NSRange(location: 0, length: ns.length)) {
                var groups: [String] = []
                for i in 0..<m.numberOfRanges {
                    let r = m.range(at: i)
                    groups.append(r.location == NSNotFound ? "" : ns.substring(with: r))
                }
                return f(groups)
            }
        }
        return gr
    }
}
