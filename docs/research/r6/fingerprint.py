#!/usr/bin/env python3
"""R6 feasibility: personal heat-response fingerprint from everyday natural experiments. SIMULATION, DEV ONLY (Virtual Elders v4).
Band-observable inputs only: T1, HR (raw or M3.2-scaled), a_std, frozen corrected room air, frozen worn/level.
NIGHTLY fit (Body-Twin slot), applied the NEXT day with fixed coefficients (causal):
  load  A_t  = EWMA_4min(min(a_std, 0.30))                       'how hard she is moving'
  amb_t = max(0, T_air_corr - 22)
  HR  ~ b0 + b1*A + b2*amb        T1 ~ c0 + c1*T_air_corr + c2*A   (day window 08-22, worn, no alarm tier on, 30 min after donning)
  rH = HR - fit, rT = T1 - fit;   G = sum(rH*rT)/sum(rT*rT) on still minutes  (bpm per C of her own wrist-thermal departure)
Sufficient statistics decay by LAM per day; ridge prior = population coefficients with weight N0 minutes (2-fold over persons).
Output per person/HR variant: per-minute rH, rT, G_day, sH, sT -> cache/fp_<pid>.npz"""
import sys, numpy as np
from common import *
LAM, N0, DAY0, DAY1 = 0.85, 240.0, 480, 1320

def ewma(x, tau):
    y = np.empty_like(x); a = 1.0 / tau; s = x[0]
    for i in range(len(x)): s += a * (x[i] - s); y[i] = s
    return y

def design(d, hk):
    hr = d["HR_meas"] if hk == "raw" else d["hr_scaled"]
    A = ewma(np.minimum(np.nan_to_num(d["a_std_g"]), 0.30), 4.0)
    ta = d[hk + "_t_air_corr"].astype(float); ta = np.where(np.isfinite(ta), ta, d["T_air_meas"])
    amb = np.maximum(0.0, ta - 22.0)
    worn = d[hk + "_worn"] == 2; lvl = d[hk + "_level"]
    don = np.zeros(len(worn), int); c = 0
    for i in range(len(worn)): c = c + 1 if worn[i] else 0; don[i] = c
    mod = d["minute_of_day"]
    ok = worn & (don >= 30) & (mod >= DAY0) & (mod < DAY1) & np.isfinite(d["T1"])
    learn = ok & (lvl == 0)
    XH = np.column_stack([np.ones(len(A)), A, amb]); XT = np.column_stack([np.ones(len(A)), ta, A])
    return hr, A, ta, XH, XT, ok, learn

def day_stats(d, hk):
    hr, A, ta, XH, XT, ok, learn = design(d, hk); out = {}
    for day in range(1, 11):
        m = learn & (d["day"] == day); mh = m & np.isfinite(hr)
        out[day] = (XH[mh].T @ XH[mh], XH[mh].T @ hr[mh], float(mh.sum()), XT[m].T @ XT[m], XT[m].T @ d["T1"][m], float(m.sum()))
    return out

def fit_person(d, hk, prior):
    """prior = (bH, bT, G0). Returns per-minute residuals using coefficients fitted on PREVIOUS days only."""
    hr, A, ta, XH, XT, ok, learn = design(d, hk); n = len(hr)
    rH = np.full(n, np.nan); rT = np.full(n, np.nan); Gd = np.full(n, np.nan); sH = np.full(n, np.nan); sT = np.full(n, np.nan)
    SH = np.zeros((3, 3)); sH_y = np.zeros(3); ST = np.zeros((3, 3)); sT_y = np.zeros(3); g_num = 0.0; g_den = 0.0; nH = 0.0
    aH = 4.0; aT = 0.15; coefs = []
    bH0, bT0, G0 = prior
    for day in range(1, 11):
        # coefficients from stats of days < day, shrunk to the population prior (N0 pseudo-minutes spread on the diagonal scale)
        RH = N0 * np.diag([1.0, 0.01, 25.0]); RT = N0 * np.diag([1.0, 900.0, 0.01])
        bH = np.linalg.solve(SH + RH, sH_y + RH @ bH0); bT = np.linalg.solve(ST + RT, sT_y + RT @ bT0)
        G = (g_num + 60.0 * 0.04 * G0) / (g_den + 60.0 * 0.04)        # prior: 60 still minutes with var(rT) = 0.04 C^2
        m = d["day"] == day
        rH[m] = hr[m] - XH[m] @ bH; rT[m] = d["T1"][m] - XT[m] @ bT; Gd[m] = G; sH[m] = aH; sT[m] = aT
        coefs.append((day, *bH, *bT, G, nH))
        # nightly update with today's learning minutes (alarm-free, worn, daytime)
        ml = m & learn; mh = ml & np.isfinite(hr)
        SH = LAM * SH + XH[mh].T @ XH[mh]; sH_y = LAM * sH_y + XH[mh].T @ hr[mh]
        ST = LAM * ST + XT[ml].T @ XT[ml]; sT_y = LAM * sT_y + XT[ml].T @ d["T1"][ml]; nH = LAM * nH + mh.sum()
        still = mh & (A < 0.02)
        if still.sum() > 30:
            # G from today's residuals around TODAY's own still-minute means (departures within the day), accumulated
            a = rH[still] - np.nanmean(rH[still]); b = rT[still] - np.nanmean(rT[still])
            g_num = LAM * g_num + float(np.sum(a * b)); g_den = LAM * g_den + float(np.sum(b * b))
            aH = 0.7 * aH + 0.3 * float(np.mean(np.abs(a))) if day > 1 else float(np.mean(np.abs(a)))
            aT = 0.7 * aT + 0.3 * float(np.mean(np.abs(b))) if day > 1 else float(np.mean(np.abs(b)))
    return dict(rH=rH, rT=rT, G=Gd, sH=sH, sT=sT, A=A, ta=ta, ok=ok, coefs=np.array(coefs))

def pop_prior(pids, hk):
    bH, bT = [], []
    for p in pids:
        d = load(p); hr, A, ta, XH, XT, ok, learn = design(d, hk); mh = learn & np.isfinite(hr)
        if mh.sum() < 500: continue
        bH.append(np.linalg.lstsq(XH[mh], hr[mh], rcond=None)[0]); bT.append(np.linalg.lstsq(XT[learn], d["T1"][learn], rcond=None)[0])
    return np.median(bH, 0), np.median(bT, 0)

if __name__ == "__main__":
    P = IDX["persons"]; folds = [[p for p in P if p % 2 == 0], [p for p in P if p % 2 == 1]]
    for hk in ("raw", "sc"):
        pri = [pop_prior(f[:25], hk) for f in folds]
        # G prior: population median of kappa-like slope is unknown to the band; use 20 bpm/C scaled by 0.8 for 'sc' (mean of U(0.6,1))
        G0 = 20.0 if hk == "raw" else 16.0
        print(hk, "prior HR [b0,bA,bamb] / T1 [c0,cTair,cA]:", np.round(pri[0][0], 3), np.round(pri[0][1], 3), flush=True)
        for k, f in enumerate(folds):
            bH0, bT0 = pri[1 - k]
            for p in f:
                d = load(p); r = fit_person(d, hk, (bH0, bT0, G0))
                np.savez_compressed("%s/cache/fp_%s_%d.npz" % (HERE, hk, p), **r)
    print("done")
