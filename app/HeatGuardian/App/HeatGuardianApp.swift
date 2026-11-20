// Heat Guardian — one iPhone app, two twin modes (DESIGN.md §1): Family (4 tabs, English) and Elder (one screen,
// Greek). SwiftUI, iOS 26 Liquid Glass, CoreBluetooth, no third-party packages.
//
// Launch arguments (simulator screenshots, see ios/README.md):
//   -HGDemo YES            start the demo          -HGDemoAt <minute index>  seek it
//   -HGMode family|elder   skip onboarding         -HGTab today|tomorrow|history|settings
//   -HGState ok|heat|water|danger|check|help|offline   force the screen state
//   -HGFamilyMsg 1|2|3     (elder) show a family message     -HGAlert help|danger|family  (family) the alert screen
//   -HGLang el|en          language (default: the mode's)    -HGOnboarding YES  show the first-launch question

import SwiftUI

@main
struct HeatGuardianApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var model = AppModel.shared
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(model)
                .environment(\.locale, model.lang.locale)
                .environment(\.hgOverride, UIOverride.fromLaunchArguments())
                .onOpenURL { model.towerHandleURL($0) }      // Shortcuts' x-success / x-error ([SMS-SHORTCUT])
                .onAppear {
                    AlertFX.shared.requestNotificationPermission()
                    let ud = UserDefaults.standard
                    if let l = ud.string(forKey: "HGLang").flatMap(Lang.init(rawValue:)) {
                        model.lang = l
                    } else if let mode = ud.string(forKey: "HGMode").flatMap(AppMode.init(rawValue:)) {
                        model.lang = mode.defaultLang
                    } else if ud.object(forKey: "hg.lang") == nil {
                        model.lang = .el          // owner decision Nov 19: Greek by default
                    }
                    if ud.bool(forKey: "HGDemo"), !model.isDemo {
                        model.startDemo()
                        if ud.object(forKey: "HGDemoAt") != nil { model.seekDemo(ud.integer(forKey: "HGDemoAt")) }
                    }
                }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .background { model.saveHistory(); model.store.save(); model.towerNotifyPendingShortcut() }
            if phase == .active { model.now = Date(); model.towerBecameActive() }
        }
    }
}

/// Owner decision Nov 19: the app runs on HER phone. SETUP on first launch, then her screen (THE TOWER).
/// The old family dashboard is a demo only: Settings › «Demo: family view» (stored as mode "family").
/// Launch arguments: -HGOnboarding YES = setup; -HGMode family = the family view; -HGMode elder = her screen.
struct RootView: View {
    @EnvironmentObject var m: AppModel
    @AppStorage(AppMode.storageKey) private var modeRaw = ""
    @AppStorage("hg.setup.done") private var setupDone = false

    private var showSetup: Bool {
        let ud = UserDefaults.standard
        if ud.bool(forKey: "HGOnboarding") { return true }
        if ud.string(forKey: "HGMode") != nil { return false }
        return !setupDone
    }
    private var familyView: Bool {
        if let a = UserDefaults.standard.string(forKey: "HGMode").flatMap(AppMode.init(rawValue:)) { return a == .family }
        return AppMode(rawValue: modeRaw) == .family
    }

    var body: some View {
        Group {
            if showSetup {
                SetupView {
                    modeRaw = AppMode.elder.rawValue
                    setupDone = true
                    m.updateLocation()
                }
            } else if familyView {
                FamilyRoot()
            } else {
                TowerHomeView()
            }
        }
        .animation(.easeInOut(duration: 0.4), value: modeRaw)
        .animation(.easeInOut(duration: 0.4), value: setupDone)
    }
}
