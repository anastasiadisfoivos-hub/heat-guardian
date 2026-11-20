# B2b — the low reading on older adults: diagnosis, sim v5, retrain, v1.2 anchor + bounded residual (Nov 13 2026)

Labels: SIM = SIMULATION; HTT = REAL young adults; Brighton = REAL 65–76, CALIBRATION (the exam is spent and it was used to fit sim v5; never held-out). DEV and calibration data only; no sealed SIM file (sets 1–4) and no HeatIN sealed watch was read. Numbers: `model/runs/b2b/` (freeze-5 analysis), `model/runs/b2b_v5aug/` (v5), `sim/VALIDATION_v5.md`.

## 1. Why freeze-5 read low (sealed Brighton bias −0.35 °C)
- With a skin reading present, the NN acted as a skin thermometer: 0.53 °C per °C of skin, 0.05 °C per 10 bpm.
- The v4 sim's insulated T1 sits at core − 0.82 °C with IQR 0.25 °C, above the air.
- Real 65+ skin (Brighton bicep) sits 1.55 °C below rectal and below the air; 88 % of minutes were outside the training envelope.
- So the NN followed only 27 % of the cycling core rise.
- HTT has no skin channel, so the real fine-tune could not correct this.
- Root cause in the sim: v4 made the skin–core gap far too uniform between people (SD 0.26 vs 0.43 °C real). Rest-phase body heating was within protocol uncertainty.

## 2. Changes
1. **Sim v5** (f055fcb): per-person skin–core coupling (SD 0.36 °C, plus 0.35 °C extra at the wrist). Energy balance untouched. DEV-only generation.
2. **Retrain** on v5 with the same pipeline and HTT fine-tune (CRC 0xEE4F7E9E, 26,900 B).
3. **v1.2 anchor + bounded residual**, in guardian C and Python: core = v1.2 + w·clamp(NN − v1.2, −0.30, +0.50).
   - The NN's weight w is 0 with no valid skin reading, outside the v5-training skin−air envelope (0.5 °C ramp), or under the existing HR out-of-range rule.
   - The −0.30 bound was fixed in advance. +0.50 was chosen on SIM-DEV v5: it beat +0.30 on every sensitivity row at equal false alarms.

## 3. Before / after

**Core MAE / bias (°C)**

| Data | freeze-5 | v5 NN alone | v1.2 alone | freeze-6 |
|---|---|---|---|---|
| Brighton | 0.448 / −0.35 (sealed P2–P10) | 0.326 / +0.07 | 0.279 / +0.23 | 0.277 / +0.17 (P1–P10, calibration) |
| HTT, LOSO | 0.284 / +0.04 | 0.280 / +0.04 | 0.261 / 0.00 | 0.261 / 0.00 |
| SIM-DEV v5 | — | 0.195 / −0.01 | 0.342 / +0.22 | 0.234 / +0.08 |

**Brighton details**
- Share of samples reading more than 0.3 °C low: v5 NN 15.2 %, v1.2 1.8 %, freeze-6 5.5 %.
- Cycling rise followed (real +0.51 °C): v5 NN 74 %, v1.2 89 %, freeze-6 95 %.

**Gains:** skin gain on SIM hot rows / Brighton is 0.53 / 0.51 for freeze-5 and 0.17 / 0.15 for v5. HR gain on SIM hot rows stays 0.045 °C per 10 bpm, so HR comes in through the v1.2 anchor.

**SIM-DEV v5 alarms, 150 persons, raw HR (HR-scaled)**

| Metric | freeze-5 binary | freeze-6 |
|---|---|---|
| S2 core-38 DRINK display | 86.2 (83.3) % | 84.9 (80.9) % |
| Core-38.5 Danger catch | 58.3 (47.2) % | 55.6 (47.2) % |
| Low-κ group: S2 display / core-38.5 caught | 82.4 % / 7 of 10 | 81.8 % / 7 of 10 |
| DRINK per day / min (median) | 3.5 / 78 | 3.0 / 66 |
| Danger per wearer-month (mean) | 8.7 | 8.6 |

**HTT DRINK / COOL / Danger caught:** 68/79, 27/33, 24/33 for freeze-5; 69/79, 27/33, 24/33 for freeze-6. False alarms are identical.

**Range:** REAL half-widths 0.605 / 0.688 °C (90 % of freeze-6's error, Brighton as calibration). Leave-one-person-out coverage: 89.8 % of all minutes; 85 % (now) and 80 % (+20 min) for Brighton people. No held-out claim. Manager accepted the wider range (M20.3).

## 4. Integration
- Code: AR block in `guardian/c/hg2_step.c`; constants `HG_AR_*` in `guardian/c/hg_guardian_cfg.h`; the Python mirror is identical.
- C == Python: golden 0.0, parity_m7 0, parity_sim_long 0 of 115,200 minutes, fastmath 0 of 1,143.
- Host tests 73/73 after re-baselining 8 traces (`REBASELINE_B2b_v5.txt`): 6 move one minute earlier; Marble Danger comes earlier and lasts longer.
- 09 compile: 302,320 B flash (+1,216 B), 68,776 B RAM (+0).
- FROZEN.txt prepared for hg2-freeze-6. The HeatIN and R6 rows in it are freeze-5 numbers, not re-run.

## 5. Risks and proof
- **Risks:** no held-out real 65+ number (Brighton is calibration); the NN still under-uses HR; SIM DRINK display −1.3 points and Danger catch −2.7 points vs freeze-5; envelope and +0.50 bound set in simulation; Virtual Elders fails at 4–7 met exercise.
- **Proof:** SEALED-SIM-4 (once, after the tag); R7's real 65+ dataset (data request); the wear test (real wrist skin−air vs the envelope).
