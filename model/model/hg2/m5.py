"""Decision M5 (Nov 12): M5.1 watch tier on f20 = core_20 (no +sd); M5.2 split-conformal per-person interval conditioned on
the Twin state ("reading today" vs "no reading"); M5.3 does the NN logit path add sensitivity at the same FA budget on
SIM-DEV heat-wave days (S2, incl. their S3-type hot nights)?
SIM part: the 100 CALIBRATION persons (never trained on, never early-stopped on). Coverage is cross-fitted (5 person
folds: quantile from 80 persons, coverage on the other 20); the exported half-widths use all 100.
HTT part (young adults 18-33, chamber walk, DEV): LOSO conformal on the out-of-fold hg2 predictions.
"Reading today": one oral reading per person-day at the first valid minute >= 09:00 (HTT: session minute 10),
T_read = T_core + N(0, 0.15) (oral thermometer +-0.1-0.2 C), Twin core_offset += 0.25 (B3 M4 beta) (T_read - core_now) clipped to
+-0.8 (ARCH 5), applied to the rest of that day. Writes runs/<tag>/results_m5.json."""
import json, os
import numpy as np
from .common import CACHE, RUNS, SEED, data_provenance, assert_no_sealed, LABEL_SIM, LABEL_HTT
from . import nn
from .train import norm
from .eval import members, ens_predict
from .danger_calib import ensemble
from .simio import persons_table, profile_of
from .htt_eval_lib import Sessions, aggregate, pick_cut

LEVEL = 0.90
CUTS = [float(c) for c in np.round(np.arange(-6, 6.01, 0.25), 2)] + [1e9]


def cq(r, level=LEVEL):
    r = np.sort(r[np.isfinite(r)]); n = len(r)
    return float(r[min(n - 1, int(np.ceil((n + 1) * level)) - 1)])


def reading_offsets(day_key, t, core_true, core_now, start_ok, rng):
    """per row: offset applied (NaN before the day's reading / no reading that day)"""
    off = np.full(len(t), np.nan)
    order = np.lexsort((t, day_key))
    dk = day_key[order]; bounds = np.flatnonzero(np.r_[True, dk[1:] != dk[:-1], True])
    for a, b in zip(bounds[:-1], bounds[1:]):
        idx = order[a:b]; ok = idx[start_ok[idx]]
        if not len(ok): continue
        r0 = ok[0]
        o = float(np.clip(0.25 * (core_true[r0] + rng.normal(0, 0.15) - core_now[r0]), -0.8, 0.8))
        sel = idx[t[idx] >= t[r0]]; off[sel] = o
    return off


def conformal(res_no, res_rd, groups, nfold=5, seed=SEED):
    """res_*: |residual| per row (res_rd NaN where no reading yet); groups: person id. Cross-fitted coverage + final q."""
    us = np.unique(groups); rng = np.random.default_rng(seed); f = dict(zip(us, rng.permutation(len(us)) % nfold))
    fold = np.array([f[g] for g in groups]); out = {}
    for name, r in (("no_reading", res_no), ("reading_today", res_rd)):
        cov = np.full(len(r), np.nan); qs = []
        for k in range(nfold):
            q = cq(r[fold != k]); qs.append(q); m = (fold == k) & np.isfinite(r); cov[m] = r[m] <= q
        pp = [float(np.nanmean(cov[groups == g])) for g in us if np.isfinite(cov[groups == g]).any()]
        out[name] = dict(half_width_90=cq(r), fold_half_widths=qs, crossfit_coverage_pct=float(np.nanmean(cov) * 100),
                         per_person_coverage_median=float(np.median(pp) * 100), per_person_coverage_p10=float(np.percentile(pp, 10) * 100),
                         share_persons_below_80pct=float(np.mean(np.array(pp) < 0.8) * 100), n_rows=int(np.isfinite(r).sum()))
    out["watch_lower_uncalibrated_C"] = float(min(0.10, max(0.0, (out["no_reading"]["half_width_90"] - out["reading_today"]["half_width_90"]) / 2)))
    return out


def sim_m5(Ps, N, view="val"):
    d = np.load(os.path.join(CACHE, "sim_%s.npz" % view)); X, Y, M = d["X"], d["Y"], d["M"]
    meta = json.load(open(os.path.join(CACHE, "sim_meta.json"))); mc = meta["meta_cols"]; col = lambda n: M[:, mc.index(n)]
    pid = col("pid").astype(int); assert_no_sealed(np.unique(pid))
    assert not set(np.unique(pid)) & (set(meta["train_ids"]) | set(meta["es_ids"])), "calibration person used in training"
    E, _ = ens_predict(Ps, nn.normalise_x(X, N["xm"], N["xs"]), N)
    t = col("t_min").astype(int); day = t // 1440; key = pid * 100 + day
    rng = np.random.default_rng(SEED + 55)
    off = reading_offsets(key, t, Y[:, 0].astype(float), E["core_now"], (t % 1440) >= 540, rng)
    out = dict(label=LABEL_SIM + " - 100 calibration persons, view " + view)
    for h, j in (("now", 0), ("20", 1), ("30", 2)):
        e_no = np.abs(E["core_" + h] - Y[:, j]); e_rd = np.abs(E["core_" + h] + off - Y[:, j])
        out["horizon_" + h] = conformal(e_no, e_rd, pid)
        out["horizon_" + h]["mae_no_reading"] = float(np.nanmean(e_no)); out["horizon_" + h]["mae_reading_today"] = float(np.nanmean(e_rd))
    # per kappa tercile coverage of the final widths (no reading)
    q = out["horizon_now"]["no_reading"]["half_width_90"]
    out["coverage_now_no_reading_per_kappa_tercile_final_q"] = {"T%d" % (k + 1): float(np.mean((np.abs(E["core_now"] - Y[:, 0]) <= q)[col("kappa_t") == k]) * 100) for k in range(3)}
    return out, (X, Y, M, E, mc)


def margins(age, f):
    md = mc = 0.20 if age >= 65 else 0.0
    if f & (2 | 8): md += 0.10
    if f & 4: md += 0.10; mc += 0.10
    if f & 1: md += 0.10; mc += 0.10
    return min(md, 0.20), min(mc, 0.20)


def gain_test(pack, k_sd, nfold=5):
    """M6.4: NN vs v1.2 where the NN has its extra senses: SIM-DEV calibration persons, per day type (S1 ordinary, PRE,
    S2 heat wave incl. S3-type hot nights, POST; S4 errands happen inside these days), per-minute series per person-day.
    Same FA budget: the NN rule's threshold is chosen per person fold on the other folds so its FA/h <= the v1.2 rule's
    FA/h there, then scored on the held-out fold. Rules: Drink v1.2 f20 >= 37.85 - margin vs NN f20_eff (+offset);
    Danger v1.2 logistic z >= -1.450 vs NN logit_p385 alone vs OR."""
    X, Y, M, E, mc = pack; col = lambda n: M[:, mc.index(n)]
    P = persons_table(); pid = col("pid").astype(int); t = col("t_min").astype(int)
    md = np.zeros(len(pid))
    for p in np.unique(pid):
        md[pid == p] = margins(float(P.loc[p, "age"]), profile_of(P.loc[p])["med_flags"])[0]
    key = pid * 100 + t // 1440; dt = col("daytype")
    f20e = E["core_20"] + k_sd * np.minimum(E["sd_20"], 0.30)
    names = {0: "S1 ordinary", 1: "PRE", 2: "POST", 3: "S2 heat wave (incl. hot nights)"}
    out = dict(note=gain_test.__doc__, k_sd=k_sd)
    OFFS = [float(x) for x in np.round(np.arange(-0.6, 0.61, 0.05), 2)] + [9.0]
    for cls in range(4):
        sel = dt == cls; ks = np.unique(key[sel])
        if not len(ks): continue
        G = {n: [] for n in ("core", "v12f20", "nnf20", "z", "lp385", "md", "subj", "sess")}
        for k in ks:
            r = np.where((key == k) & sel)[0]; mm = t[r] % 1440
            def g(v, fill):
                a_ = np.full(1440, fill, float); a_[mm] = v[r]; return a_
            G["core"].append(g(Y[:, 0].astype(float), np.nan)); G["v12f20"].append(g(col("v12_f20"), -99)); G["nnf20"].append(g(f20e, -99))
            G["z"].append(g(col("v12_z"), -99)); G["lp385"].append(g(E["lp385"], -99)); G["md"].append(np.full(1440, md[r[0]]))
            G["subj"].append(np.full(1440, k // 100)); G["sess"].append(np.full(1440, k % 100))
        G = {n: np.concatenate(v) for n, v in G.items()}
        S = Sessions(G["core"], G["subj"], G["sess"])
        us = np.unique(S.subj); rng = np.random.default_rng(SEED + 77); f = dict(zip(us, rng.permutation(len(us)) % nfold))
        fold = np.array([f[x] for x in S.subj]); res = {}
        for name, base_mask, nn_fn, ncut, thr in (
                ("Drink", G["v12f20"] >= 37.85 - G["md"], lambda i, c: G["nnf20"][S.rows[i]] >= 37.85 - G["md"][S.rows[i]] + OFFS[c], len(OFFS), 38.0),
                ("Danger_NN_alone", G["z"] >= -1.450010, lambda i, c: G["lp385"][S.rows[i]] >= CUTS[c], len(CUTS), 38.5),
                ("Danger_OR", G["z"] >= -1.450010, lambda i, c: (G["z"][S.rows[i]] >= -1.450010) | (G["lp385"][S.rows[i]] >= CUTS[c]), len(CUTS), 38.5)):
            bd, bl, bf, hours, has = S.table(lambda i, c: base_mask[S.rows[i]], 1, thr); bd, bl, bf = bd[:, 0], bl[:, 0], bf[:, 0]
            det, lead, fa, _, _ = S.table(nn_fn, ncut, thr)
            grid = OFFS if name == "Drink" else CUTS
            D = np.zeros(len(S.keys)); L = np.full(len(S.keys), np.nan); FA = np.zeros(len(S.keys)); ch = []
            for k in range(nfold):
                tr = fold != k; budget = bf[tr].sum() / hours[tr].sum()
                c = pick_cut(det, fa, hours, has, tr, grid, budget + 1e-12); ch.append(grid[c])
                D[~tr], L[~tr], FA[~tr] = det[~tr, c], lead[~tr, c], fa[~tr, c]
            ba = aggregate(bd, bl, bf, hours, has, S.subj, boot=300); na = aggregate(D, L, FA, hours, has, S.subj, boot=300)
            res[name] = dict(v12=ba, nn_same_budget=na, gain_points=float(na["sensitivity"] - ba["sensitivity"]), chosen=ch,
                             nn_beats_v12=bool(na["sensitivity"] > ba["sensitivity"] and na["fa_per_h"] <= ba["fa_per_h"] * 1.05))
        out[names[cls]] = res
    return out


def htt_m5():
    d = np.load(os.path.join(CACHE, "htt_oof.npz"), allow_pickle=True)
    E = ensemble(d["raw"], d["ym"], d["ys"]); Y = d["Y"]; subj = d["subj"]; sess = d["sess"]
    _, key = np.unique(np.array([str(a) + "|" + str(b) for a, b in zip(subj, sess)]), return_inverse=True)
    # minute index within session
    t = np.zeros(len(key), int); _, first = np.unique(key, return_index=True)
    for k, f0 in zip(*np.unique(key, return_index=True)):
        r = np.where(key == k)[0]; t[r] = np.arange(len(r))
    off = reading_offsets(key, t, np.nan_to_num(Y[:, 0], nan=np.nan).astype(float), E["core_now"], (t >= 10) & np.isfinite(Y[:, 0]),
                          np.random.default_rng(SEED + 56))
    out = dict(label=LABEL_HTT + " - LOSO conformal (quantile from the other 64 people)")
    for h, j in (("now", 0), ("20", 1)):
        e_no = np.abs(E["core_" + h] - Y[:, j]); e_rd = np.abs(E["core_" + h] + off - Y[:, j])
        res = {}
        for name, r in (("no_reading", e_no), ("reading_today", e_rd)):
            cov = np.full(len(r), np.nan)
            for s in np.unique(subj):
                m = subj == s; q = cq(r[~m]); mm = m & np.isfinite(r); cov[mm] = r[mm] <= q
            res[name] = dict(half_width_90_all=cq(r), loso_coverage_pct=float(np.nanmean(cov) * 100), mae=float(np.nanmean(r)))
        out["horizon_" + h] = res
    return out


def main():
    N = norm(); Ps = members()
    res = dict(provenance=data_provenance(), decision="M5.1-M5.3", level=LEVEL)
    s, pack = sim_m5(Ps, N, "val"); res["sim_conformal"] = s
    if os.path.exists(os.path.join(CACHE, "sim_valaug.npz")):
        res["sim_conformal_hr_scaled_M3.2"], _ = sim_m5(Ps, N, "valaug")
    res["htt_conformal"] = htt_m5()
    k_sd = json.load(open(os.path.join(RUNS, "results_danger_hg2.json")))["k_sd_chosen"]
    res["m6_4_nn_vs_v12_same_budget"] = gain_test(pack, k_sd)
    res["export"] = dict(HG2_RANGE90_NOW_NOREAD=s["horizon_now"]["no_reading"]["half_width_90"],
                         HG2_RANGE90_NOW_READ=s["horizon_now"]["reading_today"]["half_width_90"],
                         HG2_RANGE90_F20_NOREAD=s["horizon_20"]["no_reading"]["half_width_90"],
                         HG2_RANGE90_F20_READ=s["horizon_20"]["reading_today"]["half_width_90"],
                         HG2_WATCH_LOWER_UNCAL=s["horizon_20"]["watch_lower_uncalibrated_C"],
                         HG2_CONF_HALF_CAL=s["horizon_now"]["reading_today"]["half_width_90"],     # B5 ask (a): calibrated 90 % half-width
                         HG2_CONF_HALF_UNCAL=s["horizon_now"]["no_reading"]["half_width_90"])
    json.dump(res, open(os.path.join(RUNS, "results_m5.json"), "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("export",)}, indent=1))
    for dname, v in res["m6_4_nn_vs_v12_same_budget"].items():
        if not isinstance(v, dict): continue
        for rn, x in v.items():
            print(dname, rn, "v12 %d/%d %.1f%% %.3f/h | nn %.1f%% %.3f/h | gain %+.1f" % (x["v12"]["detected"], x["v12"]["events"], x["v12"]["sensitivity"],
                  x["v12"]["fa_per_h"], x["nn_same_budget"]["sensitivity"], x["nn_same_budget"]["fa_per_h"], x["gain_points"]))
    for h in ("now", "20"):
        x = s["horizon_" + h]; print(h, {n: (round(x[n]["half_width_90"], 3), round(x[n]["crossfit_coverage_pct"], 1)) for n in ("no_reading", "reading_today")})
    return res


if __name__ == "__main__":
    main()
