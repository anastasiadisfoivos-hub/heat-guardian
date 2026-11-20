#!/usr/bin/env python3
"""R6 E3: which Talzin ingredients add information on top of the frozen NN forecast?  SIMULATION DEV, 2-fold CV by person.
Logistic score on feature groups -> event-level frontier (rules.score) at fixed false-alarm budgets, strict and 'empty' definitions."""
import sys, numpy as np, json
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from common import *; from rules import *; import feats
GROUPS = {"M0 f20 only": ["f20"],
          "M1 +momentum/long memory": ["f20", "mom15", "mom45", "ew60", "dose", "W60", "W180"],
          "M2 +mass (HR-only path, env, air)": ["f20", "mom15", "mom45", "ew60", "dose", "W60", "W180", "v12", "v12z", "agree", "env", "tair"],
          "M3 +her-units exceptions": ["f20", "mom15", "mom45", "ew60", "dose", "W60", "W180", "v12", "v12z", "agree", "env", "tair", "rel", "z", "dose_her", "expo", "rT", "rH", "rec"],
          "M4 her-units only (no absolute f20)": ["rel", "z", "dose_her", "expo", "rT", "rH", "rec", "mom15", "mom45", "W60", "W180"]}
def frontier(scores, data, budgets=(3.0, 6.0, 12.0), k=5):
    allv = np.concatenate([s[np.isfinite(s)] for s in scores.values()]); out = {}
    qs = np.quantile(allv, 1 - np.logspace(-4.3, -1.3, 28)); res = []
    for th in qs:
        r = score({p: run_min(scores[p] >= th, k) for p in scores}, data); res.append((th, r))
    for b in budgets:
        ok = [(r["sens"], r["sens_S2"], r["lead"], r["fa_month"], th) for th, r in res if r["fa_month"] <= b]
        out[b] = max(ok) if ok else None
    return out, res
if __name__ == "__main__":
    P = IDX["persons"]; folds = [[p for p in P if p % 2 == 0], [p for p in P if p % 2 == 1]]; out = {}
    for hk in ("raw", "sc"):
        B = {p: feats.build(p, hk) for p in P}; data = {p: B[p][0] for p in P}
        print("== %s HR ==" % hk, flush=True)
        for name, cols in GROUPS.items():
            scores = {}; coefs = []
            for k, fold in enumerate(folds):
                tr = folds[1 - k]
                Xtr = np.concatenate([np.column_stack([B[p][1][c] for c in cols])[B[p][2]][::3] for p in tr]); ytr = np.concatenate([B[p][3][B[p][2]][::3] for p in tr])
                sc = StandardScaler().fit(Xtr); lr = LogisticRegression(C=1.0, max_iter=300, class_weight="balanced").fit(sc.transform(Xtr), ytr); coefs.append(lr.coef_[0])
                for p in fold:
                    X = np.column_stack([B[p][1][c] for c in cols]); s = lr.decision_function(sc.transform(X)); s[~B[p][2]] = -1e9; scores[p] = s
            fr, res = frontier(scores, data)
            ys = np.concatenate([B[p][3][B[p][2]] for p in P]); ss = np.concatenate([scores[p][B[p][2]] for p in P])
            r = np.argsort(np.argsort(ss)) + 1.0; n1 = ys.sum(); auc = (r[ys == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * (len(ys) - n1))
            print(" %-36s AUC %.3f | " % (name, auc) + " | ".join("<=%g/mo: sens %.2f (S2 %.2f) lead %s fa %.1f" % (b, v[0], v[1], v[2], v[3]) if v else "<=%g/mo: -" % b for b, v in fr.items()), flush=True)
            out["%s|%s" % (hk, name)] = dict(auc=float(auc), frontier={str(b): (list(map(float, v[:4])) if v else None) for b, v in fr.items()},
                                             coef=dict(zip(cols, map(float, np.mean(coefs, 0)))))
    json.dump(out, open(HERE + "/out_eval2.json", "w"), indent=1)
