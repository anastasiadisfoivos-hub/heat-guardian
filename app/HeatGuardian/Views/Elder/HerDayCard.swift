// Elder · the Her Day suggestion (HERDAY_SPEC.md §5, DESIGN.md §6): in the evening tomorrow's, in the morning
// today's — one large Greek card «Αύριο: αγορά πριν τις 09:30» with «Εντάξει». When the band has that brief open
// (nudge 7 EVENING_BRIEF / 1 BRIEF), «Εντάξει» closes it there too: CMD 0x1A ELDER_ACTION action 2 + nudge id.

import SwiftUI

struct ElderHerDay: Equatable {
    var key: String              // what «Εντάξει» dismisses ("e2026-07-15" / "m2026-07-14")
    var text: String
    var note: String
    var nudge: NudgeID           // .eveningBrief or .brief
    var nudgeOpen: Bool          // that nudge is on the band's screen now

    /// The card for `now`, or nil. Items: what the band holds (PLAN_ITEM events) when it has them, else this
    /// phone's own engine result (her phone holds her routine).
    static func make(m: AppModel, now: Date, dismissed: Set<String>) -> ElderHerDay? {
        let L = m.L
        let cal = Calendar.current
        let mod = now.minuteOfDay
        let evening = mod >= AppModel.eveningSendMinute
        let morning = mod >= min(m.routine.wakeOrDefault, 8 * 60) && mod < 12 * 60
        guard evening || morning else { return nil }
        let offset = evening ? 1 : 0
        guard let date = cal.date(byAdding: .day, value: offset, to: now) else { return nil }
        let entries = m.herEntries
        var items = BandHerDay.planItems(entries, for: date).items
        if items.isEmpty { items = m.herDay(offset, now: now)?.items ?? [] }
        if !evening {
            // the morning card stays only while her first suggestion is still ahead
            guard let first = items.filter({ $0.kind == .outingShift }).min(by: { ($0.usual ?? 9999) < ($1.usual ?? 9999) }),
                  let s = first.suggested, first.direction == .after || mod <= s else { return nil }
        }
        guard let text = L.hdCard(items, tomorrow: evening) else { return nil }
        let key = (evening ? "e" : "m") + AppModel.dayString(date)
        guard !dismissed.contains(key) else { return nil }
        let nudge: NudgeID = evening ? .eveningBrief : .brief
        let day = cal.startOfDay(for: now)
        let open = Timeline.items(m.activeStore.entries(on: day), day: day, now: now).contains { it in
            if case .nudge(let n, .shown) = it.kind { return n == nudge && now.timeIntervalSince(it.at) < 2 * 3600 }
            return false
        }
        let hasShift = items.contains { $0.kind == .outingShift }
        return ElderHerDay(key: key, text: text, note: hasShift ? L.hdCardNote : "", nudge: nudge, nudgeOpen: open)
    }
}

struct HerDayCard: View {
    var card: ElderHerDay
    var okTitle: String
    var onOK: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Palette.s16) {
            HStack(alignment: .top, spacing: Palette.s16) {
                Image(systemName: card.nudge == .eveningBrief ? "moon.stars.fill" : "sun.horizon.fill")
                    .font(.title)
                    .foregroundStyle(Palette.primary)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: Palette.s8) {
                    Text(card.text)
                        .font(.system(size: 30, weight: .bold))
                        .foregroundStyle(Palette.textPrimary)
                        .fixedSize(horizontal: false, vertical: true)
                    if !card.note.isEmpty {
                        Text(card.note)
                            .font(.system(size: 22))
                            .foregroundStyle(Palette.textPrimary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            .accessibilityElement(children: .combine)
            BigGlassButton(title: okTitle, systemImage: "checkmark", prominent: true, action: onOK)
        }
        .padding(Palette.s24)
        .frame(maxWidth: .infinity, alignment: .leading)
        .hgCard()
    }
}
