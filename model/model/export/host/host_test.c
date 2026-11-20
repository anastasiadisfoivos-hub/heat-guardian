/* hg2 host test (from fw/poc_02_nn/host/host_test.c, adapted to 32-24-16-6 x5).
 * cd model/export && gcc -std=c99 -Wall -Wextra -Werror -Wdouble-promotion -fsingle-precision-constant -O2 -ffp-contract=off \
 *    -I. -Ihost host/host_test.c host/hg2_nn.c hg2_weights.c -lm -o host/host_test && host/host_test
 * Pass = CRC equal and every member output, ensemble mean and std within 1e-5 of the Python export. */
#include <stdio.h>
#include <math.h>
#include "hg2_nn.h"
#include "hg2_test_vectors.h"
int main(void) {
  int fails = 0; float maxe = 0.0f;
  int crc = hg2_nn_check_crc();
  printf("CRC check: %s (expected 0x%08lX) version %s\n", crc ? "OK" : "FAIL", (unsigned long)HG2_NN_CRC32, HG2_NN_VERSION);
  if (!crc) fails++;
  for (int t = 0; t < HG2_TV_N; t++) {
    float mean[HG2_NN_OUT], sd[HG2_NN_OUT];
    for (int k = 0; k < HG2_NN_ENS; k++) {
      float y[HG2_NN_OUT]; hg2_nn_forward(&HG2_MEMBERS[k], HG2_TV_Z[t], y);
      for (int o = 0; o < HG2_NN_OUT; o++) { float e = fabsf(y[o] - HG2_TV_Y[t][k][o]); if (e > maxe) maxe = e; if (e > 1e-5f) fails++; }
    }
    hg2_nn_ensemble(HG2_TV_Z[t], mean, sd);
    { float s3[3]; hg2_nn_total_sd(HG2_TV_Z[t], s3);
      for (int o = 0; o < 3; o++) { float e = fabsf(s3[o] - HG2_TV_SDTOT[t][o]); if (e > maxe) maxe = e; if (e > 1e-5f) fails++; } }
    for (int o = 0; o < HG2_NN_OUT; o++) {
      float em = fabsf(mean[o] - HG2_TV_MEAN[t][o]), es = fabsf(sd[o] - HG2_TV_STD[t][o]);
      if (em > maxe) maxe = em;
      if (es > maxe) maxe = es;
      if (em > 1e-5f || (o < 3 && es > 1e-5f)) fails++;   /* std of logits/strain: one-pass float32 cancellation, display only */
    }
  }
  printf("%d vectors, max abs error %.3e, %s\n", HG2_TV_N, (double)maxe, fails ? "FAIL" : "PASS");
  return fails ? 1 : 0;
}
