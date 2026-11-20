/* T5: sizeof probe for the ARM target (read back with objdump) */
#include "hg_guardian.h"
const unsigned t5_sizes[] = { sizeof(hg_guardian_t), sizeof(hg2_state_t), sizeof(hg_kf_t), sizeof(hg_contact_t), sizeof(hg_homeout_t),
  sizeof(hg_routine_t), sizeof(hg_minute_t), sizeof(hg_minute_out_t), sizeof(hg2_aux_t), sizeof(hg2_out_t) };
