// «Her body in heat» — the health track (Foivos, Nov 18 rescope): what her wrist sensors showed in heat, computed on
// the phone from the ReportLedger day records (5-minute means) and the band's EVENTS. Pure Swift; used by the app
// screen (BodyInHeatView, Swift Charts) and by the PDF (HeatReportPDF / tools/report_mirror.py) through one model.
//
//  1. wrist SKIN temperature per day (min / mean / max) and a 24 h profile of the hottest day, next to the air at home,
//     the air outside and humidity — always called "wrist skin temperature", never body temperature;
//  2. heart response: her daytime pulse (hourly means 08-21 of quiet slots outside episodes) against the air, fitted as
//     pulse = a + b · max(0, air - 26 °C) (least squares) -> "≈ b bpm per °C above 26 °C", with her own baseline
//     (median daytime pulse in hours at <= 26 °C) and resting pulse;
//  3. recovery: after each heat episode, minutes from the episode's pulse / skin peak until back to what the air alone
//     explains for her (pulse <= fitted line + 5 bpm, skin <= expected + 0.3 °C, two 5-min slots in a row; 6 h max);
//  4. each alert with what the sensors showed, what she did and how fast she recovered;
//  5. sleep and movement on hot vs normal days;
//  6. her heat reaction in plain words, each with how sure it is (how much data it rests on).
// It is a record for a conversation with her doctor, not a diagnosis.

import Foundation

/// One heat episode: from the band's ALL_CLEAR (start = its time - its minutes) or grouped warnings without one.
struct EpisodeSpan: Equatable {
    var start: Date
    var end: Date?
    var clear: AllClear?
}

struct Fit: Equatable, Codable {
    var a: Double                 // pulse at <= 26 °C (intercept)
    var b: Double                 // bpm per °C above 26 °C
    var se: Double                // standard error of b
    var n: Int                    // hours used
    var nHot: Int                 // of them, above 26 °C
    var r2: Double
}

enum Confidence: String, Codable { case high, medium, low }

struct Recovery: Equatable, Codable {
    var at: Date
    var hrMin: Int?               // nil = not back within 6 h / no data
    var skinMin: Int?
    var peakHR: Int?
    var peakSkin: Double?
}

enum HeatBody {
    static let ref = 26.0                 // °C: strain barely changes below, rises above (Meade et al. 2024)
    static let hrBack = 5.0, skinBack = 0.3
    static let searchSlots = 72           // 6 h of 5-min slots
    static let dayFrom = 8, dayTo = 21    // daytime hours for the heart response

    /// Air around her in hour h of a record: home and out pooled (whichever she was in).
    static func airHour(_ r: DayRecord, _ h: Int) -> Double? {
        let rs = (h * 12)..<(h * 12 + 12)
        let n = rs.map { r.airHome5.n[$0] + r.airOut5.n[$0] }.reduce(0, +)
        guard n > 0 else { return nil }
        return rs.map { r.airHome5.sum[$0] + r.airOut5.sum[$0] }.reduce(0, +) / Double(n)
    }
    static func airSlot(_ r: DayRecord, _ s: Int) -> Double? {
        let n = r.airHome5.n[s] + r.airOut5.n[s]
        return n > 0 ? (r.airHome5.sum[s] + r.airOut5.sum[s]) / Double(n) : nil
    }

    static let quietMax = 20.0            // accel std (mg): above = moving; such slots are left out of the heart response

    /// Daytime hourly points (air, pulse, wrist skin) of all records: each hour averaged over its 5-min slots that were
    /// quiet (not moving) and outside heat episodes (`skip(day, slot)`), so the slope is the HEAT's, not walking's or an
    /// episode's. An hour needs >= 4 such slots.
    static func points(_ recs: [DayRecord], skip: (Int, Int) -> Bool = { _, _ in false }) -> [(air: Double, hr: Double, day: Int)] {
        hourly(recs, skip: skip).compactMap { p in p.hr.map { (p.air, $0, p.day) } }
    }

    static func hourly(_ recs: [DayRecord], skip: (Int, Int) -> Bool) -> [(air: Double, hr: Double?, skin: Double?, day: Int)] {
        var out: [(Double, Double?, Double?, Int)] = []
        for (i, r) in recs.enumerated() {
            for h in dayFrom..<dayTo {
                var a: [Double] = [], p: [Double] = [], k: [Double] = []
                for s in (h * 12)..<(h * 12 + 12) where !skip(i, s) {
                    if let m = r.act5.mean(s), m > quietMax { continue }
                    guard let air = airSlot(r, s) else { continue }
                    a.append(air)
                    if let v = r.hr5.mean(s) { p.append(v) }
                    if let v = r.skin5.mean(s) { k.append(v) }
                }
                guard a.count >= 4 else { continue }
                func mean(_ x: [Double]) -> Double? { x.count >= 4 ? x.reduce(0, +) / Double(x.count) : nil }
                out.append((a.reduce(0, +) / Double(a.count), mean(p), mean(k), i))
            }
        }
        return out
    }

    /// Wrist skin against air (plain least squares, skin = c + d · air) for the "expected skin" in recovery.
    static func skinLine(_ pts: [(air: Double, skin: Double)]) -> (c: Double, d: Double)? {
        guard pts.count >= 12 else { return nil }
        let n = Double(pts.count), mx = pts.map { $0.air }.reduce(0, +) / n, my = pts.map { $0.skin }.reduce(0, +) / n
        let sxx = pts.map { ($0.air - mx) * ($0.air - mx) }.reduce(0, +)
        guard sxx > 1e-9 else { return nil }
        let d = pts.map { ($0.air - mx) * ($0.skin - my) }.reduce(0, +) / sxx
        return (my - d * mx, d)
    }

    /// pulse = a + b · max(0, air - 26): ordinary least squares. nil with < 12 points or < 6 above 26 °C.
    static func fit(_ pts: [(air: Double, hr: Double, day: Int)]) -> Fit? {
        let xs = pts.map { max(0, $0.air - ref) }, ys = pts.map { $0.hr }
        let n = Double(xs.count), nHot = xs.filter { $0 > 0 }.count
        guard xs.count >= 12, nHot >= 6 else { return nil }
        let mx = xs.reduce(0, +) / n, my = ys.reduce(0, +) / n
        let sxx = zip(xs, xs).map { ($0 - mx) * ($1 - mx) }.reduce(0, +)
        guard sxx > 1e-9 else { return nil }
        let sxy = zip(xs, ys).map { ($0 - mx) * ($1 - my) }.reduce(0, +)
        let b = sxy / sxx, a = my - b * mx
        let sse = zip(xs, ys).map { (x: Double, y: Double) -> Double in let e = y - (a + b * x); return e * e }.reduce(0, +)
        let sst = ys.map { ($0 - my) * ($0 - my) }.reduce(0, +)
        let se = xs.count > 2 ? (sse / (n - 2) / sxx).squareRoot() : .infinity
        return Fit(a: a, b: b, se: se, n: xs.count, nHot: nHot, r2: sst > 0 ? 1 - sse / sst : 0)
    }

    static func confidence(_ f: Fit) -> Confidence {
        if f.nHot >= 40 && f.se * 4 <= abs(f.b) { return .high }
        if f.nHot >= 15 && f.se * 2 <= abs(f.b) { return .medium }
        return .low
    }
    static func confidence(episodes k: Int) -> Confidence { k >= 5 ? .high : (k >= 3 ? .medium : .low) }

    static func median(_ xs: [Double]) -> Double? {
        let s = xs.sorted()
        guard !s.isEmpty else { return nil }
        return s.count % 2 == 1 ? s[s.count / 2] : (s[s.count / 2 - 1] + s[s.count / 2]) / 2
    }

    /// Her normal daytime pulse and wrist skin: medians of the quiet daytime hours with air <= 26 °C.
    static func baselines(_ pts: [(air: Double, hr: Double?, skin: Double?, day: Int)]) -> (hr: Double?, skin: Double?) {
        let cool = pts.filter { $0.air <= ref }
        let hr = cool.compactMap { $0.hr }, sk = cool.compactMap { $0.skin }
        return (hr.count >= 6 ? median(hr) : nil, sk.count >= 6 ? median(sk) : nil)
    }

    /// Recovery after one episode (record of the day it started, its start / end as minutes of that day): minutes from
    /// the episode's peak until her pulse is back within 5 bpm of what the AIR alone explains for her (the fitted line,
    /// or her normal when there is no fit) and her wrist skin within 0.3 °C of its expected value for that air — two
    /// 5-min slots in a row, searched for 6 h.
    static func recovery(_ r: DayRecord, at: Date, from: Int, to: Int, hrExpect: (Double?) -> Double?, skinExpect: (Double?) -> Double?) -> Recovery {
        let s0 = max(0, from / 5), s1 = min(Series5.slots - 1, max(s0, to / 5))
        func peak(_ s: Series5) -> (Int, Double)? {
            (s0...s1).compactMap { i in s.mean(i).map { (i, $0) } }.max { $0.1 < $1.1 }
        }
        func back(_ s: Series5, from p: Int, margin: Double, expect: (Double?) -> Double?) -> Int? {
            var i = p + 1
            while i < min(Series5.slots - 1, p + searchSlots) {
                if let a = s.mean(i), let b = s.mean(i + 1), let ea = expect(airSlot(r, i)), let eb = expect(airSlot(r, i + 1)),
                   a <= ea + margin, b <= eb + margin { return (i - p) * 5 }
                i += 1
            }
            return nil
        }
        var rec = Recovery(at: at, hrMin: nil, skinMin: nil, peakHR: nil, peakSkin: nil)
        if let (p, v) = peak(r.hr5) {
            rec.peakHR = Int(v.rounded())
            if let e = hrExpect(airSlot(r, p)) { rec.hrMin = v <= e + hrBack ? 0 : back(r.hr5, from: p, margin: hrBack, expect: hrExpect) }
        }
        if let (p, v) = peak(r.skin5) {
            rec.peakSkin = (v * 10).rounded() / 10
            if let e = skinExpect(airSlot(r, p)) { rec.skinMin = v <= e + skinBack ? 0 : back(r.skin5, from: p, margin: skinBack, expect: skinExpect) }
        }
        return rec
    }

    /// A hot day for the hot-vs-normal comparison: >= 3 h at home in air >= 28 °C, or a hot night.
    static func isHot(_ r: DayRecord) -> Bool { r.hoursAtOrAbove(28, home: true) >= 3 || r.hotNight == true }
}
