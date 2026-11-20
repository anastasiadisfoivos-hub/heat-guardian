// Her stated routine (ECOSYSTEM_SPEC §5b). Everything is optional: nil = "not stated, the band learns it".
// Sent to the band as CMD 0x19 ROUTINE_SEED; used by the app's Tomorrow simulation (home class + nudge times).

import Foundation

struct TimeWindow: Codable, Equatable {
    var from: Int      // minute of day
    var to: Int
    func contains(_ m: Int) -> Bool { from <= to ? (m >= from && m < to) : (m >= from || m < to) }
}

enum Floor: String, Codable, CaseIterable, Identifiable { case ground, middle, top; var id: String { rawValue } }
enum Build: String, Codable, CaseIterable, Identifiable { case old, insulated; var id: String { rawValue } }

struct Routine: Codable, Equatable {
    var wake: Int?            // minute of day
    var bed: Int?
    var nap: TimeWindow?
    var out1: TimeWindow?
    var out2: TimeWindow?
    /// A/C at home: nil = not stated (ROUTINE_SEED flags 0xFF).
    var ac: Bool?
    var floor: Floor?
    var build: Build?

    static let defaultWake = 7 * 60 + 30     // tomorrow/routine.py default day
    static let defaultBed = 23 * 60

    var wakeOrDefault: Int { wake ?? Routine.defaultWake }
    var bedOrDefault: Int { bed ?? Routine.defaultBed }

    /// Tomorrow Engine home class (tomorrow/indoor.py CLASSES):
    /// insulated -> A (top floor insulated -> B); old: ground -> D, middle -> B, top -> C. nil = not stated.
    var homeClass: String? {
        guard let f = floor else { return build == .insulated ? "A" : nil }
        switch (f, build ?? .old) {
        case (.top, .insulated): return "B"
        case (_, .insulated): return "A"
        case (.ground, .old): return "D"
        case (.middle, .old): return "B"
        case (.top, .old): return "C"
        }
    }

    /// Asleep (night or nap) at minute of day m, using her stated times or the defaults.
    func asleep(_ m: Int) -> Bool {
        let night = TimeWindow(from: bedOrDefault, to: wakeOrDefault)
        return night.contains(m) || (nap?.contains(m) ?? false)
    }

    var outWindows: [TimeWindow] { [out1, out2].compactMap { $0 } }

    var seedFrame: [UInt8] {
        Frames.cmdRoutineSeed(wake: wake, bed: bed, napFrom: nap?.from, napTo: nap?.to,
                              out1From: out1?.from, out1To: out1?.to, out2From: out2?.from, out2To: out2?.to, ac: ac)
    }

    var isEmpty: Bool { self == Routine() }

    static func hhmm(_ m: Int) -> String { String(format: "%02d:%02d", (m / 60) % 24, m % 60) }

    // persistence (UserDefaults, JSON)
    private static let key = "hg.routine"
    static func load() -> Routine {
        guard let d = UserDefaults.standard.data(forKey: key), let r = try? JSONDecoder().decode(Routine.self, from: d) else { return Routine() }
        return r
    }
    func save() {
        if let d = try? JSONEncoder().encode(self) { UserDefaults.standard.set(d, forKey: Routine.key) }
    }
}

extension Date {
    /// Minute of day in the current calendar.
    var minuteOfDay: Int {
        let c = Calendar.current.dateComponents([.hour, .minute], from: self)
        return (c.hour ?? 0) * 60 + (c.minute ?? 0)
    }
    /// The same day at minute of day m.
    func at(minute m: Int) -> Date { Calendar.current.startOfDay(for: self).addingTimeInterval(TimeInterval(m * 60)) }
}
