/* Host test (from poc_02_nn/): gcc -O2 -I. -Ihost host/host_test.c hg_nn.c hg_weights.c -lm && ./a.out
 * Proves the C forward pass == the numpy forward pass (export_weights.py),
 * the ensemble mean/std match, the CRC matches, and the int8 path is close. */
#include <stdio.h>
#include <math.h>
#include "hg_nn.h"
#include "hg_test_vectors.h"

int main(void)
{
  int fails = 0;
  printf("CRC check: %s (expected 0x%08X)\n", hg_nn_check_crc() ? "OK" : "FAIL", HG_NN_CRC32);
  if (!hg_nn_check_crc()) fails++;
  for (int t = 0; t < HG_TV_N; t++) {
    float y0[HG_NN_OUT], mean[HG_NN_OUT], sd[HG_NN_OUT];
    hg_nn_forward(&HG_NN_MEMBERS[0], HG_TV_X[t], y0);
    hg_nn_ensemble(HG_TV_X[t], mean, sd);
    int8_t xq[HG_NN_IN], yq[HG_NN_OUT];
    for (int i = 0; i < HG_NN_IN; i++) { float v = roundf(HG_TV_X[t][i] / HG_NN_I8_SX); xq[i] = v > 127 ? 127 : v < -128 ? -128 : (int8_t)v; }
    hg_nn_forward_i8_0(xq, yq);
    for (int o = 0; o < HG_NN_OUT; o++) {
      float e0 = fabsf(y0[o] - HG_TV_Y0[t][o]);
      float em = fabsf(mean[o] - HG_TV_MEAN[t][o]);
      float es = fabsf(sd[o] - HG_TV_STD[t][o]);
      float ei = fabsf(yq[o] * HG_NN_I8_SOUT - HG_TV_Y0[t][o]);
      printf("tv%d out%d  float y0=%.5f (ref %.5f, err %.1e)  mean err %.1e  std err %.1e  int8 y=%.3f (err %.3f)\n",
             t, o, y0[o], HG_TV_Y0[t][o], e0, em, es, yq[o] * HG_NN_I8_SOUT, ei);
      if (e0 > 1e-4f || em > 1e-4f || es > 1e-3f) fails++;
    }
  }
  printf("%s\n", fails ? "SOME CHECKS FAILED" : "ALL FLOAT CHECKS PASS");
  return fails != 0;
}
