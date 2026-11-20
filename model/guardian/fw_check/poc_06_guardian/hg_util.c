#include "hg_fp.h"   /* T5 D1: first include - IEEE-exact float semantics even under -ffast-math */
#include "hg_util.h"

int hg_isnan(float x) { return hg_isnan_bits(x); }   /* T5 D1: IEEE bits, no x != x */

static float lerp_tab(const float *tab, int n, float pos) {
  /* pos in table units; clamps to the first/last segment (linear extrapolation beyond the ends) */
  /* T5 D1: the index is clamped BEFORE the float->int cast (NaN / +-inf / huge pos used to give (int) INT_MIN on x86) */
  float pc = (hg_isnan_bits(pos) || pos < 0.0f) ? 0.0f : (pos > (float)(n - 2) ? (float)(n - 2) : pos);
  int i = (int)pc;
  float fr = pos - (float)i;
  return tab[i] + (tab[i + 1] - tab[i]) * fr;
}

/* 26-entry table (ARCH 4.5) with 3-point (quadratic, Newton forward) interpolation: max relative error ~2e-5 vs the
 * exact Magnus formula (linear interpolation gave 4.2e-4 and flipped the env-limit bit at knife-edge minutes vs v1.2). */
float hg_psat_kpa(float t) {
  float pos = t - (float)HG_PSAT_T0;
  float pc = (hg_isnan_bits(pos) || pos < 0.0f) ? 0.0f : (pos > (float)(HG_PSAT_N - 3) ? (float)(HG_PSAT_N - 3) : pos);   /* T5 D1 */
  int i = (int)pc;
  float fr = pos - (float)i;
  float a = HG_PSAT_KPA[i], b = HG_PSAT_KPA[i + 1], c = HG_PSAT_KPA[i + 2];
  return a + fr * (b - a) + (fr * (fr - 1.0f) * 0.5f) * ((c - b) - (b - a));
}
float hg_pa_kpa(float t, float rh) { return rh * 0.01f * hg_psat_kpa(t); }

float hg2_sigmoid_lut(float z) {
  if (z <= -8.0f) return HG_SIG_LUT[0];
  if (z >= 8.0f) return HG_SIG_LUT[32];
  return lerp_tab(HG_SIG_LUT, 33, (z + 8.0f) * 2.0f);
}

float hg_ln1p(float x) {
  if (hg_isnan_bits(x) || x <= 0.0f) return 0.0f;           /* also NaN -> 0 (T5 D1: bit test) */
  float y = 1.0f + x;
  int e = 0;
  while (y >= 2.0f && e < 64) { y *= 0.5f; e++; }   /* exact scaling by powers of two */
  return (float)e * HG_LN2 + lerp_tab(HG_LNM_LUT, 33, (y - 1.0f) * 32.0f);
}

float hg_sin_tod(uint16_t minute) {
  uint16_t m = (uint16_t)(minute % 1440u);
  int i = m / 15;
  float fr = (float)(m % 15u) / 15.0f;
  return HG_SIN_TOD[i] + (HG_SIN_TOD[i + 1] - HG_SIN_TOD[i]) * fr;
}
float hg_cos_tod(uint16_t minute) { return hg_sin_tod((uint16_t)((minute % 1440u) + 360u)); }
