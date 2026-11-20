// «Αύριο»: tomorrow only — her home's indoor curve by hour (plan moved to her home class), the 28 / 30 °C bands,
// safe hours, the planned nudges as markers, the advice and the band status (sent automatically on connect).

import Combine
import Foundation

struct HourPoint: Identifiable, Equatable {
    var hour: Int
    var tIn: Double              // her home, °C (plan.t_in moved to her class)
    var tInPlan: Double          // as in plan.json
    var tOut: Double?
    var rhIn: Double
    var safe: Bool
    var slot: Plan.Slot
    var id: Int { hour }
}

struct NudgeMarker: Identifiable, Equatable {
    var id: String
    var minute: Int
    var hourValue: Double        // minute / 60, for a chart x position
    var timeText: String
    var nudge: NudgeID
    var name: String
    var bandText: String         // the band's words
    var symbol: String
    var tone: Tone
    var tInAtTime: Double?       // y position on the indoor curve
}

final class TomorrowViewModel: ObservableObject {
    static let warmC = 28.0, hotC = 30.0

    @Published private(set) var hasPlan = false
    @Published private(set) var dateTitle = ""
    @Published private(set) var hours: [HourPoint] = []
    @Published private(set) var yDomain: ClosedRange<Double> = 20...40
    @Published private(set) var safeHours: [ClosedRange<Int>] = []     // [start, end) as start...end-1
    @Published private(set) var safeText = ""
    @Published private(set) var nudges: [NudgeMarker] = []
    @Published private(set) var advice: [String] = []                  // in the chosen language
    @Published private(set) var adviceBand: [String] = []              // the band's Greek lines
    @Published private(set) var heatDay = false
    @Published private(set) var nightHeat = false
    @Published private(set) var waveDay: Int?
    @Published private(set) var homeClass: String?                     // the class the curve is for
    @Published private(set) var planHomeClass: String?                 // the class in plan.json
    @Published private(set) var adjustedToHerHome = false
    @Published private(set) var isConstructedDemo = false
    @Published private(set) var isSimulation = false
    @Published private(set) var sourceText = ""
    @Published private(set) var onBand = false                         // this plan was written to the live band
    @Published private(set) var onBandAt: Date?
    @Published private(set) var sendResult: String?
    @Published private(set) var firstSafe: String?                     // "06:00–10:00", nil = no safe hours
    /// Her Day timeline for tomorrow (HERDAY_SPEC §6).
    @Published private(set) var herDay: HerDayDisplay?

    let model: AppModel
    private var bag: AnyCancellable?

    init(model: AppModel = .shared) {
        self.model = model
        refresh()
        bag = model.objectWillChange.debounce(for: .milliseconds(30), scheduler: DispatchQueue.main).sink { [weak self] _ in self?.refresh() }
    }

    func send() { model.sendPlan() }

    /// A plan.json picked in the file importer.
    func load(_ data: Data) {
        do {
            let p = try Plan.load(from: data)
            _ = try Frames.forecastChunks(p)
            model.plan = p
            model.lastSendResult = nil
            model.autoSendPlan()
        } catch { model.lastSendResult = "plan.json: \(error)" }
    }

    func refresh() {
        let m = model, L = m.L
        let hd = m.herDayDisplay(1)
        if herDay != hd { herDay = hd }
        // The demo shows its constructed tomorrow (Athens heat-wave day 2, SIMULATION) so chart and Her Day agree.
        let demoTomorrow = m.isDemo ? m.herDayPlan(1, now: m.herDayNow) : nil
        guard let orig = demoTomorrow ?? m.plan, let p = demoTomorrow ?? m.herPlan, p.hours.count == 24 else { hasPlan = false; return }
        hasPlan = true
        let parts = p.date.split(separator: "-").compactMap { Int($0) }
        if parts.count == 3, let d = Calendar.current.date(from: DateComponents(year: parts[0], month: parts[1], day: parts[2])) {
            dateTitle = d.formatted(.dateTime.weekday(.wide).day().month(.wide).locale(m.lang.locale)).capitalized(with: m.lang.locale)
        } else { dateTitle = p.date }
        let hs = p.hours.enumerated().map { i, h in
            HourPoint(hour: h.h, tIn: h.tIn, tInPlan: orig.hours[i].tIn, tOut: h.tOut, rhIn: h.rhIn, safe: h.safe, slot: p.slot(h))
        }
        if hours != hs { hours = hs }
        let ys = hs.map { $0.tIn } + hs.compactMap { $0.tOut } + [TomorrowViewModel.warmC, TomorrowViewModel.hotC]
        yDomain = ((ys.min() ?? 20).rounded(.down) - 1)...((ys.max() ?? 40).rounded(.up) + 1)
        var ranges: [ClosedRange<Int>] = []
        var s: Int? = nil
        for i in 0...24 {
            let safe = i < 24 && p.hours[i].safe
            if safe && s == nil { s = i }
            if !safe, let st = s { ranges.append(st...(i - 1)); s = nil }
        }
        safeHours = ranges
        let rr = p.safeRanges()
        firstSafe = rr.first
        safeText = rr.isEmpty ? L.noneSafe : rr.joined(separator: ", ")
        let fmt: (Int) -> String = { Routine.hhmm($0) }
        let bh = NudgePlanner.briefHour(p)
        let nm = m.plannedNudges(on: Date()).map { n in   // owner decision Nov 19: no generic nudges (empty)
            NudgeMarker(id: n.id, minute: n.minute, hourValue: Double(n.minute) / 60, timeText: fmt(n.minute), nudge: n.nudge,
                        name: L.nudgeName(n.nudge), bandText: L.nudgeBandText(n.nudge, briefHour: bh),
                        symbol: LogRows.symbol(n.nudge), tone: LogRows.tone(n.nudge), tInAtTime: p.hours[min(23, n.hour)].tIn)
        }
        if nudges != nm { nudges = nm }
        adviceBand = p.adviceGr ?? []
        advice = m.lang == .el ? adviceBand : adviceBand.map { AdviceEN.translate($0) }
        heatDay = p.heatDay; nightHeat = p.nightHeat; waveDay = p.waveDay
        homeClass = p.homeClass; planHomeClass = orig.homeClass
        adjustedToHerHome = p.homeClass != orig.homeClass
        isConstructedDemo = p.isConstructedDemo; isSimulation = p.isSimulation
        sourceText = L.source(p.source)
        let key = m.planKey(p)
        onBand = m.planOnBand?.key == key
        onBandAt = onBand ? m.planOnBand?.at : nil
        sendResult = m.lastSendResult ?? ((!m.isDemo && p.isConstructedDemo) ? L.notSentDemoPlan : nil)
    }
}
