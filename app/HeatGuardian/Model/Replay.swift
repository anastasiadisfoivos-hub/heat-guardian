// dashboard/replays/*.json (format "hg-replay-1"): STATUS frames as hex, one per minute, produced by
// dashboard/tools/make_replay.py from the frozen guardian mirror. Bundled read-only copies.

import Foundation

struct Replay: Codable {
    struct Person: Codable { var age: Int? }
    struct Event: Codable { var i: Int; var kind: String; var alarmId: Int?
        enum CodingKeys: String, CodingKey { case i, kind, alarmId = "alarm_id" } }
    struct Path: Codable { var familyMinute: Int?
        enum CodingKeys: String, CodingKey { case familyMinute = "family_minute" } }

    var kind: String                // "sim" | "real"
    var tag: [String: String]
    var tagDetail: [String: String]
    var title: [String: String]
    var person: Person?
    var startMod: Int?              // minute of day of frame 0; nil = a session with no clock (HTT chamber)
    var status: [String]
    var screen: [Int]?
    var events: [Event]?
    var path: Path?

    enum CodingKeys: String, CodingKey {
        case kind, tag, title, person, status, screen, events, path
        case tagDetail = "tag_detail", startMod = "start_mod"
    }

    var isSim: Bool { kind == "sim" }
    var firstFamilyIndex: Int? { events?.first(where: { $0.kind == "family_alert" })?.i }

    static func bundled(_ name: String) -> Replay? {
        guard let url = Bundle.main.url(forResource: name, withExtension: "json"),
              let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(Replay.self, from: data)
    }

    /// Band screen texts (guardian/c/hg_guardian.c SCR_TXT), indexed by the recording's screen id.
    static let bandScreens = ["Όλα καλά", "Πιείτε νερό τώρα", "Πάτε σε πιο δροσερό δωμάτιο", "Χλιαρό ντους ή κρύα κομπρέσα",
                              "Είστε καλά; Πατήστε το κουμπί", "Ειδοποιήσαμε την οικογένεια", "Εντάξει, ευχαριστώ",
                              "Φορέστε το βραχιόλι", "Σφίξτε το λουράκι", "Φορτίστε το βραχιόλι",
                              "Βοήθεια: ειδοποιούμε την οικογένεια", "Δροσίστε το δωμάτιο"]
}

/// Plays a replay through AppModel.ingest(), the same decoder path as the band ("MOCK DEVICE" of the dashboard).
final class DemoPlayer {
    let replay: Replay
    let file: String
    private(set) var index: Int = 0
    private(set) var playing = false
    var speed: Int = 60 { didSet { if playing { play() } } }
    private var timer: Timer?
    private let base: Date

    /// frame -> (bytes, clock of that minute, index)
    var onFrame: (([UInt8], Date, Int) -> Void)?
    var onTick: (() -> Void)?

    init(replay: Replay, file: String) {
        self.replay = replay
        self.file = file
        // Clock: the replay's minute-of-day on today's date (sim day); a clockless session starts "now".
        let cal = Calendar.current
        if let sm = replay.startMod {
            base = cal.startOfDay(for: Date()).addingTimeInterval(TimeInterval(sm * 60))
        } else {
            base = Date().addingTimeInterval(TimeInterval(-replay.status.count * 60))
        }
    }

    var count: Int { replay.status.count }
    func clock(_ i: Int) -> Date { base.addingTimeInterval(TimeInterval(i * 60)) }
    func bytes(_ i: Int) -> [UInt8]? { Frames.fromHex(replay.status[i]) }
    var screenText: String? {
        guard let s = replay.screen, index < s.count, s[index] >= 0, s[index] < Replay.bandScreens.count else { return nil }
        return Replay.bandScreens[s[index]]
    }

    /// Same pacing rule as dashboard setPlaying(): tick = max(60000/speed ms, 50 ms), frames per tick = round(tick/ms).
    func play() {
        timer?.invalidate()
        playing = true
        let ms = 60000.0 / Double(speed)
        let tick = max(ms, 50.0)
        let per = max(1, Int((tick / ms).rounded()))
        timer = Timer.scheduledTimer(withTimeInterval: tick / 1000.0, repeats: true) { [weak self] _ in
            self?.step(per)
        }
        onTick?()
    }

    func pause() {
        timer?.invalidate()
        timer = nil
        playing = false
        onTick?()
    }

    /// Feed frames index+1 ... index+n (each one, so no family alert edge is skipped).
    func step(_ n: Int) {
        let to = min(count - 1, index + n)
        if to <= index { pause(); return }
        for i in (index + 1)...to {
            index = i
            if let b = bytes(i) { onFrame?(b, clock(i), i) }
        }
        if index >= count - 1 { pause() }
        onTick?()
    }

    /// Jump: the owner clears its demo history first; frames 0..<i are fed as history (no alerts), then frame i.
    func seek(to i: Int, prefill: ([UInt8], Date, Int) -> Void) {
        let target = max(0, min(count - 1, i))
        for k in 0..<target { if let b = bytes(k) { prefill(b, clock(k), k) } }
        index = target
        if let b = bytes(target) { onFrame?(b, clock(target), target) }
        onTick?()
    }

    deinit { timer?.invalidate() }
}
