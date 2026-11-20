"""Indoor heat model (SIMULATION; literature priors, not fits).

ROUND 3: the simulator now uses the SAME home physics as the Tomorrow Engine: tomorrow.indoor.simulate (B4's
R3 §1.6 implementation with its tested class anchors: class A "mean" anchor, B-D "min" anchor = indoor night
min tied to the outdoor night min, Sakka 2012; class C g_sun 0.15). Each virtual person keeps their own drawn
tau_s / dT_home / tau_f / g_f (persons.parquet, inside R3's ranges); g_sun and the anchor come from B4's class
table. Envelope: indoor <= 40 C (Sakka 2012, the only Athens measurement: "up to 40 C", R3 §1.1) -- applied as
a hard cap (it binds only for class A, the Bath-like temperate class, in the hottest S2 hours).
person_indoor() is the entry point. The original first-order IndoorModel below is kept for reference only.


Hourly step:
  T_slow[t+1] = T_slow[t] + (1/tau_s) * (T_out[t] + dT_home - T_slow[t])
  T_fast[t+1] = T_fast[t] + (1/tau_f) * (g_f*(T_out[t] - T_slow[t] + dT_home) + g_sun*S[t]/100 - T_fast[t])
  T_in = T_slow + T_fast
RH: absolute humidity conserved with the indoor/outdoor AH ratio 0.69 (Nguyen 2014, R3 §1.3),
RH recomputed at T_in. The bedroom is the living room + home_bed_dT (Zuurbier 2021, R3 (iii)).
Hourly series are interpolated linearly to 1-min. Vectorised over persons (arrays of shape (n,)).
"""
from __future__ import annotations

import numpy as np

AH_RATIO = 0.69


def sat_vp_kpa(t):
    """Magnus (Alduchov & Eskridge 1996) saturation vapour pressure, kPa."""
    return 0.61094 * np.exp(17.625 * t / (t + 243.04))


def abs_humidity(t, rh):
    """g/m3."""
    return 1000.0 * rh / 100.0 * sat_vp_kpa(t) * 1000.0 / (461.5 * (t + 273.15))


def rh_from_ah(t, ah):
    return np.clip(100.0 * ah / 1000.0 * 461.5 * (t + 273.15) / (sat_vp_kpa(t) * 1000.0), 1.0, 100.0)


class IndoorModel:
    def __init__(self, tau_s_h, dT_home, tau_f_h, g_f, g_sun, bed_dT=0.5, t_slow0=None, t_fast0=0.0):
        self.tau_s = np.asarray(tau_s_h, float)
        self.dT = np.asarray(dT_home, float)
        self.tau_f = np.asarray(tau_f_h, float)
        self.g_f = np.asarray(g_f, float)
        self.g_sun = np.asarray(g_sun, float)
        self.bed_dT = np.asarray(bed_dT, float)
        self.t_slow = None if t_slow0 is None else np.asarray(t_slow0, float)
        self.t_fast = np.broadcast_to(np.asarray(t_fast0, float), self.tau_s.shape).astype(float).copy()

    @classmethod
    def from_person(cls, P):
        return cls(P["home_tau_s_h"], P["home_dT"], P["home_tau_f_h"], P["home_g_f"], P["home_g_sun"], P["home_bed_dT"])

    def run_hourly(self, t_out, s_rad, rh_out):
        """t_out, s_rad, rh_out: arrays (hours,) or (hours, n). Returns dict of (hours, n) arrays."""
        t_out = np.asarray(t_out, float)
        s_rad = np.asarray(s_rad, float)
        rh_out = np.asarray(rh_out, float)
        H = t_out.shape[0]
        n = self.tau_s.shape[0] if self.tau_s.ndim else 1
        if t_out.ndim == 1:
            t_out = np.repeat(t_out[:, None], n, 1)
            s_rad = np.repeat(s_rad[:, None], n, 1)
            rh_out = np.repeat(rh_out[:, None], n, 1)
        if self.t_slow is None:
            self.t_slow = t_out[:24].mean(0) + self.dT
        tin = np.empty((H, n))
        for h in range(H):
            tin[h] = self.t_slow + self.t_fast
            ts_new = self.t_slow + (t_out[h] + self.dT - self.t_slow) / self.tau_s
            tf_new = self.t_fast + (self.g_f * (t_out[h] - self.t_slow + self.dT) + self.g_sun * s_rad[h] / 100.0 - self.t_fast) / self.tau_f
            self.t_slow, self.t_fast = ts_new, tf_new
        ah_out = abs_humidity(t_out, rh_out)
        # 6-h running mean of outdoor AH (buildings buffer humidity)
        k = np.ones(6) / 6.0
        ah_s = np.vstack([np.convolve(np.pad(ah_out[:, j], (5, 0), mode="edge"), k, mode="valid") for j in range(n)]).T
        ah_in = AH_RATIO * ah_s
        tbed = tin + self.bed_dT
        return dict(t_in=tin, rh_in=rh_from_ah(tin, ah_in), t_bed=tbed, rh_bed=rh_from_ah(tbed, ah_in), ah_in=ah_in)


def hourly_to_minutes(x_hourly):
    """Linear interpolation of an hourly series (value at the start of each hour) to 1-min."""
    x = np.asarray(x_hourly, float)
    H = x.shape[0]
    tm = np.arange(H * 60) / 60.0
    th = np.arange(H)
    if x.ndim == 1:
        return np.interp(tm, th, x)
    return np.stack([np.interp(tm, th, x[:, j]) for j in range(x.shape[1])], 1)


INDOOR_CAP_C = 40.0


def person_indoor(P: dict, t_out, s_rad, rh_out):
    """Hourly indoor series for one person (dict of scalars) with B4's model; returns t_in, rh_in, t_bed, rh_bed."""
    from tomorrow import indoor as TI
    base = TI.CLASSES[P["home_class"]]
    par = TI.HomeClass(base.name, float(P["home_tau_s_h"]), float(P["home_dT"]), float(P["home_tau_f_h"]),
                       float(P["home_g_f"]), base.g_sun, base.anchor, base.note)
    o = TI.simulate(np.asarray(t_out, float), np.asarray(s_rad, float), np.asarray(rh_out, float), params=par)
    ah = TI.AH_RATIO * TI.abs_humidity(np.asarray(t_out, float), np.asarray(rh_out, float))
    tin = np.minimum(o["t_in"], INDOOR_CAP_C)
    tbed = np.minimum(tin + float(P["home_bed_dT"]), INDOOR_CAP_C)
    return dict(t_in=tin, rh_in=TI.rh_from_ah(tin, ah), t_bed=tbed, rh_bed=TI.rh_from_ah(tbed, ah))


def indoor_model_sha():
    import hashlib
    import tomorrow.indoor as TI
    return hashlib.sha256(open(TI.__file__, "rb").read()).hexdigest()


class B4Class:
    """Validation shim: B4's class-default home (tomorrow.indoor.CLASSES[cls]) with the 40 C envelope,
    returning (hours, 1) arrays like the old IndoorModel.run_hourly."""

    def __init__(self, cls, bed_dT=0.5):
        self.cls, self.bed_dT = cls, bed_dT

    def run_hourly(self, t_out, s_rad, rh_out):
        from tomorrow import indoor as TI
        p = TI.CLASSES[self.cls]
        P = dict(home_class=self.cls, home_tau_s_h=p.tau_s, home_dT=p.dT_home, home_tau_f_h=p.tau_f, home_g_f=p.g_f,
                 home_bed_dT=self.bed_dT)
        r = person_indoor(P, t_out, s_rad, rh_out)
        return {k: np.asarray(v)[:, None] for k, v in r.items()}
