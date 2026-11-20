/* Heat Guardian R4 PoC: plain-C MLP inference for Cortex-M4F.
 * No TFLite Micro, no CMSIS-NN, no malloc. Everything the band needs to run
 * a 24 -> 32 -> 16 -> 3 ReLU MLP and a 5-member ensemble of it.
 * The weights come from the generated hg_weights.h (see export_weights.py).
 */
#pragma once
#include <stdint.h>
#include "hg_weights.h"

#ifdef __cplusplus
extern "C" {
#endif

/* One member: y[HG_NN_OUT] = MLP(x[HG_NN_IN]). Stack use: (H1 + H2) floats = 192 B. */
void hg_nn_forward(const hg_nn_member_t *m, const float *x, float *y);

/* Ensemble: mean and std over HG_NN_ENS members (std = disagreement -> warn earlier).
 * Stack use: HG_NN_ENS * HG_NN_OUT floats + one member's scratch. */
void hg_nn_ensemble(const float *x, float *mean, float *std);

/* int8 version of member 0 (same maths, integer MACs). Input x_q = round(x * 64). */
void hg_nn_forward_i8_0(const int8_t *x_q, int8_t *y_q);

/* CRC-32 (IEEE, same polynomial as zlib.crc32) of the float32 weights of every
 * member, computed at boot and compared with HG_NN_CRC32. Returns 1 if equal. */
int hg_nn_check_crc(void);

#ifdef __cplusplus
}
#endif
