"""T4 — plan correctness: acceptance 1 and 3 reproduced, random-forecast property/metamorphic tests,
errand-counterfactual sensitivity, routine-profile interop with B5's struct layout.

Run: cd /tmp && unshare -rn python3 -W ignore /home/claude/hg_ai/tests/t4/t4_plan.py  -> out/plan_props.json
"""
import copy
import hashlib
import json
import os
import struct
import sys
import time

import numpy as np

sys.path.insert(0, "/home/claude/hg_ai")
from tomorrow import plan, demo, cli, ble_frame as bf, physics  # noqa: E402
from tomorrow.routine import RoutineTemplate, pack_band_profile  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ORD = {"OK": 0, "SHORT": 1, "AVOID": 2}


def adv(p):
    return "".join(h["advice"][0] for h in p["hours"])


def check_props(p):
    """Every invariant I can state from ARCHITECTURE §6 / B4 brief. Returns list of violations."""
    v = []
    try:
        cli.validate(p)
    except Exception as e:
        v.append("schema: %s" % str(e)[:80])
    H = p["hours"]
    if [h["h"] for h in H] != list(range(24)):
        v.append("hours not 0..23")
    if sum(h["advice"] in ORD for h in H) != 24:
        v.append("advice counts do not sum to 24")
    bm = p["safe_hours_bitmap"]
    for h in H:
        if bool(bm >> h["h"] & 1) != h["safe"] or h["safe"] != (h["advice"] == "OK"):
            v.append("bitmap/safe/advice mismatch h%d" % h["h"])
        base = 0 if h["errand_extra_rise"] < 0.15 else (1 if h["errand_extra_rise"] < 0.30 else 2)
        a = ORD[h["advice"]]
        thr = p["details"]["threshold_core"]
        if a < base:
            v.append("advice below errand cut-off h%d" % h["h"])
        if a == base + 1 and h["core_indoor"] < thr - 0.005:
            v.append("escalated without indoor crossing h%d" % h["h"])
        if a == base and h["core_indoor"] >= thr + 0.005 and h["t_in"] >= 26.5 and base < 2:
            v.append("indoor crossed in a warm room but not escalated h%d" % h["h"])
    d = p["details"]
    if p["heat_day"] != (d["at_max"] is not None and d["at_max"] >= 32.7):
        v.append("heat_day flag")
    if p["night_heat"] != (d["indoor_night_min"] >= 26.0):
        v.append("night_heat flag")
    fr = [bytes.fromhex(x) for x in p["ble"]["forecast_chunks_hex"]]
    sf = bytes.fromhex(p["ble"]["safe_hours_hex"])
    if any(len(x) != 20 for x in fr + [sf]):
        v.append("frame length")
    dec = bf.decode_forecast(fr)["hours"]
    for h in range(24):
        if dec[h]["safe"] != H[h]["safe"] or dec[h]["heat_day"] != p["heat_day"] or dec[h]["night_heat"] != p["night_heat"]:
            v.append("0x11 flag mismatch h%d" % h)
    if int.from_bytes(sf[1:4], "little") != bm:
        v.append("0x14 bitmap != plan bitmap")
    if "SIMULATION" not in p["labels"] or p["attribution"] != "Weather data by Open-Meteo.com":
        v.append("labels/attribution")
    return v


def strip_time(p):
    q = copy.deepcopy(p); q.pop("generated_at", None)
    return hashlib.sha256(json.dumps(q, sort_keys=True).encode()).hexdigest()


def main():
    R = {}
    # --- acceptance 1 (in-process; CLI timing measured separately in the report) ---------------
    t0 = time.time()
    p = plan.make_plan(demo.demo_forecast(), demo.DEMO_DATE, "B")
    R["demo_seconds_inprocess"] = round(time.time() - t0, 2)
    R["demo_advice"] = adv(p)
    R["demo_flags"] = [p["heat_day"], p["night_heat"], p["wave_day"]]
    R["demo_avoid_12_18"] = sum(h["advice"] == "AVOID" for h in p["hours"][12:19])
    R["demo_ok_before_09"] = [h["h"] for h in p["hours"][:9] if h["advice"] == "OK"]
    R["demo_physics"] = [l for l in p["labels"] if l.startswith("physics")]
    R["demo_violations"] = check_props(p)
    # which AVOID hours come from the errand rule vs the indoor escalation
    R["demo_extra_max"] = max(h["errand_extra_rise"] for h in p["hours"])
    R["demo_avoid_from_errand_alone"] = sum(h["errand_extra_rise"] >= 0.30 for h in p["hours"])
    R["demo_avoid_by_escalation"] = sum(h["advice"] == "AVOID" and h["errand_extra_rise"] < 0.30 for h in p["hours"])
    R["demo_threshold"] = p["details"]["threshold_core"]
    R["demo_core_indoor_max"] = max(h["core_indoor"] for h in p["hours"])
    # determinism
    p2 = plan.make_plan(demo.demo_forecast(), demo.DEMO_DATE, "B")
    R["deterministic_sha256_equal"] = strip_time(p) == strip_time(p2)

    # --- errand counterfactual sensitivity: extreme day ----------------------------------------
    fc = demo.synthetic_forecast([(30, 46)] * 4, "2026-07-01", rh_lo=8, rh_hi=40)
    px = plan.make_plan(fc, "2026-07-04", "B")
    R["extreme_46C_extra_max"] = max(h["errand_extra_rise"] for h in px["hours"])
    R["extreme_46C_AT_max"] = max(px["details"]["apparent_t"])
    R["extreme_46C_advice"] = adv(px)
    # errand from a fixed state at controlled AT (same snapshot), physics directly
    person = physics.person_from_twin(plan.default_twin())
    m, _ = physics.make_model(person, start_minute=600)
    for i in range(60):
        m.step({"t_db": 30.0, "t_r": 30.0, "rh": 30.0, "v_air": 0.1, "met": 0.86, "clo": 0.4, "drink_mL": 0, "minute_of_day": 600.0 + i})
    snap = physics.snapshot(m)
    rises = {}
    for AT in (22, 28, 32, 36, 40, 44, 48):
        mm = physics.snapshot(snap); pk = -9
        c0 = None
        for j in range(60):
            o = mm.step({"t_db": AT, "t_r": AT, "rh": 25.0, "v_air": 1.0, "met": 2.2, "clo": 0.5, "drink_mL": 0, "minute_of_day": 660.0 + j})
            c0 = o["T_core"] if c0 is None else c0
            pk = max(pk, o["T_core"])
        rises[AT] = round(pk, 3)
    R["errand_peak_core_by_AT_from_same_state"] = rises
    R["errand_extra_vs_22_by_AT"] = {k: round(v - rises[22], 3) for k, v in rises.items()}

    # --- acceptance 3: wave-day margin, fan, 24 C day ---------------------------------------------
    fcw = demo.synthetic_forecast([(23, 32)] * 4 + [(27, 40)] * 5, "2026-07-01")
    a3 = plan.make_plan(fcw, "2026-07-07", "B"); b3 = plan.make_plan(fcw, "2026-07-07", "B", wave_day_override=1)
    R["wave_day3"] = {"wave_day": a3["wave_day"], "with_margin": adv(a3), "without": adv(b3),
                      "moved_OK_to_SHORT": [h for h in range(24) if b3["hours"][h]["advice"] == "OK" and a3["hours"][h]["advice"] == "SHORT"]}
    fcc = demo.synthetic_forecast([(18, 24)] * 4, "2026-05-01", rh_lo=50, rh_hi=70)
    pc = plan.make_plan(fcc, "2026-05-04", "B")
    R["cool_24C_day"] = {"advice": adv(pc), "flags": [pc["heat_day"], pc["night_heat"]], "bitmap": pc["safe_hours_bitmap"]}
    # 24 C day with a beta-blocker + low-sweat wearer and class C (harder case)
    tw = dict(plan.default_twin(), med_flags=physics.MED_BETA_BLOCKER | physics.MED_LOW_SWEAT)
    pc2 = plan.make_plan(fcc, "2026-05-04", "C", twin=tw)
    R["cool_24C_day_classC_meds"] = adv(pc2)

    def const_core(T, fan, bed):
        r = RoutineTemplate.default()
        r.met[:] = 0.7 if bed else 0.86; r.clo[:] = 0.6 if bed else 0.4; r.asleep[:] = False; r.wake_minute = 0
        a = np.full(25, float(T)); rh = np.full(25, 45.0)
        return plan.simulate_day(person, a, rh, a, rh, a, rh, r, fan, errands=False)["core"]
    for T in (31, 36):
        for bed in (True, False):
            nf, wf = const_core(T, False, bed), const_core(T, True, bed)
            R["fan_T%d_%s" % (T, "bed" if bed else "seated")] = {
                "benefit_peak_08_16": round(float(nf[480:960].max() - wf[480:960].max()), 3),
                "benefit_end_8h": round(float(nf[959] - wf[959]), 3),
                "rise_8h_nofan": round(float(nf[959] - nf[480]), 3)}

    # --- random forecasts: properties + metamorphic monotonicity ---------------------------------
    rng = np.random.default_rng(424242)
    viol, worse_when_cooler, n = [], [], 0
    for k in range(12):
        tmin = float(rng.uniform(-5, 31)); tmax = tmin + float(rng.uniform(4, 16))
        days = [(tmin + float(rng.normal(0, 1.5)), 0) for _ in range(4)]
        days = [(a, a + (tmax - tmin)) for a, _ in days]
        cls = "ABCD"[k % 4]
        tw = dict(plan.default_twin(), age=float(rng.uniform(65, 90)), med_flags=int(rng.integers(0, 16)),
                  mass=float(rng.uniform(45, 100)), sweat_capacity=float(rng.uniform(0.31, 0.57)))
        rt = RoutineTemplate.default() if k % 3 else RoutineTemplate.from_band(
            pack_band_profile(np.clip(rng.normal(20, 15, 24), 0, 60)))
        fan = bool(k % 2)
        fc = demo.synthetic_forecast(days, "2026-08-01", rh_lo=float(rng.uniform(5, 40)), rh_hi=float(rng.uniform(45, 95)))
        pp = plan.make_plan(fc, "2026-08-04", cls, twin=tw, routine=rt, fan_available=fan)
        n += 1
        vv = check_props(pp)
        if vv:
            viol.append({"k": k, "cls": cls, "days": days[0], "v": vv[:4]})
        # +3 degC hotter must not make any hour safer
        hot = demo.synthetic_forecast([(a + 3, b + 3) for a, b in days], "2026-08-01", rh_lo=5, rh_hi=45) if False else None
        fc_h = copy.deepcopy(fc)
        for col in ("temperature_2m", "apparent_temperature"):
            fc_h.hourly[col] = fc_h.hourly[col] + 3.0
        fc_h.daily["apparent_temperature_max"] = fc_h.daily["apparent_temperature_max"] + 3.0
        ph = plan.make_plan(fc_h, "2026-08-04", cls, twin=tw, routine=rt, fan_available=fan)
        safer = [h for h in range(24) if ORD[ph["hours"][h]["advice"]] < ORD[pp["hours"][h]["advice"]]]
        if safer:
            worse_when_cooler.append({"k": k, "cls": cls, "tmin": round(days[0][0], 1), "hours_safer_when_hotter": safer,
                                      "base": adv(pp), "hot": adv(ph)})
    R["random_plans"] = n
    R["random_violations"] = viol
    R["metamorphic_plus3C_hours_got_safer"] = worse_when_cooler

    # --- night-heat window: spec 23-07 of one night; builder mixes two nights ---------------------
    fcn = demo.synthetic_forecast([(27, 40)] * 3 + [(14, 22)] * 2, "2026-07-01")
    pn = plan.make_plan(fcn, "2026-07-04", "B")
    bt = pn["details"]["bedroom_t"]
    R["night_window_end_of_wave"] = {"night_heat": pn["night_heat"], "bed_00_06_min": round(min(bt[:7]), 2),
                                     "bed_23": bt[23], "used_min": pn["details"]["indoor_night_min"]}

    # --- routine profile interop: B5 hg_welford_t is {n, mean, m2} (guardian/c/hg_routine.h:13), pack = 'RT',1 + am + q + ... = 650 B
    am_true = np.array([0, 0, 0, 0, 0, 0, 0, 25, 40, 45, 45, 30, 20, 35, 5, 5, 20, 25, 30, 35, 30, 15, 10, 0], float)
    b5 = b"RT\x01" + b"".join(struct.pack("<3f", 7.0, a, 120.0) for a in am_true) + b"".join(struct.pack("<3f", 7.0, 30.0, 50.0) for _ in range(24))
    b5 = b5 + bytes(650 - len(b5))
    out = {}
    try:
        RoutineTemplate.from_band(b5); out["full_650B"] = "accepted"
    except Exception as e:
        out["full_650B"] = "raises %s: %s" % (type(e).__name__, e)
    t = RoutineTemplate.from_band(b5[3:3 + 576])
    out["decoded_active_minutes_from_B5_layout"] = [None if x != x else round(float(x), 1) for x in t.active_minutes]
    out["true_active_minutes"] = am_true.tolist()
    out["met_decoded"] = t.to_dict()["met"]
    out["wake_bed"] = [t.to_dict()["wake"], t.to_dict()["bed"]]
    R["routine_from_band_B5_layout"] = out
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    json.dump(R, open(os.path.join(HERE, "out", "plan_props.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(R, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
