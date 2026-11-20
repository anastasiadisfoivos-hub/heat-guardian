/* Body Twin -- on-band personalisation (B3, Heat Guardian AI sprint).
 * C99, float only, no malloc, no expf/logf/powf, no flash writes (the caller owns the save).
 * Spec: /home/claude/hg_ai/arch/ARCHITECTURE.md section 5; reference: twin/hg_twin.py (matches bit-for-bit
 * on the golden nights, checked by twin/c/host_test.c).
 *
 * Call pattern on the band (B5 hg_guardian_step / B6 sketch):
 *   boot:           hg_twin_unpack(file) -> on error hg_twin_defaults(); hg2_init(..., &twin)
 *   every minute:   hg_twin_note_tier(&acc, tier >= DRINK);  hg_twin_set_air_ref(&acc, T_ref or NAN);
 *                   hg_twin_ingest_minute(&acc, &in, asleep, location, hr_valid);
 *   phone reading:  hg_twin_ingest_reading(&acc, ...); if (hg_twin_commit_reading(&twin, &acc)) { hg2_set_twin; save; }
 *   phone room T:   hg_twin_ingest_room_reading(&acc, t_room, t_air_meas, t1)
 *   nightly:        if (hg_twin_nightly_update(&twin, &acc)) { hg2_set_twin(); hg_twin_pack(); save once }
 */
#ifndef HG_TWIN_H
#define HG_TWIN_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* The shared structs hg2_twin_t / hg2_in_t are owned by B5's guardian/c/hg2_step.h (ARCHITECTURE 4.5).
 * Build with -DHG_TWIN_USE_HG2_STEP_H once that header exists; otherwise this verbatim copy is used.
 * host_test.c checks the layout (sizeof, offsets) so a drift between the two shows up at build time. */
#if defined(HG_TWIN_USE_HG2_STEP_H)
#include "hg2_step.h"
#else
#ifndef HG2_STEP_H
typedef struct {                 /* Body Twin parameters (owned by hg_twin, read by hg2_step) */
  float rest_hr;                 /* bpm, bounds 40..100, default 70 */
  float k_person;                /* capped gap gain (field name kept for hg2_step), bounds 0.03..0.40, default 0.12 */
  float core_offset;             /* degC added to displayed/alarm core, bounds -0.8..+0.8, default 0 */
  float c_bodyheat;              /* SHTC3 contamination coefficient, bounds 0..0.4, default 0.15 */
  float t1_night_base[24];       /* degC per hour-of-day, NAN until learned */
  uint8_t days_learned;
} hg2_twin_t;

typedef struct {                 /* one minute of inputs; NAN = not available */
  float t1_c, t2_c;              /* 1-min means; t2_c = NAN when no REF board */
  float t_air_c, rh_pct;         /* SHTC3 1-min means */
  float hr_bpm;                  /* 1-min median from hg_ppg, NAN if none */
  uint8_t hr_quality;            /* hg_ppg word: 0 no skin, 1 low PI, 2 motion, 3 irregular, 4 OK */
  float pi_pct;                  /* perfusion index, NAN if none */
  float a_std_g;                 /* 1-min std of |a| in g */
  uint8_t worn;                  /* from hg_contact: 0 off, 1 loose, 2 worn */
  uint16_t minute_of_day;        /* 0..1439, 0xFFFF = unknown */
} hg2_in_t;
#endif
#endif

/* ---- bounds and defaults (ARCHITECTURE 4.5 / 5) ---- */
#define HG_TWIN_REST_HR_DEF   70.0f
#define HG_TWIN_REST_HR_MIN   40.0f
#define HG_TWIN_REST_HR_MAX  100.0f
#define HG_TWIN_K_DEF          0.12f
#define HG_TWIN_K_MIN          0.03f
/* Capped gap gain rule (DECISIONS M4.1: it is NOT the physical K (R_tissue/R_ins) -- it learns the whole wrist-core gap per
 * degC of dT, incl. the axial drop, capped; K_true is not recoverable from oral readings, corr 0.17 on SIM-DEV).
 *   0  as ARCHITECTURE 5 (default): g <- g + 0.5*((T_read - off - T1)/dT - g), bounds 0.03..0.40
 *   1  K_eff: same formula, upper bound 1.5 -> learns the whole wrist-core gap per degC of dT (incl. the axial drop)
 *   2  off: K is never learned; a reading only moves core_offset
 * hg2_step's core_flux clamp [T1, T1 + 2.5] applies unchanged. */
#ifndef HG_TWIN_K_RULE
#define HG_TWIN_K_RULE 0
#endif
#if HG_TWIN_K_RULE == 1
#define HG_TWIN_K_MAX          1.5f
#else
#define HG_TWIN_K_MAX          0.40f
#endif
#ifndef HG_TWIN_BETA_OFF
#define HG_TWIN_BETA_OFF       0.25f   /* DECISIONS M4.2 (HTT beta sweep peak; sim same-day cost 14 %) */
#endif

/* DECISIONS M4.3 -- what a phone oral reading may do:
 *   0  display-only (default): the reading moves core_offset only; the capped gap gain is never learned.
 *      Reason: the two sources found disagree on the oral->core bias (0.14 vs 0.36 degC) and both put
 *      single-reading 95 % limits at about +-0.75 degC, so no single sourced correction is solid.
 *      NOTE for hg2/B5: in this mode core_offset should feed the displayed core only, not the alarm tiers.
 *   1  sourced: t_core = t_read + HG_TWIN_ORAL_TO_CORE before both rules (gap gain + offset).
 * HG_TWIN_ORAL_TO_CORE = +0.14 degC: core-minus-oral bias 0.14 +- 0.37 degC, LoA -0.60..+0.90, electronic oral
 *   thermometer (Welch Allyn SureTemp Plus 690) vs ingestible pill, 19 adults free-living (Rajbhandary &
 *   Nallathambi 2021, arXiv:2108.00537). Alternative: rectal-minus-oral 0.648 degF = 0.36 degC (SD 0.34 degC),
 *   mercury glass, 116 inpatients mean age 61.6 (Smith 2003, BMC Nursing 2:1, doi 10.1186/1472-6955-2-1). */
#ifndef HG_TWIN_READING_MODE
#define HG_TWIN_READING_MODE   0
#endif
#ifndef HG_TWIN_ORAL_TO_CORE
#define HG_TWIN_ORAL_TO_CORE   0.14f
#endif
/* DECISIONS M4.4 / T3 F10: readings are dropped while any alarm tier is on and for 30 min after it ends. */
#define HG_TWIN_TIER_HOLDOFF_MIN 30u
#define HG_TWIN_OFF_DEF        0.0f
#define HG_TWIN_OFF_MIN       (-0.8f)
#define HG_TWIN_OFF_MAX        0.8f
#define HG_TWIN_C_DEF          0.15f
#define HG_TWIN_C_MIN          0.0f
#define HG_TWIN_C_MAX          0.4f

#define HG_TWIN_LOC_HOME    0
#define HG_TWIN_LOC_TRANSIT 1
#define HG_TWIN_LOC_OUT     2

/* ---- persisted file /twin.bin (little-endian), version 3 ----
 *   0  u32 magic 0x4857544E ('HWTN')     4  u16 version = 3     6  u16 length (whole file incl. CRC)
 *   8  hg2_twin_t packed, 113 B: f32 rest_hr, k_person (capped gap gain), core_offset, c_bodyheat, f32 t1_night_base[24], u8 days_learned
 * 121  twin learning state, 72 B: u8 t1_n[24], i16 t1_pre_cd[24]
 * 193  Guardian design-A calm baseline (DECISIONS M9.5), 5 B: f32 calm_f20 (NAN when calm_n == 0), u8 calm_n
 * 198  [v4, B5-v7] Guardian Exception-DRINK movement sums (M19.2), 8 B: f32 exc_sxx (>= 0), f32 exc_sxy; 0/0 = not learned
 * 206  routine profile bytes (opaque, owned by hg_routine), routine_len = length - 214
 * 206+R u32 save_count
 * 210+R u32 crc32 (zlib / poly 0xEDB88320, over bytes 0 .. 209+R)
 * total = 214 + R bytes; <= 900 B (7 LittleFS blocks) requires R <= 686 (B5 routine: 650 -> 864 B).
 * Version-3 files (no Exception block, 206 + R B) and version-2 files (no calm block, 201 + R B) are still accepted on load
 * with the missing blocks empty (an old file restarts the Exception slope from zero, as before v4). */
#define HG_TWIN_MAGIC      0x4857544Eu
#define HG_TWIN_VERSION    4u
#define HG_TWIN_VERSION_V3 3u
#define HG_TWIN_VERSION_V2 2u
#define HG_TWIN_FIXED_LEN  214u
#define HG_TWIN_FIXED_LEN_V3 206u
#define HG_TWIN_FIXED_LEN_V2 201u
#define HG_TWIN_FILE_MAX   900u
#define HG_TWIN_CD_NONE    (-32768)
/* calm-f20 bounds: same values as B5's HG_A_BASE_MIN/MAX (guardian/c/hg_guardian_cfg.h) */
#define HG_TWIN_CALM_MIN   36.8f
#define HG_TWIN_CALM_MAX   37.7f
/* Exception sums bounds (B5-v7): a day adds <= 840 min x (30 x 0.30 g)^2 = 68 040 to sxx; decay 0.85 -> steady state <= 4.6e5 */
#define HG_TWIN_EXC_MAX    1.0e7f

/* Accumulator: RAM learning state between nightly updates (<= 256 B, no pointers).
 * The t1_n / t1_pre_cd block is persistent (it is part of the file), everything else is reset nightly. */
typedef struct {
  /* persistent (packed into the file) */
  uint8_t  t1_n[24];          /* Welford count per hour-of-day, capped 30 */
  int16_t  t1_pre_cd[24];     /* running mean (centi-degC) while n < 3; HG_TWIN_CD_NONE otherwise */
  /* nightly */
  uint8_t  hist[64];          /* sleep HR histogram, 1 bpm bins 40..104, halved when a bin reaches 255 */
  uint16_t hist_n;            /* valid still sleep minutes (saturating) */
  int16_t  today_cd[24];      /* today's qualifying hourly mean T1 (centi-degC) or CD_NONE */
  float    cur_sum;           /* running sum of the current hour's qualifying T1 */
  uint8_t  cur_cnt, cur_h;    /* count, hour (255 = none) */
  float    c_sxx, c_sxy, c_w; /* through-origin LS for c_bodyheat, weight */
  float    air_ref;           /* reference air T for OUT-walking minutes (NAN if none) */
  uint16_t night_n, night_bad;/* night minutes, of which worn != 2 */
  uint8_t  night_alarm, tier_now;
  uint8_t  rd_pending, rd_flux;
  float    rd_t_read, rd_t1, rd_dT, rd_core;
  uint8_t  last_frozen;       /* survives the nightly reset (diagnostics) */
  uint8_t  min_since_tier;    /* minutes since an alarm tier was last on (255 = long ago); M4.4 hold-off */
  /* persistent, owned by the Guardian (design A, M9.5): stored here only so it reaches the save file */
  float    calm_f20;          /* degC, NAN when calm_n == 0 */
  uint8_t  calm_n;            /* days learned (Guardian's a_base_n), 0 = not learned */
  float    exc_sxx, exc_sxy;  /* B5-v7: Guardian Exception-DRINK movement sums (M19.2), persisted (v4); 0/0 = not learned */
} hg_twin_acc_t;

void hg_twin_defaults(hg2_twin_t *tw);
void hg_twin_acc_init(hg_twin_acc_t *acc);          /* all-empty accumulator, persistent part reset too */

void hg_twin_note_tier(hg_twin_acc_t *acc, uint8_t tier_on);      /* any tier >= DRINK on this minute */
void hg_twin_set_air_ref(hg_twin_acc_t *acc, float t_ref_c);      /* NAN = none */
void hg_twin_ingest_minute(hg_twin_acc_t *acc, const hg2_in_t *in, uint8_t asleep, uint8_t location, uint8_t hr_valid);
void hg_twin_ingest_room_reading(hg_twin_acc_t *acc, float t_room, float t_air_meas, float t1);

void hg_twin_ingest_reading(hg_twin_acc_t *acc, float t_read, float t1_5min, float dT_5min, float core_now, uint8_t flux_valid);
int  hg_twin_commit_reading(hg2_twin_t *tw, hg_twin_acc_t *acc);   /* 1 if gap gain/offset changed; 0 if dropped (tier hold-off) */

/* returns 1 if anything persistent changed (caller saves once). acc->last_frozen tells why learning was
 * skipped: 0 not frozen, 1 alarm during the night, 2 < 60 night minutes observed, 3 worn != 2 > 30 % of night.
 * The core_offset decay (x 0.70710678, half-life 2 nights) runs even when frozen. */
int  hg_twin_nightly_update(hg2_twin_t *tw, hg_twin_acc_t *acc);

/* pack: returns bytes written (214 + routine_len, v4) or -1 (buffer too small / > 900 B).
 * unpack: returns 0 on success; on any error (size, magic, version, length, CRC, out-of-bounds value)
 * returns < 0 and leaves tw/acc at defaults, *routine_len = 0, *save_count = 0. */
int  hg_twin_pack(const hg2_twin_t *tw, const hg_twin_acc_t *acc, const void *routine, uint16_t routine_len,
                  uint32_t save_count, uint8_t *buf, uint16_t buflen);
int  hg_twin_unpack(const uint8_t *buf, uint16_t len, hg2_twin_t *tw, hg_twin_acc_t *acc,
                    void *routine, uint16_t routine_cap, uint16_t *routine_len, uint32_t *save_count);

uint32_t hg_twin_crc32(uint32_t crc, const void *p, uint32_t n);   /* == zlib.crc32 */

/* Guardian design-A calm baseline (M9.5). B5 calls hg_twin_set_calm(&acc, g->a_base, g->a_base_n) after its midnight
 * update (before the save) and hg_twin_get_calm() after hg_twin_unpack() at boot to restore a_base / a_base_n.
 * set: n == 0 or non-finite f20 -> empty (NAN, 0); otherwise f20 clamped to [36.8, 37.7]. get returns n. */
void    hg_twin_set_calm(hg_twin_acc_t *acc, float calm_f20, uint8_t calm_n);
uint8_t hg_twin_get_calm(const hg_twin_acc_t *acc, float *calm_f20);
/* B5-v7: Guardian Exception-DRINK sums (hg_guardian_get_exc / set_exc). set: non-finite, sxx < 0 or |value| > 1e7 -> 0/0.
 * get returns 1 if learned (sxx > 0). */
void    hg_twin_set_exc(hg_twin_acc_t *acc, float sxx, float sxy);
int     hg_twin_get_exc(const hg_twin_acc_t *acc, float *sxx, float *sxy);

/* Clamp/repair every parameter and learning-state entry (bounds + consistency). Called at the start and the end of
 * every update; call it before hg2_set_twin() if the twin was touched by anything else. */
void hg_twin_sanitize(hg2_twin_t *tw, hg_twin_acc_t *acc);

#ifdef __cplusplus
}
#endif

#endif
