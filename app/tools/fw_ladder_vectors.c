/* EVENTS 17-21 (the 0.9.17 closed-loop action ladder) vectors made with the BAND's own code: the ladder state machine
 * hg_ld_minute / hg_ld_press in hg_fw_ladder.c emits the events with their x bytes, hg_ev_add_x + hg_ev_pack in
 * hg_fw_eco.c pack the 20-byte frame. So the app's decoder (LadderEvents.swift) is checked against firmware bytes,
 * not against its own encoder. Also EVENTS 14 POWER_OFF and 16 HAPTIC_LOST (types the app must not choke on).
 * Writes JSON to stdout. Made from band 0.9.17 (commit a486805, ECOSYSTEM_SPEC 5f); re-run on later firmware and diff.
 *
 *   G9=fw/09_guardian   (the 0.9.17 sources)
 *   gcc -std=c99 -O1 -w -I"$G9" ios/tools/fw_ladder_vectors.c "$G9/hg_fw_ladder.c" "$G9/hg_fw_ui.c" "$G9/hg_fw_eco.c" \
 *       "$G9/hg_fw.c" "$G9"/fz_*.c -lm -o /tmp/fwlv
 *   /tmp/fwlv > ios/HeatGuardianTests/ladder_vectors_fw.json
 */
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "hg_fw_eco.h"
#include "hg_fw_ladder.h"
#include "frozen/hg_guardian.h"

static hg_evring_t R;
static hg_ld_t L;
static int first = 1;
static uint32_t T0 = 1784293200u;   /* 2026-07-17 13:00 UTC: a heat-wave afternoon */
static int minute;
static const char *scen;

static void emit_raw(uint8_t type, uint8_t arg, const uint8_t x[8])
{
  uint32_t unix_s = T0 + (uint32_t)minute * 60u;
  const hg_ev_t *e = hg_ev_add_x(&R, unix_s, type, arg, x);
  uint8_t f[20]; hg_ev_pack(e, 7, f);
  printf("%s  {\"scenario\": \"%s\", \"minute\": %d, \"type\": %u, \"seq\": %u, \"boot\": 7, \"unix\": %lu, \"arg\": %u, \"x\": [",
         first ? "" : ",\n", scen, minute, type, e->seq, (unsigned long)unix_s, arg);
  for (int i = 0; i < 8; i++) printf("%s%u", i ? ", " : "", x[i]);
  printf("], \"hex\": \"");
  for (int i = 0; i < 20; i++) printf("%02x", f[i]);
  printf("\"}");
  first = 0;
}
static void take(const hg_ld_out_t *o) { for (int i = 0; i < o->n; i++) emit_raw(o->ev[i].type, o->ev[i].arg, o->ev[i].x); }
static void tick(uint8_t present, uint8_t danger, uint8_t episode, float f20)
{
  hg_ld_in_t in = { present, danger, episode, f20 }; hg_ld_out_t o; hg_ld_minute(&L, &in, &o); take(&o); minute++;
}
static void press(void) { hg_ld_out_t o; hg_ld_press(&L, &o); take(&o); }
static void start(const char *s) { hg_ld_init(&L); scen = s; minute = 0; }

int main(void)
{
  hg_ev_init(&R);
  printf("[\n");
  /* A: water worked */
  start("water_worked");
  tick(HG_ST_DRINK, 0, 1, 37.80f); tick(0, 0, 1, 37.82f); tick(0, 0, 1, 37.84f); press();
  for (int i = 0; i < 20; i++) tick(0, 0, 1, 37.84f - 0.002f * i);
  /* B: water did not help -> cooler place -> still heating -> escalation -> she presses (responsive) -> stops rising */
  start("water_failed_cool_failed");
  tick(HG_ST_DRINK, 0, 1, 37.90f); tick(0, 0, 1, 37.92f); press();
  for (int i = 0; i < 20; i++) tick(0, 0, 1, 37.92f + 0.01f * (i + 1));
  tick(0, 0, 1, 38.13f); press();
  for (int i = 0; i < 20; i++) tick(0, 0, 1, 38.13f + 0.005f * (i + 1));
  press();
  for (int i = 0; i < 25; i++) tick(0, 0, 1, 38.24f);
  /* C: no response to a cooler-place reminder (repeat after 10 min, note after 20) */
  start("no_response");
  tick(HG_ST_COOL, 0, 1, 38.00f);
  for (int i = 0; i < 21; i++) tick(0, 0, 1, 38.00f);
  /* D: the Danger line at once; then the episode ends (worked after an escalation) */
  start("danger");
  tick(0, 1, 1, 38.50f); tick(0, 1, 1, 38.55f); tick(0, 0, 0, 38.30f);
  /* E: band-side types the app must decode or skip: POWER_OFF (wearer), HAPTIC_LOST, unknown forecast byte */
  scen = "other";
  { uint8_t z[8] = {0}; emit_raw(HG_EV_POWER_OFF, 1, z); emit_raw(HG_EV_HAPTIC_LOST, 3, z); }
  printf("\n]\n");
  return 0;
}
