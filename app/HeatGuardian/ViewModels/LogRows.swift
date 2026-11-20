// UI-ready rows for the day log (Today and History share them). Semantic tone + SF Symbol per row; the views
// map Tone to colours (spec §1 rule 5: green OK, blue water, orange heat, red danger, grey offline).

import Foundation

/// Semantic accent of a row / hero. The view layer owns the actual colours.
enum Tone: String, Equatable { case ok, water, heat, danger, offline, family, neutral }

struct LogRow: Identifiable, Equatable {
    var id: String
    var at: Date
    var timeText: String         // "14:05"
    var title: String            // Greek (or English) text of the row
    var detail: String?          // nudge status, the band's quoted words, …
    var symbol: String           // SF Symbol
    var tone: Tone
    var originText: String       // «βραχιόλι» / «εσείς»
    var origin: Origin
    var isUpcoming: Bool         // a planned nudge that has not happened yet (hollow row)
    var simulated: Bool
    var clockKnown: Bool
}

enum LogRows {
    static func symbol(_ n: NudgeID) -> String {
        switch n {
        case .brief: return "sun.horizon.fill"
        case .lastCool: return "figure.walk"
        case .shutters: return "blinds.horizontal.closed"
        case .water: return "drop.fill"
        case .air: return "window.casement"
        case .ac: return "air.conditioner.horizontal.fill"
        case .eveningBrief: return "moon.stars.fill"
        case .leaveHot: return "sun.max.trianglebadge.exclamationmark"
        }
    }
    static func tone(_ n: NudgeID) -> Tone { n == .water ? .water : .heat }

    static func warnTone(_ state: String) -> Tone {
        switch state {
        case "DRINK": return .water
        case "COOL": return .heat
        case "DANGER", "CHECK", "HELP": return .danger
        default: return .offline
        }
    }
    static func warnSymbol(_ state: String) -> String {
        switch state {
        case "DRINK": return "drop.fill"
        case "COOL": return "house.fill"
        case "CHECK": return "questionmark.circle.fill"
        case "HELP": return "sos"
        case "BATTERY": return "battery.25"
        case "NOT_WORN": return "hand.raised.slash"
        default: return "exclamationmark.triangle.fill"
        }
    }

    /// `knowBrief` false = the day's plan is not known (history): the brief row shows no quoted band text.
    static func rows(_ items: [TimelineItem], L: Strings, familyName: String, briefHour: Int?, locale: Locale,
                     knowBrief: Bool = true) -> [LogRow] {
        let fmt: (Date) -> String = { $0.formatted(.dateTime.hour(.twoDigits(amPM: .omitted)).minute(.twoDigits).locale(locale)) }
        return items.map { (it: TimelineItem) -> LogRow in
            var title = "", detail: String? = nil, sym = "circle", tn = Tone.neutral, upcoming = false
            switch it.kind {
            case .nudge(let n, let st):
                title = L.nudgeName(n)
                let quote = (n == .brief && !knowBrief) ? "" : "«\(L.nudgeBandText(n, briefHour: briefHour))» · "
                detail = quote + L.nudgeStatus(st, fmt)
                sym = symbolFor(n, st)
                switch st {
                case .done: tn = .ok
                case .missed: tn = .offline
                case .upcoming: tn = LogRows.tone(n); upcoming = true
                case .shown: tn = LogRows.tone(n)
                }
            case .warning(let s):
                title = L.warnLog(s); sym = warnSymbol(s); tn = warnTone(s)
                if s != "NOT_WORN" && s != "BATTERY" { detail = "«\(L.state(s).0)»" }
            case .imOK: title = L.logImOK; sym = "checkmark.circle.fill"; tn = .ok
            case .help: title = L.logHelp; sym = "sos"; tn = .danger
            case .helpCancel: title = L.logHelpCancel; sym = "xmark.circle"; tn = .ok
            case .familyMsgShown(let k): title = L.logFamilyMsgShown(k, name: familyName); sym = "bubble.left.fill"; tn = .family
            case .familyMsgSent(let k): title = L.logFamilyMsgSent(k); sym = k == 1 ? "phone.fill" : (k == 2 ? "figure.walk" : "checkmark.bubble.fill"); tn = .family
            case .familyAck(let k): title = L.logAck(k); sym = "phone.fill"; tn = .family
            case .allClear(let mins, let fam):
                title = L.logAllClear; sym = "checkmark.circle"; tn = .ok
                detail = L.logAllClearDetail(mins, familyCalled: fam)
            }
            return LogRow(id: it.id, at: it.at, timeText: fmt(it.at), title: title, detail: detail, symbol: sym, tone: tn,
                          originText: L.origin(it.origin) + (it.clockKnown ? "" : " · " + L.clockUnknown), origin: it.origin,
                          isUpcoming: upcoming, simulated: it.simulated, clockKnown: it.clockKnown)
        }
    }

    private static func symbolFor(_ n: NudgeID, _ st: TimelineItem.NudgeStatus) -> String {
        switch st {
        case .done: return "checkmark.circle.fill"
        case .missed: return "minus.circle"
        default: return symbol(n)
        }
    }
}
