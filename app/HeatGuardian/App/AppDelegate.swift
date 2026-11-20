// The notification delegate must be in place before launch finishes, so an action tapped on the lock screen
// («Σας καλώ» / «Έρχομαι» / «Το είδα») while the app was suspended or relaunched is delivered to AppModel.

import UIKit

final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        AlertFX.shared.setUp()
        _ = AppModel.shared          // wires AlertFX.onAction and, with a saved band, starts the background re-connect
        return true
    }
}
