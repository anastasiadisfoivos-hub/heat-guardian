#!/bin/sh
# T5: which functions change code under -ffinite-math-only alone (= NaN/inf-sensitive), ARM Cortex-M4F (band) and x86-64 (host).
# Method: compile each guardian/c file at "-O2 -ffp-contract=off" and at the same + -ffinite-math-only (or + -fassociative-math
# -fno-signed-zeros -fno-trapping-math for the reassociation class), disassemble, diff per function (addresses stripped).
G=/home/claude/hg_ai/guardian/c; W=/home/claude/hg_ai/model/export; O=/home/claude/hg_ai/tests/t5/build/fm; mkdir -p $O
AG=/root/.arduino15/packages/Seeeduino/tools/arm-none-eabi-gcc/9-2019q4/bin
for tgt in arm x86; do
 if [ $tgt = arm ]; then CC="$AG/arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16"; OD=$AG/arm-none-eabi-objdump; else CC=gcc; OD=objdump; fi
 for cls in finite assoc; do
  if [ $cls = finite ]; then X="-ffinite-math-only"; else X="-fassociative-math -fno-signed-zeros -fno-trapping-math -freciprocal-math"; fi
  for f in hg_util hg_kf hg2_step hg_contact hg_homeout hg_routine hg_frames hg_guardian; do
   $CC -std=c99 -O2 -ffp-contract=off -fsingle-precision-constant -ffunction-sections -I$G -I$W -c $G/$f.c -o $O/a.o
   $CC -std=c99 -O2 -ffp-contract=off -fsingle-precision-constant -ffunction-sections $X -I$G -I$W -c $G/$f.c -o $O/b.o
   $OD -d --no-show-raw-insn $O/a.o | sed -E 's/^ +[0-9a-f]+:\s*//; s/<[^>]*>//g; s/#.*$//; s/[0-9a-f]{3,} //g' > $O/a.s
   $OD -d --no-show-raw-insn $O/b.o | sed -E 's/^ +[0-9a-f]+:\s*//; s/<[^>]*>//g; s/#.*$//; s/[0-9a-f]{3,} //g' > $O/b.s
   python3 - $O/a.s $O/b.s $tgt $cls $f <<'PY'
import sys, re
def funcs(p):
    d = {}; cur = None
    for l in open(p):
        m = re.match(r'^[0-9a-f]+ <(.+)>:', l) or re.match(r'^Disassembly of section \.text\.(\S+):', l)
        if m: cur = m.group(1); d.setdefault(cur, []); continue
        if cur and l.strip(): d[cur].append(l.strip())
    return d
a, b = funcs(sys.argv[1]), funcs(sys.argv[2])
ch = [k for k in a if k in b and a[k] != b[k]]
print("%-4s %-7s %-12s changed: %s" % (sys.argv[3], sys.argv[4], sys.argv[5], ", ".join(sorted(set(ch))) or "-"))
PY
  done
 done
done
