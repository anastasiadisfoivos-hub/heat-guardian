/* Host test for fw/08_logger/log_ring.c with a mock filesystem (acceptance 4 of brief B6 Part A).
 *   gcc -std=c99 -Wall -Wextra -Werror -O2 -I../08_logger test_ring.c ../08_logger/log_ring.c -o /tmp/test_ring && /tmp/test_ring
 * Mock FS: 512 blocks x 4 KB (the XIAO's 2 MB P25Q16H); a file of n bytes uses hg_ring_blocks_for(n)
 * blocks; directories/metadata cost 6 blocks. The sketch's rotation is replayed for 7 days:
 *   every minute: +1440 B to the current s-file, +24 B to min.bin, sometimes +events text
 *   every 3600 records: plan -> delete -> next seq -> create the next s-file (with its 24-B header)
 *   two raw captures (180 KB each) on day 1 and day 2.
 * Checks: names; classification; never > 20 s-files after creation; deletions strictly oldest
 * first; min.bin / events.txt / boot.bin never deleted; free blocks never negative (no write would
 * fail for lack of space); sequence numbers strictly increasing; next_seq survives "reboots".
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "log_ring.h"

#define BS 4096u
#define NBLK 512u
#define META 6u

static hg_logfile_t fs[HG_RING_MAX_FILES]; static int nfs = 0;
static int fails = 0;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL: " __VA_ARGS__); printf("\n"); } } while (0)

static uint32_t used_blocks(void) { uint32_t u = META; for (int i = 0; i < nfs; i++) u += fs[i].size ? hg_ring_blocks_for(fs[i].size, BS) : 1; return u; }
static int32_t free_blocks(void) { return (int32_t)NBLK - (int32_t)used_blocks(); }
static int find(char k, uint16_t seq) { for (int i = 0; i < nfs; i++) if (fs[i].kind == k && (k == 'm' || k == 'e' || k == 'b' || fs[i].seq == seq)) return i; return -1; }
static void add(char k, uint16_t seq, uint32_t size) { fs[nfs].kind = k; fs[nfs].seq = seq; fs[nfs].size = size; nfs++; }
static void del(int i) { fs[i] = fs[--nfs]; }
static int count_s(void) { int c = 0; for (int i = 0; i < nfs; i++) if (fs[i].kind == 's') c++; return c; }

static uint16_t stored_next = 0;
static long last_deleted_seq = -1;
static int deletions = 0;
static int32_t min_free_seen = 1 << 30;

static void make_room(uint32_t need, int max_s)
{
  int idx[HG_RING_MAX_FILES];
  uint32_t fb = free_blocks() > 0 ? (uint32_t)free_blocks() : 0;
  int nd = hg_ring_plan(fs, nfs, fb, BS, need, max_s, idx, HG_RING_MAX_FILES);
  /* deletions must be oldest-first among deletable files */
  for (int i = 0; i < nd; i++) {
    hg_logfile_t f = fs[idx[i]];
    CHECK(f.kind == 's' || f.kind == 'r', "plan selected non-deletable kind %c", f.kind);
    for (int j = 0; j < nfs; j++) {
      int chosen = 0; for (int q = 0; q < nd; q++) if (idx[q] == j) chosen = 1;
      if (!chosen && (fs[j].kind == 's' || (fs[j].kind == 'r' && free_blocks() < (int32_t)need)) && fs[j].seq < f.seq && f.kind == fs[j].kind)
        CHECK(0, "kept older %c%04u while deleting %c%04u", fs[j].kind, fs[j].seq, f.kind, f.seq);
    }
    CHECK((long)f.seq > last_deleted_seq || f.kind == 'r', "deletion order went backwards (%u after %ld)", f.seq, last_deleted_seq);
    if (f.kind == 's') last_deleted_seq = f.seq;
  }
  /* delete highest index first so indices stay valid */
  for (int a = 0; a < nd; a++) for (int b = a + 1; b < nd; b++) if (idx[b] > idx[a]) { int t = idx[a]; idx[a] = idx[b]; idx[b] = t; }
  for (int i = 0; i < nd; i++) { del(idx[i]); deletions++; }
}
static uint16_t take_seq(void)
{
  uint16_t s = hg_ring_next_seq(fs, nfs, stored_next);
  stored_next = (uint16_t)((s + 1) % HG_SEQ_MOD);
  return s;
}

int main(void)
{
  /* names and classification */
  char p[24]; uint16_t q = 0;
  hg_ring_make_path('s', 12, p, sizeof p); CHECK(strcmp(p, "/log/s0012.bin") == 0, "make_path %s", p);
  hg_ring_make_path('r', 10012, p, sizeof p); CHECK(strcmp(p, "/log/r0012.bin") == 0, "make_path mod %s", p);
  CHECK(hg_ring_classify("s0012.bin", &q) == 's' && q == 12, "classify s");
  CHECK(hg_ring_classify("r9999.bin", &q) == 'r' && q == 9999, "classify r");
  CHECK(hg_ring_classify("min.bin", &q) == 'm', "classify min");
  CHECK(hg_ring_classify("events.txt", &q) == 'e', "classify events");
  CHECK(hg_ring_classify("boot.bin", &q) == 'b', "classify boot");
  CHECK(hg_ring_classify("s12.bin", &q) == '?', "classify short");
  CHECK(hg_ring_classify("s0012.binx", &q) == '?', "classify long");
  CHECK(hg_ring_classify("x0012.bin", &q) == '?', "classify other");
  CHECK(hg_ring_blocks_for(86400 + 24, BS) == 23, "blocks_for hour file = %u", hg_ring_blocks_for(86400 + 24, BS));

  /* 7-day replay */
  add('b', 0, 24); add('e', 0, 0); add('m', 0, 0);
  int cur = -1; uint16_t cur_seq = 0; uint32_t recs = 0; long last_seq = -1;
  int max_s_seen = 0;
  for (uint32_t minute = 0; minute < 7u * 1440u; minute++) {
    if (cur < 0 || recs >= 3600) {
      make_room(HG_RING_MARGIN_BLOCKS, HG_RING_MAX_S_FILES);
      cur_seq = take_seq();
      CHECK((long)cur_seq > last_seq, "seq not increasing %u", cur_seq);
      last_seq = cur_seq;
      add('s', cur_seq, 24); recs = 0;
      if (count_s() > max_s_seen) max_s_seen = count_s();
      CHECK(count_s() <= HG_RING_MAX_S_FILES, "%d s-files", count_s());
    }
    if (minute == 600 || minute == 2000) {          /* raw capture of 600 s = 180,000 B + headers */
      make_room(HG_RING_RAW_BLOCKS, HG_RING_MAX_S_FILES + 1);
      uint16_t rs = take_seq(); last_seq = rs;
      add('r', rs, 600u * 308u);
    }
    if (minute == 3000) { stored_next = (uint16_t)hg_ring_next_seq(fs, nfs, stored_next); } /* "reboot": seq restored */
    cur = find('s', cur_seq);
    CHECK(cur >= 0, "current file vanished at minute %u", minute);
    fs[cur].size += 60u * 24u; recs += 60;
    fs[find('m', 0)].size += 24u;
    if (minute % 30 == 0) fs[find('e', 0)].size += 80u;
    int32_t fb = free_blocks();
    if (fb < min_free_seen) min_free_seen = fb;
    CHECK(fb >= 0, "out of space at minute %u (free %d)", minute, fb);
  }
  CHECK(find('m', 0) >= 0 && find('e', 0) >= 0 && find('b', 0) >= 0, "a permanent file was deleted");
  printf("7-day replay: %d deletions, max s-files %d, min free blocks %d of %u, min.bin %u B, final files %d\n",
         deletions, max_s_seen, min_free_seen, NBLK, fs[find('m', 0)].size, nfs);

  /* plan corner cases */
  {
    hg_logfile_t f[3] = { {'m', 0, 500000}, {'e', 0, 1000}, {'b', 0, 24} };
    int idx[4]; int nd = hg_ring_plan(f, 3, 0, BS, 40, 20, idx, 4);
    CHECK(nd == 0, "plan deleted a permanent file (nd=%d)", nd);
  }
  {
    hg_logfile_t f[4] = { {'s', 5, 86424}, {'s', 3, 86424}, {'r', 4, 184800}, {'s', 7, 86424} };
    int idx[4]; int nd = hg_ring_plan(f, 4, 0, BS, 40, 20, idx, 4);   /* need space: 3 (23) then r4 (47) */
    CHECK(nd == 2 && f[idx[0]].seq == 3 && f[idx[1]].seq == 4, "space plan order (nd=%d)", nd);
    nd = hg_ring_plan(f, 4, 100, BS, 40, 3, idx, 4);                    /* listing cap only (s+r < 3): two oldest */
    CHECK(nd == 2 && f[idx[0]].seq == 3 && f[idx[1]].seq == 4, "cap plan (nd=%d)", nd);
  }
  printf("%s\n", fails ? "TEST_RING: FAIL" : "TEST_RING: PASS");
  return fails ? 1 : 0;
}
