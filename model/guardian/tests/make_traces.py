#!/usr/bin/env python3
"""Crafted traces, one per ARCHITECTURE 7.2 row (plus 7.1 routine/contact rules), each with the EXPECTED state per minute
(column `expect`, -1 = not asserted; optional `expect_worn`). Writes tests/traces/trace_<rule>.csv + LIST.txt + INDEX.md.
Expected values are derived from the 7.2 row text, NOT from the C or the mirror:
  - hand-computed traces: crisp physical inputs (air, buttons, wear, time) whose consequence follows from the row by arithmetic;
  - HR-driven traces: the model's numeric signals (v1.2 f20 / logistic z, identical in C and mirror) are taken from the mirror,
    and an independent minimal implementation of the rows (spec_engine below) turns them into expected states.
Rows that cannot be exercised with STUB weights (NN p38/p385 paths, uncertainty sd_20 >= 0.25) are listed as such."""
import os, sys, math, struct
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))
from trace_io import minute, write_csv, default_profile, default_twin
from hg_guardian_py import Guardian, cmd_frame, K, KI
OUT = os.path.join(HERE, "traces")
U = 0xFFFF
OK, DRINK, COOL, CHECK, DANGER, IMOK, NOT_WORN, BATTERY, HELP = range(9)

def base(mod=U, tair=26.0, rh=50.0, hr=70.0, astd=0.005, **kw):
    d = dict(mod=mod, t1=34.0, t2=32.8, tair=tair, rh=rh, hr=hr, hrq=4, pi=0.6, astd=astd, dc=110000, vbat=4.0, force_worn=2)
    d.update(kw); return minute(**d)
def tick(mod, k): return U if mod == U else (mod + k) % 1440

TRACES = []
PROF_M = dict(age=75.0, sex_m=1.0, bmi=26.0, med_flags=0)
def add(name, row, mins, prof=None, twin=None, forecast=None, note=""):
    TRACES.append((name, row, mins, prof or PROF_M, twin or default_twin(), forecast, note))

def psat(t): return 0.61094 * math.exp(17.625 * t / (t + 243.04))

# ---------------------------------------------------------------- hand-computed: environmental prior
def env_trace(n, hot_from, hot_to, t=40.0, rh=40.0, astd=0.005):
    return [base(tair=t if hot_from <= k < hot_to else 26.0, rh=rh if hot_from <= k < hot_to else 50.0, astd=astd) for k in range(n)]
def expect_env(mins, hot_from, hot_to, who_too=False):   # M1.1: WHO is no longer a tier trigger
    """env_run/env_dose (v1.2) + WHO day rule (time unknown -> 32 C) -> DRINK/COOL tiers, 2-min debounce, 10-min hold."""
    run = dose = 0; who = []; tiers = {"d": [0, 0, 0], "c": [0, 0, 0], "g": [0, 0, 0]}; level = 0; exp = []; crun = 0
    for k, m in enumerate(mins):
        above = hot_from <= k < hot_to
        run = run + 1 if above else 0
        dose = min(dose + 1, 240) if above else max(dose - 1, 0)
        tin = m["tair"] - 0.15 * (m["t1"] - m["tair"])
        who.append(tin >= 32.0); w = sum(who[-45:]) >= 30 and who_too
        for key, cond in (("d", run >= 10 or dose >= 10 or w), ("c", dose >= 97)):
            r, on, off = tiers[key]; r = r + 1 if cond else 0
            if r >= 2: on, off = 1, 0
            elif on:
                if cond: off = 0
                else:
                    off += 1
                    if off >= 10: on = 0
            tiers[key] = [r, on, off]
        # M13 Danger by persistence: COOL tier on >= HG_PD_COOL_MIN while the air is above the PSU line (f20 rises at rest in
        # this hot room, so "not falling" holds; the C/mirror check of the slope is exercised by the spec traces)
        crun = crun + 1 if tiers["c"][1] else 0
        r, on, off = tiers["g"]; cond = bool(KI("HG_PD")) and tiers["c"][1] and crun >= KI("HG_PD_COOL_MIN") and above; r = r + 1 if cond else 0
        if r >= 2: on, off = 1, 0
        elif on:
            if cond: off = 0
            else:
                off += 1
                if off >= 10: on = 0
        tiers["g"] = [r, on, off]
        tgt = 3 if tiers["g"][1] else 2 if tiers["c"][1] else 1 if tiers["d"][1] else 0
        level = level + 1 if tgt > level else tgt
        exp.append(4 if (level == 3 or (KI("HG_COOL_TRANSIT") and level == 2 and tgt == 3)) else level)   # state code DANGER = 4
    return exp
m = env_trace(220, 30, 90); e = expect_env(m, 30, 90)
for x, v in zip(m, e): x["expect"] = v
add("drink_env", "DRINK on: env-prior run >= 10 min; Hold/debounce (on at 2nd true minute, off at 10th false minute)", m,
    note="40 C / 40 % for 60 min (above the older Rest line); WHO day rule also true")
m = env_trace(420, 30, 200); e = expect_env(m, 30, 200)
for x, v in zip(m, e): x["expect"] = v
add("cool_dose", "COOL on: heat dose >= 97 min (cap 240), dose unwinds 1/min", m)
# WHO day rule only (no env line: dry air)
m = [base(mod=(840 + k) % 1440, tair=33.0 if 30 <= k < 120 else 26.0, rh=35.0, astd=0.03) for k in range(200)]
w = []; exp = []; r = on = off = 0
for k, x in enumerate(m):
    tin = x["tair"] - 0.15 * (x["t1"] - x["tair"]); w.append(tin >= 32.0)
    cond = False   # M1.1: the WHO day rule only sets a reason bit; it never switches a tier
    r = r + 1 if cond else 0
    if r >= 2: on, off = 1, 0
    elif on:
        off = 0 if cond else off + 1
        if off >= 10: on = 0
    x["expect"] = on
add("drink_who_day", "M1.1: WHO day rule (T_in >= 32 C 30/45 min) is NOT a tier trigger (reason bit only)", m, note="14:00, 33 C / 35 % RH, ACTIVE (routine quiet rule not involved)")
m = [base(mod=(1380 + k) % 1440, tair=26.0, rh=50.0, astd=0.001) for k in range(120)]
for k, x in enumerate(m): x["expect"] = OK
add("drink_who_night", "M1.1: WHO night rule (T_in >= 24 C, 23-07) sets night_heat + one nudge, never DRINK", m,
    note="corrected 24.8 C bedroom: night_heat from minute 29, nudge once (checked by tests/test_m1.py)")
# AC evidence: a 2.9 C cooling step while HOME latches 120 min and blocks the WHO rule
m = []
for k in range(240):
    t = 28.0 if k < 10 else (28.0 - 2.5 * (k - 10) / 9.0 if k < 19 else 25.5)
    x = base(mod=(1380 + k) % 1440, tair=t, rh=50.0, astd=0.001); x["expect"] = OK; m.append(x)
add("who_ac_evidence", "WHO night flag needs 'no AC evidence' (DESIGN: >= 2 C drop in 15 min while HOME, latched 120 min)", m)
# env line selection: ADL line when ACTIVE >= 10 of last 30 min, Rest line otherwise
m = [base(tair=31.0, rh=90.0, astd=0.005 if k < 60 else 0.05) for k in range(140)]
for k, x in enumerate(m): x["expect"] = OK if k < 60 + 9 + 9 + 1 else DRINK   # ACTIVE count reaches 10 at k=69, run 10 at 78, on at 79
add("env_line_adl_vs_rest", "Env-prior line: Pa >= 8.048 - 0.1399 T if ACTIVE >= 10/30 min, else 8.308 - 0.1370 T (R1 3.1)", m,
    note="31 C / 90 % RH lies between the two older lines: resting = below, active = above")
# young profile: the same air is below the young line -> nothing
m = [base(tair=31.0, rh=90.0, astd=0.05) for k in range(140)]
for x in m: x["expect"] = OK
add("env_line_young", "Env-prior line: young wearers (age < 65, no flags) use 10.522 - 0.1781 T (v1.2)", m, prof=dict(age=30.0, sex_m=1.0, bmi=23.0, med_flags=0))

# ---------------------------------------------------------------- HR-driven traces: spec engine on the model's numbers
def spec_engine(mins, prof, sig, press=None):
    """Independent minimal implementation of the 7.2 rows used by the HR-driven traces (no routine, no contact)."""
    age, f = prof["age"], prof["med_flags"]
    md = mc = 0.2 if age >= 65 else 0.0
    if f & (2 | 8): md += 0.1
    if f & 4: md += 0.1; mc += 0.1
    if f & 1: md += 0.1; mc += 0.1
    T = {k: [0, 0, 0] for k in "dcgp"}
    def tier(key, cond):
        r, on, off = T[key]; r = r + 1 if cond else 0
        if r >= 2: on, off = 1, 0
        elif on:
            off = 0 if cond else off + 1
            if off >= 10: on = 0
        T[key] = [r, on, off]; return on
    pd_ring = [0.0] * 11; pdv_ring = [0.0] * 11; pd_i = 0; pd_n = 0; pd_run = 0   # M13 (+ T5 D2 protected ring)
    f32 = np.float32; mb = None; mb_age = 0; mb_warm = 255; mb_run = 0   # M19 Marble (independent float32 re-implementation of R6 s3.1)
    sf_t1 = f32(33.0); sf_ta = f32(20.0); sf_run = 0                     # B5-v7 skin floor (independent float32 re-implementation)
    sf_cut = f32(f32(37.8) - f32(0.1)) if (f & (1 | 16)) else f32(37.8)  # HR-blunted (beta-blocker / other) -> 0.1 C earlier
    level = 0; don = 0; last_worn = 0; hr_bad = 0; still_run = 0; cool_min = 0; ack = 0; strain_run = 0
    check = False; ct = 0; snooze = 0; fam = False; help_ = False; exp = []; prev_cause = 0; who = []
    for k, (m, s) in enumerate(zip(mins, sig)):
        worn = m["force_worn"]
        don = (0 if last_worn != 2 else min(don + 1, 60)) if worn == 2 else 0; last_worn = worn
        valid = worn == 2 and don >= 5; th = valid and don >= 20
        tin = s["tin"]; who.append(tin >= 32.0)
        # B5-v7: skin EWMA30 (33 C fed while off / NaN), air EWMA60 (20 C fed while NaN)
        t1v = m["t1"]; t1v = f32(t1v) if (worn != 0 and t1v == t1v and -40 <= t1v <= 85) else f32(33.0)
        sf_t1 = f32(sf_t1 + f32(f32(1.0 / 30.0) * f32(t1v - sf_t1)))
        sf_ta = f32(sf_ta + f32(f32(1.0 / 60.0) * f32((tin if tin == tin else f32(20.0)) - sf_ta)))
        # M5.2: uncalibrated lowering min(0.10, 1.645 * scale * sd20 - h_cal); M1.3: total lowering capped at 0.20
        unc = 0.0
        if th:
            if int(K("HG_UNC_CONST_MODE")): unc = min(0.10, float(K("HG_UNC_LOWER_CONST")))       # M11.4 conformal widths
            else:
                h = float(np.float32(np.float32(np.float32(K("HG_UNC_Z") * K("HG_UNC_SD_SCALE_EFF")) * s["sd20"]) - K("HG_UNC_HALF_CAL_EFF")))
                unc = min(0.10, max(0.0, h))
        ld = np.float32(min(np.float32(np.float32(md) + np.float32(unc)), np.float32(0.20)))
        lc = np.float32(min(np.float32(np.float32(mc) + np.float32(unc)), np.float32(0.20)))
        # M9.1 design A: DRINK ceiling = absolute 37.85 C WITHOUT margins (+ the personal-relative line, never learned in these
        # short / time-unknown traces); COOL keeps the capped margins
        # M11.2 DRINK: v1.2 f20 above the absolute ceiling (relative line never learned in these traces); M11.3 COOL on max(NN, v1.2) when OOD
        la = np.float32(min(np.float32(unc), np.float32(0.20)))
        f20g = max(s["f20"], s["v12f20"]) if s["ood"] else s["f20"]
        pd_ring[pd_i] = f20g; pdv_ring[pd_i] = s["v12f20"]; pd_i = (pd_i + 1) % 11
        f20_old = pd_ring[pd_i]; f20v_old = pdv_ring[pd_i]; pd_n = min(pd_n + 1, 11)   # M13 rings, every minute
        ctx = (s["tin"] == s["tin"] and s["tin"] >= K("HG_V12_CTX_C")) or s["above_old"] or s["ood"]   # M12 heat-context gate
        c1 = valid and ctx and s["v12f20"] >= np.float32(np.float32(37.85) - la); c2 = th and f20g >= np.float32(np.float32(38.35) - lc)
        cp = th and s["v12f20"] >= np.float32(np.float32(38.35) - np.float32(min(mc, 0.20)))   # M3.1 shadow v1.2 Go-cool
        env1 = s["env_run"] >= 10 or s["env_dose"] >= 10; env2 = s["env_dose"] >= 97; w = False   # M1.1
        env1 = env1 or (worn == 2 and th and sf_ta >= f32(32.0) and sf_t1 >= f32(36.8))   # B5-v7 skin DRINK (protected, HR-free)
        sf_run = sf_run + 1 if (worn == 2 and th and sf_ta >= f32(32.0) and sf_t1 >= sf_cut) else 0
        sfloor = bool(KI("HG_SF")) and sf_run >= 5                                          # B5-v7 skin-floor Danger
        hr_bad = 0 if s["hr_valid"] else hr_bad + 1
        lg = hr_bad <= 5 and valid and s["z"] >= np.float32(-1.450010)
        btn = m["button"]
        if btn == 2 and not help_: help_ = True; check = False
        if m.get("cmd") and m["cmd"][0] == 0x12 and m["cmd"][1] == 3: help_ = False
        # M19 Marble: E10/E60 of f20 (36.9 when not worn), A30/A120 of min(a_std, 0.30), leaky dose over 37.9, armed after 24 h,
        # thermal-ok, corrected air >= 28 C within 60 min; s = w0 + wL (E60-37.5) + wJ (E10-E60) + wB A30 + wS A120 + wD D >= cut x 5 min
        x = f20g if (worn != 0 and f20g == f20g) else f32(36.9)
        a_ = m["astd"]; a_ = f32(0) if not (a_ == a_ and 0 <= a_ <= 16) else f32(a_); a_ = min(a_, f32(0.30))
        if mb is None: mb = [x, x, a_, a_, f32(0)]
        mb[0] = f32(mb[0] + f32(f32(0.1) * f32(x - mb[0]))); mb[1] = f32(mb[1] + f32(K("HG_MB_A60") * f32(x - mb[1])))
        mb[2] = f32(mb[2] + f32(K("HG_MB_A30") * f32(a_ - mb[2]))); mb[3] = f32(mb[3] + f32(K("HG_MB_A120") * f32(a_ - mb[3])))
        mb[4] = f32(f32(mb[4] * K("HG_MB_DKEEP")) + (f32(x - f32(37.9)) if x > f32(37.9) else f32(0)))
        mb_warm = 0 if (tin == tin and tin >= f32(28)) else min(mb_warm + 1, 255); mb_age = min(mb_age + 1, 65535)
        sc_ = K("HG_MB_W0")
        for wv, tv in ((K("HG_MB_WL"), f32(mb[1] - f32(37.5))), (K("HG_MB_WJ"), max(f32(mb[0] - mb[1]), f32(0)) if KI("HG_MB_JUMP_RISE") else f32(mb[0] - mb[1])), (K("HG_MB_WB"), mb[2]), (K("HG_MB_WS"), mb[3]), (K("HG_MB_WD"), mb[4])):
            sc_ = f32(sc_ + f32(wv * tv))
        mb_run = min(mb_run + 1, 255) if (th and mb_age >= 1440 and mb_warm <= 60 and sf_t1 >= f32(35.5) and sc_ >= K("HG_MB_CUT")) else 0   # B5-v7 skin arming
        marble = bool(KI("HG_MARBLE")) and mb_run >= 5
        beh = False; transit = False
        if worn != 0:
            strain_run = strain_run + 1 if (th and s["strain"] >= 7.0) else 0
            tier("d", c1 or env1 or w); tier("c", c2 or env2 or strain_run >= 10)
            w2 = tier("p", cp or env2)   # M3.1: behaviour armed by the v1.2 Go-cool, never by the NN
            still_run = still_run + 1 if s["still"] else 0
            if w2:
                cool_min += 1
                if btn: ack = 1
            else: cool_min = 0; ack = 0
            beh = w2 and cool_min >= 10 and still_run >= 10 and not ack
            pd_run = pd_run + 1 if T["c"][1] else 0   # M13 Danger by persistence (COOL tier on >= X, f20 not falling, evidence)
            # M13 + T5 D2: (a) protected trigger = PSU line or v1.2 z, slope of the v1.2 f20 (>= -0.01 C / 10 min);
            #             (b) NN-added trigger = NN P385 >= 0.5, slope of the tiers' f20 (>= 0)
            run_ok = T["c"][1] and pd_run >= KI("HG_PD_COOL_MIN") and pd_n >= 11
            sv = s["v12f20"] == s["v12f20"] and f20v_old == f20v_old and np.float32(s["v12f20"] - f20v_old) >= -np.float32(0.01)
            sn = f20g == f20g and f20_old == f20_old and np.float32(f20g - f20_old) >= 0
            pers = bool(run_ok and ((sv and (s["env_above"] or (valid and s["z"] >= np.float32(-2.197225)))) or (sn and th and s["lp385"] >= 0.0)))
            pers = pers and bool(KI("HG_PD"))   # M19: the M13 rule is off in the default build
            tier("g", lg or beh or pers or marble or sfloor)
            tgt = 3 if T["g"][1] else 2 if T["c"][1] else 1 if T["d"][1] else 0
            level = level + 1 if tgt > level else tgt
            transit = bool(KI("HG_COOL_TRANSIT")) and level == 2 and tgt == 3   # M19b: COOL stepping stone -> Danger screen, no nudge
        imok = False
        if snooze > 0: snooze -= 1
        if not help_ and worn != 0:
            if check:
                if level < 3: check = False
                elif btn == 1: imok = True; check = False; snooze = 15
                else: ct += 1
            elif level == 3 and snooze == 0: check = True; ct = 0
        if help_: st = HELP
        elif imok: st = IMOK
        elif check: st = DANGER
        elif level == 3 or transit: st = DANGER
        else: st = [OK, DRINK, COOL][level]
        exp.append(st)
    return exp

def signals(mins, prof, twin):
    g = Guardian(prof, twin); sig = []
    for m in mins:
        o = g.step(dict(m, forecast=None)); a = o["aux"]
        sig.append(dict(f20=a["core20_noff"], ood=bool(a["x"][14] > K("HG_OOD_RESERVE") or a["x"][10] > K("HG_OOD_HR")), sd20=o["core_sd_20"], v12f20=a["v12_f20"], z=a["v12_z"], env_run=a["env_run"], env_dose=a["env_dose"], hr_valid=o["core_hr_valid"],
                        still=a["still"], strain=o["core_strain"], tin=a["t_air_corr"], above_old=bool(a["env_above_old"]),
                        env_above=bool(a["env_above"]), lp385=o["core_logit_p385"]))
    return sig

def hr_ramp(n, rest, peak, up_at, down_at, tair=36.0, rh=30.0, astd=0.05, **kw):
    out = []; hr = rest
    for k in range(n):
        tgt = peak if up_at <= k < down_at else rest
        hr += 0.15 * (tgt - hr)
        out.append(base(tair=tair, rh=rh, hr=hr, astd=astd, **kw))
    return out

YOUNG = dict(age=25.0, sex_m=1.0, bmi=23.0, med_flags=0)
def spec_trace(name, row, mins, prof, twin=None, note=""):
    twin = twin or dict(default_twin(), rest_hr=60.0)
    e = spec_engine(mins, prof, signals(mins, prof, twin))
    for x, v in zip(mins, e): x["expect"] = v
    add(name, row, mins, prof, twin, note=note)
    return e

# 30 C air: below WHO day and below the young/older lines -> only the HR model drives the tiers
spec_trace("drink_f20", "DRINK on: f20 >= 37.85 - m_drink for 2 consecutive min (v1.2 HG_T_DRINK_WATER)",
           hr_ramp(240, 60, 150, 20, 180, tair=30.0, rh=30.0), YOUNG)
spec_trace("cool_f20_danger_logistic", "COOL on: f20 >= 38.35 - m_cool; DANGER on: v1.2 logistic z >= -1.450 for 2 min; escalation 1 level/min",
           hr_ramp(300, 60, 178, 20, 220, tair=30.0, rh=30.0), YOUNG)
spec_trace("older_margin", "Older margin: watch tiers 0.20 C earlier at age >= 65 (Kenny 2017)",
           hr_ramp(240, 60, 140, 20, 180, tair=30.0, rh=30.0), dict(age=75.0, sex_m=1.0, bmi=26.0, med_flags=0))
spec_trace("med_margins", "Medication margins (bb 0.10 both, low-sweat 0.10 both, diuretic 0.10 DRINK) + M1.3 total cap 0.20 C",
           hr_ramp(240, 60, 130, 20, 180, tair=30.0, rh=30.0), dict(age=75.0, sex_m=0.0, bmi=27.0, med_flags=1 | 2 | 4))
m = hr_ramp(300, 60, 178, 20, 240, tair=30.0, rh=30.0)
for k in range(150, 185): m[k]["hrq"] = 2; m[k]["hr"] = float("nan")       # 35 min of MOTION-flagged PPG
spec_trace("hr_gating", "HR gating: logistic path disabled when hr_valid == 0 for > 5 min", m, YOUNG)
m = hr_ramp(300, 60, 178, 20, 260, tair=30.0, rh=30.0)
e = spec_trace("check_danger_family", "CHECK from DANGER: ask 0/2/5 min, family flag at 5 min without a press", m, YOUNG)
m = hr_ramp(300, 60, 178, 20, 260, tair=30.0, rh=30.0)
first_d = next((k for k, v in enumerate(e) if v == DANGER), None)
if first_d is not None:
    m[first_d + 3]["button"] = 1
spec_trace("check_press_imok_snooze", "Short press during CHECK: IMOK, CHECK snoozed 15 min, re-ask if the condition persists", m, YOUNG)
# behaviour path: COOL by heat dose, wrist still, no press -> DANGER (time unknown so the routine rules stay off)
m = env_trace(420, 30, 200, astd=0.001)
spec_trace("behaviour_path", "DANGER behaviour path: COOL on >= 10 min, no press, still >= 10 min -> CHECK, family at 5 min", m,
           default_profile(), default_twin())
m = env_trace(420, 30, 200, astd=0.001)
for k in (128, 129): m[k]["button"] = 1                                       # press during COOL = v1.2 acknowledgement
spec_trace("behaviour_acknowledged", "Behaviour path needs 'no press': a press during COOL acknowledges it", m, default_profile(), default_twin())
# donning blank: band put on at minute 0 with a hot, hard-working wearer -> no thermal (f20) tier for 20 min
m = hr_ramp(120, 150, 150, 0, 120, tair=30.0, rh=30.0)
spec_trace("donning_blank", "Donning blank: first 20 min after worn -> 2: no thermal alarms (valid after 5 min for the HR path)", m, YOUNG,
           note="HR already 150 at donning; the HR-only logistic path is allowed after 5 min")
# HELP: long press anywhere -> family immediately, latched until 0x12 type 3 (a type-1 ack does not clear it)
m = [base() for _ in range(90)]
m[20]["button"] = 2
for k in range(90): m[k]["expect"] = OK if k < 20 else (HELP if k < 61 else OK)
m[40]["cmd"] = cmd_frame(0x12, ack_type=1, alarm_id=(1 << 16) | 21)
m[60]["cmd"] = cmd_frame(0x12, ack_type=3, alarm_id=(1 << 16) | 21)
for k in range(60, 90): m[k]["expect"] = OK
m[60]["expect"] = OK
add("help_latch", "Long press >= 2 s anywhere: HELP, family flag immediately, latched until phone 0x12 ack type 3", m,
    note="alarm id = (seq << 16) | minute counter = (1<<16)|21; the ack is applied before minute 60's step")
# NOT_WORN: worn == 0 for 10 min -> screen; tiers frozen (not cleared) and resume after re-wear
m = env_trace(200, 0, 200)
for k in range(60, 100): m[k]["force_worn"] = 0
e = expect_env(m, 0, 200)
for k, x in enumerate(m):
    if k < 60: x["expect"] = e[k]
    elif k < 69: x["expect"] = DRINK          # frozen tier still shown until NOT_WORN at the 10th off minute (60..69)
    elif k < 100: x["expect"] = NOT_WORN
    else: x["expect"] = -1                     # the frozen state resumes; dose kept counting -> COOL soon after
m[100]["expect"] = DRINK
add("not_worn_freeze", "NOT_WORN: worn == 0 for 10 min -> NOT_WORN screen; all tiers frozen (not cleared)", m)
# BATTERY
m = [base(vbat=4.0 if k < 30 else 3.30) for k in range(60)]
for k, x in enumerate(m): x["expect"] = OK if k < 30 else BATTERY
add("battery", "BATTERY: VBAT < 3.35 V -> BATTERY state (when no tier is on); < 3.5 V soft haptics", m)

# ---------------------------------------------------------------- contact self-check (real hg_contact, force_worn off)
def contact_min(t1, t2, ta, **kw):
    return base(t1=t1, t2=t2, tair=ta, force_worn=0xFF, t1_5s=[t1] * 12, t2_5s=[t2] * 12, tair_5s=[ta] * 12, **kw)
m = []
for k in range(100):
    if k < 40: x = contact_min(34.0, 32.8, 25.0)
    else:   # band taken off: T1 and T2 relax to room air
        a = math.exp(-(k - 40) / 3.0); t1 = 25.0 + 9.0 * a; t2 = 25.0 + 7.8 * a
        x = contact_min(t1, t2, 25.0, dc=1200, pi=float("nan"), hrq=0, hr=float("nan"))
    m.append(x)
for k, x in enumerate(m):
    x["expect_worn"] = 0 if k < 1 else (2 if k < 40 else (0 if k >= 42 else -1))   # 2-min hysteresis: switch on the 2nd minute
    x["expect"] = -1 if k < 40 else (NOT_WORN if k >= 52 else -1)
add("contact_off", "Contact: off = PPG DC < 20 000 (no skin) or T1 ~ T2 ~ T_air; 2-min hysteresis; NOT_WORN after 10 min", m)
m = []
for k in range(120):
    t1 = 34.0 if (k < 50 or k >= 80) else 32.8                      # sudden -1.2 C step (air gap), recovers at 80
    t2 = 32.8 if (k < 50 or k >= 80) else 32.3
    t1s = [t1] * 12
    if k == 50: t1s = [34.0] * 4 + [32.8] * 8
    x = base(t1=t1, t2=t2, tair=25.0, force_worn=0xFF, t1_5s=t1s, t2_5s=[t2] * 12, tair_5s=[25.0] * 12)
    x["expect_worn"] = 2 if 1 <= k < 50 else (1 if 52 <= k < 80 else (2 if k >= 82 else -1)); m.append(x)
add("contact_loose_step", "Contact: loose = T1 step -0.5..-2 C in < 2 min not matched by T_air (latched until T1 recovers)", m)
m = []
for k in range(60):
    x = base(t1=34.0, t2=32.8, tair=25.0, force_worn=0xFF, charging=1 if 20 <= k < 40 else 0)
    x["expect_worn"] = 0 if (k < 1 or 20 <= k < 40) else (2 if k >= 41 else -1); m.append(x)
add("contact_charging", "Contact: charging pin = off immediately", m)
m = []
for k in range(80):   # 35 C room, band lying on a table: thermal rules disabled, only PPG + IMU decide
    x = base(t1=35.2, t2=35.1, tair=35.0, force_worn=0xFF, dc=110000 if k < 40 else 1200)
    x["expect_worn"] = 2 if 1 <= k < 40 else (0 if k >= 42 else -1); m.append(x)
add("contact_hot_room", "Contact: in rooms >= 34 C the thermal rules are disabled (R2 s5 caveat); PPG DC still detects off", m,
    note="T1 ~ T2 ~ T_air would read 'off' at 25 C; at 35 C it does not, until the PPG DC drops")

# ---------------------------------------------------------------- routine
m = [base(mod=(590 + k) % 1440, astd=0.05 if k < 10 else 0.005) for k in range(270)]
for k, x in enumerate(m):
    x["expect"] = OK if k < 190 else CHECK            # q = k - 9 for k >= 10: q > 180 at k = 190
m[210]["button"] = 1
for k in range(210, 225): m[k]["expect"] = OK
m[210]["expect"] = IMOK
for k in range(225, 270): m[k]["expect"] = CHECK
add("routine_quiet_fallback", "Routine (a) fallback before 3 learned days: awake quiet run > 180 min -> CHECK; family at 10 min; press -> IMOK + 15-min snooze", m,
    note="10:00 start, a_std 0.005 g (QUIET, not still); expected: CHECK at q = 181, family at check minute 10, press at 200")
m = [base(mod=(590 + k) % 1440, tair=31.5, rh=45.0, astd=0.05 if k < 10 else 0.005) for k in range(140)]
for k, x in enumerate(m): x["expect"] = OK if k < 100 else CHECK   # q > 90 at k = 100
add("routine_heat_coupling", "Routine (c) heat coupling: T_in >= 31 C halves B and the fallback (90 min)", m)
# T5 D5: worn from 22:00 (the whole default 22:00-08:00 sleep window is observed, >= 70 % worn)
m = [base(mod=(1320 + k) % 1440, tair=22.0, astd=0.001) for k in range(760)]
for k, x in enumerate(m): x["expect"] = OK if k < 720 else CHECK      # 22:00 + 720 = 10:00 = min(W + 2 h, 10:00), W = 08:00 default
add("routine_nowake", "Routine (b) no wake by W + 2 h (W fallback 08:00), band worn through the night -> CHECK at 10:00; family at 10 min", m)
m = [base(mod=(600 + k) % 1440, tair=22.0, astd=0.001) for k in range(100)]
for k, x in enumerate(m): x["expect"] = OK
add("routine_nowake_morning_donning", "T5 D5: band put on (or rebooted) at 10:00 after an unobserved night: no no-wake CHECK (fresh observation window)", m)
fc = bytearray(72)
for h in range(24): fc[3 * h] = 30; fc[3 * h + 1] = 40; fc[3 * h + 2] = 1      # heat-day flag
m = [base(mod=(1320 + k) % 1440, tair=22.0, astd=0.001) for k in range(760)]
for k, x in enumerate(m): x["expect"] = OK if k < 660 else CHECK      # heat day: W + 1 h = 09:00 (worn from 22:00, T5 D5)
add("routine_nowake_heatday", "Routine (b) on a heat day (forecast flag): W + 1 h -> CHECK at 09:00", m, forecast=bytes(fc))
m = [base(mod=(750 + k) % 1440, astd=0.05 if (k < 30 or k >= 70) else 0.001) for k in range(100)]   # 12:30: after the no-wake window
m[30]["apeak"] = 3.5
for k, x in enumerate(m): x["expect"] = OK if k < 32 else (CHECK if k < 70 else OK)
add("routine_impact_stillness", "M19-impact: impact |a| >= 3 g then 2 still minutes, no press -> CHECK input only (no fall-detection claim); family at 5 min", m)
m = [base(mod=(750 + k) % 1440, astd=0.05 if (k < 30 or k >= 70) else 0.001) for k in range(100)]
m[30]["apeak"] = 2.6
for x in m: x["expect"] = OK
add("routine_impact_ordinary_2g6", "M19-impact: a 2.6-g peak (ordinary arm movement on real HeatIN watches) + stillness -> no CHECK", m)
m = [base(mod=(750 + k) % 1440, astd=0.05 if (k < 30 or k >= 70) else 0.001) for k in range(100)]
m[30]["apeak"] = 3.5; m[31]["button"] = 1
for x in m: x["expect"] = OK
add("routine_impact_press_cancels", "M19-impact: impact >= 3 g then a press in the stillness window (she answers) -> no CHECK", m)
m = [base(mod=U, astd=0.005) for k in range(300)]
for x in m: x["expect"] = OK
add("time_unknown", "Time unknown: routine rules disabled (no CHECK after 300 quiet minutes), circadian features 0", m)

m = [base(tair=30.0, rh=20.0, astd=0.005) for _ in range(180)]
for k, x in enumerate(m): x["expect"] = OK if (k < 20 or k >= 45) else -1
# minutes 21-32 DRINK in C: Kalman start-up (CT0 37.1 C) on top of a clamped resting f20 of 37.62 vs the 37.65 line (residual
# 0.03 C headroom, reported); the assertion is the steady state from minute 45 on (unclamped v1.2: DRINK all 180 minutes)
add("m12_dry_room_rest", "M1.2: RH clamped to [38, 60] % in the v1.2 linear correction -> no resting DRINK in a dry 30 C room", m,
    prof=dict(age=75.0, sex_m=0.0, bmi=26.0, med_flags=0), note="unclamped v1.2 f20 = 37.84 C here (B5 finding 2)")

m = [base(tair=24.0 if k < 150 else 32.0, rh=40.0, hr=95.0, astd=0.15, t1=34.5, t2=33.5) for k in range(300)]
for k, x in enumerate(m): x["expect"] = -1 if (k < 30 or 150 <= k < 180) else (OK if k < 150 else DRINK)
add("m12_heat_context", "M12: HR-only v1.2 DRINK ceiling needs heat context -> chores at HR 95 in a 24 C room: no DRINK (v1.2 f20 "
    "37.86 >= 37.85); same chores at 32 C (corrected air >= T_ctx): DRINK", m, prof=dict(age=75.0, sex_m=0.0, bmi=26.0, med_flags=0),
    note="-DHG_V12_CTX=0 (no gate) raises DRINK in the 24 C phase")

OLDER_F = dict(age=78.0, sex_m=0.0, bmi=26.0, med_flags=0)
BB_OLD = dict(age=78.0, sex_m=0.0, bmi=26.0, med_flags=1)
def marble_day(ta, astd, t1=36.0):   # B5-v7: wrist skin 36.0 C (Marble skin arming >= 35.5 C); was 35.0 C before freeze-7
    return ([base() for _ in range(1440)] + [base(tair=ta, rh=45.0, astd=astd, hr=85.0, t1=t1, t2=t1 - 0.8) for _ in range(120)]
            + [base(tair=ta, rh=45.0, astd=0.005, hr=72.0, t1=t1, t2=t1 - 0.8) for _ in range(120)])
spec_trace("m19_marble_warm_chores", "M19 Marble Danger (spec engine = independent float32 Marble): after 24 h of wear, 0.12-g chores in a 32 C room "
           "(beta-blocker, HR 85): the movement 'wind' term arms Marble -> DANGER -> CHECK at ~45 min (R6 s3.4 KNOWN RISK: a false alarm "
           "on purpose here; forecast f20 ~37.3 C)", marble_day(32.0, 0.12), BB_OLD, twin=dict(default_twin(), rest_hr=70.0),
           note="-DHG_MARBLE=0 removes the DANGER")
e19 = spec_trace("m19b_cool_stepping_stone", "M19b: the ladder steps DRINK -> level 2 while the Danger tier (here Marble) is already on: that "
           "level-2 minute shows the DANGER screen with no COOL vibration, then the Danger CHECK; no COOL state is ever shown",
           marble_day(32.0, 0.12), BB_OLD, twin=dict(default_twin(), rest_hr=70.0), note="-DHG_COOL_TRANSIT=0 shows COOL for 1 minute before DANGER")
assert 2 not in e19 and 4 in e19, "stepping-stone trace must reach DANGER without a COOL state"
e19h = spec_trace("m19b_cool_holds", "M19b: a COOL that holds (Danger tier comes on 23 min later) keeps the COOL screen + vibration, then DANGER",
           hr_ramp(300, 60, 178, 20, 220, tair=30.0, rh=30.0), YOUNG)
assert 2 in e19h and 4 in e19h and e19h.index(4) - e19h.index(2) > 2, "hold trace must show COOL before DANGER"
spec_trace("m19_marble_cool_room", "M19 Marble heat-context gate: the same chores in a 26 C room never arm Marble (no DANGER)",
           marble_day(26.0, 0.12), BB_OLD, twin=dict(default_twin(), rest_hr=70.0))
# ---------------------------------------------------------------- B5-v7 (freeze-7): skin floor, skin DRINK, Marble skin arming
eb = spec_trace("b5v7_marble_cool_skin", "B5-v7 Marble skin arming: the M19 warm-chores day with a cool wrist (skin 35.0 C < HG_MB_SKIN_C 35.5) "
           "never arms Marble (no DANGER) - the R6 s3.4 known-risk false alarm is gone", marble_day(32.0, 0.12, t1=35.0), BB_OLD,
           twin=dict(default_twin(), rest_hr=70.0), note="-DHG_MB_SKIN_C=0 brings the M19 DANGER back")
assert 4 not in eb, "cool-skin chores must not fire Danger"
def skin_day(ta, t1_peak, hr=72.0, n_hot=240):
    """24 h at 26 C, then a hot still afternoon: air ta, HR flat (a heart that does not race), wrist skin ramps 34.5 -> t1_peak"""
    out = [base() for _ in range(1440)]
    for k in range(n_hot):
        t1 = 34.5 + (t1_peak - 34.5) * min(1.0, k / 120.0)
        out.append(base(tair=ta, rh=30.0, astd=0.004, hr=hr, t1=t1, t2=t1 - 0.3))
    return out
es = spec_trace("b5v7_skin_floor_flat_hr", "B5-v7 skin-floor Danger (HR-free): hot still afternoon at 36 C air, HR flat at 72, insulated wrist "
           "skin rises to 38.2 C -> skin DRINK at sf_t1 >= 36.8, then DANGER -> CHECK at sf_t1 >= 37.8 (5 min), no HR rise needed",
           skin_day(36.0, 38.2), OLDER_F, twin=dict(default_twin(), rest_hr=70.0), note="-DHG_SF=0 removes the DANGER")
assert 4 in es and 1 in es and es.index(1) < es.index(4), "skin-floor trace must show DRINK then DANGER"
eh = spec_trace("b5v7_skin_floor_bb_earlier", "B5-v7: the same afternoon with skin peaking at 37.75 C: no Danger for a wearer without flags, "
           "Danger for a beta-blocker wearer (HR-blunted: skin floor 0.1 C earlier, 37.7 C)", skin_day(36.0, 37.75), BB_OLD,
           twin=dict(default_twin(), rest_hr=70.0), note="med_flags 1; the no-flag twin is b5v7_skin_floor_noflag")
en = spec_trace("b5v7_skin_floor_noflag", "B5-v7: skin peaking at 37.75 C, no medication flag: skin DRINK only, no DANGER",
           skin_day(36.0, 37.75), OLDER_F, twin=dict(default_twin(), rest_hr=70.0))
assert 4 in eh and 4 not in en and 1 in en, "HR-blunted switch must change only the flagged wearer"
ec = spec_trace("b5v7_skin_floor_cool_room", "B5-v7 skin floor needs a hot room: wrist skin 38.2 C in a 29 C room (sf_ta < 32 C) -> no "
           "skin DRINK, no skin-floor DANGER", skin_day(29.0, 38.2), OLDER_F, twin=dict(default_twin(), rest_hr=70.0))
assert 4 not in ec, "cool-room skin must not fire Danger"

# ---------------------------------------------------------------- write
os.makedirs(OUT, exist_ok=True)
names = []; idx = ["# Crafted traces (ARCHITECTURE 7.2 rows)\n", "| trace | row | minutes | note |", "|---|---|---|---|"]
for name, row, mins, prof, twin, fcb, note in TRACES:
    fn = "trace_%s.csv" % name; names.append(fn)
    write_csv(os.path.join(OUT, fn), mins, prof, twin, forecast=fcb, with_expect=True)
    idx.append("| %s | %s | %d | %s |" % (fn, row, len(mins), note))
idx += ["", "Not exercisable with STUB weights (HG2_WEIGHTS_STUB = 1): the NN DRINK path (logit_p38 >= HG2_LOGIT_CUT_38), the NN DANGER",
        "path (logit_p385 >= HG2_LOGIT_CUT_385) and the uncertainty row (sd_20 >= 0.25: the stub has sd_20 = 0). They are code-covered",
        "by the property run and become crafted traces when B2's weights and cuts exist."]
open(os.path.join(OUT, "LIST.txt"), "w").write("\n".join(names) + "\n")
open(os.path.join(OUT, "INDEX.txt"), "w").write("\n".join(idx) + "\n")
print(len(names), "traces written")
