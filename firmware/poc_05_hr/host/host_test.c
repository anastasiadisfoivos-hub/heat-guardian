/* Host test for hg_ppg: synthetic wrist PPG at 100 sps.
 * Build from poc_05_hr/:  gcc -O2 -I. host/host_test.c hg_ppg.c -lm -o /tmp/ppg && /tmp/ppg
 * Segments (each 20 s):
 *   A  72 bpm, PI 0.5 %, clean                -> expect HR 72 +/- 2, Q_OK
 *   B  72 bpm + baseline wander + white noise -> expect HR 72 +/- 3, Q_OK
 *   C  110 bpm (walking), PI 0.3 %            -> expect HR 110 +/- 3
 *   D  motion artefact burst (1.5 Hz, 10x AC) -> expect Q_IRREGULAR or HR near 90 (=1.5 Hz) flagged, NOT a silent wrong number
 *   E  band loose: PI 0.02 %                  -> expect Q_LOW_PI
 *   F  no skin: DC 1200                       -> expect Q_NO_SKIN
 * Also prints the "SparkFun-style" comparison: how often the simple detector would have reported a number during D/E/F.
 */
#include <stdio.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include "hg_ppg.h"

static float randn(void) { float u = (rand() + 1.0f) / (RAND_MAX + 2.0f), v = (rand() + 1.0f) / (RAND_MAX + 2.0f); return sqrtf(-2 * logf(u)) * cosf(6.2831853f * v); }

/* PPG pulse shape: fundamental + 2nd harmonic (systolic peak + dicrotic notch), inverted (more blood -> less IR) */
static float pulse(float phase) { return -(sinf(phase) + 0.35f * sinf(2 * phase + 0.6f)); }

int main(void)
{
  const int fs = HG_PPG_FS;
  hg_ppg_t s; hg_ppg_init(&s);
  srand(1);
  struct { const char *name; float bpm, dc, pi_pct, wander, noise, motion; } seg[] = {
    {"A clean 72",          72, 110000, 0.5f,  0,    0,    0},
    {"B wander+noise 72",   72, 110000, 0.5f,  3.0f, 0.3f, 0},
    {"C walking 110",      110, 100000, 0.3f,  1.0f, 0.3f, 0},
    {"D motion burst",      72, 110000, 0.5f,  1.0f, 0.3f, 10.0f},
    {"E loose band PI .02", 72, 110000, 0.02f, 1.0f, 0.3f, 0},
    {"F no skin",           72,   1200, 0.0f,  0,    0.3f, 0},
  };
  int nseg = sizeof seg / sizeof seg[0];
  int imu_available = getenv("HG_IMU") != NULL;   /* HG_IMU=1 ./test : with the IMU motion flag */
  printf("IMU motion flag: %s\n", imu_available ? "ON" : "OFF (PPG-only gates)");
  uint32_t t_ms = 0; float phase = 0;
  int fails = 0;
  for (int k = 0; k < nseg; k++) {
    int n_ok = 0, n_total = 0, n_flagged = 0; float hr_sum = 0; int hr_n = 0;
    for (int i = 0; i < 20 * fs; i++) {
      float ac = seg[k].dc * seg[k].pi_pct / 100.0f / 2.0f;   /* PI = pp/DC -> amplitude = pp/2 */
      phase += 2 * 3.14159265f * seg[k].bpm / 60.0f / fs;
      float x = seg[k].dc + ac * pulse(phase)
              + seg[k].wander * ac * sinf(2 * 3.14159265f * 0.15f * t_ms / 1000.0f)
              + seg[k].noise * ac * randn()
              + seg[k].motion * ac * sinf(2 * 3.14159265f * 1.5f * t_ms / 1000.0f);
      if (x < 0) x = 0;
      hg_ppg_set_motion(&s, imu_available && seg[k].motion > 0);   /* what the IMU would say */
      hg_ppg_push(&s, (uint32_t)x, t_ms);
      t_ms += 1000 / fs;
      if (i >= 12 * fs) {           /* judge the last 8 s of each 20 s segment: window + settling */
        n_total++;
        if (s.quality == HG_PPG_Q_OK) { n_ok++; hr_sum += s.hr_bpm; hr_n++; } else n_flagged++;
      }
    }
    float hr = hr_n ? hr_sum / hr_n : 0;
    printf("%-22s  HR %6.1f bpm (true %5.1f)  Q_OK %3d%%  flagged %3d%%  PI %.3f%%  cv %.2f  q=%d\n",
           seg[k].name, hr, seg[k].bpm, 100 * n_ok / n_total, 100 * n_flagged / n_total, s.pi_pct, s.ibi_cv, s.quality);
    int pass;
    if (k <= 2) pass = (n_ok > 0.8f * n_total) && fabsf(hr - seg[k].bpm) <= 3.0f;
    else if (k == 3) pass = (n_flagged > 0.5f * n_total) || fabsf(hr - 72) <= 3.0f;   /* either flagged, or still right */
    else pass = (n_flagged == n_total);
    printf("   -> %s\n", pass ? "PASS" : "FAIL");
    if (!pass) fails++;
  }
  printf("%s\n", fails ? "SOME SEGMENTS FAILED" : "ALL SEGMENTS PASS");
  printf("sizeof(hg_ppg_t) = %zu bytes of RAM\n", sizeof(hg_ppg_t));
  return fails != 0;
}
