# B5 Guardian Loop test report — T5, 2026-11-12

Target: git tag `hg2-freeze-3` (7a09e19). `guardian/c` and `guardian/py` are byte-identical between the tag and HEAD (`git diff hg2-freeze-3 HEAD -- guardian` touches only the sealed-exam DONE file and the exam script, which I did not open). Weights: `model/export/hg2_weights.{c,h,json}` and `guardian/c/hg2_guard.h` match the FROZEN.txt SHA-256s. I did not run or open any sealed exam or sealed file. All my builds are out of tree (`tests/t5/build`), so nothing under `guardian/` was written.

**Verdict: FAIL (1 blocker, 4 major, 9 minor). Every finding has a diagnosed cause.**
- **Blocker:** -Ofast / fast-math (the band's compiler setting). It confirms T6b-B1 and adds a host crash.
- **The rest of the host build is clean.** C == Python holds bit for bit on my own random traces. Every FROZEN rule is implemented as written, and my independent tier oracle agrees with the C on every minute.
- **Majors:** two safety-logic gaps (M3.1 / M13, and a CHECK freezing when the band comes off), one test-validity defect, and one false-family-alert path.

Scripts: `tests/t5/` (gen_random.py, run_diff.py, build.sh, sc_harness.c + sc.py, sc_diff.py, props.py, m31.py, edge.py, twin_rt.c, fm_funcs.sh, bench.c, sizes_probe.c). Results: `tests/t5/out/`.

## Reproduced acceptance criteria

| # | Criterion (brief / ARCH §9 / task) | Command I ran | Result | Pass? |
|---|---|---|---|---|
| 1 | Builder unit/property/trace suite, Makefile flags | `tests/t5/build.sh` then `build/host_O2 guardian/tests` | 61 PASS / 0 FAIL | yes (but see D3: the M3.1 property is vacuous for the f20 path) |
| 2 | Every FROZEN.txt threshold = compiled value | probe that prints all 161 `HG_*` rows of FROZEN.txt from the compiled cfg | 161/161 equal; `HG_UNC_LOWER_CONST` 0.0179999992, `HG2_LOGIT_CUT_38` 1e9 | yes |
| 3 | Every FROZEN rule traced to code (table below) | read + grep | all rules found; 4 cfg defines unused (m3) | yes, with m3/m4 |
| 4 | **C == Python on MY random traces** (10,000 sequences; NaN/±inf/1e30/out-of-range on every float field, clock jumps, time unknown incl. junk ≥1440, long gaps, blackouts, forced worn/loose/off, charging, button storms, acks with near-right ids, PROFILE incl. NaN, FORECAST good/bad-CRC/mixed chunks, garbage frames, 10 four-day sequences) | `python3 tests/t5/run_diff.py 10000 2` | 10,000 sequences, 1,644,489 min: **0** integer/STATUS mismatches, **0** float mismatches (bit-identical float32, NaN pattern equal). State minutes OK 316k / DRINK 171k / COOL 73k / CHECK 5.8k / DANGER 406k / IMOK 6.0k / NOT_WORN 76k / BATTERY 37k / HELP 554k; 6,024 family flags | yes |
| 5 | C == Python on the logic layer with scripted Core Sense (dense alarms, exact threshold values ±1 ulp) | `python3 tests/t5/sc_diff.py 1500` | 1,500 sequences, 551,780 min, 0 mismatching minutes (29 outputs incl. internals); 1,489 family flags | yes |
| 6 | Independent tier oracle (my own re-implementation of every tier condition from FROZEN M11.2/M11.3/M12/M13 + ARCH 7.2 + M1.3/M3.1/M5.2) vs C, plus properties: no level skip, debounce 2 / hold 10 exact, DANGER only through CHECK, family only ≥5 (danger/behaviour/impact) / ≥10 (routine) min after CHECK start with no accepted press, asks at 0/2/5, HELP latched until 0x12 type 3 for its id, NOT_WORN freezes tiers + screen at 10 min, routine learning frozen under COOL/DANGER/CHECK/not-worn (M7.3 (i)), calm-f20 learning only at level 0 | `python3 tests/t5/props.py 1500` | 1,500 sequences, 551,780 min, 263,297 DANGER-tier min, 1,489 family flags: **0 violations** of every property; tiers/level == my oracle on 100 % of minutes | yes |
| 7 | M12 / M13 / design-A crafted edge cases (C and Python both) | `python3 tests/t5/edge.py` | 44 cases, 40 as expected, C == Py 44/44. The 4 that differ are D2, D4, m1 | see D2, D4, m1 |
| 8 | Design-A calm baseline ↔ Twin file round trip | `build/twin_rt` (guardian + twin/c unchanged) | 2,000 values (bounds, 1 ulp inside, random) × n ∈ {1, 2, 7, 255}: 0 mismatches, bit-identical; 40 full days through original vs restored guardian: 0 differing minutes; NaN/±inf/out-of-range/n=0 → unlearned | yes |
| 9 | sizeof(hg2_state_t) ≤ 512, sizeof(hg_guardian_t) ≤ 4 KB | ARM probe (`arm-none-eabi-gcc 9.2.1`, M4F hard-float) + host | ARM: hg2 488, guardian 3,768 (contact 1,588, routine 1,064, homeout 72). Host: 488 / 3,776 | yes (report's "3,488" is stale) |
| 10 | Stack ≤ 2 KB in hg_guardian_step | ARM `-fstack-usage` per file, deepest chain; host `-fcallgraph-info` + builder's stack_highwater.py | ARM -O2: 792 + 728 (hg2_step_aux) + 112 (hg_kf_step) = **1,632 B**; ARM -Ofast 1,560 B; host 1,760 B | yes (report's "1,216 B" not reproduced) |
| 11 | No malloc / expf / logf / powf / double / VLA / recursion | `nm -u` on the ARM objects; grep; `-Wvla` | Undefined symbols: floorf, sqrtf, memcpy, memset only; no `__aeabi_d*`; no VLA | yes |
| 12 | Code size | `arm-none-eabi-size`, ARM -O2 / -Ofast | Guardian code without weights 23,657 B (-O2) / 28,747 B (-Ofast); weights 27,432 B | — |
| 13 | ASan + UBSan (incl. float-cast-overflow) on random traces | `host_san`, 300 sequences, 49,924 min | 0 errors at the Makefile semantics | yes |
| 14 | Host timing | `build/bench` (100,000 steps) | 7.2 µs/step on a loaded host; ×50 ≈ 0.36 ms per minute-step | yes |
| 15 | **-O2 vs -Ofast -ffast-math, host gcc 13** | run_diff (all 10,000) + per-file bisection (300 seq) + per-function disassembly diff (x86 and ARM) | see D1 | **no** |

## Attacks and findings

| id | Attack | What happened | Why (diagnosed) | Severity |
|---|---|---|---|---|
| **D1** | Same frozen sources built `-Ofast -ffast-math` (the band's flags) vs `-O2` on my random traces | **Host -Ofast: replay segfaults on every sequence** (9,989 of 10,000; in a 300-sequence bisection, DRINK minutes go from 29,112 to 0 before the crash). `-O2 -ffinite-math-only` **alone** reproduces it. With `-Ofast -fno-finite-math-only` nothing crashes, but every minute's floats differ, and 1,078 state minutes in 147 of 10,000 sequences differ (threshold knife-edges; max float diff over all outputs 0.038, incl. logits) | (a) x86 `hg_isnan` (hg_util.c:13): the `volatile y != y` becomes `comiss; setne` with the parity check dropped, so NaN is reported as a number. `is_num(tair)` (hg2_step.c:33) then passes NaN to `hg_pa_kpa → hg_psat_kpa` (hg_util.c:17-22). `(int)NaN` = INT_MIN, and `pos < 0` is false for NaN, so the index stays INT_MIN and `HG_PSAT_KPA[INT_MIN]` is read out of bounds. On ARM `vcmp` keeps hg_isnan correct (T6b), and `vcvt` gives 0, so there is no crash, but this is ISA luck. (b) The reassociation class changes the NN sums, Kalman and table interpolation; knife-edge threshold minutes flip | **blocker** (confirms T6b-B1) |
| **D2** | M3.1 pairs on the scripted harness: identical protected inputs (v1.2 f20/z, PSU-line flags, heat dose, HR, buttons). A = random NN, B = NN silenced | Danger tier on in B but off in A in **292 of 1,000 pairs** (4,072 minutes; 65 family flags raised in B but not in A). Making the NN f20 non-decreasing removes all tier violations. Crafted: COOL from the heat dose for 60 min with air above the PSU line all along, and NN f20 falling 0.001 °C per 10 min → **no DANGER, no family**; same case with flat f20 → DANGER at min 21, family at 26 | M13's slope term (hg_guardian.c:230-232, 246-248) uses `f20_alarm`, which is the NN f20 unless OOD (l.159, 163). So a slowly falling NN forecast vetoes a persistence Danger whose evidence is the protected PSU line (`aux.env_above`). This breaks M3.1 ("NN … never remove an env-path alarm") in spirit. FROZEN M13 says "f20" without naming which | **major** |
| **D3** | Read the builder's M3.1 test (host_test.c `property_nn_monotone`) | Its hook rewrites `hg2_out_t.core_20/f20_eff`. In the default build (HG_TWIN_READING_MODE 0) the tiers read `aux.core20_noff` (hg_guardian.c:159), which the hook never touches. Both A and B therefore run the same real NN f20, and the f20 path is never tested. That is why the 0 violations missed D2 | Test validity: the hook is applied after `hg2_step_aux` and only to `core` | **major** |
| **D4** | DANGER CHECK open, band taken off (contact worn = 0) at CHECK minute 2 | **No family flag for the following 177 min**. The state stays DANGER/CHECK, `check_t` is frozen. Same for routine and impact CHECKs | hg_guardian.c:283 `if (!g->help && worn != 0)` skips the whole CHECK block, so the 5-min counter (l.292) never advances. "NOT_WORN: tiers frozen" (ARCH 7.2) is extended to the CHECK window. A confused wearer who removes the band (or a band that falls off during a collapse onto a hot surface, where contact uses PPG/IMU only) never triggers the family call | **major** (safety logic; the spec is silent, so this is a manager decision) |
| **D5** | Band booted / donned / time first synced between W+2 h (10:00 default) and 12:00 | Quiet wearer: routine **NOWAKE CHECK in the first minute, family flag at minute 10**. Active wearer: CHECK at minute 0, then cancelled once 3 active minutes are seen | hg_routine.c:187: `mod >= D && mod < 720 && !awake_today` with `awake_today` = 0 after init or reset (hg_routine_init). There is no minimum wear/observation time before rule (b). A watchdog reset or a late donning in that window fires it | **major** (false family alerts; M9.4 thresholds are untuned, but this is a logic gap, not a threshold) |
| m1 | Clock jumps backwards (14:40 → 13:00, e.g. a phone resync) | Treated as midnight: the calm baseline is updated with a partial day (a_base_n 0 → 1), `reading_today` is reset, the routine's `awake_today` is reset (D5 can then fire) | hg_guardian.c:151 `mod < g->last_mod`; hg_routine.c:106 | minor |
| m2 | M13 COOL-tier semantics | Persistence counts minutes in which the COOL **tier** is on, including hold minutes: COOL's condition was false for 9 of the first 20 minutes and DANGER still came at minute 21 | hg_guardian.c:245 `pd_cool_run` counts `cool.on`. This matches the FROZEN wording; recorded so the manager knows "COOL on ≥ 20 min" ≠ "heat for 20 min" | minor (as specified) |
| m3 | Magic numbers / unused cfg | `HG_ENV_ACT_WIN`, `HG_AC_STEP_WIN`, `HG_CT_RATIO_WIN`, `HG_VBAT_BOOT` are frozen but unused: the code hard-codes 30-bit mask, ring 16, ratio[30], and the boot rule is absent. Literals in code: 720 (nudge re-arm), 1.645, HR 30/220, rest-HR 40/100, c 0.4, flux gate 0.15/0.5, clamp 2.5, 25 °C/50 % defaults. The Python mirror hard-codes most tier literals (10, 97, 5, 10, 15, 30, 45) instead of reading hg_consts.json | brief: "never magic numbers in code" | minor |
| m4 | DRINK margins under design A | `HG_M_OLDER` (on DRINK), `HG_M_LOW_SWEAT`/`HG_M_BETA_BLOCKER` (on DRINK) and `HG_M_DIURETIC_DRINK` have **no effect** in the frozen build: `low_d` is computed and discarded (`(void)low_d`, hg_guardian.c:216). The diuretic "hydration proxy" margin of ARCH 7.2 is silently dead, yet FROZEN lists it as a live threshold. Also, after M12 the cfg/FROZEN text "the absolute 37.85 C line … stays as an always-firing ceiling" is false: below 30 °C corrected air (non-OOD, below the older PSU line) that line does not fire, and before the first calm baseline exists DRINK has no body path at all in such rooms | design A + M12 as decided, but undocumented | minor (documentation) |
| m5 | HELP and learning | Routine learning continues while HELP is latched (`ri.frozen` = cool/danger/check only), and calm-f20 learning ignores CHECK/HELP (only `level == 0`). HDCZA 5-min medians (sleep window) are collected under alarms | hg_guardian.c:264, 204; hg_routine.c:112-129 | minor |
| m6 | Ack matching | FAMILY_ACK and the HELP release accept a match on the low 16 bits only (= minute counter). An ack for a different alarm raised in the same minute counter (or 45.5 days later, after wrap) clears it | hg_guardian.c:69, 71 | minor |
| m7 | Test harness CMD buffer | `host_test replay` with a CMD hex longer than 64 B: stack smashing (ASan: stack-buffer-overflow, host_test.c:28/78) | `uint8_t b[64]` but `hexbytes` writes up to 256 | minor (test code only) |
| m8 | Report freshness / missing tests | B5 report numbers are stale: guardian 3,488 B (now 3,768 ARM), stack 1,216 B (now 1,632 B ARM). There is no crafted trace or unit test for M13 at all (traces/LIST.txt has none; only a re-baseline) | — | minor |
| m9 | Sensor-fault reading | NaN a_std (dead IMU) → treated as 0 g → "still" every minute → behaviour path armed and routine quiet-run CHECK after 180 min | hg2_step.c:174, hg_guardian.c:130, hg_routine.c:103 | minor (fails loud) |

Also observed and not a defect: after an IMOK, a protected-path CHECK that starts during the 15-min snooze is delayed. In one M3.1 pair an NN-raised CHECK was answered, and the v1.2-logistic CHECK of the silenced twin then reached family 5+ min earlier. This is the specified snooze (ARCH 7.2), and the wearer had pressed.

### FROZEN rule → code trace (all at hg2-freeze-3)

| Rule (FROZEN.txt / source) | Code |
|---|---|
| M11.2 DRINK = (valid ∧ heat_ctx ∧ v1.2 f20 ≥ 37.85 − unc) ∨ (thermal_ok ∧ calm learned ∧ f20 − calm ≥ 0.30 − unc) | hg_guardian.c:210-215; unc = M11.4 const 0.018 (hg_unc.h:145-147, l.164-166), only after the 20-min blank (l.149, 164) |
| M11.3 OOD: reserve > 0.60 or HR > 108 → max(NN, v1.2) | l.162-163 (strict `>`: edge tests 108.0 / 0.6 → not OOD, +1 ulp → OOD) |
| M12 heat context: corrected air ≥ 30.0 ∨ air above the older PSU line ∨ OOD; COOL/DANGER never gated | l.214; `env_above_old` hg2_step.c:191-195; tin = corrected air hg2_step.c:136 (raw 30.0 °C with T1 34 °C, c 0.15 → 29.4 °C: gate closed, as written) |
| M13 persistence: COOL tier ≥ 20 min ∧ f20 − f20(t−10) ≥ 0 ∧ (env_above ∨ NN p385 ≥ 0 ∨ v1.2 z ≥ −2.1972) | l.229-233, 245-248, 253 |
| Debounce 2 / hold 10 / ladder one level per minute | l.44-50 (`tier`), 237-257 |
| HR gating > 5 min | l.224-226 |
| Behaviour path on the shadow non-NN COOL tier (M3.1) | l.249-252 |
| M1.3 cap 0.20 | l.185-188, 210, 249 |
| Older / medication margins | l.22-30 (DRINK side dead in design A, m4) |
| PSU env lines, ADL vs rest, young | hg2_step.c:187-198 |
| COOL: f20 ≥ 38.35 − low_c ∨ dose ≥ 97 ∨ strain ≥ 7 for 10 min | l.222-223, 235-238 |
| CHECK, family 5/10/5, asks 0/2/5, IMOK + 15-min snooze | l.273-303 |
| HELP latch until 0x12 type 3 | l.144-147, 69-71 |
| NOT_WORN freeze, screen 10, phone 30 | l.234, 317, 326, 351 |
| Donning blank 20 / valid 5 | l.149; hg2_step.c:123-125, 255 |
| Battery soft < 3.5, state < 3.35 | l.334, 343 |
| M1.1 WHO = night flag + one nudge (not a tier) | l.172-184, 237 |
| M7.3 (i) learning freeze | l.264; hg_routine.c:159 |
| Design A learning (08–22 h, resting, worn, thermal_ok, level 0; median of 0.02-°C bins; EMA 0.3; [36.8, 37.7]) | l.192-207; edge tests: 37.1 °C → 37.09 (bin centre of float32 37.1), clamp 36.8/37.7, ≥ 38 °C days ignored |

### Fast-math sensitive functions (task 7)

Method: compile each file at `-O2 -ffp-contract=off` with and without `-ffinite-math-only` (NaN class), and with and without the reassociation flags. Diff the disassembly per function (`tests/t5/fm_funcs.sh` → `out/fastmath_functions.txt`). Dynamic confirmation comes from the host bisection (exactly one file at -Ofast, 300 sequences).

- **NaN/inf class, ARM M4F (the band):**
  - `hg_kf_step`: the HR gate at l.36 (T6b showed NaN then enters the Kalman) and the RH clamp at l.62.
  - `hg2_step_aux`: the inlined `hg2_guard_f`, `hg2_finite_or_nan`, `hg2_z_guard` and `hg2_clampf` (all `x == x` or `!(x >= lo)` idioms), plus the flux gates.
  - `hg2_set_twin`: the `b == b` test.
  - `dense`.
  - `hg_ln1p`: `!(x > 0)`.
  - `hg_routine_step`.
  - `hg_guardian_step`: inlined guards and NaN comparisons on tin, vbat, a_peak.
- **x86 host, additionally:**
  - `hg_isnan` itself → the D1 crash. Note it is the "fast-math-proof" helper.
  - `hg_contact_step`, `hg_status_pack`, `hg_routine_unpack`, `hg_guardian_cmd`, `hg_guardian_set_calm`.
- **Reassociation class (both ISAs):**
  - `dense`/ensemble sums, `hg_kf_step`, `hg_psat_kpa`, `hg_ln1p`, `hg_sin_tod`/`hg_cos_tod`, `u8c`, `hg_routine_step`, `hg_guardian_step`.
- **Unaffected:** `hg_homeout`, `hg_frames` (ARM), `hg_contact` (ARM, because it only uses out-of-line `hg_isnan`).
- **Host bisection:**
  - Only `hg_util.c` at -Ofast breaks behaviour on x86 (crash).
  - `hg_kf.c` or `hg2_step.c` alone gives float drift ≤ 1e-3 and 1 flipped state minute in 45,224.
  - Every other file alone: identical.
  - Host results under-report the ARM NaN breakage, because x86 `comiss` happens to keep ordered compares false for NaN. The authority for the band is T6b's ARM emulation.

Fix candidate (B6's): `#pragma GCC optimize ("no-fast-math")` in front of every frozen file, or `-fno-fast-math` for these objects. Re-run `run_diff.py` with the ARM image afterwards. Note: `-fno-finite-math-only` alone is not enough, because reassociation still flips knife-edge minutes (D1).

## Unverifiable claims in the builder's report
| Claim | Why I could not verify it |
|---|---|
| "ARM stack 1,216 B" | I measure 1,632 B (ARM -O2, deepest chain) and 1,760 B (host). Still < 2 KB |
| "guardian 3,488 B" | Now 3,768 B (ARM), after the M7/M13 additions |
| "poc_06 + guardian 264,232 B (32.6 %)" | Not rebuilt here (the CPU was shared with a parallel arduino build; B6b/T6b own the firmware size) |
| HTT / SIM rates in FROZEN.txt | Out of scope for this pass (no sealed data; I did not re-run eval_*) |

## Sources missing or wrong
- m3 (unused frozen defines, literals in code and in the Python mirror).
- m4 (DRINK margins frozen but dead; the "always-firing ceiling" text is false after M12).
- ARCH 7.3 "tier state ≤ 128 B": guardian-own state is now ≈ 424 B (3,768 − sub-structs − profile/twin), mostly `a_hist` 200 B.

## Labels missing
None found in guardian/FROZEN.txt (SIM rows carry SIMULATION / SET IN SIMULATION). M13 is correctly labelled "validated only on SEALED-SIM-2".

## Open risks I would raise to the manager
1. **D1:** do not flash any build of these sources compiled with fast-math. Host C == Python does not carry over to the band image.
2. **D2:** decide whether M13's slope uses the NN f20, max(NN, v1.2), or only the protected inputs. As built, the NN can silence an env-evidenced family call.
3. **D4:** decide whether a CHECK keeps counting (or escalates) when the band goes off mid-CHECK.
4. **D5:** add a minimum observation time (or `awake_today` restored from the Twin) before the no-wake rule. Otherwise every late donning or reset at 10:00–12:00 asks, and a quiet wearer's family is called at minute 10.
5. **D3:** fix the M3.1 test to perturb `aux.core20_noff` (the value the tiers read) and to compare family flags, not only tier bits.
