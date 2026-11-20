#!/usr/bin/env python3
"""R6 E1b: WHY is her cardiac gain (kappa) not recoverable from the wrist? SIMULATION DEV. Three estimators of bpm per C at REST
(still, worn, daytime, days 1-7): (a) oracle = HR on TRUE core excess (upper bound, not available on the band);
(b) wrist T1 in all rooms; (c) wrist T1 only in hot rooms (air >= 30 C, where the axial drop collapses, R2 1.4);
(d) activity gain bpm per unit motion (chronotropic response to chores) vs the HR scale factor f (sc only)."""
import numpy as np
from scipy.stats import pearsonr, spearmanr
from common import *; import fingerprint as fp
P = IDX["persons"]
for hk in ("raw", "sc"):
    T, a_, b_, c_, g_, nhot, fs, res = [], [], [], [], [], [], [], []
    for p in P:
        d = load(p); hr, A, ta, XH, XT, ok, learn = fp.design(d, hk); pr = PERS.loc[p]
        hf = (pr.bb_hr_factor if (pr.med_bb_nonsel or pr.med_bb_sel) else 1.0) * (0.85 if pr.med_antichol else 1.0); f = 1.0 if hk == "raw" else float(d["hr_fct"])
        m = ok & (d["day"] <= 7) & (A < 0.02) & np.isfinite(hr); amb = np.maximum(0, ta - 22)
        tod = d["minute_of_day"] / 1440 * 2 * np.pi
        def slope(u, mm):
            if mm.sum() < 200: return np.nan
            X = np.column_stack([np.ones(mm.sum()), amb[mm], u[mm]]); return np.linalg.lstsq(X, hr[mm], rcond=None)[0][2]
        circ = pr.circ_mesor - pr.circ_amp * np.cos(tod - 2 * np.pi * pr.circ_nadir_h / 24)
        T.append(f * hf * pr.kappa_core); a_.append(slope(d["T_core"] - circ, m)); b_.append(slope(d["T1"], m)); hot = m & (ta >= 30); c_.append(slope(d["T1"], hot)); nhot.append(hot.sum())
        ma = ok & (d["day"] <= 7) & np.isfinite(hr); g_.append(np.linalg.lstsq(XH[ma], hr[ma], rcond=None)[0][1]); fs.append(f); res.append(pr.reserve_factor)
    T = np.array(T); print("== %s HR, truth = f*heat_fac*kappa_core, n = %d" % (hk, len(P)))
    for nm, e in (("(a) oracle true-core excess", a_), ("(b) wrist T1, all rooms", b_), ("(c) wrist T1, air >= 30 C", c_)):
        e = np.array(e); k = np.isfinite(e); print("  %-28s n=%3d pearson %.2f spearman %.2f median est %.1f (truth %.1f)" % (nm, k.sum(), pearsonr(e[k], T[k])[0], spearmanr(e[k], T[k])[0], np.median(e[k]), np.median(T[k])))
    g_ = np.array(g_)
    print("  (d) activity gain vs reserve_factor*f: pearson %.2f | vs f alone: %.2f | vs truth kappa_eff: %.2f" % (pearsonr(g_, np.array(res) * np.array(fs))[0], pearsonr(g_, fs)[0] if hk == "sc" else np.nan, pearsonr(g_, T)[0]))
