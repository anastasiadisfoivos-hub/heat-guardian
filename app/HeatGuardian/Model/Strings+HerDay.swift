// Strings of "Her Day" (HERDAY_SPEC.md). Family mode reads them in English, Elder mode in Greek; every line has
// both so a screen never mixes languages (DESIGN.md §8). The band's own sentences stay Greek (HerDay.briefSentence).

import Foundation

extension Strings {
    func placeName(_ p: PlaceType) -> String {
        switch p {
        case .home: return t("Σπίτι", "Home")
        case .market: return t("Αγορά", "Market")
        case .church: return t("Εκκλησία", "Church")
        case .walk: return t("Βόλτα", "Walk")
        case .pharmacy: return t("Φαρμακείο", "Pharmacy")
        case .cafe: return t("Καφενείο", "Café")
        case .doctor: return t("Γιατρός", "Doctor")
        case .other: return t("Έξοδος", "Out")
        }
    }
    /// "the market" inside an English sentence; the Greek article form inside a Greek one.
    private func placeIn(_ p: PlaceType) -> String {
        switch p {
        case .home: return t("στο σπίτι", "home")
        case .market: return t("στην αγορά", "at the market")
        case .church: return t("στην εκκλησία", "at church")
        case .walk: return t("σε βόλτα", "out for a walk")
        case .pharmacy: return t("στο φαρμακείο", "at the pharmacy")
        case .cafe: return t("στο καφενείο", "at the café")
        case .doctor: return t("στον γιατρό", "at the doctor's")
        case .other: return t("έξω", "out")
        }
    }

    // MARK: family · status line (Today)
    func hdAtSince(_ p: PlaceType, _ at: String) -> String {
        p == .home ? t("Στο σπίτι από τις \(at)", "Home since \(at)") : t("\(placeIn(p).capitalizedFirst) από τις \(at)", "\(placeIn(p).capitalizedFirst) since \(at)")
    }
    func hdLeftSince(_ p: PlaceType, _ at: String) -> String {
        p == .home ? t("Έξω από τις \(at)", "Out since \(at)") : t("\(placeName(p)): έφυγε στις \(at)", "Left the \(placeName(p).lowercased()) at \(at)")
    }

    // MARK: family · timeline
    var hdCaption: String { t("Η ΜΕΡΑ ΤΗΣ", "HER DAY") }
    var hdOutside: String { t("Έξω", "Outside") }
    var hdHouse: String { t("Σπίτι", "House") }
    var hdNoRoutine: String { t("Η συνήθης μέρα της θα φανεί μετά από λίγες μέρες με το κινητό της.", "Her usual day appears after a few days with her phone.") }
    func hdHotWindow(_ from: Int, _ to: Int) -> String {
        t(String(format: "Ζέστη έξω %02d:00–%02d:00", from, to), String(format: "Hot outside %02d:00–%02d:00", from, to))
    }
    var hdNoHot: String { t("Χωρίς ζεστές ώρες έξω", "No hot hours outside") }
    func hdUsual(_ dur: Int) -> String { t("συνήθως ~\(dur) λεπτά", "usually ~\(dur) min") }
    func hdHotThen(_ c: Int?) -> String {
        c.map { t("Ζέστη τότε · \($0)° έξω", "Hot then · \($0)° outside") } ?? t("Ζέστη τότε", "Hot then")
    }
    func hdBandSuggests(_ d: ShiftDirection, _ at: String) -> String {
        d == .before ? t("Το βραχιόλι προτείνει: πριν τις \(at)", "Band suggests: before \(at)")
                     : t("Το βραχιόλι προτείνει: μετά τις \(at)", "Band suggests: after \(at)")
    }
    func hdWillSuggest(_ d: ShiftDirection, _ at: String) -> String {
        d == .before ? t("Θα προτείνει: πριν τις \(at)", "Will suggest: before \(at)")
                     : t("Θα προτείνει: μετά τις \(at)", "Will suggest: after \(at)")
    }
    var hdNoSlot: String { t("Καμία δροσερή ώρα· καλύτερα να μείνει μέσα", "No cool slot; best to stay in") }
    func hdAir(_ at: String) -> String { t("Ανοίξτε τα παράθυρα από τις \(at)", "Open the windows from \(at)") }
    var hdAirWhy: String { t("έξω πιο δροσερά από μέσα", "cooler outside than in") }
    func hdFollowed(_ at: String) -> String { t("Πήγε \(at) ✓ ακολούθησε", "Went \(at) ✓ followed") }
    func hdInHeat(_ at: String) -> String { t("Πήγε \(at), μέσα στη ζέστη", "Went \(at), in the heat") }
    func hdWent(_ at: String) -> String { t("Πήγε \(at)", "Went \(at)") }
    var hdNotGone: String { t("Δεν βγήκε", "Did not go") }
    func hdOnBand(_ at: String) -> String { t("Οι προτάσεις είναι στο βραχιόλι ✓ \(at)", "Suggestions on her band ✓ \(at)") }
    var hdGoesEvening: String { t("Οι προτάσεις πάνε στο βραχιόλι το βράδυ", "Suggestions go to her band this evening") }
    var hdNotOnBand: String { t("Δεν υπάρχουν ακόμη προτάσεις στο βραχιόλι", "No suggestions on her band yet") }
    var hdStripA11y: String { t("Ζέστη ανά ώρα, έξω και στο σπίτι", "Heat by hour, outside and in the house") }
    func hdStripValue(_ hot: String, _ peakOut: Int?, _ peakIn: Int?) -> String {
        let a = peakOut.map { t("έξω έως \($0)°", "outside up to \($0)°") } ?? ""
        let b = peakIn.map { t("σπίτι έως \($0)°", "house up to \($0)°") } ?? ""
        return [hot, a, b].filter { !$0.isEmpty }.joined(separator: ", ")
    }
    var hdCollisionA11y: String { t("Συμπίπτει με τη ζέστη", "Collides with the heat") }

    // MARK: elder · card
    var hdOK: String { t("Εντάξει", "OK") }
    /// The Elder card sentence: the band's own Greek, or its English twin.
    func hdCard(_ items: [DayPlanItem], tomorrow: Bool) -> String? {
        if el { return HerDay.briefSentence(items, tomorrow: tomorrow) }
        let head = tomorrow ? "Tomorrow: " : "Today: "
        if let k = items.filter({ $0.kind == .outingShift }).min(by: { ($0.usual ?? 9999) < ($1.usual ?? 9999) }),
           let s = k.suggested, let d = k.direction {
            return head + placeName(k.place).lowercased() + (d == .before ? " before " : " after ") + Routine.hhmm(s)
        }
        if tomorrow, let w = items.first(where: { $0.kind == .heatwaveDay }) { return "Tomorrow: heat wave, day \(w.heatwaveDay)" }
        return nil
    }
    var hdCardNote: String { t("Τότε έξω κάνει λιγότερη ζέστη.", "It is cooler outside then.") }

    var hdJumpEvening: String { t("Η μέρα της: βράδυ 20:00", "Her Day: evening 20:00") }
    var hdHotterTomorrow: String { t("Η μέρα της: πιο ζεστό αύριο («μετά τις»)", "Her Day: hotter tomorrow (\"go after\")") }

    // MARK: settings · her places (Elder mode)
    var hdPlaces: String { t("Τα μέρη της", "Her places") }
    var hdLocationOn: String { t("Τοποθεσία (επισκέψεις)", "Location (visits)") }
    var hdThisIsHome: String { t("Εδώ είναι το σπίτι", "This is home") }
    var hdHomeSet: String { t("Ορίστηκε το σπίτι ✓", "Home set ✓") }
    var hdHomeFailed: String { t("Δεν βρέθηκε η θέση. Δοκιμάστε ξανά.", "Could not get the location. Try again.") }
    var hdClearPlaces: String { t("Διαγραφή όλων των μερών", "Clear all learned places") }
    var hdNoPlaces: String { t("Κανένα μέρος ακόμη.", "No places yet.") }
    func hdVisits(_ n: Int) -> String { t("\(n) επισκέψεις", "\(n) visits") }
    var hdPlacesNote: String {
        t("Οι θέσεις μένουν μόνο σε αυτό το iPhone. Στο βραχιόλι και στην οικογένεια πηγαίνει μόνο το είδος του μέρους (π.χ. «αγορά») και η ώρα. Για να βρεθεί το είδος, γίνεται μία αναζήτηση στους Χάρτες της Apple για κάθε νέο μέρος.",
          "Locations stay on this iPhone only. The band and the family get only the kind of place (e.g. \"market\") and the time. To find the kind, Apple Maps is searched once for each new place.")
    }
    func hdAuth(_ a: LocationAuth) -> String {
        switch a {
        case .always: return t("Επιτρέπεται πάντα ✓", "Allowed always ✓")
        case .whenInUse: return t("Μόνο όταν είναι ανοιχτή η εφαρμογή — επιλέξτε «Πάντα» στις Ρυθμίσεις iPhone", "Only while the app is open — choose \"Always\" in iPhone Settings")
        case .denied: return t("Δεν επιτρέπεται — ενεργοποιήστε την στις Ρυθμίσεις iPhone", "Not allowed — turn it on in iPhone Settings")
        case .notDetermined: return t("Δεν έχει ζητηθεί ακόμη", "Not asked yet")
        }
    }
    var hdHomeBadge: String { t("σπίτι", "home") }
}

extension String {
    var capitalizedFirst: String { prefix(1).uppercased() + dropFirst() }
}
