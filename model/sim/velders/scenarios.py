"""Scenario library S1-S12 and the daily routine generator (SIMULATION).

Each person gets a spin-up day (day 0, discarded) plus `days` days. Weather regime per person:
  with p = 0.65 a 5-day S2 heat wave (Sakka 2007) preceded by 0-2 PRE days and starting on
  day 2-4, followed by POST days; otherwise an S1 ordinary summer week (with p = 0.3 of a 1-2 day
  warm spell of PRE days). Behavioural overlays (S3-S11) are drawn per day from the person's own
  seed stream (seed + id, stream 1), so sealed and dev persons never share draws.

Routine template (R3 §3.3; ARCH §6 defaults): wake ~07:00 / bed ~23:00 with per-person anchors,
meals 08/13:30/20, chores 09-11, nap 14:30 with p_nap, errand 10-12 or 18-20 with p_errand.
Every anchor is jittered by N(0, jitter_sd 20-40 min) per day, giving IS 0.7-0.9 (checked in
VALIDATION.md). Met values come only from the clamp list (ARCH §3.3).

Activity classes: 0 sleep, 1 lying, 2 sit, 3 stand, 4 adl, 5 walk.
Locations: 0 home, 1 transit, 2 out.
"""
from __future__ import annotations

import numpy as np

from .weather import hourly_weather
from .indoor import person_indoor, hourly_to_minutes

MPD = 1440
# activity -> (met, class)
ACT = {
    "sleep": (0.70, 0), "lying": (0.82, 1), "tv": (0.82, 2), "sit": (0.86, 2), "stand": (0.95, 3),
    "laundry": (1.26, 4), "adl": (1.37, 4), "cook": (1.76, 4), "walk_in": (1.80, 5), "walk_out": (2.20, 5),
}
ACT_NAMES = list(ACT.keys())
ACT_IDX = {k: i for i, k in enumerate(ACT_NAMES)}
# 1-min SD of |a| (g) per activity (R2 §6.4 / R3 §3.4: ACTIVE > 0.02 g, still <= 0.002 g)
ASTD = {"sleep": (0.0008, 0.0006), "lying": (0.002, 0.001), "tv": (0.004, 0.002), "sit": (0.006, 0.003),
        "stand": (0.012, 0.005), "laundry": (0.035, 0.010), "adl": (0.040, 0.012), "cook": (0.045, 0.012),
        "walk_in": (0.10, 0.02), "walk_out": (0.13, 0.03)}
# z-angle mean / sd (deg) per activity: lying ~0 (forearm horizontal), sitting arm in lap, walking arm hanging
ZANG = {"sleep": (5, 25), "lying": (10, 20), "tv": (-15, 15), "sit": (-20, 15), "stand": (-50, 15),
        "laundry": (-30, 25), "adl": (-30, 25), "cook": (-25, 20), "walk_in": (-65, 15), "walk_out": (-65, 15)}

EVENT_TYPES = ["core38", "core385", "hr_drift_onset", "core_inflection", "anomaly", "loose", "off", "errand",
               "nap", "shower", "fan", "ac_respite", "heatwave_day"]


def regime(rng, days):
    """Day-type list of length days+1 (index 0 = spin-up)."""
    if rng.uniform() < 0.65:
        start = int(rng.integers(2, 5))          # first S2 day (day index 2..4)
        n_pre = int(rng.integers(1, 3))
        types = []
        for d in range(days + 1):
            if d < start - n_pre:
                types.append("S1")
            elif d < start:
                types.append("PRE")
            elif d < start + 5:
                types.append(f"S2_{d - start + 1}")
            elif d < start + 7:
                types.append("POST")
            else:
                types.append("S1")
        return types, "S2"
    types = ["S1"] * (days + 1)
    if rng.uniform() < 0.3:
        s = int(rng.integers(2, days))
        for d in range(s, min(days + 1, s + int(rng.integers(1, 3)))):
            types[d] = "PRE"
    return types, "S1"


class Timeline:
    """Per-person minute-level plan (all arrays length (days+1)*1440)."""

    def __init__(self, n_min):
        z = lambda dt=np.float32: np.zeros(n_min, dt)
        self.act = np.full(n_min, ACT_IDX["sit"], np.int8)
        self.loc = z(np.int8)
        self.room = z(np.int8)        # 0 living, 1 bedroom, 2 outdoors, 3 AC place
        self.asleep = z(np.int8)
        self.fan = z(np.int8)
        self.sun = z(np.int8)          # sun on the lid
        self.drink = z()
        self.extra_loss = z()          # g/min (diuretic diuresis)
        self.worn = np.full(n_min, 2, np.int8)
        self.r_gap = z()
        self.flash = z()               # T1 evaporative flash drop, C
        self.rh_wet = z(np.int8)        # shower: island wet
        self.still = z(np.int8)         # anomaly-imposed stillness
        self.slip = z(np.int8)
        self.events = []


def _draw_block(rng, pa):
    r = rng.uniform()
    if r < 0.25 * pa:
        return "adl"
    if r < 0.37 * pa:
        return "walk_in"
    if r < 0.37 * pa + 0.25:
        return "stand"
    if r < 0.37 * pa + 0.6:
        return "sit"
    return "tv"


def _set(arr, a, b, val, n):
    a = int(max(0, min(n, a))); b = int(max(0, min(n, b)))
    if b > a:
        arr[a:b] = val


def build_person(P: dict, days: int, seed: int):
    """P: dict of scalars for one person. Returns (timeline, weather dict, day types, regime)."""
    rng = np.random.default_rng([seed, 1])
    D = days + 1
    n = D * MPD
    types, reg = regime(rng, days)
    # weather with 7 extra spin-up days for the indoor model
    pre = ["S1"] * 7
    W = hourly_weather(pre + types, rng)
    ind = person_indoor(P, W["t_out"], W["s_rad"], W["rh_out"])
    sl = slice(7 * 24, (7 + D) * 24 + 1)
    hourly = {k: np.append(np.asarray(v)[sl], np.asarray(v)[-1])[:D * 24 + 1]
              for k, v in dict(t_out=W["t_out"], rh_out=W["rh_out"], s_rad=W["s_rad"], t_in=ind["t_in"],
                               rh_in=ind["rh_in"], t_bed=ind["t_bed"], rh_bed=ind["rh_bed"]).items()}
    mins = {k: hourly_to_minutes(v)[:n].astype(np.float32) for k, v in hourly.items()}
    tl = Timeline(n)
    tl.day_types = types
    tl.regime = reg
    jit = P["jitter_sd_min"]
    hot_days = [t.startswith("S2") or t == "PRE" for t in types]
    # anomaly day (S9): 1 in 10 persons x 1 day
    anomaly_day, anomaly_kind = -1, None
    if rng.uniform() < 0.10:
        anomaly_day = int(rng.integers(2, D))
        anomaly_kind = "late_wake" if rng.uniform() < 0.5 else "stillness"
    # person's hour-of-day activity propensity (0..1): morning peak, afternoon trough, evening shoulder
    hrs = np.arange(24)
    m_pk = rng.uniform(9, 11.5); e_pk = rng.uniform(17.5, 19.5)
    prof = (np.exp(-0.5 * ((hrs - m_pk) / 1.5) ** 2) + rng.uniform(0.4, 0.8) * np.exp(-0.5 * ((hrs - e_pk) / 1.5) ** 2)) * P["active_scale"]
    prof = np.clip(prof + 0.1, 0, 1)
    template = [_draw_block(rng, prof[b // 6]) for b in range(144)]     # the person's usual day, 10-min blocks
    prev_bed = None
    for d in range(D):
        o = d * MPD
        W_ = P["wake_min"] + rng.normal(0, jit)
        B_ = P["bed_min"] + rng.normal(0, jit)
        if anomaly_day == d and anomaly_kind == "late_wake":
            W_ = max(W_, 11 * 60 + rng.uniform(0, 30))
            tl.events.append(("anomaly", d, o + 0, o + int(W_)))
        if prev_bed is None:
            prev_bed = o + B_ - MPD           # ABSOLUTE minute index of last night's bedtime
        # night sleep from last night's bedtime to this morning's wake, in the bedroom (S3: hot bedroom ->
        # more wake minutes). Round-3 fix: prev_bed was measured from yesterday's midnight but added to today's
        # (o + prev_bed > o + W_), so no stored day had a night (tester T1 finding B1).
        _set(tl.act, prev_bed, o + W_, ACT_IDX["sleep"], n)
        _set(tl.asleep, prev_bed, o + W_, 1, n)
        _set(tl.room, prev_bed, o + W_, 1, n)
        seg_bed = mins["t_bed"][max(0, int(prev_bed)):max(1, int(o + W_))]
        t_bed_night = float(seg_bed.mean()) if seg_bed.size else float(mins["t_bed"][o])
        # wake after sleep onset: ~8 % baseline, +5.5 points in a >= 30 C bedroom (Yan 2022 via R1 §3.3); the
        # round-1 extra +2 points/C above 27 C had no source and was removed in round 3
        wake_frac = 0.08 + (0.055 if t_bed_night >= 30 else 0.0)
        a, b = int(prev_bed), int(o + W_)
        if b > a:
            k = rng.uniform(size=b - a) < wake_frac / 12.5       # bouts of 5-19 min (mean 12) -> awake fraction ~wake_frac
            for s in np.nonzero(k)[0]:
                L = int(rng.integers(5, 20))
                _set(tl.act, a + s, a + s + L, ACT_IDX["lying"], n)
                _set(tl.asleep, a + s, a + s + L, 0, n)
        # awake baseline: sitting / tv / standing / short indoor walks, following the person's own fixed
        # hour-of-day activity profile (older people have routines: IS 0.7-0.9, R3 §3.3)
        aw0, aw1 = int(o + W_), int(o + B_)
        shift = int(rng.normal(0, jit))
        for t0 in range(aw0, aw1, 10):
            blk = int(((t0 - o - shift) // 10) % 144)
            name = template[blk] if rng.uniform() > 0.15 else _draw_block(rng, prof[blk // 6])
            L = 10 if name != "walk_in" else int(rng.integers(3, 8))
            _set(tl.act, t0, t0 + L, ACT_IDX[name], n)
            if name == "walk_in":
                _set(tl.act, t0 + L, t0 + 10, ACT_IDX["stand"], n)
        # meals with cooking and drinks
        for mt, cook in ((W_ + 35, 10), (13.5 * 60, 40), (20 * 60, 30)):
            mt = mt + (rng.normal(0, jit) if mt > W_ + 35 else 0)
            _set(tl.act, o + mt - cook, o + mt, ACT_IDX["cook"], n)
            _set(tl.act, o + mt, o + mt + 25, ACT_IDX["sit"], n)
            i = int(o + mt + 10)
            if 0 <= i < n:
                tl.drink[i] += rng.uniform(150, 250)
            if P["med_diuretic"] and mt < 10 * 60:
                # diuretic dose at breakfast: morning deficit 0.5-1.5 % over 3 h (S8, R1 §5)
                tot = P["diuretic_deficit_pct"] / 100.0 * P["mass_kg"] * 1000.0
                _set(tl.extra_loss, o + mt, o + mt + 180, tot / 180.0, n)
        if rng.uniform() < 0.6:
            i = int(o + W_ + 5)
            if 0 <= i < n:
                tl.drink[i] += 150.0
        # chores 09:00-11:00, active minutes scaled by frailty
        c0 = max(o + 9 * 60 + rng.normal(0, jit), o + W_ + 20)     # never before wake (late-wake S9 days)
        L = int(rng.uniform(60, 120) * P["active_scale"])
        t = int(c0)
        while t < c0 + L:
            name = ["adl", "laundry", "adl", "stand"][int(rng.integers(0, 4))]
            dur = int(rng.integers(5, 20))
            _set(tl.act, t, t + dur, ACT_IDX[name], n)
            t += dur
        # nap (S5)
        if rng.uniform() < P["p_nap"]:
            ns = o + 14.5 * 60 + rng.normal(0, jit)
            nl = rng.uniform(45, 100)
            _set(tl.act, ns, ns + nl, ACT_IDX["sleep"], n)
            _set(tl.asleep, ns, ns + nl, 1, n)
            _set(tl.room, ns, ns + nl, 1, n)
            tl.events.append(("nap", d, int(ns), int(ns + nl)))
        # errand (S4): fewer and earlier on hot days
        p_e = P["p_errand"] * (0.6 if hot_days[d] else 1.0)
        if d > 0 and rng.uniform() < p_e:
            morning = rng.uniform() < (0.8 if hot_days[d] else 0.6)
            es = o + (rng.uniform(10, 11.5) if morning else rng.uniform(18, 19.5)) * 60
            if es < o + W_ + 30:
                es = o + rng.uniform(18, 19.5) * 60
            el = rng.uniform(30, 90)
            _set(tl.act, es, es + 5, ACT_IDX["walk_out"], n); _set(tl.loc, es, es + 5, 1, n)
            _set(tl.act, es + 5, es + el - 5, ACT_IDX["walk_out"], n); _set(tl.loc, es + 5, es + el - 5, 2, n)
            # inside shops: standing part of the time
            for t0 in range(int(es + 5), int(es + el - 5), 10):
                if rng.uniform() < 0.4:
                    _set(tl.act, t0, t0 + 10, ACT_IDX["stand"], n)
            _set(tl.act, es + el - 5, es + el, ACT_IDX["walk_out"], n); _set(tl.loc, es + el - 5, es + el, 1, n)
            _set(tl.room, es, es + el, 2, n)
            sun_frac = rng.uniform(0.2, 0.5)
            t0, t1 = int(es + 5), int(es + el - 5)
            sun_on = rng.uniform() < sun_frac
            while t0 < t1:
                L = max(1, int(rng.exponential(4.0 if sun_on else 4.0 * (1 - sun_frac) / sun_frac)))
                if sun_on:
                    _set(tl.sun, t0, min(t0 + L, t1), 1, n)
                t0 += L
                sun_on = not sun_on
            tl.events.append(("errand", d, int(es), int(es + el)))
        # AC respite (S7) on heat-wave days, p = 0.15
        if types[d].startswith("S2") and rng.uniform() < 0.15:
            st = o + (11 if rng.uniform() < 0.5 else 17) * 60
            _set(tl.act, st, st + 10, ACT_IDX["walk_out"], n); _set(tl.loc, st, st + 10, 1, n); _set(tl.room, st, st + 10, 2, n)
            _set(tl.act, st + 10, st + 130, ACT_IDX["sit"], n); _set(tl.loc, st + 10, st + 130, 2, n); _set(tl.room, st + 10, st + 130, 3, n)
            _set(tl.act, st + 130, st + 140, ACT_IDX["walk_out"], n); _set(tl.loc, st + 130, st + 140, 1, n); _set(tl.room, st + 130, st + 140, 2, n)
            tl.events.append(("ac_respite", d, int(st + 10), int(st + 130)))
        # anomaly: stillness 4 h at a usually active hour
        if anomaly_day == d and anomaly_kind == "stillness":
            st = o + rng.uniform(9.5, 11) * 60
            _set(tl.act, st, st + 240, ACT_IDX["tv"], n)
            _set(tl.loc, st, st + 240, 0, n); _set(tl.room, st, st + 240, 0, n)
            _set(tl.still, st, st + 240, 1, n)
            tl.events.append(("anomaly", d, int(st), int(st + 240)))
        prev_bed = o + B_
        if types[d].startswith("S2"):
            tl.events.append(("heatwave_day", d, o, o + MPD))
    # the last evening: bedtime of the final day to the end of the record
    _set(tl.act, prev_bed, n, ACT_IDX["sleep"], n)
    _set(tl.asleep, prev_bed, n, 1, n)
    _set(tl.room, prev_bed, n, 1, n)
    # fans (S6): hot afternoons 30-50 %, 1-4 h; hot nights 30 %
    if P["fan_available"]:
        p_aft = rng.uniform(0.3, 0.5)
        for d in range(D):
            o = d * MPD
            tin_aft = mins["t_in"][o + 13 * 60:o + 19 * 60]
            if tin_aft.size and tin_aft.mean() >= 30 and rng.uniform() < p_aft:
                fs = o + rng.uniform(13, 16) * 60
                fl = rng.uniform(60, 240)
                _set(tl.fan, fs, fs + fl, 1, n)
                tl.events.append(("fan", d, int(fs), int(fs + fl)))
            tb = mins["t_bed"][o:o + 6 * 60]
            if tb.size and tb.mean() >= 29 and rng.uniform() < 0.3:
                _set(tl.fan, o, o + rng.uniform(60, 300), 1, n)
        tl.fan[tl.loc > 0] = 0
    # band events (S10/S11): one off episode per day (shower 70 % / charging 30 %), loose 0.1/h
    for d in range(1, D):
        o = d * MPD
        evening = rng.uniform() < 0.6
        st = o + (rng.uniform(19, 21.5) if evening else rng.uniform(8.5, 10)) * 60
        if tl.loc[min(int(st), n - 1)] > 0 or tl.asleep[min(int(st), n - 1)] > 0:
            st = o + rng.uniform(19, 21) * 60
        dur = rng.uniform(20, 60)
        _set(tl.worn, st, st + dur, 0, n)
        shower = rng.uniform() < 0.7
        tl.events.append(("off", d, int(st), int(st + dur)))
        if shower:
            ss = int(st + rng.uniform(2, 8))
            tl.events.append(("shower", d, ss, ss + 10))
            # re-donned with wet skin: evaporative flash (R2 §6.1) + island wet (R2 §6.2)
            don = int(st + dur)
            fd, fl = rng.uniform(1, 3), int(rng.integers(2, 6))
            for k in range(fl):
                if don + k < n:
                    tl.flash[don + k] = fd * (1 - k / fl)
            _set(tl.rh_wet, don, don + int(rng.uniform(10, 25)), 1, n)
    t = MPD
    while t < n:
        gap = rng.exponential(600.0)          # 0.1 per hour
        t = int(t + gap)
        if t >= n:
            break
        L = min(int(rng.uniform(10, 120)), n - t)
        seg = tl.worn[t:t + L]
        if (seg == 2).all() and tl.asleep[t] == 0:
            tl.worn[t:t + L] = 1
            tl.r_gap[t:t + L] = rng.uniform(0.01, 0.04)
            tl.slip[t] = 1
            for s in np.nonzero(rng.uniform(size=L) < 0.05)[0]:
                tl.slip[t + s] = 1
            tl.events.append(("loose", t // MPD, t, t + L))
        t += L
    return tl, mins, hourly


def env_arrays(P: dict, tl: Timeline, mins: dict):
    """Minute arrays of the body environment, sensor context and truth labels for one person."""
    n = tl.act.shape[0]
    met_tab = np.array([ACT[k][0] for k in ACT_NAMES])
    cls_tab = np.array([ACT[k][1] for k in ACT_NAMES], np.int8)
    met = met_tab[tl.act]
    met = np.where(met >= 1.2, np.maximum(met * P["met_adl_mult"], 1.22), np.minimum(met * P["met_rest_mult"], 1.08))
    room = tl.room
    t_db = np.select([room == 0, room == 1, room == 2, room == 3], [mins["t_in"], mins["t_bed"], mins["t_out"], 23.0])
    rh = np.select([room == 0, room == 1, room == 2, room == 3], [mins["rh_in"], mins["rh_bed"], mins["rh_out"], 50.0])
    sun_body = (room == 2) & (mins["s_rad"] > 200)
    t_r = np.where(sun_body, t_db + 12.0 * mins["s_rad"] / 900.0, t_db)
    v_air = np.where(room == 2, 0.8, np.where(tl.fan > 0, 1.5, 0.1))
    asleep = tl.asleep
    hot_bed = (room == 1) & (t_db >= 28)
    clo = np.where(room == 2, 0.55, np.where(asleep > 0, np.where(hot_bed, 0.35, 0.6), 0.4)).astype(float)
    walking = cls_tab[tl.act] == 5
    h_out = np.where(tl.fan > 0, 22.0, np.where(walking, 12.0, 8.0))
    sun_dT = np.where(tl.sun > 0, 15.0 * mins["s_rad"] / 900.0 + 3.0, 0.0)   # lid sol-air excess (R2 §2.2: lid 45-60 C)
    return dict(t_db=t_db.astype(float), rh=rh.astype(float), t_r=t_r, v_air=v_air, met=met, clo=clo,
                act_class=cls_tab[tl.act], h_out=h_out, sun_dT=sun_dT)
