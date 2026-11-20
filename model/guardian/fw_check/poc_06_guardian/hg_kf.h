/* Heat Guardian - v1.2 HR anchor, ported line for line from /home/claude/hgmodel/heat_guardian_band.c:
 * ECTemp Kalman (Buller 2013) + EWMs + 14-feature linear now/f20 (display fallback when the NN is invalid)
 * + 7-feature logistic Danger z (REPORT s5b) + the 90 % range model. expf replaced: EWM factors are hg_tables.h
 * constants, the sigmoid is not computed (z is compared with HG_DG_LOGIT_CUT), Magnus is the 26-entry table.
 * hg_kf_v12_step() additionally ports v1.2's own tier logic (only used to prove the port == heat_guardian_band.c). */
#ifndef HG_KF_H
#define HG_KF_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct {
  float age, sex_m, bmi, rest_hr, hrmax;
  uint8_t flags, started_k, started_e, ki, ei, nhr, rh_clamp, _pad;   /* rh_clamp: M1.2 (1 on the band, 0 = exact v1.2) */
  float ct, v, e5, e15, e45, last_hr;
  float hrbuf[3], kfring[16], estring[11];
  uint64_t w60;
} hg_kf_t;

typedef struct {
  float est, f20;        /* v1.2 nowcast and 20-min forecast (degC), no twin offset */
  float z;               /* Danger logistic z (P = sigmoid(z)); compare with HG_DG_LOGIT_CUT_V12 */
  float sd;              /* v1.2 range-model sd (degC), floor 0.08 */
  float kf;              /* raw Kalman state ct */
  float hr_reserve;      /* (e5 - rest)/(hrmax - rest) */
  float warn60;
} hg_kf_out_t;

void hg_kf_init(hg_kf_t *s, float age, int male, float bmi, float rest_hr, uint8_t med_flags);
void hg_kf_set_rest_hr(hg_kf_t *s, float rest_hr);
/* hr_bpm: 1-min HR, NAN (or outside 30..220) = hold last good, exactly as v1.2. amb_c, rh: room air. */
void hg_kf_step(hg_kf_t *s, float hr_bpm, float amb_c, float rh, hg_kf_out_t *o);

/* v1.2 tier port (comparison only) */
typedef struct {
  float m_drink, m_cool, lim_a, lim_b;
  int16_t run_w1, run_w2, run_dg, on_w1, on_w2, on_dg, off_w1, off_w2, off_dg;
  int16_t env_run, env_dose, still_run, cool_min;
  uint8_t cool_ack, _pad;
} hg_v12_tiers_t;
void hg_v12_tiers_init(hg_v12_tiers_t *t, float age, uint8_t med_flags);
int  hg_kf_v12_step(hg_v12_tiers_t *t, const hg_kf_out_t *o, float amb_c, float rh, int still, int button, int *why);
#ifdef __cplusplus
}
#endif
#endif
