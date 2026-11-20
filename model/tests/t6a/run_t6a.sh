#!/bin/sh
# T6a: re-run every tester check for 08_logger (no board needed). ~10 min (compile is ~9 min on 2 CPUs).
#   sh /home/claude/hg_ai/tests/t6a/run_t6a.sh
set -e
T=$(cd "$(dirname "$0")" && pwd); HG=$T/../..; S=${TMPDIR:-/tmp}/t6a; mkdir -p "$S"
LFS=$HOME/.arduino15/packages/Seeeduino/hardware/nrf52/1.1.13/libraries/Adafruit_LittleFS/src/littlefs
echo "== builder host tests"; sh "$HG/fw/tools/run_host_tests.sh" | tail -2
echo "== power-cut / never-format test"
cc -std=gnu99 -O2 -w -I"$HG/fw/08_logger" -I"$LFS" "$T/test_powercut.c" "$LFS/lfs.c" "$LFS/lfs_util.c" "$HG/fw/08_logger/log_ring.c" -o "$S/pc"
"$S/pc" 1 13 | tail -3
echo "== reset loops vs the 1 Hz ring, v1.1.0 boot path, real littlefs (supersedes test_reboot_ring.c, the v1.0 path)"
cc -std=gnu99 -O2 -w -I"$HG/fw/08_logger" -I"$LFS" "$T/test_reboot_v110.c" "$LFS/lfs.c" "$LFS/lfs_util.c" "$HG/fw/08_logger/log_ring.c" -o "$S/rb"; "$S/rb"
echo "== parse_log on appended hour files (v1.1.0)"; mkdir -p "$S/pt"; python3 -I "$T/test_parse_v110.py" "$S/pt"
echo "== (v1.0 evidence only) libc atof edge cases; the v1.1.0 parser is covered by fw/tools/test_cmdparse.c"; cc -std=c99 "$T/parse_edge.c" -lm -o "$S/pe"; "$S/pe"
echo "== rebuild a copy, compare hex and UF2 md5 with the builder's"
rm -rf "$S/rb" && mkdir -p "$S/rb/08_logger" && cp "$HG"/fw/08_logger/*.ino "$HG"/fw/08_logger/*.c "$HG"/fw/08_logger/*.h "$S/rb/08_logger/"
cd /home/claude/hg_fw && arduino-cli compile --fqbn Seeeduino:nrf52:xiaonRF52840 --export-binaries "$S/rb/08_logger" | tail -2
python3 "$HOME/.arduino15/packages/Seeeduino/hardware/nrf52/1.1.13/tools/uf2conv/uf2conv.py" -f 0xADA52840 -c -o "$S/rb/08_logger.uf2" "$S"/rb/08_logger/build/*/08_logger.ino.hex | tail -1
md5sum "$S"/rb/08_logger/build/*/08_logger.ino.hex "$S/rb/08_logger.uf2" "$HG"/fw/08_logger/build/*/08_logger.ino.hex "$HG"/fw/08_logger/build/*/08_logger.uf2
