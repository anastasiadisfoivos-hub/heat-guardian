// Her home screen's "balance" (owner decision Nov 19 18:31 "keep it green", same meaning as the band's gauge):
// 5 steps green -> yellow-green -> yellow -> orange -> red, the band's own colours (hg_fw_ladder.c COL[]).
//
// Band 0.9.18+: the band sends its gauge itself — EVENTS type 22 GAUGE, a LIVE frame (seq 0, never in the ring, never
// stored, never moves the SYNC cursor; ECOSYSTEM_SPEC 5f) on a step change, once a minute while off green and on
// connect. Her screen shows EXACTLY that step and dot (Balance.display). Fallback (no GAUGE frame for 3 min, or a band
// before 0.9.18): the band's TIER from STATUS (OK / DRINK / COOL / CHECK-DANGER-HELP), step 1 only from the ladder,
// and the dot centred in the step.
//   GAUGE x: [10] arg = step 0-4, 0xFF no forecast (grey, no dot) | [11] i8 dot -10..+10 (0 when 0xFF) | [12] why
//            1 step changed, 2 minute refresh, 3 on connect, 4 bench | [13] reminder 0 none, 1 water, 2 cooler place |
//            [14-15] i16 f20 x100 (0x8000 unknown) | [16-18] 0.   Checked byte for byte: gauge_vectors_fw.json.

import Foundation

enum Balance {
    /// The band's colours (sRGB 0-255) and whether text on them is white — hg_ga_colour().
    static let colours: [(r: Int, g: Int, b: Int, whiteText: Bool)] = [
        (0, 120, 50, true), (150, 200, 30, false), (250, 220, 40, false), (235, 120, 0, false), (170, 0, 0, true)]
    static let grey = (r: 90, g: 90, b: 90, whiteText: true)

    /// Step 0-4 from the band's state (nil = no reading / not worn / no connection: grey, no dot).
    /// `settling`: the ladder said "worked" in the last 20 min while the band is back to OK -> step 1 (yellow-green).
    static func step(viewState vs: String, connected: Bool, settling: Bool = false) -> Int? {
        guard connected else { return nil }
        switch vs {
        case "OK", "IMOK", "BATTERY": return settling ? 1 : 0
        case "DRINK": return 2
        case "COOL": return 3
        case "CHECK", "DANGER", "HELP": return 4
        default: return nil          // WAIT, NOT_WORN, OFFLINE
        }
    }

    /// The dot on the curved scale, -10 (cool) … 0 (balanced) … +10 (Danger line), centred in each step's band.
    static func dot(_ step: Int?) -> Double? {
        guard let s = step else { return nil }
        return [-5.0, 0.5, 3.0, 6.0, 9.0][max(0, min(4, s))]
    }
}

extension Balance {
    /// A GAUGE frame older than this no longer drives her screen (the band refreshes it every minute while off green
    /// and on every step change; green can stay quiet longer, so the STATUS tier takes over).
    static let gaugeFresh: TimeInterval = 3 * 60

    /// What her gauge shows: the band's own step + dot from a fresh GAUGE frame, else the STATUS-derived tier.
    /// `gaugeAt` = when the phone received the frame (the band's clock may be unset).
    static func display(gauge: BandGauge?, gaugeAt: Date?, now: Date, connected: Bool,
                        fallbackStep: Int?) -> (step: Int?, dot: Double?, fromBand: Bool) {
        if connected, let g = gauge, let at = gaugeAt, now.timeIntervalSince(at) <= gaugeFresh, at <= now.addingTimeInterval(60) {
            return (g.step, g.step == nil ? nil : Double(g.dot), true)
        }
        return (fallbackStep, dot(fallbackStep), false)
    }
}

/// EVENTS type 22 GAUGE (band 0.9.18): the band's own "keep it green" gauge, as on her wrist.
struct BandGauge: Equatable {
    static let eventType = 22
    static let noForecast: UInt8 = 0xFF

    enum Why: Int, Equatable { case stepChanged = 1, minuteRefresh = 2, onConnect = 3, bench = 4 }

    /// 0 green, 1 yellow-green, 2 yellow, 3 orange, 4 red; nil = no forecast (grey, no dot).
    var step: Int?
    /// -10 (cool) … 0 (balanced) … +10 (Danger line); 0 when there is no forecast.
    var dot: Int
    var why: Int
    /// The ladder's reminder on the colour: 0 none, 1 water, 2 cooler place.
    var reminder: Int
    /// The 20-30 min core FORECAST the gauge was computed from (°C), nil = unknown. Context only, never shown as a reading.
    var forecastC: Double?

    var whyKind: Why? { Why(rawValue: why) }
    var reminderStep: LadderStep? { reminder == 0 ? nil : LadderStep(rawValue: reminder) }

    /// nil = not a GAUGE frame, or a step this app does not know (logged, ignored).
    static func decode(_ e: BandEvent) -> BandGauge? {
        guard e.kindRaw == eventType else { return nil }
        let x = e.ext.count >= 8 ? e.ext : e.ext + [UInt8](repeating: 0, count: 8 - e.ext.count)
        let step: Int?
        if e.arg == Int(noForecast) { step = nil }
        else if (0...4).contains(e.arg) { step = e.arg }
        else { BandEventDiagnostics.shared.unknownArg(type: eventType, arg: e.arg); return nil }
        let dot = step == nil ? 0 : max(-10, min(10, Int(Int8(bitPattern: x[0]))))
        return BandGauge(step: step, dot: dot, why: Int(x[1]), reminder: Int(x[2]), forecastC: LadderEvent.c100(x[3], x[4]))
    }

    /// (arg, x) laid out exactly like the band's hg_ga_frame (tests + demo; checked against the fw vectors).
    var encoded: (arg: Int, x: [UInt8]) {
        let f = LadderEvent.i16(forecastC)
        let d = step == nil ? 0 : max(-10, min(10, dot))
        return (step ?? Int(BandGauge.noForecast),
                [UInt8(bitPattern: Int8(d)), UInt8(truncatingIfNeeded: why), UInt8(truncatingIfNeeded: reminder),
                 UInt8(f & 255), UInt8(f >> 8), 0, 0, 0])
    }
}

extension BandEvent {
    /// The 0.9.18 GAUGE live frame (nil for other types).
    var gauge: BandGauge? { BandGauge.decode(self) }
}
