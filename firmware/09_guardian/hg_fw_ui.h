/* Heat Guardian 09_guardian 0.9.17 (session FW-UI, plan FW-WORLDCLASS B.2 / C + the OWNER DECISIONS of Nov 19): the UI engine.
 * Plain C99, no malloc, no hardware, time passed in (ms): host-tested in fw/tools/test_ui.c with simulated time.
 *
 *  button   : debounce on polled samples, then exactly THREE actions (owner decision Nov 19 17:29):
 *               press (< 1.2 s)        -> HG_UI_E_SHORT
 *               hold 3 s               -> HG_UI_E_HELP; in HELP: HG_UI_E_HELP_CANCEL, or HG_UI_E_HELP_LOCKED in its first 10 s
 *               double press           -> HG_UI_E_PWR_PROMPT («Απενεργοποίηση;»), then one press -> HG_UI_E_PWR_CONFIRM,
 *                                         5 s without input -> HG_UI_E_PWR_CANCEL. Refused (the 2nd press is a plain SHORT +
 *                                         HG_UI_E_PWR_REFUSED) during HELP, during any alert, and for 60 s after a HELP (demo-b7u).
 *               released 1.2 - 3.0 s   -> HG_UI_E_MID: nothing happens.
 *             HG_UI_E_DOWN on every accepted press-down: the caller plays the tick at once (the UI task does, see hgui).
 *  haptics  : one sequencer, priorities (HELP 4 > urgent 3 > watch/cool 2 > confirmations 1 > tick 0). An equal or higher
 *             request stops the current pattern, waits 60 ms and starts; a lower one is dropped. A tick in the GAP of a
 *             higher pattern is played in the gap ("overlay") when >= 120 ms of gap are left, else skipped.
 *             The motor is reached through a driver struct (go / busy / stop / reinit); a GO that fails re-inits the
 *             driver once and tries again; if that fails too the pattern is reported (HG_UI_E_HAP_FAIL) so the caller can
 *             show the alert another way (screen flash + EVENTS 16). Never silently skipped.
 *  raise    : wrist-raise detector on the 25 Hz accelerometer samples (owner decision Nov 19 18:31): a FAST tilt of the
 *             band's face towards the sky followed by a still hold. Arm swing while walking never holds still long enough. */
#ifndef HG_FW_UI_H
#define HG_FW_UI_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* ---- button timing (ms) ---- */
#define HG_UI_DB_PRESS_MS     8      /* low and still low 8 ms later = a press (rejects motor / cable glitches) */
#define HG_UI_DB_REL_MS       30     /* high for 30 ms without a break = released (a re-press inside 30 ms is merged) */
#define HG_UI_SHORT_MAX_MS    1200   /* released before 1.2 s = a press */
#define HG_UI_HELP_MS         3000   /* held 3 s = HELP (owner: was 2 s) */
#define HG_UI_DOUBLE_GAP_MS   900    /* release of the 1st press -> down of the 2nd: a double press ([FLASH-EASY] demo-b7u: was 700) */
#define HG_UI_HELP_LOCK_MS    10000  /* no cancel in the first 10 s of a HELP */
#define HG_UI_OFF_TIMEOUT_MS  5000   /* the off prompt closes after 5 s without input */
#define HG_UI_OFF_GUARD_MS    400    /* a press starting < 400 ms after the prompt opened (a 3rd fast tap) cancels it ([FLASH-EASY]: was
                                        700; the prompt is painted ~0.3-0.5 s after it opens, so a real "yes" landed inside 700) */
#define HG_UI_OFF_AFTER_HELP_MS 60000u    /* no off prompt for 60 s after a HELP ended ([FLASH-EASY] demo build: was 10 min) */
#define HG_UI_WAKE_QUIET_MS   500    /* the press that woke the band from System OFF: ignored until released 500 ms */

enum { HG_UI_E_NONE = 0, HG_UI_E_DOWN, HG_UI_E_SHORT, HG_UI_E_MID, HG_UI_E_HELP, HG_UI_E_HELP_CANCEL, HG_UI_E_HELP_LOCKED,
       HG_UI_E_PWR_PROMPT, HG_UI_E_PWR_CONFIRM, HG_UI_E_PWR_CANCEL, HG_UI_E_PWR_REFUSED, HG_UI_E_UP,
       HG_UI_E_HAP_DONE, HG_UI_E_HAP_FAIL, HG_UI_E_N };
/* arg of PWR_CANCEL / PWR_REFUSED */
enum { HG_UI_R_TIMEOUT = 1, HG_UI_R_GUARD, HG_UI_R_HELP, HG_UI_R_ALERT, HG_UI_R_AFTER_HELP };

typedef struct { uint8_t type, arg; uint16_t dur_ms; uint32_t t_ms; } hg_ui_ev_t;   /* t = event time; dur = press length */
typedef struct { uint8_t help, alert; } hg_ui_ctx_t;   /* from the application: HELP active, any alert / CHECK / reminder open */

#define HG_UI_EVQ 16
typedef struct {
  /* debounce */
  uint8_t raw, stable; uint32_t raw_t;          /* raw level (1 = pressed) and since when */
  /* gesture */
  uint8_t consumed;                             /* this hold already gave HELP / cancel / locked */
  uint32_t t_down;
  uint32_t last_short_up; uint8_t have_short;   /* the last SHORT release (double-press window) */
  uint8_t prompt; uint32_t prompt_t0, prompt_input;
  uint8_t help_on; uint32_t help_t0, help_end; uint8_t had_help;
  hg_ui_ctx_t ctx;
  uint8_t wake_hold; uint32_t wake_t;
  /* event queue */
  hg_ui_ev_t q[HG_UI_EVQ]; uint8_t qh, qn; uint16_t qdrop;
} hg_ui_t;

void hg_ui_init(hg_ui_t *u);
void hg_ui_wake_hold(hg_ui_t *u, uint32_t now);                 /* boot after a wake from System OFF */
void hg_ui_ctx(hg_ui_t *u, const hg_ui_ctx_t *c, uint32_t now);  /* any time; edges of help are tracked here */
void hg_ui_sample(hg_ui_t *u, uint8_t pressed, uint32_t now);    /* one poll of the button line (1 = pressed) + timers */
int  hg_ui_pop(hg_ui_t *u, hg_ui_ev_t *e);                      /* 1 = an event was taken */
uint8_t hg_ui_active(const hg_ui_t *u, uint32_t now);           /* 1 = poll fast (pressed, debouncing, a window open) */
uint8_t hg_ui_off_blocked(const hg_ui_t *u, uint32_t now);      /* 0 or HG_UI_R_* */
const char *hg_ui_ev_name(uint8_t t);

/* ---- haptic sequencer ---- */
enum { HG_HP_NONE = 0, HG_HP_TICK, HG_HP_YES, HG_HP_CUE, HG_HP_WATCH, HG_HP_COOL, HG_HP_URGENT, HG_HP_HELP, HG_HP_HELP_URGENT,
       HG_HP_WORKED, HG_HP_QUESTION, HG_HP_OFF, HG_HP_ON, HG_HP_BUZZ, HG_HP_RAW, HG_HP_N };
#define HG_HP_PREEMPT_MS  60
#define HG_HP_OVERLAY_MIN 120
#define HG_HP_PLAY_MAX_MS 8000      /* one DRV sequence never plays longer (the 8 slots are < 4 s) */
#define HG_HP_POLL_MS     20
typedef struct { uint8_t wave[8]; uint8_t prio, reps; uint16_t rep_gap_ms; const char *name; } hg_hpat_t;
const hg_hpat_t *hg_hp_pat(uint8_t id);
int hg_hp_find(const char *name);                               /* id by name ("tick", "urgent" ...), 0 none */

typedef struct {
  int  (*go)(void *ctx, const uint8_t wave[8]);   /* load WAVESEQ + GO; 0 ok */
  int  (*busy)(void *ctx);                        /* 1 playing, 0 done, < 0 read failed */
  void (*stop)(void *ctx);
  int  (*reinit)(void *ctx);                      /* re-probe + init the driver; 0 ok */
  void *ctx;
} hg_hp_drv_t;

enum { HG_HP_IDLE = 0, HG_HP_WAIT, HG_HP_PLAY, HG_HP_GAP };
typedef struct {
  uint8_t id, prio, phase, reps_left, soft, ovl, errs;
  uint8_t wave[8];
  uint16_t gap;
  uint32_t t, t_go, t_poll, ovl_t;
  uint32_t last_end;                  /* ms of the last motor stop (VBAT / temperature sampling waits 2 s after) */
  uint32_t played, dropped, fails, overlays, preempts;
  uint8_t fail_id, done_id;           /* set by hg_hp_step: a pattern failed / finished (taken by the caller) */
} hg_hp_t;
void hg_hp_init(hg_hp_t *h);
/* request a pattern; soft = low battery (every pattern but the tick becomes one soft click, same repeats, gaps >= 3 s).
 * raw_effect / raw_ms only for HG_HP_RAW (bench `vib <effect> [ms]`). Returns 1 accepted (now or after the 60 ms pause),
 * 2 played as an overlay tick, 0 dropped (lower priority). */
int  hg_hp_request(hg_hp_t *h, const hg_hp_drv_t *d, uint8_t id, uint8_t soft, uint8_t raw_effect, uint16_t raw_ms, uint32_t now);
void hg_hp_stop(hg_hp_t *h, const hg_hp_drv_t *d, uint8_t max_prio, uint32_t now);   /* stop if the current prio <= max_prio */
void hg_hp_step(hg_hp_t *h, const hg_hp_drv_t *d, uint32_t now);
uint8_t hg_hp_busy(const hg_hp_t *h);         /* the motor may be running now */
uint8_t hg_hp_active(const hg_hp_t *h);       /* a pattern is in progress (step it every 5 ms) */

/* ---- wrist raise (accelerometer, g, 25 Hz) ---- */
#define HG_RZ_N          50          /* 2 s of history */
#define HG_RZ_FACE       0.80f       /* face up: the face axis carries >= 0.80 of |a| */
#define HG_RZ_FROM       0.45f       /* "arm down" before: the face axis < 0.45 of |a| ... */
#define HG_RZ_TILT_MS    1000        /* ... within the last 1 s (a slow roll in bed is not a raise) */
#define HG_RZ_STILL_MS   280         /* then still for 280 ms (walking: 600 ms) */
#define HG_RZ_STILL_WALK_MS 600
#define HG_RZ_STILL_G    0.06f       /* still: every |a| of the window within 0.06 g of its mean */
#define HG_RZ_STEP_G     0.25f       /* walking: | |a| - 1 g | > 0.25 g at >= 3 samples in the last 2 s */
#define HG_RZ_REFRACT_MS 3000
typedef struct {
  float mag[HG_RZ_N], face[HG_RZ_N]; uint32_t t[HG_RZ_N]; uint8_t i, n;
  int8_t axis, sign;                  /* face axis: 0 x, 1 y, 2 z; sign +1 / -1 (console `raise axis`) */
  uint32_t last_low, last_wake; uint8_t was_up, armed;
  uint32_t wakes, walk_rejects;
} hg_rz_t;
void hg_rz_init(hg_rz_t *r, int8_t axis, int8_t sign);
int  hg_rz_sample(hg_rz_t *r, float x, float y, float z, uint32_t now);   /* 1 = wrist raised: wake the screen */

#ifdef __cplusplus
}
#endif
#endif
