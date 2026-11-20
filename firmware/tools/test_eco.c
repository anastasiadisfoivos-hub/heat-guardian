/* Host test of fw/09_guardian/hg_fw_eco.c (0.9.7 ecosystem layer) with the FROZEN hg_frames through fz_hg_frames.c.
 *   gcc -std=c99 -O2 -Wall -Wextra -Werror -Wno-unknown-pragmas -I fw/09_guardian fw/tools/test_eco.c \
 *       fw/09_guardian/hg_fw_eco.c fw/09_guardian/fz_*.c -lm -o test_eco && ./test_eco [eco_vectors.json]
 * 1. EVENTS ring: 64 kept, seq 1.. with wrap (never 0), first-after (SYNC), frame pack/unpack + CRC = frozen hg_crc8.
 * 2. CMD 0x16-0x19: parse ok / short / CRC / field errors; the frozen parser rejects them (ERR_OP), so the firmware layer
 *    must parse them first; opcodes 0x10-0x14, 0x1F are left to the frozen parser (return 0).
 * 3. planner: daily cap 6, >= 60 min spacing, none in the sleep window / nap, warnings win (no nudge, active one MISSED),
 *    DONE / MISSED after 10 min, WATER timer reset by DONE, max 4 WATER, N1 by press after the wake time, seed + learned
 *    routine precedence, no forecast -> WATER only, day roll.
 * 4. texts: reason-line priority, next-hours line, Greek date, 30-min trend.
 * With an argument: writes the JSON test vectors for the iOS app (fw/09_guardian/eco_vectors.json). */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "hg_fw_eco.h"
#include "frozen/hg_frames.h"
#include "frozen/hg_guardian.h"

static int fails = 0;
#define CHECK(c, ...) do { if (c) { printf("PASS  "); } else { printf("FAIL  "); fails++; } printf(__VA_ARGS__); printf("\n"); } while (0)

static uint8_t FC[72];
static void fc_heat_day(void)   /* the same constructed heat day as the console `fcdemo` */
{
  static const int8_t T[24] = { 27, 27, 26, 26, 26, 26, 26, 27, 27, 27, 28, 29, 31, 32, 33, 33, 32, 31, 30, 29, 28, 28, 27, 27 };
  for (int h = 0; h < 24; h++) { FC[3 * h] = (uint8_t)T[h]; FC[3 * h + 1] = 45; FC[3 * h + 2] = (uint8_t)(1 | 2 | ((h >= 6 && h < 10) ? 4 : 0)); }
}
static void fc_cool_day(void) { for (int h = 0; h < 24; h++) { FC[3 * h] = 24; FC[3 * h + 1] = 50; FC[3 * h + 2] = 4; } }

static hg_plan_in_t base_in(uint16_t mod, int32_t day)
{
  hg_plan_in_t in; memset(&in, 0, sizeof in);
  in.mod = mod; in.day = day; in.room_c = 25.0f; in.l_sleep_on = 0xFFFF; in.l_sleep_off = 0xFFFF;
  return in;
}

typedef struct { uint8_t id; uint16_t mod; } shown_t;
/* run a whole day minute by minute; done_after >= 0: press DONE that many minutes after each show */
static int run_day(hg_plan_t *p, hg_plan_in_t tmpl, int32_t day, int done_after, shown_t *sh, int *missed, uint8_t *warn_from_to)
{
  int n = 0; int pending = -1; *missed = 0;
  for (uint16_t mod = 0; mod < 1440; mod++) {
    hg_plan_in_t in = tmpl; in.mod = mod; in.day = day;
    in.warning = warn_from_to && mod >= warn_from_to[0] * 60u && mod < warn_from_to[1] * 60u;
    hg_plan_out_t o; hg_plan_minute(p, &in, &o);
    if (o.missed) (*missed)++;
    if (o.show) { sh[n].id = o.show; sh[n].mod = mod; n++; pending = done_after >= 0 ? mod + done_after : -1; }
    if (pending >= 0 && mod == pending) { hg_plan_done(p, mod); pending = -1; }
  }
  return n;
}

static void hexs(const uint8_t *b, int n, char *o) { for (int i = 0; i < n; i++) sprintf(o + 2 * i, "%02x", b[i]); }

int herday_tests(const char *vec_path);   /* test_herday.c */

int main(int argc, char **argv)
{
  /* ---------------------------------------------------------------- 1. events */
  { static hg_evring_t r; hg_ev_init(&r);
    for (int i = 0; i < 70; i++) hg_ev_add(&r, 1000u + (uint32_t)i, (uint8_t)(1 + i % 8), (uint8_t)i);
    CHECK(r.n == 64 && hg_ev_at(&r, 0)->seq == 7 && hg_ev_at(&r, 63)->seq == 70, "ring keeps the last 64 events (seq 7..70)");
    CHECK(hg_ev_first_after(&r, 65, 0) == 59 && hg_ev_at(&r, 59)->seq == 66, "SYNC since 65 -> first sent is seq 66");
    CHECK(hg_ev_first_after(&r, 0, 0) == 0 && hg_ev_first_after(&r, 70, 0) == -1 && hg_ev_first_after(&r, 70, 1) == 0, "since 0 / other boot -> all; since newest -> none");
    CHECK(hg_ev_first_after(&r, 3, 0) == 0, "since older than the ring -> from the oldest kept");
    static hg_evring_t w; hg_ev_init(&w); w.last_seq = 0xFFC0;   /* a long boot: 63 events up to the wrap, then 3 more */
    for (int i = 0; i < 66; i++) hg_ev_add(&w, 0, 1, 0);
    CHECK(hg_ev_at(&w, 60)->seq == 0xFFFF && hg_ev_at(&w, 61)->seq == 1 && hg_ev_at(&w, 63)->seq == 3, "seq wraps 0xFFFF -> 1 (0 never used)");
    CHECK(hg_ev_first_after(&w, 0xFFFF, 0) == 61, "SYNC across the wrap (since 0xFFFF -> seq 1)");
    hg_ev_t e = { 0x1234, HG_EV_NUDGE_DONE, 4, 1763380800u, {0} }, d; uint8_t f[20]; uint16_t boot = 0;
    hg_ev_pack(&e, 0x0102, f);
    CHECK(f[0] == 3 && f[1] == 0x34 && f[2] == 0x12 && f[3] == 0x02 && f[4] == 0x01 && f[9] == 2 && f[10] == 4 && f[19] == hg_crc8(f, 19), "EVENTS frame layout + frozen CRC-8");
    int z = 1; for (int i = 11; i < 19; i++) z &= f[i] == 0; CHECK(z, "EVENTS reserved bytes 11-18 = 0");
    CHECK(hg_ev_unpack(f, &d, &boot) == 0 && d.seq == e.seq && d.unix_s == e.unix_s && boot == 0x0102, "EVENTS unpack round trip");
    f[5] ^= 1; CHECK(hg_ev_unpack(f, &d, &boot) == -2, "EVENTS CRC catches a flipped bit"); }

  /* ---------------------------------------------------------------- 2. commands */
  { uint8_t f[20]; hg_eco_cmd_t c; hg_cmd_t fc; hg_forecast_buf_t fb; hg_forecast_init(&fb);
    hg_eco_pack_sync(42, 7, f);
    CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_SYNC_EVENTS && c.since_seq == 42 && c.boot == 7, "0x16 SYNC_EVENTS parse");
    CHECK(hg_cmd_parse(f, 20, &fc, &fb) == HG_CMD_ERR_OP, "frozen hg_cmd_parse rejects 0x16 (so the layer must parse it first)");
    CHECK(hg_eco_cmd_parse(f, 19, &c) == HG_CMD_ERR_SHORT, "19-byte frame -> short");
    f[1] ^= 1; CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_CRC, "bad CRC -> -2");
    hg_eco_pack_msg(2, f); CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_FAMILY_MSG && c.msg == 2, "0x17 FAMILY_MSG parse");
    hg_eco_pack_msg(4, f); CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_FIELD, "0x17 msg 4 -> field error");
    hg_eco_pack_msg(0, f); CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_FIELD, "0x17 msg 0 -> field error");
    CHECK(hg_eco_pack_name("\xce\x9c\xce\xb1\xcf\x81\xce\xaf\xce\xb1", f) == 0 && hg_eco_cmd_parse(f, 20, &c) == HG_CMD_FAMILY_NAME && strcmp(c.name, "\xce\x9c\xce\xb1\xcf\x81\xce\xaf\xce\xb1") == 0, "0x18 FAMILY_NAME «Μαρία» parse");
    CHECK(hg_eco_pack_name("\xce\x9c\xce\xb1\xcf\x81\xce\xaf\xce\xb1\xce\xbd\xce\xbd\xce\xb1\xce\xb1", f) < 0, "0x18 name of 16 bytes refused by the packer");
    memset(f, 0, 20); f[0] = 0x18; f[1] = 0xCE; f[19] = hg_crc8(f, 19); CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_FIELD, "0x18 truncated UTF-8 -> field error");
    memset(f, 0, 20); f[0] = 0x18; f[1] = 'A'; f[3] = 'B'; f[19] = hg_crc8(f, 19); CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_FIELD, "0x18 not NUL padded -> field error");
    memset(f, 0, 20); f[0] = 0x18; f[19] = hg_crc8(f, 19); CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_FAMILY_NAME && c.name[0] == 0, "0x18 empty name = back to the default");
    hg_seed_t s; hg_seed_clear(&s); s.wake_h = 7; s.wake_m = 10; s.bed_h = 22; s.bed_m = 30; s.flags = 1;
    hg_eco_pack_seed(&s, f);
    CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ROUTINE_SEED && c.seed.wake_m == 10 && c.seed.nap_fh == 0xFF && c.seed.flags == 1, "0x19 ROUTINE_SEED parse");
    s.o1_fh = 9; s.o1_fm = 60; s.o1_th = 10; s.o1_tm = 0; hg_eco_pack_seed(&s, f); CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_FIELD, "0x19 minute 60 -> field error");
    hg_seed_clear(&s); s.flags = 2; hg_eco_pack_seed(&s, f); CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_FIELD, "0x19 flags bit1 -> field error");
    hg_seed_clear(&s); s.wake_h = 7; hg_eco_pack_seed(&s, f); CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_FIELD, "0x19 half-set pair (h set, m 0xFF) -> field error");
    int ok = 1; const uint8_t ops[] = { 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x1D, 0x1F };
    for (unsigned i = 0; i < sizeof ops; i++) { memset(f, 0, 20); f[0] = ops[i]; ok &= hg_eco_cmd_parse(f, 20, &c) == 0; }
    CHECK(ok, "opcodes 0x10-0x15, 0x1D, 0x1F are left to the frozen parser");
    ok = 1; for (uint8_t a = 1; a <= 4; a++) { hg_eco_pack_action(a, a == 2 ? 4 : 0, f); ok &= hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ELDER_ACTION && c.action == a; }
    CHECK(ok && c.nudge_id == 0, "0x1A ELDER_ACTION parse, actions 1-4");
    hg_eco_pack_action(2, 4, f); hg_eco_cmd_parse(f, 20, &c); CHECK(c.nudge_id == 4, "0x1A NUDGE_DONE carries the nudge id");
    CHECK(hg_cmd_parse(f, 20, &fc, &fb) == HG_CMD_ERR_OP, "frozen hg_cmd_parse rejects 0x1A");
    hg_eco_pack_action(0, 0, f); CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_FIELD, "0x1A action 0 -> field error");
    hg_eco_pack_action(5, 0, f); CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_FIELD, "0x1A action 5 -> field error");
    hg_eco_pack_action(2, 0, f); CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_FIELD, "0x1A NUDGE_DONE id 0 -> field error");
    hg_eco_pack_action(2, 8, f); CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ELDER_ACTION && c.nudge_id == 8, "0.9.8: 0x1A NUDGE_DONE id 8 (LEAVE_HOT) accepted");
    hg_eco_pack_action(2, 9, f); CHECK(hg_eco_cmd_parse(f, 20, &c) == HG_CMD_ERR_FIELD, "0x1A NUDGE_DONE id 9 -> field error"); }

  /* ---------------------------------------------------------------- 3. planner */
  shown_t sh[64]; int missed, n;
  { hg_plan_t p; hg_plan_init(&p); hg_plan_in_t t = base_in(0, 100); t.room_c = 29.0f;   /* no forecast, hot room all day */
    n = run_day(&p, t, 100, -1, sh, &missed, NULL);
    int only4 = 1, quiet = 0; for (int i = 0; i < n; i++) { only4 &= sh[i].id == HG_N_WATER; quiet |= sh[i].mod < 480 || sh[i].mod >= 1320; }
    int sp = 1; for (int i = 1; i < n; i++) sp &= sh[i].mod - sh[i - 1].mod >= 90;
    CHECK(n == 4 && only4, "no forecast, room 29 C: WATER only, max 4 a day (got %d)", n);
    CHECK(sp && !quiet && sh[0].mod == 480, "WATER every >= 90 min, none in the default sleep window 22:00-08:00 (first %02u:%02u)", sh[0].mod / 60, sh[0].mod % 60);
    CHECK(missed == 4, "each unanswered nudge is MISSED after 10 min (%d)", missed); }

  { fc_heat_day(); hg_plan_t p; hg_plan_init(&p); hg_plan_in_t t = base_in(0, 200); t.fc72 = FC; t.room_c = 27.0f;
    n = run_day(&p, t, 200, -1, sh, &missed, NULL);
    int sp = 1, quiet = 0, n1 = -1, n2 = -1, n3 = -1, n5 = -1, n4 = 0;   /* n3 must stay -1: SHUTTERS removed in 0.9.8 */
    for (int i = 0; i < n; i++) { if (i) sp &= sh[i].mod - sh[i - 1].mod >= 60; quiet |= sh[i].mod < 480 || sh[i].mod >= 1320;
      switch (sh[i].id) { case 1: n1 = sh[i].mod; break; case 2: n2 = sh[i].mod; break; case 3: n3 = sh[i].mod; break; case 5: n5 = sh[i].mod; break; case 4: n4++; break; default: break; } }
    printf("      heat day:"); for (int i = 0; i < n; i++) printf(" N%u@%02u:%02u", sh[i].id, sh[i].mod / 60, sh[i].mod % 60); printf("\n");
    CHECK(n <= 6 && sp && !quiet, "heat day: <= 6 nudges, >= 60 min apart, none in the sleep window (%d)", n);
    CHECK(n1 == 510, "N1 BRIEF at 08:30 without a press (default wake 07:00 + 90 min)");
    CHECK(n2 == 9 * 60 + 30, "N2 LAST_COOL 30 min before the 06-10 safe window ends (09:30)");
    CHECK(n3 == -1, "0.9.8: N3 SHUTTERS is never shown (removed)");
    CHECK(n5 == 21 * 60 + 30, "N5 AIR at 21:30 on a night-heat day (the 6th slot is kept for it)");
    CHECK(n4 >= 1, "N4 WATER during the forecast hot hours");
    char b[96]; CHECK(strcmp(hg_nudge_text(&p, HG_N_BRIEF, b, sizeof b), "\xce\xa3\xce\xae\xce\xbc\xce\xb5\xcf\x81\xce\xb1 \xce\xb6\xce\xad\xcf\x83\xcf\x84\xce\xb7. \xce\x92\xce\xb3\xce\xb5\xce\xaf\xcf\x84\xce\xb5 \xcf\x80\xcf\x81\xce\xb9\xce\xbd \xcf\x84\xce\xb9\xcf\x82 10:00") == 0, "N1 text «... Βγείτε πριν τις 10:00» (end of the 06-10 safe window)"); }

  { fc_heat_day(); hg_plan_t p; hg_plan_init(&p); hg_plan_in_t t = base_in(0, 300); t.fc72 = FC;
    uint8_t w[2] = { 8, 14 };
    n = run_day(&p, t, 300, -1, sh, &missed, w);
    int bad = 0; for (int i = 0; i < n; i++) bad |= sh[i].mod >= 480 && sh[i].mod < 840;
    CHECK(!bad, "no nudge while a guardian warning is on (08:00-14:00)");
    hg_plan_init(&p); hg_plan_in_t in = base_in(9 * 60 + 30, 301); in.fc72 = FC; hg_plan_out_t o;
    hg_plan_minute(&p, &in, &o); uint8_t id = o.show;
    in.mod++; in.warning = 1; hg_plan_minute(&p, &in, &o);
    CHECK(id && o.missed == id && !p.active, "an active nudge is replaced by a warning at once (MISSED)");
    CHECK(hg_plan_done(&p, in.mod) == 0, "DONE after the replacement does nothing"); }

  { hg_plan_t p; hg_plan_init(&p); hg_plan_in_t t = base_in(0, 400); t.room_c = 29.0f;
    n = run_day(&p, t, 400, 3, sh, &missed, NULL);
    CHECK(missed == 0 && p.done == 4, "pressed nudges are DONE, not MISSED");
    hg_plan_init(&p); hg_plan_in_t in = base_in(10 * 60, 401); in.room_c = 29.0f; hg_plan_out_t o;
    hg_plan_minute(&p, &in, &o); CHECK(o.show == HG_N_WATER, "WATER shown at 10:00");
    CHECK(hg_plan_done(&p, 10 * 60 + 9) == HG_N_WATER, "DONE at 10:09 -> WATER");
    uint16_t first = 0; for (uint16_t m = 10 * 60 + 1; m < 14 * 60 && !first; m++) { in.mod = m; hg_plan_minute(&p, &in, &o); if (o.show) first = m; }
    CHECK(first == 10 * 60 + 9 + 90, "a WATER DONE restarts the 90-min timer (next at 11:39, got %02u:%02u)", first / 60, first % 60);
    hg_plan_done(&p, in.mod); in.day = 402; in.mod = 9 * 60; hg_plan_minute(&p, &in, &o); CHECK(o.show == HG_N_WATER && p.count == 1, "a new day resets the counters"); }

  { fc_heat_day(); hg_plan_t p; hg_plan_init(&p); hg_plan_in_t in = base_in(6 * 60 + 50, 500); in.fc72 = FC; in.press = 1;
    CHECK(hg_plan_press(&p, &in) == 0, "a press at 06:50 is not the brief press (before 07:00)");
    in.mod = 7 * 60 + 5; CHECK(hg_plan_press(&p, &in) == HG_N_BRIEF, "first press after 07:00 on a heat day -> N1 BRIEF");
    hg_plan_done(&p, in.mod); in.mod = 9 * 60; CHECK(hg_plan_press(&p, &in) == 0, "N1 at most once a day");
    fc_cool_day(); hg_plan_init(&p); in.mod = 7 * 60 + 30; CHECK(hg_plan_press(&p, &in) == 0, "no brief on a day that is not a heat day");
    in.fc72 = NULL; CHECK(hg_plan_press(&p, &in) == 0, "no brief without a forecast"); }

  { fc_heat_day(); hg_seed_t s; hg_seed_clear(&s); s.wake_h = 6; s.wake_m = 0; s.bed_h = 21; s.bed_m = 0;
    s.nap_fh = 14; s.nap_fm = 0; s.nap_th = 16; s.nap_tm = 0; s.flags = 1;
    hg_plan_t p; hg_plan_init(&p); hg_plan_in_t t = base_in(0, 600); t.fc72 = FC; t.seed = &s; t.room_c = 25.0f;
    n = run_day(&p, t, 600, -1, sh, &missed, NULL);
    int bad = 0, ac = 0, n1 = -1; for (int i = 0; i < n; i++) { bad |= sh[i].mod < 360 || sh[i].mod >= 1260 || (sh[i].mod >= 840 && sh[i].mod < 960);
      ac |= sh[i].id == HG_N_AC; if (sh[i].id == 1) n1 = sh[i].mod; }
    printf("      seeded day:"); for (int i = 0; i < n; i++) printf(" N%u@%02u:%02u", sh[i].id, sh[i].mod / 60, sh[i].mod % 60); printf("\n");
    CHECK(!bad, "seed: no nudge before her wake 06:00, after her bed 21:00, or in her nap 14-16");
    CHECK(n1 == 7 * 60 + 30, "seed: brief at her wake time + 90 min (07:30)");
    CHECK(ac, "seed A/C at home: «Ανάψτε το κλιματιστικό» shown on the hot day");
    hg_plan_in_t q = base_in(6 * 60 + 30, 600); q.seed = &s; q.l_valid = 1; q.l_days = 3; q.l_sleep_on = 23 * 60; q.l_sleep_off = 7 * 60;
    CHECK(hg_plan_quiet(&q) == 1 && hg_plan_wake_ref(&q) == 7 * 60, "learned >= 3 days wins over the stated routine (06:30 asleep, wake ref 07:00)");
    q.l_days = 2; CHECK(hg_plan_quiet(&q) == 0 && hg_plan_wake_ref(&q) == 6 * 60, "learned < 3 days: the stated routine is used");
    s.o1_fh = 7; s.o1_fm = 0; s.o1_th = 9; s.o1_tm = 0;
    hg_plan_init(&p); t.room_c = 25.0f; s.flags = 0;
    n = run_day(&p, t, 601, -1, sh, &missed, NULL);
    int n2 = 0; for (int i = 0; i < n; i++) n2 |= sh[i].id == HG_N_LAST_COOL;
    CHECK(!n2, "seed: her usual outing 07-09 lies inside the safe window -> no LAST_COOL"); }

  { hg_plan_t p; hg_plan_init(&p); hg_plan_in_t in = base_in(0xFFFF, -1); in.room_c = 35.0f; hg_plan_out_t o;
    hg_plan_minute(&p, &in, &o); CHECK(!o.show, "clock unknown -> no nudge");
    in = base_in(12 * 60, 700); CHECK(hg_plan_force(&p, HG_N_SHUTTERS, &in) == 0 && !p.active, "0.9.8: console cannot force the removed N3");
    CHECK(hg_plan_force(&p, HG_N_AIR, &in) == HG_N_AIR && p.active == HG_N_AIR, "console force-show");
    for (int k = 0; k < 9; k++) { in.mod++; hg_plan_minute(&p, &in, &o); }
    CHECK(p.active && !o.missed, "still active 9 min after");
    in.mod++; hg_plan_minute(&p, &in, &o); CHECK(!p.active && o.missed == HG_N_AIR, "MISSED at 10 min"); }

  /* ---------------------------------------------------------------- 4. texts */
  { char b[96];
    CHECK(strcmp(hg_reason_text(HG2_WHY_ENV_LIMIT | HG2_WHY_TIME_IN_HEAT, HG_SCR_DRINK, 30.6f, b, sizeof b), "\xce\xa0\xce\xbf\xce\xbb\xce\xbb\xce\xae \xce\xb6\xce\xad\xcf\x83\xcf\x84\xce\xb7 \xcf\x83\xcf\x84\xce\xbf \xcf\x83\xcf\x80\xce\xaf\xcf\x84\xce\xb9 31\xc2\xb0") == 0, "reason ENV_LIMIT > TIME_IN_HEAT, room rounded «... 31°»");
    CHECK(strcmp(hg_reason_text(HG2_WHY_ENV_LIMIT | HG2_WHY_BODY, HG_SCR_COOL, 30.0f, b, sizeof b), "\xce\xa4\xce\xbf \xcf\x83\xcf\x8e\xce\xbc\xce\xb1 \xce\xb6\xce\xb5\xcf\x83\xcf\x84\xce\xb1\xce\xaf\xce\xbd\xce\xb5\xcf\x84\xce\xb1\xce\xb9") == 0, "reason BODY > ENV_LIMIT");
    CHECK(strcmp(hg_reason_text(HG2_WHY_DANGER_P, HG_SCR_DANGER, NAN, b, sizeof b), "\xce\xa4\xce\xbf \xcf\x83\xcf\x8e\xce\xbc\xce\xb1 \xce\xb6\xce\xb5\xcf\x83\xcf\x84\xce\xb1\xce\xaf\xce\xbd\xce\xb5\xcf\x84\xce\xb1\xce\xb9") == 0, "reason DANGER_P -> body line");
    CHECK(hg_reason_text(HG2_WHY_UNCERTAIN, HG_SCR_CHECK, 30.0f, b, sizeof b)[0] == 0, "UNCERTAIN only -> no line");
    CHECK(hg_reason_text(HG2_WHY_BODY, HG_SCR_OK, 30.0f, b, sizeof b)[0] == 0, "no reason line on the OK screen");
    CHECK(strcmp(hg_reason_text(HG_WHY_NO_RESPONSE_G, HG_SCR_CHECK, 30.0f, b, sizeof b), "\xce\x94\xce\xb5\xce\xbd \xce\xb1\xcf\x80\xce\xb1\xce\xbd\xcf\x84\xce\xae\xcf\x83\xce\xb1\xcf\x84\xce\xb5") == 0, "NO_RESPONSE_G -> «Δεν απαντήσατε»");
    fc_heat_day();
    CHECK(strcmp(hg_next_hours_text(FC, 9 * 60, b, sizeof b), "\xce\x91\xcf\x80\xcf\x8c 12:00 \xcf\x80\xce\xbf\xce\xbb\xce\xbb\xce\xae \xce\xb6\xce\xad\xcf\x83\xcf\x84\xce\xb7") == 0, "next hours «Από 12:00 πολλή ζέστη»");
    CHECK(hg_next_hours_text(FC, 20 * 60, b, sizeof b)[0] == 0, "evening, no hot hour left -> nothing");
    fc_cool_day(); CHECK(strcmp(hg_next_hours_text(FC, 9 * 60, b, sizeof b), HG_TXT_COOL_PM) == 0, "cool day -> «Δροσερό απόγευμα»");
    CHECK(hg_next_hours_text(NULL, 9 * 60, b, sizeof b)[0] == 0, "no forecast -> nothing");
    int32_t d17 = (int32_t)(1763337600 / 86400);   /* 2025-11-17 00:00 UTC */
    int y, m, dd, w; hg_local_date(d17, &y, &m, &dd, &w);
    CHECK(y == 2025 && m == 11 && dd == 17 && w == 1, "civil date 2025-11-17 is a Monday");
    int32_t d26 = 20774;   /* 2026-11-17 */
    hg_local_date(d26, &y, &m, &dd, &w);
    CHECK(y == 2026 && m == 11 && dd == 17 && w == 2 && strcmp(hg_date_text(d26, b, sizeof b), "\xce\xa4\xcf\x81\xce\xb9 17 \xce\x9d\xce\xbf\xce\xb5") == 0, "date line 2026-11-17 «Τρι 17 Νοε»");
    hg_local_date(11016, &y, &m, &dd, &w); CHECK(y == 2000 && m == 2 && dd == 29, "leap day 2000-02-29");
    hg_trend_t tr; hg_trend_init(&tr);
    for (int i = 0; i < 30; i++) { hg_trend_push(&tr, 26.0f + i * 0.02f); }
    CHECK(hg_trend_dir(&tr) == -2, "trend unknown before 30 min");
    hg_trend_push(&tr, 26.6f); CHECK(hg_trend_dir(&tr) == 1, "trend up (+0.6 C in 30 min)");
    hg_trend_init(&tr); for (int i = 0; i < 31; i++) { hg_trend_push(&tr, 27.0f - i * 0.01f); }
    CHECK(hg_trend_dir(&tr) == 0, "trend flat (-0.3 C)");
    hg_trend_init(&tr); for (int i = 0; i < 31; i++) { hg_trend_push(&tr, 28.0f - i * 0.02f); }
    CHECK(hg_trend_dir(&tr) == -1, "trend down (-0.6 C)");
    CHECK(strcmp(hg_family_text(1, "", b, sizeof b), "\xce\xbf\xce\xb9\xce\xba\xce\xbf\xce\xb3\xce\xad\xce\xbd\xce\xb5\xce\xb9\xce\xb1: \xcf\x83\xce\xb1\xcf\x82 \xce\xba\xce\xb1\xce\xbb\xce\xb5\xce\xaf") == 0, "family msg 1, default name «οικογένεια: σας καλεί»"); }

  /* ---------------------------------------------------------------- vectors for the app */
  if (argc > 1) {
    FILE *f = fopen(argv[1], "w"); if (!f) { printf("FAIL  cannot write %s\n", argv[1]); return 1; }
    char h[48]; uint8_t fr[20];
    fprintf(f, "{\n  \"about\": \"Heat Guardian band 0.9.7 ecosystem frames (ECOSYSTEM_SPEC.md 5/5b). Generated by fw/tools/test_eco.c from the firmware encoders. All frames 20 bytes, little-endian, byte 19 = CRC-8 poly 0x07 init 0x00 over bytes 0..18 (same as STATUS).\",\n");
    fprintf(f, "  \"crc8_check\": {\"input_ascii\": \"123456789\", \"crc8\": \"%02x\"},\n", hg_crc8((const uint8_t *)"123456789", 9));
    fprintf(f, "  \"events\": [\n");
    static const char *AN[] = { "", "nudge id", "nudge id", "nudge id", "1 band, 2 phone", "1 band, 2 phone", "1 band, 2 phone", "family msg 1..3", "guardian state (HG_ST_*)" };
    const uint8_t args[9] = { 0, HG_N_BRIEF, HG_N_WATER, HG_N_SHUTTERS, 1, 2, 1, 2, HG_ST_CHECK };
    for (uint8_t t = 1; t <= 8; t++) {
      hg_ev_t e = { (uint16_t)(t + 10), t, args[t], 1795420800u + t * 600u, {0} }; hg_ev_pack(&e, 37, fr); hexs(fr, 20, h);
      fprintf(f, "    {\"hex\": \"%s\", \"version\": 3, \"seq\": %u, \"boot_count\": 37, \"unix\": %lu, \"type\": %u, \"type_name\": \"%s\", \"arg\": %u, \"arg_meaning\": \"%s\"}%s\n",
              h, e.seq, (unsigned long)e.unix_s, t, hg_ev_name(t), e.arg, AN[t], t < 8 ? "," : "");
    }
    { hg_ev_t e = { 1, HG_EV_HELP, 1, 0, {0} }; hg_ev_pack(&e, 38, fr); hexs(fr, 20, h);
      fprintf(f, "  ],\n  \"event_clock_not_set\": {\"hex\": \"%s\", \"seq\": 1, \"boot_count\": 38, \"unix\": 0, \"type\": 5, \"type_name\": \"HELP\", \"arg\": 1},\n", h); }
    fprintf(f, "  \"commands\": [\n");
    hg_eco_pack_sync(0, 37, fr); hexs(fr, 20, h);
    fprintf(f, "    {\"hex\": \"%s\", \"op\": \"0x16\", \"name\": \"SYNC_EVENTS\", \"since_seq\": 0, \"boot_count\": 37, \"note\": \"since 0 = everything in the ring\"},\n", h);
    hg_eco_pack_sync(14, 37, fr); hexs(fr, 20, h);
    fprintf(f, "    {\"hex\": \"%s\", \"op\": \"0x16\", \"name\": \"SYNC_EVENTS\", \"since_seq\": 14, \"boot_count\": 37, \"note\": \"band re-notifies seq 15.. of boot 37 (all of the ring if its boot differs)\"},\n", h);
    for (uint8_t m = 1; m <= 3; m++) { hg_eco_pack_msg(m, fr); hexs(fr, 20, h); char t[64]; hg_family_text(m, "\xce\x9c\xce\xb1\xcf\x81\xce\xaf\xce\xb1", t, sizeof t);
      fprintf(f, "    {\"hex\": \"%s\", \"op\": \"0x17\", \"name\": \"FAMILY_MSG\", \"msg\": %u, \"band_text_with_name_Maria\": \"%s\"},\n", h, m, t); }
    hg_eco_pack_name("\xce\x9c\xce\xb1\xcf\x81\xce\xaf\xce\xb1", fr); hexs(fr, 20, h);
    fprintf(f, "    {\"hex\": \"%s\", \"op\": \"0x18\", \"name\": \"FAMILY_NAME\", \"utf8\": \"\xce\x9c\xce\xb1\xcf\x81\xce\xaf\xce\xb1\", \"bytes\": 10},\n", h);
    memset(fr, 0, 20); fr[0] = 0x18; fr[19] = hg_crc8(fr, 19); hexs(fr, 20, h);
    fprintf(f, "    {\"hex\": \"%s\", \"op\": \"0x18\", \"name\": \"FAMILY_NAME\", \"utf8\": \"\", \"note\": \"empty = back to the default %s\"},\n", h, HG_TXT_FAMDEF);
    hg_seed_t s; hg_seed_clear(&s);
    s.wake_h = 7; s.wake_m = 10; s.bed_h = 22; s.bed_m = 30; s.nap_fh = 14; s.nap_fm = 30; s.nap_th = 16; s.nap_tm = 0;
    s.o1_fh = 8; s.o1_fm = 0; s.o1_th = 9; s.o1_tm = 30; s.flags = 1;
    hg_eco_pack_seed(&s, fr); hexs(fr, 20, h);
    fprintf(f, "    {\"hex\": \"%s\", \"op\": \"0x19\", \"name\": \"ROUTINE_SEED\", \"wake\": \"07:10\", \"bed\": \"22:30\", \"nap\": \"14:30-16:00\", \"out1\": \"08:00-09:30\", \"out2\": null, \"ac_at_home\": true},\n", h);
    hg_seed_clear(&s); s.wake_h = 6; s.wake_m = 45; s.bed_h = 23; s.bed_m = 0;
    hg_eco_pack_seed(&s, fr); hexs(fr, 20, h);
    fprintf(f, "    {\"hex\": \"%s\", \"op\": \"0x19\", \"name\": \"ROUTINE_SEED\", \"wake\": \"06:45\", \"bed\": \"23:00\", \"nap\": null, \"out1\": null, \"out2\": null, \"ac_at_home\": null},\n", h);
    static const char *ACT[5] = { "", "HELP (= 2-s long press; does not cancel an active HELP) -> EVENTS HELP arg 2", "NUDGE_DONE (= press on that nudge screen; ignored if that nudge is not open) -> EVENTS NUDGE_DONE arg id",
                                  "HELP_CANCEL (= second long press) -> EVENTS HELP_CANCEL arg 2", "IM_OK (= press answering an open CHECK; ignored otherwise) -> EVENTS IM_OK arg 2" };
    for (uint8_t a = 1; a <= 4; a++) { hg_eco_pack_action(a, a == 2 ? HG_N_WATER : 0, fr); hexs(fr, 20, h);
      fprintf(f, "    {\"hex\": \"%s\", \"op\": \"0x1A\", \"name\": \"ELDER_ACTION\", \"action\": %u, \"nudge_id\": %u, \"meaning\": \"%s\"}%s\n", h, a, a == 2 ? HG_N_WATER : 0, ACT[a], a < 4 ? "," : ""); }
    fprintf(f, "  ],\n  \"replies\": \"on the console / BLE UART: '# CMD ok op=0x16' or '# CMD error <rc> op=..' with rc -1 short, -2 CRC, -4 field\"\n}\n");
    fclose(f);
    printf("wrote %s\n", argv[1]);
  }
  fails += herday_tests(argc > 2 ? argv[2] : NULL);
  printf(fails ? "TEST_ECO: FAIL (%d)\n" : "TEST_ECO: PASS\n", fails);
  return fails ? 1 : 0;
}
