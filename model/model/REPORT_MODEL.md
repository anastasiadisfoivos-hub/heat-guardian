# hg2 Core Sense — model report (B2 final, v4aug; filed by the manager from B2's final message, commit 0978398)

Weights CRC 0xB32FA3CA (unchanged by the fix round); weights JSON SHA e00eb0073ccccf2bf6bc541180b3fc0d61d2f7792e3b9997a77efe0e13768bbd. Net 32-24-16-9 ×5 (6 outputs + 3 range heads), 26,900 B; poc_02_hg2 73,884 B. Board timing not measured.

## What it is
Insulated wrist temperature + small flux term (<31 °C air) + v1.2 HR Kalman anchor + air T/RH, fused by a small network, personal constant learned on the wearer, every number with a range. NOT a wrist core thermometer. Members over-weight body types: low κ, high κ, large axial drop, high core baseline, frail/β-blocker (no flux). Trained on minutes_dev_v4 (2bce61d1…), HR augmentation M3.2, persons 270 train / 30 early-stop+range fit / 100 calibration (scored once). Thermal pathway is SIMULATION only (masked on HTT).

## SIM-DEV calibration persons — SIMULATION (Virtual Elders v4; known too-tolerant at humid rest, bed rest, HR)
MAE now/+20/+30 0.149/0.159/0.171 °C (v1.2 alone 0.342); per κ tercile 0.150/0.145/0.152; P38 AUC 0.949, P385 AUC 0.974 (8 persons with events). Coverage ±1.645 sd 88.5/91.4/90.9 % on average; 19 % of persons < 80 %; person-level corr(sd, MAE) −0.02. Informativeness 1.18 — FAIL (target 2.0; ceiling from inputs ≈ 1.5–1.7). Flux-off test pass (real pass at 34–37 °C, p99 0.10 °C). Sign checks pass.

## HTT (young adults 18–33, chamber walk; identical minutes)
| People | hg2 | v1.2 | diff (95 %) |
|---|---|---|---|
| all 65 (v1.2 fit on 52) | 0.284 | 0.261 | +0.024 (+0.012..+0.036) |
| 13 unseen by v1.2 | 0.259 | 0.244 | +0.015 (−0.004..+0.032) |
Verdict: not better than v1.2 on real data; numerically slightly worse.

## Range on REAL data
SIM-calibrated range covered 48 % of HTT minutes. New split-conformal widths from nested HTT LOSO: HALF_NOW_REAL 0.578 °C, HALF_F20_REAL 0.554 °C (_PERSON 0.611/0.604). Band rule: half-width = max(1.645·sd, REAL) until wear-test wrist data exist. HTT coverage 89.8 % (18.5 % of persons < 80 %; with _PERSON 91.8 %, 10.8 %). SIM 99.9 % (conservative).

## Fair NN vs v1.2 (same nested tuning both)
SIM Drink sensitivity v1.2 → hg2: 0.05/h 11–31 → 57–84 %; 0.10/h 22–59 → 90–98 %; 0.15/h 100 → 90–99 %; 0.20/h 100 → 98–99 %. hg2 wins only at ≤ 0.10/h (SIMULATION). HTT, both re-tuned: Drink 0.05: 65/55, 0.10: 85/79, 0.15: 89/82, 0.20: 99/100 %; Danger 0.05: 50/24, 0.10: 69/74, 0.15: 79/76, 0.20: 93/79 %. v1.2 is better on the only real data. NN logit cuts stay OFF.

## Fixes / deviations
Header corrected; golden trace vs B5 mirror diff 0.0; ±inf/NaN guards (hg2_guard.h) with clamped outputs; HR>180 non-monotone documented (OOD guard max(NN, v1.2) when hr_reserve>0.6 — B5). Deviations: held HR forever (ARCH ≤10 min); heat_dose counts down below limit; domain randomisation per person-view; κ tercile edges from all 500 persons' parameters; calibration persons' Twin knows rest HR ±3 bpm (optimistic); pinball range heads.
