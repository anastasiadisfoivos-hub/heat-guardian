#include "hg_nofastmath.h"   /* FIRST: the core builds with -Ofast; NaN must stay NaN */
/* Heat Guardian 09_guardian 0.9.17: action ladder + "keep it green" gauge. See hg_fw_ladder.h. */
#include "hg_fw_ladder.h"
#include "hg_fw_eco.h"        /* HG_EV_LD_* */
#include "hg_fw_ui.h"         /* HG_HP_* */
#include "frozen/hg_guardian.h"       /* HG_ST_* (read only) */
#include "frozen/hg_guardian_cfg.h"   /* the frozen lines (read only) */
#include <string.h>
#include <math.h>

const char HG_TXT_LD_WORKED[]  = "Μπράβο, δροσίζεστε";
const char HG_TXT_LD_STILL[]   = "Ακόμα ζεσταίνεστε";
const char HG_TXT_LD_GOCOOL[]  = "Πηγαίνετε κάπου δροσερά";
const char HG_TXT_LD_LIEDOWN[] = "Ξαπλώστε, βρέξτε τον λαιμό σας";
const char HG_TXT_LD_SEEME[]   = "Πατήστε αν με βλέπετε";
const char HG_TXT_LD_FAMILY[]  = "Ειδοποιούμε την οικογένεια";
const char HG_TXT_PWR_PROMPT[] = "Απενεργοποίηση;";
const char HG_TXT_PWR_HINT[]   = "Ένα πάτημα = ναι";
const char HG_TXT_PWR_OFF[]    = "Σβήνει...";
const char HG_TXT_HELP_ASKED[] = "Η βοήθεια έχει ζητηθεί";

static int fin(float v) { return v == v && v < 1e30f && v > -1e30f; }
static void put_c100(uint8_t *x, float v) { int16_t c = fin(v) ? (int16_t)lroundf(v * 100.0f) : INT16_MIN; x[0] = (uint8_t)c; x[1] = (uint8_t)((uint16_t)c >> 8); }
static void ev(hg_ld_out_t *o, uint8_t type, uint8_t arg, float a, float b, uint16_t u)
{
  if (o->n >= 4) return;
  hg_ld_ev_t *e = &o->ev[o->n++]; memset(e, 0, sizeof *e);
  e->type = type; e->arg = arg;
  put_c100(e->x, a); put_c100(e->x + 2, b); e->x[4] = (uint8_t)u; e->x[5] = (uint8_t)(u >> 8);   /* [11-12] f20 x100, [13-14] ref x100, [15-16] u16 */
}
static void hap(hg_ld_out_t *o, uint8_t h) { const hg_hpat_t *n = hg_hp_pat(h), *c = hg_hp_pat(o->haptic); if (!o->haptic || n->prio >= c->prio) o->haptic = h; }

void hg_ld_init(hg_ld_t *l)
{
  memset(l, 0, sizeof *l); l->f20_ref = NAN;
  for (int i = 0; i < HG_LD_HIST; i++) l->hist[i] = NAN;
}
static float last_valid(const hg_ld_t *l) { for (int i = 0; i < HG_LD_HIST; i++) if (fin(l->hist[i])) return l->hist[i]; return NAN; }

static void remind(hg_ld_t *l, uint8_t step, hg_ld_out_t *o, float f20)
{
  l->state = HG_LD_REMIND; l->step = step; l->rem_min = 0; l->repeated = 0; l->noresp = 0;
  ev(o, HG_EV_LD_REMIND, step, f20, NAN, 0); l->n_remind++;
  hap(o, step == HG_LD_S_COOL ? HG_HP_COOL : HG_HP_WATCH); o->wake = 1;
}
static void escalate(hg_ld_t *l, uint8_t why, hg_ld_out_t *o, float f20)
{
  l->state = HG_LD_ESC; l->step = HG_LD_S_ESC; l->esc_reason = why; l->esc_min = 0;
  ev(o, HG_EV_LD_ESCALATED, why, f20, l->f20_ref, 0); l->n_esc++;
  hap(o, HG_HP_URGENT); o->wake = 1;
}
static void worked(hg_ld_t *l, uint8_t step, hg_ld_out_t *o, float f20, float ref, uint8_t next)
{
  ev(o, HG_EV_LD_WORKED, step, f20, ref, 0); l->n_worked++;
  o->toast = HG_LD_TOAST_WORKED; hap(o, HG_HP_WORKED); o->wake = 1;
  l->state = next; l->step = 0;
}

static void not_worked(hg_ld_t *l, hg_ld_out_t *o, float f)
{
  l->n_not_worked++;
  if (l->step == HG_LD_S_WATER) {                             /* water did not help: next step, quiet note to the family */
    ev(o, HG_EV_LD_NOTE, HG_LD_NOTE_NOT_WORKED, f, l->f20_ref, HG_LD_S_WATER);
    o->toast = HG_LD_TOAST_STILL;
    remind(l, HG_LD_S_COOL, o, f);
  } else escalate(l, HG_LD_ESC_STILL_HEATING, o, f);         /* still rising in the cool: no more waiting steps */
}

void hg_ld_minute(hg_ld_t *l, const hg_ld_in_t *in, hg_ld_out_t *o)
{
  memset(o, 0, sizeof *o);
  memmove(l->hist + 1, l->hist, (HG_LD_HIST - 1) * sizeof l->hist[0]); l->hist[0] = in->f20; if (l->hn < HG_LD_HIST) l->hn++;
  const float f = in->f20, f_20ago = l->hn >= HG_LD_HIST ? l->hist[HG_LD_HIST - 1] : NAN;
  const uint8_t want = in->present == HG_ST_COOL ? HG_LD_S_COOL : in->present == HG_ST_DRINK ? HG_LD_S_WATER : 0;
  /* the Danger line: escalation at once, from any state */
  if (in->danger && l->state != HG_LD_ESC) { escalate(l, HG_LD_ESC_DANGER, o, f); return; }
  switch (l->state) {
    case HG_LD_IDLE:
      if (want) remind(l, want, o, f);
      break;
    case HG_LD_DONE:
      if (want) remind(l, want, o, f);                       /* shown again (worse / a new episode) */
      else if (!in->episode) l->state = HG_LD_IDLE;
      break;
    case HG_LD_REMIND:
      if (!in->episode) { l->state = HG_LD_IDLE; break; }    /* the forecast turned before she pressed */
      if (want == HG_LD_S_COOL && l->step == HG_LD_S_WATER) { remind(l, HG_LD_S_COOL, o, f); break; }   /* it got worse */
      l->rem_min++;
      if (l->rem_min == HG_LD_REPEAT_MIN && !l->repeated) {
        l->repeated = 1; ev(o, HG_EV_LD_REMIND, l->step, f, NAN, 1); l->n_remind++;
        hap(o, l->step == HG_LD_S_COOL ? HG_HP_COOL : HG_HP_WATCH); o->wake = 1;
      }
      if (l->rem_min >= HG_LD_NORESP_MIN && !l->noresp) { l->noresp = 1; ev(o, HG_EV_LD_NOTE, HG_LD_NOTE_NO_RESPONSE, f, NAN, l->step); l->n_noresp++; }
      break;
    case HG_LD_CHECK:
      if (!in->episode) { worked(l, l->step, o, f, l->f20_ref, HG_LD_IDLE); break; }   /* the forecast turned: it worked */
      if (want == HG_LD_S_COOL && l->step == HG_LD_S_WATER) { not_worked(l, o, f); break; }   /* worse during the water check */
      if (++l->chk_min < HG_LD_CHECK_MIN) break;
      if (!fin(f) || !fin(l->f20_ref)) break;                /* no forecast (band off): wait, never decide on nothing */
      if (f <= l->f20_ref + HG_LD_FLAT_C) worked(l, l->step, o, f, l->f20_ref, HG_LD_DONE);
      else not_worked(l, o, f);
      break;
    case HG_LD_ESC:
      l->esc_min++;
      if (in->danger) break;
      if (!in->episode) { worked(l, HG_LD_S_ESC, o, f, f_20ago, HG_LD_IDLE); break; }
      if (l->esc_min >= HG_LD_CHECK_MIN && fin(f) && fin(f_20ago) && f <= f_20ago + HG_LD_FLAT_C) worked(l, HG_LD_S_ESC, o, f, f_20ago, HG_LD_DONE);
      break;
    default: l->state = HG_LD_IDLE; break;
  }
}

int hg_ld_press(hg_ld_t *l, hg_ld_out_t *o)
{
  memset(o, 0, sizeof *o);
  if (l->state == HG_LD_REMIND) {
    l->f20_ref = last_valid(l);
    ev(o, HG_EV_LD_DONE, l->step, l->f20_ref, NAN, l->rem_min); l->n_done++;
    l->state = HG_LD_CHECK; l->chk_min = 0;
    hap(o, HG_HP_YES);
    return 1;
  }
  if (l->state == HG_LD_ESC) {                                /* she is responsive: the family is told, the alert stays */
    ev(o, HG_EV_LD_NOTE, HG_LD_NOTE_RESPONSIVE, last_valid(l), NAN, HG_LD_S_ESC); l->n_resp++;
    hap(o, HG_HP_YES);
    return 1;
  }
  return 0;
}
uint8_t hg_ld_reminder(const hg_ld_t *l) { return (l->state == HG_LD_REMIND || l->state == HG_LD_CHECK) ? l->step : 0; }
uint8_t hg_ld_open(const hg_ld_t *l) { return (uint8_t)(l->state == HG_LD_REMIND || l->state == HG_LD_ESC); }
const char *hg_ld_state_name(uint8_t s)
{
  static const char *N[] = { "idle", "remind", "check20", "escalated", "done" };
  return s < 5 ? N[s] : "?";
}

/* ================================================================== gauge */
void hg_ga_lines(float a_base, uint8_t a_base_n, float m_drink, float m_cool, hg_ga_lines_t *L)
{
  float ld = fin(m_drink) ? (m_drink < HG_M_TOTAL_CAP ? m_drink : HG_M_TOTAL_CAP) : 0.0f;
  float lc = fin(m_cool) ? (m_cool < HG_M_TOTAL_CAP ? m_cool : HG_M_TOTAL_CAP) : 0.0f;
  float w = HG_DRK_ABS_C;                                     /* the absolute DRINK line (design 4 ceiling) */
  if (a_base_n > 0 && fin(a_base) && a_base + HG_X_DELTA - ld < w) w = a_base + HG_X_DELTA - ld;   /* her learned calm + delta */
  L->line_c = HG_T_COOL - lc;
  L->line_d = HG_DG_T_C;
  if (w > L->line_c - 0.10f) w = L->line_c - 0.10f;
  L->line_w = w;
  L->centre = w - HG_GA_CENTRE_C;
}
static uint8_t raw_step(const hg_ga_lines_t *L, float x)
{
  if (x >= L->line_d) return 4;
  if (x >= L->line_c) return 3;
  if (x >= L->line_w) return 2;
  if (x >= L->line_w - HG_GA_NEAR_C) return 1;
  return 0;
}
uint8_t hg_ga_step(const hg_ga_lines_t *L, const hg_ga_in_t *in, uint8_t prev, int8_t *pos)
{
  const int have = in->valid && fin(in->f20);
  uint8_t floor = (in->danger || in->level >= 3) ? 4 : (in->state_cool || in->level == 2) ? 3 : (in->state_drink || in->level == 1) ? 2 : 0;
  uint8_t s;
  if (have) {
    s = raw_step(L, in->f20);
    if (prev < HG_GA_STEPS && s < prev) { uint8_t s2 = raw_step(L, in->f20 + HG_GA_HYST_C); s = s2 < prev ? s2 : prev; }   /* down only past the margin */
    float p = (in->f20 - L->centre) / (L->line_d - L->centre) * 10.0f;
    p = p > 10.0f ? 10.0f : p < -10.0f ? -10.0f : p;
    if (pos) *pos = (int8_t)lroundf(p);
  } else {
    s = floor ? floor : HG_GA_UNKNOWN;
    if (pos) *pos = 0;
  }
  if (s != HG_GA_UNKNOWN && s < floor) s = floor;
  return s;
}
static const hg_ga_col_t COL[HG_GA_STEPS + 1] = {
  { 0, 120, 50, 1, "green" }, { 150, 200, 30, 0, "yellow-green" }, { 250, 220, 40, 0, "yellow" },
  { 235, 120, 0, 0, "orange" }, { 170, 0, 0, 1, "red" }, { 90, 90, 90, 1, "grey" } };
const hg_ga_col_t *hg_ga_colour(uint8_t step) { return &COL[step < HG_GA_STEPS ? step : HG_GA_STEPS]; }
static float lin(uint8_t c) { float v = c / 255.0f; return v <= 0.04045f ? v / 12.92f : powf((v + 0.055f) / 1.055f, 2.4f); }
float hg_ga_luminance(const hg_ga_col_t *c) { return 0.2126f * lin(c->r) + 0.7152f * lin(c->g) + 0.0722f * lin(c->b); }
