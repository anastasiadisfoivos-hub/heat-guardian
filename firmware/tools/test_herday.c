/* Host test of the 0.9.8 "Her Day" band side (HERDAY_SPEC.md, ECOSYSTEM_SPEC.md 5d) in fw/09_guardian/hg_fw_eco.c.
 * Linked into test_eco (run_host_tests.sh step 8b); herday_tests() returns its failure count.
 * 1. CMD 0x1B DAY_PLAN / 0x1C VISIT parser: valid frames, every field error, CRC, short; the frozen parser rejects both.
 * 2. EVENTS type 9 VISIT / type 10 PLAN_ITEM frame layout.
 * 3. day-plan store: atomic per day, restart rules, clear, midnight roll, /dayplan.bin image (+ CRC).
 * 4. nudges: N7 EVENING_BRIEF, upgraded N1, N5 AIR re-timed by kind 2, N3 gone, N8 LEAVE_HOT (once per outing, re-arm after
 *    30 min home, max 2 a day, fresh VISIT only), and every cap / priority rule (<= 6, >= 60 min except N8, sleep window,
 *    warnings win, 10-min MISSED).
 * 5. screen layout: every Her Day text wraps into the 240 x 100 px nudge text box with the band's textBlock rule.
 * With a path: writes fw/09_guardian/herday_vectors.json (hex frames for the iOS app). */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "hg_fw_eco.h"
#include "frozen/hg_frames.h"
#include "frozen/hg_guardian.h"
#include "frozen/hg_homeout.h"

static int hfails = 0, hpass = 0;
#define HCHECK(c, ...) do { if (c) { printf("PASS  "); hpass++; } else { printf("FAIL  "); hfails++; } printf(__VA_ARGS__); printf("\n"); } while (0)

static uint8_t HFC[72];
static void hfc_heat_day(void)   /* = console `fcdemo`: heat-day + night-heat all day, safe 06-10, T_in 26-33 */
{
  static const int8_t T[24] = { 27, 27, 26, 26, 26, 26, 26, 27, 27, 27, 28, 29, 31, 32, 33, 33, 32, 31, 30, 29, 28, 28, 27, 27 };
  for (int h = 0; h < 24; h++) { HFC[3 * h] = (uint8_t)T[h]; HFC[3 * h + 1] = 45; HFC[3 * h + 2] = (uint8_t)(1 | 2 | ((h >= 6 && h < 10) ? 4 : 0)); }
}
static void hfc_cool_day(void) { for (int h = 0; h < 24; h++) { HFC[3 * h] = 24; HFC[3 * h + 1] = 50; HFC[3 * h + 2] = 4; } }

static hg_plan_in_t hin(uint16_t mod, int32_t day)
{
  hg_plan_in_t in; memset(&in, 0, sizeof in);
  in.mod = mod; in.day = day; in.room_c = 25.0f; in.l_sleep_on = 0xFFFF; in.l_sleep_off = 0xFFFF; in.home_out = HG_HO_HOME;
  return in;
}
static hg_dpi_t outing(uint8_t place, uint8_t uh, uint8_t um, uint8_t sh, uint8_t sm, uint8_t dir, uint8_t hf, uint8_t ht, uint8_t peak)
{
  hg_dpi_t t; memset(&t, 0, sizeof t);
  t.kind = 1; t.place = place; t.usual_h = uh; t.usual_m = um; t.sugg_h = sh; t.sugg_m = sm; t.dir = dir; t.hot_from = hf; t.hot_to = ht; t.peak_c = peak;
  return t;
}
static hg_dpi_t air(uint8_t sh, uint8_t sm) { hg_dpi_t t; memset(&t, 0, sizeof t); t.kind = 2; t.sugg_h = sh; t.sugg_m = sm; return t; }
static hg_dpi_t hwave(uint8_t n) { hg_dpi_t t; memset(&t, 0, sizeof t); t.kind = 3; t.hw_day = n; return t; }
/* sends a whole day's set through the real parser + store, as the phone would */
static int send_day(hg_dayplan_t *d, uint8_t day, const hg_dpi_t *its, uint8_t n)
{
  uint8_t f[20]; hg_eco_cmd_t c; int done = 0;
  if (n == 0) { hg_eco_pack_dayplan(day, 0, 0, NULL, f); if (hg_eco_cmd_parse(f, 20, &c) != HG_CMD_DAY_PLAN) return -1; return hg_dp_apply(d, c.dp_day, c.dp_index, c.dp_n, &c.dpi); }
  for (uint8_t i = 0; i < n; i++) {
    hg_eco_pack_dayplan(day, (uint8_t)(i + 1), n, &its[i], f);
    if (hg_eco_cmd_parse(f, 20, &c) != HG_CMD_DAY_PLAN) return -1;
    done = hg_dp_apply(d, c.dp_day, c.dp_index, c.dp_n, &c.dpi);
  }
  return done;
}
static int field_err(const uint8_t *f19) { uint8_t f[20]; memcpy(f, f19, 19); f[19] = hg_crc8(f, 19); hg_eco_cmd_t c; return hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_FIELD; }

typedef struct { uint8_t id; uint16_t mod; } hshown_t;
/* a whole day minute by minute; leave_at / home_at: minutes where home_out changes; warn: [from, to) min */
static int hrun_day(hg_plan_t *p, hg_plan_in_t t, int32_t day, hshown_t *sh, int *missed, const uint16_t *ho_sw, int nsw, int wf, int wt)
{
  int n = 0; *missed = 0; uint8_t ho = HG_HO_HOME;
  for (uint16_t mod = 0; mod < 1440; mod++) {
    for (int k = 0; k < nsw; k++) if (ho_sw[2 * k] == mod) ho = (uint8_t)ho_sw[2 * k + 1];
    hg_plan_in_t in = t; in.mod = mod; in.day = day; in.home_out = ho; in.warning = mod >= wf && mod < wt;
    hg_plan_out_t o; hg_plan_minute(p, &in, &o);
    if (o.missed) (*missed)++;
    if (o.show) { sh[n].id = o.show; sh[n].mod = mod; n++; }
  }
  return n;
}
static void print_day(const char *what, const hshown_t *sh, int n)
{
  printf("      %s:", what); for (int i = 0; i < n; i++) printf(" N%u@%02u:%02u", sh[i].id, sh[i].mod / 60, sh[i].mod % 60); printf("\n");
}
static int has(const hshown_t *sh, int n, uint8_t id) { int c = 0; for (int i = 0; i < n; i++) c += sh[i].id == id; return c; }
static int at(const hshown_t *sh, int n, uint8_t id) { for (int i = 0; i < n; i++) if (sh[i].id == id) return sh[i].mod; return -1; }

/* ---- the band's textBlock() wrap rule (09_guardian.ino): 10x20 font, x size 3..1, 240 px wide, nudge box y 150..250 */
static int u8len(const char *s) { int n = 0; for (; *s; s++) n += ((uint8_t)*s & 0xC0) != 0x80; return n; }
static int layout(const char *txt, int y0, int y1, int *size_out, int *lines_out, int *longest)
{
  char words[16][40]; int nw = 0;
  { const char *p = txt; while (*p && nw < 16) { while (*p == ' ') p++; int k = 0; while (*p && *p != ' ' && k < 39) words[nw][k++] = *p++; words[nw][k] = 0; if (k) nw++; if (*p && *p != ' ') return 0; } }
  for (int size = 3; size >= 1; size--) {
    int perLine = 240 / (10 * size), lineH = 22 * size, maxLines = (y1 - y0) / lineH;
    char lines[6][80]; int nl = 0; lines[0][0] = 0; int fits = 1;
    for (int i = 0; i < nw && fits; i++) {
      int cur = u8len(lines[nl]), add = u8len(words[i]) + (cur ? 1 : 0);
      if (u8len(words[i]) > perLine) { fits = 0; break; }
      if (cur + add > perLine) { if (++nl >= 6) { fits = 0; break; } lines[nl][0] = 0; cur = 0; }
      if (strlen(lines[nl]) + strlen(words[i]) + 2 > sizeof lines[nl]) { fits = 0; break; }
      if (cur) strcat(lines[nl], " ");
      strcat(lines[nl], words[i]);
    }
    if (fits && nl + 1 <= maxLines) {
      int lg = 0; for (int l = 0; l <= nl; l++) if (u8len(lines[l]) * 10 * size > lg) lg = u8len(lines[l]) * 10 * size;
      *size_out = size; *lines_out = nl + 1; *longest = lg; return 1;
    }
  }
  return 0;
}

static void hexs(const uint8_t *b, int n, char *o) { for (int i = 0; i < n; i++) sprintf(o + 2 * i, "%02x", b[i]); }

int herday_tests(const char *vec_path)
{
  printf("== Her Day (0.9.8): CMD 0x1B / 0x1C, EVENTS 9 / 10, day plan, N7, N1, N5, N8, caps ==\n");
  /* ---------------------------------------------------------------- 1. parser */
  { uint8_t f[20]; hg_eco_cmd_t c; hg_cmd_t fc; hg_forecast_buf_t fb; hg_forecast_init(&fb);
    hg_dpi_t t = outing(HG_PL_MARKET, 10, 30, 9, 30, HG_DIR_BEFORE, 11, 18, 36);
    hg_eco_pack_dayplan(1, 1, 3, &t, f);
    HCHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_DAY_PLAN && c.dp_day == 1 && c.dp_index == 1 && c.dp_n == 3 && c.dpi.kind == 1 && c.dpi.place == 1 &&
           c.dpi.usual_h == 10 && c.dpi.usual_m == 30 && c.dpi.sugg_h == 9 && c.dpi.sugg_m == 30 && c.dpi.dir == 1 && c.dpi.hot_from == 11 && c.dpi.hot_to == 18 && c.dpi.peak_c == 36,
           "0x1B DAY_PLAN kind 1 parse (tomorrow, 1/3, market, usual 10:30, before 09:30, hot 11-18, peak 36)");
    HCHECK(hg_cmd_parse(f, 20, &fc, &fb) == HG_CMD_ERR_OP, "frozen hg_cmd_parse rejects 0x1B (the layer parses it first)");
    t = outing(HG_PL_WALK, 0xFF, 0xFF, 21, 0, HG_DIR_AFTER, 12, 24, 0xFF); hg_eco_pack_dayplan(0, 2, 2, &t, f);
    HCHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_DAY_PLAN && c.dpi.usual_h == 0xFF && c.dpi.hot_to == 24 && c.dpi.peak_c == 0xFF, "kind 1 with usual n/a (0xFF 0xFF), hot to 24 (exclusive = midnight), peak unknown");
    t = air(19, 0); t.place = 3; t.usual_h = 7; hg_eco_pack_dayplan(0, 1, 1, &t, f);
    HCHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_DAY_PLAN && c.dpi.kind == 2 && c.dpi.sugg_h == 19 && c.dpi.place == 0 && c.dpi.usual_h == 0, "kind 2 AIR_OPEN parse; unused fields normalised to 0");
    t = hwave(2); hg_eco_pack_dayplan(1, 1, 1, &t, f);
    HCHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_DAY_PLAN && c.dpi.kind == 3 && c.dpi.hw_day == 2, "kind 3 HEATWAVE_DAY parse (day 2)");
    hg_eco_pack_dayplan(1, 0, 0, NULL, f);
    HCHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_DAY_PLAN && c.dp_n == 0 && c.dp_index == 0, "index 0, n 0 = clear");
    hg_eco_pack_dayplan(1, 1, 3, &t, f); HCHECK(hg_eco_cmd_parse(f, 19, &c) == HG_CMD_ERR_SHORT, "0x1B 19 bytes -> short (-1)");
    f[4] ^= 1; HCHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_CRC, "0x1B bad CRC -> -2");
    /* every field error (HERDAY 4 + the as-built ones, ECOSYSTEM_SPEC 5d) */
    const hg_dpi_t g = outing(HG_PL_MARKET, 10, 30, 9, 30, 1, 11, 18, 36);
    struct { int pos; uint8_t v; const char *what; } E[] = {
      { 1, 2, "day 2" }, { 2, 4, "index 4 > n 3" }, { 3, 7, "n 7 (> 6)" }, { 4, 0, "kind 0" }, { 4, 4, "kind 4" }, { 5, 8, "place 8" },
      { 6, 24, "usual h 24" }, { 7, 60, "usual m 60" }, { 7, 0xFF, "usual pair half set (h 10, m 0xFF)" }, { 8, 24, "suggested h 24" },
      { 9, 60, "suggested m 60" }, { 11, 24, "hot from_h 24" }, { 12, 25, "hot to_h 25" }, { 10, 0, "kind 1 direction 0" },
      { 10, 3, "kind 1 direction 3" }, { 11, 19, "kind 1 hot from 19 > to 18" } };
    int all = 1;
    for (unsigned k = 0; k < sizeof E / sizeof E[0]; k++) {
      hg_eco_pack_dayplan(0, 1, 3, &g, f); f[E[k].pos] = E[k].v; int e = field_err(f);
      if (k == 2) { f[2] = 1; e = field_err(f); }    /* n 7 with index 1 */
      HCHECK(e, "0x1B field error: %s", E[k].what); all &= e;
    }
    hg_eco_pack_dayplan(0, 0, 2, &g, f); HCHECK(field_err(f), "0x1B field error: index 0 with n 2 (index 0 only means clear)");
    hg_eco_pack_dayplan(0, 1, 1, &g, f); f[8] = 0xFF; f[9] = 0xFF; HCHECK(field_err(f), "0x1B field error: kind 1 without a suggested time");
    t = air(19, 0); hg_eco_pack_dayplan(0, 1, 1, &t, f); f[8] = 0xFF; f[9] = 0xFF; HCHECK(field_err(f), "0x1B field error: kind 2 without a suggested time");
    t = hwave(2); hg_eco_pack_dayplan(0, 1, 1, &t, f); f[14] = 32; HCHECK(field_err(f), "0x1B field error: heat-wave day 32 (5 bits in the echo)");
    t = hwave(31); hg_eco_pack_dayplan(0, 1, 1, &t, f); HCHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_DAY_PLAN, "heat-wave day 31 accepted");
    /* VISIT */
    hg_eco_pack_visit(HG_VISIT_ARRIVE, HG_PL_MARKET, 1795420800u, f);
    HCHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_VISIT && c.v_event == 1 && c.v_place == 1 && c.v_unix == 1795420800u, "0x1C VISIT arrive market parse (u32 unix little-endian)");
    HCHECK(hg_cmd_parse(f, 20, &fc, &fb) == HG_CMD_ERR_OP, "frozen hg_cmd_parse rejects 0x1C");
    hg_eco_pack_visit(HG_VISIT_LEAVE, HG_PL_HOME, 1795421000u, f); HCHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_VISIT && c.v_event == 2 && c.v_place == 0, "0x1C VISIT leave home parse");
    hg_eco_pack_visit(0, 1, 1, f); HCHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_FIELD, "0x1C field error: event 0");
    hg_eco_pack_visit(3, 1, 1, f); HCHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_FIELD, "0x1C field error: event 3");
    hg_eco_pack_visit(1, 8, 1, f); HCHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_FIELD, "0x1C field error: place 8");
    hg_eco_pack_visit(1, 1, 1, f); f[3] ^= 0x10; HCHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_CRC, "0x1C bad CRC -> -2");
    HCHECK(hg_eco_cmd_parse(f, 12, &c) == HG_CMD_ERR_SHORT, "0x1C 12 bytes -> short"); }

  /* ---------------------------------------------------------------- 2. EVENTS 9 / 10 */
  { static hg_evring_t r; hg_ev_init(&r); uint8_t x[8], f[20]; hg_ev_t d; uint16_t boot;
    hg_visit_echo(HG_VISIT_LEAVE, 0x6B0A1234u, x);
    const hg_ev_t *e = hg_ev_add_x(&r, 1795420860u, HG_EV_VISIT, HG_PL_PHARMACY, x); hg_ev_pack(e, 37, f);
    HCHECK(f[0] == 3 && f[9] == 9 && f[10] == 4 && f[11] == 2 && f[12] == 0x34 && f[13] == 0x12 && f[14] == 0x0A && f[15] == 0x6B && f[16] == 0 && f[18] == 0 && f[19] == hg_crc8(f, 19),
           "EVENTS type 9 VISIT: arg place, [11] 2 leave, [12-15] u32 visit unix, version byte stays 0x03");
    hg_dpi_t t = outing(HG_PL_CHURCH, 10, 0, 8, 30, HG_DIR_BEFORE, 11, 19, 37); hg_dp_echo(&t, 1, x);
    e = hg_ev_add_x(&r, 1795420900u, HG_EV_PLAN_ITEM, t.kind, x); hg_ev_pack(e, 37, f);
    HCHECK(f[9] == 10 && f[10] == 1 && f[11] == 2 && f[12] == 10 && f[13] == 0 && f[14] == 8 && f[15] == 30 && f[16] == 11 && f[17] == 19 && f[18] == (1 | 1 << 1),
           "EVENTS type 10 PLAN_ITEM kind 1: place, usual, sugg, hot window, [18] day | dir << 1");
    t = hwave(5); hg_dp_echo(&t, 0, x); HCHECK(x[7] == (5 << 3) && x[0] == 0 && x[3] == 0, "PLAN_ITEM kind 3: [18] = heatwave_day << 3, unused fields 0");
    HCHECK(hg_ev_unpack(f, &d, &boot) == 0 && d.type == 10 && d.x[1] == 10 && d.x[7] == 3, "EVENTS unpack keeps bytes 11-18");
    HCHECK(strcmp(hg_ev_name(9), "VISIT") == 0 && strcmp(hg_ev_name(10), "PLAN_ITEM") == 0 && strcmp(hg_ev_name(22), "?") == 0, "event names 9 VISIT, 10 PLAN_ITEM (11-13 = 0.9.9 alert quality, 14-21 = 0.9.17, 22+ unknown)"); }

  /* ---------------------------------------------------------------- 3. store */
  { static hg_dayplan_t d; hg_dp_init(&d); hg_eco_cmd_t c; uint8_t f[20];
    hg_dpi_t A[3] = { outing(1, 10, 0, 9, 0, 1, 11, 18, 35), air(19, 0), hwave(2) };
    hg_dpi_t B[2] = { outing(3, 19, 0, 21, 0, 2, 12, 21, 33), outing(5, 11, 0, 9, 30, 1, 11, 18, 34) };
    HCHECK(send_day(&d, 1, A, 3) == 1 && d.day[1].n == 3 && d.day[1].it[2].kind == 3, "a 3-item set for tomorrow is stored when 3/3 arrives");
    /* atomic: a new 2-item set: after 1/2 the old 3 items are still there */
    hg_eco_pack_dayplan(1, 1, 2, &B[0], f); hg_eco_cmd_parse(f, 20, &c);
    HCHECK(hg_dp_apply(&d, 1, 1, 2, &c.dpi) == 0 && d.day[1].n == 3 && d.day[1].it[0].place == 1, "atomic: after 1/2 of a new set the old set is unchanged");
    hg_eco_pack_dayplan(1, 2, 2, &B[1], f); hg_eco_cmd_parse(f, 20, &c);
    HCHECK(hg_dp_apply(&d, 1, 2, 2, &c.dpi) == 1 && d.day[1].n == 2 && d.day[1].it[0].place == 3 && d.day[1].it[1].place == 5, "atomic: 2/2 replaces the day in one step");
    HCHECK(d.day[0].n == 0, "today untouched by tomorrow's set");
    /* restart: 1/3, 2/3, then 1/3 again (the phone resent) -> only a full new set commits */
    hg_dp_apply(&d, 0, 1, 3, &A[0]); hg_dp_apply(&d, 0, 2, 3, &A[1]); int r1 = hg_dp_apply(&d, 0, 1, 3, &A[0]);
    int r2 = hg_dp_apply(&d, 0, 3, 3, &A[2]);
    HCHECK(r1 == 0 && r2 == 0 && d.day[0].n == 0, "an index arriving twice restarts the set (no commit with a gap)");
    HCHECK(hg_dp_apply(&d, 0, 2, 3, &A[1]) == 1 && d.day[0].n == 3, "...and the restarted set commits when complete");
    hg_dp_apply(&d, 0, 1, 2, &B[0]); HCHECK(hg_dp_apply(&d, 0, 2, 3, &A[1]) == 0 && d.day[0].n == 3, "n changing mid-set restarts it");
    HCHECK(send_day(&d, 0, NULL, 0) == 1 && d.day[0].n == 0, "index 0 n 0 clears today at once");
    /* midnight roll */
    hg_dp_init(&d); send_day(&d, 1, B, 2);
    HCHECK(hg_dp_roll(&d, 20774) == 1 && d.today == 20774 && d.day[1].n == 2, "first known day adopts the plan as is (clock arrived after the plan)");
    HCHECK(hg_dp_roll(&d, 20774) == 0, "same day: no change");
    hg_dp_apply(&d, 1, 1, 2, &A[0]);   /* a half set in flight at midnight */
    HCHECK(hg_dp_roll(&d, 20775) == 1 && d.day[0].n == 2 && d.day[0].it[0].place == 3 && d.day[1].n == 0 && d.stage_mask[1] == 0, "midnight: tomorrow becomes today, tomorrow empty, half set dropped");
    send_day(&d, 1, A, 3);
    HCHECK(hg_dp_roll(&d, 20777) == 1 && d.day[0].n == 0 && d.day[1].n == 0, "two days later: both days stale -> empty");
    HCHECK(hg_dp_roll(&d, -1) == 0, "clock unknown: no roll");
    /* file image */
    hg_dp_init(&d); d.today = 20774; send_day(&d, 0, B, 2); send_day(&d, 1, A, 3);
    uint8_t img[HG_DP_FILE]; hg_dp_file_pack(&d, img); static hg_dayplan_t e;
    HCHECK(hg_dp_file_unpack(&e, img, HG_DP_FILE) == 0 && e.today == 20774 && e.day[0].n == 2 && e.day[1].n == 3 && memcmp(&e.day, &d.day, sizeof d.day) == 0, "/dayplan.bin image round trip (148 B)");
    img[40] ^= 4; HCHECK(hg_dp_file_unpack(&e, img, HG_DP_FILE) < 0 && e.day[0].n == 0 && e.today == -1, "corrupted /dayplan.bin -> empty plan");
    HCHECK(hg_dp_file_unpack(&e, img, 100) < 0, "short /dayplan.bin -> empty plan"); }

  /* ---------------------------------------------------------------- 4. nudges */
  hshown_t sh[64]; int n, missed; char b[128];
  { /* N7: tomorrow market before 09:30 (usual 10:30) + a heat-wave day; default bedtime -> 21:00 */
    hg_dpday_t tom = { 2, { hwave(2), outing(HG_PL_MARKET, 10, 30, 9, 30, HG_DIR_BEFORE, 11, 18, 36) } };
    hg_plan_t p; hg_plan_init(&p); hg_plan_in_t t = hin(0, 900); t.dp_tomorrow = &tom;
    n = hrun_day(&p, t, 900, sh, &missed, NULL, 0, -1, -1); print_day("N7 day", sh, n);
    HCHECK(has(sh, n, HG_N_EVENING) == 1 && at(sh, n, HG_N_EVENING) == 21 * 60, "N7 once, at bedtime - 60 = 21:00 (default bedtime 22:00)");
    HCHECK(strcmp(hg_nudge_text(&p, HG_N_EVENING, b, sizeof b), "\xce\x91\xcf\x8d\xcf\x81\xce\xb9\xce\xbf: \xce\xb1\xce\xb3\xce\xbf\xcf\x81\xce\xac \xcf\x80\xcf\x81\xce\xb9\xce\xbd \xcf\x84\xce\xb9\xcf\x82 09:30") == 0, "N7 text «Αύριο: αγορά πριν τις 09:30» (kind 1 wins over kind 3)");
    HCHECK(missed == 1, "N7 not pressed -> MISSED after 10 min");
    hg_dpday_t t3 = { 1, { hwave(3) } }; hg_plan_init(&p); t.dp_tomorrow = &t3;
    n = hrun_day(&p, t, 901, sh, &missed, NULL, 0, -1, -1);
    HCHECK(has(sh, n, HG_N_EVENING) == 1 && strcmp(hg_nudge_text(&p, HG_N_EVENING, b, sizeof b), "\xce\x91\xcf\x8d\xcf\x81\xce\xb9\xce\xbf: \xce\xba\xce\xb1\xcf\x8d\xcf\x83\xcf\x89\xce\xbd\xce\xb1\xcf\x82, \xce\xbc\xce\xad\xcf\x81\xce\xb1 3") == 0, "only kind 3 tomorrow -> «Αύριο: καύσωνας, μέρα 3»");
    hg_dpday_t t2 = { 1, { air(19, 0) } }; hg_plan_init(&p); t.dp_tomorrow = &t2;
    n = hrun_day(&p, t, 902, sh, &missed, NULL, 0, -1, -1); HCHECK(has(sh, n, HG_N_EVENING) == 0, "tomorrow with only kind 2 -> no N7");
    hg_plan_init(&p); t.dp_tomorrow = NULL; n = hrun_day(&p, t, 903, sh, &missed, NULL, 0, -1, -1); HCHECK(n == 0, "no plan, cool day -> no nudge at all");
    /* first kind 1 by USUAL time; direction 2 text */
    hg_dpday_t t1 = { 2, { outing(HG_PL_CAFE, 18, 0, 19, 30, HG_DIR_AFTER, 12, 19, 34), outing(HG_PL_PHARMACY, 11, 0, 9, 0, HG_DIR_BEFORE, 11, 18, 35) } };
    hg_plan_init(&p); t.dp_tomorrow = &t1; hrun_day(&p, t, 904, sh, &missed, NULL, 0, -1, -1);
    HCHECK(strcmp(hg_nudge_text(&p, HG_N_EVENING, b, sizeof b), "\xce\x91\xcf\x8d\xcf\x81\xce\xb9\xce\xbf: \xcf\x86\xce\xb1\xcf\x81\xce\xbc\xce\xb1\xce\xba\xce\xb5\xce\xaf\xce\xbf \xcf\x80\xcf\x81\xce\xb9\xce\xbd \xcf\x84\xce\xb9\xcf\x82 09:00") == 0, "N7 picks the earliest usual time (pharmacy 11:00 before café 18:00)");
    hg_dpday_t t1b = { 1, { outing(HG_PL_WALK, 19, 0, 21, 0, HG_DIR_AFTER, 12, 21, 34) } };
    hg_plan_init(&p); t.dp_tomorrow = &t1b; hrun_day(&p, t, 905, sh, &missed, NULL, 0, -1, -1);
    HCHECK(strcmp(hg_nudge_text(&p, HG_N_EVENING, b, sizeof b), "\xce\x91\xcf\x8d\xcf\x81\xce\xb9\xce\xbf: \xce\xb2\xcf\x8c\xce\xbb\xcf\x84\xce\xb1 \xce\xbc\xce\xb5\xcf\x84\xce\xac \xcf\x84\xce\xb9\xcf\x82 21:00") == 0, "direction 2 -> «Αύριο: βόλτα μετά τις 21:00» (the spec example)");
    /* bedtime sources */
    hg_seed_t s; hg_seed_clear(&s); s.bed_h = 23; s.bed_m = 0; s.wake_h = 7; s.wake_m = 0;
    hg_plan_in_t q = hin(0, 906); q.seed = &s; HCHECK(hg_plan_n7_time(&q) == 22 * 60, "stated bedtime 23:00 -> N7 at 22:00");
    q.l_valid = 1; q.l_days = 3; q.l_sleep_on = 22 * 60 + 30; HCHECK(hg_plan_n7_time(&q) == 21 * 60 + 30, "learned >= 3 days (22:30) wins -> 21:30");
    q.l_days = 2; HCHECK(hg_plan_n7_time(&q) == 22 * 60, "learned < 3 days -> stated");
    q.seed = NULL; q.l_valid = 0; HCHECK(hg_plan_n7_time(&q) == 21 * 60, "nothing known -> 21:00");
    q.l_valid = 1; q.l_days = 5; q.l_sleep_on = 30; HCHECK(hg_plan_n7_time(&q) == 23 * 60 + 30, "learned bedtime 00:30 -> 23:30 the evening before");
    hg_plan_init(&p); t = hin(0, 907); t.dp_tomorrow = &tom; t.seed = &s; s.bed_h = 23;
    n = hrun_day(&p, t, 907, sh, &missed, NULL, 0, -1, -1);
    HCHECK(at(sh, n, HG_N_EVENING) == 22 * 60, "stated bedtime 23:00: N7 fires at 22:00 (outside her sleep window)"); }

  { /* N1 upgraded + N5 re-timed + N3 gone */
    hg_dpday_t td = { 2, { outing(HG_PL_WALK, 19, 0, 21, 0, HG_DIR_AFTER, 12, 21, 34), air(19, 0) } };
    hfc_cool_day(); hg_plan_t p; hg_plan_init(&p); hg_plan_in_t t = hin(0, 910); t.fc72 = HFC; t.dp_today = &td;
    n = hrun_day(&p, t, 910, sh, &missed, NULL, 0, -1, -1); print_day("plan on a cool-forecast day", sh, n);
    HCHECK(at(sh, n, HG_N_BRIEF) == 8 * 60 + 30, "N1 fires on a day with a kind-1 outing even when the forecast is not a heat-day (08:30)");
    HCHECK(strcmp(hg_nudge_text(&p, HG_N_BRIEF, b, sizeof b), "\xce\xa3\xce\xae\xce\xbc\xce\xb5\xcf\x81\xce\xb1: \xce\xb2\xcf\x8c\xce\xbb\xcf\x84\xce\xb1 \xce\xbc\xce\xb5\xcf\x84\xce\xac \xcf\x84\xce\xb9\xcf\x82 21:00") == 0, "N1 text «Σήμερα: βόλτα μετά τις 21:00»");
    HCHECK(at(sh, n, HG_N_AIR) == 19 * 60, "N5 AIR at the kind-2 suggested time 19:00 (not 21:30), no night-heat needed");
    hg_plan_init(&p); t.fc72 = NULL; n = hrun_day(&p, t, 911, sh, &missed, NULL, 0, -1, -1);
    HCHECK(at(sh, n, HG_N_AIR) == 19 * 60 && at(sh, n, HG_N_BRIEF) == 8 * 60 + 30, "kind 2 and kind 1 work without any forecast");
    hfc_heat_day(); hg_plan_init(&p); t = hin(0, 912); t.fc72 = HFC; t.room_c = 27.0f;
    n = hrun_day(&p, t, 912, sh, &missed, NULL, 0, -1, -1); print_day("heat day, no plan", sh, n);
    HCHECK(has(sh, n, HG_N_SHUTTERS) == 0, "N3 SHUTTERS never shown");
    HCHECK(at(sh, n, HG_N_AIR) == 21 * 60 + 30 && at(sh, n, HG_N_BRIEF) == 8 * 60 + 30, "no plan: N1 08:30 classic + N5 21:30 unchanged from 0.9.7");
    HCHECK(strcmp(hg_nudge_text(&p, HG_N_BRIEF, b, sizeof b), "\xce\xa3\xce\xae\xce\xbc\xce\xb5\xcf\x81\xce\xb1 \xce\xb6\xce\xad\xcf\x83\xcf\x84\xce\xb7. \xce\x92\xce\xb3\xce\xb5\xce\xaf\xcf\x84\xce\xb5 \xcf\x80\xcf\x81\xce\xb9\xce\xbd \xcf\x84\xce\xb9\xcf\x82 10:00") == 0, "no kind 1 today -> the 0.9.7 N1 text");
    HCHECK(hg_nudge_text(&p, HG_N_SHUTTERS, b, sizeof b)[0] == 0, "no N3 text any more");
    /* N1 by press with a kind-1 plan on a non-heat day */
    hfc_cool_day(); hg_plan_init(&p); hg_plan_in_t in = hin(7 * 60 + 10, 913); in.fc72 = HFC; in.dp_today = &td; in.press = 1;
    HCHECK(hg_plan_press(&p, &in) == HG_N_BRIEF && p.t1.kind == 1, "N1 by the first press after 07:00 also with a kind-1 plan");
    /* N7 vs AIR on a night-heat evening without kind 2: AIR (21:30) wins, N7 would block it */
    hfc_heat_day(); hg_dpday_t tom = { 1, { outing(HG_PL_MARKET, 10, 30, 9, 30, 1, 11, 18, 36) } };
    hg_plan_init(&p); t = hin(0, 914); t.fc72 = HFC; t.dp_tomorrow = &tom;
    n = hrun_day(&p, t, 914, sh, &missed, NULL, 0, -1, -1); print_day("night-heat, N7 + 21:30 AIR", sh, n);
    HCHECK(at(sh, n, HG_N_AIR) == 21 * 60 + 30 && has(sh, n, HG_N_EVENING) == 0, "AIR wins over N7 when both cannot fit (default bedtime, no kind 2)");
    hg_dpday_t tdk = { 1, { air(20, 0) } }; hg_plan_init(&p); t.dp_today = &tdk;
    n = hrun_day(&p, t, 915, sh, &missed, NULL, 0, -1, -1); print_day("kind 2 at 20:00 + N7", sh, n);
    HCHECK(at(sh, n, HG_N_AIR) == 20 * 60 && at(sh, n, HG_N_EVENING) == 21 * 60, "kind 2 at 20:00 and N7 at 21:00 both fit (60 min apart)");
    HCHECK(n == 6 && has(sh, n, HG_N_WATER) == 2, "the last two daily slots are kept for AIR and N7 (only 2 WATERs, 6 in total)"); }

  { /* N8 LEAVE_HOT */
    hg_dpday_t td = { 1, { outing(HG_PL_MARKET, 12, 0, 9, 30, HG_DIR_BEFORE, 11, 18, 36) } };
    hg_plan_t p; hg_plan_init(&p); hg_plan_in_t t = hin(0, 920); t.dp_today = &td;
    /* home; out 12:00; back 13:00; out 13:20 (only 20 min home: not re-armed); back 14:00; out 15:00 (re-armed);
     * back 15:40; out 16:30 (re-armed, but 2/day reached) */
    const uint16_t sw[] = { 12 * 60, HG_HO_TRANSIT, 12 * 60 + 5, HG_HO_OUT, 13 * 60, HG_HO_HOME, 13 * 60 + 20, HG_HO_TRANSIT, 14 * 60, HG_HO_HOME,
                            15 * 60, HG_HO_TRANSIT, 15 * 60 + 40, HG_HO_HOME, 16 * 60 + 30, HG_HO_TRANSIT, 17 * 60, HG_HO_HOME };
    n = hrun_day(&p, t, 920, sh, &missed, sw, 9, -1, -1); print_day("N8 outings", sh, n);
    int n8a = -1, n8b = -1, k8 = 0; for (int i = 0; i < n; i++) if (sh[i].id == HG_N_LEAVE_HOT) { if (!k8) n8a = sh[i].mod; else n8b = sh[i].mod; k8++; }
    HCHECK(n8a == 12 * 60, "N8 at the HOME -> TRANSIT minute inside the 11-18 hot window (12:00)");
    HCHECK(k8 == 2 && n8b == 15 * 60, "13:20 leave after 20 min home: not re-armed; 15:00 after 60 min home: N8 again; 16:30: max 2/day (got %d)", k8);
    HCHECK(strcmp(hg_nudge_text(&p, HG_N_LEAVE_HOT, b, sizeof b), "\xce\x88\xce\xbe\xcf\x89 \xce\xba\xce\xac\xce\xbd\xce\xb5\xce\xb9 \xce\xb6\xce\xad\xcf\x83\xcf\x84\xce\xb7. \xce\xa0\xce\xac\xcf\x81\xcf\x84\xce\xb5 \xce\xbd\xce\xb5\xcf\x81\xcf\x8c.") == 0, "N8 text «Έξω κάνει ζέστη. Πάρτε νερό.»");
    HCHECK(n8b - n8a < 4 * 60 && p.n8_count == 2, "two N8s 3 h apart counted (n8_count 2)");
    /* outside the hot window: no N8, and the leave still uses up the outing */
    hg_plan_init(&p); const uint16_t sw2[] = { 9 * 60, HG_HO_TRANSIT, 10 * 60, HG_HO_HOME };
    n = hrun_day(&p, t, 921, sh, &missed, sw2, 2, -1, -1); HCHECK(has(sh, n, HG_N_LEAVE_HOT) == 0, "leaving at 09:00 (before the 11-18 hot window): no N8");
    /* leaving at 10:55, the hot window opens at 11:00 -> still "as she leaves" (10-min eligibility) */
    hg_plan_init(&p); const uint16_t sw3[] = { 10 * 60 + 55, HG_HO_TRANSIT };
    n = hrun_day(&p, t, 922, sh, &missed, sw3, 1, -1, -1); HCHECK(at(sh, n, HG_N_LEAVE_HOT) == 11 * 60, "leave 10:55, hot from 11:00 -> N8 at 11:00 (within the 10 min after the leave)");
    hg_plan_init(&p); const uint16_t sw4[] = { 10 * 60 + 40, HG_HO_TRANSIT };
    n = hrun_day(&p, t, 923, sh, &missed, sw4, 1, -1, -1); HCHECK(has(sh, n, HG_N_LEAVE_HOT) == 0, "leave 10:40 (hot only 20 min later) -> no N8");
    /* warnings win; N8 waits up to 10 min for the warning to end */
    hg_plan_init(&p); n = hrun_day(&p, t, 924, sh, &missed, sw, 1, 11 * 60 + 58, 12 * 60 + 4);
    HCHECK(at(sh, n, HG_N_LEAVE_HOT) == 12 * 60 + 4, "leave during a warning: N8 right after the warning ends (12:04)");
    hg_plan_init(&p); n = hrun_day(&p, t, 925, sh, &missed, sw, 1, 11 * 60 + 58, 12 * 60 + 30);
    HCHECK(has(sh, n, HG_N_LEAVE_HOT) == 0, "warning on for the whole 10 min after the leave: no N8");
    /* sleep window */
    hg_dpday_t tn = { 1, { outing(HG_PL_WALK, 23, 0, 21, 0, HG_DIR_BEFORE, 22, 24, 31) } };
    hg_plan_init(&p); hg_plan_in_t t5 = t; t5.dp_today = &tn; const uint16_t sw5[] = { 22 * 60 + 30, HG_HO_TRANSIT };
    n = hrun_day(&p, t5, 926, sh, &missed, sw5, 1, -1, -1); HCHECK(has(sh, n, HG_N_LEAVE_HOT) == 0, "leave at 22:30 inside the sleep window (22:00-08:00): no N8");
    /* exempt from the 60-min spacing; replaces a lower nudge; counts toward 6 */
    hg_plan_init(&p); hg_plan_in_t in = hin(12 * 60 + 55, 927); in.dp_today = &td; in.room_c = 29.0f; hg_plan_out_t o;
    hg_plan_minute(&p, &in, &o); HCHECK(o.show == HG_N_WATER, "WATER shown at 12:55 (room 29 C)");
    for (uint16_t m = 12 * 60 + 56; m < 13 * 60; m++) { in.mod = m; hg_plan_minute(&p, &in, &o); }
    in.mod = 13 * 60; in.home_out = HG_HO_TRANSIT; hg_plan_minute(&p, &in, &o);
    HCHECK(o.show == HG_N_LEAVE_HOT && o.missed == HG_N_WATER && p.active == HG_N_LEAVE_HOT, "N8 5 min after WATER (no 60-min spacing) and the open WATER is MISSED");
    hg_plan_done(&p, in.mod);
    in.mod = 13 * 60 + 30; in.home_out = HG_HO_OUT; hg_plan_minute(&p, &in, &o);
    HCHECK(!o.show, "N8 restarts the 60-min spacing for the others (no WATER at 13:30)");
    hg_plan_init(&p); p.day = 928; p.count = 6; in = hin(12 * 60, 928); in.dp_today = &td; in.home_out = HG_HO_HOME; hg_plan_minute(&p, &in, &o);
    in.mod++; in.home_out = HG_HO_TRANSIT; hg_plan_minute(&p, &in, &o); HCHECK(!o.show && p.n8_pending, "6 nudges already today: no N8 (it counts toward 6)");
    /* VISIT from her phone */
    hg_plan_init(&p); in = hin(12 * 60, 929); in.dp_today = &td; in.home_out = 0xFF;
    hg_plan_visit(&p, &in, HG_VISIT_LEAVE, HG_PL_HOME, 1, &o); HCHECK(o.show == HG_N_LEAVE_HOT, "a fresh VISIT LEAVE home inside the hot window -> N8 at once");
    hg_plan_done(&p, in.mod);
    in.mod = 12 * 60 + 2; in.home_out = HG_HO_TRANSIT; hg_plan_minute(&p, &in, &o); HCHECK(!o.show, "the band's own HOME->TRANSIT of the same outing: no second N8");
    hg_plan_init(&p); in.home_out = 0xFF; hg_plan_visit(&p, &in, HG_VISIT_LEAVE, HG_PL_HOME, 0, &o); HCHECK(!o.show && p.n8_armed, "a late (queued) VISIT LEAVE: no N8, still armed");
    hg_plan_visit(&p, &in, HG_VISIT_LEAVE, HG_PL_MARKET, 1, &o); HCHECK(!o.show, "VISIT LEAVE from the market (not home): no N8");
    /* re-arm by VISIT ARRIVE home + 30 min */
    hg_plan_init(&p); in = hin(12 * 60, 930); in.dp_today = &td; in.home_out = 0xFF;
    hg_plan_visit(&p, &in, HG_VISIT_LEAVE, HG_PL_HOME, 1, &o); hg_plan_done(&p, in.mod);
    in.mod = 13 * 60; hg_plan_visit(&p, &in, HG_VISIT_ARRIVE, HG_PL_HOME, 1, &o);
    for (uint16_t m = 13 * 60; m <= 13 * 60 + 29; m++) { in.mod = m; hg_plan_minute(&p, &in, &o); }
    HCHECK(!p.n8_armed, "29 min after VISIT ARRIVE home: not re-armed yet");
    in.mod = 13 * 60 + 30; hg_plan_minute(&p, &in, &o); HCHECK(p.n8_armed, "30 min after VISIT ARRIVE home: re-armed");
    in.mod = 14 * 60 + 30; hg_plan_visit(&p, &in, HG_VISIT_LEAVE, HG_PL_HOME, 1, &o); HCHECK(o.show == HG_N_LEAVE_HOT && p.n8_count == 2, "second outing -> N8 (2/day)");
    /* a heat-day non-safe hour without any plan (forecast safe 06-10) */
    hfc_heat_day(); hg_plan_init(&p); in = hin(11 * 60, 931); in.fc72 = HFC; in.home_out = HG_HO_HOME; hg_plan_homeout(&p, &in, &o);
    in.home_out = HG_HO_TRANSIT; hg_plan_homeout(&p, &in, &o); HCHECK(o.show == HG_N_LEAVE_HOT, "heat-day, 11:00 is not a safe hour -> N8 (console homeout path)");
    hg_plan_init(&p); in.mod = 8 * 60 + 15; in.home_out = HG_HO_HOME; hg_plan_homeout(&p, &in, &o); in.home_out = HG_HO_TRANSIT; hg_plan_homeout(&p, &in, &o);
    HCHECK(!o.show, "heat-day, 08:15 is a safe hour -> no N8");
    hg_dpday_t th = { 1, { hwave(2) } }; hg_plan_init(&p); in = hin(13 * 60, 932); in.dp_today = &th; in.home_out = HG_HO_HOME; hg_plan_homeout(&p, &in, &o);
    in.home_out = HG_HO_TRANSIT; hg_plan_homeout(&p, &in, &o); HCHECK(!o.show, "kind 3 heat-day but no safe-hours info and no hot window: no N8");
    in.have_safe = 1; in.safe_bitmap = 0x3C0; hg_plan_init(&p); in.home_out = HG_HO_HOME; hg_plan_homeout(&p, &in, &o); in.home_out = HG_HO_TRANSIT; hg_plan_homeout(&p, &in, &o);
    HCHECK(o.show == HG_N_LEAVE_HOT, "kind 3 heat-day + SAFE_HOURS (13:00 not safe) -> N8");
    /* N8 timeout */
    int k = 0; for (; k < 10 && p.active; k++) { in.mod++; hg_plan_minute(&p, &in, &o); }
    HCHECK(!p.active && o.missed == HG_N_LEAVE_HOT && k == 10, "N8 not pressed -> MISSED after 10 min"); }

  { /* every cap on a full Her Day (heat-wave day 2, the demo shape): plan + 3 outings + warnings */
    hfc_heat_day();
    hg_dpday_t td = { 3, { outing(HG_PL_MARKET, 10, 30, 9, 0, HG_DIR_BEFORE, 11, 19, 37), outing(HG_PL_CAFE, 18, 0, 19, 30, HG_DIR_AFTER, 11, 19, 36), air(20, 0) } };
    hg_dpday_t tom = { 2, { hwave(3), outing(HG_PL_CHURCH, 10, 0, 8, 30, HG_DIR_BEFORE, 11, 19, 38) } };
    hg_plan_t p; hg_plan_init(&p); hg_plan_in_t t = hin(0, 940); t.fc72 = HFC; t.dp_today = &td; t.dp_tomorrow = &tom; t.room_c = 26.0f;
    const uint16_t sw[] = { 10 * 60 + 30, HG_HO_TRANSIT, 11 * 60 + 30, HG_HO_HOME, 12 * 60 + 30, HG_HO_TRANSIT, 13 * 60 + 30, HG_HO_HOME, 18 * 60, HG_HO_TRANSIT, 19 * 60, HG_HO_HOME };
    n = hrun_day(&p, t, 940, sh, &missed, sw, 6, 14 * 60, 15 * 60); print_day("full Her Day", sh, n);
    int sp = 1, quiet = 0, warn = 0;
    for (int i = 0; i < n; i++) {
      quiet |= sh[i].mod < 480 || sh[i].mod >= 1320; warn |= sh[i].mod >= 14 * 60 && sh[i].mod < 15 * 60;
      if (i && sh[i].id != HG_N_LEAVE_HOT && sh[i].mod - sh[i - 1].mod < 60) sp = 0;
    }
    HCHECK(n <= 6, "full day: <= 6 nudges in total, N8 included (%d)", n);
    HCHECK(sp, "full day: >= 60 min between nudges except N8");
    HCHECK(!quiet && !warn, "full day: none in the sleep window, none during the 14:00-15:00 warning");
    HCHECK(has(sh, n, HG_N_LEAVE_HOT) >= 1 && has(sh, n, HG_N_LEAVE_HOT) <= 2 && has(sh, n, HG_N_SHUTTERS) == 0, "full day: N8 1-2x, no N3");
    HCHECK(at(sh, n, HG_N_BRIEF) == 8 * 60 + 30 && p.t1.place == HG_PL_MARKET, "full day: N1 «Σήμερα: αγορά πριν τις 09:00» at 08:30");
    /* a warning replaces an open N7 at once */
    hg_plan_init(&p); hg_plan_in_t in = hin(21 * 60, 941); in.dp_tomorrow = &tom; hg_plan_out_t o; hg_plan_minute(&p, &in, &o);
    HCHECK(o.show == HG_N_EVENING, "N7 at 21:00");
    in.mod++; in.warning = 1; hg_plan_minute(&p, &in, &o); HCHECK(o.missed == HG_N_EVENING && !p.active, "a warning replaces the open N7 at once (MISSED)");
    in.warning = 0; for (uint16_t m = in.mod + 1; m < 22 * 60; m++) { in.mod = m; hg_plan_minute(&p, &in, &o); if (o.show) break; }
    HCHECK(!o.show, "N7 once a day (not again after the warning)");
    /* console force */
    hg_plan_init(&p); in = hin(12 * 60, 942);
    HCHECK(hg_plan_force(&p, HG_N_EVENING, &in) == 0 && !p.active, "console nudge 7 without a tomorrow plan: refused (no text)");
    in.dp_tomorrow = &tom; HCHECK(hg_plan_force(&p, HG_N_EVENING, &in) == HG_N_EVENING && p.t7.kind == 1, "console nudge 7 with a plan");
    HCHECK(hg_plan_force(&p, HG_N_LEAVE_HOT, &in) == HG_N_LEAVE_HOT && p.n8_count == 1, "console nudge 8"); }

  /* ---------------------------------------------------------------- 5. screen layout */
  { hg_plan_t p; hg_plan_init(&p); int worst_lines = 0, worst_px = 0, ok = 1, cnt = 0, minsize = 3; char worst[128] = "";
    for (int pre = 0; pre < 2; pre++) for (uint8_t pl = 0; pl < HG_PL_N; pl++) for (uint8_t dir = 1; dir <= 2; dir++) {
      hg_ptxt_t x = { 1, pl, dir, 23, 59, 0 }; if (pre) p.t7 = x; else p.t1 = x;
      const char *s = hg_nudge_text(&p, pre ? HG_N_EVENING : HG_N_BRIEF, b, sizeof b);
      int sz, ln, px; int f = layout(s, 150, 250, &sz, &ln, &px); ok &= f; cnt++;
      if (f && sz < minsize) minsize = sz;
      if (f && (ln > worst_lines || (ln == worst_lines && px > worst_px))) { worst_lines = ln; worst_px = px; snprintf(worst, sizeof worst, "%s", s); }
      if (!f) printf("      does not fit: %s\n", s);
    }
    for (uint8_t d = 0; d <= 31; d++) { hg_ptxt_t x = { 3, 0, 0, 0, 0, d }; p.t7 = x; int sz, ln, px; int f = layout(hg_nudge_text(&p, HG_N_EVENING, b, sizeof b), 150, 250, &sz, &ln, &px); ok &= f; cnt++; }
    { int sz, ln, px; const char *t8 = hg_nudge_text(&p, HG_N_LEAVE_HOT, b, sizeof b); int f = layout(t8, 150, 250, &sz, &ln, &px); ok &= f; cnt++;
      printf("      N8 «%s»: size %d, %d line(s), widest %d px\n", t8, sz, ln, px); }
    printf("      longest: «%s» -> %d lines, widest line %d px of 240\n", worst, worst_lines, worst_px);
    HCHECK(ok && worst_px <= 240 && worst_lines <= 4, "all %d Her Day texts (7 places x 2 directions x N1/N7, heat-wave day 0-31, N8) wrap and fit the 240 x 100 px nudge box", cnt); }

  /* ---------------------------------------------------------------- vectors for the iOS app */
  if (vec_path) {
    FILE *f = fopen(vec_path, "w"); if (!f) { printf("FAIL  cannot write %s\n", vec_path); return hfails + 1; }
    char h[48]; uint8_t fr[20];
    fprintf(f, "{\n  \"about\": \"Heat Guardian band 0.9.8 Her Day frames (HERDAY_SPEC.md 4, ECOSYSTEM_SPEC.md 5d). Generated by fw/tools/test_herday.c from the firmware encoders. All frames 20 bytes, little-endian, byte 19 = CRC-8 poly 0x07 init 0x00 over bytes 0..18 (same as STATUS and the 0.9.7 frames).\",\n");
    fprintf(f, "  \"crc8_check\": {\"input_ascii\": \"123456789\", \"crc8\": \"%02x\"},\n", hg_crc8((const uint8_t *)"123456789", 9));
    fprintf(f, "  \"place_types\": {\"0\": \"home\", \"1\": \"market\", \"2\": \"church\", \"3\": \"walk/park\", \"4\": \"pharmacy\", \"5\": \"cafe\", \"6\": \"doctor\", \"7\": \"other\"},\n");
    fprintf(f, "  \"day_plan\": [\n");
    struct { uint8_t day, idx, n; hg_dpi_t it; const char *note; } V[] = {
      { 1, 1, 4, outing(HG_PL_MARKET, 10, 30, 9, 30, HG_DIR_BEFORE, 11, 19, 37), "tomorrow 1/4: OUTING_SHIFT market, usual 10:30, go BEFORE 09:30, hot 11-19 (to exclusive), peak 37 C. Band N7: «Αύριο: αγορά πριν τις 09:30»" },
      { 1, 2, 4, outing(HG_PL_WALK, 19, 0, 21, 0, HG_DIR_AFTER, 12, 21, 34), "tomorrow 2/4: OUTING_SHIFT walk, usual 19:00, go AFTER 21:00, hot 12-21, peak 34 C" },
      { 1, 3, 4, air(20, 0), "tomorrow 3/4: AIR_OPEN at 20:00 (N5 AIR fires then instead of 21:30)" },
      { 1, 4, 4, hwave(2), "tomorrow 4/4: HEATWAVE_DAY day 2. The band replaces tomorrow's plan only now (index == n, all 4 received)" },
      { 0, 1, 1, outing(HG_PL_PHARMACY, 0xFF, 0xFF, 9, 0, HG_DIR_BEFORE, 11, 18, 0xFF), "today 1/1: OUTING_SHIFT pharmacy, usual n/a (0xFF 0xFF), before 09:00, peak unknown (0xFF). Band N1: «Σήμερα: φαρμακείο πριν τις 09:00»" },
      { 0, 1, 1, outing(HG_PL_CAFE, 18, 0, 19, 30, HG_DIR_AFTER, 11, 24, 36), "today 1/1: hot window to_h 24 = until midnight" },
      { 0, 0, 0, hwave(0), "clear today's plan (index 0, n 0; item bytes 0)" } };
    for (unsigned i = 0; i < sizeof V / sizeof V[0]; i++) {
      hg_eco_pack_dayplan(V[i].day, V[i].idx, V[i].n, V[i].n ? &V[i].it : NULL, fr); hexs(fr, 20, h);
      hg_eco_cmd_t c; int rc = hg_eco_cmd_parse(fr, 20, &c);
      fprintf(f, "    {\"hex\": \"%s\", \"op\": \"0x1B\", \"day\": %u, \"index\": %u, \"n\": %u, \"kind\": %u, \"place\": %u, \"usual\": [%u, %u], \"suggested\": [%u, %u], \"direction\": %u, \"hot\": [%u, %u], \"peak_c\": %u, \"heatwave_day\": %u, \"band_reply\": \"%s\", \"note\": \"%s\"}%s\n",
              h, V[i].day, V[i].idx, V[i].n, V[i].n ? V[i].it.kind : 0, V[i].it.place, V[i].it.usual_h, V[i].it.usual_m, V[i].it.sugg_h, V[i].it.sugg_m, V[i].it.dir, V[i].it.hot_from, V[i].it.hot_to,
              V[i].it.peak_c, V[i].it.hw_day, rc > 0 ? "# CMD ok op=0x1b" : "error", V[i].note, i + 1 < sizeof V / sizeof V[0] ? "," : "");
    }
    fprintf(f, "  ],\n  \"day_plan_field_errors\": [\n");
    const hg_dpi_t g = outing(HG_PL_MARKET, 10, 30, 9, 30, 1, 11, 18, 36);
    struct { int pos; uint8_t v; const char *what; } E[] = { { 1, 2, "day 2" }, { 2, 3, "index 3 > n 2" }, { 4, 0, "kind 0" }, { 4, 4, "kind 4" }, { 5, 8, "place 8" },
      { 6, 24, "usual h 24" }, { 7, 0xFF, "usual pair half set" }, { 9, 60, "suggested m 60" }, { 10, 0, "kind 1 direction 0" }, { 12, 25, "hot to_h 25" }, { 11, 19, "kind 1 hot from > to" } };
    for (unsigned i = 0; i < sizeof E / sizeof E[0]; i++) {
      hg_eco_pack_dayplan(0, 1, 2, &g, fr); fr[E[i].pos] = E[i].v; fr[19] = hg_crc8(fr, 19); hexs(fr, 20, h); hg_eco_cmd_t c;
      fprintf(f, "    {\"hex\": \"%s\", \"error\": \"%s\", \"band_reply\": \"# CMD error %d op=0x1b len=20\"},\n", h, E[i].what, hg_eco_cmd_parse(fr, 20, &c));
    }
    hg_eco_pack_dayplan(0, 1, 2, &g, fr); fr[3] = 7; fr[19] = hg_crc8(fr, 19); hexs(fr, 20, h); { hg_eco_cmd_t c;
    fprintf(f, "    {\"hex\": \"%s\", \"error\": \"n 7 (> 6)\", \"band_reply\": \"# CMD error %d op=0x1b len=20\"}\n  ],\n", h, hg_eco_cmd_parse(fr, 20, &c)); }
    fprintf(f, "  \"visit\": [\n");
    const struct { uint8_t ev, pl; uint32_t u; const char *note; } VV[] = {
      { HG_VISIT_LEAVE, HG_PL_HOME, 1795420800u, "leave home (her phone). If inside a hot window of today's plan and within 10 min of the band clock: N8 «Έξω κάνει ζέστη. Πάρτε νερό.»" },
      { HG_VISIT_ARRIVE, HG_PL_MARKET, 1795421700u, "arrive at the market" },
      { HG_VISIT_LEAVE, HG_PL_MARKET, 1795425300u, "leave the market" },
      { HG_VISIT_ARRIVE, HG_PL_HOME, 1795426200u, "back home (N8 re-arms after 30 min home)" } };
    for (unsigned i = 0; i < 4; i++) { hg_eco_pack_visit(VV[i].ev, VV[i].pl, VV[i].u, fr); hexs(fr, 20, h);
      fprintf(f, "    {\"hex\": \"%s\", \"op\": \"0x1C\", \"event\": %u, \"place\": %u, \"unix\": %lu, \"note\": \"%s\"}%s\n", h, VV[i].ev, VV[i].pl, (unsigned long)VV[i].u, VV[i].note, i < 3 ? "," : ""); }
    fprintf(f, "  ],\n  \"events\": [\n");
    { uint8_t x[8]; hg_ev_t e; memset(&e, 0, sizeof e);
      hg_visit_echo(HG_VISIT_ARRIVE, 1795421700u, x); e.seq = 21; e.type = HG_EV_VISIT; e.arg = HG_PL_MARKET; e.unix_s = 1795421712u; memcpy(e.x, x, 8); hg_ev_pack(&e, 37, fr); hexs(fr, 20, h);
      fprintf(f, "    {\"hex\": \"%s\", \"version\": 3, \"seq\": 21, \"boot_count\": 37, \"unix\": 1795421712, \"type\": 9, \"type_name\": \"VISIT\", \"arg_place\": 1, \"byte11_event\": 1, \"bytes12_15_visit_unix\": 1795421700, \"note\": \"arrive market; the frame's own unix (5-8) is when the band logged it\"},\n", h);
      hg_visit_echo(HG_VISIT_LEAVE, 1795420800u, x); e.seq = 20; e.arg = HG_PL_HOME; e.unix_s = 1795420803u; memcpy(e.x, x, 8); hg_ev_pack(&e, 37, fr); hexs(fr, 20, h);
      fprintf(f, "    {\"hex\": \"%s\", \"version\": 3, \"seq\": 20, \"boot_count\": 37, \"unix\": 1795420803, \"type\": 9, \"type_name\": \"VISIT\", \"arg_place\": 0, \"byte11_event\": 2, \"bytes12_15_visit_unix\": 1795420800, \"note\": \"leave home\"},\n", h);
      for (unsigned i = 0; i < 4; i++) {
        hg_eco_cmd_t c; hg_eco_pack_dayplan(V[i].day, V[i].idx, V[i].n, &V[i].it, fr); hg_eco_cmd_parse(fr, 20, &c);
        hg_dp_echo(&c.dpi, V[i].day, x); e.seq = (uint16_t)(30 + i); e.type = HG_EV_PLAN_ITEM; e.arg = c.dpi.kind; e.unix_s = 1795449600u; memcpy(e.x, x, 8); hg_ev_pack(&e, 37, fr); hexs(fr, 20, h);
        fprintf(f, "    {\"hex\": \"%s\", \"version\": 3, \"seq\": %u, \"boot_count\": 37, \"unix\": 1795449600, \"type\": 10, \"type_name\": \"PLAN_ITEM\", \"arg_kind\": %u, \"place\": %u, \"usual\": [%u, %u], \"suggested\": [%u, %u], \"hot\": [%u, %u], \"byte18\": %u, \"byte18_day\": %u, \"byte18_direction\": %u, \"byte18_heatwave_day\": %u, \"note\": \"echo of day_plan[%u] (peak_c is not echoed: no room)\"},\n",
                h, e.seq, c.dpi.kind, x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7], x[7] & 1, (x[7] >> 1) & 3, x[7] >> 3, i);
      }
      static const char *NN[] = { "", "", "", "", "", "", "", "EVENING_BRIEF", "LEAVE_HOT" };
      for (uint8_t id = 7; id <= 8; id++) for (uint8_t ty = 1; ty <= 3; ty++) {
        hg_ev_t q; memset(&q, 0, sizeof q); q.seq = (uint16_t)(40 + (id - 7) * 3 + ty); q.type = ty; q.arg = id; q.unix_s = 1795460000u + ty * 60u; hg_ev_pack(&q, 37, fr); hexs(fr, 20, h);
        fprintf(f, "    {\"hex\": \"%s\", \"version\": 3, \"seq\": %u, \"boot_count\": 37, \"unix\": %lu, \"type\": %u, \"type_name\": \"%s\", \"nudge_id\": %u, \"nudge_name\": \"%s\"}%s\n",
                h, q.seq, (unsigned long)q.unix_s, ty, hg_ev_name(ty), id, NN[id], (id == 8 && ty == 3) ? "" : ",");
      } }
    fprintf(f, "  ],\n  \"elder_action_new_ids\": [\n");
    for (uint8_t id = 7; id <= 8; id++) { hg_eco_pack_action(HG_ACT_NUDGE_DONE, id, fr); hexs(fr, 20, h);
      fprintf(f, "    {\"hex\": \"%s\", \"op\": \"0x1A\", \"action\": 2, \"nudge_id\": %u}%s\n", h, id, id == 7 ? "," : ""); }
    fprintf(f, "  ],\n  \"band_texts\": {\n");
    { hg_plan_t p; hg_plan_init(&p); hg_ptxt_t x7 = { 1, HG_PL_MARKET, 1, 9, 30, 0 }; p.t7 = x7; hg_ptxt_t x1 = { 1, HG_PL_WALK, 2, 21, 0, 0 }; p.t1 = x1;
      fprintf(f, "    \"N7_kind1_before\": \"%s\",\n", hg_nudge_text(&p, HG_N_EVENING, b, sizeof b));
      p.t7.dir = 2; p.t7.place = HG_PL_CAFE; p.t7.h = 21; p.t7.m = 0; fprintf(f, "    \"N7_kind1_after\": \"%s\",\n", hg_nudge_text(&p, HG_N_EVENING, b, sizeof b));
      p.t7.kind = 3; p.t7.hw = 2; fprintf(f, "    \"N7_kind3_only\": \"%s\",\n", hg_nudge_text(&p, HG_N_EVENING, b, sizeof b));
      fprintf(f, "    \"N1_kind1\": \"%s\",\n", hg_nudge_text(&p, HG_N_BRIEF, b, sizeof b));
      fprintf(f, "    \"N8\": \"%s\",\n", hg_nudge_text(&p, HG_N_LEAVE_HOT, b, sizeof b));
      fprintf(f, "    \"place_words\": [");
      for (uint8_t pl = 0; pl < HG_PL_N; pl++) fprintf(f, "\"%s\"%s", hg_place_word(pl), pl < 7 ? ", " : "");
      fprintf(f, "]\n  }\n}\n"); }
    fclose(f);
    printf("wrote %s\n", vec_path);
  }
  printf("TEST_HERDAY: %s (%d pass, %d fail)\n", hfails ? "FAIL" : "PASS", hpass, hfails);
  return hfails;
}
