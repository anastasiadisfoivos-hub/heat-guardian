#include "hg_fp.h"   /* T5 D1: first include - IEEE-exact float semantics even under -ffast-math */
#include <math.h>
#include "hg_homeout.h"
#include "hg_guardian_cfg.h"
#include "hg_util.h"

/* AH = 1000 * e / (Rv * T_K), e in Pa -> g/m3 = 2166.79 * e_kPa / (T + 273.15) (ideal gas, Rv = 461.5 J/kgK) */
float hg_abs_humidity(float t, float rh) { return 2166.79f * hg_pa_kpa(t, rh) / (t + 273.15f); }

void hg_homeout_init(hg_homeout_t *h) {
  h->ta_stable = NAN; h->ah_stable = NAN;
  for (int i = 0; i < 6; i++) h->ta_hist[i] = NAN;
  h->score = 0; h->lost_min = 0; h->transit_min = 0; h->state = HG_HO_HOME; h->hi = 0; h->hn = 0; h->have_stable = 0;
  for (int i = 0; i < 24; i++) h->prior[i] = 64;
  h->last_hour = 0xFF; h->out_min_hour = 0; h->mins_hour = 0;
}

uint8_t hg_homeout_step(hg_homeout_t *h, float tair, float rh, uint8_t walking_min, int8_t ble_bucket, uint8_t hour,
                        const uint8_t *forecast72, uint8_t has_forecast) {
  const int tok = !hg_isnan(tair), rok = !hg_isnan(rh);
  float t5 = h->ta_hist[h->hi];                      /* oldest of 6 = 5 min ago once full */
  h->ta_hist[h->hi] = tair; h->hi = (uint8_t)((h->hi + 1) % 6); if (h->hn < 6) h->hn++;
  const float ah = (tok && rok) ? hg_abs_humidity(tair, rh) : NAN;
  int pts = 0;
  if (tok && h->have_stable) {
    float d = fabsf(tair - h->ta_stable);
    if (d >= HG_HO_DT_C2) pts += 5; else if (d >= HG_HO_DT_C1) pts += 3;
  }
  if (!hg_isnan(ah) && h->have_stable && !hg_isnan(h->ah_stable) && fabsf(ah - h->ah_stable) >= HG_HO_DAH) pts += 2;
  if (walking_min >= HG_HO_WALK_BOUT) pts += 2;
  if (ble_bucket == 0) { if (h->lost_min < 60000) h->lost_min++; } else h->lost_min = 0;
  if (ble_bucket == 0 && h->lost_min > HG_HO_LOST_MIN) pts += 4;
  else if (ble_bucket == 1) pts += 1;
  else if (ble_bucket == HG_HO_RSSI_STRONG) pts -= 2;
  if (hour < 24) { if (h->prior[hour] >= 128) pts += 1; else if (h->prior[hour] < 32) pts -= 1; }
  if (has_forecast && forecast72 && hour < 24 && tok) {
    float tin = (float)(int8_t)forecast72[3 * hour];
    if (fabsf(tair - tin) <= HG_HO_FC_NEAR_C) pts -= 5;
  }
  if (walking_min == 0 && pts <= 0) pts -= 1;        /* calm minute at home drifts the score down */
  int sc = h->score - h->score / 8 + pts;            /* leaky integer integrator */
  if (sc < HG_HO_SCORE_MIN) sc = HG_HO_SCORE_MIN;
  if (sc > HG_HO_SCORE_MAX) sc = HG_HO_SCORE_MAX;
  h->score = (int16_t)sc;
  switch (h->state) {
    case HG_HO_HOME:
      if (walking_min >= HG_HO_TRANSIT_WALK && sc >= HG_HO_ENTER_TRANSIT) { h->state = HG_HO_TRANSIT; h->transit_min = 0; }
      break;
    case HG_HO_TRANSIT:
      h->transit_min++;
      if (sc >= HG_HO_ENTER_OUT) h->state = HG_HO_OUT;
      else if (sc <= 0 || h->transit_min > HG_HO_TRANSIT_MAX) h->state = HG_HO_HOME;
      break;
    default: /* OUT */
      if (sc < HG_HO_LEAVE_OUT) { h->state = HG_HO_TRANSIT; h->transit_min = 0; }
      break;
  }
  /* stable indoor reference: only while HOME and the air is steady */
  if (h->state == HG_HO_HOME && tok && h->hn >= 6 && !hg_isnan(t5) && fabsf(tair - t5) < HG_HO_STABLE_DT) {
    if (!h->have_stable) { h->ta_stable = tair; h->ah_stable = ah; h->have_stable = 1; }
    else {
      h->ta_stable = h->ta_stable + HG_HO_STABLE_A * (tair - h->ta_stable);
      if (!hg_isnan(ah)) h->ah_stable = hg_isnan(h->ah_stable) ? ah : h->ah_stable + HG_HO_STABLE_A * (ah - h->ah_stable);
    }
  }
  /* hour prior: EMA of the OUT fraction of each completed hour */
  if (hour < 24) {
    if (h->last_hour < 24 && hour != h->last_hour && h->mins_hour >= 30) {
      int frac = (255 * h->out_min_hour) / h->mins_hour;
      h->prior[h->last_hour] = (uint8_t)((h->prior[h->last_hour] * 7 + frac) / 8);
    }
    if (hour != h->last_hour) { h->out_min_hour = 0; h->mins_hour = 0; h->last_hour = hour; }
    if (h->mins_hour < 255) h->mins_hour++;
    if (h->state == HG_HO_OUT && h->out_min_hour < 255) h->out_min_hour++;
  }
  return h->state;
}
