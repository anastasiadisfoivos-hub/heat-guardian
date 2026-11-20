/* T6a-r2: resets vs the 1 Hz ring, v1.1.0 boot path, on the REAL littlefs v1.6 (Seeed core copy).
 * Mirrors 08_logger.ino v1.1.0: storageInit -> bootHourFile() (append a boot header to the newest
 * s-file if it is < HG_HOUR_FILE_BYTES, else newHourFile), flushAll() every 60 s (secBuf -> hour file,
 * min.bin every 10 min, events), newHourFile() at 3600 records with ringMakeRoom(64 blocks, 100 files),
 * the GPREGRET2 boot-loop hold (>= 3 boots in a row with uptime < 10 min -> no deletions for 30 min;
 * GPREGRET2 is cleared by a brown-out/power-on reset, so a brown-out loop gets NO hold).
 * A reset loses the RAM buffers (<= 60 s of 1 Hz records, <= 10 min of minute records).
 * Every 1 Hz record carries a global sequence number in t1 (truth), so at the end I count exactly
 * which seconds survive: retained span, holes inside it, and records lost to a full flash.
 *   cc -std=gnu99 -O2 -w -I../../fw/08_logger -I$LFS test_reboot_v110.c $LFS/lfs.c $LFS/lfs_util.c \
 *      ../../fw/08_logger/log_ring.c -o /tmp/rb && /tmp/rb
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "lfs.h"
#include "log_format.h"
#include "log_ring.h"

#define BS 4096
#define NB 512
void *pvPortMalloc(size_t n) { return malloc(n); }
void vPortFree(void *p) { free(p); }
static uint8_t flash[NB * BS];
static int bd_read(const struct lfs_config *c, lfs_block_t b, lfs_off_t o, void *buf, lfs_size_t n) { (void)c; memcpy(buf, flash + b * BS + o, n); return 0; }
static int bd_prog(const struct lfs_config *c, lfs_block_t b, lfs_off_t o, const void *buf, lfs_size_t n)
{ (void)c; uint8_t *d = flash + b * BS + o; const uint8_t *s = buf; for (lfs_size_t i = 0; i < n; i++) d[i] &= s[i]; return 0; }
static int bd_erase(const struct lfs_config *c, lfs_block_t b) { (void)c; memset(flash + b * BS, 0xFF, BS); return 0; }
static int bd_sync(const struct lfs_config *c) { (void)c; return 0; }
static uint8_t rb[256], pb[256], la[64];
static struct lfs_config cfg = { .read = bd_read, .prog = bd_prog, .erase = bd_erase, .sync = bd_sync, .read_size = 256,
  .prog_size = 256, .block_size = BS, .block_count = NB, .lookahead = 512, .read_buffer = rb, .prog_buffer = pb, .lookahead_buffer = la };
static lfs_t lfs;

static int append(const char *p, const void *d, uint32_t n)
{ lfs_file_t f; if (lfs_file_open(&lfs, &f, p, LFS_O_RDWR | LFS_O_CREAT | LFS_O_APPEND) < 0) return -1;
  lfs_ssize_t w = lfs_file_write(&lfs, &f, d, n); int rc = lfs_file_close(&lfs, &f); return (w == (lfs_ssize_t)n && rc == 0) ? 0 : -1; }
static int cnt_cb(void *p, lfs_block_t b) { (void)b; (*(uint32_t *)p)++; return 0; }
static uint32_t free_blocks(void) { uint32_t n = 0; lfs_traverse(&lfs, cnt_cb, &n); return n >= NB ? 0 : NB - n; }
static hg_logfile_t files[HG_RING_MAX_FILES]; static char names[HG_RING_MAX_FILES][16]; static int nfiles;
static void list_log(void)
{ lfs_dir_t d; struct lfs_info info; nfiles = 0; if (lfs_dir_open(&lfs, &d, "/log") < 0) return;
  while (lfs_dir_read(&lfs, &d, &info) > 0 && nfiles < HG_RING_MAX_FILES) { if (info.name[0] == '.') continue; uint16_t q = 0;
    files[nfiles].kind = hg_ring_classify(info.name, &q); files[nfiles].seq = q; files[nfiles].size = info.size;
    snprintf(names[nfiles], 16, "%.15s", info.name); nfiles++; }
  lfs_dir_close(&lfs, &d); }

/* ---- sketch state ---- */
static uint16_t next_seq = 0; static int bootloop = 0; static uint32_t uptime_ms = 0;
static char cur[32]; static uint32_t recs_in_file; static uint32_t boot = 0;
static uint8_t secbuf[70 * 24]; static int secn = 0; static uint8_t minbuf[14 * 24]; static int minn = 0;
static long truth = 0, lost_full = 0, lost_ram = 0, deletes = 0, holds = 0;

static void make_room(void)
{ if (bootloop) { holds++; return; }
  list_log(); int idx[HG_RING_MAX_FILES];
  int nd = hg_ring_plan(files, nfiles, free_blocks(), BS, HG_RING_MARGIN_BLOCKS, HG_RING_MAX_S_FILES, idx, HG_RING_MAX_FILES);
  for (int i = 0; i < nd; i++) { char p[32]; snprintf(p, sizeof p, "/log/%s", names[idx[i]]); if (lfs_remove(&lfs, p) == 0) deletes++; } }
static void header(void) { hg_rec_t r; memset(&r, 0, sizeof r); r.t_ms = uptime_ms; r.marker = HG_M_FILE; r.flags = HG_F_MARKER; r.aux = (uint16_t)boot;
  uint8_t b[24]; hg_rec_pack(&r, b); append(cur, b, 24); }
static void new_hour_file(void)
{ make_room(); list_log(); uint16_t s = hg_ring_next_seq(files, nfiles, next_seq); next_seq = (uint16_t)(s + 1);
  hg_ring_make_path('s', s, cur, sizeof cur); header(); recs_in_file = 0; }
static void boot_hour_file(void)
{ list_log(); uint16_t s;
  if (!hg_ring_boot_file(files, nfiles, HG_HOUR_FILE_BYTES, &s)) { new_hour_file(); return; }
  hg_ring_make_path('s', s, cur, sizeof cur);
  uint32_t size = 0; for (int i = 0; i < nfiles; i++) if (files[i].kind == 's' && files[i].seq == s) size = files[i].size;
  header(); recs_in_file = size / 24; }
static void flush_all(void)
{ if (secn) { if (append(cur, secbuf, secn * 24) == 0) recs_in_file += secn; else lost_full += secn; secn = 0; }
  if (minn >= 10) { append("/log/min.bin", minbuf, minn * 24); minn = 0; }
  if (recs_in_file >= 3600) new_hour_file(); }
static void do_boot(int quick_boots)
{ memset(&lfs, 0, sizeof lfs); if (lfs_mount(&lfs, &cfg)) { printf("MOUNT FAIL\n"); exit(2); }
  boot++; uptime_ms = 0; bootloop = quick_boots >= 3; secn = 0; minn = 0; boot_hour_file(); flush_all(); }
static void run_seconds(long secs)
{ for (long i = 0; i < secs; i++) {
    hg_rec_t r; memset(&r, 0, sizeof r); r.t_ms = uptime_ms; r.t1_c100 = (int16_t)(truth & 0x7FFF); r.t2_c100 = (int16_t)(truth >> 15);
    uint8_t b[24]; hg_rec_pack(&r, b); memcpy(secbuf + 24 * secn++, b, 24); truth++;
    uptime_ms += 1000;
    if (uptime_ms % 60000 == 0) { memcpy(minbuf + 24 * minn++, b, 24); flush_all(); }
    if (bootloop && uptime_ms >= 30u * 60u * 1000u) bootloop = 0;
  } }
static void reset_now(void) { lost_ram += secn; secn = 0; /* no unmount: power just goes */ }

static unsigned char *seen; static long nseen;
static void audit(const char *name)
{ memset(seen, 0, nseen); list_log(); long kept = 0, crc_bad = 0;
  for (int i = 0; i < nfiles; i++) { if (files[i].kind != 's') continue; char p[32]; snprintf(p, sizeof p, "/log/%s", names[i]);
    lfs_file_t f; lfs_file_open(&lfs, &f, p, LFS_O_RDONLY); uint8_t b[24]; hg_rec_t r;
    while (lfs_file_read(&lfs, &f, b, 24) == 24) { if (!hg_rec_unpack(b, &r)) { crc_bad++; continue; } if (r.marker == HG_M_FILE) continue;
      long t = (uint16_t)r.t1_c100 | ((long)(uint16_t)r.t2_c100 << 15); if (t < nseen && !seen[t]) { seen[t] = 1; kept++; } }
    lfs_file_close(&lfs, &f); }
  long first = -1; for (long t = 0; t < truth; t++) if (seen[t]) { first = t; break; }
  long holes = 0; for (long t = first; t >= 0 && t < truth; t++) if (!seen[t]) holes++;
  printf("%-46s boots %4u | 1 Hz kept %6ld s = %5.1f h, newest-%5.1f h..now | holes inside span %5ld s (reset RAM loss %ld, full-flash loss %ld) | deletes %ld, held %ld | CRC bad %ld\n",
         name, boot, kept, kept / 3600.0, (truth - first) / 3600.0, holes, lost_ram, lost_full, deletes, holds, crc_bad); }

static void fresh(void) { memset(flash, 0xFF, sizeof flash); memset(&lfs, 0, sizeof lfs); lfs_format(&lfs, &cfg); lfs_mount(&lfs, &cfg); lfs_mkdir(&lfs, "/log");
  next_seq = 0; truth = 0; boot = 0; lost_full = lost_ram = deletes = holds = 0; cur[0] = 0; }

int main(void)
{
  nseen = 4L * 86400L; seen = malloc(nseen);
  /* A: baseline, no resets, 3 days */
  fresh(); do_boot(1); run_seconds(3L * 86400L); audit("A baseline 3 days, no resets");
  /* B: 2.5 days, then a watchdog loop: 60 resets every 8 s (GPREGRET2 counts -> hold after 3) */
  fresh(); do_boot(1); run_seconds(60L * 3600L);
  for (int k = 0; k < 60; k++) { reset_now(); do_boot(k + 2); run_seconds(8); } audit("B 2.5 d + 60 WDT resets x 8 s (hold active)");
  /* C: 2.5 days, then a brown-out loop: 200 resets every 30 s, GPREGRET2 cleared -> NO hold */
  fresh(); do_boot(1); run_seconds(60L * 3600L);
  for (int k = 0; k < 200; k++) { reset_now(); do_boot(1); run_seconds(30); } audit("C 2.5 d + 200 brown-out resets x 30 s (no hold)");
  /* D: a reset every 47 min for 3 days (flaky contact), hold never triggers */
  fresh(); do_boot(1); for (int k = 0; k < 92; k++) { run_seconds(47L * 60L); reset_now(); do_boot(1); } audit("D reset every 47 min for 3 days");
  /* E: WDT loop that lasts 2 h while the flash is full: hold -> full-flash losses? */
  fresh(); do_boot(1); run_seconds(60L * 3600L);
  { long t_end = truth + 2L * 3600L; int q = 2; while (truth < t_end) { reset_now(); do_boot(q); q = q < 15 ? q + 1 : 15; run_seconds(5L * 60L); } }
  run_seconds(3600); audit("E 2.5 d + reset every 5 min for 2 h (hold 30 min)");
  return 0;
}
