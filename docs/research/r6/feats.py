"""R6 causal feature builder - SIMULATION DEV. Everything is band-observable and O(1)/minute on chip (leaky integrals, rings <= 60)."""
import numpy as np
from common import *
import fingerprint as fp
def leaky(x, tau):
    y = np.empty(len(x)); s = 0.0; a = 1.0 / tau
    for i in range(len(x)): s = s * (1 - a) + x[i]; y[i] = s
    return y
def lag(x, k): return np.concatenate([np.full(k, x[0]), x[:-k]])
def rollsum(x, k): c = np.cumsum(np.nan_to_num(x)); return c - np.concatenate([np.zeros(k), c[:-k]])
def build(pid, hk):
    d = load(pid); f = dict(np.load("%s/cache/fp_%s_%d.npz" % (HERE, hk, pid))); n = len(d["T1"])
    hr = (d["HR_meas"] if hk == "raw" else d["hr_scaled"]).astype(float)
    nn = d[hk + "_core_20"].astype(float); v12 = d[hk + "_v12_f20"].astype(float)
    f20 = np.where((hr > 108) & (v12 > nn), v12, nn)                     # frozen M11.3 guard (HR part)
    worn = d[hk + "_worn"] > 0; f20 = np.where(np.isfinite(f20), f20, 36.9)
    day = d["day"]; A = f["A"]
    # her calm baseline + spread of f20 from PREVIOUS days (nightly, like design A): still, daytime, no tier on
    calm = np.full(n, np.nan); sp = np.full(n, np.nan)
    for dd in range(2, 11):
        m0 = (day < dd) & f["ok"] & (d[hk + "_level"] == 0) & (A < 0.02)
        if m0.sum() > 60:
            c = np.median(f20[m0]); calm[day == dd] = c; sp[day == dd] = 1.4826 * np.median(np.abs(f20[m0] - c))
    calm = np.where(np.isfinite(calm), calm, 37.1); sp = np.clip(np.where(np.isfinite(sp), sp, 0.15), 0.05, 0.4)
    rel = f20 - calm
    # recovery failure: HR residual (her own line) held from the last still minute (<= 20 min old), else 0
    rH = np.nan_to_num(f["rH"]); still = (A < 0.02) & np.isfinite(hr)
    rec = np.zeros(n); last = 0.0; age = 99
    for i in range(n):
        if still[i]: last = rH[i]; age = 0
        else: age += 1
        rec[i] = last if age <= 20 else 0.0
    # exposure 'today': minutes since midnight with rel >= 0.3 (resets at midnight)
    ex = np.zeros(n); s = 0
    for i in range(n):
        if d["minute_of_day"][i] == 0: s = 0
        s += rel[i] >= 0.3; ex[i] = s
    X = dict(f20=f20, mom15=f20 - lag(f20, 15), mom45=f20 - lag(f20, 45), ew60=leaky(f20 - 36.9, 60) / 60 + 36.9,
             dose=leaky(np.maximum(0, f20 - 37.9), 90), dose_her=leaky(np.maximum(0, rel - 0.5), 90), rel=rel, z=rel / sp, expo=ex,
             v12=v12, v12z=d[hk + "_v12_z"].astype(float), l385=d[hk + "_logit_p385"].astype(float), env=d[hk + "_env_dose"].astype(float),
             tair=f["ta"], rT=np.nan_to_num(f["rT"]), rH=rH, rec=rec, A=A, W60=rollsum(A, 60), W180=rollsum(A, 180),
             agree=np.minimum(nn, v12), hrx=np.nan_to_num(hr - np.nanmedian(hr[(day == 1)] if np.isfinite(hr[day == 1]).any() else hr)))
    ok = worn & (day >= 2)
    fut = np.full(n, -np.inf)
    for k in range(1, 31): fut[:n - k] = np.maximum(fut[:n - k], d["T_core"][k:])
    return d, X, ok, (fut >= 38.5).astype(int)
