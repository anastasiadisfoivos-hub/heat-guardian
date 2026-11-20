// =====================================================================
// Heat Guardian R4 PoC 05: wrist HR with hg_ppg (replaces SparkFun heartRate.h)
// ---------------------------------------------------------------------
// Same MAX30102 setup as test 06 (400 Hz / 4 averaged = 100 sps, IR-only
// would be ledMode 1; test 06 used 2 = red + IR). Prints once a second:
// HR, quality word, perfusion index, and the DWT cycles per sample.
// Wiring: only the MAX30102 on D4/D5 (see SETUP.md section 6), or the full chain.
// =====================================================================
#include <Adafruit_TinyUSB.h>
#include <Wire.h>
#include <MAX30105.h>
extern "C" {
#include "hg_ppg.h"
void dwt_enable(void);
}

MAX30105 ppg;
hg_ppg_t hr;
static const uint8_t LED_POWER = 0x1F;   // ~6 mA per LED: the bench value from test 06

static void i2cHighDrive() {
  NRF_P0->PIN_CNF[4] = (NRF_P0->PIN_CNF[4] & ~GPIO_PIN_CNF_DRIVE_Msk) | (GPIO_PIN_CNF_DRIVE_H0D1 << GPIO_PIN_CNF_DRIVE_Pos);
  NRF_P0->PIN_CNF[5] = (NRF_P0->PIN_CNF[5] & ~GPIO_PIN_CNF_DRIVE_Msk) | (GPIO_PIN_CNF_DRIVE_H0D1 << GPIO_PIN_CNF_DRIVE_Pos);
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) delay(10);
  Serial.println("Heat Guardian R4 PoC 05: hg_ppg wrist HR");
  Wire.begin(); i2cHighDrive(); Wire.setClock(100000);
  if (!ppg.begin(Wire, I2C_SPEED_STANDARD)) { Serial.println("MAX30102 not found"); while (1) delay(1000); }
  i2cHighDrive();
  // powerLevel, sampleAverage, ledMode (1 = IR only: halves LED current), sampleRate, pulseWidth, adcRange
  ppg.setup(LED_POWER, 4, 1, 400, 411, 4096);   // -> 100 sps on the IR channel
  hg_ppg_init(&hr);
  dwt_enable();
}

static const char* QWORD[] = { "NO_SKIN", "LOW_PI(loose)", "MOTION", "IRREGULAR", "OK" };

void loop() {
  static uint32_t lastPrint = 0, cyc = 0, n = 0, beats = 0;
  ppg.check();
  while (ppg.available()) {
    uint32_t ir = ppg.getFIFOIR();
    ppg.nextSample();
    uint32_t c0 = DWT->CYCCNT;
    beats += hg_ppg_push(&hr, ir, millis());
    cyc += DWT->CYCCNT - c0; n++;
  }
  if (millis() - lastPrint >= 1000) {
    lastPrint = millis();
    Serial.print("HR "); Serial.print(hr.hr_bpm, 1); Serial.print(" bpm  q="); Serial.print(QWORD[hr.quality]);
    Serial.print("  PI "); Serial.print(hr.pi_pct, 3); Serial.print("%  cv "); Serial.print(hr.ibi_cv, 2);
    Serial.print("  beats "); Serial.print(beats);
    Serial.print("  cycles/sample "); Serial.println(n ? cyc / n : 0);
    cyc = 0; n = 0;
  }
}
