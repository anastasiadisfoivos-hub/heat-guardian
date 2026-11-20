// Fit check («Έλεγχος εφαρμογής») strings. Greek first, English second. One message per screen (FitCheckView).

import Foundation

extension Strings {
    var fitButton: String { t("Έλεγχος εφαρμογής", "Fit check") }
    var fitAgain: String { t("Έλεγχος ξανά", "Check again") }
    var fitClose: String { t("Κλείσιμο", "Close") }
    var fitDone: String { t("Εντάξει", "OK") }

    func fitTitle(_ s: FitState) -> String {
        switch s {
        case .checking: return t("Ελέγχουμε την εφαρμογή…", "Checking the fit…")
        case .ok: return t("Εφαρμογή OK ✓", "Fit OK ✓")
        case .loose: return t("Σφίξτε λίγο το λουράκι", "Tighten the strap a little")
        case .off: return t("Το βραχιόλι δεν φοριέται", "The band is not being worn")
        case .charging: return t("Φορτίζει — αποσυνδέστε για έλεγχο", "Charging — unplug to check")
        case .noLink: return twBandOff
        }
    }

    func fitLine(_ s: FitState) -> String {
        switch s {
        case .checking: return t("Διαρκεί περίπου 2 λεπτά.", "It takes about 2 minutes.")
        case .ok: return t("Το βραχιόλι εφαρμόζει σωστά.", "The band sits well on the wrist.")
        case .loose: return t("Το βραχιόλι δεν ακουμπά καλά στο δέρμα.", "The band is not touching the skin well.")
        case .off: return t("Φορέστε το στον καρπό, σφιχτά.", "Put it on the wrist, snugly.")
        case .charging: return t("Όσο φορτίζει, μετρά σαν να μη φοριέται.", "While it charges, it counts as not worn.")
        case .noLink: return t("Φέρτε το τηλέφωνο κοντά στο βραχιόλι.", "Bring the phone close to the band.")
        }
    }
}
