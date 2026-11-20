#!/usr/bin/env python3
"""R6 E7: does 'mass, not line' also help on REAL data?  HTT dev sessions (52 young adults walking in a hot chamber, HR only; DEV, not sealed).
The frozen freeze-3 binary is replayed (read-only) for its per-minute v1.2 forecast, v1.2 Danger logit z and its own Danger tier.
Marble-lite on the HR-only path (no skin/air/motion in HTT, so no 'wind' term):  E60, E10-E60 of v1.2 f20, D = leaky sum of max(0, f20-37.9),
optionally EWMA10 of z. Logistic score, 2-fold CV BY SUBJECT, 5-min persistence; threshold = the largest sensitivity with false alarms/h <= the
frozen Danger tier's own rate. Scoring = hgmodel/common.event_detection (same as guardian/tests/eval_htt.py)."""
import json, os, sys, tempfile
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
ROOT = "/home/claude/hg_ai"; HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT + "/guardian/py"); sys.path.insert(0, "/home/claude/hgmodel")
import run_traces, trace_io, common
trace_io.HOST = ROOT + "/guardian/c/build/m7_pd_20"
def ew(x, tau):
    y = np.empty(len(x)); s = x[0]; a = 1.0 / tau
    for i in range(len(x)): s += a * (x[i] - s); y[i] = s
    return y
def leaky(x, tau):
    y = np.empty(len(x)); s = 0.0
    for i in range(len(x)): s = s * (1 - 1.0 / tau) + x[i]; y[i] = s
    return y
def runmin(c, k):
    r = np.zeros(len(c), bool); s = 0
    for i in range(len(c)): s = s + 1 if c[i] else 0; r[i] = s >= k
    return r
sess = run_traces.htt_sessions(); raw = {f"{s['subject']}_s{s['session']}": s for s in common.load_htt()[0]}; S = []
with tempfile.TemporaryDirectory() as d:
    for name, prof, tw, mins in sess:
        trace_io.write_csv(d + "/i.csv", mins, prof, tw); c = trace_io.run_c(d + "/i.csv", d + "/o.csv"); s = raw[name]
        f20 = np.array([r["v12_f20"] for r in c], float); z = np.array([r["v12_z"] for r in c], float); f20 = np.where(np.isfinite(f20), f20, 37.0); z = np.where(np.isfinite(z), z, -6.0)
        core = np.asarray(s["core"], float); n = len(core); fut = np.full(n, -np.inf)
        for k in range(1, 31): fut[:n - k] = np.fmax(fut[:n - k], core[k:])
        E60 = ew(f20, 60); X = np.column_stack([E60 - 37.5, ew(f20, 10) - E60, leaky(np.maximum(0, f20 - 37.9), 90), ew(z, 10), f20 - 37.5])
        S.append(dict(subject=s["subject"], session=s["session"], core=core, X=X, y=(fut >= 38.5).astype(int), danger=np.array([r["level"] >= 3 for r in c])))
subs = sorted(set(s["subject"] for s in S)); folds = [set(subs[::2]), set(subs[1::2])]
def detect(mask_of):
    df = pd.concat([pd.DataFrame(dict(subject=s["subject"], session=s["session"], core=s["core"], m=mask_of(s))) for s in S], ignore_index=True)
    r = common.event_detection(df, None, 38.5, None, mask_col="m"); return float(r["sensitivity"]), float(r["false_alarms_per_h"]), float(r["median_lead_min"]) if r["median_lead_min"] == r["median_lead_min"] else np.nan, int(r["events"]), int(r["detected"])
fz = detect(lambda s: s["danger"]); out = dict(frozen=fz, label="REAL young adults, HTT dev (104 sessions), HR-only; DEV")
print("frozen Danger tier on HTT dev: %d/%d = %.1f %% at %.3f FA/h, lead %s" % (fz[4], fz[3], fz[0], fz[1], fz[2]))
for name, cols in (("marble-lite [E60, E10-E60, D]", [0, 1, 2]), ("marble-lite + smoothed z", [0, 1, 2, 3]), ("line only: f20", [4]), ("z only (EWMA10)", [3])):
    for s in S:
        tr = [t for t in S if (t["subject"] in folds[0]) != (s["subject"] in folds[0])]
    sc = {}
    for k in (0, 1):
        tr = [t for t in S if t["subject"] not in folds[k]]; Xtr = np.concatenate([t["X"][:, cols] for t in tr]); ytr = np.concatenate([t["y"] for t in tr])
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9; lr = LogisticRegression(C=1.0, max_iter=500, class_weight="balanced").fit((Xtr - mu) / sd, ytr)
        for i, t in enumerate(S):
            if t["subject"] in folds[k]: sc[i] = lr.decision_function((t["X"][:, cols] - mu) / sd)
    allv = np.concatenate([sc[i] for i in range(len(S))]); best = None; curve = []
    for q in np.linspace(0.70, 0.995, 40):
        th = np.quantile(allv, q); idx = {id(s): i for i, s in enumerate(S)}
        r = detect(lambda s: runmin(sc[idx[id(s)]] >= th, 5)); curve.append((float(q), *r))
        if r[1] <= fz[1] + 1e-9 and (best is None or r[0] > best[0]): best = r
    b15 = max([c[1:] for c in curve if c[2] <= 0.05 + 1e-9], default=None)
    print("%-32s at <= frozen FA/h: %s | at <= 0.05 FA/h: %s" % (name, "%d/%d = %.1f %% at %.3f/h lead %s" % (best[4], best[3], best[0], best[1], best[2]) if best else "-",
                                                               "%.1f %% at %.3f/h" % (b15[0], b15[1]) if b15 else "-"))
    out[name] = dict(at_frozen_fa=best, at_005=b15, curve=curve)
json.dump(out, open(HERE + "/out_htt_marble.json", "w"), indent=1)
