#!/bin/sh
# Full hg2 run for one tag: HG2_SIMVER=v2 HG2_HRAUG=1 sh model/hg2/run_all.sh   (cache must exist: python3 -m model.hg2.build_sim)
set -e
cd /home/claude/hg_ai
python3 -m model.hg2.train --oof | tail -1
for k in 1 2 3 4 5; do python3 -m model.hg2.train --seed $k | tail -1; done
python3 -m model.hg2.train --var | tail -6
python3 -m model.hg2.train --loso | tail -2
python3 -m model.hg2.danger_calib | tail -12
python3 -m model.hg2.eval > /dev/null
python3 -m model.hg2.m5 | tail -20
python3 -m model.hg2.export > /dev/null
echo "run done: $HG2_SIMVER aug=$HG2_HRAUG"
