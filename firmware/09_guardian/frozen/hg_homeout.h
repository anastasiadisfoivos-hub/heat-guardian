/* Heat Guardian - HOME / TRANSIT / OUT without GPS (ARCHITECTURE 7.1 step 3; R3 s4 proposal).
 * R3 s4: "no published equivalent; label as design" -> every weight here is DESIGN and no accuracy is claimed
 * (the Nov 16-18 wear test labels it). Scored (integer, leaky) evidence + transition constraints:
 * HOME -> OUT only via TRANSIT with >= 2 min walking; OUT -> HOME via TRANSIT. */
#ifndef HG_HOMEOUT_H
#define HG_HOMEOUT_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
enum { HG_HO_HOME = 0, HG_HO_TRANSIT = 1, HG_HO_OUT = 2 };
typedef struct {
  float ta_stable, ah_stable;        /* last stable indoor air T (C) and absolute humidity (g/m3) */
  float ta_hist[6];                  /* 1-min T_air, last 6 minutes (for |dT over 5 min|) */
  int16_t score;
  uint16_t lost_min, transit_min;
  uint8_t state, hi, hn, have_stable;
  uint8_t prior[24];                 /* per-hour OUT fraction x255 (EMA), learned while time is known */
  uint8_t last_hour, out_min_hour, mins_hour, _pad;
} hg_homeout_t;
void hg_homeout_init(hg_homeout_t *h);
/* tair: corrected SHTC3 air (C); rh %; walking_min: consecutive walking minutes; ble_bucket 2 strong / 1 weak /
 * 0 lost / -1 no phone; hour 0..23 or 0xFF unknown; forecast72: 24 x (i8 T_in, u8 RH, u8 flags) or NULL */
uint8_t hg_homeout_step(hg_homeout_t *h, float tair, float rh, uint8_t walking_min, int8_t ble_bucket, uint8_t hour,
                        const uint8_t *forecast72, uint8_t has_forecast);
float hg_abs_humidity(float t, float rh);   /* g/m3, uses the Magnus table */
#ifdef __cplusplus
}
#endif
#endif
