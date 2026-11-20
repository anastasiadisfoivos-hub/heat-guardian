/* Host test for fw/08_logger/log_format.h (acceptance 2 of brief B6 Part A).
 *   gcc -std=c99 -Wall -Wextra -Werror -O2 -I../08_logger test_record.c -o /tmp/test_record && /tmp/test_record vectors.json
 * 1. CRC-8 check value: crc8("123456789") == 0xF4 (CRC-8/SMBUS, poly 0x07).
 * 2. 10,000 random records: pack -> unpack -> identical fields, CRC OK; hex is 48 chars.
 * 3. every single-bit flip of 1,000 packed records is detected by the CRC (CRC-8 detects all
 *    1-bit errors; 192 flips x 1,000 records).
 * 4. writes 32 vectors (fields + hex) as JSON so the Python parser is checked against this C code (v2 records, and
 *    8 v1 records packed by the 1.1.1 packer kept below: old files must still parse).
 * 5. v1 records (1.1.1 packer) unpack with ver 1, z in 0.01 deg = whole degrees x 100, minute aux kept.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "log_format.h"

static uint32_t rng = 20261112u;
static uint32_t xr(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }

/* the 1.1.1 packer (format v1), kept to prove old files still parse */
static void pack_v1(const hg_rec_t *r, int8_t z_deg, uint8_t b[HG_REC_SIZE])
{
  b[0] = (uint8_t)r->t_ms; b[1] = (uint8_t)(r->t_ms >> 8); b[2] = (uint8_t)(r->t_ms >> 16); b[3] = (uint8_t)(r->t_ms >> 24);
  hg_put16(b + 4, (uint16_t)r->t1_c100); hg_put16(b + 6, (uint16_t)r->t2_c100); hg_put16(b + 8, (uint16_t)r->tair_c100);
  b[10] = r->rh; b[11] = r->hr; b[12] = r->hr_q; hg_put16(b + 13, r->pi_100); hg_put16(b + 15, r->astd_1e4);
  b[17] = (uint8_t)z_deg; b[18] = r->flags; b[19] = r->marker; b[20] = r->dc8; hg_put16(b + 21, r->aux);
  b[23] = hg_crc8(b, 23);
}
static void rand_rec(hg_rec_t *r)
{
  r->t_ms = xr();
  r->t1_c100 = (int16_t)xr(); r->t2_c100 = (int16_t)xr(); r->tair_c100 = (int16_t)xr();
  r->rh = (uint8_t)xr(); r->hr = (uint8_t)xr(); r->hr_q = (uint8_t)(xr() % 6); if (r->hr_q == 5) r->hr_q = HG_HRQ_NONE;
  r->pi_100 = (uint16_t)xr(); r->astd_1e4 = (uint16_t)xr();
  r->zangle_c100 = (int16_t)((int32_t)(xr() % 18001) - 9000); r->flags = (uint8_t)xr(); r->marker = (uint8_t)(xr() % 14); r->dc8 = (uint8_t)xr();
  r->aux = (uint16_t)xr(); r->astd_min_1e4 = (uint16_t)xr();
  if ((r->flags & HG_F_MINUTE) && !HG_REC_MIN_AUX_MARKER(r->marker)) r->aux = 0; else r->astd_min_1e4 = 0xFFFF;   /* v2: one u16 slot */
  r->ver = 2;
}
static int same(const hg_rec_t *a, const hg_rec_t *b)
{
  return a->t_ms == b->t_ms && a->t1_c100 == b->t1_c100 && a->t2_c100 == b->t2_c100 && a->tair_c100 == b->tair_c100 &&
         a->rh == b->rh && a->hr == b->hr && a->hr_q == b->hr_q && a->pi_100 == b->pi_100 && a->astd_1e4 == b->astd_1e4 &&
         a->zangle_c100 == b->zangle_c100 && a->flags == b->flags && a->marker == b->marker && a->dc8 == b->dc8 && a->aux == b->aux &&
         a->astd_min_1e4 == b->astd_min_1e4 && a->ver == b->ver;
}

int main(int argc, char **argv)
{
  int fails = 0;
  uint8_t c = hg_crc8((const uint8_t *)"123456789", 9);
  printf("crc8(\"123456789\") = 0x%02X (expect 0xF4) %s\n", c, c == 0xF4 ? "OK" : "FAIL");
  if (c != 0xF4) fails++;

  int rt_fail = 0;
  for (int i = 0; i < 10000; i++) {
    hg_rec_t a, b; uint8_t buf[HG_REC_SIZE]; char hex[HG_REC_HEX_LEN + 1];
    rand_rec(&a);
    hg_rec_pack(&a, buf);
    memset(&b, 0, sizeof b);
    if (!hg_rec_unpack(buf, &b) || !same(&a, &b)) rt_fail++;
    hg_hex(buf, HG_REC_SIZE, hex);
    if (strlen(hex) != HG_REC_HEX_LEN) rt_fail++;
  }
  printf("round-trip 10000 random records: %d failures %s\n", rt_fail, rt_fail ? "FAIL" : "OK");
  fails += rt_fail != 0;

  long flips = 0, undetected = 0;
  for (int i = 0; i < 1000; i++) {
    hg_rec_t a, b; uint8_t buf[HG_REC_SIZE];
    rand_rec(&a); hg_rec_pack(&a, buf);
    for (int bit = 0; bit < 8 * HG_REC_SIZE; bit++) {
      buf[bit / 8] ^= (uint8_t)(1u << (bit % 8));
      if (hg_rec_unpack(buf, &b)) undetected++;
      flips++;
      buf[bit / 8] ^= (uint8_t)(1u << (bit % 8));
    }
  }
  printf("single-bit flips: %ld tested, %ld undetected %s\n", flips, undetected, undetected ? "FAIL" : "OK");
  fails += undetected != 0;

  /* v1 compatibility: 1,000 records from the 1.1.1 packer */
  int v1_fail = 0;
  for (int i = 0; i < 1000; i++) {
    hg_rec_t a, b; uint8_t buf[HG_REC_SIZE]; rand_rec(&a);
    int8_t z = (int8_t)((int)(xr() % 181) - 90); a.zangle_c100 = (int16_t)(z * 100); a.aux = (uint16_t)xr(); a.astd_min_1e4 = 0xFFFF; a.ver = 1;
    a.marker = (uint8_t)(xr() % 13); a.hr_q = (uint8_t)xr();
    pack_v1(&a, z, buf);
    if (!hg_rec_unpack(buf, &b) || !same(&a, &b)) v1_fail++;
  }
  printf("v1 (1.1.1) records still unpack (ver 1, z x100, minute aux kept): %d failures %s\n", v1_fail, v1_fail ? "FAIL" : "OK");
  fails += v1_fail != 0;

  /* sentinel helper */
  if (hg_c100(36.854f, 1) != 3685 || hg_c100(-0.004f, 1) != 0 || hg_c100(1.0f, 0) != HG_T_ABSENT || hg_c100(400.0f, 1) != 32766) {
    printf("hg_c100 FAIL\n"); fails++;
  } else printf("hg_c100 rounding/sentinel OK\n");

  if (argc > 1) {
    FILE *f = fopen(argv[1], "w");
    if (!f) { perror(argv[1]); return 2; }
    fprintf(f, "{\"crc8_check_123456789\": %u, \"records\": [\n", c);
    rng = 7u;
    for (int i = 0; i < 40; i++) {
      hg_rec_t a, b; uint8_t buf[HG_REC_SIZE]; char hex[HG_REC_HEX_LEN + 1];
      rand_rec(&a);
      if (i < 32) hg_rec_pack(&a, buf);
      else { int8_t z = (int8_t)((int)(xr() % 181) - 90); a.zangle_c100 = (int16_t)(z * 100); a.marker = (uint8_t)(xr() % 13); pack_v1(&a, z, buf); }
      hg_rec_unpack(buf, &b); hg_hex(buf, HG_REC_SIZE, hex);
      fprintf(f, " {\"hex\": \"%s\", \"ver\": %u, \"t_ms\": %u, \"t1\": %d, \"t2\": %d, \"tair\": %d, \"rh\": %u, \"hr\": %u, \"hr_q\": %u, "
                 "\"pi\": %u, \"astd\": %u, \"zangle_c100\": %d, \"flags\": %u, \"marker\": %u, \"dc8\": %u, \"aux\": %u, \"astd_min\": %u}%s\n",
              hex, b.ver, b.t_ms, b.t1_c100, b.t2_c100, b.tair_c100, b.rh, b.hr, b.hr_q, b.pi_100, b.astd_1e4, b.zangle_c100,
              b.flags, b.marker, b.dc8, b.aux, b.astd_min_1e4, i < 39 ? "," : "");
    }
    fprintf(f, "]}\n");
    fclose(f);
    printf("wrote 40 vectors (32 v2, 8 v1) to %s\n", argv[1]);
  }
  printf("%s\n", fails ? "TEST_RECORD: FAIL" : "TEST_RECORD: PASS");
  return fails ? 1 : 0;
}
