#!/usr/bin/env python3
"""R1: recompute PSU HEAT older/young critical limits, sweat rates, metabolic rates,
Pa_crit fits and critical wet-bulb from the project's own training database.
Source dataset: dataset_id=3 (Zenodo 10197956, Wolf et al. 2023 Commun Earth Environ 4:486).
Run: python3 -I R1_psu_recompute.py
"""
import sqlite3, statistics as st
import numpy as np
from collections import defaultdict

DB = "/home/claude/hgdata/heat_guardian_train.sqlite"
c = sqlite3.connect(DB)
rows = list(c.execute("""select subject_id, condition, group_label, variable, value
                         from summary_points where dataset_id=3 and value is not null"""))
per = defaultdict(dict)
for sid, cond, g, v, val in rows:
    per[(sid, cond, g)][v] = val

CONDS = [f"fixed Tdb {t}C, rising Pa" for t in (34, 36, 38, 40)] + \
        [f"fixed Pa {p}mmHg, rising Tdb" for p in (12, 16)]

print(f"{'condition':38s} {'grp':6s} {'n':>3s} {'Tdb':>6s} {'Pa_kPa':>7s} {'RH%':>6s} {'Wm2':>6s} {'MET':>5s} {'sweat':>6s}")
for cond in CONDS:
    for act in ("Rest", "MinAct"):
        key = cond + "; " + act
        for g in ("older", "young"):
            sel = [d for (s, cnd, gg), d in per.items() if cnd == key and gg == g]
            if not sel:
                continue
            def m(v):
                x = [d[v] for d in sel if v in d]
                return st.mean(x) if x else float("nan")
            print(f"{key:38s} {g:6s} {len(sel):3d} {m('critical_Tdb'):6.1f} "
                  f"{m('critical_Pa'):7.2f} {m('critical_RH_derived'):6.1f} "
                  f"{m('net_metabolic_rate_per_AD'):6.1f} {m('METs'):5.2f} {m('sweat_rate'):6.0f}")

print("\nPa_crit [kPa] vs Tdb, fitted over INDIVIDUAL trials:")
for nm, sel in (("older MinAct", lambda cnd, g: g == "older" and "MinAct" in cnd),
                ("older Rest",   lambda cnd, g: g == "older" and "Rest" in cnd),
                ("young MinAct", lambda cnd, g: g == "young" and "MinAct" in cnd)):
    X = [d["critical_Tdb"] for (s, cnd, g), d in per.items()
         if sel(cnd, g) and "critical_Tdb" in d and "critical_Pa" in d]
    Y = [d["critical_Pa"] for (s, cnd, g), d in per.items()
         if sel(cnd, g) and "critical_Tdb" in d and "critical_Pa" in d]
    a, b = np.polyfit(X, Y, 1)
    print(f"  {nm:14s} n={len(X):3d}  Pa_crit = {b:.3f} {a:+.4f}*Tdb   r={np.corrcoef(X,Y)[0,1]:.3f}")

def twb_stull(T, RH):
    return (T*np.arctan(0.151977*(RH+8.313659)**0.5) + np.arctan(T+RH)
            - np.arctan(RH-1.676331) + 0.00391838*RH**1.5*np.arctan(0.023101*RH) - 4.686035)

print("\nCritical wet-bulb temperature (Stull approximation):")
agg = defaultdict(list)
for (s, cnd, g), d in per.items():
    if "critical_Tdb" in d and "critical_RH_derived" in d:
        agg[(cnd, g)].append(twb_stull(d["critical_Tdb"], d["critical_RH_derived"]))
for k in sorted(agg):
    v = agg[k]
    print(f"  {k[1]:6s} {k[0]:38s} Twb_crit = {np.mean(v):.1f} +- {np.std(v, ddof=1):.1f} C (n={len(v)})")
