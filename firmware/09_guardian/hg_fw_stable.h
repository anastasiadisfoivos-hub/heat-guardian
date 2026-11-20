/* Heat Guardian 09_guardian 0.9.15 STABLE: the plain-C decisions behind the reset / hang fixes.
 * No hardware access: the sketch does the I/O, this module decides. Host-tested in fw/tools/test_stable.c.
 *
 *   1. reset classification (FW-WORLDCLASS plan A-09 / A-10): which reset this boot follows, and whether it is
 *      boot-loop evidence. RESETPIN is tested FIRST (nRF52840 erratum 136: after a pin reset other RESETREAS
 *      bits can be set). A reset the user caused (pin, power cycle, wake) never counts as a quick boot.
 *   2. the FS-guard marker kept in .hg_noinit RAM as well as GPREGRET2 (plan A-01): GPREGRET2 is cleared by a
 *      watchdog or pin reset, the RAM copy is not, so a reset between "marker read" and "heal state saved"
 *      no longer loses the ladder rung. The guard-reset chain count also lives there.
 *   3. a bounded wait (plan A-06 / B.5 rule 1): every wait on the flash has a deadline and an error path.
 *   4. the JEDEC-verified flash wake with a bounded number of tries (plan A-04).
 *   5. the battery filter (plan A-14): no sample while the motor runs or < 2 s after, three low samples in a row.
 */
#ifndef HG_FW_STABLE_H
#define HG_FW_STABLE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* ---- 1. reset classification ---------------------------------------------------------------------- */
/* nRF52840 POWER->RESETREAS bits (PS v1.7, 5.3.7.11) */
#define HG_RR_RESETPIN 0x00000001u
#define HG_RR_DOG      0x00000002u
#define HG_RR_SREQ     0x00000004u
#define HG_RR_LOCKUP   0x00000008u
#define HG_RR_OFF      0x00010000u
#define HG_RR_LPCOMP   0x00020000u
#define HG_RR_DIF      0x00040000u
#define HG_RR_NFC      0x00080000u
#define HG_RR_VBUS     0x00100000u
enum {
  HG_RST_POWERON = 0,  /* no bit: power-on or brown-out (a power cycle by the user, or a flat battery) */
  HG_RST_PIN,          /* RESETPIN (tested first, erratum 136): the user pressed reset / double-tap for the bootloader */
  HG_RST_WATCHDOG,     /* DOG: the 8 s hardware watchdog */
  HG_RST_FSGUARD,      /* soft reset with an FS-guard marker (GPREGRET2 or its .hg_noinit copy) */
  HG_RST_UPLOAD,       /* soft reset into a NEW build */
  HG_RST_CRASH,        /* soft reset, same build, no marker: hard fault / SoftDevice fault (the core soft-resets) */
  HG_RST_LOCKUP,       /* CPU lock-up */
  HG_RST_WAKE,         /* wake from System OFF (OFF, LPCOMP, DIF, NFC or VBUS) */
  HG_RST_COUNT
};
int hg_reset_classify(uint32_t resetreas, int marker, int new_build);
const char *hg_reset_name(int cls);
/* 1 = an unexpected reset: boot-loop evidence (watchdog, fs-guard, crash, lock-up). 0 = the user / an upload. */
int hg_reset_is_fault(int cls);
/* boot.bin quick_boots after this boot: an upload starts at 0, a fault adds one, anything else leaves it as it was */
uint32_t hg_quick_boots_next(uint32_t prev, int cls, int new_build);

/* ---- 2. the FS-guard marker and the guard-reset chain in .hg_noinit ------------------------------- */
typedef struct {
  uint8_t pend;   /* 1 = reg holds a marker that this or an earlier boot has NOT yet saved into the heal state */
  uint8_t reg;    /* the marker byte (hg_heal_marker_encode) */
  uint8_t gc;     /* guard resets in a row so far (the ladder rung; 0 after 10 min stable) */
  uint8_t gfid;   /* file id of the last guard reset (its class: QSPI log or InternalFS) */
} hg_mk_ni_t;
enum { HG_MK_SRC_NONE = 0, HG_MK_SRC_GPREGRET2 = 1, HG_MK_SRC_NOINIT = 2 };
/* First thing at boot: the marker this boot must count. GPREGRET2 if it holds one, else a marker an earlier boot
 * read but never saved (ni->pend). The result is written back to ni (pend = 1) BEFORE anything can time out.
 * ni_valid = 0: the RAM did not survive (power-on), ni is initialised. *src = HG_MK_SRC_*. */
uint8_t hg_mk_pick(uint8_t gpregret2, hg_mk_ni_t *ni, int ni_valid, uint8_t *src);
/* the guard-reset chain at boot: from the marker if there is one, else from the RAM copy (a watchdog reset in
 * the middle of a chain keeps the rung), else 0 */
void hg_mk_chain(uint8_t marker, const hg_mk_ni_t *ni, int ni_valid, uint8_t *count, uint8_t *prev_fid);
/* after the heal state that counted the marker is saved: the marker is consumed (the sketch then clears GPREGRET2) */
void hg_mk_consumed(hg_mk_ni_t *ni);

/* ---- 3. bounded wait --------------------------------------------------------------------------------- */
enum { HG_WAIT_OK = 0, HG_WAIT_TIMEOUT = -1, HG_WAIT_ERROR = -2 };
/* poll: 1 = done, 0 = not yet, < 0 = error (stop). now_ms: a millisecond clock (wraps at 2^32, handled).
 * idle (may be NULL): called between polls (yield / delay / drain a FIFO). The condition is polled once more
 * after the deadline, so a task pre-empted past the deadline is not reported as a timeout when the device
 * did finish. *elapsed_ms (may be NULL) = time spent. */
typedef int (*hg_poll_fn)(void *ctx);
int hg_wait_bounded(hg_poll_fn poll, void *ctx, uint32_t (*now_ms)(void), void (*idle)(void *), void *idle_ctx,
                    uint32_t timeout_ms, uint32_t *elapsed_ms);

/* ---- 4. verified flash wake --------------------------------------------------------------------------- */
#define HG_FLASH_WAKE_TRIES 3
/* try(attempt, ctx): do the wake step of that attempt (0: plain, 1: GPIO wake + fresh peripheral, 2: + chip
 * software reset) and return the JEDEC id read afterwards. Returns the number of attempts used (1..tries) when
 * the id matched, or -1 when every try failed (the caller reports LFS_ERR_IO, never proceeds on a sleeping chip). */
int hg_flash_wake(uint32_t expect_id, uint32_t (*try_fn)(int attempt, void *ctx), void *ctx, int tries);

/* ---- 5. battery filter ------------------------------------------------------------------------------- */
#define HG_VBAT_LOW_N 3          /* low readings in a row before low-battery mode latches */
typedef struct {
  uint8_t  low_n;                /* low readings in a row so far */
  uint32_t skipped;              /* samples not taken because the motor ran (stat) */
  uint32_t low_rejected;         /* single low readings that did NOT latch (stat) */
} hg_vbat_filt_t;
enum { HG_VBAT_SKIP = -1, HG_VBAT_KEEP = 0, HG_VBAT_ENTER_LOW = 1 };
/* buzzing = motor running or < 2 s after it stopped: the sample is not taken at all (caller keeps the last value).
 * Returns HG_VBAT_ENTER_LOW on the HG_VBAT_LOW_N-th low reading in a row (v < thr, v > 2.5 V, not charging, not
 * already in low mode). A NaN reading changes nothing. */
int hg_vbat_step(hg_vbat_filt_t *f, float v, int buzzing, int charging, int low_mode, float thr);

#ifdef __cplusplus
}
#endif
#endif
