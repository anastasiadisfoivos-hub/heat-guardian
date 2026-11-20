// «Σήμερα»: everything the Today screen needs, recomputed whenever AppModel changes.

import Combine
import Foundation

struct HeroState: Equatable {
    var stateKey: String         // OK / DRINK / COOL / DANGER / CHECK / HELP / IMOK / BATTERY / NOT_WORN / WAIT / OFFLINE
    var title: String            // big word («Όλα καλά», «Χωρίς σύνδεση», …)
    var subtitle: String         // the state's explanation, or the last-known line when offline
    var reason: String?          // §4 reason line («Πολλή ζέστη στο σπίτι 31°»), nil = none
    var symbol: String           // SF Symbol (Theme.symbol)
    var tone: Tone
    var urgent: Bool             // DANGER / HELP / CHECK: pulse
    var isOffline: Bool
    var updatedText: String      // «Ενημέρωση πριν 2 λεπτά» / «Τελευταίος συγχρονισμός 14:05» / SIM clock
    var lastSyncAt: Date?
    var simulated: Bool
}

final class TodayViewModel: ObservableObject {
    @Published private(set) var hero = HeroState(stateKey: "WAIT", title: "", subtitle: "", reason: nil, symbol: "antenna.radiowaves.left.and.right",
                                                 tone: .neutral, urgent: false, isOffline: false, updatedText: "", lastSyncAt: nil, simulated: false)
    /// Today's log, oldest first, planned nudges included as `isUpcoming` rows.
    @Published private(set) var rows: [LogRow] = []
    @Published private(set) var summary = DaySummary(day: Date(), nudgesShown: 0, nudgesDone: 0, water: 0, warnings: 0, helps: 0)
    @Published private(set) var summaryText = ""
    @Published private(set) var isDemo = false
    @Published private(set) var isConnected = false
    /// No band ever connected and no demo: show the connect hint.
    @Published private(set) var needsConnect = false
    /// The latest decoded STATUS (for a details page: estimate range, vitals, contact, battery).
    @Published private(set) var status: StatusFrame?
    /// Her Day today: status line («At the market since 10:52») + timeline (HERDAY_SPEC §6).
    @Published private(set) var herDay: HerDayDisplay?
    /// Band 0.9.9 ALL_CLEAR in the last 2 h with no warning after it: the quiet «Back to normal 15:20 · 42 min».
    @Published private(set) var backToNormal: String?

    let model: AppModel
    private var bag: AnyCancellable?

    init(model: AppModel = .shared) {
        self.model = model
        refresh()
        bag = model.objectWillChange.debounce(for: .milliseconds(30), scheduler: DispatchQueue.main).sink { [weak self] _ in self?.refresh() }
    }

    func connect() { model.link.connect() }
    func startDemo() { model.startDemo() }

    func refresh() {
        let m = model, L = m.L
        let d = m.current
        let vs = AppModel.viewState(d)
        let fmt: (Date) -> String = { $0.formatted(.dateTime.hour(.twoDigits(amPM: .omitted)).minute(.twoDigits).locale(m.lang.locale)) }
        let offline = !m.isDemo && m.phase != .connected && (d != nil || m.lastSyncAt != nil)
        var h: HeroState
        if offline {
            let sync = m.lastSyncAt.map { L.lastSync(fmt($0)) } ?? ""
            h = HeroState(stateKey: "OFFLINE", title: L.noConnection,
                          subtitle: d.map { _ in L.lastKnown(L.state(vs).0, m.liveLastAt.map(fmt) ?? "—") } ?? "",
                          reason: nil, symbol: Theme.symbol("OFFLINE"), tone: .offline, urgent: false, isOffline: true,
                          updatedText: sync, lastSyncAt: m.lastSyncAt, simulated: false)
        } else {
            var upd = ""
            if m.isDemo { upd = L.sim + (m.currentAt.map { " · " + fmt($0) } ?? "") }
            else if let at = m.liveLastAt { upd = L.updated(Int(m.now.timeIntervalSince(at) / 60)) }
            else if m.phase == .connected { upd = L.connected }
            h = HeroState(stateKey: vs, title: L.state(vs).0, subtitle: L.state(vs).1, reason: m.reasonLine(d),
                          symbol: Theme.symbol(vs), tone: TodayViewModel.tone(vs), urgent: Theme.severity(vs) >= 4,
                          isOffline: false, updatedText: upd, lastSyncAt: m.lastSyncAt, simulated: m.isDemo)
        }
        let day = m.isDemo ? (m.currentAt ?? Date()) : Date()
        let entries = m.activeStore.entries(on: day)
        let items = Timeline.items(entries, planned: m.plannedNudges(on: day), day: Calendar.current.startOfDay(for: day),
                                   now: m.isDemo ? day : Date())
        let r = LogRows.rows(items, L: L, familyName: m.familyName, briefHour: m.herPlan.flatMap { NudgePlanner.briefHour($0) },
                             locale: m.lang.locale)
        let s = Timeline.summary(entries, day: day)

        if hero != h { hero = h }
        if rows != r { rows = r }
        if summary != s { summary = s; }
        let st = L.summaryLine(s)
        if summaryText != st { summaryText = st }
        if isDemo != m.isDemo { isDemo = m.isDemo }
        if isConnected != (m.phase == .connected) { isConnected = m.phase == .connected }
        let nc = !m.isDemo && m.phase != .connected && m.liveLast == nil && m.lastSyncAt == nil
        if needsConnect != nc { needsConnect = nc }
        if status != d { status = d }
        let btn = m.backToNormal(now: m.isDemo ? day : Date()).map { L.uiBackToNormal(fmt($0.at), $0.clear.minutes) }
        if backToNormal != btn { backToNormal = btn }
        let hd = m.herDayDisplay(0)
        if herDay != hd { herDay = hd }
    }

    static func tone(_ vs: String) -> Tone {
        switch vs {
        case "OK", "IMOK": return .ok
        case "DRINK": return .water
        case "COOL": return .heat
        case "DANGER", "CHECK", "HELP": return .danger
        case "OFFLINE", "NOT_WORN": return .offline
        default: return .neutral
        }
    }
}
