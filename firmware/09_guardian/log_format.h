/* Heat Guardian 08_logger: the 24-byte record (ARCHITECTURE §8, brief B6 Part A).
 *
 * One record per second (and one 1-minute summary per minute in /log/min.bin).
 * Little-endian, packed by hand (no struct packing / endianness assumptions), so the
 * same code runs on the band (ARM, LE) and on the host test (x86, LE) and the Python
 * parser can follow the byte table below exactly.
 *
 * FORMAT v2 (written from 1.1.2 on). The version is in the CRC byte: v2 stores CRC-8 XOR 0xFD, v1 stored the plain
 * CRC-8. A record therefore matches exactly one of the two (never both); hg_rec_unpack() and parse_log.py accept
 * both, so v1 files from 1.1.1 still parse. v2 adds the z-angle at 0.01 deg and, in minute records, the whole-minute
 * a_std computed exactly as the 09 guardian gets it (hg_astd.h).
 *
 *  byte  field        type  meaning (v2)
 *  0-3   t_ms         u32   ms since boot (millis()); minute records: start of the minute
 *  4-5   t1           i16   insulated skin TMP117 0x48, degC x100; 0x7FFF = absent
 *  6-7   t2           i16   reference TMP117 0x49, degC x100; 0x7FFF = absent
 *  8-9   tair         i16   SHTC3 temperature, degC x100; 0x7FFF = absent
 *  10    rh           u8    SHTC3 RH %, 255 = absent
 *  11    hr           u8    hg_ppg heart rate bpm, 0 = none
 *  12    marker|hr_q  u8    low nibble: marker 0 none, 1 donned, 2 loose, 3 off, 4 shower, 5 out, 6 home, 7 oral
 *                           reading, 8 help (long press), 9 button/custom, 10 boot, 11 time sync, 12 file start;
 *                           high nibble: hg_ppg quality 0 no skin,1 low PI,2 motion,3 irregular,4 OK; 15 = PPG off
 *  13-14 pi           u16   perfusion index % x100
 *  15-16 a_std        u16   std of |a| over the second, g x1e4 (minute: mean of the seconds' values); 0xFFFF = no IMU
 *  17-18 zangle       i16   z-angle in degrees x100 (0.01 deg), median of the last 5 s (minute: mean)
 *  19    flags        u8    bit0 button, bit1 charging/USB, bit2 BLE connected, bit3 impact (|a| >= HG_IMPACT_G = 3 g, B5-v7),
 *                           bit4 marker present, bit5 time valid, bit6 MINUTE summary, bit7 low-battery mode
 *  20    dc8          u8    1 Hz record: IR DC / 1024 (0..255, ~no skin below 20)
 *                           minute record: VBAT code = (V - 2.00) x 100 (0 = unknown)
 *  21-22 aux          u16   1 Hz record: marker 7: oral degC x100; markers 10/12: boot count (low 16 bits);
 *                           otherwise red-LED DC / 4 (latest 1/4-duty red window), 0 = none
 *                           minute record: a_std over the WHOLE minute, g x1e4 (= the 09 guardian input
 *                           hg2_in_t.a_std_g, hg_astd.h); 0xFFFF = fewer than 3 samples. EXCEPT when the minute's
 *                           marker is 7 / 10 / 12 (oral reading, boot, file): then the marker value as in v1, so the
 *                           minute file keeps its boot numbers and oral readings (that minute has no a_std_min).
 *  23    crc          u8    CRC-8 poly 0x07, init 0x00, no reflection, over bytes 0..22, XOR 0xFD (v2)
 *
 * v1 (1.1.1 and older): 12 hr_q, 13-14 pi, 15-16 a_std, 17 zangle i8 whole degrees, 18 flags, 19 marker, 20 dc8,
 * 21-22 aux (also in minute records: marker value or red DC / 4), 23 plain CRC-8.
 * 09_guardian's guardian record (marker 13 at byte 19, fw/09_guardian/hg_fw.c) keeps its own layout and the plain CRC.
 */
#ifndef HG_LOG_FORMAT_H
#define HG_LOG_FORMAT_H
#include <stdint.h>
#include <stddef.h>

#define HG_REC_SIZE      24
#define HG_REC_HEX_LEN   48
#define HG_T_ABSENT      ((int16_t)0x7FFF)
#define HG_RH_ABSENT     255
#define HG_HRQ_NONE      255

enum {
  HG_F_BUTTON = 0x01, HG_F_CHARGING = 0x02, HG_F_BLE = 0x04, HG_F_IMPACT = 0x08,
  HG_F_MARKER = 0x10, HG_F_TIME_VALID = 0x20, HG_F_MINUTE = 0x40, HG_F_LOWBAT = 0x80
};

enum {
  HG_M_NONE = 0, HG_M_DONNED = 1, HG_M_LOOSE = 2, HG_M_OFF = 3, HG_M_SHOWER = 4, HG_M_OUT = 5,
  HG_M_HOME = 6, HG_M_ORAL = 7, HG_M_HELP = 8, HG_M_BUTTON = 9, HG_M_BOOT = 10, HG_M_TIME = 11,
  HG_M_FILE = 12, HG_M_COUNT = 13
};

/* v2 minute records: bytes 21-22 hold the marker value for these markers, the whole-minute a_std otherwise */
#define HG_REC_MIN_AUX_MARKER(m) ((m) == HG_M_ORAL || (m) == HG_M_BOOT || (m) == HG_M_FILE)
#define HG_REC_V2_XOR    0xFD            /* v2 CRC byte = CRC-8 ^ 0xFD: not the syndrome of any 1- or 2-bit error over bytes 0..22 */

typedef struct {
  uint32_t t_ms;
  int16_t  t1_c100, t2_c100, tair_c100;
  uint8_t  rh, hr, hr_q;
  uint16_t pi_100, astd_1e4;
  int16_t  zangle_c100;                   /* degrees x100 (v1 files: whole degrees x100) */
  uint8_t  flags, marker, dc8;
  uint16_t aux;                           /* 1 Hz records (and v1 minute records) */
  uint16_t astd_min_1e4;                  /* minute records v2: whole-minute a_std; 0xFFFF = absent / v1 */
  uint8_t  ver;                           /* set by hg_rec_unpack: 1 or 2 */
} hg_rec_t;

/* CRC-8/SMBUS: poly 0x07, init 0x00, no reflection, no xor-out. check("123456789") = 0xF4 */
static inline uint8_t hg_crc8(const uint8_t *p, size_t n)
{
  uint8_t c = 0;
  while (n--) {
    c ^= *p++;
    for (int k = 0; k < 8; k++) c = (uint8_t)((c & 0x80) ? ((c << 1) ^ 0x07) : (c << 1));
  }
  return c;
}

static inline void hg_put16(uint8_t *b, uint16_t v) { b[0] = (uint8_t)v; b[1] = (uint8_t)(v >> 8); }
static inline uint16_t hg_get16(const uint8_t *b) { return (uint16_t)(b[0] | ((uint16_t)b[1] << 8)); }

/* always writes v2 */
static inline void hg_rec_pack(const hg_rec_t *r, uint8_t b[HG_REC_SIZE])
{
  b[0] = (uint8_t)r->t_ms; b[1] = (uint8_t)(r->t_ms >> 8); b[2] = (uint8_t)(r->t_ms >> 16); b[3] = (uint8_t)(r->t_ms >> 24);
  hg_put16(b + 4, (uint16_t)r->t1_c100);
  hg_put16(b + 6, (uint16_t)r->t2_c100);
  hg_put16(b + 8, (uint16_t)r->tair_c100);
  b[10] = r->rh; b[11] = r->hr;
  b[12] = (uint8_t)((r->marker & 15) | ((r->hr_q > 14 ? 15 : r->hr_q) << 4));
  hg_put16(b + 13, r->pi_100);
  hg_put16(b + 15, r->astd_1e4);
  hg_put16(b + 17, (uint16_t)r->zangle_c100);
  b[19] = r->flags; b[20] = r->dc8;
  hg_put16(b + 21, ((r->flags & HG_F_MINUTE) && !HG_REC_MIN_AUX_MARKER(r->marker & 15)) ? r->astd_min_1e4 : r->aux);
  b[23] = (uint8_t)(hg_crc8(b, 23) ^ HG_REC_V2_XOR);
}

/* v1 or v2 (by the CRC byte); returns 1 if the CRC matches either (the record is filled either way, as v2 if neither) */
static inline int hg_rec_unpack(const uint8_t b[HG_REC_SIZE], hg_rec_t *r)
{
  uint8_t c = hg_crc8(b, 23);
  int v1 = c == b[23], ok = v1 || (uint8_t)(c ^ HG_REC_V2_XOR) == b[23];
  r->t_ms = (uint32_t)b[0] | ((uint32_t)b[1] << 8) | ((uint32_t)b[2] << 16) | ((uint32_t)b[3] << 24);
  r->t1_c100 = (int16_t)hg_get16(b + 4);
  r->t2_c100 = (int16_t)hg_get16(b + 6);
  r->tair_c100 = (int16_t)hg_get16(b + 8);
  r->rh = b[10]; r->hr = b[11];
  r->pi_100 = hg_get16(b + 13);
  r->astd_1e4 = hg_get16(b + 15);
  if (v1) {
    r->ver = 1; r->hr_q = b[12]; r->zangle_c100 = (int16_t)((int8_t)b[17] * 100);
    r->flags = b[18]; r->marker = b[19]; r->dc8 = b[20]; r->aux = hg_get16(b + 21); r->astd_min_1e4 = 0xFFFF;
  } else {
    r->ver = 2; r->marker = b[12] & 15; r->hr_q = (b[12] >> 4) == 15 ? 255 : (uint8_t)(b[12] >> 4);
    r->zangle_c100 = (int16_t)hg_get16(b + 17);
    r->flags = b[19]; r->dc8 = b[20];
    if ((r->flags & HG_F_MINUTE) && !HG_REC_MIN_AUX_MARKER(r->marker)) { r->astd_min_1e4 = hg_get16(b + 21); r->aux = 0; }
    else { r->aux = hg_get16(b + 21); r->astd_min_1e4 = 0xFFFF; }
  }
  return ok;
}

/* 48 lowercase hex chars, NUL-terminated (out must hold 49 bytes) */
static inline void hg_hex(const uint8_t *b, size_t n, char *out)
{
  static const char H[] = "0123456789abcdef";
  for (size_t i = 0; i < n; i++) { out[2 * i] = H[b[i] >> 4]; out[2 * i + 1] = H[b[i] & 15]; }
  out[2 * n] = 0;
}

/* float -> i16 x100 with saturation; NAN/absent -> HG_T_ABSENT */
static inline int16_t hg_c100(float v, int valid)
{
  if (!valid || v != v) return HG_T_ABSENT;
  float s = v * 100.0f;
  if (s > 32766.0f) s = 32766.0f;
  if (s < -32767.0f) s = -32767.0f;
  return (int16_t)(s >= 0 ? s + 0.5f : s - 0.5f);
}

#endif
