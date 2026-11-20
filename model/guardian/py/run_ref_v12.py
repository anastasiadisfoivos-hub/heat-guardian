#!/usr/bin/env python3
"""Acceptance 2: hg_kf (port) vs heat_guardian_band.c (original) on the 104 HTT dev sessions + 20 synthetic 75-year-old
sessions (beta-blocker / diuretic / low-sweat, humid air, stillness, button presses) as in REPORT s10 v1.2 check."""
import json, os, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_traces
HERE = os.path.dirname(os.path.abspath(__file__)); C = os.path.join(HERE, "..", "c")
subprocess.check_call(["make", "-s", "-C", C, "ref"])
def write(path, sessions):
    with open(path, "w") as f:
        for prof, rest, rows in sessions:
            f.write("S %.9g %d %.9g %.9g %d\n" % (prof["age"], int(prof["sex_m"]), prof["bmi"], rest, prof["med_flags"]))
            for (hr, amb, rh, still, b) in rows: f.write("%.9g %.9g %.9g %d %d\n" % (hr, amb, rh, still, b))
            f.write("E\n")
htt = [(prof, tw["rest_hr"], [(m["hr"], m["tair"], m["rh"], 0, 0) for m in mins]) for _, prof, tw, mins in run_traces.htt_sessions()]
r = np.random.default_rng(20261112); syn = []
for k in range(20):
    prof = dict(age=75.0, sex_m=float(k % 2), bmi=float(r.uniform(22, 30)), med_flags=int([1, 2, 4, 1 | 2, 8][k % 5]))
    hr = 70.0; rows = []
    for t in range(240):
        hr += 0.2 * (60 + 70 * (1 if 60 < t < 200 else 0) - hr) + r.normal(0, 3)
        rows.append((hr if r.random() > 0.05 else float("nan"), float(r.uniform(30, 41)), float(r.uniform(30, 75)),
                     int(r.random() < 0.3), int(r.random() < 0.02)))
    syn.append((prof, float(r.uniform(55, 80)), rows))
res = {}
for name, ss in (("htt104", htt), ("synthetic20_older_meds", syn)):
    p = os.path.join(C, "build", "ref_%s.txt" % name); write(p, ss)
    out = subprocess.check_output([os.path.join(C, "build", "ref_v12")], stdin=open(p)).decode()
    print("==", name); print(out); res[name] = out
os.makedirs(os.path.join(HERE, "..", "tests", "out"), exist_ok=True)
json.dump(res, open(os.path.join(HERE, "..", "tests", "out", "ref_v12.json"), "w"), indent=1)
