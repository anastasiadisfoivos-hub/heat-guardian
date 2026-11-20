"""Tomorrow for one city: the Heat Guardian Tomorrow Engine (B4, unchanged) run for the simulated elder
(default: Virtual Elder pid 90862, the demo elder, with the Body Twin learned over 7 simulated days:
twin_learned_pid90862.json; --pid 90416 = the older b7s person) on a city's real Open-Meteo forecast, written as tomorrow_plan.json for the demo page.

SIMULATION. Physics-based planning on a simulated person, not a medical prediction.
Weather data by Open-Meteo.com (CC BY 4.0).

This file is a thin wrapper. It changes nothing in the engine's physics. It changes two things around it:
  1. the forecast is asked in the city's own local time (timezone=auto instead of Europe/Athens), so hour 0..23
     of the plan is the city's midnight..23:00;
  2. if api.open-meteo.com refuses (for example 429, daily limit), the same forecast is asked once from
     Open-Meteo's previous-runs-api.open-meteo.com host (same models, same variables).
The engine's own rules stay: a cache younger than 20 h is reused without a call; one retry per host.

  python3 run_city.py                         # Alice Springs (default)
  python3 run_city.py --city durban
  python3 run_city.py --lat -25.26 --lon -57.58 --name "Asuncion" --country Paraguay
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("HG_SIM_DIR", HERE)          # the bundled velders body model (physics.py looks here)

from tomorrow import openmeteo, cli, indoor         # noqa: E402

CITIES = {   # name, country, lat, lon
    "alice-springs": ("Alice Springs", "Australia", -23.70, 133.88),
    "asuncion": ("Asunción", "Paraguay", -25.26, -57.58),
    "durban": ("Durban", "South Africa", -29.86, 31.02),
    "brisbane": ("Brisbane", "Australia", -27.47, 153.03),
    "perth": ("Perth", "Australia", -31.95, 115.86),
    "adelaide": ("Adelaide", "Australia", -34.93, 138.60),
    "cordoba": ("Córdoba", "Argentina", -31.42, -64.18),
}
HOSTS = ["api.open-meteo.com", "previous-runs-api.open-meteo.com"]
DEFAULT_PID = 90862                              # the demo elder (firmware 0.9.17-demo-b7t and later)


def twin_path(pid: int) -> str:
    """The Body Twin learned over 7 simulated days (twin_learned_pid<id>.json, made by tools/make_twin_week.py) when it
    exists, else the drawn profile (twin_pid<id>.json)."""
    learned = os.path.join(HERE, "twin_learned_pid%d.json" % pid)
    return learned if os.path.isfile(learned) else os.path.join(HERE, "twin_pid%d.json" % pid)

_engine_build_url = openmeteo.build_url
_engine_fetch = openmeteo.fetch
_used = {"host": None}


def _url_for(host):
    def build(lat, lon):
        u = _engine_build_url(lat, lon)
        return u.replace("https://api.open-meteo.com/", "https://%s/" % host, 1).replace(
            "timezone=Europe%2FAthens", "timezone=auto")
    return build


def _fetch(lat, lon, cache_dir, **kw):
    """The engine's fetch, tried on each host in turn. A fresh cache returns at once (no call)."""
    openmeteo.RETRY_WAIT_S = 5.0
    fc, err = None, None
    for host in HOSTS:
        openmeteo.build_url = _url_for(host)
        try:
            fc = _engine_fetch(lat, lon, cache_dir, **kw)
        except openmeteo.ForecastUnavailable as e:
            fc, err = None, e
        if fc is not None and not any("live call failed" in n or n.startswith("backoff") for n in fc.notes):
            _used["host"] = host if fc.source == "open-meteo" else (_used["host"] or "cache")
            return fc
        try:                                     # this host failed: let the next host make its one call
            os.remove(openmeteo.attempt_path(lat, lon, cache_dir))
        except OSError:
            pass
    if fc is not None:
        _used["host"] = "cache"
        return fc
    raise err


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Tomorrow plan for the simulated elder in a hot city (SIMULATION)")
    ap.add_argument("--city", default="alice-springs", help="one of: " + ", ".join(CITIES))
    ap.add_argument("--lat", type=float); ap.add_argument("--lon", type=float)
    ap.add_argument("--name", help="city name shown on the page (with --lat/--lon)")
    ap.add_argument("--country", default="")
    ap.add_argument("--pid", type=int, default=DEFAULT_PID,
                    help="Virtual Elder id; needs tomorrow_engine/twin_pid<id>.json (default %d)" % DEFAULT_PID)
    ap.add_argument("--home-class", default="C", choices=list("ABCD"))
    ap.add_argument("--no-fan", action="store_true", help="her drawn profile has a fan; this removes it")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: tomorrow in the city)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "tomorrow_plan.json"))
    ap.add_argument("--cache-dir", default=os.path.join(os.path.expanduser("~"), ".hgtomorrow", "cache"))
    a = ap.parse_args(argv)

    if a.lat is not None or a.lon is not None:
        if a.lat is None or a.lon is None:
            ap.error("give both --lat and --lon")
        name, country, lat, lon = a.name or "%.2f, %.2f" % (a.lat, a.lon), a.country, a.lat, a.lon
    else:
        key = a.city.lower().replace(" ", "-")
        if key not in CITIES:
            ap.error("unknown city %r; use one of %s, or --lat/--lon" % (a.city, ", ".join(CITIES)))
        name, country, lat, lon = CITIES[key]

    TWIN = twin_path(a.pid)
    if not os.path.isfile(TWIN):
        ap.error("no twin file %s (make it with velders draw_one, see README.txt)" % TWIN)
    with open(TWIN, encoding="utf-8") as f:
        twin = json.load(f)
    openmeteo.fetch = _fetch
    tmp = a.out + ".tmp"
    args = ["--lat", str(lat), "--lon", str(lon), "--home-class", a.home_class, "--twin", TWIN,
            "--out", tmp, "--cache-dir", a.cache_dir,
            "--urban-offset", "0", "0"]          # the grid cell is the town itself (see README.txt)
    if not a.no_fan:
        args.append("--fan")
    if a.date:
        args += ["--date", a.date]
    rc = cli.main(args)
    if rc != 0:
        print("FAILED: the engine made no plan (exit %d)" % rc, file=sys.stderr)
        return rc

    with open(tmp, encoding="utf-8") as f:
        plan = json.load(f)
    with open(openmeteo.cache_path(lat, lon, a.cache_dir), encoding="utf-8") as f:
        raw = json.load(f)
    d = raw.get("daily", {})
    i = d.get("time", []).index(plan["date"]) if plan["date"] in d.get("time", []) else None
    pick = (lambda k: d[k][i] if i is not None and k in d else None)
    plan["display"] = {
        "city": name, "country": country, "lat": lat, "lon": lon,
        "grid_lat": raw.get("latitude"), "grid_lon": raw.get("longitude"), "elevation_m": raw.get("elevation"),
        "timezone": raw.get("timezone"), "timezone_abbreviation": raw.get("timezone_abbreviation"),
        "forecast_tmax": pick("temperature_2m_max"), "forecast_tmin": pick("temperature_2m_min"),
        "forecast_apparent_tmax": pick("apparent_temperature_max"),
        "fetched_at": raw.get("fetched_at"), "api_host": raw.get("api_host") or _used["host"],
        "person": "Simulated person: a %d-year-old %s (Virtual Elder pid %d)"
                  % (int(twin["age"]), "man" if twin.get("sex_m") else "woman", a.pid),
        "home": indoor.CLASSES[a.home_class].name, "fan": not a.no_fan, "urban_offset": [0.0, 0.0],
        "made_by": "tomorrow_engine/run_city.py (Tomorrow Engine B4, unchanged physics)",
    }
    if _used["host"] in HOSTS:                   # remember which host answered, for the page's footnote
        raw["api_host"] = _used["host"]
        with open(openmeteo.cache_path(lat, lon, a.cache_dir), "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False)
        plan["display"]["api_host"] = _used["host"]
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)
    os.replace(tmp, a.out)
    risky = [h["h"] for h in plan["hours"] if h["advice"] == "AVOID"]
    print("OK  %s written: %s %s, forecast max %s °C, risky hours %s. Reload the page and click Tomorrow."
          % (os.path.basename(a.out), name, plan["date"], plan["display"]["forecast_tmax"],
             ("%02d:00-%02d:00" % (risky[0], risky[-1] + 1)) if risky else "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
