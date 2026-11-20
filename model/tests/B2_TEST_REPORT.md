# B2 (Core Sense hg2, final v4aug, CRC 0xB32FA3CA) test report — 2026-11-12
Tester T2. Scripts: `tests/t2/` (t01–t09, own forward in `t2lib.py`); outputs: `tests/t2/out/*.json`. `sealed_exam_hg2.py` was NOT run; no sealed minutes/events/ppg file was opened (a file-open tracer in t01 aborts if one is).

**Verdict: PASS WITH FINDINGS.** I found no blocker. The export, the leakage guards, determinism and feature parity are all clean. Four findings are **major**, and three of them are about claims in M11: the "NN beats v1.2" comparison is unfair, the HTT "= v1.2" comparison uses a different population, and the range is only calibrated on average across persons, not per person. The fourth is that the brief's two report deliverables are missing.

## Reproduced acceptance criteria
| # | Criterion | Command | Result | Pass? |
|---|---|---|---|---|
| L1 | No sealed id in any train/val/ES/cal index; no sealed file opened; SQL only dataset 1 | `python3 tests/t2/t01_leakage.py` | 0 overlap in v0–v4/es/val/valaug (270/30/100 persons); minutes_dev_v4 has 400 persons, 0 sealed; files opened: only dev parquet, persons, scenarios_dev_v4, caches, seal json; 2 SQL, both `dataset_id = 1` | yes |
| L2 | Patched seal (dev 0 + train 1 declared sealed) makes loaders raise | t01 part E | dev_person_ids, iter_persons (both guards), check_index on v0 and val, and assert_no_sealed all raise AssertionError | yes |
| L3 | Seal integrity | t01 | canonical SHA ok; persons.parquet SHA ok; seal commit 1661242 (11:18) predates every B2 commit (first 597b35b 12:21) | yes |
| L4 | 100 calibration persons not used for training or selection | t01 + code read | disjoint from the 270 gradient and 30 ES persons; ES = early stopping + sd-head fit; tau chosen on ES-fit persons. No calibration results are committed for v3 iterations. I cannot prove that no design choice was made while looking at them (see unverifiable claims) | yes (as far as logs show) |
| E1 | CRC .c arrays == .h == train_log == export_report == json | `python3 tests/t2/t02_export.py` | all 0xB32FA3CA; the 5 member CRCs match the log | yes |
| E2 | .c == json == member npz, bitwise | t02 | yes, including X/Y mean/std == cache norm.json | yes |
| E3 | host_test (`-Werror -Wdouble-promotion -fsingle-precision-constant`) | t02 | `CRC OK, 22 vectors, max abs error 0.000e+00, PASS` | yes |
| E4 | Own numpy forward vs C, 1,000 random SIM-DEV rows, ≤ 1e-5 | t02 (own C harness + float64 numpy from the parsed .c) | members 3.6e-6, mean 2.0e-6, core °C 1.8e-7, M6 sd °C 1.4e-7 | yes |
| E5 | golden_trace NN outputs ≤ 1e-4 °C | t02 | max 2.5e-6 °C (core), 9.4e-6 (logit) | yes |
| E6 | Weights size ≤ 36 KB; no expf/logf/powf/double/malloc | t02 | 26,900 B; 0 hits | yes |
| E7 | poc_02_hg2 compile | `arduino-cli compile --fqbn Seeeduino:nrf52:xiaonRF52840` (copy) | 73,884 B flash, 7,272 B RAM (= claim) | yes |
| E8 | SHA-256 (frozen files) | t02 | hg2_weights.json `73755107…7f`, .c `79551630…cc`, .h `3888a3d3…3a` | recorded |
| D1 | Determinism: LOSO re-run | `t04_loso_rerun.py` (redirected cache) | htt_oof raw **bitwise equal** (18 min) | yes |
| D2 | Determinism: member 1 re-train | `t09_member_repro.py` | pre_* and ft_* bitwise equal | yes |
| C1 | SIM-DEV cal: MAE now/30 ≤ 0.20/0.30 | `t03_calib.py` (own forward) | 0.149 [0.136–0.161] / 0.171 | yes |
| C2 | Coverage of ±1.645 sd, 85–95 % (no scale) | t03 | 88.5 [85.3–91.5] / 91.4 / 90.9 % (= claim) | yes (aggregate only; see F3) |
| C3 | Informativeness ≥ 2.0 | t03 | quintile 1.18 [0.99–1.37], decile 1.26 | **no** (as M11 states) |
| C4 | P385 AUC ≥ 0.90 | t03 | 0.974 (P38 0.949). **Only 8 of 100 persons have a 38.5 event** | yes (thin) |
| H1 | HTT LOSO MAE ≤ 0.30, ±0.5 ≥ 85 % | `t04_htt_score.py` (own scorer) | 0.284 [0.252–0.318], 85.3 % | yes (marginal) |
| H2 | Danger OR ≥ 70 % at ≤ 0.10/h | t04 | 33/42 = 78.6 % at 0.096/h; NN path off in 100 % of folds; NN alone 73.8 % at 0.078 | yes (NN adds 0) |
| H3 | Drink ≥ 85 % at ≤ 0.15/h (hg2 f20) | t04 | 86 % at **0.174/h** | **no** (as M11 states; protected v1.2 path) |
| P1 | Flux permutation, ≥ 37 °C and 34–37 °C, \|Δcore_now\| ≤ 0.30 for 99 % | `t05_flux_sign.py` | 100 % / 100 % (p99 0.00 / 0.10 °C); band-t_air regimes also 100 % | yes (≥ 37 is nearly vacuous, F9) |
| P2 | Sign checks: ∂logit_p385/∂hr_reserve, ∂/∂kf > 0 | t05 | mean +4.59 / +3.45, 0 % negative; monotone kf/hr_reserve sweeps have 0 drops | yes |
| F1 | Feature parity with hg_guardian_py: 32 names/order, 3 persons × 1 day | `t06_features.py` | names == ARCH 4.1 table; **0 mismatching values** (one day had injected band-off, loose, NaN HR, time-unknown and T2-missing blocks) | yes |
| F2 | Independent from-spec recompute (windows, units, gates) | t06 | exact for t1/d5/d15/dT/dT_d10/flux_valid/rh/core_flux; LUT approximations ≤ 5e-4; EWM45 0.015 bpm (α rounding) | yes |
| F3 | Cache == FeatureState on raw data (10-day replay, cal person 24) | t06 | 0 mismatches in 12,975 rows; truth targets == parquet for 2 persons | yes |
| O1 | OOD outputs finite and bounded | `t07_ood.py` | 24/26 cases finite and bounded; 2 non-finite cases (F6) | partial |
| X1 | Fair "NN beats v1.2" | `t08_fairness.py` | **not fair as stated** (F1) | no |

## Attacks and findings (ranked)
| id | Attack | What happened | Why (diagnosed) | Severity |
|---|---|---|---|---|
| F1 | Rerun the M6.4 / M11 "NN beats v1.2 at the same FA budget" claim, then give v1.2 the same treatment (t08) | I reproduced the builder's numbers exactly: S1 v1.2 87.6 % at 0.316/h vs NN 99.4 % at 0.174/h. When v1.2 gets the **same offset grid and the same nested 5-fold tuning**, it reaches **100 %** at 0.14–0.17/h in S1, PRE, POST and S2. That is ≥ the NN's 98.8–99.5 % at the same budget. The NN wins only at **≤ 0.10/h**: S1 98 vs 45 %, S2 91 vs 43 %, POST 98 vs 38 % | `m5.gain_test` tunes only the NN threshold (`OFFS`, nested) and keeps v1.2 fixed at 37.85 − margin. On sim, v1.2's HR anchor reads high (M7: sim HR +12 bpm, V4), so its fixed line is out of domain and over-fires at 0.31/h. Events, scoring window (−45/+10), FA definition (no 38.0 within 60 min) and episode rule are identical for both, so those parts are fair. The asymmetry is the threshold calibration. The HR-scaled view (`valaug`), where that bias is removed, cannot be event-scored: it is cached at stride 2, so no two consecutive minutes exist. The builder did not test it either | **major** (claim) |
| F2 | HTT "hg2 = v1.2 (0.284 vs 0.29)" (t04, t04c) | 0.29 is v1.2's REPORT LOSO on 52 other-fold people. On the **same 65 people and minutes**, v1.2's fixed estimate is **0.261**, and hg2 − v1.2 = +0.012..+0.036 °C (subject bootstrap). On the 13 people v1.2 never saw (v1 split, used only as membership): 0.259 vs 0.244, CI −0.004..+0.032. Within ±0.5: 85.3 vs 88.7 % | Different populations are being compared. Even in-sample after fine-tuning, the HTT MAE is 0.27–0.28 (train_log), because the thermal inputs are masked to z = 0 on HTT. The fair statement is "not significantly worse on unseen young adults, numerically 0.015 °C worse" | **major** (claim) |
| F3 | Per-person calibration of the range (t03) | The aggregate coverage of 88.5 % hides a spread: per-person median 96.6 %, **19 % of persons below 80 %**, minimum 16 %, 41 % above 98 %. Person-level Spearman(mean sd, MAE) = −0.02. On HTT the ±1.645 sd range covers **48 %** | The sd heads were fitted pooled (pinball, ES persons). The per-person offset that dominates the error is not visible from these inputs, so the range is calibrated on average across simulated persons, not per wearer. M11's "calibrated range (88–91 %)" claim needs "on average across persons, SIMULATION" | **major** (claim) |
| F4 | Required deliverables | `model/REPORT_MODEL.md` and `reports/B2_model_report.md` do not exist | Not written. So the sim-to-real statement, the κ caveat and the SIMULATION/young-adult labels in the report cannot be checked | **major** |
| F5 | Export labels and an unmeasured number | `hg2_weights.h` lines 1–2 say "32-24-16-6 x5" and "PROVISIONAL: trained on … sim v1". `export_report.json` reports `kf_max_abs_diff_vs_B5_scalar_mirror: 0.0`, but that number is **never computed**. `results_eval_hg2.json` labels the 100 calibration persons "40-person … used for early stopping" | export.py `write_c` has a hard-coded stale header. In `golden()`, `maxd = 0.0` is never updated, because the B5 comparison call was removed after the 9-output crash in `logs/run_v4aug_rest.log`. eval.py:82 has a stale label string | minor |
| F6 | Non-finite inputs (t07) | T1 = +inf makes **every NN output NaN** (v1.2 f20 = −inf). PI = +inf makes Python `FeatureState` raise IndexError | Only NaN is treated as missing (`features.py` holds/zeros NaN only; `normalise_x` maps NaN, not inf, to 0). `ln1p(inf)` leaves y = inf after the e < 64 cap, and then `lerp_tab` truncates inf to an int (features.py:41). In C, `hg_util.c:7` does `(int)pos` on inf, which is undefined behaviour | minor (major if hg_ppg can emit DC = 0) |
| F7 | OOD HR (t07) | From HR 180 to 220 the NN **falls**: core_now 38.67 → 38.38, logit_p385 1.2 → −1.6 (kf 42.0, v1.2 f20 39.98). HR 140 with beta-blocker at 85 y: NN 37.6 vs v1.2 39.7. All outputs stay bounded | Outside training support (p99 HR 108). The M11 OOD guard (max(NN, v1.2) when hr_reserve > 0.6 or HR > 108) covers it. B5 must implement it, and a test must prove it (B5's tree is uncommitted, in progress) | minor (mitigated) |
| F8 | Coherent HR +5 bpm (t05) | logit_p385 decreases on 2.2 % of rows (min −0.13). core_20 is negative in ∂/∂kf on 5 % and ∂/∂hr_reserve on 15 % of rows | The monotonicity hinge (train.py `MONO`) covers only hr_reserve and kf, one feature at a time, not hr / hr_ewm5 / hr_above_rest together. No alarm effect today, because the NN cuts are 1e9 | minor |
| F9 | Is the ≥ 37 °C permutation meaningful? (t05) | flux_valid = 1 on only 0.46 % (T_in) / 0.03 % (band t_air) of ≥ 37 °C minutes, so the test passes by construction. At 34–37 °C (73–79 % flux-valid) it passes for real (p99 0.10 °C). A transplant attack (flux features from flux-valid rows injected into ≥ 34 °C rows) also passes: 100 % ≤ 0.30, max 0.28 | Gate `T_air < T1 − 0.5` | minor (information) |
| F10 | host_test coverage | Test-vector std is the plain between-member std. The M6 total-sd formula is never C-tested. The one-pass float32 variance of the logit outputs is off by 2.8e-5 (> 1e-5) vs float64 | hg2_nn.c `s2/5 − mu²` cancellation at \|y\| ≈ 5–7. Not used by tiers | minor |
| F11 | Spec deviations (consistent across Python, C and the mirror) | `hr` is held forever, but ARCH 4.1 says "≤ 10 min" (`hr_age` is counted, never used). `heat_dose` decrements when not above the line, but the spec says "minutes above". Domain randomisation is per person-view, not per batch; extra HR outliers are U(0, 0.12) vs spec [0.05, 0.3]. `persons.parquet['split']` is empty, but the brief says seal_hg2 fills it. κ tercile edges use the parameters of all 500 persons, sealed ones included (no outcomes) | Design choices that were not disclosed in a report | minor |
| F12 | Calibration-person Twin | `build_sim.nominal_twin` sets rest_hr = **true** hr_rest + N(0, 3) for the calibration, golden and gain-test persons | The calibration numbers assume a Twin that already knows rest HR to ±3 bpm. Day-1 wearers will be worse | minor (optimism) |

## Unverifiable claims
| Claim | Why |
|---|---|
| "100 calibration persons never used for any choice" | The code and logs are consistent with it (ES monitor only, no v3 calibration results committed), but uncommitted iterations cannot be audited |
| golden_trace reproduced by B5's C `hg2_step` ≤ 1e-4 | B5's 9-output C/Python integration is uncommitted. I verified the golden NN outputs against my own forward (2.5e-6 °C) and the features against the mirror (bitwise) |
| DWT < 1 ms on the M4F | Not measured on hardware |

## Labels missing
The `hg2_weights.h` header has a stale "PROVISIONAL sim v1" / "32-24-16-6" label, and the eval label is wrong (F5). There is no B2 report, so the report labels are unverifiable (F4). The JSON results carry SIMULATION / young-adult labels.

## Open risks to the manager
- Replace "NN beats v1.2 at the same FA budget" with: "at ≤ 0.10/h on SIM-DEV the NN Drink line reaches 91–98 % vs 38–59 % for a re-thresholded v1.2. At 0.15/h, v1.2 re-thresholded on sim matches it (SIMULATION)" (F1).
- HTT: report v1.2 on the same minutes (0.261 / 0.244 on the unseen 13) next to hg2 (0.284 / 0.259), not REPORT's 0.29 (F2).
- The range is calibrated across persons, not per person (19 % of simulated persons < 80 % coverage; HTT 48 %). The conformal widths HG2_CONF_HALF_* inherit this (F3).
- B5 must implement and test the M11 OOD guard (F7) and an isfinite guard on T1/PI/T2 (F6) before freeze.
- B2 still owes REPORT_MODEL.md and B2_model_report.md, plus a regenerated header (F4, F5).
