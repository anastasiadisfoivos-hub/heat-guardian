#include "hg_fp.h"   /* T5 D1: first include - IEEE-exact float semantics even under -ffast-math */
/* See hg_kf.h. Constants: /home/claude/hgmodel/heat_guardian_model.h (copied below as the v1.2 export; do not edit). */
#include "hg_kf.h"
#include "hg_tables.h"
#include "hg_util.h"
#include "hg_guardian_cfg.h"
#include "heat_guardian_model_v12.h"

void hg_kf_init(hg_kf_t *s, float age, int male, float bmi, float rest_hr, uint8_t med_flags) {
  s->age = age; s->sex_m = male ? 1.0f : 0.0f; s->bmi = bmi; s->rest_hr = rest_hr; s->flags = med_flags;
  s->hrmax = (med_flags & HG_MED_BETA_BLOCKER) ? (HG_HRMAX_BB_A - HG_HRMAX_B * age)   /* Brawner 2004 */
                                               : (HG_HRMAX_A - HG_HRMAX_B * age);     /* Tanaka 2001, true age */
  s->ct = HG_KF_CT0; s->v = HG_KF_V0;
  s->e5 = s->e15 = s->e45 = rest_hr;
  s->rh_clamp = 1;   /* M1.2 default on; the v1.2 reference harness sets 0 */
  s->nhr = 0; s->started_k = 0; s->started_e = 0; s->ki = 0; s->ei = 0;
  s->w60 = 0; s->last_hr = rest_hr;
  for (int i = 0; i < 3; i++) s->hrbuf[i] = 0.0f;
  for (int i = 0; i < 16; i++) s->kfring[i] = 0.0f;
  for (int i = 0; i < 11; i++) s->estring[i] = 0.0f;
}

void hg_kf_set_rest_hr(hg_kf_t *s, float rest_hr) { s->rest_hr = rest_hr; }

static float med3(const float *b, int n) {
  if (n == 1) return b[0];
  if (n == 2) return 0.5f * (b[0] + b[1]);
  float a = b[0], c = b[1], d = b[2];
  if (a > c) { float t = a; a = c; c = t; }
  if (c > d) { c = d; }
  return a > c ? a : c;
}
static int popcount64(uint64_t v) { int n = 0; while (v) { v &= v - 1; n++; } return n; }

void hg_kf_step(hg_kf_t *s, float hr_bpm, float amb_c, float rh, hg_kf_out_t *o) {
  (void)rh;
  if (hg_isnan_bits(hr_bpm) || hr_bpm < 30.0f || hr_bpm > 220.0f) hr_bpm = s->last_hr;   /* hold last good value (v1.2) */
  s->last_hr = hr_bpm;
  float ctp = HG_KF_A * s->ct, vp = HG_KF_A * HG_KF_A * s->v + HG_KF_GAMMA * HG_KF_GAMMA;
  float c = 2.0f * HG_KF_B2 * ctp + HG_KF_B1;
  float k = vp * c / (c * c * vp + HG_KF_SIGMA * HG_KF_SIGMA);
  float hrp = HG_KF_B2 * ctp * ctp + HG_KF_B1 * ctp + HG_KF_B0;
  s->ct = ctp + k * ((hr_bpm - (s->rest_hr - 70.0f)) - hrp);
  s->v = (1.0f - k * c) * vp;
  if (s->nhr < 3) s->hrbuf[s->nhr++] = hr_bpm; else { s->hrbuf[0] = s->hrbuf[1]; s->hrbuf[1] = s->hrbuf[2]; s->hrbuf[2] = hr_bpm; }
  s->e5 = s->e5 + HG_EWM_A5 * (hr_bpm - s->e5);
  s->e15 = s->e15 + HG_EWM_A15 * (hr_bpm - s->e15);
  s->e45 = s->e45 + HG_EWM_A45 * (hr_bpm - s->e45);
  if (!s->started_k) { for (int i = 0; i < 16; i++) s->kfring[i] = s->ct; s->started_k = 1; }
  s->kfring[s->ki] = s->ct;
  float kf15 = s->kfring[(s->ki + 1) % 16];
  s->ki = (uint8_t)((s->ki + 1) % 16);
  float age_c = s->age < HG_AGE_MIN ? HG_AGE_MIN : (s->age > HG_AGE_MAX ? HG_AGE_MAX : s->age);
  float x[HG_N_FEAT];
  x[HG_F_HR] = med3(s->hrbuf, s->nhr);
  x[HG_F_HR_EWM5] = s->e5; x[HG_F_HR_EWM15] = s->e15; x[HG_F_HR_EWM45] = s->e45;
  x[HG_F_HR_ABOVE_REST] = s->e5 - s->rest_hr;
  x[HG_F_HR_RESERVE_FRAC] = (s->e5 - s->rest_hr) / (s->hrmax - s->rest_hr);
  x[HG_F_HR_TREND] = s->e5 - s->e45;
  /* M1.2: clamp RH to the v1.2 training range inside the linear correction only (env/physics paths keep true RH).
   * Reason: the v1.2 fit saw RH 38-60 %; below that its -0.012 C/% term invents a resting DRINK. */
  float rh_lin = rh;
  if (s->rh_clamp) rh_lin = rh < HG_KF_RH_MIN ? HG_KF_RH_MIN : (rh > HG_KF_RH_MAX ? HG_KF_RH_MAX : rh);
  x[HG_F_AMB] = amb_c; x[HG_F_RH] = rh_lin; x[HG_F_AGE] = age_c; x[HG_F_SEX_M] = s->sex_m; x[HG_F_BMI] = s->bmi;
  x[HG_F_KF] = s->ct; x[HG_F_KF_D15] = s->ct - kf15;
  float est = s->ct + HG_NOW_INTERCEPT, f20 = s->ct + HG_F20_INTERCEPT;
  for (int i = 0; i < HG_N_FEAT; i++) { est += HG_NOW_COEF[i] * x[i]; f20 += HG_F20_COEF[i] * x[i]; }
  float sh = s->age >= 65.0f ? HG_OLDER_DANGER_SHIFT : 0.0f;   /* PROVISIONAL (0) as v1.2 */
  float es = est + sh, fs = f20 + sh;
  if (!s->started_e) { for (int i = 0; i < 11; i++) s->estring[i] = es; s->started_e = 1; }
  s->estring[s->ei] = es;
  float est10 = s->estring[(s->ei + 1) % 11];
  s->ei = (uint8_t)((s->ei + 1) % 11);
  s->w60 = ((s->w60 << 1) | (fs >= HG_T_DRINK_WATER ? 1u : 0u)) & ((1ULL << 60) - 1ULL);
  float warn60 = (float)popcount64(s->w60) / 60.0f;
  float d[HG_N_DGF];
  d[HG_DGF_EST] = es; d[HG_DGF_RISE20] = fs - es; d[HG_DGF_EST_D10] = es - est10; d[HG_DGF_WARN60] = warn60;
  d[HG_DGF_HR_ABOVE_REST] = x[HG_F_HR_ABOVE_REST]; d[HG_DGF_HR_RESERVE_FRAC] = x[HG_F_HR_RESERVE_FRAC]; d[HG_DGF_AMB] = amb_c;
  float z = HG_DG_B;
  for (int i = 0; i < HG_N_DGF; i++) z += HG_DG_W[i] * d[i];
  float sd = 1.2533141f * (HG_SD_C[0] + HG_SD_C[1] * est + HG_SD_C[2] * x[HG_F_HR_RESERVE_FRAC] + HG_SD_C[3] * warn60);
  o->est = est; o->f20 = f20; o->z = z; o->sd = sd < 0.08f ? 0.08f : sd; o->kf = s->ct;
  o->hr_reserve = x[HG_F_HR_RESERVE_FRAC]; o->warn60 = warn60;
}

/* ---------------- v1.2 tiers, line for line (comparison harness only) ---------------- */
void hg_v12_tiers_init(hg_v12_tiers_t *t, float age, uint8_t f) {
  float m = age >= HG_OLDER_AGE ? HG_OLDER_WATCH_MARGIN : 0.0f;
  t->m_drink = m; t->m_cool = m;
  if (f & (HG_MED_DIURETIC | HG_MED_ACE_ARB)) t->m_drink += HG_DIURETIC_DRINK_MARGIN;
  if (f & HG_MED_LOW_SWEAT) { t->m_drink += HG_LOW_SWEAT_WATCH_MARGIN; t->m_cool += HG_LOW_SWEAT_WATCH_MARGIN; }
  if (f & HG_MED_BETA_BLOCKER) { t->m_drink += HG_BB_WATCH_MARGIN; t->m_cool += HG_BB_WATCH_MARGIN; }
  int older_env = (age >= HG_OLDER_AGE) || (f != 0);
  t->lim_a = older_env ? HG_LIM_OLD_A : HG_LIM_YOUNG_A; t->lim_b = older_env ? HG_LIM_OLD_B : HG_LIM_YOUNG_B;
  t->run_w1 = t->run_w2 = t->run_dg = 0; t->on_w1 = t->on_w2 = t->on_dg = 0; t->off_w1 = t->off_w2 = t->off_dg = 0;
  t->env_run = t->env_dose = 0; t->still_run = t->cool_min = 0; t->cool_ack = 0;
}
static int tier16(int cond, int16_t *run, int16_t *on, int16_t *off, int k) {
  *run = cond ? (int16_t)(*run + 1) : 0;
  if (*run >= k) { *on = 1; *off = 0; }
  else if (*on) { if (cond) *off = 0; else if (++*off >= HG_HOLD_MIN) *on = 0; }
  return *on;
}
int hg_kf_v12_step(hg_v12_tiers_t *t, const hg_kf_out_t *o, float amb_c, float rh, int still, int button, int *why) {
  int above = hg_pa_kpa(amb_c, rh) >= t->lim_a + t->lim_b * amb_c;
  t->env_run = above ? (int16_t)(t->env_run + 1) : 0;
  if (above) { if (t->env_dose < HG_ENV_DOSE_CAP) t->env_dose++; } else if (t->env_dose > 0) t->env_dose--;
  int env1 = (t->env_run >= HG_ENV_DRINK_RUN_MIN) || (t->env_dose >= HG_ENV_DRINK_RUN_MIN);
  int env2 = t->env_dose >= HG_ENV_COOL_DOSE_MIN;
  int c1 = o->f20 >= HG_T_DRINK_WATER - t->m_drink, c2 = o->f20 >= HG_T_GO_COOL - t->m_cool;
  int w1 = tier16(c1 || env1, &t->run_w1, &t->on_w1, &t->off_w1, HG_DEBOUNCE_MIN);
  int w2 = tier16(c2 || env2, &t->run_w2, &t->on_w2, &t->off_w2, HG_DEBOUNCE_MIN);
  t->still_run = still ? (int16_t)(t->still_run + 1) : 0;
  if (w2) { t->cool_min++; if (button) t->cool_ack = 1; } else { t->cool_min = 0; t->cool_ack = 0; }
  int beh = w2 && t->cool_min >= HG_BEH_COOL_MIN && t->still_run >= HG_STILL_MIN && !t->cool_ack;
  int dg = tier16((o->z >= HG_DG_LOGIT_CUT) || beh, &t->run_dg, &t->on_dg, &t->off_dg, HG_DANGER_HOLD_MIN);
  if (why) *why = (above ? HG_WHY_ENV_LIMIT : 0) | (env2 ? HG_WHY_TIME_IN_HEAT : 0) | (beh ? HG_WHY_NO_RESPONSE : 0)
                  | (o->z >= HG_DG_LOGIT_CUT ? HG_WHY_DANGER_P : 0) | (c1 ? HG_WHY_BODY : 0);
  if (dg) return 3;
  if (w2) return 2;
  if (w1) return 1;
  return 0;
}
