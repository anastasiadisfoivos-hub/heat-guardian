"""HTT-DEV for hg2 (young adults 18-33, chamber walk, DEV): all 65 people, both sessions (ARCH 3.1: the 13 v1-sealed
people are SPENT and folded into DEV for hg2). Real pill core + lab HR. The band's thermal/wrist inputs do not exist:
air = session ambient + SHTC3-like noise (sensor model), everything in HTT_MASK -> NaN (z = 0), flux_valid = 0.
Time of day unknown (0xFFFF). Identities are never used to pick anything; subjects are only grouping keys."""
import sys
import numpy as np
from . import features as FT
from .common import SEED

sys.path.insert(0, "/home/claude/hgmodel")
F = np.float32


def load(noise=True, seed=SEED):
    import common as V1   # /home/claude/hgmodel/common.py (read-only DB)
    sessions, subj = V1.load_htt()
    rng = np.random.default_rng(seed + 31)
    lanes = []
    for s in sessions:
        p = subj.loc[s["subject"]]
        rest = float(p.resting_hr) if np.isfinite(p.resting_hr) else 70.0
        prof = dict(age=float(p.age), sex_m=1.0 if p.sex == "M" else 0.0, bmi=float(p.bmi), med_flags=0)
        n = len(s["hr"])
        if noise:
            tair = (s["amb"] + rng.normal(0, 0.3) + rng.normal(0, 0.15, n)).astype(F)
            rh = np.clip(s["rh"] + rng.normal(0, 2) + rng.normal(0, 0.5, n), 0, 100).astype(F)
        else:
            tair = np.full(n, s["amb"], F); rh = np.full(n, s["rh"], F)
        lanes.append(dict(subject=s["subject"], session=s["session"], prof=prof, rest=rest, hr=s["hr"].astype(F), tair=tair, rh=rh,
                          core=s["core"].astype(np.float64), hrmax=208 - 0.7 * prof["age"]))
    return lanes


def targets(l):
    c = l["core"]; n = len(c)
    c20 = np.full(n, np.nan); c30 = np.full(n, np.nan); c20[:max(n - 20, 0)] = c[20:]; c30[:max(n - 30, 0)] = c[30:]
    mx = np.full(n, np.nan)
    for t in range(n):
        w = c[t + 1:t + 31]
        if len(w) and np.isfinite(w).any(): mx[t] = np.nanmax(w)
    p38 = np.where(np.isfinite(mx), (mx >= 38.0).astype(float), np.nan); p385 = np.where(np.isfinite(mx), (mx >= 38.5).astype(float), np.nan)
    strain = np.clip(5 * (c - 36.9) / (39.5 - 36.9) + 5 * (l["hr"] - l["rest"]) / (l["hrmax"] - l["rest"]), 0, 10)
    return np.stack([c, c20, c30, p38, p385, strain], 1).astype(F)


def features(lanes):
    """runs all sessions as lock-step lanes; returns list of (X [n,32] masked, aux dict) per session"""
    T = max(len(l["hr"]) for l in lanes); N = len(lanes)
    pad = lambda a, v: np.concatenate([a, np.full(T - len(a), v, a.dtype)])
    cols = dict(t1=np.full((T, N), np.nan, F), t2=np.full((T, N), np.nan, F), pi=np.full((T, N), np.nan, F),
                astd=np.full((T, N), np.nan, F), worn=np.full((T, N), 2, np.int64), mod=np.full((T, N), 0xFFFF, np.int64),
                hrq=np.full((T, N), 4, np.int64),
                hr=np.stack([pad(l["hr"], np.nan) for l in lanes], 1), tair=np.stack([pad(l["tair"], np.nan) for l in lanes], 1),
                rh=np.stack([pad(l["rh"], np.nan) for l in lanes], 1))
    prof = {k: np.array([l["prof"][k] for l in lanes]) for k in lanes[0]["prof"]}
    tw = dict(rest_hr=np.array([l["rest"] for l in lanes]), k_person=0.12, core_offset=0.0, c_bodyheat=0.15,
              t1_night_base=np.full((N, 24), np.nan))
    X, aux, idx = FT.run_lanes(cols, prof, tw)
    out = []
    for j, l in enumerate(lanes):
        sel = (idx[:, 1] == j) & (idx[:, 0] < len(l["hr"]))
        x = X[sel].copy(); x[:, FT.HTT_MASK] = np.nan; x[:, 5] = 0
        out.append((x, {k: v[sel] for k, v in aux.items()}))
    return out
