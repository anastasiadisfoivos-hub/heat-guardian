#!/bin/sh
# Proves that every translation unit of a sketch is compiled WITHOUT fast-math, although the Seeed core passes -Ofast.
#   sh fw/tools/check_nofastmath.sh <sketch dir> [<arduino build path>]
# 1. source: every top-level .ino/.c/.cpp has hg_nofastmath.h (directly or through fw_flags.h) as its FIRST #include
# 2. control: the core's arm gcc at -Ofast folds isnan() to "movs r0, #0" without the header and keeps a VCMP with it
# 3. objects (if a build path is given): every sketch object has hg_nofastmath_probe() with a VCMP, and there is one
#    object per source file
set -e
SK=$(cd "$1" && pwd); BP=$2; fail=0
GCC=$HOME/.arduino15/packages/Seeeduino/tools/arm-none-eabi-gcc/9-2019q4/bin
T=${TMPDIR:-/tmp}/nofm.$$; mkdir -p $T
n_src=0
for f in "$SK"/*.ino "$SK"/*.c "$SK"/*.cpp; do
  [ -f "$f" ] || continue; n_src=$((n_src + 1))
  first=$(grep -m1 '^#include' "$f")
  case "$first" in
    *'"hg_nofastmath.h"'*) echo "SRC ok   $(basename $f)";;
    *'"fw_flags.h"'*) grep -m1 '^#include' "$SK/fw_flags.h" | grep -q '"hg_nofastmath.h"' && echo "SRC ok   $(basename $f) (fw_flags.h -> hg_nofastmath.h)" || { echo "SRC FAIL $(basename $f): fw_flags.h does not include hg_nofastmath.h first"; fail=1; };;
    *) echo "SRC FAIL $(basename $f): first include is '$first'"; fail=1;;
  esac
done
F="-mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 -Ofast -c"
printf 'int p(float x) { return __builtin_isnan(x); }\n' > $T/a.c
printf '#include "%s/hg_nofastmath.h"\nint p(float x) { return __builtin_isnan(x); }\n' "$SK" > $T/b.c
$GCC/arm-none-eabi-gcc $F $T/a.c -o $T/a.o; $GCC/arm-none-eabi-gcc $F $T/b.c -o $T/b.o
A=$($GCC/arm-none-eabi-objdump -d $T/a.o | grep -A3 '<p>:' | tail -3 | tr -s ' \t' ' ' | cut -d' ' -f4- | tr '\n' ';')
B=$($GCC/arm-none-eabi-objdump -d $T/b.o | grep -A3 '<p>:' | tail -3 | tr -s ' \t' ' ' | cut -d' ' -f4- | tr '\n' ';')
echo "CONTROL -Ofast without header: $A"
echo "CONTROL -Ofast with header   : $B"
echo "$A" | grep -q 'vcmp' && { echo "CONTROL FAIL: the plain -Ofast build kept the compare (control is not a control)"; fail=1; }
echo "$B" | grep -q 'vcmp' || { echo "CONTROL FAIL: the header did not keep the compare"; fail=1; }
if [ -n "$BP" ]; then
  n_obj=0
  for o in "$BP"/sketch/*.o; do
    n_obj=$((n_obj + 1))
    d=$($GCC/arm-none-eabi-objdump -d "$o" | awk '/<[^>]*hg_nofastmath_probe[^>]*>:/{p=1;next} p&&/^$/{exit} p')
    if echo "$d" | grep -q 'vcmp'; then echo "OBJ ok   $(basename $o): probe keeps vcmp"; else echo "OBJ FAIL $(basename $o): probe folded or missing"; fail=1; fi
  done
  [ $n_obj = $n_src ] || { echo "OBJ FAIL: $n_obj objects for $n_src sources"; fail=1; }
fi
rm -rf $T
[ $fail = 0 ] && echo "CHECK_NOFASTMATH: PASS ($(basename $SK): $n_src sources${BP:+, $n_obj objects})" || { echo "CHECK_NOFASTMATH: FAIL"; exit 1; }
