// Draws the doctor's report (HeatReport model: blocks + generic ChartSpec / TableSpec) as an A4 PDF ON THE PHONE with
// UIGraphicsPDFRenderer — no server. ios/tools/report_mirror.py is a line-by-line Python mirror of this file (same
// constants, same block and chart drawing), used to render the sample PDF on Linux; keep the two in step. Every page
// carries the header, the footer ("not a medical device / not a diagnosis") and, in demo mode, the SIMULATION label.
// Two passes: the first lays out without drawing to count the pages ("Page n / N").

import Foundation
import UIKit

enum HeatReportPDF {
    // layout constants (report_mirror.py top)
    static let PW: CGFloat = 595, PH: CGFloat = 842, M: CGFloat = 40
    static var CW: CGFloat { PW - 2 * M }
    static let headY: CGFloat = 34, bodyY: CGFloat = 66
    static var footY: CGFloat { PH - 26 }
    static var bottom: CGFloat { footY - 16 }
    static let tileH: CGFloat = 50, gap: CGFloat = 8, pairGap: CGFloat = 16

    static func hex(_ v: UInt32) -> UIColor {
        UIColor(red: CGFloat((v >> 16) & 255) / 255, green: CGFloat((v >> 8) & 255) / 255, blue: CGFloat(v & 255) / 255, alpha: 1)
    }
    /// DESIGN.md palette F tokens on a white page (+ the print-only chart tokens).
    static let tokens: [String: UInt32] = [
        "primary": 0x003F88, "health": 0x13A89E, "soft": 0xE3F1F8, "text": 0x0B1B2B, "text2": 0x5B6B7B, "hair": 0xDCE4EC,
        "heat": 0xF08A24, "heatdark": 0xB4452A, "water": 0x2F80ED, "danger": 0xE5484D, "zebra": 0xF2F6FA, "page": 0xFFFFFF,
        "simbg": 0xFDECEC, "chipbg": 0xFFF1DC, "chipink": 0xB4560A, "skinband": 0xC9D6E3, "twin": 0xB9A3D6, "white": 0xFFFFFF]
    /// sequential warm ramp, light -> dark: 26-28, 28-30, 30-32, >= 32 °C
    static let band: [UInt32] = [0xFBD9A6, 0xF5A65B, 0xE07B12, 0xA8401E]
    static func color(_ name: String) -> UIColor { hex(tokens[name] ?? 0x0B1B2B) }

    /// The PDF bytes. Writes nothing to disk.
    static func render(_ r: HeatReport) -> Data {
        var dry = Drawer(r: r, dry: true, pages: 0, begin: {})
        dry.draw()
        let fmt = UIGraphicsPDFRendererFormat()
        fmt.documentInfo = [kCGPDFContextTitle as String: r.t["title"] ?? "Heat report",
                            kCGPDFContextCreator as String: "Heat Guardian (on-device)"]
        let ren = UIGraphicsPDFRenderer(bounds: CGRect(x: 0, y: 0, width: PW, height: PH), format: fmt)
        return ren.pdfData { ctx in
            var d = Drawer(r: r, dry: false, pages: dry.page, begin: { ctx.beginPage() })
            d.draw()
        }
    }

    /// A temporary file for the share sheet (complete file protection).
    static func file(_ r: HeatReport) throws -> URL {
        let name = (r.simulated ? "HeatGuardian-report-SIMULATION" : "HeatGuardian-report") + "-\(r.days)d.pdf"
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(name)
        try render(r).write(to: url, options: [.atomic, .completeFileProtection])
        return url
    }

    struct Drawer {
        let r: HeatReport
        let t: [String: String]
        let dry: Bool
        let pages: Int
        let begin: () -> Void
        var page = 0
        var y: CGFloat = HeatReportPDF.bodyY

        init(r: HeatReport, dry: Bool, pages: Int, begin: @escaping () -> Void) {
            self.r = r; self.t = r.t; self.dry = dry; self.pages = pages; self.begin = begin
        }
        func s(_ k: String) -> String { t[k] ?? k }

        // ---- primitives (top-left coordinates)
        func attrs(_ size: CGFloat, _ bold: Bool, _ c: String) -> [NSAttributedString.Key: Any] {
            [.font: UIFont.systemFont(ofSize: size, weight: bold ? .bold : .regular), .foregroundColor: HeatReportPDF.color(c)]
        }
        func width(_ str: String, _ size: CGFloat, _ bold: Bool = false) -> CGFloat {
            NSAttributedString(string: str, attributes: attrs(size, bold, "text")).size().width
        }
        func text(_ x: CGFloat, _ y: CGFloat, _ str: String, _ size: CGFloat = 9.5, _ bold: Bool = false, _ c: String = "text", _ al: String = "l") {
            guard !dry else { return }
            let a = NSAttributedString(string: str, attributes: attrs(size, bold, c))
            let w = a.size().width
            a.draw(at: CGPoint(x: al == "r" ? x - w : (al == "c" ? x - w / 2 : x), y: y))
        }
        func wrap(_ str: String, _ size: CGFloat, _ w: CGFloat, _ bold: Bool = false) -> [String] {
            var lines: [String] = [], cur = ""
            for word in str.split(separator: " ", omittingEmptySubsequences: false).map(String.init) {
                let tt = (cur + " " + word).trimmingCharacters(in: .whitespaces)
                if width(tt, size, bold) <= w || cur.isEmpty { cur = tt } else { lines.append(cur); cur = word }
            }
            if !cur.isEmpty { lines.append(cur) }
            return lines
        }
        func para(_ x: CGFloat, _ y: CGFloat, _ str: String, _ size: CGFloat = 9.5, _ w: CGFloat = HeatReportPDF.CW, _ bold: Bool = false,
                  _ c: String = "text", _ lead: CGFloat = 1.32) -> CGFloat {
            var y = y
            for ln in wrap(str, size, w, bold) { text(x, y, ln, size, bold, c); y += size * lead }
            return y
        }
        func rect(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat, fill: UIColor? = nil, stroke: UIColor? = nil, r: CGFloat = 0, lw: CGFloat = 0.6) {
            guard !dry, w > 0, h > 0 else { return }
            let rr = min(r, w / 2, h / 2)
            let p = rr > 0 ? UIBezierPath(roundedRect: CGRect(x: x, y: y, width: w, height: h), cornerRadius: rr)
                           : UIBezierPath(rect: CGRect(x: x, y: y, width: w, height: h))
            if let f = fill { f.setFill(); p.fill() }
            if let s = stroke { s.setStroke(); p.lineWidth = lw; p.stroke() }
        }
        func rect(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat, _ fill: String, r: CGFloat = 0) {
            rect(x, y, w, h, fill: HeatReportPDF.color(fill), r: r)
        }
        func line(_ x0: CGFloat, _ y0: CGFloat, _ x1: CGFloat, _ y1: CGFloat, _ c: String = "hair", _ w: CGFloat = 0.6, dash: [CGFloat]? = nil) {
            guard !dry else { return }
            let p = UIBezierPath()
            p.move(to: CGPoint(x: x0, y: y0)); p.addLine(to: CGPoint(x: x1, y: y1))
            p.lineWidth = w
            if let d = dash { p.setLineDash(d, count: d.count, phase: 0) }
            HeatReportPDF.color(c).setStroke(); p.stroke()
        }
        func polyline(_ pts: [CGPoint], _ c: String, _ w: CGFloat = 1.6, dash: [CGFloat]? = nil) {
            guard !dry, pts.count >= 2 else { return }
            let p = UIBezierPath()
            p.move(to: pts[0]); for q in pts.dropFirst() { p.addLine(to: q) }
            p.lineWidth = w; p.lineJoinStyle = .round
            if let d = dash { p.setLineDash(d, count: d.count, phase: 0) }
            HeatReportPDF.color(c).setStroke(); p.stroke()
        }
        func dot(_ x: CGFloat, _ y: CGFloat, _ rad: CGFloat, _ c: UIColor) {
            guard !dry else { return }
            c.setFill(); UIBezierPath(ovalIn: CGRect(x: x - rad, y: y - rad, width: 2 * rad, height: 2 * rad)).fill()
        }

        // ---- pages
        mutating func beginPage() {
            if !dry { begin() }
            page += 1
            y = bodyY
            rect(0, 0, PW, PH, "page")
            text(M, headY - 10, "HEAT GUARDIAN", 8, true, "primary")
            if let n = r.name { text(M + 92, headY - 10, n, 8, false, "text2") }
            if r.simulated {
                let w = width(s("sim"), 8, true) + 14
                rect(PW - M - w, headY - 14, w, 15, "danger", r: 7.5)
                text(PW - M - w / 2, headY - 11, s("sim"), 8, true, "white", "c")
            }
            line(M, headY + 6, PW - M, headY + 6)
            line(M, footY - 8, PW - M, footY - 8)
            text(M, footY - 2, s("footer") + (r.simulated ? " · " + s("sim") : ""), 7.5, false, "text2")
            text(PW - M, footY - 2, "\(s("page")) \(page) / \(pages)", 7.5, false, "text2", "r")
        }
        mutating func need(_ h: CGFloat) { if y + h > bottom { beginPage() } }

        // ---- blocks
        mutating func draw() {
            beginPage()
            for b in r.blocks {
                switch b.kind {
                case "break": beginPage()
                case "heading": need(40); text(M, y, b.text ?? "", 12.5, true); y += 21
                case "para":
                    need(CGFloat(wrap(b.text ?? "", 9.5, CW).count) * 12.5)
                    y = para(M, y, b.text ?? "", 9.5) + 6
                case "note": y = para(M, y, b.text ?? "", 8, CW, false, "text2") + 10
                case "twinwarn": twinWarn(b.text ?? "")
                case "cover": cover()
                case "summary": summary(b.lines ?? [])
                case "figures": figures(b.figures ?? [])
                case "chart":
                    if let c = b.chart { need(CGFloat(c.h) + 10); chart(c, M, y, CW, CGFloat(c.h)); y += CGFloat(c.h) + 14 }
                case "pair":
                    if let c = b.chart {
                        let h = CGFloat(max(c.h, b.chart2?.h ?? 0)), w = (CW - pairGap) / 2
                        need(h + 10)
                        chart(c, M, y, w, h)
                        if let c2 = b.chart2 { chart(c2, M + w + pairGap, y, w, h) }
                        y += h + 14
                    }
                case "table": if let tb = b.table { table(tb) }
                case "questions": questions(b.items ?? [])
                case "meds": meds(b.meds ?? [])
                case "privacy": privacy()
                default: break
                }
            }
        }

        mutating func twinWarn(_ str: String) {
            let lines = wrap(str, 9, CW - 24, true)
            let h = 12 + CGFloat(lines.count) * 12
            need(h + 8)
            rect(M, y, CW, h, fill: HeatReportPDF.color("simbg"), stroke: HeatReportPDF.color("danger"), r: 6, lw: 0.8)
            var yy = y + 6
            for ln in lines { text(M + 12, yy, ln, 9, true, "danger"); yy += 12 }
            y += h + 8
        }

        mutating func cover() {
            text(M, y, s("title"), 22, true); y += 34
            for (k, v) in [(s("name"), r.name), (s("period"), r.periodText), (s("generated"), r.generatedText)] {
                guard let v = v else { continue }
                text(M, y, k, 9.5, false, "text2"); text(M + 80, y, v, 9.5, true); y += 14.5
            }
            y += 6
            rect(M, y, CW, 50, "soft", r: 8)                         // Greek AND English, always
            text(M + 12, y + 10, s("disclaimer_el"), 9.5, true, "primary")
            text(M + 12, y + 27, s("disclaimer_en"), 9.5, true, "primary")
            y += 56
            y = para(M, y, s("no_bodytemp"), 8.5, CW, false, "text2") + 4
            if r.simulated {
                rect(M, y, CW, 22, fill: HeatReportPDF.color("simbg"), stroke: HeatReportPDF.color("danger"), r: 6, lw: 0.8)
                text(M + 12, y + 6, s("sim") + " — " + s("sim_note"), 9, true, "danger")
                y += 30
            }
            y += 6
        }

        mutating func summary(_ lines: [HeatReport.Line]) {
            for ln in lines {
                need(CGFloat(wrap(ln.text, 10, CW - 18).count) * 13.2 + 18)
                dot(M + 4, y + 6, 2.6, HeatReportPDF.color("primary"))
                var yy = para(M + 14, y, ln.text, 10, CW - 18)
                if let c = ln.conf {
                    let w = width(c, 7.6, true) + 12
                    rect(M + 14, yy, w, 12.5, "zebra", r: 6)
                    text(M + 20, yy + 2.2, c, 7.6, true, "text2")
                    yy += 14
                }
                y = yy + 6
            }
        }

        mutating func figures(_ figs: [HeatReport.Figure]) {
            let per = 4, tw = (CW - CGFloat(per - 1) * gap) / CGFloat(per)
            let rows = (figs.count + per - 1) / per
            need(CGFloat(rows) * (tileH + gap))
            for (i, f) in figs.enumerated() {
                let cx = M + CGFloat(i % per) * (tw + gap), cy = y + CGFloat(i / per) * (tileH + gap)
                rect(cx, cy, tw, tileH, "zebra", r: 7)
                text(cx + 10, cy + 8, f.value, 17, true)
                for (j, ln) in wrap(f.label, 7.8, tw - 20).prefix(2).enumerated() { text(cx + 10, cy + 29 + CGFloat(j) * 9.5, ln, 7.8, false, "text2") }
            }
            y += CGFloat(rows) * (tileH + gap) + 8
        }

        mutating func questions(_ qs: [String]) {
            for (i, q) in qs.enumerated() {
                need(CGFloat(wrap(q, 10, CW - 18).count) * 13.2 + 4)
                text(M, y, "\(i + 1).", 10, true, "primary")
                y = para(M + 18, y, q, 10, CW - 18) + 4
            }
        }

        mutating func meds(_ ms: [HeatReport.Med]) {
            if ms.isEmpty { y = para(M, y, s("meds_none"), 9.5, CW, false, "text2") + 6 }
            for m in ms {
                need(30)
                text(M, y, m.name, 10, true)
                var x = M + width(m.name, 10, true) + 8
                if let c = m.cls { text(x, y + 0.5, c, 9, false, "text2"); x += width(c, 9) + 8 }
                if m.flagged {
                    let w = width(s("meds_flag"), 8, true) + 14
                    rect(x, y - 2, w, 14, "chipbg", r: 7)
                    text(x + 7, y + 1, s("meds_flag"), 8, true, "chipink")
                }
                y += 15
                if m.guessed { text(M + 12, y - 2, s("meds_guess"), 7.8, false, "text2"); y += 11 }
                y += 2
            }
            y += 8
        }

        mutating func privacy() {
            let lines = wrap(s("privacy_text"), 8.8, CW - 24)
            let h = 30 + CGFloat(lines.count) * 8.8 * 1.35
            need(h)
            rect(M, y, CW, h, "soft", r: 8)
            text(M + 12, y + 10, s("privacy"), 10, true, "primary")
            var yy = y + 28
            for ln in lines { text(M + 12, yy, ln, 8.8); yy += 8.8 * 1.35 }
            y += h + 8
        }

        // ---- generic table (wrapping cells)
        mutating func table(_ tb: TableSpec) {
            let scale = CW / CGFloat(tb.cols.map { $0.w }.reduce(0, +))
            let ws = tb.cols.map { CGFloat($0.w) * scale }
            let many = tb.rows.count > 16
            let fs: CGFloat = many ? 7.0 : 7.6, lead = fs * 1.25
            func tx(_ x: CGFloat, _ w: CGFloat, _ al: String) -> CGFloat { al == "r" ? x + w - 2 : (al == "c" ? x + w / 2 : x + 2) }
            func header(_ d: inout Drawer) {
                var x = M, hl = 1
                for (c, w) in zip(tb.cols, ws) {
                    let ls = Array(d.wrap(c.label, 6.8, w - 4, true).prefix(2))
                    hl = max(hl, ls.count)
                    for (j, ln) in ls.enumerated() { d.text(tx(x, w, c.align), d.y + CGFloat(j) * 8, ln, 6.8, true, "text2", c.align) }
                    x += w
                }
                d.y += 8 * CGFloat(hl) + 4
                d.line(M, d.y - 2, M + CW, d.y - 2, "text2", 0.6)
            }
            need(60)
            header(&self)
            for (i, row) in tb.rows.enumerated() {
                let cells = zip(row, ws).map { wrap($0.0, fs, $0.1 - 6) }
                let rh = max(many ? 11.5 : 13.0, CGFloat(cells.map { $0.count }.max() ?? 1) * lead + 3)
                if y + rh > bottom { beginPage(); header(&self) }
                if i % 2 == 1 { rect(M, y - 1, CW, rh, "zebra") }
                var x = M
                for (k, (c, w)) in zip(tb.cols, ws).enumerated() {
                    var px = tx(x, w, c.align)
                    if tb.dotCol == k, i < tb.dots.count, let dc = tb.dots[i] { dot(x + 4, y + min(rh, 13) / 2 - 1, 2.6, HeatReportPDF.color(dc)); px += 6 }
                    let bold = tb.boldCol == k && i < tb.bold.count && tb.bold[i]
                    for (j, ln) in cells[k].enumerated() { text(px, y + 1.5 + CGFloat(j) * lead, ln, fs, bold, "text", c.align) }
                    x += w
                }
                y += rh
            }
            line(M, y, M + CW, y)
            y += 6
            if let n = tb.note { y = para(M, y, n, 7.4, CW, false, "text2", 1.3) + 10 }
        }

        // ---- generic chart (ChartSpec)
        func chart(_ s: ChartSpec, _ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat) {
            var yy = para(x, y, s.title, 9.5, w, true, "text", 1.25)
            if let n = s.note { yy = para(x, yy + 1, n, 7.2, w, false, "text2", 1.28) }
            if s.legend {
                var items: [(String, String, UIColor)] = []
                for se in s.series where se.kind != "rule" {
                    if se.kind == "stack" {
                        for (i, nm) in se.name.split(separator: "|").enumerated() { items.append((String(nm), "stack", HeatReportPDF.hex(band[min(i, 3)]))) }
                    } else { items.append((se.name, se.kind, HeatReportPDF.color(se.color))) }
                }
                if !items.isEmpty {
                    var lx = x, ly = yy + 3
                    for (nm, kind, cl) in items {
                        let iw = 16 + width(nm, 7.2) + 12
                        if lx + iw > x + w { lx = x; ly += 11 }
                        swatch(lx, ly + 4, kind, cl)
                        text(lx + 16, ly, nm, 7.2, false, "text2")
                        lx += iw
                    }
                    yy = ly + 13
                }
            }
            let top = yy + 6, base = y + h - 14, ph = base - top, ax = x + 30, aw = w - 32
            func X(_ v: Double) -> CGFloat { ax + aw * CGFloat((v - s.xMin) / (s.xMax - s.xMin)) }
            func Y(_ v: Double) -> CGFloat { base - ph * CGFloat((v - s.yMin) / (s.yMax - s.yMin)) }
            for tk in s.yTicks { line(ax, Y(tk.v), ax + aw, Y(tk.v), "hair", 0.5); text(ax - 4, Y(tk.v) - 4, tk.label, 6.8, false, "text2", "r") }
            for tk in s.xTicks { text(X(tk.v), base + 3, tk.label, 6.8, false, "text2", "c") }
            let bw = aw * CGFloat(s.barWidth / (s.xMax - s.xMin))
            for se in s.series {
                let cl = HeatReportPDF.color(se.color)
                switch se.kind {
                case "rule":
                    for p in se.pts where !p.isEmpty {
                        line(ax, Y(p[0]), ax + aw, Y(p[0]), "text2", 1, dash: [3, 3])
                        text(ax + aw, Y(p[0]) - 10, se.name, 7, false, "text2", "r")
                    }
                case "line", "dashed":
                    polyline(se.pts.filter { $0.count >= 2 }.map { CGPoint(x: X($0[0]), y: Y($0[1])) }, se.color, 1.8, dash: se.kind == "dashed" ? [4, 3] : nil)
                    if se.pts.count <= 31 { for p in se.pts where p.count >= 2 { dot(X(p[0]), Y(p[1]), 2.0, cl) } }
                case "dots":
                    for p in se.pts where p.count >= 2 { dot(X(p[0]), Y(p[1]), se.pts.count > 60 ? 2.1 : 2.6, cl) }
                case "bars":
                    for p in se.pts where p.count >= 2 && p[1] > 0 { rect(X(p[0]) - bw / 2, Y(p[1]), bw, Y(s.yMin) - Y(p[1]), fill: cl, r: min(3, bw / 2)) }
                case "range":
                    for p in se.pts where p.count >= 3 {
                        let a = Y(max(p[1], p[2])), b = Y(min(p[1], p[2]))
                        rect(X(p[0]) - bw / 2, a, bw, b - a, fill: cl, r: min(4, bw / 2))
                    }
                case "stack":
                    for p in se.pts where p.count >= 2 {
                        var acc = 0.0
                        for (i, v) in p.dropFirst().enumerated() where v > 0 {
                            let y0 = Y(acc + v), hh = Y(acc) - y0, g: CGFloat = acc > 0 ? 1 : 0   // 2 px surface gap between stacked fills
                            rect(X(p[0]) - bw / 2, y0, bw, max(0.5, hh - g), fill: HeatReportPDF.hex(band[min(i, 3)]))
                            acc += v
                        }
                    }
                default: break
                }
            }
        }

        func swatch(_ x: CGFloat, _ y: CGFloat, _ kind: String, _ c: UIColor) {
            guard !dry else { return }
            switch kind {
            case "line", "dashed":
                let p = UIBezierPath(); p.move(to: CGPoint(x: x, y: y)); p.addLine(to: CGPoint(x: x + 12, y: y)); p.lineWidth = 2
                if kind == "dashed" { p.setLineDash([3, 2], count: 2, phase: 0) }
                c.setStroke(); p.stroke()
            case "dots": dot(x + 6, y, 2.6, c)
            default: rect(x + 1, y - 4, 10, 8, fill: c, r: 2)
            }
        }
    }
}
