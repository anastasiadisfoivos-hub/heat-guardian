/* Heat Guardian 09_guardian 0.9.8: ecosystem layer (events, new commands, day plan, planner, texts). See hg_fw_eco.h,
 * ECOSYSTEM_SPEC.md and HERDAY_SPEC.md. The Greek strings are UTF-8 written as \x escapes (the Greek text is in the comment next to each). */
#include "fw_flags.h"
#include "hg_fw_eco.h"
#include "frozen/hg_frames.h"       /* hg_crc8 (frozen, the STATUS CRC) + HG_CMD_ERR_* */
#include "frozen/hg_guardian.h"     /* HG_SCR_*, HG_WHY_*, HG2_WHY_* */
#include "frozen/hg_homeout.h"      /* HG_HO_HOME / TRANSIT / OUT (read only) */
#include <math.h>
#include <stdio.h>
#include <string.h>

/* ================================================================== events */
void hg_ev_init(hg_evring_t *r) { memset(r, 0, sizeof *r); }

int hg_seq_after(uint16_t a, uint16_t b) { return a != b && (uint16_t)(a - b) < 0x8000u; }

const hg_ev_t *hg_ev_add(hg_evring_t *r, uint32_t unix_s, uint8_t type, uint8_t arg) { return hg_ev_add_x(r, unix_s, type, arg, NULL); }

const hg_ev_t *hg_ev_add_x(hg_evring_t *r, uint32_t unix_s, uint8_t type, uint8_t arg, const uint8_t x[8])
{
  uint16_t s = (uint16_t)(r->last_seq + 1u); if (s == 0) s = 1;
  r->last_seq = s;
  hg_ev_t *e = &r->ev[r->head];
  e->seq = s; e->type = type; e->arg = arg; e->unix_s = unix_s;
  if (x) memcpy(e->x, x, 8); else memset(e->x, 0, 8);
  r->head = (uint8_t)((r->head + 1u) % HG_EV_RING);
  if (r->n < HG_EV_RING) r->n++;
  return e;
}

const hg_ev_t *hg_ev_at(const hg_evring_t *r, uint8_t i)
{
  if (i >= r->n) return NULL;
  return &r->ev[(r->head + HG_EV_RING - r->n + i) % HG_EV_RING];
}

int hg_ev_first_after(const hg_evring_t *r, uint16_t since, uint8_t all)
{
  for (uint8_t i = 0; i < r->n; i++) {
    const hg_ev_t *e = hg_ev_at(r, i);
    if (all || since == 0 || hg_seq_after(e->seq, since)) return i;
  }
  return -1;
}

static void put16(uint8_t *b, uint16_t v) { b[0] = (uint8_t)v; b[1] = (uint8_t)(v >> 8); }
static void put32(uint8_t *b, uint32_t v) { for (int i = 0; i < 4; i++) b[i] = (uint8_t)(v >> (8 * i)); }
static uint16_t get16(const uint8_t *b) { return (uint16_t)(b[0] | (b[1] << 8)); }
static uint32_t get32(const uint8_t *b) { return (uint32_t)b[0] | ((uint32_t)b[1] << 8) | ((uint32_t)b[2] << 16) | ((uint32_t)b[3] << 24); }

void hg_ev_pack(const hg_ev_t *e, uint16_t boot, uint8_t o[20])
{
  memset(o, 0, 20);
  o[0] = HG_EV_FRAME_VER; put16(o + 1, e->seq); put16(o + 3, boot); put32(o + 5, e->unix_s);
  o[9] = e->type; o[10] = e->arg; memcpy(o + 11, e->x, 8);
  o[19] = hg_crc8(o, 19);
}

int hg_ev_unpack(const uint8_t in[20], hg_ev_t *e, uint16_t *boot)
{
  if (in[0] != HG_EV_FRAME_VER) return -1;
  if (hg_crc8(in, 19) != in[19]) return -2;
  e->seq = get16(in + 1); if (boot) *boot = get16(in + 3); e->unix_s = get32(in + 5); e->type = in[9]; e->arg = in[10]; memcpy(e->x, in + 11, 8);
  return 0;
}

const char *hg_ev_name(uint8_t t)
{
  static const char *N[] = { "?", "NUDGE_SHOWN", "NUDGE_DONE", "NUDGE_MISSED", "IM_OK", "HELP", "HELP_CANCEL", "FAMILY_MSG_SHOWN", "WARN_SHOWN", "VISIT", "PLAN_ITEM",
                             "ALERT_HELD", "ALL_CLEAR", "SCORE",   /* 0.9.9 alert quality (hg_fw_alert.h) */
                             "POWER_OFF", "BATT_CRITICAL", "HAPTIC_LOST", "LD_REMIND", "LD_DONE", "LD_WORKED", "LD_ESCALATED", "LD_NOTE" };   /* 0.9.17 */
  return t < sizeof N / sizeof N[0] ? N[t] : "?";
}

/* ================================================================== new commands */
void hg_seed_clear(hg_seed_t *s) { memset(s, 0xFF, sizeof *s); }

uint16_t hg_seed_mod(uint8_t h, uint8_t m) { return (h < 24u && m < 60u) ? (uint16_t)(h * 60u + m) : 0xFFFFu; }

int hg_seed_any(const hg_seed_t *s)
{
  const uint8_t *b = (const uint8_t *)s;
  for (size_t i = 0; i < sizeof *s; i++) if (b[i] != 0xFF) return 1;
  return 0;
}

int hg_utf8_ok(const uint8_t *s, uint16_t n)
{
  for (uint16_t i = 0; i < n;) {
    uint8_t c = s[i];
    if (c < 0x20u || c == 0x7Fu) return 0;
    int k;
    if (c < 0x80u) k = 0;
    else if (c >= 0xC2u && c <= 0xDFu) k = 1;
    else if ((c & 0xF0u) == 0xE0u) k = 2;
    else if (c >= 0xF0u && c <= 0xF4u) k = 3;
    else return 0;                                     /* stray continuation byte, overlong 2-byte lead, > U+10FFFF */
    if ((uint32_t)i + (uint32_t)k >= n && k) return 0; /* truncated sequence */
    for (int j = 1; j <= k; j++) if ((s[i + j] & 0xC0u) != 0x80u) return 0;
    i = (uint16_t)(i + 1 + k);
  }
  return 1;
}

static int pair_ok(uint8_t h, uint8_t m) { return (h == 0xFF && m == 0xFF) || (h < 24u && m < 60u); }

int hg_eco_cmd_parse(const uint8_t *p, uint16_t n, hg_eco_cmd_t *c)
{
  memset(c, 0, sizeof *c);
  if (!p || n < 1) return 0;
  if (p[0] < HG_CMD_SYNC_EVENTS || p[0] > HG_CMD_VISIT) return 0;   /* not ours: the frozen parser's job */
  if (n < 20) return HG_CMD_ERR_SHORT;
  if (hg_crc8(p, 19) != p[19]) return HG_CMD_ERR_CRC;
  c->op = p[0];
  switch (p[0]) {
    case HG_CMD_SYNC_EVENTS: c->since_seq = get16(p + 1); c->boot = get16(p + 3); break;
    case HG_CMD_FAMILY_MSG: c->msg = p[1]; if (c->msg < 1 || c->msg > 3) return HG_CMD_ERR_FIELD; break;
    case HG_CMD_FAMILY_NAME: {
      uint16_t len = 0; while (len < HG_FAMNAME_MAX && p[1 + len]) len++;
      for (uint16_t i = len; i < HG_FAMNAME_MAX; i++) if (p[1 + i]) return HG_CMD_ERR_FIELD;   /* NUL padded */
      if (!hg_utf8_ok(p + 1, len)) return HG_CMD_ERR_FIELD;
      memcpy(c->name, p + 1, len); c->name[len] = 0;
      break; }
    case HG_CMD_ROUTINE_SEED: {
      memcpy(&c->seed, p + 1, 17);
      const uint8_t *b = p + 1;
      for (int i = 0; i < 16; i += 2) if (!pair_ok(b[i], b[i + 1])) return HG_CMD_ERR_FIELD;
      if (b[16] != 0xFF && (b[16] & 0xFEu)) return HG_CMD_ERR_FIELD;
      break; }
    case HG_CMD_ELDER_ACTION:
      c->action = p[1]; c->nudge_id = p[2];
      if (c->action < HG_ACT_HELP || c->action > HG_ACT_IM_OK) return HG_CMD_ERR_FIELD;
      if (c->action == HG_ACT_NUDGE_DONE && (c->nudge_id < 1 || c->nudge_id >= HG_N_COUNT)) return HG_CMD_ERR_FIELD;
      break;
    case HG_CMD_DAY_PLAN: {                          /* HERDAY_SPEC 4 + the as-built rules (ECOSYSTEM_SPEC 5d) */
      const uint8_t day = p[1], idx = p[2], n = p[3], k = p[4];
      c->dp_day = day; c->dp_index = idx; c->dp_n = n;
      if (day > 1 || n > HG_DP_MAX || idx > n) return HG_CMD_ERR_FIELD;
      if (n == 0) break;                             /* index 0, n 0 = clear this day's plan (the item bytes are ignored) */
      if (idx == 0) return HG_CMD_ERR_FIELD;         /* index 0 only with n 0 */
      if (k < HG_DPK_OUTING_SHIFT || k > HG_DPK_HEATWAVE_DAY || p[5] >= HG_PL_N) return HG_CMD_ERR_FIELD;
      if (!pair_ok(p[6], p[7]) || !pair_ok(p[8], p[9])) return HG_CMD_ERR_FIELD;   /* h <= 23, m <= 59, or 0xFF 0xFF */
      if (p[11] > 23 || p[12] > 24) return HG_CMD_ERR_FIELD;                        /* hot to_h is exclusive: 24 = midnight */
      hg_dpi_t *t = &c->dpi; memset(t, 0, sizeof *t); t->kind = k;
      if (k == HG_DPK_OUTING_SHIFT) {
        if (p[8] == 0xFF || (p[10] != HG_DIR_BEFORE && p[10] != HG_DIR_AFTER) || p[11] > p[12]) return HG_CMD_ERR_FIELD;
        t->place = p[5]; t->usual_h = p[6]; t->usual_m = p[7]; t->sugg_h = p[8]; t->sugg_m = p[9]; t->dir = p[10];
        t->hot_from = p[11]; t->hot_to = p[12]; t->peak_c = p[13];
      } else if (k == HG_DPK_AIR_OPEN) {
        if (p[8] == 0xFF) return HG_CMD_ERR_FIELD;
        t->sugg_h = p[8]; t->sugg_m = p[9];
      } else {
        if (p[14] > 31) return HG_CMD_ERR_FIELD;    /* 5 bits in the PLAN_ITEM echo */
        t->hw_day = p[14];
      }
      break; }
    case HG_CMD_VISIT:
      c->v_event = p[1]; c->v_place = p[2]; c->v_unix = get32(p + 3);
      if ((c->v_event != HG_VISIT_ARRIVE && c->v_event != HG_VISIT_LEAVE) || c->v_place >= HG_PL_N) return HG_CMD_ERR_FIELD;
      break;
  }
  return c->op;
}

static void seal(uint8_t o[20]) { o[19] = hg_crc8(o, 19); }
void hg_eco_pack_sync(uint16_t since, uint16_t boot, uint8_t o[20]) { memset(o, 0, 20); o[0] = HG_CMD_SYNC_EVENTS; put16(o + 1, since); put16(o + 3, boot); seal(o); }
void hg_eco_pack_msg(uint8_t msg, uint8_t o[20]) { memset(o, 0, 20); o[0] = HG_CMD_FAMILY_MSG; o[1] = msg; seal(o); }
int hg_eco_pack_name(const char *s, uint8_t o[20])
{
  size_t len = strlen(s);
  if (len > HG_FAMNAME_MAX || !hg_utf8_ok((const uint8_t *)s, (uint16_t)len)) return -1;
  memset(o, 0, 20); o[0] = HG_CMD_FAMILY_NAME; memcpy(o + 1, s, len); seal(o); return 0;
}
void hg_eco_pack_action(uint8_t action, uint8_t nudge_id, uint8_t o[20]) { memset(o, 0, 20); o[0] = HG_CMD_ELDER_ACTION; o[1] = action; o[2] = nudge_id; seal(o); }
void hg_eco_pack_seed(const hg_seed_t *s, uint8_t o[20]) { memset(o, 0, 20); o[0] = HG_CMD_ROUTINE_SEED; memcpy(o + 1, s, 17); seal(o); }
void hg_eco_pack_dayplan(uint8_t day, uint8_t index, uint8_t n, const hg_dpi_t *t, uint8_t o[20])
{
  memset(o, 0, 20); o[0] = HG_CMD_DAY_PLAN; o[1] = day; o[2] = index; o[3] = n;
  if (t) { o[4] = t->kind; o[5] = t->place; o[6] = t->usual_h; o[7] = t->usual_m; o[8] = t->sugg_h; o[9] = t->sugg_m;
           o[10] = t->dir; o[11] = t->hot_from; o[12] = t->hot_to; o[13] = t->peak_c; o[14] = t->hw_day; }
  seal(o);
}
void hg_eco_pack_visit(uint8_t event, uint8_t place, uint32_t unix_s, uint8_t o[20])
{
  memset(o, 0, 20); o[0] = HG_CMD_VISIT; o[1] = event; o[2] = place; put32(o + 3, unix_s); seal(o);
}

/* ================================================================== day plan store (HERDAY_SPEC 4) */
void hg_dp_init(hg_dayplan_t *d) { memset(d, 0, sizeof *d); d->today = -1; }

int hg_dp_roll(hg_dayplan_t *d, int32_t day)
{
  if (day < 0 || d->today == day) return 0;
  if (d->today < 0) { d->today = day; return 1; }              /* plan arrived before the clock: it belongs to this day */
  if (day == d->today + 1) d->day[0] = d->day[1];              /* midnight: tomorrow becomes today */
  else memset(&d->day[0], 0, sizeof d->day[0]);                /* > 1 day later (or the clock went back): stale */
  memset(&d->day[1], 0, sizeof d->day[1]);
  memset(d->stage, 0, sizeof d->stage); d->stage_mask[0] = d->stage_mask[1] = 0;
  d->today = day;
  return 1;
}

int hg_dp_apply(hg_dayplan_t *d, uint8_t day, uint8_t idx, uint8_t n, const hg_dpi_t *t)
{
  if (day > 1 || n > HG_DP_MAX || idx > n) return 0;
  hg_dpday_t *st = &d->stage[day];
  if (n == 0) { memset(&d->day[day], 0, sizeof d->day[day]); memset(st, 0, sizeof *st); d->stage_mask[day] = 0; return 1; }
  if (idx == 0 || !t) return 0;
  const uint8_t bit = (uint8_t)(1u << (idx - 1));
  if (st->n != n || (d->stage_mask[day] & bit)) { memset(st, 0, sizeof *st); st->n = n; d->stage_mask[day] = 0; }   /* a new set */
  st->it[idx - 1] = *t; d->stage_mask[day] |= bit;
  if (d->stage_mask[day] != (uint8_t)((1u << n) - 1u)) return 0;
  d->day[day] = *st;                                           /* atomic: the whole set at once */
  memset(st, 0, sizeof *st); d->stage_mask[day] = 0;
  return 1;
}

static uint16_t dpi_key(const hg_dpi_t *t)
{
  uint16_t u = hg_seed_mod(t->usual_h, t->usual_m);
  return u != 0xFFFF ? u : hg_seed_mod(t->sugg_h, t->sugg_m);
}
int hg_dp_first_outing(const hg_dpday_t *d)
{
  int best = -1;
  if (!d) return -1;
  for (int i = 0; i < d->n && i < HG_DP_MAX; i++)
    if (d->it[i].kind == HG_DPK_OUTING_SHIFT && (best < 0 || dpi_key(&d->it[i]) < dpi_key(&d->it[best]))) best = i;
  return best;
}
int hg_dp_find(const hg_dpday_t *d, uint8_t kind)
{
  if (!d) return -1;
  for (int i = 0; i < d->n && i < HG_DP_MAX; i++) if (d->it[i].kind == kind) return i;
  return -1;
}
int hg_dp_in_hot(const hg_dpday_t *d, uint16_t mod)
{
  if (!d || mod >= 1440u) return 0;
  for (int i = 0; i < d->n && i < HG_DP_MAX; i++) {
    const hg_dpi_t *t = &d->it[i];
    if (t->kind == HG_DPK_OUTING_SHIFT && t->hot_from < t->hot_to && mod >= t->hot_from * 60u && mod < t->hot_to * 60u) return 1;
  }
  return 0;
}
void hg_dp_echo(const hg_dpi_t *t, uint8_t day, uint8_t x[8])
{
  x[0] = t->place; x[1] = t->usual_h; x[2] = t->usual_m; x[3] = t->sugg_h; x[4] = t->sugg_m; x[5] = t->hot_from; x[6] = t->hot_to;
  x[7] = (uint8_t)((day & 1u) | ((t->dir & 3u) << 1) | ((t->hw_day & 31u) << 3));
}
void hg_visit_echo(uint8_t event, uint32_t unix_s, uint8_t x[8]) { memset(x, 0, 8); x[0] = event; put32(x + 1, unix_s); }

static uint32_t crc32_le(const uint8_t *b, uint16_t n)
{
  uint32_t c = 0xFFFFFFFFu;
  for (uint16_t i = 0; i < n; i++) { c ^= b[i]; for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u))); }
  return ~c;
}
#define DP_MAGIC 0x4E414C50u   /* "PLAN" */
void hg_dp_file_pack(const hg_dayplan_t *d, uint8_t o[HG_DP_FILE])
{
  memset(o, 0, HG_DP_FILE);
  put32(o, DP_MAGIC); o[4] = 1; put32(o + 6, (uint32_t)d->today);
  uint8_t *b = o + 10;
  for (int k = 0; k < 2; k++) { *b++ = d->day[k].n; for (int i = 0; i < HG_DP_MAX; i++) { memcpy(b, &d->day[k].it[i], 11); b += 11; } }
  put32(o + HG_DP_FILE - 4, crc32_le(o, HG_DP_FILE - 4));
}
int hg_dp_file_unpack(hg_dayplan_t *d, const uint8_t *in, uint16_t n)
{
  hg_dp_init(d);
  if (!in || n != HG_DP_FILE || get32(in) != DP_MAGIC || in[4] != 1) return -1;
  if (get32(in + HG_DP_FILE - 4) != crc32_le(in, HG_DP_FILE - 4)) return -2;
  hg_dayplan_t t; hg_dp_init(&t);
  t.today = (int32_t)get32(in + 6);
  const uint8_t *b = in + 10;
  for (int k = 0; k < 2; k++) {
    t.day[k].n = *b++;
    if (t.day[k].n > HG_DP_MAX) return -3;
    for (int i = 0; i < HG_DP_MAX; i++) { memcpy(&t.day[k].it[i], b, 11); b += 11; }
    for (int i = 0; i < t.day[k].n; i++) { const hg_dpi_t *q = &t.day[k].it[i];
      if (q->kind < 1 || q->kind > 3 || q->place >= HG_PL_N) return -3; }
  }
  *d = t;
  return 0;
}
static const char *const PLACE_W[HG_PL_N] = {
  "\xce\xad\xce\xbe\xce\xbf\xce\xb4\xce\xbf" /* έξοδο (home: not an outing place) */,
  "\xce\xb1\xce\xb3\xce\xbf\xcf\x81\xce\xac" /* αγορά */,
  "\xce\xb5\xce\xba\xce\xba\xce\xbb\xce\xb7\xcf\x83\xce\xaf\xce\xb1" /* εκκλησία */,
  "\xce\xb2\xcf\x8c\xce\xbb\xcf\x84\xce\xb1" /* βόλτα */,
  "\xcf\x86\xce\xb1\xcf\x81\xce\xbc\xce\xb1\xce\xba\xce\xb5\xce\xaf\xce\xbf" /* φαρμακείο */,
  "\xce\xba\xce\xb1\xcf\x86\xce\xb5\xce\xbd\xce\xb5\xce\xaf\xce\xbf" /* καφενείο */,
  "\xce\xb3\xce\xb9\xce\xb1\xcf\x84\xcf\x81\xcf\x8c" /* γιατρό */,
  "\xce\xad\xce\xbe\xce\xbf\xce\xb4\xce\xbf" /* έξοδο */ };
const char *hg_place_word(uint8_t pl) { return PLACE_W[pl < HG_PL_N ? pl : HG_PL_OTHER]; }

/* ================================================================== planner */
void hg_plan_init(hg_plan_t *p)
{
  memset(p, 0, sizeof *p); p->day = -1; p->last_mod = 0xFFFF; p->n4_last = 0xFFFF; p->brief_hh = 0xFF;
  p->n8_armed = 1; p->prev_ho = 0xFF; p->home_since = -1;
}

static int in_win(uint16_t mod, uint16_t a, uint16_t b)   /* [a, b), wraps midnight; a == b or unknown -> 0 */
{
  if (a >= 1440u || b >= 1440u || a == b) return 0;
  return a < b ? (mod >= a && mod < b) : (mod >= a || mod < b);
}

int hg_plan_quiet(const hg_plan_in_t *in)
{
  const hg_seed_t *s = in->seed;
  uint16_t sb = s ? hg_seed_mod(s->bed_h, s->bed_m) : 0xFFFF, sw = s ? hg_seed_mod(s->wake_h, s->wake_m) : 0xFFFF;
  uint16_t on, off;
  if (in->l_valid && in->l_days >= 3) { on = in->l_sleep_on; off = in->l_sleep_off; }     /* learned >= 3 days wins */
  else if (sb != 0xFFFF && sw != 0xFFFF) { on = sb; off = sw; }                          /* stated routine */
  else if (in->l_valid) { on = in->l_sleep_on; off = in->l_sleep_off; }
  else { on = 22u * 60u; off = 8u * 60u; }                                               /* the routine module's default */
  if (in_win(in->mod, on, off)) return 1;
  if (s && in_win(in->mod, hg_seed_mod(s->nap_fh, s->nap_fm), hg_seed_mod(s->nap_th, s->nap_tm))) return 1;
  return 0;
}

uint16_t hg_plan_wake_ref(const hg_plan_in_t *in)
{
  uint16_t w = 7u * 60u;
  if (in->l_valid && in->l_days >= 3 && in->l_sleep_off < 1440u) w = in->l_sleep_off;
  else if (in->seed && hg_seed_mod(in->seed->wake_h, in->seed->wake_m) != 0xFFFF) w = hg_seed_mod(in->seed->wake_h, in->seed->wake_m);
  if (w > 10u * 60u + 30u) w = 10u * 60u + 30u;     /* the brief is a morning message (auto at w + 90 min, before 12:00) */
  return w;
}

static int fc_tin(const uint8_t *fc, int h) { return (int)(int8_t)fc[3 * h]; }
static int fc_flag(const uint8_t *fc, int h, uint8_t bit) { return (fc[3 * h + 2] & bit) != 0; }

int hg_fc_safe(const hg_plan_in_t *in, int h)
{
  if (h < 0 || h > 23) return 0;
  if (in->have_safe) return (int)((in->safe_bitmap >> h) & 1u);
  return in->fc72 ? fc_flag(in->fc72, h, 4) : 0;
}

int hg_fc_first_safe(const hg_plan_in_t *in, int from_h, int *start, int *end)
{
  for (int h = 0; h < 24; h++) {
    if (!hg_fc_safe(in, h) || (h && hg_fc_safe(in, h - 1))) continue;
    int e = h; while (e < 24 && hg_fc_safe(in, e)) e++;
    if (e > from_h) { *start = h; *end = e; return 1; }
  }
  return 0;
}

static void day_roll(hg_plan_t *p, int32_t day)
{
  if (p->day == day) return;
  p->day = day; p->count = 0; p->shown_mask = 0; p->n4_count = 0; p->last_mod = 0xFFFF; p->n4_last = 0xFFFF; p->brief_hh = 0xFF;
  p->n8_count = 0;                                     /* N8 armed / home state carry over midnight (she may be out) */
}

static void show(hg_plan_t *p, uint8_t id, uint16_t mod)
{
  p->active = id; p->active_left = HG_PLAN_SHOW_MIN; p->count++; p->shown_mask |= (uint16_t)(1u << id);
  p->last_mod = mod; p->shown++;                       /* N8 too: the others keep 60 min after it (N8 itself ignores spacing) */
  if (id == HG_N_WATER) { p->n4_count++; p->n4_last = mod; }
  if (id == HG_N_LEAVE_HOT) p->n8_count++;
}

/* N1: the day's first kind-1 outing (HERDAY 5), else the 0.9.7 safe-window brief */
static void brief_prepare(hg_plan_t *p, const hg_plan_in_t *in)
{
  int s, e, i = hg_dp_first_outing(in->dp_today);
  memset(&p->t1, 0, sizeof p->t1);
  if (i >= 0) { const hg_dpi_t *t = &in->dp_today->it[i]; p->t1.kind = 1; p->t1.place = t->place; p->t1.dir = t->dir; p->t1.h = t->sugg_h; p->t1.m = t->sugg_m; }
  p->brief_hh = hg_fc_first_safe(in, in->mod / 60, &s, &e) ? (uint8_t)e : 0xFF;
}
/* N7: tomorrow's first kind-1 outing, else a heat-wave day; returns 0 when tomorrow has neither */
static int evening_prepare(hg_plan_t *p, const hg_plan_in_t *in)
{
  int i = hg_dp_first_outing(in->dp_tomorrow);
  memset(&p->t7, 0, sizeof p->t7);
  if (i >= 0) { const hg_dpi_t *t = &in->dp_tomorrow->it[i]; p->t7.kind = 1; p->t7.place = t->place; p->t7.dir = t->dir; p->t7.h = t->sugg_h; p->t7.m = t->sugg_m; return 1; }
  i = hg_dp_find(in->dp_tomorrow, HG_DPK_HEATWAVE_DAY);
  if (i >= 0) { p->t7.kind = 3; p->t7.hw = in->dp_tomorrow->it[i].hw_day; return 1; }
  return 0;
}

uint16_t hg_plan_n7_time(const hg_plan_in_t *in)
{
  uint16_t bed = HG_PLAN_N7_DEF_BED;
  uint16_t sb = in->seed ? hg_seed_mod(in->seed->bed_h, in->seed->bed_m) : 0xFFFF;
  if (in->l_valid && in->l_days >= 3 && in->l_sleep_on < 1440u) bed = in->l_sleep_on;   /* learned >= 3 days */
  else if (sb != 0xFFFF) bed = sb;                                                        /* stated 0x19 */
  uint16_t t = (uint16_t)((bed + 1440u - 60u) % 1440u);
  if (t < 18u * 60u) t = t < 12u * 60u ? 23u * 60u : 18u * 60u;   /* a bedtime after 01:00 or before 19:00: keep it an evening */
  return t;
}

/* the AIR time today: kind 2 suggested time, else 21:30 (0.9.7) */
static uint16_t air_time(const hg_plan_in_t *in, int *kind2)
{
  int i = hg_dp_find(in->dp_today, HG_DPK_AIR_OPEN);
  *kind2 = i >= 0;
  return i >= 0 ? hg_seed_mod(in->dp_today->it[i].sugg_h, in->dp_today->it[i].sugg_m) : (uint16_t)(21u * 60u + 30u);
}

/* common gates: clock, warnings, daily cap, spacing, nothing on screen */
static int gates(const hg_plan_t *p, const hg_plan_in_t *in)
{
  if (in->mod >= 1440u || in->day < 0 || in->warning || in->hold || p->active) return 0;   /* 0.9.9: hold = validity gate */
  if (p->count >= HG_PLAN_MAX_DAY) return 0;
  if (p->last_mod != 0xFFFF && in->mod >= p->last_mod && in->mod - p->last_mod < HG_PLAN_SPACING) return 0;
  return 1;
}

static int seen(const hg_plan_t *p, uint8_t id) { return (p->shown_mask >> id) & 1u; }

int hg_plan_hot_now(const hg_plan_in_t *in)
{
  if (in->mod >= 1440u) return 0;
  const int h = in->mod / 60;
  if (hg_dp_in_hot(in->dp_today, in->mod)) return 1;                   /* a kind-1 hot window of today's plan */
  const int heat_day = (in->fc72 && fc_flag(in->fc72, h, 1)) || hg_dp_find(in->dp_today, HG_DPK_HEATWAVE_DAY) >= 0;
  const int have_safe_info = in->have_safe || in->fc72;                /* "non-safe" needs a SAFE_HOURS bitmap or a forecast */
  return heat_day && have_safe_info && !hg_fc_safe(in, h);
}

static int room_hot(const hg_plan_in_t *in, float lim) { return in->room_c == in->room_c && in->room_c >= lim; }

static uint8_t pick(hg_plan_t *p, const hg_plan_in_t *in)
{
  const uint8_t *fc = in->fc72;
  const uint16_t mod = in->mod; const int h = mod / 60;
  const int heat_day = fc && fc_flag(fc, h, 1), night_heat = fc && fc_flag(fc, h, 2);
  const int outing_today = hg_dp_first_outing(in->dp_today) >= 0;
  /* N5 AIR today: at the kind-2 suggested time (HERDAY 5), else 21:30 on a night-heat day / room >= 27 C (0.9.7) */
  int k2; const uint16_t ta = air_time(in, &k2);
  const int air_due = !seen(p, HG_N_AIR) && ta < 1440u && (k2 || fc);
  const uint16_t ta_end = (uint16_t)(ta + 45u);
  /* N7 due tonight: tomorrow's plan has a kind-1 or kind-3 item */
  const uint16_t t7 = hg_plan_n7_time(in);
  hg_plan_in_t atA = *in; atA.mod = ta; hg_plan_in_t at7 = *in; at7.mod = t7;
  const int n7_due = !seen(p, HG_N_EVENING) && (hg_dp_first_outing(in->dp_tomorrow) >= 0 || hg_dp_find(in->dp_tomorrow, HG_DPK_HEATWAVE_DAY) >= 0);
  /* the last daily slots are kept for the evening ones still due (N5 AIR, N7 EVENING_BRIEF): else four WATERs starve them */
  const int air_res = air_due && (k2 || night_heat) && mod < ta_end && !hg_plan_quiet(&atA);
  const int n7_res = n7_due && mod < t7 + 60u && !hg_plan_quiet(&at7);
  const int only_reserved = (air_res + n7_res) && p->count >= HG_PLAN_MAX_DAY - (air_res + n7_res);
  /* N1 BRIEF: first press after her wake time, or wake time + 90 min (default 07:00 / 08:30), before 12:00, on a heat-day
   * or a day whose plan has a kind-1 outing (0.9.8: then «Σήμερα: {place} πριν/μετά τις HH:MM») */
  uint16_t w = hg_plan_wake_ref(in);
  if (in->herday_only) {                               /* 0.9.17: Her Day timing advice only */
    if (outing_today && !seen(p, HG_N_BRIEF) && mod < 12u * 60u && ((in->press && mod >= w) || mod >= w + 90u)) { brief_prepare(p, in); return HG_N_BRIEF; }
    if (n7_due && mod >= t7 && mod < t7 + 60u && evening_prepare(p, in)) return HG_N_EVENING;
    return 0;
  }
  if (!only_reserved && (heat_day || outing_today) && !seen(p, HG_N_BRIEF) && mod < 12u * 60u && ((in->press && mod >= w) || mod >= w + 90u)) { brief_prepare(p, in); return HG_N_BRIEF; }
  /* N2 LAST_COOL: 30 min before the morning safe window ends (window starting before 12:00), heat-day. Skipped when her
   * stated out window lies inside that safe window (she already goes out in the cool: 5b alignment). */
  if (!only_reserved && heat_day && !seen(p, HG_N_LAST_COOL)) {
    int s, e;
    if (hg_fc_first_safe(in, h, &s, &e) && s < 12 && e < 24) {
      uint16_t t = (uint16_t)(e * 60 - 30), te = (uint16_t)(e * 60 - 5);
      int inside = 0;
      if (in->seed) {
        const hg_seed_t *sd = in->seed;
        uint16_t f1 = hg_seed_mod(sd->o1_fh, sd->o1_fm), t1 = hg_seed_mod(sd->o1_th, sd->o1_tm);
        uint16_t f2 = hg_seed_mod(sd->o2_fh, sd->o2_fm), t2 = hg_seed_mod(sd->o2_th, sd->o2_tm);
        inside = (f1 != 0xFFFF && t1 != 0xFFFF && f1 >= s * 60 && t1 <= e * 60 && f1 < t1) ||
                 (f2 != 0xFFFF && t2 != 0xFFFF && f2 >= s * 60 && t2 <= e * 60 && f2 < t2);
      }
      if (!inside && mod >= t && mod < te) return HG_N_LAST_COOL;
    }
  }
  /* (N3 SHUTTERS removed in 0.9.8: a habit she already has) */
  /* N6 AC (5b): A/C at home stated, hot hour (forecast or room) -> «Ανάψτε το κλιματιστικό», once a day */
  if (!only_reserved && fc && !seen(p, HG_N_AC) && in->seed && in->seed->flags != 0xFF && (in->seed->flags & 1u) &&
      (fc_tin(fc, h) >= HG_PLAN_HOT_C || room_hot(in, HG_PLAN_HOT_C))) return HG_N_AC;
  /* N5 AIR: kind 2 -> [sugg, sugg + 45 min); else 21:30-22:15 on a night-heat day, or room >= 27 C then */
  if (air_due && mod >= ta && mod < ta_end && (k2 || night_heat || room_hot(in, HG_PLAN_AIR_ROOM_C))) return HG_N_AIR;
  /* N7 EVENING_BRIEF: [bedtime - 60, bedtime), once a day, only if tomorrow's plan has a kind-1 or kind-3 item.
   * AIR wins: no N7 while an AIR still due tonight would then be blocked by the 60-min spacing. */
  if (n7_due) {
    const int air_blocks = air_due && (k2 || night_heat) && mod < ta && mod + HG_PLAN_SPACING > ta && !hg_plan_quiet(&atA);
    if (mod >= t7 && mod < t7 + 60u && !air_blocks && evening_prepare(p, in)) return HG_N_EVENING;
  }
  /* N4 WATER: hot hour (forecast T_in or room >= 28 C), every 90 min, max 4 a day. Without a forecast: room only. */
  if (!only_reserved && p->n4_count < HG_PLAN_N4_MAX && ((fc && fc_tin(fc, h) >= HG_PLAN_HOT_C) || room_hot(in, HG_PLAN_HOT_C)) &&
      (p->n4_last == 0xFFFF || (mod >= p->n4_last && mod - p->n4_last >= HG_PLAN_N4_EVERY))) return HG_N_WATER;
  return 0;
}

/* ---- N8 LEAVE_HOT (HERDAY 5): leave = HOME -> TRANSIT/OUT of the frozen home/out state, or a fresh VISIT LEAVE from home.
 * Once per outing (re-armed after >= 30 min back HOME, band state or a VISIT ARRIVE home), max 2 a day, counts toward the
 * 6, exempt from the 60-min spacing, never over a warning or in the sleep window; eligible for 10 min after the leave. */
static int32_t abs_min(const hg_plan_in_t *in) { return in->day * 1440 + (int32_t)in->mod; }
static void n8_leave(hg_plan_t *p)
{
  if (p->n8_armed) { p->n8_armed = 0; p->n8_pending = HG_PLAN_N8_WAIT; }
  p->home_since = -1; p->visit_home = 0;
}
static void ho_track(hg_plan_t *p, const hg_plan_in_t *in)
{
  const uint8_t ho = in->home_out;
  if (ho <= HG_HO_OUT) {
    if (p->prev_ho == HG_HO_HOME && ho != HG_HO_HOME) n8_leave(p);
    p->prev_ho = ho;
  }
  if (ho == HG_HO_HOME || p->visit_home) {
    if (p->home_since < 0) p->home_since = abs_min(in);
    if (!p->n8_armed && abs_min(in) - p->home_since >= HG_PLAN_N8_REARM) p->n8_armed = 1;
  } else p->home_since = -1;
}
static void n8_try(hg_plan_t *p, const hg_plan_in_t *in, hg_plan_out_t *out, int tick)
{
  if (!p->n8_pending) return;
  if (!in->warning && !in->hold && p->active != HG_N_LEAVE_HOT && p->n8_count < HG_PLAN_N8_MAX && p->count < HG_PLAN_MAX_DAY &&
      !hg_plan_quiet(in) && hg_plan_hot_now(in)) {
    if (p->active) { out->missed = p->active; p->active = 0; p->missed++; }   /* it replaces a lower nudge (MISSED) */
    show(p, HG_N_LEAVE_HOT, in->mod); out->show = HG_N_LEAVE_HOT; p->n8_pending = 0;
    return;
  }
  if (tick) p->n8_pending--;
}

void hg_plan_minute(hg_plan_t *p, const hg_plan_in_t *in, hg_plan_out_t *out)
{
  out->show = 0; out->missed = 0;
  if (p->active) {                                      /* MISSED: replaced by a warning, or 10 min without a press */
    if (in->warning || p->active_left <= 1) { out->missed = p->active; p->active = 0; p->missed++; }
    else p->active_left--;
  }
  if (in->mod >= 1440u || in->day < 0) return;
  day_roll(p, in->day);
  if (in->ext_nudge) p->last_mod = in->mod;            /* the frozen bedtime nudge counts for the spacing */
  ho_track(p, in);                                     /* 0.9.8 N8: leave detection + re-arm */
  { hg_plan_out_t o8 = { 0, 0 }; n8_try(p, in, &o8, 1);
    if (o8.show) { out->show = o8.show; if (o8.missed) out->missed = o8.missed; return; } }
  if (!gates(p, in) || hg_plan_quiet(in)) return;
  hg_plan_in_t i2 = *in; i2.press = 0;
  uint8_t id = pick(p, &i2);
  if (id) { show(p, id, in->mod); out->show = id; }
}

uint8_t hg_plan_press(hg_plan_t *p, const hg_plan_in_t *in)
{
  if (in->mod >= 1440u || in->day < 0) return 0;
  day_roll(p, in->day);
  if (!gates(p, in)) return 0;                          /* the press itself proves she is awake: no sleep-window gate */
  const uint8_t *fc = in->fc72; const int h = in->mod / 60;
  if (!((!in->herday_only && fc && fc_flag(fc, h, 1)) || hg_dp_first_outing(in->dp_today) >= 0) || seen(p, HG_N_BRIEF) || in->mod >= 12u * 60u ||
      in->mod < hg_plan_wake_ref(in)) return 0;
  brief_prepare(p, in);
  show(p, HG_N_BRIEF, in->mod);
  return HG_N_BRIEF;
}

uint8_t hg_plan_done(hg_plan_t *p, uint16_t mod)
{
  uint8_t id = p->active;
  if (!id) return 0;
  p->active = 0; p->done++;
  if (id == HG_N_WATER && mod < 1440u) p->n4_last = mod;   /* a WATER DONE restarts the 90-min timer */
  return id;
}

uint8_t hg_plan_cancel(hg_plan_t *p) { uint8_t id = p->active; if (id) { p->active = 0; p->missed++; } return id; }

uint8_t hg_plan_force(hg_plan_t *p, uint8_t id, const hg_plan_in_t *in)
{
  if (id < 1 || id >= HG_N_COUNT || id == HG_N_SHUTTERS) return 0;
  if (in->day >= 0) day_roll(p, in->day);
  if (id == HG_N_EVENING) { hg_ptxt_t keep = p->t7; if (!evening_prepare(p, in)) { p->t7 = keep; return 0; } }   /* no tomorrow plan: no text */
  if (p->active) hg_plan_cancel(p);
  if (id == HG_N_BRIEF) brief_prepare(p, in);
  show(p, id, in->mod < 1440u ? in->mod : 0);
  return id;
}

void hg_plan_visit(hg_plan_t *p, const hg_plan_in_t *in, uint8_t event, uint8_t place, uint8_t fresh, hg_plan_out_t *out)
{
  out->show = 0; out->missed = 0;
  if (event == HG_VISIT_ARRIVE) {
    p->visit_home = place == HG_PL_HOME;
    if (p->visit_home && p->home_since < 0 && in->mod < 1440u && in->day >= 0) p->home_since = abs_min(in);
  } else if (event == HG_VISIT_LEAVE) {
    if (place == HG_PL_HOME && fresh) n8_leave(p);  /* a late (queued) leave is history, not "she is leaving now" */
    p->visit_home = 0;
  }
  if (in->mod >= 1440u || in->day < 0) return;
  day_roll(p, in->day);
  n8_try(p, in, out, 0);
}

void hg_plan_homeout(hg_plan_t *p, const hg_plan_in_t *in, hg_plan_out_t *out)
{
  out->show = 0; out->missed = 0;
  if (in->mod >= 1440u || in->day < 0) return;
  day_roll(p, in->day);
  ho_track(p, in);
  n8_try(p, in, out, 0);
}

/* ================================================================== texts */
const char HG_TXT_BRAVO[]  = "\xce\x9c\xcf\x80\xcf\x81\xce\xac\xce\xb2\xce\xbf \xe2\x9c\x93" /* Μπράβο ✓ */;
const char HG_TXT_FAMACK[] = "\xce\x97 \xce\xbf\xce\xb9\xce\xba\xce\xbf\xce\xb3\xce\xad\xce\xbd\xce\xb5\xce\xb9\xce\xb1 \xce\xb5\xce\xb9\xce\xb4\xce\xbf\xcf\x80\xce\xbf\xce\xb9\xce\xae\xce\xb8\xce\xb7\xce\xba\xce\xb5 \xe2\x9c\x93" /* Η οικογένεια ειδοποιήθηκε ✓ */;
const char HG_TXT_FAMDEF[] = "\xce\xbf\xce\xb9\xce\xba\xce\xbf\xce\xb3\xce\xad\xce\xbd\xce\xb5\xce\xb9\xce\xb1" /* οικογένεια */;
const char HG_TXT_COOL_PM[] = "\xce\x94\xcf\x81\xce\xbf\xcf\x83\xce\xb5\xcf\x81\xcf\x8c \xce\xb1\xcf\x80\xcf\x8c\xce\xb3\xce\xb5\xcf\x85\xce\xbc\xce\xb1" /* Δροσερό απόγευμα */;

const char *hg_nudge_text(const hg_plan_t *p, uint8_t id, char *b, uint16_t n)
{
  switch (id) {
    case HG_N_BRIEF:
      if (p->t1.kind == 1)
        snprintf(b, n, p->t1.dir == HG_DIR_AFTER ? "\xce\xa3\xce\xae\xce\xbc\xce\xb5\xcf\x81\xce\xb1: %s \xce\xbc\xce\xb5\xcf\x84\xce\xac \xcf\x84\xce\xb9\xcf\x82 %02u:%02u" /* Σήμερα: %s μετά τις %02u:%02u */
                                                 : "\xce\xa3\xce\xae\xce\xbc\xce\xb5\xcf\x81\xce\xb1: %s \xcf\x80\xcf\x81\xce\xb9\xce\xbd \xcf\x84\xce\xb9\xcf\x82 %02u:%02u" /* Σήμερα: %s πριν τις %02u:%02u */,
                 hg_place_word(p->t1.place), (unsigned)p->t1.h, (unsigned)p->t1.m);
      else if (p->brief_hh != 0xFF) snprintf(b, n, "\xce\xa3\xce\xae\xce\xbc\xce\xb5\xcf\x81\xce\xb1 \xce\xb6\xce\xad\xcf\x83\xcf\x84\xce\xb7. \xce\x92\xce\xb3\xce\xb5\xce\xaf\xcf\x84\xce\xb5 \xcf\x80\xcf\x81\xce\xb9\xce\xbd \xcf\x84\xce\xb9\xcf\x82 %02u:00" /* Σήμερα ζέστη. Βγείτε πριν τις %02u:00 */, (unsigned)p->brief_hh);
      else snprintf(b, n, "%s", "\xce\xa3\xce\xae\xce\xbc\xce\xb5\xcf\x81\xce\xb1 \xce\xb6\xce\xad\xcf\x83\xcf\x84\xce\xb7. \xce\x9c\xce\xb5\xce\xaf\xce\xbd\xce\xb5\xcf\x84\xce\xb5 \xce\xbc\xce\xad\xcf\x83\xce\xb1" /* Σήμερα ζέστη. Μείνετε μέσα */);
      return b;
    case HG_N_LAST_COOL: return "\xce\xa4\xce\xb5\xce\xbb\xce\xb5\xcf\x85\xcf\x84\xce\xb1\xce\xaf\xce\xb1 \xce\xb4\xcf\x81\xce\xbf\xcf\x83\xce\xb5\xcf\x81\xce\xae \xcf\x8e\xcf\x81\xce\xb1 \xce\xb3\xce\xb9\xce\xb1 \xce\xad\xce\xbe\xce\xbf\xce\xb4\xce\xbf" /* Τελευταία δροσερή ώρα για έξοδο */;
    case HG_N_WATER:     return "\xce\x8f\xcf\x81\xce\xb1 \xce\xb3\xce\xb9\xce\xb1 \xce\xad\xce\xbd\xce\xb1 \xcf\x80\xce\xbf\xcf\x84\xce\xae\xcf\x81\xce\xb9 \xce\xbd\xce\xb5\xcf\x81\xcf\x8c" /* Ώρα για ένα ποτήρι νερό */;
    case HG_N_AIR:       return "\xce\x91\xce\xbd\xce\xbf\xce\xaf\xce\xbe\xcf\x84\xce\xb5 \xcf\x84\xce\xb1 \xcf\x80\xce\xb1\xcf\x81\xce\xac\xce\xb8\xcf\x85\xcf\x81\xce\xb1 \xce\xbd\xce\xb1 \xce\xb4\xcf\x81\xce\xbf\xcf\x83\xce\xaf\xcf\x83\xce\xb5\xce\xb9" /* Ανοίξτε τα παράθυρα να δροσίσει */;
    case HG_N_AC:        return "\xce\x91\xce\xbd\xce\xac\xcf\x88\xcf\x84\xce\xb5 \xcf\x84\xce\xbf \xce\xba\xce\xbb\xce\xb9\xce\xbc\xce\xb1\xcf\x84\xce\xb9\xcf\x83\xcf\x84\xce\xb9\xce\xba\xcf\x8c" /* Ανάψτε το κλιματιστικό */;
    case HG_N_EVENING:
      if (p->t7.kind == 1)
        snprintf(b, n, p->t7.dir == HG_DIR_AFTER ? "\xce\x91\xcf\x8d\xcf\x81\xce\xb9\xce\xbf: %s \xce\xbc\xce\xb5\xcf\x84\xce\xac \xcf\x84\xce\xb9\xcf\x82 %02u:%02u" /* Αύριο: %s μετά τις %02u:%02u */
                                                 : "\xce\x91\xcf\x8d\xcf\x81\xce\xb9\xce\xbf: %s \xcf\x80\xcf\x81\xce\xb9\xce\xbd \xcf\x84\xce\xb9\xcf\x82 %02u:%02u" /* Αύριο: %s πριν τις %02u:%02u */,
                 hg_place_word(p->t7.place), (unsigned)p->t7.h, (unsigned)p->t7.m);
      else if (p->t7.kind == 3) snprintf(b, n, "\xce\x91\xcf\x8d\xcf\x81\xce\xb9\xce\xbf: \xce\xba\xce\xb1\xcf\x8d\xcf\x83\xcf\x89\xce\xbd\xce\xb1\xcf\x82, \xce\xbc\xce\xad\xcf\x81\xce\xb1 %u" /* Αύριο: καύσωνας, μέρα %u */, (unsigned)p->t7.hw);
      else b[0] = 0;
      return b;
    case HG_N_LEAVE_HOT: return "\xce\x88\xce\xbe\xcf\x89 \xce\xba\xce\xac\xce\xbd\xce\xb5\xce\xb9 \xce\xb6\xce\xad\xcf\x83\xcf\x84\xce\xb7. \xce\xa0\xce\xac\xcf\x81\xcf\x84\xce\xb5 \xce\xbd\xce\xb5\xcf\x81\xcf\x8c." /* Έξω κάνει ζέστη. Πάρτε νερό. */;
    default:             return "";
  }
}

const char *hg_reason_text(uint8_t why, uint8_t scr, float room_c, char *b, uint16_t n)
{
  b[0] = 0;
  if (scr != HG_SCR_DRINK && scr != HG_SCR_COOL && scr != HG_SCR_CHECK && scr != HG_SCR_DANGER) return b;
  if (why & (HG2_WHY_BODY | HG2_WHY_NN | HG2_WHY_DANGER_P)) snprintf(b, n, "%s", "\xce\xa4\xce\xbf \xcf\x83\xcf\x8e\xce\xbc\xce\xb1 \xce\xb6\xce\xb5\xcf\x83\xcf\x84\xce\xb1\xce\xaf\xce\xbd\xce\xb5\xcf\x84\xce\xb1\xce\xb9" /* Το σώμα ζεσταίνεται */);
  else if (why & HG2_WHY_ENV_LIMIT) {
    if (room_c == room_c && room_c > -50.0f && room_c < 80.0f) snprintf(b, n, "\xce\xa0\xce\xbf\xce\xbb\xce\xbb\xce\xae \xce\xb6\xce\xad\xcf\x83\xcf\x84\xce\xb7 \xcf\x83\xcf\x84\xce\xbf \xcf\x83\xcf\x80\xce\xaf\xcf\x84\xce\xb9 %d\xc2\xb0" /* Πολλή ζέστη στο σπίτι %d° */, (int)floorf(room_c + 0.5f));
    else snprintf(b, n, "%s", "\xce\xa0\xce\xbf\xce\xbb\xce\xbb\xce\xae \xce\xb6\xce\xad\xcf\x83\xcf\x84\xce\xb7 \xcf\x83\xcf\x84\xce\xbf \xcf\x83\xcf\x80\xce\xaf\xcf\x84\xce\xb9" /* Πολλή ζέστη στο σπίτι */);
  }
  else if (why & HG2_WHY_TIME_IN_HEAT) snprintf(b, n, "%s", "\xce\xa0\xce\xbf\xce\xbb\xce\xbb\xce\xad\xcf\x82 \xcf\x8e\xcf\x81\xce\xb5\xcf\x82 \xcf\x83\xcf\x84\xce\xb7 \xce\xb6\xce\xad\xcf\x83\xcf\x84\xce\xb7" /* Πολλές ώρες στη ζέστη */);
  else if (why & HG_WHY_NO_RESPONSE_G) snprintf(b, n, "%s", "\xce\x94\xce\xb5\xce\xbd \xce\xb1\xcf\x80\xce\xb1\xce\xbd\xcf\x84\xce\xae\xcf\x83\xce\xb1\xcf\x84\xce\xb5" /* Δεν απαντήσατε */);
  return b;
}

const char *hg_family_text(uint8_t msg, const char *name, char *b, uint16_t n)
{
  const char *who = (name && name[0]) ? name : HG_TXT_FAMDEF;
  switch (msg) {
    case 1: snprintf(b, n, "%s: \xcf\x83\xce\xb1\xcf\x82 \xce\xba\xce\xb1\xce\xbb\xce\xb5\xce\xaf" /* %s: σας καλεί */, who); break;
    case 2: snprintf(b, n, "%s: \xce\xad\xcf\x81\xcf\x87\xce\xb5\xcf\x84\xce\xb1\xce\xb9" /* %s: έρχεται */, who); break;
    case 3: snprintf(b, n, "%s: \xce\xb5\xce\xaf\xce\xb4\xce\xb5 \xcf\x84\xce\xbf \xce\xbc\xce\xae\xce\xbd\xcf\x85\xce\xbc\xce\xb1 \xe2\x9c\x93" /* %s: είδε το μήνυμα ✓ */, who); break;
    default: b[0] = 0;
  }
  return b;
}

const char *hg_next_hours_text(const uint8_t *fc, uint16_t mod, char *b, uint16_t n)
{
  b[0] = 0;
  if (!fc || mod >= 1440u) return b;
  int h0 = mod / 60;
  for (int h = h0; h < 24; h++) if (fc_tin(fc, h) >= HG_PLAN_VERY_HOT_C) { snprintf(b, n, "\xce\x91\xcf\x80\xcf\x8c %02d:00 \xcf\x80\xce\xbf\xce\xbb\xce\xbb\xce\xae \xce\xb6\xce\xad\xcf\x83\xcf\x84\xce\xb7" /* Από %02d:00 πολλή ζέστη */, h); return b; }
  if (h0 < 18) {                                         /* no very hot hour left: a cool afternoon if 12-19 stays < 28 C */
    int mx = -128; for (int h = h0 > 12 ? h0 : 12; h < 20; h++) if (fc_tin(fc, h) > mx) mx = fc_tin(fc, h);
    if (mx < HG_PLAN_HOT_C) snprintf(b, n, "%s", HG_TXT_COOL_PM);
  }
  return b;
}

void hg_local_date(int32_t z, int *y, int *mon, int *mday, int *wday)
{
  *wday = (int)((z % 7 + 7 + 4) % 7);                  /* 1970-01-01 was a Thursday (0 = Sunday) */
  z += 719468;                                         /* H. Hinnant, civil_from_days */
  int32_t era = (z >= 0 ? z : z - 146096) / 146097;
  uint32_t doe = (uint32_t)(z - era * 146097);
  uint32_t yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
  int32_t yy = (int32_t)yoe + era * 400;
  uint32_t doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
  uint32_t mp = (5 * doy + 2) / 153;
  *mday = (int)(doy - (153 * mp + 2) / 5 + 1);
  *mon = (int)(mp < 10 ? mp + 3 : mp - 9);
  *y = (int)(yy + (*mon <= 2));
}

const char *hg_date_text(int32_t day, char *b, uint16_t n)
{
  static const char *const WD[7] = { "\xce\x9a\xcf\x85\xcf\x81" /* Κυρ */, "\xce\x94\xce\xb5\xcf\x85" /* Δευ */, "\xce\xa4\xcf\x81\xce\xb9" /* Τρι */, "\xce\xa4\xce\xb5\xcf\x84" /* Τετ */, "\xce\xa0\xce\xb5\xce\xbc" /* Πεμ */, "\xce\xa0\xce\xb1\xcf\x81" /* Παρ */, "\xce\xa3\xce\xb1\xce\xb2" /* Σαβ */ };
  static const char *const MO[12] = { "\xce\x99\xce\xb1\xce\xbd" /* Ιαν */, "\xce\xa6\xce\xb5\xce\xb2" /* Φεβ */, "\xce\x9c\xce\xb1\xcf\x81" /* Μαρ */, "\xce\x91\xcf\x80\xcf\x81" /* Απρ */, "\xce\x9c\xce\xb1\xce\x90" /* Μαΐ */, "\xce\x99\xce\xbf\xcf\x85\xce\xbd" /* Ιουν */, "\xce\x99\xce\xbf\xcf\x85\xce\xbb" /* Ιουλ */,
                                      "\xce\x91\xcf\x85\xce\xb3" /* Αυγ */, "\xce\xa3\xce\xb5\xcf\x80" /* Σεπ */, "\xce\x9f\xce\xba\xcf\x84" /* Οκτ */, "\xce\x9d\xce\xbf\xce\xb5" /* Νοε */, "\xce\x94\xce\xb5\xce\xba" /* Δεκ */ };
  b[0] = 0;
  if (day < 0) return b;
  int y, m, d, w; hg_local_date(day, &y, &m, &d, &w);
  snprintf(b, n, "%s %d %s", WD[w], d, MO[m - 1]);
  return b;
}

void hg_trend_init(hg_trend_t *t) { for (int i = 0; i < 31; i++) t->c100[i] = INT16_MIN; t->i = 0; t->n = 0; }
void hg_trend_push(hg_trend_t *t, float c)
{
  t->c100[t->i] = (c == c && c > -50.0f && c < 80.0f) ? (int16_t)floorf(c * 100.0f + 0.5f) : INT16_MIN;
  t->i = (uint8_t)((t->i + 1u) % 31u); if (t->n < 31) t->n++;
}
int hg_trend_dir(const hg_trend_t *t)
{
  if (t->n < 31) return -2;
  int16_t now = t->c100[(t->i + 30u) % 31u], old = t->c100[t->i];   /* newest, and the one 30 min before it */
  if (now == INT16_MIN || old == INT16_MIN) return -2;
  int d = now - old;
  return d >= 50 ? 1 : (d <= -50 ? -1 : 0);
}
