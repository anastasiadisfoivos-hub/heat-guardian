#!/usr/bin/env python3
"""Acceptance 1: hg2_step (C, via host_test replay with force_worn = the trace's worn) vs B2's golden_trace.parquet.
f20_eff/f30_eff are compared against core_20/core_30 because M5.1 removed '+1 sd' (B2's golden may still contain it)."""
import json, os, sys, tempfile
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "py"))
from trace_io import minute, write_csv, run_c
E = "/home/claude/hg_ai/model/export"
g = pd.read_parquet(E + "/golden_trace.parquet"); meta = json.load(open(E + "/golden_trace_meta.json"))
res = {}
temps = ["out_core_now", "out_core_20", "out_core_30", "out_kf"]; flags = ["out_flux_valid", "out_hr_valid", "out_valid"]
mx = {k: 0.0 for k in temps + ["out_logit_p38", "out_logit_p385", "out_strain", "out_sd_now", "out_sd_20", "x"]}; fl_bad = 0; n = 0
with tempfile.TemporaryDirectory() as d:
    for pid, gp in g.groupby("person_id", sort=False):
        tw = meta["twins"][str(pid)]; prof = tw["profile"]; twin = tw["twin"]
        mins = [minute(mod=int(r.minute_of_day), t1=r.t1_c, t2=r.t2_c, tair=r.t_air_c, rh=r.rh_pct, hr=r.hr_bpm, hrq=int(r.hr_quality),
                       pi=r.pi_pct, astd=r.a_std_g, force_worn=int(r.worn)) for r in gp.itertuples()]
        write_csv(d + "/i.csv", mins, prof, twin); rows = run_c(d + "/i.csv", d + "/o.csv")
        xcols = [c for c in gp.columns if c[:1] == "x" and c[1:3].isdigit()]
        for r, (_, q) in zip(rows, gp.iterrows()):
            n += 1
            for k in temps + ["out_logit_p38", "out_logit_p385", "out_strain", "out_sd_now"]:
                a, b = r[k[4:]], float(q[k])
                if np.isfinite(a) and np.isfinite(b): mx[k] = max(mx[k], abs(a - b))
                elif np.isfinite(a) != np.isfinite(b): mx[k] = float("inf")
            for i, c in enumerate(xcols):
                a, b = r["x%d" % i], float(q[c])
                if np.isfinite(a) and np.isfinite(b): mx["x"] = max(mx["x"], abs(a - b))
                elif np.isfinite(a) != np.isfinite(b): mx["x"] = float("inf")
            fl_bad += int(any(int(r[k[4:]]) != int(q[k]) for k in flags))
golden_f20_has_sd = float(np.nanmax(np.abs(g.out_f20_eff - g.out_core_20)))
out = dict(rows=n, max_abs_diff=mx, flag_mismatch_rows=fl_bad, golden_f20_eff_minus_core20_max=golden_f20_has_sd,
           pass_1e4=all(v <= 1e-4 for k, v in mx.items()) and fl_bad == 0)
print(json.dumps(out, indent=1)); json.dump(out, open(os.path.join(HERE, "out", "golden_check.json"), "w"), indent=1)
sys.exit(0 if out["pass_1e4"] else 1)
