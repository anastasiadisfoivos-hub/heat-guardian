# 09_guardian — 72-hour soak plan (NOT run yet)

**Goal.** Before the band goes on anyone's wrist as a guardian, prove four things on the bench:
- it runs 72 h without a single reset;
- the battery curve is real;
- the Body Twin saves exactly once a night;
- every minute is on the flash.

**Pass criteria:**
1. `stat` at the end: `resets: watchdog=0`, `quick_boots=0` or 1, and `boot` unchanged since the start.
2. `guardian minutes=` within ±3 of 4,320.
3. `twin … saves_this_boot=3` (one per night), `nightly_runs=3`, `load=ok` after a forced reboot at the end.
4. The parsed dump has ≥ 99.9 % of the 4,320 minutes (input and guardian records both).
5. 0 CRC errors.
6. `i2c timeouts=0`, `ppg … overflows` growing by less than 1 per hour.
7. `loop_stack_free_min` stays above 1,000 B.

## Set-up (day 0, about 20 min)

1. Flash `09_guardian.uf2` (README step 3).
2. Set the clock and the wearer with `time <unix>` and `profile 78 0 26 0`.
3. Strap the band around something warm and still, a glass of water at ~34 °C on a towel. Or wear it, if the plan is a wear test.
4. Leave the Mac connected over USB for the first and last hour only. Run it on battery in between, so the battery curve is real.
5. Start a capture:

```
python3 capture.py live --minutes 60
```

6. Open the dashboard once and check that STATUS arrives every minute.

## Every 12 hours (5 min)

1. USB in, then `stat`. Note `vbat`, `guardian minutes`, `twin saves`, `resets`, `stack`.
2. Run:

```
python3 capture.py dumpnew
```

3. USB out.
4. Charge whenever `vbat` is below 3.6 V, and note the time on and off charge. Charging minutes carry the charging flag.

## Deliberate tests in the soak (each logged with `mark 9` before it)

| Hour | Action | Expected |
|---|---|---|
| 2 | loosen the strap for 10 min | «Σφίξτε το λουράκι» within ~2 min; worn returns to 2 after re-tightening |
| 6 | take it off for 15 min | NOT_WORN screen at 10 min; STATUS bit `not_worn` |
| 24 | send a plan from the dashboard (`tomorrow/plan.json`) | `FORECAST complete`, `SAFE_HOURS` events; plan page on button press |
| 25 | hold the button 2 s | HELP screen, family flag in STATUS; dashboard "Family notified" clears it |
| 48 | reset button once | boot+1, `FILE APPEND` event (same day file), no minute file deleted |
| 71 | `stat` then reset | twin `load=ok`, calm baseline and rest HR as before |

## After the soak

1. Pull everything:

```
python3 capture.py dump
```

2. Parse it:

```
python3 parse_log.py dump_*.txt -o soak.parquet --guardian-out soak_guardian.parquet --report soak_report.txt
```

3. Read the battery curve from the minute records (`vbat`). Expected ≥ 2 days per charge. This is an ESTIMATE, not measured: the PPG runs 30 s a minute, the screen is off, the QSPI flash sleeps.
4. Write the result table into `reports/B6b_guardian_report.md`, with failures and their causes.
