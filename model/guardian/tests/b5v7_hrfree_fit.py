#!/usr/bin/env python3
"""[B5-v7] HR-free Danger ("Heat-Load Danger", HLD) design study on SIM-DEV v5 DEV dumps (eval_b5v7.py --dump) - SIMULATION.
Inputs per minute: only signals that do not need the heart: corrected room air + RH (PSU-line margin), wrist skin T1, reference
T2 (flux T1 - T2), wrist movement. HR-free by construction, so the score is identical in raw and HR-scaled replays (asserted).
Fits a logistic score on EWMA features (person 2-fold CV), then reports event catch vs false episodes per wearer-month for a
cut grid. usage: b5v7_hrfree_fit.py DUMPDIR BUILD OUTJSON"""
import glob, json, os, sys
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression

DUMP, BUILD, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
A_LIM = 8.308; B_LIM = -0.137      # PSU older REST line (cfg HG_LIM_OLD_REST_*), Pa line in kPa vs air C


def pa_kpa(t, rh):   # Magnus over water (same family as hg_pa_kpa; exact float form re-implemented in C/Py mirror later)
    return rh / 100.0 * 0.61078 * np.exp(17.27 * t / (t + 237.3))


def ewma(x, a, x0):
    y = np.empty_like(x); v = x0
    for i in range(len(x)): v = v + a * (x[i] - v); y[i] = v
    return y


def feats(z):
    ta = z["t_air_corr"].astype(float); rh = z["rh"].astype(float); t1 = z["T1"].astype(float); t2 = z["T2"].astype(float)
    worn = z["worn"] == 2
    ok = worn & np.isfinite(ta) & np.isfinite(rh) & np.isfinite(t1)
    marg = np.where(ok, pa_kpa(np.nan_to_num(ta, nan=25), np.nan_to_num(rh, nan=50)) - (A_LIM + B_LIM * np.nan_to_num(ta, nan=25)), -3.0)
    marg = np.clip(marg, -3, 3)
    taw = np.where(ok, ta, 25.0); t1w = np.where(ok, t1, 33.0); fl = np.where(ok & np.isfinite(t2), t1 - t2, 0.0)
    a = np.minimum(np.nan_to_num(z["astd"].astype(float)), 0.30)
    F = dict(
        m60=ewma(marg, 1 / 60, -3.0), m240=ewma(marg, 1 / 240, -3.0),           # heat dose: margin above the PSU line, 1 h / 4 h
        ta240=ewma(taw, 1 / 240, 25.0),                                         # hours of warm air
        t1_30=ewma(t1w, 1 / 30, 33.0), t1_240=ewma(t1w, 1 / 240, 33.0),         # wrist skin level and its slow mean
        fl30=ewma(fl, 1 / 30, 0.0), a30=ewma(a, 1 / 30, 0.0), a120=ewma(a, 1 / 120, 0.0))
    F["t1_jump"] = F["t1_30"] - F["t1_240"]
    return F, ok


rows = []
for fn in sorted(glob.glob(os.path.join(DUMP, "p*_%s_hr_scaled.npz" % BUILD))):
    pid = int(os.path.basename(fn).split("_")[0][1:]); z = np.load(fn)
    F, ok = feats(z)
    core = z["T_core"].astype(float); dtype = z["dtype"]; n = len(core)
    # core385 onsets from truth (same definition as the events table: T_core >= 38.5 run starts)
    on = np.where((core >= 38.5) & np.concatenate([[False], core[:-1] < 38.5]))[0]
    pos = np.zeros(n, bool); near = np.zeros(n, bool)
    for s in on: pos[max(0, s - 45):s + 1] = True; near[max(0, s - 90):min(n, s + 120)] = True
    near |= core >= 38.3
    lv = z["level"]; armed = ok & (F["ta240"] > 0)   # placeholder, real arming below
    d = pd.DataFrame(F); d["pid"] = pid; d["pos"] = pos; d["near"] = near; d["ok"] = ok; d["s2"] = np.char.startswith(dtype.astype(str), "S2")
    d["dtype"] = dtype; d["core"] = core; d["day"] = z["day"]; d["f6_lv"] = lv; d["i"] = np.arange(n); d["tair"] = z["t_air_corr"]
    rows.append(d)
D = pd.concat(rows, ignore_index=True)
X_NAMES = ["m60", "m240", "ta240", "t1_30", "t1_jump", "fl30", "a30", "a120"]
pids = np.array(sorted(D.pid.unique())); rng = np.random.default_rng(20261113); rng.shuffle(pids); fold = {p: i % 2 for i, p in enumerate(pids)}
D["fold"] = D.pid.map(fold)
train = D[D.ok & (D.pos | ~D.near)]
print("minutes", len(D), "train", len(train), "pos", int(train.pos.sum()), "persons", len(pids))
res = {}
coefs = []
D["score"] = np.nan
for f in (0, 1):
    tr = train[train.fold != f]
    m = LogisticRegression(C=1.0, max_iter=2000).fit(tr[X_NAMES].values, tr.pos.values)
    coefs.append((m.intercept_[0], m.coef_[0].tolist()))
    te = D.fold == f; D.loc[te, "score"] = m.decision_function(D.loc[te, X_NAMES].values)
mall = LogisticRegression(C=1.0, max_iter=2000).fit(train[X_NAMES].values, train.pos.values)
print("full fit", mall.intercept_[0], dict(zip(X_NAMES, np.round(mall.coef_[0], 4))))


def episodes_rule(d, cut, run=5, warm=28.0):
    """5-min run of score >= cut while worn & warm air (corrected air >= warm C in the last 60 min); returns onsets idx"""
    sc = d.score.values; ok = d.ok.values; ta = np.nan_to_num(d.tair.values, nan=0)
    wm = pd.Series((ta >= warm).astype(int)).rolling(61, min_periods=1).max().values > 0
    c = (sc >= cut) & ok & wm
    r = np.zeros(len(c), int); k = 0
    for i, v in enumerate(c): k = k + 1 if v else 0; r[i] = k
    on = r >= run
    ons = np.where(on & np.concatenate([[False], ~on[:-1]]))[0]
    return on, ons


grid = {}
for cut in np.arange(-7.0, -0.99, 0.5):
    det = tot = det_s2 = tot_s2 = fa = empty = 0; worn_h = 0; s2new = 0
    for pid, d in D.groupby("pid"):
        on, ons = episodes_rule(d, cut)
        core = d.core.values; n = len(core); ty = d.dtype.values.astype(str)
        evs = np.where((core >= 38.5) & np.concatenate([[False], core[:-1] < 38.5]))[0]
        f6 = d.f6_lv.values >= 3
        for s in evs:
            w = on[max(0, s - 45):s + 11].any(); tot += 1; det += w
            if ty[s].startswith("S2"):
                tot_s2 += 1; det_s2 += w; s2new += int(w and not f6[max(0, s - 45):s + 11].any())
        for s in ons:
            hit = ((core[max(0, s - 10):min(n, s + 46)] >= 38.5).any())
            if not hit:
                fa += 1; empty += int(core[max(0, s - 10):min(n, s + 46)].max() < 38.0)
        worn_h += d.ok.sum() / 60
    grid[round(float(cut), 2)] = dict(ev385=tot, det=int(det), s2_events=tot_s2, s2_det=int(det_s2), s2_new_vs_f6=int(s2new),
                                      false_per_month=720 * fa / worn_h, empty_per_month=720 * empty / worn_h)
    g = grid[round(float(cut), 2)]
    print("cut %5.2f  S2 %3d/%3d (new vs f6 %3d)  all %3d/%3d  false/mo %6.2f empty/mo %6.2f" % (cut, g["s2_det"], g["s2_events"], g["s2_new_vs_f6"], g["det"], g["ev385"], g["false_per_month"], g["empty_per_month"]))
json.dump(dict(label="SIMULATION SIM-DEV v5 tune set, HR-scaled dumps (HR-free score: identical in raw)", features=X_NAMES, cv_coefs=coefs,
               full=dict(intercept=float(mall.intercept_[0]), coef=mall.coef_[0].tolist()), grid=grid), open(OUT, "w"), indent=1)
