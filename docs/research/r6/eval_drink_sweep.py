#!/usr/bin/env python3
"""R6 E5b: DRINK trade-off curve for the 'exception + settled' design (D3) - SIMULATION DEV. See eval_drink.py."""
import json, numpy as np
from common import *; from eval_drink import metrics
P = IDX["persons"]; out = {}
for hk in ("raw", "sc"):
    for calm in (False, True):
        for var, delta, R, rise in (("D1", 0.30, 0, 0), ("D1", 0.24, 0, 0), ("D3", 0.30, 120, 0.15), ("D3", 0.24, 120, 0.15), ("D3", 0.24, 60, 0.10), ("D3", 0.20, 120, 0.10)):
            r = metrics(P, hk, var, DELTA=delta, R=R, RISE=rise, CALM_ONLY=calm); k = "%s|%s|calm_only=%d|delta=%.2f|R=%d|rise=%.2f" % (hk, var, calm, delta, R, rise); out[k] = r
            print("%-52s drink/day %.2f (mean %.2f)  min/day %.0f (mean %.0f)  S2 display %.3f informed %.3f" % (k, r["drink_per_day_median"], r["drink_per_day_mean"], r["drink_min_median"], r["drink_min_mean"], r["s2_sens"], r["s2_informed"]), flush=True)
json.dump(out, open(HERE + "/out_drink_sweep.json", "w"), indent=1)
