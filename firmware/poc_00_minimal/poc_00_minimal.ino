// Heat Guardian R4 PoC 00: the smallest sketch on this core (USB Serial only).
// Baseline for measuring what each PoC adds in flash/RAM.
#include <Adafruit_TinyUSB.h>
static float x[24];
void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) delay(10);
  Serial.println("Heat Guardian R4 PoC 00: minimal");
  for (int i = 0; i < 24; i++) x[i] = 0.1f * (i - 12);
}
void loop() {
  float s = 0; for (int i = 0; i < 24; i++) s += x[i];
  Serial.print("sum "); Serial.println(s, 4);
  Serial.print(" "); Serial.print(s, 4); Serial.print(" "); Serial.print((uint32_t)s); Serial.println(" us");
  x[0] += 0.01f; delay(1000);
}
