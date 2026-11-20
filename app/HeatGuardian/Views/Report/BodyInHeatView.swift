// Family · History › «Her body in heat» (Foivos, Nov 18): the health track of her body in heat, the same model the
// doctor's PDF draws (HeatReport from HeatReportBuilder): her heat reaction in plain words with confidence, wrist skin
// temperature next to the air and humidity, heart response to heat with her baseline, recovery after each episode,
// the alerts with what the sensors showed, sleep and movement on hot vs normal days. Native Swift Charts (SpecChart),
// glass cards over the state's colour field (DESIGN.md §2, §5). Demo data says SIMULATION.

import SwiftUI
import Charts

struct BodyInHeatView: View {
    @EnvironmentObject var m: AppModel
    var field: FieldState = .ok

    var body: some View {
        let L = m.L
        ScrollView {
            LazyVStack(alignment: .leading, spacing: Palette.s12) {
                Text(L.bhScreenSub).font(.subheadline).foregroundStyle(Palette.textOnField)
                if m.isDemo { SimBadge(text: L.sim) }
                if m.reportHasData(days: 14) {
                    let r = m.makeReport(days: 14, includeName: false, lang: m.lang)
                    card { SummaryLines(lines: r.summary, title: L.bhSummaryTitle) }
                    ForEach(["skin_days", "skin_24h", "rh_days", "hr_scatter", "hr_rest", "recovery", "sleep", "activity", "twin"], id: \.self) { id in
                        if let c = r.chart(id) { card { SpecChart(spec: c) } }
                    }
                    card { AlertRowsView(table: r.alerts, title: L.bhPageAlerts) }
                    NavigationLink { ReportView() } label: {
                        Label(L.rpTitle, systemImage: "doc.text").font(.body.weight(.semibold))
                            .frame(maxWidth: .infinity, minHeight: 44)
                    }
                    .buttonStyle(.glass)
                    Text(r.t["disclaimer_en"] ?? "").font(.footnote).foregroundStyle(Palette.textOnField)
                } else {
                    Text(L.rpNoData).font(.body).foregroundStyle(Palette.textOnField)
                }
            }
            .padding(.horizontal, 20)
            .padding(.bottom, Palette.s32)
        }
        .scrollIndicators(.hidden)
        .background { StateField(state: field) }
        .navigationTitle(L.bhScreenTitle)
        .navigationBarTitleDisplayMode(.inline)
    }

    private func card<C: View>(@ViewBuilder _ c: () -> C) -> some View {
        c().padding(20).frame(maxWidth: .infinity, alignment: .leading).hgCard()
    }
}

/// Her heat reaction in plain words; each line with how sure it is.
struct SummaryLines: View {
    var lines: [HeatReport.Line]
    var title: String
    var body: some View {
        VStack(alignment: .leading, spacing: Palette.s12) {
            Text(title).font(.headline).foregroundStyle(Palette.textPrimary).accessibilityAddTraits(.isHeader)
            ForEach(Array(lines.enumerated()), id: \.offset) { _, l in
                VStack(alignment: .leading, spacing: Palette.s4) {
                    Text(l.text).font(.body).foregroundStyle(Palette.textPrimary).fixedSize(horizontal: false, vertical: true)
                    if let c = l.conf { Text(c).font(.footnote.weight(.semibold)).foregroundStyle(Palette.textOnField) }
                }
                .accessibilityElement(children: .combine)
            }
        }
    }
}

/// The alerts table as quiet rows (phone width): when + alert, the sensors, what she did, recovery.
struct AlertRowsView: View {
    var table: TableSpec
    var title: String
    var body: some View {
        VStack(alignment: .leading, spacing: Palette.s12) {
            Text(title).font(.headline).foregroundStyle(Palette.textPrimary).accessibilityAddTraits(.isHeader)
            ForEach(Array(table.rows.enumerated().reversed()), id: \.offset) { _, row in
                VStack(alignment: .leading, spacing: 2) {
                    Text(row[0] + " · " + row[1]).font(.subheadline.weight(.semibold)).foregroundStyle(Palette.textPrimary)
                    Text(zip(table.cols.dropFirst(2).prefix(4), row.dropFirst(2).prefix(4)).map { $0.0.label + " " + $0.1 }.joined(separator: " · "))
                        .font(.footnote.monospacedDigit()).foregroundStyle(Palette.textOnField)
                    Text(row[6]).font(.footnote).foregroundStyle(Palette.textPrimary)
                    Text(table.cols[7].label + " " + row[7]).font(.footnote).foregroundStyle(Palette.textOnField)
                }
                .accessibilityElement(children: .combine)
            }
            if let n = table.note { Text(n).font(.footnote).foregroundStyle(Palette.textOnField) }
        }
    }
}

/// One ChartSpec drawn with Swift Charts — the same spec the PDF and the Linux mirror draw.
struct SpecChart: View {
    var spec: ChartSpec

    struct Mk: Identifiable {
        var id: Int
        var kind: String
        var series: String
        var color: Color
        var x: Double, y: Double, y2: Double
    }

    static func color(_ name: String) -> Color { Color(uiColor: HeatReportPDF.color(name)) }
    static let band: [Color] = HeatReportPDF.band.map { Color(uiColor: HeatReportPDF.hex($0)) }

    private var marks: [Mk] {
        var out: [Mk] = []
        let hw = spec.barWidth / 2
        for (si, se) in spec.series.enumerated() {
            let c = SpecChart.color(se.color)
            for p in se.pts {
                let id = si * 100_000 + out.count
                switch se.kind {
                case "rule": if let y = p.first { out.append(Mk(id: id, kind: "rule", series: se.name, color: SpecChart.color("text2"), x: 0, y: y, y2: y)) }
                case "range": if p.count >= 3 { out.append(Mk(id: id, kind: "rect", series: se.name, color: c, x: p[0] - hw, y: min(p[1], p[2]), y2: max(p[1], p[2]))) }
                case "bars": if p.count >= 2 { out.append(Mk(id: id, kind: "rect", series: se.name, color: c, x: p[0] - hw, y: spec.yMin, y2: p[1])) }
                case "stack":
                    var acc = 0.0
                    for (i, v) in p.dropFirst().enumerated() where v > 0 {
                        out.append(Mk(id: id + i, kind: "rect", series: se.name, color: SpecChart.band[min(i, 3)], x: p[0] - hw, y: acc, y2: acc + v))
                        acc += v
                    }
                default: if p.count >= 2 { out.append(Mk(id: id, kind: se.kind, series: se.name, color: c, x: p[0], y: p[1], y2: p[1])) }
                }
            }
        }
        return out
    }

    private func label(_ ticks: [ChartSpec.Tick], _ v: Double) -> String {
        ticks.min { abs($0.v - v) < abs($1.v - v) }?.label ?? ""
    }

    var body: some View {
        let w = spec.barWidth
        VStack(alignment: .leading, spacing: Palette.s8) {
            Text(spec.title).font(.subheadline.weight(.semibold)).foregroundStyle(Palette.textPrimary).accessibilityAddTraits(.isHeader)
            if let n = spec.note { Text(n).font(.footnote).foregroundStyle(Palette.textOnField).fixedSize(horizontal: false, vertical: true) }
            Chart {
                ForEach(marks) { mk in
                    if mk.kind == "rect" {
                        RectangleMark(xStart: .value("x0", mk.x), xEnd: .value("x1", mk.x + w), yStart: .value("y0", mk.y), yEnd: .value("y1", mk.y2))
                            .foregroundStyle(mk.color)
                            .cornerRadius(3)
                    } else if mk.kind == "rule" {
                        RuleMark(y: .value(mk.series, mk.y))
                            .foregroundStyle(mk.color)
                            .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 3]))
                    } else if mk.kind == "dots" {
                        PointMark(x: .value("x", mk.x), y: .value("y", mk.y))
                            .foregroundStyle(mk.color)
                            .symbolSize(18)
                    } else {
                        LineMark(x: .value("x", mk.x), y: .value("y", mk.y), series: .value("series", mk.series))
                            .foregroundStyle(mk.color)
                            .lineStyle(StrokeStyle(lineWidth: 2, dash: mk.kind == "dashed" ? [4, 3] : []))
                    }
                }
            }
            .chartXScale(domain: spec.xMin...spec.xMax)
            .chartYScale(domain: spec.yMin...spec.yMax)
            .chartXAxis {
                AxisMarks(values: spec.xTicks.map { $0.v }) { v in
                    AxisValueLabel { Text(label(spec.xTicks, v.as(Double.self) ?? 0)) }
                }
            }
            .chartYAxis {
                AxisMarks(position: .leading, values: spec.yTicks.map { $0.v }) { v in
                    AxisGridLine()
                    AxisValueLabel { Text(label(spec.yTicks, v.as(Double.self) ?? 0)) }
                }
            }
            .frame(height: max(140, CGFloat(spec.h) * 0.85))
            .accessibilityLabel(Text(spec.title))
            if spec.legend { legend }
        }
    }

    private var legend: some View {
        let items: [(String, String, Color)] = spec.series.filter { $0.kind != "rule" }.flatMap { se -> [(String, String, Color)] in
            se.kind == "stack" ? se.name.split(separator: "|").enumerated().map { (String($0.element), "rect", SpecChart.band[min($0.offset, 3)]) }
                               : [(se.name, se.kind, SpecChart.color(se.color))]
        }
        return VStack(alignment: .leading, spacing: 4) {
            ForEach(Array(items.enumerated()), id: \.offset) { _, it in
                HStack(spacing: 6) {
                    RoundedRectangle(cornerRadius: 2).fill(it.2).frame(width: 12, height: it.1 == "line" || it.1 == "dashed" ? 3 : 8)
                    Text(it.0).font(.footnote).foregroundStyle(Palette.textOnField)
                }
            }
        }
        .accessibilityHidden(true)
    }
}
