#!/usr/bin/env python3
"""R6 E4: the on-chip 'Motion Danger' score (4 EWMA states, one dot product) - SIMULATION DEV, 2-fold CV by person.
  E10, E60 = EWMA(10 / 60 min) of the frozen tier forecast f20;  A30, A120 = EWMA(30 / 120 min) of min(a_std, 0.30 g)
  s = w0 + wL*(E60-37.5) + wM*(E10-E60) + wB*A30 + wS*A120        Danger_M when s >= cut for 5 consecutive worn minutes
Compared with the frozen Danger tier and with OR(frozen, new); false alarms strict (< 38.5 C) and 'empty' (peak < 38.2 C)."""
import json, numpy as np
from sklearn.linear_model import LogisticRegression
from common import *; from rules import *; import feats
def ew(x, tau):
    y = np.empty(len(x)); s = x[0]; a = 1.0 / tau
    for i in range(len(x)): s += a * (x[i] - s); y[i] = s
    return y
def score2(fires, data):
    """adds the 'empty' false-alarm rate (peak core < 38.2 within [onset-10, onset+60]) to rules.score"""
    r = score(fires, data); e = 0; nd = 0
    for pid, fire in fires.items():
        tc = data[pid]["T_core"]; n = len(tc); nd += 10
        for o in episodes(fire): e += tc[max(0, o - 10):min(n, o + 61)].max() < 38.2
    r["empty_month"] = 30.0 * e / nd; return r
def feat4(B):
    d, X, ok, y = B; f20 = X["f20"]; a = np.minimum(np.nan_to_num(d["a_std_g"]), 0.30)
    E10, E60 = ew(f20, 10), ew(f20, 60)
    return np.column_stack([E60 - 37.5, E10 - E60, ew(a, 30), ew(a, 120)])
if __name__ == "__main__":
    P = IDX["persons"]; folds = [[p for p in P if p % 2 == 0], [p for p in P if p % 2 == 1]]; out = {}
    for hk in ("raw", "sc"):
        B = {p: feats.build(p, hk) for p in P}; data = {p: B[p][0] for p in P}; F = {p: feat4(B[p]) for p in P}
        frozen = {p: data[p][hk + "_level"] >= 3 for p in P}
        scores = {}; W = []
        for k, fold in enumerate(folds):
            tr = folds[1 - k]; Xtr = np.concatenate([F[p][B[p][2]][::2] for p in tr]); ytr = np.concatenate([B[p][3][B[p][2]][::2] for p in tr])
            lr = LogisticRegression(C=10.0, max_iter=500, class_weight="balanced").fit(Xtr, ytr); W.append(np.r_[lr.intercept_, lr.coef_[0]])
            for p in fold: s = lr.intercept_[0] + F[p] @ lr.coef_[0]; s[~B[p][2]] = -1e9; scores[p] = s
        Xa = np.concatenate([F[p][B[p][2]][::2] for p in P]); ya = np.concatenate([B[p][3][B[p][2]][::2] for p in P])
        lra = LogisticRegression(C=10.0, max_iter=500, class_weight="balanced").fit(Xa, ya)
        print("== %s HR ==  fold weights [w0, wL, wM, wB, wS]:" % hk, np.round(W, 2).tolist(), " all-DEV:", np.round(np.r_[lra.intercept_, lra.coef_[0]], 2).tolist())
        r = score2(frozen, data); print("  frozen Danger (freeze-3)        sens %.2f S2 %.2f lead %s | strict FA %.1f/mo (S1 %.1f) | empty FA %.1f/mo" % (r["sens"], r["sens_S2"], r["lead"], r["fa_month"], r["fa_month_S1"], r["empty_month"]))
        allv = np.concatenate([scores[p][B[p][2]] for p in P]); rows = []
        for q in 1 - np.logspace(-4.2, -1.5, 22):
            th = np.quantile(allv, q); new = {p: run_min(scores[p] >= th, 5) for p in P}
            r1 = score2(new, data); r2 = score2({p: new[p] | frozen[p] for p in P}, data); rows.append((float(th), r1, r2))
        for b in (2.0, 4.0, 6.0, 8.0, 15.0):
            c = [x for x in rows if x[1]["fa_month"] <= b]
            if c:
                th, r1, r2 = max(c, key=lambda x: x[1]["sens_S2"] + 0.001 * x[1]["sens"])
                print("  Motion Danger, strict FA <= %-4g  sens %.2f S2 %.2f (n=%d/%d) lead %s | strict FA %.1f/mo (S1 %.1f, median wearer %.1f) | empty FA %.1f/mo | cut %.2f || OR frozen: S2 %.2f FA %.1f" % (
                    b, r1["sens"], r1["sens_S2"], r1["n"], r1["n_S2"], r1["lead"], r1["fa_month"], r1["fa_month_S1"], r1["fa_month_median"], r1["empty_month"], th, r2["sens_S2"], r2["fa_month"]))
        out[hk] = dict(weights_cv=np.round(W, 4).tolist(), weights_all=np.round(np.r_[lra.intercept_, lra.coef_[0]], 4).tolist(),
                       rows=[(th, {k: v for k, v in r1.items()}) for th, r1, _ in rows])
        # kappa-tercile and class breakdown at the <= 6/mo point
        c = [x for x in rows if x[1]["fa_month"] <= 6.0]; th = max(c, key=lambda x: x[1]["sens_S2"])[0]
        cuts = np.quantile(PERS.loc[P, "kappa_core"], [1 / 3, 2 / 3]); grp = {"k_low": [], "k_mid": [], "k_high": []}; cls = {}
        for p in P:
            fire = run_min(scores[p] >= th, 5); d = data[p]; kk = PERS.loc[p, "kappa_core"]; g = "k_low" if kk < cuts[0] else "k_mid" if kk < cuts[1] else "k_high"
            for (ts, te, day) in events(p, "core385"):
                i = ts - d["t0"]; hit = bool(fire[max(0, i - 45):i + 11].any()); grp[g].append(hit); cls.setdefault(d["types"][day - 1][:2], []).append(hit)
                cls.setdefault("act>=4" if d["activity_class"][i] >= 4 else "rest", []).append(hit)
        print("   at <=6/mo:", {k: "%d/%d" % (sum(v), len(v)) for k, v in {**grp, **cls}.items()})
    json.dump(out, open(HERE + "/out_eval3.json", "w"), indent=1)
