/* [T3] Independent C replay driver for hg_twin (tester-written, not the builder's host_test).
 * Reads an event CSV in the golden_events.csv column layout (kind,t1,t2,tair,rh,hr,hrq,pi,astd,worn,tod,
 * asleep,loc,hr_valid,tier,air_ref,r0..r4) and prints, after every 'u' (nightly update), one line:
 *   U,<changed>,<frozen>,<29 params %.9g>,<t1_n[24]>,<t1_pre_cd[24]>
 * Event 'r' = ingest_reading + commit (prints R,<ret>,k,off). 'q' = room reading. 'P' (kind) = pack the
 * current state with a 650-B routine stand-in and print the hex (H,<len>,<hex>).
 * Usage: t3_driver events.csv > out.txt */
#include "hg_twin.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static float pf(const char *s) { return strtof(s, NULL); }

static int split(char *line, char **tok, int max)
{
  int n = 0; char *p = line;
  while (n < max) {
    tok[n++] = p;
    char *c = strchr(p, ',');
    if (!c) break;
    *c = 0; p = c + 1;
  }
  char *nl = strchr(tok[n - 1], '\n'); if (nl) *nl = 0;
  return n;
}

int main(int argc, char **argv)
{
  if (argc < 2) return 2;
  FILE *fe = fopen(argv[1], "r");
  if (!fe) return 3;
  static hg2_twin_t tw; static hg_twin_acc_t acc;
  hg_twin_defaults(&tw); hg_twin_acc_init(&acc);
  char line[2048];
  while (fgets(line, sizeof line, fe)) {
    char *t[32]; int n = split(line, t, 32);
    if (n < 21) continue;
    char k = t[0][0];
    if (k == 'm') {
      hg2_in_t in; memset(&in, 0, sizeof in);
      in.t1_c = pf(t[1]); in.t2_c = pf(t[2]); in.t_air_c = pf(t[3]); in.rh_pct = pf(t[4]); in.hr_bpm = pf(t[5]);
      in.hr_quality = (uint8_t)atoi(t[6]); in.pi_pct = pf(t[7]); in.a_std_g = pf(t[8]); in.worn = (uint8_t)atoi(t[9]);
      in.minute_of_day = (uint16_t)atol(t[10]);
      hg_twin_note_tier(&acc, (uint8_t)atoi(t[14]));
      hg_twin_set_air_ref(&acc, pf(t[15]));
      hg_twin_ingest_minute(&acc, &in, (uint8_t)atoi(t[11]), (uint8_t)atoi(t[12]), (uint8_t)atoi(t[13]));
    } else if (k == 'r') {
      hg_twin_ingest_reading(&acc, pf(t[16]), pf(t[17]), pf(t[18]), pf(t[19]), (uint8_t)(atoi(t[20]) ? 1 : 0));
      int r = hg_twin_commit_reading(&tw, &acc);
      printf("R,%d,%.9g,%.9g\n", r, (double)tw.k_person, (double)tw.core_offset);
    } else if (k == 'q') {
      hg_twin_ingest_room_reading(&acc, pf(t[16]), pf(t[17]), pf(t[18]));
    } else if (k == 'u') {
      int ch = hg_twin_nightly_update(&tw, &acc);
      printf("U,%d,%d,%.9g,%.9g,%.9g,%.9g", ch, acc.last_frozen, (double)tw.rest_hr, (double)tw.k_person,
             (double)tw.core_offset, (double)tw.c_bodyheat);
      for (int h = 0; h < 24; h++) printf(",%.9g", (double)tw.t1_night_base[h]);
      printf(",%d", tw.days_learned);
      for (int h = 0; h < 24; h++) printf(",%d", acc.t1_n[h]);
      for (int h = 0; h < 24; h++) printf(",%d", acc.t1_pre_cd[h]);
      printf("\n");
    } else if (k == 'P') {
      static uint8_t rout[650], buf[900];
      for (int i = 0; i < 650; i++) rout[i] = (uint8_t)((i * 31 + 7) & 255);
      int len = hg_twin_pack(&tw, &acc, rout, 650, 77u, buf, sizeof buf);
      printf("H,%d,", len);
      for (int i = 0; i < len; i++) printf("%02x", buf[i]);
      printf("\n");
    }
  }
  fclose(fe);
  return 0;
}
