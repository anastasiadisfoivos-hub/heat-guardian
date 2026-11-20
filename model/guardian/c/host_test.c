#define _POSIX_C_SOURCE 200809L
#include "hg_fp.h"   /* T5 D1: first include - IEEE-exact float semantics even under -ffast-math */
/* Heat Guardian - guardian/c host tests.
 *   ./host_test                       unit + property tests (+ crafted traces and vectors found under ../tests)
 *   ./host_test replay in.csv out.csv per-minute replay through hg_guardian_step (format: py/run_traces.py)
 * Prints one PASS/FAIL line per test with its max diff. Exit code = number of failed tests. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "hg_guardian.h"
#include "hg_guardian_cfg.h"
#include "hg2_weights.h"
#include "hg_util.h"
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

static int n_fail = 0, n_pass = 0;
static void report(const char *name, int ok, const char *fmt, double v) {
  printf("%s %-46s ", ok ? "PASS" : "FAIL", name);
  printf(fmt, v); printf("\n");
  if (ok) n_pass++; else n_fail++;
}

/* ------------------------------------------------------------ CSV replay */
static void hexbytes(const char *h, uint8_t *b, int *n, int cap) {   /* T5 m7: never writes past cap bytes */
  int k = 0;
  while (h[0] && h[1] && k < cap) { unsigned v; if (sscanf(h, "%2x", &v) != 1) break; b[k++] = (uint8_t)v; h += 2; }
  *n = k;
}
static float tokf(char **save) { char *t = strtok_r(NULL, ",\r\n", save); return t ? strtof(t, NULL) : NAN; }
static long toki(char **save) { char *t = strtok_r(NULL, ",\r\n", save); return t ? strtol(t, NULL, 10) : 0; }

typedef struct { hg_guardian_t g; hg_forecast_buf_t fc; int have_fc; hg2_aux_t aux; } replay_t;
static replay_t RP;

static int replay(const char *inp, const char *outp, int check_expect, int *mism) {
  FILE *fi = fopen(inp, "r"); if (!fi) { perror(inp); return -1; }
  FILE *fo = outp ? fopen(outp, "w") : NULL;
  static char line[16384];
  hg2_profile_t prof = { 75.0f, 0.0f, 26.0f, 0 };
  hg2_twin_t tw; memset(&tw, 0, sizeof tw);
  tw.rest_hr = 70.0f; tw.k_person = 0.12f; tw.core_offset = 0.0f; tw.c_bodyheat = 0.15f;
  for (int h = 0; h < 24; h++) tw.t1_night_base[h] = NAN;
  int started = 0, row = 0, bad = 0;
  hg_forecast_init(&RP.fc); RP.have_fc = 0;
  while (fgets(line, sizeof line, fi)) {
    char *save = NULL;
    if (line[0] == '#') {
      char *t = strtok_r(line, ",\r\n", &save);
      if (!strcmp(t, "#PROFILE")) { prof.age = tokf(&save); prof.sex_m = tokf(&save); prof.bmi = tokf(&save); prof.med_flags = (uint8_t)toki(&save); }
      else if (!strcmp(t, "#TWIN")) {
        tw.rest_hr = tokf(&save); tw.k_person = tokf(&save); tw.core_offset = tokf(&save); tw.c_bodyheat = tokf(&save);
        for (int h = 0; h < 24; h++) tw.t1_night_base[h] = tokf(&save);
      } else if (!strcmp(t, "#FORECAST")) {
        char *hx = strtok_r(NULL, ",\r\n", &save); int n = 0; hexbytes(hx, RP.fc.data, &n, (int)sizeof RP.fc.data); RP.have_fc = n == 72;
      }
      continue;
    }
    if (!strncmp(line, "mod,", 4)) continue;
    if (!started) { hg_guardian_init(&RP.g, &prof, &tw); started = 1; }
    hg_minute_t m; memset(&m, 0, sizeof m);
    char *t = strtok_r(line, ",\r\n", &save); if (!t) continue;
    m.s.minute_of_day = (uint16_t)strtol(t, NULL, 10);
    m.s.t1_c = tokf(&save); m.s.t2_c = tokf(&save); m.s.t_air_c = tokf(&save); m.s.rh_pct = tokf(&save); m.s.hr_bpm = tokf(&save);
    m.s.hr_quality = (uint8_t)toki(&save); m.s.pi_pct = tokf(&save); m.s.a_std_g = tokf(&save); m.a_peak_g = tokf(&save);
    m.ppg_dc = (uint32_t)toki(&save); m.flat_still_min = (uint8_t)toki(&save); m.button = (uint8_t)toki(&save);
    m.charging = (uint8_t)toki(&save); m.vbat = tokf(&save); m.ble_bucket = (int8_t)toki(&save); m.force_worn = (uint8_t)toki(&save);
    char *cmd = strtok_r(NULL, ",\r\n", &save);
    for (int k = 0; k < 12; k++) m.t1_5s[k] = tokf(&save);
    for (int k = 0; k < 12; k++) m.t2_5s[k] = tokf(&save);
    for (int k = 0; k < 12; k++) m.tair_5s[k] = tokf(&save);
    for (int k = 0; k < 12; k++) m.zangle_5s[k] = tokf(&save);
    long expect = -1, expect_worn = -1;
    if (check_expect) { char *e = strtok_r(NULL, ",\r\n", &save); if (e) expect = strtol(e, NULL, 10);
      e = strtok_r(NULL, ",\r\n", &save); if (e) expect_worn = strtol(e, NULL, 10); }
    if (cmd && cmd[0] != '-') {
      uint8_t b[64]; int n = 0; hexbytes(cmd, b, &n, (int)sizeof b);
      hg_cmd_t c; int r = hg_cmd_parse(b, (uint16_t)n, &c, &RP.fc);
      if (r > 0) { hg_guardian_cmd(&RP.g, &c); if (r == HG_CMD_FORECAST && RP.fc.complete) RP.have_fc = 1; }
    }
    m.forecast72 = RP.have_fc ? RP.fc.data : NULL; m.has_forecast = (uint8_t)RP.have_fc;
    hg_minute_out_t o; memset(&o, 0, sizeof o);
    RP.g.hg2_dbg = &RP.aux;
    hg_guardian_step(&RP.g, &m, &o);
    if ((expect >= 0 && expect != o.state) || (expect_worn >= 0 && expect_worn != o.worn)) {
      if (bad < 5) fprintf(stderr, "  %s row %d: state %d (exp %ld) worn %d (exp %ld)\n", inp, row, o.state, expect, o.worn, expect_worn);
      bad++; }
    if (fo) {
      char hx[41]; for (int i = 0; i < 20; i++) sprintf(hx + 2 * i, "%02x", o.status[i]);
      const hg2_out_t *c = &o.core; const hg2_aux_t *a = &RP.aux;
      fprintf(fo, "%d,%d,%d,%d,%lu,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d", row, o.state, o.level, o.family_alert, (unsigned long)o.alarm_id,
              o.check_reason, o.check_min, o.haptic, o.screen, o.worn, o.home_out, o.routine_score, o.why, o.tiers, o.routine_req,
              o.imok_resp_min, o.notify_not_worn);
      fprintf(fo, ",%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%d,%d,%d,%.9g,%.9g,%.9g,%.9g,%d,%d,%s",
              (double)c->core_now, (double)c->core_20, (double)c->sd_now, (double)c->f20_eff, (double)c->logit_p38, (double)c->logit_p385,
              (double)c->strain, (double)c->kf, (double)c->core_flux, (double)c->core_30, c->flux_valid, c->hr_valid, c->valid,
              (double)a->v12_est, (double)a->v12_f20, (double)a->v12_z, (double)a->t_air_corr, a->env_run, a->env_dose, hx);
      for (int i = 0; i < HG2_N_IN; i++) fprintf(fo, ",%.9g", (double)a->x[i]);
      for (int i = 0; i < HG2_N_OUT; i++) fprintf(fo, ",%.9g", (double)a->nn_mean[i]);
      for (int i = 0; i < HG2_N_OUT; i++) fprintf(fo, ",%.9g", (double)a->nn_sd[i]);
      fprintf(fo, ",%d,%d", o.night_heat, o.nudge);
      fprintf(fo, "\n");
    }
    row++;
  }
  fclose(fi); if (fo) fclose(fo);
  if (mism) *mism = bad;
  return row;
}

/* ------------------------------------------------------------ unit tests */
static void test_sizes(void) {
  report("sizeof(hg2_state_t) <= 512", sizeof(hg2_state_t) <= 512 && hg2_state_size() == sizeof(hg2_state_t), "%.0f B", (double)sizeof(hg2_state_t));
  report("sizeof(hg_guardian_t) <= 4096", sizeof(hg_guardian_t) <= 4096, "%.0f B", (double)sizeof(hg_guardian_t));
  printf("     sizes: guardian %u, hg2 %u, kf %u, contact %u, homeout %u, routine %u, minute_in %u, minute_out %u\n",
         (unsigned)sizeof(hg_guardian_t), (unsigned)sizeof(hg2_state_t), (unsigned)sizeof(hg_kf_t), (unsigned)sizeof(hg_contact_t),
         (unsigned)sizeof(hg_homeout_t), (unsigned)sizeof(hg_routine_t), (unsigned)sizeof(hg_minute_t), (unsigned)sizeof(hg_minute_out_t));
}
static void test_crc8(const char *path) {
  const uint8_t chk[9] = { '1', '2', '3', '4', '5', '6', '7', '8', '9' };
  int ok = hg_crc8(chk, 9) == 0xF4;
  int n = 0, bad = 0;
  FILE *f = fopen(path, "r");
  if (f) {
    char line[1024];
    while (fgets(line, sizeof line, f)) {
      char hx[900]; unsigned c;
      if (sscanf(line, "%899s %x", hx, &c) != 2) continue;
      uint8_t b[450]; int nb = 0; if (hx[0] != '-') hexbytes(hx, b, &nb, (int)sizeof b);
      n++; if (hg_crc8(b, (uint16_t)nb) != c) bad++;
    }
    fclose(f);
  }
  report("CRC-8 poly 0x07 check + vectors", ok && f && bad == 0, "%.0f vectors", (double)n);
}
static void test_weights_crc(void) { report("hg2 weights CRC-32 (" HG2_NN_VERSION ")", hg2_check_crc(), "0x%08.0f", 0.0); }
static void test_luts(void) {
  double e1 = 0, e2 = 0, e3 = 0, e4 = 0;
  for (int i = 0; i <= 3200; i++) { float z = -8.0f + 0.005f * (float)i; double d = fabs((double)hg2_sigmoid_lut(z) - 1 / (1 + exp(-(double)z))); if (d > e1) e1 = d; }
  for (int i = 0; i <= 2500; i++) { float t = 20.0f + 0.01f * (float)i; double td = (double)t; double ex = (double)61094 / 100000 * exp((double)17625 / 1000 * td / (td + (double)24304 / 100)); double d = fabs((double)hg_psat_kpa(t) / ex - 1); if (d > e2) e2 = d; }
  for (int i = 0; i <= 5000; i++) { float x = 0.01f * (float)i; double d = fabs((double)hg_ln1p(x) - log1p((double)x)); if (d > e3) e3 = d; }
  for (int m = 0; m < 1440; m++) { double d = fabs((double)hg_sin_tod((uint16_t)m) - sin(2 * (double)M_PI * m / 1440)); double d2 = fabs((double)hg_cos_tod((uint16_t)m) - cos(2 * (double)M_PI * m / 1440)); if (d > e4) e4 = d; if (d2 > e4) e4 = d2; }
  report("sigmoid LUT max err <= 0.004", e1 <= (double)4 / 1000, "%.2e", e1);
  report("Magnus table (quadratic) max rel err <= 5e-5", e2 <= (double)5 / 100000, "%.2e", e2);
  report("ln1p table max err <= 2e-4", e3 <= (double)2 / 10000, "%.2e", e3);
  report("sin/cos tod table max err <= 1e-3", e4 <= (double)1 / 1000, "%.2e", e4);
}
static void test_frames(void) {
  /* CMD parser: good frames accepted, bad CRC and short frames rejected */
  uint8_t t[7] = { 0x10, 0x00, 0x2D, 0x31, 0x67, 8, 0 }; t[6] = hg_crc8(t, 6);
  hg_cmd_t c; hg_forecast_buf_t fc; hg_forecast_init(&fc);
  int ok = hg_cmd_parse(t, 7, &c, &fc) == HG_CMD_TIME && c.unix_s == 0x67312D00u && c.tz_q == 8;
  t[6] ^= 1; ok = ok && hg_cmd_parse(t, 7, &c, &fc) == HG_CMD_ERR_CRC;
  ok = ok && hg_cmd_parse(t, 5, &c, &fc) == HG_CMD_ERR_SHORT;
  uint8_t bad_op[7] = { 0x55, 0, 0, 0, 0, 0, 0 }; bad_op[6] = hg_crc8(bad_op, 6);
  ok = ok && hg_cmd_parse(bad_op, 7, &c, &fc) == HG_CMD_ERR_OP;
  int nfc = 0;
  for (int ch = 0; ch < 4; ch++) {
    uint8_t f[20]; f[0] = 0x11;
    for (int k = 0; k < 6; k++) { f[1 + 3 * k] = (uint8_t)(int8_t)(25 + ch); f[2 + 3 * k] = (uint8_t)(40 + k); f[3 + 3 * k] = (uint8_t)((ch << 3) | (k & 7)); }
    f[19] = hg_crc8(f, 19);
    if (hg_cmd_parse(f, 20, &c, &fc) == HG_CMD_FORECAST) nfc++;
  }
  ok = ok && nfc == 4 && fc.complete && fc.data[3 * 7] == 26 && fc.data[3 * 7 + 1] == 41 && fc.data[3 * 7 + 2] == 1;
  uint8_t f2[20]; memset(f2, 0, 20); f2[0] = 0x11; f2[3] = 0x08; f2[19] = hg_crc8(f2, 19);   /* inconsistent chunk index */
  ok = ok && hg_cmd_parse(f2, 20, &c, &fc) == HG_CMD_ERR_FIELD;
  report("CMD parser: accept good / reject CRC, short, op, field", ok, "%.0f", 0.0);
  hg_info_t inf = { 0x0100, HG2_NN_CRC32, 7, 1, 3, "hg2stub" };
  uint8_t o[20]; hg_info_pack(&inf, o);
  report("INFO frame CRC-8", o[19] == hg_crc8(o, 19) && o[0] == 0x02, "%.0f", 0.0);
}
static void test_ble_vectors(const char *path) {
  FILE *f = fopen(path, "r");
  if (!f) { report("B4 ble_vectors (0x11/0x14 decode)", 0, "%.0f missing", 0.0); return; }
  hg_forecast_buf_t fc; hg_forecast_init(&fc); hg_cmd_t c;
  char line[512]; int nf = 0, nh = 0, bad = 0, sok = 0;
  while (fgets(line, sizeof line, f)) {
    char hx[128]; uint8_t b[64]; int n = 0;
    if (line[0] == 'F' && sscanf(line + 2, "%127s", hx) == 1) { hexbytes(hx, b, &n, (int)sizeof b); if (hg_cmd_parse(b, (uint16_t)n, &c, &fc) == HG_CMD_FORECAST) nf++; else bad++; }
    else if (line[0] == 'H') { int h, t, rh, fl; if (sscanf(line + 2, "%d %d %d %d", &h, &t, &rh, &fl) == 4) { nh++;
        if ((int8_t)fc.data[3 * h] != t || fc.data[3 * h + 1] != rh || fc.data[3 * h + 2] != fl) bad++; } }
    else if (line[0] == 'S') { unsigned bm, pid; char tag[64];
      if (sscanf(line + 2, "%127s %u %u %63s", hx, &bm, &pid, tag) == 4) { hexbytes(hx, b, &n, (int)sizeof b);
        for (char *q = tag; *q; q++) if (*q == '_') *q = ' ';
        sok = hg_cmd_parse(b, (uint16_t)n, &c, NULL) == HG_CMD_SAFE_HOURS && c.safe_bitmap == bm && c.plan_id == pid && !strcmp(c.tag, tag); } }
  }
  fclose(f);
  report("B4 ble_vectors: 0x11 chunks + 24 h decode + 0x14", nf == 4 && fc.complete && nh == 24 && bad == 0 && sok, "%.0f mismatches", (double)bad);
}

static void test_calm_api(void) {   /* M9.5: the Twin persists design A's calm-f20 baseline through this API */
  static hg_guardian_t g; hg2_profile_t p = { 75.0f, 0.0f, 26.0f, 0 }; hg2_twin_t tw; memset(&tw, 0, sizeof tw);
  tw.rest_hr = 70.0f; tw.k_person = 0.12f; tw.c_bodyheat = 0.15f; for (int h = 0; h < 24; h++) tw.t1_night_base[h] = NAN;
  hg_guardian_init(&g, &p, &tw);
  hg_calm_t c = { 37.31f, 4 }, o; int ok = hg_guardian_set_calm(&g, &c); hg_guardian_get_calm(&g, &o);
  ok = ok && o.calm_f20_c == 37.31f && o.calm_f20_n == 4;
  hg_calm_t bad1 = { NAN, 3 }, bad2 = { 39.0f, 3 };
  ok = ok && !hg_guardian_set_calm(&g, &bad1); hg_guardian_get_calm(&g, &o); ok = ok && o.calm_f20_n == 0;
  ok = ok && !hg_guardian_set_calm(&g, &bad2); hg_guardian_get_calm(&g, &o); ok = ok && o.calm_f20_n == 0;
  report("M9.5 calm-f20 get/set round-trip + NaN/out-of-bounds rejected", ok, "%.0f", 0.0);
  { hg_exc_t e = { 12.5f, 2.5f }, eo; int ok2 = hg_guardian_set_exc(&g, &e); hg_guardian_get_exc(&g, &eo);
    ok2 = ok2 && eo.sxx == 12.5f && eo.sxy == 2.5f && g.x_c == 0.2f;
    hg_exc_t bad = { NAN, 1.0f }; ok2 = ok2 && !hg_guardian_set_exc(&g, &bad) && g.x_sxx == 0.0f && g.x_c == 0.0f;
    hg_exc_t bad2 = { -1.0f, 1.0f }; ok2 = ok2 && !hg_guardian_set_exc(&g, &bad2);
    report("M19 Exception DRINK sums get/set round-trip + NaN/negative rejected", ok2, "%.0f", 0.0); }
}

static void test_routine_pack(void) {
  static hg_routine_t r, r2; hg_routine_init(&r);
  for (int h = 0; h < 24; h++) { r.am[h].n = 5; r.am[h].mean = (float)h; r.am[h].m2 = 2; r.maxq[h] = (int16_t)(10 * h); }
  r.sleep_on = 1350; r.sleep_off = 420; r.n_wake = 3; r.wake_hist[0] = 420;
  uint8_t buf[HG_ROUTINE_PACK_BYTES];
  uint16_t n = hg_routine_pack(&r, buf, sizeof buf);
  int ok = n == HG_ROUTINE_PACK_BYTES && n <= 700 && hg_routine_unpack(&r2, buf, n) && r2.maxq[23] == 230 && r2.sleep_on == 1350;
  buf[100] ^= 0x5A; ok = ok && !hg_routine_unpack(&r2, buf, n) && r2.am[5].n == 0.0f;   /* corruption -> defaults */
  report("routine pack/unpack (<= 700 B) + corruption -> defaults", ok, "%.0f B", (double)n);
}

/* ------------------------------------------------------------ property tests (10,000 random sequences) */
static uint32_t rs = 2463534242u;
static uint32_t xr(void) { rs ^= rs << 13; rs ^= rs >> 17; rs ^= rs << 5; return rs; }
static float ur(float a, float b) { return a + (b - a) * (float)(xr() & 0xFFFFFF) / 16777216.0f; }

static void property_tests(int nseq) {
  static hg_guardian_t g;
  long viol[12] = { 0 }; long steps = 0, help_seen = 0, fam_seen = 0, checks_seen = 0, frozen_hours = 0;
  for (int sq = 0; sq < nseq; sq++) {
    hg2_profile_t p = { ur(60, 90), (float)(xr() & 1), ur(20, 34), (uint8_t)(xr() & 15) };
    hg2_twin_t tw; memset(&tw, 0, sizeof tw); tw.rest_hr = ur(50, 85); tw.k_person = 0.12f; tw.c_bodyheat = 0.15f;
    for (int h = 0; h < 24; h++) tw.t1_night_base[h] = NAN;
    hg_guardian_init(&g, &p, &tw);
    int len = 120 + (int)(xr() % 360);
    uint16_t mod = (xr() & 7) == 0 ? 0xFFFF : (uint16_t)(xr() % 1440);
    float hr = ur(60, 100), ta = ur(22, 42), rh = ur(15, 70);
    int worn = 2, worn_left = 60, help_latched = 0; uint32_t help_id = 0;
    hg_tier_t pd = g.drink, pc = g.cool, pg = g.danger; uint8_t plev = 0, pfam = 0, pcm = 0xFF;
    int hour_dirty = 0; uint8_t hcur = 0xFF; float n_before = 0;
    for (int t = 0; t < len; t++) {
      hg_minute_t m; memset(&m, 0, sizeof m);
      if (--worn_left <= 0) { worn = (xr() % 10) < 7 ? 2 : (int)(xr() % 2); worn_left = 5 + (int)(xr() % 60); }
      hr += ur(-6, 6.5f); if (hr < 45) hr = 45; if (hr > 195) hr = 195;
      ta += ur(-0.4f, 0.42f); if (ta < 18) ta = 18; if (ta > 46) ta = 46;
      rh += ur(-2, 2); if (rh < 5) rh = 5; if (rh > 95) rh = 95;
      m.s.minute_of_day = mod; m.s.t1_c = ur(33, 36); m.s.t2_c = (xr() & 3) ? m.s.t1_c - ur(0, 2) : NAN;
      m.s.t_air_c = ta; m.s.rh_pct = rh; m.s.hr_bpm = hr; m.s.hr_quality = (xr() % 10) < 8 ? 4 : (uint8_t)(xr() % 4);
      m.s.pi_pct = ur(0.02f, 1.5f); m.s.a_std_g = (xr() & 3) == 0 ? ur(0, 0.002f) : ur(0, 0.2f);
      for (int k = 0; k < 12; k++) { m.t1_5s[k] = m.s.t1_c; m.t2_5s[k] = m.s.t2_c; m.tair_5s[k] = ta; m.zangle_5s[k] = ur(-30, 30); }
      m.a_peak_g = (xr() % 200) == 0 ? 2.5f : 1.1f; m.ppg_dc = 100000; m.vbat = ur(3.3f, 4.2f); m.ble_bucket = (int8_t)((int)(xr() % 4) - 1);
      uint32_t b = xr() % 100; m.button = b < 3 ? 1 : (b < 4 ? 2 : 0);
      m.force_worn = (uint8_t)worn;
      /* random phone acks, incl. the right HELP id */
      if (help_latched && (xr() % 40) == 0) {
        hg_cmd_t c; memset(&c, 0, sizeof c); c.op = HG_CMD_FAMILY_ACK; c.ack_type = (uint8_t)(1 + xr() % 3); c.alarm_id = (xr() & 1) ? help_id : xr();
        hg_guardian_cmd(&g, &c);
        if (c.ack_type == 3 && (c.alarm_id == help_id || (c.alarm_id & 0xFFFF) == (help_id & 0xFFFF))) help_latched = 0;
      }
      uint8_t h_now = mod < 1440 ? (uint8_t)(mod / 60) : 0xFF;
      if (h_now != hcur) {   /* P7: learning frozen under alarms / not worn: an hour that had them must not be committed */
        if (hcur < 24 && hour_dirty && g.rt.am[hcur].n != n_before) viol[6]++;
        if (hcur < 24 && hour_dirty) frozen_hours++;
        hcur = h_now; hour_dirty = 0; n_before = h_now < 24 ? g.rt.am[h_now].n : 0;
      }
      hg_minute_out_t o; hg2_aux_t aux; g.hg2_dbg = &aux;
      hg_guardian_step(&g, &m, &o); steps++;
#if HG_M7_ROUTINE
      if (h_now < 24 && ((o.tiers & 6) || o.check_min != 0xFF || worn != 2)) hour_dirty = 1;   /* M7.3 (i): DRINK does not freeze */
#else
      if (h_now < 24 && (o.tiers || worn != 2)) hour_dirty = 1;
#endif
      if (o.level > plev + 1) viol[0]++;                                             /* P1 no level skip */
      const hg_tier_t *nt[3] = { &g.drink, &g.cool, &g.danger }, *pt[3] = { &pd, &pc, &pg };
      for (int k = 0; k < 3; k++) {
        if (!pt[k]->on && nt[k]->on && nt[k]->run < HG_DEBOUNCE_MIN) viol[1]++;      /* P2 2-min debounce */
        if (pt[k]->on && !nt[k]->on && !(nt[k]->off == HG_HOLD_MIN && nt[k]->run == 0)) viol[2]++;   /* P3 10-min hold exact */
        if (worn == 0 && (nt[k]->on != pt[k]->on || nt[k]->run != pt[k]->run || nt[k]->off != pt[k]->off)) viol[3]++; /* P9 frozen */
      }
      if (o.check_min != 0xFF) {
        checks_seen++;
        int ask = (o.check_min == 0 || o.check_min == 2 || o.check_min == 5) && o.check_min != pcm;   /* first minute at that time (the timer pauses while worn == 0) */
        if (ask && !(o.haptic == HG_HAP_CHECK || o.haptic == HG_HAP_SOFT)) {
          if (getenv("HG_DBG") && viol[4] < 8) printf("  dbg P4: seq %d t %d check_min %d prev %d worn %d haptic %d state %d button %d\n", sq, t, o.check_min, pcm, worn, o.haptic, o.state, m.button);
          viol[4]++; }  /* P4 asks at 0/2/5 */
      }
      if (!pfam && o.family_alert) {                                                  /* P5/P10 family only via CHECK window or HELP */
        fam_seen++;
        if (o.state != HG_ST_HELP) {
          int fmin = (o.check_reason & (HG_CR_DANGER | HG_CR_BEHAVIOUR | HG_CR_IMPACT)) ? 5 : 10;
          if (o.check_min == 0xFF || o.check_min < fmin) viol[5]++;
          if ((o.check_reason & (HG_CR_DANGER | HG_CR_BEHAVIOUR)) == 0 && (o.check_reason & HG_CR_IMPACT) == 0 && o.check_min != 10) viol[5]++;
        }
      }
      if (m.button == 2 && !help_latched) { help_latched = 1; help_id = g.help_id; help_seen++; }
      if (help_latched && o.state != HG_ST_HELP) viol[7]++;                            /* P6 HELP latched until ack type 3 */
      if (!help_latched && o.state == HG_ST_HELP) viol[7]++;
      if (mod == 0xFFFF && (o.routine_req != 0 || o.routine_score != 255 || aux.x[23] != 0.0f || aux.x[24] != 0.0f)) viol[8]++;  /* P8 */
      if (o.state > HG_ST_HELP || o.level > 3) viol[9]++;
      if (o.status[19] != hg_crc8(o.status, 19)) viol[10]++;
      if (o.haptic != HG_HAP_NONE && o.haptic != HG_HAP_SOFT && m.vbat < HG_VBAT_SOFT) viol[11]++;
      pd = g.drink; pc = g.cool; pg = g.danger; plev = o.level; pfam = o.family_alert; pcm = o.check_min;
      if (mod != 0xFFFF) mod = (uint16_t)((mod + 1) % 1440);
    }
  }
  const char *names[12] = { "no level skip", "2-min debounce", "10-min hold exact", "NOT_WORN freezes tiers", "CHECK asks at 0/2/5 min",
                            "family only after 5/10-min CHECK window", "learning frozen under alarms/not worn", "HELP latched until 0x12 type 3",
                            "time unknown: routine + circadian off", "state/level in range", "STATUS CRC-8", "battery < 3.5 V -> soft haptics" };
  printf("     property run: %d sequences, %ld minutes, %ld CHECK-minutes, %ld family flags, %ld HELP, %ld frozen hours\n",
         nseq, steps, checks_seen, fam_seen, help_seen, frozen_hours);
  for (int k = 0; k < 12; k++) { char nm[96]; snprintf(nm, sizeof nm, "property: %s", names[k]); report(nm, viol[k] == 0, "%.0f violations", (double)viol[k]); }
}

/* M3.1: the NN can only ADD alarms / lower thresholds. Two guardians see identical inputs; in A every NN-derived output is
 * silenced (f20/f30 = 30 C, sd 0, logits -100, strain 0), so A runs on the protected paths only (PSU env lines, v1.2 logistic
 * Danger, behaviour path); in B the NN outputs are random. Property: every tier on in A is on in B, and level_A <= level_B. */
/* T5 D3: the hooks rewrite what the tiers READ (aux->core20_noff in the default build) as well as hg2_out_t */
static void hook_silent(hg2_out_t *c, hg2_aux_t *a, void *x) { (void)x; c->core_20 = c->core_30 = c->f20_eff = c->f30_eff = 30.0f; c->sd_20 = c->sd_30 = 0.0f;
  c->logit_p38 = c->logit_p385 = -100.0f; c->strain = 0.0f; a->core20_noff = 30.0f; }
static float hook_nn = 37.5f;
static void hook_random(hg2_out_t *c, hg2_aux_t *a, void *x) { (void)x;
  hook_nn += ur(-0.06f, 0.059f); if (hook_nn < 36.0f) hook_nn = 36.0f; if (hook_nn > 39.5f) hook_nn = 39.5f;   /* random walk: rising AND falling slopes */
  c->core_20 = hook_nn; c->sd_20 = ur(0.0f, 0.5f); a->core20_noff = hook_nn;
  c->f20_eff = c->core_20; c->core_30 = c->core_20; c->f30_eff = c->f20_eff;
  c->logit_p38 = ur(-10.0f, 10.0f); c->logit_p385 = ur(-10.0f, 10.0f); c->strain = ur(0.0f, 10.0f); }
static void property_nn_monotone(int nseq) {
  static hg_guardian_t A, B;
  long viol = 0, prot_min = 0, prot_danger = 0, steps = 0, fam_a = 0, fam_viol = 0;
  for (int sq = 0; sq < nseq; sq++) {
    hg2_profile_t p = { ur(60, 90), (float)(xr() & 1), ur(20, 34), (uint8_t)(xr() & 15) };
    hg2_twin_t tw; memset(&tw, 0, sizeof tw); tw.rest_hr = ur(50, 85); tw.k_person = 0.12f; tw.c_bodyheat = 0.15f;
    for (int h = 0; h < 24; h++) tw.t1_night_base[h] = NAN;
    hg_guardian_init(&A, &p, &tw); hg_guardian_init(&B, &p, &tw);
    A.nn_test_hook = hook_silent; B.nn_test_hook = hook_random; hook_nn = ur(36.8f, 38.8f);
    const int presses = (int)(sq & 1); uint8_t fa_prev = 0;
    int len = 120 + (int)(xr() % 360);
    uint16_t mod = (xr() & 7) == 0 ? 0xFFFF : (uint16_t)(xr() % 1440);
    float hr = ur(60, 120), ta = ur(28, 44), rh = ur(15, 80); int worn = 2, worn_left = 90;
    for (int t = 0; t < len; t++) {
      hg_minute_t m; memset(&m, 0, sizeof m);
      if (--worn_left <= 0) { worn = (xr() % 10) < 8 ? 2 : (int)(xr() % 2); worn_left = 5 + (int)(xr() % 90); }
      hr += ur(-6, 6.5f); if (hr < 45) hr = 45; if (hr > 195) hr = 195;
      ta += ur(-0.4f, 0.42f); if (ta < 18) ta = 18; if (ta > 46) ta = 46;
      rh += ur(-2, 2); if (rh < 5) rh = 5; if (rh > 95) rh = 95;
      m.s.minute_of_day = mod; m.s.t1_c = ur(33, 36); m.s.t2_c = m.s.t1_c - ur(0, 2); m.s.t_air_c = ta; m.s.rh_pct = rh; m.s.hr_bpm = hr;
      m.s.hr_quality = (xr() % 10) < 8 ? 4 : (uint8_t)(xr() % 4); m.s.pi_pct = ur(0.1f, 1.5f);
      m.s.a_std_g = (xr() % 3) ? ur(0, 0.002f) : ur(0, 0.2f);
      for (int k = 0; k < 12; k++) { m.t1_5s[k] = m.s.t1_c; m.t2_5s[k] = m.s.t2_c; m.tair_5s[k] = ta; m.zangle_5s[k] = ur(-30, 30); }
      m.a_peak_g = 1.1f; m.ppg_dc = 100000; m.vbat = 3.9f; m.ble_bucket = -1; m.force_worn = (uint8_t)worn;
      uint32_t b = xr() % 100; m.button = (presses && b < 4) ? 1 : 0;   /* presses in half the pairs; no HELP */
      hg_minute_out_t oa, ob; hg_guardian_step(&A, &m, &oa); hg_guardian_step(&B, &m, &ob); steps++;
      if ((oa.tiers & ~ob.tiers) || oa.level > ob.level) { viol++; if (getenv("HG_DBG31") && viol < 6) printf("DBG sq %d t %d tiers %u/%u lvl %u/%u worn %d coolA %u/%u runs %u/%u pd %u/%u dz %u/%u\n", sq, t, oa.tiers, ob.tiers, oa.level, ob.level, worn, A.cool.on, B.cool.on, A.cool.run, B.cool.run, A.pd_cool_run, B.pd_cool_run, A.danger.run, B.danger.run); }
      /* T5 D3: family alerts too - without presses, a thermal family call of the NN-silenced twin must be pending in the other */
      if (!presses && oa.family_alert && !fa_prev && (oa.check_reason & 3u)) { fam_a++; if (!ob.family_alert) fam_viol++; }
      fa_prev = oa.family_alert;
      if (oa.tiers) prot_min++;
      if (oa.tiers & 4) prot_danger++;
      if (mod != 0xFFFF) mod = (uint16_t)((mod + 1) % 1440);
    }
  }
  printf("     M3.1 run: %d sequence pairs, %ld minutes, %ld minutes with a protected-path tier, %ld with protected DANGER\n", nseq, steps, prot_min, prot_danger);
  printf("     M3.1 family: %ld thermal family calls of the NN-silenced twin (no presses), %ld missing in the NN twin\n", fam_a, fam_viol);
  report("property M3.1: NN never removes a protected alarm or family call", viol == 0 && fam_viol == 0 && prot_danger > 0 && fam_a > 0,
         "%.0f violations", (double)(viol + fam_viol));
}

/* M19: the M3.1 property on LONG sequences (3 days) - the only length that arms Marble (24 h) and runs Exception DRINK's
 * nightly learning and settled rule. NN-silenced twin vs random-NN twin, identical protected inputs, no presses. */
static void property_m19_long(int npairs) {
  static hg_guardian_t A, B;
  long viol = 0, fam_a = 0, fam_viol = 0, steps = 0, danger_b = 0, drink_a = 0;
  for (int sq = 0; sq < npairs; sq++) {
    hg2_profile_t p = { ur(65, 90), (float)(xr() & 1), ur(20, 34), (uint8_t)(xr() & 15) };
    hg2_twin_t tw; memset(&tw, 0, sizeof tw); tw.rest_hr = ur(55, 80); tw.k_person = 0.12f; tw.c_bodyheat = 0.15f;
    for (int h = 0; h < 24; h++) tw.t1_night_base[h] = NAN;
    hg_guardian_init(&A, &p, &tw); hg_guardian_init(&B, &p, &tw);
    A.nn_test_hook = hook_silent; B.nn_test_hook = hook_random; hook_nn = ur(36.8f, 37.6f);
    uint16_t mod = (uint16_t)(xr() % 1440); float hr = ur(60, 90), ta = ur(24, 30), rh = ur(30, 60), a = 0.005f; uint8_t fa_prev = 0;
    for (int t = 0; t < 3 * 1440; t++) {
      hg_minute_t m; memset(&m, 0, sizeof m);
      if (xr() % 60 == 0) a = (xr() % 3 == 0) ? ur(0.05f, 0.25f) : ur(0.0f, 0.01f);                  /* bouts of chores */
      hr += ur(-3, 3.1f); if (hr < 55) hr = 55; if (hr > 125) hr = 125;
      ta += ur(-0.2f, 0.205f); if (ta < 22) ta = 22; if (ta > 35) ta = 35;
      m.s.minute_of_day = mod; m.s.t1_c = ur(33.5f, 36.5f); m.s.t2_c = m.s.t1_c - ur(0.2f, 1.5f); m.s.t_air_c = ta; m.s.rh_pct = rh;
      m.s.hr_bpm = hr; m.s.hr_quality = 4; m.s.pi_pct = 0.6f; m.s.a_std_g = a;
      for (int k = 0; k < 12; k++) { m.t1_5s[k] = m.s.t1_c; m.t2_5s[k] = m.s.t2_c; m.tair_5s[k] = ta; m.zangle_5s[k] = ur(-30, 30); }
      m.a_peak_g = 1.1f; m.ppg_dc = 100000; m.vbat = 3.9f; m.ble_bucket = -1; m.force_worn = 2;
      /* the NN-silenced twin keeps NO NN-fed path: Marble reads the tiers' f20 (NN, or v1.2 only via the OOD max with an
       * unphysical 30 C NN), so it is disarmed there; Marble is an NN-family path that may only ADD (M3.1 protects v1.2 / env /
       * behaviour paths) */
      A.mb_age = 0;
      hg_minute_out_t oa, ob; hg_guardian_step(&A, &m, &oa); hg_guardian_step(&B, &m, &ob); steps++;
      if ((oa.tiers & ~ob.tiers) || oa.level > ob.level) { viol++; if (getenv("HG_DBG19") && viol < 8) printf("DBG19 sq %d t %d mod %u tiers %u/%u lvl %u/%u dA %u/%u xprev %u/%u since %u/%u marbleA %u\n", sq, t, mod, oa.tiers, ob.tiers, oa.level, ob.level, A.drink.on, B.drink.on, A.x_prev, B.x_prev, A.x_since, B.x_since, A.mb_run); }
      if (oa.family_alert && !fa_prev && (oa.check_reason & 3u)) { fam_a++; if (!ob.family_alert) fam_viol++; }
      fa_prev = oa.family_alert;
      if (ob.tiers & 4) danger_b++;
      if (oa.tiers & 1) drink_a++;
      mod = (uint16_t)((mod + 1) % 1440);
    }
  }
  printf("     M19 long M3.1: %d pairs x 3 days, %ld minutes, NN-twin DANGER %ld min, silenced-twin DRINK %ld min, %ld family calls (silenced)\n",
         npairs, steps, danger_b, drink_a, fam_a);
  report("property M3.1 (3-day, Marble + Exception DRINK armed): NN never removes a protected alarm or family call",
         viol == 0 && fam_viol == 0 && danger_b > 0, "%.0f violations", (double)(viol + fam_viol));
}

/* M19 / T5 D1: NaN / inf / huge inputs on every field for 3 days must never leave a NaN or inf in the Marble or Exception
 * DRINK state (5 EWMAs, heat mass, slope sums, settled f20), and the state must keep moving after the bad minutes stop. */
static int fin(float x) { return hg_isfinite_bits(x); }
static void test_m19_nan_state(int nseq) {
  static hg_guardian_t G; long bad = 0;
  const float junk[4] = { NAN, INFINITY, -INFINITY, 1e30f };
  for (int sq = 0; sq < nseq; sq++) {
    hg2_profile_t p = { 78, 1, 26, 0 }; hg2_twin_t tw; memset(&tw, 0, sizeof tw); tw.rest_hr = 70; tw.k_person = 0.12f; tw.c_bodyheat = 0.15f;
    for (int h = 0; h < 24; h++) tw.t1_night_base[h] = NAN;
    hg_guardian_init(&G, &p, &tw);
    uint16_t mod = 480;
    for (int t = 0; t < 3 * 1440; t++) {
      hg_minute_t m; memset(&m, 0, sizeof m);
      const int junky = t < 2 * 1440 && (xr() % 4 == 0);
      m.s.minute_of_day = mod; m.s.t1_c = ur(34.5f, 36.5f); m.s.t2_c = m.s.t1_c - 0.8f; m.s.t_air_c = ur(27, 33); m.s.rh_pct = 45;
      m.s.hr_bpm = ur(70, 110); m.s.hr_quality = 4; m.s.pi_pct = 0.6f; m.s.a_std_g = ur(0, 0.2f);
      if (junky) { const float j = junk[xr() % 4]; switch (xr() % 5) { case 0: m.s.a_std_g = j; break; case 1: m.s.t_air_c = j; break;
                   case 2: m.s.t1_c = j; break; case 3: m.s.hr_bpm = j; break; default: m.s.rh_pct = j; } }
      for (int k = 0; k < 12; k++) { m.t1_5s[k] = m.s.t1_c; m.t2_5s[k] = m.s.t2_c; m.tair_5s[k] = m.s.t_air_c; m.zangle_5s[k] = 0; }
      m.a_peak_g = 1.1f; m.ppg_dc = 100000; m.vbat = 3.9f; m.ble_bucket = -1; m.force_worn = 2;
      hg_minute_out_t o; hg_guardian_step(&G, &m, &o);
      if (!(fin(G.mb_e10) && fin(G.mb_e60) && fin(G.mb_a30) && fin(G.mb_a120) && fin(G.mb_d) && fin(G.x_c) && fin(G.x_sxx)
            && fin(G.x_sxy) && fin(G.x_dww) && fin(G.x_dwd) && fin(G.x_dw) && fin(G.x_dref) && fin(G.x_last)
            && fin(G.sf_t1) && fin(G.sf_ta) && G.sf_t1 >= -40.0f && G.sf_t1 <= 85.0f && G.sf_ta >= -40.0f && G.sf_ta <= 85.0f)) bad++;   /* B5-v7 skin-floor state */
      mod = (uint16_t)((mod + 1) % 1440);
    }
    if (!(G.mb_age >= HG_MB_ARM_MIN && G.mb_a120 > 0.0f && G.mb_e60 > 35.0f)) bad++;   /* state still alive after the junk */
  }
  report("M19 NaN/inf/1e30 inputs (3 days) never poison the Marble / Exception DRINK state", bad == 0, "%.0f bad minutes", (double)bad);
  { /* B5-v7: PROFILE field 5 = medication flags (0..31 integers only); the skin-floor HR-blunted switch follows it */
    static hg_guardian_t P5; hg2_profile_t pp = { 78.0f, 0.0f, 26.0f, 0 }; hg2_twin_t tt; memset(&tt, 0, sizeof tt); tt.rest_hr = 70.0f;
    tt.k_person = 0.12f; tt.c_bodyheat = 0.15f; for (int h = 0; h < 24; h++) tt.t1_night_base[h] = NAN;
    hg_guardian_init(&P5, &pp, &tt);
    hg_cmd_t c; memset(&c, 0, sizeof c); c.op = HG_CMD_PROFILE; c.field = 5;
    int ok5 = 1; const float m0 = P5.m_cool;
    c.value = 16.0f; ok5 &= hg_guardian_cmd(&P5, &c) == 1 && P5.prof.med_flags == 16 && P5.m_cool == m0;      /* HRB bit: no margin */
    c.value = 1.0f;  ok5 &= hg_guardian_cmd(&P5, &c) == 1 && P5.prof.med_flags == 1 && P5.m_cool > m0;        /* beta-blocker margin */
    c.value = 32.0f; ok5 &= hg_guardian_cmd(&P5, &c) == 0 && P5.prof.med_flags == 1;
    c.value = 1.5f;  ok5 &= hg_guardian_cmd(&P5, &c) == 0 && P5.prof.med_flags == 1;
    c.value = -1.0f; ok5 &= hg_guardian_cmd(&P5, &c) == 0;
    c.value = NAN;   ok5 &= hg_guardian_cmd(&P5, &c) == 0 && P5.prof.med_flags == 1;
    report("B5-v7 PROFILE field 5 (med flags 0..31, integers) applied; 32 / 1.5 / -1 / NaN rejected", ok5, "%.0f", 0.0); }
}

/* M4.3: a +1 C thermometer reading (Twin offset +1 and the 0x13 field-0 reading) must not change any tier decision in the
 * default build: two guardians, identical inputs, one with core_offset +1 and a reading every few hours. */
static void property_reading_display_only(int nseq) {
  static hg_guardian_t A, B;
  long diff = 0, disp = 0, steps = 0, alarms = 0;
  for (int sq = 0; sq < nseq; sq++) {
    hg2_profile_t p = { ur(60, 90), (float)(xr() & 1), ur(20, 34), (uint8_t)(xr() & 15) };
    hg2_twin_t ta; memset(&ta, 0, sizeof ta); ta.rest_hr = ur(50, 85); ta.k_person = 0.12f; ta.c_bodyheat = 0.15f;
    for (int h = 0; h < 24; h++) ta.t1_night_base[h] = NAN;
    hg2_twin_t tb = ta; tb.core_offset = 1.0f;
    hg_guardian_init(&A, &p, &ta); hg_guardian_init(&B, &p, &tb);
    int len = 120 + (int)(xr() % 360); uint16_t mod = (uint16_t)(xr() % 1440);
    float hr = ur(60, 120), tair = ur(26, 44), rh = ur(15, 80);
    for (int t = 0; t < len; t++) {
      hg_minute_t m; memset(&m, 0, sizeof m);
      hr += ur(-6, 6.5f); if (hr < 45) hr = 45; if (hr > 195) hr = 195;
      tair += ur(-0.4f, 0.42f); if (tair < 18) tair = 18; if (tair > 46) tair = 46;
      m.s.minute_of_day = mod; m.s.t1_c = ur(33, 36); m.s.t2_c = m.s.t1_c - ur(0, 2); m.s.t_air_c = tair; m.s.rh_pct = rh; m.s.hr_bpm = hr;
      m.s.hr_quality = 4; m.s.pi_pct = 0.6f; m.s.a_std_g = (xr() % 3) ? ur(0, 0.002f) : ur(0, 0.2f);
      for (int k = 0; k < 12; k++) { m.t1_5s[k] = m.s.t1_c; m.t2_5s[k] = m.s.t2_c; m.tair_5s[k] = tair; m.zangle_5s[k] = ur(-30, 30); }
      m.a_peak_g = 1.1f; m.ppg_dc = 100000; m.vbat = 3.9f; m.ble_bucket = -1; m.force_worn = 2; m.button = (xr() % 100) < 3 ? 1 : 0;
      if (t % 180 == 30) { hg_cmd_t c; memset(&c, 0, sizeof c); c.op = HG_CMD_PROFILE; c.field = 0; c.value = 38.0f; hg_guardian_cmd(&B, &c); }
      hg_minute_out_t oa, ob; hg_guardian_step(&A, &m, &oa); hg_guardian_step(&B, &m, &ob); steps++;
      if (oa.state != ob.state || oa.level != ob.level || oa.tiers != ob.tiers || oa.family_alert != ob.family_alert || oa.check_reason != ob.check_reason) diff++;
      if (oa.tiers) alarms++;
      if (fabsf(ob.core.core_now - oa.core.core_now - 1.0f) < 1e-3f) disp++;
      mod = (uint16_t)((mod + 1) % 1440);
    }
  }
  printf("     M4.3 run: %d pairs, %ld minutes, %ld with a tier on, %ld minutes where the display shows +1 C\n", nseq, steps, alarms, disp);
  report("M4.3: +1 C reading changes no tier decision (default)", HG_TWIN_READING_MODE || (diff == 0 && alarms > 0 && disp == steps), "%.0f differing minutes", (double)diff);
}

/* [B2-fix] + M11.3 + M12: OOD guard at HR 150 / 180 / 200 in a 24 C room (no heat context except OOD). B2: above HR 180 the NN
 * core/logit_p385 FALL with rising HR, so the tiers must read max(NN, v1.2) and the v1.2 DRINK ceiling must stay armed (OOD
 * opens the M12 gate). Control at HR 95 (not OOD): the gated v1.2 path must not raise DRINK in that cool, dry room. */
static void ood_run(float hr, int len, hg2_aux_t *last_aux, hg2_out_t *last_core, int *drink_any, int *cool_last) {
  static hg_guardian_t g; hg2_profile_t p = { 75.0f, 0.0f, 26.0f, 0 }; hg2_twin_t tw; memset(&tw, 0, sizeof tw);
  tw.rest_hr = 70.0f; tw.k_person = 0.12f; tw.c_bodyheat = 0.15f; for (int h = 0; h < 24; h++) tw.t1_night_base[h] = NAN;
  hg_guardian_init(&g, &p, &tw); g.hg2_dbg = last_aux; *drink_any = 0;
  for (int t = 0; t < len; t++) {
    hg_minute_t m; memset(&m, 0, sizeof m);
    m.s.minute_of_day = (uint16_t)(600 + t); m.s.t1_c = 34.5f; m.s.t2_c = 33.5f; m.s.t_air_c = 24.0f; m.s.rh_pct = 40.0f;
    m.s.hr_bpm = hr; m.s.hr_quality = 4; m.s.pi_pct = 0.6f; m.s.a_std_g = 0.15f;
    for (int k = 0; k < 12; k++) { m.t1_5s[k] = 34.5f; m.t2_5s[k] = 33.5f; m.tair_5s[k] = 24.0f; m.zangle_5s[k] = 0.0f; }
    m.a_peak_g = 1.1f; m.ppg_dc = 100000; m.vbat = 3.9f; m.ble_bucket = -1; m.force_worn = 2;
    hg_minute_out_t o; hg_guardian_step(&g, &m, &o);
    if (o.tiers & 1u) *drink_any = 1;
    *last_core = o.core; *cool_last = (o.tiers >> 1) & 1u;
  }
}
static void test_ood_guard(void) {
  const float hrs[3] = { 150.0f, 180.0f, 200.0f }; float nn[3], v12[3]; int ok = 1;
  for (int i = 0; i < 3; i++) {
    hg2_aux_t a; hg2_out_t c; int d, cl; ood_run(hrs[i], 60, &a, &c, &d, &cl);
    nn[i] = a.core20_noff; v12[i] = a.v12_f20;
    const int ood = a.x[14] > HG_OOD_RESERVE || a.x[10] > HG_OOD_HR;
    const float f20a = (ood && v12[i] > nn[i]) ? v12[i] : nn[i];
    printf("     OOD HR %3.0f: NN f20 %.3f  v1.2 f20 %.3f  tiers read %.3f  ood=%d  DRINK=%d  COOL=%d  env_above_old=%d\n",
           (double)hrs[i], (double)nn[i], (double)v12[i], (double)f20a, ood, d, cl, a.env_above_old);
    ok = ok && ood && !a.env_above_old && (v12[i] < HG_T_DRINK - HG_M_TOTAL_CAP || d) && (f20a < HG_T_COOL + 0.05f || cl)
         && c.core_20 >= 30.0f && c.core_20 <= 45.0f && c.sd_20 >= 0.0f && c.sd_20 <= 3.0f;
  }
  ok = ok && v12[2] >= v12[1] && v12[1] >= v12[0];      /* the protected v1.2 path is monotone in HR */
  { hg2_aux_t a; hg2_out_t c; int d, cl; ood_run(95.0f, 60, &a, &c, &d, &cl);
    printf("     control HR 95: v1.2 f20 %.3f ood=%d DRINK=%d (gate closed: 24 C, below the older line)\n", (double)a.v12_f20,
           a.x[14] > HG_OOD_RESERVE || a.x[10] > HG_OOD_HR, d);
    ok = ok && !(a.x[14] > HG_OOD_RESERVE || a.x[10] > HG_OOD_HR) && (!HG_V12_CTX || !d); }
  report("OOD guard HR 150/180/200: tiers read max(NN, v1.2), M12 gate open, DRINK armed", ok, "%.0f", 0.0);
}
/* [B2-fix] input guards: +-inf / out-of-range inputs behave exactly like NaN; outputs stay finite and bounded */
static void test_input_guards(void) {
  static hg_guardian_t A, B; hg2_profile_t p = { 75.0f, 0.0f, 26.0f, 0 }; hg2_twin_t tw; memset(&tw, 0, sizeof tw);
  tw.rest_hr = 70.0f; tw.k_person = 0.12f; tw.c_bodyheat = 0.15f; for (int h = 0; h < 24; h++) tw.t1_night_base[h] = NAN;
  hg_guardian_init(&A, &p, &tw); hg_guardian_init(&B, &p, &tw);
  const float bad[6] = { INFINITY, -INFINITY, 1e30f, -1e30f, 200.0f, -100.0f };
  int diff = 0, unbounded = 0;
  for (int t = 0; t < 400; t++) {
    hg_minute_t m; memset(&m, 0, sizeof m);
    m.s.minute_of_day = (uint16_t)((480 + t) % 1440); m.s.t1_c = 35.0f; m.s.t2_c = 34.0f; m.s.t_air_c = 33.0f; m.s.rh_pct = 50.0f;
    m.s.hr_bpm = 90.0f; m.s.hr_quality = 4; m.s.pi_pct = 0.6f; m.s.a_std_g = 0.05f;
    for (int k = 0; k < 12; k++) { m.t1_5s[k] = 35.0f; m.t2_5s[k] = 34.0f; m.tair_5s[k] = 33.0f; }
    m.a_peak_g = 1.1f; m.ppg_dc = 100000; m.vbat = 3.9f; m.ble_bucket = -1; m.force_worn = 2;
    hg_minute_t mb = m, ma = m;
    if (t % 7 == 3) { int f = (t / 7) % 7; const float v = (f == 6 && bad[t % 6] == 200.0f) ? 1e30f : bad[t % 6];   /* HR 200 is a valid HR */
      float *pa = f == 0 ? &ma.s.t1_c : f == 1 ? &ma.s.t2_c : f == 2 ? &ma.s.t_air_c : f == 3 ? &ma.s.rh_pct : f == 4 ? &ma.s.pi_pct : f == 5 ? &ma.s.a_std_g : &ma.s.hr_bpm;
      float *pb = f == 0 ? &mb.s.t1_c : f == 1 ? &mb.s.t2_c : f == 2 ? &mb.s.t_air_c : f == 3 ? &mb.s.rh_pct : f == 4 ? &mb.s.pi_pct : f == 5 ? &mb.s.a_std_g : &mb.s.hr_bpm;
      *pa = v; *pb = NAN; }
    hg_minute_out_t oa, ob; hg_guardian_step(&A, &ma, &oa); hg_guardian_step(&B, &mb, &ob);
    { const float *fa = &oa.core.core_now, *fb = &ob.core.core_now; int d = 0;   /* field-wise (NaN == NaN), not memcmp (padding) */
      const float va[] = { oa.core.core_now, oa.core.core_20, oa.core.sd_now, oa.core.sd_20, oa.core.logit_p38, oa.core.logit_p385, oa.core.strain, oa.core.kf };
      const float vb[] = { ob.core.core_now, ob.core.core_20, ob.core.sd_now, ob.core.sd_20, ob.core.logit_p38, ob.core.logit_p385, ob.core.strain, ob.core.kf };
      (void)fa; (void)fb;
      for (int q = 0; q < 8; q++) if (!(va[q] == vb[q] || (va[q] != va[q] && vb[q] != vb[q]))) d = 1;
      if (d || oa.tiers != ob.tiers || oa.state != ob.state || oa.core.valid != ob.core.valid || oa.why != ob.why
          || memcmp(oa.status, ob.status, sizeof oa.status) != 0) diff++; }
    if (!(oa.core.core_now >= 30.0f && oa.core.core_now <= 45.0f && oa.core.sd_now >= 0.0f && oa.core.sd_now <= 3.0f
          && oa.core.logit_p385 >= -100.0f && oa.core.logit_p385 <= 100.0f)) unbounded++;
  }
  printf("     guards: %d differing, %d unbounded\n", diff, unbounded);
  report("[B2-fix] input guards: inf / out-of-range == NaN, outputs bounded", diff == 0 && (HG2_WEIGHTS_STUB || unbounded == 0), "%.0f differing minutes", (double)(diff + unbounded));
}

/* T5 D4: a DANGER CHECK must keep counting when the band comes off: family at CHECK minute HG_FAMILY_DANGER_MIN as if no press
 * (a press while off is not accepted), screen «Φορέστε το βραχιόλι». Before the fix the countdown froze (no family for hours). */
static void test_check_band_off(void) {
  static hg_guardian_t g; hg2_profile_t p = { 75.0f, 0.0f, 26.0f, 0 }; hg2_twin_t tw; memset(&tw, 0, sizeof tw);
  tw.rest_hr = 70.0f; tw.k_person = 0.12f; tw.c_bodyheat = 0.15f; for (int h = 0; h < 24; h++) tw.t1_night_base[h] = NAN;
  hg_guardian_init(&g, &p, &tw);
  int check_start = -1, fam_t = -1, scr_ok = 1, t_off = -1;
  for (int t = 0; t < 200; t++) {
    hg_minute_t m; memset(&m, 0, sizeof m);
    m.s.minute_of_day = (uint16_t)(600 + t); m.s.t1_c = 35.0f; m.s.t2_c = 34.0f; m.s.t_air_c = 30.0f; m.s.rh_pct = 30.0f;
    m.s.hr_bpm = 178.0f; m.s.hr_quality = 4; m.s.pi_pct = 0.6f; m.s.a_std_g = 0.05f;
    for (int k = 0; k < 12; k++) { m.t1_5s[k] = 35.0f; m.t2_5s[k] = 34.0f; m.tair_5s[k] = 30.0f; }
    m.a_peak_g = 1.1f; m.ppg_dc = 100000; m.vbat = 3.9f; m.ble_bucket = -1;
    m.force_worn = (check_start >= 0 && t >= check_start + 2) ? 0 : 2;          /* band off at CHECK minute 2 */
    if (check_start >= 0 && t == check_start + 3) m.button = 1;                 /* a press while off: not accepted */
    hg_minute_out_t o; hg_guardian_step(&g, &m, &o);
    if (check_start < 0 && o.check_min == 0 && (o.check_reason & 1u)) check_start = t;
    if (m.force_worn == 0 && t_off < 0) t_off = t;
    if (m.force_worn == 0 && o.check_min != 0xFF && o.screen != HG_SCR_NOT_WORN) scr_ok = 0;
    if (fam_t < 0 && o.family_alert) fam_t = t;
  }
  printf("     band off during DANGER CHECK: CHECK at %d, off at %d, family at %d (expect CHECK + %d)\n", check_start, t_off, fam_t, HG_FAMILY_DANGER_MIN);
  report("T5 D4: CHECK keeps counting with the band off; family as if no press; «Φορέστε το βραχιόλι»",
         check_start >= 0 && fam_t == check_start + HG_FAMILY_DANGER_MIN && scr_ok, "%.0f", 0.0);
}
/* T5 m1: a backward clock step (phone re-sync 14:40 -> 13:00) is not midnight: the calm baseline must not take a partial day */
static void test_clock_back_not_midnight(void) {
  static hg_guardian_t g; hg2_profile_t p = { 75.0f, 0.0f, 26.0f, 0 }; hg2_twin_t tw; memset(&tw, 0, sizeof tw);
  tw.rest_hr = 70.0f; tw.k_person = 0.12f; tw.c_bodyheat = 0.15f; for (int h = 0; h < 24; h++) tw.t1_night_base[h] = NAN;
  hg_guardian_init(&g, &p, &tw);
  uint16_t mod = 480; int ok = 1;
  for (int t = 0; t < 600; t++) {
    hg_minute_t m; memset(&m, 0, sizeof m);
    if (t == 400) mod = (uint16_t)(mod - 100);                                     /* clock steps back 100 min */
    m.s.minute_of_day = mod; m.s.t1_c = 34.0f; m.s.t2_c = 33.0f; m.s.t_air_c = 26.0f; m.s.rh_pct = 50.0f; m.s.hr_bpm = 70.0f;
    m.s.hr_quality = 4; m.s.pi_pct = 0.6f; m.s.a_std_g = 0.001f;
    for (int k = 0; k < 12; k++) { m.t1_5s[k] = 34.0f; m.t2_5s[k] = 33.0f; m.tair_5s[k] = 26.0f; }
    m.a_peak_g = 1.1f; m.ppg_dc = 100000; m.vbat = 3.9f; m.ble_bucket = -1; m.force_worn = 2;
    hg_minute_out_t o; hg_guardian_step(&g, &m, &o);
    if (g.a_base_n != 0) ok = 0;
    mod = (uint16_t)((mod + 1) % 1440);
  }
  report("T5 m1: backward clock step is not midnight (calm baseline not updated)", ok, "%.0f", 0.0);
}

static void crafted_traces(const char *dir) {
  char lst[512]; snprintf(lst, sizeof lst, "%s/traces/LIST.txt", dir);
  FILE *f = fopen(lst, "r");
  if (!f) { report("crafted traces (tests/traces/LIST.txt)", 0, "%.0f missing", 0.0); return; }
  char name[256];
  while (fscanf(f, "%255s", name) == 1) {
    char p[800]; snprintf(p, sizeof p, "%s/traces/%s", dir, name);
    int bad = 0; int rows = replay(p, NULL, 1, &bad);
    char nm[300]; snprintf(nm, sizeof nm, "trace %s", name);
    report(nm, rows > 0 && bad == 0, "%.0f mismatching minutes", (double)bad);
  }
  fclose(f);
}

int main(int argc, char **argv) {
  if (argc >= 4 && !strcmp(argv[1], "replay")) { int r = replay(argv[2], argv[3], 0, NULL); return r < 0; }
  if (argc >= 3 && !strcmp(argv[1], "check")) { int bad = 0; int r = replay(argv[2], NULL, 1, &bad); printf("%d rows, %d mismatches\n", r, bad); return bad != 0; }
  const char *tests = argc >= 2 ? argv[1] : "../tests";
  char p[512];
  printf("Heat Guardian guardian/c host tests (weights %s, stub=%d)\n", HG2_NN_VERSION, HG2_WEIGHTS_STUB);
  test_sizes();
  snprintf(p, sizeof p, "%s/crc8_vectors.txt", tests); test_crc8(p);
  snprintf(p, sizeof p, "%s/ble_vectors.txt", tests); test_ble_vectors(p);
  test_weights_crc(); test_luts(); test_frames(); test_routine_pack(); test_calm_api();
  test_ood_guard(); test_input_guards(); test_check_band_off(); test_clock_back_not_midnight();
  property_tests(argc >= 3 ? atoi(argv[2]) : 10000);
  property_nn_monotone(argc >= 3 ? atoi(argv[2]) : 10000);
  property_m19_long(argc >= 3 ? (atoi(argv[2]) / 100 > 4 ? atoi(argv[2]) / 100 : 4) : 100);
  property_reading_display_only(argc >= 3 ? atoi(argv[2]) / 4 : 2500);
  test_m19_nan_state(argc >= 3 ? (atoi(argv[2]) / 1000 > 4 ? atoi(argv[2]) / 1000 : 4) : 10);
  crafted_traces(tests);
  printf("%d passed, %d failed\n", n_pass, n_fail);
  return n_fail;
}
