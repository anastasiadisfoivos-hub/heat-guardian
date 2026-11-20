// «Ιστορικό»: past days' logs, newest first, each with its one-line summary («4/5 ✓ · 3 νερό · 0 προειδοποιήσεις»).

import Combine
import Foundation

struct HistoryDay: Identifiable, Equatable {
    var day: Date
    var title: String            // «Τρίτη 17 Νοεμβρίου»
    var summary: DaySummary
    var summaryText: String
    var rows: [LogRow]
    var id: Date { day }
}

final class HistoryViewModel: ObservableObject {
    @Published private(set) var days: [HistoryDay] = []
    @Published private(set) var isDemo = false
    @Published private(set) var emptyText = ""
    /// This week's alert quality (band 0.9.9 scorecard / log): the card at the top.
    @Published private(set) var quality: AlertQualityWeek?

    let model: AppModel
    private var bag: AnyCancellable?
    private var lastVersion = -1
    private var lastLang: Lang?
    private var lastDay: Date?

    init(model: AppModel = .shared) {
        self.model = model
        refresh()
        bag = model.objectWillChange.debounce(for: .milliseconds(30), scheduler: DispatchQueue.main).sink { [weak self] _ in self?.refresh() }
    }

    func refresh() {
        let m = model, L = m.L
        // Only the log and the language change this screen: skip the per-minute STATUS updates.
        let today = Calendar.current.startOfDay(for: Date())
        guard m.logVersion != lastVersion || m.lang != lastLang || isDemo != m.isDemo || lastDay != today else { return }
        lastVersion = m.logVersion; lastLang = m.lang; lastDay = today
        isDemo = m.isDemo
        emptyText = L.noHistory
        let st = m.activeStore
        quality = m.alertQualityWeek()
        days = st.days.filter { m.isDemo || $0 < today }.map { (d: Date) -> HistoryDay in
            let e = st.entries(on: d)
            let s = Timeline.summary(e, day: d)
            let rows = LogRows.rows(Timeline.items(e, day: d), L: L, familyName: m.familyName, briefHour: nil, locale: m.lang.locale,
                                   knowBrief: false)
            return HistoryDay(day: d, title: d.formatted(.dateTime.weekday(.wide).day().month(.wide).locale(m.lang.locale)),
                              summary: s, summaryText: L.summaryLine(s), rows: rows)
        }
    }
}
