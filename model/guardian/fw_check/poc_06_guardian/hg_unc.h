/* M5.2 uncertainty constants, taken from B2's hg2 export when it provides them (see hg_guardian_cfg.h M5 block).
 * HG2_CONF_HALF_CAL: split-conformal half-width (degC) of the calibrated "reading today" interval (B2, not exported yet).
 * HG2_CONF_SD_SCALE / HG2_SD_SCALE_RECOMMENDED: factor that makes 1.645*sd a calibrated 90 % half-width.
 * PROVISIONAL fallbacks while B2 has not exported them: scale = HG2_SD_SCALE_RECOMMENDED (dev-calibrated, 2.98) or 1;
 * h_cal = 0 (every bit of width counts as excess -> the lowering saturates at 0.10 C whenever sd_20 >= 0.02 C / scale). */
#ifndef HG_UNC_H
#define HG_UNC_H
#include "hg2_weights.h"
#if defined(HG2_CONF_SD_SCALE)
#define HG_UNC_SD_SCALE_EFF (HG2_CONF_SD_SCALE)
#elif defined(HG2_SD_SCALE_RECOMMENDED)
#define HG_UNC_SD_SCALE_EFF (HG2_SD_SCALE_RECOMMENDED)
#else
#define HG_UNC_SD_SCALE_EFF (1.0f)
#endif
#if defined(HG2_CONF_HALF_CAL)
#define HG_UNC_HALF_CAL_EFF (HG2_CONF_HALF_CAL)
#else
#define HG_UNC_HALF_CAL_EFF (0.0f)
#endif
/* M11.4: real conformal widths. B2 exports HG2_WATCH_LOWER_UNCAL (= half of the f20 90 % half-width excess,
 * (HG2_RANGE90_F20_NOREAD - HG2_RANGE90_F20_READ) / 2 = 0.018 C): used as the constant uncalibrated lowering when present. */
#if defined(HG2_WATCH_LOWER_UNCAL)
#define HG_UNC_CONST_MODE 1
#define HG_UNC_LOWER_CONST (HG2_WATCH_LOWER_UNCAL)
#else
#define HG_UNC_CONST_MODE 0
#define HG_UNC_LOWER_CONST (0.0f)
#endif
/* [B2-fix] 0978398: the displayed range half-width is max(1.645*sd, HG2_CONF_HALF_NOW_REAL) (nested-LOSO split-conformal
 * 90 % on HTT, REAL young adults) until wear-test wrist data exists. Display only: the tiers keep the M11.4 constant lowering. */
#if defined(HG2_CONF_HALF_NOW_REAL)
#define HG_RANGE_HALF_REAL_EFF (HG2_CONF_HALF_NOW_REAL)
#else
#define HG_RANGE_HALF_REAL_EFF (0.0f)
#endif
#if defined(HG2_EPS_V)
#define HG2_EPS_V_EFF (HG2_EPS_V)
#else
#define HG2_EPS_V_EFF (0.0f)
#endif
#endif
