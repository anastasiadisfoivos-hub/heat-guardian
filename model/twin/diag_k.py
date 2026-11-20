"""[B3-fix] item 5: what does the ARCHITECTURE section 5 K rule actually estimate?  *** SIMULATION (SIM-DEV only) ***

At every reading opportunity the eval uses (days 1-3, 09:00-12:00, home, worn >= 30 min, still 30 min, flux valid,
dT_5 >= 0.5) on all SIM-DEV persons, with noise-free T_core as the reading:
    k_obs = (T_core - T1_5)/dT_5                       (what the rule converges to, offset 0)
          = (T_deep - T1)/dT  +  (T_core - T_deep)/dT  =  k_tissue  +  axial term
    K_true (persons.parquet) = R_tissue / R_ins          (the sim's definition; excludes R_mount)
Also tested: the 2-reading slope of (T_core - T1) on dT (can two readings at different dT separate K from the gap?).
Writes results/k_diag.json.
"""
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/claude/hg_ai/twin")
from sim_io import DevMinutes, load_persons, sealed_sim_ids  # noqa: E402

COLS = ["person_id", "day", "minute_of_day", "T_core", "T_deep_wrist", "T1", "T2", "T_air_meas", "a_std_g", "worn_truth",
        "location", "s_skbf", "T_in", "flux_valid_truth"]


def main(path="/home/claude/hg_ai/sim/data/minutes_dev.parquet"):
    sealed = sealed_sim_ids()
    dm = DevMinutes(COLS, path=path)
    P = load_persons().set_index("person_id")
    rows = []
    for pid in dm.persons():
        assert pid not in sealed
        m = dm.person(pid)
        worn = m.worn_truth.values == 2
        don = np.zeros(len(m), int)
        for i in range(1, len(m)):
            don[i] = don[i - 1] + 1 if worn[i] else 0
        still30 = pd.Series(m.a_std_g.values < 0.02).rolling(31, min_periods=31).min().fillna(0).values.astype(bool)
        dT = (m.T1 - m.T2).values
        t15 = pd.Series(m.T1.values).rolling(5, min_periods=5).mean().values
        dT5 = pd.Series(dT).rolling(5, min_periods=5).mean().values
        days = sorted(m.day.unique())[:3]
        for d in days:
            ok = ((m.day.values == d) & (m.minute_of_day.values >= 540) & (m.minute_of_day.values <= 720) & worn & (don >= 30)
                  & (m.location.values == 0) & still30 & (m.flux_valid_truth.values == 1) & (dT5 >= 0.5))
            idx = np.where(ok)[0]
            if not len(idx):
                continue
            i = idx[0]
            rows.append(dict(person_id=pid, day=d, T_core=m.T_core.values[i], T_deep=m.T_deep_wrist.values[i], T1_5=t15[i], dT_5=dT5[i],
                             s=m.s_skbf.values[i], T_in=m.T_in.values[i]))
    R = pd.DataFrame(rows)
    R["k_obs"] = (R.T_core - R.T1_5) / R.dT_5
    R["k_tissue"] = (R.T_deep - R.T1_5) / R.dT_5
    R["axial_term"] = (R.T_core - R.T_deep) / R.dT_5
    R["gap"] = R.T_core - R.T1_5
    R = R.join(P[["K_true", "R_tissue", "R_mount", "R_ins", "a_axial", "b_axial"]], on="person_id")
    R["K_tm"] = (R.R_tissue + R.R_mount) / R.R_ins
    # what the spec rule ends at after the person's readings (gain 0.5 from 0.12, clamp 0.03..0.40), and unclamped
    per = []
    for pid, g in R.groupby("person_id"):
        k_spec = 0.12; k_wide = 0.12
        for ko in g.k_obs:
            k_spec = min(max(k_spec + 0.5 * (ko - k_spec), 0.03), 0.40)
            k_wide = min(max(k_wide + 0.5 * (ko - k_wide), 0.03), 1.5)
        slope = np.polyfit(g.dT_5, g.gap, 1)[0] if len(g) >= 2 and g.dT_5.std() > 0.2 else np.nan
        per.append(dict(person_id=pid, n_read=len(g), k_spec=k_spec, k_wide=k_wide, slope=slope, K_true=g.K_true.iloc[0],
                        K_tm=g.K_tm.iloc[0], k_obs_med=g.k_obs.median(), gap_med=g.gap.median(), dT_sd=g.dT_5.std()))
    Q = pd.DataFrame(per)
    c = lambda a, b: float(np.corrcoef(a, b)[0, 1]) if len(a) > 2 else None  # noqa: E731
    sl = Q.dropna(subset=["slope"])
    out = {"label": "SIMULATION, SIM-DEV persons only", "n_persons_with_reading": int(len(Q)), "n_readings": int(len(R)),
           "dT_5_median_degC": float(R.dT_5.median()),
           "k_obs": dict(median=float(R.k_obs.median()), p10=float(R.k_obs.quantile(0.1)), p90=float(R.k_obs.quantile(0.9)),
                         share_above_0_40=float((R.k_obs > 0.40).mean())),
           "decomposition_median": dict(k_tissue=float(R.k_tissue.median()), axial_term=float(R.axial_term.median()),
                                        axial_degC=float((R.T_core - R.T_deep).median())),
           "K_true_median": float(Q.K_true.median()), "K_tissue_plus_mount_median": float(Q.K_tm.median()),
           "corr": dict(k_obs_vs_K_true=c(R.k_obs, R.K_true), k_tissue_vs_K_true=c(R.k_tissue, R.K_true),
                        k_tissue_vs_K_tm=c(R.k_tissue, R.K_tm), k_spec_final_vs_K_true=c(Q.k_spec, Q.K_true),
                        k_wide_final_vs_k_obs=c(Q.k_wide, Q.k_obs_med), two_reading_slope_vs_K_true=c(sl.slope, sl.K_true)),
           "spec_rule_final": dict(median=float(Q.k_spec.median()), share_at_upper_bound=float((Q.k_spec >= 0.3999).mean())),
           "wide_rule_final_bound_1_5": dict(median=float(Q.k_wide.median()), share_at_upper_bound=float((Q.k_wide >= 1.4999).mean())),
           "two_reading_slope": dict(n=int(len(sl)), median=float(sl.slope.median()) if len(sl) else None,
                                     median_abs_err_vs_K_true=float((sl.slope - sl.K_true).abs().median()) if len(sl) else None,
                                     dT_sd_median=float(Q.dT_sd.median()))}
    R.to_csv("/home/claude/hg_ai/twin/results/k_diag_readings.csv", index=False)
    json.dump(out, open("/home/claude/hg_ai/twin/results/k_diag.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
