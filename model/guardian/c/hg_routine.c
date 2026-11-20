#include "hg_fp.h"   /* T5 D1: first include - IEEE-exact float semantics even under -ffast-math */
#include <math.h>
#include <string.h>
#include "hg_routine.h"
#include "hg_guardian_cfg.h"
#include "hg_util.h"

static void wf_init(hg_welford_t *w) { w->n = 0.0f; w->mean = 0.0f; w->m2 = 0.0f; }
static void wf_add(hg_welford_t *w, float x) {
  const float cap = (float)HG_RT_WELFORD_NCAP;
  if (w->n < cap) w->n += 1.0f; else w->m2 = w->m2 * ((cap - 1.0f) / cap);
  float d = x - w->mean;
  w->mean += d / w->n;
  w->m2 += d * (x - w->mean);
}
static float wf_sd(const hg_welford_t *w) { return w->n >= 2.0f ? sqrtf(w->m2 / (w->n - 1.0f)) : 0.0f; }

void hg_routine_init(hg_routine_t *r) {
  for (int h = 0; h < 24; h++) { wf_init(&r->am[h]); wf_init(&r->q[h]); r->maxq[h] = 0; }
  for (int i = 0; i < 288; i++) r->med5[i] = 255;
  for (int i = 0; i < 36; i++) r->med5_ok[i] = 0;
  for (int i = 0; i < 60; i++) r->dz[i] = 0;
  for (int i = 0; i < 7; i++) r->wake_hist[i] = 0;
  r->last_z = NAN;
  r->sleep_on = HG_RT_SLEEP_DEF_ON; r->sleep_off = HG_RT_SLEEP_DEF_OFF;
  r->qrun = 0; r->q_hour_max = 0; r->last_mod = 0xFFFF; r->act10 = 0;
  r->sleep_valid = 0; r->n_wake = 0; r->wake_i = 0; r->days_learned = 0;
  r->dzn = 0; r->block_ok = 0; r->block_idx = 0xFFFF; r->cur_hour = 0xFF;
  r->act_in_hour = 0; r->hour_minutes = 0; r->hour_clean = 0; r->last_hour_done = 0xFF;
  r->last_hour_act = 0; r->awake_today = 0; r->impact_pending = 0; r->score = 255; r->last_req = 0; r->hdcza_thr = 0;
  r->prev_asleep = 0; r->night_worn = 0; r->imp_still = 0;
}

static int in_window(uint16_t m, uint16_t on, uint16_t off) {
  if (on <= off) return m >= on && m < off;
  return m >= on || m < off;                              /* window wraps past midnight */
}
static int popc16(uint16_t v) { int n = 0; while (v) { v &= (uint16_t)(v - 1u); n++; } return n; }

static uint16_t median_wake(const hg_routine_t *r) {
  if (r->n_wake == 0) return HG_RT_W_DEFAULT;
  uint16_t a[7]; int n = r->n_wake;
  for (int i = 0; i < n; i++) { uint16_t x = r->wake_hist[i]; int j = i; while (j > 0 && a[j - 1] > x) { a[j] = a[j - 1]; j--; } a[j] = x; }
  return a[(n - 1) / 2];                                  /* lower median */
}

void hg_routine_noon(hg_routine_t *r) {
  /* chronological order: block 144 (12:00 yesterday) .. 287, 0 .. 143 (11:55 today) */
  uint8_t fl[288];
  int nok = 0;
  for (int c = 0; c < 288; c++) { int b = (c + 144) % 288; if (r->med5_ok[b >> 3] & (1u << (b & 7))) nok++; }
  if (nok < HG_HDCZA_MIN_WORN) return;
  int k = (nok * HG_HDCZA_PCT + 99) / 100;                /* nearest-rank 10th percentile */
  int cum = 0, p10 = 0;
  for (int v = 0; v < 256; v++) {
    for (int b = 0; b < 288; b++) if ((r->med5_ok[b >> 3] & (1u << (b & 7))) && r->med5[b] == v) cum++;
    if (cum >= k) { p10 = v; break; }
  }
  int thr = HG_HDCZA_MULT * p10;
  if (thr < HG_HDCZA_THR_MIN) thr = HG_HDCZA_THR_MIN;
  if (thr > HG_HDCZA_THR_MAX) thr = HG_HDCZA_THR_MAX;
  r->hdcza_thr = (uint8_t)thr;
  for (int c = 0; c < 288; c++) {
    int b = (c + 144) % 288;
    fl[c] = (uint8_t)(((r->med5_ok[b >> 3] & (1u << (b & 7))) && r->med5[b] < thr) ? 1 : 0);
  }
  /* remove inactive runs <= 30 min */
  for (int c = 0; c < 288;) {
    if (!fl[c]) { c++; continue; }
    int e = c; while (e < 288 && fl[e]) e++;
    if (e - c <= HG_HDCZA_MINBLK) for (int i = c; i < e; i++) fl[i] = 0;
    c = e;
  }
  /* fill active gaps < 60 min that sit between two inactive runs */
  for (int c = 0; c < 288;) {
    if (fl[c]) { c++; continue; }
    int e = c; while (e < 288 && !fl[e]) e++;
    if (c > 0 && e < 288 && (e - c) < HG_HDCZA_MAXGAP) for (int i = c; i < e; i++) fl[i] = 1;
    c = e;
  }
  int best = 0, bs = -1;
  for (int c = 0; c < 288;) {
    if (!fl[c]) { c++; continue; }
    int e = c; while (e < 288 && fl[e]) e++;
    if (e - c > best) { best = e - c; bs = c; }
    c = e;
  }
  if (bs < 0) return;
  r->sleep_on = (uint16_t)((((bs + 144) % 288) * 5) % 1440);
  r->sleep_off = (uint16_t)((((bs + best + 144) % 288) * 5) % 1440);
  r->sleep_valid = 1;
  r->wake_hist[r->wake_i] = r->sleep_off; r->wake_i = (uint8_t)((r->wake_i + 1) % HG_RT_WAKE_HIST);
  if (r->n_wake < HG_RT_WAKE_HIST) r->n_wake++;
  if (r->days_learned < 255) r->days_learned++;
}

void hg_routine_step(hg_routine_t *r, const hg_routine_in_t *in, hg_routine_out_t *out) {
  out->req = 0; out->asleep = 0; out->thr = 0; out->wake_deadline = 0;
  const uint16_t mod = in->minute_of_day;
  if (mod >= 1440u) {                                     /* time unknown: routine disabled, nothing learned */
    out->routine_score = 255; out->q = r->qrun; r->last_z = NAN; r->dzn = 0; r->block_ok = 0; r->block_idx = 0xFFFF;
    r->cur_hour = 0xFF; r->impact_pending = 0; r->imp_still = 0; r->last_mod = 0xFFFF; return;
  }
  const int worn = in->worn == 2;
  const float astd = hg_isnan(in->a_std_g) ? 0.0f : in->a_std_g;
  const int active = astd > HG_ACTIVE_G, still = astd <= HG_STILL_G;
  /* --- day boundaries --- */
  if (r->last_mod != 0xFFFF && mod < r->last_mod && r->last_mod - mod >= HG_MIDNIGHT_MIN_STEP) r->awake_today = 0;   /* midnight (T5 m1) */
  if (r->last_mod != 0xFFFF && r->last_mod < 720u && mod >= 720u) hg_routine_noon(r);   /* noon recompute */
  /* --- HDCZA 5-s angle changes into 5-min blocks --- */
  const uint16_t bi = (uint16_t)(mod / 5u);
  if (bi != r->block_idx) { r->block_idx = bi; r->dzn = 0; r->block_ok = 1; }
  if (!worn || !in->zangle_5s) { r->block_ok = 0; r->last_z = NAN; }
  else for (int k = 0; k < 12; k++) {
    float z = in->zangle_5s[k];
    if (!hg_isnan(z) && !hg_isnan(r->last_z) && r->dzn < 60) {
      float d = fabsf(z - r->last_z) * 100.0f + 0.5f;
      r->dz[r->dzn++] = (uint8_t)(d >= 255.0f ? 255.0f : floorf(d));
    }
    r->last_z = z;
  }
  if (mod % 5u == 4u) {
    int okb = r->block_ok && r->dzn >= 30;
    if (okb) {
      uint8_t a[60]; int n = r->dzn;
      for (int i = 0; i < n; i++) { uint8_t x = r->dz[i]; int j = i; while (j > 0 && a[j - 1] > x) { a[j] = a[j - 1]; j--; } a[j] = x; }
      r->med5[bi] = a[(n - 1) / 2];
      r->med5_ok[bi >> 3] = (uint8_t)(r->med5_ok[bi >> 3] | (1u << (bi & 7)));
    } else { r->med5[bi] = 255; r->med5_ok[bi >> 3] = (uint8_t)(r->med5_ok[bi >> 3] & ~(1u << (bi & 7))); }
    r->dzn = 0; r->block_ok = 0;
  }
  /* --- sleep window and the awake quiet run --- */
  const int asleep = in_window(mod, r->sleep_on, r->sleep_off);
  /* T5 D5: worn minutes of THIS sleep window (reset when the window starts or is first seen after a boot) */
  if (asleep && !r->prev_asleep) r->night_worn = 0;
  if (asleep && worn && r->night_worn < 1440) r->night_worn++;
  r->prev_asleep = (uint8_t)asleep;
  const int quiet_off = asleep;   /* M9.3: the M7.3 (ii) widened suppression was removed */
  if (active || quiet_off) r->qrun = 0; else if (worn && r->qrun < 1440) r->qrun++;
  /* --- hourly learning --- */
  const uint8_t h = (uint8_t)(mod / 60u);
  if (h != r->cur_hour) {
    if (r->cur_hour < 24 && r->hour_clean && r->hour_minutes >= 60) {
      wf_add(&r->am[r->cur_hour], (float)r->act_in_hour);
      wf_add(&r->q[r->cur_hour], (float)r->q_hour_max);
      if ((int16_t)r->q_hour_max > r->maxq[r->cur_hour]) r->maxq[r->cur_hour] = (int16_t)r->q_hour_max;
    }
    if (r->cur_hour < 24) {
      /* routine score from the hour just completed (R3 s3.4 step 3; A7.1: 255 - min(255, 64 max z)) */
      const hg_welford_t *w = &r->am[r->cur_hour];
      int sc = 255;
      if (r->hour_minutes >= 60 && w->n >= (float)HG_RT_LEARN_DAYS && w->mean >= HG_RT_ACTIVE_HOUR_MIN &&
          !in_window((uint16_t)(r->cur_hour * 60u + 30u), r->sleep_on, r->sleep_off)) {
        float sd = wf_sd(w); if (sd < HG_RT_SD_FLOOR_AM) sd = HG_RT_SD_FLOOR_AM;
        float zz = (w->mean - (float)r->act_in_hour) / sd;
        if (zz > 0.0f) { float p = 64.0f * zz; sc = p >= 255.0f ? 0 : 255 - (int)p; }
      }
      r->score = (uint8_t)sc; r->last_hour_act = r->act_in_hour; r->last_hour_done = r->cur_hour;
    }
    r->cur_hour = h; r->act_in_hour = 0; r->hour_minutes = 0; r->hour_clean = 1; r->q_hour_max = 0;
  }
  if (r->hour_minutes < 255) r->hour_minutes++;
  if (active && r->act_in_hour < 255) r->act_in_hour++;
  if (r->qrun > r->q_hour_max) r->q_hour_max = r->qrun;
  if (!worn || in->frozen) r->hour_clean = 0;
  /* --- wake detection (DESIGN: >= 3 ACTIVE minutes in a 10-min window, from W - 3 h on) --- */
  r->act10 = (uint16_t)(((r->act10 << 1) | (active ? 1u : 0u)) & 0x3FFu);
  const uint16_t W = median_wake(r);
  const int from = (int)W - HG_RT_WAKE_LOOKBACK;
  if ((int)mod >= (from < 0 ? 0 : from) && popc16(r->act10) >= HG_RT_WAKE_ACT) r->awake_today = 1;
  /* --- rules --- */
  uint8_t req = 0;
  if (worn) {
    const int heat = (!hg_isnan(in->t_in) && in->t_in >= HG_RT_HEAT_TIN) || in->cool_on;   /* rule (c) */
    if (!quiet_off) {                                                                       /* rule (a) */
      int thr = -1;
      if (r->am[h].n >= (float)HG_RT_LEARN_DAYS) {
        static const int16_t B[5] = { HG_RT_B2, HG_RT_B1, HG_RT_B0, HG_RT_B1, HG_RT_B2 };
        for (int d = -2; d <= 2; d++) {
          int hh = ((int)h + d + 24) % 24;
          if (r->am[hh].n < (float)HG_RT_LEARN_DAYS) continue;
          int b = heat ? B[d + 2] / 2 : B[d + 2];
          int t = r->maxq[hh] + b;
          if (t > thr) thr = t;
        }
      } else thr = heat ? HG_RT_FALLBACK_MIN / 2 : HG_RT_FALLBACK_MIN;
      out->thr = (uint16_t)thr;
      if ((int)r->qrun > thr) req |= HG_RT_REQ_QUIET;
    }
    int D = (int)W + (in->heat_day ? HG_RT_NOWAKE_HEAT_MIN : HG_RT_NOWAKE_MIN);              /* rule (b) */
    if (D > HG_RT_NOWAKE_CAP) D = HG_RT_NOWAKE_CAP;
    out->wake_deadline = (uint16_t)D;
    const int win = r->sleep_off >= r->sleep_on ? r->sleep_off - r->sleep_on : 1440 - r->sleep_on + r->sleep_off;
    const int night_seen = 100 * (int)r->night_worn >= HG_RT_NOWAKE_WORN_PCT * win;                  /* T5 D5 */
    if ((int)mod >= D && mod < 720u && !r->awake_today && night_seen) req |= HG_RT_REQ_NOWAKE;
  }
  /* rule (d), M19-impact: impact, then HG_IMPACT_STILL_MIN consecutive STILL worn minutes with no press -> CHECK input (once);
   * any movement, press or loss of contact before that cancels it */
  if (r->impact_pending) {
    if (!worn || !still || in->button) { r->impact_pending = 0; r->imp_still = 0; }
    else if (++r->imp_still >= HG_IMPACT_STILL_MIN) { req |= HG_RT_REQ_IMPACT; r->impact_pending = 0; r->imp_still = 0; }
  }
  if (in->impact && worn) { r->impact_pending = 1; r->imp_still = 0; }
  if (req) r->hour_clean = 0;                             /* GE: readings that caused an alert are not learned */
  r->last_req = req; r->last_mod = mod;
  out->req = req; out->routine_score = r->score; out->asleep = (uint8_t)asleep; out->q = r->qrun;
}

/* ---------------- persistence (Twin file, <= 700 B) ---------------- */
uint16_t hg_routine_pack(const hg_routine_t *r, uint8_t *buf, uint16_t cap) {
  if (cap < HG_ROUTINE_PACK_BYTES) return 0;
  uint16_t p = 0;
  buf[p++] = 'R'; buf[p++] = 'T'; buf[p++] = 1;
  memcpy(buf + p, r->am, sizeof r->am); p = (uint16_t)(p + sizeof r->am);
  memcpy(buf + p, r->q, sizeof r->q); p = (uint16_t)(p + sizeof r->q);
  memcpy(buf + p, r->maxq, sizeof r->maxq); p = (uint16_t)(p + sizeof r->maxq);
  memcpy(buf + p, r->wake_hist, sizeof r->wake_hist); p = (uint16_t)(p + sizeof r->wake_hist);
  memcpy(buf + p, &r->sleep_on, 2); p += 2; memcpy(buf + p, &r->sleep_off, 2); p += 2;
  buf[p++] = r->sleep_valid; buf[p++] = r->n_wake; buf[p++] = r->wake_i; buf[p++] = r->days_learned;
  uint8_t x = 0; for (uint16_t i = 0; i < p; i++) x = (uint8_t)(x ^ buf[i]);
  buf[p++] = x;
  while (p < HG_ROUTINE_PACK_BYTES) buf[p++] = 0;
  return p;
}
int hg_routine_unpack(hg_routine_t *r, const uint8_t *buf, uint16_t len) {
  hg_routine_init(r);
  const uint16_t body = 3 + sizeof r->am + sizeof r->q + sizeof r->maxq + sizeof r->wake_hist + 4 + 4;
  if (len < body + 1 || buf[0] != 'R' || buf[1] != 'T' || buf[2] != 1) return 0;
  uint8_t x = 0; for (uint16_t i = 0; i < body; i++) x = (uint8_t)(x ^ buf[i]);
  if (x != buf[body]) return 0;
  uint16_t p = 3;
  hg_routine_t t; hg_routine_init(&t);
  memcpy(t.am, buf + p, sizeof t.am); p = (uint16_t)(p + sizeof t.am);
  memcpy(t.q, buf + p, sizeof t.q); p = (uint16_t)(p + sizeof t.q);
  memcpy(t.maxq, buf + p, sizeof t.maxq); p = (uint16_t)(p + sizeof t.maxq);
  memcpy(t.wake_hist, buf + p, sizeof t.wake_hist); p = (uint16_t)(p + sizeof t.wake_hist);
  memcpy(&t.sleep_on, buf + p, 2); p += 2; memcpy(&t.sleep_off, buf + p, 2); p += 2;
  t.sleep_valid = buf[p++]; t.n_wake = buf[p++]; t.wake_i = buf[p++]; t.days_learned = buf[p++];
  /* bounds: a corrupted file must never produce a NaN or an out-of-range value */
  int ok = t.sleep_on < 1440 && t.sleep_off < 1440 && t.n_wake <= 7 && t.wake_i < 7;
  for (int h = 0; h < 24 && ok; h++) {
    const hg_welford_t *a = &t.am[h], *b = &t.q[h];
    ok = !hg_isnan(a->n) && !hg_isnan(a->mean) && !hg_isnan(a->m2) && !hg_isnan(b->n) && !hg_isnan(b->mean) && !hg_isnan(b->m2)
         && a->n >= 0.0f && a->n <= (float)HG_RT_WELFORD_NCAP && b->n >= 0.0f && b->n <= (float)HG_RT_WELFORD_NCAP
         && a->m2 >= 0.0f && b->m2 >= 0.0f && t.maxq[h] >= 0 && t.maxq[h] <= 1440;
  }
  for (int i = 0; i < 7 && ok; i++) ok = t.wake_hist[i] < 1440;
  if (!ok) return 0;
  *r = t;
  return 1;
}
