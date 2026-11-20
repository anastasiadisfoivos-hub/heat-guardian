#!/usr/bin/env python3
"""Body Twin week for the demo elder -- SIMULATION ONLY.   python3 -I tools/make_twin_week.py

1. Simulates 7 days of wear for Virtual Elder pid 90862 with the project's Virtual Elders simulator (sim/velders:
   build_person = her daily routine and a summer weather regime, Gagge-Ji two-node body, BandSensors = what the
   band's sensors read). The person is drawn fresh with draw_one(90862): no persons.parquet row, no sealed file read.
2. Runs the real Body Twin (twin/hg_twin.py, the float32 mirror of the band's hg_twin.c) on those minutes, minute by
   minute, with a nightly update at 03:30, exactly as eval_sim.run_person feeds it (band-side signals: HR when the
   PPG quality is 4, hr_valid = 3 of the last 5 minutes good, worn / asleep / location from the simulator's truth,
   no alarm tier during the week, no phone thermometer readings).
3. Writes
     tomorrow_engine/twin_learned_pid90862.json   the twin the Tomorrow Engine uses: her profile (age, sex, mass,
                                                  height, medicines: what the phone sets with `profile`) + what the
                                                  Body Twin learned (rest_hr, k_person, core_offset); sweat capacity
                                                  is not learnable on the band (no sweat sensor) -> engine default 0.44
     twin_week.json                               what the page shows (night-by-night rest HR, learned vs true values)
"""
import json
import math
import os
import sys

os.environ.setdefault("HG_SIM_VERSION", "v5")
SIM = os.environ.get("HG_SIM_ROOT", "/home/claude/hg_ai/sim")
TWIN = os.environ.get("HG_TWIN_ROOT", "/home/claude/wt_b15/twin")
sys.path.insert(0, SIM); sys.path.insert(0, TWIN)

import numpy as np                                     # noqa: E402
from velders.persons import draw_one                   # noqa: E402
from velders.population import simulate_chunk          # noqa: E402
from hg_twin import BodyTwin                           # noqa: E402

PID, DAYS, UPDATE_TOD = 90862, 7, 210
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)


def main():
    P = draw_one(PID)
    assert "sealed" not in json.dumps({k: str(v) for k, v in P.items()}).lower()
    Q = dict(P, person_id=32000)   # label only (the package stores ids as int16); every draw uses P["seed"] = seed + 90862
    (_pid, df, _ev, _ppg, day_types, regime), = simulate_chunk(([Q], DAYS))
    tw = BodyTwin()
    HR = df.HR_meas.values.astype(float); HQ = df.hr_quality.values.astype(int)
    q = []; nights = []
    for i, r in enumerate(df.itertuples(index=False)):
        hr = HR[i] if HQ[i] == 4 and np.isfinite(HR[i]) else float("nan")
        q.append(HQ[i] == 4); q = q[-5:]
        tw.ingest_minute(dict(t1_c=r.T1, t2_c=r.T2, t_air_c=r.T_air_meas, hr_bpm=hr, hr_quality=int(r.hr_quality),
                              a_std_g=r.a_std_g, worn=int(r.worn_truth), minute_of_day=int(r.minute_of_day),
                              asleep=int(r.asleep), location=int(r.location), hr_valid=int(sum(q) >= 3), tier_on=0,
                              air_ref=float("nan")))
        if int(r.minute_of_day) == UPDATE_TOD:
            ch = tw.nightly_update()
            nights.append(dict(night=len(nights) + 1, day=int(r.day), rest_hr=round(float(tw.params["rest_hr"]), 2),
                               p10_night_hr=ch.get("p10_night_hr"), frozen=ch.get("frozen", "")))
    p = tw.params
    base = [None if not math.isfinite(float(x)) else round(float(x), 2) for x in p["t1_night_base"]]
    night_h = [h for h in (0, 1, 2, 3, 4, 5) if base[h] is not None]
    t1_night_learned = round(float(np.mean([base[h] for h in night_h])), 2) if night_h else None
    sl = df[(df.asleep == 1) & (df.worn_truth == 2) & (df.a_std_g <= 0.002)]
    floor_true = float(np.percentile(sl.HR_true.values.astype(float), 10))   # same definition as the twin, on TRUE heart rate
    m = df[(df.asleep == 1) & (df.worn_truth == 2) & (df.minute_of_day < 360)]
    t1_night_sim = round(float(m.T1.mean()), 2) if len(m) else None
    out = dict(
        what="SIMULATION: 7 simulated days of wear, Virtual Elder pid %d; Body Twin = twin/hg_twin.py (mirror of hg_twin.c)" % PID,
        pid=PID, days=DAYS, regime=str(regime), day_types=[str(x) for x in day_types],
        defaults=dict(rest_hr=70.0, core_offset=0.0, k_person=0.12),
        nights=nights,
        learned=dict(rest_hr=round(float(p["rest_hr"]), 1), core_offset=round(float(p["core_offset"]), 2),
                     k_person=round(float(p["k_person"]), 3), c_bodyheat=round(float(p["c_bodyheat"]), 3),
                     days_learned=int(p["days_learned"]), t1_night_base=base, t1_night_mean_00_06=t1_night_learned),
        truth=dict(rest_hr_same_definition=round(floor_true + 5.0, 1), night_hr_floor_true=round(floor_true, 1),
                   rest_hr_drawn_seated=round(float(P["hr_rest"]), 1), t1_night_mean_00_06=t1_night_sim,
                   note="the twin's rest_hr = 10th percentile of her still sleeping heart rate + 5 bpm (hg_twin.py); "
                        "rest_hr_same_definition = the same on the simulator's TRUE heart rate over the week; "
                        "rest_hr_drawn_seated = velders draw_one hr_rest (a different quantity: awake, seated)"),
        not_learned="core_offset needs a phone thermometer reading (none this week); sweat capacity has no sensor on the band",
    )
    with open(os.path.join(ROOT, "twin_week.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    twin = dict(name="Virtual Elder pid %d, Body Twin learned over %d simulated days (twin/hg_twin.py)" % (PID, DAYS),
                age=round(float(P["age"]), 1), sex_m=int(P["sex_m"]), mass=round(float(P["mass_kg"]), 2),
                height=round(float(P["height_m"]), 3),
                med_flags=(1 if P["med_bb_nonsel"] or P["med_bb_sel"] else 0) | (2 if P["med_diuretic"] else 0)
                | (4 if P["med_antichol"] else 0) | (8 if P["med_ace_arb"] else 0),
                rest_hr=round(float(p["rest_hr"]), 1), k_person=round(float(p["k_person"]), 3),
                core_offset=round(float(p["core_offset"]), 2), sweat_capacity=0.44)
    with open(os.path.join(ROOT, "tomorrow_engine", "twin_learned_pid%d.json" % PID), "w", encoding="utf-8") as f:
        json.dump(twin, f, ensure_ascii=False, indent=1); f.write("\n")
    print(json.dumps(dict(nights=nights, learned=out["learned"], truth=out["truth"]), indent=1))


if __name__ == "__main__":
    main()
