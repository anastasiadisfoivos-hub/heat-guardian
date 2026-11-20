/* Heat Guardian R4 PoC 05: streaming wrist HR from the MAX30102 IR channel.
 *
 * Replaces SparkFun heartRate.cpp (Maxim PBA: DC estimator + 23-tap FIR + zero
 * crossing, no refractory, no interval validation, no quality gate).
 *
 * Pipeline, one call per IR sample at HG_PPG_FS Hz (50 or 100):
 *   1. DC tracker (1-pole, tau ~1.5 s) -> perfusion index PI = AC_pp / DC
 *   2. 2nd-order Butterworth band-pass 0.5-4 Hz (two biquads, Direct Form II)
 *   3. slope-sign peak detector with an adaptive threshold (0.5 x envelope),
 *      refractory 300 ms (max 200 bpm)
 *   4. inter-beat-interval (IBI) validation: 300-2000 ms and within +/-30 % of
 *      the running median of the last 8 IBIs
 *   5. 10-s window: HR = 60000 / median(valid IBIs in window), needs >= 5 beats
 *   6. quality gate -> HG_PPG_Q_*: no skin (DC too low), PI too low (band loose),
 *      motion (IMU flag, or PI implausible: > 2 % at the wrist or > 3x its 30-s baseline),
 *      irregular (IBI CV > 25 %), or OK
 *
 * Cost (see R4 report): ~60 MAC/sample -> ~0.01 % of the CPU at 100 Hz; RAM ~150 B.
 * No raw-sample buffer: everything is streaming.
 */
#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

#ifndef HG_PPG_FS
#define HG_PPG_FS 100            /* samples per second; 50 or 100 (coefficients cover both) */
#endif
#define HG_PPG_WIN_MS   10000    /* HR window */
#define HG_PPG_MAX_BEATS 40      /* 10 s at 240 bpm */

enum { HG_PPG_Q_NO_SKIN = 0, HG_PPG_Q_LOW_PI = 1, HG_PPG_Q_MOTION = 2, HG_PPG_Q_IRREGULAR = 3, HG_PPG_Q_OK = 4 };

typedef struct {
  /* DC + envelope */
  float dc, env_hi, env_lo;
  /* band-pass biquad states (DF2T), two sections */
  float z1a, z2a, z1b, z2b;
  /* peak detector */
  float prev, prev2;
  uint32_t last_peak_ms;
  /* beats in the window */
  uint32_t beat_ms[HG_PPG_MAX_BEATS];
  uint8_t  n_beats;
  uint16_t ibi_hist[8]; uint8_t ibi_n; uint8_t rejects;
  float    pi_slow;       /* 30-s baseline of PI, for the plausibility gate */
  uint8_t  motion;        /* set by the firmware from the IMU (still-wrist variance), 1 = moving */
  /* outputs */
  float    hr_bpm;        /* 0 if not available */
  float    pi_pct;        /* perfusion index in % */
  float    ibi_cv;        /* coefficient of variation of IBIs in the window */
  uint8_t  quality;       /* HG_PPG_Q_* */
} hg_ppg_t;

void hg_ppg_init(hg_ppg_t *s);
/* Tell the detector what the IMU sees (call whenever the still-wrist flag changes).
 * Periodic arm motion (walking) produces a clean fake "pulse" at the cadence that
 * no PPG-only test can reject with certainty; the IMU is the authority. */
static inline void hg_ppg_set_motion(hg_ppg_t *s, int moving) { s->motion = (uint8_t)moving; }
/* Feed one IR sample (raw 18-bit ADC count) with its time in ms. Returns 1 on a beat. */
int  hg_ppg_push(hg_ppg_t *s, uint32_t ir, uint32_t now_ms);

#ifdef __cplusplus
}
#endif
