/* M11.5 integration: guardian learns a calm-f20 baseline over crafted calm days -> hg_guardian_calm_to_twin -> hg_twin_pack
 * (with the 650-B routine profile) -> hg_twin_unpack -> hg_guardian_calm_from_twin into a FRESH guardian -> same baseline,
 * same routine bytes; a corrupted file restores nothing. */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "hg_guardian_twin.h"
static int fails = 0;
static void rep(const char *n, int ok) { printf("%s %s\n", ok ? "PASS" : "FAIL", n); if (!ok) fails++; }
int main(void) {
  static hg_guardian_t g, g2; hg2_profile_t p = { 75.0f, 0.0f, 26.0f, 0 }; hg2_twin_t tw; hg_twin_defaults(&tw);
  hg_guardian_init(&g, &p, &tw);
  /* 3 calm days: 25 C room, HR 66, sitting, time known -> the guardian's own learner fills a_base */
  for (int d = 0; d < 3; d++) for (int mod = 0; mod < 1440; mod++) {
    hg_minute_t m; memset(&m, 0, sizeof m);
    m.s.minute_of_day = (uint16_t)mod; m.s.t1_c = 34.0f; m.s.t2_c = 32.8f; m.s.t_air_c = 25.0f; m.s.rh_pct = 45.0f; m.s.hr_bpm = 66.0f;
    m.s.hr_quality = 4; m.s.pi_pct = 0.6f; m.s.a_std_g = 0.008f;
    for (int k = 0; k < 12; k++) { m.t1_5s[k] = 34.0f; m.t2_5s[k] = 32.8f; m.tair_5s[k] = 25.0f; m.zangle_5s[k] = 10.0f; }
    m.a_peak_g = 1.0f; m.ppg_dc = 110000; m.vbat = 3.9f; m.ble_bucket = -1; m.force_worn = 2;
    hg_minute_out_t o; hg_guardian_step(&g, &m, &o);
  }
  hg_calm_t c1; hg_guardian_get_calm(&g, &c1);
  printf("     learned calm f20 %.4f C over %u days\n", (double)c1.calm_f20_c, c1.calm_f20_n);
  rep("guardian learned a calm baseline (n >= 2)", c1.calm_f20_n >= 2 && c1.calm_f20_c >= 36.8f && c1.calm_f20_c <= 37.7f);
  /* B5-v7 (manager item 2): the Exception-DRINK sums ride in the twin file (v4). Learned sums are used if any, else set ones */
  hg_exc_t e1; hg_guardian_get_exc(&g, &e1);
  printf("     learned Exception sums sxx %.4g sxy %.4g\n", (double)e1.sxx, (double)e1.sxy);
  if (!(e1.sxx > 1.0f)) { e1.sxx = 812.5f; e1.sxy = 97.25f; rep("set Exception sums accepted", hg_guardian_set_exc(&g, &e1)); }
  const float xc1 = g.x_c;
  hg_twin_acc_t acc; hg_twin_acc_init(&acc); hg_guardian_calm_to_twin(&g, &acc);
  uint8_t rt[HG_ROUTINE_PACK_BYTES]; uint16_t rn = hg_routine_pack(&g.rt, rt, sizeof rt);
  uint8_t file[900]; int n = hg_twin_pack(&tw, &acc, rt, rn, 7, file, sizeof file);
  printf("     twin file %d B (routine %u B)\n", n, rn);
  rep("twin pack <= 900 B", n > 0 && n <= 900);
  hg2_twin_t tw2; hg_twin_acc_t acc2; uint8_t rt2[700]; uint16_t rn2 = 0; uint32_t sc = 0;
  int u = hg_twin_unpack(file, (uint16_t)n, &tw2, &acc2, rt2, sizeof rt2, &rn2, &sc);
  hg_guardian_init(&g2, &p, &tw2);
  int restored = hg_guardian_calm_from_twin(&g2, &acc2);
  hg_calm_t c2; hg_guardian_get_calm(&g2, &c2);
  rep("unpack ok + calm restored into a fresh guardian, bit-identical", u == 0 && restored && c2.calm_f20_n == c1.calm_f20_n &&
      memcmp(&c2.calm_f20_c, &c1.calm_f20_c, 4) == 0);
  hg_exc_t e2; hg_guardian_get_exc(&g2, &e2);
  rep("B5-v7 Exception sums restored into a fresh guardian, bit-identical, same slope c",
      memcmp(&e2.sxx, &e1.sxx, 4) == 0 && memcmp(&e2.sxy, &e1.sxy, 4) == 0 && memcmp(&g2.x_c, &xc1, 4) == 0 && xc1 > 0.0f);
  hg_routine_t r2; rep("routine profile survives the twin file", rn2 == rn && memcmp(rt, rt2, rn) == 0 && hg_routine_unpack(&r2, rt2, rn2));
  file[200] ^= 0x40;
  hg_twin_acc_t acc3; uint16_t rn3 = 0; hg2_twin_t tw3;
  int u3 = hg_twin_unpack(file, (uint16_t)n, &tw3, &acc3, rt2, sizeof rt2, &rn3, &sc);
  static hg_guardian_t g3; hg_guardian_init(&g3, &p, &tw3);
  int r3 = hg_guardian_calm_from_twin(&g3, &acc3); hg_calm_t c3; hg_guardian_get_calm(&g3, &c3);
  hg_exc_t e3; hg_guardian_get_exc(&g3, &e3);
  rep("corrupted file -> nothing restored (baseline unlearned, Exception sums 0)", u3 < 0 && !r3 && c3.calm_f20_n == 0 && e3.sxx == 0.0f && e3.sxy == 0.0f && g3.x_c == 0.0f);
  return fails;
}
