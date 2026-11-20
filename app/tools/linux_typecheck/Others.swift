// CoreBluetooth + AVFoundation + UserNotifications + UniformTypeIdentifiers stubs (one module "Others"; the check
// script rewrites the app's imports of those frameworks to `import Others`).
@_exported import Foundation

// CoreBluetooth
public class CBUUID: NSObject { public init(string: String) {} }
public enum CBManagerState { case unknown, resetting, unsupported, unauthorized, poweredOff, poweredOn }
public struct CBCharacteristicProperties: OptionSet { public let rawValue: Int; public init(rawValue: Int) { self.rawValue = rawValue }
    public static let write = CBCharacteristicProperties(rawValue: 8), writeWithoutResponse = CBCharacteristicProperties(rawValue: 4) }
public enum CBCharacteristicWriteType { case withResponse, withoutResponse }
public class CBCharacteristic: NSObject { public var uuid: CBUUID { fatalError() }; public var value: Data? { nil }; public var isNotifying: Bool { false }; public var properties: CBCharacteristicProperties { [] } }
public class CBService: NSObject { public var uuid: CBUUID { fatalError() }; public var characteristics: [CBCharacteristic]? { nil } }
public enum CBPeripheralState { case disconnected, connecting, connected, disconnecting }
public protocol CBPeripheralDelegate: AnyObject {}
public class CBPeripheral: NSObject {
    public var name: String? { nil }; public var identifier: UUID { UUID() }; public var state: CBPeripheralState { .disconnected }
    public weak var delegate: CBPeripheralDelegate?; public var services: [CBService]? { nil }
    public func discoverServices(_ s: [CBUUID]?) {}
    public func discoverCharacteristics(_ c: [CBUUID]?, for s: CBService) {}
    public func setNotifyValue(_ on: Bool, for c: CBCharacteristic) {}
    public func readValue(for c: CBCharacteristic) {}
    public func writeValue(_ d: Data, for c: CBCharacteristic, type: CBCharacteristicWriteType) {}
}
public protocol CBCentralManagerDelegate: AnyObject { func centralManagerDidUpdateState(_ c: CBCentralManager) }
public let CBCentralManagerOptionRestoreIdentifierKey = "r", CBCentralManagerOptionShowPowerAlertKey = "p",
           CBCentralManagerScanOptionAllowDuplicatesKey = "d", CBCentralManagerRestoredStatePeripheralsKey = "rp",
           CBAdvertisementDataLocalNameKey = "n", CBAdvertisementDataServiceUUIDsKey = "u", CBATTErrorDomain = "att", CBErrorDomain = "cb"
public class CBCentralManager: NSObject {
    public init(delegate: CBCentralManagerDelegate?, queue: DispatchQueue?, options: [String: Any]? = nil) {}
    public var state: CBManagerState { .unknown }; public var isScanning: Bool { false }
    public func retrieveConnectedPeripherals(withServices s: [CBUUID]) -> [CBPeripheral] { [] }
    public func retrievePeripherals(withIdentifiers i: [UUID]) -> [CBPeripheral] { [] }
    public func scanForPeripherals(withServices s: [CBUUID]?, options: [String: Any]? = nil) {}
    public func stopScan() {}
    public func connect(_ p: CBPeripheral, options: [String: Any]? = nil) {}
    public func cancelPeripheralConnection(_ p: CBPeripheral) {}
}
public struct CBATTError { public enum Code: Int { case insufficientAuthentication = 5, insufficientAuthorization = 8, insufficientEncryptionKeySize = 12, insufficientEncryption = 15 } }
public struct CBError { public enum Code: Int { case encryptionTimedOut = 15, peerRemovedPairingInformation = 14 } }

// AVFoundation
public class AVAudioSession {
    public static func sharedInstance() -> AVAudioSession { AVAudioSession() }
    public enum Category { case playback }; public enum Mode { case `default` }
    public struct CategoryOptions: OptionSet { public let rawValue: Int; public init(rawValue: Int) { self.rawValue = rawValue }; public static let duckOthers = CategoryOptions(rawValue: 1) }
    public struct SetActiveOptions: OptionSet { public let rawValue: Int; public init(rawValue: Int) { self.rawValue = rawValue }; public static let notifyOthersOnDeactivation = SetActiveOptions(rawValue: 1) }
    public func setCategory(_ c: Category, mode: Mode, options: CategoryOptions = []) throws {}
    public func setActive(_ a: Bool, options: SetActiveOptions = []) throws {}
}
public class AVAudioPlayer { public init(contentsOf u: URL) throws {}; public var numberOfLoops = 0; public var volume: Float = 1
    @discardableResult public func play() -> Bool { true }; public func stop() {} }

// UserNotifications
public struct UNAuthorizationOptions: OptionSet { public let rawValue: Int; public init(rawValue: Int) { self.rawValue = rawValue }
    public static let alert = UNAuthorizationOptions(rawValue: 1), sound = UNAuthorizationOptions(rawValue: 2), badge = UNAuthorizationOptions(rawValue: 4) }
public struct UNNotificationPresentationOptions: OptionSet { public let rawValue: Int; public init(rawValue: Int) { self.rawValue = rawValue }
    public static let list = UNNotificationPresentationOptions(rawValue: 1), banner = UNNotificationPresentationOptions(rawValue: 2) }
public struct UNNotificationSoundName { public init(_ s: String) {} }
public class UNNotificationSound { public init(named: UNNotificationSoundName) {}; public class var `default`: UNNotificationSound { fatalError() } }
public enum UNNotificationInterruptionLevel { case passive, active, timeSensitive, critical }
public class UNNotificationContent { public init() {}; public var categoryIdentifier: String { "" }; public var userInfo: [AnyHashable: Any] { [:] } }
public class UNMutableNotificationContent: UNNotificationContent { public override init() {}; public var title = "", body = ""; public var sound: UNNotificationSound?; public var interruptionLevel = UNNotificationInterruptionLevel.active
    public override var categoryIdentifier: String { get { "" } set {} }; public override var userInfo: [AnyHashable: Any] { get { [:] } set {} } }
public class UNCalendarNotificationTrigger: UNNotificationTrigger { public init(dateMatching: DateComponents, repeats: Bool) {} }
public struct UNNotificationActionOptions: OptionSet { public let rawValue: UInt; public init(rawValue: UInt) { self.rawValue = rawValue }
    public static let authenticationRequired = Self(rawValue: 1), destructive = Self(rawValue: 2), foreground = Self(rawValue: 4) }
public class UNNotificationActionIcon { public convenience init(systemImageName: String) { fatalError() }; public convenience init(templateImageName: String) { fatalError() } }
public class UNNotificationAction { public convenience init(identifier: String, title: String, options: UNNotificationActionOptions = [], icon: UNNotificationActionIcon?) { fatalError() }
    public convenience init(identifier: String, title: String, options: UNNotificationActionOptions = []) { fatalError() } }
public struct UNNotificationCategoryOptions: OptionSet { public let rawValue: UInt; public init(rawValue: UInt) { self.rawValue = rawValue }
    public static let customDismissAction = Self(rawValue: 1) }
public class UNNotificationCategory: Hashable { public convenience init(identifier: String, actions: [UNNotificationAction], intentIdentifiers: [String], options: UNNotificationCategoryOptions = []) { fatalError() }
    public static func == (a: UNNotificationCategory, b: UNNotificationCategory) -> Bool { true }; public func hash(into h: inout Hasher) {} }
public class UNNotificationTrigger {}
public class UNNotificationRequest { public init(identifier: String, content: UNNotificationContent, trigger: UNNotificationTrigger?) {}; public var identifier: String { "" }; public var content: UNNotificationContent { fatalError() } }
public class UNNotification { public var request: UNNotificationRequest { fatalError() }; public var date: Date { Date() } }
public class UNNotificationResponse { public var notification: UNNotification { fatalError() }; public var actionIdentifier: String { "" } }
public let UNNotificationDefaultActionIdentifier = "d", UNNotificationDismissActionIdentifier = "x"
public protocol UNUserNotificationCenterDelegate: AnyObject {}
public class UNUserNotificationCenter {
    public static func current() -> UNUserNotificationCenter { UNUserNotificationCenter() }
    public weak var delegate: UNUserNotificationCenterDelegate?
    public func requestAuthorization(options: UNAuthorizationOptions, completionHandler: @escaping (Bool, Error?) -> Void) {}
    public func add(_ r: UNNotificationRequest, withCompletionHandler: ((Error?) -> Void)? = nil) {}
    public func removeAllDeliveredNotifications() {}
    public func setNotificationCategories(_ c: Set<UNNotificationCategory>) {}
    public func removePendingNotificationRequests(withIdentifiers: [String]) {}
    public func removeDeliveredNotifications(withIdentifiers: [String]) {}
    public func getDeliveredNotifications(completionHandler: @escaping ([UNNotification]) -> Void) {}
}

// CoreLocation (Her Day: Visits, one-shot fix, authorization)
public struct CLLocationCoordinate2D { public var latitude: Double; public var longitude: Double
    public init() { latitude = 0; longitude = 0 }; public init(latitude: Double, longitude: Double) { self.latitude = latitude; self.longitude = longitude } }
public func CLLocationCoordinate2DIsValid(_ c: CLLocationCoordinate2D) -> Bool { true }
public typealias CLLocationDistance = Double
public typealias CLLocationAccuracy = Double
public let kCLLocationAccuracyHundredMeters: CLLocationAccuracy = 100
public class CLLocation: NSObject { public init(latitude: Double, longitude: Double) {}; public var coordinate: CLLocationCoordinate2D { CLLocationCoordinate2D() }
    public func distance(from l: CLLocation) -> CLLocationDistance { 0 } }
public class CLVisit: NSObject { public var arrivalDate: Date { Date() }; public var departureDate: Date { Date() }
    public var coordinate: CLLocationCoordinate2D { CLLocationCoordinate2D() }; public var horizontalAccuracy: CLLocationAccuracy { 0 } }
public enum CLAuthorizationStatus: Int32 { case notDetermined = 0, restricted, denied, authorizedAlways, authorizedWhenInUse }
public protocol CLLocationManagerDelegate: NSObjectProtocol {}
public class CLLocationManager: NSObject {
    public override init() {}
    public weak var delegate: CLLocationManagerDelegate?
    public var authorizationStatus: CLAuthorizationStatus { .notDetermined }
    public var desiredAccuracy: CLLocationAccuracy = 0
    public func requestAlwaysAuthorization() {}; public func requestWhenInUseAuthorization() {}
    public func startMonitoringVisits() {}; public func stopMonitoringVisits() {}; public func requestLocation() {}
}

// MapKit (Her Day: point of interest near a visit -> place type)
public struct MKPointOfInterestCategory: Hashable, RawRepresentable { public let rawValue: String; public init(rawValue: String) { self.rawValue = rawValue }
    public static let foodMarket = Self(rawValue: "MKPOICategoryFoodMarket"), store = Self(rawValue: "MKPOICategoryStore"), bakery = Self(rawValue: "MKPOICategoryBakery"),
        park = Self(rawValue: "MKPOICategoryPark"), beach = Self(rawValue: "MKPOICategoryBeach"), nationalPark = Self(rawValue: "MKPOICategoryNationalPark"),
        pharmacy = Self(rawValue: "MKPOICategoryPharmacy"), cafe = Self(rawValue: "MKPOICategoryCafe"), restaurant = Self(rawValue: "MKPOICategoryRestaurant"),
        hospital = Self(rawValue: "MKPOICategoryHospital") }
public class MKPlacemark: NSObject { public var coordinate: CLLocationCoordinate2D { CLLocationCoordinate2D() } }
public class MKMapItem: NSObject { public var name: String? { nil }
    @available(*, deprecated, message: "deprecated in iOS 26.0: use location / address") public var placemark: MKPlacemark { MKPlacemark() }
    public var location: CLLocation { CLLocation(latitude: 0, longitude: 0) }
    public var pointOfInterestCategory: MKPointOfInterestCategory? { nil } }
public class MKLocalPointsOfInterestRequest: NSObject { public init(center: CLLocationCoordinate2D, radius: CLLocationDistance) {} }
public class MKLocalSearch: NSObject {
    public class Response: NSObject { public var mapItems: [MKMapItem] { [] } }
    public init(request: MKLocalPointsOfInterestRequest) {}
    public func start(completionHandler: @escaping @MainActor @Sendable (MKLocalSearch.Response?, (any Error)?) -> Void) {}
}

// Security (Keychain) — TowerKeychain.swift
public typealias OSStatus = Int32
public typealias CFDictionary = NSDictionary
public typealias CFTypeRef = AnyObject
public let errSecSuccess: OSStatus = 0
public let kSecClass = "class", kSecClassGenericPassword = "genp", kSecAttrService = "svce", kSecAttrAccount = "acct",
           kSecReturnData = "r_Data", kSecMatchLimit = "m_Limit", kSecMatchLimitOne = "m_LimitOne", kSecValueData = "v_Data",
           kSecAttrAccessible = "pdmn", kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly = "cku"
@discardableResult public func SecItemCopyMatching(_ q: CFDictionary, _ r: UnsafeMutablePointer<AnyObject?>?) -> OSStatus { 0 }
@discardableResult public func SecItemAdd(_ q: CFDictionary, _ r: UnsafeMutablePointer<AnyObject?>?) -> OSStatus { 0 }
@discardableResult public func SecItemDelete(_ q: CFDictionary) -> OSStatus { 0 }
