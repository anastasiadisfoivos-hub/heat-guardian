#!/usr/bin/env python3
"""M7 evaluation on SIM-DEV v3 - SIMULATION (Virtual Elders v3; known too-tolerant at humid rest, bed rest and HR).
Frozen v3 files (minutes_dev_v3 / events_dev_v3 / scenarios_dev_v3), SHA-256 asserted; sealed files never opened.
Persons: all S9-anomaly DEV persons + an even stride of the rest up to N. Each person is replayed through every build in
CONFIGS (C, host_test replay), with and without the M3.2 HR-rise scaling (HR_meas' = rest + f (HR_meas - rest), f ~ U(0.6, 1.0)
seeded per person: the V4 sim-HR-too-high sensitivity analysis). Inputs are sensor columns only.
Metrics (M1.4 budgets; S1 days, median person): DRINK episodes/day (onsets of the DRINK screen) <= 1, DRINK screen min/day <= 60,
COOL onsets/week <= 1, CHECK starts/wearer-week <= 1; S2: sensitivity to core38 events >= 85 % (display: a DRINK/COOL/DANGER
screen in [event-45, event+10] min; informed: display OR DRINK tier on at the event with a nudge in the previous 120 min);
S9: routine CHECK started in [anomaly start, anomaly end + 90 min] for >= 90 % of anomaly days.
usage: eval_sim_m7.py N_PERSONS TAG   (builds listed in CONFIGS must exist: see build_m7.sh)"""
import hashlib, json, os, subprocess, sys, tempfile
from multiprocessing import Pool
import numpy as np, pandas as pd, pyarrow.parquet as pq
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "py"))
from trace_io import OUTCOLS
from sim_adapter import profile_of, sealed_ids
SIM = "/home/claude/hg_ai/sim/data"; OUT = os.path.join(HERE, "out"); BUILD = os.environ.get("HG_M7_BUILD", os.path.join(HERE, "..", "c", "build"))
V = os.environ.get("HG_SIM_VERSION", "v4")   # M11: final training sim v4 (v3 kept for the M7/M9 rows)
MIN, EVT, SCN = "minutes_dev_%s.parquet" % V, "events_dev_%s.parquet" % V, "scenarios_dev_%s.parquet" % V
SHA_MIN = {"v3": "ac2778626bfdd63ea52715db73acbff9c4b5d71fecd8a518346e88bdd9f6f208",
           "v4": "2bce61d1b08e6d2d978c06bc25a09350ebda6f977288dfdf863559b5ce7911b9",
           "v5": "cff1dcf09535532465ff2bc8da0d593d29308a40d5eea8003a374ffa9a983ee6"}[V]   # v5: B2b-v5 (DEV only, --dev-only)   # sim/data/README.md
CONFIGS = json.load(open(os.path.join(BUILD, "m7_builds.json")))["configs"]       # name -> binary
IX = {k: i for i, k in enumerate(OUTCOLS)}
COLS = ["person_id", "day", "minute_of_day", "t_min", "T_core", "T1", "T2", "T_air_meas", "RH_meas", "HR_meas", "hr_quality", "PI", "a_std_g", "zangle_deg"]
NAMES = ("state", "level", "tiers", "check_min", "check_reason", "family_alert", "alarm_id")

def csv_for(g, prof, hr):
    n = len(g); z = g.zangle_deg.values.astype(float); zp = np.concatenate([[z[0]], z[:-1]])
    zs = np.stack([zp + (z - zp) * (k + 1) / 12.0 for k in range(12)], 1)
    t1, t2, ta = g.T1.values, g.T2.values, g.T_air_meas.values
    sc = np.column_stack([g.minute_of_day.values, t1, t2, ta, g.RH_meas.values, hr, g.hr_quality.values, g.PI.values, g.a_std_g.values,
                          np.ones(n), np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n), np.full(n, 3.9), np.full(n, -1), np.full(n, 255), np.zeros(n)])
    return np.column_stack([sc, np.repeat(t1[:, None], 12, 1), np.repeat(t2[:, None], 12, 1), np.repeat(ta[:, None], 12, 1), zs])

def metrics(o, g, types, ev38, anom, t0, ev385=()):
    st, lv, tiers, cm, cr = (o[k].values for k in ("state", "level", "tiers", "check_min", "check_reason"))
    fa_ = o["family_alert"].values; g_on = (lv >= 3) & (np.concatenate([[0], lv[:-1]]) < 3)
    # family alert SENT = a new alarm id minted while a CHECK runs (family_pending latches until the phone acks: no acks in replay)
    aid = o["alarm_id"].values; f_on = (aid != np.concatenate([[aid[0]], aid[:-1]])) & (cm != 255)
    drink_scr = st == 1
    d_on = drink_scr & ~np.concatenate([[False], drink_scr[:-1]])
    c_on = (st == 2) & (np.concatenate([[0], st[:-1]]) < 2)   # M19b: COOL nudges actually emitted (COOL screen entered from OK/DRINK = the COOL vibration)
    k_on = (cm == 0) & (np.concatenate([[255], cm[:-1]]) != 0)
    day = g.day.values; per = []
    for dd in sorted(set(day)):
        m = day == dd
        per.append(dict(day=int(dd), dtype=types[int(dd) - 1], drink=int(d_on[m].sum()), drink_min=int(drink_scr[m].sum()),
                        cool=int(c_on[m].sum()), check=int(k_on[m].sum()), check_routine=int((k_on & ((cr & 12) > 0))[m].sum()),
                        check_danger=int((k_on & ((cr & 3) > 0))[m].sum()), danger=int(g_on[m].sum()), family=int(f_on[m].sum()),
                        family_thermal=int((f_on & ((np.concatenate([[0], cr[:-1]]) & 3) > 0))[m].sum())))
    disp = (st == 1) | (st == 2) | (st == 4)
    nudge_recent = pd.Series(d_on.astype(int)).rolling(121, min_periods=1).max().values > 0
    sens = []
    for e in ev38:
        if not types[int(e.day) - 1].startswith("S2"): continue
        a, b = max(0, int(e.t_start) - 45 - t0), min(len(st), int(e.t_start) + 11 - t0); te = min(len(st) - 1, int(e.t_start) - t0)
        sens.append((int(disp[a:b].any()), int(disp[a:b].any() or ((tiers[te] & 1) and nudge_recent[te]))))
    s9 = []
    for e in anom:
        a, b = max(0, int(e.t_start) - t0), min(len(st), int(e.t_end) + 91 - t0)
        s9.append(int((k_on[a:b] & ((cr[a:b] & 12) > 0)).any()))
    s385 = []   # M13: ev385 -> DANGER display in [t-45, t+10], family alert raised in [t-45, t+15], lead of the DANGER display
    for e in ev385:
        a, b = max(0, int(e.t_start) - 45 - t0), min(len(st), int(e.t_start) + 11 - t0); w = np.where(lv[a:b] >= 3)[0]
        fb = min(len(st), int(e.t_start) + 16 - t0)
        s385.append(dict(dtype=types[int(e.day) - 1][:2], danger=int(len(w) > 0), family=int(f_on[a:fb].any()),
                         lead=float(int(e.t_start) - t0 - (a + w[0])) if len(w) else None))
    return per, sens, s9, s385

def run_person(args):
    rg, persons_set = args
    f = pq.ParquetFile(os.path.join(SIM, MIN)); g = f.read_row_group(rg, columns=COLS).to_pandas().sort_values("t_min")
    pid = int(g.person_id.iloc[0])
    if pid not in persons_set: return None
    assert pid not in sealed_ids()
    P = pd.read_parquet(os.path.join(SIM, "persons.parquet")).set_index("person_id").loc[pid].to_dict(); prof = profile_of(P)
    types = pd.read_parquet(os.path.join(SIM, SCN)).set_index("person_id").loc[pid, "day_types_1_to_N"].split(",")
    E = pd.read_parquet(os.path.join(SIM, EVT)); E = E[E.person_id == pid]
    ev38 = list(E[E.type == "core38"].itertuples()); ev385 = list(E[E.type == "core385"].itertuples()); anom = list(E[E.type == "anomaly"].itertuples())
    rest = float(P["hr_rest"]); fct = np.random.default_rng(20261112 + pid).uniform(0.6, 1.0)
    hr0 = g.HR_meas.values.astype(float); hr1 = rest + fct * (hr0 - rest)
    out = dict(pid=pid, regime=None, res={})
    with tempfile.TemporaryDirectory() as d:
        for hk, hr in (("hr_raw", hr0), ("hr_scaled", hr1)):
            with open(d + "/i.csv", "w") as fh:
                fh.write("#PROFILE,%r,%r,%r,%d\n#TWIN,70,0.12,0,0.15%s\nmod,...\n" % (prof["age"], prof["sex_m"], prof["bmi"], prof["med_flags"], ",nan" * 24))
                np.savetxt(fh, csv_for(g, prof, hr), fmt="%.7g", delimiter=",")
            for name, binary in CONFIGS.items():
                subprocess.check_call([os.path.join(BUILD, binary), "replay", d + "/i.csv", d + "/o.csv"])
                o = pd.read_csv(d + "/o.csv", header=None, usecols=[IX[k] for k in NAMES]).rename(columns={IX[k]: k for k in NAMES})
                out["res"][(name, hk)] = metrics(o, g, types, ev38, anom, int(g.t_min.values[0]), ev385)
    return out

def summarise(rows, sens, s9, s385=()):
    D = pd.DataFrame(rows); s1 = D[D.dtype == "S1"]; pp = s1.groupby("person").mean(numeric_only=True)
    r = dict(s1_persons=int(len(pp)), drink_per_day=float(pp.drink.median()), drink_min_per_day=float(pp.drink_min.median()),
             cool_per_week=float(7 * pp.cool.median()), check_per_week=float(7 * pp.check.median()),
             check_routine_per_week_mean=float(7 * pp.check_routine.mean()), check_danger_per_week_mean=float(7 * pp.check_danger.mean()),
             drink_per_day_p90=float(pp.drink.quantile(.9)), drink_min_p90=float(pp.drink_min.quantile(.9)))
    S = np.array(sens) if sens else np.zeros((0, 2))
    r.update(s2_events=int(len(S)), s2_sens_display=float(100 * S[:, 0].mean()) if len(S) else None,
             s2_sens_informed=float(100 * S[:, 1].mean()) if len(S) else None,
             s9_days=len(s9), s9_sens=float(100 * np.mean(s9)) if s9 else None)
    D2 = D[D.dtype.str.startswith("S2")]; p2 = D2.groupby("person").mean(numeric_only=True)
    r.update(danger_per_month_s1_mean=float(30 * pp.danger.mean()), danger_per_month_s1_median=float(30 * pp.danger.median()),
             danger_per_week_s1_mean=float(7 * pp.danger.mean()), family_per_month_s1_mean=float(30 * pp.family.mean()),
             danger_per_week_s2_mean=float(7 * p2.danger.mean()) if len(p2) else None, check_per_week_s2=float(7 * p2.check.median()) if len(p2) else None,
             check_danger_per_week_s2_mean=float(7 * p2.check_danger.mean()) if len(p2) else None)
    for cl in ("all", "S1", "S2", "PR", "PO"):
        q = [x for x in s385 if cl == "all" or x["dtype"] == cl]; L = [x["lead"] for x in q if x["lead"] is not None]
        r["ev385_%s" % cl] = dict(events=len(q), danger_sens=100 * np.mean([x["danger"] for x in q]) if q else None,
                                 family_sens=100 * np.mean([x["family"] for x in q]) if q else None, lead_median=float(np.median(L)) if L else None)
    r["meets_s1"] = bool(r["drink_per_day"] <= 1 and r["drink_min_per_day"] <= 60 and r["cool_per_week"] <= 1 and r["check_per_week"] <= 1)
    r["meets_s2"] = bool((r["s2_sens_display"] or 0) >= 85); r["meets_s9"] = bool((r["s9_sens"] or 0) >= 90)
    return r

def main():
    n, tag = int(sys.argv[1]), sys.argv[2]
    h = hashlib.sha256()
    with open(os.path.join(SIM, MIN), "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 22), b""): h.update(blk)
    assert h.hexdigest() == SHA_MIN, "%s is not the frozen %s" % (MIN, V)
    E = pd.read_parquet(os.path.join(SIM, EVT)); anom_p = sorted(set(E[E.type == "anomaly"].person_id))
    f = pq.ParquetFile(os.path.join(SIM, MIN))
    # person id per row group (one row group per person)
    rg_pid = [int(f.read_row_group(i, columns=["person_id"]).column(0)[0].as_py()) for i in range(f.metadata.num_row_groups)]
    sealed = sealed_ids(); assert not set(rg_pid) & sealed
    others = [p for p in rg_pid if p not in anom_p]; k = max(0, n - len(anom_p))
    chosen = set(anom_p) | set(others[:: max(1, len(others) // max(k, 1))][:k])
    with Pool(int(os.environ.get("HG_WORKERS", "2"))) as pool:
        res = [r for r in pool.map(run_person, [(i, chosen) for i in range(len(rg_pid))]) if r]
    scen = pd.read_parquet(os.path.join(SIM, SCN)).set_index("person_id")
    persons = pd.read_parquet(os.path.join(SIM, "persons.parquet")).set_index("person_id")
    kap = persons.loc[[r["pid"] for r in res], "kappa_core"]; cuts = np.quantile(kap.values, [1 / 3, 2 / 3])
    table = {}
    for (name, hk) in res[0]["res"]:
        for grp in ("all", "t0", "t1", "t2"):
            rows, sens, s9, s385 = [], [], [], []
            for r in res:
                t = int(np.searchsorted(cuts, persons.loc[r["pid"], "kappa_core"], side="right"))
                if grp != "all" and grp != "t%d" % t: continue
                per, se, s, s3 = r["res"][(name, hk)]; s385 += s3
                for p in per: p["person"] = r["pid"]; rows.append(p)
                sens += se; s9 += s
            table["%s|%s|%s" % (name, hk, grp)] = summarise(rows, sens, s9, s385)
    info = json.load(open(os.path.join(BUILD, "m7_builds.json")))
    out = dict(label="SIMULATION (Virtual Elders %s; known too-tolerant at humid rest, bed rest, and HR) - SIM-DEV %s" % (V, V),
               persons=len(res), anomaly_persons=len(anom_p), kappa_cuts=[float(c) for c in cuts], weights=info["weights"], table=table)
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, "eval_sim_m7_%s.json" % tag), "w"), indent=1, default=float)
    print("persons", len(res), "weights", info["weights"])
    for key, r in table.items():
        if key.endswith("|all"):
            print("%-28s DRINK/d %4.1f min/d %5.0f COOL/wk %4.1f CHECK/wk %4.1f (routine %.1f danger %.1f) | S2 %5.1f%% (inf %5.1f%%) | S9 %5.1f%% | S1 %s S2 %s S9 %s"
                  % (key[:-4], r["drink_per_day"], r["drink_min_per_day"], r["cool_per_week"], r["check_per_week"], r["check_routine_per_week_mean"],
                     r["check_danger_per_week_mean"], r["s2_sens_display"] or 0, r["s2_sens_informed"] or 0, r["s9_sens"] or 0,
                     r["meets_s1"], r["meets_s2"], r["meets_s9"]))

if __name__ == "__main__":
    main()
