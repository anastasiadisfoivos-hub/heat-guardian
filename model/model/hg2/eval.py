"""hg2 dev evaluation (B2 brief eval a-e). PROVISIONAL (sim v1, M2).
 (a) HTT-DEV LOSO (young adults 18-33, chamber walk, DEV): core MAE, within +-0.3/+-0.5, by subject-bootstrap; tiers in
     results_danger_hg2.json (danger_calib.py).
 (b) SIM-DEV validation subset, 40 persons (SIMULATION): MAE now/+20/+30 per kappa tercile and per day type, P38/P385 AUC,
     reliability (10 bins), coverage of +-1.645 sd (sd floor 0.08 C).
 (c) flux-permutation test (M2.5): flux_valid forced 0 (dT, dT_d10, flux_valid = 0, core_flux = t1) on every minute with
     room air T_in >= 37 C, and separately 34-37 C; pass = |d core_now| <= 0.30 C for >= 99 % of those minutes.
 (d) sign checks by finite differences on 10,000 random dev minutes: mean d logit_p385 / d hr_reserve > 0, / d kf > 0.
 (e) ensemble sd informative: MAE(top sd decile) >= 2 x MAE(bottom sd decile).
Writes model/results_eval_hg2.json."""
import json, os
import numpy as np
from sklearn.metrics import roc_auc_score
from .common import RUNS, CACHE, MODEL, SEED, data_provenance, assert_no_sealed, LABEL_SIM, LABEL_HTT
from . import nn
from .train import load_member, norm, flux_off
from .danger_calib import ensemble

F = np.float32


def members(ft=True):
    return [load_member(k)[1 if ft else 0] for k in range(1, 6)]


def ens_predict(Ps, Z, N):
    raw = np.stack([nn.predict(P, Z) for P in Ps])
    return ensemble(raw, N["ym"], N["ys"]), raw


def mae_tab(E, Y, sel):
    return {h: float(np.nanmean(np.abs(E["core_" + h][sel] - Y[sel, j]))) for j, h in enumerate(("now", "20", "30"))} | {"n": int(sel.sum())}


def boot_mae(err, subj, boot=1000, seed=7):
    us = np.unique(subj); idx = {u: np.where(subj == u)[0] for u in us}; rng = np.random.default_rng(seed); o = []
    for _ in range(boot):
        r = np.concatenate([idx[u] for u in rng.choice(us, len(us))]); o.append(np.nanmean(err[r]))
    return [float(np.percentile(o, 2.5)), float(np.percentile(o, 97.5))]


def htt_part():
    d = np.load(os.path.join(CACHE, "htt_oof.npz"), allow_pickle=True)
    E = ensemble(d["raw"], d["ym"], d["ys"]); Y = d["Y"]; subj = d["subj"]
    ok = np.isfinite(Y[:, 0])
    out = dict(label=LABEL_HTT + " (LOSO: each member fine-tuned without the left-out person)", n_people=int(len(np.unique(subj))),
               n_minutes=int(ok.sum()))
    for name, est in (("hg2 core_now (LOSO)", E["core_now"]), ("v1.2 estimate (fixed v1.2 coefficients; fit on 52 of these 65, so in-sample for them)", d["aux_v12_est"])):
        e = np.abs(est - Y[:, 0])
        out[name] = dict(MAE=float(np.nanmean(e[ok])), MAE_95=boot_mae(np.where(ok, e, np.nan), subj),
                         within_0_3=float(np.mean(e[ok] <= 0.3) * 100), within_0_5=float(np.mean(e[ok] <= 0.5) * 100))
    for h, j in (("20", 1), ("30", 2)):
        m = np.isfinite(Y[:, j]); out["hg2 core_%s MAE (LOSO)" % h] = float(np.nanmean(np.abs(E["core_" + h][m] - Y[m, j])))
    m = np.isfinite(Y[:, 1]); out["v1.2 f20 MAE vs core(t+20)"] = float(np.nanmean(np.abs(d["aux_v12_f20"][m] - Y[m, 1])))
    out["reference_REPORT_v1.2_LOSO_52dev_MAE"] = 0.29
    pre = np.load(os.path.join(CACHE, "htt_pretrain_only.npy"))
    Ep = ensemble(pre, d["ym"], d["ys"])
    out["SIM-pretrained only, no HTT fine-tune: core_now MAE"] = float(np.nanmean(np.abs(Ep["core_now"][ok] - Y[ok, 0])))
    for j, nm in ((3, "p38"), (4, "p385")):
        m = np.isfinite(Y[:, j])
        if len(np.unique(Y[m, j])) == 2: out["AUC_%s (LOSO)" % nm] = float(roc_auc_score(Y[m, j], E["lp" + nm[1:]][m]))
    sd = np.maximum(E["sd_now"], 0.08); cov = np.abs(E["core_now"] - Y[:, 0]) <= 1.645 * sd
    out["coverage_1.645sd_now"] = float(np.mean(cov[ok]) * 100)
    return out


def reliability(p, y, bins=10):
    edges = np.linspace(0, 1, bins + 1); rows = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (p >= a) & ((p < b) if b < 1 else (p <= b))
        rows.append(dict(bin=[float(a), float(b)], n=int(m.sum()), mean_pred=float(p[m].mean()) if m.any() else None,
                         observed=float(y[m].mean()) if m.any() else None))
    return rows


def sim_part(Ps, N, view="val"):
    d = np.load(os.path.join(CACHE, "sim_%s.npz" % view)); X, Y, M = d["X"], d["Y"], d["M"]
    meta = json.load(open(os.path.join(CACHE, "sim_meta.json"))); mc = meta["meta_cols"]
    ids = np.unique(M[:, 0]).astype(int); assert_no_sealed(ids); assert sorted(ids.tolist()) == sorted(meta["val_ids"])
    col = lambda n: M[:, mc.index(n)]
    Z = nn.normalise_x(X, N["xm"], N["xs"]); E, raw = ens_predict(Ps, Z, N)
    out = dict(label=LABEL_SIM + " - the 100 SIM-DEV calibration persons (never trained on, never used for early stopping or any choice; never SEALED-SIM)",
               n_minutes=int(len(X)), persons=ids.tolist())
    out["overall"] = mae_tab(E, Y, np.ones(len(X), bool))
    out["v1.2 estimate on the same minutes (HR anchor alone)"] = float(np.nanmean(np.abs(col("v12_est") - Y[:, 0])))
    out["per_kappa_tercile"] = {"T%d" % (t + 1): mae_tab(E, Y, col("kappa_t") == t) for t in range(3)}
    names = {0: "S1 ordinary", 1: "PRE (warm-up)", 2: "POST heat wave", 3: "S2 heat-wave day (extrapolated multi-day; day-2 escalation not represented)"}
    out["per_daytype"] = {names[t]: mae_tab(E, Y, col("daytype") == t) for t in range(4)}
    out["per_location"] = {n: mae_tab(E, Y, col("location") == i) for i, n in enumerate(("home", "transit", "out"))}
    tin = col("T_in")
    out["per_room_air"] = {n: mae_tab(E, Y, s) for n, s in (("<28", tin < 28), ("28-31", (tin >= 28) & (tin < 31)), ("31-34", (tin >= 31) & (tin < 34)),
                                                         ("34-37", (tin >= 34) & (tin < 37)), (">=37", tin >= 37))}
    out["per_flux_valid_feature"] = {"flux_valid=1": mae_tab(E, Y, X[:, 5] == 1), "flux_valid=0": mae_tab(E, Y, X[:, 5] == 0)}
    for j, nm in ((3, "p38"), (4, "p385")):
        m = np.isfinite(Y[:, j]); p = 1 / (1 + np.exp(-E["lp" + nm[1:]][m]))
        out["AUC_" + nm] = float(roc_auc_score(Y[m, j], E["lp" + nm[1:]][m])); out["prevalence_" + nm] = float(Y[m, j].mean())
        out["AUC_%s_per_kappa_tercile" % nm] = {"T%d" % (t + 1): float(roc_auc_score(Y[m & (col("kappa_t") == t), j], E["lp" + nm[1:]][m & (col("kappa_t") == t)]))
                                               for t in range(3) if len(np.unique(Y[m & (col("kappa_t") == t), j])) == 2}
        out["reliability_" + nm] = reliability(p, Y[m, j]); out["brier_" + nm] = float(np.mean((p - Y[m, j]) ** 2))
    cov = {}
    for h, j in (("now", 0), ("20", 1), ("30", 2)):
        m = np.isfinite(Y[:, j]); sd = np.maximum(E["sd_" + h][m], 0.08)
        cov[h] = float(np.mean(np.abs(E["core_" + h][m] - Y[m, j]) <= 1.645 * sd) * 100)
    out["coverage_1.645sd_pct"] = cov
    out["coverage_now_per_kappa_tercile"] = {"T%d" % (t + 1): float(np.mean((np.abs(E["core_now"] - Y[:, 0]) <= 1.645 * np.maximum(E["sd_now"], 0.08))[col("kappa_t") == t]) * 100) for t in range(3)}
    out["sd_now_median"] = float(np.median(E["sd_now"]))
    # conformal-style scale k so that +-1.645*max(k*sd, 0.08) covers 90 % (dev-calibrated on this subset; a recommendation)
    e0 = np.abs(E["core_now"] - Y[:, 0]); lo_, hi_ = 0.5, 50.0
    for _ in range(50):
        mid = (lo_ + hi_) / 2
        if np.mean(e0 <= 1.645 * np.maximum(mid * E["sd_now"], 0.08)) < 0.90: lo_ = mid
        else: hi_ = mid
    out["sd_scale_for_90pct"] = float(hi_)
    # (e) sd informativeness
    err = np.abs(E["core_now"] - Y[:, 0]); q = np.quantile(E["sd_now"], [0.2, 0.8])
    lo, hi = float(err[E["sd_now"] <= q[0]].mean()), float(err[E["sd_now"] >= q[1]].mean())
    out["sd_informative"] = dict(mae_bottom_quintile=lo, mae_top_quintile=hi, ratio=hi / lo, pass_ge_2x=hi / lo >= 2,
                                 rule="M6.3: MAE(top sd quintile) / MAE(bottom sd quintile) >= 2.0")
    qq = np.quantile(E["sd_now"], np.linspace(0, 1, 6))
    out["mae_by_sd_quintile"] = [float(err[(E["sd_now"] >= a) & (E["sd_now"] <= b)].mean()) for a, b in zip(qq[:-1], qq[1:])]
    out["coverage_1.645sd_no_floor_pct"] = {h: float(np.mean((np.abs(E["core_" + h] - Y[:, j]) <= 1.645 * E["sd_" + h])[np.isfinite(Y[:, j])]) * 100)
                                            for h, j in (("now", 0), ("20", 1), ("30", 2))}
    out["between_member_share_of_variance_now"] = float(np.mean(E["btw_sd_now"] ** 2) / np.mean(E["sd_now"] ** 2))
    out["pass_coverage_85_95"] = bool(85 <= out["coverage_1.645sd_no_floor_pct"]["now"] <= 95)
    # (c) flux permutation (M2.5)
    Ef, _ = ens_predict(Ps, nn.normalise_x(flux_off(X), N["xm"], N["xs"]), N)
    dlt = np.abs(Ef["core_now"] - E["core_now"])
    perm = {}
    for n, s in ((">=37 (M2.5 primary)", tin >= 37), ("34-37 (reported separately)", (tin >= 34) & (tin < 37)), (">=34 (original ARCH wording)", tin >= 34)):
        perm[n] = dict(n=int(s.sum()), share_le_0_30=float(np.mean(dlt[s] <= 0.30) * 100) if s.any() else None,
                       p99_abs_delta=float(np.percentile(dlt[s], 99)) if s.any() else None, max_abs_delta=float(dlt[s].max()) if s.any() else None,
                       share_flux_valid_before=float(np.mean(X[s, 5] == 1) * 100) if s.any() else None,
                       p99_abs_delta_on_flux_valid_minutes=float(np.percentile(dlt[s & (X[:, 5] == 1)], 99)) if (s & (X[:, 5] == 1)).any() else None,
                       passes=bool(np.mean(dlt[s] <= 0.30) >= 0.99) if s.any() else None)
    out["flux_permutation"] = perm
    out["flux_permutation_note"] = "regime = SIM room/ambient air truth T_in (the band sees t_air); permutation applied to the feature vector"
    # (d) sign checks
    rng = np.random.default_rng(SEED + 5); r = rng.choice(len(X), 10000, replace=False); Xr = X[r]
    base = ens_predict(Ps, nn.normalise_x(Xr, N["xm"], N["xs"]), N)[0]["lp385"]
    sg = {}
    for nm, j, h in (("hr_reserve", 14, 0.05), ("kf", 20, 0.10)):
        Xp = Xr.copy(); Xp[:, j] += h
        g = (ens_predict(Ps, nn.normalise_x(Xp, N["xm"], N["xs"]), N)[0]["lp385"] - base) / h
        sg[nm] = dict(step=h, mean_dlogit=float(g.mean()), share_positive=float(np.mean(g > 0) * 100), share_negative=float(np.mean(g < 0) * 100),
                      passes=bool(g.mean() > 0))
    out["sign_checks_logit_p385"] = sg
    return out, E, Y, M


def es_monitor(Ps, N):
    """M6 iteration monitor: the 10 ES persons not used for anything else (not calibration persons)"""
    from .train import es_split
    d = np.load(os.path.join(CACHE, "sim_es.npz")); X, Y, M = d["X"], d["Y"], d["M"]
    _, mon = es_split(M); m = np.isin(M[:, 0].astype(int), mon); X, Y = X[m], Y[m]
    E, _ = ens_predict(Ps, nn.normalise_x(X, N["xm"], N["xs"]), N)
    err = np.abs(E["core_now"] - Y[:, 0]); q = np.quantile(E["sd_now"], [0.2, 0.8])
    return dict(persons=[int(x) for x in mon], mae_now=float(err.mean()),
                informativeness=float(err[E["sd_now"] >= q[1]].mean() / err[E["sd_now"] <= q[0]].mean()),
                coverage_no_floor=float(np.mean(err <= 1.645 * E["sd_now"]) * 100),
                btw_share=float(np.mean(E["btw_sd_now"] ** 2) / np.mean(E["sd_now"] ** 2)))


def main():
    N = norm(); Ps = members()
    res = dict(provenance=data_provenance(), status="PROVISIONAL (sim v1, M2): final numbers re-run on sim v2")
    res["es_monitor_10_persons"] = es_monitor(Ps, N)
    res["htt_dev_loso"] = htt_part()
    res["sim_dev_val"], *_ = sim_part(Ps, N, "val")
    k = res["sim_dev_val"]["sd_scale_for_90pct"]
    if os.path.exists(os.path.join(CACHE, "sim_valaug.npz")): res["sim_dev_val_hr_scaled_M3.2"], *_ = sim_part(Ps, N, "valaug")
    if "sim_dev_val_hr_scaled_M3.2" in res:
        d = np.load(os.path.join(CACHE, "sim_valaug.npz")); Ea, _ = ens_predict(Ps, nn.normalise_x(d["X"], N["xm"], N["xs"]), N)
        res["sim_dev_val_hr_scaled_M3.2"]["coverage_now_with_val_sd_scale_k"] = float(np.mean(np.abs(Ea["core_now"] - d["Y"][:, 0]) <= 1.645 * np.maximum(k * Ea["sd_now"], 0.08)) * 100)
    if "sim_dev_val_hr_scaled_M3.2" in res: res["sim_dev_val_hr_scaled_M3.2"]["note"] = ("same 40 persons, HR rise above rest scaled by f ~ U(0.6, 1.0) per person (M3.2), "
                                                 "i.e. the 'real older hearts rise less' world the augmentation targets")
    json.dump(res, open(os.path.join(RUNS, "results_eval_hg2.json"), "w"), indent=1)
    print(json.dumps(res, indent=1)[:6000])
    return res


if __name__ == "__main__":
    main()
