#!/bin/bash
# M12 attribution ablations. Builds from a PATCHED SCRATCH COPY of guardian/c (the frozen sources under tag hg2-freeze are
# not modified). Patches: HG_DRINK_PATHS (1 NN-relative, 2 v1.2 ceiling, 3 both = frozen), overridable HG_A_BASE_MIN,
# per-minute raw path conditions in routine_req bits 6 (v1.2 ceiling) / 7 (NN-relative), a_base + a_base_n appended to replay rows.
set -e
HERE=$(cd "$(dirname "$0")" && pwd); S=${SCRATCH:-/tmp/claude-0/m12src}; rm -rf $S; mkdir -p $S/old_w
cp -r $HERE/../../c/* $S/
(cd /home/claude/hg_ai && git show f316ef4:model/export/hg2_weights.c > $S/old_w/hg2_weights.c && git show f316ef4:model/export/hg2_weights.h > $S/old_w/hg2_weights.h)
python3 - "$S" <<'PY'
import sys; S = sys.argv[1]
def patch(p, old, new):
    s = open(p).read(); assert old in s, (p, old[:60]); s = s.replace(old, new, 1); open(p, "w").write(s)
patch(S + "/hg_guardian.c", "  const int c_body1 = (core.valid && f20_v12 >= HG_T_DRINK - low_a) || (thermal_ok && g->a_base_n > 0 && f20_alarm - g->a_base >= HG_A_DELTA - low_a);",
      """  const int c_v12_raw = core.valid && f20_v12 >= HG_T_DRINK - low_a;
  const int c_rel_raw = thermal_ok && g->a_base_n > 0 && f20_alarm - g->a_base >= HG_A_DELTA - low_a;
  g->abl_bits = (uint8_t)((c_v12_raw ? 64 : 0) | (c_rel_raw ? 128 : 0));
  const int c_body1 = ((HG_DRINK_PATHS & 2) && c_v12_raw) || ((HG_DRINK_PATHS & 1) && c_rel_raw);""")
patch(S + "/hg_guardian.c", "  out->routine_req = ro.req;", "  out->routine_req = (uint8_t)(ro.req | g->abl_bits);")
patch(S + "/hg_guardian.h", "  hg2_aux_t *hg2_dbg;", "  uint8_t abl_bits;\n  hg2_aux_t *hg2_dbg;")
patch(S + "/hg_guardian_cfg.h", "#define HG_A_BASE_MIN         (36.8f)", "#ifndef HG_A_BASE_MIN\n#define HG_A_BASE_MIN         (36.8f)\n#endif")
patch(S + "/hg_guardian_cfg.h", "#define HG_A_EMA", "#ifndef HG_DRINK_PATHS\n#define HG_DRINK_PATHS 3\n#endif\n#define HG_A_EMA")
patch(S + "/host_test.c", '      fprintf(fo, ",%d,%d", o.night_heat, o.nudge);', '      fprintf(fo, ",%d,%d,%.9g,%d", o.night_heat, o.nudge, (double)RP.g.a_base, RP.g.a_base_n);')
PY
F="-std=c99 -O2 -ffp-contract=off -fsingle-precision-constant -I$S"
SRC="$S/host_test.c $S/hg_util.c $S/hg_tables.c $S/hg_kf.c $S/hg2_step.c $S/hg_contact.c $S/hg_homeout.c $S/hg_routine.c $S/hg_frames.c $S/hg_guardian.c"
NEW=/home/claude/hg_ai/model/export
B=$HERE/bin; mkdir -p $B
gcc $F -I$NEW -DHG_DRINK_PATHS=1 $SRC $NEW/hg2_weights.c -lm -o $B/a_nn_only
gcc $F -I$NEW -DHG_DRINK_PATHS=2 $SRC $NEW/hg2_weights.c -lm -o $B/b_v12_only
gcc $F -I$NEW -DHG_DRINK_PATHS=3 $SRC $NEW/hg2_weights.c -lm -o $B/c_both
gcc $F -I$NEW -DHG_DRINK_PATHS=3 "-DHG_A_BASE_MIN=(36.3f)" $SRC $NEW/hg2_weights.c -lm -o $B/d_both_base363
gcc $F -I$S/old_w -DHG_DRINK_PATHS=3 $SRC $S/old_w/hg2_weights.c -lm -o $B/e_both_oldweights
echo built; ls $B; grep -o 'HG2_NN_CRC32 0x[0-9A-F]*' $NEW/hg2_weights.h $S/old_w/hg2_weights.h
