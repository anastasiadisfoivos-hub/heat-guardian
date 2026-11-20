/* [b7t: 0.9.17-demo-b7t, branch b17-demo-b7t (first: b7n, commit 8947e2c)] argv: S presses mode(usb|ble) noresp(0|1). ble = exactly what a Mac page gets over
 * Bluetooth NUS on a fast link: the replies to its command + the `#R` / `#E` lines (demoStart/demoLine/demoService); the
 * `# DEMO` evLog lines are USB-only in b7n. usb = the `# DEMO` stream (+ BLE lines are not on USB).
 * SIM-STAGE host emitter: the band's `replay` through the SAME code as fw/tools/test_demo.c (hg_fw_demo.c -> hg_fw.c ->
 * frozen guardian -> alert layer -> planner -> ladder -> gauge), printing the USB serial lines with the firmware's own
 * format strings (09_guardian.ino: evLog "# DEMO " prefix while a replay runs, demoMinute(), ladderApply(), ecoEventX(),
 * uiShort()). argv: S (s per sim minute) presses ("31,70" or "") */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "hg_fw_demo.h"
#include "frozen/hg_guardian_cfg.h"
#include "hg_fw_ladder.h"
#include "hg_fw_ui.h"
#include "hg_fw_eco.h"
static hg_ld_t LD; static hg_ga_lines_t GL; static uint8_t gaStep = HG_GA_UNKNOWN; static int8_t gaPos = 0;
static hg_guardian_t g; static hg_fw_t fw; static hg2_twin_t tw; static hg_twin_acc_t acc; static hg_al_t AL; static hg_plan_t PL;
static const char *STN[] = { "OK", "DRINK", "COOL", "CHECK", "DANGER", "IMOK", "NOT_WORN", "BATTERY", "HELP" };
static int BLE = 0; static char DMev[48]; static int DMfam = 0;
static unsigned seq = 100; static unsigned long unix0 = 1795000000UL; static int S = 2; static int32_t curk = 0;
#define DEMO(...) do { if (!BLE) { printf("# DEMO "); printf(__VA_ARGS__); printf("\n"); } } while (0)
#define BLEF(...) do { if (BLE) printf(__VA_ARGS__); } while (0)
static void evt(uint8_t type, uint8_t arg) { { size_t L = strlen(DMev); snprintf(DMev + L, sizeof DMev - L, "%s%s.%u", L ? "," : "", hg_ev_name(type), arg); if (type == HG_EV_LD_NOTE || type == HG_EV_LD_ESCALATED) DMfam = 1; }
  ++seq; DEMO("EVT seq=%u type=%u %s arg=%u unix=%lu", seq, type, hg_ev_name(type), arg, unix0 + (unsigned long)(curk * S)); }
static void ladderApply(const hg_ld_out_t *lo) { for (int i = 0; i < lo->n; i++) { DEMO("LADDER %s arg=%u state=%s", hg_ev_name(lo->ev[i].type), lo->ev[i].arg, hg_ld_state_name(LD.state)); evt(lo->ev[i].type, lo->ev[i].arg); } }
int main(int argc, char **argv)
{
  S = argc > 1 ? atoi(argv[1]) : 2; const char *presses = argc > 2 ? argv[2] : "";
  BLE = argc > 3 && !strcmp(argv[3], "ble"); const int noresp = argc > 4 && atoi(argv[4]);
  hg_ld_init(&LD);
  hg_demo_st_t s = { &fw, &g, &tw, &acc, &AL, &PL, 0 };
  hg_demo_init(&s);
  printf("# REPLAY started (%lu s per simulated minute, %lu s in all); `replay stop` = back to live now\n", (unsigned long)S, (unsigned long)(S * hg_demo_n));
  if (noresp) {
    DEMO("REPLAY noresp: she does not respond (short presses ignored); the real ladder decides: reminder -> repeat at 10 min -> "
          "LD_NOTE no-response (family SMS) at 20 min; ladder EVENTS marked SIMULATION (byte 18 = 0x%02X)", HG_DEMO_X7_SIM);
    printf("# REPLAY noresp: no presses; first reminder ~%lu s, repeat ~%lu s, no-response note ~%lu s after the warm-up\n",
           (unsigned long)(25 * S), (unsigned long)(35 * S), (unsigned long)(45 * S));   /* b7t: 09_guardian.ino demoStart() */
  }
  BLEF("#R start el=%s nr=%u s=%lu n=%u t0=%02u:%02u\n", HG_DEMO_ELDER, noresp, (unsigned long)S, hg_demo_n, hg_demo_start_mod / 60, hg_demo_start_mod % 60);
  { char l[176]; snprintf(l, sizeof l, "REPLAY start: SIMULATED heat episode (sim/velders person, %u min from %02u:%02u), %lu s per simulated minute; "
        "warm-up %ld quiet minutes; frozen engine, real screen/buzz/alerts/BLE; nothing stored, twin never saved",
        hg_demo_n, hg_demo_start_mod / 60, hg_demo_start_mod % 60, (unsigned long)S, (long)-hg_demo_first()); if (!BLE) printf("# DEMO %s\n", l); }
  for (int32_t k = hg_demo_first(); k < 0; k++) hg_demo_quiet_minute(&s, k);
  DMev[0] = 0; DMfam = 0;
  BLEF("#R warm done st=%s\n", STN[fw.last_out.state < 9 ? fw.last_out.state : 0]);
  DEMO("REPLAY warm-up done: state %s; showing %02u:%02u-%02u:%02u", STN[fw.last_out.state < 9 ? fw.last_out.state : 0], hg_demo_start_mod / 60, hg_demo_start_mod % 60,
       hg_demo_mod(hg_demo_n - 1) / 60, hg_demo_mod(hg_demo_n - 1) % 60);
  int last_state = 0xFF, last_scr = 0xFF;
  for (int32_t k = 0; k < hg_demo_n; k++) {
    curk = k;
    hg_demo_feed_minute(&s, k);
    hg_fw_ctx_t c; hg_demo_ctx(k, &c); hg_fw_act_t act; const uint32_t tms = hg_demo_ms(k);
    hg_fw_minute(&fw, &g, &tw, &acc, &c, tms, &act);
    const hg_minute_out_t *o = &fw.last_out;
    hg_al_in_t ai = { &fw.last_in, o, tw.rest_hr, NULL, c.minute_of_day, c.local_day, c.vbat, tms };
    hg_al_out_t ao; hg_al_minute(&AL, &ai, &ao);
    if (o->state != last_state || o->screen != last_scr) {
      DEMO("STATE %u screen %u level %u tiers %u core %.2f sd %.2f f20 %.2f why 0x%02x worn %u check %u family %u",
           o->state, o->screen, o->level, o->tiers, o->core.core_now, o->core.sd_now, o->core.f20_eff, o->why, o->worn, o->check_reason, o->family_alert);
      if (o->state != last_state && o->state != HG_ST_OK && o->state != HG_ST_IMOK && o->state != HG_ST_DRINK && o->state != HG_ST_COOL) evt(HG_EV_WARN_SHOWN, o->state);
      last_state = o->state; last_scr = o->screen;
    }
    char vb[48];
    if (ao.present) { DEMO("ALERT %s shown%s (persisted; valid=%s f20 %.2f)", ao.present == HG_ST_DRINK ? "DRINK" : "COOL", ao.soft ? " soft (one kind of evidence)" : "",
                           hg_al_valid_text(AL.valid, vb, sizeof vb), o->core.f20_eff); evt(HG_EV_WARN_SHOWN, ao.present); }
    if (ao.clear) { DEMO("ALERT all-clear peak=%u minutes=%u family=%u tick=%u", ao.clear_peak, ao.clear_min, ao.clear_family, ao.clear_tick); evt(HG_EV_ALL_CLEAR, ao.clear_peak); }
    const int danger = o->level >= 3 || (o->check_reason & HG_CR_DANGER);
    const float f20 = (o->core.valid && o->worn) ? o->core.f20_eff : NAN;
    hg_ld_in_t li = { ao.present, (uint8_t)danger, (uint8_t)(o->level > 0 || AL.pres), f20 };
    hg_ld_out_t lo; hg_ld_minute(&LD, &li, &lo);
    hg_ga_lines(g.a_base, g.a_base_n, g.m_drink, g.m_cool, &GL);
    hg_ga_in_t gi = { f20, o->level, (uint8_t)danger, (uint8_t)(o->state == HG_ST_DRINK), (uint8_t)(o->state == HG_ST_COOL), (uint8_t)(f20 == f20) };
    int8_t gp = 0; uint8_t gs = hg_ga_step(&GL, &gi, gaStep, &gp);
    if (gs != gaStep || gp != gaPos) {
      int wake = gs != gaStep && gs != HG_GA_UNKNOWN && gaStep != HG_GA_UNKNOWN;
      if (gs != gaStep) DEMO("GAUGE %s -> %s f20 %.2f dot %d lines %.2f/%.2f/%.2f%s", hg_ga_colour(gaStep)->name, hg_ga_colour(gs)->name, f20, gp,
                             GL.line_w, GL.line_c, GL.line_d, wake ? " (screen woken)" : "");
      gaStep = gs; gaPos = gp;
    }
    ladderApply(&lo);
    /* ecoMinute(): planner, alertNotes(), planOut() */
    hg_plan_in_t pin; hg_demo_plan_in(&s, k, &pin);
    hg_plan_out_t po; hg_al_plan_minute(&AL, &ao, &PL, &pin, &po);
    hg_al_valid_text(AL.valid, vb, sizeof vb);
    for (int i = 0; i < ao.n_notes; i++) {
      const hg_al_note_t *n = &ao.notes[i];
      if (n->reason == 0) { DEMO("ALERT %s hold limit reached: shown anyway (arg %u) valid=%s", hg_al_what_name(n->what), n->arg, vb); continue; }
      DEMO("ALERT %s %s reason=%s arg=%u valid=%s", hg_al_what_name(n->what), n->what == HG_AL_W_CHECK ? "audit (passed through, NOT held)" : "held", hg_al_reason_name(n->reason), n->arg, vb);
    }
    if (po.missed) { hg_al_event(&AL, HG_EV_NUDGE_MISSED, po.missed, tms); evt(HG_EV_NUDGE_MISSED, po.missed); }
    if (po.show) { hg_al_event(&AL, HG_EV_NUDGE_SHOWN, po.show, tms); evt(HG_EV_NUDGE_SHOWN, po.show); }
    const hg_demo_row_t *r = hg_demo_row(k);
    if (!BLE) printf("# DEMO %02u:%02u t=%lus | SIM input T1 %.2f T2 %.2f air %.1f RH %.0f HR %.0f | SIM true core %.2f | band core %.2f f20 %.2f -> %s level %u\n",
       hg_demo_mod(k) / 60, hg_demo_mod(k) % 60, (unsigned long)(k * S), r->t1 / 100.0f, r->t2 / 100.0f, r->ta / 100.0f, r->rh / 10.0f,
       r->hr == HG_DEMO_NOHR ? NAN : r->hr / 10.0f, r->core / 100.0f, o->core.core_now, o->core.f20_eff, STN[o->state < 9 ? o->state : 0], o->level);
    { const uint8_t rr = hg_ld_reminder(&LD); const char *rm = rr == HG_LD_S_WATER ? "water" : rr == HG_LD_S_COOL ? "cool" : "-";
      const int fam = DMfam || o->family_alert;   /* demoLine(), fast link: every minute */
      BLEF("#R k=%ld t=%02u:%02u c=%.2f f=%.2f sc=%.2f st=%s lv=%u ld=%s rm=%s ga=%s dot=%d fam=%u nr=%u b=%u\n", (long)k,
           hg_demo_mod(k) / 60, hg_demo_mod(k) % 60, o->core.core_now, o->core.f20_eff, r->core / 100.0f, STN[o->state < 9 ? o->state : 0], o->level,
           hg_ld_state_name(LD.state), rm, hg_ga_colour(gaStep)->name, (int)gaPos, fam ? 1 : 0, noresp, 0);
      if (DMev[0]) { BLEF("#E k=%ld fam=%u ev=%s\n", (long)k, fam ? 1 : 0, DMev); DMev[0] = 0; DMfam = 0; } else if (fam) DMfam = 0; }
    if (!noresp) { char key[16]; snprintf(key, sizeof key, ",%d,", (int)k); char list[128]; snprintf(list, sizeof list, ",%s,", presses);
      if (strstr(list, key)) {   /* uiShort(): hg_fw_button + hg_ld_press -> ladderApply -> BUTTON line */
        hg_fw_button(&fw, 1); hg_ld_out_t lp;
        if (hg_ld_press(&LD, &lp)) { int esc = LD.state == HG_LD_ESC; ladderApply(&lp); DEMO("BUTTON press -> ladder %s (%s)", esc ? "responsive" : "done", hg_ld_state_name(LD.state)); }
      } }
  }
  DEMO("REPLAY end of the episode: this screen stays 2 min, then live (or `replay stop`)");
  BLEF("#R end\n");
  return 0;
}
