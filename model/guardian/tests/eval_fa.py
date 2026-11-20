#!/usr/bin/env python3
"""Alarm-rate evaluation of the Guardian Loop (C build via host_test replay).
  eval_fa.py crafted   CRAFTED synthetic weeks (trace_gen.py): engineering smoke test, NOT evidence (label CRAFTED)
  eval_fa.py sim       SIM-DEV (B1) person-days, all scenarios, SIMULATION label; sealed persons excluded
  eval_fa.py office    the 14 DEV office subjects of dataset 16 (real wrists, 20-30 C); refuses before the seal exists and
                       asserts that no SEALED-OFFICE subject is read. Never run by B5 (manager instruction: dataset 16 untouched).
Counts per person-day: DRINK / COOL episode onsets, CHECK starts, family flags; rates per day, per hour, per week, per month.
Targets (B5 brief acceptance 5) are printed next to the numbers; a rate over target is REPORTED, never tuned."""
import json, os, sys, tempfile, hashlib
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "py"))
from trace_io import write_csv, run_c, minute, default_twin
OUT = os.path.join(HERE, "out")

def count(rows):
    c = dict(drink=0, cool=0, check=0, family=0, danger=0, minutes=len(rows), drink_min=0, cool_min=0, check_reasons={})
    pl = 0; pf = 0; pcm = 0xFF
    for r in rows:
        lv = r["level"]
        if lv >= 1 and pl < 1: c["drink"] += 1
        if lv >= 2 and pl < 2: c["cool"] += 1
        if lv >= 3 and pl < 3: c["danger"] += 1
        if r["check_min"] == 0 and pcm != 0: c["check"] += 1; c["check_reasons"][r["check_reason"]] = c["check_reasons"].get(r["check_reason"], 0) + 1
        if r["family_alert"] and not pf: c["family"] += 1
        c["drink_min"] += lv >= 1; c["cool_min"] += lv >= 2
        pl, pf, pcm = lv, r["family_alert"], r["check_min"]
    return c

def run_sets(sets, label):
    tot = {}; per = []
    with tempfile.TemporaryDirectory() as d:
        for name, prof, tw, mins, tag in sets:
            write_csv(d + "/i.csv", mins, prof, tw); rows = run_c(d + "/i.csv", d + "/o.csv")
            c = count(rows); c["name"] = name; c["tag"] = tag; per.append(c)
    res = {"label": label}
    for tag in sorted(set(c["tag"] for c in per)):
        cs = [c for c in per if c["tag"] == tag]; days = sum(c["minutes"] for c in cs) / 1440.0
        r = {k: sum(c[k] for c in cs) for k in ("drink", "cool", "danger", "check", "family", "drink_min", "cool_min")}
        r.update(days=days, drink_per_day=r["drink"] / days, cool_per_day=r["cool"] / days, check_per_week=7 * r["check"] / days,
                 family_per_month=30 * r["family"] / days, drink_per_h=r["drink"] / (24 * days), drink_hours_per_day=r["drink_min"] / 60 / days)
        reasons = {}
        for c in cs:
            for k, v in c["check_reasons"].items(): reasons[k] = reasons.get(k, 0) + v
        r["check_reason_bits"] = reasons
        res[tag] = r
    return res, per

def crafted():
    import trace_gen
    sets = []
    for k in range(6):
        p = trace_gen.person(2000 + k)
        sets.append(("p%d_ordinary_week" % k, p["profile"], p["twin"], trace_gen.days(p, 7, "ordinary", seed=11), "CRAFTED ordinary week (indoor 26-29 C)"))
        sets.append(("p%d_heat_week" % k, p["profile"], p["twin"], trace_gen.days(p, 5, "heat", seed=12), "CRAFTED heat week (indoor 31-34 C)"))
        sets.append(("p%d_cool_week" % k, p["profile"], p["twin"], trace_gen.days(p, 7, "cool", seed=13), "CRAFTED cool week (indoor 22-25 C)"))
    return sets

def office_segments(c, sid):
    """dataset-16 subject -> list of (session_id, replay minutes). Dataset 16 is long format: one row per (session, t_s) on a
    per-session clock ("office 1-min grid"); sessions are NOT on a common wall clock. Pre-registered (M12 exam, Nov 12):
    each session with a regular 60-s grid and >= 30 rows is one continuous wear segment replayed by a FRESH guardian
    (day-1 state); sparser sessions (the 400-s "s-1" overview grid) are excluded. Bare wrist skin as T1 (not insulated),
    no T2, office air, activity = acc-magnitude std per min (g); time of day unknown (0xFFFF: routine/circadian off)."""
    import pandas as pd
    ts = pd.read_sql("SELECT session_id, t_s, skin_temp_c, hr_bpm, activity, activity_unit, ambient_c, rh_pct FROM timeseries "
                     "WHERE dataset_id = 16 AND subject_id = ? ORDER BY session_id, t_s", c, params=(str(sid),))
    segs = []
    for ses, g in ts.groupby("session_id", sort=True):
        dt = g.t_s.diff().dropna()
        if len(g) < 30 or not (dt == 60.0).all(): continue
        segs.append((str(ses), [minute(mod=0xFFFF, t1=r.skin_temp_c, tair=r.ambient_c, rh=r.rh_pct if r.rh_pct == r.rh_pct else 45.0,
                                       hr=r.hr_bpm, hrq=4 if r.hr_bpm == r.hr_bpm else 0,
                                       astd=r.activity if (isinstance(r.activity_unit, str) and r.activity_unit.endswith(" g")) or r.activity_unit == "g" else float("nan"),
                                       dc=110000, vbat=3.9) for r in g.itertuples()]))
    return segs

def office_dev_ids(c):
    seal = "/home/claude/hg_ai/model/sealed_hg2.json"
    import pandas as pd
    sealed = set(str(s) for s in json.load(open(seal))["sealed_office_subject_ids"])
    subs = [str(s) for s in pd.read_sql("SELECT DISTINCT subject_id FROM subjects WHERE dataset_id = 16", c).subject_id]
    dev = sorted(set(subs) - sealed); assert not set(dev) & sealed and len(dev) == len(subs) - len(sealed)
    return dev

def office():
    seal = "/home/claude/hg_ai/model/sealed_hg2.json"
    if not os.path.exists(seal): raise SystemExit("refusing: sealed_hg2.json does not exist yet")
    sealed = set(str(s) for s in json.load(open(seal))["sealed_office_subject_ids"])
    import sqlite3, pandas as pd
    c = sqlite3.connect("file:/home/claude/hgdata/heat_guardian_train.sqlite?mode=ro", uri=True)
    subs = [str(s) for s in pd.read_sql("SELECT DISTINCT subject_id FROM subjects WHERE dataset_id = 16", c).subject_id]
    dev = sorted(set(subs) - sealed); assert not set(dev) & sealed and len(dev) == len(subs) - len(sealed)
    sets = []
    for sid in dev:   # query only DEV ids (the sealed ids never enter a query)
        for ses, mins in office_segments(c, sid):
            sets.append((sid + "/" + ses, dict(age=35.0, sex_m=0.0, bmi=24.0, med_flags=0), default_twin(), mins, "DEV office (real wrists; young/middle-aged)"))
    return sets

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "crafted"
    if which == "crafted": sets, label = crafted(), "CRAFTED synthetic traces - engineering smoke test, NOT simulation, NOT evidence"
    elif which == "sim":
        import sim_adapter
        sets = [(n, pr, tw, mi, "SIMULATION " + str(mi[0]["truth"].get("scenario"))) for n, pr, tw, mi in sim_adapter.sim_sets(10 ** 6)]
        label = "SIMULATION (B1 Virtual Elders, SIM-DEV only)"
    elif which == "office": sets, label = office(), "DEV office subjects (real), dataset 16 minus SEALED-OFFICE"
    else: raise SystemExit(__doc__)
    res, per = run_sets(sets, label)
    os.makedirs(OUT, exist_ok=True)
    json.dump(dict(summary=res, per=per), open(os.path.join(OUT, "eval_fa_%s.json" % which), "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))
