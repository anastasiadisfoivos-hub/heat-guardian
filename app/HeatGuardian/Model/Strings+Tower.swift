// Strings of the three jobs (owner decision Nov 19): SETUP, THE TOWER (home, Settings › Tower, outbox) and HISTORY.
// Greek first, English second. The SMS texts themselves are in Model/Tower/SMSText.swift.

import Foundation

extension Strings {
    func twTime(_ d: Date) -> String {
        let c = Calendar.current.dateComponents([.hour, .minute], from: d)
        return String(format: "%02d:%02d", c.hour ?? 0, c.minute ?? 0)
    }

    // MARK: history (DayStory)
    func twReminder(_ s: LadderStep) -> String {
        switch s {
        case .water: return t("Υπενθύμιση: νερό", "Reminder: water")
        case .coolerPlace: return t("Υπενθύμιση: πιο δροσερό μέρος", "Reminder: somewhere cooler")
        case .escalation: return t("Έλεγχος", "Check")
        }
    }
    func twRepeated(append d: String?) -> String {
        [d, t("ξανά μετά από 10 λεπτά", "repeated after 10 min")].compactMap { $0 }.joined(separator: " · ")
    }
    func twDonePressed(_ at: Date, minutes: Int) -> String {
        t("πάτησε «έγινε» \(twTime(at))", "pressed \"done\" \(twTime(at))")
    }
    func twWorkedAt(_ at: Date) -> String { t("δούλεψε \(twTime(at))", "worked \(twTime(at))") }
    var twNotWorked: String { t("δεν βοήθησε", "did not help") }
    var twNoResponse: String { t("δεν απάντησε", "no response") }
    var twSettled: String { t("Σταμάτησε να ζεσταίνεται", "Stopped heating up") }
    var twResponsive: String { t("Πάτησε το κουμπί: σας βλέπει", "Pressed the button: responsive") }
    func twEscalated(_ w: EscalationReason) -> String {
        w == .dangerLine ? t("Κίνδυνος: ειδοποιήθηκε η οικογένεια", "Danger: family alerted")
                         : t("Ζεσταινόταν ακόμα στη δροσιά: ειδοποιήθηκε η οικογένεια", "Still heating in the cool: family alerted")
    }
    func twPowerOff(_ byWearer: Bool) -> String {
        byWearer ? t("Έκλεισε το βραχιόλι", "She switched the band off") : t("Το βραχιόλι έκλεισε (USB)", "Band switched off (USB)")
    }
    /// BATT_CRITICAL / POWER_OFF 3 (band 0.9.18): «battery ended» row.
    var twBattery: String { t("Η μπαταρία τελείωσε: το βραχιόλι έκλεισε", "Battery ran out: the band switched off") }
    /// BATT_LOW (band 0.9.18): «battery low» row (the band said «Φορτίστε απόψε»).
    var twBatteryLow: String { t("Χαμηλή μπαταρία: φορτίστε απόψε", "Battery low: charge it tonight") }
    var twHaptic: String { t("Το μοτέρ δόνησης δεν απάντησε (έδειξε στην οθόνη)", "Vibration motor did not respond (shown on screen)") }
    func twHelp(_ fromPhone: Bool) -> String {
        fromPhone ? t("Ζήτησε βοήθεια (από το κινητό)", "Asked for help (on the phone)") : t("Ζήτησε βοήθεια (κουμπί)", "Asked for help (button)")
    }
    var twHelpCancel: String { t("Ακύρωσε τη βοήθεια", "Cancelled the help call") }
    func twAllClear(minutes: Int) -> String {
        minutes > 0 ? t("Πάλι όλα καλά (\(minutes) λεπτά)", "Back to normal (\(minutes) min)") : t("Πάλι όλα καλά", "Back to normal")
    }
    var twDryShort: String { t("δοκιμή", "dry run") }
    var twTestSMS: String { t("Δοκιμαστικό SMS", "Test SMS") }
    var twSMSOnly: String { t("SMS στην οικογένεια", "SMS to the family") }
    var twSMSTo: String { t("SMS σε", "SMS to") }
    var twHistory: String { t("Ιστορικό", "History") }
    var twNoHistory: String { t("Τίποτα για αυτή τη μέρα. Όταν το βραχιόλι δώσει υπενθύμιση, θα φαίνεται εδώ.",
                                "Nothing on this day. When the band gives a reminder it shows here.") }
    func twDaySummary(_ s: DayStorySummary) -> String {
        var parts: [String] = []
        if s.reminders > 0 { parts.append(t("\(s.reminders) υπενθ. · \(s.worked) δούλεψαν", "\(s.reminders) reminders · \(s.worked) worked")) }
        if s.escalations > 0 { parts.append(t("\(s.escalations) κίνδυνος", "\(s.escalations) danger")) }
        if s.helps > 0 { parts.append(t("\(s.helps) βοήθεια", "\(s.helps) help")) }
        if s.smsSent > 0 { parts.append(t("\(s.smsSent) SMS", "\(s.smsSent) SMS")) }
        return parts.isEmpty ? t("Ήσυχη μέρα", "Quiet day") : parts.joined(separator: " · ")
    }
    func twOutcome(_ o: StoryRow.Outcome) -> String {
        switch o {
        case .worked: return t("Δούλεψε", "Worked")
        case .notWorked: return t("Δεν βοήθησε", "Did not help")
        case .noResponse: return t("Χωρίς απάντηση", "No response")
        case .open: return t("Σε εξέλιξη", "Ongoing")
        }
    }

    // MARK: home (her screen)
    var twBandOn: String { t("Βραχιόλι συνδεδεμένο", "Band connected") }
    var twBandOff: String { t("Χωρίς σύνδεση με το βραχιόλι", "Band not connected") }
    func twBandOffSince(_ d: Date) -> String { t("από τις \(twTime(d))", "since \(twTime(d))") }
    func twBalanceTitle(_ step: Int?) -> String {
        switch step {
        case 0: return t("Σε ισορροπία", "In balance")
        case 1: return t("Σχεδόν στο όριο", "Close to the line")
        case 2: return t("Πιείτε νερό", "Drink water")
        case 3: return t("Πηγαίνετε κάπου δροσερά", "Go somewhere cooler")
        case 4: return t("Πολλή ζέστη", "Too hot")
        default: return t("Χωρίς ένδειξη", "No reading")
        }
    }
    func twBalanceReason(_ step: Int?) -> String {
        switch step {
        case 0: return t("Το σώμα σας τα πάει καλά με τη ζέστη.", "Your body is coping well with the heat.")
        case 1: return t("Λίγο πριν το όριό σας. Ένα ποτήρι νερό βοηθά.", "Just under your line. A glass of water helps.")
        case 2: return t("Το βραχιόλι βλέπει ότι ζεσταίνεστε.", "The band sees you are warming up.")
        case 3: return t("Ζεσταίνεστε ακόμα. Λίγη δροσιά θα βοηθήσει.", "You are still warming up. Somewhere cooler will help.")
        case 4: return t("Ξαπλώστε, βρέξτε τον λαιμό σας. Η οικογένεια ειδοποιείται.", "Lie down, wet your neck. Your family is being told.")
        default: return t("Όταν συνδεθεί το βραχιόλι, θα δείτε εδώ πώς είστε.", "When the band connects you will see here how you are.")
        }
    }
    var twWorkedToast: String { t("Μπράβο, δροσίζεστε", "Well done, you are cooling down") }
    var twStillToast: String { t("Ακόμα ζεσταίνεστε", "You are still warming up") }
    var twHistoryButton: String { t("Ιστορικό και αναφορά", "History and report") }
    var twSettingsHint: String { t("Ρυθμίσεις: κρατήστε πατημένο 2 δευτερόλεπτα", "Settings: press and hold for 2 seconds") }
    var twHelpSent: String { t("Η οικογένεια ειδοποιείται με SMS.", "Your family is being told by SMS.") }
    var twHelpSentDry: String { t("ΔΟΚΙΜΗ: τα SMS φαίνονται στα εξερχόμενα, δεν στέλνονται.", "DRY RUN: the SMS show in the outbox, they are not sent.") }
    var twGaugeA11y: String { t("Ισορροπία ζέστης", "Heat balance") }
    func twGaugeA11yValue(_ step: Int?) -> String { twBalanceTitle(step) }

    // MARK: Settings › Tower
    var twTower: String { t("Πύργος ειδοποιήσεων (SMS)", "Alert tower (SMS)") }
    var twTowerShort: String { t("Πύργος", "Tower") }
    var twModeLive: String { t("ΕΝΕΡΓΟ: τα SMS στέλνονται μέσω Twilio.", "LIVE: SMS are sent through Twilio.") }
    var twModeDry: String { t("ΔΟΚΙΜΗ (χωρίς λογαριασμό): τα SMS φαίνονται στα εξερχόμενα, δεν στέλνονται.",
                              "DRY RUN (no account): the SMS show in the outbox, nothing is sent.") }
    var twCreds: String { t("Λογαριασμός Twilio", "Twilio account") }

    // MARK: [SMS-SHORTCUT] iPhone Shortcut sender
    func twModeShortcut(_ name: String) -> String {
        t("ΕΝΕΡΓΟ: τα μηνύματα φεύγουν από αυτό το iPhone με τη Συντόμευση «\(name)».",
          "LIVE: messages go from this iPhone through the Shortcut \"\(name)\".")
    }
    /// The live / dry-run line for the Tower's current sender.
    func twMode(_ tw: TowerEngine) -> String {
        tw.sender == .shortcut ? twModeShortcut(ShortcutAPI.name(tw.prefs.shortcutName)) : (tw.mode == .live ? twModeLive : twModeDry)
    }
    var twSender: String { t("Αποστολή μέσω", "Send through") }
    var twSenderTwilio: String { "Twilio" }
    var twSenderShortcut: String { t("Συντόμευση iPhone", "iPhone Shortcut") }
    var twShortcutName: String { t("Όνομα Συντόμευσης", "Shortcut name") }
    func twShortcutHowTo(_ name: String) -> String {
        t("Φτιάξτε στην εφαρμογή Συντομεύσεις μια Συντόμευση με όνομα «\(name)»: «Λήψη εισόδου κειμένου» → «Αποστολή μηνύματος» (στην επαφή) με «Είσοδος συντόμευσης», «Εμφάνιση κατά την εκτέλεση» κλειστό.",
          "In the Shortcuts app, create a Shortcut named \"\(name)\": \"Receive text input\" → \"Send Message\" (to the contact) with \"Shortcut Input\", \"Show When Run\" off.")
    }
    var twShortcutTest: String { t("Δοκιμή της Συντόμευσης", "Test the Shortcut") }
    var twShortcutWaiting: String { t("Περιμένει: πατήστε την ειδοποίηση για να σταλεί", "Waiting: tap the notification to send it") }
    var twShortcutTapTitle: String { t("Πατήστε για να σταλεί η ειδοποίηση", "Tap to send the alert") }
    var twShortcutTapBody: String { t("Το μήνυμα στην οικογένεια φεύγει από τη Συντόμευση μόλις ανοίξει η εφαρμογή.",
                                      "The message to the family goes through the Shortcut as soon as the app opens.") }
    var twSID: String { "Account SID" }
    var twToken: String { "Auth Token" }
    var twFrom: String { t("Αριθμός αποστολέα (From)", "From number") }
    var twSave: String { t("Αποθήκευση στο Keychain", "Save to the Keychain") }
    var twDelete: String { t("Διαγραφή λογαριασμού (επιστροφή σε δοκιμή)", "Remove account (back to dry run)") }
    var twSaved: String { t("Αποθηκεύτηκε στο Keychain αυτού του iPhone.", "Saved in this iPhone's Keychain.") }
    var twSaveFailed: String { t("Δεν αποθηκεύτηκε.", "Could not save.") }
    func twCredProblems(_ p: [String]) -> String {
        p.map { k in
            switch k {
            case "sid": return t("Το Account SID ξεκινά με AC και έχει 34 χαρακτήρες.", "The Account SID starts with AC and has 34 characters.")
            case "token": return t("Το Auth Token έχει 32 χαρακτήρες.", "The Auth Token has 32 characters.")
            default: return t("Γράψτε τον αριθμό αποστολέα του Twilio (π.χ. +1…).", "Type your Twilio sender number (e.g. +1…).")
            }
        }.joined(separator: " ")
    }
    var twCredsNote: String { t("Από το twilio.com/console. Μένουν μόνο στο Keychain αυτού του iPhone: δεν φαίνονται, δεν καταγράφονται, δεν φεύγουν από το κινητό εκτός από την αποστολή στο Twilio.",
                                "From twilio.com/console. They stay only in this iPhone's Keychain: never shown, never logged, never leave the phone except to Twilio itself.") }
    var twTokenStored: String { t("Αποθηκευμένο (δεν εμφανίζεται)", "Stored (not shown)") }
    var twRules: String { t("Πότε στέλνεται SMS", "When an SMS goes") }
    var twSimSMS: String { t("Αποστολή SMS και στην προσομοίωση", "Send SMS in the simulation too") }
    var twSimSMSNote: String { t("Μόνο για επίδειξη: η προσομοίωση (ΠΡΟΣΟΜΟΙΩΣΗ) στέλνει πραγματικά SMS στην οικογένεια, με «(δοκιμή)» στο τέλος.",
                                 "Demo only: the simulation sends real SMS to the family, ending with \"(test)\".") }
    var twNotesBySMS: String { t("Σημειώσεις με SMS («το νερό δεν βοήθησε», «δεν απάντησε»)", "Notes by SMS (\"water did not help\", \"no response\")") }
    var twDisconnectSMS: String { t("SMS όταν το βραχιόλι μείνει 60 λεπτά χωρίς σύνδεση", "SMS when the band is disconnected for 60 min") }
    var twSMSLang: String { t("Γλώσσα των SMS", "SMS language") }
    var twCountry: String { t("Κωδικός χώρας για αριθμούς χωρίς +", "Country code for numbers without +") }
    var twTest: String { t("Στείλτε δοκιμαστικό SMS", "Send a test SMS") }
    var twOutbox: String { t("Εξερχόμενα SMS", "SMS outbox") }
    var twOutboxEmpty: String { t("Κανένα SMS ακόμα.", "No SMS yet.") }
    var twRetry: String { t("Ξανά", "Retry") }
    var twClearOutbox: String { t("Καθαρισμός λίστας", "Clear the list") }
    func twStatus(_ s: OutboxItem.Status, dry: Bool) -> String {
        switch s {
        case .queued: return t("Σε αναμονή", "Queued")
        case .sending: return t("Στέλνεται", "Sending")
        case .sent: return dry ? t("Δοκιμή: θα στελνόταν", "Dry run: would be sent") : t("Στάλθηκε", "Sent")
        case .failed: return t("Απέτυχε", "Failed")
        case .skipped: return t("Δεν στάλθηκε (όριο SMS)", "Not sent (SMS limit)")
        }
    }
    func twAttempts(_ n: Int) -> String { t("προσπάθειες: \(n)", "attempts: \(n)") }
    func twNextTry(_ d: Date) -> String { t("επόμενη δοκιμή \(twTime(d))", "next try \(twTime(d))") }
    func twSegments(_ n: Int) -> String { t("\(n) τμήμα SMS", "\(n) SMS part") + (n > 1 ? t("τα", "s") : "") }
    var twNoContacts: String { t("Δεν υπάρχει επαφή με αριθμό: προσθέστε στις Ρυθμίσεις › Οικογένεια.", "No contact with a number: add one in Settings › Family.") }
    var twLimitsNote: String { t("Ίδιο μήνυμα στο ίδιο άτομο: μία φορά ανά 10–30 λεπτά. Το πολύ 6 SMS την ώρα ανά άτομο (η ΒΟΗΘΕΙΑ και ο κίνδυνος περνούν πάντα). Χωρίς internet: νέα προσπάθεια σε 30 δ, 1, 2, 4… έως 15 λεπτά.",
                                 "Same message to the same person: once per 10-30 min. At most 6 SMS an hour per person (HELP and danger always go). No internet: retried after 30 s, 1, 2, 4 … up to 15 min.") }
    var twDemoSMS: String { t("Επίδειξη: «το νερό δεν βοήθησε» → «ζεσταίνεται ακόμα»", "Demo: \"water did not help\" → \"still heating\"") }
    var twDemoNote: String { t("Περνά τα συμβάντα του βραχιολιού (ΠΡΟΣΟΜΟΙΩΣΗ) από τον ίδιο αποκωδικοποιητή· τα SMS μένουν πάντα δοκιμή.",
                               "Plays band events (SIMULATION) through the same decoder; these SMS are always dry run.") }
    var twBackgroundNote: String { t("Το iPhone της πρέπει να μένει με Bluetooth ανοιχτό. Η εφαρμογή δουλεύει και κλειδωμένη· αν την κλείσετε με σάρωση προς τα πάνω, το iOS σταματά τη σύνδεση μέχρι να ανοίξει ξανά.",
                                     "Her iPhone must keep Bluetooth on. The app works while locked; if you swipe it away, iOS stops the link until it is opened again.") }

    // MARK: contacts (Setup + Settings)
    var twFamily: String { t("Οικογένεια (SMS)", "Family (SMS)") }
    var twContactName: String { t("Όνομα", "Name") }
    var twContactPhone: String { t("Κινητό", "Mobile number") }
    var twContactEmail: String { t("Email (προαιρετικό, για την αναφορά)", "Email (optional, for the report)") }
    var twAddContact: String { t("Προσθήκη ατόμου", "Add a person") }
    var twBadPhone: String { t("Ο αριθμός δεν φαίνεται σωστός.", "This number does not look right.") }
    var twContactsNote: String { t("1 έως 3 άτομα. Παίρνουν SMS όταν το βραχιόλι χρειάζεται την οικογένεια.", "1 to 3 people. They get an SMS when the band needs the family.") }
    var twFamilyView: String { t("Επίδειξη: προβολή οικογένειας", "Demo: family view") }
    var twFamilyViewNote: String { t("Η παλιά οθόνη της οικογένειας (καρτέλες), μόνο για επίδειξη. Η οικογένεια πλέον παίρνει SMS.",
                                     "The old family screens (tabs), for demos only. The family now gets SMS.") }
    var twBackToTower: String { t("Πίσω στην οθόνη της", "Back to her screen") }

    // MARK: report sharing
    var twEmailReport: String { t("Αποστολή με email στην οικογένεια", "Email to the family") }
    var twShareReport: String { t("Κοινοποίηση (WhatsApp, Μηνύματα…)", "Share (WhatsApp, Messages…)") }
    var twNoPDFbySMS: String { t("Το SMS δεν μπορεί να μεταφέρει PDF: στείλτε την αναφορά με email ή WhatsApp.",
                                 "An SMS cannot carry a PDF: send the report by email or WhatsApp.") }
    var twNoMail: String { t("Δεν έχει ρυθμιστεί λογαριασμός Mail σε αυτό το iPhone: χρησιμοποιήστε την Κοινοποίηση.",
                             "No Mail account on this iPhone: use Share instead.") }
    var twMailSubject: String { t("Αναφορά ζέστης για τον γιατρό", "Heat report for the doctor") }
    var twMailBody: String { t("Η αναφορά ζέστης από το βραχιόλι Heat Guardian, για τον γιατρό. Δεν είναι ιατρική διάγνωση.",
                               "The heat report from the Heat Guardian band, for the doctor. It is not a medical diagnosis.") }

    // MARK: setup
    var suNext: String { t("Συνέχεια", "Continue") }
    var suBack: String { t("Πίσω", "Back") }
    var suSkip: String { t("Παράλειψη", "Skip") }
    var suDone: String { t("Έτοιμο", "Done") }
    var suLangQ: String { t("Γλώσσα", "Language") }
    var suWelcome: String { t("Καλώς ήρθατε. Θα ρυθμίσουμε το βραχιόλι μαζί, μία ερώτηση τη φορά.",
                              "Welcome. We will set up the band together, one question at a time.") }
    var suPairQ: String { t("Συνδέστε το βραχιόλι", "Connect the band") }
    var suPairNote: String { t("Κρατήστε το βραχιόλι κοντά στο κινητό και πατήστε «Σύνδεση». Αν ζητηθεί κωδικός, γράψτε τα 6 ψηφία της οθόνης του.",
                               "Keep the band near the phone and tap \"Connect\". If a code is asked, type the 6 digits on its screen.") }
    var suConnect: String { t("Σύνδεση", "Connect") }
    var suConnected: String { t("Συνδέθηκε", "Connected") }
    var suNameQ: String { t("Πώς σας λένε;", "What is your name?") }
    var suNameNote: String { t("Έτσι θα σας λέει η οικογένεια στα μηνύματα.", "This is the name your family sees in the messages.") }
    var suAgeQ: String { t("Πόσων χρονών είστε;", "How old are you?") }
    var suSexQ: String { t("Είστε…", "You are…") }
    var suMedsQ: String { t("Παίρνετε κάποιο από αυτά τα φάρμακα;", "Do you take any of these medicines?") }
    var suMedsNote: String { t("Προαιρετικό. Βοηθά το βραχιόλι να σας καταλάβει.", "Optional. It helps the band understand you.") }
    var suWakeQ: String { t("Τι ώρα ξυπνάτε συνήθως;", "When do you usually wake up?") }
    var suBedQ: String { t("Τι ώρα κοιμάστε συνήθως;", "When do you usually go to sleep?") }
    var suContactQ: String { t("Ποιον να ειδοποιούμε;", "Who should we tell?") }
    func suContactN(_ n: Int) -> String { t("Άτομο \(n) από 3", "Person \(n) of 3") }
    var suAnotherQ: String { t("Θέλετε να προσθέσετε κι άλλο άτομο;", "Add another person?") }
    var suYesAnother: String { t("Ναι, κι άλλο άτομο", "Yes, another person") }
    var suNoFinish: String { t("Όχι, συνέχεια", "No, continue") }
    var suAllSet: String { t("Όλα έτοιμα", "All set") }
    var suAllSetNote: String { t("Το κινητό σας μένει δίπλα στο βραχιόλι και ειδοποιεί την οικογένεια όταν χρειαστεί. Αφήστε την εφαρμογή ανοιχτή στο παρασκήνιο.",
                                 "Your phone stays with the band and tells your family when needed. Leave the app running in the background.") }
    var suStepOf: (Int, Int) -> String { { a, b in self.t("Βήμα \(a) από \(b)", "Step \(a) of \(b)") } }
}
