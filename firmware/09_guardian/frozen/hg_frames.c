#include "hg_fp.h"   /* T5 D1: first include - IEEE-exact float semantics even under -ffast-math */
#include <math.h>
#include <string.h>
#include "hg_frames.h"
#include "hg_util.h"

uint8_t hg_crc8(const uint8_t *p, uint16_t n) {
  uint8_t c = 0;
  while (n--) { c ^= *p++; for (int k = 0; k < 8; k++) c = (uint8_t)((c & 0x80u) ? (((unsigned)c << 1) ^ 0x07u) : ((unsigned)c << 1)); }
  return c;
}
static int32_t rnd100(float x) { return (int32_t)floorf(x * 100.0f + 0.5f); }
static void put16(uint8_t *b, uint16_t v) { b[0] = (uint8_t)(v & 0xFF); b[1] = (uint8_t)(v >> 8); }
static void put32(uint8_t *b, uint32_t v) { for (int i = 0; i < 4; i++) b[i] = (uint8_t)(v >> (8 * i)); }
static uint32_t get32(const uint8_t *b) { return (uint32_t)b[0] | ((uint32_t)b[1] << 8) | ((uint32_t)b[2] << 16) | ((uint32_t)b[3] << 24); }
static uint16_t i16c(float t) {                       /* degC x100 as i16, NAN/out of range -> 0x8000 */
  if (hg_isnan(t) || t < -300.0f || t > 300.0f) return 0x8000u;
  return (uint16_t)(int16_t)rnd100(t);
}
static uint8_t u8c(float v, float scale) {           /* saturating u8 of v*scale, NAN -> 0 */
  if (hg_isnan(v) || v <= 0.0f) return 0;
  float x = v * scale + 0.5f; return x >= 255.0f ? 255 : (uint8_t)x;
}

void hg_status_pack(const hg_status_t *s, uint8_t o[20]) {
  memset(o, 0, 20);
  o[0] = (uint8_t)(0x01u | (s->family_pending ? 0x10u : 0u) | (s->not_worn ? 0x20u : 0u));
  o[1] = (uint8_t)((s->state_code & 7u) | (s->contact_ok ? 8u : 0u) | (s->time_synced ? 16u : 0u) | (s->charging ? 32u : 0u)
                   | (s->home ? 64u : 0u) | (s->ppg_valid ? 128u : 0u));
  { int32_t c = hg_isnan(s->core_c) ? 0 : rnd100(s->core_c); if (c < 0) c = 0; if (c > 65535) c = 65535; put16(o + 2, (uint16_t)c); }
  o[4] = u8c(s->half_range_c, 100.0f);
  o[5] = u8c(s->hr_bpm, 1.0f);
  o[6] = s->hr_q;
  put16(o + 7, i16c(s->t1_c)); put16(o + 9, i16c(s->t2_c)); put16(o + 11, i16c(s->tair_c));
  o[13] = hg_isnan(s->rh_pct) ? 255 : u8c(s->rh_pct, 1.0f);
  o[14] = s->battery_pct;
  if (s->family_pending) put16(o + 15, s->alarm_id16); else { o[15] = s->routine_score; o[16] = s->activity; }
  put16(o + 17, s->minute_counter);
  o[19] = hg_crc8(o, 19);
}

void hg_info_pack(const hg_info_t *s, uint8_t o[20]) {
  memset(o, 0, 20);
  o[0] = 0x02; put16(o + 1, s->fw_version); put32(o + 3, s->nn_crc); put16(o + 7, s->boot_count); o[9] = s->reset_reason;
  put16(o + 10, s->twin_saves);
  for (int i = 0; i < 7 && s->hg2_tag[i]; i++) o[12 + i] = (uint8_t)s->hg2_tag[i];
  o[19] = hg_crc8(o, 19);
}

void hg_forecast_init(hg_forecast_buf_t *f) { memset(f->data, 0, 72); f->have_mask = 0; f->complete = 0; }

int hg_cmd_parse(const uint8_t *p, uint16_t n, hg_cmd_t *c, hg_forecast_buf_t *fc) {
  memset(c, 0, sizeof *c);
  if (!p || n < 2) return HG_CMD_ERR_SHORT;
  uint16_t need;
  switch (p[0]) {
    case HG_CMD_TIME: case HG_CMD_FAMILY_ACK: case HG_CMD_PROFILE: need = 7; break;
    case HG_CMD_FORECAST: case HG_CMD_SAFE_HOURS: need = 20; break;
    case HG_CMD_DEBUG: need = 3; break;
    default: return HG_CMD_ERR_OP;
  }
  if (n < need) return HG_CMD_ERR_SHORT;
  if (p[0] == HG_CMD_DEBUG) need = n > 20 ? 20 : n;
  if (hg_crc8(p, (uint16_t)(need - 1)) != p[need - 1]) return HG_CMD_ERR_CRC;
  c->op = p[0];
  switch (p[0]) {
    case HG_CMD_TIME: c->unix_s = get32(p + 1); c->tz_q = (int8_t)p[5]; break;
    case HG_CMD_FAMILY_ACK: c->ack_type = p[1]; c->alarm_id = get32(p + 2); if (c->ack_type < 1 || c->ack_type > 3) return HG_CMD_ERR_FIELD; break;
    case HG_CMD_PROFILE: { uint32_t u = get32(p + 2); float v; memcpy(&v, &u, 4); c->field = p[1]; c->value = v;
      if (hg_isnan(v)) return HG_CMD_ERR_FIELD;
      break; }
    case HG_CMD_FORECAST: {
      uint8_t ch = (uint8_t)((p[3] >> 3) & 3u);
      for (int k = 0; k < 6; k++) if (((p[3 + 3 * k] >> 3) & 3u) != ch || (p[3 + 3 * k] & 0xE0u)) return HG_CMD_ERR_FIELD;   /* chunk index must agree */
      c->chunk = ch;
      if (fc) {
        for (int k = 0; k < 6; k++) {
          int hh = ch * 6 + k;
          fc->data[3 * hh] = p[1 + 3 * k]; fc->data[3 * hh + 1] = p[2 + 3 * k]; fc->data[3 * hh + 2] = (uint8_t)(p[3 + 3 * k] & 0x07u);
        }
        fc->have_mask = (uint8_t)(fc->have_mask | (1u << ch));
        fc->complete = fc->have_mask == 0x0Fu;
      }
      break; }
    case HG_CMD_SAFE_HOURS:
      c->safe_bitmap = (uint32_t)p[1] | ((uint32_t)p[2] << 8) | ((uint32_t)p[3] << 16); c->plan_id = p[4];
      for (int i = 0; i < 14; i++) c->tag[i] = (char)p[5 + i];
      c->tag[14] = 0; break;
    default: break;
  }
  return c->op;
}
