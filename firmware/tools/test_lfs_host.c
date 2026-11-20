/* Host test: the REAL littlefs v1.6 (the copy inside the Seeed core) on a 2 MB RAM "flash" with the
 * exact config of 08_logger (block 4096, read/prog 256, lookahead 512, 512 blocks), driven by the
 * sketch's write pattern and the same ring policy (log_ring.c):
 *   - every minute: open-append-close 60 x 24 B to the hour file, 24 B to min.bin, sometimes events
 *   - every 3600 records: ring plan (free blocks measured with lfs_traverse) -> remove -> new file
 *   - one 10-minute raw capture per day (308-B blocks, flushed every 10 blocks)
 *   - a "reboot" (unmount + mount) every 26 h
 * The RAM flash behaves like NOR: erase sets 0xFF, program can only clear bits (a program that would
 * set a bit is counted as an error), erase counts per block are recorded (wear).
 * At the end every remaining record file is read back and every record's CRC and continuity checked.
 *   cc -std=gnu99 -O2 -I../08_logger -I$CORE/libraries/Adafruit_LittleFS/src/littlefs test_lfs_host.c \
 *      ../08_logger/log_ring.c $CORE/.../lfs.c $CORE/.../lfs_util.c -o /tmp/test_lfs && /tmp/test_lfs [days]
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "lfs.h"
#include "log_format.h"
#include "log_ring.h"

#define BS 4096
#define NB 512
/* the Seeed core's lfs_util.h allocates file buffers with FreeRTOS pvPortMalloc(); host shims: */
void *pvPortMalloc(size_t n) { return malloc(n); }
void vPortFree(void *p) { free(p); }

static uint8_t flash[NB * BS];
static uint32_t erases[NB];
static long prog_bad = 0, n_prog = 0, n_erase = 0, n_read = 0;

static int bd_read(const struct lfs_config *c, lfs_block_t b, lfs_off_t off, void *buf, lfs_size_t n)
{ (void)c; memcpy(buf, flash + b * BS + off, n); n_read++; return 0; }
static int bd_prog(const struct lfs_config *c, lfs_block_t b, lfs_off_t off, const void *buf, lfs_size_t n)
{
  (void)c; uint8_t *d = flash + b * BS + off; const uint8_t *s = buf;
  for (lfs_size_t i = 0; i < n; i++) { if ((d[i] & s[i]) != s[i]) prog_bad++; d[i] &= s[i]; }
  n_prog++; return 0;
}
static int bd_erase(const struct lfs_config *c, lfs_block_t b) { (void)c; memset(flash + b * BS, 0xFF, BS); erases[b]++; n_erase++; return 0; }
static int bd_sync(const struct lfs_config *c) { (void)c; return 0; }

static uint8_t rb[256], pb[256], la[512 / 8];
static struct lfs_config cfg = {
  .context = NULL, .read = bd_read, .prog = bd_prog, .erase = bd_erase, .sync = bd_sync,
  .read_size = 256, .prog_size = 256, .block_size = BS, .block_count = NB, .lookahead = 512,
  .read_buffer = rb, .prog_buffer = pb, .lookahead_buffer = la, .file_buffer = NULL
};
static lfs_t lfs;
static int fails = 0;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL: " __VA_ARGS__); printf("\n"); } } while (0)

static int cnt_cb(void *p, lfs_block_t b) { (void)b; (*(uint32_t *)p)++; return 0; }
static uint32_t free_blocks(void) { uint32_t n = 0; lfs_traverse(&lfs, cnt_cb, &n); return n >= NB ? 0 : NB - n; }

static int append(const char *path, const void *d, uint32_t n)
{
  lfs_file_t f;
  if (lfs_file_open(&lfs, &f, path, LFS_O_RDWR | LFS_O_CREAT) < 0) return -1;
  lfs_file_seek(&lfs, &f, 0, LFS_SEEK_END);
  lfs_ssize_t w = lfs_file_write(&lfs, &f, d, n);
  int rc = lfs_file_close(&lfs, &f);
  return (w == (lfs_ssize_t)n && rc == 0) ? 0 : -1;
}

static hg_logfile_t files[HG_RING_MAX_FILES]; static char names[HG_RING_MAX_FILES][16]; static int nfiles;
static void list_log(void)
{
  lfs_dir_t d; struct lfs_info info; nfiles = 0;
  if (lfs_dir_open(&lfs, &d, "/log") < 0) return;
  while (lfs_dir_read(&lfs, &d, &info) > 0 && nfiles < HG_RING_MAX_FILES) {
    if (info.name[0] == '.') continue;
    uint16_t seq = 0; char k = hg_ring_classify(info.name, &seq);
    files[nfiles].kind = k; files[nfiles].seq = seq; files[nfiles].size = info.size;
    snprintf(names[nfiles], sizeof names[nfiles], "%.15s", info.name); nfiles++;
  }
  lfs_dir_close(&lfs, &d);
}
static uint16_t next_seq_stored = 0;
static long deleted = 0, write_errors = 0, boot_appends = 0;
static void make_room(uint32_t need, int max_s)
{
  list_log();
  int idx[HG_RING_MAX_FILES];
  int nd = hg_ring_plan(files, nfiles, free_blocks(), BS, need, max_s, idx, HG_RING_MAX_FILES);
  for (int i = 0; i < nd; i++) { char p[32]; snprintf(p, sizeof p, "/log/%s", names[idx[i]]); if (lfs_remove(&lfs, p) == 0) deleted++; }
}
static uint16_t take_seq(void) { list_log(); uint16_t s = hg_ring_next_seq(files, nfiles, next_seq_stored); next_seq_stored = (uint16_t)((s + 1) % HG_SEQ_MOD); return s; }

static uint32_t t_ms = 0; static uint16_t boot = 1;
static void rec_at(uint8_t *b, uint32_t t, uint8_t marker, uint16_t aux, uint8_t flags)
{
  hg_rec_t r; memset(&r, 0, sizeof r);
  r.t_ms = t; r.t1_c100 = (int16_t)(3300 + t / 1000 % 50); r.t2_c100 = HG_T_ABSENT; r.tair_c100 = 2400; r.rh = 45;
  r.hr = 70; r.hr_q = 4; r.marker = marker; r.aux = aux; r.flags = flags | (marker ? HG_F_MARKER : 0);
  hg_rec_pack(&r, b);
}

int main(int argc, char **argv)
{
  int days = argc > 1 ? atoi(argv[1]) : 3;
  int min_every = argc > 2 ? atoi(argv[2]) : 1;     /* minutes between min.bin appends (sketch: HG_MIN_FLUSH_EVERY) */
  memset(flash, 0xFF, sizeof flash);
  CHECK(lfs_format(&lfs, &cfg) == 0, "format");
  CHECK(lfs_mount(&lfs, &cfg) == 0, "mount");
  lfs_mkdir(&lfs, "/log");
  char cur[32] = ""; uint32_t recs = 0;
  uint8_t secbuf[60 * HG_REC_SIZE];
  uint32_t min_free = NB, total_minutes = (uint32_t)days * 1440u;
  for (uint32_t m = 0; m < total_minutes; m++) {
    if (!cur[0] || recs >= 3600) {
      make_room(HG_RING_MARGIN_BLOCKS, HG_RING_MAX_S_FILES);
      uint16_t s = take_seq(); hg_ring_make_path('s', s, cur, sizeof cur);
      uint8_t h[HG_REC_SIZE]; rec_at(h, t_ms, HG_M_FILE, boot, 0);
      if (append(cur, h, HG_REC_SIZE)) write_errors++;
      recs = 0;
    }
    for (int i = 0; i < 60; i++) { rec_at(secbuf + i * HG_REC_SIZE, t_ms, 0, 0, 0); t_ms += 1000; }
    if (append(cur, secbuf, sizeof secbuf)) write_errors++;
    recs += 60;
    static uint8_t mbuf[16 * HG_REC_SIZE]; static int mn = 0;
    rec_at(mbuf + mn * HG_REC_SIZE, t_ms - 60000, 0, 0, HG_F_MINUTE); mn++;
    if (mn >= min_every) { if (append("/log/min.bin", mbuf, mn * HG_REC_SIZE)) write_errors++; mn = 0; }
    if (m % 30 == 0) { const char *e = "MARK boot=1 t_ms=123456789 m=9 name=button v=0 src=button unix=1763280000\n"; if (append("/log/events.txt", e, strlen(e))) write_errors++; }
    if (m % 1440 == 600) {                       /* 10-minute raw capture, flushed every 10 blocks */
      make_room(HG_RING_RAW_BLOCKS, HG_RING_MAX_S_FILES + 1);
      char rp[32]; hg_ring_make_path('r', take_seq(), rp, sizeof rp);
      uint8_t blk[10 * 308]; memset(blk, 0x5A, sizeof blk);
      for (int k = 0; k < 60; k++) if (append(rp, blk, sizeof blk)) write_errors++;
    }
    if (m % 1567 == 1566) {                        /* reboot (every ~26 h, mid-hour): remount, boot.bin rewrite, append to the newest hour file */
      lfs_unmount(&lfs); CHECK(lfs_mount(&lfs, &cfg) == 0, "remount at minute %u", m); boot++;
      uint8_t bb[24]; memset(bb, boot, sizeof bb);
      lfs_file_t bf; if (lfs_file_open(&lfs, &bf, "/log/boot.bin", LFS_O_RDWR | LFS_O_CREAT | LFS_O_TRUNC) == 0) { lfs_file_write(&lfs, &bf, bb, 24); lfs_file_close(&lfs, &bf); } else write_errors++;
      list_log(); uint16_t bs;
      if (hg_ring_boot_file(files, nfiles, HG_HOUR_FILE_BYTES, &bs)) {
        hg_ring_make_path('s', bs, cur, sizeof cur);
        uint8_t h[HG_REC_SIZE]; rec_at(h, t_ms, HG_M_FILE, boot, 0);
        if (append(cur, h, HG_REC_SIZE)) write_errors++;
        boot_appends++;
      } else cur[0] = 0;
    }
    if (m % 60 == 0) { uint32_t f = free_blocks(); if (f < min_free) min_free = f; }
  }
  /* read back and verify every record file */
  list_log();
  long recs_ok = 0, recs_bad = 0, s_files = 0, gaps = 0;
  for (int i = 0; i < nfiles; i++) {
    if (files[i].kind != 's' && files[i].kind != 'm') continue;
    if (files[i].kind == 's') s_files++;
    char p[32]; snprintf(p, sizeof p, "/log/%s", names[i]);
    lfs_file_t f; CHECK(lfs_file_open(&lfs, &f, p, LFS_O_RDONLY) == 0, "open %s", p);
    uint8_t b[HG_REC_SIZE]; hg_rec_t r; long prev = -1;
    CHECK(files[i].size % HG_REC_SIZE == 0, "%s size %u not a multiple of 24", p, files[i].size);
    while (lfs_file_read(&lfs, &f, b, HG_REC_SIZE) == HG_REC_SIZE) {
      if (hg_rec_unpack(b, &r)) recs_ok++; else recs_bad++;
      if (files[i].kind == 's' && r.marker != HG_M_FILE) { if (prev >= 0 && r.t_ms != (uint32_t)prev + 1000u) gaps++; prev = r.t_ms; }
    }
    lfs_file_close(&lfs, &f);
  }
  uint32_t maxe = 0, used_e = 0; double sume = 0;
  for (int b = 0; b < NB; b++) { if (erases[b] > maxe) maxe = erases[b]; if (erases[b]) used_e++; sume += erases[b]; }
  printf("littlefs v1.6 host run: %d days, %u minutes, min.bin appended every %d min\n", days, total_minutes, min_every);
  { int top[3] = {-1, -1, -1};
    for (int b = 0; b < NB; b++) for (int k = 0; k < 3; k++) if (top[k] < 0 || erases[b] > erases[top[k]]) { for (int j = 2; j > k; j--) top[j] = top[j - 1]; top[k] = b; break; }
    printf("  hottest blocks: #%d %u, #%d %u, #%d %u erases (littlefs v1 rewrites a directory pair on every file close)\n",
           top[0], erases[top[0]], top[1], erases[top[1]], top[2], erases[top[2]]); }
  printf("  files now: %d (hour files %ld), deleted %ld, write errors %ld, NOR violations %ld\n", nfiles, s_files, deleted, write_errors, prog_bad);
  printf("  reboots that appended to the open hour file: %ld\n", boot_appends);
  printf("  records read back: %ld OK, %ld CRC bad, %ld gaps inside hour files\n", recs_ok, recs_bad, gaps);
  printf("  min free blocks seen (hourly): %u of %d\n", min_free, NB);
  printf("  erases: total %.0f, per day %.0f, blocks touched %u, max per block %u, mean %.1f\n", sume, sume / days, used_e, maxe, sume / NB);
  printf("  max erases/block/day %.1f -> 100,000-cycle NOR (P25Q16H class figure) lasts %.0f days at this rate\n",
         (double)maxe / days, 100000.0 / ((double)maxe / days));
  for (int i = 0; i < nfiles; i++) printf("    /log/%-10s %8u B\n", names[i], files[i].size);
  CHECK(write_errors == 0, "write errors");
  CHECK(prog_bad == 0, "NOR violations");
  CHECK(recs_bad == 0, "CRC errors on read-back");
  CHECK(gaps == 0, "gaps");
  CHECK(min_free >= 8, "free space fell to %u blocks", min_free);
  printf("%s\n", fails ? "TEST_LFS_HOST: FAIL" : "TEST_LFS_HOST: PASS");
  return fails ? 1 : 0;
}
