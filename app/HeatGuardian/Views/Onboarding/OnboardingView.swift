// First launch (DESIGN.md §1): one question — «I wear the band» (Elder mode) / «I'm family» (Family mode).
// The screen starts in the phone's language (Greek phone -> Greek) with a small toggle, so it never mixes the two
// languages; the choice then sets the mode's default language (Family English, Elder Greek).

import SwiftUI

struct OnboardingView: View {
    @EnvironmentObject var m: AppModel
    var onChoose: (AppMode) -> Void
    @State private var lang: Lang = Locale.current.language.languageCode?.identifier == "el" ? .el : .en

    var body: some View {
        let L = Strings(lang: lang)
        ZStack {
            StateField(state: .ok)
            VStack(spacing: Palette.s24) {
                Picker(L.language, selection: $lang) {
                    ForEach(Lang.allCases) { Text($0.native).tag($0) }
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 260)
                Spacer(minLength: 0)
                GlassOrb(symbol: "shield.checkmark", tint: FieldState.ok.accent, size: 120)
                Text("Heat Guardian")
                    .font(.largeTitle.weight(.bold))
                    .foregroundStyle(Palette.textPrimary)
                Text(L.uiWhoUses)
                    .font(.title2.weight(.semibold))
                    .foregroundStyle(Palette.textPrimary)
                    .multilineTextAlignment(.center)
                    .accessibilityAddTraits(.isHeader)
                Spacer(minLength: 0)
                GlassEffectContainer(spacing: Palette.s16) {
                    VStack(spacing: Palette.s16) {
                        RoleButton(title: L.uiIWear, note: L.uiIWearNote, symbol: "applewatch") { onChoose(.elder) }
                        RoleButton(title: L.uiImFamily, note: L.uiImFamilyNote, symbol: "person.2") { onChoose(.family) }
                    }
                }
                Text(L.uiChangeLater)
                    .font(.footnote)
                    .foregroundStyle(Palette.textOnField)
            }
            .padding(Palette.s24)
        }
        .environment(\.locale, lang.locale)
    }
}

private struct RoleButton: View {
    var title: String
    var note: String
    var symbol: String
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: Palette.s16) {
                Image(systemName: symbol)
                    .font(.title)
                    .frame(width: 40)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 4) {
                    Text(title).font(.title3.weight(.bold))
                    Text(note).font(.subheadline).foregroundStyle(Palette.textOnField)
                }
                Spacer(minLength: 0)
            }
            .foregroundStyle(Palette.textPrimary)
            .padding(.horizontal, Palette.s8)
            .frame(maxWidth: .infinity, minHeight: 72, alignment: .leading)
        }
        .buttonStyle(.glass)
    }
}

#Preview("Onboarding") {
    OnboardingView(onChoose: { _ in }).environmentObject(AppModel.shared)
}
