/* T4: drive B5's hg_frames.c (compiled read-only from guardian/c) with frames read as hex lines.
 * stdin lines:  C <hex>   -> prints CRC-8 of the bytes
 *               P <hex>   -> parses as a CMD frame, prints op/chunk and, for 0x11, the assembled 72-B buffer state */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "hg_frames.h"
static int hex2b(const char *h, uint8_t *b) { int n = 0; unsigned v; while (h[0] && h[1] && sscanf(h, "%2x", &v) == 1) { b[n++] = (uint8_t)v; h += 2; } return n; }
int main(void) {
  char line[4096]; uint8_t b[2048]; hg_forecast_buf_t fc; hg_forecast_init(&fc); hg_cmd_t c;
  while (fgets(line, sizeof line, stdin)) {
    line[strcspn(line, "\r\n")] = 0;
    int n = hex2b(line + 2, b);
    if (line[0] == 'C') printf("C %02x\n", hg_crc8(b, (uint16_t)n));
    else if (line[0] == 'R') { hg_forecast_init(&fc); printf("R\n"); }
    else if (line[0] == 'P') {
      int r = hg_cmd_parse(b, (uint16_t)n, &c, &fc);
      printf("P r=%d op=%d chunk=%d mask=%u complete=%u bitmap=%lu plan_id=%u tag=%s data=", r, c.op, c.chunk, fc.have_mask, fc.complete,
             (unsigned long)c.safe_bitmap, c.plan_id, c.tag);
      for (int i = 0; i < 72; i++) printf("%02x", fc.data[i]);
      printf("\n");
    }
  }
  return 0;
}
