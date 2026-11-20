# B1 Virtual Elders — delivery report (SIMULATION)

All numbers SIMULATION. Paths: sim/velders/ (body, sensors, indoor, weather, scenarios, persons, population, protocols, validate*, run),
sim/data/ (persons.parquet [sealed, untouched], minutes/ppg_1hz/events _dev|_sealed.parquet, scenarios.parquet, README.md),
sim/VALIDATION.md + VALIDATION.csv, sim/tests/test_body.py (18 pass, 2 strict xfail with reasons), sim/figs/*.png.

VALIDATION: 28/46 PASS; mandatory 10/18 PASS (V1 V2 V3 V5 V6 V8 V9 V12 V14 V17). FAIL with diagnosed why: V4 (81 vs 74 bpm at 36 C; trades
against V12 via the omega frame factor), V7 (+0.70 vs +1.1, no supine term), V13/V15/V16 (rest limits too tolerant), V18 (0.19 C/h plateau drift),
V19 (49 % in 2-6 RH pts, median lead 3.1), V27 (no day-2 escalation without a forbidden heat-debt term); also V22-V26, MONO (<=0.025 C below 30 C),
R2-dT34 (R2 internal conflict), R2-dT-cool (5.9 C at 20 C), R3-iii, R3-IS.

Three numbers: V2 = +0.16/+0.73/+0.91 C; V19 median lead 3.1 RH points, 49 % in window; V27 day-2 minus day-1 peak = -0.03 C.
Runtime 238-397 s for 500 x 10 days on 2 CPUs; 477 MB; byte-identical rerun.
minutes_dev sha256 d67daa97...983d1e, minutes_sealed 144fe6e9...b707d.

Conflicts: ARCH rest factor 0.75 -> 1.0 (fails V2 otherwise); omega frame factor 1.6; HR formula double-counts ambient (fixed);
R2 dT<=0.6 at 34 C contradicts R2 physics (holds from ~38 C). velders.body public API unchanged.

## Round 2 (Nov 12, DECISIONS M2) — SIMULATION
VALIDATION 30/46; must-pass 12/17 (V27 now a documented limitation). New PASS: V15, V18. Still FAIL, stopped with numbers (M2.4): V4, V7, V13, V16, V19.
- V13/V16 mechanism: once a resting person hits the wettedness cap, the skin node warms 34->37 C and the added dry heat loss at 34 C air
  keeps them compensable ~1 kPa longer (cap reached 3.75 kPa, inflection 4.70); at 40 C the same warming only cuts dry gain, so the Rest
  limit falls with T_db while PSU's is flat. Rest factor 0.65-1.0, clothing x2 and breakpoint detection all fail to fix it without breaking V2/V12.
- V4 vs V12/V15 trade-off: fr1.8/rest1.0 -> V4 75.8 PASS, V12 FAIL (+0.41); fr1.6/rest0.85 (chosen) -> V4 86.5 FAIL, V12/V15/V18 PASS.
  Cause: ~60 % of the healthy tercile sit at their cap at Meade 36 C/45 % and drift ~17 bpm.
- V7: bedding clo 0.6->0.8 changes nothing (+0.71); the needed supine mattress-contact term has no source (searched). V19: 50 % (64 % without beta-blockers).
- Changes: OMEGA_REST_FACTOR 0.85; HR core-excess unclipped (floor -0.5 C); V18 on Cottle's fixed-environment design.
v2 data: sim/data/*_v2.parquet (v1 kept). minutes_dev_v2 293e0daa...bcf34, minutes_sealed_v2 03c1c09d...4cc3. 514 s. velders.body API unchanged.

## Round 3 (Nov 12, tester T1 + B3 bug fixes) — SIMULATION
Must-pass 11/17 (V1 now FAIL after honest re-score); 28/47 rows overall. v3 data: sim/data/*_v3.parquet (v1/v2 kept);
minutes_dev_v3 ac277862...f6f208, minutes_sealed_v3 3dadd5f1...a5677e. Nights restored (asleep 91 % of 01-05 h minutes, 33 % of all);
sleep a_std median 1.61 mg, 85.5 % <= 2 mg; indoor = B4 tomorrow.indoor (home max 40.0 C). See VALIDATION.md round-3 list.

## v4 (DECISIONS M8) — SIMULATION
Must-pass 11/17 (unchanged). Full DEV validation: V19-dry 60 % HR first, median lead +0.8 C (v3: 0 %, -5.8 C); V19 humid 51 % in 2-6 RH pts,
median 3.1; V4 85.9 bpm (FAIL, unchanged); V2 +0.16/+0.72/+0.96 (PASS). minutes_dev_v4 2bce61d1...7911b9, minutes_sealed_v4 14f2f03a...393847.
