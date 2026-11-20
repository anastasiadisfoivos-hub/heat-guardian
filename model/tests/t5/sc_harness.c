/* T5 scripted-core harness: the frozen Guardian Loop (guardian/c/hg_guardian.c + contact/homeout/routine/frames/util,
 * compiled unchanged) linked against a STUB Core Sense whose outputs are read from a script. This lets the tests drive
 * f20 / v1.2 z / env flags / heat context to exact float values (M12, M13 edge cases, M3.1 pairs, hold/debounce oracle).
 * The stub reproduces only the donning counter / valid flag of hg2_step.c (lines 123-126, 255), everything else is scripted.
 *   ./sc_harness in.csv out.csv
 * in.csv : #PROFILE,age,sex_m,bmi,flags  then rows
 *   mod,button,worn,vbat,astd,apeak,cmd_hex|-,hr_valid,logit_p38,logit_p385,strain,sd_20,core20,v12_f20,v12_z,tair,
 *   env_above,env_above_old,env_run,env_dose,active,still,x10,x14,rh
 * out.csv: one row per minute (see OUT below). */
#define _POSIX_C_SOURCE 200809L
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "hg_guardian.h"
#include "hg_guardian_cfg.h"

typedef struct { float hr_valid, l38, l385, strain, sd20, core20, v12f20, v12z, tair, ea, eao, erun, edose, act, still, x10, x14, rh; } scr_t;
static scr_t S;

void hg2_init(hg2_state_t *s, const hg2_profile_t *p, const hg2_twin_t *tw) { (void)p; memset(s, 0, sizeof *s); s->core_offset = tw->core_offset; s->rh_last = NAN; }
void hg2_set_twin(hg2_state_t *s, const hg2_twin_t *tw) { s->core_offset = tw->core_offset; }
void hg2_step(hg2_state_t *s, const hg2_in_t *in, hg2_out_t *out) { (void)s; (void)in; (void)out; }
int hg2_check_crc(void) { return 1; }
uint16_t hg2_state_size(void) { return (uint16_t)sizeof(hg2_state_t); }
void hg2_step_aux(hg2_state_t *s, const hg2_in_t *in, hg2_out_t *o, hg2_aux_t *a) {
  const uint8_t worn = in->worn;                       /* = hg2_step.c 123-126 */
  if (worn == 2) { if (s->last_worn != 2) s->min_since_don = 0; else if (s->min_since_don < 60) s->min_since_don++; }
  else s->min_since_don = 0;
  s->last_worn = worn;
  s->rh_last = S.rh;
  memset(o, 0, sizeof *o);
  o->core_now = S.core20; o->core_20 = S.core20; o->core_30 = S.core20; o->f20_eff = S.core20; o->f30_eff = S.core20;
  o->sd_now = 0.1f; o->sd_20 = S.sd20; o->sd_30 = S.sd20; o->logit_p38 = S.l38; o->logit_p385 = S.l385; o->strain = S.strain;
  o->kf = 0.0f; o->core_flux = NAN; o->flux_valid = 0; o->hr_valid = (uint8_t)(S.hr_valid != 0.0f);
  o->valid = (uint8_t)((worn == 2) && (s->min_since_don >= HG_DON_VALID_MIN));   /* = hg2_step.c 255 */
  o->why = 0;
  if (a) {
    memset(a, 0, sizeof *a);
    a->x[10] = S.x10; a->x[14] = S.x14; a->core20_noff = S.core20; a->v12_f20 = S.v12f20; a->v12_z = S.v12z; a->v12_est = S.v12f20;
    a->t_air_corr = S.tair; a->env_above = (uint8_t)S.ea; a->env_above_old = (uint8_t)S.eao; a->env_run = (int16_t)S.erun;
    a->env_dose = (int16_t)S.edose; a->active = (uint8_t)S.act; a->still = (uint8_t)S.still;
  }
}

static void hexbytes(const char *h, uint8_t *b, int *n) { int k = 0; while (h[0] && h[1] && k < 64) { unsigned v; if (sscanf(h, "%2x", &v) != 1) break; b[k++] = (uint8_t)v; h += 2; } *n = k; }
static float tf(char **sv) { char *t = strtok_r(NULL, ",\r\n", sv); return t ? strtof(t, NULL) : NAN; }

int main(int argc, char **argv) {
  if (argc < 3) return 2;
  FILE *fi = fopen(argv[1], "r"), *fo = fopen(argv[2], "w"); if (!fi || !fo) return 2;
  static char line[4096]; static hg_guardian_t g; int started = 0;
  hg2_profile_t prof = { 75.0f, 0.0f, 26.0f, 0 }; hg2_twin_t tw; memset(&tw, 0, sizeof tw);
  tw.rest_hr = 70.0f; tw.k_person = 0.12f; tw.c_bodyheat = 0.15f; for (int h = 0; h < 24; h++) tw.t1_night_base[h] = NAN;
  hg_forecast_buf_t fc; hg_forecast_init(&fc);
  while (fgets(line, sizeof line, fi)) {
    char *sv = NULL;
    if (line[0] == '#') { char *t = strtok_r(line, ",\r\n", &sv);
      if (!strcmp(t, "#PROFILE")) { prof.age = tf(&sv); prof.sex_m = tf(&sv); prof.bmi = tf(&sv); prof.med_flags = (uint8_t)tf(&sv); }
      if (!strcmp(t, "#CALM")) { if (!started) { hg_guardian_init(&g, &prof, &tw); started = 1; } hg_calm_t c; c.calm_f20_c = tf(&sv); c.calm_f20_n = (uint8_t)tf(&sv); hg_guardian_set_calm(&g, &c); }
      continue; }
    if (!started) { hg_guardian_init(&g, &prof, &tw); started = 1; }
    hg_minute_t m; memset(&m, 0, sizeof m);
    char *t = strtok_r(line, ",\r\n", &sv); if (!t) continue;
    m.s.minute_of_day = (uint16_t)strtol(t, NULL, 10);
    m.button = (uint8_t)tf(&sv); m.force_worn = (uint8_t)tf(&sv); m.vbat = tf(&sv); m.s.a_std_g = tf(&sv); m.a_peak_g = tf(&sv);
    char *cmd = strtok_r(NULL, ",\r\n", &sv);
    S.hr_valid = tf(&sv); S.l38 = tf(&sv); S.l385 = tf(&sv); S.strain = tf(&sv); S.sd20 = tf(&sv); S.core20 = tf(&sv);
    S.v12f20 = tf(&sv); S.v12z = tf(&sv); S.tair = tf(&sv); S.ea = tf(&sv); S.eao = tf(&sv); S.erun = tf(&sv); S.edose = tf(&sv);
    S.act = tf(&sv); S.still = tf(&sv); S.x10 = tf(&sv); S.x14 = tf(&sv); S.rh = tf(&sv);
    m.s.hr_quality = 4; m.s.hr_bpm = NAN; m.s.t1_c = NAN; m.s.t2_c = NAN; m.s.t_air_c = NAN; m.s.rh_pct = NAN; m.s.pi_pct = NAN;
    for (int k = 0; k < 12; k++) { m.t1_5s[k] = NAN; m.t2_5s[k] = NAN; m.tair_5s[k] = NAN; m.zangle_5s[k] = NAN; }
    m.ppg_dc = 100000; m.ble_bucket = -1;
    if (cmd && cmd[0] != '-') { uint8_t b[64]; int n = 0; hexbytes(cmd, b, &n); hg_cmd_t c; if (hg_cmd_parse(b, (uint16_t)n, &c, &fc) > 0) hg_guardian_cmd(&g, &c); }
    hg_minute_out_t o; memset(&o, 0, sizeof o);
    hg_guardian_step(&g, &m, &o);
    fprintf(fo, "%d,%d,%d,%lu,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%.9g,%d,%d,%d,%d\n",
            o.state, o.level, o.family_alert, (unsigned long)o.alarm_id, o.check_reason, o.check_min, o.haptic, o.screen, o.tiers,
            o.routine_req, o.imok_resp_min, o.notify_not_worn, o.why, o.night_heat, o.nudge, o.worn,
            g.help, g.snooze, g.pd_cool_run, g.cool_p.on, g.cool_ack, g.still_run, g.check_active, g.a_base_n, (double)g.a_base,
            g.a_n, g.rt.hour_clean, (int)g.hg2.min_since_don, g.beh_now);
  }
  fclose(fi); fclose(fo); return 0;
}
