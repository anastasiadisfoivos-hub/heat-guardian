#!/bin/sh
# The ARM-image checks (need arduino-cli builds; host tests are run_host_tests.sh). Low priority.
#   sh fw/tools/run_arm_checks.sh [<08 build path> <09 build path>]
# 1. check_nofastmath.sh on both sketches (source + every object, if build paths are given)
# 2. emu_08_nan.py: 08's record code run from the 08 ELF with NaN (missing) sensors
# 3. tests/t6b emulators (T6b's Unicorn harness): the 09 ELF == host golden bit for bit (hg2, twin file, full pipeline)
set -e
R=$(cd "$(dirname "$0")/../.." && pwd); N="nice -n 19"; O=${TMPDIR:-/tmp}/hg_arm; mkdir -p $O
E8=$R/fw/08_logger/build/Seeeduino.nrf52.xiaonRF52840/08_logger.ino.elf
E9=$R/fw/09_guardian/build/Seeeduino.nrf52.xiaonRF52840/09_guardian.ino.elf
echo "== 1. no fast-math in any translation unit"
sh $R/fw/tools/check_nofastmath.sh $R/fw/08_logger $1 | tail -1
sh $R/fw/tools/check_nofastmath.sh $R/fw/09_guardian $2 | tail -1
echo "== 2. 08 records with missing sensors (ARM image)"
$N python3 $R/fw/tools/emu_08_nan.py $E8 "08 $(strings $E8 | grep -m1 -o '08-logger-[0-9.]*')" | tail -1
echo "== 3. 09 ARM image vs host golden (tests/t6b)"
T=$R/tests/t6b; G9=$R/fw/09_guardian
python3 $T/make_scenario.py $O >/dev/null
( cd $G9/frozen && gcc -std=c99 -O2 -fsingle-precision-constant -ffp-contract=off -DHG_TWIN_USE_HG2_STEP_H=1 -I. $T/hg2_trace_host.c hg2_step.c hg2_weights.c hg_kf.c hg_util.c hg_tables.c hg_twin.c -lm -o $O/h2ref ) && $O/h2ref $O/in.bin $O/out_host.bin >/dev/null
( cd $G9 && gcc -std=gnu11 -O2 -fsingle-precision-constant -ffp-contract=off -Wno-unknown-pragmas -I. $T/fw_trace_host.c hg_fw.c fz_*.c -lm -o $O/fwhost ) && $O/fwhost $O act_host.bin >/dev/null
$N python3 $T/arm_emulate_twin.py $E9; $N python3 $T/arm_emulate_hg2.py $E9 $O/in.bin $O/out_host.bin; $N python3 $T/arm_emulate_fw.py $E9 $O
