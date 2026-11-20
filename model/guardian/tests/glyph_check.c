/* B5-v7: every codepoint of every guardian screen text must exist in the 09 firmware's font (u8g2_font_10x20_t_greek) */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "u8g2.h"
#include "hg_guardian.h"
static int utf8_next(const unsigned char **p, uint32_t *cp) {
  const unsigned char *s = *p; if (!*s) return 0;
  if (s[0] < 0x80) { *cp = s[0]; *p += 1; return 1; }
  if ((s[0] & 0xE0) == 0xC0 && (s[1] & 0xC0) == 0x80) { *cp = ((s[0] & 0x1Fu) << 6) | (s[1] & 0x3Fu); *p += 2; return 1; }
  if ((s[0] & 0xF0) == 0xE0 && (s[1] & 0xC0) == 0x80 && (s[2] & 0xC0) == 0x80) { *cp = ((s[0] & 0x0Fu) << 12) | ((s[1] & 0x3Fu) << 6) | (s[2] & 0x3Fu); *p += 3; return 1; }
  return -1;
}
int main(void) {
  u8g2_t u; u8g2_Setup_null(&u, U8G2_R0, u8x8_byte_empty, u8x8_dummy_cb); u8g2_SetFont(&u, u8g2_font_10x20_t_greek);
  int bad = 0;
  for (int i = 0; i < HG_SCR_N; i++) {
    const unsigned char *p = (const unsigned char *)hg_screen_text((uint8_t)i); uint32_t cp; int r, n = 0;
    while ((r = utf8_next(&p, &cp)) == 1) { n++; if (!u8g2_IsGlyph(&u, (uint16_t)cp)) { printf("FAIL screen %d: U+%04X not in the font\n", i, cp); bad++; } }
    if (r < 0) { printf("FAIL screen %d: invalid UTF-8\n", i); bad++; }
    printf("screen %2d (%2d chars): %s\n", i, n, hg_screen_text((uint8_t)i));
  }
  if (strcmp(hg_screen_text(HG_SCR_NOT_WORN), "\xce\xa6\xce\xbf\xcf\x81\xce\xad\xcf\x83\xcf\x84\xce\xb5 \xcf\x84\xce\xbf \xce\xb2\xcf\x81\xce\xb1\xcf\x87\xce\xb9\xcf\x8c\xce\xbb\xce\xb9")) { printf("FAIL screen 7 is not «Φορέστε το βραχιόλι»\n"); bad++; }
  if (strcmp(hg_screen_text(HG_SCR_BATTERY), "\xce\xa6\xce\xbf\xcf\x81\xcf\x84\xce\xaf\xcf\x83\xcf\x84\xce\xb5 \xcf\x84\xce\xbf \xce\xb2\xcf\x81\xce\xb1\xcf\x87\xce\xb9\xcf\x8c\xce\xbb\xce\xb9")) { printf("FAIL screen 9 is not «Φορτίστε το βραχιόλι»\n"); bad++; }
  for (int i = 0; i < HG_SCR_N; i++) if (strstr(hg_screen_text((uint8_t)i), "\xce\xbf\xce\xbb\xce\xac\xce\xb9")) { printf("FAIL screen %d still has the typo\n", i); bad++; }
  printf("%s: %d screen texts, every glyph in u8g2_font_10x20_t_greek, screens 7/9 spelled «βραχιόλι»\n", bad ? "FAIL" : "PASS", HG_SCR_N);
  return bad != 0;
}
