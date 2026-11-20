#!/bin/sh
# Heat Guardian 08_logger: every host test, in one go. No board needed.
#   sh /home/claude/hg_ai/fw/tools/run_host_tests.sh
# Exit code 0 only if all pass.
set -e
T=$(cd "$(dirname "$0")" && pwd)
FW="$T/../08_logger"
OUT="${TMPDIR:-/tmp}/hg08_host"
mkdir -p "$OUT"
LFS="$HOME/.arduino15/packages/Seeeduino/hardware/nrf52/1.1.13/libraries/Adafruit_LittleFS/src/littlefs"
CFLAGS="-std=c99 -Wall -Wextra -Werror -O2"

echo "== 1. hg_ppg (copied from poc_05: identical except the first line, #include \"hg_nofastmath.h\" (1.1.2)) =="
grep -v '^#include "hg_nofastmath.h"' "$FW/hg_ppg.c" | cmp - "$T/../poc_05_hr/hg_ppg.c" && cmp "$FW/hg_ppg.h" "$T/../poc_05_hr/hg_ppg.h" && cmp "$FW/hg_ppg_coeffs.h" "$T/../poc_05_hr/hg_ppg_coeffs.h" && echo "hg_ppg identical to poc_05 (+ the no-fast-math include)"
gcc -O2 -I"$FW" "$T/../poc_05_hr/host/host_test.c" "$FW/hg_ppg.c" -lm -o "$OUT/ppg"
"$OUT/ppg" | tail -12

echo "== 2. record pack/unpack + CRC-8 (10,000 random records) =="
gcc $CFLAGS -I"$FW" "$T/test_record.c" -o "$OUT/test_record"
"$OUT/test_record" "$T/record_vectors.json"

echo "== 3. ring logic with a mock filesystem (7 days) =="
gcc $CFLAGS -I"$FW" "$T/test_ring.c" "$FW/log_ring.c" -o "$OUT/test_ring"
"$OUT/test_ring"

echo "== 3b. resets never delete undumped hours (T6a B1, model B = the sketch's boot path) =="
gcc $CFLAGS -I"$FW" "$T/test_reboot.c" "$FW/log_ring.c" -o "$OUT/test_reboot"
"$OUT/test_reboot"

echo "== 3c. bounded I2C on a hung bus (T6a M2, mock TWIM) =="
gcc $CFLAGS -DHG_HOST -I"$T" -I"$FW" "$T/test_i2c.c" "$FW/hg_i2c.c" -o "$OUT/test_i2c"
"$OUT/test_i2c"

echo "== 3d. command-line number parsing (T6a m1/m4) =="
gcc $CFLAGS "$T/test_cmdparse.c" -lm -o "$OUT/test_cmdparse"
"$OUT/test_cmdparse"

echo "== 4. real littlefs v1.6 on a RAM flash, sketch write pattern (3 days) =="
cc -std=gnu99 -O2 -w -I"$FW" -I"$LFS" "$T/test_lfs_host.c" "$FW/log_ring.c" "$LFS/lfs.c" "$LFS/lfs_util.c" -o "$OUT/test_lfs"
"$OUT/test_lfs" 3 10

echo "== 5. parse_log.py on SIMULATED streams =="
python3 "$T/test_parse_log.py" | grep -E "^(PASS|FAIL)|TEST_PARSE_LOG"
echo "== 6. source checks for board-only fixes (T6a M1/M2/M3/B1/m5/m9) =="
sh "$T/test_static.sh"
echo "== 6b. 08_logger: every sketch file starts with hg_nofastmath.h (T6b B1; objects: fw/tools/run_arm_checks.sh) =="
sh "$T/check_nofastmath.sh" "$FW" | tail -1
echo "== 7. 09_guardian: frozen inputs byte-identical to tag hg2-freeze-6 =="
sh "$T/sync_frozen.sh" --check | tail -1

echo "== 8. 09_guardian glue (hg_fw.c) with the frozen guardian/twin through the fz_ wrappers =="
G9="$T/../09_guardian"
gcc -std=c99 -O2 -Wall -Wextra -Werror -Wno-unknown-pragmas -I"$G9" "$T/test_fw.c" "$G9/hg_fw.c" "$G9"/fz_*.c -lm -o "$OUT/test_fw"
"$OUT/test_fw" "$OUT/frames.txt"

echo "== 8b. ecosystem layer: 0.9.7 (events, CMD 0x16-0x1A, planner, texts) + 0.9.8 Her Day (CMD 0x1B/0x1C, EVENTS 9/10, day plan, N7/N8, caps, layout) + the app test vectors =="
gcc -std=c99 -O2 -Wall -Wextra -Werror -Wno-unknown-pragmas -I"$G9" "$T/test_eco.c" "$T/test_herday.c" "$G9/hg_fw_eco.c" "$G9"/fz_*.c -lm -o "$OUT/test_eco"
"$OUT/test_eco" "$OUT/eco_vectors.json" "$OUT/herday_vectors.json" > "$OUT/test_eco.txt" || { grep -E "^FAIL" "$OUT/test_eco.txt"; tail -1 "$OUT/test_eco.txt"; exit 1; }
echo "$(grep -c '^PASS' "$OUT/test_eco.txt") checks passed, $(grep -c '^FAIL' "$OUT/test_eco.txt") failed"; grep -E "^TEST_HERDAY" "$OUT/test_eco.txt"; tail -1 "$OUT/test_eco.txt"
cmp "$OUT/eco_vectors.json" "$G9/eco_vectors.json" && echo "eco_vectors.json up to date (0.9.7 frames unchanged)"
cmp "$OUT/herday_vectors.json" "$G9/herday_vectors.json" && echo "herday_vectors.json up to date"
echo "== 8d. 0.9.9 alert quality: validity gate, persistence + hysteresis, two evidence, all-clear, scorecard + 6 staged scenes (fw/09_guardian/scenes) =="
gcc -std=c99 -O2 -Wall -Wextra -Werror -Wno-unknown-pragmas -I"$G9" "$T/test_alerts.c" "$G9/hg_fw.c" "$G9/hg_fw_eco.c" "$G9/hg_fw_alert.c" "$G9"/fz_*.c -lm -o "$OUT/test_alerts"
"$OUT/test_alerts" "$G9/scenes" "$OUT/scenes_table.md" > "$OUT/test_alerts.txt" || { grep -E "^FAIL" "$OUT/test_alerts.txt"; tail -1 "$OUT/test_alerts.txt"; exit 1; }
cat "$OUT/scenes_table.md"; tail -1 "$OUT/test_alerts.txt"
echo "== 8e. 0.9.10 FS-HEAL: heal state machine + the REAL littlefs v1.6 with a poisoned events file (assert -> heal -> new generation) =="
gcc -std=gnu99 -O2 -Wall -Wextra -Werror -I"$G9" -I"$LFS" -c "$T/test_heal.c" -o "$OUT/test_heal.o"
gcc -std=c99 -O2 -Wall -Wextra -Werror -I"$G9" -c "$G9/hg_fw_heal.c" -o "$OUT/hg_fw_heal.o"
cc -std=gnu99 -O2 -w -I"$G9" -I"$LFS" "$OUT/test_heal.o" "$OUT/hg_fw_heal.o" "$G9/log_ring.c" "$LFS/lfs.c" "$LFS/lfs_util.c" -o "$OUT/test_heal"
"$OUT/test_heal" > "$OUT/test_heal.txt" 2> "$OUT/test_heal_asserts.txt" || { grep -E "^FAIL" "$OUT/test_heal.txt"; tail -1 "$OUT/test_heal.txt"; exit 1; }
echo "$(grep -c '^PASS' "$OUT/test_heal.txt") checks passed; expected littlefs asserts from the poisoned file: $(grep -c 'Assertion' "$OUT/test_heal_asserts.txt")"; tail -1 "$OUT/test_heal.txt"
echo "== 8f. 0.9.15 STABLE: reset classes (erratum 136), FS-guard marker ordering model, guard chain, bounded wait, verified wake, VBAT filter =="
gcc -std=c99 -O2 -Wall -Wextra -Werror -I"$G9" "$T/test_stable.c" "$G9/hg_fw_stable.c" "$G9/hg_fw_heal.c" -lm -o "$OUT/test_stable"
"$OUT/test_stable" > "$OUT/test_stable.txt" || { grep -E "^FAIL" "$OUT/test_stable.txt"; tail -1 "$OUT/test_stable.txt"; exit 1; }
echo "$(grep -c '^PASS' "$OUT/test_stable.txt") checks passed"; tail -1 "$OUT/test_stable.txt"
echo "== 8g. 0.9.15 flash glue: the REAL littlefs v1.6 over a chip that falls asleep, 0.9.14 glue (returns 0) vs 0.9.15 glue (LFS_ERR_IO) =="
cc -std=gnu99 -O2 -w -I"$LFS" "$T/test_flashio.c" "$LFS/lfs.c" "$LFS/lfs_util.c" -o "$OUT/test_flashio"
"$OUT/test_flashio" 200 400
echo "== 8h. 0.9.16 BOOT GUARD: journal words (CRC-4, torn writes), ladder, plans, ledger, simulated NOR page (fault loop, copies, compaction), 200,000 random boots, supervisor =="
gcc -std=c99 -O2 -Wall -Wextra -Werror -I"$G9" "$T/test_bootguard.c" "$G9/hg_bootguard.c" "$G9/hg_fw_stable.c" "$G9/hg_fw_heal.c" -o "$OUT/test_bootguard"
"$OUT/test_bootguard" > "$OUT/test_bootguard.txt" || { grep -E "^FAIL" "$OUT/test_bootguard.txt"; tail -1 "$OUT/test_bootguard.txt"; exit 1; }
echo "$(grep -c '^PASS' "$OUT/test_bootguard.txt") checks passed"; tail -1 "$OUT/test_bootguard.txt"
echo "== 8i. 0.9.17 UI: button (press / hold 3 s HELP / cancel lock / double press off prompt / refusals, every timing edge, 20,000 random streams, uptime wrap), haptic sequencer, wrist raise =="
gcc -std=c99 -O2 -Wall -Wextra -Werror -I"$G9" "$T/test_ui.c" "$G9/hg_fw_ui.c" -lm -o "$OUT/test_ui"
"$OUT/test_ui" > "$OUT/test_ui.txt" || { grep -E "^FAIL" "$OUT/test_ui.txt"; tail -1 "$OUT/test_ui.txt"; exit 1; }
echo "$(grep -c '^PASS' "$OUT/test_ui.txt") checks passed"; tail -1 "$OUT/test_ui.txt"
echo "== 8j. 0.9.17 action ladder (worked / not worked / no press / Danger / a press never cancels), keep-it-green gauge, Her-Day-only planner =="
gcc -std=c99 -O2 -Wall -Wextra -Werror -Wno-unknown-pragmas -I"$G9" "$T/test_ladder.c" "$G9/hg_fw_ladder.c" "$G9/hg_fw_ui.c" "$G9/hg_fw_eco.c" "$G9"/fz_*.c -lm -o "$OUT/test_ladder"
"$OUT/test_ladder" > "$OUT/test_ladder.txt" || { grep -E "^FAIL" "$OUT/test_ladder.txt"; tail -1 "$OUT/test_ladder.txt"; exit 1; }
echo "$(grep -c '^PASS' "$OUT/test_ladder.txt") checks passed"; tail -1 "$OUT/test_ladder.txt"
echo "== 8k. [FW-DEMO] 0.9.17-demo replay: the embedded SIMULATED heat episode (hg_demo_trace.h) through hg_fw + the frozen guardian + alerts + planner + ladder + gauge, as the band runs it =="
gcc -std=c99 -O2 -Wall -Wextra -Werror -Wno-unknown-pragmas -I"$G9" "$T/test_demo.c" "$G9/hg_fw_demo.c" "$G9/hg_fw.c" "$G9/hg_fw_eco.c" "$G9/hg_fw_alert.c" "$G9/hg_fw_ladder.c" "$G9/hg_fw_ui.c" "$G9"/fz_*.c -lm -o "$OUT/test_demo"
"$OUT/test_demo" 2 "$OUT/demo_table.md" 31,70 > "$OUT/test_demo.txt" || { tail -3 "$OUT/test_demo.txt"; exit 1; }
grep -E "ALERT|ALL-CLEAR|nudge|GAUGE|LADDER" "$OUT/test_demo.txt" | cut -c1-14,96-; grep "SIM marker" "$OUT/test_demo.txt"; tail -1 "$OUT/test_demo.txt"
grep -q "pid 90862 (velders" "$G9/hg_demo_trace.h" && grep -q '#define HG_DEMO_ELDER "velders-pid90862"' "$G9/hg_fw_demo.h" || { echo "FAIL: HG_DEMO_ELDER does not name the trace's person"; exit 1; }   # [DEMO-NORESP] `#R start el=`
"$OUT/test_demo" 2 "" "" noresp > "$OUT/test_demo_noresp.txt" || { tail -3 "$OUT/test_demo_noresp.txt"; exit 1; }   # [DEMO-NORESP] replay noresp
grep -E "LADDER|SIM marker" "$OUT/test_demo_noresp.txt" | cut -c1-14,96-; tail -1 "$OUT/test_demo_noresp.txt"
echo "== 8c. 0.9.8 Her Day + 0.9.9 all-clear texts: every glyph in the band font (u8g2_font_10x20_t_greek) =="
U8G2="$HOME/Arduino/libraries/U8g2/src/clib"
gcc -std=c99 -O1 -w -I"$U8G2" -I"$G9" "$T/test_herday_glyphs.c" "$G9/hg_fw_eco.c" "$G9/hg_fw_alert.c" "$G9/hg_fw_ladder.c" "$G9/hg_fw_ui.c" "$G9"/fz_hg_frames.c "$G9"/fz_hg_util.c "$G9"/fz_hg_tables.c "$U8G2"/u8g2_font.c "$U8G2"/u8g2_fonts.c "$U8G2"/u8g2_setup.c "$U8G2"/u8g2_d_setup.c "$U8G2"/u8g2_d_memory.c "$U8G2"/u8g2_buffer.c "$U8G2"/u8g2_hvline.c "$U8G2"/u8g2_ll_hvline.c "$U8G2"/u8g2_intersection.c "$U8G2"/u8x8_*.c "$U8G2"/u8g2_kerning.c -lm -o "$OUT/test_herday_glyphs"
"$OUT/test_herday_glyphs" | tail -1

echo "== 9. dashboard decoder (JS) == B5 Python unpacker; guardian log records =="
python3 "$T/test_dashboard.py" "$OUT/frames.txt" | grep -E "PASS|FAIL"
echo "== 10. 09_guardian source checks (acceptance 2-4) =="
sh "$T/test_static_09.sh" | tail -1
echo "ALL HOST TESTS PASSED"
