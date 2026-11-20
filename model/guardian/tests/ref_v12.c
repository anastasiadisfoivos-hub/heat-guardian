/* hg_kf (guardian/c) vs the ORIGINAL v1.2 reference /home/claude/hgmodel/heat_guardian_band.c (included read-only).
 * stdin: "S age male bmi rest_hr flags" starts a session, then per minute "hr amb rh still button", "E" ends it.
 * stdout: per-session and overall max |d est|, |d f20|, |d z| (z_ref = logit(p_ref)), |d p|, state agreement. */
#include "/home/claude/hgmodel/heat_guardian_band.c"
#include <stdio.h>
#include <string.h>
#include "hg_kf.h"
#include "hg_util.h"

int main(void) {
  char line[256];
  hg_state ref; hg_kf_t kf; hg_v12_tiers_t vt; int in_s = 0;
  double mx_est = 0, mx_f20 = 0, mx_z = 0, mx_p = 0; long n = 0, agree = 0, nses = 0;
  long st_ref[4] = {0}, st_new[4] = {0};
  while (fgets(line, sizeof line, stdin)) {
    if (line[0] == 'S') {
      float age, bmi, rest; int male, flags;
      if (sscanf(line + 1, "%f %d %f %f %d", &age, &male, &bmi, &rest, &flags) != 5) return 2;
      hg_init(&ref, age, male, bmi, rest, flags);
      hg_kf_init(&kf, age, male, bmi, rest, (uint8_t)flags); kf.rh_clamp = 0;   /* exact v1.2 for the line-for-line check */ hg_v12_tiers_init(&vt, age, (uint8_t)flags);
      in_s = 1; nses++; continue;
    }
    if (line[0] == 'E') { in_s = 0; continue; }
    if (!in_s) continue;
    float hr, amb, rh; int still, button;
    if (sscanf(line, "%f %f %f %d %d", &hr, &amb, &rh, &still, &button) != 5) continue;
    float e, f, p, rg; int why = 0, why2 = 0;
    hg_risk q = hg_step(&ref, hr, amb, rh, still, button, &e, &f, &p, &rg, &why);
    hg_kf_out_t o; hg_kf_step(&kf, hr, amb, rh, &o);
    int q2 = hg_kf_v12_step(&vt, &o, amb, rh, still, button, &why2);
    double de = fabs((double)e - (double)o.est), df = fabs((double)f - (double)o.f20);
    double pn = 1.0 / (1.0 + exp(-(double)o.z)), dp = fabs((double)p - pn);
    if (de > mx_est) mx_est = de;
    if (df > mx_f20) mx_f20 = df;
    if (dp > mx_p) mx_p = dp;
    if (p > 1e-30f && p < 1.0f - 1e-6f) { double zr = log((double)p / (1.0 - (double)p)); double dz = fabs(zr - (double)o.z); if (dz > mx_z) mx_z = dz; }
    n++; if ((int)q == q2 && why == why2) agree++;
    else { double pa_ref = (double)rh * 0.01 * 0.61094 * exp(17.625 * (double)amb / ((double)amb + 243.04)); fprintf(stderr, "  mismatch: amb %.4f rh %.4f state %d/%d why %d/%d Pa_exact %.5f Pa_table %.5f line %.5f\n", (double)amb, (double)rh, (int)q, q2, why, why2, pa_ref, (double)hg_pa_kpa(amb, rh), (double)(vt.lim_a + vt.lim_b * amb)); }
    st_ref[(int)q]++; st_new[q2]++;
  }
  printf("sessions %ld minutes %ld\nmax|d est| %.3e C\nmax|d f20| %.3e C\nmax|d z| %.3e\nmax|d p| %.3e\nstate+why agreement %ld/%ld = %.4f %%\n",
         nses, n, mx_est, mx_f20, mx_z, mx_p, agree, n, 100.0 * (double)agree / (double)(n ? n : 1));
  printf("state minutes ref  OK %ld DRINK %ld COOL %ld DANGER %ld\nstate minutes port OK %ld DRINK %ld COOL %ld DANGER %ld\n",
         st_ref[0], st_ref[1], st_ref[2], st_ref[3], st_new[0], st_new[1], st_new[2], st_new[3]);
  return 0;
}
