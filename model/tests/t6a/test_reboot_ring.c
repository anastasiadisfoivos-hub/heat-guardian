/* T6a: what a run of resets does to the 1 Hz ring (log_ring.c, the code the sketch uses).
 * The sketch calls newHourFile() -> ringMakeRoom(HG_RING_MARGIN_BLOCKS, HG_RING_MAX_S_FILES) in EVERY
 * setup(), so every boot creates a new s-file. The ring keeps at most 20 s-files BY COUNT.
 * Start: the steady state of the builder's 3-day littlefs run (17 full hour files + min/events/boot).
 * Then R resets, each running for `secs` seconds before the next reset (brown-out loop, WDT loop).
 *   cc -std=c99 -I../../fw/08_logger test_reboot_ring.c ../../fw/08_logger/log_ring.c -o /tmp/rr && /tmp/rr
 */
#include <stdio.h>
#include <string.h>
#include "log_ring.h"

static hg_logfile_t f[HG_RING_MAX_FILES]; static int n;
static uint32_t used_blocks(void) { uint32_t u = 4; for (int i = 0; i < n; i++) u += hg_ring_blocks_for(f[i].size, 4096); return u; }

static void scenario(int resets, uint32_t secs)
{
  n = 0; uint16_t seq = 0;
  for (int i = 0; i < 17; i++) { f[n].kind = 's'; f[n].seq = seq++; f[n].size = 86424; n++; }
  f[n].kind = 'm'; f[n].size = 70000; n++; f[n].kind = 'e'; f[n].size = 20000; n++; f[n].kind = 'b'; f[n].size = 24; n++;
  long full_before = 17, full_lost = 0;
  for (int r = 0; r < resets; r++) {
    int del[HG_RING_MAX_FILES];
    uint32_t freeb = 512 - used_blocks();
    int nd = hg_ring_plan(f, n, freeb, 4096, HG_RING_MARGIN_BLOCKS, HG_RING_MAX_S_FILES, del, HG_RING_MAX_FILES);
    /* remove in descending index order */
    for (int a = 0; a < nd; a++) for (int b = a + 1; b < nd; b++) if (del[b] > del[a]) { int t = del[a]; del[a] = del[b]; del[b] = t; }
    for (int i = 0; i < nd; i++) { if (f[del[i]].kind == 's' && f[del[i]].size >= 86424) full_lost++; f[del[i]] = f[--n]; }
    f[n].kind = 's'; f[n].seq = hg_ring_next_seq(f, n, seq); seq = f[n].seq + 1; f[n].size = 24 + 24 * secs; n++;
  }
  int full_left = 0; uint32_t sec_left = 0;
  for (int i = 0; i < n; i++) if (f[i].kind == 's') { if (f[i].size >= 86424) full_left++; sec_left += (f[i].size - 24) / 24; }
  printf("%3d resets, %5u s between resets: full hour files %ld -> %d (lost %ld h of 1 Hz data); 1 Hz seconds kept on flash: %u (%.1f h)\n",
         resets, secs, full_before, full_left, full_lost, sec_left, sec_left / 3600.0);
}

int main(void)
{
  scenario(5, 10); scenario(20, 10); scenario(30, 10); scenario(30, 60); scenario(60, 8);
  return 0;
}
