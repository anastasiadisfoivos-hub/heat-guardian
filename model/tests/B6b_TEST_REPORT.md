# B6b test report: 09_guardian v0.9.1 (commit 4b5579d), 2026-11-12

**Verdict: FAIL, NO-GO for flashing.** There is 1 BLOCKER, 3 MAJOR and 15 MINOR findings, and each one has a diagnosed cause.

There is no board here, so this is the review a firmware engineer would do before flashing. Every number below comes from a command I ran (scripts and outputs are in `tests/t6b/`; `sh tests/t6b/run_t6b.sh [elf]` reruns all of it), or it is marked ESTIMATE / UNVERIFIED.

The blocker was found by running **the shipped ARM image itself** under a Cortex-M4F emulator (Unicorn). The source was not used for this. The image is byte-identical to the builder's `.uf2`.

## 0. The blocker in one paragraph

The Seeed core compiles every sketch file with **`-Ofast`** (from `compile_commands.json`: `... -Ofast -o ...`). `-Ofast` turns on `-ffast-math`, including `-ffinite-math-only`: the compiler assumes NaN never occurs.

`fw_flags.h` adds `single-precision-constant` and `fp-contract=off`, but it does not turn fast-math off. The frozen code uses NaN as its "not available" sentinel everywhere.

On the shipped image:
- (a) `hg_kf.c:36` `if (!(hr_bpm >= 30 && hr_bpm <= 220)) hr_bpm = s->last_hr;` is compiled as `vcmpe s0,#30; bmi …; vcmpe s0,220; bgt …`, so a NaN HR is **not** replaced. The v1.2 Kalman state then becomes NaN after the first minute without HR and stays NaN until a reboot. That kills the protected v1.2 DRINK/Danger paths (M3.1).
- (b) hg2 outputs differ from the sealed-exam golden by up to 0.17 °C core and 2.5 logit units.
- (c) `hg_twin.c:389/403` `isnan()` is folded to 0, so `hg_twin_unpack` rejects every real Body-Twin file (rc −7). The Twin never survives a reboot.

On a SYNTHETIC heat afternoon (room to 37 °C, HR to 108), the host golden shows **297 DRINK minutes and the shipped image shows 0**.

A control build was compiled only in scratch and nothing was committed. It is identical except for one added line, `#pragma GCC optimize ("no-fast-math")` in a copy of `fw_flags.h`. It matches the golden **bit for bit**: 0 differences over 4,000 hg2 minutes and 2,880 full-pipeline minutes, and the twin loads with rc 0. That confirms both the emulator and the cause.

## Reproduced acceptance criteria

| # | Criterion (brief B6 Part B / caller) | Command I ran | Result | Pass? |
|---|---|---|---|---|
| 1 | 29 frozen files byte-identical to tag `hg2-freeze-3`; FROZEN.txt sha 30b0b131… | `tests/t6b/check_frozen.sh` (my own blob compare) + `sync_frozen.sh --check` | 28 matched by unique name. `hg2_guard.h` exists twice in the tag (guardian/c and model/export/host, which differ); the copy = guardian/c = FROZEN.txt hash 4633a522…. FROZEN.txt@tag = 30b0b131…. CRC 0xB32FA3CA. Only host-only files were not copied | PASS |
| 1b | `.ino` is what `make_09.py` generates | regenerate + `cmp` | identical | PASS |
| A1 | compile, flash ≤ 30 %, RAM ≤ 80 KB | `nice -n 19 arduino-cli compile … --jobs 1 --export-binaries` (copy) | 296,432 B (36 %), 68,616 B (28 %). The rebuilt hex is identical to the builder's | flash FAIL (accepted by M14), RAM PASS |
| 7 | .uf2 md5 = rebuild, family ID, start address | core `uf2conv.py -f 0xADA52840 -c`; `t6b/uf2_info.py` | md5 bfe66af6d61a5f8273596d2eca79662f = the builder's. 1,158 blocks, family 0xADA52840, flags 0x2000, start 0x27000 (= S140 v7 `nrf52840_s140_v7.ld` origin), 0 byte mismatches vs hex | PASS |
| 7 | host tests | `TMPDIR=… nice -n 19 sh fw/tools/run_host_tests.sh` | ALL HOST TESTS PASSED | PASS (but see B1: all host tests use -O2, never -Ofast) |
| A2 | CRC at boot; refuses on failure; «Σφάλμα μοντέλου» | source (guardian_layer.inc:291, 306, 101-104); `hg2_check_crc()` **run from the ARM image** = 1 | correct | PASS (but see m4) |
| A3 | Twin saved only nightly / PROFILE; ≤ 5/day; no `InternalFS.format` | source; `test_fw`; `t6b/safety_e2e` D | true for a normal clock; the cap is per *local* day (m2) | PASS w/ finding |
| A4 | `hg_guardian_step` once a minute from `loop()`; 24 h ring 28.8 KB; 0x1F DEBUG | source: only `guardianSecond`→`guardianMinute`→`hg_fw_minute`; `sizeof` ring 28,800 | correct | PASS |
| 2 | units and NaN sentinels into the frozen API | read `hg_fw.c` + `fwSecond` (layer:24-32) | T2/RH/HR/PI/a_std NaN when missing; minute_of_day 0xFFFF; V; g; deg. z-angle is stale (not NaN) when the IMU is lost (m9) | PASS w/ finding, **but B1 makes NaN unsafe on the band** |
| 2 | Twin pack/unpack + calm get/set at the right moments | source + test_fw + emulation | order correct (boot: unpack→init→calm_from_twin→routine; nightly: update→set_twin→pack incl. calm_to_twin). **On the band, unpack always fails (B1c)** | FAIL (B1) |
| 2 | nothing per minute to internal flash | grep `InternalFS` | only `twinSave`/`profileSave`. Logs go to QSPI every 10 min | PASS |
| 3 | timing vs 8 s WDT | `t6b/bench.c` (20,000 minutes, host) | `hg_fw_minute` p50 4.1 µs, p99.9 25 µs on the host; ×50 ≈ 1.3 ms ESTIMATE. Nightly update + twin pack ×50 ≈ 0.5 ms. ARM `-fstack-usage` chain about 2.4 KB of the 4 KB loop stack (ESTIMATE) | PASS |
| 3 | screen/haptics never block the minute step | source order (`guardianSecond`: step first, then `uiDraw`) | the step is not blocked. The redraw blocks the loop for about 0.3-0.4 s after it (m7) | PASS w/ finding |
| 3 | 30 s HR window | `t6b/ppg_restart.c` (unchanged hg_ppg, SYNTHETIC signal) | after each restart, quality = MOTION for 10-11 s (PI baseline), then about 19 OK s/min (≥ 3 needed) | PASS w/ finding (m6) |
| 4 | CHECK → button → family_alert end to end | `t6b/safety_e2e` A/B | family flag exactly 5 minute-steps after the CHECK screen. A press in any wall minute 1-5 (including the last one) gives IMOK and no family. The ≤ 60 s confirmation latency does not shorten the window | PASS |
| 4 | DANGER never silenced by NN | B5's `host_test.c` from the tag, built against `fw/09_guardian/frozen` | 61/61 incl. "M3.1 NN never removes a protected alarm: 0 violations" | PASS on host, **FAIL on the band: B1 removes the v1.2 protected paths** |
| 4 | low-battery path | source + `safety_e2e` E | guardian emits HG_HAP_SOFT at 3.38 V, but `vibrate()` plays nothing below 3.40 V | FAIL (M1) |
| 4 | brown-out at boot with motor | source: `setup()` never vibrates; < 3.45 V → lowBatMode (no motor, PPG off, BL 20 %) | no motor at boot | PASS |
| 5 | STATUS/CMD vs `tomorrow/tests/ble_vectors.json` + dashboard | `t6b/frames_test.py` (frozen `hg_cmd_parse`) + builder's `test_dashboard.py` | 4 forecast chunks → 24 h decode 0 mismatches; SAFE_HOURS bitmap/plan/tag equal; dashboard TIME/ACK/DEBUG accepted; decodeStatus = B5 unpacker on 978 frames | PASS |
| 5 | malformed CMD rejected | same | 200/200 single-bit flips rejected; short / unknown op / ack type 0 or 9 / PROFILE NaN / mixed chunk rejected; 4/5000 random frames accepted (CRC-8 chance) | PASS w/ finding (m2: TIME has no range check) |
| 5 | time sync | source (layer:238-241, 327-334) | works; an extra partial minute on sync (m3) | PASS w/ finding |
| 6 | power vs 250 mAh | `t6b/power_estimate.py` (R4 A6 table, rows recomputed for 09) | ESTIMATE: 2.10 mA calm → 4.2 days; a tier on all day 3.4 mA → 2.6 days; HELP latched with no phone 33 mA → about 6 h | PASS (≥ 2 days) w/ M2 |
| 8 | README flash guide (Mac, Arduino IDE 2) | read as Foivos | usable; nits in m12 | PASS w/ findings |
| — | AI-only flash 60,527 B (M14) | my own map parse (`t6b/ai_flash_out.txt`) | 60,527 B = 20.4 % of the image, 7.5 % of the 811 KB app area | PASS |
| — | "pragma build == flag build" | ARM gcc, every frozen .c, `-Ofast` ± flags (`t6b/pragma_vs_flags.txt`) | identical instructions, 0 vfma | TRUE but not enough: both builds are fast-math (B1) |

## Attacks and findings

| id | Attack | What happened | Why (diagnosed cause) | Severity |
|---|---|---|---|---|
| **B1** | Run the shipped ARM image (not the source) under Unicorn Cortex-M4F against the host golden (frozen code, guardian/c Makefile flags) on SYNTHETIC inputs: `arm_emulate_hg2.py`, `arm_emulate_fw.py`, `arm_emulate_twin.py` → `t6b/arm_emulation_results.txt` | **hg2 (4,000 min):** core_now max diff 0.167 °C, logit_p385 2.53, strain 0.45. kf is NaN in 3,852 minutes from minute 148 (the first HR dropout) on. **Full pipeline (2,880 min):** 297 state mismatches; host DRINK 297 min vs **band 0**. **Twin:** a freshly packed file → `hg_twin_unpack` rc −7 | The core builds the sketch with `-Ofast` (= `-ffast-math`), and `fw_flags.h` does not turn it off. The probe (`isnan_probe_arm_Ofast.txt`) compiles `isnan`→`movs r0,#0`, `isfinite`→`#1`, `x!=x`→`#0` (only `hg_isnan`'s volatile survives). `hg_kf.c:36` becomes `bmi`/`bgt`, which are false for NaN, so NaN HR enters the KF. `hg_twin.c:389, 403`: `!isnan(b)` → 1 → err for every unlearned hour (2 self-compares at -O2, 0 in the shipped object: `twin_isnan_arm.txt`). Reassociation changes every NN sum. **Control:** the same sketch with `#pragma GCC optimize ("no-fast-math")` added to a scratch `fw_flags.h` → 0 differences on all three tests and twin rc 0. Host x86 bisection (`ofast_bisect.txt`) also flags `hg_twin` and `hg_util` (the `hg_util` crash is host-gcc-13-specific; the ARM `hg_isnan` keeps its `vcmp`). No test in the repo compiles at `-Ofast`. "C == Python" from the sealed exam therefore does **not** carry over to the band | **BLOCKER** (protected safety path dead on the band; Twin never persists; exam equivalence broken) |
| M1 | Low battery: what plays at 3.38 V | the guardian outputs HG_HAP_SOFT (R4 A8.2); nothing vibrates | `pofPoll` sets `pofHold` below 3.40 V (layer:283-287), and `vibrate()` returns on `lowBatMode \|\| pofHold` (ino:522). R4 A8 kills the motor only on POFWARN (VDD < 2.8 V) and keeps the soft tick to 3.35 V and below. So DRINK/COOL/CHECK/DANGER are silent for the last charge (ESTIMATE: hours at about 2 mA). Deviation 3 discloses "motor off" but not the silencing | MAJOR |
| M2 | Accidental 2 s press with no phone ack | HELP stays latched; the screen stays on at 100 % (`uiAlert`, BL_WARNING_PCT); ESTIMATE about 6 h to empty | Only 0x12 ack type 3 clears HELP (frozen, correct per A7.2). The dashboard's only ack sends type 1 (`dashboard.html` `cmdFamilyAck(1, …)`), and no tool sends type 3 except typing a `frame` hex by hand. This also breaks the brief's "No screen always-on in 09". `safety_e2e` C | MAJOR |
| M3 | Console `profile …` during HELP / CHECK | HELP, family_pending and the active CHECK are all cleared | `guardianCommand` "profile" calls `hg_guardian_init()` (memset) and restores only calm + routine (layer:371-374). It is reachable over the open BLE UART (no pairing). `safety_e2e` C: state 8 → 0, family 1 → 0 | MAJOR |
| m1 | HELP latency | the family flag appears at the next minute boundary (0-60 s) | the button is latched in `hg_fw_button` and consumed by the step. ARCH 7.2 says "family flag immediately". The README discloses only the IMOK latency | MINOR |
| m2 | CRC-valid TIME frames stepping the date | 1,440 nightly updates + 1,440 twin saves in one real day (`safety_e2e` D) | `saves_today` resets when `local_day` changes (hg_fw.c:250), and TIME has no range check (unix 0, 0xFFFFFFFF, tz_q −128 accepted: `frames_out.txt`). Console `profileSave` has no cap. Needs a buggy or hostile phone (CMD is unauthenticated) | MINOR |
| m3 | TIME sync mid-minute | one extra partial minute step (uptime index → unix index; a backward re-sync across a boundary does it again) | `guardianSecond` steps on `idx != lastIdx` (layer:331-334). It advances CHECK/debounce counters by one; HR may be invalid for that minute | MINOR |
| m4 | CRC-failure claim | README "keeps logging" and BOOT_LOG "keeps logging its minute inputs" are false | `guardianMinute` returns before `hg_fw_minute` builds `rec_in` (layer:306), and make_09 removed the 1 Hz and 08 minute writers | MINOR |
| m5 | CHECK haptic | 3 pulses per 7 s run, not 4 (12 in 30 s, not 15) | `serviceMotor` stops the DRV after 5 s (ino:540); HAP_CHECK lasts 7 s | MINOR |
| m6 | PPG restart each minute | MOTION for the first 10-11 s, then OK (`ppg_restart_out.txt`) | `hg_ppg_init` resets `pi_slow` (tau 30 s), so `PI > 3 × pi_slow` → MOTION until about 12 s. This is not "settling". About 19 OK s/min on a clean SYNTHETIC signal; the real-wrist margin is UNVERIFIED | MINOR |
| m7 | Screen wake blocks the loop | ESTIMATE 0.3-0.4 s (SLPOUT 120 ms + `fillScreen` in `screenWake` + again in `uiDraw(true)`) > MAX30102 FIFO 320 ms | full redraws are synchronous in `guardianMinute`/`uiButton`. Expect `stat` "ppg overflows" > 0 on wakes | MINOR |
| m8 | Forecast / plan freshness | old plans are never expired; a partial new plan is mixed with old chunks and still counts as "complete" | `FC` is initialised only at boot (layer:296); `have_mask` stays 0x0F | MINOR |
| m9 | IMU lost | `z_5s` gets the last z-angle, not NaN | `zMed` is not updated when `accN < 3` (ino:945-958) | MINOR |
| m10 | iOS connection parameters | min = max = 990 ms | `BLEConnection::requestConnectionParameter` sets min = max; Apple asks min + 15 ms ≤ max (relevant to a future iOS app only) | MINOR |
| m11 | B4 "every CMD frame is 20 B" | a 20-B TIME with its CRC at byte 19 is rejected (rc −2) | frozen `hg_cmd_parse` defines 7-B TIME/ACK/PROFILE. Doc inconsistency for whoever writes the phone app | MINOR |
| m12 | README as Foivos | works; nits | example `time 1763287200` is Nov 2025 (he is told to use `date +%s`); `dumpmin` is listed but 09 no longer writes `/log/min.bin`; Finder's "Disk Not Ejected Properly" after the copy is normal and not mentioned; the dashboard cannot clear HELP | MINOR |
| m13 | Flash budget | 36 % vs 30 % | accepted by M14; the no-fast-math fix adds 576 B (297,008) | MINOR |
| m14 | PPG power vs R4 budget | ESTIMATE PPG ≈ 1 mA vs R4's 0.23 mA | 09 keeps 08's SpO2 400 sps × avg 4 (`SPO2_CONFIG 0x2F`): IR LED duty 16.4 % vs R4's 4.1 %, and 50 % duty (disclosed). Still ≥ 2 days | MINOR |
| m15 | Short press during HELP or DANGER-without-CHECK | the «Εντάξει, ευχαριστώ» toast appears although nothing is acknowledged | `uiButton` shows IMOK for any state ∈ {CHECK, DANGER, HELP} (layer:147) | MINOR |

## Unverifiable claims in the builder's report

| Claim | Why I could not verify it |
|---|---|
| "On the core's arm gcc the pragma build matches the flag build" | Verified as stated (identical instructions), but the claim is misleading: both builds use fast-math, so neither matches the -O2 golden (B1) |
| Any on-board behaviour (current, boot print, BLE, haptics, screen) | no board; BOOT_LOG.txt is written from source, as the builder says |
| `loop_stack_free_min > 1000 B` | ESTIMATE only (my ARM `-fstack-usage` chain about 2.4 KB used of 4 KB) |

## Sources missing or wrong
- README/BOOT_LOG "keeps logging on CRC failure" is wrong (m4).
- hg_fw.h says the PPG "needs ~10 s to settle". The measured cause is the PI-baseline gate (m6).
- The R4 A6 PPG budget no longer applies to 09's sampling settings (m14).

## Labels missing
None in the builder's report: no board numbers are claimed, and the soak battery life is labelled ESTIMATE. All my emulation inputs and the heat scenario are labelled SYNTHETIC.

## Open risks I would raise to the manager
1. **Do not flash 09 until B1 is fixed and re-tested on the ARM image.** The candidate fix is one line in `fw_flags.h` (`#pragma GCC optimize ("no-fast-math")`), which B6b owns. The emulation scripts here are the regression test.
2. Every Arduino build of frozen code (poc_02, poc_06 and any other) has the same `-Ofast` exposure. "C == Python" must be re-stated as "host C == Python; band image == host C (emulated)".
3. The low-battery motor cut (M1) and the HELP latch / console re-init (M2, M3) are design calls on safety vs power. The manager decides.
4. 08_logger (flashing Monday) also builds with `-Ofast`. I did not re-assess it for fast-math. It has no NaN-sentinel model code; `vbat == vbat` checks there fold to true.
5. PPG margin (m6, m7) and the real current can only be measured by the soak: watch `ppg overflows`, HR-valid minutes per hour, and the battery curve.
