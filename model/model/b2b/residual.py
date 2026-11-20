"""B2b fix: ANCHOR + BOUNDED RESIDUAL ("AR").  Reference implementation (float32, scalar + vectorised identical).

  core_AR = v1.2 + w * clamp(NN - v1.2, -R, +R)          (now and +20 min; +30 uses the +20 rule on the NN's +30 output)

  v1.2 (HR Kalman + linear correction, frozen inside the guardian) is the ANCHOR: the only estimator validated on real core
  (young HTT 0.25 C; it also carries the HR dynamics the NN ignores once a skin reading is present - diagnosis.json).
  The NN may move the anchor by at most R = 0.30 C (fixed a priori, manager's value; sensitivity 0.2/0.5 reported).
  Variant "AR_asym" (R = 0.30 down, R_up = 0.50 up; REPORT_B2b.md): lowering stays tight, raising is looser - chosen on
  SIM-DEV v4 (DEV) after the symmetric rule lost heat-wave Danger catches (53 -> 44 / 63); a DEV choice, disclosed.
  w in [0, 1] is the product of three gates, all fixed BEFORE any DEV scoring from the training distribution and the
  M11.3 rule, not from any exam:
    g_skin : the NN's only extra sense over v1.2 is the thermal channel. No valid skin reading (T1 NaN, band not worn
             = 2, or < 20-min donning blank) -> 0. Real data with no skin channel (HTT) therefore get v1.2 exactly:
             there the NN uses the same HR + air as v1.2 and is worse on real data (M16.1).
    g_env  : T1 - air must lie inside the envelope the NN was trained on: p0.5..p99.5 of SIM-training T1 - air at that
             air temperature (ENV_AIR / ENV_LO / ENV_HI, from model/cache/v4aug/sim_v0.npz training persons, 2-C bins,
             linear in air, flat outside 24..40 C). Ramp to 0 over ENV_RAMP = 0.5 C outside it.
    g_hr   : the M11.3 out-of-distribution HR rule (hr_reserve > 0.60 or HR > 108 bpm) -> 0 (was: max(NN, v1.2)).
  Ensemble spread is NOT a gate: on DEV it does not track error (corr 0.03 SIM, 0.00 HTT; diagnosis.json), so a
  spread shrink would be unsupported decoration (M11: "models disagree" is not a supported claim).
  Output clamps unchanged (30..45 C). Twin core_offset is added after, for display only (M4.3), exactly as before.
"""
import os, sys
import numpy as np

F = np.float32
R_DEFAULT = F(0.30)
ENV_RAMP = F(0.5)
# SIM-DEV v4 training persons (member view 0, every 2nd minute), T1 - T_air percentiles in |air - c| <= 1 C bins
ENV_AIR = np.array([24, 26, 28, 30, 32, 34, 36, 38, 40], F)
ENV_LO = np.array([7.10, 6.51, 5.45, 3.89, 2.43, 0.91, -0.72, -2.53, -4.06], F)
ENV_HI = np.array([12.22, 10.46, 8.99, 7.38, 5.73, 4.15, 2.31, 0.64, -0.77], F)
OOD_RESERVE, OOD_HR, DON_BLANK = F(0.60), F(108.0), 20
R_UP_DEFAULT = None
if os.environ.get("B2B_TAG", "v4aug") != "v4aug":
    # B2b-v5: single source of truth = guardian/c/hg_guardian_cfg.h (exact float32 bits via guardian/py/hg_consts.json)
    sys.path.insert(0, "/home/claude/hg_ai/guardian/py")
    import hg_guardian_py as _hg
    _n = _hg.KI("HG_AR_ENV_N")
    ENV_AIR, ENV_LO, ENV_HI = (np.array(_hg.KA(k, _n), F) for k in ("HG_AR_ENV_AIR", "HG_AR_ENV_LO", "HG_AR_ENV_HI"))
    R_DEFAULT, R_UP_DEFAULT, ENV_RAMP = F(_hg.K("HG_AR_R_DOWN")), F(_hg.K("HG_AR_R_UP")), F(_hg.K("HG_AR_RAMP"))


def env_bounds(air):
    a = np.clip(np.asarray(air, F), ENV_AIR[0], ENV_AIR[-1])
    return np.interp(a, ENV_AIR, ENV_LO).astype(F), np.interp(a, ENV_AIR, ENV_HI).astype(F)


def gate(t1, air, hr, hr_reserve, worn=2, min_since_don=60, use_env=True, use_hr=True):
    """w in [0,1]; vectorised. t1/air raw degC (NaN = none), hr bpm, hr_reserve as feature x[14]"""
    t1, air, hr, res = (np.asarray(v, F) for v in (t1, air, hr, hr_reserve))
    ok = np.isfinite(t1) & np.isfinite(air) & (np.asarray(worn) == 2) & (np.asarray(min_since_don) >= DON_BLANK)
    w = ok.astype(F)
    if use_env:
        lo, hi = env_bounds(np.where(np.isfinite(air), air, F(30)))
        d = np.where(np.isfinite(t1) & np.isfinite(air), t1 - air, F(0)).astype(F)
        out = np.maximum(np.maximum(lo - d, d - hi), F(0))
        w = (w * np.clip(F(1) - out / ENV_RAMP, 0, 1)).astype(F)
    if use_hr:
        bad = (res > OOD_RESERVE) | (hr > OOD_HR)
        w = np.where(bad, F(0), w).astype(F)
    return w


def combine(v12, nn, w, R=R_DEFAULT, R_up=None):
    """R bounds a LOWERING correction, R_up (default = R) a RAISING one (reading low is the dangerous direction)"""
    v12, nn, w = (np.asarray(v, F) for v in (v12, nn, w))
    if R_up is None: R_up = R_UP_DEFAULT if R == R_DEFAULT else None
    ru = F(R if R_up is None else R_up)
    r = np.clip(np.where(np.isfinite(nn), nn - v12, F(0)), -F(R), ru).astype(F)
    return np.clip(v12 + w * r, 30, 45).astype(F)


def from_features(X, v12_est, v12_f20, nn_now, nn_f20, worn=2, R=R_DEFAULT, R_up=None, **kw):
    """X raw 32-feature rows (x[0] t1, x[6] corrected air, x[10] hr, x[14] hr_reserve, x[22] min_since_don/60)"""
    X = np.asarray(X, F)
    msd = np.rint(X[:, 22] * 60) if X.ndim == 2 else np.rint(X[22] * 60)
    w = gate(X[..., 0], X[..., 6], X[..., 10], X[..., 14], worn=worn, min_since_don=msd, **kw)
    return combine(v12_est, nn_now, w, R, R_up), combine(v12_f20, nn_f20, w, R, R_up), w
