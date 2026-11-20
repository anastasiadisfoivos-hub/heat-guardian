// Family · TOMORROW (DESIGN.md §5): colour field of tomorrow's worst state, "Tomorrow" + one-line verdict,
// Swift Charts of her indoor °C by hour (28 / 30 °C soft bands, safe hours teal, planned nudges as markers),
// the planned nudges as a short list, and "On her band ✓ 21:04".

import SwiftUI
import UniformTypeIdentifiers

struct TomorrowView: View {
    @EnvironmentObject var m: AppModel
    @Environment(\.hgOverride) private var override
    @StateObject private var vm = TomorrowViewModel()
    @State private var importing = false

    var body: some View {
        let L = m.L
        let field = override.state?.field ?? worstField
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Palette.s24) {
                    header(L)
                    if vm.hasPlan {
                        TomorrowChart(vm: vm, L: L)
                            .frame(height: 230)
                            .padding(Palette.s16)
                            .hgCard()
                        if let hd = vm.herDay { HerDaySection(d: hd, L: L) }
                        nudgeList(L)
                        Text(bandLine(L))
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(Palette.textOnField)
                        if vm.isConstructedDemo || vm.isSimulation { SimBadge(text: L.sim) }
                    } else {
                        Text(L.uiNoPlan).font(.body).foregroundStyle(Palette.textOnField)
                    }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, Palette.s32)
            }
            .scrollIndicators(.hidden)
            .background { StateField(state: field) }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { importing = true } label: { Image(systemName: "doc.badge.plus") }
                        .accessibilityLabel(L.loadPlan)
                }
            }
            .fileImporter(isPresented: $importing, allowedContentTypes: [.json]) { res in
                if case .success(let url) = res {
                    let ok = url.startAccessingSecurityScopedResource()
                    defer { if ok { url.stopAccessingSecurityScopedResource() } }
                    if let data = try? Data(contentsOf: url) { vm.load(data) }
                }
            }
        }
    }

    /// Tomorrow's worst state: >= 32 °C indoors = danger, a heat day or >= 28 °C = heat, else ok.
    private var worstField: FieldState {
        let peak = vm.hours.map { $0.tIn }.max() ?? 0
        if peak >= 32 { return .danger }
        if vm.heatDay || peak >= TomorrowViewModel.warmC { return .heat }
        return .ok
    }

    @ViewBuilder
    private func header(_ L: Strings) -> some View {
        VStack(alignment: .leading, spacing: Palette.s8) {
            Text(L.tomorrow)
                .font(.largeTitle.weight(.bold))
                .foregroundStyle(Palette.textPrimary)
                .accessibilityAddTraits(.isHeader)
            Text(verdict(L))
                .font(.title3.weight(.semibold))
                .foregroundStyle(Palette.textPrimary)
            if !vm.dateTitle.isEmpty {
                Text(vm.dateTitle)
                    .font(.subheadline)
                    .foregroundStyle(Palette.textOnField)
            }
        }
        .padding(.top, Palette.s16)
    }

    /// "Heat wave day 2 · safe out 06–10"
    private func verdict(_ L: Strings) -> String {
        var a: String
        if vm.heatDay, let w = vm.waveDay, w >= 1 { a = L.waveDay(w) }
        else if vm.heatDay { a = L.heatDay }
        else if vm.nightHeat { a = L.hotNight }
        else { a = L.uiMildDay }
        if let r = vm.firstSafe { a += " · " + L.uiSafeOut(r) }
        else if vm.hasPlan { a += " · " + L.uiStayIn }
        return a
    }

    @ViewBuilder
    private func nudgeList(_ L: Strings) -> some View {
        if !vm.nudges.isEmpty {
            VStack(alignment: .leading, spacing: Palette.s4) {
                Text(L.uiPlanned)
                    .font(.footnote.weight(.semibold))
                    .tracking(0.6)
                    .foregroundStyle(Palette.textOnField)
                    .accessibilityAddTraits(.isHeader)
                ForEach(vm.nudges) { n in
                    HStack(spacing: Palette.s12) {
                        Text(n.timeText)
                            .font(.body.weight(.semibold).monospacedDigit())
                            .foregroundStyle(Palette.textPrimary)
                            .frame(width: 56, alignment: .leading)
                        Image(systemName: n.symbol)
                            .foregroundStyle(n.tone.color)
                            .frame(width: 24)
                            .accessibilityHidden(true)
                        Text(n.name)
                            .font(.body)
                            .foregroundStyle(Palette.textPrimary)
                        Spacer(minLength: 0)
                    }
                    .padding(.vertical, 6)
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }

    /// "On her band ✓ 21:04" / "Goes to the band by itself when it is near" / the last send result.
    private func bandLine(_ L: Strings) -> String {
        if vm.onBand, let at = vm.onBandAt {
            return L.uiOnBand(m.sexMale, at.formatted(.dateTime.hour(.twoDigits(amPM: .omitted)).minute(.twoDigits).locale(m.lang.locale)))
        }
        return vm.sendResult ?? L.uiSendsItself
    }
}

#Preview("Tomorrow") { FamilyPreview(state: nil, tab: .tomorrow) }
#Preview("Tomorrow · Greek") { FamilyPreview(state: nil, tab: .tomorrow, lang: .el) }
