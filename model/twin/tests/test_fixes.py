"""[B3-fix] Regression tests for the T3 findings (tests/B3_TEST_REPORT.md). Each test failed on commit 39a6106
and passes after the fix; logs in twin/results/fix_tests_before.log / fix_tests_after.log.

Run: python3 /home/claude/hg_ai/twin/tests/test_fixes.py
"""
import os
import struct
import subprocess
import sys
import tempfile
import zlib

import numpy as np

TW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, TW)
import hg_twin as H  # noqa: E402
from hg_twin import BodyTwin  # noqa: E402
import sim_io  # noqa: E402

C_DIR = os.path.join(TW, "c")
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def _bounded(t):
    p = t.params
    ok = 40 <= p["rest_hr"] <= 100 and 0.03 <= p["k_person"] <= H.K_MAX and -0.8 <= p["core_offset"] <= 0.8 and 0 <= p["c_bodyheat"] <= 0.4
    return ok and all(np.isnan(x) or 25 <= x <= 42 for x in p["t1_night_base"])


def t_f1_seal_key():
    try:
        ids = sim_io.sealed_sim_ids()
        check("F1 seal key sealed_sim_person_ids read (100 ids)", len(ids) == 100)
    except Exception as e:  # noqa: BLE001
        check("F1 seal key sealed_sim_person_ids read (100 ids)", False, repr(e)[:80])
    old = sim_io.SEAL
    sim_io.SEAL = "/nonexistent/sealed_hg2.json"
    try:
        sim_io.sealed_sim_ids(); ok = False
    except sim_io.SealMissing:
        ok = True
    finally:
        sim_io.SEAL = old
    check("F1 missing seal still fails closed", ok)
    try:
        dm = sim_io.DevMinutes(["person_id", "day"], path="/home/claude/hg_ai/sim/data/minutes_dev.parquet")
        check("F1 minutes path is a parameter", dm is not None and len(dm.persons()) > 0)
    except TypeError as e:
        check("F1 minutes path is a parameter", False, str(e)[:80])


def stuck_twin(minutes=1000, nights=3):
    t = BodyTwin()
    for _ in range(nights):
        for i in range(1440):          # a normal night so the update is not frozen
            tod = (210 + i) % 1440
            t.ingest_minute(dict(t1_c=33.0, t_air_c=29.0, hr_bpm=55, a_std_g=0.001, worn=2, minute_of_day=tod,
                                 asleep=int(tod >= 1380 or tod < 420), location=0, hr_valid=1))
        for i in range(minutes):        # clock stuck at 03:20, qualifying minutes
            t.ingest_minute(dict(t1_c=33.0, t_air_c=24.0, hr_bpm=55, a_std_g=0.001, worn=2, minute_of_day=200,
                                 asleep=1, location=0, hr_valid=1))
        t.nightly_update()
    return t


def t_f2_stuck_clock():
    t = stuck_twin()
    b = float(t.params["t1_night_base"][3])
    check("F2 stuck clock: hour-3 baseline == true T1 33.0 and in bounds", abs(b - 33.0) < 0.006 and _bounded(t), f"base={b:.3f}")
    t = stuck_twin(3000, 1)
    check("F4 stuck 3000 min: centi-degree state stays in int16 and equals 3300", int(t.t1_pre_cd[3]) == 3300, f"pre={int(t.t1_pre_cd[3])}")
    check("F4 _cd clamps to int16", H._cd(np.float32(500.0)) == 32767 and H._cd(np.float32(-500.0)) == -32767)


def _file_with(n, pre, base=np.nan):
    t = BodyTwin()
    t.t1_n[5] = n; t.t1_pre_cd[5] = pre; t.params["t1_night_base"][5] = base
    body = bytearray(t.to_bytes(b"", 0))
    body[-4:] = struct.pack("<I", zlib.crc32(bytes(body[:-4])) & 0xFFFFFFFF)
    return bytes(body)


def t_f3_load_consistency():
    cases = {"n1_pre_none": (1, H.CD_NONE), "n0_pre_set": (0, 3300), "n2_pre_out_of_range": (2, -3), "n3_pre_set": (3, 3300)}
    for k, (n, pre) in cases.items():
        base = np.float32(33.0) if n >= 3 else np.nan
        _, _, _, ok = BodyTwin.from_bytes(_file_with(n, pre, base))
        check(f"F3 inconsistent learning state rejected on load ({k})", not ok)
    _, _, _, ok = BodyTwin.from_bytes(_file_with(2, 3310))
    check("F3 consistent n=2 state still accepted", ok)
    t = BodyTwin(); t.t1_n[5] = 1; t.t1_pre_cd[5] = H.CD_NONE
    t.nightly_update()
    check("F3 inconsistent RAM state reset by sanitize", t.t1_n[5] == 0 and t.t1_pre_cd[5] == H.CD_NONE)


def t_f6_golden_interior_k():
    import pandas as pd
    e = pd.read_parquet(os.path.join(TW, "tests", "golden_sourced_expected.parquet"))   # K moves only in sourced mode (M4.3)
    k = e.k_person.values
    check("F6 crafted golden has K strictly inside (0.03, 0.40) after a reading", bool(((k > 0.0301) & (k < 0.3999) & (np.abs(k - 0.12) > 1e-6)).any()),
          f"K values {sorted(set(np.round(k, 4)))}")


def t_f7_extern_c():
    with tempfile.TemporaryDirectory() as d:
        cpp = os.path.join(d, "x.cpp")
        open(cpp, "w").write('#include "hg_twin.h"\nint main(){hg2_twin_t t; hg_twin_defaults(&t); return t.rest_hr == 70.0f ? 0 : 1;}\n')
        r1 = subprocess.run(["gcc", "-std=c99", "-O2", "-c", os.path.join(C_DIR, "hg_twin.c"), "-o", os.path.join(d, "t.o")], capture_output=True)
        r2 = subprocess.run(["g++", "-O2", "-I", C_DIR, cpp, os.path.join(d, "t.o"), "-o", os.path.join(d, "x"), "-lm"], capture_output=True, text=True)
        ok = r1.returncode == 0 and r2.returncode == 0 and subprocess.run([os.path.join(d, "x")]).returncode == 0
        check("F7 hg_twin.h links from C++ (extern \"C\")", ok, r2.stderr.strip().splitlines()[-1][:80] if r2.returncode else "")


def t_f8_no_fma_on_arduino_flags():
    import glob
    g = sorted(glob.glob(os.path.expanduser("~/.arduino15/packages/Seeeduino/tools/arm-none-eabi-gcc/*/bin/arm-none-eabi-gcc")))
    if not g:
        check("F8 no vfma with Arduino gnu11 flags", False, "arm gcc not found"); return
    with tempfile.TemporaryDirectory() as d:
        o = os.path.join(d, "a.o")
        subprocess.run([g[0], "-std=gnu11", "-Os", "-mcpu=cortex-m4", "-mthumb", "-mfloat-abi=hard", "-mfpu=fpv4-sp-d16",
                        "-c", os.path.join(C_DIR, "hg_twin.c"), "-o", o], check=True)
        dis = subprocess.run([os.path.join(os.path.dirname(g[0]), "arm-none-eabi-objdump"), "-d", o], capture_output=True, text=True).stdout
        n = dis.count("vfma") + dis.count("vfms") + dis.count("vfnm")
        check("F8 no fused multiply-add in the band object (gnu11, as Arduino builds .c)", n == 0, f"{n} fused ops")


def t_bounds_after_every_update():
    rng = np.random.default_rng(9); t = BodyTwin(); bad = 0
    for night in range(30):
        stuck = rng.random() < 0.3
        for i in range(1440 if not stuck else 900):
            tod = 200 if stuck else (210 + i) % 1440
            t.ingest_minute(dict(t1_c=rng.uniform(25, 42), t_air_c=rng.uniform(15, 30), hr_bpm=rng.uniform(40, 104), a_std_g=0.001,
                                 worn=2, minute_of_day=tod, asleep=int(rng.random() < 0.5), location=0, hr_valid=1))
        t.nightly_update(); bad += not _bounded(t)
    check("F2 every parameter in bounds after every nightly update (30 nights, 30 % stuck clock)", bad == 0, f"{bad} bad")


if __name__ == "__main__":
    for fn in (t_f1_seal_key, t_f2_stuck_clock, t_f3_load_consistency, t_f6_golden_interior_k, t_f7_extern_c,
               t_f8_no_fma_on_arduino_flags, t_bounds_after_every_update):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            check(fn.__name__ + " raised", False, repr(e)[:100])
    nf = sum(1 for _, ok in results if not ok)
    print(f"RESULT: {len(results) - nf} pass, {nf} fail")
    sys.exit(1 if nf else 0)
