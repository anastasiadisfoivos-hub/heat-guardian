#!/usr/bin/env python3
"""R6-comparable DEV evaluation (SIMULATION, Virtual Elders v4, DEV only). Replays R6's 110 DEV persons (research/r6/cache/index.json:
all 43 core-38.5 persons + 67 calibration persons) through one or more guardian host builds, raw and HR-scaled (same inputs as
R6's build_cache.py / eval_sim_m7.py), and scores them with R6's OWN code (read-only imports from research/r6):
  Danger : final_danger.per_person / summ on level >= 3  (caught in [t-45, t+10]; episodes after 30 quiet min; strict FA = core
           never >= 38.5 in [onset-10, onset+60]; empty FA = never >= 38.2; rates per wearer-month), + the low-kappa third.
  DRINK  : eval_drink.metrics' frozen-binary branch (S1 median-person DRINK screen onsets/day and minutes/day; S2 core-38
           sensitivity of any DRINK/COOL/DANGER display in [t-45, t+10]; informed = display or a nudge in the last 120 min).
usage: eval_r6_style.py OUT_TAG name=binary [name=binary ...]   -> tests/out/eval_r6_style_<OUT_TAG>.json"""
import json, os, subprocess, sys, tempfile
from multiprocessing import Pool
import numpy as np, pandas as pd, pyarrow.parquet as pq
HERE = os.path.dirname(os.path.abspath(__file__)); G = os.path.dirname(HERE); ROOT = os.path.dirname(G); R6 = os.path.join(ROOT, "research", "r6")
sys.path.insert(0, R6); sys.path.insert(0, os.path.join(G, "py"))
from common import IDX, PERS, load, events          # R6 (DEV only)
from build_cache import csv_for, profile_of, IX
SIM = os.path.join(ROOT, "sim", "data")
BINS = dict(a.split("=", 1) for a in sys.argv[2:])
COLS = ["state", "level"]

def run_one(args):
    pid, rg = args
    g = pq.ParquetFile(os.path.join(SIM, "minutes_dev_v4.parquet")).read_row_group(rg).to_pandas().sort_values("t_min")
    assert int(g.person_id.iloc[0]) == pid
    P = PERS.loc[pid].to_dict(); prof = profile_of(P); rest = float(P["hr_rest"])
    hr0 = g.HR_meas.values.astype(float); hr1 = rest + np.random.default_rng(20261112 + pid).uniform(0.6, 1.0) * (hr0 - rest)
    out = {}
    with tempfile.TemporaryDirectory() as td:
        for hk, hr in (("raw", hr0), ("sc", hr1)):
            with open(td + "/i.csv", "w") as fh:
                fh.write("#PROFILE,%r,%r,%r,%d\n#TWIN,70,0.12,0,0.15%s\nmod,...\n" % (prof["age"], prof["sex_m"], prof["bmi"], prof["med_flags"], ",nan" * 24))
                np.savetxt(fh, csv_for(g, hr), fmt="%.7g", delimiter=",")
            for nm, b in BINS.items():
                subprocess.check_call([b, "replay", td + "/i.csv", td + "/o.csv"])
                o = pd.read_csv(td + "/o.csv", header=None, usecols=[IX[k] for k in COLS]).rename(columns={IX[k]: k for k in COLS})
                out[(nm, hk)] = (o.state.values.astype(np.int8), o.level.values.astype(np.int8))
    return pid, out

def drink_metrics(P, res, nm, hk, data):
    per, sens, inf = [], [], []
    for p in P:
        d = data[p]; st, lv = res[p][(nm, hk)]
        dd_ = st == 1; cp_ = lv >= 2
        on = dd_ & ~np.concatenate([[False], dd_[:-1]]); types = d["types"]; day = d["day"]
        s1 = [dy for dy in range(1, 11) if types[dy - 1] == "S1"]
        if s1: per.append((np.mean([on[day == dy].sum() for dy in s1]), np.mean([dd_[day == dy].sum() for dy in s1])))
        disp = dd_ | cp_; nud = np.zeros(len(on), bool)
        for i in np.where(on)[0]: nud[i:i + 121] = True
        for (ts, te, dy) in events(p, "core38"):
            if not types[dy - 1].startswith("S2"): continue
            i = ts - d["t0"]; a = max(0, i - 45); b = min(len(disp), i + 11); h = bool(disp[a:b].any()); sens.append(h); inf.append(h or bool(nud[min(i, len(nud) - 1)]))
    per = np.array(per)
    return dict(drink_per_day_median=float(np.median(per[:, 0])), drink_min_median=float(np.median(per[:, 1])),
                drink_per_day_mean=float(per[:, 0].mean()), drink_min_mean=float(per[:, 1].mean()), s2_events=len(sens),
                s2_sens=float(np.mean(sens)), s2_informed=float(np.mean(inf)))

def main():
    import final_danger as FD
    P = IDX["persons"]; f = pq.ParquetFile(os.path.join(SIM, "minutes_dev_v4.parquet"))
    rg = {int(f.metadata.row_group(i).column(0).statistics.min): i for i in range(f.metadata.num_row_groups)}
    with Pool(int(os.environ.get("HG_WORKERS", "2"))) as pool: res = dict(pool.map(run_one, [(p, rg[p]) for p in P], chunksize=1))
    data = {p: load(p) for p in P}
    cuts = np.quantile(PERS.loc[P, "kappa_core"], [1 / 3, 2 / 3]); low = [p for p in P if PERS.loc[p, "kappa_core"] < cuts[0]]
    out = {}
    for nm in BINS:
        for hk in ("raw", "sc"):
            rows = FD.per_person({p: res[p][(nm, hk)][1] >= 3 for p in P}, data)
            s = FD.summ(rows, boot=400); sl = FD.summ(rows, low)
            out["%s|%s" % (nm, hk)] = dict(danger=s, danger_low_kappa=sl, drink=drink_metrics(P, res, nm, hk, data))
            print("%-10s %-3s Danger: heat-wave %d/%d = %.2f [%s] all %.2f lead %s | strict FA %.1f/mo [%s] empty %.1f | low-k %d ev %.2f | "
                  "DRINK %.2f/day %.0f min (mean %.2f / %.0f) S2 %.3f inf %.3f" % (
                      nm, hk, s["hit_S2"], s["n_S2"], s["sens_S2"], "-".join("%.2f" % x for x in s["ci_sens_S2"]), s["sens"], s["lead"],
                      s["fa_month"], "-".join("%.1f" % x for x in s["ci_fa"]), s["empty_month"], sl["n"], sl["sens"],
                      out["%s|%s" % (nm, hk)]["drink"]["drink_per_day_median"], out["%s|%s" % (nm, hk)]["drink"]["drink_min_median"],
                      out["%s|%s" % (nm, hk)]["drink"]["drink_per_day_mean"], out["%s|%s" % (nm, hk)]["drink"]["drink_min_mean"],
                      out["%s|%s" % (nm, hk)]["drink"]["s2_sens"], out["%s|%s" % (nm, hk)]["drink"]["s2_informed"]), flush=True)
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    json.dump(dict(label="SIMULATION DEV v4 - R6's 110 persons, R6 scoring", persons=len(P), table=out),
              open(os.path.join(HERE, "out", "eval_r6_style_%s.json" % sys.argv[1]), "w"), indent=1, default=float)

if __name__ == "__main__":
    main()
