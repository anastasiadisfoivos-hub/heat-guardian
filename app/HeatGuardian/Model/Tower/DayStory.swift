// HISTORY on her phone (owner decision Nov 19, job 3): one day as a short story of alerts, what she did, and whether
// it worked — built from the band's EVENTS (0.9.17 ladder, HELP, older WARN_SHOWN / ALL_CLEAR) and the Tower outbox
// (which SMS went to whom). Pure Foundation, tested on Linux (TowerTests).

import Foundation

struct StoryRow: Identifiable, Equatable {
    enum Tone: Equatable { case calm, watch, warn, urgent, good }
    enum Outcome: Equatable { case worked, notWorked, noResponse, open }
    var id: String
    var at: Date
    var symbol: String          // SF Symbol
    var title: String
    var detail: String?
    var tone: Tone
    var outcome: Outcome?
    var simulated: Bool
    /// SMS sent for this row (contact names), with the dry-run flag.
    var sms: [String] = []
}

struct DayStorySummary: Equatable {
    var reminders = 0
    var worked = 0
    var notWorked = 0
    var escalations = 0
    var helps = 0
    var smsSent = 0
}

enum DayStory {
    static func rows(_ entries: [LogEntry], outbox: [OutboxItem], lang: Lang, day: Date,
                     calendar: Calendar = .current) -> [StoryRow] {
        let L = Strings(lang: lang)
        let dayEntries = entries.filter { calendar.isDate($0.at, inSameDayAs: day) }.sorted { $0.at < $1.at }
        var out: [StoryRow] = []
        var openReminder: [LadderStep: Int] = [:]           // step -> index of its reminder row
        for e in dayEntries {
            func row(_ sym: String, _ t: String, _ d: String? = nil, _ tone: StoryRow.Tone) -> StoryRow {
                StoryRow(id: e.id, at: e.at, symbol: sym, title: t, detail: d, tone: tone, outcome: nil, simulated: e.simulated || e.isBandReplay)   // band `replay`: SIM badge
            }
            if let lv = e.ladder {
                switch lv {
                case .reminder(let s, let rep, _):
                    if rep, let i = openReminder[s] {
                        out[i].detail = L.twRepeated(append: out[i].detail)
                        continue
                    }
                    var r = row(s == .water ? "drop.fill" : "house.fill", L.twReminder(s), nil, .watch)
                    r.outcome = .open
                    openReminder[s] = out.count
                    out.append(r)
                case .done(let s, let mins, _):
                    if let i = openReminder[s] { out[i].detail = L.twDonePressed(e.at, minutes: mins) }
                    else { out.append(row("hand.tap.fill", L.twDonePressed(e.at, minutes: mins), nil, .calm)) }
                case .worked(let s, _, _):
                    if s != .escalation, let i = openReminder[s] {
                        out[i].outcome = .worked
                        out[i].detail = [out[i].detail, L.twWorkedAt(e.at)].compactMap { $0 }.joined(separator: " · ")
                        openReminder[s] = nil
                    } else {
                        out.append(row("checkmark.circle.fill", L.twSettled, nil, .good))
                    }
                case .note(.waterDidNotHelp, _, _, _):
                    if let i = openReminder[.water] {
                        out[i].outcome = .notWorked
                        out[i].detail = [out[i].detail, L.twNotWorked].compactMap { $0 }.joined(separator: " · ")
                        openReminder[.water] = nil
                    } else { out.append(row("drop.triangle.fill", L.twNotWorked, nil, .warn)) }
                case .note(.noResponse, let s, _, _):
                    let st = s ?? .water
                    if let i = openReminder[st] {
                        out[i].outcome = .noResponse
                        out[i].detail = [out[i].detail, L.twNoResponse].compactMap { $0 }.joined(separator: " · ")
                        openReminder[st] = nil
                    } else { out.append(row("questionmark.circle.fill", L.twNoResponse, nil, .warn)) }
                case .note(.responsive, _, _, _):
                    out.append(row("hand.raised.fill", L.twResponsive, nil, .calm))
                case .escalated(let why, _, _):
                    if why == .stillHeating, let i = openReminder[.coolerPlace] {
                        out[i].outcome = .notWorked; openReminder[.coolerPlace] = nil
                    }
                    out.append(row("exclamationmark.triangle.fill", L.twEscalated(why), nil, .urgent))
                case .powerOff(let byWearer):
                    out.append(row("power", L.twPowerOff(byWearer), nil, .calm))
                case .batteryCritical, .powerOffBattery:
                    // 0.9.18 sends BATT_CRITICAL then POWER_OFF 3 a second later: one «battery ended» row
                    if let last = out.last, last.symbol == "battery.0percent", e.at.timeIntervalSince(last.at) < 5 * 60 { continue }
                    out.append(row("battery.0percent", L.twBattery, nil, .warn))
                case .batteryLow:
                    out.append(row("battery.25percent", L.twBatteryLow, nil, .watch))
                case .hapticLost:
                    out.append(row("iphone.radiowaves.left.and.right.slash", L.twHaptic, nil, .warn))
                }
                continue
            }
            switch e.kind {
            case .help: out.append(row("sos", L.twHelp(e.arg == 2), nil, .urgent))
            case .helpCancel: out.append(row("xmark.circle.fill", L.twHelpCancel, nil, .calm))
            case .warnShown:
                // bands before 0.9.17: the warning itself (no ladder events then)
                let st = e.warnState ?? "DRINK"
                guard ["DRINK", "COOL", "CHECK", "DANGER"].contains(st) else { continue }
                out.append(row(st == "DRINK" ? "drop.fill" : (st == "COOL" ? "house.fill" : "exclamationmark.triangle.fill"),
                               L.state(st).0, nil, st == "DRINK" || st == "COOL" ? .watch : .urgent))
            case .imOK: out.append(row("hand.raised.fill", L.twResponsive, nil, .calm))
            case .allClear:
                let c = e.allClear
                out.append(row("checkmark.seal.fill", L.twAllClear(minutes: c?.minutes ?? 0), nil, .good))
            default: continue
            }
        }
        // SMS: attach each outbox item to the row it was sent for (by its dedupe key, the latest such row up to 60 min
        // earlier), else it gets its own row
        func matches(_ r: StoryRow, _ key: String) -> Bool {
            switch key {
            case "help": return r.symbol == "sos"
            case "help-cancel": return r.symbol == "xmark.circle.fill"
            case "escalation": return r.tone == .urgent && r.symbol == "exclamationmark.triangle.fill"
            case "note-water": return r.outcome == .notWorked || r.symbol == "drop.triangle.fill"
            case "note-noresponse": return r.outcome == .noResponse || r.symbol == "questionmark.circle.fill"
            case "responsive": return r.symbol == "hand.raised.fill"
            case "settled": return r.symbol == "checkmark.circle.fill"
            case "battery": return r.symbol == "battery.0percent"
            default: return false
            }
        }
        let sms = outbox.filter { calendar.isDate($0.createdAt, inSameDayAs: day) && ($0.status == .sent || $0.status == .queued || $0.status == .sending) }
        for s in sms {
            let label = s.contactName + (s.dryRun ? " (" + L.twDryShort + ")" : "")
            if let i = out.lastIndex(where: { r in
                r.simulated == s.simulated && r.at <= s.createdAt.addingTimeInterval(60) && s.createdAt.timeIntervalSince(r.at) < 3600
                    && matches(r, s.dedupeKey) }) {
                if !out[i].sms.contains(label) { out[i].sms.append(label) }
            } else if s.dedupeKey.hasPrefix("test") {
                out.append(StoryRow(id: "sms-" + s.id, at: s.createdAt, symbol: "message.fill", title: L.twTestSMS, detail: nil,
                                    tone: .calm, outcome: nil, simulated: s.simulated, sms: [label]))
            } else {
                out.append(StoryRow(id: "sms-" + s.id, at: s.createdAt, symbol: "message.fill", title: L.twSMSOnly, detail: s.body,
                                    tone: .calm, outcome: nil, simulated: s.simulated, sms: [label]))
            }
        }
        return out.sorted { $0.at < $1.at }
    }

    static func summary(_ rows: [StoryRow]) -> DayStorySummary {
        var s = DayStorySummary()
        for r in rows {
            if r.outcome != nil { s.reminders += 1 }
            if r.outcome == .worked { s.worked += 1 }
            if r.outcome == .notWorked { s.notWorked += 1 }
            if r.symbol == "exclamationmark.triangle.fill" && r.tone == .urgent { s.escalations += 1 }
            if r.symbol == "sos" { s.helps += 1 }
            s.smsSent += r.sms.count
        }
        return s
    }
}
