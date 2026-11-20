"""T4 — Greek strings: fit on the 240x280 ST7789 at 35-55 px (R3 §6.2), one action per message, provenance.

Two renderers:
  (a) the font the band firmware actually uses (07_all_parts.ino:155-159: u8g2_font_10x20_t_greek, monospace
      10x20 px) scaled x2 (20x40 px cell ~ 35-40 px glyphs) and x3 (30x60 px ~ 55 px glyphs);
  (b) DejaVu Sans Bold (proportional) at the font size whose capital-Η height is 35 px and 55 px, measured with PIL.
Word wrap at 224 px (8 px side margins). R3 §6.2 limit: <= 2 lines per message (6-8 Greek characters per line at 35-40 px).
Run: python3 /home/claude/hg_ai/tests/t4/t4_greek.py   -> out/greek.json
"""
import json
import os
import sys

from PIL import ImageFont

sys.path.insert(0, "/home/claude/hg_ai")
from tomorrow import advice_gr as A  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H, MARGIN = 240, 280, 8


def wrap(words, fits):
    lines, cur, overflow = [], "", False
    for w in words:
        t = (cur + " " + w).strip()
        if fits(t):
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
            if not fits(w):
                overflow = True
    if cur:
        lines.append(cur)
    return lines, overflow


def size_for_cap(px):
    for s in range(10, 200):
        f = ImageFont.truetype(FONT, s)
        b = f.getbbox("Η")
        if b[3] - b[1] >= px:
            return s, f


def measure(s):
    out = {"chars": len(s)}
    words = s.split()
    for scale, cell_w, cell_h in ((2, 20, 40), (3, 30, 60)):
        per = (W - 2 * MARGIN) // cell_w
        lines, ov = wrap(words, lambda t: len(t) <= per)
        out["mono_x%d" % scale] = {"lines": len(lines), "fits_screen": len(lines) * cell_h <= H and not ov,
                                   "word_overflow": ov, "r3_two_lines": len(lines) <= 2}
    for cap in (35, 55):
        size, f = size_for_cap(cap)
        lh = int(size * 1.2)
        lines, ov = wrap(words, lambda t: f.getlength(t) <= W - 2 * MARGIN)
        out["dejavu_cap%d" % cap] = {"font_px": size, "lines": len(lines), "fits_screen": len(lines) * lh <= H and not ov,
                                     "word_overflow": ov, "r3_two_lines": len(lines) <= 2,
                                     "widest_word_px": round(max(f.getlength(w) for w in words))}
    return out


def main():
    filled = {
        "SAFE_HOURS_T(1 range)": A.SAFE_HOURS_T.format(ranges="06:00–08:00"),
        "SAFE_HOURS_T(2 ranges)": A.SAFE_HOURS_T.format(ranges="05:00–07:00, 20:00–22:00"),
        "NIGHT_HEAT_T": A.NIGHT_HEAT_T.format(hh="22"),
        "HOUSE_WILL_REACH_T": A.HOUSE_WILL_REACH_T.format(t=39),
        "MOVE_ERRAND_T": A.MOVE_ERRAND_T.format(good="05:00", usual="10:00"),
    }
    strings = {n: getattr(A, n) for n in ("DRINK_NOW", "GO_COOLER_ROOM", "OPEN_WINDOWS_EVENING", "SHOWER_COMPRESS",
                                          "ARE_YOU_OK", "DRINK_PLENTY", "HEAT_DAY", "SAFE_HOURS_LABEL",
                                          "NO_SAFE_HOURS", "NIGHT_HEAT_CLOSED")}
    strings.update(filled)
    R = {}
    for n, s in strings.items():
        R[n] = {"text": s, **measure(s)}
    summary = {k: [n for n, r in R.items() if not r[k]["fits_screen"]] for k in ("mono_x2", "mono_x3", "dejavu_cap35", "dejavu_cap55")}
    summary.update({k + "_over_2_lines": [n for n, r in R.items() if not r[k]["r3_two_lines"]]
                    for k in ("mono_x2", "mono_x3", "dejavu_cap35", "dejavu_cap55")})
    # which plan-level strings are NOT in the sourced set (R3 §6.6 / ARCH §6)
    r3_band = ["Πιείτε νερό τώρα", "Πάτε σε πιο δροσερό δωμάτιο", "Ανοίξτε παράθυρα το βράδυ", "Χλιαρό ντους ή κρύα κομπρέσα",
               "Είστε καλά; Πατήστε το κουμπί", "Πίνετε άφθονα υγρά", "Ώρες για έξοδο: 06:00–08:00", "Αύριο: ημέρα καύσωνα",
               "Νύχτα ζεστή: ανοίξτε το παράθυρο μετά τις 22:00"]
    summary["not_verbatim_sourced"] = [n for n, s in strings.items() if s not in r3_band]
    R["_summary"] = summary
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    json.dump(R, open(os.path.join(HERE, "out", "greek.json"), "w"), indent=1, ensure_ascii=False)
    for n, r in R.items():
        if n == "_summary":
            continue
        print("%-24s %2d ch | mono x2 %d ln %s | mono x3 %d ln %s | DV35 %d ln %s | DV55 %d ln %s%s | %s" % (
            n, r["chars"], r["mono_x2"]["lines"], "ok" if r["mono_x2"]["fits_screen"] else "NO",
            r["mono_x3"]["lines"], "ok" if r["mono_x3"]["fits_screen"] else "NO",
            r["dejavu_cap35"]["lines"], "ok" if r["dejavu_cap35"]["fits_screen"] else "NO",
            r["dejavu_cap55"]["lines"], "ok" if r["dejavu_cap55"]["fits_screen"] else "NO",
            " (word overflow)" if r["dejavu_cap55"]["word_overflow"] else "", r["text"]))
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
