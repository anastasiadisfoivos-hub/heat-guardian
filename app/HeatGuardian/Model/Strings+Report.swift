// Strings of the «Heat report for the doctor» (PDF made on the phone) and its screens. Greek / English.
// Claims (research report, "What the product must not claim or do"): never a body / core temperature number, strain
// only as the band's state words, "not a medical device, not a diagnosis", medicines only "ask your doctor whether
// this matters in heat", the questions are questions, never conclusions.

import Foundation

extension Strings {
    // band state words as the report shows them (the band's own Greek words; English adds the Greek in brackets)
    func rpStateWord(_ i: Int) -> String {
        let g = ["Όλα καλά", "Ζεστή μέρα", "Πολλή ζέστη"][max(0, min(2, i))]
        if el { return g }
        return ["All good", "Hot day", "Too hot"][max(0, min(2, i))] + " («" + g + "»)"
    }
    func rpStateShort(_ i: Int) -> String { el ? ["Όλα καλά", "Ζεστή μέρα", "Πολλή ζέστη"][max(0, min(2, i))] : ["All good", "Hot day", "Too hot"][max(0, min(2, i))] }

    func rpClass(_ c: MedClass) -> String {
        switch c {
        case .diuretic: return t("διουρητικό", "diuretic")
        case .betaBlocker: return t("β-αναστολέας", "beta-blocker")
        case .anticholinergic: return t("αντιχολινεργικό", "anticholinergic")
        case .antipsychotic: return t("αντιψυχωσικό", "antipsychotic")
        case .sglt2: return t("αναστολέας SGLT2", "SGLT2 inhibitor")
        case .other: return t("άλλο", "other")
        }
    }

    // screens
    var rpTitle: String { t("Αναφορά ζέστης για τον γιατρό", "Heat report for the doctor") }
    var rpShortTitle: String { t("Αναφορά για τον γιατρό", "Report for the doctor") }
    var rpPeriod: String { t("Περίοδος", "Period") }
    func rpDays(_ n: Int) -> String { el ? "\(n) ημέρες" : "\(n) days" }
    var rpIncludeName: String { t("Με το όνομά της", "Include her name") }
    var rpLanguage: String { t("Γλώσσα αναφοράς", "Report language") }
    var rpMake: String { t("Δημιουργία PDF", "Create PDF") }
    var rpShare: String { t("Κοινοποίηση…", "Share…") }
    var rpMaking: String { t("Δημιουργείται…", "Creating…") }
    var rpOff: String { t("Η αναφορά είναι κλειστή. Ανοίγει μόνο από το δικό της κινητό (Ρυθμίσεις).",
                          "The report is turned off. Only she can turn it on, in Settings on her phone.") }
    var rpToggle: String { t("Αναφορά για τον γιατρό", "Report for the doctor") }
    var rpToggleNote: String { t("Όταν είναι κλειστό, αυτό το κινητό δεν φτιάχνει αναφορά. Τα δεδομένα μένουν μόνο στο κινητό.",
                                 "When off, this phone makes no report. The data stays on the phone.") }
    var rpDeleteData: String { t("Διαγραφή δεδομένων αναφοράς", "Delete report data") }
    var rpPreviewNote: String { t("Μένει σε αυτό το κινητό μέχρι να πατήσετε «Κοινοποίηση».", "Stays on this phone until you tap Share.") }
    var rpNoData: String { t("Δεν υπάρχουν ακόμα αρκετά δεδομένα από το βραχιόλι για αυτή την περίοδο.",
                             "There is not enough data from the band for this period yet.") }

    // consent (first time)
    var rpConsentTitle: String { t("Πριν φτιάξετε την αναφορά", "Before you make the report") }
    var rpConsentBody: [String] {
        el ? ["Η αναφορά είναι ένα PDF για τον γιατρό της: ώρες ζέστης στο σπίτι και έξω, ζεστές νύχτες, τι έκανε το βραχιόλι και πώς απάντησε, σφυγμός σε ηρεμία, ύπνος, κίνηση, και τα φάρμακα που γράψατε.",
              "Φτιάχνεται μέσα σε αυτό το κινητό. Δεν στέλνεται πουθενά — ούτε σε εμάς. Φεύγει μόνο αν πατήσετε «Κοινοποίηση» και διαλέξετε σε ποιον.",
              "Είναι δεδομένα υγείας: χρειάζεται η δική της συγκατάθεση. Μπορεί να την ανακαλέσει όποτε θέλει και να κλείσει την αναφορά από το κινητό της.",
              "Δεν είναι ιατρική συσκευή ούτε διάγνωση. Δεν δείχνει θερμοκρασία σώματος."]
           : ["The report is a PDF for her doctor: hours of heat at home and outside, hot nights, what the band did and how she answered, resting pulse, sleep, movement, and the medicines you entered.",
              "It is made on this phone. It is not sent anywhere — not to us either. It leaves the phone only when you tap Share and choose who gets it.",
              "This is health data: it needs her consent. She can withdraw it at any time and turn the report off on her phone.",
              "It is not a medical device and not a diagnosis. It shows no body temperature."]
    }
    var rpConsentElder: String { t("Συμφωνώ να φτιάχνεται η αναφορά", "I agree to the report being made") }
    var rpConsentFamily: String { t("Εκείνη συμφώνησε να φτιάξω την αναφορά", "She agreed that I make this report") }
    var rpContinue: String { t("Συνέχεια", "Continue") }

    // medicines (Settings)
    var mlTitle: String { t("Τα φάρμακά της (για τον γιατρό)", "Her medicines (for the doctor)") }
    var mlAdd: String { t("Προσθήκη φαρμάκου", "Add a medicine") }
    var mlName: String { t("Όνομα (όπως στο κουτί)", "Name (as on the box)") }
    var mlClass: String { t("Κατηγορία (αν την ξέρετε)", "Type (if you know it)") }
    var mlClassNone: String { t("Δεν ξέρω", "Don't know") }
    var mlNote: String { t("Μένουν μόνο σε αυτό το κινητό. Μπαίνουν στην αναφορά για τον γιατρό με τη φράση «ρωτήστε τον γιατρό αν έχει σημασία στη ζέστη» — ποτέ συμβουλή να αλλάξει κάτι.",
                           "Stored on this phone only. They go into the doctor's report with \"ask your doctor whether this matters in heat\" — never advice to change anything.") }
    func mlGuess(_ c: MedClass) -> String { el ? "μάλλον \(rpClass(c)) (από το όνομα)" : "probably a \(rpClass(c)) (from the name)" }

    /// The report's own text, in the report's language (the PDF and its Python mirror draw exactly these).
    var rpLabels: [String: String] {
        [
            "title": rpTitle,
            "sim": "ΠΡΟΣΟΜΟΙΩΣΗ · SIMULATION",
            "sim_note": t("Δεδομένα επίδειξης, όχι πραγματικού ατόμου.", "Demo data, not a real person."),
            "disclaimer_el": "Δημιουργήθηκε από το Heat Guardian. Δεν είναι ιατρική συσκευή. Δεν είναι διάγνωση.",
            "disclaimer_en": "Generated by Heat Guardian. Not a medical device. Not a diagnosis.",
            "no_bodytemp": t("Η αναφορά δεν δείχνει θερμοκρασία σώματος: ένα βραχιόλι στον καρπό δεν τη μετρά αξιόπιστα. Η «καταπόνηση» φαίνεται μόνο με τις λέξεις του βραχιολιού.",
                         "This report shows no body temperature: a wrist band cannot measure it reliably. Strain appears only as the band's own words."),
            "name": t("Όνομα", "Name"),
            "period": t("Περίοδος", "Period"),
            "generated": t("Δημιουργήθηκε", "Generated"),
            "key": t("Με μια ματιά", "At a glance"),
            "questions": t("Ερωτήσεις για συζήτηση με τον γιατρό", "Questions to discuss with the doctor"),
            "questions_note": t("Προκύπτουν αυτόματα από τα δεδομένα. Είναι ερωτήσεις, όχι συμπεράσματα.",
                                "Made automatically from the data. They are questions, not conclusions."),
            "meds": t("Φάρμακα (όπως τα έγραψε η ίδια ή η οικογένεια)", "Medicines (as entered by her or the family)"),
            "meds_none": t("Δεν γράφτηκαν φάρμακα στην εφαρμογή.", "No medicines were entered in the app."),
            "meds_flag": t("ρωτήστε τον γιατρό αν έχει σημασία στη ζέστη", "ask your doctor whether this matters in heat"),
            "meds_guess": t("κατηγορία από το όνομα — ελέγξτε", "type guessed from the name — please check"),
            "daily": t("Κάθε μέρα", "Day by day"),
            "c_date": t("Ημέρα", "Day"),
            "c_data": t("Δεδ. ώρες", "Data h"),
            "c_home26": t("Σπίτι ≥26°", "Home ≥26°"),
            "c_home28": t("Σπίτι ≥28°", "Home ≥28°"),
            "c_out28": t("Έξω ≥28°", "Out ≥28°"),
            "c_night": t("Ζεστή νύχτα", "Hot night"),
            "c_state": t("Βραχιόλι", "Band word"),
            "c_nudges": t("Υπενθ. έγιναν/όλες", "Nudges done/all"),
            "c_checks": t("«Καλά;» απ./όλα", "Checks ans./all"),
            "c_alerts": t("Ειδοπ.", "Alerts"),
            "c_family": t("Οικογ.", "Family"),
            "c_held": t("Κρατ.", "Held"),
            "c_shift": t("Έξοδοι μετακ.", "Outings shifted"),
            "daily_note": t("Ώρες = ώρες με τον αέρα γύρω της (αισθητήρας του βραχιολιού) σε αυτή τη θερμοκρασία. «Σπίτι/Έξω» από το αν ήταν κοντά στο κινητό του σπιτιού. Ζεστή νύχτα = ο αέρας στο σπίτι έμεινε ≥26 °C τις περισσότερες ώρες 00–06. Βραχιόλι = η πιο έντονη λέξη της ημέρας. Κρατ. = ειδοποιήσεις που το βραχιόλι κράτησε πίσω (π.χ. ντους, χαλαρό λουρί). Έξοδοι = πρόταση «Η μέρα της» που ακολούθησε / όσες έγιναν.",
                              "Hours = hours with the air around her (the band's sensor) at that temperature. Home / Out from whether she was near the home phone. Hot night = the air at home stayed ≥26 °C for most of 00–06. Band word = the day's strongest band word. Held = alerts the band held back (e.g. shower, loose strap). Outings = Her Day suggestions followed / made."),
            "exposure": t("Ώρες ζέστης στο σπίτι, ανά θερμοκρασία αέρα", "Hours of heat at home, by air temperature"),
            "trends": t("Τάσεις", "Trends"),
            "t_hr": t("Σφυγμός σε ηρεμία σε σχέση με το συνηθισμένο της", "Resting pulse against her usual"),
            "t_hr_note": t("Χαμηλότερος σφυγμός όσο ήταν ακίνητη (10ο εκατοστημόριο). Συνηθισμένο = διάμεσος της περιόδου σε αυτό το κινητό· το «σωματικό δίδυμο» του βραχιολιού κρατά τη δική του τιμή.",
                           "Her low pulse while still (10th percentile). Usual = the period's median on this phone; the band's Body Twin keeps its own value."),
            "t_sleep": t("Ύπνος (εκτίμηση από την ακινησία του καρπού)", "Sleep (estimated from wrist stillness)"),
            "t_act": t("Κίνηση (ώρες με κίνηση)", "Movement (hours moving)"),
            "t_skin": t("Θερμοκρασία δέρματος στον καρπό — μόνο για πλαίσιο", "Wrist skin temperature — context only"),
            "t_skin_note": t("Μέτρηση του αισθητήρα στο δέρμα του καρπού: ακολουθεί τον χώρο. ΔΕΝ είναι θερμοκρασία σώματος.",
                             "The skin sensor's reading at the wrist: it follows the room. It is NOT body temperature."),
            "usual": t("συνηθισμένο", "usual"),
            "air_home": t("αέρας σπιτιού", "air at home"),
            "skin": t("δέρμα καρπού", "wrist skin"),
            "episodes": t("Επεισόδια ζέστης", "Heat episodes"),
            "episodes_none": t("Κανένα επεισόδιο σε αυτή την περίοδο.", "No episodes in this period."),
            "e_when": t("Πότε", "When"),
            "e_peak": t("Πιο έντονη λέξη", "Strongest word"),
            "e_did": t("Τι έκανε το βραχιόλι", "What the band did"),
            "e_end": t("Πώς τελείωσε", "How it ended"),
            "privacy": t("Ιδιωτικότητα", "Privacy"),
            "privacy_text": t("Η αναφορά φτιάχτηκε μέσα στο κινητό από τα δεδομένα του βραχιολιού. Δεν πέρασε από κανέναν διακομιστή και δεν τη βλέπει η Heat Guardian. Βγήκε από το κινητό μόνο επειδή κάποιος πάτησε «Κοινοποίηση». Είναι δεδομένα υγείας: σύμφωνα με τον ΓΚΠΔ (GDPR) χρειάζονται τη ρητή συγκατάθεσή της, που μπορεί να ανακαλέσει όποτε θέλει. Όποιος τη λαμβάνει είναι υπεύθυνος για το αντίγραφό του.",
                              "This report was made on the phone from the band's data. It did not pass through any server and Heat Guardian does not see it. It left the phone only because someone tapped Share. It is health data: under the EU GDPR it needs her explicit consent, which she can withdraw at any time. Whoever receives it is responsible for their copy."),
            "page": t("Σελίδα", "Page"),
            "footer": "Heat Guardian · " + t("όχι ιατρική συσκευή · όχι διάγνωση", "not a medical device · not a diagnosis"),
            "yes": t("ναι", "yes"),
            "no": t("όχι", "no"),
            "dash": "–",
        ]
    }

    // key figures
    func rpFigHotNights(_ n: Int) -> String { el ? "ζεστές νύχτες" : (n == 1 ? "hot night" : "hot nights") }
    var rpFigHome28: String { t("ώρες στο σπίτι ≥28 °C", "hours at home ≥28 °C") }
    var rpFigOut28: String { t("ώρες έξω ≥28 °C", "hours outside ≥28 °C") }
    var rpFigChecks: String { t("«Είστε καλά;» απαντήθηκαν", "\"Are you OK?\" answered") }
    var rpFigAlerts: String { t("ειδοποιήσεις / κρατήθηκαν", "alerts / held back") }
    var rpFigFamily: String { t("φορές ειδοποιήθηκε η οικογένεια", "times the family was contacted") }
    var rpFigShift: String { t("έξοδοι μετακινήθηκαν (ακολούθησε)", "outings shifted (followed)") }

    // episode lines
    var rpDidDrink: String { t("υπενθύμισε νερό", "reminded her to drink") }
    var rpDidCool: String { t("ζήτησε να πάει σε δροσιά", "asked her to move somewhere cooler") }
    var rpDidCheck: String { t("ρώτησε «Είστε καλά;»", "asked \"Are you OK?\"") }
    var rpDidDanger: String { t("έδειξε «Πολλή ζέστη»", "showed \"Too hot\"") }
    func rpDidImOK(_ min: Int?) -> String {
        let m = min.map { el ? " σε \($0) λ." : " after \($0) min" } ?? ""
        return t("απάντησε «Είμαι καλά»", "she answered \"I'm OK\"") + m
    }
    var rpDidHelp: String { t("πάτησε ΒΟΗΘΕΙΑ", "she pressed HELP") }
    var rpDidFamily: String { t("ειδοποιήθηκε η οικογένεια", "the family was contacted") }
    func rpDidNudges(_ done: Int, _ shown: Int) -> String { el ? "υπενθυμίσεις \(done)/\(shown) έγιναν" : "reminders \(done)/\(shown) done" }
    func rpDidHeld(_ n: Int, _ why: String) -> String { el ? "κράτησε πίσω \(n) (\(why))" : "held back \(n) (\(why))" }
    func rpEndClear(_ time: String, _ mins: Int) -> String { el ? "Πάλι όλα καλά \(time) (\(mins) λεπτά)" : "Back to normal \(time) (\(mins) min)" }
    var rpEndUnknown: String { t("χωρίς «Πάλι όλα καλά» (βραχιόλι πριν το 0.9.9 ή το κινητό ήταν μακριά)",
                                 "no all-clear received (band before 0.9.9, or the phone was away)") }
    func rpEpisodesMore(_ n: Int) -> String { el ? "… και \(n) παλαιότερα επεισόδια" : "… and \(n) earlier episodes" }

    // questions (always questions, never conclusions)
    func rqHotNights(_ n: Int, _ dates: String, fluidPlan: Bool) -> String {
        if fluidPlan {
            return el ? "\(n) ζεστές νύχτες (\(dates)). Με τα φάρμακά της, πόσο πρέπει να πίνει τις ζεστές μέρες;"
                      : "\(n) hot nights (\(dates)). With her medicines, how much should she drink on hot days?"
        }
        return el ? "\(n) ζεστές νύχτες (\(dates)). Έπινε αρκετά νερό; Κοιμόταν καλά;"
                  : "\(n) hot nights (\(dates)). Was she drinking enough? Did she sleep well?"
    }
    func rqRestHR(_ n: Int, _ by: Int, _ dates: String) -> String {
        el ? "Ο σφυγμός της σε ηρεμία ήταν \(by)+ πάνω από το συνηθισμένο \(n) μέρες (\(dates)). Χρειάζεται να το δούμε;"
           : "Her resting pulse was \(by)+ above her usual on \(n) days (\(dates)). Is this worth checking?"
    }
    func rqChecks(_ missed: Int, _ asked: Int) -> String {
        el ? "Δεν απάντησε στο «Είστε καλά;» \(missed) από \(asked) φορές. Υπάρχει κάτι που της δυσκολεύει την απάντηση (ακοή, όραση, κούραση);"
           : "She did not answer \"Are you OK?\" \(missed) of \(asked) times. Is there anything that makes answering hard (hearing, eyesight, tiredness)?"
    }
    func rqHome28(_ h: Int) -> String {
        el ? "Πέρασε \(h) ώρες στο σπίτι με αέρα 28 °C ή πάνω. Υπάρχει πιο δροσερό μέρος για τις πιο ζεστές ώρες;"
           : "She spent \(h) hours at home in air of 28 °C or more. Is there a cooler place for the hottest hours?"
    }
    func rqMeds(_ names: String) -> String {
        el ? "Παίρνει \(names). Έχει σημασία στη ζέστη;" : "She takes \(names). Does this matter in heat?"
    }
    func rqSleep(_ mins: Int) -> String {
        el ? "Τις ζεστές νύχτες κοιμήθηκε περίπου \(mins) λεπτά λιγότερο (εκτίμηση). Έχει σημασία για εκείνη;"
           : "On hot nights she slept about \(mins) min less (estimated). Does that matter for her?"
    }
    func rqActivity(_ pct: Int) -> String {
        el ? "Τις πιο ζεστές μέρες κινήθηκε περίπου \(pct)% λιγότερο. Είναι αναμενόμενο για εκείνη;"
           : "On the hottest days she moved about \(pct)% less. Is that expected for her?"
    }
    var rqNone: String { t("Τίποτα δεν ξεχώρισε σε αυτή την περίοδο. Υπάρχει κάτι που θέλετε να προσέξουμε το επόμενο κύμα ζέστης;",
                           "Nothing stood out in this period. Is there anything to watch for in the next heat wave?") }
}
