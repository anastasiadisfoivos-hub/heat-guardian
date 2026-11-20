/* Heat Guardian 08_logger: file-ring policy. See log_ring.h. */
#include "hg_nofastmath.h"   /* FIRST: the core builds with -Ofast; NaN must stay NaN */
#include "log_ring.h"
#include <string.h>
#include <stdio.h>

static int is_digit(char c) { return c >= '0' && c <= '9'; }

char hg_ring_classify(const char *name, uint16_t *seq)
{
  if (!name) return '?';
  if (strcmp(name, "min.bin") == 0) return 'm';
  if (strcmp(name, "events2.txt") == 0 || strcmp(name, "events.txt") == 0) return 'e';   /* legacy (0.9.6-0.9.9) events logs: kept, never opened by 0.9.10 */
  if (strncmp(name, "events_", 7) == 0 && strlen(name) > 11 && strcmp(name + strlen(name) - 4, ".txt") == 0) {   /* 0.9.10 FS-HEAL: events_<gen>.txt */
    for (const char *p = name + 7; p < name + strlen(name) - 4; p++) if (!is_digit(*p)) return '?';
    return 'e';
  }
  if (strcmp(name, "boot.bin") == 0) return 'b';
  /* [sr]DDDD.bin, exactly 9 characters */
  if ((name[0] == 's' || name[0] == 'r') && strlen(name) == 9 &&
      is_digit(name[1]) && is_digit(name[2]) && is_digit(name[3]) && is_digit(name[4]) &&
      strcmp(name + 5, ".bin") == 0) {
    if (seq) *seq = (uint16_t)((name[1] - '0') * 1000 + (name[2] - '0') * 100 + (name[3] - '0') * 10 + (name[4] - '0'));
    return name[0];
  }
  return '?';
}

void hg_ring_make_path(char kind, uint16_t seq, char *out, size_t outlen)
{
  snprintf(out, outlen, "/log/%c%04u.bin", kind, (unsigned)(seq % HG_SEQ_MOD));
}

uint32_t hg_ring_blocks_for(uint32_t size, uint32_t block_size)
{
  if (block_size <= 16) return 1;
  uint32_t usable = block_size - 8;   /* conservative: up to two 4-byte CTZ pointers per block */
  return (size + usable - 1) / usable + 1;
}

int hg_ring_plan(const hg_logfile_t *files, int n, uint32_t free_blocks, uint32_t block_size,
                 uint32_t need_blocks, int max_s, int *del_idx, int max_del)
{
  int s_count = 0, ndel = 0;
  uint8_t taken[HG_RING_MAX_FILES];
  if (n > HG_RING_MAX_FILES) n = HG_RING_MAX_FILES;
  memset(taken, 0, sizeof taken);
  for (int i = 0; i < n; i++) if (files[i].kind == 's' || files[i].kind == 'r') s_count++;
  uint32_t freed = 0;
  while (ndel < max_del) {
    int need_count = (s_count >= max_s);
    int need_space = (free_blocks + freed < need_blocks);
    if (!need_count && !need_space) break;
    /* oldest deletable s or r file */
    int best = -1;
    for (int i = 0; i < n; i++) {
      if (taken[i]) continue;
      char k = files[i].kind;
      if (k != 's' && k != 'r') continue;
      if (best < 0 || files[i].seq < files[best].seq) best = i;
    }
    if (best < 0) break;            /* nothing left to delete */
    taken[best] = 1;
    del_idx[ndel++] = best;
    freed += hg_ring_blocks_for(files[best].size, block_size);
    s_count--;
  }
  return ndel;
}

int hg_ring_boot_file(const hg_logfile_t *files, int n, uint32_t full_bytes, uint16_t *seq)
{
  int best = -1;
  for (int i = 0; i < n; i++) if (files[i].kind == 's' && (best < 0 || files[i].seq > files[best].seq)) best = i;
  /* the newest s file must also be the newest file overall (a raw capture after it means it was closed) */
  for (int i = 0; i < n && best >= 0; i++) if (files[i].kind == 'r' && files[i].seq > files[best].seq) best = -1;
  if (best < 0 || files[best].size >= full_bytes) return 0;
  *seq = files[best].seq;
  return 1;
}

uint16_t hg_ring_next_seq(const hg_logfile_t *files, int n, uint16_t stored_next)
{
  uint32_t next = stored_next % HG_SEQ_MOD;
  for (int i = 0; i < n; i++) {
    if (files[i].kind != 's' && files[i].kind != 'r') continue;
    uint32_t cand = (uint32_t)files[i].seq + 1u;
    if (cand > next) next = cand;
  }
  return (uint16_t)(next % HG_SEQ_MOD);
}
