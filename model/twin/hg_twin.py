"""Body Twin -- Python reference implementation (B3, Heat Guardian AI sprint).

Mirrors twin/c/hg_twin.c operation-for-operation in float32 so the C port can be checked to 1e-5
(in practice bit-exact). Spec: /home/claude/hg_ai/arch/ARCHITECTURE.md section 5 and
/home/claude/hg_ai/arch/briefs/B3_twin.md "Update rules".

Four learned things, nightly, bounded:
  rest_hr        <- rest_hr + 0.3*(p10_night_hr + 5 - rest_hr)            (>= 60 valid still sleep minutes)
  k_person       = capped gap gain (M4.1): g + 0.5*((t_read - core_offset - t1_5)/dT_5 - g), bounds 0.03..0.40,
                 phone reading, flux_valid, dT >= 0.5, sourced reading mode only (M4.3; default display-only)
  core_offset    <- off + 0.25*(t_read - core_now) on a reading (beta M4.2; dropped during a tier + 30 min, M4.4); x 0.70710678 every nightly update (half-life 2 d)
  c_bodyheat     <- c + 0.3*(LS slope of (T_air_meas - T_ref) on (T1 - T_air_meas) - c)   (>= 30 weighted points)
  t1_night_base  per hour of day: Welford mean (n capped at 30) of the day's mean T1 over >= 20
                 worn+still+T_air<28 minutes of that hour; NAN until n >= 3
Nothing nightly is learned when an alarm tier was on during the night, when worn != 2 for > 30 % of the
night, or when fewer than 60 night minutes were observed (no evidence of a night). The offset decay
always runs (it is time, not learning).

Not learnable on the band: sweat capacity (no sweat sensor), HR-core slope (no core reference) --
see REPORT_TWIN.md.
"""
import math
import struct
import zlib

import numpy as np

f = np.float32

# ---- bounds / defaults (ARCHITECTURE section 4.5 + 5) ----
REST_HR_DEF, REST_HR_MIN, REST_HR_MAX = f(70.0), f(40.0), f(100.0)
K_DEF, K_MIN, K_MAX = f(0.12), f(0.03), f(0.40)
# Capped gap gain rule variants (C: -DHG_TWIN_K_RULE=n). DECISIONS M4.1: params["k_person"] is the "capped gap
# gain" -- it learns the wrist-core gap per degC of dT incl. the axial drop, NOT the physical K (results/k_diag.json).
# 0 = ARCHITECTURE 5 as written, bound 0.40 (default). 1 = upper bound 1.5. 2 = never learned.
K_RULE_SPEC, K_RULE_KEFF, K_RULE_OFF = 0, 1, 2
K_MAX_BY_RULE = {0: f(0.40), 1: f(1.5), 2: f(0.40)}
OFF_DEF, OFF_MIN, OFF_MAX = f(0.0), f(-0.8), f(0.8)
C_DEF, C_MIN, C_MAX = f(0.15), f(0.0), f(0.4)

# ---- rule constants ----
G_REST = f(0.3)            # rest_hr EMA gain
REST_SLEEP_TO_SEATED = f(5.0)  # +5 bpm: sleeping floor -> seated rest (Meade 2024 design choice)
P_REST = f(0.1)            # 10th percentile
MIN_SLEEP_MIN = 60         # >= 60 valid still sleep minutes
G_K = f(0.5)               # K gain on a reading
MIN_DT_READING = f(0.5)    # dT_5min >= 0.5 degC for a K update
BETA_OFF = f(0.25)         # DECISIONS M4.2 (HTT beta sweep peak; was 0.35 from REPORT 5b C1)
# DECISIONS M4.3: 0 display-only (default; reading moves core_offset only, the capped gap gain is never learned),
# 1 sourced: t_core = t_read + ORAL_TO_CORE before both rules. +0.14 degC = core-minus-oral bias 0.14 +- 0.37,
# LoA -0.60..+0.90, electronic oral vs pill, 19 adults (Rajbhandary & Nallathambi 2021, arXiv:2108.00537);
# alternative 0.36 degC rectal-minus-oral, glass, 116 inpatients (Smith 2003, BMC Nursing 2:1, doi 10.1186/1472-6955-2-1).
READING_MODE_DISPLAY, READING_MODE_SOURCED = 0, 1
READING_MODE = READING_MODE_DISPLAY
ORAL_TO_CORE = f(0.14)
TIER_HOLDOFF_MIN = 30      # DECISIONS M4.4 / T3 F10
DECAY_OFF = f(0.70710678)  # 2-day half-life, one step per nightly update
G_C = f(0.3)               # c_bodyheat EMA gain
MIN_C_WEIGHT = f(30.0)     # >= 30 OUT-walking minutes (or one phone room reading = weight 30)
ROOM_READING_WEIGHT = f(30.0)
T1_MIN_PER_HOUR = 20       # >= 20 qualifying minutes in an hour
T1_N_CAP = 30              # Welford n cap (forgetting)
T1_N_VALID = 3             # NAN until n >= 3
T_AIR_BASELINE_MAX = f(28.0)
STILL_G = f(0.002)         # still: a_std <= 0.002 g (MC section 4e)
ACTIVE_G = f(0.02)         # ACTIVE / walking: a_std > 0.02 g (R3 section 3.4)
HR_LO, HR_BINS = 40, 64    # histogram 40..104 bpm, 1-bpm bins, uint8 counts with halving
NIGHT_MIN_OBS = 60
NIGHT_BAD_FRAC_NUM, NIGHT_BAD_FRAC_DEN = 3, 10  # worn != 2 for > 30 % of the night -> freeze
T1_OK_LO, T1_OK_HI = f(25.0), f(42.0)
TREAD_LO, TREAD_HI = f(34.0), f(40.0)
CORE_LO, CORE_HI = f(34.0), f(42.0)
TAIR_LO, TAIR_HI = f(-20.0), f(60.0)
CD_NONE = -32768

LOC_HOME, LOC_TRANSIT, LOC_OUT = 0, 1, 2

# ---- file layout (little-endian) ----
MAGIC = 0x4857544E   # 'HWTN'
VERSION = 4                            # v4 (B5-v7) adds the Guardian Exception sums; v3 (calm, M9.5) and v2 still load
VERSION_V3 = 3
VERSION_V2 = 2
HDR_FMT = "<IHH"                       # magic, version, length            8 B
TWIN_FMT = "<4f24fB"                   # hg2_twin_t packed               113 B
EXT_FMT = "<24B24h"                    # t1_n[24], t1_pre_cd[24]          72 B
CALM_FMT = "<fB"                       # calm_f20 (NAN if n == 0), calm_n   5 B
TAIL_FMT = "<I"                        # save_count (crc follows)         4 + 4 B
FIXED_LEN_V2 = struct.calcsize(HDR_FMT) + struct.calcsize(TWIN_FMT) + struct.calcsize(EXT_FMT) + 8
EXC_FMT = "<ff"                        # exc_sxx (>= 0), exc_sxy; 0/0 = not learned   8 B (v4)
FIXED_LEN_V3 = FIXED_LEN_V2 + struct.calcsize(CALM_FMT)   # 206
FIXED_LEN = FIXED_LEN_V3 + struct.calcsize(EXC_FMT)       # 214
EXC_MAX = f(1.0e7)
CALM_OFFSET = struct.calcsize(HDR_FMT) + struct.calcsize(TWIN_FMT) + struct.calcsize(EXT_FMT)   # 193
CALM_MIN, CALM_MAX = f(36.8), f(37.7)   # = B5 HG_A_BASE_MIN/MAX
FILE_MAX = 900


def _fin(x):
    return x is not None and math.isfinite(float(x))


def _clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


CD_LO, CD_HI = 2500, 4200   # valid centi-degree range of a staged hourly mean (25..42 degC)


def _cd(x):
    """float32 degC -> int16 centi-degrees, round half up via floor (same as C floorf(x*100+0.5)), clamped to int16."""
    v = np.floor(f(x) * f(100.0) + f(0.5))
    if not math.isfinite(v):
        return CD_NONE
    return int(min(max(v, -32767.0), 32767.0))


def _cd_ok(v):
    return CD_LO <= int(v) <= CD_HI


class BodyTwin:
    PARAM_NAMES = ["rest_hr", "k_person", "core_offset", "c_bodyheat", "t1_night_base", "days_learned"]

    def __init__(self, k_rule=K_RULE_SPEC, beta=None, reading_mode=None):
        self.k_rule = k_rule
        self.reading_mode = READING_MODE if reading_mode is None else reading_mode
        self.min_since_tier = 255
        self.k_max = K_MAX_BY_RULE[k_rule]
        self.beta = BETA_OFF if beta is None else f(beta)
        self.params = self.defaults()
        # persistent learning state that lives in the file next to hg2_twin_t
        self.t1_n = np.zeros(24, np.uint8)
        self.t1_pre_cd = np.full(24, CD_NONE, np.int64)
        self._reset_acc()
        self.tier_now = 0
        self.air_ref = f(np.nan)
        self.save_count = 0
        self.last_frozen = 0
        self.calm_f20 = f(np.nan)   # Guardian design-A calm baseline (M9.5), owned by B5, persisted here
        self.calm_n = 0
        self.exc_sxx = f(0.0); self.exc_sxy = f(0.0)   # B5-v7: Guardian Exception-DRINK sums, persisted (v4)

    # ------------------------------------------------------------------ defaults
    @staticmethod
    def defaults():
        return dict(rest_hr=REST_HR_DEF, k_person=K_DEF, core_offset=OFF_DEF, c_bodyheat=C_DEF,
                    t1_night_base=np.full(24, np.nan, np.float32), days_learned=0)

    def reset_defaults(self):
        self.params = self.defaults()
        self.t1_n[:] = 0
        self.t1_pre_cd[:] = CD_NONE
        self._reset_acc()

    def _reset_acc(self):
        self.hist = np.zeros(HR_BINS, np.int64)   # uint8 semantics
        self.hist_n = 0                            # uint16 saturating
        self.cur_h = 255
        self.cur_sum = f(0.0)
        self.cur_cnt = 0
        self.today_cd = np.full(24, CD_NONE, np.int64)
        self.c_sxx = f(0.0); self.c_sxy = f(0.0); self.c_w = f(0.0)
        self.night_n = 0; self.night_bad = 0; self.night_alarm = 0
        self.rd_pending = 0
        self.rd = (f(np.nan), f(np.nan), f(np.nan), f(np.nan), 0)

    # ------------------------------------------------------------------ Guardian calm baseline (M9.5)
    def set_calm(self, calm_f20, calm_n):
        n = int(calm_n) & 0xFF
        v = f(calm_f20) if calm_f20 is not None else f(np.nan)
        if n == 0 or not math.isfinite(v):
            self.calm_f20, self.calm_n = f(np.nan), 0
        else:
            self.calm_f20, self.calm_n = _clamp(v, CALM_MIN, CALM_MAX), n

    def get_calm(self):
        return (self.calm_f20 if self.calm_n else f(np.nan)), self.calm_n

    # ------------------------------------------------------------------ Guardian Exception sums (B5-v7, = hg_twin_set/get_exc)
    def set_exc(self, sxx, sxy):
        a, b = f(sxx), f(sxy)
        self.exc_sxx, self.exc_sxy = (a, b) if _exc_ok(a, b) else (f(0.0), f(0.0))

    def get_exc(self):
        return self.exc_sxx, self.exc_sxy, int(self.exc_sxx > 0)

    # ------------------------------------------------------------------ per-minute context
    def note_tier(self, tier_on):
        self.tier_now = 1 if tier_on else 0

    def set_air_ref(self, t_ref):
        self.air_ref = f(t_ref) if _fin(t_ref) else f(np.nan)

    # ------------------------------------------------------------------ per-minute ingest
    def _flush_hour(self):
        if self.cur_h < 24 and self.cur_cnt >= T1_MIN_PER_HOUR and self.today_cd[self.cur_h] == CD_NONE:
            mean = self.cur_sum / f(self.cur_cnt)
            self.today_cd[self.cur_h] = _cd(mean)
        self.cur_h = 255; self.cur_sum = f(0.0); self.cur_cnt = 0

    def ingest_minute(self, m):
        """m: dict with hg2_in_t fields (t1_c, t2_c, t_air_c, rh_pct, hr_bpm, hr_quality, pi_pct, a_std_g,
        worn, minute_of_day) + asleep, location, hr_valid; optional tier_on, air_ref (set the context first,
        exactly like the C caller does with hg_twin_note_tier / hg_twin_set_air_ref)."""
        if "tier_on" in m:
            self.note_tier(m["tier_on"])
        if self.tier_now:
            self.min_since_tier = 0
        elif self.min_since_tier < 255:
            self.min_since_tier += 1
        if "air_ref" in m:
            self.set_air_ref(m["air_ref"])
        t1 = f(m.get("t1_c", np.nan)); tair = f(m.get("t_air_c", np.nan)); hr = f(m.get("hr_bpm", np.nan))
        astd = f(m.get("a_std_g", np.nan))
        worn = int(m.get("worn", 0)) & 0xFF
        tod = int(m.get("minute_of_day", 0xFFFF)) & 0xFFFF
        asleep = 1 if int(m.get("asleep", 0)) & 0xFF else 0
        loc = int(m.get("location", 0)) & 0xFF
        hr_valid = 1 if int(m.get("hr_valid", 0)) & 0xFF else 0

        tod_known = tod < 1440
        night = asleep or (tod_known and (tod >= 1380 or tod < 360))
        if night:
            if self.night_n < 65535:
                self.night_n += 1
            if worn != 2 and self.night_bad < 65535:
                self.night_bad += 1
            if self.tier_now:
                self.night_alarm = 1
        if self.tier_now or worn != 2:
            return
        still = math.isfinite(astd) and astd >= f(0.0) and astd <= STILL_G
        # 1. night HR floor histogram
        if asleep and hr_valid and still and math.isfinite(hr) and hr >= f(HR_LO) and hr < f(HR_LO + HR_BINS):
            b = int(hr - f(HR_LO))
            if b > HR_BINS - 1:
                b = HR_BINS - 1
            if self.hist[b] >= 255:
                self.hist >>= 1
            self.hist[b] += 1
            if self.hist_n < 65535:
                self.hist_n += 1
        t1_ok = math.isfinite(t1) and T1_OK_LO <= t1 <= T1_OK_HI
        tair_ok = math.isfinite(tair) and TAIR_LO < tair < TAIR_HI
        # 2. per-hour T1 baseline (worn, still, T_air < 28)
        if tod_known and still and t1_ok and tair_ok and tair < T_AIR_BASELINE_MAX:
            h = tod // 60
            if h != self.cur_h:
                self._flush_hour()
                self.cur_h = h
            if self.cur_cnt < 255:          # sum and count saturate together (stuck clock, T3 F2)
                self.cur_sum = self.cur_sum + t1
                self.cur_cnt += 1
        # 3. c_bodyheat: OUT and walking, against a reference air temperature
        if loc == LOC_OUT and math.isfinite(astd) and astd > ACTIVE_G and t1_ok and tair_ok and math.isfinite(self.air_ref):
            x = t1 - tair; y = tair - self.air_ref
            self.c_sxx = self.c_sxx + x * x
            self.c_sxy = self.c_sxy + x * y
            self.c_w = self.c_w + f(1.0)

    def ingest_room_reading(self, t_room, t_air_meas, t1):
        t_room, t_air_meas, t1 = f(t_room), f(t_air_meas), f(t1)
        if not (math.isfinite(t_room) and math.isfinite(t_air_meas) and math.isfinite(t1)):
            return
        if not (TAIR_LO < t_room < TAIR_HI and TAIR_LO < t_air_meas < TAIR_HI and T1_OK_LO <= t1 <= T1_OK_HI):
            return
        x = t1 - t_air_meas; y = t_air_meas - t_room
        self.c_sxx = self.c_sxx + ROOM_READING_WEIGHT * x * x
        self.c_sxy = self.c_sxy + ROOM_READING_WEIGHT * x * y
        self.c_w = self.c_w + ROOM_READING_WEIGHT

    # ------------------------------------------------------------------ readings
    def ingest_reading(self, t_read, t_stamp, t1_5min, dT_5min, core_now, flux_valid):
        """Phone oral/tympanic reading (0x13 field 0). t_stamp is informational: the caller must reject
        readings older than 15 min before calling (the C API has no clock)."""
        self.rd = (f(t_read), f(t1_5min), f(dT_5min), f(core_now), 1 if flux_valid else 0)
        self.rd_pending = 1
        self.rd_stamp = t_stamp

    def commit_reading(self):
        """Apply a pending reading now (same-day readings are what helps, REPORT 5b). Returns 1 if changed.
        Dropped while an alarm tier is on or < 30 min after it ended (DECISIONS M4.4)."""
        if not self.rd_pending:
            return 0
        self.rd_pending = 0
        self._sanitize()
        if self.tier_now or self.min_since_tier < TIER_HOLDOFF_MIN:
            return 0
        p = self.params
        t_raw, t1, dT, core_now, fv = self.rd
        old = (p["k_person"], p["core_offset"])
        if not (math.isfinite(t_raw) and TREAD_LO <= t_raw <= TREAD_HI):
            return 0
        if self.reading_mode == READING_MODE_SOURCED:
            t_read = t_raw + ORAL_TO_CORE
            if (fv and math.isfinite(dT) and dT >= MIN_DT_READING and dT < f(15.0)
                    and math.isfinite(t1) and T1_OK_LO <= t1 <= T1_OK_HI):
                g_obs = (t_read - p["core_offset"] - t1) / dT       # capped gap gain (M4.1)
                g = p["k_person"] + G_K * (g_obs - p["k_person"])
                if self.k_rule != K_RULE_OFF:
                    p["k_person"] = _clamp(g, K_MIN, self.k_max)
        else:
            t_read = t_raw                                         # display-only (M4.3)
        if math.isfinite(core_now) and CORE_LO <= core_now <= CORE_HI:
            off = p["core_offset"] + self.beta * (t_read - core_now)
            p["core_offset"] = _clamp(off, OFF_MIN, OFF_MAX)
        self.sanitize()        # bounds re-checked after every update, before hg2_set_twin
        return int((p["k_person"], p["core_offset"]) != old)

    # ------------------------------------------------------------------ nightly
    def sanitize(self):
        """Bounds + learning-state consistency (mirror of hg_twin_sanitize)."""
        p = self.params
        for k, d, lo, hi in (("rest_hr", REST_HR_DEF, REST_HR_MIN, REST_HR_MAX), ("k_person", K_DEF, K_MIN, self.k_max),
                             ("core_offset", OFF_DEF, OFF_MIN, OFF_MAX), ("c_bodyheat", C_DEF, C_MIN, C_MAX)):
            v = f(p[k])
            p[k] = d if not math.isfinite(v) else _clamp(v, lo, hi)
        b = p["t1_night_base"]
        for h in range(24):
            n = int(self.t1_n[h])
            if n >= T1_N_VALID:
                bad = not (math.isfinite(b[h]) and T1_OK_LO <= b[h] <= T1_OK_HI)
            elif n == 0:
                bad = False
            else:
                bad = not _cd_ok(self.t1_pre_cd[h])
            if bad:
                n = 0
            n = min(n, T1_N_CAP)
            self.t1_n[h] = n
            if n == 0 or n >= T1_N_VALID:
                self.t1_pre_cd[h] = CD_NONE
            if n < T1_N_VALID:
                b[h] = np.nan
            if self.today_cd[h] != CD_NONE and not _cd_ok(self.today_cd[h]):
                self.today_cd[h] = CD_NONE
        if self.cur_h > 23:
            self.cur_h = 255; self.cur_sum = f(0.0); self.cur_cnt = 0
        if self.calm_n == 0 or not (math.isfinite(self.calm_f20) and CALM_MIN <= self.calm_f20 <= CALM_MAX):
            self.calm_f20, self.calm_n = f(np.nan), 0
        if not _exc_ok(self.exc_sxx, self.exc_sxy):
            self.exc_sxx, self.exc_sxy = f(0.0), f(0.0)
        if not (math.isfinite(self.c_sxx) and math.isfinite(self.c_sxy) and math.isfinite(self.c_w)
                and self.c_w >= 0 and self.c_sxx >= 0):
            self.c_sxx = f(0.0); self.c_sxy = f(0.0); self.c_w = f(0.0)

    _sanitize = sanitize

    def _p10(self):
        total = int(self.hist.sum())
        target = P_REST * f(total)
        cum = 0
        for b in range(HR_BINS):
            c = int(self.hist[b])
            if c and f(cum + c) >= target:
                return f(HR_LO + b) + (target - f(cum)) / f(c)
            cum += c
        return f(HR_LO + HR_BINS)

    def frozen_reason(self):
        if self.night_alarm:
            return "alarm"
        if self.night_n < NIGHT_MIN_OBS:
            return "no_night"
        if self.night_bad * NIGHT_BAD_FRAC_DEN > self.night_n * NIGHT_BAD_FRAC_NUM:
            return "not_worn"
        return ""

    def nightly_update(self):
        """Returns dict of changes (empty if nothing changed). Resets the nightly accumulators."""
        p = self.params
        ch = {}
        if self.rd_pending and self.commit_reading():
            ch["reading"] = 1
        self._sanitize()
        before = self._snapshot()
        self._flush_hour()
        # offset decay: always
        p["core_offset"] = _clamp(p["core_offset"] * DECAY_OFF, OFF_MIN, OFF_MAX)
        why = self.frozen_reason()
        self.last_frozen = {"": 0, "alarm": 1, "no_night": 2, "not_worn": 3}[why]
        if not why:
            # rest HR
            if self.hist_n >= MIN_SLEEP_MIN:
                p10 = self._p10()
                r = p["rest_hr"] + G_REST * (p10 + REST_SLEEP_TO_SEATED - p["rest_hr"])
                p["rest_hr"] = _clamp(r, REST_HR_MIN, REST_HR_MAX)
                ch["p10_night_hr"] = float(p10)
            # T1 hourly baseline
            b = p["t1_night_base"]
            for h in range(24):
                cd = int(self.today_cd[h])
                if cd == CD_NONE:
                    continue
                n = int(self.t1_n[h])
                if n == 0:
                    self.t1_pre_cd[h] = cd; self.t1_n[h] = 1
                elif n == 1:
                    self.t1_pre_cd[h] = (int(self.t1_pre_cd[h]) + cd) // 2; self.t1_n[h] = 2   # floor, == C mean2_cd_
                elif n == 2:
                    m2 = f(self.t1_pre_cd[h]) / f(100.0)
                    x = f(cd) / f(100.0)
                    b[h] = m2 + (x - m2) / f(3.0)
                    self.t1_n[h] = 3; self.t1_pre_cd[h] = CD_NONE
                else:
                    n2 = n + 1 if n < T1_N_CAP else T1_N_CAP
                    x = f(cd) / f(100.0)
                    b[h] = b[h] + (x - b[h]) / f(n2)
                    self.t1_n[h] = n2
            # c_bodyheat
            if self.c_w >= MIN_C_WEIGHT and self.c_sxx > f(1e-3):
                c_ls = self.c_sxy / self.c_sxx
                if math.isfinite(c_ls):
                    c = p["c_bodyheat"] + G_C * (_clamp(c_ls, f(-1.0), f(1.0)) - p["c_bodyheat"])
                    p["c_bodyheat"] = _clamp(c, C_MIN, C_MAX)
            p["days_learned"] = min(int(p["days_learned"]) + 1, 255)
        else:
            ch["frozen"] = why
        self.sanitize()        # bounds re-checked after every update, before hg2_set_twin
        after = self._snapshot()
        for k in before:
            if not _same(before[k], after[k]):
                ch[k] = after[k]
        self._reset_acc()
        return ch

    def _snapshot(self):
        p = self.params
        return dict(rest_hr=p["rest_hr"], k_person=p["k_person"], core_offset=p["core_offset"],
                    c_bodyheat=p["c_bodyheat"], t1_night_base=p["t1_night_base"].copy(),
                    days_learned=p["days_learned"], t1_n=self.t1_n.copy(), t1_pre_cd=self.t1_pre_cd.copy())

    def changed_flag(self, ch):
        return int(any(k not in ("frozen", "p10_night_hr") for k in ch))

    # ------------------------------------------------------------------ persistence
    def to_bytes(self, routine=b"", save_count=None):
        p = self.params
        sc = self.save_count if save_count is None else save_count
        length = FIXED_LEN + len(routine)
        body = struct.pack(HDR_FMT, MAGIC, VERSION, length)
        body += struct.pack(TWIN_FMT, p["rest_hr"], p["k_person"], p["core_offset"], p["c_bodyheat"],
                            *[float(x) for x in p["t1_night_base"]], int(p["days_learned"]))
        body += struct.pack(EXT_FMT, *[int(x) for x in self.t1_n], *[int(x) for x in self.t1_pre_cd])
        body += struct.pack(CALM_FMT, float(self.calm_f20) if self.calm_n else float("nan"), int(self.calm_n))
        body += struct.pack(EXC_FMT, float(self.exc_sxx), float(self.exc_sxy))
        body += bytes(routine) + struct.pack(TAIL_FMT, sc)
        return body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF)

    @classmethod
    def from_bytes(cls, buf):
        """Returns (twin, routine_bytes, save_count, ok). On any failure: defaults, b'', 0, False."""
        t = cls()
        try:
            if len(buf) < FIXED_LEN_V2 or len(buf) > FILE_MAX:
                raise ValueError("size")
            magic, ver, length = struct.unpack_from(HDR_FMT, buf, 0)
            if magic != MAGIC or ver not in (VERSION, VERSION_V3, VERSION_V2) or length != len(buf):
                raise ValueError("header")
            fixed = FIXED_LEN if ver == VERSION else FIXED_LEN_V3 if ver == VERSION_V3 else FIXED_LEN_V2
            if len(buf) < fixed:
                raise ValueError("size")
            if zlib.crc32(buf[:-4]) & 0xFFFFFFFF != struct.unpack_from("<I", buf, len(buf) - 4)[0]:
                raise ValueError("crc")
            o = struct.calcsize(HDR_FMT)
            v = struct.unpack_from(TWIN_FMT, buf, o); o += struct.calcsize(TWIN_FMT)
            e = struct.unpack_from(EXT_FMT, buf, o); o += struct.calcsize(EXT_FMT)
            calm, calm_n = float("nan"), 0
            if ver != VERSION_V2:
                calm, calm_n = struct.unpack_from(CALM_FMT, buf, o); o += struct.calcsize(CALM_FMT)
                calm = f(calm)
                if (not math.isnan(calm)) if calm_n == 0 else not (math.isfinite(calm) and CALM_MIN <= calm <= CALM_MAX):
                    raise ValueError("calm")
            exs, exy = f(0.0), f(0.0)
            if ver == VERSION:
                exs, exy = (f(x) for x in struct.unpack_from(EXC_FMT, buf, o)); o += struct.calcsize(EXC_FMT)
                if not _exc_ok(exs, exy):
                    raise ValueError("exc")
            rlen = length - fixed
            routine = bytes(buf[o:o + rlen]); o += rlen
            sc = struct.unpack_from(TAIL_FMT, buf, o)[0]
            p = dict(rest_hr=f(v[0]), k_person=f(v[1]), core_offset=f(v[2]), c_bodyheat=f(v[3]),
                     t1_night_base=np.array(v[4:28], np.float32), days_learned=int(v[28]))
            if not _params_in_bounds(p, e[:24], e[24:], t.k_max):
                raise ValueError("bounds")
            t.params = p
            t.t1_n = np.array(e[:24], np.uint8); t.t1_pre_cd = np.array(e[24:], np.int64)
            t.save_count = sc
            t.calm_f20, t.calm_n = (f(calm), int(calm_n)) if calm_n else (f(np.nan), 0)
            t.exc_sxx, t.exc_sxy = exs, exy
            return t, routine, sc, True
        except (ValueError, struct.error):
            return cls(), b"", 0, False

    def params_vector(self):
        """30 floats in a fixed order (used by the golden trace): rest, K, off, c, base[24], days."""
        p = self.params
        return [float(p["rest_hr"]), float(p["k_person"]), float(p["core_offset"]), float(p["c_bodyheat"])] + \
            [float(x) for x in p["t1_night_base"]] + [float(p["days_learned"])]


def _exc_ok(sxx, sxy):   # = hg_twin.c exc_ok_
    return math.isfinite(sxx) and math.isfinite(sxy) and 0 <= sxx <= EXC_MAX and -EXC_MAX <= sxy <= EXC_MAX


def _same(a, b):
    if isinstance(a, np.ndarray):
        return a.shape == b.shape and bool(np.all((a == b) | (np.isnan(a.astype(float)) & np.isnan(b.astype(float)))))
    if isinstance(a, (float, np.floating)) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def _params_in_bounds(p, t1n, pre, k_max=K_MAX):
    for k, lo, hi in (("rest_hr", REST_HR_MIN, REST_HR_MAX), ("k_person", K_MIN, k_max),
                      ("core_offset", OFF_MIN, OFF_MAX), ("c_bodyheat", C_MIN, C_MAX)):
        if not (math.isfinite(p[k]) and lo <= p[k] <= hi):
            return False
    for h in range(24):          # learning-state consistency (T3 F3), same rules as hg_twin_unpack
        b = p["t1_night_base"][h]; n = t1n[h]
        if n > T1_N_CAP:
            return False
        if n >= T1_N_VALID:
            if not (math.isfinite(b) and T1_OK_LO <= b <= T1_OK_HI) or pre[h] != CD_NONE:
                return False
        else:
            if not math.isnan(b):
                return False
            if n == 0 and pre[h] != CD_NONE:
                return False
            if n > 0 and not _cd_ok(pre[h]):
                return False
    return True
