// What the Elder screen shows right now (DESIGN.md §6), from the same band data as the family app plus the
// wearer's own just-pressed actions (shown at once, before the band's EVENTS confirm them).

import Foundation

/// The wearer's own presses on this phone, kept until the band confirms (or a few minutes pass).
struct ElderLocal: Equatable {
    var helpAt: Date?                    // HELP sent
    var helpCancelledAt: Date?
    var imOKAt: Date?
    var doneNudgeIDs: Set<String> = []   // log row ids closed with «Έγινε ✓»
    var dismissedMsgIDs: Set<String> = []
    var linkFailed = false               // the last HELP could not reach a live band
    var herDayDismissed: Set<String> = []  // Her Day cards closed with «Εντάξει»
}

struct OpenNudge: Equatable {
    var rowID: String
    var nudge: NudgeID
    var title: String                    // the band's own words («Ώρα για ένα ποτήρι νερό»)
}

struct FamilyMessage: Equatable {
    var rowID: String
    var text: String                     // «Μαρία: σας καλεί»
}

struct ElderSnapshot: Equatable {
    var field: FieldState
    var title: String
    var guidance: String
    var symbol: String
    var openNudge: OpenNudge?
    var checkOpen: Bool
    var helpActive: Bool
    var message: FamilyMessage?

    static func make(m: AppModel, local: ElderLocal, override o: UIOverride, now: Date) -> ElderSnapshot {
        let L = m.L
        let d = m.current
        let offline = !m.isDemo && m.phase != .connected && (d != nil || m.lastSyncAt != nil)
        var vs = o.state?.viewState ?? (offline ? "OFFLINE" : AppModel.viewState(d))

        // her own presses win until the band says otherwise
        let helpLocal = local.helpAt.map { at in
            (m.isDemo || now.timeIntervalSince(at) < 180) && (local.helpCancelledAt ?? .distantPast) < at
        } ?? false
        let cancelled = local.helpCancelledAt.map { now.timeIntervalSince($0) < 120 } ?? false
        if o.state == nil {
            if helpLocal { vs = "HELP" } else if vs == "HELP" && cancelled { vs = "OK" }
        }
        let imOKRecent = local.imOKAt.map { now.timeIntervalSince($0) < 120 } ?? false
        let checkOpen = vs == "CHECK" && !imOKRecent
        if vs == "CHECK" && imOKRecent { vs = "IMOK" }

        let hot = (d?.tairC ?? 0) >= TomorrowViewModel.warmC || TodayDisplay.todayIsHeatDay(m)
        let field = o.state?.field ?? FieldState.from(viewState: vs, hotDay: hot)
        var title = FieldState.ownTitle(vs) ? L.state(vs).0 : field.title(L)
        var guidance = L.uiGuidance(field)
        if checkOpen { title = L.uiAreYouOK; guidance = L.t("Πατήστε «Είμαι καλά».", "Tap \"I'm OK\".") }
        if vs == "NOT_WORN" { guidance = L.off }

        // the open nudge (shown on the band, not yet done / missed), from today's log
        let day = Calendar.current.startOfDay(for: now)
        let items = Timeline.items(m.activeStore.entries(on: day), day: day, now: now)
        var open: OpenNudge?
        if let it = items.last(where: { item in
            if case .nudge(_, .shown) = item.kind { return now.timeIntervalSince(item.at) < 3600 && !local.doneNudgeIDs.contains(item.id) }
            return false
        }), case .nudge(let n, _) = it.kind {
            open = OpenNudge(rowID: it.id, nudge: n, title: L.el ? L.nudgeBandText(n, briefHour: nil) : L.nudgeName(n))
        }
        if let s = o.state, s == .water, !local.doneNudgeIDs.contains("sample") {
            open = OpenNudge(rowID: "sample", nudge: .water, title: L.el ? L.nudgeBandText(.water, briefHour: nil) : L.nudgeName(.water))
        }
        if open != nil && field != .help && !checkOpen { guidance = open!.title }
        // band 0.9.9 «Πάλι όλα καλά»: a quiet line for an hour after the episode ended (no sound, no button)
        if open == nil && !checkOpen && !field.urgent && o.state == nil, let b = m.backToNormal(now: now),
           now.timeIntervalSince(b.at) < 3600 {
            guidance = L.uiElderBackToNormal(b.at.formatted(.dateTime.hour(.twoDigits(amPM: .omitted)).minute(.twoDigits).locale(m.lang.locale)))
        }

        // the latest family message (FAMILY_MSG_SHOWN in the last 30 min)
        var msg: FamilyMessage?
        if let it = items.last(where: { item in
            if case .familyMsgShown = item.kind { return now.timeIntervalSince(item.at) < 1800 && !local.dismissedMsgIDs.contains(item.id) }
            return false
        }), case .familyMsgShown(let k) = it.kind {
            msg = FamilyMessage(rowID: it.id, text: L.uiFamilyMsg(k, name: m.familyName))
        }
        if let k = o.familyMsg, !local.dismissedMsgIDs.contains("sample-msg") {
            msg = FamilyMessage(rowID: "sample-msg", text: L.uiFamilyMsg(k, name: m.familyName.isEmpty ? L.t("Μαρία", "Maria") : m.familyName))
        }

        return ElderSnapshot(field: field, title: title, guidance: guidance,
                             symbol: checkOpen ? "questionmark.circle" : (FieldState.ownTitle(vs) ? Theme.symbol(vs) : field.symbol),
                             openNudge: field == .help ? nil : open, checkOpen: checkOpen, helpActive: field == .help,
                             message: msg)
    }
}
