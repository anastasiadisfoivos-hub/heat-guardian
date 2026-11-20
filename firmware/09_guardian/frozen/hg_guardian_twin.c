#include "hg_fp.h"   /* T5 D1: first include - IEEE-exact float semantics even under -ffast-math */
#include "hg_guardian_twin.h"
void hg_guardian_calm_to_twin(const hg_guardian_t *g, hg_twin_acc_t *acc) {
  hg_calm_t c; hg_guardian_get_calm(g, &c);
  hg_twin_set_calm(acc, c.calm_f20_c, c.calm_f20_n);
  hg_guardian_exc_to_twin(g, acc);   /* B5-v7 */
}
void hg_guardian_exc_to_twin(const hg_guardian_t *g, hg_twin_acc_t *acc) {
  hg_exc_t e; hg_guardian_get_exc(g, &e);
  hg_twin_set_exc(acc, e.sxx, e.sxy);
}
int hg_guardian_exc_from_twin(hg_guardian_t *g, const hg_twin_acc_t *acc) {
  hg_exc_t e; hg_twin_get_exc(acc, &e.sxx, &e.sxy);
  return hg_guardian_set_exc(g, &e) && e.sxx > 0.0f;
}
int hg_guardian_calm_from_twin(hg_guardian_t *g, const hg_twin_acc_t *acc) {
  hg_calm_t c; float f = 0.0f;
  c.calm_f20_n = hg_twin_get_calm(acc, &f); c.calm_f20_c = f;
  (void)hg_guardian_exc_from_twin(g, acc);   /* B5-v7: Exception sums restored with the calm baseline */
  return hg_guardian_set_calm(g, &c) && c.calm_f20_n > 0;
}
