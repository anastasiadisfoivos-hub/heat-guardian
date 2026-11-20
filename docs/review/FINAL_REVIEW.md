# Heat Guardian AI sprint — independent final review

Reviewer: independent (built none of it). Date: 12 Nov 2026, repo HEAD `a9edee0`.
Method: files, git history and my own commands only; no builder summary was taken on trust.
`fw/` is moving (B6 fix round in progress: `fw/08_logger` has uncommitted edits and a new `hg_nofastmath.h`); firmware findings below describe the committed state.

## 0. Verdict in one page

**The process is honest and the seals hold. The results are weaker than DECISIONS M11/M13 read, and three of them are not written down anywhere yet.**

What is solid:
- Both seals were made before what they guard, the three DONE files were each written once, no training or evaluation code touched sealed data, and the frozen sources are byte-identical from tag to exam to firmware copy.
- Testers found real blockers (no nights in sim v2, an unfair NN-vs-v1.2 comparison, fast-math breaking the shipped ARM image) and every one has a diagnosed cause.

What a judge will find if the team does not say it first:
1. **The neural network is not better than the old heart-rate Kalman on the only real data** (0.284 vs 0.261 °C on identical minutes, difference significant). M11 still says "= v1.2".
2. **The family-alert tier is weak even after the M13 fix**: 61 % of core-38.5 events in simulated heat waves with raw HR (11/18), 22 % with the HR bias removed (4/18), median lead −2 min, and about 15 false Danger episodes per wearer-month on ordinary days.
3. **The DRINK alarm budget is missed on both sealed sets** (3.65–4.0 per day, 142–144 min/day against a budget already relaxed from 1/60 to 3/90). No decision records this.
4. **The firmware as built does not run the frozen model** (`-Ofast` removes NaN handling: 0 DRINK minutes on the band where the host shows 297). T6b verdict is NO-GO; fix in progress.
5. **Nothing here is evidence about a real person over 65.** The submission draft that must say so (checklist item 10) does not exist yet.

None of these is fatal for WAICY. The sealed-exam discipline, the simulator with its failures published, and a wristband that works on a real wrist are a strong entry *if the pitch claims exactly what section 3 supports*.

---

## 1. ARCHITECTURE §9 checklist

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 1 | Seal exists, hash matches `persons.parquet`, predates training | **PASS** | `sha256sum sim/data/persons.parquet` = `eb9ad75e…5aca` = `model/sealed_hg2.json`. Canonical string re-hashed by me = `fce91b45…366c`. Seal commit `1661242` 11:18:17; first B2 commit `597b35b` 12:21; the only earlier work is B3's twin code (no sim minutes existed). File mtime 11:18:16 agrees. |
| 2 | DONE written once; numbers in `reports/` equal the file | **PARTIAL** | Each DONE file has exactly one commit (`5ae8297`, `1759117`, `0c3533b`), all by the manager, working tree clean. But **`reports/` contains no sealed number at all**. The only summary is DECISIONS M13 (set 1), which matches the file but is selective. The model-level exam and the set-2 exam are reported nowhere. |
| 3 | No training script indexes a sealed id | **PASS** | `assert_no_sealed` in `model/hg2/{common,train,build_sim,eval,export,m5,fix_b2,simio}.py`; guards in `twin/sim_io.py`, `guardian/py/sim_adapter.py`. My own check of `model/cache/v4aug/*.npz`: train 270, early-stop 30, calibration 100 persons, 0 sealed in each. Only `sealed_exam_*.py` and `sim/tools/gen_sealed2.py` name a sealed file. T2 L1–L3 (file-open tracer) agrees. |
| 4 | Weights CRC = training log = firmware boot print | **PARTIAL** | I recomputed zlib CRC-32 over the 26,900 weight bytes in `hg2_weights.json`: `0xB32FA3CA` = `model/logs/run_v4aug.log` = `hg2_weights.h:30` = `FROZEN.txt` = `fw/09_guardian/frozen/hg2_weights.h`. The boot print in `fw/09_guardian/BOOT_LOG.txt` is "written from the source, NOT captured from a board". |
| 5 | Every threshold in `hg_guardian.c` appears in §7.2 with source | **FAIL as written** | §7.2 is stale: it still describes `f20 = mean + sd`, the WHO night rule as a tier trigger and the `sd ≥ 0.25` rule, and has zero mentions of design A, `HG_V12_CTX_C`, the OOD guard or Danger-by-persistence. In substance the job is done elsewhere: every define in `FROZEN.txt` carries `[SOURCE]`, `[DESIGN]`, `[M-decision]` or `[SET IN SIMULATION]`. Three alarm thresholds are SET IN SIMULATION (Δ 0.30 °C, T_ctx 30 °C, X 20 min) and about 40 are DESIGN. |
| 6 | Every SIM number in `reports/` says SIMULATION | **FAIL (minor)** | `reports/B4_tomorrow_report.md` gives indoor model outputs (night minima 30.3–33.9 °C, demo plan) with no label. `model/sealed_exam_hg2_DONE.json` labels v4 data "Virtual Elders v2"; `train_log.json` still says "PROVISIONAL (sim v1, M2)". B1 and REPORT_MODEL are labelled. |
| 7 | `VALIDATION.md` has no empty why | **PASS** | `VALIDATION.csv`: 47 rows, 28 PASS, 19 FAIL, 0 FAIL without a why (my script). Mandatory rows 11/17. |
| 8 | `arduino-cli compile` output for 08 and 09 with sizes | **PASS** | 08 v1.1.0: 211,024 B (26 %), RAM 32,216 B (`tests/t6a/compile_log_v110.txt`). 09 v0.9.1: 296,432 B (36 %), RAM 68,616 B (`tests/t6b/compile_uf2.txt`). Both must be re-pasted after the B6 fix. |
| 9 | Every TEST_REPORT has zero "failing without why" | **PARTIAL** | The six reports that exist all state it and I found none. **There is no test report for B5 (Guardian Loop) and none for B7 (dashboard)**: the module that decides every alarm has no independent tester. `B1_TEST_REPORT.md` tested sim v2 (verdict FAIL); v3 and v4, the training simulator, were never re-tested. |
| 10 | §2 honest-position page verbatim in the submission draft | **FAIL** | No submission draft exists in the repo. |

### Seal timeline (git + mtimes + DONE timestamps, all consistent)

| Time (EET) | Event |
|---|---|
| 11:05 | `persons.parquet` committed (500 persons) |
| 11:18 | **Seal 1** (100 sim persons + 5 office subjects) |
| 12:21 → 13:53 | B2 training runs v1 → v4aug |
| 14:20 / 15:15 | tags `hg2-freeze`, `hg2-freeze-2` |
| 15:15–15:16 | Model-level sealed exam, once (git `d150de8`) |
| 15:29–15:51 | System sealed exam set 1, once (tag `hg2-freeze-2`) |
| 15:51:58 | **Seal 2** (ids 500–599, seed 20261113) — before generation |
| 15:52–15:53 | SEALED-SIM-2 generated by `gen_sealed2.py` |
| 16:21:45 | tag `hg2-freeze-3` (only change vs freeze-2: the persistence rule, 6 files, 53 lines) |
| 16:22–16:46 | System sealed exam set 2, once |

Notes on the timeline:
- **History rewrite at 16:19–16:21** (reflog: `tmp` commit, an amend that swallowed B7's commit, a manager reset). I diffed the dangling commits against what replaced them: the guardian tree is identical apart from one added dry-run file. The first `hg2-freeze-3` tag object is dangling and was re-created on `7a09e19` with the same FROZEN hash. Benign, but it should be written down.
- `3fdae9a` changed the exam script 35 s before the set-2 run (README hash parser). It touches only the hash-reading guard, which runs before the DONE file is written. It implies a first attempt stopped at that guard. Acceptable; disclose.
- Seal 2 cannot hash data that does not exist yet, so it hashes ids + seed + generator commit; data hashes were written by B1 at generation and asserted by the exam. Sound.
- T1 finding F9: in simulator rounds 1–2 the builder's validation simulated sealed persons' parameter vectors (33 of 169 in the limits cohort). Not a training leak, fixed in round 3, but the simulator's two calibration constants were chosen while those outputs were in view.

---

## 2. Scientific integrity

### 2.1 Decisions that are defensible
- **M1** (alarm fatigue rules), **M2.3** (day-2 escalation moved to documented limitation rather than tuned), **M4/M10** (Twin claim cut down to what is measured), **M5** (drop the uncertainty claim when data refuted it), **M11** not-met rows reported as not met, **M12** (COOL/DANGER never gated), **M14** (flash over budget reported, wording changed rather than the number).
- **M3**: training on a simulator that fails mandatory rows is defensible because the non-NN safety paths stay as OR-paths and the property test proves the NN cannot remove an alarm. One correction: T1 showed "all biases point the same way" is not established (indoor homes peak above any Athens measurement; night metabolic rate was high).
- **M8**: changing the simulator's HR model after seeing DRINK over-fire is the riskiest-looking step. It is recorded as a bug fix with the mechanism named, V4 still fails afterwards, and the old data are kept. Acceptable.

### 2.2 Where a target or budget moved, or was missed quietly

| Issue | What happened | Judgement |
|---|---|---|
| **DRINK budget** | M1.4: ≤ 1/day, ≤ 60 min/day. M9.2 revised to ≤ 3/day, ≤ 90 min, right above the measured 2.5 / 86 on sim v3, with a public-health reason added afterwards. On v4 DEV at freeze: 3.5/day, 102 min (commit `d150de8` message: "no T_ctx meets 3/day & 90 min/day raw"). Sealed: 4.0 / 142 (set 1), 3.65 / 143.5 (set 2). | Moved once with a stated reason, then **missed with no decision recorded**. The exam JSON still prints the original 1/60 targets. Must be reported as a missed budget. |
| **Danger budget (M15)** | "≤ 1 per wearer-month on S1" is read on the median wearer, which is 0 for every X and for the rule switched off. The mean is 8.4/month on DEV and exceeds the budget for every option. | Disclosed, but a criterion every option passes selects nothing. X = 20 was chosen on sensitivity alone. Say that. |
| **V18** | Passed in round 2 after the scoring protocol changed to Cottle's fixed-environment design. | Target range unchanged, protocol changed; disclosed in VALIDATION item 11. Borderline but honest. |
| **COOL ≤ 1/week** | Set 2: 1.4/week on the median S1 wearer; mean 1.3 false COOL episodes per day. | Missed on set 2, unrecorded. |
| **S9 routine ≥ 90 %** | Set 1: 12/13. Set 2: 16/20 = 80 %. Routine CHECK 11/wearer-week against ≤ 1. | M9.4 already says routine is untuned; the set-2 miss is unrecorded. |

### 2.3 M11 statements that the team's own tester overturned (not amended)
- "NN beats v1.2 at the same FA budget (98–99.5 % at 0.10–0.17/h vs 88–95 % at 0.31/h)" compares different false-alarm rates. With the same tuning for both (T2 F1, `REPORT_MODEL.md`): NN wins only at ≤ 0.10/h in simulation; at 0.15/h v1.2 reaches 100 %.
- "HTT dev = v1.2 (0.284 vs 0.29)" compares different people. Same 65 people and minutes: v1.2 0.261, hg2 0.284, difference +0.024 °C (95 % CI +0.012 to +0.036). On real alarms v1.2 is also ahead (Drink 85 vs 79 % at 0.10/h).
- "Coverage 88.5/91.4/90.9 %" is the DEV calibration set. **Sealed: 85.0 % (84.7 % with HR scaling, below the 85 % floor); conformal interval 86.2–86.9 % against a 90 % target.** 19 % of simulated persons get under 80 %; on real HTT data the simulated range covers 48 %.

`REPORT_MODEL.md` has the first two right. DECISIONS, which the pitch is drawn from, does not.

### 2.4 M13: is the handling adequate?
**Process: yes.** The 0 % was reported, the rule change was declared post-exam, a new set was sealed before it was generated, generated blind, and scored once on a frozen tag. This is the right way to recover from a spent exam.

**What is still missing:**
1. The set-2 result is not filed (no M16, no report). It must be reported as it is: Danger catches 11/18 in heat waves with raw HR (person-bootstrap CI 25–79 %), **4/18 with HR scaling**, 3/17 on ordinary days, 6/27 on errands, median lead −2 min.
2. The price is not stated: 251 Danger onsets on 508 ordinary person-days, 247 of them false, so about **15 per wearer-month** on average (5.8 with HR scaling); 4.4 false per wearer-week in heat waves; roughly 6 % precision. In simulation nobody presses the button, so each one is a family call.
3. The rule's three evidence thresholds (NN logit ≥ 0, v1.2 z ≥ logit 0.10, 10-min slope) are DESIGN and were never swept.
4. Set 2 comes from the same simulator. It shows the rule generalises to new virtual persons, not that it is right for real ones.
5. **Set 2 is now spent.** Any further change to an alarm rule needs a third set or the label DEV.

### 2.5 Other points
- **"Until the band has learned her, it warns earlier"** is implemented as a threshold lowering of **0.018 °C** (`HG2_WATCH_LOWER_UNCAL`, `hg_unc.h`). True in code, meaningless in effect.
- **SEALED-OFFICE "0 alarms in 5.9 days"**: 5 subjects, about 1.2 days each, in sessions of roughly 85 min at 20–30 °C. Routine CHECK cannot fire (no clock). My inference, not verified: with a 20-min donning blank and 60 calm minutes needed for the personal baseline, the personal-relative DRINK path rarely arms in such short sessions. The zero is real but tests little.
- **HTT acceptance rows are DEV** and sit on the line: COOL 0.102 false/h (budget 0.10); Danger moved 0.086 → 0.096 with M13.
- **C == Python, 0 mismatching minutes** holds on the host build. The shipped ARM image differs (T6b B1).
- Member disagreement does not track error (informativeness 1.18 DEV, 1.23 sealed, target 2.0). M11 says so; keep it out of the pitch.

---

## 3. Claims audit

Labels: **REAL** = real people; **SIM** = supported only in simulation; **NO** = not supported.

| # | Claim the team could make | Status | Number and source |
|---|---|---|---|
| 1 | Core estimate within ~0.25–0.30 °C from heart rate on unseen people | REAL, young adults, v1.2 | 0.25 °C sealed, 13 people (CI 0.19–0.31); 0.29 LOSO. `/home/claude/hgmodel/REPORT.md` |
| 2 | Warns ~20 min before 38.0 °C | REAL, young adults, v1.2 | 18/21, median 20 min, 0.12 false/h, sealed. Same file |
| 3 | Frozen band logic on real chamber data | REAL, DEV | Drink 68/79 (86 %) at 0.080/h, lead 18 min; Cool 27/33 at 0.102/h; Danger 24/33 at 0.096/h. `guardian/FROZEN.txt` |
| 4 | New network is as good as v1.2 on real data | **NO** | 0.284 vs 0.261, CI excludes 0. `model/REPORT_MODEL.md`, T2 F2 |
| 5 | Network estimates core to 0.16 °C on unseen virtual elders | SIM | 0.160 / 0.173 / 0.184 °C now/+20/+30, sealed. `model/sealed_exam_hg2_DONE.json` |
| 6 | Network halves the HR-only error where it has skin, flux and air | SIM, DEV | 0.149 vs 0.342 °C. `REPORT_MODEL.md` |
| 7 | "NN beats v1.2 at the same false-alarm budget" | SIM, only ≤ 0.10/h | 90–98 % vs 22–59 % at 0.10/h; v1.2 equal or better at 0.15/h. T2 F1 |
| 8 | Network does not use the flux channel as a thermometer in heat | SIM | Flux-off changes core ≤ 0.10 °C (p99) at 34–37 °C. T2 P1 |
| 9 | "Drink water" catches 9 in 10 strain events in heat waves | SIM, sealed ×2 | 256/277 = 92 %, 337/361 = 93 % (raw HR); 87 % and 90 % HR-scaled. System DONE files |
| 10 | "Go somewhere cool" catches core-38.5 in heat waves | SIM, sealed ×2 | 17/18 both sets (Wilson 74–99 %). Cost: ~1.5 false COOL per day in a heat wave |
| 11 | DRINK stays within the nagging budget | **NO** | 3.65–4.0/day, 142–144 min/day vs ≤ 3 / ≤ 90 |
| 12 | Family is alerted at dangerous strain | SIM, weak | 0/18 (set 1); after M13 11/18 raw, 4/18 HR-scaled (set 2) |
| 13 | Family alerts are rare | **NO** | ~15 false Danger per wearer-month, mean (median wearer 0) |
| 14 | "Five models vote; when they disagree it warns earlier" | **NO** | Informativeness 1.18–1.23 vs 2.0. M11 |
| 15 | Every estimate has a calibrated range | SIM, on average | 85.0 % sealed for a 90 % interval; 19 % of persons < 80 % |
| 16 | Range shown on the band is honest for real people | REAL, young, DEV | ±0.58 °C covers 89.8 % of HTT minutes |
| 17 | "Warns earlier until it has learned her" | **NO** (0.018 °C) | `hg_unc.h` |
| 18 | Body Twin learns her core temperature | **NO** | +0.0025 °C median. M10 |
| 19 | Body Twin learns resting HR, calm baseline, routine, sleep window | SIM (rest HR within 4 bpm) | M10; `twin/results/sim_eval_v3.json` |
| 20 | Routine anomaly detection | SIM, untuned | 12/13 and 16/20; 11 false CHECKs per wearer-week |
| 21 | No alarms in ordinary office life | REAL, thin | 0 in 5.9 days, 5 sealed subjects (see 2.5) |
| 22 | The network can never silence a safety alarm | Supported on host | Property test, mutation-checked; 61/61 on frozen sources (T6b) |
| 23 | Band C code equals the Python reference exactly | Supported on host; **NO on the band today** | 0 mismatching minutes in both system exams; ARM image diverges (T6b B1) |
| 24 | The AI is tiny | Supported | Weights 26,900 B; AI total 60,527 B = 7.5 % of app flash; whole firmware 36 % |
| 25 | < 1 ms per inference; days of battery | **NO, estimates** | ×50 host scaling ≈ 1.3 ms; 2.1 mA → 4.2 days from a table. No board measurement |
| 26 | Simulator validated against published older-adult physiology | Partly | 28/47 rows, mandatory 11/17, every failure diagnosed. `sim/VALIDATION.md` |
| 27 | Sealed exams, run once | Supported | Section 1 |
| 28 | Tomorrow Engine gives a personal safe-hours plan | Runs end to end; SIM, unvalidated | 28 tests; T4 F1: indoor model reaches 43 °C, above any measurement |
| 29 | Validated on older adults / measures core temperature / detects falls / prevents deaths | **NO** | ARCH §2 guardrail |

### Claims sheet: the 12 strongest defensible one-liners

1. **"On 13 young adults the model had never seen, heart rate alone gave core temperature to 0.25 °C and warned 18 of 21 times, a median 20 minutes early."** REAL, sealed, young adults in a chamber. `hgmodel/REPORT.md`
2. **"The exact logic frozen into the band catches 86 % of 38.0 °C events on real chamber data at 0.08 false alarms per hour."** REAL, development data. `guardian/FROZEN.txt`
3. **"No recording of a person over 65 in heat exists that we could use, so we built 500 virtual elders from published physiology and published every place the simulator is wrong: it passes 28 of 47 checks, and each failure has a diagnosed cause."** `sim/VALIDATION.md`
4. **"We locked 100 virtual people away before any training, hashed the list, and scored them once."** `model/sealed_hg2.json`, git `1661242`, section 1
5. **"On those 100 unseen virtual elders the network estimates core temperature to 0.16 °C."** SIMULATION, sealed. `model/sealed_exam_hg2_DONE.json`
6. **"In simulated heat waves, 'drink water' fired before 92–93 % of strain events and 'go somewhere cool' before 17 of 18 dangerous ones, on two separate sealed sets."** SIMULATION. `guardian/sealed_exam_system_DONE.json`, `…_set2_DONE.json`
7. **"Our first sealed exam showed the family alert caught 0 of 18. We reported it, changed the rule, sealed 100 new virtual people and tested once more: 11 of 18, and only 4 of 18 when we remove the simulator's heart-rate bias. That tier is not solved."** SIMULATION. DECISIONS M13, set-2 DONE
8. **"On real data our neural network is not better than the simple heart-rate model, so the band keeps the simple model as a protected path, and a test proves the network can add an alarm but never remove one."** `REPORT_MODEL.md`; B5 property test; T6b 61/61
9. **"The band never shows a bare number: on real people its range is ±0.6 °C and covers 90 % of minutes."** REAL, young adults, DEV. `REPORT_MODEL.md`
10. **"The whole AI is 59 KB, 7.5 % of the chip's program space; the network itself is 27 KB."** `reports/B6b_guardian_report.md`, `tests/t6b/ai_flash_out.txt`
11. **"Our own tester ran the compiled firmware in an emulator and found a compiler flag silently disabling the heat alarms; we fixed it before it touched a wrist."** Say this only after the fix passes re-emulation. `tests/B6b_TEST_REPORT.md`
12. **"What we cannot claim: that it measures core temperature, that it works on older adults, or that it prevents deaths. Nothing we have is measured on a person over 65 in heat."** ARCH §2

Wear-test lines (sensor behaviour, contact check, real false alarms per day, battery) are added only after Nov 18, with n = 1 and the wearer's age stated.

---

## 4. Red team: ten questions from a judge who knows ML and physiology

**1. You have no data from anyone over 65. Why should I believe any of this applies to them?**
You should not, for accuracy. Real evidence is young adults in a chamber. The elder-specific part is a simulation built from published older-adult measurements, and is labelled so everywhere. What the project shows is a method and a device ready for a real older-adult study.

**2. You trained on your simulator and tested on your simulator. Isn't that circular?**
Yes. The sealed sets prove the network generalises to virtual people with unseen parameters, nothing more. That is why the heart-rate model validated on real people stays a protected path, and why the simulator's known errors are listed.

**3. Your simulator fails 6 of 17 mandatory checks. Why train on it?**
Each failure is traced: resting older adults tolerate about 1 kPa more humidity than measured, resting HR at 36 °C is 86 against 74 bpm, bed rest warms +0.7 against +1.1 °C. These mostly make the simulator too forgiving, so a model trained on it would under-warn; the measured environmental limit lines therefore fire independently of the network. Our tester also found one bias the other way (simulated homes get hotter than any measured Athens home).

**4. Does the neural network beat the Kalman filter?**
On real data, no: 0.284 against 0.261 °C on the same minutes. In simulation, where it also sees skin temperature and air, it halves the error (0.15 against 0.34 °C) and gives better alarms only at tight false-alarm budgets. Whether that survives contact with real wrists is unknown.

**5. A wrist cannot give core temperature. What is the second temperature sensor for?**
Agreed, and the documents say so. The flux term only carries information below about 31 °C room air; in a hot room the gradient collapses. A test confirms the network does not lean on it in heat (switching it off moves the estimate ≤ 0.10 °C at 34–37 °C). The product is the strain warning, not the number.

**6. How often does it nag?**
In simulation, 3.65 to 4 "drink" prompts and about 140 minutes of prompt per ordinary summer day on the median wearer. Our budget was 3 and 90. We missed it. About one prompt in six precedes a real event.

**7. How often is the family called, and how often for nothing?**
The family tier catches 11 of 18 dangerous events in simulated heat waves, 4 of 18 under the more realistic heart-rate assumption, and on average fires about 15 times a month falsely on ordinary days, concentrated in a minority of wearers. Every one first asks "are you OK?" and a button press cancels the call; the simulation has nobody pressing. This is the weakest part.

**8. You call it an ensemble of five. Does disagreement mean anything?**
No. Error in the most-uncertain fifth of minutes is only 1.2 times the least-uncertain fifth; we wanted 2. The range covers 85 % of unseen simulated minutes for a nominal 90 %, and 19 % of virtual persons get under 80 %. The band shows a wider range fitted on real data, ±0.6 °C.

**9. You changed the Danger rule after seeing sealed results. That is tuning on the test set.**
It would be if we had reported the second number as the first. We published the 0 %, declared the first set spent, sealed a new set before generating it, and ran once. Both results are in the repository with commit times.

**10. Does this run on the chip, or only on a laptop?**
The code compiles to 296 KB and matches the Python reference minute for minute on a laptop build. Our tester showed the microcontroller build did not, because of a compiler flag; [state the fix result]. Inference time and battery life are estimates until measured on the band.

Likely follow-ups: beta-blockers (heart-rate paths weaken; only a threshold margin compensates, unvalidated); what a 3-day test on one healthy young wearer proves (sensors, contact check, false alarms, firmware; nothing about elders or heat).

---

## 5. Highest-value work before Nov 29, ranked by effect on winning

1. **Get correct firmware onto the wrist by Monday.** Land the fast-math fix for 09 **and** 08, re-run T6b's ARM emulation against the golden (expect 0 differences) and T6a on the edited 08. `08_logger` was GO at v1.1.1 and now has uncommitted changes four days before the wear test: keep the tested v1.1.1 `.uf2` as the fallback. No wear data means no real-hardware evidence at all.
2. **Make the wear test produce claims, decided before recording.** `tests/wear_exam.py` does not exist and there is no `wear-freeze` tag. Write the protocol now: labelled events (loose, off, shower, outdoors, a warm room, stairs), a reference HR (chest strap or watch) for PPG error, oral readings, nights 1–2 as dev for the sleep/quiet thresholds and night 3 as the test. Then replay the logs through the frozen host build for real false alarms per day. If any relative over 65 can wear a second logger for even one ordinary day, do it: one real older wrist changes the pitch more than any further simulation.
3. **Write the submission around section 3, and file the results.** One sealed-results report with all three DONE files as they are, including the missed budgets; an M16 for set 2; amend M11's three statements; ARCH §2 verbatim in the draft. Lead with the method and the failures you found yourselves (claims 3, 4, 7, 8, 11). Remove "five models vote", "learns her body temperature" and "warns earlier until it has learned her".
4. **Stop tuning alarms on the simulator.** Both sealed sets are spent, and the family tier's problem (resting older hearts do not race) will not be fixed by another threshold. Present it as the open problem and the reason a real study is the next step. If one change is made, pre-register it and seal a third set first.
5. **Close the review gaps cheaply:** an independent test of the Guardian Loop (none exists), a short T1 pass on sim v4, ARCH §7.2 rewritten to match the frozen build, stale labels fixed, the history rewrite and the pre-exam script edit noted in DECISIONS.
6. **Demo:** dashboard replay of the real wear day beside the simulated heat-wave day, board timing (DWT) and a measured battery curve, the 72 h soak. These turn claim 25 from an estimate into a measurement.
