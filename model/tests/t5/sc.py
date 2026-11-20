#!/usr/bin/env python3
"""T5 scripted-core (SC) layer: drive the frozen Guardian Loop with scripted Core Sense outputs.
C side = build/sc_O2 (sc_harness.c + the unchanged guardian/c files except hg2_step.c).
Python side = guardian/py/hg_guardian_py.Guardian with its hg2 replaced by the same script (FakeHG2).
"""
import os, sys, subprocess, tempfile, struct
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/home/claude/hg_ai/guardian/py")
import hg_guardian_py as G
from hg_guardian_py import cmd_frame
F = np.float32; NAN = float("nan")
SC_BIN = os.environ.get("T5_SC_BIN", os.path.join(HERE, "build", "sc_O2"))
FIELDS = ["hr_valid", "l38", "l385", "strain", "sd20", "core20", "v12f20", "v12z", "tair", "ea", "eao", "erun", "edose", "act", "still", "x10", "x14", "rh"]
OUT = ["state", "level", "family_alert", "alarm_id", "check_reason", "check_min", "haptic", "screen", "tiers", "routine_req", "imok",
       "notify_not_worn", "why", "night_heat", "nudge", "worn", "help", "snooze", "pd_cool_run", "cool_p_on", "cool_ack", "still_run",
       "check_active", "a_base_n", "a_base", "a_n", "hour_clean", "msd", "beh"]

def row(mod=600, button=0, worn=2, vbat=4.0, astd=0.01, apeak=1.0, cmd=None, hr_valid=1, l38=-100.0, l385=-100.0, strain=0.0,
        sd20=0.1, core20=36.9, v12f20=36.9, v12z=-6.0, tair=25.0, ea=0, eao=0, erun=0, edose=0, act=None, still=None,
        x10=70.0, x14=0.0, rh=50.0):
    if act is None: act = 1 if astd > 0.02 else 0
    if still is None: still = 1 if astd <= 0.002 else 0
    return dict(mod=mod, button=button, worn=worn, vbat=vbat, astd=astd, apeak=apeak, cmd=cmd, hr_valid=hr_valid, l38=l38, l385=l385,
                strain=strain, sd20=sd20, core20=core20, v12f20=v12f20, v12z=v12z, tair=tair, ea=ea, eao=eao, erun=erun, edose=edose,
                act=act, still=still, x10=x10, x14=x14, rh=rh)

def env_counters(rows):
    """fill erun/edose from ea exactly as hg2_step.c 197-198 does"""
    run = dose = 0
    for r in rows:
        run = min(run + 1, 30000) if r["ea"] else 0
        dose = (min(dose + 1, 240) if dose < 240 else dose) if r["ea"] else max(dose - 1, 0)
        r["erun"], r["edose"] = run, dose
    return rows

def _f(v):
    v = float(v); return "nan" if v != v else repr(float(F(v)))

def write(path, prof, rows, calm=None):
    with open(path, "w") as f:
        f.write("#PROFILE,%s,%s,%s,%d\n" % (_f(prof["age"]), _f(prof["sex_m"]), _f(prof["bmi"]), prof["med_flags"]))
        if calm is not None: f.write("#CALM,%s,%d\n" % (_f(calm[0]), calm[1]))
        for r in rows:
            f.write(",".join([str(int(r["mod"])), str(int(r["button"])), str(int(r["worn"])), _f(r["vbat"]), _f(r["astd"]), _f(r["apeak"]),
                              r["cmd"].hex() if r["cmd"] else "-"] + [_f(r[k]) for k in FIELDS]) + "\n")

def run_c(prof, rows, calm=None, exe=None):
    with tempfile.TemporaryDirectory() as d:
        i, o = os.path.join(d, "i.csv"), os.path.join(d, "o.csv")
        write(i, prof, rows, calm)
        subprocess.check_call([exe or SC_BIN, i, o])
        res = []
        for line in open(o):
            p = line.strip().split(",")
            res.append({k: (float(v) if k == "a_base" else int(v)) for k, v in zip(OUT, p)})
    return res

class _W: pass
class FakeHG2:
    def __init__(s, w):
        s.min_since_don = 0; s.last_worn = 0; s.rh_last = F(NAN); s.core_offset = F(0); s.W = w; s.cur = None
    def step(s, i):
        worn = i["worn"]
        if worn == 2:
            if s.last_worn != 2: s.min_since_don = 0
            elif s.min_since_don < 60: s.min_since_don += 1
        else: s.min_since_don = 0
        s.last_worn = worn
        r = s.cur; s.rh_last = F(r["rh"])
        c20 = F(r["core20"])
        core = dict(core_now=c20, core_20=c20, core_30=c20, sd_now=F(0.1), sd_20=F(r["sd20"]), sd_30=F(r["sd20"]), logit_p38=F(r["l38"]),
                    logit_p385=F(r["l385"]), strain=F(r["strain"]), f20_eff=c20, f30_eff=c20, kf=F(0), core_flux=F(NAN), flux_valid=0,
                    hr_valid=int(r["hr_valid"] != 0), valid=int(worn == 2 and s.min_since_don >= 5), why=0)
        x = [F(0)] * 32; x[10] = F(r["x10"]); x[14] = F(r["x14"])
        aux = dict(core20_noff=c20, x=x, nn_mean=[F(0)] * 6, nn_sd=[F(0)] * 6, v12_est=F(r["v12f20"]), v12_f20=F(r["v12f20"]), v12_z=F(r["v12z"]),
                   v12_sd=F(0), t_air_corr=F(r["tair"]), env_run=int(r["erun"]), env_dose=int(r["edose"]), env_above=int(r["ea"]),
                   env_above_old=int(r["eao"]), active=int(r["act"]), still=int(r["still"]), active30=0)
        return core, aux

def run_py(prof, rows, calm=None):
    twin = dict(rest_hr=70.0, k_person=0.12, core_offset=0.0, c_bodyheat=0.15, t1_night_base=[NAN] * 24)
    g = G.Guardian(prof, twin)
    w = _W(); w.cut38 = g.hg2.W.cut38; w.cut385 = g.hg2.W.cut385
    g.hg2 = FakeHG2(w)
    if calm is not None:   # = hg_guardian_set_calm (bounds 36.8..37.7, n == 0 -> unlearned)
        c, n = F(calm[0]), calm[1]
        if n == 0 or c != c or c < G.K("HG_A_BASE_MIN") or c > G.K("HG_A_BASE_MAX"): g.a_base, g.a_base_n = F(0), 0
        else: g.a_base, g.a_base_n = c, n
    res = []
    for r in rows:
        if r["cmd"]: g.cmd(r["cmd"])
        g.hg2.cur = r
        m = dict(mod=r["mod"], t1=NAN, t2=NAN, tair=NAN, rh=NAN, hr=NAN, hrq=4, pi=NAN, astd=r["astd"], apeak=r["apeak"], dc=100000, flat=0,
                 button=r["button"], charging=0, vbat=r["vbat"], ble=-1, force_worn=r["worn"], cmd=None,
                 t1_5s=[NAN] * 12, t2_5s=[NAN] * 12, tair_5s=[NAN] * 12, zang=[NAN] * 12, forecast=None)
        o = g.step(m)
        res.append(dict(state=o["state"], level=o["level"], family_alert=o["family_alert"], alarm_id=o["alarm_id"], check_reason=o["check_reason"],
                        check_min=o["check_min"], haptic=o["haptic"], screen=o["screen"], tiers=o["tiers"], routine_req=o["routine_req"],
                        imok=o["imok_resp_min"], notify_not_worn=o["notify_not_worn"], why=o["why"], night_heat=o["night_heat"], nudge=o["nudge"],
                        worn=o["worn"], help=g.help, snooze=g.snooze, pd_cool_run=g.pd_cool_run, cool_p_on=g.cool_p.on, cool_ack=g.cool_ack,
                        still_run=g.still_run, check_active=g.check_active, a_base_n=g.a_base_n, a_base=float(g.a_base), a_n=g.a_n,
                        hour_clean=g.rt.hour_clean, msd=g.hg2.min_since_don, beh=int(bool(o["why"] & 4))))
    return res

# ------------------------------------------------------------------ random scripts (my generator)
TH = [37.85, 37.832, 38.35, 38.15, 38.168, 37.65, 30.0, -1.45, -2.1972246]
def _near(rng, v):
    f = F(v); k = int(rng.integers(0, 3))
    return float(f) if k == 0 else float(np.nextafter(f, F(1e9))) if k == 1 else float(np.nextafter(f, F(-1e9)))

def rand_script(i):
    rng = np.random.default_rng(777000 + i)
    n = int(rng.integers(40, 700))
    age = float(F(rng.choice([45.0, 64.0, 65.0, 80.0])))
    prof = dict(age=age, sex_m=0.0, bmi=26.0, med_flags=int(rng.integers(0, 16)))
    calm = None
    if rng.random() < 0.4: calm = (float(F(rng.uniform(36.6, 37.9))), int(rng.integers(0, 4)))
    mod = int(rng.integers(0, 1440)) if rng.random() < 0.9 else 0xFFFF
    c20 = rng.uniform(36.7, 38.6); v12 = rng.uniform(36.7, 38.8); z = rng.uniform(-5, 0); ta = rng.uniform(22, 38)
    l385 = rng.uniform(-6, 2); strain = rng.uniform(0, 9); hrv = 1; ea = 0; eao = 0; worn = 2; wl = 0; storm = 0; astd = 0.01
    rows = []
    for t in range(n):
        if rng.random() < 0.004: mod = int(rng.integers(0, 1440))
        elif rng.random() < 0.002: mod = 0xFFFF
        elif mod == 0xFFFF and rng.random() < 0.02: mod = int(rng.integers(0, 1440))
        c20 += rng.normal(0, 0.02); v12 += rng.normal(0, 0.025); z += rng.normal(0, 0.12); ta += rng.normal(0, 0.15)
        l385 += rng.normal(0, 0.3); strain += rng.normal(0, 0.3)
        c20 = min(max(c20, 36.0), 39.5); v12 = min(max(v12, 36.0), 39.8); z = min(max(z, -8), 3); ta = min(max(ta, 15), 45)
        l385 = min(max(l385, -10), 5); strain = min(max(strain, 0), 10)
        if rng.random() < 0.03: c20 = _near(rng, rng.choice(TH[:6]))
        if rng.random() < 0.03: v12 = _near(rng, rng.choice(TH[:6]))
        if rng.random() < 0.03: z = _near(rng, rng.choice(TH[7:]))
        if rng.random() < 0.03: ta = _near(rng, 30.0)
        if rng.random() < 0.02: hrv = 1 - hrv
        if rng.random() < 0.03: ea = 1 - ea
        if rng.random() < 0.03: eao = 1 - eao
        if wl <= 0 and rng.random() < 0.01: worn = int(rng.choice([0, 0, 1])); wl = int(rng.integers(2, 40))
        if wl > 0: wl -= 1
        else: worn = 2
        if rng.random() < 0.15: astd = float(rng.choice([0.001, 0.002, 0.0021, 0.01, 0.02, 0.0201, 0.08]))
        if storm <= 0 and rng.random() < 0.01: storm = int(rng.integers(3, 15))
        if storm > 0: storm -= 1; b = int(rng.choice([0, 1, 2], p=[0.55, 0.445, 0.005]))
        else: b = 1 if rng.random() < 0.02 else (2 if rng.random() < 0.0003 else 0)
        cmd = None
        if rng.random() < 0.02:
            cmd = cmd_frame(0x12, ack_type=int(rng.integers(1, 4)), alarm_id=(int(rng.integers(1, 4)) << 16) | ((t + 1 - int(rng.integers(0, 60 if rng.random() < 0.5 else t + 1))) & 0xFFFF))
        hr = float(rng.uniform(55, 120)) if rng.random() < 0.9 else float(rng.choice([108.0, float(np.nextafter(F(108), F(200))), 150.0]))
        res = float(rng.uniform(0, 0.7)) if rng.random() < 0.9 else float(rng.choice([0.6, float(np.nextafter(F(0.6), F(2))), 0.9]))
        rows.append(row(mod=mod, button=b, worn=worn, vbat=float(F(rng.uniform(3.3, 4.2))), astd=astd,
                        apeak=float(rng.choice([1.0, 2.5])) if rng.random() < 0.01 else 1.0, cmd=cmd, hr_valid=hrv,
                        l38=float(F(rng.uniform(-10, 3))), l385=float(F(l385)), strain=float(F(strain)), sd20=float(F(rng.uniform(0, 0.4))),
                        core20=float(F(c20)), v12f20=float(F(v12)), v12z=float(F(z)), tair=float(F(ta)), ea=ea, eao=eao, x10=hr, x14=res,
                        rh=float(F(rng.uniform(20, 80)))))
        if mod < 1440: mod = (mod + 1) % 1440
    return prof, env_counters(rows), calm
