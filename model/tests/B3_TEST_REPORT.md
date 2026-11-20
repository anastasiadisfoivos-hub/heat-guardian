# B3 Body Twin: test report, 2026-11-12 (tester T3)

**Verdict: PASS WITH FINDINGS.** Criteria 2 (HTT, C1 gain) and 1 (SIM) are not met. No finding is a blocker. Seal and safety rules hold. Every failure below has a diagnosed cause, and no row says "cause unknown".

Tester files:
- Suite: `/home/claude/hg_ai/tests/B3/test_t3.py`, with helpers `t3_common.py` and `t3_driver.c`.
- Run log: `tests/B3/t3_run.log`. Machine-readable results: `tests/B3/t3_results.json`.
- Firmware harness: `/home/claude/hg_ai/tests/t3_poc/` (base, twin_plain and twin_externc copies of poc_06).
- To re-run: `python3 /home/claude/hg_ai/tests/B3/test_t3.py`. Last run: 36 PASS, 1 FAIL (FMA build, see F8), 6 DEFECT (reproduced on purpose), 1 PENDING, 2 RISK.

## Reproduced acceptance criteria

| # | Criterion (brief) | Command I ran | Result | Pass? |
|---|---|---|---|---|
| 1 | SIM leave-first-days-in: median gain ≥ 0.05 °C, top quartile ≥ 0.10, nobody worse by > 0.03, flux-absent not worse | — | `sim/data/minutes_dev.parquet` was still being written (no parquet footer) at test time. `eval_sim.py` cannot run in any case because of F1 | **PENDING** |
| 2a | HTT: learned rest HR not worse than defaults by > 0.01 °C | `python3 tests/B3/run_eval_htt_copy.py <scratch>` (the builder's script, unchanged, writing to scratch) | Output is byte-identical to `twin/results/htt_eval.json`. R1 −0.0013 (CI −0.0068..+0.0035), Rinf +0.0014 (CI −0.0065..+0.0083). Worst single person −0.144 °C. REAL DATA, young adults, DEV | yes |
| 2b | HTT: C1 same-session reading gain 0.01–0.05 °C | same | Gain vs D: +0.0080, +0.0088, +0.0131 over the 3 noise draws. **2 of 3 draws fall below 0.01.** The builder's explanation reproduces: scoring every minute from minute 0 gives +0.020/+0.020/+0.025, and the β sweep (draw 11) peaks at β 0.25 (+0.0135 vs Rinf) while β 0.35 gives +0.0066 | **no (major, cause diagnosed)** |
| 3a | C == Python on 10 golden nights ≤ 1e-5 | `make -C twin/c test`, plus my own driver built with exactly the brief's flags at -O0 and -O2 on 40 new random streams (400 nightly updates) | Builder golden: max diff 0. Mine: **bit-identical** at -O0 and -O2, including all 40 packed files. The golden is CRAFTED, not SIM-DEV (sim pending), and it never checks an interior K value (F6) | yes |
| 3b | Fuzz never leaves bounds | builder fuzz, plus my 200-night C fuzz with a sequential clock and 30 % NaN/inf/out-of-range fields | Builder fuzz: 0 violations. Mine: 0 violations. **However, a stuck clock pushes t1_night_base to 129 °C (F2)** | **no (F2)** |
| 3c | Corrupt file → defaults | builder flips every bit; I ran 6,000 random multi-byte mutations comparing C and Python verdicts | Every CRC-breaking mutation is rejected and returns defaults. C and Python verdicts agree in 6,000/6,000. A CRC-valid file with an inconsistent learning state is accepted (F3) | yes, with F3 |
| 4 | File ≤ 900 B; round-trip byte-identical; CRC == zlib | T4a/T4b; `hg_twin_crc32` vs `zlib.crc32` on 140 random buffers plus chaining | 140/140 equal. With B5's real routine (`HG_ROUTINE_PACK_BYTES` 650) the file is 851 B, or 7 blocks. A 700-B routine (the ARCH limit) is refused: the limit is 699 (F9) | yes |
| 5 | acc ≤ 256 B, sizeof reported, no dynamic memory, clean compile | host build plus `arm-none-eabi-gcc 9-2019q4 -mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -Os` with the brief's flags | acc 240 B, hg2_twin_t 116 B. ARM `.text` 4,342 B at -Os (builder claimed 4,344) and 4,880 B at -O2. Undefined symbols are only floorf, memcpy and memset. A grep for expf/logf/powf/double/malloc finds nothing | yes |
| — | Compile inside poc_06 (arduino-cli) | `arduino-cli compile --fqbn Seeeduino:nrf52:xiaonRF52840 --export-binaries` on base and on the twin copies in tests/t3_poc (the hook is in `t3_hook.cpp`) | Base: 216,312 B (26 %), RAM 15,548 B. Twin with an `extern "C"` wrapper: **222,344 B (27 %), +6,032 B flash** (includes the hook and libm floorf), RAM 17,456 B (+1,908, of which ~1.8 kB is the harness's 900 + 650 B buffers), `.hex` exported (this core exports no `.uf2`, same as the base build; `.uf2` would need a separate uf2conv step). Twin with a plain `#include "hg_twin.h"`: **link fails** with `undefined reference to hg_twin_defaults(hg2_twin_t*)` etc. (F7) | yes, given the wrapper |

## Attacks and findings

| id | Attack | What happened | Why (diagnosed) | Severity |
|---|---|---|---|---|
| F1 | `sim_io.sealed_sim_ids()` on the real `model/sealed_hg2.json` | Raises `SealMissing`. `eval_sim.py` and `make_golden.py --source sim` cannot run | The manager's seal stores the ids under `sealed_sim_person_ids`. `sim_io.py` only looks for `sealed_sim_ids`, `sim_ids`, `sealed_sim`, `sim`, `SIM` or `sealed.{sim,...}`. The reader fails closed, so no sealed data was read. On a synthetic file with the key it does accept, DevMinutes returned no sealed id, refused `person(sealed)` and dropped a mixed row group entirely (T6c) | major (blocks criterion 1 and the SIM golden; not a leak) |
| F2 | `minute_of_day` stuck, or only one hour qualifying for > 255 min with the nightly update missed | t1_night_base[3] = **129.41 °C** in Python and C (true T1 33.0; bounds 25..42). Realistic variant: a heat wave where only 03:00–03:59 is below 28 °C, with 5 missed updates, gives an hourly mean of 40.00 °C against a true 34.00 °C | `hg_twin.c` ingest_minute: `cur_sum` keeps adding but `if (a->cur_cnt < 255u) a->cur_cnt++` saturates, and `flush_hour_` divides by 255. `hg_twin.py` does the same. The flush only happens when a *qualifying* minute arrives in another hour. Nothing range-checks the value after the update (`sanitize_` runs at the start of the next one), so a value out of bounds reaches `hg2_set_twin` | major (fuzz "never leaves bounds" fails) |
| F3 | CRC-valid file with t1_n[h]=1 and t1_pre_cd[h]=CD_NONE | Accepted by both C and Python. Two nights later t1_night_base[5] = **−87.23 °C** | `hg_twin_unpack` checks t1_n and t1_night_base but never checks t1_pre_cd against 2500..4200 or against CD_NONE when n < 3. The n==1 and n==2 paths then do arithmetic on −32768 | minor (needs a buggy writer or a CRC collision) |
| F4 | int16 overflow of the centi-degree cast (3000 stuck minutes) | t1_pre_cd Python **38824**, C **−26712**: C ≠ Python | `cd_()`: `(int16_t)floorf(x*100+0.5f)` is undefined behaviour when the value is out of range. The Python `_cd` keeps an unbounded int | minor (follows from F2) |
| F5 | n==1 integer mean with a negative odd sum | Python −1, C 0 | Python `//` floors and C `/` truncates (hg_twin.py nightly_update and hg_twin.c, n==1 branch). Only reachable through F3-type states | minor |
| F6 | Coverage of the builder's golden | k_person across all 10 golden nights is only {0.12, 0.40}. The crafted reading (37.05, 33.6, dT 2.4) gives k_obs 1.44, which clamps on night 1 | host_test never checks the K formula's interior C-vs-Python. My T1 covers it: 77 updates with K strictly interior, bit-exact | minor (coverage) |
| F7 | `hg_twin.h` included from the C++ sketch | The header has no `#ifdef __cplusplus extern "C"` guard. In the poc build, a C++ unit references mangled `_Z12hg_twin_pack...` symbols while hg_twin.c exports C names, so it **fails to link** unless the caller wraps the include (hg_nn.h and hg_ppg.h have the guard) | Missing guard in hg_twin.h | minor (integration; B6 hits it on the first build) |
| F8 | Band arithmetic vs the host golden | Arduino compiles `.c` files with `-std=gnu11`, so fp-contract=fast. The ARM object then has **9 `vfma.f32`**; with `-std=c99` it has 0. My host emulation (-O3 -march=native -ffp-contract=fast) gives max diff 7.66e-6 after 10 nights: within 1e-5, but not bit-exact, and 20/40 packed files differ | The builder's Makefile adds `-ffp-contract=off`, so its "bit-for-bit" claim covers the host build only. A centi-degree rounding flip in `cd_()` would cost 3e-3 | minor |
| F9 | Routine-size budget | The 72-B persistent learning state (t1_n, t1_pre_cd) is not in ARCH §5. Routine must be ≤ 699 B against ARCH's ≤ 700 | Design addition, disclosed by the builder. B5 is at 650, so it fits | minor |
| F10 | Required outputs | `twin/REPORT_TWIN.md` does not exist (the update rules with sources, the layout, and what is not learnable live only in docstrings). The `hg_twin_pack` signature differs from the brief (it adds `acc` and `save_count`). Readings are applied immediately by `commit_reading`, including during an alarm, while ARCH says "nightly" and "nothing updates while an alarm tier was on". `t_stamp` and the "≥ 30 min seated" condition are not enforced in C | Builder could not write .md files; the rest are API choices, disclosed | minor |

Checks that passed:
- All rule oracles (T2, 21 checks): p10 within 1 bpm of the numpy percentile; the 59/60, 19/20, 29/30, 30 %/31 % and dT 0.49/0.5 boundaries; Welford mean of 3 values; n capped at 30 (step 3/30 exact); offset decay of exactly ¼ after 4 updates; one night-time alarm minute freezes learning.
- No parameter moves per minute.
- Determinism: sha256 of the Python replay is identical across runs.
- Host time is 9 ns per `ingest_minute` call (×50 gives 0.5 µs).
- The SHA-256 of persons.parquet matches the seal.

## Unverifiable claims in the builder's report

| Claim | Why |
|---|---|
| "C == Python bit-exact" on the band | True on the host (-std=c99). Not true for the Arduino gnu11 build (F8) |
| SIM evaluation numbers | None claimed. PENDING: no complete sim minutes file, plus F1 |

## Labels

HTT JSON is labelled "REAL DATA, young adults, DEV". `eval_sim.py` labels its output SIMULATION. `REPORT_TWIN.md` is missing, so its labels cannot be checked.

## Open risks for the manager

1. **The K rule as specified (ARCH §5) learns the axial gap, not K.** k_obs = K_true + Δ_axial/dT. With the R2 §6.3 constants, after 3 readings the learned K has median 0.40 and sits at the upper bound in 85 % of SIMULATED persons, while the median K_true is 0.135 (T5b). This was already visible in the builder's own golden. Expect criterion 1's |K_true − 0.12| quartile to fail for this reason. It is a spec problem, not a builder bug.
2. MAX30102 outliers (ARCH §3.3: p 0.20, U(−30, +15)), if `hr_valid` does not catch them: rest_hr error after 7 nights has median −0.40 bpm and p10 −2.66 (T5, SIMULATION). The effect is small.
3. HTT C1 misses 0.01 at β 0.35. Re-tuning β on the same HTT data would be dev-on-dev, so freeze any change before the wear test.
4. F2 needs a post-update bounds pass or a 255-minute flush to close before B5/B6 integrate.
