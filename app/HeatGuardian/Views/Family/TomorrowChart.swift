// Swift Charts: her indoor °C by hour (area + line), 28 °C and 30 °C soft bands, safe hours as a teal band,
// planned nudges as small SF Symbol markers on the curve (DESIGN.md §5 TOMORROW). All x values are Double hours.

import Charts
import SwiftUI

struct TomorrowChart: View {
    @ObservedObject var vm: TomorrowViewModel
    var L: Strings

    private var lo: Double { vm.yDomain.lowerBound }
    private var hi: Double { vm.yDomain.upperBound }

    var body: some View {
        Chart {
            bands
            safe
            curve
            markers
        }
        .chartXScale(domain: 0.0...24.0)
        .chartYScale(domain: lo...hi)
        .chartXAxis {
            AxisMarks(values: [0.0, 6.0, 12.0, 18.0, 24.0]) { v in
                AxisGridLine()
                AxisValueLabel {
                    if let h = v.as(Double.self) { Text(String(format: "%02d", Int(h) % 24)) }
                }
            }
        }
        .chartYAxis {
            AxisMarks(position: .leading, values: .automatic(desiredCount: 4)) { v in
                AxisGridLine()
                AxisValueLabel {
                    if let t = v.as(Double.self) { Text("\(Int(t))°") }
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(L.uiIndoorA11y)
        .accessibilityValue(a11ySummary)
    }

    /// 28–30 °C warm band and >= 30 °C hot band.
    @ChartContentBuilder
    private var bands: some ChartContent {
        RectangleMark(xStart: .value(L.uiHourAxis, 0.0), xEnd: .value(L.uiHourAxis, 24.0),
                      yStart: .value("°C", max(lo, TomorrowViewModel.warmC)), yEnd: .value("°C", max(lo, min(hi, TomorrowViewModel.hotC))))
            .foregroundStyle(Palette.heat.opacity(0.10))
        RectangleMark(xStart: .value(L.uiHourAxis, 0.0), xEnd: .value(L.uiHourAxis, 24.0),
                      yStart: .value("°C", max(lo, min(hi, TomorrowViewModel.hotC))), yEnd: .value("°C", hi))
            .foregroundStyle(Palette.danger.opacity(0.10))
    }

    @ChartContentBuilder
    private var safe: some ChartContent {
        ForEach(Array(vm.safeHours.enumerated()), id: \.offset) { _, r in
            RectangleMark(xStart: .value(L.uiHourAxis, Double(r.lowerBound)), xEnd: .value(L.uiHourAxis, Double(r.upperBound + 1)),
                          yStart: .value("°C", lo), yEnd: .value("°C", hi))
                .foregroundStyle(Palette.health.opacity(0.16))
        }
    }

    @ChartContentBuilder
    private var curve: some ChartContent {
        ForEach(vm.hours) { h in
            AreaMark(x: .value(L.uiHourAxis, Double(h.hour)), yStart: .value("°C", lo), yEnd: .value("°C", h.tIn))
                .interpolationMethod(.catmullRom)
                .foregroundStyle(LinearGradient(colors: [Palette.heat.opacity(0.28), Palette.heat.opacity(0.02)],
                                                startPoint: .top, endPoint: .bottom))
        }
        ForEach(vm.hours) { h in
            LineMark(x: .value(L.uiHourAxis, Double(h.hour)), y: .value("°C", h.tIn))
                .interpolationMethod(.catmullRom)
                .lineStyle(StrokeStyle(lineWidth: 2.5, lineCap: .round))
                .foregroundStyle(Palette.textPrimary)
        }
    }

    @ChartContentBuilder
    private var markers: some ChartContent {
        ForEach(vm.nudges) { n in
            PointMark(x: .value(L.uiHourAxis, n.hourValue), y: .value("°C", n.tInAtTime ?? lo))
                .symbol {
                    Image(systemName: n.symbol)
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(n.tone.color)
                        .padding(4)
                        .background(Palette.surface, in: Circle())
                }
        }
    }

    private var a11ySummary: String {
        let peak = vm.hours.max(by: { $0.tIn < $1.tIn })
        let p = peak.map { String(format: "%02d:00 %.0f°", $0.hour, $0.tIn) } ?? ""
        return p + (vm.safeText.isEmpty ? "" : " · " + L.uiSafeBand + " " + vm.safeText)
    }
}
