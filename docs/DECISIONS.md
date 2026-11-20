# Manager decisions (binding; ARCHITECTURE wins otherwise)

## M1 (Nov 12) — Alarm fatigue: B5 findings 1–3
Principle: a band that says "drink water" 19 h a day is ignored and taken off. Silence when calm is a safety feature.
1. **WHO 24 °C night rule is NOT a tier trigger.** It sets the `night_heat` flag (screen icon + one bedtime nudge «Δροσίστε το δωμάτιο» max once per evening) and feeds Tomorrow Engine. DRINK/COOL fire only from the body/strain paths and the PSU environmental-limit path.
2. **RH is clamped to the v1.2 training range [38, 60] % inside the v1.2 linear correction only** (the physics/env paths use true RH). Reason: extrapolation outside the fit range is not evidence.
3. **Margins do not stack beyond +0.20 °C total** (older + medication + uncertainty-lowering combined, cap 0.20 °C on the watch tiers). Reason: each margin was sourced alone (Kenny 2017 0.2 °C; meds 0.1 °C); their sum was never measured.
4. **Acceptance budgets (hard):** in S1 (ordinary summer week) DRINK ≤ 1 episode/day and ≤ 60 min/day on the median SIM-DEV person; COOL ≤ 1/week; CHECK ≤ 1/wearer-week; in S2 (heat wave) DRINK sensitivity to ev38 ≥ 85 %. If budgets and sensitivity cannot both be met, report the trade-off curve and stop — the manager decides.

## M2 (Nov 12) — Virtual Elders v1 failed 8 of 18 must-pass rows
1. **B2 starts now on sim v1, labelled PROVISIONAL.** It builds and debugs the full pipeline (features, training, export, C golden). Final training re-runs on sim v2. Every B2 artefact records the SHA-256 of the minutes_dev.parquet it trained on.
2. **B1 calibration round 2** targets V13/V15/V16/V18 (older Rest limits too tolerant — the model does not reproduce PSU's flat ~3.5 kPa Rest line), V7 (no lying-posture term; a sourced posture/clothing/bedding term is allowed), V19 (HR-lead window), V4. Tolerances do not change.
3. **V27 (day-2 escalation) moves from must-pass to "documented limitation".** The heat-debt ban stays: the only evidence is n = 4 workers (Meade 2017). Every multi-day number is reported as "extrapolated multi-day; day-2 escalation not represented".
4. **If round 2 cannot satisfy a row without violating another must-pass row**, B1 stops on that row, reports the trade-off with numbers, and the manager picks. No row is passed by editing a tolerance or a target.
5. R2's "ΔT ≤ 0.6 °C at ≥ 34 °C" is corrected to the regime B1 derived from R2's own physics (holds from ≈ 38 °C); B2's flux-off permutation test runs at T_air ≥ 37 °C and also reports 34–37 °C separately.

## M3 (Nov 12) — Freeze Virtual Elders v2 as the training simulator
Setting chosen: frame 1.6, rest factor 0.85 (V2, V12, V15, V18 pass). Must-pass 12/17; 30/46 overall. Further two-node tuning is stopped: the remaining failures are structural (B1 traced them minute by minute).
**All residual biases point the same way — the simulator is too tolerant, so a model trained on it would under-warn:**
- V13/V16: resting older adults in humid heat survive ~1 kPa longer in the sim than in PSU (skin warming adds dry heat loss once ω hits its cap).
- V4: sim HR at 36 °C rest 86.5 vs 74 measured → the NN would expect more HR rise per unit strain than a real older heart shows → under-reads real strain.
- V7: bed rest at 31 °C +0.71 vs +1.1 °C measured (no sourced mattress-contact term exists).
Mitigations (binding):
1. **The safety rules that do not depend on the NN stay OR-paths and are never suppressed by it**: PSU measured Rest/ADL environmental lines (R1 trial fits, D6), the v1.2 logistic Danger, the behaviour path. B5 adds a property test: NN output can only lower thresholds / add alarms, never remove an env-path alarm.
2. **B2 augments HR**: during training, scale each sim person's HR rise above rest by U(0.6, 1.0) (domain randomisation toward the measured 74 bpm), and reports SEALED-SIM metrics both with and without augmentation.
3. **Night**: because V7 under-reads bed rest, the Tomorrow Engine's night-heat flag and the bedtime nudge (M1.1) are the night defence; reported as such.
4. V19: accepted — median lead 3.1 RH points matches R1; the ±8-point person spread is reported as real variability, not tuned away.
5. Every SIM number in reports carries "SIMULATION (Virtual Elders v2; known too-tolerant at humid rest, bed rest, and HR)".

## M4 (Nov 12) — Body Twin
1. The flux-constant rule stays as written but is **renamed "capped gap gain"** everywhere (code comments, reports, pitch). It does not learn K; K is not recoverable from oral readings (corr 0.17). Never call it K in the pitch.
2. **β (same-day reading weight) = 0.25.** Real HTT data prefers it 2:1 over 0.35; sim cost 14 %. Frozen before wear-freeze.
3. **Oral → core correction**: oral readings are biased low vs core; an uncorrected −0.3 °C bias turns the gain negative. B3 adds a sourced oral-to-core offset (cite it) applied before learning; if no solid source, readings feed only the display, not learning.
4. **F10: readings are ignored for learning while any alarm tier is on** (and for 30 min after).
5. The sleep-stillness threshold (0.002 g) is NOT tuned on the simulator; it is set from the wear-test recordings (dev nights) before wear-freeze. B1 checks sim accel noise against R2 §6.
6. Twin acceptance on SIM is reported as measured (+0.005 °C median, SIMULATION) after sim v3; the honest pitch line is "personalisation matters for the offset on the day of a reading", not "the band learns your body temperature".

## M5 (Nov 12) — hg2 results on HTT + SIM v2 (pipeline debug)
Facts: on real young-adult data (HTT, HR only) hg2 = v1.2 (MAE 0.283 vs 0.29); its Danger/Drink logit paths add nothing at the 0.10 FA/h budget; ensemble sd does not track error (coverage 55 %, informativeness 1.0×); the error is per-person.
1. **D7 is replaced.** The watch tier uses f20 (no "+1·sd"): 87 % at 0.139 FA/h on HTT dev, within the ≤ 0.15 budget. Uncertainty is no longer "models disagree → warn earlier" (not supported by data).
2. **New uncertainty rule (honest version): split-conformal per-person interval.** Calibrate the ±range on DEV persons held out from training (B2 splits SIM-DEV 300 train / 100 calibration persons; HTT by LOSO), conditioned on Twin state: "no same-day reading" (wide) vs "reading today" (narrow). The band shows the range; the watch tiers lower their threshold by min(0.10 °C, half the excess width) while uncalibrated (no reading yet). Sealed-SIM checks coverage once.
3. NN Danger/Drink logit cuts stay OFF unless SIM-DEV v3 (S2/S3 scenarios, with flux + skin channels HTT lacks) shows a gain at the same FA budget; B2 reports that test. The NN core estimate + range is still what the band and the phone show.
4. Pitch consequence: drop "five models vote and when unsure it warns earlier". Replace with "every estimate comes with a calibrated range; until the band has learned her, it warns earlier".
5. B5 re-baselines the 10 crafted traces whose expected states came from the stub, against model/export, with a diff of each changed expectation and its reason.

## M6 (Nov 12, Foivos: "make it identical to the pitch, try harder") — supersedes M5.4
The pitch line stays: "five models vote; when they disagree it warns earlier". We make it TRUE, measured, not asserted.
1. **Body-hypothesis ensemble.** The error is per-person (mesor, axial drop, κ), so members must disagree exactly where persons differ: each member trains on a different person-parameter stratum mix (e.g. κ low/high, axial drop low/high, mesor low/high, beta-blocker, frail), all members see all scenarios. On a new wearer they disagree until the Body Twin pins her down — disagreement then *is* "I don't know her body yet".
2. **Heteroscedastic heads**: every member outputs mean + log-variance (Gaussian NLL) so loose band / flux invalid / noisy HR widen the range per minute. Total sd = sqrt(mean aleatoric + between-member variance).
3. **Acceptance (hard, SIM-DEV calibration persons, then SEALED-SIM once):** informativeness = MAE in the top-sd quintile ÷ MAE in the bottom quintile ≥ 2.0; coverage of ±1.645 sd 85–95 % WITHOUT a post-hoc scale; f20_eff = mean + 1·sd restored on the watch tiers IF Drink FA/h ≤ 0.15 on HTT dev at ≥ 85 % sensitivity; otherwise the sd coefficient is the largest that meets the budget (reported).
4. **"NN beats v1.2"** is tested where the NN has its extra senses (skin T1, flux, air, motion): SIM-DEV v3 S1–S4, at the same FA budget. On HTT (HR only) the target is "not worse". If either fails, the number is reported as it is — results are never faked; the build keeps going until it passes or the manager decides.

## M7 (Nov 12) — DRINK fires ~7×/day on SIM-DEV v2 (precision 11 %)
Diagnosis inputs: v2 had no night sleep (persons awake all night → extra minutes/CHECKs); sim HR runs high (V4 +12 bpm) so the v1.2 HR anchor reads high on sim; resting older f20 sits 0.06 °C under an absolute line.
1. **Re-measure first on v3** (real nights) and with the M3.2 HR-rise scaling applied to the sim HR fed to the band (sensitivity analysis for the V4 bias). Report both.
2. Then evaluate three designs behind flags, on v3, same budgets (M1.4):
   - **A personal-relative line**: DRINK when f20 − her own learned calm f20 (Twin, resting daytime median, bounded) ≥ Δ, with Δ chosen so S2 sensitivity ≥ 85 %; the absolute 38.0-anchored line stays as a ceiling (always fires above it).
   - **B nudge, not state**: DRINK is a one-shot nudge (vibrate + screen 10 min) with a 2 h refractory unless the forecast keeps rising by ≥ 0.1 °C; COOL/DANGER stay states.
   - **C = A + B.**
3. Routine CHECK: evaluate on v3 nights first; then the quiet rule uses per-person learned buffers (R3 GE method) and is suppressed in the learned sleep window; target ≤ 1/wearer-week on S1, S9 sensitivity ≥ 90 %.
4. Pick rule: the design with the highest S2 sensitivity that meets all S1 budgets; if none meets them, report the curve, I decide. Thresholds that cannot be validated on real data get frozen at wear-freeze and labelled "set in simulation".

## M8 (Nov 12) — Virtual Elders v4 = v3 + the three HR/detection bug fixes
Adopt HR_AMB_SPAN = 14, HR_AMB_TAU = 5 min (design choice, Rowell 1974 qualitative — labelled as such), HR_PLATEAU = pre_ramp; local vasodilation OFF (it breaks V19 humid and the dry limit). V19-dry goes from HR-lags (−5.8 °C) to HR-leads (+1.2 °C median, 61 % of persons; target 80 % → still FAIL, documented). These are bug fixes, not tuning: the old formula cancelled HR above 36 °C, outside the Meade range it came from. B1 regenerates *_v4.parquet once with a full validation run; B2's FINAL ensemble trains on v4. v3 stays for comparison.

## M9 (Nov 12) — DRINK/CHECK design picked
1. **Adopt design A, Δ = 0.30 °C (personal-relative DRINK line), labelled "set in simulation".** Only design keeping S2 ≥ 85 % (86.0 % raw HR). S1 median: 2.5 DRINK/day, 86 min/day.
2. **M1.4's S1 DRINK budget is revised, with the reason on record:** ≤ 3 nudges/day and ≤ 90 min/day on hot S1 days. Reason: EODY/WHO heat advice for 65+ is to drink regularly through hot days; 2–3 well-timed reminders on a 30–33 °C day match public-health advice. COOL ≤ 1/week and CHECK ≤ 1/week are unchanged (COOL measured 0/week).
3. **M7.3: keep part (i)** (DRINK no longer freezes routine learning), **drop part (ii)** (±60 min sleep-window suppression hid anomalies: S9 89.7 → 76.9 %).
4. **Routine CHECK is not tuned on the simulator.** v3/v4 wrist z-angle during sleep is noisier than awake (sim artifact), so sleep detection fails on sim. No sim regeneration for this (would destabilise the training set). The quiet-rule and sleep-detection thresholds are set on the real wear-test nights (dev) before wear-freeze; the reported CHECK rate is "measured on N real nights", not simulated.
5. The calm-f20 baseline for design A is persisted in the Body Twin save file (B3), not guardian RAM.

## M10 (Nov 12) — What "Body Twin learns her" honestly means
Sim v3: learning offsets/K improves the core estimate by ~0 (+0.0025 °C median); readings that learn hurt (29 persons worse). Display-only stays. The Twin's real, measurable personalisation is: (1) her resting HR (within 4 bpm of truth, SIM), (2) her **calm-f20 baseline that drives the personal-relative DRINK line (design A, M9)** — this is what cuts nagging while keeping 86 % sensitivity, (3) her routine profile, (4) her sleep window. The pitch "learns her body" is backed by (1)–(4), never by "learns her core temperature". Final testers re-run T3 against file format v3.

## M11 (Nov 12) — hg2 final (sim v4) accepted for integration
- Accepted: coverage 88.5/91.4/90.9 % with no post-hoc scale (PASS); NN beats v1.2 on SIM-DEV v4 at the same FA budget (Drink 98–99.5 % at 0.10–0.17/h vs 88–95 % at 0.31/h; SIMULATION); HTT dev = v1.2 (0.284 vs 0.29).
- **Not met, reported as-is:** sd informativeness 1.18 (target 2.0; ceiling from these inputs ≈ 1.6, sim errors are uniform across situations); member disagreement does not track error. **The pitch line "when the models disagree it warns earlier" is NOT supported and is not used.** The supported uncertainty claims: a calibrated range (88–91 % coverage on unseen simulated people) and "until the band has learned her, it warns earlier" (M5.2, conformal widths HG2_CONF_HALF_UNCAL/CAL).
- HTT Drink with NN f20 (k = 0): 86 % at 0.174/h > 0.15 budget. **Watch tier on HTT-like exertion uses the protected v1.2 f20 path; the NN path adds where it has extra senses.** B5 implements: DRINK = A-relative line on NN f20 OR v1.2 f20 above the absolute ceiling; out-of-distribution guard: when hr_reserve > 0.6 or HR > p99 of training (108 bpm), use max(NN, v1.2).
- Next: B5 integrates the 32-24-16-9 export → freeze → manager runs the sealed exam once → B6b 09_guardian → final testers + independent Fable review.

## M12 (Nov 12) — HR-only v1.2 DRINK path needs heat context
Confirmed: 5-min valid gate for the HR-only v1.2 path (recorded in FROZEN.txt). DRINK excess on v4 is 52 % v1.2-ceiling-only onsets during chores/meals in 28 °C rooms (not heat). Decision: the v1.2 ceiling path counts for DRINK only with heat context = (corrected room air ≥ T_ctx) OR (air above the PSU older-adult line) OR (OOD guard active). Evaluate T_ctx ∈ {28, 29, 30} °C on v4 DEV (150) + HTT dev; pick the lowest T_ctx meeting DRINK ≤ 3/day & ≤ 90 min/day (raw HR) with S2 ≥ 85 %; if none, the one with best S2 within budget — report, I confirm. COOL/DANGER paths unchanged (never gated by context). Also integrate B2's fix commit 0978398 (guards, REAL conformal widths with max(1.645·sd, REAL), OOD guard) before re-freezing as tag `hg2-freeze-2` with a fresh FROZEN.txt hash.

## M13 (Nov 12) — Sealed results + the Danger gap
Full-system sealed exam (SEALED-SIM v4, 100 held-out persons, run once, C == Python 0 mismatches; SEALED-OFFICE 5 real subjects, 5.9 days):
- DRINK 84–92 % (raw HR), COOL catches 94 % of core-38.5 events in heat waves (S2) and 86 % in POST; DANGER (family path) ~0 % in every class; routine S9 12/13; CHECK 7/wk + routine 11/wk (untuned, M9.4); office: 0 alarms of any kind in 5.9 real days.
- Reading: at 38.5 °C the wearer IS warned (COOL), but the family is never called, because Danger paths need a racing heart (v1.2/NN) or stillness + no button (behaviour). Older bodies at rest don't race (the product's own premise).
Decision:
1. **Danger by persistence**: COOL on for ≥ X min AND f20 not falling (≥ 0) AND (env above PSU line OR NN P385 high OR v1.2 z high) → «Είστε καλά;» CHECK → family after 5 min without a press. X ∈ {20, 30, 45} tuned on DEV only (ev385 sensitivity vs CHECK/Danger per week on S1/S2).
2. **Fresh exam set**: the first sealed set is now spent for Danger design. B1 generates **SEALED-SIM-2: 100 new virtual persons, ids 500–599, seed 20261113**, from the same frozen distributions and simulator v4, sealed by the manager (hash of ids + seed + generator commit) BEFORE generation; nobody opens it until the freeze-3 system exam.
3. Disclosure: the first sealed results are reported as-is (incl. Danger 0 %); the persistence rule is a post-exam design change validated only on SEALED-SIM-2.

## M14 (Nov 12) — 09_guardian size
Flash 36 % (296 KB) vs the 30 % pitch target. Keep USB console (needed for soak + wear test) and the full screen driver. Pitch wording becomes: "the AI (network + guardian + twin) is ~10 % of the chip; the whole firmware about a third" — B6b reports the exact AI-only byte count. 09 is rebuilt from tag hg2-freeze-3 once M13 lands, then tested (T6b) before any flash.

## M15 (Nov 12) — Danger persistence X = 20 min confirmed
X = 20 (best ev385 sensitivity: family 27.8 → 43.1 % SIM-DEV raw; HTT Danger unchanged 72.7 %, FA 0.086 → 0.096/h). Budget read on the median wearer (0/month for all X), consistent with every other S1 metric; the MEAN (8.4/month, driven by a minority) is reported alongside, every time. Each Danger first asks «Είστε καλά;» — a press stops the family call. Then: SEALED-SIM-2 system exam, run once.

## M16 (Nov 12) — Amendments after the independent review (review/FINAL_REVIEW.md)
1. **M11 amended:** on real data (HTT, identical minutes) hg2 is WORSE than v1.2: 0.284 vs 0.261 °C (CI excludes 0); on the 13 unseen-by-v1.2 people 0.259 vs 0.244 (n.s.). "= v1.2" and "NN beats v1.2" are withdrawn. NN advantage is SIMULATION-only, at strict FA budgets (≤ 0.10/h).
2. **Sealed numbers are the only headline numbers.** Coverage claim = 85.0 % (sealed set 1), not the DEV 88–91 %. Family tier (set 2): 11/18 raw, 4/18 HR-scaled; ~15 Danger CHECK episodes per wearer-month (each asks «Είστε καλά;» first).
3. **DRINK budget missed on both sealed sets** (3.65–4.0/day, ~143 min/day vs 3/90). Recorded, not re-tuned: both sealed sets are spent; no more alarm tuning on the simulator. The real rate comes from the wear test.
4. "Five models vote" and "warns earlier until learned" (0.018 °C) are NOT pitch claims.
5. Pitch claims come only from review/FINAL_REVIEW.md's claims sheet.
6. Next: fast-math fix (B6) → re-test; wear_exam.py + protocol + `wear-freeze` before recording; Guardian Loop and dashboard testers; submission draft from the claims sheet.

## M17 (Nov 12, Foivos: "no stopping until it's perfect; invent something new") — Round 2 of research + invention
Weak spots (M16): NN worse than v1.2 on real data; family tier weak; DRINK nags; zero 65+ time series. Plan:
1. **R5 (Fable): hunt REAL older-adult heat time series** (core + HR + skin, per-minute) — PSU HEAT, Kenny HEAT lab (Ottawa), Meade/Notley/Flouris, home-monitoring pill studies, supplements, OSF/Figshare/Zenodo/PhysioNet/Dryad. Download what is open. This is the single highest-leverage item: it turns SIMULATION claims into real ones.
2. **R6 (Fable): invention** — apply Foivos's Talzin methods (exceptions/drift-only detection, momentum, multi-source agreement, calibrated two tiers, sealed exams, "every failure has a why") to the weak spots; candidate new idea: a **personal heat-response fingerprint learned from everyday natural experiments** (each warm afternoon/chore/shower is a small perturbation; fit her own HR/skin response per unit heat load → personal κ and limit → personalised Danger/Drink). Spec + feasibility + a test plan.
3. **SEALED-SIM-3 sealed now** (ids 600–699, seed 20261114, model/sealed_hg2_set3.json) for any new method; generated blind only after the method freezes.

## M18 (Nov 12) — REAL older-adult data found (R5) and sealed
- Brighton/Waldock (CC BY-ND 3.0): 10 people aged 65–76 at 35 °C/50 % RH, rectal + HR + 4 skin sites + ambient every 5 min, 3 sessions each — the only real 65+ core series. **P2–P10 sealed as the REAL 65+ exam**; P1 + summary sheets (seen by R5) are DEV. Derived tables stay internal (ND licence).
- HeatIN Montreal 2025 (CC BY 4.0): ~3.5 M watch-minutes of real older-adult wrist PPG HR + near-wrist temp + motion + room T/RH. **Half the watches sealed** (seed 20261115) as the REAL false-alarm/routine exam; the other half DEV.
- Seal file: model/sealed_real_older.json (hashes of both source files). Kenny-lab 8-h data: email drafted (R5) — needs an adult in CC.

## M19 (Nov 12) — Invention results (R6) adopted
1. **Marble Danger** (main variant, research/R6_invention.md §8) replaces the M13 persistence rule: Danger = v1.2 logistic OR behaviour OR Marble (5 EWMAs incl. leaky heat mass, linear score ≥ cut for 5 min, armed only if room ≥ 28 °C in the last 60 min; 22 B RAM). DEV: heat-wave core-38.5 caught 49/63 at ~5.5 false/wearer-month (raw and HR-scaled) vs frozen 29/63 / 20/63; low-κ third (the silent-heart group — the product's premise) 22/37 vs 5/37. Chosen over the conservative variant because the low-κ group is the point. Known risk: movement term unbounded in warm rooms → the REAL HeatIN exam (older adults at home) is the check on that.
2. **Exception DRINK** adopted (her forecast vs her own usual rise for this much movement, learned in rooms < 30 °C; 2 h quiet after a nudge): DEV 4.0 → 3.0/day, 119 → 78 min, heat-wave sensitivity 93 → 89 %.
3. **Personal heat fingerprint (κ recovery) FAILED** (corr 0.05–0.24): the wrist reports skin blood flow, not core, at ordinary temperatures. Kept in shadow mode on the wear test only. Reported as a negative result with its why.
4. Disclosed: on DEV persons the NN never saw, Marble 8/20 vs frozen 7/20 (raw) — the headline is optimistic; SEALED-SIM-3 decides.
5. Order: B5 (after T5 fixes) builds Marble + Exception DRINK → freeze-5 → manager runs SEALED-SIM-3 (generated blind after freeze) + the two REAL older-adult exams (M18), each once.

## M20 (Nov 13) — Real older-adult exams on freeze-5, then sim v5 + freeze-6
1. REAL exams run once on hg2-freeze-5: Brighton (65–76, chamber) hg2 MAE 0.448 / bias −0.35 FAIL, v1.2 0.232 PASS, coverage 76.8 % FAIL, DRINK 7/7 rectal ≥ 38.0 at ~21 min lead PASS, DRINK unconfirmed 0.56/h FAIL; HeatIN (17 sealed watches at home) variant A H1–H4 all PASS. Reported as they are, for freeze-5 only.
2. Diagnosis (B2b, DEV): the NN acted as a skin thermometer; sim v4 made the skin–core gap too uniform. Sim v5 (f055fcb) adds per-person skin coupling, fitted on Brighton → **Brighton is calibration from now on, never held-out for any later version.**
3. freeze-6 = Core Sense retrained on v5 + v1.2 anchor with bounded NN residual (−0.30 / +0.50 °C). Wider display range accepted (0.605 / 0.688 °C) — honest over narrow; display only, no held-out coverage claim.
4. SEALED-SIM-3 (v4) retired unopened; SEALED-SIM-4 (v5, ids 700–799) sealed before v5 generation and scored once on freeze-6.
5. Fresh real 65+ proof needs a data request (R7: Ottawa Kenny/Meade, VU Daanen).
