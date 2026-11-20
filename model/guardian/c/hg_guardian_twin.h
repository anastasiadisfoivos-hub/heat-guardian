/* M11.5 bridge: Guardian design-A calm baseline <-> B3's Body Twin save file (twin/c/hg_twin.h, M9.5 field at offset 193).
 * Compiled only in builds that link hg_twin (09_guardian firmware, tests/twin_integration.c); build with
 * -DHG_TWIN_USE_HG2_STEP_H -I../../twin/c so both sides share guardian/c/hg2_step.h's hg2_twin_t / hg2_in_t. */
#ifndef HG_GUARDIAN_TWIN_H
#define HG_GUARDIAN_TWIN_H
#include "hg_guardian.h"
#include "hg_twin.h"
#ifdef __cplusplus
extern "C" {
#endif
/* before the nightly save: guardian -> twin accumulator (the twin packs it) */
void hg_guardian_calm_to_twin(const hg_guardian_t *g, hg_twin_acc_t *acc);
/* at boot after hg_twin_unpack(): twin accumulator -> guardian; returns 1 if a learned baseline was restored */
int  hg_guardian_calm_from_twin(hg_guardian_t *g, const hg_twin_acc_t *acc);
/* B5-v7: the Exception-DRINK movement sums ride along (twin file v4). calm_to_twin also copies them (guardian -> acc) and
 * calm_from_twin also restores them (acc -> guardian, rejected values leave them unlearned); separate entry points: */
void hg_guardian_exc_to_twin(const hg_guardian_t *g, hg_twin_acc_t *acc);
int  hg_guardian_exc_from_twin(hg_guardian_t *g, const hg_twin_acc_t *acc);
#ifdef __cplusplus
}
#endif
#endif
