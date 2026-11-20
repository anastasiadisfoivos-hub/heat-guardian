// =====================================================================
// Heat Guardian R4 PoC 06: EVERYTHING in one build, to measure the real total
//   07_all_parts (screen, Greek font, haptics, TMP117 x2, SHTC3, ICM-20649)
// + MAX30102 via the SparkFun library + hg_ppg wrist HR detector (PoC 05)
// + Bluefruit BLE UART + battery service + advertising (PoC 01)
// + plain-C NN ensemble 5 x (24-32-16-3) with CRC check (PoC 02)
// + InternalFS save/load of the Body Twin file (PoC 03)
// + hardware watchdog (PoC 04)
// The loop runs the ensemble once a minute and feeds the watchdog once a loop.
// This is the number to compare with the 30 % flash budget (243 KB of 811 KB).
// =====================================================================
// (original header follows)
// Heat Guardian Band A - bench test 07: all parts together
// ---------------------------------------------------------------------
// Board : Seeed XIAO nRF52840 (plain), core "Seeed nRF52 Boards"
// Wiring: screen + button + Qwiic chain, exactly as in tests 01-05.
//         NOT the MAX30102 (test it alone with 06 first).
// Libraries: GFX Library for Arduino, U8g2, Adafruit DRV2605 Library,
//            Adafruit TMP117, Adafruit SHTC3 Library, Adafruit ICM20X
//
// What it does:
//   - The screen shows one of the six states (symbol + Greek label).
//   - SHORT press of the OK button -> next state. Its vibration plays.
//   - LONG press (1 s) -> replay the vibration of the current state.
//   - Serial Monitor: sensor line once a second (+ still-wrist flag).
//     Typing n = next state, r = replay, 0-5 = jump to that state.
//
// Power rule (independent review): the backlight never runs above 50%
// while the motor runs. The sketch drops it to 50% before every
// vibration and puts it back when the DRV2605L says it is finished.
// =====================================================================

#if !defined(ARDUINO_NRF52_ADAFRUIT) || !defined(ARDUINO_Seeed_XIAO_nRF52840)
#error "Wrong board. Pick Tools > Board > Seeed nRF52 Boards > Seeed XIAO nRF52840 (not mbed, not Sense)."
#endif

#include <Adafruit_TinyUSB.h>  // USB Serial on this core
#include <SPI.h>
#include <Wire.h>
#include <U8g2lib.h>            // must come BEFORE Arduino_GFX: turns on the Greek font support
#include <Arduino_GFX_Library.h>
#include <Adafruit_DRV2605.h>
#include <Adafruit_TMP117.h>
#include <Adafruit_SHTC3.h>
#include <Adafruit_ICM20649.h>
#include <bluefruit.h>          // R4: Bluefruit52Lib (ships with the Seeed nRF52 core)
#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>
#include <MAX30105.h>
#include <nrf_wdt.h>
extern "C" {
#include "hg_nn.h"
#include "hg_ppg.h"
#include "hg_guardian.h"
#include "hg2_weights.h"   // B5 Guardian Loop (guardian/c), compile check only
}
using namespace Adafruit_LittleFS_Namespace;

// ---- R4: PPG + NN + storage + watchdog ------------------------------------
extern uint16_t stillSec;
MAX30105 ppg; bool hasPpg = false;
hg_ppg_t hrDet;
struct __attribute__((packed)) TwinFile { uint32_t magic; uint16_t version, length; float p[5]; uint16_t days; uint8_t routine[62]; uint32_t save_count, crc32; };
TwinFile twin;
static uint32_t crc32b(const void* q, size_t n) { const uint8_t* b = (const uint8_t*)q; uint32_t c = ~0u; while (n--) { c ^= *b++; for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u))); } return ~c; }
static bool twinSave() { twin.magic = 0x57544748u; twin.version = 1; twin.length = sizeof twin; twin.save_count++; twin.crc32 = crc32b(&twin, sizeof twin - 4);
  File f(InternalFS); if (!f.open("/twin.bin", FILE_O_WRITE)) return false; f.seek(0); f.truncate(0); size_t n = f.write((const uint8_t*)&twin, sizeof twin); f.close(); return n == sizeof twin; }
static bool twinLoad() { File f(InternalFS); if (!f.open("/twin.bin", FILE_O_READ)) return false; size_t n = f.read((uint8_t*)&twin, sizeof twin); f.close();
  return n == sizeof twin && twin.magic == 0x57544748u && twin.crc32 == crc32b(&twin, sizeof twin - 4); }
static void wdtStart(uint32_t ms) { NRF_WDT->CONFIG = (WDT_CONFIG_HALT_Pause << WDT_CONFIG_HALT_Pos) | (WDT_CONFIG_SLEEP_Run << WDT_CONFIG_SLEEP_Pos);
  NRF_WDT->CRV = (uint32_t)(((uint64_t)ms * 32768u) / 1000u) - 1u; NRF_WDT->RREN = WDT_RREN_RR0_Msk; NRF_WDT->TASKS_START = 1; }
static inline void wdtFeed() { NRF_WDT->RR[0] = WDT_RR_RR_Reload; }
float nnIn[HG_NN_IN], nnMean[HG_NN_OUT], nnStd[HG_NN_OUT];
static hg_guardian_t G;            // ~3.5 KB, static (no malloc)
static hg_minute_t GM; static hg_minute_out_t GO;
static void guardianInit() {
  hg2_profile_t p = { 75.0f, 0.0f, 26.0f, 0 };
  hg2_twin_t tw; memset(&tw, 0, sizeof tw); tw.rest_hr = 70.0f; tw.k_person = 0.12f; tw.c_bodyheat = 0.15f;
  for (int h = 0; h < 24; h++) tw.t1_night_base[h] = NAN;
  hg_guardian_init(&G, &p, &tw);
  Serial.print("hg2 "); Serial.print(HG2_NN_VERSION); Serial.println(hg2_check_crc() ? " crc OK" : " crc MISMATCH");
}
static void runInference() {   // once per minute: the Guardian Loop (sensor wiring is B6's 09_guardian; here: HR + still only)
  nnIn[0] = hrDet.hr_bpm / 100.0f; nnIn[1] = stillSec / 60.0f; nnIn[2] = hrDet.pi_pct;
  hg_nn_ensemble(nnIn, nnMean, nnStd);
  memset(&GM, 0, sizeof GM);
  GM.s.t1_c = NAN; GM.s.t2_c = NAN; GM.s.t_air_c = NAN; GM.s.rh_pct = NAN;
  GM.s.hr_bpm = hrDet.hr_bpm > 0 ? hrDet.hr_bpm : NAN; GM.s.hr_quality = hrDet.quality; GM.s.pi_pct = hrDet.pi_pct;
  GM.s.a_std_g = stillSec > 0 ? 0.001f : 0.05f; GM.s.minute_of_day = 0xFFFF;
  for (int k = 0; k < 12; k++) { GM.t1_5s[k] = NAN; GM.t2_5s[k] = NAN; GM.tair_5s[k] = NAN; GM.zangle_5s[k] = NAN; }
  GM.vbat = 3.9f; GM.ble_bucket = -1; GM.force_worn = 0xFF; GM.ppg_dc = (uint32_t)hrDet.dc;
  uint32_t t0 = micros();
  hg_guardian_step(&G, &GM, &GO);
  uint32_t dt = micros() - t0;
  Serial.print("guardian state "); Serial.print(GO.state); Serial.print(" worn "); Serial.print(GO.worn);
  Serial.print(" us "); Serial.println(dt);
}

// ---- R4: BLE -------------------------------------------------------------
BLEUart bleuart;   // Nordic UART Service (6E400001-...)
BLEBas  blebas;    // Battery Service 0x180F
static void bleSetup() {
  Bluefruit.configPrphBandwidth(BANDWIDTH_LOW);   // 1 peripheral link, small buffers
  Bluefruit.begin(1, 0);                          // 1 peripheral, 0 central
  Bluefruit.setTxPower(0);                        // 0 dBm: enough for a phone in the same room
  Bluefruit.setName("HeatGuardian");
  bleuart.begin();
  blebas.begin(); blebas.write(100);
  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(bleuart);
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 1600);    // 20 ms fast for 30 s, then 1000 ms slow (units of 0.625 ms)
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);
}

// ---- pins ---------------------------------------------------------------
const int8_t LCD_DC   = D0;
const int8_t LCD_CS   = D9;   // D9 is the core's default MISO. MISO is moved to D6 so D9 stays an output.
const int8_t LCD_SCK  = D8;
const int8_t LCD_MOSI = D10;
const int8_t LCD_BL   = D3;
const int8_t SPI_DUMMY_MISO = D6;  // leave D6 unconnected
const int8_t LCD_RST  = D7;        // RST -> D7 (bench and final band)
const uint8_t PIN_BTN = D2;        // to GND, INPUT_PULLUP
// I2C: D4 = SDA, D5 = SCL (the core's default Wire)

const uint8_t LCD_ROTATION = 0;
#define USE_GREEK 1

// ---- power rule -----------------------------------------------------------
const uint8_t BL_NORMAL_PCT  = 60;   // brief: 60% normally
const uint8_t BL_WARNING_PCT = 100;  // brief: 100% during warnings
const uint8_t BL_MOTOR_MAX   = 50;   // review: never above 50% while the motor runs

// ---- still-wrist detector -------------------------------------------------
const float STILL_VAR_THRESHOLD = 0.005f;  // (m/s^2)^2, same as 02_sensors
const uint16_t STILL_SECONDS = 60;
const uint16_t IMU_HZ = 25;

Arduino_DataBus* bus = new Arduino_HWSPI(LCD_DC, LCD_CS, &SPI);
Arduino_GFX* gfx = new Arduino_ST7789(bus, LCD_RST, LCD_ROTATION, true /* IPS */,
                                      240, 280, 0, 20, 0, 20);
Adafruit_DRV2605 drv;
Adafruit_TMP117 tmpSkin, tmpRef;
Adafruit_SHTC3 shtc3;
Adafruit_ICM20649 imu;
bool hasDrv = false, hasSkin = false, hasRef = false, hasSht = false, hasImu = false;

#define C_BLACK  RGB565(0, 0, 0)
#define C_WHITE  RGB565(255, 255, 255)
#define C_GREEN  RGB565(0, 200, 70)
#define C_BLUE   RGB565(40, 140, 255)
#define C_ORANGE RGB565(255, 140, 0)
#define C_RED    RGB565(235, 30, 30)
#define C_YELLOW RGB565(255, 230, 0)

// ---- states -------------------------------------------------------------
enum State : uint8_t { ST_OK, ST_DRINK, ST_COOL, ST_DANGER, ST_IMOK, ST_BATTERY, ST_COUNT };
const char* LABEL_GR[ST_COUNT] = {
  "Όλα καλά", "Πιείτε νερό", "Πηγαίνετε σε δροσιά", "Κίνδυνος", "Λήφθηκε: Είμαι καλά", "Χαμηλή μπαταρία"
};
const char* LABEL_LAT[ST_COUNT] = {
  "Ola kala", "Pieite nero", "Pigainete se drosia", "Kindynos", "Lifthike: Eimai kala", "Chamili mpataria"
};
const char* STATE_NAME[ST_COUNT] = { "All OK", "Drink water", "Go somewhere cool", "Danger", "I'm OK received", "Battery low" };

// ---- drawing helpers ----------------------------------------------------
static void thickLine(float x0, float y0, float x1, float y1, float r, uint16_t c) {
  float dx = x1 - x0, dy = y1 - y0;
  float len = sqrtf(dx * dx + dy * dy);
  if (len < 0.5f) { gfx->fillCircle(x0, y0, r, c); return; }
  float nx = -dy / len * r, ny = dx / len * r;
  gfx->fillTriangle(x0 + nx, y0 + ny, x1 + nx, y1 + ny, x1 - nx, y1 - ny, c);
  gfx->fillTriangle(x0 + nx, y0 + ny, x1 - nx, y1 - ny, x0 - nx, y0 - ny, c);
  gfx->fillCircle(x0, y0, r, c);
  gfx->fillCircle(x1, y1, r, c);
}

static void drawCheck(int cx, int cy, int s, uint16_t c) {
  float r = s * 0.075f;
  thickLine(cx - 0.42f * s, cy + 0.02f * s, cx - 0.12f * s, cy + 0.32f * s, r, c);
  thickLine(cx - 0.12f * s, cy + 0.32f * s, cx + 0.44f * s, cy - 0.34f * s, r, c);
}

static void drawDrop(int cx, int cy, int s, uint16_t c) {
  int r = s * 0.32f;
  int ccy = cy + s * 0.16f;
  gfx->fillCircle(cx, ccy, r, c);
  gfx->fillTriangle(cx, cy - s * 0.50f, cx - r * 0.94f, ccy - r * 0.34f, cx + r * 0.94f, ccy - r * 0.34f, c);
  gfx->fillCircle(cx - r * 0.40f, ccy + r * 0.05f, r * 0.14f, C_WHITE);  // small shine
}

static void drawHouse(int cx, int cy, int s, uint16_t c) {
  int bx = cx - s * 0.36f, bw = s * 0.72f, by = cy - s * 0.05f, bh = s * 0.50f;
  gfx->fillRect(bx, by, bw, bh, c);
  gfx->fillTriangle(cx - s * 0.52f, by + 2, cx, cy - s * 0.50f, cx + s * 0.52f, by + 2, c);
  // white snowflake on the wall: "go somewhere cool"
  int fx = cx, fy = by + bh * 0.48f, fr = s * 0.15f;
  for (int k = 0; k < 3; k++) {
    float a = k * 3.14159f / 3.0f;
    thickLine(fx - fr * cosf(a), fy - fr * sinf(a), fx + fr * cosf(a), fy + fr * sinf(a), 2.5f, C_WHITE);
  }
}

static void drawWarning(int cx, int cy, int s, uint16_t c) {
  gfx->fillTriangle(cx, cy - s * 0.50f, cx - s * 0.54f, cy + s * 0.42f, cx + s * 0.54f, cy + s * 0.42f, c);
  int bw = s * 0.10f;
  gfx->fillRoundRect(cx - bw / 2, cy - s * 0.20f, bw, s * 0.36f, bw / 2, C_BLACK);
  gfx->fillCircle(cx, cy + s * 0.28f, s * 0.06f, C_BLACK);
}

static void drawCheckCircle(int cx, int cy, int s, uint16_t c) {
  gfx->fillCircle(cx, cy, s * 0.50f, c);
  gfx->fillCircle(cx, cy, s * 0.42f, C_BLACK);
  drawCheck(cx, cy, s * 0.62f, c);
}

static void drawBattery(int cx, int cy, int s, uint16_t outline, uint16_t bar) {
  int w = s * 0.86f, h = s * 0.46f, t = 6;
  int x = cx - w / 2 - s * 0.04f, y = cy - h / 2;
  gfx->fillRoundRect(x, y, w, h, 8, outline);
  gfx->fillRoundRect(x + t, y + t, w - 2 * t, h - 2 * t, 4, C_BLACK);
  gfx->fillRect(x + w, cy - h * 0.18f, s * 0.08f, h * 0.36f, outline);  // the + nub
  int inner = w - 2 * t - 8;
  gfx->fillRect(x + t + 4, y + t + 4, inner / 4, h - 2 * t - 8, bar);   // one red bar left
}

static uint16_t utf8Len(const char* s) {
  uint16_t n = 0;
  for (; *s; s++) if (((uint8_t)*s & 0xC0) != 0x80) n++;
  return n;
}

static void drawLabel(const char* txt, int baselineY) {
  // u8g2_font_10x20_t_greek: monospace, 10 px per character, ~20 px tall.
  uint16_t chars = utf8Len(txt);
  uint8_t size = (chars * 10 * 2 <= 232) ? 2 : 1;  // big text when it fits
  int w = chars * 10 * size;
  gfx->setFont(u8g2_font_10x20_t_greek);
  gfx->setUTF8Print(true);
  gfx->setTextSize(size);
  gfx->setTextColor(C_WHITE);
  gfx->setCursor((240 - w) / 2, baselineY + (size == 2 ? 10 : 0));
  gfx->print(txt);
  gfx->setTextSize(1);
}

static void drawState(uint8_t st) {
  const int cx = 120, cy = 112, s = 150;
  gfx->fillScreen(C_BLACK);
  switch (st) {
    case ST_OK:      drawCheck(cx, cy, s, C_GREEN); break;
    case ST_DRINK:   drawDrop(cx, cy, s, C_BLUE); break;
    case ST_COOL:    drawHouse(cx, cy, s, C_ORANGE); break;
    case ST_DANGER:  drawWarning(cx, cy, s, C_RED); break;
    case ST_IMOK:    drawCheckCircle(cx, cy, s, C_GREEN); break;
    case ST_BATTERY: drawBattery(cx, cy, s, C_WHITE, C_RED); break;
  }
  drawLabel(USE_GREEK ? LABEL_GR[st] : LABEL_LAT[st], 235);
}


// ---- vibration patterns (DRV2605L ERM library effect IDs) -----------------
// 0x80 | n = a pause of n x 10 ms inside the sequence. 0 ends it. Max 8 slots.
#define WAIT10MS(n) (0x80 | (n))
const uint8_t PATTERN[ST_COUNT][8] = {
  { 2, 0 },                                         // All OK: soft tick (Strong Click 60%)
  { 10, WAIT10MS(10), 10, 0 },                      // Drink: double click x2
  { 15, WAIT10MS(30), 15, WAIT10MS(30), 15, 0 },    // Cool: 750 ms alert x3, 300 ms gaps
  { 16, 52, 0 },                                    // Danger: 1000 ms alert + pulsing strong
  { 50, 0 },                                        // I'm OK: soft buzz (Buzz 40%)
  { 12, 0 },                                        // Battery low: triple click
};
const bool IS_WARNING[ST_COUNT] = { false, true, true, true, false, true };

uint8_t state = ST_OK;
uint8_t blTarget = BL_NORMAL_PCT;
bool motorBusy = false;
uint32_t motorStart = 0;

static void hgBoot() {
  pinMode(VBAT_ENABLE, OUTPUT);  // review rule: P0.14 LOW at boot
  digitalWrite(VBAT_ENABLE, LOW);
  pinMode(LCD_BL, OUTPUT);
  digitalWrite(LCD_BL, LOW);
}

// The ONLY function that writes the backlight. It enforces the power rule.
static void applyBacklight() {
  uint8_t pct = blTarget;
  if (motorBusy && pct > BL_MOTOR_MAX) pct = BL_MOTOR_MAX;
  analogWrite(LCD_BL, (uint16_t)pct * 255 / 100);
}

static void startPattern(uint8_t st) {
  if (!hasDrv) return;
  motorBusy = true;
  applyBacklight();               // dim FIRST, then start the motor
  uint8_t i = 0;
  for (; i < 8 && PATTERN[st][i]; i++) drv.setWaveform(i, PATTERN[st][i]);
  if (i < 8) drv.setWaveform(i, 0);
  drv.go();
  motorStart = millis();
  Serial.print("  vibration: state "); Serial.println(st);
}

static void serviceMotor() {
  if (!motorBusy) return;
  static uint32_t lastPoll = 0;
  if (millis() - lastPoll < 20) return;
  lastPoll = millis();
  bool playing = drv.readRegister8(DRV2605_REG_GO) & 0x01;
  if (!playing || millis() - motorStart > 5000) {
    if (playing) drv.stop();
    motorBusy = false;
    applyBacklight();             // motor is off: back to the full target
  }
}

static void enterState(uint8_t st, bool vibrate) {
  state = st % ST_COUNT;
  blTarget = IS_WARNING[state] ? BL_WARNING_PCT : BL_NORMAL_PCT;
  Serial.print("STATE -> "); Serial.print(state); Serial.print(" "); Serial.println(STATE_NAME[state]);
  if (vibrate) startPattern(state);   // sets the 50% cap before anything else
  applyBacklight();
  drawState(state);
}

// ---- button ---------------------------------------------------------------
static void serviceButton() {
  static bool stable = false, lastRaw = false, longSent = false;
  static uint32_t rawChanged = 0, pressedAt = 0;
  uint32_t now = millis();
  bool raw = (digitalRead(PIN_BTN) == LOW);
  if (raw != lastRaw) { lastRaw = raw; rawChanged = now; }
  if (raw != stable && now - rawChanged >= 30) {
    stable = raw;
    if (stable) { pressedAt = now; longSent = false; }
    else if (!longSent) { Serial.println("button: SHORT"); enterState(state + 1, true); }
  }
  if (stable && !longSent && now - pressedAt >= 1000) {
    longSent = true;
    Serial.println("button: LONG (replay)");
    startPattern(state);
  }
}

// ---- sensors --------------------------------------------------------------
float accSum = 0, accSumSq = 0, lastMag = 0, lastVar = -1;
uint16_t accN = 0, stillSec = 0;

static void sampleImu() {
  if (!hasImu) return;
  sensors_event_t a, g, t;
  if (!imu.getEvent(&a, &g, &t)) return;
  float m = sqrtf(a.acceleration.x * a.acceleration.x + a.acceleration.y * a.acceleration.y +
                  a.acceleration.z * a.acceleration.z);
  lastMag = m; accSum += m; accSumSq += m * m; accN++;
}

static void printSensors(uint32_t now) {
  if (hasImu && accN >= 5) {
    float mean = accSum / accN;
    float var = accSumSq / accN - mean * mean;
    if (var < 0) var = 0;
    lastVar = var;
    if (var < STILL_VAR_THRESHOLD) { if (stillSec < 65000) stillSec++; } else stillSec = 0;
  } else { lastVar = -1; stillSec = 0; }
  accSum = accSumSq = 0; accN = 0;

  sensors_event_t e, hum;
  Serial.print("t="); Serial.print(now / 1000); Serial.print("s | skin ");
  if (hasSkin) { tmpSkin.getEvent(&e); Serial.print(e.temperature, 2); Serial.print("C"); } else Serial.print("---");
  Serial.print(" | ref ");
  if (hasRef) { tmpRef.getEvent(&e); Serial.print(e.temperature, 2); Serial.print("C"); } else Serial.print("---");
  Serial.print(" | air ");
  if (hasSht) { shtc3.getEvent(&hum, &e); Serial.print(e.temperature, 1); Serial.print("C ");
                Serial.print(hum.relative_humidity, 0); Serial.print("%RH"); } else Serial.print("---");
  Serial.print(" | acc ");
  if (lastVar >= 0) {
    Serial.print(lastMag, 2); Serial.print(" var "); Serial.print(lastVar, 5);
    Serial.print(" | still ");
    if (stillSec >= STILL_SECONDS) Serial.print("YES");
    else { Serial.print(stillSec); Serial.print("/"); Serial.print(STILL_SECONDS); Serial.print("s"); }
  } else Serial.print("---");
  Serial.print(" | state "); Serial.print(state);
  Serial.print(" bl "); Serial.print(motorBusy && blTarget > BL_MOTOR_MAX ? BL_MOTOR_MAX : blTarget); Serial.println("%");
  // R4: same numbers over BLE UART (text for now; the binary frame is specified in R4 section 5)
  if (Bluefruit.connected()) {
    char line[48];
    snprintf(line, sizeof line, "t=%lu st=%u still=%u\n", (unsigned long)(now / 1000), state, stillSec);
    bleuart.write((const uint8_t*)line, strlen(line));
  }
}

// High drive (H0D1) on D4 SDA / D5 SCL. The bus pull-ups sink more current than the
// nRF52840's standard drive guarantees (PARTS_REFERENCE.md, I2C bus section).
// Call it right after Wire.begin() AND again after the sensor libraries' begin():
// those call Wire.begin() inside, and Wire.begin() puts the pins back to standard drive.
static void i2cHighDrive() {
  NRF_P0->PIN_CNF[4] = (NRF_P0->PIN_CNF[4] & ~GPIO_PIN_CNF_DRIVE_Msk) | (GPIO_PIN_CNF_DRIVE_H0D1 << GPIO_PIN_CNF_DRIVE_Pos);  // D4 SDA
  NRF_P0->PIN_CNF[5] = (NRF_P0->PIN_CNF[5] & ~GPIO_PIN_CNF_DRIVE_Msk) | (GPIO_PIN_CNF_DRIVE_H0D1 << GPIO_PIN_CNF_DRIVE_Pos);  // D5 SCL
}

void setup() {
  hgBoot();
  pinMode(PIN_BTN, INPUT_PULLUP);
  Serial.begin(115200);
  while (!Serial && millis() < 3000) delay(10);
  Serial.println();
  Serial.println("Heat Guardian bench test 07: all parts");

  Wire.begin();
  i2cHighDrive();
  Wire.setClock(100000);
  hasDrv = drv.begin(&Wire);
  if (hasDrv) { drv.useERM(); drv.selectLibrary(2); drv.setMode(DRV2605_MODE_INTTRIG); }
  hasSkin = tmpSkin.begin(0x48, &Wire);
  hasRef  = tmpRef.begin(0x49, &Wire);
  hasSht  = shtc3.begin(&Wire);
  hasImu  = imu.begin_I2C(0x68, &Wire) || imu.begin_I2C(0x69, &Wire);
  hasPpg  = ppg.begin(Wire, I2C_SPEED_STANDARD);
  if (hasPpg) ppg.setup(0x1F, 4, 1, 400, 411, 4096);   // IR only, 100 sps
  hg_ppg_init(&hrDet);
  guardianInit();
  if (hasImu) { imu.setAccelRange(ICM20649_ACCEL_RANGE_4_G); imu.setGyroRange(ICM20649_GYRO_RANGE_500_DPS); }
  i2cHighDrive();  // again: the library begin() calls reset the drive

  Serial.print("DRV2605L "); Serial.print(hasDrv ? "OK" : "missing");
  Serial.print(" | TMP117 0x48 "); Serial.print(hasSkin ? "OK" : "missing");
  Serial.print(" | TMP117 0x49 "); Serial.print(hasRef ? "OK" : "missing");
  Serial.print(" | SHTC3 "); Serial.print(hasSht ? "OK" : "missing");
  Serial.print(" | ICM-20649 "); Serial.println(hasImu ? "OK" : "missing");

  SPI.setPins(SPI_DUMMY_MISO, LCD_SCK, LCD_MOSI);  // keep D9 (CS) an output
  // SPI mode 0 fix (found in test 04c): the library picks mode 2 on this core,
  // which the ST7789 misreads. Start the bus ourselves, then skip it in gfx.
  if (!bus->begin(8000000, SPI_MODE0)) Serial.println("bus->begin() failed");
  if (!gfx->begin(GFX_SKIP_DATABUS_BEGIN)) Serial.println("gfx->begin() failed");
  gfx->fillScreen(RGB565(0, 0, 0));

  bleSetup();      // R4
  InternalFS.begin();
  if (!twinLoad()) { memset(&twin, 0, sizeof twin); twin.p[2] = 65.0f; twinSave(); }
  Serial.print("twin saves="); Serial.print(twin.save_count);
  Serial.print(" | NN "); Serial.print(HG_NN_VERSION); Serial.println(hg_nn_check_crc() ? " crc OK" : " crc MISMATCH");
  enterState(ST_OK, true);
  wdtStart(8000);
  Serial.println("Short press = next state, long press = replay. Serial: n, r, 0-5.");
}

void loop() {
  static uint32_t nextSample = 0, nextPrint = 1000, nextInfer = 60000;
  uint32_t now = millis();
  wdtFeed();
  if (hasPpg) { ppg.check(); while (ppg.available()) { hg_ppg_set_motion(&hrDet, stillSec == 0); hg_ppg_push(&hrDet, ppg.getFIFOIR(), millis()); ppg.nextSample(); } }
  if ((int32_t)(now - nextInfer) >= 0) { nextInfer += 60000; runInference(); }
  static uint32_t nextSave = 86400000UL;                       // Body Twin save ONCE A DAY (flash wear, R4 A3)
  if ((int32_t)(now - nextSave) >= 0) { nextSave += 86400000UL; twinSave(); }

  serviceButton();
  serviceMotor();

  if ((int32_t)(now - nextSample) >= 0) { nextSample = now + 1000 / IMU_HZ; sampleImu(); }
  if ((int32_t)(now - nextPrint) >= 0) { nextPrint += 1000; printSensors(now); }

  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'n' || c == 'N') enterState(state + 1, true);
    else if (c == 'r' || c == 'R') startPattern(state);
    else if (c >= '0' && c <= '5') enterState(c - '0', true);
  }
}
