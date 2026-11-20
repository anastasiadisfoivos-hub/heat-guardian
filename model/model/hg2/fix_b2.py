"""[B2-fix] answers to tests/B2_TEST_REPORT.md (no retraining; weights CRC 0xB32FA3CA unchanged).
 (1) REAL-data range: split-conformal half-widths from HTT LOSO residuals, nested by person (each held-out person's
     coverage uses a width computed from the other 64 people only); exported HG2_CONF_HALF_{NOW,F20}_REAL. Band rule:
     half-width = max(1.645 sd_sim, HALF_REAL) until wrist data from the wear test exists. Per-person coverage
     distributions (share of persons < 80 %) on the 100 SIM calibration persons and on HTT, old vs new widths.
 (2) FAIR NN vs v1.2: BOTH rules get the same threshold grid and the same nested tuning (SIM: 5 person folds; HTT: LOSO),
     at FA budgets 0.05/0.10/0.15/0.20 per h; SIM per day type + errand days (S4) + hot-night days (S3); HTT on identical
     minutes, all 65 people and the 13 people v1.2 never saw (v1 sealed list, used only as a membership filter).
Labels: SIM = "SIMULATION (Virtual Elders v4; known too-tolerant at humid rest, bed rest, and HR)"; HTT = young adults
18-33, chamber walk, DEV. Writes runs/<tag>/results_fix_b2.json."""
import json, os
import numpy as np
from .common import CACHE, RUNS, SEED, data_provenance, assert_no_sealed, LABEL_SIM, LABEL_HTT
from . import nn
from .train import norm
from .eval import members, ens_predict
from .danger_calib import ensemble
from .simio import persons_table, profile_of
from .htt_eval_lib import Sessions, aggregate, pick_cut
from .m5 import margins, cq

BUDGETS = [0.05, 0.10, 0.15, 0.20]
OFFS = [float(x) for x in np.round(np.arange(-0.8, 0.81, 0.05), 2)] + [9.0]
CUTS = [float(c) for c in np.round(np.arange(-6, 6.01, 0.25), 2)] + [1e9]


def per_person_cov(err, half, groups):
    pp = np.array([np.mean(err[groups == g] <= half[groups == g]) for g in np.unique(groups)])
    return dict(pooled=float(np.mean(err <= half) * 100), per_person_median=float(np.median(pp) * 100),
                per_person_min=float(pp.min() * 100), share_persons_below_80=float(np.mean(pp < 0.8) * 100),
                share_persons_above_98=float(np.mean(pp > 0.98) * 100), n_persons=int(len(pp)))


# ----------------------------------------------------------------------------------------------- (1) real-data widths
def real_widths():
    d = np.load(os.path.join(CACHE, "htt_oof.npz"), allow_pickle=True)
    E = ensemble(d["raw"], d["ym"], d["ys"]); Y = d["Y"]; subj = d["subj"]
    out = dict(label=LABEL_HTT + " - nested LOSO split-conformal")
    for h, j in (("now", 0), ("20", 1), ("30", 2)):
        ok = np.isfinite(Y[:, j]); e = np.abs(E["core_" + h] - Y[:, j]); sd = E["sd_" + h]
        # nested: the width that scores person s comes from the other 64 people
        w_loso = np.full(len(e), np.nan); w_rob = np.full(len(e), np.nan)
        for s in np.unique(subj):
            m = subj == s; o = ok & ~m
            w_loso[m] = cq(e[o])
            # person-robust width: smallest w with >= 90 % of the OTHER people covered >= 80 % (person-level quantile)
            pq = np.array([np.quantile(e[o & (subj == g)], 0.80) for g in np.unique(subj[o])])
            w_rob[m] = float(np.quantile(pq, 0.90))
        old = 1.645 * np.maximum(sd, 0.0)
        res = dict(width_final_pooled90=cq(e[ok]),
                   width_final_person_robust=float(np.quantile([np.quantile(e[ok & (subj == g)], 0.80) for g in np.unique(subj[ok])], 0.90)),
                   coverage_old_sim_sd=per_person_cov(e[ok], old[ok], subj[ok]),
                   coverage_new_max_pooled=per_person_cov(e[ok], np.maximum(old, w_loso)[ok], subj[ok]),
                   coverage_new_max_person_robust=per_person_cov(e[ok], np.maximum(old, w_rob)[ok], subj[ok]),
                   median_old_half=float(np.median(old[ok])))
        out["horizon_" + h] = res
    return out


def sim_coverage(Ps, N, W):
    d = np.load(os.path.join(CACHE, "sim_val.npz")); X, Y, M = d["X"], d["Y"], d["M"]
    pid = M[:, 0].astype(int); assert_no_sealed(np.unique(pid))
    E, _ = ens_predict(Ps, nn.normalise_x(X, N["xm"], N["xs"]), N)
    out = dict(label=LABEL_SIM + " - 100 calibration persons")
    for h, j, wk in (("now", 0, "now"), ("20", 1, "20")):
        ok = np.isfinite(Y[:, j]); e = np.abs(E["core_" + h] - Y[:, j]); old = 1.645 * E["sd_" + h]
        out["horizon_" + h] = dict(sim_sd_only=per_person_cov(e[ok], old[ok], pid[ok]),
                                   max_sd_real_pooled=per_person_cov(e[ok], np.maximum(old, W[wk]["pooled"])[ok], pid[ok]),
                                   max_sd_real_person_robust=per_person_cov(e[ok], np.maximum(old, W[wk]["robust"])[ok], pid[ok]),
                                   person_spearman_mean_sd_vs_mae=float(_spear([old[ok][pid[ok] == g].mean() for g in np.unique(pid[ok])],
                                                                               [e[ok][pid[ok] == g].mean() for g in np.unique(pid[ok])])))
    return out, (X, Y, M, E)


def _spear(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b)); return np.corrcoef(ra, rb)[0, 1]


# ----------------------------------------------------------------------------------------------- (2) fair comparison
def tune_compare(S, rules, thr, folds):
    """rules: {name: (fn(i, c) -> mask, grid)}. Same nested procedure for every rule: per fold, the threshold with the
    highest sensitivity at FA/h <= budget on the other folds, scored on the held-out fold."""
    out = {}
    tabs = {n: S.table(fn, len(g), thr) for n, (fn, g) in rules.items()}
    for B in BUDGETS:
        res = {}
        for n, (fn, g) in rules.items():
            det, lead, fa, hours, has = tabs[n]
            D = np.zeros(len(S.keys)); L = np.full(len(S.keys), np.nan); FA = np.zeros(len(S.keys)); ch = []
            for k in np.unique(folds):
                tr = folds != k; c = pick_cut(det, fa, hours, has, tr, g, B); ch.append(g[c])
                D[~tr], L[~tr], FA[~tr] = det[~tr, c], lead[~tr, c], fa[~tr, c]
            a = aggregate(D, L, FA, hours, has, S.subj, boot=300)
            res[n] = dict(detected=a["detected"], events=a["events"], sensitivity=a["sensitivity"], sensitivity_95=a["sensitivity_95"],
                          fa_per_h=a["fa_per_h"], fa_per_h_95=a["fa_per_h_95"], lead_median=a["lead_median"],
                          threshold_median=float(np.median(ch)))
        names = list(rules)
        # paired difference (subject bootstrap) of the first two rules
        res["sens_diff_%s_minus_%s" % (names[1], names[0])] = res[names[1]]["sensitivity"] - res[names[0]]["sensitivity"]
        out["budget_%.2f" % B] = res
    return out


def sim_fair(pack):
    X, Y, M, E = pack
    meta = json.load(open(os.path.join(CACHE, "sim_meta.json"))); mc = meta["meta_cols"]; col = lambda n: M[:, mc.index(n)]
    P = persons_table(); pid = col("pid").astype(int); t = col("t_min").astype(int)
    md = np.zeros(len(pid))
    for p in np.unique(pid): md[pid == p] = margins(float(P.loc[p, "age"]), profile_of(P.loc[p])["med_flags"])[0]
    key = pid * 100 + t // 1440; dt = col("daytype"); loc = col("location"); tin = col("T_in"); mod = t % 1440
    night = (mod >= 1380) | (mod < 420)
    errand_days = set(np.unique(key[loc == 2])); hot_night = set(np.unique(key[night & (tin >= 28)]))
    groups = {"S1 ordinary": dt == 0, "PRE": dt == 1, "S2 heat wave": dt == 3, "POST": dt == 2,
              "S4 errand days (any minute out)": np.isin(key, list(errand_days)),
              "S3 hot-night days (bedroom >= 28 C at night)": np.isin(key, list(hot_night))}
    out = dict(label=LABEL_SIM + " - 100 calibration persons; both rules tuned by the same nested 5-person-fold procedure",
               rules="Drink: v1.2 f20 >= 37.85 - margin + d vs hg2 core_20 (k_sd = 0) >= 37.85 - margin + d, d in -0.8..+0.8; "
                     "Danger: v1.2 logistic z >= c vs hg2 logit_p385 >= c, c in -6..6; 2-min onset, REPORT 5 FA definition")
    for gname, sel in groups.items():
        ks = np.unique(key[sel])
        if len(ks) < 5: continue
        G = {n: [] for n in ("core", "v12", "nn", "z", "lp", "md", "subj", "sess")}
        for k in ks:
            r = np.where((key == k) & sel)[0]; mm = mod[r]
            def g(v, fill):
                a = np.full(1440, fill, float); a[mm] = v[r]; return a
            G["core"].append(g(Y[:, 0].astype(float), np.nan)); G["v12"].append(g(col("v12_f20"), -99)); G["nn"].append(g(E["core_20"], -99))
            G["z"].append(g(col("v12_z"), -99)); G["lp"].append(g(E["lp385"], -99)); G["md"].append(np.full(1440, md[r[0]]))
            G["subj"].append(np.full(1440, k // 100)); G["sess"].append(np.full(1440, k % 100))
        G = {n: np.concatenate(v) for n, v in G.items()}
        S = Sessions(G["core"], G["subj"], G["sess"])
        us = np.unique(S.subj); f = dict(zip(us, np.random.default_rng(SEED + 77).permutation(len(us)) % 5))
        folds = np.array([f[s] for s in S.subj])
        R = lambda i: S.rows[i]
        drink = {"v1.2": (lambda i, c: G["v12"][R(i)] >= 37.85 - G["md"][R(i)] + OFFS[c], OFFS),
                 "hg2": (lambda i, c: G["nn"][R(i)] >= 37.85 - G["md"][R(i)] + OFFS[c], OFFS)}
        danger = {"v1.2": (lambda i, c: G["z"][R(i)] >= CUTS[c], CUTS), "hg2": (lambda i, c: G["lp"][R(i)] >= CUTS[c], CUTS)}
        out[gname] = dict(n_person_days=len(ks), drink=tune_compare(S, drink, 38.0, folds), danger=tune_compare(S, danger, 38.5, folds))
    return out


def htt_fair():
    d = np.load(os.path.join(CACHE, "htt_oof.npz"), allow_pickle=True)
    E = ensemble(d["raw"], d["ym"], d["ys"]); Y = d["Y"]; subj = d["subj"]
    v1_sealed = set(json.load(open("/home/claude/hgmodel/sealed_split.json"))["sealed_subjects"])   # membership filter only
    ok = np.isfinite(Y[:, 0]); out = dict(label=LABEL_HTT + " - identical minutes for both models")
    us = np.unique(subj); idx = {u: np.where(subj == u)[0] for u in us}
    for name, people in (("all 65 (v1.2 coefficients were fit on 52 of them)", us), ("13 people v1.2 never saw", [u for u in us if u in v1_sealed])):
        m = ok & np.isin(subj, list(people))
        e2 = np.abs(E["core_now"] - Y[:, 0]); e1 = np.abs(d["aux_v12_est"] - Y[:, 0])
        rng = np.random.default_rng(SEED); diffs = []
        for _ in range(2000):
            r = np.concatenate([idx[u] for u in rng.choice(list(people), len(people))]); r = r[ok[r]]
            diffs.append(e2[r].mean() - e1[r].mean())
        out[name] = dict(n_people=len(people), n_minutes=int(m.sum()), hg2_mae=float(e2[m].mean()), v12_mae=float(e1[m].mean()),
                         diff_hg2_minus_v12=float(e2[m].mean() - e1[m].mean()), diff_95=[float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
                         hg2_within_0_5=float(np.mean(e2[m] <= 0.5) * 100), v12_within_0_5=float(np.mean(e1[m] <= 0.5) * 100))
    S = Sessions(Y[:, 0].astype(float), subj, d["sess"]); folds = np.array([np.where(us == s)[0][0] for s in S.subj])   # LOSO
    R = lambda i: S.rows[i]
    v12f, nnf, z, lp = d["aux_v12_f20"], E["core_20"], d["aux_v12_z"], E["lp385"]
    out["drink_nested_LOSO"] = tune_compare(S, {"v1.2": (lambda i, c: v12f[R(i)] >= 37.85 + OFFS[c], OFFS),
                                                "hg2": (lambda i, c: nnf[R(i)] >= 37.85 + OFFS[c], OFFS)}, 38.0, folds)
    out["danger_nested_LOSO"] = tune_compare(S, {"v1.2": (lambda i, c: z[R(i)] >= CUTS[c], CUTS),
                                                 "hg2": (lambda i, c: lp[R(i)] >= CUTS[c], CUTS)}, 38.5, folds)
    return out


def main():
    N = norm(); Ps = members()
    res = dict(provenance=data_provenance(), weights_crc="0xB32FA3CA (unchanged; no retraining)")
    res["real_widths_htt"] = rw = real_widths()
    W = {"now": dict(pooled=rw["horizon_now"]["width_final_pooled90"], robust=rw["horizon_now"]["width_final_person_robust"]),
         "20": dict(pooled=rw["horizon_20"]["width_final_pooled90"], robust=rw["horizon_20"]["width_final_person_robust"])}
    res["sim_calibration_coverage"], pack = sim_coverage(Ps, N, W)
    res["export"] = dict(HG2_CONF_HALF_NOW_REAL=W["now"]["pooled"], HG2_CONF_HALF_F20_REAL=W["20"]["pooled"],
                         HG2_CONF_HALF_NOW_REAL_PERSON=W["now"]["robust"], HG2_CONF_HALF_F20_REAL_PERSON=W["20"]["robust"],
                         rule="displayed/alarm half-width = max(1.645*sd_sim, HG2_CONF_HALF_*_REAL) until wear-test wrist data exists; "
                              "_PERSON = width for >= 90 % of held-out people to get >= 80 % coverage")
    res["fair_sim"] = sim_fair(pack)
    res["fair_htt"] = htt_fair()
    json.dump(res, open(os.path.join(RUNS, "results_fix_b2.json"), "w"), indent=1)
    print(json.dumps(res["export"], indent=1))
    return res


if __name__ == "__main__":
    main()
