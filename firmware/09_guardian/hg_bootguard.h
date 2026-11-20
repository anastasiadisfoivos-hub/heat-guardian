/* Heat Guardian 09_guardian 0.9.16 BOOT GUARD (session FW-BOOTGUARD, plan FW-WORLDCLASS D.1 / D.2 / D.4, stage 0.9.16).
 * Plain C, no hardware access: the sketch reads the memory-mapped journal page and does the flash writes through the
 * hg_bg_flash_t callbacks; this module decides. Host-tested in fw/tools/test_bootguard.c (with a simulated NOR page).
 *
 *   1. boot journal: one reserved internal-flash page (0xEB000), 4-byte entries appended in order. Each boot writes STARTED
 *      (its reset class, the ladder level it runs at, the previous boot's last checkpoint and uptime) before anything that
 *      can fail; HEALTHY at 60 s, STABLE at 10 min, CLEAN before a deliberate System OFF, REST before the ladder's own off.
 *      The same "this boot" record is mirrored in .hg_noinit RAM; the two copies are merged conservatively (higher level wins).
 *   2. ladder: the level of a boot = the previous boot's level + 1 when the previous boot ended in a FAULT before HEALTHY.
 *      A reset the user asked for (pin, power, wake, upload) restarts at 0. 0-1 normal, 2 careful, 3 safe, 4-5 minimal,
 *      6 rest (System OFF). A boot after REST starts at 3 (safe). Faults after HEALTHY but before STABLE (slow faults) climb
 *      too, from the 6th in a row, but never past minimal.
 *   3. reset ledger: every reset named (the 0.9.15 classes + supervisor / assert / stack / malloc / fault-inject), read back
 *      from the journal: counts per class and the last 8 with uptime and checkpoint.
 *   4. supervisor: the only feeder of the hardware watchdog after boot; the app task must check in within 5 s (or be inside a
 *      guarded file call that is still doing flash I/O), else a NAMED soft reset; a writer job stuck outside any guard is
 *      reported (storage off), never a reset.
 */
#ifndef HG_BOOTGUARD_H
#define HG_BOOTGUARD_H
#include <stdint.h>
#include "hg_fw_stable.h"
#ifdef __cplusplus
extern "C" {
#endif

/* ---- reset classes: hg_fw_stable's HG_RST_* (0..7) + the soft resets this firmware names itself ---------------------- */
enum {
  HG_BG_RST_SUPERVISOR = HG_RST_COUNT,  /* 8: the supervisor reset a task that stopped checking in */
  HG_BG_RST_ASSERT,                     /* 9: an assert outside any guarded file call (plan A-24: never a log format) */
  HG_BG_RST_STACK,                      /* 10: FreeRTOS stack-overflow hook */
  HG_BG_RST_MALLOC,                     /* 11: FreeRTOS malloc-failed hook */
  HG_BG_RST_INJECT,                     /* 12: bench fault injection (fault loop) */
  HG_BG_RST_REBOOT,                     /* 13: a reset a USB command asked for (fault loop arming): NOT a fault */
  HG_BG_RST_COUNT                       /* 14 (<= 16: 4 bits in a journal entry) */
};
/* reset codes our own code leaves in .hg_noinit right before NVIC_SystemReset() */
enum { HG_BG_RC_NONE = 0, HG_BG_RC_SUPERVISOR = 1, HG_BG_RC_ASSERT = 2, HG_BG_RC_STACK = 3, HG_BG_RC_MALLOC = 4, HG_BG_RC_INJECT = 5,
       HG_BG_RC_REBOOT = 6 };
/* base = hg_reset_classify(); a CRASH (soft reset, same build, no FS marker) with a reset code is named by the code */
int hg_bg_classify(int base_cls, uint8_t rcode);
const char *hg_bg_class_name(int cls);   /* short names for the ledger */
int hg_bg_is_fault(int cls);             /* watchdog, fs-guard, crash, lock-up, supervisor, assert, stack, malloc, inject */

/* ---- journal entries ---------------------------------------------------------------------------------------------------
 * word = type(4) | payload(24) | check(4). Types 1..5 (never 0 or 15: an erased word 0xFFFFFFFF and a zeroed word never decode).
 * STARTED payload: cls(4) level(3) slow(4) cp(6) upc(7)  - cp/upc describe the PREVIOUS boot (63 / 127 = unknown). */
enum { HG_BG_T_STARTED = 1, HG_BG_T_HEALTHY = 2, HG_BG_T_STABLE = 3, HG_BG_T_CLEAN = 4, HG_BG_T_REST = 5 };
#define HG_BG_PAGE_WORDS 1024
#define HG_BG_CP_UNKNOWN 63u
#define HG_BG_UP_UNKNOWN 127u
#define HG_BG_LEVEL_MAX 6u
#define HG_BG_SLOW_MAX 15u
typedef struct { uint8_t type, cls, level, slow, cp, upc; } hg_bg_entry_t;
uint32_t hg_bg_encode(const hg_bg_entry_t *e);
int hg_bg_decode(uint32_t w, hg_bg_entry_t *e);   /* 1 = valid entry, 0 = erased word, -1 = corrupt (bad check / type) */
/* uptime code (7 bits): 0..59 s exact, 60..118 = 1..59 min, 119..126 = >= 1,2,4,..128 h, 127 = unknown */
uint8_t hg_bg_up_encode(uint32_t ms);
uint32_t hg_bg_up_decode_s(uint8_t c);            /* lower bound in seconds (0xFFFFFFFF = unknown) */

/* ---- the previous boot, as one copy (journal or .hg_noinit) saw it ---------------------------------------------------- */
typedef struct {
  uint8_t valid;          /* a STARTED (or noinit record) was found */
  uint8_t level, slow;    /* the level / slow-fault count it ran at */
  uint8_t healthy, stable, clean, rest;
  uint8_t cls;            /* how IT was started */
  uint8_t cp, upc;        /* (journal only) last checkpoint + uptime of the boot before it */
} hg_bg_prev_t;
/* conservative merge of two copies: valid if either is; level / slow = max; healthy / stable only if every valid copy says
 * so; clean / rest from either (they only exist in the journal) */
void hg_bg_merge(hg_bg_prev_t *dst, const hg_bg_prev_t *other);

/* ---- page scan: append position, previous boot, ledger ----------------------------------------------------------------- */
#define HG_BG_LAST_N 8
typedef struct {
  int append;                          /* index of the first erased word after the last used one (HG_BG_PAGE_WORDS = full) */
  int used, corrupt;                   /* used words, words that failed the check */
  hg_bg_prev_t prev;                   /* the newest STARTED and the marks after it */
  uint16_t boots;                      /* STARTED entries on the page */
  uint16_t by_cls[HG_BG_RST_COUNT];    /* resets per class on the page */
  uint8_t nlast; hg_bg_entry_t last[HG_BG_LAST_N];   /* STARTED entries, newest first */
} hg_bg_scan_t;
void hg_bg_scan(const uint32_t *page, int nwords, hg_bg_scan_t *s);

/* ---- flash access for appends (the sketch: NVMC before the SoftDevice, sd_flash_* after; the test: a simulated NOR page) */
typedef struct {
  const volatile uint32_t *page;                     /* memory-mapped page, HG_BG_PAGE_WORDS words */
  int (*write_word)(void *ctx, int idx, uint32_t w); /* program one word (1 = the call succeeded) */
  int (*erase)(void *ctx);                           /* erase the page (1 = ok) */
  void *ctx;
} hg_bg_flash_t;
#define HG_BG_KEEP_WORDS 32   /* compaction keeps the newest 32 valid words (>= 8 boots) */
/* append one entry; a full page is compacted first (erase, the newest HG_BG_KEEP_WORDS valid words written back). Every word is
 * read back; a word that did not take is skipped (one retry at the next index). 1 = the entry is on the page. */
int hg_bg_append(const hg_bg_flash_t *f, uint32_t w);

/* ---- ladder ------------------------------------------------------------------------------------------------------------ */
enum { HG_BG_NORMAL = 0, HG_BG_CAREFUL = 1, HG_BG_SAFE = 2, HG_BG_MINIMAL = 3, HG_BG_REST = 4, HG_BG_MODE_COUNT = 5 };
const char *hg_bg_mode_name(int mode);
int hg_bg_mode_of(uint8_t level);   /* 0-1 normal, 2 careful, 3 safe, 4-5 minimal, >= 6 rest */
typedef struct { uint8_t level, slow, mode; } hg_bg_decision_t;
/* cls = this boot's class (hg_bg_classify). prev = the merged previous boot. */
void hg_bg_decide(const hg_bg_prev_t *prev, int cls, hg_bg_decision_t *d);
#define HG_BG_SLOW_FROM 6u   /* slow faults in a row before the ladder climbs on them */

/* one boot's decision, exactly as the sketch makes it: scan the journal, merge the .hg_noinit copy (ni = NULL when the RAM did not
 * survive), decide. Then the sketch appends hg_bg_started() BEFORE anything that can fail, and mirrors "this boot" with hg_bg_cur(). */
void hg_bg_boot(const uint32_t *page, const hg_bg_prev_t *ni, int cls, hg_bg_scan_t *s, hg_bg_prev_t *merged, hg_bg_decision_t *d);
uint32_t hg_bg_started(int cls, const hg_bg_decision_t *d, uint8_t prev_cp, uint8_t prev_upc);
uint32_t hg_bg_mark(uint8_t type);   /* HG_BG_T_HEALTHY / STABLE / CLEAN / REST */
void hg_bg_cur(hg_bg_prev_t *cur, int cls, const hg_bg_decision_t *d);   /* the .hg_noinit record of this boot */

/* the stage the previous boot died in (the sketch maps its checkpoint to one of these) */
enum { HG_BG_STG_NONE = 0, HG_BG_STG_STORAGE = 1, HG_BG_STG_BLE = 2, HG_BG_STG_IFS = 3 };
typedef struct {
  uint8_t storage_off;    /* do not mount the QSPI log */
  uint8_t ifs_erase;      /* erase the InternalFS region raw (NVMC, SoftDevice off) before BLE starts */
  uint8_t ifs_off;        /* no InternalFS file of ours this boot (profile / twin / eco from RAM or defaults) */
  uint8_t ble_off;        /* do not start the SoftDevice / BLE */
  uint8_t rest;           /* service screen, one Warning pattern, System OFF */
} hg_bg_plan_t;
/* each rung starts a strict subset of the rung above; screen, buttons, motor, sensors and the guardian are never left out */
void hg_bg_plan(int mode, int dead_stage, hg_bg_plan_t *p);

/* ---- supervisor (timer task, every 250 ms) ------------------------------------------------------------------------------ */
#define HG_SUP_APP_MS        5000u   /* app task silent this long -> named supervisor reset (before the 8 s hardware watchdog) */
#define HG_SUP_GUARD_IO_MS   4000u   /* = HG_FS_DEADLINE_MS: a guarded call with flash I/O this recent counts as alive */
#define HG_SUP_GUARD_TOT_MS 30000u   /* = HG_FS_TOTAL_MS */
#define HG_SUP_WRITER_MS    90000u   /* a writer job this old, outside any guarded call = stuck -> storage off (no reset) */
typedef struct {
  uint32_t now, app_beat;            /* ms */
  uint8_t app_in_guard;              /* the app task is inside a guarded file call */
  uint32_t guard_since_io, guard_total;
  uint8_t writer_busy, writer_in_guard;
  uint32_t writer_job_t0;
} hg_sup_in_t;
typedef struct { uint8_t feed, reset_app, writer_stuck; } hg_sup_out_t;
typedef struct {
  uint32_t last_tick, max_tick_gap, max_app_age, max_writer_age, ticks;
  uint8_t started;
} hg_sup_t;
void hg_sup_step(hg_sup_t *s, const hg_sup_in_t *in, hg_sup_out_t *out);

/* the service text of the rest rung (u8g2_font_10x20_t_greek, checked by test_herday_glyphs.c) */
#define HG_BG_TXT_SERVICE "\xce\xa7\xcf\x81\xce\xb5\xce\xb9\xce\xac\xce\xb6\xce\xb5\xcf\x84\xce\xb1\xce\xb9 \xce\xad\xce\xbb\xce\xb5\xce\xb3\xcf\x87\xce\xbf"   /* «Χρειάζεται έλεγχο» */

#ifdef __cplusplus
}
#endif
#endif
