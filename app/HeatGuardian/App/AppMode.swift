// One app, two twin modes (DESIGN.md §1): Family (English by default) and Elder (Greek by default).
// Chosen once on first launch, persisted in UserDefaults "hg.mode"; switchable in Settings › Advanced.
// Launch argument `-HGMode family|elder` overrides it (simulator screenshots).

import Foundation

enum AppMode: String, CaseIterable, Identifiable {
    case family, elder
    var id: String { rawValue }

    static let storageKey = "hg.mode"

    /// The persisted mode (nil = onboarding not done yet). A `-HGMode` launch argument wins.
    /// Owner decision Nov 19: the app is HER phone (the Tower) = .elder; .family only while «Demo: family view» is on.
    static var current: AppMode? {
        let ud = UserDefaults.standard
        if let a = ud.string(forKey: "HGMode"), let m = AppMode(rawValue: a) { return m }
        if let m = AppMode(rawValue: ud.string(forKey: storageKey) ?? "") { return m }
        return ud.bool(forKey: "hg.setup.done") ? .elder : nil
    }

    /// DESIGN.md §1: Family = English, Elder = Greek (the other language stays a toggle in Settings).
    var defaultLang: Lang { self == .family ? .en : .el }
}
