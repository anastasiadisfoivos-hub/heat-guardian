"""[T3] shared helpers: build the builder's C (unchanged) with the brief's flags, ctypes mirror, event writer, Python replay."""
import ctypes as C
import math
import os
import subprocess
import sys

import numpy as np

TW = "/home/claude/hg_ai/twin"
SRC = TW + "/c"
HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
sys.path.insert(0, TW)
from hg_twin import BodyTwin  # noqa: E402

f32 = np.float32
# exactly the flags in the B3 brief / ARCHITECTURE 4.5 (the builder's Makefile adds -ffp-contract=off etc.)
BRIEF_FLAGS = ["-std=c99", "-Wall", "-Wextra", "-Werror", "-Wdouble-promotion", "-fsingle-precision-constant"]
COLS = ["t1_c", "t2_c", "t_air_c", "rh_pct", "hr_bpm", "hr_quality", "pi_pct", "a_std_g", "worn", "minute_of_day",
        "asleep", "location", "hr_valid", "tier_on", "air_ref"]
INTC = {"hr_quality", "worn", "minute_of_day", "asleep", "location", "hr_valid", "tier_on"}


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(" ".join(cmd) + "\n" + r.stdout + r.stderr)
    return r.stdout + r.stderr


def build_driver(tag="O2", extra=("-O2",)):
    os.makedirs(BUILD, exist_ok=True)
    out = os.path.join(BUILD, f"t3_driver_{tag}")
    sh(["gcc", *BRIEF_FLAGS, *extra, "-I", SRC, "-o", out, os.path.join(HERE, "t3_driver.c"), SRC + "/hg_twin.c", "-lm"])
    return out


def build_lib():
    os.makedirs(BUILD, exist_ok=True)
    out = os.path.join(BUILD, "libhgtwin.so")
    sh(["gcc", *BRIEF_FLAGS, "-O2", "-fPIC", "-shared", "-o", out, SRC + "/hg_twin.c", "-lm"])
    return C.CDLL(out)


class Twin(C.Structure):
    _fields_ = [("rest_hr", C.c_float), ("k_person", C.c_float), ("core_offset", C.c_float), ("c_bodyheat", C.c_float),
                ("t1_night_base", C.c_float * 24), ("days_learned", C.c_uint8)]


class In(C.Structure):
    _fields_ = [("t1_c", C.c_float), ("t2_c", C.c_float), ("t_air_c", C.c_float), ("rh_pct", C.c_float),
                ("hr_bpm", C.c_float), ("hr_quality", C.c_uint8), ("pi_pct", C.c_float), ("a_std_g", C.c_float),
                ("worn", C.c_uint8), ("minute_of_day", C.c_uint16)]


class Acc(C.Structure):
    _fields_ = [("t1_n", C.c_uint8 * 24), ("t1_pre_cd", C.c_int16 * 24), ("hist", C.c_uint8 * 64), ("hist_n", C.c_uint16),
                ("today_cd", C.c_int16 * 24), ("cur_sum", C.c_float), ("cur_cnt", C.c_uint8), ("cur_h", C.c_uint8),
                ("c_sxx", C.c_float), ("c_sxy", C.c_float), ("c_w", C.c_float), ("air_ref", C.c_float),
                ("night_n", C.c_uint16), ("night_bad", C.c_uint16), ("night_alarm", C.c_uint8), ("tier_now", C.c_uint8),
                ("rd_pending", C.c_uint8), ("rd_flux", C.c_uint8), ("rd_t_read", C.c_float), ("rd_t1", C.c_float),
                ("rd_dT", C.c_float), ("rd_core", C.c_float), ("last_frozen", C.c_uint8)]


def setup_lib(lib):
    P = C.POINTER
    lib.hg_twin_crc32.restype = C.c_uint32
    lib.hg_twin_crc32.argtypes = [C.c_uint32, C.c_void_p, C.c_uint32]
    lib.hg_twin_unpack.argtypes = [C.c_char_p, C.c_uint16, P(Twin), P(Acc), C.c_void_p, C.c_uint16, P(C.c_uint16), P(C.c_uint32)]
    lib.hg_twin_pack.argtypes = [P(Twin), P(Acc), C.c_void_p, C.c_uint16, C.c_uint32, C.c_void_p, C.c_uint16]
    lib.hg_twin_ingest_minute.argtypes = [P(Acc), P(In), C.c_uint8, C.c_uint8, C.c_uint8]
    lib.hg_twin_ingest_reading.argtypes = [P(Acc), C.c_float, C.c_float, C.c_float, C.c_float, C.c_uint8]
    lib.hg_twin_commit_reading.argtypes = [P(Twin), P(Acc)]
    lib.hg_twin_nightly_update.argtypes = [P(Twin), P(Acc)]
    lib.hg_twin_note_tier.argtypes = [P(Acc), C.c_uint8]
    lib.hg_twin_set_air_ref.argtypes = [P(Acc), C.c_float]
    lib.hg_twin_defaults.argtypes = [P(Twin)]
    lib.hg_twin_acc_init.argtypes = [P(Acc)]
    return lib


def fmt(v):
    v = float(v)
    if math.isnan(v):
        return "nan"
    if math.isinf(v):
        return "inf" if v > 0 else "-inf"
    return repr(v)


def write_events(ev, path):
    """ev: list of dicts kind in m/r/q/u/P. Floats are cast to float32 FIRST, so C and Python see the same value."""
    rows = []
    with open(path, "w") as fh:
        for e in ev:
            k = e["kind"]
            vals = []
            for c in COLS:
                v = e.get(c, 0 if c in INTC else np.nan)
                vals.append(str(int(v)) if c in INTC else fmt(f32(v)))
            r = [fmt(f32(e.get(f"r{i}", np.nan))) for i in range(4)] + [str(int(e.get("r4", 0)))]
            fh.write(k + "," + ",".join(vals + r) + "\n")
            rows.append(e)
    return path


def py_replay(ev):
    """Replay with the builder's Python reference, from the same float32 values the CSV carries."""
    tw = BodyTwin()
    out = []
    for e in ev:
        k = e["kind"]
        if k == "m":
            m = {c: (int(e.get(c, 0)) if c in INTC else f32(e.get(c, np.nan))) for c in COLS}
            tw.ingest_minute(m)
        elif k == "r":
            tw.ingest_reading(f32(e.get("r0", np.nan)), 0, f32(e.get("r1", np.nan)), f32(e.get("r2", np.nan)),
                              f32(e.get("r3", np.nan)), int(e.get("r4", 0)))
            r = tw.commit_reading()
            out.append(("R", r, float(tw.params["k_person"]), float(tw.params["core_offset"])))
        elif k == "q":
            tw.ingest_room_reading(f32(e.get("r0", np.nan)), f32(e.get("r1", np.nan)), f32(e.get("r2", np.nan)))
        elif k == "u":
            ch = tw.nightly_update()
            out.append(("U", tw.changed_flag(ch), tw.last_frozen, *tw.params_vector(),
                        *[int(x) for x in tw.t1_n], *[int(x) for x in tw.t1_pre_cd]))
        elif k == "P":
            rout = bytes(((i * 31 + 7) & 255) for i in range(650))
            out.append(("H", tw.to_bytes(rout, save_count=77).hex()))
    return tw, out


def c_replay(driver, csv_path):
    txt = subprocess.run([driver, csv_path], capture_output=True, text=True, check=True).stdout
    out = []
    for line in txt.strip().splitlines():
        p = line.split(",")
        if p[0] == "U":
            out.append(("U", int(p[1]), int(p[2]), *[float(x) for x in p[3:32]], *[int(x) for x in p[32:]]))
        elif p[0] == "R":
            out.append(("R", int(p[1]), float(p[2]), float(p[3])))
        elif p[0] == "H":
            out.append(("H", p[2]))
    return out


def compare(py, c):
    """Returns (max abs diff over float params, list of mismatch descriptions)."""
    bad = []; mx = 0.0
    if len(py) != len(c):
        return float("inf"), [f"length py={len(py)} c={len(c)}"]
    for i, (a, b) in enumerate(zip(py, c)):
        if a[0] != b[0]:
            bad.append(f"{i}: kind {a[0]} vs {b[0]}"); continue
        if a[0] == "H":
            if a[1] != b[1]:
                bad.append(f"{i}: packed file differs")
            continue
        if a[0] == "R":
            fl = [(2, a[2], b[2]), (3, a[3], b[3])]; ints = [(1, a[1], b[1])]
        else:
            fl = [(j, a[j], b[j]) for j in range(3, 32)]; ints = [(j, a[j], b[j]) for j in (1, 2)] + [(j, a[j], b[j]) for j in range(32, 80)]
        for j, x, y in fl:
            if math.isnan(x) or math.isnan(y):
                if not (math.isnan(x) and math.isnan(y)):
                    bad.append(f"{i}: field {j} py={x} c={y}")
                continue
            d = abs(x - y); mx = max(mx, d)
            if d > 1e-5:
                bad.append(f"{i}: field {j} py={x!r} c={y!r} d={d:.3g}")
        for j, x, y in ints:
            if int(x) != int(y):
                bad.append(f"{i}: int field {j} py={x} c={y}")
    return mx, bad
