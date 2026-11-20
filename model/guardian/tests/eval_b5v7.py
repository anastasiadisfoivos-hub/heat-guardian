#!/usr/bin/env python3
"""[B5-v7] DEV evaluator for Guardian Loop variants on SIM-DEV v5 - SIMULATION (Virtual Elders v5; known too-tolerant at humid rest,
bed rest and HR). Never opens a sealed file (sealed ids asserted absent, set-1 seal + set-4/5 ids are not in the DEV file).

Scores every build with the PRE-REGISTERED sealed-exam protocol (sealed_exam_system.score_person / aggregate, unchanged) driven by
the C replay (C == Python is checked separately: parity_sim_long / golden / fastmath), plus the FROZEN.txt SIM-DEV rows' metrics
(S1 Danger per wearer-month, mean person; false Danger per wearer-month over all day classes).

Person sets (DEV only):  tune = the 150 persons of eval_sim_m7 (all anomaly persons + an even stride; = FROZEN.txt SIM-DEV v5 rows)
                         check = the other DEV persons (never used to choose a value; reported as a second DEV opinion)
usage: eval_b5v7.py --builds name=binary,... --set tune|check|all [--n N] [--dump DIR] --tag TAG
"""
import argparse, json, os, subprocess, sys, tempfile
from multiprocessing import Pool
import numpy as np, pandas as pd, pyarrow.parquet as pq
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "py")); sys.path.insert(0, HERE)
from trace_io import OUTCOLS
from sim_adapter import profile_of, sealed_ids
import sealed_exam_system as SE
SIM = "/home/claude/hg_ai/sim/data"; MIN = "minutes_dev_v5.parquet"; EVT = "events_dev_v5.parquet"; SCN = "scenarios_dev_v5.parquet"
SHA_MIN = "cff1dcf09535532465ff2bc8da0d593d29308a40d5eea8003a374ffa9a983ee6"
IX = {k: i for i, k in enumerate(OUTCOLS)}
COLS = ["person_id", "day", "minute_of_day", "t_min", "T_in", "T_core", "T1", "T2", "T_air_meas", "RH_meas", "HR_meas", "hr_quality", "PI",
        "a_std_g", "zangle_deg"]
KEEP = ("state", "level", "tiers", "check_min", "check_reason", "worn", "alarm_id")
DUMP = ("core_20", "v12_f20", "v12_z", "t_air_corr", "env_dose", "env_run", "valid", "x14", "x10")


def csv_for(g, hr):
    n = len(g); z = g.zangle_deg.values.astype(float); zp = np.concatenate([[z[0]], z[:-1]])
    zs = np.stack([zp + (z - zp) * (k + 1) / 12.0 for k in range(12)], 1)
    t1, t2, ta = g.T1.values, g.T2.values, g.T_air_meas.values
    sc = np.column_stack([g.minute_of_day.values, t1, t2, ta, g.RH_meas.values, hr, g.hr_quality.values, g.PI.values, g.a_std_g.values,
                          np.ones(n), np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n), np.full(n, 3.9), np.full(n, -1), np.full(n, 255), np.zeros(n)])
    return np.column_stack([sc, np.repeat(t1[:, None], 12, 1), np.repeat(t2[:, None], 12, 1), np.repeat(ta[:, None], 12, 1), zs])


def run_person(args):
    rg, builds, dump = args
    f = pq.ParquetFile(os.path.join(SIM, MIN)); g = f.read_row_group(rg, columns=COLS).to_pandas().sort_values("t_min").reset_index(drop=True)
    pid = int(g.person_id.iloc[0]); assert pid not in sealed_ids()
    P = pd.read_parquet(os.path.join(SIM, "persons.parquet")).set_index("person_id").loc[pid].to_dict(); prof = profile_of(P)
    types = pd.read_parquet(os.path.join(SIM, SCN)).set_index("person_id").loc[pid, "day_types_1_to_N"].split(",")
    E = pd.read_parquet(os.path.join(SIM, EVT)); E = E[E.person_id == pid]
    t0 = int(g.t_min.values[0]); n = len(g); day = g.day.values.astype(int); mod = g.minute_of_day.values.astype(int)
    rest = float(P["hr_rest"]); fct = np.random.default_rng(SE.RNG_SEED + pid).uniform(0.6, 1.0)
    hr0 = g.HR_meas.values.astype(float); hr1 = rest + fct * (hr0 - rest)
    dtype = np.array([types[d - 1] for d in day]); cls = {c: dtype == c for c in ("S1", "PRE", "POST")}
    cls["S2"] = np.char.startswith(dtype.astype(str), "S2")
    s3 = np.zeros(n, bool); s3w = []; tin = g.T_in.values.astype(float)
    for d in sorted(set(day)):
        a = np.where((day == d) & (mod >= 1380))[0]; b = np.where((day == d + 1) & (mod < 420))[0]; w = np.concatenate([a, b])
        if len(w) >= 60 and np.nanmedian(tin[w]) >= SE.S3_TIN_C: s3[w] = True; s3w.append(w)
    s4 = np.zeros(n, bool); s4w = []
    for e in E[E.type == "errand"].itertuples():
        w = np.arange(max(0, int(e.t_start) - t0), min(n, int(e.t_end) + 61 - t0))
        if len(w): s4[w] = True; s4w.append(w)
    cls["S3"] = s3; cls["S4"] = s4
    anom = list(E[E.type == "anomaly"].itertuples()); cls["S9"] = np.isin(day, list(set(int(e.day) for e in anom)))
    evs = {k: [(int(e.t_start) - t0, int(e.t_end) - t0) for e in E[E.type == k].itertuples()] for k in ("core38", "core385")}
    out = dict(pid=pid, med=int(prof["med_flags"]), kappa=float(P.get("kappa_core", np.nan)), res={})
    zero_pm = np.zeros((n, 3), int); zero_ton = np.zeros((n, 3), bool)
    with tempfile.TemporaryDirectory() as d:
        for hk, hr in (("hr_raw", hr0), ("hr_scaled", hr1)):
            with open(d + "/i.csv", "w") as fh:
                fh.write("#PROFILE,%r,%r,%r,%d\n#TWIN,70,0.12,0,0.15%s\nmod,...\n" % (prof["age"], prof["sex_m"], prof["bmi"], prof["med_flags"], ",nan" * 24))
                np.savetxt(fh, csv_for(g, hr), fmt="%.7g", delimiter=",")
            for name, binary in builds.items():
                subprocess.check_call([binary, "replay", d + "/i.csv", d + "/o.csv"])
                cols = list(KEEP) + (list(DUMP) if dump else [])
                o = pd.read_csv(d + "/o.csv", header=None, usecols=[IX[k] for k in cols]).rename(columns={IX[k]: k for k in cols})
                st, lv, cr, cm, worn = (o[k].values.astype(int) for k in ("state", "level", "check_reason", "check_min", "worn"))
                R = SE.score_person(st, lv, cr, cm, worn, zero_pm, zero_ton, day, dtype, cls, s3w, s4w, evs, anom, t0, 0)
                # FROZEN.txt SIM-DEV row metrics: Danger display onsets on S1 days; family alerts (new alarm id while a CHECK runs)
                g_on = (lv >= 3) & (np.concatenate([[0], lv[:-1]]) < 3); aid = o.alarm_id.values
                f_on = (aid != np.concatenate([[aid[0]], aid[:-1]])) & (cm != 255)
                R["s1_days"] = int(len(set(day[cls["S1"]]))); R["s1_danger"] = int(g_on[cls["S1"]].sum()); R["s1_family"] = int(f_on[cls["S1"]].sum())
                R["drink_on_s1"] = int(((st == 1) & ~np.concatenate([[False], st[:-1] == 1]))[cls["S1"]].sum())
                R["ev385"] = [dict(cls=str(dtype[s])[:2], danger=int((lv[max(0, s - 45):min(n, s + 11)] >= 3).any()),
                                   family=int(f_on[max(0, s - 45):min(n, s + 16)].any())) for s, e in evs["core385"] if 0 <= s < n]
                out["res"][(name, hk)] = R
                if dump:
                    np.savez_compressed(os.path.join(dump, "p%d_%s_%s.npz" % (pid, name, hk)), **{k: o[k].values for k in cols},
                                        T_core=g.T_core.values.astype(np.float32), day=day, mod=mod, dtype=dtype.astype(str),
                                        T1=g.T1.values.astype(np.float32), T2=g.T2.values.astype(np.float32), tair=g.T_air_meas.values.astype(np.float32),
                                        rh=g.RH_meas.values.astype(np.float32), astd=g.a_std_g.values.astype(np.float32), hr=hr.astype(np.float32),
                                        tin=tin.astype(np.float32))
    return out


def persons_of(which, n):
    E = pd.read_parquet(os.path.join(SIM, EVT)); anom_p = sorted(set(E[E.type == "anomaly"].person_id))
    f = pq.ParquetFile(os.path.join(SIM, MIN))
    rg_pid = [int(f.metadata.row_group(i).column(0).statistics.min) for i in range(f.metadata.num_row_groups)]
    assert not set(rg_pid) & sealed_ids()
    others = [p for p in rg_pid if p not in anom_p]; k = max(0, 150 - len(anom_p))
    tune = set(anom_p) | set(others[:: max(1, len(others) // max(k, 1))][:k])   # = eval_sim_m7 150 selection
    sel = tune if which == "tune" else (set(rg_pid) - tune if which == "check" else set(rg_pid))
    rgs = [i for i, p in enumerate(rg_pid) if p in sel]
    return rgs[:n] if n else rgs


def summarise(res, name, hk, sub=None):
    rr = [r for r in res if sub is None or sub(r)]
    if not rr or not any(r["res"][(name, hk)]["s1_days"] for r in rr): return None
    A = SE.aggregate([dict(pid=r["pid"], modes={hk: r["res"][(name, hk)]}) for r in rr], hk)
    day_cls = [c for c in ("S1", "PRE", "POST", "S2") if c in A]
    fa = sum(A[c]["tiers"]["DANGER"]["false_alarms"] for c in day_cls); wh = sum(A[c]["worn_h"] for c in day_cls)
    s1 = [r["res"][(name, hk)] for r in rr if r["res"][(name, hk)]["s1_days"]]
    ev = [e for r in rr for e in r["res"][(name, hk)]["ev385"]]; ev2 = [e for e in ev if e["cls"] == "S2"]
    T = lambda c, t, k: (A.get(c, {}).get("tiers", {}).get(t, {}) or {}).get(k)
    return dict(persons=len(rr),
                S2_danger_sens=T("S2", "DANGER", "sensitivity_pct"), S2_danger_k=T("S2", "DANGER", "detected"), S2_danger_n=T("S2", "DANGER", "events"),
                S2_cool_sens=T("S2", "COOL", "sensitivity_pct"), S2_drink_sens=T("S2", "DRINK", "sensitivity_pct"),
                S2_display=A.get("S2", {}).get("s2_display_sensitivity_pct"),
                S4_drink_fa=T("S4", "DRINK", "fa_per_h"), S4_cool_fa=T("S4", "COOL", "fa_per_h"), S4_danger_fa=T("S4", "DANGER", "fa_per_h"),
                S1_drink_day=A["budgets"]["S1_drink_per_day"], S1_drink_min=A["budgets"]["S1_drink_min_per_day"],
                S1_drink_day_mean=float(np.mean([x["drink_on_s1"] / x["s1_days"] for x in s1])),
                S1_drink_fa=T("S1", "DRINK", "fa_per_h"), S1_danger_fa=T("S1", "DANGER", "fa_per_h"), S2_danger_fa=T("S2", "DANGER", "fa_per_h"),
                S1_cool_week=A["budgets"]["S1_cool_per_week"], S1_check_week=A["budgets"]["S1_check_per_week"], S9=A["budgets"]["S9_sens"],
                danger_month_s1_mean=float(30 * np.mean([x["s1_danger"] / x["s1_days"] for x in s1])),
                family_month_s1_mean=float(30 * np.mean([x["s1_family"] / x["s1_days"] for x in s1])),
                false_danger_month_all=720.0 * fa / wh if wh else None,
                ev385_danger_all=100 * np.mean([e["danger"] for e in ev]) if ev else None,
                ev385_family_s2=100 * np.mean([e["family"] for e in ev2]) if ev2 else None)


def main():
    a = argparse.ArgumentParser(); a.add_argument("--builds", required=True); a.add_argument("--set", default="tune")
    a.add_argument("--n", type=int, default=0); a.add_argument("--dump", default=None); a.add_argument("--tag", required=True)
    a.add_argument("--workers", type=int, default=2); a.add_argument("--pids", default=None, help="comma list of DEV person ids (diagnostics)"); a.add_argument("--out", default=os.path.join(HERE, "out"))
    o = a.parse_args()
    builds = dict(x.split("=", 1) for x in o.builds.split(","))
    if o.dump: os.makedirs(o.dump, exist_ok=True)
    rgs = persons_of(o.set, o.n)
    if o.pids:
        want = set(int(x) for x in o.pids.split(",")); f = pq.ParquetFile(os.path.join(SIM, MIN))
        rgs = [i for i in range(f.metadata.num_row_groups) if int(f.metadata.row_group(i).column(0).statistics.min) in want]
    with Pool(o.workers) as pool: res = pool.map(run_person, [(i, builds, o.dump) for i in rgs], chunksize=1)
    table = {}
    for name in builds:
        for hk in ("hr_raw", "hr_scaled"):
            table["%s|%s" % (name, hk)] = summarise(res, name, hk)
            table["%s|%s|bb" % (name, hk)] = summarise(res, name, hk, lambda r: r["med"] & 1)
    out = dict(label="SIMULATION (Virtual Elders v5; known too-tolerant at humid rest, bed rest and HR) - SIM-DEV v5 %s set, sealed-exam "
                     "protocol scoring via C replay" % o.set, set=o.set, persons=len(res), builds=builds, table=table)
    os.makedirs(o.out, exist_ok=True)
    json.dump(out, open(os.path.join(o.out, "eval_b5v7_%s.json" % o.tag), "w"), indent=1, default=float)
    print("persons", len(res), "set", o.set)
    for k, r in table.items():
        if k.endswith("|bb") or r is None: continue
        print("%-22s S2Dng %5.1f%% (%s/%s) COOL %5.1f disp %5.1f | S4 FA/h D %.3f C %.3f G %.3f | S1 DRINK/d %.2f (mean %.2f) %3.0f min | "
              "Dng/mo S1 %.2f falseAll %.2f | ev385 %.1f fam %.1f | S9 %.0f"
              % (k, r["S2_danger_sens"] or 0, r["S2_danger_k"], r["S2_danger_n"], r["S2_cool_sens"] or 0, r["S2_display"] or 0, r["S4_drink_fa"] or 0,
                 r["S4_cool_fa"] or 0, r["S4_danger_fa"] or 0, r["S1_drink_day"], r["S1_drink_day_mean"], r["S1_drink_min"], r["danger_month_s1_mean"],
                 r["false_danger_month_all"] or 0, r["ev385_danger_all"] or 0, r["ev385_family_s2"] or 0, r["S9"] or 0))


if __name__ == "__main__":
    main()
