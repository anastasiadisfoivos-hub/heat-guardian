"""Virtual Elders population (SIMULATION).

draw_persons(n=500, seed=20261112) -> DataFrame, one row per person, every drawn parameter a
column, `split` column empty (the manager's seal script fills it; this package never decides
the dev/sealed split).

Every distribution is ARCHITECTURE.md §3.3 (sources R1/R2/R3 as cited there). Person i is drawn
from its own generator seeded (seed + i) so a person's parameters never depend on n.

Two documented construction choices (not in the §3.3 table, needed to make it consistent):
  * Medication classes are drawn with a Gaussian copula (equicorrelated latent "multimorbidity",
    rho solved numerically) so that BOTH the marginal class rates of §3.3 AND "none 55 %" hold;
    with independent draws "none" would be 51.7 %.
  * "Women get an effective age +7 y for the limit parameters" (R1 §3.2): the limit parameters
    of §3.3 (omega_max, SkBF-max multiplier) are uniform/log-normal and carry no age term, so
    effective age enters as a rank correlation (Gaussian copula, rho_age = 0.5) that keeps the
    marginals exactly as specified while older/female persons get lower limits (R1 §3.1: T_crit
    falls with age, Fisher 2023; women 40-60 ~ men 65+, Kenney 2025).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import norm

from . import SEED

MED_P = {"bb": 0.20, "diuretic": 0.15, "antichol": 0.05, "ace_arb": 0.20}   # ARCH §3.3
P_NONE_TARGET = 0.55
RHO_AGE = 0.5

HOME_CLASSES = ["A", "B", "C", "D"]
HOME_P = [0.10, 0.50, 0.25, 0.15]          # ARCH §3.3 / R3 §1.6
# R3 §1.6 class table: (tau_s lo, hi) h, (dT_home lo, hi) C, (tau_f lo, hi) h, (g_f lo, hi), g_sun [C per 100 W/m2]
HOME_PARAMS = {
    "A": ((24, 48), (4.0, 5.0), (3, 3), (0.10, 0.20), 0.0),
    "B": ((48, 72), (2.0, 3.0), (3, 3), (0.20, 0.25), 0.1),
    "C": ((24, 36), (4.0, 5.0), (2, 2), (0.30, 0.30), 0.3),
    "D": ((72, 120), (1.0, 2.0), (4, 6), (0.10, 0.10), 0.0),
}


def _gh_none_prob(rho: float, ps) -> float:
    x, w = np.polynomial.hermite_e.hermegauss(80)
    w = w / w.sum()
    t = norm.ppf(1 - np.asarray(ps))
    p_off = np.ones_like(x)
    for tc in t:
        p_off *= norm.cdf((tc - np.sqrt(rho) * x) / np.sqrt(1 - rho))
    return float((w * p_off).sum())


def med_copula_rho() -> float:
    ps = list(MED_P.values())
    return brentq(lambda r: _gh_none_prob(r, ps) - P_NONE_TARGET, 1e-6, 0.95)


def _clip(x, lo, hi):
    return float(min(max(x, lo), hi))


def draw_one(pid: int, seed: int = SEED, rho_med: float | None = None) -> dict:
    rng = np.random.default_rng(seed + pid)
    if rho_med is None:
        rho_med = med_copula_rho()
    p: dict = {"person_id": pid, "seed": seed + pid}
    # demographics / anthropometry (R1 §2.4, PSU cohort)
    p["age"] = rng.uniform(65, 85)
    p["sex_m"] = int(rng.uniform() < 0.5)
    p["eff_age"] = p["age"] + (0.0 if p["sex_m"] else 7.0)
    p["height_m"] = float(rng.normal(1.70, 0.09))
    p["bmi"] = _clip(rng.normal(26, 4), 19, 38)
    p["mass_kg"] = p["bmi"] * p["height_m"] ** 2
    p["A_D"] = 0.202 * p["mass_kg"] ** 0.425 * p["height_m"] ** 0.725   # DuBois
    p["vo2max"] = _clip(rng.normal(28, 9), 12, 50)
    # metabolic multipliers (R1 §1.6); met values themselves come from the clamp list
    p["met_rest_mult"] = float(np.exp(rng.normal(0, 0.08)))
    p["met_adl_mult"] = float(np.exp(rng.normal(0, 0.10)))
    # sweating (R1 §1.4 Ji 2022, §2.1)
    p["thr_sw_core"] = 37.0 + rng.normal(0, 0.15)
    p["thr_sw_skin"] = 34.3 + rng.normal(0, 0.3)
    z_age = (p["eff_age"] - 78.5) / 7.0           # standardised effective age (65..92)
    z_w = -RHO_AGE * z_age + np.sqrt(1 - RHO_AGE ** 2) * rng.normal()
    p["omega_max"] = 0.31 + 0.26 * float(norm.cdf(z_w))   # marginal U(0.31, 0.57)
    p["c_sw"] = 170.0
    # skin blood flow (R1 §1.3, §1.4)
    p["skbf_min"] = 0.75 * float(np.exp(rng.normal(0, 0.15)))
    p["skbf_neutral"] = 6.3 * float(np.exp(rng.normal(0, 0.15)))
    z_b = -RHO_AGE * z_age + np.sqrt(1 - RHO_AGE ** 2) * rng.normal()
    p["skbf_max"] = 63.0 * float(np.exp(0.15 * z_b))         # marginal 63 x LogN(0, 0.15)
    p["dil_gain"] = 30.0 * float(np.exp(rng.normal(0, 0.3)))
    p["dil_thr"] = 37.3
    p["str_gain"] = 0.375
    p["str_thr"] = 33.25
    # heart rate (R1 §2.3, §5; REPORT §7)
    p["kappa_core"] = rng.uniform(14, 30)
    p["reserve_factor"] = 0.72 + 0.28 * (p["kappa_core"] - 14) / 16   # drawn with kappa
    p["kappa_amb"] = max(0.0, float(rng.normal(1.0, 0.4)))
    p["hr_rest"] = _clip(rng.normal(66, 9), 45, 95)
    hr_noise = rng.normal(0, 10)
    # circadian (R1 §3.3)
    p["circ_mesor"] = 36.9 + rng.normal(0, 0.15)
    p["circ_amp"] = rng.uniform(0.25, 0.45)
    p["circ_nadir_h"] = 4.5 + rng.normal(0, 1.0)
    # fluid (R1 §2.4, §4)
    p["tbw_L"] = 0.50 * p["mass_kg"] * 0.88
    p["thirst_factor"] = rng.uniform(0.4, 0.8)
    # frailty (R1 §8.9, unvalidated by construction)
    p["frailty"] = rng.uniform(0, 1)
    # medication (R1 §5): Gaussian copula, marginals of ARCH §3.3, P(none) = 0.55
    g = rng.normal()
    meds = {}
    for k, pk in MED_P.items():
        z = np.sqrt(rho_med) * g + np.sqrt(1 - rho_med) * rng.normal()
        meds[k] = int(z > norm.ppf(1 - pk))
    bb_nonsel = int(meds["bb"] and rng.uniform() < 0.5)
    p["med_bb_nonsel"] = bb_nonsel
    p["med_bb_sel"] = int(meds["bb"] and not bb_nonsel)
    p["med_diuretic"] = meds["diuretic"]
    p["med_antichol"] = meds["antichol"]
    p["med_ace_arb"] = meds["ace_arb"]
    p["med_none"] = int(not any(meds.values()))
    p["antichol_sweat_factor"] = rng.uniform(0.35, 0.65)
    p["bb_hr_factor"] = rng.uniform(0.4, 0.6)          # R2 §6.3: HR rise with heat x0.4-0.6
    p["diuretic_deficit_pct"] = rng.uniform(0.5, 1.5)   # R1 §5 / ARCH S8
    p["hr_max"] = (164 if meds["bb"] else 208) - 0.7 * p["age"] + hr_noise
    p["acclim"] = int(rng.uniform() < 0.5)              # R1 §4 switch, both reported
    # home (R3 §1.6)
    hc = HOME_CLASSES[int(rng.choice(4, p=HOME_P))]
    p["home_class"] = hc
    (ts, dth, tf, gf, gsun) = HOME_PARAMS[hc]
    p["home_tau_s_h"] = rng.uniform(*ts)
    p["home_dT"] = rng.uniform(*dth)
    p["home_tau_f_h"] = rng.uniform(*tf)
    p["home_g_f"] = rng.uniform(*gf)
    p["home_g_sun"] = gsun
    p["home_bed_dT"] = rng.uniform(0.4, 0.6)          # R3 (iii) Zuurbier: bedroom warmer
    p["fan_available"] = int(rng.uniform() < 0.6)
    p["ac_available"] = 0
    # routine anchors (R3 §3.3; ARCH §6 routine defaults)
    p["wake_min"] = _clip(rng.normal(7 * 60, 40), 5.5 * 60, 9 * 60)
    p["bed_min"] = _clip(rng.normal(23 * 60, 40), 21.5 * 60, 24.5 * 60)
    p["jitter_sd_min"] = rng.uniform(20, 40)
    p["p_nap"] = rng.uniform(0.3, 0.8)
    p["p_errand"] = rng.uniform(0.3, 0.7) * (1 - 0.5 * p["frailty"])
    p["active_scale"] = 1 - 0.5 * p["frailty"]
    # wrist sensor constants (R2 §6.1-6.4)
    p["R_tissue"] = rng.uniform(0.008, 0.014)
    p["R_mount"] = rng.uniform(0.002, 0.008)
    p["R_ins"] = _clip(rng.normal(0.082, 0.006), 0.065, 0.10)   # 3 mm EVA, R2 §2.1
    p["R_lid"] = 0.012
    p["K_true"] = p["R_tissue"] / p["R_ins"]           # ARCH §3.3 K = R_tissue / R_ins (R2 §2.2: ~0.12)
    p["a_axial"] = rng.uniform(0.3, 0.8)
    p["b_axial"] = rng.uniform(0.08, 0.2)
    p["tau_T1_min"] = rng.uniform(3, 5)
    p["tau_T2_min"] = rng.uniform(5, 10)
    p["tau_don_min"] = rng.uniform(20, 30) / 3.0      # 95 % in 20-30 min
    p["tmp_off1"] = rng.uniform(-0.1, 0.1)
    p["tmp_off2"] = rng.uniform(-0.1, 0.1)
    p["tmp_pair_resid"] = rng.normal(0, 0.02)         # after box matching (R2 §2.5)
    p["sht_T_off"] = rng.uniform(-0.3, 0.3)
    p["sht_RH_off"] = rng.uniform(-2, 2)
    p["c_bodyheat"] = rng.uniform(0.05, 0.3)
    p["sleeve_dT"] = rng.uniform(0.5, 2.0)
    p["PI0"] = rng.uniform(0.2, 1.5)
    p["p_out"] = 0.20
    p["acc_off_x"], p["acc_off_y"], p["acc_off_z"] = rng.uniform(-0.065, 0.065, 3)
    p["tremor_phys_g"] = rng.uniform(0.001, 0.005)
    p["tremor_ess_g"] = rng.uniform(0.010, 0.050) if rng.uniform() < 0.05 else 0.0
    p["split"] = ""
    return p


def draw_persons(n: int = 500, seed: int = SEED) -> pd.DataFrame:
    rho = med_copula_rho()
    df = pd.DataFrame([draw_one(i, seed, rho) for i in range(n)])
    for c in df.columns:
        if df[c].dtype == np.float64:
            df[c] = df[c].astype(np.float64)
    return df
