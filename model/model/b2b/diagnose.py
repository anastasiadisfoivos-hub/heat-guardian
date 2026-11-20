#!/usr/bin/env python3
"""B2b step 1 - WHY does hg2 read low on older adults? DEV ONLY (Brighton P1, HTT-DEV LOSO, SIM-DEV v4 calibration persons).
Writes model/runs/b2b/diagnosis.json (summary numbers only; Brighton is CC BY-ND, no derived per-minute tables are written).
usage: python3 -m model.b2b.diagnose"""
import json, os
import numpy as np
from . import devdata as D

OUT = D.RUNS; os.makedirs(OUT, exist_ok=True)
F = np.float32
R3 = lambda v: None if v is None or not np.isfinite(v) else round(float(v), 3)


def nn_core(ens, X, k=0):
    return ens.core(ens.members(X.astype(F)), k).mean(0)


def sens(ens, X, col_groups, dl):
    """median finite-difference d core_now / d input (deg C per unit), cols in col_groups shifted together"""
    b = nn_core(ens, X); Xp = X.copy()
    for c, s in col_groups: Xp[:, c] = Xp[:, c] + s * dl
    return float(np.nanmedian((nn_core(ens, Xp) - b) / dl))


T1G = [(0, 1), (25, 1), (9, 1)]                 # t1, core_flux (= t1 when flux invalid), t1 - air
HRG = [(10, 1), (11, 1), (12, 1), (13, 1)]      # hr, ewm5, ewm45, hr above rest (hr_reserve left: second order)
AIRG = [(6, 1), (9, -1)]


def main():
    ens = D.Ens(); res = {}
    # ---------------- SIM-DEV v4 calibration persons (SIMULATION, never trained on)
    S = D.sim_val(stride=3, ens=ens)
    X, y, v12 = S["X"], S["Y"][:, 0], S["M"]["v12_est"]
    nn = ens.core(S["R"]).mean(0)
    ok = np.isfinite(y) & np.isfinite(X[:, 0])
    hot = ok & (X[:, 6] >= 34) & (X[:, 6] <= 36.5)
    t1a = X[:, 9]
    res["sim"] = dict(label="SIMULATION, SIM-DEV v4 calibration persons (100, ages 65-85), every 3rd minute",
                      rows=int(ok.sum()), nn_mae=R3(np.mean(abs(nn[ok] - y[ok]))), nn_bias=R3(np.mean(nn[ok] - y[ok])),
                      v12_mae=R3(np.mean(abs(v12[ok] - y[ok]))), v12_bias=R3(np.mean(v12[ok] - y[ok])),
                      hot_rows=int(hot.sum()),
                      hot_core_minus_t1_median=R3(np.median(y[hot] - X[hot, 0])),
                      hot_core_minus_t1_iqr=[R3(v) for v in np.percentile(y[hot] - X[hot, 0], [25, 75])],
                      hot_t1_minus_air_median=R3(np.median(t1a[hot])),
                      hot_t1_minus_air_p01_p99=[R3(v) for v in np.percentile(t1a[hot], [1, 99])],
                      hot_share_t1_below_air=R3(100 * np.mean(t1a[hot] < 0)),
                      hot_nn_bias=R3(np.mean(nn[hot] - y[hot])), hot_v12_bias=R3(np.mean(v12[hot] - y[hot])))
    idx = np.where(hot)[0][::40]; Xh = X[idx].copy()
    res["sim"]["hot_gain_core_per_t1"] = R3(sens(ens, Xh, T1G, 0.5))
    res["sim"]["hot_gain_core_per_10bpm"] = R3(10 * sens(ens, Xh, HRG, 10))
    res["sim"]["hot_gain_core_per_air"] = R3(sens(ens, Xh, AIRG, 0.5))
    # tracking slope in SIM hot rows: regress estimate on truth
    res["sim"]["hot_slope_nn_on_core"] = R3(np.polyfit(y[hot].astype(float), nn[hot].astype(float), 1)[0])
    res["sim"]["hot_slope_v12_on_core"] = R3(np.polyfit(y[hot].astype(float), v12[hot].astype(float), 1)[0])
    # in-distribution envelope of t1 - air per air band, used later by the OOD shrink (p0.5..p99.5 over SIM worn rows)
    env = {}
    for lo in range(16, 40, 2):
        m = ok & (X[:, 6] >= lo) & (X[:, 6] < lo + 2)
        if m.sum() > 500: env[lo] = [R3(v) for v in np.percentile(t1a[m], [0.5, 99.5])]
    res["sim"]["t1_minus_air_envelope_by_air_2C"] = env
    # member spread vs error in SIM (does disagreement track error?)
    sp = ens.core(S["R"]).std(0)
    res["sim"]["corr_member_spread_abs_err"] = R3(np.corrcoef(sp[ok], abs(nn[ok] - y[ok]))[0, 1])
    del S, X

    # ---------------- HTT-DEV LOSO (REAL young adults; thermal inputs masked -> NN = HR + air path only)
    H = D.htt_oof(); e_nn = H["nn"] - H["y"]; e_v = H["v12"] - H["y"]; okh = np.isfinite(H["y"])
    yc = H["y"][okh]
    res["htt"] = dict(label="REAL young adults 18-33 (HTT-DEV, 65 people), NN leave-one-subject-out; skin/flux masked (none in HTT)",
                      rows=int(okh.sum()), nn_mae=R3(np.mean(abs(e_nn[okh]))), nn_bias=R3(np.mean(e_nn[okh])),
                      v12_mae=R3(np.mean(abs(e_v[okh]))), v12_bias=R3(np.mean(e_v[okh])),
                      slope_nn_on_core=R3(np.polyfit(yc, H["nn"][okh], 1)[0]), slope_v12_on_core=R3(np.polyfit(yc, H["v12"][okh], 1)[0]),
                      nn_bias_core_ge_38=R3(np.mean(e_nn[okh][yc >= 38])), v12_bias_core_ge_38=R3(np.mean(e_v[okh][yc >= 38])),
                      corr_member_spread_abs_err=R3(np.corrcoef(H["spread"][okh], abs(e_nn[okh]))[0, 1]),
                      resid_nn_minus_v12_sd=R3(np.std((H["nn"] - H["v12"])[okh])),
                      corr_resid_with_v12_error=R3(np.corrcoef((H["nn"] - H["v12"])[okh], -e_v[okh])[0, 1]))
    idx = np.where(okh)[0][::20]; Xt = H["X"][idx].copy()
    res["htt"]["gain_core_per_10bpm_deployed"] = R3(10 * sens(ens, Xt, HRG, 10))
    del H

    # ---------------- Brighton P1 (REAL 65-76, DEV): frozen guardian, then counterfactual inputs
    def summ(S, key="core_now"):
        e = np.concatenate([s[key][s["t_ref"]] - s["y_ref"] for s in S]); return R3(np.mean(abs(e))), R3(np.mean(e))
    S = D.brighton_p1()
    t = np.concatenate([s["t_ref"] for s in S]); yy = np.concatenate([s["y_ref"] for s in S])
    Xr = np.concatenate([s["X"][s["t_ref"]] for s in S])
    rest = (t >= 10) & (t <= 30)
    b = dict(label="REAL 65-76, Brighton P1 only (DEV), bicep skin as T1, lab HR, 35 C chamber",
             samples=int(len(yy)), nn=summ(S), v12=summ(S, "v12_est"),
             rest_rectal_minus_bicep_median=R3(np.median(yy[rest] - Xr[rest, 0])),
             rest_bicep_minus_air_median=R3(np.median(Xr[rest, 9])),
             share_t1_minus_air_outside_sim_envelope=None,
             rest_core_mean=R3(np.mean(yy[rest])))
    lo = {int(k): v for k, v in env.items()}
    out_env = [not (lo.get(int(a // 2 * 2)) and lo[int(a // 2 * 2)][0] <= d <= lo[int(a // 2 * 2)][1])
               for a, d in zip(Xr[:, 6], Xr[:, 9]) if np.isfinite(a) and np.isfinite(d)]
    b["share_t1_minus_air_outside_sim_envelope"] = R3(100 * np.mean(out_env))
    # within-session tracking: rise from end of rest (t=30) to end of cycling (t=65)
    rises = []
    for s in S:
        i30, i65 = list(s["t_ref"]).index(30), list(s["t_ref"]).index(65)
        rises.append([s["y_ref"][i65] - s["y_ref"][i30], s["core_now"][65] - s["core_now"][30], s["v12_est"][65] - s["v12_est"][30]])
    rises = np.array(rises)
    b["rise_30_to_65_rectal_nn_v12_mean"] = [R3(v) for v in rises.mean(0)]
    b["gain_core_per_t1"] = R3(sens(ens, Xr[np.isfinite(Xr[:, 0])], T1G, 0.5))
    b["gain_core_per_10bpm"] = R3(10 * sens(ens, Xr[np.isfinite(Xr[:, 0])], HRG, 10))
    # counterfactual 1: skin shifted to the SIM coupling (T1 + (P1 gap - SIM gap)) -> how much of the reading is the skin channel
    shift = float(b["rest_rectal_minus_bicep_median"] - res["sim"]["hot_core_minus_t1_median"])
    b["cf_skin_to_sim_coupling_shift_C"] = R3(shift)
    def mut_t1(m, tt):
        if np.isfinite(m["t1"]): m["t1"] = m["t1"] + shift; m["t1_5s"] = [m["t1"]] * 12
    b["cf_skin_to_sim_coupling"] = summ(D.brighton_p1(mutate=mut_t1))
    def mut_mask(m, tt):
        m["t1"] = float("nan"); m["t1_5s"] = [float("nan")] * 12
    b["cf_no_skin"] = summ(D.brighton_p1(mutate=mut_mask))
    b["note"] = ("P1 is one cool person (rest rectal ~36.5) and never exceeds 37.4 C; its pooled NN bias is near 0 while v1.2 reads +0.6, "
                 "so P1 cannot reproduce the sealed mean bias; it shows the mechanism (gain, coupling, tracking).")
    res["brighton_p1"] = b
    json.dump(res, open(os.path.join(OUT, "diagnosis.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
