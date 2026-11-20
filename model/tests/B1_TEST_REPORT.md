# B1 test report — 2026-11-12 (tester T1, Virtual Elders v2 frozen)

**Everything below is SIMULATION** (Virtual Elders v2; known too-tolerant at humid rest, bed rest and HR, plus the new findings below).
Scripts: `/home/claude/hg_ai/tests/t1/`, outputs: `/home/claude/hg_ai/tests/t1/out/`. Builder code and files were not modified.
My own scripts simulate **DEV persons only**. The builder's validation sections (re-run as is, see §1) simulate sealed persons' parameter vectors internally (finding F9). I did not look at their per-person outputs.

Verdict: **FAIL**. There are two blockers (B1: no night sleep after day 0 in the training data; B2: V1 is scored PASS but fails by R1's own definition). The rest of the module reproduces well: 44/46 VALIDATION rows regenerate exactly, the leakage and split are clean, reruns are byte-identical, and the labels are correct to the quantisation level. **Zero findings without a diagnosed why.**

## Reproduced acceptance criteria
| # | Criterion (brief/ARCH) | Command I ran | Result | Pass? |
|---|---|---|---|---|
| 1 | Every VALIDATION row regenerates with its own command | `python3 -I tests/t1/run_section.py <s>` for all 7 sections (builder code, rows written to `tests/t1/out/rows_*.json`), then `tests/t1/t_compare_validation.py` | **44/46 identical**. 2 differ (V19, KAPPA), see F7 | 44/46 |
| 2 | Ji agreement (9 conditions, ≤0.05/0.3 °C) | section agree | 0.00e+00 / 0.00e+00 (line-by-line re-implementation; features off) | PASS |
| 3 | Energy balance < 1 W/m² per step | `t_physics_props.py` (own closure, 60 dev persons × 2 days random env) | 5.7e-14 W/m², provided that the *previous* step's E_sk is used (F12) | PASS |
| 4 | No NaN in truth; sensor NaN only "no reading" | `t_props_dev.py 4` (100 dev persons, 1.44 M rows) | truth NaN 0; NaN only in HR_meas (off + no-reading) and PI (off) | PASS |
| 5 | Core 35–41 °C in the data | same | 36.38–39.18 °C | PASS |
| 6 | T1 ≤ T_core | same | 4711/1.28 M worn minutes violate. 4442 have hot air ≥ core−0.5, 247 sun on lid, 22 come from lag within 30 min of a sun episode (`t_diag_dT.py`) | PASS (all explained) |
| 7 | ΔT ≤ 0.6 at T_air ≥ 38 °C (M2.5 regime) | `t_props_dev.py`, `t_sensor_consistency.py` | data: 99.86–99.93 % per bin ≥ 38 °C; every violation is a T1/T2 lag ≤ 40 min after a location change; steady state, all 400 dev sensor sets: max 0.35 °C | PASS |
| 8 | ΔT at 34 °C (R2 literal) | same | 14.7 % ≤ 0.6 at 34–35 °C; steady-state max 1.29 °C. Confirms the builder's R2-dT34 FAIL | FAIL (known, M2.5) |
| 9 | R2 §6.5 fan / loose cross-consistency | `t_sensor_consistency.py` | fan: T1↓, ΔT↑, SHTC3 contamination↓ for 100 % of persons; loose: T1↓, ΔT↓, PI↓ for 100 % | PASS |
| 10 | Monotone ΔT_core in T_db | `t_mono.py` (1 °C grid 22–44, RH 20/45/70, met 0.86/1.37, 400 dev) | violations ≤ 0.028 °C; **also above 30 °C** (F11) | FAIL (known sub-30 + new) |
| 11 | Labels ev38_30 / ev385_30 / strain_psi | `t_props_dev.py` (own sliding max over (t, t+30]) | 184 / 11 mismatches in 1.44 M rows, all within 0.0006 °C of the threshold (F13); PSI max err 0.0016 | PASS (minor) |
| 12 | Determinism / byte identity | `t_repro.py` | dev person 0 regenerated: all 36 columns byte-identical to `minutes_dev_v2`; rerun identical; alone == batched with another dev person | PASS |
| 13 | Parquet sha256 / size | `sha256sum` | dev_v2 293e0daa…bcf34, sealed_v2 03c1c09d…84cc3 (match the report); v2 total 455 MiB = 477 MB | PASS |
| 14 | Sealed persons absent from DEV | `t_leakage.py` (sealed files: person_id column only) | 0 sealed ids in minutes/ppg/events dev (v1 and v2); the sealed files hold exactly the 100 sealed ids; persons sha = seal json; seed = 20261112 + id, unique; streams [seed,1..4] per person | PASS |
| 15 | Builder pytest | `pytest -q sim/tests` | 18 passed, 2 xfailed (strict) | PASS |
| 16 | 500 × 10 d in < 2 h | not re-run (shared CPUs) | — | unverified |

## Re-derived targets (task 2)
| Target | Independent source | My number | B1's target | Copied correctly? |
|---|---|---|---|---|
| V12 older ADL P_a,crit 34/36/38/40 | raw PSU Excel `hgdata/raw/3_psu_heat/…Compiled Data.xlsx`, mean of trials (`t_rederive_psu.py`) | 3.411 / 3.213 / 3.072 / 2.537 kPa | 3.41/3.21/3.07/2.54 | yes. V13/V14/V15 also reproduce exactly |
| V2 Meade 2024 +0.2/+0.7/+0.9 ±0.15 | R1 §7.1 + §3.2 line 300 (CIs 0.0–0.3 / 0.5–0.8 / 0.8–1.1). The full text could not be fetched (EHP/PMC blocked) | — | identical to R1 | yes. R1's CIs indicate a contrast vs the 22 °C arm, which supports B1's "minus 22 °C arm" convention. The 22 °C arm itself rises +0.47 °C in the sim (`t_v2_convention.py`) |
| V5 sweat 20/26/31/80 ±15 | R1 §7.1 | — | identical | yes. PASS only as skin water loss E_sk/0.68 (12/14/35/66). Regulatory sweat alone (0/1/26/69) fails at 22 and 26 °C |
| V21 ratio 0.44–0.63 | raw PSU Excel | measured older ADL at the limit 77–90 g/(m²h); ratio 0.44–0.63 ✓ | — | yes. The sim's absolute sweat is too high (F8) |

## Attacks and findings (ranked)
| id | Attack | What happened | Why (diagnosed) | Severity |
|---|---|---|---|---|
| **B1** | Routine in the stored data (`t_sleep_bug.py`) | **No night sleep on any stored day.** asleep = 0 for 100 % of 01:00–05:00 minutes in `minutes_dev_v2`. Mean asleep is 2.8 % of minutes (naps only), and 3 persons never sleep at all. From bedtime to wake the person "sits" (act=sit, met 0.86, living room, clo 0.4, a_std ≈ 0.006 g) and drinks ~0.59 L between 01:00 and 05:00 each night. For person 6, `build_person` gives asleep minutes per day [384, 0, 0, 0, 0, 0, 0, 0, 89, 83, 79] | `scenarios.py` build_person: `_set(tl.act, o + prev_bed, o + W_, …)`, where `prev_bed` = yesterday's `B_` (≈1380 min, measured from **yesterday's** midnight). For d ≥ 1, start = o+1380 > end = o+420, so `_set` does nothing. Only day 0 (spin-up, discarded) has `prev_bed = B_ − MPD`. The minutes left over keep the Timeline default `sit`/room 0. This removes S3 night heat, the bedroom (+0.4–0.6 °C), sleep met 0.7, bed clo, the SHTC3 sleeve and night stillness from **all** training data (about 1/3 of the minutes). The validation protocols build their own routines, so no VALIDATION row exposes it. B2 is training on this data now | **blocker** |
| B1b | S9 late-wake anomaly | the "no wake until 11:00" days show sitting until about 10:00 and then chores (person 0, day 5) | consequence of B1. Separately, chores (09:00 + jitter) and meals at fixed clock times are written after the sleep block and would overwrite a late wake even after a fix | blocker (with B1) |
| **B2** | V1 scoring | the table shows "36.40 C at 08:00 … 8-h mean 36.63" → **PASS** | `validate.py` section_rest tests `abs(8-h mean − 36.7) ≤ 0.2`. R1 V1: thermoneutral baseline 36.7 ± 0.2, "accept 36.8–37.2 at other times of day". The 08:00 value 36.40 is outside 36.5–36.9, and the daytime mean 36.63 is outside 36.8–37.2. **It fails under both readings**, so the true must-pass count is **11/17**, not 12/17. Consequence: the morning resting core is ~0.3 °C low (the 22 °C arm then rises +0.47 °C over the day) | **blocker** (mandatory row) |
| F3 | V19 second half (12 mmHg) | the value column shows a median lead of **−4.4 °C** (regenerated −5.8 °C): HR drift starts at T_db 48 °C, **after** the core inflection at 42 °C. Kenney: HR first, 41 vs 43 °C. The pass logic scores only the humid half, and M3.4 cites only the humid median | drift is driven by w/w_max > 0.94 (`body.py` DRIFT_THR). In dry heat the wettedness cap is reached late, so HR drift follows the core instead of leading it. Bias: in dry heat the NN learns that HR lags core → it under-warns | major |
| F4 | Indoor maxima by home class (`t_props_dev` side query) | class C homes peak at a median 42.8 °C and a max **43.3 °C** indoors, above the outdoor max (41.3 °C) and above the only Athens measurement (Sakka 2012: "up to 40 °C", R3 §1.1). Class A homes reach 40.2 °C | R3 §1.6 class C: ΔT_home +4–5 °C (given "on hot days") is applied always, plus g_sun 0.3 °C per 100 W/m². R3-i/ii are run on single mid-parameter homes only; no row checks the population's indoor maxima. Bias: **over**-exposure (pessimistic), which contradicts M3's claim that all biases point one way | major |
| F5 | Calibration reproducibility | `body.py` cites `tools/calib_v3.py`, `tools/calib_omega.py`, `tools/calib_acclim.py`; `sim/tools/` contains only `figs.py` and `write_validation.py` | the constants OMEGA_FRAME 1.6, ACCLIM_THR_SHIFT 0.9, ACCLIM_OMEGA_GAIN 0.5 and SKIN_REPORT_OFFSET 0.12/1.2 cannot be regenerated from the repo | major |
| F6 | PSU protocol humidity (`t_psu_supersat.py`) | the P_a ramp runs to **223 % RH** at 34 °C. 20 % of the healthy cohort's V13 34 °C P_a,crit lie **at or above saturation** (5.32 kPa) | `protocols.psu` never caps P_a at p_sat and `body.step` accepts RH > 100. This inflates the V13 34 °C mean (4.70) and the builder's mechanistic numbers. The direction still holds (at 100 % RH rest the core rises 0.31 °C/h) | major |
| F7 | Table vs command | V19: table 49 %/62 %, HR-onset RH 55 %, 12 mmHg −4.4 °C; regenerated 50 %/64 %, 54 %, −5.8 °C. KAPPA T1: 2.9 vs 3.1 | `validation_rows.json` (limits section) predates the last `body.py` edit (HR core-excess unclip changes HR timing). The why-text already quotes the new numbers (50/64 %). The report's V2 triple (+0.91) is round 1; the table has +0.96 | minor |
| F8 | Absolute sweat / storage | V21 older sweat at the limit 152 g/(m²h) vs PSU 84–90 (1.8×); young twin 242 vs 136–178. V11 storage 577 kJ vs 358 ± 173 (outside +1 SD) | OMEGA_FRAME 1.6 enlarges the evaporative capacity. Ratio rows pass while absolute rows are not scored. Too tolerant (more evaporation) | minor |
| F9 | Sealed hygiene | the builder's validation and tests simulate sealed persons: 6 sealed in the sensor probe (ids < 40), 33/169 in the "healthy" limit cohort, 22/100 in R2-dT-cool, sealed id 37 in the pytest random sample. `scenarios_v2.parquet` stores sealed persons' regime and day types beside dev rows | not a training leak (the dev files are clean, check 14), but sealed parameter vectors' outputs were inspected while calibrating the simulator, against "anything looked at during development is dev". Note that my rerun of the builder's sections did the same | major |
| F10 | Builder-made tolerances | V10 accepts 31.5−0.5 (ARCH "—"; value 31.3 < 31.5). V20's check `max(w_cap) < 0.85×1.6` can never fail (w_max is clipped at 1.0); the model-frame cap reaches 0.90. V25 is computed on the healthy tercile only (ARCH: across persons); its why-text says "Rest SD 4.8" but the value column says 3.98. V29 window 1–3 h set by the builder | `validate.py` lines in section_rest/limits | minor |
| F11 | Monotonicity, finer grid (`t_mono.py`, `t_mono_diag.py`) | violations **above 30 °C**: 20 % RH ADL 30→31 (11 persons, −0.018), 31→32, 32→33, 34→35; 20 % rest 36→37; 45 % ADL 30→31 (8 persons). Below 30 °C up to 30/400 persons per step, worst −0.0276 (claim: ≤ 7/500, ≤ 0.025) | same Gagge mechanism the builder names (vasoconstriction release below skin 33.25 °C). With ADL evaporation in dry air the skin node stays at 32.4–33.2 °C up to T_db ≈ 35 °C. A_COF 0.2 changes nothing (no sweating drive there). The builder's 2 °C grid at 45 % RH hid it | minor |
| F12 | Energy API | same-step closure from the returned dict has residuals up to 280 W/m² | the returned `E_sk` is the value used in the **next** step, and the ENERGY row is an integrator identity (it holds by construction) | minor |
| F13 | Labels vs stored T_core | 184 ev38 / 11 ev385 disagreements in 1.44 M rows | labels are computed from unquantised float32 T_core, then the column is rounded to 0.001 (`population.quantise`) | minor |
| F14 | Column semantics | outdoors, `T_in` is the home temperature (README: "outdoors = T_out") while `RH_in` is the outdoor RH | `population.py` T_in/RH_in assembly | minor |
| F15 | HR floor / core ceiling | HR_true below the drawn rest by up to κ·0.5 (min 38.7 bpm in data). With off-library environments (46 °C/90 %) core reaches 45.5 °C with no ceiling | unsourced negative κ_core extrapolation (floor −0.5 °C); no collapse state | minor |
| F16 | Missing output | no RMSSD column although ARCH §3.3 / R2 §6.3 list it | not implemented | minor |

## M3 bias claims (task 7, own protocol code; DEV healthy cohort n = 136; `t_m3_bias.py`)
- **V13 humid rest too tolerant:** confirmed. With my detector (0.2 °C above the pre-ramp trend) the 34 °C P_a,crit is 6.1 kPa (builder 4.70, PSU 3.53). The magnitude depends on the method; see F6.
- **V4 HR:** confirmed. ΔHR(36 − 22 °C) is +25.7 bpm (Meade +14) at ΔCore +1.07 °C. The slope is 23.9 bpm/°C vs 15.6, so a real +14 bpm would be read as **+0.58 °C instead of +0.9** (under-read).
- **V7 bed rest:** confirmed under the delta convention: +0.76 °C at met 0.82 and +0.59 °C at met 0.70, vs +1.1. Caveat: the absolute peak is 37.62 °C, inside 37.8 ± 0.2, only because the baseline is 0.3 °C low (B2).
- **"All residual biases point the same way" is not established:** F4 (indoor heat too high) and B1 (night met 0.86 vs 0.7 is warmer; night drinking and living-room air are cooler) push in mixed directions; F3 and F8 add further under-warning.
- V2 depends on drinking: without drinks, 36 °C gives +1.075 (FAIL); with the builder's thirst policy plus 2 glasses, +0.964.

## Unverifiable claims in the builder's report
| Claim | Why |
|---|---|
| Runtime 514 s for 500 × 10 d | full rerun not done (2 shared CPUs); per-person 15 s single-process is consistent |
| Byte-identical full rerun | verified for one dev person and batching, not for the whole files |
| V7/V13/V4 "levers tried" numbers (fr 1.8 → V4 75.8, etc.) | no script or log of those sweeps in the repo (cf. F5) |

## Sources missing or wrong
- OMEGA_FRAME 1.6, OMEGA_REST_FACTOR 0.85 (ARCH says 0.75; accepted by M3), A_COF 1.0 (Ji 0.2), HC_FLOOR 2.5, DRIFT_* constants, skin report offset 0.12/1.2: calibrated, with no script (F5).
- CIRC_ATT_SPAN 8 / FLOOR 0.25 / CIRC_RELAX_MIN 360 (R1 §3.3 gives only the qualitative "nadir attenuated at 30 °C") and the "+3 °C + 15·S/900" lid excess (R2 §6.1 gives only "lid 45–60 °C"): no numeric source.

## Labels missing
- The data files carry the `label: SIMULATION` metadata and the README banner ✓. The report is labelled SIMULATION ✓. Nothing missing.

## Open risks I would raise to the manager (≤ 5)
1. **Sim v2 training data have no nights (B1).** Every SIM-DEV/SEALED-SIM number from B2/B3/B5, the routine detector's S9 sensitivity and the night-heat story rest on it. After the fix, regenerate v3 and re-seal-check.
2. Must-pass is **11/17**, not 12/17 (V1).
3. HR leads core only in humid heat; in dry heat it lags by ~6 °C T_db (F3). An HR-anchored alarm will be late in dry heat waves.
4. Class C indoor exposure exceeds anything measured in Athens (43 vs 40 °C). Event base rates (ev38 in 7.6 % of minutes) are inflated for those persons.
5. The calibration constants cannot be reproduced from the repo (F5).
