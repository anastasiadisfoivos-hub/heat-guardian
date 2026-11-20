/* 0.9.17 (FW-UI) host test: button state machine (every timing edge of the owner's three actions), haptic sequencer
 * (priorities, pre-emption, overlay tick, repeats, low battery, silent motor), wrist-raise detector on synthetic traces.
 * Simulated time, deterministic (fixed LCG seed). */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include "hg_fw_ui.h"

static int fails = 0, passes = 0;
#define CHECK(c, ...) do { if (c) { passes++; printf("PASS "); } else { fails++; printf("FAIL "); } printf(__VA_ARGS__); printf("\n"); } while (0)

/* ------------------------------------------------------------------ button harness */
typedef struct { uint32_t a, b; } iv_t;           /* pressed in [a, b) (contact time, release time) */
static iv_t IV[64]; static int nIV;
static int pressed_at(uint32_t t) { for (int i = 0; i < nIV; i++) if ((int32_t)(t - IV[i].a) >= 0 && (int32_t)(t - IV[i].b) < 0) return 1; return 0; }
typedef struct { hg_ui_ev_t e; uint32_t seen; } rec_t;
static rec_t R[512]; static int nR;
static hg_ui_t U;
static void run(uint32_t from, uint32_t to, uint32_t step) {
  for (uint32_t t = from; (int32_t)(to - t) > 0; t += step ? step : (hg_ui_active(&U, t) ? 5u : 20u)) {   /* 0 = adaptive, as the hgui task */
    hg_ui_sample(&U, (uint8_t)pressed_at(t), t);
    hg_ui_ev_t e; while (hg_ui_pop(&U, &e)) if (nR < 512) { R[nR].e = e; R[nR].seen = t; nR++; }
  }
}
static void reset(void) { hg_ui_init(&U); nIV = 0; nR = 0; }
static void press(uint32_t a, uint32_t dur) { IV[nIV].a = a; IV[nIV].b = a + dur; nIV++; }
static int count(uint8_t type) { int n = 0; for (int i = 0; i < nR; i++) if (R[i].e.type == type) n++; return n; }
static const rec_t *first(uint8_t type) { for (int i = 0; i < nR; i++) if (R[i].e.type == type) return &R[i]; return NULL; }
static int meaningful(void) { int n = 0; for (int i = 0; i < nR; i++) if (R[i].e.type != HG_UI_E_DOWN && R[i].e.type != HG_UI_E_UP) n++; return n; }

static void test_button(uint32_t T0) {
  printf("-- button (t0 = %lu)\n", (unsigned long)T0);
  /* B1 a plain press */
  reset(); press(T0 + 100, 200); run(T0, T0 + 2000, 5);
  const rec_t *d = first(HG_UI_E_DOWN);
  CHECK(count(HG_UI_E_SHORT) == 1 && meaningful() == 1, "B1 a 200 ms press = exactly one SHORT");
  CHECK(d && d->seen - (T0 + 100) <= 10, "B1 press-down accepted %lu ms after contact (<= 10 at 5 ms polling)", d ? (unsigned long)(d->seen - (T0 + 100)) : 999ul);
  CHECK(first(HG_UI_E_SHORT) && first(HG_UI_E_SHORT)->e.dur_ms == 200, "B1 press length measured contact -> release (200 ms)");
  /* B1b 20 ms idle polling (the hgui task sleeps 20 ms when nothing is going on) */
  reset(); press(T0 + 107, 200); run(T0, T0 + 2000, 0);
  d = first(HG_UI_E_DOWN);
  CHECK(d && d->seen - (T0 + 107) <= 30, "B1b adaptive polling (20 ms idle, 5 ms once something moves): down seen %lu ms after contact (<= 30)", d ? (unsigned long)(d->seen - (T0 + 107)) : 999ul);
  /* B2 contact bounce (1 ms sampling): 5 bounces of 2 ms inside the first 10 ms = one press */
  reset(); for (int k = 0; k < 5; k++) press(T0 + 100 + 4 * k, 2); press(T0 + 120, 300); run(T0, T0 + 2000, 1);
  CHECK(count(HG_UI_E_DOWN) == 1 && count(HG_UI_E_SHORT) == 1, "B2 contact bounce = one press (downs %d, shorts %d)", count(HG_UI_E_DOWN), count(HG_UI_E_SHORT));
  /* B2b a 6 ms glitch (motor / cable) is not a press */
  reset(); press(T0 + 100, 6); run(T0, T0 + 1000, 1);
  CHECK(count(HG_UI_E_DOWN) == 0, "B2b a 6 ms glitch is not a press");
  /* B3 release bounce: a 20 ms open inside a hold is merged */
  reset(); press(T0 + 100, 400); press(T0 + 520, 400); run(T0, T0 + 3000, 1);
  CHECK(count(HG_UI_E_DOWN) == 1 && count(HG_UI_E_SHORT) == 1 && first(HG_UI_E_SHORT)->e.dur_ms == 820, "B3 a 20 ms opening inside a press is merged (one 820 ms press)");
  /* B4 the lengths */
  static const struct { uint32_t dur; uint8_t want; } L[] = { {1195, HG_UI_E_SHORT}, {1205, HG_UI_E_MID}, {2000, HG_UI_E_MID}, {2990, HG_UI_E_MID}, {3010, HG_UI_E_HELP}, {6000, HG_UI_E_HELP} };
  for (unsigned i = 0; i < sizeof L / sizeof L[0]; i++) {
    reset(); press(T0 + 100, L[i].dur); run(T0, T0 + 9000, 5);
    CHECK(count(L[i].want) == 1 && meaningful() == 1, "B4 released after %lu ms -> %s only", (unsigned long)L[i].dur, hg_ui_ev_name(L[i].want));
  }
  reset(); press(T0 + 100, 5000); run(T0, T0 + 9000, 5);
  const rec_t *h = first(HG_UI_E_HELP);
  CHECK(h && h->seen - (T0 + 100) >= 3000 && h->seen - (T0 + 100) <= 3010, "B4 HELP fires while still held, at %lu ms", h ? (unsigned long)(h->seen - (T0 + 100)) : 0ul);
  /* B5 double press */
  reset(); press(T0 + 100, 150); press(T0 + 100 + 150 + 600, 150); run(T0, T0 + 3000, 5);
  CHECK(count(HG_UI_E_PWR_PROMPT) == 1 && count(HG_UI_E_SHORT) == 1, "B5 two presses 600 ms apart = SHORT + off prompt (the 2nd is not a SHORT)");
  reset(); press(T0 + 100, 150); press(T0 + 100 + 150 + 850, 150); run(T0, T0 + 3000, 5);
  CHECK(count(HG_UI_E_PWR_PROMPT) == 1 && count(HG_UI_E_SHORT) == 1, "B5 two presses 850 ms apart = off prompt (demo-b7u gap 900 ms)");
  reset(); press(T0 + 100, 150); press(T0 + 100 + 150 + 960, 150); run(T0, T0 + 3000, 5);
  CHECK(count(HG_UI_E_PWR_PROMPT) == 0 && count(HG_UI_E_SHORT) == 2, "B5 two presses 960 ms apart = two SHORTs");
  reset(); press(T0 + 100, 1300); press(T0 + 1500, 150); run(T0, T0 + 4000, 5);
  CHECK(count(HG_UI_E_PWR_PROMPT) == 0, "B5 a MID then a press is not a double press");
  /* B6 the prompt */
  reset(); press(T0 + 100, 150); press(T0 + 500, 150); press(T0 + 1800, 200); run(T0, T0 + 9000, 5);
  CHECK(count(HG_UI_E_PWR_PROMPT) == 1 && count(HG_UI_E_PWR_CONFIRM) == 1 && count(HG_UI_E_SHORT) == 1, "B6 prompt, one press 1.15 s later = CONFIRM");
  reset(); press(T0 + 100, 150); press(T0 + 500, 150); press(T0 + 850, 120); run(T0, T0 + 9000, 5);
  CHECK(count(HG_UI_E_PWR_CONFIRM) == 0 && count(HG_UI_E_PWR_CANCEL) == 1 && first(HG_UI_E_PWR_CANCEL)->e.arg == HG_UI_R_GUARD, "B6 a 3rd fast tap (200 ms after the prompt) cancels, never confirms");
  reset(); press(T0 + 100, 150); press(T0 + 500, 150); press(T0 + 1150, 150); run(T0, T0 + 9000, 5);
  CHECK(count(HG_UI_E_PWR_CONFIRM) == 1, "B6 a press 500 ms after the prompt opened confirms (demo-b7u guard 400 ms; 0.9.17's 700 cancelled it)");
  reset(); press(T0 + 100, 150); press(T0 + 500, 150); run(T0, T0 + 9000, 5);
  const rec_t *c = first(HG_UI_E_PWR_CANCEL); const rec_t *pp = first(HG_UI_E_PWR_PROMPT);
  CHECK(c && c->e.arg == HG_UI_R_TIMEOUT && pp && c->seen - pp->e.t_ms >= 5000 && c->seen - pp->e.t_ms <= 5010, "B6 no input for 5 s closes the prompt (%lu ms)", c && pp ? (unsigned long)(c->seen - pp->e.t_ms) : 0ul);
  reset(); press(T0 + 100, 150); press(T0 + 500, 150); press(T0 + 3000, 1500); run(T0, T0 + 12000, 5);
  c = first(HG_UI_E_PWR_CANCEL);
  CHECK(count(HG_UI_E_PWR_CONFIRM) == 0 && c && c->seen >= T0 + 4500 + 5000, "B6 a 1.5 s hold at the prompt does nothing and restarts the 5 s");
  reset(); press(T0 + 100, 150); press(T0 + 500, 150); press(T0 + 1500, 4000); run(T0, T0 + 9000, 5);
  CHECK(count(HG_UI_E_PWR_CONFIRM) == 0 && count(HG_UI_E_HELP) == 1 && first(HG_UI_E_PWR_CANCEL) && first(HG_UI_E_PWR_CANCEL)->e.arg == HG_UI_R_HELP, "B6 a 3 s hold at the prompt = HELP (prompt closed)");
  /* B7 refusals */
  reset(); { hg_ui_ctx_t x = { 0, 1 }; hg_ui_ctx(&U, &x, T0); } press(T0 + 100, 150); press(T0 + 500, 150); run(T0, T0 + 3000, 5);
  CHECK(count(HG_UI_E_PWR_PROMPT) == 0 && count(HG_UI_E_SHORT) == 2 && first(HG_UI_E_PWR_REFUSED)->e.arg == HG_UI_R_ALERT, "B7 during an alert a double press = two presses (refused: alert)");
  reset(); press(T0 + 100, 3500); press(T0 + 5000, 150); press(T0 + 5400, 150); run(T0, T0 + 8000, 5);
  CHECK(count(HG_UI_E_HELP) == 1 && count(HG_UI_E_PWR_PROMPT) == 0 && first(HG_UI_E_PWR_REFUSED)->e.arg == HG_UI_R_HELP, "B7 during HELP: refused (help)");
  /* HELP, cancelled at 12 s, then double presses at +30 s (refused) and +61 s (prompt) (demo-b7u: 60 s block) */
  reset(); press(T0 + 100, 3500); press(T0 + 12000, 3500);
  press(T0 + 15100 + 30000, 150); press(T0 + 15100 + 30400, 150);
  press(T0 + 15100 + 61000, 150); press(T0 + 15100 + 61400, 150);
  run(T0, T0 + 15100 + 70000, 5);
  CHECK(count(HG_UI_E_HELP_CANCEL) == 1 && count(HG_UI_E_PWR_REFUSED) == 1 && first(HG_UI_E_PWR_REFUSED)->e.arg == HG_UI_R_AFTER_HELP && count(HG_UI_E_PWR_PROMPT) == 1,
        "B7 after a HELP: refused for 60 s, allowed after");
  /* B8 cancel lock */
  reset(); press(T0 + 100, 3200); press(T0 + 4000, 3200); run(T0, T0 + 9000, 5);
  CHECK(count(HG_UI_E_HELP) == 1 && count(HG_UI_E_HELP_LOCKED) == 1 && count(HG_UI_E_HELP_CANCEL) == 0, "B8 a 2nd 3 s hold 4 s after HELP is LOCKED (no cancel)");
  reset(); press(T0 + 100, 3200); press(T0 + 10200, 3200); run(T0, T0 + 15000, 5);
  CHECK(count(HG_UI_E_HELP_CANCEL) == 1, "B8 a 2nd 3 s hold reaching 3 s at 10.1 s after HELP cancels");
  reset(); press(T0 + 100, 3200); press(T0 + 6000, 3200); run(T0, T0 + 9500, 5);
  CHECK(count(HG_UI_E_HELP_CANCEL) == 0 && count(HG_UI_E_HELP_LOCKED) == 1, "B8 a hold reaching 3 s at 9 s after HELP is LOCKED (edge)");
  reset(); press(T0 + 100, 20000); run(T0, T0 + 22000, 5);
  CHECK(count(HG_UI_E_HELP) == 1 && meaningful() == 1, "B8 one 20 s hold = one HELP, never a cancel");
  reset(); { hg_ui_ctx_t x = { 1, 0 }; hg_ui_ctx(&U, &x, T0 + 50); } press(T0 + 1000, 3200); press(T0 + 11000, 3200); run(T0, T0 + 15000, 5);
  CHECK(count(HG_UI_E_HELP_LOCKED) == 1 && count(HG_UI_E_HELP_CANCEL) == 1 && count(HG_UI_E_HELP) == 0, "B9 HELP from the phone: lock counted from when the band saw it");
  /* B10 the wake press */
  reset(); hg_ui_wake_hold(&U, T0); press(T0, 2000); press(T0 + 2300, 150); press(T0 + 3000, 150); run(T0, T0 + 4000, 5);
  CHECK(count(HG_UI_E_SHORT) == 1 && count(HG_UI_E_HELP) == 0 && first(HG_UI_E_SHORT)->e.t_ms >= T0 + 3000, "B10 the wake press (even 2 s) and a press 300 ms after it are ignored; the next works");
  /* B11 an alert opening while the prompt is up closes it */
  reset(); press(T0 + 100, 150); press(T0 + 500, 150); run(T0, T0 + 1500, 5);
  { hg_ui_ctx_t x = { 0, 1 }; hg_ui_ctx(&U, &x, T0 + 1500); } run(T0 + 1500, T0 + 2000, 5);
  CHECK(first(HG_UI_E_PWR_CANCEL) && first(HG_UI_E_PWR_CANCEL)->e.arg == HG_UI_R_ALERT, "B11 an alert closes the open prompt");
}

/* B12: random edge streams, the invariants */
static uint32_t rng = 12345;
static uint32_t rnd(uint32_t n) { rng = rng * 1103515245u + 12345u; return (rng >> 8) % n; }
static void test_fuzz(void) {
  int bad_confirm = 0, bad_hold = 0, bad_help = 0, bad_alert = 0, bad_short = 0, streams = 20000, confirms = 0, prompts = 0;
  for (int s = 0; s < streams; s++) {
    reset(); uint32_t t = 1000; int alert = (s % 5) == 0;
    if (alert) { hg_ui_ctx_t x = { 0, 1 }; hg_ui_ctx(&U, &x, 0); }
    int n = 2 + (int)rnd(8);
    for (int k = 0; k < n && nIV < 60; k++) {
      uint32_t dur = rnd(4) == 0 ? 2000 + rnd(5000) : 40 + rnd(1400);
      if (dur > 2950 && dur < 3050) dur = 3100;
      press(t, dur); t += dur + 40 + rnd(1500);
    }
    run(0, t + 7000, 5);
    int open = 0;
    for (int i = 0; i < nR; i++) {
      uint8_t ty = R[i].e.type;
      if (ty == HG_UI_E_PWR_PROMPT) { open = 1; prompts++; if (alert) bad_alert++; }
      if (ty == HG_UI_E_PWR_CONFIRM) { confirms++; if (!open) bad_confirm++; open = 0; if (R[i].e.dur_ms >= HG_UI_SHORT_MAX_MS) bad_hold++; }
      if (ty == HG_UI_E_PWR_CANCEL) open = 0;
      if ((ty == HG_UI_E_SHORT || ty == HG_UI_E_PWR_CONFIRM) && R[i].e.dur_ms >= HG_UI_HELP_MS) bad_short++;
    }
    /* every press >= 3 s gave exactly one of HELP / CANCEL / LOCKED */
    int holds = 0; for (int i = 0; i < nIV; i++) if (IV[i].b - IV[i].a >= HG_UI_HELP_MS + 10) holds++;
    int got = count(HG_UI_E_HELP) + count(HG_UI_E_HELP_CANCEL) + count(HG_UI_E_HELP_LOCKED);
    if (got != holds) bad_help++;
  }
  CHECK(!bad_confirm, "B12 %d random streams: a CONFIRM always follows an open prompt (%d prompts, %d confirms)", streams, prompts, confirms);
  CHECK(!bad_hold, "B12 a hold never confirms the power-off");
  CHECK(!bad_help, "B12 every hold >= 3 s gives exactly one HELP / cancel / locked (%d streams wrong)", bad_help);
  CHECK(!bad_alert, "B12 never an off prompt during an alert");
  CHECK(!bad_short, "B12 a press >= 3 s is never a SHORT or a confirm");
}

/* ------------------------------------------------------------------ haptics harness */
typedef struct { uint32_t now, end; int playing, go_n, stop_n, reinit_n, fail_go, fail_reinit, busy_err, stuck; uint8_t last[8]; uint32_t go_t[64]; uint8_t go_w0[64]; } mock_t;
static mock_t M;
static uint32_t wave_ms(const uint8_t w[8]) {
  uint32_t ms = 0;
  for (int i = 0; i < 8 && w[i]; i++) {
    if (w[i] & 0x80) ms += 10u * (w[i] & 0x7F);
    else ms += w[i] == 16 ? 1000 : w[i] == 15 ? 750 : w[i] == 52 ? 1000 : w[i] <= 2 ? 30 : 120;
  }
  return ms;
}
static int m_go(void *c, const uint8_t w[8]) { (void)c; if (M.fail_go) { M.fail_go--; return -1; } memcpy(M.last, w, 8); M.playing = 1; M.end = M.now + wave_ms(w);
  if (M.go_n < 64) { M.go_t[M.go_n] = M.now; M.go_w0[M.go_n] = w[0]; } M.go_n++; return 0; }
static int m_busy(void *c) { (void)c; if (M.busy_err) return -1; if (M.stuck) return 1; if (M.playing && (int32_t)(M.now - M.end) >= 0) M.playing = 0; return M.playing; }
static void m_stop(void *c) { (void)c; M.playing = 0; M.stop_n++; }
static int m_reinit(void *c) { (void)c; M.reinit_n++; if (M.fail_reinit) return -1; return 0; }
static const hg_hp_drv_t DRV = { m_go, m_busy, m_stop, m_reinit, NULL };
static hg_hp_t H;
static void hrun(uint32_t from, uint32_t to) { for (M.now = from; (int32_t)(to - M.now) > 0; M.now += 5) hg_hp_step(&H, &DRV, M.now); }
static void hreset(void) { memset(&M, 0, sizeof M); hg_hp_init(&H); }

static void test_haptics(void) {
  printf("-- haptic sequencer\n");
  hreset(); M.now = 1000; hg_hp_request(&H, &DRV, HG_HP_TICK, 0, 0, 0, 1000);
  CHECK(M.go_n == 1 && M.go_t[0] == 1000 && M.go_w0[0] == 2, "H1 tick from idle: GO written in the same call (0 ms), effect 2 (today's press strength)");
  hrun(1000, 1500); CHECK(!hg_hp_active(&H) && H.done_id == HG_HP_TICK, "H1 tick done");
  /* H2 priorities */
  hreset(); M.now = 0; hg_hp_request(&H, &DRV, HG_HP_URGENT, 0, 0, 0, 0); hrun(0, 500);
  int r = hg_hp_request(&H, &DRV, HG_HP_COOL, 0, 0, 0, M.now);
  CHECK(r == 0 && H.id == HG_HP_URGENT, "H2 COOL (2) during URGENT (3) is dropped");
  r = hg_hp_request(&H, &DRV, HG_HP_TICK, 0, 0, 0, M.now);
  CHECK(r == 0 && M.go_n == 1, "H2 a tick while URGENT is mid-pulse is skipped");
  uint32_t t0 = M.now; r = hg_hp_request(&H, &DRV, HG_HP_HELP, 0, 0, 0, M.now); hrun(t0, t0 + 200);
  CHECK(r == 1 && M.stop_n == 1 && M.go_n == 2 && M.go_t[1] - t0 >= 60 && M.go_t[1] - t0 <= 65 && H.id == HG_HP_HELP, "H2 HELP (4) pre-empts URGENT: stop, 60 ms, start (%lu ms)", (unsigned long)(M.go_t[1] - t0));
  hreset(); hg_hp_request(&H, &DRV, HG_HP_COOL, 0, 0, 0, 0); hrun(0, 300); t0 = M.now;
  r = hg_hp_request(&H, &DRV, HG_HP_WATCH, 0, 0, 0, M.now); hrun(t0, t0 + 100);
  CHECK(r == 1 && H.id == HG_HP_WATCH && M.stop_n == 1, "H2 an equal priority request replaces the current pattern");
  /* H3 overlay tick in a gap */
  hreset(); hg_hp_request(&H, &DRV, HG_HP_COOL, 0, 0, 0, 0); hrun(0, 4000);   /* first 3 pulses ~2.85 s, then the 10 s gap */
  CHECK(H.phase == HG_HP_GAP, "H3 COOL is in its 10 s gap");
  r = hg_hp_request(&H, &DRV, HG_HP_TICK, 0, 0, 0, M.now);
  CHECK(r == 2 && M.go_n == 2 && M.go_w0[1] == 2, "H3 a press in the gap of an alert pattern gets its tick (overlay)");
  hrun(M.now, 16000);
  CHECK(M.go_n == 3 && M.go_w0[2] == 15 && H.id == HG_HP_COOL, "H3 the COOL repeat still comes after the overlay tick");
  CHECK(M.go_t[2] >= 2850 + 10000 && M.go_t[2] <= 2850 + 10000 + 30, "H3 COOL repeat 10 s after the first ended (at %lu ms)", (unsigned long)M.go_t[2]);
  /* H5 URGENT total */
  hreset(); hg_hp_request(&H, &DRV, HG_HP_URGENT, 0, 0, 0, 0); hrun(0, 60000);
  CHECK(M.go_n == 4 && H.last_end >= 29000 && H.last_end <= 30000, "H5 URGENT = 4 x 7 s with 0.5 s gaps, ends at %lu ms (~30 s)", (unsigned long)H.last_end);
  /* H6 low battery */
  hreset(); hg_hp_request(&H, &DRV, HG_HP_URGENT, 1, 0, 0, 0); hrun(0, 60000);
  CHECK(M.go_n == 4 && M.go_w0[0] == 2 && M.last[1] == 0 && M.go_t[1] - M.go_t[0] >= 3000, "H6 low battery: every repeat one soft click, >= 3 s apart, never silent");
  hreset(); hg_hp_request(&H, &DRV, HG_HP_TICK, 1, 0, 0, 0); CHECK(M.go_w0[0] == 2, "H6 the tick is the same on a low battery");
  /* H7 silent motor */
  hreset(); M.fail_go = 1; hg_hp_request(&H, &DRV, HG_HP_URGENT, 0, 0, 0, 0);
  CHECK(M.reinit_n == 1 && M.go_n == 1 && H.fails == 0 && hg_hp_active(&H), "H7 GO fails once: driver re-initialised, pattern plays");
  hreset(); M.fail_go = 5; M.fail_reinit = 1; hg_hp_request(&H, &DRV, HG_HP_URGENT, 0, 0, 0, 0);
  CHECK(H.fails == 1 && H.fail_id == HG_HP_URGENT && !hg_hp_active(&H), "H7 GO + re-init fail: reported as HAP_FAIL (the caller flashes the screen), never silent");
  hreset(); M.fail_go = 1; M.fail_reinit = 1; hg_hp_request(&H, &DRV, HG_HP_COOL, 0, 0, 0, 0); hrun(0, 100);
  CHECK(H.fail_id == HG_HP_COOL, "H7 also for COOL");
  /* H8 busy read errors */
  hreset(); hg_hp_request(&H, &DRV, HG_HP_WATCH, 0, 0, 0, 0); M.busy_err = 1; hrun(0, 200);
  CHECK(!hg_hp_active(&H), "H8 3 failed status reads end the pattern (no hang)");
  /* H9 stop */
  hreset(); hg_hp_request(&H, &DRV, HG_HP_URGENT, 0, 0, 0, 0); hrun(0, 100); hg_hp_stop(&H, &DRV, 2, M.now);
  CHECK(hg_hp_active(&H), "H9 stop(max 2) leaves URGENT (3) playing");
  hg_hp_stop(&H, &DRV, 3, M.now); CHECK(!hg_hp_active(&H) && !M.playing, "H9 stop(max 3) stops it");
  /* H10 raw */
  hreset(); hg_hp_request(&H, &DRV, HG_HP_RAW, 0, 47, 1000, 0); hrun(0, 5000);
  CHECK(M.go_w0[0] == 47 && M.go_n >= 4 && M.go_n <= 10 && H.last_end <= 1300, "H10 vib 47 1000: effect 47 repeated for ~1 s (%d times, ends %lu)", M.go_n, (unsigned long)H.last_end);
  hreset(); hg_hp_request(&H, &DRV, HG_HP_RAW, 0, 14, 0, 0); hrun(0, 5000); CHECK(M.go_n == 1 && M.go_w0[0] == 14, "H10 vib 14: once");
  /* H11 stuck */
  hreset(); hg_hp_request(&H, &DRV, HG_HP_YES, 0, 0, 0, 0); M.stuck = 1; hrun(0, 9000);
  CHECK(!hg_hp_active(&H) && M.stop_n == 1, "H11 a pattern that never ends is stopped at 8 s");
  /* H12 the names */
  CHECK(hg_hp_find("urgent") == HG_HP_URGENT && hg_hp_find("tick") == HG_HP_TICK && hg_hp_find("bogus") == 0, "H12 pattern names for `vib <name>`");
  int distinct = 1; for (int a = 1; a < HG_HP_RAW; a++) for (int b = a + 1; b < HG_HP_RAW; b++)
    if (a != HG_HP_URGENT && b != HG_HP_HELP_URGENT && memcmp(hg_hp_pat(a)->wave, hg_hp_pat(b)->wave, 8) == 0 && hg_hp_pat(a)->reps == hg_hp_pat(b)->reps) distinct = 0;
  CHECK(distinct, "H12 every pattern is a different rhythm (HELP_URGENT = URGENT at HELP priority)");
}

/* ------------------------------------------------------------------ wrist raise */
static hg_rz_t RZ;
static float nz(void) { return ((float)rnd(1000) / 1000.0f - 0.5f) * 0.02f; }
/* angle a (deg): 0 = face to the side (arm hanging), 90 = face to the sky; extra = |a| added along gravity */
static int feed(uint32_t t, float a_deg, float extra) {
  float r = a_deg * 3.14159265f / 180.0f, m = 1.0f + extra;
  return hg_rz_sample(&RZ, -cosf(r) * m + nz(), nz(), sinf(r) * m + nz(), t);
}
static void test_raise(void) {
  printf("-- wrist raise (25 Hz)\n");
  int w = 0; uint32_t t = 0, tw = 0;
  hg_rz_init(&RZ, 2, 1);
  for (; t < 2000; t += 40) w += feed(t, 0, 0);
  for (int k = 0; k <= 10; k++, t += 40) w += feed(t, 9.0f * k, 0.15f * sinf(3.14159f * k / 10.0f));
  uint32_t up = t;
  for (; t < up + 3000; t += 40) { int x = feed(t, 90, 0); if (x && !tw) tw = t; w += x; }
  CHECK(w == 1 && tw - up <= 400, "R1 raise in 0.4 s and look: one wake %lu ms after the face is up", (unsigned long)(tw - up));
  /* R2 walking 60 s, arm swinging */
  hg_rz_init(&RZ, 2, 1); w = 0;
  for (t = 0; t < 60000; t += 40) {
    float ph = (float)t / 1100.0f * 6.2831853f, step = fmodf((float)t, 550.0f);
    w += feed(t, 40.0f + 38.0f * sinf(ph), 0.45f * expf(-(step / 60.0f) * (step / 60.0f)) - 0.1f * sinf(ph * 2.0f));
  }
  CHECK(w == 0, "R2 60 s of walking with arm swing: no wake (%d)", w);
  /* R2b walking with the face up most of the time (carrying a bag in front) */
  hg_rz_init(&RZ, 2, 1); w = 0;
  for (t = 0; t < 60000; t += 40) { float step = fmodf((float)t, 520.0f); float ph = (float)t / 1040.0f * 6.2831853f;
    w += feed(t, 60.0f + 30.0f * sinf(ph), 0.4f * expf(-(step / 60.0f) * (step / 60.0f))); }
  CHECK(w == 0, "R2b 60 s of walking, face swinging 30-90 deg: no wake (%d)", w);
  /* R3 a slow roll in bed (4 s) */
  hg_rz_init(&RZ, 2, 1); w = 0;
  for (t = 0; t < 2000; t += 40) w += feed(t, 0, 0);
  for (int k = 0; k <= 100; k++, t += 40) w += feed(t, 0.9f * k, 0);
  for (uint32_t e = t + 5000; t < e; t += 40) w += feed(t, 90, 0);
  CHECK(w == 0, "R3 turning slowly onto the back (4 s): no wake");
  /* R4 lying still face up */
  hg_rz_init(&RZ, 2, 1); w = 0; for (t = 0; t < 60000; t += 40) w += feed(t, 90, 0);
  CHECK(w == 0, "R4 60 s face up and still from the start: no wake");
  /* R5 two raises, 5 s apart, arm lowered between: 2; a re-raise within 3 s: not again */
  hg_rz_init(&RZ, 2, 1); w = 0; t = 0;
  for (int rep = 0; rep < 2; rep++) {
    for (uint32_t e = t + 1500; t < e; t += 40) w += feed(t, 0, 0);
    for (int k = 0; k <= 8; k++, t += 40) w += feed(t, 11.25f * k, 0);
    for (uint32_t e = t + 2000; t < e; t += 40) w += feed(t, 90, 0);
  }
  CHECK(w == 2, "R5 two raises: two wakes (%d)", w);
  for (int k = 0; k <= 5; k++, t += 40) w += feed(t, 90 - 15.0f * k, 0);
  for (int k = 0; k <= 5; k++, t += 40) w += feed(t, 15.0f + 15.0f * k, 0);
  for (uint32_t e = t + 400; t < e; t += 40) w += feed(t, 90, 0);
  CHECK(w == 2, "R5 a quick re-raise inside 3 s does not wake again");
  /* R6 stop walking, then raise */
  hg_rz_init(&RZ, 2, 1); w = 0;
  for (t = 0; t < 10000; t += 40) { float step = fmodf((float)t, 550.0f), ph = (float)t / 1100.0f * 6.2831853f;
    w += feed(t, 30.0f * sinf(ph), 0.45f * expf(-(step / 60.0f) * (step / 60.0f))); }
  for (int k = 0; k <= 10; k++, t += 40) w += feed(t, 9.0f * k, 0.1f);
  for (uint32_t e = t + 2000; t < e; t += 40) w += feed(t, 90, 0);
  CHECK(w == 1, "R6 walking, stop, raise and look: one wake");
  /* R7 the axis is configurable (a band worn the other way round) */
  hg_rz_init(&RZ, 2, -1); w = 0;
  for (t = 0; t < 2000; t += 40) w += hg_rz_sample(&RZ, -1, 0, 0, t);
  for (int k = 0; k <= 10; k++, t += 40) { float r = 9.0f * k * 3.14159265f / 180.0f; w += hg_rz_sample(&RZ, -cosf(r), 0, -sinf(r), t); }
  for (uint32_t e = t + 2000; t < e; t += 40) w += hg_rz_sample(&RZ, 0, 0, -1, t);
  CHECK(w == 1, "R7 face axis -z: one wake");
}

int main(void) {
  test_button(0);
  test_button(0xFFFFFFFFu - 5000u);   /* across the uptime wrap of the 32-bit millisecond counter */
  test_fuzz();
  test_haptics();
  test_raise();
  printf("TEST_UI: %d passed, %d failed\n", passes, fails);
  printf("%s\n", fails ? "TEST_UI: FAIL" : "TEST_UI: PASS");
  return fails != 0;
}
