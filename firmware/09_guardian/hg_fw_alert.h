/* Heat Guardian 09_guardian 0.9.9: ALERT QUALITY rules layer (branch b14-alerts). Plain C99, no malloc, no hardware,
 * host-tested in fw/tools/test_alerts.c (staged scenes: the .csv files in fw/09_guardian/scenes).
 *
 * It sits between the FROZEN guardian's minute output (hg_minute_out_t, never changed) and what the band DOES with it:
 * buzz, wake the screen, log WARN_SHOWN, start a planner nudge. It never changes how strain / core / tiers are computed.
 *
 *  1 VALIDITY GATE    worn (frozen hg_contact), skin plausible, pulse signal quality, shower / sun-on-sensor signatures.
 *                     Invalid input = UNKNOWN, never HIGH: DRINK / COOL interruptions and nudges wait (logged).
 *  2 PERSISTENCE      DRINK needs 5, COOL 3 consecutive valid minutes of the frozen state with f20 not falling back;
 *    + HYSTERESIS     one normal minute resets. Once shown, the episode is latched: it ends only after 10 calm minutes
 *                     AND f20 0.20 C below the f20 it was shown at (or 60 calm minutes); only then can it fire again.
 *  3 TWO EVIDENCE     COOL interrupts at full strength only when EXPOSURE (trusted air >= 28 C in the last hour, the
 *                     frozen env reason bits, or a forecast heat-day hour) AND PHYSIOLOGY (frozen body reason bits,
 *                     strain >= 5, or pulse >= her resting + 15 bpm while still) agree. Exposure alone = a soft
 *                     nudge-strength COOL; body alone (no heat around her: exercise, fever) = held, at most 30 min, then
 *                     soft. Both logged ONE_EVIDENCE. Frozen CHECK / DANGER are NOT gated (see SAFETY below): audited only.
 *  4 SPEAK ON CHANGE  one buzz when an episode starts or worsens, nothing while it holds or eases, one all-clear
 *    + ALL-CLEAR      «Πάλι όλα καλά» + EVENTS ALL_CLEAR when a shown episode ends.
 *  5 SCORECARD        sent per type, held back per reason, acknowledged, missed, time to acknowledge.
 *
 * SAFETY (what this layer may NOT do): the frozen CHECK («Είστε καλά;») starts its own family timer (5 / 10 min) inside
 * the frozen state machine. Holding or delaying the question would let the family be called before she was ever asked,
 * so CHECK, DANGER, HELP, IMOK, NOT_WORN, BATTERY and their haptics pass through unchanged. Every hold of DRINK / COOL
 * is bounded (60 / 30 min of continuous hold while the frozen tier stays on -> shown, logged HOLD_LIMIT); the frozen
 * STATUS frame still carries the real state, and the screen shows it whenever she looks. */
#ifndef HG_FW_ALERT_H
#define HG_FW_ALERT_H
#include <stdint.h>
#include "frozen/hg_guardian.h"
#include "hg_fw_eco.h"
#ifdef __cplusplus
extern "C" {
#endif

/* ---- the numbers (each one's reason: README 0.9.9 and ECOSYSTEM_SPEC 5e) ---- */
#define HG_AL_N_DRINK        5      /* consecutive valid DRINK minutes before the DRINK buzz (report rank 2: "for example 5") */
#define HG_AL_N_COOL         3      /* COOL: shorter, it is the more urgent tier */
#define HG_AL_F20_BACK       0.05f  /* a minute counts only if f20 >= f20 at the run start - 0.05 C (not self-correcting) */
#define HG_AL_BACKSTOP_DRINK 15     /* valid frozen-DRINK minutes after which it is shown even if f20 wobbles */
#define HG_AL_BACKSTOP_COOL  10
#define HG_AL_HOLD_MAX_DRINK 60     /* a validity hold never lasts longer than this while the frozen tier stays on */
#define HG_AL_HOLD_MAX_COOL  30
#define HG_AL_CLEAR_CALM     10     /* episode end: 10 calm valid minutes ... */
#define HG_AL_CLEAR_DROP     0.20f  /* ... and f20 0.20 C below the f20 it was shown at (the lower threshold) */
#define HG_AL_CLEAR_CALM_MAX 60     /* ... or 60 calm minutes whatever f20 says */
#define HG_AL_SKIN_MIN       28.0f  /* skin plausible on a wrist */
#define HG_AL_SKIN_MAX       40.5f
#define HG_AL_PPG_BAD_OF5    3      /* pulse quality < 3 (no skin / low PI / motion) in >= 3 of the last 5 minutes */
#define HG_AL_WET_RH         80.0f  /* shower: RH >= 80 % after a >= 20 %RH rise in 5 min with a >= 1.0 C skin step */
#define HG_AL_WET_RISE       20.0f
#define HG_AL_WET_SKIN       1.0f
#define HG_AL_WET_EXIT_RH    70.0f  /* wet until RH < 70 %, then 15 min drying; 45 min at most from the start */
#define HG_AL_WET_DRY        15
#define HG_AL_WET_MAX        45
#define HG_AL_SUN_RISE       4.0f   /* sun: air sensor +4 C in 5 min while skin moved <= 1 C, top sensor >= 1.5 C over skin */
#define HG_AL_SUN_SKIN       1.0f
#define HG_AL_SUN_TOP        1.5f
#define HG_AL_SUN_EXIT       1.0f   /* until top - skin < 1 C (45 min at most), then 10 min cool-down */
#define HG_AL_SUN_COOLDOWN   10
#define HG_AL_SUN_MAX        45
#define HG_AL_WARM_C         28.0f  /* exposure: trusted air >= 28 C at some minute of the last 60 (= frozen HG_MB_WARM_C) */
#define HG_AL_HR_ABOVE       15.0f  /* physiology: pulse >= resting + 15 bpm ... */
#define HG_AL_HR_STILL_G     0.05f  /* ... while still (a_std <= 0.05 g), in >= 3 of the last 5 minutes */
#define HG_AL_STRAIN         5.0f   /* physiology: frozen strain (0-10) >= 5 */
#define HG_AL_ROOM_PERSIST   5      /* planner room input = the lowest trusted room value of the last 5 minutes */
#define HG_AL_HELD_EV_DAY    16     /* at most 16 ALERT_HELD EVENTS frames a day (the log line and counter are always kept) */

/* validity bits (0 = valid) */
enum { HG_AL_V_NOT_WORN = 1, HG_AL_V_LOOSE = 2, HG_AL_V_SKIN = 4, HG_AL_V_PPG = 8, HG_AL_V_WET = 16, HG_AL_V_SUN = 32 };
/* hold reasons (counters, log, EVENTS ALERT_HELD byte 11) */
enum { HG_AL_R_NOT_WORN = 1, HG_AL_R_LOOSE, HG_AL_R_SKIN, HG_AL_R_PPG, HG_AL_R_WET, HG_AL_R_SUN,
       HG_AL_R_PERSIST,      /* the frozen tier ended before it persisted: a self-corrected candidate */
       HG_AL_R_REPEAT,       /* the same episode came back: not repeated */
       HG_AL_R_ONE_EV,       /* COOL with one kind of evidence: shown as a soft nudge-strength COOL */
       HG_AL_R_N };
/* what was held / sent */
enum { HG_AL_W_DRINK = 1, HG_AL_W_COOL = 2, HG_AL_W_NUDGE = 3, HG_AL_W_BEDTIME = 4, HG_AL_W_CHECK = 5 };
/* sent counters */
enum { HG_AL_K_NUDGE = 0, HG_AL_K_DRINK, HG_AL_K_COOL, HG_AL_K_COOL_SOFT, HG_AL_K_CHECK, HG_AL_K_FAMILY, HG_AL_K_CLEAR,
       HG_AL_K_BEDTIME, HG_AL_K_N };

typedef struct {
  uint16_t sent[HG_AL_K_N];
  uint16_t held[HG_AL_R_N];        /* [0] unused */
  uint16_t ack, missed;            /* ack = nudge DONE + I'm OK on a CHECK; missed = nudge MISSED + CHECK unanswered (family) */
  uint16_t tta_n, tta_max_s; uint32_t tta_sum_s;   /* time to acknowledge (prompt shown -> press) */
  uint16_t check_1ev;              /* audit: frozen thermal CHECKs with one kind of evidence (passed through, not held) */
  uint16_t hold_limit;             /* holds that hit their bound and were shown anyway */
  uint32_t unknown_min, minutes;   /* minutes with invalid input / all minutes */
} hg_al_score_t;

typedef struct { uint8_t what, reason, arg, ev; } hg_al_note_t;   /* arg: nudge id / state; ev: also an EVENTS frame */

typedef struct {
  /* validity history: [0] = this minute ... [5] = 5 minutes ago */
  float t1h[6], t2h[6], tah[6], rhh[6]; uint8_t hn;
  uint8_t ppg_bits, hr_bits;      /* last 5 minutes: pulse quality poor / pulse high while still */
  uint8_t wet, sun, wet_dry, sun_cool; uint16_t wet_min, sun_min;
  uint32_t warm_lo, warm_hi;       /* 60 minute bits: trusted air >= 28 C */
  float room5[HG_AL_ROOM_PERSIST]; uint8_t room_i;
  uint8_t valid;                   /* HG_AL_V_* of this minute */
  /* persistence, per tier (index 1 DRINK, 2 COOL) */
  uint8_t run[3]; float ref[3]; uint16_t on_min[3], hold_min[3]; uint16_t held_bits[3]; uint8_t cand[3];
  /* episode */
  uint8_t pres, pres_soft, peak, tpeak, ep_family, prev_state, prev_check, prev_family;
  uint16_t ep_min, calm_run, calm_valid_run; float f20_pres;
  /* nudges held this hold-run (bit = id) */
  uint16_t nudge_held;
  /* time to acknowledge */
  uint32_t check_ms, nudge_ms; uint8_t check_open, nudge_open;
  int32_t ev_day; uint8_t ev_today;
  hg_al_score_t sc;
} hg_al_t;

typedef struct {
  const hg_minute_t *in;           /* the frozen guardian's input this minute (FW.last_in) */
  const hg_minute_out_t *o;        /* its output (FW.last_out), read only */
  float rest_hr;                   /* Body Twin resting pulse (TW.rest_hr) */
  const uint8_t *fc72;             /* forecast (24 x i8 T_in, u8 RH, u8 flags) or NULL */
  uint16_t mod; int32_t day;       /* local minute / day, 0xFFFF / -1 unknown */
  float vbat;
  uint32_t ms;                     /* millis() now (time to acknowledge) */
} hg_al_in_t;

typedef struct {
  uint8_t haptic;                  /* HG_HAP_* the band plays now: replaces o->haptic */
  uint8_t present;                 /* HG_ST_DRINK / HG_ST_COOL shown now (wake + WARN_SHOWN), 0 none */
  uint8_t soft;                    /* the COOL is shown at nudge strength (one kind of evidence) */
  uint8_t wake;                    /* the band should wake the screen for the frozen state change (0 for quiet changes) */
  uint8_t clear;                   /* an all-clear now: show «Πάλι όλα καλά», EVENTS ALL_CLEAR */
  uint8_t clear_peak, clear_tick, clear_family; uint16_t clear_min;
  uint8_t nudge_hold, nudge_reason;   /* planner: no new nudge now */
  float room_c;                    /* planner room input: trusted + persisted, NAN unknown */
  uint8_t n_notes; hg_al_note_t notes[8];
} hg_al_out_t;

void hg_al_init(hg_al_t *a);
/* once a minute, right after hg_fw_minute() */
void hg_al_minute(hg_al_t *a, const hg_al_in_t *in, hg_al_out_t *out);
/* every EVENTS frame the band logs (NUDGE_SHOWN / DONE / MISSED, IM_OK, ...): scorecard + time to acknowledge */
void hg_al_event(hg_al_t *a, uint8_t type, uint8_t arg, uint32_t ms);
/* the planner minute with the validity gate: pin->hold / pin->room_c from ao; a held nudge is found by a shadow run on a
 * copy of the planner and logged once per hold (note appended to ao); then the real planner runs (it keeps its own
 * bookkeeping: timeouts, day roll, N8 arming). */
void hg_al_plan_minute(hg_al_t *a, hg_al_out_t *ao, hg_plan_t *p, hg_plan_in_t *pin, hg_plan_out_t *po);
/* EVENTS payloads (bytes 11-18) */
void hg_al_held_x(const hg_al_note_t *n, uint8_t x[8]);         /* type 11: [11] reason [12] arg (nudge id / state) */
void hg_al_clear_x(const hg_al_out_t *o, uint8_t x[8]);         /* type 12: [11-12] u16 minutes [13] family [14] tick */
void hg_al_score_x(const hg_al_t *a, uint8_t page, uint8_t x[8]);   /* type 13 page 0..2 */
const char *hg_al_reason_name(uint8_t r);
const char *hg_al_what_name(uint8_t w);
const char *hg_al_valid_text(uint8_t v, char *buf, uint16_t n);   /* "ok" or "not_worn+ppg" ... */
uint8_t hg_al_first_reason(uint8_t valid_bits);                   /* the reason code of the highest-priority bit */
extern const char HG_TXT_ALLCLEAR[];   /* «Πάλι όλα καλά» */

#ifdef __cplusplus
}
#endif
#endif
