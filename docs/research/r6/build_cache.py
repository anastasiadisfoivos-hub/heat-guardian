#!/usr/bin/env python3
"""R6 cache builder - SIMULATION, DEV ONLY (Virtual Elders v4). Never opens a *sealed* file.
DEV whitelist = person ids in scenarios_dev_v4.parquet. Replays each chosen DEV person through the FROZEN freeze-3 host
binary (guardian/c/build/m7_pd_20, read-only) with raw HR and with the M3.2 HR-rise scaling (same seed rule as eval_sim_m7.py),
and stores sensors + truth + frozen per-minute outputs in cache/p<id>.npz.
Persons: every DEV person with a core385 event (43) + calibration persons (not gradient-trained by hg2) up to N."""
import json, os, subprocess, sys, tempfile
from multiprocessing import Pool
import numpy as np, pandas as pd, pyarrow.parquet as pq
ROOT = "/home/claude/hg_ai"; SIM = ROOT + "/sim/data"; HERE = os.path.dirname(os.path.abspath(__file__))
BIN = ROOT + "/guardian/c/build/m7_pd_20"
sys.path.insert(0, ROOT + "/guardian/py")
from trace_io import OUTCOLS
IX = {k: i for i, k in enumerate(OUTCOLS)}
KEEP = ["state", "level", "tiers", "check_min", "check_reason", "alarm_id", "worn", "core_now", "core_20", "sd_now", "logit_p38",
        "logit_p385", "strain", "v12_est", "v12_f20", "v12_z", "t_air_corr", "env_run", "env_dose", "valid", "hr_valid", "flux_valid"]
SENS = ["t_min", "day", "minute_of_day", "T1", "T2", "T_air_meas", "RH_meas", "HR_meas", "hr_quality", "PI", "a_std_g", "zangle_deg"]
TRUTH = ["T_core", "HR_true", "met", "T_in", "RH_in", "location", "activity_class", "asleep", "fan", "worn_truth", "s_skbf", "w",
         "deficit_pct", "drink_mL", "T_deep_wrist"]

def profile_of(p):
    f = (1 if (p.get("med_bb_nonsel", 0) or p.get("med_bb_sel", 0)) else 0) | (2 if p.get("med_diuretic", 0) else 0) \
        | (4 if p.get("med_antichol", 0) else 0) | (8 if p.get("med_ace_arb", 0) else 0)
    return dict(age=float(p["age"]), sex_m=float(p["sex_m"]), bmi=float(p["bmi"]), med_flags=int(f))

def csv_for(g, hr):
    n = len(g); z = g.zangle_deg.values.astype(float); zp = np.concatenate([[z[0]], z[:-1]])
    zs = np.stack([zp + (z - zp) * (k + 1) / 12.0 for k in range(12)], 1)
    t1, t2, ta = g.T1.values, g.T2.values, g.T_air_meas.values
    sc = np.column_stack([g.minute_of_day.values, t1, t2, ta, g.RH_meas.values, hr, g.hr_quality.values, g.PI.values, g.a_std_g.values,
                          np.ones(n), np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n), np.full(n, 3.9), np.full(n, -1), np.full(n, 255), np.zeros(n)])
    return np.column_stack([sc, np.repeat(t1[:, None], 12, 1), np.repeat(t2[:, None], 12, 1), np.repeat(ta[:, None], 12, 1), zs])

def run(args):
    rg, pid = args
    out = "%s/cache/p%d.npz" % (HERE, pid)
    if os.path.exists(out): return pid
    f = pq.ParquetFile(SIM + "/minutes_dev_v4.parquet"); g = f.read_row_group(rg).to_pandas().sort_values("t_min")
    assert int(g.person_id.iloc[0]) == pid
    P = pd.read_parquet(SIM + "/persons.parquet").set_index("person_id").loc[pid].to_dict(); prof = profile_of(P)
    rest = float(P["hr_rest"]); fct = np.random.default_rng(20261112 + pid).uniform(0.6, 1.0)
    hr0 = g.HR_meas.values.astype(float); hr1 = rest + fct * (hr0 - rest)
    d = {k: g[k].values for k in SENS + TRUTH}; d["hr_scaled"] = hr1; d["hr_fct"] = fct
    with tempfile.TemporaryDirectory() as td:
        for hk, hr in (("raw", hr0), ("sc", hr1)):
            with open(td + "/i.csv", "w") as fh:
                fh.write("#PROFILE,%r,%r,%r,%d\n#TWIN,70,0.12,0,0.15%s\nmod,...\n" % (prof["age"], prof["sex_m"], prof["bmi"], prof["med_flags"], ",nan" * 24))
                np.savetxt(fh, csv_for(g, hr), fmt="%.7g", delimiter=",")
            subprocess.check_call([BIN, "replay", td + "/i.csv", td + "/o.csv"])
            o = pd.read_csv(td + "/o.csv", header=None, usecols=[IX[k] for k in KEEP]).rename(columns={IX[k]: k for k in KEEP})
            assert len(o) == len(g), (pid, hk, len(o), len(g))
            for k in KEEP: d["%s_%s" % (hk, k)] = o[k].values.astype(np.float32)
    np.savez_compressed(out, **d); return pid

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    scen = pd.read_parquet(SIM + "/scenarios_dev_v4.parquet"); dev = set(scen.person_id)
    E = pd.read_parquet(SIM + "/events_dev_v4.parquet"); ev = sorted(set(E[E.type == "core385"].person_id))
    meta = json.load(open(ROOT + "/model/cache/v4aug/sim_meta.json")); val = [p for p in meta["val_ids"] if p not in ev]
    chosen = (ev + val)[:n]; assert set(chosen) <= dev
    f = pq.ParquetFile(SIM + "/minutes_dev_v4.parquet")
    rg_pid = [int(f.read_row_group(i, columns=["person_id"]).column(0)[0].as_py()) for i in range(f.metadata.num_row_groups)]
    jobs = [(i, p) for i, p in enumerate(rg_pid) if p in set(chosen)]
    with Pool(2) as pool: done = pool.map(run, jobs)
    json.dump(dict(persons=sorted(done), ev385_persons=ev, train_ids_in=[p for p in done if p in set(meta["train_ids"]) | set(meta["es_ids"])],
                   label="SIMULATION DEV v4"), open(HERE + "/cache/index.json", "w"))
    print(len(done), "persons cached;", len(ev), "with core385")
if __name__ == "__main__": main()
