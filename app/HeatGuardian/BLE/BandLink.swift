// CoreBluetooth link to the band. Mirrors dashboard/js/ble.js (BandLink): connect -> subscribe STATUS -> send TIME ->
// read STATUS once -> read INFO -> (owner's on-connect writes) -> subscribe EVENTS (0.9.7) -> owner sends SYNC_EVENTS. Writes are serialised (one GATT operation at a time).
//
// Pairing (fw 0.9.5, branch b7-ble-sec): STATUS / CMD / INFO need an encrypted, MITM link. iOS starts bonding by
// itself on the first secured access (the STATUS subscribe below) and shows the system "Bluetooth Pairing Request"
// with a code field; the band shows the 6 digits. Bonded once, iOS reconnects without a prompt. A refused/cancelled
// pairing surfaces as an ATT "insufficient authentication/encryption" error on that subscribe -> .pairingFailed.
// Older bands (0.9.3/0.9.4) have no security: the subscribe simply succeeds, no prompt.
//
// The link hands RAW bytes to its owner; decoding happens in AppModel.ingest(), the same path the demo player uses.

import CoreBluetooth
import Foundation

final class BandLink: NSObject {
    enum Phase: Equatable {
        case idle, poweredOff, unauthorized, scanning, connecting, pairing, connected, reconnecting
        case failed(String), pairingFailed, pairingRemoved, notFound
    }

    var onPhase: ((Phase) -> Void)?
    var onStatusBytes: (([UInt8]) -> Void)?
    var onInfo: ((Frames.Info) -> Void)?
    /// EVENTS notify (0004), raw bytes; decoded in AppModel.
    var onEventBytes: (([UInt8]) -> Void)?
    /// STATUS is subscribed and TIME is queued: the owner queues its own on-connect writes after TIME.
    var onReady: (() -> Void)?
    /// EVENTS notify is on (fw 0.9.7+): the owner sends SYNC_EVENTS now, so the replayed events arrive.
    var onEventsReady: (() -> Void)?
    var onWrite: ((String, String) -> Void)?   // (label, hex)

    private(set) var phase: Phase = .idle { didSet { if phase != oldValue { onPhase?(phase) } } }
    private(set) var deviceName: String?
    var hasConsole: Bool { nusRX != nil }
    /// The band offers the EVENTS characteristic (fw 0.9.7+).
    var hasEvents: Bool { eventsChar != nil }
    var isConnected: Bool { phase == .connected }

    private var central: CBCentralManager?
    private var peripheral: CBPeripheral?
    private var statusChar: CBCharacteristic?
    private var cmdChar: CBCharacteristic?
    private var infoChar: CBCharacteristic?
    private var eventsChar: CBCharacteristic?
    private var nusRX: CBCharacteristic?
    private var wantConnection = false
    private var scanTimer: Timer?
    private var queue: [(bytes: [UInt8], label: String, toConsole: Bool)] = []
    private var writing = false

    private static let savedKey = "hg.bandUUID"
    private static let restoreID = "gr.heatguardian.family.central"
    private let svcUUID = CBUUID(string: HG.service)
    private let nusUUID = CBUUID(string: HG.nusService)

    static var hasSavedBand: Bool { UserDefaults.standard.string(forKey: savedKey) != nil }

    /// Creating the central manager shows the Bluetooth permission prompt the first time, so it is created lazily
    /// (Connect button), or at launch when a band was already paired (needed for background state restoration).
    func ensureCentral() {
        guard central == nil else { return }
        central = CBCentralManager(delegate: self, queue: .main, options: [
            CBCentralManagerOptionRestoreIdentifierKey: BandLink.restoreID,
            CBCentralManagerOptionShowPowerAlertKey: true,
        ])
    }

    func connect() {
        wantConnection = true
        ensureCentral()
        if central?.state == .poweredOn { start() }
        // otherwise centralManagerDidUpdateState calls start()
    }

    func disconnect() {
        wantConnection = false
        stopScan()
        if let p = peripheral { central?.cancelPeripheralConnection(p) }
        resetChars()
        phase = .idle
    }

    /// Forget the saved band in this app. The iOS bond itself lives in iPhone Settings › Bluetooth.
    func forget() {
        disconnect()
        UserDefaults.standard.removeObject(forKey: BandLink.savedKey)
        peripheral = nil
        deviceName = nil
    }

    // MARK: writes

    /// `urgent` (default: by opcode, `Frames.isUrgentCommand`) = ahead of the on-connect writes (HELP from the phone,
    /// family replies, SYNC_EVENTS). With the band's ~1 s connection interval each write-with-response takes about a
    /// second, and a fresh connection queues up to ~20 (name, routine, plan, visits, day plans): a HELP at the back of
    /// that queue would wait ~20 s.
    func send(_ bytes: [UInt8], label: String, urgent: Bool? = nil) {
        if urgent ?? Frames.isUrgentCommand(bytes) {
            let i = queue.firstIndex { !Frames.isUrgentCommand($0.bytes) && !$0.toConsole } ?? queue.count
            queue.insert((bytes, label, false), at: i)
        } else {
            queue.append((bytes, label, false))
        }
        pump()
    }

    /// Calls `done` when every queued write has gone out (or after `timeout` s): used by background notification
    /// actions so iOS does not suspend the app before the band got the command.
    func whenFlushed(timeout: TimeInterval = 6, _ done: @escaping () -> Void) {
        let start = Date()
        func poll() {
            if (queue.isEmpty && !writing) || Date().timeIntervalSince(start) > timeout || phase != .connected { done(); return }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { poll() }
        }
        poll()
    }

    /// A text line for the band's Nordic UART console (e.g. "profile 78 0 23.0 9"). Split into 20-byte writes.
    func sendConsoleLine(_ line: String) -> Bool {
        guard nusRX != nil else { return false }
        let bytes = Array((line + "\n").utf8)
        var i = 0
        while i < bytes.count {
            let part = Array(bytes[i..<min(i + 20, bytes.count)])
            queue.append((part, i == 0 ? "UART " + line : "UART …", true))
            i += 20
        }
        pump()
        return true
    }

    private func pump() {
        guard !writing, !queue.isEmpty, let p = peripheral, phase == .connected else { return }
        let item = queue.removeFirst()
        guard let ch = item.toConsole ? nusRX : cmdChar else { pump(); return }
        let withResponse = ch.properties.contains(.write)
        p.writeValue(Data(item.bytes), for: ch, type: withResponse ? .withResponse : .withoutResponse)
        onWrite?(item.label, Frames.toHex(item.bytes))
        if withResponse {
            writing = true   // released in didWriteValueFor
        } else {
            writing = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { [weak self] in
                self?.writing = false
                self?.pump()
            }
        }
    }

    // MARK: private

    private func start() {
        guard let c = central else { return }
        // 1. already connected to iOS (e.g. by another app or restored)
        if let p = c.retrieveConnectedPeripherals(withServices: [svcUUID]).first { attach(p); return }
        // 2. the band we paired before: a pending connect never times out and also works in the background
        if let s = UserDefaults.standard.string(forKey: BandLink.savedKey), let id = UUID(uuidString: s),
           let p = c.retrievePeripherals(withIdentifiers: [id]).first {
            attach(p)
            return
        }
        // 3. scan (foreground). The band may not put its 128-bit service in the advert, so match the name too.
        phase = .scanning
        c.scanForPeripherals(withServices: nil, options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
        scanTimer?.invalidate()
        scanTimer = Timer.scheduledTimer(withTimeInterval: 25, repeats: false) { [weak self] _ in
            guard let self = self, self.phase == .scanning else { return }
            self.stopScan()
            self.phase = .notFound
        }
    }

    private func stopScan() {
        scanTimer?.invalidate()
        scanTimer = nil
        if central?.isScanning == true { central?.stopScan() }
    }

    private func attach(_ p: CBPeripheral) {
        stopScan()
        peripheral = p
        p.delegate = self
        deviceName = p.name ?? HG.namePrefix
        phase = .connecting
        if p.state == .connected { p.discoverServices([svcUUID, nusUUID]) } else { central?.connect(p, options: nil) }
    }

    private func resetChars() {
        statusChar = nil; cmdChar = nil; infoChar = nil; eventsChar = nil; nusRX = nil
        queue.removeAll(); writing = false
    }

    private func isPairingError(_ error: Error) -> Bool {
        let ns = error as NSError
        if ns.domain == CBATTErrorDomain {
            let code = CBATTError.Code(rawValue: ns.code)
            return code == .insufficientAuthentication || code == .insufficientEncryption
                || code == .insufficientEncryptionKeySize || code == .insufficientAuthorization
        }
        if ns.domain == CBErrorDomain {
            let code = CBError.Code(rawValue: ns.code)
            return code == .encryptionTimedOut
        }
        return false
    }

    private func isPeerRemovedPairing(_ error: Error?) -> Bool {
        guard let ns = error as NSError?, ns.domain == CBErrorDomain else { return false }
        return CBError.Code(rawValue: ns.code) == .peerRemovedPairingInformation
    }
}

extension BandLink: CBCentralManagerDelegate {
    func centralManagerDidUpdateState(_ c: CBCentralManager) {
        switch c.state {
        case .poweredOn:
            if wantConnection || BandLink.hasSavedBand {
                wantConnection = true
                if let p = peripheral, p.state == .connected {
                    // Restored after a background relaunch: iOS kept the link, but this process has not discovered the
                    // services yet (not allowed before .poweredOn), so STATUS / CMD are still nil. Discover them now.
                    if statusChar == nil || cmdChar == nil {
                        phase = .connecting
                        p.discoverServices([svcUUID, nusUUID])
                    }
                } else {
                    start()
                }
            }
        case .poweredOff: phase = .poweredOff
        case .unauthorized: phase = .unauthorized
        default: break
        }
    }

    func centralManager(_ c: CBCentralManager, willRestoreState dict: [String: Any]) {
        if let ps = dict[CBCentralManagerRestoredStatePeripheralsKey] as? [CBPeripheral], let p = ps.first {
            peripheral = p
            p.delegate = self
            deviceName = p.name ?? HG.namePrefix
            wantConnection = true
            // Discovery waits for centralManagerDidUpdateState(.poweredOn): CoreBluetooth calls are not allowed yet.
            if p.state == .connected { phase = .connecting }
        }
    }

    func centralManager(_ c: CBCentralManager, didDiscover p: CBPeripheral, advertisementData: [String: Any], rssi RSSI: NSNumber) {
        let advName = (advertisementData[CBAdvertisementDataLocalNameKey] as? String) ?? p.name ?? ""
        let advSvcs = (advertisementData[CBAdvertisementDataServiceUUIDsKey] as? [CBUUID]) ?? []
        guard advName.hasPrefix(HG.namePrefix) || advSvcs.contains(svcUUID) else { return }
        attach(p)
    }

    func centralManager(_ c: CBCentralManager, didConnect p: CBPeripheral) {
        phase = .connecting
        p.discoverServices([svcUUID, nusUUID])
    }

    func centralManager(_ c: CBCentralManager, didFailToConnect p: CBPeripheral, error: Error?) {
        phase = .failed(error?.localizedDescription ?? "connect")
        // A failed link setup (common right after the band reboots / wakes from System OFF) must not end the
        // reconnect: keep a pending connect while the owner still wants the band.
        retryConnect(p)
    }

    /// Pending connect again after 2 s (no timeout on iOS: it completes when the band advertises).
    private func retryConnect(_ p: CBPeripheral) {
        guard wantConnection else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            guard let self = self, self.wantConnection, let c = self.central, c.state == .poweredOn, self.peripheral === p,
                  p.state == .disconnected else { return }
            self.phase = .reconnecting
            c.connect(p, options: nil)
        }
    }

    /// A GATT error on a live link (discovery / subscribe): drop the link so the pending reconnect starts clean.
    private func restartLink(_ p: CBPeripheral, _ why: String) {
        phase = .failed(why)
        if wantConnection { central?.cancelPeripheralConnection(p) }
    }

    func centralManager(_ c: CBCentralManager, didDisconnectPeripheral p: CBPeripheral, error: Error?) {
        resetChars()
        if isPeerRemovedPairing(error) { phase = .pairingRemoved; wantConnection = false; return }
        if phase == .pairingFailed { return }
        if wantConnection {
            // (also after restartLink: a discovery / subscribe error on the last link)
            phase = .reconnecting
            c.connect(p, options: nil)   // pending connect: iOS reconnects when the band is back in range
        } else {
            phase = .idle
        }
    }
}

extension BandLink: CBPeripheralDelegate {
    func peripheral(_ p: CBPeripheral, didDiscoverServices error: Error?) {
        if let e = error { restartLink(p, e.localizedDescription); return }
        for s in p.services ?? [] {
            if s.uuid == svcUUID {
                p.discoverCharacteristics([CBUUID(string: HG.status), CBUUID(string: HG.cmd), CBUUID(string: HG.info),
                                           CBUUID(string: HG.events)], for: s)
            } else if s.uuid == nusUUID {
                p.discoverCharacteristics([CBUUID(string: HG.nusRX)], for: s)
            }
        }
        if !(p.services ?? []).contains(where: { $0.uuid == svcUUID }) { phase = .failed("Heat Guardian service not found") }
    }

    func peripheral(_ p: CBPeripheral, didDiscoverCharacteristicsFor s: CBService, error: Error?) {
        if let e = error { restartLink(p, e.localizedDescription); return }
        for ch in s.characteristics ?? [] {
            switch ch.uuid {
            case CBUUID(string: HG.status): statusChar = ch
            case CBUUID(string: HG.cmd): cmdChar = ch
            case CBUUID(string: HG.info): infoChar = ch
            case CBUUID(string: HG.events): eventsChar = ch
            case CBUUID(string: HG.nusRX): nusRX = ch
            default: break
            }
        }
        if s.uuid == svcUUID {
            guard let st = statusChar, cmdChar != nil else { phase = .failed("STATUS/CMD missing"); return }
            // First secured access: on fw 0.9.5 this is where iOS shows its pairing prompt.
            phase = .pairing
            p.setNotifyValue(true, for: st)
        }
    }

    func peripheral(_ p: CBPeripheral, didUpdateNotificationStateFor ch: CBCharacteristic, error: Error?) {
        if ch.uuid == CBUUID(string: HG.events) {
            // An older band or a refused subscribe: the log simply has no band events.
            if error == nil && ch.isNotifying { onEventsReady?() }
            return
        }
        guard ch.uuid == CBUUID(string: HG.status) else { return }
        if let e = error {
            if isPairingError(e) {
                phase = .pairingFailed
                wantConnection = false
                central?.cancelPeripheralConnection(p)
            } else {
                restartLink(p, e.localizedDescription)
            }
            return
        }
        UserDefaults.standard.set(p.identifier.uuidString, forKey: BandLink.savedKey)
        deviceName = p.name ?? HG.namePrefix
        phase = .connected
        // The band's clock comes from the phone: send TIME first (with the local time zone in quarter hours).
        send(Frames.cmdTimeNow(), label: "TIME")
        p.readValue(for: ch)                       // one STATUS now, then a notify each minute / change
        if let info = infoChar { p.readValue(for: info) }
        onReady?()
        // EVENTS (0.9.7): subscribe after STATUS (the secured access that triggers pairing has already happened).
        if let ev = eventsChar { p.setNotifyValue(true, for: ev) }
    }

    func peripheral(_ p: CBPeripheral, didUpdateValueFor ch: CBCharacteristic, error: Error?) {
        if let e = error {
            if ch.uuid == CBUUID(string: HG.status), isPairingError(e) { phase = .pairingFailed }
            return
        }
        guard let v = ch.value else { return }
        let bytes = [UInt8](v)
        if ch.uuid == CBUUID(string: HG.status) {
            onStatusBytes?(bytes)
        } else if ch.uuid == CBUUID(string: HG.events) {
            onEventBytes?(bytes)
        } else if ch.uuid == CBUUID(string: HG.info), let i = try? Frames.decodeInfo(bytes) {
            onInfo?(i)
        }
    }

    func peripheral(_ p: CBPeripheral, didWriteValueFor ch: CBCharacteristic, error: Error?) {
        writing = false
        if let e = error, isPairingError(e) { phase = .pairingFailed }
        pump()
    }
}
