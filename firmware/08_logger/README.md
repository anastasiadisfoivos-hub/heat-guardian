# 08_logger — the wear-test recorder

The band records everything once a second for the 3-day wear test (Nov 16–18) and keeps it on its own 2 MB flash chip. It also sends the same numbers live over Bluetooth and USB. Nothing clever: no alarms, no model.

**Status (Nov 13, v1.1.5): first real-board pass.** On board B, 1.1.5 found the flash after a RST (storage=OK, mounted, flash_jedec=856015, flash_wake_fails=0), wrote records, I2C timeouts 0, DRV2605 found. 1.1.2–1.1.4 could not reach the flash chip on a real board: it was stuck asleep (see BENCH_LOG.md, "Real bench, Nov 13"); 1.1.5 fixes that. Battery life, PPG on the wrist and multi-day logging are still untested. If anything differs, write down what you saw and send it.

---

## Monday: flash it and start the test

Do these one at a time. Each step says what you should see.

### Step 1 — Get the file

You need **08_logger.uf2**. Claude sends it to you (it lives in `fw/08_logger/build/Seeeduino.nrf52.xiaonRF52840/` here). Save it in your **Downloads** folder. This is the exact binary that was compiled and checked: you do not need to compile anything.

There is a second file, **08_logger_nodcdc.uf2**. Use it only if the screen stays completely dark and nothing appears in the Serial Monitor after flashing the normal one (it runs the chip's power supply in the older, safer mode; it costs a little battery).

### Step 2 — Put the board in bootloader mode

1. Plug the band's XIAO into the Mac with the USB-C **data** cable.
2. Double-tap the tiny reset button next to the USB-C socket (like a double-click).
3. The LED pulses slowly and a drive whose name starts with **XIAO** appears in Finder.

(Same as SETUP.md section 2.6.)

### Step 3 — Drag the file onto the drive

1. Drag **08_logger.uf2** onto the XIAO drive.
2. The drive disappears by itself after a few seconds and the band restarts. macOS may say the disk was not ejected properly: ignore it.
3. The screen lights up with the status page for 15 seconds, then goes dark. **Dark screen = normal** (it sleeps to save battery; press the button to see it).
4. If Finder shows **"Error -36"** or refuses, copy it with Terminal instead (the drive name may be slightly different; check it in Finder's sidebar and change `XIAO-SENSE` if needed):

```
cp -X ~/Downloads/08_logger.uf2 /Volumes/XIAO-SENSE/
```

*Fallback if the .uf2 will not go on:* put the `08_logger` folder in Downloads, open the sketch from Terminal (your 11 Nov lesson):

```
open -a "Arduino IDE" ~/Downloads/08_logger/08_logger.ino
```

then pick **Seeed XIAO nRF52840** and the port, click **Upload**. No extra libraries are needed beyond GFX Library for Arduino and U8g2 (the sensor libraries are no longer used; they can stay installed).

### Step 4 — Open the Serial Monitor

1. Arduino IDE 2 > Tools > Port > the **/dev/cu.usbmodem…** one. **Pick it again now**: the name changes after flashing.
2. Tools > Serial Monitor. Speed **115200 baud**. Line ending: **Newline**.
3. Press the reset button once (single tap) if it stays empty.

You should see lines starting with `#`, then one long line of letters and numbers every second (that is the record, in hex). Every 10 seconds there is a readable line that starts with `# S`.

### Step 5 — Set the clock

The band has no clock of its own after a restart. In Terminal on the Mac run:

```
date +%s
```

It prints a number like `1763287200`. In the Serial Monitor's input box type `time` and that number, for example `time 1763287200`, and press Enter.

You should see a line `# TIME boot=… unix=1763287200 …`.

(Once the tools are on your Mac, `python3 capture.py time` does the same with no typing; close the Serial Monitor first.)

### Step 6 — Check everything with stat

Type `stat` and press Enter. Check these lines:

| Line | Good | If not |
|---|---|---|
| `storage=OK (formatted (first use))` on the very first boot, `storage=OK (mounted)` after that | the flash works | **"formatted" on any later boot means the data was wiped: stop and tell me.** NO FLASH / CORRUPT: see "Problems" |
| `sensors: TMP117-0x48=1 TMP117-0x49=1 SHTC3=1 ICM20649=1 … MAX30102=1(on) DRV2605=1` | every part answers. **0x49 = 1 if the REF sensor is fitted** (0 only if you have not fitted it yet) | a 0 means that part is not answering: unplug USB, check its plug, try again |
| `REF TMP117 0x49: PRESENT  T2=…  T1-T2=…` | the second TMP117 answers; T2 is a sensible temperature, a little below T1 when worn | `NOT FOUND`: check its ADDR jumper is closed (SETUP.md 4.1) and its plug |
| `ICM20649=1(0x68,accel-LP-25Hz)` | motion sensor in low-power mode, gyro off | `accel-LN-gyro-off` also works, uses a bit more battery: tell me |
| `vbat=…V` | about 3.7–4.2 V | below 3.6 V: charge first |
| `time=SET` | clock set | repeat step 5 |
| `now: T1=… HR=…` | T1 is a sensible skin/room temperature | — |
| `resets: watchdog=0` | no crashes since first use | any watchdog reset: tell me (this counter works since v1.1.0) |
| `i2c ok=… timeouts=0 … bus_at_boot=ok` | the sensor bus is healthy | `timeouts` growing or `STUCK-LOW`: a Qwiic plug is loose. The band keeps recording what it can |

### Step 7 — Put the band on

1. Put it on and tighten it.
2. Type `mark 1` and press Enter. (1 = "donned".) You should see `# MARK … name=donned …`.
3. Wait one minute, type `stat` again, and check `now: HR=` shows a number and `q=4` at least some of the time while you sit still.

### Step 8 — Unplug and live normally

Unplug the USB cable. The band keeps recording on its battery. Write the start time on paper.

---

## During the 3 days

### Markers: tell the recording what happened

A marker is a label stored inside the recording at that second. They are what the final exam is scored against, so they matter more than anything else you do.

| Number | Name | When |
|---|---|---|
| 1 | donned | you just put the band on |
| 2 | loose | you loosened it on purpose (loose-band test) |
| 3 | off | you just took it off |
| 4 | shower | shower starts (take it off first, or mark 3) |
| 5 | out | you leave home |
| 6 | home | you are back home |
| 7 | oral | you took an oral thermometer reading — type `mark oral 36.85` with your number |
| 8 | help | **long press** of the button (2 s) |
| 9 | button / custom | **short press** of the button, or `mark 9` |

Three ways to add one:
- **Button:** short press = marker 9, long press (2 s) = marker 8. Both vibrate and wake the screen for 15 s. Write on paper what each short press meant.
- **USB:** in the Serial Monitor, `mark 5` (or `mark out`).
- **Phone, no cable:** any BLE UART app (for example nRF Connect or Adafruit Bluefruit Connect). Connect to **HeatGuardian**, open UART, send `mark 5`. The phone also receives the hex record every second.

### Battery (ESTIMATE — nothing was measured)

The estimate is about 2.5–3.5 days on a full charge (heart-rate sensor on all the time). **Top it up every evening**: plug USB into the Mac or a charger for about **3 hours**, or until `stat` shows `vbat` of 4.1 V or more (the XIAO charges slowly, about 50 mA). The recording carries on while charging (each second is flagged "charging", so the temperatures from that time are not used for skin analysis). Run `stat` and note `vbat` each morning: that gives the real battery curve.

If the battery falls below 3.35 V the band goes into "charge me" mode by itself: it stops the heart-rate sensor and the vibration but keeps logging temperatures and motion. It switches back when charged.

### The screen

It is dark on purpose. Press the button to see it for 15 s:

| Line | Meaning |
|---|---|
| T1 / T2 | skin / reference temperature (T2 shows --.-- without the second TMP117) |
| Air | SHTC3 air temperature and humidity |
| HR | heart rate, quality word (OK / MOTION / LOOSE / NO SKIN / IRREG), perfusion index |
| Move, z | motion this second (g), wrist angle |
| Bat | battery voltage, % (rough), USB when plugged in |
| Mark | last marker and how long ago |
| Log | current file, OK or ERR |
| Time | set / NOT SET, BLE on / adv |
| Up | time since start, boot number |

---

## Getting the data off the band

Do this at the end of each day (with USB plugged in for charging anyway) and at the end of the test. Close the Arduino Serial Monitor first.

Claude sends you the `tools` folder too; put it in Downloads. Once, install the serial library in Terminal:

```
python3 -m pip install --user pyserial
```

If that says "externally-managed-environment", use this instead:

```
python3 -m pip install --user --break-system-packages pyserial
```

Go to the tools folder:

```
cd ~/Downloads/tools
```

The first time, pull everything (a few minutes; not measured yet):

```
python3 capture.py dump
```

After that, pull only what is new since the last dump (much faster):

```
python3 capture.py dumpnew
```

(Both save a `dump..._<date>_<time>.txt` file and stop by themselves at `# DUMP DONE`. If you are not sure, use `python3 capture.py dump`.) **Send the .txt file to Claude**: it is turned into a table here (that needs numpy/pandas/pyarrow, which your Mac does not need).

What is kept on the flash: the **last ~17–20 hours** at 1 record per second (one file per hour, the oldest deleted automatically when space runs out), and the **1-minute summary for the whole test** (`min.bin`, never deleted), plus `events.txt` (every boot, reset, marker, clock sync). A `raw 600` capture uses the space of about 2 hours of 1 Hz data. Resets no longer cost data: after a reset the band keeps writing into the same hour file, and seconds are saved to flash already 10 s and 30 s after a start. If it restarts 3 times in a row without reaching 10 minutes of running (uploads do not count), it deletes nothing for 30 minutes. So pull a dump at least once every 16 hours if you want every second; the minute file covers everything regardless. `stat` shows `undumped_deleted=` — anything above 0 means some 1 Hz hours were overwritten before you pulled them.

---

## Command list (USB Serial Monitor or BLE UART, one per line)

| Command | What it does |
|---|---|
| `help` | the list below, on the device |
| `stat` | sensors, battery, clock, files, free space, resets, error counters |
| `time <unix>` | set the clock (from `date +%s`) |
| `mark <1-9 or name>` | add a marker; `mark oral 36.85` (or `36,85`) stores the reading and echoes the stored value |
| `dump` | stream every file as text lines (USB: a few minutes, not measured; BLE: very slow, use USB) |
| `dump new` | stream only the hour/raw files not dumped before, plus events.txt and min.bin |
| `dumpmin` | stream only the 1-minute file |
| `dump stop` | stop a dump |
| `raw <seconds>` | record raw infrared PPG at 100 samples/s for 10–1800 s (default 600) into its own file; on USB it also streams live. `raw stop` ends it early |
| `live on` / `live off` | the 1-per-second hex lines on USB on/off (BLE always gets them) |
| `screen` | wake the screen for 15 s |
| `buzz` | test vibration |
| `erase YES` | delete every log file (only between tests! USB only) |
| `format YES` | rebuild the file system — refused unless `stat` says CORRUPT (USB only) |

**The raw PPG recording (do it once on Monday, sitting, then once walking):** type `raw 600`, sit still for 5 minutes, then stand and walk around the room for 5 minutes. This 10-minute recording is what sets the heart-rate detector's thresholds (R4 A7).

---

## Problems

| You see | Do this |
|---|---|
| No XIAO drive after the double-tap | another cable (data cable); try the double-tap again; unplug/replug |
| `storage=NO FLASH` | the flash chip did not answer. Recording still goes to BLE/USB. Type `flashdiag` and send its lines plus the `stat` line with `flash_jedec=`. Then unplug USB **and** the battery for 60 s (a reset or re-flash does not power the flash chip off) and try again. If it stays, flash `flash_unlock.uf2` and send its output |
| `storage=CORRUPT` | the file system on the flash is damaged; `dump` cannot read it. **Do NOT type format** (it erases everything). Tell me first; the 1 Hz stream still goes to BLE/USB, so keep the Serial Monitor or a phone connected meanwhile |
| a sensor shows 0 in `stat` | unplug USB, reseat that part's Qwiic plug, plug in again. The band re-checks missing sensors every minute and logs "SENSOR BACK". A sensor is marked missing only after 3 failed reads in a row |
| screen dark and Serial Monitor silent after flashing | flash **08_logger_nodcdc.uf2** the same way |
| `resets: watchdog=` more than 0 | the band froze and restarted itself. The recording continues in a new file. Tell me the number and roughly when |
| `HR` always 0 or `NO SKIN` while worn | tighten the band; the sensor window must touch the skin |
| Upload from Arduino IDE fails | double-tap reset, pick the port again, Upload (SETUP.md 2.6) |

---

## For the reviewer: what is in this folder

- `08_logger.ino` — the sketch. Pin map, SPI mode-0 fix, I2C high drive, bounded Serial wait, watchdog: unchanged from 07 / R4 PoCs. Since v1.1.0 no Wire and no sensor libraries: every I2C transfer goes through `hg_i2c.c` (TWIM0, deadline per transfer, bus clear); the MAX30102, ICM-20649 and DRV2605L are set up with the same register values the libraries wrote.
- `hg_i2c.c/.h` — the bounded I2C master (host-tested with a mock TWIM).
- `hg_ppg.c/.h`, `hg_ppg_coeffs.h` — copied from `poc_05_hr`, identical except the first line `#include "hg_nofastmath.h"` (checked by `tools/run_host_tests.sh`).
- `hg_nofastmath.h` — included FIRST by every file of the sketch. The Seeed core compiles with `-Ofast`, which makes the compiler assume NaN never happens. In v1.1.1 that turned a missing reading into −327.67 °C and RH 0 instead of "absent" (seen by running the 1.1.1 image in an emulator, `tools/emu_08_nan.py`). Fixed in 1.1.2; `tools/check_nofastmath.sh` proves it for every compiled file.
- `hg_astd.h` — the whole-minute a_std, the same code 09 feeds the guardian.
- `log_format.h` — the 24-byte record (byte table at the top of the file), CRC-8 poly 0x07. **Format v2 since 1.1.2:** z-angle in 0.01° (was whole degrees) and, in minute records, the whole-minute a_std exactly as 09 computes it (`a_std_min_g` in the parsed table) next to the per-second average. v2 records store the CRC XOR 0xFD, so the parser tells v1 and v2 apart by record and old 1.1.1 files still parse.
- `log_ring.c/.h` — which hour file to delete next (pure C, host-tested).
- `build/Seeeduino.nrf52.xiaonRF52840/08_logger_nodcdc.uf2` — the same sketch built with `-DHG_DCDC=0` (`--build-property compiler.cpp.extra_flags=-DHG_DCDC=0`), reports fw `08-logger-1.1.5-nodcdc`. (`08_logger.ino.zip` in that folder is the old 1.1.2 package; use the .uf2 files.)
- `build/Seeeduino.nrf52.xiaonRF52840/08_logger.uf2` — made from `08_logger.ino.hex` with the core's `uf2conv.py -f 0xADA52840 -c` (the Seeed core skips UF2 for the XIAO, so arduino-cli does not make one).
- `BENCH_LOG.md`, `bench_sim/` — the 10-minute bench log, **SIMULATED** (no board here).
- Host tests: `sh ../tools/run_host_tests.sh`.

Record file formats:
- `/log/sNNNN.bin`, `/log/min.bin`: back-to-back 24-byte records (`log_format.h`). Each hour file starts with a header record (marker 12, aux = boot number). Minute records have flag bit 6 set and carry VBAT in byte 20 and (v2) the whole-minute a_std in bytes 21-22, except boot / oral / file minutes, which keep the marker value there.
- `/log/rNNNN.bin`: 308-byte blocks: u32 t_first_ms, u16 n, u16 fs (100), then 100 × 3-byte big-endian IR samples.
- Text stream: record lines = 48 hex characters; `#` lines are comments/events; `E ` lines are events.txt in a dump; `R0`–`R3` lines are the four quarters of a raw block.
