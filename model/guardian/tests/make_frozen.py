#!/usr/bin/env python3
"""Writes guardian/FROZEN.txt: the hg2-freeze-7 record (freeze-6 + B5-v7: HR-free skin-floor Danger, skin DRINK, Marble skin arming,
NN-DRINK heat/skin context, twin file v4, Greek screen fix; freeze-6 = freeze-5 + B2b-v5 Core Sense v5 + AR anchor/residual). Weights identity (SHA-256 of the exported files + CRC-32 + version),
the build defaults, every numeric threshold of hg_guardian_cfg.h with its exact float32 value as compiled and its SOURCE/DESIGN
comment, the uncertainty constants taken from the export, and the measured rows this freeze was accepted on."""
import hashlib, json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); G = os.path.join(HERE, ".."); C = os.path.join(G, "c"); E = "/home/claude/hg_ai/model/export"
sys.path.insert(0, os.path.join(G, "py"))
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
consts = json.load(open(os.path.join(G, "py", "hg_consts.json")))
import numpy as np
val = {k: float(np.frombuffer(bytes.fromhex(v), ">f4")[0]) for k, v in consts.items()}
hdr = open(os.path.join(E, "hg2_weights.h")).read()
crc = re.search(r"HG2_NN_CRC32 (0x[0-9A-Fa-f]+)", hdr).group(1); ver = re.search(r'HG2_NN_VERSION "([^"]+)"', hdr).group(1)
git = subprocess.run(["git", "-C", G, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
L = ["HEAT GUARDIAN - guardian/c FREEZE RECORD (tag hg2-freeze-7 - PREPARED BY B5-v7, NOT TAGGED; = hg2-freeze-6 + B5-v7: HR-free skin-floor Danger, skin DRINK, Marble skin arming, NN-DRINK heat/skin context, twin v4, screen-text fix; supersedes hg2-freeze-6)", "=" * 72, "",
     "Freeze rule (M7.4/M9): thresholds that cannot be validated on real data are frozen here and labelled SET IN SIMULATION.",
     "The sealed exam is run ONCE by the manager on this frozen build; nothing below may change after the tag.", "",
     "WEIGHTS (model/export, B2)", "  version              %s" % ver, "  HG2_NN_CRC32         %s" % crc,
     "  sha256 hg2_weights.c %s" % sha(os.path.join(E, "hg2_weights.c")), "  sha256 hg2_weights.h %s" % sha(os.path.join(E, "hg2_weights.h")),
     "  sha256 hg2_weights.json %s  (the sealed exam's --weights-sha)" % sha(os.path.join(E, "hg2_weights.json")),
     "  sha256 hg2_guard.h   %s  (guardian/c copy of model/export/host/hg2_guard.h, B2 fix 0978398)" % sha(os.path.join(C, "hg2_guard.h")),
     "  training data        %s" % re.search(r'HG2_TRAIN_DATA_SHA256 "([^"]+)"', hdr).group(1),
     "  network              32-24-16-9 x5 (6 task outputs + 3 sd heads), sd = sqrtf(mean_k(v^2 + EPS_V) + between-member var) * Y_STD",
     "  NN logit cuts        HG2_LOGIT_CUT_38 = HG2_LOGIT_CUT_385 = 1e9 (NN Drink/Danger logit paths OFF, M5.3)",
     "  conformal 90 %% half-widths: f20 no-reading %s / reading %s; now %s / %s (degC)" % tuple(
         re.search(r"%s \(([0-9.]+)f\)" % n, hdr).group(1) for n in ("HG2_RANGE90_F20_NOREAD", "HG2_RANGE90_F20_READ", "HG2_RANGE90_NOW_NOREAD", "HG2_RANGE90_NOW_READ")),
     "  REAL range widths    HG2_CONF_HALF_NOW_REAL %s, HG2_CONF_HALF_F20_REAL %s (degC; B2b-v5: 90 %% of the AR core's |error|, HTT + Brighton 65-76 y)" % tuple(
         re.search(r"%s \(([0-9.]+)f\)" % n, hdr).group(1) for n in ("HG2_CONF_HALF_NOW_REAL", "HG2_CONF_HALF_F20_REAL")),
     "  displayed range      half-width = max(1.645 * max(sd_now, %.2f), HG2_CONF_HALF_NOW_REAL = %.4f) C  [B2-fix]; DISPLAY ONLY - the tiers keep" % (val["HG_SD_FLOOR"], val["HG_RANGE_HALF_REAL_EFF"]),
     "                       the M11.4 constant lowering. B2b-v5 widths = max(pooled HTT + Brighton, Brighton-only) split-conformal 90 %;",
     "                       Brighton = CALIBRATION (spent exam), so these widths have NO held-out coverage claim (model/runs/v5aug/results_b2b.json)",
     "  input guards         [B2-fix] hg2_guard.h once at hg_guardian_step entry and again in hg2_step: T1/T2/T_air -40..85 C, RH 0..100 %,",
     "                       PI 0..100 %, a_std 0..16 g, HR finite (+ its 30..220 gate, also on the STATUS HR) -> else NAN; z guard; outputs",
     "                       core 30..45 C, sd 0..3 C, logits -100..100, strain 0..10",
     "", "BUILD DEFAULTS (hg_guardian_cfg.h)",
     "  HG_DRINK_DESIGN = %d (design A, personal-relative DRINK; M9.1)" % int(val["HG_DRINK_DESIGN"]),
     "  HG_A_DELTA      = %.9g C  SET IN SIMULATION (SIM-DEV v3/v4)" % val["HG_A_DELTA"],
     "  HG_M7_ROUTINE   = %d (M7.3 (i): DRINK does not freeze routine learning; (ii) removed, M9.3)" % int(val["HG_M7_ROUTINE"]),
     "  HG_TWIN_READING_MODE = 0 (M4.3: thermometer readings are display-only)",
     "  M5.2 uncalibrated lowering = %.9g C (B2 HG2_WATCH_LOWER_UNCAL; inside the %.2f C M1.3 cap)" % (val["HG_UNC_LOWER_CONST"], val["HG_M_TOTAL_CAP"]),
     "  M11.2 DRINK = (valid and v1.2 f20 >= 37.85 - lowering) OR (20-min thermal blank passed and calm baseline learned and",
     "                guarded NN f20 - calm >= Delta - lowering).  M11.3 OOD guard: hr_reserve > %.2f or HR > %.0f -> max(NN, v1.2)."
     % (val["HG_OOD_RESERVE"], val["HG_OOD_HR"]),
     "  Interpretation recorded at freeze: the v1.2 ceiling is HR-only, so it is gated at the 5-min `valid` point and not by the",
     "  20-min thermal donning blank (A7.2 'no thermal alarms'); HTT dev: the 20-min gate cut DRINK lead 23 -> 6 min.",
     "  M12 (manager decision): this 5-min valid gate for the HR-only v1.2 path is CONFIRMED.",
     "  M12 heat-context gate: the v1.2 ceiling term counts only when (corrected room air >= HG_V12_CTX_C = %.1f C) OR (air above the" % val["HG_V12_CTX_C"],
     "                PSU older-adult line, ADL/rest by activity, for every wearer) OR (M11.3 OOD guard active). COOL/DANGER never gated.",
     "  HG_V12_CTX_C    = %.1f C  SET IN SIMULATION (v4 SIM-DEV 150 + HTT dev sweep 28/29/30; manager CONFIRMED 30 C)" % val["HG_V12_CTX_C"],
     "  M13 Danger by persistence: DANGER (-> CHECK -> family after %d min without a press) also when the COOL tier has been on" % int(val["HG_FAMILY_DANGER_MIN"]),
     "                >= HG_PD_COOL_MIN = %d min AND f20 now - f20 %d min ago >= 0 AND (air above the wearer's PSU line OR NN logit_p385" % (int(val["HG_PD_COOL_MIN"]), int(val["HG_PD_SLOPE_MIN"])),
     "                >= %.1f OR v1.2 Danger z >= %.4f = logit(0.10)). Post-sealed-exam design change (set 1 spent): validated only on SEALED-SIM-2." % (val["HG_PD_NN_LOGIT"], val["HG_PD_V12_Z"]),
     "  HG_PD_COOL_MIN  = %d min  SET IN SIMULATION (SIM-DEV v4 150 sweep 20/30/45 at hg2-freeze-3; manager to confirm)" % int(val["HG_PD_COOL_MIN"]),
     "  T5 fixes (freeze-4): D1 every TU includes hg_fp.h first (no fast-math sub-option, no FP contraction; NaN/inf tests on IEEE bits;",
     "                table indices clamped before the cast) -> -O2 and -Ofast -ffast-math give byte-identical replays (tests/fastmath_check.py);",
     "                twin/c/hg_twin.c the same. D2 M13 = (a) PROTECTED trigger: PSU line or v1.2 z, slope of the v1.2 f20 >= -%.2f C/10 min" % val["HG_PD_SLOPE_EPS_V12"],
     "                OR (b) NN-added trigger: NN P385 high, slope of the tiers' f20 >= 0 (NN only adds; NEW value HG_PD_SLOPE_EPS_V12). D3 M3.1",
     "                property perturbs aux.core20_noff + checks family calls. D4 a running CHECK keeps counting with the band off (family as if no",
     "                press, screen Forieste to vraxioli). D5 no-wake CHECK only after >= %d %% of the sleep window was worn (NEW HG_RT_NOWAKE_WORN_PCT)." % int(val["HG_RT_NOWAKE_WORN_PCT"]),
     "                m1 midnight = a clock step back of >= %d min only (NEW HG_MIDNIGHT_MIN_STEP)." % int(val["HG_MIDNIGHT_MIN_STEP"]),
     "  M19 (freeze-5): HG_PD = %d -> the M13 persistence rule above is OFF (its values stay listed, inactive)." % int(val["HG_PD"]),
     "  M19.1 MARBLE DANGER: Danger = v1.2 logistic OR behaviour OR Marble. E10/E60 = EWMA of the tiers' f20 (36.9 when not worn), A30/A120 =",
     "                EWMA of min(a_std, 0.30 g), D = leaky (1 - 1/90) sum of max(0, f20 - 37.9); s = w0 + wL (E60 - 37.5) + wJ (E10 - E60) + wB A30",
     "                + wS A120 + wD D >= CUT %.4f for %d armed minutes; armed = thermal_ok, >= %d min since boot, corrected air >= %.0f C within %d min." % (val["HG_MB_CUT"], int(val["HG_MB_RUN_MIN"]), int(val["HG_MB_ARM_MIN"]), val["HG_MB_WARM_C"], int(val["HG_MB_WARM_WIN"])),
     "                Weights/CUT SET IN SIMULATION = R6's all-DEV fits (110 DEV persons), mean of raw and HR-scaled; NOT refitted on 400 persons.",
     "  M19.2 EXCEPTION DRINK (HG_DRINK_DESIGN = %d): f20 - calm - c W30 >= %.2f - lowering; c = her movement slope learned in rooms < 30 C;" % (int(val["HG_DRINK_DESIGN"]), val["HG_X_DELTA"]),
     "                settled: an NN-only DRINK start within %d min of the last one is held unless f20 rose %.2f C. B5 deviation from R6: protected" % (int(val["HG_X_SETTLE_MIN"]), val["HG_X_RISE_C"]),
     "                (v1.2 / PSU env) starts are never held (M3.1); R6's all-starts version fails the 3-day M3.1 property (304 violations).",
     "  M19 job 2 IMPACT CHECK (REAL HeatIN DEV only): HG_IMPACT_G 2.0 -> %.1f g, then %d consecutive still worn minutes with no press -> CHECK input" % (val["HG_IMPACT_G"], int(val["HG_IMPACT_STILL_MIN"])),
     "                (a press, movement or loss of contact cancels). Why: at 2 g a wrist trips on ordinary arm swings (2.8 % of off-charger minutes).",
     "  M19b (manager review of ea8f8a1): (1) Marble jump term RISING only: s += wJ max(0, E10 - E60) (HG_MB_JUMP_RISE = %d) - a falling" % int(val["HG_MB_JUMP_RISE"]),
     "                forecast never raises s; weights not refitted. (2) COOL stepping stone (HG_COOL_TRANSIT = %d): when the ladder steps 1 -> 2 while" % int(val["HG_COOL_TRANSIT"]),
     "                the Danger tier is already on, that minute shows the DANGER screen with no vibration (no COOL nudge); a COOL that holds is",
     "                unchanged. COOL rates below count COOL nudges actually emitted (COOL screen entered from OK/DRINK). m19a = ea8f8a1 behaviour.",
     "  M19 job 3 MARBLE MOVEMENT TERM: NOT bounded (1 wind-driven Marble fire in 1072 real DEV wearer-days; see the HeatIN rows and the cfg comment).",
     "  NaN / fast-math: Marble and Exception state reject NaN f20 (fed 36.9 / not learned); NEW host test: NaN/inf/1e30 on every field for 3 days",
     "                leaves every Marble / Exception state finite; passes at -O2 and at -Ofast -ffast-math; fastmath_check 1141 inputs byte-identical.",
     "  B2b-v5 (freeze-6): WEIGHTS retrained on Virtual Elders v5 (B1-v5 @ f055fcb: v4 + per-person skin-core coupling fitted on Brighton,",
     "                DEV ids only) with the same pipeline/HTT fine-tune; skin gain 0.53 -> 0.17 C/C on SIM hot rows (model/runs/b2b_v5aug/eval_v5.json).",
     "  B2b AR (HG_B2B = %d): core_now/20/30 and core20_noff = v1.2 + w * clamp(NN - v1.2, -%.2f, +%.2f); w = (T1 and air valid, worn = 2," % (int(val["HG_B2B"]), val["HG_AR_R_DOWN"], val["HG_AR_R_UP"]),
     "                >= 20 min donned) x envelope ramp (T1 - corrected air inside the SIM-v5-training p0.5..p99.5 band at that air, ramp to 0",
     "                over %.2f C outside; HG_AR_ENV_* tables) x (not the M11.3 OOD HR rule). R_DOWN fixed a priori (manager); R_UP 0.50 chosen" % val["HG_AR_RAMP"],
     "                on SIM-DEV v5 over 0.30 (S2 core-38 display 84.9 vs 83.9 % raw, equal false alarms); envelope SET IN SIMULATION. The M11.3",
     "                max(NN, v1.2) stays and is a no-op (w = 0 there). Reference: model/b2b/residual.py; C == Python: golden, parity_m7, parity_sim_long.",
     "  B5-v7 (freeze-7, weights UNCHANGED 0xEE4F7E9E): four HR-free / nag changes, every value SET IN SIMULATION on SIM-DEV v5 (tune = the",
     "                FROZEN-comparable 150 DEV persons; check = the other 250 DEV persons, never used to choose a value):",
     "                (1) SKIN-FLOOR DANGER (HG_SF = %d): sf_t1 = EWMA(1/30) of the insulated wrist T1 (%.1f C fed while off/NaN), sf_ta = EWMA(1/60)" % (int(val["HG_SF"]), val["HG_SF_T1_OFF"]),
     "                of corrected air (%.1f C fed while NaN); Danger also after %d minutes of worn == 2, thermal_ok, sf_ta >= %.1f C and sf_t1 >= %.2f C" % (val["HG_SF_TA_OFF"], int(val["HG_SF_RUN_MIN"]), val["HG_SF_TA_C"], val["HG_SF_T1_C"]),
     "                (%.2f C lower for an HR-blunted wearer = PROFILE med bit 0 beta-blocker or NEW bit 4 = %d 'other HR-limiting drug / pacemaker')." % (val["HG_SF_HRB_DT"], int(val["HG_MEDF_HRB"])),
     "                -> CHECK cause DANGER -> family after %d min without a press. It needs no heart-rate rise. Measured effect of the HR-blunted" % int(val["HG_FAMILY_DANGER_MIN"]),
     "                switch on SIM-DEV v5 check set: 0 events and 0 alarms changed (DESIGN, kept for the real beta-blocker wearer; trace b5v7_skin_floor_bb_earlier).",
     "                (2) SKIN DRINK (protected, HR-free, on the env1 path; never held by the settled rule): sf_ta >= %.1f C and sf_t1 >= %.2f C." % (val["HG_SF_TA_C"], val["HG_SF_DRINK_C"]),
     "                (3) MARBLE SKIN ARMING: Marble armed only while sf_t1 >= %.2f C (R6 s3.4 known risk: wind-driven false Danger with a cool wrist)." % val["HG_MB_SKIN_C"],
     "                (4) NN Exception DRINK context: the NN-only DRINK term counts only if corrected air reached %.1f C in the last %d min AND" % (val["HG_X_CTX_C"], int(val["HG_X_CTX_WIN"])),
     "                sf_t1 >= %.2f C (protected v1.2-ceiling / PSU / skin starts untouched, M3.1)." % val["HG_X_SKIN_C"],
     "                PROFILE CMD field 5 = med flags 0..31 (integers; guardian margins + skin-floor switch now; hg2 copy via the firmware's hg_fw_apply_profile).",
     "                Twin file v4 (twin/c/hg_twin.[ch], twin/hg_twin.py): + 8 B Exception sums (sxx, sxy) at offset 198 -> 864 B with the 650-B",
     "                routine (<= 900); v3/v2 files still load (Exception empty); corrupt / out-of-bounds blocks reject the file; C == Python bytes.",
     "                Screen texts 7 and 9: «βραχιολάι» -> «βραχιόλι» (guardian/tests/glyph_check.c: every glyph in u8g2_font_10x20_t_greek).",
     "                fw/09: the log's impact flag uses HG_IMPACT_G (3 g) like the impact CHECK (was its own 2 g).",
     "", "SOURCE HASHES (sha256 at generation; guardian/c, host_test.c excluded; python mirror + consts; twin/c + twin/hg_twin.py)"] + [
     "  %s  %s" % (hashlib.sha256(open(os.path.join(G, f), "rb").read()).hexdigest(), f) for f in
     sorted(["c/" + x for x in os.listdir(C) if x.endswith((".c", ".h")) and x != "host_test.c"]) + ["py/hg_guardian_py.py", "py/hg_consts.json", "py/hg_tables.json",
                                                                                                   "../twin/c/hg_twin.c", "../twin/c/hg_twin.h", "../twin/hg_twin.py"]] + [
     "", "THRESHOLDS (exact float32 as compiled; source = the comment block above each define in hg_guardian_cfg.h)"]
src = open(os.path.join(C, "hg_guardian_cfg.h")).read().split("\n")
comment = ""
for line in src:
    s = line.strip()
    if s.startswith("/*") or s.startswith("*"): comment = (comment + " " + s.strip("/* ")).strip() if not s.startswith("/*") else s.strip("/* ")
    m = re.match(r"#define\s+(HG_\w+)\s", s)
    if m and m.group(1) in val:
        tag = "SET IN SIMULATION" if "SET IN SIMULATION" in s else "DESIGN" if "DESIGN" in s.split("/*", 1)[-1] and "/*" in s else "SOURCE" if "SOURCE" in comment else ("DESIGN" if "DESIGN" in comment else ("M-decision" if re.search(r"\bM\d", comment) else "see cfg"))
        L.append("  %-24s = %-14.9g [%s] %s" % (m.group(1), val[m.group(1)], tag, comment[:150]))
    if s and not (s.startswith("/*") or s.startswith("*") or s.startswith("#define") or s.startswith("#if") or s.startswith("#endif")): comment = ""
L += ["", "ACCEPTANCE ROWS (measured on this build)"]
for fn, label in (("eval_htt_b5v7_f7.json", "HTT dev (REAL, young adults 18-33, HR only, chamber walk; = freeze-6, no T1 in HTT)"),
):
    p = os.path.join(HERE, "out", fn)
    if os.path.exists(p):
        d = json.load(open(p))
        for k, v in d.items():
            L.append("  %s %-6s: sensitivity %.1f %% (%d/%d), false alarms %.3f /h, median lead %.0f min" % (label, k, v["sensitivity"], v["detected"], v["events"], v["false_alarms_per_h"], v["median_lead_min"]))
def _row(r):
    return ("S2 core-38.5 Danger %5.1f %% (%d/%d) | S2 display %5.1f %% | S4 FA/h DRINK %.3f COOL %.3f DANGER %.3f | S1 DRINK/day median %.2f mean %.2f, %3.0f min"
            " | false Danger/wearer-month %.2f (S1 mean %.2f) | family/month S1 %.2f" % (r["S2_danger_sens"], r["S2_danger_k"], r["S2_danger_n"], r["S2_display"],
            r["S4_drink_fa"], r["S4_cool_fa"], r["S4_danger_fa"], r["S1_drink_day"], r["S1_drink_day_mean"], r["S1_drink_min"], r["false_danger_month_all"],
            r["danger_month_s1_mean"], r["family_month_s1_mean"]))
for fn, keys, label in (("eval_b5v7_final_tune.json", ["f6", "f7"], "tune 150 (FROZEN-comparable; values chosen here), f6 = freeze-6, f7 = THIS BUILD"),
                        ("eval_b5v7_final_check.json", ["f6", "f7"], "check 250 (never used to choose), f6 = freeze-6, f7 = THIS BUILD")):
    p = os.path.join(HERE, "out", fn)
    if os.path.exists(p):
        d = json.load(open(p)); L.append("  SIM-DEV v5 B5-v7 - %s - %s, sealed-exam protocol via C replay (eval_b5v7.py)" % (label, d["label"].split(" - ")[0]))
        for k in keys:
            for hk in ("hr_raw", "hr_scaled"):
                L.append("    %-4s %-9s %s" % (k, hk, _row(d["table"]["%s|%s" % (k, hk)])))
L += ["    notes: 'family/month S1' counts EVERY unanswered CHECK of any cause (routine CHECKs included: the simulator never presses the",
      "    button), so it is not a Danger rate. ev385 family-in-window fell f6 -> f7 on check (30 -> 23 raw, 23 -> 19 HR-scaled of 37) because",
      "    freeze-7 alerts the family EARLIER and the Danger stays on: counting 'already alerted, Danger still standing' gives 30 -> 31 raw,",
      "    23 -> 27 HR-scaled (guardian/tests/b5v7_family_window.py, out/b5v7_family_window_check.txt). HR-blunted switch: 0 changes on DEV",
      "    (no DEV person carries the new bit 16; a build with HG_SF_HRB_DT = 0 matched f7 exactly, out/eval_b5v7_hrb_check.json). Goal-1 ratio false Danger/wearer-month",
      "    f7/f6 = %.3f (tune, HR-scaled) / %.3f (check, HR-scaled) vs the <= 1.2 budget." % tuple(
          json.load(open(os.path.join(HERE, "out", fn)))["table"]["f7|hr_scaled"]["false_danger_month_all"] /
          json.load(open(os.path.join(HERE, "out", fn)))["table"]["f6|hr_scaled"]["false_danger_month_all"]
          for fn in ("eval_b5v7_final_tune.json", "eval_b5v7_final_check.json"))]
L.append("  ROWS BELOW UNTIL 'SIM-DEV v5' ARE THE hg2-freeze-5 BUILD ON SIM-DEV v4 (not re-run for freeze-6; R6's cache is v4-only):")
for fn, label in (("eval_r6_style_m19b_vs_f4.json", "R6-comparable (R6's 110 DEV persons, R6's own scoring code; f4 = freeze-4, m19a = ea8f8a1, m19b = this build)"),
                  ("eval_r6_style_m19_variants.json", "R6-faithful variants (explanation only, not built)")):
    p = os.path.join(HERE, "out", fn)
    if os.path.exists(p):
        d = json.load(open(p)); L.append("  %s - %s" % (label, d["label"]))
        for key, r in d["table"].items():
            dz, dl, dk = r["danger"], r["drink"], r["danger_low_kappa"]
            L.append("    %-15s Danger heat-wave %d/%d = %.0f %% [%s], all %.0f %%, lead %s min, strict FA %.1f/mo, empty %.1f/mo, low-kappa %.0f %% | DRINK %.2f/day %.0f min, S2 %.0f %%"
                     % (key, dz["hit_S2"], dz["n_S2"], 100 * dz["sens_S2"], "-".join("%.0f" % (100 * x) for x in dz["ci_sens_S2"]), 100 * dz["sens"], dz["lead"],
                        dz["fa_month"], dz["empty_month"], 100 * dk["sens"], dl["drink_per_day_median"], dl["drink_min_median"], 100 * dl["s2_sens"]))
L.append("  R6 reference (R6_invention.md s5.2/s7.2, new Danger tier): raw 51/63 at 12.6 FA/mo, HR-scaled 50/63 at 8.6; DRINK 3.0/day 78 min 89 % raw, 2.0/66/87 % scaled.")
p = os.path.join(HERE, "out", "eval_sim_m7_m19b_v4_150.json")
if os.path.exists(p):
    d = json.load(open(p)); L.append("  %s, %d persons, weights %s (freeze4 = this build with -DHG_MARBLE=0 -DHG_PD=1 -DHG_DRINK_DESIGN=1; m19a = -DHG_MB_JUMP_RISE=0 -DHG_COOL_TRANSIT=0)" % (d["label"], d["persons"], d["weights"]["crc"]))
    for key, r in d["table"].items():
        if key.endswith("|all"):
            e = r["ev385_all"]; e2 = r["ev385_S2"]
            L.append("    %-17s ev385 %d: Danger %.1f %%, family %.1f %%, lead %s min | S2 %d: %.1f %% | S1 Danger/month mean %.2f median %.2f | S2 Danger/wk %.2f"
                     % (key[:-4], e["events"], e["danger_sens"], e["family_sens"], e["lead_median"], e2["events"], e2["danger_sens"] or 0,
                        r["danger_per_month_s1_mean"], r["danger_per_month_s1_median"], r["danger_per_week_s2_mean"]))
            L.append("    %-17s S1 median: DRINK %.1f/day, %.0f min/day, COOL %.1f/wk, CHECK %.1f/wk | S2 CHECK %.1f/wk | S2 sens %.1f %% | S9 %.1f %%"
                     % ("", r["drink_per_day"], r["drink_min_per_day"], r["cool_per_week"], r["check_per_week"], r["check_per_week_s2"], r["s2_sens_display"] or 0, r["s9_sens"] or 0))
L.append("    note: COOL/wk = COOL nudges emitted. ea8f8a1 (m19a) showed 3.1/wk median raw because Marble DANGER climbed through a 1-minute COOL;")
L.append("          M19b removes those stepping-stone nudges -> 0.0/wk (freeze-4 0.35). Low-kappa third (ev385, t0 rows): default raw/HR-scaled 7/10,")
L.append("          m19a 7/10, freeze-4 1/10 and 0/10 - the rising-only jump term costs no event on SIM-DEV (R6-style 110: low-kappa 22/37 raw both).")
p = os.path.join(HERE, "out", "eval_sim_m7_b2bv5_v5_150.json")   # B2b-v5: this build (ar) vs freeze-5 binary on SIM-DEV v5
if os.path.exists(p):
    d = json.load(open(p)); L.append("  SIM-DEV v5 - %s, %d persons (freeze5 = the hg2-freeze-5 binary; nn5 = v5 NN without AR; ar = THIS BUILD; arsym = R_UP 0.30; v12 = R 0)" % (d["label"], d["persons"]))
    for key, r in d["table"].items():
        if key.endswith("|all"):
            e = r["ev385_all"]; lk = d["table"][key[:-4] + "|t0"]
            L.append("    %-17s S1 median DRINK %.2f/day %.0f min | S2 core-38 display %.1f %% | ev385 Danger %.1f %% family %.1f %% | Danger/month mean %.2f | low-kappa S2 %.1f %% ev385 %s"
                     % (key[:-4], r["drink_per_day"], r["drink_min_per_day"], r["s2_sens_display"] or 0, e["danger_sens"], e["family_sens"], r["danger_per_month_s1_mean"],
                        lk["s2_sens_display"] or 0, lk["ev385_all"]["danger_sens"]))
for fn, lab in (("heatin_dev_b5v7_f6.json", "hg2-freeze-6 (tag)"), ("heatin_dev_b5v7_f7.json", "THIS BUILD (working tree)")):
    p = os.path.join(HERE, "out", fn)
    if os.path.exists(p):
        d = json.load(open(p)); R = d["results"]
        for v, key in (("A", "A_primary_room_air_missing"), ("B", "B_secondary_proxy_building_air_no_verdict")):
            ag = R[key]["aggregate"]; g = lambda k: "%.2f (mean %.2f)" % (ag[k]["median"], ag[k]["mean"]) if isinstance(ag.get(k), dict) else str(ag.get(k))
            L.append("  REAL HeatIN DEV watches (B5-v7 re-run, %s) variant %s: %d watches, %d wearer-days, verdicts %s" % (lab, v, ag["watches_scored"], ag["wearer_days"], R[key]["verdicts"]))
            L.append("      median watch: DRINK/day %s, DRINK min/day %s, COOL/wk %s, DANGER/month %s, CHECK/wk %s, family/month %s"
                     % (g("drink_per_day"), g("drink_min_per_day"), g("cool_per_week"), g("danger_per_month"), g("check_per_week"), g("family_per_month")))
L.append("  HeatIN rows below: hg2-freeze-5 build (historical).")
p = os.path.join(HERE, "out", "heatin_dev_m19b.json")
if os.path.exists(p):
    d = json.load(open(p)); b = d["baseline_freeze3"]
    L.append("  REAL older adults at home, HeatIN Montreal DEV watches (%s)" % d["label"])
    for v, nm in (("A", "variant A (room air missing; the pre-registered verdict variant)"), ("B", "variant B (proxy building air; no verdict)")):
        m = d[v]["metrics"]; f = lambda k: "%.2f (mean %.2f)" % (m[k]["median"], m[k]["mean"])
        L.append("    %s: %d watches, %d wearer-days, verdicts %s" % (nm, d[v]["watches_scored"], d[v]["wearer_days"], d[v]["verdicts"]))
        L.append("      median watch: DRINK/day %s, DRINK min/day %s, COOL/wk %s, DANGER/month %s" % (f("drink_per_day"), f("drink_min_per_day"), f("cool_per_week"), f("danger_per_month")))
        L.append("      CHECK/wk %s [impact %s, no-wake %s, quiet %s], family/month %s" % (f("check_per_week"), f("impact_per_week"), f("nowake_per_week"), f("quiet_run_per_week"), f("family_per_month")))
    L.append("    before (hg2-freeze-3, same script, variant A): CHECK/wk median %.2f (mean %.2f), impact CHECK/wk median %.2f" % (b["check_per_week_median"], b["check_per_week_mean"], b["impact_per_week_median"]))
    mb = d["marble_variant_B"]; e = d["ea8f8a1"]
    L.append("    ea8f8a1 (before M19b): CHECK/wk A %.2f, B %.2f; COOL/wk A %.2f, B %.2f; DANGER/month mean A %.3f, B %.3f; Marble Danger episodes (B) %d"
             % (e["A"]["check_per_week"]["median"], e["B"]["check_per_week"]["median"], e["A"]["cool_per_week"]["median"], e["B"]["cool_per_week"]["median"],
                e["A"]["danger_per_month"]["mean"], e["B"]["danger_per_month"]["mean"], mb["ea8f8a1"]["danger_onsets_marble"]))
    L.append("    M19b: Marble Danger episodes (B) %d; COOL nudges emitted (B) %d, stepping stones silenced %d (pre-registered COOL/wk counts level >= 2)"
             % (mb["danger_onsets_marble"], mb["cool_nudges_emitted"], mb["cool_stepping_stones_silenced"]))
    L.append("    Marble on variant B: %d runs in %d wearer-days; score terms (level/jump/wind/mass) %s" % (mb["marble_runs"], d["B"]["wearer_days"],
             "; ".join("%.1f/%.1f/%.1f/%.1f @%.1f C" % (x["level"], x["jump"], x["wind"], x["mass"], x["tair"]) for x in mb["fires"])))
    L.append("    All alarms here are UNCONFIRMED (no core reference); t1 = watch-case temperature, not skin; HeatIN ages >= 50 by protocol, not 65+.")
p = os.path.join(G, "fw_check", "arduino_compile_freeze7_candidate.txt")
if os.path.exists(p):
    L.append("  FIRMWARE SIZE (guardian/fw_check/arduino_compile_freeze7_candidate.txt; scratch copy of fw/09_guardian, frozen/ = this tree)")
    L += ["    " + x.strip() for x in open(p).read().split("\n") if x.strip().startswith(("frozen = ", "freeze-7 candidate", "-> +"))]
L += ["  Routine CHECK thresholds: NOT validated (M9.4) - set on the real wear-test nights before wear-freeze; sim CHECK rate not a claim.",
      "", "guardian git HEAD at generation: %s" % git]
open(os.path.join(G, "FROZEN.txt"), "w").write("\n".join(L) + "\n")
print("\n".join(L[:40])); print("... %d lines" % len(L))
