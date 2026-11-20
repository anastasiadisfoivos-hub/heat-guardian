#!/usr/bin/env python3
"""Python mirror of HeatGuardian/Views/Report/HeatReportPDF.swift (the doctor's report, drawn on the phone with UIKit).
It draws the HeatReport MODEL JSON that the Swift builder makes (ReportTests.testWriteSampleJSON with HG_REPORT_JSON
set): the same blocks (cover, summary, chart, chart pair, table, …), the same generic chart and table drawing, the same
constants and order, so the numbers, words and charts are the app's own. Fonts differ: the phone uses SF Pro, this
mirror Liberation Sans (the Greek-capable sans on Linux).

    HG_REPORT_JSON=/tmp/report.json ios/tools/linux_xctest/run.sh
    python3 -I ios/tools/report_mirror.py /tmp/report.json out.pdf
"""
import json, sys
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor

# ---- layout constants (HeatReportPDF.swift)
PW, PH = 595.0, 842.0
M = 40.0
CW = PW - 2 * M
HEAD_Y = 34.0
BODY_Y = 66.0
FOOT_Y = PH - 26.0
BOTTOM = FOOT_Y - 16.0
TILE_H = 50.0
GAP = 8.0
PAIR_GAP = 16.0

C = dict(primary="#003F88", health="#13A89E", soft="#E3F1F8", text="#0B1B2B", text2="#5B6B7B", hair="#DCE4EC", heat="#F08A24",
         heatdark="#B4452A", water="#2F80ED", danger="#E5484D", zebra="#F2F6FA", page="#FFFFFF", simbg="#FDECEC", chipbg="#FFF1DC",
         chipink="#B4560A", skinband="#C9D6E3", twin="#B9A3D6", white="#FFFFFF")
BAND = ["#FBD9A6", "#F5A65B", "#E07B12", "#A8401E"]

FONT, BOLD = "HGSans", "HGSans-Bold"


def setup_fonts():
    pdfmetrics.registerFont(TTFont(FONT, "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"))
    pdfmetrics.registerFont(TTFont(BOLD, "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"))


def col(name): return C.get(name, name)


class Doc:
    """Top-left coordinates like UIKit (y grows down). dry=True lays out without drawing (counts the pages)."""

    def __init__(self, c, rep, dry, pages):
        self.c, self.r, self.t, self.dry, self.pages = c, rep, rep["t"], dry, pages
        self.page = 0
        self.y = BODY_Y

    def Y(self, y): return PH - y

    # ---- primitives
    def width(self, s, size, bold=False): return pdfmetrics.stringWidth(s, BOLD if bold else FONT, size)

    def text(self, x, y, s, size=9.5, bold=False, color="text", align="l"):
        if self.dry: return
        self.c.setFillColor(HexColor(col(color)))
        self.c.setFont(BOLD if bold else FONT, size)
        by = self.Y(y + size * 0.9)
        if align == "r": self.c.drawRightString(x, by, s)
        elif align == "c": self.c.drawCentredString(x, by, s)
        else: self.c.drawString(x, by, s)

    def wrap(self, s, size, w, bold=False):
        lines, cur = [], ""
        for word in s.split(" "):
            t = (cur + " " + word).strip()
            if self.width(t, size, bold) <= w or not cur: cur = t
            else: lines.append(cur); cur = word
        if cur: lines.append(cur)
        return lines

    def para(self, x, y, s, size=9.5, w=CW, bold=False, color="text", lead=1.32):
        for ln in self.wrap(s, size, w, bold):
            self.text(x, y, ln, size, bold, color)
            y += size * lead
        return y

    def rect(self, x, y, w, h, fill=None, stroke=None, r=0, lw=0.6):
        if self.dry or w <= 0 or h <= 0: return
        if fill: self.c.setFillColor(HexColor(col(fill)))
        if stroke: self.c.setStrokeColor(HexColor(col(stroke))); self.c.setLineWidth(lw)
        r = min(r, w / 2, h / 2)
        if r > 0: self.c.roundRect(x, self.Y(y + h), w, h, r, stroke=1 if stroke else 0, fill=1 if fill else 0)
        else: self.c.rect(x, self.Y(y + h), w, h, stroke=1 if stroke else 0, fill=1 if fill else 0)

    def line(self, x0, y0, x1, y1, color="hair", w=0.6, dash=None):
        if self.dry: return
        self.c.setStrokeColor(HexColor(col(color))); self.c.setLineWidth(w)
        self.c.setDash(dash or [])
        self.c.line(x0, self.Y(y0), x1, self.Y(y1))
        self.c.setDash([])

    def polyline(self, pts, color, w=1.6, dash=None):
        if self.dry or len(pts) < 2: return
        self.c.setStrokeColor(HexColor(col(color))); self.c.setLineWidth(w); self.c.setDash(dash or [])
        self.c.setLineJoin(1)
        p = self.c.beginPath()
        p.moveTo(pts[0][0], self.Y(pts[0][1]))
        for x, y in pts[1:]: p.lineTo(x, self.Y(y))
        self.c.drawPath(p, stroke=1, fill=0)
        self.c.setDash([])

    def dot(self, x, y, r, color):
        if self.dry: return
        self.c.setFillColor(HexColor(col(color))); self.c.circle(x, self.Y(y), r, stroke=0, fill=1)

    # ---- pages
    def begin_page(self):
        if self.page and not self.dry: self.c.showPage()
        self.page += 1
        self.y = BODY_Y
        r, t = self.r, self.t
        self.rect(0, 0, PW, PH, fill="page")
        self.text(M, HEAD_Y - 10, "HEAT GUARDIAN", 8, True, "primary")
        if r.get("name"): self.text(M + 92, HEAD_Y - 10, r["name"], 8, False, "text2")
        if r["simulated"]:
            w = self.width(t["sim"], 8, True) + 14
            self.rect(PW - M - w, HEAD_Y - 14, w, 15, fill="danger", r=7.5)
            self.text(PW - M - w / 2, HEAD_Y - 11, t["sim"], 8, True, "white", "c")
        self.line(M, HEAD_Y + 6, PW - M, HEAD_Y + 6)
        self.line(M, FOOT_Y - 8, PW - M, FOOT_Y - 8)
        self.text(M, FOOT_Y - 2, t["footer"] + (" · " + t["sim"] if r["simulated"] else ""), 7.5, False, "text2")
        self.text(PW - M, FOOT_Y - 2, "%s %d / %d" % (t["page"], self.page, self.pages), 7.5, False, "text2", "r")

    def need(self, h):
        if self.y + h > BOTTOM: self.begin_page()

    # ---- blocks
    def draw(self):
        self.begin_page()
        for b in self.r["blocks"]:
            getattr(self, "b_" + b["kind"])(b)

    def b_break(self, b): self.begin_page()

    def b_heading(self, b):
        self.need(40)
        self.text(M, self.y, b["text"], 12.5, True)
        self.y += 21

    def b_para(self, b):
        lines = self.wrap(b["text"], 9.5, CW)
        self.need(len(lines) * 12.5)
        self.y = self.para(M, self.y, b["text"], 9.5) + 6

    def b_note(self, b):
        self.y = self.para(M, self.y, b["text"], 8, CW, False, "text2") + 10

    def b_twinwarn(self, b):
        lines = self.wrap(b["text"], 9, CW - 24, True)
        h = 12 + len(lines) * 12
        self.need(h + 8)
        self.rect(M, self.y, CW, h, fill="simbg", stroke="danger", r=6, lw=0.8)
        yy = self.y + 6
        for ln in lines: self.text(M + 12, yy, ln, 9, True, "danger"); yy += 12
        self.y += h + 8

    def b_cover(self, b):
        r, t = self.r, self.t
        self.text(M, self.y, t["title"], 22, True); self.y += 34
        for k, v in ((t["name"], r.get("name")), (t["period"], r["periodText"]), (t["generated"], r["generatedText"])):
            if not v: continue
            self.text(M, self.y, k, 9.5, False, "text2"); self.text(M + 80, self.y, v, 9.5, True); self.y += 14.5
        self.y += 6
        self.rect(M, self.y, CW, 50, fill="soft", r=8)                     # Greek AND English, always
        self.text(M + 12, self.y + 10, t["disclaimer_el"], 9.5, True, "primary")
        self.text(M + 12, self.y + 27, t["disclaimer_en"], 9.5, True, "primary")
        self.y += 56
        self.y = self.para(M, self.y, t["no_bodytemp"], 8.5, CW, False, "text2") + 4
        if r["simulated"]:
            self.rect(M, self.y, CW, 22, fill="simbg", stroke="danger", r=6, lw=0.8)
            self.text(M + 12, self.y + 6, t["sim"] + " — " + t["sim_note"], 9, True, "danger")
            self.y += 30
        self.y += 6

    def b_summary(self, b):
        for ln in b["lines"]:
            lines = self.wrap(ln["text"], 10, CW - 18)
            self.need(len(lines) * 13.2 + 18)
            self.dot(M + 4, self.y + 6, 2.6, "primary")
            yy = self.para(M + 14, self.y, ln["text"], 10, CW - 18)
            if ln.get("conf"):
                w = self.width(ln["conf"], 7.6, True) + 12
                self.rect(M + 14, yy, w, 12.5, fill="zebra", r=6)
                self.text(M + 20, yy + 2.2, ln["conf"], 7.6, True, "text2")
                yy += 14
            self.y = yy + 6

    def b_figures(self, b):
        per = 4; tw = (CW - (per - 1) * GAP) / per
        figs = b["figures"]
        rows = (len(figs) + per - 1) // per
        self.need(rows * (TILE_H + GAP))
        for i, f in enumerate(figs):
            cx = M + (i % per) * (tw + GAP); cy = self.y + (i // per) * (TILE_H + GAP)
            self.rect(cx, cy, tw, TILE_H, fill="zebra", r=7)
            self.text(cx + 10, cy + 8, f["value"], 17, True)
            for j, ln in enumerate(self.wrap(f["label"], 7.8, tw - 20)[:2]):
                self.text(cx + 10, cy + 29 + j * 9.5, ln, 7.8, False, "text2")
        self.y += rows * (TILE_H + GAP) + 8

    def b_chart(self, b):
        h = b["chart"]["h"]
        self.need(h + 10)
        self.chart(b["chart"], M, self.y, CW, h)
        self.y += h + 14

    def b_pair(self, b):
        h = max(b["chart"]["h"], (b.get("chart2") or {}).get("h", 0))
        self.need(h + 10)
        w = (CW - PAIR_GAP) / 2
        self.chart(b["chart"], M, self.y, w, h)
        if b.get("chart2"): self.chart(b["chart2"], M + w + PAIR_GAP, self.y, w, h)
        self.y += h + 14

    def b_questions(self, b):
        for i, q in enumerate(b["items"]):
            self.need(len(self.wrap(q, 10, CW - 18)) * 13.2 + 4)
            self.text(M, self.y, "%d." % (i + 1), 10, True, "primary")
            self.y = self.para(M + 18, self.y, q, 10, CW - 18) + 4

    def b_meds(self, b):
        t = self.t
        if not b["meds"]:
            self.y = self.para(M, self.y, t["meds_none"], 9.5, CW, False, "text2") + 6
        for m in b["meds"]:
            self.need(30)
            self.text(M, self.y, m["name"], 10, True)
            x = M + self.width(m["name"], 10, True) + 8
            if m.get("cls"):
                self.text(x, self.y + 0.5, m["cls"], 9, False, "text2"); x += self.width(m["cls"], 9) + 8
            if m["flagged"]:
                w = self.width(t["meds_flag"], 8, True) + 14
                self.rect(x, self.y - 2, w, 14, fill="chipbg", r=7)
                self.text(x + 7, self.y + 1, t["meds_flag"], 8, True, "chipink")
            self.y += 15
            if m["guessed"]:
                self.text(M + 12, self.y - 2, t["meds_guess"], 7.8, False, "text2"); self.y += 11
            self.y += 2
        self.y += 8

    def b_privacy(self, b):
        t = self.t
        lines = self.wrap(t["privacy_text"], 8.8, CW - 24)
        h = 30 + len(lines) * 8.8 * 1.35
        self.need(h)
        self.rect(M, self.y, CW, h, fill="soft", r=8)
        self.text(M + 12, self.y + 10, t["privacy"], 10, True, "primary")
        yy = self.y + 28
        for ln in lines: self.text(M + 12, yy, ln, 8.8); yy += 8.8 * 1.35
        self.y += h + 8

    # ---- generic table (wrapping cells)
    def b_table(self, b):
        tb = b["table"]
        cols = tb["cols"]
        scale = CW / sum(c["w"] for c in cols)
        ws = [c["w"] * scale for c in cols]
        many = len(tb["rows"]) > 16
        fs = 7.0 if many else 7.6
        lead = fs * 1.25

        def tx(x, w, al): return x + w - 2 if al == "r" else (x + w / 2 if al == "c" else x + 2)

        def header():
            x = M
            hl = 1
            for c, w in zip(cols, ws):
                ls = self.wrap(c["label"], 6.8, w - 4, True)[:2]
                hl = max(hl, len(ls))
                for j, ln in enumerate(ls): self.text(tx(x, w, c["align"]), self.y + j * 8, ln, 6.8, True, "text2", c["align"])
                x += w
            self.y += 8 * hl + 4
            self.line(M, self.y - 2, M + CW, self.y - 2, "text2", 0.6)

        self.need(60)
        header()
        for i, row in enumerate(tb["rows"]):
            cells = [self.wrap(v, fs, w - 6) for v, w in zip(row, ws)]
            rh = max(11.5 if many else 13.0, max(len(c) for c in cells) * lead + 3)
            if self.y + rh > BOTTOM:
                self.begin_page(); header()
            if i % 2 == 1: self.rect(M, self.y - 1, CW, rh, fill="zebra")
            x = M
            for k, (c, w, lines) in enumerate(zip(cols, ws, cells)):
                px = tx(x, w, c["align"])
                if tb.get("dotCol") == k and tb["dots"][i]:
                    self.dot(x + 4, self.y + min(rh, 13) / 2 - 1, 2.6, tb["dots"][i]); px += 6
                bold = tb.get("boldCol") == k and tb["bold"][i]
                for j, ln in enumerate(lines):
                    self.text(px, self.y + 1.5 + j * lead, ln, fs, bold, "text", c["align"])
                x += w
            self.y += rh
        self.line(M, self.y, M + CW, self.y)
        self.y += 6
        if tb.get("note"):
            self.y = self.para(M, self.y, tb["note"], 7.4, CW, False, "text2", 1.3) + 10

    # ---- generic chart (ChartSpec)
    def chart(self, s, x, y, w, h):
        yy = self.para(x, y, s["title"], 9.5, w, True, "text", 1.25)
        if s.get("note"): yy = self.para(x, yy + 1, s["note"], 7.2, w, False, "text2", 1.28)
        legend = [se for se in s["series"] if se["kind"] != "rule"] if s.get("legend", True) else []
        stack = [se for se in s["series"] if se["kind"] == "stack"]
        if legend:
            lx, ly = x, yy + 3
            items = []
            for se in legend:
                if se["kind"] == "stack":
                    for i, nm in enumerate(se["name"].split("|")): items.append((nm, "stack", BAND[i]))
                else: items.append((se["name"], se["kind"], se["color"]))
            for nm, kind, cl in items:
                iw = 16 + self.width(nm, 7.2) + 12
                if lx + iw > x + w: lx = x; ly += 11
                self.legend_swatch(lx, ly + 4, kind, cl)
                self.text(lx + 16, ly, nm, 7.2, False, "text2")
                lx += iw
            yy = ly + 13
        top = yy + 6; base = y + h - 14; ph = base - top
        ax = x + 30; aw = w - 32
        X = lambda v: ax + aw * (v - s["xMin"]) / (s["xMax"] - s["xMin"])
        Yv = lambda v: base - ph * (v - s["yMin"]) / (s["yMax"] - s["yMin"])
        for tk in s["yTicks"]:
            self.line(ax, Yv(tk["v"]), ax + aw, Yv(tk["v"]), "hair", 0.5)
            self.text(ax - 4, Yv(tk["v"]) - 4, tk["label"], 6.8, False, "text2", "r")
        for tk in s["xTicks"]:
            self.text(X(tk["v"]), base + 3, tk["label"], 6.8, False, "text2", "c")
        bw = aw * s.get("barWidth", 0.6) / (s["xMax"] - s["xMin"])
        for se in s["series"]:
            k, cl, pts = se["kind"], se["color"], se["pts"]
            if k == "rule":
                for p in pts:
                    self.line(ax, Yv(p[0]), ax + aw, Yv(p[0]), "text2", 1.0, [3, 3])
                    self.text(ax + aw, Yv(p[0]) - 10, se["name"], 7, False, "text2", "r")
            elif k in ("line", "dashed"):
                self.polyline([(X(p[0]), Yv(p[1])) for p in pts], cl, 1.8, [4, 3] if k == "dashed" else None)
                if len(pts) <= 31:
                    for p in pts: self.dot(X(p[0]), Yv(p[1]), 2.0, cl)
            elif k == "dots":
                for p in pts: self.dot(X(p[0]), Yv(p[1]), 2.1 if len(pts) > 60 else 2.6, cl)
            elif k == "bars":
                for p in pts:
                    if p[1] <= 0: continue
                    self.rect(X(p[0]) - bw / 2, Yv(p[1]), bw, Yv(s["yMin"]) - Yv(p[1]), fill=cl, r=min(3, bw / 2))
            elif k == "range":
                for p in pts:
                    a, b2 = Yv(max(p[1], p[2])), Yv(min(p[1], p[2]))
                    self.rect(X(p[0]) - bw / 2, a, bw, b2 - a, fill=cl, r=min(4, bw / 2))
            elif k == "stack":
                for p in pts:
                    acc = 0.0
                    for i, v in enumerate(p[1:]):
                        if v <= 0: continue
                        y0 = Yv(acc + v); hh = Yv(acc) - y0
                        g = 1 if acc > 0 else 0                       # 2 px surface gap between stacked fills
                        self.rect(X(p[0]) - bw / 2, y0, bw, max(0.5, hh - g), fill=BAND[i])
                        acc += v

    def legend_swatch(self, x, y, kind, color):
        if kind in ("line", "dashed"): self.line(x, y, x + 12, y, color, 2, [3, 2] if kind == "dashed" else None)
        elif kind == "dots": self.dot(x + 6, y, 2.6, color)
        else: self.rect(x + 1, y - 4, 10, 8, fill=color, r=2)


def main():
    src, out = sys.argv[1], sys.argv[2]
    setup_fonts()
    rep = json.load(open(src, encoding="utf-8"))
    c = canvas.Canvas(out, pagesize=(PW, PH))
    dry = Doc(c, rep, True, 0); dry.draw()                      # pass 1: count the pages
    Doc(c, rep, False, dry.page).draw()
    c.setTitle(rep["t"]["title"]); c.setCreator("Heat Guardian (Linux mirror of the on-device PDF)")
    c.save()
    print("wrote", out, dry.page, "pages")


if __name__ == "__main__":
    main()
