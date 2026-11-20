// Family · HISTORY (DESIGN.md §5): a list of days, each a glass row — date, «4/5 ✓ · 3 water · 0 warnings», state
// dot; tap -> that day's full log in the same quiet row style as Today. Over the current state's colour field.

import SwiftUI

struct HistoryView: View {
    @EnvironmentObject var m: AppModel
    @Environment(\.hgOverride) private var override
    @StateObject private var vm = HistoryViewModel()
    @StateObject private var today = TodayViewModel()

    var body: some View {
        let L = m.L
        let field = TodayDisplay.make(vm: today, m: m, override: override).field
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: Palette.s12) {
                    NavigationLink { BodyInHeatView(field: field) } label: {
                        HStack(spacing: Palette.s16) {
                            Image(systemName: "waveform.path.ecg").font(.title3).foregroundStyle(Palette.textPrimary).accessibilityHidden(true)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(L.bhScreenTitle).font(.body.weight(.semibold)).foregroundStyle(Palette.textPrimary)
                                Text(L.bhScreenSub).font(.subheadline).foregroundStyle(Palette.textOnField)
                            }
                            Spacer(minLength: 0)
                            Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(Palette.textOnField)
                                .accessibilityHidden(true)
                        }
                        .padding(.horizontal, 20).padding(.vertical, 16)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .contentShape(Rectangle())
                        .hgCard()
                        .accessibilityElement(children: .combine)
                    }
                    .buttonStyle(.plain)
                    if let q = vm.quality { AlertQualityCard(q: q, L: L) }
                    if vm.days.isEmpty {
                        Text(vm.emptyText)
                            .font(.body)
                            .foregroundStyle(Palette.textOnField)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.top, Palette.s16)
                    }
                    ForEach(vm.days) { d in
                        NavigationLink {
                            DayDetailView(day: d, field: field)
                        } label: {
                            HistoryRow(day: d)
                        }
                        .buttonStyle(.plain)
                    }
                    if vm.isDemo { SimBadge(text: L.sim).padding(.top, Palette.s8) }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, Palette.s32)
            }
            .scrollIndicators(.hidden)
            .background { StateField(state: field) }
            .navigationTitle(L.tabHistory)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    NavigationLink { ReportView() } label: { Image(systemName: "doc.text") }
                        .accessibilityLabel(Text(L.rpTitle))
                }
            }
        }
    }
}

/// «Alert quality» (band 0.9.9, ECOSYSTEM_SPEC 5e): this week sent / held back / acknowledged / missed, the hold-back
/// reasons in plain words, and where the numbers come from. A quiet glass card, no colour alarm.
struct AlertQualityCard: View {
    var q: AlertQualityWeek
    var L: Strings

    var body: some View {
        VStack(alignment: .leading, spacing: Palette.s12) {
            HStack(alignment: .firstTextBaseline) {
                Text(L.aqTitle).font(.headline).foregroundStyle(Palette.textPrimary)
                Spacer(minLength: Palette.s8)
                Text(L.aqWeek).font(.subheadline).foregroundStyle(Palette.textOnField)
            }
            HStack(spacing: 0) {
                stat(q.sent, L.aqSent)
                stat(q.heldTotal, L.aqHeld)
                stat(q.acknowledged, L.aqAck)
                stat(q.missed, L.aqMissed)
            }
            if q.source == .none && q.sent == 0 {
                Text(L.aqNone).font(.subheadline).foregroundStyle(Palette.textOnField)
            }
            if !q.heldSorted.isEmpty {
                VStack(alignment: .leading, spacing: Palette.s4) {
                    Text(L.aqHeldWhy).font(.subheadline.weight(.semibold)).foregroundStyle(Palette.textPrimary)
                    ForEach(q.heldSorted, id: \.0) { r, n in
                        HStack(alignment: .firstTextBaseline, spacing: Palette.s8) {
                            Text("\(n)").font(.subheadline.weight(.semibold).monospacedDigit()).foregroundStyle(Palette.textPrimary)
                                .frame(minWidth: 24, alignment: .trailing)
                            Text(L.heldReason(r)).font(.subheadline).foregroundStyle(Palette.textOnField)
                        }
                        .accessibilityElement(children: .combine)
                    }
                }
            }
            if let a = q.avgAckSeconds { Text(L.aqAvgAck(a)).font(.footnote).foregroundStyle(Palette.textOnField) }
            Text(L.aqSource(q.source)).font(.footnote).foregroundStyle(Palette.textOnField)
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .hgCard()
    }

    private func stat(_ n: Int, _ label: String) -> some View {
        VStack(spacing: 2) {
            Text("\(n)")
                .font(.title2.weight(.bold).monospacedDigit())
                .foregroundStyle(Palette.textPrimary)
                .contentTransition(.numericText())
            Text(label)
                .font(.footnote)
                .foregroundStyle(Palette.textOnField)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
        }
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .combine)
    }
}

/// One day: date, summary, state dot — a glass row.
struct HistoryRow: View {
    var day: HistoryDay

    private var tone: Tone {
        if day.summary.helps > 0 { return .danger }
        if day.summary.warnings > 0 { return .heat }
        return .ok
    }

    var body: some View {
        HStack(spacing: Palette.s16) {
            Circle()
                .fill(tone.color)
                .frame(width: 12, height: 12)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(day.title)
                    .font(.body.weight(.semibold))
                    .foregroundStyle(Palette.textPrimary)
                Text(day.summaryText)
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(Palette.textOnField)
            }
            Spacer(minLength: 0)
            Image(systemName: "chevron.right")
                .font(.footnote.weight(.semibold))
                .foregroundStyle(Palette.textOnField)
                .accessibilityHidden(true)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())
        .hgCard()
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
    }
}

/// A past day's full log, same row style as Today.
struct DayDetailView: View {
    var day: HistoryDay
    var field: FieldState

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Palette.s4) {
                Text(day.summaryText)
                    .font(.subheadline.weight(.semibold).monospacedDigit())
                    .foregroundStyle(Palette.textOnField)
                    .padding(.bottom, Palette.s12)
                ForEach(day.rows) { LogRowLine(row: $0) }
            }
            .padding(.horizontal, 20)
            .padding(.bottom, Palette.s32)
        }
        .scrollIndicators(.hidden)
        .background { StateField(state: field) }
        .navigationTitle(day.title)
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview("History") { FamilyPreview(state: .ok, tab: .history) }
