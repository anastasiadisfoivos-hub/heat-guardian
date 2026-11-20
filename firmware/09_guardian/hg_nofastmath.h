/* hg_nofastmath.h: include this FIRST in every .ino / .c / .cpp of 08_logger and 09_guardian.
 *
 * The Seeed nRF52 core (1.1.13) compiles every sketch file with -Ofast, which turns on -ffast-math: the compiler
 * assumes NaN and Inf never occur. Then isnan(x) becomes 0, x != x becomes 0, x == x becomes 1, and NaN comparisons
 * are reordered. Heat Guardian code uses NaN for "missing" everywhere: the frozen guardian, the 08 records,
 * the vbat/aStd/rh guards. The Arduino IDE has no per-sketch compiler flags, so this pragma switches fast-math
 * off for every function defined after it in the file, and so for the whole file when it is the first include.
 * (In a .ino the builder puts <Arduino.h> above it; nothing of ours is defined there.)
 *
 * Proof (fw/tools/check_nofastmath.sh):
 *  - every top-level sketch file starts with this include;
 *  - every object the build produced contains hg_nofastmath_probe() compiled to a real VCMP;
 *  - a control compile without the pragma folds the same probe to "movs r0, #0".
 * The tests/t6b emulator then shows that the ARM image == the host golden bit for bit (B6b report).
 * hg_nofastmath_probe is "used", so it is in every object file; --gc-sections drops it from the image (0 bytes). */
#ifndef HG_NOFASTMATH_H
#define HG_NOFASTMATH_H
#pragma GCC optimize ("no-fast-math")
static int __attribute__((used, noinline)) hg_nofastmath_probe(float x) { return __builtin_isnan(x); }
#endif
