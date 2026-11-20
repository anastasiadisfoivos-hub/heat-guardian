"""Indoor temperature/humidity model (R3 §1.6): two-node lumped building, hourly
(slow node = building mass + air; fast node = window/ventilation path; T_in = T_slow + T_fast;
see simulate() for the two anchor forms).
    RH_in   : absolute humidity conserved, AH_in = AH_ratio * AH_out (Nguyen 2014, beta 0.69)

Integration: exact exponential update per hour (stable for any tau). All parameters are
LITERATURE PRIORS (R3 §1.6 table, values inside its ranges, see CLASSES); only class A dynamics come from a fit (Bath,
our own DERIVED analysis). There is no Athens indoor dataset: say "literature prior".
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np

# ---- class table: R3 §1.6 ------------------------------------------------------------
@dataclass(frozen=True)
class HomeClass:
    name: str
    tau_s: float      # h
    dT_home: float    # degC
    tau_f: float      # h
    g_f: float        # -
    g_sun: float      # degC per 100 W/m2
    anchor: str       # "mean": dT_home is indoor-mean minus outdoor-mean (Bath fit, R3 equation as printed)
                      # "min":  dT_home is indoor night-min minus outdoor night-min (how R3 anchors B-D on Sakka)
    note: str


CLASSES = {
    "A": HomeClass("A insulated temperate (Bath-like)", 36.0, 4.5, 3.0, 0.15, 0.0, "mean",
                   "FIT: Bath (R3 §1.4, DERIVED) tau 24-48 h, offset +4..+5 on the mean, g_f 0.10-0.20"),
    # B-D: literature priors. Values chosen inside the R3 §1.6 ranges (B4-fix, see REPORT): the warm end for B
    # (tau_s 72 of 48-72, dT +3.0 of +2..+3, g_f 0.25 of 0.20-0.25) is the only corner that gives at the same
    # time S1 indoor 26-29 degC (ARCH S1), creep 0.2-0.8 K/day (Sakka) and night min >= 28 from wave night 2.
    "B": HomeClass("B Athens concrete apartment, mid floor, shaded", 72.0, 3.0, 3.0, 0.25, 0.1, "min",
                   "PRIOR: Sakka 2012, Zuurbier 2021; R3 ranges tau_s 48-72, dT +2..+3 (indoor min vs outdoor min), g_f 0.20-0.25"),
    # C: tau_s 36 (24-36), dT +4.0 (+4..+5), g_f 0.30, tau_f 2 as R3; g_sun 0.15 instead of R3's point 0.3 so that
    # C-B = +1.5..2.5 degC on the daily mean during a wave (Zuurbier under-roof +1.6/+2.2) — DEVIATION, reported.
    "C": HomeClass("C Athens top floor / under roof, S-W windows", 36.0, 4.0, 2.0, 0.30, 0.15, "min",
                   "PRIOR: Zuurbier 2021, Vandentorren 2006; g_sun 0.15 (R3 point 0.3) is a B4 deviation"),
    "D": HomeClass("D ground floor, old masonry, shutters", 96.0, 1.5, 5.0, 0.10, 0.0, "min",
                   "PRIOR: Zuurbier 2021; R3 ranges tau_s 72-120, dT +1..+2, tau_f 4-6, g_f 0.10"),
}

AH_RATIO = 0.69          # Nguyen, Schwartz, Dockery 2014 (Indoor Air 24:103), indoor/outdoor AH slope
BEDROOM_OFFSET = 0.5     # R3 §1.6 (iii): bedroom 0.4-0.6 degC warmer than living room (Zuurbier 2021)
ATHENS_CENTRE = (37.98, 23.73)


def urban_offset_for(lat: float, lon: float) -> tuple[float, float]:
    """(night, heat-wave-day) offset added to T_out before the model (Founda & Santamouris 2017).

    0 for the central-Athens Open-Meteo cell (it already is the dense city, R3 §1.6);
    +1.5 night / +3.5 heat-wave day elsewhere: R3 §1.6 values (ARCHITECTURE §6 says +1.0/+2.0; the research
    file wins by the ARCH preamble — conflict reported). Tunable from the CLI.
    """
    dlat = (lat - ATHENS_CENTRE[0]) * 111.0
    dlon = (lon - ATHENS_CENTRE[1]) * 111.0 * math.cos(math.radians(lat))
    return (0.0, 0.0) if math.hypot(dlat, dlon) <= 5.0 else (1.5, 3.5)


def sat_vp_kpa(t):
    """Magnus (Alduchov & Eskridge 1996), kPa."""
    t = np.asarray(t, dtype=float)
    return 0.61094 * np.exp(17.625 * t / (t + 243.04))


def abs_humidity(t, rh):
    """g/m3."""
    return 2166.8 * (np.asarray(rh) / 100.0) * sat_vp_kpa(t) / (np.asarray(t) + 273.15)


def rh_from_ah(t, ah):
    return np.clip(ah * (np.asarray(t) + 273.15) / (2166.8 * sat_vp_kpa(t)) * 100.0, 1.0, 100.0)


def _trailing(x, n, fn):
    out = np.empty(len(x))
    for i in range(len(x)):
        out[i] = fn(x[max(0, i - n + 1):i + 1])
    return out


def simulate(t_out, shortwave=None, rh_out=None, home_class="B", is_day=None, heat_day=None,
             urban_offset=(0.0, 0.0), t_slow0=None, t_fast0=0.0, ah_ratio=AH_RATIO,
             params: HomeClass | None = None, start_index: int = 0) -> dict:
    """Hourly indoor model.

    anchor "mean" (class A, R3 equation as printed):
        T_slow' = (T_out + dT - T_slow)/tau_s ;  T_fast' = (g_f (T_out - T_slow + dT) + g_sun S/100 - T_fast)/tau_f
    anchor "min" (classes B-D, B4-fix): R3 anchors dT_home on "indoor min vs outdoor min" (Sakka), so
        T_slow' = (N24 + dT - T_slow)/tau_s ;  T_fast' = (g_f (T_out - N24) + g_sun S/100 - T_fast)/tau_f
        with N24 = trailing 24-h minimum of T_out (causal). Indoor night min ~ outdoor min + dT.
    t_slow0: initial slow node. Default = settled on the first 24 h (mean or min + dT). Callers should pass
             a carried-over state (plan.make_plan does, from the previous night's run) or >= 7 days of history.
    start_index: integrate from this hour with (t_slow0, t_fast0) as the state there (carry-over); earlier
             hours only feed the trailing 24-h reference and are returned as that constant state.
    NaNs in t_out are filled by interpolation/hold before the model runs.
    """
    p = params or CLASSES[home_class]
    t_out = np.asarray(t_out, dtype=float)
    if np.isnan(t_out).any():
        idx = np.arange(len(t_out)); ok = ~np.isnan(t_out)
        t_out = np.interp(idx, idx[ok], t_out[ok])
    n = len(t_out)
    S = np.zeros(n) if shortwave is None else np.nan_to_num(np.asarray(shortwave, dtype=float))
    day = np.ones(n) if is_day is None else np.asarray(is_day, dtype=float)
    hd = np.zeros(n) if heat_day is None else np.asarray(heat_day, dtype=float)
    t_eff = t_out + np.where(day > 0.5, urban_offset[1] * hd, urban_offset[0])
    ks = 1.0 - math.exp(-1.0 / p.tau_s)
    kf = 1.0 - math.exp(-1.0 / p.tau_f)
    if p.anchor == "min":
        ref = _trailing(t_eff, 24, np.min)
    else:
        ref = t_eff
    if t_slow0 is None:
        ts = (np.min(t_eff[start_index:start_index + 24]) if p.anchor == "min"
              else np.mean(t_eff[start_index:start_index + 24])) + p.dT_home
    else:
        ts = float(t_slow0)
    tf = float(t_fast0)
    slow = np.empty(n); fast = np.empty(n)
    slow[:start_index] = ts; fast[:start_index] = tf
    for i in range(start_index, n):
        slow[i] = ts; fast[i] = tf
        if p.anchor == "min":
            target_f = p.g_f * (t_eff[i] - ref[i]) + p.g_sun * S[i] / 100.0
        else:
            target_f = p.g_f * (t_eff[i] - ts + p.dT_home) + p.g_sun * S[i] / 100.0
        ts += ks * (ref[i] + p.dT_home - ts)
        tf += kf * (target_f - tf)
    t_in = slow + fast
    out = {"t_in": t_in, "t_bed": t_in + BEDROOM_OFFSET, "t_slow": slow, "t_fast": fast, "t_out_eff": t_eff}
    if rh_out is not None:
        rh = np.asarray(rh_out, dtype=float)
        if np.isnan(rh).any():
            idx = np.arange(len(rh)); ok = ~np.isnan(rh)
            rh = np.interp(idx, idx[ok], rh[ok])
        ah = ah_ratio * abs_humidity(t_out, rh)
        out["rh_in"] = rh_from_ah(t_in, ah)
        out["rh_bed"] = rh_from_ah(t_in + BEDROOM_OFFSET, ah)
    return out


def class_table() -> list[dict]:
    return [dict(cls=k, **asdict(v)) for k, v in CLASSES.items()]


# ---- metrics used by the R3 sanity tests ------------------------------------------------
def lag_and_ratio(t_in, t_out):
    """Same method as research/bath_indoor_outdoor_stats.py: lag of max cross-correlation of
    de-trended (24 h centred mean removed) hourly anomalies, 0..12 h; amplitude ratio =
    mean daily range indoor / mean daily range outdoor (whole days only)."""
    import pandas as pd
    a = pd.Series(t_in); b = pd.Series(t_out)
    an = a - a.rolling(24, center=True).mean(); bn = b - b.rolling(24, center=True).mean()
    ab = pd.concat([an, bn], axis=1).dropna()
    cc = [ab.iloc[:, 0].corr(ab.iloc[:, 1].shift(l)) for l in range(13)]
    lag = int(np.nanargmax(cc))
    nd = len(a) // 24
    A = np.asarray(a)[:nd * 24].reshape(nd, 24); B = np.asarray(b)[:nd * 24].reshape(nd, 24)
    ok = ~(np.isnan(A).any(1) | np.isnan(B).any(1))
    ratio = float((A[ok].max(1) - A[ok].min(1)).mean() / (B[ok].max(1) - B[ok].min(1)).mean())
    return lag, ratio
