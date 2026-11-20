// FIT CHECK («Έλεγχος εφαρμογής»): is the band on the wrist well enough to read? Shown right after she puts it on.
//
// What the band tells the phone (STATUS, frozen hg_frames.c; set in frozen hg_guardian.c from frozen hg_contact.c):
//   byte 1 bit 3 (0x08) contact_ok = hg_contact worn == 2 (good). worn 1 (loose) and worn 0 (off) both send 0.
//   byte 0 bit 5 (0x20) not_worn   = the band's NOT_WORN state: worn == 0 for >= 10 min (HG_NOTWORN_SCREEN_MIN) and no
//                                     HELP / IMOK / CHECK running. It stays set until worn != 0 again.
//   byte 1 bit 5 (0x20) charging   = the charger pin. hg_contact forces worn = 0 at once while charging.
// worn itself (0 / 1 / 2) is NOT sent over BLE (only in the band's flash log record), so "loose" cannot be told apart
// from "just taken off" by a bit. What the phone can say honestly:
//   charging -> «Φορτίζει» · contact_ok -> OK · not_worn -> off · neither, after the band had time to decide -> loose.
// The last one is an inference: "the band is not reporting good contact, and has not called it off". In the minutes
// after she puts the band on that means it does not sit tight enough (or was only just taken off: the 10-min NOT_WORN
// rule has not fired yet). The screen asks her to tighten the strap, which is right in both cases.
// The band decides contact once a minute with a 2-minute hysteresis, so the phone waits `window` before any verdict
// other than OK / charging.

import Foundation

enum FitState: String, CaseIterable, Identifiable {
    case checking, ok, loose, off, charging, noLink
    var id: String { rawValue }
}

enum FitCheck {
    /// 2-min contact hysteresis + up to 1 min until the band's next minute frame.
    static let window: TimeInterval = 180
    /// A STATUS older than this is not a reading of "now" (the band sends one a minute).
    static let fresh: TimeInterval = 150

    /// The fit verdict from the band's own bits. `startedAt` = when this check (or «Έλεγχος ξανά») started.
    static func state(frame d: StatusFrame?, frameAt: Date?, connected: Bool, startedAt: Date, now: Date) -> FitState {
        guard connected else { return .noLink }
        guard let d = d, let at = frameAt, now.timeIntervalSince(at) <= fresh else { return .checking }
        if d.charging { return .charging }
        if d.contactOK { return .ok }
        // Wait for the band's verdict: a frame decided after the check started, and the window has passed.
        guard at >= startedAt, now.timeIntervalSince(startedAt) >= window else { return .checking }
        return d.notWorn ? .off : .loose
    }

    /// Opened by itself when a REAL band connects: contact not good yet, not on the charger (no nagging every night on
    /// the charger), and not within 12 h after an OK was shown.
    static func shouldAutoShow(frame d: StatusFrame?, okShownAt: Date?, now: Date) -> Bool {
        guard let d = d, !d.contactOK, !d.charging else { return false }
        if let ok = okShownAt, now.timeIntervalSince(ok) < 12 * 3600 { return false }
        return true
    }

    /// When an OK was last shown for a real band (UserDefaults "hg.fit.okAt"; never set by the mock).
    static var okShownAt: Date? {
        get { UserDefaults.standard.object(forKey: "hg.fit.okAt") as? Date }
        set { UserDefaults.standard.set(newValue, forKey: "hg.fit.okAt") }
    }

    /// Progress of the calm "checking" ring, 0…1.
    static func progress(elapsed: TimeInterval, mock: Bool) -> Double {
        let span = mock ? FitCheckMock.checkSeconds : window
        return max(0, min(1, elapsed / span))
    }
}

/// FILMING MOCK, not a reading. Scripted so the competition video can show the whole story without a band:
/// first check -> «Σφίξτε λίγο το λουράκι»; after «Έλεγχος ξανά» -> «Εφαρμογή OK ✓».
/// Used ONLY in the app's demo mode (or the -HGFitMock launch argument) and ONLY while no real band is connected
/// (FitCheckView checks the BLE phase on every tick); the screen carries the ΠΡΟΣΟΜΟΙΩΣΗ badge while it runs.
enum FitCheckMock {
    static let checkSeconds: TimeInterval = 10

    /// `round` 0 = the first check, 1+ = after «Έλεγχος ξανά».
    static func state(round: Int, elapsed: TimeInterval) -> FitState {
        if elapsed < checkSeconds { return .checking }
        return round == 0 ? .loose : .ok
    }
}
