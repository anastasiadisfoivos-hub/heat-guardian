/* Make every translation unit of 09_guardian compile like guardian/c's Makefile (-fsingle-precision-constant
 * -ffp-contract=off, and no fast-math: the core's -Ofast is undone by hg_nofastmath.h) inside the Arduino IDE, which has no per-sketch compiler flags. Checked on the core's
 * arm-none-eabi-gcc 9-2019q4: hg2_step.c built through these pragmas gives the same instructions as the flags,
 * and without them gcc contracts 14 multiply-adds into vfma (different rounding from the host golden). */
#include "hg_nofastmath.h"   /* FIRST: the core builds with -Ofast; the frozen code needs real NaN (T6b B1) */
#ifndef HG_FW_FLAGS_H
#define HG_FW_FLAGS_H
#pragma GCC optimize ("fp-contract=off")
#pragma GCC optimize ("single-precision-constant")
#ifndef HG_TWIN_USE_HG2_STEP_H
#define HG_TWIN_USE_HG2_STEP_H 1   /* guardian/c Makefile: hg_twin + hg_guardian_twin share hg2_step.h's types */
#endif
#endif
