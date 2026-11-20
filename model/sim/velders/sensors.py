"""BandSensors — what the Heat Guardian band would see, R2 §6 (SIMULATION). Vectorised over persons.

T1/T2 (TMP117 skin side / reference across 3 mm EVA), R2 §6.1 physical model:
  T_deep = T_core - D_axial,  D_axial = a + b*(T_core - T_air)*(1 - s)
  q = (T_deep - T_sa) / (R_tissue' + R_mount' + R_gap + R_ins + R_lid + 1/h_out)
  T1 = T_deep - q*(R_tissue' + R_mount' + R_gap),  T2 = T1 - q*R_ins
  first-order lags tau_T1 3-5 min (tissue), tau_T2 5-10 min (lid); donning: 20-30 min to 95 %.
  R_tissue' = R_tissue x0.7 when s > 0.7; R_mount' halves when sweating under the pod.
  T_sa = local air + sun-on-lid excess (lid 45-60 C -> T2 > T1).
SHTC3 (R2 §6.2): T_air_meas = T_air + off + c*(T1 - T_air) [c scaled by 8/h_out] + sleeve at night
  + sun; tau 1.5 min; RH from the true vapour pressure at the measured island temperature + off;
  sweat-saturation and shower episodes push RH to 90-100 %.
MAX30102 HR (R2 §6.3): N(0, 3) still, x1.3 with motion, sd 10 walking; outliers p_out x3 with
  motion (+0.2 when PI < 0.2 %, x2 when loose) -> 50 % "no reading" (NaN) / 50 % U(-30, +15) bpm.
  PI = PI0 * g(s), g = exp(2.5 (s - 0.5)) (2-4x from constricted to dilated), lowered by dehydration.
ICM-20649 (R2 §6.4): a_std from the activity + tremor + 1.4 mg noise floor; z-angle from posture.
Cross-signal consistency (R2 §6.5): T1 - T_air, dT and PI all derive from the same s and h_out;
a loose band changes T1, dT, PI and the IMU (slip rotation) together.

All per-minute random numbers are pre-drawn per person from that person's own stream
(seed + id, stream 2), so outputs do not depend on how persons are batched.
"""
from __future__ import annotations

import numpy as np

from .indoor import sat_vp_kpa

TMP_LSB = 0.0078125
SLEEVE_P = 0.4          # fraction of sleep minutes with the arm under the sheet


def person_noise(seed: int, n_min: int) -> dict:
    rng = np.random.default_rng([seed, 2])
    f = np.float32
    return dict(
        n_t1=rng.normal(0, 0.008 / np.sqrt(12), n_min).astype(f),   # 12 one-shot reads / min (5 s)
        n_t2=rng.normal(0, 0.008 / np.sqrt(12), n_min).astype(f),
        n_sht=rng.normal(0, 0.05 / np.sqrt(6), n_min).astype(f),
        n_rh=rng.normal(0, 0.2 / np.sqrt(6), n_min).astype(f),
        n_hr=rng.normal(0, 1, n_min).astype(f),
        u_out=rng.uniform(0, 1, n_min).astype(f),
        u_kind=rng.uniform(0, 1, n_min).astype(f),
        u_out_val=rng.uniform(-30, 15, n_min).astype(f),
        u_q=rng.uniform(0, 1, n_min).astype(f),
        n_pi=rng.normal(0, 0.1, n_min).astype(f),
        n_a=rng.normal(0, 1, n_min).astype(f),
        n_z=rng.normal(0, 1, n_min).astype(f),
        u_wet=rng.uniform(0, 1, n_min).astype(f),
        u_sleeve=(rng.uniform(0, 1, n_min // 60 + 2) < SLEEVE_P),
        slip_ang=rng.uniform(20, 40, n_min).astype(f) * np.where(rng.uniform(size=n_min) < 0.5, -1, 1).astype(f),
    )


class BandSensors:
    def __init__(self, P: dict, noise: dict):
        g = lambda k: np.asarray(P[k], float)
        self.P = {k: g(k) for k in ("a_axial", "b_axial", "R_tissue", "R_mount", "R_ins", "R_lid", "tau_T1_min",
                                    "tau_T2_min", "tau_don_min", "tmp_off1", "tmp_off2", "tmp_pair_resid", "sht_T_off",
                                    "sht_RH_off", "c_bodyheat", "sleeve_dT", "PI0", "p_out", "acc_off_z",
                                    "tremor_phys_g", "tremor_ess_g", "mass_kg")}
        self.N = noise          # dict of (T, n) arrays
        n = self.P["a_axial"].shape[0]
        self.n = n
        self.t1 = None
        self.t2 = None
        self.t1_true = None
        self.sht = None
        self.min_since_don = np.full(n, 60.0)
        self.prev_worn = np.full(n, 2)
        self.wet_run = np.zeros(n)
        self.t = 0
        from .body import v5_skin_offsets           # v5: per-person skin-core coupling (zeros in v4)
        ds, dw = v5_skin_offsets(P["seed"]) if "seed" in P else (np.zeros(n), np.zeros(n))
        self.d_wrist_total = ds + dw

    def step(self, truth: dict, ctx: dict) -> dict:
        P, N, i = self.P, self.N, self.t
        self.t += 1
        Tc, s, Ta, RHa = truth["T_core"], truth["s_skbf"], truth["T_air"], truth["RH_air"]
        worn = ctx["worn"].astype(int)
        h_out = ctx["h_out"]
        # --- physical model
        d_ax = np.maximum(P["a_axial"] + P["b_axial"] * (Tc - Ta) * (1 - s), 0.1)
        t_deep = Tc - d_ax
        r_t = P["R_tissue"] * np.where(s > 0.7, 0.7, 1.0)
        r_m = P["R_mount"] * np.where(truth["m_sweat"] > 50, 0.5, 1.0)
        r_gap = np.where(worn == 1, ctx["r_gap"], 0.0)
        local_air = Ta
        t_sa = local_air + ctx["sun_dT"]
        r_out = P["R_lid"] + 1.0 / h_out
        q = (t_deep - t_sa) / (r_t + r_m + r_gap + P["R_ins"] + r_out)
        t1_ss = t_deep - q * (r_t + r_m + r_gap)
        t2_ss = t1_ss - q * P["R_ins"]
        off = worn == 0
        t1_ss = np.where(off, t_sa, t1_ss)
        t2_ss = np.where(off, t_sa, t2_ss)
        # donning bookkeeping
        donned = (worn > 0) & (self.prev_worn == 0)
        self.min_since_don = np.where(donned, 0.0, np.where(worn > 0, self.min_since_don + 1, 0.0))
        self.prev_worn = worn
        tau1 = np.where(off, 3.0, np.where(self.min_since_don < 30, P["tau_don_min"], P["tau_T1_min"]))
        tau2 = np.where(self.min_since_don < 30, np.maximum(P["tau_don_min"], P["tau_T2_min"]), P["tau_T2_min"])
        if self.t1 is None:
            self.t1, self.t2 = t1_ss.copy(), t2_ss.copy()
        else:
            self.t1 = self.t1 + (t1_ss - self.t1) * (1 - np.exp(-1.0 / tau1))
            self.t2 = self.t2 + (t2_ss - self.t2) * (1 - np.exp(-1.0 / tau2))
        # v5: per-person skin-core coupling offset on the skin-side reading; T1 and T2 move together so the heat-flux dT
        # (and every v4 flux property) is unchanged; zero in v4
        dw = np.where(worn > 0, self.d_wrist_total, 0.0)
        t1_true = self.t1 - ctx["flash"] - dw
        t2_true = self.t2 - dw
        T1 = np.round((t1_true + P["tmp_off1"] + N["n_t1"][i]) / TMP_LSB) * TMP_LSB
        T2 = np.round((t2_true + P["tmp_off1"] + P["tmp_pair_resid"] + N["n_t2"][i]) / TMP_LSB) * TMP_LSB
        # --- SHTC3
        c = np.where(off, 0.0, P["c_bodyheat"] * 8.0 / h_out)
        sleeve = (ctx["asleep"] > 0) & N["u_sleeve"][i // 60] & ~off
        sht_ss = Ta + c * (t1_true - Ta) + np.where(sleeve, P["sleeve_dT"], 0.0) + 0.4 * ctx["sun_dT"]
        if self.sht is None:
            self.sht = sht_ss.copy()
        else:
            self.sht = self.sht + (sht_ss - self.sht) * (1 - np.exp(-1.0 / 1.5))
        T_air_meas = self.sht + P["sht_T_off"] + N["n_sht"][i]
        pa = RHa / 100.0 * sat_vp_kpa(Ta)
        rh_meas = 100.0 * pa / sat_vp_kpa(self.sht) + P["sht_RH_off"] + N["n_rh"][i]
        # sweat saturation of the island (R2 §6.2): onset prob rises with sweat rate; 10-60 min
        start_wet = (~off) & (N["u_wet"][i] < 0.002 * np.clip(truth["m_sweat"] / 60.0, 0, 3))
        self.wet_run = np.where(start_wet & (self.wet_run <= 0), 10 + 50 * N["u_q"][i], np.maximum(self.wet_run - 1, 0))
        self.wet_run = np.where(off, 0, self.wet_run)
        wet = (self.wet_run > 0) | (ctx["rh_wet"] > 0)
        rh_meas = np.where(wet, 90.0 + 10.0 * N["u_q"][i], rh_meas)
        rh_meas = np.clip(rh_meas, 0.0, 100.0)
        # --- PPG
        loose = worn == 1
        PI = P["PI0"] * np.exp(2.5 * (s - 0.5)) * np.clip(1 - 0.05 * truth["deficit_pct"], 0.5, 1) * np.where(loose, 0.4, 1.0)
        PI = PI * np.exp(N["n_pi"][i])
        a_true = ctx["a_std_true"]
        moving = a_true > 0.05
        walking = ctx["act_class"] == 5
        sd = np.where(walking, 10.0, np.where(moving, 3.9, 3.0))
        p_out = P["p_out"] * np.where(moving, 3.0, 1.0) + np.where(PI < 0.2, 0.2, 0.0)
        p_out = np.minimum(p_out * np.where(loose, 2.0, 1.0), 0.9)
        is_out = N["u_out"][i] < p_out
        no_read = is_out & (N["u_kind"][i] < 0.5)
        hr = truth["HR_true"] + sd * N["n_hr"][i]
        hr = np.where(is_out & ~no_read, truth["HR_true"] + N["u_out_val"][i], hr)
        hr = np.where(no_read | off, np.nan, hr)
        q_ok = np.where(moving, 2, 4)
        quality = np.where(off, 0, np.where(no_read, np.where(PI < 0.3, 1, np.where(moving, 2, 3)),
                                            np.where(is_out, np.where(N["u_q"][i] < 0.5, 3, q_ok), q_ok)))
        PI = np.where(off, np.nan, PI)
        # --- IMU
        # tremor is a waking phenomenon: physiological (postural) and essential tremor both disappear in sleep,
        # so asleep minutes carry only wrist micro-movement + the ICM-20649 noise floor (285 ug/sqrt(Hz) x sqrt(25 Hz)
        # = 1.4 mg, R2 §6.4). Round 3 fix (B3: sleep a_std was >= 2.8 mg because awake tremor was added in bed).
        awake_f = (1 - off) * (1 - (ctx["asleep"] > 0))
        a_std = np.sqrt((a_true + (P["tremor_phys_g"] + P["tremor_ess_g"]) * awake_f) ** 2 + 0.0014 ** 2)
        a_std = np.where(off, np.sqrt(0.0002 ** 2 + 0.0014 ** 2), a_std)
        zang = ctx["zangle_true"] + 3.0 * N["n_z"][i] + np.degrees(np.arcsin(np.clip(P["acc_off_z"], -1, 1)))
        zang = np.where(ctx["slip"] > 0, zang + N["slip_ang"][i], zang)
        zang = np.clip(np.where(off, 88.0 + 0.5 * N["n_z"][i], zang), -90.0, 90.0)
        a_std = np.where(ctx["slip"] > 0, np.maximum(a_std, 0.02), a_std)
        flux_valid = (worn == 2) & (t1_true - t2_true > 0.15) & (Ta < t1_true - 0.5) & (self.min_since_don >= 20)
        return dict(T1=T1, T2=T2, T_air_meas=T_air_meas, RH_meas=rh_meas, HR_meas=hr, hr_quality=quality,
                    PI=PI, a_std_g=a_std, zangle_deg=zang, flux_valid_truth=flux_valid, worn_truth=worn,
                    T_deep_wrist=t_deep, T1_true=t1_true, T2_true=t2_true, min_since_don=self.min_since_don.copy())
