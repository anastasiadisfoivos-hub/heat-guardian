// =====================================================================
// Heat Guardian Band A - 08_logger: the wear-test recorder (Nov 16-18 2026)
// ---------------------------------------------------------------------
// Board : Seeed XIAO nRF52840 (plain), core "Seeed nRF52 Boards" 1.1.13
// Wiring: EXACTLY as 07_all_parts (pin map unchanged) + MAX30102 on the I2C bus.
// Libraries: GFX Library for Arduino, U8g2, Adafruit DRV2605, Adafruit ICM20X,
//            SparkFun MAX3010x (+ the core's Bluefruit52Lib, Adafruit_LittleFS,
//            Adafruit_SPIFlash). TMP117 and SHTC3 are driven with plain I2C here.
//
// What it does (nothing clever, by design):
//   - every second: one 24-byte record (log_format.h) with skin/ref/air temperature,
//     humidity, heart rate + quality + perfusion index, motion, z-angle, flags, marker
//   - writes it to the 2 MB QSPI flash (LittleFS, /log/sNNNN.bin, one file per hour,
//     last 20 hours kept) and a 1-minute summary to /log/min.bin for the whole test
//   - sends it as a 48-hex-character line over BLE UART and USB serial
//   - commands (USB serial or BLE UART): help stat time mark dump dumpmin raw erase ...
//   - button: short press = marker 9 "button", long press (2 s) = marker 8 "help";
//     both vibrate and wake the screen for 15 s; otherwise the screen sleeps
//
// Rules carried over (SETUP.md lessons, R4): SPI mode 0 for the ST7789; I2C high drive
// after every library begin(); never analogRead D4/D5; ICM-20649 gyro OFF, accel-only
// low power 25 Hz; TMP117 one-shot only; watchdog 8 s fed only in loop(); Serial wait
// bounded (3 s); backlight <= 50 % while the motor runs; QSPI flash in deep power-down
// whenever no file is being written.
// =====================================================================

#if !defined(ARDUINO_NRF52_ADAFRUIT) || !defined(ARDUINO_Seeed_XIAO_nRF52840)
#error "Wrong board. Pick Tools > Board > Seeed nRF52 Boards > Seeed XIAO nRF52840 (not mbed, not Sense)."
#endif

#include "hg_nofastmath.h"   // FIRST: the core builds with -Ofast; NaN must stay NaN (see the header)
#include "hg_astd.h"         // the whole-minute a_std, one implementation with 09 (hg_fw.c)
#include <Adafruit_TinyUSB.h>   // USB Serial on this core
#include <SPI.h>
#include <U8g2lib.h>             // must come BEFORE Arduino_GFX: turns on the Greek font support
#include <Arduino_GFX_Library.h>
#include <bluefruit.h>
#include <Adafruit_LittleFS.h>
#include <Adafruit_SPIFlashBase.h>
#include <nrf_wdt.h>
#include <stdarg.h>
extern "C" {
#include "hg_ppg.h"
#include "log_format.h"
#include "log_ring.h"
#include "hg_i2c.h"
}
using namespace Adafruit_LittleFS_Namespace;

#ifndef HG_DCDC
#define HG_DCDC 1               // DC/DC on (Zephyr's xiao_ble board file boots in DC/DC mode; T6a R1). 0 = LDO only
#endif
#ifndef HG_FLASH_DPD
#define HG_FLASH_DPD 1          // 1 = flash chip in deep power-down (0xB9) between writes. 0 = bench variant: never sent
#endif
#if HG_DCDC
#define HG_V_DCDC ""
#else
#define HG_V_DCDC "-nodcdc"
#endif
#if HG_FLASH_DPD
#define HG_V_DPD ""
#else
#define HG_V_DPD "-nodpd"
#endif
#define HG_FW_VERSION "08-logger-1.1.5" HG_V_DCDC HG_V_DPD
#define HG_FW_SHORT   "1.1.5"

// ---- pins (unchanged from 07) ---------------------------------------------
const int8_t LCD_DC   = D0;
const int8_t LCD_CS   = D9;
const int8_t LCD_SCK  = D8;
const int8_t LCD_MOSI = D10;
const int8_t LCD_BL   = D3;
const int8_t SPI_DUMMY_MISO = D6;  // leave D6 unconnected
const int8_t LCD_RST  = D7;
const uint8_t PIN_BTN = D2;        // to GND, INPUT_PULLUP
const uint8_t PIN_NCHG = 23;       // D23 = P0.17, BQ25100 ~CHG (LOW while charging)
// I2C: D4 = SDA, D5 = SCL

// ---- tuning ---------------------------------------------------------------
const uint8_t  BL_NORMAL_PCT = 60, BL_MOTOR_MAX = 50, BL_LOWBAT_PCT = 20;
const uint32_t SCREEN_ON_MS = 15000;
const uint32_t LONG_PRESS_MS = 2000;
const uint16_t IMU_PERIOD_MS = 40;            // 25 Hz
const float    MOTION_STD_G = 0.0072f;        // 07's still threshold (var 0.005 (m/s^2)^2) -> moving for hg_ppg
const float    IMPACT_G = 2.0f;
const uint32_t TMP_PERIOD_MS = 5000, TMP_CONV_MS = 200;   // one-shot 8x avg = 125 ms typ
const uint32_t SHT_PERIOD_MS = 10000, SHT_CONV_MS = 20;   // normal mode 12.1 ms max
const uint32_t AFTER_BUZZ_MS = 2000;           // no temperature reading < 2 s after a buzz (R4 A8.5)
const float    VBAT_CHARGE_ME = 3.45f, VBAT_RESUME = 3.55f, VBAT_SOFT = 3.50f, VBAT_PPG_OFF = 3.35f;
const uint8_t  PPG_LED_PA = 0x1F;              // ~6 mA, the bench value of test 06
const uint16_t RAW_BLOCK_N = 100;              // raw capture: 1 s of IR per block

// ---- display --------------------------------------------------------------
Arduino_DataBus* bus = new Arduino_HWSPI(LCD_DC, LCD_CS, &SPI);
Arduino_GFX* gfx = new Arduino_ST7789(bus, LCD_RST, 0, true /* IPS */, 240, 280, 0, 20, 0, 20);
#define C_BLACK  RGB565(0, 0, 0)
#define C_WHITE  RGB565(255, 255, 255)
#define C_GREEN  RGB565(0, 200, 70)
#define C_ORANGE RGB565(255, 140, 0)
#define C_RED    RGB565(235, 30, 30)
#define C_GREY   RGB565(150, 150, 150)

// ---- devices (all I2C through hg_i2c: bounded, no Wire, no sensor libraries) ----
hg_ppg_t hrDet;
BLEUart bleuart;
BLEBas  blebas;
BLEDis  bledis;
bool hasDrv = false, hasSkin = false, hasRef = false, hasSht = false, hasImu = false, hasPpg = false;
uint8_t imuAddr = 0x68;
bool imuLowPower = false;

// =====================================================================
// small helpers: output channels
// =====================================================================
enum { CH_USB = 1, CH_BLE = 2 };
static uint32_t usbDrops = 0, bleDrops = 0;
static bool liveUsb = true;

// BLE TX queue: everything for BLE goes through it, drained <= 2 packets per loop pass
static uint8_t bleQ[2048];
static uint16_t bleQHead = 0, bleQTail = 0;
static uint16_t bleQCount() { return (uint16_t)((bleQHead - bleQTail) & (sizeof bleQ - 1)); }
static uint16_t bleQFree() { return (uint16_t)(sizeof bleQ - 1 - bleQCount()); }
static bool bleReady() { return Bluefruit.connected() && bleuart.notifyEnabled(); }
static void bleQPut(const char* s, uint16_t n) {
  if (!bleReady()) return;
  if (n > bleQFree()) { bleDrops++; return; }
  for (uint16_t i = 0; i < n; i++) { bleQ[bleQHead] = (uint8_t)s[i]; bleQHead = (bleQHead + 1) & (sizeof bleQ - 1); }
}
static void bleService() {
  if (!bleReady()) { bleQHead = bleQTail = 0; return; }
  for (int k = 0; k < 2 && bleQCount(); k++) {
    uint8_t pkt[20]; uint16_t n = 0;
    while (n < 20 && bleQCount()) { pkt[n++] = bleQ[bleQTail]; bleQTail = (bleQTail + 1) & (sizeof bleQ - 1); }
    bleuart.write(pkt, n);   // one notification; may wait <= 100 ms for a TX buffer (BLE_GENERIC_TIMEOUT)
  }
}

// USB: never block. Write only what the CDC buffer can take right now (drop + count otherwise).
static bool usbPut(const char* s, uint16_t n) {
  if (!Serial || n > 250) return false;            // CDC TX buffer is 256 B (tusb_config_nrf.h)
  uint32_t t0 = millis();
  while (Serial && Serial.availableForWrite() < (int)n && millis() - t0 < 10) yield();   // <= 10 ms
  if (!Serial || Serial.availableForWrite() < (int)n) { usbDrops++; return false; }
  Serial.write((const uint8_t*)s, n);
  return true;
}
static void outLine(uint8_t ch, const char* s) {
  uint16_t n = strlen(s);
  if (ch & CH_USB) usbPut(s, n);
  if (ch & CH_BLE) bleQPut(s, n);
}
static void outf(uint8_t ch, const char* fmt, ...) {
  char buf[192];
  va_list ap; va_start(ap, fmt); vsnprintf(buf, sizeof buf, fmt, ap); va_end(ap);
  outLine(ch, buf);
}
// Longer replies (stat, help) to USB: wait a little for buffer space instead of dropping.
static void usbReply(const char* s) {
  if (!Serial) return;
  uint16_t n = strlen(s);
  uint32_t t0 = millis();
  while (Serial && Serial.availableForWrite() < (int)n && millis() - t0 < 50) yield();
  if (n <= 250) usbPut(s, n);
}
static void replyf(uint8_t ch, const char* fmt, ...) {
  char buf[192];
  va_list ap; va_start(ap, fmt); vsnprintf(buf, sizeof buf, fmt, ap); va_end(ap);
  if (ch & CH_USB) usbReply(buf);
  if (ch & CH_BLE) bleQPut(buf, strlen(buf));
}

// =====================================================================
// reset reason, watchdog, battery, charging, time
// =====================================================================
static uint32_t resetReason = 0;
static void wdtStart(uint32_t ms) {
  NRF_WDT->CONFIG = (WDT_CONFIG_HALT_Pause << WDT_CONFIG_HALT_Pos) | (WDT_CONFIG_SLEEP_Run << WDT_CONFIG_SLEEP_Pos);
  NRF_WDT->CRV = (uint32_t)(((uint64_t)ms * 32768u) / 1000u) - 1u;
  NRF_WDT->RREN = WDT_RREN_RR0_Msk;
  NRF_WDT->TASKS_START = 1;
}
static inline void wdtFeed() { NRF_WDT->RR[0] = WDT_RR_RR_Reload; }
static const char* resetName(uint32_t rr) {
  if (rr & POWER_RESETREAS_DOG_Msk) return "WATCHDOG";
  if (rr & POWER_RESETREAS_RESETPIN_Msk) return "RESET-PIN";
  if (rr & POWER_RESETREAS_SREQ_Msk) return "SOFTWARE(upload)";
  if (rr & POWER_RESETREAS_LOCKUP_Msk) return "LOCKUP";
  if (rr & (POWER_RESETREAS_OFF_Msk | POWER_RESETREAS_VBUS_Msk)) return "WAKE";
  return "POWER-ON/BROWN-OUT";
}

// VBAT on P0.31 (AIN7) through the XIAO's 1M/510k divider, enabled by P0.14 LOW.
// The core's analogRead() uses a 3 us acquisition time, too short for a ~340 kOhm source
// (nRF52840 PS SAADC table: 3 us <= 10 kOhm, 40 us <= 800 kOhm), so read it here with 40 us.
static float vbat = NAN;
static float readVbat() {
  NRF_SAADC->RESOLUTION = SAADC_RESOLUTION_VAL_12bit;
  NRF_SAADC->OVERSAMPLE = SAADC_OVERSAMPLE_OVERSAMPLE_Over4x;
  NRF_SAADC->ENABLE = SAADC_ENABLE_ENABLE_Enabled;
  for (int i = 0; i < 8; i++) { NRF_SAADC->CH[i].PSELP = SAADC_CH_PSELP_PSELP_NC; NRF_SAADC->CH[i].PSELN = SAADC_CH_PSELN_PSELN_NC; }
  NRF_SAADC->CH[0].CONFIG = (SAADC_CH_CONFIG_GAIN_Gain1_6 << SAADC_CH_CONFIG_GAIN_Pos) |
                            (SAADC_CH_CONFIG_REFSEL_Internal << SAADC_CH_CONFIG_REFSEL_Pos) |
                            (SAADC_CH_CONFIG_TACQ_40us << SAADC_CH_CONFIG_TACQ_Pos) |
                            (SAADC_CH_CONFIG_MODE_SE << SAADC_CH_CONFIG_MODE_Pos) |
                            (SAADC_CH_CONFIG_BURST_Enabled << SAADC_CH_CONFIG_BURST_Pos);
  NRF_SAADC->CH[0].PSELP = SAADC_CH_PSELP_PSELP_AnalogInput7;   // P0.31 = VBAT. Never an I2C pin.
  volatile int16_t v = 0;
  NRF_SAADC->RESULT.PTR = (uint32_t)&v;
  NRF_SAADC->RESULT.MAXCNT = 1;
  NRF_SAADC->EVENTS_STARTED = 0; NRF_SAADC->EVENTS_END = 0; NRF_SAADC->EVENTS_STOPPED = 0;
  NRF_SAADC->TASKS_START = 1;
  uint32_t t0 = micros();
  while (!NRF_SAADC->EVENTS_STARTED && micros() - t0 < 2000) {}
  NRF_SAADC->EVENTS_STARTED = 0;
  NRF_SAADC->TASKS_SAMPLE = 1;
  while (!NRF_SAADC->EVENTS_END && micros() - t0 < 4000) {}
  bool ok = NRF_SAADC->EVENTS_END;
  NRF_SAADC->EVENTS_END = 0;
  NRF_SAADC->TASKS_STOP = 1;
  while (!NRF_SAADC->EVENTS_STOPPED && micros() - t0 < 6000) {}
  NRF_SAADC->EVENTS_STOPPED = 0;
  NRF_SAADC->CH[0].PSELP = SAADC_CH_PSELP_PSELP_NC;            // release the pin
  NRF_SAADC->OVERSAMPLE = 0;
  NRF_SAADC->ENABLE = SAADC_ENABLE_ENABLE_Disabled;
  if (!ok) return NAN;
  int16_t raw = v < 0 ? 0 : v;
  return raw * (3.6f / 4096.0f) * (1510.0f / 510.0f);
}
static bool vbusPresent() {
  uint32_t st = 0;
  uint8_t sd = 0; sd_softdevice_is_enabled(&sd);
  if (sd) sd_power_usbregstatus_get(&st); else st = NRF_POWER->USBREGSTATUS;
  return st & POWER_USBREGSTATUS_VBUSDETECT_Msk;
}
static bool charging() { return vbusPresent() || digitalRead(PIN_NCHG) == LOW; }
static uint8_t batteryPct(float v) {   // rough LiPo resting curve, display only
  if (!(v == v)) return 0;
  static const float V[] = {3.30f, 3.50f, 3.60f, 3.70f, 3.75f, 3.80f, 3.90f, 4.00f, 4.10f, 4.20f};
  static const uint8_t P[] = {0, 5, 10, 20, 35, 50, 65, 80, 92, 100};
  if (v <= V[0]) return 0;
  for (int i = 1; i < 10; i++) if (v < V[i]) return P[i - 1] + (uint8_t)((P[i] - P[i - 1]) * (v - V[i - 1]) / (V[i] - V[i - 1]));
  return 100;
}

static bool timeValid = false;
static uint32_t epochAtSync = 0, msAtSync = 0;
static uint32_t nowUnix() { return timeValid ? epochAtSync + (millis() - msAtSync) / 1000u : 0; }

static uint32_t bootCount = 0;
static bool lowBatMode = false;     // "charge me": no PPG, no motor, screen dim; logging continues

// =====================================================================
// I2C: every transfer goes through hg_i2c.c (TWIM0, deadline per transfer, bus clear on a hang).
// A device that fails 3 transfers in a row is marked missing and re-probed once a minute.
// =====================================================================
extern "C" uint32_t hg_i2c_micros(void) { return micros(); }
extern "C" void hg_i2c_poll_hook(void) {}
static void i2cPins() {   // input buffer on, pull-up, HIGH drive (H0D1, SETUP.md / 07)
  uint32_t cnf = (GPIO_PIN_CNF_DIR_Input << GPIO_PIN_CNF_DIR_Pos) | (GPIO_PIN_CNF_INPUT_Connect << GPIO_PIN_CNF_INPUT_Pos) |
                 (GPIO_PIN_CNF_PULL_Pullup << GPIO_PIN_CNF_PULL_Pos) | (GPIO_PIN_CNF_DRIVE_H0D1 << GPIO_PIN_CNF_DRIVE_Pos);
  NRF_P0->PIN_CNF[4] = cnf;   // D4 SDA (P0.04)
  NRF_P0->PIN_CNF[5] = cnf;   // D5 SCL (P0.05)
}
static bool i2cLinesHigh() { return (NRF_P0->IN & (1u << 4)) && (NRF_P0->IN & (1u << 5)); }
// 9 SCL pulses with SDA released, then a STOP: frees a slave that was left holding SDA low
extern "C" void hg_i2c_bus_clear(void) {
  NRF_P0->OUTSET = (1u << 4) | (1u << 5);
  NRF_P0->PIN_CNF[5] = (GPIO_PIN_CNF_DIR_Output << GPIO_PIN_CNF_DIR_Pos) | (GPIO_PIN_CNF_INPUT_Connect << GPIO_PIN_CNF_INPUT_Pos) |
                       (GPIO_PIN_CNF_PULL_Pullup << GPIO_PIN_CNF_PULL_Pos) | (GPIO_PIN_CNF_DRIVE_H0D1 << GPIO_PIN_CNF_DRIVE_Pos);
  for (int i = 0; i < 9; i++) { NRF_P0->OUTCLR = 1u << 5; delayMicroseconds(5); NRF_P0->OUTSET = 1u << 5; delayMicroseconds(5); }
  NRF_P0->PIN_CNF[4] = NRF_P0->PIN_CNF[5];                    // SDA output: low then high while SCL high = STOP
  NRF_P0->OUTCLR = 1u << 4; delayMicroseconds(5); NRF_P0->OUTSET = 1u << 4; delayMicroseconds(5);
  i2cPins();
}
static bool i2cWrite(uint8_t addr, const uint8_t* d, uint8_t n) { return hg_i2c_write(addr, d, n) == HG_I2C_OK; }
static bool i2cWriteReg8(uint8_t addr, uint8_t reg, uint8_t v) { uint8_t b[2] = {reg, v}; return i2cWrite(addr, b, 2); }
static bool i2cReadReg(uint8_t addr, uint8_t reg, uint8_t* d, uint8_t n) { return hg_i2c_write_read(addr, &reg, 1, d, n) == HG_I2C_OK; }
static bool i2cRead(uint8_t addr, uint8_t* d, uint8_t n) { return hg_i2c_read(addr, d, n) == HG_I2C_OK; }
static bool i2cBusOkAtBoot = true;

enum { DEV_SKIN, DEV_REF, DEV_SHT, DEV_IMU, DEV_PPG, DEV_DRV, DEV_N };
static const char* DEV_NAME[DEV_N] = { "tmp117-0x48", "tmp117-0x49", "shtc3", "icm20649", "max30102", "drv2605" };
static uint8_t devFails[DEV_N];
static bool* devFlag(int d);
static void evLog(const char* fmt, ...);
static bool devResult(int d, bool ok) {   // 3 consecutive failures -> missing (re-probed every minute)
  if (ok) { devFails[d] = 0; return true; }
  if (++devFails[d] >= 3 && *devFlag(d)) { *devFlag(d) = false; devFails[d] = 0; evLog("SENSOR LOST %s t_ms=%lu", DEV_NAME[d], (unsigned long)millis()); }
  return false;
}

// =====================================================================
// TMP117 x2: one-shot, 8x averaging, every 5 s, triggered back-to-back
// =====================================================================
static float t1C = NAN, t2C = NAN;
static bool tmpProbe(uint8_t a) {
  uint8_t b[2];
  if (!i2cReadReg(a, 0x0F, b, 2)) return false;
  return ((((uint16_t)b[0] << 8) | b[1]) & 0x0FFF) == 0x0117;
}
static bool tmpTrigger(uint8_t a) {
  // CONFIG: MOD = 11 one-shot, AVG = 01 (8 samples), everything else 0 -> 0x0C20
  uint8_t b[3] = {0x01, 0x0C, 0x20};
  return i2cWrite(a, b, 3);
}
static bool tmpRead(uint8_t a, float* out) {
  uint8_t b[2];
  if (!i2cReadReg(a, 0x00, b, 2)) return false;
  int16_t raw = (int16_t)(((uint16_t)b[0] << 8) | b[1]);
  if (raw == (int16_t)0x8000) return false;     // reset value: no conversion yet
  *out = raw * 0.0078125f;
  return true;
}

// =====================================================================
// SHTC3: wake, measure (normal, T first, no clock stretching), read after 20 ms, sleep
// =====================================================================
static float tairC = NAN, rhPct = NAN;
static uint8_t shtCrc(const uint8_t* d) {   // CRC-8 poly 0x31 init 0xFF (Sensirion)
  uint8_t c = 0xFF;
  for (int i = 0; i < 2; i++) { c ^= d[i]; for (int k = 0; k < 8; k++) c = (c & 0x80) ? (c << 1) ^ 0x31 : (c << 1); }
  return c;
}
static bool shtCmd(uint16_t cmd) { uint8_t b[2] = {(uint8_t)(cmd >> 8), (uint8_t)cmd}; return i2cWrite(0x70, b, 2); }
static bool shtProbe() {
  shtCmd(0x3517); delayMicroseconds(300);                 // wake up
  uint8_t b[3]; bool ok = shtCmd(0xEFC8) && i2cRead(0x70, b, 3) && shtCrc(b) == b[2] && (((b[0] << 8) | b[1]) & 0x083F) == 0x0807;
  shtCmd(0xB098);                                          // sleep
  return ok;
}
static bool shtTrigger() { if (!shtCmd(0x3517)) return false; delayMicroseconds(300); return shtCmd(0x7866); }
static bool shtRead() {
  uint8_t b[6];
  bool ok = i2cRead(0x70, b, 6) && shtCrc(b) == b[2] && shtCrc(b + 3) == b[5];
  shtCmd(0xB098);
  if (!ok) return false;
  uint16_t st = (b[0] << 8) | b[1], sh = (b[3] << 8) | b[4];
  tairC = -45.0f + 175.0f * st / 65536.0f;
  rhPct = 100.0f * sh / 65536.0f;
  return true;
}

// =====================================================================
// ICM-20649: accelerometer only, duty-cycled low power, 25 Hz, gyro OFF (R4 A6 finding 1)
// =====================================================================
static const float ACC_LSB_PER_G = 8192.0f;   // +-4 g range
static bool imuRaw(float* ax, float* ay, float* az) {
  uint8_t b[6];
  if (!devResult(DEV_IMU, i2cReadReg(imuAddr, 0x2D, b, 6))) return false;   // bank 0 ACCEL_XOUT_H..ZOUT_L
  *ax = (int16_t)((b[0] << 8) | b[1]) / ACC_LSB_PER_G;
  *ay = (int16_t)((b[2] << 8) | b[3]) / ACC_LSB_PER_G;
  *az = (int16_t)((b[4] << 8) | b[5]) / ACC_LSB_PER_G;
  return true;
}
static bool imuSelfCheck() {   // 10 samples: |a| near 1 g and not frozen
  float lastx = 1e9f; int moving = 0, okc = 0;
  for (int i = 0; i < 10; i++) {
    delay(45);
    float x, y, z;
    if (!imuRaw(&x, &y, &z)) continue;
    float m = sqrtf(x * x + y * y + z * z);
    if (m > 0.6f && m < 1.4f) okc++;
    if (x != lastx) moving++;
    lastx = x;
  }
  return okc >= 7 && moving >= 2;
}
static bool imuProbe(uint8_t a) {                 // WHO_AM_I (bank 0, 0x00) = 0xE1 for the ICM-20649
  uint8_t id = 0;
  i2cWriteReg8(a, 0x7F, 0x00);
  return i2cReadReg(a, 0x00, &id, 1) && id == 0xE1;
}
static bool imuConfigure() {
  i2cWriteReg8(imuAddr, 0x7F, 0x00);
  i2cWriteReg8(imuAddr, 0x06, 0x80);              // PWR_MGMT_1: DEVICE_RESET
  delay(50);
  uint8_t pm = 0x80;
  for (int i = 0; i < 10 && (pm & 0x80); i++) { delay(5); if (!i2cReadReg(imuAddr, 0x06, &pm, 1)) pm = 0x80; }
  if (pm & 0x80) return false;
  i2cWriteReg8(imuAddr, 0x06, 0x01);              // wake, auto clock
  delay(30);
  i2cWriteReg8(imuAddr, 0x7F, 0x20);              // REG_BANK_SEL = bank 2
  i2cWriteReg8(imuAddr, 0x10, 0x00);              // ACCEL_SMPLRT_DIV_1
  i2cWriteReg8(imuAddr, 0x11, 44);                // ACCEL_SMPLRT_DIV_2: 1125 Hz / (1 + 44) = 25 Hz
  i2cWriteReg8(imuAddr, 0x14, 0x29);              // ACCEL_CONFIG: DLPFCFG 5 (~12 Hz, low-noise fallback), FS_SEL 0 (+-4 g), FCHOICE 1
  i2cWriteReg8(imuAddr, 0x15, 0x02);              // ACCEL_CONFIG_2: DEC3_CFG 2 = average 16 samples in duty-cycled mode (lower noise)
  i2cWriteReg8(imuAddr, 0x7F, 0x00);              // REG_BANK_SEL = bank 0
  i2cWriteReg8(imuAddr, 0x07, 0x07);              // PWR_MGMT_2: accel on, gyro x/y/z OFF
  i2cWriteReg8(imuAddr, 0x05, 0x20);              // LP_CONFIG: ACCEL_CYCLE = 1 (duty-cycled)
  i2cWriteReg8(imuAddr, 0x06, 0x29);              // PWR_MGMT_1: LP_EN | TEMP_DIS | CLKSEL = 1, not asleep
  delay(30);
  imuLowPower = imuSelfCheck();
  if (!imuLowPower) {                             // fall back: low-noise accel, gyro still off
    i2cWriteReg8(imuAddr, 0x05, 0x00);
    i2cWriteReg8(imuAddr, 0x06, 0x09);            // TEMP_DIS | CLKSEL = 1
    delay(30);
  }
  return true;
}

// =====================================================================
// MAX30102: SpO2 mode (red + IR) at 100 sps; red LED on 1 s out of every 4 s
// Own FIFO reader: the SparkFun check() keeps only 4 samples (STORAGE_SIZE 4) and loses the
// rest when the loop is slower than 40 ms; it also fills only RED in ledMode 1.
// =====================================================================
static uint32_t ppgSampleMs = 0;        // 10 ms grid clock for hg_ppg (keeps hg_ppg's 1 s update tick)
static uint32_t ppgSamples = 0, ppgOverflows = 0, ppgReadErrors = 0;
static bool redOn = false;
static uint32_t redSum = 0; static uint16_t redN = 0, redSkip = 0;
static uint32_t redDc = 0;              // latest red-window DC (counts)
static bool ppgEnabled = false;

// raw capture state
static bool rawActive = false;
static uint32_t rawEndMs = 0, rawSamples = 0, rawDropped = 0;
static uint8_t rawBlock[8 + 3 * RAW_BLOCK_N];
static uint16_t rawBlockN = 0;
static uint8_t rawBuf[12 * sizeof(rawBlock)];
static uint16_t rawBufLen = 0;
static uint16_t rawSeq = 0;
static uint8_t rawCh = 0;
static uint8_t rawUsbBlk[8 + 3 * RAW_BLOCK_N]; static uint8_t rawUsbQ = 4; static uint32_t rawUsbDrops = 0;
static void rawPushSample(uint32_t ir, uint32_t tms);

static bool ppgInit() {                           // MAX30102 registers as SparkFun setup(0x1F, 4, 2, 400, 411, 4096)
  uint8_t id = 0, m = 0x40;
  if (!i2cReadReg(0x57, 0xFF, &id, 1) || id != 0x15) return false;   // PART_ID
  i2cWriteReg8(0x57, 0x09, 0x40);                 // MODE_CONFIG: RESET
  for (int i = 0; i < 20 && (m & 0x40); i++) { delay(5); if (!i2cReadReg(0x57, 0x09, &m, 1)) m = 0x40; }
  if (m & 0x40) return false;
  i2cWriteReg8(0x57, 0x08, 0x50);                 // FIFO_CONFIG: SMP_AVE 4, FIFO_ROLLOVER_EN
  i2cWriteReg8(0x57, 0x09, 0x03);                 // MODE_CONFIG: SpO2 mode (LED1 red + LED2 IR)
  i2cWriteReg8(0x57, 0x0A, 0x2F);                 // SPO2_CONFIG: ADC 4096 nA, 400 sps (avg 4 -> 100 sps), 411 us
  i2cWriteReg8(0x57, 0x0C, 0x00);                 // LED1_PA red off (switched on 1 s in 4)
  i2cWriteReg8(0x57, 0x0D, PPG_LED_PA);           // LED2_PA IR ~6 mA
  i2cWriteReg8(0x57, 0x04, 0); i2cWriteReg8(0x57, 0x05, 0); i2cWriteReg8(0x57, 0x06, 0);
  return true;
}
static void ppgSetRed(bool on) {
  if (!hasPpg) return;
  i2cWriteReg8(0x57, 0x0C, on ? PPG_LED_PA : 0x00);   // LED1_PA (red)
  redOn = on; redSum = 0; redN = 0; redSkip = 10;      // skip 100 ms after switching
}
static void ppgEnable(bool on) {
  if (!hasPpg) { ppgEnabled = false; return; }
  uint8_t mode = 0x03;                                  // SpO2 mode (red + IR) if the read fails
  i2cReadReg(0x57, 0x09, &mode, 1);
  if (on) mode &= ~0x80; else mode |= 0x80;             // MODE_CONFIG bit7 SHDN
  i2cWriteReg8(0x57, 0x09, mode);
  ppgEnabled = on;
  if (on) { i2cWriteReg8(0x57, 0x04, 0); i2cWriteReg8(0x57, 0x05, 0); i2cWriteReg8(0x57, 0x06, 0); ppgSampleMs = 0; }
}
static void ppgServiceBody(bool moving);
static void ppgService(bool moving) {
  static bool inService = false;                         // re-entered from lfsErase(): skip
  if (!hasPpg || !ppgEnabled || inService) return;
  inService = true;
  ppgServiceBody(moving);
  inService = false;
}
static void ppgServiceBody(bool moving) {
  uint8_t p[3];
  if (!devResult(DEV_PPG, i2cReadReg(0x57, 0x04, p, 3))) { ppgReadErrors++; return; }   // WR_PTR, OVF_COUNTER, RD_PTR
  uint8_t n = (p[0] - p[2]) & 31;
  if (p[1]) { n = 32; ppgOverflows += p[1]; }
  if (!n) return;
  uint32_t now = millis();
  if (ppgSampleMs == 0 || (int32_t)(now - (ppgSampleMs + 10u * n)) > 100 || (int32_t)(now - (ppgSampleMs + 10u * n)) < -100)
    ppgSampleMs = (now - 10u * n) / 10u * 10u;          // (re)align the 10 ms grid to real time
  hg_ppg_set_motion(&hrDet, moving);
  while (n) {
    uint8_t k = n > 10 ? 10 : n;                         // 10 samples x 6 B = 60 B < 64 B Wire buffer
    uint8_t d[60];
    if (!devResult(DEV_PPG, i2cReadReg(0x57, 0x07, d, k * 6))) { ppgReadErrors++; return; }
    for (uint8_t i = 0; i < k; i++) {
      uint32_t red = (((uint32_t)d[6 * i] << 16) | ((uint32_t)d[6 * i + 1] << 8) | d[6 * i + 2]) & 0x3FFFF;
      uint32_t ir  = (((uint32_t)d[6 * i + 3] << 16) | ((uint32_t)d[6 * i + 4] << 8) | d[6 * i + 5]) & 0x3FFFF;
      ppgSampleMs += 10;
      hg_ppg_push(&hrDet, ir, ppgSampleMs);
      ppgSamples++;
      if (redOn) { if (redSkip) redSkip--; else { redSum += red; redN++; } }
      if (rawActive) rawPushSample(ir, ppgSampleMs);
    }
    n -= k;
  }
}

// =====================================================================
// haptics (07 patterns) + backlight rule
// =====================================================================
#define WAIT10MS(n) (0x80 | (n))
const uint8_t PAT_SHORT[8] = { 10, WAIT10MS(10), 10, 0 };  // 07 "Drink": double click x2
const uint8_t PAT_LONG[8]  = { 16, 52, 0 };                // 07 "Danger": 1000 ms alert + pulsing strong
const uint8_t PAT_SOFT[8]  = { 2, 0 };                     // 07 "All OK": soft tick (low battery)
static bool motorBusy = false;
static uint32_t motorStart = 0, motorEnd = 0;
static bool screenOn = false;
static uint8_t blTarget = 0;

static void blOff() {
  for (int i = 0; i < HWPWM_MODULE_NUM; i++) {
    if (HwPWMx[i]->checkPin(LCD_BL)) {
      HwPWMx[i]->removePin(LCD_BL);
      if (HwPWMx[i]->usedChannelCount() == 0) HwPWMx[i]->stop();   // no PWM clock left running
    }
  }
  pinMode(LCD_BL, OUTPUT);
  digitalWrite(LCD_BL, LOW);
}
static void applyBacklight() {   // the ONLY function that turns the backlight on
  uint8_t pct = screenOn ? blTarget : 0;
  if (motorBusy && pct > BL_MOTOR_MAX) pct = BL_MOTOR_MAX;
  if (pct == 0) { blOff(); return; }
  analogWrite(LCD_BL, (uint16_t)pct * 255 / 100);
}
static bool drvInit() {                           // the Adafruit_DRV2605 begin()/useERM()/selectLibrary(2)/INTTRIG sequence
  uint8_t st = 0;
  if (!i2cReadReg(0x5A, 0x00, &st, 1)) return false;
  uint8_t id = st >> 5; if (id != 3 && id != 4 && id != 6 && id != 7) return false;   // DRV2605/2604/2605L/2604L
  static const uint8_t init[][2] = { {0x01, 0x00}, {0x02, 0x00}, {0x04, 1}, {0x05, 0}, {0x0D, 0}, {0x0E, 0}, {0x0F, 0},
                                     {0x10, 0}, {0x13, 0x64}, {0x03, 2}, {0x01, 0x00} };
  for (auto& r : init) if (!i2cWriteReg8(0x5A, r[0], r[1])) return false;
  uint8_t fb = 0, c3 = 0;
  if (!i2cReadReg(0x5A, 0x1A, &fb, 1) || !i2cReadReg(0x5A, 0x1D, &c3, 1)) return false;
  i2cWriteReg8(0x5A, 0x1A, fb & 0x7F);            // FEEDBACK: N_ERM_LRA = 0 (ERM)
  i2cWriteReg8(0x5A, 0x1D, c3 | 0x20);            // CONTROL3: ERM open loop
  return true;
}
static void vibrate(const uint8_t* pat) {
  if (!hasDrv || lowBatMode) return;
  if (vbat == vbat && vbat < VBAT_SOFT && !charging()) pat = PAT_SOFT;   // brown-out rule (R4 A8.2)
  motorBusy = true;
  applyBacklight();               // dim FIRST, then start the motor
  uint8_t i = 0;
  for (; i < 8 && pat[i]; i++) i2cWriteReg8(0x5A, 0x04 + i, pat[i]);   // WAVESEQ1..8
  if (i < 8) i2cWriteReg8(0x5A, 0x04 + i, 0);
  devResult(DEV_DRV, i2cWriteReg8(0x5A, 0x0C, 1));                       // GO
  motorStart = millis();
}
static void serviceMotor() {
  if (!motorBusy) return;
  static uint32_t lastPoll = 0;
  if (millis() - lastPoll < 20) return;
  lastPoll = millis();
  uint8_t go = 0;
  bool okr = devResult(DEV_DRV, i2cReadReg(0x5A, 0x0C, &go, 1));
  bool playing = okr && (go & 0x01);
  if (!playing || millis() - motorStart > 5000) {
    if (playing) i2cWriteReg8(0x5A, 0x0C, 0);
    motorBusy = false;
    motorEnd = millis();
    applyBacklight();
  }
}
static bool recentlyBuzzed() { return motorBusy || (motorEnd && millis() - motorEnd < AFTER_BUZZ_MS); }

// =====================================================================
// markers
// =====================================================================
static const char* MARK_NAME[HG_M_COUNT] = { "none", "donned", "loose", "off", "shower", "out", "home",
                                             "oral", "help", "button", "boot", "time", "file" };
struct MarkQ { uint8_t m; uint16_t v; };
static MarkQ markQ[8]; static uint8_t markHead = 0, markTail = 0;
static uint8_t lastMarker = 0; static uint16_t lastMarkerVal = 0; static uint32_t lastMarkerMs = 0;
static bool pendButton = false;
static void evLog(const char* fmt, ...);
static void queueMarker(uint8_t m, uint16_t v, const char* src) {
  uint8_t nh = (markHead + 1) & 7;
  if (nh != markTail) { markQ[markHead].m = m; markQ[markHead].v = v; markHead = nh; }
  if (m != HG_M_BOOT && m != HG_M_FILE) { lastMarker = m; lastMarkerVal = v; lastMarkerMs = millis(); }
  evLog("MARK boot=%lu t_ms=%lu m=%u name=%s v=%u src=%s unix=%lu", (unsigned long)bootCount, (unsigned long)millis(),
        m, m < HG_M_COUNT ? MARK_NAME[m] : "?", v, src, (unsigned long)nowUnix());
}

// =====================================================================
// storage: QSPI flash (P25Q16H, 2 MB) + LittleFS v1.6 with our own config
// The core's ExternalFileSystem library is NOT used: it is written for the Wio Tracker
// (P25Q32H, 4 MB hard-coded, ignores flash.begin() failure) and would not detect the
// XIAO's P25Q16H (JEDEC 85 60 15) and would address 4 MB on a 2 MB part.
// =====================================================================
static const SPIFlash_Device_t XIAO_FLASH[2] = {
  { .total_size = (1UL << 21), .start_up_time_us = 5000, .manufacturer_id = 0x85, .memory_type = 0x60,
    .capacity = 0x15, .max_clock_speed_mhz = 55, .quad_enable_bit_mask = 0x02, .has_sector_protection = 1,
    .supports_fast_read = 1, .supports_qspi = 1, .supports_qspi_writes = 1, .write_status_register_split = 1,
    .single_status_byte = 0, .is_fram = 0 },   // P25Q16H (XIAO nRF52840, variant.h)
  { .total_size = (1UL << 22), .start_up_time_us = 5000, .manufacturer_id = 0x85, .memory_type = 0x60,
    .capacity = 0x16, .max_clock_speed_mhz = 104, .quad_enable_bit_mask = 0x02, .has_sector_protection = 1,
    .supports_fast_read = 1, .supports_qspi = 1, .supports_qspi_writes = 1, .write_status_register_split = 1,
    .single_status_byte = 0, .is_fram = 0 },   // P25Q32H (as in the core's ExternalFileSystem.cpp)
};
Adafruit_FlashTransport_QSPI qspiTr;
Adafruit_SPIFlashBase qflash(&qspiTr);
static bool flashAwake = false, qspiActive = false;
static uint32_t flashWakes = 0, flashJedec = 0, flashWakeFails = 0;
// 1.1.5 ROOT-CAUSE FIX (bench Nov 13): flashSleep() put the chip in deep power-down (0xB9). A reset or a
// re-flash does NOT power-cycle the flash (3V3 stays up), so the next start found a sleeping chip. The nRF
// QSPI peripheral cannot be trusted to wake it: ACTIVATE against a chip in deep power-down stalls (nrfx gives
// up after 1 ms, then every custom instruction times out and the driver returns its untouched buffer =
// "JEDEC 000000"), so the 0xAB sent THROUGH the peripheral never reached the chip - in this sketch, in
// flashid, in 1.1.3's retries. The chip is now woken by bit-banging 0xAB on the pins as plain GPIO with the
// peripheral off, before every nrfx_qspi_init (Zephyr does the same job in nrf_qspi_nor.c exit_dpd).
static const uint8_t QP_SCK = 21, QP_CS = 25, QP_IO0 = 20, QP_IO1 = 24, QP_IO2 = 22, QP_IO3 = 23;   // P0.xx
static inline void qpOut(uint8_t p, bool v) {
  if (v) NRF_P0->OUTSET = 1u << p; else NRF_P0->OUTCLR = 1u << p;
  NRF_P0->PIN_CNF[p] = (GPIO_PIN_CNF_DIR_Output << GPIO_PIN_CNF_DIR_Pos) | (GPIO_PIN_CNF_INPUT_Connect << GPIO_PIN_CNF_INPUT_Pos);
}
static inline void qpW(uint8_t p, bool v) { if (v) NRF_P0->OUTSET = 1u << p; else NRF_P0->OUTCLR = 1u << p; }
static void qpPins(uint32_t io1Pull) {            // QSPI peripheral must be OFF (qspiActive == false)
  qpOut(QP_CS, 1); qpOut(QP_SCK, 0); qpOut(QP_IO0, 1); qpOut(QP_IO2, 1); qpOut(QP_IO3, 1);   // WP#, HOLD# high
  NRF_P0->PIN_CNF[QP_IO1] = (GPIO_PIN_CNF_DIR_Input << GPIO_PIN_CNF_DIR_Pos) | (GPIO_PIN_CNF_INPUT_Connect << GPIO_PIN_CNF_INPUT_Pos) |
                            (io1Pull << GPIO_PIN_CNF_PULL_Pos);
  delayMicroseconds(2);
}
static void qpXfer(uint8_t op, uint8_t* rx, uint8_t n) {   // SPI mode 0, ~250 kHz, MSB first; CS high right after the last clock
  qpW(QP_CS, 0); delayMicroseconds(1);
  for (int i = 7; i >= 0; i--) { qpW(QP_IO0, (op >> i) & 1); delayMicroseconds(1); qpW(QP_SCK, 1); delayMicroseconds(1); qpW(QP_SCK, 0); }
  for (uint8_t k = 0; k < n; k++) { uint8_t v = 0;
    for (int i = 0; i < 8; i++) { delayMicroseconds(1); qpW(QP_SCK, 1); v = (uint8_t)((v << 1) | ((NRF_P0->IN >> QP_IO1) & 1u)); delayMicroseconds(1); qpW(QP_SCK, 0); }
    rx[k] = v; }
  delayMicroseconds(1); qpW(QP_CS, 1); qpW(QP_IO0, 1); delayMicroseconds(2);
}
static void gpioWake(bool reset) {                 // 0xAB (+ optional 0x66/0x99) as GPIO; ~100 us
  qpPins(GPIO_PIN_CNF_PULL_Pullup);
  qpXfer(0xAB, NULL, 0); delayMicroseconds(50);    // tRES1 8 us max-class; 50 us margin
  if (reset) { qpXfer(0x66, NULL, 0); delayMicroseconds(5); qpXfer(0x99, NULL, 0); delayMicroseconds(100); }   // tRST 30 us
}
static uint32_t gpioId(uint32_t pull) {           // JEDEC by bit-bang (peripheral off), IO1 pulled up or down
  qpPins(pull); delayMicroseconds(20);
  uint8_t id[3]; qpXfer(0x9F, id, 3);
  return ((uint32_t)id[0] << 16) | (id[1] << 8) | id[2];
}
static void qspiOff() {           // T6a M3: the nRF QSPI peripheral itself draws current while enabled
  if (qspiActive && NRF_QSPI->ENABLE) {
    // nRF52840 erratum 122, Nordic's order: DEACTIVATE task + 0x054 while the peripheral is still ENABLED,
    // then disable (1.1.4 wrote them after the disable). nrfx_qspi_uninit() then disables and resets its state.
    *(volatile uint32_t*)0x40029010ul = 1ul;
    *(volatile uint32_t*)0x40029054ul = 1ul;
  }
  qspiTr.end();                   // nrfx_qspi_uninit: DEACTIVATE + disable
  NRF_P0->OUTSET = 1u << 25;      // QSPI CS (P0.25) held high as a GPIO while the peripheral is off
  NRF_P0->PIN_CNF[25] = (GPIO_PIN_CNF_DIR_Output << GPIO_PIN_CNF_DIR_Pos) | (GPIO_PIN_CNF_INPUT_Disconnect << GPIO_PIN_CNF_INPUT_Pos);
  qspiActive = false;
}
static void qspiOn() {
  if (qspiActive) return;
  gpioWake(false);                // the chip must be awake BEFORE the peripheral's ACTIVATE (see above)
  qspiTr.begin();                 // nrfx_qspi_init (2 MHz) ...
  qspiTr.setClockSpeed(55000000u, 55000000u);   // ... then 16 MHz as after qflash.begin()
  qspiActive = true;
}
static void flashWake() {
  if (flashAwake) return;
  qspiOn();                       // wakes the chip by GPIO first
  qspiTr.runCommand(0xAB);        // and once more through the peripheral (harmless when awake)
  delayMicroseconds(50);          // tRES1 (P25Q16H: 8 us typ class figure; 50 us margin)
  uint8_t id[3] = {0, 0, 0};
  if (!qspiTr.readCommand(0x9F, id, 3) || id[0] != 0x85) flashWakeFails++;   // stat: flash_wake_fails
  flashAwake = true; flashWakes++;
}
static int lfsRead(const struct lfs_config*, lfs_block_t b, lfs_off_t off, void* buf, lfs_size_t n) {
  flashWake(); qflash.readBuffer(b * 4096u + off, (uint8_t*)buf, n); return 0;
}
static int lfsProg(const struct lfs_config*, lfs_block_t b, lfs_off_t off, const void* buf, lfs_size_t n) {
  flashWake(); qflash.writeBuffer(b * 4096u + off, (const uint8_t*)buf, n); return 0;
}
// Erase without blocking the PPG: a 4 KB erase takes 40-50 ms typ, 300 ms max (Puya datasheet) and the
// MAX30102 FIFO holds 320 ms, so keep draining the FIFO while the flash is busy (T6a m9).
static int lfsErase(const struct lfs_config*, lfs_block_t b) {
  flashWake();
  qflash.waitUntilReady();
  NRF_QSPI->EVENTS_READY = 0;
  NRF_QSPI->ERASE.PTR = b * 4096u;
  NRF_QSPI->ERASE.LEN = QSPI_ERASE_LEN_LEN_4KB;
  NRF_QSPI->TASKS_ERASESTART = 1;  // the QSPI sends WREN itself
  uint32_t t0 = millis();
  while (!NRF_QSPI->EVENTS_READY && millis() - t0 < 1000) { ppgService(hrDet.motion); delay(1); }
  NRF_QSPI->EVENTS_READY = 0;
  while ((qflash.readStatus() & 0x01) && millis() - t0 < 1500) { ppgService(hrDet.motion); delay(1); }
  qflash.waitUntilReady();
  return 0;
}
static int lfsSync(const struct lfs_config*) { return 0; }
static __attribute__((aligned(4))) uint8_t lfsRdBuf[256], lfsPrBuf[256], lfsLaBuf[512 / 8];
static struct lfs_config logCfg = {
  .context = NULL, .read = lfsRead, .prog = lfsProg, .erase = lfsErase, .sync = lfsSync,
  .read_size = 256, .prog_size = 256, .block_size = 4096, .block_count = 512, .lookahead = 512,
  .read_buffer = lfsRdBuf, .prog_buffer = lfsPrBuf, .lookahead_buffer = lfsLaBuf, .file_buffer = NULL
};
Adafruit_LittleFS logFS(&logCfg);

enum { FS_NO_FLASH = 0, FS_CORRUPT = 1, FS_OK = 2 };
static uint8_t fsState = FS_NO_FLASH;
static const char* FS_NAME[] = { "NO FLASH", "CORRUPT (type: format YES)", "OK" };
static bool dumpActive = false;
static void flashSleep() {
  if (fsState == FS_NO_FLASH || !flashAwake || dumpActive) return;   // no device -> qflash has no descriptor
  qflash.waitUntilReady();
#if HG_FLASH_DPD
  qspiTr.runCommand(0xB9);        // flash chip: deep power-down (~23 uA -> ~1 uA class; power.md); woken by GPIO
#endif
  flashAwake = false;
  qspiOff();                      // nRF QSPI peripheral: off too
}

// dumped_next: s/r files with seq >= dumped_next have not been fully dumped yet ("dump new")
// quick_boots: boots in a row that did not reach 10 min of uptime (kept on flash: the nRF retained registers are
// cleared by watchdog, pin and brown-out resets, T6a n1). Uploads (software resets) do not count.
struct BootFile { uint32_t magic, boot_count; uint16_t next_seq, dumped_next; uint32_t wdt_resets, other_resets, quick_boots, crc; };
static BootFile bootf;
static uint16_t curSeq = 0;
static char curPath[24] = "";
static uint32_t recsInFile = 0;
static uint32_t flushOk = 0, flushErr = 0, recsLost = 0, filesDeleted = 0;
static bool fsFull = false;

static uint32_t crc32b(const void* q, size_t n) { const uint8_t* b = (const uint8_t*)q; uint32_t c = ~0u; while (n--) { c ^= *b++; for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u))); } return ~c; }

static bool fileAppend(const char* path, const uint8_t* d, uint32_t n) {
  File f(logFS);
  if (!f.open(path, FILE_O_WRITE)) return false;   // FILE_O_WRITE opens at the end (append)
  uint32_t w = f.write(d, n);
  f.close();
  return w == n;
}
static bool bootSave() {
  bootf.magic = 0x48474254u; bootf.crc = crc32b(&bootf, sizeof bootf - 4);
  File f(logFS);
  if (!f.open("/log/boot.bin", FILE_O_WRITE)) return false;
  f.seek(0); f.truncate(0);
  bool ok = f.write((const uint8_t*)&bootf, sizeof bootf) == sizeof bootf;
  f.close();
  return ok;
}
static void bootLoad() {
  File f(logFS);
  bool ok = false;
  if (f.open("/log/boot.bin", FILE_O_READ)) { ok = f.read((uint8_t*)&bootf, sizeof bootf) == sizeof bootf; f.close(); }
  if (!ok || bootf.magic != 0x48474254u || bootf.crc != crc32b(&bootf, sizeof bootf - 4)) memset(&bootf, 0, sizeof bootf);
}

// list /log into the ring module's table
static hg_logfile_t ringFiles[HG_RING_MAX_FILES];
static char ringNames[HG_RING_MAX_FILES][12];
static int ringN = 0;
static void listLog() {
  ringN = 0;
  File dir = logFS.open("/log", FILE_O_READ);
  if (!dir || !dir.isDirectory()) return;
  File e(logFS);
  while (ringN < HG_RING_MAX_FILES && (e = dir.openNextFile(FILE_O_READ))) {
    const char* nm = e.name();
    uint16_t seq = 0;
    char k = hg_ring_classify(nm, &seq);
    ringFiles[ringN].kind = k; ringFiles[ringN].seq = seq; ringFiles[ringN].size = e.size();
    strncpy(ringNames[ringN], nm, 11); ringNames[ringN][11] = 0;
    ringN++;
    e.close();
  }
  dir.close();
}
static int countBlock(void* p, lfs_block_t) { (*(uint32_t*)p)++; return 0; }
static uint32_t usedBlocks() {
  uint32_t n = 0;
  logFS._lockFS();
  lfs_traverse(logFS._getFS(), countBlock, &n);
  logFS._unlockFS();
  return n;
}
static uint32_t freeBlocks() { uint32_t u = usedBlocks(); return u >= logCfg.block_count ? 0 : logCfg.block_count - u; }

static uint32_t undumpedDeleted = 0;
static bool bootLoop = false;                      // >= 3 quick boots: no file deletions for 30 min
static uint8_t quickBoots = 0;
static void ringMakeRoom(uint32_t needBlocks, int maxS) {
  if (bootLoop) { evLog("RING HOLD boot-loop: no deletions t_ms=%lu", (unsigned long)millis()); fsFull = freeBlocks() < 8; return; }
  listLog();
  int del[HG_RING_MAX_FILES];
  int nd = hg_ring_plan(ringFiles, ringN, freeBlocks(), logCfg.block_size, needBlocks, maxS, del, HG_RING_MAX_FILES);
  for (int i = 0; i < nd; i++) {
    char p[24]; snprintf(p, sizeof p, "/log/%s", ringNames[del[i]]);
    bool undumped = ringFiles[del[i]].seq >= bootf.dumped_next;
    if (logFS.remove(p)) { filesDeleted++; if (undumped) undumpedDeleted++;
      evLog("DELETE %s size=%lu %s", p, (unsigned long)ringFiles[del[i]].size, undumped ? "UNDUMPED" : "dumped"); }
  }
  fsFull = freeBlocks() < 8;
}
static uint16_t takeSeq() {
  listLog();
  uint16_t s = hg_ring_next_seq(ringFiles, ringN, bootf.next_seq);
  bootf.next_seq = (uint16_t)((s + 1) % HG_SEQ_MOD);
  bootSave();
  return s;
}

static void buildRecordBase(hg_rec_t* r);
static void newHourFile() {
  if (fsState != FS_OK) return;
  ringMakeRoom(HG_RING_MARGIN_BLOCKS, HG_RING_MAX_S_FILES);
  curSeq = takeSeq();
  hg_ring_make_path('s', curSeq, curPath, sizeof curPath);
  hg_rec_t r; buildRecordBase(&r);
  r.marker = HG_M_FILE; r.flags |= HG_F_MARKER; r.aux = (uint16_t)bootCount;
  uint8_t b[HG_REC_SIZE]; hg_rec_pack(&r, b);
  if (!fileAppend(curPath, b, HG_REC_SIZE)) flushErr++;
  recsInFile = 0;
  evLog("FILE boot=%lu t_ms=%lu path=%s free_blocks=%lu", (unsigned long)bootCount, (unsigned long)millis(), curPath, (unsigned long)freeBlocks());
}

// after a reset: keep appending to the newest hour file if it is not full (T6a blocker B1) -
// a new file per boot is what used to push full hours out of the ring
static void bootHourFile() {
  if (fsState != FS_OK) return;
  listLog();
  uint16_t seq;
  if (!hg_ring_boot_file(ringFiles, ringN, HG_HOUR_FILE_BYTES, &seq)) { newHourFile(); return; }
  curSeq = seq;
  hg_ring_make_path('s', curSeq, curPath, sizeof curPath);
  uint32_t size = 0;
  for (int i = 0; i < ringN; i++) if (ringFiles[i].kind == 's' && ringFiles[i].seq == seq) size = ringFiles[i].size;
  hg_rec_t r; buildRecordBase(&r);
  r.marker = HG_M_FILE; r.flags |= HG_F_MARKER; r.aux = (uint16_t)bootCount;   // boot header inside the file
  uint8_t b[HG_REC_SIZE]; hg_rec_pack(&r, b);
  if (!fileAppend(curPath, b, HG_REC_SIZE)) flushErr++;
  recsInFile = size / HG_REC_SIZE;
  evLog("FILE APPEND boot=%lu t_ms=%lu path=%s records=%lu", (unsigned long)bootCount, (unsigned long)millis(), curPath, (unsigned long)recsInFile);
}

// does a littlefs superblock exist? ("littlefs" magic in metadata block 0 or 1)
static bool lfsSignature() {
  uint8_t b[256];
  for (uint32_t blk = 0; blk < 2; blk++) {
    qflash.readBuffer(blk * 4096u, b, sizeof b);
    for (int i = 0; i + 8 <= (int)sizeof b; i++) if (memcmp(b + i, "littlefs", 8) == 0) return true;
  }
  return false;
}
static char fsMsg[64] = "";
// bench diagnostic (1.1.4): "flashdiag" prints the raw QSPI state and the chip ID step by step
static uint32_t bootQspi[4] = {0, 0, 0, 0};       // ENABLE, PSEL.SCK, PSEL.CSN, PSEL.IO0 before storageInit
static void flashDiag(uint8_t ch) {
  replyf(ch, "# FLASHDIAG boot: enable=%lu sck=%08lx csn=%08lx io0=%08lx\n", (unsigned long)bootQspi[0],
         (unsigned long)bootQspi[1], (unsigned long)bootQspi[2], (unsigned long)bootQspi[3]);
  replyf(ch, "# FLASHDIAG now: enable=%lu sck=%08lx csn=%08lx io0=%08lx io1=%08lx io2=%08lx io3=%08lx ifconfig0=%08lx ifconfig1=%08lx\n",
         (unsigned long)NRF_QSPI->ENABLE, (unsigned long)NRF_QSPI->PSEL.SCK, (unsigned long)NRF_QSPI->PSEL.CSN,
         (unsigned long)NRF_QSPI->PSEL.IO0, (unsigned long)NRF_QSPI->PSEL.IO1, (unsigned long)NRF_QSPI->PSEL.IO2,
         (unsigned long)NRF_QSPI->PSEL.IO3, (unsigned long)NRF_QSPI->IFCONFIG0, (unsigned long)NRF_QSPI->IFCONFIG1);
  replyf(ch, "# FLASHDIAG pins: P0.25 cnf=%08lx out=%lu  P0.21 cnf=%08lx  P0.20 cnf=%08lx  P0.24 cnf=%08lx\n",
         (unsigned long)NRF_P0->PIN_CNF[25], (unsigned long)((NRF_P0->OUT >> 25) & 1), (unsigned long)NRF_P0->PIN_CNF[21],
         (unsigned long)NRF_P0->PIN_CNF[20], (unsigned long)NRF_P0->PIN_CNF[24]);
  replyf(ch, "# FLASHDIAG fw=%s jedec=%06lx wakes=%lu wake_fails=%lu\n", HG_FW_VERSION, (unsigned long)flashJedec,
         (unsigned long)flashWakes, (unsigned long)flashWakeFails);
  const char* step[4] = {"as-is", "end+begin", "+AB wake", "+66/99 reset"};
  for (int k = 0; k < 4; k++) {
    if (k == 1) { qspiOff(); delay(5); qspiTr.begin(); qspiActive = true; }
    if (k == 2) { qspiTr.runCommand(0xAB); delayMicroseconds(100); }
    if (k == 3) { qspiTr.runCommand(0x66); delayMicroseconds(50); qspiTr.runCommand(0x99); delay(1); }
    uint8_t id[3] = {0xA5, 0xA5, 0xA5}; bool r1 = qspiTr.readCommand(0x9F, id, 3);
    uint8_t sr = 0xA5; bool r2 = qspiTr.readCommand(0x05, &sr, 1);
    replyf(ch, "# FLASHDIAG %-13s id=%02x %02x %02x sr=%02x rdy=%d,%d%s\n", step[k], id[0], id[1], id[2], sr, r1, r2,
           (r1 && r2) ? "" : "  (QSPI instruction timed out: peripheral stuck, a5 = nothing read)");
  }
  // the same chip by bit-bang with the peripheral off: idU == idD -> the chip drives IO1; ffffff/000000 -> chip silent
  qspiOff();
  uint32_t u = gpioId(GPIO_PIN_CNF_PULL_Pullup), d = gpioId(GPIO_PIN_CNF_PULL_Pulldown);
  replyf(ch, "# FLASHDIAG gpio-as-is   idU=%06lx idD=%06lx\n", (unsigned long)u, (unsigned long)d);
  gpioWake(true);
  u = gpioId(GPIO_PIN_CNF_PULL_Pullup); d = gpioId(GPIO_PIN_CNF_PULL_Pulldown);
  replyf(ch, "# FLASHDIAG gpio-AB+rst  idU=%06lx idD=%06lx%s\n", (unsigned long)u, (unsigned long)d,
         (u == 0x856015ul && d == 0x856015ul) ? "  OK" : (u == 0xFFFFFFul && d == 0) ? "  chip SILENT" : "");
  qspiOn();
  qspiActive = true; flashAwake = true;
  replyf(ch, "# FLASHDIAG done (reboot with RST before trusting storage again)\n");
}
static void storageInit() {
  // 1.1.3 (bench Nov 13): on a real XIAO the JEDEC read returned 000000 here while a bare test that sent
  // reset-enable/reset (0x66/0x99) first read 85 60 15 on the same board. So: wake + software reset the chip,
  // check the ID ourselves, retry with a fresh peripheral, and keep the first raw ID for the stat line.
  // 1.1.5: the wake + reset go out by GPIO with the peripheral OFF (a sleeping chip stalls the QSPI ACTIVATE)
  bool ok = false; uint32_t firstId = 0xFFFFFFFFul;
  for (int attempt = 0; attempt < 4 && !ok; attempt++) {
    if (attempt) { qspiOff(); delay(20 * attempt); }
    gpioWake(true);                                           // 0xAB, 0x66, 0x99 bit-banged
    uint32_t g = gpioId(GPIO_PIN_CNF_PULL_Pulldown);          // the chip's own answer, no peripheral involved
    if (firstId == 0xFFFFFFFFul) firstId = g;
    qspiTr.begin(); qspiActive = true;
    uint8_t id[3] = {0, 0, 0}; qspiTr.readCommand(0x9F, id, 3);
    flashJedec = ((uint32_t)id[0] << 16) | (id[1] << 8) | id[2];
    if (id[0] != 0x85) continue;
    ok = qflash.begin(XIAO_FLASH, 2);                          // begins the transport again (harmless) and resets it
  }
  flashAwake = true;
  qspiActive = true;
  if (!ok) { fsState = FS_NO_FLASH; snprintf(fsMsg, sizeof fsMsg, "QSPI flash not detected, JEDEC %06lx gpio %06lx", (unsigned long)flashJedec, (unsigned long)firstId); return; }
  logCfg.block_count = qflash.size() / 4096u;
  if (logFS.begin()) { fsState = FS_OK; strcpy(fsMsg, "mounted"); }
  else if (!lfsSignature()) {                   // blank / never ours: safe to format
    logFS.format();
    fsState = logFS.begin() ? FS_OK : FS_CORRUPT;
    strcpy(fsMsg, fsState == FS_OK ? "formatted (first use)" : "format failed");
  } else {                                      // ours but unreadable: never auto-format (data!)
    fsState = FS_CORRUPT; strcpy(fsMsg, "mount failed, data kept");
  }
  if (fsState != FS_OK) return;
  if (!logFS.exists("/log")) logFS.mkdir("/log");
  bootLoad();
  bootf.boot_count++;
  if (resetReason & POWER_RESETREAS_DOG_Msk) bootf.wdt_resets++;
  else if (!(resetReason & (POWER_RESETREAS_SREQ_Msk | POWER_RESETREAS_RESETPIN_Msk))) bootf.other_resets++;
  bootf.quick_boots = (resetReason & POWER_RESETREAS_SREQ_Msk) ? 0 : bootf.quick_boots + 1;   // cleared after 10 min up
  quickBoots = (uint8_t)(bootf.quick_boots > 255 ? 255 : bootf.quick_boots);
  bootLoop = quickBoots >= 3;
  bootSave();
  bootCount = bootf.boot_count;
}

// RAM buffers, flushed once a minute
static uint8_t secBuf[70 * HG_REC_SIZE]; static uint16_t secN = 0;
// min.bin is appended every HG_MIN_FLUSH_EVERY minutes, not every minute: littlefs v1 rewrites the
// /log directory pair on EVERY file close, so each close is one erase of the same two 4 KB blocks.
// Measured with the real littlefs v1.6 on a RAM flash (fw/tools/test_lfs_host.c): 1-min min.bin
// appends -> 1,529 erases/block/day on the hot pair (65 days of continuous logging to 100 k cycles);
// every 10 min -> 881/day (114 days). The 1 Hz hour files are still flushed every 60 s.
#define HG_MIN_FLUSH_EVERY 10
static uint8_t minBuf[(HG_MIN_FLUSH_EVERY + 4) * HG_REC_SIZE];  static uint8_t minN = 0;
static char evBuf[1024]; static uint16_t evLen = 0; static uint32_t evDropped = 0;
static void evLog(const char* fmt, ...) {
  char line[176];
  va_list ap; va_start(ap, fmt); int n = vsnprintf(line, sizeof line - 1, fmt, ap); va_end(ap);
  if (n < 0) return;
  if (n > (int)sizeof line - 2) n = sizeof line - 2;
  line[n++] = '\n'; line[n] = 0;
  if ((size_t)evLen + (size_t)n < sizeof evBuf) { memcpy(evBuf + evLen, line, n); evLen += n; } else evDropped++;
  // events are also echoed live as comments
  char c[184]; snprintf(c, sizeof c, "# %s", line);
  outLine(CH_USB | CH_BLE, c);
}
static bool erasing = false;
static void flushAll(bool force = true) {
  if (erasing) return;                     // erase in progress: keep the records in RAM (<= 70 s)
  if (fsState != FS_OK) { recsLost += secN; secN = 0; minN = 0; evLen = 0; return; }
  bool ok = true;
  if (secN) { if (fileAppend(curPath, secBuf, (uint32_t)secN * HG_REC_SIZE)) recsInFile += secN; else { ok = false; recsLost += secN; } secN = 0; }
  if (minN && (force || minN >= HG_MIN_FLUSH_EVERY || recsInFile >= 3600)) { if (!fileAppend("/log/min.bin", minBuf, (uint32_t)minN * HG_REC_SIZE)) ok = false; minN = 0; }
  if (evLen) {   // events logged during this write (e.g. from ppgService inside an erase) are kept (T6a n3)
    uint16_t n = evLen;
    if (!fileAppend("/log/events.txt", (const uint8_t*)evBuf, n)) ok = false;
    memmove(evBuf, evBuf + n, evLen - n); evLen -= n;
  }
  if (ok) flushOk++; else flushErr++;
  if (recsInFile >= 3600) newHourFile();
  flashSleep();
}

// =====================================================================
// raw PPG capture (raw <seconds>): IR samples to /log/rNNNN.bin (+ live 'R' lines on USB)
// block = u32 t_first_ms, u16 n, u16 fs (=100), then n x 3 B IR (big-endian 18-bit), 308 B
// =====================================================================
static char rawPath[24] = "";
static void rawFlush() {
  // blocks may be appended while this write runs (ppgService() during a flash erase), so write only
  // the n bytes present now and keep whatever arrived after them
  uint16_t n = rawBufLen;
  if (!n) return;
  if (fsState == FS_OK) { if (!fileAppend(rawPath, rawBuf, n)) rawDropped += n / sizeof rawBlock; }
  noInterrupts();
  memmove(rawBuf, rawBuf + n, rawBufLen - n);
  rawBufLen -= n;
  interrupts();
}
static void rawCloseBlock() {
  if (!rawBlockN) return;
  rawBlock[4] = (uint8_t)rawBlockN; rawBlock[5] = (uint8_t)(rawBlockN >> 8);
  rawBlock[6] = 100; rawBlock[7] = 0;
  if (rawBlockN < RAW_BLOCK_N) memset(rawBlock + 8 + 3 * rawBlockN, 0, 3 * (RAW_BLOCK_N - rawBlockN));
  if (rawBufLen + sizeof rawBlock <= sizeof rawBuf) { memcpy(rawBuf + rawBufLen, rawBlock, sizeof rawBlock); rawBufLen += sizeof rawBlock; }
  else rawDropped++;
  if (rawCh & CH_USB) {                 // live copy on USB, sent in 4 quarter lines by rawUsbService()
    if (rawUsbQ < 4) rawUsbDrops++;
    memcpy(rawUsbBlk, rawBlock, sizeof rawBlock); rawUsbQ = 0;
  }
  rawBlockN = 0;
}
// one raw line = 'R' + quarter index 0..3 + 77 bytes of a 308-byte block as hex (157 chars incl. \n)
static void rawLine(uint8_t ch, const uint8_t* q77, uint8_t q) {
  char h[2 + 2 * 77 + 2];
  h[0] = 'R'; h[1] = (char)('0' + q);
  hg_hex(q77, 77, h + 2);
  h[156] = '\n'; h[157] = 0;
  outLine(ch, h);
}
static void rawUsbService() {
  while (rawUsbQ < 4 && Serial && Serial.availableForWrite() >= 160) { rawLine(CH_USB, rawUsbBlk + 77 * rawUsbQ, rawUsbQ); rawUsbQ++; }
}
static void rawPushSample(uint32_t ir, uint32_t tms) {
  if (rawBlockN == 0) { rawBlock[0] = tms; rawBlock[1] = tms >> 8; rawBlock[2] = tms >> 16; rawBlock[3] = tms >> 24; }
  uint8_t* p = rawBlock + 8 + 3 * rawBlockN;
  p[0] = (uint8_t)(ir >> 16); p[1] = (uint8_t)(ir >> 8); p[2] = (uint8_t)ir;
  rawSamples++;
  if (++rawBlockN >= RAW_BLOCK_N) rawCloseBlock();
}
static void rawStop(const char* why) {
  if (!rawActive) return;
  rawActive = false;
  rawCloseBlock(); rawFlush(); flashSleep();
  evLog("RAW STOP path=%s samples=%lu dropped_blocks=%lu why=%s", rawPath, (unsigned long)rawSamples, (unsigned long)rawDropped, why);
}
static void rawStart(uint32_t seconds, uint8_t ch) {
  if (rawActive) rawStop("restart");
  if (!hasPpg || !ppgEnabled) { replyf(ch, "# RAW: PPG not running\n"); return; }
  if (seconds < 10) seconds = 10;
  if (seconds > 1800) seconds = 1800;
  if (fsState == FS_OK) {
    ringMakeRoom(HG_RING_RAW_BLOCKS, HG_RING_MAX_S_FILES + 1);
    rawSeq = takeSeq();
    hg_ring_make_path('r', rawSeq, rawPath, sizeof rawPath);
    flashSleep();
  } else strcpy(rawPath, "(no flash: USB only)");
  rawSamples = rawDropped = 0; rawBlockN = 0; rawBufLen = 0; rawCh = ch;
  rawEndMs = millis() + seconds * 1000u;
  rawActive = true;
  evLog("RAW START path=%s seconds=%lu boot=%lu t_ms=%lu", rawPath, (unsigned long)seconds, (unsigned long)bootCount, (unsigned long)millis());
}

// =====================================================================
// per-second record + minute summary
// =====================================================================
static float accSumD = 0, accSumD2 = 0, accM0 = 0, accX = 0, accY = 0, accZ = 0;
static uint16_t accN = 0; static bool accImpact = false;
static float aStd = 0; static int16_t zMed = 0; static int16_t zHist[5]; static uint8_t zN = 0;   // z-angle in 0.01 deg (log v2)
static float secAMean = 0, secAM2 = 0; static uint16_t secAN = 0;   // this second of |a|: mean, M2, n (minute a_std, hg_astd.h)
static bool moving = false;
static uint32_t recCount = 0;

// NaN aStd (no IMU samples) -> 0xFFFF. noinline: fw/tools/emu_08_nan.py runs it from the ARM image (1.1.2)
static uint16_t __attribute__((noinline)) astdField(float a) { return (a == a) ? (uint16_t)constrain((long)lroundf(a * 10000.0f), 0L, 65535L) : 0xFFFF; }
static void buildRecordBase(hg_rec_t* r) {
  memset(r, 0, sizeof *r);
  r->t_ms = millis();
  r->t1_c100 = hg_c100(t1C, hasSkin); r->t2_c100 = hg_c100(t2C, hasRef); r->tair_c100 = hg_c100(tairC, hasSht);
  r->rh = (hasSht && rhPct == rhPct) ? (uint8_t)constrain((int)(rhPct + 0.5f), 0, 100) : HG_RH_ABSENT;
  r->hr_q = HG_HRQ_NONE;
  if (charging()) r->flags |= HG_F_CHARGING;
  if (Bluefruit.connected()) r->flags |= HG_F_BLE;
  if (timeValid) r->flags |= HG_F_TIME_VALID;
  if (lowBatMode) r->flags |= HG_F_LOWBAT;
}

static void secondStats() {   // close the IMU second
  if (accN >= 3) {
    float md = accSumD / accN, var = accSumD2 / accN - md * md;
    aStd = sqrtf(var > 0 ? var : 0);
    secAMean = accM0 + md; secAM2 = (var > 0 ? var : 0) * accN; secAN = accN;
    float mx = accX / accN, my = accY / accN, mz = accZ / accN;
    float z = atan2f(mz, sqrtf(mx * mx + my * my)) * 57.29578f;
    zHist[zN % 5] = (int16_t)constrain(lroundf(z * 100.0f), -9000L, 9000L); zN++;
    int16_t t[5]; uint8_t n = zN < 5 ? zN : 5;
    memcpy(t, zHist, n * sizeof t[0]);
    for (uint8_t i = 1; i < n; i++) { int16_t k = t[i]; int j = i - 1; while (j >= 0 && t[j] > k) { t[j + 1] = t[j]; j--; } t[j + 1] = k; }
    zMed = t[n / 2];
  } else { aStd = NAN; secAN = 0; }
  moving = (aStd == aStd) && aStd > MOTION_STD_G;
}

// minute accumulator
struct MinAcc { uint32_t t0; float s1, s2, sa, srh, spi, sast, sz; uint16_t n1, n2, na, nrh, n, nz, nast; float amean, am2; uint32_t an; uint8_t hr[60]; uint8_t nhr; uint8_t q[5]; uint8_t flags, marker; uint16_t aux; uint32_t sred; uint16_t nred; };
static MinAcc ma; static bool maOpen = false;
static void minuteReset(uint32_t t0) { memset(&ma, 0, sizeof ma); ma.t0 = t0; maOpen = true; }
static void minuteAdd(const hg_rec_t* r) {
  if (r->t1_c100 != HG_T_ABSENT) { ma.s1 += r->t1_c100; ma.n1++; }
  if (r->t2_c100 != HG_T_ABSENT) { ma.s2 += r->t2_c100; ma.n2++; }
  if (r->tair_c100 != HG_T_ABSENT) { ma.sa += r->tair_c100; ma.na++; }
  if (r->rh != HG_RH_ABSENT) { ma.srh += r->rh; ma.nrh++; }
  ma.spi += r->pi_100; ma.sz += r->zangle_c100; ma.n++; ma.nz++;
  hg_astd_add(&ma.amean, &ma.am2, &ma.an, secAMean, secAM2, secAN);   // whole-minute a_std as 09 computes it (log v2)
  if (r->astd_1e4 != 0xFFFF) { ma.sast += r->astd_1e4; ma.nast++; }   // 0xFFFF = no IMU that second (1.1.2)
  if (r->hr_q == HG_PPG_Q_OK && r->hr > 0 && ma.nhr < 60) ma.hr[ma.nhr++] = r->hr;
  if (r->hr_q <= 4) ma.q[r->hr_q]++;
  ma.flags |= r->flags & (HG_F_BUTTON | HG_F_CHARGING | HG_F_BLE | HG_F_IMPACT | HG_F_LOWBAT);
  ma.flags = (ma.flags & ~HG_F_TIME_VALID) | (r->flags & HG_F_TIME_VALID);
  if (r->marker && !ma.marker && r->marker != HG_M_FILE) { ma.marker = r->marker; ma.aux = r->aux; ma.flags |= HG_F_MARKER; }
  if (!(r->marker == HG_M_ORAL || r->marker == HG_M_BOOT || r->marker == HG_M_FILE) && r->aux) { ma.sred += r->aux; ma.nred++; }
}
static void minuteClose() {
  if (!maOpen || ma.n == 0) return;
  hg_rec_t r; memset(&r, 0, sizeof r);
  r.t_ms = ma.t0;
  r.t1_c100 = ma.n1 ? (int16_t)lroundf(ma.s1 / ma.n1) : HG_T_ABSENT;
  r.t2_c100 = ma.n2 ? (int16_t)lroundf(ma.s2 / ma.n2) : HG_T_ABSENT;
  r.tair_c100 = ma.na ? (int16_t)lroundf(ma.sa / ma.na) : HG_T_ABSENT;
  r.rh = ma.nrh ? (uint8_t)lroundf(ma.srh / ma.nrh) : HG_RH_ABSENT;
  if (ma.nhr >= 5) {   // median of the seconds with quality OK
    for (uint8_t i = 1; i < ma.nhr; i++) { uint8_t k = ma.hr[i]; int j = i - 1; while (j >= 0 && ma.hr[j] > k) { ma.hr[j + 1] = ma.hr[j]; j--; } ma.hr[j + 1] = k; }
    r.hr = ma.hr[ma.nhr / 2]; r.hr_q = HG_PPG_Q_OK;
  } else {
    r.hr = 0; uint8_t best = HG_HRQ_NONE, bc = 0;
    for (uint8_t q = 0; q < 5; q++) if (ma.q[q] > bc) { bc = ma.q[q]; best = q; }
    r.hr_q = best;
  }
  r.pi_100 = (uint16_t)lroundf(ma.spi / ma.n);
  r.astd_1e4 = ma.nast ? (uint16_t)lroundf(ma.sast / ma.nast) : 0xFFFF;
  r.zangle_c100 = (int16_t)lroundf(ma.sz / ma.nz);
  r.astd_min_1e4 = astdField(hg_astd_std(ma.am2, ma.an));
  r.flags = ma.flags | HG_F_MINUTE;
  r.marker = ma.marker;
  r.aux = ma.marker ? ma.aux : (ma.nred ? (uint16_t)(ma.sred / ma.nred) : 0);
  r.dc8 = (vbat == vbat && vbat > 2.0f) ? (uint8_t)constrain((int)lroundf((vbat - 2.0f) * 100.0f), 1, 255) : 0;
  uint8_t b[HG_REC_SIZE]; hg_rec_pack(&r, b);
  if (minN < sizeof minBuf / HG_REC_SIZE) { memcpy(minBuf + minN * HG_REC_SIZE, b, HG_REC_SIZE); minN++; }
  maOpen = false;
}

static void emitSecond(uint32_t tick) {
  hg_rec_t r; buildRecordBase(&r);
  r.t_ms = tick;
  if (hasPpg && ppgEnabled) {
    r.hr = hrDet.hr_bpm > 0 ? (uint8_t)constrain((int)lroundf(hrDet.hr_bpm), 1, 255) : 0;
    r.hr_q = hrDet.quality;
    r.pi_100 = (uint16_t)constrain((long)lroundf(hrDet.pi_pct * 100.0f), 0L, 65535L);
    float dc = hrDet.dc < 0 ? 0 : hrDet.dc;
    r.dc8 = (uint8_t)constrain((long)(dc / 1024.0f), 0L, 255L);
    r.aux = (uint16_t)constrain((long)(redDc / 4u), 0L, 65535L);
  }
  r.astd_1e4 = astdField(aStd);
  r.zangle_c100 = zMed;
  if (accImpact) r.flags |= HG_F_IMPACT;
  if (pendButton) { r.flags |= HG_F_BUTTON; pendButton = false; }
  if (markTail != markHead) {
    r.marker = markQ[markTail].m;
    if (r.marker == HG_M_ORAL || r.marker == HG_M_BOOT || r.marker == HG_M_FILE) r.aux = markQ[markTail].v;
    r.flags |= HG_F_MARKER;
    markTail = (markTail + 1) & 7;
  }
  uint8_t b[HG_REC_SIZE]; hg_rec_pack(&r, b);
  recCount++;
  char line[HG_REC_HEX_LEN + 2]; hg_hex(b, HG_REC_SIZE, line); line[48] = '\n'; line[49] = 0;
  if (liveUsb) usbPut(line, 49);
  bleQPut(line, 49);
  if (secN < sizeof secBuf / HG_REC_SIZE) { memcpy(secBuf + secN * HG_REC_SIZE, b, HG_REC_SIZE); secN++; } else recsLost++;
  // minute boundaries on the ms-since-boot clock
  uint32_t m0 = tick / 60000u * 60000u;
  if (!maOpen) minuteReset(m0);
  else if (m0 != ma.t0) { minuteClose(); minuteReset(m0); }
  minuteAdd(&r);
}

// =====================================================================
// screen: status page while awake, ST7789 SLPIN + backlight GPIO LOW otherwise
// =====================================================================
static uint32_t screenOffAt = 0;
static void screenWake(uint32_t ms) {
  if (!screenOn) {
    gfx->displayOn();             // SLPOUT (120 ms)
    gfx->fillScreen(C_BLACK);
    screenOn = true;
  }
  blTarget = lowBatMode ? BL_LOWBAT_PCT : BL_NORMAL_PCT;
  applyBacklight();
  screenOffAt = millis() + ms;
}
static void screenSleep() {
  if (!screenOn) return;
  screenOn = false;
  applyBacklight();               // -> backlight GPIO LOW, PWM released
  gfx->displayOff();              // SLPIN (120 ms)
}
static void drawLine(int row, uint16_t col, const char* txt) {
  int y = 6 + row * 25;
  gfx->fillRect(0, y, 240, 25, C_BLACK);
  gfx->setCursor(4, y + 19);
  gfx->setTextColor(col);
  gfx->print(txt);
}
static void fmtT(char* o, size_t n, float v, bool ok) { if (ok && v == v) snprintf(o, n, "%.2f", v); else snprintf(o, n, "--.--"); }
static void drawStatus() {
  if (!screenOn) return;
  gfx->setFont(u8g2_font_10x20_t_greek);
  gfx->setUTF8Print(true);
  gfx->setTextSize(1);
  char a[12], b2[12], l[40];
  drawLine(0, lowBatMode ? C_RED : C_GREY, lowBatMode ? "CHARGE ME  (logging on)" : "HG 08_logger " HG_FW_SHORT);
  fmtT(a, sizeof a, t1C, hasSkin); fmtT(b2, sizeof b2, t2C, hasRef);
  snprintf(l, sizeof l, "T1 %s  T2 %s", a, b2); drawLine(1, C_WHITE, l);
  fmtT(a, sizeof a, tairC, hasSht);
  if (hasSht && rhPct == rhPct) snprintf(l, sizeof l, "Air %s C  %d %%", a, (int)lroundf(rhPct)); else snprintf(l, sizeof l, "Air --.-- C");
  drawLine(2, C_WHITE, l);
  static const char* QW[] = { "NO SKIN", "LOOSE", "MOTION", "IRREG", "OK" };
  if (hasPpg && ppgEnabled) snprintf(l, sizeof l, "HR %3d %-7s PI %.2f", (int)lroundf(hrDet.hr_bpm), QW[hrDet.quality], hrDet.pi_pct);
  else snprintf(l, sizeof l, "HR --- (PPG %s)", hasPpg ? "off" : "missing");
  drawLine(3, (hasPpg && ppgEnabled && hrDet.quality == HG_PPG_Q_OK) ? C_GREEN : C_ORANGE, l);
  snprintf(l, sizeof l, "Move %.4f g  z %.2f", aStd == aStd ? aStd : 0.0f, zMed / 100.0f); drawLine(4, C_WHITE, l);
  snprintf(l, sizeof l, "Bat %.2f V %d%% %s", vbat == vbat ? vbat : 0.0f, batteryPct(vbat), charging() ? "USB" : ""); drawLine(5, (vbat == vbat && vbat < VBAT_SOFT) ? C_ORANGE : C_WHITE, l);
  if (lastMarker) snprintf(l, sizeof l, "Mark %u %s %lus ago", lastMarker, MARK_NAME[lastMarker], (unsigned long)((millis() - lastMarkerMs) / 1000));
  else snprintf(l, sizeof l, "Mark: none yet");
  drawLine(6, C_WHITE, l);
  if (fsState == FS_OK) snprintf(l, sizeof l, "Log %s %s", curPath + 5, flushErr ? "ERR" : "OK");
  else snprintf(l, sizeof l, "Log: %s", fsState == FS_NO_FLASH ? "NO FLASH" : "FS ERROR");
  drawLine(7, (fsState == FS_OK && !flushErr) ? C_GREEN : C_RED, l);
  snprintf(l, sizeof l, "Time %s  BLE %s", timeValid ? "set" : "NOT SET", Bluefruit.connected() ? "on" : "adv");
  drawLine(8, timeValid ? C_WHITE : C_ORANGE, l);
  uint32_t up = millis() / 1000;
  snprintf(l, sizeof l, "Up %luh%02lum  boot %lu", (unsigned long)(up / 3600), (unsigned long)(up / 60 % 60), (unsigned long)bootCount);
  drawLine(9, C_GREY, l);
  if (rawActive) { snprintf(l, sizeof l, "RAW %lus left", (unsigned long)((rawEndMs - millis()) / 1000)); drawLine(10, C_ORANGE, l); }
  else drawLine(10, C_GREY, "");
}

// =====================================================================
// button: short = marker 9 "button", long (2 s) = marker 8 "help"; both vibrate + wake screen
// =====================================================================
static void serviceButton() {
  static bool stable = false, lastRaw = false, longSent = false;
  static uint32_t rawChanged = 0, pressedAt = 0;
  uint32_t now = millis();
  bool raw = (digitalRead(PIN_BTN) == LOW);
  if (raw != lastRaw) { lastRaw = raw; rawChanged = now; }
  if (raw != stable && now - rawChanged >= 30) {
    stable = raw;
    if (stable) { pressedAt = now; longSent = false; screenWake(SCREEN_ON_MS); }
    else if (!longSent) { pendButton = true; queueMarker(HG_M_BUTTON, 0, "button"); vibrate(PAT_SHORT); }
  }
  if (stable && !longSent && now - pressedAt >= LONG_PRESS_MS) {
    longSent = true; pendButton = true;
    queueMarker(HG_M_HELP, 0, "button-long");
    vibrate(PAT_LONG);
  }
}

// =====================================================================
// dump: stream files as text lines without blocking the loop
//   "# FILE <path> size=<n>"  then record lines (48 hex) / 'R' raw lines / 'E ' event lines
//   "# END <path> bytes=<n>"   ...   "# DUMP DONE files=<n>"
// =====================================================================
static char dumpList[HG_RING_MAX_FILES][24]; static uint8_t dumpN = 0, dumpI = 0;
static uint8_t eraseN = 0, eraseI = 0;     // erase reuses dumpList
static uint32_t dumpOff = 0, dumpSize = 0; static uint8_t dumpCh = 0; static bool dumpHdr = false;
static char dumpCarry[180]; static uint16_t dumpCarryN = 0;
enum { DUMP_ALL = 0, DUMP_MIN = 1, DUMP_NEW = 2 };
static uint8_t dumpMode = DUMP_ALL;
static void dumpStart(uint8_t mode, uint8_t ch) {
  bool minOnly = (mode == DUMP_MIN);
  if (fsState != FS_OK) { replyf(ch, "# DUMP: storage %s\n", FS_NAME[fsState]); return; }
  if (erasing) { replyf(ch, "# DUMP: erase in progress\n"); return; }
  flushAll();
  listLog();
  dumpN = 0; dumpI = 0; dumpOff = 0; dumpHdr = false; dumpCarryN = 0; dumpCh = ch;
  if (minOnly) { strcpy(dumpList[dumpN++], "/log/min.bin"); }
  else {
    strcpy(dumpList[dumpN++], "/log/events.txt");
    // s and r files in sequence order, then min.bin
    bool used[HG_RING_MAX_FILES] = {false};
    for (;;) {
      int best = -1;
      for (int i = 0; i < ringN; i++) if (!used[i] && (ringFiles[i].kind == 's' || ringFiles[i].kind == 'r') &&
                                          (mode != DUMP_NEW || ringFiles[i].seq >= bootf.dumped_next) &&
                                          (best < 0 || ringFiles[i].seq < ringFiles[best].seq)) best = i;
      if (best < 0 || dumpN >= HG_RING_MAX_FILES - 1) break;
      used[best] = true;
      snprintf(dumpList[dumpN++], 24, "/log/%s", ringNames[best]);
    }
    strcpy(dumpList[dumpN++], "/log/min.bin");
  }
  dumpActive = true; dumpMode = mode;
  replyf(ch, "# DUMP START mode=%s files=%u boot=%lu t_ms=%lu unix=%lu\n", mode == DUMP_NEW ? "new" : (minOnly ? "min" : "all"), dumpN, (unsigned long)bootCount, (unsigned long)millis(), (unsigned long)nowUnix());
}
static void dumpStop(const char* why) {
  if (!dumpActive) return;
  dumpActive = false;
  replyf(dumpCh, "# DUMP %s\n", why);
  flashSleep();
}
static uint16_t dumpRoom() {
  if (dumpCh & CH_USB) return Serial ? (uint16_t)max(0, Serial.availableForWrite()) : 0;
  return bleReady() ? bleQFree() : 0;
}
static void dumpService() {
  if (!dumpActive) return;
  if ((dumpCh & CH_USB) && !Serial) { dumpStop("ABORTED usb gone"); return; }
  if ((dumpCh & CH_BLE) && !bleReady()) { dumpStop("ABORTED ble gone"); return; }
  for (int iter = 0; iter < 16; iter++) {
    if (dumpI >= dumpN) {
      // everything older than the file being written now has been sent once: "dump new" skips it next time
      if (dumpMode != DUMP_MIN && curSeq >= bootf.dumped_next) { bootf.dumped_next = curSeq; bootSave(); }
      dumpStop("DONE");
      return;
    }
    const char* path = dumpList[dumpI];
    bool isTxt = strstr(path, ".txt") != NULL, isRaw = path[5] == 'r';
    uint16_t lineBytes = isRaw ? 77 : (isTxt ? 64 : HG_REC_SIZE);
    if (dumpRoom() < (isRaw ? 170 : (isTxt ? 200 : 64))) return;   // wait for the channel (USB CDC buffer: 256 B)
    if (!dumpHdr) {
      File f(logFS); dumpSize = 0;
      if (f.open(path, FILE_O_READ)) { dumpSize = f.size(); f.close(); }
      outf(dumpCh, "# FILE %s size=%lu\n", path, (unsigned long)dumpSize);
      dumpHdr = true; dumpOff = 0; dumpCarryN = 0;
      continue;
    }
    if (dumpOff >= dumpSize) {
      if (isTxt && dumpCarryN) { dumpCarry[dumpCarryN] = 0; outf(dumpCh, "E %s\n", dumpCarry); dumpCarryN = 0; }
      outf(dumpCh, "# END %s bytes=%lu\n", path, (unsigned long)dumpOff);
      dumpI++; dumpHdr = false;
      continue;
    }
    uint8_t buf[80];
    uint32_t want = lineBytes; if (dumpOff + want > dumpSize) want = dumpSize - dumpOff;
    File f(logFS); uint32_t got = 0;
    if (f.open(path, FILE_O_READ)) { f.seek(dumpOff); got = f.read(buf, want); f.close(); }
    if (got == 0) { outf(dumpCh, "# READ ERROR %s at %lu\n", path, (unsigned long)dumpOff); dumpI++; dumpHdr = false; continue; }
    dumpOff += got;
    if (isTxt) {
      for (uint32_t i = 0; i < got; i++) {
        char c = (char)buf[i];
        if (c == '\n' || dumpCarryN >= sizeof dumpCarry - 1) { dumpCarry[dumpCarryN] = 0; outf(dumpCh, "E %s\n", dumpCarry); dumpCarryN = 0; }
        if (c != '\n') dumpCarry[dumpCarryN++] = c;
      }
    } else if (isRaw) {
      if (got == 77) rawLine(dumpCh, buf, (uint8_t)(((dumpOff - got) % sizeof rawBlock) / 77));
    } else {
      char h[HG_REC_HEX_LEN + 2];
      if (got == HG_REC_SIZE) { hg_hex(buf, got, h); h[48] = '\n'; h[49] = 0; outLine(dumpCh, h); }
    }
  }
}

// =====================================================================
// commands (USB serial and BLE UART, one per line)
// =====================================================================
static void printStat(uint8_t ch) {
  uint32_t up = millis() / 1000;
  replyf(ch, "# STAT fw=%s boot=%lu reset=%s(0x%08lx) up=%luh%02lum%02lus\n", HG_FW_VERSION, (unsigned long)bootCount,
         resetName(resetReason), (unsigned long)resetReason, (unsigned long)(up / 3600), (unsigned long)(up / 60 % 60), (unsigned long)(up % 60));
  replyf(ch, "# STAT resets: watchdog=%lu power/brownout=%lu (since first use) quick_boots=%u bootloop_hold=%d\n",
         (unsigned long)bootf.wdt_resets, (unsigned long)bootf.other_resets, quickBoots, bootLoop);
  replyf(ch, "# STAT time=%s unix=%lu t_ms=%lu\n", timeValid ? "SET" : "NOT-SET", (unsigned long)nowUnix(), (unsigned long)millis());
  replyf(ch, "# STAT vbat=%.3fV (%u%%) charging=%d lowbat_mode=%d\n", vbat == vbat ? vbat : 0.0f, batteryPct(vbat), charging(), lowBatMode);
  replyf(ch, "# STAT REF TMP117 0x49: %s  T2=%.2f  T1-T2=%.2f\n", hasRef ? "PRESENT" : "NOT FOUND (=1 expected once the REF sensor is fitted)",
         t2C, t1C - t2C);
  replyf(ch, "# STAT sensors: TMP117-0x48=%d TMP117-0x49=%d SHTC3=%d ICM20649=%d(0x%02x,%s) MAX30102=%d(%s) DRV2605=%d\n",
         hasSkin, hasRef, hasSht, hasImu, imuAddr, imuLowPower ? "accel-LP-25Hz" : "accel-LN-gyro-off", hasPpg, ppgEnabled ? "on" : "off", hasDrv);
  replyf(ch, "# STAT now: T1=%.2f T2=%.2f Tair=%.2f RH=%.1f HR=%.1f q=%u PI=%.3f a_std=%.4f z=%.2f\n",
         t1C, t2C, tairC, rhPct, hrDet.hr_bpm, hrDet.quality, hrDet.pi_pct, aStd, zMed / 100.0f);
  replyf(ch, "# STAT ppg samples=%lu overflows=%lu i2c_err=%lu  usb_drops=%lu ble_drops=%lu raw_usb_drops=%lu loop_stack_free_min=%lu B\n",
         (unsigned long)ppgSamples, (unsigned long)ppgOverflows, (unsigned long)ppgReadErrors, (unsigned long)usbDrops, (unsigned long)bleDrops,
         (unsigned long)rawUsbDrops, (unsigned long)uxTaskGetStackHighWaterMark(NULL) * 4u);
  replyf(ch, "# STAT i2c ok=%lu nack=%lu timeouts=%lu bus_clears=%lu bus_at_boot=%s  flash_jedec=%06lx flash_wakes=%lu flash_wake_fails=%lu dumped_next=s%04u undumped_deleted=%lu\n",
         (unsigned long)hg_i2c_stats.ok, (unsigned long)hg_i2c_stats.nack, (unsigned long)hg_i2c_stats.timeouts, (unsigned long)hg_i2c_stats.bus_clears,
         i2cBusOkAtBoot ? "ok" : "STUCK-LOW", (unsigned long)flashJedec, (unsigned long)flashWakes,
         (unsigned long)flashWakeFails, bootf.dumped_next, (unsigned long)undumpedDeleted);
  replyf(ch, "# STAT storage=%s (%s) file=%s recs_in_file=%lu records=%lu flush_ok=%lu flush_err=%lu lost=%lu deleted=%lu ev_dropped=%lu\n",
         FS_NAME[fsState], fsMsg, curPath, (unsigned long)recsInFile, (unsigned long)recCount, (unsigned long)flushOk,
         (unsigned long)flushErr, (unsigned long)recsLost, (unsigned long)filesDeleted, (unsigned long)evDropped);
  if (fsState == FS_OK) {
    listLog();
    uint32_t fb = freeBlocks();
    replyf(ch, "# STAT free=%lu bytes (%lu of %lu blocks)%s\n", (unsigned long)fb * 4096u, (unsigned long)fb, (unsigned long)logCfg.block_count, fsFull ? " FULL" : "");
    for (int i = 0; i < ringN; i++) replyf(ch, "# STAT   /log/%s %lu\n", ringNames[i], (unsigned long)ringFiles[i].size);
    flashSleep();
  }
  if (rawActive) replyf(ch, "# STAT raw active path=%s samples=%lu left=%lus\n", rawPath, (unsigned long)rawSamples, (unsigned long)((rawEndMs - millis()) / 1000));
}
static void printHelp(uint8_t ch) {
  static const char* H[] = {
    "# commands (USB serial or BLE UART, one per line):\n",
    "#   stat                 status: sensors, battery, files, free space, resets\n",
    "#   time <unix>          set the clock (Mac Terminal: date +%s)\n",
    "#   mark <n|name> [T]    1 donned 2 loose 3 off 4 shower 5 out 6 home 7 oral <degC> 8 help 9 custom\n",
    "#   dump | dump new      stream all files | only files not dumped yet (+ events, min.bin); dump stop\n",
    "#   dumpmin              stream only min.bin\n",
    "#   raw <s>              record <s> seconds (10..1800, default 600) of raw IR at 100 sps; raw stop\n",
    "#   live on|off          1 Hz hex lines on USB (BLE always streams)\n",
    "#   screen | buzz        wake the screen 15 s | test vibration\n",
    "#   erase YES            delete every log file (USB only)\n",
    "#   format YES           re-create the file system: only when stat says CORRUPT (USB only)\n",
  };
  for (auto s : H) replyf(ch, "%s", s);
}
static bool eqi(const char* a, const char* b) { return strcasecmp(a, b) == 0; }
static void handleCommand(char* line, uint8_t ch) {
  char* argv[4]; int argc = 0;
  for (char* t = strtok(line, " \t\r"); t && argc < 4; t = strtok(NULL, " \t\r")) argv[argc++] = t;
  if (!argc) return;
  const char* src = (ch == CH_USB) ? "usb" : "ble";
  if (eqi(argv[0], "help") || eqi(argv[0], "?")) printHelp(ch);
  else if (eqi(argv[0], "stat")) printStat(ch);
  else if (eqi(argv[0], "time") && argc < 2) replyf(ch, "# TIME needs the unix time: time <unix>  (Mac Terminal: date +%%s)\n");
  else if (eqi(argv[0], "time")) {
    uint32_t u = strtoul(argv[1], NULL, 10);
    if (u < 1700000000UL || u > 4000000000UL) { replyf(ch, "# TIME rejected: %s (expect unix seconds, e.g. 1763280000)\n", argv[1]); return; }
    epochAtSync = u; msAtSync = millis(); timeValid = true;
    evLog("TIME boot=%lu t_ms=%lu unix=%lu src=%s", (unsigned long)bootCount, (unsigned long)msAtSync, (unsigned long)u, src);
    queueMarker(HG_M_TIME, 0, src);
  }
  else if (eqi(argv[0], "mark") && argc >= 2) {
    int m = -1;
    if (isdigit((unsigned char)argv[1][0])) m = atoi(argv[1]);
    else for (int i = 1; i <= 9; i++) if (eqi(argv[1], MARK_NAME[i])) m = i;
    if (eqi(argv[1], "custom")) m = 9;
    if (m < 1 || m > 9) { replyf(ch, "# MARK rejected: use 1..9 or donned/loose/off/shower/out/home/oral/help/custom\n"); return; }
    uint16_t v = 0;
    if (m == HG_M_ORAL) {
      float t = 0;
      if (argc >= 3) {                       // accept 36.85 and 36,85 (Greek decimal comma, T6a m1)
        char num[16]; strncpy(num, argv[2], sizeof num - 1); num[sizeof num - 1] = 0;
        for (char* c = num; *c; c++) if (*c == ',') *c = '.';
        char* end = NULL; t = strtof(num, &end);
        if (end == num || *end) t = 0;       // trailing junk -> rejected
      }
      if (t < 30.0f || t > 43.0f) { replyf(ch, "# MARK oral needs the reading, e.g. mark oral 36.85 (got '%s')\n", argc >= 3 ? argv[2] : ""); return; }
      v = (uint16_t)lroundf(t * 100.0f);
      replyf(ch, "# MARK oral stored %u.%02u C\n", v / 100, v % 100);
    }
    queueMarker((uint8_t)m, v, src);
  }
  else if (eqi(argv[0], "dump")) {
    if (argc >= 2 && eqi(argv[1], "stop")) dumpStop("STOPPED");
    else dumpStart(argc >= 2 && eqi(argv[1], "new") ? DUMP_NEW : DUMP_ALL, ch);
  }
  else if (eqi(argv[0], "dumpmin")) dumpStart(DUMP_MIN, ch);
  else if (eqi(argv[0], "raw")) { if (argc >= 2 && eqi(argv[1], "stop")) rawStop("command"); else rawStart(argc >= 2 ? strtoul(argv[1], NULL, 10) : 600, ch); }
  else if (eqi(argv[0], "live") && argc >= 2) { liveUsb = eqi(argv[1], "on"); replyf(ch, "# LIVE usb=%d\n", liveUsb); }
  else if (eqi(argv[0], "screen")) screenWake(SCREEN_ON_MS);
  else if (eqi(argv[0], "buzz")) vibrate(PAT_SHORT);
  else if (eqi(argv[0], "flashdiag")) flashDiag(ch);
  else if (eqi(argv[0], "erase")) {
    if (argc < 2 || strcmp(argv[1], "YES") != 0) { replyf(ch, "# ERASE: type  erase YES  to delete every log file\n"); return; }
    if (ch != CH_USB) { replyf(ch, "# ERASE only over USB\n"); return; }
    if (fsState != FS_OK) { replyf(ch, "# ERASE: storage %s\n", FS_NAME[fsState]); return; }
    dumpStop("STOPPED by erase"); rawStop("erase");
    flushAll(); listLog();
    eraseN = 0;
    for (int i = 0; i < ringN && eraseN < HG_RING_MAX_FILES; i++) if (ringFiles[i].kind != 'b') snprintf(dumpList[eraseN++], 24, "/log/%.11s", ringNames[i]);
    eraseI = 0; erasing = true;                // one file per loop pass: no long stall near the watchdog (T6a m8)
    replyf(ch, "# ERASE started: %u files\n", eraseN);
  }
  else if (eqi(argv[0], "format")) {
    if (argc < 2 || strcmp(argv[1], "YES") != 0) { replyf(ch, "# FORMAT: type  format YES  (destroys all logs)\n"); return; }
    if (ch != CH_USB) { replyf(ch, "# FORMAT only over USB\n"); return; }
    if (fsState == FS_NO_FLASH) { replyf(ch, "# FORMAT: no flash\n"); return; }
    if (fsState == FS_OK) { replyf(ch, "# FORMAT refused: storage is OK (use erase YES to clear logs)\n"); return; }
    dumpStop("STOPPED by format"); rawStop("format");
    logFS.end(); logFS.format();
    fsState = logFS.begin() ? FS_OK : FS_CORRUPT;
    strcpy(fsMsg, fsState == FS_OK ? "formatted by command" : "format failed");
    if (fsState == FS_OK) { logFS.mkdir("/log"); bootf.boot_count = bootCount; bootSave(); newHourFile(); }
    replyf(ch, "# FORMAT %s\n", FS_NAME[fsState]);
    flashSleep();
  }
  else replyf(ch, "# unknown command: %s  (type help)\n", argv[0]);
}
static void eraseService() {
  if (!erasing) return;
  if (eraseI < eraseN) { logFS.remove(dumpList[eraseI++]); return; }
  erasing = false;
  secN = 0; minN = 0;
  bootf.dumped_next = bootf.next_seq; bootSave();
  evLog("ERASE boot=%lu t_ms=%lu files=%u", (unsigned long)bootCount, (unsigned long)millis(), eraseN);
  newHourFile(); flushAll();
  replyf(CH_USB, "# ERASE done\n");
}
static void serviceCommands() {
  static char ub[96]; static uint8_t un = 0;
  while (Serial && Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') { if (un) { ub[un] = 0; handleCommand(ub, CH_USB); un = 0; } }
    else if (un < sizeof ub - 1) ub[un++] = c;
  }
  static char bb[96]; static uint8_t bn = 0;
  while (bleuart.available()) {
    char c = bleuart.read();
    if (c == '\n' || c == '\r') { if (bn) { bb[bn] = 0; handleCommand(bb, CH_BLE); bn = 0; } }
    else if (bn < sizeof bb - 1) bb[bn++] = c;
  }
}

// =====================================================================
// BLE
// =====================================================================
static void bleSetup() {
  Bluefruit.autoConnLed(false);                    // no blue LED blinking (power, and it is a wearable)
  Bluefruit.configPrphBandwidth(BANDWIDTH_LOW);    // 1 link, MTU 23, small buffers (R4 A1)
  Bluefruit.begin(1, 0);
#if HG_DCDC
  sd_power_dcdc_mode_set(NRF_POWER_DCDC_ENABLE);   // R4 A6: the core does not enable it
#endif
  Bluefruit.setTxPower(0);
  Bluefruit.setName("HeatGuardian");
  bledis.setManufacturer("Heat Guardian");
  bledis.setModel("Band A 08_logger");
  bledis.setFirmwareRev(HG_FW_VERSION);
  bledis.begin();
  bleuart.begin();
  blebas.begin(); blebas.write(batteryPct(vbat));
  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(bleuart);
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 1636);     // 20 ms for 30 s, then 1022.5 ms (units of 0.625 ms)
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);
}

// =====================================================================
// setup / loop
// =====================================================================
static bool* devFlag(int d) {
  switch (d) { case DEV_SKIN: return &hasSkin; case DEV_REF: return &hasRef; case DEV_SHT: return &hasSht;
               case DEV_IMU: return &hasImu; case DEV_PPG: return &hasPpg; default: return &hasDrv; }
}
// probe (and initialise) one device; used at boot and once a minute for missing devices
static bool probeDev(int d) {
  switch (d) {
    case DEV_SKIN: return tmpProbe(0x48);
    case DEV_REF:  return tmpProbe(0x49);
    case DEV_SHT:  return shtProbe();
    case DEV_IMU:
      if (imuProbe(0x68)) imuAddr = 0x68; else if (imuProbe(0x69)) imuAddr = 0x69; else return false;
      return imuConfigure();
    case DEV_PPG:
      if (!ppgInit()) return false;
      hg_ppg_init(&hrDet);
      ppgEnabled = true;
      if (lowBatMode) ppgEnable(false);
      return true;
    default: return drvInit();
  }
}

// boot-loop detector: boot.bin's quick_boots (see BootFile); >= 3 -> no deletions for 30 min.
// 0xA0 | n = n boots in a row that did not reach 10 min of uptime.
// quickBoots and bootLoop are declared with the storage code
// bootLoop (declared with the storage code): >= 3 quick boots -> no file deletions for 30 min
static const uint32_t BOOTLOOP_HOLD_MS = 30u * 60u * 1000u;

static uint32_t setupMs = 0;
void setup() {
  resetReason = readResetReason();                 // the core's init() saved and cleared RESETREAS (T6a M1)
  pinMode(VBAT_ENABLE, OUTPUT); digitalWrite(VBAT_ENABLE, LOW);   // review rule: P0.14 LOW
  pinMode(LCD_BL, OUTPUT); digitalWrite(LCD_BL, LOW);
  pinMode(PIN_BTN, INPUT_PULLUP);
  pinMode(PIN_NCHG, INPUT_PULLUP);
  vbat = readVbat();                               // VBAT before anything else (R4 A8.1)

  Serial.begin(115200);
  while (!Serial && millis() < 3000) delay(10);    // bounded
  wdtStart(8000);                                  // from here on a hang resets the board; fed only in loop()
  outf(CH_USB, "\n# Heat Guardian %s  reset=%s(0x%08lx)  vbat=%.3f V\n", HG_FW_VERSION, resetName(resetReason),
       (unsigned long)resetReason, vbat);

  // 1. recording and console FIRST, so a stuck I2C bus still leaves a log + BLE (T6a M2)
  bootQspi[0] = NRF_QSPI->ENABLE; bootQspi[1] = NRF_QSPI->PSEL.SCK; bootQspi[2] = NRF_QSPI->PSEL.CSN; bootQspi[3] = NRF_QSPI->PSEL.IO0;
  storageInit();
  bleSetup();
  lowBatMode = (vbat == vbat) && vbat > 2.5f && vbat < VBAT_CHARGE_ME && !charging();
  evLog("BOOT boot=%lu t_ms=%lu fw=%s reset=%s rr=0x%08lx vbat=%.3f lowbat=%d quick_boots=%u bootloop=%d storage=%s(%s) jedec=%06lx",
        (unsigned long)bootCount, (unsigned long)millis(), HG_FW_VERSION, resetName(resetReason), (unsigned long)resetReason, vbat,
        lowBatMode, quickBoots, bootLoop, FS_NAME[fsState], fsMsg, (unsigned long)flashJedec);
  bootHourFile();
  queueMarker(HG_M_BOOT, (uint16_t)bootCount, "boot");
  flushAll();                                      // BOOT line + file header on flash now, before any sensor traffic

  // 2. screen (SPI, independent of I2C)
  SPI.setPins(SPI_DUMMY_MISO, LCD_SCK, LCD_MOSI);  // keep D9 (CS) an output
  if (!bus->begin(8000000, SPI_MODE0)) outf(CH_USB, "# bus->begin() failed\n");   // SPI mode 0 fix (04c)
  if (!gfx->begin(GFX_SKIP_DATABUS_BEGIN)) outf(CH_USB, "# gfx->begin() failed\n");
  gfx->fillScreen(C_BLACK);
  screenOn = true;                                 // gfx->begin() leaves the panel awake

  // 3. I2C sensors, every transfer bounded (hg_i2c.c)
  i2cPins();
  if (!i2cLinesHigh()) { hg_i2c_bus_clear(); delay(1); }
  i2cBusOkAtBoot = i2cLinesHigh();
  hg_i2c_begin(5, 4);                              // SCL P0.05 (D5), SDA P0.04 (D4), 100 kHz
  hg_ppg_init(&hrDet);
  if (i2cBusOkAtBoot) for (int d = 0; d < DEV_N; d++) *devFlag(d) = probeDev(d);
  if (hasPpg) ppgEnable(!lowBatMode);              // also clears the FIFO filled during setup
  evLog("SENSORS t_ms=%lu bus=%s skin=%d ref=%d sht=%d imu=%d imu_lp=%d ppg=%d drv=%d i2c_timeouts=%lu",
        (unsigned long)millis(), i2cBusOkAtBoot ? "ok" : "STUCK-LOW", hasSkin, hasRef, hasSht, hasImu, imuLowPower, hasPpg, hasDrv,
        (unsigned long)hg_i2c_stats.timeouts);

  screenWake(SCREEN_ON_MS);
  drawStatus();
  setupMs = millis();
  outf(CH_USB, "# ready in %lu ms. Type help.\n", (unsigned long)setupMs);
}

void loop() {
  static uint32_t nextImu = 0, nextSec = 0, nextTmp = 500, tmpReadAt = 0, nextSht = 1000, shtReadAt = 0;
  static uint32_t nextVbat = 10000, nextProbe = 60000, nextStatus = 10000, nextDraw = 0, nextPpg = 0;
  static bool tmpPending = false, shtPending = false;
  wdtFeed();
  uint32_t now = millis();
  if (nextSec == 0) nextSec = (now / 1000 + 1) * 1000;

  // MAX30102 FIFO every 100 ms (~10 samples per burst; the FIFO holds 32 = 320 ms)
  if ((int32_t)(now - nextPpg) >= 0) { nextPpg = now + 100; ppgService(moving); }

  // IMU 25 Hz
  if (hasImu && (int32_t)(now - nextImu) >= 0) {
    nextImu = now + IMU_PERIOD_MS;
    float x, y, z;
    if (imuRaw(&x, &y, &z)) {
      float m = sqrtf(x * x + y * y + z * z);
      if (accN == 0) accM0 = m;
      float d = m - accM0;
      accSumD += d; accSumD2 += d * d; accX += x; accY += y; accZ += z; accN++;
      if (m >= IMPACT_G) accImpact = true;
    }
  }

  // TMP117 one-shot every 5 s (not within 2 s of a buzz), read 200 ms later
  if (!tmpPending && (int32_t)(now - nextTmp) >= 0 && !recentlyBuzzed()) {
    nextTmp = now + TMP_PERIOD_MS;
    bool a = hasSkin && tmpTrigger(0x48);
    bool b = hasRef && tmpTrigger(0x49);
    if (a || b) { tmpPending = true; tmpReadAt = now + TMP_CONV_MS; }
  }
  if (tmpPending && (int32_t)(now - tmpReadAt) >= 0) {
    tmpPending = false;
    // a failed read keeps the last value; 3 failures in a row mark the sensor missing (T6a m7)
    if (hasSkin && !devResult(DEV_SKIN, tmpRead(0x48, &t1C)) && !hasSkin) t1C = NAN;
    if (hasRef && !devResult(DEV_REF, tmpRead(0x49, &t2C)) && !hasRef) t2C = NAN;
  }
  // SHTC3 every 10 s
  if (hasSht && !shtPending && (int32_t)(now - nextSht) >= 0 && !recentlyBuzzed()) {
    nextSht = now + SHT_PERIOD_MS;
    if (shtTrigger()) { shtPending = true; shtReadAt = now + SHT_CONV_MS; }
  }
  if (shtPending && (int32_t)(now - shtReadAt) >= 0) {
    shtPending = false;
    if (!devResult(DEV_SHT, shtRead()) && !hasSht) tairC = rhPct = NAN;
  }

  serviceButton();
  serviceMotor();
  serviceCommands();
  dumpService();
  eraseService();
  rawUsbService();
  bleService();

  // 1 Hz record
  while ((int32_t)(now - nextSec) >= 0) {
    uint32_t tick = nextSec;
    nextSec += 1000;
    if (now - tick >= 1000) continue;            // stalled > 1 s: leave a gap (the parser reports it)
    secondStats();
    accSumD = accSumD2 = accX = accY = accZ = 0; accN = 0;
    emitSecond(tick);
    accImpact = false;
    bool flushNow = (tick % 60000u == 0) || secN >= 60 || tick == 10000u || tick == 30000u;   // early flushes: short boots keep their seconds (T6a n2)
    // red LED 1 s of every 4 s for the DC-ratio contact check
    if (hasPpg && ppgEnabled) {
      uint32_t s = tick / 1000;
      if (redOn && redN) redDc = redSum / redN;
      ppgSetRed((s % 4) == 0);
    }
    if (rawActive && (int32_t)(now - rawEndMs) >= 0) rawStop("done");
    if (rawActive && rawBufLen >= 10 * sizeof rawBlock) { rawFlush(); flashSleep(); }
    if (flushNow) flushAll(false);               // once a minute (or if a stall filled the buffer)
  }

  // battery every 10 s; low-battery mode with hysteresis
  if ((int32_t)(now - nextVbat) >= 0) {
    nextVbat = now + 10000;
    float v = readVbat();
    if (v == v) vbat = v;
    bool chg = charging();
    if (!lowBatMode && vbat == vbat && vbat > 2.5f && vbat < VBAT_PPG_OFF && !chg) {
      lowBatMode = true; ppgEnable(false); rawStop("low battery");
      evLog("LOWBAT ON t_ms=%lu vbat=%.3f", (unsigned long)now, vbat);
      screenWake(5000);
    } else if (lowBatMode && (chg || (vbat == vbat && vbat >= VBAT_RESUME))) {
      lowBatMode = false; if (hasPpg) { ppgEnable(true); ppgSetRed(false); }
      evLog("LOWBAT OFF t_ms=%lu vbat=%.3f chg=%d", (unsigned long)now, vbat, chg);
    }
    blebas.write(batteryPct(vbat));
  }

  // re-probe sensors that went missing (loose Qwiic plug), once a minute
  if ((int32_t)(now - nextProbe) >= 0) {
    nextProbe = now + 60000;
    if (!i2cLinesHigh()) hg_i2c_recover();         // SDA/SCL held low: TWIM off, 9-clock clear, TWIM on (T6a n4)
    if (i2cLinesHigh()) {
      for (int d = 0; d < DEV_N; d++) if (!*devFlag(d) && probeDev(d)) {
        *devFlag(d) = true; devFails[d] = 0;
        if (d == DEV_PPG) ppgEnable(!lowBatMode);
        evLog("SENSOR BACK %s t_ms=%lu", DEV_NAME[d], (unsigned long)now);
      }
    }
    static bool quickCleared = false;              // 10 min of uptime = not a boot loop (one boot.bin write)
    if (!quickCleared && now >= 10u * 60u * 1000u) {
      quickCleared = true;
      if (fsState == FS_OK && bootf.quick_boots) { bootf.quick_boots = 0; bootSave(); flashSleep(); }
    }
    if (bootLoop && now >= BOOTLOOP_HOLD_MS) { bootLoop = false; evLog("BOOTLOOP CLEARED t_ms=%lu", (unsigned long)now); }
  }

  // human-readable status comment every 10 s on USB
  if ((int32_t)(now - nextStatus) >= 0) {
    nextStatus = now + 10000;
    outf(CH_USB, "# S boot=%lu t_ms=%lu T1=%.2f T2=%.2f Tair=%.2f RH=%.0f HR=%.0f q=%u PI=%.2f a=%.4f z=%.2f bat=%.2f log=%s stack_free=%lu%s\n",
         (unsigned long)bootCount, (unsigned long)now, t1C, t2C, tairC, rhPct, hrDet.hr_bpm, hrDet.quality, hrDet.pi_pct, aStd, zMed / 100.0f,
         vbat, fsState == FS_OK ? "OK" : FS_NAME[fsState], (unsigned long)uxTaskGetStackHighWaterMark(NULL) * 4u, timeValid ? "" : " TIME-NOT-SET");
  }

  // screen
  if (screenOn) {
    if ((int32_t)(now - screenOffAt) >= 0 && !motorBusy) screenSleep();
    else if ((int32_t)(now - nextDraw) >= 0) { nextDraw = now + 1000; drawStatus(); }
  }

  delay(10);  // FreeRTOS tickless idle -> System ON sleep between passes
}
