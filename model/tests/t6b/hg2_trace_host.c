/* T6b: reference run of the FROZEN hg2_step with the guardian/c Makefile flags (the flags of the sealed-exam golden):
 * writes N minutes of inputs (hg2_in_t, 36 B) to in.bin and outputs (hg2_out_t) to out_host.bin.
 * The inputs are SYNTHETIC random walks (not data): worn, T2 dropouts (NaN), HR dropouts (NaN), heat episodes. */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "hg2_step.h"
#include "hg2_state.h"
#include "hg_twin.h"
static uint32_t r = 2026u; static float ur(void) { r = r * 1664525u + 1013904223u; return (float)((r >> 8) & 0xFFFFFF) / 16777216.0f; }
int main(int argc, char **argv) {
  int N = 4000; FILE *fi = fopen(argv[1], "wb"), *fo = fopen(argv[2], "wb");
  hg2_profile_t p = { 75.0f, 0.0f, 26.0f, 0 }; hg2_twin_t tw; hg_twin_defaults(&tw);
  static struct hg2_state s; hg2_init(&s, &p, &tw);
  float t1 = 33.5f, ta = 27.0f, hr = 70.0f, rh = 45.0f;
  for (int i = 0; i < N; i++) {
    int heat = (i % 900) > 500;
    ta += (heat ? 0.03f : -0.02f) + (ur() - 0.5f) * 0.1f; if (ta < 22) ta = 22; if (ta > 41) ta = 41;
    t1 += 0.02f * ((32.0f + 0.12f * ta) - t1) + (ur() - 0.5f) * 0.05f;
    hr += 0.05f * ((heat ? 95.0f : 68.0f) - hr) + (ur() - 0.5f) * 3.0f;
    rh += (ur() - 0.5f) * 1.0f; if (rh < 20) rh = 20; if (rh > 80) rh = 80;
    hg2_in_t in; memset(&in, 0, sizeof in);
    in.t1_c = t1; in.t2_c = ((i / 200) % 4 == 3) ? NAN : t1 - 1.2f - 0.02f * (ta - 25.0f);
    in.t_air_c = ta; in.rh_pct = rh;
    int hrok = ((i / 37) % 5) != 4; in.hr_bpm = hrok ? hr : NAN; in.hr_quality = hrok ? 4 : 2;
    in.pi_pct = hrok ? 0.4f + 0.1f * ur() : NAN; in.a_std_g = (i % 120) < 30 ? 0.03f * ur() : 0.002f * ur();
    in.worn = (i % 1300) < 20 ? 1 : 2; in.minute_of_day = (uint16_t)((480 + i) % 1440);
    hg2_out_t o; hg2_step(&s, &in, &o);
    fwrite(&in, sizeof in, 1, fi); fwrite(&o, sizeof o, 1, fo);
  }
  fclose(fi); fclose(fo);
  printf("sizeof hg2_in_t %u hg2_out_t %u hg2_state %u hg2_twin_t %u hg2_profile_t %u\n", (unsigned)sizeof(hg2_in_t), (unsigned)sizeof(hg2_out_t),
         (unsigned)sizeof(struct hg2_state), (unsigned)sizeof(hg2_twin_t), (unsigned)sizeof(hg2_profile_t));
  return 0;
}
