/* Host test of the 0.9.10 FS-HEAL layer (fw/09_guardian/hg_fw_heal.c).
 *   sh fw/tools/run_host_tests.sh   (section 8e)
 * Part A: the heal state machine boot by boot: marker encode/decode, first 0.9.10 boot, a marker naming each file id,
 *         dying inside a heal remove, boot loop without marker (quiet + blind heal), the trouble streak -> log-area
 *         format -> storage switched off, mount failures, stable uptime, runtime append failures, generations, names.
 * Part B: the REAL littlefs v1.6 of the Seeed core (sketch config) with a POISONED events file: one CTZ skip pointer
 *         that only lfs_ctz_extend reads (not the allocator's traversal) is corrupted. Shows the bench symptom exactly:
 *         the other files still append (traversal fine), the events append aborts in LFS_ASSERT (= the silent
 *         "b _exit" spin on the band) on EVERY "boot", and renaming does not help. Then the heal: marker -> quarantine ->
 *         remove -> events_<gen+1>.txt appends, every other file intact, and the poisoned name is never opened again.
 * Usage: test_heal
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <sys/wait.h>
#include <sys/mman.h>
#include "hg_fw_heal.h"
#include "log_ring.h"
#include "lfs.h"

static int fails = 0, passes = 0;
#define CHECK(c, ...) do { if (c) { printf("PASS  "); passes++; } else { printf("FAIL  "); fails++; } printf(__VA_ARGS__); printf("\n"); } while (0)

/* ------------------------------------------------------------------ Part A helpers */
static hg_heal_state_t S; static hg_heal_boot_t B;
#define BUILD 0x12345678u
static uint8_t mk(uint8_t cause, uint8_t fid) { return hg_heal_marker_encode(cause, fid, 1, 0); }
/* one boot through the three phases, as storageInit() calls them (mount ok) */
static void boot(uint8_t marker, int bootloop, uint16_t max_gen, const char *s_newest)
{
  hg_heal_state_t saved = S; int valid;
  hg_heal_state_seal(&saved); valid = hg_heal_state_valid(&saved);   /* round trip through "InternalFS" */
  S = saved;
  hg_heal_begin(&S, &B, valid, marker, BUILD);
  if (!B.disable && !B.format_pre_mount) hg_heal_after_boot(&S, &B, bootloop, max_gen, s_newest, "/log/r0003.bin");
  if (B.format || B.format_pre_mount) hg_heal_formatted(&S);
  if (B.remove_path[0]) hg_heal_remove_done(&S, &B, 1);
}

static void part_a(void)
{
  printf("== A. heal state machine ==\n");
  /* markers */
  int okrt = 1;
  for (uint8_t c = HG_CAUSE_DEADLINE; c <= HG_CAUSE_ASSERT; c++) for (uint8_t f = 0; f < HG_FID_COUNT; f++)
    for (uint8_t n = 1; n <= 3; n++) for (uint8_t ib = 0; ib <= 1; ib++) {
      uint8_t cc, ff, nn, ii;
      if (!hg_heal_marker_decode(hg_heal_marker_encode(c, f, n, ib), &cc, &ff, &nn, &ii) || cc != c || ff != f || nn != n || ii != ib) okrt = 0;
    }
  CHECK(okrt, "marker round trip: every cause x file id x count 1-3 x ifs flag");
  uint8_t c, f, n, ib;
  CHECK(!hg_heal_marker_decode(0x00, &c, &f, &n, &ib) && !hg_heal_marker_decode(0x8F, &c, &f, &n, &ib) &&
        !hg_heal_marker_decode(0x4C, &c, &f, &n, &ib), "no marker from 0x00 (watchdog/power-on clear) or any count-0 byte");
  CHECK(hg_heal_marker_encode(HG_CAUSE_ASSERT, HG_FID_NONE, 7, 0) == hg_heal_marker_encode(HG_CAUSE_ASSERT, HG_FID_NONE, 3, 0),
        "count saturates at 3");

  /* names */
  CHECK(hg_heal_events_gen("events_12.txt") == 12 && hg_heal_events_gen("events_1.txt") == 1 && !hg_heal_events_gen("events_0.txt") &&
        !hg_heal_events_gen("events_.txt") && !hg_heal_events_gen("events2.txt") && !hg_heal_events_gen("events.txt") &&
        !hg_heal_events_gen("events_1.txtx") && !hg_heal_events_gen("events_1a.txt") && !hg_heal_events_gen("events_99999.txt"),
        "events_<gen>.txt parsing (legacy names and junk are not a generation)");
  char p[24]; hg_heal_events_path(7, p, sizeof p);
  uint16_t q;
  CHECK(strcmp(p, "/log/events_7.txt") == 0 && hg_ring_classify("events_7.txt", &q) == 'e' && hg_ring_classify("events_65535.txt", &q) == 'e' &&
        hg_ring_classify("events2.txt", &q) == 'e' && hg_ring_classify("events_x.txt", &q) == '?' && hg_ring_classify("events_.txt", &q) == '?',
        "log_ring: events_<gen>.txt and the legacy names are kind 'e' (never deleted by the ring)");
  CHECK(hg_heal_is_legacy_events("events.txt") && hg_heal_is_legacy_events("events2.txt") && !hg_heal_is_legacy_events("events_2.txt"),
        "legacy events names");

  /* 1. first 0.9.10 boot on THIS band: no /fsheal.bin, no marker (0.9.6 died by watchdog), legacy files, no events_* yet */
  memset(&S, 0xA5, sizeof S);
  hg_heal_begin(&S, &B, 0, 0x00, BUILD);
  hg_heal_after_boot(&S, &B, 0, 0, "/log/s0002.bin", "");
  CHECK(B.state_new && B.reset_quick_boots && !B.marker && !B.heal_boot && !B.quiet && !B.format && !B.rotate_events && !B.new_sfile &&
        S.gen == 1 && S.streak == 0 && !B.remove_path[0], "first 0.9.10 boot: new state, gen 1 (events_1.txt), quick_boots reset, nothing healed");
  CHECK(!hg_heal_is_quarantined(&S, "/log/s0002.bin"), "first boot keeps appending to the newest s-file");
  CHECK(B.new_build && S.build == BUILD, "first boot of a build is flagged (quick_boots of the old firmware are reset)");
  { hg_heal_state_t t = S; hg_heal_boot_t tb; hg_heal_begin(&t, &tb, 1, 0, BUILD);
    CHECK(!tb.new_build && !tb.reset_quick_boots, "same build again: not an upload (a soft reset of it counts as a quick boot)");
    hg_heal_begin(&t, &tb, 1, 0, BUILD + 1);
    CHECK(tb.new_build && tb.reset_quick_boots && !tb.state_new, "another build with a valid state: an upload, quick_boots reset, state kept"); }

  /* 2. state lost later while events_5 exists: never reuse a file of unknown health */
  hg_heal_state_t keep = S;
  hg_heal_begin(&S, &B, 0, 0x00, BUILD); hg_heal_after_boot(&S, &B, 0, 5, "", "");
  CHECK(S.gen == 6, "state lost with events_5.txt on disk -> gen 6 (a fresh file)");
  S = keep;
  boot(0, 0, 1, "/log/s0002.bin");
  CHECK(S.gen == 1 && !B.heal_boot, "normal boot with its own events_1.txt on disk keeps gen 1");

  /* 3. the bench bug: the events append asserted */
  boot(mk(HG_CAUSE_ASSERT, HG_FID_EVENTS), 0, 1, "/log/s0002.bin");
  CHECK(B.marker && B.cause == HG_CAUSE_ASSERT && B.fid == HG_FID_EVENTS && B.heal_boot && !B.quiet && B.rotate_events && S.gen == 2 &&
        hg_heal_is_quarantined(&S, "/log/events_1.txt") && strcmp(B.remove_path, "/log/events_1.txt") == 0 && S.streak == 1 && S.faults == 1,
        "marker ASSERT:events -> events_1 quarantined + removed, live log events_2.txt, streak 1");
  CHECK(!B.new_sfile && !S.pending[0], "an events marker leaves the s-file alone; pending cleared after the remove");

  /* 4. died INSIDE the heal remove: the file is never touched again */
  hg_heal_begin(&S, &B, 1, mk(HG_CAUSE_ASSERT, HG_FID_EVENTS), BUILD); hg_heal_after_boot(&S, &B, 0, 2, "/log/s0002.bin", "");
  CHECK(strcmp(S.pending, "/log/events_2.txt") == 0, "pending = the file about to be removed (saved before the remove)");
  hg_heal_begin(&S, &B, 1, mk(HG_CAUSE_DEADLINE, HG_FID_HEAL), BUILD); hg_heal_after_boot(&S, &B, 0, 3, "/log/s0002.bin", "");
  CHECK(B.heal_boot && !S.pending[0] && hg_heal_is_quarantined(&S, "/log/events_2.txt") && !B.remove_path[0] && S.gen == 3 && S.streak == 3,
        "died in the heal remove -> quarantined for good, no second remove, gen stays 3, streak 3");

  /* 5. stable: the trouble is over */
  CHECK(hg_heal_stable(&S, 1) && S.streak == 0 && !hg_heal_stable(&S, 1), "10 min stable with storage OK clears the streak (once)");
  S.streak = 2; CHECK(!hg_heal_stable(&S, 0) && S.streak == 2, "stable with storage off does not clear the streak"); S.streak = 0;

  /* 6. boot loop without a marker (hang with interrupts off -> hardware watchdog) */
  boot(0, 1, 3, "/log/s0004.bin");
  CHECK(B.quiet && B.heal_boot && B.rotate_events && B.new_sfile && S.gen == 4 && !hg_heal_is_quarantined(&S, "/log/events_3.txt") &&
        !B.remove_path[0] && S.streak == 1, "boot loop, no marker -> quiet boot + blind heal (new events gen, new s-file, nothing quarantined or removed)");

  /* 7. the s-file asserted */
  boot(mk(HG_CAUSE_ASSERT, HG_FID_SFILE), 0, 4, "/log/s0005.bin");
  CHECK(B.new_sfile && hg_heal_is_quarantined(&S, "/log/s0005.bin") && !B.rotate_events && S.gen == 4 && !B.remove_path[0],
        "marker ASSERT:sfile -> newest s-file quarantined (kept, not removed: data), new s-file, events gen unchanged");
  CHECK(S.streak == 2 && hg_heal_stable(&S, 1) && S.streak == 0, "streak 2 after two troubled boots; 10 min stable clears it");
  /* 8. dump read, raw, boot.bin */
  strcpy(S.dump_path, "/log/s0001.bin");
  boot(mk(HG_CAUSE_DEADLINE, HG_FID_DUMP), 0, 4, "/log/s0006.bin");
  CHECK(hg_heal_is_quarantined(&S, "/log/s0001.bin") && !S.dump_path[0] && !B.rotate_events, "marker DEADLINE:dump -> the file being dumped is quarantined");
  boot(mk(HG_CAUSE_ASSERT, HG_FID_BOOT), 0, 4, "/log/s0006.bin");
  CHECK(B.remove_boot && strcmp(B.quarantine_path, "/log/boot.bin") == 0, "marker ASSERT:boot -> remove boot.bin before reading it");
  boot(mk(HG_CAUSE_DEADLINE, HG_FID_RING), 0, 4, "/log/s0007.bin");
  CHECK(!B.rotate_events && !B.new_sfile && !B.quarantine_path[0] && S.gen == 4 && S.streak == 3,
        "0.9.11: marker DEADLINE:ring (no file named) -> counted (streak 3), NOTHING quarantined or rotated");

  /* 9. the 4th troubled boot in a row re-formats the log area (before mounting it, a marker said so) */
  boot(mk(HG_CAUSE_ASSERT, HG_FID_LIST), 0, 4, "/log/s0006.bin");
  CHECK(B.format && B.format_pre_mount && S.formats == 1 && S.streak == 0 && S.gen == 5 && !S.q[0][0],
        "4th troubled boot -> log area re-formatted (pre-mount), formats 1, streak 0, new gen, quarantine list emptied");
  /* 10. a fresh log area that still fails: 3 more troubled boots are tolerated, the 4th switches storage off */
  for (int i = 0; i < 3; i++) boot(mk(HG_CAUSE_DEADLINE, HG_FID_MOUNT), 0, 0, "");
  CHECK(!B.disable && S.post_format == 3 && !B.format, "after a heal format: 3 more troubled boots, no format loop");
  boot(mk(HG_CAUSE_DEADLINE, HG_FID_MOUNT), 0, 0, "");
  CHECK(B.disable && S.disabled && !B.format, "4th -> storage switched off (the band runs without a log: never a boot loop)");
  boot(0, 0, 0, "");
  CHECK(B.disable, "storage stays off on the next boot");
  hg_heal_reset(&S); boot(0, 0, 0, "");
  CHECK(!B.disable && !S.disabled && S.streak == 0, "fsheal reset switches it back on");

  /* 11. mount failures (our file system, unreadable): 4 in a row -> re-format after mounting failed */
  hg_heal_state_init(&S); S.gen = 9;
  for (int i = 0; i < 4; i++) {
    hg_heal_begin(&S, &B, 1, 0, BUILD); hg_heal_mount_failed(&S, &B);
    if (i < 3) CHECK(!B.format && S.streak == (uint8_t)(i + 1), "mount failure %d -> kept (data), streak %d", i + 1, i + 1);
  }
  CHECK(B.format && !B.format_pre_mount, "4th mount failure in a row -> re-format the log area");
  hg_heal_formatted(&S);
  CHECK(S.gen == 10 && S.formats == 1, "after the format: gen 10");

  /* 12. a mount marker alone retries the mount (the format only when the streak runs out) */
  hg_heal_state_init(&S); S.gen = 2;
  hg_heal_begin(&S, &B, 1, mk(HG_CAUSE_DEADLINE, HG_FID_MOUNT), BUILD);
  CHECK(!B.format && !B.format_pre_mount && B.heal_boot, "one mount deadline: mount again (streak 1)");
  hg_heal_begin(&S, &B, 1, mk(HG_CAUSE_ASSERT, HG_FID_FORMAT), BUILD);
  CHECK(B.disable && !B.format && !B.format_pre_mount && !S.disabled, "0.9.11: the format itself died -> storage OFF this boot (not persisted)");

  /* 12b. 0.9.11 count rule (the bench sequence): the count travels in GPREGRET2, so it is known before ANY flash call */
  hg_heal_state_init(&S); S.gen = 1;
  hg_heal_begin(&S, &B, 1, hg_heal_marker_encode(HG_CAUSE_ASSERT, HG_FID_EVENTS, 1, 0), BUILD);
  CHECK(B.count == 1 && !B.format && !B.disable, "1st guard reset (events) -> heal only");
  hg_heal_after_boot(&S, &B, 0, 1, "/log/s0002.bin", "");
  CHECK(hg_heal_is_quarantined(&S, "/log/events_1.txt") && S.gen == 2, "  events_1 quarantined, gen 2");
  hg_heal_begin(&S, &B, 0, hg_heal_marker_encode(HG_CAUSE_ASSERT, HG_FID_LIST, 2, 0), BUILD);   /* state NOT saved (as on the bench) */
  CHECK(B.count == 2 && B.format && B.format_pre_mount && !B.disable && !B.quarantine_path[0],
        "2nd guard reset in a row, fid=list (unnamed), heal state lost -> re-format BEFORE mounting, nothing quarantined");
  /* 0.9.16 (plan A-24): a fid=none marker (only an older build can leave one) never touches the log area */
  { hg_heal_state_t S2; hg_heal_boot_t B2; hg_heal_state_init(&S2); S2.gen = 3; S2.streak = 3;
    for (uint8_t c = 1; c <= 3; c++) {
      hg_heal_begin(&S2, &B2, 1, hg_heal_marker_encode(HG_CAUSE_ASSERT, HG_FID_NONE, c, 0), BUILD);
      CHECK(B2.marker && B2.count == c && !B2.format && !B2.format_pre_mount && !B2.disable && !S2.disabled && !B2.heal_boot && S2.streak == 3,
            "0.9.16 A-24: fid=none marker count %u -> counted (faults=%lu), no streak, no format, no storage-off", c, (unsigned long)S2.faults);
      hg_heal_after_boot(&S2, &B2, 0, 3, "/log/s0001.bin", "");
      CHECK(!B2.format && !B2.disable && !B2.quarantine_path[0] && S2.gen == 3, "  ... and after the boot: nothing quarantined, events generation kept");
    }
    hg_heal_begin(&S2, &B2, 1, hg_heal_marker_encode(HG_CAUSE_DEADLINE, HG_FID_NONE, 3, 1), BUILD);
    CHECK(!B2.format && !B2.disable, "0.9.16 A-24: fid=none with ifs_bad, count 3: still no format / storage-off"); }
  hg_heal_begin(&S, &B, 1, hg_heal_marker_encode(HG_CAUSE_DEADLINE, HG_FID_LIST, 3, 0), BUILD);
  CHECK(B.disable && !B.format, "3rd in a row (failed again after the format) -> storage OFF this boot");
  hg_heal_begin(&S, &B, 1, hg_heal_marker_encode(HG_CAUSE_ASSERT, HG_FID_IFS, 1, 1), BUILD);
  CHECK(B.ifs_bad && B.fid == HG_FID_IFS && !B.format && !B.quarantine_path[0], "an InternalFS assert: ifs_bad carried, counted, nothing quarantined");
  hg_heal_begin(&S, &B, 1, 0x00, BUILD);
  CHECK(!B.marker && !B.format && !B.disable && !B.count, "clean boot (register 0): the chain is over");

  /* 12c. 0.9.13: per-class counts + progress deadline (the 0.9.12 bench: InternalFS faults + one slow events append = log OFF) */
  CHECK(hg_heal_next_count(0, 0, HG_FID_EVENTS) == 1 && hg_heal_next_count(1, HG_FID_EVENTS, HG_FID_EVENTS) == 2 &&
        hg_heal_next_count(2, HG_FID_NONE, HG_FID_SFILE) == 3 && hg_heal_next_count(3, HG_FID_EVENTS, HG_FID_EVENTS) == 3,
        "log faults in a row count 1, 2, 3 (any log file id, saturating)");
  CHECK(hg_heal_next_count(3, HG_FID_IFS_ECO, HG_FID_EVENTS) == 1 && hg_heal_next_count(2, HG_FID_EVENTS, HG_FID_IFS_TWIN) == 1 &&
        hg_heal_next_count(1, HG_FID_IFS_ECO, HG_FID_IFS_TWIN) == 2,
        "a fault of the OTHER class restarts at 1: 3 InternalFS faults then a log fault = log count 1, not 'storage off'");
  { uint8_t prev = 0, pf = 0, c3 = 0; const uint8_t seq[4] = { HG_FID_IFS_ECO, HG_FID_IFS_ECO, HG_FID_IFS_HEAL, HG_FID_EVENTS };
    for (int i = 0; i < 4; i++) { c3 = hg_heal_next_count(prev, pf, seq[i]); prev = c3; pf = seq[i]; }
    hg_heal_state_init(&S);
    hg_heal_begin(&S, &B, 1, hg_heal_marker_encode(HG_CAUSE_DEADLINE, HG_FID_EVENTS, c3, 1), BUILD);
    CHECK(c3 == 1 && !B.disable && !B.format && B.count == 1, "the bench chain (ifs, ifs, ifs, events DEADLINE) -> events count 1: heal only, storage stays ON"); }
  CHECK(!hg_heal_deadline_hit(6000, 300) && !hg_heal_deadline_hit(29000, 1400), "a slow call that keeps doing flash I/O is not killed (6 s, 29 s)");
  CHECK(hg_heal_deadline_hit(4100, 4100) && hg_heal_deadline_hit(31000, 10), "no I/O for > 4 s, or > 30 s in total = hung");

  /* 13. runtime: an append that fails (error, not a hang) */
  hg_heal_state_init(&S); S.gen = 3; uint8_t fr = 0;
  int r1 = hg_heal_events_result(&S, &fr, 1), r2 = hg_heal_events_result(&S, &fr, 1), r3 = hg_heal_events_result(&S, &fr, 0);
  CHECK(!r1 && !r2 && !r3 && fr == 0 && S.gen == 3, "2 failed appends then a good one: nothing rotates");
  hg_heal_events_result(&S, &fr, 1); hg_heal_events_result(&S, &fr, 1); int r6 = hg_heal_events_result(&S, &fr, 1);
  CHECK(r6 && S.gen == 4 && hg_heal_is_quarantined(&S, "/log/events_3.txt") && fr == 0, "3 failed appends in a row -> events gen 4, events_3 quarantined");

  /* 14. quarantine list: newest first, capacity HG_HEAL_QMAX, no duplicates */
  hg_heal_state_init(&S);
  for (int i = 0; i < HG_HEAL_QMAX + 2; i++) { char x[24]; snprintf(x, sizeof x, "/log/s%04d.bin", i); hg_heal_quarantine(&S, x); }
  hg_heal_quarantine(&S, "/log/s0005.bin");
  CHECK(hg_heal_is_quarantined(&S, "/log/s0005.bin") && hg_heal_is_quarantined(&S, "/log/s0002.bin") && !hg_heal_is_quarantined(&S, "/log/s0001.bin") &&
        S.quarantined == HG_HEAL_QMAX + 2 && !hg_heal_is_quarantined(&S, ""), "quarantine FIFO keeps the newest %d", HG_HEAL_QMAX);

  /* 15. state integrity */
  hg_heal_state_init(&S); S.gen = 4; hg_heal_state_seal(&S);
  hg_heal_state_t bad = S; bad.gen = 5;
  CHECK(hg_heal_state_valid(&S) && !hg_heal_state_valid(&bad), "heal state CRC catches a changed byte");
  CHECK(sizeof(hg_heal_state_t) <= 256, "heal state is %u bytes (one small InternalFS file)", (unsigned)sizeof(hg_heal_state_t));
}

/* ------------------------------------------------------------------ Part B: real littlefs, poisoned file */
#define BS 4096
#define NB 512
void *pvPortMalloc(size_t n) { return malloc(n); }
void vPortFree(void *p) { free(p); }
static uint8_t flash[NB * BS];
static int bd_read(const struct lfs_config *c, lfs_block_t b, lfs_off_t off, void *buf, lfs_size_t n)
{ (void)c; memcpy(buf, flash + b * BS + off, n); return 0; }
static int bd_prog(const struct lfs_config *c, lfs_block_t b, lfs_off_t off, const void *buf, lfs_size_t n)
{ (void)c; uint8_t *d = flash + b * BS + off; const uint8_t *s = buf; for (lfs_size_t i = 0; i < n; i++) d[i] &= s[i]; return 0; }
static int bd_erase(const struct lfs_config *c, lfs_block_t b) { (void)c; memset(flash + b * BS, 0xFF, BS); return 0; }
static int bd_sync(const struct lfs_config *c) { (void)c; return 0; }
static uint8_t rb[256], pb[256], la[512 / 8];
static struct lfs_config cfg = {
  .read = bd_read, .prog = bd_prog, .erase = bd_erase, .sync = bd_sync,
  .read_size = 256, .prog_size = 256, .block_size = BS, .block_count = NB, .lookahead = 512,
  .read_buffer = rb, .prog_buffer = pb, .lookahead_buffer = la
};
static lfs_t lfs;
static int append(const char *path, const void *d, uint32_t n)   /* = the sketch's fileAppend (Adafruit FILE_O_WRITE) */
{
  lfs_file_t f;
  if (lfs_file_open(&lfs, &f, path, LFS_O_RDWR | LFS_O_CREAT) < 0) return -1;
  lfs_file_seek(&lfs, &f, 0, LFS_SEEK_END);
  lfs_ssize_t w = lfs_file_write(&lfs, &f, d, n);
  int rc = lfs_file_close(&lfs, &f);
  return (w == (lfs_ssize_t)n && rc == 0) ? 0 : -1;
}
static int cnt_cb(void *p, lfs_block_t b) { (void)b; (*(uint32_t *)p)++; return 0; }
static int used_blocks(void) { uint32_t n = 0; return lfs_traverse(&lfs, cnt_cb, &n) ? -1 : (int)n; }
static uint32_t ctz_index(uint32_t size)   /* lfs.c lfs_ctz_index for 4 KB blocks: index of the block holding byte `size` */
{
  uint32_t b = BS - 2 * 4, i = size / b;
  if (i == 0) return 0;
  return (size - 4 * (__builtin_popcount(i - 1) + 2)) / b;
}
static const char EVLINE[] = "MARK boot=232 t_ms=1852 m=10 name=boot v=232 src=boot unix=0 ................................................"
                             "................................................................................................................"
                             "....................................................\n";   /* 285 B, the bench's evLen */
/* "a boot": mount, append 1 record to the s-file, append the events buffer. Returns 0 ok, 1 events append failed,
 * 2 = aborted (LFS_ASSERT -> abort; on the band: the silent spin until the watchdog). */
static int boot_child(const char *events_path, int appends)
{
  fflush(stdout);
  pid_t pid = fork();
  if (pid == 0) {
    alarm(5);
    if (lfs_mount(&lfs, &cfg)) _exit(3);
    uint8_t rec[24]; memset(rec, 0x11, sizeof rec);
    if (append("/log/s0002.bin", rec, sizeof rec)) _exit(4);
    for (int i = 0; i < appends; i++) if (append(events_path, EVLINE, sizeof EVLINE - 1)) _exit(1);
    lfs_unmount(&lfs);
    _exit(0);
  }
  int st; waitpid(pid, &st, 0);
  if (WIFSIGNALED(st)) return WTERMSIG(st) == SIGABRT ? 2 : 10 + WTERMSIG(st);
  return WEXITSTATUS(st);
}

static void part_b(void)
{
  printf("== B. real littlefs v1.6 (Seeed core copy), poisoned events file ==\n");
  memset(flash, 0xFF, sizeof flash);
  lfs_format(&lfs, &cfg); lfs_mount(&lfs, &cfg); lfs_mkdir(&lfs, "/log");
  uint8_t rec[24];
  for (int i = 0; i < 1616; i++) { memset(rec, i & 0xFF, sizeof rec); append("/log/s0002.bin", rec, sizeof rec); }
  /* events_1.txt grows until its last block is block index 7 (8 blocks), a few hundred bytes before index 8 */
  lfs_file_t f; struct lfs_info info;
  for (;;) {
    lfs_stat(&lfs, "/log/events_1.txt", &info);
    if (lfs_stat(&lfs, "/log/events_1.txt", &info) == 0 && ctz_index(info.size + 3 * (sizeof EVLINE - 1)) >= 8) break;
    append("/log/events_1.txt", EVLINE, sizeof EVLINE - 1);
  }
  lfs_file_open(&lfs, &f, "/log/events_1.txt", LFS_O_RDONLY);
  lfs_block_t head = f.head; uint32_t size = f.size;
  lfs_file_close(&lfs, &f);
  lfs_unmount(&lfs);
  uint32_t idx = ctz_index(size - 1);
  /* walk back to block index 4 through slot 0 (index n -> n-1) */
  lfs_block_t blk = head;
  for (uint32_t k = idx; k > 4; k--) memcpy(&blk, flash + blk * BS, 4);
  /* poison slot 2 of block index 4 (its skip pointer to index 0): read only by lfs_ctz_find/lfs_ctz_extend, never by the
   * allocator's lfs_ctz_traverse (slots 0/1) - the same "one file's skip pointer" damage that the bench pointed at */
  uint32_t bad = 0xFFFFFFFFu; memcpy(flash + blk * BS + 8, &bad, 4);
  printf("      events_1.txt size=%u, last block index %u, poisoned block %u slot 2\n", (unsigned)size, (unsigned)idx, (unsigned)blk);

  lfs_mount(&lfs, &cfg);
  int ub = used_blocks();
  CHECK(ub > 0 && append("/log/s0002.bin", rec, sizeof rec) == 0, "poisoned FS: traversal (free blocks, %d used) and s-file appends still work", ub);
  lfs_unmount(&lfs);

  /* the boot loop: every boot dies at the same events append */
  int r1 = boot_child("/log/events_1.txt", 4), r2 = boot_child("/log/events_1.txt", 4);
  CHECK(r1 == 2 && r2 == 2, "every boot: the events append aborts in LFS_ASSERT (band: silent spin -> watchdog), boot after boot (rc %d, %d)", r1, r2);
  /* reading the poisoned file across the bad pointer aborts too (why a dump read is guarded) */
  fflush(stdout);
  pid_t pid = fork();
  if (pid == 0) {
    alarm(5); lfs_mount(&lfs, &cfg);
    lfs_file_t g; uint8_t b[64];
    if (lfs_file_open(&lfs, &g, "/log/events_1.txt", LFS_O_RDONLY) < 0) _exit(3);
    lfs_file_seek(&lfs, &g, 100, LFS_SEEK_SET);   /* index 0 from the last block: through slot 2 of index 4 */
    lfs_file_read(&lfs, &g, b, sizeof b); _exit(0);
  }
  int st; waitpid(pid, &st, 0);
  CHECK(WIFSIGNALED(st) && WTERMSIG(st) == SIGABRT, "a dump read through the bad pointer aborts the same way");

  /* the heal, as the sketch does it: GPREGRET2 marker ASSERT:events -> hg_heal_* -> guarded remove -> new generation */
  hg_heal_state_init(&S); S.gen = 1;
  hg_heal_begin(&S, &B, 1, hg_heal_marker_encode(HG_CAUSE_ASSERT, HG_FID_EVENTS, 1, 0), BUILD);
  lfs_mount(&lfs, &cfg);
  hg_heal_after_boot(&S, &B, 0, 1, "/log/s0002.bin", "");
  CHECK(strcmp(B.remove_path, "/log/events_1.txt") == 0 && S.gen == 2, "heal plan: remove events_1.txt, live log events_2.txt");
  int used_before = used_blocks();
  int rm = lfs_remove(&lfs, B.remove_path);
  hg_heal_remove_done(&S, &B, rm == 0);
  int used_after = used_blocks();
  CHECK(rm == 0 && used_after < used_before, "remove of the poisoned file works (metadata only, it never walks the bad pointer): %d -> %d blocks", used_before, used_after);
  lfs_unmount(&lfs);
  char ev[24]; hg_heal_events_path(S.gen, ev, sizeof ev);
  int r3 = boot_child(ev, 200);
  CHECK(r3 == 0, "next boot: 200 appends (57 KB, many block crossings) to %s, no abort (rc %d)", ev, r3);
  int r4 = boot_child(ev, 20);
  CHECK(r4 == 0, "and the boot after that (rc %d)", r4);
  /* the children's writes live in their forked copies: now the same boot for real, in this process */
  lfs_mount(&lfs, &cfg);
  memset(rec, 0x11, sizeof rec); int pr = append("/log/s0002.bin", rec, sizeof rec);
  for (int i = 0; i < 200 && !pr; i++) pr = append(ev, EVLINE, sizeof EVLINE - 1);
  lfs_stat(&lfs, ev, &info);
  CHECK(!pr && info.size == 200 * (sizeof EVLINE - 1), "%s holds 200 x 285 B after a real boot", ev);
  lfs_unmount(&lfs);

  lfs_mount(&lfs, &cfg);
  lfs_stat(&lfs, "/log/s0002.bin", &info);
  uint32_t n = info.size / 24, okrec = 0;
  lfs_file_open(&lfs, &f, "/log/s0002.bin", LFS_O_RDONLY);
  for (uint32_t i = 0; i < 1616; i++) { lfs_file_read(&lfs, &f, rec, 24); int good = 1; for (int k = 0; k < 24; k++) if (rec[k] != (uint8_t)(i & 0xFF)) good = 0; okrec += good; }
  lfs_file_close(&lfs, &f);
  CHECK(okrec == 1616 && n == 1616 + 2, "s0002.bin intact through poison + heal: %u of 1616 records + %u boot records", (unsigned)okrec, (unsigned)(n - 1616));
  CHECK(lfs_stat(&lfs, "/log/events_1.txt", &info) == LFS_ERR_NOENT && hg_heal_is_quarantined(&S, "/log/events_1.txt"),
        "events_1.txt gone and quarantined (never opened again, even if the remove had failed)");
  CHECK(used_blocks() > 0, "traversal still fine");
  lfs_unmount(&lfs);
}

/* Part C: the bench sequence on real littlefs: damage that ANY allocation walks (slot 0 of the s-file's last block),
 * so even a brand-new events_1.txt asserts; then the next guarded abort (count 2) re-formats and every write works again. */
static void part_c(void)
{
  printf("== C. real littlefs, damage under the allocator: marker events -> fid=sfile -> format ==\n");
  memset(flash, 0xFF, sizeof flash);
  lfs_format(&lfs, &cfg); lfs_mount(&lfs, &cfg); lfs_mkdir(&lfs, "/log");
  uint8_t rec[24]; memset(rec, 0x22, sizeof rec);
  for (int i = 0; i < 1616; i++) append("/log/s0002.bin", rec, sizeof rec);
  lfs_file_t f; lfs_file_open(&lfs, &f, "/log/s0002.bin", LFS_O_RDONLY); lfs_block_t head = f.head; lfs_file_close(&lfs, &f);
  lfs_unmount(&lfs);
  uint32_t bad = 0xFFFFFFFFu; memcpy(flash + head * BS, &bad, 4);   /* slot 0: read by lfs_ctz_traverse = every lfs_alloc */
  int r1 = boot_child("/log/events_1.txt", 1);
  CHECK(r1 == 2 || r1 == 4, "boot 1: a FRESH events_1.txt write aborts too (the allocator walks the damage) (rc %d)", r1);
  hg_heal_state_init(&S); S.gen = 1;
  hg_heal_begin(&S, &B, 1, hg_heal_marker_encode(HG_CAUSE_ASSERT, HG_FID_EVENTS, 1, 0), BUILD);
  hg_heal_after_boot(&S, &B, 0, 1, "/log/s0002.bin", "");
  int r2 = boot_child("/log/events_2.txt", 1);
  CHECK(r2 == 2 || r2 == 4, "boot 2: quarantine + new generation cannot help, the next write aborts again (rc %d)", r2);
  hg_heal_begin(&S, &B, 0, hg_heal_marker_encode(HG_CAUSE_ASSERT, HG_FID_SFILE, 2, 0), BUILD);   /* 0.9.16: every log call is guarded, so
     the 2nd abort is booked to its file id (0.9.10-0.9.15 saw fid=none here, which 0.9.16 no longer formats on: plan A-24) */
  CHECK(B.format_pre_mount && !B.quarantine_path[0], "boot 3: count 2 -> format before mounting");
  lfs_format(&lfs, &cfg); lfs_mount(&lfs, &cfg); lfs_mkdir(&lfs, "/log"); lfs_unmount(&lfs);
  hg_heal_formatted(&S);
  char ev[24]; hg_heal_events_path(S.gen, ev, sizeof ev);
  int r3 = boot_child(ev, 200);
  CHECK(r3 == 0, "after the format: s-file + 200 events appends to %s, no abort (rc %d)", ev, r3);
  hg_heal_begin(&S, &B, 1, 0x00, BUILD);
  CHECK(!B.format && !B.disable, "next clean boot: no marker, normal");
}

/* Part D (0.9.12): a poisoned InternalFS. Model of the core's flash_nrf5x: one RAM cache page, reads see the cache,
 * the page reaches the flash only at a sync / page change - and with the SoftDevice on, that write can be LOST silently
 * (NRF_EVT_FLASH_OPERATION_ERROR is taken as done). Same lfs v1.6, InternalFS geometry (7 x 4 KB, read = prog = 4 KB).
 * Everything that touches the image runs in a child (it may abort); the image is shared memory. */
#define IBS 4096
#define INB 7
static uint8_t *ifl, icache[IBS]; static int ipage = -1, iflushes = 0; static uint64_t ilose = 0;   /* bit k = flush #k is lost */
static unsigned irs = 0; static int irate = 0;
static void iflush(void) { if (ipage < 0) return; irs = irs * 1103515245u + 12345u;
  int lost = (iflushes < 64 && ((ilose >> iflushes) & 1u)) || (irate && (irs >> 8) % 100 < (unsigned)irate); iflushes++; if (!lost) memcpy(ifl + ipage * IBS, icache, IBS); ipage = -1; }
static void iload(int b) { if (ipage == b) return; iflush(); memcpy(icache, ifl + b * IBS, IBS); ipage = b; }
static int ird(const struct lfs_config *c, lfs_block_t b, lfs_off_t o, void *buf, lfs_size_t n)
{ (void)c; memcpy(buf, ((int)b == ipage ? icache : ifl + b * IBS) + o, n); return 0; }
static int ipr(const struct lfs_config *c, lfs_block_t b, lfs_off_t o, const void *buf, lfs_size_t n) { (void)c; iload((int)b); memcpy(icache + o, buf, n); return 0; }
static int ier(const struct lfs_config *c, lfs_block_t b) { (void)c; iload((int)b); memset(icache, 0xFF, IBS); return 0; }
static int isy(const struct lfs_config *c) { (void)c; iflush(); return 0; }
static struct lfs_config icfg = { .read = ird, .prog = ipr, .erase = ier, .sync = isy, .read_size = IBS, .prog_size = IBS,
  .block_size = IBS, .block_count = INB, .lookahead = 128 };
static lfs_t ilfs;
static uint8_t IPROF[28];
static int isave(const char *p, const void *d, int n)
{ lfs_file_t f; if (lfs_file_open(&ilfs, &f, p, LFS_O_RDWR | LFS_O_CREAT) < 0) return -1;
  lfs_file_truncate(&ilfs, &f, 0); lfs_file_write(&ilfs, &f, d, n); return lfs_file_close(&ilfs, &f); }
static int iread(const char *p, void *d, int n)
{ lfs_file_t f; if (lfs_file_open(&ilfs, &f, p, LFS_O_RDONLY) < 0) return -1; int r = lfs_file_read(&ilfs, &f, d, n); lfs_file_close(&ilfs, &f); return r; }
/* run one job in a child: 0 ok, 1 job said no, 2 aborted in LFS_ASSERT, 3 other death */
static int ichild(int job, uint64_t arg)
{
  fflush(stdout); pid_t pid = fork();
  if (pid == 0) {
    alarm(5); uint8_t b[900]; memset(b, 0x5A, sizeof b); ipage = -1; iflushes = 0; ilose = 0;
    if (job == 0) {            /* build: profile + twin + eco + heal state, then saves while the phone is connected, flush #arg lost */
      memset(ifl, 0xFF, INB * IBS); lfs_format(&ilfs, &icfg); lfs_mount(&ilfs, &icfg);
      isave("/profile.bin", IPROF, 28); isave("/twin.bin", b, 214);
      if (!(arg >> 32)) { isave("/dayplan.bin", b, 400); isave("/fsheal.bin", b, 176); }   /* random-loss runs create them while losing */
      iflush(); iflushes = 0; ilose = arg >> 32 ? 0 : arg; if (arg >> 32) { irs = (unsigned)(arg >> 32); irate = 50; }
      for (int k = 0; k < (irate ? 60 : 12); k++) isave(k % 3 == 0 ? "/twin.bin" : k % 3 == 1 ? "/dayplan.bin" : "/fsheal.bin", b, k % 3 == 0 ? 214 : k % 3 == 1 ? 400 : 176);
      ilose = 0; irate = 0; iflush(); _exit(0);
    }
    if (job == 1) {            /* a boot's InternalFS work */
      if (lfs_mount(&ilfs, &icfg)) _exit(1);
      iread("/profile.bin", b, 28); iread("/twin.bin", b, 214); iread("/dayplan.bin", b, 400); iread("/fsheal.bin", b, 176);
      for (int k = 0; k < 6; k++) { if (isave("/fsheal.bin", b, 176) || isave("/dayplan.bin", b, 400) || isave("/twin.bin", b, 214)) _exit(1); }
      iflush(); _exit(0);
    }
    if (job == 2) {            /* the ladder's format: profile into RAM (guarded read), format ONLY InternalFS, profile back */
      uint8_t r[28]; int g = -1;
      fflush(stdout); pid_t rp = fork();   /* the backup read may itself die: then the profile is lost, the format still runs */
      if (rp == 0) { alarm(5); if (!lfs_mount(&ilfs, &icfg) && iread("/profile.bin", r, 28) == 28 && !memcmp(r, IPROF, 28)) _exit(0); _exit(1); }
      int st; waitpid(rp, &st, 0); g = WIFEXITED(st) && !WEXITSTATUS(st);
      memset(ifl, 0xFF, INB * IBS); ipage = -1;
      lfs_format(&ilfs, &icfg); lfs_mount(&ilfs, &icfg);
      if (g) isave("/profile.bin", IPROF, 28);
      iflush(); _exit(g ? 0 : 1);
    }
    if (job == 3) {            /* the profile reads back */
      uint8_t r[28]; if (lfs_mount(&ilfs, &icfg) || iread("/profile.bin", r, 28) != 28 || memcmp(r, IPROF, 28)) _exit(1); _exit(0);
    }
    _exit(9);
  }
  int st; waitpid(pid, &st, 0);
  if (WIFSIGNALED(st)) return WTERMSIG(st) == SIGABRT ? 2 : 3;
  return WEXITSTATUS(st) == 0 ? 0 : 1;
}
static void part_d(void)
{
  printf("== D. 0.9.12 poisoned InternalFS (silently lost flash page writes) -> ladder ==\n");
  for (int i = 0; i < 28; i++) IPROF[i] = (uint8_t)(0x40 + i);
  ifl = mmap(NULL, INB * IBS, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
  if (ifl == MAP_FAILED) { CHECK(0, "mmap"); return; }
  CHECK(ichild(0, 0) == 0 && ichild(1, 0) == 0, "healthy InternalFS: build + a boot's loads/saves run clean");
  int found = -1, lost_ok = 0;   /* single lost page writes first, then pairs (deterministic order) */
  for (int k = 0; k < 40 && found < 0; k++) {
    if (ichild(0, 1ull << k) != 0) continue;
    int r = ichild(1, 0);
    if (r == 2) found = k; else if (r == 0) lost_ok++;
  }
  for (int k = 0; k < 40 && found < 0; k++) for (int m = k + 1; m < 40 && found < 0; m++) {
    if (ichild(0, (1ull << k) | (1ull << m)) != 0) continue;
    int r = ichild(1, 0);
    if (r == 2) found = k * 100 + m; else if (r == 0) lost_ok++;
  }
  /* single and paired losses are survived by littlefs (it falls back to the older metadata copy); a phone connection
     that keeps dropping page writes (50 %, 60 saves) eventually is not: deterministic seeds */
  int seed = -1;
  int during = 0;
  for (unsigned sd = 1; sd < 2000 && found < 0; sd++) {
    int rb = ichild(0, (uint64_t)sd << 32);
    if (rb == 2) { found = 0; seed = (int)sd; during = 1; break; }   /* asserted inside a save (the band: an FS-GUARD reset) */
    if (rb == 0 && ichild(1, 0) == 2) { found = 0; seed = (int)sd; }
  }
  CHECK(found >= 0, "silently lost page writes make littlefs assert on InternalFS %s: the bench 'last=ASSERT:ifs' (seed %d; %d single/paired losses were survived)",
        during ? "during a save" : "on the next boot", seed, lost_ok);
  if (found < 0) return;
  const char *pp[3];
  int a1 = hg_heal_ifs_plan(HG_FID_IFS_ECO, 1, 0, pp, 3);
  CHECK(a1 == HG_IFS_REMOVE && pp[0] && pp[1] && pp[2] && !strcmp(pp[2], "/dayplan.bin"), "ifs fault 1 (eco) -> remove famname/routine/dayplan");
  int a1b = hg_heal_ifs_plan(HG_FID_IFS_TWIN, 1, 0, pp, 3);
  CHECK(a1b == HG_IFS_REMOVE && !strcmp(pp[0], "/twin.bin") && !pp[1], "ifs fault 1 (twin) -> remove /twin.bin only");
  CHECK(hg_heal_ifs_plan(HG_FID_IFS_TWIN, 1, HG_FID_IFS_TWIN, pp, 3) == HG_IFS_FORMAT, "the same file failing again later -> format, never a 2nd remove-and-reset");
  CHECK(hg_heal_ifs_plan(HG_FID_IFS_HEAL, 1, 0, pp, 3) == HG_IFS_FORMAT && !pp[0],
        "0.9.13: InternalFS itself (mount/format, the old /fsheal.bin) asserting -> format + profile restore at once");
  CHECK(hg_heal_ifs_plan(HG_FID_IFS_ECO, 2, 0, pp, 3) == HG_IFS_FORMAT && hg_heal_ifs_plan(HG_FID_IFS_ECO, 3, 0, pp, 3) == HG_IFS_OFF &&
        hg_heal_ifs_plan(HG_FID_EVENTS, 2, 0, pp, 3) == HG_IFS_NONE, "2nd in a row -> format InternalFS, 3rd -> InternalFS off; QSPI ids are not InternalFS");
  hg_heal_state_init(&S); S.gen = 5;
  hg_heal_begin(&S, &B, 1, hg_heal_marker_encode(HG_CAUSE_ASSERT, HG_FID_IFS_ECO, 2, 0), BUILD);
  CHECK(B.ifs_action == HG_IFS_FORMAT && !B.format && !B.format_pre_mount && !B.disable && S.streak == 0,
        "an InternalFS marker never formats or switches off the QSPI log, and is not in its streak");
  int fr = ichild(2, 0);
  CHECK(fr == 0 || fr == 1, "the ladder's InternalFS format runs on the poisoned image (profile backup %s)", fr == 0 ? "read OK" : "not readable: defaults");
  CHECK(ichild(1, 0) == 0 && ichild(1, 0) == 0, "after the InternalFS format: two boots of loads/saves run clean");
  if (fr == 0) CHECK(ichild(3, 0) == 0, "the wearer's profile (age/sex/bmi/med) survived the InternalFS format");
}

int main(void)
{
  part_a();
  part_b();
  part_c();
  part_d();
  printf("TEST_HEAL: %d passed, %d failed\n", passes, fails);
  return fails ? 1 : 0;
}
