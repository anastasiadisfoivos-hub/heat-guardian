/* Heat Guardian - table maths that replaces libm calls the band does not use (ARCHITECTURE 4.5: no expf/logf/powf).
 * The Python mirror (py/hg_util_py.py) reproduces each function operation-for-operation in float32. */
#ifndef HG_UTIL_H
#define HG_UTIL_H
#include <stdint.h>
#include "hg_tables.h"
#ifdef __cplusplus
extern "C" {
#endif
float hg_psat_kpa(float t);          /* Magnus saturation vapour pressure, 26-entry table 20..45 C, linear (extrapolated) */
float hg_pa_kpa(float t, float rh);  /* rh * 0.01 * psat(t) */
float hg2_sigmoid_lut(float z);      /* display only: 33 entries over [-8, 8], max error 0.003 */
float hg_ln1p(float x);              /* ln(1 + x) for x >= 0 (x < 0 -> 0), max error ~1.2e-4 */
float hg_sin_tod(uint16_t minute);   /* sin(2 pi m / 1440), 97-entry table, linear */
float hg_cos_tod(uint16_t minute);
int   hg_isnan(float x);             /* x != x, written so -ffast-math cannot fold it */
#ifdef __cplusplus
}
#endif
#endif
