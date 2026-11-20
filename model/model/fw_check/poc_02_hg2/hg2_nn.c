#include "hg2_nn.h"
#include "hg2_guard.h"
#include <math.h>
#include <stddef.h>
static void dense(const float *W, const float *b, const float *x, float *y, int n_in, int n_out, int relu) {
  for (int o = 0; o < n_out; o++) {
    const float *w = W + (size_t)o * n_in;
    float acc = b[o];
    for (int i = 0; i < n_in; i++) acc += w[i] * x[i];
    y[o] = (relu && acc < 0.0f) ? 0.0f : acc;
  }
}
void hg2_nn_forward(const hg2_member_t *m, const float *z, float *y) {
  float h1[HG2_NN_H1], h2[HG2_NN_H2];
  dense(m->W1, m->b1, z, h1, HG2_NN_IN, HG2_NN_H1, 1);
  dense(m->W2, m->b2, h1, h2, HG2_NN_H1, HG2_NN_H2, 1);
  dense(m->W3, m->b3, h2, y, HG2_NN_H2, HG2_NN_OUT, 0);
}
/* M6.2 total sd (normalised units) for outputs 0..2: sqrtf(mean_k(v_k^2 + EPS_V) + between-member variance) */
void hg2_nn_total_sd(const float *z, float *sd3) {
  float s[3] = {0.0f, 0.0f, 0.0f}, s2[3] = {0.0f, 0.0f, 0.0f}, a[3] = {0.0f, 0.0f, 0.0f};
  for (int k = 0; k < HG2_NN_ENS; k++) {
    float y[HG2_NN_OUT];
    hg2_nn_forward(&HG2_MEMBERS[k], z, y);
    for (int o = 0; o < 3; o++) { s[o] += y[o]; s2[o] += y[o] * y[o]; a[o] += y[6 + o] * y[6 + o] + HG2_EPS_V; }
  }
  for (int o = 0; o < 3; o++) {
    float mu = s[o] / (float)HG2_NN_ENS, var = s2[o] / (float)HG2_NN_ENS - mu * mu;
    sd3[o] = sqrtf(a[o] / (float)HG2_NN_ENS + (var > 0.0f ? var : 0.0f));
  }
}
void hg2_nn_ensemble(const float *z, float *mean, float *sd) {
  float s[HG2_NN_OUT], s2[HG2_NN_OUT];
  for (int o = 0; o < HG2_NN_OUT; o++) { s[o] = 0.0f; s2[o] = 0.0f; }
  for (int k = 0; k < HG2_NN_ENS; k++) {
    float y[HG2_NN_OUT];
    hg2_nn_forward(&HG2_MEMBERS[k], z, y);
    for (int o = 0; o < HG2_NN_OUT; o++) { s[o] += y[o]; s2[o] += y[o] * y[o]; }
  }
  for (int o = 0; o < HG2_NN_OUT; o++) {
    float mu = s[o] / (float)HG2_NN_ENS, var = s2[o] / (float)HG2_NN_ENS - mu * mu;
    mean[o] = mu; sd[o] = var > 0.0f ? sqrtf(var) : 0.0f;
  }
}
static unsigned long crc32_update(unsigned long crc, const void *p, size_t n) {
  const unsigned char *b = (const unsigned char *)p;
  crc = ~crc & 0xFFFFFFFFul;
  while (n--) { crc ^= *b++; for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320ul & (0ul - (crc & 1ul))); }
  return ~crc & 0xFFFFFFFFul;
}
int hg2_nn_check_crc(void) {
  unsigned long c = 0;
  for (int k = 0; k < HG2_NN_ENS; k++) {
    const hg2_member_t *m = &HG2_MEMBERS[k];
    c = crc32_update(c, m->W1, 4u * HG2_NN_H1 * HG2_NN_IN); c = crc32_update(c, m->b1, 4u * HG2_NN_H1);
    c = crc32_update(c, m->W2, 4u * HG2_NN_H2 * HG2_NN_H1); c = crc32_update(c, m->b2, 4u * HG2_NN_H2);
    c = crc32_update(c, m->W3, 4u * HG2_NN_OUT * HG2_NN_H2); c = crc32_update(c, m->b3, 4u * HG2_NN_OUT);
  }
  return c == (unsigned long)HG2_NN_CRC32;
}
