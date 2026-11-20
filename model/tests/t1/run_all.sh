#!/bin/bash
cd /home/claude/hg_ai/tests/t1
for s in agree indoor routine sensor rest multiday limits; do
  nice -n 10 python3 -I run_section.py $s > out/log_$s.txt 2>&1
done
echo ALLDONE > out/done.txt
