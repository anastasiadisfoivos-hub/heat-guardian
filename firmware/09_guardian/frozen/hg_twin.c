/* Body Twin -- C99 implementation. See hg_twin.h and twin/hg_twin.py (reference, same operation order). */
#include "hg_twin.h"
#include <math.h>
#include <string.h>

/* Bit-exactness with the Python reference needs every float op rounded separately: no fused multiply-add.
 * Arduino compiles .c files with -std=gnu11 (fp-contract=fast) -> force it off here (T3 F8). */
/* T5 D1 (B5, manager-directed): also neutralise -ffast-math (the band builds -Ofast): no finite-math-only (NaN tests
 * folded), no re-association / reciprocal maths (bit-exactness), and NaN/inf tests read the IEEE bits (memcpy). */
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC optimize ("no-fast-math", "no-unsafe-math-optimizations", "no-associative-math", "no-reciprocal-math", \
                      "no-finite-math-only", "signed-zeros", "trapping-math", "fp-contract=off")
#endif
#if defined(__clang__)
#pragma float_control(precise, on)
#pragma STDC FP_CONTRACT OFF
#endif
#if !defined(__GNUC__) && !defined(__clang__) && defined(__FAST_MATH__)
#error "hg_twin.c: build without fast-math"
#endif
static int nan_bits_(float x) { uint32_t u; memcpy(&u, &x, sizeof u); return (u & 0x7FFFFFFFu) > 0x7F800000u; }
static int fin_bits_(float x) { uint32_t u; memcpy(&u, &x, sizeof u); return (u & 0x7F800000u) != 0x7F800000u; }

#define G_REST         0.3f
#define REST_PLUS      5.0f
#define P_REST         0.1f
#define MIN_SLEEP_MIN  60u
#define G_K            0.5f
#define MIN_DT_READ    0.5f
#define BETA_OFF       HG_TWIN_BETA_OFF
#define DECAY_OFF      0.70710678f
#define G_C            0.3f
#define MIN_C_WEIGHT   30.0f
#define ROOM_WEIGHT    30.0f
#define T1_MIN_PER_H   20u
#define T1_N_CAP       30u
#define T1_N_VALID     3u
#define TAIR_BASE_MAX  28.0f
#define STILL_G        0.002f
#define ACTIVE_G       0.02f
#define HR_LO          40
#define HR_BINS        64
#define NIGHT_MIN_OBS  60u
#define T1_OK_LO       25.0f
#define T1_OK_HI       42.0f
#define TREAD_LO       34.0f
#define TREAD_HI       40.0f
#define CORE_LO        34.0f
#define CORE_HI        42.0f
#define TAIR_LO        (-20.0f)
#define TAIR_HI        60.0f
#define CD_LO          2500   /* valid centi-degree range of a learned/staged hourly mean (25..42 degC) */
#define CD_HI          4200

static float clampf_(float x, float lo, float hi) { return x < lo ? lo : (x > hi ? hi : x); }
static int fin_(float x) { return fin_bits_(x); }
static int same_(float a, float b) { return (a == b) || (nan_bits_(a) && nan_bits_(b)); }
static int16_t cd_(float x)
{
  float v = floorf(x * 100.0f + 0.5f);
  if (nan_bits_(v)) return (int16_t)HG_TWIN_CD_NONE;
  if (v > 32767.0f) return 32767;
  if (v < -32767.0f) return -32767;
  return (int16_t)v;
}
static int cd_ok_(int16_t v) { return v >= CD_LO && v <= CD_HI; }
static int16_t mean2_cd_(int16_t a, int16_t b)      /* floor((a+b)/2), identical to Python // */
{
  int32_t s = (int32_t)a + (int32_t)b, q = s / 2;
  if ((s % 2) != 0 && s < 0) q--;
  return (int16_t)q;
}

uint32_t hg_twin_crc32(uint32_t crc, const void *p, uint32_t n)
{
  const uint8_t *b = (const uint8_t *)p;
  crc = ~crc;
  while (n--) {
    crc ^= *b++;
    for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
  }
  return ~crc;
}

void hg_twin_defaults(hg2_twin_t *tw)
{
  tw->rest_hr = HG_TWIN_REST_HR_DEF;
  tw->k_person = HG_TWIN_K_DEF;
  tw->core_offset = HG_TWIN_OFF_DEF;
  tw->c_bodyheat = HG_TWIN_C_DEF;
  for (int h = 0; h < 24; h++) tw->t1_night_base[h] = NAN;
  tw->days_learned = 0;
}

static void reset_nightly_(hg_twin_acc_t *a)
{
  memset(a->hist, 0, sizeof a->hist);
  a->hist_n = 0;
  for (int h = 0; h < 24; h++) a->today_cd[h] = HG_TWIN_CD_NONE;
  a->cur_sum = 0.0f; a->cur_cnt = 0; a->cur_h = 255;
  a->c_sxx = 0.0f; a->c_sxy = 0.0f; a->c_w = 0.0f;
  a->night_n = 0; a->night_bad = 0; a->night_alarm = 0;
  a->rd_pending = 0; a->rd_flux = 0;
  a->rd_t_read = NAN; a->rd_t1 = NAN; a->rd_dT = NAN; a->rd_core = NAN;
  /* tier_now and air_ref are per-minute context set by the caller: kept */
}

void hg_twin_acc_init(hg_twin_acc_t *a)
{
  memset(a, 0, sizeof *a);
  for (int h = 0; h < 24; h++) { a->t1_n[h] = 0; a->t1_pre_cd[h] = HG_TWIN_CD_NONE; }
  a->tier_now = 0; a->air_ref = NAN; a->last_frozen = 0; a->min_since_tier = 255;
  a->calm_f20 = NAN; a->calm_n = 0;
  reset_nightly_(a);
}

void hg_twin_set_calm(hg_twin_acc_t *a, float f20, uint8_t n)
{
  if (n == 0 || !fin_(f20)) { a->calm_f20 = NAN; a->calm_n = 0; return; }
  a->calm_f20 = clampf_(f20, HG_TWIN_CALM_MIN, HG_TWIN_CALM_MAX);
  a->calm_n = n;
}

uint8_t hg_twin_get_calm(const hg_twin_acc_t *a, float *f20)
{
  if (f20) *f20 = a->calm_n ? a->calm_f20 : NAN;
  return a->calm_n;
}

static int exc_ok_(float sxx, float sxy)   /* B5-v7: finite, sxx in [0, 1e7], |sxy| <= 1e7 */
{
  return fin_(sxx) && fin_(sxy) && sxx >= 0.0f && sxx <= HG_TWIN_EXC_MAX && sxy >= -HG_TWIN_EXC_MAX && sxy <= HG_TWIN_EXC_MAX;
}
void hg_twin_set_exc(hg_twin_acc_t *a, float sxx, float sxy)
{
  if (!exc_ok_(sxx, sxy)) { a->exc_sxx = 0.0f; a->exc_sxy = 0.0f; return; }
  a->exc_sxx = sxx; a->exc_sxy = sxy;
}
int hg_twin_get_exc(const hg_twin_acc_t *a, float *sxx, float *sxy)
{
  if (sxx) *sxx = a->exc_sxx;
  if (sxy) *sxy = a->exc_sxy;
  return a->exc_sxx > 0.0f;
}

void hg_twin_note_tier(hg_twin_acc_t *a, uint8_t tier_on) { a->tier_now = tier_on ? 1u : 0u; }
void hg_twin_set_air_ref(hg_twin_acc_t *a, float t) { a->air_ref = fin_(t) ? t : NAN; }

static void flush_hour_(hg_twin_acc_t *a)
{
  if (a->cur_h < 24 && a->cur_cnt >= T1_MIN_PER_H && a->today_cd[a->cur_h] == HG_TWIN_CD_NONE) {
    float mean = a->cur_sum / (float)a->cur_cnt;
    a->today_cd[a->cur_h] = cd_(mean);
  }
  a->cur_h = 255; a->cur_sum = 0.0f; a->cur_cnt = 0;
}

void hg_twin_ingest_minute(hg_twin_acc_t *a, const hg2_in_t *in, uint8_t asleep, uint8_t location, uint8_t hr_valid)
{
  const float t1 = in->t1_c, tair = in->t_air_c, hr = in->hr_bpm, astd = in->a_std_g;
  const uint16_t tod = in->minute_of_day;
  const int tod_known = tod < 1440u;
  const int night = asleep || (tod_known && (tod >= 1380u || tod < 360u));
  if (a->tier_now) a->min_since_tier = 0;
  else if (a->min_since_tier < 255u) a->min_since_tier++;
  if (night) {
    if (a->night_n < 65535u) a->night_n++;
    if (in->worn != 2 && a->night_bad < 65535u) a->night_bad++;
    if (a->tier_now) a->night_alarm = 1;
  }
  if (a->tier_now || in->worn != 2) return;
  const int still = fin_(astd) && astd >= 0.0f && astd <= STILL_G;

  /* 1. sleep HR floor histogram */
  if (asleep && hr_valid && still && fin_(hr) && hr >= (float)HR_LO && hr < (float)(HR_LO + HR_BINS)) {
    int b = (int)(hr - (float)HR_LO);
    if (b > HR_BINS - 1) b = HR_BINS - 1;
    if (a->hist[b] >= 255u) for (int i = 0; i < HR_BINS; i++) a->hist[i] = (uint8_t)(a->hist[i] >> 1);
    a->hist[b]++;
    if (a->hist_n < 65535u) a->hist_n++;
  }
  const int t1_ok = fin_(t1) && t1 >= T1_OK_LO && t1 <= T1_OK_HI;
  const int tair_ok = fin_(tair) && tair > TAIR_LO && tair < TAIR_HI;

  /* 2. hourly T1 baseline */
  if (tod_known && still && t1_ok && tair_ok && tair < TAIR_BASE_MAX) {
    uint8_t h = (uint8_t)(tod / 60u);
    if (h != a->cur_h) { flush_hour_(a); a->cur_h = h; }
    if (a->cur_cnt < 255u) {            /* sum and count saturate together (stuck clock, T3 F2) */
      a->cur_sum = a->cur_sum + t1;
      a->cur_cnt++;
    }
  }
  /* 3. c_bodyheat on OUT-walking minutes against a reference air temperature */
  if (location == HG_TWIN_LOC_OUT && fin_(astd) && astd > ACTIVE_G && t1_ok && tair_ok && fin_(a->air_ref)) {
    float x = t1 - tair, y = tair - a->air_ref;
    a->c_sxx = a->c_sxx + x * x;
    a->c_sxy = a->c_sxy + x * y;
    a->c_w = a->c_w + 1.0f;
  }
}

void hg_twin_ingest_room_reading(hg_twin_acc_t *a, float t_room, float t_air_meas, float t1)
{
  if (!(fin_(t_room) && fin_(t_air_meas) && fin_(t1))) return;
  if (!(t_room > TAIR_LO && t_room < TAIR_HI && t_air_meas > TAIR_LO && t_air_meas < TAIR_HI &&
        t1 >= T1_OK_LO && t1 <= T1_OK_HI)) return;
  float x = t1 - t_air_meas, y = t_air_meas - t_room;
  a->c_sxx = a->c_sxx + ROOM_WEIGHT * x * x;
  a->c_sxy = a->c_sxy + ROOM_WEIGHT * x * y;
  a->c_w = a->c_w + ROOM_WEIGHT;
}

void hg_twin_ingest_reading(hg_twin_acc_t *a, float t_read, float t1_5min, float dT_5min, float core_now, uint8_t flux_valid)
{
  a->rd_t_read = t_read; a->rd_t1 = t1_5min; a->rd_dT = dT_5min; a->rd_core = core_now;
  a->rd_flux = flux_valid ? 1u : 0u;
  a->rd_pending = 1;
}

void hg_twin_sanitize(hg2_twin_t *tw, hg_twin_acc_t *a)
{
  tw->rest_hr = fin_(tw->rest_hr) ? clampf_(tw->rest_hr, HG_TWIN_REST_HR_MIN, HG_TWIN_REST_HR_MAX) : HG_TWIN_REST_HR_DEF;
  tw->k_person = fin_(tw->k_person) ? clampf_(tw->k_person, HG_TWIN_K_MIN, HG_TWIN_K_MAX) : HG_TWIN_K_DEF;
  tw->core_offset = fin_(tw->core_offset) ? clampf_(tw->core_offset, HG_TWIN_OFF_MIN, HG_TWIN_OFF_MAX) : HG_TWIN_OFF_DEF;
  tw->c_bodyheat = fin_(tw->c_bodyheat) ? clampf_(tw->c_bodyheat, HG_TWIN_C_MIN, HG_TWIN_C_MAX) : HG_TWIN_C_DEF;
  for (int h = 0; h < 24; h++) {
    float b = tw->t1_night_base[h];
    uint8_t n = a->t1_n[h];
    int bad;
    if (n >= T1_N_VALID) bad = !(fin_(b) && b >= T1_OK_LO && b <= T1_OK_HI);
    else if (n == 0) bad = 0;
    else bad = !cd_ok_(a->t1_pre_cd[h]);
    if (bad) n = 0;
    if (n > T1_N_CAP) n = (uint8_t)T1_N_CAP;
    a->t1_n[h] = n;
    if (n == 0 || n >= T1_N_VALID) a->t1_pre_cd[h] = HG_TWIN_CD_NONE;
    if (n < T1_N_VALID) tw->t1_night_base[h] = NAN;
    if (a->today_cd[h] != HG_TWIN_CD_NONE && !cd_ok_(a->today_cd[h])) a->today_cd[h] = HG_TWIN_CD_NONE;
  }
  if (a->cur_h > 23u) { a->cur_h = 255; a->cur_sum = 0.0f; a->cur_cnt = 0; }
  if (a->calm_n == 0 || !(fin_(a->calm_f20) && a->calm_f20 >= HG_TWIN_CALM_MIN && a->calm_f20 <= HG_TWIN_CALM_MAX)) {
    a->calm_f20 = NAN; a->calm_n = 0;
  }
  if (!exc_ok_(a->exc_sxx, a->exc_sxy)) { a->exc_sxx = 0.0f; a->exc_sxy = 0.0f; }   /* B5-v7 */
  if (!(fin_(a->c_sxx) && fin_(a->c_sxy) && fin_(a->c_w) && a->c_w >= 0.0f && a->c_sxx >= 0.0f)) {
    a->c_sxx = 0.0f; a->c_sxy = 0.0f; a->c_w = 0.0f;
  }
}

int hg_twin_commit_reading(hg2_twin_t *tw, hg_twin_acc_t *a)
{
  if (!a->rd_pending) return 0;
  a->rd_pending = 0;
  hg_twin_sanitize(tw, a);
  /* M4.4: dropped (not deferred) while a tier is on or < 30 min after it ended */
  if (a->tier_now || a->min_since_tier < HG_TWIN_TIER_HOLDOFF_MIN) return 0;
  const float t_raw = a->rd_t_read, t1 = a->rd_t1, dT = a->rd_dT, core_now = a->rd_core;
  const float k0 = tw->k_person, o0 = tw->core_offset;
  if (!(fin_(t_raw) && t_raw >= TREAD_LO && t_raw <= TREAD_HI)) return 0;
#if HG_TWIN_READING_MODE == 1
  const float t_read = t_raw + HG_TWIN_ORAL_TO_CORE;     /* sourced oral -> core correction (M4.3) */
  if (a->rd_flux && fin_(dT) && dT >= MIN_DT_READ && dT < 15.0f && fin_(t1) && t1 >= T1_OK_LO && t1 <= T1_OK_HI) {
    float g_obs = (t_read - tw->core_offset - t1) / dT;   /* capped gap gain (M4.1) */
    float g = tw->k_person + G_K * (g_obs - tw->k_person);
#if HG_TWIN_K_RULE != 2
    tw->k_person = clampf_(g, HG_TWIN_K_MIN, HG_TWIN_K_MAX);
#else
    (void)g;
#endif
  }
#else
  const float t_read = t_raw;                             /* display-only: no learning of the gap gain (M4.3) */
  (void)t1; (void)dT;
#endif
  if (fin_(core_now) && core_now >= CORE_LO && core_now <= CORE_HI) {
    float off = tw->core_offset + BETA_OFF * (t_read - core_now);
    tw->core_offset = clampf_(off, HG_TWIN_OFF_MIN, HG_TWIN_OFF_MAX);
  }
  hg_twin_sanitize(tw, a);           /* bounds re-checked after every update, before hg2_set_twin */
  return (tw->k_person != k0 || tw->core_offset != o0) ? 1 : 0;
}

static float p10_(const hg_twin_acc_t *a)
{
  uint32_t total = 0;
  for (int b = 0; b < HR_BINS; b++) total += a->hist[b];
  const float target = P_REST * (float)total;
  uint32_t cum = 0;
  for (int b = 0; b < HR_BINS; b++) {
    uint32_t c = a->hist[b];
    if (c && (float)(cum + c) >= target) return (float)(HR_LO + b) + (target - (float)cum) / (float)c;
    cum += c;
  }
  return (float)(HR_LO + HR_BINS);
}

int hg_twin_nightly_update(hg2_twin_t *tw, hg_twin_acc_t *a)
{
  int changed = 0;
  if (a->rd_pending && hg_twin_commit_reading(tw, a)) changed = 1;
  hg_twin_sanitize(tw, a);
  const hg2_twin_t old = *tw;
  uint8_t old_n[24]; int16_t old_pre[24];
  memcpy(old_n, a->t1_n, sizeof old_n); memcpy(old_pre, a->t1_pre_cd, sizeof old_pre);

  flush_hour_(a);
  tw->core_offset = clampf_(tw->core_offset * DECAY_OFF, HG_TWIN_OFF_MIN, HG_TWIN_OFF_MAX);

  uint8_t why = 0;
  if (a->night_alarm) why = 1;
  else if (a->night_n < NIGHT_MIN_OBS) why = 2;
  else if ((uint32_t)a->night_bad * 10u > (uint32_t)a->night_n * 3u) why = 3;
  a->last_frozen = why;

  if (!why) {
    if (a->hist_n >= MIN_SLEEP_MIN) {
      float p10 = p10_(a);
      float r = tw->rest_hr + G_REST * (p10 + REST_PLUS - tw->rest_hr);
      tw->rest_hr = clampf_(r, HG_TWIN_REST_HR_MIN, HG_TWIN_REST_HR_MAX);
    }
    for (int h = 0; h < 24; h++) {
      int16_t cd = a->today_cd[h];
      if (cd == HG_TWIN_CD_NONE) continue;
      uint8_t n = a->t1_n[h];
      if (n == 0) { a->t1_pre_cd[h] = cd; a->t1_n[h] = 1; }
      else if (n == 1) { a->t1_pre_cd[h] = mean2_cd_(a->t1_pre_cd[h], cd); a->t1_n[h] = 2; }
      else if (n == 2) {
        float m2 = (float)a->t1_pre_cd[h] / 100.0f;
        float x = (float)cd / 100.0f;
        tw->t1_night_base[h] = m2 + (x - m2) / 3.0f;
        a->t1_n[h] = 3; a->t1_pre_cd[h] = HG_TWIN_CD_NONE;
      } else {
        uint8_t n2 = (uint8_t)(n < T1_N_CAP ? n + 1u : T1_N_CAP);
        float x = (float)cd / 100.0f;
        tw->t1_night_base[h] = tw->t1_night_base[h] + (x - tw->t1_night_base[h]) / (float)n2;
        a->t1_n[h] = n2;
      }
    }
    if (a->c_w >= MIN_C_WEIGHT && a->c_sxx > 1e-3f) {
      float c_ls = a->c_sxy / a->c_sxx;
      if (fin_(c_ls)) {
        float c = tw->c_bodyheat + G_C * (clampf_(c_ls, -1.0f, 1.0f) - tw->c_bodyheat);
        tw->c_bodyheat = clampf_(c, HG_TWIN_C_MIN, HG_TWIN_C_MAX);
      }
    }
    if (tw->days_learned < 255u) tw->days_learned++;
  }
  hg_twin_sanitize(tw, a);           /* bounds re-checked after every update, before hg2_set_twin */

  if (!same_(old.rest_hr, tw->rest_hr) || !same_(old.k_person, tw->k_person) || !same_(old.core_offset, tw->core_offset) ||
      !same_(old.c_bodyheat, tw->c_bodyheat) || old.days_learned != tw->days_learned) changed = 1;
  for (int h = 0; h < 24; h++)
    if (!same_(old.t1_night_base[h], tw->t1_night_base[h]) || old_n[h] != a->t1_n[h] || old_pre[h] != a->t1_pre_cd[h]) changed = 1;
  reset_nightly_(a);
  return changed;
}

/* ---- little-endian packing helpers ---- */
static void put_u16_(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static void put_u32_(uint8_t *p, uint32_t v) { for (int i = 0; i < 4; i++) p[i] = (uint8_t)(v >> (8 * i)); }
static void put_f32_(uint8_t *p, float f) { uint32_t u; memcpy(&u, &f, 4); put_u32_(p, u); }
static uint16_t get_u16_(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static uint32_t get_u32_(const uint8_t *p) { return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24); }
static float get_f32_(const uint8_t *p) { uint32_t u = get_u32_(p); float f; memcpy(&f, &u, 4); return f; }

int hg_twin_pack(const hg2_twin_t *tw, const hg_twin_acc_t *a, const void *routine, uint16_t routine_len,
                 uint32_t save_count, uint8_t *buf, uint16_t buflen)
{
  const uint32_t len = HG_TWIN_FIXED_LEN + routine_len;
  if (len > HG_TWIN_FILE_MAX || len > buflen || (routine_len && !routine)) return -1;
  uint8_t *p = buf;
  put_u32_(p, HG_TWIN_MAGIC); put_u16_(p + 4, (uint16_t)HG_TWIN_VERSION); put_u16_(p + 6, (uint16_t)len); p += 8;
  put_f32_(p, tw->rest_hr); put_f32_(p + 4, tw->k_person); put_f32_(p + 8, tw->core_offset); put_f32_(p + 12, tw->c_bodyheat); p += 16;
  for (int h = 0; h < 24; h++, p += 4) put_f32_(p, tw->t1_night_base[h]);
  *p++ = tw->days_learned;
  for (int h = 0; h < 24; h++) *p++ = a->t1_n[h];
  for (int h = 0; h < 24; h++, p += 2) put_u16_(p, (uint16_t)a->t1_pre_cd[h]);
  put_f32_(p, a->calm_n ? a->calm_f20 : NAN); p[4] = a->calm_n; p += 5;
  put_f32_(p, a->exc_sxx); put_f32_(p + 4, a->exc_sxy); p += 8;   /* v4 (B5-v7) */
  if (routine_len) memcpy(p, routine, routine_len);
  p += routine_len;
  put_u32_(p, save_count); p += 4;
  put_u32_(p, hg_twin_crc32(0, buf, (uint32_t)(p - buf)));
  return (int)len;
}

int hg_twin_unpack(const uint8_t *buf, uint16_t len, hg2_twin_t *tw, hg_twin_acc_t *a,
                   void *routine, uint16_t routine_cap, uint16_t *routine_len, uint32_t *save_count)
{
  hg2_twin_t t; hg_twin_acc_t ac;
  int err = 0;
  hg_twin_defaults(tw); hg_twin_acc_init(a);
  if (routine_len) *routine_len = 0;
  if (save_count) *save_count = 0;
  if (!buf || len < HG_TWIN_FIXED_LEN_V2 || len > HG_TWIN_FILE_MAX) return -1;
  if (get_u32_(buf) != HG_TWIN_MAGIC) return -2;
  const uint16_t ver = get_u16_(buf + 4);
  if (ver != HG_TWIN_VERSION && ver != HG_TWIN_VERSION_V3 && ver != HG_TWIN_VERSION_V2) return -3;
  const uint16_t fixed = (uint16_t)(ver == HG_TWIN_VERSION ? HG_TWIN_FIXED_LEN : ver == HG_TWIN_VERSION_V3 ? HG_TWIN_FIXED_LEN_V3 : HG_TWIN_FIXED_LEN_V2);
  if (len < fixed) return -1;
  if (get_u16_(buf + 6) != len) return -4;
  if (hg_twin_crc32(0, buf, (uint32_t)len - 4u) != get_u32_(buf + len - 4)) return -5;
  const uint16_t rlen = (uint16_t)(len - fixed);
  if (rlen > routine_cap || (rlen && !routine)) return -6;
  const uint8_t *p = buf + 8;
  hg_twin_defaults(&t); hg_twin_acc_init(&ac);
  t.rest_hr = get_f32_(p); t.k_person = get_f32_(p + 4); t.core_offset = get_f32_(p + 8); t.c_bodyheat = get_f32_(p + 12); p += 16;
  for (int h = 0; h < 24; h++, p += 4) t.t1_night_base[h] = get_f32_(p);
  t.days_learned = *p++;
  for (int h = 0; h < 24; h++) ac.t1_n[h] = *p++;
  for (int h = 0; h < 24; h++, p += 2) ac.t1_pre_cd[h] = (int16_t)get_u16_(p);
  float calm = NAN; uint8_t calm_n = 0;
  if (ver != HG_TWIN_VERSION_V2) {        /* M9.5 calm block (v3, v4): n == 0 <-> NAN; n > 0 -> finite and in bounds */
    calm = get_f32_(p); calm_n = p[4]; p += 5;
    if (calm_n == 0 ? !nan_bits_(calm) : !(fin_(calm) && calm >= HG_TWIN_CALM_MIN && calm <= HG_TWIN_CALM_MAX)) err = 1;
  }
  float exs = 0.0f, exy = 0.0f;
  if (ver == HG_TWIN_VERSION) {           /* B5-v7 Exception block (v4): finite, sxx in [0, 1e7], |sxy| <= 1e7 */
    exs = get_f32_(p); exy = get_f32_(p + 4); p += 8;
    if (!exc_ok_(exs, exy)) err = 1;
  }
  /* bounds: a CRC-valid file with an impossible value is treated as corrupt */
  if (!(fin_(t.rest_hr) && t.rest_hr >= HG_TWIN_REST_HR_MIN && t.rest_hr <= HG_TWIN_REST_HR_MAX)) err = 1;
  if (!(fin_(t.k_person) && t.k_person >= HG_TWIN_K_MIN && t.k_person <= HG_TWIN_K_MAX)) err = 1;
  if (!(fin_(t.core_offset) && t.core_offset >= HG_TWIN_OFF_MIN && t.core_offset <= HG_TWIN_OFF_MAX)) err = 1;
  if (!(fin_(t.c_bodyheat) && t.c_bodyheat >= HG_TWIN_C_MIN && t.c_bodyheat <= HG_TWIN_C_MAX)) err = 1;
  for (int h = 0; h < 24; h++) {          /* learning-state consistency (T3 F3) */
    float b = t.t1_night_base[h];
    uint8_t n = ac.t1_n[h];
    int16_t pre = ac.t1_pre_cd[h];
    if (n > T1_N_CAP) err = 1;
    if (n >= T1_N_VALID) { if (!(fin_(b) && b >= T1_OK_LO && b <= T1_OK_HI) || pre != HG_TWIN_CD_NONE) err = 1; }
    else {
      if (!nan_bits_(b)) err = 1;
      if (n == 0 && pre != HG_TWIN_CD_NONE) err = 1;
      if (n > 0 && !cd_ok_(pre)) err = 1;
    }
  }
  if (err) return -7;
  if (rlen) memcpy(routine, p, rlen);
  p += rlen;
  *tw = t;
  memcpy(a->t1_n, ac.t1_n, sizeof a->t1_n);
  memcpy(a->t1_pre_cd, ac.t1_pre_cd, sizeof a->t1_pre_cd);
  a->calm_f20 = calm; a->calm_n = calm_n;
  a->exc_sxx = exs; a->exc_sxy = exy;
  if (routine_len) *routine_len = rlen;
  if (save_count) *save_count = get_u32_(p);
  return 0;
}
