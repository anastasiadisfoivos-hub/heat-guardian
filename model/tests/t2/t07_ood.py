"""T2-07 OOD / nonsense inputs through FeatureState (the band's feature path mirror) + the exported ensemble (tester forward,
M6 sd rule). Every output must be finite and bounded: core in [30, 45], sd in (0, 5], strain in [0, 10], logits finite.
Run: cd /home/claude/hg_ai && HG2_SIMVER=v4 python3 tests/t2/t07_ood.py"""
import json, os, sys
sys.path.insert(0, "/home/claude/hg_ai"); sys.path.insert(0, "/home/claude/hg_ai/tests/t2")
os.environ["HG2_SIMVER"] = "v4"
import numpy as np
from model.hg2 import features as FT
from t2lib import load_weights, ens
W = load_weights(); F = np.float32; T = 360


def base(**kw):
    c = dict(t1=np.full(T, 34.5), t2=np.full(T, 33.0), tair=np.full(T, 27.0), rh=np.full(T, 45.0), hr=np.full(T, 72.0), hrq=np.full(T, 4),
             pi=np.full(T, 1.0), astd=np.full(T, 0.01), worn=np.full(T, 2), mod=(480 + np.arange(T)) % 1440)
    for k, v in kw.items(): c[k] = np.broadcast_to(np.asarray(v, float), (T,)).copy() if np.ndim(v) == 0 else np.asarray(v, float)
    return c


ramp = lambda a, b: np.linspace(a, b, T)
step = lambda lo, hi, t0=60: np.where(np.arange(T) >= t0, hi, lo).astype(float)
cases = {
    "nominal": base(),
    "HR 140 flat T1 36.4": base(hr=step(75, 140), t1=36.4, t2=35.4, tair=30),
    "HR 160 flat T1 36.4": base(hr=step(75, 160), t1=36.4, t2=35.4, tair=30),
    "HR 180": base(hr=step(75, 180), t1=36.4, t2=35.4, tair=30),
    "HR 220 (max accepted)": base(hr=step(75, 220), tair=30),
    "HR 250 (rejected -> hold)": base(hr=step(75, 250)),
    "HR 0": base(hr=step(75, 0)),
    "HR NaN all (no PPG)": base(hr=np.nan, hrq=0, pi=np.nan),
    "HR 140 + beta-blocker 85y": dict(base(hr=step(75, 140), tair=34), _prof=dict(age=85, sex_m=0, bmi=30, med_flags=1)),
    "T1 flat 36.0 exactly, air 38 (stuck sensor in heat)": base(t1=36.0, t2=36.0, tair=38, rh=40),
    "T1 flat 30.0 (cold stuck)": base(t1=30.0, t2=29.0, tair=22),
    "T2 NaN all (no REF board)": base(t2=np.nan),
    "T2 NaN + T1 NaN (no thermal)": base(t1=np.nan, t2=np.nan),
    "T2 inf": base(t2=np.inf),
    "T1 inf": base(t1=step(34.5, np.inf, 100)),
    "T_air NaN all": base(tair=np.nan, rh=np.nan),
    "T_air 60, RH 100": base(tair=60, rh=100, t1=40, t2=39.5),
    "T_air -40, RH 0": base(tair=-40, rh=0, t1=25, t2=10),
    "loose band (worn=1) T1 sinks to air": base(worn=step(2, 1), t1=np.where(np.arange(T) >= 60, ramp(34.5, 29.0), 34.5), tair=28),
    "band off (worn=0) 5 h": base(worn=step(2, 0)),
    "on/off flicker every minute": base(worn=np.where(np.arange(T) % 2, 2, 0)),
    "time unknown": base(mod=np.full(T, 0xFFFF)),
    "PI inf, astd 50 g": base(pi=np.inf, astd=50.0),
    "astd NaN, PI NaN": base(astd=np.nan, pi=np.nan),
    "hot room 36C, HR 110, T1 37": base(tair=36, rh=55, hr=step(80, 110), t1=37.0, t2=36.8),
}
prof0 = dict(age=78, sex_m=1, bmi=27, med_flags=0)
tw = dict(rest_hr=70.0, k_person=0.12, core_offset=0.0, c_bodyheat=0.15, t1_night_base=np.full(24, np.nan))
R = {}
for name, c in cases.items():
    prof = c.pop("_prof", prof0) if isinstance(c, dict) else prof0
    cols = {k: (np.asarray(v, np.int64) if k in ("hrq", "worn", "mod") else np.asarray(v, F))[:, None] for k, v in c.items()}
    pr = {k: np.array([v]) for k, v in prof.items()}; twv = {k: (np.array([v]) if np.ndim(v) == 0 else v[None]) for k, v in tw.items()}
    try:
        with np.errstate(all="ignore"):
            X, aux, idx = FT.run_lanes(cols, pr, twv)
            E = ens(W, X)
    except Exception as e:
        R[name] = dict(exception=type(e).__name__ + ": " + str(e)[:120]); continue
    last = slice(-60, None)
    fin = {k: bool(np.isfinite(v).all()) for k, v in E.items()}
    bounded = bool(np.isfinite(E["core_now"]).all() and (E["core_now"] >= 30).all() and (E["core_now"] <= 45).all()
                   and np.isfinite(E["sd_now"]).all() and (E["sd_now"] > 0).all() and (E["sd_now"] <= 5).all()
                   and np.isfinite(E["lp385"]).all() and (E["strain"] >= 0).all() and (E["strain"] <= 10).all())
    R[name] = dict(all_finite=all(fin.values()), nonfinite_outputs=[k for k, v in fin.items() if not v], bounded=bounded,
                   features_nonfinite=[FT.NAMES[j] for j in range(32) if not np.isfinite(np.nan_to_num(X[:, j], nan=0.0)).all()],
                   core_now_last_h=[float(np.nanmin(E["core_now"][last])), float(np.nanmax(E["core_now"][last]))],
                   core_20_last=float(E["core_20"][-1]), sd_now_last=float(E["sd_now"][-1]), lp385_last=float(E["lp385"][-1]),
                   strain_last=float(E["strain"][-1]), v12_f20_last=float(aux["v12_f20"][-1]), kf_last=float(X[-1, 20]),
                   valid_share_last_h=float(np.mean(aux["valid"][last])), hr_reserve_last=float(X[-1, 14]))
json.dump(R, open("/home/claude/hg_ai/tests/t2/out/t07_ood.json", "w"), indent=1)
for k, v in R.items():
    if "exception" in v: print("%-50s EXCEPTION %s" % (k, v["exception"])); continue
    print("%-50s fin=%d bnd=%d core[%.2f,%.2f] c20 %.2f sd %.3f lp385 %.1f strain %.1f v12f20 %.2f kf %.2f valid %.2f %s %s" % (
        k, v["all_finite"], v["bounded"], *v["core_now_last_h"], v["core_20_last"], v["sd_now_last"], v["lp385_last"], v["strain_last"], v["v12_f20_last"],
        v["kf_last"], v["valid_share_last_h"], v["nonfinite_outputs"], v["features_nonfinite"]))
