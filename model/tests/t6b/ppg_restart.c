/* T6b: what does hg_ppg (unchanged, from 08) report in the first 30 s after hg_ppg_init(), which 09 calls at second 0 of
 * every minute when it re-enables the PPG? Synthetic IR (SYNTHETIC, not a wrist): DC 110,000 counts, pulse PI ~0.4 %,
 * 70 bpm, white noise. Prints the quality word per second and how many OK seconds the minute gets (hg_fw needs >= 3). */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include "hg_ppg.h"
int main(int argc, char **argv) {
  float bpm = argc > 1 ? atof(argv[1]) : 70.0f, pi = argc > 2 ? atof(argv[2]) : 0.4f;
  hg_ppg_t s; srand(1);
  int okmin[5] = {0}; int first_ok[5];
  for (int m = 0; m < 5; m++) {           /* 5 consecutive minutes, re-init each minute like 09 */
    hg_ppg_init(&s); first_ok[m] = -1;
    char q[31]; q[30] = 0; double pis = 0;
    for (int sec = 0; sec < 30; sec++) {
      for (int k = 0; k < 100; k++) {
        uint32_t t = (uint32_t)(m * 60000 + sec * 1000 + k * 10 + 1);
        double ph = fmod(t / 1000.0 * bpm / 60.0, 1.0);
        double pulse = ph < 0.3 ? sin(ph / 0.3 * M_PI) : 0.0;   /* systolic bump */
        double ir = 110000.0 * (1.0 - pi / 100.0 * pulse) + ((rand() / (double)RAND_MAX) - 0.5) * 40.0;
        hg_ppg_push(&s, (uint32_t)ir, t);
      }
      q[sec] = '0' + s.quality; pis += s.pi_pct;
      if (s.quality == 4 && s.hr_bpm >= 30) { okmin[m]++; if (first_ok[m] < 0) first_ok[m] = sec; }
    }
    printf("minute %d: quality per second [%s]  OK seconds %d  first OK at s=%d  last HR %.1f  PI mean(30 s) %.3f vs steady %.3f\n", m, q, okmin[m], first_ok[m], s.hr_bpm, pis / 30, s.pi_pct);
  }
  return 0;
}
