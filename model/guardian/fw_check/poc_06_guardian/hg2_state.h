/* hg2 state layout. Included only by hg2_step.c and by hg_guardian.h (which embeds the state by value: no malloc).
 * No pointers. sizeof must stay <= 512 B (B5 brief; checked in host_test). */
#ifndef HG2_STATE_H
#define HG2_STATE_H
#include "hg2_step.h"
#include "hg_kf.h"
struct hg2_state {
  hg_kf_t kf;                         /* v1.2 anchor (Kalman, EWMs, rings, logistic) */
  float age, sex_m, bmi, hrmax;
  float rest_hr, k_person, core_offset, c_bodyheat;
  int16_t t1nb[24];                   /* twin night baseline x100, INT16_MIN = unknown */
  float hr_last, hr_e5, hr_e45, act_e30;
  float t1_last, t2_last, tair_last, rh_last;
  float ring_t1[16], ring_tair[16], ring_dt[11];
  uint32_t act_hist;                  /* bit i = ACTIVE i minutes ago (30 used) */
  uint16_t min_since_active, min_since_don;
  int16_t env_run, env_dose;
  uint8_t med_flags, older_env, hr_age, hr_q_hist;
  uint8_t ri16, ri11, started, last_worn;
};
#endif
