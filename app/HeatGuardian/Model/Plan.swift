// Tomorrow Engine plan (tomorrow/plan.json, format "tomorrow-1"). Only the fields the app uses are decoded;
// everything else in the file is ignored. Optional fields keep the test-vector plans (h, t_in, rh_in, safe) decodable.

import Foundation

struct Plan: Codable, Equatable {
    struct Hour: Codable, Equatable {
        var h: Int
        var tOut: Double?
        var rhOut: Double?
        var tIn: Double
        var rhIn: Double
        var advice: String?   // "OK" | "SHORT" | "AVOID"
        var safe: Bool

        enum CodingKeys: String, CodingKey {
            case h, advice, safe
            case tOut = "t_out", rhOut = "rh_out", tIn = "t_in", rhIn = "rh_in"
        }
    }
    struct Ble: Codable, Equatable {
        var forecastChunksHex: [String]?
        var safeHoursHex: String?
        enum CodingKeys: String, CodingKey { case forecastChunksHex = "forecast_chunks_hex", safeHoursHex = "safe_hours_hex" }
    }

    var date: String
    var heatDay: Bool
    var nightHeat: Bool
    var waveDay: Int?
    var hours: [Hour]
    var adviceGr: [String]?
    var labels: [String]?
    var source: String?
    var attribution: String?
    var homeClass: String?
    var staleForecast: Bool?
    var ble: Ble?

    enum CodingKeys: String, CodingKey {
        case date, hours, labels, source, attribution, ble
        case heatDay = "heat_day", nightHeat = "night_heat", waveDay = "wave_day", adviceGr = "advice_gr"
        case homeClass = "home_class", staleForecast = "stale_forecast"
    }

    var isSimulation: Bool { (labels ?? []).contains("SIMULATION") }
    var isConstructedDemo: Bool { source == "CONSTRUCTED DEMO DAY" }

    /// "safe" = an OK hour in daylight (Tomorrow Engine); an OK hour at night is not offered as an outing hour.
    enum Slot: String { case ok = "OK", night = "NIGHT", short = "SHORT", avoid = "AVOID" }
    func slot(_ hr: Hour) -> Slot {
        if hr.safe { return .ok }
        if hr.advice == "OK" { return .night }
        if hr.advice == "SHORT" { return .short }
        return .avoid
    }

    /// Safe ranges as "HH:00–HH:00" (same rule as dashboard ranges()).
    func safeRanges() -> [String] {
        var out: [(Int, Int)] = []
        var s: Int? = nil
        for (i, h) in hours.enumerated() {
            if h.safe && s == nil { s = i }
            if (!h.safe || i == hours.count - 1), let st = s {
                let e = (h.safe && i == hours.count - 1) ? hours.count : i
                out.append((st, e))
                s = nil
            }
        }
        return out.map { String(format: "%02d:00–%02d:00", $0.0, $0.1) }
    }

    static func load(from data: Data) throws -> Plan { try JSONDecoder().decode(Plan.self, from: data) }

    static func bundled() -> Plan? {
        guard let url = Bundle.main.url(forResource: "plan", withExtension: "json"),
              let data = try? Data(contentsOf: url) else { return nil }
        return try? load(from: data)
    }
}
