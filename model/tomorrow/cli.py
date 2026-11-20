"""Command line: python -m tomorrow --lat 37.98 --lon 23.73 --home-class B --twin twin.json --out plan.json
                [--demo] [--ble-out frames.bin] [--date YYYY-MM-DD] [--cache-dir DIR] [--fan]
                [--urban-offset NIGHT DAY] [--routine-profile profile.bin]
--demo never touches the network. Without --demo: one Open-Meteo call at most (cache < 20 h → none)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import jsonschema

from . import plan as planmod, openmeteo, demo
from .routine import RoutineTemplate

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, "schema.json")


def validate(plan: dict) -> None:
    with open(SCHEMA, encoding="utf-8") as f:
        jsonschema.validate(plan, json.load(f))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tomorrow", description=__doc__.splitlines()[0])
    ap.add_argument("--lat", type=float, default=37.98)
    ap.add_argument("--lon", type=float, default=23.73)
    ap.add_argument("--home-class", default="B", choices=list("ABCD"))
    ap.add_argument("--twin", default=None, help="twin/profile JSON (default: 'Maria, 78')")
    ap.add_argument("--out", default="plan.json")
    ap.add_argument("--demo", action="store_true", help="constructed Athens heat-wave day, offline")
    ap.add_argument("--ble-out", default=None, help="write the 5 BLE frames (4 x 0x11 + 0x14) concatenated")
    ap.add_argument("--date", default=None, help="plan date (default: tomorrow, Europe/Athens)")
    ap.add_argument("--cache-dir", default=os.path.join(HERE, "cache"))
    ap.add_argument("--fan", action="store_true", help="home has a fan")
    ap.add_argument("--urban-offset", nargs=2, type=float, default=None, metavar=("NIGHT", "DAY"))
    ap.add_argument("--routine-profile", default=None, help="band 576-B routine profile file")
    a = ap.parse_args(argv)

    twin = planmod.default_twin()
    if a.twin:
        with open(a.twin, encoding="utf-8") as f:
            twin.update(json.load(f))
    routine = RoutineTemplate.default()
    if a.routine_profile:
        with open(a.routine_profile, "rb") as f:
            routine = RoutineTemplate.from_band(f.read())

    if a.demo:
        fc = demo.demo_forecast()
        date = demo.DEMO_DATE
    else:
        fc = openmeteo.fetch(a.lat, a.lon, a.cache_dir)
        if a.date:
            date = a.date
        else:
            # Europe/Athens is UTC+2/+3; the forecast's own offset is in the response
            off = int(fc.raw.get("utc_offset_seconds", 7200))
            date = (datetime.now(timezone.utc) + timedelta(seconds=off) + timedelta(days=1)).date().isoformat()

    state_path = None if a.demo else os.path.join(
        a.cache_dir, "indoor_state_%.2f_%.2f_%s.json" % (a.lat, a.lon, a.home_class))
    state = None
    if state_path and os.path.exists(state_path):
        try:
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, ValueError):
            state = None
    try:
        p = planmod.make_plan(fc, date, a.home_class, twin, routine, fan_available=a.fan,
                              urban_offset=tuple(a.urban_offset) if a.urban_offset else None, indoor_state=state)
    except ValueError as e:                      # e.g. a cache older than the 16-day horizon
        print("NO PLAN: %s" % e, file=sys.stderr)
        return 3
    validate(p)
    if state_path:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(p["details"]["indoor_state"], f)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=1)
    if a.ble_out:
        with open(a.ble_out, "wb") as f:
            for hx in p["ble"]["forecast_chunks_hex"] + [p["ble"]["safe_hours_hex"]]:
                f.write(bytes.fromhex(hx))
    adv = "".join({"OK": "o", "SHORT": "s", "AVOID": "X"}[h["advice"]] for h in p["hours"])
    print("%s %s source=%s heat_day=%s night_heat=%s wave_day=%d hours[00..23]=%s"
          % (p["date"], a.home_class, p["source"], p["heat_day"], p["night_heat"], p["wave_day"], adv))
    for s in p["advice_gr"]:
        print("  " + s)
    print("  " + " | ".join(p["labels"]))
    print("  " + p["attribution"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
