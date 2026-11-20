/* hg2 ensemble inference for the host test and the poc_02_hg2 compile check (R4 poc_02 pattern, 32-24-16-6 x5).
 * Same loop order as guardian/c/hg2_step.c dense(): acc = b; acc += w[i]*x[i] sequentially. */
#pragma once
#include "hg2_weights.h"
#ifdef __cplusplus
extern "C" {
#endif
void hg2_nn_forward(const hg2_member_t *m, const float *z, float *y);
void hg2_nn_ensemble(const float *z, float *mean, float *sd);
int hg2_nn_check_crc(void);
void hg2_nn_total_sd(const float *z, float *sd3);   /* M6.2 total sd, normalised units */
#ifdef __cplusplus
}
#endif
