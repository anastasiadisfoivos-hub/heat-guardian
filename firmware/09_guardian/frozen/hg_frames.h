/* Heat Guardian - BLE frames (R4 A5 layout; ARCHITECTURE 1.1, 6 ble_frame.py). All little-endian.
 * CRC-8: poly 0x07, init 0x00, no reflection, no final xor (CRC-8/SMBUS; check("123456789") = 0xF4).
 * Deviations from R4 A5, each forced by a size or field gap (REPORT_GUARDIAN.md "frames"):
 *  STATUS byte 1 bits 0-2 state codes 0 OK 1 DRINK 2 COOL 3 DANGER 4 IMOK 5 BATTERY (R4) + 6 CHECK 7 HELP (new states);
 *  STATUS byte 0 = 0x01 version in bits 0-3, bit 4 = family alert pending, bit 5 = NOT_WORN screen (R4 had no field);
 *  while bit 4 is set bytes 15-16 carry the 16-bit alarm id instead of routine score / activity.
 *  0x11 FORECAST: [0x11][6 x (i8 T_in, u8 RH, u8 flags)][crc] = 20 B; flags bits 0-2 = heat-day, night-heat, safe-hour
 *  (ARCH 6), bits 3-4 = chunk index 0..3 (repeated in all 6 hours), bits 5-7 = 0; R4's separate chunk/total bytes do not
 *  fit 20 B. Same resolution as B4's tomorrow/ble_frame.py (its vectors are the shared reference). */
#ifndef HG_FRAMES_H
#define HG_FRAMES_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
uint8_t hg_crc8(const uint8_t *p, uint16_t n);

typedef struct {
  uint8_t state_code;      /* 0..7 as above */
  uint8_t contact_ok, time_synced, charging, home, ppg_valid, family_pending, not_worn;
  float core_c, half_range_c, hr_bpm; uint8_t hr_q;
  float t1_c, t2_c, tair_c, rh_pct;  /* NAN -> 0x8000 (i16) or 255 (u8) */
  uint8_t battery_pct, routine_score, activity;
  uint16_t minute_counter, alarm_id16;
} hg_status_t;
void hg_status_pack(const hg_status_t *s, uint8_t out[20]);

typedef struct {
  uint16_t fw_version; uint32_t nn_crc; uint16_t boot_count; uint8_t reset_reason; uint16_t twin_saves; char hg2_tag[7];
} hg_info_t;
void hg_info_pack(const hg_info_t *s, uint8_t out[20]);   /* [0]=0x02 [1-2]fw [3-6]crc [7-8]boots [9]reset [10-11]saves [12-18]tag [19]crc8 */

enum { HG_CMD_NONE = 0, HG_CMD_TIME = 0x10, HG_CMD_FORECAST = 0x11, HG_CMD_FAMILY_ACK = 0x12, HG_CMD_PROFILE = 0x13,
       HG_CMD_SAFE_HOURS = 0x14, HG_CMD_DEBUG = 0x1F };
#define HG_CMD_ERR_SHORT (-1)
#define HG_CMD_ERR_CRC   (-2)
#define HG_CMD_ERR_OP    (-3)
#define HG_CMD_ERR_FIELD (-4)
typedef struct {
  uint8_t op;
  uint32_t unix_s; int8_t tz_q;                       /* 0x10 */
  uint8_t chunk;                                      /* 0x11: chunk index; data written into the forecast buffer */
  uint8_t ack_type; uint32_t alarm_id;                /* 0x12 */
  uint8_t field; float value;                         /* 0x13: field 0 thermometer reading C, 2 resting HR, 4 skin-ref gain,
                                                        * 5 medication flags (B5-v7, integer 0..31: 1 beta-blocker, 2 diuretic,
                                                        * 4 low-sweat, 8 ACE/ARB, 16 other HR-limiting drug / pacemaker);
                                                        * unknown fields are answered 0 (older bands ignore field 5) */
  uint32_t safe_bitmap; uint8_t plan_id; char tag[15]; /* 0x14 (tag NUL-terminated) */
} hg_cmd_t;
typedef struct { uint8_t data[72]; uint8_t have_mask; uint8_t complete; } hg_forecast_buf_t;
void hg_forecast_init(hg_forecast_buf_t *f);
/* returns the opcode (> 0) or a negative HG_CMD_ERR_*; FORECAST chunks are assembled into *fc (complete when all 4) */
int hg_cmd_parse(const uint8_t *p, uint16_t n, hg_cmd_t *c, hg_forecast_buf_t *fc);
#ifdef __cplusplus
}
#endif
#endif
