/* Heat Guardian R4 PoC: plain-C MLP inference. See hg_nn.h. */
#include "hg_nn.h"
#include <math.h>
#include <string.h>

/* y[n_out] = relu?(W[n_out][n_in] . x + b). W is row-major, as the exporter writes it. */
static inline void dense(const float *W, const float *b, const float *x,
                         float *y, int n_in, int n_out, int relu)
{
  for (int o = 0; o < n_out; o++) {
    const float *w = W + (size_t)o * n_in;
    float acc = b[o];
    /* 4-way unrolled so the compiler emits back-to-back vfma.f32 on the M4F */
    int i = 0;
    for (; i + 4 <= n_in; i += 4) {
      acc += w[i] * x[i];
      acc += w[i + 1] * x[i + 1];
      acc += w[i + 2] * x[i + 2];
      acc += w[i + 3] * x[i + 3];
    }
    for (; i < n_in; i++) acc += w[i] * x[i];
    y[o] = (relu && acc < 0.0f) ? 0.0f : acc;
  }
}

void hg_nn_forward(const hg_nn_member_t *m, const float *x, float *y)
{
  float h1[HG_NN_H1], h2[HG_NN_H2];
  dense(m->W1, m->b1, x,  h1, HG_NN_IN, HG_NN_H1, 1);
  dense(m->W2, m->b2, h1, h2, HG_NN_H1, HG_NN_H2, 1);
  dense(m->W3, m->b3, h2, y,  HG_NN_H2, HG_NN_OUT, 0);
}

void hg_nn_ensemble(const float *x, float *mean, float *std)
{
  float ys[HG_NN_ENS][HG_NN_OUT];
  for (int k = 0; k < HG_NN_ENS; k++) hg_nn_forward(&HG_NN_MEMBERS[k], x, ys[k]);
  for (int o = 0; o < HG_NN_OUT; o++) {
    float s = 0.0f, s2 = 0.0f;
    for (int k = 0; k < HG_NN_ENS; k++) { s += ys[k][o]; s2 += ys[k][o] * ys[k][o]; }
    float mu = s / HG_NN_ENS;
    float var = s2 / HG_NN_ENS - mu * mu;
    mean[o] = mu;
    std[o]  = var > 0.0f ? sqrtf(var) : 0.0f;
  }
}

/* ---- int8 path (member 0) -------------------------------------------------
 * acc(int32) = sum(int8 w * int8 x) + b_q ; y_q = sat8( (acc * M) >> (31 + S) )
 * M, S come from the exporter (Q0.31 multiplier + right shift), i.e. the same
 * "requantize" step TFLite-Micro does. ReLU is just clamping at 0. */
static inline int8_t requant(int32_t acc, int32_t M, int S, int relu)
{
  int64_t p = (int64_t)acc * M;                 /* smull on the M4: 1 instruction */
  int32_t r = (int32_t)(p >> (31 + S));
  if (relu && r < 0) r = 0;
  if (r > 127) r = 127;
  if (r < -128) r = -128;
  return (int8_t)r;
}

static inline void dense_i8(const int8_t *W, const int32_t *b, const int8_t *x,
                            int8_t *y, int n_in, int n_out, int32_t M, int S, int relu)
{
  for (int o = 0; o < n_out; o++) {
    const int8_t *w = W + (size_t)o * n_in;
    int32_t acc = b[o];
    for (int i = 0; i < n_in; i++) acc += (int32_t)w[i] * (int32_t)x[i];
    y[o] = requant(acc, M, S, relu);
  }
}

void hg_nn_forward_i8_0(const int8_t *x_q, int8_t *y_q)
{
  int8_t h1[HG_NN_H1], h2[HG_NN_H2];
  dense_i8(&W1q_0[0][0], b1q_0, x_q, h1, HG_NN_IN, HG_NN_H1, HG_NN_M1_0, HG_NN_S1_0, 1);
  dense_i8(&W2q_0[0][0], b2q_0, h1,  h2, HG_NN_H1, HG_NN_H2, HG_NN_M2_0, HG_NN_S2_0, 1);
  dense_i8(&W3q_0[0][0], b3q_0, h2,  y_q, HG_NN_H2, HG_NN_OUT, HG_NN_M3_0, HG_NN_S3_0, 0);
}

/* ---- CRC-32 over the weight bytes (bitwise, no table: 0 B of flash for a table) */
static uint32_t crc32_update(uint32_t crc, const void *p, size_t n)
{
  const uint8_t *b = (const uint8_t *)p;
  crc = ~crc;
  while (n--) {
    crc ^= *b++;
    for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
  }
  return ~crc;
}

int hg_nn_check_crc(void)
{
  uint32_t c = 0;
  for (int k = 0; k < HG_NN_ENS; k++) {
    const hg_nn_member_t *m = &HG_NN_MEMBERS[k];
    c = crc32_update(c, m->W1, sizeof(float) * HG_NN_H1 * HG_NN_IN);
    c = crc32_update(c, m->b1, sizeof(float) * HG_NN_H1);
    c = crc32_update(c, m->W2, sizeof(float) * HG_NN_H2 * HG_NN_H1);
    c = crc32_update(c, m->b2, sizeof(float) * HG_NN_H2);
    c = crc32_update(c, m->W3, sizeof(float) * HG_NN_OUT * HG_NN_H2);
    c = crc32_update(c, m->b3, sizeof(float) * HG_NN_OUT);
  }
  return c == HG_NN_CRC32;
}
