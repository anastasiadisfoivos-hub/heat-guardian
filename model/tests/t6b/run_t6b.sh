#!/bin/sh
# T6b: rerun every T6b check. Low priority (a sealed exam may share the CPU).
#   sh tests/t6b/run_t6b.sh [<09_guardian.ino.elf>]
# Without an ELF it rebuilds 09 once (arduino-cli, --jobs 1, nice 19, ~6 min) into $TMPDIR/t6b_b09.
set -e
R=/home/claude/hg_ai; T=$R/tests/t6b; G9=$R/fw/09_guardian; O=${TMPDIR:-/tmp}/t6b; mkdir -p $O
N="nice -n 19"
echo "== 1 frozen files vs tag ${HG_FREEZE_TAG:-hg2-freeze-6}";      sh $T/check_frozen.sh
echo "== 1b make_09.py regenerates the committed .ino"; cp $G9/09_guardian.ino $O/ino && python3 $R/fw/tools/make_09.py >/dev/null && cmp $G9/09_guardian.ino $O/ino && echo REGEN_IDENTICAL
echo "== 7 builder host tests";                     TMPDIR=$O $N sh $R/fw/tools/run_host_tests.sh | tail -1
echo "== B5 host + property tests on the frozen copy"
git -C $R show ${HG_FREEZE_TAG:-hg2-freeze-6}:guardian/c/host_test.c > $O/b5_host_test.c
( cd $G9/frozen && $N gcc -std=c99 -Wall -Wextra -Werror -Wdouble-promotion -fsingle-precision-constant -O2 -ffp-contract=off -I. $O/b5_host_test.c \
  hg2_step.c hg2_weights.c hg_contact.c hg_frames.c hg_guardian.c hg_homeout.c hg_kf.c hg_routine.c hg_tables.c hg_util.c -lm -o $O/b5 )
( cd $R/guardian/c && $N $O/b5 ../tests | tail -1 )
echo "== 3 timing";  ( cd $G9 && $N gcc -std=c99 -D_POSIX_C_SOURCE=199309L -O2 -Wno-unknown-pragmas -I. $T/bench.c hg_fw.c fz_*.c -lm -o $O/bench ) && $N $O/bench
echo "== 3 PPG restart"; ( cd $G9 && gcc -O2 -I. $T/ppg_restart.c hg_ppg.c -lm -o $O/ppgr ) && $O/ppgr 70 0.4 | head -1
echo "== 4 safety end to end"; ( cd $G9 && $N gcc -std=c99 -O2 -Wno-unknown-pragmas -I. $T/safety_e2e.c hg_fw.c fz_*.c -lm -o $O/safety ) && $O/safety
echo "== 5 frames"; ( cd $G9 && gcc -std=c99 -O1 -I. -Ifrozen $T/frames_test.c frozen/hg_frames.c frozen/hg_util.c frozen/hg_tables.c -lm -o $O/frames ) && python3 $T/frames_test.py $O/frames
echo "== 6 power ESTIMATE"; python3 $T/power_estimate.py
echo "== B1 fast-math: compiler probe";
GCC=$HOME/.arduino15/packages/Seeeduino/tools/arm-none-eabi-gcc/9-2019q4/bin
cat > $O/probe.c <<'P'
#include "/home/claude/hg_ai/fw/09_guardian/fw_flags.h"
#include <math.h>
int probe_isnan(float x) { return isnan(x); }
P
$GCC/arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 -Ofast -c $O/probe.c -o $O/probe.o && $GCC/arm-none-eabi-objdump -d $O/probe.o | grep -A2 "<probe_isnan>:"
ELF=$1
if [ -z "$ELF" ]; then
  rm -rf $O/sk $O/b09 && mkdir -p $O/sk && cp -r $G9 $O/sk/ && rm -rf $O/sk/09_guardian/build
  $N arduino-cli compile --fqbn Seeeduino:nrf52:xiaonRF52840 --jobs 1 --build-path $O/b09 $O/sk/09_guardian | tail -2
  ELF=$O/b09/09_guardian.ino.elf
fi
python3 -c "import unicorn, elftools" 2>/dev/null || pip install --break-system-packages unicorn pyelftools >/dev/null
( cd $G9/frozen && gcc -std=c99 -O2 -fsingle-precision-constant -ffp-contract=off -DHG_TWIN_USE_HG2_STEP_H=1 -I. $T/hg2_trace_host.c hg2_step.c hg2_weights.c hg_kf.c hg_util.c hg_tables.c hg_twin.c -lm -o $O/h2ref ) && $O/h2ref $O/in.bin $O/out_host.bin
python3 $T/make_scenario.py $O >/dev/null
( cd $G9 && gcc -std=gnu11 -O2 -fsingle-precision-constant -ffp-contract=off -Wno-unknown-pragmas -I. $T/fw_trace_host.c hg_fw.c fz_*.c -lm -o $O/fwhost ) && $O/fwhost $O act_host.bin
echo "== B1 shipped ARM image under emulation"
$N python3 $T/arm_emulate_twin.py $ELF; $N python3 $T/arm_emulate_hg2.py $ELF $O/in.bin $O/out_host.bin; $N python3 $T/arm_emulate_fw.py $ELF $O
