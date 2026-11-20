#!/bin/sh
# B2 export checks: host test (C == Python test vectors) + arduino-cli compile of poc_02_hg2 with the trained weights.
set -e
E=/home/claude/hg_ai/model/export; S=/home/claude/hg_ai/model/fw_check/poc_02_hg2
cd $E && gcc -std=c99 -Wall -Wextra -Werror -Wdouble-promotion -fsingle-precision-constant -O2 -ffp-contract=off \
  -I. -Ihost host/host_test.c host/hg2_nn.c hg2_weights.c -lm -o host/host_test && host/host_test
cp $E/hg2_weights.c $E/hg2_weights.h $E/host/hg2_nn.c $E/host/hg2_nn.h $S/
cd /home/claude/hg_fw && arduino-cli compile --fqbn Seeeduino:nrf52:xiaonRF52840 $S 2>&1 | tail -4
arm-none-eabi-size 2>/dev/null || true
