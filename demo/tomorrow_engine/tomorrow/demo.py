"""The CONSTRUCTED Athens heat-wave demo day (REPORT §8, ARCHITECTURE §6): 29 degC at 06:00 ->
41 degC at 15:00, RH 46 -> 15 %, clear sky, Tmin 28 degC; three identical hot days precede it so the
indoor model starts warm. NOT a measured record — every output says "CONSTRUCTED DEMO DAY".

Apparent temperature for the constructed hours ("apparent_temperature" column): Steadman (1994) SHADE
form, like Open-Meteo's own AT (which, measured on the cached response, carries ~no solar term); plan.py adds
the sun term for the errand (plan.sun_exposed_at). The heat-day flag does not use this column: it uses Baccini's shade AT from T and dew point (plan.py).
History: seven ordinary summer days (ARCH S1, 23/32 degC) precede the three hot days, so the indoor
model is spun up from a normal summer state, not settled at heat-wave level.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .openmeteo import Forecast

DEMO_DATE = "2026-07-14"
N_PRE = 3


def _temp_profile(tmin=28.0, tmax=41.0, t06=None):
    """24 hourly values: tmin at 05:00, t06 at 06:00 (default tmin + 1), tmax at 15:00, cosine segments.
    Defaults = the REPORT §8 demo day (28 / 29 at 06:00 / 41 at 15:00)."""
    t06 = tmin + 1.0 if t06 is None else t06
    t = np.empty(24)
    for h in range(24):
        if 6 <= h <= 15:
            f = (1 - math.cos(math.pi * (h - 6) / 9)) / 2
            t[h] = t06 + (tmax - t06) * f
        else:
            k = h - 15 if h > 15 else h + 9                        # hours since 15:00 (15:00 -> 05:00 = 14 h)
            f = (1 + math.cos(math.pi * k / 14)) / 2
            t[h] = tmin + (tmax - tmin) * f
    t[5] = tmin
    return t


def _shortwave():
    """Clear-sky July Athens (sunrise ~06:10, sunset ~20:50 local), peak ~900 W/m2 (constructed)."""
    h = np.arange(24) + 0.5
    return np.clip(900 * np.sin(math.pi * (h - 6.2) / 14.6), 0, None).round(0)


def apparent_bom(ta, rh, ws_ms, sw=None):
    """Steadman (1994) / Australian BoM apparent temperature. sw=None: SHADE form
    AT = Ta + 0.33 e - 0.70 ws - 4.00. With sw: SUN-EXPOSED radiation form
    AT = Ta + 0.348 e - 0.70 ws + 0.70 Q/(ws + 10) - 4.25, Q = absorbed short-wave per m2 of body surface,
    taken as 0.7 (skin/clothing absorptivity) x 0.25 (projected-area factor of a standing person) x global
    short-wave (constructed assumption, B4-fix). e hPa, ws m/s."""
    e = rh / 100 * 6.105 * np.exp(17.27 * ta / (237.7 + ta))
    if sw is None:
        return ta + 0.33 * e - 0.70 * ws_ms - 4.00
    q = 0.7 * 0.25 * np.asarray(sw, float)
    return ta + 0.348 * e - 0.70 * ws_ms + 0.70 * q / (ws_ms + 10) - 4.25


def _day_rows(tmin, tmax, rh_lo=15.0, rh_hi=46.0, ws_kmh=10.0):
    t = _temp_profile(tmin, tmax)
    t06 = t[6]
    rh = np.clip(rh_hi - (t - t06) / max(tmax - t06, 1e-6) * (rh_hi - rh_lo), rh_lo, 90)
    rh[t < t06] = rh_hi + (t06 - t[t < t06]) * 3                    # night: a little more humid
    sw = _shortwave()
    ws = np.full(24, float(ws_kmh))
    at = apparent_bom(t, rh, ws / 3.6)              # SHADE, like Open-Meteo's own AT; plan.py adds the sun
    return t, rh, sw, ws, at


def synthetic_forecast(days: list[tuple[float, float]], start: str, source="CONSTRUCTED DEMO DAY",
                       rh_lo=15.0, rh_hi=46.0, note="") -> Forecast:
    """Constructed hourly forecast from a list of (Tmin, Tmax) days (same diurnal shape as the demo
    day); one extra copy of the last day is appended so 24:00 of the last day can be interpolated."""
    days = list(days) + [days[-1]]
    cols = {k: [] for k in ("temperature_2m", "relative_humidity_2m", "apparent_temperature",
                            "shortwave_radiation", "wind_speed_10m", "is_day")}
    dmax = []
    for tmin, tmax in days:
        t, rh, sw, ws, at = _day_rows(tmin, tmax, rh_lo, rh_hi)
        for k, v in zip(cols, (t.round(1), rh.round(0), at.round(1), sw, ws, (sw > 0).astype(float))):
            cols[k].append(v)
        dmax.append((tmax, tmin, float(at.max().round(1))))
    idx = pd.date_range(pd.Timestamp(start), periods=24 * len(days), freq="h")
    hourly = pd.DataFrame({k: np.concatenate(v) for k, v in cols.items()}, index=idx)
    for k in ("wet_bulb_temperature_2m", "uv_index", "dew_point_2m"):
        hourly[k] = np.nan
    dates = pd.date_range(idx[0], periods=len(days), freq="D")
    daily = pd.DataFrame(dmax, index=dates, columns=["temperature_2m_max", "temperature_2m_min",
                                                     "apparent_temperature_max"])
    return Forecast(hourly=hourly, daily=daily, source=source, fetched_at=None, forecast_age_h=float("nan"),
                    lat=37.98, lon=23.73, elevation=None, notes=[note] if note else [])


N_NORMAL = 7            # ordinary summer days before the wave (ARCH S1: Tmax 30-33)


def demo_forecast(n_pre: int = N_PRE, n_normal: int = N_NORMAL) -> Forecast:
    start = (pd.Timestamp(DEMO_DATE) - pd.Timedelta(days=n_pre + n_normal)).strftime("%Y-%m-%d")
    return synthetic_forecast([(23.0, 32.0)] * n_normal + [(28.0, 41.0)] * (n_pre + 1), start,
                              note="constructed: %d ordinary days (23/32), %d identical hot days, then the demo day"
                              % (n_normal, n_pre))
