#include "hg_nofastmath.h"   /* FIRST: the core builds with -Ofast; NaN must stay NaN */
/* Heat Guardian 09_guardian 0.9.10 FS-HEAL decisions. See hg_fw_heal.h. */
#include "hg_fw_heal.h"
#include <string.h>
#include <stdio.h>

static const char *const FID_NAME[HG_FID_COUNT] = {
  "none", "events", "sfile", "boot", "raw", "ring", "mount", "heal", "dump", "list", "format", "other", "ifs_heal", "ifs_twin", "ifs_profile", "ifs_eco"
};
const char *hg_heal_fid_name(uint8_t fid) { return fid < HG_FID_COUNT ? FID_NAME[fid] : "?"; }
const char *hg_heal_cause_name(uint8_t cause)
{
  return cause == HG_CAUSE_DEADLINE ? "DEADLINE" : cause == HG_CAUSE_ASSERT ? "ASSERT" : "none";
}

int hg_heal_fid_is_ifs(uint8_t fid) { return fid >= HG_FID_IFS_HEAL && fid <= HG_FID_IFS_ECO; }
const char *hg_heal_ifs_files(uint8_t fid)
{
  switch (fid) {
    case HG_FID_IFS_HEAL: return "/fsheal.bin";
    case HG_FID_IFS_TWIN: return "/twin.bin";
    case HG_FID_IFS_PROFILE: return "/profile.bin";
    case HG_FID_IFS_ECO: return "/famname.bin+/routine.bin+/dayplan.bin";
    default: return "";
  }
}
int hg_heal_ifs_plan(uint8_t fid, uint8_t count, uint8_t prev_fid, const char **paths, int max_paths)
{
  int n = 0;
  for (int i = 0; i < max_paths; i++) paths[i] = NULL;
  if (!hg_heal_fid_is_ifs(fid) || count == 0) return HG_IFS_NONE;
  if (count >= 3) return HG_IFS_OFF;
  if (count == 2 || prev_fid == fid) return HG_IFS_FORMAT;   /* the same file twice: never a second reset for it */
  if (fid == HG_FID_IFS_HEAL) return HG_IFS_FORMAT;   /* 0.9.13: InternalFS itself (mount / format / the old /fsheal.bin): format at once */
  static const char *const ECO[3] = { "/famname.bin", "/routine.bin", "/dayplan.bin" };
  if (fid == HG_FID_IFS_ECO) { for (int i = 0; i < 3 && n < max_paths; i++) paths[n++] = ECO[i]; }
  else if (n < max_paths) paths[n++] = fid == HG_FID_IFS_HEAL ? "/fsheal.bin" : fid == HG_FID_IFS_TWIN ? "/twin.bin" : "/profile.bin";
  return HG_IFS_REMOVE;
}

int hg_heal_deadline_hit(uint32_t total_ms, uint32_t since_io_ms)
{
  return since_io_ms > HG_FS_DEADLINE_MS || total_ms > HG_FS_TOTAL_MS;
}
uint8_t hg_heal_next_count(uint8_t prev_count, uint8_t prev_fid, uint8_t fid)
{
  if (!prev_count || hg_heal_fid_is_ifs(prev_fid) != hg_heal_fid_is_ifs(fid)) return 1;
  return prev_count >= 3 ? 3 : (uint8_t)(prev_count + 1);
}

uint8_t hg_heal_marker_encode(uint8_t cause, uint8_t fid, uint8_t count, uint8_t ifs_bad)
{
  if (count < 1) count = 1;
  if (count > 3) count = 3;
  return (uint8_t)((cause == HG_CAUSE_ASSERT ? 0x80u : 0u) | (ifs_bad ? 0x40u : 0u) | (uint8_t)(count << 4) | (fid & 0x0Fu));
}
int hg_heal_marker_decode(uint8_t reg, uint8_t *cause, uint8_t *fid, uint8_t *count, uint8_t *ifs_bad)
{
  uint8_t c = (reg >> 4) & 3u, f = reg & 0x0Fu;
  int ok = c != 0 && f < HG_FID_COUNT;
  if (cause) *cause = ok ? ((reg & 0x80u) ? HG_CAUSE_ASSERT : HG_CAUSE_DEADLINE) : HG_CAUSE_NONE;
  if (fid) *fid = ok ? f : HG_FID_NONE;
  if (count) *count = ok ? c : 0;
  if (ifs_bad) *ifs_bad = ok ? ((reg & 0x40u) ? 1 : 0) : 0;
  return ok;
}

uint32_t hg_heal_crc32(const void *p, size_t n)
{
  const uint8_t *b = (const uint8_t *)p; uint32_t c = ~0u;
  while (n--) { c ^= *b++; for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u))); }
  return ~c;
}
void hg_heal_state_init(hg_heal_state_t *s)
{
  memset(s, 0, sizeof *s);
  s->magic = HG_HEAL_MAGIC; s->ver = HG_HEAL_VER;
  hg_heal_state_seal(s);
}
void hg_heal_state_seal(hg_heal_state_t *s) { s->crc = hg_heal_crc32(s, offsetof(hg_heal_state_t, crc)); }
int hg_heal_state_valid(const hg_heal_state_t *s)
{
  return s->magic == HG_HEAL_MAGIC && s->ver == HG_HEAL_VER && s->crc == hg_heal_crc32(s, offsetof(hg_heal_state_t, crc));
}

void hg_heal_events_path(uint16_t gen, char *out, size_t n) { snprintf(out, n, "/log/events_%u.txt", (unsigned)gen); }
uint16_t hg_heal_events_gen(const char *name)
{
  if (!name || strncmp(name, "events_", 7) != 0) return 0;
  const char *p = name + 7; uint32_t g = 0; int digits = 0;
  while (*p >= '0' && *p <= '9' && digits < 6) { g = g * 10u + (uint32_t)(*p - '0'); p++; digits++; }
  if (!digits || strcmp(p, ".txt") != 0 || g == 0 || g > 65535u) return 0;
  return (uint16_t)g;
}
int hg_heal_is_legacy_events(const char *name)
{
  return name && (strcmp(name, "events.txt") == 0 || strcmp(name, "events2.txt") == 0);
}

static uint16_t next_gen(uint16_t g) { return g >= 65535u ? 1u : (uint16_t)(g + 1u); }
static void pcopy(char *dst, const char *src)
{
  size_t n = 0;
  if (src) while (n < HG_HEAL_PATH - 1 && src[n]) n++;
  if (n) memmove(dst, src, n);
  dst[n] = 0;
}
int hg_heal_is_quarantined(const hg_heal_state_t *s, const char *path)
{
  if (!path || !path[0]) return 0;
  for (int i = 0; i < HG_HEAL_QMAX; i++) if (s->q[i][0] && strncmp(s->q[i], path, HG_HEAL_PATH - 1) == 0) return 1;
  return 0;
}
void hg_heal_quarantine(hg_heal_state_t *s, const char *path)
{
  if (!path || !path[0] || hg_heal_is_quarantined(s, path)) return;
  for (int i = HG_HEAL_QMAX - 1; i > 0; i--) memcpy(s->q[i], s->q[i - 1], HG_HEAL_PATH);   /* newest first, oldest falls off */
  pcopy(s->q[0], path);
  s->quarantined++;
}

static void count_trouble(hg_heal_state_t *s, hg_heal_boot_t *b)
{
  if (b->heal_boot) return;            /* once per boot */
  b->heal_boot = 1;
  s->heals++;
  if (s->streak < 255) s->streak++;
  if (s->formats && s->post_format < 255) s->post_format++;
  if (s->formats && s->post_format > HG_HEAL_DISABLE_AFTER) { b->disable = 1; s->disabled = 1; b->format = 0; b->format_pre_mount = 0; return; }
  if (s->streak > HG_HEAL_FORMAT_AFTER) b->format = 1;
}

void hg_heal_begin(hg_heal_state_t *s, hg_heal_boot_t *b, int state_valid, uint8_t marker_reg, uint32_t build_id)
{
  memset(b, 0, sizeof *b);
  if (!state_valid) { hg_heal_state_init(s); b->state_new = 1; }
  if (s->build != build_id) { b->new_build = 1; b->reset_quick_boots = 1; s->build = build_id; }
  if (s->disabled) { b->disable = 1; }
  b->marker = (uint8_t)hg_heal_marker_decode(marker_reg, &b->cause, &b->fid, &b->count, &b->ifs_bad);
  if (!b->marker) return;
  s->faults++; s->last_cause = b->cause; s->last_fid = b->fid;
  /* 0.9.16 (plan A-24): fid none = the reset came from outside any guarded file call (0.9.16 itself books such an assert as
     a CRASH for the boot guard, never as a marker; a "none" marker can only be left by an older build). It is counted
     (faults) and NEVER touches the log area: no streak, no re-format, no storage-off. 0.9.11-0.9.15 re-formatted on it. */
  if (b->fid == HG_FID_NONE) return;
  if (hg_heal_fid_is_ifs(b->fid)) {
    /* 0.9.12: an InternalFS fault is healed on InternalFS (the sketch did it before loading this state);
       it says nothing about the QSPI log: no QSPI streak, no QSPI format, no storage-off */
    const char *pp[3]; b->ifs_action = (uint8_t)hg_heal_ifs_plan(b->fid, b->count, s->ifs_healed, pp, 3);
    return;
  }
  count_trouble(s, b);
  if (b->disable) return;
  /* 0.9.11: ANY guard reset (any file id, none and ifs included) counts; the count is in the register */
  if (b->count >= HG_HEAL_DISABLE_AT_COUNT || b->fid == HG_FID_FORMAT) {
    /* failed again after a format, or the format itself died: run without a log this boot (not persisted:
       the next power-up tries again, and a clean boot clears the register) */
    b->disable = 1; b->format = 0; b->format_pre_mount = 0; return;
  }
  if (b->count >= HG_HEAL_FORMAT_AT_COUNT) b->format = 1;
  if (b->fid == HG_FID_MOUNT) {
    /* the mount itself died: mounting again may die again; only the format path heals it */
    if (b->format) b->format_pre_mount = 1;
    return;
  }
  if (b->format) { b->format_pre_mount = 1; return; }   /* do not even mount the old area */
  if (b->fid == HG_FID_BOOT) { b->remove_boot = 1; pcopy(b->quarantine_path, "/log/boot.bin"); pcopy(s->pending, "/log/boot.bin"); }
  if (b->fid == HG_FID_HEAL && s->pending[0]) {
    /* died inside a heal remove: that file is quarantined for good and never removed again */
    hg_heal_quarantine(s, s->pending); pcopy(b->quarantine_path, s->pending); s->pending[0] = 0;
  }
}

void hg_heal_mount_failed(hg_heal_state_t *s, hg_heal_boot_t *b)
{
  count_trouble(s, b);
}

void hg_heal_after_boot(hg_heal_state_t *s, hg_heal_boot_t *b, int bootloop, uint16_t max_gen_on_disk,
                        const char *newest_sfile, const char *newest_raw)
{
  /* the events generation: a new state never reuses a file whose health is unknown */
  if (s->gen == 0 || max_gen_on_disk >= s->gen) {
    uint16_t g = max_gen_on_disk ? (uint16_t)(max_gen_on_disk + 1u) : 1u;
    if (s->gen && max_gen_on_disk == s->gen) g = s->gen;   /* the state's own live file: keep appending */
    s->gen = g;
  }
  if (bootloop && !b->disable) {
    b->quiet = 1;
    count_trouble(s, b);
  }
  if (b->disable || b->format) return;
  char cur[HG_HEAL_PATH]; hg_heal_events_path(s->gen, cur, sizeof cur);
  int named = 0;
  if (b->marker) {
    switch (b->fid) {
      case HG_FID_EVENTS:
        hg_heal_quarantine(s, cur); pcopy(b->quarantine_path, cur);
        pcopy(b->remove_path, cur); b->rotate_events = 1; named = 1; break;
      case HG_FID_SFILE:
        if (newest_sfile && newest_sfile[0]) { hg_heal_quarantine(s, newest_sfile); pcopy(b->quarantine_path, newest_sfile); }
        b->new_sfile = 1; named = 1; break;
      case HG_FID_RAW:
        if (newest_raw && newest_raw[0]) { hg_heal_quarantine(s, newest_raw); pcopy(b->quarantine_path, newest_raw); }
        named = 1; break;
      case HG_FID_DUMP:
        if (s->dump_path[0]) { hg_heal_quarantine(s, s->dump_path); pcopy(b->quarantine_path, s->dump_path); s->dump_path[0] = 0; }
        named = 1; break;
      case HG_FID_BOOT: case HG_FID_HEAL:
        named = 1; break;               /* handled in hg_heal_begin */
      default: break;                   /* ring / list / other / none: no single file to blame */
    }
  }
  (void)named;   /* 0.9.11: an unnamed marker (none / ring / list / other / ifs) quarantines NOTHING: it only counts */
  if (bootloop && !b->marker) {
    /* boot loop with no marker: leave the files that were being appended to (new events generation, new s-file),
       but put nothing on the quarantine list - nothing named them */
    if (!b->rotate_events) b->rotate_events = 1;
    b->new_sfile = 1;
  }
  if (b->rotate_events) s->gen = next_gen(s->gen);
  if (b->remove_path[0]) pcopy(s->pending, b->remove_path);   /* saved BEFORE the remove is tried */
}

void hg_heal_remove_done(hg_heal_state_t *s, hg_heal_boot_t *b, int ok)
{
  (void)ok; (void)b;
  s->pending[0] = 0;
}

void hg_heal_formatted(hg_heal_state_t *s)
{
  if (s->formats < 255) s->formats++;
  s->streak = 0; s->post_format = 0;
  memset(s->q, 0, sizeof s->q);
  s->pending[0] = 0; s->dump_path[0] = 0;
  s->gen = next_gen(s->gen);
}

int hg_heal_stable(hg_heal_state_t *s, int storage_ok)
{
  if (!storage_ok) return 0;
  if (!s->streak && !s->post_format) return 0;
  s->streak = 0; s->post_format = 0;
  return 1;
}

int hg_heal_events_result(hg_heal_state_t *s, uint8_t *fails_in_row, int failed)
{
  if (!failed) { *fails_in_row = 0; return 0; }
  if (*fails_in_row < 255) (*fails_in_row)++;
  if (*fails_in_row < HG_HEAL_RUNTIME_FAILS) return 0;
  char cur[HG_HEAL_PATH]; hg_heal_events_path(s->gen, cur, sizeof cur);
  hg_heal_quarantine(s, cur);
  s->gen = next_gen(s->gen);
  *fails_in_row = 0;
  return 1;
}

void hg_heal_reset(hg_heal_state_t *s)
{
  s->disabled = 0; s->streak = 0; s->post_format = 0; s->pending[0] = 0;
}
