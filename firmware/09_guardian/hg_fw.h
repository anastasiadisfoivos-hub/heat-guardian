/* Heat Guardian 09_guardian: the firmware glue between the 1 Hz sensing layer (from 08_logger) and the FROZEN
 * Guardian Loop / Body Twin (fw/09_guardian/frozen = git tag hg2-freeze-6, never edited).
 * Plain C99, no malloc, no hardware: host-tested in fw/tools/test_fw.c with the same frozen sources.
 *
 *  per second : hg_fw_second()   -> 1-min summaries + the twelve 5-s samples hg_guardian_step() wants
 *  per minute : hg_fw_minute()   -> hg_minute_t, hg_guardian_step(), Body Twin ingest, nightly update decision,
 *                                    STATUS frame into the 24 h RAM ring, the two 24-B log records
 *  PPG duty   : hg_fw_ppg_on()   -> first 30 s of every minute, continuous while a tier / CHECK / HELP is on
 *
 * Deviation from the brief (R4 A6 "30 s every 2 min"): the frozen hg2 sets hr_valid = HR OK in >= 3 of the last 5
 * minutes and the v1.2 logistic Danger path switches off after 5 invalid minutes (A7.2 "HR gating"). A 2-minute duty
 * cycle would leave at most 2-3 HR minutes in 5 and silently turn the HR paths off, which is not what the sealed exam
 * evaluated. 30 s of every minute keeps one HR estimate per minute (hg_ppg needs ~10 s to settle) at ~half the LED power.
 */
#ifndef HG_FW_H
#define HG_FW_H
#include <stdint.h>
#ifndef HG_TWIN_USE_HG2_STEP_H
#define HG_TWIN_USE_HG2_STEP_H 1
#endif
#include "frozen/hg_guardian.h"
#include "frozen/hg_guardian_twin.h"
#include "frozen/hg_twin.h"
#ifdef __cplusplus
extern "C" {
#endif

#define HG_FW_RING_MIN     1440      /* 24 h of STATUS frames (20 B) = 28,800 B (ARCH 7.3) */
#define HG_FW_PPG_ON_S     30        /* PPG on for the first 30 s of each minute */
#define HG_FW_NIGHT_FROM   180       /* nightly Body Twin update: first 30 still minutes after 03:00 ... */
#define HG_FW_NIGHT_LATEST 300       /* ... or at 05:00 at the latest (minute of day, local) */
#define HG_FW_NIGHT_STILL  30
#define HG_FW_STILL_G      0.002f    /* still: a_std <= 0.002 g (A7.2 "Still / active") */
#define HG_FW_MAX_SAVES_DAY 5        /* twin file saves per day (R4 A3 wear rule) */
#define HG_FW_TWIN_BUF     900

typedef struct {              /* one second from the sensing layer; NAN / 0 when not available */
  float t1_c, t2_c, tair_c, rh_pct;     /* latest TMP117/SHTC3 values (they update every 5 / 10 s) */
  float hr_bpm; uint8_t hr_q; uint8_t ppg_on;   /* hg_ppg output; ppg_on = 0 while the PPG is duty-cycled off */
  float pi_pct; uint32_t ppg_dc;
  float a_mean, a_m2; uint16_t a_n;     /* this second's |a| samples (g): mean, sum of squared deviations, count (25 Hz) */
  float a_peak_g, zangle_deg;           /* max |a| this second; z-angle (5-s median) */
} hg_fw_sec_t;

typedef struct {
  /* minute accumulator */
  float s_t1, s_t2, s_ta, s_rh, s_pi; uint8_t n_t1, n_t2, n_ta, n_rh, n_pi;
  float a_mean, a_m2; uint32_t a_n;     /* Chan's parallel merge of the seconds: exact in float (|a| ~ 1 g, std ~ 1e-3 g) */
  float s_astd; uint8_t n_astd;         /* sum / count of the 1-s stds (the log's per-second-average a_std) */
  float a_peak; uint8_t hr[60]; uint8_t n_hr; uint8_t q_cnt[5]; uint32_t dc[60]; uint8_t n_dc;
  float t1_5s[12], t2_5s[12], ta_5s[12], z_5s[12];
  uint8_t secs, button;
  /* minute-level state */
  uint8_t flat_still;                   /* minutes flat (|z| >= 75 deg) and still */
  uint16_t still_run;                   /* consecutive still minutes (nightly trigger) */
  int32_t night_done_day;               /* local day index of the last nightly update, -1 none */
  uint16_t saves_today; int32_t saves_day;
  uint32_t minutes, nightly_runs;
  /* outputs kept for the firmware */
  hg_minute_t last_in;
  hg_minute_out_t last_out;
  uint8_t ring[HG_FW_RING_MIN][20]; uint16_t ring_head, ring_n;
} hg_fw_t;

typedef struct {                        /* what the sketch passes in once a minute besides the seconds */
  uint16_t minute_of_day;               /* local, 0xFFFF unknown */
  int32_t  local_day;                   /* days since 1970 in local time, -1 unknown */
  uint8_t  charging; float vbat; int8_t ble_bucket;
  const uint8_t *forecast72; uint8_t has_forecast;
} hg_fw_ctx_t;

typedef struct {                        /* what the sketch must do after a minute */
  uint8_t save_twin;                    /* 1: pack + write /twin.bin now (nightly) */
  uint8_t nightly;                      /* 1: a nightly Body Twin update ran this minute */
  uint8_t status_changed;               /* STATUS state/flags byte changed: notify now */
  uint8_t rec_in[24], rec_g[24];        /* log records (fw/08_logger/log_format.h layout; rec_g = marker 13) */
} hg_fw_act_t;

void hg_fw_init(hg_fw_t *f);
void hg_fw_second(hg_fw_t *f, const hg_fw_sec_t *s);
void hg_fw_button(hg_fw_t *f, uint8_t kind);          /* 1 short, 2 long (HELP); latched into the next minute */
void hg_fw_minute(hg_fw_t *f, hg_guardian_t *g, hg2_twin_t *tw, hg_twin_acc_t *acc, const hg_fw_ctx_t *ctx,
                  uint32_t t_ms_minute_start, hg_fw_act_t *act);
void hg_fw_discard_minute(hg_fw_t *f);
/* model refused (CRC): the minute's input record only (the guardian does not run), then drop the samples */
void hg_fw_minute_inputs(hg_fw_t *f, const hg_fw_ctx_t *ctx, uint32_t t_ms, uint8_t rec[24]);
/* new wearer profile (console `profile`): profile constants only, no re-init: alarms / CHECK / HELP / learning kept */
void hg_fw_apply_profile(hg_guardian_t *g, const hg2_profile_t *p);              /* model refused (CRC): drop the minute's samples */
int  hg_fw_ppg_on(const hg_fw_t *f, uint8_t sec_in_minute);
/* pack the twin file (guardian calm baseline + routine into it); returns bytes or < 0 */
int  hg_fw_twin_pack(const hg_guardian_t *g, const hg2_twin_t *tw, hg_twin_acc_t *acc, uint32_t save_count, uint8_t *buf, uint16_t cap);
/* restore at boot: unpack -> guardian init with the twin -> calm baseline + routine. Returns 0 ok, < 0 defaults used */
int  hg_fw_twin_load(hg_guardian_t *g, const hg2_profile_t *p, hg2_twin_t *tw, hg_twin_acc_t *acc, const uint8_t *buf, uint16_t len, uint32_t *save_count);
/* the last n STATUS frames, oldest first; returns how many were copied */
uint16_t hg_fw_ring_get(const hg_fw_t *f, uint16_t n, uint8_t (*out)[20]);
uint8_t  hg_fw_asleep(const hg_guardian_t *g, uint16_t mod);
/* 24-B guardian log record (marker 13), CRC-8 like log_format.h */
void hg_fw_pack_grec(uint32_t t_ms, const hg_minute_out_t *o, uint8_t flags, uint8_t b[24]);

#ifdef __cplusplus
}
#endif
#endif
