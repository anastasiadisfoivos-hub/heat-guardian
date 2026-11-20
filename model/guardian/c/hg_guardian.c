#include "hg_fp.h"   /* T5 D1: first include - IEEE-exact float semantics even under -ffast-math */
/* Heat Guardian - Guardian Loop (see hg_guardian.h). Every number comes from hg_guardian_cfg.h. */
#include <math.h>
#include <string.h>
#include "hg_guardian.h"
#include "hg_guardian_cfg.h"
#include "hg2_weights.h"
#include "hg_unc.h"
#include "hg2_guard.h"
#if HG_AC_STEP_WIN + 1 != 16
#error "ta_ring[16] holds HG_AC_STEP_WIN + 1 minutes (T5 m3)"
#endif
#if HG_X_W_N != HG_X_W_N_DECL
#error "HG_X_W_N (cfg) != HG_X_W_N_DECL (hg_guardian.h)"
#endif
#if HG_PD_SLOPE_MIN + 1 != HG_PD_RING_N
#error "HG_PD_RING_N must be HG_PD_SLOPE_MIN + 1"
#endif
#if HG_A_HIST_N != HG_A_HIST_N_DECL
#error "HG_A_HIST_N (cfg) != HG_A_HIST_N_DECL (hg_guardian.h)"
#endif
#include "hg_util.h"

#define MEDF_BB 1
#define MEDF_DIU 2
#define MEDF_LS 4
#define MEDF_ACE 8
#define MEDF_HRB HG_MEDF_HRB   /* B5-v7: other heart-rate-limiting drug / pacemaker (PROFILE field 5) */

static void margins(hg_guardian_t *g) {
  /* A7.2 "Older margin" + "Medication margins" = v1.2 hg_init() */
  const hg2_profile_t *p = &g->prof;
  float m = p->age >= HG_OLDER_AGE ? HG_M_OLDER : 0.0f;
  g->m_drink = m; g->m_cool = m;
  if (p->med_flags & (MEDF_DIU | MEDF_ACE)) g->m_drink += HG_M_DIURETIC_DRINK;
  if (p->med_flags & MEDF_LS) { g->m_drink += HG_M_LOW_SWEAT; g->m_cool += HG_M_LOW_SWEAT; }
  if (p->med_flags & MEDF_BB) { g->m_drink += HG_M_BETA_BLOCKER; g->m_cool += HG_M_BETA_BLOCKER; }
}

void hg_guardian_init(hg_guardian_t *g, const hg2_profile_t *p, const hg2_twin_t *tw) {
  memset(g, 0, sizeof *g);
  g->prof = *p; g->twin = *tw;
  hg2_init(&g->hg2, p, tw);
  hg_contact_init(&g->ct); hg_homeout_init(&g->ho); hg_routine_init(&g->rt);
  margins(g);
  for (int i = 0; i < 16; i++) g->ta_ring[i] = NAN;
  g->last_state = HG_ST_OK; g->last_mod = 0xFFFF; g->b_since = 65535u; g->b_last_f20 = 0.0f; g->a_base = 0.0f;
  g->mb_warm = 255; g->x_since = 65535u; g->x_last = -9.0f; g->x_dref = HG_X_DREF0;   /* M19 */
  g->sf_t1 = HG_SF_T1_OFF; g->sf_ta = HG_SF_TA_OFF; g->sf_run = 0; g->x_warm = 255;  /* B5-v7 */
}

void hg_guardian_set_twin(hg_guardian_t *g, const hg2_twin_t *tw) { g->twin = *tw; hg2_set_twin(&g->hg2, tw); }

/* v1.2 tier(): on after k consecutive true minutes; off at the HG_HOLD_MIN-th consecutive false minute */
static uint8_t tier(hg_tier_t *t, int cond, int k) {
  t->run = cond ? (uint8_t)(t->run < 255 ? t->run + 1 : 255) : 0;
  if (t->run >= k) { t->on = 1; t->off = 0; }
  else if (t->on) { if (cond) t->off = 0; else if (++t->off >= HG_HOLD_MIN) t->on = 0; }
  return t->on;
}
static int popcount64(uint64_t v) { int n = 0; while (v) { v &= v - 1; n++; } return n; }
static uint16_t inc16(uint16_t v) { return v < 65535u ? (uint16_t)(v + 1u) : v; }

static uint32_t new_alarm(hg_guardian_t *g) {
  g->alarm_seq++;
  return ((uint32_t)g->alarm_seq << 16) | g->minute_counter;   /* low 16 bits = minute counter (STATUS bytes 15-16) */
}

void hg_guardian_get_calm(const hg_guardian_t *g, hg_calm_t *out) { out->calm_f20_c = g->a_base; out->calm_f20_n = g->a_base_n; }
int hg_guardian_set_calm(hg_guardian_t *g, const hg_calm_t *in) {
  if (in->calm_f20_n == 0) { g->a_base = 0.0f; g->a_base_n = 0; return 1; }
  if (hg_isnan(in->calm_f20_c) || in->calm_f20_c < HG_A_BASE_MIN || in->calm_f20_c > HG_A_BASE_MAX) { g->a_base = 0.0f; g->a_base_n = 0; return 0; }
  g->a_base = in->calm_f20_c; g->a_base_n = in->calm_f20_n; return 1;
}

void hg_guardian_get_exc(const hg_guardian_t *g, hg_exc_t *out) { out->sxx = g->x_sxx; out->sxy = g->x_sxy; }
int hg_guardian_set_exc(hg_guardian_t *g, const hg_exc_t *in) {
  if (!hg_isfinite_bits(in->sxx) || !hg_isfinite_bits(in->sxy) || in->sxx < 0.0f) { g->x_sxx = 0.0f; g->x_sxy = 0.0f; g->x_c = 0.0f; return 0; }
  g->x_sxx = in->sxx; g->x_sxy = in->sxy;
  if (g->x_sxx > HG_X_SXX_MIN) { const float c = g->x_sxy / g->x_sxx; g->x_c = c < 0.0f ? 0.0f : (c > HG_X_C_MAX ? HG_X_C_MAX : c); }
  else g->x_c = 0.0f;
  return 1;
}

int hg_guardian_cmd(hg_guardian_t *g, const hg_cmd_t *c) {
  if (c->op == HG_CMD_FAMILY_ACK) {
    int ch = 0;
    if (g->family_pending && (c->alarm_id == g->alarm_id || (c->alarm_id & 0xFFFFu) == (g->alarm_id & 0xFFFFu))) { g->family_pending = 0; ch = 1; }
    /* A7.2 "Long press": HELP latched until phone 0x12 ack type 3 */
    if (g->help && c->ack_type == 3 && (c->alarm_id == g->help_id || (c->alarm_id & 0xFFFFu) == (g->help_id & 0xFFFFu))) { g->help = 0; ch = 1; }
    return ch;
  }
  if (c->op == HG_CMD_PROFILE) {
    float v = c->value;
    switch (c->field) {   /* R4 A5 field ids; 2 = resting HR (Twin bounds 40..100, ARCH 5) */
      case 2: if (v >= 40.0f && v <= 100.0f) { g->twin.rest_hr = v; hg2_set_twin(&g->hg2, &g->twin); return 1; } return 0;
      case 0: if (v >= HG_READING_MIN_C && v <= HG_READING_MAX_C) { g->reading_today = 1; return 1; } return 0;   /* M5.2; K/offset: hg_twin */
      case 4: if (v >= 0.0f && v <= 0.4f) { g->twin.c_bodyheat = v; hg2_set_twin(&g->hg2, &g->twin); return 1; } return 0;
      /* B5-v7: field 5 = medication flags (integer 0..31: 1 beta-blocker, 2 diuretic, 4 low-sweat, 8 ACE/ARB, 16 other HR-limiting
       * drug / pacemaker). Applied to the guardian margins and the skin-floor switch now; Core Sense (hg2) keeps its boot copy
       * until the next boot (the firmware saves the profile). Older phones never send field 5; older bands answer 0 (unknown). */
      case 5: if (v >= 0.0f && v <= 31.0f && v == (float)(int)v) { g->prof.med_flags = (uint8_t)(int)v; margins(g); return 1; } return 0;
      default: return 0;  /* 3 = sweat prior belongs to the phone (B3) */
    }
  }
  return 0;
}

static const char *const SCR_TXT[HG_SCR_N] = {
  "\xce\x8c\xce\xbb\xce\xb1 \xce\xba\xce\xb1\xce\xbb\xce\xac",                                   /* Όλα καλά */
  "\xce\xa0\xce\xb9\xce\xb5\xce\xaf\xcf\x84\xce\xb5 \xce\xbd\xce\xb5\xcf\x81\xcf\x8c \xcf\x84\xcf\x8e\xcf\x81\xce\xb1", /* Πιείτε νερό τώρα (R3 6.6) */
  "\xce\xa0\xce\xac\xcf\x84\xce\xb5 \xcf\x83\xce\xb5 \xcf\x80\xce\xb9\xce\xbf \xce\xb4\xcf\x81\xce\xbf\xcf\x83\xce\xb5\xcf\x81\xcf\x8c \xce\xb4\xcf\x89\xce\xbc\xce\xac\xcf\x84\xce\xb9\xce\xbf", /* Πάτε σε πιο δροσερό δωμάτιο */
  "\xce\xa7\xce\xbb\xce\xb9\xce\xb1\xcf\x81\xcf\x8c \xce\xbd\xcf\x84\xce\xbf\xcf\x85\xcf\x82 \xce\xae \xce\xba\xcf\x81\xcf\x8d\xce\xb1 \xce\xba\xce\xbf\xce\xbc\xcf\x80\xcf\x81\xce\xad\xcf\x83\xce\xb1", /* Χλιαρό ντους ή κρύα κομπρέσα */
  "\xce\x95\xce\xaf\xcf\x83\xcf\x84\xce\xb5 \xce\xba\xce\xb1\xce\xbb\xce\xac; \xce\xa0\xce\xb1\xcf\x84\xce\xae\xcf\x83\xcf\x84\xce\xb5 \xcf\x84\xce\xbf \xce\xba\xce\xbf\xcf\x85\xce\xbc\xcf\x80\xce\xaf", /* Είστε καλά; Πατήστε το κουμπί */
  "\xce\x95\xce\xb9\xce\xb4\xce\xbf\xcf\x80\xce\xbf\xce\xb9\xce\xae\xcf\x83\xce\xb1\xce\xbc\xce\xb5 \xcf\x84\xce\xb7\xce\xbd \xce\xbf\xce\xb9\xce\xba\xce\xbf\xce\xb3\xce\xad\xce\xbd\xce\xb5\xce\xb9\xce\xb1", /* Ειδοποιήσαμε την οικογένεια */
  "\xce\x95\xce\xbd\xcf\x84\xce\xac\xce\xbe\xce\xb5\xce\xb9, \xce\xb5\xcf\x85\xcf\x87\xce\xb1\xcf\x81\xce\xb9\xcf\x83\xcf\x84\xcf\x8e", /* Εντάξει, ευχαριστώ (design) */
  "\xce\xa6\xce\xbf\xcf\x81\xce\xad\xcf\x83\xcf\x84\xce\xb5 \xcf\x84\xce\xbf \xce\xb2\xcf\x81\xce\xb1\xcf\x87\xce\xb9\xcf\x8c\xce\xbb\xce\xb9", /* Φορέστε το βραχιόλι (A7.1) */
  "\xce\xa3\xcf\x86\xce\xaf\xce\xbe\xcf\x84\xce\xb5 \xcf\x84\xce\xbf \xce\xbb\xce\xbf\xcf\x85\xcf\x81\xce\xac\xce\xba\xce\xb9", /* Σφίξτε το λουράκι (A7.1) */
  "\xce\xa6\xce\xbf\xcf\x81\xcf\x84\xce\xaf\xcf\x83\xcf\x84\xce\xb5 \xcf\x84\xce\xbf \xce\xb2\xcf\x81\xce\xb1\xcf\x87\xce\xb9\xcf\x8c\xce\xbb\xce\xb9", /* Φορτίστε το βραχιόλι (design) */
  "\xce\x92\xce\xbf\xce\xae\xce\xb8\xce\xb5\xce\xb9\xce\xb1: \xce\xb5\xce\xb9\xce\xb4\xce\xbf\xcf\x80\xce\xbf\xce\xb9\xce\xbf\xcf\x8d\xce\xbc\xce\xb5 \xcf\x84\xce\xb7\xce\xbd \xce\xbf\xce\xb9\xce\xba\xce\xbf\xce\xb3\xce\xad\xce\xbd\xce\xb5\xce\xb9\xce\xb1" /* Βοήθεια: ειδοποιούμε την οικογένεια (design) */,
  "\xce\x94\xcf\x81\xce\xbf\xcf\x83\xce\xaf\xcf\x83\xcf\x84\xce\xb5 \xcf\x84\xce\xbf \xce\xb4\xcf\x89\xce\xbc\xce\xac\xcf\x84\xce\xb9\xce\xbf" /* Δροσίστε το δωμάτιο (M1.1 nudge) */
};
const char *hg_screen_text(uint8_t s) { return s < HG_SCR_N ? SCR_TXT[s] : ""; }

void hg_guardian_step(hg_guardian_t *g, const hg_minute_t *in_raw, hg_minute_out_t *out) {
  /* [B2-fix] 0978398: every float sensor input is guarded once here (hg2_guard.h): +-inf / NaN / out of sensor range -> NAN,
   * so the contact check, the routine, STATUS and hg2 all see the same "not available" value */
  hg_minute_t gm = *in_raw;
  gm.s.t1_c = hg2_guard_f(gm.s.t1_c, -40.0f, 85.0f); gm.s.t2_c = hg2_guard_f(gm.s.t2_c, -40.0f, 85.0f);
  gm.s.t_air_c = hg2_guard_f(gm.s.t_air_c, -40.0f, 85.0f); gm.s.rh_pct = hg2_guard_f(gm.s.rh_pct, 0.0f, 100.0f);
  gm.s.pi_pct = hg2_guard_f(gm.s.pi_pct, 0.0f, 100.0f); gm.s.a_std_g = hg2_guard_f(gm.s.a_std_g, 0.0f, 16.0f);
  gm.s.hr_bpm = hg2_finite_or_nan(gm.s.hr_bpm);
  for (int k = 0; k < 12; k++) {
    gm.t1_5s[k] = hg2_guard_f(gm.t1_5s[k], -40.0f, 85.0f); gm.t2_5s[k] = hg2_guard_f(gm.t2_5s[k], -40.0f, 85.0f);
    gm.tair_5s[k] = hg2_guard_f(gm.tair_5s[k], -40.0f, 85.0f);
  }
  const hg_minute_t *in = &gm;
  g->minute_counter++;
  const uint16_t mod = in->s.minute_of_day;
  const int tknown = mod < 1440u;
  /* ---- 1. contact self-check ---- */
  uint8_t ctw = hg_contact_step(&g->ct, in->t1_5s, in->t2_5s, in->tair_5s, in->s.pi_pct, in->s.hr_quality, in->ppg_dc,
                                in->s.a_std_g, in->flat_still_min, in->charging);
  const uint8_t worn = in->force_worn != 0xFF ? in->force_worn : ctw;
  /* ---- 2. Core Sense ---- */
  hg2_in_t s2 = in->s; s2.worn = worn;
  hg2_out_t core; hg2_aux_t aux;
  hg2_step_aux(&g->hg2, &s2, &core, &aux);
  if (g->nn_test_hook) g->nn_test_hook(&core, &aux, g->nn_test_ctx);   /* M3.1 test hook (NULL on the band) */
  if (g->hg2_dbg) *g->hg2_dbg = aux;
  const float tin = aux.t_air_corr;
  /* ---- 3. home / out ---- */
  const float astd = hg_isnan(in->s.a_std_g) ? 0.0f : in->s.a_std_g;
  g->walk_run = astd >= HG_WALK_G ? (uint8_t)(g->walk_run < 255 ? g->walk_run + 1 : 255) : 0;
  const uint8_t hour = tknown ? (uint8_t)(mod / 60u) : 0xFF;
  const uint8_t *fc = (in->has_forecast && in->forecast72) ? in->forecast72 : (const uint8_t *)0;
  const uint8_t ho = hg_homeout_step(&g->ho, tin, g->hg2.rh_last, g->walk_run, in->ble_bucket, hour, fc, fc ? 1 : 0);
  /* AC evidence (DESIGN, cfg): >= 2 C drop of corrected air within 15 min while HOME, latched 120 min */
  if (!g->started) { for (int i = 0; i < 16; i++) g->ta_ring[i] = tin; g->started = 1; }
  g->ta_ring[g->tai] = tin;
  const float ta15 = g->ta_ring[(g->tai + 1) % 16];
  g->tai = (uint8_t)((g->tai + 1) % 16);
  if (ho == HG_HO_HOME && !hg_isnan(tin) && !hg_isnan(ta15) && ta15 - tin >= HG_AC_STEP_C) g->ac_latch = HG_AC_LATCH_MIN;
  else if (g->ac_latch > 0) g->ac_latch--;
  /* ---- 4. buttons: long press = HELP anywhere (A7.2), latched ---- */
  int imok = 0;
  if (in->button == 2 && !g->help) {
    g->help = 1; g->help_id = new_alarm(g); g->alarm_id = g->help_id; g->family_pending = 1;
    g->check_active = 0; g->check_cause = 0;
  }
  /* ---- 5. tiers (frozen, not cleared, while worn == 0: A7.2 NOT_WORN) ---- */
  const int thermal_ok = core.valid && g->hg2.min_since_don >= HG_DON_BLANK_MIN;          /* A7.2 "Donning blank" */
  /* B5-v7: skin-floor EWMAs (every minute, worn or not) - read by the skin-floor Danger, the DRINK skin context and skin DRINK */
  {
    const float t1in = (worn != 0 && !hg_isnan(in->s.t1_c)) ? in->s.t1_c : HG_SF_T1_OFF;
    const float tain = hg_isnan(tin) ? HG_SF_TA_OFF : tin;
    g->sf_t1 = g->sf_t1 + HG_SF_A30 * (t1in - g->sf_t1);
    g->sf_ta = g->sf_ta + HG_SF_A60 * (tain - g->sf_ta);
  }
  /* M5.2: uncalibrated (no thermometer reading today) -> lower by min(0.10, half-width excess over the calibrated one) */
  const int midnight = tknown && g->last_mod < 1440u && mod < g->last_mod && g->last_mod - mod >= HG_MIDNIGHT_MIN_STEP;   /* T5 m1 */
  if (midnight) g->reading_today = 0;          /* a reading counts for its day */
  g->last_mod = mod;
  float unc = 0.0f;
  /* M4.3: in default mode a reading never changes a tier, so it cannot end the uncalibrated state either */
  const int calibrated = HG_TWIN_READING_MODE ? g->reading_today : 0;
  /* M4.3: the tiers read the forecast without the Twin's display offset (default) */
  const float off_alarm = HG_TWIN_READING_MODE ? g->hg2.core_offset : 0.0f;
  const float f20_nn = HG_TWIN_READING_MODE ? core.f20_eff : aux.core20_noff;
  const float f20_v12 = aux.v12_f20 + off_alarm;
  /* M11.3 OOD guard: outside hg2's training HR range the tiers read max(NN, v1.2) */
  const int ood = aux.x[14] > HG_OOD_RESERVE || aux.x[10] > HG_OOD_HR;
  const float f20_alarm = (ood && f20_v12 > f20_nn) ? f20_v12 : f20_nn;
  if (thermal_ok && !calibrated) {
#if HG_UNC_CONST_MODE
    unc = HG_UNC_LOWER_CONST < HG_UNC_MAX ? HG_UNC_LOWER_CONST : HG_UNC_MAX;   /* M11.4: B2's conformal widths */
#else
    float h = HG_UNC_Z * HG_UNC_SD_SCALE_EFF * core.sd_20 - HG_UNC_HALF_CAL_EFF;
    unc = h > HG_UNC_MAX ? HG_UNC_MAX : (h > 0.0f ? h : 0.0f);
#endif
  }
  int who_cond = 0;
  if (!hg_isnan(tin)) {
    int night = tknown && (mod >= HG_WHO_NIGHT_START || mod < HG_WHO_NIGHT_END);
    who_cond = tin >= (night ? HG_WHO_NIGHT_C : HG_WHO_DAY_C);                            /* time unknown -> day value */
  }
  g->who_hist = ((g->who_hist << 1) | (who_cond ? 1u : 0u)) & ((1ULL << HG_WHO_WIN) - 1ULL);
  const int who = popcount64(g->who_hist) >= HG_WHO_NEED && g->ac_latch == 0;
  /* M1.1: the WHO rule is not a tier trigger; at night it is the night_heat flag + one bedtime nudge per evening */
  const int night_known = tknown && (mod >= HG_WHO_NIGHT_START || mod < HG_WHO_NIGHT_END);
  const int night_heat = who && night_known;
  if (tknown && mod >= 720u && mod < HG_WHO_NIGHT_START) g->nudge_done = 0;   /* re-armed every afternoon */
  int nudge = 0;
  if (night_heat && !g->nudge_done && worn != 0) { nudge = 1; g->nudge_done = 1; }
  /* M1.3: total lowering (older + medication + uncertainty) capped at 0.20 C. Reason: margins sourced alone, sum unmeasured */
  float low_d = g->m_drink + unc, low_c = g->m_cool + unc;
  if (low_d > HG_M_TOTAL_CAP) low_d = HG_M_TOTAL_CAP;
  if (low_c > HG_M_TOTAL_CAP) low_c = HG_M_TOTAL_CAP;
#if HG_DRINK_DESIGN == 1 || HG_DRINK_DESIGN == 3 || HG_DRINK_DESIGN == 4
  /* M7 A: personal-relative line. Learn the calm f20 (daily median of resting daytime minutes), then DRINK when f20 rises
   * HG_A_DELTA above it; the absolute 37.85 C v1.2 line (no margins) stays as a ceiling - after M12 only WITH heat context
   * (corrected air >= T_ctx, above the older PSU line, or OOD), so it does not always fire (T5 m4). */
  if (midnight) {
    if (g->a_n >= HG_A_MIN_CALM) {
      uint32_t cum = 0; int i = 0;
      for (; i < HG_A_HIST_N; i++) { cum += g->a_hist[i]; if (2u * cum >= g->a_n) break; }
      float med = HG_A_HIST_T0 + HG_A_HIST_BIN * ((float)i + 0.5f);
      float b = g->a_base_n ? g->a_base + HG_A_EMA * (med - g->a_base) : med;
      g->a_base = b < HG_A_BASE_MIN ? HG_A_BASE_MIN : (b > HG_A_BASE_MAX ? HG_A_BASE_MAX : b);
      if (g->a_base_n < 255) g->a_base_n++;
    }
    for (int i = 0; i < HG_A_HIST_N; i++) g->a_hist[i] = 0;
    g->a_n = 0;
#if HG_DRINK_DESIGN == 4
    /* M19 Exception DRINK, nightly: fold today's sums (taken against x_dref) once a calm baseline exists, then her slope c */
    if (g->a_base_n > 0) {
      const float dsxy = g->x_dwd - (g->a_base - g->x_dref) * g->x_dw;
      g->x_sxx = HG_X_DECAY * g->x_sxx + g->x_dww;
      g->x_sxy = HG_X_DECAY * g->x_sxy + dsxy;
    }
    if (g->x_sxx > HG_X_SXX_MIN) { const float c = g->x_sxy / g->x_sxx; g->x_c = c < 0.0f ? 0.0f : (c > HG_X_C_MAX ? HG_X_C_MAX : c); }
    else g->x_c = 0.0f;
    g->x_dww = 0.0f; g->x_dwd = 0.0f; g->x_dw = 0.0f; g->x_dref = g->a_base_n > 0 ? g->a_base : HG_X_DREF0;
#endif
  }
  if (tknown && mod >= HG_A_DAY_START && mod < HG_A_DAY_END && worn == 2 && thermal_ok && !aux.active && g->level == 0) {
    float pos = (f20_alarm - HG_A_HIST_T0) / HG_A_HIST_BIN;
    if (pos >= 0.0f && pos < (float)HG_A_HIST_N && g->a_n < 65535u) { g->a_hist[(int)pos]++; g->a_n++; }
  }
  /* M11.2: DRINK = A-relative line on the (guarded) NN f20 OR the protected v1.2 f20 above the absolute ceiling;
   * the M5.2 lowering applies to both, inside the M1.3 cap */
  const float low_a = unc < HG_M_TOTAL_CAP ? unc : HG_M_TOTAL_CAP;
  /* M11 freeze note: the v1.2 ceiling is HR-only (not thermal), so it is gated at the 5-min `valid` point, not by the 20-min
   * thermal donning blank (A7.2 "no thermal alarms"); HTT dev: the 20-min gate cut DRINK lead 23 -> 6 min, sensitivity 87 -> 83 % */
  /* M12: the HR-only v1.2 ceiling counts only with heat context (room air >= T_ctx, air above the PSU older line, or OOD) */
  const int heat_ctx = !HG_V12_CTX || (!hg_isnan(tin) && tin >= HG_V12_CTX_C) || aux.env_above_old || ood;
  const int c_v12_drink = core.valid && heat_ctx && f20_v12 >= HG_T_DRINK - low_a;
#if HG_DRINK_DESIGN == 4
  /* M19 Exception DRINK: W30 ring (every minute), then the exception line */
  {
    const float aq = astd > HG_MB_ACLIP ? HG_MB_ACLIP : astd;
    const uint8_t q = (uint8_t)(aq / HG_X_W_STEP + 0.5f);
    g->x_wq = (uint16_t)(g->x_wq - g->x_ring[g->x_i] + q); g->x_ring[g->x_i] = q; g->x_i = (uint8_t)((g->x_i + 1) % HG_X_W_N);
  }
  const float w30 = (float)g->x_wq * HG_X_W_STEP;
  /* B5-v7: NN Exception line only with heat context (room air reached HG_X_CTX_C in the last HG_X_CTX_WIN min; 0 = off) */
  g->x_warm = (!hg_isnan(tin) && tin >= HG_X_CTX_C) ? 0 : (uint8_t)(g->x_warm < 255 ? g->x_warm + 1 : 255);
  const int x_ctx = (!(HG_X_CTX_C > 0.0f) || g->x_warm <= HG_X_CTX_WIN) && (!(HG_X_SKIN_C > 0.0f) || g->sf_t1 >= HG_X_SKIN_C);
  const int c_body1 = c_v12_drink || (x_ctx && thermal_ok && g->a_base_n > 0 && (f20_alarm - g->a_base) - g->x_c * w30 >= HG_X_DELTA - low_a);
#else
  const int c_body1 = c_v12_drink || (thermal_ok && g->a_base_n > 0 && f20_alarm - g->a_base >= HG_A_DELTA - low_a);
#endif
  (void)low_d;
#else
  const int c_body1 = thermal_ok && f20_alarm >= HG_T_DRINK - low_d;
#endif
  const int c_nn38 = thermal_ok && core.logit_p38 >= HG2_LOGIT_CUT_38;
  const int env1 = (aux.env_run >= HG_ENV_DRINK_RUN_MIN || aux.env_dose >= HG_ENV_DRINK_RUN_MIN)
                   || ((HG_SF_DRINK_C > 0.0f) && worn == 2 && thermal_ok && g->sf_ta >= HG_SF_TA_C && g->sf_t1 >= HG_SF_DRINK_C);   /* B5-v7 skin DRINK (protected, HR-free) */
  const int c_body2 = thermal_ok && f20_alarm >= HG_T_COOL - low_c;
  const int env2 = aux.env_dose >= HG_ENV_COOL_DOSE_MIN;
  g->hr_bad_run = core.hr_valid ? 0 : inc16(g->hr_bad_run);
  const int lg_ok = g->hr_bad_run <= HG_HR_GATE_MIN;                                        /* A7.2 "HR gating" */
  const int lg = lg_ok && core.valid && aux.v12_z >= HG_DG_LOGIT_CUT_V12;
  const int nn385 = thermal_ok && core.logit_p385 >= HG2_LOGIT_CUT_385;
  int beh = 0, pers_now = 0, marble = 0, cool_transit = 0;
#if HG_MARBLE
  /* ---- M19 Marble Danger state (every minute, worn or not) ---- */
  {
    const float xin = (worn != 0 && !hg_isnan(f20_alarm)) ? f20_alarm : HG_MB_F20_OFF;
    const float ain = astd > HG_MB_ACLIP ? HG_MB_ACLIP : astd;
    if (!g->mb_started) { g->mb_e10 = xin; g->mb_e60 = xin; g->mb_a30 = ain; g->mb_a120 = ain; g->mb_d = 0.0f; g->mb_started = 1; }
    g->mb_e10 = g->mb_e10 + HG_MB_A10 * (xin - g->mb_e10);
    g->mb_e60 = g->mb_e60 + HG_MB_A60 * (xin - g->mb_e60);
    g->mb_a30 = g->mb_a30 + HG_MB_A30 * (ain - g->mb_a30);
    g->mb_a120 = g->mb_a120 + HG_MB_A120 * (ain - g->mb_a120);
    g->mb_d = g->mb_d * HG_MB_DKEEP + (xin > HG_MB_KNEE ? xin - HG_MB_KNEE : 0.0f);
    g->mb_warm = (!hg_isnan(tin) && tin >= HG_MB_WARM_C) ? 0 : (uint8_t)(g->mb_warm < 255 ? g->mb_warm + 1 : 255);
    if (g->mb_age < 65535u) g->mb_age++;
    const int armed = thermal_ok && g->mb_age >= HG_MB_ARM_MIN && g->mb_warm <= HG_MB_WARM_WIN
                      && (!(HG_MB_SKIN_C > 0.0f) || g->sf_t1 >= HG_MB_SKIN_C);   /* B5-v7 skin arming (0 = off) */
    float s = HG_MB_W0;
    s = s + HG_MB_WL * (g->mb_e60 - HG_MB_LREF);
#if HG_MB_JUMP_RISE
    { const float jr = g->mb_e10 - g->mb_e60; s = s + HG_MB_WJ * (jr > 0.0f ? jr : 0.0f); }   /* M19b: a falling forecast never raises s */
#else
    s = s + HG_MB_WJ * (g->mb_e10 - g->mb_e60);
#endif
    s = s + HG_MB_WB * g->mb_a30;
    s = s + HG_MB_WS * g->mb_a120;
    s = s + HG_MB_WD * g->mb_d;
    g->mb_run = (armed && s >= HG_MB_CUT) ? (uint8_t)(g->mb_run < 255 ? g->mb_run + 1 : 255) : 0;
    marble = g->mb_run >= HG_MB_RUN_MIN;
  }
#endif
  int sfloor = 0;
#if HG_SF
  /* ---- B5-v7 SKIN-FLOOR Danger (HR-free): wrist skin EWMA30 near core in a hot room (cfg HG_SF_*) ---- */
  {
    const int hrb = (g->prof.med_flags & (MEDF_BB | MEDF_HRB)) != 0;
    const float cut = hrb ? HG_SF_T1_C - HG_SF_HRB_DT : HG_SF_T1_C;
    g->sf_run = (worn == 2 && thermal_ok && g->sf_ta >= HG_SF_TA_C && g->sf_t1 >= cut) ? (uint8_t)(g->sf_run < 255 ? g->sf_run + 1 : 255) : 0;
    sfloor = g->sf_run >= HG_SF_RUN_MIN;
  }
#endif
  /* M13 f20 ring (every minute, worn or not): f20_old = the tiers' f20 HG_PD_SLOPE_MIN minutes ago */
  /* T5 D2: a second ring holds the PROTECTED f20 (v1.2 anchor, no NN) so a protected-evidence persistence trigger never
   * depends on the NN forecast's slope (M3.1: the NN may only add triggers) */
  g->pd_ring[g->pd_i] = f20_alarm; g->pdv_ring[g->pd_i] = f20_v12;
  g->pd_i = (uint8_t)((g->pd_i + 1) % (HG_PD_SLOPE_MIN + 1));
  const float f20_old = g->pd_ring[g->pd_i], f20v_old = g->pdv_ring[g->pd_i];
  if (g->pd_n <= HG_PD_SLOPE_MIN) g->pd_n++;
  if (worn != 0) {
    g->strain_run = (thermal_ok && core.strain >= HG_STRAIN_COOL) ? inc16(g->strain_run) : 0;
    const int strain10 = g->strain_run >= HG_STRAIN_COOL_MIN;
    const int w1 = tier(&g->drink, c_body1 || c_nn38 || env1, HG_DEBOUNCE_MIN);   /* M1.1: WHO removed */
    tier(&g->cool, c_body2 || env2 || strain10, HG_DEBOUNCE_MIN);
    (void)w1;
    g->still_run = aux.still ? inc16(g->still_run) : 0;
    /* M3.1: the behaviour path runs on a SHADOW Go-cool tier built only from non-NN inputs (= v1.2's Go-cool: v1.2 f20 with
     * the capped margins, or the PSU heat dose). Reason: on the main COOL tier an NN that raises COOL earlier lets a harmless
     * press in those extra minutes "acknowledge" the episode and silence the behaviour DANGER - the NN would REMOVE an alarm. */
    /* M13 Danger by persistence: COOL on >= HG_PD_COOL_MIN, f20 not falling over HG_PD_SLOPE_MIN, + heat/body evidence */
    g->pd_cool_run = g->cool.on ? inc16(g->pd_cool_run) : 0;
    /* T5 D2: two triggers, OR-ed (M3.1: the NN may only ADD triggers, never veto a protected one).
     *  (a) PROTECTED: evidence = air above the PSU line or v1.2 Danger z high; slope of the protected v1.2 f20 (no NN input,
     *      except through the COOL tier, where the NN can only add minutes).
     *  (b) NN-added: evidence = NN P385 high; slope of the tiers' f20 (guarded NN). A silenced NN (logit -100) adds nothing. */
    const int pd_run_ok = HG_PD && g->cool.on && g->pd_cool_run >= HG_PD_COOL_MIN && g->pd_n > HG_PD_SLOPE_MIN;
    const int slope_v = !hg_isnan(f20_v12) && !hg_isnan(f20v_old) && f20_v12 - f20v_old >= -HG_PD_SLOPE_EPS_V12;
    const int pers_prot = pd_run_ok && slope_v && (aux.env_above || (core.valid && aux.v12_z >= HG_PD_V12_Z));
    const int slope_nn = !hg_isnan(f20_alarm) && !hg_isnan(f20_old) && f20_alarm - f20_old >= 0.0f;
    const int pers = pers_prot || (pd_run_ok && slope_nn && thermal_ok && core.logit_p385 >= HG_PD_NN_LOGIT);
    const int c_v12 = thermal_ok && aux.v12_f20 + off_alarm >= HG_T_COOL - (g->m_cool < HG_M_TOTAL_CAP ? g->m_cool : HG_M_TOTAL_CAP);
    const int wp = tier(&g->cool_p, c_v12 || env2, HG_DEBOUNCE_MIN);
    if (wp) { g->cool_min = inc16(g->cool_min); if (in->button) g->cool_ack = 1; } else { g->cool_min = 0; g->cool_ack = 0; }
    beh = wp && g->cool_min >= HG_BEH_COOL_MIN && g->still_run >= HG_STILL_MIN && !g->cool_ack;
    tier(&g->danger, lg || nn385 || beh || pers || marble || sfloor, HG_DEBOUNCE_MIN);
    pers_now = pers || marble || sfloor;   /* B5-v7: skin floor -> CHECK cause DANGER */
    /* M19 Exception DRINK settled rule on the DRINK tier: an NN-only START within HG_X_SETTLE_MIN of the last DRINK is held back
     * unless f20 rose HG_X_RISE_C above the f20 of the last nudge; protected starts (v1.2 ceiling, PSU env) are never held */
    int dshow = g->drink.on;
#if HG_DRINK_DESIGN == 4
    if (dshow && !g->x_prev) {
      if (g->x_since < HG_X_SETTLE_MIN && f20_alarm < g->x_last + HG_X_RISE_C && !(c_v12_drink || env1)) dshow = 0;
      else if (!hg_isnan(f20_alarm)) g->x_last = f20_alarm;   /* a NaN f20 never enters the settled state (D1) */
    }
    g->x_since = dshow ? (uint16_t)0 : (uint16_t)(g->x_since < 65535u ? g->x_since + 1u : 65535u);
    g->x_prev = (uint8_t)dshow;
#endif
    g->drink_shown = (uint8_t)dshow;
    /* ladder: escalation one level per minute max, de-escalation follows the tier holds (A7.2 "Hold / debounce") */
    const uint8_t target = g->danger.on ? 3 : g->cool.on ? 2 : dshow ? 1 : 0;
    if (target > g->level) g->level++; else g->level = target;
    /* M19b: the ladder just stepped 1 -> 2 while the Danger tier is already on (it reaches 3 next minute: the tier holds): this COOL
     * minute is a stepping stone - no COOL screen, no COOL vibration; the Danger screen shows now and the CHECK starts at level 3 */
    cool_transit = HG_COOL_TRANSIT && g->level == 2 && target == 3;
  }
  g->beh_now = (uint8_t)beh;
#if HG_DRINK_DESIGN == 4
  /* M19 Exception DRINK learning (R6 s7.1 'calm brain'): daytime, worn, thermal-ok, below COOL, room < 30 C (corrected air) */
  if (tknown && mod >= HG_A_DAY_START && mod < HG_A_DAY_END && worn == 2 && thermal_ok && g->level < 2 && !hg_isnan(tin)
      && tin < HG_X_CALM_TIN && !hg_isnan(f20_alarm)) {
    g->x_dww = g->x_dww + w30 * w30;
    g->x_dwd = g->x_dwd + w30 * (f20_alarm - g->x_dref);
    g->x_dw = g->x_dw + w30;
  }
#endif
  /* ---- 6. routine ---- */
  hg_routine_in_t ri;
  ri.minute_of_day = mod; ri.a_std_g = in->s.a_std_g; ri.zangle_5s = in->zangle_5s; ri.worn = worn;
#if HG_M7_ROUTINE
  ri.frozen = (uint8_t)(g->cool.on || g->danger.on || g->check_active);   /* M7.3 (i): DRINK does not freeze learning */
#else
  ri.frozen = (uint8_t)(g->drink.on || g->cool.on || g->danger.on);
#endif
  ri.heat_day = (uint8_t)(fc && tknown ? (fc[3 * hour + 2] & 1u) : 0u);
  ri.t_in = tin; ri.cool_on = g->cool.on; ri.impact = (uint8_t)(!hg_isnan(in->a_peak_g) && in->a_peak_g >= HG_IMPACT_G);
  ri.button = (uint8_t)(in->button != 0);
  hg_routine_out_t ro;
  hg_routine_step(&g->rt, &ri, &ro);
  /* ---- 7. CHECK (A7.2 "CHECK", "Short press during CHECK") ---- */
  uint8_t cause_now = 0;
  if (g->level == 3) cause_now |= (uint8_t)((lg || nn385 || pers_now) ? HG_CR_DANGER : 0) | (uint8_t)(beh ? HG_CR_BEHAVIOUR : 0);
  if (g->level == 3 && !(cause_now & (HG_CR_DANGER | HG_CR_BEHAVIOUR))) cause_now |= g->last_cause ? g->last_cause : HG_CR_DANGER; /* held */
  if (ro.req & HG_RT_REQ_QUIET) cause_now |= HG_CR_ROUTINE_QUIET;
  if (ro.req & HG_RT_REQ_NOWAKE) cause_now |= HG_CR_ROUTINE_NOWAKE;
  if (ro.req & HG_RT_REQ_IMPACT) cause_now |= HG_CR_IMPACT;
  if (g->level == 3) g->last_cause = (uint8_t)(cause_now & (HG_CR_DANGER | HG_CR_BEHAVIOUR)); else g->last_cause = 0;
  uint8_t hap = HG_HAP_NONE;
  int fam_now = 0;
  if (g->snooze > 0) g->snooze--;
  /* T5 D4: a CHECK already running keeps counting when the band comes off (contact worn == 0): the tiers are frozen as
   * NOT_WORN says, but the countdown is not - the family is called at the same minute as if nobody pressed (safety first;
   * a press while the band is off is not accepted), and the screen asks «Φορέστε το βραχιόλι». */
  const int check_off = g->check_active && worn == 0;
  if (!g->help && (worn != 0 || g->check_active)) {
    if (g->check_active) {
      /* causes that persist; impact stays until the wearer moves again; band off: the cause is held as it was */
      uint8_t keep = check_off ? g->check_cause : (uint8_t)(cause_now | ((g->check_cause & HG_CR_IMPACT) && !aux.active ? HG_CR_IMPACT : 0));
      g->check_cause |= keep;
      if (!(keep & 0x1Fu)) { g->check_active = 0; g->check_cause = 0; }
      else if (in->button == 1 && !check_off) {
        imok = 1; out->imok_resp_min = g->check_t; g->check_active = 0; g->check_cause = 0; g->snooze = HG_SNOOZE_MIN;
      } else {
        g->check_t = (uint8_t)(g->check_t < 255 ? g->check_t + 1 : 255);
        const uint8_t fmin = (g->check_cause & (HG_CR_DANGER | HG_CR_BEHAVIOUR)) ? HG_FAMILY_DANGER_MIN
                           : (g->check_cause & HG_CR_IMPACT) ? HG_FAMILY_IMPACT_MIN : HG_FAMILY_ROUTINE_MIN;
        if (g->check_t == HG_ASK_T1 || g->check_t == HG_ASK_T2) hap = HG_HAP_CHECK;
        if (!g->family_sent && g->check_t >= fmin) {
          g->family_sent = 1; g->family_pending = 1; g->alarm_id = new_alarm(g); fam_now = 1; hap = HG_HAP_CHECK;
        }
      }
    } else if (cause_now && g->snooze == 0) {
      g->check_active = 1; g->check_cause = cause_now; g->check_t = HG_ASK_T0; g->family_sent = 0; hap = HG_HAP_CHECK;
    }
  }
  /* short press outside a CHECK during COOL is the v1.2 acknowledgement (handled in the tier block) */
  /* ---- 7b. M7 B: DRINK nudge (one-shot, 2 h refractory unless f20 keeps rising) ---- */
#if HG_DRINK_DESIGN == 2 || HG_DRINK_DESIGN == 3
  if (g->b_left > 0) g->b_left--;
  if (g->b_since < 65535u) g->b_since++;
  if (g->level == 1 && worn != 0) {
    int onset = !g->b_prev_drink && g->b_since >= HG_B_REFRACTORY_MIN;
    int rising = g->b_since >= HG_B_NUDGE_MIN && f20_alarm >= g->b_last_f20 + HG_B_RISE_C;
    if (onset || rising) { g->b_left = HG_B_NUDGE_MIN; g->b_since = 0; g->b_last_f20 = f20_alarm; }
  }
  g->b_prev_drink = (uint8_t)(g->level >= 1);
#endif
  /* ---- 8. NOT_WORN ---- */
  g->notworn_min = worn == 0 ? inc16(g->notworn_min) : 0;
  /* ---- 9. state, screen, haptics ---- */
  uint8_t st, scr;
  if (g->help) { st = HG_ST_HELP; scr = HG_SCR_HELP; }
  else if (imok) { st = HG_ST_IMOK; scr = HG_SCR_IMOK; }
  else if (g->check_active) {
    st = (g->check_cause & (HG_CR_DANGER | HG_CR_BEHAVIOUR)) ? HG_ST_DANGER : HG_ST_CHECK;
    scr = worn == 0 ? HG_SCR_NOT_WORN : (g->family_sent ? HG_SCR_FAMILY : HG_SCR_CHECK);   /* T5 D4 */
  }
  else if (g->notworn_min >= HG_NOTWORN_SCREEN_MIN) { st = HG_ST_NOT_WORN; scr = HG_SCR_NOT_WORN; }
  else if (g->level == 3 || cool_transit) { st = HG_ST_DANGER; scr = HG_SCR_DANGER; }   /* M19b: transit = Danger flow, silent */
  else if (g->level == 2) { st = HG_ST_COOL; scr = HG_SCR_COOL; }
#if HG_DRINK_DESIGN == 2 || HG_DRINK_DESIGN == 3
  else if (g->level == 1 && g->b_left > 0) { st = HG_ST_DRINK; scr = HG_SCR_DRINK; }   /* M7 B: DRINK shown only as a nudge */
#else
  else if (g->level == 1) { st = HG_ST_DRINK; scr = HG_SCR_DRINK; }
#endif
  else if (!hg_isnan(in->vbat) && in->vbat < HG_VBAT_LOW) { st = HG_ST_BATTERY; scr = HG_SCR_BATTERY; }
  else { st = HG_ST_OK; scr = nudge ? HG_SCR_NUDGE : (worn == 1 ? HG_SCR_LOOSE : HG_SCR_OK); }
  if (hap == HG_HAP_NONE && st != g->last_state) {
    if (st == HG_ST_DRINK && g->last_state == HG_ST_OK) hap = HG_HAP_WATCH;
    else if (st == HG_ST_COOL && g->last_state < HG_ST_COOL) hap = HG_HAP_COOL;
    else if (st == HG_ST_HELP) hap = HG_HAP_CHECK;
    else if (st == HG_ST_IMOK) hap = HG_HAP_TICK;
  }
  if (hap == HG_HAP_NONE && nudge && st == HG_ST_OK) hap = HG_HAP_TICK;   /* M1.1: one soft cue with the bedtime nudge */
  if (hap != HG_HAP_NONE && !hg_isnan(in->vbat) && in->vbat < HG_VBAT_SOFT) hap = HG_HAP_SOFT;   /* R4 A8 */
  g->last_state = st;
  /* ---- 10. outputs ---- */
  out->state = st; out->level = g->level; out->family_alert = g->family_pending; out->alarm_id = g->alarm_id;
  out->check_reason = g->check_active ? g->check_cause : 0; out->check_min = g->check_active ? g->check_t : 0xFF;
  out->haptic = hap; out->screen = scr; out->core = core;
  out->routine_score = ro.routine_score; out->home_out = ho; out->worn = worn;
  out->why = (uint8_t)(core.why | (beh ? HG_WHY_NO_RESPONSE_G : 0) | (who ? HG_WHY_WHO : 0) | (unc > 0.0f ? HG2_WHY_UNCERTAIN : 0));
  out->notify_not_worn = (uint8_t)(g->notworn_min >= HG_NOTWORN_PHONE_MIN);
  out->tiers = (uint8_t)(g->drink_shown | (g->cool.on << 1) | (g->danger.on << 2));   /* M19: DRINK bit = after the settled rule */
  out->routine_req = ro.req;
  out->night_heat = (uint8_t)night_heat; out->nudge = (uint8_t)nudge;
  if (!imok) out->imok_resp_min = 0xFF;
  (void)fam_now;
  hg_status_t ss;
  static const uint8_t CODE[9] = { 0, 1, 2, 6, 3, 4, 0, 5, 7 };   /* HG_ST_* -> STATUS code (hg_frames.h) */
  ss.state_code = st == HG_ST_NOT_WORN ? g->level : CODE[st];
  if (st == HG_ST_NOT_WORN && g->level == 3) ss.state_code = 3;
  ss.contact_ok = worn == 2; ss.time_synced = (uint8_t)tknown; ss.charging = in->charging; ss.home = ho == HG_HO_HOME;
  ss.ppg_valid = core.hr_valid; ss.family_pending = g->family_pending; ss.not_worn = st == HG_ST_NOT_WORN;
  ss.core_c = core.valid ? core.core_now : NAN;
  ss.half_range_c = 1.645f * (core.sd_now > HG_SD_FLOOR ? core.sd_now : HG_SD_FLOOR);
  if (ss.half_range_c < HG_RANGE_HALF_REAL_EFF) ss.half_range_c = HG_RANGE_HALF_REAL_EFF;   /* [B2-fix] max(1.645 sd, REAL) */
  ss.hr_bpm = (in->s.hr_quality == 4 && in->s.hr_bpm >= 30.0f && in->s.hr_bpm <= 220.0f) ? in->s.hr_bpm : NAN;   /* [B2-fix]: hg2's HR gate */ ss.hr_q = in->s.hr_quality;
  ss.t1_c = in->s.t1_c; ss.t2_c = in->s.t2_c; ss.tair_c = in->s.t_air_c; ss.rh_pct = in->s.rh_pct;
  {
    float b = hg_isnan(in->vbat) ? 0.0f : (in->vbat - HG_VBAT_EMPTY) / (HG_VBAT_FULL - HG_VBAT_EMPTY) * 100.0f + 0.5f;
    ss.battery_pct = (uint8_t)(b <= 0.0f ? 0.0f : (b >= 100.0f ? 100.0f : b));
  }
  ss.routine_score = ro.routine_score;
  { float a = astd * 1000.0f + 0.5f; ss.activity = (uint8_t)(a >= 255.0f ? 255.0f : a); }
  ss.minute_counter = g->minute_counter; ss.alarm_id16 = (uint16_t)(g->alarm_id & 0xFFFFu);
  hg_status_pack(&ss, out->status);
}
