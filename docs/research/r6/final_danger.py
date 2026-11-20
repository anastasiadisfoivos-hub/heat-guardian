#!/usr/bin/env python3
"""R6 E6: MOMENTUM DANGER v0 at one pre-chosen operating point - SIMULATION DEV (Virtual Elders v4), 2-fold CV by person.
State (5 floats): E10, E60 = EWMA of the tier forecast f20; A30, A120 = EWMA of min(a_std, 0.30 g); D = leaky sum (1/90 per min) of max(0, f20 - 37.9)
Score s = w0 + wL (E60 - 37.5) + wM (E10 - E60) + wB A30 + wS A120 + wD D ; fires when s >= cut for 5 consecutive worn minutes.
Operating point: the cut whose CV strict false-alarm rate is <= 6 per wearer-month. Reports person-bootstrap CIs, subgroup tables,
'Momentum replaces the M13 persistence path' (frozen pd_off binary OR Momentum), and the her-units add-on test."""
import json, os, subprocess, tempfile, numpy as np, pandas as pd, pyarrow.parquet as pq
from sklearn.linear_model import LogisticRegression
from common import *; from rules import *; import feats
from eval3 import ew
from build_cache import csv_for, profile_of, IX
BUDGET = 6.0
VARIANT = os.environ.get("R6_VARIANT", "G0")   # G0 = 5-state score; G3 = G0 armed only with heat context (room air >= 28 C within the last 60 min) = MARBLE DANGER as recommended; G2 = alternative guard (wind clipped at 0.025 g, armed only while E60 >= 37.8 and D > 0)
def pdoff_level(p, hk):
    """frozen freeze-2-equivalent binary (m7_pd_off: no M13 persistence path), same inputs; cached."""
    fn = "%s/cache/pdoff_%s_%d.npy" % (HERE, hk, p)
    if os.path.exists(fn): return np.load(fn)
    f = pq.ParquetFile(SIM + "/minutes_dev_v4.parquet")
    global _RG
    try: _RG
    except NameError: _RG = {int(f.read_row_group(i, columns=["person_id"]).column(0)[0].as_py()): i for i in range(f.metadata.num_row_groups)}
    g = f.read_row_group(_RG[p]).to_pandas().sort_values("t_min"); P_ = PERS.loc[p].to_dict(); prof = profile_of(P_)
    hr = g.HR_meas.values.astype(float)
    if hk == "sc": hr = float(P_["hr_rest"]) + np.random.default_rng(20261112 + p).uniform(0.6, 1.0) * (hr - float(P_["hr_rest"]))
    with tempfile.TemporaryDirectory() as td:
        with open(td + "/i.csv", "w") as fh:
            fh.write("#PROFILE,%r,%r,%r,%d\n#TWIN,70,0.12,0,0.15%s\nmod,...\n" % (prof["age"], prof["sex_m"], prof["bmi"], prof["med_flags"], ",nan" * 24))
            np.savetxt(fh, csv_for(g, hr), fmt="%.7g", delimiter=",")
        subprocess.check_call([ROOT + "/guardian/c/build/m7_pd_off", "replay", td + "/i.csv", td + "/o.csv"])
        lv = pd.read_csv(td + "/o.csv", header=None, usecols=[IX["level"]]).values[:, 0].astype(np.int8)
    np.save(fn, lv); return lv
def per_person(fires, data):
    rows = {}
    for p, fire in fires.items():
        d = data[p]; tc = d["T_core"]; n = len(tc); ev = []
        for (ts, te, day) in events(p, "core385"):
            i = ts - d["t0"]; w = np.where(fire[max(0, i - 45):min(n, i + 11)])[0]
            ev.append((d["types"][day - 1][:2], len(w) > 0, (i - max(0, i - 45) - w[0]) if len(w) else np.nan, int(d["activity_class"][i] >= 4)))
        fa = 0; em = 0; fa1 = 0
        for o in episodes(fire):
            pk = tc[max(0, o - 10):min(n, o + 61)].max(); fa += pk < 38.5; em += pk < 38.2; fa1 += (pk < 38.5) and d["types"][int(d["day"][o]) - 1] == "S1"
        rows[p] = dict(ev=ev, fa=fa, em=em, fa1=fa1, s1=sum(t == "S1" for t in d["types"]))
    return rows
def summ(rows, ids=None, boot=0, seed=1):
    ids = list(rows) if ids is None else ids
    def stat(sel):
        ev = [e for p in sel for e in rows[p]["ev"]]; s2 = [e[1] for e in ev if e[0] == "S2"]; lead = [e[2] for e in ev if e[1]]
        return (np.mean([e[1] for e in ev]) if ev else np.nan, np.mean(s2) if s2 else np.nan, 3.0 * sum(rows[p]["fa"] for p in sel) / len(sel),
                3.0 * sum(rows[p]["em"] for p in sel) / len(sel), len(ev), len(s2), sum(s2), np.median(lead) if lead else np.nan,
                30.0 * sum(rows[p]["fa1"] for p in sel) / max(1, sum(rows[p]["s1"] for p in sel)))
    r = stat(ids); out = dict(sens=r[0], sens_S2=r[1], fa_month=r[2], empty_month=r[3], n=r[4], n_S2=r[5], hit_S2=r[6], lead=r[7], fa_month_S1=r[8],
                              fa_month_median=float(np.median([3.0 * rows[p]["fa"] for p in ids])), persons=len(ids))
    if boot:
        rng = np.random.default_rng(seed); B = np.array([stat(list(rng.choice(ids, len(ids))))[:4] for _ in range(boot)])
        out["ci_sens"] = np.nanpercentile(B[:, 0], [2.5, 97.5]).round(3).tolist(); out["ci_sens_S2"] = np.nanpercentile(B[:, 1], [2.5, 97.5]).round(3).tolist()
        out["ci_fa"] = np.nanpercentile(B[:, 2], [2.5, 97.5]).round(2).tolist()
    return out
def F5(B):
    d, X, ok, y = B; f20 = X["f20"]; a = np.minimum(np.nan_to_num(d["a_std_g"]), 0.30); E60 = ew(f20, 60)
    if VARIANT == "G2": return np.column_stack([E60 - 37.5, ew(f20, 10) - E60, np.clip(ew(a, 30) - ew(a, 120), 0, 0.025), X["dose"]])
    return np.column_stack([E60 - 37.5, ew(f20, 10) - E60, ew(a, 30), ew(a, 120), X["dose"]])
def gate(B_p):
    d, X, ok, y = B_p
    if VARIANT == "G3":                                   # heat context: corrected room air >= 28 C at some minute of the last 60
        hot = np.nan_to_num(X["tair"], nan=0.0) >= 28.0; g = np.zeros(len(hot), bool); c = 10 ** 6
        for i in range(len(hot)): c = 0 if hot[i] else c + 1; g[i] = c <= 60
        return g
    return (ew(X["f20"], 60) >= 37.8) & (X["dose"] > 0)
def cv_scores(P, B, F, folds):
    sc = {}; W = []
    for k, fold in enumerate(folds):
        tr = folds[1 - k]; Xtr = np.concatenate([F[p][B[p][2]][::2] for p in tr]); ytr = np.concatenate([B[p][3][B[p][2]][::2] for p in tr])
        mu, sd = Xtr.mean(0), Xtr.std(0); lr = LogisticRegression(C=1.0, max_iter=800, class_weight="balanced").fit((Xtr - mu) / sd, ytr)
        w = lr.coef_[0] / sd; w0 = lr.intercept_[0] - np.sum(w * mu); W.append(np.r_[w0, w])
        for p in fold:
            s = w0 + F[p] @ w; s[~B[p][2]] = -1e9
            if VARIANT in ("G2", "G3"): s[~gate(B[p])] = -1e9
            sc[p] = s
    return sc, W
def pick(sc, B, data, P, budget):
    allv = np.concatenate([sc[p][B[p][2]] for p in P]); best = None
    for q in 1 - np.logspace(-4.2, -1.6, 40):
        th = np.quantile(allv, q); rows = per_person({p: run_min(sc[p] >= th, 5) for p in P}, data); r = summ(rows)
        if r["fa_month"] <= budget and (best is None or r["sens_S2"] + 0.001 * r["sens"] > best[1]["sens_S2"] + 0.001 * best[1]["sens"]): best = (float(th), r, rows)
    return best
if __name__ == "__main__":
    P = IDX["persons"]; folds = [[p for p in P if p % 2 == 0], [p for p in P if p % 2 == 1]]; out = {}
    meta = json.load(open(ROOT + "/model/cache/v4aug/sim_meta.json")); trained = set(meta["train_ids"]) | set(meta["es_ids"])
    cuts = np.quantile(PERS.loc[P, "kappa_core"], [1 / 3, 2 / 3])
    for hk in ("raw", "sc"):
        B = {p: feats.build(p, hk) for p in P}; data = {p: B[p][0] for p in P}; F = {p: F5(B[p]) for p in P}
        sc, W = cv_scores(P, B, F, folds); th, r, rows = pick(sc, B, data, P, BUDGET); mom = {p: run_min(sc[p] >= th, 5) for p in P}
        Xa = np.concatenate([F[p][B[p][2]][::2] for p in P]); ya = np.concatenate([B[p][3][B[p][2]][::2] for p in P]); mu, sd = Xa.mean(0), Xa.std(0)
        lr = LogisticRegression(C=1.0, max_iter=800, class_weight="balanced").fit((Xa - mu) / sd, ya); wa = lr.coef_[0] / sd; w0a = lr.intercept_[0] - np.sum(wa * mu)
        fz = per_person({p: data[p][hk + "_level"] >= 3 for p in P}, data); off = {p: pdoff_level(p, hk) >= 3 for p in P}
        rep = per_person({p: mom[p] | off[p] for p in P}, data); orr = per_person({p: mom[p] | (data[p][hk + "_level"] >= 3) for p in P}, data)
        print("== %s HR ==  CV weights (%s):" % (hk, VARIANT), np.round(W, 3).tolist(), "| all-DEV:", np.round(np.r_[w0a, wa], 3).tolist(), "| CV cut %.2f" % th)
        def show(nm, rr, boot=400):
            s = summ(rr, boot=boot)
            print("  %-46s ev385 all %.2f [%s]  S2 %d/%d = %.2f [%s]  lead %s | strict FA %.1f/mo [%s] (S1 days %.1f, median wearer %.1f) | empty FA %.1f/mo" % (
                nm, s["sens"], "-".join("%.2f" % x for x in s["ci_sens"]), s["hit_S2"], s["n_S2"], s["sens_S2"], "-".join("%.2f" % x for x in s["ci_sens_S2"]), s["lead"],
                s["fa_month"], "-".join("%.1f" % x for x in s["ci_fa"]), s["fa_month_S1"], s["fa_month_median"], s["empty_month"]), flush=True); return s
        out[hk] = dict(weights_cv=np.round(W, 4).tolist(), weights_all=np.round(np.r_[w0a, wa], 4).tolist(), cut=th,
                       frozen=show("frozen freeze-3 Danger", fz), frozen_no_persistence=show("frozen without M13 persistence (pd_off)", per_person(off, data)),
                       momentum=show("MOMENTUM DANGER alone (<= %g/mo)" % BUDGET, rows), replace=show("Momentum REPLACES M13 persistence (pd_off OR mom)", rep),
                       or_frozen=show("Momentum OR full freeze-3 Danger", orr))
        sub = {"hg2-trained persons": [p for p in P if p in trained], "calibration persons (not trained)": [p for p in P if p not in trained],
               "kappa low": [p for p in P if PERS.loc[p, "kappa_core"] < cuts[0]], "kappa mid": [p for p in P if cuts[0] <= PERS.loc[p, "kappa_core"] < cuts[1]],
               "kappa high": [p for p in P if PERS.loc[p, "kappa_core"] >= cuts[1]], "beta-blocker": [p for p in P if PERS.loc[p, "med_bb_nonsel"] or PERS.loc[p, "med_bb_sel"]],
               "no beta-blocker": [p for p in P if not (PERS.loc[p, "med_bb_nonsel"] or PERS.loc[p, "med_bb_sel"])]}
        out[hk]["subgroups"] = {}
        for nm, ids in sub.items():
            a = summ(rows, ids); b = summ(fz, ids); out[hk]["subgroups"][nm] = dict(momentum=a, frozen=b)
            print("     %-34s n=%3d persons, %3d events: momentum %.2f at %.1f/mo | frozen %.2f at %.1f/mo" % (nm, len(ids), a["n"], a["sens"], a["fa_month"], b["sens"], b["fa_month"]))
        ev = [e for p in P for e in rows[p]["ev"]]; evf = [e for p in P for e in fz[p]["ev"]]
        for nm, k in (("during activity", 1), ("at rest", 0)):
            print("     %-34s %3d events: momentum %.2f | frozen %.2f" % (nm, sum(e[3] == k for e in ev), np.mean([e[1] for e in ev if e[3] == k]), np.mean([e[1] for e in evf if e[3] == k])))
        for c in ("S1", "S2", "PR", "PO"): print("     day class %s: %d events: momentum %.2f | frozen %.2f" % (c, sum(e[0] == c for e in ev), np.mean([e[1] for e in ev if e[0] == c]), np.mean([e[1] for e in evf if e[0] == c])))
        # her-units add-on: + (f20 - her calm), z, thermal exception rT, recovery-failure rec
        F2 = {p: np.column_stack([F[p], B[p][1]["rel"], B[p][1]["z"], B[p][1]["rT"], B[p][1]["rec"]]) for p in P}
        sc2, _ = cv_scores(P, B, F2, folds); th2, r2, rows2 = pick(sc2, B, data, P, BUDGET); out[hk]["plus_her_units"] = show("Momentum + her-units exceptions (<= %g/mo)" % BUDGET, rows2)
        for b in (3.0, 10.0):
            for nm, s_, F_ in (("Momentum", sc, F), ("Momentum + her-units", sc2, F2)):
                t_, r_, _ = pick(s_, B, data, P, b); print("     budget <= %g/mo: %-22s all %.2f S2 %.2f lead %s FA %.1f empty %.1f" % (b, nm, r_["sens"], r_["sens_S2"], r_["lead"], r_["fa_month"], r_["empty_month"]))
                out[hk]["budget_%g_%s" % (b, nm)] = r_
    json.dump(out, open(HERE + "/out_final_danger%s.json" % ("" if VARIANT == "G0" else "_" + VARIANT), "w"), indent=1, default=float)
