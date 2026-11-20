#!/bin/sh
# Source checks for fixes that cannot run on the host (each line failed on the pre-fix sketch da256d5).
#   sh test_static.sh [sketch.ino]
F=${1:-$(dirname "$0")/../08_logger/08_logger.ino}
fail=0
chk() { if eval "$2"; then echo "PASS  $1"; else echo "FAIL  $1"; fail=1; fi; }
chk "M1 reset reason from the core's saved copy (readResetReason)" "grep -q 'resetReason = readResetReason()' '$F'"
chk "M1 RESETREAS is not read directly (init() cleared it)"        "! grep -q 'resetReason = NRF_POWER->RESETREAS' '$F'"
chk "M2 no Wire / sensor libraries (unbounded waits)"               "! grep -Eq '#include <(Wire|MAX30105|Adafruit_DRV2605|Adafruit_ICM20649)\.h>' '$F'"
chk "M2 storage + BLE start before the first I2C transfer"         "awk '/^void setup/{s=1} s&&/storageInit\(\);/{a=NR} s&&/bleSetup\(\);/{b=NR} s&&/hg_i2c_begin/{c=NR} END{exit !(a&&b&&c&&a<c&&b<c)}' '$F'"
chk "M3 QSPI peripheral switched off after deep power-down"        "grep -q 'qspiOff();' '$F' && grep -q 'qspiTr.end()' '$F'"
chk "B1 boot appends to the open hour file"                        "grep -q 'bootHourFile();' '$F' && ! awk '/^void setup/{s=1} s&&/^}/{exit} s&&/  newHourFile\(\);/{f=1} END{exit !f}' '$F'"
chk "m9 PPG drained during flash erase"                            "grep -q 'ppgService(hrDet.motion)' '$F'"
chk "m5 erase/format refused over BLE"                             "grep -q 'ERASE only over USB' '$F' && grep -q 'FORMAT only over USB' '$F'"
chk "n1 quick-boot counter in boot.bin, not GPREGRET (cleared by WDT/pin/BOR)" "grep -q 'quick_boots' '$F' && ! grep -q 'GPREGRET' '$F'"
chk "n2 1 Hz records flushed at 10 s and 30 s of uptime"            "grep -q 'tick == 10000u || tick == 30000u' '$F'"
chk "n3 events logged during an events.txt write are kept"          "grep -q 'memmove(evBuf, evBuf + n' '$F'"
chk "n4 loop bus recovery disables TWIM (hg_i2c_recover)"            "grep -q 'hg_i2c_recover();' '$F' && ! grep -q 'hg_i2c_stats.ok)' '$F'"
chk "0x49 REF sensor status line in stat"                            "grep -q 'REF TMP117 0x49' '$F'"
[ $fail = 0 ] && echo "TEST_STATIC: PASS" || { echo "TEST_STATIC: FAIL"; exit 1; }
