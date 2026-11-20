"""Wearer routine template for tomorrow (ARCHITECTURE §6 routine.py, §7.1 step 4).

A RoutineTemplate is 24 hourly slots of expected behaviour at HOME (the indoor trajectory):
met (ASHRAE units, clamped to the R1 §1.6 activity set), clo, asleep, fan, and the hours in
which the wearer usually goes out (``errand_hours``). Errands are not simulated inside the
indoor trajectory; plan.py evaluates a counterfactual errand at every hour instead.

Sources: met values R1 §1.6 (0.7 sleep, 0.82 lying/TV, 0.86 seated rest, 1.37 ADL, 1.76
cooking; never 1.1-1.2, R1 §7.4 finding 3); clo 0.4 at home, 0.6 in bed with a sheet, 0.5 out
(R1 §1.7). Default day: ARCHITECTURE §6 (wake 07:30, meals 08/13/20, chores 09-11, nap 14-16
p 0.5, errands 10-11 and 18-19 p 0.6, bed 23:00).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

import numpy as np

MET_SLEEP, MET_LYING, MET_REST, MET_ADL, MET_COOK = 0.7, 0.82, 0.86, 1.37, 1.76
CLO_HOME, CLO_BED, CLO_OUT = 0.4, 0.6, 0.5
PROFILE_BYTES = 650            # B5's STABLE FORMAT v1 (guardian/c/hg_routine.h, HG_ROUTINE_PACK_BYTES); B5 owns it
LEARNED_N = 3                  # a slot counts as learned when n >= 3 (hg_routine.h, HG_RT_LEARN_DAYS)
ACTIVE_MIN_AWAKE = 5.0         # an hour with >= 5 active minutes on average counts as awake (design choice)


@dataclass
class RoutineTemplate:
    met: np.ndarray                       # (24,) expected met at home
    clo: np.ndarray                       # (24,)
    asleep: np.ndarray                    # (24,) bool
    wake_minute: int                      # minute of day of the morning wake
    bed_minute: int                       # minute of day of going to bed
    errand_hours: list = field(default_factory=list)
    source: str = "default"
    active_minutes: np.ndarray | None = None

    # ---- constructors -------------------------------------------------------------------
    @classmethod
    def default(cls) -> "RoutineTemplate":
        met = np.full(24, MET_REST)
        met[9:11] = MET_ADL                       # chores 09-11
        met[7] = MET_ADL                          # 07:30 wake, washing (minute plan handles the half hour)
        met[8] = MET_ADL                          # breakfast
        met[12] = MET_COOK                        # lunch cooking
        met[13] = MET_ADL                         # lunch
        met[14:16] = MET_SLEEP                    # nap p 0.5 -> included (conservative-neutral: low met, still)
        met[19] = MET_COOK                        # dinner cooking
        met[20] = MET_ADL                         # dinner
        met[21:23] = MET_LYING                    # TV
        asleep = np.zeros(24, bool)
        asleep[:8] = True; asleep[23] = True; asleep[14:16] = True
        met[asleep] = MET_SLEEP
        met[7] = MET_ADL                          # wake 07:30: second half of 07 active
        clo = np.where(asleep, CLO_BED, CLO_HOME)
        clo[14:16] = CLO_HOME                     # nap on the sofa
        return cls(met=met, clo=clo, asleep=asleep, wake_minute=450, bed_minute=1380,
                   errand_hours=[10, 18], source="default")

    @classmethod
    def from_active_minutes(cls, am: np.ndarray, source: str) -> "RoutineTemplate":
        """Map mean active minutes per hour (a_std > 0.02 g, R3 §3.4) to met at home."""
        d = cls.default()
        am = np.asarray(am, dtype=float)
        known = ~np.isnan(am)
        if known.sum() < 12:                      # too little learned: keep the default
            d.source = source + " (insufficient, default used)"
            return d
        am = np.where(known, am, np.nan)
        awake = np.where(known, am >= ACTIVE_MIN_AWAKE, ~d.asleep)
        frac = np.clip(np.nan_to_num(am, nan=0.0) / 60.0, 0, 1)
        met = np.where(frac >= 0.33, MET_ADL, np.where(frac >= 0.10, MET_REST, MET_LYING))
        met = np.where(awake, met, MET_SLEEP)
        # wake = first awake hour from 04:00; bed = first asleep hour after 20:00
        order = list(range(4, 24))
        wake_h = next((h for h in order if awake[h]), 8)
        bed_h = next((h for h in range(20, 24) if not awake[h]), 23)
        asleep = ~awake
        clo = np.where(asleep & ((np.arange(24) < wake_h) | (np.arange(24) >= bed_h)), CLO_BED, CLO_HOME)
        errands = [h for h in (10, 18) if known[h] and am[h] >= 30]      # very active hour = likely out
        return cls(met=met, clo=clo, asleep=asleep, wake_minute=wake_h * 60, bed_minute=bed_h * 60,
                   errand_hours=errands or d.errand_hours, source=source, active_minutes=am)

    @classmethod
    def from_band(cls, profile_bytes: bytes) -> "RoutineTemplate":
        """Decode B5's persisted routine profile, STABLE FORMAT v1 (guardian/c/hg_routine.h, 650 B, LE):
        'R','T',1 | am[24]{f32 n, mean, m2} | q[24]{n, mean, m2} | maxq[24] i16 | wake_hist[7] u16 |
        sleep_on u16 | sleep_off u16 | sleep_valid u8 | n_wake u8 | wake_i u8 | days_learned u8 | XOR(0..648).
        Raises ValueError on a wrong length/magic/version/XOR (the caller then uses default())."""
        b = bytes(profile_bytes)
        if len(b) != PROFILE_BYTES:
            raise ValueError("routine profile must be %d bytes (B5 v1), got %d" % (PROFILE_BYTES, len(b)))
        if b[0:3] != b"RT\x01":
            raise ValueError("routine profile magic/version is not 'R','T',1")
        x = 0
        for v in b[:649]:
            x ^= v
        if x != b[649]:
            raise ValueError("routine profile XOR check failed")
        w = struct.unpack_from("<144f", b, 3)
        maxq = struct.unpack_from("<24h", b, 579)
        wake_hist = struct.unpack_from("<7H", b, 627)
        sleep_on, sleep_off = struct.unpack_from("<2H", b, 641)
        sleep_valid, n_wake, _wake_i, days = b[645], b[646], b[647], b[648]
        am = np.array([w[3 * h + 1] if w[3 * h] >= LEARNED_N else np.nan for h in range(24)])
        q = np.array([w[72 + 3 * h + 1] if w[72 + 3 * h] >= LEARNED_N else np.nan for h in range(24)])
        t = cls.from_active_minutes(am, "band profile (B5 v1, %d days learned)" % days)
        if n_wake:
            t.wake_minute = int(np.median(np.array(wake_hist[:min(n_wake, 7)], dtype=float)))
        elif sleep_valid:
            t.wake_minute = int(sleep_off)
        if sleep_valid:
            t.bed_minute = int(sleep_on)
        t.quiet_minutes = q
        t.max_quiet = np.array(maxq)
        return t

    @classmethod
    def from_log(cls, minutes_df) -> "RoutineTemplate":
        """From a minute log with columns minute_of_day and a_std_g (ACTIVE = a_std > 0.02 g)."""
        df = minutes_df
        if "day" not in df:
            df = df.assign(day=np.arange(len(df)) // 1440)
        act = (df["a_std_g"].to_numpy() > 0.02).astype(float)
        hour = (df["minute_of_day"].to_numpy() // 60).astype(int)
        per = {}
        for d, h, a in zip(df["day"].to_numpy(), hour, act):
            per[(d, h)] = per.get((d, h), 0.0) + a
        am = np.full(24, np.nan)
        for h in range(24):
            v = [per[k] for k in per if k[1] == h]
            if v:
                am[h] = float(np.mean(v))
        return cls.from_active_minutes(am, "log")

    # ---- minute plan for the physics --------------------------------------------------
    def minute_plan(self):
        """Arrays of 1440: met, clo, asleep (wake/bed honoured at minute resolution)."""
        met = np.repeat(self.met, 60).astype(float)
        clo = np.repeat(self.clo, 60).astype(float)
        asleep = np.repeat(self.asleep, 60)
        w = self.wake_minute
        if 0 < w < 1440:
            asleep[:w] = True; asleep[w:(w // 60 + 1) * 60] = False
            met[:w] = np.where(np.arange(w) >= (w // 60) * 60, MET_SLEEP, met[:w])
            met[w:(w // 60 + 1) * 60] = MET_ADL
        return met, clo, asleep

    def to_dict(self) -> dict:
        return {"source": self.source, "wake": "%02d:%02d" % divmod(self.wake_minute, 60),
                "bed": "%02d:%02d" % divmod(self.bed_minute, 60), "errand_hours": list(map(int, self.errand_hours)),
                "met": [round(float(x), 2) for x in self.met]}


def pack_band_profile(am_mean, q_mean=None, n=7, wake_hist=(), sleep_on=1380, sleep_off=450,
                      sleep_valid=0, days_learned=7) -> bytes:
    """Python mirror of B5's hg_routine_pack (test helper / phone tooling); m2 = 0, maxq = 0."""
    q_mean = np.zeros(24) if q_mean is None else q_mean
    vals = []
    for arr in (am_mean, q_mean):
        for h in range(24):
            vals += [float(n), float(arr[h]), 0.0]
    wh = list(wake_hist)[:7] + [0] * (7 - len(list(wake_hist)[:7]))
    body = (b"RT\x01" + struct.pack("<144f", *vals) + struct.pack("<24h", *([0] * 24)) + struct.pack("<7H", *wh)
            + struct.pack("<2H", sleep_on, sleep_off) + bytes([sleep_valid, len(list(wake_hist)[:7]), 0, days_learned]))
    x = 0
    for v in body:
        x ^= v
    return body + bytes([x])
