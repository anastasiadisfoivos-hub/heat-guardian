"""TwoNodeOlder — stateful Gagge-Ji two-node thermoregulation model for people aged 65-85,
1-min step, continuous across days, vectorised over persons (SIMULATION).

Base physics: Gagge, Stolwijk & Nishi 1971 two-node model with the older-adult control of
Ji et al. 2022 (Building Simulation 15:1815, doi 10.1007/s12273-022-0890-3), re-implemented line
by line from pythermalcomfort.models.two_nodes_gagge_ji (R1 §1.1, §1.4, §1.5). With every
feature switched off and Ji's default parameters the result equals pythermalcomfort to < 0.01 C
(tests/test_body.py).

Features layered on top (each can be switched off; sources in brackets):
  person      per-person thresholds, SkBF min/neutral/max, vasodilation gain (ARCH §3.3, R1 §1.4)
  omega       hard skin-wettedness cap omega_max x (1.0 at ADL, 0.75 at rest) replacing Ji's 0.85
              (R1 §2.1, §8.8; Kenney 2025 Table 2)
  frailty     thresholds +0.1 f, omega_max x(1-0.3 f), SkBF_max x(1-0.3 f) (ARCH §3.3; unvalidated)
  circadian   set-point rhythm (R1 §3.3): thermo-effector thresholds move with c(t) and the core is
              driven along c(t) by an energy-conserving core<->skin heat transfer; the nocturnal fall
              is attenuated when the room is > 26 C (R1 §3.3, §4 point 2)
  hydration   water balance; +0.10 C per % body-mass deficit as a threshold shift (Sawka 1996 lower
              bound, R1 §2.4); sweat suppression 0.3 x the young coefficient (Meade 2019)
  medication  R1 §5 parameterisation table (beta-blocker, anticholinergic; diuretic and ACE/ARB act
              only through water balance / thirst, which live in scenarios.py)
  acclim      seasonal acclimatisation ramp over 10 hot days (Notley 2020, R1 §4; V30)
  skinfix     R1 §7.4 finding 2 (skin node 1.0-1.3 C cold at 31-36 C): see SKIN_FIX below.

Heart rate (ARCH B1 brief): HR = rest + k_amb*max(0, T_exp-22) + k_core*excess_core
            + 35*(met-0.86)*reserve_factor + drift, where excess_core is the core rise above the
  person's circadian/set-point reference minus the 0.07 C/C ambient part that k_amb already
  contains (R1 §2.3: Meade's +1.0 bpm/C ambient and "~14 bpm/C core" are the SAME trend; adding
  both double-counts and V4 would fail by ~+20 bpm at 36 C -> conflict reported). Drift is driven by
  cardiovascular strain = SkBF fraction x wettedness fraction, accumulated over time above a strain
  limit (not by core), so its onset precedes the core inflection (R1 §3.2, V19).
"""
from __future__ import annotations

import os

import numpy as np

MET_FACTOR = 58.2
SBC = 0.000000056697
MET_CLAMP = (0.7, 0.82, 0.86, 0.95, 1.26, 1.37, 1.76, 1.8, 2.2)   # ARCH §3.3, R1 §1.6

JI_DEFAULTS = dict(
    c_sw=170.0, dil_gain=30.0, str_gain=0.375, a_cof=0.2,
    skbf_min=0.75, skbf_max=63.0, skbf_neutral=6.3,
    dil_thr=37.3, str_thr=33.25, thr_sw_core=37.0, thr_sw_skin=34.3, shiv_thr=36.7,
    evap_reg_max=400.0, sweat_eff_max=0.9, w_max=0.85,
    mass_kg=70.0, A_D=1.8258, omega_max=0.85, frailty=0.0,
    hr_rest=66.0, kappa_core=22.0, kappa_amb=1.0, reserve_factor=0.86, hr_max=150.0,
    circ_mesor=36.9, circ_amp=0.35, circ_nadir_h=4.5, tbw_L=32.0, acclim=0,
    med_bb_nonsel=0, med_bb_sel=0, med_antichol=0, med_diuretic=0, med_ace_arb=0,
    antichol_sweat_factor=0.5, bb_hr_factor=0.5,
)

YOUNG_OVERRIDES = dict(   # Gagge/ASHRAE 55 young column of R1 §1.4 (young twin, V21/V22/V24)
    dil_gain=120.0, str_gain=0.5, skbf_min=0.5, skbf_max=90.0, dil_thr=36.8, str_thr=33.7,
    thr_sw_core=36.8, thr_sw_skin=33.7, shiv_thr=36.8, evap_reg_max=500.0, omega_max=0.85,
    frailty=0.0, med_bb_nonsel=0, med_bb_sel=0, med_antichol=0, med_diuretic=0, med_ace_arb=0,
)

ALL_FEATURES = ("person", "omega", "frailty", "circadian", "hydration", "medication", "acclim", "skinfix")

# R1 §7.4 finding 2 -- chosen fix: a calibrated REPORT offset (below); physics untouched. Raising the clothing
# vapour resistance (I_CL_FIX < 0.45) was tried and rejected (raised core/HR, did not fix 36 C skin). Feasible
# offsets: tools/calib_sweeps.py skin; see VALIDATION.md row V3.
I_CL_FIX = 0.45
SKIN_REPORT_OFFSET_K = 0.12   # R1 §7.4 finding 2: calibrated REPORT offset (physics untouched), V3:
SKIN_REPORT_OFFSET_W = 1.2    #   T_skin_mean = T_skin_node + 0.12 (T_core - T_skin_node) + 1.2 max(0, w - 0.07)

# Wettedness frame conversion. Kenney 2025 measured omega_max with partitional calorimetry
# (E_max from their own h_e / clothing convention); the Gagge-Ji E_max uses a larger evaporative
# resistance (clo 0.4, i_cl 0.45, free convection), so the same physical limit is a larger w in
# this model. One global factor, calibrated against the published PSU critical limits V12/V13
# (tools/calib_sweeps.py omega), converts the measured omega_max into the model frame; the person
# distribution U(0.31, 0.57) and the rest/ADL ratio 0.75 are kept exactly (ARCH §3.3).
OMEGA_FRAME = 1.6
CLO_EFF_MULT = 1.0          # skin-node insulation multiplier (round-2 experiment)
MESOR_SETPOINT = False      # round 3 experiment: a mesor offset on the core->skin flow is cancelled by Ji shivering (36.7 C + circadian) at 22 C; off
HC_FLOOR = 2.5              # W/m2K, R1 §1.5 indoor free convection 2.5-3.4
OMEGA_REST_FACTOR = 0.85   # ARCH 0.75 fails R1 V2 (+1.05..+2.0 at 36 C); 1.0 makes V15 too tolerant; 0.85 = round-2 compromise
A_COF = 1.0   # skin weighting of the sweat drive (Ji a_cof = 0.2); see calib notes

# Circadian
CIRC_ATT_T0 = 26.0     # C, nocturnal fall attenuated above this room temperature (R1 §3.3)
CIRC_ATT_SPAN = 8.0    # C, attenuation reaches its floor at 26 + 8 * 0.75 = 32 C
CIRC_ATT_FLOOR = 0.25
CIRC_RELAX_MIN = 360.0 # min, effective rhythm relaxes back to the nominal one (no heat debt)
CIRC_FALL_H = 9.5      # sawtooth: fall peak->nadir 9.5 h, rise nadir->peak 14.5 h

# Hydration
HYD_THR_PER_PCT = 0.10       # C per % body-mass deficit (R1 §2.4, lower bound)
HYD_SWEAT_PER_PCT = 0.3 * 0.014   # young: 199 vs 211 W/m2 at ~4 % (Meade 2019) -> 1.4 %/%, x0.3

# Medication (R1 §5)
BB_NONSEL_CORE = 0.11
BB_SKBF_MAX = 0.85
ANTICHOL_CORE = 0.42
ANTICHOL_HR = 1.45

# Acclimatisation (V30 calibration, tools/calib_sweeps.py acclim)
ACCLIM_THR_SHIFT = 0.9
ACCLIM_OMEGA_GAIN = 0.5
ACCLIM_HOT_C = 30.0          # a day counts as hot if the exposure max >= 30 C
ACCLIM_DAYS = 10.0

# HR
HR_AMB_TAU = 5.0             # min, HR follows ambient within minutes (Rowell 1974, qualitative; design choice, M8)
HR_AMB_SPAN = 14.0            # C above 22: Meade 0.07 C/C trend spans 22-36 C only (M8, round 4)
HR_CORE_PER_AMB = 0.07       # C core per C ambient already inside kappa_amb (Meade 2024, R1 §2.3)
DRIFT_THR = 0.94             # strain limit: fraction of the wettedness cap in use (V19 calibration)
DRIFT_RATE = 5.0             # bpm/min per unit above the limit (x (1 + SkBF fraction))
DRIFT_TAU = 60.0             # min, drift decays when below the limit
DRIFT_MAX = 30.0
LOC_GAIN = 0.0               # L/(h m2) per C skin above LOC_THR (round-4 experiment; 0 = off)
LOC_THR = 35.0
SV_OLDER_ML = 68.0           # Minson 1998, older stroke volume at thermal tolerance
CV_HR_SCALE = 1.0
DRIFT_W0 = 1.0               # drift weight = (DRIFT_W0 + SkBF fraction)


# ---- Virtual Elders v5 (B1-v5, Nov 13): population-level adjustments fitted on Brighton/Waldock (REAL 65-76 y, 35 C chamber;
# spent exam, now calibration, DECISIONS M20) within literature bounds; see sim/VALIDATION_v5.md and sim/tools/brighton_calib.py.
# Empty dict = v4 behaviour (byte-identical). Selected by the environment variable HG_SIM_VERSION=v5 (or set by tools).
V5_FROZEN = {
    # per-person skin-core COUPLING heterogeneity (sensor/report layer; energy balance untouched): Brighton between-person SD of
    # rectal - 4-site mean skin is 0.43 C at rest / 0.48 C cycling (10 people, Control) vs v4 0.26 / 0.27 C for matched DEV
    # vectors; minus ~0.06 C thermistor noise -> extra SD 0.34 / 0.39 -> 0.36 C. Applied to T_skin_mean and (via T_deep) T1/T2.
    "SKIN_COUPLING_SD": 0.36,
    # extra SINGLE-SITE term for the wrist T1 (a single site spreads more than a 4-site mean: Brighton rectal - bicep SD 0.48 rest /
    # 0.62 cycling vs 0.43 / 0.48 for the mean) -> T1 total extra SD sqrt(0.36^2 + 0.35^2) = 0.50 C.
    "WRIST_SITE_SD": 0.35,
    "CLIP_SD": 3.0,
}
V5 = dict(V5_FROZEN) if os.environ.get("HG_SIM_VERSION", "v4") == "v5" else {}


def _apply_v5(p):
    """mutates the per-person parameter arrays (float) in place; keys: *_mult multiply, *_shift add"""
    for k, v in V5.items():
        if k.isupper(): continue
        if k.endswith("_mult") and k[:-5] in p: p[k[:-5]] = p[k[:-5]] * v
        elif k.endswith("_shift") and k[:-6] in p: p[k[:-6]] = p[k[:-6]] + v


def v5_skin_offsets(seeds):
    """v5 per-person offsets (C), deterministic from each person's own seed (new stream 7; v4 streams untouched).
    Returns (d_skin, d_wrist): T_skin_mean -= d_skin; T_deep(wrist) -= d_skin + d_wrist. Zeros when v5 is off."""
    seeds = np.atleast_1d(np.asarray(seeds)).astype(np.int64)
    if not V5 or "SKIN_COUPLING_SD" not in V5:
        return np.zeros(len(seeds)), np.zeros(len(seeds))
    z = np.array([np.random.default_rng([int(sd), 7]).standard_normal(2) for sd in seeds])
    c = V5.get("CLIP_SD", 3.0)
    z = np.clip(z, -c, c)
    return V5["SKIN_COUPLING_SD"] * z[:, 0], V5.get("WRIST_SITE_SD", 0.0) * z[:, 1]


def p_sat_torr(t):
    return np.exp(18.6686 - 4030.183 / (t + 235.0))


def p_sat_kpa(t):
    return p_sat_torr(t) * 0.133322


def circadian(minute_of_day, amp, nadir_h, fall_h=CIRC_FALL_H):
    """Sawtooth-cosine rhythm (R1 §3.3): minimum -amp at nadir, maximum +amp fall_h before it."""
    t = np.mod(np.asarray(minute_of_day, dtype=float) / 60.0 - nadir_h, 24.0)   # h since nadir
    rise_h = 24.0 - fall_h
    theta = np.where(t < rise_h, np.pi + np.pi * t / rise_h, np.pi * (t - rise_h) / fall_h)
    return amp * np.cos(theta)


class TwoNodeOlder:
    """Vectorised over N persons. person: dict of scalars or arrays (missing keys -> Ji defaults)."""

    def __init__(self, person: dict, features=ALL_FEATURES, young: bool = False,
                 t_core0=None, t_skin0=None, minute_of_day0: float = 0.0, ji_init: bool = False,
                 compute_ref: bool = True):
        self.features = set(features)
        par = dict(JI_DEFAULTS)
        if "person" in self.features or young:
            par.update({k: v for k, v in person.items() if k in JI_DEFAULTS})
        else:   # anthropometry is always the person's
            for k in ("mass_kg", "A_D"):
                if k in person:
                    par[k] = person[k]
        if young:
            par.update(YOUNG_OVERRIDES)
        n = 1
        for v in par.values():
            if np.ndim(v) > 0:
                n = max(n, len(v))
        self.n = n
        self.p = {k: np.broadcast_to(np.asarray(v, dtype=float), (n,)).copy() for k, v in par.items()}
        if V5 and not young:
            _apply_v5(self.p)
        self.young = young
        p = self.p
        f = p["frailty"] if "frailty" in self.features else np.zeros(n)
        self._f = f
        med = "medication" in self.features
        self.bb = (p["med_bb_nonsel"] + p["med_bb_sel"] > 0) if med else np.zeros(n, bool)
        self.bb_nonsel = (p["med_bb_nonsel"] > 0) if med else np.zeros(n, bool)
        self.antichol = (p["med_antichol"] > 0) if med else np.zeros(n, bool)
        self.skbf_max = p["skbf_max"] * (1 - 0.3 * f) * np.where(self.bb_nonsel, BB_SKBF_MAX, 1.0)
        self.sweat_factor = np.where(self.antichol, p["antichol_sweat_factor"], 1.0)
        self.thr_base = 0.1 * f + np.where(self.bb_nonsel, BB_NONSEL_CORE, 0.0) + np.where(self.antichol, ANTICHOL_CORE, 0.0)
        self.omega_person = p["omega_max"] * (1 - 0.3 * f)
        # state
        self.minute_of_day = float(minute_of_day0)
        if ji_init:
            tc0, ts0 = 36.49, 36.8
        else:
            tc0 = p["circ_mesor"] - 0.25 + (circadian(minute_of_day0, p["circ_amp"], p["circ_nadir_h"]) if "circadian" in self.features else 0)
            ts0 = 33.5
        self.t_core = np.full(n, tc0, dtype=float) if t_core0 is None else np.broadcast_to(np.asarray(t_core0, float), (n,)).copy()
        self.t_skin = np.full(n, ts0, dtype=float) if t_skin0 is None else np.broadcast_to(np.asarray(t_skin0, float), (n,)).copy()
        self.m_bl = p["skbf_neutral"].copy()
        self.alfa = np.full(n, 0.1)
        self.e_skin = None          # Ji init: 0.1 * met (set on first step)
        self.w = np.full(n, 0.06)
        self.h_cc = np.full(n, 3.0)
        self.h_r = np.full(n, 4.7)
        self.m = None
        self.c_eff = circadian(minute_of_day0, p["circ_amp"], p["circ_nadir_h"]) if "circadian" in self.features else np.zeros(n)
        self.c_prev_nom = self.c_eff.copy()
        self.deficit_g = np.zeros(n)
        self.hot_days = np.zeros(n)
        self.day_tmax = np.full(n, -99.0)
        self.t_exp = None
        self.drift = np.zeros(n)
        self.t_ref_neutral = np.full(n, 36.7)
        self.last = {}
        self.set_off = np.zeros(n)
        if compute_ref:
            self.t_ref_neutral = self._neutral_reference(person, young)
            if "circadian" in self.features and "person" in self.features and MESOR_SETPOINT:
                # Round 3 (V1): the drawn circadian mesor (ARCH §3.3: 36.9 + N(0, 0.15)) was only an initial value.
                # It is now the defended core level: the core->skin conductive flow is referenced to an offset so
                # that the thermoneutral (22 C, seated) 24-h mean core equals the person's mesor. Energy-conserving.
                sub = TwoNodeOlder(person, features=self.features, young=young, compute_ref=False, minute_of_day0=0.0)
                acc = np.zeros(n)
                env = dict(t_db=22.0, rh=45.0, v_air=0.1, t_r=22.0, clo=0.4, drink_mL=0.0,
                           met=np.where(np.asarray(person.get("met_rest_mult", 1.0)) > 0,
                                        np.minimum(0.86 * np.asarray(person.get("met_rest_mult", 1.0), float), 1.08), 0.86))
                for t in range(2 * 1440):
                    env["minute_of_day"] = t % 1440
                    o = sub.step(env)
                    if t >= 1440:
                        acc += o["T_core"]
                t24 = acc / 1440.0
                self.set_off = p["circ_mesor"] - t24
                self.t_ref_neutral = self.t_ref_neutral + self.set_off

    # ------------------------------------------------------------------ reference core
    def _neutral_reference(self, person, young):
        """Core at equilibrium, 22 C / 45 % / 0.1 m/s / clo 0.4 / met 0.86, circadian off:
        the HR model's set-point reference (Meade 2024 thermoneutral baseline, V1)."""
        feats = [f for f in self.features if f not in ("circadian", "hydration", "acclim")]
        ref = TwoNodeOlder(person, features=feats, young=young, compute_ref=False)
        env = dict(t_db=22.0, rh=45.0, v_air=0.1, t_r=22.0, met=0.86, clo=0.4, drink_mL=0.0)
        for _ in range(720):
            ref.step(env)
        return ref.t_core

    # ------------------------------------------------------------------ step
    def step(self, env: dict) -> dict:
        p, n = self.p, self.n
        tdb = np.broadcast_to(np.asarray(env["t_db"], float), (n,))
        tr = np.broadcast_to(np.asarray(env.get("t_r", env["t_db"]), float), (n,))
        rh = np.broadcast_to(np.asarray(env["rh"], float), (n,))
        v = np.broadcast_to(np.asarray(env.get("v_air", 0.1), float), (n,))
        met = np.broadcast_to(np.asarray(env["met"], float), (n,))
        clo = np.broadcast_to(np.asarray(env.get("clo", 0.4), float), (n,))
        drink = np.broadcast_to(np.asarray(env.get("drink_mL", 0.0), float), (n,))
        extra_loss = np.broadcast_to(np.asarray(env.get("extra_water_loss_g", 0.0), float), (n,))
        standing = np.broadcast_to(np.asarray(env.get("standing", met >= 0.95), bool), (n,))
        mod = env.get("minute_of_day", None)
        if mod is None:
            mod = self.minute_of_day
        self.minute_of_day = float(np.mod(mod + 1.0, 1440.0))
        feats = self.features

        vp = rh / 100.0 * p_sat_torr(tdb)            # torr, as pythermalcomfort
        air_speed = np.maximum(v, 0.1)
        if self.e_skin is None:
            self.e_skin = 0.1 * met
            self.m = met * MET_FACTOR
        mass, A_D = p["mass_kg"], p["A_D"]

        # ---- circadian set point
        if "circadian" in feats:
            c_nom = circadian(mod, p["circ_amp"], p["circ_nadir_h"])
            dc = c_nom - self.c_prev_nom
            dc = np.where(np.abs(dc) > 0.5, 0.0, dc)
            att = np.clip(1.0 - (tdb - CIRC_ATT_T0) / CIRC_ATT_SPAN, CIRC_ATT_FLOOR, 1.0)
            dc_eff = np.where(dc < 0, dc * att, dc) + (c_nom - self.c_eff) / CIRC_RELAX_MIN
            self.c_prev_nom = c_nom
            c_shift = self.c_eff + dc_eff
        else:
            dc_eff = np.zeros(n)
            c_shift = np.zeros(n)
        # ---- hydration shift
        deficit_pct = np.maximum(self.deficit_g, 0.0) / (mass * 1000.0) * 100.0
        hyd_shift = HYD_THR_PER_PCT * deficit_pct if "hydration" in feats else np.zeros(n)
        # ---- acclimatisation
        if "acclim" in feats:
            a = np.where(p["acclim"] > 0, np.minimum(self.hot_days / ACCLIM_DAYS, 1.0), 0.0)
        else:
            a = np.zeros(n)
        shift = c_shift + hyd_shift + self.thr_base - ACCLIM_THR_SHIFT * a
        t_cr0_dil = p["dil_thr"] + shift
        t_sk0_cons = p["str_thr"] + 0.0
        t_cr0_sw = p["thr_sw_core"] + shift
        t_sk0_sw = p["thr_sw_skin"] + (0.1 * self._f) - ACCLIM_THR_SHIFT * a
        t_cr0_sh = p["shiv_thr"] + c_shift

        # ---- clothing / heat transfer (Ji / ASHRAE)
        r_clo = 0.155 * clo * (CLO_EFF_MULT if "skinfix" in feats else 1.0)
        f_a_cl = np.where(clo < 0.5, 1.0 + 0.2 * clo, 1.05 + 0.1 * clo)
        lr = 2.2
        i_cl = np.where(clo > 0, I_CL_FIX if "skinfix" in feats else 0.45, 1.0)
        if "omega" in feats:
            act_fac = np.where(met < 1.2, OMEGA_REST_FACTOR, 1.0)
            w_max = np.minimum(OMEGA_FRAME * self.omega_person * act_fac * (1.0 + ACCLIM_OMEGA_GAIN * a), 1.0)
            evap_max = p["evap_reg_max"]
        else:
            acc = (p["acclim"] > 0) & ("acclim_ji" in feats)
            w_max = np.where(acc, 1.0, p["w_max"])
            evap_max = np.where(acc, 1.25, 1.0) * p["evap_reg_max"]
        m_rsw_max = evap_max / 0.68 * p["sweat_eff_max"] * self.sweat_factor

        h_t = self.h_r + self.h_cc
        r_a = 1.0 / (f_a_cl * h_t)
        t_op = (self.h_r * tr + self.h_cc * tdb) / h_t
        t_cl = (r_a * self.t_skin + r_clo * t_op) / (r_a + r_clo)
        rad_f = np.where(standing, 0.77, 0.7)
        h_r = self.h_r
        conv = np.zeros(n, bool)
        for _ in range(150):
            h_r_new = 4.0 * 0.97 * SBC * ((t_cl + tr) / 2.0 + 273.15) ** 3.0 * rad_f
            h_r = np.where(conv, h_r, h_r_new)
            h_t = h_r + self.h_cc
            r_a = 1.0 / (f_a_cl * h_t)
            t_op = (h_r * tr + self.h_cc * tdb) / h_t
            t_cl_new = (r_a * self.t_skin + r_clo * t_op) / (r_a + r_clo)
            newly = np.abs(t_cl_new - t_cl) < 0.01
            t_cl = np.where(conv, t_cl, t_cl_new)
            conv = conv | newly
            if conv.all():
                break
        self.h_r = h_r
        d_tcl_air = t_cl - tdb
        h_cc_next = np.where(air_speed < 0.2,
                             np.where(d_tcl_air > 0, 2.5 * np.abs(d_tcl_air) ** 0.16, 2.5 * np.abs(d_tcl_air) ** 0.41),
                             8.6 * air_speed ** 0.53)
        if "person" in feats:
            # Gao's free-convection law -> 0 as T_cl -> T_db, which switches evaporation off whenever the
            # clothing crosses air temperature (found by the monotonicity test at 38-40 C). Floor at the low
            # end of R1 §1.5's indoor range (2.5 W/m2K) and the ASHRAE activity term 5.66 (met-0.85)^0.39.
            h_cc_next = np.maximum(h_cc_next, np.maximum(HC_FLOOR, 5.66 * np.maximum(met - 0.85, 0.0) ** 0.39))
        q_sensible = (self.t_skin - t_op) / (r_a + r_clo)
        m = self.m
        q_res = 0.0023 * m * (44.0 - vp)
        c_res = 0.0014 * m * (34.0 - tdb)
        hf_cs = (self.t_core - self.t_skin - self.set_off) * (5.28 + 1.163 * self.m_bl)
        s_core = m - hf_cs - q_res - c_res
        s_skin = hf_cs - q_sensible - self.e_skin
        tc_sk = 0.97 * self.alfa * mass
        tc_cr = 0.97 * (1 - self.alfa) * mass
        # circadian forcing: move core along dc_eff, energy taken from / given to the skin node
        s_circ = dc_eff * tc_cr * 60.0 / A_D
        s_core = s_core + s_circ
        s_skin = s_skin - s_circ
        self.t_skin = self.t_skin + s_skin * A_D / (tc_sk * 60.0)
        self.t_core = self.t_core + s_core * A_D / (tc_cr * 60.0)
        if "circadian" in feats:
            self.c_eff = self.c_eff + dc_eff
        self.h_cc = h_cc_next
        storage = s_core + s_skin       # W/m2 (energy balance check)

        # ---- skin blood flow
        t_cr_dil = np.maximum(0, self.t_core - t_cr0_dil)
        t_sk_cons = np.maximum(0, t_sk0_cons - self.t_skin)
        m_bl = (p["skbf_neutral"] + p["dil_gain"] * t_cr_dil) / (1 + p["str_gain"] * t_sk_cons)
        # round 4 (experiment, off by default): LOCAL skin-temperature-driven vasodilation (local-heating / NO
        # pathway), independent of core; its cardiac-output demand is converted to HR below.
        loc = LOC_GAIN * np.maximum(0.0, self.t_skin - LOC_THR) if ("person" in feats and LOC_GAIN > 0) else 0.0
        m_bl = m_bl + loc
        m_bl = np.minimum(self.skbf_max, m_bl)
        m_bl = np.maximum(p["skbf_min"], m_bl)
        self.m_bl = m_bl
        t_sk_sw = np.maximum(0, self.t_skin - t_sk0_sw)
        t_cr_sw = np.maximum(0, self.t_core - t_cr0_sw)
        self.alfa = 0.0417737 + 0.7451832 / (m_bl + 0.5854417)
        hyd_sweat = (1.0 - HYD_SWEAT_PER_PCT * deficit_pct) if "hydration" in feats else 1.0
        m_rsw = (self.sweat_factor * hyd_sweat * p["c_sw"] *
                 ((1 - self.alfa) * t_cr_sw + (self.alfa + (A_COF if "person" in feats else p["a_cof"])) * t_sk_sw) * np.exp(t_sk_sw / 10.7))
        m_rsw = np.minimum(m_rsw, m_rsw_max)
        e_rsw = 0.68 * m_rsw
        r_e_cl = r_clo / (lr * i_cl)
        r_e_a = 1.0 / (lr * f_a_cl * self.h_cc)
        r_total = r_e_cl + r_e_a
        e_max = (p_sat_torr(self.t_skin) - vp) / r_total
        e_max_safe = np.where(np.abs(e_max) < 1e-9, 1e-9, e_max)
        p_rsw = e_rsw / e_max_safe
        he_n = 1.0 / r_total
        w_dif = 1.0 / (2.0 + 2.46 * he_n)
        wp = w_dif + (1 - w_dif) * p_rsw
        wp_safe = np.where(np.abs(wp) < 1e-12, 1e-12, wp)
        w = (np.sqrt(2 * wp ** 2 + 1) - 1) / wp_safe
        w = np.minimum(w, w_max)
        p_rsw = (w - w_dif) / (1.0 - w_dif)
        e_rsw = np.maximum(0, p_rsw * e_max)
        e_diff = np.maximum(0, w * e_max - e_rsw)
        cond = e_max < 0
        w = np.where(cond, 0.0, w)
        e_diff = np.where(cond, 0.0, e_diff)
        e_rsw = np.where(cond, 0.0, e_rsw)
        self.w = w
        self.e_skin = e_rsw + e_diff
        t_cr_sh = np.maximum(0, t_cr0_sh - self.t_core)
        met_shiv = 19.4 * t_cr_sh * t_sk_cons + 50 * t_cr_sh + 0.5 * t_sk_cons
        self.m = met * MET_FACTOR + met_shiv

        # sweat produced: regulatory drive, limited to what the capped wettedness can evaporate
        eff = 1.0 - 0.5 * w ** 2
        m_sweat = np.minimum(m_rsw, e_rsw / 0.68 / np.maximum(eff, 0.5))
        # ---- water balance (g)
        resp_water = q_res * A_D * 60.0 / 2430.0                       # g/min
        insens_water = e_diff * A_D * 60.0 / 2430.0
        sweat_water = m_sweat * A_D / 60.0
        urine = np.where(self.deficit_g > 0, np.maximum(0.3, 1.0 - 0.3 * deficit_pct), 1.0)   # mL/min
        metab_water = 0.25
        self.deficit_g = self.deficit_g + sweat_water + insens_water + resp_water + urine + extra_loss - drink - metab_water
        # surplus water is excreted within ~1 h
        self.deficit_g = np.where(self.deficit_g < 0, self.deficit_g * (1 - 1 / 60.0), self.deficit_g)
        if "hydration" not in feats:
            self.deficit_g[:] = 0.0

        # ---- acclimatisation day counter
        self.day_tmax = np.maximum(self.day_tmax, tdb)
        if int(mod) == 1439:
            self.hot_days = self.hot_days + (self.day_tmax >= ACCLIM_HOT_C)
            self.day_tmax[:] = -99.0

        # ---- heart rate
        if self.t_exp is None:
            self.t_exp = np.array(tdb, dtype=float)
        self.t_exp = self.t_exp + (tdb - self.t_exp) / HR_AMB_TAU
        amb = np.maximum(0.0, self.t_exp - 22.0)
        t_ref = self.t_ref_neutral + shift
        # linear (not clipped at 0): a max(0, .) clip biases the population-mean HR upward when some persons are
        # above and others below the ambient-explained core (round 2, V4); floor -0.5 C keeps HR sane when cool
        excess = np.maximum(self.t_core - t_ref - HR_CORE_PER_AMB * np.minimum(amb, HR_AMB_SPAN), -0.5)
        s_lin = np.clip((m_bl - p["skbf_min"]) / np.maximum(self.skbf_max - p["skbf_min"], 1e-6), 0, 1)
        w_frac = np.clip(w / np.maximum(w_max, 1e-6), 0, 1)
        # cardiovascular strain: use of the evaporative reserve (w / w_max), weighted by the SkBF fraction;
        # drift accumulates over the time spent above the strain limit (not a function of core)
        strain_cv = w_frac * (1.0 + s_lin) / 2.0
        above = w_frac - DRIFT_THR
        self.drift = np.where(above > 0, np.minimum(self.drift + DRIFT_RATE * above * (DRIFT_W0 + s_lin), DRIFT_MAX),
                              self.drift * (1 - 1 / DRIFT_TAU))
        heat_fac = np.where(self.bb, p["bb_hr_factor"], 1.0) * np.where(self.antichol, ANTICHOL_HR, 1.0)
        # round 4 (experiment): HR for the cardiac output that the LOCAL skin flow needs at a fixed stroke volume
        # (HR = dCO / SV; older SV 68 mL at thermal tolerance, Minson 1998; CO rises with SkBF, Rowell 1974)
        loc_flow = np.minimum(loc, self.skbf_max) * A_D / 60.0 if np.ndim(loc) else np.zeros(n)   # L/min
        hr_cv = CV_HR_SCALE * 1000.0 * loc_flow / SV_OLDER_ML
        hr = (p["hr_rest"] + heat_fac * (p["kappa_amb"] * amb + p["kappa_core"] * excess + self.drift + hr_cv)
              + 35.0 * (met - 0.86) * p["reserve_factor"])
        hr = np.minimum(hr, p["hr_max"])

        s_log = np.clip(np.log(m_bl / p["skbf_min"]) / np.log(np.maximum(self.skbf_max / p["skbf_min"], 1.0001)), 0, 1)
        t_skin_rep = self.t_skin + ((SKIN_REPORT_OFFSET_K * (self.t_core - self.t_skin) + SKIN_REPORT_OFFSET_W * np.maximum(w - 0.07, 0.0)) if "skinfix" in feats else 0.0)
        out = dict(T_core=self.t_core.copy(), T_skin=t_skin_rep, T_skin_node=self.t_skin.copy(),
                   s_skbf=s_log, s_lin=s_lin, m_bl=m_bl, m_sweat=m_sweat, w=w, w_max=w_max,
                   deficit_pct=np.maximum(self.deficit_g, 0) / (mass * 1000.0) * 100.0,
                   HR=hr, E_sk=self.e_skin.copy(), Q_sens=q_sensible, M=m, E_res=q_res, C_res=c_res,
                   storage=storage, strain_cv=strain_cv, drift=self.drift.copy(), T_ref=t_ref,
                   water_loss_gpm=sweat_water + insens_water + resp_water + urine + extra_loss)
        self.last = out
        return out
