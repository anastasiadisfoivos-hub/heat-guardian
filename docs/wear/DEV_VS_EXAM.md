# What the wear test SETS (day 1, dev) and what it SCORES (days 2–3, exam)

Rule: nothing is tuned and scored on the same data. Day 1 = Mon 16 after school → Tue 17 12:00 (night 1). Days 2–3 = Tue 17 12:00 → Thu 19 12:00 (nights 2–3). Older-relative sessions are never dev.

ARCHITECTURE §3.2 rule 6 says thresholds are frozen before the recordings are opened. How both hold: the **rules** that turn day 1 into thresholds are code in `tests/wear_exam.py`, frozen with it by the tag `wear-freeze` before Monday. Their **values** come out of day 1 automatically. `--phase dev` drops every row after DEV_END before computing anything, so a person can look at day 1 but cannot pick a number from days 2–3. The exam recomputes the dev values itself and refuses if `wear/DEV_THRESHOLDS.json` was hand-edited.

## Set on day 1 (dev)

| Threshold | Frozen value now | Day-1 rule (exact, in the exam's docstring) | Who asked for it |
|---|---|---|---|
| Sleep stillness `HG_STILL_G` | 0.002 g (MC §4e) | 95th percentile of a_std over night-1 in-bed minutes, rounded up to 0.0005 g, clamped 0.001–0.010 | M4.5 |
| Routine quiet/active split `HG_ACTIVE_G` (quiet-run rule) | 0.02 g (R3 §3.4) | smallest of 0.005 / 0.0075 / 0.01 / 0.015 / 0.02 / 0.03 g keeping ≥ 97 % of night-1 in-bed minutes non-active | M9.4 |
| Sleep detection: HDCZA multiplier | 15 (van Hees 2018) | the one of 10 / 15 / 20 with the smallest night-1 onset + wake error vs the diary; ties → 15 | M9.4 |
| Walking minute for home/out `HG_WALK_G` | 0.05 g (DESIGN, "set on the wear test") | 10th percentile of a_std in day-1 WALK minutes, rounded down to 0.005 g, clamped 0.02–0.10 | FROZEN.txt |
| Contact: loose step `HG_CT_STEP_C`, ratio drop `HG_CT_RATIO_DROP`, off nearness `HG_CT_OFF_NEAR_C` | −0.5 °C, 0.7, 1.0 °C (R2 §5) | grid −0.3/−0.5/−0.8 × 0.6/0.7/0.8 × 1.0/1.5, best (not-worn caught) − 3 × (worn called not-worn) on day 1; ties → frozen | brief item 7 |
| SHTC3 body-heat coefficient c (Twin `c_bodyheat`) | 0.15 (twin default) | median c of the day-1 room tests | R2 §6.2 ("fit c per band") |
| Resting HR (Twin) | 70 bpm | 10th percentile of valid in-bed HR on night 1 | M10 (1) |

## Scored on days 2–3 (exam), never tuned

| Analysis | Scored with | Pass / consistency line |
|---|---|---|
| (a) Sensors vs simulator: donning transient, ΔT across the foam, c, PPG valid rate, loose signature | measured values | sim ranges (20–30 min, 2–5 °C, c 0.05–0.30, ≥ 75 % at rest, T1 and PI fall when loose) |
| (b) Contact confusion matrix | frozen thresholds **and** day-1 thresholds | off ≥ 90 %, worn→off ≤ 1 %, loose episodes ≥ 50 %, worn→loose ≤ 2 % |
| (c) Home/out vs out/home marks | frozen DESIGN thresholds | trips ≥ 50 %, home→OUT ≤ 5 % |
| (d) Sleep window vs diary; in-bed stillness | frozen HDCZA **and** day-1 multiplier; day-1 STILL_G | errors ≤ 60 min per night; ≥ 90 % in-bed still |
| (e) Frozen guardian replay (tag hg2-freeze-3): alarms per day by path | frozen build; day-1 variant beside it; elder-profile swap reported | DRINK ≤ 3 and ≤ 90 min/day; COOL = DANGER = 0; CHECK ≤ 1 over 2 days |
| (f) Oral reading vs displayed range | frozen build | ≥ 80 % inside, n ≥ 4 |
| (g) Battery, resets, coverage, CRC | firmware as worn | 0 watchdog, 0 CRC errors, ≥ 99 % minutes |

## Never set from the wear test

Alarm thresholds (DRINK Δ 0.30 °C, T_ctx 30 °C, COOL, DANGER, persistence X = 20 min), the NN, the conformal range, the PSU lines. M16.3: no more alarm tuning; the wear test only measures their real false-alarm rate. A day-1 threshold that later goes into firmware is reported with its days 2–3 score, labelled "set on 1 real night, scored on 2".

## Risks the manager should know before `wear-freeze`

1. **R1 — a_std is not the same number on 08 and 09.** 08 logs the std of |a| inside each second; the exam averages those per minute. 09 (`hg_fw.c`) computes one std over the whole minute, which also includes slow movement between seconds, so it is always ≥ the 08 value. Day-1 still/active/walk thresholds are therefore in 08 units and would be too low (too sensitive to stillness) if copied into 09 unchanged. The fix belongs in firmware (log both), not in the exam.
2. **R2 — z-angle is logged in whole degrees.** HDCZA thresholds are 0.13–0.50°, below the 1° step, so in the replay a 5-min block is "inactive" only when its z median does not change at all. 09 uses float z on the band. The exam's sleep-window result is a lower bound for 09.
3. **R3 — the replay never presses the button.** Every CHECK not cleared by movement becomes a would-be family call; they are reported, not scored as family alerts.
4. **R4 — BLE is "unknown" in the replay** (08 logs no RSSI, and his phone travels with him). Home/out rests on air change and walking only. School is labelled OUT but is indoors, so C3 agreement will be low by design.
5. **R5 — the replay is the Python mirror of hg2-freeze-3**, not the ARM image. The fast-math bug (T6b) is in the ARM build; the mirror is the reference.
6. **R6 — n = 1, one healthy young wearer, November.** No heat exposure, so every thermal alarm is false and sensitivity is not tested. Nothing here is evidence about older adults; the relative's hours are descriptive.
7. **R7 — on the synthetic self-test the frozen guardian started 3–4 CHECKs per exam day**: routine quiet runs > 180 min (the fallback rule; the learned buffers need 3 days per hour slot, which 3 days barely give) because a seated person's a_std stayed under 0.02 g, plus one "no wake" CHECK because a calm morning never reached 3 ACTIVE minutes. If real days look the same, E3 fails on the frozen build and the day-1 ACTIVE_G variant (E4) is the number to discuss. This is a property of the synthetic generator, not a measurement.

Self-test: `python3 wear/selftest/selftest.py` (synthetic only; ~1 min; 19 checks).
