@_exported import Foundation
public enum UIUserInterfaceStyle { case unspecified, light, dark }
public class UITraitCollection { public var userInterfaceStyle: UIUserInterfaceStyle { .light } }
public class UIColor {
    public init() {}
    public init(red: CGFloat, green: CGFloat, blue: CGFloat, alpha: CGFloat) {}
    public init(dynamicProvider: @escaping (UITraitCollection) -> UIColor) {}
    public static let systemGroupedBackground = UIColor(), secondarySystemGroupedBackground = UIColor(), tertiarySystemFill = UIColor(),
                      separator = UIColor(), systemBackground = UIColor()
}
public struct UIBackgroundTaskIdentifier: Equatable { public static let invalid = UIBackgroundTaskIdentifier() }
public class UIApplication { public static let shared = UIApplication(); public func open(_ u: URL) {}
    public func open(_ u: URL, options: [OpenExternalURLOptionsKey: Any] = [:], completionHandler: ((Bool) -> Void)? = nil) {}
    public struct OpenExternalURLOptionsKey: Hashable {}
    public static let openSettingsURLString = "app-settings:"
    public func beginBackgroundTask(withName: String?, expirationHandler: (@MainActor @Sendable () -> Void)? = nil) -> UIBackgroundTaskIdentifier { .invalid }
    public func endBackgroundTask(_ t: UIBackgroundTaskIdentifier) {}
    public func canOpenURL(_ u: URL) -> Bool { true }
    public enum State: Int { case active, inactive, background }
    public var applicationState: State { .active }
    public struct LaunchOptionsKey: Hashable { public static let bluetoothCentrals = LaunchOptionsKey() } }
public protocol UIApplicationDelegate: AnyObject {}
public class UINotificationFeedbackGenerator { public init() {}; public enum FeedbackType { case warning, success, error }
    public func prepare() {}; public func notificationOccurred(_ t: FeedbackType) {} }
public class UIImpactFeedbackGenerator { public enum Style { case light, heavy }; public init(style: Style) {}; public func impactOccurred() {} }

// APP-REPORT: on-device PDF (UIGraphicsPDFRenderer + text and paths)
public class UIFont { public struct Weight { public static let regular = Weight(), bold = Weight(), semibold = Weight() }
    public static func systemFont(ofSize: CGFloat, weight: Weight) -> UIFont { UIFont() } }
extension NSAttributedString.Key { public static let font = NSAttributedString.Key("NSFont"), foregroundColor = NSAttributedString.Key("NSColor") }
extension NSAttributedString { public func size() -> CGSize { .zero }; public func draw(at: CGPoint) {} }
extension UIColor { public func setFill() {}; public func setStroke() {} }
public enum CGLineJoin { case miter, round, bevel }
public class UIBezierPath { public init() {}; public init(rect: CGRect) {}; public init(roundedRect: CGRect, cornerRadius: CGFloat) {}
    public init(ovalIn: CGRect) {}; public var lineWidth: CGFloat = 1; public var lineJoinStyle: CGLineJoin = .miter
    public func move(to: CGPoint) {}; public func addLine(to: CGPoint) {}; public func fill() {}; public func stroke() {}
    public func setLineDash(_ p: UnsafePointer<CGFloat>?, count: Int, phase: CGFloat) {} }
public let kCGPDFContextTitle = "Title", kCGPDFContextCreator = "Creator"
public class UIGraphicsPDFRendererFormat { public init() {}; public var documentInfo: [String: Any] = [:] }
public class UIGraphicsPDFRendererContext { public func beginPage() {} }
public class UIGraphicsPDFRenderer { public init(bounds: CGRect, format: UIGraphicsPDFRendererFormat) {}
    public func pdfData(actions: (UIGraphicsPDFRendererContext) -> Void) -> Data { Data() } }

// APP-TOWER: UIViewController + MessageUI (MailView); MessageUI imports are rewritten to `import Others`, so
// these live here (UIKit is always imported next to it).
open class UIViewController: NSObject {}
public enum MFMailComposeResult { case cancelled, saved, sent, failed }
public protocol MFMailComposeViewControllerDelegate: AnyObject {
    func mailComposeController(_ controller: MFMailComposeViewController, didFinishWith result: MFMailComposeResult, error: Error?)
}
public class MFMailComposeViewController: UIViewController {
    public static func canSendMail() -> Bool { true }
    public weak var mailComposeDelegate: MFMailComposeViewControllerDelegate?
    public func setToRecipients(_ r: [String]?) {}
    public func setSubject(_ s: String) {}
    public func setMessageBody(_ b: String, isHTML: Bool) {}
    public func addAttachmentData(_ d: Data, mimeType: String, fileName: String) {}
}
