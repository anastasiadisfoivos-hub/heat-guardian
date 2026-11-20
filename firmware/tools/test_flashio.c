/* Heat Guardian 09_guardian 0.9.15 (FW-915-STABLE): the REAL littlefs v1.6 of the Seeed core (built with asserts, as on the band)
 * over a flash that "falls asleep" at random moments, the way the plan's A-04 hypothesis describes the band's chip:
 *   - OLD glue (0.9.14): the callbacks return 0 whatever happened: a read from the sleeping chip hands littlefs all-0xFF
 *     (or all-0x00) bytes as data, a program or erase silently does nothing.
 *   - NEW glue (0.9.15): the verified wake fails, the callback returns LFS_ERR_IO and touches nothing.
 * Each run is a forked child doing random appends / reads / removes / remounts for a while; the parent counts how the child
 * ended: clean, LFS_ASSERT (SIGABRT = on the band the old silent spin / now an FS-guard reset), or hung (alarm).
 * This measures what littlefs does with each glue. It does NOT prove the band's chip really sleeps (that is the hypothesis). */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <sys/wait.h>
#include <fcntl.h>
#include "lfs.h"

#define BS 4096
#define NB 64
static uint8_t fl[NB * BS];
static unsigned rs = 1;
static unsigned rnd(void) { rs = rs * 1103515245u + 12345u; return (rs >> 8) & 0xFFFFFF; }
static int newglue = 0, asleep = 0, sleep_left = 0, rate = 0, fill00 = 0;
static unsigned long ioerr = 0;
static void maybe_sleep(void)
{
  if (sleep_left > 0) { if (--sleep_left == 0) asleep = 0; return; }
  if (rate && (int)(rnd() % 1000) < rate) { asleep = 1; sleep_left = 1 + (int)(rnd() % 6); }
}
static int brd(const struct lfs_config *c, lfs_block_t b, lfs_off_t o, void *buf, lfs_size_t n)
{
  (void)c; maybe_sleep();
  if (asleep) { if (newglue) { ioerr++; return LFS_ERR_IO; } memset(buf, fill00 ? 0x00 : 0xFF, n); return 0; }
  memcpy(buf, fl + b * BS + o, n); return 0;
}
static int bpr(const struct lfs_config *c, lfs_block_t b, lfs_off_t o, const void *buf, lfs_size_t n)
{
  (void)c; maybe_sleep();
  if (asleep) { if (newglue) { ioerr++; return LFS_ERR_IO; } return 0; }
  const uint8_t *s = buf; for (lfs_size_t i = 0; i < n; i++) fl[b * BS + o + i] &= s[i]; return 0;   /* NOR: 1 -> 0 only */
}
static int ber(const struct lfs_config *c, lfs_block_t b)
{
  (void)c; maybe_sleep();
  if (asleep) { if (newglue) { ioerr++; return LFS_ERR_IO; } return 0; }
  memset(fl + b * BS, 0xFF, BS); return 0;
}
static int bsy(const struct lfs_config *c) { (void)c; return 0; }
static uint8_t rb[256], pb[256], lb[NB / 8];
static struct lfs_config cfg = { .read = brd, .prog = bpr, .erase = ber, .sync = bsy, .read_size = 256, .prog_size = 256,
  .block_size = BS, .block_count = NB, .lookahead = NB, .read_buffer = rb, .prog_buffer = pb, .lookahead_buffer = lb };
static lfs_t L;
/* the Seeed core's lfs_util.h allocates with FreeRTOS pvPortMalloc(); host shims */
void *pvPortMalloc(size_t n) { return malloc(n); }
void vPortFree(void *p) { free(p); }

static int child(unsigned seed, int ops)
{
  rs = seed; asleep = 0; sleep_left = 0;
  int keep = rate; rate = 0;
  memset(fl, 0xFF, sizeof fl);
  if (lfs_format(&L, &cfg) || lfs_mount(&L, &cfg)) return 9;
  lfs_mkdir(&L, "/log");
  rate = keep;
  uint8_t d[600]; for (unsigned i = 0; i < sizeof d; i++) d[i] = (uint8_t)i;
  char p[32]; int mounted = 1;
  for (int k = 0; k < ops; k++) {
    unsigned a = rnd() % 100;
    if (!mounted) { if (lfs_mount(&L, &cfg) == 0) mounted = 1; continue; }
    if (a < 60) {                                       /* append, as the sketch's fileAppend */
      snprintf(p, sizeof p, "/log/f%u.bin", rnd() % 6);
      lfs_file_t f; if (lfs_file_open(&L, &f, p, LFS_O_WRONLY | LFS_O_CREAT | LFS_O_APPEND) >= 0) {
        lfs_file_write(&L, &f, d, 24 + rnd() % 500); lfs_file_close(&L, &f); }
    } else if (a < 80) {
      snprintf(p, sizeof p, "/log/f%u.bin", rnd() % 6);
      lfs_file_t f; if (lfs_file_open(&L, &f, p, LFS_O_RDONLY) >= 0) { uint8_t r[300]; while (lfs_file_read(&L, &f, r, sizeof r) > 0) {} lfs_file_close(&L, &f); }
    } else if (a < 88) {
      snprintf(p, sizeof p, "/log/f%u.bin", rnd() % 6); lfs_remove(&L, p);
    } else if (a < 95) {
      lfs_dir_t dir; if (lfs_dir_open(&L, &dir, "/log") == 0) { struct lfs_info in; while (lfs_dir_read(&L, &dir, &in) > 0) {} lfs_dir_close(&L, &dir); }
    } else { lfs_unmount(&L); mounted = 0; }
  }
  return 0;
}
/* 0 clean, 2 LFS_ASSERT (abort), 3 hung / other signal */
static int run(unsigned seed, int ops)
{
  fflush(stdout); pid_t pid = fork();
  if (pid == 0) { alarm(10); int fd = open("/dev/null", 1); if (fd >= 0) dup2(fd, 2); _exit(child(seed, ops)); }
  int st; waitpid(pid, &st, 0);
  if (WIFSIGNALED(st)) return WTERMSIG(st) == SIGABRT ? 2 : 3;
  return WEXITSTATUS(st) ? 1 : 0;
}

int main(int argc, char **argv)
{
  int runs = argc > 1 ? atoi(argv[1]) : 300, ops = argc > 2 ? atoi(argv[2]) : 400;
  int fails = 0;
  const int rates[2] = { 5, 30 };                       /* per-mille chance per flash op that the chip falls asleep */
  for (int ri = 0; ri < 2; ri++) for (int f0 = 0; f0 < 2; f0++) {
    int res[2][4] = {{0}};
    for (int g = 0; g < 2; g++) {
      newglue = g; rate = rates[ri]; fill00 = f0;
      for (int i = 0; i < runs; i++) { int r = run(1000u + (unsigned)i * 7919u + (unsigned)ri, ops); res[g][r]++; }
    }
    printf("sleep rate %2d/1000 ops, sleeping chip reads %s: OLD glue %3d clean %3d LFS_ASSERT %3d hung | NEW glue %3d clean %3d LFS_ASSERT %3d hung  (%d runs x %d ops)\n",
           rates[ri], f0 ? "0x00" : "0xFF", res[0][0] + res[0][1], res[0][2], res[0][3], res[1][0] + res[1][1], res[1][2], res[1][3], runs, ops);
    if (res[1][3]) { printf("FAIL  new glue hung %d runs\n", res[1][3]); fails++; }
    if (res[1][2] > res[0][2]) { printf("FAIL  new glue asserts more often than the old one\n"); fails++; }
  }
  printf("TEST_FLASHIO: %s\n", fails ? "FAIL" : "PASS (see the counts: NEW glue asserts = what is left for the FS guard to catch)");
  return fails ? 1 : 0;
}
