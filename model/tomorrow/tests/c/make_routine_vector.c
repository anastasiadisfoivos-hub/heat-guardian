/* Builds the shared B4<->B5 routine-profile test vector WITH B5's OWN packer (guardian/c/hg_routine.c, read-only).
 * Build+run: see tests/test_routine.py (gcc -std=c99 -I../../../guardian/c ... ../../../guardian/c/hg_routine.c). */
#include <stdio.h>
#include <string.h>
#include "hg_routine.h"
int main(void) {
  hg_routine_t r; hg_routine_init(&r);
  for (int h = 0; h < 24; h++) {
    float am = (h < 7 || h >= 23) ? 0.5f : (h == 7 ? 20.0f : (h >= 9 && h < 11) ? 42.0f : (h == 14 || h == 15) ? 3.0f : 15.0f);
    r.am[h].n = (h == 3) ? 2.0f : 10.0f;            /* hour 3 deliberately NOT learned (n < 3) */
    r.am[h].mean = am; r.am[h].m2 = 4.0f * (r.am[h].n - 1.0f);
    r.q[h].n = 10.0f; r.q[h].mean = (h < 7) ? 60.0f : 20.0f; r.q[h].m2 = 9.0f;
    r.maxq[h] = (int16_t)((h < 7) ? 60 : 45);
  }
  uint16_t w[7] = {425, 430, 440, 450, 435, 445, 420};
  memcpy(r.wake_hist, w, sizeof w); r.n_wake = 7; r.wake_i = 0;
  r.sleep_on = 1380; r.sleep_off = 430; r.sleep_valid = 1; r.days_learned = 10;
  uint8_t buf[HG_ROUTINE_PACK_BYTES];
  uint16_t n = hg_routine_pack(&r, buf, sizeof buf);
  hg_routine_t back; int ok = hg_routine_unpack(&back, buf, n);
  if (n != HG_ROUTINE_PACK_BYTES || !ok) { fprintf(stderr, "pack/unpack failed\n"); return 1; }
  for (uint16_t i = 0; i < n; i++) printf("%02x", buf[i]);
  printf("\n");
  return 0;
}
