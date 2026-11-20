#!/usr/bin/env python3
"""R6 E4b ablation: which few states does the Motion Danger score need? SIMULATION DEV, 2-fold CV by person, strict FA budgets."""
import json, sys, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from common import *; from rules import *; import feats
from eval3 import ew, score2
def allfeats(B):
    d, X, ok, y = B; f20 = X["f20"]; a = np.minimum(np.nan_to_num(d["a_std_g"]), 0.30)
    return dict(E60=ew(f20, 60) - 37.5, M10=ew(f20, 10) - ew(f20, 60), A30=ew(a, 30), A120=ew(a, 120), dose=X["dose"], f20=f20 - 37.5, mom15=X["mom15"], mom45=X["mom45"],
                W60=X["W60"], W180=X["W180"], E30=ew(f20, 30) - 37.5, A60=ew(a, 60), A180=ew(a, 180), env=X["env"], v12=X["v12"] - 37.5)
SETS = {"a E60,M10,A30,A120": ["E60", "M10", "A30", "A120"], "b a+dose": ["E60", "M10", "A30", "A120", "dose"], "c b+f20": ["E60", "M10", "A30", "A120", "dose", "f20"],
        "d E60,mom45,mom15,W60,W180,dose,f20 (=M1)": ["E60", "mom45", "mom15", "W60", "W180", "dose", "f20"], "e E60,M10,W60,W180": ["E60", "M10", "W60", "W180"],
        "f E60,M10,W60,W180,dose,f20": ["E60", "M10", "W60", "W180", "dose", "f20"], "g f + v12, env (mass)": ["E60", "M10", "W60", "W180", "dose", "f20", "v12", "env"],
        "h level only: E60": ["E60"], "i level+momentum: E60,M10,dose,f20": ["E60", "M10", "dose", "f20"]}
if __name__ == "__main__":
    P = IDX["persons"]; folds = [[p for p in P if p % 2 == 0], [p for p in P if p % 2 == 1]]; out = {}
    for hk in ("raw", "sc"):
        B = {p: feats.build(p, hk) for p in P}; data = {p: B[p][0] for p in P}; AF = {p: allfeats(B[p]) for p in P}
        print("== %s HR ==" % hk, flush=True)
        for name, cols in SETS.items():
            scores = {}
            for k, fold in enumerate(folds):
                tr = folds[1 - k]; Xtr = np.concatenate([np.column_stack([AF[p][c] for c in cols])[B[p][2]][::2] for p in tr]); ytr = np.concatenate([B[p][3][B[p][2]][::2] for p in tr])
                sc = StandardScaler().fit(Xtr); lr = LogisticRegression(C=1.0, max_iter=500, class_weight="balanced").fit(sc.transform(Xtr), ytr)
                for p in fold: s = lr.decision_function(sc.transform(np.column_stack([AF[p][c] for c in cols]))); s[~B[p][2]] = -1e9; scores[p] = s
            allv = np.concatenate([scores[p][B[p][2]] for p in P]); rows = []
            for q in 1 - np.logspace(-4.2, -1.6, 20):
                th = np.quantile(allv, q); rows.append(score2({p: run_min(scores[p] >= th, 5) for p in P}, data))
            line = " %-44s" % name; out["%s|%s" % (hk, name)] = {}
            for b in (3.0, 6.0, 10.0):
                c = [r for r in rows if r["fa_month"] <= b]; r = max(c, key=lambda r: r["sens_S2"] + 0.001 * r["sens"]) if c else None
                line += " | <=%g: all %.2f S2 %.2f lead %2.0f fa %.1f empty %.1f" % (b, r["sens"], r["sens_S2"], r["lead"], r["fa_month"], r["empty_month"]) if r else " | <=%g: -" % b
                out["%s|%s" % (hk, name)][str(b)] = r
            print(line, flush=True)
    json.dump(out, open(HERE + "/out_eval3b.json", "w"), indent=1)
