/* 0.9.17 (FW-UI) host test: the closed-loop action ladder (worked / not worked / no press / Danger skip / a press never
 * cancels a prediction), the "keep it green" gauge mapping (lines, steps, hysteresis, floors, dot, colours) and the
 * Her-Day-only planner (no clock-driven generic nudges). Simulated minutes, deterministic. */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include "hg_fw_ladder.h"
#include "hg_fw_eco.h"
#include "hg_fw_ui.h"
#include "frozen/hg_guardian.h"

static int fails = 0, passes = 0;
#define CHECK(c, ...) do { if (c) { passes++; printf("PASS "); } else { fails++; printf("FAIL "); } printf(__VA_ARGS__); printf("\n"); } while (0)

static hg_ld_t L; static hg_ld_out_t O;
typedef struct { int minute; uint8_t type, arg; uint8_t x[8]; } evr_t;
static evr_t E[256]; static int nE; static int minute;
static uint8_t lastHap, lastToast;
static void take(const hg_ld_out_t *o) {
  for (int i = 0; i < o->n && nE < 256; i++) { E[nE].minute = minute; E[nE].type = o->ev[i].type; E[nE].arg = o->ev[i].arg; memcpy(E[nE].x, o->ev[i].x, 8); nE++; }
  if (o->haptic) lastHap = o->haptic;
  if (o->toast) lastToast = o->toast;
}
static void reset(void) { hg_ld_init(&L); nE = 0; minute = 0; lastHap = lastToast = 0; }
static void tick(uint8_t present, uint8_t danger, uint8_t episode, float f20) {
  hg_ld_in_t in = { present, danger, episode, f20 }; hg_ld_minute(&L, &in, &O); take(&O); minute++;
}
static int prs(void) { hg_ld_out_t o; int r = hg_ld_press(&L, &o); take(&o); return r; }
static int cnt(uint8_t t, int arg) { int n = 0; for (int i = 0; i < nE; i++) if (E[i].type == t && (arg < 0 || E[i].arg == arg)) n++; return n; }
static int at(uint8_t t, int arg) { for (int i = 0; i < nE; i++) if (E[i].type == t && (arg < 0 || E[i].arg == arg)) return E[i].minute; return -1; }

static void test_ladder(void) {
  printf("-- ladder\n");
  /* L1 water, worked */
  reset();
  tick(HG_ST_DRINK, 0, 1, 37.80f);
  CHECK(L.state == HG_LD_REMIND && cnt(HG_EV_LD_REMIND, 1) == 1 && lastHap == HG_HP_WATCH && hg_ld_reminder(&L) == HG_LD_S_WATER, "L1 DRINK shown -> water reminder (EVENTS 17 arg 1, Watch pattern)");
  tick(0, 0, 1, 37.82f); tick(0, 0, 1, 37.84f);
  CHECK(prs() == 1 && L.state == HG_LD_CHECK && cnt(HG_EV_LD_DONE, 1) == 1 && lastHap == HG_HP_YES, "L1 her press = done (EVENTS 18), the 20 min check starts");
  for (int k = 0; k < 19; k++) tick(0, 0, 1, 37.86f);
  CHECK(cnt(HG_EV_LD_WORKED, -1) == 0, "L1 nothing decided before 20 min");
  tick(0, 0, 1, 37.87f);
  CHECK(cnt(HG_EV_LD_WORKED, 1) == 1 && lastToast == HG_LD_TOAST_WORKED && lastHap == HG_HP_WORKED && L.state == HG_LD_DONE,
        "L1 f20 +0.03 C in 20 min = stopped rising -> worked «Μπράβο, δροσίζεστε» (EVENTS 19)");
  tick(0, 0, 1, 37.86f); CHECK(L.state == HG_LD_DONE && nE == 3, "L1 the episode goes on: no new step, nothing new to say");
  tick(0, 0, 0, 37.5f); CHECK(L.state == HG_LD_IDLE, "L1 episode over -> idle");
  /* L2 water not worked -> cooler place -> still heating -> escalation */
  reset(); tick(HG_ST_DRINK, 0, 1, 37.80f); prs();
  for (int k = 0; k < 20; k++) tick(0, 0, 1, 37.80f + 0.01f * k);
  CHECK(cnt(HG_EV_LD_NOTE, HG_LD_NOTE_NOT_WORKED) == 1 && cnt(HG_EV_LD_REMIND, 2) == 1 && lastToast == HG_LD_TOAST_STILL && L.state == HG_LD_REMIND && L.step == HG_LD_S_COOL,
        "L2 still rising after water: «Ακόμα ζεσταίνεστε», quiet family note (EVENTS 21 arg 1), next step cooler place");
  prs();
  for (int k = 0; k < 20; k++) tick(0, 0, 1, 38.00f + 0.01f * k);
  CHECK(cnt(HG_EV_LD_ESCALATED, HG_LD_ESC_STILL_HEATING) == 1 && L.state == HG_LD_ESC && lastHap == HG_HP_URGENT,
        "L2 still rising in the cool: escalation (EVENTS 20 arg 2 = family alert), urgent pattern, no more waiting steps");
  CHECK(hg_ld_open(&L) && hg_ld_reminder(&L) == 0, "L2 escalation is an open alert (no off prompt), the screen is the escalation screen");
  /* L3 COOL first: cooler place, worked */
  reset(); tick(HG_ST_COOL, 0, 1, 38.4f);
  CHECK(cnt(HG_EV_LD_REMIND, 2) == 1 && lastHap == HG_HP_COOL, "L3 COOL shown -> cooler-place reminder (Cool pattern)");
  prs(); for (int k = 0; k < 20; k++) tick(0, 0, 1, 38.4f - 0.01f * k);
  CHECK(cnt(HG_EV_LD_WORKED, 2) == 1, "L3 falling -> worked (EVENTS 19 arg 2)");
  /* L4 no press */
  reset(); tick(HG_ST_DRINK, 0, 1, 37.8f);
  for (int k = 0; k < 60; k++) tick(0, 0, 1, 37.8f);
  CHECK(cnt(HG_EV_LD_REMIND, 1) == 2 && at(HG_EV_LD_REMIND, -1) == 0 && E[1].minute == 10 && E[1].x[4] == 1, "L4 no press: one repeat at 10 min (x[15] = 1)");
  CHECK(cnt(HG_EV_LD_NOTE, HG_LD_NOTE_NO_RESPONSE) == 1 && at(HG_EV_LD_NOTE, HG_LD_NOTE_NO_RESPONSE) == 20 && nE == 3, "L4 then the family note 'no response' at 20 min, and nothing more (60 min)");
  CHECK(prs() == 1 && L.state == HG_LD_CHECK, "L4 a late press still starts the 20 min check");
  /* L5 Danger skips the ladder */
  reset(); tick(HG_ST_DRINK, 0, 1, 37.8f); tick(0, 1, 1, 38.6f);
  CHECK(cnt(HG_EV_LD_ESCALATED, HG_LD_ESC_DANGER) == 1 && at(HG_EV_LD_ESCALATED, -1) == 1, "L5 Danger line crossed during a reminder: escalation at once (EVENTS 20 arg 1)");
  reset(); tick(0, 1, 1, 38.6f);
  CHECK(cnt(HG_EV_LD_ESCALATED, HG_LD_ESC_DANGER) == 1 && cnt(HG_EV_LD_REMIND, -1) == 0, "L5 from nothing: escalation at once, no waiting step");
  reset(); tick(HG_ST_DRINK, 0, 1, 37.8f); prs(); tick(0, 0, 1, 37.9f); tick(0, 1, 1, 38.6f);
  CHECK(cnt(HG_EV_LD_ESCALATED, HG_LD_ESC_DANGER) == 1 && L.state == HG_LD_ESC, "L5 during the 20 min check too");
  /* L6 a press never cancels a prediction */
  reset(); tick(0, 1, 1, 38.6f);
  CHECK(prs() == 1 && L.state == HG_LD_ESC && cnt(HG_EV_LD_NOTE, HG_LD_NOTE_RESPONSIVE) == 1 && lastHap == HG_HP_YES, "L6 press during escalation: family told 'responsive' (EVENTS 21 arg 3), escalation stays");
  for (int k = 0; k < 30; k++) tick(0, 1, 1, 38.6f);   /* the frozen CHECK may have taken the press (I'm OK); the Danger tier stays on */
  CHECK(L.state == HG_LD_ESC && cnt(HG_EV_LD_WORKED, -1) == 0, "L6 30 more Danger minutes: still escalated, nothing cleared by the press");
  prs(); CHECK(cnt(HG_EV_LD_NOTE, HG_LD_NOTE_RESPONSIVE) == 2 && L.state == HG_LD_ESC, "L6 every press is another 'responsive' note");
  tick(0, 0, 1, 38.70f);
  CHECK(L.state == HG_LD_ESC, "L6 Danger flag off but the forecast still above 20 min ago: still escalated");
  tick(0, 0, 1, 38.30f);
  CHECK(L.state == HG_LD_DONE && cnt(HG_EV_LD_WORKED, HG_LD_S_ESC) == 1, "L6 only the forecast clears it: below 20 min ago -> worked (EVENTS 19 arg 3)");
  reset(); tick(0, 0, 1, 37.8f); tick(HG_ST_COOL, 0, 1, 38.4f); prs();
  for (int k = 0; k < 20; k++) tick(0, 0, 1, 38.4f + 0.01f * k);   /* -> escalated (still heating) */
  for (int k = 0; k < 25; k++) tick(0, 0, 1, 38.6f + 0.01f * k);   /* still rising, no Danger flag */
  CHECK(L.state == HG_LD_ESC, "L6 a glue escalation (no frozen Danger) stays while the forecast rises");
  /* L7 a press in the 20 min check is not the ladder's business; the check goes on */
  reset(); tick(HG_ST_DRINK, 0, 1, 37.8f); prs(); tick(0, 0, 1, 37.8f);
  CHECK(prs() == 0 && L.state == HG_LD_CHECK && L.chk_min == 1, "L7 a press during the 20 min check changes nothing");
  /* L8 the episode ends */
  reset(); tick(HG_ST_DRINK, 0, 1, 37.8f); tick(0, 0, 0, 37.5f);
  CHECK(L.state == HG_LD_IDLE && cnt(HG_EV_LD_WORKED, -1) == 0, "L8 episode over before a press: idle, no 'worked' claimed");
  reset(); tick(HG_ST_DRINK, 0, 1, 37.8f); prs(); tick(0, 0, 0, 37.5f);
  CHECK(L.state == HG_LD_IDLE && cnt(HG_EV_LD_WORKED, 1) == 1, "L8 episode over during the check: worked");
  /* L9 no forecast at check time */
  reset(); tick(HG_ST_DRINK, 0, 1, 37.8f); prs();
  for (int k = 0; k < 30; k++) tick(0, 0, 1, NAN);
  CHECK(L.state == HG_LD_CHECK && cnt(HG_EV_LD_ESCALATED, -1) == 0 && cnt(HG_EV_LD_NOTE, -1) == 0, "L9 band off (no f20) at the check: waits, never escalates on nothing");
  tick(0, 0, 1, 37.8f); CHECK(cnt(HG_EV_LD_WORKED, 1) == 1, "L9 back on and flat: worked");
  /* L10 worse during the water check */
  reset(); tick(HG_ST_DRINK, 0, 1, 37.8f); prs(); tick(0, 0, 1, 38.0f); tick(HG_ST_COOL, 0, 1, 38.4f);
  CHECK(cnt(HG_EV_LD_NOTE, HG_LD_NOTE_NOT_WORKED) == 1 && L.step == HG_LD_S_COOL && L.state == HG_LD_REMIND, "L10 COOL during the water check: next step at once");
  /* L11 frame payload */
  reset(); tick(HG_ST_DRINK, 0, 1, 37.81f);
  CHECK((int16_t)(E[0].x[0] | (E[0].x[1] << 8)) == 3781 && (int16_t)(E[0].x[2] | (E[0].x[3] << 8)) == INT16_MIN, "L11 EVENTS x: f20 x100 = 3781, no reference = INT16_MIN");
  CHECK(strcmp(hg_ev_name(HG_EV_LD_NOTE), "LD_NOTE") == 0 && strcmp(hg_ev_name(HG_EV_HAPTIC_LOST), "HAPTIC_LOST") == 0 && strcmp(hg_ev_name(22), "?") == 0, "L11 event names 14-21");
}

static void test_gauge(void) {
  printf("-- gauge\n");
  hg_ga_lines_t Ln; hg_ga_lines(NAN, 0, 0.0f, 0.0f, &Ln);
  CHECK(fabsf(Ln.line_w - 37.75f) < 1e-4f && fabsf(Ln.line_c - 38.35f) < 1e-4f && fabsf(Ln.line_d - 38.5f) < 1e-4f, "G1 not learned: lines 37.75 / 38.35 / 38.50");
  hg_ga_lines_t Lp; hg_ga_lines(37.20f, 5, 0.1f, 0.3f, &Lp);
  CHECK(fabsf(Lp.line_w - (37.20f + 0.24f - 0.1f)) < 1e-4f && fabsf(Lp.line_c - (38.35f - 0.20f)) < 1e-4f, "G1 learned calm 37.20, margins: her lines %.2f / %.2f (margin capped 0.20)", Lp.line_w, Lp.line_c);
  /* G2 sweep: monotonic */
  uint8_t prev = HG_GA_UNKNOWN; int mono = 1, ups = 0; int8_t pos, lastpos = -11; int posmono = 1;
  for (float f = 36.8f; f <= 38.9f; f += 0.01f) {
    hg_ga_in_t in = { f, 0, 0, 0, 0, 1 }; uint8_t s = hg_ga_step(&Ln, &in, prev, &pos);
    if (prev != HG_GA_UNKNOWN && s < prev) mono = 0;
    if (s != prev) ups++;
    prev = s;
    if (pos < lastpos) posmono = 0;
    lastpos = pos;
  }
  CHECK(mono && ups == 5 && prev == 4, "G2 rising forecast: green -> yellow-green -> yellow -> orange -> red, once each");
  CHECK(posmono, "G2 the dot only moves right as the forecast rises");
  struct { float f; uint8_t s; } P[] = { {37.50f, 0}, {37.61f, 1}, {37.80f, 2}, {38.40f, 3}, {38.55f, 4} };
  int ok = 1; for (unsigned i = 0; i < 5; i++) { hg_ga_in_t in = { P[i].f, 0, 0, 0, 0, 1 }; if (hg_ga_step(&Ln, &in, HG_GA_UNKNOWN, NULL) != P[i].s) ok = 0; }
  CHECK(ok, "G2 37.50 green, 37.61 yellow-green, 37.80 yellow, 38.40 orange, 38.55 red");
  /* G3 hysteresis */
  hg_ga_in_t a = { 37.76f, 0, 0, 0, 0, 1 }; uint8_t s = hg_ga_step(&Ln, &a, HG_GA_UNKNOWN, NULL);
  a.f20 = 37.72f; uint8_t s2 = hg_ga_step(&Ln, &a, s, NULL); a.f20 = 37.69f; uint8_t s3 = hg_ga_step(&Ln, &a, s2, NULL);
  CHECK(s == 2 && s2 == 2 && s3 == 1, "G3 down a step only 0.05 C under the line (37.72 stays yellow, 37.69 yellow-green)");
  int changes = 0; prev = 2; for (int k = 0; k < 200; k++) { hg_ga_in_t n = { 37.75f + ((k * 7919) % 41 - 20) / 1000.0f, 0, 0, 0, 0, 1 }; uint8_t x = hg_ga_step(&Ln, &n, prev, NULL); if (x != prev) changes++; prev = x; }
  CHECK(changes <= 1, "G3 +-0.02 C noise on a line: %d step change(s) in 200 min (no flicker, no wake storm)", changes);
  /* G4 floors from the frozen state */
  hg_ga_in_t b = { 37.30f, 0, 0, 1, 0, 1 }; CHECK(hg_ga_step(&Ln, &b, HG_GA_UNKNOWN, NULL) == 2, "G4 frozen DRINK shown: at least yellow");
  hg_ga_in_t c = { 37.30f, 2, 0, 0, 1, 1 }; CHECK(hg_ga_step(&Ln, &c, HG_GA_UNKNOWN, NULL) == 3, "G4 COOL: at least orange");
  hg_ga_in_t d = { 37.30f, 3, 1, 0, 0, 1 }; CHECK(hg_ga_step(&Ln, &d, HG_GA_UNKNOWN, NULL) == 4, "G4 Danger: red");
  hg_ga_in_t e = { NAN, 0, 0, 0, 0, 0 }; CHECK(hg_ga_step(&Ln, &e, 2, &pos) == HG_GA_UNKNOWN, "G4 no forecast, no tier: grey (unknown), no dot");
  hg_ga_in_t f = { NAN, 2, 0, 0, 1, 0 }; CHECK(hg_ga_step(&Ln, &f, HG_GA_UNKNOWN, NULL) == 3, "G4 no forecast but COOL: orange");
  /* G5 dot */
  hg_ga_in_t g1 = { Ln.centre, 0, 0, 0, 0, 1 }, g2 = { Ln.line_d, 0, 0, 0, 0, 1 }, g3 = { 36.0f, 0, 0, 0, 0, 1 }; int8_t p1, p2, p3;
  hg_ga_step(&Ln, &g1, HG_GA_UNKNOWN, &p1); hg_ga_step(&Ln, &g2, HG_GA_UNKNOWN, &p2); hg_ga_step(&Ln, &g3, HG_GA_UNKNOWN, &p3);
  CHECK(p1 == 0 && p2 == 10 && p3 == -10, "G5 the dot: centre = balanced (0), the Danger line = +10, far below = -10");
  /* G6 colours: different in lightness too, readable text */
  float Y[6]; int dl = 1, ct = 1;
  for (int i = 0; i < 6; i++) Y[i] = hg_ga_luminance(hg_ga_colour(i < 5 ? (uint8_t)i : HG_GA_UNKNOWN));
  for (int i = 0; i < 5; i++) for (int j = i + 1; j < 5; j++) if (fabsf(Y[i] - Y[j]) < 0.05f) dl = 0;
  for (int i = 0; i < 6; i++) { const hg_ga_col_t *k = hg_ga_colour(i < 5 ? (uint8_t)i : HG_GA_UNKNOWN);
    float cr = k->text_white ? 1.05f / (Y[i] + 0.05f) : (Y[i] + 0.05f) / 0.05f; printf("     %-12s L=%.2f text %s contrast %.1f\n", k->name, Y[i], k->text_white ? "white" : "black", cr); if (cr < 4.5f) ct = 0; }
  CHECK(dl, "G6 the 5 colours differ in lightness (>= 0.05 relative luminance apart: works without colour vision)");
  CHECK(ct, "G6 text on every colour has contrast >= 4.5:1");
}

/* Her Day only: a hot day with no plan gives no nudge; a plan outing gives N1, tomorrow's plan N7 */
static uint8_t FC[72];
static void test_planner(void) {
  printf("-- planner: Her Day only (owner decision Nov 19 18:04)\n");
  for (int h = 0; h < 24; h++) { FC[3 * h] = 33; FC[3 * h + 1] = 40; FC[3 * h + 2] = 1 | 2; }
  for (int mode = 0; mode < 2; mode++) {
    hg_plan_t p; hg_plan_init(&p); int shown[HG_N_COUNT] = { 0 }; int total = 0;
    hg_dpday_t tomorrow; memset(&tomorrow, 0, sizeof tomorrow);
    for (int m = 0; m < 1440; m++) {
      hg_plan_in_t in; memset(&in, 0, sizeof in);
      in.mod = (uint16_t)m; in.day = 20000; in.fc72 = FC; in.room_c = 31.0f; in.home_out = 0xFF; in.herday_only = (uint8_t)mode;
      hg_seed_t sd; hg_seed_clear(&sd); sd.flags = 1; in.seed = &sd;      /* A/C at home stated: N6 would fire */
      hg_plan_out_t o; hg_plan_minute(&p, &in, &o);
      if (o.show) { shown[o.show]++; total++; hg_plan_done(&p, (uint16_t)m); }
    }
    if (mode == 0) CHECK(total > 0 && (shown[HG_N_WATER] || shown[HG_N_AC] || shown[HG_N_AIR]), "P0 control (flag off, 0.9.16 behaviour): %d generic nudges on a hot day", total);
    else CHECK(total == 0, "P1 Her Day only, hot day, no plan: no nudge at all (no water / air / A/C / last-cool / brief)");
  }
  /* with a plan */
  hg_plan_t p; hg_plan_init(&p); int shown[HG_N_COUNT] = { 0 };
  hg_dpday_t today, tom; memset(&today, 0, sizeof today); memset(&tom, 0, sizeof tom);
  today.n = 1; today.it[0].kind = HG_DPK_OUTING_SHIFT; today.it[0].place = HG_PL_MARKET; today.it[0].usual_h = 11; today.it[0].sugg_h = 9; today.it[0].sugg_m = 30; today.it[0].dir = HG_DIR_BEFORE;
  tom = today;
  for (int m = 0; m < 1440; m++) {
    hg_plan_in_t in; memset(&in, 0, sizeof in);
    in.mod = (uint16_t)m; in.day = 20000; in.fc72 = FC; in.room_c = 31.0f; in.home_out = 0xFF; in.herday_only = 1; in.dp_today = &today; in.dp_tomorrow = &tom;
    hg_plan_out_t o; hg_plan_minute(&p, &in, &o);
    if (o.show) { shown[o.show]++; hg_plan_done(&p, (uint16_t)m); }
  }
  int other = 0; for (int i = 0; i < HG_N_COUNT; i++) if (i != HG_N_BRIEF && i != HG_N_EVENING) other += shown[i];
  CHECK(shown[HG_N_BRIEF] == 1 && shown[HG_N_EVENING] == 1 && other == 0, "P2 with today's and tomorrow's plan: N1 «Σήμερα: αγορά πριν τις 09:30» and N7 only");
}

int main(void) {
  test_ladder(); test_gauge(); test_planner();
  printf("TEST_LADDER: %d passed, %d failed\n", passes, fails);
  printf("%s\n", fails ? "TEST_LADDER: FAIL" : "TEST_LADDER: PASS");
  return fails != 0;
}
