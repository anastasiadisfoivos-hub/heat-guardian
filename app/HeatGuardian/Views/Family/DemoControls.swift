// Demo controls (pushed from Settings): recording, speed, scrubber, jumps, «trigger alert now (for filming)».

import SwiftUI

/// Demo controls (sheet from Now, or pushed from Settings).
struct DemoControls: View {
    @EnvironmentObject var m: AppModel
    @State private var file = "sim_heatwave"

    var body: some View {
        let L = m.L
        let p = m.demo
        Form {
            Section {
                HStack { SimBadge(text: L.sim); Spacer() }
                Picker(L.recording, selection: $file) {
                    Text(m.lang == .el ? "Μέρα καύσωνα, εικονικό άτομο 398" : "Heat-wave day, virtual person 398").tag("sim_heatwave")
                    Text(m.lang == .el ? "Θάλαμος θερμότητας HTT1 (πραγματικά δεδομένα, νέος ενήλικας)" : "Heat chamber HTT1 (real data, young adult)").tag("htt_chamber")
                }
                .onChange(of: file) { _, f in m.startDemo(file: f, speed: p?.speed ?? 60) }
                if let p = p {
                    Text(p.replay.tag[m.lang.rawValue] ?? "").font(.footnote.weight(.bold)).foregroundStyle(Palette.sim)
                    Text(p.replay.tagDetail[m.lang.rawValue] ?? "").font(.footnote).foregroundStyle(.secondary)
                }
            } footer: { Text(L.demoNote) }

            if let p = p {
                Section(L.speed) {
                    Picker(L.speed, selection: Binding(get: { p.speed }, set: { m.setDemoSpeed($0) })) {
                        Text("1×").tag(1)
                        Text("10×").tag(10)
                        Text("60×").tag(60)
                    }
                    .pickerStyle(.segmented)
                    Button { m.toggleDemoPlay() } label: {
                        Label(p.playing ? L.pause : L.play, systemImage: p.playing ? "pause.fill" : "play.fill")
                    }
                    Slider(value: Binding(get: { Double(p.index) }, set: { m.seekDemo(Int($0)) }), in: 0...Double(max(1, p.count - 1)), step: 1)
                    Text(clock(p)).font(.footnote.monospacedDigit()).foregroundStyle(.secondary)
                }
                Section {
                    if p.replay.startMod != nil {
                        Button { m.seekDemo(420) } label: { Label(L.jumpMorning, systemImage: "sunrise.fill") }
                    }
                    if p.replay.startMod == 0 {
                        // Her Day: 20:00 = tomorrow's plan is on the band (evening send at 18:00), the elder card shows
                        Button { m.seekDemo(20 * 60) } label: { Label(L.hdJumpEvening, systemImage: "moon.stars.fill") }
                        Toggle(isOn: Binding(get: { m.demoHotterTomorrow }, set: { m.setDemoHotterTomorrow($0) })) {
                            Label(L.hdHotterTomorrow, systemImage: "thermometer.sun.fill")
                        }
                    }
                    if let fi = p.replay.firstFamilyIndex {
                        Button { m.seekDemo(max(0, fi - 6)) } label: { Label(L.jumpBefore, systemImage: "backward.end.fill") }
                    }
                    Button { m.triggerDemoAlert() } label: {
                        Label(L.triggerAlert, systemImage: "bell.and.waves.left.and.right.fill").foregroundStyle(Palette.danger)
                    }
                }
                Section {
                    Button(role: .destructive) { m.stopDemo() } label: { Label(L.demoStop, systemImage: "stop.fill") }
                }
            } else {
                Section {
                    Button { m.startDemo(file: file) } label: { Label(L.demoStart, systemImage: "play.fill") }
                    Button { m.triggerDemoAlert() } label: {
                        Label(L.triggerAlert, systemImage: "bell.and.waves.left.and.right.fill").foregroundStyle(Palette.danger)
                    }
                }
            }
        }
        .navigationTitle(L.demo)
        .onAppear { if let p = m.demo { file = p.file } }
    }

    private func clock(_ p: DemoPlayer) -> String {
        if let sm = p.replay.startMod {
            let mm = (sm + p.index) % 1440
            return String(format: "%02d:%02d", mm / 60, mm % 60)
        }
        return "\(p.index + 1) / \(p.count) \(m.L.minutesShort)"
    }
}
