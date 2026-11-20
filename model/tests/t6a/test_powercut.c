/* T6a power-cut test for 08_logger's storageInit() decision logic.
 *
 * Runs the REAL littlefs v1.6 (Seeed core copy) on a 2 MB RAM NOR flash with 08_logger's exact
 * config and a write pattern close to the sketch (minute appends to the hour file, min.bin every
 * 10 min, events.txt, boot.bin truncate-rewrite at every new file, ring deletions).
 * At every K-th program/erase operation it CLONES the flash, applies a TORN version of that operation
 * to the clone (erase: first half of the block erased, rest old data; prog: first half of the bytes
 * programmed), and then "reboots" the clone with the sketch's own decision:
 *     mount OK                       -> FS_OK   (then every record file is read and CRC-checked)
 *     mount fails, "littlefs" magic  -> FS_CORRUPT (data kept, logging STOPS until `format YES`)
 *     mount fails, no magic          -> FORMAT (= data loss)  <-- must never happen
 * Exit 0 only if FORMAT never happens.
 *   cc -std=gnu99 -O2 -w -I../../fw/08_logger -I$LFS test_powercut.c $LFS/lfs.c $LFS/lfs_util.c \
 *      ../../fw/08_logger/log_ring.c -o /tmp/pc && /tmp/pc [days] [every_k]
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

static uint8_t flash[NB * BS], clone_[NB * BS];
static uint8_t *cur_img = flash;
static long ops = 0, every_k = 37;
static long n_checks = 0, n_ok = 0, n_corrupt = 0, n_format = 0, n_crc_bad = 0, n_records_seen = 0;

static int check_clone(void);

static void torn(int is_erase, lfs_block_t b, lfs_off_t off, const void *buf, lfs_size_t n)
{
  memcpy(clone_, flash, sizeof flash);
  if (is_erase) memset(clone_ + b * BS, 0xFF, BS / 2);
  else { uint8_t *d = clone_ + b * BS + off; const uint8_t *s = buf; for (lfs_size_t i = 0; i < n / 2; i++) d[i] &= s[i]; }
  check_clone();
}

static int bd_read(const struct lfs_config *c, lfs_block_t b, lfs_off_t off, void *buf, lfs_size_t n)
{ memcpy(buf, (uint8_t *)c->context + b * BS + off, n); return 0; }
static int bd_prog(const struct lfs_config *c, lfs_block_t b, lfs_off_t off, const void *buf, lfs_size_t n)
{
  uint8_t *img = c->context;
  if (img == flash && (++ops % every_k) == 0) torn(0, b, off, buf, n);
  uint8_t *d = img + b * BS + off; const uint8_t *s = buf;
  for (lfs_size_t i = 0; i < n; i++) d[i] &= s[i];
  return 0;
}
static int bd_erase(const struct lfs_config *c, lfs_block_t b)
{
  uint8_t *img = c->context;
  if (img == flash && (++ops % every_k) == 0) torn(1, b, 0, NULL, 0);
  memset(img + b * BS, 0xFF, BS); return 0;
}
static int bd_sync(const struct lfs_config *c) { (void)c; return 0; }

static uint8_t rb[256], pb[256], la[64], rb2[256], pb2[256], la2[64];
static struct lfs_config cfg = { .context = flash, .read = bd_read, .prog = bd_prog, .erase = bd_erase, .sync = bd_sync,
  .read_size = 256, .prog_size = 256, .block_size = BS, .block_count = NB, .lookahead = 512,
  .read_buffer = rb, .prog_buffer = pb, .lookahead_buffer = la, .file_buffer = NULL };
static struct lfs_config cfg2 = { .context = clone_, .read = bd_read, .prog = bd_prog, .erase = bd_erase, .sync = bd_sync,
  .read_size = 256, .prog_size = 256, .block_size = BS, .block_count = NB, .lookahead = 512,
  .read_buffer = rb2, .prog_buffer = pb2, .lookahead_buffer = la2, .file_buffer = NULL };
static lfs_t lfs, lfs2;

/* 08_logger.ino lfsSignature(): "littlefs" in the first 256 B of block 0 or 1 */
static int signature(const uint8_t *img)
{
  for (int blk = 0; blk < 2; blk++)
    for (int i = 0; i + 8 <= 256; i++) if (memcmp(img + blk * BS + i, "littlefs", 8) == 0) return 1;
  return 0;
}

static int check_clone(void)
{
  n_checks++;
  memset(&lfs2, 0, sizeof lfs2);
  if (lfs_mount(&lfs2, &cfg2) != 0) {
    if (signature(clone_)) n_corrupt++; else { n_format++; printf("FORMAT would happen at op %ld\n", ops); }
    return 0;
  }
  n_ok++;
  lfs_dir_t d; struct lfs_info info;
  if (lfs_dir_open(&lfs2, &d, "/log") == 0) {
    char names[64][16]; int nn = 0;
    while (lfs_dir_read(&lfs2, &d, &info) > 0 && nn < 64) if (info.name[0] != '.') snprintf(names[nn++], 16, "%.15s", info.name);
    lfs_dir_close(&lfs2, &d);
    for (int i = 0; i < nn; i++) {
      uint16_t q; char k = hg_ring_classify(names[i], &q);
      if (k != 's' && k != 'm') continue;
      char p[32]; snprintf(p, sizeof p, "/log/%s", names[i]);
      lfs_file_t f; if (lfs_file_open(&lfs2, &f, p, LFS_O_RDONLY) < 0) { n_crc_bad++; continue; }
      uint8_t b[HG_REC_SIZE]; hg_rec_t r;
      while (lfs_file_read(&lfs2, &f, b, HG_REC_SIZE) == HG_REC_SIZE) { n_records_seen++; if (!hg_rec_unpack(b, &r)) n_crc_bad++; }
      lfs_file_close(&lfs2, &f);
    }
  }
  lfs_unmount(&lfs2);
  return 0;
}

static int append(const char *path, const void *dd, uint32_t n)
{
  lfs_file_t f;
  if (lfs_file_open(&lfs, &f, path, LFS_O_RDWR | LFS_O_CREAT) < 0) return -1;
  lfs_file_seek(&lfs, &f, 0, LFS_SEEK_END);
  lfs_file_write(&lfs, &f, dd, n);
  return lfs_file_close(&lfs, &f);
}
static int rewrite(const char *path, const void *dd, uint32_t n)   /* bootSave(): open, truncate(0), write */
{
  lfs_file_t f;
  if (lfs_file_open(&lfs, &f, path, LFS_O_RDWR | LFS_O_CREAT) < 0) return -1;
  lfs_file_truncate(&lfs, &f, 0);
  lfs_file_write(&lfs, &f, dd, n);
  return lfs_file_close(&lfs, &f);
}
static int cnt_cb(void *p, lfs_block_t b) { (void)b; (*(uint32_t *)p)++; return 0; }
static uint32_t free_blocks(void) { uint32_t n = 0; lfs_traverse(&lfs, cnt_cb, &n); return n >= NB ? 0 : NB - n; }
static hg_logfile_t files[64]; static char names[64][16]; static int nfiles;
static void list_log(void)
{
  lfs_dir_t d; struct lfs_info info; nfiles = 0;
  if (lfs_dir_open(&lfs, &d, "/log") < 0) return;
  while (lfs_dir_read(&lfs, &d, &info) > 0 && nfiles < 64) {
    if (info.name[0] == '.') continue;
    uint16_t seq = 0; char k = hg_ring_classify(info.name, &seq);
    files[nfiles].kind = k; files[nfiles].seq = seq; files[nfiles].size = info.size;
    snprintf(names[nfiles], 16, "%.15s", info.name); nfiles++;
  }
  lfs_dir_close(&lfs, &d);
}

int main(int argc, char **argv)
{
  int days = argc > 1 ? atoi(argv[1]) : 1;
  every_k = argc > 2 ? atol(argv[2]) : 37;
  memset(flash, 0xFF, sizeof flash);
  /* 08's first boot: mount fails on blank flash, no signature -> format (expected, nothing to lose) */
  if (lfs_mount(&lfs, &cfg) == 0 || signature(flash)) { printf("unexpected: blank flash mounts or has a signature\n"); return 2; }
  lfs_format(&lfs, &cfg); lfs_mount(&lfs, &cfg); lfs_mkdir(&lfs, "/log");
  uint8_t bootf[24] = {0};
  char cur[32] = ""; uint32_t recs = 0, t = 0; uint16_t nxt = 0;
  uint8_t sec[60 * 24], mb[10 * 24]; int mn = 0;
  for (uint32_t m = 0; m < (uint32_t)days * 1440u; m++) {
    if (!cur[0] || recs >= 3600) {
      list_log(); int idx[64];
      int nd = hg_ring_plan(files, nfiles, free_blocks(), BS, HG_RING_MARGIN_BLOCKS, HG_RING_MAX_S_FILES, idx, 64);
      for (int i = 0; i < nd; i++) { char p[32]; snprintf(p, sizeof p, "/log/%s", names[idx[i]]); lfs_remove(&lfs, p); }
      list_log(); uint16_t s = hg_ring_next_seq(files, nfiles, nxt); nxt = (uint16_t)(s + 1);
      bootf[0]++; rewrite("/log/boot.bin", bootf, sizeof bootf);
      hg_ring_make_path('s', s, cur, sizeof cur);
      hg_rec_t r; memset(&r, 0, sizeof r); r.t_ms = t; r.marker = HG_M_FILE; uint8_t h[24]; hg_rec_pack(&r, h);
      append(cur, h, 24); recs = 0;
    }
    for (int i = 0; i < 60; i++) { hg_rec_t r; memset(&r, 0, sizeof r); r.t_ms = t; r.t1_c100 = 3300; hg_rec_pack(&r, sec + 24 * i); t += 1000; }
    append(cur, sec, sizeof sec); recs += 60;
    { hg_rec_t r; memset(&r, 0, sizeof r); r.t_ms = t; r.flags = HG_F_MINUTE; hg_rec_pack(&r, mb + 24 * mn); mn++; }
    if (mn >= 10) { append("/log/min.bin", mb, mn * 24); mn = 0; }
    if (m % 7 == 0) { const char *e = "MARK boot=1 t_ms=1 m=9 name=button v=0 src=button unix=0\n"; append("/log/events.txt", e, strlen(e)); }
  }
  printf("power-cut test: %d day(s), %ld flash ops, torn op every %ld -> %ld reboots simulated\n", days, ops, every_k, n_checks);
  printf("  mount OK %ld | mount FAILED but signature found (FS_CORRUPT, logging stops) %ld | would FORMAT (data loss) %ld\n",
         n_ok, n_corrupt, n_format);
  printf("  after OK mounts: %ld records read back, %ld CRC-bad records / unopenable files\n", n_records_seen, n_crc_bad);
  printf("%s\n", n_format ? "T6A_POWERCUT: FAIL (format would wipe data)" : (n_corrupt ? "T6A_POWERCUT: PASS (no wipe) WITH CORRUPT-STATE CASES" : "T6A_POWERCUT: PASS"));
  return n_format ? 1 : 0;
}
