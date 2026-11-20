/* T5: host timing of hg_guardian_step (100,000 minutes, -O2 Makefile flags) */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include "hg_guardian.h"
static hg_guardian_t g;
int main(void) {
  hg2_profile_t p = { 75.0f, 0.0f, 26.0f, 0 }; hg2_twin_t tw; memset(&tw, 0, sizeof tw);
  tw.rest_hr = 70.0f; tw.k_person = 0.12f; tw.c_bodyheat = 0.15f; for (int h = 0; h < 24; h++) tw.t1_night_base[h] = NAN;
  hg_guardian_init(&g, &p, &tw);
  struct timespec a, b; clock_gettime(CLOCK_MONOTONIC, &a); unsigned acc = 0;
  for (int t = 0; t < 100000; t++) {
    hg_minute_t m; memset(&m, 0, sizeof m);
    m.s.minute_of_day = (uint16_t)(t % 1440); m.s.t1_c = 34.5f + 0.001f * (float)(t % 500); m.s.t2_c = 33.5f; m.s.t_air_c = 31.0f; m.s.rh_pct = 50.0f;
    m.s.hr_bpm = 80.0f + (float)(t % 40); m.s.hr_quality = 4; m.s.pi_pct = 0.6f; m.s.a_std_g = (t % 7) ? 0.01f : 0.05f;
    for (int k = 0; k < 12; k++) { m.t1_5s[k] = m.s.t1_c; m.t2_5s[k] = 33.5f; m.tair_5s[k] = 31.0f; m.zangle_5s[k] = (float)(k * 3); }
    m.a_peak_g = 1.0f; m.ppg_dc = 100000; m.vbat = 3.9f; m.ble_bucket = 2; m.force_worn = 0xFF;
    hg_minute_out_t o; hg_guardian_step(&g, &m, &o); acc += o.state;
  }
  clock_gettime(CLOCK_MONOTONIC, &b);
  double us = ((double)(b.tv_sec - a.tv_sec) * 1e9 + (double)(b.tv_nsec - a.tv_nsec)) / 1e3 / 100000.0;
  printf("hg_guardian_step host: %.2f us/call (x50 M4F rough factor = %.3f ms per minute-step) [%u]\n", us, us * 50.0 / 1000.0, acc);
  return 0;
}
