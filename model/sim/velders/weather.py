"""Synthetic Athens-summer outdoor weather (SIMULATION).

Day-level (Tmax, Tmin, dew point) -> hourly temperature with a piecewise-cosine diurnal shape
(minimum 06:00, maximum 15:00), RH from a fixed daily dew point, clear-sky shortwave radiation
(sunrise ~06:15, sunset ~20:45 local in July; peak ~900 W/m2). S1 and S2 numbers are ARCH §3.3
(S2 = Sakka-2007 heat wave: Tmax 38-42, Tmin 26-28; R3 §1.1). The shapes, not the values, are
the only thing taken from the Open-Meteo sample (research/openmeteo_sample.json is November, so
only the diurnal timing convention is used).
"""
from __future__ import annotations

import numpy as np

from .indoor import sat_vp_kpa

T_MIN_H, T_MAX_H = 6.0, 15.0


def diurnal(tmax_days, tmin_days, tmin_next=None):
    """Hourly temperature for consecutive days. Rising 06->15 h from Tmin to Tmax, falling 15->30 h
    (06 h next day) from Tmax to next day's Tmin."""
    tmax = np.asarray(tmax_days, float)
    tmin = np.asarray(tmin_days, float)
    D = len(tmax)
    tmin_n = np.append(tmin[1:], tmin[-1] if tmin_next is None else tmin_next)
    tmin_p = np.insert(tmin[:-1], 0, tmin[0])
    out = np.empty(D * 24)
    for d in range(D):
        for h in range(24):
            if h < T_MIN_H:            # falling from previous day's max to today's min
                tm_prev = tmax[d - 1] if d > 0 else tmax[d]
                u = (h + 24 - T_MAX_H) / (24 - T_MAX_H + T_MIN_H)
                out[d * 24 + h] = tmin[d] + (tm_prev - tmin[d]) * 0.5 * (1 + np.cos(np.pi * u))
            elif h <= T_MAX_H:
                u = (h - T_MIN_H) / (T_MAX_H - T_MIN_H)
                out[d * 24 + h] = tmin[d] + (tmax[d] - tmin[d]) * 0.5 * (1 - np.cos(np.pi * u))
            else:
                u = (h - T_MAX_H) / (24 - T_MAX_H + T_MIN_H)
                out[d * 24 + h] = tmin_n[d] + (tmax[d] - tmin_n[d]) * 0.5 * (1 + np.cos(np.pi * u))
    return out


def solar(D, peak=900.0, sunrise=6.25, sunset=20.75, cloud=None):
    h = np.arange(D * 24) % 24 + 0.5
    day = (h > sunrise) & (h < sunset)
    s = np.where(day, peak * np.clip(np.sin(np.pi * (h - sunrise) / (sunset - sunrise)), 0, 1) ** 1.2, 0.0)
    if cloud is not None:
        s = s * np.repeat(1 - np.asarray(cloud), 24)
    return s


def rh_from_dew(t, td):
    return np.clip(100 * sat_vp_kpa(td) / sat_vp_kpa(t), 5, 100)


def make_days(day_types, rng):
    """day_types: list of 'S1', 'PRE', 'S2_k' (k = 1..5 heat-wave day), 'POST'.
    Returns (tmax, tmin, tdew) per day."""
    tmax, tmin, tdew = [], [], []
    for t in day_types:
        if t == "S1":
            tmax.append(rng.uniform(30, 33)); tmin.append(rng.uniform(22, 24)); tdew.append(rng.uniform(14, 18))
        elif t == "PRE":
            tmax.append(rng.uniform(33, 36)); tmin.append(rng.uniform(24, 26)); tdew.append(rng.uniform(13, 17))
        elif t == "POST":
            tmax.append(rng.uniform(32, 35)); tmin.append(rng.uniform(24, 26)); tdew.append(rng.uniform(14, 18))
        elif t.startswith("S2_"):
            k = int(t[3:])
            tmax.append(38.0 + (k - 1) * 0.75 + rng.uniform(-0.5, 0.5))     # ramps 38 -> 41 (+-0.5)
            tmin.append(26.0 + (k - 1) * 0.4 + rng.uniform(-0.3, 0.3))      # ramps 26 -> 27.6
            tdew.append(rng.uniform(14, 18))
        else:
            raise ValueError(t)
    return np.clip(tmax, 0, 42.5), np.clip(tmin, 0, 28.3), np.array(tdew)


def hourly_weather(day_types, rng):
    tmax, tmin, tdew = make_days(day_types, rng)
    T = diurnal(tmax, tmin)
    td = np.repeat(tdew, 24)
    td = np.minimum(td, T - 0.5)
    return dict(t_out=T, rh_out=rh_from_dew(T, td), s_rad=solar(len(day_types)), tmax=tmax, tmin=tmin)
