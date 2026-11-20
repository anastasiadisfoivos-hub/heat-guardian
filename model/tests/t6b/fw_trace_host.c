/* T6b: host reference of the whole 09 minute pipeline (hg_fw glue + FROZEN guardian/hg2/twin) with the sealed-exam golden
 * flags for the frozen code (-O2 -fsingle-precision-constant -ffp-contract=off). Reads sec.bin / ctx.bin from
 * make_scenario.py, writes act.bin = per minute { save_twin, nightly, status_changed, rec_in[24], rec_g[24] } (51 B). */
#include <stdio.h>
#include <string.h>
#include "hg_fw.h"
static hg_guardian_t g; static hg_fw_t fw; static hg2_twin_t tw; static hg_twin_acc_t acc;
int main(int argc, char **argv) {
  char p[512]; snprintf(p, sizeof p, "%s/sec.bin", argv[1]); FILE *fs = fopen(p, "rb");
  snprintf(p, sizeof p, "%s/ctx.bin", argv[1]); FILE *fc = fopen(p, "rb");
  snprintf(p, sizeof p, "%s/%s", argv[1], argv[2]); FILE *fo = fopen(p, "wb");
  hg2_profile_t pr = { 75.0f, 0.0f, 26.0f, 0 }; uint32_t sc = 0;
  hg_fw_init(&fw); hg_fw_twin_load(&g, &pr, &tw, &acc, NULL, 0, &sc);
  if (sizeof(hg_fw_sec_t) != 52) { printf("layout %u\n", (unsigned)sizeof(hg_fw_sec_t)); return 1; }
  unsigned char cb[10]; uint32_t t = 0; int n = 0;
  while (fread(cb, 10, 1, fc) == 1) {
    for (int s = 0; s < 60; s++) { hg_fw_sec_t x; if (fread(&x, 52, 1, fs) != 1) return 1; hg_fw_second(&fw, &x); }
    hg_fw_ctx_t c; memset(&c, 0, sizeof c); memcpy(&c.minute_of_day, cb, 2); memcpy(&c.local_day, cb + 2, 4); memcpy(&c.vbat, cb + 6, 4);
    c.ble_bucket = -1; hg_fw_act_t a; hg_fw_minute(&fw, &g, &tw, &acc, &c, t, &a); t += 60000;
    fwrite(&a, 51, 1, fo); n++;
  }
  fclose(fo); printf("host: %d minutes\n", n); return 0;
}
