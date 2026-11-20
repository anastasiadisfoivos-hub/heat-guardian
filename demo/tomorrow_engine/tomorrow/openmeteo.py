"""Open-Meteo forecast fetch with a one-call-per-night cache (ARCHITECTURE §6, R3 §5).

Rules implemented here (binding):
- exactly the R3 §5 URL (16 forecast days + 2 past days, Europe/Athens);
- cache file ``<cache_dir>/openmeteo_<lat>_<lon>.json`` holding the raw response plus
  ``fetched_at`` (UTC ISO); if the cache is < 20 h old no call is made;
- on any HTTP error / 429 / network error / truncated body: ONE retry after 60 s, then give up and
  use the cache (any age) with ``source = "cache"`` and ``forecast_age_h`` set. Never a loop;
- every live attempt is recorded in ``openmeteo_<lat>_<lon>.attempt.json``; no new attempt within
  20 h of the last one, even after a failure (re-running the CLI never adds calls);
- a ``fetched_at`` > 1 h in the future is a clock error: the cache counts as stale, age clamped >= 0;
- ``null`` values at the end of the 16-day horizon become NaN.

Weather data by Open-Meteo.com (CC BY 4.0).
"""
from __future__ import annotations

import http.client
import json
import math
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ATTRIBUTION = "Weather data by Open-Meteo.com"
HOURLY_VARS = ["temperature_2m", "relative_humidity_2m", "apparent_temperature",
               "wet_bulb_temperature_2m", "shortwave_radiation", "wind_speed_10m",
               "uv_index", "dew_point_2m", "is_day"]
DAILY_VARS = ["temperature_2m_max", "temperature_2m_min", "apparent_temperature_max", "uv_index_max"]
CACHE_FRESH_H = 20.0
BACKOFF_H = 20.0            # after ANY live attempt (ok or failed) no new call for 20 h: one call per night
FUTURE_TOL_H = 1.0          # a fetched_at more than 1 h in the future is a clock error: cache treated as stale
RETRY_WAIT_S = 60.0
TIMEOUT_S = 20.0


class ForecastUnavailable(RuntimeError):
    """No live forecast and no cache on disk."""


def build_url(lat: float, lon: float) -> str:
    """The R3 §5 URL, verbatim apart from the coordinates."""
    return ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
            "&hourly=%s&daily=%s&timezone=Europe%%2FAthens&forecast_days=16&past_days=2"
            % (_fmt(lat), _fmt(lon), ",".join(HOURLY_VARS), ",".join(DAILY_VARS)))


def _fmt(x: float) -> str:
    return ("%.2f" % float(x)).rstrip("0").rstrip(".")


def cache_path(lat: float, lon: float, cache_dir: str) -> str:
    return os.path.join(cache_dir, "openmeteo_%.2f_%.2f.json" % (float(lat), float(lon)))


@dataclass
class Forecast:
    hourly: pd.DataFrame            # index = local naive timestamps (Europe/Athens), NaN for nulls
    daily: pd.DataFrame             # index = local dates
    source: str                     # "open-meteo" | "cache" | "CONSTRUCTED DEMO DAY"
    fetched_at: str | None          # UTC ISO of the fetch that produced the data
    forecast_age_h: float           # hours between fetched_at and now
    lat: float
    lon: float
    elevation: float | None = None
    raw: dict = field(default_factory=dict, repr=False)
    notes: list = field(default_factory=list)

    def day(self, date) -> pd.DataFrame:
        """The 24 hourly rows of one local date; nulls filled by time interpolation, edge hold."""
        d = pd.Timestamp(date).normalize()
        rows = self.hourly.loc[(self.hourly.index >= d) & (self.hourly.index < d + pd.Timedelta(hours=24))].copy()
        if len(rows) != 24:
            raise ValueError("forecast has %d hours for %s (need 24)" % (len(rows), d.date()))
        if rows.isna().any().any():
            self.notes.append("null values on %s filled by interpolation/hold" % d.date())
            rows = rows.interpolate(limit_direction="both")
        return rows


def parse(raw: dict, source: str, fetched_at: str | None, now: datetime | None = None) -> Forecast:
    """Turn an Open-Meteo JSON dict into a Forecast. ``null`` → NaN; trailing all-null hours dropped."""
    h = raw["hourly"]
    idx = pd.to_datetime(h["time"])
    cols = {k: np.array([np.nan if v is None else v for v in h.get(k, [None] * len(idx))], dtype=float)
            for k in HOURLY_VARS}
    hourly = pd.DataFrame(cols, index=idx)
    core = ["temperature_2m", "relative_humidity_2m", "apparent_temperature"]
    valid = ~hourly[core].isna().all(axis=1)
    if valid.any():
        last = valid[valid].index[-1]
        n_drop = int((hourly.index > last).sum())
        hourly = hourly.loc[:last]
    else:
        n_drop = len(hourly)
        hourly = hourly.iloc[:0]
    d = raw.get("daily", {})
    daily = pd.DataFrame({k: np.array([np.nan if v is None else v for v in d.get(k, [])], dtype=float)
                          for k in DAILY_VARS if k in d}, index=pd.to_datetime(d.get("time", [])))
    now = now or datetime.now(timezone.utc)
    age = _age_h(fetched_at, now)
    fc = Forecast(hourly=hourly, daily=daily, source=source, fetched_at=fetched_at, forecast_age_h=age,
                  lat=float(raw.get("latitude", math.nan)), lon=float(raw.get("longitude", math.nan)),
                  elevation=raw.get("elevation"), raw=raw)
    if n_drop:
        fc.notes.append("%d trailing null hours at the horizon end dropped" % n_drop)
    return fc


def _age_h_raw(fetched_at: str | None, now: datetime) -> float:
    if not fetched_at:
        return float("nan")
    try:
        t = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    except ValueError:
        return float("nan")
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (now - t).total_seconds() / 3600.0


def _age_h(fetched_at: str | None, now: datetime) -> float:
    """Age in hours, never negative (a future timestamp is clamped to 0 here; fetch() treats it as stale)."""
    a = _age_h_raw(fetched_at, now)
    return a if a != a else round(max(0.0, a), 2)


def attempt_path(lat: float, lon: float, cache_dir: str) -> str:
    return cache_path(lat, lon, cache_dir)[:-5] + ".attempt.json"


def _last_attempt_age_h(path: str, now: datetime) -> float:
    try:
        with open(path, encoding="utf-8") as f:
            a = _age_h_raw(json.load(f).get("attempted_at"), now)
    except (OSError, ValueError, AttributeError):
        return float("inf")
    return float("inf") if a != a or a < -FUTURE_TOL_H else a


def _write_attempt(path: str, now: datetime, result: str) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"attempted_at": now.astimezone(timezone.utc).isoformat(timespec="seconds"), "result": result}, f)
    except OSError:
        pass


def _read_cache(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _http_get(url: str, urlopen) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "heat-guardian-tomorrow/1"})
    with urlopen(req, timeout=TIMEOUT_S) as r:
        status = getattr(r, "status", 200)
        if status != 200:
            raise urllib.error.HTTPError(url, status, "HTTP %s" % status, None, None)
        return json.loads(r.read().decode("utf-8"))


def fetch(lat: float, lon: float, cache_dir: str, now: datetime | None = None,
          _urlopen=None, _sleep=None) -> Forecast:
    """One nightly fetch with cache + single retry. See module docstring for the rules.

    ``_urlopen`` / ``_sleep`` are injection points for the tests (no network in tests).
    """
    urlopen = urllib.request.urlopen if _urlopen is None else _urlopen
    sleep = time.sleep if _sleep is None else _sleep
    now = now or datetime.now(timezone.utc)
    os.makedirs(cache_dir, exist_ok=True)
    path = cache_path(lat, lon, cache_dir)
    cached = _read_cache(path)
    apath = attempt_path(lat, lon, cache_dir)

    if cached is not None:
        raw_age = _age_h_raw(cached.get("fetched_at"), now)
        if raw_age < -FUTURE_TOL_H:
            note = "cache fetched_at is %.1f h in the future (clock error): treated as stale" % -raw_age
        elif raw_age < CACHE_FRESH_H:
            fc = parse(cached, "cache", cached.get("fetched_at"), now)
            fc.notes.append("cache < %g h old: no call made" % CACHE_FRESH_H)
            return fc
        else:
            note = None
    else:
        note = None

    last = _last_attempt_age_h(apath, now)
    if last < BACKOFF_H:                       # a call was already made tonight (e.g. it failed): do not call again
        if cached is None:
            raise ForecastUnavailable("last Open-Meteo attempt %.1f h ago (backoff %g h) and no cache" % (last, BACKOFF_H))
        fc = parse(cached, "cache", cached.get("fetched_at"), now)
        fc.notes.append("backoff: last attempt %.1f h ago (< %g h), no call made" % (last, BACKOFF_H))
        if note:
            fc.notes.append(note)
        return fc

    url = build_url(lat, lon)
    errors = []
    _write_attempt(apath, now, "started")
    for attempt in (0, 1):                      # attempt 1 is the single retry; no loop beyond it
        if attempt == 1:
            sleep(RETRY_WAIT_S)
        try:
            raw = _http_get(url, urlopen)
            if "hourly" not in raw:
                raise ValueError("response has no 'hourly' block: %s" % str(raw)[:120])
            raw["fetched_at"] = now.astimezone(timezone.utc).isoformat(timespec="seconds")
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False)
            os.replace(tmp, path)
            _write_attempt(apath, now, "ok")
            return parse(raw, "open-meteo", raw["fetched_at"], now)
        except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as e:
            # HTTPError ⊂ URLError (429 here); IncompleteRead ⊂ HTTPException (truncated body)
            errors.append("%s: %s" % (type(e).__name__, getattr(e, "code", "") or e))

    _write_attempt(apath, now, "failed: " + "; ".join(errors)[:200])
    if cached is None:
        raise ForecastUnavailable("Open-Meteo failed twice (%s) and no cache at %s" % ("; ".join(errors), path))
    fc = parse(cached, "cache", cached.get("fetched_at"), now)
    fc.notes.append("live call failed (%s); using cached forecast" % "; ".join(errors))
    return fc
