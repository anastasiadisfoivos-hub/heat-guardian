/* [FW-DEMO] Host run of the 0.9.16-demo heat-episode REPLAY: the embedded SIMULATED trace (fw/09_guardian/hg_demo_trace.h)
 * through the SAME code the band runs on `replay`: hg_fw_demo.c (input) -> hg_fw.c -> the FROZEN guardian (fz_*.c) ->
 * the alert layer (hg_fw_alert.c) -> the planner (hg_fw_eco.c), with the band's fresh demo state, the quiet warm-up and the
 * simulated clock. Prints the minute-by-minute table: what the band shows / buzzes and at which replay second.
 *   sh fw/tools/run_host_tests.sh   (section 8i)      or      test_demo [seconds per simulated minute] [table.md]
 * 0.9.17: + the action ladder and the keep-it-green gauge exactly as guardianMinute() steps them; argv[3] = comma list of
 * replay minutes after which she presses the button once (as uiShort(): hg_fw_button + hg_ld_press), e.g. "31".
 * Exit 1 if the episode never reaches a DRINK or COOL alert or never clears (the demo would show nothing).
 * [DEMO-NORESP] 0.9.17-demo-b7n: argv[4] = "noresp" (= the band's `replay noresp`: no presses at all): exit 1 unless the REAL
 * ladder, with nobody pressing, sends LD_REMIND, its 10-min repeat and LD_NOTE 2 "no response" (the phone's family SMS), and
 * the SIMULATION marker (frame byte 18 = HG_DEMO_X7_SIM) is set on ladder frames only. The marker is checked in BOTH modes
 * (plain `replay` too): every ladder event of the run, packed as the band sends it, must carry it.
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "hg_fw_demo.h"
#include "frozen/hg_guardian_cfg.h"
#include "hg_fw_ladder.h"
#include "hg_fw_ui.h"

static hg_ld_t LD; static hg_ga_lines_t GL; static uint8_t gaStep = HG_GA_UNKNOWN; static int8_t gaPos = 0;
static hg_guardian_t g; static hg_fw_t fw; static hg2_twin_t tw; static hg_twin_acc_t acc; static hg_al_t AL; static hg_plan_t PL;

static const char *ST[] = { "OK", "DRINK", "COOL", "CHECK", "DANGER", "IMOK", "NOT_WORN", "BATTERY", "HELP" };
static const char *SCR[] = { "OK", "DRINK", "COOL", "DANGER", "CHECK", "FAMILY", "IMOK", "NOT_WORN", "LOOSE", "BATTERY", "HELP", "NUDGE" };
static const char *HAP[] = { "-", "WATCH(2 long)", "COOL(3 long x2)", "CHECK(30 s)", "TICK", "SOFT" };
static const char *NUD[] = { "", "N1 brief", "N2 last cool hour", "N3 shutters", "N4 WATER «Πιείτε νερό»", "N5 air", "N6 A/C", "N7 evening", "N8 leave hot" };

int main(int argc, char **argv)
{
  const int S = argc > 1 ? atoi(argv[1]) : 2;
  FILE *md = argc > 2 && argv[2][0] ? fopen(argv[2], "w") : NULL;
  const char *presses = argc > 3 ? argv[3] : "";
  const int noresp = argc > 4 && !strcmp(argv[4], "noresp");
  int nr_remind = -1, nr_repeat = -1, nr_note = -1;
  if (noresp && presses[0]) { printf("TEST_DEMO FAIL: noresp with presses\n"); return 1; }
  int marked = 0;
  {
    for (int t = 1; t < 24; t++) {                  /* the marker: ladder types 17-21 only, x[0..6] untouched; through the real packer */
      uint8_t x[8] = { 1, 2, 3, 4, 5, 6, 0, 0 }; hg_demo_mark_x((uint8_t)t, x);
      hg_evring_t R; memset(&R, 0, sizeof R); uint8_t f[20]; hg_ev_pack(hg_ev_add_x(&R, 1u, (uint8_t)t, 2, x), 7, f);
      const int lad = t >= HG_EV_LD_REMIND && t <= HG_EV_LD_NOTE;
      if (f[18] != (lad ? HG_DEMO_X7_SIM : 0) || f[11] != 1 || f[16] != 6 || f[17] != 0) { printf("TEST_DEMO FAIL: SIM marker type %d byte18 0x%02x\n", t, f[18]); return 1; }
    }
    printf("== replay: SIM marker byte 18 = 0x%02X on ladder frames 17-21 only: ok\n", HG_DEMO_X7_SIM);
  }
  hg_ld_init(&LD);
  hg_demo_st_t s = { &fw, &g, &tw, &acc, &AL, &PL, 0 };
  hg_demo_init(&s);                                 /* the band's fresh demo state (same function) */
  for (int32_t k = hg_demo_first(); k < 0; k++) hg_demo_quiet_minute(&s, k);
  const hg_minute_out_t *o0 = &fw.last_out;
  printf("== warm-up %d calm min + %u pre-roll min (%02u:%02u-%02u:%02u): state %s level %u core %.2f f20 %.2f worn %u check %u\n", HG_DEMO_WARM, hg_demo_pre,
         hg_demo_mod(hg_demo_first()) / 60, hg_demo_mod(hg_demo_first()) % 60, hg_demo_mod(0) / 60, hg_demo_mod(0) % 60,
         ST[o0->state], o0->level, o0->core.core_now, o0->core.f20_eff, o0->worn, o0->check_reason);
  printf("== replay %u simulated minutes, %d s per minute (%d s total). SIMULATION input, frozen engine output.\n", hg_demo_n, S, hg_demo_n * S);
  if (md) fprintf(md, "| replay s | sim clock | sim truth core | band core est (f20) | frozen state / level | gauge colour (dot) | ladder | band shows | buzz | note |\n|---|---|---|---|---|---|---|---|---|---|\n");
  printf("  sec  clock  T1    T2    air   RH  HR    | truth core | est core f20  | state  lv scr     | buzz / event\n");
  int drink = 0, cool = 0, clear = 0, last_state = -1, last_scr = -1; uint8_t prev_check = 0, prev_fam = 0;
  for (int32_t k = 0; k < hg_demo_n; k++) {
    hg_demo_feed_minute(&s, k);
    hg_fw_ctx_t c; hg_demo_ctx(k, &c); hg_fw_act_t act; const uint32_t tms = hg_demo_ms(k);
    hg_fw_minute(&fw, &g, &tw, &acc, &c, tms, &act);
    const hg_minute_out_t *o = &fw.last_out;
    hg_al_in_t ai = { &fw.last_in, o, tw.rest_hr, NULL, c.minute_of_day, c.local_day, c.vbat, tms };
    hg_al_out_t ao; hg_al_minute(&AL, &ai, &ao);
    hg_plan_in_t pin; hg_demo_plan_in(&s, k, &pin);
    hg_plan_out_t po; hg_al_plan_minute(&AL, &ao, &PL, &pin, &po);
    if (po.missed) hg_al_event(&AL, HG_EV_NUDGE_MISSED, po.missed, tms);
    if (po.show) hg_al_event(&AL, HG_EV_NUDGE_SHOWN, po.show, tms);
    /* 0.9.17: ladder + gauge, as guardianMinute() */
    const int danger = o->level >= 3 || (o->check_reason & HG_CR_DANGER);
    const float f20 = (o->core.valid && o->worn) ? o->core.f20_eff : NAN;
    hg_ld_in_t li = { ao.present, (uint8_t)danger, (uint8_t)(o->level > 0 || AL.pres), f20 };
    hg_ld_out_t lo; hg_ld_minute(&LD, &li, &lo);
    hg_ga_lines(g.a_base, g.a_base_n, g.m_drink, g.m_cool, &GL);
    hg_ga_in_t gi = { f20, o->level, (uint8_t)danger, (uint8_t)(o->state == HG_ST_DRINK), (uint8_t)(o->state == HG_ST_COOL), (uint8_t)(f20 == f20) };
    int8_t gp = 0; uint8_t gs = hg_ga_step(&GL, &gi, gaStep, &gp);
    const int ga_changed = gs != gaStep; gaStep = gs; gaPos = gp;
    char ev[384] = "";
#define ADD(...) do { size_t L_ = strlen(ev); snprintf(ev + L_, sizeof ev - L_, __VA_ARGS__); } while (0)
    if (ao.present) { ADD("ALERT %s shown%s; ", ao.present == HG_ST_DRINK ? "DRINK «Πιείτε νερό»" : "COOL «Δροσιστείτε»", ao.soft ? " (soft)" : ""); if (ao.present == HG_ST_DRINK) drink++; else cool++; }
    if (ao.clear) { ADD("ALL-CLEAR «Πάλι όλα καλά» (peak %u, %u min); ", ao.clear_peak, ao.clear_min); clear++; }
    if (o->check_min != 0xFF && !prev_check) ADD("CHECK «Είστε καλά;» opens; ");
    if (o->family_alert && !prev_fam) ADD("FAMILY alert; ");
    if (po.show) ADD("nudge %s; ", NUD[po.show < 9 ? po.show : 0]);
    if (po.missed) ADD("nudge %u missed (10 min, nobody pressed); ", po.missed);
    for (int i = 0; i < ao.n_notes; i++) ADD("held %s/%s; ", hg_al_what_name(ao.notes[i].what), hg_al_reason_name(ao.notes[i].reason));
    if (o->state != last_state || o->screen != last_scr) ADD("frozen screen -> %s; ", SCR[o->screen < HG_SCR_N ? o->screen : 0]);
    if (ga_changed) ADD("GAUGE -> %s; ", hg_ga_colour(gs)->name);
    for (int i = 0; i < lo.n; i++) {
      ADD("LADDER %s arg %u; ", hg_ev_name(lo.ev[i].type), lo.ev[i].arg);
      { uint8_t x[8]; memcpy(x, lo.ev[i].x, 8); hg_demo_mark_x(lo.ev[i].type, x);   /* as ladderApply() during any replay */
        hg_evring_t R; memset(&R, 0, sizeof R); uint8_t f[20]; hg_ev_pack(hg_ev_add_x(&R, 1u, lo.ev[i].type, lo.ev[i].arg, x), 7, f);
        if (f[18] != HG_DEMO_X7_SIM || memcmp(f + 11, lo.ev[i].x, 7)) { printf("TEST_DEMO FAIL: replay ladder frame %s without the SIM marker\n", hg_ev_name(lo.ev[i].type)); return 1; }
        marked++; }
      if (lo.ev[i].type == HG_EV_LD_REMIND && lo.ev[i].x[4] == 0 && nr_remind < 0) nr_remind = k;
      if (lo.ev[i].type == HG_EV_LD_REMIND && lo.ev[i].x[4] == 1 && nr_repeat < 0) nr_repeat = k;
      if (lo.ev[i].type == HG_EV_LD_NOTE && lo.ev[i].arg == HG_LD_NOTE_NO_RESPONSE && nr_note < 0) nr_note = k;
    }
    if (lo.toast == HG_LD_TOAST_WORKED) ADD("«Μπράβο, δροσίζεστε» 10 s; ");
    if (lo.toast == HG_LD_TOAST_STILL) ADD("«Ακόμα ζεσταίνεστε» 6 s; ");
    if (lo.haptic) ADD("ladder buzz %s; ", hg_hp_pat(lo.haptic)->name);
    { const uint8_t r = hg_ld_reminder(&LD); const char *t = r == HG_LD_S_COOL ? "«Πηγαίνετε κάπου δροσερά»" : r == HG_LD_S_WATER ? "«Πιείτε νερό»" : "";
      static uint8_t prev_r = 0; if (r != prev_r && r) ADD("text on gauge %s; ", t); prev_r = r; }
    if (LD.state == HG_LD_ESC) ADD("ESCALATION screen; ");
    const hg_demo_row_t *r = hg_demo_row(k);
    const uint8_t hap = ao.haptic;
    printf("  %4d %02u:%02u %5.2f %5.2f %5.1f %3.0f %5.1f | %6.2f     | %6.2f %5.2f | %-6s %u  %-7s | %-12s %3d %-6s | %s %s\n", k * S, c.minute_of_day / 60, c.minute_of_day % 60,
           r->t1 / 100.0, r->t2 / 100.0, r->ta / 100.0, r->rh / 10.0, r->hr == HG_DEMO_NOHR ? NAN : r->hr / 10.0, r->core / 100.0,
           o->core.core_now, o->core.f20_eff, ST[o->state < 9 ? o->state : 0], o->level, SCR[o->screen < HG_SCR_N ? o->screen : 0],
           hg_ga_colour(gs)->name, gp, hg_ld_state_name(LD.state), hap ? HAP[hap < 6 ? hap : 0] : "", ev);
    if (md && (ev[0] || hap || lo.haptic || k == 0 || k == hg_demo_n - 1 || k % 10 == 0))
      fprintf(md, "| %d | %02u:%02u | %.2f | %.2f (%.2f) | %s / %u | %s (%d) | %s | %s | %s | %s |\n", k * S, c.minute_of_day / 60, c.minute_of_day % 60, r->core / 100.0,
              o->core.core_now, o->core.f20_eff, ST[o->state < 9 ? o->state : 0], o->level, hg_ga_colour(gs)->name, gp, hg_ld_state_name(LD.state),
              SCR[o->screen < HG_SCR_N ? o->screen : 0], hap ? HAP[hap < 6 ? hap : 0] : "-", ev[0] ? ev : "-");
    { char key[16]; snprintf(key, sizeof key, ",%d,", (int)k); char list[128]; snprintf(list, sizeof list, ",%s,", presses);
      if (strstr(list, key)) {                     /* she presses between this minute and the next (uiShort) */
        hg_fw_button(&fw, 1); hg_ld_out_t lp; int took = hg_ld_press(&LD, &lp);
        printf("  >>> PRESS at replay %d-%d s: ladder %s -> %s", (int)k * S, (int)(k + 1) * S - 1, took ? "took it" : "not its business", hg_ld_state_name(LD.state));
        for (int i = 0; i < lp.n; i++) printf(", %s arg %u", hg_ev_name(lp.ev[i].type), lp.ev[i].arg);
        printf("\n");
        if (md) fprintf(md, "| %d-%d | (press) | | | | | %s | | | button press: %s |\n", (int)k * S, (int)(k + 1) * S - 1, hg_ld_state_name(LD.state), took ? "ladder DONE (20-min check starts)" : "no ladder meaning");
      } }
    last_state = o->state; last_scr = o->screen; prev_check = o->check_min != 0xFF; prev_fam = o->family_alert;
  }
  const hg_al_score_t *sc = &AL.sc;
  printf("== score: sent drink %u cool %u cool_soft %u check %u family %u all_clear %u nudge %u; held persist %u one_evidence %u wet %u\n",
         sc->sent[HG_AL_K_DRINK], sc->sent[HG_AL_K_COOL], sc->sent[HG_AL_K_COOL_SOFT], sc->sent[HG_AL_K_CHECK], sc->sent[HG_AL_K_FAMILY],
         sc->sent[HG_AL_K_CLEAR], sc->sent[HG_AL_K_NUDGE], sc->held[HG_AL_R_PERSIST], sc->held[HG_AL_R_ONE_EV], sc->held[HG_AL_R_WET]);
  if (md) fclose(md);
  const int ok = (drink + cool) > 0 && clear > 0;
  if (!marked) { printf("TEST_DEMO FAIL: no ladder event to mark\n"); return 1; }
  printf("== replay: %d ladder frames, every one with the SIM marker 0x%02X in byte 18\n", marked, HG_DEMO_X7_SIM);
  if (noresp) {
    const int nok = ok && nr_remind >= 0 && nr_repeat == nr_remind + HG_LD_REPEAT_MIN && nr_note == nr_remind + HG_LD_NORESP_MIN;
    printf("TEST_DEMO_NORESP %s: no press; reminder min %d (%d s), repeat min %d (%d s), LD_NOTE 2 no-response min %d (%d s) at %d s per minute\n",
           nok ? "PASS" : "FAIL", nr_remind, nr_remind * S, nr_repeat, nr_repeat * S, nr_note, nr_note * S, S);
    return nok ? 0 : 1;
  }
  printf("TEST_DEMO %s: alerts shown drink %d cool %d, all-clear %d\n", ok ? "PASS" : "FAIL", drink, cool, clear);
  return ok ? 0 : 1;
}
