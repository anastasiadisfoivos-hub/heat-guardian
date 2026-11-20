/* Heat Guardian 09_guardian 0.9.16 BOOT GUARD: host tests for hg_bootguard.c (session FW-BOOTGUARD, plan E.1 test_bootguard.c).
 *   A. reset classes (the 0.9.15 classes + supervisor / assert / stack / malloc / fault-inject), fault or not
 *   B. journal words: round trip, erased / zero words, every single-bit flip rejected, NOR torn writes, uptime code
 *   C. every ladder decision (fast faults, user resets, uploads, rest, slow faults), modes, plans (strict subsets)
 *   D. page scan + ledger (last 8, counts per class), merge of the two copies (journal + .hg_noinit)
 *   E. a simulated NOR page (bits only 1 -> 0, erase by page) driven through hg_bg_append exactly as the sketch drives it:
 *      fault loop -> every rung -> REST -> a press -> SAFE; pin resets never climb; journal writes failing (RAM copy carries);
 *      RAM lost (journal carries); a power cut inside every word; compaction (the ledger survives, an erase failure)
 *   F. 200,000 random boots: a fast fault loop always ends at REST within 6 resets, never later; slow faults never REST;
 *      a user reset after a normal boot always restarts at level 0
 *   G. supervisor: feed / named reset / guarded call making progress / millis() wrap / writer stuck -> storage off */
#include "hg_bootguard.h"
#include "hg_fw_stable.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static int npass = 0, nfail = 0;
#define CHECK(c, ...) do { if (c) { npass++; printf("PASS  "); } else { nfail++; printf("FAIL  "); } printf(__VA_ARGS__); printf("\n"); } while (0)
static unsigned rs = 12345u;
static unsigned rnd(void) { rs = rs * 1103515245u + 12345u; return rs >> 8; }

/* ---------------- A ---------------- */
static void part_a(void)
{
  printf("== A. reset classes ==\n");
  CHECK(hg_bg_classify(HG_RST_CRASH, HG_BG_RC_NONE) == HG_RST_CRASH, "soft reset, same build, no marker, no code = CRASH (hard fault / SoftDevice fault)");
  CHECK(hg_bg_classify(HG_RST_CRASH, HG_BG_RC_SUPERVISOR) == HG_BG_RST_SUPERVISOR && hg_bg_classify(HG_RST_CRASH, HG_BG_RC_ASSERT) == HG_BG_RST_ASSERT &&
        hg_bg_classify(HG_RST_CRASH, HG_BG_RC_STACK) == HG_BG_RST_STACK && hg_bg_classify(HG_RST_CRASH, HG_BG_RC_MALLOC) == HG_BG_RST_MALLOC &&
        hg_bg_classify(HG_RST_CRASH, HG_BG_RC_INJECT) == HG_BG_RST_INJECT, "a CRASH with a reset code is named by the code");
  int ok = 1;
  for (int c = 0; c < HG_RST_COUNT; c++) if (c != HG_RST_CRASH) for (uint8_t r = 0; r < 8; r++) if (hg_bg_classify(c, r) != c) ok = 0;
  CHECK(ok, "a code never renames a pin / power / watchdog / fs-guard / upload / lock-up / wake reset (a stale code is ignored)");
  CHECK(hg_bg_is_fault(HG_RST_WATCHDOG) && hg_bg_is_fault(HG_RST_FSGUARD) && hg_bg_is_fault(HG_RST_CRASH) && hg_bg_is_fault(HG_RST_LOCKUP) &&
        hg_bg_is_fault(HG_BG_RST_SUPERVISOR) && hg_bg_is_fault(HG_BG_RST_ASSERT) && hg_bg_is_fault(HG_BG_RST_STACK) &&
        hg_bg_is_fault(HG_BG_RST_MALLOC) && hg_bg_is_fault(HG_BG_RST_INJECT), "faults: watchdog, fs-guard, crash, lock-up, supervisor, assert, stack, malloc, inject");
  CHECK(!hg_bg_is_fault(HG_RST_PIN) && !hg_bg_is_fault(HG_RST_POWERON) && !hg_bg_is_fault(HG_RST_WAKE) && !hg_bg_is_fault(HG_RST_UPLOAD) &&
        !hg_bg_is_fault(HG_BG_RST_REBOOT), "never a fault (plan B.5 rule 7): pin, power-on, wake, upload, a commanded reboot");
  CHECK(HG_BG_RST_COUNT <= 16 && strcmp(hg_bg_class_name(HG_BG_RST_SUPERVISOR), "SUPERVISOR") == 0 && strcmp(hg_bg_class_name(99), "?") == 0,
        "%d classes fit the 4-bit field; names", HG_BG_RST_COUNT);
}

/* ---------------- B ---------------- */
static void part_b(void)
{
  printf("== B. journal words ==\n");
  int rt = 1, flips = 1, n = 0;
  for (int t = HG_BG_T_STARTED; t <= HG_BG_T_REST; t++)
    for (int k = 0; k < 4000; k++) {
      hg_bg_entry_t e, d; memset(&e, 0, sizeof e); e.type = (uint8_t)t;
      if (t == HG_BG_T_STARTED) { e.cls = (uint8_t)(rnd() % HG_BG_RST_COUNT); e.level = (uint8_t)(rnd() % 7); e.slow = (uint8_t)(rnd() % 16);
                                  e.cp = (uint8_t)(rnd() % 64); e.upc = (uint8_t)(rnd() % 128); }
      uint32_t w = hg_bg_encode(&e);
      if (hg_bg_decode(w, &d) != 1 || memcmp(&e, &d, sizeof e) != 0 || w == 0xFFFFFFFFu || w == 0) rt = 0;
      for (int b = 0; b < 32; b++) if (hg_bg_decode(w ^ (1u << b), NULL) == 1) flips = 0;
      n++;
    }
  CHECK(rt, "%d random entries of every type: encode -> decode identical, never 0xFFFFFFFF or 0", n);
  CHECK(flips, "every single-bit flip of every one of them is rejected (CRC-4 check nibble)");
  CHECK(hg_bg_decode(0xFFFFFFFFu, NULL) == 0 && hg_bg_decode(0, NULL) == -1, "erased word = 0 (empty), all-zero word = corrupt");
  /* NOR torn write: a power cut inside a program leaves some of the 0-bits still 1 */
  int torn = 0, tornValid = 0;
  for (int k = 0; k < 20000; k++) {
    hg_bg_entry_t e; memset(&e, 0, sizeof e); e.type = HG_BG_T_STARTED; e.cls = (uint8_t)(rnd() % HG_BG_RST_COUNT); e.level = (uint8_t)(rnd() % 7);
    uint32_t w = hg_bg_encode(&e), t2 = w | (rnd() & rnd() & ~w);   /* a random subset of the 0-bits not programmed yet */
    if (t2 == w || t2 == 0xFFFFFFFFu) continue;
    torn++; if (hg_bg_decode(t2, NULL) == 1) tornValid++;
  }
  CHECK(tornValid * 10 < torn, "torn writes that still decode as some valid entry: %d of %d (< 10 %%; one torn word per power cut at most)", tornValid, torn);
  int up = 1;
  uint32_t prev = 0;
  for (uint32_t ms = 0; ms < 600000000u; ms += 997u + ms / 50u) {
    uint8_t c = hg_bg_up_encode(ms); uint32_t s = hg_bg_up_decode_s(c);
    if (c >= 127 || s > ms / 1000u || s < prev) up = 0;
    prev = s;
  }
  CHECK(up, "uptime code: never 'unknown', a lower bound, monotonic (0 .. 166 h)");
  CHECK(hg_bg_up_encode(12500) == 12 && hg_bg_up_decode_s(hg_bg_up_encode(125000)) == 120 && hg_bg_up_decode_s(hg_bg_up_encode(3u * 3600000u)) == 7200 &&
        hg_bg_up_decode_s(127) == 0xFFFFFFFFu, "uptime code: 12.5 s -> 12 s, 125 s -> 2 min, 3 h -> >= 2 h, 127 = unknown");
}

/* ---------------- C ---------------- */
static hg_bg_prev_t P(int level, int slow, int healthy, int stable, int rest)
{
  hg_bg_prev_t p; memset(&p, 0, sizeof p);
  p.valid = 1; p.level = (uint8_t)level; p.slow = (uint8_t)slow; p.healthy = (uint8_t)(healthy || stable); p.stable = (uint8_t)stable; p.rest = (uint8_t)rest;
  return p;
}
static int lvl(hg_bg_prev_t p, int cls) { hg_bg_decision_t d; hg_bg_decide(&p, cls, &d); return d.level; }
static void part_c(void)
{
  printf("== C. ladder ==\n");
  hg_bg_prev_t none; memset(&none, 0, sizeof none);
  CHECK(lvl(none, HG_RST_CRASH) == 0, "no journal, no RAM copy (first boot ever): level 0");
  int walk = 1;
  for (int l = 0; l < 6; l++) if (lvl(P(l, l, 0, 0, 0), HG_RST_CRASH) != l + 1) walk = 0;
  CHECK(walk && lvl(P(6, 6, 0, 0, 0), HG_RST_WATCHDOG) == 6, "a fault before HEALTHY climbs one level (0 -> 1 ... -> 6, saturating)");
  int fc[] = { HG_RST_WATCHDOG, HG_RST_FSGUARD, HG_RST_CRASH, HG_RST_LOCKUP, HG_BG_RST_SUPERVISOR, HG_BG_RST_ASSERT, HG_BG_RST_STACK, HG_BG_RST_MALLOC, HG_BG_RST_INJECT };
  int allf = 1; for (unsigned i = 0; i < sizeof fc / sizeof fc[0]; i++) if (lvl(P(2, 2, 0, 0, 0), fc[i]) != 3) allf = 0;
  CHECK(allf, "every fault class climbs");
  int uc[] = { HG_RST_PIN, HG_RST_POWERON, HG_RST_WAKE, HG_RST_UPLOAD };
  int allu = 1; for (unsigned i = 0; i < 4; i++) if (lvl(P(5, 9, 0, 0, 0), uc[i]) != 0) allu = 0;
  CHECK(allu, "pin / power-on / wake / upload after a level-5 boot: back to level 0 (a reset the user asked for is not a fault)");
  CHECK(lvl(P(6, 6, 0, 0, 1), HG_RST_WAKE) == 3 && lvl(P(6, 6, 0, 0, 1), HG_RST_PIN) == 3 && lvl(P(6, 6, 0, 0, 1), HG_RST_POWERON) == 3,
        "after REST: a press (wake), a reset or a power cycle tries again from SAFE (level 3)");
  CHECK(lvl(P(6, 6, 0, 0, 1), HG_RST_UPLOAD) == 0, "after REST: a new build starts at level 0");
  CHECK(lvl(P(4, 4, 1, 0, 0), HG_RST_CRASH) == 0, "a fault after HEALTHY (60 s): the fast streak is over (slow count 5, level 0)");
  CHECK(lvl(P(4, 4, 1, 1, 0), HG_RST_CRASH) == 0 && lvl(P(0, 12, 1, 1, 0), HG_RST_CRASH) == 0, "a fault after STABLE (10 min): level 0, slow count cleared");
  int sl[16]; for (int s = 0; s < 16; s++) sl[s] = lvl(P(0, s, 1, 0, 0), HG_RST_CRASH);
  CHECK(sl[0] == 0 && sl[4] == 0 && sl[5] == 2 && sl[6] == 2 && sl[7] == 3 && sl[9] == 4 && sl[11] == 5 && sl[14] == 5 && sl[15] == 5,
        "slow faults: the 6th in a row -> careful, then +1 every 2nd, capped at minimal (never REST): %d %d %d %d %d %d", sl[4], sl[5], sl[7], sl[9], sl[11], sl[15]);
  CHECK(hg_bg_mode_of(0) == HG_BG_NORMAL && hg_bg_mode_of(1) == HG_BG_NORMAL && hg_bg_mode_of(2) == HG_BG_CAREFUL && hg_bg_mode_of(3) == HG_BG_SAFE &&
        hg_bg_mode_of(4) == HG_BG_MINIMAL && hg_bg_mode_of(5) == HG_BG_MINIMAL && hg_bg_mode_of(6) == HG_BG_REST, "plan D.1 table: 0-1 normal, 2 careful, 3 safe, 4-5 minimal, 6 rest");
  hg_bg_plan_t p;
  hg_bg_plan(HG_BG_NORMAL, HG_BG_STG_BLE, &p);
  CHECK(!p.storage_off && !p.ifs_erase && !p.ifs_off && !p.ble_off && !p.rest, "normal: everything (even when the last boot died in BLE)");
  hg_bg_plan(HG_BG_CAREFUL, HG_BG_STG_NONE, &p);
  CHECK(p.storage_off && !p.ifs_erase && !p.ifs_off && !p.ble_off && !p.rest, "careful: no QSPI log");
  hg_bg_plan(HG_BG_SAFE, HG_BG_STG_NONE, &p);
  CHECK(p.storage_off && p.ifs_erase && !p.ifs_off && !p.ble_off, "safe: + InternalFS erased raw before BLE");
  hg_bg_plan(HG_BG_SAFE, HG_BG_STG_BLE, &p);
  CHECK(p.ble_off && p.ifs_off, "safe, died in BLE: BLE skipped (and so InternalFS, which only Bluefruit mounts)");
  hg_bg_plan(HG_BG_SAFE, HG_BG_STG_IFS, &p);
  CHECK(p.ifs_off && !p.ble_off, "safe, died loading InternalFS files: those skipped");
  hg_bg_plan(HG_BG_MINIMAL, HG_BG_STG_NONE, &p);
  CHECK(p.storage_off && p.ifs_erase && p.ifs_off && !p.ble_off, "minimal: + no InternalFS file of ours");
  hg_bg_plan(HG_BG_REST, HG_BG_STG_NONE, &p);
  CHECK(p.rest && p.storage_off && p.ble_off && p.ifs_off, "rest: nothing starts, service screen + off");
  int sub = 1;
  for (int d = 0; d < 4; d++) {
    int prevStarted = 7;
    for (int m = 0; m < HG_BG_MODE_COUNT; m++) {
      hg_bg_plan(m, d, &p);
      int started = (!p.storage_off) | (!p.ble_off) << 1 | (!p.ifs_off) << 2;
      if ((started & ~prevStarted) != 0) sub = 0;   /* a rung never starts something the rung above it left out */
      prevStarted = started;
    }
  }
  CHECK(sub, "each rung starts a subset of the rung above, for every dead stage (plan D.1 argument 2)");
}

/* ---------------- D ---------------- */
static uint32_t pg[HG_BG_PAGE_WORDS];
static void part_d(void)
{
  printf("== D. scan + ledger + merge ==\n");
  memset(pg, 0xFF, sizeof pg);
  hg_bg_scan_t s; hg_bg_scan(pg, HG_BG_PAGE_WORDS, &s);
  CHECK(s.append == 0 && !s.prev.valid && s.boots == 0, "erased page: empty, no previous boot");
  int n = 0;
  for (int b = 0; b < 12; b++) {
    hg_bg_decision_t d = { (uint8_t)(b % 7), 0, 0 };
    pg[n++] = hg_bg_started(b < 3 ? HG_RST_PIN : HG_BG_RST_SUPERVISOR, &d, (uint8_t)b, (uint8_t)(10 + b));
    if (b % 2) pg[n++] = hg_bg_mark(HG_BG_T_HEALTHY);
  }
  pg[n++] = 0x12345678u;                             /* junk */
  pg[n++] = hg_bg_mark(HG_BG_T_STABLE);
  hg_bg_scan(pg, HG_BG_PAGE_WORDS, &s);
  CHECK(s.append == n && s.used == n && s.corrupt == 1 && s.boots == 12 && s.by_cls[HG_RST_PIN] == 3 && s.by_cls[HG_BG_RST_SUPERVISOR] == 9,
        "12 boots: append=%d corrupt=%d, counts per class (3 pin, 9 supervisor)", s.append, s.corrupt);
  CHECK(s.nlast == 8 && s.last[0].cp == 11 && s.last[7].cp == 4 && s.last[0].upc == 21, "ledger: the last 8 STARTED, newest first (checkpoint, uptime)");
  CHECK(s.prev.valid && s.prev.level == 11 % 7 && s.prev.healthy && s.prev.stable && !s.prev.rest, "previous boot = the newest STARTED + its marks (junk ignored)");
  hg_bg_prev_t a = P(2, 2, 1, 0, 0), b = P(4, 1, 0, 0, 0);
  hg_bg_merge(&a, &b);
  CHECK(a.level == 4 && a.slow == 2 && !a.healthy, "merge: higher level / slow count wins, HEALTHY only if both copies say so");
  hg_bg_prev_t c; memset(&c, 0, sizeof c); hg_bg_prev_t r = P(1, 0, 0, 0, 1);
  hg_bg_merge(&c, &r); CHECK(c.valid && c.rest && c.level == 1, "merge into an empty copy = the other copy");
  hg_bg_prev_t e = P(3, 0, 0, 0, 0), inv; memset(&inv, 0, sizeof inv); hg_bg_merge(&e, &inv);
  CHECK(e.level == 3 && e.valid, "merge with an invalid copy changes nothing");
}

/* ---------------- E: simulated NOR page + device ---------------- */
static uint32_t nor[HG_BG_PAGE_WORDS];
static int wrFail = 0, erFail = 0, cutAt = -1, writes = 0, erases = 0;
static int nor_write(void *ctx, int i, uint32_t w)
{
  (void)ctx; writes++;
  if (wrFail && (int)(rnd() % 100) < wrFail) { nor[i] &= w | (rnd() & ~w & 0x0F0F0F0Fu); return 0; }   /* failed: some bits taken */
  if (cutAt >= 0 && writes == cutAt) { nor[i] &= w | (rnd() & ~w); return 0; }                          /* power cut mid-program */
  nor[i] &= w; return 1;                             /* NOR: bits only go 1 -> 0 */
}
static int nor_erase(void *ctx) { (void)ctx; erases++; if (erFail) return 0; memset(nor, 0xFF, sizeof nor); return 1; }
static const hg_bg_flash_t NF = { nor, nor_write, nor_erase, NULL };

typedef struct { hg_bg_prev_t ni; int niValid; hg_bg_decision_t d; int cls; } dev_t;
/* one boot, mirroring setup(): classify, scan + merge + decide, STARTED appended, "this boot" mirrored in RAM */
static int dev_boot(dev_t *v, int cls)
{
  hg_bg_scan_t s; hg_bg_prev_t m;
  hg_bg_boot(nor, v->niValid ? &v->ni : NULL, cls, &s, &m, &v->d);
  hg_bg_append(&NF, hg_bg_started(cls, &v->d, 5, 7));
  hg_bg_cur(&v->ni, cls, &v->d); v->niValid = 1; v->cls = cls;
  if (v->d.mode == HG_BG_REST) { hg_bg_append(&NF, hg_bg_mark(HG_BG_T_REST)); v->niValid = 0; }   /* System OFF: RAM gone */
  return v->d.mode;
}
static void dev_healthy(dev_t *v) { hg_bg_append(&NF, hg_bg_mark(HG_BG_T_HEALTHY)); v->ni.healthy = 1; }
static void dev_stable(dev_t *v) { hg_bg_append(&NF, hg_bg_mark(HG_BG_T_STABLE)); v->ni.stable = 1; }
static void part_e(void)
{
  printf("== E. simulated NOR page + device ==\n");
  dev_t v; memset(&v, 0, sizeof v); memset(nor, 0xFF, sizeof nor); wrFail = erFail = 0; cutAt = -1;
  dev_boot(&v, HG_RST_UPLOAD); dev_healthy(&v); dev_stable(&v);
  int modes[8], k = 0;
  modes[k++] = dev_boot(&v, HG_BG_RST_REBOOT);       /* "fault loop 6": a commanded reset (not a fault), then 6 boots crash */
  while (k < 8 && modes[k - 1] != HG_BG_REST) modes[k++] = dev_boot(&v, HG_BG_RST_INJECT);
  CHECK(k == 7 && modes[0] == HG_BG_NORMAL && modes[1] == HG_BG_NORMAL && modes[2] == HG_BG_CAREFUL && modes[3] == HG_BG_SAFE &&
        modes[4] == HG_BG_MINIMAL && modes[5] == HG_BG_MINIMAL && modes[6] == HG_BG_REST,
        "fault loop 6: boots at level 0..5 crash (normal, normal, careful, safe, minimal, minimal), the 7th boot is REST (dark)");
  CHECK(dev_boot(&v, HG_RST_WAKE) == HG_BG_SAFE && v.d.level == 3, "a press from off (wake, RAM lost): SAFE");
  dev_healthy(&v);
  CHECK(dev_boot(&v, HG_RST_CRASH) == HG_BG_NORMAL, "SAFE boot reached HEALTHY, then a crash: normal again (slow count %u)", v.d.slow);
  int pin = 1; for (int i = 0; i < 10; i++) if (dev_boot(&v, HG_RST_PIN) != HG_BG_NORMAL || v.d.level) pin = 0;
  CHECK(pin, "10 pin resets in a row (never HEALTHY): level 0 every time");
  /* journal writes fail: the RAM copy carries the ladder */
  memset(nor, 0xFF, sizeof nor); memset(&v, 0, sizeof v); dev_boot(&v, HG_RST_UPLOAD);
  wrFail = 100; k = 0; int m;
  do { m = dev_boot(&v, HG_RST_WATCHDOG); k++; } while (m != HG_BG_REST && k < 10);
  CHECK(k == 6, "every journal write fails (flash dead): the .hg_noinit copy alone walks to REST in %d resets", k);
  wrFail = 0;
  /* RAM lost at every boot (only for the test: a soft / watchdog reset keeps it): the journal alone */
  memset(nor, 0xFF, sizeof nor); memset(&v, 0, sizeof v); dev_boot(&v, HG_RST_UPLOAD); k = 0;
  do { v.niValid = 0; m = dev_boot(&v, HG_RST_CRASH); k++; } while (m != HG_BG_REST && k < 10);
  CHECK(k == 6, "RAM copy lost at every boot: the journal alone walks to REST in %d resets", k);
  /* the two copies disagree: the higher level wins */
  memset(nor, 0xFF, sizeof nor); memset(&v, 0, sizeof v); dev_boot(&v, HG_RST_UPLOAD); v.ni.level = 4;
  CHECK(dev_boot(&v, HG_RST_CRASH) == HG_BG_MINIMAL && v.d.level == 5, "journal says level 0, RAM says 4: level 5 (the larger copy)");
  /* power cut inside every word written by a short history: the page always parses, appends continue after the torn word */
  int cutsOk = 1;
  for (int c = 1; c <= 12; c++) {
    memset(nor, 0xFF, sizeof nor); memset(&v, 0, sizeof v); writes = 0; cutAt = c;
    dev_boot(&v, HG_RST_UPLOAD); dev_healthy(&v); dev_boot(&v, HG_RST_CRASH); dev_boot(&v, HG_RST_CRASH); dev_healthy(&v); dev_stable(&v);
    dev_boot(&v, HG_RST_CRASH); dev_boot(&v, HG_RST_CRASH);
    cutAt = -1; v.niValid = 0;                       /* the cut = power-on: RAM lost */
    hg_bg_scan_t s; hg_bg_scan(nor, HG_BG_PAGE_WORDS, &s);
    int mode = dev_boot(&v, HG_RST_POWERON);
    hg_bg_scan_t s2; hg_bg_scan(nor, HG_BG_PAGE_WORDS, &s2);
    if (mode != HG_BG_NORMAL || s2.append <= s.append || s.used > 14) cutsOk = 0;
  }
  CHECK(cutsOk, "power cut inside each of the first 12 words: the page parses, the next boot appends after it, power-on = level 0");
  /* compaction */
  memset(nor, 0xFF, sizeof nor); memset(&v, 0, sizeof v); erases = 0; dev_boot(&v, HG_RST_UPLOAD);
  int lvOk = 1;
  for (int i = 0; i < 3000; i++) {
    int cls = (i % 5 == 4) ? HG_RST_PIN : HG_RST_CRASH;
    dev_boot(&v, cls);
    if (i % 3 == 0) dev_healthy(&v);
    if (v.d.mode == HG_BG_REST) { dev_boot(&v, HG_RST_WAKE); dev_healthy(&v); }
    hg_bg_scan_t s; hg_bg_scan(nor, HG_BG_PAGE_WORDS, &s);
    if (!s.prev.valid || s.prev.level != v.d.level || s.nlast < (s.boots < 8 ? s.boots : 8) || (i > 20 && s.nlast < 8) || s.append >= HG_BG_PAGE_WORDS) lvOk = 0;
  }
  CHECK(lvOk && erases >= 2, "3,000 boots: the page compacted %d times, the previous boot and the last 8 resets always readable", erases);
  /* erase fails during compaction: the append fails, the RAM copy still has the level */
  memset(nor, 0x00, sizeof nor);                     /* a full page of junk */
  for (int i = 0; i < HG_BG_PAGE_WORDS; i++) nor[i] = hg_bg_mark(HG_BG_T_HEALTHY);
  memset(&v, 0, sizeof v); v.niValid = 1; v.ni = P(3, 3, 0, 0, 0); erFail = 1;
  int r = dev_boot(&v, HG_RST_CRASH);
  CHECK(r == HG_BG_MINIMAL && v.d.level == 4, "full page and the erase fails: the boot still runs at the RAM copy's level + 1 (%d)", v.d.level);
  erFail = 0;
  CHECK(hg_bg_append(&NF, hg_bg_mark(HG_BG_T_HEALTHY)) == 1, "the next append compacts the page and works");
  hg_bg_scan_t s3; hg_bg_scan(nor, HG_BG_PAGE_WORDS, &s3);
  CHECK(s3.append == HG_BG_KEEP_WORDS + 1, "compaction kept the newest %d valid words (+1 new): append=%d", HG_BG_KEEP_WORDS, s3.append);
}

/* ---------------- F: random boots ---------------- */
static void part_f(void)
{
  printf("== F. 200,000 random boots ==\n");
  dev_t v; memset(&v, 0, sizeof v); memset(nor, 0xFF, sizeof nor); wrFail = 3; erFail = 0; cutAt = -1;
  dev_boot(&v, HG_RST_UPLOAD);
  int fastRun = 0, maxFast = 0, restBad = 0, userNot0 = 0, rests = 0, prevMode = 0;
  for (long i = 0; i < 200000; i++) {
    int healthy = 0;
    if (prevMode != HG_BG_REST) {                    /* the boot just made runs for a while, then ends somehow */
      unsigned o = rnd() % 100;
      if (o < 35) {} else if (o < 60) { dev_healthy(&v); healthy = 1; } else { dev_healthy(&v); dev_stable(&v); healthy = 1; }
    }
    unsigned e = rnd() % 100; int cls;
    static const int FC[5] = { HG_RST_WATCHDOG, HG_RST_FSGUARD, HG_RST_CRASH, HG_BG_RST_SUPERVISOR, HG_BG_RST_ASSERT };
    if (prevMode == HG_BG_REST) cls = (e < 70) ? HG_RST_WAKE : (e < 85 ? HG_RST_PIN : HG_RST_POWERON);
    else if (e < 70) cls = FC[rnd() % 5];
    else if (e < 85) cls = HG_RST_PIN; else if (e < 95) cls = HG_RST_POWERON; else cls = HG_RST_UPLOAD;
    if (cls == HG_RST_POWERON || prevMode == HG_BG_REST) v.niValid = 0;   /* RAM survives soft / watchdog / pin resets only */
    int fault = hg_bg_is_fault(cls), fast = fault && !healthy && prevMode != HG_BG_REST;
    int m = dev_boot(&v, cls);
    fastRun = fast ? fastRun + 1 : 0;
    if (fastRun > maxFast) maxFast = fastRun;
    if (m == HG_BG_REST) { rests++; if (!fast) restBad++; fastRun = 0; }
    if (!fault && prevMode != HG_BG_REST && v.d.level != 0) userNot0++;
    prevMode = m;
  }
  CHECK(maxFast <= 6, "fast faults in a row (no HEALTHY in between) never exceed 6 before REST: max run %d, %d rests, journal writes failing 3 %%", maxFast, rests);
  CHECK(restBad == 0, "REST only ever right after a fast fault (never after a slow fault, a user reset or an upload)");
  CHECK(userNot0 == 0, "a pin / power-on reset or an upload after a running boot always restarts at level 0");
  wrFail = 0;
}

/* ---------------- G: supervisor ---------------- */
static void part_g(void)
{
  printf("== G. supervisor ==\n");
  hg_sup_t s; memset(&s, 0, sizeof s); hg_sup_in_t in; hg_sup_out_t o; memset(&in, 0, sizeof in);
  in.now = 10000; in.app_beat = 9990; hg_sup_step(&s, &in, &o);
  CHECK(o.feed && !o.reset_app && !o.writer_stuck, "app checked in 10 ms ago: feed");
  in.now = 14980; hg_sup_step(&s, &in, &o); CHECK(o.feed && !o.reset_app, "app silent 4.99 s: still fed");
  in.now = 15000; hg_sup_step(&s, &in, &o); CHECK(!o.feed && o.reset_app, "app silent 5.01 s: no feed, named supervisor reset (before the 8 s watchdog)");
  in.app_in_guard = 1; in.guard_since_io = 300; in.guard_total = 12000; in.now = 22000;
  hg_sup_step(&s, &in, &o); CHECK(o.feed && !o.reset_app, "app silent 12 s but inside a guarded file call doing flash I/O: fed (plan D.4)");
  in.guard_since_io = 4500; hg_sup_step(&s, &in, &o); CHECK(!o.feed && o.reset_app, "guarded call with no I/O for 4.5 s: not fed (the FS guard resets it first, with its marker)");
  in.guard_since_io = 10; in.guard_total = 31000; hg_sup_step(&s, &in, &o); CHECK(!o.feed, "guarded call running 31 s: not fed");
  in.app_in_guard = 0; in.now = 0x00000100u; in.app_beat = 0xFFFFFF00u; hg_sup_step(&s, &in, &o);
  CHECK(o.feed, "millis() wrap: a beat 512 ms ago across the wrap is fresh");
  in.now = 1000; in.app_beat = 1003; hg_sup_step(&s, &in, &o); CHECK(o.feed, "a beat stamped just after 'now' was read (race) counts as fresh, not as 49 days old");
  in.app_beat = 1000; in.writer_busy = 1; in.writer_job_t0 = 1000 - 95000u; in.writer_in_guard = 0; hg_sup_step(&s, &in, &o);
  CHECK(o.feed && o.writer_stuck && !o.reset_app, "writer busy 95 s outside any guarded call: storage off, never a reset");
  in.writer_in_guard = 1; hg_sup_step(&s, &in, &o); CHECK(!o.writer_stuck, "writer inside a guarded call: the FS guard owns it");
  in.writer_in_guard = 0; in.writer_job_t0 = 1000 - 20000u; hg_sup_step(&s, &in, &o); CHECK(!o.writer_stuck, "writer busy 20 s: fine");
  memset(&s, 0, sizeof s); in.writer_busy = 0;
  in.now = 100; in.app_beat = 100; hg_sup_step(&s, &in, &o); in.now = 350; hg_sup_step(&s, &in, &o); in.now = 2350; hg_sup_step(&s, &in, &o);
  CHECK(s.max_tick_gap == 2000 && s.ticks == 3, "timer check-in: the largest gap between supervisor ticks is kept (%lu ms)", (unsigned long)s.max_tick_gap);
}

int main(void)
{
  part_a(); part_b(); part_c(); part_d(); part_e(); part_f(); part_g();
  printf("TEST_BOOTGUARD: %d passed, %d failed\n", npass, nfail);
  return nfail ? 1 : 0;
}
