#include "hg_fp.h"   /* T5 D1: first include - IEEE-exact float semantics even under -ffast-math */
/* Heat Guardian - Core Sense hg2 runtime. Spec: ARCHITECTURE 4.1 (features), 4.3 (ensemble/uncertainty), 4.5 (API).
 * Feature semantics (B2's features.py must reproduce these; guardian/py/hg2_py.py is the bit-exact mirror):
 *  - "hold" features (t1, t_air, rh) keep the last finite value; NaN until first seen. Any NaN feature is
 *    replaced by its training mean at normalisation (z = 0)  ==  the "masked to 0" rule of ARCH 4.2 for HTT rows.
 *  - delta features are 0 when either end is NaN. Rings start filled with the first value (as v1.2's kfring).
 *  - T1 is held (frozen) while worn == 0. T2 is never held (flux needs a live reference).
 *  - hr: last minute with hr_quality == 4 (OK) and 30..220 bpm, held; hr_valid = OK in >= 3 of the last 5 minutes.
 *  - The Kalman anchor gets the OK-quality HR or NAN (v1.2 then holds its own last value).
 *  - Unknown air for the v1.2 linear model: 25 C / 50 % (DESIGN default; coefficients 0.002 C/C and -0.01 C/%). */
#include <math.h>
#include "hg2_state.h"
#include "hg2_weights.h"
#include "hg_util.h"
#include "hg_guardian_cfg.h"
#include "hg2_guard.h"
#if HG_ENV_ACT_WIN < 1 || HG_ENV_ACT_WIN > 31
#error "HG_ENV_ACT_WIN must fit the 32-bit activity history"
#endif

#if HG2_NN_IN != HG2_N_IN || HG2_NN_ENS != HG2_N_ENS || (HG2_NN_OUT != HG2_N_OUT && HG2_NN_OUT != HG2_N_OUT + 3)
#error "hg2_weights.h does not match the ARCH 4.5 network shape 32-24-16-6 x5"
#endif

#define HG_MEDF_BB   1   /* HG_MED_BETA_BLOCKER */
#define HG_MEDF_LS   4   /* HG_MED_LOW_SWEAT */
#define T1NB_NONE    (-32768)

/* feature indices, ARCH 4.1 order */
enum { X_T1, X_T1_D5, X_T1_D15, X_DT, X_DT_D10, X_FLUX_VALID, X_T_AIR, X_T_AIR_D15, X_RH, X_T1_MINUS_AIR,
       X_HR, X_HR_EWM5, X_HR_EWM45, X_HR_ABOVE_REST, X_HR_RESERVE, X_HR_VALID, X_LOG_PI, X_ACT, X_ACT_EWM30,
       X_MIN_SINCE_ACTIVE, X_KF, X_HEAT_DOSE, X_MIN_SINCE_DON, X_SIN_TOD, X_COS_TOD, X_CORE_FLUX, X_T1_ANOM,
       X_AGE, X_SEX_M, X_BMI, X_BB, X_LOW_SWEAT };

uint16_t hg2_state_size(void) { return (uint16_t)sizeof(hg2_state_t); }

static int is_num(float x) { return !hg_isnan(x); }

void hg2_set_twin(hg2_state_t *s, const hg2_twin_t *tw) {
  s->rest_hr = tw->rest_hr; s->k_person = tw->k_person; s->core_offset = tw->core_offset; s->c_bodyheat = tw->c_bodyheat;
  for (int h = 0; h < 24; h++) {
    float b = tw->t1_night_base[h];
    s->t1nb[h] = (!hg_isnan_bits(b) && b > 0.0f && b < 60.0f) ? (int16_t)floorf(b * 100.0f + 0.5f) : (int16_t)T1NB_NONE;
  }
  hg_kf_set_rest_hr(&s->kf, tw->rest_hr);
}

void hg2_init(hg2_state_t *s, const hg2_profile_t *p, const hg2_twin_t *tw) {
  hg_kf_init(&s->kf, p->age, p->sex_m > 0.5f, p->bmi, tw->rest_hr, p->med_flags);
  s->age = p->age; s->sex_m = p->sex_m; s->bmi = p->bmi; s->hrmax = s->kf.hrmax; s->med_flags = p->med_flags;
  s->older_env = (uint8_t)((p->age >= HG_OLDER_AGE) || (p->med_flags != 0));   /* v1.2 rule: older line if 65+ or any flag */
  hg2_set_twin(s, tw);
  s->hr_last = tw->rest_hr; s->hr_e5 = tw->rest_hr; s->hr_e45 = tw->rest_hr; s->act_e30 = 0.0f;
  s->t1_last = NAN; s->t2_last = NAN; s->tair_last = NAN; s->rh_last = NAN;
  for (int i = 0; i < 16; i++) { s->ring_t1[i] = NAN; s->ring_tair[i] = NAN; }
  for (int i = 0; i < 11; i++) s->ring_dt[i] = 0.0f;
  s->act_hist = 0; s->min_since_active = 0; s->min_since_don = 0; s->env_run = 0; s->env_dose = 0;
  s->hr_age = 0; s->hr_q_hist = 0; s->ri16 = 0; s->ri11 = 0; s->started = 0; s->last_worn = 0;
}

static void dense(const float *W, const float *b, const float *x, float *y, int n_in, int n_out, int relu) {
  for (int o = 0; o < n_out; o++) {
    const float *w = W + o * n_in;
    float acc = b[o];
    for (int i = 0; i < n_in; i++) acc += w[i] * x[i];      /* sequential order: the Python mirror depends on it */
    y[o] = (relu && acc < 0.0f) ? 0.0f : acc;
  }
}
/* mean/sd over members for every network output (sd = between-member); ale[0..2] = mean_k(v_k^2 + EPS_V) of the three
 * sd heads when the export has them (M11: 32-24-16-9, outputs 6..8), else 0. Order = B2's export.py outputs() (golden). */
static void ensemble(const float *z, float *mean, float *sd, float *ale) {
  float s[HG2_NN_OUT], s2[HG2_NN_OUT], a[3] = { 0.0f, 0.0f, 0.0f };
  for (int o = 0; o < HG2_NN_OUT; o++) { s[o] = 0.0f; s2[o] = 0.0f; }
  for (int k = 0; k < HG2_N_ENS; k++) {
    float h1[HG2_NN_H1], h2[HG2_NN_H2], y[HG2_NN_OUT];
    const hg2_member_t *m = &HG2_MEMBERS[k];
    dense(m->W1, m->b1, z, h1, HG2_N_IN, HG2_NN_H1, 1);
    dense(m->W2, m->b2, h1, h2, HG2_NN_H1, HG2_NN_H2, 1);
    dense(m->W3, m->b3, h2, y, HG2_NN_H2, HG2_NN_OUT, 0);
    for (int o = 0; o < HG2_NN_OUT; o++) { s[o] += y[o]; s2[o] += y[o] * y[o]; }
#if HG2_NN_OUT == HG2_N_OUT + 3
    for (int o = 0; o < 3; o++) a[o] += y[HG2_N_OUT + o] * y[HG2_N_OUT + o] + HG2_EPS_V;
#endif
  }
  for (int o = 0; o < HG2_NN_OUT; o++) {
    float mu = s[o] / (float)HG2_N_ENS;
    float var = s2[o] / (float)HG2_N_ENS - mu * mu;
    mean[o] = mu; sd[o] = var > 0.0f ? sqrtf(var) : 0.0f;
  }
  for (int o = 0; o < 3; o++) ale[o] = a[o] / (float)HG2_N_ENS;
}

static uint32_t crc32_update(uint32_t crc, const void *p, uint32_t n) {
  const uint8_t *b = (const uint8_t *)p;
  crc = ~crc;
  while (n--) { crc ^= *b++; for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u))); }
  return ~crc;
}
int hg2_check_crc(void) {
  uint32_t c = 0;
  for (int k = 0; k < HG2_N_ENS; k++) {
    const hg2_member_t *m = &HG2_MEMBERS[k];
    c = crc32_update(c, m->W1, 4u * HG2_NN_H1 * HG2_N_IN);  c = crc32_update(c, m->b1, 4u * HG2_NN_H1);
    c = crc32_update(c, m->W2, 4u * HG2_NN_H2 * HG2_NN_H1); c = crc32_update(c, m->b2, 4u * HG2_NN_H2);
    c = crc32_update(c, m->W3, 4u * HG2_NN_OUT * HG2_NN_H2); c = crc32_update(c, m->b3, 4u * HG2_NN_OUT);
  }
  return c == HG2_NN_CRC32;
}

static float clampf(float x, float lo, float hi) { return x < lo ? lo : (x > hi ? hi : x); }
static int popcount32(uint32_t v) { int n = 0; while (v) { v &= v - 1; n++; } return n; }

void hg2_step(hg2_state_t *s, const hg2_in_t *in, hg2_out_t *out) { hg2_step_aux(s, in, out, (hg2_aux_t *)0); }

void hg2_step_aux(hg2_state_t *s, const hg2_in_t *in_raw, hg2_out_t *out, hg2_aux_t *aux) {
  float x[HG2_N_IN];
  /* [B2-fix] 0978398 input guards (hg2_guard.h): +-inf, NaN and out-of-sensor-range values are "not available" (NAN).
   * SOURCE: TMP117/SHTC3 -40..85 C, RH 0..100 %, PI 0..100 %, a_std 0..16 g (ICM-20649 full scale); HR keeps its 30..220 gate */
  hg2_in_t gin = *in_raw;
  gin.t1_c = hg2_guard_f(gin.t1_c, -40.0f, 85.0f); gin.t2_c = hg2_guard_f(gin.t2_c, -40.0f, 85.0f);
  gin.t_air_c = hg2_guard_f(gin.t_air_c, -40.0f, 85.0f); gin.rh_pct = hg2_guard_f(gin.rh_pct, 0.0f, 100.0f);
  gin.pi_pct = hg2_guard_f(gin.pi_pct, 0.0f, 100.0f); gin.a_std_g = hg2_guard_f(gin.a_std_g, 0.0f, 16.0f);
  gin.hr_bpm = hg2_finite_or_nan(gin.hr_bpm);
  const hg2_in_t *in = &gin;
  const uint8_t worn = in->worn;
  /* --- donning counter (feature 22, valid, flux gate) --- */
  if (worn == 2) {
    if (s->last_worn != 2) s->min_since_don = 0; else if (s->min_since_don < 60) s->min_since_don++;
  } else s->min_since_don = 0;
  s->last_worn = worn;
  /* --- temperatures --- */
  if (worn != 0 && is_num(in->t1_c)) s->t1_last = in->t1_c;
  const float t1 = s->t1_last;
  const int t1ok = is_num(t1);
  const float t2 = in->t2_c;
  if (is_num(in->t_air_c)) s->tair_last = in->t_air_c;
  if (is_num(in->rh_pct)) s->rh_last = in->rh_pct;
  const float traw = s->tair_last, rh = s->rh_last;
  float tair = traw;
  if (is_num(traw) && t1ok) tair = traw - s->c_bodyheat * (t1 - traw);     /* ARCH 4.1 #6 body-heat correction */
  const int tairok = is_num(tair);
  const int flux_valid = (worn == 2) && t1ok && is_num(t2) && tairok && (t1 - t2 > 0.15f) && (tair < t1 - 0.5f)
                         && (s->min_since_don >= HG_DON_BLANK_MIN);        /* ARCH 4.1 #5, R2 s7.6 */
  const float dT = flux_valid ? (t1 - t2) : 0.0f;
  if (!s->started) {
    for (int i = 0; i < 16; i++) { s->ring_t1[i] = t1; s->ring_tair[i] = tair; }
    for (int i = 0; i < 11; i++) s->ring_dt[i] = dT;
    s->started = 1;
  }
  s->ring_t1[s->ri16] = t1; s->ring_tair[s->ri16] = tair; s->ring_dt[s->ri11] = dT;
  const float t1_5 = s->ring_t1[(s->ri16 + 11) % 16], t1_15 = s->ring_t1[(s->ri16 + 1) % 16];
  const float ta_15 = s->ring_tair[(s->ri16 + 1) % 16], dt_10 = s->ring_dt[(s->ri11 + 1) % 11];
  s->ri16 = (uint8_t)((s->ri16 + 1) % 16); s->ri11 = (uint8_t)((s->ri11 + 1) % 11);
  x[X_T1] = t1;
  x[X_T1_D5] = (t1ok && is_num(t1_5)) ? t1 - t1_5 : 0.0f;
  x[X_T1_D15] = (t1ok && is_num(t1_15)) ? t1 - t1_15 : 0.0f;
  x[X_DT] = dT;
  x[X_DT_D10] = flux_valid ? dT - dt_10 : 0.0f;
  x[X_FLUX_VALID] = flux_valid ? 1.0f : 0.0f;
  x[X_T_AIR] = tair;
  x[X_T_AIR_D15] = (tairok && is_num(ta_15)) ? tair - ta_15 : 0.0f;
  x[X_RH] = rh;
  x[X_T1_MINUS_AIR] = (t1ok && tairok) ? t1 - tair : NAN;
  /* --- heart rate --- */
  const int hr_good = (in->hr_quality == 4) && (in->hr_bpm >= 30.0f) && (in->hr_bpm <= 220.0f);
  if (hr_good) { s->hr_last = in->hr_bpm; s->hr_age = 0; } else if (s->hr_age < 255) s->hr_age++;
  s->hr_q_hist = (uint8_t)(((s->hr_q_hist << 1) | (hr_good ? 1u : 0u)) & 0x1Fu);
  const int hr_valid = popcount32(s->hr_q_hist) >= 3;
  const float hr = s->hr_last;
  s->hr_e5 = s->hr_e5 + HG_EWM_A5 * (hr - s->hr_e5);
  s->hr_e45 = s->hr_e45 + HG_EWM_A45 * (hr - s->hr_e45);
  x[X_HR] = hr; x[X_HR_EWM5] = s->hr_e5; x[X_HR_EWM45] = s->hr_e45;
  x[X_HR_ABOVE_REST] = hr - s->rest_hr;
  x[X_HR_RESERVE] = (hr - s->rest_hr) / (s->hrmax - s->rest_hr);
  x[X_HR_VALID] = hr_valid ? 1.0f : 0.0f;
  x[X_LOG_PI] = is_num(in->pi_pct) ? hg_ln1p(in->pi_pct) : 0.0f;
  /* --- motion --- */
  const float astd = is_num(in->a_std_g) ? in->a_std_g : 0.0f;
  const float act = hg_ln1p(100.0f * astd);
  s->act_e30 = s->act_e30 + HG_EWM_A30 * (act - s->act_e30);
  const int active = astd > HG_ACTIVE_G;                       /* A7.2 "Still / active" */
  if (active) s->min_since_active = 0; else if (s->min_since_active < 240) s->min_since_active++;
  s->act_hist = (s->act_hist << 1) | (active ? 1u : 0u);
  const int active30 = popcount32(s->act_hist & ((1u << HG_ENV_ACT_WIN) - 1u));   /* T5 m3: window from cfg (30 -> 0x3FFFFFFF) */
  x[X_ACT] = act; x[X_ACT_EWM30] = s->act_e30; x[X_MIN_SINCE_ACTIVE] = (float)s->min_since_active / 240.0f;
  /* --- v1.2 Kalman anchor --- */
  hg_kf_out_t ko;
  hg_kf_step(&s->kf, hr_good ? in->hr_bpm : NAN, tairok ? tair : 25.0f, is_num(rh) ? rh : 50.0f, &ko);
  x[X_KF] = ko.kf;
  /* --- PSU environmental limit (A7.2 "Env-prior line") and heat dose --- */
  int above = 0, above_old = 0; float pa = NAN, lim = NAN;
  if (tairok && is_num(rh)) {
    float a, b;
    const int adl = active30 >= HG_ENV_ACT_MIN;
    const float ao = adl ? HG_LIM_OLD_ADL_A : HG_LIM_OLD_REST_A, bo = adl ? HG_LIM_OLD_ADL_B : HG_LIM_OLD_REST_B;
    if (!s->older_env) { a = HG_LIM_YOUNG_A; b = HG_LIM_YOUNG_B; } else { a = ao; b = bo; }
    pa = hg_pa_kpa(tair, rh); lim = a + b * tair;
    above = pa >= lim;
    above_old = pa >= ao + bo * tair;          /* M12 heat context: the older-adult line for every wearer */
  }
  s->env_run = above ? (int16_t)(s->env_run < 30000 ? s->env_run + 1 : s->env_run) : 0;
  if (above) { if (s->env_dose < HG_ENV_DOSE_CAP) s->env_dose++; } else if (s->env_dose > 0) s->env_dose--;
  x[X_HEAT_DOSE] = (float)s->env_dose / 240.0f;
  x[X_MIN_SINCE_DON] = (float)s->min_since_don / 60.0f;
  const int tknown = in->minute_of_day < 1440u;
  x[X_SIN_TOD] = tknown ? hg_sin_tod(in->minute_of_day) : 0.0f;
  x[X_COS_TOD] = tknown ? hg_cos_tod(in->minute_of_day) : 0.0f;
  float core_flux = t1;
  if (flux_valid) core_flux = clampf(t1 + s->k_person * dT, t1, t1 + 2.5f);   /* R2 s7.6 clamp */
  x[X_CORE_FLUX] = core_flux;
  float t1a = 0.0f;
  if (tknown && t1ok) { int16_t b = s->t1nb[in->minute_of_day / 60u]; if (b != T1NB_NONE) t1a = t1 - (float)b / 100.0f; }
  x[X_T1_ANOM] = t1a;
  x[X_AGE] = s->age / 100.0f; x[X_SEX_M] = s->sex_m; x[X_BMI] = s->bmi / 30.0f;
  x[X_BB] = (s->med_flags & HG_MEDF_BB) ? 1.0f : 0.0f;
  x[X_LOW_SWEAT] = (s->med_flags & HG_MEDF_LS) ? 1.0f : 0.0f;
  /* --- ensemble --- */
  float z[HG2_N_IN], mean[HG2_NN_OUT], sd[HG2_NN_OUT], ale[3];
  for (int i = 0; i < HG2_N_IN; i++) { float v = x[i]; z[i] = is_num(v) ? hg2_z_guard((v - HG2_X_MEAN[i]) / HG2_X_STD[i]) : 0.0f; }   /* [B2-fix] z guard */
  ensemble(z, mean, sd, ale);
  /* --- outputs --- */
  const float off = s->core_offset;
#if HG2_WEIGHTS_STUB
  (void)ale;
  out->core_now = ko.est + off; out->core_20 = ko.f20 + off; out->core_30 = ko.f20 + off;
  out->sd_now = ko.sd; out->sd_20 = 0.0f; out->sd_30 = 0.0f;
  out->logit_p38 = -100.0f; out->logit_p385 = -100.0f;
  {
    float psi = 5.0f * (ko.est - HG_PSI_T0) / (HG_PSI_TMAX - HG_PSI_T0) + 5.0f * (hr - s->rest_hr) / (s->hrmax - s->rest_hr);
    out->strain = clampf(psi, 0.0f, 10.0f);
  }
#else
  out->core_now = mean[0] * HG2_Y_STD[0] + HG2_Y_MEAN[0] + off;
  out->core_20 = mean[1] * HG2_Y_STD[1] + HG2_Y_MEAN[1] + off;
  out->core_30 = mean[2] * HG2_Y_STD[2] + HG2_Y_MEAN[2] + off;
#if HG2_NN_OUT == HG2_N_OUT + 3
  /* M6.2 / M11: total sd = sqrtf(aleatoric (sd heads) + between-member variance) in normalised units, times Y_STD */
  { float tot[3]; for (int o = 0; o < 3; o++) tot[o] = sqrtf(ale[o] + sd[o] * sd[o]);
    out->sd_now = tot[0] * HG2_Y_STD[0]; out->sd_20 = tot[1] * HG2_Y_STD[1]; out->sd_30 = tot[2] * HG2_Y_STD[2]; }
#else
  out->sd_now = sd[0] * HG2_Y_STD[0]; out->sd_20 = sd[1] * HG2_Y_STD[1]; out->sd_30 = sd[2] * HG2_Y_STD[2];
#endif
  out->logit_p38 = mean[3]; out->logit_p385 = mean[4];
  out->strain = clampf(mean[5], 0.0f, 10.0f);
  /* [B2-fix] bounded outputs (hg2_guard.h): core 30..45 C, sd 0..3 C, logits -100..100 */
  out->core_now = hg2_clampf(out->core_now, 30.0f, 45.0f); out->core_20 = hg2_clampf(out->core_20, 30.0f, 45.0f);
  out->core_30 = hg2_clampf(out->core_30, 30.0f, 45.0f);
  out->sd_now = hg2_clampf(out->sd_now, 0.0f, 3.0f); out->sd_20 = hg2_clampf(out->sd_20, 0.0f, 3.0f);
  out->sd_30 = hg2_clampf(out->sd_30, 0.0f, 3.0f);
  out->logit_p38 = hg2_clampf(out->logit_p38, -100.0f, 100.0f); out->logit_p385 = hg2_clampf(out->logit_p385, -100.0f, 100.0f);
#endif
  /* M5.1: D7 replaced - what the tiers use is the forecast itself (no "+1 sd"); field kept for API stability */
  out->f20_eff = out->core_20;
  const float core20_noff = HG2_WEIGHTS_STUB ? ko.f20 : hg2_clampf(mean[1] * HG2_Y_STD[1] + HG2_Y_MEAN[1], 30.0f, 45.0f);   /* M4.3 */
  out->f30_eff = out->core_30;
  out->kf = ko.kf;
  out->core_flux = flux_valid ? core_flux : NAN;
  out->flux_valid = (uint8_t)flux_valid; out->hr_valid = (uint8_t)hr_valid;
  out->valid = (uint8_t)((worn == 2) && (s->min_since_don >= HG_DON_VALID_MIN));
  out->why = (uint8_t)((above ? HG2_WHY_ENV_LIMIT : 0) | (s->env_dose >= HG_ENV_COOL_DOSE_MIN ? HG2_WHY_TIME_IN_HEAT : 0)
             | (ko.z >= HG_DG_LOGIT_CUT_V12 ? HG2_WHY_DANGER_P : 0) | (out->f20_eff >= HG_T_DRINK ? HG2_WHY_BODY : 0)
             | ((out->logit_p38 >= HG2_LOGIT_CUT_38 || out->logit_p385 >= HG2_LOGIT_CUT_385) ? HG2_WHY_NN : 0));
  /* HG2_WHY_UNCERTAIN is now set by the Guardian Loop when the M5.2 lowering is active */
  if (aux) {
    for (int i = 0; i < HG2_N_IN; i++) aux->x[i] = x[i];
    for (int o = 0; o < HG2_N_OUT; o++) { aux->nn_mean[o] = mean[o]; aux->nn_sd[o] = sd[o]; }
    aux->core20_noff = core20_noff;
    aux->v12_est = ko.est; aux->v12_f20 = ko.f20; aux->v12_z = ko.z; aux->v12_sd = ko.sd;
    aux->t_air_corr = tair; aux->pa_kpa = pa; aux->lim_kpa = lim; aux->env_run = s->env_run; aux->env_dose = s->env_dose;
    aux->env_above = (uint8_t)above; aux->env_above_old = (uint8_t)above_old; aux->active = (uint8_t)active; aux->still = (uint8_t)(astd <= HG_STILL_G);
    aux->active30 = (uint8_t)active30;
  }
}
