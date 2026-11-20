/* Heat Guardian 09_guardian 0.9.17 (session FW-UI): the closed-loop ACTION LADDER and the "keep it green" GAUGE.
 * Glue / rules layer only: plain C99, no malloc, no hardware, reads the frozen guardian's minute output and never writes it.
 * Host-tested in fw/tools/test_ladder.c (simulated minutes).
 *
 * LADDER (OWNER DECISIONS Nov 19 18:22 + 18:23):
 *   Watch (the rules layer shows DRINK / COOL = the first line crossed by the 20-30 min forecast)
 *     -> reminder by cause: DRINK = water («Πιείτε νερό τώρα»), COOL = cooler place («Πηγαίνετε κάπου δροσερά»)
 *     -> her press = "done" -> a 20 min check: the forecast must STOP RISING (f20 <= f20 at the press + 0.05 C)
 *          worked                       -> «Μπράβο, δροσίζεστε», EVENTS LD_WORKED
 *          water did not help           -> «Ακόμα ζεσταίνεστε» + next step «Πηγαίνετε κάπου δροσερά», quiet family note
 *          still rising in the cool     -> ESCALATION: «Πατήστε αν με βλέπετε» + family alert, screen «Ξαπλώστε, βρέξτε τον λαιμό σας»
 *     -> no press: one repeat after 10 min, then (20 min) family note "no response"
 *   Danger line crossed at any time (frozen level 3 or a CHECK with the DANGER cause) -> escalation at once.
 *   A PRESS NEVER CANCELS A PREDICTION: a press is "I did it" (reminder -> 20 min check) or "I am here" (escalation -> family
 *   note "responsive", the escalation stays). Only the forecast clears: escalation ends when there is no danger and f20 has
 *   not risen over the last 20 min (or the episode is over). The frozen CHECK / IM_OK path still gets the press as before
 *   (honest input); it may clear ITS check, this layer keeps its own state, its family alert was already sent at escalation.
 * GAUGE (OWNER DECISION Nov 19 18:31): the home screen colour + a dot on a curved scale from the FORECAST f20 against her
 *   personal lines (read from the frozen state, never written), floored by the frozen state (DRINK >= yellow, COOL >= orange,
 *   DANGER = red). 5 steps green -> yellow-green -> yellow -> orange -> red, different in lightness too. */
#ifndef HG_FW_LADDER_H
#define HG_FW_LADDER_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

#define HG_LD_CHECK_MIN   20     /* the check after "done" */
#define HG_LD_REPEAT_MIN  10     /* no press: one repeat after 10 min ... */
#define HG_LD_NORESP_MIN  20     /* ... then the family note "no response" */
#define HG_LD_FLAT_C      0.05f  /* "stopped rising": f20 rose less than this */
#define HG_LD_HIST        21     /* f20 of the last 21 minutes (index 0 = now, 20 = 20 min ago) */

enum { HG_LD_IDLE = 0, HG_LD_REMIND, HG_LD_CHECK, HG_LD_ESC, HG_LD_DONE };
enum { HG_LD_S_WATER = 1, HG_LD_S_COOL = 2, HG_LD_S_ESC = 3 };                 /* step (EVENTS arg) */
enum { HG_LD_ESC_DANGER = 1, HG_LD_ESC_STILL_HEATING = 2 };                    /* LD_ESCALATED arg */
enum { HG_LD_NOTE_NOT_WORKED = 1, HG_LD_NOTE_NO_RESPONSE = 2, HG_LD_NOTE_RESPONSIVE = 3 };   /* LD_NOTE arg */
enum { HG_LD_TOAST_NONE = 0, HG_LD_TOAST_WORKED, HG_LD_TOAST_STILL };           /* «Μπράβο, δροσίζεστε» / «Ακόμα ζεσταίνεστε» */

typedef struct {
  uint8_t present;          /* the rules layer shows DRINK / COOL this minute (hg_al_out_t.present: HG_ST_DRINK / HG_ST_COOL), else 0 */
  uint8_t danger;           /* frozen: level >= 3 or a CHECK whose cause has HG_CR_DANGER */
  uint8_t episode;          /* a heat episode is on: frozen level > 0 or the rules layer still holds a shown episode */
  float f20;                /* frozen core.f20_eff (NaN = unknown) */
} hg_ld_in_t;

typedef struct { uint8_t type, arg; uint8_t x[8]; } hg_ld_ev_t;
typedef struct {
  uint8_t n; hg_ld_ev_t ev[4];   /* EVENTS to log + notify (HG_EV_LD_*) */
  uint8_t haptic;                /* HG_HP_* to play now (0 none) */
  uint8_t toast;                 /* HG_LD_TOAST_* */
  uint8_t wake;                  /* wake the screen (the ladder said something) */
} hg_ld_out_t;

typedef struct {
  uint8_t state, step, esc_reason, repeated, noresp;
  uint16_t rem_min, chk_min, esc_min;
  float f20_ref;
  float hist[HG_LD_HIST]; uint8_t hn;
  uint32_t n_remind, n_done, n_worked, n_not_worked, n_esc, n_noresp, n_resp;   /* stat */
} hg_ld_t;

void hg_ld_init(hg_ld_t *l);
void hg_ld_minute(hg_ld_t *l, const hg_ld_in_t *in, hg_ld_out_t *o);
/* a short press (after the tick). Returns 1 if the ladder took its meaning ("done" / "responsive"), 0 if not its business. */
int  hg_ld_press(hg_ld_t *l, hg_ld_out_t *o);
uint8_t hg_ld_reminder(const hg_ld_t *l);     /* 0, HG_LD_S_WATER or HG_LD_S_COOL: the reminder text on the home screen */
uint8_t hg_ld_open(const hg_ld_t *l);         /* 1 = waiting for her (reminder or escalation): an "alert" for the button */
const char *hg_ld_state_name(uint8_t s);

/* the texts (owner decisions; every glyph checked by fw/tools/test_herday_glyphs.c) */
extern const char HG_TXT_LD_WORKED[];   /* «Μπράβο, δροσίζεστε» */
extern const char HG_TXT_LD_STILL[];    /* «Ακόμα ζεσταίνεστε» */
extern const char HG_TXT_LD_GOCOOL[];   /* «Πηγαίνετε κάπου δροσερά» */
extern const char HG_TXT_LD_LIEDOWN[];  /* «Ξαπλώστε, βρέξτε τον λαιμό σας» */
extern const char HG_TXT_LD_SEEME[];    /* «Πατήστε αν με βλέπετε» */
extern const char HG_TXT_LD_FAMILY[];   /* «Ειδοποιούμε την οικογένεια» */
extern const char HG_TXT_PWR_PROMPT[];  /* «Απενεργοποίηση;» */
extern const char HG_TXT_PWR_HINT[];    /* «Ένα πάτημα = ναι» */
extern const char HG_TXT_PWR_OFF[];     /* «Σβήνει…» (the ellipsis drawn as three dots) */
extern const char HG_TXT_HELP_ASKED[];  /* «Η βοήθεια έχει ζητηθεί» */

/* ---- gauge ---- */
#define HG_GA_STEPS     5
#define HG_GA_UNKNOWN   0xFF
#define HG_GA_HYST_C    0.05f    /* a step goes DOWN only when f20 is 0.05 C below its boundary */
#define HG_GA_NEAR_C    0.15f    /* yellow-green: within 0.15 C under her first (water) line */
#define HG_GA_CENTRE_C  0.50f    /* the scale centre ("balanced") = 0.50 C under the first line */
typedef struct { float line_w, line_c, line_d, centre; } hg_ga_lines_t;
/* her personal lines from the frozen state (read only): learned calm f20 a_base (+ HG_X_DELTA, capped at the absolute
 * DRINK line), the COOL line minus her capped margin, the Danger line 38.5 C. */
void hg_ga_lines(float a_base, uint8_t a_base_n, float m_drink, float m_cool, hg_ga_lines_t *L);
typedef struct { float f20; uint8_t level, danger, state_drink, state_cool, valid; } hg_ga_in_t;
/* step 0..4 (HG_GA_UNKNOWN: no forecast and no tier: grey, no dot); pos = dot position -10 (cool) .. 0 (balanced) .. +10 (Danger line) */
uint8_t hg_ga_step(const hg_ga_lines_t *L, const hg_ga_in_t *in, uint8_t prev, int8_t *pos);
typedef struct { uint8_t r, g, b, text_white; const char *name; } hg_ga_col_t;
const hg_ga_col_t *hg_ga_colour(uint8_t step);   /* HG_GA_UNKNOWN -> grey */
float hg_ga_luminance(const hg_ga_col_t *c);       /* WCAG relative luminance (sRGB) */

#ifdef __cplusplus
}
#endif
#endif
