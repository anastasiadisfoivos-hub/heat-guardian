#!/usr/bin/env python3
"""T5 crafted edge cases on the scripted-core harness (C sc_O2 and the Python mirror, both checked):
M12 heat-context gate (room exactly 30.0 C, one ulp below, OOD edges), M13 persistence (f20 flat vs falling 0.001 per 10 min,
COOL toggling around 20 min, hold-bridged COOL), DANGER->CHECK->family timing, design-A calm baseline learning + set/get.
  python3 edge.py  -> out/edge.json (+ printed table)"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc
F = np.float32
UP = lambda v: float(np.nextafter(F(v), F(1e9))); DN = lambda v: float(np.nextafter(F(v), F(-1e9)))
PROF = dict(age=75.0, sex_m=0.0, bmi=26.0, med_flags=0)
results = []

def run(name, rows, prof=PROF, calm=None):
    c = sc.run_c(prof, rows, calm); p = sc.run_py(prof, rows, calm)
    same = all((F(a[k]) == F(b[k])) if k == "a_base" else a[k] == b[k] for a, b in zip(c, p) for k in sc.OUT)
    return c, same

def first(c, pred):
    for t, o in enumerate(c):
        if pred(o): return t
    return None

def rec(case, expect, got, same, note=""):
    ok = expect == got
    results.append(dict(case=case, expect=expect, got=got, pass_=ok, c_eq_py=same, note=note))
    print("%-62s expect %-14s got %-14s %s %s %s" % (case, expect, got, "PASS" if ok else "FAIL", "C==Py" if same else "C!=Py", note))

# ---------------- M12 heat context: v1.2 ceiling 37.9 (>= 37.85), only the gate varies; DRINK expected at row 6 (valid at msd 5)
def m12(tair, x10=70.0, x14=0.1, eao=0, v12=37.9, n=40):
    return [sc.row(mod=600 + t, v12f20=v12, core20=36.9, tair=tair, x10=x10, x14=x14, eao=eao) for t in range(n)]
for nm, kw, exp in [("M12 corrected air exactly 30.0 C", dict(tair=30.0), 6),
                    ("M12 corrected air 30.0 - 1 ulp", dict(tair=DN(30.0)), None),
                    ("M12 29.99 C but air above PSU older line", dict(tair=29.99, eao=1), 6),
                    ("M12 25 C, HR exactly 108 (not OOD: '> 108')", dict(tair=25.0, x10=108.0), None),
                    ("M12 25 C, HR 108 + 1 ulp (OOD opens the gate)", dict(tair=25.0, x10=UP(108.0)), 6),
                    ("M12 25 C, hr_reserve exactly 0.6 (not OOD)", dict(tair=25.0, x14=0.6), None),
                    ("M12 25 C, hr_reserve 0.6 + 1 ulp (OOD)", dict(tair=25.0, x14=UP(0.6)), 6),
                    ("M12 30 C, v1.2 f20 = 37.85 exactly (before thermal blank)", dict(tair=30.0, v12=37.85), 6),
                    ("M12 30 C, v1.2 f20 = 37.85 - 1 ulp (fires only once the 0.018 lowering starts, row 21)", dict(tair=30.0, v12=DN(37.85)), 21)]:
    c, same = run(nm, m12(**kw)); rec(nm, exp, first(c, lambda o: o["tiers"] & 1), same)
# M5.2 lowering only after the 20-min thermal blank: 37.832 fires from msd 20 (row 20 cond, row 21 on), not at row 6
lo = float(F(F(37.85) - F(0.0179999992)))
c, same = run("M5.2", m12(30.0, v12=lo)); rec("M5.2 v1.2 f20 = 37.85-0.018 (fires only after 20-min blank)", 21, first(c, lambda o: o["tiers"] & 1), same)
c, same = run("M5.2b", m12(30.0, v12=DN(lo))); rec("M5.2 v1.2 f20 = 37.85-0.018 - 1 ulp", None, first(c, lambda o: o["tiers"] & 1), same)

# ---------------- M13 persistence. COOL from the heat dose (edose 120 >= 97, env2), PSU-line evidence ea=1, no v1.2/NN Danger,
# a_std 0.01 (not still -> behaviour path off). COOL on at row 1; pd_cool_run = 20 at row 20; DANGER tier at row 21 -> level 3,
# CHECK (state DANGER) at row 21, family at row 26 (5 min, no press).
def m13(f20fn, n=60, ea=1, edose_fn=lambda t: 120, l385=-100.0, z=-6.0, button_at=()):
    return [sc.row(mod=780 + t, core20=f20fn(t), v12f20=36.9, tair=34.0, ea=ea, eao=ea, erun=0, edose=edose_fn(t), l385=l385, v12z=z,
                   astd=0.01, button=1 if t in button_at else 0) for t in range(n)]
c, same = run("flat", m13(lambda t: 37.5))
rec("M13 f20 flat: DANGER (CHECK) row", 21, first(c, lambda o: o["state"] == 4), same)
rec("M13 f20 flat: family flag row", 26, first(c, lambda o: o["family_alert"]), same)
c, same = run("fall", m13(lambda t: float(F(37.5 - 0.0001 * t))))
rec("M13 f20 falling 0.001 per 10 min: no DANGER", None, first(c, lambda o: o["tiers"] & 4), same, "env evidence present all along")
c, same = run("fall1", m13(lambda t: 37.5 if t < 30 else 37.499))
rec("M13 one 0.001 drop at row 30: danger before it", 21, first(c, lambda o: o["tiers"] & 4), same)
c, same = run("rise", m13(lambda t: float(F(37.5 + 0.0001 * t))))
rec("M13 f20 rising: DANGER row", 21, first(c, lambda o: o["state"] == 4), same)
c, same = run("noev", m13(lambda t: 37.5, ea=0))
rec("M13 no evidence (ea 0, NN<0, z low): no DANGER", None, first(c, lambda o: o["tiers"] & 4), same)
c, same = run("nn0", m13(lambda t: 37.5, ea=0, l385=0.0))
rec("M13 evidence NN logit_p385 exactly 0.0 (needs thermal blank: row>=20)", 21, first(c, lambda o: o["tiers"] & 4), same)
c, same = run("z", m13(lambda t: 37.5, ea=0, z=-2.19722509))
rec("M13 evidence v1.2 z exactly logit(0.10)", 21, first(c, lambda o: o["tiers"] & 4), same)
c, same = run("zdn", m13(lambda t: 37.5, ea=0, z=DN(-2.19722509)))
rec("M13 evidence v1.2 z 1 ulp below logit(0.10)", None, first(c, lambda o: o["tiers"] & 4), same)
# COOL toggling: env2 false rows 15..24 (10 min -> COOL off at row 24), on again at 26 -> pd_cool_run 20 at row 45 -> DANGER row 46
c, same = run("tog10", m13(lambda t: 37.5, n=90, edose_fn=lambda t: 0 if 5 <= t <= 14 else 120))
rec("M13 COOL off at 14 (10 false min), back on at 16: DANGER row", 36, first(c, lambda o: o["tiers"] & 4), same)
# 9 false minutes (5..13): the 10-min hold bridges, COOL never off -> DANGER at 21 although COOL's condition was false 9 of 20 min
c, same = run("tog9", m13(lambda t: 37.5, n=90, edose_fn=lambda t: 0 if 5 <= t <= 13 else 120))
rec("M13 COOL condition false 9 min (hold bridges): DANGER row", 21, first(c, lambda o: o["tiers"] & 4), same, "persistence counts the held tier")
# press during the CHECK at row 23 -> IMOK, snooze 15 -> re-ask at 39 (= 23 + 15 + 1), family at 44
c, same = run("press", m13(lambda t: 37.5, n=70, button_at=(23,)))
rec("M13 press at row 23 -> IMOK row", 23, first(c, lambda o: o["state"] == 5), same)
rec("M13 after IMOK: re-ask (CHECK) row", 38, first(c[24:], lambda o: o["check_active"]) + 24 if first(c[24:], lambda o: o["check_active"]) is not None else None, same)
rec("M13 after IMOK: family row", 43, first(c, lambda o: o["family_alert"]), same)
# press in the very minute the CHECK opens (row 21) is not an IMOK
c, same = run("press21", m13(lambda t: 37.5, n=40, button_at=(21,)))
rec("press in the CHECK's first minute (row 21): IMOK?", None, first(c, lambda o: o["state"] == 5), same, "first-minute press ignored; family row %s" % first(c, lambda o: o["family_alert"]))
# band taken off during the CHECK (worn 0 from row 23): family flag?
rows = m13(lambda t: 37.5, n=200)
for t in range(23, 200): rows[t]["worn"] = 0
c, same = run("off", rows)
rec("DANGER CHECK, band off from row 23: family flag within 3 h", "row<=60", ("row %s" % first(c, lambda o: o["family_alert"])), same,
    "state at row 199 = %d" % c[-1]["state"])

# ---------------- design A calm baseline: 08:00-22:00 resting minutes, median bin, EMA, bounds; DRINK = f20 - calm >= 0.3 - 0.018
def day(f20, n_days=2, start=480, active_every=0):
    rows = []; mod = start
    for t in range(n_days * 1440):
        rows.append(sc.row(mod=mod, core20=f20(t), v12f20=36.9, tair=25.0, astd=0.05 if (t % 30) < 3 else 0.01))
        mod = (mod + 1) % 1440
    return rows
c, same = run("calm", day(lambda t: 37.1))
k = first(c, lambda o: o["a_base_n"] > 0)
rec("design A: calm learned at first midnight (row 960)", 960, k, same)
pos = float(F(F(F(37.1) - F(36)) / F(0.0199999996))); b_exp = round(float(F(F(36) + F(F(0.0199999996) * F(int(pos) + 0.5)))), 4)
rec("design A: calm value = bin centre of float32(37.1) (pos %.5f)" % pos, b_exp, round(c[k]["a_base"], 4) if k is not None else None, same,
    "median quantised to 0.02-C bin centres")
base = F(c[k]["a_base"]); thr = float(F(base + F(F(0.300000012) - F(0.0179999992))))
def stepf(v): return lambda t: 37.1 if t < 1000 else v
for v, exp in ((thr, 1001), (DN(thr), None)):
    c, same = run("rel%s" % v, day(stepf(v)))
    rec("design A: f20 %.6f after calm %.4f (25 C room, no heat context)" % (v, float(base)), exp, first(c, lambda o: o["tiers"] & 1), same)
# bounds: calm 36.0 day -> clamp 36.8 ; 37.95 day -> clamp 37.7 ; f20 below 36 / >= 38 not counted
for v, exp in ((36.3, 36.8), (37.95, 37.7)):
    c, same = run("b%s" % v, day(lambda t: v))
    rec("design A: calm clamp for a %.2f day" % v, exp, round(c[-1]["a_base"], 4), same)
c, same = run("hot", day(lambda t: 38.2))
rec("design A: f20 >= 38.0 all day -> nothing learned (out of histogram)", 0, c[-1]["a_base_n"], same,
    "a day spent >= 38 C (and level 0) is ignored")
# set/get round-trip through hg_guardian_set_calm (+ NaN / inf / out of bounds)
for val, n, exp in ((37.2, 3, (37.2, 3)), (float("nan"), 3, (0.0, 0)), (float("inf"), 3, (0.0, 0)), (36.79, 2, (0.0, 0)), (37.7, 1, (37.7, 1)), (37.4, 0, (0.0, 0))):
    c, same = run("set", [sc.row(mod=600)], calm=(val, n))
    rec("set_calm(%s, %d) -> (a_base, n)" % (val, n), (round(float(F(exp[0])), 4), exp[1]), (round(c[0]["a_base"], 4), c[0]["a_base_n"]), same)
# backwards clock jump counts as a 'midnight' (baseline updated mid-day)
rows = day(lambda t: 37.3, n_days=1)[:400]
for t in range(400, 700): rows.append(sc.row(mod=(480 + t - 300) % 1440, core20=37.3, v12f20=36.9, tair=25.0, astd=0.05 if (t % 30) < 3 else 0.01))   # 14:40 -> 13:00 jump
c, same = run("jump", rows)
rec("clock jumps back 14:40 -> 13:00: calm baseline updated?", 0, c[-1]["a_base_n"], same, "a backward jump is treated as midnight")
# ---------------- routine NOWAKE at donning / after a reset between W+2 h (10:00) and 12:00
for start, quiet in ((615, True), (615, False), (735, True)):
    rows = [sc.row(mod=start + t, core20=36.9, v12f20=36.9, tair=25.0, astd=(0.01 if quiet or t % 10 > 2 else 0.05)) for t in range(30)]
    c, same = run("nowake", rows)
    rec("fresh boot/donning at %02d:%02d, %s wearer: routine CHECK row / family row" % (start // 60, start % 60, "quiet" if quiet else "active"),
        "None / None", "%s / %s" % (first(c, lambda o: o["check_active"]), first(c, lambda o: o["family_alert"])), same)
json.dump(results, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "edge.json"), "w"), indent=1, default=str)
print("cases %d, pass %d, C==Py %d" % (len(results), sum(r["pass_"] for r in results), sum(r["c_eq_py"] for r in results)))
