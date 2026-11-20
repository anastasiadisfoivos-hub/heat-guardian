/* m1 regression: the oral-reading parser used by 08_logger.ino handleCommand() ("mark oral <T>").
 * The function below is a byte-for-byte copy of the sketch's parsing lines; pre-fix (atof) is shown too.
 *   gcc -std=c99 -Wall -Wextra -Werror test_cmdparse.c -o /tmp/tc && /tmp/tc
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
static long parse_new(const char *arg)
{
  float t = 0;
  char num[16]; strncpy(num, arg, sizeof num - 1); num[sizeof num - 1] = 0;
  for (char* c = num; *c; c++) if (*c == ',') *c = '.';
  char* end = NULL; t = strtof(num, &end);
  if (end == num || *end) t = 0;
  if (t < 30.0f || t > 43.0f) return -1;
  return lroundf(t * 100.0f);
}
static long parse_old(const char *arg) { float t = (float)atof(arg); if (t < 30.0f || t > 43.0f) return -1; return lroundf(t * 100.0f); }
int main(void)
{
  struct { const char *in; long want; } v[] = { {"36.85", 3685}, {"36,85", 3685}, {"37", 3700}, {"36.855", 3686},
                                               {"3685", -1}, {"abc", -1}, {"36.8x", -1}, {"", -1}, {"29.9", -1} };
  int fails = 0;
  for (unsigned i = 0; i < sizeof v / sizeof v[0]; i++) {
    long n = parse_new(v[i].in), o = parse_old(v[i].in);
    int ok = n == v[i].want; fails += !ok;
    printf("%s mark oral %-7s -> stored %ld (want %ld; pre-fix atof gave %ld)\n", ok ? "PASS" : "FAIL", v[i].in, n, v[i].want, o);
  }
  printf("%s\n", fails ? "TEST_CMDPARSE: FAIL" : "TEST_CMDPARSE: PASS");
  return fails ? 1 : 0;
}
