"""Writes ble_vectors.json: fixed, physics-independent 0x11/0x14 frames for B5's C parser test.
Run: python -I -m tomorrow.tests.make_vectors   (or python make_vectors.py from this folder)."""
import json
import os

from tomorrow import ble_frame as bf

HERE = os.path.dirname(os.path.abspath(__file__))


def fixed_plan():
    t_in = [30.4, 30.1, 29.6, 29.2, 28.9, 28.6, 28.5, 28.7, 29.4, 30.2, 31.0, 31.8,
            32.5, 33.1, 33.6, 33.9, 34.0, 33.8, 33.4, 32.9, 32.3, 31.7, 31.1, -3.6]   # -3.6: sign test
    rh_in = [48, 49, 50, 51, 52, 53, 53, 52, 49, 45, 41, 37, 33, 30, 28, 27, 27, 28, 30, 33, 36, 39, 42, 100]
    safe = [h in (5, 6, 7, 21, 22) for h in range(24)]
    return {"date": "2026-07-14", "home_class": "B", "heat_day": True, "night_heat": False,
            "hours": [{"h": h, "t_in": t_in[h], "rh_in": rh_in[h], "safe": safe[h]} for h in range(24)]}


def main():
    p = fixed_plan()
    fr = bf.forecast_chunks(p)
    sh = bf.safe_hours_frame(p)
    out = {"layout": bf.__doc__, "plan": p,
           "forecast_chunks_hex": [f.hex() for f in fr],
           "decoded_hours": bf.decode_forecast(fr)["hours"],
           "safe_hours_hex": sh.hex(), "safe_hours_bitmap": bf.safe_bitmap(p),
           "plan_id": bf.plan_id(p["date"]), "tag": "2026-07-14 B"}
    with open(os.path.join(HERE, "ble_vectors.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(out["forecast_chunks_hex"], out["safe_hours_hex"])


if __name__ == "__main__":
    main()
