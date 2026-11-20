/* Heat Guardian 09_guardian 0.9.9: alert-quality rules layer. See hg_fw_alert.h (what, why, and what it may not do).
 * Reads the frozen guardian's minute output; never writes guardian state. */
#include "fw_flags.h"
#include "hg_fw_alert.h"
#include "frozen/hg_guardian_cfg.h"   /* HG_HAP_*, HG_VBAT_SOFT (read only) */
#include <math.h>
#include <string.h>
#include <stdio.h>

/* «Πάλι όλα καλά» */
const char HG_TXT_ALLCLEAR[] = "\xce\xa0\xce\xac\xce\xbb\xce\xb9 \xcf\x8c\xce\xbb\xce\xb1 \xce\xba\xce\xb1\xce\xbb\xce\xac";

static int fin(float v) { return v == v && v < 1e30f && v > -1e30f; }
static uint8_t pop5(uint8_t b) { uint8_t n = 0; for (int i = 0; i < 5; i++) n = (uint8_t)(n + ((b >> i) & 1u)); return n; }
static void inc(uint16_t *c) { if (*c < 65535u) (*c)++; }
static uint8_t sat8(uint32_t v) { return (uint8_t)(v > 255u ? 255u : v); }

void hg_al_init(hg_al_t *a)
{
  memset(a, 0, sizeof *a);
  for (int k = 0; k < 6; k++) { a->t1h[k] = NAN; a->t2h[k] = NAN; a->tah[k] = NAN; a->rhh[k] = NAN; }
  for (int k = 0; k < HG_AL_ROOM_PERSIST; k++) a->room5[k] = NAN;
  for (int k = 0; k < 3; k++) a->ref[k] = NAN;
  a->f20_pres = NAN; a->prev_state = HG_ST_OK; a->ev_day = -1;
}

static void note(hg_al_out_t *o, uint8_t what, uint8_t reason, uint8_t arg, uint8_t ev)
{
  if (o->n_notes >= sizeof o->notes / sizeof o->notes[0]) return;
  hg_al_note_t *n = &o->notes[o->n_notes++]; n->what = what; n->reason = reason; n->arg = arg; n->ev = ev;
}
static void held(hg_al_t *a, hg_al_out_t *o, uint8_t what, uint8_t reason, uint8_t arg)
{
  if (reason > 0 && reason < HG_AL_R_N) inc(&a->sc.held[reason]);
  note(o, what, reason, arg, 1);
}

uint8_t hg_al_first_reason(uint8_t v)
{
  if (v & HG_AL_V_NOT_WORN) return HG_AL_R_NOT_WORN;
  if (v & HG_AL_V_LOOSE) return HG_AL_R_LOOSE;
  if (v & HG_AL_V_SKIN) return HG_AL_R_SKIN;
  if (v & HG_AL_V_WET) return HG_AL_R_WET;
  if (v & HG_AL_V_SUN) return HG_AL_R_SUN;
  if (v & HG_AL_V_PPG) return HG_AL_R_PPG;
  return 0;
}

/* min over history slots 1..5 that exist (NAN if none) */
static float hmin(const float *h, uint8_t hn)
{
  float m = NAN;
  for (uint8_t k = 1; k < 6 && k < hn; k++) if (fin(h[k]) && (!fin(m) || h[k] < m)) m = h[k];
  return m;
}
static float hmaxdev(const float *h, uint8_t hn)   /* max |h[0] - h[k]|, k = 1..5 */
{
  float d = 0.0f;
  if (!fin(h[0])) return 0.0f;
  for (uint8_t k = 1; k < 6 && k < hn; k++) if (fin(h[k])) { float x = fabsf(h[0] - h[k]); if (x > d) d = x; }
  return d;
}

/* ---- 1. validity: history, signatures, bits ---- */
static void validity(hg_al_t *a, const hg_al_in_t *in)
{
  const hg_minute_t *m = in->in; const hg_minute_out_t *o = in->o;
  for (int k = 5; k > 0; k--) { a->t1h[k] = a->t1h[k - 1]; a->t2h[k] = a->t2h[k - 1]; a->tah[k] = a->tah[k - 1]; a->rhh[k] = a->rhh[k - 1]; }
  a->t1h[0] = m->s.t1_c; a->t2h[0] = m->s.t2_c; a->tah[0] = m->s.t_air_c; a->rhh[0] = m->s.rh_pct;
  if (a->hn < 6) a->hn++;
  const float t1 = m->s.t1_c, ta = m->s.t_air_c, rh = m->s.rh_pct;
  const float top = fin(m->s.t2_c) ? m->s.t2_c : ta;          /* the outward sensor (REF TMP117), else the air sensor */
  /* pulse quality poor (0 no skin, 1 low PI, 2 motion; 3 irregular is NOT poor: atrial fibrillation is common at 80+) */
  a->ppg_bits = (uint8_t)(((a->ppg_bits << 1) | (o->worn != 0 && m->s.hr_quality < 3)) & 0x1Fu);
  const int hr_ok = m->s.hr_quality == 4 && fin(m->s.hr_bpm);
  const int still = fin(m->s.a_std_g) && m->s.a_std_g <= HG_AL_HR_STILL_G;
  a->hr_bits = (uint8_t)(((a->hr_bits << 1) | (hr_ok && still && fin(in->rest_hr) && m->s.hr_bpm >= in->rest_hr + HG_AL_HR_ABOVE)) & 0x1Fu);
  /* shower / wet: a fast humidity jump to >= 80 % with a skin step (both, so humid weather alone never trips it) */
  if (a->wet) {
    a->wet_min++;
    if (a->wet == 1 && !(fin(rh) && rh >= HG_AL_WET_EXIT_RH)) { a->wet = 2; a->wet_dry = HG_AL_WET_DRY; }
    else if (a->wet == 2 && a->wet_dry && --a->wet_dry == 0) a->wet = 0;
    if (a->wet_min >= HG_AL_WET_MAX) a->wet = 0;              /* bounded: an untested signature never hides more than 45 min */
  } else {
    float rmin = hmin(a->rhh, a->hn);
    if (fin(rh) && fin(rmin) && rh >= HG_AL_WET_RH && rh - rmin >= HG_AL_WET_RISE && hmaxdev(a->t1h, a->hn) >= HG_AL_WET_SKIN) {
      a->wet = 1; a->wet_min = 0; a->wet_dry = 0;
    }
  }
  /* sun on the sensor: the air sensor jumps, the skin does not, the outward sensor is clearly hotter than the skin */
  if (a->sun) {
    a->sun_min++;
    if (a->sun == 1 && !(fin(top) && fin(t1) && top - t1 >= HG_AL_SUN_EXIT)) { a->sun = 2; a->sun_cool = HG_AL_SUN_COOLDOWN; }
    else if (a->sun == 2 && a->sun_cool && --a->sun_cool == 0) a->sun = 0;
    if (a->sun == 1 && a->sun_min >= HG_AL_SUN_MAX) { a->sun = 2; a->sun_cool = HG_AL_SUN_COOLDOWN; }   /* bounded; the sensors still cool down */
  } else {
    float tamin = hmin(a->tah, a->hn), t1min = hmin(a->t1h, a->hn);
    if (fin(ta) && fin(tamin) && fin(t1) && fin(t1min) && fin(top) && ta - tamin >= HG_AL_SUN_RISE && t1 - t1min <= HG_AL_SUN_SKIN &&
        top - t1 >= HG_AL_SUN_TOP) { a->sun = 1; a->sun_min = 0; a->sun_cool = 0; }
  }
  uint8_t v = 0;
  if (o->worn == 0) v |= HG_AL_V_NOT_WORN;
  else if (o->worn == 1) v |= HG_AL_V_LOOSE;
  if (!(fin(t1) && t1 >= HG_AL_SKIN_MIN && t1 <= HG_AL_SKIN_MAX)) v |= HG_AL_V_SKIN;
  if (o->worn != 0 && pop5(a->ppg_bits) >= HG_AL_PPG_BAD_OF5) v |= HG_AL_V_PPG;
  if (a->wet) v |= HG_AL_V_WET;
  if (a->sun) v |= HG_AL_V_SUN;
  a->valid = v;
  /* trusted air: for exposure evidence and the planner's room value */
  const int trusted = fin(ta) && !a->wet && !a->sun;
  const uint32_t w = (uint32_t)(trusted && ta >= HG_AL_WARM_C);
  a->warm_hi = (a->warm_hi << 1) | (a->warm_lo >> 31); a->warm_hi &= 0x0FFFFFFFu;   /* 28 + 32 = 60 minutes */
  a->warm_lo = (a->warm_lo << 1) | w;
  a->room5[a->room_i] = trusted ? ta : NAN; a->room_i = (uint8_t)((a->room_i + 1) % HG_AL_ROOM_PERSIST);
}

static int exposure(const hg_al_t *a, const hg_al_in_t *in)
{
  const hg_minute_out_t *o = in->o;
  if (a->warm_lo || a->warm_hi) return 1;                                   /* trusted air >= 28 C in the last hour */
  if ((o->why & (HG2_WHY_ENV_LIMIT | HG2_WHY_TIME_IN_HEAT)) && !a->wet && !a->sun) return 1;   /* frozen env reasons, air trusted */
  if (in->fc72 && in->mod < 1440u && (in->fc72[3 * (in->mod / 60u) + 2] & 1u)) return 1;     /* forecast heat-day hour */
  return 0;
}
static int physiology(const hg_al_t *a, const hg_al_in_t *in)
{
  const hg_minute_out_t *o = in->o;
  if (o->why & (HG2_WHY_BODY | HG2_WHY_NN | HG2_WHY_DANGER_P)) return 1;  /* the frozen engine's own body reasons */
  if (o->core.valid && fin(o->core.strain) && o->core.strain >= HG_AL_STRAIN) return 1;
  return pop5(a->hr_bits) >= 3;                                             /* pulse above her own resting value, while still */
}

static uint8_t batt(const hg_al_in_t *in, uint8_t hap)   /* R4 A8, the frozen rule: low battery -> soft tick */
{
  return (hap != HG_HAP_NONE && fin(in->vbat) && in->vbat < HG_VBAT_SOFT) ? (uint8_t)HG_HAP_SOFT : hap;
}

static void present(hg_al_t *a, const hg_al_in_t *in, hg_al_out_t *out, uint8_t L, int two)
{
  const float f20 = in->o->core.valid ? in->o->core.f20_eff : NAN;
  a->pres = L; if (a->peak < L) a->peak = L; if (a->tpeak < L) a->tpeak = L;
  if (fin(f20) && (!fin(a->f20_pres) || f20 > a->f20_pres)) a->f20_pres = f20;
  out->present = L == 1 ? HG_ST_DRINK : HG_ST_COOL; out->wake = 1;
  if (L == 1) { out->haptic = batt(in, HG_HAP_WATCH); inc(&a->sc.sent[HG_AL_K_DRINK]); a->pres_soft = 0; }
  else if (two) { out->haptic = batt(in, HG_HAP_COOL); inc(&a->sc.sent[HG_AL_K_COOL]); a->pres_soft = 0; }
  else { out->haptic = HG_HAP_SOFT; out->soft = 1; inc(&a->sc.sent[HG_AL_K_COOL_SOFT]); a->pres_soft = 1;
         if (!(a->held_bits[L] & (1u << HG_AL_R_ONE_EV))) { inc(&a->sc.held[HG_AL_R_ONE_EV]); note(out, HG_AL_W_COOL, HG_AL_R_ONE_EV, HG_ST_COOL, 1); } }
  a->held_bits[L] = 0; a->hold_min[L] = 0;
}

void hg_al_minute(hg_al_t *a, const hg_al_in_t *in, hg_al_out_t *out)
{
  memset(out, 0, sizeof *out);
  out->haptic = HG_HAP_NONE; out->room_c = NAN;
  const hg_minute_out_t *o = in->o;
  const uint8_t s = o->state;
  if (in->day != a->ev_day) { a->ev_day = in->day; a->ev_today = 0; }
  validity(a, in);
  a->sc.minutes++;
  if (a->valid) a->sc.unknown_min++;
  const int E = exposure(a, in), P = physiology(a, in);
  const float f20 = o->core.valid ? o->core.f20_eff : NAN;
  const uint8_t v = a->valid;

  /* planner inputs: persisted trusted room; no new nudge while the band is off / implausible / in the shower */
  { float r = NAN; int ok = 1;
    for (int k = 0; k < HG_AL_ROOM_PERSIST; k++) { float x = a->room5[k]; if (!fin(x)) { ok = 0; break; } if (!fin(r) || x < r) r = x; }
    out->room_c = ok ? r : NAN; }
  { uint8_t nb = (uint8_t)(v & (HG_AL_V_NOT_WORN | HG_AL_V_SKIN | HG_AL_V_WET));
    out->nudge_hold = nb != 0; out->nudge_reason = hg_al_first_reason(nb); }

  /* frozen haptics: pass through, except the DRINK / COOL onset buzz (this layer decides it) and the bedtime tip on invalid input */
  if (s == HG_ST_DRINK || s == HG_ST_COOL) out->haptic = HG_HAP_NONE;
  else if (s == HG_ST_OK && o->nudge) {
    uint8_t nb = (uint8_t)(v & (HG_AL_V_NOT_WORN | HG_AL_V_SKIN | HG_AL_V_WET));
    if (nb) held(a, out, HG_AL_W_BEDTIME, hg_al_first_reason(nb), 0);
    else { out->haptic = o->haptic; inc(&a->sc.sent[HG_AL_K_BEDTIME]); }
  } else out->haptic = o->haptic;
  /* screen wake for frozen state changes: not for quiet ones (into OK / DRINK / COOL: the layer speaks for those) */
  if (s != a->prev_state && s != HG_ST_OK && s != HG_ST_DRINK && s != HG_ST_COOL) out->wake = 1;

  /* ---- CHECK / DANGER / family: pass through, scorecard + two-evidence audit ---- */
  const uint8_t check_on = o->check_min != 0xFF;
  if (check_on && !a->prev_check) {
    inc(&a->sc.sent[HG_AL_K_CHECK]); a->check_open = 1; a->check_ms = in->ms;
    if (a->peak < 3) a->peak = 3;
    if (o->check_reason & (HG_CR_DANGER | HG_CR_BEHAVIOUR)) {
      a->tpeak = 3;
      if (!(E && P)) { inc(&a->sc.check_1ev); note(out, HG_AL_W_CHECK, HG_AL_R_ONE_EV, o->check_reason, 0); }   /* audit only */
    }
    a->pres = 3;
  }
  if (s == HG_ST_DANGER) { a->pres = 3; if (a->peak < 3) a->peak = 3; a->tpeak = 3; }   /* DANGER after an I'm OK (snoozed CHECK) */
  if (o->family_alert && !a->prev_family) {
    inc(&a->sc.sent[HG_AL_K_FAMILY]); a->ep_family = 1;
    if (a->check_open) { inc(&a->sc.missed); a->check_open = 0; }
  }
  if (!check_on) a->check_open = a->check_open && s == HG_ST_IMOK;   /* the CHECK ended without a press or a family call */

  /* ---- 2/3. persistence + hysteresis + two evidence for DRINK (1) and COOL (2); COOL first ---- */
  for (uint8_t L = 2; L >= 1; L--) {
    const int on = L == 1 ? (s == HG_ST_DRINK || s == HG_ST_COOL) : s == HG_ST_COOL;
    if (!on) {
      if (a->cand[L] && a->pres < L && !a->held_bits[L] && a->run[L] && o->level < L && (s == HG_ST_OK || s == HG_ST_DRINK)) {
        inc(&a->sc.held[HG_AL_R_PERSIST]); note(out, L == 1 ? HG_AL_W_DRINK : HG_AL_W_COOL, HG_AL_R_PERSIST, L == 1 ? HG_ST_DRINK : HG_ST_COOL, 1);
      }
      a->cand[L] = 0; a->run[L] = 0; a->on_min[L] = 0; a->hold_min[L] = 0; a->held_bits[L] = 0; a->ref[L] = NAN;
      continue;
    }
    if (!a->cand[L]) {
      a->cand[L] = 1;
      if (a->pres >= L && !out->present) { inc(&a->sc.held[HG_AL_R_REPEAT]); note(out, L == 1 ? HG_AL_W_DRINK : HG_AL_W_COOL, HG_AL_R_REPEAT, L == 1 ? HG_ST_DRINK : HG_ST_COOL, 1); }
    }
    if (a->pres >= L) {                              /* latched: say nothing, unless a soft COOL now has both kinds of evidence */
      if (L == 2 && a->pres == 2 && a->pres_soft && E && P && !out->present) {
        a->pres_soft = 0; out->present = HG_ST_COOL; out->wake = 1; out->haptic = batt(in, HG_HAP_COOL); inc(&a->sc.sent[HG_AL_K_COOL]);
      }
      continue;
    }
    const uint8_t block = (uint8_t)(v & (L == 1 ? 0xFFu : (HG_AL_V_NOT_WORN | HG_AL_V_LOOSE | HG_AL_V_SKIN | HG_AL_V_WET)));
    if (block) {
      const uint8_t r = hg_al_first_reason(block);
      if (!(a->held_bits[L] & (1u << r))) { a->held_bits[L] |= (uint16_t)(1u << r); held(a, out, L == 1 ? HG_AL_W_DRINK : HG_AL_W_COOL, r, L == 1 ? HG_ST_DRINK : HG_ST_COOL); }
      if (++a->hold_min[L] >= (L == 1 ? HG_AL_HOLD_MAX_DRINK : HG_AL_HOLD_MAX_COOL)) {   /* bounded: shown anyway */
        inc(&a->sc.hold_limit); note(out, L == 1 ? HG_AL_W_DRINK : HG_AL_W_COOL, 0, L == 1 ? HG_ST_DRINK : HG_ST_COOL, 0);
        present(a, in, out, L, E && P);
      }
      continue;
    }
    a->on_min[L]++;
    if (a->run[L] == 0 || !fin(f20) || !fin(a->ref[L]) || f20 >= a->ref[L] - HG_AL_F20_BACK) {
      if (a->run[L] == 0) a->ref[L] = f20;
      if (a->run[L] < 255) a->run[L]++;
    } else { a->run[L] = 1; a->ref[L] = f20; }      /* falling back: restart the count from here */
    if (!(a->run[L] >= (L == 1 ? HG_AL_N_DRINK : HG_AL_N_COOL) || a->on_min[L] >= (L == 1 ? HG_AL_BACKSTOP_DRINK : HG_AL_BACKSTOP_COOL))) {
      a->hold_min[L] = 0; continue;                  /* not persisted yet */
    }
    if (L == 2 && !E) {                              /* COOL from the body alone, no heat exposure (exercise, fever): «go somewhere
                                                        cooler» has nothing to act on; wait (bounded), then a soft COOL */
      if (!(a->held_bits[L] & (1u << HG_AL_R_ONE_EV))) { a->held_bits[L] |= (uint16_t)(1u << HG_AL_R_ONE_EV); held(a, out, HG_AL_W_COOL, HG_AL_R_ONE_EV, HG_ST_COOL); }
      if (++a->hold_min[L] >= HG_AL_HOLD_MAX_COOL) { inc(&a->sc.hold_limit); note(out, HG_AL_W_COOL, 0, HG_ST_COOL, 0); present(a, in, out, L, 0); }
      continue;
    }
    present(a, in, out, L, E && P);                  /* exposure without physiology: soft COOL (present() logs ONE_EVIDENCE) */
  }

  /* ---- 4. episode end -> all-clear ---- */
  if (a->pres) {
    if (a->ep_min < 65535u) a->ep_min++;
    const int calm = o->level == 0 && !check_on && s != HG_ST_DRINK && s != HG_ST_COOL && s != HG_ST_CHECK && s != HG_ST_DANGER && s != HG_ST_HELP;
    if (calm) { inc(&a->calm_run); if (!v) inc(&a->calm_valid_run); }
    else { a->calm_run = 0; a->calm_valid_run = 0; }
    const int dropped = !fin(a->f20_pres) || (fin(f20) && f20 <= a->f20_pres - HG_AL_CLEAR_DROP);
    if ((a->calm_valid_run >= HG_AL_CLEAR_CALM && dropped) || a->calm_run >= HG_AL_CLEAR_CALM_MAX) {
      out->clear = 1; out->clear_peak = a->peak; out->clear_family = a->ep_family; out->clear_min = a->ep_min;
      out->clear_tick = (uint8_t)(a->tpeak >= 2 || a->ep_family);
      if (out->clear_tick && out->haptic == HG_HAP_NONE) out->haptic = HG_HAP_TICK;
      if (!out->wake) out->wake = 1;
      inc(&a->sc.sent[HG_AL_K_CLEAR]);
      a->pres = 0; a->pres_soft = 0; a->peak = 0; a->tpeak = 0; a->ep_family = 0; a->ep_min = 0; a->calm_run = 0; a->calm_valid_run = 0; a->f20_pres = NAN;
    }
  }
  a->prev_state = s; a->prev_check = check_on; a->prev_family = o->family_alert;
  /* EVENTS cap for ALERT_HELD (the counters and log lines are never capped) */
  for (uint8_t i = 0; i < out->n_notes; i++) if (out->notes[i].ev) { if (a->ev_today >= HG_AL_HELD_EV_DAY) out->notes[i].ev = 0; else a->ev_today++; }
}

void hg_al_plan_minute(hg_al_t *a, hg_al_out_t *ao, hg_plan_t *p, hg_plan_in_t *pin, hg_plan_out_t *po)
{
  static hg_plan_t sh; sh = *p;                    /* shadow: what 0.9.8 would start (no gate, the raw room value) */
  hg_plan_in_t i2 = *pin; i2.hold = 0; hg_plan_out_t so;
  hg_plan_minute(&sh, &i2, &so);
  pin->hold = ao->nudge_hold; pin->room_c = ao->room_c;
  hg_plan_minute(p, pin, po);
  if (so.show && so.show != po->show && so.show < 16) {
    if (!(a->nudge_held & (1u << so.show))) {         /* once per nudge id per hold run */
      a->nudge_held |= (uint16_t)(1u << so.show);
      uint8_t r = pin->hold ? ao->nudge_reason : (a->valid & HG_AL_V_SUN) ? HG_AL_R_SUN : (a->valid & HG_AL_V_WET) ? HG_AL_R_WET : HG_AL_R_PERSIST;
      uint8_t before = ao->n_notes;
      held(a, ao, HG_AL_W_NUDGE, r, so.show);
      if (ao->n_notes > before && ao->notes[ao->n_notes - 1].ev) { if (a->ev_today >= HG_AL_HELD_EV_DAY) ao->notes[ao->n_notes - 1].ev = 0; else a->ev_today++; }
    }
  } else if (!pin->hold && !so.show) a->nudge_held = 0;
}

void hg_al_event(hg_al_t *a, uint8_t type, uint8_t arg, uint32_t ms)
{
  (void)arg;
  switch (type) {
    case HG_EV_NUDGE_SHOWN: inc(&a->sc.sent[HG_AL_K_NUDGE]); a->nudge_open = 1; a->nudge_ms = ms; break;
    case HG_EV_NUDGE_DONE: inc(&a->sc.ack);
      if (a->nudge_open) { uint32_t s = (ms - a->nudge_ms + 500u) / 1000u; a->sc.tta_sum_s += s; inc(&a->sc.tta_n); if (s > a->sc.tta_max_s) a->sc.tta_max_s = (uint16_t)(s > 65535u ? 65535u : s); }
      a->nudge_open = 0; break;
    case HG_EV_NUDGE_MISSED: inc(&a->sc.missed); a->nudge_open = 0; break;
    case HG_EV_IM_OK:
      if (a->check_open) { inc(&a->sc.ack); uint32_t s = (ms - a->check_ms + 500u) / 1000u; a->sc.tta_sum_s += s; inc(&a->sc.tta_n);
        if (s > a->sc.tta_max_s) { a->sc.tta_max_s = (uint16_t)(s > 65535u ? 65535u : s); }
        a->check_open = 0; }
      break;
    default: break;
  }
}

void hg_al_held_x(const hg_al_note_t *n, uint8_t x[8]) { memset(x, 0, 8); x[0] = n->reason; x[1] = n->arg; }
void hg_al_clear_x(const hg_al_out_t *o, uint8_t x[8])
{
  memset(x, 0, 8); x[0] = (uint8_t)o->clear_min; x[1] = (uint8_t)(o->clear_min >> 8); x[2] = o->clear_family; x[3] = o->clear_tick;
}
void hg_al_score_x(const hg_al_t *a, uint8_t page, uint8_t x[8])
{
  memset(x, 0, 8);
  const hg_al_score_t *s = &a->sc;
  if (page == 0) for (int i = 0; i < 8; i++) x[i] = sat8(s->sent[i]);
  else if (page == 1) for (int i = 0; i < 8; i++) x[i] = sat8(s->held[i + 1]);
  else {
    x[0] = sat8(s->held[HG_AL_R_ONE_EV]); x[1] = sat8(s->ack); x[2] = sat8(s->missed); x[3] = sat8(s->check_1ev);
    uint32_t avg = s->tta_n ? (s->tta_sum_s + s->tta_n / 2u) / s->tta_n : 0u; if (avg > 65535u) avg = 65535u;
    x[4] = (uint8_t)avg; x[5] = (uint8_t)(avg >> 8); x[6] = (uint8_t)s->tta_max_s; x[7] = (uint8_t)(s->tta_max_s >> 8);
  }
}

const char *hg_al_reason_name(uint8_t r)
{
  static const char *N[] = { "LIMIT", "NOT_WORN", "LOOSE", "SKIN", "PPG", "SHOWER", "SUN", "PERSIST", "REPEAT", "ONE_EVIDENCE" };
  return r < sizeof N / sizeof N[0] ? N[r] : "?";
}
const char *hg_al_what_name(uint8_t w)
{
  static const char *N[] = { "?", "DRINK", "COOL", "NUDGE", "BEDTIME", "CHECK" };
  return w < sizeof N / sizeof N[0] ? N[w] : "?";
}
const char *hg_al_valid_text(uint8_t v, char *buf, uint16_t n)
{
  static const char *B[] = { "not_worn", "loose", "skin", "ppg", "shower", "sun" };
  if (!n) return buf;
  buf[0] = 0;
  if (!v) { snprintf(buf, n, "ok"); return buf; }
  for (int i = 0; i < 6; i++) if (v & (1u << i)) {
    size_t l = strlen(buf); if (l + 1 >= n) break;
    snprintf(buf + l, n - l, "%s%s", l ? "+" : "", B[i]);
  }
  return buf;
}
