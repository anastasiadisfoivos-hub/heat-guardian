# 08_logger — 10-minute bench log

## Real bench, Nov 13 2026 (two real XIAO nRF52840 boards, run by Foivos)

**Symptom.** 1.1.2, 1.1.3 and 1.1.4 all reported `storage=NO FLASH (QSPI flash not detected, JEDEC 000000)` on board A and on board B. A bare test sketch (`flashid`: QSPI begin, 0xAB, 0x66/0x99, read 0x9F) read `85 60 15` on fresh board B, also after the wires were soldered on. After the logger had run, the same `flashid` read `00 00 00` on both boards. 1.1.4's `flashdiag` showed correct QSPI pins and config but `id=00 00 00` at every step.

**Recovery.** USB unplugged 60 s (no battery attached) → `flashid` read `85 60 15` on board B again. The stuck state is volatile: only a power-off clears it. A reset or a re-flash does not, because the flash chip stays powered.

**Cause (from the code; consistent with all bench results).** The logger puts the flash in deep power-down (0xB9) between writes to save current. After a reset the chip is still asleep. The nRF52840's QSPI peripheral stalls when it is activated against a sleeping chip, so every command sent through it, including the 0xAB wake-up, times out. The driver then returns its untouched buffer, read as "JEDEC 000000". Board A's "heat damage" was most likely this too.

**Fix (1.1.5, branch bench-flash).** Before every QSPI start (boot, each retry, every wake after a sleep), the peripheral is switched off and 0xAB is sent by driving the flash pins directly as plain GPIO (+0x66/0x99 at boot). The Nordic erratum-122 register writes are now done in Nordic's order (before the disable). `stat` adds `flash_wakes` and `flash_wake_fails`. `flashdiag` adds return codes and a GPIO-read ID.

**Result, 1.1.5 on board B after one RST** (values as reported from the bench; not the verbatim lines): `boot=2 reset=RESET-PIN quick_boots=2`, `flash_jedec=856015 flash_wakes=1 flash_wake_fails=0`, `storage=OK (mounted)`, records written, 503/512 blocks free, I2C timeouts 0, DRV2605 = 1.

Not yet tested: a re-flash while the chip sleeps, a run over several days, battery current with the GPIO wake.

---

## Earlier: simulated 10-minute log

**SIMULATED. There is no board in this workspace.** The stream below was produced on the host by `fw/tools/sim_stream.py`, which writes lines in exactly the firmware's formats with plausible bench values (not measurements), and parsed by `fw/tools/parse_log.py`. It proves the recording format, the parser and the gap report, not the band. The first real bench log is Foivos's Monday capture (`python3 capture.py live --minutes 10`, then `parse_log.py`).

Reproduce:

```
cd /home/claude/hg_ai/fw && python3 tools/sim_stream.py --seconds 600 -o 08_logger/bench_sim/sim_capture_10min.txt --dumpmin --bin 08_logger/bench_sim/s0042.bin
```

```
cd /home/claude/hg_ai/fw && python3 tools/parse_log.py 08_logger/bench_sim/sim_capture_10min.txt -o 08_logger/bench_sim/sim_capture_10min.parquet --report 08_logger/bench_sim/sim_report.txt
```

## Parsed summary (clean stream, `bench_sim/sim_report.txt`)

| Item | Value |
|---|---|
| 1 Hz records | 600 (t_ms 2,840 … 601,840, boot 3) |
| 1-min summary records (dumpmin section) | 11 (minutes 0–10 since boot; minute 10 is the partial one) |
| CRC errors | 0 |
| Gaps | 0, coverage 100.00 % |
| Unparsed lines | 0 (comment `#` lines are ignored by design) |
| Markers decoded | boot, time, donned, button, oral (36.71 °C) — in order, oral value correct |
| Clock | one `TIME` sync at t_ms 22,440 → every row has unix time, rows before the sync back-dated |
| Sensor availability (simulated) | T1 100 %, T2 0 % (second TMP117 absent → NaN, as on the current band), T_air 100 %, RH 100 %, HR 92 %, motion 100 % |
| Battery (minute records, simulated) | 4.06 V → 4.06 V |
| Parquet | 611 rows, columns `T1, T2, T_air_meas, RH_meas, HR_meas, hr_quality, PI, a_std_g, zangle_deg, button, charging, marker` + bookkeeping |

## Gap detection (5 record lines deleted from the same stream)

595 records, **5 gaps, 5 s missing, coverage 99.17 %**, each gap listed with the t_ms before and after it (t_ms 51,840 / 151,840 / 251,840 / 351,840 / 451,840). One corrupted hex digit → 1 CRC error, that record dropped, reported as 1 gap. (`fw/tools/test_parse_log.py`, all 23 checks PASS.)

## Sizes (from the record format, exact)

| File | Size |
|---|---|
| one 1 Hz record | 24 B (48 hex characters + newline = 49 B on the wire) |
| `/log/sNNNN.bin`, one hour | 3,600 × 24 B + 24 B header = 86,424 B |
| `/log/min.bin`, one day | 1,440 × 24 B = 34,560 B (3 days: 103,680 B) |
| `/log/rNNNN.bin`, `raw 600` | 600 × 308 B = 184,800 B |
| 10-min simulated hour file `bench_sim/s0042.bin` | 14,424 B (600 records + header) |

## Storage over 3 days (real littlefs v1.6 on a host RAM flash, `fw/tools/test_lfs_host.c`)

Same file system code as the band (the copy in the Seeed core), same configuration (512 × 4 KB blocks, read/prog 256 B, lookahead 512), same write pattern (60 records appended every minute, min.bin every 10 minutes, events, one 10-minute raw capture per day, a remount every 26 h), same ring policy (`log_ring.c`):

| Item | Result |
|---|---|
| Records read back | 65,537, 0 CRC errors, 0 gaps inside hour files |
| Write errors / NOR-rule violations | 0 / 0 |
| Hour files kept at the end of day 3 | 17 (plus one raw file, min.bin, events.txt, boot.bin); min free 49 blocks |
| Wear | hottest pair of blocks (the `/log` directory: littlefs v1 rewrites it on every file close) 2,642 erases in 3 days = 881/day → 100,000-cycle flash lasts ~114 days of continuous logging at this rate; every other block ≤ 37 erases |

With min.bin appended every minute instead of every 10, the hot pair takes 1,529 erases/day (~65 days). This is why the firmware buffers 10 minute-records before writing min.bin.

## What only the board can show

Real current draw and battery life, PPG signal quality on the wrist, ICM-20649 low-power self-check result, QSPI flash detection (JEDEC 85 60 15 expected) and flush timing, BLE throughput, watchdog resets. Monday's `stat` output answers most of these.
