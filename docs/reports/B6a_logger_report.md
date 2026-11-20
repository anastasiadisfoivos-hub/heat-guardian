# [B6a-fix] 08_logger v1.1.0 — delivery report after tester T6a (Nov 12)

**Binaries:** `fw/08_logger/build/Seeeduino.nrf52.xiaonRF52840/`
- `08_logger.uf2` (md5 c3048570…, from .hex 1c2a5a83…): 211,024 B flash (26%), 32,216 B RAM (13%).
- `08_logger_nodcdc.uf2` (md5 66947e44…; `-DHG_DCDC=0`; reports fw `08-logger-1.1.0-nodcdc`): 211,040 B.
- No warnings from the sketch files at `--warnings all`. Both UF2s start at 0x27000.

**Host tests:** run with `sh fw/tools/run_host_tests.sh`; all PASS. Each new test fails on the pre-fix code.
- **B1** (`test_reboot.c`, real log_ring.c, 17-hour steady state, 5/20/30/60 resets): 0 full hours lost, and the 1 Hz seconds kept never drop. Built against the da256d5 ring with `-DOLD_API` it FAILS (17 h lost at 20 resets).
- **M2** (`test_i2c.c`, mock TWIM): on a hung bus, the core's Wire wait loop never returns. hg_i2c returns TIMEOUT in 16.4 ms, clears the bus, and the next transfer succeeds.
- **m1** (`test_cmdparse.c`): `36,85` was stored as 36.00 before the fix and is 36.85 now. Trailing junk is rejected.
- **littlefs over 3 days, with reboots that append and the boot.bin rewrite**: 0 CRC errors, 0 gaps.
- **Board-only fixes** (`test_static.sh`, 8 source checks): all FAIL on da256d5, all PASS now.

**Tester's run_t6a.sh:** see the bottom of this file.

**Fixes**
1. **B1 (resets deleted undumped data):**
   - After a reset the band keeps appending to the newest hour file, with a header record carrying the boot number. The parser splits the file by boot (tested).
   - The ring deletes by free space only. The 20-file count limit is gone; the last-resort listing cap is 100.
   - If the band resets 3 times in a row before reaching 10 min of uptime (counted in GPREGRET2), it deletes nothing for 30 min.
   - `boot.bin` stores a dump watermark. `dump new` sends only undumped files, and `stat` shows `undumped_deleted`.
2. **M2 (I2C could hang the band):**
   - The core's I2C library (Wire) and the three sensor libraries are gone. All I2C goes through hg_i2c.c: one deadline per transfer, then a 9-clock bus clear.
   - The MAX30102, ICM-20649 and DRV2605L are set up with the libraries' register values.
   - A sensor is marked missing only after 3 failures in a row, and missing sensors are re-probed every minute.
   - Storage, BLE, the BOOT event and the first flush now happen before any I2C traffic.
3. **M1 (reset reason always read 0):** `readResetReason()`, so the watchdog counter now works.
4. **M3 (QSPI peripheral never switched off):** after deep power-down, `qspiTr.end()` plus the anomaly-122 workaround, with the CS pin held high. The peripheral is switched back on when the flash is next needed.
5. **Minors:**
   - m1 decimal comma, and the stored oral value is echoed back.
   - m3 the flash's JEDEC ID is printed.
   - m4 `time` with no number now says what it needs.
   - m5 `erase`/`format` work over USB only; `format` is refused while storage is OK.
   - m7 sensors use the 3-strike rule.
   - m8 `erase` deletes one file per loop pass, so it cannot run into the watchdog.
   - m9 the PPG FIFO is drained during flash erases; raw blocks are kept during a flush.
   - README: the tester's points 1–9 plus the CORRUPT wording ("do NOT format").
6. **Item 6:** I did the small part (`dump new` + watermark). I did not do the compact 10-byte record. It changes the record format that parse_log, the tests, B1's column map and the tester's scripts are built on, two working days before flashing. Proper reset handling plus `dump new` make "dump every 16 h" workable. Revisit for 09.
7. **Item 7:** the nodcdc UF2, with one README line on when to use it.

**Not fixed:**
- m6: no RAM survives a reset here (the linker script has no .noinit section), so the clock is lost on reset. Every boot is logged; sync again with `time`.
- Battery ESTIMATE stays 2.5–3.5 days. M3 removes the ~0.7 mA the tester flagged. It is still unmeasured.
- **Main new risk:** the new I2C and device setup code has never run on hardware. The register values were copied from the libraries and checked, but Monday's `stat` must show every sensor = 1 and `i2c timeouts=0`.

**Tester's `tests/t6a/run_t6a.sh`, rerun after the fix (exit 0):**
- Builder host tests: PASS.
- Power-cut test: 2,005 torn reboots, 0 would-format, 0 bad CRC.
- Rebuilt copy: hex and UF2 md5 identical to the shipped ones.
- Two parts of it do not test the fixed sketch:
  - Its reset-loop test still makes a NEW file on every boot, which is the old sketch path. Its losses drop from 17 h to 1 h at 20 resets, and to 4 h at 60, only because the count limit is gone. The sketch now appends to the open hour file instead; `fw/tools/test_reboot.c` model B covers that path and loses 0 h.
  - `parse_edge.c` tests libc `atof` alone, not the sketch's new parser; `fw/tools/test_cmdparse.c` covers that.
  - The tester may want to update both scripts.

---
# [B6a-1.1.1] the four T6a-r2 minors + REF sensor (Nov 12)

- **n4:** the loop's bus recovery now calls `hg_i2c_recover()`, which disables TWIM, clears the bus, then re-enables it. Before, the clear ran with TWIM enabled and never reached the pins. The cumulative `|| ok` condition is gone. Proven by `test_i2c.c` (the clear runs with ENABLE=0); it does not link against the 1.1.0 driver.
- **n1:** the quick-boot counter is now stored in boot.bin (`quick_boots`) instead of GPREGRET2. GPREGRET2 is cleared by watchdog, pin and brown-out resets. Uploads do not count. The counter is cleared with one write after 10 min of uptime. Comment and README fixed.
- **n2:** 1 Hz records are also flushed at 10 s and 30 s of uptime, so short boots keep their seconds.
- **n3:** events logged while events.txt is being written are kept (same partial-write pattern as rawFlush).
- **REF sensor:** `stat` prints a line `REF TMP117 0x49: PRESENT|NOT FOUND  T2=…  T1-T2=…`. README pass criterion: 0x49 = 1 if the REF sensor is fitted.
- **Tests:** `test_static.sh` gains 5 checks. All 5 FAIL on 26393fc; all 13 PASS now. `run_host_tests.sh`: ALL PASS.
- **Binaries:**
  - `08_logger.uf2`: md5 f381c628…, 211,424 B flash, 32,216 B RAM, fw 08-logger-1.1.1.
  - `08_logger_nodcdc.uf2`: md5 113ecdb5…, fw 08-logger-1.1.1-nodcdc.
  - 0 sketch warnings.
