/* [B2-fix] input/output guards for hg2 (C99, no isfinite/expf needed). B5: call hg2_guard_f on every float field of
 * hg2_in_t before hg2_step, and hg2_clampf on the outputs, exactly as model/hg2/features.py and export.outputs() do.
 *   t1_c, t2_c, t_air_c : hg2_guard_f(x, -40, 85)      rh_pct : (0, 100)      pi_pct : (0, 100)
 *   a_std_g             : hg2_guard_f(x, 0, 16)        hr_bpm : finite else NAN (the 30..220 gate stays in hg2_step)
 *   outputs: core_* / f20_eff / f30_eff clamp 30..45, sd_* 0..3, logit_* -100..100, strain 0..10.
 * A comparison with NaN is false and +-inf fails the range test, so both map to "not available". */
#ifndef HG2_GUARD_H
#define HG2_GUARD_H
#include <math.h>
static inline float hg2_guard_f(float x, float lo, float hi) { return (x >= lo && x <= hi) ? x : NAN; }
static inline float hg2_finite_or_nan(float x) { return (x == x && x <= 3.4e38f && x >= -3.4e38f) ? x : NAN; }
static inline float hg2_clampf(float x, float lo, float hi) { return !(x >= lo) ? lo : (x > hi ? hi : x); }
/* z-score guard: NaN or +-inf feature -> z = 0 */
static inline float hg2_z_guard(float z) { return (z == z && z <= 3.4e38f && z >= -3.4e38f) ? z : 0.0f; }
#endif
