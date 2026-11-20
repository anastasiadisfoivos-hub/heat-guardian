"""[T3] Tester suite for B3 Body Twin. Run: python3 /home/claude/hg_ai/tests/B3/test_t3.py   (prints one line per test)
Every test is EXPECT-PASS or EXPECT-DEFECT: a DEFECT test asserts that the defect is reproduced (so the suite stays
green while documenting it); it flips to "FIXED?" when the builder's code changes behaviour.
SIMULATION checks that need sim/data/minutes_*.parquet are reported PENDING."""
import ctypes as C
import hashlib
import json
import math
import os
import sys
import tempfile
import time
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t3_common import (BodyTwin, Twin, In, Acc, build_driver, build_lib, setup_lib, write_events, py_replay, c_replay,
                       compare, f32, BUILD, TW)  # noqa: E402

RES = {}


def inb(t):
    """bounds compared in float32, as the C does (0.4f != 0.4 in double)."""
    F = lambda x: float(f32(x))
    v = [t.rest_hr, t.k_person, t.core_offset, t.c_bodyheat]
    return (all(map(math.isfinite, v)) and F(40) <= v[0] <= F(100) and F(0.03) <= v[1] <= F(0.4) and F(-0.8) <= v[2] <= F(0.8)
            and 0 <= v[3] <= F(0.4) and all(math.isnan(x) or 25 <= x <= 42 for x in t.t1_night_base))


def rec(name, status, detail=""):
    RES[name] = (status, detail)
    print(f"[{status}] {name}: {detail}")


# --------------------------------------------------------------------------- stream generator (tester's own)
def stream(seed, nights=10, garbage=0.02, readings=True, alarm_p=0.1, offwear_p=0.1, upd_tod=420, room=True):
    """10 nights of plausible band minutes + interior K readings (k_obs inside 0.03..0.40), random freezes,
    random garbage minutes, room readings, then a pack event. Nightly update at upd_tod each day."""
    r = np.random.default_rng(seed)
    ev = []
    rest = r.uniform(48, 85); k_true = r.uniform(0.05, 0.35); off_true = r.normal(0, 0.2)
    t1_base = r.uniform(32.0, 34.5)
    for d in range(nights):
        alarm_night = r.random() < alarm_p
        off_night = r.random() < offwear_p
        hot = r.random() < 0.3
        for i in range(1440):
            tod = (upd_tod + 1 + i) % 1440
            asleep = int(tod >= 1350 or tod < 400)
            tair = (29.5 if hot else 25.0) + 1.5 * math.sin(2 * math.pi * (tod - 900) / 1440) + r.normal(0, 0.2)
            astd = 0.0012 if asleep else (0.04 if r.random() < 0.25 else 0.0018)
            t1 = t1_base + (0.5 if asleep else 0) + r.normal(0, 0.08)
            hr = rest - 7 + r.normal(0, 2.5) if asleep else rest + 10 + r.normal(0, 5)
            if r.random() < 0.2:
                hr = np.nan if r.random() < 0.5 else hr + r.uniform(-30, 15)
            worn = 2
            if off_night and asleep and r.random() < 0.6:
                worn = int(r.integers(0, 2))
            tier = int(alarm_night and asleep and 30 <= tod < 40)
            loc, air_ref = 0, np.nan
            if 600 <= tod < 600 + int(r.integers(10, 60)):
                loc, astd, air_ref = 2, 0.06, 31.0 + r.normal(0, 0.3)
                tair = air_ref + r.uniform(0.05, 0.3) * (t1 - air_ref) + r.normal(0, 0.1)
            e = dict(kind="m", t1_c=t1, t2_c=t1 - r.uniform(0.3, 3.0), t_air_c=tair, rh_pct=50.0, hr_bpm=hr,
                     hr_quality=4 if np.isfinite(hr) else 0, pi_pct=0.7, a_std_g=astd, worn=worn, minute_of_day=tod,
                     asleep=asleep, location=loc, hr_valid=int(np.isfinite(hr)), tier_on=tier, air_ref=air_ref)
            if r.random() < garbage:
                bad = [np.nan, np.inf, -np.inf, 1e30, -1e30, -40.0, 60.0, 0.0, 250.0]
                for c in ("t1_c", "t_air_c", "hr_bpm", "a_std_g", "air_ref", "t2_c"):
                    if r.random() < 0.5:
                        e[c] = bad[r.integers(len(bad))]
                if r.random() < 0.3:
                    e["minute_of_day"] = 0xFFFF
                if r.random() < 0.2:
                    e["worn"] = int(r.integers(0, 256))
            ev.append(e)
            if readings and tod == 560 and r.random() < 0.7:
                dT = f32(r.uniform(0.45, 3.0)); t1r = f32(t1_base + r.normal(0, 0.1))
                ev.append(dict(kind="r", r0=t1r + off_true + k_true * dT + r.normal(0, 0.05), r1=t1r, r2=dT,
                               r3=36.9 + r.normal(0, 0.3), r4=int(r.random() < 0.85)))
            if room and tod == 700 and r.random() < 0.3:
                ev.append(dict(kind="q", r0=24.0 + r.normal(0, 0.5), r1=25.0 + r.normal(0, 0.5), r2=33.5))
        ev.append(dict(kind="u"))
    ev.append(dict(kind="P"))
    return ev


# --------------------------------------------------------------------------- T1 golden C == Python
def t1_golden():
    drivers = {"O0": build_driver("O0", ["-O0"]), "O2": build_driver("O2", ["-O2"]),
               "O3fma": build_driver("O3fma", ["-O3", "-march=native", "-ffp-contract=fast"])}
    tmp = tempfile.mkdtemp(dir=BUILD)
    worst = {k: 0.0 for k in drivers}; fails = {k: [] for k in drivers}
    k_interior = 0; n_upd = 0; frozen_codes = set()
    for seed in range(40):
        ev = stream(1000 + seed)
        path = write_events(ev, os.path.join(tmp, f"s{seed}.csv"))
        _, py = py_replay(ev)
        for row in py:
            if row[0] == "U":
                n_upd += 1; frozen_codes.add(row[2])
                if 0.03 < row[4] < 0.40 and abs(row[4] - 0.12) > 1e-6:
                    k_interior += 1
        for tag, drv in drivers.items():
            mx, bad = compare(py, c_replay(drv, path))
            worst[tag] = max(worst[tag], mx); fails[tag] += [f"seed {seed}: {b}" for b in bad[:3]]
    ok = all(not v for v in fails.values()) and all(w <= 1e-5 for w in worst.values())
    rec("T1 golden C==Python, 40 random streams x 10 nights (400 updates), 3 builds",
        "PASS" if ok else "FAIL",
        f"max|C-Py| {worst}; updates {n_upd}; K strictly interior after {k_interior} updates; frozen codes seen {sorted(frozen_codes)}; "
        f"mismatches {sum(len(v) for v in fails.values())} {[v[:2] for v in fails.values() if v]}")
    # builder's own golden: does it ever test an interior K?
    import pandas as pd
    ex = pd.read_parquet(TW + "/tests/golden_expected.parquet")
    ks = sorted(set(np.round(ex.k_person.values.astype(float), 6)))
    rec("T1b builder golden covers interior K values?", "DEFECT" if set(ks) <= {0.12, 0.4} else "PASS",
        f"builder golden k_person values = {ks} (default and the upper clamp only: the K formula's interior is never "
        "checked C-vs-Python by host_test)")


# --------------------------------------------------------------------------- T2 rule oracles (Python ref; C checked via T1)
def night(tw, n_sleep=120, hr=55.0, tod0=0, t1=33.5, tair=24.0, worn=2, tier=0, extra=None):
    for i in range(n_sleep):
        m = dict(t1_c=t1, t2_c=t1 - 2, t_air_c=tair, hr_bpm=hr if np.isscalar(hr) else hr[i], a_std_g=0.001,
                 worn=worn if np.isscalar(worn) else worn[i], minute_of_day=(tod0 + i) % 1440, asleep=1,
                 location=0, hr_valid=1, tier_on=tier if np.isscalar(tier) else tier[i])
        if extra:
            m.update(extra)
        tw.ingest_minute(m)


def t2_rules():
    out = []
    # rest_hr: p10 of a known sample, rule value
    r = np.random.default_rng(7); hr = r.normal(56, 3, 300).astype(np.float32)
    tw = BodyTwin(); night(tw, 300, hr); ch = tw.nightly_update()
    p10_true = float(np.percentile(hr, 10)); p10 = ch.get("p10_night_hr", np.nan)
    exp = 70 + 0.3 * (p10 + 5 - 70)
    out.append(("rest_hr p10 vs numpy percentile (|d| <= 1 bpm, histogram)", abs(p10 - p10_true) <= 1.0, f"hist {p10:.3f} np {p10_true:.3f}"))
    out.append(("rest_hr rule value", abs(float(tw.params['rest_hr']) - exp) < 1e-4, f"{float(tw.params['rest_hr']):.5f} vs {exp:.5f}"))
    # 59 vs 60 valid sleep minutes
    for n, should in ((59, False), (60, True)):
        tw = BodyTwin(); night(tw, n, 50.0); night(tw, 80, np.nan, tod0=200)   # pad night_n with HR-less minutes
        tw.nightly_update(); moved = float(tw.params["rest_hr"]) != 70.0
        out.append((f"rest_hr with {n} valid sleep minutes moves={should}", moved == should, f"rest={float(tw.params['rest_hr']):.3f}"))
    # K: dT 0.49 vs 0.5; interior formula
    for dT, should in ((0.49, False), (0.5, True)):
        tw = BodyTwin(); tw.ingest_reading(37.0, 0, 36.9, dT, 36.9, 1); tw.commit_reading()
        moved = float(tw.params["k_person"]) != f32(0.12)
        out.append((f"K moves at dT={dT}: {should}", moved == should, f"K={float(tw.params['k_person']):.6f}"))
    tw = BodyTwin(); tw.ingest_reading(36.9, 0, 36.5, 2.0, 36.7, 1); tw.commit_reading()
    kexp = 0.12 + 0.5 * ((36.9 - 0 - 36.5) / 2.0 - 0.12); oexp = 0.35 * (36.9 - 36.7)
    out.append(("K interior formula", abs(float(tw.params["k_person"]) - kexp) < 1e-6, f"{float(tw.params['k_person']):.6f} vs {kexp:.6f}"))
    out.append(("offset formula", abs(float(tw.params["core_offset"]) - oexp) < 1e-6, f"{float(tw.params['core_offset']):.6f} vs {oexp:.6f}"))
    # no flux -> K untouched, offset still learns
    tw = BodyTwin(); tw.ingest_reading(36.9, 0, 33.5, 2.0, 36.7, 0); tw.commit_reading()
    out.append(("flux_valid=0: K frozen, offset learns", float(tw.params["k_person"]) == f32(0.12) and float(tw.params["core_offset"]) != 0, ""))
    # decay half-life 2 nightly updates (also when frozen)
    tw = BodyTwin(); tw.params["core_offset"] = f32(0.6)
    for _ in range(4):
        tw.nightly_update()
    out.append(("offset decay 4 updates -> 1/4", abs(float(tw.params["core_offset"]) / 0.6 - 0.25) < 1e-6, f"{float(tw.params['core_offset']) / 0.6:.7f}"))
    # freeze: one alarm minute at night; worn != 2 at exactly 30 % vs 31 %
    tw = BodyTwin(); night(tw, 200, 50.0, tier=np.r_[np.zeros(199), 1]); tw.nightly_update()
    out.append(("one alarm minute at night freezes", tw.last_frozen == 1 and float(tw.params["rest_hr"]) == 70.0, f"frozen={tw.last_frozen}"))
    for nbad, should in ((60, 0), (62, 3)):
        tw = BodyTwin(); w = np.full(200, 2); w[:nbad] = 0; night(tw, 200, 50.0, worn=w); tw.nightly_update()
        out.append((f"worn!=2 for {nbad}/200 night minutes -> frozen code {should}", tw.last_frozen == should, f"got {tw.last_frozen}"))
    # baseline: 19 vs 20 qualifying minutes; NAN until 3 nights; mean of 3
    for nq, should in ((19, False), (20, True)):
        tw = BodyTwin()
        for d in range(3):
            night(tw, 100, 50.0, tod0=0)                      # night_n
            for i in range(nq):
                tw.ingest_minute(dict(t1_c=33.0 + d * 0.1, t_air_c=24.0, a_std_g=0.001, worn=2, minute_of_day=720 + i, hr_valid=0))
            tw.nightly_update()
        learned = math.isfinite(tw.params["t1_night_base"][12])
        out.append((f"baseline hour 12 with {nq} minutes/night x3 learned={should}", learned == should,
                    f"base12={tw.params['t1_night_base'][12]}"))
    out.append(("baseline mean of 3 nights (33.0, 33.1, 33.2) = 33.1 +- 0.01", abs(float(tw.params["t1_night_base"][12]) - 33.1) < 0.011,
                f"{float(tw.params['t1_night_base'][12]):.4f}"))
    tw = BodyTwin()
    for d in range(2):
        night(tw, 100, 50.0); [tw.ingest_minute(dict(t1_c=33.0, t_air_c=24.0, a_std_g=0.001, worn=2, minute_of_day=720 + i)) for i in range(30)]
        tw.nightly_update()
    out.append(("baseline NAN after 2 nights", math.isnan(tw.params["t1_night_base"][12]), ""))
    # T_air >= 28 -> not learned
    tw = BodyTwin()
    for d in range(4):
        night(tw, 100, 50.0); [tw.ingest_minute(dict(t1_c=33.0, t_air_c=28.0, a_std_g=0.001, worn=2, minute_of_day=720 + i)) for i in range(60)]
        tw.nightly_update()
    out.append(("baseline not learned at T_air = 28.0", math.isnan(tw.params["t1_night_base"][12]), ""))
    # n cap 30: after 40 nights at 33.0 then 1 night at 36.0 -> step 3/30 = 0.1
    tw = BodyTwin()
    for d in range(41):
        night(tw, 100, 50.0); v = 33.0 if d < 40 else 36.0
        [tw.ingest_minute(dict(t1_c=v, t_air_c=24.0, a_std_g=0.001, worn=2, minute_of_day=720 + i)) for i in range(30)]
        tw.nightly_update()
    out.append(("Welford n capped at 30 (step = 3/30)", abs(float(tw.params["t1_night_base"][12]) - 33.1) < 0.002,
                f"{float(tw.params['t1_night_base'][12]):.4f}, n={int(tw.t1_n[12])}"))
    # c_bodyheat 29 vs 30 OUT-walking minutes, LS slope
    for n, should in ((29, False), (30, True)):
        tw = BodyTwin(); night(tw, 100, 50.0)
        for i in range(n):
            t1 = 33.0 + 0.01 * i; ref = 30.0; tm = ref + 0.25 * (t1 - ref) / (1 + 0.25)   # T_air_meas - ref = c*(T1 - T_air_meas) with c = 0.25
            tw.ingest_minute(dict(t1_c=t1, t_air_c=tm, a_std_g=0.05, worn=2, minute_of_day=600 + i, location=2, air_ref=ref))
        tw.nightly_update(); c = float(tw.params["c_bodyheat"])
        exp = 0.15 + 0.3 * (0.25 - 0.15) if should else 0.15
        out.append((f"c_bodyheat with {n} OUT-walking minutes", abs(c - exp) < 1e-4, f"c={c:.5f} exp {exp:.5f}"))
    # no update per minute: params constant between nightly updates (except an explicit commit_reading)
    tw = BodyTwin(); snap = tw.params_vector(); ev = stream(5, nights=1, readings=False)
    for e in ev:
        if e["kind"] == "m":
            tw.ingest_minute({k: v for k, v in e.items() if k != "kind"})
    same = all((a == b) or (math.isnan(a) and math.isnan(b)) for a, b in zip(snap, tw.params_vector()))
    out.append(("no parameter changes per minute (1440 minutes, no update)", same, ""))
    nf = sum(1 for _, ok, _ in out if not ok)
    for name, ok, det in out:
        rec("T2 " + name, "PASS" if ok else "FAIL", det)
    return nf


# --------------------------------------------------------------------------- T3 bounds attacks the builder's fuzz misses
def t3_bounds(lib):
    # (a) minute_of_day stuck (RTC/clock fault) or only one qualifying hour for > 255 min without a nightly update:
    #     cur_cnt saturates at 255 while cur_sum keeps adding -> hourly mean inflated -> t1_night_base out of 25..42
    def stuck(tw_py, tw_c, acc, nights=3, minutes=1000):
        for d in range(nights):
            for i in range(minutes):
                m = dict(t1_c=33.0, t2_c=31.0, t_air_c=24.0, a_std_g=0.001, worn=2, minute_of_day=180, asleep=1, hr_bpm=55.0, hr_valid=1)
                tw_py.ingest_minute(m)
                cin = In(33.0, 31.0, 24.0, 50.0, 55.0, 4, 0.7, 0.001, 2, 180)
                lib.hg_twin_ingest_minute(C.byref(acc), C.byref(cin), 1, 0, 1)
            tw_py.nightly_update(); lib.hg_twin_nightly_update(C.byref(tw_c), C.byref(acc))
    tw = BodyTwin(); twc = Twin(); acc = Acc(); lib.hg_twin_defaults(C.byref(twc)); lib.hg_twin_acc_init(C.byref(acc))
    stuck(tw, twc, acc)
    bpy = float(tw.params["t1_night_base"][3]); bc = twc.t1_night_base[3]
    viol = not (25 <= bpy <= 42) and not (25 <= bc <= 42)
    rec("T3a stuck minute_of_day (1000 still minutes in hour 3 per night, 3 nights)", "DEFECT" if viol else "PASS",
        f"t1_night_base[3] Python={bpy:.2f} C={bc:.2f} degC (bounds 25..42; true T1 = 33.0). cur_cnt saturates at 255 "
        "(hg_twin.c ingest_minute 'if (a->cur_cnt < 255u) a->cur_cnt++' while cur_sum keeps adding; flush_hour_ divides by 255)")
    # (a2) same mechanism, realistic: heat wave, only 03:00-03:59 is < 28 degC, nightly update missed for 5 days
    tw = BodyTwin()
    for d in range(5):
        for tod in range(1440):
            tair = 27.5 if 180 <= tod < 240 else 30.0
            tw.ingest_minute(dict(t1_c=34.0, t_air_c=tair, a_std_g=0.001, worn=2, minute_of_day=tod, asleep=int(tod < 400), hr_bpm=60.0, hr_valid=1))
    tw.nightly_update()
    rec("T3a2 heat wave, only hour 3 qualifies, nightly update missed 5 days", "INFO",
        f"today mean for hour 3 -> t1_n[3]={int(tw.t1_n[3])}, pre_cd={int(tw.t1_pre_cd[3])} (true 3400): one night only, but the cd is "
        f"{'INFLATED' if tw.t1_pre_cd[3] > 3410 else 'ok'}")
    # (b) int16 overflow of the centi-degree cast when the inflated mean > 327.67 degC (UB in C, Python keeps int64)
    tw = BodyTwin(); twc = Twin(); acc = Acc(); lib.hg_twin_defaults(C.byref(twc)); lib.hg_twin_acc_init(C.byref(acc))
    stuck(tw, twc, acc, nights=1, minutes=3000)
    rec("T3b centi-degree int16 overflow (3000 stuck minutes)", "DEFECT" if int(tw.t1_pre_cd[3]) != acc.t1_pre_cd[3] else "PASS",
        f"t1_pre_cd[3] Python={int(tw.t1_pre_cd[3])} C={acc.t1_pre_cd[3]} (C (int16_t)floorf(x) out of range = undefined behaviour; C != Python)")
    # (c) CRC-valid file whose learning state is inconsistent: t1_n=1 with t1_pre_cd = CD_NONE -> accepted -> baseline far outside bounds
    py = BodyTwin(); py.t1_n[5] = 1; py.t1_pre_cd[5] = -32768
    blob = py.to_bytes(b"", save_count=1)
    t2, _, _, okpy = BodyTwin.from_bytes(blob)
    twc = Twin(); acc = Acc(); rl = C.c_uint16(); sc = C.c_uint32()
    rc = lib.hg_twin_unpack(blob, len(blob), C.byref(twc), C.byref(acc), None, 0, C.byref(rl), C.byref(sc))
    for d in range(2):
        night_c = [In(33.0, 31.0, 24.0, 50.0, 55.0, 4, 0.7, 0.001, 2, (300 + i) % 1440) for i in range(100)]
        for cin in night_c:
            lib.hg_twin_ingest_minute(C.byref(acc), C.byref(cin), 1, 0, 1)
        lib.hg_twin_nightly_update(C.byref(twc), C.byref(acc))
    b5 = twc.t1_night_base[5]
    rec("T3c CRC-valid file, t1_n[5]=1 with t1_pre_cd[5]=CD_NONE", "DEFECT" if (rc == 0 and okpy and not (25 <= b5 <= 42)) else "PASS",
        f"unpack C rc={rc}, Python ok={okpy}; after 2 nights t1_night_base[5] = {b5:.2f} degC (bounds 25..42) -- hg_twin_unpack "
        "range-checks t1_n and t1_night_base but not t1_pre_cd; sanitize_ only runs at the START of the next update")
    # (d) Python vs C rounding of the n==1 mean for negative / odd sums (only reachable from (c)-type states)
    py = BodyTwin(); py.t1_n[5] = 1; py.t1_pre_cd[5] = -3301
    t2, _, _, ok = BodyTwin.from_bytes(py.to_bytes(b"", 1))
    blob = py.to_bytes(b"", 1)
    twc = Twin(); acc = Acc(); lib.hg_twin_unpack(blob, len(blob), C.byref(twc), C.byref(acc), None, 0, C.byref(rl), C.byref(sc))
    for i in range(100):
        t2.ingest_minute(dict(t1_c=33.0, t_air_c=24.0, a_std_g=0.001, worn=2, minute_of_day=(300 + i) % 1440, asleep=1))
        cin = In(33.0, 31.0, 24.0, 50.0, float("nan"), 0, 0.7, 0.001, 2, (300 + i) % 1440)
        lib.hg_twin_ingest_minute(C.byref(acc), C.byref(cin), 1, 0, 0)
    t2.nightly_update(); lib.hg_twin_nightly_update(C.byref(twc), C.byref(acc))
    rec("T3d n==1 integer mean, negative odd sum: Python floor // vs C truncation", "DEFECT" if int(t2.t1_pre_cd[5]) != acc.t1_pre_cd[5] else "PASS",
        f"Python {int(t2.t1_pre_cd[5])} vs C {acc.t1_pre_cd[5]} (minor: only from a semantically corrupt file)")
    # (e) extreme but finite context: air_ref = 3e38, readings with dT = 14.99, t_read at bounds
    twc = Twin(); acc = Acc(); lib.hg_twin_defaults(C.byref(twc)); lib.hg_twin_acc_init(C.byref(acc))
    lib.hg_twin_set_air_ref(C.byref(acc), 3e38)
    for i in range(200):
        cin = In(42.0, 20.0, -19.9, 0.0, 250.0, 4, 0.0, 0.5, 2, (i * 7) % 1440)
        lib.hg_twin_ingest_minute(C.byref(acc), C.byref(cin), 1, 2, 1)
    lib.hg_twin_ingest_reading(C.byref(acc), 40.0, 25.0, 14.99, 34.0, 1)
    lib.hg_twin_nightly_update(C.byref(twc), C.byref(acc))
    vals = [twc.rest_hr, twc.k_person, twc.core_offset, twc.c_bodyheat]
    ok = inb(twc)
    rec("T3e extreme finite inputs (air_ref 3e38, dT 14.99, T_air -19.9, HR 250)", "PASS" if ok else "FAIL", f"params {['%.4f' % v for v in vals]}")
    # (f) C fuzz with sequential clock and 30 % garbage, 200 nights, bounds after every update
    r = np.random.default_rng(99); twc = Twin(); acc = Acc(); lib.hg_twin_defaults(C.byref(twc)); lib.hg_twin_acc_init(C.byref(acc))
    worst = 0
    wild = [float("nan"), float("inf"), float("-inf"), 1e30, -40.0, 60.0, 0.0, 250.0]
    for d in range(200):
        for i in range(0, 1440, 3):
            g = lambda lo, hi: wild[r.integers(len(wild))] if r.random() < 0.3 else float(r.uniform(lo, hi))
            cin = In(g(25, 42), g(20, 40), g(10, 45), g(0, 100), g(30, 110), int(r.integers(0, 5)), g(0, 3), g(0, 0.003), 2 if r.random() < 0.9 else int(r.integers(0, 256)), i)
            lib.hg_twin_note_tier(C.byref(acc), int(r.random() < 0.002)); lib.hg_twin_set_air_ref(C.byref(acc), g(20, 40))
            lib.hg_twin_ingest_minute(C.byref(acc), C.byref(cin), int(i < 420), int(r.integers(0, 3)), int(r.random() < 0.7))
        if r.random() < 0.5:
            lib.hg_twin_ingest_reading(C.byref(acc), g(35, 39), g(30, 36), g(0, 4), g(35, 39), 1)
            lib.hg_twin_commit_reading(C.byref(twc), C.byref(acc))
        lib.hg_twin_nightly_update(C.byref(twc), C.byref(acc))
        worst += 0 if inb(twc) else 1
    rec("T3f C fuzz: 200 nights, sequential clock, 30 % NaN/inf/out-of-range fields", "PASS" if worst == 0 else "FAIL",
        f"updates out of bounds: {worst}; final rest {twc.rest_hr:.2f} K {twc.k_person:.3f} off {twc.core_offset:.3f} c {twc.c_bodyheat:.3f} days {twc.days_learned}")


# --------------------------------------------------------------------------- T4 file format
def t4_file(lib):
    r = np.random.default_rng(3)
    bad = 0
    for n in (0, 1, 3, 9, 100, 899, 4096):
        for _ in range(20):
            b = r.integers(0, 256, n, dtype=np.uint8).tobytes()
            if lib.hg_twin_crc32(0, b, n) != zlib.crc32(b):
                bad += 1
    # chained crc
    b = r.integers(0, 256, 300, dtype=np.uint8).tobytes()
    chain = lib.hg_twin_crc32(lib.hg_twin_crc32(0, b[:100], 100), b[100:], 200) == zlib.crc32(b)
    rec("T4a C crc32 == zlib.crc32 on 140 random buffers (0..4096 B) + chaining", "PASS" if bad == 0 and chain else "FAIL", f"mismatches {bad}, chain {chain}")
    # pack with B5's real routine size (HG_ROUTINE_PACK_BYTES 650) and the ARCHITECTURE ceiling 700
    tw = Twin(); acc = Acc(); lib.hg_twin_defaults(C.byref(tw)); lib.hg_twin_acc_init(C.byref(acc))
    buf = (C.c_uint8 * 1024)(); rout = (C.c_uint8 * 700)()
    l650 = lib.hg_twin_pack(C.byref(tw), C.byref(acc), rout, 650, 1, buf, 1024)
    l699 = lib.hg_twin_pack(C.byref(tw), C.byref(acc), rout, 699, 1, buf, 1024)
    l700 = lib.hg_twin_pack(C.byref(tw), C.byref(acc), rout, 700, 1, buf, 1024)
    rec("T4b file size with B5 routine 650 B / 699 / 700 (ARCH allows routine <= 700)", "PASS" if l650 == 851 and l699 == 900 else "FAIL",
        f"650 -> {l650} B (<= 900, 7 x 128-B blocks = {math.ceil(l650 / 128)}), 699 -> {l699}, 700 -> {l700} (refused: the 72-B learning "
        "state not in ARCH 5 makes routine <= 699, ARCH says <= 700 -> 1-B spec mismatch, minor)")
    # Python vs C verdict on 3000 random mutations of a valid file (1-4 bytes changed, CRC NOT fixed), and 3000 with CRC fixed
    py = BodyTwin(); py.params["rest_hr"] = f32(61.0); py.params["t1_night_base"][3] = f32(33.4); py.t1_n[3] = 5; py.t1_pre_cd[3] = -32768
    good = py.to_bytes(bytes(range(200)), 9)
    disagree = 0; acc_nocrc = 0; acc_fixed = 0; oob_after = 0
    for trial in range(6000):
        b = bytearray(good)
        for _ in range(int(r.integers(1, 5))):
            b[int(r.integers(8, len(b) - 4))] = int(r.integers(0, 256))
        if trial >= 3000:
            b[-4:] = (zlib.crc32(bytes(b[:-4])) & 0xFFFFFFFF).to_bytes(4, "little")
        b = bytes(b)
        _, _, _, okp = BodyTwin.from_bytes(b)
        twc = Twin(); acc = Acc(); rl = C.c_uint16(); sc = C.c_uint32(); rb = (C.c_uint8 * 900)()
        rc = lib.hg_twin_unpack(b, len(b), C.byref(twc), C.byref(acc), rb, 900, C.byref(rl), C.byref(sc))
        if okp != (rc == 0):
            disagree += 1
        if rc == 0:
            if trial < 3000:
                if b != good:
                    acc_nocrc += 1
            else:
                acc_fixed += 1
                if not inb(twc):
                    oob_after += 1
        else:
            if not (twc.rest_hr == f32(70) and twc.k_person == f32(0.12) and twc.days_learned == 0 and rl.value == 0 and sc.value == 0):
                oob_after += 1
    rec("T4c 6000 random multi-byte mutations: C unpack == Python from_bytes verdict; corrupt -> defaults",
        "PASS" if disagree == 0 and acc_nocrc == 0 and oob_after == 0 else "FAIL",
        f"verdict disagreements {disagree}; mutated files accepted without a CRC fix {acc_nocrc}; CRC-fixed semantic mutations accepted "
        f"{acc_fixed}/3000 (all in bounds: {oob_after == 0})")
    # wrong length field / version / magic
    rc = []
    for off, val in ((0, 0x00), (4, 0x03), (6, 0x00)):
        b = bytearray(good); b[off] = val; b[-4:] = (zlib.crc32(bytes(b[:-4])) & 0xFFFFFFFF).to_bytes(4, "little")
        twc = Twin(); acc = Acc(); rl = C.c_uint16(); sc = C.c_uint32(); rb = (C.c_uint8 * 900)()
        rc.append(lib.hg_twin_unpack(bytes(b), len(b), C.byref(twc), C.byref(acc), rb, 900, C.byref(rl), C.byref(sc)))
    rec("T4d bad magic / version / length with a valid CRC rejected", "PASS" if all(x < 0 for x in rc) else "FAIL", f"rc {rc}")
    # routine_cap smaller than routine -> rejected, defaults
    twc = Twin(); acc = Acc(); rl = C.c_uint16(); sc = C.c_uint32(); rb = (C.c_uint8 * 100)()
    rcx = lib.hg_twin_unpack(good, len(good), C.byref(twc), C.byref(acc), rb, 100, C.byref(rl), C.byref(sc))
    rec("T4e routine_cap too small -> error, defaults", "PASS" if rcx < 0 and twc.rest_hr == f32(70) else "FAIL", f"rc {rcx}, rest {twc.rest_hr}")


# --------------------------------------------------------------------------- T5 PPG outlier effect on the night floor (ARCH sensor model)
def t5_outliers():
    r = np.random.default_rng(11); errs = []
    for p in range(200):
        true_sleep = r.uniform(48, 70); tw = BodyTwin()
        for night_i in range(7):
            hr = true_sleep + r.normal(0, 3, 400)
            out = r.random(400) < 0.20                                  # ARCH 3.3: outliers p 0.20 at rest, U(-30, +15)
            hr[out] = hr[out] + r.uniform(-30, 15, out.sum())
            night(tw, 400, hr.astype(np.float32)); tw.nightly_update()
        clean_p10 = true_sleep - 1.2816 * 3
        errs.append(float(tw.params["rest_hr"]) - (clean_p10 + 5))
    e = np.array(errs)
    rec("T5 rest_hr bias from MAX30102 outliers (SIMULATION of ARCH 3.3 noise, hr_valid assumed not to catch them)", "RISK",
        f"rest_hr - clean target after 7 nights: median {np.median(e):+.2f} bpm, p90 {np.percentile(e, 90):+.2f}, p10 {np.percentile(e, 10):+.2f}")


def t5b_k_axial():
    """ARCH 5 K rule uses T_read (core) - T1 over dT; R2 6.3 sensor model: T_deep = T_core - D_axial, K_true = R_tissue/R_ins.
    So k_obs = K_true + D_axial/dT (+ offset effects). R2 6.3 numbers: a U(0.3,0.8), b U(0.08,0.2), dT 2-5 indoors."""
    r = np.random.default_rng(2); ks = []
    for _ in range(2000):
        a, b, s = r.uniform(0.3, 0.8), r.uniform(0.08, 0.2), r.uniform(0, 0.5)
        Tc, Ta = 37.0, r.uniform(24, 30); dax = a + b * (Tc - Ta) * (1 - s)
        Kt = r.uniform(0.008, 0.014) / 0.082; dT = r.uniform(2, 5); T1 = Tc - dax - Kt * dT
        tw = BodyTwin()
        for d in range(3):
            tw.ingest_reading(Tc + r.normal(0, 0.2), 0, T1, dT, np.nan, 1); tw.commit_reading()
        ks.append((float(tw.params["k_person"]), Kt))
    k = np.array(ks)
    rec("T5b K rule absorbs the axial gap (SIMULATION from R2 6.3 constants, 3 readings, offset not yet learned)", "RISK",
        f"learned K median {np.median(k[:, 0]):.3f} (at upper bound 0.40 in {100 * np.mean(k[:, 0] >= 0.3999):.0f} %), K_true median {np.median(k[:, 1]):.3f}: "
        "k_obs = K_true + D_axial/dT; spec rule (ARCH 5), not a builder deviation")


# --------------------------------------------------------------------------- T6 sim reader + seal
def t6_seal():
    import sim_io
    try:
        sim_io.sealed_sim_ids(); found = True; msg = "ok"
    except Exception as ex:          # noqa: BLE001
        found = False; msg = f"{type(ex).__name__}: {ex}"
    rec("T6a sim_io.sealed_sim_ids() reads the REAL model/sealed_hg2.json", "DEFECT" if not found else "PASS",
        msg[:260] + " -> eval_sim.py and make_golden.py --source sim cannot run (fail-closed: safe, but blocks acceptance 1 and the SIM golden)")
    js = json.load(open("/home/claude/hg_ai/model/sealed_hg2.json"))
    sealed = [int(x) for x in js["sealed_sim_person_ids"]]
    sha = hashlib.sha256(open("/home/claude/hg_ai/sim/data/persons.parquet", "rb").read()).hexdigest()
    rec("T6b seal SHA-256 of persons.parquet matches", "PASS" if sha == js["persons_parquet_sha256"] else "FAIL", sha[:16])
    # synthetic minutes file: one row group per person + one mixed group; ids include sealed ones. NO sealed DATA is read
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    d = tempfile.mkdtemp(dir=BUILD)
    dev = [i for i in range(500) if i not in set(sealed)]
    ids = sealed[:3] + dev[:5]
    w = None; path = os.path.join(d, "minutes_dev.parquet")
    for pid in ids:
        t = pa.Table.from_pandas(pd.DataFrame(dict(person_id=np.full(10, pid, np.int64), day=np.zeros(10, np.int64), minute_of_day=np.arange(10))), preserve_index=False)
        w = w or pq.ParquetWriter(path, t.schema); w.write_table(t)
    mixed = pa.Table.from_pandas(pd.DataFrame(dict(person_id=np.array([dev[6]] * 5 + [sealed[4]] * 5, np.int64), day=np.zeros(10, np.int64), minute_of_day=np.arange(10))), preserve_index=False)
    w.write_table(mixed); w.close()
    seal = os.path.join(d, "seal.json"); json.dump({"sealed_sim_ids": sealed}, open(seal, "w"))
    old = (sim_io.SIM, sim_io.SEAL); sim_io.SIM, sim_io.SEAL = d, seal
    try:
        dm = sim_io.DevMinutes(["person_id", "day", "minute_of_day"])
        got = dm.persons()
        leak = set(got) & set(sealed)
        try:
            dm.person(sealed[0]); refused = False
        except AssertionError:
            refused = True
        lost = dev[6] not in got
        phantom = [p for p in got if p not in ids]
        rec("T6c DevMinutes on a synthetic file with sealed row groups (seal key patched to one sim_io accepts)",
            "PASS" if not leak and refused else "FAIL",
            f"sealed ids returned {sorted(leak)}; person(sealed) refused {refused}; dev person in a mixed group dropped {lost} (safe); "
            f"phantom ids listed {phantom[:5]}")
    finally:
        sim_io.SIM, sim_io.SEAL = old
    # every script that touches sim asserts on the seal
    srcs = {n: open(os.path.join(TW, n)).read() for n in ("eval_sim.py", "sim_io.py", "tests/make_golden.py")}
    rec("T6d sealed-id assertion present in eval_sim / sim_io / make_golden", "PASS" if all("sealed" in s and "assert" in s for s in srcs.values()) else "FAIL", "")
    has_sim = any(os.path.exists(f"/home/claude/hg_ai/sim/data/{n}") for n in ("minutes_dev.parquet", "minutes_all.parquet"))
    readable = False
    if has_sim:
        try:
            pq.ParquetFile("/home/claude/hg_ai/sim/data/minutes_dev.parquet"); readable = True
        except Exception:        # noqa: BLE001  (B1 still writing: no footer yet)
            readable = False
    rec("T6e ARCH 5 test 1 (SIM leave-first-days-in, acceptance 1)", "PENDING",
        ("minutes_dev.parquet readable" if readable else "sim/data/minutes_dev.parquet absent or still being written (no parquet footer)")
        + "; eval_sim.py cannot run anyway until T6a is fixed")


# --------------------------------------------------------------------------- T7 timing, determinism, sizes, symbols
def t7_misc(lib):
    cin = In(33.0, 31.0, 24.0, 50.0, 55.0, 4, 0.7, 0.001, 2, 100)
    acc = Acc(); lib.hg_twin_acc_init(C.byref(acc))
    src = r'''#define _POSIX_C_SOURCE 199309L
#include "hg_twin.h"
#include <stdio.h>
#include <time.h>
int main(void){ static hg_twin_acc_t a; static hg2_twin_t t; hg_twin_defaults(&t); hg_twin_acc_init(&a);
 hg2_in_t in = {33.0f, 31.0f, 24.0f, 50.0f, 55.0f, 4, 0.7f, 0.001f, 2, 0};
 struct timespec s, e; clock_gettime(CLOCK_MONOTONIC, &s);
 for (long i = 0; i < 100000; i++) { in.minute_of_day = (uint16_t)(i % 1440); in.hr_bpm = 50.0f + (float)(i % 13);
   hg_twin_ingest_minute(&a, &in, (uint8_t)(in.minute_of_day < 420), 0, 1); if (i % 1440 == 1439) hg_twin_nightly_update(&t, &a); }
 clock_gettime(CLOCK_MONOTONIC, &e); printf("%ld\n", ((long)(e.tv_sec - s.tv_sec) * 1000000000L + (long)(e.tv_nsec - s.tv_nsec)) / 100000L); return (int)t.days_learned == 0; }'''
    p = os.path.join(BUILD, "t3_timing.c"); open(p, "w").write(src)
    from t3_common import sh, BRIEF_FLAGS, SRC
    sh(["gcc", *BRIEF_FLAGS, "-O2", "-I", SRC, "-o", p[:-2], p, SRC + "/hg_twin.c", "-lm"])
    import subprocess
    ns = float(subprocess.run([p[:-2]], capture_output=True, text=True).stdout)
    rec("T7a host timing of ingest_minute (+ nightly every 1440)", "PASS" if ns * 50 < 1e6 else "FAIL", f"{ns:.1f} ns/call host; x50 = {ns * 50 / 1000:.1f} us (budget 1000 us)")
    h = []
    for _ in range(2):
        _, o = py_replay(stream(4242)); h.append(hashlib.sha256(repr(o).encode()).hexdigest())
    rec("T7b determinism: Python replay twice, sha256 equal", "PASS" if h[0] == h[1] else "FAIL", h[0][:16])
    rec("T7c sizes", "PASS" if C.sizeof(Acc) == 240 and C.sizeof(Twin) == 116 else "FAIL",
        f"ctypes mirror: hg_twin_acc_t {C.sizeof(Acc)} B (<= 256), hg2_twin_t {C.sizeof(Twin)} B")
    txt = open(TW + "/c/hg_twin.c").read()
    import re
    hits = re.findall(r"\b(expf|logf|powf|exp|log|pow|double|malloc|calloc|free)\s*\(|\bdouble\b", txt)
    rec("T7d grep expf|logf|powf|double|malloc in hg_twin.c", "PASS" if not hits else "FAIL", f"hits {hits}")


def main():
    os.makedirs(BUILD, exist_ok=True)
    lib = setup_lib(build_lib())
    t1_golden()
    t2_rules()
    t3_bounds(lib)
    t4_file(lib)
    t5_outliers()
    t5b_k_axial()
    t6_seal()
    t7_misc(lib)
    json.dump({k: list(v) for k, v in RES.items()}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "t3_results.json"), "w"), indent=1)
    n = {s: sum(1 for v in RES.values() if v[0] == s) for s in ("PASS", "FAIL", "DEFECT", "PENDING", "RISK", "INFO")}
    print("SUMMARY", n)


if __name__ == "__main__":
    main()
