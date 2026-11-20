/* T6b: host timing of the once-a-minute work (hg_fw_minute = hg_guardian_step incl. the hg2 5-member ensemble + twin ingest),
 * the nightly update and the twin pack, plus worst-case variants. Built with the same fz_ wrappers as the sketch. */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <stdlib.h>
#include "hg_fw.h"
static double dts[20000]; static int cmpd(const void*a,const void*b){double x=*(const double*)a,y=*(const double*)b;return x<y?-1:x>y;}
static double now_s(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
static hg_guardian_t g; static hg_fw_t fw; static hg2_twin_t tw; static hg_twin_acc_t acc;
static uint32_t rng = 7u; static float ur(void) { rng = rng * 1664525u + 1013904223u; return (float)((rng >> 8) & 0xFFFFFF) / 16777216.0f; }
static void fill_minute(int hot) {
  for (int sec = 0; sec < 60; sec++) {
    hg_fw_sec_t s; memset(&s, 0, sizeof s);
    s.t1_c = hot ? 36.0f : 33.8f; s.t2_c = hot ? 35.5f : 32.0f; s.tair_c = hot ? 36.0f : 25.0f; s.rh_pct = 45;
    s.ppg_on = 1; s.hr_q = 4; s.hr_bpm = (hot ? 105.0f : 68.0f) + ur(); s.pi_pct = 0.5f; s.ppg_dc = 110000;
    s.a_mean = 1.0f; s.a_m2 = 0.0001f * ur(); s.a_n = 25; s.a_peak_g = 1.02f; s.zangle_deg = 10;
    hg_fw_second(&fw, &s);
  }
}
int main(void) {
  hg2_profile_t p = { 75.0f, 0.0f, 26.0f, 0 };
  hg_twin_defaults(&tw); hg_twin_acc_init(&acc); hg_guardian_init(&g, &p, &tw); hg_fw_init(&fw);
  const int N = 20000; double tmin = 0, tmax = 0, tsum = 0; int states[9] = {0};
  for (int i = 0; i < N; i++) {
    int hot = (i % 1440) > 700 && (i % 1440) < 1000;
    fill_minute(hot);
    hg_fw_ctx_t c = { (uint16_t)(i % 1440), 20000 + i / 1440, 0, 3.9f, 2, NULL, 0 }; hg_fw_act_t a;
    double t0 = now_s(); hg_fw_minute(&fw, &g, &tw, &acc, &c, (uint32_t)i * 60000u, &a); double dt = now_s() - t0;
    dts[i] = dt; tsum += dt; if (i == 0 || dt < tmin) tmin = dt; if (dt > tmax) tmax = dt; states[fw.last_out.state]++;
  }
  printf("hg_fw_minute: N=%d mean %.2f us  min %.2f us  max %.2f us (host)\n", N, tsum / N * 1e6, tmin * 1e6, tmax * 1e6);
  qsort(dts, N, sizeof(double), cmpd); printf("percentiles: p50 %.2f us p99 %.2f us p99.9 %.2f us (host; max is scheduler noise on a loaded 2-CPU box)\n", dts[N/2]*1e6, dts[N*99/100]*1e6, dts[N*999/1000]*1e6);
  printf("x50: p99.9 %.2f ms\n", dts[N*999/1000]*50e3);
  printf("states:"); for (int k = 0; k < 9; k++) printf(" %d", states[k]); printf("\n");
  double t0 = now_s(); for (int i = 0; i < 2000; i++) hg_twin_nightly_update(&tw, &acc); double tn = (now_s() - t0) / 2000;
  static uint8_t buf[HG_FW_TWIN_BUF]; t0 = now_s(); int n = 0; for (int i = 0; i < 2000; i++) n = hg_fw_twin_pack(&g, &tw, &acc, 1, buf, sizeof buf); double tp = (now_s() - t0) / 2000;
  static hg_guardian_t g2; uint32_t sc; t0 = now_s(); for (int i = 0; i < 2000; i++) hg_fw_twin_load(&g2, &p, &tw, &acc, buf, (uint16_t)n, &sc); double tl = (now_s() - t0) / 2000;
  printf("nightly_update %.2f us, twin_pack %.2f us (%d B), twin_load %.2f us (host)\n", tn * 1e6, tp * 1e6, n, tl * 1e6);
  printf("x50 (rough M4F factor, T template): minute mean %.2f ms max %.2f ms; nightly+pack %.2f ms\n", tsum / N * 50e3, tmax * 50e3, (tn + tp) * 50e3);
  return 0;
}
