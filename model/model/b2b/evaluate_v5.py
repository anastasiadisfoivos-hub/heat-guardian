#!/usr/bin/env python3
"""B2b-v5 evaluation (run with B2B_TAG=v5aug after the v5 retrain + export + gen_consts). DEV / calibration only:
  SIM-DEV v5 calibration persons (100, never trained on; SIMULATION), HTT-DEV LOSO (REAL young), Brighton P1..P10
  (REAL 65-76, CALIBRATION - spent exam, never held-out). Compares the freeze-5 numbers (v4 NN; from model/runs/b2b and the
  sealed-exam summary) with the v5 NN alone, v1.2 alone and v5 AR (the guardian's own AR via the Python mirror on Brighton).
Also: the v5 NN's skin / HR gains (is it still a skin thermometer?) and the REAL range widths for AR (split conformal on
HTT + Brighton, nested leave-one-person-out coverage). Writes model/runs/b2b_v5aug/eval_v5.json.
usage: B2B_TAG=v5aug python3 -m model.b2b.evaluate_v5"""
import json, os
import numpy as np
from . import devdata as D, residual as AR
from .diagnose import sens, T1G, HRG
from .evaluate_core import stats, conformal_q, R3

assert D.TAG == "v5aug"


def main():
    ens = D.Ens(); res = dict(label="B2b-v5: Core Sense retrained on Virtual Elders v5; AR bounds R_down %.2f / R_up %.2f" % (AR.R_DEFAULT, AR.R_UP_DEFAULT))
    # ---------------- SIM-DEV v5 (SIMULATION)
    S = D.sim_val(stride=2, ens=ens)
    X, Y, M = S["X"], S["Y"], S["M"]
    C0 = ens.core(S["R"], 0).mean(0); C1 = ens.core(S["R"], 1).mean(0)
    worn = np.where(np.isfinite(X[:, 0]), 2, 0)
    ok = np.isfinite(Y[:, 0]) & np.isfinite(X[:, 0]); ok20 = ok & np.isfinite(Y[:, 1])
    hot = ok & (X[:, 6] >= 34) & (X[:, 6] <= 36.5)
    a0, a1, w = AR.from_features(X, M["v12_est"], M["v12_f20"], C0, C1, worn=worn)
    sim = dict(label="SIMULATION - SIM-DEV v5 calibration persons (100)", AR_mean_w=R3(np.mean(w[ok])))
    for nm, (p, q) in {"v5_NN": (C0, C1), "v12_alone": (M["v12_est"], M["v12_f20"]), "v5_AR": (a0, a1)}.items():
        sim[nm] = dict(now=stats((p - Y[:, 0])[ok]), f20=stats((q - Y[:, 1])[ok20]), now_core_ge_38=stats((p - Y[:, 0])[ok & (Y[:, 0] >= 38)]),
                       now_low_kappa=stats((p - Y[:, 0])[ok & (M["kappa_t"] == 0)]))
    idx = np.where(hot)[0][::40]; Xh = X[idx].copy()
    sim["gain_core_per_t1_hot"] = R3(sens(ens, Xh, T1G, 0.5)); sim["gain_core_per_10bpm_hot"] = R3(10 * sens(ens, Xh, HRG, 10))
    sim["core_minus_t1_hot_iqr"] = [R3(v) for v in np.percentile(Y[hot, 0] - X[hot, 0], [25, 75])]
    sp = ens.core(S["R"]).std(0); sim["corr_member_spread_abs_err"] = R3(np.corrcoef(sp[ok], abs(C0[ok] - Y[ok, 0]))[0, 1])
    res["sim_v5"] = sim; del S, X
    # ---------------- HTT LOSO (REAL young)
    H = D.htt_oof(); okh = np.isfinite(H["y"]); okh20 = okh & np.isfinite(H["y20"])
    b0, b1, _ = AR.from_features(H["X"], H["v12"], H["v12_f20"], H["nn"], H["nn20"], worn=np.full(len(H["y"]), 2))
    res["htt"] = {nm: dict(now=stats((p - H["y"])[okh]), f20=stats((q - H["y20"])[okh20]))
                  for nm, (p, q) in {"v5_NN": (H["nn"], H["nn20"]), "v12_alone": (H["v12"], H["v12_f20"]), "v5_AR": (b0, b1)}.items()}
    res["htt"]["label"] = "REAL young adults 18-33 (65), NN leave-one-subject-out; no skin channel"
    idx = np.where(okh)[0][::20]; res["htt"]["gain_core_per_10bpm"] = R3(10 * sens(ens, H["X"][idx].copy(), HRG, 10))
    # ---------------- Brighton P1..P10 (REAL 65-76, CALIBRATION, not held-out); AR = the guardian mirror's own output
    B = D.brighton_p1(sheets=["P%d" % i for i in range(1, 11)])
    br = dict(label="REAL 65-76 Brighton P1..P10, 30 sessions - CALIBRATION (spent exam, used to fit sim v5); NOT held-out")
    err = {k: [] for k in ("v5_NN", "v12_alone", "v5_AR")}; err20 = {k: [] for k in err}; per = {k: {} for k in err}
    rises = []
    for s in B:
        tr = list(s["t_ref"])
        for nm, (p, q) in {"v5_NN": (s["nn_now"], s["nn20"]), "v12_alone": (s["v12_est"], s["v12_f20"]), "v5_AR": (s["core_now"], s["core20"])}.items():
            e = p[s["t_ref"]] - s["y_ref"]; err[nm].append(e); per[nm].setdefault(s["sheet"], []).append(e)
            err20[nm].append(np.array([q[t] - s["y_ref"][tr.index(t + 20)] for t in tr if t + 20 in tr]))
        if 30 in tr and 65 in tr:
            rises.append([s["y_ref"][tr.index(65)] - s["y_ref"][tr.index(30)], s["nn_now"][65] - s["nn_now"][30],
                          s["v12_est"][65] - s["v12_est"][30], s["core_now"][65] - s["core_now"][30]])
    for nm in err:
        e = np.concatenate(err[nm]); br[nm] = dict(now=stats(e), f20=stats(np.concatenate(err20[nm])),
                                                    share_low_by_0p3=R3(100 * np.mean(e < -0.3)))
    br["rise_30_65_rectal_nn_v12_ar"] = [R3(v) for v in np.mean(rises, 0)]
    Xb = np.concatenate([s["X"][s["t_ref"]] for s in B]); Xb = Xb[np.isfinite(Xb[:, 0])]
    br["gain_core_per_t1"] = R3(sens(ens, Xb, T1G, 0.5)); br["gain_core_per_10bpm"] = R3(10 * sens(ens, Xb, HRG, 10))
    lo, hi = AR.env_bounds(Xb[:, 6]); br["share_t1_minus_air_inside_envelope"] = R3(100 * np.mean((Xb[:, 9] >= lo) & (Xb[:, 9] <= hi)))
    br["v5_AR_mean_w_at_refs"] = None
    lv = {}
    for s in B:
        for tier, k in (("drink", 1), ("cool", 2), ("danger", 3)): lv.setdefault(tier, 0); lv[tier] += int(np.any(s["level"] >= k))
    br["sessions_with_tier_any"] = lv
    res["brighton_calibration"] = br
    # ---------------- REAL range widths for AR (HTT 65 + Brighton 10 people), nested leave-one-person-out
    rows = [(s_, abs(b0 - H["y"])[okh & (H["subj"] == s_)], abs(b1 - H["y20"])[okh20 & (H["subj"] == s_)]) for s_ in np.unique(H["subj"])]
    for sh in per["v5_AR"]:
        e = np.concatenate(per["v5_AR"][sh])
        e20 = np.concatenate([np.array([s["core20"][t] - s["y_ref"][list(s["t_ref"]).index(t + 20)] for t in s["t_ref"] if t + 20 in list(s["t_ref"])])
                              for s in B if s["sheet"] == sh])
        rows.append(("B" + sh, abs(e), abs(e20)))
    rng = {}
    for k, nm in ((1, "now"), (2, "f20")):
        q = conformal_q(np.concatenate([r[k] for r in rows])); cov = []
        for i, r in enumerate(rows):
            qi = conformal_q(np.concatenate([rows[j][k] for j in range(len(rows)) if j != i])); cov.append((float(np.mean(r[k] <= qi)), len(r[k]), r[0]))
        cv = np.array([c for c, n, _ in cov]); nn_ = np.array([n for c, n, _ in cov]); old = np.array([p.startswith("B") for _, _, p in cov])
        # older-adult-only width (Brighton people only; calibration)
        qo = conformal_q(np.concatenate([r[k] for r in rows if r[0].startswith("B")]))
        rng[nm] = dict(half_pooled_90=R3(q), half_brighton_only_90=R3(qo), loso_coverage_minutes_pct=R3(100 * np.sum(cv * nn_) / nn_.sum()),
                       loso_share_persons_below_80_pct=R3(100 * np.mean(cv < 0.8)), loso_brighton_mean_coverage_pct=R3(100 * np.mean(cv[old])))
    res["range_real"] = rng
    os.makedirs(D.RUNS, exist_ok=True)
    json.dump(res, open(os.path.join(D.RUNS, "eval_v5.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
