// Family · TODAY (DESIGN.md §5, Figma "Today — v2 minimal glass" + "Today — state tones").
// Colour field = state. Toolbar: «● Maria» (live dot = connected) and the call button (system glass items).
// Centre: orb, state word, ONE subtitle line, prevention dots. One "Next" card. "TODAY" + quiet log rows.

import SwiftUI

struct TodayView: View {
    @EnvironmentObject var m: AppModel
    @Environment(\.hgOverride) private var override
    @StateObject private var vm = TodayViewModel()
    @Binding var tab: AppTab

    var body: some View {
        let d = TodayDisplay.make(vm: vm, m: m, override: override)
        NavigationStack {
            ScrollView {
                VStack(spacing: Palette.s32) {
                    TodayHero(d: d, L: m.L)
                    nextSection(d)
                    if let hd = vm.herDay, hd.status != nil || !hd.rows.isEmpty {
                        HerDaySection(d: hd, L: m.L, showStatus: true)
                    }
                    TodayLog(rows: d.rows, L: m.L, onSeeAll: { tab = .history })
                    if vm.isDemo { SimBadge(text: m.L.sim) }
                }
                .padding(.horizontal, 20)
                .padding(.top, Palette.s8)
                .padding(.bottom, Palette.s32)
            }
            .scrollIndicators(.hidden)
            .background { StateField(state: d.field) }
            .toolbar { toolbarContent(d) }
            .toolbarTitleDisplayMode(.inline)
        }
        .sensoryFeedback(.warning, trigger: d.field) { old, new in new.severity > old.severity && new.severity >= 3 }
    }

    @ViewBuilder
    private func nextSection(_ d: TodayDisplay) -> some View {
        let L = m.L
        if d.isHelp {
            VStack(spacing: Palette.s12) {
                HelpNextCard(title: L.uiCallNow(m.sexMale), subtitle: L.uiCallSub(m.sexMale), action: L.uiCallAction) {
                    m.familyCallNow()
                }
                Button { m.familyComing() } label: {
                    Label(L.actComing, systemImage: "figure.walk")
                        .font(.body.weight(.semibold))
                        .frame(maxWidth: .infinity, minHeight: 44)
                }
                .buttonStyle(.glass)
            }
        } else if let n = d.next {
            NextCard(item: n)
        }
    }

    @ToolbarContentBuilder
    private func toolbarContent(_ d: TodayDisplay) -> some ToolbarContent {
        let L = m.L
        let name = m.wearerName.isEmpty ? L.uiWearer : m.wearerName
        let live = vm.isConnected || vm.isDemo
        ToolbarItem(placement: .topBarLeading) {
            HStack(spacing: 6) {
                Circle()
                    .fill(live ? Palette.ok : Palette.offline)
                    .frame(width: 8, height: 8)
                Text(name)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Palette.textPrimary)
            }
            .padding(.horizontal, 6)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(name + ", " + (live ? L.uiLinkUp : L.uiLinkDown))
        }
        ToolbarItem(placement: .topBarTrailing) {
            if let url = m.wearerTelURL {
                Link(destination: url) { Image(systemName: "phone") }
                    .accessibilityLabel(L.uiCallA11y(name))
            } else {
                Button { tab = .settings } label: { Image(systemName: "phone") }
                    .accessibilityLabel(L.uiCallA11y(name))
                    .accessibilityHint(L.uiAddNumber)
            }
        }
    }
}

/// Orb + state word (44 pt bold) + one subtitle line + prevention dots.
struct TodayHero: View {
    var d: TodayDisplay
    var L: Strings

    var body: some View {
        VStack(spacing: Palette.s16) {
            GlassOrb(symbol: d.symbol, tint: d.field.accent, size: 132, pulse: d.field.urgent)
                .padding(.bottom, Palette.s8)
            Text(d.title)
                .font(.system(size: 44, weight: .bold))
                .foregroundStyle(d.field.wordColor)
                .multilineTextAlignment(.center)
                .minimumScaleFactor(0.6)
                .lineLimit(2)
                .contentTransition(.opacity)
                .accessibilityAddTraits(.isHeader)
            Text(d.subtitle)
                .font(.body)
                .foregroundStyle(Palette.textOnField)
                .multilineTextAlignment(.center)
                .contentTransition(.numericText())
            PreventionDots(done: d.done, total: d.total, label: L.uiPrevention,
                           a11y: L.uiPreventionA11y(d.done, d.total))
                .padding(.top, Palette.s4)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, Palette.s24)
        .animation(.easeInOut(duration: 0.8), value: d.field)
    }
}

/// "TODAY" caption + 3–6 quiet rows + "See all".
struct TodayLog: View {
    var rows: [LogRow]
    var L: Strings
    var onSeeAll: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Palette.s4) {
            HStack {
                Text(L.uiTodayCaption)
                    .font(.footnote.weight(.semibold))
                    .tracking(0.6)
                    .foregroundStyle(Palette.textOnField)
                    .accessibilityAddTraits(.isHeader)
                Spacer()
                Button(L.uiSeeAll, action: onSeeAll)
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(Palette.primary)
                    .frame(minHeight: 44)
            }
            if rows.isEmpty {
                Text(L.uiNothingYet)
                    .font(.body)
                    .foregroundStyle(Palette.textOnField)
                    .padding(.vertical, 6)
            }
            ForEach(rows) { LogRowLine(row: $0) }
        }
    }
}

#Preview("Today · ok") { FamilyPreview(state: .ok, tab: .today) }
#Preview("Today · heat") { FamilyPreview(state: .heat, tab: .today) }
#Preview("Today · water") { FamilyPreview(state: .water, tab: .today) }
#Preview("Today · danger") { FamilyPreview(state: .danger, tab: .today) }
#Preview("Today · help") { FamilyPreview(state: .help, tab: .today) }
#Preview("Today · offline") { FamilyPreview(state: .offline, tab: .today) }
#Preview("Today · help · dark") { FamilyPreview(state: .help, tab: .today).preferredColorScheme(.dark) }
