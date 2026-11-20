// Her phone's on-device visit store (HERDAY_SPEC.md §2, §6; Elder mode only). Learned places keep their coordinates
// HERE, for matching the next visit to the same place — they are never sent anywhere: the band gets only the place
// TYPE and the time (CMD 0x1C VISIT), queued while the band is away. Persisted as JSON in Application Support
// (visits.json), 60 days. Pure Foundation (tested on Linux); Core Location feeds it through AppModel.

import Foundation

/// Location permission as the app shows it (VisitMonitor maps CLAuthorizationStatus to it).
enum LocationAuth: Equatable { case notDetermined, denied, whenInUse, always }

struct LearnedPlace: Codable, Identifiable, Equatable {
    var id: String
    var lat: Double
    var lon: Double
    var type: PlaceType              // from the POI lookup, or set by the family in Settings
    var name: String?                // POI name (shown in Settings on her phone only)
    var typed = false                // the POI lookup ran (once per place)
    var userTyped = false            // set by hand: the lookup never overrides it
}

struct VisitRecord: Codable, Identifiable, Equatable {
    var id: String
    var placeID: String
    var arrive: Date?                // nil = iOS did not know the arrival
    var leave: Date?
}

/// A VISIT frame waiting for the band. The place is resolved to its type when it is sent (a POI lookup or the home
/// rule may have typed the place meanwhile).
struct PendingVisit: Codable, Equatable {
    var edge: VisitEdge
    var placeID: String
    var at: Date
}

final class VisitStore {
    private(set) var places: [LearnedPlace] = []
    private(set) var visits: [VisitRecord] = []
    private(set) var pending: [PendingVisit] = []
    /// Set with «Εδώ είναι το σπίτι» in Settings; else the home rule decides.
    private(set) var homeSetByUser: String?

    static let matchRadius = 120.0       // metres: a new visit within this of a learned place is that place
    static let keepDays = 60
    static let maxPending = 64

    private let url: URL?

    init(fileName: String? = "visits.json") {
        if let f = fileName {
            url = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent(f)
            load()
        } else {
            url = nil
        }
    }

    private struct File: Codable {
        var places: [LearnedPlace]
        var visits: [VisitRecord]
        var pending: [PendingVisit]
        var homeSetByUser: String?
    }

    private func load() {
        guard let u = url, let d = try? Data(contentsOf: u), let f = try? JSONDecoder().decode(File.self, from: d) else { return }
        places = f.places; visits = f.visits; pending = f.pending; homeSetByUser = f.homeSetByUser
        prune(now: Date())
    }

    func save() {
        guard let u = url else { return }
        try? FileManager.default.createDirectory(at: u.deletingLastPathComponent(), withIntermediateDirectories: true)
        let f = File(places: places, visits: visits, pending: pending, homeSetByUser: homeSetByUser)
        if let d = try? JSONEncoder().encode(f) { try? d.write(to: u, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication]) }
    }

    private func prune(now: Date) {
        let cut = now.addingTimeInterval(-Double(VisitStore.keepDays) * 86400)
        visits.removeAll { ($0.leave ?? $0.arrive ?? now) < cut }
        let used = Set(visits.map { $0.placeID } + [homeSetByUser].compactMap { $0 })
        places.removeAll { !used.contains($0.id) }
    }

    /// Great-circle distance in metres (haversine).
    static func distance(_ lat1: Double, _ lon1: Double, _ lat2: Double, _ lon2: Double) -> Double {
        let r = 6_371_000.0, d2r = Double.pi / 180
        let dLat = (lat2 - lat1) * d2r, dLon = (lon2 - lon1) * d2r
        let a = sin(dLat / 2) * sin(dLat / 2) + cos(lat1 * d2r) * cos(lat2 * d2r) * sin(dLon / 2) * sin(dLon / 2)
        return 2 * r * asin(min(1, sqrt(a)))
    }

    /// The learned place within 120 m (nearest), or a new one.
    func place(lat: Double, lon: Double) -> (LearnedPlace, isNew: Bool) {
        if let p = places.map({ ($0, VisitStore.distance(lat, lon, $0.lat, $0.lon)) })
            .filter({ $0.1 <= VisitStore.matchRadius }).min(by: { $0.1 < $1.1 })?.0 {
            return (p, false)
        }
        let p = LearnedPlace(id: UUID().uuidString, lat: lat, lon: lon, type: .other)
        places.append(p)
        return (p, true)
    }

    /// One CLVisit (iOS sends a visit at arrival and again, with the departure, when she leaves). Returns the place
    /// (and whether it is new, so the caller looks its type up) and queues the ARRIVE / LEAVE edges not yet queued.
    @discardableResult
    func record(lat: Double, lon: Double, arrive: Date?, leave: Date?, now: Date = Date()) -> (LearnedPlace, isNew: Bool) {
        let (p, isNew) = place(lat: lat, lon: lon)
        // the same visit again: same place, arrival within 2 min (or both unknown and still open)
        if let i = visits.lastIndex(where: { v in
            v.placeID == p.id && v.leave == nil && (arrive == nil || v.arrive == nil || abs(v.arrive!.timeIntervalSince(arrive!)) < 120)
        }) {
            if visits[i].arrive == nil, let a = arrive { visits[i].arrive = a }
            if let l = leave {
                visits[i].leave = l
                enqueue(PendingVisit(edge: .leave, placeID: p.id, at: l))
            }
        } else {
            let v = VisitRecord(id: UUID().uuidString, placeID: p.id, arrive: arrive, leave: leave)
            visits.append(v)
            if let a = arrive { enqueue(PendingVisit(edge: .arrive, placeID: p.id, at: a)) }
            if let l = leave { enqueue(PendingVisit(edge: .leave, placeID: p.id, at: l)) }
        }
        prune(now: now)
        return (p, isNew)
    }

    private func enqueue(_ v: PendingVisit) {
        pending.append(v)
        if pending.count > VisitStore.maxPending { pending.removeFirst(pending.count - VisitStore.maxPending) }
    }

    func setType(_ placeID: String, _ t: PlaceType, name: String? = nil, byUser: Bool) {
        guard let i = places.firstIndex(where: { $0.id == placeID }) else { return }
        if places[i].userTyped && !byUser { return }
        places[i].type = t
        places[i].typed = true
        if let n = name { places[i].name = n }
        if byUser { places[i].userTyped = true }
    }

    /// «Εδώ είναι το σπίτι»: the place at these coordinates (learned or new) becomes home.
    func setHome(lat: Double, lon: Double) {
        let (p, _) = place(lat: lat, lon: lon)
        homeSetByUser = p.id
    }

    func setHome(placeID: String?) { homeSetByUser = placeID }

    func remove(_ placeID: String) {
        places.removeAll { $0.id == placeID }
        visits.removeAll { $0.placeID == placeID }
        pending.removeAll { $0.placeID == placeID }
        if homeSetByUser == placeID { homeSetByUser = nil }
    }

    func clearAll() {
        places = []; visits = []; pending = []; homeSetByUser = nil
    }

    /// Home: set by hand, else the home rule (most overnight dwell, last 14 days).
    func homeID(now: Date = Date()) -> String? {
        if let h = homeSetByUser { return h }
        let stays = visits.compactMap { v in v.arrive.map { HomeRule.Stay(placeID: v.placeID, arrive: $0, leave: v.leave) } }
        return HomeRule.detect(stays, now: now)
    }

    func type(of placeID: String, home: String?) -> PlaceType {
        if placeID == home { return .home }
        return places.first { $0.id == placeID }?.type ?? .other
    }

    /// The visits as the routine model sees them (type resolved now; home included as type 0).
    func samples(now: Date = Date()) -> [VisitSample] {
        let h = homeID(now: now)
        return visits.compactMap { v in v.arrive.map { VisitSample(place: type(of: v.placeID, home: h), arrive: $0, leave: v.leave) } }
    }

    /// The queued VISIT frames, oldest first, with the place resolved; `markSent` drops them.
    func pendingFrames(now: Date = Date()) -> [(PendingVisit, [UInt8])] {
        let h = homeID(now: now)
        return pending.map { p in
            (p, Frames.cmdVisit(p.edge, place: type(of: p.placeID, home: h), unix: UInt32(max(0, p.at.timeIntervalSince1970))))
        }
    }

    func markSent(_ sent: [PendingVisit]) {
        for s in sent { if let i = pending.firstIndex(of: s) { pending.remove(at: i) } }
    }
}
