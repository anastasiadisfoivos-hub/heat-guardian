/* Heat Guardian - Guardian Loop: once per minute on the band (ARCHITECTURE 7.1 pipeline, 7.2 state machine).
 * Contact -> home/out -> routine -> Core Sense (hg2) -> tiers OK/DRINK/COOL/CHECK/DANGER (+ IMOK, NOT_WORN, BATTERY,
 * HELP) -> screen, haptics, STATUS frame. All thresholds: hg_guardian_cfg.h (each with its source).
 * Python mirror: guardian/py/hg_guardian_py.py (per-minute state must be identical). C99, no malloc, no expf. */
#ifndef HG_GUARDIAN_H
#define HG_GUARDIAN_H
#include <stdint.h>
#include "hg2_step.h"
#include "hg2_state.h"
#include "hg_contact.h"
#include "hg_homeout.h"
#include "hg_routine.h"
#include "hg_frames.h"
#define HG_PD_RING_N 11   /* = HG_PD_SLOPE_MIN + 1 (checked in hg_guardian.c) */
#define HG_X_W_N_DECL 30  /* = HG_X_W_N (checked in hg_guardian.c) */
#define HG_A_HIST_N_DECL 100   /* = HG_A_HIST_N (hg_guardian_cfg.h) */
#ifdef __cplusplus
extern "C" {
#endif
enum { HG_ST_OK = 0, HG_ST_DRINK, HG_ST_COOL, HG_ST_CHECK, HG_ST_DANGER, HG_ST_IMOK, HG_ST_NOT_WORN, HG_ST_BATTERY, HG_ST_HELP };
/* check_reason bits */
#define HG_CR_DANGER         1
#define HG_CR_BEHAVIOUR      2
#define HG_CR_ROUTINE_QUIET  4
#define HG_CR_ROUTINE_NOWAKE 8
#define HG_CR_IMPACT         16
/* extra why bits on top of HG2_WHY_* */
#define HG_WHY_NO_RESPONSE_G 4
#define HG_WHY_WHO           128
enum { HG_SCR_OK = 0, HG_SCR_DRINK, HG_SCR_COOL, HG_SCR_DANGER, HG_SCR_CHECK, HG_SCR_FAMILY, HG_SCR_IMOK, HG_SCR_NOT_WORN,
       HG_SCR_LOOSE, HG_SCR_BATTERY, HG_SCR_HELP, HG_SCR_NUDGE, HG_SCR_N };   /* NUDGE: M1.1 bedtime «Δροσίστε το δωμάτιο» */

typedef struct {
  hg2_in_t s;                        /* s.worn is ignored: it is computed here by hg_contact */
  float t1_5s[12], t2_5s[12], tair_5s[12];   /* the last minute's 5-s samples (NAN if absent) */
  float zangle_5s[12];               /* z-angle 5-s medians (deg), for HDCZA */
  float a_peak_g;                    /* max |a| in the minute (g), for the impact rule */
  uint32_t ppg_dc;                   /* hg_ppg DC level, 0 = no PPG this minute */
  uint8_t flat_still_min;            /* minutes of flat orientation + no motion (IMU layer) */
  uint8_t button;                    /* 0 none, 1 short press, 2 long press >= 2 s (HELP) */
  uint8_t charging;
  float vbat;                        /* V */
  int8_t ble_bucket;                 /* 2 strong (> -75 dBm), 1 weak, 0 lost, -1 no phone */
  const uint8_t *forecast72;         /* 24 x (i8 T_in, u8 RH, u8 flags) from 0x11, or NULL */
  uint8_t has_forecast;
  uint8_t force_worn;                /* 0xFF = use hg_contact (always on the band); replay/test hook for data without T1 */
} hg_minute_t;

typedef struct {
  uint8_t state;                     /* HG_ST_* */
  uint8_t level;                     /* thermal ladder actually displayed: 0 OK 1 DRINK 2 COOL 3 DANGER */
  uint8_t family_alert;              /* 1 = family alert pending (phone relays), until 0x12 ack */
  uint32_t alarm_id;
  uint8_t check_reason;              /* HG_CR_* of the active CHECK (0 if none) */
  uint8_t check_min;                 /* minutes since the CHECK started, 0xFF if none */
  uint8_t haptic, screen;
  hg2_out_t core;
  uint8_t routine_score, home_out, worn, why;
  uint8_t notify_not_worn, tiers;    /* tiers: bit0 drink on, bit1 cool on, bit2 danger on */
  uint8_t routine_req, imok_resp_min;
  uint8_t night_heat, nudge;         /* M1.1: WHO night flag (icon, Tomorrow Engine) and the once-per-evening nudge minute */
  uint8_t status[20];
} hg_minute_out_t;

typedef struct { uint8_t run, on, off; } hg_tier_t;

typedef struct {
  struct hg2_state hg2;
  hg_contact_t ct;
  hg_homeout_t ho;
  hg_routine_t rt;
  hg2_profile_t prof;
  hg2_twin_t twin;
  float m_drink, m_cool;
  float ta_ring[16];                 /* corrected air, 15-min AC-evidence check */
  uint64_t who_hist;
  uint32_t alarm_seq, alarm_id, help_id;
  hg_tier_t drink, cool, danger;
  uint16_t strain_run, still_run, cool_min, hr_bad_run, ac_latch, notworn_min, snooze, minute_counter;
  uint8_t walk_run, cool_ack, level, check_active, check_cause, check_t, family_sent, family_pending;
  uint8_t help, last_state, tai, started, beh_now, last_cause, nudge_done, _pad_m1;
  hg_tier_t cool_p;
  uint16_t last_mod; uint8_t reading_today, _pad_m5;
  uint16_t a_hist[HG_A_HIST_N_DECL]; uint16_t a_n; float a_base; uint8_t a_base_n, b_prev_drink;   /* M7 A */
  uint16_t pd_cool_run; uint8_t pd_i, pd_n; float pd_ring[HG_PD_RING_N];                   /* M13 persistence */
  float pdv_ring[HG_PD_RING_N];      /* T5 D2: protected (v1.2) f20 ring, same index/count as pd_ring */
  float mb_e10, mb_e60, mb_a30, mb_a120, mb_d;   /* M19 Marble Danger: 5 states (20 B) */
  uint16_t mb_age; uint8_t mb_warm, mb_run;     /* minutes since boot (sat.), minutes since warm air (sat. 255), s >= CUT run */
  uint8_t mb_started, x_i, x_prev, drink_shown;    /* M19 Exception DRINK: ring index, settled-rule state */
  uint8_t x_ring[HG_X_W_N_DECL]; uint16_t x_wq, x_since;   /* W30 ring (0.0012-g steps) + integer running sum */
  float x_c, x_sxx, x_sxy, x_dww, x_dwd, x_dw, x_dref, x_last;   /* her movement slope, decayed sums, today's sums, settled f20 */
  uint16_t dg_sus_run; uint8_t dg_ls_run;      /* B5-v8b: sustained-38.0 run, anticholinergic drug-line run (3 B) */
  float sf_t1, sf_ta; uint8_t sf_run, x_warm;   /* B5-v7: skin-floor Danger EWMAs + run, DRINK heat-context counter (10 B) */
  float skb_sum, skb_base; uint16_t skb_n; uint8_t skb_days, _pad_b9;   /* B9-REALWRIST: wearer's settled-skin baseline (12 B) */
  uint16_t b_since; uint8_t b_left, _pad_m7; float b_last_f20;                                    /* M7 B */  /* M5.2: same-day thermometer reading received (set by 0x13 field 0) */                  /* M3.1: shadow v1.2 Go-cool tier (v1.2 f20 + heat dose only) that arms the behaviour path */
  hg2_aux_t *hg2_dbg;                /* debug/test hook: if non-NULL the minute's hg2 aux is copied here (NULL on the band) */
  /* M3.1 property test only (NULL on the band): rewrites the NN-derived outputs - hg2_out_t AND the aux values the tiers
   * actually read (aux->core20_noff; T5 D3: the old hook only reached hg2_out_t, so the f20 path was never perturbed) */
  void (*nn_test_hook)(hg2_out_t *core, hg2_aux_t *aux, void *ctx);
  void *nn_test_ctx;
} hg_guardian_t;

void hg_guardian_init(hg_guardian_t *g, const hg2_profile_t *p, const hg2_twin_t *tw);
void hg_guardian_set_twin(hg_guardian_t *g, const hg2_twin_t *tw);      /* nightly, from hg_twin */
void hg_guardian_step(hg_guardian_t *g, const hg_minute_t *in, hg_minute_out_t *out);
/* phone commands already parsed by hg_cmd_parse(): FAMILY_ACK and PROFILE are applied here (TIME/FORECAST/SAFE_HOURS
 * belong to the firmware clock and buffers). Returns 1 if the command changed guardian state. */
int hg_guardian_cmd(hg_guardian_t *g, const hg_cmd_t *c);
/* M9.5: design A's calm-f20 baseline is persisted by the Body Twin (B3), not guardian RAM. Twin-file field (5 B packed):
 *   f32 calm_f20_c  (degC, bounded 36.8..37.7, meaningless while n == 0)   u8 calm_f20_n (days learned, 0 = not learned)
 * B3 calls hg_guardian_get_calm() at the nightly save and hg_guardian_set_calm() after loading the file (before the first
 * minute). set_calm rejects NaN / out-of-bounds values (returns 0 and leaves the baseline unlearned). */
typedef struct { float calm_f20_c; uint8_t calm_f20_n; } hg_calm_t;
void hg_guardian_get_calm(const hg_guardian_t *g, hg_calm_t *out);
int  hg_guardian_set_calm(hg_guardian_t *g, const hg_calm_t *in);
/* M19 Exception DRINK: her movement-response sums, to be saved with the Twin (8 B: f32 sxx, f32 sxy; B3 to add to the file).
 * set_exc rejects NaN/inf, sxx < 0 (returns 0 and clears them); the slope c is recomputed from the sums. */
typedef struct { float sxx, sxy; } hg_exc_t;
void hg_guardian_get_exc(const hg_guardian_t *g, hg_exc_t *out);
int  hg_guardian_set_exc(hg_guardian_t *g, const hg_exc_t *in);
const char *hg_screen_text(uint8_t screen);                              /* Greek, UTF-8 */
#ifdef __cplusplus
}
#endif
#endif
