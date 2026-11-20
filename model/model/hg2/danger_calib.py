"""ARCH 4.4 step 4: nested LOSO calibration on HTT-DEV (young adults 18-33, chamber walk, DEV) of
  DANGER = (v1.2 logistic z >= -1.450 for 2 min) OR (hg2 logit_p385 >= cut_385 for 2 min), event 38.5, combined <= 0.10 FA/h
  DRINK  = (hg2 f20_eff >= 37.85 for 2 min) OR (hg2 logit_p38 >= cut_38 for 2 min),          event 38.0, combined <= 0.15 FA/h
For every left-out person: the cut is chosen on the other 64 people's out-of-fold predictions (models fine-tuned without
those people, REPORT 5b practice), then that person is scored. hg2 predictions come from train.py --loso (each member
fine-tuned without the left-out subject; pretraining never saw HTT). Exported cuts = the same choice on all 65.
Writes model/results_danger_hg2.json."""
import json, os
import numpy as np
from .common import RUNS, CACHE, MODEL, data_provenance, LABEL_HTT
from .htt_eval_lib import Sessions, pick_cut, aggregate

CUTS = [float(c) for c in np.round(np.arange(-6, 6.01, 0.25), 2)] + [1e9]
V12_CUT = -1.450010
T_DRINK, T_COOL = 37.85, 38.35


EPS_V = 1e-3   # == nn.EPS_V


def ensemble(raw, ym, ys, k_sd=1.0):
    """M6.2: total sd = sqrt(mean aleatoric (v^2 + eps) + between-member variance of the means), in degC.
    f20_eff = core_20 + k_sd * min(sd_20, 0.30) (M6.3: k_sd = largest coefficient meeting the HTT Drink budget)."""
    raw = np.where(np.isfinite(raw), raw, 0)
    mu = raw.mean(0)
    core = np.clip(mu[:, :3] * ys + ym, 30, 45)
    if raw.shape[2] >= 9:
        ale = (raw[:, :, 6:9] ** 2 + EPS_V).mean(0); btw = raw[:, :, :3].var(0)
        sdc = np.sqrt(ale + btw) * ys
    else:
        sdc = raw.std(0)[:, :3] * ys
    return dict(core_now=core[:, 0], core_20=core[:, 1], core_30=core[:, 2], sd_now=sdc[:, 0], sd_20=sdc[:, 1], sd_30=sdc[:, 2],
                f20_eff=core[:, 1] + k_sd * np.minimum(sdc[:, 1], 0.30), btw_sd_now=(np.sqrt(raw[:, :, 0].var(0)) * ys[0]), lp38=mu[:, 3], lp385=mu[:, 4], strain=np.clip(mu[:, 5], 0, 10))


def load():
    d = np.load(os.path.join(CACHE, "htt_oof.npz"), allow_pickle=True)
    E = ensemble(d["raw"], d["ym"], d["ys"])
    return d, E


def nested(S, base, score, thr, fa_max):
    """base: bool per row (fixed path); score: float per row (NN logit path, swept). returns per-session det/lead/fa at
    the nested cut + the pooled cut on all subjects"""
    det, lead, fa, hours, has = S.table(lambda i, c: base[S.rows[i]] | (np.nan_to_num(score[S.rows[i]], nan=-99) >= CUTS[c]), len(CUTS), thr)
    n = len(S.keys); D = np.zeros(n); L = np.full(n, np.nan); FA = np.zeros(n); chosen = {}
    for s in np.unique(S.subj):
        te = S.subj == s; c = pick_cut(det, fa, hours, has, ~te, CUTS, fa_max); chosen[str(s)] = CUTS[c]
        D[te], L[te], FA[te] = det[te, c], lead[te, c], fa[te, c]
    pooled = pick_cut(det, fa, hours, has, np.ones(n, bool), CUTS, fa_max)
    return (D, L, FA, hours, has), chosen, CUTS[pooled]


def fixed(S, mask, thr):
    det, lead, fa, hours, has = S.table(lambda i, c: mask[S.rows[i]], 1, thr)
    return det[:, 0], lead[:, 0], fa[:, 0], hours, has


def paired(a, b, subj, has, boot=2000, seed=7):
    """sensitivity(b) - sensitivity(a) in points, 95 % by resampling subjects"""
    us = np.unique(subj); idx = {u: np.where(subj == u)[0] for u in us}; rng = np.random.default_rng(seed); out = []
    for _ in range(boot):
        r = np.concatenate([idx[u] for u in rng.choice(us, len(us))]); h = has[r]
        out.append(100 * (b[r][h].sum() - a[r][h].sum()) / max(h.sum(), 1))
    return dict(mean=float(100 * (b[has].sum() - a[has].sum()) / has.sum()), ci95=[float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))])


def main():
    d, E = load()
    S = Sessions(d["Y"][:, 0].astype(float), d["subj"], d["sess"])
    subj_s = S.subj
    z = d["aux_v12_z"]; f20v = d["aux_v12_f20"]
    res = dict(label=LABEL_HTT, provenance=data_provenance(), n_people=int(len(np.unique(subj_s))), n_sessions=len(S.keys),
               definitions=__doc__)
    # ---- Danger
    dz = z >= V12_CUT
    v12 = fixed(S, dz, 38.5)
    orr, chosen385, pooled385 = nested(S, dz, E["lp385"], 38.5, 0.10)
    nn_only, _, _ = nested(S, np.zeros(len(z), bool), E["lp385"], 38.5, 0.10)
    res["danger"] = {"v1.2 logistic alone (z >= -1.450, 2 min)": aggregate(*v12, subj_s),
                     "OR-rule v1.2 OR hg2 logit_p385 (nested cut, <= 0.10/h)": aggregate(*orr, subj_s),
                     "hg2 logit_p385 alone (nested cut, <= 0.10/h)": aggregate(*nn_only, subj_s),
                     "paired_OR_minus_v12_points": paired(v12[0], orr[0], subj_s, v12[4]),
                     "cut_385_nested_per_fold": dict(median=float(np.median(list(chosen385.values()))),
                                                     range=[min(chosen385.values()), max(chosen385.values())],
                                                     share_off=float(np.mean([c > 1e8 for c in chosen385.values()]))),
                     "cut_385_pooled_all_65": pooled385}
    # ---- Drink
    # M6.3: largest sd coefficient k with Drink (f20 + k sd) <= 0.15 FA/h at >= 85 % sensitivity on HTT-DEV (pooled LOSO OOF)
    ksweep = []
    for kk in np.round(np.arange(0, 3.01, 0.1), 2):
        a = aggregate(*fixed(S, E["core_20"] + kk * np.minimum(E["sd_20"], 0.30) >= T_DRINK, 38.0), subj_s, boot=1)
        ksweep.append(dict(k=float(kk), sensitivity=a["sensitivity"], fa_per_h=a["fa_per_h"], lead_median=a["lead_median"]))
    okk = [r["k"] for r in ksweep if r["fa_per_h"] <= 0.15 and r["sensitivity"] >= 85]
    K_SD = max(okk) if okk else 0.0
    res["k_sd_sweep_drink"] = ksweep; res["k_sd_chosen"] = K_SD
    res["k_sd_rule"] = "largest k in 0..3 (step 0.1) with Drink FA/h <= 0.15 and sensitivity >= 85 % (M6.3); 1.0 restores D7"
    E = ensemble(d["raw"], d["ym"], d["ys"], K_SD)
    df = E["f20_eff"] >= T_DRINK          # M6.3: f20_eff = core_20 + k sd
    v12d = fixed(S, f20v >= T_DRINK, 38.0)
    hg2d = fixed(S, df, 38.0)
    ord_, chosen38, pooled38 = nested(S, df, E["lp38"], 38.0, 0.15)
    res["drink"] = {"v1.2 f20 >= 37.85": aggregate(*v12d, subj_s), "hg2 f20_eff = core_20 + k sd (k = %.1f) >= 37.85" % K_SD: aggregate(*hg2d, subj_s),
                    "hg2 core_20 alone (k = 0) >= 37.85": aggregate(*fixed(S, E["core_20"] >= T_DRINK, 38.0), subj_s, boot=300),
                    "hg2 f20 OR logit_p38 (nested cut, <= 0.15/h)": aggregate(*ord_, subj_s),
                    "paired_hg2_f20eff_minus_v12_points": paired(v12d[0], hg2d[0], subj_s, v12d[4]),
                    "cut_38_nested_per_fold": dict(median=float(np.median(list(chosen38.values()))),
                                                   range=[min(chosen38.values()), max(chosen38.values())],
                                                   share_off=float(np.mean([c > 1e8 for c in chosen38.values()]))),
                    "cut_38_pooled_all_65": pooled38}
    curve = []
    for th in np.round(np.arange(37.75, 38.16, 0.05), 2):        # M1.4: trade-off curve reported, threshold NOT changed by B2
        a = aggregate(*fixed(S, E["core_20"] >= th, 38.0), subj_s, boot=1)
        curve.append(dict(threshold=float(th), sensitivity=a["sensitivity"], fa_per_h=a["fa_per_h"], lead_median=a["lead_median"]))
    res["drink"]["tradeoff_curve_f20_threshold (information only; thresholds stay v1.2)"] = curve
    # ---- Cool (v1.2 threshold, event 38.5)
    res["cool"] = {"v1.2 f20 >= 38.35": aggregate(*fixed(S, f20v >= T_COOL, 38.5), subj_s),
                   "hg2 f20_eff (k sd) >= 38.35": aggregate(*fixed(S, E["f20_eff"] >= T_COOL, 38.5), subj_s),
                   "hg2 core_20 alone >= 38.35": aggregate(*fixed(S, E["core_20"] >= T_COOL, 38.5), subj_s, boot=300)}
    res["export_cuts"] = dict(HG2_LOGIT_CUT_38=pooled38, HG2_LOGIT_CUT_385=pooled385, HG2_SD_K=K_SD,
                              note="1e9 = NN path never fires (the pooled choice found no cut that adds sensitivity within the FA budget)")
    json.dump(res, open(os.path.join(RUNS, "results_danger_hg2.json"), "w"), indent=1)
    for k in ("danger", "drink", "cool"):
        for n, v in res[k].items():
            if isinstance(v, dict) and "sensitivity" in v:
                print("%-6s %-60s %3d/%3d = %5.1f%% [%4.0f-%4.0f]  FA/h %.3f [%.3f-%.3f]  lead %s" % (
                    k, n, v["detected"], v["events"], v["sensitivity"], *v["sensitivity_95"], v["fa_per_h"], *v["fa_per_h_95"], v["lead_median"]))
    print("cuts", res["export_cuts"])
    return res


if __name__ == "__main__":
    main()
