#!/bin/bash
# Builds the M7 evaluation binaries against whatever is in model/export now (stub if absent) and records its CRC/version.
set -e
cd "$(dirname "$0")/../c"
W=../../model/export; [ -f $W/hg2_weights.h ] || W=stub
F="-std=c99 -Wall -Wextra -Werror -Wdouble-promotion -fsingle-precision-constant -O2 -ffp-contract=off -I. -I$W"
S="host_test.c hg_util.c hg_tables.c hg_kf.c hg2_step.c hg_contact.c hg_homeout.c hg_routine.c hg_frames.c hg_guardian.c $W/hg2_weights.c -lm"
mkdir -p build
b() { gcc $F $2 $S -o build/m7_$1; }
rm -f build/m7_*
if [ "$1" = "final" ]; then   # M11: the default (to-be-frozen) build only
  b default     ""
elif [ "$1" = "m19" ]; then   # M19: Marble + Exception DRINK (default) vs the hg2-freeze-4 rules
  b default     ""
  b freeze4     "-DHG_MARBLE=0 -DHG_PD=1 -DHG_DRINK_DESIGN=1"
  b m19a        "-DHG_MB_JUMP_RISE=0 -DHG_COOL_TRANSIT=0"   # M19b: = ea8f8a1 (two-sided jump, COOL stepping stone shown)
elif [ "$1" = "m13" ]; then   # M13: Danger-by-persistence X sweep 20/30/45 min + the hg2-freeze-2 rule (no persistence)
  b pd_off      "-DHG_PD=0"
  for x in 20 30 45; do b pd_$x "-DHG_PD=1 -DHG_PD_COOL_MIN=$x"; done
elif [ "$1" = "m12" ]; then   # M12: heat-context gate sweep T_ctx 28/29/30 C + the ungated hg2-freeze rule
  b ctx_off     "-DHG_V12_CTX=0"
  for t in 28 29 30; do b ctx_$t "-DHG_V12_CTX=1 -DHG_V12_CTX_C=(${t}.0f)"; done
elif [ "$1" = "m9" ]; then   # M9: part (i) alone + the default build
  b base_r0     "-DHG_DRINK_DESIGN=0 -DHG_M7_ROUTINE=0"
  b base_i      "-DHG_DRINK_DESIGN=0 -DHG_M7_ROUTINE=1"
  b A030_r0     "-DHG_DRINK_DESIGN=1 -DHG_M7_ROUTINE=0"
  b default     ""
else
  b base_r0 "-DHG_DRINK_DESIGN=0 -DHG_M7_ROUTINE=0"
  b base    "-DHG_DRINK_DESIGN=0 -DHG_M7_ROUTINE=1"
  for d in 0.30 0.40 0.50; do b A_$d "-DHG_DRINK_DESIGN=1 -DHG_M7_ROUTINE=1 -DHG_A_DELTA=(${d}f)"; b C_$d "-DHG_DRINK_DESIGN=3 -DHG_M7_ROUTINE=1 -DHG_A_DELTA=(${d}f)"; done
  b B       "-DHG_DRINK_DESIGN=2 -DHG_M7_ROUTINE=1"
fi
CRC=$(grep -o 'HG2_NN_CRC32 0x[0-9A-Fa-f]*' $W/hg2_weights.h | awk '{print $2}'); VER=$(grep -o 'HG2_NN_VERSION "[^"]*"' $W/hg2_weights.h | cut -d'"' -f2)
HC=$(grep -c HG2_CONF_HALF_CAL $W/hg2_weights.h || true)
python3 - "$CRC" "$VER" "$W" "$HC" <<'PY'
import json, sys, glob, os
crc, ver, w, hc = sys.argv[1:]
cfg = {os.path.basename(p)[3:]: os.path.basename(p) for p in sorted(glob.glob("build/m7_*")) if os.access(p, os.X_OK) and not p.endswith(".json")}
json.dump(dict(weights=dict(crc=crc, version=ver, dir=w, has_conf_half_cal=hc != "0"), configs=cfg), open("build/m7_builds.json", "w"), indent=1)
print(crc, ver, "HG2_CONF_HALF_CAL" if hc != "0" else "no HG2_CONF_HALF_CAL", sorted(cfg))
PY
