# REAL older-adult exams (M18) — how to run them, once

Two pre-registered scripts (metrics, input mapping and pass lines are fixed in each docstring, written before any sealed row was read):

| Script | Data | Sealed part | What it scores |
|---|---|---|---|
| `tests/real_exam_brighton.py` | Brighton/Waldock, 65–76 y, 35 °C/50 % chamber, 5-min rectal + HR + skin + ambient (CC BY-ND 3.0) | sheets P2–P10 | core MAE/bias vs rectal (hg2 and v1.2 alone), displayed-range coverage (REAL widths), DRINK/COOL/DANGER vs rectal ≥ 38.0/38.5 with leads, false alarms/h |
| `tests/real_exam_heatin.py` | HeatIN Montreal 2025 watch minutes (CC BY 4.0) | 17 sealed watch macIDs | false-alarm/behaviour only (no core reference): alarms per wearer-day/week/month by tier and path, CHECKs by cause, no-wake, contact self-check |

Both: refuse to run twice (DONE file written first: `tests/real_exam_brighton_DONE.json`, `tests/real_exam_heatin_DONE.json`), assert the seal (`model/sealed_real_older.json` canonical hash + file SHA-256s), load the guardian **from the tag** (`git archive`, weights SHA-256 checked against that tag's FROZEN.txt), and in exam mode assert `git diff --quiet <tag> -- guardian/c guardian/py model/export` and that the script itself is committed unchanged. Results: `tests/out/real_exam_*_SEALED.json` (summary numbers only — the ND licence forbids derived data files; never commit per-minute tables).

## Manager: exact commands (after freeze-5 and SEALED-SIM-3, each once)

Pre-checks:

```
cd /home/claude/hg_ai && git diff --quiet hg2-freeze-5 -- guardian/c guardian/py model/export && echo TREE=TAG
```

```
test ! -e /home/claude/hg_ai/tests/real_exam_brighton_DONE.json && test ! -e /home/claude/hg_ai/tests/real_exam_heatin_DONE.json && echo NOT-RUN
```

Optional DEV rehearsal on the frozen tag (never touches DONE):

```
cd /home/claude/hg_ai && python3 -I tests/real_exam_brighton.py --tag hg2-freeze-5 --dry-run-dev
```

The exams:

```
cd /home/claude/hg_ai && python3 -I tests/real_exam_brighton.py --tag hg2-freeze-5
```

```
cd /home/claude/hg_ai && python3 -I tests/real_exam_heatin.py --tag hg2-freeze-5
```

The HeatIN replay is slow (pure-Python float32 mirror, ~1 ms/minute, ~2.4 M watch-minutes × 2 variants): budget 1–3 h on this 2-CPU box; run it in the background, nothing else heavy alongside. A crash after the DONE file is written still spends the exam.

## Input-mapping caveats (attach to every number)

Brighton: lab HR (not wrist PPG); T1 = **bicep** skin (closest site to the wrist in the file), flux invalid (no reference sensor); 5→1 min by causal hold (primary) / linear (secondary); assumed 5-min cognitive test between rest and cycling; motion invented from the protocol (0.01 g seated, 0.05 g cycling); sex unknown (0.5); time of day unknown (routine and the personal-relative DRINK line are off); nobody reaches 38.5 °C (file max 38.34) → no Danger sensitivity claim; the last row of a session may be outside the chamber (secondary 0–65 min figure reported).

HeatIN: no watch→room key (R5) — **room air is missing in the primary variant A**; variant B uses the median of all HeatIN room nodes as a building-air proxy (not her room, no verdict). T1 = the watch's case thermometer (BMP280), not skin; no flux; no PPG DC (the no-skin rule cannot fire; the watch reports an "HR" on the charger 93 % of minutes); HR good only when `hr_conf ≥ 70`; a_std mapped from the per-minute |a| range with DEV-set anchors; no z-angle (sleep window stays the 22:00–08:00 default); no button presses (family counts are unanswered CHECKs, an upper bound); ages unknown (protocol ≥ 50), default profile age 75. Every alarm is **unconfirmed**, not false.

## DEV dry-run numbers (hg2-freeze-3, DEV data only — NOT exam results)

Brighton, participant P1 only (3 sessions, 45 reference samples, 3.5 h, rectal max 37.39 °C), HOLD:
- hg2 core MAE 0.372 °C, bias +0.05 (0–65 min: 0.264); v1.2 alone MAE 0.685, bias **+0.69** (reads the cycling HR as heat).
- Displayed range (REAL widths) covers 88.9 % (NN-sd-only width 71.1 %).
- No 38.0/38.5 events in P1 → no sensitivity. DRINK fired once per session at minute 55–60 of cycling (v1.2 path) → 3 unconfirmed (all censored) = 0.86/h.
- Linear resampling: same within 0.01 °C.
- Why the final row hurts hg2: the post-exercise test row (skin falls, sometimes outside the chamber) drops hg2 to 34.9–36.0 °C.

HeatIN, 18 DEV watches (variant A primary: 17 watches with ≥ 7 wearer-days, 1,259 wearer-days; median watch):
- DRINK 1.56/day, 52 min/day; COOL 0.32/week; DANGER 0.00/month (mean 0.04); family 0.25/month → H1–H3 would PASS.
- CHECK **14.1/week → H4 would FAIL**. Why: impact+stillness CHECKs 13.1/week. `apeak` = the Bangle's per-minute |a| max, which passes 2 g in ordinary wrist movement. That is a mapping artefact as much as a band finding. NO-WAKE 0.93/week (13 % of days; the sleep window stays at the default because there is no z-angle). Quiet-run CHECKs 0.
- Contact: 99.5 % of off-charger minutes are called worn, with no loose minutes. This is expected, because with no room air and no PPG DC only the charging flag can mark the band off. In 2.0 % of worn-called minutes (mean 9.5 %) there was no HR for 60 min or more.
- Variant B (building-air proxy, no verdict): DRINK 1.91/day, 85 min/day; 2.44/day on proxy-hot days; COOL 0.81/week; DANGER 0 (mean 0.19)/month; CHECK 12.0/week; the thermal contact rules now fire (5.3 % loose, 0.9 loose episodes/day).
- Full DEV replay took 105 min wall on the shared 2-CPU box.
