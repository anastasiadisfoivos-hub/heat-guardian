// SETTINGS (DESIGN.md §5): the system Form (Liquid Glass comes with it). Family name (shown on her band), her
// profile, medicines, routine, home type (-> class A–D), notifications, connection, diagnostics + demo, language,
// the hidden mode switch, and About with one honest line on how alerts travel. Elder mode opens the same screen
// from a long press on the clock, for the family to set up.

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var m: AppModel
    @StateObject private var vm = SettingsViewModel()
    @AppStorage(AppMode.storageKey) private var modeRaw = ""
    @State private var thermo = ""
    var onDone: (() -> Void)?

    var body: some View {
        let L = m.L
        NavigationStack {
            Form {
                ContactsSection(L: L)
                familySection(L)
                profileSection(L)
                medicinesSection(L)
                MedListSection(L: L)
                SettingsRoutineSection(vm: vm, L: L)
                if AppMode(rawValue: modeRaw) == .elder || AppMode.current == .elder { PlacesSection(L: L) }
                homeSection(L)
                notificationsSection(L)
                connectionSection(L)
                diagnosticsSection(L)
                languageSection(L)
                advancedSection(L)
                Section(L.about) {
                    Text(L.uiAboutRelay).font(.footnote)
                    Text(L.footer).font(.footnote).foregroundStyle(.secondary)
                }
            }
            .navigationTitle(L.tabSettings)
            .toolbar {
                if let done = onDone {
                    ToolbarItem(placement: .confirmationAction) { Button(L.done, action: done) }
                }
            }
        }
    }

    private func familySection(_ L: Strings) -> some View {
        Section {
            TextField(L.familyName, text: vm.binding(\.familyName))
                .textContentType(.givenName)
            Button { _ = vm.sendFamilyName() } label: { Label(L.sendProfile, systemImage: "arrow.up.circle") }
        } header: { Text(L.familyName) } footer: { Text(L.familyNameNote(vm.familyNameBytes)) }
    }

    private func profileSection(_ L: Strings) -> some View {
        Section {
            TextField(L.name, text: $m.wearerName).textContentType(.name)
            TextField(L.phone, text: $m.wearerPhone).keyboardType(.phonePad).textContentType(.telephoneNumber)
            Stepper(value: $m.age, in: 18...110) { LabeledContent(L.age, value: "\(m.age)") }
            Picker(L.sex, selection: $m.sexMale) {
                Text(L.female).tag(false)
                Text(L.male).tag(true)
            }
            Stepper(value: $m.bmi, in: 14...50, step: 0.5) { LabeledContent(L.bmi, value: m.bmi.f1(m.lang)) }
            Stepper(value: $m.restHR, in: 40...100) { LabeledContent(L.restHR, value: "\(m.restHR)") }
            TextField(L.thermo, text: $thermo).keyboardType(.decimalPad)
        } header: { Text(L.uiHerProfile) } footer: { Text(L.thermoNote) }
    }

    private func medicinesSection(_ L: Strings) -> some View {
        Section {
            Toggle(L.medBeta, isOn: vm.medBinding(1))
            Toggle(L.medDiuretic, isOn: vm.medBinding(2))
            Toggle(L.medLowSweat, isOn: vm.medBinding(4))
            Toggle(L.medAce, isOn: vm.medBinding(8))
            Toggle(L.medOther, isOn: vm.medBinding(16))
            Button {
                vm.sendProfile(thermometer: Double(thermo.replacingOccurrences(of: ",", with: ".")))
            } label: { Label(L.sendProfile, systemImage: "arrow.up.circle") }
            if let r = vm.sendResult { Text(r).font(.footnote).foregroundStyle(.secondary) }
        } header: { Text(L.meds) } footer: {
            VStack(alignment: .leading, spacing: 4) {
                Text(L.profileHow)
                Text(vm.profileLine).font(.footnote.monospaced()).textSelection(.enabled)
            }
        }
    }

    private func homeSection(_ L: Strings) -> some View {
        Section {
            Picker(L.floorLabel, selection: vm.binding(\.routine.floor)) {
                Text("—").tag(Floor?.none)
                ForEach(Floor.allCases) { Text(L.floorName($0)).tag(Floor?.some($0)) }
            }
            Picker(L.buildLabel, selection: vm.binding(\.routine.build)) {
                Text("—").tag(Build?.none)
                ForEach(Build.allCases) { Text(L.buildName($0)).tag(Build?.some($0)) }
            }
            if let c = vm.homeClass { LabeledContent(L.uiHomeClass(c), value: c) }
        } header: { Text(L.uiHomeType) }
    }

    private func notificationsSection(_ L: Strings) -> some View {
        Section {
            Toggle(L.summaryToggle, isOn: vm.binding(\.summaryOn))
            Button { vm.requestNotifications() } label: { Label(L.notifPermission, systemImage: "bell.badge") }
        } header: { Text(L.notifPermission) } footer: { Text(L.notifNote) }
    }

    private func connectionSection(_ L: Strings) -> some View {
        let c = vm.connection
        return Section {
            Label { Text(c.text) } icon: { Image(systemName: c.symbol).foregroundStyle(c.tone.color) }
            if c.connected || c.busy {
                Button(L.disconnect, role: .destructive) { vm.disconnect() }
            } else {
                Button { vm.connect() } label: { Label(L.connect, systemImage: "link") }
            }
            if c.hasSavedBand { Button(L.forget, role: .destructive) { vm.forget() } }
            if let fw = vm.fwText { LabeledContent("fw", value: fw) }
        } header: { Text(L.band) } footer: { Text(c.help) }
    }

    private func diagnosticsSection(_ L: Strings) -> some View {
        Section {
            NavigationLink { DemoControls() } label: { Label(L.demo, systemImage: "play.rectangle") }
            if vm.isDemo {
                Button(L.demoStop, role: .destructive) { vm.stopDemo() }
            } else {
                Button { vm.startDemo() } label: { Label(L.demoStart, systemImage: "play") }
            }
            ForEach(vm.diagnostics, id: \.self) { Text($0).font(.footnote.monospaced()) }
            if !vm.writes.isEmpty {
                DisclosureGroup(L.lastWrites) {
                    ForEach(vm.writes) { w in
                        VStack(alignment: .leading, spacing: 2) {
                            Text((w.simulated ? L.sim + " · " : "") + w.label).font(.caption.weight(.semibold))
                            Text(w.hex).font(.caption.monospaced()).foregroundStyle(.secondary).textSelection(.enabled)
                        }
                    }
                }
            }
        } header: { Text(L.diagnostics) } footer: { Text(L.demoNote) }
    }

    private func languageSection(_ L: Strings) -> some View {
        Section(L.language) {
            Picker(L.language, selection: $m.lang) {
                ForEach(Lang.allCases) { Text($0.native).tag($0) }
            }
            .pickerStyle(.segmented)
        }
    }

    private func advancedSection(_ L: Strings) -> some View {
        Section(L.uiAdvanced) {
            // owner decision Nov 19: the family dashboard is no longer the product (the family gets SMS); kept behind
            // this toggle for the competition demo. Off = her screen (the Tower).
            Toggle(L.twFamilyView, isOn: Binding(
                get: { AppMode(rawValue: modeRaw) == .family },
                set: { on in
                    modeRaw = (on ? AppMode.family : AppMode.elder).rawValue
                    m.updateLocation()
                    onDone?()
                }))
            Text(L.twFamilyViewNote).font(.footnote).foregroundStyle(.secondary)
        }
    }
}

/// Routine: wake, bed, nap, two usual outings, A/C (ROUTINE_SEED 0x19).
struct SettingsRoutineSection: View {
    @EnvironmentObject var m: AppModel
    @ObservedObject var vm: SettingsViewModel
    var L: Strings

    var body: some View {
        Section {
            timeRow(L.wakeTime, \.wake, 7 * 60 + 30)
            timeRow(L.bedTime, \.bed, 23 * 60)
            windowRow(L.napTime, \.nap, 14 * 60, 16 * 60)
            windowRow(L.outTime + " 1", \.out1, 10 * 60, 11 * 60)
            windowRow(L.outTime + " 2", \.out2, 18 * 60, 19 * 60)
            Picker(L.hasAC, selection: vm.binding(\.routine.ac)) {
                Text("—").tag(Bool?.none)
                Text(L.t("Ναι", "Yes")).tag(Bool?.some(true))
                Text(L.t("Όχι", "No")).tag(Bool?.some(false))
            }
            Button { _ = vm.sendRoutine() } label: { Label(L.sendRoutine, systemImage: "arrow.up.circle") }
        } header: { Text(L.uiRoutine) } footer: { Text(L.routineSeedNote) }
    }

    @ViewBuilder
    private func timeRow(_ title: String, _ kp: WritableKeyPath<Routine, Int?>, _ fallback: Int) -> some View {
        Toggle(title, isOn: vm.isSet(kp, fallback: fallback))
        if m.routine[keyPath: kp] != nil {
            DatePicker(title, selection: vm.timeBinding(kp, fallback: fallback), displayedComponents: .hourAndMinute)
        }
    }

    @ViewBuilder
    private func windowRow(_ title: String, _ kp: WritableKeyPath<Routine, TimeWindow?>, _ from: Int, _ to: Int) -> some View {
        Toggle(title, isOn: vm.windowBinding(kp, from: from, to: to))
        if m.routine[keyPath: kp] != nil {
            DatePicker(L.t("από", "from"), selection: vm.windowEdge(kp, start: true), displayedComponents: .hourAndMinute)
            DatePicker(L.t("έως", "to"), selection: vm.windowEdge(kp, start: false), displayedComponents: .hourAndMinute)
        }
    }
}

#Preview("Settings") { FamilyPreview(state: nil, tab: .settings) }
