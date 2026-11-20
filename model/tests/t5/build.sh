#!/bin/sh
# T5: out-of-tree host builds of the frozen guardian/c (hg2-freeze-3). Nothing is written under guardian/.
set -e
G=/home/claude/hg_ai/guardian/c
W=/home/claude/hg_ai/model/export
B=/home/claude/hg_ai/tests/t5/build
mkdir -p $B
FILES="hg_util.c hg_tables.c hg_kf.c hg2_step.c hg_contact.c hg_homeout.c hg_routine.c hg_frames.c hg_guardian.c"
BASE="-std=c99 -Wall -Wextra -Wdouble-promotion -fsingle-precision-constant -I$G -I$W"
O2="-O2 -ffp-contract=off"             # = guardian/c/Makefile CFLAGS (+ -Werror below)
cd $G
SRC=""; for f in $FILES; do SRC="$SRC $G/$f"; done
gcc $BASE -Werror $O2 host_test.c $SRC $W/hg2_weights.c -lm -o $B/host_O2
gcc $BASE -Werror -O2 host_test.c $SRC $W/hg2_weights.c -lm -o $B/host_O2_brief          # brief flags (no -ffp-contract=off)
gcc $BASE -Ofast -ffast-math host_test.c $SRC $W/hg2_weights.c -lm -o $B/host_Ofast
gcc $BASE -Ofast -ffast-math -fno-finite-math-only host_test.c $SRC $W/hg2_weights.c -lm -o $B/host_Ofast_nofinite
gcc $BASE -O2 -ffp-contract=off -ffinite-math-only host_test.c $SRC $W/hg2_weights.c -lm -o $B/host_O2_finite
# per-file bisection: exactly one file at -Ofast, everything else (incl. host_test.c) at the Makefile flags
for f in $FILES hg2_weights.c; do
  rm -f $B/obj_*.o
  for g in $FILES; do
    if [ "$g" = "$f" ]; then fl="-Ofast -ffast-math"; else fl="$O2"; fi
    gcc $BASE $fl -c $G/$g -o $B/obj_$g.o
  done
  if [ "$f" = "hg2_weights.c" ]; then fl="-Ofast -ffast-math"; else fl="$O2"; fi
  gcc $BASE $fl -c $W/hg2_weights.c -o $B/obj_w.o
  gcc $BASE $O2 -c host_test.c -o $B/obj_host.o
  gcc $B/obj_*.o -lm -o $B/host_only_${f%.c}
done
rm -f $B/obj_*.o
echo built: $(ls $B)
