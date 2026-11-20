/* Heat Guardian - contact self-check (ARCHITECTURE 7.1 step 2, 7.2 "Contact thresholds"; R2 s5 table; R4 A7).
 * Evaluated once per minute on a 10-min ring of 5-s temperatures. Output 0 off / 1 loose / 2 worn, 2-min hysteresis.
 * Not implemented from the A7.2 row: "TMCC/CV irregular -> loose" - an irregular rhythm (atrial fibrillation,
 * ~10 % prevalence at 80+) would read as a permanently loose band; hg_ppg's IRREGULAR word is therefore not a
 * contact signal here (reported in REPORT_GUARDIAN.md). */
#ifndef HG_CONTACT_H
#define HG_CONTACT_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define HG_CT_RING 120               /* 10 min x 12 samples of 5 s */
typedef struct {
  float t1[HG_CT_RING], t2[HG_CT_RING], ta[HG_CT_RING];
  float ratio[30];
  float t1_ref;                      /* T1 before the loose step (latch release level) */
  uint32_t dc_hist[3];               /* PPG DC of the last 3 minutes (0 = no PPG that minute) */
  uint16_t ri;                       /* next write index into the 5-s ring */
  uint16_t n5;                       /* number of 5-s samples seen (saturating) */
  uint8_t rti, rtn, out, cand, cand_run, loose_latch, reason, _pad;
} hg_contact_t;
#define HG_CT_R_CHARGING 1
#define HG_CT_R_NOSKIN   2
#define HG_CT_R_FLAT     4
#define HG_CT_R_THERMOFF 8
#define HG_CT_R_STEP     16
#define HG_CT_R_RATIO    32
#define HG_CT_R_PI       64
#define HG_CT_R_HOT      128         /* thermal rules disabled (T_air >= 34 C) */
void hg_contact_init(hg_contact_t *c);
uint8_t hg_contact_step(hg_contact_t *c, const float t1_5s[12], const float t2_5s[12], const float tair_5s[12],
                        float pi, uint8_t ppg_q, uint32_t ppg_dc, float a_std, uint8_t flat_still_min, uint8_t charging);
#ifdef __cplusplus
}
#endif
#endif
