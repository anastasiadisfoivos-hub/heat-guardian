/* Host test for hg_twin (B3). Build: make -C twin/c test
 * 1. golden replay: twin/tests/golden_events.csv -> parameters after every nightly update vs the Python
 *    reference (golden_expected.csv), tolerance 1e-5, plus t1_n / t1_pre_cd exact, changed/frozen exact
 * 2. final file: pack() byte-identical to Python to_bytes() (golden_final.hex), CRC == zlib.crc32
 * 3. pack/unpack round trip byte-identical; every single-byte flip and every truncation -> unpack fails -> defaults
 * 4. fuzz: 10,000 random minutes (+ random readings, room readings, nightly updates) with NaN/inf/out-of-range
 *    -> every parameter always inside its bounds, never NaN (t1_night_base: NaN or inside 25..42)
 * 5. decay half-life: two nightly updates halve core_offset (|ratio - 0.5| < 1e-6)
 * 6. sizes: sizeof(hg_twin_acc_t) <= 256, sizeof(hg2_twin_t) reported, struct layout == ARCHITECTURE 4.5 */
#include "hg_twin.h"
#include <math.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int fails = 0;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL: " __VA_ARGS__); printf("\n"); } } while (0)

static float pf(const char *s) { return strtof(s, NULL); }  /* handles nan, inf, -inf */

static void params_vec(const hg2_twin_t *t, float v[30])
{
  v[0] = t->rest_hr; v[1] = t->k_person; v[2] = t->core_offset; v[3] = t->c_bodyheat;
  for (int h = 0; h < 24; h++) v[4 + h] = t->t1_night_base[h];
  v[28] = (float)t->days_learned;
  v[29] = 0.0f;
}

static int in_bounds(const hg2_twin_t *t)
{
  if (!(isfinite(t->rest_hr) && t->rest_hr >= 40.0f && t->rest_hr <= 100.0f)) return 0;
  if (!(isfinite(t->k_person) && t->k_person >= 0.03f && t->k_person <= HG_TWIN_K_MAX)) return 0;
  if (!(isfinite(t->core_offset) && t->core_offset >= -0.8f && t->core_offset <= 0.8f)) return 0;
  if (!(isfinite(t->c_bodyheat) && t->c_bodyheat >= 0.0f && t->c_bodyheat <= 0.4f)) return 0;
  for (int h = 0; h < 24; h++) {
    float b = t->t1_night_base[h];
    if (!isnan(b) && !(isfinite(b) && b >= 25.0f && b <= 42.0f)) return 0;
  }
  return 1;
}

static int split(char *line, char **tok, int max)
{
  int n = 0; char *p = line;
  while (n < max) {
    tok[n++] = p;
    char *c = strchr(p, ',');
    if (!c) break;
    *c = 0; p = c + 1;
  }
  char *nl = strchr(tok[n - 1], '\n'); if (nl) *nl = 0;
  return n;
}

static hg2_twin_t g_tw; static hg_twin_acc_t g_acc; static int g_interior_k = 0;

static const char *g_prefix = "golden";
static void test_golden(const char *dir)
{
  char path[512], line[2048], eline[4096];
  snprintf(path, sizeof path, "%s/%s_events.csv", dir, g_prefix);
  FILE *fe = fopen(path, "r");
  snprintf(path, sizeof path, "%s/%s_expected.csv", dir, g_prefix);
  FILE *fx = fopen(path, "r");
  if (!fe || !fx) { CHECK(0, "golden files missing in %s", dir); if (fe) fclose(fe); if (fx) fclose(fx); return; }
  hg_twin_defaults(&g_tw); hg_twin_acc_init(&g_acc);
  int nupd = 0; double maxerr = 0.0; long nmin = 0;
  while (fgets(line, sizeof line, fe)) {
    char *t[32]; int n = split(line, t, 32);
    if (n < 21) { CHECK(0, "bad event line"); continue; }
    char k = t[0][0];
    if (k == 'm') {
      hg2_in_t in;
      memset(&in, 0, sizeof in);
      in.t1_c = pf(t[1]); in.t2_c = pf(t[2]); in.t_air_c = pf(t[3]); in.rh_pct = pf(t[4]); in.hr_bpm = pf(t[5]);
      in.hr_quality = (uint8_t)atoi(t[6]); in.pi_pct = pf(t[7]); in.a_std_g = pf(t[8]); in.worn = (uint8_t)atoi(t[9]);
      in.minute_of_day = (uint16_t)atol(t[10]);
      hg_twin_note_tier(&g_acc, (uint8_t)atoi(t[14]));
      hg_twin_set_air_ref(&g_acc, pf(t[15]));
      hg_twin_ingest_minute(&g_acc, &in, (uint8_t)atoi(t[11]), (uint8_t)atoi(t[12]), (uint8_t)atoi(t[13]));
      nmin++;
    } else if (k == 'r') {
      hg_twin_ingest_reading(&g_acc, pf(t[16]), pf(t[17]), pf(t[18]), pf(t[19]), (uint8_t)atoi(t[20]) ? 1 : 0);
      hg_twin_commit_reading(&g_tw, &g_acc);
    } else if (k == 'q') {
      hg_twin_ingest_room_reading(&g_acc, pf(t[16]), pf(t[17]), pf(t[18]));
    } else if (k == 'u') {
      int ch = hg_twin_nightly_update(&g_tw, &g_acc);
      if (!fgets(eline, sizeof eline, fx)) { CHECK(0, "expected file too short"); break; }
      char *x[96]; int nx = split(eline, x, 96);
      CHECK(nx == 2 + 29 + 48, "expected line has %d fields", nx);
      CHECK(ch == atoi(x[0]), "night %d changed C=%d Py=%s", nupd, ch, x[0]);
      CHECK(g_acc.last_frozen == atoi(x[1]), "night %d frozen C=%d Py=%s", nupd, g_acc.last_frozen, x[1]);
      float v[30]; params_vec(&g_tw, v);
      for (int i = 0; i < 29; i++) {
        float e = pf(x[2 + i]);
        if (isnan(e) || isnan(v[i])) { CHECK(isnan(e) && isnan(v[i]), "night %d param %d C=%g Py=%g", nupd, i, (double)v[i], (double)e); continue; }
        double d = fabs((double)v[i] - (double)e);
        if (d > maxerr) maxerr = d;
        CHECK((float)d <= 1e-5f, "night %d param %d C=%.9g Py=%.9g", nupd, i, (double)v[i], (double)e);
      }
      for (int h = 0; h < 24; h++) {
        CHECK(g_acc.t1_n[h] == atoi(x[31 + h]), "night %d t1_n[%d]", nupd, h);
        CHECK(g_acc.t1_pre_cd[h] == atoi(x[55 + h]), "night %d t1_pre_cd[%d]", nupd, h);
      }
      CHECK(in_bounds(&g_tw), "night %d out of bounds", nupd);
      if (g_tw.k_person > 0.0301f && g_tw.k_person < HG_TWIN_K_MAX - 0.0001f && g_tw.k_person != 0.12f) g_interior_k = 1;
      nupd++;
    }
  }
  fclose(fe); fclose(fx);
  printf("golden: %ld minutes, %d nightly updates, max |C - Py| = %.3g\n", nmin, nupd, maxerr);
  CHECK(nupd == 10, "expected 10 nightly updates, got %d", nupd);
  CHECK(g_interior_k || HG_TWIN_K_RULE == 2 || HG_TWIN_READING_MODE == 0 || strstr(g_prefix, "sim"), "F6 golden never exercised an interior K value");

  /* final file byte-identical with Python (same routine stand-in, save_count 10) */
  uint8_t rout[624];
  for (int i = 0; i < 512; i++) rout[i] = (uint8_t)(i & 255);
  memset(rout + 512, 0, 112);
  hg_twin_set_calm(&g_acc, 37.21f, 4);   /* M9.5 calm block, same as make_golden.py */
  hg_twin_set_exc(&g_acc, 1234.5f, -56.25f);   /* B5-v7 Exception block (v4), same as make_golden.py */
  uint8_t buf[900]; int len = hg_twin_pack(&g_tw, &g_acc, rout, 624, 10, buf, sizeof buf);
  snprintf(path, sizeof path, "%s/%s_final.hex", dir, g_prefix);
  FILE *fh = fopen(path, "r");
  static char hex[4096];
  if (!fh || !fgets(hex, sizeof hex, fh)) { CHECK(0, "golden_final.hex missing"); if (fh) fclose(fh); return; }
  fclose(fh);
  int hl = (int)strcspn(hex, "\r\n");
  CHECK(hl == 2 * len, "file length C=%d Py=%d", len, hl / 2);
  int diff = 0;
  for (int i = 0; i < len && 2 * i + 1 < hl; i++) {
    unsigned b; sscanf(hex + 2 * i, "%2x", &b);
    if (b != buf[i]) diff++;
  }
  CHECK(diff == 0, "packed file differs from Python in %d bytes", diff);
  printf("pack: %d B (routine 624 B), byte-identical with Python: %s\n", len, diff ? "NO" : "yes");
}

static void test_roundtrip_and_corruption(void)
{
  uint8_t rout[624], rout2[700], buf[900], buf2[900];
  for (int i = 0; i < 624; i++) rout[i] = (uint8_t)(i * 7 + 3);
  int len = hg_twin_pack(&g_tw, &g_acc, rout, 624, 1234, buf, sizeof buf);
  CHECK(len == 838, "pack length %d (v4: 830 + 8 B Exception block)", len);
  hg2_twin_t t; hg_twin_acc_t a; uint16_t rl; uint32_t sc;
  int r = hg_twin_unpack(buf, (uint16_t)len, &t, &a, rout2, sizeof rout2, &rl, &sc);
  CHECK(r == 0 && rl == 624 && sc == 1234 && memcmp(rout, rout2, 624) == 0, "unpack failed r=%d", r);
  int len2 = hg_twin_pack(&t, &a, rout2, rl, sc, buf2, sizeof buf2);
  CHECK(len2 == len && memcmp(buf, buf2, (size_t)len) == 0, "round trip not byte-identical");
  /* CRC vs zlib known vector: crc32("123456789") = 0xCBF43926 */
  CHECK(hg_twin_crc32(0, "123456789", 9) == 0xCBF43926u, "crc32 check value");
  /* every single-byte flip (all 8 single-bit flips of every byte) must be rejected */
  int accepted = 0, defaults_ok = 1;
  for (int i = 0; i < len; i++)
    for (int bit = 0; bit < 8; bit++) {
      memcpy(buf2, buf, (size_t)len);
      buf2[i] ^= (uint8_t)(1u << bit);
      if (hg_twin_unpack(buf2, (uint16_t)len, &t, &a, rout2, sizeof rout2, &rl, &sc) == 0) accepted++;
      else if (!(t.rest_hr == 70.0f && t.k_person == 0.12f && t.core_offset == 0.0f && t.c_bodyheat == 0.15f &&
                 isnan(t.t1_night_base[0]) && t.days_learned == 0 && rl == 0 && sc == 0)) defaults_ok = 0;
    }
  CHECK(accepted == 0, "%d corrupted files accepted", accepted);
  CHECK(defaults_ok, "corrupted file did not yield defaults");
  int trunc_ok = 1;
  for (int l = 0; l < len; l++) if (hg_twin_unpack(buf, (uint16_t)l, &t, &a, rout2, sizeof rout2, &rl, &sc) == 0) trunc_ok = 0;
  CHECK(trunc_ok, "truncated file accepted");
  CHECK(hg_twin_pack(&g_tw, &g_acc, rout, 700, 0, buf, sizeof buf) == -1, "901-B file must be refused");
  CHECK(hg_twin_pack(&g_tw, &g_acc, rout, 600, 0, buf, 100) == -1, "small buffer must be refused");
  /* CRC-valid file with an out-of-bounds value -> rejected */
  hg2_twin_t bad = g_tw; bad.k_person = HG_TWIN_K_MAX + 0.5f;
  len = hg_twin_pack(&bad, &g_acc, NULL, 0, 0, buf, sizeof buf);
  CHECK(hg_twin_unpack(buf, (uint16_t)len, &t, &a, NULL, 0, &rl, &sc) < 0, "out-of-bounds K accepted");
  printf("file: round trip identical, %d x 8 bit flips + %d truncations all rejected -> defaults\n", 830, 830);
}

static uint32_t rs = 12345u;
static uint32_t rnd(void) { rs ^= rs << 13; rs ^= rs >> 17; rs ^= rs << 5; return rs; }
static float urand(float lo, float hi) { return lo + (hi - lo) * (float)(rnd() & 0xFFFFFF) / 16777216.0f; }
static float wild(float lo, float hi)
{
  switch (rnd() % 8) {
    case 0: return NAN;
    case 1: return INFINITY;
    case 2: return -INFINITY;
    case 3: return urand(-1e30f, 1e30f);
    case 4: return urand(-200.0f, 200.0f);
    default: return urand(lo, hi);
  }
}

static void test_fuzz(void)
{
  hg2_twin_t t; hg_twin_acc_t a;
  hg_twin_defaults(&t); hg_twin_acc_init(&a);
  int bad = 0, nupd = 0;
  for (int i = 0; i < 10000; i++) {
    hg2_in_t in;
    in.t1_c = wild(25, 40); in.t2_c = wild(20, 38); in.t_air_c = wild(15, 40); in.rh_pct = wild(0, 100);
    in.hr_bpm = wild(35, 120); in.hr_quality = (uint8_t)rnd(); in.pi_pct = wild(0, 3); in.a_std_g = wild(0, 0.004f);
    in.worn = (uint8_t)(rnd() % 4 == 0 ? rnd() : 2u); in.minute_of_day = (uint16_t)(rnd() % 3 == 0 ? rnd() : rnd() % 1440u);
    hg_twin_note_tier(&a, (uint8_t)(rnd() % 50 == 0));
    hg_twin_set_air_ref(&a, wild(15, 40));
    hg_twin_ingest_minute(&a, &in, (uint8_t)(rnd() % 2 ? rnd() : 0u), (uint8_t)(rnd() % 3), (uint8_t)(rnd() % 2));
    if (rnd() % 200 == 0) { hg_twin_ingest_reading(&a, wild(35, 39), wild(30, 37), wild(-1, 6), wild(35, 39), (uint8_t)rnd()); hg_twin_commit_reading(&t, &a); }
    if (rnd() % 300 == 0) hg_twin_ingest_room_reading(&a, wild(15, 40), wild(15, 40), wild(25, 40));
    if (rnd() % 150 == 0) { hg_twin_nightly_update(&t, &a); nupd++; }
    if (!in_bounds(&t)) bad++;
  }
  hg_twin_nightly_update(&t, &a);
  if (!in_bounds(&t)) bad++;
  /* corrupt RAM twin: sanitised on the next update */
  t.rest_hr = NAN; t.k_person = INFINITY; t.core_offset = -5.0f; t.c_bodyheat = NAN; t.t1_night_base[3] = INFINITY;
  hg_twin_nightly_update(&t, &a);
  if (!in_bounds(&t)) bad++;
  CHECK(bad == 0, "fuzz: %d minutes with a parameter out of bounds", bad);
  printf("fuzz: 10000 random minutes, %d nightly updates, out-of-bounds minutes = %d\n", nupd, bad);
}

/* ---- [B3-fix] regressions for tests/B3_TEST_REPORT.md ---- */
static void put16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static void recrc(uint8_t *buf, int len)
{
  uint32_t c = hg_twin_crc32(0, buf, (uint32_t)len - 4u);
  for (int i = 0; i < 4; i++) buf[len - 4 + i] = (uint8_t)(c >> (8 * i));
}

static void test_fixes(void)
{
  hg2_twin_t t; hg_twin_acc_t a;
  /* F2/F4: clock stuck in hour 3 for 1000 (x3 nights) and 3000 minutes */
  for (int pass = 0; pass < 2; pass++) {
    int stuck = pass ? 3000 : 1000, nights = pass ? 1 : 3, bad = 0;
    hg_twin_defaults(&t); hg_twin_acc_init(&a);
    for (int d = 0; d < nights; d++) {
      for (int i = 0; i < 1440; i++) {
        uint16_t tod = (uint16_t)((210 + i) % 1440);
        hg2_in_t in = {33.0f, NAN, 29.0f, 45.0f, 55.0f, 4, 0.8f, 0.001f, 2, tod};
        hg_twin_ingest_minute(&a, &in, (uint8_t)(tod >= 1380 || tod < 420), 0, 1);
      }
      for (int i = 0; i < stuck; i++) {
        hg2_in_t in = {33.0f, NAN, 24.0f, 45.0f, 55.0f, 4, 0.8f, 0.001f, 2, 200};
        hg_twin_ingest_minute(&a, &in, 1, 0, 1);
      }
      hg_twin_nightly_update(&t, &a);
      if (!in_bounds(&t)) bad++;
    }
    if (pass == 0) CHECK(bad == 0 && fabsf(t.t1_night_base[3] - 33.0f) < 0.006f, "F2 stuck clock base[3] = %g", (double)t.t1_night_base[3]);
    else CHECK(a.t1_pre_cd[3] == 3300, "F4 stuck 3000 min pre_cd = %d", a.t1_pre_cd[3]);
  }
  /* F3: CRC-valid files with an inconsistent learning state are rejected */
  const struct { uint8_t n; int16_t pre; float base; } cs[4] = {
    {1, HG_TWIN_CD_NONE, NAN}, {0, 3300, NAN}, {2, -3, NAN}, {3, 3300, 33.0f}};
  for (int k = 0; k < 4; k++) {
    hg_twin_defaults(&t); hg_twin_acc_init(&a);
    uint8_t buf[900];
    int len = hg_twin_pack(&t, &a, NULL, 0, 0, buf, sizeof buf);
    buf[121 + 5] = cs[k].n;
    put16(buf + 145 + 2 * 5, (uint16_t)cs[k].pre);
    uint32_t u; memcpy(&u, &cs[k].base, 4);
    for (int i = 0; i < 4; i++) buf[8 + 16 + 4 * 5 + i] = (uint8_t)(u >> (8 * i));
    recrc(buf, len);
    hg2_twin_t t2; hg_twin_acc_t a2; uint16_t rl; uint32_t sc;
    CHECK(hg_twin_unpack(buf, (uint16_t)len, &t2, &a2, NULL, 0, &rl, &sc) < 0, "F3 inconsistent state case %d accepted", k);
  }
  /* F3: inconsistent RAM state is repaired by the next update */
  hg_twin_defaults(&t); hg_twin_acc_init(&a);
  a.t1_n[5] = 1; a.t1_pre_cd[5] = HG_TWIN_CD_NONE;
  hg_twin_nightly_update(&t, &a);
  CHECK(a.t1_n[5] == 0 && a.t1_pre_cd[5] == HG_TWIN_CD_NONE, "F3 RAM state not repaired");
  printf("fixes: stuck clock (1000x3, 3000 min), 4 inconsistent files rejected, RAM state repaired\n");
}

/* ---- [B3-M4] DECISIONS M4.2-M4.4 ---- */
static void m4_minute(hg_twin_acc_t *a, uint8_t tier)
{
  hg2_in_t in = {34.0f, 31.5f, 24.0f, 45.0f, 60.0f, 4, 0.8f, 0.001f, 2, 600};
  hg_twin_note_tier(a, tier);
  hg_twin_ingest_minute(a, &in, 0, 0, 1);
}
static int m4_read(hg2_twin_t *t, hg_twin_acc_t *a)
{
  hg_twin_ingest_reading(a, 37.0f, 34.0f, 2.5f, 36.6f, 1);
  return hg_twin_commit_reading(t, a);
}
static void test_m4(void)
{
  hg2_twin_t t; hg_twin_acc_t a;
  hg_twin_defaults(&t); hg_twin_acc_init(&a); m4_minute(&a, 0); m4_read(&t, &a);
  const float tc = 37.0f + (HG_TWIN_READING_MODE == 1 ? HG_TWIN_ORAL_TO_CORE : 0.0f);
  CHECK(fabsf(t.core_offset - HG_TWIN_BETA_OFF * (tc - 36.6f)) < 1e-6f, "M4.2 offset %g", (double)t.core_offset);
  if (HG_TWIN_READING_MODE == 0) CHECK(t.k_person == 0.12f, "M4.3 display-only reading moved the gap gain");
  hg_twin_defaults(&t); hg_twin_acc_init(&a); m4_minute(&a, 1);
  CHECK(m4_read(&t, &a) == 0 && t.core_offset == 0.0f, "M4.4 reading during a tier applied");
  for (int i = 0; i < 29; i++) m4_minute(&a, 0);
  CHECK(m4_read(&t, &a) == 0 && t.core_offset == 0.0f, "M4.4 reading 29 min after a tier applied");
  m4_minute(&a, 0); m4_minute(&a, 0);
  CHECK(m4_read(&t, &a) == 1, "M4.4 reading 31 min after a tier dropped");
  hg_twin_defaults(&t); hg_twin_acc_init(&a); m4_minute(&a, 1);
  hg_twin_ingest_reading(&a, 37.0f, 34.0f, 2.5f, 36.6f, 1); hg_twin_nightly_update(&t, &a);
  CHECK(t.core_offset == 0.0f, "M4.4 pending reading applied at the nightly update during hold-off");
  printf("M4: beta %.2f, reading mode %d, tier hold-off %u min -- checked\n", (double)HG_TWIN_BETA_OFF, HG_TWIN_READING_MODE, HG_TWIN_TIER_HOLDOFF_MIN);
}

/* ---- [B3-M9] DECISIONS M9.5: Guardian calm-f20 baseline in the save file ---- */
static void test_m9(void)
{
  hg2_twin_t t, t2; hg_twin_acc_t a, a2; uint8_t buf[900], rout[650], r2[700]; uint16_t rl; uint32_t sc; float v;
  memset(rout, 0x5A, sizeof rout);
  hg_twin_defaults(&t); hg_twin_acc_init(&a);
  CHECK(hg_twin_get_calm(&a, &v) == 0 && isnan(v), "M9 fresh calm not empty");
  hg_twin_set_calm(&a, 37.12f, 5);
  int len = hg_twin_pack(&t, &a, rout, 650, 3, buf, sizeof buf);
  CHECK(len == 864, "M9 file with 650-B routine is %d B (v4: 856 + 8 B Exception block)", len);
  CHECK(hg_twin_unpack(buf, (uint16_t)len, &t2, &a2, r2, sizeof r2, &rl, &sc) == 0 && hg_twin_get_calm(&a2, &v) == 5 && v == 37.12f,
        "M9 calm lost in pack/unpack");
  hg_twin_set_calm(&a, 39.0f, 2); CHECK(hg_twin_get_calm(&a, &v) == 2 && v == 37.7f, "M9 setter does not clamp");
  hg_twin_set_calm(&a, NAN, 4);   CHECK(hg_twin_get_calm(&a, &v) == 0 && isnan(v), "M9 NaN not emptied");
  /* inconsistent calm blocks rejected */
  const struct { float v; uint8_t n; } cs[3] = {{NAN, 3}, {38.5f, 3}, {37.0f, 0}};
  for (int k = 0; k < 3; k++) {
    hg_twin_acc_init(&a);
    len = hg_twin_pack(&t, &a, NULL, 0, 0, buf, sizeof buf);
    uint32_t u; memcpy(&u, &cs[k].v, 4);
    for (int i = 0; i < 4; i++) buf[193 + i] = (uint8_t)(u >> (8 * i));
    buf[197] = cs[k].n; recrc(buf, len);
    CHECK(hg_twin_unpack(buf, (uint16_t)len, &t2, &a2, NULL, 0, &rl, &sc) < 0, "M9 inconsistent calm case %d accepted", k);
  }
  /* version-2 file (no calm block) still loads with an empty calm */
  hg_twin_acc_init(&a); hg_twin_set_calm(&a, 37.3f, 7); t.rest_hr = 61.0f;
  len = hg_twin_pack(&t, &a, rout, 2, 9, buf, sizeof buf);
  memmove(buf + 193, buf + 206, (size_t)(len - 206)); len -= 13;   /* v4 -> v2: drop calm (5 B) + Exception (8 B) blocks */
  buf[4] = 2; buf[5] = 0; buf[6] = (uint8_t)len; buf[7] = (uint8_t)(len >> 8); recrc(buf, len);
  CHECK(hg_twin_unpack(buf, (uint16_t)len, &t2, &a2, r2, sizeof r2, &rl, &sc) == 0 && t2.rest_hr == 61.0f && rl == 2 && sc == 9 &&
        hg_twin_get_calm(&a2, &v) == 0, "M9 version-2 file not migrated");
  /* nightly Twin updates never touch the calm baseline */
  hg_twin_defaults(&t); hg_twin_acc_init(&a); hg_twin_set_calm(&a, 37.3f, 7);
  hg_twin_nightly_update(&t, &a); hg_twin_nightly_update(&t, &a);
  CHECK(hg_twin_get_calm(&a, &v) == 7 && v == 37.3f, "M9 calm changed by nightly update");
  printf("M9: calm block 5 B, 864 B (v4) with 650-B routine, 3 inconsistent blocks rejected, v2 migrates\n");
}

/* ---- [B5-v7] Guardian Exception-DRINK sums in the save file (twin v4; manager item 2) ---- */
static void test_b5v7_exc(void)
{
  hg2_twin_t t, t2; hg_twin_acc_t a, a2; uint8_t buf[900], rout[650], r2[700]; uint16_t rl; uint32_t sc; float x, y;
  memset(rout, 0x33, sizeof rout);
  hg_twin_defaults(&t); hg_twin_acc_init(&a);
  CHECK(hg_twin_get_exc(&a, &x, &y) == 0 && x == 0.0f && y == 0.0f, "B5-v7 fresh Exception sums not empty");
  hg_twin_set_exc(&a, 4321.25f, 123.5f); hg_twin_set_calm(&a, 37.25f, 3);
  int len = hg_twin_pack(&t, &a, rout, 650, 11, buf, sizeof buf);
  CHECK(len == 864 && len <= (int)HG_TWIN_FILE_MAX, "B5-v7 v4 file %d B", len);
  CHECK(hg_twin_unpack(buf, (uint16_t)len, &t2, &a2, r2, sizeof r2, &rl, &sc) == 0 && hg_twin_get_exc(&a2, &x, &y) == 1 &&
        x == 4321.25f && y == 123.5f && rl == 650 && sc == 11, "B5-v7 Exception sums lost in pack/unpack");
  /* setter rejects NaN / inf / negative sxx / out of bounds */
  const float bad[5][2] = {{NAN, 1.0f}, {1.0f, INFINITY}, {-1.0f, 0.0f}, {2.0e7f, 0.0f}, {1.0f, -2.0e7f}};
  for (int k = 0; k < 5; k++) { hg_twin_set_exc(&a, bad[k][0], bad[k][1]); CHECK(hg_twin_get_exc(&a, &x, &y) == 0 && x == 0.0f && y == 0.0f, "B5-v7 setter case %d", k); }
  /* corrupted Exception block (CRC re-made so only the bounds check can catch it) -> whole file rejected, defaults */
  for (int k = 0; k < 5; k++) {
    hg_twin_acc_init(&a); len = hg_twin_pack(&t, &a, NULL, 0, 0, buf, sizeof buf);
    uint32_t u; memcpy(&u, &bad[k][0], 4); for (int i = 0; i < 4; i++) buf[198 + i] = (uint8_t)(u >> (8 * i));
    memcpy(&u, &bad[k][1], 4); for (int i = 0; i < 4; i++) buf[202 + i] = (uint8_t)(u >> (8 * i));
    recrc(buf, len);
    CHECK(hg_twin_unpack(buf, (uint16_t)len, &t2, &a2, NULL, 0, &rl, &sc) < 0 && hg_twin_get_exc(&a2, &x, &y) == 0, "B5-v7 corrupt Exception case %d accepted", k);
  }
  /* a flipped byte without CRC repair -> rejected */
  hg_twin_acc_init(&a); hg_twin_set_exc(&a, 10.0f, 2.0f); len = hg_twin_pack(&t, &a, NULL, 0, 0, buf, sizeof buf);
  buf[200] ^= 0x40; CHECK(hg_twin_unpack(buf, (uint16_t)len, &t2, &a2, NULL, 0, &rl, &sc) == -5, "B5-v7 CRC not checked over the Exception block");
  /* version-3 file (calm, no Exception block) still loads: calm kept, Exception empty */
  hg_twin_acc_init(&a); hg_twin_set_calm(&a, 37.4f, 6); hg_twin_set_exc(&a, 99.0f, 9.0f); t.rest_hr = 63.0f;
  len = hg_twin_pack(&t, &a, rout, 3, 5, buf, sizeof buf);
  memmove(buf + 198, buf + 206, (size_t)(len - 206)); len -= 8;
  buf[4] = 3; buf[5] = 0; buf[6] = (uint8_t)len; buf[7] = (uint8_t)(len >> 8); recrc(buf, len);
  CHECK(hg_twin_unpack(buf, (uint16_t)len, &t2, &a2, r2, sizeof r2, &rl, &sc) == 0 && t2.rest_hr == 63.0f && rl == 3 && sc == 5 &&
        hg_twin_get_calm(&a2, &x) == 6 && x == 37.4f && hg_twin_get_exc(&a2, &x, &y) == 0, "B5-v7 version-3 file not migrated");
  /* nightly updates and sanitize never touch good sums; sanitize empties bad ones */
  hg_twin_defaults(&t); hg_twin_acc_init(&a); hg_twin_set_exc(&a, 50.0f, -3.0f);
  hg_twin_nightly_update(&t, &a); hg_twin_sanitize(&t, &a);
  CHECK(hg_twin_get_exc(&a, &x, &y) == 1 && x == 50.0f && y == -3.0f, "B5-v7 Exception sums changed by nightly update");
  a.exc_sxx = NAN; hg_twin_sanitize(&t, &a); CHECK(a.exc_sxx == 0.0f && a.exc_sxy == 0.0f, "B5-v7 sanitize kept NaN sums");
  printf("B5-v7: Exception block 8 B (v4 file 864 B with 650-B routine), 5 bad setter + 5 corrupt files rejected, v3 migrates\n");
}

static void test_decay(void)
{
  hg2_twin_t t; hg_twin_acc_t a;
  hg_twin_defaults(&t); hg_twin_acc_init(&a);
  t.core_offset = 0.4f;
  hg_twin_nightly_update(&t, &a); hg_twin_nightly_update(&t, &a);
  CHECK(fabsf(t.core_offset / 0.4f - 0.5f) < 1e-6f, "half-life: ratio %.8f", (double)(t.core_offset / 0.4f));
  CHECK(a.last_frozen == 2, "empty night must be frozen (no night observed)");
  CHECK(t.days_learned == 0, "frozen nights must not count as learned");
  /* K never moves without a reading, even with a full night of flux data */
  hg_twin_defaults(&t); hg_twin_acc_init(&a);
  for (int d = 0; d < 5; d++) {
    for (int i = 0; i < 1440; i++) {
      hg2_in_t in = {33.5f, 31.0f, 24.0f, 45.0f, 55.0f, 4, 0.8f, 0.001f, 2, (uint16_t)((210 + i) % 1440)};
      hg_twin_ingest_minute(&a, &in, (uint8_t)(in.minute_of_day >= 1380 || in.minute_of_day < 420), 0, 1);
    }
    hg_twin_nightly_update(&t, &a);
  }
  CHECK(t.k_person == 0.12f && t.core_offset == 0.0f, "K/offset moved without a reading");
  CHECK(!isnan(t.t1_night_base[12]) && fabsf(t.t1_night_base[12] - 33.5f) < 0.006f, "baseline hour 12 = %g", (double)t.t1_night_base[12]);
  /* flux absent (T2 = NAN -> flux_valid 0): reading must not touch K */
  hg_twin_ingest_reading(&a, 37.0f, 33.5f, NAN, 36.8f, 0);
  hg_twin_commit_reading(&t, &a);
  CHECK(t.k_person == 0.12f, "K moved on a reading without flux");
  printf("decay: 2 nights -> x%.6f; K/offset unchanged without readings; flux-absent reading leaves K\n", (double)(0.70710678f * 0.70710678f));
}

int main(int argc, char **argv)
{
  const char *dir = argc > 1 ? argv[1] : "../tests";
  if (argc > 2) g_prefix = argv[2];
  printf("gap-gain rule %d (max %.2f), beta %.2f, reading mode %d, golden set %s\n", HG_TWIN_K_RULE, (double)HG_TWIN_K_MAX, (double)HG_TWIN_BETA_OFF, HG_TWIN_READING_MODE, g_prefix);
  printf("sizeof(hg2_twin_t) = %u B (packed in file: 113 B), sizeof(hg_twin_acc_t) = %u B, sizeof(hg2_in_t) = %u B\n",
         (unsigned)sizeof(hg2_twin_t), (unsigned)sizeof(hg_twin_acc_t), (unsigned)sizeof(hg2_in_t));
  CHECK(sizeof(hg_twin_acc_t) <= 256, "acc too big");
  CHECK(offsetof(hg2_twin_t, t1_night_base) == 16 && offsetof(hg2_twin_t, days_learned) == 112, "hg2_twin_t layout drift");
  test_golden(dir);
  test_roundtrip_and_corruption();
  test_fuzz();
  test_decay();
  test_fixes();
  test_m4();
  test_m9();
  test_b5v7_exc();
  printf(fails ? "RESULT: %d FAILURES\n" : "RESULT: ALL PASS\n", fails);
  return fails ? 1 : 0;
}
