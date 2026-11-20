// =====================================================================
// Heat Guardian R4 PoC 02: plain-C MLP + 5-member ensemble on the XIAO nRF52840
// ---------------------------------------------------------------------
// Compiles hg_nn.c with the generated hg_weights.h (run export_weights.py
// first). On the board it prints, once a second:
//   - CRC check of the weights in flash (must say OK)
//   - cycles and microseconds for 1 member and for the 5-member ensemble
//     (measured with the Cortex-M4 DWT cycle counter, 64 MHz)
//   - cycles for the int8 member
// Compare with poc_00_minimal to get the NN's flash cost.
// =====================================================================
#include <Adafruit_TinyUSB.h>
extern "C" {
#include "hg_nn.h"
void dwt_enable(void);   // provided by the Seeed/Adafruit core (cores/nRF5/delay.c)
}

static float x[HG_NN_IN];

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) delay(10);
  Serial.println("Heat Guardian R4 PoC 02: NN timing");
  Serial.print("weights "); Serial.print(HG_NN_VERSION);
  Serial.print(" crc "); Serial.println(hg_nn_check_crc() ? "OK" : "MISMATCH");
  dwt_enable();
  for (int i = 0; i < HG_NN_IN; i++) x[i] = 0.1f * (i - 12);   // any z-scored looking input
}

void loop() {
  float y[HG_NN_OUT], mean[HG_NN_OUT], sd[HG_NN_OUT];
  int8_t xq[HG_NN_IN], yq[HG_NN_OUT];
  for (int i = 0; i < HG_NN_IN; i++) xq[i] = (int8_t)(x[i] / HG_NN_I8_SX);

  uint32_t c0 = DWT->CYCCNT;
  hg_nn_forward(&HG_NN_MEMBERS[0], x, y);
  uint32_t c1 = DWT->CYCCNT;
  hg_nn_ensemble(x, mean, sd);
  uint32_t c2 = DWT->CYCCNT;
  hg_nn_forward_i8_0(xq, yq);
  uint32_t c3 = DWT->CYCCNT;

  Serial.print("1 member: "); Serial.print(c1 - c0); Serial.print(" cycles = ");
  Serial.print((c1 - c0) / 64.0f, 1); Serial.print(" us | ensemble x5: ");
  Serial.print(c2 - c1); Serial.print(" cycles = "); Serial.print((c2 - c1) / 64.0f, 1);
  Serial.print(" us | int8 member: "); Serial.print(c3 - c2); Serial.print(" cycles = ");
  Serial.print((c3 - c2) / 64.0f, 1); Serial.println(" us");
  Serial.print("  y = "); Serial.print(y[0], 4); Serial.print(" "); Serial.print(y[1], 4); Serial.print(" "); Serial.print(y[2], 4);
  Serial.print(" | mean "); Serial.print(mean[0], 4); Serial.print(" std "); Serial.println(sd[0], 4);
  x[0] += 0.01f;  // stop the compiler from hoisting anything
  delay(1000);
}
