#include "hg_nofastmath.h"   /* FIRST: the core builds with -Ofast; NaN must stay NaN */
/* Heat Guardian 09_guardian 0.9.17 UI engine: button gestures, haptic sequencer, wrist raise. See hg_fw_ui.h. */
#include "hg_fw_ui.h"
#include <string.h>
#include <math.h>

/* ================================================================== button */
static void push(hg_ui_t *u, uint8_t type, uint8_t arg, uint16_t dur, uint32_t t)
{
  if (u->qn >= HG_UI_EVQ) { u->qdrop++; return; }
  hg_ui_ev_t *e = &u->q[(u->qh + u->qn) % HG_UI_EVQ];
  e->type = type; e->arg = arg; e->dur_ms = dur; e->t_ms = t; u->qn++;
}
int hg_ui_pop(hg_ui_t *u, hg_ui_ev_t *e)
{
  if (!u->qn) return 0;
  *e = u->q[u->qh]; u->qh = (uint8_t)((u->qh + 1) % HG_UI_EVQ); u->qn--;
  return 1;
}
void hg_ui_init(hg_ui_t *u) { memset(u, 0, sizeof *u); }
void hg_ui_wake_hold(hg_ui_t *u, uint32_t now) { u->wake_hold = 1; u->wake_t = now; }

uint8_t hg_ui_off_blocked(const hg_ui_t *u, uint32_t now)
{
  if (u->help_on) return HG_UI_R_HELP;
  if (u->ctx.alert) return HG_UI_R_ALERT;
  if (u->had_help && (uint32_t)(now - u->help_end) < HG_UI_OFF_AFTER_HELP_MS) return HG_UI_R_AFTER_HELP;
  return 0;
}

void hg_ui_ctx(hg_ui_t *u, const hg_ui_ctx_t *c, uint32_t now)
{
  if (c->help && !u->ctx.help && !u->help_on) { u->help_on = 1; u->help_t0 = now; }          /* HELP from the phone */
  if (!c->help && u->ctx.help) { if (u->help_on || !u->had_help || (uint32_t)(now - u->help_end) > 2000u) u->help_end = now;
                                 u->help_on = 0; u->had_help = 1; }                          /* HELP ended (any source) */
  u->ctx = *c;
}

static void on_down(hg_ui_t *u, uint32_t t)
{
  u->t_down = t; u->consumed = 0;
  if (u->prompt) u->prompt_input = t;
  push(u, HG_UI_E_DOWN, 0, 0, t);
}
static void on_up(hg_ui_t *u, uint32_t t)
{
  uint32_t dur = t - u->t_down;
  push(u, HG_UI_E_UP, u->consumed, (uint16_t)(dur > 65535u ? 65535u : dur), t);
  if (u->consumed) return;                                       /* the hold already gave HELP / cancel / locked */
  if (dur < HG_UI_SHORT_MAX_MS) {
    if (u->prompt) {                                             /* the off prompt: one press = yes ... */
      u->prompt = 0; u->have_short = 0;
      if ((uint32_t)(u->t_down - u->prompt_t0) < HG_UI_OFF_GUARD_MS) push(u, HG_UI_E_PWR_CANCEL, HG_UI_R_GUARD, (uint16_t)dur, t);   /* ... not a 3rd fast tap */
      else push(u, HG_UI_E_PWR_CONFIRM, 0, (uint16_t)dur, t);
      return;
    }
    if (u->have_short && (uint32_t)(u->t_down - u->last_short_up) <= HG_UI_DOUBLE_GAP_MS) {
      u->have_short = 0;
      uint8_t r = hg_ui_off_blocked(u, t);
      if (r) { push(u, HG_UI_E_SHORT, 0, (uint16_t)dur, t); push(u, HG_UI_E_PWR_REFUSED, r, 0, t); }
      else { u->prompt = 1; u->prompt_t0 = u->prompt_input = t; push(u, HG_UI_E_PWR_PROMPT, 0, (uint16_t)dur, t); }
      return;
    }
    push(u, HG_UI_E_SHORT, 0, (uint16_t)dur, t);
    u->have_short = 1; u->last_short_up = t;
    return;
  }
  u->have_short = 0;                                             /* 1.2 - 3.0 s: nothing (owner decision) */
  if (u->prompt) u->prompt_input = t;
  push(u, HG_UI_E_MID, 0, (uint16_t)dur, t);
}
static void timers(hg_ui_t *u, uint32_t now)
{
  if (u->stable && u->raw && !u->consumed && (uint32_t)(now - u->t_down) >= HG_UI_HELP_MS) {   /* still pressed now (a release being debounced is not a hold) */
    u->consumed = 1; u->have_short = 0;
    if (u->prompt) { u->prompt = 0; push(u, HG_UI_E_PWR_CANCEL, HG_UI_R_HELP, 0, now); }
    if (u->help_on) {
      if ((uint32_t)(now - u->help_t0) >= HG_UI_HELP_LOCK_MS) { u->help_on = 0; u->help_end = now; u->had_help = 1; push(u, HG_UI_E_HELP_CANCEL, 0, 0, now); }
      else push(u, HG_UI_E_HELP_LOCKED, 0, 0, now);
    } else { u->help_on = 1; u->help_t0 = now; push(u, HG_UI_E_HELP, 0, 0, now); }
  }
  if (u->prompt) {
    uint8_t r = u->help_on ? HG_UI_R_HELP : u->ctx.alert ? HG_UI_R_ALERT : 0;
    if (r) { u->prompt = 0; push(u, HG_UI_E_PWR_CANCEL, r, 0, now); }
    else if (!u->stable && (uint32_t)(now - u->prompt_input) >= HG_UI_OFF_TIMEOUT_MS) { u->prompt = 0; push(u, HG_UI_E_PWR_CANCEL, HG_UI_R_TIMEOUT, 0, now); }
  }
}
void hg_ui_sample(hg_ui_t *u, uint8_t pressed, uint32_t now)
{
  pressed = pressed ? 1 : 0;
  if (u->wake_hold) {                                            /* the wake press is not a command */
    if (pressed) u->wake_t = now;
    else if ((uint32_t)(now - u->wake_t) >= HG_UI_WAKE_QUIET_MS) { u->wake_hold = 0; u->raw = u->stable = 0; u->raw_t = now; }
    return;
  }
  if (pressed != u->raw) { u->raw = pressed; u->raw_t = now; }
  if (u->raw != u->stable) {
    if (u->raw && (uint32_t)(now - u->raw_t) >= HG_UI_DB_PRESS_MS) { u->stable = 1; on_down(u, u->raw_t); }
    else if (!u->raw && (uint32_t)(now - u->raw_t) >= HG_UI_DB_REL_MS) { u->stable = 0; on_up(u, u->raw_t); }
  }
  timers(u, now);
}
uint8_t hg_ui_active(const hg_ui_t *u, uint32_t now)
{
  return (uint8_t)(u->wake_hold || u->raw || u->stable || u->raw != u->stable || u->prompt ||
                   (u->have_short && (uint32_t)(now - u->last_short_up) <= HG_UI_DOUBLE_GAP_MS + 50u));
}
const char *hg_ui_ev_name(uint8_t t)
{
  static const char *N[HG_UI_E_N] = { "none", "down", "short", "mid", "help", "help_cancel", "help_locked", "pwr_prompt", "pwr_confirm",
                                      "pwr_cancel", "pwr_refused", "up", "hap_done", "hap_fail" };
  return t < HG_UI_E_N ? N[t] : "?";
}

/* ================================================================== haptic sequencer */
#define W(n) (uint8_t)(0x80 | (n))   /* DRV2605L wait slot: n x 10 ms */
static const hg_hpat_t PAT[HG_HP_N] = {
  /* id                 wave                                                prio reps gap    name */
  [HG_HP_NONE]        = { { 0 },                                              0, 0, 0,     "none" },
  [HG_HP_TICK]        = { { 2, 0 },                                           0, 1, 0,     "tick" },      /* press-down: the click the band always gave (60 %) */
  [HG_HP_YES]         = { { 10, 0 },                                          1, 1, 0,     "yes" },       /* taken: I'm OK, done, cancel done, responsive */
  [HG_HP_CUE]         = { { 2, W(25), 2, 0 },                                 1, 1, 0,     "cue" },       /* Her Day tip, family message: soft double */
  [HG_HP_WATCH]       = { { 15, W(40), 15, 0 },                               2, 1, 0,     "watch" },     /* water reminder: 2 long pulses (unchanged) */
  [HG_HP_COOL]        = { { 15, W(30), 15, W(30), 15, 0 },                    2, 2, 10000, "cool" },      /* cooler-place reminder: 3 long, again after 10 s */
  [HG_HP_URGENT]      = { { 16, W(100), 16, W(100), 16, W(100), 16, 0 },      3, 4, 500,   "urgent" },    /* CHECK / DANGER / escalation: 1 s on 1 s off ~30 s */
  [HG_HP_HELP]        = { { 16, 52, 0 },                                      4, 1, 0,     "help" },      /* HELP taken: 1 s alert + pulsing strong */
  [HG_HP_HELP_URGENT] = { { 16, W(100), 16, W(100), 16, W(100), 16, 0 },      4, 4, 500,   "help_urgent" },
  [HG_HP_WORKED]      = { { 12, 0 },                                          1, 1, 0,     "worked" },    /* «Μπράβο, δροσίζεστε»: triple click */
  [HG_HP_QUESTION]    = { { 7, W(20), 7, W(20), 1, 0 },                       1, 1, 0,     "question" },  /* «Απενεργοποίηση;»: bump, bump, CLICK (no ramp: 70 was a long fading buzz) */
  [HG_HP_OFF]         = { { 17, W(8), 18, W(8), 19, 0 },                      1, 1, 0,     "off" },       /* three clicks falling */
  [HG_HP_ON]          = { { 19, W(8), 18, W(8), 17, 0 },                      1, 1, 0,     "on" },        /* three clicks rising */
  [HG_HP_BUZZ]        = { { 10, W(10), 10, 0 },                               1, 1, 0,     "buzz" },      /* the bench `buzz` (07 "Drink") */
  [HG_HP_RAW]         = { { 0 },                                              1, 1, 60,    "raw" },       /* `vib <effect> [ms]` */
};
const hg_hpat_t *hg_hp_pat(uint8_t id) { return &PAT[id < HG_HP_N ? id : 0]; }
int hg_hp_find(const char *name)
{
  for (int i = 1; i < HG_HP_N; i++) if (name && strcmp(name, PAT[i].name) == 0) return i;
  return 0;
}
static const uint8_t TICKW[8] = { 2, 0 };
void hg_hp_init(hg_hp_t *h) { memset(h, 0, sizeof *h); }
static void start_seg(hg_hp_t *h, const hg_hp_drv_t *d, uint32_t now)
{
  int rc = d->go(d->ctx, h->wave);
  if (rc != 0) { if (d->reinit(d->ctx) == 0) rc = d->go(d->ctx, h->wave); }   /* motor silent: re-init once, try again */
  if (rc != 0) { h->fails++; h->fail_id = h->id; h->phase = HG_HP_IDLE; h->last_end = now; return; }
  h->phase = HG_HP_PLAY; h->t_go = h->t_poll = now; h->errs = 0;
}
static uint32_t raw_until;
int hg_hp_request(hg_hp_t *h, const hg_hp_drv_t *d, uint8_t id, uint8_t soft, uint8_t raw_effect, uint16_t raw_ms, uint32_t now)
{
  if (id == HG_HP_NONE || id >= HG_HP_N) return 0;
  const hg_hpat_t *p = &PAT[id];
  uint32_t start = now;
  if (h->phase != HG_HP_IDLE) {
    if (p->prio < h->prio) {
      if (id == HG_HP_TICK && h->phase == HG_HP_GAP && !h->ovl && (int32_t)(h->t - now) >= HG_HP_OVERLAY_MIN && d->go(d->ctx, TICKW) == 0) {
        h->ovl = 1; h->ovl_t = h->t_poll = now; h->overlays++; return 2;
      }
      h->dropped++; return 0;
    }
    if (h->phase == HG_HP_PLAY || h->ovl) { d->stop(d->ctx); h->last_end = now; start = now + HG_HP_PREEMPT_MS; }
    h->preempts++; h->ovl = 0;
  }
  h->id = id; h->prio = p->prio; h->soft = (uint8_t)(soft && id != HG_HP_TICK);
  memcpy(h->wave, p->wave, 8);
  h->reps_left = p->reps; h->gap = p->rep_gap_ms;
  if (id == HG_HP_RAW) {
    memset(h->wave, 0, 8); h->wave[0] = raw_effect;
    if (raw_ms) { h->reps_left = 255; raw_until = now + (raw_ms > 10000u ? 10000u : raw_ms); } else raw_until = now;
  }
  if (h->soft) { memset(h->wave, 0, 8); h->wave[0] = 2; if (h->gap < 3000) h->gap = 3000; }   /* low battery: one soft click per repeat */
  h->played++; h->done_id = 0;
  h->phase = HG_HP_WAIT; h->t = start;
  if ((int32_t)(now - start) >= 0) start_seg(h, d, now);
  return 1;
}
void hg_hp_stop(hg_hp_t *h, const hg_hp_drv_t *d, uint8_t max_prio, uint32_t now)
{
  if (h->phase == HG_HP_IDLE || h->prio > max_prio) return;
  if (h->phase == HG_HP_PLAY || h->ovl) { d->stop(d->ctx); h->last_end = now; }
  h->phase = HG_HP_IDLE; h->ovl = 0;
}
static void seg_done(hg_hp_t *h, uint32_t now)
{
  h->last_end = now;
  int more = h->reps_left > 1 && !(h->id == HG_HP_RAW && (int32_t)(now - raw_until) >= 0);
  if (more) { h->reps_left--; h->phase = HG_HP_GAP; h->t = now + h->gap; }
  else { h->phase = HG_HP_IDLE; h->done_id = h->id; }
}
void hg_hp_step(hg_hp_t *h, const hg_hp_drv_t *d, uint32_t now)
{
  switch (h->phase) {
    case HG_HP_WAIT: if ((int32_t)(now - h->t) >= 0) start_seg(h, d, now); break;
    case HG_HP_PLAY:
      if ((uint32_t)(now - h->t_go) > HG_HP_PLAY_MAX_MS) { d->stop(d->ctx); seg_done(h, now); break; }
      if ((uint32_t)(now - h->t_poll) >= HG_HP_POLL_MS) {
        h->t_poll = now;
        int b = d->busy(d->ctx);
        if (b < 0) { if (++h->errs >= 3) seg_done(h, now); }   /* the read fails: assume it ended */
        else if (b == 0) seg_done(h, now);
      }
      break;
    case HG_HP_GAP:
      if (h->ovl && ((uint32_t)(now - h->t_poll) >= HG_HP_POLL_MS)) {
        h->t_poll = now;
        if (d->busy(d->ctx) <= 0 || (uint32_t)(now - h->ovl_t) > 500u) { h->ovl = 0; h->last_end = now; }
      }
      if ((int32_t)(now - h->t) >= 0) { if (h->ovl) { d->stop(d->ctx); h->ovl = 0; } start_seg(h, d, now); }
      break;
    default: break;
  }
}
uint8_t hg_hp_busy(const hg_hp_t *h) { return (uint8_t)(h->phase == HG_HP_PLAY || h->ovl); }
uint8_t hg_hp_active(const hg_hp_t *h) { return (uint8_t)(h->phase != HG_HP_IDLE); }

/* ================================================================== wrist raise */
void hg_rz_init(hg_rz_t *r, int8_t axis, int8_t sign)
{
  memset(r, 0, sizeof *r);
  r->axis = (int8_t)(axis < 0 || axis > 2 ? 2 : axis); r->sign = (int8_t)(sign < 0 ? -1 : 1);
}
int hg_rz_sample(hg_rz_t *r, float x, float y, float z, uint32_t now)
{
  if (!(x == x) || !(y == y) || !(z == z)) return 0;
  const float m = sqrtf(x * x + y * y + z * z);
  const float a = r->axis == 0 ? x : r->axis == 1 ? y : z;
  const float f = m > 0.3f ? (float)r->sign * a / m : 0.0f;
  r->mag[r->i] = m; r->face[r->i] = f; r->t[r->i] = now;
  r->i = (uint8_t)((r->i + 1) % HG_RZ_N); if (r->n < HG_RZ_N) r->n++;
  if (f < HG_RZ_FROM) { r->last_low = now; r->armed = 1; }
  if (f < HG_RZ_FACE - 0.10f) r->was_up = 0;                     /* left the face-up position: the next raise counts */
  if (f < HG_RZ_FACE || r->was_up || !r->armed) return 0;
  /* walking before the raise: impacts in the second that ended 1 s ago */
  int steps = 0;
  for (int k = 0; k < r->n; k++) {
    uint32_t age = now - r->t[k];
    if (age >= 1000u && age < 2000u && fabsf(r->mag[k] - 1.0f) > HG_RZ_STEP_G) steps++;
  }
  const uint32_t still_ms = steps >= 3 ? HG_RZ_STILL_WALK_MS : HG_RZ_STILL_MS;
  /* face up and still for still_ms (every sample of the window), the window long enough */
  float s = 0.0f; int n = 0; uint32_t oldest = now;
  for (int k = 0; k < r->n; k++) {
    uint32_t age = now - r->t[k];
    if (age > still_ms) continue;
    if (r->face[k] < HG_RZ_FACE) return 0;
    s += r->mag[k]; n++; if ((int32_t)(r->t[k] - oldest) < 0) oldest = r->t[k];
  }
  if (n < 3 || (uint32_t)(now - oldest) + 45u < still_ms) return 0;
  const float mean = s / (float)n;
  for (int k = 0; k < r->n; k++) if ((uint32_t)(now - r->t[k]) <= still_ms && fabsf(r->mag[k] - mean) > HG_RZ_STILL_G) return 0;
  /* the tilt came fast: "arm down" less than 1 s before the still window started */
  const uint32_t still_start = now - still_ms;
  if ((int32_t)(still_start - r->last_low) > (int32_t)HG_RZ_TILT_MS) return 0;
  if (r->last_wake && (uint32_t)(now - r->last_wake) < HG_RZ_REFRACT_MS) return 0;
  r->was_up = 1; r->last_wake = now; if (!r->last_wake) r->last_wake = 1; r->wakes++;
  if (steps >= 3) r->walk_rejects++;   /* (counted: a raise that needed the longer hold) */
  return 1;
}
