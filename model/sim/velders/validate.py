"""Validation checklist (R1 §7 V1-V30, R3 (i)-(iii), R2 §6.5, Ji agreement, monotonicity). SIMULATION.

python -I -m velders.validate [--section all|rest|limits|multiday|indoor|sensor|agree] [--n 500]
Writes /home/claude/hg_ai/sim/validation_rows.json (merged by section) and VALIDATION.md.
Targets/tolerances are copied from ARCHITECTURE.md §3.3 / R1 §7 / R2 §6.5 / R3 §1.6; never edited here.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np

from . import body as B
from .body import TwoNodeOlder, ALL_FEATURES, p_sat_torr, circadian
from .protocols import load_persons, meade, psu, constant_run, person_met, rh_from_pa_torr, _env
from .population import thirst_threshold

ROWS_PATH = "/home/claude/hg_ai/sim/validation_rows.json"
CMD = "cd /home/claude/hg_ai/sim && python3 -I -m velders.validate --section {s}"


def row(id_, target, tol, value, passed, why="", section="", note=""):
    return dict(id=id_, target=target, tol=tol, value=value, result="PASS" if passed else "FAIL", why=why,
                section=section, cmd=CMD.format(s=section), note=note)


def thirst_policy_factory(P):
    thr = thirst_threshold(P)
    state = {"refr": np.zeros(len(P["mass_kg"]))}

    def pol(b, i):
        defp = np.maximum(b.deficit_g, 0) / (P["mass_kg"] * 1000.0) * 100.0
        th = (defp > thr) & (state["refr"] <= 0)
        state["refr"] = np.where(th, 30.0, state["refr"] - 1)
        return np.where(th, 150.0, 0.0) + (np.where(i % 240 == 120, 200.0, 0.0))   # + a glass with each snack/meal (2 in 8 h)
    return pol


# =========================================================================== resting / indoor
def healthy(P):
    """Meade/O'Connor/Lee cohorts were healthy community volunteers (R1 §8.9): validate the resting rows
    on the frailty tercile 1 (f < 1/3) analogue; medication flags are kept (56 % of Meade's cohort had
    prescriptions)."""
    k = P["frailty"] < 1 / 3
    return {kk: v[k] for kk, v in P.items()}


def section_rest(P):
    P = healthy(P)
    out = []
    R = {T: meade(P, T, drink_policy=thirst_policy_factory(P)) for T in (22, 26, 31, 36)}
    d = {T: R[T]["dcore"] - R[22]["dcore"] for T in R}
    tg = {26: 0.2, 31: 0.7, 36: 0.9}
    vals = {T: float(np.mean(d[T])) for T in tg}
    ok = all(abs(vals[T] - tg[T]) <= 0.15 for T in tg)
    out.append(row("V2", "core rise 8 h seated 26/31/36 C = +0.2/+0.7/+0.9 C (Meade 2024)", "+-0.15",
                   " / ".join(f"{vals[T]:+.2f}" for T in tg) + f" (population mean, n={len(d[26])}; minus the 22 C arm)",
                   ok, "" if ok else "see note", "rest"))
    core22 = R[22]["T_core"][:, :].mean()
    c0 = float(np.mean(R[22]["c0"]))
    m22 = R[22]["M"].mean() if "M" in R[22] else float("nan")
    okV1 = (36.5 <= c0 <= 36.9) or (36.8 <= core22 <= 37.2)
    out.append(row("V1", "resting core thermoneutral 36.7 +-0.2 C (baseline); accept 36.8-37.2 at other times of day (R1 V1)", "36.5-36.9 baseline OR 36.8-37.2 daytime",
                   f"baseline 08:00 after 6 h at 22 C: {c0:.2f} C; 08:00-16:00 mean {core22:.2f} C", okV1, "", "rest"))
    sk = {T: float(R[T]["T_skin"][-60:].mean()) for T in R}
    tgs = {22: 31.7, 26: 32.9, 31: 34.9, 36: 35.9}
    ok = all(abs(sk[T] - tgs[T]) <= 0.5 for T in tgs)
    out.append(row("V3", "mean skin 22/26/31/36 C = 31.7/32.9/34.9/35.9 C", "+-0.5",
                   " / ".join(f"{sk[T]:.2f}" for T in tgs) + f" (fix: i_cl {B.I_CL_FIX}, report offset k {B.SKIN_REPORT_OFFSET_K})", ok, "", "rest"))
    hr = {T: float(R[T]["HR"][-60:].mean() - R[22]["HR"][-60:].mean()) + 60.0 for T in R}
    tgh = {22: 60, 26: 62, 31: 69, 36: 74}
    ok = all(abs(hr[T] - tgh[T]) <= 3 for T in tgh)
    out.append(row("V4", "resting HR 22/26/31/36 C = 60/62/69/74 bpm", "+-3 bpm",
                   " / ".join(f"{hr[T]:.1f}" for T in tgh) + " (60 + population-mean change vs 22 C; drawn rest HR is N(66,9), ARCH)", ok, "", "rest"))
    wl = {T: float((R[T]["water_loss_gpm"].mean(0) * 60 / P["A_D"]).mean()) for T in R}
    sw = {T: float((R[T]["m_sweat"].mean(0)).mean()) for T in R}
    tgw = {22: 20, 26: 26, 31: 31, 36: 80}
    # Meade measured whole-body sweat (mass loss); compare regulatory sweat + insensible skin loss
    ins = {T: wl[T] - sw[T] for T in R}
    skinloss = {T: float(np.mean((R[T]["E_sk"].mean(0) / 0.68))) for T in R}
    ok = all(abs(skinloss[T] - tgw[T]) <= 15 for T in tgw)
    out.append(row("V5", "whole-body sweat 22/26/31/36 C = 20/26/31/80 g/(h m2)", "+-15",
                   " / ".join(f"{skinloss[T]:.0f}" for T in tgw) + " (skin water loss E_sk/0.68 = regulatory + diffusion; regulatory alone " +
                   " / ".join(f"{sw[T]:.0f}" for T in tgw) + ")", ok, "", "rest"))
    dr = {T: float(np.mean(R[T]["drunk_mL"])) / 1000 for T in (22, 36)}
    dfc = float(np.mean(R[36]["deficit_pct"][-1]))
    ok = abs(dr[22] - 0.48) <= 0.2 and abs(dr[36] - 1.22) <= 0.2
    out.append(row("V6", "fluid intake 8 h 0.48 L (22 C) -> 1.22 L (36 C); deficit -0.5..-0.7 %", "+-0.2 L",
                   f"{dr[22]:.2f} -> {dr[36]:.2f} L; deficit at 36 C {dfc:.2f} %", ok, "", "rest"))
    # V7 bed rest 31 C, peak core +1.1 (fan 1.5 m/s +0.9)
    pk = {}
    for v in (0.1, 1.5):
        r = meade(P, 31, met=0.82, v=v, clo=0.6, drink_policy=thirst_policy_factory(P))
        pk[v] = float(np.mean(r["peak"]))
    r22 = meade(P, 22, met=0.82, clo=0.6, drink_policy=thirst_policy_factory(P))
    p22 = float(np.mean(r22["peak"]))
    ok = abs(pk[0.1] - p22 - 1.1) <= 0.2 and abs(pk[1.5] - p22 - 0.9) <= 0.2
    out.append(row("V7", "8 h bed rest 31 C: peak core +1.1 C; with 1.5 m/s fan +0.9 C (O'Connor 2026)", "+-0.2",
                   f"{pk[0.1]-p22:+.2f} / fan {pk[1.5]-p22:+.2f} (lying met 0.82, sleepwear+sheet clo 0.6 (R1 §1.7); peak rise minus the 22 C arm's peak rise {p22:+.2f}, same convention as V2)", ok, "", "rest"))
    v8 = {}
    for v in (0.1, 2.0, 4.0):
        r = meade(P, 36, v=v, drink_policy=thirst_policy_factory(P))
        v8[v] = float(np.mean(r["dcore"] - R[22]["dcore"]))
    ok = all(abs(x - 1.0) <= 0.2 for x in v8.values())
    out.append(row("V8", "8 h seated 36 C, fans 0/2/4 m/s: +1.0 C in all three (Lee 2025)", "+-0.2",
                   " / ".join(f"{v8[v]:+.2f}" for v in v8) + " (minus the 22 C arm, same convention as V2: same lab and protocol as Meade 2024)", ok, "", "rest"))
    # V9 circadian: constant routine 24 C seated, cosinor on day 2-3
    b = TwoNodeOlder(P, minute_of_day0=0)
    core = []
    for t in range(3 * 1440):
        o = b.step(_env(24.0, 45.0, person_met(P, 0.86), mod=t % 1440))
        core.append(o["T_core"])
    core = np.array(core)[1440:]
    tm = np.arange(core.shape[0]) % 1440 / 60.0
    X = np.stack([np.ones_like(tm), np.cos(2 * np.pi * tm / 24), np.sin(2 * np.pi * tm / 24)], 1)
    beta = np.linalg.lstsq(X, core, rcond=None)[0]
    amp = np.hypot(beta[1], beta[2])
    nadir = np.array([tm[:1440][np.argmin(core[:1440, j])] for j in range(core.shape[1])])
    ok = 0.30 - 0.1 <= amp.mean() <= 0.40 + 0.1 and abs(np.median(nadir) - 4.5) <= 1.0
    out.append(row("V9", "circadian amplitude 0.30-0.40 C, nadir ~04:30", "+-0.1 C, +-1 h",
                   f"cosinor amplitude {amp.mean():.2f} (sd {amp.std():.2f}); nadir median {np.median(nadir):.2f} h (constant routine 24 C)",
                   ok, "", "rest", note="partly by construction: amplitude and nadir are drawn per person (ARCH §3.3)"))
    ok = all(31.5 - 0.5 <= sk[T] <= 36.0 + 0.5 for T in sk)
    out.append(row("V10", "mean skin range indoors 22-36 C: 31.5-36.0 C", "-", f"{min(sk.values()):.1f}-{max(sk.values()):.1f}", ok, "", "rest"))
    return out


# =========================================================================== limits
def section_limits(P, Py=None):
    Pfull = P
    P = healthy(P)      # PSU HEAT / Kenny / Carrillo cohorts: healthy volunteers (R1 §8.9)
    out = []
    psu_res = {}
    for act in ("adl", "rest"):
        for T in (34, 36, 38, 40):
            psu_res[(act, "h", T)] = psu(P, "humid", T, act)
        for pa in (12, 16):
            psu_res[(act, "d", pa)] = psu(P, "dry", pa, act)
    tg = {"adl": [3.41, 3.21, 3.07, 2.54], "rest": [3.53, 3.52, 3.57, 2.88]}
    for vid, act in (("V12", "adl"), ("V13", "rest")):
        v = [float(np.nanmean(psu_res[(act, "h", T)]["Pa_crit_kPa"])) for T in (34, 36, 38, 40)]
        ok = all(abs(a - b) <= 0.3 for a, b in zip(v, tg[act]))
        out.append(row(vid, f"critical P_a older {act.upper()} 34/36/38/40 C = " + "/".join(map(str, tg[act])) + " kPa", "+-0.3 kPa",
                       " / ".join(f"{x:.2f}" for x in v), ok, "", "limits"))
    tgd = {"adl": [42.9, 40.3], "rest": [46.1, 44.1]}
    for vid, act in (("V14", "adl"), ("V15", "rest")):
        v = [float(np.nanmean(psu_res[(act, "d", pa)]["T_crit"])) for pa in (12, 16)]
        ok = all(abs(a - b) <= 2.0 for a, b in zip(v, tgd[act]))
        out.append(row(vid, f"critical T_db older {act.upper()} 12/16 mmHg = " + "/".join(map(str, tgd[act])) + " C", "+-2 C",
                       " / ".join(f"{x:.1f}" for x in v), ok, "", "limits"))
    # V16 critical wet bulb (Stull) humid protocols
    def stull(t, rh):
        return (t * np.arctan(0.151977 * np.sqrt(rh + 8.313659)) + np.arctan(t + rh) - np.arctan(rh - 1.676331)
                + 0.00391838 * rh ** 1.5 * np.arctan(0.023101 * rh) - 4.686035)
    twb = {}
    for act in ("adl", "rest"):
        twb[act] = [float(np.nanmean(stull(T, psu_res[(act, "h", T)]["RH_crit"]))) for T in (34, 36, 38, 40)]
    ok = (27.0 - 0.5 <= min(twb["adl"]) and max(twb["adl"]) <= 28.3 + 0.5 and 28.3 - 0.5 <= min(twb["rest"]) and max(twb["rest"]) <= 29.9 + 0.5)
    out.append(row("V16", "critical T_wb humid: ADL 27.0-28.3, Rest 28.3-29.9 C", "+-0.5 C (range edges)",
                   "ADL " + "/".join(f"{x:.1f}" for x in twb["adl"]) + "; Rest " + "/".join(f"{x:.1f}" for x in twb["rest"]), ok, "", "limits"))
    ra = np.concatenate([psu_res[("adl", "h", T)]["rate_above"] for T in (34, 36, 38, 40)])
    rr = np.concatenate([psu_res[("rest", "h", T)]["rate_above"] for T in (34, 36, 38, 40)])
    ok = abs(np.nanmean(ra) - 0.62) <= 0.48 and abs(np.nanmean(rr) - 0.69) <= 0.50
    out.append(row("V17", "core rise rate above the limit 0.62 +-0.48 (ADL), 0.69 +-0.50 (Rest) C/h", "within 1 SD",
                   f"ADL {np.nanmean(ra):.2f} (sd {np.nanstd(ra):.2f}); Rest {np.nanmean(rr):.2f} (sd {np.nanstd(rr):.2f}) C/h, first 30 min after inflection", ok, "", "limits"))
    # V18 (Cottle 2022 design): fixed environment just below each person's own limit (P_a,crit - 0.3 kPa at 36 C),
    # 60-min equilibration + 120 min, rate over the last 60 min.
    rates = []
    for act in ("adl", "rest"):
        pc = psu_res[(act, "h", 36)]["Pa_crit_kPa"]
        pa_fix = np.where(np.isnan(pc), 3.0, pc - 0.3) / 0.133322
        base = 1.37 if act == "adl" else 0.86
        b = TwoNodeOlder(P, minute_of_day0=9 * 60)
        mm = person_met(P, base)
        core = []
        for t in range(180):
            o = b.step(_env(36.0, rh_from_pa_torr(36.0, pa_fix), mm, v=0.2, mod=9 * 60 + t))
            core.append(o["T_core"])
        core = np.array(core)
        rates.append((core[-1] - core[-61]))
    rb = np.concatenate(rates)
    ok = 0.06 <= np.nanmedian(rb) <= 0.15
    out.append(row("V18", "core rise rate just below the limit 0.06-0.15 C/h (Cottle 2022 compensable fixed environment)", "range",
                   f"median {np.nanmedian(rb):.3f} C/h (IQR {np.nanpercentile(rb,25):.2f}-{np.nanpercentile(rb,75):.2f}); fixed 36 C at each person's P_a,crit - 0.3 kPa, "
                   f"ADL and Rest, last 60 of 180 min (09:00-12:00, circadian rise included)", ok, "", "limits"))
    r36 = psu_res[("adl", "h", 36)]
    # lead in RH points at minute resolution (P_a ramps 1 mmHg / 5 min = 0.448 RH points / min at 36 C)
    lead = (r36["inflection_min"] - r36["hr_onset_min"]) * 0.2 * 100 / p_sat_torr(36.0)
    frac = float(np.mean((lead >= 2) & (lead <= 6)))
    r12 = psu_res[("adl", "d", 12)]
    leadT = (r12["inflection_min"] - r12["hr_onset_min"]) * 0.2
    nobb = (P["med_bb_nonsel"] + P["med_bb_sel"]) == 0
    frac_nobb = float(np.mean(((lead >= 2) & (lead <= 6))[nobb]))
    ok = frac >= 0.8
    out.append(row("V19", "HR drift onset precedes core inflection by 2-6 RH points at 36 C (ADL) for >= 80 % of persons (Kenney 2025: 53 vs 57 % RH; 41 vs 43 C at 12 mmHg)",
                   ">= 80 % in [2, 6]", f"{100*frac:.0f} % in [2,6] ({100*frac_nobb:.0f} % without beta-blockers); median lead {np.nanmedian(lead):.1f} RH points (HR onset RH {np.nanmedian(r36['RH_hr']):.0f} %, core {np.nanmedian(r36['RH_crit']):.0f} %); "
                   f"12 mmHg: median lead {np.nanmedian(leadT):.1f} C (HR {np.nanmedian(r12['T_hr']):.1f}, core {np.nanmedian(r12['T_crit']):.1f})", ok, "", "limits"))
    hr_first_dry = float(np.mean(leadT > 0))
    out.append(row("V19-dry", "dry half of V19: at 12 mmHg (ADL) HR drift onset precedes the core inflection (Kenney 2025: HR 41 C vs core 43 C, lead ~2 C)",
                   "HR first (lead > 0) for >= 80 % of persons", f"{100*hr_first_dry:.0f} % HR first; median lead {np.nanmedian(leadT):+.1f} C "
                   f"(HR onset T_db {np.nanmedian(r12['T_hr']):.1f}, core inflection {np.nanmedian(r12['T_crit']):.1f})", hr_first_dry >= 0.8, "", "limits"))
    wc = np.concatenate([psu_res[("adl", "h", T)]["w_cap"] for T in (34,)])
    ok = float(np.max(wc)) < 0.85 * B.OMEGA_FRAME + 1e-9
    out.append(row("V20", "omega_max 65+: 0.47/0.40 ADL, 0.31/0.34 Rest, never 0.85", "-",
                   f"person omega_max U(0.31,0.57) x(1-0.3f), rest factor {B.OMEGA_REST_FACTOR}, then x{B.OMEGA_FRAME} frame factor -> model-frame cap ADL {np.mean(wc):.2f} (max {np.max(wc):.2f})", ok, "", "limits",
                   note="the measured omega distribution is used exactly; the frame factor converts Kenney's partitional-calorimetry E_max convention into the Gagge-Ji E_max"))
    # young twin
    if Py is None:
        Py = P
    sy = np.concatenate([psu(Py, "humid", T, "adl", young=True)["sweat_crit"] for T in (36, 40)])
    so = np.concatenate([psu_res[("adl", "h", T)]["sweat_crit"] for T in (36, 40)])
    ratio = np.nanmean(so) / np.nanmean(sy)
    ok = 0.44 <= ratio <= 0.63
    out.append(row("V21", "sweat rate at the limit older/young 0.44-0.63 (young twin)", "range",
                   f"{ratio:.2f} (older {np.nanmean(so):.0f}, young twin {np.nanmean(sy):.0f} g/(h m2), humid 36/40 C ADL)", ok, "", "limits"))
    out.append(row("V22", "cardiac output at tolerance older/young 0.67x; same absolute HR rise", "-",
                   f"not represented: the model has no stroke-volume/cardiac-output state; proxy = SkBF ceiling ratio {np.mean(P['skbf_max'])/90:.2f} (63/90)", False,
                   "No cardiac-output state in a two-node model; the HR model gives the same absolute HR rise by construction (kappa ranges are age-independent). Not needed for training targets.", "limits"))
    out.append(row("V24", "decrement appears from 40-44 y", "-", "not testable: population is 65-85 only; young twin uses the R1 §1.4 young column", False,
                   "The simulator has no middle-aged parameterisation (ARCH draws age U(65,85)); an age sweep 20-70 would need a Ji-to-Gagge interpolation that R1 does not source.", "limits"))
    # V23: 9 h at 40 C (Carrillo 2024) -- seated, RH 9 % (Carrillo protocol was 40 C / 9 % RH)
    R = constant_run(P, 40.0, 9.0, 0.86, 540, spin=(22, 45, 0.86, 120), keys=("T_core",))
    rise = R["T_core"].max(0) - R["T_core"][0]
    f = float(np.mean(rise > 1.0))
    ok = abs(f - 0.39) <= 0.10
    out.append(row("V23", "fraction of 64-79 y exceeding +1.0 C in 9 h at 40 C = 39 %", "+-10 points",
                   f"{100*f:.0f} % (seated, 40 C / 9 % RH assumed, no drinking)", ok, "", "limits"))
    # V25 / V26 / frailty
    Tc12 = psu_res[("adl", "d", 12)]["T_crit"]
    sd = float(np.nanstd(Tc12))
    ok = 3.0 <= sd <= 5.0
    out.append(row("V25", "T_crit SD across persons at 12 mmHg ~4 C (ARCH: 3-5 C)", "3-5 C",
                   f"{sd:.2f} C (ADL); Rest {np.nanstd(psu_res[('rest','d',12)]['T_crit']):.2f} C", ok, "", "limits"))
    male = P["sex_m"] > 0
    fm = float(np.nanmean(Tc12[~male]) - np.nanmean(Tc12[male]))
    ok = fm < 0
    out.append(row("V26", "women's limits below men's", "sign", f"women - men T_crit(12 mmHg, ADL) = {fm:+.2f} C", ok, "", "limits"))
    terc = np.digitize(Pfull["frailty"], [1 / 3, 2 / 3])
    Tf = psu(Pfull, "dry", 12, "adl")["T_crit"]
    d = float(np.nanmean(Tf[terc == 2]) - np.nanmean(Tf[terc == 0]))
    out.append(row("FRAIL", "frailty tercile 3 limits below tercile 1", "sign", f"T3 - T1 T_crit = {d:+.2f} C", d < 0, "", "limits",
                   note="frailty axis unvalidated by construction (R1 §8.9)"))
    # V11 Kenny 2017 3 h at 44 C / 30 % RH
    R = constant_run(P, 44.0, 30.0, 0.86, 180, spin=(22, 45, 0.86, 120), keys=("T_core", "storage"))
    end = float(np.mean(R["T_core"][-1])); stor = float(np.mean(R["storage"].sum(0) * 60 * P["A_D"] / 1000))
    Ry = constant_run(Py, 44.0, 30.0, 0.86, 180, spin=(22, 45, 0.86, 120), young=True, keys=("T_core", "storage"))
    stor_y = float(np.mean(Ry["storage"].sum(0) * 60 * Py["A_D"] / 1000))
    ok = abs(end - 37.8) <= 0.3
    out.append(row("V11", "3 h at 44 C / 30 % RH: end core 37.8 +-0.3 (young 37.6); storage 358 vs 202 kJ (1.8x)", "+-0.3 C",
                   f"end core {end:.2f} C (young twin {float(np.mean(Ry['T_core'][-1])):.2f}); storage {stor:.0f} vs young twin {stor_y:.0f} kJ ({stor/max(stor_y,1):.1f}x)", ok, "", "limits"))
    # kappa tercile summary (HR at 36 C humid ADL limit)
    kt = np.digitize(P["kappa_core"], [14 + 16 / 3, 14 + 32 / 3])
    s = "; ".join(f"kappa T{k+1}: HR-onset lead median {np.nanmedian(lead[kt==k]):.1f} RH pts, HR at inflection {np.nanmean(r36['hr'][np.clip(np.nan_to_num(r36['inflection_min']).astype(int),0,None), np.arange(len(kt))][kt==k]):.0f} bpm" for k in range(3))
    out.append(row("KAPPA", "per-kappa-tercile summary (ARCH §3.3: report all results per kappa tercile)", "-", s, True, "", "limits"))
    return out


# =========================================================================== multi-day
def section_multiday(P):
    out = []
    # V27: controlled two-day S2 run -- class-B indoor profile of S2 days 1-2 (R3 §1.6), identical fixed routine
    # both days (no errands), thirst drinking; peak core and peak HR per day (extrapolated multi-day, R1 §4)
    from .weather import hourly_weather
    from .indoor import B4Class, hourly_to_minutes
    W = hourly_weather(["S1"] * 7 + ["PRE", "PRE"] + [f"S2_{k}" for k in range(1, 6)], np.random.default_rng(11))
    im = B4Class("B")
    ri = im.run_hourly(W["t_out"], W["s_rad"], W["rh_out"])
    tin = hourly_to_minutes(ri["t_in"][:, 0]); tbed = hourly_to_minutes(ri["t_bed"][:, 0]); rhin = hourly_to_minutes(ri["rh_in"][:, 0])
    o0 = 8 * 1440          # start at the last PRE day
    Ph = healthy(P)
    bb = TwoNodeOlder(Ph, minute_of_day0=0)
    pol = thirst_policy_factory(Ph)
    peaks, hrp, dmorn = {}, {}, {}
    for t in range(3 * 1440):
        mod = t % 1440; d = t // 1440
        sleep = mod < 7 * 60 or mod >= 23 * 60
        nap = 14 * 60 + 30 <= mod < 15 * 60 + 30
        act = 0.7 if (sleep or nap) else (1.37 if (9 * 60 <= mod < 10 * 60 or 19 * 60 <= mod < 19 * 60 + 30) else 0.86)
        T = tbed[o0 + t] if (sleep or nap) else tin[o0 + t]
        o = bb.step(dict(t_db=T, rh=rhin[o0 + t], met=person_met(Ph, act), clo=0.6 if sleep else 0.4, minute_of_day=mod,
                         drink_mL=pol(bb, t) * (0 if sleep else 1)))
        peaks[d] = np.maximum(peaks.get(d, o["T_core"] * 0 - 99), o["T_core"])
        hrp[d] = np.maximum(hrp.get(d, o["HR"] * 0 - 99), o["HR"])
        if mod == 7 * 60:
            dmorn[d] = o["deficit_pct"].copy()
    dpk = float(np.mean(peaks[2] - peaks[1])); dh = float(np.mean(hrp[2] - hrp[1]))
    ok = dpk >= 0.2 and abs(dh) <= 3
    out.append(row("V27", "S2: day-2 core peak >= day-1 peak + 0.2 C with HR peak within +-3 bpm (extrapolated multi-day; Meade 2017 workers 38.1 -> 38.4, HR unchanged)",
                   ">= +0.2 C; |dHR| <= 3", f"day-2 minus day-1 peak core {dpk:+.2f} C (sd {np.std(peaks[2]-peaks[1]):.2f}); peak HR {dh:+.1f} bpm; "
                   f"day-1 peak {np.mean(peaks[1]):.2f} C; controlled run, class-B indoor, identical routine, n={len(Ph['seed'])}",
                   ok, "", "multiday", note="extrapolated multi-day"))
    ok = np.mean(dmorn[1]) > 0 and np.mean(dmorn[2]) > 0
    out.append(row("V28", "hydration carry-over: dehydrated before and after on both days (USG 1.025 -> 1.029)", "deficit > 0 both mornings",
                   f"07:00 deficit day 1 {np.mean(dmorn[1]):.2f} %, day 2 {np.mean(dmorn[2]):.2f} %", ok, "", "multiday",
                   note="extrapolated multi-day; USG not modelled, deficit used"))
    # V29 AC respite: 8 h at 36 C; 2 h at 23 C from h 3-5; benefit gone within ~2 h
    b = TwoNodeOlder(P, minute_of_day0=8 * 60 - 360)
    mod = 8 * 60 - 360
    for _ in range(360):
        b.step(_env(22, 45, person_met(P, 0.86), mod=mod)); mod += 1
    bc = TwoNodeOlder(P, minute_of_day0=8 * 60 - 360)
    mod2 = 8 * 60 - 360
    for _ in range(360):
        bc.step(_env(22, 45, person_met(P, 0.86), mod=mod2)); mod2 += 1
    ca, cc = [], []
    pol_a, pol_c = thirst_policy_factory(P), thirst_policy_factory(P)
    for t in range(10 * 60):
        T = 23.0 if 180 <= t < 300 else 36.0
        ca.append(b.step(_env(T, 45 if T > 30 else 50, person_met(P, 0.86), mod=mod, drink=pol_a(b, t)))["T_core"]); mod += 1
        cc.append(bc.step(_env(36.0, 45, person_met(P, 0.86), mod=mod2, drink=pol_c(bc, t)))["T_core"]); mod2 += 1
    ca, cc = np.array(ca).mean(1), np.array(cc).mean(1)
    benefit = cc[299] - ca[299]
    gap = cc - ca
    gone = np.argmax((np.arange(len(gap)) > 300) & (gap < 0.2 * benefit)) - 300
    ok = 60 <= gone <= 180
    out.append(row("V29", "AC respite: 2 h at 23 C cuts core by 0.8 C; benefit gone within ~2 h", "gone in 1-3 h",
                   f"benefit at end of respite {benefit:.2f} C; back within 20 % of control after {gone} min", ok, "", "multiday"))
    # V30 acclimatisation: storage over 3 h at 44 C with a=0 vs a=1
    Pa = dict(P); Pa["acclim"] = np.ones_like(P["acclim"])
    st = {}
    for days in (0, 10):
        bb = TwoNodeOlder(Pa, minute_of_day0=9 * 60 - 120)
        bb.hot_days[:] = days
        m = 9 * 60 - 120
        for _ in range(120):
            bb.step(_env(22, 45, person_met(P, 0.86), mod=m)); m += 1
        s = 0
        for _ in range(180):
            o = bb.step(_env(44, 30, person_met(P, 0.86), mod=m)); m += 1
            s = s + o["storage"]
        st[days] = float(np.mean(s * 60 * P["A_D"] / 1000))
    dS = st[10] - st[0]
    ok = abs(dS + 213) <= 82
    out.append(row("V30", "acclimatisation: heat storage over 3 h at 44 C falls by 213 kJ (CI 131-295)", "within CI",
                   f"{dS:+.0f} kJ ({st[0]:.0f} -> {st[10]:.0f}) with the switch on at 10 hot days", ok, "", "multiday"))
    return out


SECTIONS = {"rest": section_rest, "limits": section_limits, "multiday": section_multiday}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", default="rest")
    ap.add_argument("--n", type=int, default=500)
    a = ap.parse_args(argv)
    P = load_persons(idx=slice(0, a.n))
    secs = list(SECTIONS) if a.section == "all" else [a.section]
    rows = json.load(open(ROWS_PATH)) if os.path.exists(ROWS_PATH) else {}
    for s in secs:
        if s in ("indoor", "sensor", "agree", "routine"):
            from . import validate_extra as VX
            rs = getattr(VX, "section_" + s)(P)
        else:
            rs = SECTIONS[s](P)
        rows[s] = rs
        for r in rs:
            print(f"{r['id']:7s} {r['result']}  {r['value']}")
    json.dump(rows, open(ROWS_PATH, "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
