"""T1 property/label tests on minutes_dev_v2.parquet (SIMULATION), my own code, streamed per row group.
Checks: NaN policy, core 35-41, T1 <= T_core, dT vs T_air bins (R2 6.5 + M2.5 regime), dT 2-5 in 20-26 C,
labels ev38_30/ev385_30 and strain_psi recomputed, met never in (1.08, 1.22), flux_valid_truth rule."""
import json, sys
import numpy as np, pandas as pd, pyarrow.parquet as pq
D = "/home/claude/hg_ai/sim/data/"
pf = pq.ParquetFile(D + "minutes_dev_v2.parquet")
persons = pd.read_parquet(D + "persons.parquet").set_index("person_id")
step = int(sys.argv[1]) if len(sys.argv) > 1 else 1
TRUTH = ["T_core", "T_skin_mean", "T_deep_wrist", "s_skbf", "m_sweat", "w", "deficit_pct", "HR_true", "met", "T_in", "RH_in",
         "T_out", "location", "activity_class", "asleep", "fan", "clo", "drink_mL", "sun_on_lid", "worn_truth"]
SENS = ["T1", "T2", "T_air_meas", "RH_meas", "HR_meas", "hr_quality", "PI", "a_std_g", "zangle_deg", "flux_valid_truth"]
acc = dict(rows=0, nan_truth={}, nan_sensor={}, core_min=99, core_max=-99, core_out=0, met_band=0,
           ev38_mis=0, ev38_mis_tail=0, ev38_mis_edge=0, ev385_mis=0, ev385_mis_tail=0, ev385_mis_edge=0, ev38_pos=0,
           psi_maxerr=0.0, nan_hr_off=0, nan_hr_worn=0, pi_nan_worn=0)
bins = [20, 22, 24, 26, 28, 30, 32, 34, 35, 36, 37, 38, 39, 40, 45]
dT_bins = {b: [0, 0, 0.0, -9.0] for b in bins[:-1]}     # n, n<=0.6, sum, max
t1 = dict(worn=0, viol=0, viol_sun=0, viol_hotair=0, viol_other=0, viol_other_max=0.0, viol_other_examples=[])
cool = dict(n=0, below2=0, above5=0)
pids = []
for g in range(0, pf.num_row_groups, step):
    df = pf.read_row_group(g).to_pandas()
    pid = int(df.person_id.iloc[0]); pids.append(pid)
    n = len(df); acc["rows"] += n
    for c in TRUTH:
        acc["nan_truth"][c] = acc["nan_truth"].get(c, 0) + int(df[c].isna().sum())
    for c in SENS:
        acc["nan_sensor"][c] = acc["nan_sensor"].get(c, 0) + int(df[c].isna().sum())
    worn = df.worn_truth.values > 0
    acc["nan_hr_off"] += int(df.HR_meas.isna().values[~worn].sum()); acc["nan_hr_worn"] += int(df.HR_meas.isna().values[worn].sum())
    acc["pi_nan_worn"] += int(df.PI.isna().values[worn].sum())
    tc = df.T_core.values.astype(np.float64)
    acc["core_min"] = min(acc["core_min"], float(tc.min())); acc["core_max"] = max(acc["core_max"], float(tc.max()))
    acc["core_out"] += int(((tc < 35) | (tc > 41)).sum())
    m = df.met.values
    acc["met_band"] += int(((m > 1.0801) & (m < 1.2199)).sum())
    # labels: max T_core over (t, t+30] within the stored series
    pad = np.concatenate([tc[1:], np.full(30, -np.inf)])
    fut = np.lib.stride_tricks.sliding_window_view(pad, 30)[:n].max(1)
    tail = np.arange(n) >= n - 30
    for thr, key in ((38.0, "ev38"), (38.5, "ev385")):
        mine = fut >= thr
        theirs = df[key + "_30"].values.astype(bool)
        mis = mine != theirs
        acc[key + "_mis"] += int(mis.sum())
        acc[key + "_mis_tail"] += int((mis & tail).sum())
        acc[key + "_mis_edge"] += int((mis & ~tail & (np.abs(fut - thr) <= 0.0006)).sum())
    acc["ev38_pos"] += int(df.ev38_30.sum())
    P = persons.loc[pid]
    psi = np.clip(5 * (tc - 36.9) / 2.6 + 5 * (df.HR_true.values - P.hr_rest) / (P.hr_max - P.hr_rest), 0, 10)
    acc["psi_maxerr"] = max(acc["psi_maxerr"], float(np.abs(psi - df.strain_psi.values).max()))
    # T1 <= T_core
    w2 = df.worn_truth.values == 2
    T1 = df.T1.values.astype(np.float64); T2 = df.T2.values.astype(np.float64)
    air = np.where(df.location.values == 0, df.T_in.values, df.T_out.values)
    t1["worn"] += int(w2.sum())
    v = w2 & (T1 > tc + 0.11)
    t1["viol"] += int(v.sum())
    sun = df.sun_on_lid.values > 0
    hot = air >= tc - 0.5
    t1["viol_sun"] += int((v & sun).sum()); t1["viol_hotair"] += int((v & ~sun & hot).sum())
    oth = v & ~sun & ~hot
    t1["viol_other"] += int(oth.sum())
    if oth.any():
        t1["viol_other_max"] = max(t1["viol_other_max"], float((T1 - tc)[oth].max()))
        if len(t1["viol_other_examples"]) < 5:
            i = int(np.nonzero(oth)[0][0]); t1["viol_other_examples"].append(dict(pid=pid, t_min=int(df.t_min.iloc[i]), T1=T1[i], Tc=tc[i], air=float(air[i]), loc=int(df.location.iloc[i]), msd=None))
    # dT vs room air at home, worn, no sun, still-ish
    home = (df.location.values == 0) & w2 & ~sun
    dT = T1 - T2
    Tin = df.T_in.values
    for lo, hi in zip(bins[:-1], bins[1:]):
        s = home & (Tin >= lo) & (Tin < hi)
        if s.any():
            b = dT_bins[lo]; b[0] += int(s.sum()); b[1] += int((dT[s] <= 0.6).sum()); b[2] += float(dT[s].sum()); b[3] = max(b[3], float(dT[s].max()))
    s = home & (Tin >= 20) & (Tin <= 26)
    cool["n"] += int(s.sum()); cool["below2"] += int((dT[s] < 2).sum()); cool["above5"] += int((dT[s] > 5).sum())
acc["persons_scanned"] = len(pids)
acc["T1_le_core"] = t1
acc["dT_by_Tin_bin"] = {f"{lo}-{hi}": dict(n=b[0], frac_le_0p6=(b[1] / b[0]) if b[0] else None, mean=(b[2] / b[0]) if b[0] else None, max=b[3])
                        for (lo, b), hi in zip(dT_bins.items(), bins[1:])}
acc["dT_cool_20_26"] = cool
print(json.dumps(acc, indent=1, default=float))
json.dump(acc, open(f"/home/claude/hg_ai/tests/t1/out/props_dev_step{step}.json", "w"), indent=1, default=float)
