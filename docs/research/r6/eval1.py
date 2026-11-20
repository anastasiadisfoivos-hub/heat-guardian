#!/usr/bin/env python3
"""R6 E1/E2 - SIMULATION DEV. E1: is her gain G (bpm per C) recoverable?  E2: do her-units exceptions separate ev385 minutes?"""
import sys, numpy as np
from common import *
from scipy.stats import spearmanr, pearsonr
def auc(s, y):
    m = np.isfinite(s); s = s[m]; y = y[m]
    if y.sum() == 0 or y.sum() == len(y): return np.nan
    r = np.argsort(np.argsort(s)) + 1.0; n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
def fut_max(x, h=30):
    n = len(x); out = np.full(n, -np.inf)
    for k in range(1, h + 1): out[:n - k] = np.maximum(out[:n - k], x[k:])
    return out
if __name__ == "__main__":
    P = IDX["persons"]
    for hk in ("raw", "sc"):
        Gs, Gt, S = [], [], {k: [] for k in ("y", "rT", "rH", "rHc", "fuse", "minz", "nn20", "v12z", "l385", "kap", "day", "pid", "relnn")}
        for p in P:
            d = load(p); f = dict(np.load("%s/cache/fp_%s_%d.npz" % (HERE, hk, p)))
            pr = PERS.loc[p]; hf = (pr.bb_hr_factor if (pr.med_bb_nonsel or pr.med_bb_sel) else 1.0) * (0.85 if pr.med_antichol else 1.0)
            fct = 1.0 if hk == "raw" else float(d["hr_fct"])
            Gt.append(fct * hf * pr.kappa_core); Gs.append([f["coefs"][k][7] for k in (3, 5, 7, 9)])   # G used on day 4, 6, 8, 10
            ok = f["ok"] & (d["day"] >= 3)
            y = (fut_max(d["T_core"]) >= 38.5).astype(int)
            G = np.clip(f["G"], 5, 40); rHc = f["rH"] / G
            # personal-relative NN: NN f20 minus her own median f20 of previous days' ok & level 0 minutes
            nn = d[hk + "_core_20"].astype(float); rel = np.full(len(nn), np.nan)
            for day in range(2, 11):
                m0 = (d["day"] < day) & f["ok"] & (d[hk + "_level"] == 0) & (f["A"] < 0.02)
                if m0.sum() > 60: rel[d["day"] == day] = nn[d["day"] == day] - np.nanmedian(nn[m0])
            for k, v in (("y", y), ("rT", f["rT"]), ("rH", f["rH"]), ("rHc", rHc), ("fuse", 0.5 * (f["rT"] + rHc)), ("minz", np.minimum(f["rT"] / f["sT"], f["rH"] / f["sH"])),
                         ("nn20", nn), ("v12z", d[hk + "_v12_z"].astype(float)), ("l385", d[hk + "_logit_p385"].astype(float)),
                         ("kap", np.full(len(y), pr.kappa_core)), ("day", d["day"]), ("pid", np.full(len(y), p)), ("relnn", rel)):
                S[k].append(np.asarray(v)[ok])
        S = {k: np.concatenate(v) for k, v in S.items()}; Gs = np.array(Gs); Gt = np.array(Gt)
        print("== %s HR ==  E1 gain recovery (truth = f * heat_fac * kappa_core; n=%d persons)" % (hk, len(P)))
        for j, dd in enumerate((3, 5, 7, 9)):
            print("   after %d days: pearson %.2f spearman %.2f  median est %.1f vs truth %.1f  MAE %.1f bpm/C" % (dd, pearsonr(Gs[:, j], Gt)[0], spearmanr(Gs[:, j], Gt)[0], np.median(Gs[:, j]), np.median(Gt), np.mean(np.abs(Gs[:, j] - Gt))))
        y = S["y"]; print("   E2 minute AUC for 'core >= 38.5 within 30 min' (%d positive of %d minutes, %d persons)" % (y.sum(), len(y), len(set(S["pid"][y == 1]))))
        cuts = np.quantile(PERS.loc[P, "kappa_core"], [1 / 3, 2 / 3])
        for k in ("nn20", "relnn", "l385", "v12z", "rT", "rH", "rHc", "fuse", "minz"):
            a = [auc(S[k], y)] + [auc(S[k][g], y[g]) for g in (S["kap"] < cuts[0], (S["kap"] >= cuts[0]) & (S["kap"] < cuts[1]), S["kap"] >= cuts[1])]
            # sensitivity at the threshold giving 1 % of negative minutes above it
            thr = np.nanquantile(S[k][y == 0], 0.99); se = np.nanmean(S[k][y == 1] >= thr)
            print("     %-6s AUC all %.3f | kappa low %.3f mid %.3f high %.3f | minute-sens at 1%% FPR %.2f" % (k, *a, se))
