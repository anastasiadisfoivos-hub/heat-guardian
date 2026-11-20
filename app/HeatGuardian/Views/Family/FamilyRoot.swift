// Family mode: the system TabView (iOS 26 floating glass tab bar, minimizes on scroll) — no custom tab bar
// (DESIGN.md §8). Four tabs: Today · Tomorrow · History · Settings. HELP / DANGER / unanswered CHECK take over
// the whole screen with AlertView.

import SwiftUI

enum AppTab: String, Hashable { case today, tomorrow, history, settings }

struct FamilyRoot: View {
    @EnvironmentObject var m: AppModel
    @Environment(\.hgOverride) private var override
    @State private var tab: AppTab
    @State private var sampleAlert: AlertInfo?

    init(tab: AppTab? = nil) {
        let start = tab ?? AppTab(rawValue: UserDefaults.standard.string(forKey: "HGTab") ?? "") ?? .today
        _tab = State(initialValue: start)
    }

    var body: some View {
        let L = m.L
        TabView(selection: $tab) {
            Tab(L.tabToday, systemImage: "heart", value: AppTab.today) { TodayView(tab: $tab) }
            Tab(L.tabTomorrow, systemImage: "sun.max", value: AppTab.tomorrow) { TomorrowView() }
            Tab(L.tabHistory, systemImage: "clock", value: AppTab.history) { HistoryView() }
            Tab(L.tabSettings, systemImage: "gearshape", value: AppTab.settings) { SettingsView() }
        }
        .tabBarMinimizeBehavior(.onScrollDown)
        .tint(Palette.primary)
        .fullScreenCover(item: $m.alert) { a in
            AlertView(a: a).environmentObject(m)
        }
        .fullScreenCover(item: $sampleAlert) { a in
            AlertView(a: a, sample: true).environmentObject(m)
        }
        .onAppear {
            if let k = override.alert, sampleAlert == nil { sampleAlert = SampleData.alert(k) }
        }
    }
}

/// Previews: a family tab with a state override (no band needed).
struct FamilyPreview: View {
    var state: OverrideState?
    var tab: AppTab = .today
    var lang: Lang = .en

    var body: some View {
        FamilyRoot(tab: tab)
            .environmentObject(AppModel.shared)
            .environment(\.hgOverride, UIOverride(state: state))
            .environment(\.locale, lang.locale)
            .onAppear { AppModel.shared.lang = lang }
    }
}
