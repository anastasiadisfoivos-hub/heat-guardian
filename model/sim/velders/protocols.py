"""Laboratory protocols used for validation (scenario S12 and the R1 §7 checklist). SIMULATION.

All runs are vectorised over a person table (dict of arrays). Protocol assumptions that the
papers do not pin down are stated in each docstring and repeated in VALIDATION.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .body import TwoNodeOlder, ALL_FEATURES, p_sat_torr, MET_CLAMP

PERSONS_PATH = "/home/claude/hg_ai/sim/data/persons.parquet"


SEALED_JSON = "/home/claude/hg_ai/model/sealed_hg2.json"


def load_persons(path=PERSONS_PATH, idx=None, dev_only=True) -> dict:
    """Validation/tests use DEV persons only (round 3, tester F9): sealed parameter vectors are never simulated
    during development. `idx` slices the DEV table."""
    import json
    df = pd.read_parquet(path)
    if dev_only:
        sealed = set(json.load(open(SEALED_JSON))["sealed_sim_person_ids"])
        df = df[~df.person_id.isin(sealed)].reset_index(drop=True)
    if idx is not None:
        df = df.iloc[idx]
    return {c: df[c].values for c in df.columns if df[c].dtype != object}


def dev_persons_df(path=PERSONS_PATH):
    import json
    df = pd.read_parquet(path)
    sealed = set(json.load(open(SEALED_JSON))["sealed_sim_person_ids"])
    return df[~df.person_id.isin(sealed)].reset_index(drop=True)


def person_met(P: dict, base: float) -> np.ndarray:
    """Clamp-list met x person multiplier, kept out of the 1.1-1.2 band (R1 §7.4 finding 3)."""
    if base >= 1.2:
        return np.maximum(base * P["met_adl_mult"], 1.22)
    return np.minimum(base * P["met_rest_mult"], 1.08)


def _env(t_db, rh, met, v=0.1, clo=0.4, mod=None, drink=0.0, tr=None):
    e = dict(t_db=t_db, rh=rh, v_air=v, met=met, clo=clo, drink_mL=drink)
    if tr is not None:
        e["t_r"] = tr
    if mod is not None:
        e["minute_of_day"] = mod
    return e


def rh_from_pa_torr(t, pa_torr):
    return 100.0 * pa_torr / p_sat_torr(t)


# --------------------------------------------------------------------------- Meade 2024
def meade(P, T, hours=8, rh=45.0, v=0.1, clo=0.4, met=0.86, features=ALL_FEATURES, young=False,
          start_mod=8 * 60, spin_h=6, drink_policy=None, posture_lying=False):
    """Meade 2024 (EHP 132:27003): 8 h seated at T / 45 % RH after a thermoneutral baseline.
    Assumptions: 6 h spin-up at 22 C seated; exposure 08:00-16:00; v 0.1 m/s; clo 0.4.
    Returns per-person arrays. Delta core is end-minus-start (callers subtract the 22 C arm)."""
    b = TwoNodeOlder(P, features=features, young=young, minute_of_day0=start_mod - spin_h * 60)
    mod = start_mod - spin_h * 60
    m = person_met(P, met) if met in MET_CLAMP else np.full(b.n, met)
    for _ in range(spin_h * 60):
        o = b.step(_env(22.0, 45.0, person_met(P, 0.86), mod=mod)); mod += 1
    c0 = o["T_core"].copy()
    rec = {k: [] for k in ("T_core", "T_skin", "HR", "m_sweat", "w", "water_loss_gpm", "deficit_pct", "E_sk", "drift", "strain_cv")}
    drunk = np.zeros(b.n)
    for i in range(hours * 60):
        d = 0.0
        if drink_policy is not None:
            d = drink_policy(b, i)
            drunk += d
        o = b.step(_env(T, rh, m, v=v, clo=clo, mod=mod, drink=d)); mod += 1
        for k in rec:
            rec[k].append(o[k])
    R = {k: np.array(v) for k, v in rec.items()}   # (t, n)
    R["c0"] = c0
    R["dcore"] = R["T_core"][-1] - c0
    R["peak"] = R["T_core"].max(0) - c0
    R["drunk_mL"] = drunk
    return R


# --------------------------------------------------------------------------- PSU HEAT
def _inflection(core, start, thr=0.1, win=15, sustain=30, base_win=30):
    """Core inflection: first minute >= start at which the 15-min core slope exceeds the
    compensable plateau slope (mean slope over the `base_win` min before `start`, i.e. the end of
    the equilibration) by more than thr C/h, sustained for `sustain` min. The plateau slope is
    subtracted because the compensable state itself drifts by 0.05-0.1 C/h (circadian morning rise,
    hydration; V18 0.06-0.15 C/h), which a fixed 0.1 C/h threshold would mistake for the limit.
    core: (t, n). Returns float array of minute indices (nan = no inflection)."""
    t, n = core.shape
    rate = np.full_like(core, np.nan)
    rate[win:] = (core[win:] - core[:-win]) * 60.0 / win
    base = (core[start] - core[start - base_win]) * 60.0 / base_win
    above = rate > (np.maximum(base, 0.0) + thr)[None, :]
    run = np.zeros(above.shape, dtype=int)
    run[-1] = above[-1]
    for i in range(t - 2, -1, -1):
        run[i] = (run[i + 1] + 1) * above[i]
    out = np.full(n, np.nan)
    for j in range(n):
        idx = np.nonzero(run[start:, j] >= sustain)[0]
        if idx.size:
            out[j] = start + idx[0]
    return out


INFLECTION_METHOD = "slope"
HR_PLATEAU = "pre_ramp"     # M8: plateau = last 10 min before the ramp (Kenney "30-40 min in" counts from exposure start)


def _inflection_bp(core, start, stop_rise=1.0, min_seg=15):
    """PSU-style critical point: breakpoint of a continuous two-segment linear fit of core vs time over the ramp,
    from the ramp start until the core has risen `stop_rise` C above its ramp-start value (trials are stopped
    after the core departs from equilibrium; Wolf 2023 / Kenney 2025 define the limit as the inflection of core
    temperature, i.e. the departure from its compensable trajectory)."""
    t, n = core.shape
    out = np.full(n, np.nan)
    for j in range(n):
        c = core[start:, j]
        above = np.nonzero(c > c[0] + stop_rise)[0]
        end = int(above[0]) if above.size else len(c)
        if end < 2 * min_seg + 2:
            continue
        y = c[:end]
        x = np.arange(end, dtype=float)
        best, bk = np.inf, None
        for k in range(min_seg, end - min_seg, 2):
            h = np.maximum(x - k, 0.0)
            A = np.stack([np.ones_like(x), x, h], 1)
            coef, res, *_ = np.linalg.lstsq(A, y, rcond=None)
            sse = float(((A @ coef - y) ** 2).sum())
            if sse < best and coef[2] > 0:
                best, bk = sse, k
        if bk is not None:
            out[j] = start + bk
    return out


def _hr_drift_onset(hr, start, plateau=(30, 40), rise=5.0, hold=10):
    t, n = hr.shape
    base = hr[start + plateau[0]:start + plateau[1]].mean(0)
    above = hr > base + rise
    out = np.full(n, np.nan)
    for j in range(n):
        a = above[start + plateau[1]:, j]
        run = 0
        for i, x in enumerate(a):
            run = run + 1 if x else 0
            if run >= hold:
                out[j] = start + plateau[1] + i - hold + 1
                break
    return out


def psu(P, mode: str, fixed: float, activity: str = "adl", features=ALL_FEATURES, young=False,
        clo=0.4, v=0.2, equil_min=120, max_min=420, start_mod=9 * 60, pa_start=6.0, t_start=36.0):
    """PSU HEAT critical-environment protocol (Wolf 2023; Kenney 2025; Cottle 2022).
    mode 'humid': T_db fixed = `fixed` C, P_a starts at 12 mmHg and rises 1 mmHg every 5 min.
    mode 'dry'  : P_a fixed = `fixed` mmHg, T_db starts at 34 C and rises 1 C every 5 min.
    Assumptions (not given in R1): 60-min equilibration at the starting environment, shorts +
    T-shirt clo 0.4, chamber air 0.2 m/s, protocol starts 09:00, constant metabolic rate.
    Critical environment = environment at the core inflection (15-min slope > 0.1 C/h sustained
    30 min). HR drift onset = first minute HR exceeds its ramp-minute-30-40 plateau by 5 bpm for 10 min."""
    base = 1.37 if activity == "adl" else 0.86
    b = TwoNodeOlder(P, features=features, young=young, minute_of_day0=start_mod - equil_min)
    met = person_met(P, base) if not young else np.full(b.n, base)
    mod = start_mod - equil_min
    T_hist, pa_hist, core, hr, sweat, w, wmax, storage = [], [], [], [], [], [], [], []
    for i in range(equil_min + max_min):
        k = max(0, i - equil_min) // 5
        if mode == "humid":
            T, pa = fixed, pa_start + (k if i >= equil_min else 0)
        else:
            T, pa = t_start + (k if i >= equil_min else 0), fixed
        pa = min(pa, p_sat_torr(T))          # round 3: the ramp stops at saturation (100 % RH), tester F6
        o = b.step(_env(T, rh_from_pa_torr(T, pa), met, v=v, clo=clo, mod=mod)); mod += 1
        T_hist.append(T); pa_hist.append(pa); core.append(o["T_core"]); hr.append(o["HR"])
        sweat.append(o["m_sweat"]); w.append(o["w"]); wmax.append(o["w_max"]); storage.append(o["storage"])
    core, hr, sweat, w = map(np.array, (core, hr, sweat, w))
    T_hist, pa_hist = np.array(T_hist), np.array(pa_hist)
    inf = _inflection_bp(core, equil_min) if INFLECTION_METHOD == "breakpoint" else _inflection(core, equil_min)
    if HR_PLATEAU == "pre_ramp":
        # plateau = the elevated steady state at the starting environment (last 10 min before the ramp);
        # Kenney's "30-40 min in" counts from exposure start, i.e. before their ramp (round 4)
        ons = _hr_drift_onset(hr, equil_min - 40)
    else:
        ons = _hr_drift_onset(hr, equil_min)

    def at(arr, idx):
        out = np.full(len(idx), np.nan)
        ok = ~np.isnan(idx)
        out[ok] = arr[idx[ok].astype(int)] if arr.ndim == 1 else arr[idx[ok].astype(int), np.nonzero(ok)[0]]
        return out

    rh_hist = rh_from_pa_torr(T_hist, pa_hist)
    res = dict(inflection_min=inf, hr_onset_min=ons,
               T_crit=at(T_hist, inf), Pa_crit_kPa=at(pa_hist, inf) * 0.133322, RH_crit=at(rh_hist, inf),
               T_hr=at(T_hist, ons), RH_hr=at(rh_hist, ons),
               sweat_crit=at(sweat, inf), w_crit=at(w, inf), w_cap=np.array(wmax)[-1],
               core=core, hr=hr, T=T_hist, pa=pa_hist, equil=equil_min)
    # rise rate above the limit (first 30 min after inflection) and below (30 min before)
    rate_above = np.full(b.n, np.nan); rate_below = np.full(b.n, np.nan)
    for j in range(b.n):
        if not np.isnan(inf[j]):
            i0 = int(inf[j])
            if i0 + 30 < core.shape[0]:
                rate_above[j] = (core[i0 + 30, j] - core[i0, j]) * 2.0
            if i0 - 30 >= equil_min:
                rate_below[j] = (core[i0, j] - core[i0 - 30, j]) * 2.0
    res["rate_above"] = rate_above
    res["rate_below"] = rate_below
    return res


# --------------------------------------------------------------------------- other lab protocols
def constant_run(P, T, rh, met, minutes, v=0.1, clo=0.4, features=ALL_FEATURES, young=False,
                 start_mod=9 * 60, spin=None, keys=("T_core", "T_skin", "HR", "storage", "m_sweat")):
    b = TwoNodeOlder(P, features=features, young=young, minute_of_day0=start_mod - (spin[3] if spin else 0))
    mod = start_mod - (spin[3] if spin else 0)
    if spin:
        for _ in range(spin[3]):
            b.step(_env(spin[0], spin[1], person_met(P, spin[2]), mod=mod)); mod += 1
    m = person_met(P, met) if met in MET_CLAMP else np.full(b.n, met)
    rec = {k: [] for k in keys}
    for _ in range(minutes):
        o = b.step(_env(T, rh, m, v=v, clo=clo, mod=mod)); mod += 1
        for k in keys:
            rec[k].append(o[k])
    R = {k: np.array(x) for k, x in rec.items()}
    R["body"] = b
    return R
