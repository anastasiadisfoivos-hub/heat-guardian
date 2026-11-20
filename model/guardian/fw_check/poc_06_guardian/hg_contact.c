#include "hg_fp.h"   /* T5 D1: first include - IEEE-exact float semantics even under -ffast-math */
#include <math.h>
#include "hg_contact.h"
#include "hg_guardian_cfg.h"
#include "hg_util.h"
#if HG_CT_RATIO_WIN != 30
#error "ratio[30] in hg_contact.h holds HG_CT_RATIO_WIN minutes (T5 m3)"
#endif

void hg_contact_init(hg_contact_t *c) {
  for (int i = 0; i < HG_CT_RING; i++) { c->t1[i] = NAN; c->t2[i] = NAN; c->ta[i] = NAN; }
  for (int i = 0; i < 30; i++) c->ratio[i] = NAN;
  c->t1_ref = NAN; c->dc_hist[0] = c->dc_hist[1] = c->dc_hist[2] = 0;
  c->ri = 0; c->n5 = 0; c->rti = 0; c->rtn = 0; c->out = 0; c->cand = 0; c->cand_run = 0; c->loose_latch = 0; c->reason = 0;
}

/* mean of the finite values among the 12 samples that end `back` samples before the newest one */
static float mean12(const float *r, uint16_t ri, int back) {
  float s = 0.0f; int n = 0;
  for (int k = 0; k < 12; k++) {
    int idx = ((int)ri - 1 - back - k + 4 * HG_CT_RING) % HG_CT_RING;
    float v = r[idx];
    if (!hg_isnan(v)) { s += v; n++; }
  }
  return n ? s / (float)n : NAN;
}
static float at(const float *r, uint16_t ri, int back) { return r[((int)ri - 1 - back + 4 * HG_CT_RING) % HG_CT_RING]; }

static float median30(const float *v) {
  float a[30]; int n = 0;
  for (int i = 0; i < 30; i++) if (!hg_isnan(v[i])) { float x = v[i]; int j = n++; while (j > 0 && a[j - 1] > x) { a[j] = a[j - 1]; j--; } a[j] = x; }
  if (n == 0) return NAN;
  return (n & 1) ? a[n / 2] : 0.5f * (a[n / 2 - 1] + a[n / 2]);
}

uint8_t hg_contact_step(hg_contact_t *c, const float t1_5s[12], const float t2_5s[12], const float tair_5s[12],
                        float pi, uint8_t ppg_q, uint32_t ppg_dc, float a_std, uint8_t flat_still_min, uint8_t charging) {
  (void)ppg_q; (void)a_std;
  for (int k = 0; k < 12; k++) {
    c->t1[c->ri] = t1_5s[k]; c->t2[c->ri] = t2_5s ? t2_5s[k] : NAN; c->ta[c->ri] = tair_5s[k];
    c->ri = (uint16_t)((c->ri + 1) % HG_CT_RING);
  }
  if (c->n5 < 1000) c->n5 = (uint16_t)(c->n5 + 12);
  const float t1m = mean12(c->t1, c->ri, 0), t2m = mean12(c->t2, c->ri, 0), tam = mean12(c->ta, c->ri, 0);
  const int t1ok = !hg_isnan(t1m), t2ok = !hg_isnan(t2m), taok = !hg_isnan(tam);
  const int hot = taok && tam >= HG_CT_HOT_C;               /* R2 s5 caveat */
  const int thermal = t1ok && taok && !hot;
  c->dc_hist[2] = c->dc_hist[1]; c->dc_hist[1] = c->dc_hist[0]; c->dc_hist[0] = ppg_dc;
  /* per-minute ratio dT/(T1 - T_air) ring (30 min) */
  float r_now = NAN;
  if (thermal && t2ok && (t1m - tam) > HG_CT_RATIO_DEN_MIN) r_now = (t1m - t2m) / (t1m - tam);
  float r_med = median30(c->ratio);
  c->ratio[c->rti] = r_now; c->rti = (uint8_t)((c->rti + 1) % 30); if (c->rtn < 30) c->rtn++;
  int nratio = 0; for (int i = 0; i < 30; i++) if (!hg_isnan(c->ratio[i])) nratio++;
  uint8_t reason = hot ? HG_CT_R_HOT : 0;
  uint8_t cand = 2;
  /* ---------------- OFF ---------------- */
  int off = 0;
  if (charging) { off = 1; reason |= HG_CT_R_CHARGING; }
  if (ppg_dc != 0u && ppg_dc < HG_CT_DC_NOSKIN) { off = 1; reason |= HG_CT_R_NOSKIN; }
  if (flat_still_min >= HG_CT_FLAT_MIN) {
    float t1_10 = (c->n5 >= HG_CT_RING) ? mean12(c->t1, c->ri, HG_CT_RING - 12) : NAN;
    int falling = t1ok && !hg_isnan(t1_10) && (t1m < t1_10 - HG_CT_FALL_C);
    if (hot || falling) { off = 1; reason |= HG_CT_R_FLAT; }  /* in hot rooms only the IMU part is usable */
  }
  if (thermal && tam < HG_CT_OFF_TAIR_MAX) {
    if (t2ok) {
      if (fabsf(t1m - t2m) < HG_CT_OFF_DT_C && fabsf(t1m - tam) <= HG_CT_OFF_NEAR_C && fabsf(t2m - tam) <= HG_CT_OFF_NEAR_C)
        { off = 1; reason |= HG_CT_R_THERMOFF; }
    } else if (fabsf(t1m - tam) <= HG_CT_OFF_NEAR_C) { off = 1; reason |= HG_CT_R_THERMOFF; }   /* no REF board */
  }
  if (off) { cand = 0; c->loose_latch = 0; }
  else {
    /* ---------------- LOOSE ---------------- */
    int loose = 0;
    if (thermal && c->n5 >= HG_CT_STEP_WIN_S5 + 3) {
      /* newest 15-s mean vs the max over the previous 2 min, air change over the same span */
      float now = 0.0f, anow = 0.0f; int n = 0, na = 0;
      for (int k = 0; k < 3; k++) { float v = at(c->t1, c->ri, k), a = at(c->ta, c->ri, k);
        if (!hg_isnan(v)) { now += v; n++; } if (!hg_isnan(a)) { anow += a; na++; } }
      if (n && na) {
        now /= (float)n; anow /= (float)na;
        float mx = -1000.0f, amx = NAN;
        for (int k = 3; k < 3 + HG_CT_STEP_WIN_S5; k++) { float v = at(c->t1, c->ri, k); if (!hg_isnan(v) && v > mx) { mx = v; amx = at(c->ta, c->ri, k); } }
        float drop = now - mx;
        if (mx > -999.0f && !hg_isnan(amx) && drop <= HG_CT_STEP_C && (anow - amx) > HG_CT_AIR_MATCH * drop) {
          loose = 1; reason |= HG_CT_R_STEP;
          if (!c->loose_latch) { c->loose_latch = 1; c->t1_ref = mx; }
        }
      }
    }
    if (c->loose_latch) {
      if (!thermal || (t1ok && t1m >= c->t1_ref - HG_CT_RECOVER_C)) c->loose_latch = 0;
      else { loose = 1; reason |= HG_CT_R_STEP; }
    }
    if (!hg_isnan(r_now) && nratio >= HG_CT_RATIO_MINN && !hg_isnan(r_med) && r_med > 0.0f && r_now < HG_CT_RATIO_DROP * r_med)
      { loose = 1; reason |= HG_CT_R_RATIO; }
    if (!hg_isnan(pi) && pi < HG_CT_PI_LOOSE && ppg_dc != 0u && c->dc_hist[2] != 0u &&
        (float)ppg_dc > HG_CT_DC_RISE * (float)c->dc_hist[2]) { loose = 1; reason |= HG_CT_R_PI; }
    cand = loose ? 1 : 2;
  }
  c->reason = reason;
  /* ---------------- hysteresis (A7.1 step 2: 2 min); the charger pin is trusted immediately ---------------- */
  if (charging) { c->out = 0; c->cand = 0; c->cand_run = 0; return c->out; }
  if (cand == c->out) { c->cand_run = 0; c->cand = cand; }
  else {
    if (cand == c->cand) c->cand_run++; else { c->cand = cand; c->cand_run = 1; }
    if (c->cand_run >= HG_CT_HYST_MIN) { c->out = cand; c->cand_run = 0; }
  }
  return c->out;
}
