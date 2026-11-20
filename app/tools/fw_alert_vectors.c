/* EVENTS 11 ALERT_HELD / 12 ALL_CLEAR / 13 SCORE vectors made with the BAND's own packers (band 0.9.9:
 * hg_al_held_x / hg_al_clear_x / hg_al_score_x in hg_fw_alert.c, hg_ev_add_x + hg_ev_pack in hg_fw_eco.c), so the app's
 * decoder is checked against the firmware bytes, not against its own encoder. Writes JSON to stdout.
 *
 *   G9=fw/09_guardian   (the 0.9.9 sources)
 *   gcc -std=c99 -O1 -w -I"$G9" ios/tools/fw_alert_vectors.c "$G9/hg_fw_eco.c" "$G9/hg_fw_alert.c" "$G9/hg_fw.c" "$G9"/fz_*.c -lm -o /tmp/fwav
 *   /tmp/fwav > ios/HeatGuardianTests/alert_vectors_fw.json
 */
#include <stdio.h>
#include <string.h>
#include "hg_fw_eco.h"
#include "hg_fw_alert.h"

static hg_evring_t R;
static int first = 1;

static void emit(uint16_t boot, uint32_t unix_s, uint8_t type, uint8_t arg, const uint8_t x[8], const char *extra)
{
  const hg_ev_t *e = hg_ev_add_x(&R, unix_s, type, arg, x);
  uint8_t f[20]; hg_ev_pack(e, boot, f);
  printf("%s  {\"type\": %u, \"seq\": %u, \"boot\": %u, \"unix\": %lu, \"arg\": %u, \"x\": [", first ? "" : ",\n", type, e->seq, boot,
         (unsigned long)unix_s, arg);
  for (int i = 0; i < 8; i++) printf("%s%u", i ? ", " : "", x[i]);
  printf("], %s\"hex\": \"", extra);
  for (int i = 0; i < 20; i++) printf("%02x", f[i]);
  printf("\"}");
  first = 0;
}

int main(void)
{
  hg_ev_init(&R);
  printf("{\"about\": \"band 0.9.9 EVENTS 11/12/13 from the firmware's own packers (ios/tools/fw_alert_vectors.c)\",\n \"events\": [\n");
  /* ALERT_HELD: every what x a few reasons */
  static const uint8_t held[][3] = { {1, 7, 1}, {2, 9, 2}, {3, 5, 4}, {4, 1, 0}, {1, 4, 1}, {2, 6, 2}, {3, 7, 6}, {1, 8, 1}, {2, 2, 2}, {1, 3, 1} };
  for (unsigned i = 0; i < sizeof held / sizeof held[0]; i++) {
    hg_al_note_t n = { held[i][0], held[i][1], held[i][2], 1 };
    uint8_t x[8]; hg_al_held_x(&n, x);
    char ex[96]; snprintf(ex, sizeof ex, "\"what\": %u, \"reason\": %u, \"held_arg\": %u, ", n.what, n.reason, n.arg);
    emit(9, 1789460000u + i * 60u, HG_EV_ALERT_HELD, n.what, x, ex);
  }
  /* ALL_CLEAR: peak, minutes (incl. > 255 and the u16 max), family, tick */
  static const uint16_t cm[][4] = { {1, 12, 0, 0}, {2, 47, 0, 1}, {3, 95, 1, 1}, {3, 300, 1, 1}, {2, 65535, 0, 1} };
  for (unsigned i = 0; i < sizeof cm / sizeof cm[0]; i++) {
    hg_al_out_t o; memset(&o, 0, sizeof o);
    o.clear = 1; o.clear_peak = (uint8_t)cm[i][0]; o.clear_min = cm[i][1]; o.clear_family = (uint8_t)cm[i][2]; o.clear_tick = (uint8_t)cm[i][3];
    uint8_t x[8]; hg_al_clear_x(&o, x);
    char ex[128]; snprintf(ex, sizeof ex, "\"peak\": %u, \"minutes\": %u, \"family\": %u, \"tick\": %u, ", cm[i][0], cm[i][1], cm[i][2], cm[i][3]);
    emit(9, 1789470000u + i * 600u, HG_EV_ALL_CLEAR, o.clear_peak, x, ex);
  }
  /* SCORE: one scorecard, pages 0-2 (with a saturated counter and a time to acknowledge > 255 s) */
  hg_al_t a; memset(&a, 0, sizeof a);
  uint16_t sent[HG_AL_K_N] = { 14, 3, 1, 2, 1, 0, 2, 300 };
  memcpy(a.sc.sent, sent, sizeof sent);
  for (int r = 1; r < HG_AL_R_N; r++) a.sc.held[r] = (uint16_t)(r * 2);
  a.sc.ack = 12; a.sc.missed = 3; a.sc.check_1ev = 1; a.sc.tta_n = 3; a.sc.tta_sum_s = 3 * 97 + 1; a.sc.tta_max_s = 412;
  for (uint8_t pg = 0; pg < 3; pg++) {
    uint8_t x[8]; hg_al_score_x(&a, pg, x);
    char ex[32]; snprintf(ex, sizeof ex, "\"page\": %u, ", pg);
    emit(9, 1789516800u, HG_EV_SCORE, pg, x, ex);
  }
  printf("\n ]}\n");
  return 0;
}
