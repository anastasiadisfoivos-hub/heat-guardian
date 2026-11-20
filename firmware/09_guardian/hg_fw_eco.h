/* Heat Guardian 09_guardian 0.9.8: the band side of the ecosystem spec (ECOSYSTEM_SPEC.md sections 2-5b) + "Her Day"
 * (HERDAY_SPEC.md, ECOSYSTEM_SPEC.md 5d): CMD 0x1B DAY_PLAN, 0x1C VISIT, EVENTS 9 VISIT / 10 PLAN_ITEM, nudges N7 / N8.
 * Plain C99, no malloc, no hardware, no frozen-engine change: host-tested in fw/tools/test_eco.c.
 *
 *  events   : 64-event RAM ring + the 20-byte EVENTS frame (characteristic HG_UUID("0004"), read + notify)
 *  commands : 0x16 SYNC_EVENTS, 0x17 FAMILY_MSG, 0x18 FAMILY_NAME, 0x19 ROUTINE_SEED, 0x1A ELDER_ACTION, 0x1B DAY_PLAN, 0x1C VISIT, parsed HERE before the frozen
 *             hg_cmd_parse() (which answers HG_CMD_ERR_OP for them). Existing opcodes never reach this parser's logic.
 *  day plan : today + tomorrow (<= 6 items each), atomic per day, midnight roll, file image for /dayplan.bin
 *  planner  : the prevention nudges N1, N2, N4-N8 (N3 removed in 0.9.8), once a minute after guardianMinute(); only reads
 *             the guardian's output.
 *  helpers  : reason line under DRINK/COOL/CHECK/DANGER, local date, room-temperature trend.
 * CRC-8 of every new frame = the frozen hg_crc8() (poly 0x07, init 0, = STATUS / existing CMDs). */
#ifndef HG_FW_ECO_H
#define HG_FW_ECO_H
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif

/* ------------------------------------------------------------------ events (spec 5) */
#define HG_EV_RING        64
#define HG_EV_FRAME_VER   0x03
enum { HG_EV_NUDGE_SHOWN = 1, HG_EV_NUDGE_DONE = 2, HG_EV_NUDGE_MISSED = 3, HG_EV_IM_OK = 4, HG_EV_HELP = 5,
       HG_EV_HELP_CANCEL = 6, HG_EV_FAMILY_MSG_SHOWN = 7, HG_EV_WARN_SHOWN = 8,
       HG_EV_VISIT = 9, HG_EV_PLAN_ITEM = 10,                           /* 0.9.8 (HERDAY_SPEC 4) */
       HG_EV_ALERT_HELD = 11, HG_EV_ALL_CLEAR = 12, HG_EV_SCORE = 13,   /* 0.9.9 alert quality (hg_fw_alert.h, ECOSYSTEM_SPEC 5e) */
       /* 0.9.17 (FW-UI). Apps older than 0.9.17 drop unknown types (EventLog.fromBand: `guard let k = e.kind else { return nil }`).
        * x = bytes 11-18: [11-12] i16 f20 x100 (INT16_MIN unknown), [13-14] i16 reference f20 x100, [15-16] u16 extra, rest 0 */
       HG_EV_POWER_OFF = 14,        /* arg 1 = the wearer (double press + confirm), 2 = USB pwroff; sent before System OFF */
       HG_EV_BATT_CRITICAL = 15,    /* reserved for 0.9.18 (critical battery auto-off) */
       HG_EV_HAPTIC_LOST = 16,      /* arg = HG_HP_* pattern the motor could not play (re-init failed): the screen flashed instead */
       HG_EV_LD_REMIND = 17,        /* ladder reminder shown: arg 1 water, 2 cooler place; [15] 0 first / 1 the 10-min repeat */
       HG_EV_LD_DONE = 18,          /* she pressed "done" to a reminder: arg = step; [15-16] minutes after the reminder; the 20-min check starts */
       HG_EV_LD_WORKED = 19,        /* the forecast stopped rising: arg 1 water, 2 cooler place, 3 after an escalation; [13-14] = the reference */
       HG_EV_LD_ESCALATED = 20,     /* family alert: arg 1 Danger line, 2 still heating after cooling down */
       HG_EV_LD_NOTE = 21 };        /* quiet family note: arg 1 water did not help, 2 no response to a reminder, 3 responsive (escalation) */
/* x = frame bytes 11-18 (0 for types 1-8; VISIT / PLAN_ITEM payloads, see hg_dp_echo / hg_visit_echo) */
typedef struct { uint16_t seq; uint8_t type, arg; uint32_t unix_s; uint8_t x[8]; } hg_ev_t;
typedef struct { hg_ev_t ev[HG_EV_RING]; uint16_t last_seq; uint8_t head, n; } hg_evring_t;   /* 1032 B */

void hg_ev_init(hg_evring_t *r);
/* appends (overwriting the oldest when full); seq runs 1, 2, ... 0xFFFF, 1 (0 is never used = "nothing seen") */
const hg_ev_t *hg_ev_add(hg_evring_t *r, uint32_t unix_s, uint8_t type, uint8_t arg);
const hg_ev_t *hg_ev_add_x(hg_evring_t *r, uint32_t unix_s, uint8_t type, uint8_t arg, const uint8_t x[8]);   /* x NULL = zeros */
const hg_ev_t *hg_ev_at(const hg_evring_t *r, uint8_t i);          /* i = 0 oldest .. n-1 newest, NULL if out of range */
/* index (0 = oldest) of the first event after since_seq, or -1. all = 1 or since_seq = 0: from the oldest. */
int  hg_ev_first_after(const hg_evring_t *r, uint16_t since_seq, uint8_t all);
int  hg_seq_after(uint16_t a, uint16_t b);                         /* serial-number order (RFC 1982): a after b */
/* [0]=0x03 [1-2]seq [3-4]boot [5-8]unix [9]type [10]arg [11-18]x (0 for types 1-8) [19]crc8(0..18), little-endian */
void hg_ev_pack(const hg_ev_t *e, uint16_t boot, uint8_t out[20]);
int  hg_ev_unpack(const uint8_t in[20], hg_ev_t *e, uint16_t *boot);   /* 0 ok, < 0 bad version / CRC (x filled too) */
const char *hg_ev_name(uint8_t type);

/* ------------------------------------------------------------------ new commands (spec 5, 5b) */
enum { HG_CMD_SYNC_EVENTS = 0x16, HG_CMD_FAMILY_MSG = 0x17, HG_CMD_FAMILY_NAME = 0x18, HG_CMD_ROUTINE_SEED = 0x19,
       HG_CMD_ELDER_ACTION = 0x1A, HG_CMD_DAY_PLAN = 0x1B, HG_CMD_VISIT = 0x1C };
/* 0x1A ELDER_ACTION (the elder-mode phone app acting for the band button): [1] action, [2] nudge id for action 2 */
enum { HG_ACT_HELP = 1, HG_ACT_NUDGE_DONE = 2, HG_ACT_HELP_CANCEL = 3, HG_ACT_IM_OK = 4 };
/* event arg for IM_OK / HELP / HELP_CANCEL: where it came from */
enum { HG_SRC_BAND = 1, HG_SRC_PHONE = 2 };
#define HG_FAMNAME_MAX 14
/* ROUTINE_SEED: hour/minute pairs, 0xFF 0xFF = not set; flags 0xFF = not set, else bit0 = A/C at home */
typedef struct {
  uint8_t wake_h, wake_m, bed_h, bed_m, nap_fh, nap_fm, nap_th, nap_tm;
  uint8_t o1_fh, o1_fm, o1_th, o1_tm, o2_fh, o2_fm, o2_th, o2_tm, flags;
} hg_seed_t;
/* ---- 0.9.8 "Her Day" (HERDAY_SPEC.md 3-4) */
enum { HG_PL_HOME = 0, HG_PL_MARKET = 1, HG_PL_CHURCH = 2, HG_PL_WALK = 3, HG_PL_PHARMACY = 4, HG_PL_CAFE = 5, HG_PL_DOCTOR = 6,
       HG_PL_OTHER = 7, HG_PL_N = 8 };
enum { HG_DPK_OUTING_SHIFT = 1, HG_DPK_AIR_OPEN = 2, HG_DPK_HEATWAVE_DAY = 3 };
enum { HG_DIR_BEFORE = 1, HG_DIR_AFTER = 2 };
enum { HG_VISIT_ARRIVE = 1, HG_VISIT_LEAVE = 2 };
#define HG_DP_MAX 6
/* one DAY_PLAN item, normalised: fields a kind does not use are 0 (kind 1 usual = 0xFF 0xFF when n/a; peak 0xFF unknown) */
typedef struct { uint8_t kind, place, usual_h, usual_m, sugg_h, sugg_m, dir, hot_from, hot_to, peak_c, hw_day; } hg_dpi_t;
typedef struct { uint8_t n; hg_dpi_t it[HG_DP_MAX]; } hg_dpday_t;
/* day[0] today, day[1] tomorrow; today = local day index they belong to (-1: clock never known since the plan came) */
typedef struct { int32_t today; hg_dpday_t day[2], stage[2]; uint8_t stage_mask[2]; } hg_dayplan_t;
typedef struct {
  uint8_t op;
  uint16_t since_seq, boot;                 /* 0x16 */
  uint8_t msg;                              /* 0x17: 1 calls you, 2 is coming, 3 saw the message */
  char name[HG_FAMNAME_MAX + 1];            /* 0x18: UTF-8, NUL-terminated; "" = back to the default */
  hg_seed_t seed;                           /* 0x19 */
  uint8_t action, nudge_id;                 /* 0x1A */
  uint8_t dp_day, dp_index, dp_n; hg_dpi_t dpi;   /* 0x1B (dpi normalised) */
  uint8_t v_event, v_place; uint32_t v_unix;      /* 0x1C */
} hg_eco_cmd_t;
/* 0 = not one of 0x16..0x1C (give it to the frozen hg_cmd_parse), > 0 = the opcode, < 0 = HG_CMD_ERR_* (same codes as
 * hg_frames.h: -1 short, -2 CRC, -3 op, -4 field). Every frame is exactly 20 B with the CRC-8 in byte 19. */
int  hg_eco_cmd_parse(const uint8_t *p, uint16_t n, hg_eco_cmd_t *c);
void hg_eco_pack_sync(uint16_t since_seq, uint16_t boot, uint8_t out[20]);
void hg_eco_pack_msg(uint8_t msg, uint8_t out[20]);
int  hg_eco_pack_name(const char *utf8, uint8_t out[20]);          /* < 0 if longer than 14 B or not valid UTF-8 */
void hg_eco_pack_seed(const hg_seed_t *s, uint8_t out[20]);
void hg_eco_pack_action(uint8_t action, uint8_t nudge_id, uint8_t out[20]);
/* 0x1B: bytes 4..14 from the item as given (raw: kind, place, usual h/m, sugg h/m, dir, hot from/to, peak, hw day) */
void hg_eco_pack_dayplan(uint8_t day, uint8_t index, uint8_t n, const hg_dpi_t *it, uint8_t out[20]);
void hg_eco_pack_visit(uint8_t event, uint8_t place, uint32_t unix_s, uint8_t out[20]);
void hg_seed_clear(hg_seed_t *s);                                  /* everything "not set" */
uint16_t hg_seed_mod(uint8_t h, uint8_t m);                        /* minute of day, 0xFFFF if not set */
int  hg_seed_any(const hg_seed_t *s);                              /* 1 if any field is set */
int  hg_utf8_ok(const uint8_t *s, uint16_t n);                     /* well-formed, no control characters */

/* ------------------------------------------------------------------ day plan store (HERDAY_SPEC 4) */
void hg_dp_init(hg_dayplan_t *d);
/* local midnight: tomorrow becomes today. day < 0 (clock unknown): nothing. Returns 1 if the content / day changed (save). */
int  hg_dp_roll(hg_dayplan_t *d, int32_t day);
/* one parsed DAY_PLAN item. Returns 1 when the day's set is complete and REPLACES the stored day (index 0, n 0 = clear),
 * 0 while staged. A set restarts when n changes or an index arrives twice; the stored day never holds a partial set. */
int  hg_dp_apply(hg_dayplan_t *d, uint8_t day, uint8_t index, uint8_t n, const hg_dpi_t *it);
int  hg_dp_first_outing(const hg_dpday_t *d);       /* index of the kind-1 item with the earliest usual time (else sugg), -1 */
int  hg_dp_find(const hg_dpday_t *d, uint8_t kind); /* first item of that kind, -1 */
int  hg_dp_in_hot(const hg_dpday_t *d, uint16_t mod);   /* mod inside any kind-1 hot window [from, to) */
/* EVENTS type 10 payload (bytes 11-18): place, usual h, m, sugg h, m, hot from, to, day | dir << 1 | hw_day << 3 */
void hg_dp_echo(const hg_dpi_t *it, uint8_t day, uint8_t x[8]);
void hg_visit_echo(uint8_t event, uint32_t unix_s, uint8_t x[8]);   /* type 9: [11] event, [12-15] u32 unix */
#define HG_DP_FILE 148                              /* /dayplan.bin image: magic, version, today, 2 x (n + 6 x 11), CRC-32 */
void hg_dp_file_pack(const hg_dayplan_t *d, uint8_t out[HG_DP_FILE]);
int  hg_dp_file_unpack(hg_dayplan_t *d, const uint8_t *in, uint16_t n);   /* 0 ok; < 0 -> d = empty */
const char *hg_place_word(uint8_t place);           /* «αγορά» ... («έξοδο» for home / unknown) */

/* ------------------------------------------------------------------ planner (spec 2, 5b; HERDAY 5) */
enum { HG_N_BRIEF = 1, HG_N_LAST_COOL = 2, HG_N_SHUTTERS = 3 /* removed in 0.9.8, id kept */, HG_N_WATER = 4, HG_N_AIR = 5,
       HG_N_AC = 6, HG_N_EVENING = 7, HG_N_LEAVE_HOT = 8, HG_N_COUNT = 9 };
#define HG_PLAN_MAX_DAY     6      /* nudges per day, all kinds */
#define HG_PLAN_SPACING     60     /* min between two nudges (from the start of the last one) */
#define HG_PLAN_SHOW_MIN    10     /* a nudge stays active up to 10 min, then MISSED */
#define HG_PLAN_N4_EVERY    90     /* WATER: every 90 min while hot (from the last WATER shown or DONE) */
#define HG_PLAN_N4_MAX      4
#define HG_PLAN_HOT_C       28     /* forecast T_in / room >= 28 C: hot hour (N3, N4, N6) */
#define HG_PLAN_AIR_ROOM_C  27     /* N5 room rule */
#define HG_PLAN_VERY_HOT_C  30     /* main face next-hours line */
#define HG_PLAN_N8_MAX      2      /* LEAVE_HOT: max 2 a day, once per outing */
#define HG_PLAN_N8_REARM    30     /* re-armed after >= 30 min back HOME */
#define HG_PLAN_N8_WAIT     10     /* a leave stays eligible 10 min (a warning / the sleep window may be on at the door) */
#define HG_PLAN_N7_DEF_BED  (22u * 60u)   /* N7 at bedtime - 60 min; default bedtime 22:00 -> 21:00 */
typedef struct { uint8_t kind, place, dir, h, m, hw; } hg_ptxt_t;   /* N1 / N7 text parameters (kind 0 = classic N1 / none) */
typedef struct {
  int32_t day;                     /* local day the counters belong to, -1 none */
  uint8_t count, n4_count, active, active_left, brief_hh;   /* brief_hh: end of the safe window, 0xFF none */
  uint16_t shown_mask;             /* bit id: shown today */
  uint16_t last_mod, n4_last;      /* minute of day of the last nudge / last WATER (shown or DONE), 0xFFFF none */
  uint32_t shown, done, missed;    /* since boot, for stat */
  /* 0.9.8 */
  uint8_t n8_count, n8_armed, n8_pending, prev_ho, visit_home;
  int32_t home_since;              /* absolute local minute (day x 1440 + mod) since she is HOME, -1 not home */
  hg_ptxt_t t1, t7;
} hg_plan_t;
typedef struct {
  uint16_t mod; int32_t day;       /* local minute of day / day index; 0xFFFF / -1 = clock unknown -> no nudge */
  uint8_t warning;                 /* a guardian warning (any state but OK) or a held HELP / I'm OK toast is on */
  const uint8_t *fc72;             /* forecast 24 x (i8 T_in, u8 RH, u8 flags) when complete, else NULL */
  uint32_t safe_bitmap; uint8_t have_safe;
  float room_c;                    /* SHTC3 minute mean, NAN unknown */
  const hg_seed_t *seed;           /* ROUTINE_SEED or NULL */
  uint8_t l_valid, l_days;         /* learned routine (frozen Body Twin routine): sleep window valid, days learned */
  uint16_t l_sleep_on, l_sleep_off;
  uint8_t press;                   /* evaluating a short press now (N1 "first wake-up press") */
  uint8_t ext_nudge;               /* the frozen guardian's own bedtime nudge is on this minute: counts for spacing */
  const hg_dpday_t *dp_today, *dp_tomorrow;   /* 0.9.8 day plan (NULL = none / not for this day) */
  uint8_t home_out;                /* 0.9.8 HG_HO_* this minute (frozen home/out state or the console `homeout`), 0xFF unknown */
  uint8_t hold;                    /* 0.9.9 validity gate (hg_fw_alert.c): no new nudge now (an open one is NOT cancelled, it waits) */
  uint8_t herday_only;             /* 0.9.17 owner decision (Nov 19 18:04): only Her Day timing advice on the band - N1 only with a
                                    * plan outing, N7, N8; no clock-driven generic nudges (N2 last cool hour, N4 water, N5 air, N6 A/C) */
} hg_plan_in_t;
typedef struct { uint8_t show, missed; } hg_plan_out_t;

void    hg_plan_init(hg_plan_t *p);
void    hg_plan_minute(hg_plan_t *p, const hg_plan_in_t *in, hg_plan_out_t *out);   /* once a minute */
uint8_t hg_plan_press(hg_plan_t *p, const hg_plan_in_t *in);       /* on a short press: N1 by press; returns id or 0 */
uint8_t hg_plan_done(hg_plan_t *p, uint16_t mod);                  /* press on the nudge screen: id DONE, or 0 */
uint8_t hg_plan_cancel(hg_plan_t *p);                              /* a warning replaced it: id MISSED, or 0 */
uint8_t hg_plan_force(hg_plan_t *p, uint8_t id, const hg_plan_in_t *in);   /* console `nudge <id>` (no caps); 0 = none / no text */
/* 0.9.8 N8: a VISIT from her phone (fresh = the visit time is within 10 min of the band clock) and the console `homeout`:
 * both may show N8 at once (out->show; out->missed = a lower nudge it replaced) */
void    hg_plan_visit(hg_plan_t *p, const hg_plan_in_t *in, uint8_t event, uint8_t place, uint8_t fresh, hg_plan_out_t *out);
void    hg_plan_homeout(hg_plan_t *p, const hg_plan_in_t *in, hg_plan_out_t *out);
int     hg_plan_hot_now(const hg_plan_in_t *in);           /* N8 condition: hot window of today's plan / non-safe hour of a heat-day */
uint16_t hg_plan_n7_time(const hg_plan_in_t *in);          /* N7 minute of day (bedtime - 60) */
int     hg_plan_quiet(const hg_plan_in_t *in);                     /* sleep window or nap: no nudge */
uint16_t hg_plan_wake_ref(const hg_plan_in_t *in);                 /* the N1 reference wake time (minute of day) */
int     hg_fc_safe(const hg_plan_in_t *in, int h);                 /* hour h safe (SAFE_HOURS bitmap, else forecast flag) */
int     hg_fc_first_safe(const hg_plan_in_t *in, int from_h, int *start, int *end);   /* first run ending after from_h */

/* ------------------------------------------------------------------ texts (UTF-8 Greek; ° and ✓ are drawn, not font glyphs) */
const char *hg_nudge_text(const hg_plan_t *p, uint8_t id, char *buf, uint16_t n);
/* reason line for DRINK/COOL/CHECK/DANGER: BODY|NN|DANGER_P > ENV_LIMIT (+ room C) > TIME_IN_HEAT > NO_RESPONSE_G;
 * "" when only UNCERTAIN (or nothing) is set or the screen is another one */
const char *hg_reason_text(uint8_t why, uint8_t screen, float room_c, char *buf, uint16_t n);
const char *hg_family_text(uint8_t msg, const char *name, char *buf, uint16_t n);   /* {name}: σας καλεί ... */
extern const char HG_TXT_BRAVO[], HG_TXT_FAMACK[], HG_TXT_FAMDEF[], HG_TXT_COOL_PM[];
const char *hg_next_hours_text(const uint8_t *fc72, uint16_t mod, char *buf, uint16_t n);   /* main face, "" none */
void hg_local_date(int32_t day, int *y, int *mon, int *mday, int *wday);   /* day = days since 1970-01-01 (local) */
const char *hg_date_text(int32_t day, char *buf, uint16_t n);     /* «Τρι 17 Νοε», "" when the day is unknown */
/* 30-min room trend: +1 up (>= +0.5 C), 0 flat, -1 down, -2 unknown. ring = 31 x c100 (INT16_MIN = no value) */
typedef struct { int16_t c100[31]; uint8_t i, n; } hg_trend_t;
void hg_trend_init(hg_trend_t *t);
void hg_trend_push(hg_trend_t *t, float room_c);
int  hg_trend_dir(const hg_trend_t *t);

#ifdef __cplusplus
}
#endif
#endif
