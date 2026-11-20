"""24 h body simulation for the Tomorrow Engine (ARCHITECTURE §6 physics.py).

Uses B1's ``velders.body.TwoNodeOlder`` when it can be imported from /home/claude/hg_ai/sim.
Until then (or if it fails to import) it falls back to ``StubTwoNodeOlder`` below, a line-for-line
port of the Gagge-Ji older-adult two-node model (Ji et al. 2022, Build Simul 15:1815,
doi:10.1007/s12273-022-0890-3, as in pythermalcomfort.two_nodes_gagge_ji) with three additions
taken from ARCHITECTURE §3.3 / R1: an optional per-person w_max cap = omega_max x (1.0 ADL, 0.75 rest)
(R1 §2.1, Kenney 2025; OFF by default, see the w_max comment in step()), circadian shift of the central set-points (mesor 36.9, amplitude 0.35,
nadir 04:30; R1 §3.3), and a frailty/medication-free person. Every plan made with the stub
carries the label "physics: STUB two-node (velders not available)".

Both classes share B1's public API: ``Model(person: dict)``, ``.step(env) -> dict`` with
``env = {t_db, rh, v_air, t_r, met, clo, drink_mL}`` and the return containing at least
``T_core, T_skin``.
"""
from __future__ import annotations

import copy
import math
import os
import sys

import numpy as np

SIM_DIR = os.environ.get("HG_SIM_DIR", "/home/claude/hg_ai/sim")

SBC = 5.6697e-8


def vapour_pressure_torr(t_db: float, rh: float) -> float:
    """Ambient vapour pressure in torr (mmHg), the unit two_nodes_gagge_ji uses (p_sat_torr form)."""
    return rh / 100.0 * math.exp(18.6686 - 4030.183 / (t_db + 235.0))


class StubTwoNodeOlder:
    """STUB — Gagge-Ji older two-node, 1-min step, stateful. Used only until velders lands."""

    IS_STUB = True

    def __init__(self, person: dict):
        p = dict(person)
        self.mass = float(p.get("mass", 70.0))
        self.height = float(p.get("height", 1.65))
        self.A = 0.202 * self.mass ** 0.425 * self.height ** 0.725      # DuBois
        self.omega_max = float(p.get("omega_max", 0.44))
        self.circ_amp = float(p.get("circ_amp", 0.35))
        self.circ_nadir_h = float(p.get("circ_nadir_h", 4.5))
        self.circadian = bool(p.get("circadian", True))
        self.w_max_fixed = p.get("w_max_fixed")          # for the pythermalcomfort agreement test
        self.use_omega_cap = bool(p.get("use_omega_cap", False))
        self.minute = int(p.get("start_minute", 0))
        c0 = self._circ(self.minute)
        self.t_core = float(p.get("T_core0", 36.9 + c0))
        self.t_skin = float(p.get("T_skin0", 34.0))
        self.m_bl = 6.3
        self.alfa = 0.1
        self.e_skin = None
        self.w = 0.06
        self.h_cc = 3.0
        self.h_r = 4.7

    def _circ(self, minute):
        if not self.circadian:
            return 0.0
        acro = (self.circ_nadir_h + 12.0) * 60.0
        return self.circ_amp * math.cos(2.0 * math.pi * (minute - acro) / 1440.0)

    def step(self, env: dict) -> dict:
        t_db = float(env["t_db"]); tr = float(env.get("t_r", t_db)); v = max(float(env.get("v_air", 0.1)), 0.1)
        met = float(env.get("met", 0.86)); clo = float(env.get("clo", 0.4))
        pa = vapour_pressure_torr(t_db, float(env.get("rh", 45.0)))         # torr
        standing = met >= 1.2
        c = self._circ(self.minute)
        t_cr0_dil, t_sk0_cons, t_cr0_sw, t_sk0_sw, t_cr0_sh = 37.3 + c, 33.25, 37.0 + c, 34.3, 36.7 + c
        m = met * 58.2
        if self.e_skin is None:
            self.e_skin = 0.1 * met
        r_clo = 0.155 * clo
        f_a_cl = 1.0 + 0.2 * clo if clo < 0.5 else 1.05 + 0.1 * clo
        lr = 2.2
        # w_max: Ji 2022 default 0.85 (unacclimatised). The ARCHITECTURE §3.3 cap omega_max x (1.0 ADL /
        # 0.75 rest) is NOT applied in the stub: applied as Gagge's w_max it gives +1.27..+2.30 degC after
        # 8 h seated at 36 degC / 45 % (omega 0.57..0.31) vs the measured +0.9 +- 0.15 (R1 V2, Meade 2024),
        # while 0.85 gives +0.74. Calibrating that cap is B1's job (V2); velders.body is used when present.
        w_max = self.w_max_fixed if self.w_max_fixed is not None else (
            self.omega_max * (1.0 if met >= 1.2 else 0.75) if self.use_omega_cap else 0.85)
        m_rsw_max = 400.0 / 0.68 * 0.9

        h_t = self.h_r + self.h_cc
        r_a = 1.0 / (f_a_cl * h_t)
        t_op = (self.h_r * tr + self.h_cc * t_db) / h_t
        t_cl = (r_a * self.t_skin + r_clo * t_op) / (r_a + r_clo)
        for _ in range(150):
            self.h_r = 4.0 * 0.97 * SBC * ((t_cl + tr) / 2.0 + 273.15) ** 3 * (0.77 if standing else 0.7)
            h_t = self.h_r + self.h_cc
            r_a = 1.0 / (f_a_cl * h_t)
            t_op = (self.h_r * tr + self.h_cc * t_db) / h_t
            t_new = (r_a * self.t_skin + r_clo * t_op) / (r_a + r_clo)
            done = abs(t_new - t_cl) < 0.01
            t_cl = t_new
            if done:
                break
        d = t_cl - t_db
        if v < 0.2:
            self.h_cc = 2.5 * d ** 0.16 if d > 0 else 2.5 * abs(d) ** 0.41
        else:
            self.h_cc = 8.6 * v ** 0.53
        q_sens = (self.t_skin - t_op) / (r_a + r_clo)
        q_res = 0.0023 * m * (44.0 - pa)
        c_res = 0.0014 * m * (34.0 - t_db)
        hf_cs = (self.t_core - self.t_skin) * (5.28 + 1.163 * self.m_bl)
        s_core = m - hf_cs - q_res - c_res
        s_skin = hf_cs - q_sens - self.e_skin
        tc_sk = 0.97 * self.alfa * self.mass
        tc_cr = 0.97 * (1 - self.alfa) * self.mass
        self.t_skin += s_skin * self.A / (tc_sk * 60.0)
        self.t_core += s_core * self.A / (tc_cr * 60.0)

        t_cr_dil = max(0.0, self.t_core - t_cr0_dil)
        t_sk_cons = max(0.0, t_sk0_cons - self.t_skin)
        self.m_bl = min(63.0, max(0.75, (6.3 + 0.6 * 50 * t_cr_dil) / (1 + 0.5 * 0.75 * t_sk_cons)))
        t_sk_sw = max(0.0, self.t_skin - t_sk0_sw)
        t_cr_sw = max(0.0, self.t_core - t_cr0_sw)
        self.alfa = 0.0417737 + 0.7451832 / (self.m_bl + 0.5854417)
        m_rsw = min(170 * ((1 - self.alfa) * t_cr_sw + (self.alfa + 0.2) * t_sk_sw) * math.exp(t_sk_sw / 10.7), m_rsw_max)
        e_rsw = 0.68 * m_rsw
        r_total = r_clo / (lr * (0.45 if clo > 0 else 1.0)) + 1.0 / (lr * f_a_cl * self.h_cc)
        e_max = (math.exp(18.6686 - 4030.183 / (self.t_skin + 235.0)) - pa) / r_total
        if e_max > 0:
            p_rsw = e_rsw / e_max
            wd = 1.0 / (2.0 + 2.46 / r_total)
            wp = wd + (1 - wd) * p_rsw
            w = (math.sqrt(2 * wp ** 2 + 1) - 1) / wp
            w = min(w, w_max)
            p_rsw = (w - wd) / (1.0 - wd)
            e_rsw = max(0.0, p_rsw * e_max)
            e_diff = max(0.0, w * e_max - e_rsw)
        else:
            w = e_rsw = e_diff = 0.0
        self.w = w
        self.e_skin = e_rsw + e_diff
        t_cr_sh = max(0.0, t_cr0_sh - self.t_core)
        m_shiv = 19.4 * t_cr_sh * t_sk_cons + 50 * t_cr_sh + 0.5 * t_sk_cons
        # (shivering feeds the next step's M through met; ignored at the warm conditions we plan for)
        self.minute = (self.minute + 1) % 1440
        return {"T_core": self.t_core, "T_skin": self.t_skin, "w": w, "m_sweat": m_rsw,
                "s_skbf": (self.m_bl - 0.75) / (63.0 - 0.75), "E_sk": self.e_skin, "Q_sens": q_sens,
                "M": m, "M_shiv": m_shiv}


def load_body_class():
    """Return (class, label). Prefer B1's velders.body.TwoNodeOlder; fall back to the stub."""
    if os.environ.get("HG_FORCE_STUB") == "1":
        return StubTwoNodeOlder, "physics: STUB two-node (forced)"
    if os.path.isdir(os.path.join(SIM_DIR, "velders")) and SIM_DIR not in sys.path:
        sys.path.insert(0, SIM_DIR)
    try:
        from velders.body import TwoNodeOlder     # noqa: WPS433
        return TwoNodeOlder, "physics: velders.body.TwoNodeOlder (B1)"
    except Exception as e:                          # ImportError or B1 work-in-progress errors
        return StubTwoNodeOlder, "physics: STUB two-node (velders not available: %s)" % type(e).__name__


# ---- person from Twin/profile ------------------------------------------------------------
# HG_MED_* bits exactly as /home/claude/hgmodel/heat_guardian_model.h lines 51-54
MED_BETA_BLOCKER, MED_DIURETIC, MED_LOW_SWEAT, MED_ACE_ARB = 1, 2, 4, 8
# B5-v7: PROFILE field 5 bit 4 = other heart-rate-limiting drug or pacemaker (guardian HG_MEDF_HRB). On the band it only moves
# the skin-floor Danger 0.1 C earlier (no DRINK/COOL margin); here it adds no margin either and the HR model is unchanged
# (no HR_max source for these drugs). Older twin.json files never set it.
MED_HR_LIMITING = 16
MED_ALL = 31


def person_from_twin(twin: dict) -> dict:
    """Build the person dict (brief: age, sex, mass, height, med_flags, omega_max prior,
    kappa_core = 22, rest_hr) from twin.json, with the key names both models read
    (velders.body uses mass_kg, A_D, hr_rest, omega_max, kappa_core, med_*; unknown keys are ignored)."""
    age = float(twin.get("age", 78)); sex_m = int(twin.get("sex_m", 0))
    mass = float(twin.get("mass", 65.0)); height = float(twin.get("height", 1.60))
    flags = int(twin.get("med_flags", 0))
    if not 0 <= flags <= MED_ALL:
        raise ValueError("med_flags must be 0..31, got %r" % flags)
    rest = float(twin.get("rest_hr", 70.0))
    bb = 1 if flags & MED_BETA_BLOCKER else 0
    p = {
        "age": age, "sex": "m" if sex_m else "f", "sex_m": sex_m,
        "mass": mass, "height": height, "mass_kg": mass,
        "A_D": 0.202 * mass ** 0.425 * height ** 0.725,              # DuBois
        "med_flags": flags,
        "omega_max": float(twin.get("sweat_capacity", 0.44)),       # prior midpoint of U(0.31,0.57), R1 §2.1
        "kappa_core": 22.0,                                         # midpoint of U(14,30), ARCHITECTURE §3.3
        "rest_hr": rest, "hr_rest": rest,
        # Tanaka / Brawner HR_max (ARCHITECTURE §3.3 table, without the random term)
        "hr_max": (164.0 if bb else 208.0) - 0.7 * age,
        # selectivity is unknown from the band flag: selective is the common prescription (design choice)
        "med_bb_sel": bb, "med_bb_nonsel": 0,
        "med_antichol": 1 if flags & MED_LOW_SWEAT else 0,
        "med_diuretic": 1 if flags & MED_DIURETIC else 0,
        "med_ace_arb": 1 if flags & MED_ACE_ARB else 0,
    }
    p["bmi"] = mass / height ** 2
    return p


class _ScalarAdapter:
    """Wrap a vectorised (n = 1) velders model so step() returns Python floats."""

    def __init__(self, inner):
        self.inner = inner

    def step(self, env):
        out = self.inner.step(env)
        return {k: (float(np.ravel(v)[0]) if np.ndim(v) else v) for k, v in out.items()}


def make_model(person: dict, start_minute: int = 0):
    cls, label = load_body_class()
    pp = dict(person)
    try:
        if getattr(cls, "IS_STUB", False):
            pp.setdefault("start_minute", start_minute)
            model = cls(pp)
        else:
            model = _ScalarAdapter(cls(pp, minute_of_day0=float(start_minute)))
            model.step({"t_db": 25.0, "rh": 45.0, "v_air": 0.1, "t_r": 25.0, "met": 0.7, "clo": 0.6,
                        "drink_mL": 0.0, "minute_of_day": float(start_minute)})   # smoke step on a throw-away copy below
            model = _ScalarAdapter(cls(pp, minute_of_day0=float(start_minute)))
    except Exception as e:  # B1 work in progress: fall back, say so
        pp.setdefault("start_minute", start_minute)
        model = StubTwoNodeOlder(pp)
        label = "physics: STUB two-node (velders failed: %s: %s)" % (type(e).__name__, str(e)[:60])
    return model, label


def run(model, envs: list[dict]) -> np.ndarray:
    """Step a model through a list of minute envs; returns T_core per minute."""
    out = np.empty(len(envs))
    for i, e in enumerate(envs):
        out[i] = model.step(e)["T_core"]
    return out


def snapshot(model):
    return copy.deepcopy(model)
