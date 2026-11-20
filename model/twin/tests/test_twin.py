"""Python-side unit tests for the Body Twin reference (run: python3 -m pytest -q twin/tests or python3 twin/tests/test_twin.py)."""
import math
import os
import sys
import zlib

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from hg_twin import BodyTwin, FIXED_LEN  # noqa: E402


def _bounded(t):
    p = t.params
    ok = 40 <= p["rest_hr"] <= 100 and 0.03 <= p["k_person"] <= 0.40 and -0.8 <= p["core_offset"] <= 0.8 and 0 <= p["c_bodyheat"] <= 0.4
    b = p["t1_night_base"]
    return ok and all(math.isnan(x) or 25 <= x <= 42 for x in b) and all(math.isfinite(p[k]) for k in ("rest_hr", "k_person", "core_offset", "c_bodyheat"))


def test_roundtrip_and_crc():
    t = BodyTwin(); t.params["rest_hr"] = np.float32(61.5); t.t1_n[3] = 2; t.t1_pre_cd[3] = 3412
    blob = t.to_bytes(b"\x01\x02\x03", save_count=7)
    assert len(blob) == FIXED_LEN + 3
    assert zlib.crc32(blob[:-4]) == int.from_bytes(blob[-4:], "little")
    t2, r, sc, ok = BodyTwin.from_bytes(blob)
    assert ok and r == b"\x01\x02\x03" and sc == 7 and t2.to_bytes(r, sc) == blob


def test_corrupt_gives_defaults():
    blob = bytearray(BodyTwin().to_bytes(bytes(624), 3))
    for i in range(0, len(blob), 7):
        b = bytearray(blob); b[i] ^= 0x10
        t, r, sc, ok = BodyTwin.from_bytes(bytes(b))
        assert not ok and t.params["rest_hr"] == np.float32(70) and r == b"" and sc == 0


def test_decay_half_life():
    t = BodyTwin(); t.params["core_offset"] = np.float32(0.4)
    t.nightly_update(); t.nightly_update()
    assert abs(float(t.params["core_offset"]) / 0.4 - 0.5) < 1e-6
    assert t.last_frozen == 2 and t.params["days_learned"] == 0


def test_fuzz_bounds():
    rng = np.random.default_rng(5); t = BodyTwin()
    wild = lambda lo, hi: rng.choice([np.nan, np.inf, -np.inf, rng.uniform(-1e30, 1e30), rng.uniform(lo, hi), rng.uniform(lo, hi)])
    for i in range(5000):
        t.ingest_minute(dict(t1_c=wild(25, 40), t2_c=wild(20, 38), t_air_c=wild(15, 40), hr_bpm=wild(35, 120), a_std_g=wild(0, 0.004),
                             worn=int(rng.integers(0, 4)), minute_of_day=int(rng.integers(0, 1600)), asleep=int(rng.integers(0, 2)),
                             location=int(rng.integers(0, 3)), hr_valid=int(rng.integers(0, 2)), tier_on=int(rng.random() < 0.02),
                             air_ref=wild(15, 40)))
        if rng.random() < 0.005:
            t.ingest_reading(wild(35, 39), 0, wild(30, 37), wild(-1, 6), wild(35, 39), int(rng.integers(0, 2))); t.commit_reading()
        if rng.random() < 0.007:
            t.nightly_update()
        assert _bounded(t)


def test_no_K_without_reading_and_no_K_without_flux():
    t = BodyTwin()
    for d in range(4):
        for i in range(1440):
            tod = (210 + i) % 1440
            t.ingest_minute(dict(t1_c=33.5, t2_c=31.0, t_air_c=24.0, hr_bpm=55.0, a_std_g=0.001, worn=2, minute_of_day=tod,
                                 asleep=int(tod >= 1380 or tod < 420), location=0, hr_valid=1))
        t.nightly_update()
    assert t.params["k_person"] == np.float32(0.12) and t.params["core_offset"] == 0
    t.ingest_reading(37.0, 0, 33.5, float("nan"), 36.8, 0); t.commit_reading()
    assert t.params["k_person"] == np.float32(0.12)
    assert abs(float(t.params["rest_hr"]) - (70 + (60 - 70) * (1 - 0.7 ** 4))) < 0.6   # p10 of a flat 55 -> 55.x + 5


if __name__ == "__main__":
    for k, fn in list(globals().items()):
        if k.startswith("test_"):
            fn(); print("ok", k)
