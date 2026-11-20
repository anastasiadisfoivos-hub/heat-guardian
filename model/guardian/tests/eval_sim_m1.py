#!/usr/bin/env python3
"""M1.4 budgets on SIM-DEV (SIMULATION (Virtual Elders v2; known too-tolerant at humid rest, bed rest, and HR)).
Frozen v2 files only (manager, M3): minutes_dev_v2 / events_dev_v2 / scenarios_v2, SHA-256 asserted; minutes_sealed* never opened.
400 DEV persons x 10 days; sealed persons excluded and asserted.
C build (host_test replay), STUB weights => tiers are driven by the v1.2 HR anchor + PSU env path (+ M1.1-M1.3).
Inputs are sensor columns only (T1, T2, T_air_meas, RH_meas, HR_meas, hr_quality, PI, a_std_g, zangle_deg); no truth column
enters the band (PPG DC unknown -> 0, impact peak unknown -> 1 g). Twin = population defaults (rest HR 70, no learning).
Budgets (arch/DECISIONS.md M1.4): S1 days: DRINK <= 1 episode/day and <= 60 min/day on the median person; COOL <= 1/week;
CHECK <= 1/wearer-week. S2: DRINK sensitivity to core38 events >= 85 % (warned = DRINK on in [event-45, event+10] min)."""
import json, os, sys, subprocess, tempfile
from multiprocessing import Pool
import numpy as np, pandas as pd, pyarrow.parquet as pq
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "py"))
from trace_io import OUTCOLS, HOST as HOST0
HOST = os.environ.get("HG_HOST", HOST0)
from sim_adapter import profile_of, sealed_ids
SIM = "/home/claude/hg_ai/sim/data"; OUT = os.path.join(HERE, "out")
MIN = "minutes_dev_v2.parquet"; EVT = "events_dev_v2.parquet"; SCN = "scenarios_v2.parquet"
SHA_MIN = "293e0daa28e18a337ccd29dee4e55c4e98aa34f7cdeb207babe79eeb5d4bcf34"   # sim/data/README.md v2 table
COLS = ["person_id", "day", "minute_of_day", "t_min", "T_core", "T1", "T2", "T_air_meas", "RH_meas", "HR_meas", "hr_quality", "PI", "a_std_g", "zangle_deg"]
IX = {k: i for i, k in enumerate(OUTCOLS)}

def run_person(rg):
    f = pq.ParquetFile(os.path.join(SIM, MIN))
    g = f.read_row_group(rg, columns=COLS).to_pandas().sort_values("t_min")
    pid = int(g.person_id.iloc[0])
    assert pid not in sealed_ids()
    p = pd.read_parquet(os.path.join(SIM, "persons.parquet")).set_index("person_id").loc[pid].to_dict()
    prof = profile_of(p); n = len(g)
    z = g.zangle_deg.values.astype(float); zp = np.concatenate([[z[0]], z[:-1]])
    zs = np.stack([zp + (z - zp) * (k + 1) / 12.0 for k in range(12)], 1)
    t1, t2, ta = g.T1.values, g.T2.values, g.T_air_meas.values
    sc = np.column_stack([g.minute_of_day.values, t1, t2, ta, g.RH_meas.values, g.HR_meas.values, g.hr_quality.values, g.PI.values,
                          g.a_std_g.values, np.ones(n), np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n), np.full(n, 3.9),
                          np.full(n, -1), np.full(n, 255), np.zeros(n)])
    arr = np.column_stack([sc, np.repeat(t1[:, None], 12, 1), np.repeat(t2[:, None], 12, 1), np.repeat(ta[:, None], 12, 1), zs])
    with tempfile.TemporaryDirectory() as d:
        with open(d + "/i.csv", "w") as fh:
            fh.write("#PROFILE,%r,%r,%r,%d\n" % (prof["age"], prof["sex_m"], prof["bmi"], prof["med_flags"]))
            fh.write("#TWIN,70,0.12,0,0.15" + ",nan" * 24 + "\nmod,...\n")
            np.savetxt(fh, arr, fmt="%.7g", delimiter=",")
        subprocess.check_call([HOST, "replay", d + "/i.csv", d + "/o.csv"])
        names = ("level", "check_min", "family_alert", "check_reason", "env_run", "env_dose", "f20_eff", "strain", "night_heat", "nudge")
        o = pd.read_csv(d + "/o.csv", header=None, usecols=[IX[k] for k in names])
    o = o.rename(columns={IX[k]: k for k in names})   # usecols keeps FILE order: rename by index, never by position
    lv = o.level.values; cm = o.check_min.values; fam = o.family_alert.values
    prev = np.concatenate([[0], lv[:-1]])
    drink_on = (lv >= 1) & (prev < 1); cool_on = (lv >= 2) & (prev < 2)
    check_on = (cm == 0) & (np.concatenate([[255], cm[:-1]]) != 0)
    cr = o.check_reason.values
    fam_on = (fam == 1) & (np.concatenate([[0], fam[:-1]]) == 0)
    day = g.day.values; tc = g.T_core.values
    envp = (o.env_run.values >= 10) | (o.env_dose.values >= 10)
    # truth for diagnosis only (never an input): does the core reach 38.0 C within 60 min of a DRINK onset?
    fut = pd.Series(tc[::-1]).rolling(61, min_periods=1).max().values[::-1]
    per_day = []
    for dd in sorted(set(day)):
        m = day == dd
        per_day.append(dict(day=int(dd), drink=int(drink_on[m].sum()), drink_min=int((lv[m] >= 1).sum()), cool=int(cool_on[m].sum()),
                            check=int(check_on[m].sum()), family=int(fam_on[m].sum()), nudge=int(o.nudge.values[m].sum()),
                            night_heat_min=int(o.night_heat.values[m].sum()),
                            check_danger=int((check_on & ((cr & 3) > 0))[m].sum()), check_quiet=int((check_on & ((cr & 4) > 0))[m].sum()),
                            check_nowake=int((check_on & ((cr & 8) > 0))[m].sum()),
                            drink_min_env=int(((lv >= 1) & envp)[m].sum()), drink_onset_true38=int((drink_on & (fut >= 38.0))[m].sum()),
                            core38_min=int((tc[m] >= 38.0).sum()), f20_med=float(np.median(o.f20_eff.values[m])), core_med=float(np.median(tc[m]))))
    return pid, per_day, (lv >= 1).astype(np.int8), int(g.t_min.values[0])

def main():
    import hashlib
    h = hashlib.sha256()
    with open(os.path.join(SIM, MIN), "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 22), b""): h.update(blk)
    assert h.hexdigest() == SHA_MIN, "minutes_dev_v2.parquet is not the frozen v2"
    f = pq.ParquetFile(os.path.join(SIM, MIN))
    n = f.metadata.num_row_groups if len(sys.argv) < 2 else int(sys.argv[1])
    persons = pd.read_parquet(os.path.join(SIM, "persons.parquet")).set_index("person_id")
    scen = pd.read_parquet(os.path.join(SIM, SCN)).set_index("person_id")
    ev = pd.read_parquet(os.path.join(SIM, EVT)); ev = ev[ev.type == "core38"]
    stride = int(os.environ.get("HG_STRIDE", "1"))
    with Pool(2) as pool: res = pool.map(run_person, range(0, n, stride))
    sealed = sealed_ids(); assert not set(r[0] for r in res) & sealed
    dev_k = persons.loc[[r[0] for r in res], "kappa_core"]
    cuts = np.quantile(dev_k.values, [1 / 3, 2 / 3])
    rows, sens = [], []
    for pid, per_day, drink, t0 in res:
        types = scen.loc[pid, "day_types_1_to_N"].split(","); k = persons.loc[pid, "kappa_core"]
        terc = int(np.searchsorted(cuts, k, side="right"))
        for dct in per_day:
            dct.update(person=pid, tercile=terc, regime=scen.loc[pid, "regime"], dtype=types[dct["day"] - 1]); rows.append(dct)
        for e in ev[ev.person_id == pid].itertuples():
            dtype = types[int(e.day) - 1]
            if not dtype.startswith("S2"): continue
            a, b = max(0, int(e.t_start) - 45 - t0), min(len(drink), int(e.t_start) + 11 - t0)
            sens.append(dict(person=pid, tercile=terc, warned=int(drink[a:b].any())))
    D = pd.DataFrame(rows); S = pd.DataFrame(sens)
    out = dict(label="SIMULATION (Virtual Elders v2; known too-tolerant at humid rest, bed rest, and HR) - SIM-DEV, STUB weights (v1.2 HR anchor + PSU env path), M1.1-M1.3 applied, twin defaults",
               persons=len(res), kappa_tercile_cuts=[float(c) for c in cuts], groups={})
    def summ(Dg, Sg):
        s1 = Dg[Dg.dtype == "S1"]; pp = s1.groupby("person").mean(numeric_only=True)
        r = dict(s1_person_days=int(len(s1)), s1_persons=int(len(pp)))
        if len(pp):
            r.update(drink_per_day_median=float(pp.drink.median()), drink_per_day_p90=float(pp.drink.quantile(.9)),
                     drink_min_per_day_median=float(pp.drink_min.median()), drink_min_per_day_p90=float(pp.drink_min.quantile(.9)),
                     cool_per_week_median=float(7 * pp.cool.median()), cool_per_week_p90=float(7 * pp.cool.quantile(.9)),
                     check_per_week_median=float(7 * pp.check.median()), check_per_week_p90=float(7 * pp.check.quantile(.9)),
                     family_per_month_mean=float(30 * pp.family.mean()), nudges_per_day_mean=float(pp.nudge.mean()),
                     drink_min_share_env_path=float(s1.drink_min_env.sum() / max(s1.drink_min.sum(), 1)),
                     drink_onset_precision_core38_60min=float(s1.drink_onset_true38.sum() / max(s1.drink.sum(), 1)),
                     true_core38_min_per_day_median=float(pp.core38_min.median()), f20_median=float(s1.f20_med.median()),
                     true_core_median=float(s1.core_med.median()),
                     check_causes_per_week_mean=dict(danger_or_behaviour=float(7 * pp.check_danger.mean()), routine_quiet=float(7 * pp.check_quiet.mean()),
                                                     routine_nowake=float(7 * pp.check_nowake.mean())))
        s2 = Dg[Dg.dtype.str.startswith("S2")]; p2 = s2.groupby("person").mean(numeric_only=True)
        if len(p2): r.update(s2_drink_per_day_median=float(p2.drink.median()), s2_drink_min_per_day_median=float(p2.drink_min.median()),
                             s2_cool_per_day_median=float(p2.cool.median()), s2_check_per_week_median=float(7 * p2.check.median()))
        if len(Sg): r.update(s2_core38_events=int(len(Sg)), s2_drink_sensitivity_pct=float(100 * Sg.warned.mean()))
        r["budget_pass"] = dict(drink_per_day=r.get("drink_per_day_median", 9) <= 1, drink_min=r.get("drink_min_per_day_median", 999) <= 60,
                                cool_week=r.get("cool_per_week_median", 9) <= 1, check_week=r.get("check_per_week_median", 9) <= 1,
                                s2_sensitivity=r.get("s2_drink_sensitivity_pct", 0) >= 85)
        return r
    out["groups"]["all"] = summ(D, S)
    for t in range(3): out["groups"]["kappa_tercile_%d" % t] = summ(D[D.tercile == t], S[S.tercile == t] if len(S) else S)
    os.makedirs(OUT, exist_ok=True)
    tag = os.environ.get("HG_TAG", "")
    json.dump(out, open(os.path.join(OUT, "eval_sim_m1%s.json" % tag), "w"), indent=1, default=float)
    D.to_csv(os.path.join(OUT, "eval_sim_m1%s_days.csv" % tag), index=False)
    print(json.dumps(out, indent=1, default=float))

if __name__ == "__main__":
    main()
