#!/usr/bin/env python3
"""M12 DRINK attribution on SIM-DEV v4 (SIMULATION; Virtual Elders v4, known too-tolerant at humid rest, bed rest and HR).
Same 150 DEV persons as eval_sim_m7.py (all S9-anomaly persons + stride), raw and HR-scaled HR, ablation binaries from
build_ablation.sh. Truth columns (activity_class, location, T_in) are read ONLY to describe when DRINK onsets happen;
they never enter the band. No threshold is changed."""
import json, os, subprocess, sys, tempfile, collections
from multiprocessing import Pool
import numpy as np, pandas as pd, pyarrow.parquet as pq
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, os.path.join(HERE, "..", "..", "py"))
os.environ.setdefault("HG_SIM_VERSION", "v4")
import eval_sim_m7 as E
from trace_io import OUTCOLS
BIN = os.path.join(HERE, "bin"); CONF = ["a_nn_only", "b_v12_only", "c_both", "d_both_base363", "e_both_oldweights"]
IX = {k: i for i, k in enumerate(OUTCOLS)}; IA, IAN = len(OUTCOLS), len(OUTCOLS) + 1
ACT = {0: "sleep", 1: "lying", 2: "sit", 3: "stand", 4: "adl", 5: "walk"}; LOC = {0: "home", 1: "transit", 2: "out"}

def run_person(args):
    rg, chosen = args
    f = pq.ParquetFile(os.path.join(E.SIM, E.MIN))
    g = f.read_row_group(rg, columns=E.COLS + ["activity_class", "location", "T_in"]).to_pandas().sort_values("t_min")
    pid = int(g.person_id.iloc[0])
    if pid not in chosen: return None
    assert pid not in E.sealed_ids()
    P = pd.read_parquet(os.path.join(E.SIM, "persons.parquet")).set_index("person_id").loc[pid].to_dict(); prof = E.profile_of(P)
    types = pd.read_parquet(os.path.join(E.SIM, E.SCN)).set_index("person_id").loc[pid, "day_types_1_to_N"].split(",")
    EV = pd.read_parquet(os.path.join(E.SIM, E.EVT)); EV = EV[EV.person_id == pid]
    ev38 = list(EV[EV.type == "core38"].itertuples()); anom = list(EV[EV.type == "anomaly"].itertuples())
    rest = float(P["hr_rest"]); fct = np.random.default_rng(20261112 + pid).uniform(0.6, 1.0)
    hr0 = g.HR_meas.values.astype(float); hr1 = rest + fct * (hr0 - rest)
    out = dict(pid=pid, res={}, onsets={}, base={})
    day = g.day.values
    with tempfile.TemporaryDirectory() as d:
        for hk, hr in (("hr_raw", hr0), ("hr_scaled", hr1)):
            with open(d + "/i.csv", "w") as fh:
                fh.write("#PROFILE,%r,%r,%r,%d\n#TWIN,70,0.12,0,0.15%s\nmod,...\n" % (prof["age"], prof["sex_m"], prof["bmi"], prof["med_flags"], ",nan" * 24))
                np.savetxt(fh, E.csv_for(g, prof, hr), fmt="%.7g", delimiter=",")
            for name in CONF:
                subprocess.check_call([os.path.join(BIN, name), "replay", d + "/i.csv", d + "/o.csv"])
                raw = pd.read_csv(d + "/o.csv", header=None)
                o = raw[[IX[k] for k in E.NAMES]].rename(columns={IX[k]: k for k in E.NAMES})
                out["res"][(name, hk)] = E.metrics(o, g, types, ev38, anom, int(g.t_min.values[0]))
                out["base"][(name, hk)] = (float(raw[IA].values[-1]), int(raw[IAN].values[-1]))
                if name in ("c_both", "d_both_base363"):
                    st = o.state.values; on = np.where((st == 1) & np.concatenate([[False], st[:-1] != 1]))[0]
                    bits = raw[IX["routine_req"]].values
                    rows = []
                    for i in on:
                        if types[int(day[i]) - 1] != "S1": continue
                        # path that drove the tier: conditions are true at the onset (2nd consecutive minute) and the minute before
                        b = int(bits[i]) | int(bits[i - 1] if i else 0)
                        path = ("v12+nn" if (b & 64 and b & 128) else "v12" if b & 64 else "nn" if b & 128 else "other(env)")
                        rows.append((path, int(g.minute_of_day.values[i] // 60), ACT.get(int(g.activity_class.values[i]), "?"),
                                     LOC.get(int(g.location.values[i]), "?"), float(g.T_in.values[i])))
                    out["onsets"][(name, hk)] = rows
    return out

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    EVA = pd.read_parquet(os.path.join(E.SIM, E.EVT)); anom_p = sorted(set(EVA[EVA.type == "anomaly"].person_id))
    f = pq.ParquetFile(os.path.join(E.SIM, E.MIN))
    rg_pid = [int(f.read_row_group(i, columns=["person_id"]).column(0)[0].as_py()) for i in range(f.metadata.num_row_groups)]
    assert not set(rg_pid) & E.sealed_ids()
    others = [p for p in rg_pid if p not in anom_p]; k = max(0, n - len(anom_p))
    chosen = set(anom_p) | set(others[:: max(1, len(others) // max(k, 1))][:k])
    with Pool(int(os.environ.get("HG_WORKERS", "2"))) as pool:
        res = [r for r in pool.map(run_person, [(i, chosen) for i in range(len(rg_pid))]) if r]
    table = {}
    for key in res[0]["res"]:
        rows, sens, s9 = [], [], []
        for r in res:
            per, se, s = r["res"][key]
            for p in per: p["person"] = r["pid"]; rows.append(p)
            sens += se; s9 += s
        table["%s|%s" % key] = E.summarise(rows, sens, s9)
    attrib = {}
    for key in res[0]["onsets"]:
        on = [x for r in res for x in r["onsets"][key]]
        c = lambda i: dict(collections.Counter(x[i] for x in on).most_common())
        tin = np.array([x[4] for x in on]) if on else np.zeros(0)
        attrib["%s|%s" % key] = dict(n_onsets_S1=len(on), path=c(0), hour=dict(sorted(collections.Counter(x[1] for x in on).items())),
                                     activity=c(2), location=c(3), T_in_median=float(np.median(tin)) if len(tin) else None,
                                     T_in_share_ge_30=float(np.mean(tin >= 30)) if len(tin) else None)
    bases = {}
    for key in res[0]["base"]:
        b = [r["base"][key] for r in res]; learned = [x for x, nn in b if nn > 0]
        bases["%s|%s" % key] = dict(learned=len(learned), persons=len(b), at_lower_bound=int(sum(1 for x in learned if x <= (36.3 if "363" in key[0] else 36.8) + 1e-4)),
                                    median=float(np.median(learned)) if learned else None, p10=float(np.percentile(learned, 10)) if learned else None)
    out = dict(label="SIMULATION (Virtual Elders v4; known too-tolerant at humid rest, bed rest, and HR) - SIM-DEV v4, M12 ablations",
               persons=len(res), table=table, attribution=attrib, calm_base=bases)
    json.dump(out, open(os.path.join(HERE, "eval_m12_v4_%d.json" % n), "w"), indent=1, default=float)
    for key, r in table.items():
        print("%-30s DRINK/d %4.1f  min/d %5.0f  S2 %5.1f%%  COOL/wk %.1f" % (key, r["drink_per_day"], r["drink_min_per_day"], r["s2_sens_display"] or 0, r["cool_per_week"]))
    for key, a in attrib.items(): print(key, json.dumps(a))
    for key, b in bases.items(): print(key, json.dumps(b))

if __name__ == "__main__":
    main()
