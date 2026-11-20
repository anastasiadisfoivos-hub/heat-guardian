// [T3] tester hook (C++ translation unit, like the sketch)
#include <Arduino.h>
#include "hg_twin.h"

// [T3] tester hook: exercise every hg_twin entry point so nothing is dead-stripped
static hg2_twin_t t3Twin; static hg_twin_acc_t t3Acc; static uint8_t t3Buf[900]; static uint8_t t3Rout[650];
extern "C" void t3TwinBoot() {
  hg_twin_defaults(&t3Twin); hg_twin_acc_init(&t3Acc);
  uint16_t rl = 0; uint32_t sc = 0;
  int n = hg_twin_pack(&t3Twin, &t3Acc, t3Rout, 650, 1, t3Buf, sizeof t3Buf);
  if (n > 0 && hg_twin_unpack(t3Buf, (uint16_t)n, &t3Twin, &t3Acc, t3Rout, 650, &rl, &sc) != 0) hg_twin_defaults(&t3Twin);
  Serial.print("twin file "); Serial.println(n);
}
extern "C" void t3TwinMinute(float t1, float t2, float tair, float hr, float astd, uint16_t tod) {
  hg2_in_t in = {t1, t2, tair, 50.0f, hr, 4, 0.7f, astd, 2, tod};
  hg_twin_note_tier(&t3Acc, 0); hg_twin_set_air_ref(&t3Acc, NAN);
  hg_twin_ingest_minute(&t3Acc, &in, tod < 420, 0, 1);
  hg_twin_ingest_room_reading(&t3Acc, 25.0f, tair, t1);
  if (tod == 560) { hg_twin_ingest_reading(&t3Acc, 36.9f, t1, t1 - t2, 36.8f, 1); hg_twin_commit_reading(&t3Twin, &t3Acc); }
  if (tod == 420 && hg_twin_nightly_update(&t3Twin, &t3Acc)) Serial.println(t3Twin.rest_hr);
}
