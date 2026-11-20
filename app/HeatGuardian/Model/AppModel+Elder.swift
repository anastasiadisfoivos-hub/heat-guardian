// Elder-mode actions (DESIGN.md §6) and the Family Today HELP shortcuts.
// Elder buttons go to the band as CMD 0x1A ELDER_ACTION — the same path as the band's own button: the band raises
// HELP / closes the nudge / answers the CHECK and emits its EVENTS frame, so the family phone sees it.
// Demo mode never writes to a band: the frame is logged (SIMULATION) and the event the band would emit is added
// to the demo log, so both screens follow.

import Foundation
import UIKit

extension AppModel {
    /// Sends ELDER_ACTION. Returns true when it was written to a connected live band (false = demo or no link).
    @discardableResult
    func sendElderAction(_ action: HG.ElderAction, nudge: NudgeID? = nil) -> Bool {
        let f = Frames.cmdElderAction(action, nudge: nudge?.rawValue ?? 0)
        let label: String
        switch action {
        case .help: label = "ELDER_ACTION 1 HELP"
        case .nudgeDone: label = "ELDER_ACTION 2 NUDGE_DONE \(nudge?.rawValue ?? 0)"
        case .helpCancel: label = "ELDER_ACTION 3 HELP_CANCEL"
        case .imOK: label = "ELDER_ACTION 4 IM_OK"
        }
        let live = !isDemo && link.isConnected
        sendCommand(f, label: label, source: source)
        if isDemo { addDemoElderEvent(action, nudge: nudge) }
        // THE TOWER: a HELP on her phone is an SMS from her phone at once (the band's EVENTS echo dedupes with it)
        if action == .help || action == .helpCancel { towerPhoneHelp(cancel: action == .helpCancel) }
        return live
    }

    private func addDemoElderEvent(_ action: HG.ElderAction, nudge: NudgeID?) {
        let at = currentAt ?? Date()
        let kind: LogKind
        var arg = 2                                       // EVENTS arg 2 = pressed on the phone (fw 5c)
        switch action {
        case .help: kind = .help
        case .helpCancel: kind = .helpCancel
        case .imOK: kind = .imOK
        case .nudgeDone:
            kind = .nudgeDone
            arg = nudge?.rawValue ?? 0
            // the replay would otherwise close this nudge again (done / missed) a few minutes later
            let day = Calendar.current.startOfDay(for: at)
            if let n = nudge, let p = plannedNudges(on: day).last(where: { $0.nudge == n && $0.minute <= at.minuteOfDay }) {
                demoNudgesFired.insert("c" + p.id)
            }
        }
        demoStore.add(LogEntry(id: "sim-elder-" + UUID().uuidString, at: at, kind: kind, arg: arg, origin: .band,
                               simulated: true))
        logChanged()
    }

    /// Today HELP card «Call her now»: FAMILY_ACK 2 (when the band has an alarm id) + FAMILY_MSG 1, then the dialler.
    func familyCallNow() {
        familyReply(msg: 1, alarmId: current?.alarmId16, source: source)
        if alert != nil { dismissAlert() }
        if !isDemo, let url = wearerTelURL { UIApplication.shared.open(url) }
    }

    /// Today HELP «I'm coming»: FAMILY_MSG 2.
    func familyComing() {
        familyReply(msg: 2, alarmId: nil, source: source)
        if alert != nil { dismissAlert() }
    }

    /// tel: link to the wearer's saved number (nil = none saved).
    var wearerTelURL: URL? {
        let digits = wearerPhone.filter { "+0123456789".contains($0) }
        return digits.isEmpty ? nil : URL(string: "tel://" + digits)
    }
}
