// The day log (ECOSYSTEM_SPEC §5): band EVENTS + what the family sent, merged without duplicates, persisted as
// one JSON file (Application Support/events.json, 60 days). Band entries are keyed "b<boot>-<seq>", so a SYNC_EVENTS
// replay or a re-notify of the same event never adds a second row.

import Foundation

enum Origin: String, Codable { case band, you }

enum LogKind: String, Codable {
    // from the band (BandEvent.Kind)
    case nudgeShown, nudgeDone, nudgeMissed, imOK, help, helpCancel, familyMsgShown, warnShown
    case visit, planItem             // Her Day (types 9 / 10): not log rows; read by HerDayDisplay
    case alertHeld, score            // alert quality (types 11 / 13): not log rows; read by AlertQuality
    case allClear                    // type 12: «Back to normal» row (quiet, never an alarm)
    // band 0.9.17 (types 14-21, LadderEvents.swift): the action ladder + power / haptic; the Tower + History read them
    case powerOff, battCritical, hapticLost
    case battLow                     // band 0.9.18 (type 23): «Χαμηλή μπαταρία» (History only)
    case ldRemind, ldDone, ldWorked, ldEscalated, ldNote
    // from this phone ("you")
    case familyMsgSent, familyAckSent
}

struct LogEntry: Codable, Identifiable, Equatable {
    var id: String
    var at: Date
    var kind: LogKind
    var arg: Int
    var origin: Origin
    var simulated: Bool = false
    /// false = the band's clock was not set; `at` is when the phone received it.
    var clockKnown: Bool = true
    /// EVENTS bytes 11..18 for types 9 VISIT / 10 PLAN_ITEM (nil for the others; optional so older files decode).
    var ext: [UInt8]? = nil
    /// The band's boot count (EVENTS bytes 3-4); nil for phone entries and files written before 0.9.9 support.
    var boot: Int? = nil
    var nudge: NudgeID? { [.nudgeShown, .nudgeDone, .nudgeMissed].contains(kind) ? NudgeID(rawValue: arg) : nil }
    /// WARN_SHOWN arg = guardian HG_ST_* code (HG.guardianStateNames; fw 0.9.7 ECOSYSTEM_SPEC 5c).
    var warnState: String? {
        guard kind == .warnShown else { return nil }
        return arg >= 0 && arg < HG.guardianStateNames.count ? HG.guardianStateNames[arg] : "DRINK"
    }

    /// Kinds whose EVENTS bytes 11..18 are kept (their fields are decoded on demand).
    static let extKinds: Set<LogKind> = [.visit, .planItem, .alertHeld, .allClear, .score,
                                         .powerOff, .battCritical, .battLow, .hapticLost, .ldRemind, .ldDone, .ldWorked, .ldEscalated, .ldNote]

    static func fromBand(_ e: BandEvent, receivedAt: Date, simulated: Bool = false) -> LogEntry? {
        // A type this app does not know (a newer band): ignored and logged, never a row (ECOSYSTEM_SPEC: must ignore).
        guard let k = e.kind else { BandEventDiagnostics.shared.unknownType(e.kindRaw); return nil }
        // A 0.9.17 type with an arg this app does not know: ignored too (decode logs it).
        if LadderEvent.ladderTypes.contains(e.kindRaw), e.ladder == nil { return nil }
        let kind: LogKind
        switch k {
        case .nudgeShown: kind = .nudgeShown
        case .nudgeDone: kind = .nudgeDone
        case .nudgeMissed: kind = .nudgeMissed
        case .imOK: kind = .imOK
        case .help: kind = .help
        case .helpCancel: kind = .helpCancel
        case .familyMsgShown: kind = .familyMsgShown
        case .warnShown: kind = .warnShown
        case .visit: kind = .visit
        case .planItem: kind = .planItem
        case .alertHeld: kind = .alertHeld
        case .allClear: kind = .allClear
        case .score: kind = .score
        case .powerOff: kind = .powerOff
        case .battCritical: kind = .battCritical
        case .hapticLost: kind = .hapticLost
        case .ldRemind: kind = .ldRemind
        case .ldDone: kind = .ldDone
        case .ldWorked: kind = .ldWorked
        case .ldEscalated: kind = .ldEscalated
        case .ldNote: kind = .ldNote
        case .battLow: kind = .battLow
        }
        let at = e.hasClock ? Date(timeIntervalSince1970: TimeInterval(e.unix)) : receivedAt
        return LogEntry(id: (simulated ? "sim-" : "") + "b\(e.boot)-\(e.seq)", at: at, kind: kind, arg: e.arg,
                        origin: .band, simulated: simulated, clockKnown: e.hasClock,
                        ext: extKinds.contains(kind) ? e.ext : nil, boot: e.boot)
    }

    /// The band event again (for the Her Day / alert-quality decoders).
    private var bandEvent: BandEvent {
        let k: BandEvent.Kind
        switch kind {
        case .visit: k = .visit
        case .alertHeld: k = .alertHeld
        case .allClear: k = .allClear
        case .score: k = .score
        case .powerOff: k = .powerOff
        case .battCritical: k = .battCritical
        case .hapticLost: k = .hapticLost
        case .ldRemind: k = .ldRemind
        case .ldDone: k = .ldDone
        case .ldWorked: k = .ldWorked
        case .ldEscalated: k = .ldEscalated
        case .ldNote: k = .ldNote
        case .battLow: k = .battLow
        default: k = .planItem
        }
        return BandEvent(seq: 0, boot: boot ?? 0, unix: UInt32(max(0, at.timeIntervalSince1970)), kindRaw: k.rawValue, arg: arg, ext: ext ?? [])
    }
    /// EVENTS type 11 fields (nil for other entries).
    var alertHeld: AlertHeld? { kind == .alertHeld ? bandEvent.alertHeld : nil }
    /// EVENTS type 12 fields (nil for other entries).
    var allClear: AllClear? { kind == .allClear ? bandEvent.allClear : nil }
    /// EVENTS type 13 fields (nil for other entries).
    var scorePage: ScorePage? { kind == .score ? bandEvent.scorePage : nil }
    /// EVENTS type 9 fields (nil for other entries).
    var visit: VisitEvent? { kind == .visit ? bandEvent.visit : nil }
    /// EVENTS type 10 fields (nil for other entries).
    var planItem: DayPlanItem? { kind == .planItem ? bandEvent.planItem : nil }
    /// EVENTS types 14-21 (band 0.9.17) and 23 (0.9.18), nil for other entries.
    var ladder: LadderEvent? { LadderEvent.ladderTypes.contains(bandKindRaw ?? 0) ? bandEvent.ladder : nil }
    private var bandKindRaw: Int? {
        switch kind {
        case .powerOff: return 14
        case .battCritical: return 15
        case .hapticLost: return 16
        case .ldRemind: return 17
        case .ldDone: return 18
        case .ldWorked: return 19
        case .ldEscalated: return 20
        case .ldNote: return 21
        case .battLow: return 23
        default: return nil
        }
    }
}

/// One row of a day's timeline. A nudge's shown / done / missed events collapse into one row.
struct TimelineItem: Identifiable, Equatable {
    enum NudgeStatus: Equatable { case upcoming, shown, done(Date), missed(Date) }
    enum Kind: Equatable {
        case nudge(NudgeID, NudgeStatus)
        case warning(String)             // STATUS state name
        case imOK, help, helpCancel
        case familyMsgShown(Int)         // the band showed family message 1/2/3
        case familyMsgSent(Int)          // you sent family message 1/2/3
        case familyAck(Int)              // you sent FAMILY_ACK type
        case allClear(minutes: Int, familyCalled: Bool)   // the band's «Πάλι όλα καλά» (0.9.9)
    }
    var id: String
    var at: Date
    var kind: Kind
    var origin: Origin
    var simulated: Bool
    var clockKnown: Bool
}

struct DaySummary: Identifiable, Equatable {
    var day: Date
    var nudgesShown: Int
    var nudgesDone: Int
    var water: Int          // N4 done
    var warnings: Int
    var helps: Int
    var id: Date { day }
}

enum Timeline {
    /// Entries of one day -> rows (newest last). `planned` adds hollow "upcoming" rows for nudges not seen yet.
    static func items(_ entries: [LogEntry], planned: [PlannedNudge] = [], day: Date, now: Date = Date()) -> [TimelineItem] {
        var out: [TimelineItem] = []
        var openNudge: [NudgeID: Int] = [:]      // nudge -> index in out of its open "shown" row
        for e in entries.sorted(by: { $0.at < $1.at }) {
            switch e.kind {
            case .nudgeShown:
                guard let n = e.nudge else { continue }
                openNudge[n] = out.count
                out.append(TimelineItem(id: e.id, at: e.at, kind: .nudge(n, .shown), origin: .band, simulated: e.simulated, clockKnown: e.clockKnown))
            case .nudgeDone, .nudgeMissed:
                guard let n = e.nudge else { continue }
                let st: TimelineItem.NudgeStatus = e.kind == .nudgeDone ? .done(e.at) : .missed(e.at)
                if let i = openNudge[n] { out[i].kind = .nudge(n, st); openNudge[n] = nil }
                else { out.append(TimelineItem(id: e.id, at: e.at, kind: .nudge(n, st), origin: .band, simulated: e.simulated, clockKnown: e.clockKnown)) }
            case .imOK: out.append(row(e, .imOK))
            case .help: out.append(row(e, .help))
            case .helpCancel: out.append(row(e, .helpCancel))
            case .familyMsgShown: out.append(row(e, .familyMsgShown(e.arg)))
            case .warnShown: out.append(row(e, .warning(e.warnState ?? "DRINK")))
            case .familyMsgSent: out.append(row(e, .familyMsgSent(e.arg)))
            case .familyAckSent: out.append(row(e, .familyAck(e.arg)))
            case .allClear:
                let c = e.allClear
                out.append(row(e, .allClear(minutes: c?.minutes ?? 0, familyCalled: c?.familyCalled ?? false)))
            case .visit, .planItem, .alertHeld, .score: continue   // Her Day section / Alert quality card, not log rows
            case .powerOff, .battCritical, .battLow, .hapticLost, .ldRemind, .ldDone, .ldWorked, .ldEscalated, .ldNote:
                continue   // band 0.9.17: the Tower history (DayStory) shows these, the family log rows do not
            }
        }
        // planned nudges: shown as upcoming when no event of that nudge happened within 45 min of its time
        for p in planned {
            let t = day.at(minute: p.minute)
            guard t > now.addingTimeInterval(-15 * 60) else { continue }
            let seen = out.contains { item in
                if case .nudge(let n, _) = item.kind { return n == p.nudge && abs(item.at.timeIntervalSince(t)) < 45 * 60 }
                return false
            }
            if !seen { out.append(TimelineItem(id: "plan-" + p.id, at: t, kind: .nudge(p.nudge, .upcoming), origin: .band, simulated: false, clockKnown: true)) }
        }
        return out.sorted { $0.at < $1.at }
    }

    private static func row(_ e: LogEntry, _ k: TimelineItem.Kind) -> TimelineItem {
        TimelineItem(id: e.id, at: e.at, kind: k, origin: e.origin, simulated: e.simulated, clockKnown: e.clockKnown)
    }

    static func summary(_ entries: [LogEntry], day: Date) -> DaySummary {
        DaySummary(day: day,
                   nudgesShown: entries.filter { $0.kind == .nudgeShown }.count,
                   nudgesDone: entries.filter { $0.kind == .nudgeDone }.count,
                   water: entries.filter { $0.kind == .nudgeDone && $0.nudge == .water }.count,
                   warnings: entries.filter { $0.kind == .warnShown }.count,
                   helps: entries.filter { $0.kind == .help }.count)
    }
}

/// Persistent log + the SYNC_EVENTS cursor.
final class EventStore {
    private(set) var entries: [LogEntry] = []
    private var ids = Set<String>()
    /// The last band event seen: SYNC_EVENTS(since seq, boot) on the next connection.
    private(set) var cursorBoot: Int?
    private(set) var cursorSeq: Int = 0
    static let keepDays = 60

    private let url: URL
    private let persist: Bool

    init(fileName: String? = "events.json") {
        if let f = fileName {
            url = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent(f)
            persist = true
            load()
        } else {
            url = URL(fileURLWithPath: "/dev/null")
            persist = false
        }
    }

    private struct File: Codable { var entries: [LogEntry]; var cursorBoot: Int?; var cursorSeq: Int }

    private func load() {
        guard let d = try? Data(contentsOf: url), let f = try? JSONDecoder().decode(File.self, from: d) else { return }
        let cut = Date().addingTimeInterval(-Double(EventStore.keepDays) * 86400)
        entries = f.entries.filter { $0.at >= cut }.sorted { $0.at < $1.at }
        ids = Set(entries.map { $0.id })
        cursorBoot = f.cursorBoot
        cursorSeq = f.cursorSeq
    }

    func save() {
        guard persist else { return }
        try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        if let d = try? JSONEncoder().encode(File(entries: entries, cursorBoot: cursorBoot, cursorSeq: cursorSeq)) {
            try? d.write(to: url, options: .atomic)
        }
    }

    /// Adds an entry unless its id is known. Returns true when it was new.
    @discardableResult
    func add(_ e: LogEntry) -> Bool {
        guard !ids.contains(e.id) else { return false }
        ids.insert(e.id)
        if let last = entries.last, last.at > e.at {
            let i = entries.firstIndex { $0.at > e.at } ?? entries.count
            entries.insert(e, at: i)
        } else {
            entries.append(e)
        }
        return true
    }

    /// A band event: advances the cursor (u16 seq wraps; "newer" = 1..32767 ahead) and adds it if new.
    @discardableResult
    func addBand(_ ev: BandEvent, receivedAt: Date) -> LogEntry? {
        // GAUGE (type 22, band 0.9.18) is a LIVE frame (seq 0): never a row, and it must never move the cursor — not
        // even on a new boot count, where it would reset the cursor to seq 0 (ECOSYSTEM_SPEC 5f).
        if ev.kindRaw == BandGauge.eventType { return nil }
        if cursorBoot != ev.boot {
            cursorBoot = ev.boot
            cursorSeq = ev.seq
        } else {
            let ahead = (ev.seq - cursorSeq + 65536) % 65536
            if ahead > 0 && ahead < 32768 { cursorSeq = ev.seq }
        }
        guard let e = LogEntry.fromBand(ev, receivedAt: receivedAt), add(e) else { return nil }
        return e
    }

    func entries(on day: Date) -> [LogEntry] {
        let d0 = Calendar.current.startOfDay(for: day)
        let d1 = d0.addingTimeInterval(86400 + 3600)   // DST-safe upper bound, then compare by day
        return entries.filter { $0.at >= d0 && $0.at < d1 && Calendar.current.isDate($0.at, inSameDayAs: d0) }
    }

    /// Days with at least one log row, newest first (VISIT / PLAN_ITEM / ALERT_HELD / SCORE events alone do not make a day).
    var days: [Date] {
        let cal = Calendar.current
        var seen = Set<Date>()
        var out: [Date] = []
        for e in entries.reversed() where ![.visit, .planItem, .alertHeld, .score].contains(e.kind) {
            let d = cal.startOfDay(for: e.at)
            if seen.insert(d).inserted { out.append(d) }
        }
        return out
    }

    func clear() {
        entries = []; ids = []; cursorBoot = nil; cursorSeq = 0
    }
}
