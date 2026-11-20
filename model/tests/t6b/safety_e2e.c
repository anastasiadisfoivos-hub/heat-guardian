/* T6b end-to-end safety paths through the 09 glue (hg_fw.c) + the FROZEN guardian, minute by minute, emulating what
 * 09_guardian.ino does (button latched by hg_fw_button() during the minute, consumed at the boundary).
 *  A. impact + stillness -> CHECK -> no press -> family_alert at check minute 5 (wall-clock latency of the flag)
 *  B. press at every minute 0..5 after the CHECK appeared (last second before the boundary) -> IMOK, no family
 *  C. HELP (long press) -> latched; FAMILY_ACK type 1 (what the dashboard's only button sends) does NOT clear it;
 *     the console 'profile' command path (hg_guardian_init + calm + routine restore, as guardian_layer.inc:371-374)
 *     clears HELP / family_pending / an active CHECK.
 *  D. clock spoof: a CRC-valid TIME that changes the local day every minute -> nightly updates + twin saves per real day.
 *  E. low battery: haptic id the guardian emits at 3.38 V vs what the sketch's vibrate() does (pofHold < 3.40 V). */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "hg_fw.h"
static hg_guardian_t g; static hg_fw_t fw; static hg2_twin_t tw; static hg_twin_acc_t acc;
static const hg2_profile_t P = { 75.0f, 0.0f, 26.0f, 0 };
static int fails = 0;
#define CHECK(c, ...) do { printf((c) ? "PASS  " : "FAIL  "); if (!(c)) fails++; printf(__VA_ARGS__); printf("\n"); } while (0)
static uint32_t rng = 99u; static float ur(void) { rng = rng * 1664525u + 1013904223u; return (float)((rng >> 8) & 0xFFFFFF) / 16777216.0f; }
static void reset(void) { hg_twin_defaults(&tw); hg_twin_acc_init(&acc); hg_guardian_init(&g, &P, &tw); hg_fw_init(&fw); }
/* one minute; still = a_std ~0.0005 g; peak = |a| max; vbat */
static void minute(int mod, int day, int still, float peak, int button, float vbat) {
  for (int s = 0; s < 60; s++) {
    hg_fw_sec_t x; memset(&x, 0, sizeof x);
    x.t1_c = 33.8f; x.t2_c = 32.3f; x.tair_c = 25.0f; x.rh_pct = 45; x.ppg_on = s < 30; x.hr_q = 4; x.hr_bpm = 68 + ur();
    x.pi_pct = 0.5f; x.ppg_dc = 110000; x.a_mean = 1.0f; x.a_n = 25;
    float sd = still ? 0.0005f : 0.03f; x.a_m2 = sd * sd * 25.0f * (0.8f + 0.4f * ur());
    x.a_peak_g = (s == 10 && peak > 0) ? peak : 1.0f + sd; x.zangle_deg = still ? 5.0f : 10.0f + 20.0f * ur();
    hg_fw_second(&fw, &x);
  }
  if (button) hg_fw_button(&fw, (uint8_t)button);
  hg_fw_ctx_t c = { (uint16_t)mod, day, 0, vbat, -1, NULL, 0 }; hg_fw_act_t a;
  hg_fw_minute(&fw, &g, &tw, &acc, &c, 0, &a);
}
static int warm(void) { int m = 0; for (; m < 60; m++) minute(600 + m, 20000, 0, 0, 0, 3.9f); return 600 + m; }
int main(void) {
  /* A */
  reset(); int mod = warm();
  minute(mod++, 20000, 1, 3.0f, 0, 3.9f);            /* impact */
  int t_check = -1, t_fam = -1;
  for (int k = 0; k < 20; k++) {
    minute(mod, 20000, 1, 0, 0, 3.9f);
    if (t_check < 0 && fw.last_out.state == HG_ST_CHECK) t_check = mod;
    if (t_fam < 0 && fw.last_out.family_alert) t_fam = mod;
    mod++;
  }
  printf("INFO  A: CHECK at step %d (reason 0x%02x), family_alert at step %d\n", t_check, g.check_cause, t_fam);
  CHECK(t_check > 0 && t_fam - t_check == 5, "A impact CHECK -> family flag 5 minute-steps after the CHECK screen (%d)", t_fam - t_check);
  /* B: press during minute j after the CHECK step (the press is latched and seen at the next boundary) */
  for (int j = 0; j < 6; j++) {
    reset(); mod = warm(); minute(mod++, 20000, 1, 3.0f, 0, 3.9f);
    int cs = -1; for (int k = 0; k < 5 && cs < 0; k++) { minute(mod, 20000, 1, 0, 0, 3.9f); if (fw.last_out.state == HG_ST_CHECK) cs = mod; mod++; }
    int imok = 0, fam = 0;
    for (int k = 0; k < 8; k++) { minute(mod, 20000, 1, 0, k == j, 3.9f); imok |= fw.last_out.state == HG_ST_IMOK; fam |= fw.last_out.family_alert; mod++; }
    printf("%s  B press in wall minute %d after the CHECK appeared -> IMOK %d, family %d%s\n", (j < 5 ? (imok && !fam) : 1) ? "PASS" : "FAIL", j + 1, imok, fam,
           j == 4 ? "  (pressed in the last minute before the flag: still counts)" : j == 5 ? "  (after the flag: expected family=1)" : "");
    if (j < 5 && !(imok && !fam)) fails++;
  }
  /* C */
  reset(); mod = warm(); minute(mod++, 20000, 0, 0, 2, 3.9f);
  CHECK(fw.last_out.state == HG_ST_HELP && fw.last_out.family_alert, "C long press -> HELP + family_alert");
  { hg_cmd_t c; memset(&c, 0, sizeof c); c.op = HG_CMD_FAMILY_ACK; c.ack_type = 1; c.alarm_id = g.alarm_id; hg_guardian_cmd(&g, &c);
    for (int k = 0; k < 3; k++) minute(mod++, 20000, 0, 0, 1, 3.9f); }
  printf("INFO  C after dashboard ack (type 1) + 3 short presses: state %u (8 = HELP), family_alert %u, help latch %u -> screen stays on at 100 %% (uiAlert)\n",
         fw.last_out.state, fw.last_out.family_alert, g.help);
  CHECK(g.help == 1, "C HELP is NOT cleared by the dashboard's only ack (type 1) nor by short presses (needs 0x12 type 3, which no shipped tool sends)");
  { uint8_t rt[HG_ROUTINE_PACK_BYTES]; uint16_t rn = hg_routine_pack(&g.rt, rt, sizeof rt); hg_calm_t calm; hg_guardian_get_calm(&g, &calm);
    hg_guardian_init(&g, &P, &tw); hg_guardian_set_calm(&g, &calm); if (rn) hg_routine_unpack(&g.rt, rt, rn);   /* guardian_layer.inc:371-374 */
    minute(mod++, 20000, 0, 0, 0, 3.9f); }
  printf("INFO  C after console 'profile ...' (guardian re-init): state %u, family_alert %u, help %u\n", fw.last_out.state, fw.last_out.family_alert, g.help);
  CHECK(!(g.help == 0 && fw.last_out.family_alert == 0), "C console 'profile' must not clear a latched HELP / pending family alert (it does: guardian_layer.inc:374)");
  /* D */
  reset(); int saves = 0, nightly = 0;
  for (int m = 0; m < 1440; m++) {                    /* one real day; the 'clock' says a new day every minute at 06:00 */
    for (int s = 0; s < 60; s++) { hg_fw_sec_t x; memset(&x, 0, sizeof x); x.t1_c = 33.8f; x.t2_c = 32.3f; x.tair_c = 25; x.rh_pct = 45; x.a_mean = 1; x.a_n = 25; x.a_m2 = 0.02f; hg_fw_second(&fw, &x); }
    hg_fw_ctx_t c = { 360, 30000 + m, 0, 3.9f, 2, NULL, 0 }; hg_fw_act_t a; hg_fw_minute(&fw, &g, &tw, &acc, &c, 0, &a);
    saves += a.save_twin; nightly += a.nightly;
  }
  printf("INFO  D 1440 real minutes with a TIME frame per minute stepping the local day: nightly updates %d, twin saves requested %d\n", nightly, saves);
  CHECK(saves <= HG_FW_MAX_SAVES_DAY, "D <= 5 InternalFS twin saves per REAL day under a clock that jumps (got %d; the cap is per *local* day)", saves);
  /* E */
  reset(); mod = warm(); minute(mod++, 20000, 1, 3.0f, 0, 3.38f); int hap = -1;
  for (int k = 0; k < 6; k++) { minute(mod++, 20000, 1, 0, 0, 3.38f); if (fw.last_out.haptic) { hap = fw.last_out.haptic; break; } }
  printf("INFO  E VBAT 3.38 V: guardian state %u emits haptic %d (HG_HAP_SOFT = R4 A8.2 soft tick); 09 vibrate() returns early when pofHold (VBAT < 3.40 V)"
         " -> nothing plays\n", fw.last_out.state, hap);
  printf("%s\n", fails ? "SAFETY_E2E: FINDINGS" : "SAFETY_E2E: PASS");
  return 0;
}
