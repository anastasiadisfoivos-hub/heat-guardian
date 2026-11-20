// Heat Guardian: copy of R4 poc_02_nn with the trained hg2 weights (32-24-16-6 x5), B2 compile/size/timing check.
// Files hg2_weights.c/.h and hg2_nn.c/.h are copied from model/export by model/hg2/fw_check.sh.
#include <Adafruit_TinyUSB.h>
extern "C" {
#include "hg2_nn.h"
void dwt_enable(void);
}
static float z[HG2_NN_IN];
void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) delay(10);
  Serial.println("Heat Guardian poc_02_hg2: hg2 NN timing");
  Serial.print("weights "); Serial.print(HG2_NN_VERSION);
  Serial.print(" crc "); Serial.println(hg2_nn_check_crc() ? "OK" : "MISMATCH");
  dwt_enable();
  for (int i = 0; i < HG2_NN_IN; i++) z[i] = 0.1f * (i - 16);
}
void loop() {
  float y[HG2_NN_OUT], mean[HG2_NN_OUT], sd[HG2_NN_OUT];
  uint32_t c0 = DWT->CYCCNT;
  hg2_nn_forward(&HG2_MEMBERS[0], z, y);
  uint32_t c1 = DWT->CYCCNT;
  hg2_nn_ensemble(z, mean, sd);
  uint32_t c2 = DWT->CYCCNT;
  Serial.print("1 member: "); Serial.print((c1 - c0) / 64.0f, 1); Serial.print(" us | ensemble x5: ");
  Serial.print((c2 - c1) / 64.0f, 1); Serial.print(" us | core_now ");
  Serial.println(mean[0] * HG2_Y_STD[0] + HG2_Y_MEAN[0], 3);
  z[0] += 0.001f;
  delay(1000);
}
