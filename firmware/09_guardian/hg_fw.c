/* Heat Guardian 09_guardian: firmware glue. See hg_fw.h. Compiled with -fsingle-precision-constant -ffp-contract=off
 * semantics (fw_flags.h pragmas) like the frozen sources. */
#include "fw_flags.h"
#include "hg_fw.h"
#include "hg_astd.h"   /* the minute a_std, shared with 08_logger */
#include <math.h>
#include <string.h>
#define hg_crc8 hg_log_crc8      /* log_format.h and hg_frames.h both name their (identical) CRC-8 hg_crc8 */
#include "log_format.h"
#include "frozen/hg_guardian_cfg.h"   /* B5-v7: HG_IMPACT_G for the log impact flag (same constant as the impact CHECK) */
#undef hg_crc8

static int fin(float v) { return v == v && v < 1e30f && v > -1e30f; }

static void min_reset(hg_fw_t *f)
{
  f->s_t1 = f->s_t2 = f->s_ta = f->s_rh = f->s_pi = 0.0f; f->n_t1 = f->n_t2 = f->n_ta = f->n_rh = f->n_pi = 0;
  f->a_mean = 0.0f; f->a_m2 = 0.0f; f->a_n = 0; f->s_astd = 0.0f; f->n_astd = 0; f->a_peak = 0.0f; f->n_hr = 0; f->n_dc = 0;
  memset(f->q_cnt, 0, sizeof f->q_cnt);
  for (int k = 0; k < 12; k++) { f->t1_5s[k] = NAN; f->t2_5s[k] = NAN; f->ta_5s[k] = NAN; f->z_5s[k] = NAN; }
  f->secs = 0; f->button = 0;
}

void hg_fw_init(hg_fw_t *f)
{
  memset(f, 0, sizeof *f);
  f->night_done_day = -1; f->saves_day = -1;
  min_reset(f);
  f->last_out.state = HG_ST_OK;
}

void hg_fw_discard_minute(hg_fw_t *f) { min_reset(f); }

void hg_fw_button(hg_fw_t *f, uint8_t kind) { if (kind > f->button) f->button = kind; }

void hg_fw_second(hg_fw_t *f, const hg_fw_sec_t *s)
{
  if (fin(s->t1_c)) { f->s_t1 += s->t1_c; f->n_t1++; }
  if (fin(s->t2_c)) { f->s_t2 += s->t2_c; f->n_t2++; }
  if (fin(s->tair_c)) { f->s_ta += s->tair_c; f->n_ta++; }
  if (fin(s->rh_pct)) { f->s_rh += s->rh_pct; f->n_rh++; }
  hg_astd_add(&f->a_mean, &f->a_m2, &f->a_n, s->a_mean, s->a_m2, s->a_n);   /* Chan et al. parallel merge (hg_astd.h) */
  if (s->a_n >= 3 && fin(s->a_mean) && fin(s->a_m2)) { f->s_astd += sqrtf(s->a_m2 > 0.0f ? s->a_m2 / (float)s->a_n : 0.0f); f->n_astd++; }
  if (fin(s->a_peak_g) && s->a_peak_g > f->a_peak) f->a_peak = s->a_peak_g;
  if (s->ppg_on) {
    if (s->hr_q <= 4) f->q_cnt[s->hr_q]++;
    if (s->hr_q == 4 && fin(s->hr_bpm) && s->hr_bpm >= 30.0f && s->hr_bpm <= 220.0f && f->n_hr < 60) f->hr[f->n_hr++] = (uint8_t)(s->hr_bpm + 0.5f);
    if (fin(s->pi_pct)) { f->s_pi += s->pi_pct; f->n_pi++; }
    if (f->n_dc < 60) f->dc[f->n_dc++] = s->ppg_dc;
  }
  if (f->secs < 60 && (f->secs % 5u) == 4u) {             /* the twelve 5-s samples */
    uint8_t k = (uint8_t)(f->secs / 5u);
    f->t1_5s[k] = fin(s->t1_c) ? s->t1_c : NAN; f->t2_5s[k] = fin(s->t2_c) ? s->t2_c : NAN;
    f->ta_5s[k] = fin(s->tair_c) ? s->tair_c : NAN; f->z_5s[k] = fin(s->zangle_deg) ? s->zangle_deg : NAN;
  }
  if (f->secs < 255) f->secs++;
}

static void isort8(uint8_t *v, int n) { for (int i = 1; i < n; i++) { uint8_t k = v[i]; int j = i - 1; while (j >= 0 && v[j] > k) { v[j + 1] = v[j]; j--; } v[j + 1] = k; } }
static void isort32(uint32_t *v, int n) { for (int i = 1; i < n; i++) { uint32_t k = v[i]; int j = i - 1; while (j >= 0 && v[j] > k) { v[j + 1] = v[j]; j--; } v[j + 1] = k; } }
static void isortf(float *v, int n) { for (int i = 1; i < n; i++) { float k = v[i]; int j = i - 1; while (j >= 0 && v[j] > k) { v[j + 1] = v[j]; j--; } v[j + 1] = k; } }

uint8_t hg_fw_asleep(const hg_guardian_t *g, uint16_t mod)
{
  if (mod >= 1440u || !g->rt.sleep_valid) return 0;
  uint16_t on = g->rt.sleep_on, off = g->rt.sleep_off;
  if (on == off) return 0;
  return on < off ? (uint8_t)(mod >= on && mod < off) : (uint8_t)(mod >= on || mod < off);
}

int hg_fw_ppg_on(const hg_fw_t *f, uint8_t sec)
{
  const hg_minute_out_t *o = &f->last_out;
  int alert = o->tiers != 0 || o->state == HG_ST_CHECK || o->state == HG_ST_DANGER || o->state == HG_ST_HELP ||
              o->state == HG_ST_DRINK || o->state == HG_ST_COOL;
  return alert || sec < HG_FW_PPG_ON_S;
}

static uint16_t u16c(float v, float scale) { if (!fin(v)) return 0; float x = v * scale + 0.5f; return (uint16_t)(x < 0.0f ? 0.0f : (x > 65535.0f ? 65535.0f : x)); }
static uint8_t u8c(float v, float scale) { if (!fin(v)) return 255; float x = v * scale + 0.5f; return (uint8_t)(x < 0.0f ? 0.0f : (x > 254.0f ? 254.0f : x)); }

/* guardian record, 24 B, t_ms / flags / marker / crc at the log_format.h positions; marker = 13:
 *  4-5 core_now x100 (0 = invalid)  6 sd_now x100  7-8 f20_eff x100  9 state  10 level | tiers << 4
 *  11 worn | home_out << 2 | night_heat << 4 | nudge << 5 | family_alert << 6   12 why  13 routine_score
 *  14 check_reason  15 screen  16 haptic | hr_valid << 4 | flux_valid << 5 | core valid << 6   17 check_min
 *  18 flags (bit4 marker, bit6 minute + the input record's charging/ble/time bits)  19 marker 13
 *  20 strain x20  21-22 minute counter  23 CRC-8 */
void hg_fw_pack_grec(uint32_t t_ms, const hg_minute_out_t *o, uint8_t flags, uint8_t b[24])
{
  memset(b, 0, 24);
  b[0] = (uint8_t)t_ms; b[1] = (uint8_t)(t_ms >> 8); b[2] = (uint8_t)(t_ms >> 16); b[3] = (uint8_t)(t_ms >> 24);
  uint16_t c = o->core.valid ? u16c(o->core.core_now, 100.0f) : 0, f20 = o->core.valid ? u16c(o->core.f20_eff, 100.0f) : 0;
  b[4] = (uint8_t)c; b[5] = (uint8_t)(c >> 8);
  b[6] = u8c(o->core.sd_now, 100.0f);
  b[7] = (uint8_t)f20; b[8] = (uint8_t)(f20 >> 8);
  b[9] = o->state; b[10] = (uint8_t)((o->level & 15) | (o->tiers << 4));
  b[11] = (uint8_t)((o->worn & 3) | ((o->home_out & 3) << 2) | ((o->night_heat & 1) << 4) | ((o->nudge & 1) << 5) | ((o->family_alert & 1) << 6));
  b[12] = o->why; b[13] = o->routine_score; b[14] = o->check_reason; b[15] = o->screen;
  b[16] = (uint8_t)((o->haptic & 15) | ((o->core.hr_valid & 1) << 4) | ((o->core.flux_valid & 1) << 5) | ((o->core.valid & 1) << 6));
  b[17] = o->check_min;
  b[18] = (uint8_t)(flags | HG_F_MARKER | HG_F_MINUTE);
  b[19] = 13;
  b[20] = u8c(o->core.strain, 20.0f);
  uint16_t mc = (uint16_t)(o->status[17] | (o->status[18] << 8));   /* STATUS minute counter */
  b[21] = (uint8_t)mc; b[22] = (uint8_t)(mc >> 8);
  b[23] = hg_crc8(b, 23);
}

/* the minute's hg_minute_t from the 1-s sums (also updates the flat/still run counters); zmed = median z-angle or NAN */
static void build_minute(hg_fw_t *f, const hg_fw_ctx_t *ctx, hg_minute_t *mp, float *zmed_out)
{
  hg_minute_t m; memset(&m, 0, sizeof m);
  m.s.t1_c = f->n_t1 ? f->s_t1 / f->n_t1 : NAN;
  m.s.t2_c = f->n_t2 ? f->s_t2 / f->n_t2 : NAN;
  m.s.t_air_c = f->n_ta ? f->s_ta / f->n_ta : NAN;
  m.s.rh_pct = f->n_rh ? f->s_rh / f->n_rh : NAN;
  uint8_t qbest = 0, qn = 0;
  for (uint8_t q = 0; q < 5; q++) if (f->q_cnt[q] > qn) { qn = f->q_cnt[q]; qbest = q; }
  if (f->n_hr >= 3) { isort8(f->hr, f->n_hr); m.s.hr_bpm = f->hr[f->n_hr / 2]; m.s.hr_quality = 4; }
  else { m.s.hr_bpm = NAN; m.s.hr_quality = qn ? (qbest == 4 ? 3 : qbest) : 0; }   /* < 3 OK seconds is not an OK minute */
  m.s.pi_pct = f->n_pi ? f->s_pi / f->n_pi : NAN;
  m.s.a_std_g = hg_astd_std(f->a_m2, f->a_n);
  m.s.worn = 2;                                     /* ignored: hg_guardian computes it (hg_contact) */
  m.s.minute_of_day = ctx->minute_of_day;
  memcpy(m.t1_5s, f->t1_5s, sizeof m.t1_5s); memcpy(m.t2_5s, f->t2_5s, sizeof m.t2_5s);
  memcpy(m.tair_5s, f->ta_5s, sizeof m.tair_5s); memcpy(m.zangle_5s, f->z_5s, sizeof m.zangle_5s);
  m.a_peak_g = f->a_peak;
  if (f->n_dc) { isort32(f->dc, f->n_dc); m.ppg_dc = f->dc[f->n_dc / 2]; } else m.ppg_dc = 0;
  /* flat + still minutes (contact rule "flat orientation + no motion >= 30 min") */
  float zs[12]; int nz = 0;
  for (int k = 0; k < 12; k++) if (fin(f->z_5s[k])) zs[nz++] = f->z_5s[k];
  float zmed = NAN; if (nz) { isortf(zs, nz); zmed = zs[nz / 2]; }
  int still = fin(m.s.a_std_g) && m.s.a_std_g <= HG_FW_STILL_G;
  f->flat_still = (still && fin(zmed) && fabsf(zmed) >= 75.0f) ? (uint8_t)(f->flat_still < 255 ? f->flat_still + 1 : 255) : 0;
  f->still_run = still ? (uint16_t)(f->still_run < 65535 ? f->still_run + 1 : 65535) : 0;
  m.flat_still_min = f->flat_still;
  m.button = f->button; m.charging = ctx->charging; m.vbat = ctx->vbat; m.ble_bucket = ctx->ble_bucket;
  m.forecast72 = ctx->forecast72; m.has_forecast = ctx->has_forecast; m.force_worn = 0xFF;
  *mp = m; *zmed_out = zmed;
}

/* the minute's input record (log_format.h, flag bit6); returns its flags */
static uint8_t pack_inputs(const hg_fw_t *f, const hg_minute_t *mp, float zmed, const hg_fw_ctx_t *ctx, uint32_t t_ms, uint8_t out[24])
{
  const hg_minute_t m = *mp;
  hg_rec_t r; memset(&r, 0, sizeof r);
  r.t_ms = t_ms;
  r.t1_c100 = hg_c100(m.s.t1_c, fin(m.s.t1_c)); r.t2_c100 = hg_c100(m.s.t2_c, fin(m.s.t2_c)); r.tair_c100 = hg_c100(m.s.t_air_c, fin(m.s.t_air_c));
  r.rh = fin(m.s.rh_pct) ? (uint8_t)(m.s.rh_pct + 0.5f) : HG_RH_ABSENT;
  r.hr = fin(m.s.hr_bpm) ? (uint8_t)m.s.hr_bpm : 0; r.hr_q = f->n_dc ? m.s.hr_quality : HG_HRQ_NONE;
  r.pi_100 = fin(m.s.pi_pct) ? u16c(m.s.pi_pct, 100.0f) : 0;
  r.astd_1e4 = f->n_astd ? u16c(f->s_astd / f->n_astd, 10000.0f) : 0xFFFF;        /* mean of the 1-s stds (as 08's minute record) */
  r.astd_min_1e4 = fin(m.s.a_std_g) ? u16c(m.s.a_std_g, 10000.0f) : 0xFFFF;   /* the guardian's whole-minute a_std (log v2) */
  r.zangle_c100 = fin(zmed) ? (int16_t)(zmed >= 0 ? zmed * 100.0f + 0.5f : zmed * 100.0f - 0.5f) : 0;
  r.flags = (uint8_t)(HG_F_MINUTE | (ctx->charging ? HG_F_CHARGING : 0) | (ctx->ble_bucket >= 0 ? HG_F_BLE : 0) |
                      (ctx->minute_of_day < 1440u ? HG_F_TIME_VALID : 0) | (m.button ? HG_F_BUTTON : 0) | (m.a_peak_g >= HG_IMPACT_G ? HG_F_IMPACT : 0));
  r.dc8 = fin(ctx->vbat) && ctx->vbat > 2.0f ? (uint8_t)((ctx->vbat - 2.0f) * 100.0f + 0.5f) : 0;
  r.aux = (uint16_t)(m.ppg_dc / 4u > 65535u ? 65535u : m.ppg_dc / 4u);
  hg_rec_pack(&r, out);
  return r.flags;
}

void hg_fw_minute_inputs(hg_fw_t *f, const hg_fw_ctx_t *ctx, uint32_t t_ms, uint8_t rec[24])
{
  hg_minute_t m; float zmed;
  build_minute(f, ctx, &m, &zmed);
  pack_inputs(f, &m, zmed, ctx, t_ms, rec);
  min_reset(f);
}

void hg_fw_minute(hg_fw_t *f, hg_guardian_t *g, hg2_twin_t *tw, hg_twin_acc_t *acc, const hg_fw_ctx_t *ctx,
                  uint32_t t_ms, hg_fw_act_t *act)
{
  memset(act, 0, sizeof *act);
  hg_minute_t m; float zmed;
  build_minute(f, ctx, &m, &zmed);

  hg_minute_out_t o;
  hg_guardian_step(g, &m, &o);

  /* Body Twin: ingest this minute, nightly update once per local day */
  hg_twin_note_tier(acc, (uint8_t)(o.tiers != 0));
  { hg2_in_t s2 = m.s; s2.worn = o.worn;
    uint8_t loc = o.home_out == HG_HO_HOME ? HG_TWIN_LOC_HOME : (o.home_out == HG_HO_OUT ? HG_TWIN_LOC_OUT : HG_TWIN_LOC_TRANSIT);
    hg_twin_ingest_minute(acc, &s2, hg_fw_asleep(g, ctx->minute_of_day), loc, o.core.hr_valid); }
  if (ctx->local_day != f->saves_day) { f->saves_day = ctx->local_day; f->saves_today = 0; }
  if (ctx->local_day >= 0 && ctx->minute_of_day < 720u && ctx->minute_of_day >= HG_FW_NIGHT_FROM &&
      f->night_done_day != ctx->local_day && (f->still_run >= HG_FW_NIGHT_STILL || ctx->minute_of_day >= HG_FW_NIGHT_LATEST)) {
    f->night_done_day = ctx->local_day;
    hg_twin_nightly_update(tw, acc);
    hg_guardian_set_twin(g, tw);
    act->nightly = 1; f->nightly_runs++;
    if (f->saves_today < HG_FW_MAX_SAVES_DAY) { act->save_twin = 1; f->saves_today++; }
  }

  act->status_changed = (uint8_t)(f->minutes == 0 || o.status[0] != f->last_out.status[0] || o.status[1] != f->last_out.status[1] ||
                                  o.state != f->last_out.state);
  memcpy(f->ring[f->ring_head], o.status, 20);
  f->ring_head = (uint16_t)((f->ring_head + 1) % HG_FW_RING_MIN); if (f->ring_n < HG_FW_RING_MIN) f->ring_n++;

  /* log records: the minute's inputs + the guardian record */
  uint8_t fl = pack_inputs(f, &m, zmed, ctx, t_ms, act->rec_in);
  hg_fw_pack_grec(t_ms, &o, (uint8_t)(fl & (HG_F_CHARGING | HG_F_BLE | HG_F_TIME_VALID)), act->rec_g);

  f->last_in = m; f->last_out = o; f->minutes++;
  min_reset(f);
}

/* T6b M3: a new wearer profile without hg_guardian_init(). The frozen init derives these constants from the profile
 * and nothing else: g->prof, the watch margins m_drink/m_cool, hg2's age/sex/bmi/hrmax/med_flags/older_env and the
 * v1.2 Kalman's age/sex/bmi/hrmax/flags. They are taken from a scratch guardian initialised by the frozen code with
 * the new profile (so the formulas are the frozen ones); every other byte of g is kept: HELP, CHECK, family alert,
 * tiers, the Kalman state, routine, calm baseline. test_fw.c checks exactly that. */
void hg_fw_apply_profile(hg_guardian_t *g, const hg2_profile_t *p)
{
  static hg_guardian_t t;                           /* 3.7 KB, static: not on the 4 KB loop stack */
  hg_guardian_init(&t, p, &g->twin);
  g->prof = t.prof; g->m_drink = t.m_drink; g->m_cool = t.m_cool;
  g->hg2.age = t.hg2.age; g->hg2.sex_m = t.hg2.sex_m; g->hg2.bmi = t.hg2.bmi; g->hg2.hrmax = t.hg2.hrmax;
  g->hg2.med_flags = t.hg2.med_flags; g->hg2.older_env = t.hg2.older_env;
  g->hg2.kf.age = t.hg2.kf.age; g->hg2.kf.sex_m = t.hg2.kf.sex_m; g->hg2.kf.bmi = t.hg2.kf.bmi;
  g->hg2.kf.hrmax = t.hg2.kf.hrmax; g->hg2.kf.flags = t.hg2.kf.flags;
}

int hg_fw_twin_pack(const hg_guardian_t *g, const hg2_twin_t *tw, hg_twin_acc_t *acc, uint32_t save_count, uint8_t *buf, uint16_t cap)
{
  uint8_t rt[HG_ROUTINE_PACK_BYTES];
  hg_guardian_calm_to_twin(g, acc);
  uint16_t rn = hg_routine_pack(&g->rt, rt, sizeof rt);
  return hg_twin_pack(tw, acc, rt, rn, save_count, buf, cap);
}

int hg_fw_twin_load(hg_guardian_t *g, const hg2_profile_t *p, hg2_twin_t *tw, hg_twin_acc_t *acc, const uint8_t *buf, uint16_t len, uint32_t *save_count)
{
  uint8_t rt[700]; uint16_t rn = 0; uint32_t sc = 0;
  int rc = buf ? hg_twin_unpack(buf, len, tw, acc, rt, sizeof rt, &rn, &sc) : -1;
  if (rc < 0) { hg_twin_defaults(tw); hg_twin_acc_init(acc); rn = 0; sc = 0; }
  hg_twin_sanitize(tw, acc);
  hg_guardian_init(g, p, tw);
  if (rc >= 0) {
    hg_guardian_calm_from_twin(g, acc);
    if (rn) hg_routine_unpack(&g->rt, rt, rn);
  }
  if (save_count) *save_count = sc;
  return rc < 0 ? rc : 0;
}

uint16_t hg_fw_ring_get(const hg_fw_t *f, uint16_t n, uint8_t (*out)[20])
{
  if (n > f->ring_n) n = f->ring_n;
  uint16_t start = (uint16_t)((f->ring_head + HG_FW_RING_MIN - n) % HG_FW_RING_MIN);
  for (uint16_t i = 0; i < n; i++) memcpy(out[i], f->ring[(start + i) % HG_FW_RING_MIN], 20);
  return n;
}
