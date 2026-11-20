// Sound, haptics and local notifications for the family alert.
// Categories: HG_ALERT with «Σας καλώ» / «Έρχομαι» / «Το είδα». Gentle and evening-summary notifications.
// chime.wav (bundled) = the dashboard's three-tone chime (880 / 660 / 880 Hz) followed by silence, 4 s long, looped.

import AVFoundation
import UIKit
import UserNotifications

final class AlertFX: NSObject, UNUserNotificationCenterDelegate {
    static let shared = AlertFX()
    private var player: AVAudioPlayer?
    private var hapticTimer: Timer?

    /// Notification actions (identifier, userInfo, done). Set by AppModel; `done` must be called when the work
    /// (e.g. the BLE writes) is finished so iOS can suspend the app again.
    var onAction: ((String, [AnyHashable: Any], @escaping () -> Void) -> Void)?

    static let alertCategory = "HG_ALERT"
    static let actionCall = "HG_CALL"         // «Σας καλώ»  -> FAMILY_ACK 2 + FAMILY_MSG 1 (opens the app / dialler)
    static let actionComing = "HG_COMING"     // «Έρχομαι»   -> FAMILY_MSG 2 (background, works from the lock screen)
    static let actionSeen = "HG_SEEN"         // «Το είδα»   -> FAMILY_MSG 3 (background)
    static let summaryID = "hg.summary"

    /// Called from AppDelegate.didFinishLaunching, so actions tapped while the app was not running are delivered.
    func setUp() {
        UNUserNotificationCenter.current().delegate = self
        registerCategories(Strings(lang: .el))
    }

    /// Action titles are fixed at registration: re-register when the language changes.
    func registerCategories(_ L: Strings) {
        let call = UNNotificationAction(identifier: AlertFX.actionCall, title: L.actCall, options: [.foreground],
                                        icon: UNNotificationActionIcon(systemImageName: "phone.fill"))
        let coming = UNNotificationAction(identifier: AlertFX.actionComing, title: L.actComing, options: [],
                                          icon: UNNotificationActionIcon(systemImageName: "figure.walk"))
        let seen = UNNotificationAction(identifier: AlertFX.actionSeen, title: L.actSeen, options: [],
                                        icon: UNNotificationActionIcon(systemImageName: "checkmark"))
        let cat = UNNotificationCategory(identifier: AlertFX.alertCategory, actions: [call, coming, seen],
                                         intentIdentifiers: [], options: [])
        UNUserNotificationCenter.current().setNotificationCategories([cat])
    }

    func requestNotificationPermission() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in }
    }

    /// Plays even with the ring/silent switch on silent (category .playback) while the app is open.
    func start() {
        stop()
        do {
            try AVAudioSession.sharedInstance().setCategory(.playback, mode: .default, options: [.duckOthers])
            try AVAudioSession.sharedInstance().setActive(true)
        } catch { /* the screen and the haptics still show the alert */ }
        if let url = Bundle.main.url(forResource: "chime", withExtension: "wav") {
            player = try? AVAudioPlayer(contentsOf: url)
            player?.numberOfLoops = -1
            player?.volume = 1.0
            player?.play()
        }
        buzz()
        hapticTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in self?.buzz() }
    }

    func stop() {
        player?.stop()
        player = nil
        hapticTimer?.invalidate()
        hapticTimer = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: [.notifyOthersOnDeactivation])
    }

    private func buzz() {
        let g = UINotificationFeedbackGenerator()
        g.prepare()
        g.notificationOccurred(.warning)
    }

    func tick() {
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }

    /// Local notification: the lock-screen / background path (the app keeps running in the background through
    /// UIBackgroundModes bluetooth-central, so a STATUS notify from the band wakes it).
    /// Urgent (HELP / DANGER / CHECK not answered): chime, with the three family actions. Interruption level .active:
    /// the app has no Time Sensitive Notifications entitlement (a free Personal Team cannot sign it), so alerts respect
    /// Focus / Do Not Disturb. With a paid team, add the capability back and use .timeSensitive here.
    func post(title: String, body: String, id: String, userInfo: [AnyHashable: Any] = [:]) {
        let c = UNMutableNotificationContent()
        c.title = title
        c.body = body
        c.sound = UNNotificationSound(named: UNNotificationSoundName("chime.wav"))
        c.interruptionLevel = .active
        c.categoryIdentifier = AlertFX.alertCategory
        c.userInfo = userInfo
        let req = UNNotificationRequest(identifier: id, content: c, trigger: nil)
        UNUserNotificationCenter.current().add(req) { _ in }
    }

    /// [SMS-SHORTCUT] The app is in the background and cannot open Shortcuts itself: «tap to send the alert». Tapping
    /// it brings the app to the front, which opens the waiting Shortcut (AppModel.towerBecameActive).
    func postShortcutTap(title: String, body: String, id: String) {
        let c = UNMutableNotificationContent()
        c.title = title
        c.body = body
        c.sound = .default
        c.interruptionLevel = .active
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: id, content: c, trigger: nil)) { _ in }
    }

    /// Gentle (2 missed nudges in a row): no sound, passive (does not light the screen).
    func postGentle(title: String, body: String, id: String) {
        let c = UNMutableNotificationContent()
        c.title = title
        c.body = body
        c.interruptionLevel = .passive
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: id, content: c, trigger: nil)) { _ in }
    }

    /// The evening summary: one pending request (same id = replaced), at `date`, with the latest text.
    func scheduleSummary(title: String, body: String, at date: Date) {
        let c = UNMutableNotificationContent()
        c.title = title
        c.body = body
        c.sound = .default
        c.interruptionLevel = .active
        let comps = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: date)
        let trig = UNCalendarNotificationTrigger(dateMatching: comps, repeats: false)
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: AlertFX.summaryID, content: c, trigger: trig)) { _ in }
    }

    func cancelSummary() {
        UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: [AlertFX.summaryID])
    }

    /// Removes delivered ALERT notifications only (the summary and gentle ones stay in the list).
    func clearDelivered() {
        let center = UNUserNotificationCenter.current()
        center.getDeliveredNotifications { list in
            let ids = list.filter { $0.request.content.categoryIdentifier == AlertFX.alertCategory }.map { $0.request.identifier }
            center.removeDeliveredNotifications(withIdentifiers: ids)
        }
    }

    // While the app is open the full-screen alert already plays the chime: show the banner in the list only.
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        if notification.request.content.categoryIdentifier == AlertFX.alertCategory {
            completionHandler([.list])
        } else {
            completionHandler([.banner, .list])
        }
    }

    /// Lock-screen / banner actions. Runs in the background for «Έρχομαι» / «Το είδα» (the app is alive through
    /// bluetooth-central while the band is connected); a background task keeps it awake until the writes are out.
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        let id = response.actionIdentifier
        guard [AlertFX.actionCall, AlertFX.actionComing, AlertFX.actionSeen].contains(id), let handler = onAction else {
            completionHandler()
            return
        }
        let info = response.notification.request.content.userInfo
        DispatchQueue.main.async {
            var task = UIBackgroundTaskIdentifier.invalid
            var finished = false
            let finish = {
                guard !finished else { return }
                finished = true
                completionHandler()
                if task != .invalid { UIApplication.shared.endBackgroundTask(task) }
            }
            task = UIApplication.shared.beginBackgroundTask(withName: "hg.familyAction") { finish() }
            handler(id, info, finish)
        }
    }
}
