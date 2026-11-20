/* Heat Guardian 09_guardian 0.9.15 STABLE: host tests for hg_fw_stable.c (session FW-915-STABLE).
 *   A. reset classification (erratum 136, user resets are not boot-loop evidence, quick_boots)
 *   B. FS-guard marker persistence ORDERING: a model of the sketch's boot steps (0.9.14 order vs 0.9.15 order) with a reset of
 *      every kind injected at every step; the marker (= the ladder rung) must never be lost by 0.9.15
 *   C. the guard-reset chain survives a watchdog reset (the rung climbs instead of restarting at 1)
 *   D. bounded wait: ok / timeout / error / pre-emption past the deadline / millis() wrap / idle callback
 *   E. verified flash wake: bounded tries, -1 when the chip never answers
 *   F. VBAT filter: one sagged sample during a buzz cannot latch low-battery mode
 * The boot-order model in B mirrors setup() in 09_guardian.ino by hand: it is a model, not the sketch itself. */
#include "hg_fw_stable.h"
#include "hg_fw_heal.h"
#include <stdio.h>
#include <string.h>
#include <math.h>

static int npass = 0, nfail = 0;
#define CHECK(c, ...) do { if (c) { npass++; printf("PASS  "); } else { nfail++; printf("FAIL  "); } printf(__VA_ARGS__); printf("\n"); } while (0)

/* ---------------- A ---------------- */
static void part_a(void)
{
  printf("== A. reset classification ==\n");
  CHECK(hg_reset_classify(0, 0, 0) == HG_RST_POWERON, "no bits = power-on / brown-out");
  CHECK(hg_reset_classify(HG_RR_RESETPIN, 0, 0) == HG_RST_PIN, "RESETPIN = pin reset");
  CHECK(hg_reset_classify(HG_RR_RESETPIN | HG_RR_DOG, 0, 0) == HG_RST_PIN, "erratum 136: RESETPIN + a stray DOG bit = pin reset (0.9.14 said WATCHDOG)");
  CHECK(hg_reset_classify(HG_RR_RESETPIN | HG_RR_SREQ | HG_RR_LOCKUP, 0, 0) == HG_RST_PIN, "erratum 136: RESETPIN + stray SREQ/LOCKUP = pin reset");
  CHECK(hg_reset_classify(HG_RR_DOG, 0, 0) == HG_RST_WATCHDOG, "DOG alone = watchdog");
  CHECK(hg_reset_classify(HG_RR_SREQ, 1, 0) == HG_RST_FSGUARD, "soft reset + marker = FS-GUARD");
  CHECK(hg_reset_classify(HG_RR_SREQ, 0, 1) == HG_RST_UPLOAD, "soft reset into a new build = upload");
  CHECK(hg_reset_classify(HG_RR_SREQ, 1, 1) == HG_RST_UPLOAD, "a new build wins over a stale marker (upload)");
  CHECK(hg_reset_classify(HG_RR_SREQ, 0, 0) == HG_RST_CRASH, "soft reset, same build, no marker = CRASH (0.9.14 printed SOFTWARE(upload))");
  CHECK(hg_reset_classify(HG_RR_LOCKUP, 0, 0) == HG_RST_LOCKUP, "LOCKUP");
  CHECK(hg_reset_classify(HG_RR_OFF, 0, 0) == HG_RST_WAKE && hg_reset_classify(HG_RR_VBUS, 0, 0) == HG_RST_WAKE &&
        hg_reset_classify(HG_RR_DIF, 0, 0) == HG_RST_WAKE, "OFF / VBUS / DIF = wake");
  CHECK(hg_reset_classify(HG_RR_RESETPIN, 1, 0) == HG_RST_PIN, "pin reset with a marker still pending in RAM: classed PIN (the heal ladder still counts the marker)");
  int faults = 0, user = 0;
  for (int c = 0; c < HG_RST_COUNT; c++) { if (hg_reset_is_fault(c)) faults++; else user++; }
  CHECK(faults == 4 && hg_reset_is_fault(HG_RST_WATCHDOG) && hg_reset_is_fault(HG_RST_FSGUARD) && hg_reset_is_fault(HG_RST_CRASH) &&
        hg_reset_is_fault(HG_RST_LOCKUP) && !hg_reset_is_fault(HG_RST_PIN) && !hg_reset_is_fault(HG_RST_POWERON) &&
        !hg_reset_is_fault(HG_RST_WAKE) && !hg_reset_is_fault(HG_RST_UPLOAD), "faults = watchdog, fs-guard, crash, lock-up; never pin / power / wake / upload");
  /* every RESETREAS combination of the 9 bits: classify never returns out of range; with RESETPIN set it is always PIN */
  int bad = 0; const uint32_t bits[9] = { HG_RR_RESETPIN, HG_RR_DOG, HG_RR_SREQ, HG_RR_LOCKUP, HG_RR_OFF, HG_RR_LPCOMP, HG_RR_DIF, HG_RR_NFC, HG_RR_VBUS };
  for (unsigned m = 0; m < 512; m++) for (int mk = 0; mk < 2; mk++) for (int nb = 0; nb < 2; nb++) {
    uint32_t rr = 0; for (int i = 0; i < 9; i++) if (m & (1u << i)) rr |= bits[i];
    int c = hg_reset_classify(rr, mk, nb);
    if (c < 0 || c >= HG_RST_COUNT) bad++;
    if ((rr & HG_RR_RESETPIN) && c != HG_RST_PIN) bad++;
  }
  CHECK(bad == 0, "all 2048 RESETREAS x marker x build combinations classify in range, RESETPIN always first");
  /* ten pin resets in a row never set the boot-loop hold (quick_boots >= 3) */
  uint32_t q = 0; for (int i = 0; i < 10; i++) q = hg_quick_boots_next(q, hg_reset_classify(HG_RR_RESETPIN | (i & 1 ? HG_RR_DOG : 0), 0, 0), 0);
  CHECK(q == 0, "ten pin resets in a row (some with a stray DOG bit): quick_boots stays 0 (plan 0.9.15 'done when')");
  q = 0; for (int i = 0; i < 10; i++) q = hg_quick_boots_next(q, HG_RST_POWERON, 0);
  CHECK(q == 0, "ten power cycles: quick_boots stays 0");
  q = 2; q = hg_quick_boots_next(q, HG_RST_PIN, 0);
  CHECK(q == 2, "a pin reset neither adds to nor clears the evidence of a real loop (2 stays 2)");
  q = 0; for (int i = 0; i < 3; i++) q = hg_quick_boots_next(q, HG_RST_WATCHDOG, 0);
  CHECK(q == 3, "three watchdog resets in a row = 3 (the boot-loop hold still works)");
  q = 0; q = hg_quick_boots_next(q, HG_RST_CRASH, 0); q = hg_quick_boots_next(q, HG_RST_FSGUARD, 0); q = hg_quick_boots_next(q, HG_RST_LOCKUP, 0);
  CHECK(q == 3, "crash + fs-guard + lock-up count");
  CHECK(hg_quick_boots_next(7, HG_RST_UPLOAD, 1) == 0 && hg_quick_boots_next(7, HG_RST_PIN, 1) == 0, "a new build starts at 0 (double-tap + upload too)");
  CHECK(strcmp(hg_reset_name(HG_RST_PIN), "RESET-PIN") == 0 && strcmp(hg_reset_name(99), "?") == 0, "names");
}

/* ---------------- B: boot-order model ---------------- */
enum { R_SOFT, R_WDT, R_PIN, R_POWER, R_N };
static const char *RN[R_N] = { "soft", "watchdog", "pin", "power" };
typedef struct {
  uint8_t gpregret2;          /* survives soft reset only */
  int ni_valid; hg_mk_ni_t mk; /* .hg_noinit: survives soft, watchdog, pin; lost on power */
  int counted;                /* faults counted into the heal state on flash (survives everything) */
} dev_t;
static void dev_reset(dev_t *d, int r)
{
  if (r != R_SOFT) d->gpregret2 = 0;                    /* Nordic reset table: GPREGRET kept only by a soft reset */
  if (r == R_POWER) { d->ni_valid = 0; memset(&d->mk, 0x5A, sizeof d->mk); }   /* RAM garbage */
}
/* the FS guard dies: the marker into GPREGRET2 (and, from 0.9.15, the RAM copy), soft reset */
static void dev_guard_die(dev_t *d, int with_ni, uint8_t count)
{
  uint8_t v = hg_heal_marker_encode(HG_CAUSE_DEADLINE, HG_FID_EVENTS, count, 0);
  d->gpregret2 = v;
  if (with_ni) { d->mk.reg = v; d->mk.pend = 1; d->mk.gc = count; d->mk.gfid = HG_FID_EVENTS; d->ni_valid = 1; }
  dev_reset(d, R_SOFT);
}
/* one boot. reset_at = the step at which a reset of kind r hits (-1 = none). Returns 1 if the boot ran to the end.
 * 0.9.14 order: read GPREGRET2 + clear it at once (step 0), Serial wait (1), ifs ladder / healLoad / hg_heal_begin (2), healSave (3).
 * 0.9.15 order: hg_mk_pick into .hg_noinit (0), Serial wait (1), ... (2), healSave (3), consume + clear GPREGRET2 (4). */
static int boot(dev_t *d, int v15, int reset_at, int r)
{
  uint8_t m;
  if (v15) { uint8_t src; m = hg_mk_pick(d->gpregret2, &d->mk, d->ni_valid, &src); d->ni_valid = 1; }
  else { m = d->gpregret2; d->gpregret2 = 0; }
  if (reset_at == 0) { dev_reset(d, r); return 0; }
  if (reset_at == 1) { dev_reset(d, r); return 0; }     /* the 3 s Serial wait / a slow step */
  if (reset_at == 2) { dev_reset(d, r); return 0; }     /* InternalFS ladder, heal load */
  if (hg_heal_marker_decode(m, 0, 0, 0, 0)) d->counted++;   /* healSave: counted on flash */
  if (reset_at == 3) { dev_reset(d, r); return 0; }     /* between the save and the consume (0.9.15 only: a 2-instruction window) */
  if (v15) { hg_mk_consumed(&d->mk); d->gpregret2 = 0; }
  if (reset_at == 4) { dev_reset(d, r); return 0; }
  return 1;
}
static void part_b(void)
{
  printf("== B. marker persistence ordering (model of setup()) ==\n");
  int lost14 = 0, lost15 = 0, double15 = 0, cases = 0;
  for (int r = 0; r < R_N; r++) for (int at = 0; at <= 4; at++) {
    for (int v15 = 0; v15 < 2; v15++) {
      dev_t d; memset(&d, 0, sizeof d); d.ni_valid = 1;
      dev_guard_die(&d, v15, 1);
      boot(&d, v15, at, r);                              /* the boot after the guard reset dies at step `at` */
      boot(&d, v15, -1, 0);                              /* the next boot runs through */
      boot(&d, v15, -1, 0);                              /* and one more: nothing counted twice afterwards */
      if (!v15) { if (d.counted == 0) lost14++; continue; }
      cases++;
      if (d.counted == 0 && r != R_POWER) { lost15++; printf("      0.9.15 LOST: %s reset at step %d\n", RN[r], at); }
      if (d.counted > 1) double15++;
      if (r == R_POWER && at <= 2) CHECK(d.counted == 0, "0.9.15: a power cut before the save loses the marker (RAM and GPREGRET2 both gone): known, not a fault reset (%s at %d)", RN[r], at);
    }
  }
  CHECK(lost15 == 0, "0.9.15: a soft / watchdog / pin reset at ANY step after the marker read never loses it (%d cases)", cases);
  CHECK(lost14 >= 6, "0.9.14 order demonstrably lost it: %d of 20 reset cases (watchdog/pin in the Serial wait = plan A-01)", lost14);
  { dev_t d; memset(&d, 0, sizeof d); d.ni_valid = 1; dev_guard_die(&d, 0, 1); boot(&d, 0, 1, R_WDT); boot(&d, 0, -1, 0);
    CHECK(d.counted == 0, "0.9.14: FS-guard reset -> watchdog in the Serial wait -> the rung is gone"); }
  { dev_t d; memset(&d, 0, sizeof d); d.ni_valid = 1; dev_guard_die(&d, 1, 1); boot(&d, 1, 1, R_WDT); boot(&d, 1, -1, 0);
    CHECK(d.counted == 1, "0.9.15: the same sequence: counted exactly once (from the .hg_noinit copy)"); }
  CHECK(double15 <= 3, "0.9.15: double counting only for a reset in the save->consume window (step 3), the safe direction (%d)", double15);
  { dev_t d; memset(&d, 0, sizeof d); d.ni_valid = 1; dev_guard_die(&d, 1, 1); boot(&d, 1, -1, 0);
    boot(&d, 1, -1, 0); boot(&d, 1, 2, R_WDT); boot(&d, 1, -1, 0);
    CHECK(d.counted == 1, "0.9.15: a consumed marker is never counted again by later boots or resets"); }
  /* pick details */
  { hg_mk_ni_t ni; memset(&ni, 0, sizeof ni); uint8_t src = 9;
    uint8_t g = hg_heal_marker_encode(HG_CAUSE_ASSERT, HG_FID_SFILE, 2, 0);
    CHECK(hg_mk_pick(g, &ni, 1, &src) == g && src == HG_MK_SRC_GPREGRET2 && ni.pend && ni.reg == g, "GPREGRET2 marker picked and copied into RAM, pending");
    CHECK(hg_mk_pick(0, &ni, 1, &src) == g && src == HG_MK_SRC_NOINIT, "GPREGRET2 cleared by a watchdog: the RAM copy is used");
    hg_mk_consumed(&ni);
    CHECK(hg_mk_pick(0, &ni, 1, &src) == 0 && src == HG_MK_SRC_NONE && !ni.pend, "consumed: nothing picked");
    memset(&ni, 0xA7, sizeof ni);
    CHECK(hg_mk_pick(0, &ni, 0, &src) == 0 && ni.pend == 0 && ni.gc == 0, "RAM not valid (power-on garbage): ignored and cleared");
    memset(&ni, 0, sizeof ni); ni.pend = 1; ni.reg = 0x05;   /* count bits 0 = not a marker */
    CHECK(hg_mk_pick(0, &ni, 1, &src) == 0 && !ni.pend, "an undecodable RAM marker is dropped"); }
}

/* ---------------- C: chain ---------------- */
static void part_c(void)
{
  printf("== C. the guard-reset chain across a watchdog reset ==\n");
  hg_mk_ni_t ni; memset(&ni, 0, sizeof ni);
  uint8_t c, f;
  uint8_t m1 = hg_heal_marker_encode(HG_CAUSE_DEADLINE, HG_FID_EVENTS, 1, 0);
  hg_mk_chain(m1, &ni, 1, &c, &f);
  CHECK(c == 1 && f == HG_FID_EVENTS, "marker count 1 -> chain 1");
  ni.gc = c; ni.gfid = f;                                /* the sketch keeps it in RAM */
  hg_mk_chain(0, &ni, 1, &c, &f);                        /* then a watchdog reset: no marker */
  CHECK(c == 1 && f == HG_FID_EVENTS, "watchdog reset (no marker): the chain is restored from RAM (0.9.14: back to 0)");
  CHECK(hg_heal_next_count(c, f, HG_FID_EVENTS) == 2, "so the next guard reset is rung 2 (re-format), not rung 1 again");
  hg_mk_chain(0, &ni, 0, &c, &f);
  CHECK(c == 0, "power-on (RAM lost): chain 0");
  ni.gc = 9; hg_mk_chain(0, &ni, 1, &c, &f);
  CHECK(c == 3, "a corrupt chain count is clamped to 3");
}

/* ---------------- D: bounded wait ---------------- */
static uint32_t clk; static uint32_t clk_step = 1;
static uint32_t now_ms(void) { uint32_t t = clk; clk += clk_step; return t; }
static int polls, done_at, err_at;
static int poll_fn(void *ctx) { (void)ctx; polls++; if (err_at && polls >= err_at) return -3; return (done_at && polls >= done_at) ? 1 : 0; }
static int idles; static void idle_fn(void *c) { (void)c; idles++; }
static int jump_poll(void *ctx) { (void)ctx; polls++; if (polls == 1) { clk += 5000; return 0; } return 1; }   /* pre-empted for 5 s, then done */
static void part_d(void)
{
  printf("== D. bounded wait ==\n");
  uint32_t el;
  clk = 0; clk_step = 1; polls = 0; done_at = 1; err_at = 0;
  CHECK(hg_wait_bounded(poll_fn, NULL, now_ms, NULL, NULL, 10, &el) == HG_WAIT_OK && polls == 1, "already done: OK at the first poll");
  clk = 0; polls = 0; done_at = 5; idles = 0;
  CHECK(hg_wait_bounded(poll_fn, NULL, now_ms, idle_fn, NULL, 100, &el) == HG_WAIT_OK && idles == 4, "done after 5 polls, idle called between polls");
  clk = 0; polls = 0; done_at = 0;
  int r = hg_wait_bounded(poll_fn, NULL, now_ms, NULL, NULL, 50, &el);
  CHECK(r == HG_WAIT_TIMEOUT && el >= 50 && el < 60, "never ready: TIMEOUT after the deadline (elapsed %u ms)", (unsigned)el);
  clk = 0; polls = 0; done_at = 0; err_at = 3;
  CHECK(hg_wait_bounded(poll_fn, NULL, now_ms, NULL, NULL, 1000, &el) == HG_WAIT_ERROR && polls == 3, "the poll reports an error: ERROR at once, no waiting out the deadline");
  err_at = 0;
  clk = 0; polls = 0;
  CHECK(hg_wait_bounded(jump_poll, NULL, now_ms, NULL, NULL, 100, &el) == HG_WAIT_OK, "pre-empted past the deadline but the device finished: OK, not a false timeout");
  clk = 0xFFFFFFF0u; polls = 0; done_at = 0;
  r = hg_wait_bounded(poll_fn, NULL, now_ms, NULL, NULL, 40, &el);
  CHECK(r == HG_WAIT_TIMEOUT && el >= 40 && el < 50, "across the millis() wrap: still exactly bounded (%u ms)", (unsigned)el);
  clk = 0; polls = 0; done_at = 0;
  r = hg_wait_bounded(poll_fn, NULL, now_ms, NULL, NULL, 0, &el);
  CHECK(r == HG_WAIT_TIMEOUT && polls == 2, "timeout 0: one poll + the last look, then TIMEOUT");
}

/* ---------------- E: wake ---------------- */
static int wake_ok_at; static int tries_seen;
static uint32_t chip_try(int a, void *ctx) { (void)ctx; tries_seen++; return a >= wake_ok_at ? 0x856015u : (a == 0 ? 0xFFFFFFu : 0u); }
static void part_e(void)
{
  printf("== E. verified flash wake ==\n");
  wake_ok_at = 0; tries_seen = 0;
  CHECK(hg_flash_wake(0x856015u, chip_try, NULL, HG_FLASH_WAKE_TRIES) == 1 && tries_seen == 1, "awake chip: 1 try");
  wake_ok_at = 2; tries_seen = 0;
  CHECK(hg_flash_wake(0x856015u, chip_try, NULL, HG_FLASH_WAKE_TRIES) == 3 && tries_seen == 3, "chip that needs the software reset: 3rd try");
  wake_ok_at = 99; tries_seen = 0;
  CHECK(hg_flash_wake(0x856015u, chip_try, NULL, HG_FLASH_WAKE_TRIES) == -1 && tries_seen == 3, "dead / asleep chip: -1 after exactly 3 tries (bounded, error reported)");
  wake_ok_at = 0; tries_seen = 0;
  CHECK(hg_flash_wake(0x856016u, chip_try, NULL, 3) == -1, "wrong id (another part answering) is not accepted");
}

/* ---------------- F: VBAT ---------------- */
static void part_f(void)
{
  printf("== F. VBAT filter ==\n");
  hg_vbat_filt_t f; memset(&f, 0, sizeof f);
  const float T = 3.35f;
  CHECK(hg_vbat_step(&f, 3.20f, 1, 0, 0, T) == HG_VBAT_SKIP && f.skipped == 1 && f.low_n == 0, "a sample during a buzz is not taken (the 0.9.14 bug: one such sample latched low-battery mode)");
  CHECK(hg_vbat_step(&f, 3.30f, 0, 0, 0, T) == HG_VBAT_KEEP, "1st low reading (not during a buzz): no latch");
  CHECK(hg_vbat_step(&f, 3.80f, 0, 0, 0, T) == HG_VBAT_KEEP && f.low_n == 0 && f.low_rejected == 1, "a good reading resets the run (single low ignored, counted)");
  int r1 = hg_vbat_step(&f, 3.30f, 0, 0, 0, T), r2 = hg_vbat_step(&f, 3.31f, 0, 0, 0, T), r3 = hg_vbat_step(&f, 3.29f, 0, 0, 0, T);
  CHECK(r1 == HG_VBAT_KEEP && r2 == HG_VBAT_KEEP && r3 == HG_VBAT_ENTER_LOW, "three low readings in a row latch it");
  memset(&f, 0, sizeof f);
  hg_vbat_step(&f, 3.30f, 0, 0, 0, T); hg_vbat_step(&f, NAN, 0, 0, 0, T); hg_vbat_step(&f, 3.0f, 1, 0, 0, T);
  CHECK(hg_vbat_step(&f, 3.30f, 0, 0, 0, T) == HG_VBAT_KEEP && f.low_n == 2, "NaN and buzz-skipped samples neither count nor break the run");
  CHECK(hg_vbat_step(&f, 3.30f, 0, 0, 0, T) == HG_VBAT_ENTER_LOW, "... the 3rd real low reading latches");
  memset(&f, 0, sizeof f);
  for (int i = 0; i < 5; i++) r1 = hg_vbat_step(&f, 3.30f, 0, 1, 0, T);
  CHECK(r1 == HG_VBAT_KEEP && f.low_n == 0, "charging: never latches");
  for (int i = 0; i < 5; i++) r1 = hg_vbat_step(&f, 3.30f, 0, 0, 1, T);
  CHECK(r1 == HG_VBAT_KEEP, "already in low mode: no second ENTER");
  memset(&f, 0, sizeof f);
  for (int i = 0; i < 5; i++) r1 = hg_vbat_step(&f, 1.0f, 0, 0, 0, T);
  CHECK(r1 == HG_VBAT_KEEP && f.low_n == 0, "a reading <= 2.5 V (no battery / ADC fault) never latches (as 0.9.14)");
  /* a buzz every other sample with sagged values: never latches */
  memset(&f, 0, sizeof f); int ent = 0;
  for (int i = 0; i < 1000; i++) { int buzz = (i % 2) == 0; if (hg_vbat_step(&f, buzz ? 3.10f : 3.70f, buzz, 0, 0, T) == HG_VBAT_ENTER_LOW) ent++; }
  CHECK(ent == 0 && f.skipped == 500, "1,000 samples, sag only under the motor: never latches (500 skipped)");
}

int main(void)
{
  part_a(); part_b(); part_c(); part_d(); part_e(); part_f();
  printf("TEST_STABLE: %d passed, %d failed\n", npass, nfail);
  return nfail ? 1 : 0;
}
