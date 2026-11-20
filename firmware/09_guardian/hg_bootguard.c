#include "hg_nofastmath.h"   /* FIRST: the core builds with -Ofast; NaN must stay NaN */
/* Heat Guardian 09_guardian 0.9.16 BOOT GUARD decisions. See hg_bootguard.h. */
#include "hg_bootguard.h"
#include <string.h>

/* ---- reset classes ---- */
int hg_bg_classify(int base_cls, uint8_t rcode)
{
  if (base_cls != HG_RST_CRASH) return base_cls;
  switch (rcode) {
    case HG_BG_RC_SUPERVISOR: return HG_BG_RST_SUPERVISOR;
    case HG_BG_RC_ASSERT:     return HG_BG_RST_ASSERT;
    case HG_BG_RC_STACK:      return HG_BG_RST_STACK;
    case HG_BG_RC_MALLOC:     return HG_BG_RST_MALLOC;
    case HG_BG_RC_INJECT:     return HG_BG_RST_INJECT;
    case HG_BG_RC_REBOOT:     return HG_BG_RST_REBOOT;
    default:                  return HG_RST_CRASH;   /* hard fault / SoftDevice fault: the core soft-resets with no trace */
  }
}
const char *hg_bg_class_name(int cls)
{
  static const char *const N[HG_BG_RST_COUNT] = { "POWER-ON", "RESET-PIN", "WATCHDOG", "FS-GUARD", "UPLOAD", "CRASH", "LOCKUP", "WAKE",
                                                  "SUPERVISOR", "ASSERT", "STACK", "MALLOC", "FAULT-INJECT", "REBOOT" };
  return cls >= 0 && cls < HG_BG_RST_COUNT ? N[cls] : "?";
}
int hg_bg_is_fault(int cls)
{
  if (cls >= HG_BG_RST_SUPERVISOR && cls <= HG_BG_RST_INJECT) return 1;
  return hg_reset_is_fault(cls);
}

/* ---- entries ---- */
static uint8_t crc4(uint32_t v28)                     /* CRC-4 (x^4 + x + 1) over 28 bits, MSB first */
{
  uint8_t c = 0;
  for (int i = 27; i >= 0; i--) {
    uint8_t b = (uint8_t)(((v28 >> i) & 1u) ^ ((c >> 3) & 1u));
    c = (uint8_t)((c << 1) & 0x0Fu);
    if (b) c ^= 0x03u;
  }
  return (uint8_t)(c ^ 0x05u);                       /* never 0 for an all-zero word */
}
uint32_t hg_bg_encode(const hg_bg_entry_t *e)
{
  uint32_t p = 0;
  if (e->type == HG_BG_T_STARTED)
    p = ((uint32_t)(e->cls & 0x0Fu) << 20) | ((uint32_t)(e->level & 0x07u) << 17) | ((uint32_t)(e->slow & 0x0Fu) << 13) |
        ((uint32_t)(e->cp & 0x3Fu) << 7) | (uint32_t)(e->upc & 0x7Fu);
  uint32_t v28 = ((uint32_t)(e->type & 0x0Fu) << 24) | p;
  return (v28 << 4) | crc4(v28);
}
int hg_bg_decode(uint32_t w, hg_bg_entry_t *e)
{
  if (w == 0xFFFFFFFFu) return 0;
  uint32_t v28 = w >> 4;
  hg_bg_entry_t x; memset(&x, 0, sizeof x);
  x.type = (uint8_t)(v28 >> 24);
  if ((w & 0x0Fu) != crc4(v28) || x.type < HG_BG_T_STARTED || x.type > HG_BG_T_REST) return -1;
  uint32_t p = v28 & 0xFFFFFFu;
  if (x.type == HG_BG_T_STARTED) {
    x.cls = (uint8_t)((p >> 20) & 0x0Fu); x.level = (uint8_t)((p >> 17) & 0x07u); x.slow = (uint8_t)((p >> 13) & 0x0Fu);
    x.cp = (uint8_t)((p >> 7) & 0x3Fu); x.upc = (uint8_t)(p & 0x7Fu);
    if (x.cls >= HG_BG_RST_COUNT || x.level > HG_BG_LEVEL_MAX) return -1;
  } else if (p) return -1;                           /* marks carry no payload */
  if (e) *e = x;
  return 1;
}
uint8_t hg_bg_up_encode(uint32_t ms)
{
  uint32_t s = ms / 1000u;
  if (s < 60u) return (uint8_t)s;
  uint32_t m = s / 60u;
  if (m < 60u) return (uint8_t)(59u + m);            /* 60..118 = 1..59 min */
  uint32_t h = m / 60u; uint8_t c = 119u;            /* 119 = >= 1 h, 120 = >= 2 h, 121 = >= 4 h ... 126 = >= 128 h */
  while (h >= 2u && c < 126u) { h >>= 1; c++; }
  return c;
}
uint32_t hg_bg_up_decode_s(uint8_t c)
{
  if (c >= HG_BG_UP_UNKNOWN) return 0xFFFFFFFFu;
  if (c < 60u) return c;
  if (c < 119u) return (uint32_t)(c - 59u) * 60u;
  return 3600u << (c - 119u);
}

/* ---- copies ---- */
void hg_bg_merge(hg_bg_prev_t *d, const hg_bg_prev_t *o)
{
  if (!o->valid) return;
  if (!d->valid) { *d = *o; return; }
  if (o->level > d->level) d->level = o->level;
  if (o->slow > d->slow) d->slow = o->slow;
  d->healthy = (uint8_t)(d->healthy && o->healthy);
  d->stable = (uint8_t)(d->stable && o->stable);
  d->clean = (uint8_t)(d->clean || o->clean);
  d->rest = (uint8_t)(d->rest || o->rest);
}

/* ---- scan ---- */
void hg_bg_scan(const uint32_t *page, int n, hg_bg_scan_t *s)
{
  memset(s, 0, sizeof *s);
  hg_bg_entry_t ring[HG_BG_LAST_N]; int rn = 0, rh = 0;
  for (int i = 0; i < n; i++) {
    hg_bg_entry_t e; int r = hg_bg_decode(page[i], &e);
    if (r == 0) continue;
    s->used++; s->append = i + 1;
    if (r < 0) { s->corrupt++; continue; }           /* ignored: a torn word only ever comes with a power loss */
    if (e.type == HG_BG_T_STARTED) {
      memset(&s->prev, 0, sizeof s->prev);
      s->prev.valid = 1; s->prev.level = e.level; s->prev.slow = e.slow; s->prev.cls = e.cls; s->prev.cp = e.cp; s->prev.upc = e.upc;
      s->boots++; s->by_cls[e.cls]++;
      ring[rh] = e; rh = (rh + 1) % HG_BG_LAST_N; if (rn < HG_BG_LAST_N) rn++;
    } else if (s->prev.valid) {
      if (e.type == HG_BG_T_HEALTHY) s->prev.healthy = 1;
      else if (e.type == HG_BG_T_STABLE) { s->prev.healthy = 1; s->prev.stable = 1; }
      else if (e.type == HG_BG_T_CLEAN) s->prev.clean = 1;
      else if (e.type == HG_BG_T_REST) s->prev.rest = 1;
    }
  }
  for (int k = 0; k < rn; k++) s->last[k] = ring[(rh - 1 - k + 2 * HG_BG_LAST_N) % HG_BG_LAST_N];
  s->nlast = (uint8_t)rn;
}

/* ---- append (+ compaction) ---- */
static int put_word(const hg_bg_flash_t *f, int *idx, uint32_t w)
{
  for (int t = 0; t < 2 && *idx < HG_BG_PAGE_WORDS; t++) {
    int i = (*idx)++;
    if (f->page[i] != 0xFFFFFFFFu) continue;         /* not erased (junk): never program over it */
    if (f->write_word(f->ctx, i, w) && f->page[i] == w) return 1;
  }
  return 0;
}
int hg_bg_append(const hg_bg_flash_t *f, uint32_t w)
{
  int app = 0;
  for (int i = HG_BG_PAGE_WORDS - 1; i >= 0; i--) if (f->page[i] != 0xFFFFFFFFu) { app = i + 1; break; }
  if (app >= HG_BG_PAGE_WORDS - 1) {                 /* full (one word of slack for the retry): compact */
    uint32_t keep[HG_BG_KEEP_WORDS]; int k = 0;
    for (int i = HG_BG_PAGE_WORDS - 1; i >= 0 && k < HG_BG_KEEP_WORDS; i--) if (hg_bg_decode(f->page[i], NULL) == 1) keep[k++] = f->page[i];
    if (!f->erase(f->ctx)) return 0;
    for (int i = 0; i < HG_BG_PAGE_WORDS; i++) if (f->page[i] != 0xFFFFFFFFu) return 0;   /* the erase did not take */
    app = 0;
    for (int j = k - 1; j >= 0; j--) put_word(f, &app, keep[j]);   /* oldest first; a failed one is lost, not fatal */
  }
  return put_word(f, &app, w);
}

/* ---- ladder ---- */
const char *hg_bg_mode_name(int m)
{
  static const char *const N[HG_BG_MODE_COUNT] = { "NORMAL", "CAREFUL", "SAFE", "MINIMAL", "REST" };
  return m >= 0 && m < HG_BG_MODE_COUNT ? N[m] : "?";
}
int hg_bg_mode_of(uint8_t level)
{
  if (level <= 1) return HG_BG_NORMAL;
  if (level == 2) return HG_BG_CAREFUL;
  if (level == 3) return HG_BG_SAFE;
  if (level <= 5) return HG_BG_MINIMAL;
  return HG_BG_REST;
}
static uint8_t inc_sat(uint8_t v, uint8_t max) { return v >= max ? max : (uint8_t)(v + 1u); }
void hg_bg_decide(const hg_bg_prev_t *p, int cls, hg_bg_decision_t *d)
{
  d->level = 0; d->slow = 0;
  if (!p->valid || cls == HG_RST_UPLOAD) {}          /* first boot / a new build: a fresh start */
  else if (p->rest) d->level = 3;                    /* the ladder switched the band off: a press tries again from SAFE */
  else if (!hg_bg_is_fault(cls)) {}                  /* pin, power, wake: the user asked for this reset, never a rung */
  else if (!p->healthy) { d->level = inc_sat(p->level, HG_BG_LEVEL_MAX); d->slow = inc_sat(p->slow, HG_BG_SLOW_MAX); }
  else if (!p->stable) {                             /* up 60 s but not 10 min: a slow fault */
    d->slow = inc_sat(p->slow, HG_BG_SLOW_MAX);
    if (d->slow >= HG_BG_SLOW_FROM) { uint8_t l = (uint8_t)(2u + (d->slow - HG_BG_SLOW_FROM) / 2u); d->level = l > 5u ? 5u : l; }
  }
  d->mode = (uint8_t)hg_bg_mode_of(d->level);
}
void hg_bg_boot(const uint32_t *page, const hg_bg_prev_t *ni, int cls, hg_bg_scan_t *s, hg_bg_prev_t *m, hg_bg_decision_t *d)
{
  hg_bg_scan(page, HG_BG_PAGE_WORDS, s);
  *m = s->prev;
  if (ni) hg_bg_merge(m, ni);
  hg_bg_decide(m, cls, d);
}
uint32_t hg_bg_started(int cls, const hg_bg_decision_t *d, uint8_t prev_cp, uint8_t prev_upc)
{
  hg_bg_entry_t e; memset(&e, 0, sizeof e);
  e.type = HG_BG_T_STARTED; e.cls = (uint8_t)cls; e.level = d->level; e.slow = d->slow;
  e.cp = prev_cp > HG_BG_CP_UNKNOWN ? HG_BG_CP_UNKNOWN : prev_cp; e.upc = prev_upc > HG_BG_UP_UNKNOWN ? HG_BG_UP_UNKNOWN : prev_upc;
  return hg_bg_encode(&e);
}
uint32_t hg_bg_mark(uint8_t type) { hg_bg_entry_t e; memset(&e, 0, sizeof e); e.type = type; return hg_bg_encode(&e); }
void hg_bg_cur(hg_bg_prev_t *c, int cls, const hg_bg_decision_t *d)
{
  memset(c, 0, sizeof *c);
  c->valid = 1; c->level = d->level; c->slow = d->slow; c->cls = (uint8_t)cls; c->cp = HG_BG_CP_UNKNOWN; c->upc = HG_BG_UP_UNKNOWN;
}
void hg_bg_plan(int mode, int dead, hg_bg_plan_t *p)
{
  memset(p, 0, sizeof *p);
  if (mode <= HG_BG_NORMAL) return;
  p->storage_off = 1;                                /* careful and above: no QSPI log */
  if (mode == HG_BG_CAREFUL) return;
  if (mode == HG_BG_REST) { p->rest = 1; p->ifs_off = 1; p->ble_off = 1; return; }
  p->ifs_erase = 1;                                  /* safe and above: no littlefs code can assert on InternalFS */
  if (dead == HG_BG_STG_BLE) p->ble_off = 1;         /* the stage that died is skipped */
  if (dead == HG_BG_STG_IFS || mode == HG_BG_MINIMAL) p->ifs_off = 1;
  if (p->ble_off) p->ifs_off = 1;                    /* InternalFS is only mounted by Bluefruit.begin() */
}

/* ---- supervisor ---- */
static uint32_t age(uint32_t now, uint32_t t) { return (int32_t)(now - t) < 0 ? 0u : now - t; }   /* a beat newer than "now" = 0 */
void hg_sup_step(hg_sup_t *s, const hg_sup_in_t *in, hg_sup_out_t *o)
{
  memset(o, 0, sizeof *o);
  if (s->started) { uint32_t g = age(in->now, s->last_tick); if (g > s->max_tick_gap) s->max_tick_gap = g; }
  s->started = 1; s->last_tick = in->now; s->ticks++;
  uint32_t a = age(in->now, in->app_beat);
  if (a > s->max_app_age) s->max_app_age = a;
  int alive = a < HG_SUP_APP_MS ||
              (in->app_in_guard && in->guard_since_io <= HG_SUP_GUARD_IO_MS && in->guard_total <= HG_SUP_GUARD_TOT_MS);
  o->feed = (uint8_t)alive; o->reset_app = (uint8_t)!alive;
  if (in->writer_busy) {
    uint32_t w = age(in->now, in->writer_job_t0);
    if (w > s->max_writer_age) s->max_writer_age = w;
    if (!in->writer_in_guard && w > HG_SUP_WRITER_MS) o->writer_stuck = 1;
  }
}
