// What the Family Today screen shows, worked out from TodayViewModel (+ a screenshot override): the field tone,
// the state word, ONE subtitle line, the prevention dots, the one "Next" card and the quiet log rows.

import Foundation

struct TodayDisplay: Equatable {
    var field: FieldState
    var title: String
    var subtitle: String
    var symbol: String
    var next: NextItem?
    var done: Int
    var total: Int
    var rows: [LogRow]
    var isHelp: Bool { field == .help }

    static func make(vm: TodayViewModel, m: AppModel, override o: UIOverride) -> TodayDisplay {
        let L = m.L
        let male = m.sexMale
        let h = vm.hero
        let fmt: (Date) -> String = { $0.formatted(.dateTime.hour(.twoDigits(amPM: .omitted)).minute(.twoDigits).locale(m.lang.locale)) }
        let now = m.isDemo ? (m.currentAt ?? Date()) : Date()

        let vs = o.state?.viewState ?? (h.isOffline ? "OFFLINE" : h.stateKey)
        let d = vm.status
        let hotDay = (d?.tairC ?? 0) >= TomorrowViewModel.warmC || todayIsHeatDay(m)
        let field = o.state?.field ?? FieldState.from(viewState: vs, hotDay: hotDay)
        let title = FieldState.ownTitle(vs) ? L.state(vs).0 : field.title(L, male: male)

        // ONE subtitle line: offline -> last seen; danger/help -> reason line or body estimate; else room · pulse.
        var subtitle: String
        if o.state != nil {
            subtitle = sampleSubtitle(o.state!, L, now: fmt(now))
        } else if h.isOffline {
            let seen = m.liveLastAt ?? m.lastSyncAt
            let last = m.liveLast.map { L.state(AppModel.viewState($0)).0 } ?? "—"
            subtitle = seen.map { L.uiLastSeen(fmt($0), last) } ?? L.uiConnectHint
        } else if vm.needsConnect {
            subtitle = L.uiConnectHint
        } else if !field.urgent, let b = vm.backToNormal {
            subtitle = b                                   // 0.9.9 all-clear: a quiet status, never an alarm
        } else if field.urgent, let r = h.reason {
            subtitle = r
        } else if field.urgent, let d = d, d.hasEstimate {
            subtitle = L.reasonBody + " · " + L.uiBodyEst(d.coreC.f1(m.lang))
        } else {
            subtitle = vitalsLine(d, L) ?? h.subtitle
        }
        if subtitle.isEmpty { subtitle = h.subtitle }

        // prevention dots: done / max(shown, planned), 5 when nothing is known yet
        let planned = m.plannedNudges(on: Calendar.current.startOfDay(for: now)).count
        var total = max(vm.summary.nudgesShown, planned)
        var done = vm.summary.nudgesDone
        if total == 0 { total = 5 }
        if o.state != nil { done = 3; total = 5 }
        done = min(done, total)

        return TodayDisplay(field: field, title: title, subtitle: subtitle,
                            symbol: FieldState.ownTitle(vs) ? Theme.symbol(vs) : field.symbol,
                            next: nextItem(field: field, vs: vs, vm: vm, m: m, now: now, fmt: fmt),
                            done: done, total: total, rows: Array(recentRows(vm.rows, now: now)))
    }

    /// "Home 26° · pulse 72" (no line when the band sent neither).
    static func vitalsLine(_ d: StatusFrame?, _ L: Strings) -> String? {
        guard let d = d else { return nil }
        var parts: [String] = []
        if let t = d.tairC { parts.append(L.uiHome(Int(t.rounded()))) }
        if d.hrBpm > 0 { parts.append(L.uiPulse(d.hrBpm)) }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }

    static func todayIsHeatDay(_ m: AppModel) -> Bool {
        guard let p = m.herPlan else { return false }
        return p.heatDay && (m.isDemo || p.date == AppModel.dayString(Date()))
    }

    /// The day's last 6 rows that already happened (planned nudges are in the Next card instead).
    static func recentRows(_ rows: [LogRow], now: Date) -> ArraySlice<LogRow> {
        let past = rows.filter { !$0.isUpcoming }.reversed()
        return Array(past).prefix(6)
    }

    static func nextItem(field: FieldState, vs: String, vm: TodayViewModel, m: AppModel, now: Date,
                         fmt: (Date) -> String) -> NextItem? {
        let L = m.L, male = m.sexMale
        switch field {
        case .help:
            return nil                                        // the solid «Call her now» card
        case .offline where vs == "OFFLINE":
            return NextItem(symbol: "iphone.gen3", title: L.uiMoveCloser, origin: L.uiBandAlone,
                            time: (m.lastSyncAt).map(fmt) ?? "", tone: .offline)
        default: break
        }
        if vs == "CHECK" || (field == .danger && vm.status?.familyPending == true) {
            return NextItem(symbol: "questionmark.circle", title: L.uiAskedOK(male), origin: L.uiFromBand,
                            time: fmt(now), tone: .danger)
        }
        if vs == "DRINK" {
            return NextItem(symbol: "drop", title: L.uiReminded(male), origin: L.uiFromBand,
                            time: (m.currentAt).map(fmt) ?? fmt(now), tone: .water)
        }
        if let r = vm.rows.first(where: { $0.isUpcoming && $0.at >= now.addingTimeInterval(-15 * 60) }) {
            return NextItem(symbol: r.symbol, title: r.title, origin: L.uiNextOnBand(male), time: r.timeText, tone: r.tone)
        }
        return nil
    }

    /// Screenshot override lines (DESIGN.md / Figma state tones).
    static func sampleSubtitle(_ s: OverrideState, _ L: Strings, now: String) -> String {
        switch s {
        case .ok: return L.uiHome(26) + " · " + L.uiPulse(72)
        case .heat: return L.uiHome(29) + " · " + L.uiPulse(76)
        case .water: return L.uiHome(31) + " · " + L.reasonBody
        case .danger, .check: return L.reasonBody + " · " + L.uiBodyEst(L.el ? "38,4" : "38.4")
        case .help: return L.t("Πάτησε ΒΟΗΘΕΙΑ · ", "Pressed HELP · ") + now
        case .offline: return L.uiLastSeen("13:05", L.state("OK").0)
        }
    }
}
