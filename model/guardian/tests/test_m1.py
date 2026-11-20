#!/usr/bin/env python3
"""M1 decision checks on the C build (arch/DECISIONS.md M1.1-M1.3).
M1.1 night_heat flag + exactly one nudge per evening, no tier; M1.2 RH clamp only inside the v1.2 linear model;
M1.3 total watch-threshold lowering capped at 0.20 C."""
import os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "py")); sys.path.insert(0, HERE)
from trace_io import run_c, write_csv, minute
from hg_guardian_py import KF, K
fails = 0
def check(name, ok, info=""):
    global fails; print("%s %s %s" % ("PASS" if ok else "FAIL", name, info)); fails += 0 if ok else 1
T = os.path.join(HERE, "traces")
with tempfile.TemporaryDirectory() as d:
    r = run_c(os.path.join(T, "trace_drink_who_night.csv"), d + "/o.csv")
    nh = [x["night_heat"] for x in r]; nu = [i for i, x in enumerate(r) if x["nudge"]]
    check("M1.1 night_heat set from 30/45 min, no tier", nh.index(1) == 29 and all(x["tiers"] == 0 for x in r), "first night_heat minute %d" % nh.index(1))
    check("M1.1 exactly one nudge per evening (screen NUDGE, tick)", nu == [29] and r[29]["screen"] == 11 and r[29]["haptic"] == 4, "nudges at %s" % nu)
    # two evenings: re-armed in the afternoon
    base = lambda mod: minute(mod=mod % 1440, t1=34.0, t2=32.8, tair=26.0, rh=50.0, hr=70.0, hrq=4, pi=0.6, astd=0.001, dc=110000, vbat=4.0, force_worn=2)
    mins = [base(1380 + k) for k in range(2 * 1440)]
    write_csv(d + "/i.csv", mins, dict(age=75.0, sex_m=1.0, bmi=26.0, med_flags=0), dict(rest_hr=70.0, k_person=0.12, core_offset=0.0, c_bodyheat=0.15))
    r2 = run_c(d + "/i.csv", d + "/o2.csv")
    check("M1.1 one nudge per evening over 2 nights", sum(x["nudge"] for x in r2) == 2, "%d nudges" % sum(x["nudge"] for x in r2))
    check("M1.1 no night_heat by day", all(not x["night_heat"] for x, m in zip(r2, mins) if 7 * 60 <= m["mod"] < 23 * 60))
    r3 = run_c(os.path.join(T, "trace_drink_who_day.csv"), d + "/o3.csv")
    check("M1.1 WHO day rule: reason bit only", any(x["why"] & 128 for x in r3) and all(x["tiers"] == 0 for x in r3))
# M1.2 on the v1.2 model itself
def f20(rh, clamp):
    k = KF(75, 0, 26, 70, 0); k.rh_clamp = clamp
    for _ in range(240): o = k.step(70, 30.0, rh)
    return float(o["f20"])
check("M1.2 RH 20 % clamped = RH 38 % (resting f20)", abs(f20(20, True) - f20(38, True)) < 1e-6, "%.3f (unclamped %.3f)" % (f20(20, True), f20(20, False)))
check("M1.2 RH inside range unchanged", abs(f20(50, True) - f20(50, False)) < 1e-6)
check("M1.3 cap constant 0.20 C", abs(float(K("HG_M_TOTAL_CAP")) - 0.2) < 1e-7)
sys.exit(fails)
