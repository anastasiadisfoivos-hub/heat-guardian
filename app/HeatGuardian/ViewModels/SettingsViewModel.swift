// «Ρυθμίσεις»: the family member's name, her profile + medicines, her routine / home, notifications, connection,
// diagnostics. Editable values are Bindings straight into AppModel (persisted there); the rest is read-only state.

import Combine
import Foundation
import SwiftUI

struct ConnectionState: Equatable {
    var text: String
    var symbol: String
    var tone: Tone
    var connected: Bool
    var busy: Bool               // scanning / connecting / pairing / reconnecting
    var hasSavedBand: Bool
    var help: String             // connect instructions for this firmware
}

final class SettingsViewModel: ObservableObject {
    static let medBits: [(bit: Int, key: String)] = [(1, "beta"), (2, "diuretic"), (4, "lowSweat"), (8, "ace"), (16, "other")]

    @Published private(set) var connection = ConnectionState(text: "", symbol: "", tone: .neutral, connected: false, busy: false, hasSavedBand: false, help: "")
    @Published private(set) var fwText: String?                // «0.9.7»
    @Published private(set) var diagnostics: [String] = []     // plain lines
    @Published private(set) var writes: [WriteLog] = []
    @Published private(set) var familyNameBytes = 0            // of 14
    @Published private(set) var homeClass: String?             // A–D from floor + build, nil = not stated
    @Published private(set) var profileLine = ""               // `profile <age> <sex> <bmi> <meds>` console line
    @Published private(set) var sendResult: String?
    @Published private(set) var isDemo = false
    @Published private(set) var bandHasEvents = false          // fw 0.9.7 EVENTS present

    let model: AppModel
    private var bag: AnyCancellable?

    init(model: AppModel = .shared) {
        self.model = model
        refresh()
        bag = model.objectWillChange.debounce(for: .milliseconds(30), scheduler: DispatchQueue.main).sink { [weak self] _ in self?.refresh() }
    }

    /// Two-way binding to any persisted AppModel setting, e.g. binding(\.familyName), binding(\.routine.ac).
    func binding<T>(_ kp: ReferenceWritableKeyPath<AppModel, T>) -> Binding<T> {
        Binding(get: { self.model[keyPath: kp] }, set: { self.model[keyPath: kp] = $0 })
    }

    /// One medicine checkbox (PROFILE field 5 bit).
    func medBinding(_ bit: Int) -> Binding<Bool> {
        Binding(get: { (self.model.medFlags & bit) != 0 },
                set: { on in if on { self.model.medFlags |= bit } else { self.model.medFlags &= ~bit } })
    }

    /// An optional minute-of-day as a Date for a DatePicker (nil -> `fallback`), and the switch that turns it on/off.
    func timeBinding(_ kp: WritableKeyPath<Routine, Int?>, fallback: Int) -> Binding<Date> {
        Binding(get: { Date().at(minute: self.model.routine[keyPath: kp] ?? fallback) },
                set: { self.model.routine[keyPath: kp] = $0.minuteOfDay })
    }
    func isSet(_ kp: WritableKeyPath<Routine, Int?>, fallback: Int) -> Binding<Bool> {
        Binding(get: { self.model.routine[keyPath: kp] != nil },
                set: { self.model.routine[keyPath: kp] = $0 ? fallback : nil })
    }
    func windowBinding(_ kp: WritableKeyPath<Routine, TimeWindow?>, from: Int, to: Int) -> Binding<Bool> {
        Binding(get: { self.model.routine[keyPath: kp] != nil },
                set: { self.model.routine[keyPath: kp] = $0 ? TimeWindow(from: from, to: to) : nil })
    }
    func windowEdge(_ kp: WritableKeyPath<Routine, TimeWindow?>, start: Bool) -> Binding<Date> {
        Binding(get: {
            let w = self.model.routine[keyPath: kp]
            return Date().at(minute: (start ? w?.from : w?.to) ?? 0)
        }, set: { d in
            guard var w = self.model.routine[keyPath: kp] else { return }
            if start { w.from = d.minuteOfDay } else { w.to = d.minuteOfDay }
            self.model.routine[keyPath: kp] = w
        })
    }

    // actions
    func connect() { model.link.connect() }
    func disconnect() { model.link.disconnect() }
    func forget() { model.link.forget() }
    @discardableResult func sendFamilyName() -> Bool { model.sendFamilyName() }
    @discardableResult func sendRoutine() -> Bool { model.sendRoutine() }
    func sendProfile(thermometer: Double?) { model.sendProfile(thermometer: thermometer) }
    func startDemo() { model.startDemo() }
    func stopDemo() { model.stopDemo() }
    func requestNotifications() { AlertFX.shared.requestNotificationPermission() }

    func refresh() {
        let m = model, L = m.L
        let (text, sym, tone) = SettingsViewModel.phase(m, L)
        let busy = [BandLink.Phase.scanning, .connecting, .pairing, .reconnecting].contains(m.phase)
        let c = ConnectionState(text: text, symbol: sym, tone: tone, connected: m.phase == .connected, busy: busy,
                                hasSavedBand: BandLink.hasSavedBand, help: L.connectBody(m.info?.fwVersion))
        if connection != c { connection = c }
        fwText = m.info?.fwText
        var dg = ["\(m.stats.frames) \(L.frames), \(m.stats.crcErrors) \(L.crcRejected), \(m.stats.gaps) \(L.gaps)"]
        if let i = m.info {
            dg.append("\(L.model) \(i.hg2Tag) 0x\(String(format: "%08x", i.nnCRC)), fw \(i.fwText), boots \(i.bootCount)")
        }
        if let b = m.store.cursorBoot { dg.append("EVENTS boot \(b) seq \(m.store.cursorSeq), \(m.store.entries.count)") }
        if let u = BandEventDiagnostics.shared.summary { dg.append(u) }
        if diagnostics != dg { diagnostics = dg }
        writes = m.writes
        familyNameBytes = Frames.familyNameBytes(m.familyName).count
        homeClass = m.routine.homeClass
        profileLine = m.profileLine
        sendResult = m.lastSendResult
        isDemo = m.isDemo
        bandHasEvents = m.link.hasEvents
    }

    static func phase(_ m: AppModel, _ L: Strings) -> (String, String, Tone) {
        switch m.phase {
        case .idle: return (L.disconnected, "antenna.radiowaves.left.and.right.slash", .offline)
        case .poweredOff: return (L.btOff, "exclamationmark.circle", .heat)
        case .unauthorized: return (L.btDenied, "exclamationmark.circle", .heat)
        case .scanning: return (L.scanning, "magnifyingglass", .neutral)
        case .connecting: return (L.connecting, "dot.radiowaves.left.and.right", .neutral)
        case .pairing: return (L.pairing, "lock.fill", .neutral)
        case .connected: return (L.connected + (m.link.deviceName.map { " — \($0)" } ?? ""), "checkmark.circle.fill", .ok)
        case .reconnecting: return (L.reconnecting, "arrow.triangle.2.circlepath", .neutral)
        case .failed(let e): return (L.failed + e, "xmark.octagon.fill", .danger)
        case .pairingFailed: return (L.pairFailed, "lock.slash.fill", .danger)
        case .pairingRemoved: return (L.pairRemoved, "lock.slash.fill", .danger)
        case .notFound: return (L.t("Δεν βρέθηκε βραχιόλι κοντά.", "No band found nearby."), "questionmark.circle", .heat)
        }
    }
}
