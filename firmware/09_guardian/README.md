# 09_guardian — the Heat Guardian product firmware

This is the band that actually guards. It does what 08_logger does: it reads the same sensors, keeps the same safety rules and records every minute on its flash chip. On top of that, once a minute it runs the **frozen Guardian Loop**: Core Sense hg2, the drink / cool / danger tiers, the CHECK question «Είστε καλά;» and the Body Twin. It then shows the result on the screen, vibrates, and tells the phone.

**0.9.17-demo-b7u (Nov 20, session FLASH-EASY):** flashing without the reset button: `bash bench-tests/flash_band.command <file.zip>` (serial DFU, adafruit-nrfutil `--touch 1200`, works from any build) or `<file.uf2>` (USB `uf2` / `dfu` command -> XIAO-SENSE drive). Power off: double-press gap 900 ms, prompt guard 400 ms, blocked 60 s (was 10 min) after a HELP, a refused double press shows «Όχι τώρα: <why>» 2 s + one tick; `stat` line `# STAT power` (prompts / refusals / last reason / wake source). HELP screen: «Η βοήθεια έχει ζητηθεί» + «Κρατήστε 3 δευτ. για ακύρωση» after the 10 s lock, no «ειδοποιούμε / ειδοποιήθηκε» screens (the phone is told exactly as before). USB `live on|off` = LIVE demo (gauge colour from the real skin temperature vs a 20-s baseline, «ΖΩΝΤΑΝΑ», screen on); the old hex stream is now `hex on|off`. Build line unchanged; also `09_guardian_v0917_demo_b7u.zip` (the DFU package).

**Status (Nov 19, v0.9.17 = 0.9.16 + UI ENGINE (session FW-UI, plan FW-WORLDCLASS stage 0.9.17 + the owner decisions of Nov 19; `hg_fw_ui.c` (button gestures, haptic sequencer, wrist raise), `hg_fw_ladder.c` (closed-loop action ladder, "keep it green" gauge); host tests `fw/tools/test_ui.c`, `fw/tools/test_ladder.c`): a task `hgui` owns the button and the motor, polls the button (20 ms idle, 5 ms while active) and plays the tick on press-DOWN itself, so a screen redraw can no longer delay or swallow a press; TWIM0 behind a mutex (two tasks). The button has exactly three actions: press; hold 3 s = HELP (a 2nd 3-s hold cancels, locked the first 10 s); double press = «Απενεργοποίηση;», one press = System OFF (CLEAN in the journal), 5 s = closed, refused during HELP / any alert or reminder / 10 min after a HELP; 1.2-3.0 s = nothing. Haptic patterns by rhythm and priority (tick, yes, cue, watch, cool, urgent, help, worked, question, off, on); same DRV2605L strength; a silent motor is re-initialised for every pattern and, if still silent, the screen flashes and EVENTS 16 HAPTIC_LOST goes out. The band no longer shows clock-driven generic nudges (N2 last-cool, N4 water, N5 air, N6 A/C, the frozen bedtime tip): Her Day timing advice only. Action ladder (glue only, frozen untouched): reminder by cause -> press = done -> 20-min check (forecast stopped rising = «Μπράβο, δροσίζεστε»; water did not help = «Ακόμα ζεσταίνεστε» + «Πηγαίνετε κάπου δροσερά» + a family note; still rising in the cool or the Danger line = escalation «Πατήστε αν με βλέπετε» / «Ξαπλώστε, βρέξτε τον λαιμό σας» / «Ειδοποιούμε την οικογένεια» + family alert); a press never cancels a prediction. Home screen = gauge: full-screen colour green / yellow-green / yellow / orange / red from the 20-30 min forecast against her lines + a dot on a curved scale; wakes on wrist raise (8 s), any press (15 s) and a gauge step change. EVENTS 14 POWER_OFF, 16 HAPTIC_LOST, 17-21 ladder (ECOSYSTEM_SPEC 5f). USB `vib <effect|name> [ms]`, `ui`, `gauge <0-4|auto>`, `raise [on|off|axis ..]`, `ladder water|cool|danger|off`. `build/09_guardian_v0917.uf2`; build line unchanged from 0.9.16.) Previous: v0.9.16 = 0.9.15 + BOOT GUARD (session FW-BOOTGUARD, plan FW-WORLDCLASS stage 0.9.16, `hg_bootguard.c`, host test `fw/tools/test_bootguard.c`): boot journal on the raw page 0xEB000 (STARTED before anything that can fail, HEALTHY at 60 s, STABLE at 10 min, CLEAN / REST before System OFF) + its RAM copy in `.hg_noinit`; ladder 0-1 normal, 2 careful (no QSPI log), 3 safe (+ InternalFS erased raw before BLE, the stage that died skipped; profile restored from the RAM copy), 4-5 minimal (+ no InternalFS file of ours), 6 rest (Χρειάζεται έλεγχο, Warning pattern, System OFF; a button press = SAFE); pin / power / wake / upload never climb; slow faults (after 60 s, before 10 min) climb from the 6th in a row, never to rest; reset ledger in `stat` (counts per class + the last 8 with uptime and checkpoint; new classes SUPERVISOR / ASSERT / STACK / MALLOC / FAULT-INJECT / REBOOT); the app runs in its own task `hgapp` with a 12 KB static stack; the supervisor (timer task, 250 ms) is the only feeder of the watchdog: app silent 5 s = named SUPERVISOR reset, a writer stuck outside a guard = storage off; plan A-24: an assert outside a guarded file call is an ASSERT reset, never an FS-HEAL marker, and FS-HEAL never formats on a fid=none marker; screen + motor before storage (splash, power-up clicks); USB `fault hang-app|hardfault|assert|loop N`, `pwroff`; `build/09_guardian_v0916.uf2`. **Build line** adds two wraps: `arduino-cli compile --fqbn Seeeduino:nrf52:xiaonRF52840 --build-property "compiler.c.elf.extra_flags=-Wl,--wrap=flash_nrf5x_event_cb,--wrap=vApplicationStackOverflowHook,--wrap=vApplicationMallocFailedHook"` (without the two new ones it still builds; the stack / malloc hooks then stay the core's do-nothing ones).) Previous: v0.9.15 = 0.9.14 + reset/hang fixes (session FW-915-STABLE, plan FW-WORLDCLASS stage 0.9.15): watchdog fed first in setup() (a soft reset does not stop it), Serial wait only with USB power and fed inside; the FS-guard marker and the guard-reset chain kept in .hg_noinit until the heal state is saved (GPREGRET2 cleared only after); flash glue rewritten without Adafruit_SPIFlashBase: every read/program/erase bounded and returning LFS_ERR_IO on failure, wake verified by JEDEC with 3 tries, erase read back; no deep power-down after writes (peripheral off, chip in standby); writer task at priority 0; the timer feeds the watchdog for loop-side guarded calls that make I/O progress; reset classes (RESETPIN first, erratum 136; pin/power/wake are not boot-loop evidence; same-build soft reset without marker = CRASH); VBAT not sampled during a buzz, low-battery mode on 3 low readings in a row; stat: stack free per task, flash error counters, boot class; USB `fault arm|hang-fs|flash-sleep`; `build/09_guardian_v0915.uf2`. Build line unchanged (`--wrap=flash_nrf5x_event_cb`).) Previous: v0.9.14 = 0.9.13 + all periodic log writes in a low-priority writer task (loop() never waits on flash; dump/stat/commands say BUSY while it writes), FS_SLOW lines (ms, erases, programs, reads, littlefs rc) for any log call > 500 ms or failing, flash block-protect bits checked + cleared at boot, events file rotates at 16 KB (16 generations kept), stat shows the last reset cause and the writer. v0.9.13 = 0.9.12 + heal state OFF InternalFS (in `.hg_noinit` RAM + a raw reserved flash page 0xEC000, read back after every write), watchdog checkpoint trace (`# WDT last boot hung after checkpoint <name>`), old `/fsheal.bin` removed on the upgrade boot, InternalFS-itself faults -> format with the profile kept, the USB format escape refuses to run on two boots in a row (press reset to re-allow), a hung FS call is "no flash I/O for 4 s or > 30 s total" (a slow call that keeps doing I/O is not killed and keeps the watchdog fed), fault counts per class (log vs InternalFS), `ifsformat` boot escape. v0.9.12 = 0.9.11 + InternalFS self-heal: every InternalFS call guarded per file (heal/twin/profile/eco), 1st fault of a file -> remove it, 2nd in a row or the same file again -> profile backed up in RAM, InternalFS (only) formatted, profile written back, 3rd -> InternalFS off for the boot; every InternalFS write is flash-error checked and read back, up to 3 tries. **Build with** `arduino-cli compile --fqbn Seeeduino:nrf52:xiaonRF52840 --build-property "compiler.c.elf.extra_flags=-Wl,--wrap=flash_nrf5x_event_cb"` (counts the SoftDevice flash-op errors; without the flag it still builds, the count stays 0). v0.9.11 = 0.9.10 + guard-reset count in GPREGRET2: 2nd guard reset in a row re-formats the log area before any other log call, 3rd = storage off for that boot; unnamed markers quarantine nothing; InternalFS calls guarded; USB `fsformat` escape in the first 3 s and as a command). v0.9.10: compiled + host-tested, NOT yet on a board. 0.9.10 = FS-HEAL: the log file system heals itself, a bad file can no longer boot-loop the band (branch b15-fsheal, on top of 0.9.9).** Previous: v0.9.9 = alert quality: the band stays silent unless the input is valid and the alert persists, never repeats itself, and says "all clear" at the end (branch b14-alerts, on top of 0.9.8 + the events2.txt fix).** Previous: v0.9.8 = the band side of "Her Day" (`HERDAY_SPEC.md`, ECOSYSTEM_SPEC.md 5d; branch b13-herday, on top of 0.9.7). Before that: v0.9.7 = the band side of ECOSYSTEM_SPEC.md (branch b12-ecosystem, on top of 0.9.6). Before that: v0.9.6 = demo bug fixes, bench retest pending; the base (0.9.4 + `hg2-freeze-10` + D1/D6/D9 pins) runs on band B. Earlier status (Nov 13, v0.9.4): compiled and host-tested. The ARM image gives the same guardian output as the host golden bit for bit in an emulator (tests/t6b). Never run on a board.** First flash after the wear test.

**What you can trust and what you cannot:**
- The guardian rules are the exact frozen files (tag `hg2-freeze-6`: Marble Danger, Exception DRINK, 3 g impact CHECK, the v5 Core Sense with the v1.2 anchor). They are checked byte for byte at every build.
- The plumbing around them (screens, buttons, BLE, files) is new. Only the board can prove it.

## Wiring on board B (Nov 16; button + RST changed Nov 20, 0.9.17-demo-b7) - D0, D9 and D2 are physically damaged

| Signal | Pin |
|---|---|
| Screen DIN (MOSI) / CLK (SCK) | D10 / D8 |
| Screen CS / DC | **D1** (was D9) / **D6** (was D0) |
| Screen RST / BL | **3V3** (tied high, no MCU pin; was D7 - the firmware sends a software reset) / D3 |
| SPI dummy MISO | D9 (dead pin, never read) |
| I2C SDA / SCL, button | D4 / D5, **D7** (was D2: D2 reads stuck LOW since Nov 20) |

Never move a used signal back to D0, D9 or D2.

## Source of truth (from v0.9.6)

`09_guardian.ino` is now **hand-maintained**: edit it directly. `fw/tools/make_09.py` and `guardian_layer.inc` are **retired** - they drifted from the flashed firmware (screen on D0/D9, profile `med` limit 31 vs 15, none of the 0.9.6 fixes). Do not run `make_09.py`.

## What changed in v0.9.10 (Nov 18) - FS-HEAL, logging can never brick the band (branch b15-fsheal)

**The bug (band B on 0.9.6-rescue, quick_boots=22):** the boot stopped inside the append to `/log/events2.txt` (yesterday:
`events.txt`) and the watchdog reset it, every boot. **Root cause:** littlefs v1.6 in the Seeed core is compiled WITH asserts.
One corrupt CTZ skip pointer in a file trips `LFS_ASSERT(head >= 2 && head <= block_count)` in `lfs_ctz_extend` /
`lfs_ctz_find` (lfs.c 1144 / 1235). The assert calls newlib `__assert_func` -> `fiprintf(stderr)` (goes nowhere) -> `abort` ->
`_exit`, and `_exit` in this toolchain is the single instruction `b _exit`: a silent spin until the 8 s watchdog. The next boot
appends the same bytes at the same place and dies again. The allocator's traversal reads only pointer slots 0/1, so the other
files keep working (that is why `s0002.bin` appended fine). `fw/tools/test_heal.c` part B reproduces exactly this with the real
littlefs. Renaming moved the problem to the next file; where the bad pointer came from (a power cut while the band was handled,
or a write that did not reach the chip) cannot be proven without a raw image of the flash.

| | v0.9.10 (INFO `0x0910`) |
|---|---|
| Guard | Every log-FS call runs in `FsGuard(file id)`: the id is in RAM while the call runs. Our own `__assert_func` and a 0.5 s FreeRTOS timer (a call longer than 4 s = hung) write the id into the nRF register GPREGRET2 and soft-reset at once (GPREGRET2 survives a soft reset). The watchdog is fed at the start of each FS call; 4 s < 8 s, so it stays the backstop (a hang with interrupts off) and never hides a hang |
| Heal at boot | The marker names the file: events -> that `events_<gen>.txt` is quarantined, removed, and the log moves to `events_<gen+1>.txt`; s-file -> it is left as it is (data) and a new one starts; boot.bin -> removed before reading; a dump read -> that file is skipped by later dumps. Died inside the heal's own remove -> that file is never touched again. Quarantined names are never opened (max 4 remembered) |
| Boot loop, no marker | `quick_boots >= 3` -> **quiet boot**: sensing, alerts, screen and BLE run, but no record / events / raw writes until 10 min of uptime (events stay in RAM, records are counted as dropped); blind heal (new events generation, new s-file). A soft reset of the SAME build is counted as a quick boot (only a new build = an upload), so even a lost marker cannot hide a loop |
| Escalation | 4th troubled boot in a row (marker, boot loop or mount failure) -> **re-format the LOG area only** (QSPI). Profile, twin, family name, routine, day plan and the heal state are on InternalFS: untouched. If the fresh log area fails 4 more boots in a row -> **storage switched off** (`storage=DISABLED`), the band runs without a log. `fsheal reset` (USB) switches it back on |
| Runtime | A write that fails is dropped and counted (`stat`: `flush_err`, `lost`, FS_HEAL `ev_failed_bytes`); 3 failed events appends in a row -> new generation; 3 failed s-file appends -> new s-file. Never retried in a loop |
| Files | Events log: `/log/events_<gen>.txt` (`gen` 1, 2, ...). The old `events.txt` / `events2.txt` are kept and never opened; `rmold` (USB) removes them under the guard. `dump` lists every non-quarantined `events_*.txt` in order, then s/r, then min.bin; `parse_log.py` reads all three names |
| State | InternalFS `/fsheal.bin` (176 B: generation, streaks, counters, quarantine list); written only on heal events, a new build, and per dumped file |
| Console | `fsheal` (state + quarantined files; also in `stat`), `fsheal reset`, `rmold`, `format YES` now also when DISABLED |
| Kept | The 0.9.6 BOOT-TRACE lines around the boot-time flush (USB only, never logged) |
| Guardian | **unchanged**: `frozen/` and `fz_*.c` byte-identical to `hg2-freeze-10` |

First boot after flashing (no marker, new build): `FS_HEAL boot=<n> marker=none bootloop=0 quiet=0 state=new gen=1 events=/log/events_1.txt ...
legacy=events.txt+events2.txt(kept,never-opened) quick_boots_reset_from=<n>`; full expected print in `BOOT_LOG.txt`.

## What changed in v0.9.9 (Nov 18) - alert quality (branch b14-alerts)

The idea: one false alarm in her first week costs more than one missed mild one, so the band only interrupts her when the
reading is trustworthy, the alert has lasted, and it is new. New file `hg_fw_alert.c/.h` (plain C, host-tested); it only
changes what the band DOES with the frozen guardian's output (buzz, wake the screen, log, start a nudge). The frozen guardian,
the STATUS frame and what the screen shows when she looks are unchanged. Details and every number's reason: ECOSYSTEM_SPEC.md 5e.

| | v0.9.9 (INFO `0x0099`) |
|---|---|
| 1. Validity gate | Before DRINK / COOL / a nudge can buzz: band worn (frozen contact check), skin 28-40.5 °C, pulse signal not poor in 3 of the last 5 minutes, no shower signature (humidity jumps 20 %RH to >= 80 % with a 1 °C skin step), no sun-on-sensor signature (air sensor +4 °C in 5 min while skin moves <= 1 °C and the outward sensor is 1.5 °C over skin). Invalid = UNKNOWN, never HIGH: the alert waits, and the wait is logged with its reason. Both signatures are untested guesses (the research report says so): each lasts 45 min at most, humid weather alone never trips the shower one |
| Bounded | A hold never hides a frozen tier for good: DRINK is shown after 60 min, COOL after 30 min of continuous hold (logged `hold limit`) |
| 2. Persistence | DRINK needs 5, COOL 3 consecutive valid minutes, with the estimate not falling back (a minute counts only if f20 >= its value at the start - 0.05 °C); one normal minute resets. A frozen tier that ends earlier is logged `PERSIST` (a self-corrected alarm) |
| Hysteresis | Once shown, an episode is latched: if it goes and comes back, no second buzz (`REPEAT`). It ends only after 10 calm valid minutes AND f20 0.20 °C below the value it was shown at (or after 60 calm minutes); then a new episode may fire |
| 3. Two kinds of evidence | Full COOL buzz only when heat EXPOSURE (trusted air >= 28 °C in the last hour, the frozen heat reasons, or a forecast heat-day hour) and the BODY (frozen body reasons, strain >= 5, or pulse >= her resting + 15 bpm while still) agree. Heat alone = soft tick; body alone (cool air: exercise, fever) = held up to 30 min, then soft. Logged `ONE_EVIDENCE` |
| 4. Speak on change | One buzz when an episode starts or gets worse; nothing while it holds or eases (quiet changes no longer wake the screen). When a shown episode ends: «Πάλι όλα καλά» for 10 s (soft tick if it reached COOL / CHECK or the family was called) and EVENTS type 12 ALL_CLEAR for the family app |
| 5. Scorecard | Console `score`: sent per type, held back per reason, acknowledged, missed, time to acknowledge, unknown minutes; also 3 EVENTS type 13 SCORE frames (on `score` and at local midnight). Every hold-back is a line `ALERT ... held reason=...` in events2.txt and (max 16 a day) an EVENTS type 11 ALERT_HELD frame. `stat` has an `alerts` line |
| NOT changed (safety) | CHECK «Είστε καλά;», DANGER, HELP, I'm OK, NOT_WORN, BATTERY and their buzzes pass through exactly as the frozen guardian gives them: the frozen CHECK starts its own family timer, so holding the question would let the family be called before she was asked. A thermal CHECK with only one kind of evidence is counted (`check_one_evidence_audit`), never held |
| 6. Staged scenes | `scenes/*.csv` (minute keyframes, reusable by the app and the demo video): shower, band on a table, brisk walk on a cool day, sun on the sensor -> 0 interruptions (0.9.8 had 2, 0, 2, 1); slow build-up in a hot flat -> water nudge, DRINK, CHECK, family, all-clear; fast build-up -> COOL, CHECK (answered), all-clear. `fw/tools/run_host_tests.sh` 8d prints the table |
| Planner | N1-N8 unchanged, but run through the gate: no new nudge while the band is off / implausible / in the shower (an open one is not cancelled); the room value it sees is the lowest trusted value of the last 5 minutes (so a sun-heated or shower-steamed sensor never starts WATER / A/C / AIR) |
| Guardian | **unchanged**: `frozen/` and `fz_*.c` byte-identical to 0df5cd9 (frozen sources = tag `hg2-freeze-10`) |
| Flash / RAM | **358,712 B (44 %) / 75,548 B (31 %)** (0.9.8: 347,664 / 75,160); `build/09_guardian_v099_alerts.uf2`, md5 in `09_guardian_v099_alerts.uf2.md5` |

Bench check without a phone: `score` (all zeros after boot), take the band off for 15 min near a warm lamp -> `score` shows the hold-backs; `stat` -> `alerts valid=not_worn+skin`.

## What changed in v0.9.8 (Nov 17) - "Her Day", band side (branch b13-herday)

| | v0.9.8 (INFO `0x0098`) |
|---|---|
| Idea | the band speaks only where her learned day (from her phone) COLLIDES with the heat, plus when to air the flat. Spec: `HERDAY_SPEC.md` (shared), as-built details: ECOSYSTEM_SPEC.md 5d |
| CMD 0x1B DAY_PLAN | today + tomorrow, up to 6 items each (1 OUTING_SHIFT, 2 AIR_OPEN, 3 HEATWAVE_DAY); a day is replaced only when its whole set has arrived (atomic); saved in `/dayplan.bin`; at local midnight tomorrow becomes today |
| CMD 0x1C VISIT | arrive / leave + place type from her phone (iOS Visits). No coordinates ever reach the band |
| EVENTS | type 9 VISIT, type 10 PLAN_ITEM (every stored item is echoed, so every phone sees the same plan); nudge ids 7 EVENING_BRIEF, 8 LEAVE_HOT. Version byte stays 0x03 |
| N7 EVENING_BRIEF | at bedtime - 60 min (default 21:00) if tomorrow has an outing collision or a heat-wave day: «Αύριο: αγορά πριν τις 09:30» / «Αύριο: βόλτα μετά τις 21:00» / «Αύριο: καύσωνας, μέρα 2». Soft haptic, press = done |
| N1 BRIEF | with a kind-1 item today: «Σήμερα: {place} πριν/μετά τις HH:MM» (also on a day the forecast does not flag); else unchanged |
| N8 LEAVE_HOT | she leaves home (band HOME -> TRANSIT, or a VISIT LEAVE from home) inside a hot window of today's plan or a non-safe hour of a heat-day: one soft buzz «Έξω κάνει ζέστη. Πάρτε νερό.» Once per outing (re-armed after 30 min back home), max 2 a day |
| N5 AIR | at the kind-2 suggested time when the plan has one, else 21:30 as before |
| N3 SHUTTERS | removed (a habit she already has) |
| Caps | unchanged: <= 6 a day (N8 counts), >= 60 min apart (N8 exempt), none in the sleep window, warnings win, 10 min -> MISSED. The last daily slots are kept for AIR / N7 when still due tonight |
| BLE | 2 phones at once (her phone + the family phone): `Bluefruit.begin(2, 0)`, advertising restarts while a link is free, STATUS and EVENTS notified to each phone (own EVENTS cursor per phone, SYNC_EVENTS answers only the phone that asked); home/out uses the stronger phone's RSSI |
| Console | `dayplan ...`, `dayplan <day> clear`, `dayplan`, `visit <arrive|leave> <place>`, `homeout <home|out|off>`, `nudge 7` / `nudge 8` (table below) |
| Guardian | **unchanged**: `frozen/` and `fz_*.c` byte-identical (frozen sources = tag `hg2-freeze-10`) |
| Flash / RAM | **347,456 B (42 %) / 75,160 B (31 %)** (0.9.7: 334,356 / 74,008); `build/09_guardian_v098.uf2`, md5 `d65022c2b306ca171d3acda603d9125d` |
| Tests | `fw/tools/run_host_tests.sh` 8b (test_eco + test_herday: parser, store, every nudge rule and cap, screen layout) and 8c (every glyph in the font); vectors for the iOS app: `herday_vectors.json` |

## What changed in v0.9.7 (Nov 16) - ecosystem, band side (branch b12-ecosystem)

| | v0.9.7 (INFO `0x0097`; the version lives in ONE define, `HG_FW_SHORT`) |
|---|---|
| New file | `hg_fw_eco.c/.h`: events ring + EVENTS frame, CMD 0x16-0x1A parser, the planner, reason / date / next-hours texts. Plain C, host-tested by `fw/tools/test_eco.c` |
| Planner (spec 2, 5b) | nudges N1 brief, N2 last cool hour, N3 shutters, N4 water, N5 air, N6 A/C; max 6/day, >= 60 min apart, never in the sleep window / nap, never over a warning; press = DONE («Μπράβο ✓»), 10 min = MISSED |
| Main face (spec 3) | big clock, Greek date, state-colour ring, next-hours line, room °C + 30-min trend arrow, battery %; only changed parts are repainted |
| Warnings (spec 4) | one reason line under DRINK / COOL / CHECK / DANGER (8 px font so 26 characters fit) |
| BLE (spec 5) | EVENTS characteristic `...0004` (read + notify); CMD 0x16 SYNC_EVENTS, 0x17 FAMILY_MSG, 0x18 FAMILY_NAME, 0x19 ROUTINE_SEED, 0x1A ELDER_ACTION, all parsed before the frozen parser; «Η οικογένεια ειδοποιήθηκε ✓» after the family ack. Layouts: ECOSYSTEM_SPEC.md 5c, vectors: `eco_vectors.json` |
| Console | `nudge <1-6>`, `famsg <1-3>`, `famname <name>`, `routine <wake> <bed>`, `events`, `fcdemo` |
| Guardian | **unchanged**: `frozen/` and `fz_*.c` byte-identical to 96a8e63; ARM image == host golden (tests/t6b) |
| Flash / RAM | **334,356 B (41 %) / 74,008 B (31 %)** (0.9.6: 309,296 / 72,888) |

## What changed in v0.9.6 (Nov 16) - demo fixes (branch b11-demo-fixes)

| | v0.9.6 (INFO `0x0096`; `0x0095` is used by b7-ble-sec) |
|---|---|
| Base | the firmware flashed on band B: 0.9.4 + frozen files of `hg2-freeze-10` (byte-identical) + screen CS D1 / DC D6 / dummy MISO D9 |
| HELP / I'm OK | the toast stays until the guardian has acted on the press (next minute + 1 s): no fall-back to a stale OK / CHECK; I'm OK answers any open CHECK |
| Haptics | cancel / I'm OK stop the running pattern (GO=0 first, `hapLeft = 0`); a silently reset DRV2605L (STANDBY or LRA mode) is re-initialised before GO (`DRV re-init` event) |
| Screen | wake from sleep repaints everything (no black screen); a wake-press only wakes (no MAIN/PLAN flip); phone cancel drops a stale HELP toast; cancel restores normal brightness |
| Sensors | TMP117 / SHTC3 trigger failures count toward SENSOR LOST (then NaN + re-probe), no stale value fed forever; SHTC3 wake NACK not fatal |
| Console | `profile <age> <sex_m> <bmi> <med>` can set again (argv limit 6); `time` re-anchors the minute like BLE TIME |
| Guardian | **unchanged**: no threshold, model, rule or tuning touched; `frozen/` and `fz_*.c` byte-identical |
| Flash / RAM | **309,296 B (38 %) / 72,888 B (30 %)** (base: 307,616 / 68,896; +3.9 KB RAM = the profile-set path's scratch guardian, dead code before) |

## What changed in v0.9.4 (Nov 13) - flash wake fix from 08_logger 1.1.5

| | v0.9.4 |
|---|---|
| Bug (seen on a real XIAO with 08) | the flash chip sleeps (0xB9) between writes; a reset or re-flash does not power it off, and the nRF QSPI peripheral cannot wake it (ACTIVATE stalls, JEDEC reads `000000`, `storage=NO FLASH`) until a full power-off |
| Fix (same code as 08 1.1.5) | before every QSPI start (boot, each of 4 storage-init retries, every wake) the peripheral is off and `0xAB` (at boot also `0x66`/`0x99`) is bit-banged on the QSPI pins as GPIO; JEDEC checked on every wake; erratum-122 writes before the disable |
| New | stat fields `flash_wakes` / `flash_wake_fails`, console command `flashdiag`; version 0.9.4 (INFO `0x0094`) |
| Unchanged | everything else (guardian, BLE, screens, deep power-down between writes) |
| Flash / RAM | **304,576 B (37 %) / 68,816 B (28 %)** (0.9.3: 302,320 / 68,776) |
| Tested | host tests, static checks, ARM emulator == host golden. **Not run on a board** |

If it still shows `storage=NO FLASH`: type `flashdiag`, send its lines and the `stat` line, then unplug USB **and** battery for 60 s.

## What changed in v0.9.3 (Nov 13)

| | v0.9.3 |
|---|---|
| Guardian rules | re-synced to tag `hg2-freeze-6` (was `hg2-freeze-3`); 30 files byte-identical, hashes in `FROZEN_SHA256.txt` |
| Model | `hg2-20261113-ca75ce4-simv5aug`, CRC `0xEE4F7E9E` (INFO frame tag `ca75ce4`, now taken from `HG2_NN_VERSION`) |
| Firmware code | only the version (0.9.3, INFO `0x0093`) and the INFO tag. No glue change was needed |
| Flash / RAM | **302,320 B (37 %) / 68,776 B (28 %)**. Was about 297,008 B; still over the 30 % budget (accepted in M14) |
| No fast-math | `hg_nofastmath.h` first in every sketch file; frozen files now also include `hg_fp.h`. Checked on all 17 objects |
| Wiring (Nov 13; **superseded Nov 16, see the wiring section at the top**) | screen DIN D10, CLK D8, CS D9, DC D0, RST D7, BL D3; I2C SDA D4, SCL D5; button D2. 08 and 09 already matched, so nothing changed. DRV2605L EN is tied to VCC and IN to GND: the firmware never used either pin (internal trigger) |
| Behaviour you may notice | an impact CHECK needs a 3 g knock (was 2 g); the 08 log's impact flag stays at 2 g |

Checked here: host tests, the ARM image under the emulator (same output as the host golden, bit for bit), the BLE frames against `tomorrow/` and the dashboard, and the Greek screen texts against the font. **Still never run on a board.**

---

## Flash it

These are the same steps as 08 (08 README, steps 1–4). One step at a time.

### Step 1 — Get the file

**09_guardian_v099_alerts.uf2** (v0.9.9, in `fw/09_guardian/build/`, md5 in `09_guardian_v099_alerts.uf2.md5`). Save it in Downloads. (`09_guardian_v098.uf2` is the previous v0.9.8 and `09_guardian.uf2` v0.9.7, kept to go back.)

### Step 2 — Bootloader mode

Plug in the XIAO and double-tap the reset button. The drive **XIAO…** appears.

### Step 3 — Copy the file

Drag the file onto the drive. The drive disappears by itself when the copy is done; a "Disk Not Ejected Properly" message after that is normal. If Finder complains, use Terminal (change the drive name if yours is different):

```
cp -X ~/Downloads/09_guardian_v099_alerts.uf2 /Volumes/XIAO-SENSE/
```

What you should see:
- The screen shows the green check «Όλα καλά» for 15 seconds, then goes dark.
- If it shows a red triangle and **«Σφάλμα μοντέλου»** (model error), the model file is damaged. Stop and tell me. The band refuses to guard with a damaged model, but it keeps logging the minute sensor inputs.

### Step 4 — Serial Monitor, clock, wearer

Open the Serial Monitor (115200 baud, Newline) and pick the port again. Then type these three lines, pressing Enter after each.

First, the clock. Get the number in Terminal:

```
date +%s
```

Then type `time` and that number, for example `time 1794700800`. The band assumes Athens winter time (UTC+2). The phone or dashboard sends the time zone itself.

Second, the wearer. Type `profile` followed by age, sex (1 = male, 0 = female), BMI and medicine bits. For example, a 78-year-old woman with BMI 26 and no medicines:

```
profile 78 0 26 0
```

When no profile is saved the band uses the target-user default `profile 75 0 26 0`. Medicine bits: 1 = beta-blocker, 2 = diuretic, 4 = low-sweat drug, 8 = ACE/ARB. Add them up.

Third, type `stat` and check these lines:

| Line | Good |
|---|---|
| `STAT model hg2-20261113-ca75ce4-simv5aug crc=OK(0xee4f7e9e)` | the sealed model, intact |
| `STAT sensors: … =1` for every part | 0x49 = 1 if the REF sensor is fitted |
| `STAT REF TMP117 0x49: PRESENT` | the second TMP117 answers |
| `STAT twin load=defaults(…)` on the first boot, `load=ok(0)` after the first night | the Body Twin file |
| `STAT i2c … timeouts=0` | the sensor bus is healthy |
| `loop_stack_free_min=` above 1000 B | the guardian has room to run |

### Step 5 — Wear it

Put it on and unplug it. After the first minutes the screen stays dark unless something happens. Press the button to see the current screen.

---

## What the band shows and does

| Screen (Greek) | When | Vibration |
|---|---|---|
| ✓ «Όλα καλά» | nothing to do | none |
| 💧 «Πιείτε νερό τώρα» | DRINK tier (personal heat-strain line, M9/M11) | 2 long pulses |
| 🏠 «Πάτε σε πιο δροσερό δωμάτιο» | COOL tier | 3 long pulses, again after 10 s |
| ⚠ «Χλιαρό ντους ή κρύα κομπρέσα» | DANGER | (then CHECK) |
| ⚠ «Είστε καλά; Πατήστε το κουμπί» | CHECK: danger, behaviour, routine or impact | 1 s on / 1 s off for ~30 s, asked again at 2 and 5 min |
| ⚠ «Ειδοποιήσαμε την οικογένεια» | no press: the phone was told to alert the family | — |
| ◯✓ «Πάλι όλα καλά» | 0.9.9: a DRINK / COOL / CHECK episode she was told about has ended (10 s) | soft tick if it reached COOL or CHECK |
| ◯✓ «Εντάξει, ευχαριστώ» | you pressed during a CHECK | tick |
| «Φορέστε το βραχιόλι» / «Σφίξτε το λουράκι» | band off / loose (contact self-check) | — |
| «Φορτίστε το βραχιόλι» | battery low | — |
| «Βοήθεια: ειδοποιούμε την οικογένεια» | you held the button 2 s (HELP) | strong |
| 🏠 «Δροσίστε το δωμάτιο» | once in the evening on a hot night (M1.1 nudge) | tick |
| «Ώρες για έξοδο» + hours | press the button while all is OK, after the phone sent tomorrow's plan | — |

The texts and every threshold come from the frozen guardian. Nothing on the screen is decided in the firmware. Since 0.9.9 the firmware decides only WHEN a DRINK / COOL buzzes and wakes the screen (valid input, 5 / 3 minutes, once per episode); pressing the button always shows the real current screen.

**Button:**
- Short press during a CHECK = "I'm OK". The band answers at once; the guardian confirms at the next minute boundary, so up to 60 s later.
- Short press otherwise = show the screen, then the plan page.
- Hold for 2 s = HELP.
- HELP by mistake? Hold for 2 s again: HELP is cancelled, the family flag is cleared, and the screen goes back to normal brightness. The phone can cancel it too (dashboard **Cancel HELP**).
- Low battery: alerts still vibrate, but only as a soft tick.

The screen sleeps after 15 s. During CHECK, DANGER and HELP it stays on.

**Heart-rate sensor:** on for the first 30 s of every minute. It stays on all the time while any tier, CHECK or HELP is on.

---

## Phone / laptop: the dashboard

1. Download `fw/tools` to the Mac (`dashboard.html` and `hg_ble.js`).
2. In Terminal, go to that folder:

```
cd ~/Downloads/tools
```

3. Serve the folder:

```
python3 -m http.server 8000
```

4. Open **http://localhost:8000/dashboard.html** in Chrome and click **Connect to the band**.

On connect it sends the clock (with the time zone) and then shows the live state, core estimate ± range, heart rate, temperatures and battery. Its buttons:
- **Send plan.json:** sends tomorrow's plan from the Tomorrow Engine (`tomorrow/plan.json`).
- **Family notified:** sends the acknowledgement after a family alert.
- **Cancel HELP:** cancels a HELP that was pressed by mistake.
- **Last 60 minutes:** prints the band's minute history in the console box.

Safari and iPhone cannot do Web Bluetooth. Use Chrome on the Mac or on Android.

**BLE details (frozen with `uuidgen` on Nov 12):**

| Item | Value |
|---|---|
| Service | `0c760000-038b-46d5-8532-954dd1c5e01d` |
| STATUS (notify + read, 20 B, once a minute and on every change) | `0c760001-…` |
| CMD (write, ≤ 20 B: 0x10 TIME, 0x11 FORECAST, 0x12 FAMILY_ACK, 0x13 PROFILE, 0x14 SAFE_HOURS, 0x1F DEBUG) | `0c760002-…` |
| INFO (read, 20 B: fw, model CRC, boots, reset reason, twin saves) | `0c760003-…` |
| Also present | Battery service, Device Information (firmware = `09-guardian-0.9.6 hg2-20261113-ca75ce4-simv5aug`), and the Nordic UART console of 08 |
| Connection | 975–990 ms interval, latency 1, timeout 6 s (iOS rules); advertising 20 ms for 30 s, then 1022.5 ms. 0.9.8: up to 2 phones at once; advertising restarts while one link is free |
| EVENTS (read + notify, 20 B) and CMD 0x16-0x1C | `0c760004-…`; layouts in ECOSYSTEM_SPEC.md 5c / 5d, vectors `eco_vectors.json`, `herday_vectors.json` |

The frame layouts are `guardian/c/hg_frames.h` (frozen).

---

## What is recorded, and getting it off

Every minute, two 24-byte records go into `/log/sNNNN.bin`, one file per day:
- the minute's sensor inputs (the 08 minute format);
- a guardian record: state, screen, core, sd, f20, tiers, worn, home/out, routine score, CHECK reason and haptic.

Records are written to flash every 10 minutes and the last 20+ days are kept. Events (boots, state changes, twin saves, phone commands) go to `events_<gen>.txt` (0.9.10; a new generation after each FS heal).

Pull them exactly like 08. From the tools folder:

```
python3 capture.py dump
```

Parse here with `parse_log.py dump_….txt --guardian-out guardian.parquet`.

The band also keeps the last 24 hours of STATUS frames in RAM. `ring 60` (USB) or the dashboard button prints them.

**The Body Twin** is stored in `/twin.bin` on the chip's own flash. It is saved:
- once a night, during the first 30 still minutes after 03:00 (05:00 at the latest), and only when the clock is set;
- when the phone sends a PROFILE value.

That is at most 5 saves a day, never periodically. The file system is never formatted, because that would erase the Bluetooth bonds.

---

## Commands (USB Serial Monitor or BLE UART)

All of 08's commands: `stat`, `time`, `mark`, `dump`, `dump new`, `raw`, `erase YES`, `format YES`, `help`. Plus these:

| Command | What it does |
|---|---|
| `profile <age> <sex> <bmi> <meds>` | sets the wearer, saved. Applied at once without restarting the guardian: an alert, CHECK or HELP that is on stays on |
| `state` | the guardian state and the 20-byte STATUS frame now |
| `ring <n>` | the last n minutes of STATUS frames (hex) |
| `frame <hex>` | feeds a phone frame by hand, e.g. a 0x10 TIME frame |
| `log on` / `log off` | the 1 Hz debug records on USB and BLE UART (off by default) |
| `screen diag` | 08's sensor page for 15 s |
| `nudge <id>` | show a nudge now, no caps (1 brief, 2 last cool, 4 water, 5 air, 6 A/C, 7 evening brief, 8 leave hot; 7 needs a tomorrow plan) |
| `famsg <1-3>` / `famname <name>` / `routine <wake> <bed>` / `events` / `fcdemo` | 0.9.7 bench commands (family message, family name, stated routine, event ring, DEMO heat-day forecast) |
| `dayplan <day> <kind> <place> <uh> <um> <sh> <sm> <dir> <hf> <ht> <peak> <hw>` | 0.9.8: add one Her Day item to day 0 (today) or 1 (tomorrow). The day's stored items + this one are sent as one atomic CMD 0x1B set through the real parser, so the band echoes PLAN_ITEM events exactly as for the phone. `-` = 255 (n/a). Example: `dayplan 1 1 1 10 30 9 30 1 11 19 37 0` = tomorrow, market usually 10:30, go before 09:30, hot 11-19, 37 °C |
| `dayplan <day> clear` / `dayplan` | clear a day / print both days |
| `visit <arrive\|leave> <place>` | 0.9.8: a CMD 0x1C VISIT with the band clock as its time; place = 0-7 or home, market, church, walk, pharmacy, cafe, doctor, other |
| `homeout <home\|out\|off>` | 0.9.8: override the home/out state the planner sees (the guardian's own state is untouched). `homeout home`, then `homeout out` = the HOME -> TRANSIT that triggers N8; `off` = back to the guardian |
| `score` | 0.9.9: the alert scorecard since boot (sent per type, held back per reason, acknowledged, missed, time to acknowledge) and 3 EVENTS SCORE frames |
| `fsheal` / `fsheal reset` | 0.9.10: FS-HEAL state (events generation, quiet, streaks, quarantined files, counters) / switch storage back on after `storage=DISABLED` (USB only) |
| `rmold` | 0.9.10: remove the legacy `events.txt` / `events2.txt` (USB only, guarded; skipped if a remove of it died before) |

**Bench test of Her Day without a phone** (there is no `clock` fast-forward; jump the clock with `time <unix>`, which re-anchors the minute):
1. `time <unix>` (a day, 11:50 local), `fcdemo` (optional heat day).
2. `dayplan 0 1 1 12 0 9 30 1 11 18 36 0` (today: market, hot 11-18) and `dayplan 1 1 3 19 0 21 0 2 12 21 34 0` (tomorrow: walk after 21:00). `events` shows the PLAN_ITEM echoes.
3. `homeout home`, then `homeout out` -> «Έξω κάνει ζέστη. Πάρτε νερό.» (N8). `homeout out` again does nothing (once per outing); `homeout home`, `time` +30 min, `homeout out` -> N8 again; a third time -> nothing (2 a day).
4. `visit leave home` does the same through the phone path (only if its time is within 10 min of the band clock).
5. `time <unix of 21:00 local>` -> N7 «Αύριο: βόλτα μετά τις 21:00» at the next minute. `stat` shows the `herday` line.

---

## Problems

| You see | Do this |
|---|---|
| «Σφάλμα μοντέλου» | the weights CRC failed. Re-flash the .uf2; if it stays, tell me |
| `twin load=defaults` after several nights | the twin file is not being saved or read. Send `stat` and the `events_<gen>.txt` from `dump` |
| `# FS_HEAL ...` lines at boot | the band healed its log (a file quarantined, a new events generation, a quiet boot or a log-area format). It keeps running. Send the lines and `fsheal` |
| `storage=DISABLED` | the log area kept failing even after a re-format: the band works but does not record. Send `fsheal` and `flashdiag`, then `fsheal reset` and reboot |
| state stuck on «Φορέστε το βραχιόλι» while worn | contact check: tighten the band; send `stat` |
| the screen never wakes for a DRINK | check `stat` says `guardian minutes=` growing; send `ring 60` |
| dark, silent after flashing | flash 08_logger_nodcdc.uf2 to test the board, then tell me (a no-DC/DC 09 can be built) |

---

## For the reviewer

- `09_guardian.ino` is the **hand-maintained** source since v0.9.6. It was generated by `fw/tools/make_09.py` from `fw/08_logger/08_logger.ino` plus `guardian_layer.inc`; both are retired (see "Source of truth").
- `frozen/`: the 30 guardian/c, model/export and twin/c sources (now with `hg_fp.h`), copied with `git archive` from tag `hg2-freeze-6` by `fw/tools/sync_frozen.sh`. Hashes are in `FROZEN_SHA256.txt`; `--check` verifies them.
- `fz_*.c`: one wrapper per frozen .c. Each applies `-fsingle-precision-constant -ffp-contract=off` through `fw_flags.h` pragmas, the same instructions the host Makefile's flags give (checked on the core's arm gcc). That is because the Arduino IDE has no per-sketch flags.
- `hg_fw.c/.h`: the glue (1-min summaries, guardian step, twin ingest + nightly, PPG duty, records, 24 h ring), host-tested in `fw/tools/test_fw.c`.
- `BOOT_LOG.txt` is the expected boot print. `SOAK_PLAN.md` is the 72-hour soak.
