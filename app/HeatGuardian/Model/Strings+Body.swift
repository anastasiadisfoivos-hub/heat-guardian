// Strings of «Her body in heat» (app screen + the health-track pages of the doctor's report). Greek / English.
// "Wrist skin temperature" is always named so; there is no body-temperature number (the Body Twin estimate appears
// only behind HeatReportBuilder.SHOW_TWIN_ESTIMATE, labelled "model estimate, not measured").

import Foundation

extension Strings {
    private func dec(_ x: Double) -> String { let s = String(format: "%.1f", x); return el ? s.replacingOccurrences(of: ".", with: ",") : s }
    private func hm(_ minutes: Double) -> String {
        let m = Int(minutes.rounded()); return el ? "\(m / 60) ώ. \(String(format: "%02d", m % 60))" : "\(m / 60) h \(String(format: "%02d", m % 60))"
    }

    var bhScreenTitle: String { t("Το σώμα της στη ζέστη", "Her body in heat") }
    var bhScreenSub: String { t("Τι έδειξαν οι αισθητήρες του βραχιολιού τις τελευταίες 14 μέρες.", "What the band's sensors showed over the last 14 days.") }
    var bhSummaryTitle: String { t("Πώς αντιδρά στη ζέστη", "How she reacts to heat") }
    var bhSummaryNote: String { t("Υπολογίζεται στο κινητό από τις μετρήσεις του βραχιολιού. Η βεβαιότητα δείχνει πόσα δεδομένα στηρίζουν κάθε πρόταση. Δεν είναι διάγνωση.",
                                  "Computed on the phone from the band's readings. \"Confidence\" says how much data each line rests on. Not a diagnosis.") }
    var bhPageSkin: String { t("Θερμοκρασία δέρματος στον καρπό, αέρας και υγρασία", "Wrist skin temperature, air and humidity") }
    var bhPageHeart: String { t("Η καρδιά της στη ζέστη και η επαναφορά", "Her heart in heat, and recovery") }
    var bhPageAlerts: String { t("Ειδοποιήσεις: τι έδειξαν οι αισθητήρες, τι έκανε, πόσο γρήγορα επανήλθε", "Alerts: what the sensors showed, what she did, how fast she recovered") }
    var bhPageSleep: String { t("Ύπνος και κίνηση: ζεστές μέρες και κανονικές", "Sleep and movement: hot days vs normal days") }
    var bhNoAlerts: String { t("Καμία ειδοποίηση ζέστης σε αυτή την περίοδο.", "No heat alerts in this period.") }

    func bhConf(_ c: Confidence) -> String {
        switch c {
        case .high: return t("βεβαιότητα: υψηλή", "confidence: high")
        case .medium: return t("βεβαιότητα: μέτρια", "confidence: medium")
        case .low: return t("βεβαιότητα: χαμηλή (λίγα δεδομένα)", "confidence: low (little data)")
        }
    }

    // charts
    var bhSkinDays: String { t("Θερμοκρασία δέρματος στον καρπό ανά ημέρα (ελάχ.–μέγ., μέση), με τον αέρα", "Wrist skin temperature per day (min–max, mean), with the air") }
    var bhSkinNote: String { t("Θερμοκρασία δέρματος στον καρπό: ακολουθεί τον χώρο. ΔΕΝ είναι θερμοκρασία σώματος. Αέρας = αισθητήρας του βραχιολιού.",
                               "Wrist skin temperature: it follows the room. It is NOT body temperature. Air = the band's own sensor.") }
    var bhSkinRange: String { t("δέρμα καρπού ελάχ.–μέγ.", "wrist skin min–max") }
    var bhSkinMean: String { t("δέρμα καρπού", "wrist skin temperature") }
    var bhAirHome: String { t("αέρας στο σπίτι", "air at home") }
    var bhAirOut: String { t("αέρας έξω", "air outside") }
    var bhRhDays: String { t("Υγρασία γύρω της (μέση ημέρας)", "Humidity around her (daily mean)") }
    var bhRh: String { t("υγρασία", "humidity") }
    func bhProfile(_ day: String) -> String { el ? "24 ώρες της πιο ζεστής μέρας (\(day))" : "24 hours of the hottest day (\(day))" }
    var bhRhProfile: String { t("Υγρασία την ίδια μέρα", "Humidity that day") }
    var bhHourPoints: String { t("μία ώρα (08–21)", "one hour (08–21)") }
    func bhFitLine(_ b: Double) -> String { el ? "≈ \(dec(b)) παλμοί/λεπτό ανά °C πάνω από 26 °C" : "≈ \(dec(b)) bpm per °C above 26 °C" }
    func bhNormal(_ v: Int) -> String { el ? "το κανονικό της \(v)" : "her normal \(v)" }
    var bhHRTitle: String { t("Σφυγμός μέρας σε σχέση με τη θερμοκρασία αέρα", "Daytime pulse against the air temperature") }
    func bhFitNote(_ f: Fit, _ conf: String) -> String {
        el ? "Γραμμή: ≈ \(dec(f.b)) παλμοί/λεπτό για κάθε °C αέρα πάνω από 26 °C, από \(f.n) ήσυχες ώρες μέρας (\(f.nHot) πάνω από 26 °C· χωρίς επεισόδια και περπάτημα) · \(conf). Κανονικό = διάμεσος ήσυχος σφυγμός μέρας σε ≤ 26 °C."
           : "Line: ≈ \(dec(f.b)) bpm for each °C of air above 26 °C, from \(f.n) quiet daytime hours (\(f.nHot) above 26 °C; episodes and walking left out) · \(conf). Normal = her median quiet daytime pulse at ≤ 26 °C."
    }
    var bhFitNone: String { t("Δεν υπάρχουν ακόμη αρκετές ζεστές ώρες για να φανεί η απόκριση της καρδιάς.", "Not enough hot hours yet to show the heart's response.") }
    var bhRest: String { t("σφυγμός ηρεμίας", "resting pulse") }
    func bhUsual(_ v: Int) -> String { el ? "συνηθισμένο \(v)" : "usual \(v)" }
    var bhRestTitle: String { t("Σφυγμός ηρεμίας ανά ημέρα", "Resting pulse per day") }
    var bhRestNote: String { t("Χαμηλότερος σφυγμός όσο ήταν ακίνητη (10ο εκατοστημόριο). Συνηθισμένο = διάμεσος της περιόδου.",
                               "Her low pulse while still (10th percentile). Usual = the period's median.") }
    var bhRecTitle: String { t("Επαναφορά μετά από κάθε επεισόδιο (λεπτά)", "Recovery after each episode (minutes)") }
    var bhRecNote: String { t("Από την κορυφή του επεισοδίου μέχρι ο σφυγμός να είναι ξανά ≤ 5 πάνω από ό,τι εξηγεί ο αέρας για εκείνη (η γραμμή πάνω) και το δέρμα καρπού ≤ 0,3 °C πάνω από το αναμενόμενο. Χωρίς μπάρα = όχι μέσα σε 6 ώρες.",
                              "From the episode's peak until her pulse is back within 5 bpm of what the air alone explains for her (the line above) and her wrist skin within 0.3 °C of its expected value. No bar = not within 6 h.") }
    var bhRecHR: String { t("σφυγμός", "pulse") }
    var bhRecSkin: String { t("δέρμα καρπού", "wrist skin") }
    var bhSleepTitle: String { t("Ύπνος (εκτίμηση από την ακινησία του καρπού)", "Sleep (estimated from wrist stillness)") }
    var bhActTitle: String { t("Κίνηση (ώρες με κίνηση)", "Movement (hours moving)") }
    var bhNormalDays: String { t("κανονικές μέρες", "normal days") }
    var bhHotDays: String { t("ζεστές μέρες", "hot days") }
    var bhTwinTitle: String { t("ΕΚΤΙΜΗΣΗ ΜΟΝΤΕΛΟΥ (Σωματικό Δίδυμο), όχι μέτρηση", "MODEL ESTIMATE (Body Twin), not measured") }
    var bhTwinNote: String { t("Εύρος της ημέρας της εκτίμησης θερμοκρασίας πυρήνα από το μοντέλο του βραχιολιού. Τα φορητά πέφτουν έξω 0,3–0,6 °C· μην τη χρησιμοποιείτε ως μέτρηση.",
                               "Daily range of the band model's core-temperature estimate. Wearable estimates are off by 0.3–0.6 °C; do not use it as a measurement.") }
    var bhTwinRange: String { t("εκτίμηση μοντέλου ελάχ.–μέγ.", "model estimate min–max") }
    var bhTwinWarn: String { t("Ενότητα ενεργή με απόφαση της ομάδας (SHOW_TWIN_ESTIMATE). Εκτίμηση μοντέλου, όχι μέτρηση, όχι διάγνωση.",
                               "Section switched on by the team (SHOW_TWIN_ESTIMATE). Model estimate, not measured, not a diagnosis.") }

    // her heat reaction in plain words
    func bhSumHeart(_ b: Double, _ normal: Int, _ at30: Int, _ n: Int) -> String {
        el ? "Στη ζέστη η καρδιά της ανεβαίνει πάνω από το κανονικό της: περίπου +\(dec(b)) παλμούς/λεπτό για κάθε °C αέρα πάνω από 26 °C. Στους 30 °C ο σφυγμός της μέρας ήταν περίπου \(at30), ενώ το κανονικό της (≤ 26 °C) είναι \(normal)."
           : "In heat her heart rises above her normal: about +\(dec(b)) bpm for each °C of air above 26 °C. At 30 °C her daytime pulse was about \(at30), against her normal \(normal) at 26 °C or less."
    }
    var bhSumHeartNone: String { t("Δεν υπάρχουν ακόμη αρκετές ζεστές ώρες για να πούμε πώς αντιδρά η καρδιά της.", "Not enough hot hours yet to say how her heart reacts.") }
    func bhSumRecovery(_ hr: Int, _ skin: Int?, _ k: Int, _ notBack: Int) -> String {
        let sk = skin.map { el ? ", το δέρμα του καρπού σε περίπου \($0) λεπτά" : ", her wrist skin in about \($0) min" } ?? ""
        let nb = notBack > 0 ? (el ? " (\(notBack) φορές όχι μέσα σε 6 ώρες)" : " (\(notBack) not within 6 h)") : ""
        return el ? "Μετά από ένα επεισόδιο ζέστης επανέρχεται σε περίπου \(hr) λεπτά (σφυγμός)\(sk) — διάμεσος \(k) επεισοδίων\(nb)."
                  : "After a heat episode she recovers in about \(hr) min (pulse)\(sk) — median of \(k) episodes\(nb)."
    }
    func bhSumSlower(_ a: Int, _ c: Int) -> String {
        el ? "Η επαναφορά έγινε πιο αργή μέσα στην περίοδο: από ~\(a) σε ~\(c) λεπτά (πρώτα / τελευταία επεισόδια)."
           : "Recovery got slower during the period: from ~\(a) to ~\(c) min (earlier / later episodes)."
    }
    func bhSumFaster(_ a: Int, _ c: Int) -> String {
        el ? "Η επαναφορά έγινε πιο γρήγορη μέσα στην περίοδο: από ~\(a) σε ~\(c) λεπτά." : "Recovery got faster during the period: from ~\(a) to ~\(c) min."
    }
    var bhSumRecNone: String { t("Υπήρξαν επεισόδια, αλλά όχι αρκετά δεδομένα για τον χρόνο επαναφοράς.", "There were episodes, but not enough data for recovery times.") }
    func bhSumSkin(_ d: Double, _ a: Double, _ c: Double) -> String {
        el ? "Το δέρμα του καρπού ήταν κατά μέσο όρο \(dec(d)) °C θερμότερο τις ζεστές μέρες (\(dec(c)) έναντι \(dec(a)) °C) — ακολουθεί τον χώρο, δεν είναι θερμοκρασία σώματος."
           : "Her wrist skin was on average \(dec(d)) °C warmer on hot days (\(dec(c)) vs \(dec(a)) °C) — it follows the room; it is not body temperature."
    }
    func bhSumSleepAct(_ sh: Double, _ sn: Double, _ ah: Double, _ an: Double) -> String {
        el ? "Ύπνος (εκτίμηση): \(hm(sh)) τις ζεστές νύχτες έναντι \(hm(sn)) τις κανονικές. Κίνηση: \(dec(ah)) ώρες τις ζεστές μέρες έναντι \(dec(an))."
           : "Sleep (estimated): \(hm(sh)) on hot nights vs \(hm(sn)) on normal nights. Movement: \(dec(ah)) h on hot days vs \(dec(an)) h."
    }
    var bhFigSlope: String { t("παλμοί/λεπτό ανά °C πάνω από 26 °C", "bpm per °C above 26 °C") }
    var bhFigRecovery: String { t("λεπτά επαναφοράς σφυγμού (διάμεσος)", "min for her pulse to recover (median)") }

    // alerts table
    func bhAlertWord(_ s: String) -> String {
        switch s {
        case "DRINK": return t("Πιείτε νερό", "Drink water")
        case "COOL": return t("Πηγαίνετε σε δροσιά", "Move somewhere cool")
        case "CHECK": return t("«Είστε καλά;»", "\"Are you OK?\"")
        default: return t("Πολλή ζέστη", "Too hot")
        }
    }
    var bhNoAnswer: String { t("δεν απάντησε", "no answer") }
    func bhDidReminder(_ n: Int) -> String { el ? "έκανε την υπενθύμιση (\(n))" : "did the reminder (\(n))" }
    var bhWentHome: String { t("γύρισε σπίτι", "went home") }
    func bhStayed(_ home: Bool) -> String { home ? t("έμεινε στο σπίτι", "stayed at home") : t("ήταν έξω", "was out") }
    func bhRecCell(_ hr: Int?, _ sk: Int?) -> String {
        func m(_ v: Int?) -> String { v.map { "\($0)′" } ?? (el ? ">6 ώ." : ">6 h") }
        return m(hr) + " / " + m(sk)
    }
    var bhAlertsNote: String { t("Αισθητήρες = μέσος όρος 5 λεπτών τη στιγμή της ειδοποίησης (αέρας, υγρασία, δέρμα καρπού, σφυγμός). «Τι έκανε» = τα επόμενα 30 λεπτά. Επανήλθε = λεπτά από την κορυφή του επεισοδίου.",
                                 "Sensors = 5-minute means at the moment of the alert (air, humidity, wrist skin, pulse). \"What she did\" = the next 30 min. Recovered = minutes from the episode's peak.") }

    // questions added by the health track
    func rqHeart(_ b: Double) -> String {
        el ? "Ο σφυγμός της ανεβαίνει περίπου \(dec(b)) παλμούς/λεπτό για κάθε °C πάνω από 26 °C. Είναι αναμενόμενο για εκείνη και τα φάρμακά της;"
           : "Her pulse rises about \(dec(b)) bpm for each °C above 26 °C. Is that expected for her and her medicines?"
    }
    func rqRecovery(_ m: Int) -> String {
        el ? "Μετά από ένα επεισόδιο ζέστης ο σφυγμός της χρειάζεται περίπου \(m) λεπτά να επανέλθει. Χρειάζεται να το προσέξουμε;"
           : "After a heat episode her pulse takes about \(m) min to settle. Is that something to watch?"
    }
}
