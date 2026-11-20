/* Heat Guardian 08_logger: file-ring policy for /log on the QSPI flash.
 * Pure C, no filesystem calls: the sketch lists /log, asks this module what to delete and what
 * to call the next file, then does the deleting. The same code is unit-tested on the host with
 * a mock filesystem (fw/tools/test_ring.c) and with the real littlefs v1.6 on a RAM disk
 * (fw/tools/test_lfs_host.c).
 *
 * Files:   /log/sNNNN.bin  one hour of 1 Hz records (3600 x 24 B = 86,400 B), deletable
 *          /log/rNNNN.bin  one raw-PPG capture (raw <s> command), deletable
 *          /log/min.bin    1-min summaries for the whole test, NEVER deleted by the ring
 *          /log/events.txt boots, resets, markers, time syncs, NEVER deleted by the ring
 *          /log/boot.bin   boot counter + next sequence number, NEVER deleted by the ring
 * NNNN is one sequence counter shared by s and r files (0..9999, persisted in boot.bin), so
 * "oldest" is simply "lowest sequence number".
 */
#ifndef HG_LOG_RING_H
#define HG_LOG_RING_H
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif

#define HG_RING_MAX_S_FILES   100     /* last-resort cap on s+r files (listing capacity), NOT the retention rule:
                                         retention is by free space only, so short files left by resets never
                                         push full hour files out (T6a blocker B1) */
#define HG_RING_MARGIN_BLOCKS 64      /* free 4 KB blocks required before a new hour file (256 KB): next hour (23) + min.bin growth + littlefs copy-on-write slack */
#define HG_RING_RAW_BLOCKS    96      /* free blocks required before a raw capture (384 KB): 10-min raw (46) + the growing hour file (23) + slack */
#define HG_RING_MAX_FILES     128     /* listing capacity */
#define HG_HOUR_FILE_BYTES    (24u + 3600u * 24u)  /* header + one hour of 1 Hz records */
#define HG_SEQ_MOD            10000u

typedef struct {
  char     kind;      /* 's' hourly, 'r' raw, 'm' min.bin, 'e' events.txt, 'b' boot.bin, '?' other */
  uint16_t seq;       /* for s/r */
  uint32_t size;      /* bytes */
} hg_logfile_t;

/* Parse a bare file name (no directory). Returns the kind; *seq set for s/r. */
char hg_ring_classify(const char *name, uint16_t *seq);

/* "/log/s0012.bin" */
void hg_ring_make_path(char kind, uint16_t seq, char *out, size_t outlen);

/* littlefs v1 blocks a file of `size` bytes occupies (CTZ skip-list: <= 8 B of pointers per
 * block for files < 16 MB), +1 for safety. Used only to *estimate* what a deletion frees. */
uint32_t hg_ring_blocks_for(uint32_t size, uint32_t block_size);

/* Decide which deletable files (kinds s and r) to remove, oldest sequence first, so that after
 * the removals (a) fewer than max_s s+r files remain (last-resort listing cap, HG_RING_MAX_S_FILES)
 * and (b) free_blocks + freed >= need_blocks. Rule (b) is the retention rule. Writes indices into `files` to del_idx (oldest first)
 * and returns how many. Never selects m/e/b/? files. If even deleting every deletable file is not
 * enough, it deletes them all and returns that count (the caller then logs "FS FULL"). */
int hg_ring_plan(const hg_logfile_t *files, int n, uint32_t free_blocks, uint32_t block_size,
                 uint32_t need_blocks, int max_s, int *del_idx, int max_del);

/* Which hour file to write after a boot: if the newest 's' file holds fewer than `full_bytes`
 * bytes, keep appending to it (returns 1, *seq = its seq) - a reset must not start a new file,
 * because new files are what push old data out. Otherwise returns 0 (caller makes a new file). */
int hg_ring_boot_file(const hg_logfile_t *files, int n, uint32_t full_bytes, uint16_t *seq);

/* Next sequence number: max(stored_next, 1 + highest s/r seq on disk) mod HG_SEQ_MOD. */
uint16_t hg_ring_next_seq(const hg_logfile_t *files, int n, uint16_t stored_next);

#ifdef __cplusplus
}
#endif
#endif
