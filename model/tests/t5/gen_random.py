#!/usr/bin/env python3
"""T5 (tester) - my own random minute-sequence generator for the full Guardian Loop (C replay vs Python mirror).
Independent of the builder's generators (host_test.c property_tests, trace_gen.py). Every value is rounded to float32
up front so the C (strtof) and the Python mirror see the same number.
Covers: NaN / +-inf / 1e30 / out-of-range / exact range edges on every float field, clock jumps (forward/back), time
unknown (0xFFFF and other >= 1440 values), long gaps (mod jumps of 5-50 h), sensor blackouts, forced worn/loose/off,
charging, button storms (short/long mixes), FAMILY_ACK with near-right ids, PROFILE commands incl. NaN, FORECAST chunks
(good, bad CRC, mismatched chunk ids), garbage frames, low battery, impacts.
Usage: imported by run_diff.py (seq(i) -> (name, profile, twin, minutes))."""
import os, sys, struct
import numpy as np
sys.path.insert(0, "/home/claude/hg_ai/guardian/py")
from trace_io import minute
from hg_guardian_py import cmd_frame, crc8

F32 = lambda v: float(np.float32(v))
NAN = float("nan"); INF = float("inf")
SEED0 = 515151

def _bad(rng, lo, hi):
    c = rng.integers(0, 10)
    return [NAN, INF, -INF, 1e30, -1e30, hi + 50.0, lo - 50.0, lo, hi, F32(np.nextafter(np.float32(hi), np.float32(1e9)))][c]

def seq(i, max_len=None):
    rng = np.random.default_rng(SEED0 + i)
    # ---- length: 70 % short, 25 % medium, 5 % long (multi-day for the noon/HDCZA path)
    u = rng.random()
    n = int(rng.integers(20, 120)) if u < 0.70 else int(rng.integers(120, 400)) if u < 0.95 else int(rng.integers(400, 1500))
    if i % 1000 == 999: n = 4 * 1440 + int(rng.integers(0, 600))    # 10 four-day sequences
    if max_len: n = min(n, max_len)
    # ---- profile / twin (float32-exact)
    age = [F32(rng.uniform(18, 100)), 65.0, F32(np.nextafter(np.float32(65), np.float32(0))), 64.0, 99.0][int(rng.integers(0, 5))]
    prof = dict(age=age, sex_m=float(rng.integers(0, 2)), bmi=F32(rng.uniform(15, 45)), med_flags=int(rng.integers(0, 16)))
    nb = [NAN] * 24
    if rng.random() < 0.5: nb = [F32(rng.uniform(32, 36.5)) if rng.random() < 0.8 else NAN for _ in range(24)]
    twin = dict(rest_hr=F32(rng.uniform(40, 100)), k_person=F32(rng.uniform(0.03, 0.40)), core_offset=F32(rng.uniform(-0.8, 0.8)),
                c_bodyheat=F32(rng.uniform(0.0, 0.4)) if rng.random() < 0.8 else 0.0, t1_night_base=nb)
    regime = ["calm", "heat", "exert", "chaos", "heat"][int(rng.integers(0, 5))]
    ta = rng.uniform(18, 30) if regime == "calm" else rng.uniform(30, 45) if regime == "heat" else rng.uniform(20, 40)
    rh = rng.uniform(5, 95); hr = rng.uniform(55, 80) if regime == "calm" else rng.uniform(80, 150)
    t1 = rng.uniform(33, 35.5) if regime == "calm" else rng.uniform(34.5, 37.5)
    t2off = rng.uniform(0.0, 2.0); has_t2 = rng.random() < 0.7
    mod = 0xFFFF if rng.random() < 0.15 else int(rng.integers(0, 1440))
    blackout = 0; storm = 0; charging = 0; forced = 0xFF; forced_left = 0; flat = 0
    mins = []
    for r in range(n):
        # ---- clock: jumps, unknown stretches, long gaps
        x = rng.random()
        if x < 0.003: mod = int(rng.integers(0, 1440))                                       # jump (either direction)
        elif x < 0.005: mod = 0xFFFF                                                          # sync lost
        elif x < 0.006: mod = int(rng.integers(1440, 65535))                                  # junk >= 1440
        elif x < 0.008 and mod < 1440: mod = (mod + int(rng.integers(300, 3000))) % 1440      # long gap (minutes skipped)
        elif x < 0.010 and mod >= 1440: mod = int(rng.integers(0, 1440))                      # re-sync
        # ---- slow drifts
        ta += rng.normal(0, 0.15); ta = min(max(ta, 10.0), 50.0)
        rh += rng.normal(0, 1.0); rh = min(max(rh, 2.0), 99.0)
        hr += rng.normal(0, 3.0) + (0.3 if regime in ("heat", "exert") and hr < 140 else 0.0); hr = min(max(hr, 35.0), 210.0)
        t1 += rng.normal(0, 0.03) + (0.004 if regime == "heat" else 0.0); t1 = min(max(t1, 28.0), 40.0)
        if rng.random() < 0.002: blackout = int(rng.integers(10, 200))
        if rng.random() < 0.002: charging = int(rng.integers(5, 90))
        if forced_left <= 0 and rng.random() < 0.01: forced = [0, 1, 2, 2][int(rng.integers(0, 4))]; forced_left = int(rng.integers(3, 120))
        if forced_left > 0: forced_left -= 1
        else: forced = 0xFF
        if rng.random() < 0.003: flat = 1
        flat = min(flat + 1, 255) if flat else 0
        if rng.random() < 0.01: flat = 0
        # ---- one minute of sensors
        if regime == "calm": astd = [0.001, 0.008, 0.01, 0.05, 0.2][int(rng.integers(0, 5))]
        else: astd = [0.0015, 0.03, 0.1, 0.3, 0.002][int(rng.integers(0, 5))]
        astd = F32(astd * rng.uniform(0.5, 1.5)) if rng.random() < 0.7 else F32(astd)
        m = dict(mod=mod, t1=F32(t1), t2=F32(t1 - t2off) if has_t2 else NAN, tair=F32(ta), rh=F32(rh), hr=F32(hr),
                 hrq=4 if rng.random() < 0.8 else int(rng.integers(0, 6)), pi=F32(rng.uniform(0.0, 2.0)), astd=astd,
                 apeak=F32(rng.uniform(2.0, 5.0)) if rng.random() < 0.005 else 1.0, dc=100000 if rng.random() < 0.9 else int(rng.choice([0, 500, 19999, 20000, 4000000])),
                 flat=flat, charging=1 if charging else 0, vbat=F32(rng.uniform(3.25, 4.2)) if rng.random() < 0.97 else NAN,
                 ble=int(rng.integers(-1, 3)), force_worn=forced)
        if charging: charging -= 1
        if blackout:
            blackout -= 1
            for k in ("t1", "t2", "tair", "rh", "hr", "pi"): m[k] = NAN
            m["hrq"] = 0; m["dc"] = 0
        # ---- nonsense injection on each float field (~1 % each)
        for k, lo, hi in (("t1", -40, 85), ("t2", -40, 85), ("tair", -40, 85), ("rh", 0, 100), ("hr", 30, 220), ("pi", 0, 100),
                          ("astd", 0, 16), ("apeak", 0, 16), ("vbat", 3.0, 4.3)):
            if rng.random() < 0.01: m[k] = F32(_bad(rng, lo, hi))
        # ---- 5-s arrays (contact check) + z-angle
        jt = rng.normal(0, 0.02, 12)
        t1s = [F32(m["t1"] + j) if m["t1"] == m["t1"] and abs(m["t1"]) < 1e3 else m["t1"] for j in jt]
        t2s = [F32(m["t2"] + j) if m["t2"] == m["t2"] and abs(m["t2"]) < 1e3 else m["t2"] for j in jt]
        tas = [m["tair"]] * 12
        if rng.random() < 0.02:                                           # loose-band step inside the minute
            d = rng.uniform(0.5, 2.0); t1s = [F32(v - d) if v == v and abs(v) < 1e3 else v for v in t1s]
        for arr, lo, hi in ((t1s, -40, 85), (t2s, -40, 85), (tas, -40, 85)):
            for k in range(12):
                if rng.random() < 0.003: arr[k] = F32(_bad(rng, lo, hi))
        zs = [F32(rng.normal(0, 2 if astd < 0.01 else 25)) for _ in range(12)]
        if rng.random() < 0.01: zs[int(rng.integers(0, 12))] = [NAN, INF, -INF][int(rng.integers(0, 3))]
        # ---- buttons: storms, single presses, long presses
        if storm <= 0 and rng.random() < 0.01: storm = int(rng.integers(3, 20))
        if storm > 0: storm -= 1; b = int(rng.choice([0, 1, 2], p=[0.6, 0.38, 0.02]))
        else: b = 1 if rng.random() < 0.01 else (2 if rng.random() < 0.0007 else 0)
        # ---- phone commands
        cmd = None; y = rng.random()
        if y < 0.02:   # FAMILY_ACK, id with the right low-16 bits for an alarm raised k minutes ago (minute_counter = row + 1)
            low = (r + 1 - int(rng.integers(0, 40 if rng.random() < 0.6 else 600))) & 0xFFFF
            cmd = cmd_frame(0x12, ack_type=int(rng.integers(1, 4)), alarm_id=(int(rng.integers(1, 6)) << 16) | low)
        elif y < 0.023:
            v = [NAN, INF, F32(rng.uniform(30, 45)), F32(rng.uniform(30, 110)), F32(rng.uniform(-0.1, 0.5)), 34.0, 42.0, 40.0, 100.0, 0.4][int(rng.integers(0, 10))]
            cmd = cmd_frame(0x13, field=int(rng.integers(0, 6)), value=v)
        elif y < 0.026:
            ch = int(rng.integers(0, 4))
            hours = [(int(rng.integers(15, 45)), int(rng.integers(10, 90)), int(rng.integers(0, 8))) for _ in range(6)]
            cmd = cmd_frame(0x11, chunk=ch, hours=hours)
            if rng.random() < 0.2: cmd = cmd[:-1] + bytes([cmd[-1] ^ 0x55])                    # bad CRC
            elif rng.random() < 0.1: c2 = bytearray(cmd); c2[6] ^= 0x08; c2[19] = crc8(c2[:19]); cmd = bytes(c2)   # mixed chunk ids
        elif y < 0.027:
            cmd = bytes(rng.integers(0, 256, int(rng.integers(1, 25))).astype(np.uint8))         # garbage
        mm = minute(mod=m["mod"], t1=m["t1"], t2=m["t2"], tair=m["tair"], rh=m["rh"], hr=m["hr"], hrq=m["hrq"], pi=m["pi"],
                    astd=m["astd"], apeak=m["apeak"], dc=m["dc"], flat=m["flat"], button=b, charging=m["charging"], vbat=m["vbat"],
                    ble=m["ble"], force_worn=m["force_worn"], cmd=cmd, t1_5s=t1s, t2_5s=t2s, tair_5s=tas, zang=zs)
        mins.append(mm)
        if mod < 1440: mod = (mod + 1) % 1440
    return ("rnd%05d_%s" % (i, regime), prof, twin, mins)

if __name__ == "__main__":
    tot = 0
    for i in range(int(sys.argv[1]) if len(sys.argv) > 1 else 20):
        tot += len(seq(i)[3])
    print("minutes", tot)
