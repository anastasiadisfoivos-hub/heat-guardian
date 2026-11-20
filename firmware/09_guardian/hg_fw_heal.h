/* Heat Guardian 09_guardian 0.9.10 FS-HEAL: the log file system heals itself instead of boot-looping.
 * Plain C, no filesystem calls (the sketch does the I/O); host-tested in fw/tools/test_heal.c, part of it
 * against the REAL littlefs v1.6 with a poisoned file.
 *
 * Why this exists (bench Nov 17-18, 0.9.6-rescue boot loop, quick_boots=22):
 *   littlefs v1.6 in the Seeed core is built WITH asserts (LFS_ASSERT = newlib assert). A corrupt CTZ skip
 *   pointer in one file (lfs.c lfs_ctz_find / lfs_ctz_extend: LFS_ASSERT(head >= 2 && head <= block_count))
 *   calls __assert_func -> fiprintf(stderr, nowhere) -> abort -> _exit, and _exit in this toolchain is
 *   "b _exit": a silent spin until the 8 s watchdog. The append of the next boot hits the same pointer, so
 *   every boot dies at the same line. Renaming the live file only moved the problem to the next file.
 *
 * The fix, in three layers:
 *   1. guard: every log-FS call runs with a RAM "in progress" file id (fsOp). If it asserts (our own
 *      __assert_func) or does not return within HG_FS_DEADLINE_MS (a 0.5 s FreeRTOS timer), the band writes
 *      the id into GPREGRET2 and soft-resets at once. GPREGRET2 survives a soft reset (not a watchdog reset,
 *      B6a n1), so the id reaches the next boot. A hang with interrupts off still ends in the hardware
 *      watchdog, without a marker: the boot-loop path (2) covers that.
 *   2. heal at boot (this module decides, the sketch does it): the file named by the marker is quarantined
 *      (never opened again; the events log moves to a new generation events_<gen>.txt, a dead s-file is
 *      left and a new one started), a boot loop with no marker gets the same "blind" heal and a quiet boot
 *      (no non-essential log writes until 10 min of uptime), and after HG_HEAL_FORMAT_AFTER troubled boots in
 *      a row the LOG area is re-formatted (profile, twin, family name, routine, day plan, heal state live on
 *      InternalFS, a different chip region and file system: untouched). If even a fresh log area keeps
 *      failing, storage is switched off (the band runs, it just does not log) instead of looping.
 *   3. runtime: a write that returns an error is dropped and counted; HG_HEAL_RUNTIME_FAILS failed events
 *      appends in a row move the events log to a new generation.
 * The heal state lives on InternalFS (/fsheal.bin), not on the flash it is healing.
 */
#ifndef HG_FW_HEAL_H
#define HG_FW_HEAL_H
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif

/* file ids written into the marker (5 bits) */
enum {
  HG_FID_NONE = 0,     /* assert outside any guarded FS call */
  HG_FID_EVENTS = 1,   /* /log/events_<gen>.txt append */
  HG_FID_SFILE = 2,    /* the current /log/sNNNN.bin (records, header) */
  HG_FID_BOOT = 3,     /* /log/boot.bin read or write */
  HG_FID_RAW = 4,      /* the current /log/rNNNN.bin */
  HG_FID_RING = 5,     /* ring deletion / erase command removes */
  HG_FID_MOUNT = 6,    /* lfs_mount / mkdir */
  HG_FID_HEAL = 7,     /* a heal remove (died there: that file is never touched again) */
  HG_FID_DUMP = 8,     /* a dump read (the file is in heal state dump_path) */
  HG_FID_LIST = 9,     /* listing /log, free-block count (lfs_traverse) */
  HG_FID_FORMAT = 10,  /* re-formatting the log area */
  HG_FID_OTHER = 11,
  HG_FID_IFS_HEAL = 12,     /* InternalFS itself: mount / format / removing the old 0.9.12 /fsheal.bin (0.9.13: the heal state is off InternalFS) */
  HG_FID_IFS_TWIN = 13,     /* /twin.bin */
  HG_FID_IFS_PROFILE = 14,  /* /profile.bin */
  HG_FID_IFS_ECO = 15,      /* /famname.bin, /routine.bin, /dayplan.bin (all re-sent by the phone) */
  HG_FID_COUNT = 16
};
enum { HG_CAUSE_NONE = 0, HG_CAUSE_DEADLINE = 1, HG_CAUSE_ASSERT = 2 };

#define HG_FS_DEADLINE_MS       4000u  /* 0.9.13: NO flash I/O for this long inside one FS call = hung (a CPU spin, an assert-free loop) */
#define HG_FS_TOTAL_MS          30000u /* 0.9.13: one FS call still doing I/O after this long = runaway (relocation storm); the
                                          watchdog is fed by the deadline timer while the call makes I/O progress */
/* 0.9.13 deadline rule: 1 = the FS call is hung (reset), 0 = let it run (and feed the watchdog if io_progress) */
int hg_heal_deadline_hit(uint32_t total_ms, uint32_t since_io_ms);
/* 0.9.13: the next marker's count. Faults count only against faults of the SAME class (QSPI log vs InternalFS):
 * an InternalFS fault followed by a QSPI fault starts the QSPI count at 1 (0.9.12 shared one count: 2 InternalFS faults
 * + 1 QSPI fault = "3 in a row" = log storage off). prev_count 0 = no fault before this boot. */
uint8_t hg_heal_next_count(uint8_t prev_count, uint8_t prev_fid, uint8_t fid);
#define HG_HEAL_FORMAT_AFTER    3u     /* troubled boots in a row before the log area is re-formatted (the 4th re-formats) */
#define HG_HEAL_DISABLE_AFTER   3u     /* troubled boots in a row AFTER a heal format before storage is switched off */
#define HG_HEAL_RUNTIME_FAILS   3u     /* failed events appends in a row -> new events generation */
#define HG_HEAL_QMAX            4      /* quarantined paths remembered (FIFO) */
#define HG_HEAL_PATH            24
#define HG_HEAL_MAGIC           0x4C414548u   /* "HEAL" */
#define HG_HEAL_VER             1u

const char *hg_heal_fid_name(uint8_t fid);
const char *hg_heal_cause_name(uint8_t cause);

/* 0.9.11 GPREGRET2 byte: bit 7 cause (1 assert, 0 deadline), bit 6 ifs_bad (an InternalFS call died in this chain:
 * do not touch InternalFS for heal state), bits 5-4 count = guard resets in a row (1..3, saturating), bits 3-0 file id.
 * count 0 or an unknown file id = no marker (0x00 after a watchdog / power-on reset). The COUNT is the bad-boot streak:
 * it lives in the register itself, so it is "persisted" before any flash operation of the next boot can fail. */
uint8_t hg_heal_marker_encode(uint8_t cause, uint8_t fid, uint8_t count, uint8_t ifs_bad);
int hg_heal_marker_decode(uint8_t reg, uint8_t *cause, uint8_t *fid, uint8_t *count, uint8_t *ifs_bad);   /* 1 = valid */
#define HG_FID_IFS HG_FID_IFS_HEAL
int hg_heal_fid_is_ifs(uint8_t fid);
/* 0.9.12 InternalFS ladder, decided from the marker BEFORE any InternalFS call of the boot (not counted in the QSPI streak):
 *   count 1 -> remove the file(s) of that file id (quarantine), count 2 -> back up the profile in RAM, format ONLY InternalFS,
 *   write the profile back, count >= 3 -> no InternalFS at all this boot (RAM state; a clean boot tries again). */
enum { HG_IFS_NONE = 0, HG_IFS_REMOVE = 1, HG_IFS_FORMAT = 2, HG_IFS_OFF = 3 };
/* returns the action; paths = files to remove. prev_fid = the InternalFS file id healed last time (state byte ifs_healed):
 * the same file failing again later is not removed a second time, InternalFS is formatted instead */
int hg_heal_ifs_plan(uint8_t fid, uint8_t count, uint8_t prev_fid, const char **paths, int max_paths);
const char *hg_heal_ifs_files(uint8_t fid);   /* "/twin.bin" etc. for the FS_HEAL line */
#define HG_HEAL_FORMAT_AT_COUNT  2u    /* 2nd guard reset in a row -> re-format the log area before any other log call */
#define HG_HEAL_DISABLE_AT_COUNT 3u    /* 3rd (= it failed again after the format), or the format itself died -> storage off */

typedef struct {
  uint32_t magic;
  uint16_t ver;
  uint16_t gen;              /* events generation: the live log is /log/events_<gen>.txt; 0 = not chosen yet */
  uint8_t  streak;           /* troubled boots in a row (marker, boot loop, mount failure); 0 after 10 min stable */
  uint8_t  post_format;      /* troubled boots in a row since the last heal format */
  uint8_t  disabled;         /* 1 = storage switched off by the heal (console: fsheal reset) */
  uint8_t  last_cause, last_fid;
  uint8_t  formats;          /* heal formats so far */
  uint8_t  ifs_healed;       /* 0.9.12: InternalFS file id last quarantined (0 = none; cleared by an InternalFS format) */
  uint8_t  ifs_heals;        /* 0.9.12: InternalFS heals so far */
  uint32_t build;            /* firmware build id the state was last saved by (a different one = an upload) */
  uint32_t faults;           /* markers seen (asserts + deadlines) */
  uint32_t heals;            /* heal boots */
  uint32_t quarantined;      /* files quarantined so far */
  char     pending[HG_HEAL_PATH];    /* a heal remove in progress (died there -> quarantined for good) */
  char     dump_path[HG_HEAL_PATH];  /* the file a dump is reading now */
  char     q[HG_HEAL_QMAX][HG_HEAL_PATH];
  uint32_t crc;
} hg_heal_state_t;

uint32_t hg_heal_crc32(const void *p, size_t n);
void hg_heal_state_init(hg_heal_state_t *s);
void hg_heal_state_seal(hg_heal_state_t *s);
int  hg_heal_state_valid(const hg_heal_state_t *s);

/* events file of a generation: "/log/events_7.txt" */
void hg_heal_events_path(uint16_t gen, char *out, size_t n);
/* "events_7.txt" -> 7; anything else (incl. the legacy events.txt / events2.txt) -> 0 */
uint16_t hg_heal_events_gen(const char *name);
/* legacy (0.9.6 - 0.9.9) events files: never opened by 0.9.10 */
int hg_heal_is_legacy_events(const char *name);

int  hg_heal_is_quarantined(const hg_heal_state_t *s, const char *path);
void hg_heal_quarantine(hg_heal_state_t *s, const char *path);

/* One boot's heal decisions. The sketch calls hg_heal_begin (before mount), hg_heal_mount_failed (only if
 * the mount failed on a flash that holds our file system), hg_heal_after_boot (after boot.bin, with the
 * /log listing), then does what the flags say. */
typedef struct {
  uint8_t marker, cause, fid;   /* the marker this boot found */
  uint8_t count, ifs_bad;       /* guard resets in a row (from the marker), InternalFS died in this chain */
  uint8_t ifs_action;           /* 0.9.12: HG_IFS_* for an InternalFS marker (the QSPI log is left alone) */
  uint8_t state_new;            /* no valid /fsheal.bin: first 0.9.10 boot (or the state was lost) */
  uint8_t heal_boot;            /* this boot counted as troubled (streak++) */
  uint8_t format;               /* re-format the log area */
  uint8_t format_pre_mount;     /* ... before even mounting it (a marker said mount/format died) */
  uint8_t disable;              /* switch storage off for this boot (and until "fsheal reset") */
  uint8_t quiet;                /* no non-essential log writes until 10 min of uptime */
  uint8_t rotate_events;        /* a new events generation was taken (gen++) */
  uint8_t new_sfile;            /* do not append to the newest s-file: start a new one */
  uint8_t remove_boot;          /* remove /log/boot.bin before reading it (FID_BOOT marker) */
  uint8_t new_build;            /* first boot of this firmware build (an upload, or the first 0.9.10 boot) */
  uint8_t reset_quick_boots;    /* = new_build: the old firmware's boot-loop count does not apply. A soft reset of the
                                   SAME build is never an upload: it is the FS guard (even if GPREGRET2 were lost),
                                   so the sketch counts it as a quick boot instead of clearing the count */
  char remove_path[HG_HEAL_PATH];      /* try to remove this file (guarded, FID_HEAL) */
  char quarantine_path[HG_HEAL_PATH];  /* what was quarantined this boot ("" = nothing named) */
} hg_heal_boot_t;

void hg_heal_begin(hg_heal_state_t *s, hg_heal_boot_t *b, int state_valid, uint8_t marker_reg, uint32_t build_id);
void hg_heal_mount_failed(hg_heal_state_t *s, hg_heal_boot_t *b);
void hg_heal_after_boot(hg_heal_state_t *s, hg_heal_boot_t *b, int bootloop, uint16_t max_gen_on_disk,
                        const char *newest_sfile, const char *newest_raw);
/* after the guarded remove of b->remove_path: clears s->pending (the path stays quarantined either way) */
void hg_heal_remove_done(hg_heal_state_t *s, hg_heal_boot_t *b, int ok);
/* after a heal format: fresh log area, nothing quarantined any more, new events generation */
void hg_heal_formatted(hg_heal_state_t *s);
/* 10 min of uptime with storage working: the trouble is over. Returns 1 if the state changed (save it). */
int hg_heal_stable(hg_heal_state_t *s, int storage_ok);
/* runtime: one more failed (1) or good (0) events append. Returns 1 when the events log moved to a new
 * generation (the old file is quarantined; the sketch saves the state and logs it). */
int hg_heal_events_result(hg_heal_state_t *s, uint8_t *fails_in_row, int failed);
/* console "fsheal reset": storage back on, streaks cleared (generation and quarantine list kept) */
void hg_heal_reset(hg_heal_state_t *s);

#ifdef __cplusplus
}
#endif
#endif
