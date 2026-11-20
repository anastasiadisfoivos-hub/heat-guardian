#!/usr/bin/env python3
"""R6 E5: DRINK nagging. SIMULATION DEV. Python EMULATION of the frozen DRINK tier (design A; validated below against the frozen
binary's own level >= 1 minutes), then Talzin variants:
  D1 'exception' : the personal line is her calm f20 PLUS her own usual rise for this much recent movement
                   rel_x = f20 - calm - c_p * W30 ; c_p = her slope of (f20 - calm) on W30, fitted nightly on previous days (all level < 2 minutes)
  D2 'settled'   : after a DRINK episode ends, no new DRINK for R = 120 min unless f20 >= (f20 at the last nudge) + 0.15 C
                   (Talzin: right after a sudden change a marble is less likely to change again on its own). COOL/DANGER untouched.
  D3 = D1 + D2 ;  D4 'momentum': the A-path needs the forecast not to be falling (EWMA10 - EWMA60 >= 0).
Metrics as eval_sim_m7: S1 days DRINK onsets/day and DRINK minutes/day (median person); S2 days core38 sensitivity = any
DRINK/COOL/DANGER display in [t-45, t+10]; 'informed' = display OR a DRINK nudge in the previous 120 min."""
import json, numpy as np
from common import *; import feats
from eval3 import ew
LOW = 0.018
def tier(cond, k=2, hold=10):
    on = np.zeros(len(cond), bool); run = 0; o = 0; off = 0
    for i, c in enumerate(cond):
        run = run + 1 if c else 0
        if run >= k: o = 1; off = 0
        elif o:
            if c: off = 0
            else:
                off += 1
                if off >= hold: o = 0
        on[i] = o
    return on
def emulate(p, hk, variant, DELTA=0.30, R=120, RISE=0.15, CALM_ONLY=False):
    d, X, ok, _ = feats.build(p, hk); n = len(d["T1"]); f20 = X["f20"]; mod = d["minute_of_day"]; day = d["day"]
    hr = (d["HR_meas"] if hk == "raw" else d["hr_scaled"]).astype(float); worn = d[hk + "_worn"]; a = np.nan_to_num(d["a_std_g"])
    don = np.zeros(n, int); c = 0
    for i in range(n): c = c + 1 if worn[i] > 0 else 0; don[i] = c
    valid = d[hk + "_valid"] > 0; thermal_ok = valid & (don >= 20); active = a > 0.02
    fl = d[hk + "_level"]; cool_plus = fl >= 2                       # COOL / DANGER taken from the frozen binary (untouched)
    tin = X["tair"]; ctx = (tin >= 30.0) | (d[hk + "_env_run"] > 0) | (hr > 108)
    v12p = valid & ctx & (d[hk + "_v12_f20"] >= 37.85 - LOW)
    env1 = (d[hk + "_env_run"] >= 10) | (d[hk + "_env_dose"] >= 10)
    W30 = feats.rollsum(np.minimum(a, 0.30), 30); M = ew(f20, 10) - ew(f20, 60)
    # calm baseline as frozen: daily median of resting daytime level-0 minutes, EMA 0.3, clamp [36.8, 37.7]; uses the FROZEN level (same data it saw)
    base = np.full(n, np.nan); b = np.nan; cp = np.zeros(n); sxx = 0.0; sxy = 0.0
    for dd in range(1, 11):
        m = day == dd; base[m] = b
        cp[m] = np.clip(sxy / sxx, 0.0, 0.6) if sxx > 1.0 else 0.0
        mm = m & (mod >= 480) & (mod < 1320) & (worn == 2) & thermal_ok & ~active & (fl == 0)
        if mm.sum() >= 60:
            med = np.median(f20[mm]); b = med if not np.isfinite(b) else b + 0.3 * (med - b); b = min(max(b, 36.8), 37.7)
        if np.isfinite(b):                                            # her usual rise per unit of recent movement (level < 2 minutes of today)
            ml = m & (mod >= 480) & (mod < 1320) & (worn == 2) & thermal_ok & (fl < 2)
            if CALM_ONLY: ml &= (tin < 30.0)                           # 'calm brain': her usual response is learned in ordinary rooms only
            sxx = 0.85 * sxx + float(np.sum(W30[ml] ** 2)); sxy = 0.85 * sxy + float(np.sum(W30[ml] * (f20[ml] - b)))
    have = np.isfinite(base); rel = np.where(have, f20 - base, -9.0)
    if variant in ("D1", "D3"): rel = rel - cp * W30
    ap = thermal_ok & have & (rel >= DELTA - LOW)
    if variant == "D4": ap &= (M >= 0.0)
    drink = tier((v12p | ap | env1) & (worn > 0))
    if variant in ("D2", "D3"):
        out = np.zeros(n, bool); since = 10 ** 6; last = -9.0; prev = False
        for i in range(n):
            x = drink[i]
            if x and not prev:                                        # would start an episode
                if since < R and f20[i] < last + RISE: x = False    # settled: she was just told
                else: last = f20[i]
            if x: since = 0
            else: since += 1
            out[i] = x; prev = x
        drink = out
    disp_drink = drink & ~cool_plus & (worn > 0)
    return d, disp_drink, cool_plus, drink
def metrics(P, hk, variant, frozen=False, **kw):
    per = []; sens = []; inf = []; agree = []
    for p in P:
        d, dd_, cp_, drink = emulate(p, hk, "D0" if frozen else variant, **kw)
        if frozen: dd_ = d[hk + "_state"] == 1; cp_ = d[hk + "_level"] >= 2
        fz = (d[hk + "_level"] >= 1); agree.append(((drink | cp_) == fz).mean())
        on = dd_ & ~np.concatenate([[False], dd_[:-1]]); types = d["types"]; day = d["day"]
        s1 = [dy for dy in range(1, 11) if types[dy - 1] == "S1"]
        if s1: per.append((np.mean([on[day == dy].sum() for dy in s1]), np.mean([dd_[day == dy].sum() for dy in s1])))
        disp = dd_ | cp_; nud = np.zeros(len(on), bool)
        idx = np.where(on)[0]
        for i in idx: nud[i:i + 121] = True
        for (ts, te, dy) in events(p, "core38"):
            if not types[dy - 1].startswith("S2"): continue
            i = ts - d["t0"]; a = max(0, i - 45); b = min(len(disp), i + 11); h = bool(disp[a:b].any()); sens.append(h); inf.append(h or bool(nud[min(i, len(nud) - 1)]))
    per = np.array(per)
    return dict(s1_persons=len(per), drink_per_day_median=float(np.median(per[:, 0])), drink_min_median=float(np.median(per[:, 1])), drink_per_day_mean=float(per[:, 0].mean()),
                drink_min_mean=float(per[:, 1].mean()), s2_events=len(sens), s2_sens=float(np.mean(sens)), s2_informed=float(np.mean(inf)), emu_agree=float(np.mean(agree)))
if __name__ == "__main__":
    P = IDX["persons"]; out = {}
    for hk in ("raw", "sc"):
        print("== %s HR ==" % hk, flush=True)
        r = metrics(P, hk, "D0", frozen=True); print("  FROZEN binary      ", {k: round(v, 2) for k, v in r.items()}); out[hk + "|frozen"] = r
        for v in ("D0", "D1", "D2", "D3", "D4"):
            r = metrics(P, hk, v); print("  %s emulation       " % v, {k: round(v_, 2) for k, v_ in r.items()}, flush=True); out[hk + "|" + v] = r
    json.dump(out, open(HERE + "/out_drink.json", "w"), indent=1)
