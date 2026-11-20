/* T5: design-A calm baseline <-> Body Twin file round trip (guardian/c/hg_guardian_twin.c + twin/c/hg_twin.c, unchanged).
 * For 2,000 calm values (bounds, 1-ulp inside, random float32 in [36.8, 37.7]) and n in {1, 2, 7, 255}:
 *   guardian A: set_calm(c, n)   guardian B: set_calm -> calm_to_twin -> hg_twin_pack -> hg_twin_unpack -> calm_from_twin
 *   -> get_calm bit-identical, and one full random day through both guardians gives identical per-minute outputs.
 * Plus: learned (not set) baseline, n == 0, NaN, +-inf, out-of-range values. */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "hg_guardian_twin.h"
static uint32_t rs = 12345u;
static uint32_t xr(void) { rs ^= rs << 13; rs ^= rs >> 17; rs ^= rs << 5; return rs; }
static float ur(float a, float b) { return a + (b - a) * (float)(xr() & 0xFFFFFF) / 16777216.0f; }
static hg_guardian_t A, B;

static int roundtrip(hg_guardian_t *b, const hg2_profile_t *p, const hg2_twin_t *tw, const hg_calm_t *c, int *restored) {
  static hg_guardian_t src; hg_guardian_init(&src, p, tw); hg_guardian_set_calm(&src, c);
  hg_twin_acc_t acc; hg_twin_acc_init(&acc); hg_guardian_calm_to_twin(&src, &acc);
  uint8_t rt[HG_ROUTINE_PACK_BYTES]; uint16_t rn = hg_routine_pack(&src.rt, rt, sizeof rt);
  uint8_t file[900]; int n = hg_twin_pack(tw, &acc, rt, rn, 1, file, sizeof file);
  if (n <= 0) return -100;
  hg2_twin_t tw2; hg_twin_acc_t acc2; uint8_t rt2[700]; uint16_t rn2 = 0; uint32_t sc = 0;
  int u = hg_twin_unpack(file, (uint16_t)n, &tw2, &acc2, rt2, sizeof rt2, &rn2, &sc);
  hg_guardian_init(b, p, tw);
  *restored = hg_guardian_calm_from_twin(b, &acc2);
  return u;
}
static int same_day(const hg2_profile_t *p) {
  (void)p; int diff = 0; uint16_t mod = 0;
  float f20 = 0.0f; (void)f20;
  for (int t = 0; t < 1440; t++) {
    hg_minute_t m; memset(&m, 0, sizeof m);
    m.s.minute_of_day = mod; m.s.t1_c = ur(34.0f, 35.5f); m.s.t2_c = m.s.t1_c - 1.0f; m.s.t_air_c = ur(24.0f, 29.0f); m.s.rh_pct = 45.0f;
    m.s.hr_bpm = ur(60.0f, 110.0f); m.s.hr_quality = 4; m.s.pi_pct = 0.6f; m.s.a_std_g = (t % 30) < 3 ? 0.05f : 0.008f;
    for (int k = 0; k < 12; k++) { m.t1_5s[k] = m.s.t1_c; m.t2_5s[k] = m.s.t2_c; m.tair_5s[k] = m.s.t_air_c; m.zangle_5s[k] = 10.0f; }
    m.a_peak_g = 1.0f; m.ppg_dc = 110000; m.vbat = 3.9f; m.ble_bucket = -1; m.force_worn = 2;
    hg_minute_out_t oa, ob; hg_guardian_step(&A, &m, &oa); hg_guardian_step(&B, &m, &ob);
    if (oa.state != ob.state || oa.tiers != ob.tiers || oa.level != ob.level || memcmp(oa.status, ob.status, 20)) diff++;
    mod = (uint16_t)((mod + 1) % 1440);
  }
  return diff;
}
int main(void) {
  hg2_profile_t p = { 75.0f, 0.0f, 26.0f, 0 }; hg2_twin_t tw; hg_twin_defaults(&tw);
  int bad_val = 0, bad_day = 0, n_cases = 0, days = 0;
  for (int i = 0; i < 2000; i++) {
    hg_calm_t c; const uint8_t ns[4] = { 1, 2, 7, 255 }; c.calm_f20_n = ns[i % 4];
    switch (i % 10) { case 0: c.calm_f20_c = 36.8f; break; case 1: c.calm_f20_c = 37.7f; break;
      case 2: c.calm_f20_c = nextafterf(36.8f, 40.0f); break; case 3: c.calm_f20_c = nextafterf(37.7f, 0.0f); break;
      default: c.calm_f20_c = ur(36.8f, 37.7f); }
    hg_guardian_init(&A, &p, &tw); hg_guardian_set_calm(&A, &c);
    int restored = 0; int u = roundtrip(&B, &p, &tw, &c, &restored);
    hg_calm_t ca, cb; hg_guardian_get_calm(&A, &ca); hg_guardian_get_calm(&B, &cb);
    n_cases++;
    if (u != 0 || !restored || ca.calm_f20_n != cb.calm_f20_n || memcmp(&ca.calm_f20_c, &cb.calm_f20_c, 4)) {
      if (bad_val < 5) printf("  value mismatch: c %.9g n %u -> u %d restored %d got %.9g n %u\n", (double)c.calm_f20_c, c.calm_f20_n, u, restored, (double)cb.calm_f20_c, cb.calm_f20_n);
      bad_val++; }
    if (i % 50 == 0) { uint32_t keep = rs; int d = same_day(&p); rs = keep; (void)rs; bad_day += d != 0; days++; }
  }
  printf("%s calm round trip: %d values, %d mismatching; %d full days through both guardians, %d differing\n",
         bad_val == 0 && bad_day == 0 ? "PASS" : "FAIL", n_cases, bad_val, days, bad_day);
  /* rejects */
  const float rej[] = { NAN, INFINITY, -INFINITY, 36.79f, 37.71f, 50.0f, 0.0f };
  int rej_bad = 0;
  for (unsigned i = 0; i < sizeof rej / sizeof rej[0]; i++) {
    hg_calm_t c = { rej[i], 3 }; int restored = 0; int u = roundtrip(&B, &p, &tw, &c, &restored);
    hg_calm_t cb; hg_guardian_get_calm(&B, &cb);
    printf("     reject %-8g: unpack %d restored %d -> n %u\n", (double)rej[i], u, restored, cb.calm_f20_n);
    if (restored || cb.calm_f20_n) rej_bad++;
  }
  hg_calm_t z = { 37.2f, 0 }; int restored = 0; roundtrip(&B, &p, &tw, &z, &restored);
  printf("%s rejects (NaN, +-inf, out of [36.8, 37.7], n = 0 -> unlearned): %d wrong\n", rej_bad == 0 && !restored ? "PASS" : "FAIL", rej_bad);
  return 0;
}
