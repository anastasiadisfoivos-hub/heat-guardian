"""CRAFTED synthetic person-days for the Guardian Loop (NOT the Virtual Elders simulator, NOT evidence about people).
Purpose: exercise every code path (sleep, wake, sitting, errands, shower/off, loose band, fans, hot rooms, buttons) so the
C build and the Python mirror can be compared minute by minute, and so the false-alarm machinery can be smoke-tested
before B1's SIM-DEV data exists. Every number produced from these traces is labelled CRAFTED.
"""
import math
import numpy as np
from trace_io import minute

def person(seed):
    r = np.random.default_rng(seed)
    return dict(profile=dict(age=float(r.uniform(65, 85)), sex_m=float(r.integers(0, 2)), bmi=float(r.uniform(21, 32)),
                             med_flags=int(r.choice([0, 0, 0, 1, 2, 4, 8, 3]))),
                twin=dict(rest_hr=float(r.uniform(58, 80)), k_person=0.12, core_offset=0.0, c_bodyheat=0.15, t1_night_base=[float("nan")] * 24),
                wake=int(r.normal(420, 30)), bed=int(r.normal(1380, 30)), seed=seed)

def days(p, n_days=1, scenario="ordinary", seed=None, time_known=True, events=True):
    """scenario: ordinary (indoor 26-29 C), heat (indoor 31-34 C, night >= 29), cool (22-25 C)"""
    r = np.random.default_rng(p["seed"] * 7919 + (seed or 0))
    rest = p["twin"]["rest_hr"]
    out = []
    zang = float(r.uniform(-20, 20)); hr = rest; t1 = 33.8; tair_lag = None
    for d in range(n_days):
        base, amp = {"ordinary": (27.5, 1.5), "heat": (32.5, 1.5), "cool": (23.5, 1.0)}[scenario]
        base += (0.3 * d if scenario == "heat" else 0.0)
        wake = p["wake"] + int(r.normal(0, 20)); bed = p["bed"] + int(r.normal(0, 20))
        errand = (int(r.uniform(600, 690)), int(r.uniform(30, 80))) if (events and r.random() < 0.6) else None
        shower = int(r.uniform(wake + 30, wake + 120)) if (events and r.random() < 0.7) else None
        loose = (int(r.uniform(800, 1100)), int(r.uniform(10, 60))) if (events and r.random() < 0.3) else None
        nap = (int(r.uniform(840, 900)), int(r.uniform(40, 110))) if (events and r.random() < 0.5) else None
        presses = set(int(x) for x in r.uniform(wake, bed, size=r.integers(0, 3)))
        for mod in range(1440):
            asleep = mod < wake or mod >= bed
            napping = nap is not None and nap[0] <= mod < nap[0] + nap[1]
            out_now = errand is not None and errand[0] <= mod < errand[0] + errand[1]
            tin = base + amp * math.sin(2 * math.pi * (mod - 960) / 1440 + math.pi / 2) * -1
            tair = (36.0 + r.normal(0, 0.3)) if (out_now and scenario == "heat") else (31.0 if out_now else tin)
            rh = 45 + 8 * math.sin(2 * math.pi * mod / 1440) + (-15 if out_now else 0)
            if asleep or napping: a = float(r.uniform(0.0005, 0.003)) if r.random() > 0.03 else float(r.uniform(0.02, 0.05))
            elif out_now: a = float(r.uniform(0.06, 0.15))
            else: a = float(r.uniform(0.003, 0.015)) if r.random() < 0.6 else float(r.uniform(0.025, 0.12))
            met_hr = rest - (6 if asleep else 0) + 140 * a + 0.8 * max(0.0, tair - 26)
            hr += 0.3 * (met_hr - hr) + r.normal(0, 2.0)
            zang = zang + (r.normal(0, 0.05) if (asleep or napping) else r.normal(0, 3.0))
            zang = max(-80, min(80, zang))
            worn_state = 2
            if shower is not None and shower <= mod < shower + 25: worn_state = 0
            if loose is not None and loose[0] <= mod < loose[0] + loose[1]: worn_state = 1
            t1_target = 33.6 + 0.25 * (tair - 27) + (0.4 if asleep else 0) if worn_state == 2 else (tair + 1.0 if worn_state == 0 else 32.0)
            t1 += (t1_target - t1) * (0.25 if worn_state != 1 else 0.6)
            t1s = [t1 + r.normal(0, 0.02) for _ in range(12)]
            dT = max(0.05, 0.35 * (t1 - tair)) if worn_state == 2 else (0.02 if worn_state == 0 else 0.15 * (t1 - tair))
            t2s = [v - dT + r.normal(0, 0.01) for v in t1s]
            tas = [tair + r.normal(0, 0.05) for _ in range(12)]
            zs = [zang + r.normal(0, 0.02 if (asleep or napping) else 1.5) for _ in range(12)]
            hrq = 4 if (worn_state == 2 and r.random() > (0.2 if a < 0.02 else 0.4)) else (1 if worn_state == 1 else (0 if worn_state == 0 else 2))
            dc = 110000 if worn_state == 2 else (1200 if worn_state == 0 else 140000)
            pi = float(r.uniform(0.3, 1.2)) if worn_state == 2 else (0.02 if worn_state == 1 else float("nan"))
            m = minute(mod=mod if time_known else 0xFFFF, t1=float(np.mean(t1s)), t2=float(np.mean(t2s)), tair=float(np.mean(tas)),
                       rh=float(rh), hr=float(hr) if hrq == 4 else float("nan"), hrq=hrq, pi=pi, astd=a,
                       apeak=1.0 + 3 * a, dc=dc, flat=0, button=1 if mod in presses else 0, charging=0, vbat=3.9,
                       ble=-1 if not out_now else 0, t1_5s=t1s, t2_5s=t2s, tair_5s=tas, zang=zs)
            m["truth"] = dict(asleep=asleep, out=out_now, worn=worn_state, day=d)
            out.append(m)
    return out
