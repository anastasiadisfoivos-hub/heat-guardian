// Elder mode location (HERDAY_SPEC.md §2, §3, §6): iOS Visits (CLLocationManager.startMonitoringVisits, Always
// authorization), a one-shot fix for «Εδώ είναι το σπίτι», and the place-type lookup (MapKit points of interest
// near the visit). The coordinates stay on this phone (VisitStore); the band and the family only ever get a type.
// Privacy note: the POI lookup is an Apple Maps request (Apple sees that point, as for any map search) — once per
// new place, never repeated for a known place. No other server is involved.

import CoreLocation
import Foundation
import MapKit

final class VisitMonitor: NSObject, CLLocationManagerDelegate {
    typealias Auth = LocationAuth

    /// (lat, lon, arrival or nil, departure or nil)
    var onVisit: ((Double, Double, Date?, Date?) -> Void)?
    var onAuth: ((Auth) -> Void)?
    /// One-shot fix for «Εδώ είναι το σπίτι».
    var onHere: ((Double, Double) -> Void)?
    var onHereFailed: (() -> Void)?

    private let lm = CLLocationManager()
    private var wanted = false
    private var wantHere = false

    override init() {
        super.init()
        lm.delegate = self
    }

    var auth: Auth { VisitMonitor.map(lm.authorizationStatus) }

    static func map(_ s: CLAuthorizationStatus) -> Auth {
        switch s {
        case .authorizedAlways: return .always
        case .authorizedWhenInUse: return .whenInUse
        case .denied, .restricted: return .denied
        case .notDetermined: return .notDetermined
        @unknown default: return .denied
        }
    }

    /// Starts Visits monitoring, asking for Always authorization first if needed.
    func start() {
        wanted = true
        switch lm.authorizationStatus {
        case .notDetermined, .authorizedWhenInUse:
            lm.requestAlwaysAuthorization()
        default:
            break
        }
        if lm.authorizationStatus == .authorizedAlways || lm.authorizationStatus == .authorizedWhenInUse {
            lm.startMonitoringVisits()
        }
    }

    func stop() {
        wanted = false
        lm.stopMonitoringVisits()
    }

    /// «Εδώ είναι το σπίτι»: one location fix (100 m is plenty for matching a place).
    func requestHere() {
        wantHere = true
        lm.desiredAccuracy = kCLLocationAccuracyHundredMeters
        if lm.authorizationStatus == .notDetermined { lm.requestWhenInUseAuthorization() } else { lm.requestLocation() }
    }

    // MARK: CLLocationManagerDelegate

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        onAuth?(auth)
        let s = manager.authorizationStatus
        if wanted && (s == .authorizedAlways || s == .authorizedWhenInUse) { manager.startMonitoringVisits() }
        if wantHere && s != .notDetermined { manager.requestLocation() }
    }

    func locationManager(_ manager: CLLocationManager, didVisit visit: CLVisit) {
        let a: Date? = visit.arrivalDate == Date.distantPast ? nil : visit.arrivalDate
        let d: Date? = visit.departureDate == Date.distantFuture ? nil : visit.departureDate
        let c = visit.coordinate
        guard CLLocationCoordinate2DIsValid(c), a != nil || d != nil else { return }
        onVisit?(c.latitude, c.longitude, a, d)
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard wantHere, let l = locations.last else { return }
        wantHere = false
        onHere?(l.coordinate.latitude, l.coordinate.longitude)
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        if wantHere {
            wantHere = false
            onHereFailed?()
        }
    }

    // MARK: place type (MapKit POI near the visit)

    /// The nearest point of interest within ~80 m -> place type (+ its name, kept on this phone). `.other` when
    /// nothing is found. The completion runs on the main queue.
    static func lookupType(lat: Double, lon: Double, completion: @escaping (PlaceType, String?) -> Void) {
        let center = CLLocationCoordinate2D(latitude: lat, longitude: lon)
        let req = MKLocalPointsOfInterestRequest(center: center, radius: 80)
        let search = MKLocalSearch(request: req)
        search.start { response, _ in
            let here = CLLocation(latitude: lat, longitude: lon)
            // iOS 26: MKMapItem.location (MKMapItem.placemark is deprecated in iOS 26.0)
            let best = (response?.mapItems ?? []).min { a, b in a.location.distance(from: here) < b.location.distance(from: here) }
            let t = PlaceMapping.type(category: categoryKey(best?.pointOfInterestCategory), name: best?.name)
            DispatchQueue.main.async { completion(t, best?.name) }
        }
    }

    /// MKPointOfInterestCategory -> the keys PlaceMapping knows (spec §3).
    static func categoryKey(_ c: MKPointOfInterestCategory?) -> String? {
        guard let c = c else { return nil }
        let table: [(MKPointOfInterestCategory, String)] = [
            (.foodMarket, "foodMarket"), (.store, "store"), (.bakery, "bakery"),
            (.park, "park"), (.beach, "beach"), (.nationalPark, "nationalPark"),
            (.pharmacy, "pharmacy"), (.cafe, "cafe"), (.restaurant, "restaurant"), (.hospital, "hospital"),
        ]
        return table.first { $0.0 == c }?.1
    }
}
