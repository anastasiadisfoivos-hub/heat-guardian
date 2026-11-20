/* T6b: the frozen hg_cmd_parse() (what 09 runs on every CMD write) against tomorrow/tests/ble_vectors.json (B4) and
 * the dashboard's own frames, plus malformed-frame attacks. Input on stdin, one line per frame: "<tag> <hex>". */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "frozen/hg_frames.h"
static int hexb(const char *h, uint8_t *b) { int n = 0; while (h[0] && h[1] && n < 64) { unsigned v; sscanf(h, "%2x", &v); b[n++] = (uint8_t)v; h += 2; } return n; }
int main(void) {
  char tag[64], hx[200]; hg_forecast_buf_t fc; hg_forecast_init(&fc);
  while (scanf("%63s %199s", tag, hx) == 2) {
    uint8_t b[64]; int n = hexb(hx, b); hg_cmd_t c;
    int rc = hg_cmd_parse(b, (uint16_t)n, &c, &fc);
    printf("%s n=%d rc=%d", tag, n, rc);
    if (rc == HG_CMD_TIME) printf(" unix=%u tz_q=%d", c.unix_s, c.tz_q);
    if (rc == HG_CMD_FAMILY_ACK) printf(" ack=%u alarm=0x%08x", c.ack_type, c.alarm_id);
    if (rc == HG_CMD_PROFILE) printf(" field=%u value=%g", c.field, c.value);
    if (rc == HG_CMD_FORECAST) printf(" chunk=%u mask=0x%x complete=%u", c.chunk, fc.have_mask, fc.complete);
    if (rc == HG_CMD_SAFE_HOURS) printf(" bitmap=%u plan=%u tag=%s", c.safe_bitmap, c.plan_id, c.tag);
    printf("\n");
  }
  printf("FC");
  for (int h = 0; h < 24; h++) printf(" %d/%u/%u", (int8_t)fc.data[3 * h], fc.data[3 * h + 1], fc.data[3 * h + 2]);
  printf("\n");
  return 0;
}
