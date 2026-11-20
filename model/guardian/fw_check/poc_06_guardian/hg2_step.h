/* Heat Guardian - Core Sense runtime hg2 (ARCHITECTURE 4.5, verbatim API).
 * C99, float only, no malloc, no expf/logf/powf (sqrtf and fabsf allowed). Host build:
 * -std=c99 -Wall -Wextra -Werror -Wdouble-promotion -fsingle-precision-constant.
 * Feature builder = ARCHITECTURE 4.1 (32 features). Python mirror: guardian/py/hg2_py.py (B2 must match it).
 * While hg2_weights.h has HG2_WEIGHTS_STUB == 1 the network still runs (code path, CRC, timing) but the outputs
 * come from the v1.2 Kalman anchor (hg_kf): core_now/core_20 = v1.2 est/f20 (+ twin offset), core_30 = f20,
 * sd_20 = sd_30 = 0 (single model), sd_now = v1.2 range sd, logits = -100, strain = Moran PSI(est, HR). */
#ifndef HG2_STEP_H
#define HG2_STEP_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define HG2_N_IN  32
#define HG2_N_OUT 6
#define HG2_N_ENS 5

typedef struct {                 /* profile, set once by hg2_init() */
  float age, sex_m, bmi;         /* years, 1/0, kg/m2 */
  uint8_t med_flags;             /* HG_MED_* bits from heat_guardian_model.h */
} hg2_profile_t;

typedef struct {                 /* Body Twin parameters (owned by hg_twin, read here) */
  float rest_hr;                 /* bpm, bounds 40..100, default 70 */
  float k_person;                /* flux constant, bounds 0.03..0.40, default 0.12 */
  float core_offset;             /* degC added to displayed/alarm core, bounds -0.8..+0.8, default 0 */
  float c_bodyheat;              /* SHTC3 contamination coefficient, bounds 0..0.4, default 0.15 */
  float t1_night_base[24];       /* degC per hour-of-day, NAN until learned */
  uint8_t days_learned;
} hg2_twin_t;

typedef struct {                 /* one minute of inputs; NAN = not available */
  float t1_c, t2_c;              /* 1-min means; t2_c = NAN when no REF board */
  float t_air_c, rh_pct;         /* SHTC3 1-min means */
  float hr_bpm;                  /* 1-min median from hg_ppg, NAN if none */
  uint8_t hr_quality;            /* hg_ppg word: 0 no skin, 1 low PI, 2 motion, 3 irregular, 4 OK */
  float pi_pct;                  /* perfusion index, NAN if none */
  float a_std_g;                 /* 1-min std of |a| in g */
  uint8_t worn;                  /* from hg_contact: 0 off, 1 loose, 2 worn */
  uint16_t minute_of_day;        /* 0..1439, 0xFFFF = unknown */
} hg2_in_t;

typedef struct {
  float core_now, core_20, core_30;   /* degC, include twin.core_offset */
  float sd_now, sd_20, sd_30;         /* ensemble std, degC */
  float f20_eff, f30_eff;             /* mean + 1.0*min(sd, 0.30): what the tiers use */
  float logit_p38, logit_p385;        /* ensemble-mean logits; compare with HG2_LOGIT_CUT_* */
  float strain;                       /* 0..10 */
  float kf;                           /* the v1.2 Kalman anchor alone, for display/debug */
  float core_flux;                    /* T1 + K*dT clamped, NAN if !flux_valid */
  uint8_t flux_valid, hr_valid, valid; /* valid = 0 while worn != 2 or minutes_since_don < 5 */
  uint8_t why;                        /* HG_WHY_* bits for the Greek reason line */
} hg2_out_t;

typedef struct hg2_state hg2_state_t;   /* opaque by convention; layout in hg2_state.h (only hg2_step.c touches it) */

void hg2_init(hg2_state_t *s, const hg2_profile_t *p, const hg2_twin_t *tw);
void hg2_set_twin(hg2_state_t *s, const hg2_twin_t *tw);     /* after a nightly update */
void hg2_step(hg2_state_t *s, const hg2_in_t *in, hg2_out_t *out);  /* once per minute */
int  hg2_check_crc(void);                                     /* weights CRC, at boot */
uint16_t hg2_state_size(void);                                /* == sizeof(hg2_state_t) */
float hg2_sigmoid_lut(float z);                               /* display only (hg_util.c) */

/* ---- additions used by the Guardian Loop and the tests (not in ARCH 4.5; they do not change the API above) ---- */
typedef struct {
  float x[HG2_N_IN];             /* raw (un-normalised) feature vector of this minute */
  float nn_mean[HG2_N_OUT], nn_sd[HG2_N_OUT];   /* raw ensemble outputs (normalised space for 0..2) */
  float v12_est, v12_f20, v12_z, v12_sd; /* the v1.2 HR anchor of this minute */
  float core20_noff;             /* M4.3: core_20 WITHOUT twin.core_offset (what the alarm tiers read in default mode) */
  float t_air_corr, pa_kpa, lim_kpa;
  int16_t env_run, env_dose;
  uint8_t env_above, active, still, active30;
  uint8_t env_above_old;         /* M12: air above the PSU older-adult line (ADL/rest by activity), whatever the wearer's age */
} hg2_aux_t;
void hg2_step_aux(hg2_state_t *s, const hg2_in_t *in, hg2_out_t *out, hg2_aux_t *aux);  /* aux may be NULL */
#define HG2_WHY_ENV_LIMIT    1   /* = HG_WHY_ENV_LIMIT (v1.2) */
#define HG2_WHY_TIME_IN_HEAT 2
#define HG2_WHY_DANGER_P     8
#define HG2_WHY_BODY         16
#define HG2_WHY_NN           32  /* an NN logit path is over its cut */
#define HG2_WHY_UNCERTAIN    64  /* sd_20 >= 0.25 */
#ifdef __cplusplus
}
#endif
#endif
