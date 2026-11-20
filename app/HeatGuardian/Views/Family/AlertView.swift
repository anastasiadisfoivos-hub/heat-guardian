// Full-screen ALERT (DESIGN.md §5): help colour field, big orb with the warning symbol, «Maria pressed HELP · 14:52»,
// «Call her» (.glassProminent, tel:) and «I'm coming» (.glass), small «Seen». Sends FAMILY_ACK / FAMILY_MSG through the
// backend exactly as before: ackCall = FAMILY_ACK 2 + FAMILY_MSG 1 + dialler, ackComing = MSG 2, ackSeen = MSG 3.
// Chime + haptics are started by AppModel.raiseAlert.

import SwiftUI

struct AlertView: View {
    @EnvironmentObject var m: AppModel
    @Environment(\.dismiss) private var dismiss
    let a: AlertInfo
    /// Screenshot / preview sample (-HGAlert): buttons only close the screen.
    var sample = false

    var body: some View {
        let L = m.L
        let field: FieldState = a.kind == .danger ? .danger : .help
        let at = a.at.formatted(.dateTime.hour(.twoDigits(amPM: .omitted)).minute(.twoDigits).locale(m.lang.locale))
        ZStack {
            StateField(state: field)
            VStack(spacing: Palette.s24) {
                topRow(L)
                Spacer(minLength: Palette.s16)
                GlassOrb(symbol: a.kind == .help ? "sos" : "exclamationmark.triangle", tint: field.accent, size: 168, pulse: true)
                VStack(spacing: Palette.s12) {
                    Text(m.alertTitle(a))
                        .font(.system(size: 40, weight: .bold))
                        .foregroundStyle(field.wordColor)
                        .multilineTextAlignment(.center)
                        .minimumScaleFactor(0.6)
                        .accessibilityAddTraits(.isHeader)
                    Text(L.uiAlertLine(a.kind, name: m.wearerName, at: at, male: m.sexMale))
                        .font(.title3.weight(.semibold))
                        .foregroundStyle(Palette.textPrimary)
                        .multilineTextAlignment(.center)
                }
                Spacer(minLength: Palette.s16)
                actions(L)
            }
            .padding(.horizontal, Palette.s24)
            .padding(.vertical, Palette.s16)
        }
        .accessibilityAction(named: Text(L.uiCallHer(m.sexMale))) { call() }
        .accessibilityAction(named: Text(L.actComing)) { coming() }
    }

    private func topRow(_ L: Strings) -> some View {
        HStack {
            if a.source == .demo || sample { SimBadge(text: L.sim) }
            Spacer()
            if !m.muted && !sample {
                Button { m.muteAlert() } label: { Image(systemName: "speaker.slash") }
                    .buttonStyle(.glass)
                    .buttonBorderShape(.circle)
                    .controlSize(.large)
                    .accessibilityLabel(L.uiMuteA11y)
            }
        }
        .frame(minHeight: 44)
    }

    private func actions(_ L: Strings) -> some View {
        GlassEffectContainer(spacing: Palette.s12) {
            VStack(spacing: Palette.s12) {
                Button(action: call) {
                    Label(L.uiCallHer(m.sexMale), systemImage: "phone.fill")
                        .font(.title3.weight(.bold))
                        .frame(maxWidth: .infinity, minHeight: 56)
                }
                .buttonStyle(.glassProminent)
                .tint(Palette.helpSolid)

                Button(action: coming) {
                    Label(L.actComing, systemImage: "figure.walk")
                        .font(.title3.weight(.semibold))
                        .foregroundStyle(Palette.textPrimary)
                        .frame(maxWidth: .infinity, minHeight: 56)
                }
                .buttonStyle(.glass)

                Button(L.actSeen, action: seen)
                    .font(.body.weight(.semibold))
                    .foregroundStyle(Palette.textPrimary)
                    .frame(minHeight: 44)
            }
        }
    }

    private func call() { if sample { dismiss() } else { m.ackCall() } }
    private func coming() { if sample { dismiss() } else { m.ackComing() } }
    private func seen() { if sample { dismiss() } else { m.ackSeen() } }
}

#Preview("Alert · help") {
    AlertView(a: SampleData.alert(.help), sample: true).environmentObject(AppModel.shared)
}
#Preview("Alert · danger") {
    AlertView(a: SampleData.alert(.danger), sample: true).environmentObject(AppModel.shared)
}
#Preview("Alert · no answer") {
    AlertView(a: SampleData.alert(.family), sample: true).environmentObject(AppModel.shared)
}
