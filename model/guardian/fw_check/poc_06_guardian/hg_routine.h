/* Heat Guardian - routine learning and anomaly rules (ARCHITECTURE 7.1 step 4; R3 s3.2 HDCZA, s3.4, s3.5).
 * Deviations from the ARCH text, both forced by the sources (see REPORT_GUARDIAN.md):
 *  - 5-min medians of |d z-angle| are stored in 0.01 deg units (u8, saturating at 2.55 deg), not 0.5 deg: the HDCZA
 *    threshold is clamped to 0.13..0.50 deg (GGIR), unrepresentable on a 0.5 deg grid.
 *  - the quiet run q used by rule (a) counts AWAKE quiet minutes only (reset inside the sleep window): R3 s3.4 says
 *    B "is widened to cover the whole sleep window"; the no-wake case is rule (b)'s job. */
#ifndef HG_ROUTINE_H
#define HG_ROUTINE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct { float n, mean, m2; } hg_welford_t;
typedef struct {
  hg_welford_t am[24], q[24];        /* 576 B: active minutes per hour, longest awake quiet run seen in each hour */
  int16_t maxq[24];                  /* 48 B */
  uint8_t med5[288];                 /* 288 B: 5-min median |d z-angle|, 0.01 deg, last 24 h by block-of-day */
  uint8_t med5_ok[36];               /* bit per block: block fully worn */
  uint8_t dz[60];                    /* current block's 5-s |d angle| values */
  float last_z;
  uint16_t wake_hist[7];
  uint16_t sleep_on, sleep_off;      /* minute of day, sleep window [on, off) */
  uint16_t qrun, q_hour_max, last_mod, act10;
  uint8_t sleep_valid, n_wake, wake_i, days_learned;
  uint8_t dzn, block_ok, cur_hour, _p0;
  uint16_t block_idx, _p1;
  uint8_t act_in_hour, hour_minutes, hour_clean, last_hour_done;
  uint8_t last_hour_act, awake_today, impact_pending, score;
  uint8_t last_req, hdcza_thr, prev_asleep, imp_still;   /* imp_still: M19-impact still minutes after the impact */
  uint16_t night_worn, _pad2;        /* T5 D5: worn minutes inside the current sleep window (RAM only, never packed: a boot starts at 0) */
} hg_routine_t;

typedef struct {
  uint16_t minute_of_day;            /* 0xFFFF unknown -> routine disabled (A7.2 time-unknown rule) */
  float a_std_g;
  const float *zangle_5s;            /* 12 values (deg) or NULL */
  uint8_t worn;                      /* 2 = worn; anything else freezes learning and disables the rules */
  uint8_t frozen;                    /* any tier >= DRINK on -> learning frozen (A7.1 step 4) */
  uint8_t heat_day;                  /* forecast flag bit 0 for today */
  float t_in;                        /* corrected air (C) for heat coupling */
  uint8_t cool_on;
  uint8_t impact;                    /* |a| peak >= HG_IMPACT_G in this minute (1 Hz layer) */
  uint8_t button;                    /* M19-impact: any press this minute cancels a pending impact CHECK */
} hg_routine_in_t;

#define HG_RT_REQ_QUIET  1
#define HG_RT_REQ_NOWAKE 2
#define HG_RT_REQ_IMPACT 4
typedef struct {
  uint8_t req;                       /* HG_RT_REQ_* bits: CHECK requests (level-true while the condition holds) */
  uint8_t routine_score;             /* 0..255, 255 = fully on routine */
  uint8_t asleep;
  uint16_t q;                        /* awake quiet run (min) */
  uint16_t thr;                      /* rule (a) threshold in force this minute (min), 0 if none */
  uint16_t wake_deadline;            /* rule (b) deadline (minute of day) */
} hg_routine_out_t;

void hg_routine_init(hg_routine_t *r);
void hg_routine_step(hg_routine_t *r, const hg_routine_in_t *in, hg_routine_out_t *out);
void hg_routine_noon(hg_routine_t *r);           /* HDCZA recompute (called automatically when 12:00 is crossed) */
/* ---- persisted routine profile: STABLE FORMAT v1, exactly HG_ROUTINE_PACK_BYTES = 650 B (B3 twin file needs <= 699 B;
 * B4's tomorrow/routine.py reads it). Little-endian, float = IEEE-754 binary32, no padding:
 *   off   0  u8   'R' (0x52)
 *   off   1  u8   'T' (0x54)
 *   off   2  u8   version = 1
 *   off   3  24 x {f32 n, f32 mean, f32 m2}  am[h]  active minutes per clock hour h = 0..23 (Welford; n capped 30)
 *   off 291  24 x {f32 n, f32 mean, f32 m2}  q[h]   longest AWAKE quiet run (min) seen in hour h (Welford)
 *   off 579  24 x i16  maxq[h]  max of q samples (min), 0..1440
 *   off 627  7 x u16   wake_hist  last HDCZA wake times (minute of day, ring, n_wake valid entries)
 *   off 641  u16  sleep_on    (minute of day)   off 643  u16 sleep_off (minute of day), window [on, off) wraps midnight
 *   off 645  u8   sleep_valid (0 = default 22:00-08:00, 1 = from HDCZA)
 *   off 646  u8   n_wake (0..7)   off 647 u8 wake_i (next ring slot)   off 648 u8 days_learned
 *   off 649  u8   XOR of bytes 0..648
 * SD of a slot = sqrt(m2 / (n - 1)) for n >= 2. A slot counts as learned when n >= 3 (HG_RT_LEARN_DAYS).
 * Any change to this layout must bump the version byte. */
#define HG_ROUTINE_PACK_BYTES 650
uint16_t hg_routine_pack(const hg_routine_t *r, uint8_t *buf, uint16_t cap);    /* -> bytes written, 0 if cap too small */
int hg_routine_unpack(hg_routine_t *r, const uint8_t *buf, uint16_t len);       /* 1 ok, 0 bad (r reset to defaults) */
#ifdef __cplusplus
}
#endif
#endif
