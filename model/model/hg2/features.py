"""hg2 feature builder (ARCHITECTURE 4.1, 32 features) and targets (4.2).

`FeatureState` is the stateful, causal, one-minute-at-a-time mirror of the C `hg2_step` feature path. It is
vectorised over N independent lanes (persons / sessions stepping in lock-step) but every lane is computed with the
same float32 operations, in the same order, as B5's scalar reference `guardian/py/hg_guardian_py.py::HG2.step`
(itself bit-exact with guardian/c/hg2_step.c). Constants and tables are the exact float32 bits the C compiler produced
(B5's hg_consts.json / hg_tables.json), loaded through B5's module so there is one source of truth.
`tests_features.py` proves lane-by-lane bitwise equality with B5's scalar class and minute-by-minute == batch.

KF anchor: line-for-line port of heat_guardian_band.c lines 94-101 (ECTemp with the rest_hr - 70 offset) + the v1.2
linear correction / logistic, via B5's port (M1.2 RH clamp [38, 60] inside the v1.2 linear correction only).
"""
import math, os, sys
import numpy as np
from .common import GUARD_PY

sys.path.insert(0, GUARD_PY)
import hg_guardian_py as REF   # noqa: E402  (constants/tables + the scalar reference used in the tests)

F = np.float32
K, KI, KA = REF.K, REF.KI, REF.KA
NAMES = ["t1", "t1_d5", "t1_d15", "dT", "dT_d10", "flux_valid", "t_air", "t_air_d15", "rh", "t1_minus_air",
         "hr", "hr_ewm5", "hr_ewm45", "hr_above_rest", "hr_reserve", "hr_valid", "log_pi", "act", "act_ewm30",
         "min_since_active", "kf", "heat_dose", "min_since_don", "sin_tod", "cos_tod", "core_flux", "t1_anom",
         "age", "sex_m", "bmi", "bb_flag", "low_sweat_flag"]
assert len(NAMES) == 32
TARGETS = ["core_now", "core_20", "core_30", "logit_p38", "logit_p385", "strain"]
# HTT rows: thermal/wrist pathway absent -> NaN -> z = 0 (ARCH 4.2), flux_valid = 0 (raw)
HTT_MASK = [0, 1, 2, 3, 4, 9, 16, 17, 18, 19, 22, 25, 26]

LNM = np.array(REF.LNM, F); PSAT = np.array(REF.PSAT, F); SINT = np.array(REF.SINT, F); LN2 = REF.LN2
A5, A15, A45, A30 = REF.A5, REF.A15, REF.A45, REF.A30


def _f(x): return np.asarray(x, dtype=F)


def lerp_tab(tab, n, pos):
    pos = _f(pos)
    i = np.where(np.isnan(pos), 0, np.trunc(np.nan_to_num(pos, nan=0.0))).astype(np.int64)
    i = np.where(pos < 0, 0, i); i = np.minimum(i, n - 2)
    fr = (pos - i.astype(F)).astype(F)
    return (tab[i] + ((tab[i + 1] - tab[i]).astype(F) * fr).astype(F)).astype(F)


def ln1p(x):
    x = _f(x)
    pos = x > 0
    y = (F(1) + np.where(pos, x, F(0))).astype(F)
    e = np.zeros(x.shape, np.int64)
    for _ in range(64):
        m = (y >= 2) & (e < 64)
        if not m.any(): break
        y = np.where(m, (y * F(0.5)).astype(F), y); e = e + m
    r = ((e.astype(F) * LN2).astype(F) + lerp_tab(LNM, 33, ((y - F(1)).astype(F) * F(32)).astype(F))).astype(F)
    return np.where(pos, r, F(0)).astype(F)


def psat(t):
    pos = (_f(t) - F(20)).astype(F)
    i = np.where(np.isnan(pos), 0, np.trunc(np.nan_to_num(pos, nan=0.0))).astype(np.int64)
    i = np.where(pos < 0, 0, i); i = np.minimum(i, 23)
    fr = (pos - i.astype(F)).astype(F); a, b, c = PSAT[i], PSAT[i + 1], PSAT[i + 2]
    lin = (a + (fr * (b - a).astype(F)).astype(F)).astype(F)
    q = (((fr * (fr - F(1)).astype(F)).astype(F) * F(0.5)).astype(F) * ((c - b).astype(F) - (b - a).astype(F)).astype(F)).astype(F)
    return (lin + q).astype(F)


def sin_tod(m):
    m = np.asarray(m, np.int64) % 1440; i = m // 15
    fr = ((m % 15).astype(F) / F(15)).astype(F)
    return (SINT[i] + ((SINT[i + 1] - SINT[i]).astype(F) * fr).astype(F)).astype(F)


def cos_tod(m): return sin_tod((np.asarray(m, np.int64) % 1440) + 360)


def hrmax_of(age, med_flags):
    age = _f(age); bb = (np.asarray(med_flags) & 1) != 0
    return np.where(bb, (K("HG_HRMAX_BB_A") - (K("HG_HRMAX_B") * age).astype(F)).astype(F),
                    (K("HG_HRMAX_A") - (K("HG_HRMAX_B") * age).astype(F)).astype(F)).astype(F)


class FeatureState:
    """N lanes of the C hg2 feature state. prof/twin: dicts of arrays (or scalars) of length N.
    prof: age, sex_m, bmi, med_flags.  twin: rest_hr, k_person, core_offset, c_bodyheat, t1_night_base [N,24] (NaN = none)."""

    def __init__(s, prof, twin, n):
        s.n = n
        bc = lambda v, dt=F: np.broadcast_to(np.asarray(v, dt), (n,)).copy()
        s.age, s.sex_m, s.bmi = bc(prof["age"]), bc(prof["sex_m"]), bc(prof["bmi"])
        s.med = bc(prof["med_flags"], np.int64)
        s.hrmax = hrmax_of(s.age, s.med)
        s.older_env = (s.age >= 65) | (s.med != 0)
        s.set_twin(twin)
        r = s.rest_hr
        # --- KF (v1.2 port) state
        s.ct = np.full(n, K("HG_KF_CT0"), F); s.v = np.full(n, K("HG_KF_V0"), F)
        s.k_e5 = r.copy(); s.k_e15 = r.copy(); s.k_e45 = r.copy(); s.k_last_hr = r.copy()
        s.hrbuf = []; s.kfring = np.zeros((16, n), F); s.estring = np.zeros((11, n), F); s.k_started = False
        s.ki = 0; s.ei = 0; s.w60 = np.zeros((60, n), bool); s.w60i = 0
        # --- hg2 state
        s.hr_last = r.copy(); s.hr_e5 = r.copy(); s.hr_e45 = r.copy(); s.act_e30 = np.zeros(n, F)
        s.t1_last = np.full(n, np.nan, F); s.tair_last = np.full(n, np.nan, F); s.rh_last = np.full(n, np.nan, F)
        s.ring_t1 = np.full((16, n), np.nan, F); s.ring_tair = np.full((16, n), np.nan, F); s.ring_dt = np.zeros((11, n), F)
        s.act30 = np.zeros((30, n), bool); s.a30i = 0
        s.min_since_active = np.zeros(n, np.int64); s.min_since_don = np.zeros(n, np.int64)
        s.env_run = np.zeros(n, np.int64); s.env_dose = np.zeros(n, np.int64)
        s.hrq5 = np.zeros((5, n), bool); s.q5i = 0
        s.ri16 = 0; s.ri11 = 0; s.started = False; s.last_worn = np.zeros(n, np.int64)

    def set_twin(s, twin, lanes=None):
        n = s.n
        bc = lambda v: np.broadcast_to(np.asarray(v, F), (n,)).copy()
        rest, kp, off, c = bc(twin["rest_hr"]), bc(twin["k_person"]), bc(twin["core_offset"]), bc(twin["c_bodyheat"])
        nb = np.broadcast_to(np.asarray(twin.get("t1_night_base", np.full(24, np.nan)), F), (n, 24))
        ok = (nb == nb) & (nb > 0) & (nb < 60)
        cent = np.where(ok, np.floor(((np.where(ok, nb, F(0)) * F(100)).astype(F) + F(0.5)).astype(F)), np.nan)
        if lanes is None or not hasattr(s, "rest_hr"):
            s.rest_hr, s.k_person, s.core_offset, s.c_bodyheat, s.t1nb = rest, kp, off, c, cent
        else:
            s.rest_hr[lanes], s.k_person[lanes], s.core_offset[lanes], s.c_bodyheat[lanes] = rest[lanes], kp[lanes], off[lanes], c[lanes]
            s.t1nb[lanes] = cent[lanes]

    # ---------------------------------------------------------------- v1.2 Kalman anchor (B5 KF.step, vectorised)
    def _kf(s, hr, amb, rh):
        hr = np.where((hr >= 30) & (hr <= 220), hr, s.k_last_hr).astype(F); s.k_last_hr = hr
        A, G, B0, B1, B2, S = K("HG_KF_A"), K("HG_KF_GAMMA"), K("HG_KF_B0"), K("HG_KF_B1"), K("HG_KF_B2"), K("HG_KF_SIGMA")
        ctp = (A * s.ct).astype(F); vp = (((A * A) * s.v).astype(F) + F(G * G)).astype(F)
        c = (((F(2) * B2) * ctp).astype(F) + B1).astype(F)
        k = ((vp * c).astype(F) / (((c * c).astype(F) * vp).astype(F) + F(S * S)).astype(F)).astype(F)
        hrp = ((((B2 * ctp).astype(F) * ctp).astype(F) + (B1 * ctp).astype(F)).astype(F) + B0).astype(F)
        s.ct = (ctp + (k * ((hr - (s.rest_hr - F(70)).astype(F)).astype(F) - hrp).astype(F)).astype(F)).astype(F)
        s.v = ((F(1) - (k * c).astype(F)).astype(F) * vp).astype(F)
        if len(s.hrbuf) < 3: s.hrbuf.append(hr)
        else: s.hrbuf = [s.hrbuf[1], s.hrbuf[2], hr]
        s.k_e5 = (s.k_e5 + (A5 * (hr - s.k_e5)).astype(F)).astype(F)
        s.k_e15 = (s.k_e15 + (A15 * (hr - s.k_e15)).astype(F)).astype(F)
        s.k_e45 = (s.k_e45 + (A45 * (hr - s.k_e45)).astype(F)).astype(F)
        if not s.k_started: s.kfring[:] = s.ct[None, :]; s.k_started = True
        s.kfring[s.ki] = s.ct; kf15 = s.kfring[(s.ki + 1) % 16].copy(); s.ki = (s.ki + 1) % 16
        amin, amax = K("HG_AGE_MIN"), K("HG_AGE_MAX")
        age_c = np.where(s.age < amin, amin, np.where(s.age > amax, amax, s.age)).astype(F)
        b = s.hrbuf
        if len(b) == 1: med = b[0]
        elif len(b) == 2: med = (F(0.5) * (b[0] + b[1]).astype(F)).astype(F)
        else:
            a, c2, d = b; lo = np.minimum(a, c2); hi = np.maximum(a, c2)   # if a > c swap
            hi = np.where(hi > d, d, hi)                                     # if c > d: c = d
            med = np.where(lo > hi, lo, hi)
        x = [None] * 14
        x[0] = med; x[1] = s.k_e5; x[2] = s.k_e15; x[3] = s.k_e45
        x[4] = (s.k_e5 - s.rest_hr).astype(F); x[5] = (x[4] / (s.hrmax - s.rest_hr).astype(F)).astype(F)
        x[6] = (s.k_e5 - s.k_e45).astype(F)
        rmin, rmax = K("HG_KF_RH_MIN"), K("HG_KF_RH_MAX")
        x[7] = amb; x[8] = np.where(rh < rmin, rmin, np.where(rh > rmax, rmax, rh)).astype(F)
        x[9] = age_c; x[10] = s.sex_m; x[11] = s.bmi; x[12] = s.ct; x[13] = (s.ct - kf15).astype(F)
        NOWC, F20C = KA("HG_NOW_COEF", 14), KA("HG_F20_COEF", 14)
        est = (s.ct + K("HG_NOW_INTERCEPT")).astype(F); f20 = (s.ct + K("HG_F20_INTERCEPT")).astype(F)
        for i in range(14):
            est = (est + (NOWC[i] * x[i]).astype(F)).astype(F); f20 = (f20 + (F20C[i] * x[i]).astype(F)).astype(F)
        sh = np.where(s.age >= 65, K("HG_OLDER_DANGER_SHIFT"), F(0)).astype(F)
        es = (est + sh).astype(F); fs = (f20 + sh).astype(F)
        if not hasattr(s, "_e_started"): s.estring[:] = es[None, :]; s._e_started = True
        s.estring[s.ei] = es; est10 = s.estring[(s.ei + 1) % 11].copy(); s.ei = (s.ei + 1) % 11
        s.w60[s.w60i] = fs >= K("HG_T_DRINK_WATER"); s.w60i = (s.w60i + 1) % 60
        warn60 = (s.w60.sum(0).astype(F) / F(60)).astype(F)
        DGW, SDC = KA("HG_DG_W", 7), KA("HG_SD_C", 4)
        d = [es, (fs - es).astype(F), (es - est10).astype(F), warn60, x[4], x[5], amb]
        z = np.full(s.n, K("HG_DG_B"), F)
        for i in range(7): z = (z + (DGW[i] * d[i]).astype(F)).astype(F)
        sd = (F(1.2533141) * ((((SDC[0] + (SDC[1] * est).astype(F)).astype(F) + (SDC[2] * x[5]).astype(F)).astype(F)
                               + (SDC[3] * warn60).astype(F)).astype(F))).astype(F)
        sd = np.where(sd < F(0.08), F(0.08), sd).astype(F)
        return dict(est=est, f20=f20, z=z, sd=sd, kf=s.ct.copy(), warn60=warn60)

    # ---------------------------------------------------------------- one minute
    def step(s, t1, t2, tair, rh, hr, hrq, pi, astd, worn, mod):
        """all args arrays [N] (NaN = not available; mod 0xFFFF = time unknown). Returns (x [N,32] float32, aux dict)."""
        n = s.n; t1, t2, tair, rh, hr, pi, astd = map(_f, (t1, t2, tair, rh, hr, pi, astd))
        # [B2-fix] input guard (C: hg2_guard.h): +-inf, NaN and out-of-sensor-range values are "not available" (NaN).
        # Ranges: TMP117/SHTC3 -40..85 C, RH 0..100 %, PI 0..100 %, a_std 0..16 g (ICM-20649 full scale); HR keeps its
        # own 30..220 gate. Identical to the unguarded B5 mirror for every in-range input (tests_features stays bitwise).
        g = lambda v, lo, hi: np.where((v >= lo) & (v <= hi), v, F(np.nan)).astype(F)
        with np.errstate(invalid="ignore"):
            t1, t2, tair = g(t1, -40, 85), g(t2, -40, 85), g(tair, -40, 85); rh = g(rh, 0, 100); pi = g(pi, 0, 100)
            astd = g(astd, 0, 16); hr = np.where(np.isfinite(hr), hr, F(np.nan)).astype(F)
        worn = np.asarray(worn, np.int64); hrq = np.asarray(hrq, np.int64); mod = np.asarray(mod, np.int64)
        x = np.zeros((32, n), F)
        w2 = worn == 2
        s.min_since_don = np.where(w2, np.where(s.last_worn != 2, 0, np.minimum(s.min_since_don + 1, 60)), 0)
        s.last_worn = worn.copy()
        upd = (worn != 0) & ~np.isnan(t1)
        s.t1_last = np.where(upd, t1, s.t1_last); t1v = s.t1_last; t1ok = ~np.isnan(t1v)
        s.tair_last = np.where(np.isnan(tair), s.tair_last, tair); s.rh_last = np.where(np.isnan(rh), s.rh_last, rh)
        traw, rhv = s.tair_last, s.rh_last
        corr = (traw - (s.c_bodyheat * (t1v - traw).astype(F)).astype(F)).astype(F)
        ta = np.where(~np.isnan(traw) & t1ok, corr, traw).astype(F); taok = ~np.isnan(ta)
        with np.errstate(invalid="ignore"):
            fv = (w2 & t1ok & ~np.isnan(t2) & taok & ((t1v - t2).astype(F) > F(0.15)) & (ta < (t1v - F(0.5)).astype(F))
                  & (s.min_since_don >= KI("HG_DON_BLANK_MIN")))
        dT = np.where(fv, (t1v - t2).astype(F), F(0)).astype(F)
        if not s.started:
            s.ring_t1[:] = t1v[None]; s.ring_tair[:] = ta[None]; s.ring_dt[:] = dT[None]; s.started = True
        s.ring_t1[s.ri16] = t1v; s.ring_tair[s.ri16] = ta; s.ring_dt[s.ri11] = dT
        t1_5, t1_15 = s.ring_t1[(s.ri16 + 11) % 16], s.ring_t1[(s.ri16 + 1) % 16]
        ta_15, dt_10 = s.ring_tair[(s.ri16 + 1) % 16], s.ring_dt[(s.ri11 + 1) % 11]
        s.ri16 = (s.ri16 + 1) % 16; s.ri11 = (s.ri11 + 1) % 11
        x[0] = t1v
        x[1] = np.where(t1ok & ~np.isnan(t1_5), (t1v - t1_5).astype(F), F(0))
        x[2] = np.where(t1ok & ~np.isnan(t1_15), (t1v - t1_15).astype(F), F(0))
        x[3] = dT; x[4] = np.where(fv, (dT - dt_10).astype(F), F(0)); x[5] = fv.astype(F)
        x[6] = ta; x[7] = np.where(taok & ~np.isnan(ta_15), (ta - ta_15).astype(F), F(0)); x[8] = rhv
        x[9] = np.where(t1ok & taok, (t1v - ta).astype(F), np.nan)
        with np.errstate(invalid="ignore"):
            good = (hrq == 4) & (hr >= 30) & (hr <= 220)
        s.hr_last = np.where(good, hr, s.hr_last).astype(F)
        s.hrq5[s.q5i] = good; s.q5i = (s.q5i + 1) % 5
        hr_valid = s.hrq5.sum(0) >= 3
        h = s.hr_last
        s.hr_e5 = (s.hr_e5 + (A5 * (h - s.hr_e5).astype(F)).astype(F)).astype(F)
        s.hr_e45 = (s.hr_e45 + (A45 * (h - s.hr_e45).astype(F)).astype(F)).astype(F)
        x[10] = h; x[11] = s.hr_e5; x[12] = s.hr_e45; x[13] = (h - s.rest_hr).astype(F)
        x[14] = ((h - s.rest_hr).astype(F) / (s.hrmax - s.rest_hr).astype(F)).astype(F); x[15] = hr_valid.astype(F)
        x[16] = np.where(np.isnan(pi), F(0), ln1p(np.where(np.isnan(pi), F(0), pi)))
        a = np.where(np.isnan(astd), F(0), astd).astype(F)
        act = ln1p((F(100) * a).astype(F))
        s.act_e30 = (s.act_e30 + (A30 * (act - s.act_e30).astype(F)).astype(F)).astype(F)
        active = a > K("HG_ACTIVE_G")
        s.min_since_active = np.where(active, 0, np.minimum(s.min_since_active + 1, 240))
        s.act30[s.a30i] = active; s.a30i = (s.a30i + 1) % 30; active30 = s.act30.sum(0)
        x[17] = act; x[18] = s.act_e30; x[19] = (s.min_since_active.astype(F) / F(240)).astype(F)
        ko = s._kf(np.where(good, hr, np.nan).astype(F), np.where(taok, ta, F(25)).astype(F),
                   np.where(np.isnan(rhv), F(50), rhv).astype(F))
        x[20] = ko["kf"]
        envok = taok & ~np.isnan(rhv)
        adl = active30 >= KI("HG_ENV_ACT_MIN")
        la = np.where(~s.older_env, K("HG_LIM_YOUNG_A"), np.where(adl, K("HG_LIM_OLD_ADL_A"), K("HG_LIM_OLD_REST_A"))).astype(F)
        lb = np.where(~s.older_env, K("HG_LIM_YOUNG_B"), np.where(adl, K("HG_LIM_OLD_ADL_B"), K("HG_LIM_OLD_REST_B"))).astype(F)
        pa = ((np.where(envok, rhv, F(0)) * F(0.01)).astype(F) * psat(np.where(envok, ta, F(25)))).astype(F)
        lim = (la + (lb * np.where(envok, ta, F(25))).astype(F)).astype(F)
        above = envok & (pa >= lim)
        s.env_run = np.where(above, np.minimum(s.env_run + 1, 30000), 0)
        s.env_dose = np.where(above, np.minimum(s.env_dose + 1, KI("HG_ENV_DOSE_CAP")), np.maximum(s.env_dose - 1, 0))
        x[21] = (s.env_dose.astype(F) / F(240)).astype(F); x[22] = (s.min_since_don.astype(F) / F(60)).astype(F)
        tk = mod < 1440; mm = np.where(tk, mod, 0)
        x[23] = np.where(tk, sin_tod(mm), F(0)); x[24] = np.where(tk, cos_tod(mm), F(0))
        cf = (t1v + (s.k_person * dT).astype(F)).astype(F); hi = (t1v + F(2.5)).astype(F)
        cf = np.where(cf < t1v, t1v, np.where(cf > hi, hi, cf))
        core_flux = np.where(fv, cf, t1v).astype(F); x[25] = core_flux
        b = s.t1nb[np.arange(n), mm // 60]
        x[26] = np.where(tk & t1ok & ~np.isnan(b), (t1v - (np.nan_to_num(b).astype(F) / F(100)).astype(F)).astype(F), F(0))
        x[27] = (s.age / F(100)).astype(F); x[28] = s.sex_m; x[29] = (s.bmi / F(30)).astype(F)
        x[30] = ((s.med & 1) != 0).astype(F); x[31] = ((s.med & 4) != 0).astype(F)
        aux = dict(v12_est=ko["est"], v12_f20=ko["f20"], v12_z=ko["z"], v12_sd=ko["sd"], kf=ko["kf"], t_air_corr=ta,
                   env_run=s.env_run.copy(), env_dose=s.env_dose.copy(), env_above=above, active=active,
                   flux_valid=fv, hr_valid=hr_valid, valid=w2 & (s.min_since_don >= KI("HG_DON_VALID_MIN")),
                   min_since_don=s.min_since_don.copy(), core_flux=np.where(fv, cf, np.nan).astype(F))
        return x.T.copy(), aux


def run_lanes(cols, prof, twin, twin_updates=None, keep=None):
    """cols: dict of [T, N] arrays (t1,t2,tair,rh,hr,hrq,pi,astd,worn,mod). Steps all T minutes.
    twin_updates: {t: (twin_dict, lanes)} applied before minute t. keep: bool [T, N] rows to return (None = all).
    Returns X [rows, 32], aux dict of [rows], idx (t, lane) of each row."""
    T, N = cols["t1"].shape
    st = FeatureState(prof, twin, N)
    Xs, AUX, IDX = [], {k: [] for k in ("v12_est", "v12_f20", "v12_z", "v12_sd", "valid", "flux_valid", "hr_valid", "t_air_corr", "core_flux")}, []
    for t in range(T):
        if twin_updates and t in twin_updates:
            tw, lanes = twin_updates[t]; st.set_twin(tw, lanes)
        x, aux = st.step(*(cols[k][t] for k in ("t1", "t2", "tair", "rh", "hr", "hrq", "pi", "astd", "worn", "mod")))
        sel = slice(None) if keep is None else keep[t]
        if keep is not None and not sel.any(): continue
        Xs.append(x[sel]); IDX.append(np.stack([np.full(N, t)[sel], np.arange(N)[sel]], 1))
        for k in AUX: AUX[k].append(np.asarray(aux[k])[sel])
    return np.concatenate(Xs), {k: np.concatenate(v) for k, v in AUX.items()}, np.concatenate(IDX)


def build_features(df_minutes, twin, profile):
    """One person/session, minute by minute (the reference API of the B2 brief). df_minutes: the sim columns
    T1, T2, T_air_meas, RH_meas, HR_meas, hr_quality, PI, a_std_g, worn_truth, minute_of_day (sorted by t_min).
    Returns ndarray [n, 32] float32 (raw, un-normalised)."""
    cols = sim_cols(df_minutes)
    st = FeatureState(profile, twin, 1)
    out = np.empty((len(df_minutes), 32), F)
    for t in range(len(df_minutes)):
        out[t] = st.step(*(cols[k][t] for k in ("t1", "t2", "tair", "rh", "hr", "hrq", "pi", "astd", "worn", "mod")))[0][0]
    return out


def sim_cols(df):
    """sim minutes dataframe (one person) -> [T, 1] input columns of hg2_in_t"""
    g = lambda c, dt=F: np.asarray(df[c].values, dt)[:, None]
    return dict(t1=g("T1"), t2=g("T2"), tair=g("T_air_meas"), rh=g("RH_meas"), hr=g("HR_meas"), hrq=g("hr_quality", np.int64),
                pi=g("PI"), astd=g("a_std_g"), worn=g("worn_truth", np.int64), mod=g("minute_of_day", np.int64))


def build_targets(df):
    """6 targets per minute from SIM truth (ARCH 4.2): core now/+20/+30 (NaN past the end), ev38_30, ev385_30, strain_psi."""
    c = np.asarray(df["T_core"].values, np.float64); n = len(c)
    c20 = np.full(n, np.nan); c30 = np.full(n, np.nan); c20[:max(n - 20, 0)] = c[20:]; c30[:max(n - 30, 0)] = c[30:]
    p38 = np.asarray(df["ev38_30"].values, np.float64); p385 = np.asarray(df["ev385_30"].values, np.float64)
    p38[n - 30:] = np.nan; p385[n - 30:] = np.nan
    return np.stack([c, c20, c30, p38, p385, np.asarray(df["strain_psi"].values, np.float64)], 1).astype(F)
