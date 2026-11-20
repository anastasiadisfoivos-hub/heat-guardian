/* Host test of fw/09_guardian/hg_fw.c (the glue) with the FROZEN guardian/twin sources compiled through the same
 * fz_*.c wrappers the sketch uses.
 *   sh fw/tools/run_host_tests.sh   (or see the gcc line there)
 * 1. minute summaries: means, HR median of OK seconds, a_std from the per-second Chan merge == the std of all 1,500
 *    samples (double reference), the twelve 5-s slots.
 * 2. pass-through: every minute, a second guardian fed the glue's own hg_minute_t gives the identical STATUS frame
 *    (the glue adds nothing to the frozen state machine).
 * 3. scenario, 4 days, clock known: 3 calm days then a hot afternoon -> no DRINK/COOL on calm days, DRINK on the hot
 *    day; exactly one nightly Body Twin update per day; <= 5 saves/day; twin file pack -> load restores the calm baseline.
 * 4. clock unknown -> no nightly update, no save.
 * 5. PPG duty: on for seconds 0-29 only when calm, all 60 while a tier is on.
 * 6. 24 h ring keeps the last 1,440 STATUS frames, oldest first; guardian record CRC + layout.
 */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "hg_fw.h"
#include "hg_astd.h"
#define hg_crc8 hg_log_crc8
#include "log_format.h"
#undef hg_crc8

static int fails = 0;
#define CHECK(c, ...) do { if (c) { printf("PASS  "); } else { printf("FAIL  "); fails++; } printf(__VA_ARGS__); printf("\n"); } while (0)

static uint32_t rng = 12345u;
static float urand(void) { rng = rng * 1664525u + 1013904223u; return (float)((rng >> 8) & 0xFFFFFF) / 16777216.0f; }

typedef struct { float t1, t2, ta, rh, hr, pi, amp; } env_t;

/* one second of synthetic sensing (25 |a| samples), returns the sample sums for the reference */
static void make_second(hg_fw_sec_t *s, const env_t *e, int sec, double *ref_sum, double *ref_sum2, int *ref_n)
{
  memset(s, 0, sizeof *s);
  s->t1_c = e->t1; s->t2_c = e->t2; s->tair_c = e->ta; s->rh_pct = e->rh;
  s->ppg_on = sec < 30; s->hr_q = 4; s->hr_bpm = e->hr + (urand() - 0.5f) * 2.0f; s->pi_pct = e->pi; s->ppg_dc = 110000;
  float a0 = 0, sum = 0; float m2 = 0, mean = 0; int n = 0; float peak = 0;
  for (int k = 0; k < 25; k++) {
    float a = 1.0f + e->amp * (urand() - 0.5f);
    if (k == 0) a0 = a;
    (void)a0;
    n++; float d = a - mean; mean += d / n; m2 += d * (a - mean);   /* Welford per second (the sketch's role) */
    sum += a; if (a > peak) peak = a;
    *ref_sum += a; *ref_sum2 += (double)a * a; (*ref_n)++;
  }
  (void)sum;
  s->a_mean = mean; s->a_m2 = m2; s->a_n = (uint16_t)n; s->a_peak_g = peak; s->zangle_deg = 10.0f;
}

static hg_guardian_t g, gref; static hg_fw_t fw; static hg2_twin_t tw; static hg_twin_acc_t acc;

int main(int argc, char **argv)
{
  FILE *fr = argc > 1 ? fopen(argv[1], "w") : NULL;   /* STATUS frames + guardian records for the dashboard / parser tests */
  hg2_profile_t p = { 75.0f, 0.0f, 26.0f, 0 };
  hg_twin_defaults(&tw); hg_twin_acc_init(&acc);
  hg_guardian_init(&g, &p, &tw); hg_guardian_init(&gref, &p, &tw);
  hg_fw_init(&fw);

  /* ---- 1. one minute of summaries ---- */
  { env_t e = { 33.5f, 31.0f, 25.0f, 45.0f, 70.0f, 0.5f, 0.02f };
    double rs = 0, rs2 = 0; int rn = 0;
    float am = 0, a2 = 0; uint32_t an = 0;   /* what 08_logger's minuteAdd() does with the same seconds (log v2 a_std_min) */
    for (int sec = 0; sec < 60; sec++) { hg_fw_sec_t s; make_second(&s, &e, sec, &rs, &rs2, &rn); if (sec == 34) s.t1_c = NAN; hg_fw_second(&fw, &s);
      hg_astd_add(&am, &a2, &an, s.a_mean, s.a_m2, s.a_n); }
    hg_fw_ctx_t c = { 600, 20000, 0, 3.9f, -1, NULL, 0 }; hg_fw_act_t a;
    hg_fw_minute(&fw, &g, &tw, &acc, &c, 60000, &a);
    const hg_minute_t *m = &fw.last_in;
    double mean = rs / rn, sd = sqrt(rs2 / rn - mean * mean);
    CHECK(fabsf(m->s.t1_c - 33.5f) < 1e-4f && fabsf(m->s.t_air_c - 25.0f) < 1e-4f && fabsf(m->s.rh_pct - 45.0f) < 1e-4f, "minute means (one NAN second skipped)");
    CHECK(m->s.hr_quality == 4 && fabsf(m->s.hr_bpm - 70.0f) <= 1.0f, "HR = median of the OK seconds (%.1f, q %u)", m->s.hr_bpm, m->s.hr_quality);
    CHECK(fabs(m->s.a_std_g - sd) < 2e-5, "a_std from the per-second merge %.6f == std of all 1500 samples %.6f", m->s.a_std_g, sd);
    float a08 = hg_astd_std(a2, an);
    CHECK(memcmp(&a08, &m->s.a_std_g, 4) == 0, "08's per-minute a_std (hg_astd.h, as minuteAdd/minuteClose) == the guardian's input bit for bit (%.7f)", a08);
    CHECK(isnan(m->t1_5s[6]) && fabsf(m->t1_5s[5] - 33.5f) < 1e-6f && fabsf(m->zangle_5s[11] - 10.0f) < 1e-6f, "5-s slots (slot 6 = the NAN second 34)");
    hg_rec_t r; CHECK(hg_rec_unpack(a.rec_in, &r) && r.flags & HG_F_MINUTE && r.t1_c100 == 3350 && r.ver == 2, "minute input record CRC (v2) + T1");
    CHECK(r.astd_min_1e4 == (uint16_t)(m->s.a_std_g * 10000.0f + 0.5f) && r.zangle_c100 == 1000 && r.astd_1e4 != 0xFFFF,
          "minute record v2: a_std_min = guardian a_std (%u), z 10.00 deg in 0.01 deg (%d), per-second-average a_std %u", r.astd_min_1e4, r.zangle_c100, r.astd_1e4);
    CHECK(hg_log_crc8(a.rec_g, 23) == a.rec_g[23] && a.rec_g[19] == 13, "guardian record CRC + marker 13");
  }

  /* ---- 3 + 2. four days, clock known ---- */
  hg_fw_init(&fw); hg_twin_defaults(&tw); hg_twin_acc_init(&acc); hg_guardian_init(&g, &p, &tw); hg_guardian_init(&gref, &p, &tw);
  int drink_calm = 0, cool_calm = 0, drink_hot = 0, passthrough_bad = 0, saves = 0, nightly = 0, max_saves_day = 0;
  int ppg_bad = 0;
  uint32_t tms = 0;
  for (int day = 0; day < 4; day++) {
    int saves_day = 0;
    for (int mod = 0; mod < 1440; mod++) {
      int hot = (day == 3 && mod >= 12 * 60 && mod < 18 * 60);
      int night = mod < 7 * 60 || mod >= 23 * 60;
      env_t e = { hot ? 35.5f : 33.8f, hot ? 35.0f : 32.2f, hot ? 35.0f : 25.0f, hot ? 40.0f : 45.0f,
                  hot ? 70.0f + (mod - 720) * 0.12f : (night ? 58.0f : 68.0f), 0.5f, night ? 0.001f : 0.03f };
      if (hot && e.hr > 110.0f) e.hr = 110.0f;
      double rs = 0, rs2 = 0; int rn = 0;
      for (int sec = 0; sec < 60; sec++) {
        if (!hg_fw_ppg_on(&fw, (uint8_t)sec) && sec < 30) ppg_bad++;
        if (fw.last_out.tiers == 0 && fw.last_out.state == HG_ST_OK && hg_fw_ppg_on(&fw, (uint8_t)sec) && sec >= 30) ppg_bad++;
        hg_fw_sec_t s; make_second(&s, &e, sec, &rs, &rs2, &rn); s.ppg_on = (uint8_t)hg_fw_ppg_on(&fw, (uint8_t)sec); hg_fw_second(&fw, &s);
      }
      hg_fw_ctx_t c = { (uint16_t)mod, 20000 + day, 0, 3.9f, -1, NULL, 0 }; hg_fw_act_t a;
      hg_fw_minute(&fw, &g, &tw, &acc, &c, tms, &a); tms += 60000;
      hg_minute_out_t o2; hg_guardian_step(&gref, &fw.last_in, &o2);
      if (a.nightly) { nightly++; hg_guardian_set_twin(&gref, &tw); }
      if (fr && (mod % 7 == 0 || (day == 3 && hot && mod % 2 == 0))) {
        fprintf(fr, "S "); for (int i = 0; i < 20; i++) fprintf(fr, "%02x", fw.last_out.status[i]);
        fprintf(fr, "\nG "); for (int i = 0; i < 24; i++) fprintf(fr, "%02x", a.rec_g[i]);
        fprintf(fr, " %u %u %d %u %u\n", fw.last_out.state, fw.last_out.screen, fw.last_out.core.valid ? (int)lroundf(fw.last_out.core.core_now * 100.0f) : 0,
                fw.last_out.tiers, fw.last_out.worn);
      }
      if (memcmp(o2.status, fw.last_out.status, 20) != 0 || o2.state != fw.last_out.state) passthrough_bad++;
      if (a.save_twin) { saves++; saves_day++; }
      uint8_t st = fw.last_out.state;
      if (day < 3) { drink_calm += st == HG_ST_DRINK; cool_calm += st == HG_ST_COOL; }
      else if (hot) drink_hot += (st == HG_ST_DRINK || st == HG_ST_COOL || (fw.last_out.tiers & 1));
    }
    if (saves_day > max_saves_day) max_saves_day = saves_day;
  }
  CHECK(passthrough_bad == 0, "pass-through: a second guardian fed the glue's hg_minute_t gives identical STATUS frames (%d mismatches / 5760 min)", passthrough_bad);
  CHECK(drink_calm == 0 && cool_calm == 0, "calm days: 0 DRINK and 0 COOL minutes (got %d / %d)", drink_calm, cool_calm);
  CHECK(drink_hot > 0, "hot afternoon (35 C room, HR rising to 110): DRINK/COOL tier minutes %d (SYNTHETIC trace, not a validation)", drink_hot);
  CHECK(nightly == 4 && max_saves_day <= HG_FW_MAX_SAVES_DAY && saves == 4, "one nightly Body Twin update per day (%d), saves %d, max/day %d", nightly, saves, max_saves_day);
  CHECK(ppg_bad == 0, "PPG duty: seconds 0-29 always on; 30-59 off unless a tier/alert is on (%d violations)", ppg_bad);
  { static uint8_t buf[HG_FW_TWIN_BUF]; hg_calm_t c1; hg_guardian_get_calm(&g, &c1);
    int n = hg_fw_twin_pack(&g, &tw, &acc, 9, buf, sizeof buf);
    static hg_guardian_t g2; hg2_twin_t tw2; hg_twin_acc_t acc2; uint32_t sc = 0;
    int rc = hg_fw_twin_load(&g2, &p, &tw2, &acc2, buf, (uint16_t)n, &sc);
    hg_calm_t c2; hg_guardian_get_calm(&g2, &c2);
    CHECK(n > 0 && n <= 900 && rc == 0 && sc == 9 && c2.calm_f20_n == c1.calm_f20_n && memcmp(&c1.calm_f20_c, &c2.calm_f20_c, 4) == 0 &&
          c1.calm_f20_n > 0 && g2.rt.days_learned == g.rt.days_learned && g2.rt.sleep_on == g.rt.sleep_on,
          "twin file %d B: load restores calm baseline (n %u -> %u), routine profile and save count", n, c1.calm_f20_n, c2.calm_f20_n);
#if HG_TWIN_VERSION >= 4   /* B5-v7 (freeze-7): the Exception-DRINK sums survive the reboot (twin file v4) */
    { hg_exc_t e1, e2; hg_guardian_get_exc(&g, &e1); hg_guardian_get_exc(&g2, &e2);
      CHECK(memcmp(&e1, &e2, sizeof e1) == 0 && memcmp(&g.x_c, &g2.x_c, 4) == 0,
            "twin v4: Exception sums restored after reboot (sxx %.4g sxy %.4g, slope c %.4f)", (double)e1.sxx, (double)e1.sxy, (double)g2.x_c); }
#endif
    buf[100] ^= 1; static hg_guardian_t g3; int rc3 = hg_fw_twin_load(&g3, &p, &tw2, &acc2, buf, (uint16_t)n, &sc);
    hg_calm_t c3; hg_guardian_get_calm(&g3, &c3);
    CHECK(rc3 < 0 && c3.calm_f20_n == 0 && tw2.rest_hr == 70.0f, "corrupted twin file -> defaults, nothing restored");
#if HG_TWIN_VERSION >= 4
    { hg_exc_t e3; hg_guardian_get_exc(&g3, &e3); CHECK(e3.sxx == 0.0f && e3.sxy == 0.0f, "corrupted twin v4 file -> Exception sums empty"); }
#endif
  }
  { static uint8_t out[HG_FW_RING_MIN][20]; uint16_t n = hg_fw_ring_get(&fw, 2000, out);
    CHECK(n == 1440 && memcmp(out[1439], fw.last_out.status, 20) == 0, "24 h RAM ring: 1440 frames, newest last");
    uint16_t mc0 = (uint16_t)(out[0][17] | (out[0][18] << 8)), mc1 = (uint16_t)(out[1439][17] | (out[1439][18] << 8));
    CHECK((uint16_t)(mc1 - mc0) == 1439, "ring frames are consecutive minutes (%u..%u)", mc0, mc1); }

  /* ---- 4. clock unknown ---- */
  hg_fw_init(&fw); hg_guardian_init(&g, &p, &tw); int night_unknown = 0;
  for (int mi = 0; mi < 1440; mi++) {
    env_t e = { 33.8f, 32.2f, 25.0f, 45.0f, 60.0f, 0.5f, 0.001f }; double rs = 0, rs2 = 0; int rn = 0;
    for (int sec = 0; sec < 60; sec++) { hg_fw_sec_t s; make_second(&s, &e, sec, &rs, &rs2, &rn); hg_fw_second(&fw, &s); }
    hg_fw_ctx_t c = { 0xFFFF, -1, 0, 3.9f, -1, NULL, 0 }; hg_fw_act_t a; hg_fw_minute(&fw, &g, &tw, &acc, &c, 0, &a);
    night_unknown += a.nightly + a.save_twin;
  }
  CHECK(night_unknown == 0, "clock unknown: no nightly update and no save in 24 h");

  /* ---- 7. T6b M2/M3: HELP, a profile change during it (no re-init), cancel with ack type 3; CRC-refused minute ---- */
  { hg_fw_init(&fw); hg_guardian_init(&g, &p, &tw); uint32_t t7 = 0;
    env_t e = { 33.8f, 32.2f, 25.0f, 45.0f, 66.0f, 0.5f, 0.02f };
#define MIN7() do { double rs = 0, rs2 = 0; int rn = 0; for (int sec = 0; sec < 60; sec++) { hg_fw_sec_t s; make_second(&s, &e, sec, &rs, &rs2, &rn); hg_fw_second(&fw, &s); } \
      hg_fw_ctx_t c = { 600, 20000, 0, 3.9f, 2, NULL, 0 }; hg_fw_act_t a; hg_fw_minute(&fw, &g, &tw, &acc, &c, t7, &a); t7 += 60000; } while (0)
    for (int i = 0; i < 30; i++) MIN7();
    hg_fw_button(&fw, 2); MIN7();
    CHECK(fw.last_out.state == HG_ST_HELP && fw.last_out.family_alert == 1 && g.help == 1, "long press -> HELP + family alert (state %u)", fw.last_out.state);
    static hg_guardian_t gb, gf; memcpy(&gb, &g, sizeof g);
    hg2_profile_t p2 = { 17.0f, 1.0f, 21.0f, 1 };
    hg_fw_apply_profile(&g, &p2);
    hg_guardian_init(&gf, &p2, &g.twin);
    int same_prof = memcmp(&g.prof, &gf.prof, sizeof g.prof) == 0 && g.m_drink == gf.m_drink && g.m_cool == gf.m_cool &&
                    g.hg2.hrmax == gf.hg2.hrmax && g.hg2.older_env == gf.hg2.older_env && g.hg2.med_flags == gf.hg2.med_flags &&
                    g.hg2.kf.hrmax == gf.hg2.kf.hrmax && g.hg2.kf.flags == gf.hg2.kf.flags && g.hg2.kf.age == gf.hg2.kf.age;
    /* every other byte unchanged: put the profile fields back into the snapshot and compare the whole struct */
    gb.prof = g.prof; gb.m_drink = g.m_drink; gb.m_cool = g.m_cool;
    gb.hg2.age = g.hg2.age; gb.hg2.sex_m = g.hg2.sex_m; gb.hg2.bmi = g.hg2.bmi; gb.hg2.hrmax = g.hg2.hrmax; gb.hg2.med_flags = g.hg2.med_flags; gb.hg2.older_env = g.hg2.older_env;
    gb.hg2.kf.age = g.hg2.kf.age; gb.hg2.kf.sex_m = g.hg2.kf.sex_m; gb.hg2.kf.bmi = g.hg2.kf.bmi; gb.hg2.kf.hrmax = g.hg2.kf.hrmax; gb.hg2.kf.flags = g.hg2.kf.flags;
    CHECK(same_prof && memcmp(&gb, &g, sizeof g) == 0 && g.help == 1 && g.family_pending == 1,
          "profile during HELP: profile constants == a fresh frozen init (hrmax %.1f, m_drink %.2f), every other byte kept, HELP + family kept",
          g.hg2.kf.hrmax, g.m_drink);
    MIN7();
    CHECK(fw.last_out.state == HG_ST_HELP && fw.last_out.family_alert == 1, "next minute: still HELP with the family alert (state %u)", fw.last_out.state);
    hg_cmd_t ack; memset(&ack, 0, sizeof ack); ack.op = HG_CMD_FAMILY_ACK; ack.ack_type = 3; ack.alarm_id = g.help_id;
    int chg = hg_guardian_cmd(&g, &ack); MIN7();
    CHECK(chg == 1 && g.help == 0 && fw.last_out.state != HG_ST_HELP && fw.last_out.family_alert == 0,
          "cancel (ack type 3 with the HELP id, as the band's 2nd long press and the dashboard send): HELP off, family flag off (state %u, check reason %u)", fw.last_out.state, fw.last_out.check_reason);
    uint16_t mc = g.minute_counter;
    { double rs = 0, rs2 = 0; int rn = 0; for (int sec = 0; sec < 60; sec++) { hg_fw_sec_t s; make_second(&s, &e, sec, &rs, &rs2, &rn); hg_fw_second(&fw, &s); } }
    hg_fw_ctx_t c = { 601, 20000, 0, 3.9f, 2, NULL, 0 }; uint8_t rin[24]; hg_fw_minute_inputs(&fw, &c, 123, rin);
    hg_rec_t r; CHECK(hg_rec_unpack(rin, &r) && (r.flags & HG_F_MINUTE) && r.t1_c100 == 3380 && r.t_ms == 123 && g.minute_counter == mc && fw.secs == 0,
          "model refused (CRC): the minute input record is still logged, the guardian is not stepped");
#undef MIN7
  }
  printf("sizeof hg_guardian_t %u, hg_fw_t %u (ring %u), hg_twin_acc_t %u\n", (unsigned)sizeof(hg_guardian_t), (unsigned)sizeof(hg_fw_t),
         (unsigned)sizeof fw.ring, (unsigned)sizeof(hg_twin_acc_t));
  if (fr) fclose(fr);
  printf("%s\n", fails ? "TEST_FW: FAIL" : "TEST_FW: PASS");
  return fails ? 1 : 0;
}
