/* B1 regression test (T6a blocker): a run of resets must never delete undumped 1 Hz history.
 *   gcc -std=c99 -Wall -Wextra -Werror -I../08_logger test_reboot.c ../08_logger/log_ring.c -o /tmp/test_reboot && /tmp/test_reboot
 * Start: the 3-day steady state (17 full hour files + min/events/boot, as in test_lfs_host / T6a).
 * Model A (the tester's model, worst case): EVERY boot makes a new short file and runs the plan.
 * Model B (the sketch since [B6a-fix]): at boot hg_ring_boot_file() says "append to the newest hour
 *   file" unless it is full; the plan only runs when a file is full.
 * Pass = model B loses 0 full hour files and the 1 Hz seconds kept never go down, for 5..60 resets.
 * Model A is printed for information (it is what the pre-fix sketch did; with a near-full flash any
 * scheme that adds a file per boot must delete something). Build with -DOLD_API against the pre-fix
 * log_ring.c (git show da256d5:fw/08_logger/log_ring.c) to see the failure the fix removes: the
 * pre-fix build counts model A and FAILS (17 h lost at 20 resets).
 */
#include <stdio.h>
#include <string.h>
#include "log_ring.h"
#ifndef HG_HOUR_FILE_BYTES
#define HG_HOUR_FILE_BYTES (24u + 3600u * 24u)
#endif

static hg_logfile_t f[HG_RING_MAX_FILES]; static int n;
static int fails = 0;
static uint32_t used_blocks(void) { uint32_t u = 6; for (int i = 0; i < n; i++) u += hg_ring_blocks_for(f[i].size, 4096); return u; }
static void start(void)
{
  n = 0;
  for (int i = 0; i < 17; i++) { f[n].kind = 's'; f[n].seq = (uint16_t)i; f[n].size = 86424; n++; }
  f[n].kind = 'm'; f[n].seq = 0; f[n].size = 70000; n++;
  f[n].kind = 'e'; f[n].seq = 0; f[n].size = 20000; n++;
  f[n].kind = 'b'; f[n].seq = 0; f[n].size = 24; n++;
}
static long make_room(void)
{
  int del[HG_RING_MAX_FILES]; long lost = 0;
  uint32_t u = used_blocks(), fb = u >= 512 ? 0 : 512 - u;
  int nd = hg_ring_plan(f, n, fb, 4096, HG_RING_MARGIN_BLOCKS, HG_RING_MAX_S_FILES, del, HG_RING_MAX_FILES);
  for (int a = 0; a < nd; a++) for (int b = a + 1; b < nd; b++) if (del[b] > del[a]) { int t = del[a]; del[a] = del[b]; del[b] = t; }
  for (int i = 0; i < nd; i++) { if (f[del[i]].kind == 's' && f[del[i]].size >= HG_HOUR_FILE_BYTES) lost++; f[del[i]] = f[--n]; }
  return lost;
}
static uint32_t secs_kept(void) { uint32_t s = 0; for (int i = 0; i < n; i++) if (f[i].kind == 's') s += (f[i].size / 24u) - 1u; return s; }

static void scenario(char model, int resets, uint32_t secs)
{
  start();
  uint16_t next = 17; long lost = 0; uint32_t before = secs_kept();
  for (int r = 0; r < resets; r++) {
    int append = 0; uint16_t seq = 0;
#ifndef OLD_API
    if (model == 'B') append = hg_ring_boot_file(f, n, HG_HOUR_FILE_BYTES, &seq);
#endif
    if (append) {
      for (int i = 0; i < n; i++) if (f[i].kind == 's' && f[i].seq == seq) { f[i].size += 24u + 24u * secs; if (f[i].size > HG_HOUR_FILE_BYTES + 24u * 60u) f[i].size = HG_HOUR_FILE_BYTES; }
    } else {
      lost += make_room();
      f[n].kind = 's'; f[n].seq = hg_ring_next_seq(f, n, next); next = (uint16_t)(f[n].seq + 1); f[n].size = 24u + 24u * secs; n++;
    }
  }
  uint32_t after = secs_kept();
  int ok = lost == 0 && after >= before;
#ifdef OLD_API
  int counted = 1;
#else
  int counted = (model == 'B');
#endif
  if (!ok && counted) fails++;
  printf("%s model %c %3d resets x %4u s: full hour files lost %ld, 1 Hz seconds kept %u -> %u\n",
         counted ? (ok ? "PASS" : "FAIL") : "INFO", model, resets, secs, lost, before, after);
}

int main(void)
{
  int R[] = {5, 20, 30, 60}; uint32_t S[] = {10, 10, 60, 8};
  for (int i = 0; i < 4; i++) scenario('A', R[i], S[i]);
#ifndef OLD_API
  for (int i = 0; i < 4; i++) scenario('B', R[i], S[i]);
  /* boot-file rule details */
  hg_logfile_t g[3] = { {'s', 4, 1000}, {'s', 5, 2000}, {'m', 0, 10} }; uint16_t q = 0;
  if (!(hg_ring_boot_file(g, 3, HG_HOUR_FILE_BYTES, &q) == 1 && q == 5)) { fails++; printf("FAIL boot_file picks newest\n"); }
  g[1].size = HG_HOUR_FILE_BYTES;
  if (hg_ring_boot_file(g, 3, HG_HOUR_FILE_BYTES, &q) != 0) { fails++; printf("FAIL boot_file full -> new\n"); }
  hg_logfile_t h[2] = { {'s', 5, 2000}, {'r', 6, 184800} };
  if (hg_ring_boot_file(h, 2, HG_HOUR_FILE_BYTES, &q) != 0) { fails++; printf("FAIL boot_file after raw -> new\n"); }
#endif
  printf("%s\n", fails ? "TEST_REBOOT: FAIL" : "TEST_REBOOT: PASS");
  return fails ? 1 : 0;
}
