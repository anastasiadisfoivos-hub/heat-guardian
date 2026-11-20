// HISTORY + REPORT (owner decision Nov 19, job 3): her days, newest first; each day = the alerts, what she did and
// whether it worked, and which SMS went to whom (DayStory). The toolbar opens the doctor's report (PDF made on the
// phone, shared by email to the family or the share sheet; an SMS cannot carry a PDF).

import SwiftUI

struct TowerHistoryView: View {
    @EnvironmentObject var m: AppModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        let L = m.L
        _ = m.logVersion; _ = m.towerVersion
        let cal = Calendar.current
        var dayset = Set(m.activeStore.days)
        for it in m.tower.outbox.items where it.simulated == m.isDemo { dayset.insert(cal.startOfDay(for: it.createdAt)) }
        dayset.insert(cal.startOfDay(for: m.isDemo ? (m.currentAt ?? Date()) : Date()))
        let days: [Date] = Array(dayset.sorted(by: >).prefix(14))
        return List {
            Section {
                NavigationLink { ReportView() } label: {
                    Label(L.rpShortTitle, systemImage: "doc.richtext").font(.title3.weight(.semibold)).frame(minHeight: 52)
                }
                Text(L.twNoPDFbySMS).font(.callout).foregroundStyle(.secondary)
            }
            ForEach(days, id: \.self) { d in
                let rows = DayStory.rows(m.activeStore.entries, outbox: m.tower.outbox.items.filter { $0.simulated == m.isDemo },
                                         lang: m.lang, day: d)
                Section {
                    if rows.isEmpty {
                        Text(L.twNoHistory).font(.body).foregroundStyle(.secondary)
                    } else {
                        ForEach(rows) { r in StoryRowView(r: r, L: L) }
                    }
                } header: {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(d, format: .dateTime.weekday(.wide).day().month(.wide)).font(.headline)
                        Text(L.twDaySummary(DayStory.summary(rows))).font(.subheadline)
                    }
                    .textCase(nil)
                }
            }
        }
        .navigationTitle(L.twHistory)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) { Button(L.done) { dismiss() } }
        }
    }
}

struct StoryRowView: View {
    var r: StoryRow
    var L: Strings

    private var tint: Color {
        switch r.tone {
        case .calm: return Palette.primary
        case .watch: return Palette.water
        case .warn: return Palette.heat
        case .urgent: return Palette.danger
        case .good: return Palette.ok
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: Palette.s12) {
            Image(systemName: r.symbol).font(.title3).foregroundStyle(tint).frame(width: 30).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 4) {
                HStack(alignment: .firstTextBaseline) {
                    Text(r.title).font(.body.weight(.semibold))
                    Spacer(minLength: 4)
                    Text(L.twTime(r.at)).font(.subheadline.monospacedDigit()).foregroundStyle(.secondary)
                }
                if let d = r.detail { Text(d).font(.subheadline).foregroundStyle(.secondary) }
                if let o = r.outcome {
                    Text(L.twOutcome(o)).font(.footnote.weight(.semibold))
                        .padding(.horizontal, 8).padding(.vertical, 3)
                        .background(outcomeColour(o).opacity(0.16), in: Capsule())
                        .foregroundStyle(outcomeColour(o))
                }
                if !r.sms.isEmpty {
                    Label(L.twSMSTo + " " + r.sms.joined(separator: ", "), systemImage: "message")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                if r.simulated { SimBadge(text: L.sim) }
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
    }

    private func outcomeColour(_ o: StoryRow.Outcome) -> Color {
        switch o {
        case .worked: return Color(hex: 0x0E7C74)
        case .notWorked, .noResponse: return Color.dynamic(0xA83A0A, 0xFF9B73)
        case .open: return Palette.primary
        }
    }
}
