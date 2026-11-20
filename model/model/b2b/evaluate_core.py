#!/usr/bin/env python3
"""B2b step 3a - core MAE / bias / range coverage, freeze-5 (NN) vs v1.2 alone vs AR (anchor + bounded residual). DEV ONLY.
Also recalibrates the displayed-range widths on REAL DEV data (HTT-DEV 65 + Brighton P1) by split conformal, reported with a
leave-one-subject-out (nested) coverage so the coverage figure is not in-sample.
Writes model/runs/b2b/core_eval.json (summary numbers only).  usage: python3 -m model.b2b.evaluate_core"""
import json, os
import numpy as np
from . import devdata as D, residual as AR

OUT = D.RUNS; os.makedirs(OUT, exist_ok=True)
R3 = lambda v: None if v is None or not np.isfinite(v) else round(float(v), 3)
V12_UNSEEN = {"HTT2", "HTT5", "HTT9", "HTT17", "HTT21", "HTT26", "HTT28", "HTT45", "HTT51", "HTT55", "HTT61", "HTT62", "HTT64"}
HALF_F5 = 0.5778   # freeze-5 HG2_CONF_HALF_NOW_REAL


def stats(e):
    e = np.asarray(e, float); e = e[np.isfinite(e)]
    return dict(n=int(len(e)), mae=R3(np.mean(abs(e))), bias=R3(np.mean(e)))


def boot_ci(per, fn, n=2000, seed=20261113):
    keys = list(per); rng = np.random.default_rng(seed); v = []
    for _ in range(n):
        e = np.concatenate([per[keys[i]] for i in rng.choice(len(keys), len(keys))]); v.append(fn(e))
    return [R3(np.percentile(v, 2.5)), R3(np.percentile(v, 97.5))]


def conformal_q(a, level=0.90):
    a = np.sort(np.asarray(a, float)); n = len(a)
    return float(a[min(n - 1, int(np.ceil((n + 1) * level)) - 1)])


def main():
    ens = D.Ens(); res = dict(R=float(AR.R_DEFAULT), env_ramp=float(AR.ENV_RAMP))
    variants = {"AR": dict(R=0.30), "AR_R0.2": dict(R=0.20), "AR_R0.5": dict(R=0.50), "AR_noenv": dict(R=0.30, use_env=False),
                "AR_asym": dict(R=0.30, R_up=0.50)}

    def ar(X, v12, v12f, nn, nnf, worn=2, R=0.30, R_up=None, **kw):
        return AR.from_features(X, v12, v12f, nn, nnf, worn=worn, R=np.float32(R), R_up=R_up, **kw)

    # ---------------- SIM-DEV v4 calibration persons (SIMULATION)
    S = D.sim_val(stride=2, ens=ens)
    X, Y, M = S["X"], S["Y"], S["M"]
    C = ens.core(S["R"], 0).mean(0); C20 = ens.core(S["R"], 1).mean(0)
    sdt, _ = ens.sd_total(S["R"], 0)
    worn = np.where(np.isfinite(X[:, 0]), 2, 0)
    ok = np.isfinite(Y[:, 0]) & np.isfinite(X[:, 0]); ok20 = ok & np.isfinite(Y[:, 1])
    pid = S["pid"]; kap = M["kappa_t"]
    sim = dict(label="SIMULATION - SIM-DEV v4 calibration persons (100, 65-85 y, never trained on), every 2nd worn minute")
    est = {"freeze5_NN": (C, C20), "v12_alone": (M["v12_est"], M["v12_f20"])}
    for nm, kw in variants.items():
        a, b, w = ar(X, M["v12_est"], M["v12_f20"], C, C20, worn=worn, **kw); est[nm] = (a, b)
        if nm == "AR": sim["AR_mean_w"] = R3(np.mean(w[ok])); sim["AR_share_w0"] = R3(100 * np.mean(w[ok] == 0))
        if nm == "AR": sim["AR_share_clamped"] = R3(100 * np.mean(abs(C - M["v12_est"])[ok] > 0.30))
    for nm, (a, b) in est.items():
        r = dict(now=stats((a - Y[:, 0])[ok]), f20=stats((b - Y[:, 1])[ok20]))
        for t in (0, 1, 2):
            m = ok & (kap == t); r["now_kappa_t%d" % t] = stats((a - Y[:, 0])[m])
        hi = ok & (Y[:, 0] >= 38.0); r["now_core_ge_38"] = stats((a - Y[:, 0])[hi])
        hot = ok & (X[:, 6] >= 32); r["now_air_ge_32"] = stats((a - Y[:, 0])[hot])
        sim[nm] = r
    res["sim"] = sim
    sim_err = {nm: (a - Y[:, 0])[ok] for nm, (a, b) in est.items()}
    sim_sd = sdt[ok]
    del S, X

    # ---------------- HTT-DEV (REAL young adults, NN LOSO; v1.2 fit on 52 of these 65 people -> in-sample for those)
    H = D.htt_oof(); okh = np.isfinite(H["y"]); okh20 = okh & np.isfinite(H["y20"])
    worn_h = np.full(len(H["y"]), 2)
    htt = dict(label="REAL young adults 18-33, HTT-DEV 65 people; NN = leave-one-subject-out members; no skin channel")
    est_h = {"freeze5_NN": (H["nn"], H["nn20"]), "v12_alone": (H["v12"], H["v12_f20"])}
    for nm, kw in variants.items():
        a, b, w = ar(H["X"], H["v12"], H["v12_f20"], H["nn"], H["nn20"], worn=worn_h, **kw); est_h[nm] = (a, b)
        if nm == "AR": htt["AR_mean_w"] = R3(np.mean(w[okh]))
    unseen = np.array([s in V12_UNSEEN for s in H["subj"]])
    for nm, (a, b) in est_h.items():
        per = {s: (a - H["y"])[okh & (H["subj"] == s)] for s in np.unique(H["subj"])}
        htt[nm] = dict(now=stats((a - H["y"])[okh]), f20=stats((b - H["y20"])[okh20]), now_unseen13=stats((a - H["y"])[okh & unseen]),
                       now_mae_ci95=boot_ci(per, lambda e: np.mean(abs(e))))
    res["htt"] = htt

    # ---------------- Brighton P1 (REAL 65-76, DEV)
    B = D.brighton_p1()
    p1 = dict(label="REAL 65-76, Brighton P1 only (DEV): 3 sessions, 45 reference samples, rectal max 37.39 C, bicep skin, lab HR")
    est_b = {}
    for s in B:
        X = s["X"]; msd = np.array([min(60, 30 + i) for i in range(len(X))])   # pre-roll 30 min: donning blank passed at elapsed 0
        Xm = X.copy(); Xm[:, 22] = msd / 60.0
        cands = {"freeze5_NN": (s["core_now"], s["core20"]), "v12_alone": (s["v12_est"], s["v12_f20"])}
        for nm, kw in variants.items():
            a, b, w = ar(Xm, s["v12_est"], s["v12_f20"], s["core_now"], s["core20"], worn=2, **kw); cands[nm] = (a, b)
            if nm == "AR": s["w"] = w; s["AR_now"] = a
        for nm, (a, b) in cands.items():
            d = est_b.setdefault(nm, dict(now=[], f20=[]))
            d["now"].append(a[s["t_ref"]] - s["y_ref"])
            tr = list(s["t_ref"])
            d["f20"].append(np.array([b[t] - s["y_ref"][tr.index(t + 20)] for t in tr if t + 20 in tr]))
    for nm, d in est_b.items():
        p1[nm] = dict(now=stats(np.concatenate(d["now"])), f20=stats(np.concatenate(d["f20"])),
                      now_per_session=[stats(e)["bias"] for e in d["now"]])
    p1["AR_mean_w_at_refs"] = R3(np.mean(np.concatenate([s["w"][s["t_ref"]] for s in B])))
    rises = []
    for s in B:
        a = s["AR_now"]
        tr = list(s["t_ref"])
        rises.append([s["y_ref"][tr.index(65)] - s["y_ref"][tr.index(30)], s["core_now"][65] - s["core_now"][30],
                      s["v12_est"][65] - s["v12_est"][30], a[65] - a[30]])
    p1["rise_30_65_rectal_nn_v12_AR"] = [R3(v) for v in np.mean(rises, 0)]
    res["brighton_p1"] = p1

    # ---------------- range: recalibrate on REAL DEV (HTT 65 + P1), nested LOSO coverage
    a_h, b_h = est_h["AR"]
    rows = [(s, abs(a_h - H["y"])[okh & (H["subj"] == s)], abs(b_h - H["y20"])[okh20 & (H["subj"] == s)]) for s in np.unique(H["subj"])]
    rows.append(("BrightonP1", abs(np.concatenate(est_b["AR"]["now"])), abs(np.concatenate(est_b["AR"]["f20"]))))
    rng = dict()
    for k, nm in ((1, "now"), (2, "f20")):
        pooled = np.concatenate([r[k] for r in rows])
        q = conformal_q(pooled)
        # person-balanced: each person's minutes weighted 1/n_person (quantile of the weighted distribution)
        vals = np.concatenate([r[k] for r in rows]); wts = np.concatenate([np.full(len(r[k]), 1.0 / max(len(r[k]), 1)) for r in rows])
        o = np.argsort(vals); cw = np.cumsum(wts[o]) / wts.sum(); qp = float(vals[o][np.searchsorted(cw, 0.90)])
        cov, low = [], 0
        for i, r in enumerate(rows):            # nested: width from the other people only
            others = np.concatenate([rows[j][k] for j in range(len(rows)) if j != i]); qi = conformal_q(others)
            c = float(np.mean(r[k] <= qi)) if len(r[k]) else np.nan; cov.append((c, len(r[k])))
        cv = np.array([c for c, n in cov]); nn_ = np.array([n for c, n in cov])
        rng[nm] = dict(half_pooled_90=R3(q), half_person_balanced_90=R3(qp),
                       loso_coverage_minutes_pct=R3(100 * np.sum(cv * nn_) / nn_.sum()),
                       loso_share_persons_below_80_pct=R3(100 * np.mean(cv < 0.80)),
                       brighton_p1_loso_coverage_pct=R3(100 * cov[-1][0]))
    # coverage of the frozen width (0.5778) around AR and around freeze-5 NN on the same real DEV rows
    for nm in ("freeze5_NN", "AR", "v12_alone"):
        a, _ = est_h[nm]
        e = np.concatenate([abs(a - H["y"])[okh], abs(np.concatenate(est_b[nm]["now"]))])
        rng["coverage_at_frozen_0.5778_%s_pct" % nm] = R3(100 * np.mean(e <= HALF_F5))
        rng["p1_coverage_at_frozen_0.5778_%s_pct" % nm] = R3(100 * np.mean(abs(np.concatenate(est_b[nm]["now"])) <= HALF_F5))
    ef = np.concatenate([abs(b_h - H["y20"])[okh20], abs(np.concatenate(est_b["AR"]["f20"]))])
    rng["coverage_f20_at_frozen_0.5538_AR_pct"] = R3(100 * np.mean(ef <= 0.5538))
    rng["htt_unseen13_coverage_AR_at_new_now_pct"] = R3(100 * np.mean(abs(a_h - H["y"])[okh & unseen] <= rng["now"]["half_pooled_90"]))
    # SIM coverage of the new width (display rule max(1.645 sd, half)) - SIMULATION
    hn = rng["now"]["half_pooled_90"]
    for nm in ("freeze5_NN", "AR"):
        rng["sim_coverage_display_rule_%s_pct" % nm] = R3(100 * np.mean(abs(sim_err[nm]) <= np.maximum(1.645 * np.maximum(sim_sd, 0.08), hn)))
    res["range_real_dev"] = rng
    json.dump(res, open(os.path.join(OUT, "core_eval.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
