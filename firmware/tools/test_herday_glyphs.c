/* 0.9.8 Her Day: every codepoint of every new band text (N1 / N7 with all 8 place words and both directions, the heat-wave
 * line, N8) exists in the 09 firmware's screen font u8g2_font_10x20_t_greek (same method as guardian/tests/glyph_check.c). */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "u8g2.h"
#include "hg_fw_eco.h"
#include "hg_fw_alert.h"
#include "hg_bootguard.h"
#include "hg_fw_ladder.h"
static int utf8_next(const unsigned char **p, uint32_t *cp) {
  const unsigned char *s = *p; if (!*s) return 0;
  if (s[0] < 0x80) { *cp = s[0]; *p += 1; return 1; }
  if ((s[0] & 0xE0) == 0xC0 && (s[1] & 0xC0) == 0x80) { *cp = ((s[0] & 0x1Fu) << 6) | (s[1] & 0x3Fu); *p += 2; return 1; }
  if ((s[0] & 0xF0) == 0xE0 && (s[1] & 0xC0) == 0x80 && (s[2] & 0xC0) == 0x80) { *cp = ((s[0] & 0x0Fu) << 12) | ((s[1] & 0x3Fu) << 6) | (s[2] & 0x3Fu); *p += 3; return 1; }
  return -1;
}
static u8g2_t U; static int bad = 0, texts = 0;
static void chk(const char *t) {
  const unsigned char *p = (const unsigned char *)t; uint32_t cp; int r; texts++;
  while ((r = utf8_next(&p, &cp)) == 1) if (!u8g2_IsGlyph(&U, (uint16_t)cp)) { printf("FAIL U+%04X not in the font: %s\n", (unsigned)cp, t); bad++; }
  if (r < 0) { printf("FAIL invalid UTF-8: %s\n", t); bad++; }
}
int main(void) {
  u8g2_Setup_null(&U, U8G2_R0, u8x8_byte_empty, u8x8_dummy_cb); u8g2_SetFont(&U, u8g2_font_10x20_t_greek);
  hg_plan_t p; hg_plan_init(&p); char b[128];
  for (uint8_t pl = 0; pl < HG_PL_N; pl++) for (uint8_t d = 1; d <= 2; d++) {
    hg_ptxt_t x = { 1, pl, d, 9, 30, 0 }; p.t1 = x; p.t7 = x;
    chk(hg_nudge_text(&p, HG_N_BRIEF, b, sizeof b)); chk(hg_nudge_text(&p, HG_N_EVENING, b, sizeof b));
  }
  hg_ptxt_t h = { 3, 0, 0, 0, 0, 2 }; p.t7 = h; chk(hg_nudge_text(&p, HG_N_EVENING, b, sizeof b));
  chk(hg_nudge_text(&p, HG_N_LEAVE_HOT, b, sizeof b));
  chk(HG_TXT_ALLCLEAR);                                   /* 0.9.9 all-clear «Πάλι όλα καλά» */
  chk(HG_BG_TXT_SERVICE);                                 /* 0.9.16 boot guard rest rung «Χρειάζεται έλεγχο» */
  chk("Heat Guardian");                                   /* 0.9.16 splash */
  /* 0.9.17 FW-UI: ladder, escalation, power-off, HELP lock (owner decisions Nov 19) */
  chk(HG_TXT_LD_WORKED); chk(HG_TXT_LD_STILL); chk(HG_TXT_LD_GOCOOL); chk(HG_TXT_LD_LIEDOWN); chk(HG_TXT_LD_SEEME); chk(HG_TXT_LD_FAMILY);
  chk(HG_TXT_PWR_PROMPT); chk(HG_TXT_PWR_HINT); chk(HG_TXT_PWR_OFF); chk(HG_TXT_HELP_ASKED);
  printf("%s: %d Her Day + all-clear + boot guard + 0.9.17 UI texts, every glyph in u8g2_font_10x20_t_greek\n", bad ? "FAIL" : "PASS", texts);
  return bad != 0;
}
