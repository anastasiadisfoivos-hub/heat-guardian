#include "hg_nofastmath.h"   /* FIRST: the core builds with -Ofast; NaN must stay NaN */
/* Heat Guardian 09_guardian 0.9.15 STABLE decisions. See hg_fw_stable.h. */
#include "hg_fw_stable.h"
#include "hg_fw_heal.h"
#include <string.h>

/* ---- 1. reset classification ---- */
int hg_reset_classify(uint32_t rr, int marker, int new_build)
{
  if (rr & HG_RR_RESETPIN) return HG_RST_PIN;          /* erratum 136: first */
  if (rr & HG_RR_DOG) return HG_RST_WATCHDOG;
  if (rr & HG_RR_LOCKUP) return HG_RST_LOCKUP;
  if (rr & HG_RR_SREQ) {
    if (new_build) return HG_RST_UPLOAD;
    return marker ? HG_RST_FSGUARD : HG_RST_CRASH;
  }
  if (rr & (HG_RR_OFF | HG_RR_LPCOMP | HG_RR_DIF | HG_RR_NFC | HG_RR_VBUS)) return HG_RST_WAKE;
  if (marker) return HG_RST_FSGUARD;                   /* no bit but a marker (should not happen): it still is a guard reset */
  return HG_RST_POWERON;
}
const char *hg_reset_name(int cls)
{
  static const char *const N[HG_RST_COUNT] = { "POWER-ON/BROWN-OUT", "RESET-PIN", "WATCHDOG", "FS-GUARD", "UPLOAD", "CRASH(soft reset, same build, no marker)", "LOCKUP", "WAKE" };
  return cls >= 0 && cls < HG_RST_COUNT ? N[cls] : "?";
}
int hg_reset_is_fault(int cls)
{
  return cls == HG_RST_WATCHDOG || cls == HG_RST_FSGUARD || cls == HG_RST_CRASH || cls == HG_RST_LOCKUP;
}
uint32_t hg_quick_boots_next(uint32_t prev, int cls, int new_build)
{
  if (new_build || cls == HG_RST_UPLOAD) return 0;
  if (hg_reset_is_fault(cls)) return prev >= 0xFFFFFFFEu ? prev : prev + 1u;
  return prev;
}

/* ---- 2. marker + chain ---- */
uint8_t hg_mk_pick(uint8_t gpregret2, hg_mk_ni_t *ni, int ni_valid, uint8_t *src)
{
  uint8_t m = 0, s = HG_MK_SRC_NONE;
  if (!ni_valid) memset(ni, 0, sizeof *ni);
  if (hg_heal_marker_decode(gpregret2, 0, 0, 0, 0)) { m = gpregret2; s = HG_MK_SRC_GPREGRET2; }
  else if (ni_valid && ni->pend && hg_heal_marker_decode(ni->reg, 0, 0, 0, 0)) { m = ni->reg; s = HG_MK_SRC_NOINIT; }
  ni->reg = m; ni->pend = m ? 1u : 0u;
  if (src) *src = s;
  return m;
}
void hg_mk_chain(uint8_t marker, const hg_mk_ni_t *ni, int ni_valid, uint8_t *count, uint8_t *prev_fid)
{
  uint8_t c = 0, f = 0, cause = 0, ib = 0;
  if (hg_heal_marker_decode(marker, &cause, &f, &c, &ib)) { *count = c; *prev_fid = f; return; }
  if (ni_valid && ni->gc) { *count = ni->gc > 3 ? 3 : ni->gc; *prev_fid = ni->gfid; return; }
  *count = 0; *prev_fid = 0;
}
void hg_mk_consumed(hg_mk_ni_t *ni) { ni->pend = 0; }

/* ---- 3. bounded wait ---- */
int hg_wait_bounded(hg_poll_fn poll, void *ctx, uint32_t (*now_ms)(void), void (*idle)(void *), void *idle_ctx,
                    uint32_t timeout_ms, uint32_t *elapsed_ms)
{
  uint32_t t0 = now_ms();
  int r;
  for (;;) {
    r = poll(ctx);
    if (r != 0) break;
    if ((uint32_t)(now_ms() - t0) >= timeout_ms) {
      r = poll(ctx);                                   /* one last look: pre-empted past the deadline != timed out */
      if (r == 0) { if (elapsed_ms) *elapsed_ms = now_ms() - t0; return HG_WAIT_TIMEOUT; }
      break;
    }
    if (idle) idle(idle_ctx);
  }
  if (elapsed_ms) *elapsed_ms = now_ms() - t0;
  return r > 0 ? HG_WAIT_OK : HG_WAIT_ERROR;
}

/* ---- 4. verified wake ---- */
int hg_flash_wake(uint32_t expect_id, uint32_t (*try_fn)(int attempt, void *ctx), void *ctx, int tries)
{
  if (tries < 1) tries = 1;
  for (int a = 0; a < tries; a++) if (try_fn(a, ctx) == expect_id) return a + 1;
  return -1;
}

/* ---- 5. battery filter ---- */
int hg_vbat_step(hg_vbat_filt_t *f, float v, int buzzing, int charging, int low_mode, float thr)
{
  if (buzzing) { f->skipped++; return HG_VBAT_SKIP; }
  if (!(v == v)) return HG_VBAT_KEEP;                  /* NaN: no reading */
  if (charging || low_mode || !(v > 2.5f) || !(v < thr)) {
    if (f->low_n && !low_mode && !charging) f->low_rejected++;   /* a low run that ended before latching */
    f->low_n = 0;
    return HG_VBAT_KEEP;
  }
  if (f->low_n < 255) f->low_n++;
  if (f->low_n >= HG_VBAT_LOW_N) { f->low_n = 0; return HG_VBAT_ENTER_LOW; }
  return HG_VBAT_KEEP;
}
