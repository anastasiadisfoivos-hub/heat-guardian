/* Host test of the 0.9.9 alert-quality rules layer (fw/09_guardian/hg_fw_alert.c) on top of the FROZEN guardian (through the
 * same fz_*.c wrappers as the sketch), the glue (hg_fw.c) and the planner (hg_fw_eco.c).
 *   sh fw/tools/run_host_tests.sh   (section 8d)
 * Part A: STAGED SCENES (the .csv files in fw/09_guardian/scenes): each scene is replayed second by second through hg_fw -> frozen guardian ->
 *         rules layer -> planner, after a calm 24 h warm-up (so the Marble Danger path is armed, as on a worn band). The sequence
 *         of interruptions (buzzes) must equal the scene's "expect=" line. The same replay WITHOUT the rules layer (= 0.9.8
 *         behaviour) is printed next to it, so the table shows what the layer removed.
 * Part B: unit checks on hand-made minutes: validity holds, bounded holds, persistence reset, hysteresis, two evidence,
 *         CHECK pass-through even on invalid input, all-clear once, scorecard + EVENTS payloads.
 * Usage: test_alerts <scenes dir> [table.md]
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "hg_fw.h"
#include "hg_fw_eco.h"
#include "hg_fw_alert.h"
#include "frozen/hg_guardian_cfg.h"   /* HG_HAP_* */

static int fails = 0, passes = 0;
#define CHECK(c, ...) do { if (c) { printf("PASS  "); passes++; } else { printf("FAIL  "); fails++; } printf(__VA_ARGS__); printf("\n"); } while (0)

/* ------------------------------------------------------------------ scene files */
#define NCOL 10
typedef struct { float m, v[NCOL]; } kf_t;
typedef struct { char name[32], expect[160]; kf_t k[64]; int nk, start_mod, warm; } scene_t;

static int scene_load(const char *fn, scene_t *s)
{
  FILE *f = fopen(fn, "r"); if (!f) return -1;
  memset(s, 0, sizeof *s); s->warm = 1440;
  const char *b = strrchr(fn, '/'); b = b ? b + 1 : fn; snprintf(s->name, sizeof s->name, "%.*s", (int)(strcspn(b, ".")), b);
  char l[512];
  while (fgets(l, sizeof l, f)) {
    if (l[0] == '#') {
      char *p;
      if ((p = strstr(l, "expect="))) { p += 7; snprintf(s->expect, sizeof s->expect, "%s", p); s->expect[strcspn(s->expect, " \r\n")] = 0; }
      if ((p = strstr(l, "start="))) { int h, m; if (sscanf(p + 6, "%d:%d", &h, &m) == 2) s->start_mod = h * 60 + m; }
      if ((p = strstr(l, "warmup="))) s->warm = atoi(p + 7);
      continue;
    }
    if (l[0] < '0' || l[0] > '9' || s->nk >= 64) continue;
    kf_t *k = &s->k[s->nk]; char *tok = strtok(l, ","); k->m = (float)atof(tok);
    for (int i = 0; i < NCOL; i++) { tok = strtok(NULL, ",\r\n"); k->v[i] = (tok && tok[0] != '-') ? (float)atof(tok) : NAN; }
    if (isnan(k->v[9])) k->v[9] = 0;
    s->nk++;
  }
  fclose(f);
  return s->nk;
}
static void scene_at(const scene_t *s, float t, float *v)   /* linear between keyframes; hr_q / button step */
{
  if (t <= s->k[0].m) { memcpy(v, s->k[0].v, sizeof s->k[0].v); return; }
  for (int i = 1; i < s->nk; i++) if (t <= s->k[i].m) {
    const kf_t *a = &s->k[i - 1], *b = &s->k[i]; float u = (t - a->m) / (b->m - a->m);
    for (int j = 0; j < NCOL; j++) { float x = a->v[j], y = b->v[j]; v[j] = (isnan(x) || isnan(y)) ? (u < 0.5f ? x : y) : x + u * (y - x); }
    v[5] = u < 1.0f ? a->v[5] : b->v[5]; v[9] = 0; return;
  }
  memcpy(v, s->k[s->nk - 1].v, sizeof s->k[0].v);
}
static int scene_button(const scene_t *s, int minute) { for (int i = 0; i < s->nk; i++) if ((int)s->k[i].m == minute && s->k[i].v[9] > 0) return (int)s->k[i].v[9]; return 0; }

/* ------------------------------------------------------------------ replay */
static uint32_t rng;
static float ur(void) { rng = rng * 1664525u + 1013904223u; return (float)((rng >> 8) & 0xFFFFFF) / 16777216.0f; }
static hg_guardian_t g; static hg_fw_t fw; static hg2_twin_t tw; static hg_twin_acc_t acc; static hg_al_t AL; static hg_plan_t PL;

typedef struct { char seq[400], tl[400]; int n_alerts, n_buzz, n_held, n_unknown, first_min, frozen_first_min; hg_al_score_t sc; char held_txt[300]; } run_t;

static void seq_add(run_t *r, const char *lab, int k)
{
  r->n_alerts++; if (r->first_min < 0) r->first_min = k;
  { size_t T = strlen(r->tl); if (T < sizeof r->tl - 24) snprintf(r->tl + T, sizeof r->tl - T, "%s%s@%d", T ? " " : "", lab, k); }
  size_t L = strlen(r->seq); const char *last = strrchr(r->seq, ',');
  last = last ? last + 1 : r->seq;
  if (L && strcmp(last, lab) == 0) return;          /* consecutive duplicates collapsed in the sequence (still counted) */
  snprintf(r->seq + L, sizeof r->seq - L, "%s%s", L ? "," : "", lab);
}

static void run_scene(const scene_t *s, int gated, run_t *r)
{
  memset(r, 0, sizeof *r); r->first_min = -1; r->frozen_first_min = -1;
  rng = 12345u;
  hg2_profile_t p = { 75.0f, 0.0f, 26.0f, 0 };      /* the target wearer (README default) */
  hg_twin_defaults(&tw); hg_twin_acc_init(&acc); hg_guardian_init(&g, &p, &tw); hg_fw_init(&fw); hg_al_init(&AL); hg_plan_init(&PL);
  const int dur = (int)s->k[s->nk - 1].m; uint32_t tms = 0;
  uint8_t prev_check = 0, prev_fam = 0;
  for (int k = -s->warm; k <= dur; k++) {
    const int amod = s->start_mod + k; const int32_t day = 20000 + (amod < 0 ? -1 : amod / 1440); const uint16_t mod = (uint16_t)(((amod % 1440) + 1440) % 1440);
    float v[NCOL];
    if (k < 0) { int night = mod < 7 * 60 || mod >= 23 * 60; float c[NCOL] = { 33.8f, 32.2f, 25.0f, 45, night ? 58.0f : 68.0f, 4, 0.5f, night ? 0.001f : 0.03f, 10, 0 }; memcpy(v, c, sizeof c); }
    /* a press during this minute: answers an open CHECK (I'm OK), else a press on an open nudge = DONE (the sketch's uiButton) */
    const int btn = k >= 0 ? scene_button(s, k) : 0;
    const uint32_t press_ms = tms + 30000u;
    if (btn == 1) {
      if (fw.last_out.check_min != 0xFF) { hg_fw_button(&fw, 1); if (gated) hg_al_event(&AL, HG_EV_IM_OK, 1, press_ms); }
      else if (PL.active) { uint8_t id = hg_plan_done(&PL, mod); if (gated) hg_al_event(&AL, HG_EV_NUDGE_DONE, id, press_ms); }
    }
    for (int sec = 0; sec < 60; sec++) {
      if (k >= 0) scene_at(s, k + sec / 60.0f, v);
      hg_fw_sec_t q; memset(&q, 0, sizeof q);
      q.t1_c = v[0]; q.t2_c = v[1]; q.tair_c = v[2]; q.rh_pct = v[3];
      q.ppg_on = (uint8_t)hg_fw_ppg_on(&fw, (uint8_t)sec);
      q.hr_q = (uint8_t)v[5]; q.hr_bpm = isnan(v[4]) ? NAN : v[4] + (ur() - 0.5f) * 2.0f; q.pi_pct = v[6]; q.ppg_dc = q.hr_q == 0 ? 5000u : 110000u;
      float m = 0, m2 = 0, pk = 0; int n = 0;
      for (int j = 0; j < 25; j++) { float a = 1.0f + v[7] * 3.4641f * (ur() - 0.5f); n++; float d = a - m; m += d / n; m2 += d * (a - m); if (a > pk) pk = a; }
      q.a_mean = m; q.a_m2 = m2; q.a_n = 25; q.a_peak_g = pk; q.zangle_deg = v[8];
      hg_fw_second(&fw, &q);
    }
    hg_fw_ctx_t c = { mod, day, 0, 3.9f, 2, NULL, 0 }; hg_fw_act_t act;
    hg_fw_minute(&fw, &g, &tw, &acc, &c, tms, &act); tms += 60000;
    const hg_minute_out_t *o = &fw.last_out;
    hg_plan_in_t pin; memset(&pin, 0, sizeof pin);
    pin.mod = mod; pin.day = day; pin.warning = o->state != HG_ST_OK; pin.room_c = fw.last_in.s.t_air_c;
    pin.l_valid = g.rt.sleep_valid; pin.l_days = g.rt.days_learned; pin.l_sleep_on = g.rt.sleep_on; pin.l_sleep_off = g.rt.sleep_off;
    pin.ext_nudge = o->nudge; pin.home_out = o->home_out;
    hg_plan_out_t po;
    const uint8_t check_on = o->check_min != 0xFF;
    if (k >= 0 && r->frozen_first_min < 0 && (o->haptic != HG_HAP_NONE)) r->frozen_first_min = k;
    if (gated) {
      hg_al_in_t ai = { &fw.last_in, o, tw.rest_hr, NULL, mod, day, 3.9f, tms };
      hg_al_out_t ao; hg_al_minute(&AL, &ai, &ao);
      hg_al_plan_minute(&AL, &ao, &PL, &pin, &po);
      if (po.missed) hg_al_event(&AL, HG_EV_NUDGE_MISSED, po.missed, tms);
      if (po.show) hg_al_event(&AL, HG_EV_NUDGE_SHOWN, po.show, tms);
      if (k < 0) continue;
      if (ao.n_notes) for (int i = 0; i < ao.n_notes; i++) {
        r->n_held++;
        size_t L = strlen(r->held_txt);
        if (L < sizeof r->held_txt - 40) snprintf(r->held_txt + L, sizeof r->held_txt - L, "%s%s/%s@%d", L ? " " : "", hg_al_what_name(ao.notes[i].what), hg_al_reason_name(ao.notes[i].reason), k);
      }
      if (AL.valid) r->n_unknown++;
      if (getenv("HG_TRACE") && (ao.haptic != HG_HAP_NONE || po.show)) printf("   trace %s @%d state %u haptic %u nudge %u\n", s->name, k, o->state, ao.haptic, po.show);
      if (ao.haptic != HG_HAP_NONE && o->state != HG_ST_IMOK) r->n_buzz++;   /* the I'm OK tick answers her press: not an alert */
      if (po.show) r->n_buzz++;                                              /* the sketch vibrates every nudge it shows */
      if (ao.present == HG_ST_DRINK) seq_add(r, "DRINK", k);
      if (ao.present == HG_ST_COOL) seq_add(r, ao.soft ? "COOL~" : "COOL", k);
      if (check_on && !prev_check) seq_add(r, "CHECK", k);
      if (o->family_alert && !prev_fam) seq_add(r, "FAMILY", k);
      if (o->state == HG_ST_OK && o->nudge && ao.haptic != HG_HAP_NONE) seq_add(r, "BEDTIME", k);
      if (po.show) { char b[12]; snprintf(b, sizeof b, "NUDGE%u", po.show); seq_add(r, b, k); }
      if (ao.clear) seq_add(r, "CLEAR", k);
    } else {                                        /* 0.9.8: every frozen haptic + the planner on the raw room value */
      hg_plan_minute(&PL, &pin, &po);
      if (k < 0) continue;
      if (o->haptic != HG_HAP_NONE) {
        r->n_buzz++;
        if (o->state == HG_ST_DRINK) seq_add(r, "DRINK", k);
        else if (o->state == HG_ST_COOL) seq_add(r, "COOL", k);
        else if (check_on && !prev_check) seq_add(r, "CHECK", k);
        else if (o->family_alert && !prev_fam) seq_add(r, "FAMILY", k);
        else if (check_on) seq_add(r, "CHECK", k);
        else if (o->state == HG_ST_OK && o->nudge) seq_add(r, "BEDTIME", k);
        else if (o->state == HG_ST_IMOK) { r->n_buzz--; }   /* the I'm OK tick answers her press: not an alert */
        else if (o->state == HG_ST_DANGER) seq_add(r, "DANGER", k);
      }
      if (po.show) { r->n_buzz++; char b[12]; snprintf(b, sizeof b, "NUDGE%u", po.show); seq_add(r, b, k); }
    }
    prev_check = check_on; prev_fam = o->family_alert;
  }
  if (gated) r->sc = AL.sc;
}

/* ------------------------------------------------------------------ Part B helpers: hand-made minutes straight into the layer */
static hg_minute_t M; static hg_minute_out_t O; static hg_al_t A; static hg_al_out_t AO; static uint32_t T;
static void mk(uint8_t st, uint8_t level, float f20, uint8_t worn, float t1, float ta, float rh, uint8_t hrq, float hr, uint8_t why)
{
  memset(&M, 0, sizeof M); memset(&O, 0, sizeof O);
  M.s.t1_c = t1; M.s.t2_c = t1 - 1.5f; M.s.t_air_c = ta; M.s.rh_pct = rh; M.s.hr_quality = hrq; M.s.hr_bpm = hr; M.s.a_std_g = 0.01f;
  O.state = st; O.level = level; O.worn = worn; O.why = why; O.check_min = 0xFF; O.core.valid = 1; O.core.f20_eff = f20; O.core.strain = 2.0f;
  O.screen = st == HG_ST_DRINK ? HG_SCR_DRINK : st == HG_ST_COOL ? HG_SCR_COOL : HG_SCR_OK;
}
static void step(void) { hg_al_in_t ai = { &M, &O, 70.0f, NULL, 600, 20000, 3.9f, T }; hg_al_minute(&A, &ai, &AO); T += 60000u; }
static int has_note(uint8_t what, uint8_t reason) { for (int i = 0; i < AO.n_notes; i++) if (AO.notes[i].what == what && AO.notes[i].reason == reason) return 1; return 0; }
#define WARM(st, lv, f20) mk(st, lv, f20, 2, 34.5f, 30.0f, 45.0f, 4, 80.0f, HG2_WHY_BODY)

int main(int argc, char **argv)
{
  const char *dir = argc > 1 ? argv[1] : "fw/09_guardian/scenes";
  FILE *md = argc > 2 ? fopen(argv[2], "w") : NULL;
  static const char *SC[] = { "shower", "table", "walk_cool", "sun_sensor", "hot_flat_slow", "hot_fast" };
  printf("== A. staged scenes (frozen guardian + rules layer + planner, after a calm 24 h warm-up) ==\n");
  if (md) fprintf(md, "| scene | expected | 0.9.8 (no rules layer): buzzes / sequence | 0.9.9: buzzes / sequence | held back (what/reason@minute) |\n|---|---|---|---|---|\n");
  for (unsigned i = 0; i < sizeof SC / sizeof SC[0]; i++) {
    char fn[512]; snprintf(fn, sizeof fn, "%s/%s.csv", dir, SC[i]);
    static scene_t s; int nk = scene_load(fn, &s);
    CHECK(nk >= 2, "scene %s loads (%d keyframes)", SC[i], nk);
    if (nk < 2) continue;
    static run_t base, gate; run_scene(&s, 0, &base); run_scene(&s, 1, &gate);
    printf("   %-14s expect [%s]\n   %-14s 0.9.8: %d buzzes [%s]\n   %-14s 0.9.9: %d buzzes [%s] unknown-min %d\n   %-14s held: %s\n",
           s.name, s.expect, "", base.n_buzz, base.tl, "", gate.n_buzz, gate.tl, gate.n_unknown, "", gate.held_txt[0] ? gate.held_txt : "-");
    CHECK(strcmp(gate.seq, s.expect) == 0, "scene %s: interruptions [%s] == expected [%s]", s.name, gate.seq, s.expect);
    if (md) fprintf(md, "| %s | %s | %d / %s | %d / %s | %s |\n", s.name, s.expect[0] ? s.expect : "none", base.n_buzz, base.tl[0] ? base.tl : "-",
                    gate.n_buzz, gate.tl[0] ? gate.tl : "-", gate.held_txt[0] ? gate.held_txt : "-");
    if (!strcmp(SC[i], "hot_fast")) {
      CHECK(gate.sc.ack == 1 && gate.sc.tta_n == 1 && gate.sc.missed == 0, "hot_fast: her press counted as acknowledged (ack %u, time to acknowledge %lu s, missed %u)",
            gate.sc.ack, (unsigned long)(gate.sc.tta_n ? gate.sc.tta_sum_s / gate.sc.tta_n : 0), gate.sc.missed);
    }
    if (!strcmp(SC[i], "hot_flat_slow")) {
      CHECK(gate.sc.missed >= 1 && gate.sc.sent[HG_AL_K_FAMILY] == 1, "hot_flat_slow: the unanswered CHECK counts as missed (%u) and the family call is sent once (%u)",
            gate.sc.missed, gate.sc.sent[HG_AL_K_FAMILY]);
    }
  }
  if (md) fclose(md);

  printf("== B. unit checks ==\n");
  /* B1 persistence: DRINK needs 5 valid minutes; one normal minute resets */
  hg_al_init(&A); T = 0;
  for (int i = 0; i < 8; i++) { WARM(HG_ST_OK, 0, 37.2f); step(); }
  int shown_at = -1;
  for (int i = 0; i < 4; i++) { WARM(HG_ST_DRINK, 1, 37.70f); step(); if (AO.present) shown_at = i; }
  WARM(HG_ST_OK, 0, 37.5f); step();
  CHECK(shown_at < 0 && has_note(HG_AL_W_DRINK, HG_AL_R_PERSIST), "4 DRINK minutes then a normal one: nothing shown, logged PERSIST (self-corrected)");
  for (int i = 0; i < 6 && shown_at < 0; i++) { WARM(HG_ST_DRINK, 1, 37.70f + 0.01f * i); step(); if (AO.present == HG_ST_DRINK) shown_at = i; }
  CHECK(shown_at == HG_AL_N_DRINK - 1 && AO.haptic == HG_HAP_WATCH && AO.wake, "DRINK shown on the 5th consecutive valid minute with the 2-pulse buzz (minute %d)", shown_at);
  /* B2 latched: DRINK off and on again inside the episode = no second buzz, REPEAT logged */
  for (int i = 0; i < 3; i++) { WARM(HG_ST_OK, 0, 37.60f); step(); }
  int again = 0, rep = 0;
  for (int i = 0; i < 10; i++) { WARM(HG_ST_DRINK, 1, 37.75f); step(); again |= AO.present != 0 || AO.haptic != HG_HAP_NONE; rep |= has_note(HG_AL_W_DRINK, HG_AL_R_REPEAT); }
  CHECK(!again && rep, "same episode comes back: no repeat buzz, REPEAT logged");
  /* B3 hysteresis: 10 calm minutes but f20 not 0.20 below -> no all-clear; then f20 drops -> exactly one all-clear */
  int clears = 0;
  for (int i = 0; i < 15; i++) { WARM(HG_ST_OK, 0, 37.70f); step(); clears += AO.clear; }
  CHECK(clears == 0 && A.pres == 1, "10+ calm minutes with f20 still near the shown value (37.70 vs 37.75): episode stays latched, no all-clear");
  int clear_tick = -1;
  for (int i = 0; i < 15; i++) { WARM(HG_ST_OK, 0, 37.40f); step(); if (AO.clear) { clears++; clear_tick = AO.clear_tick; } }
  CHECK(clears == 1 && clear_tick == 0 && A.pres == 0, "f20 0.35 C below: one all-clear (a DRINK-only episode: screen + event, no buzz)");
  int fresh = -1;
  for (int i = 0; i < 6 && fresh < 0; i++) { WARM(HG_ST_DRINK, 1, 37.80f); step(); if (AO.present == HG_ST_DRINK) fresh = i; }
  CHECK(fresh == HG_AL_N_DRINK - 1, "after the all-clear a new DRINK episode can fire again (after 5 minutes)");
  /* B4 validity: not worn / shower hold DRINK; bounded */
  hg_al_init(&A);
  int pres = 0; int nw = 0;
  for (int i = 0; i < 30; i++) { mk(HG_ST_DRINK, 1, 37.8f, 0, 27.5f, 27.0f, 45, 0, NAN, HG2_WHY_BODY); step(); pres |= AO.present != 0; nw |= has_note(HG_AL_W_DRINK, HG_AL_R_NOT_WORN); }
  CHECK(!pres && nw && (A.valid & HG_AL_V_NOT_WORN) && AO.nudge_hold, "band off: DRINK held (NOT_WORN logged once), nudges held, state UNKNOWN");
  hg_al_init(&A); int lim = -1;
  for (int i = 0; i < 70 && lim < 0; i++) { mk(HG_ST_DRINK, 1, 37.8f, 1, 33.0f, 29.0f, 45, 4, 80.0f, HG2_WHY_BODY); step(); if (AO.present) lim = i; }
  CHECK(lim == HG_AL_HOLD_MAX_DRINK - 1 && A.sc.hold_limit == 1, "a hold is bounded: a loose band holds DRINK at most %d min, then it is shown and logged (shown at minute %d)", HG_AL_HOLD_MAX_DRINK, lim);
  hg_al_init(&A); lim = -1;
  for (int i = 0; i < 40 && lim < 0; i++) { mk(HG_ST_COOL, 2, 38.4f, 1, 34.0f, 33.0f, 45, 4, 95.0f, HG2_WHY_BODY); step(); if (AO.present) lim = i; }
  CHECK(lim == HG_AL_HOLD_MAX_COOL - 1, "COOL hold bounded at %d min (shown at minute %d)", HG_AL_HOLD_MAX_COOL, lim);
  /* shower signature */
  hg_al_init(&A);
  for (int i = 0; i < 6; i++) { mk(HG_ST_OK, 0, 37.2f, 2, 33.8f, 27.0f, 45, 4, 72, 0); step(); }
  mk(HG_ST_OK, 0, 37.2f, 2, 36.0f, 31.0f, 85, 2, 80, 0); step();
  CHECK(A.valid & HG_AL_V_WET, "shower signature: RH 45 -> 85 %% with a +2.2 C skin step in 1 min -> SHOWER");
  hg_al_init(&A);
  for (int i = 0; i < 6; i++) { mk(HG_ST_OK, 0, 37.2f, 2, 35.0f, 33.0f, 60, 4, 72, 0); step(); }
  mk(HG_ST_OK, 0, 37.2f, 2, 35.1f, 33.0f, 84, 4, 72, 0); step();
  CHECK(!(A.valid & HG_AL_V_WET), "humid weather alone (RH 60 -> 84 %%, skin unchanged) is NOT a shower: humid heat must never be hidden");
  hg_al_init(&A); int wet_end = -1;
  for (int i = 0; i < 6; i++) { mk(HG_ST_OK, 0, 37.2f, 2, 33.8f, 27.0f, 45, 4, 72, 0); step(); }
  for (int i = 0; i < 120 && wet_end < 0; i++) { mk(HG_ST_OK, 0, 37.2f, 2, 37.0f, 32.0f, 96, 2, 80, 0); step(); if (!(A.valid & HG_AL_V_WET)) wet_end = i; }
  CHECK(wet_end == HG_AL_WET_MAX, "a shower signature never lasts more than %d min even if the humidity stays at 96 %% (ended at %d)", HG_AL_WET_MAX, wet_end);
  /* sun signature */
  hg_al_init(&A);
  for (int i = 0; i < 6; i++) { mk(HG_ST_OK, 0, 37.2f, 2, 33.8f, 26.0f, 45, 4, 70, 0); step(); }
  mk(HG_ST_OK, 0, 37.2f, 2, 34.1f, 31.0f, 35, 4, 70, 0); M.s.t2_c = 37.0f; step();
  CHECK(A.valid & HG_AL_V_SUN, "sun signature: air +5 C in a minute, skin +0.3 C, outward sensor 2.9 C over skin -> SUN");
  /* B5 two kinds of evidence for COOL */
  hg_al_init(&A);
  for (int i = 0; i < 65; i++) { mk(HG_ST_OK, 0, 37.2f, 2, 33.0f, 18.0f, 50, 4, 70, 0); step(); }   /* a cool hour: no exposure */
  int soft = -1, hap = -1, at = -1, onev = 0;
  int drink_at = -1;
  for (int i = 0; i < 40 && soft < 0; i++) { mk(HG_ST_COOL, 2, 38.4f, 2, 33.0f, 18.0f, 50, 4, 120, HG2_WHY_BODY); M.s.a_std_g = 0.2f; step(); onev |= has_note(HG_AL_W_COOL, HG_AL_R_ONE_EV);
    if (AO.present == HG_ST_DRINK && drink_at < 0) drink_at = i;
    if (AO.present == HG_ST_COOL) { soft = AO.soft; hap = AO.haptic; at = i; } }
  CHECK(onev && at == HG_AL_N_COOL - 1 + HG_AL_HOLD_MAX_COOL - 1 && soft == 1 && hap == HG_HAP_SOFT && drink_at == HG_AL_N_DRINK - 1,
        "COOL from the body only (18 C air, brisk movement): COOL held ONE_EVIDENCE (the DRINK nudge still comes after 5 min = 'nudge at most'); "
        "bounded: after %d min a soft nudge-strength COOL (minute %d)", HG_AL_HOLD_MAX_COOL, at);
  hg_al_init(&A);
  for (int i = 0; i < 5; i++) { mk(HG_ST_OK, 0, 37.2f, 2, 34.0f, 31.0f, 40, 4, 72, 0); step(); }
  soft = -1;
  for (int i = 0; i < 5 && soft < 0; i++) { mk(HG_ST_COOL, 2, 37.9f, 2, 34.0f, 31.0f, 40, 4, 72, HG2_WHY_TIME_IN_HEAT); step(); if (AO.present) { soft = AO.soft; hap = AO.haptic; } }
  CHECK(soft == 1 && hap == HG_HAP_SOFT && has_note(HG_AL_W_COOL, HG_AL_R_ONE_EV), "COOL from heat exposure only (31 C for hours, body calm): soft nudge-strength COOL at once after persistence, ONE_EVIDENCE logged");
  hg_al_init(&A);
  for (int i = 0; i < 5; i++) { mk(HG_ST_OK, 0, 37.2f, 2, 35.0f, 33.0f, 40, 4, 80, 0); step(); }
  soft = -1;
  for (int i = 0; i < 5 && soft < 0; i++) { mk(HG_ST_COOL, 2, 38.4f, 2, 35.5f, 34.0f, 40, 4, 100, HG2_WHY_BODY | HG2_WHY_ENV_LIMIT); step(); if (AO.present) { soft = AO.soft; hap = AO.haptic; } }
  CHECK(soft == 0 && hap == HG_HAP_COOL, "COOL with exposure (34 C air) AND physiology: full COOL pattern after %d minutes", HG_AL_N_COOL);
  /* B6 CHECK passes through unchanged, even on invalid input (the frozen family timer cannot be paused) */
  hg_al_init(&A);
  mk(HG_ST_CHECK, 1, 37.6f, 0, 27.0f, 27.0f, 96, 0, NAN, 0); O.check_min = 0; O.check_reason = HG_CR_ROUTINE_QUIET; O.haptic = HG_HAP_CHECK; O.screen = HG_SCR_CHECK; step();
  CHECK(AO.haptic == HG_HAP_CHECK && AO.wake && A.sc.sent[HG_AL_K_CHECK] == 1, "frozen CHECK on a band reading UNKNOWN: buzz and screen passed through unchanged (never held)");
  mk(HG_ST_DANGER, 3, 38.6f, 2, 36.0f, 36.0f, 40, 4, 110, HG2_WHY_BODY); O.check_min = 0; O.check_reason = HG_CR_DANGER; O.haptic = HG_HAP_CHECK; step();
  mk(HG_ST_DANGER, 3, 38.6f, 2, 36.0f, 36.0f, 40, 4, 110, HG2_WHY_BODY); O.check_min = 2; O.check_reason = HG_CR_DANGER; O.haptic = HG_HAP_CHECK; step();
  CHECK(AO.haptic == HG_HAP_CHECK, "the frozen re-ask at 2 min passes through (the ladder before the family call is kept)");
  /* B7 thermal CHECK with one kind of evidence: audited, not held */
  hg_al_init(&A);
  for (int i = 0; i < 65; i++) { mk(HG_ST_OK, 0, 37.2f, 2, 33.0f, 20.0f, 50, 4, 70, 0); step(); }
  mk(HG_ST_DANGER, 3, 38.6f, 2, 33.0f, 20.0f, 50, 4, 70, HG2_WHY_BODY); O.check_min = 0; O.check_reason = HG_CR_DANGER; O.haptic = HG_HAP_CHECK; step();
  CHECK(AO.haptic == HG_HAP_CHECK && A.sc.check_1ev == 1 && has_note(HG_AL_W_CHECK, HG_AL_R_ONE_EV), "thermal CHECK with physiology only: passed through AND counted in the audit (check_1ev = 1)");
  /* B8 scorecard: I'm OK after 40 s, family on an unanswered CHECK */
  hg_al_init(&A); T = 1000000u;
  mk(HG_ST_CHECK, 0, 37.2f, 2, 34.0f, 30.0f, 45, 4, 80, 0); O.check_min = 0; O.check_reason = HG_CR_IMPACT; O.haptic = HG_HAP_CHECK; step();
  hg_al_event(&A, HG_EV_IM_OK, 1, T - 60000u + 40000u);
  CHECK(A.sc.ack == 1 && A.sc.tta_n == 1 && A.sc.tta_sum_s == 40, "I'm OK 40 s after the question: ack 1, time to acknowledge 40 s");
  mk(HG_ST_CHECK, 0, 37.2f, 2, 34.0f, 30.0f, 45, 4, 80, 0); O.check_min = 0xFF; step();
  mk(HG_ST_CHECK, 0, 37.2f, 2, 34.0f, 30.0f, 45, 4, 80, 0); O.check_min = 0; O.check_reason = HG_CR_ROUTINE_QUIET; step();
  mk(HG_ST_CHECK, 0, 37.2f, 2, 34.0f, 30.0f, 45, 4, 80, 0); O.check_min = 10; O.check_reason = HG_CR_ROUTINE_QUIET; O.family_alert = 1; step();
  CHECK(A.sc.missed == 1 && A.sc.sent[HG_AL_K_FAMILY] == 1 && A.sc.sent[HG_AL_K_CHECK] == 2, "unanswered CHECK -> family: missed 1, family 1, CHECK prompts 2");
  hg_al_event(&A, HG_EV_NUDGE_SHOWN, 4, 0); hg_al_event(&A, HG_EV_NUDGE_MISSED, 4, 600000);
  CHECK(A.sc.missed == 2 && A.sc.sent[HG_AL_K_NUDGE] == 1, "nudge shown then MISSED: counted");
  /* B8b planner through the gate: band off -> N4 WATER held (NOT_WORN logged once), open nudge not cancelled; worn again -> it comes */
  { static hg_al_t keep; keep = A;                  /* B9 below reads the B8 scorecard */
    hg_al_init(&A); hg_plan_init(&PL); int shown = -1, heldn = 0; uint16_t md = 11 * 60;
    for (int i = 0; i < 40 && shown < 0; i++, md++) {
      int off = i < 20;
      mk(HG_ST_OK, 0, 37.2f, off ? 0 : 2, off ? 27.0f : 34.0f, 30.0f, 40, off ? 0 : 4, off ? NAN : 75.0f, 0);
      hg_al_in_t ai = { &M, &O, 70.0f, NULL, md, 20000, 3.9f, T }; hg_al_minute(&A, &ai, &AO); T += 60000u;
      hg_plan_in_t pin; memset(&pin, 0, sizeof pin); pin.mod = md; pin.day = 20000; pin.room_c = 30.0f; pin.home_out = 0xFF;
      hg_plan_out_t po; hg_al_plan_minute(&A, &AO, &PL, &pin, &po);
      heldn += has_note(HG_AL_W_NUDGE, HG_AL_R_NOT_WORN);
      if (po.show) shown = i;
    }
    CHECK(heldn == 1 && shown == 20, "band off 20 min in a 30 C room: N4 WATER held once (NOT_WORN), shown the first minute it is worn again (minute %d)", shown);
    A = keep; }
  /* B9 EVENTS payloads round-trip through the real frame packer */
  { uint8_t x[8], f[20]; hg_evring_t R; hg_ev_init(&R); hg_ev_t e; uint16_t boot;
    hg_al_score_x(&A, 2, x); const hg_ev_t *p = hg_ev_add_x(&R, 1794700800u, HG_EV_SCORE, 2, x); hg_ev_pack(p, 7, f);
    int rc = hg_ev_unpack(f, &e, &boot);
    CHECK(rc == 0 && f[0] == 0x03 && f[9] == 13 && f[10] == 2 && f[12] == 1 && f[13] == 2 && f[15] == 40, "EVENTS type 13 SCORE page 2: version 0x03 kept, ack 1, missed 2, avg time to ack 40 s, CRC ok");
    hg_al_note_t n = { HG_AL_W_DRINK, HG_AL_R_WET, HG_ST_DRINK, 1 }; hg_al_held_x(&n, x); p = hg_ev_add_x(&R, 1794700800u, HG_EV_ALERT_HELD, n.what, x); hg_ev_pack(p, 7, f);
    CHECK(hg_ev_unpack(f, &e, &boot) == 0 && f[9] == 11 && f[10] == HG_AL_W_DRINK && f[11] == HG_AL_R_WET && f[12] == HG_ST_DRINK, "EVENTS type 11 ALERT_HELD: [10] what, [11] reason, [12] state");
    hg_al_out_t co; memset(&co, 0, sizeof co); co.clear_min = 300; co.clear_family = 1; co.clear_tick = 1; co.clear_peak = 3; hg_al_clear_x(&co, x);
    p = hg_ev_add_x(&R, 1794700800u, HG_EV_ALL_CLEAR, co.clear_peak, x); hg_ev_pack(p, 7, f);
    CHECK(hg_ev_unpack(f, &e, &boot) == 0 && f[9] == 12 && f[10] == 3 && f[11] == 44 && f[12] == 1 && f[13] == 1 && f[14] == 1, "EVENTS type 12 ALL_CLEAR: [10] peak, [11-12] 300 min, [13] family, [14] tick");
    CHECK(!strcmp(hg_ev_name(11), "ALERT_HELD") && !strcmp(hg_ev_name(12), "ALL_CLEAR") && !strcmp(hg_ev_name(13), "SCORE"), "event names for the log");
  }
  printf("TEST_ALERTS: %s (%d pass, %d fail)\n", fails ? "FAIL" : "PASS", passes, fails);
  return fails != 0;
}
