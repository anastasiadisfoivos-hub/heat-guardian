/* T5 D1 (fast-math robustness). Include FIRST in every guardian/c translation unit (before any header that defines inline
 * functions), so every function of the Guardian Loop, hg2 and the v1.2 port is compiled with IEEE-exact float semantics
 * even when the firmware build passes -Ofast / -ffast-math (the Arduino nRF52 core does):
 *  - GCC: the optimize pragma switches off, for these functions, every -ffast-math sub-option that changes results:
 *    finite-math-only (NaN/inf tests folded away), associative/reciprocal math (re-ordered sums: knife-edge tier flips),
 *    signed zeros, trapping math, and FP contraction (FMA). Decision-critical sums then keep the source order on every ISA.
 *  - clang: float_control(precise, on) + FP_CONTRACT OFF for the same effect.
 *  - any other compiler with __FAST_MATH__: refuse to build (better no build than a band with silent NaN/order bugs).
 * NaN / inf tests never rely on x != x either: hg_isnan / hg_isfinite read the IEEE-754 bits (memcpy), which no
 * floating-point flag can fold. Host result: -O2 and -Ofast -ffast-math give bit-identical outputs (tests/fastmath_check.sh). */
#ifndef HG_FP_H
#define HG_FP_H
#if defined(__clang__)
#pragma float_control(precise, on)
#pragma STDC FP_CONTRACT OFF
#elif defined(__GNUC__)
#pragma GCC optimize ("no-fast-math", "no-unsafe-math-optimizations", "no-associative-math", "no-reciprocal-math", \
                      "no-finite-math-only", "signed-zeros", "trapping-math", "fp-contract=off")
#elif defined(__FAST_MATH__)
#error "Heat Guardian: build these sources without fast-math (IEEE NaN/inf semantics and summation order are required)"
#endif
#include <stdint.h>
#include <string.h>
static inline uint32_t hg_fbits(float x) { uint32_t u; memcpy(&u, &x, sizeof u); return u; }
/* exponent all ones and mantissa != 0 */
static inline int hg_isnan_bits(float x) { return (hg_fbits(x) & 0x7FFFFFFFu) > 0x7F800000u; }
/* exponent not all ones (excludes +-inf and NaN) */
static inline int hg_isfinite_bits(float x) { return (hg_fbits(x) & 0x7F800000u) != 0x7F800000u; }
#endif
