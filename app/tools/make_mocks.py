#!/usr/bin/env python3
"""HTML/CSS MOCKS of the SwiftUI screens (no iOS simulator here), rendered with Playwright to ios/shots/mock_*.png
at 390x844, DPR 2. Values come from the bundled replay decoded by mirror_frames.py (the Python mirror of
Frames.swift), the chart is drawn with the same rules as DayChart.swift, copy = Strings.swift (Greek).
These are mocks of the layout, not screenshots of the app.

    python3 -I ios/tools/make_mocks.py
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mirror_frames as M  # noqa: E402

IOS = os.path.dirname(HERE)
OUT = os.path.join(IOS, "shots")
RES = os.path.join(IOS, "HeatGuardian", "Resources")
R = json.load(open(os.path.join(RES, "sim_heatwave.json"), encoding="utf-8"))
PLAN = json.load(open(os.path.join(RES, "plan.json"), encoding="utf-8"))

COL = {"OK": "#29A885", "IMOK": "#29A885", "DRINK": "#F2A626", "COOL": "#F27329", "DANGER": "#E0333B", "CHECK": "#E0333B",
       "HELP": "#E0333B", "WAIT": "#5C85CC", "BATTERY": "#8C94A1", "NOT_WORN": "#8C94A1"}
SEV = {"DRINK": 2, "COOL": 3, "CHECK": 4, "DANGER": 4, "HELP": 4, "WAIT": 0}
STATE = {"OK": ("Όλα καλά", "Δεν χρειάζεται να κάνετε κάτι."),
         "DRINK": ("Πιείτε νερό", "Το βραχιόλι υπενθύμισε να πιει νερό."),
         "COOL": ("Πηγαίνετε σε δροσιά", "Το βραχιόλι ζήτησε να πάει σε πιο δροσερό χώρο. Ένα τηλεφώνημα βοηθά."),
         "DANGER": ("Κίνδυνος", "Πολύ υψηλή θερμική καταπόνηση. Τηλεφωνήστε τώρα.")}
# SF Symbol stand-ins (simple SVG paths, 24x24)
SYM = {
    "OK": '<path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>',
    "DRINK": '<path d="M12 3.2C9.2 7.2 6.5 10.3 6.5 14a5.5 5.5 0 0011 0c0-3.7-2.7-6.8-5.5-10.8z" fill="currentColor"/>',
    "COOL": '<path d="M3.5 11.5L12 4l8.5 7.5V20a1 1 0 01-1 1H15v-5.5H9V21H4.5a1 1 0 01-1-1z" fill="currentColor"/>',
    "DANGER": '<path d="M12 3.5L2.5 20h19z" fill="currentColor"/><rect x="11" y="9" width="2" height="6" rx="1" fill="#fff" opacity=".001"/><path d="M12 9.5v4.5" stroke="var(--hole)" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="17" r="1.25" fill="var(--hole)"/>',
}
ICON = {
    "heart": '<path d="M12 20s-7-4.4-7-10a4 4 0 017-2.6A4 4 0 0119 10c0 5.6-7 10-7 10z" fill="currentColor"/>',
    "hand": '<path d="M8 12V6.5a1.3 1.3 0 012.6 0V11m0-5.5V5a1.3 1.3 0 012.6 0v6m0-5a1.3 1.3 0 012.6 0v6m0-3.5a1.3 1.3 0 012.4.7V14c0 3.9-2.6 7-6.4 7S6 18.3 5 15.4L3.9 12.6a1.3 1.3 0 012.3-1.1L8 14" fill="currentColor"/>',
    "house": SYM["COOL"],
    "battery": '<rect x="2.5" y="7" width="17" height="10" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.6"/><rect x="4.5" y="9" width="10" height="6" rx="1" fill="currentColor"/><rect x="20.5" y="10" width="1.6" height="4" rx=".8" fill="currentColor"/>',
    "seal": '<circle cx="12" cy="12" r="9" fill="currentColor"/><path d="M8 12.3l2.7 2.7L16.3 9.4" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "thermo": '<path d="M10 4a2 2 0 014 0v9.3a4 4 0 11-4 0z" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="12" cy="16.5" r="2" fill="currentColor"/><path d="M12 9v6" stroke="currentColor" stroke-width="1.7"/>',
    "play": '<rect x="2.5" y="5" width="19" height="14" rx="3" fill="currentColor"/><path d="M10 9v6l5-3z" fill="#fff"/>',
    "pause": '<rect x="7" y="5" width="3.4" height="14" rx="1" fill="currentColor"/><rect x="13.6" y="5" width="3.4" height="14" rx="1" fill="currentColor"/>',
    "sliders": '<path d="M4 7h10M18 7h2M4 17h4M12 17h8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="16" cy="7" r="2.2" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="10" cy="17" r="2.2" fill="none" stroke="currentColor" stroke-width="1.8"/>',
    "phone": '<path d="M6.6 3.5l2.6.3 1.3 4-2 1.5a12 12 0 006.2 6.2l1.5-2 4 1.3.3 2.6c0 1-1 2-2.2 2A16.5 16.5 0 014.6 5.7c0-1.2 1-2.2 2-2.2z" fill="currentColor"/>',
    "check": SYM["OK"],
    "mute": '<path d="M4 9h3.5L12 5v14l-4.5-4H4z" fill="currentColor"/><path d="M15.5 9.5l5 5m0-5l-5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    "waves": '<path d="M12 7v10M8.5 9.5v5M15.5 9.5v5M5 11v2M19 11v2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    "tab_now": '<rect x="3" y="3" width="18" height="18" rx="5" fill="currentColor"/><path d="M12 16.5s-4-2.5-4-5.6a2.2 2.2 0 014-1.3 2.2 2.2 0 014 1.3c0 3.1-4 5.6-4 5.6z" fill="#fff"/>',
    "tab_sun": '<circle cx="12" cy="12" r="4.2" fill="currentColor"/><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    "tab_chart": '<rect x="4" y="12" width="3.6" height="8" rx="1" fill="currentColor"/><rect x="10.2" y="5" width="3.6" height="15" rx="1" fill="currentColor"/><rect x="16.4" y="9" width="3.6" height="11" rx="1" fill="currentColor"/>',
    "tab_gear": '<circle cx="12" cy="12" r="7.5" fill="none" stroke="currentColor" stroke-width="3" stroke-dasharray="3 2.4"/><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="2"/>',
    "radio": '<circle cx="12" cy="12" r="2" fill="currentColor"/><path d="M8 8a5.6 5.6 0 000 8M16 8a5.6 5.6 0 010 8M5.2 5.2a9.6 9.6 0 000 13.6M18.8 5.2a9.6 9.6 0 010 13.6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
}


def svg(body, size, color="currentColor"):
    return f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" style="color:{color}">{body}</svg>'


def gr(x):
    return ("%.1f" % x).replace(".", ",")


def frame(i):
    d = M.decode_status(list(bytes.fromhex(R["status"][i])))
    d["state"] = "NOT_WORN" if d["notWorn"] else M.STATE_NAMES[d["stateCode"]]
    return d


def clock(i):
    m = (R["start_mod"] + i) % 1440
    return "%02d:%02d" % (m // 60, m % 60)


CSS = """
:root{--bg:#F2F2F7;--card:#FFFFFF;--ink:#000;--ink2:rgba(60,60,67,.62);--fill:rgba(118,118,128,.12);--sep:rgba(60,60,67,.18);--hole:#fff;--tab:rgba(249,249,249,.94)}
.dark{--bg:#000;--card:#1C1C1E;--ink:#fff;--ink2:rgba(235,235,245,.62);--fill:rgba(118,118,128,.24);--sep:rgba(84,84,88,.6);--tab:rgba(22,22,24,.94)}
*{box-sizing:border-box;margin:0;padding:0}
body{width:390px;height:844px;overflow:hidden;background:var(--bg);color:var(--ink);font-family:Inter,"DejaVu Sans",sans-serif;-webkit-font-smoothing:antialiased;position:relative}
.status{height:47px;display:flex;align-items:flex-end;justify-content:space-between;padding:0 30px 6px 40px;font-weight:600;font-size:16px}
.nav{display:flex;justify-content:space-between;align-items:flex-end;padding:4px 16px 8px}
.nav h1{font-family:"Inter Display",Inter;font-size:34px;font-weight:700;letter-spacing:.2px}
.wrap{padding:0 16px}
.card{background:var(--card);border-radius:26px;padding:20px;margin-bottom:16px}
.tiles{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.tile{background:var(--card);border-radius:22px;padding:16px}
.tl{font-size:15px;font-weight:600;display:flex;gap:6px;align-items:center}
.tv{font-family:"Inter Display",Inter;font-size:34px;font-weight:600;margin-top:8px;font-variant-numeric:tabular-nums}
.tu{font-size:13px;color:var(--ink2);margin-top:6px}
.sec{font-size:15px;font-weight:600;color:var(--ink2);display:flex;align-items:center;gap:6px}
.sim{display:inline-flex;gap:5px;align-items:center;font-size:12px;font-weight:700;letter-spacing:.8px;color:#6B5CE6;background:rgba(107,92,230,.14);padding:5px 10px;border-radius:99px}
.tabbar{position:absolute;left:0;right:0;bottom:0;height:83px;background:var(--tab);border-top:.5px solid var(--sep);display:flex;justify-content:space-around;padding-top:7px;backdrop-filter:blur(20px)}
.tab{display:flex;flex-direction:column;align-items:center;gap:3px;font-size:10px;font-weight:500;color:#8E8E93;width:80px}
.tab.on{color:#29A885}
"""


def phone(body, dark=False, tab="now", title="Μαρία", clock_txt="13:35", scroll=0):
    tabs = [("now", "tab_now", "Τώρα"), ("tom", "tab_sun", "Αύριο"), ("week", "tab_chart", "Εβδομάδα"), ("set", "tab_gear", "Ρυθμίσεις")]
    tb = "".join(f'<div class="tab {"on" if k == tab else ""}">{svg(ICON[ic], 26)}<span>{lab}</span></div>' for k, ic, lab in tabs)
    nav = f'<div class="nav"><h1>{title}</h1>{svg(ICON["play"], 24, "#6B5CE6")}</div>' if title else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body class="{'dark' if dark else ''}"><div class="status"><span>{clock_txt}</span><span>●●●● ▮</span></div>{nav}
<div class="wrap" style="transform:translateY(-{scroll}px)">{body}</div><div class="tabbar">{tb}</div></body></html>"""


def chart(upto, dark):
    W, HC, GAP, HS = 284.0, 132.0, 12.0, 44.0
    y0, y1 = 36.0, 39.5
    X = lambda i: i / 1440.0 * W
    Y = lambda c: HC - (min(y1, max(y0, c)) - y0) / (y1 - y0) * HC
    pts = [frame(i) for i in range(upto + 1)]
    segs, cur = [], []
    for i, d in enumerate(pts):
        has = d["coreC"] > 0 and not d["notWorn"]
        if not has:
            if len(cur) > 1: segs.append(cur)
            cur = []
        else: cur.append((i, d))
    if len(cur) > 1: segs.append(cur)
    band = line = ""
    for s in segs:
        top = " ".join("%.1f,%.1f" % (X(i), Y(d["coreC"] + d["halfRangeC"])) for i, d in s)
        bot = " ".join("%.1f,%.1f" % (X(i), Y(d["coreC"] - d["halfRangeC"])) for i, d in reversed(s))
        band += f'<polygon points="{top} {bot}" fill="rgba(84,140,242,.22)"/>'
        line += '<polyline points="%s" fill="none" stroke="#548CF2" stroke-width="2" stroke-linejoin="round"/>' % " ".join("%.1f,%.1f" % (X(i), Y(d["coreC"])) for i, d in s)
    runs = []
    for i, d in enumerate(pts):
        vs = d["state"]
        if runs and runs[-1][2] == vs: runs[-1][1] = i
        else: runs.append([i, i, vs])
    stairs = ""
    for a, b, vs in runs:
        sev = max(1, SEV.get(vs, 1)); h = HS * (0.25 + 0.25 * (sev - 1))
        stairs += '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="%s"/>' % (X(a), HC + GAP + HS - h, max(X(b + 1) - X(a) - .5, 1), h, COL.get(vs, "#8C94A1"))
    fam = "".join('<rect x="%.1f" y="0" width="2" height="%.0f" fill="#E0333B"/>' % (X(i) - 1, HC + GAP + HS)
                  for i, d in enumerate(pts) if d["familyPending"] and (i == 0 or not pts[i - 1]["familyPending"]))
    grid = "".join('<line x1="0" x2="%.0f" y1="%.1f" y2="%.1f" stroke="var(--sep)" stroke-width=".5"/>' % (W, Y(c), Y(c)) for c in (37, 38, 39))
    ylab = "".join(f'<div style="position:absolute;left:0;top:{Y(c) - 7:.1f}px;font-size:11px;color:var(--ink2)">{c}°</div>' for c in (37, 38, 39))
    cursor = '<rect x="%.1f" y="0" width="1" height="%.0f" fill="var(--ink2)"/>' % (X(upto), HC + GAP + HS)
    ticks = "".join(f'<span style="position:absolute;left:{max(0, min(W - 36, X(h * 60) - 18)) + 30:.0f}px;font-size:11px;color:var(--ink2)">{h:02d}:00</span>' for h in (0, 6, 12, 18, 24))
    H = HC + GAP + HS
    leg = lambda c, t: f'<span style="display:inline-flex;align-items:center;gap:5px;font-size:11px;color:var(--ink2);margin-right:12px"><i style="width:12px;height:8px;border-radius:2px;background:{c};display:inline-block"></i>{t}</span>'
    return f"""<div style="position:relative;height:{H:.0f}px;margin-top:4px">{ylab}
<svg style="position:absolute;left:30px;top:0" width="{W:.0f}" height="{H:.0f}"><rect x="0" y="{HC + GAP:.0f}" width="{W:.0f}" height="{HS:.0f}" rx="6" fill="var(--fill)"/>{grid}{band}{line}{stairs}{fam}{cursor}</svg></div>
<div style="position:relative;height:16px;margin-top:6px">{ticks}</div>
<div style="margin-top:8px">{leg("rgba(84,140,242,.5)", "Εκτίμηση με το εύρος της")}{leg("#E0333B", "Ειδοποίηση οικογένειας") if fam else ""}</div>
<div style="margin-top:6px">{leg(COL["OK"], "Όλα καλά")}{leg(COL["DRINK"], "Νερό")}{leg(COL["COOL"], "Δροσιά")}{leg(COL["DANGER"], "Κίνδυνος")}</div>"""


def now_screen(i, dark):
    d = frame(i); vs = d["state"]; c = COL[vs]; word, why = STATE[vs]
    lo, hi, mid = d["coreC"] - d["halfRangeC"], d["coreC"] + d["halfRangeC"], d["coreC"]
    pos = lambda x: max(0, min(1, (x - 36) / 4)) * 100
    hero = f"""
<div style="display:flex;align-items:center;gap:10px;background:var(--card);border-radius:99px;padding:4px 6px 4px 12px;margin:2px 0 6px">
 <span class="sim">{svg(ICON["play"], 13, "#6B5CE6")}ΠΡΟΣΟΜΟΙΩΣΗ</span><span style="font-size:12px;color:var(--ink2);flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">Μέρα καύσωνα, εικονικό άτομο 398</span>
 <span style="font-size:12px;font-weight:600;color:var(--ink2)">60×</span><span style="width:36px;display:flex;justify-content:center;color:#29A885">{svg(ICON["pause"], 18)}</span><span style="width:36px;display:flex;justify-content:center;color:#29A885">{svg(ICON["sliders"], 20)}</span></div>
<div style="display:flex;flex-direction:column;align-items:center;padding:0 0 10px">
 <div style="position:relative;width:258px;height:238px;display:flex;align-items:center;justify-content:center">
  <div style="position:absolute;width:258px;height:258px;border-radius:50%;background:radial-gradient(circle, {c}57 30%, {c}00 70%)"></div>
  <div style="position:relative;width:136px;height:136px;border-radius:50%;background:linear-gradient({c}EB,{c});box-shadow:0 10px 22px {c}73;display:flex;align-items:center;justify-content:center;--hole:{c}">{svg(SYM[vs], 64, "#fff")}</div>
 </div>
 <div style="font-family:'Inter Display',Inter;font-size:34px;font-weight:700;text-align:center">{word}</div>
 <div style="font-size:17px;color:var(--ink2);text-align:center;margin-top:10px;line-height:1.3;padding:0 8px">{why}</div>
 <div style="font-size:13px;font-weight:500;color:var(--ink2);margin-top:10px">ΠΡΟΣΟΜΟΙΩΣΗ · {clock(i)}</div>
</div>"""
    core = f"""<div class="card"><div style="display:flex;justify-content:space-between;align-items:center"><span class="sec">{svg(ICON["thermo"], 18)}Εκτίμηση θερμοκρασίας σώματος</span>
<span style="font-size:11px;font-weight:700;letter-spacing:.8px;color:var(--ink2);border:1px solid var(--sep);border-radius:99px;padding:2px 7px">ΕΚΤΙΜΗΣΗ</span></div>
<div style="font-family:'Inter Display',Inter;font-size:40px;font-weight:600;margin-top:12px;font-variant-numeric:tabular-nums">{gr(lo)}–{gr(hi)} °C</div>
<div style="font-size:15px;color:var(--ink2);margin-top:4px">μέση τιμή {gr(mid)} °C</div>
<div style="position:relative;height:30px;margin-top:14px"><div style="position:absolute;top:4px;left:0;right:0;height:8px;border-radius:4px;background:var(--fill)"></div>
<div style="position:absolute;top:4px;left:{pos(lo):.1f}%;width:{pos(hi) - pos(lo):.1f}%;height:8px;border-radius:4px;background:{c}D9"></div>
<div style="position:absolute;top:1px;left:calc({pos(mid):.1f}% - 7px);width:14px;height:14px;border-radius:50%;background:var(--card);box-shadow:inset 0 0 0 3px {c}"></div>
{"".join(f'<span style="position:absolute;top:17px;left:calc({pos(t):.0f}% - {0 if t == 36 else 16 if t == 40 else 8}px);font-size:11px;color:var(--ink2)">{t}°</span>' for t in (36, 37, 38, 39, 40))}</div>
<div style="font-size:13px;color:var(--ink2);margin-top:12px">Υπολογίζεται από τον καρπό και τον παλμό. Δεν είναι θερμόμετρο.</div></div>"""
    tile = lambda ic, tint, lab, val, unit: f'<div class="tile"><div class="tl" style="color:{tint}">{svg(ICON[ic], 18)}{lab}</div><div class="tv">{val}</div><div class="tu">{unit}</div></div>'
    tiles = '<div class="tiles">' + tile("heart", "#FF2D55", "Παλμοί", d["hrBpm"] or "—", "παλμοί/λεπτό" if d["hrBpm"] else "κίνηση") + \
        tile("hand", "#FF9500", "Δέρμα", gr(d["t1C"]), "°C") + tile("house", "#30B0C7", "Χώρος", gr(d["tairC"]), f"°C  ·  {d['rhPct']} % RH") + \
        tile("battery", "#34C759", "Μπαταρία", d["batteryPct"], "%") + "</div>"
    contact = f'<div class="tile" style="display:flex;gap:12px;align-items:center;margin-bottom:16px">{svg(ICON["seal"], 28, COL["OK"])}<div><div class="sec" style="font-size:15px">Επαφή</div><div style="font-size:17px;font-weight:600;margin-top:2px">Εφαρμόζει καλά</div></div></div>'
    ch = f'<div class="card"><div style="display:flex;justify-content:space-between;align-items:center"><span class="sec">Η μέρα</span><span class="sim">{svg(ICON["play"], 13, "#6B5CE6")}ΠΡΟΣΟΜΟΙΩΣΗ</span></div>{chart(i, dark)}</div>'
    return hero + core + tiles + contact + ch


def alert_screen(i):
    d = frame(i)
    lo, hi = d["coreC"] - d["halfRangeC"], d["coreC"] + d["halfRangeC"]
    pill = lambda ic, t: f'<span style="display:inline-flex;gap:6px;align-items:center;background:rgba(255,255,255,.18);border-radius:99px;padding:8px 12px;font-size:15px;font-weight:600">{svg(ICON[ic], 16, "#fff")}{t}</span>'
    rings = "".join(f'<div style="position:absolute;width:150px;height:150px;border-radius:50%;border:2px solid rgba(255,255,255,.35);transform:scale({s});opacity:{o}"></div>' for s, o in ((1.25, .7), (1.6, .4), (1.95, .15)))
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}
body{{background:linear-gradient(#DB2B36,#800D1C);color:#fff}}</style></head><body>
<div class="status"><span>{clock(i)}</span><span>●●●● ▮</span></div>
<div style="padding:0 24px;display:flex;flex-direction:column;height:797px">
 <div style="display:flex;justify-content:space-between;align-items:center;min-height:30px"><span class="sim" style="color:#fff;background:rgba(255,255,255,.22)">{svg(ICON["play"], 13, "#fff")}ΠΡΟΣΟΜΟΙΩΣΗ</span><span style="font-size:17px;font-weight:600;opacity:.85">{clock(i)}</span></div>
 <div style="height:230px;display:flex;align-items:center;justify-content:center;position:relative;margin-top:28px">{rings}
  <div style="position:relative;width:150px;height:150px;border-radius:50%;background:rgba(255,255,255,.16);display:flex;align-items:center;justify-content:center;--hole:#C42430">{svg(SYM["DANGER"], 70, "#fff")}</div></div>
 <div style="text-align:center;font-size:20px;font-weight:600;opacity:.85;margin-top:4px">Μαρία</div>
 <div style="text-align:center;font-family:'Inter Display',Inter;font-size:34px;font-weight:700;line-height:1.15;margin-top:10px">Ειδοποίηση για την οικογένεια</div>
 <div style="text-align:center;font-size:20px;opacity:.92;margin-top:10px;line-height:1.3">Δεν πατήθηκε το κουμπί στο «Είστε καλά;».</div>
 <div style="display:flex;gap:10px;justify-content:center;margin-top:18px">{pill("thermo", f"{gr(lo)}–{gr(hi)} °C")}{pill("house", f"{gr(d['tairC'])} °C")}{pill("heart", d["hrBpm"])}</div>
 <div style="text-align:center;font-size:11px;opacity:.7;margin-top:6px">ΕΚΤΙΜΗΣΗ · Υπολογίζεται από τον καρπό και τον παλμό. Δεν είναι θερμόμετρο.</div>
 <div style="flex:1"></div>
 <div style="background:#fff;color:#DB2B36;border-radius:20px;height:64px;display:flex;align-items:center;justify-content:center;gap:10px;font-size:20px;font-weight:700">{svg(ICON["phone"], 22, "#DB2B36")}Θα τηλεφωνήσω</div>
 <div style="background:rgba(255,255,255,.2);border-radius:20px;height:60px;display:flex;align-items:center;justify-content:center;gap:10px;font-size:20px;font-weight:600;margin-top:12px">{svg(ICON["check"], 22, "#fff")}Είναι καλά</div>
 <div style="height:44px;display:flex;align-items:center;justify-content:center;gap:8px;font-size:16px;font-weight:600;opacity:.85;margin-top:12px">{svg(ICON["mute"], 18, "#fff")}Σίγαση</div>
 <div style="text-align:center;font-size:13px;opacity:.75;margin:4px 0 26px">Το βραχιόλι ενημερώθηκε ότι ειδοποιηθήκατε. (ΠΡΟΣΟΜΟΙΩΣΗ)</div>
</div></body></html>"""


def tomorrow_screen():
    p = PLAN
    def slot(h):
        if h["safe"]: return ("#29A885", 18)
        if h["advice"] == "OK": return ("rgba(140,148,161,.45)", 18)
        if h["advice"] == "SHORT": return ("#F2A626", 30)
        return ("#E0333B", 42)
    bars = "".join(f'<div style="flex:1;height:{slot(h)[1]}px;background:{slot(h)[0]};border-radius:3px"></div>' for h in p["hours"])
    W, H = 318.0, 140.0
    allv = [h["t_in"] for h in p["hours"]] + [h["t_out"] for h in p["hours"]]
    import math
    lo, hi = math.floor(min(allv)) - 1, math.ceil(max(allv)) + 1
    X = lambda i: i / 23 * W; Y = lambda v: H - (v - lo) / (hi - lo) * H
    pin = " ".join("%.1f,%.1f" % (X(i), Y(h["t_in"])) for i, h in enumerate(p["hours"]))
    pout = " ".join("%.1f,%.1f" % (X(i), Y(h["t_out"])) for i, h in enumerate(p["hours"]))
    adv_icon = lambda g: "DRINK" if ("νερό" in g or "υγρά" in g) else "COOL" if "δροσερό" in g else "DANGER" if "καύσωνας" in g else "OK"
    adv = "".join(f'<div style="display:flex;gap:12px;align-items:center;padding:5px 0"><span style="width:26px;display:flex;justify-content:center;--hole:#fff">{svg(SYM[adv_icon(g)], 18, "#F27329")}</span><span style="font-size:17px;font-weight:500">{g}</span></div>' for g in p["advice_gr"][:6])
    chip = lambda t, c: f'<span style="display:inline-flex;align-items:center;font-size:15px;font-weight:600;color:{c};background:{c}24;padding:7px 12px;border-radius:99px;margin:0 8px 8px 0">{t}</span>'
    body = f"""<div style="font-size:22px;font-weight:600;margin:4px 0 10px">Τρίτη 14 Ιουλίου</div>
<div style="margin-bottom:8px"><span class="sim" style="margin-right:8px">{svg(ICON["play"], 13, "#6B5CE6")}ΚΑΤΑΣΚΕΥΑΣΜΕΝΗ ΜΕΡΑ ΕΠΙΔΕΙΞΗΣ</span><span class="sim">{svg(ICON["play"], 13, "#6B5CE6")}ΠΡΟΣΟΜΟΙΩΣΗ</span></div>
<div style="margin-bottom:8px">{chip("☀ Ημέρα καύσωνα", "#F27329")}{chip("☾ Ζεστή νύχτα", "#F2A626")}{chip("4η μέρα καύσωνα", "#8E8E93")}</div>
<div class="card"><div class="sec">Ώρες για έξοδο</div><div style="font-family:'Inter Display',Inter;font-size:22px;font-weight:600;margin:10px 0 14px">Καμία ώρα δεν είναι ασφαλής για έξοδο.</div>
<div style="display:flex;gap:3px;align-items:flex-end;height:44px">{bars}</div>
<div style="display:flex;justify-content:space-between;font-size:11px;color:var(--ink2);margin-top:6px"><span>00</span><span>06</span><span>12</span><span>18</span><span>23</span></div></div>
<div class="card"><div class="sec" style="justify-content:space-between"><span>Θερμοκρασία</span><span style="font-size:11px;font-weight:400">━ Μέσα &nbsp; <span style="color:#F27329">┅ Έξω</span></span></div>
<svg width="{W:.0f}" height="{H:.0f}" style="margin-top:8px"><polyline points="{pout}" fill="none" stroke="#F27329" stroke-width="2.5" stroke-dasharray="6 5"/><polyline points="{pin}" fill="none" stroke="var(--ink)" stroke-width="2.5"/></svg></div>
<div class="card"><div class="sec">Συμβουλές</div>{adv}</div>"""
    return phone(body, tab="tom", title="Αύριο")


def shoot(pages):
    os.makedirs(OUT, exist_ok=True)
    tmp = os.path.join(OUT, "_html"); os.makedirs(tmp, exist_ok=True)
    jobs = []
    for name, html in pages:
        p = os.path.join(tmp, name + ".html"); open(p, "w", encoding="utf-8").write(html)
        jobs.append({"html": p, "png": os.path.join(OUT, name + ".png")})
    js = """const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const c=await b.newContext({viewport:{width:390,height:844},deviceScaleFactor:2});
const p=await c.newPage();for(const j of JSON.parse(process.argv[1])){await p.goto('file://'+j.html);await p.waitForTimeout(150);await p.screenshot({path:j.png});console.log(j.png)}await b.close()})();"""
    subprocess.run(["node", "-e", js, json.dumps(jobs)], check=True)
    for j in jobs: os.remove(j["html"])
    os.rmdir(tmp)


if __name__ == "__main__":
    shoot([
        ("mock_now_cool_light", phone(now_screen(815, False))),
        ("mock_now_cool_dark", phone(now_screen(815, True), dark=True)),
        ("mock_now_ok_light", phone(now_screen(790, False), clock_txt="13:10")),
        ("mock_now_cool_light_scrolled", phone(now_screen(815, False), scroll=640, title="")),
        ("mock_alert", alert_screen(843)),
        ("mock_tomorrow_light", tomorrow_screen()),
    ])
