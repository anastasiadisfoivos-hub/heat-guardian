/* hg_astd.h: the whole-minute std of |a| (g), ONE implementation for 08_logger and 09_guardian (hg_fw.c).
 *
 * Per second the sketch gives the second's |a| samples as (mean, M2 = sum of squared deviations, n). The minute
 * merges them with Chan et al.'s parallel formula and the minute value is sqrt(M2 / n) (population std over every
 * sample of the minute), NAN below 3 samples. This is the a_std_g the guardian (hg2_in_t.a_std_g) gets in 09, so the
 * value 08 logs per minute (log_format.h v2 minute records, bytes 21-22) is the same number for the same samples.
 * fw/tools/test_fw.c checks 08's use == hg_fw.c bit for bit and == the std of all samples (double reference). */
#ifndef HG_ASTD_H
#define HG_ASTD_H
#include <stdint.h>
#include <math.h>

static inline int hg_astd_fin(float v) { return v == v && v < 1e30f && v > -1e30f; }

static inline void hg_astd_reset(float *mean, float *m2, uint32_t *n) { *mean = 0.0f; *m2 = 0.0f; *n = 0; }

/* merge one second (smean, sm2, sn) into the minute (mean, m2, n) */
static inline void hg_astd_add(float *mean, float *m2, uint32_t *n, float smean, float sm2, uint16_t sn)
{
  if (!(sn && hg_astd_fin(smean) && hg_astd_fin(sm2))) return;
  uint32_t nn = *n + sn;
  float d = smean - *mean;
  *mean += d * (float)sn / (float)nn;
  *m2 += sm2 + d * d * (float)*n * (float)sn / (float)nn;
  *n = nn;
}

static inline float hg_astd_std(float m2, uint32_t n) { return n >= 3 ? sqrtf(m2 > 0.0f ? m2 / (float)n : 0.0f) : NAN; }

#endif
