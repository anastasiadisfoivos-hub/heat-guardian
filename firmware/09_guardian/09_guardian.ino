// =====================================================================
// Heat Guardian Band A - 09_guardian: the product firmware. HAND-MAINTAINED SOURCE since 0.9.6: edit this file.
// (fw/tools/make_09.py + guardian_layer.inc are RETIRED: they drifted and would put the screen back on the dead D0/D9. See README.)
// ---------------------------------------------------------------------
// = 08_logger v1.1.2 (sensing, bounded I2C, QSPI log, watchdog, boot safety, BLE UART console, dump)
// + the FROZEN Guardian Loop / Core Sense hg2 / Body Twin (tag hg2-freeze-10 on band B, fw/09_guardian/frozen, byte-identical,
//   compiled through fz_*.c with the host flags) driven once a minute by hg_fw.c
// + custom BLE service (STATUS notify / CMD write / INFO read), Twin file on InternalFS, Greek screens, haptic
//   patterns, power rules (screen sleeps, PPG 30 s of every minute, QSPI deep power-down, DC/DC).
// + 0.9.7 ecosystem layer (hg_fw_eco.c, ECOSYSTEM_SPEC.md): prevention nudges (planner), main clock face, warning reason
//   line, EVENTS characteristic + event ring, CMD 0x16-0x19 parsed before the frozen parser, family messages, routine seed.
// + 0.9.9 alert-quality rules layer (hg_fw_alert.c, ECOSYSTEM_SPEC.md 5e): validity gate, persistence + hysteresis, two kinds of
//   evidence for COOL, speak on change + all-clear, alert scorecard (`score`). CHECK / DANGER / HELP pass through unchanged.
// + 0.9.10 FS-HEAL (hg_fw_heal.c): every log-FS call is guarded (assert or > 4 s -> file id in GPREGRET2 + soft reset), the next
//   boot quarantines that file, the events log is /log/events_<gen>.txt (new generation per heal), a boot loop gets a quiet boot,
//   repeated trouble re-formats the LOG area only, and as a last resort storage is switched off: logging can never brick the band.
// + 0.9.16 BOOT GUARD (hg_bootguard.c): boot journal (raw page 0xEB000) + ladder (careful / safe / minimal / rest = System OFF), every
//   reset named in a ledger, the app in its own 12 KB task, a supervisor in the timer task is the only feeder of the watchdog.
// Board / libraries: as 08_logger. Wiring (board B, D0 + D9 + D2 damaged): screen DC D6, CS D1, SCK D8, MOSI D10, BL D3,
// screen RST tied to 3V3 (no MCU pin; software reset SWRESET at init), dummy MISO D9 (never read); I2C SDA D4 / SCL D5;
// button D7 (to GND; moved from D2, which reads stuck LOW since Nov 20) (README.md).
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
#include <InternalFileSystem.h>
#include <Adafruit_SPIFlashBase.h>
#include <nrf_wdt.h>
#include <stdarg.h>
extern "C" {
#include "hg_ppg.h"
#define hg_crc8 hg_log_crc8   /* log_format.h and the frozen hg_frames.h both define an (identical) hg_crc8 */
#include "log_format.h"
#undef hg_crc8
#include "log_ring.h"
#include "hg_i2c.h"
#include "hg_fw.h"
#include "hg_fw_eco.h"       // 0.9.7: events, CMD 0x16-0x19, planner, texts (plain C, host-tested: fw/tools/test_eco.c)
#include "hg_fw_alert.h"     // 0.9.9: alert-quality rules layer (plain C, host-tested with staged scenes: fw/tools/test_alerts.c)
#include "hg_fw_heal.h"      // 0.9.10 FS-HEAL: log file system self-healing decisions (plain C, host-tested: fw/tools/test_heal.c)
#include "hg_fw_stable.h"    // 0.9.15: reset classes, marker in .hg_noinit, bounded waits, verified flash wake, VBAT filter (fw/tools/test_stable.c)
#include "hg_bootguard.h"    // 0.9.16: boot journal, ladder, reset ledger, supervisor decisions (fw/tools/test_bootguard.c)
#include "hg_fw_ui.h"        // 0.9.17: button gestures, haptic sequencer, wrist raise (fw/tools/test_ui.c)
#include "hg_fw_ladder.h"    // 0.9.17: closed-loop action ladder + "keep it green" gauge (fw/tools/test_ladder.c)
#include "hg_fw_demo.h"      // [FW-DEMO] 0.9.16-demo: `replay` = SIMULATED heat-episode input, real engine (fw/tools/test_demo.c)
#include "frozen/hg2_weights.h"
#include "frozen/hg_guardian_cfg.h"
}
using namespace Adafruit_LittleFS_Namespace;

#ifndef HG_DCDC
#define HG_DAY_RECS (2u * 1440u)
#define HG_DAY_FILE_BYTES (24u + HG_DAY_RECS * 24u)
#define HG_DCDC 1               // DC/DC on (Zephyr's xiao_ble board file boots in DC/DC mode; T6a R1). 0 = LDO only
#endif
#define HG_FW_SHORT   "0.9.17-demo-b7g"  /* THE version: HG_FW_VERSION is built from it. -b7g = [PRIVACY] help example is a target-user profile; [FW-DEMO]: 0.9.17 + `replay` (simulated heat episode); -b = [OFF-CONFIRM]; -b7 = [BTN-D7] button on D7, screen RST tied to 3V3; -b7u = [FLASH-EASY] USB `uf2` / `dfu` = into the UF2 bootloader (no double tap); -b7n = [DEMO-NORESP] `replay noresp [s]` (she never presses: the real ladder's no-response path); ladder EVENTS of ANY replay marked SIMULATION in byte 18; -b7s = [REPLAY-SCREEN] the screen stays on at full brightness for the whole replay (warm-up + run); -b7t = [DEMO-PICK] the replay trace is Virtual Elder pid 90862 (a showcase pick for estimate accuracy) in a cooler last room; firmware code unchanged; -b7f = [SCREEN-FLIP] `flip` turns the screen image 180 deg (persisted in /screen.bin, default 0) */
#define HG_FW_NUM     0x0917   /* INFO frame fw_version (BCD; 0x0095 = b7-ble-sec, 0x0096 = b11 demo fixes, 0x0097 = b12 ecosystem, 0x0098 = b13 Her Day, 0x0099 = b14 alert quality, 0x0910 = 0.9.10 b15 FS-HEAL, 0x0911 = 0.9.11 FS-HEAL count + format, 0x0912 = 0.9.12 InternalFS heal, 0x0913 = 0.9.13 progress deadline + per-class counts, 0x0914 = 0.9.14 log writer task, 0x0915 = 0.9.15 reset/hang fixes, 0x0916 = 0.9.16 boot guard, 0x0917 = 0.9.17 UI engine) */
#if HG_DCDC
#define HG_FW_VERSION "09-guardian-" HG_FW_SHORT
#else
#define HG_FW_VERSION "09-guardian-" HG_FW_SHORT "-nodcdc"
#endif

// ---- pins (board B: D0, D9 and D2 are damaged - never put a used signal back on them) ----
const int8_t LCD_DC   = D6;   // moved from D0 (Nov 16: D0 pin damaged on board B)
const int8_t LCD_CS   = D1;   // moved from D9 (Nov 15: D9 pin reads stuck LOW on board B)
const int8_t LCD_SCK  = D8;
const int8_t LCD_MOSI = D10;
const int8_t LCD_BL   = D3;
const int8_t SPI_DUMMY_MISO = D9;  // dead pin D9, used only as unused dummy MISO
const int8_t LCD_RST  = GFX_NOT_DEFINED;  // [BTN-D7] no reset pin: the panel's RST is tied to 3V3; Arduino_ST7789::tftInit()
                                         // then skips the pin pulse and still sends SWRESET (0x01) + 120 ms before the init table
const uint8_t PIN_BTN = D7;        // to GND, INPUT_PULLUP ([BTN-D7] Nov 20: moved from D2, which reads stuck LOW on board B)
const uint8_t PIN_NCHG = 23;       // D23 = P0.17, BQ25100 ~CHG (LOW while charging)
// I2C: D4 = SDA, D5 = SCL

// ---- tuning ---------------------------------------------------------------
const uint8_t  BL_NORMAL_PCT = 60, BL_MOTOR_MAX = 50, BL_LOWBAT_PCT = 20, BL_WARNING_PCT = 100;
static bool uiAlert(); static void fwSecond(const hg_rec_t*); static bool eqi(const char*, const char*);
enum { UM_HAP = 1, UM_STOP, UM_CTX };              // 0.9.17: app -> hgui messages (here: before the generated prototypes)
struct UiMsg { uint8_t kind, a, b, c; uint16_t ms; };
static TaskHandle_t uiTask = NULL; static volatile uint32_t uiBeatMs = 0;   // the hgui task + its check-in (supervisor)
static float accPeak = 0;   // max |a| this second for hg_fw (secAMean/secAM2/secAN are 08's own since 1.1.2)
const uint32_t SCREEN_ON_MS = 15000;            // plan C.5: wake by press 15 s after the last press
const uint32_t RAISE_ON_MS = 8000;              // 0.9.17: wrist raise: 8 s (a false raise costs less)
const uint16_t IMU_PERIOD_MS = 40;            // 25 Hz
const float    MOTION_STD_G = 0.0072f;        // 07's still threshold (var 0.005 (m/s^2)^2) -> moving for hg_ppg
const float    IMPACT_G = HG_IMPACT_G;          // B5-v7 (manager): the log flag uses the guardian's impact constant (3 g since M19), not its own 2 g
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
#define C_BLUE   RGB565(40, 140, 255)
#define C_YELLOW RGB565(255, 230, 0)

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
static bool liveUsb = false;       // 09: the 1 Hz hex stream is debug-only ("log on")
static bool logBle = false;

// BLE TX queue: everything for BLE goes through it, drained <= 2 packets per loop pass
static uint8_t bleQ[2048];
static uint16_t bleQHead = 0, bleQTail = 0;
static uint16_t bleQCount() { return (uint16_t)((bleQHead - bleQTail) & (sizeof bleQ - 1)); }
static uint16_t bleQFree() { return (uint16_t)(sizeof bleQ - 1 - bleQCount()); }
static bool bleOn = true;          // 0.9.16: false when the boot guard skipped BLE (no SoftDevice: no Bluefruit / bleuart / hg* call at all)
// [DEMO-NORESP] 0.9.17-demo-b7n: the NUS text goes to EVERY link that subscribed to NUS TX (a Mac page + the phone), not only
// to the last-connected one (Bluefruit.connHandle(): a 2nd link connecting, or any link dropping, used to silence it).
#define HG_NUS_SLOTS 4
static uint8_t bleNusMask() {
  if (!bleOn || !Bluefruit.connected()) return 0;
  uint8_t m = 0;
  for (uint16_t h = 0; h < HG_NUS_SLOTS; h++) if (Bluefruit.connected(h) && bleuart.notifyEnabled(h)) m |= (uint8_t)(1u << h);
  return m;
}
static bool bleReady() { return bleOn && bleNusMask() != 0; }
static void bleQPut(const char* s, uint16_t n) {
  if (!bleReady()) return;
  if (n > bleQFree()) { bleDrops++; return; }
  for (uint16_t i = 0; i < n; i++) { bleQ[bleQHead] = (uint8_t)s[i]; bleQHead = (bleQHead + 1) & (sizeof bleQ - 1); }
}
static void bleService() {
  const uint8_t m = bleNusMask();
  if (!m) { bleQHead = bleQTail = 0; return; }
  for (int k = 0; k < 2 && bleQCount(); k++) {
    uint8_t pkt[20]; uint16_t n = 0, t = bleQTail;
    while (n < 20 && n < bleQCount()) { pkt[n++] = bleQ[t]; t = (t + 1) & (sizeof bleQ - 1); }
    bool sent = false;
    for (uint16_t h = 0; h < HG_NUS_SLOTS; h++) if (m & (1u << h)) sent |= bleuart.write(h, pkt, n) > 0;   // may wait <= 100 ms for a TX buffer
    if (!sent) break;                               // no link took it: keep it, the same chunk next pass (was: lost)
    bleQTail = t;
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
static bool wdtSurvived = false;                  // 0.9.15: the watchdog was still running at the top of setup() (a soft reset does not stop it)
// 0.9.16 (plan D.4): the reload register is written in ONE place (wdtHwFeed). Before the supervisor runs, wdtFeed() feeds it directly
// (setup's first statements); once the supervisor runs, wdtFeed() is only the app task's check-in and the supervisor decides.
static volatile bool supOn = false;                 // the supervisor tick runs (fsDogCb)
static volatile uint32_t appBeatMs = 0;             // the app task's last check-in
static inline void wdtHwFeed() { NRF_WDT->RR[0] = WDT_RR_RR_Reload; }
static void wdtStart(uint32_t ms) {
  if (NRF_WDT->RUNSTATUS & 1u) { wdtHwFeed(); return; }   // running: CONFIG/CRV are locked, the old 8 s stands
  NRF_WDT->CONFIG = (WDT_CONFIG_HALT_Pause << WDT_CONFIG_HALT_Pos) | (WDT_CONFIG_SLEEP_Run << WDT_CONFIG_SLEEP_Pos);
  NRF_WDT->CRV = (uint32_t)(((uint64_t)ms * 32768u) / 1000u) - 1u;
  NRF_WDT->RREN = WDT_RREN_RR0_Msk;
  NRF_WDT->TASKS_START = 1;
}
static inline void wdtFeed() { appBeatMs = millis(); if (!supOn) wdtHwFeed(); }
// 0.9.13: RAM that survives soft and watchdog resets (.hg_noinit: NOBITS, outside .bss, not zeroed by the startup code).
// cp = the last checkpoint passed (printed after a WATCHDOG reset: where the band hung); hs = the FS-HEAL state copy.
#define HG_NI_MAGIC 0x494E4748u
// 0.9.15: mk (the FS-guard marker + the guard-reset chain, hg_fw_stable.h) is appended AFTER hs, behind its own magic2, so
// the 0.9.13/0.9.14 layout (and the heal-state copy in it) still reads on the upgrade boot.
#define HG_NI_MAGIC2 0x3531394Bu
// 0.9.16: the boot-guard record of this boot (the RAM copy of the journal), the reset code our own soft resets leave, the fault-loop
// counter and a copy of the wearer profile (restored after a SAFE boot erased InternalFS), appended behind magic3. The section moves
// with .bss (it follows it), so an upgrade / rollback boot finds no valid magic at the new address and starts the RAM copy fresh.
#define HG_NI_MAGIC3 0x3631394Bu
struct HgNoinit { uint32_t magic; uint16_t cp, cp_prev; uint32_t cp_ms, boot_ms, boots; uint8_t esc_done, esc_pad[3]; hg_heal_state_t hs;
                  uint32_t magic2; hg_mk_ni_t mk;
                  uint32_t magic3; hg_bg_prev_t bg; uint8_t rcode, rarg, floop, rpad; uint32_t prof[6]; };
static HgNoinit NI __attribute__((section(".hg_noinit,\"aw\",%nobits@")));
// 0.9.16: every soft reset our own code asks for leaves a reset code first, so the next boot names it (ledger, plan D.2)
static void bgSoftReset(uint8_t rc) { NI.magic3 = HG_NI_MAGIC3; NI.rcode = rc; NVIC_SystemReset(); for (;;) {} }
static const char* const CP_NAME[] = {
  "none", "setup:start", "setup:serial", "setup:escape-wait", "setup:ifs-ladder", "setup:heal-load", "setup:storage",
  "setup:ble", "setup:boot-flush", "setup:screen", "setup:sensors", "setup:guardian", "setup:ui", "loop:top", "loop:ppg",
  "loop:imu", "loop:tmp-sht", "loop:button-motor", "loop:commands", "loop:dump-erase", "loop:ble-uart", "loop:1hz-record",
  "loop:flush", "loop:hg-ble", "loop:vbat", "loop:probe", "loop:screen", "loop:end", "fs:format-escape", "fs:ifs-format",
  "setup:bootguard", "setup:ifs-erase", "setup:off", "fault:inject"
};
// 0.9.16: the ids are stored in the boot journal (6 bits): append new ones at the END, never renumber
enum { CP_NONE, CP_S_START, CP_S_SERIAL, CP_S_ESC, CP_S_IFS, CP_S_HEAL, CP_S_STORAGE, CP_S_BLE, CP_S_FLUSH, CP_S_SCREEN, CP_S_SENSORS,
       CP_S_GUARDIAN, CP_S_UI, CP_L_TOP, CP_L_PPG, CP_L_IMU, CP_L_TMP, CP_L_BTN, CP_L_CMD, CP_L_DUMP, CP_L_BLEU, CP_L_REC, CP_L_FLUSH,
       CP_L_HGBLE, CP_L_VBAT, CP_L_PROBE, CP_L_SCREEN, CP_L_END, CP_F_ESC, CP_F_IFS, CP_S_BG, CP_S_IFSERASE, CP_S_OFF, CP_F_INJECT, CP_COUNT };
// the stage a checkpoint belongs to, for the ladder's "skip the stage that died" (plan D.1 rung 3)
static uint8_t bgStageOf(uint16_t cp) {
  switch (cp) {
    case CP_S_STORAGE: case CP_S_FLUSH: case CP_L_FLUSH: case CP_L_DUMP: case CP_F_ESC: return HG_BG_STG_STORAGE;
    case CP_S_BLE: case CP_L_BLEU: case CP_L_HGBLE: return HG_BG_STG_BLE;
    case CP_S_IFS: case CP_S_GUARDIAN: case CP_F_IFS: case CP_S_IFSERASE: return HG_BG_STG_IFS;
    default: return HG_BG_STG_NONE;
  }
}
static inline void CP(uint16_t id) { NI.cp = id; NI.cp_ms = millis(); }
static inline void CPS(uint16_t id) { CP(id); wdtFeed(); }   // setup steps: a checkpoint + the watchdog fed between steps
static volatile uint32_t ifsFlashEvents = 0, ifsFlashErrors = 0;   // SoftDevice flash events (counted by __wrap_flash_nrf5x_event_cb)
static uint16_t niLastCp = 0; static uint32_t niLastMs = 0, niBoots = 0; static bool niValid = false, niEscDone = false, niExtValid = false;
static uint8_t mkSrc = HG_MK_SRC_NONE;              // 0.9.15: where this boot's marker came from (GPREGRET2 / .hg_noinit copy)
static int rstClass = HG_RST_POWERON;               // 0.9.15: hg_reset_classify() of this boot (set once the build id is known)
#define HG_BUILD_ID HG_FW_VERSION " " __DATE__ " " __TIME__   /* FS-HEAL: a soft reset of the SAME build is never an upload */
static bool fsGuardReset = false;                 // 0.9.10: this boot follows an FS-guard soft reset (GPREGRET2 marker)
static char bootWhy[112] = "";                     // 0.9.14: the boot's reset story for stat (marker / watchdog checkpoint)
static bool usbFsFormat = false;                   // 0.9.11: "fsformat" received on USB in the first 3 s
static bool usbIfsFormat = false;                  // 0.9.13: "ifsformat" received on USB in the first 3 s
// 0.9.15: one classification (hg_fw_stable.c): RESETPIN first (erratum 136), soft reset = upload only for a new build,
// same build + marker = FS-GUARD, same build without one = CRASH. fsGuardReset stays for the old callers.
static const char* resetName(uint32_t) { return hg_reset_name(rstClass); }

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
static hg_vbat_filt_t vbatF;        // 0.9.15: VBAT filter (hg_fw_stable.c)

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
// 0.9.17 (plan B.3): two tasks use TWIM0 - hgapp (sensors) and hgui (the DRV2605L). One mutex, taken per transfer, never held
// across a delay; priority inheritance keeps the hgui task's wait short (longest sensor transfer: the PPG FIFO burst, ~5 ms).
static SemaphoreHandle_t i2cMtx = NULL;
static volatile uint32_t i2cLockFails = 0;
struct I2cLock {
  bool ok, held;
  I2cLock() : ok(true), held(false) {
    if (i2cMtx) { held = xSemaphoreTake(i2cMtx, pdMS_TO_TICKS(200)) == pdTRUE; ok = held; if (!ok) i2cLockFails++; }
  }
  ~I2cLock() { if (held) xSemaphoreGive(i2cMtx); }
};
static bool i2cWrite(uint8_t addr, const uint8_t* d, uint8_t n) { I2cLock l; return l.ok && hg_i2c_write(addr, d, n) == HG_I2C_OK; }
static bool i2cWriteReg8(uint8_t addr, uint8_t reg, uint8_t v) { uint8_t b[2] = {reg, v}; return i2cWrite(addr, b, 2); }
static bool i2cReadReg(uint8_t addr, uint8_t reg, uint8_t* d, uint8_t n) { I2cLock l; return l.ok && hg_i2c_write_read(addr, &reg, 1, d, n) == HG_I2C_OK; }
static bool i2cRead(uint8_t addr, uint8_t* d, uint8_t n) { I2cLock l; return l.ok && hg_i2c_read(addr, d, n) == HG_I2C_OK; }
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
static bool shtTrigger() { shtCmd(0x3517); delayMicroseconds(300); return shtCmd(0x7866); }   // 0.9.6: wake may NACK when already awake: not fatal
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
// haptics + backlight rule. 0.9.17: after boot the hgui task owns the DRV2605L (sequencer in hg_fw_ui.c, the drv* functions
// below run in that task). vibrate() / serviceMotor() are only for setup() before that task starts (power-up, the rest rung).
// =====================================================================
#define WAIT10MS(n) (0x80 | (n))
const uint8_t PAT_SHORT[8] = { 10, WAIT10MS(10), 10, 0 };  // 07 "Drink": double click x2
const uint8_t PAT_LONG[8]  = { 16, 52, 0 };                // 07 "Danger": 1000 ms alert + pulsing strong
const uint8_t PAT_SOFT[8]  = { 2, 0 };                     // 07 "All OK": soft tick (low battery)
static volatile bool motorBusy = false;          // 0.9.17: written by the hgui task (sequencer playing), read by the app
static bool pofHold = false;        // supply sagging (VBAT poll, see pofPoll): soft haptic tick only
static uint32_t motorStart = 0; static volatile uint32_t motorEnd = 0;
static volatile bool uiTaskOn = false;            // 0.9.17: the hgui task runs (then nobody else touches the DRV2605L)
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
static bool demoScreenHold();      // [REPLAY-SCREEN] a replay is running (warm-up or minutes; not the 2 min end screen)
static uint8_t blNormalPct() {      // [REPLAY-SCREEN] the resting backlight level; a replay = full (filmed beside the big screen)
  if (demoScreenHold()) return BL_WARNING_PCT;
  return lowBatMode ? BL_LOWBAT_PCT : (uiAlert() ? BL_WARNING_PCT : BL_NORMAL_PCT);
}
static void applyBacklight() {   // the ONLY function that turns the backlight on
  uint8_t pct = screenOn ? blTarget : 0;
  if (motorBusy && pct > BL_MOTOR_MAX && !demoScreenHold()) pct = BL_MOTOR_MAX;   // [REPLAY-SCREEN] no dip on camera while it buzzes
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
static void vibrate(const uint8_t* pat) {           // boot only (setup before the hgui task, the rest rung)
  if (!hasDrv || uiTaskOn) return;
  if (lowBatMode || pofHold) pat = PAT_SOFT;   // R4 A8.2: low battery = soft tick only, never silent (T6b M1)
  if (vbat == vbat && vbat < VBAT_SOFT && !charging()) pat = PAT_SOFT;   // brown-out rule (R4 A8.2)
  if (motorBusy) i2cWriteReg8(0x5A, 0x0C, 0);   // 0.9.6: stop the pattern still playing, so the new one (e.g. a cancel tick) is felt
  uint8_t md = 0, fbk = 0;                         // 0.9.6: a silent DRV2605L reset leaves it in STANDBY / LRA mode -> re-init
  if (i2cReadReg(0x5A, 0x01, &md, 1) && i2cReadReg(0x5A, 0x1A, &fbk, 1) && ((md & 0x40) || (fbk & 0x80))) {
    bool ok = drvInit(); evLog("DRV re-init mode=0x%02x fb=0x%02x ok=%d", md, fbk, ok);
  }
  motorBusy = true;
  applyBacklight();               // dim FIRST, then start the motor
  uint8_t i = 0;
  for (; i < 8 && pat[i]; i++) i2cWriteReg8(0x5A, 0x04 + i, pat[i]);   // WAVESEQ1..8
  if (i < 8) i2cWriteReg8(0x5A, 0x04 + i, 0);
  devResult(DEV_DRV, i2cWriteReg8(0x5A, 0x0C, 1));                       // GO
  motorStart = millis();
}
static void serviceMotor() {
  if (!motorBusy || uiTaskOn) return;
  static uint32_t lastPoll = 0;
  if (millis() - lastPoll < 20) return;
  lastPoll = millis();
  uint8_t go = 0;
  bool okr = devResult(DEV_DRV, i2cReadReg(0x5A, 0x0C, &go, 1));
  bool playing = okr && (go & 0x01);
  if (!playing || millis() - motorStart > 8000) {   // 09: HAP_CHECK runs 7 s (T6b m5)
    if (playing) i2cWriteReg8(0x5A, 0x0C, 0);
    motorBusy = false;
    motorEnd = millis();
    applyBacklight();
  }
}
static bool recentlyBuzzed() { return motorBusy || (motorEnd && millis() - motorEnd < AFTER_BUZZ_MS); }
// ---- 0.9.17 the sequencer's motor driver (hgui task). A silent DRV2605L reset (STANDBY / LRA mode) is re-initialised before GO.
static volatile uint32_t drvReinits = 0, drvGoFails = 0;
static int drvGo(void*, const uint8_t w[8]) {
  if (!hasDrv) { drvGoFails++; return -1; }
  uint8_t md = 0, fbk = 0;
  if (i2cReadReg(0x5A, 0x01, &md, 1) && i2cReadReg(0x5A, 0x1A, &fbk, 1) && ((md & 0x40) || (fbk & 0x80))) { drvReinits++; if (!drvInit()) { drvGoFails++; return -1; } }
  uint8_t i = 0;
  for (; i < 8 && w[i]; i++) if (!i2cWriteReg8(0x5A, 0x04 + i, w[i])) { drvGoFails++; return -1; }   // WAVESEQ1..8
  if (i < 8 && !i2cWriteReg8(0x5A, 0x04 + i, 0)) { drvGoFails++; return -1; }
  if (!i2cWriteReg8(0x5A, 0x0C, 1)) { drvGoFails++; return -1; }                                     // GO
  return 0;
}
static int drvBusy(void*) { uint8_t go = 0; return i2cReadReg(0x5A, 0x0C, &go, 1) ? (go & 1) : -1; }
static void drvStop(void*) { i2cWriteReg8(0x5A, 0x0C, 0); }
static int drvReinit(void*) { drvReinits++; bool ok = drvInit(); hasDrv = ok; return ok ? 0 : -1; }   // plan A-13: on demand, every pattern

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
// 0.9.15: the Adafruit_SPIFlashBase layer is NOT used any more: its readBuffer / writeBuffer / waitUntilReady / begin wait
// on the chip with no time limit, return success when the chip did not answer, and its status read returns an uninitialised
// byte when the QSPI command fails (plan A-04 / A-06). Every flash access below is bounded and reports its errors.
Adafruit_FlashTransport_QSPI qspiTr;   // the transport only: nrfx init/uninit, custom instructions (each bounded to 1 ms by nrfx)
static bool flashAwake = false, qspiActive = false;
static volatile bool flashVerify = true;            // 0.9.15: check the JEDEC id at the next flash access (set at every guarded log call
                                                    // and after any flash error: a chip asleep behind the driver's back is caught)
static uint32_t flashIdExpect = 0x856015ul, flashBytes = 0;   // the id and size found at boot
static uint32_t flashWakeRetries = 0, flashRdErr = 0, flashPrErr = 0, flashErErr = 0, flashRdyTimeouts = 0, flashXferTimeouts = 0,
                flashEraseVerifyFails = 0, flashErrLastMs = 0;
static uint8_t flashErrLastOp = 0;                  // 'r' read, 'p' program, 'e' erase, 'w' wake
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
  qspiTr.setClockSpeed(55000000u, 55000000u);   // ... then the run-time clock (as the Adafruit flash begin() set it)
  qspiActive = true;
}
static volatile uint32_t ioRd = 0, ioPr = 0, ioEr = 0;   // 0.9.14: QSPI flash I/O counters (read / prog / erase calls)
static TaskHandle_t wrTask = NULL; static volatile bool wrRunning = false, setupDone = false;   // 0.9.14 log writer task
static volatile bool wrBusy = false;                // (0.9.16: declared here, the supervisor reads it)
static inline bool inWriter() { return wrTask && xTaskGetCurrentTaskHandle() == wrTask; }
// ---------------------------------------------------------------- 0.9.15 bounded flash primitives (plan A-04 / A-05 / A-06)
// Rules: every wait has a deadline (hg_wait_bounded); a failure is returned, never hidden; a peripheral that did not finish is
// reset (qspiOff: erratum-122 order) and the next access wakes + verifies the chip again (flashVerify).
static uint32_t hgMs() { return millis(); }
static void flashErr(char op, volatile uint32_t* ctr) { (*ctr)++; flashErrLastOp = (uint8_t)op; flashErrLastMs = millis(); flashVerify = true; }
static int flashSrPoll(void*) {                     // 1 = WIP clear, 0 = busy, -1 = the status read itself failed
  uint8_t sr = 0xFF;
  if (!qspiTr.readCommand(0x05, &sr, 1)) return -1;
  return (sr & 0x01) ? 0 : 1;                       // WIP only: a failed program leaves WEL set, which is not "busy" (A-06)
}
static volatile bool flashDrainPpg = false;         // erase wait: drain the PPG FIFO meanwhile (loop task only, never the writer)
static void flashIdleYield(void*) { yield(); }
static void flashIdleSleep(void*) { if (flashDrainPpg && !inWriter()) ppgService(hrDet.motion); delay(1); }
// the chip is ready (WIP clear) within ms; on a timeout: write-disable, peripheral reset, false
static bool flashReady(uint32_t ms, bool sleepy) {
  int r = hg_wait_bounded(flashSrPoll, NULL, hgMs, sleepy ? flashIdleSleep : flashIdleYield, NULL, ms, NULL);
  if (r == HG_WAIT_OK) return true;
  flashRdyTimeouts++; flashVerify = true;
  qspiTr.runCommand(0x04);                          // WRDI
  return false;
}
static int qspiReadyPoll(void*) { return NRF_QSPI->EVENTS_READY ? 1 : 0; }
// one QSPI DMA transfer (word-aligned RAM buffer, length multiple of 4) with a deadline; on a timeout the peripheral is reset
static bool qspiXfer(bool rd, uint32_t addr, void* buf, uint32_t n, uint32_t ms) {
  if (!qspiActive || !NRF_QSPI->ENABLE) return false;
  NRF_QSPI->EVENTS_READY = 0;
  if (rd) { NRF_QSPI->READ.SRC = addr; NRF_QSPI->READ.DST = (uint32_t)buf; NRF_QSPI->READ.CNT = n; NRF_QSPI->TASKS_READSTART = 1; }
  else    { NRF_QSPI->WRITE.DST = addr; NRF_QSPI->WRITE.SRC = (uint32_t)buf; NRF_QSPI->WRITE.CNT = n; NRF_QSPI->TASKS_WRITESTART = 1; }
  if (hg_wait_bounded(qspiReadyPoll, NULL, hgMs, NULL, NULL, ms, NULL) != HG_WAIT_OK) {
    flashXferTimeouts++; qspiOff(); flashAwake = false; flashVerify = true; return false;
  }
  NRF_QSPI->EVENTS_READY = 0;
  return true;
}
static __attribute__((aligned(4))) uint8_t qBounce[256];
static inline bool inRam4(const void* p) { uint32_t a = (uint32_t)p; return (a & 3u) == 0 && a >= 0x20000000u && a < 0x20040000u; }
static bool flashRead(uint32_t addr, uint8_t* dst, uint32_t n) {
  if (!(addr & 3u) && !(n & 3u) && inRam4(dst)) return qspiXfer(true, addr, dst, n, 50);   // 4 KB at 16 MHz quad: ~0.6 ms
  while (n) {                                       // unaligned: through a bounce buffer, <= 256 B at a time
    uint32_t a0 = addr & ~3u, lead = addr - a0, chunk = n < 256u - lead ? n : 256u - lead, len4 = (lead + chunk + 3u) & ~3u;
    if (!qspiXfer(true, a0, qBounce, len4, 20)) return false;
    memcpy(dst, qBounce + lead, chunk); addr += chunk; dst += chunk; n -= chunk;
  }
  return true;
}
static bool flashProg(uint32_t addr, const uint8_t* src, uint32_t n) {   // page by page (a program never crosses a 256 B page)
  while (n) {
    uint32_t room = 256u - (addr & 255u), chunk = n < room ? n : room;
    uint32_t a0 = addr & ~3u, lead = addr - a0, len4 = (lead + chunk + 3u) & ~3u;   // lead + chunk <= 256 (same page)
    memset(qBounce, 0xFF, len4); memcpy(qBounce + lead, src, chunk);             // 0xFF pad = bits left as they are
    if (!flashReady(20, false)) return false;
    qspiTr.runCommand(0x06);                        // WREN (the peripheral sends one too; a second is harmless)
    if (!qspiXfer(false, a0, qBounce, len4, 20)) return false;
    if (!flashReady(30, false)) return false;       // tPP max (Puya class) ~3 ms; 30 ms = dead
    addr += chunk; src += chunk; n -= chunk;
  }
  return true;
}
// wake + JEDEC check, 3 tries (plain / GPIO wake + fresh peripheral / + chip software reset); false = the chip is not there
static uint32_t flashWakeTry(int attempt, void*) {
  if (attempt == 0) { if (!qspiActive) qspiOn(); }  // qspiOn = GPIO 0xAB first (a sleeping chip stalls the peripheral)
  else { flashWakeRetries++; qspiOff(); delayMicroseconds(100); gpioWake(attempt >= 2); qspiOn(); }
  qspiTr.runCommand(0xAB);                          // once more through the peripheral (harmless when awake)
  delayMicroseconds(50);                            // tRES1 (8 us class; 50 us margin)
  uint8_t id[3] = {0, 0, 0};
  if (!qspiTr.readCommand(0x9F, id, 3)) return 0;
  return ((uint32_t)id[0] << 16) | ((uint32_t)id[1] << 8) | id[2];
}
static bool flashWake() {
  if (flashAwake && qspiActive && !flashVerify) return true;
  bool cold = !flashAwake || !qspiActive;
  int r = hg_flash_wake(flashIdExpect, flashWakeTry, NULL, HG_FLASH_WAKE_TRIES);
  if (cold) flashWakes++;
  if (r < 0) { flashWakeFails++; flashErrLastOp = 'w'; flashErrLastMs = millis(); flashAwake = false; return false; }   // stat: flash_wake_fails
  flashAwake = true; flashVerify = false;
  return true;
}
// 0.9.10: a block number past the chip (a corrupt pointer that slipped past littlefs) is an I/O error, never a wrapped address
// 0.9.15: every driver failure is LFS_ERR_IO (0.9.14 returned 0 whatever happened: garbage as metadata, programs silently dropped)
static int lfsRead(const struct lfs_config* c, lfs_block_t b, lfs_off_t off, void* buf, lfs_size_t n) {
  if (b >= c->block_count || off + n > c->block_size) return LFS_ERR_IO;
  fsIo(); ioRd++;
  if (!flashWake() || !flashRead(b * 4096u + off, (uint8_t*)buf, n)) { flashErr('r', &flashRdErr); return LFS_ERR_IO; }
  return 0;
}
static int lfsProg(const struct lfs_config* c, lfs_block_t b, lfs_off_t off, const void* buf, lfs_size_t n) {
  if (b >= c->block_count || off + n > c->block_size) return LFS_ERR_IO;
  fsIo(); ioPr++;
  if (!flashWake() || !flashProg(b * 4096u + off, (const uint8_t*)buf, n)) { flashErr('p', &flashPrErr); return LFS_ERR_IO; }
  return 0;
}
// Erase without blocking the PPG: a 4 KB erase takes 40-50 ms typ, 300 ms max (Puya datasheet) and the
// MAX30102 FIFO holds 320 ms, so keep draining the FIFO while the flash is busy (T6a m9).
// 0.9.14: the PPG FIFO is drained here only when the loop itself waits on flash (setup / commands); the writer task
// just sleeps - the loop keeps running and drains it itself (two tasks must not share the I2C bus)
// 0.9.15: bounded, checked: READY within 1 s, WIP clear within 1.5 s, then the block must read back as all 0xFF.
static int lfsErase(const struct lfs_config* c, lfs_block_t b) {
  if (b >= c->block_count) return LFS_ERR_IO;
  fsIo(); ioEr++;
  if (!flashWake() || !flashReady(50, false)) { flashErr('e', &flashErErr); return LFS_ERR_IO; }
  NRF_QSPI->EVENTS_READY = 0;
  NRF_QSPI->ERASE.PTR = b * 4096u;
  NRF_QSPI->ERASE.LEN = QSPI_ERASE_LEN_LEN_4KB;
  NRF_QSPI->TASKS_ERASESTART = 1;  // the QSPI sends WREN itself
  flashDrainPpg = true;
  bool ok = hg_wait_bounded(qspiReadyPoll, NULL, hgMs, flashIdleSleep, NULL, 1000, NULL) == HG_WAIT_OK;
  NRF_QSPI->EVENTS_READY = 0;
  if (!ok) { flashXferTimeouts++; qspiOff(); flashAwake = false; }
  else ok = flashReady(1500, true);
  flashDrainPpg = false;
  if (ok) {                                         // read back: an erase that did not take is an error, not a later verify storm
    static __attribute__((aligned(4))) uint32_t chk[64];
    for (uint32_t o = 0; ok && o < 4096u; o += sizeof chk) {
      if (!flashRead(b * 4096u + o, (uint8_t*)chk, sizeof chk)) { ok = false; break; }
      for (unsigned i = 0; i < 64; i++) if (chk[i] != 0xFFFFFFFFu) { ok = false; flashEraseVerifyFails++; break; }
    }
  }
  fsIo();                                           // 0.9.13: erase done = progress
  if (!ok) { flashErr('e', &flashErErr); return LFS_ERR_IO; }
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

enum { FS_NO_FLASH = 0, FS_CORRUPT = 1, FS_OK = 2, FS_DISABLED = 3, FS_BGOFF = 4 };   // 0.9.16: BGOFF = not started (boot guard rung)
static uint8_t fsState = FS_NO_FLASH;
static const char* FS_NAME[] = { "NO FLASH", "CORRUPT (type: format YES)", "OK", "DISABLED (fs-heal; usb: fsheal reset)", "OFF (boot guard: back at the next normal boot)" };
static bool dumpActive = false;
static SemaphoreHandle_t fsMtxEarly();          // (fsMtx is declared with the guard below)
// 0.9.15 (plan A-05, decision 5): the chip is NOT put into deep power-down any more (0.9.14 did it after every writer job:
// thousands of wakes a day, each one a chance to talk to a sleeping chip). Only the nRF QSPI peripheral is switched off;
// the chip stays in standby (~10 uA class). Deep power-down is for System OFF only (not in 0.9.15).
static void flashSleep() {
  if (fsState == FS_NO_FLASH || fsState == FS_BGOFF || !qspiActive || dumpActive) return;
  SemaphoreHandle_t m = fsMtxEarly();
  if (m && xSemaphoreTakeRecursive(m, 0) != pdTRUE) return;          // 0.9.14: the other task is using the flash: it idles it after
  flashReady(50, false);                                             // bounded: never switch the peripheral off mid-program
  flashAwake = false;
  qspiOff();                      // nRF QSPI peripheral off (the next access: GPIO wake + JEDEC check)
  if (m) xSemaphoreGiveRecursive(m);
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

// ---------------------------------------------------------------------
// 0.9.10 FS-HEAL guard (hg_fw_heal.h). ROOT CAUSE of the 0.9.6 boot loops: littlefs v1.6 here is built with
// asserts; a corrupt CTZ skip pointer in one file trips LFS_ASSERT(head >= 2 && head <= block_count) in
// lfs_ctz_find / lfs_ctz_extend -> newlib __assert_func -> abort -> _exit, which is "b _exit": a silent spin
// until the 8 s watchdog, at the same append on every boot. Now:
//   - every logFS call runs inside FsGuard(fid): fsOp = the file id (RAM), watchdog fed once at the start;
//   - our __assert_func (below) and the FS deadline timer (an FS call > HG_FS_DEADLINE_MS) write the id into
//     GPREGRET2 and soft-reset at once (GPREGRET2 survives a soft reset, not a watchdog reset);
//   - the next boot reads it and quarantines that file (hg_heal_* decisions, healAfterBoot / healFormat in storageInit).
// The deadline (4 s) is shorter than the watchdog (8 s), so the watchdog stays the backstop for a hang with
// interrupts off and never masks a hang inside an FS call.
// ---------------------------------------------------------------------
// 0.9.14: two guard slots, [0] QSPI log (now mostly the writer task), [1] InternalFS (loop) - they can run at the same time.
// QSPI log calls are serialised by a recursive mutex (fsMtx): the writer task and the loop's few log calls (stat, dump,
// commands) never interleave inside littlefs.
static volatile uint8_t fsOpC[2] = {HG_FID_NONE, HG_FID_NONE};
static volatile uint32_t fsOpT0C[2] = {0, 0}, fsIoTC[2] = {0, 0};
static volatile bool fsOpLoop[2] = {false, false};   // 0.9.15: the guarded call runs in loop()/setup() (not the writer): the timer keeps the
                                                    // watchdog fed while it makes I/O progress (plan A-03)
static volatile uint32_t fsIoN = 0;
static volatile bool appWaitFs = false;             // 0.9.16: the app task waits for the log mutex the writer holds (supervisor: alive while
                                                    // the writer's guarded call makes I/O progress)
static uint32_t fsGuarded = 0, fsMaxMs[2] = {0, 0}; static uint8_t fsMaxFid[2] = {0, 0};   // longest call: [0] QSPI log, [1] InternalFS
static SemaphoreHandle_t fsMtx = NULL;
static SemaphoreHandle_t fsMtxEarly() { return fsMtx; }
static inline void fsIoK(int k) { fsIoTC[k] = millis(); fsIoN++; }
static inline void fsIo() { fsIoK(0); }
#define fsOp (fsOpC[0] ? fsOpC[0] : fsOpC[1])     /* for the assert handler: the log call if one runs, else the InternalFS one */
struct FsGuard {
  uint8_t prev; uint32_t t0; int k;
  explicit FsGuard(uint8_t fid) {
    k = hg_heal_fid_is_ifs(fid) ? 1 : 0;
    if (k == 0 && fsMtx) { if (!inWriter()) { wdtFeed(); appWaitFs = true; } xSemaphoreTakeRecursive(fsMtx, portMAX_DELAY); appWaitFs = false; }
    prev = fsOpC[k]; if (!inWriter()) wdtFeed(); t0 = millis(); fsOpT0C[k] = t0; fsIoTC[k] = t0; fsOpLoop[k] = !inWriter(); fsOpC[k] = fid; fsGuarded++;
    if (k == 0) flashVerify = true;                 // 0.9.15: JEDEC check at the first flash access of every log call
  }
  ~FsGuard() {
    uint32_t d = millis() - t0;
    if (d > fsMaxMs[k]) { fsMaxMs[k] = d; fsMaxFid[k] = fsOpC[k]; }
    fsOpT0C[k] = millis(); fsIoTC[k] = fsOpT0C[k]; fsOpC[k] = prev;
    if (k == 0 && fsMtx) xSemaphoreGiveRecursive(fsMtx);
  }
};
static bool svcOk() { return __get_IPSR() == 0 && __get_PRIMASK() == 0 && __get_BASEPRI() == 0; }   // a SoftDevice call (SVC) is allowed here
static bool sdOn() { uint8_t sd = 0; if (svcOk()) sd_softdevice_is_enabled(&sd); return sd; }
static uint8_t gpregret2Read() {
  if (sdOn()) { uint32_t v = 0; sd_power_gpregret_get(1, &v); return (uint8_t)v; }
  return (uint8_t)NRF_POWER->GPREGRET2;
}
static void gpregret2Write(uint8_t v) {
  if (sdOn()) { sd_power_gpregret_clr(1, 0xFFu); if (v) sd_power_gpregret_set(1, v); }
  else NRF_POWER->GPREGRET2 = v;
}
static uint8_t guardCount = 0;                     // guard resets in a row so far (from the marker; 0 after 10 min stable)
static uint8_t guardPrevFid = 0;                   // 0.9.13: the file id of the last fault (its class: QSPI log or InternalFS)
static bool ifsBad = false;                         // InternalFS switched off for this boot (0.9.12: only on the 3rd InternalFS fault in a row)
extern "C" void hgFsDie(uint8_t cause, uint8_t fid) {
  uint8_t cnt = hg_heal_next_count(guardCount, guardPrevFid, fid);
  uint8_t v = hg_heal_marker_encode(cause, fid, cnt, ifsBad);   // 0.9.13: per class
  NI.magic2 = HG_NI_MAGIC2; NI.mk.reg = v; NI.mk.pend = 1; NI.mk.gc = cnt; NI.mk.gfid = fid;   // 0.9.15: RAM copy (a watchdog / pin reset clears GPREGRET2)
  if (svcOk()) gpregret2Write(v);                   // SoftDevice on: through its API (POWER is a restricted peripheral)
  else NRF_POWER->GPREGRET2 = v;                    // handler mode / masked: direct (SoftDevice off at boot, or last resort)
  NVIC_SystemReset();                               // soft reset: GPREGRET2 survives it
  for (;;) {}
}
// newlib's assert ends in "b _exit" (silent spin, see above): ours names the FS call and resets in ~1 ms instead.
// 0.9.16 (plan A-24): an assert with NO guarded file call running (Bluefruit's own InternalFS mount, any library) is not a file-system
// fault: no FS-HEAL marker (0.9.10-0.9.15 booked it as "fid none" and re-formatted the log area on the 2nd), a named soft reset
// (ASSERT in the ledger) that the boot guard's ladder counts instead.
extern "C" void __assert_func(const char* file, int line, const char* func, const char* expr) {
  (void)file; (void)line; (void)func; (void)expr;
  if (fsOp == HG_FID_NONE) bgSoftReset(HG_BG_RC_ASSERT);
  hgFsDie(HG_CAUSE_ASSERT, fsOp);
  for (;;) {}
}
// 0.9.16: the FreeRTOS hooks do nothing in this core's release build (an overflow = silent corruption, plan A-11). Linked in with
// -Wl,--wrap=vApplicationStackOverflowHook,--wrap=vApplicationMallocFailedHook (README build line; without the flags they stay inert).
static TaskHandle_t appTask = NULL;
extern "C" void __wrap_vApplicationStackOverflowHook(TaskHandle_t t, char* name) {
  (void)name;
  NI.rarg = t == appTask ? 1 : (t && t == wrTask) ? 2 : (t && t == xTimerGetTimerDaemonTaskHandle()) ? 3 : (t && t == uiTask) ? 4 : 0;
  bgSoftReset(HG_BG_RC_STACK);
}
extern "C" void __wrap_vApplicationMallocFailedHook(void) { NI.rarg = 0; bgSoftReset(HG_BG_RC_MALLOC); }
// 0.9.16 SUPERVISOR (plan D.4): the same 250 ms timer tick also decides the watchdog feed (hg_sup_step): the app task must check in
// (wdtFeed) within 5 s, or be inside a guarded file call that still does flash I/O; otherwise a NAMED soft reset (SUPERVISOR, with its
// checkpoint) before the 8 s hardware watchdog. A writer job stuck outside any guard switches storage off; it never resets the band.
// No printf here (the timer task has 1 KB of stack); the FS deadline line below is the one exception kept from 0.9.13.
static SoftwareTimer fsDogTimer;
static hg_sup_t SUP;
static volatile bool wrStuck = false;               // the writer task hung outside a guarded call: storage off for this boot
static volatile uint32_t wrJobT0 = 0;
static void fsDogCb(TimerHandle_t) {                // FreeRTOS timer task (priority 2 > app task 1): runs while the app spins
  for (int k = 0; k < 2; k++) {
  uint8_t f = fsOpC[k];
  if (f == HG_FID_NONE) continue;
  uint32_t now = millis(), tot = now - fsOpT0C[k], io = now - fsIoTC[k];
  // 0.9.13: hung = no flash I/O for 4 s, or still going after 30 s. A slow call that keeps doing I/O is NOT killed (0.9.12
  // killed any call > 4 s: a slow erase / long traversal could be a false positive) and keeps the watchdog fed meanwhile.
  if (hg_heal_deadline_hit(tot, io)) {
    char m[120]; int n = snprintf(m, sizeof m, "# FS_HEAL DEADLINE fid=%s total_ms=%lu since_io_ms=%lu io=%lu -> reset\n",
                                  hg_heal_fid_name(f), (unsigned long)tot, (unsigned long)io, (unsigned long)fsIoN);
    if (Serial && n > 0 && Serial.availableForWrite() >= n) { Serial.write((const uint8_t*)m, (size_t)n); Serial.flush(); }   // never blocks
    hgFsDie(HG_CAUSE_DEADLINE, f);
  }
  }
  // 0.9.16: the supervisor. (0.9.15 fed the watchdog here for a loop-side guarded call with I/O in the last 1.5 s; that rule is now
  // part of hg_sup_step: an app-side guarded call with I/O in the last 4 s and < 30 s total counts as a check-in.)
  hg_sup_in_t in; memset(&in, 0, sizeof in);
  in.now = millis(); in.app_beat = appBeatMs;
  for (int k = 0; k < 2; k++) if (fsOpC[k] != HG_FID_NONE && fsOpLoop[k]) {
    uint32_t io = in.now - fsIoTC[k], tot = in.now - fsOpT0C[k];
    if (!in.app_in_guard || io < in.guard_since_io) { in.app_in_guard = 1; in.guard_since_io = io; in.guard_total = tot; }
  }
  if (appWaitFs && fsOpC[0] != HG_FID_NONE && !fsOpLoop[0]) {   // the app is blocked behind the writer's guarded call
    uint32_t io = in.now - fsIoTC[0], tot = in.now - fsOpT0C[0];
    if (!in.app_in_guard || io < in.guard_since_io) { in.app_in_guard = 1; in.guard_since_io = io; in.guard_total = tot; }
  }
  in.writer_busy = wrBusy; in.writer_in_guard = fsOpC[0] != HG_FID_NONE && !fsOpLoop[0]; in.writer_job_t0 = wrJobT0;
  hg_sup_out_t o; hg_sup_step(&SUP, &in, &o);
  if (o.writer_stuck) wrStuck = true;
  if (o.reset_app) { NI.rarg = 1; bgSoftReset(HG_BG_RC_SUPERVISOR); }   // checkpoint = NI.cp (the app's last one)
  { uint32_t ub = uiBeatMs; if (uiTaskOn && ub && in.now - ub > 5000u && (int32_t)(in.now - ub) > 0) { NI.rarg = 4; bgSoftReset(HG_BG_RC_SUPERVISOR); } }   // 0.9.17: hgui silent 5 s
  if (o.feed) wdtHwFeed();
}

// heal state (0.9.13: .hg_noinit RAM + a reserved raw internal-flash page, see healSave)
static hg_heal_state_t HS; static hg_heal_boot_t HB;
static uint8_t healMarkerReg = 0;                   // GPREGRET2 as found at boot (cleared right after reading)
static bool healStateValid = false;
static uint8_t healIfsHealed = 0;                   // 0.9.12: InternalFS file id quarantined this boot (0xFF = InternalFS formatted)
static bool fsQuiet = false;                        // quiet boot: no non-essential log writes until 10 min of uptime
static bool sfileAtQuietEnd = false;                // start a new s-file when the quiet boot ends
static uint32_t quietDroppedRecs = 0, evDroppedFailed = 0, healSaves = 0;
static uint8_t evFailsInRow = 0, sFailsInRow = 0;
static char evPath[HG_HEAL_PATH] = "/log/events_1.txt";
static uint32_t evBytes = 0;                        // 0.9.14: bytes in the live events file (rotation at HG_EV_ROTATE_BYTES)
static bool ifsWrite(const char* path, const void* d, size_t n, uint8_t fid);
// 0.9.13: the heal state is NOT on any file system any more (0.9.12's /fsheal.bin on InternalFS was itself asserting):
//  1. a copy in .hg_noinit RAM (survives soft and watchdog resets; not zeroed by the startup code; CRC-checked), and
//  2. a raw, reserved internal-flash page HEAL_PAGE (0xEC000, between the app and InternalFS), written as append-only
//     slots, every write read back from the memory-mapped flash (no littlefs, no silent-success callbacks), <= 3 tries.
// A power-on reset loses (1); (2) has the last saved copy.
#define HEAL_PAGE 0xEC000u
#define HEAL_SLOT ((sizeof(hg_heal_state_t) + 3u) & ~3u)
#define HEAL_SLOTS (4096u / HEAL_SLOT)
extern uint32_t __etext;                            // end of the app image in flash (the page must lie above it)
static uint32_t healFlashWrites = 0, healFlashFails = 0; static int8_t healSrc = -1;   // 0 noinit, 1 flash page, -1 new
static bool nvmcReady(uint32_t ms) { uint32_t t = millis(); while (!NRF_NVMC->READY) { if (millis() - t > ms) return false; } return true; }
static bool sdFlashWait(uint32_t evBefore, uint32_t ms) {   // SoftDevice flash op: wait for its event (our wrap counts them)
  uint32_t t = millis(); while (ifsFlashEvents == evBefore) { if (millis() - t > ms) return false; delay(1); } return true;
}
static bool nvPageErase(uint32_t page) {           // 0.9.16: any reserved raw page (heal state 0xEC000, boot journal 0xEB000)
  if ((uint32_t)&__etext >= page) return false;      // never erase into the app
  if (sdOn()) { uint32_t e = ifsFlashEvents; uint32_t r;
    uint32_t tb = millis(); while ((r = sd_flash_page_erase(page / 4096u)) == NRF_ERROR_BUSY) { if (millis() - tb > 2000) return false; delay(1); }   // 0.9.15: bounded
    if (r != NRF_SUCCESS) return false; sdFlashWait(e, 400); }
  else { NRF_NVMC->CONFIG = NVMC_CONFIG_WEN_Een; NRF_NVMC->ERASEPAGE = page; bool ok = nvmcReady(200); NRF_NVMC->CONFIG = NVMC_CONFIG_WEN_Ren; if (!ok) return false; }
  for (uint32_t a = page; a < page + 4096u; a += 4) if (*(volatile uint32_t*)a != 0xFFFFFFFFu) return false;
  return true;
}
static bool healPageErase() { return nvPageErase(HEAL_PAGE); }
static bool healPageWrite(uint32_t addr, const void* d, uint32_t n) {   // n multiple of 4, target erased
  if (sdOn()) { uint32_t e = ifsFlashEvents; uint32_t r;
    uint32_t tb = millis(); while ((r = sd_flash_write((uint32_t*)addr, (const uint32_t*)d, n / 4)) == NRF_ERROR_BUSY) { if (millis() - tb > 2000) return false; delay(1); }   // 0.9.15: bounded
    if (r != NRF_SUCCESS) return false; sdFlashWait(e, 200); }
  else { NRF_NVMC->CONFIG = NVMC_CONFIG_WEN_Wen;
    for (uint32_t i = 0; i < n; i += 4) { *(volatile uint32_t*)(addr + i) = ((const uint32_t*)d)[i / 4]; nvmcReady(5); }
    NRF_NVMC->CONFIG = NVMC_CONFIG_WEN_Ren; }
  return memcmp((const void*)addr, d, n) == 0;      // the flash is memory-mapped: the real check
}
static bool healSlotEmpty(uint32_t a) { for (uint32_t i = 0; i < HEAL_SLOT; i += 4) if (*(volatile uint32_t*)(a + i) != 0xFFFFFFFFu) return false; return true; }
static SemaphoreHandle_t healMtx = NULL;          // 0.9.14: the writer task and loop() may both save the heal state
static bool healSaveBody();
static bool healSave() {
  if (!healMtx) healMtx = xSemaphoreCreateRecursiveMutex();
  if (healMtx) xSemaphoreTakeRecursive(healMtx, portMAX_DELAY);
  bool ok = healSaveBody();
  if (healMtx) xSemaphoreGiveRecursive(healMtx);
  return ok;
}
static bool healSaveBody() {
  hg_heal_state_seal(&HS);
  memcpy(&NI.hs, &HS, sizeof HS);                   // 1. noinit copy (always)
  if ((uint32_t)&__etext >= HEAL_PAGE) return false; // never write into the app
  static uint8_t buf[HEAL_SLOT]; memset(buf, 0xFF, sizeof buf); memcpy(buf, &HS, sizeof HS);
  bool ok = false;
  for (int a = 0; a < 3 && !ok; a++) {
    uint32_t slot = HEAL_SLOTS;
    for (uint32_t i = 0; i < HEAL_SLOTS; i++) if (healSlotEmpty(HEAL_PAGE + i * HEAL_SLOT)) { slot = i; break; }
    if (slot == HEAL_SLOTS || a > 0) { if (!healPageErase()) continue; slot = 0; }   // full, or a failed try: start the page over
    ok = healPageWrite(HEAL_PAGE + slot * HEAL_SLOT, buf, HEAL_SLOT);
  }
  if (ok) { healSaves++; healFlashWrites++; } else healFlashFails++;
  return ok;
}
static void healLoad() {
  healStateValid = false;
  if (NI.magic == HG_NI_MAGIC && hg_heal_state_valid(&NI.hs)) { memcpy(&HS, &NI.hs, sizeof HS); healStateValid = true; healSrc = 0; return; }
  for (int i = (int)HEAL_SLOTS - 1; i >= 0; i--) {  // the last valid slot is the newest (slots are written in order)
    const hg_heal_state_t* c = (const hg_heal_state_t*)(HEAL_PAGE + (uint32_t)i * HEAL_SLOT);
    if (!healSlotEmpty((uint32_t)c) && hg_heal_state_valid(c)) { memcpy(&HS, c, sizeof HS); healStateValid = true; healSrc = 1; return; }
  }
  healSrc = -1;
}
static void evPathUpdate() { hg_heal_events_path(HS.gen ? HS.gen : 1, evPath, sizeof evPath); }

// ---------------------------------------------------------------- 0.9.16 boot journal I/O (decisions: hg_bootguard.c)
// One reserved raw page, BG_PAGE (0xEB000: below the heal page 0xEC000 and InternalFS 0xED000, far above the app image). Written with
// the NVMC directly before the SoftDevice starts (the STARTED entry: synchronous, bounded) and through sd_flash_write after; every word
// read back from the memory-mapped flash. One mutex (healMtx) for every raw-page write: the writer task saves the heal state, the app
// task writes the journal.
#define BG_PAGE 0xEB000u
static uint32_t bgWrites = 0, bgWriteFails = 0;
static int bgWriteWord(void*, int idx, uint32_t w) {
  static uint32_t wb;                                // static: the SoftDevice reads the source after the call returns
  wb = w;
  return healPageWrite(BG_PAGE + 4u * (uint32_t)idx, &wb, 4) ? 1 : 0;
}
static int bgErase(void*) { return nvPageErase(BG_PAGE) ? 1 : 0; }
static const hg_bg_flash_t BGF = { (const volatile uint32_t*)BG_PAGE, bgWriteWord, bgErase, NULL };
static bool bgAppend(uint32_t w) {
  if ((uint32_t)&__etext >= BG_PAGE) { bgWriteFails++; return false; }
  if (!healMtx) healMtx = xSemaphoreCreateRecursiveMutex();
  if (healMtx) xSemaphoreTakeRecursive(healMtx, portMAX_DELAY);
  bool ok = hg_bg_append(&BGF, w) == 1;
  if (healMtx) xSemaphoreGiveRecursive(healMtx);
  if (ok) bgWrites++; else bgWriteFails++;
  return ok;
}

// every log write goes through here: a quarantined path is never opened again; a failure is a dropped write + counter
// 0.9.14: littlefs directly (the Adafruit File wrapper hides the error code) + a FS_SLOW line for any call > 500 ms or any
// failure: fid, bytes, ms, and the erases / programs / reads it took (many erases = littlefs relocating blocks whose
// verify failed; many reads = a long walk), and the littlefs error code (-5 IO, -28 NOSPC, -84 CORRUPT ...).
static int32_t fsLastRc = 0; static uint8_t fsLastRcFid = 0; static uint32_t fsSlowN = 0, fsFailN = 0;
static char fsSlowLast[128] = "";
static void evLog(const char* fmt, ...);
static bool fileAppend(const char* path, const uint8_t* d, uint32_t n, uint8_t fid) {
  if (hg_heal_is_quarantined(&HS, path)) return false;
  FsGuard g(fid);
  uint32_t r0 = ioRd, p0 = ioPr, e0 = ioEr, t0 = millis();
  lfs_t* L = logFS._getFS(); lfs_file_t f; lfs_ssize_t w = -1;
  logFS._lockFS();
  int rc = lfs_file_open(L, &f, path, LFS_O_WRONLY | LFS_O_CREAT | LFS_O_APPEND);
  if (rc >= 0) { w = lfs_file_write(L, &f, d, n); int rc2 = lfs_file_close(L, &f); if (w < 0) rc = (int)w; else if (rc2 < 0) rc = rc2; }
  logFS._unlockFS();
  uint32_t ms = millis() - t0;
  bool ok = rc >= 0 && w == (lfs_ssize_t)n;
  if (!ok) { fsLastRc = rc < 0 ? rc : -999; fsLastRcFid = fid; fsFailN++; }
  if (ms > 500 || !ok) {
    fsSlowN++;
    snprintf(fsSlowLast, sizeof fsSlowLast, "fid=%s path=%s bytes=%lu ms=%lu erases=%lu progs=%lu reads=%lu rc=%d", hg_heal_fid_name(fid), path,
             (unsigned long)n, (unsigned long)ms, (unsigned long)(ioEr - e0), (unsigned long)(ioPr - p0), (unsigned long)(ioRd - r0), ok ? 0 : (int)fsLastRc);
    evLog("FS_SLOW %s", fsSlowLast);
  }
  return ok;
}
static bool fsRemove(const char* path, uint8_t fid) { FsGuard g(fid); return logFS.remove(path); }
static bool bootSave() {
  bootf.magic = 0x48474254u; bootf.crc = crc32b(&bootf, sizeof bootf - 4);
  FsGuard g(HG_FID_BOOT);
  File f(logFS);
  if (!f.open("/log/boot.bin", FILE_O_WRITE)) return false;
  f.seek(0); f.truncate(0);
  bool ok = f.write((const uint8_t*)&bootf, sizeof bootf) == sizeof bootf;
  f.close();
  return ok;
}
static void bootLoad() {
  FsGuard g(HG_FID_BOOT);
  File f(logFS);
  bool ok = false;
  if (f.open("/log/boot.bin", FILE_O_READ)) { ok = f.read((uint8_t*)&bootf, sizeof bootf) == sizeof bootf; f.close(); }
  if (!ok || bootf.magic != 0x48474254u || bootf.crc != crc32b(&bootf, sizeof bootf - 4)) memset(&bootf, 0, sizeof bootf);
}

// list /log into the ring module's table
static hg_logfile_t ringFiles[HG_RING_MAX_FILES];
static char ringNames[HG_RING_MAX_FILES][16];      // 0.9.10: 16 (events_<gen>.txt is 12+ characters)
static int ringN = 0;
static void listLog() {
  ringN = 0;
  FsGuard g(HG_FID_LIST);
  File dir = logFS.open("/log", FILE_O_READ);
  if (!dir || !dir.isDirectory()) return;
  File e(logFS);
  while (ringN < HG_RING_MAX_FILES && (e = dir.openNextFile(FILE_O_READ))) {
    const char* nm = e.name();
    uint16_t seq = 0;
    char k = hg_ring_classify(nm, &seq);
    ringFiles[ringN].kind = k; ringFiles[ringN].seq = seq; ringFiles[ringN].size = e.size();
    strncpy(ringNames[ringN], nm, 15); ringNames[ringN][15] = 0;
    ringN++;
    e.close();
  }
  dir.close();
}
static int countBlock(void* p, lfs_block_t) { (*(uint32_t*)p)++; return 0; }
static uint32_t usedBlocks() {
  uint32_t n = 0;
  FsGuard g(HG_FID_LIST);
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
    if (fsRemove(p, HG_FID_RING)) { filesDeleted++; if (undumped) undumpedDeleted++;
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
  if (fsQuiet) { sfileAtQuietEnd = true; return; } // quiet boot: the new file is started when it ends
  ringMakeRoom(HG_RING_MARGIN_BLOCKS, HG_RING_MAX_S_FILES);
  curSeq = takeSeq();
  hg_ring_make_path('s', curSeq, curPath, sizeof curPath);
  hg_rec_t r; buildRecordBase(&r);
  r.marker = HG_M_FILE; r.flags |= HG_F_MARKER; r.aux = (uint16_t)bootCount;
  uint8_t b[HG_REC_SIZE]; hg_rec_pack(&r, b);
  if (!fileAppend(curPath, b, HG_REC_SIZE, HG_FID_SFILE)) flushErr++;
  recsInFile = 0; sFailsInRow = 0;
  evLog("FILE boot=%lu t_ms=%lu path=%s free_blocks=%lu", (unsigned long)bootCount, (unsigned long)millis(), curPath, (unsigned long)freeBlocks());
}

// after a reset: keep appending to the newest hour file if it is not full (T6a blocker B1) -
// a new file per boot is what used to push full hours out of the ring
static void bootHourFile() {
  if (fsState != FS_OK) return;
  if (fsQuiet) { sfileAtQuietEnd = true; return; }  // quiet boot: nothing appended until it ends (then a new file)
  listLog();
  uint16_t seq;
  if (HB.new_sfile || !hg_ring_boot_file(ringFiles, ringN, HG_DAY_FILE_BYTES, &seq)) { newHourFile(); return; }
  curSeq = seq;
  hg_ring_make_path('s', curSeq, curPath, sizeof curPath);
  if (hg_heal_is_quarantined(&HS, curPath)) { newHourFile(); return; }   // FS-HEAL: never append to a quarantined file
  uint32_t size = 0;
  for (int i = 0; i < ringN; i++) if (ringFiles[i].kind == 's' && ringFiles[i].seq == seq) size = ringFiles[i].size;
  hg_rec_t r; buildRecordBase(&r);
  r.marker = HG_M_FILE; r.flags |= HG_F_MARKER; r.aux = (uint16_t)bootCount;   // boot header inside the file
  uint8_t b[HG_REC_SIZE]; hg_rec_pack(&r, b);
  if (!fileAppend(curPath, b, HG_REC_SIZE, HG_FID_SFILE)) flushErr++;
  recsInFile = size / HG_REC_SIZE;
  evLog("FILE APPEND boot=%lu t_ms=%lu path=%s records=%lu", (unsigned long)bootCount, (unsigned long)millis(), curPath, (unsigned long)recsInFile);
}

// does a littlefs superblock exist? ("littlefs" magic in metadata block 0 or 1)
static bool lfsSignature() {
  uint8_t b[256];
  for (uint32_t blk = 0; blk < 2; blk++) {
    if (!flashRead(blk * 4096u, b, sizeof b)) return true;   // 0.9.15: unreadable is NOT blank: never a reason to format
    for (int i = 0; i + 8 <= (int)sizeof b; i++) if (memcmp(b + i, "littlefs", 8) == 0) return true;
  }
  return false;
}
static char fsMsg[64] = "";
// bench diagnostic (1.1.4): "flashdiag" prints the raw QSPI state and the chip ID step by step
static uint32_t bootQspi[4] = {0, 0, 0, 0};
static uint8_t flashSr1 = 0, flashSr2 = 0; static bool flashSrCleared = false;   // 0.9.14: status registers at boot       // ENABLE, PSEL.SCK, PSEL.CSN, PSEL.IO0 before storageInit
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
// ---- FS-HEAL boot steps (decisions: hg_fw_heal.c; this is only the I/O) ----
static uint32_t healPrevQuick = 0xFFFFFFFFu;        // quick_boots before the first-0.9.10-boot reset (0xFFFFFFFF = not reset)
static uint16_t legacyEvents = 0;                   // 1 = events.txt, 2 = events2.txt present (kept, never opened)
static void healFormat(const char* why) {            // re-format the LOG area only (InternalFS: profile, twin, plan, heal state untouched)
  bool ok;
  { FsGuard g(HG_FID_FORMAT); logFS.end(); ok = logFS.format() && logFS.begin(); }
  if (ok) { FsGuard g(HG_FID_MOUNT); logFS.mkdir("/log"); }
  fsState = ok ? FS_OK : FS_CORRUPT;
  strcpy(fsMsg, ok ? "re-formatted by fs-heal" : "fs-heal format failed");
  hg_heal_formatted(&HS); HB.format = 0; HB.quiet = 0; HB.new_sfile = 0; HB.remove_path[0] = 0;
  evPathUpdate(); healSave();
  evLog("FS_HEAL format log area why=%s result=%s formats=%u gen=%u (profile/twin/plan on InternalFS kept)", why, ok ? "ok" : "FAILED",
        HS.formats, HS.gen);
  evLog("FS_HEAL logs lost: every /log file (no salvage: reading the damaged area can assert again)");
}
static void healAfterBoot() {
  // newest s / r file and the highest events generation on disk
  listLog();
  uint16_t maxGen = 0, sMax = 0, rMax = 0; bool sAny = false, rAny = false;
  legacyEvents = 0;
  for (int i = 0; i < ringN; i++) {
    uint16_t g = hg_heal_events_gen(ringNames[i]); if (g > maxGen) maxGen = g;
    if (strcmp(ringNames[i], "events.txt") == 0) legacyEvents |= 1;
    if (strcmp(ringNames[i], "events2.txt") == 0) legacyEvents |= 2;
    if (ringFiles[i].kind == 's' && (!sAny || ringFiles[i].seq > sMax)) { sMax = ringFiles[i].seq; sAny = true; }
    if (ringFiles[i].kind == 'r' && (!rAny || ringFiles[i].seq > rMax)) { rMax = ringFiles[i].seq; rAny = true; }
  }
  char sPath[24] = "", rPath[24] = "";
  if (sAny) hg_ring_make_path('s', sMax, sPath, sizeof sPath);
  if (rAny) hg_ring_make_path('r', rMax, rPath, sizeof rPath);
  uint16_t genBefore = HS.gen;
  hg_heal_after_boot(&HS, &HB, bootLoop, maxGen, sPath, rPath);
  if (HB.disable) { healSave(); fsState = FS_DISABLED; strcpy(fsMsg, "switched off by fs-heal"); return; }
  if (HB.format) {
    healFormat(bootLoop ? "boot loop" : "marker");
    bootf.boot_count = bootCount; bootf.quick_boots = 0; quickBoots = 0; bootLoop = false;   // the fresh log area gets a fair start
    if (fsState == FS_OK) bootSave();
    return;
  }
  evPathUpdate();
  fsQuiet = HB.quiet;
  { char base[24]; snprintf(base, sizeof base, "events_%u.txt", (unsigned)HS.gen);   // 0.9.14: current events file size (rotation at 16 KB)
    for (int i = 0; i < ringN; i++) if (strcmp(ringNames[i], base) == 0) evBytes = ringFiles[i].size; }
  if (HB.quarantine_path[0])
    evLog("FS_HEAL quarantine fid=%s path=%s (never opened again)", HB.marker ? hg_heal_fid_name(HB.fid) : "bootloop", HB.quarantine_path);
  else if (HB.marker)
    evLog("FS_HEAL marker fid=%s count=%u: counted, nothing quarantined (no file named)", hg_heal_fid_name(HB.fid), HB.count);
  if (HB.rotate_events) evLog("FS_HEAL events gen %u -> %u path=%s", genBefore, HS.gen, evPath);
  if (HB.new_sfile && !fsQuiet) evLog("FS_HEAL new s-file (the newest one is left as it is)");
  if (HB.state_new || HB.new_build || HB.heal_boot || genBefore != HS.gen || HB.remove_path[0]) healSave();   // pending saved BEFORE the remove
  if (HB.remove_path[0]) {
    bool rc = fsRemove(HB.remove_path, HG_FID_HEAL);
    hg_heal_remove_done(&HS, &HB, rc); healSave();
    evLog("FS_HEAL remove %s %s", HB.remove_path, rc ? "ok" : "failed (kept, quarantined)");
  }
}
// 0.9.15: replaces Adafruit_SPIFlashBase::begin (unbounded WIP / suspend loops, no error path): P25Q16H (85 60 15) or P25Q32H (85 60 16),
// 55 MHz, quad enable checked, every wait bounded. The chip was just woken + software-reset by GPIO (storageInit).
static bool flashChipInit(uint32_t id) {
  uint8_t cap = (uint8_t)id;
  if ((id >> 8) != 0x8560u || (cap != 0x15 && cap != 0x16)) return false;
  flashIdExpect = id; flashBytes = 1ul << cap;
  if (!flashReady(500, true)) return false;
  qspiTr.setClockSpeed(55000000u, 55000000u);
  uint8_t sr2 = 0;
  if (!qspiTr.readCommand(0x35, &sr2, 1)) return false;
  if (!(sr2 & 0x02)) {                              // QE: the transport reads with 0x6B and programs with 0x32 (quad)
    uint8_t v = (uint8_t)(sr2 | 0x02);
    qspiTr.runCommand(0x06); qspiTr.writeCommand(0x31, &v, 1);
    if (!flashReady(100, true)) return false;
    if (!qspiTr.readCommand(0x35, &sr2, 1) || !(sr2 & 0x02)) return false;
  }
  qspiTr.runCommand(0x04);                          // WRDI
  return true;
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
    ok = flashChipInit(flashJedec);                           // 0.9.15: bounded (was Adafruit_SPIFlashBase::begin)
  }
  flashAwake = true;
  qspiActive = true;
  flashVerify = !ok;
  if (!ok) { fsState = FS_NO_FLASH; snprintf(fsMsg, sizeof fsMsg, "QSPI flash not detected, JEDEC %06lx gpio %06lx", (unsigned long)flashJedec, (unsigned long)firstId); return; }
  // 0.9.14: block-protect bits. P25Q16H SR1 bits 2-6 = BP0-BP4, SR2 bit 6 = CMP. Set bits make programs/erases in part of
  // the chip silently do nothing -> littlefs's verify fails -> it relocates block after block (seconds per append, then
  // an error). Read them every boot, clear them if set (SR2 written back unchanged except CMP, so QE stays on).
  { uint8_t a = 0, b2 = 0; qspiTr.readCommand(0x05, &a, 1); qspiTr.readCommand(0x35, &b2, 1); flashSr1 = a; flashSr2 = b2;
    if ((a & 0x7C) || (b2 & 0x40)) {
      uint8_t w[2] = { 0x00, (uint8_t)(b2 & 0xBF) };
      qspiTr.runCommand(0x06); qspiTr.writeCommand(0x01, w, 2); flashReady(100, true);
      qspiTr.readCommand(0x05, &a, 1); qspiTr.readCommand(0x35, &b2, 1);
      flashSrCleared = true;
      evLog("FS_HEAL flash block-protect bits were set (sr1=0x%02x sr2=0x%02x) -> cleared (now sr1=0x%02x sr2=0x%02x)", flashSr1, flashSr2, a, b2);
      flashSr1 = a; flashSr2 = b2;
    } }
  logCfg.block_count = flashBytes / 4096u;
  if (usbFsFormat) {                            // 0.9.11 emergency USB escape: format unconditionally, nothing else first
    HB.disable = 0; HB.format_pre_mount = 0; HB.format = 0; HB.marker = 0; guardCount = 0; hg_heal_reset(&HS);
    healFormat("usb fsformat");
    outf(CH_USB, "# FS_HEAL formatted\n"); Serial.flush();
    if (fsState != FS_OK) return;
  } else if (HB.disable) {
    fsState = FS_DISABLED; strcpy(fsMsg, "switched off by fs-heal");
    evLog("FS_HEAL storage OFF this boot (guard resets in a row=%u, last fid=%s): the band runs without a log", HB.count, hg_heal_fid_name(HB.fid));
    return;
  } else if (HB.format_pre_mount) {                    // FS-HEAL: a marker says mount/format died, or the trouble streak ran out
    healFormat(HB.count >= HG_HEAL_FORMAT_AT_COUNT ? "guard resets in a row" : "pre-mount");
  } else {
    bool mounted; { FsGuard g(HG_FID_MOUNT); mounted = logFS.begin(); }
    if (mounted) { fsState = FS_OK; strcpy(fsMsg, "mounted"); }
    else if (!lfsSignature()) {                 // blank / never ours: safe to format
      { FsGuard g(HG_FID_FORMAT); logFS.format(); fsState = logFS.begin() ? FS_OK : FS_CORRUPT; }
      strcpy(fsMsg, fsState == FS_OK ? "formatted (first use)" : "format failed");
    } else {                                    // ours but unreadable: kept until FS-HEAL's streak says re-format
      fsState = FS_CORRUPT; strcpy(fsMsg, "mount failed, data kept");
      hg_heal_mount_failed(&HS, &HB);
      if (HB.disable) { healSave(); fsState = FS_DISABLED; strcpy(fsMsg, "switched off by fs-heal"); return; }
      if (HB.format) healFormat("mount failed");
      else healSave();
    }
  }
  if (fsState != FS_OK) return;
  { FsGuard g(HG_FID_MOUNT); if (!logFS.exists("/log")) logFS.mkdir("/log"); }
  if (HB.remove_boot) {                         // FS-HEAL: boot.bin itself killed the last boot
    healSave();                                 // pending = /log/boot.bin, BEFORE the remove
    bool rc = fsRemove("/log/boot.bin", HG_FID_HEAL);
    hg_heal_remove_done(&HS, &HB, rc);
    evLog("FS_HEAL quarantine fid=boot path=/log/boot.bin remove=%s (counters restart)", rc ? "ok" : "failed");
  }
  bootLoad();
  bootf.boot_count++;
  // FS-HEAL: a soft reset is an upload only when the build changed. A soft reset of the same build is the FS guard
  // (marker or not: if GPREGRET2 were ever lost, the reset still counts towards the boot-loop detector)
  // 0.9.15 (plan A-09 / A-10): only an unexpected reset (watchdog, fs-guard, crash = soft reset of the same build with no marker,
  // lock-up) is boot-loop evidence. Pin reset (tested first, erratum 136), power cycle and wake leave quick_boots as it was; a new
  // build starts it at 0. (0.9.14 counted every boot that was not an upload: four power cycles at a demo = boot-loop hold.)
  if (hg_reset_is_fault(rstClass)) bootf.wdt_resets++;
  else if (rstClass == HG_RST_POWERON) bootf.other_resets++;
  if (HB.reset_quick_boots) healPrevQuick = bootf.quick_boots;   // new build: the old firmware's loop does not count
  bootf.quick_boots = hg_quick_boots_next(bootf.quick_boots, rstClass, HB.reset_quick_boots);   // cleared after 10 min up
  quickBoots = (uint8_t)(bootf.quick_boots > 255 ? 255 : bootf.quick_boots);
  bootLoop = quickBoots >= 3;
  bootSave();
  bootCount = bootf.boot_count;
  healAfterBoot();
}

// RAM buffers, flushed once a minute
static uint8_t secBuf[70 * HG_REC_SIZE]; static uint16_t secN = 0;
// min.bin is appended every HG_MIN_FLUSH_EVERY minutes, not every minute: littlefs v1 rewrites the
// /log directory pair on EVERY file close, so each close is one erase of the same two 4 KB blocks.
// Measured with the real littlefs v1.6 on a RAM flash (fw/tools/test_lfs_host.c): 1-min min.bin
// appends -> 1,529 erases/block/day on the hot pair (65 days of continuous logging to 100 k cycles);
// every 10 min -> 881/day (114 days). The 1 Hz hour files are still flushed every 60 s.
#define HG_MIN_FLUSH_EVERY 20   /* 09: records (= 10 minutes x inputs + guardian) per flash write */
static uint8_t minBuf[(HG_MIN_FLUSH_EVERY + 4) * HG_REC_SIZE];  static uint8_t minN = 0;
static char evBuf[1024]; static uint16_t evLen = 0; static uint32_t evDropped = 0;
// 0.9.14: the writer task never touches evBuf / USB / BLE: its lines go into wrLog and loop() logs them (wrLogDrain).
// A line starting with \x01 is a USB-only TRACE line (never in the events file).
static char wrLog[768]; static volatile uint16_t wrLogLen = 0; static uint32_t wrLogDrops = 0;
static void wrLogPush(const char* line) {
  uint16_t n = (uint16_t)strlen(line) + 1;
  taskENTER_CRITICAL();
  if (wrLogLen + n <= sizeof wrLog) { memcpy(wrLog + wrLogLen, line, n); wrLogLen += n; } else wrLogDrops++;
  taskEXIT_CRITICAL();
}
static bool demoLogOn();                            // [FW-DEMO] a replay is running (defined with the replay)
static bool evRealLine = false;                     // [FW-DEMO] wrLogDrain(): a writer-task line is real, never DEMO
static void evLog(const char* fmt, ...) {
  char line[176];
  va_list ap; va_start(ap, fmt); int n = vsnprintf(line, sizeof line - 1, fmt, ap); va_end(ap);
  if (n < 0) return;
  if (inWriter()) { wrLogPush(line); return; }
  if (n > (int)sizeof line - 2) n = sizeof line - 2;
  line[n++] = '\n'; line[n] = 0;
  if (demoLogOn() && !evRealLine) {                 // [FW-DEMO] replay: marked DEMO, echoed only, NEVER written to the events file
    char c[184]; snprintf(c, sizeof c, "# DEMO %s", line); outLine(CH_USB, c); return;   // [DEMO-NORESP] BLE: the compact `#R` lines instead
  }
  if ((size_t)evLen + (size_t)n < sizeof evBuf) { memcpy(evBuf + evLen, line, n); evLen += n; } else evDropped++;
  // events are also echoed live as comments
  char c[184]; snprintf(c, sizeof c, "# %s", line);
  outLine(CH_USB | CH_BLE, c);
}
static bool erasing = false;
// BOOT-TRACE (0.9.6-trace, kept): during the boot-time flushAll only, one short USB-only line per step + flush, so
// the last line printed shows where a hang is. Never written to flash or BLE.
#define TR(...) do { if (inWriter()) { char t_[120]; t_[0] = 1; snprintf(t_ + 1, sizeof t_ - 1, __VA_ARGS__); wrLogPush(t_); } \
                     else { outf(CH_USB, __VA_ARGS__); Serial.flush(); } } while (0)
static bool trFlush = false;            // the boot flush: TRACE lines (USB only) around each step
// ---------------------------------------------------------------- 0.9.14 log writer task
// loop() never writes the log any more: logKick() moves the pending minute records + events into the job buffers and
// wakes the writer task, which does the littlefs appends (an append can take seconds when littlefs relocates blocks;
// the bench saw 18 s). While the writer is busy, new data simply waits in loop()'s buffers for the next kick.
#define HG_EV_ROTATE_BYTES 16384u   /* events file rotates to a new generation at 16 KB */
#define HG_EV_KEEP_GENS    16       /* events generations kept on the log area (oldest removed) */
static uint8_t jMin[sizeof minBuf]; static uint16_t jMinN = 0; static char jEv[sizeof evBuf]; static uint16_t jEvLen = 0;
static bool jNewFile = false, jTrace = false, wantNewFile = false;
static SemaphoreHandle_t wrSem = NULL;
static uint32_t wrJobs = 0, wrSkips = 0, wrMaxMs = 0, wrLastMs = 0, evRotations = 0, evPruned = 0;
static void evRotatePrune() {                     // writer task: events file full -> next generation, keep the newest HG_EV_KEEP_GENS
  uint16_t old = HS.gen; HS.gen = HS.gen >= 65535u ? 1u : (uint16_t)(HS.gen + 1u); evPathUpdate(); healSave(); evBytes = 0; evRotations++;
  evLog("FS_HEAL events rotate %u -> %u at %lu B (path=%s)", old, HS.gen, (unsigned long)HG_EV_ROTATE_BYTES, evPath);
  listLog();
  for (;;) {
    int n = 0, oldest = -1;
    for (int i = 0; i < ringN; i++) { uint16_t g = hg_heal_events_gen(ringNames[i]); if (!g) continue; n++;
      if (oldest < 0 || g < hg_heal_events_gen(ringNames[oldest])) oldest = i; }
    if (n <= HG_EV_KEEP_GENS || oldest < 0) break;
    char p[24]; snprintf(p, sizeof p, "/log/%s", ringNames[oldest]);
    bool rc = fsRemove(p, HG_FID_RING); evPruned++;
    evLog("FS_HEAL events prune %s %s", p, rc ? "ok" : "failed");
    ringNames[oldest][0] = 0;                       // gone from this listing either way
  }
}
static void flushCore(bool force) {              // runs in the writer task (or in setup before it starts)
  (void)force;
  bool ok = true;
  if (trFlush) TR("# TRACE %lu flush minN=%u evLen=%u\n", (unsigned long)millis(), (unsigned)jMinN, (unsigned)jEvLen);
  if (jNewFile) { jNewFile = false; newHourFile(); }
  if (jMinN) {
    if (trFlush) TR("# TRACE %lu before fileAppend min %s\n", (unsigned long)millis(), curPath);
    if (fileAppend(curPath, jMin, (uint32_t)jMinN * HG_REC_SIZE, HG_FID_SFILE)) { recsInFile += jMinN; sFailsInRow = 0; } else { ok = false; recsLost += jMinN; sFailsInRow++; }
    jMinN = 0;
    if (trFlush) TR("# TRACE %lu after fileAppend min ok=%d\n", (unsigned long)millis(), (int)ok);
  }
  if (jEvLen) {
    uint16_t n = jEvLen;
    // FS-HEAL: live log is /log/events_<gen>.txt. A failed append = bytes dropped + counted, never retried in a loop;
    // HG_HEAL_RUNTIME_FAILS failures in a row move the log to a new generation. A HANG here is caught by the guard.
    if (trFlush) TR("# TRACE %lu before fileAppend events %s n=%u\n", (unsigned long)millis(), evPath, (unsigned)n);
    bool evOk = fileAppend(evPath, (const uint8_t*)jEv, n, HG_FID_EVENTS);
    if (trFlush) TR("# TRACE %lu after fileAppend events ok=%d\n", (unsigned long)millis(), (int)evOk);
    if (!evOk) { ok = false; evDroppedFailed += n; } else evBytes += n;
    jEvLen = 0;
    char old[HG_HEAL_PATH]; strcpy(old, evPath);
    if (hg_heal_events_result(&HS, &evFailsInRow, !evOk)) {
      evPathUpdate(); healSave(); evBytes = 0;
      evLog("FS_HEAL runtime: %u failed appends to %s -> events gen %u path=%s", (unsigned)HG_HEAL_RUNTIME_FAILS, old, HS.gen, evPath);
    } else if (evBytes >= HG_EV_ROTATE_BYTES) evRotatePrune();
  }
  if (ok) flushOk++; else flushErr++;
  if (sFailsInRow >= HG_HEAL_RUNTIME_FAILS) {   // FS-HEAL runtime: the s-file keeps failing -> leave it, start a new one
    evLog("FS_HEAL runtime: %u failed appends to %s -> new s-file", (unsigned)sFailsInRow, curPath);
    sFailsInRow = 0; newHourFile();
  } else if (recsInFile >= HG_DAY_RECS) {
    if (trFlush) TR("# TRACE %lu before newHourFile\n", (unsigned long)millis());
    newHourFile();   /* 09: one file per day of minute records */
  }
  flashSleep();
  if (trFlush) TR("# TRACE %lu after flashSleep\n", (unsigned long)millis());
}
static void wrTaskFn(void*) {
  for (;;) {
    xSemaphoreTake(wrSem, portMAX_DELAY);
    uint32_t t0 = millis(); wrJobT0 = t0;             // 0.9.16: the supervisor's view of this job
    trFlush = jTrace;
    flushCore(true);
    trFlush = false; jTrace = false;
    wrLastMs = millis() - t0; if (wrLastMs > wrMaxMs) wrMaxMs = wrLastMs; wrJobs++;
    wrBusy = false;
  }
}
static void wrStart() {
  if (wrTask) return;
  wrSem = xSemaphoreCreateBinary();
  // 0.9.15 (plan A-03): priority 0, below loop(). configUSE_TIME_SLICING is 0 in this core, so at loop's priority a long littlefs
  // traversal (no blocking call inside) held the CPU and starved loop() past the watchdog. Now loop() pre-empts the writer the moment
  // it is ready; the writer runs in loop()'s delay(10) gaps. A mutex it holds is priority-inherited, so it cannot invert this.
  if (wrSem && xTaskCreate(wrTaskFn, "logw", 1536, NULL, TASK_PRIO_LOWEST, &wrTask) == pdPASS) wrRunning = true;   // 6 KB stack
}
// loop() side: hand the pending log data to the writer (never waits)
static void flushAll(bool force = true) {
  if (erasing) return;                     // erase in progress: keep the records in RAM (<= 70 s)
  if (fsState != FS_OK || wrStuck) { recsLost += secN; secN = 0; minN = 0; evLen = 0; return; }   // 0.9.16: a stuck writer = storage off
  if (fsQuiet) {                           // FS-HEAL quiet boot: records dropped (counted), events kept in RAM until it ends
    quietDroppedRecs += secN + (force || minN >= HG_MIN_FLUSH_EVERY ? minN : 0); recsLost += secN; secN = 0;
    if (force || minN >= HG_MIN_FLUSH_EVERY) { recsLost += minN; minN = 0; }
    return;
  }
  if (wrBusy) { wrSkips++; return; }       // the writer is still on the last job: the data waits for the next kick
  secN = 0;                                // (09 writes minute records only)
  if (minN && (force || minN >= HG_MIN_FLUSH_EVERY)) { memcpy(jMin, minBuf, (size_t)minN * HG_REC_SIZE); jMinN = minN; minN = 0; }
  if (evLen) { memcpy(jEv, evBuf, evLen); jEvLen = evLen; evLen = 0; }
  if (wantNewFile) { jNewFile = true; wantNewFile = false; }
  if (!jMinN && !jEvLen && !jNewFile) return;
  jTrace = trFlush;
  if (!wrRunning) { flushCore(force); return; }
  wrJobT0 = millis(); wrBusy = true; xSemaphoreGive(wrSem);   // 0.9.16: the job's start for the supervisor, set BEFORE busy
}
static void wrLogDrain() {                        // loop(): log what the writer task said
  if (!wrLogLen) return;
  static char tmp[sizeof wrLog]; uint16_t n;
  taskENTER_CRITICAL(); n = wrLogLen; memcpy(tmp, wrLog, n); wrLogLen = 0; taskEXIT_CRITICAL();
  for (uint16_t i = 0; i < n; ) {
    const char* l = tmp + i; uint16_t k = (uint16_t)strlen(l);
    if (l[0] == 1) outf(CH_USB, "%s", l + 1); else { evRealLine = true; evLog("%s", l); evRealLine = false; }
    i += k + 1;
  }
}

// =====================================================================
// raw PPG capture (raw <seconds>): IR samples to /log/rNNNN.bin (+ live 'R' lines on USB)
// block = u32 t_first_ms, u16 n, u16 fs (=100), then n x 3 B IR (big-endian 18-bit), 308 B
// =====================================================================
static char rawPath[24] = "";
static void rawFlush() {
  if (wrBusy) return;                      // 0.9.14: keep the blocks in RAM until the writer is idle (rawDropped if it fills)
  // blocks may be appended while this write runs (ppgService() during a flash erase), so write only
  // the n bytes present now and keep whatever arrived after them
  uint16_t n = rawBufLen;
  if (!n) return;
  if (fsState == FS_OK && !fsQuiet && rawPath[0] == '/') { if (!fileAppend(rawPath, rawBuf, n, HG_FID_RAW)) rawDropped += n / sizeof rawBlock; }
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
  if (wrBusy) { replyf(ch, "# BUSY: the log writer is on a slow flash write, try again in a few seconds\n"); return; }
  if (rawActive) rawStop("restart");
  if (!hasPpg || !ppgEnabled) { replyf(ch, "# RAW: PPG not running\n"); return; }
  if (seconds < 10) seconds = 10;
  if (seconds > 1800) seconds = 1800;
  if (fsState == FS_OK && fsQuiet) strcpy(rawPath, "(quiet boot: USB only)");
  else if (fsState == FS_OK) {
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
  if (bleOn && Bluefruit.connected()) r->flags |= HG_F_BLE;
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
  if (logBle) bleQPut(line, 49);
  /* 09: 1 Hz records are not stored on flash (power, wear); the minute records are (guardianMinute) */
  fwSecond(&r);                                    // 09: feed the minute summariser (hg_fw.c)
}

// =====================================================================
// screen: status page while awake, ST7789 SLPIN + backlight GPIO LOW otherwise
// =====================================================================
static uint32_t screenOffAt = 0;
enum { UI_MAIN = 0, UI_PLAN = 1, UI_DIAG = 2, UI_TOAST = 3 };   // 0.9.6: moved up (screenWake resets uiDrawnPage)
static uint8_t uiPage = UI_MAIN, uiToastScr = 0, uiDrawnScr = 0xFF, uiDrawnPage = 0xFF; static uint32_t uiToastUntil = 0;
static void screenWake(uint32_t ms) {
  if (!screenOn) {
    gfx->displayOn();             // SLPOUT (120 ms)
    gfx->fillScreen(C_BLACK);
    screenOn = true;
    uiDrawnPage = 0xFF;           // 0.9.6: the panel is black now -> the next uiDraw() repaints everything
  }
  blTarget = blNormalPct();
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
static void drawDiag() {
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
  else snprintf(l, sizeof l, "Log: %s", fsState == FS_NO_FLASH ? "NO FLASH" : fsState == FS_BGOFF ? "OFF (guard)" : "FS ERROR");
  drawLine(7, (fsState == FS_OK && !flushErr) ? C_GREEN : C_RED, l);
  snprintf(l, sizeof l, "Time %s  BLE %s", timeValid ? "set" : "NOT SET", !bleOn ? "off" : Bluefruit.connected() ? "on" : "adv");
  drawLine(8, timeValid ? C_WHITE : C_ORANGE, l);
  uint32_t up = millis() / 1000;
  snprintf(l, sizeof l, "Up %luh%02lum  boot %lu", (unsigned long)(up / 3600), (unsigned long)(up / 60 % 60), (unsigned long)bootCount);
  drawLine(9, C_GREY, l);
  if (rawActive) { snprintf(l, sizeof l, "RAW %lus left", (unsigned long)((rawEndMs - millis()) / 1000)); drawLine(10, C_ORANGE, l); }
  else drawLine(10, C_GREY, "");
}

// =====================================================================
// 0.9.17 UI ENGINE (plan B.1 / B.2, session FW-UI): the hgui task owns the button and the motor. It polls the button (20 ms idle,
// 5 ms while something moves), plays the tick itself on press-DOWN (no app decision needed), runs the haptic sequencer and sends
// the button events to the app (queue). The app decides what a press MEANS (uiDispatch) and asks for patterns (hapPost).
// A screen redraw in the app (300-500 ms) can no longer swallow a press or delay the tick: hgui (priority 2) pre-empts it.
// =====================================================================
static hg_ui_t UI; static hg_hp_t HP; static hg_rz_t RZ;
static QueueHandle_t uiInQ = NULL, uiOutQ = NULL;
static volatile uint32_t p2bLast = 0, p2bMax = 0, uiPresses = 0, uiOutDrops = 0, uiInDrops = 0, hapFails = 0;
static const hg_hp_drv_t HPDRV = { drvGo, drvBusy, drvStop, drvReinit, NULL };
static StaticTask_t uiTcb; static StackType_t uiStack[512];          // 2 KB (plan B.1)
static void uiOut(const hg_ui_ev_t* e) { if (!uiOutQ || xQueueSend(uiOutQ, e, 0) != pdTRUE) uiOutDrops++; }
static void uiHandleMsg(const UiMsg* m, uint32_t now) {
  switch (m->kind) {
    case UM_HAP: hg_hp_request(&HP, &HPDRV, m->a, m->b, m->c, m->ms, now); break;
    case UM_STOP: hg_hp_stop(&HP, &HPDRV, m->a, now); break;
    case UM_CTX: { hg_ui_ctx_t c = { m->a, m->b }; hg_ui_ctx(&UI, &c, now); break; }
    default: break;
  }
}
static void uiStep(uint32_t now) {
  hg_ui_sample(&UI, digitalRead(PIN_BTN) == LOW, now);
  hg_ui_ev_t e;
  while (hg_ui_pop(&UI, &e)) {
    if (e.type == HG_UI_E_DOWN) {                   // the tick FIRST (plan B.2 rule 1); p2b = first low sample -> GO written
      hg_hp_request(&HP, &HPDRV, HG_HP_TICK, 0, 0, 0, millis());
      uint32_t d = millis() - e.t_ms; p2bLast = d; if (d > p2bMax) p2bMax = d; uiPresses++;
    }
    uiOut(&e);
  }
  hg_hp_step(&HP, &HPDRV, now);
  if (HP.fail_id) { hg_ui_ev_t f; f.type = HG_UI_E_HAP_FAIL; f.arg = HP.fail_id; f.dur_ms = 0; f.t_ms = now; HP.fail_id = 0; hapFails++; uiOut(&f); }
  motorBusy = hg_hp_busy(&HP); motorEnd = HP.last_end;
  uiBeatMs = now ? now : 1;
}
static void uiTaskFn(void*) {
  for (;;) {
    uint32_t now = millis();
    bool fast = hg_ui_active(&UI, now) || hg_hp_active(&HP);
    UiMsg m;
    if (xQueueReceive(uiInQ, &m, pdMS_TO_TICKS(fast ? 5 : 20)) == pdTRUE) { do uiHandleMsg(&m, millis()); while (xQueueReceive(uiInQ, &m, 0) == pdTRUE); }
    uiStep(millis());
  }
}
static void uiSend(const UiMsg& m) {
  if (uiTaskOn) { if (xQueueSend(uiInQ, &m, 0) != pdTRUE) uiInDrops++; }
  else uiHandleMsg(&m, millis());                   // no hgui task (creation failed): the app runs the engine inline
}
static bool hapSoftNow() { return lowBatMode || pofHold || (vbat == vbat && vbat < VBAT_SOFT && !charging()); }   // R4 A8.2: soft, never silent
static void hapPost(uint8_t id) { if (!id) return; UiMsg m = { UM_HAP, id, (uint8_t)hapSoftNow(), 0, 0 }; uiSend(m); }
static void hapRaw(uint8_t effect, uint16_t ms) { UiMsg m = { UM_HAP, HG_HP_RAW, 0, effect, ms }; uiSend(m); }
static void hapStop(uint8_t maxPrio) { UiMsg m = { UM_STOP, maxPrio, 0, 0, 0 }; uiSend(m); }
static void uiStart(bool wakeHold) {                // after the power-up pattern: from here on only hgui touches the motor
  hg_ui_init(&UI); hg_hp_init(&HP);
  if (wakeHold) hg_ui_wake_hold(&UI, millis());     // the press that woke the band from System OFF is not a command (plan C.2)
  uiInQ = xQueueCreate(16, sizeof(UiMsg)); uiOutQ = xQueueCreate(24, sizeof(hg_ui_ev_t));
  if (uiInQ && uiOutQ) uiTask = xTaskCreateStatic(uiTaskFn, "hgui", 512, NULL, TASK_PRIO_NORMAL, uiStack, &uiTcb);
  uiTaskOn = uiTask != NULL;
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
  if (wrBusy) { replyf(ch, "# BUSY: the log writer is on a slow flash write, try again in a few seconds\n"); return; }
  listLog();                               // 0.9.14: no flush here (the writer owns writes); the last minutes come with the next dump
  dumpN = 0; dumpI = 0; dumpOff = 0; dumpHdr = false; dumpCarryN = 0; dumpCh = ch;
  if (minOnly) { strcpy(dumpList[dumpN++], "/log/min.bin"); }
  else {
    // FS-HEAL: every events_<gen>.txt in generation order (quarantined ones and the legacy events.txt /
    // events2.txt are never opened), then s and r files in sequence order (quarantined ones skipped), then min.bin
    bool used[HG_RING_MAX_FILES] = {false};
    for (;;) {
      int best = -1;
      for (int i = 0; i < ringN; i++) {
        uint16_t g = hg_heal_events_gen(ringNames[i]);
        if (!used[i] && g && (best < 0 || g < hg_heal_events_gen(ringNames[best]))) best = i;
      }
      if (best < 0 || dumpN >= HG_RING_MAX_FILES - 2) break;
      used[best] = true;
      char p[24]; snprintf(p, sizeof p, "/log/%s", ringNames[best]);
      if (!hg_heal_is_quarantined(&HS, p)) strcpy(dumpList[dumpN++], p);
    }
    for (;;) {
      int best = -1;
      for (int i = 0; i < ringN; i++) if (!used[i] && (ringFiles[i].kind == 's' || ringFiles[i].kind == 'r') &&
                                          (mode != DUMP_NEW || ringFiles[i].seq >= bootf.dumped_next) &&
                                          (best < 0 || ringFiles[i].seq < ringFiles[best].seq)) best = i;
      if (best < 0 || dumpN >= HG_RING_MAX_FILES - 1) break;
      used[best] = true;
      char p[24]; snprintf(p, sizeof p, "/log/%s", ringNames[best]);
      if (!hg_heal_is_quarantined(&HS, p)) strcpy(dumpList[dumpN++], p);
    }
    strcpy(dumpList[dumpN++], "/log/min.bin");
  }
  dumpActive = true; dumpMode = mode;
  replyf(ch, "# DUMP START mode=%s files=%u boot=%lu t_ms=%lu unix=%lu\n", mode == DUMP_NEW ? "new" : (minOnly ? "min" : "all"), dumpN, (unsigned long)bootCount, (unsigned long)millis(), (unsigned long)nowUnix());
}
static void dumpStop(const char* why) {
  if (!dumpActive) return;
  dumpActive = false;
  HS.dump_path[0] = 0;                             // 0.9.12: RAM only (no InternalFS write per dump)
  replyf(dumpCh, "# DUMP %s\n", why);
  flashSleep();
}
static uint16_t dumpRoom() {
  if (dumpCh & CH_USB) return Serial ? (uint16_t)max(0, Serial.availableForWrite()) : 0;
  return bleReady() ? bleQFree() : 0;
}
static void dumpService() {
  if (!dumpActive) return;
  if (wrBusy) return;                      // 0.9.14: the dump pauses while the writer task writes (never blocks loop())
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
      // FS-HEAL: remember which file the dump reads (a read can trip the same corrupt pointer as an append)
      strncpy(HS.dump_path, path, HG_HEAL_PATH - 1); HS.dump_path[HG_HEAL_PATH - 1] = 0;   // 0.9.12: RAM only
      FsGuard g(HG_FID_DUMP);
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
    uint32_t got = 0;
    { FsGuard g(HG_FID_DUMP); File f(logFS); if (f.open(path, FILE_O_READ)) { f.seek(dumpOff); got = f.read(buf, want); f.close(); } }
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
// 09 GUARDIAN LAYER (inserted into 08_logger by fw/tools/make_09.py)
// The frozen Guardian Loop runs once a minute through hg_fw.c; everything here is plumbing: screens, haptics,
// BLE service, Body Twin file, profile, commands. No threshold or rule lives here.
// =====================================================================
static hg_guardian_t G;                 // frozen Guardian Loop state (3.7 KB)
static hg_fw_t FW;                      // glue + 24 h STATUS ring (29.7 KB)
static hg2_twin_t TW; static hg_twin_acc_t TACC;
static hg2_profile_t PROF = { 75.0f, 0.0f, 26.0f, 0 };   // default wearer: 75 y, female, BMI 26, no medicines (target user)
static bool modelOk = false;
static int twinLoadRc = -99; static uint32_t twinSaveCount = 0, twinSavesBoot = 0;
static int8_t tzQ = 8;                  // local time = UTC + tzQ x 15 min (8 = Athens winter; BLE TIME carries it)
static hg_forecast_buf_t FC;
static bool haveSafe = false; static uint32_t safeBitmap = 0; static uint8_t safePlanId = 0; static char safeTag[15] = "";
static bool everConnected = false;
#define HG_MAX_LINKS 2                  // 0.9.8: her phone + the family phone (Bluefruit.begin(2, 0))
#define HG_CONN_SLOTS 4                 // per-connection state is indexed by the SoftDevice conn handle (0..3 kept)
static uint32_t lastMinuteTick = 0, timeSyncGen = 0; static uint8_t lastState = 0xFF, lastScreen = 0xFF;

// ---------------------------------------------------------------- 0.9.7 ecosystem layer (hg_fw_eco.c; ECOSYSTEM_SPEC.md 2-5b)
// No threshold / model / guardian logic here: the planner only READS the guardian's output, warnings always win.
static hg_evring_t EV;                  // the last 64 events (RAM, static; also written to events.txt)
static hg_plan_t PL;                    // planner (nudges N1-N6) state
static hg_seed_t SEED; static bool haveSeed = false;           // CMD 0x19 / console `routine`, /routine.bin
static char famName[HG_FAMNAME_MAX + 1] = "";                   // CMD 0x18 / console `famname`, /famname.bin ("" = «οικογένεια»)
static hg_trend_t TREND;                // 30-min room trend for the main face
static uint16_t evTxLast[HG_CONN_SLOTS]; static bool evTxAll[HG_CONN_SLOTS]; static volatile bool evConnFresh[HG_CONN_SLOTS];   // EVENTS notify cursor, per link (0.9.8)
static uint16_t curConn = BLE_CONN_HANDLE_INVALID;   // the link whose CMD frame is being handled (0x16 SYNC is per link)
// ---------------------------------------------------------------- 0.9.8 Her Day (HERDAY_SPEC.md; ECOSYSTEM_SPEC.md 5d)
static hg_dayplan_t DP;                 // today + tomorrow plans (CMD 0x1B), /dayplan.bin, midnight roll
static uint8_t hoSim = 0xFF;            // console `homeout home|out` overrides the frozen home/out state for the planner, 0xFF = off
static uint32_t dpSaves = 0, visitsRx = 0;
static uint8_t famMsg = 0; static uint32_t famMsgUntil = 0;     // family message overlay (60 s), 0 = none
static bool fcDemo = false;             // console `fcdemo` loaded a constructed forecast (logged as DEMO)
static const uint32_t NUDGE_SCREEN_MS = 120000;                 // a nudge keeps the screen on 2 min; it stays active 10 min
static const uint32_t FAMMSG_MS = 60000;
enum { SCR_X_NUDGE = 0x40, SCR_X_BRAVO = 0x50, SCR_X_FAMACK = 0x51, SCR_X_FAMMSG = 0x52, SCR_X_CLEAR = 0x53,   // band-only screens (>= HG_SCR_N)
       SCR_X_ESC = 0x60, SCR_X_WORKED = 0x61, SCR_X_STILL = 0x62, SCR_X_HELPASKED = 0x63, SCR_X_PWR = 0x64,          // 0.9.17
       SCR_X_PWRNO = 0x65, SCR_X_HELPON = 0x66 };         // [FLASH-EASY] off refused (why, 2 s) | HELP without «ειδοποιούμε»
// ---------------------------------------------------------------- 0.9.9 alert quality (hg_fw_alert.c; ECOSYSTEM_SPEC.md 5e)
// Decides only what the band DOES with the frozen output (buzz, wake, WARN_SHOWN, nudges); the frozen state, STATUS frame and
// screen content are untouched. CHECK / DANGER / HELP / IMOK haptics pass through as the frozen guardian gives them.
static hg_al_t AL;
static hg_al_out_t ALO;                 // this minute's decision (guardianMinute -> ecoMinute)
// ---------------------------------------------------------------- 0.9.17 action ladder + gauge (hg_fw_ladder.c; owner decisions Nov 19)
static hg_ld_t LD;                      // closed-loop ladder (glue only: reads the frozen output, never writes it)
static hg_ga_lines_t GL; static uint8_t gaStep = HG_GA_UNKNOWN; static int8_t gaPos = 0;
static uint8_t gaForce = 0xFE;          // console `gauge <0-4>`: display override for the bench (0xFE = off)
static bool pwrPrompt = false;          // «Απενεργοποίηση;» on screen
// [FLASH-EASY] power path diagnostics (stat) + the refusal toast «Όχι τώρα: ...» (2 s)
static uint32_t pwrPrompts = 0, pwrRefusals = 0, pwrCancels = 0, pwrNoUntil = 0, helpSeenMs = 0;
static char pwrNoTxt[72] = "", pwrLastWhy[32] = "-";
// [FLASH-EASY] LIVE demo (`live on|off`, RAM only): the gauge DISPLAYS the real skin temperature T1 against a baseline (mean of
// the first 20 s of good contact after `live on`): 0 C green, +1 yellow, +2 orange, >= +3 red, interpolated; screen kept on,
// wrist raise ignored, «ΖΩΝΤΑΝΑ» tag. The engine, ladder, alerts and their screens run unchanged.
static bool liveDemo = false; static float liveBase = NAN, liveD = NAN, liveAcc = 0.0f; static uint8_t liveN = 0; static uint32_t liveNext = 0;
static bool ldBench = false;            // console `ladder ...`: the bench episode stays "on" until `ladder off` (no real heat needed)
static uint32_t flashUntil = 0, hapLostEvMs = 0, raiseWakes = 0; static bool raiseOn = true;
static uint8_t scrRot = 0;                          // [SCREEN-FLIP] 0 = as before, 2 = image turned 180 deg (/screen.bin; `flip`)
static const uint32_t CLEAR_MS = 10000; // the all-clear «Πάλι όλα καλά» toast
static void ecoEvent(uint8_t type, uint8_t arg);
static void ecoEventX(uint8_t type, uint8_t arg, const uint8_t* x);
static uint8_t ecoPress();
static void nudgeShow(uint8_t id, bool buzz);
static void famShow(uint8_t msg);
static uint8_t uiSrc = HG_SRC_BAND;    // event arg for IM_OK / HELP / HELP_CANCEL: 1 band button, 2 phone (0x1A ELDER_ACTION)

// ---------------------------------------------------------------- [FW-DEMO] heat-episode replay state (code: after guardianSecond)
// Replay = SIMULATED sensor input (hg_demo_trace.h, sim/velders) fed to the normal 1 Hz input of hg_fw; the frozen guardian,
// the alert layer, the planner, the screen, the haptics, EVENTS and STATUS are the real code. The live guardian state is
// copied aside (heap) at start and copied back at `replay stop` / the end; a reboot always comes back live.
enum { DM_OFF = 0, DM_WARM = 1, DM_RUN = 2, DM_END = 3 };
static struct { uint8_t on, noresp, fam; uint16_t btnIgn; int32_t k, kShown; uint32_t stepMs, nextMs, endMs; uint8_t* bak; hg_demo_st_t st;
                char ev[64]; char key[64]; } DM;   // [DEMO-NORESP] noresp: presses ignored, ladder EVENTS marked SIM; ev/fam/key: the `#R` line
static bool demoLogOn() { return DM.on != DM_OFF; }
static bool demoScreenHold() { return DM.on == DM_WARM || DM.on == DM_RUN; }   // [REPLAY-SCREEN] `#R end` lets the screen sleep again
static void connFast(uint16_t h, bool fast);         // [DEMO-NORESP] (with the replay code)
static uint32_t alNowMs() { return DM.on >= DM_RUN ? hg_demo_ms(DM.kShown) : millis(); }   // the alert layer's clock

// ---------------------------------------------------------------- local time
static int32_t localSecsReal() { return timeValid ? (int32_t)nowUnix() + (int32_t)tzQ * 900 : -1; }
static int32_t localSecs() {                        // [FW-DEMO] while a replay shows, the clock is the simulated one
  if (DM.on >= DM_RUN) { int32_t r = localSecsReal(); return (r >= 0 ? r / 86400 : HG_DEMO_DAY0) * 86400 + (int32_t)hg_demo_mod(DM.kShown) * 60; }
  return localSecsReal();
}
static uint16_t localMod() { int32_t s = localSecs(); return s < 0 ? 0xFFFF : (uint16_t)((s / 60) % 1440); }
static int32_t localDay() { int32_t s = localSecs(); return s < 0 ? -1 : s / 86400; }

// ---------------------------------------------------------------- 1 Hz -> hg_fw
static void fwSecond(const hg_rec_t*) {
  if (DM.on) return;                                // [FW-DEMO] replay: the simulated seconds are fed by demoMinute(), not the sensors
  hg_fw_sec_t s;
  s.t1_c = hasSkin ? t1C : NAN; s.t2_c = hasRef ? t2C : NAN; s.tair_c = hasSht ? tairC : NAN; s.rh_pct = hasSht ? rhPct : NAN;
  s.ppg_on = (uint8_t)(hasPpg && ppgEnabled);
  s.hr_bpm = hrDet.hr_bpm > 0 ? hrDet.hr_bpm : NAN; s.hr_q = hrDet.quality; s.pi_pct = hrDet.pi_pct;
  s.ppg_dc = hrDet.dc > 0 ? (uint32_t)hrDet.dc : 0;
  s.a_mean = secAMean; s.a_m2 = secAM2; s.a_n = secAN; s.a_peak_g = accPeak; s.zangle_deg = secAN >= 3 ? zMed / 100.0f : NAN;   // IMU lost -> NaN, not the stale z (T6b m9)
  hg_fw_second(&FW, &s);
}

// ---------------------------------------------------------------- 07's icons (copied unchanged by make_09.py)
// --- from /home/claude/hg_fw/07_all_parts/07_all_parts.ino (read-only), verbatim ---
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

// ---------------------------------------------------------------- 0.9.7 icons (same primitive style as 07's)
static void drawSunClock(int cx, int cy, int s, uint16_t c) {      // sun with clock hands: "the cool hours of the day"
  float r = s * 0.27f;
  for (int k = 0; k < 8; k++) {
    float a = k * 0.785398f, ca = cosf(a), sa = sinf(a);
    thickLine(cx + ca * r * 1.30f, cy + sa * r * 1.30f, cx + ca * r * 1.72f, cy + sa * r * 1.72f, s * 0.035f, c);
  }
  gfx->fillCircle(cx, cy, r, c);
  gfx->fillCircle(cx, cy, r - s * 0.06f, C_BLACK);
  thickLine(cx, cy, cx, cy - r * 0.62f, s * 0.03f, c);              // hour hand at 12
  thickLine(cx, cy, cx + r * 0.48f, cy + r * 0.10f, s * 0.03f, c);  // minute hand towards 3
}
static void drawShutters(int cx, int cy, int s, uint16_t c) {      // roller shutter: box on top, slats, side rails
  int w = s * 0.70f, h = s * 0.80f, x = cx - w / 2, y = cy - h / 2 + s * 0.04f;
  gfx->fillRoundRect(x - s * 0.07f, y - s * 0.12f, w + s * 0.14f, s * 0.11f, 3, c);
  gfx->fillRect(x - 4, y, 4, h, c); gfx->fillRect(x + w, y, 4, h, c);
  int sh = h / 6;
  for (int i = 0; i < 6; i++) gfx->fillRect(x + 3, y + i * sh + 2, w - 6, sh - 5, c);
}
static void drawWindow(int cx, int cy, int s, uint16_t c) {        // window frame + cross, with cool air waves
  int w = s * 0.62f, h = s * 0.80f, x = cx - w / 2 - s * 0.10f, y = cy - h / 2, t = s * 0.06f;
  gfx->fillRect(x, y, w, h, c); gfx->fillRect(x + t, y + t, w - 2 * t, h - 2 * t, C_BLACK);
  gfx->fillRect(cx - s * 0.10f - t / 2, y, t, h, c); gfx->fillRect(x, cy - t / 2, w, t, c);
  for (int k = 0; k < 3; k++) {                                     // three short waves to the right (air coming in)
    float yy = cy - s * 0.20f + k * s * 0.20f, x0 = x + w + s * 0.04f;
    thickLine(x0, yy, x0 + s * 0.08f, yy - s * 0.04f, 2.0f, C_WHITE);
    thickLine(x0 + s * 0.08f, yy - s * 0.04f, x0 + s * 0.16f, yy, 2.0f, C_WHITE);
  }
}
static void drawPhone(int cx, int cy, int s, uint16_t c) {         // smartphone: "a message from the family"
  int w = s * 0.50f, h = s * 0.90f, x = cx - w / 2, y = cy - h / 2;
  gfx->fillRoundRect(x, y, w, h, s * 0.08f, c);
  gfx->fillRect(x + s * 0.05f, y + s * 0.10f, w - s * 0.10f, h - s * 0.24f, C_BLACK);
  gfx->fillCircle(cx, y + h - s * 0.07f, s * 0.035f, C_BLACK);
  for (int k = 0; k < 3; k++) gfx->fillRect(x + s * 0.10f, y + s * 0.20f + k * s * 0.14f, w - s * 0.20f - (k == 2 ? s * 0.12f : 0), s * 0.05f, C_WHITE);
}

// ---------------------------------------------------------------- 0.9.7 rich text: the Greek fonts have no °, ✓ or arrows,
// so those UTF-8 characters are drawn in their character cell (cw x size wide) by richPrint
static uint8_t richSpecial(const char* p) {
  const uint8_t* u = (const uint8_t*)p;
  if (u[0] == 0xC2 && u[1] == 0xB0) return 1;                                    // °
  if (u[0] == 0xE2 && u[1] == 0x9C && u[2] == 0x93) return 2;                    // ✓
  if (u[0] == 0xE2 && u[1] == 0x86 && u[2] >= 0x91 && u[2] <= 0x93) return (uint8_t)(3 + u[2] - 0x91);   // ↑ → ↓
  return 0;
}
static void richGlyph(uint8_t k, int x, int y, uint8_t sz, uint16_t c, uint8_t cw) {
  float s = sz, cxp = x + cw * sz * 0.5f, capH = (cw == 8 ? 10 : 13) * s;   // y = baseline
  switch (k) {
    case 1: gfx->fillCircle(cxp, y - capH + 2 * s, 3 * s, c); gfx->fillCircle(cxp, y - capH + 2 * s, 1.4f * s, C_BLACK); break;
    case 2: drawCheck(cxp, y - capH * 0.45f, capH * 1.05f, c); break;
    case 3: thickLine(cxp, y - 1 * s, cxp, y - capH + 4 * s, 1.1f * s, c);
            gfx->fillTriangle(cxp, y - capH - 1 * s, cxp - 4 * s, y - capH + 5 * s, cxp + 4 * s, y - capH + 5 * s, c); break;
    case 4: thickLine(x + 1 * s, y - capH * 0.5f, x + cw * s - 5 * s, y - capH * 0.5f, 1.1f * s, c);
            gfx->fillTriangle(x + cw * s, y - capH * 0.5f, x + cw * s - 6 * s, y - capH * 0.5f - 4 * s, x + cw * s - 6 * s, y - capH * 0.5f + 4 * s, c); break;
    case 5: thickLine(cxp, y - capH, cxp, y - 5 * s, 1.1f * s, c);
            gfx->fillTriangle(cxp, y + 1 * s, cxp - 4 * s, y - 5 * s, cxp + 4 * s, y - 5 * s, c); break;
    default: break;
  }
}
static void richPrint(const char* txt, int x, int y, uint8_t sz, uint16_t col, uint8_t cw) {   // (x, baseline y)
  gfx->setTextColor(col); gfx->setTextSize(sz);
  char run[88]; uint8_t rn = 0; int cx = x, rx = x;
  for (const char* p = txt;;) {
    uint8_t k = *p ? richSpecial(p) : 0;
    bool startChar = ((uint8_t)*p & 0xC0) != 0x80;
    if (!*p || k || (rn >= sizeof run - 5 && startChar)) {
      if (rn) { run[rn] = 0; gfx->setCursor(rx, y); gfx->print(run); rn = 0; }
      if (!*p) break;
      if (k) { richGlyph(k, cx, y, sz, col, cw); cx += cw * sz; p += (k == 1 ? 2 : 3); continue; }
    }
    if (!rn) rx = cx;
    if (startChar) cx += cw * sz;
    run[rn++] = *p++;
  }
  gfx->setTextSize(1);
}



// ---------------------------------------------------------------- screens
static bool helpCancelled = false;      // HELP cancelled on the band or by the phone: until the next minute step shows it
static bool uiToastHold = false;        // 0.9.6: HELP / I'm OK toast held until guardianMinute() has acted on the button press
static bool uiAlertEx(bool withPrompt) {   // keep the screen on while the wearer must act
  uint8_t st = FW.last_out.state;
  if (st == HG_ST_HELP && (helpCancelled || !G.help)) return false;
  if ((withPrompt && pwrPrompt) || LD.state == HG_LD_ESC) return true;   // 0.9.17
  return modelOk && FW.minutes && (st == HG_ST_CHECK || st == HG_ST_DANGER || st == HG_ST_HELP);
}
static bool uiAlert() { return uiAlertEx(true); }
// [OFF-CONFIRM] the hgui "alert" context must NOT count the off prompt itself: it did, so the engine closed «Απενεργοποίηση;»
// as "an alert" ~20 ms after opening it (the gauge painted over it) and the confirming press became a plain press.
static uint16_t tbCol = C_WHITE;         // 0.9.17: text colour of textBlock (black on the light gauge colours)
static void textBlock(const char* txt, int y0, int y1) {   // centred, word-wrapped Greek text, largest size that fits
  gfx->setFont(u8g2_font_10x20_t_greek); gfx->setUTF8Print(true); gfx->setTextColor(tbCol);
  char words[16][40]; int nw = 0;
  { const char* p = txt; while (*p && nw < 16) { while (*p == ' ') p++; int k = 0; while (*p && *p != ' ' && k < 39) words[nw][k++] = *p++; words[nw][k] = 0; if (k) nw++; } }
  for (int size = 3; size >= 1; size--) {
    int perLine = 240 / (10 * size), lineH = 22 * size, maxLines = (y1 - y0) / lineH;
    char lines[6][80]; int nl = 0; lines[0][0] = 0; bool fits = true;
    for (int i = 0; i < nw && fits; i++) {
      int cur = utf8Len(lines[nl]), add = utf8Len(words[i]) + (cur ? 1 : 0);
      if (utf8Len(words[i]) > perLine) { fits = false; break; }
      if (cur + add > perLine) { if (++nl >= 6) { fits = false; break; } lines[nl][0] = 0; cur = 0; add = utf8Len(words[i]); }
      if (cur) strcat(lines[nl], " ");
      strcat(lines[nl], words[i]);
    }
    if (fits && nl + 1 <= maxLines) {
      gfx->setTextSize(size);
      int ytop = y0 + ((y1 - y0) - (nl + 1) * lineH) / 2;
      for (int l = 0; l <= nl; l++) { int w = utf8Len(lines[l]) * 10 * size; richPrint(lines[l], (240 - w) / 2, ytop + (l + 1) * lineH - 4 * size, (uint8_t)size, tbCol, 10); }   // 0.9.7: ° ✓ drawn
      gfx->setTextSize(1);
      return;
    }
  }
}
static void drawIconAt(uint8_t scr, int cx, int cy, int s) {
  switch (scr) {
    case HG_SCR_OK:       drawCheck(cx, cy, s, C_GREEN); break;
    case HG_SCR_DRINK:    drawDrop(cx, cy, s, C_BLUE); break;
    case HG_SCR_COOL: case HG_SCR_NUDGE: drawHouse(cx, cy, s, C_ORANGE); break;
    case HG_SCR_DANGER: case HG_SCR_CHECK: case HG_SCR_HELP: case HG_SCR_FAMILY: drawWarning(cx, cy, s, C_RED); break;
    case HG_SCR_IMOK:     drawCheckCircle(cx, cy, s, C_GREEN); break;
    case HG_SCR_BATTERY:  drawBattery(cx, cy, s, C_WHITE, C_RED); break;
    case HG_SCR_NOT_WORN: case HG_SCR_LOOSE: drawWarning(cx, cy, s, C_ORANGE); break;
    default: break;
  }
}
static void drawIcon(uint8_t scr) { drawIconAt(scr, 120, 82, 120); }
static void drawNudgeIcon(uint8_t id) {   // spec 1.5 icon set: sun-clock, shutters, drop, window, house
  switch (id) {
    case HG_N_BRIEF: case HG_N_LAST_COOL: drawSunClock(120, 82, 120, C_ORANGE); break;
    case HG_N_SHUTTERS: drawShutters(120, 82, 120, C_ORANGE); break;
    case HG_N_WATER: drawDrop(120, 82, 120, C_BLUE); break;
    case HG_N_AIR: drawWindow(120, 82, 120, C_BLUE); break;
    case HG_N_AC: drawHouse(120, 82, 120, C_BLUE); break;
    case HG_N_EVENING: drawSunClock(120, 82, 120, C_ORANGE); break;     // 0.9.8: tomorrow's day
    case HG_N_LEAVE_HOT: drawDrop(120, 82, 120, C_ORANGE); break;      // 0.9.8: hot outside, take water
    default: break;
  }
}
static void drawFooter() {
  gfx->fillRect(0, 252, 240, 28, C_BLACK);
  gfx->setFont(u8g2_font_10x20_t_greek); gfx->setTextSize(1); gfx->setTextColor(C_GREY);
  char l[32]; uint16_t mod = localMod();
  if (mod < 1440) snprintf(l, sizeof l, "%02u:%02u   %u%%%s", mod / 60, mod % 60, batteryPct(vbat), charging() ? " +" : "");
  else snprintf(l, sizeof l, "--:--   %u%%%s", batteryPct(vbat), charging() ? " +" : "");
  gfx->setCursor((240 - utf8Len(l) * 10) / 2, 274); gfx->print(l);
}
static void drawPlan() {
  gfx->fillScreen(C_BLACK);
  textBlock("\xce\x8f\xcf\x81\xce\xb5\xcf\x82 \xce\xb3\xce\xb9\xce\xb1 \xce\xad\xce\xbe\xce\xbf\xce\xb4\xce\xbf", 10, 80);   // Ώρες για έξοδο
  char l[96] = ""; int n = 0;
  for (int h = 0; h < 24 && n < 4; h++) {
    if (!(safeBitmap & (1ul << h)) || (h && (safeBitmap & (1ul << (h - 1))))) continue;
    int e = h; while (e < 24 && (safeBitmap & (1ul << e))) e++;
    char r[16]; snprintf(r, sizeof r, "%s%02d-%02d", n ? " " : "", h, e); strcat(l, r); n++;
  }
  textBlock(n ? l : "-", 90, 240);
}
// ---------------------------------------------------------------- 0.9.17 home screen = the "keep it green" gauge (owner decision Nov 19 18:31)
// Full-screen colour from the 20-30 min FORECAST against her lines (hg_ga_step), a dot on a curved scale (centre = balanced,
// right = getting hot) so it reads without colour, the clock in the arc, the reminder text (ladder / frozen DRINK-COOL) under it.
// Repainted only when the step, the dot or the text change (a full fill blocks the app ~300 ms; hgui keeps the button alive).
static struct { uint8_t step; int8_t pos; uint16_t bg; char clk[8], txt[64], low[40], bottom[24]; bool valid; } GM;
static void cpyz(char* d, size_t n, const char* s) { size_t k = strlen(s); if (k >= n) k = n - 1; memcpy(d, s, k); d[k] = 0; }
static void centerText(const char* t, int y, uint16_t col) { richPrint(t, (240 - (int)utf8Len(t) * 10) / 2, y, 1, col, 10); }
static void arcXY(float p, int r, int* x, int* y) { float a = (90.0f - p * 7.0f) * DEG_TO_RAD; *x = 120 + (int)lroundf(r * cosf(a)); *y = 150 - (int)lroundf(r * sinf(a)); }
static void drawGauge(bool full, const char* text) {
  static char b[48];
  uint8_t st = gaForce < HG_GA_STEPS ? gaForce : gaStep;
  int8_t pos = gaForce < HG_GA_STEPS ? (int8_t)(gaForce * 4 - 6) : gaPos;
  const hg_ga_col_t* k = hg_ga_colour(st);
  uint16_t bg = RGB565(k->r, k->g, k->b), fg = k->text_white ? C_WHITE : C_BLACK;
  if (liveDemo) {                                   // [FLASH-EASY] LIVE: colour position c 0..4 from the skin delta (green until the baseline)
    float d = liveD == liveD ? liveD : 0.0f, c = d <= 0.0f ? 0.0f : d <= 1.0f ? 2.0f * d : d <= 2.0f ? 1.0f + d : d <= 3.0f ? 1.0f + d : 4.0f;
    c = roundf(c * 10.0f) / 10.0f;                  // 0.1 steps: a repaint only when the shade moves
    uint8_t s0 = (uint8_t)c, s1 = s0 < HG_GA_STEPS - 1 ? (uint8_t)(s0 + 1) : s0; float f = c - (float)s0;
    const hg_ga_col_t *a = hg_ga_colour(s0), *b2 = hg_ga_colour(s1);
    bg = RGB565((uint8_t)lroundf(a->r + (b2->r - a->r) * f), (uint8_t)lroundf(a->g + (b2->g - a->g) * f), (uint8_t)lroundf(a->b + (b2->b - a->b) * f));
    st = (uint8_t)lroundf(c); k = hg_ga_colour(st); fg = k->text_white ? C_WHITE : C_BLACK;
    pos = (int8_t)lroundf(-6.0f + 4.0f * c);
  }
  if (!text) text = "";
  gfx->setFont(u8g2_font_10x20_t_greek); gfx->setUTF8Print(true);
  if (full || !GM.valid || st != GM.step || pos != GM.pos || bg != GM.bg || strcmp(text, GM.txt)) {
    gfx->fillScreen(bg);
    for (int i = -20; i <= 20; i++) { int x, y; arcXY(i * 0.5f, 96, &x, &y); gfx->fillCircle(x, y, (i % 10 == 0) ? 4 : 2, fg); }   // the scale
    if (st != HG_GA_UNKNOWN) { int x, y; arcXY(pos, 96, &x, &y); gfx->fillCircle(x, y, 13, fg); gfx->fillCircle(x, y, 6, bg); }   // the dot (a ring)
    if (text[0]) { tbCol = fg; textBlock(text, 158, 250); tbCol = C_WHITE; }
    GM.step = st; GM.pos = pos; GM.bg = bg; cpyz(GM.txt, sizeof GM.txt, text); GM.clk[0] = GM.low[0] = GM.bottom[0] = 0; GM.valid = true;
  }
  uint16_t mod = localMod();
  if (mod < 1440) snprintf(b, sizeof b, "%02u:%02u", mod / 60, mod % 60); else strcpy(b, "--:--");
  if (strcmp(b, GM.clk)) { gfx->fillRect(66, 100, 108, 46, bg); richPrint(b, 70, 140, 2, fg, 10); cpyz(GM.clk, sizeof GM.clk, b); }
  if (!text[0]) {                                   // nothing to do: the date under the arc
    hg_date_text(localDay(), b, sizeof b);
    if (strcmp(b, GM.low)) { gfx->fillRect(0, 170, 240, 30, bg); centerText(b, 192, fg); cpyz(GM.low, sizeof GM.low, b); }
  }
  float room = FW.minutes ? FW.last_in.s.t_air_c : NAN;
  char rb[16];
  if (room == room) snprintf(rb, sizeof rb, "%d\xc2\xb0", (int)lroundf(room)); else snprintf(rb, sizeof rb, "--\xc2\xb0");
  snprintf(b, sizeof b, "%s|%u%%%s", rb, batteryPct(vbat), charging() ? "+" : "");
  if (strcmp(b, GM.bottom)) {
    gfx->fillRect(0, 252, 240, 28, bg);
    richPrint(rb, 18, 274, 1, fg, 10);
    const char* bp = strchr(b, '|') + 1;
    richPrint(bp, 222 - (int)utf8Len(bp) * 10, 274, 1, fg, 10);
    cpyz(GM.bottom, sizeof GM.bottom, b);
  }
}
static const char* gaugeText(uint8_t scr) {         // the reminder on the colour: the ladder's step, else the frozen DRINK / COOL text
  uint8_t r = hg_ld_reminder(&LD);
  if (r == HG_LD_S_COOL) return HG_TXT_LD_GOCOOL;
  if (r == HG_LD_S_WATER) return hg_screen_text(HG_SCR_DRINK);
  if (scr == HG_SCR_DRINK || scr == HG_SCR_COOL) return hg_screen_text(scr);
  return "";
}
static void reasonLine(const char* r, int y) {   // spec 4: one line under the warning, 8 px font so 26 characters fit
  gfx->setFont(u8g2_font_unifont_t_greek); gfx->setUTF8Print(true);
  richPrint(r, (240 - (int)utf8Len(r) * 8) / 2, y, 1, C_WHITE, 8);
  gfx->setFont(u8g2_font_10x20_t_greek);
}
static void drawScreen(uint8_t scr, const char* reason) {
  static char t[96];
  if (scr >= SCR_X_NUDGE && scr < SCR_X_BRAVO) { drawNudgeIcon(scr - SCR_X_NUDGE); textBlock(hg_nudge_text(&PL, scr - SCR_X_NUDGE, t, sizeof t), 150, 250); }
  else if (scr == SCR_X_BRAVO) { drawCheckCircle(120, 82, 120, C_GREEN); textBlock(HG_TXT_BRAVO, 150, 250); }
  else if (scr == SCR_X_FAMACK) { drawCheckCircle(120, 82, 120, C_GREEN); textBlock(HG_TXT_FAMACK, 150, 250); }
  else if (scr == SCR_X_FAMMSG) { drawPhone(120, 82, 120, C_BLUE); textBlock(hg_family_text(famMsg, famName, t, sizeof t), 150, 250); }
  else if (scr == SCR_X_CLEAR) { drawCheckCircle(120, 82, 120, C_GREEN); textBlock(HG_TXT_ALLCLEAR, 150, 250); }   // 0.9.9 all-clear
  else if (scr == SCR_X_ESC) {                       // 0.9.17 escalation: responsiveness check + what to do + the family is told
    gfx->fillScreen(RGB565(170, 0, 0));
    textBlock(HG_TXT_LD_FAMILY, 4, 52); textBlock(HG_TXT_LD_LIEDOWN, 56, 196); textBlock(HG_TXT_LD_SEEME, 200, 250);
  }
  else if (scr == SCR_X_WORKED) {                    // 0.9.17 «Μπράβο, δροσίζεστε»: the colour slides back to green
    const hg_ga_col_t* g = hg_ga_colour(0); uint16_t bg = RGB565(g->r, g->g, g->b);
    for (int x = 0; x < 240; x += 40) gfx->fillRect(x, 0, 40, 280, bg);
    drawCheckCircle(120, 82, 120, C_WHITE); textBlock(HG_TXT_LD_WORKED, 150, 250);
  }
  else if (scr == SCR_X_STILL) { drawHouse(120, 82, 120, C_ORANGE); textBlock(HG_TXT_LD_STILL, 150, 250); }
  else if (scr == SCR_X_HELPASKED) { drawWarning(120, 82, 120, C_RED); textBlock(HG_TXT_HELP_ASKED, 150, 250); }
  else if (scr == SCR_X_PWR) { textBlock(HG_TXT_PWR_PROMPT, 60, 150); textBlock(HG_TXT_PWR_HINT, 170, 240); }
  else if (scr == SCR_X_PWRNO) { textBlock(pwrNoTxt, 50, 230); }   // [FLASH-EASY] «Όχι τώρα: ...»
  else if (scr == SCR_X_HELPON) {                    // [FLASH-EASY] HELP on the band: no «ειδοποιούμε την οικογένεια» (the phone is told as before)
    drawWarning(120, 82, 120, C_RED); textBlock(HG_TXT_HELP_ASKED, 150, 225);
    if (reason && reason[0]) reasonLine(reason, 250);   // «Κρατήστε 3 δευτ. για ακύρωση» once the 10 s lock is over
  }
  else if (reason && reason[0]) { drawIconAt(scr, 120, 68, 100); textBlock(hg_screen_text(scr), 124, 214); reasonLine(reason, 238); }
  else { drawIcon(scr); textBlock(hg_screen_text(scr), 150, 250); }
}
static void uiDrawBody(bool full);
static void uiDraw(bool full) {                     // [FW-DEMO] + the persistent «ΠΡΟΣΟΜΟΙΩΣΗ» label while a replay runs
  uiDrawBody(full);
  if (screenOn && liveDemo) {                       // [FLASH-EASY] the live-sensor demo says so (top right, clear of the arc)
    static const char LV[] = "\xce\x96\xce\xa9\xce\x9d\xce\xa4\xce\x91\xce\x9d\xce\x91";   // ΖΩΝΤΑΝΑ
    gfx->setFont(u8g2_font_unifont_t_greek); gfx->setUTF8Print(true);
    gfx->fillRect(240 - 54, 0, 54, 17, C_BLACK); gfx->setTextSize(1); gfx->setTextColor(C_GREEN);
    for (int i = 0; LV[2 * i]; i++) { char g[3] = { LV[2 * i], LV[2 * i + 1], 0 }; gfx->setCursor(240 - 52 + i * 7, 13); gfx->print(g); }
    gfx->setFont(u8g2_font_10x20_t_greek);
  }
  if (!screenOn || !DM.on) return;
  gfx->setFont(u8g2_font_unifont_t_greek); gfx->setUTF8Print(true);
  static const char L[] = "\xce\xa0\xce\xa1\xce\x9f\xce\xa3\xce\x9f\xce\x9c\xce\x9f\xce\x99\xce\xa9\xce\xa3\xce\x97";   // ΠΡΟΣΟΜΟΙΩΣΗ
  gfx->fillRect(0, 0, 80, 17, C_BLACK);            // 0.9.17: the gauge fills the screen with colour: a black box keeps it legible
  gfx->setTextSize(1); gfx->setTextColor(C_ORANGE);
  for (int i = 0; L[2 * i]; i++) { char g[3] = { L[2 * i], L[2 * i + 1], 0 }; gfx->setCursor(1 + i * 7, 13); gfx->print(g); }   // 7 px pitch: x 1-79, clear of the gauge arc
  gfx->setFont(u8g2_font_10x20_t_greek);
}
static void uiDrawBody(bool full) {
  if (!screenOn) return;
  if (!modelOk) {   // ARCH B6b acceptance 2: CRC failure -> stay on the error screen
    if (full || uiDrawnPage != 0xEE) { gfx->fillScreen(C_BLACK); drawWarning(120, 82, 120, C_RED);
      textBlock("\xce\xa3\xcf\x86\xce\xac\xce\xbb\xce\xbc\xce\xb1 \xce\xbc\xce\xbf\xce\xbd\xcf\x84\xce\xad\xce\xbb\xce\xbf\xcf\x85", 150, 250); uiDrawnPage = 0xEE; }   // Σφάλμα μοντέλου
    return;
  }
  uint8_t page = uiPage, scr = FW.minutes ? FW.last_out.screen : HG_SCR_OK;
  if (scr == HG_SCR_HELP && (helpCancelled || !G.help)) scr = HG_SCR_OK;   // cancelled HELP: no stale HELP screen
  if (scr == HG_SCR_NUDGE) scr = HG_SCR_OK;         // 0.9.17 owner decision: the frozen bedtime tip is a generic nudge, not shown
  if ((scr == HG_SCR_CHECK || scr == HG_SCR_DANGER || scr == HG_SCR_FAMILY || scr == HG_SCR_IMOK || scr == HG_SCR_OK || scr == HG_SCR_DRINK ||
       scr == HG_SCR_COOL) && LD.state == HG_LD_ESC) scr = SCR_X_ESC;   // 0.9.17 escalation wording (HELP / NOT_WORN keep theirs)
  bool overlay = false;
  if (uiToastHold || (uiToastUntil && (int32_t)(millis() - uiToastUntil) < 0)) { overlay = true; scr = uiToastScr; } else uiToastUntil = 0;
  if (overlay && scr == HG_SCR_HELP && helpCancelled) { overlay = false; scr = HG_SCR_OK; }   // 0.9.6: no stale HELP toast after a cancel
  if (overlay && scr == HG_SCR_IMOK && LD.state == HG_LD_ESC) { overlay = false; scr = SCR_X_ESC; }   // 0.9.17: a press never ends the escalation
  if (scr == HG_SCR_HELP) scr = SCR_X_HELPON;       // [FLASH-EASY] owner: no "notifying the family" screen after a HELP
  if (pwrNoUntil && (int32_t)(millis() - pwrNoUntil) >= 0) pwrNoUntil = 0;
  if (pwrNoUntil) { overlay = true; scr = SCR_X_PWRNO; }   // [FLASH-EASY] «Όχι τώρα: ...» 2 s
  if (pwrPrompt) { overlay = true; scr = SCR_X_PWR; }
  if (famMsgUntil && (int32_t)(millis() - famMsgUntil) >= 0) famMsgUntil = 0;
  if (!overlay && famMsgUntil) { overlay = true; scr = SCR_X_FAMMSG; }            // 0.9.7: family message, 60 s
  if (overlay) page = UI_TOAST; else if (uiAlert()) page = UI_MAIN;
  if (page == UI_DIAG) { if (full || uiDrawnPage != UI_DIAG) gfx->fillScreen(C_BLACK); uiDrawnPage = UI_DIAG; drawDiag(); return; }
  if (page == UI_PLAN) { if (full || uiDrawnPage != UI_PLAN) drawPlan(); uiDrawnPage = UI_PLAN; return; }
  if (page == UI_MAIN && scr == HG_SCR_OK && PL.active) scr = SCR_X_NUDGE + PL.active;   // 0.9.7: a nudge only on the OK screen
  if (page == UI_MAIN && (scr == HG_SCR_OK || scr == HG_SCR_DRINK || scr == HG_SCR_COOL)) {   // 0.9.17: the gauge (+ the reminder)
    drawGauge(full || uiDrawnPage != UI_MAIN || uiDrawnScr != scr, gaugeText(scr));
    uiDrawnScr = scr; uiDrawnPage = page; return;
  }
  static char why[48], drawnWhy[48];
  if (page == UI_TOAST) why[0] = 0;
  else hg_reason_text(FW.last_out.why, scr, FW.last_in.s.t_air_c, why, sizeof why);   // spec 4
  if (scr == SCR_X_HELPON) cpyz(why, sizeof why, (helpSeenMs && millis() - helpSeenMs >= HG_UI_HELP_LOCK_MS) ? "\xce\x9a\xcf\x81\xce\xb1\xcf\x84\xce\xae\xcf\x83\xcf\x84\xce\xb5 3 \xce\xb4\xce\xb5\xcf\x85\xcf\x84. \xce\xb3\xce\xb9\xce\xb1 \xce\xb1\xce\xba\xcf\x8d\xcf\x81\xcf\x89\xcf\x83\xce\xb7" : "");   // Κρατήστε 3 δευτ. για ακύρωση
  if (full || uiDrawnPage != page || uiDrawnScr != scr || strcmp(why, drawnWhy)) {
    gfx->fillScreen(C_BLACK); drawScreen(scr, why);
    uiDrawnScr = scr; uiDrawnPage = page; strcpy(drawnWhy, why);
    full = true;                                    // 0.9.6: the screen was cleared -> repaint the footer too
  }
  static uint32_t lastFoot = 0;
  if (full || millis() - lastFoot > 30000) { lastFoot = millis(); drawFooter(); }
}
static void uiToast(uint8_t scr, uint32_t ms, bool hold) { uiToastScr = scr; uiToastUntil = millis() + ms; uiToastHold = hold; screenWake(SCREEN_ON_MS); uiDraw(true); }

// ---------------------------------------------------------------- haptics (HG_HAP_* from the guardian, R3 6.3) -> the hgui sequencer
static const uint8_t HAP_COOL[8]  = { 15, WAIT10MS(30), 15, WAIT10MS(30), 15, 0 };   // boot only: the rest rung's Warning (vibrate)
static uint8_t hpFromFrozen(uint8_t hap, const hg_minute_out_t* o) {   // 0.9.17: the frozen / rules-layer haptic as a sequencer pattern
  if (o->screen == HG_SCR_NUDGE && o->state == HG_ST_OK) return HG_HP_NONE;   // owner decision: no generic bedtime tip
  switch (hap) {
    case HG_HAP_WATCH: return HG_HP_WATCH;
    case HG_HAP_COOL:  return HG_HP_COOL;
    case HG_HAP_CHECK: return o->state == HG_ST_HELP ? HG_HP_HELP_URGENT : HG_HP_URGENT;
    case HG_HAP_TICK:  return HG_HP_TICK;
    case HG_HAP_SOFT:  return HG_HP_CUE;
    default: return HG_HP_NONE;
  }
}
static uint8_t hpMax(uint8_t a, uint8_t b) { if (!a) return b; if (!b) return a; return hg_hp_pat(b)->prio >= hg_hp_pat(a)->prio ? b : a; }

// ---------------------------------------------------------------- button (0.9.17: the meaning of the hgui events; owner decision Nov 19 17:29)
static bool helpCancel(const char* src) {   // accidental HELP: a 2nd 3-s hold (band, after the 10 s lock) or ack type 3 (phone) cancels it
  if (FW.button == 2) { FW.button = 0; evLog("HELP cancelled before the guardian saw it src=%s", src); helpCancelled = false; return true; }
  if (!G.help) return false;
  hg_cmd_t c; memset(&c, 0, sizeof c); c.op = HG_CMD_FAMILY_ACK; c.ack_type = 3; c.alarm_id = G.help_id;
  int ch = hg_guardian_cmd(&G, &c);                 // frozen A7.2 rule: HELP latched until ack type 3 (also clears its family flag)
  evLog("HELP cancelled src=%s alarm=%lu changed=%d family=%u", src, (unsigned long)c.alarm_id, ch, G.family_pending);
  ecoEvent(HG_EV_HELP_CANCEL, uiSrc);               // 0.9.7: arg 1 band, 2 phone (ELDER_ACTION 3)
  helpCancelled = true;                             // uiAlert() off -> normal brightness at the next wake/toast
  hapStop(4);                                       // 0.9.6: stop the rest of the HELP haptic pattern
  blTarget = blNormalPct();   // 0.9.6: drop the warning brightness now
  applyBacklight();
  return ch != 0;
}
static bool checkOpen() { return FW.last_out.state == HG_ST_CHECK || (FW.last_out.check_min != 0xFF && FW.last_out.worn != 0); }
static void demoStop(const char* why);
static bool helpOn() { return FW.button == 2 || (G.help && !helpCancelled); }
static void ladderApply(const hg_ld_out_t* lo, uint8_t frozenHp);
static void uiHelp() {                              // a 3-s hold (or the phone's ELDER_ACTION 1)
  if (DM.on) demoStop("HELP (3 s hold / phone)");   // [FW-DEMO] a real HELP always goes to the LIVE guardian
  pendButton = true;
  hg_fw_button(&FW, 2);                             // latched: the guardian sees it at the minute boundary
  helpCancelled = false; pwrPrompt = false;
  uint8_t m = hg_plan_cancel(&PL); if (m) ecoEvent(HG_EV_NUDGE_MISSED, m);   // 0.9.7: HELP replaces a nudge at once
  famMsgUntil = 0;
  ecoEvent(HG_EV_HELP, uiSrc);
  hapPost(HG_HP_HELP); uiToast(HG_SCR_HELP, 15000, true);   // 0.9.6: held until the guardian has acted on the press
}
static void uiShort(bool wasAsleep) {               // a press (< 1.2 s), already felt as the tick on press-down
  if (DM.on && DM.noresp) {                         // [DEMO-NORESP] the scenario is "she does not respond": no press reaches the engine or the ladder
    DM.btnIgn++; evLog("BUTTON press ignored: replay noresp (simulated: she does not respond)");
    screenWake(SCREEN_ON_MS); uiDraw(wasAsleep); return;
  }
  pendButton = true;
  hg_fw_button(&FW, 1);                             // honest input: the frozen guardian sees every press (its CHECK / I'm OK path)
  hg_ld_out_t lo;
  if (modelOk && hg_ld_press(&LD, &lo)) {           // 0.9.17: "I did it" (reminder -> 20 min check) / "I am here" (escalation stays)
    bool esc = LD.state == HG_LD_ESC;
    hapStop(3);
    if (checkOpen()) ecoEvent(HG_EV_IM_OK, uiSrc);  // the frozen CHECK takes it as I'm OK: the event says so (the ladder note says more)
    ladderApply(&lo, 0);
    evLog("BUTTON press -> ladder %s (%s)", esc ? "responsive" : "done", hg_ld_state_name(LD.state));
    uiPage = UI_MAIN; screenWake(SCREEN_ON_MS); uiDraw(true); return;
  }
  if (checkOpen()) {   // "I'm OK" only answers a CHECK (T6b m15; 0.9.6: any open CHECK)
    hapStop(3); hapPost(HG_HP_YES); ecoEvent(HG_EV_IM_OK, uiSrc); uiToast(HG_SCR_IMOK, 10000, true); return;   // never a nudge DONE
  }
  if (wasAsleep) { uiPage = UI_MAIN; uint8_t n1 = ecoPress(); screenWake(n1 ? NUDGE_SCREEN_MS : SCREEN_ON_MS); uiDraw(n1 != 0); return; }   // 0.9.6: a wake-press only wakes (0.9.17: painted at press-down already)
  if (famMsgUntil) { famMsgUntil = 0; screenWake(SCREEN_ON_MS); uiDraw(true); return; }   // 0.9.7: a press closes the family message
  if (PL.active && uiDrawnScr == SCR_X_NUDGE + PL.active && uiDrawnPage == UI_MAIN) {      // 0.9.7: press on the nudge screen = DONE
    uint8_t id = hg_plan_done(&PL, localMod());
    ecoEvent(HG_EV_NUDGE_DONE, id); hapPost(HG_HP_YES);
    uiToast(SCR_X_BRAVO, 3000, false); return;                                              // «Μπράβο ✓» 3 s
  }
  uiPage = (uiPage == UI_MAIN && haveSafe) ? UI_PLAN : UI_MAIN;
  uint8_t n1 = ecoPress(); if (n1) uiPage = UI_MAIN;                                        // 0.9.7: N1 BRIEF on the first press after her wake time
  screenWake(n1 ? NUDGE_SCREEN_MS : SCREEN_ON_MS); uiDraw(true);
}
static void pwrOffNow(uint8_t src);
// [FLASH-EASY] the off double press refused: say why (Greek, 2 s) + one 'refused' tick, log it. The reasons mirror the hgui context
// (uiAppService): HELP on / within 60 s of a HELP / an alert, reminder, nudge or family message open.
static void pwrRefused(const hg_ui_ev_t* e) {
  char w[48]; const char* en;
  if (e->arg == HG_UI_R_HELP) { cpyz(w, sizeof w, "\xce\x92\xce\x9f\xce\x97\xce\x98\xce\x95\xce\x99\xce\x91 \xce\xb5\xce\xbd\xce\xb5\xcf\x81\xce\xb3\xce\xae"); en = "HELP on"; }   // ΒΟΗΘΕΙΑ ενεργή
  else if (e->arg == HG_UI_R_AFTER_HELP) {
    uint32_t el = e->t_ms - UI.help_end, left = el < HG_UI_OFF_AFTER_HELP_MS ? (HG_UI_OFF_AFTER_HELP_MS - el + 999u) / 1000u : 1u;
    snprintf(w, sizeof w, "\xce\xbc\xce\xb5\xcf\x84\xce\xac \xce\xb1\xcf\x80\xcf\x8c \xce\x92\xce\x9f\xce\x97\xce\x98\xce\x95\xce\x99\xce\x91 (%lu \xce\xb4\xce\xb5\xcf\x85\xcf\x84.)", (unsigned long)left);   // μετά από ΒΟΗΘΕΙΑ (x δευτ.)
    en = "within 60 s of a HELP";
  }
  else if (famMsgUntil) { cpyz(w, sizeof w, "\xce\xbc\xce\xae\xce\xbd\xcf\x85\xce\xbc\xce\xb1 \xce\xbf\xce\xb9\xce\xba\xce\xbf\xce\xb3\xce\xad\xce\xbd\xce\xb5\xce\xb9\xce\xb1\xcf\x82"); en = "family message on screen"; }   // μήνυμα οικογένειας
  else if (PL.active) { cpyz(w, sizeof w, "\xcf\x83\xcf\x85\xce\xbc\xce\xb2\xce\xbf\xcf\x85\xce\xbb\xce\xae \xcf\x83\xcf\x84\xce\xb7\xce\xbd \xce\xbf\xce\xb8\xcf\x8c\xce\xbd\xce\xb7"); en = "a Her Day tip is open"; }   // συμβουλή στην οθόνη
  else if (!uiAlertEx(false) && !checkOpen() && LD.state != HG_LD_ESC && (hg_ld_open(&LD) || FW.last_out.state == HG_ST_DRINK || FW.last_out.state == HG_ST_COOL)) {
    cpyz(w, sizeof w, "\xcf\x85\xcf\x80\xce\xb5\xce\xbd\xce\xb8\xcf\x8d\xce\xbc\xce\xb9\xcf\x83\xce\xb7"); en = "a reminder (water / cool) is open"; }   // υπενθύμιση
  else { cpyz(w, sizeof w, "\xce\xb5\xce\xb9\xce\xb4\xce\xbf\xcf\x80\xce\xbf\xce\xaf\xce\xb7\xcf\x83\xce\xb7"); en = "an alert (check / danger / escalation)"; }   // ειδοποίηση
  snprintf(pwrNoTxt, sizeof pwrNoTxt, "\xce\x8c\xcf\x87\xce\xb9 \xcf\x84\xcf\x8e\xcf\x81\xce\xb1: %s", w);   // Όχι τώρα: ...
  cpyz(pwrLastWhy, sizeof pwrLastWhy, en); pwrRefusals++;
  evLog("POWER double press refused: %s (toast shown 2 s)", en);
  hapPost(HG_HP_TICK);
  pwrNoUntil = millis() + 2000u; if (!pwrNoUntil) pwrNoUntil = 1;
  uiPage = UI_MAIN; screenWake(SCREEN_ON_MS); uiDraw(true);
}
static bool uiWasAsleep = false; static bool holdOn = false; static uint32_t holdT0 = 0; static int holdBar = 0;
static void uiDispatch(const hg_ui_ev_t* e) {       // the ONE place where a button event gets its meaning (plan B.2 rule 2)
  switch (e->type) {
    case HG_UI_E_DOWN: uiWasAsleep = !screenOn; holdOn = true; holdT0 = e->t_ms; holdBar = 0; screenWake(SCREEN_ON_MS); if (uiWasAsleep) { uiPage = UI_MAIN; uiDraw(true); } break;
    case HG_UI_E_UP: holdOn = false; if (holdBar) { holdBar = 0; uiDraw(true); } break;
    case HG_UI_E_SHORT: queueMarker(HG_M_BUTTON, 0, "button"); uiShort(uiWasAsleep); break;
    case HG_UI_E_MID: evLog("BUTTON released after %u ms (1.2-3.0 s): no action (owner decision)", e->dur_ms); break;
    case HG_UI_E_HELP:
      holdOn = false;
      if (helpOn()) { evLog("BUTTON 3 s hold while HELP is already on (from the phone): kept, not cancelled"); uiToast(SCR_X_HELPASKED, 3000, false); break; }
      queueMarker(HG_M_HELP, 0, "button-long"); uiHelp(); break;
    case HG_UI_E_HELP_CANCEL:
      holdOn = false;
      if (helpOn()) { helpCancel("button"); hapPost(HG_HP_YES); uiToast(HG_SCR_OK, 5000, false); } break;
    case HG_UI_E_HELP_LOCKED: holdOn = false; evLog("BUTTON 3 s hold in the first 10 s of HELP: locked, HELP stays"); uiToast(SCR_X_HELPASKED, 3000, false); break;
    case HG_UI_E_PWR_PROMPT: pwrPrompt = true; pwrNoUntil = 0; pwrPrompts++; hapPost(HG_HP_QUESTION); evLog("POWER prompt shown (double press)"); screenWake(SCREEN_ON_MS); uiDraw(true); break;
    case HG_UI_E_PWR_CONFIRM: pwrOffNow(1); break;
    case HG_UI_E_PWR_CANCEL: if (e->arg == HG_UI_R_HELP) holdOn = false;
      pwrCancels++; pwrPrompt = false; evLog("POWER prompt closed (%s)", e->arg == HG_UI_R_TIMEOUT ? "5 s, no input" : e->arg == HG_UI_R_GUARD ? "a fast 3rd tap" :
                                                              e->arg == HG_UI_R_HELP ? "HELP" : "an alert"); uiDraw(true); break;
    case HG_UI_E_PWR_REFUSED: pwrRefused(e); break;   // [FLASH-EASY] no longer silent: «Όχι τώρα: <why>» 2 s + one tick
    case HG_UI_E_HAP_FAIL: {                       // plan A-13 / B.5 rule 8: the motor is silent -> the screen flashes, the family is told
      const hg_hpat_t* p = hg_hp_pat(e->arg);
      evLog("HAPTIC LOST pattern=%s prio=%u (DRV2605L re-init failed): screen flash instead", p->name, p->prio);
      if (p->prio >= 2) { flashUntil = millis() + 4000u; if (!flashUntil) flashUntil = 1; uiPage = UI_MAIN; screenWake(SCREEN_ON_MS); uiDraw(true); }
      if (p->prio >= 2 || !hapLostEvMs || millis() - hapLostEvMs > 3600000u) { hapLostEvMs = millis() | 1u; ecoEvent(HG_EV_HAPTIC_LOST, e->arg); }
      break; }
    default: break;
  }
}
static void uiAppService(uint32_t now) {            // app loop: events from hgui, the context it needs, backlight, hold bar, flash
  if (!uiTaskOn) uiStep(now);
  hg_ui_ev_t e; int n = 0;
  while (n++ < 8 && uiOutQ && xQueueReceive(uiOutQ, &e, 0) == pdTRUE) uiDispatch(&e);
  static uint8_t ch = 0xFF, ca = 0xFF;
  uint8_t h = helpOn(), a = (uint8_t)(uiAlertEx(false) || checkOpen() || hg_ld_open(&LD) || PL.active || famMsgUntil ||
                                      (FW.minutes && FW.last_out.state != HG_ST_OK && FW.last_out.state != HG_ST_IMOK && FW.last_out.state != HG_ST_NOT_WORN &&
                                       FW.last_out.state != HG_ST_BATTERY));
  if (h && !helpSeenMs) { helpSeenMs = millis() | 1u; } else if (!h) helpSeenMs = 0;   // [FLASH-EASY] the HELP screen's cancel hint after 10 s
  if (h != ch || a != ca) { ch = h; ca = a; UiMsg m = { UM_CTX, h, a, 0, 0 }; uiSend(m); }
  static bool mb = false; if (motorBusy != mb) { mb = motorBusy; applyBacklight(); }   // the 50 % cap while the motor runs
  if (holdOn && screenOn && now - holdT0 >= 1000u) {   // hold progress toward HELP (3 s), a red bar at the top
    int w = (int)((now - holdT0 - 1000u) * 240u / (HG_UI_HELP_MS - 1000u)); if (w > 240) w = 240;
    if (w >= holdBar + 8 || (w == 240 && holdBar < 240)) { gfx->fillRect(holdBar, 0, w - holdBar, 8, C_RED); holdBar = w; }
  }
  if (flashUntil) {                                 // silent motor: blink the backlight (full / off) for 4 s
    if ((int32_t)(now - flashUntil) >= 0) { flashUntil = 0; blTarget = blNormalPct(); applyBacklight(); }
    else { blTarget = ((now / 250u) & 1u) ? BL_WARNING_PCT : 0; applyBacklight(); }
  }
}

// ---------------------------------------------------------------- 0.9.12 InternalFS writes that cannot fail silently
// ROOT CAUSE of the InternalFS asserts (most likely): with the SoftDevice on, the core's flash_nrf5x.c erases/programs a
// page through sd_flash_*, then waits for ANY flash event - NRF_EVT_FLASH_OPERATION_ERROR (the SoftDevice could not fit
// the ~85 ms page erase between BLE radio events, e.g. with the phone connected) releases it exactly like SUCCESS, and
// InternalFileSystem.cpp returns 0 to littlefs either way. The page silently keeps its old bytes, littlefs metadata
// goes inconsistent, and a later call trips an LFS_ASSERT. We count those error events (link with
// -Wl,--wrap=flash_nrf5x_event_cb, see README; without it the count stays 0) and re-do + read back every write.
static uint32_t ifsRetries = 0, ifsVerifyFails = 0, ifsSaveFails = 0;
extern "C" void __real_flash_nrf5x_event_cb(uint32_t evt) __attribute__((weak));
extern "C" void __wrap_flash_nrf5x_event_cb(uint32_t evt) {
  ifsFlashEvents++; if (evt == NRF_EVT_FLASH_OPERATION_ERROR) ifsFlashErrors++;
  fsIoK(1);                                         // 0.9.13: an InternalFS page operation finished = progress
  if (__real_flash_nrf5x_event_cb) __real_flash_nrf5x_event_cb(evt);
}
static bool ifsWriteOnce(const char* path, const void* d, size_t n, uint8_t fid) {
  FsGuard g(fid);
  File f(InternalFS); if (!f.open(path, FILE_O_WRITE)) return false;
  f.seek(0); f.truncate(0); bool ok = f.write((const uint8_t*)d, n) == n; f.close(); return ok;
}
static bool ifsReadBack(const char* path, const void* d, size_t n, uint8_t fid) {
  FsGuard g(fid);
  File f(InternalFS); bool ok = false;
  if (f.open(path, FILE_O_READ)) {
    if (f.size() == n) { uint8_t b[64]; size_t o = 0; ok = true;
      while (ok && o < n) { size_t k = n - o < sizeof b ? n - o : sizeof b; ok = f.read(b, k) == (int)k && !memcmp(b, (const uint8_t*)d + o, k); o += k; } }
    f.close();
  }
  return ok;
}
static void evLog(const char* fmt, ...);
static bool ifsWrite(const char* path, const void* d, size_t n, uint8_t fid) {
  if (ifsBad) return false;
  for (int a = 0; a < 3; a++) {
    uint32_t e0 = ifsFlashErrors;
    bool ok = ifsWriteOnce(path, d, n, fid);
    bool ferr = ifsFlashErrors != e0;
    if (ok && !ferr && ifsReadBack(path, d, n, fid)) { ifsRetries += (uint32_t)a; return true; }
    if (ferr) evLog("FS_HEAL ifs flash op error writing %s (SoftDevice could not schedule it), try %d of 3", path, a + 1);
    else ifsVerifyFails++;
    delay(30);
  }
  ifsSaveFails++;
  evLog("FS_HEAL ifs write of %s failed 3 times: kept in RAM only", path);
  return false;
}
// The InternalFS ladder, run in setup() from the GPREGRET2 marker BEFORE any other InternalFS call:
// 1st fault of a file -> remove it (quarantine); 2nd in a row, or the same file again later -> back up the profile in
// RAM, format ONLY InternalFS, write the profile back; 3rd in a row -> InternalFS off for this boot.
static bool profileLoad(); static bool profileSave();
static void ifsHealBoot(uint8_t fid, uint8_t count, uint8_t prevFid) {
  const char* pp[3];
  int act = hg_heal_ifs_plan(fid, count, prevFid, pp, 3);
  const char* nm = hg_heal_fid_name(fid);
  if (act == HG_IFS_OFF) {
    ifsBad = true;
    evLog("FS_HEAL ifs OFF this boot: InternalFS faults in a row=%u (last %s %s); profile/twin/family/day plan/heal state in RAM only", count, nm, hg_heal_ifs_files(fid));
    return;
  }
  if (act == HG_IFS_REMOVE) {
    for (int i = 0; i < 3 && pp[i]; i++) {
      bool rc; { FsGuard g(fid); InternalFS.begin(); rc = InternalFS.remove(pp[i]); }
      evLog("FS_HEAL ifs quarantine fid=%s remove %s %s", nm, pp[i], rc ? "ok" : "failed (absent)");
    }
    healIfsHealed = fid;
    return;
  }
  if (act == HG_IFS_FORMAT) {
    bool prof = false;
    if (fid != HG_FID_IFS_PROFILE) { { FsGuard g(HG_FID_IFS_HEAL); InternalFS.begin(); } prof = profileLoad(); }   // RAM backup in PROF
    bool ok; { FsGuard g(HG_FID_IFS_HEAL); ok = InternalFS.format(); InternalFS.begin(); }
    bool ps = prof && profileSave();
    healIfsHealed = 0xFF;                           // state file is gone: written fresh, ifs_healed cleared
    evLog("FS_HEAL ifs format InternalFS (fid=%s %s, fault %u in a row%s): %s; profile %s (age %.0f sex_m %.0f bmi %.1f med %u); twin, family name, routine, day plan, heal state, BLE bonds start fresh",
          nm, hg_heal_ifs_files(fid), count, prevFid == fid ? ", same file as last time" : "", ok ? "ok" : "FAILED",
          ps ? "restored" : prof ? "NOT restored" : "default (not readable)", PROF.age, PROF.sex_m, PROF.bmi, PROF.med_flags);
  }
}

// ---------------------------------------------------------------- Body Twin + profile files (InternalFS)
struct ProfileFile { uint32_t magic; float age, sex_m, bmi; uint8_t med, pad[3]; uint32_t crc; };
static_assert(sizeof(ProfileFile) == sizeof(((HgNoinit*)0)->prof), "the .hg_noinit profile copy holds one ProfileFile");
static bool profileLoad() {
  ProfileFile pf; bool ok = false;
  if (ifsBad) return false;
  { FsGuard g(HG_FID_IFS_PROFILE); File f(InternalFS);
    if (f.open("/profile.bin", FILE_O_READ)) { ok = f.read((uint8_t*)&pf, sizeof pf) == sizeof pf; f.close(); } }
  if (!ok || pf.magic != 0x46525048u || pf.crc != crc32b(&pf, sizeof pf - 4)) return false;
  if (!(pf.age >= 1 && pf.age <= 120 && pf.bmi >= 10 && pf.bmi <= 60)) return false;
  PROF.age = pf.age; PROF.sex_m = pf.sex_m; PROF.bmi = pf.bmi; PROF.med_flags = pf.med;
  memcpy(NI.prof, &pf, sizeof pf);                  // 0.9.16: RAM copy (a SAFE boot erases InternalFS and restores it from here)
  return true;
}
// 0.9.16: the profile from the .hg_noinit copy (it survives the soft / watchdog resets of a fault loop, not a power cycle)
static bool profileFromNoinit() {
  ProfileFile pf; memcpy(&pf, NI.prof, sizeof pf);
  if (pf.magic != 0x46525048u || pf.crc != crc32b(&pf, sizeof pf - 4)) return false;
  if (!(pf.age >= 1 && pf.age <= 120 && pf.bmi >= 10 && pf.bmi <= 60)) return false;
  PROF.age = pf.age; PROF.sex_m = pf.sex_m; PROF.bmi = pf.bmi; PROF.med_flags = pf.med; return true;
}
static bool profileSave() {
  ProfileFile pf; memset(&pf, 0, sizeof pf);
  pf.magic = 0x46525048u; pf.age = PROF.age; pf.sex_m = PROF.sex_m; pf.bmi = PROF.bmi; pf.med = PROF.med_flags; pf.crc = crc32b(&pf, sizeof pf - 4);
  memcpy(NI.prof, &pf, sizeof pf);                  // 0.9.16: RAM copy, even when InternalFS is off
  return ifsWrite("/profile.bin", &pf, sizeof pf, HG_FID_IFS_PROFILE);   // 0.9.12: guarded, flash-error checked, read back
}
static void infoUpdate();
static bool twinSave(const char* why) {   // only from the nightly hook or a PROFILE write (B6b acceptance 3); never format
  if (DM.on) { evLog("TWIN SAVE skipped why=%s: replay running (the Body Twin never learns from simulated data)", why); return false; }
  static uint8_t buf[HG_FW_TWIN_BUF];
  int n = hg_fw_twin_pack(&G, &TW, &TACC, twinSaveCount + 1, buf, sizeof buf);
  bool ok = false;
  if (n > 0) ok = ifsWrite("/twin.bin", buf, (size_t)n, HG_FID_IFS_TWIN);   // 0.9.12: guarded, flash-error checked, read back
  if (ok) { twinSaveCount++; twinSavesBoot++; }
  evLog("TWIN SAVE why=%s ok=%d bytes=%d save_count=%lu rest_hr=%.1f days=%u", why, ok, n, (unsigned long)twinSaveCount, TW.rest_hr, TW.days_learned);
  infoUpdate();
  return ok;
}
static void twinLoadAndInit() {
  static uint8_t buf[HG_FW_TWIN_BUF]; int n = 0;
  // rc -1 = no /twin.bin yet (it is first written by the nightly hook, which needs the clock and a night), -2.. = rejected
  if (!ifsBad) { FsGuard g(HG_FID_IFS_TWIN); File f(InternalFS);
    if (f.open("/twin.bin", FILE_O_READ)) { n = f.read(buf, sizeof buf); f.close(); } }
  twinLoadRc = hg_fw_twin_load(&G, &PROF, &TW, &TACC, n > 0 ? buf : NULL, (uint16_t)(n > 0 ? n : 0), &twinSaveCount);
}

// ---------------------------------------------------------------- BLE HG service (R4 A5; UUID base frozen with uuidgen, README)
#define HG_UUID(x) "0c76" x "-038b-46d5-8532-954dd1c5e01d"
BLEService        hgSvc(HG_UUID("0000"));
BLECharacteristic hgStatus(HG_UUID("0001")), hgCmd(HG_UUID("0002")), hgInfo(HG_UUID("0003"));
BLECharacteristic hgEvents(HG_UUID("0004"));        // 0.9.7: EVENTS, read + notify, 20-byte frames (hg_ev_pack)
static volatile uint8_t cmdQ[4][20]; static volatile uint8_t cmdLen[4]; static volatile uint8_t cmdHead = 0, cmdTail = 0;
static uint16_t debugLeft = 0; static uint8_t debugCh = 0;
static volatile uint16_t cmdConn[4];
static void hgCmdCb(uint16_t conn, BLECharacteristic*, uint8_t* data, uint16_t len) {   // BLE task: copy only
  uint8_t nh = (cmdHead + 1) & 3; if (nh == cmdTail) return;
  if (len > 20) len = 20;
  for (uint16_t i = 0; i < len; i++) cmdQ[cmdHead][i] = data[i];
  cmdLen[cmdHead] = (uint8_t)len; cmdConn[cmdHead] = conn; cmdHead = nh;
}
static volatile bool advKick = false;
static void hgOnConnect(uint16_t conn) {
  everConnected = true;
  if (conn < HG_CONN_SLOTS) evConnFresh[conn] = true;   // 0.9.7: live EVENTS from now on; the app catches up with SYNC_EVENTS
  BLEConnection* c = Bluefruit.Connection(conn);
  if (c) { c->monitorRssi(); c->requestConnectionParameter(792, 1, 600); }   // 990 ms, latency 1, 6 s (R4 A5, Apple QA1931)
  if (DM.on) connFast(conn, true);                  // [DEMO-NORESP] a page connecting during a replay gets the fast interval too
  advKick = true;                                   // 0.9.8: keep advertising while a 2nd link is free
}
static void hgOnDisconnect(uint16_t, uint8_t) { advKick = true; }
static void advService() {                          // 0.9.8: advertising stops on every connect; restart it while < 2 links
  if (!advKick || !bleOn) return;
  advKick = false;
  if (Bluefruit.Periph.connected() < HG_MAX_LINKS && !Bluefruit.Advertising.isRunning()) Bluefruit.Advertising.start(0);
}
static int8_t bleBucket() {                         // home/out input: the STRONGEST connected phone (0.9.8: up to 2 links)
  if (!bleOn || !Bluefruit.connected()) return everConnected ? 0 : -1;
  int8_t best = 0;
  for (uint16_t h = 0; h < HG_CONN_SLOTS; h++) {
    if (!Bluefruit.connected(h)) continue;
    BLEConnection* c = Bluefruit.Connection(h);
    int8_t r = c ? c->getRssi() : 0;
    if (r != 0 && (best == 0 || r > best)) best = r;
  }
  return (best != 0 && best > -75) ? 2 : 1;
}
static void infoUpdate() {
  if (!bleOn) return;
  hg_info_t in; memset(&in, 0, sizeof in);
  in.fw_version = HG_FW_NUM; in.nn_crc = HG2_NN_CRC32; in.boot_count = (uint16_t)bootCount;
  in.reset_reason = (uint8_t)((resetReason & POWER_RESETREAS_DOG_Msk) ? 1 : (resetReason & POWER_RESETREAS_RESETPIN_Msk) ? 2 :
                              (resetReason & POWER_RESETREAS_SREQ_Msk) ? 3 : (resetReason & POWER_RESETREAS_LOCKUP_Msk) ? 4 : 0);
  in.twin_saves = (uint16_t)twinSaveCount; memcpy(in.hg2_tag, HG2_NN_VERSION + 13, 7);   /* "hg2-YYYYMMDD-<7-char commit>-..." -> the commit (ca75ce4 at freeze-6) */
  uint8_t o[20]; hg_info_pack(&in, o); hgInfo.write(o, 20);
}
static void hgBleBegin() {
  hgSvc.begin();
  hgStatus.setProperties(CHR_PROPS_NOTIFY | CHR_PROPS_READ); hgStatus.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS); hgStatus.setFixedLen(20); hgStatus.begin();
  hgCmd.setProperties(CHR_PROPS_WRITE | CHR_PROPS_WRITE_WO_RESP); hgCmd.setPermission(SECMODE_NO_ACCESS, SECMODE_OPEN); hgCmd.setMaxLen(20);
  hgCmd.setWriteCallback(hgCmdCb); hgCmd.begin();
  hgInfo.setProperties(CHR_PROPS_READ); hgInfo.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS); hgInfo.setFixedLen(20); hgInfo.begin();
  hgEvents.setProperties(CHR_PROPS_NOTIFY | CHR_PROPS_READ); hgEvents.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS); hgEvents.setFixedLen(20); hgEvents.begin();
  uint8_t z[20] = {0}; hgStatus.write(z, 20); hgEvents.write(z, 20);
  Bluefruit.Periph.setConnInterval(780, 792);      // 975-990 ms preferred
  Bluefruit.Periph.setConnSlaveLatency(1);
  Bluefruit.Periph.setConnSupervisionTimeout(600); // 6 s
}
static void statusPublish(const uint8_t st[20]) {
  if (!bleOn) return;
  hgStatus.write(st, 20);
  for (uint16_t h = 0; h < HG_CONN_SLOTS; h++)      // 0.9.8: every connected phone
    if (Bluefruit.connected(h) && hgStatus.notifyEnabled(h)) hgStatus.notify(h, st, 20);
}
static void ecoCommand(const hg_eco_cmd_t* e, uint8_t ch);
static void handleFrame(const uint8_t* p, uint8_t n, uint8_t ch) {
  {                                                 // 0.9.7/0.9.8: CMD 0x16-0x1C are parsed HERE, before the frozen parser
    hg_eco_cmd_t e; int erc = hg_eco_cmd_parse(p, n, &e);   // 0 = not ours -> unchanged frozen path below
    if (erc < 0) { replyf(ch, "# CMD error %d op=0x%02x len=%u\n", erc, n ? p[0] : 0, n); return; }
    if (erc > 0) { ecoCommand(&e, ch); replyf(ch, "# CMD ok op=0x%02x\n", e.op); return; }
  }
  if (fcDemo && n && (p[0] == HG_CMD_FORECAST || p[0] == HG_CMD_SAFE_HOURS)) {   // 0.9.7: real plan data replaces the console DEMO
    hg_forecast_init(&FC); haveSafe = false; fcDemo = false; evLog("FORECAST DEMO dropped: real plan data arriving");
  }
  hg_cmd_t c; int rc = hg_cmd_parse(p, n, &c, &FC);
  if (rc < 0) { replyf(ch, "# CMD error %d op=0x%02x len=%u\n", rc, n ? p[0] : 0, n); return; }
  switch (c.op) {
    case HG_CMD_TIME:
      if (c.unix_s < 1735689600u || c.unix_s > 4102444800u || c.tz_q < -48 || c.tz_q > 56) {   // 2025..2100, UTC-12..+14 (T6b m2)
        replyf(ch, "# CMD TIME rejected unix=%lu tz_q=%d\n", (unsigned long)c.unix_s, c.tz_q); return; }
      timeSyncGen++;
      epochAtSync = c.unix_s; msAtSync = millis(); timeValid = true; tzQ = c.tz_q;
      evLog("TIME boot=%lu t_ms=%lu unix=%lu tzq=%d src=ble", (unsigned long)bootCount, (unsigned long)msAtSync, (unsigned long)c.unix_s, tzQ);
      queueMarker(HG_M_TIME, 0, "ble"); break;
    case HG_CMD_FORECAST: if (FC.complete) evLog("FORECAST complete (4 chunks) t_ms=%lu", (unsigned long)millis()); break;
    case HG_CMD_SAFE_HOURS:
      haveSafe = true; safeBitmap = c.safe_bitmap; safePlanId = c.plan_id; memcpy(safeTag, c.tag, sizeof safeTag - 1); safeTag[sizeof safeTag - 1] = 0;
      evLog("SAFE_HOURS bitmap=0x%06lx plan=%u tag=%s", (unsigned long)safeBitmap, safePlanId, safeTag); break;
    case HG_CMD_FAMILY_ACK: case HG_CMD_PROFILE: {
      bool helpBefore = G.help, famBefore = G.family_pending;
      int changed = hg_guardian_cmd(&G, &c);
      if (helpBefore && !G.help) { helpCancelled = true; hapStop(4); uiToastUntil = 0; uiToastHold = false;   // 0.9.6: drop the HELP toast + haptics
        evLog("HELP cancelled src=phone"); ecoEvent(HG_EV_HELP_CANCEL, 2); if (screenOn) { screenWake(SCREEN_ON_MS); uiDraw(true); } }
      // 0.9.7: the family got the HELP / DANGER alert (ack 1 or 2 clears the pending flag) -> «Η οικογένεια ειδοποιήθηκε ✓»
      else if (c.op == HG_CMD_FAMILY_ACK && c.ack_type != 3 && famBefore && !G.family_pending && !uiToastHold && !helpOn()) uiToast(SCR_X_FAMACK, 5000, false);   // [FLASH-EASY] not after a HELP
      evLog("CMD op=0x%02x field=%u value=%.3f ack=%u alarm=%lu changed=%d", c.op, c.field, c.value, c.ack_type, (unsigned long)c.alarm_id, changed);
      if (changed && c.op == HG_CMD_PROFILE && (c.field == 2 || c.field == 4)) {
        TW = G.twin;                                 // the guardian applied the Twin parameter; persist it
        if (FW.saves_today < HG_FW_MAX_SAVES_DAY) { FW.saves_today++; twinSave("profile"); }
        else evLog("TWIN SAVE deferred to nightly (5 saves today)");
      }
      break; }
    case HG_CMD_DEBUG: debugLeft = p[1] ? p[1] : 60; if (n >= 4 && p[2]) debugLeft = (uint16_t)(p[1] | (p[2] << 8)); if (debugLeft > HG_FW_RING_MIN) debugLeft = HG_FW_RING_MIN;
      debugCh = ch == CH_USB ? CH_USB : CH_BLE; replyf(debugCh, "# DEBUG ring frames=%u\n", debugLeft); break;
  }
  replyf(ch, "# CMD ok op=0x%02x\n", c.op);
}
static void evFreshService() {
  for (uint16_t h = 0; h < HG_CONN_SLOTS; h++) if (evConnFresh[h]) { evConnFresh[h] = false; evTxLast[h] = EV.last_seq; evTxAll[h] = false; }
}
static void eventsService() {                      // EVENTS notifications, <= 2 per loop pass per phone, in seq order
  if (!bleOn) return;
  evFreshService();
  for (uint16_t h = 0; h < HG_CONN_SLOTS; h++) {    // 0.9.8: each connected phone has its own cursor (SYNC_EVENTS is per link)
    if (!Bluefruit.connected(h) || !hgEvents.notifyEnabled(h)) continue;
    for (int k = 0; k < 2; k++) {
      int i = hg_ev_first_after(&EV, evTxLast[h], evTxAll[h] ? 1 : 0);
      if (i < 0) break;
      const hg_ev_t* e = hg_ev_at(&EV, (uint8_t)i);
      uint8_t f[20]; hg_ev_pack(e, (uint16_t)bootCount, f);
      if (!hgEvents.notify(h, f, 20)) break;        // no TX buffer now: the same event again next pass
      evTxLast[h] = e->seq; evTxAll[h] = false;
    }
  }
}
static void hgBleService() {
  advService();
  evFreshService();                                 // before a SYNC in this pass
  while (cmdTail != cmdHead) {
    uint8_t b[20]; uint8_t n = cmdLen[cmdTail];
    for (uint8_t i = 0; i < n; i++) b[i] = cmdQ[cmdTail][i];
    curConn = cmdConn[cmdTail];
    cmdTail = (cmdTail + 1) & 3;
    handleFrame(b, n, CH_BLE);
    curConn = BLE_CONN_HANDLE_INVALID;
  }
  // 0x1F DEBUG: stream the last N minutes of STATUS frames ("G <40 hex>"), two lines per pass
  static uint8_t fr[1][20];
  for (int k = 0; k < 2 && debugLeft; k++) {
    if (debugCh == CH_BLE ? bleQFree() < 48 : (!Serial || Serial.availableForWrite() < 48)) break;
    uint16_t have = FW.ring_n; if (debugLeft > have) debugLeft = have; if (!debugLeft) break;
    uint16_t idx = (uint16_t)((FW.ring_head + HG_FW_RING_MIN - debugLeft) % HG_FW_RING_MIN);
    memcpy(fr[0], FW.ring[idx], 20);
    char h[48]; h[0] = 'G'; h[1] = ' '; hg_hex(fr[0], 20, h + 2); strcat(h, "\n"); outLine(debugCh, h);
    debugLeft--;
  }
  eventsService();
}

// ---------------------------------------------------------------- 0.9.7 ecosystem: events, planner glue, family messages, files
static void ecoEvent(uint8_t type, uint8_t arg) { ecoEventX(type, arg, NULL); }
static void ecoEventX(uint8_t type, uint8_t arg, const uint8_t* x) {   // 0.9.8: x = frame bytes 11-18 (VISIT / PLAN_ITEM)
  if (DM.on) {                                      // [DEMO-NORESP] the `#R` line lists this minute's EVENTS (NAME.arg)
    size_t L = strlen(DM.ev); snprintf(DM.ev + L, sizeof DM.ev - L, "%s%s.%u", L ? "," : "", hg_ev_name(type), arg);
    if (type == HG_EV_LD_NOTE || type == HG_EV_LD_ESCALATED) DM.fam = 1;
  }
  hg_al_event(&AL, type, arg, alNowMs());           // 0.9.9 scorecard: shown / done / missed / I'm OK, time to acknowledge
  const hg_ev_t* e = hg_ev_add_x(&EV, nowUnix(), type, arg, x);
  uint8_t f[20]; hg_ev_pack(e, (uint16_t)bootCount, f); if (bleOn) hgEvents.write(f, 20);   // read value = the newest event
  evLog("EVT seq=%u type=%u %s arg=%u unix=%lu", e->seq, type, hg_ev_name(type), arg, (unsigned long)e->unix_s);   // -> events.txt
}
static bool dpSave();
static void dpRoll() {
  int32_t d = localDay();
  if (hg_dp_roll(&DP, d)) { bool ok = dpSave(); evLog("DAYPLAN roll day=%ld today=%u tomorrow=%u saved=%d", (long)d, DP.day[0].n, DP.day[1].n, ok); }
}
static void planIn(hg_plan_in_t* in, bool press) {
  if (DM.on) {                                      // [FW-DEMO] the simulated person: no forecast, seed, day plan or console override
    hg_demo_plan_in(&DM.st, DM.kShown, in);
    in->warning = in->warning || uiToastHold || (G.help && !helpCancelled);
    in->press = press; return;
  }
  memset(in, 0, sizeof *in);
  in->mod = localMod(); in->day = localDay();
  in->warning = (FW.minutes && FW.last_out.state != HG_ST_OK) || uiToastHold || (G.help && !helpCancelled) || FW.button == 2;
  in->fc72 = FC.complete ? FC.data : NULL;
  in->safe_bitmap = safeBitmap; in->have_safe = haveSafe;
  in->room_c = FW.minutes ? FW.last_in.s.t_air_c : NAN;
  in->seed = haveSeed ? &SEED : NULL;
  in->l_valid = G.rt.sleep_valid; in->l_days = G.rt.days_learned; in->l_sleep_on = G.rt.sleep_on; in->l_sleep_off = G.rt.sleep_off;
  in->press = press;
  in->ext_nudge = (uint8_t)(FW.minutes && FW.last_out.nudge);
  dpRoll();                                         // 0.9.8: local midnight -> tomorrow's plan becomes today's
  bool dpNow = DP.today >= 0 && DP.today == in->day;
  in->dp_today = dpNow && DP.day[0].n ? &DP.day[0] : NULL;
  in->dp_tomorrow = dpNow && DP.day[1].n ? &DP.day[1] : NULL;
  in->home_out = hoSim != 0xFF ? hoSim : (FW.minutes ? FW.last_out.home_out : 0xFF);
  in->herday_only = 1;                              // 0.9.17 owner decision (Nov 19 18:04): Her Day timing advice only, no generic nudges
}
static void nudgeShow(uint8_t id, bool buzz) {
  ecoEvent(HG_EV_NUDGE_SHOWN, id);
  uiPage = UI_MAIN;
  if (buzz) hapPost(HG_HP_CUE);                     // 0.9.17: the sequencer drops it under a warning pattern still playing
  screenWake(NUDGE_SCREEN_MS); uiDraw(true);
}
static uint8_t ecoPress() {                         // a short press (not an I'm OK): N1 BRIEF by press
  if (!modelOk) return 0;
  hg_plan_in_t in; planIn(&in, true);
  uint8_t id = hg_plan_press(&PL, &in);
  if (id) ecoEvent(HG_EV_NUDGE_SHOWN, id);
  return id;
}
static void planOut(const hg_plan_out_t* o) {      // MISSED (timeout / replaced by N8) first, then the new nudge
  if (o->missed) ecoEvent(HG_EV_NUDGE_MISSED, o->missed);
  if (o->show) nudgeShow(o->show, true);
  else if (o->missed && screenOn) uiDraw(false);
}
static void scoreEmit(const char* why) {            // 0.9.9: EVENTS type 13 SCORE, pages 0-2 (console `score`, local midnight)
  for (uint8_t pg = 0; pg < 3; pg++) { uint8_t x[8]; hg_al_score_x(&AL, pg, x); ecoEventX(HG_EV_SCORE, pg, x); }
  evLog("SCORE emitted (%s)", why);
}
static void alertNotes() {                          // 0.9.9: every hold-back / audit of this minute -> the events log (0.9.10: events_<gen>.txt) (+ EVENTS 11)
  char vb[48]; hg_al_valid_text(AL.valid, vb, sizeof vb);
  for (uint8_t i = 0; i < ALO.n_notes; i++) {
    const hg_al_note_t* n = &ALO.notes[i];
    if (n->reason == 0) { evLog("ALERT %s hold limit reached: shown anyway (arg %u) valid=%s", hg_al_what_name(n->what), n->arg, vb); continue; }
    evLog("ALERT %s %s reason=%s arg=%u valid=%s", hg_al_what_name(n->what), n->what == HG_AL_W_CHECK ? "audit (passed through, NOT held)" : "held",
          hg_al_reason_name(n->reason), n->arg, vb);
    if (n->ev) { uint8_t x[8]; hg_al_held_x(n, x); ecoEventX(HG_EV_ALERT_HELD, n->what, x); }
  }
}
static void ecoMinute() {                           // once a minute, right after guardianMinute()
  if (!modelOk) return;
  hg_trend_push(&TREND, FW.last_in.s.t_air_c);
  hg_plan_in_t in; planIn(&in, false);
  hg_plan_out_t o; hg_al_plan_minute(&AL, &ALO, &PL, &in, &o);   // 0.9.9: validity gate + trusted, persisted room value
  alertNotes();
  planOut(&o);
  if (DM.on) return;                                // [FW-DEMO] the simulated day never rolls the scorecard
  static int32_t scoreDay = -1; int32_t d = localDay();
  if (d >= 0 && scoreDay >= 0 && d != scoreDay) scoreEmit("midnight");
  if (d >= 0) scoreDay = d;
}
static void famShow(uint8_t msg) {
  famMsg = msg; famMsgUntil = millis() + FAMMSG_MS; if (!famMsgUntil) famMsgUntil = 1;
  ecoEvent(HG_EV_FAMILY_MSG_SHOWN, msg);
  hapPost(HG_HP_CUE);                               // soft double (the sequencer: a warning pattern still playing wins)
  screenWake(FAMMSG_MS); uiDraw(true);
}
static bool ifsSave(const char* path, const void* d, size_t n) { return ifsWrite(path, d, n, HG_FID_IFS_ECO); }
static bool ifsLoad(const char* path, void* d, size_t n) {
  if (ifsBad) return false;
  FsGuard g(HG_FID_IFS_ECO);
  File f(InternalFS); bool ok = false;
  if (f.open(path, FILE_O_READ)) { ok = f.read((uint8_t*)d, n) == (int)n; f.close(); }
  return ok;
}
struct FamFile { uint32_t magic; char name[16]; uint32_t crc; };
struct SeedFile { uint32_t magic; uint8_t seed[17], pad[3]; uint32_t crc; };
static bool famNameSave() {
  FamFile ff; memset(&ff, 0, sizeof ff); ff.magic = 0x4D414646u; strncpy(ff.name, famName, HG_FAMNAME_MAX); ff.crc = crc32b(&ff, sizeof ff - 4);
  return ifsSave("/famname.bin", &ff, sizeof ff);
}
static bool seedSave() {
  SeedFile sf; memset(&sf, 0, sizeof sf); sf.magic = 0x44455352u; memcpy(sf.seed, &SEED, 17); sf.crc = crc32b(&sf, sizeof sf - 4);
  return ifsSave("/routine.bin", &sf, sizeof sf);
}
// [SCREEN-FLIP] the screen rotation, a small file next to /famname.bin, same ifsSave/ifsLoad + magic + crc as the eco files
struct ScrFile { uint32_t magic; uint8_t rot, pad[3]; uint32_t crc; };
static bool scrRotSave() {
  ScrFile sf; memset(&sf, 0, sizeof sf); sf.magic = 0x54524353u; sf.rot = scrRot; sf.crc = crc32b(&sf, sizeof sf - 4);
  return ifsSave("/screen.bin", &sf, sizeof sf);
}
static void scrRotLoad() {                          // boot: absent / bad file = 0 (the look of every build before -b7f)
  ScrFile sf;
  if (ifsLoad("/screen.bin", &sf, sizeof sf) && sf.magic == 0x54524353u && sf.crc == crc32b(&sf, sizeof sf - 4) && (sf.rot == 0 || sf.rot == 2)) scrRot = sf.rot;
}
static void ecoLoad() {                             // boot: family name + routine seed (InternalFS, next to /profile.bin)
  FamFile ff; SeedFile sf;
  if (ifsLoad("/famname.bin", &ff, sizeof ff) && ff.magic == 0x4D414646u && ff.crc == crc32b(&ff, sizeof ff - 4)) {
    ff.name[HG_FAMNAME_MAX] = 0; if (hg_utf8_ok((const uint8_t*)ff.name, (uint16_t)strlen(ff.name))) strcpy(famName, ff.name);
  }
  hg_seed_clear(&SEED); haveSeed = false;
  if (ifsLoad("/routine.bin", &sf, sizeof sf) && sf.magic == 0x44455352u && sf.crc == crc32b(&sf, sizeof sf - 4)) { memcpy(&SEED, sf.seed, 17); haveSeed = hg_seed_any(&SEED); }
}
static void seedLog(const char* src, bool saved) {
  evLog("ROUTINE_SEED src=%s saved=%d wake=%02u:%02u bed=%02u:%02u nap=%02u:%02u-%02u:%02u out1=%02u:%02u-%02u:%02u out2=%02u:%02u-%02u:%02u flags=0x%02x (planner only; the frozen routine learner is not seeded)",
        src, saved, SEED.wake_h, SEED.wake_m, SEED.bed_h, SEED.bed_m, SEED.nap_fh, SEED.nap_fm, SEED.nap_th, SEED.nap_tm,
        SEED.o1_fh, SEED.o1_fm, SEED.o1_th, SEED.o1_tm, SEED.o2_fh, SEED.o2_fm, SEED.o2_th, SEED.o2_tm, SEED.flags);
}
// ---------------------------------------------------------------- 0.9.8 Her Day: DAY_PLAN store, VISIT, PLAN_ITEM echo
static bool dpSave() {
  static uint8_t img[HG_DP_FILE]; hg_dp_file_pack(&DP, img);
  bool ok = ifsSave("/dayplan.bin", img, sizeof img); if (ok) dpSaves++;
  return ok;
}
static void dpLoad() {
  static uint8_t img[HG_DP_FILE]; int rc = -9;
  if (ifsLoad("/dayplan.bin", img, sizeof img)) rc = hg_dp_file_unpack(&DP, img, sizeof img); else hg_dp_init(&DP);
  evLog("DAYPLAN load rc=%d day=%ld today=%u tomorrow=%u", rc, (long)DP.today, DP.day[0].n, DP.day[1].n);
}
static void dpLogDay(uint8_t day) {
  const hg_dpday_t* d = &DP.day[day];
  for (uint8_t i = 0; i < d->n; i++) { const hg_dpi_t* t = &d->it[i];
    evLog("DAYPLAN %s %u/%u kind=%u place=%u usual=%02u:%02u sugg=%02u:%02u dir=%u hot=%02u-%02u peak=%u hw=%u", day ? "tomorrow" : "today", i + 1, d->n,
          t->kind, t->place, t->usual_h, t->usual_m, t->sugg_h, t->sugg_m, t->dir, t->hot_from, t->hot_to, t->peak_c, t->hw_day); }
}
static void dayPlanItem(const hg_eco_cmd_t* e) {   // CMD 0x1B: atomic per day; every stored item is echoed as EVENTS type 10
  dpRoll();
  if (!hg_dp_apply(&DP, e->dp_day, e->dp_index, e->dp_n, &e->dpi)) {
    evLog("DAYPLAN %s item %u/%u staged", e->dp_day ? "tomorrow" : "today", e->dp_index, e->dp_n); return; }
  if (DP.today < 0 && localDay() >= 0) DP.today = localDay();
  bool ok = dpSave();
  evLog("DAYPLAN %s replaced: %u item(s) saved=%d", e->dp_day ? "tomorrow" : "today", DP.day[e->dp_day].n, ok);
  dpLogDay(e->dp_day);
  for (uint8_t i = 0; i < DP.day[e->dp_day].n; i++) {   // echo rule: every phone sees the same plan
    uint8_t x[8]; const hg_dpi_t* t = &DP.day[e->dp_day].it[i]; hg_dp_echo(t, e->dp_day, x);
    ecoEventX(HG_EV_PLAN_ITEM, t->kind, x);
  }
}
static void visitRx(const hg_eco_cmd_t* e) {       // CMD 0x1C from her phone: EVENTS type 9 + the N8 leave path
  uint8_t x[8]; hg_visit_echo(e->v_event, e->v_unix, x);
  ecoEventX(HG_EV_VISIT, e->v_place, x);
  visitsRx++;
  uint32_t now = nowUnix();
  bool fresh = timeValid && e->v_unix && (now > e->v_unix ? now - e->v_unix : e->v_unix - now) <= 600u;   // a queued old leave is history
  if (!modelOk) return;
  hg_plan_in_t in; planIn(&in, false); hg_plan_out_t o;
  hg_plan_visit(&PL, &in, e->v_event, e->v_place, (uint8_t)fresh, &o);
  evLog("VISIT %s place=%u unix=%lu fresh=%d n8=%u", e->v_event == HG_VISIT_ARRIVE ? "arrive" : "leave", e->v_place, (unsigned long)e->v_unix, fresh, o.show);
  planOut(&o);
}

// 0x1A ELDER_ACTION: the elder-mode phone app presses the band's button for her. Each action takes exactly the band's
// own path (same marker, guardian latch, toast, haptics, EVENTS frame with arg 2 = phone); anything not applicable is ignored.
static void elderAction(uint8_t a, uint8_t id) {
  bool helpOn = FW.button == 2 || G.help;
  const char* res = "done";
  uiSrc = HG_SRC_PHONE;
  switch (a) {
    case HG_ACT_HELP:                                 // = a 2-s long press, but never a cancel
      if (helpOn) res = "ignored (HELP already active; cancel = action 3)";
      else { queueMarker(HG_M_HELP, 0, "phone"); uiHelp(); }
      break;
    case HG_ACT_HELP_CANCEL:                          // = the band's second long press
      if (helpOn) { helpCancel("phone"); hapPost(HG_HP_YES); uiToast(HG_SCR_OK, 5000, false); }
      else res = "ignored (no HELP active)";
      break;
    case HG_ACT_IM_OK:                                // = a short press answering an open CHECK
      if (checkOpen() || LD.state == HG_LD_ESC) { queueMarker(HG_M_BUTTON, 0, "phone"); uiShort(false); }
      else res = "ignored (no CHECK open)";
      break;
    case HG_ACT_NUDGE_DONE:                           // = a press on that nudge's screen
      if (PL.active && PL.active == id) { uint8_t d = hg_plan_done(&PL, localMod()); ecoEvent(HG_EV_NUDGE_DONE, d); hapPost(HG_HP_YES); uiToast(SCR_X_BRAVO, 3000, false); }
      else res = "ignored (that nudge is not open)";
      break;
    default: res = "ignored"; break;
  }
  uiSrc = HG_SRC_BAND;
  evLog("ELDER_ACTION action=%u nudge=%u %s", a, id, res);
}
static void ecoCommand(const hg_eco_cmd_t* e, uint8_t ch) {
  switch (e->op) {
    case HG_CMD_SYNC_EVENTS: {                      // per link: only the phone that asked is re-sent (USB `frame`: every link)
      bool all = e->boot != (uint16_t)bootCount;
      for (uint16_t h = 0; h < HG_CONN_SLOTS; h++) if (curConn == BLE_CONN_HANDLE_INVALID || curConn == h) { evTxLast[h] = e->since_seq; evTxAll[h] = all; }
      evLog("SYNC_EVENTS since=%u boot=%u band_boot=%u ring=%u last_seq=%u conn=%d%s", e->since_seq, e->boot, (unsigned)(uint16_t)bootCount, EV.n, EV.last_seq,
            curConn == BLE_CONN_HANDLE_INVALID ? -1 : (int)curConn, all ? " (other boot: all)" : "");
      break; }
    case HG_CMD_FAMILY_MSG: famShow(e->msg); break;
    case HG_CMD_FAMILY_NAME: { strcpy(famName, e->name); bool ok = famNameSave();
      evLog("FAMILY_NAME '%s' saved=%d", famName[0] ? famName : "(default)", ok); break; }
    case HG_CMD_ROUTINE_SEED: { SEED = e->seed; haveSeed = hg_seed_any(&SEED); seedLog(ch == CH_USB ? "usb" : "ble", seedSave()); break; }
    case HG_CMD_ELDER_ACTION: elderAction(e->action, e->nudge_id); break;
    case HG_CMD_DAY_PLAN: dayPlanItem(e); break;      // 0.9.8
    case HG_CMD_VISIT: visitRx(e); break;             // 0.9.8
    default: break;
  }
}

// ---------------------------------------------------------------- brown-out (R4 A8)
// POFCON V28 is enabled (the power-fail comparator also blocks NVMC writes below 2.8 V: a half-written twin file is
// impossible). The SoftDevice's POFWARN event is swallowed by the core's SOC task (bluefruit.cpp), so the "flush on
// warning" rule is done by polling VBAT here: below 3.40 V off USB -> flush the logs once; alarms keep a soft tick (R4 A8.2).
static void pofPoll() {
  bool low = (vbat == vbat) && vbat > 2.5f && vbat < 3.40f && !charging();
  if (low && !pofHold) { pofHold = true; evLog("POF VBAT %.3f: flush, soft haptics only", vbat); flushAll(); }
  else if (!low && pofHold && vbat >= 3.50f) { pofHold = false; evLog("POF clear VBAT %.3f", vbat); }
}

// ---------------------------------------------------------------- boot + once-a-minute step
static void guardianBoot() {
  modelOk = hg2_check_crc();
  if (sdOn()) { sd_power_pof_enable(1); sd_power_pof_threshold_set(NRF_POWER_THRESHOLD_V28); }   // 0.9.16: no SoftDevice when BLE is off
  bool prof = profileLoad();
  bool profRam = false;
  if (!prof && profileFromNoinit()) {               // 0.9.16: file gone (SAFE erase, an InternalFS heal) but the RAM copy survived
    profRam = true; bool w = !ifsBad && profileSave();
    evLog("BOOTGUARD profile restored from RAM (age %.0f sex_m %.0f bmi %.1f med %u) file=%s", PROF.age, PROF.sex_m, PROF.bmi, PROF.med_flags,
          w ? "written" : ifsBad ? "not written (InternalFS off this boot)" : "write failed");
  }
  twinLoadAndInit();
  hg_forecast_init(&FC);
  hg_fw_init(&FW);
  infoUpdate();
  evLog("GUARDIAN boot=%lu nn=%s crc=%s(0x%08lx) profile=%s(age %.0f sex_m %.0f bmi %.1f med %u) twin=%s(rc %d, saves %lu, rest_hr %.1f, days %u, calm_n %u)",
        (unsigned long)bootCount, HG2_NN_VERSION, modelOk ? "OK" : "MISMATCH", (unsigned long)HG2_NN_CRC32, prof ? "file" : profRam ? "ram-copy" : "default",
        PROF.age, PROF.sex_m, PROF.bmi, PROF.med_flags, twinLoadRc == 0 ? "loaded" : "defaults", twinLoadRc, (unsigned long)twinSaveCount,
        TW.rest_hr, TW.days_learned, G.a_base_n);
  hg_ev_init(&EV); hg_plan_init(&PL); hg_trend_init(&TREND); ecoLoad();   // 0.9.7
  hg_al_init(&AL); memset(&ALO, 0, sizeof ALO); ALO.room_c = NAN;          // 0.9.9
  hg_ld_init(&LD); hg_ga_lines(G.a_base, G.a_base_n, G.m_drink, G.m_cool, &GL);   // 0.9.17
  dpLoad();                                         // 0.9.8 Her Day plan (rolled to the current day once the clock is known)
  evLog("ECO fw=%s events_ring=%u famname=%s seed=%s", HG_FW_SHORT, HG_EV_RING, famName[0] ? famName : "(default)", haveSeed ? "set" : "none");
  if (haveSeed) seedLog("file", true);
}
static void guardianMinute(uint32_t tick) {
  lastMinuteTick = tick;
  hg_fw_ctx_t c;
  c.minute_of_day = localMod(); c.local_day = localDay(); c.charging = (uint8_t)charging(); c.vbat = vbat;
  c.ble_bucket = bleBucket(); c.forecast72 = FC.complete ? FC.data : NULL; c.has_forecast = FC.complete;
  if (DM.on) hg_demo_ctx(DM.kShown, &c);            // [FW-DEMO] the simulated person's minute: her clock, not charging, 3.9 V, no forecast
  if (!modelOk) {                                  // refuse to run on wrong weights (acceptance 2), but keep logging the inputs
    uint8_t rin[24]; hg_fw_minute_inputs(&FW, &c, tick, rin);
    if ((size_t)minN + 1u <= sizeof minBuf / HG_REC_SIZE) { memcpy(minBuf + minN * HG_REC_SIZE, rin, 24); minN++; } else recsLost++;
    uiToastHold = false;
    return;
  }
  hg_fw_act_t a;
  hg_fw_minute(&FW, &G, &TW, &TACC, &c, tick, &a);
  helpCancelled = false;                            // the new STATUS already shows the cancelled HELP
  if (uiToastHold) {                                // 0.9.6: the guardian has now seen the press: keep the toast 1 s more, then the new state shows
    uiToastHold = false;
    if (!uiToastUntil || (int32_t)(millis() + 1000u - uiToastUntil) > 0) uiToastUntil = millis() + 1000u;
    screenWake(SCREEN_ON_MS);
  }
  const hg_minute_out_t* o = &FW.last_out;
  if (DM.on) {}                                     // [FW-DEMO] replayed minutes are never stored (logs / twin learning stay real)
  else if ((size_t)minN + 2u <= sizeof minBuf / HG_REC_SIZE) { memcpy(minBuf + minN * HG_REC_SIZE, a.rec_in, 24); memcpy(minBuf + (minN + 1) * HG_REC_SIZE, a.rec_g, 24); minN += 2; }
  else recsLost += 2;
  if (a.nightly) evLog("NIGHTLY twin update day=%ld mod=%u rest_hr=%.1f days=%u frozen=%u", (long)c.local_day, c.minute_of_day, TW.rest_hr, TW.days_learned, TACC.last_frozen);
  if (a.save_twin) twinSave("nightly");
  statusPublish(o->status);
  // 0.9.9 alert-quality rules layer: decides the buzz / wake / WARN_SHOWN for DRINK and COOL; everything else passes through
  hg_al_in_t ai = { &FW.last_in, o, TW.rest_hr, c.forecast72, c.minute_of_day, c.local_day, c.vbat, alNowMs() };   // [FW-DEMO] = before when live
  hg_al_minute(&AL, &ai, &ALO);
  if (o->state != lastState || o->screen != lastScreen) {
    evLog("STATE %u screen %u level %u tiers %u core %.2f sd %.2f f20 %.2f why 0x%02x worn %u check %u family %u",
          o->state, o->screen, o->level, o->tiers, o->core.core_now, o->core.sd_now, o->core.f20_eff, o->why, o->worn, o->check_reason, o->family_alert);
    if (o->state != lastState && o->state != HG_ST_OK && o->state != HG_ST_IMOK && o->state != HG_ST_DRINK && o->state != HG_ST_COOL)
      ecoEvent(HG_EV_WARN_SHOWN, o->state);         // 0.9.7 echo (0.9.9: DRINK / COOL are echoed when the rules layer shows them)
    if (ALO.wake && !ALO.present && !ALO.clear) { uiPage = UI_MAIN; screenWake(SCREEN_ON_MS); }   // 0.9.9: quiet changes do not wake
    lastState = o->state; lastScreen = o->screen;
    uiDraw(true);
  }
  if (ALO.present) {                                // 0.9.9: DRINK / COOL persisted on valid input: shown now
    char vb[48];
    evLog("ALERT %s shown%s (persisted; valid=%s f20 %.2f)", ALO.present == HG_ST_DRINK ? "DRINK" : "COOL", ALO.soft ? " soft (one kind of evidence)" : "",
          hg_al_valid_text(AL.valid, vb, sizeof vb), o->core.f20_eff);
    ecoEvent(HG_EV_WARN_SHOWN, ALO.present);
    uiPage = UI_MAIN; screenWake(SCREEN_ON_MS); uiDraw(true);
  }
  if (ALO.clear) {                                  // 0.9.9: a shown episode ended: one «Πάλι όλα καλά» + EVENTS ALL_CLEAR
    uint8_t x[8]; hg_al_clear_x(&ALO, x);
    evLog("ALERT all-clear peak=%u minutes=%u family=%u tick=%u", ALO.clear_peak, ALO.clear_min, ALO.clear_family, ALO.clear_tick);
    ecoEventX(HG_EV_ALL_CLEAR, ALO.clear_peak, x);
    if (o->state == HG_ST_OK) { uiPage = UI_MAIN; uiToast(SCR_X_CLEAR, CLEAR_MS, false); }
  }
  // 0.9.17 closed-loop action ladder (glue only; owner decisions Nov 19 18:22 / 18:23) + the gauge, then ONE haptic after the paint
  const bool danger = o->level >= 3 || (o->check_reason & HG_CR_DANGER);
  const float f20 = (o->core.valid && o->worn) ? o->core.f20_eff : NAN;
  hg_ld_in_t li = { ALO.present, (uint8_t)danger, (uint8_t)(o->level > 0 || AL.pres || ldBench), f20 };
  hg_ld_out_t lo; hg_ld_minute(&LD, &li, &lo);
  hg_ga_lines(G.a_base, G.a_base_n, G.m_drink, G.m_cool, &GL);
  hg_ga_in_t gi = { f20, o->level, (uint8_t)danger, (uint8_t)(o->state == HG_ST_DRINK), (uint8_t)(o->state == HG_ST_COOL), (uint8_t)(f20 == f20) };
  int8_t gp = 0; uint8_t gs = hg_ga_step(&GL, &gi, gaStep, &gp);
  if (gs != gaStep || gp != gaPos) {
    bool wake = gs != gaStep && gs != HG_GA_UNKNOWN && gaStep != HG_GA_UNKNOWN;   // auto-wake on a step change (not on band off / on)
    if (gs != gaStep) evLog("GAUGE %s -> %s f20 %.2f dot %d lines %.2f/%.2f/%.2f%s", hg_ga_colour(gaStep)->name, hg_ga_colour(gs)->name, f20, gp,
                            GL.line_w, GL.line_c, GL.line_d, wake ? " (screen woken)" : "");
    gaStep = gs; gaPos = gp;
    if (wake) { uiPage = UI_MAIN; screenWake(SCREEN_ON_MS); }
    if (screenOn) uiDraw(false);
  }
  ladderApply(&lo, hpFromFrozen(ALO.haptic, o));   // 0.9.9 rules-layer haptic (= the frozen one except DRINK / COOL / held bedtime) + the ladder's
}
static void ladderApply(const hg_ld_out_t* lo, uint8_t frozenHp) {
  for (uint8_t i = 0; i < lo->n; i++) {
    const hg_ld_ev_t* e = &lo->ev[i];
    evLog("LADDER %s arg=%u state=%s", hg_ev_name(e->type), e->arg, hg_ld_state_name(LD.state));
    if (DM.on) { uint8_t x[8]; memcpy(x, e->x, 8); hg_demo_mark_x(e->type, x); ecoEventX(e->type, e->arg, x); continue; }   // [DEMO-NORESP] SIM marker: EVERY replay (plain + noresp)
    ecoEventX(e->type, e->arg, e->x);
  }
  if (lo->toast == HG_LD_TOAST_WORKED) { uiPage = UI_MAIN; uiToast(SCR_X_WORKED, 10000, false); }
  else if (lo->toast == HG_LD_TOAST_STILL) { uiPage = UI_MAIN; uiToast(SCR_X_STILL, 6000, false); }
  else if (lo->wake) { uiPage = UI_MAIN; screenWake(SCREEN_ON_MS); uiDraw(true); }
  uint8_t hp = hpMax(frozenHp, lo->haptic);
  if (hp) hapPost(hp);                              // plan B.2 rule 4: the screen was painted above, the pattern starts now
}
static void guardianSecond(uint32_t tick) {
  // minute boundary: the local clock's minute when the time is known, else 60 s of uptime
  static uint32_t lastIdx = 0xFFFFFFFFu; static uint32_t lastGen = 0;
  int32_t ls = localSecs();
  uint32_t idx = ls >= 0 ? (uint32_t)ls / 60u : tick / 60000u;
  uint8_t sec = (uint8_t)(ls >= 0 ? (uint32_t)ls % 60u : (tick / 1000u) % 60u);
  if (lastIdx == 0xFFFFFFFFu || lastGen != timeSyncGen) { lastIdx = idx; lastGen = timeSyncGen; }   // TIME sync: re-anchor, no extra partial minute (T6b m3)
  if (idx != lastIdx) { lastIdx = idx; if (!DM.on) { guardianMinute(tick); ecoMinute(); } }   // 0.9.7: the planner runs after the guardian ([FW-DEMO] not while replaying)
  // PPG: first 30 s of every minute, continuous while a tier / alert is on (hg_fw.h explains why not 30 s / 2 min)
  bool want = hasPpg && !lowBatMode && (rawActive || hg_fw_ppg_on(&FW, sec));
  if (hasPpg && !lowBatMode && want != ppgEnabled) { ppgEnable(want); if (want) { hg_ppg_init(&hrDet); ppgSetRed(false); } }
}

// ---------------------------------------------------------------- [FW-DEMO] heat-episode replay (console `replay [s]`, `replay stop`)
// SIMULATED INPUT ONLY (sim/velders, see hg_demo_trace.h): the frozen guardian and every layer after it are the real code.
// fw/tools/test_demo.c runs the same input through the same code on the host and prints what the band will show.
#define DM_N_BAK 12
static void* const DM_P[DM_N_BAK] = { &G, &FW, &TW, &TACC, &AL, &ALO, &PL, &TREND, &LD, &GL, &gaStep, &gaPos };
static const size_t DM_S[DM_N_BAK] = { sizeof G, sizeof FW, sizeof TW, sizeof TACC, sizeof AL, sizeof ALO, sizeof PL, sizeof TREND, sizeof LD, sizeof GL, sizeof gaStep, sizeof gaPos };
static const char* demoStName(uint8_t st) {
  static const char* const N[] = { "OK", "DRINK", "COOL", "CHECK", "DANGER", "IMOK", "NOT_WORN", "BATTERY", "HELP" };
  return st < 9 ? N[st] : "?";
}
// [DEMO-NORESP] while a replay runs, ask every link for a 30-60 ms interval (Apple QA1931-valid: min >= 15 ms, min + 15 <= max,
// latency 0, 5 s timeout) so the `#R` lines reach a Mac page on time (BANDWIDTH_LOW = ~1 notification per interval); back to
// the normal 990 ms at the end. The central may refuse: then the `#R` lines thin out on their own (demoLine).
static void connFast(uint16_t h, bool fast) {
  BLEConnection* c = Bluefruit.Connection(h);
  if (!c || !c->connected()) return;
  if (fast) { ble_gap_conn_params_t p = { 24, 48, 0, 500 }; sd_ble_gap_conn_param_update(h, &p); }
  else c->requestConnectionParameter(792, 1, 600);
}
static void connFastAll(bool fast) { if (bleOn) for (uint16_t h = 0; h < HG_NUS_SLOTS; h++) connFast(h, fast); }
static bool nusFast() {                             // every NUS subscriber is on an interval <= 100 ms
  const uint8_t m = bleNusMask(); if (!m) return false;
  for (uint16_t h = 0; h < HG_NUS_SLOTS; h++) if (m & (1u << h)) { BLEConnection* c = Bluefruit.Connection(h); if (!c || c->getConnectionInterval() > 80) return false; }
  return true;
}
static void demoStart(uint32_t stepS, uint8_t ch, bool noresp) {
  if (DM.on) { replyf(ch, "# REPLAY already running (minute %ld of %u): replay stop\n", (long)DM.kShown, hg_demo_n); return; }
  if (!modelOk) { replyf(ch, "# REPLAY refused: model CRC mismatch\n"); return; }
  const uint8_t st = FW.last_out.state;
  if (G.help || G.family_pending || (FW.minutes && (st == HG_ST_CHECK || st == HG_ST_DANGER || st == HG_ST_HELP))) {
    replyf(ch, "# REPLAY refused: the live guardian has an open alert (state %s help %u family %u)\n", demoStName(st), G.help, G.family_pending); return;
  }
  size_t tot = 0; for (int i = 0; i < DM_N_BAK; i++) tot += DM_S[i];
  DM.bak = (uint8_t*)malloc(tot);
  if (!DM.bak) { replyf(ch, "# REPLAY refused: no memory for the live-state copy (%u B)\n", (unsigned)tot); return; }
  for (size_t i = 0, o = 0; i < DM_N_BAK; o += DM_S[i], i++) memcpy(DM.bak + o, DM_P[i], DM_S[i]);   // the LIVE state, put aside
  DM.st.fw = &FW; DM.st.g = &G; DM.st.tw = &TW; DM.st.acc = &TACC; DM.st.al = &AL; DM.st.pl = &PL;
  hg_demo_init(&DM.st);                             // fresh state for the simulated person (host test: the same function)
  memset(&ALO, 0, sizeof ALO); ALO.room_c = NAN; hg_trend_init(&TREND);
  DM.stepMs = stepS * 1000u; DM.k = hg_demo_first(); DM.kShown = DM.k; DM.on = DM_WARM; DM.noresp = noresp ? 1 : 0;
  DM.btnIgn = 0; DM.fam = 0; DM.ev[0] = 0; DM.key[0] = 0;
  hapStop(3); uiToastUntil = 0; uiToastHold = false; helpCancelled = false; lastState = lastScreen = 0xFF;
  hg_ld_init(&LD); gaStep = HG_GA_UNKNOWN; gaPos = 0; GM.valid = false;   // 0.9.17 ladder + gauge start fresh for the simulated person
  evLog("REPLAY start: SIMULATED heat episode (sim/velders person, %u min from %02u:%02u), %lu s per simulated minute; "
        "warm-up %ld quiet minutes; frozen engine, real screen/buzz/alerts/BLE; nothing stored, twin never saved",
        hg_demo_n, hg_demo_start_mod / 60, hg_demo_start_mod % 60, (unsigned long)stepS, (long)-hg_demo_first());
  replyf(ch, "# REPLAY started (%lu s per simulated minute, %lu s in all); `replay stop` = back to live now\n", (unsigned long)stepS,
         (unsigned long)(stepS * hg_demo_n));
  if (noresp) {                                     // [DEMO-NORESP] same input, same engine; only her presses are taken away
    evLog("REPLAY noresp: she does not respond (short presses ignored); the real ladder decides: reminder -> repeat at 10 min -> "
          "LD_NOTE no-response (family SMS) at 20 min; ladder EVENTS marked SIMULATION (byte 18 = 0x%02X)", HG_DEMO_X7_SIM);
    replyf(ch, "# REPLAY noresp: no presses; first reminder ~%lu s, repeat ~%lu s, no-response note ~%lu s after the warm-up\n",
           (unsigned long)(25 * stepS), (unsigned long)(35 * stepS), (unsigned long)(45 * stepS));   /* [DEMO-PICK] b7t trace: minutes 25 / 35 / 45 (host test 8k) */
  }
  outf(CH_BLE, "#R start el=%s nr=%u s=%lu n=%u t0=%02u:%02u\n", HG_DEMO_ELDER, DM.noresp, (unsigned long)stepS, hg_demo_n, hg_demo_start_mod / 60, hg_demo_start_mod % 60);
  connFastAll(true);
  uiPage = UI_MAIN; screenWake(SCREEN_ON_MS); uiDraw(true);
}
static void demoStop(const char* why) {
  if (!DM.on) return;
  for (size_t i = 0, o = 0; i < DM_N_BAK; o += DM_S[i], i++) memcpy(DM_P[i], DM.bak + o, DM_S[i]);   // the LIVE state back
  free(DM.bak); DM.bak = NULL; DM.on = DM_OFF; DM.noresp = 0;
  outf(CH_BLE, "#R stop why=%s\n", why); connFastAll(false);
  hg_fw_discard_minute(&FW);                        // the live minute that was open at the start is stale: start a clean one
  timeSyncGen++;                                    // guardianSecond() re-anchors on the real clock (no extra partial minute)
  hapStop(3); uiToastUntil = 0; uiToastHold = false; lastState = lastScreen = 0xFF; GM.valid = false;
  evLog("REPLAY stop why=%s: live sensors and the live guardian state are back (state %s)", why, demoStName(FW.last_out.state));
  if (FW.minutes) statusPublish(FW.last_out.status);   // the phones see the live state again
  uiPage = UI_MAIN; screenWake(SCREEN_ON_MS); uiDraw(true);
}
// [DEMO-NORESP] compact BLE lines (USB gets the long `# DEMO` line). One minute line, <= ~121 B:
//   #R k=<min 0..n-1> t=<hh:mm sim clock> c=<band core est C> f=<f20: 20-30 min forecast C> sc=<SIMULATED true core C>
//      st=<frozen state> lv=<frozen level 0..3> ld=<ladder state> rm=<reminder on screen: -|water|cool> ga=<gauge colour>
//      dot=<gauge dot -10..+10> fam=<1: a family event (LD_NOTE / LD_ESCALATED / frozen family alert) since the last line>
//      nr=<1 noresp> b=<presses ignored so far>
// then, when any EVENTS went out since the last `#E` (minute events AND those from a press between minutes):
//   #E k=<min> fam=<0|1> ev=<NAME.arg,...>        (cleared only once printed)
// The minute line is sent every minute while every NUS link is fast (<= 100 ms interval), else only when st/lv/ld/rm/ga
// change, events or fam are pending, k % 5 == 0 or the last minute (a 990 ms link carries ~20 B/s).
static void demoLine(int32_t k) {
  const hg_minute_out_t* o = &FW.last_out; const uint8_t r = hg_ld_reminder(&LD);
  const char* rm = r == HG_LD_S_WATER ? "water" : r == HG_LD_S_COOL ? "cool" : "-";
  char key[64]; snprintf(key, sizeof key, "%s|%u|%s|%s|%s", demoStName(o->state), o->level, hg_ld_state_name(LD.state), rm, hg_ga_colour(gaStep)->name);
  const bool fam = DM.fam || o->family_alert;
  if (nusFast() || strcmp(key, DM.key) || fam || DM.ev[0] || k % 5 == 0 || k == hg_demo_n - 1) {
    const hg_demo_row_t* row = hg_demo_row(k);
    outf(CH_BLE, "#R k=%ld t=%02u:%02u c=%.2f f=%.2f sc=%.2f st=%s lv=%u ld=%s rm=%s ga=%s dot=%d fam=%u nr=%u b=%u\n", (long)k,
         hg_demo_mod(k) / 60, hg_demo_mod(k) % 60, o->core.core_now, o->core.f20_eff, row->core / 100.0f, demoStName(o->state), o->level,
         hg_ld_state_name(LD.state), rm, hg_ga_colour(gaStep)->name, (int)gaPos, fam ? 1 : 0, DM.noresp, DM.btnIgn);
    strcpy(DM.key, key);
  }
  if (DM.ev[0]) { outf(CH_BLE, "#E k=%ld fam=%u ev=%s\n", (long)k, fam ? 1 : 0, DM.ev); DM.ev[0] = 0; DM.fam = 0; }
  else if (fam) DM.fam = 0;
}
static void demoMinute(int32_t k) {                 // one visible simulated minute through the band's normal minute path
  DM.kShown = k;                                    // DM.ev / DM.fam keep what happened since the last line (presses too)
  hg_demo_feed_minute(&DM.st, k);                   // 60 simulated seconds into hg_fw_second (= what fwSecond() does live)
  guardianMinute(hg_demo_ms(k));                    // frozen guardian + alert layer + screen + haptics + EVENTS + STATUS
  ecoMinute();                                      // planner (nudges)
  const hg_demo_row_t* r = hg_demo_row(k); const hg_minute_out_t* o = &FW.last_out;
  outf(CH_USB, "# DEMO %02u:%02u t=%lus | SIM input T1 %.2f T2 %.2f air %.1f RH %.0f HR %.0f | SIM true core %.2f | band core %.2f f20 %.2f -> %s level %u\n",
       hg_demo_mod(k) / 60, hg_demo_mod(k) % 60, (unsigned long)(k * (DM.stepMs / 1000u)), r->t1 / 100.0f, r->t2 / 100.0f, r->ta / 100.0f, r->rh / 10.0f,
       r->hr == HG_DEMO_NOHR ? NAN : r->hr / 10.0f, r->core / 100.0f, o->core.core_now, o->core.f20_eff, demoStName(o->state), o->level);
  demoLine(k);
  screenWake(SCREEN_ON_MS);                         // the screen stays on for the whole replay
}
static void demoService(uint32_t now) {
  if (DM.on == DM_WARM) {                           // quiet warm-up in slices of <= 40 ms (the app keeps checking in)
    uint32_t t0 = millis();
    while (DM.k < 0 && millis() - t0 < 40u) { hg_demo_quiet_minute(&DM.st, DM.k); DM.k++; }
    wdtFeed();
    if (DM.k >= 0) {
      DM.on = DM_RUN; DM.nextMs = millis(); DM.kShown = 0; DM.ev[0] = 0; DM.fam = 0;
      outf(CH_BLE, "#R warm done st=%s\n", demoStName(FW.last_out.state));
      evLog("REPLAY warm-up done: state %s; showing %02u:%02u-%02u:%02u", demoStName(FW.last_out.state), hg_demo_start_mod / 60, hg_demo_start_mod % 60,
            hg_demo_mod(hg_demo_n - 1) / 60, hg_demo_mod(hg_demo_n - 1) % 60);
    }
    return;
  }
  if (DM.on == DM_RUN && (int32_t)(now - DM.nextMs) >= 0) {
    demoMinute(DM.k); DM.k++; DM.nextMs += DM.stepMs;
    if (DM.k >= hg_demo_n) { DM.on = DM_END; DM.endMs = now + 120000u; evLog("REPLAY end of the episode: this screen stays 2 min, then live (or `replay stop`)"); outf(CH_BLE, "#R end\n"); }
    return;
  }
  if (DM.on == DM_END && (int32_t)(now - DM.endMs) >= 0) demoStop("end of the episode + 2 min");
}

// ---------------------------------------------------------------- stat + commands
static void guardianStat(uint8_t ch) {
  const hg_minute_out_t* o = &FW.last_out;
  replyf(ch, "# STAT model %s crc=%s(0x%08lx) profile age=%.0f sex_m=%.0f bmi=%.1f med=%u tz_q=%d\n", HG2_NN_VERSION, modelOk ? "OK" : "MISMATCH",
         (unsigned long)HG2_NN_CRC32, PROF.age, PROF.sex_m, PROF.bmi, PROF.med_flags, tzQ);
  replyf(ch, "# STAT guardian minutes=%lu state=%u screen=%u level=%u tiers=%u core=%.2f sd=%.2f f20=%.2f strain=%.1f why=0x%02x worn=%u home=%u routine=%u family=%u\n",
         (unsigned long)FW.minutes, o->state, o->screen, o->level, o->tiers, o->core.core_now, o->core.sd_now, o->core.f20_eff, o->core.strain,
         o->why, o->worn, o->home_out, o->routine_score, o->family_alert);
  replyf(ch, "# STAT twin load=%s(%d) saves_total=%lu saves_this_boot=%lu saves_today=%u nightly_runs=%lu rest_hr=%.1f days=%u calm_n=%u\n",
         twinLoadRc == 0 ? "ok" : "defaults", twinLoadRc, (unsigned long)twinSaveCount, (unsigned long)twinSavesBoot, FW.saves_today,
         (unsigned long)FW.nightly_runs, TW.rest_hr, TW.days_learned, G.a_base_n);
  replyf(ch, "# STAT ble bucket=%d forecast=%s%s safe_hours=%s(0x%06lx) ppg_on=%d pof_hold=%d\n", bleBucket(), FC.complete ? "yes" : "no",
         fcDemo ? "(DEMO)" : "", haveSafe ? "yes" : "no", (unsigned long)safeBitmap, ppgEnabled, pofHold);
  replyf(ch, "# STAT eco day=%ld nudges_today=%u active=%u water_today=%u shown=%lu done=%lu missed=%lu events=%u last_seq=%u seed=%s famname=%s\n",
         (long)PL.day, PL.count, PL.active, PL.n4_count, (unsigned long)PL.shown, (unsigned long)PL.done, (unsigned long)PL.missed, EV.n, EV.last_seq,
         haveSeed ? "set" : "none", famName[0] ? famName : "(default)");
  replyf(ch, "# STAT herday plan_day=%ld today=%u tomorrow=%u saves=%lu visits=%lu n8_today=%u n8_armed=%u home_out=%u%s links=%u/%u\n",
         (long)DP.today, DP.day[0].n, DP.day[1].n, (unsigned long)dpSaves, (unsigned long)visitsRx, PL.n8_count, PL.n8_armed,
         hoSim != 0xFF ? hoSim : (FW.minutes ? FW.last_out.home_out : 0xFF), hoSim != 0xFF ? "(console)" : "", bleOn ? Bluefruit.Periph.connected() : 0, HG_MAX_LINKS);
  if (DM.on) replyf(ch, "# STAT REPLAY running (DEMO, simulated input%s): phase %u minute %ld of %u ladder %s\n", DM.noresp ? ", noresp" : "", DM.on, (long)DM.kShown, hg_demo_n, hg_ld_state_name(LD.state));
  char vb[48];
  replyf(ch, "# STAT alerts valid=%s shower=%u sun=%u episode=%u peak=%u minutes=%lu unknown_min=%lu (score: `score`)\n", hg_al_valid_text(AL.valid, vb, sizeof vb),
         AL.wet, AL.sun, AL.pres, AL.peak, (unsigned long)AL.sc.minutes, (unsigned long)AL.sc.unknown_min);
}
static void scorePrint(uint8_t ch) {                // 0.9.9 alert scorecard (since boot, RAM)
  const hg_al_score_t* s = &AL.sc;
  replyf(ch, "# SCORE sent nudge=%u drink=%u cool=%u cool_soft=%u check=%u family=%u all_clear=%u bedtime=%u\n", s->sent[HG_AL_K_NUDGE], s->sent[HG_AL_K_DRINK],
         s->sent[HG_AL_K_COOL], s->sent[HG_AL_K_COOL_SOFT], s->sent[HG_AL_K_CHECK], s->sent[HG_AL_K_FAMILY], s->sent[HG_AL_K_CLEAR], s->sent[HG_AL_K_BEDTIME]);
  replyf(ch, "# SCORE held not_worn=%u loose=%u skin=%u ppg=%u shower=%u sun=%u persist=%u repeat=%u one_evidence=%u hold_limit=%u\n",
         s->held[HG_AL_R_NOT_WORN], s->held[HG_AL_R_LOOSE], s->held[HG_AL_R_SKIN], s->held[HG_AL_R_PPG], s->held[HG_AL_R_WET], s->held[HG_AL_R_SUN],
         s->held[HG_AL_R_PERSIST], s->held[HG_AL_R_REPEAT], s->held[HG_AL_R_ONE_EV], s->hold_limit);
  replyf(ch, "# SCORE acknowledged=%u missed=%u time_to_ack n=%u avg=%lus max=%us check_one_evidence_audit=%u unknown_min=%lu/%lu\n", s->ack, s->missed, s->tta_n,
         (unsigned long)(s->tta_n ? (s->tta_sum_s + s->tta_n / 2u) / s->tta_n : 0u), s->tta_max_s, s->check_1ev, (unsigned long)s->unknown_min, (unsigned long)s->minutes);
}
static bool parseHm(const char* t, unsigned* h, unsigned* m) {   // "hh:mm" (no sscanf: newlib scanf costs ~2 KB of flash)
  char* e = NULL; unsigned long a = strtoul(t, &e, 10);
  if (e == t || *e != ':') return false;
  const char* t2 = e + 1; unsigned long b = strtoul(t2, &e, 10);
  if (e == t2 || *e || a > 23 || b > 59) return false;
  *h = (unsigned)a; *m = (unsigned)b; return true;
}
static bool guardianCommand(int argc, char** argv, uint8_t ch) {
  if (eqi(argv[0], "gauge")) {                      // 0.9.17 bench: display override only (the forecast mapping is untouched)
    if (argc >= 2 && argv[1][0] >= '0' && argv[1][0] <= '4' && !argv[1][1]) gaForce = (uint8_t)(argv[1][0] - '0'); else gaForce = 0xFE;
    replyf(ch, "# GAUGE %s\n", gaForce < HG_GA_STEPS ? hg_ga_colour(gaForce)->name : "auto (the forecast)");
    uiPage = UI_MAIN; screenWake(SCREEN_ON_MS); uiDraw(true); return true;
  }
  if (eqi(argv[0], "raise")) {                      // 0.9.17 wrist raise: which axis faces the sky when she looks
    if (argc >= 2 && (eqi(argv[1], "on") || eqi(argv[1], "off"))) raiseOn = eqi(argv[1], "on");
    if (argc >= 4 && eqi(argv[1], "axis")) { char a = argv[2][0] | 0x20; hg_rz_init(&RZ, a == 'x' ? 0 : a == 'y' ? 1 : 2, argv[3][0] == '-' ? -1 : 1); }
    float x = 0, y = 0, z = 0; bool ok = hasImu && imuRaw(&x, &y, &z);
    replyf(ch, "# RAISE %s axis=%c%c wakes=%lu now x=%.2f y=%.2f z=%.2f g%s (hold the band as if reading it: the axis near +1.00 or -1.00 is the face)\n",
           raiseOn ? "on" : "off", RZ.sign > 0 ? '+' : '-', "xyz"[RZ.axis], (unsigned long)raiseWakes, x, y, z, ok ? "" : " (IMU not read)");
    return true;
  }
  if (eqi(argv[0], "ladder") && argc >= 2) {        // 0.9.17 bench (USB only): drive the ladder without heat; its EVENTS are real
    if (ch != CH_USB) { replyf(ch, "# LADDER: USB only\n"); return true; }
    hg_ld_out_t lo; memset(&lo, 0, sizeof lo);
    float f = FW.minutes && FW.last_out.core.valid ? FW.last_out.core.f20_eff : NAN;
    if (eqi(argv[1], "off")) { hg_ld_init(&LD); ldBench = false; replyf(ch, "# LADDER reset\n"); uiDraw(true); return true; }
    hg_ld_in_t li = { (uint8_t)(eqi(argv[1], "water") ? HG_ST_DRINK : eqi(argv[1], "cool") ? HG_ST_COOL : 0), (uint8_t)eqi(argv[1], "danger"), 1, f };
    if (!li.present && !li.danger) { replyf(ch, "# LADDER water|cool|danger|off\n"); return true; }
    if (LD.state != HG_LD_IDLE) hg_ld_init(&LD);
    ldBench = true;
    hg_ld_minute(&LD, &li, &lo); ladderApply(&lo, 0);
    replyf(ch, "# LADDER %s -> %s (the next minutes run on the real forecast: flat for 20 min after a press = worked)\n", argv[1], hg_ld_state_name(LD.state));
    return true;
  }
  if (eqi(argv[0], "state")) {
    const hg_minute_out_t* o = &FW.last_out; char h[44]; hg_hex(o->status, 20, h);
    replyf(ch, "# STATE %u screen %u core %.2f status %s\n", o->state, o->screen, o->core.core_now, h); return true;
  }
  if (eqi(argv[0], "ring")) { debugLeft = argc >= 2 ? (uint16_t)atoi(argv[1]) : 60; if (debugLeft > HG_FW_RING_MIN) debugLeft = HG_FW_RING_MIN; debugCh = ch; return true; }
  if (eqi(argv[0], "log") && argc >= 2) { liveUsb = logBle = eqi(argv[1], "on"); replyf(ch, "# LOG 1 Hz debug stream %s\n", liveUsb ? "on" : "off"); return true; }
  if (eqi(argv[0], "frame") && argc >= 2) {      // a phone frame typed as hex (testing without a phone)
    uint8_t b[20]; uint8_t n = 0; const char* h = argv[1];
    while (n < 20 && isxdigit((unsigned char)h[0]) && isxdigit((unsigned char)h[1])) { char t[3] = {h[0], h[1], 0}; b[n++] = (uint8_t)strtoul(t, NULL, 16); h += 2; }
    handleFrame(b, n, ch); return true;
  }
  // ---- 0.9.7 bench commands (no phone needed)
  if (eqi(argv[0], "nudge") && argc >= 2) {         // force-show a nudge (no caps; a warning still wins)
    int id = atoi(argv[1]);
    hg_plan_in_t in; planIn(&in, false);
    if (id < 1 || id >= HG_N_COUNT || id == HG_N_SHUTTERS) { replyf(ch, "# NUDGE needs 1 brief 2 last-cool 4 water 5 air 6 a/c 7 evening 8 leave-hot (3 shutters removed in 0.9.8)\n"); return true; }
    if (in.warning) { replyf(ch, "# NUDGE blocked: a guardian warning / HELP is on (warnings always win)\n"); return true; }
    if (!hg_plan_force(&PL, (uint8_t)id, &in)) { replyf(ch, "# NUDGE %d has no text: nudge 7 needs a tomorrow plan with a kind 1 or 3 item (dayplan 1 ...)\n", id); return true; }
    evLog("NUDGE forced id=%d src=console", id); nudgeShow((uint8_t)id, true);
    replyf(ch, "# NUDGE %d shown (press = DONE, 10 min = MISSED)\n", id); return true;
  }
  if (eqi(argv[0], "famsg") && argc >= 2) {
    int m = atoi(argv[1]); if (m < 1 || m > 3) { replyf(ch, "# FAMSG needs 1 calls you, 2 is coming, 3 saw the message\n"); return true; }
    famShow((uint8_t)m); replyf(ch, "# FAMSG %d shown 60 s\n", m); return true;
  }
  if (eqi(argv[0], "famname")) {
    if (argc < 2) { replyf(ch, "# FAMNAME now '%s'; set: famname <name> (UTF-8, max 14 bytes), famname - = default\n", famName[0] ? famName : HG_TXT_FAMDEF); return true; }
    char nm[HG_FAMNAME_MAX + 2] = "";
    if (strcmp(argv[1], "-") != 0)
      for (int i = 1; i < argc; i++) {
        if (strlen(nm) + (i > 1) + strlen(argv[i]) > HG_FAMNAME_MAX) { replyf(ch, "# FAMNAME rejected: longer than 14 bytes\n"); return true; }
        if (i > 1) strcat(nm, " ");
        strcat(nm, argv[i]);
      }
    if (!hg_utf8_ok((const uint8_t*)nm, (uint16_t)strlen(nm))) { replyf(ch, "# FAMNAME rejected: not valid UTF-8\n"); return true; }
    strcpy(famName, nm); bool ok = famNameSave();
    evLog("FAMILY_NAME '%s' saved=%d src=console", famName[0] ? famName : "(default)", ok); replyf(ch, "# FAMNAME saved=%d\n", ok); return true;
  }
  if (eqi(argv[0], "routine")) {
    if (argc >= 2 && eqi(argv[1], "off")) { hg_seed_clear(&SEED); haveSeed = false; seedLog("console", seedSave()); replyf(ch, "# ROUTINE cleared\n"); return true; }
    unsigned wh, wm, bh, bm;
    if (argc < 3 || !parseHm(argv[1], &wh, &wm) || !parseHm(argv[2], &bh, &bm)) {
      replyf(ch, "# ROUTINE set: routine <wake hh:mm> <bed hh:mm>  (routine off = clear; nap/outings/A-C via CMD 0x19)\n"); return true; }
    if (!haveSeed) hg_seed_clear(&SEED);
    SEED.wake_h = (uint8_t)wh; SEED.wake_m = (uint8_t)wm; SEED.bed_h = (uint8_t)bh; SEED.bed_m = (uint8_t)bm; haveSeed = true;
    bool ok = seedSave(); seedLog("console", ok); replyf(ch, "# ROUTINE saved=%d\n", ok); return true;
  }
  if (eqi(argv[0], "score")) { scorePrint(ch); scoreEmit("console"); return true; }   // 0.9.9: counters + 3 EVENTS SCORE frames
  if (eqi(argv[0], "events")) {
    replyf(ch, "# EVENTS n=%u last_seq=%u boot=%u\n", EV.n, EV.last_seq, (unsigned)(uint16_t)bootCount);
    for (uint8_t i = 0; i < EV.n; i++) {
      const hg_ev_t* e = hg_ev_at(&EV, i); uint8_t f[20]; char h[44]; hg_ev_pack(e, (uint16_t)bootCount, f); hg_hex(f, 20, h);
      replyf(ch, "# EV seq=%u type=%u %s arg=%u unix=%lu frame=%s\n", e->seq, e->type, hg_ev_name(e->type), e->arg, (unsigned long)e->unix_s, h);
    }
    return true;
  }
  // ---- 0.9.8 Her Day bench commands: each builds the real phone frame and feeds it through handleFrame (same parser path)
  if (eqi(argv[0], "dayplan")) {
    if (argc == 1) {
      replyf(ch, "# DAYPLAN plan_day=%ld (band day %ld) today=%u tomorrow=%u\n", (long)DP.today, (long)localDay(), DP.day[0].n, DP.day[1].n);
      for (uint8_t d = 0; d < 2; d++) for (uint8_t i = 0; i < DP.day[d].n; i++) { const hg_dpi_t* t = &DP.day[d].it[i];
        replyf(ch, "# DP %s %u/%u kind=%u place=%u usual=%u:%u sugg=%u:%u dir=%u hot=%u-%u peak=%u hw=%u\n", d ? "tomorrow" : "today", i + 1, DP.day[d].n,
               t->kind, t->place, t->usual_h, t->usual_m, t->sugg_h, t->sugg_m, t->dir, t->hot_from, t->hot_to, t->peak_c, t->hw_day); }
      return true;
    }
    int day = atoi(argv[1]);
    if (argc == 3 && eqi(argv[2], "clear") && (day == 0 || day == 1)) { uint8_t f[20]; hg_eco_pack_dayplan((uint8_t)day, 0, 0, NULL, f); handleFrame(f, 20, ch); return true; }
    if (argc < 13 || (day != 0 && day != 1)) {
      replyf(ch, "# DAYPLAN add one item: dayplan <day 0|1> <kind 1|2|3> <place 0-7> <uh> <um> <sh> <sm> <dir 1|2> <hf> <ht> <peak> <hw>  (- = 255 = n/a)\n");
      replyf(ch, "#   dayplan <day> clear | dayplan = show. The day's stored items + this one are re-sent as one atomic set.\n"); return true; }
    uint8_t v[11];
    for (int i = 0; i < 11; i++) { const char* a = argv[2 + i]; long x = strcmp(a, "-") == 0 ? 255 : strtol(a, NULL, 10); v[i] = (uint8_t)(x < 0 ? 0 : x > 255 ? 255 : x); }
    hg_dpi_t it; it.kind = v[0]; it.place = v[1]; it.usual_h = v[2]; it.usual_m = v[3]; it.sugg_h = v[4]; it.sugg_m = v[5]; it.dir = v[6];
    it.hot_from = v[7]; it.hot_to = v[8]; it.peak_c = v[9]; it.hw_day = v[10];
    dpRoll();
    hg_dpday_t cur = DP.day[day];
    if (cur.n >= HG_DP_MAX) { replyf(ch, "# DAYPLAN day %d already has 6 items (dayplan %d clear)\n", day, day); return true; }
    uint8_t n = (uint8_t)(cur.n + 1), f[20];
    for (uint8_t i = 0; i < n; i++) {               // as the phone sends a set: index 1..n, the new item last
      hg_eco_pack_dayplan((uint8_t)day, (uint8_t)(i + 1), n, i < cur.n ? &cur.it[i] : &it, f);
      handleFrame(f, 20, ch);
    }
    return true;
  }
  if (eqi(argv[0], "visit")) {
    static const char* const PN[HG_PL_N] = { "home", "market", "church", "walk", "pharmacy", "cafe", "doctor", "other" };
    int ev = argc >= 2 ? (eqi(argv[1], "arrive") ? 1 : eqi(argv[1], "leave") ? 2 : 0) : 0, pl = -1;
    if (argc >= 3) { for (int i = 0; i < HG_PL_N; i++) if (eqi(argv[2], PN[i])) pl = i;
                     if (pl < 0 && isdigit((unsigned char)argv[2][0])) pl = atoi(argv[2]); }
    if (!ev || pl < 0 || pl >= HG_PL_N) { replyf(ch, "# VISIT: visit <arrive|leave> <place 0-7 | home market church walk pharmacy cafe doctor other> (time = band clock)\n"); return true; }
    uint8_t f[20]; hg_eco_pack_visit((uint8_t)ev, (uint8_t)pl, nowUnix(), f); handleFrame(f, 20, ch); return true;
  }
  if (eqi(argv[0], "homeout")) {
    if (argc >= 2 && (eqi(argv[1], "home") || eqi(argv[1], "out") || eqi(argv[1], "off"))) {
      hoSim = eqi(argv[1], "home") ? HG_HO_HOME : eqi(argv[1], "out") ? HG_HO_TRANSIT : 0xFF;
      hg_plan_in_t in; planIn(&in, false); hg_plan_out_t o; o.show = o.missed = 0;
      if (modelOk && hoSim != 0xFF) hg_plan_homeout(&PL, &in, &o);
      evLog("HOMEOUT console=%s n8=%u", argv[1], o.show);
      replyf(ch, "# HOMEOUT %s (planner only; the guardian's own home/out is untouched)%s\n", argv[1], o.show ? ": N8 shown" : "");
      planOut(&o); return true;
    }
    replyf(ch, "# HOMEOUT now %u%s; homeout home | out (= HOME -> TRANSIT, the N8 trigger) | off (back to the guardian's state)\n",
           hoSim != 0xFF ? hoSim : (FW.minutes ? FW.last_out.home_out : 0xFF), hoSim != 0xFF ? " (console)" : ""); return true;
  }
  if (eqi(argv[0], "fcdemo")) {                     // a constructed heat day: main face + planner demo without the phone
    static const int8_t T[24] = { 27, 27, 26, 26, 26, 26, 26, 27, 27, 27, 28, 29, 31, 32, 33, 33, 32, 31, 30, 29, 28, 28, 27, 27 };
    for (int h = 0; h < 24; h++) { FC.data[3 * h] = (uint8_t)T[h]; FC.data[3 * h + 1] = 45; FC.data[3 * h + 2] = (uint8_t)(1 | 2 | ((h >= 6 && h < 10) ? 4 : 0)); }
    FC.have_mask = 0x0F; FC.complete = 1; fcDemo = true;
    haveSafe = true; safeBitmap = 0x0003C0ul; safePlanId = 0; strcpy(safeTag, "DEMO");
    evLog("FORECAST DEMO loaded by console (constructed heat day: safe 06-10, T_in max 33 C, heat-day + night-heat): NOT a real forecast");
    replyf(ch, "# FCDEMO loaded (DEMO data, also seen by the guardian as a forecast; reboot or a real FORECAST replaces it)\n");
    if (screenOn) uiDraw(true);
    return true;
  }
  if (eqi(argv[0], "replay")) {                     // [FW-DEMO] SIMULATED heat episode through the real engine
    if (argc >= 2 && eqi(argv[1], "stop")) { if (DM.on) demoStop("command"); else replyf(ch, "# REPLAY not running\n"); return true; }
    const bool nr = argc >= 2 && eqi(argv[1], "noresp");   // [DEMO-NORESP] `replay noresp [s]`
    const int ai = nr ? 2 : 1;
    long sp = argc > ai ? atol(argv[ai]) : 2;
    if (sp < 1 || sp > 60) { replyf(ch, "# REPLAY: replay [noresp] [seconds per simulated minute 1..60, default 2] | replay stop\n"); return true; }
    demoStart((uint32_t)sp, ch, nr); return true;
  }
  if (eqi(argv[0], "profile")) {
    if (DM.on && argc >= 5) { replyf(ch, "# PROFILE: a replay is running (replay stop first)\n"); return true; }
    if (argc < 5) { replyf(ch, "# PROFILE now age=%.0f sex_m=%.0f bmi=%.1f med=%u; set: profile <age> <sex_m 0/1> <bmi> <med bits>\n", PROF.age, PROF.sex_m, PROF.bmi, PROF.med_flags); return true; }
    float age = atof(argv[1]), sx = atof(argv[2]), bmi = atof(argv[3]); int med = atoi(argv[4]);
    if (!(age >= 1 && age <= 120 && (sx == 0 || sx == 1) && bmi >= 10 && bmi <= 60 && med >= 0 && med <= 15)) { replyf(ch, "# PROFILE rejected\n"); return true; }
    PROF.age = age; PROF.sex_m = sx; PROF.bmi = bmi; PROF.med_flags = (uint8_t)med;
    hg_fw_apply_profile(&G, &PROF);                 // profile constants only: alarms, CHECK, HELP, tiers and learning untouched
    bool ok = profileSave();
    evLog("PROFILE age=%.0f sex_m=%.0f bmi=%.1f med=%u saved=%d (applied without restart; state %u help %u family %u kept)", age, sx, bmi, med, ok, FW.last_out.state, G.help, G.family_pending);
    replyf(ch, "# PROFILE saved=%d\n", ok); return true;
  }
  return false;
}

// =====================================================================
// 0.9.16 BOOT GUARD (plan FW-WORLDCLASS D.1 / D.2 / D.4, stage 0.9.16; the decisions are in hg_bootguard.c, host-tested)
//  - journal STARTED written before anything that can fail; HEALTHY at 60 s, STABLE at 10 min; the RAM copy in .hg_noinit
//  - ladder: normal / careful (no QSPI log) / safe (+ InternalFS erased raw, the stage that died skipped) / minimal (+ no InternalFS
//    file of ours) / rest (service screen, Warning pattern, System OFF; a press = SAFE). Screen, button, motor, sensors and the
//    guardian run in every rung that runs at all: the band always alerts while it is on.
//  - ledger: every reset named (stat), read back from the journal
// =====================================================================
#define HG_APP_STACK_WORDS 3072u                    /* 12 KB: the app task (the whole setup + loop body, plan A-11) */
#define IFS_ADDR  0xED000u                          /* the core's InternalFileSystem.cpp LFS_FLASH_ADDR (nRF52840) ... */
#define IFS_PAGES 7u                                /* ... and LFS_FLASH_TOTAL_SIZE = 7 pages */
static int bgClass = HG_RST_POWERON;                // this boot in the ledger (hg_bg_classify: 0.9.15 class + our own reset codes)
static hg_bg_scan_t BGS; static hg_bg_prev_t BGM; static hg_bg_decision_t BGD; static hg_bg_plan_t BGP;
static bool bgNiValid = false, bgStartedOk = false, bgHealthy = false, bgStable = false, gfxUp = false;
static uint8_t bgRcode = 0, bgRarg = 0, bgFloop = 0, bgDead = HG_BG_STG_NONE, bgPrevCp = HG_BG_CP_UNKNOWN, bgPrevUpc = HG_BG_UP_UNKNOWN;
static const char* const BG_TASK[5] = { "-", "app", "writer", "timer", "ui" };
static const char* const BG_STAGE[4] = { "none", "storage", "ble", "internalfs" };
const uint8_t PAT_PWRUP[8] = { 19, WAIT10MS(8), 18, WAIT10MS(8), 17, 0 };   // plan C.4 power-up: three clicks, rising (60 / 80 / 100 %)
static const char* cpName(uint8_t cp) { return cp < CP_COUNT ? CP_NAME[cp] : "?"; }
static void upText(char* o, size_t n, uint8_t upc) {
  uint32_t s = hg_bg_up_decode_s(upc);
  if (s == 0xFFFFFFFFu) snprintf(o, n, "?"); else if (s < 60u) snprintf(o, n, "%lus", (unsigned long)s);
  else if (s < 3600u) snprintf(o, n, "%lumin", (unsigned long)(s / 60u)); else snprintf(o, n, ">=%luh", (unsigned long)(s / 3600u));
}
// the ladder decision of this boot + the STARTED entry, before anything that can fail (SoftDevice off: NVMC, synchronous)
static void bgBoot() {
  CPS(CP_S_BG);
  bgClass = hg_bg_classify(rstClass, bgNiValid ? bgRcode : 0);
  bgPrevCp = (niValid && niLastCp < HG_BG_CP_UNKNOWN) ? (uint8_t)niLastCp : (uint8_t)HG_BG_CP_UNKNOWN;
  bgPrevUpc = niValid ? hg_bg_up_encode(niLastMs) : (uint8_t)HG_BG_UP_UNKNOWN;
  hg_bg_boot((const uint32_t*)BG_PAGE, bgNiValid ? &NI.bg : NULL, bgClass, &BGS, &BGM, &BGD);
  bgDead = (hg_bg_is_fault(bgClass) && bgPrevCp != HG_BG_CP_UNKNOWN) ? bgStageOf(bgPrevCp) : (uint8_t)HG_BG_STG_NONE;
  hg_bg_plan(BGD.mode, bgDead, &BGP);
  bgStartedOk = bgAppend(hg_bg_started(bgClass, &BGD, bgPrevCp, bgPrevUpc));
  hg_bg_cur(&NI.bg, bgClass, &BGD); NI.magic3 = HG_NI_MAGIC3; NI.rcode = 0; NI.rarg = 0;   // the RAM copy of this boot
}
static void bgSplash() {                            // plan C.7 "Heat Guardian"; the version (+ the rung when it is not NORMAL) underneath
  gfx->fillScreen(C_BLACK);
  textBlock("Heat Guardian", 96, 176);
  char l[40]; snprintf(l, sizeof l, "      %s%s%s", HG_FW_SHORT, BGD.mode ? "  " : "", BGD.mode ? hg_bg_mode_name(BGD.mode) : "");
  gfx->setFont(u8g2_font_10x20_t_greek); gfx->setUTF8Print(true); gfx->setTextSize(1);
  drawLine(9, BGD.mode ? C_ORANGE : C_GREY, l);
  screenWake(SCREEN_ON_MS);
}
// plan D.5 steps 9-12 (0.9.16: used by the rest rung and the USB pwroff test only): every step bounded, continues if one fails
static void hgSystemOff(const char* why) {
  CP(CP_S_OFF);
  if (uiTask) {                                     // 0.9.17: hgui stops first (taken between two I2C transfers: never holding the bus)
    bool took = i2cMtx && xSemaphoreTake(i2cMtx, pdMS_TO_TICKS(300)) == pdTRUE;
    uiBeatMs = 0; vTaskSuspend(uiTask); uiTaskOn = false;
    if (took) xSemaphoreGive(i2cMtx);
  }
  outf(CH_USB, "# OFF %s: System OFF now. Press the button to turn the band on.\n", why);
  if (hasPpg) ppgEnable(false);                     // the PPG LEDs are the big draw
  if (hasDrv) { i2cWriteReg8(0x5A, 0x0C, 0); i2cWriteReg8(0x5A, 0x01, 0x40); }   // DRV2605L: stop, STANDBY
  screenOn = false; applyBacklight();               // backlight GPIO LOW, PWM released
  if (gfxUp) gfx->displayOff();                     // SLPIN
  if (fsState == FS_OK && !wrBusy && !dumpActive) { // plan A-05: the flash chip's deep power-down only before System OFF
    SemaphoreHandle_t m = fsMtxEarly();
    if (!m || xSemaphoreTakeRecursive(m, 500) == pdTRUE) { if (flashWake()) qspiTr.runCommand(0xB9); qspiOff(); if (m) xSemaphoreGiveRecursive(m); }
  }
  NRF_TWIM0->ENABLE = 0;                            // TWIM off; P0.14 stays LOW (the VBAT divider rule)
  uint32_t t0 = millis(), hi = millis();            // the button released for 300 ms (<= 10 s), or the press would wake it at once
  while (millis() - t0 < 10000u) { wdtFeed(); if (digitalRead(PIN_BTN) == LOW) hi = millis(); else if (millis() - hi >= 300u) break; delay(10); }
  uint32_t pin = g_ADigitalPinMap[PIN_BTN];         // D7: input, pull-up, SENSE low = the wake source
  for (uint32_t q = 0; q < 48u; q++)                // [OFF-CONFIRM] the button is the ONLY GPIO wake source: SENSE off on every other pin
    if (q != pin) { NRF_GPIO_Type* pp = q >= 32u ? NRF_P1 : NRF_P0; pp->PIN_CNF[q & 31u] &= ~GPIO_PIN_CNF_SENSE_Msk; }
  NRF_P0->LATCH = 0xFFFFFFFFu; NRF_P1->LATCH = 0xFFFFFFFFu;
  NRF_GPIO_Type* port = pin >= 32u ? NRF_P1 : NRF_P0;
  port->PIN_CNF[pin & 31u] = (GPIO_PIN_CNF_DIR_Input << GPIO_PIN_CNF_DIR_Pos) | (GPIO_PIN_CNF_INPUT_Connect << GPIO_PIN_CNF_INPUT_Pos) |
                             (GPIO_PIN_CNF_PULL_Pullup << GPIO_PIN_CNF_PULL_Pos) | (GPIO_PIN_CNF_SENSE_Low << GPIO_PIN_CNF_SENSE_Pos);
  port->LATCH = 1u << (pin & 31u);
  delay(20);                                        // the USB line above leaves
  wdtHwFeed();                                      // System OFF stops the watchdog; a wake resets it (Nordic reset table)
  if (sdOn()) sd_power_system_off();                // POWER is restricted while the SoftDevice runs; returns only on an error
  else { NRF_POWER->SYSTEMOFF = 1; __DSB(); }
  for (volatile uint32_t i = 0; i < 200000u; i++) {}   // (a debugger emulates System OFF)
  NVIC_SystemReset();
}
// [FLASH-EASY] the core's enterUf2Dfu() (cores/nRF5/wiring.c: GPREGRET = 0x57 UF2 magic, NVIC_SystemReset) with the two things
// this firmware adds to every reset it asks for: the REBOOT reset code (a commanded reset: never a ladder rung, as bgSoftReset), and
// the SoftDevice API for GPREGRET while BLE runs (POWER is restricted, as gpregret2Write). The watchdog keeps running through a soft
// reset: the supervisor fed it <= 250 ms ago (the wait loops check in), so >= 7.7 s remain for the bootloader's start-up, then the
// Adafruit bootloader feeds it in its DFU loop (bootloader.c wait_for_events, 0.4.0-0.6.x). (No extra wdtHwFeed: D.4, one feeder.)
#define HG_DFU_MAGIC_UF2 0x57u                     // = DFU_MAGIC_UF2_RESET (private to wiring.c)
static void hgEnterUf2() {
  NI.magic3 = HG_NI_MAGIC3; NI.rcode = HG_BG_RC_REBOOT; NI.rarg = 0;
  if (sdOn()) { sd_power_gpregret_clr(0, 0xFFFFFFFFu); sd_power_gpregret_set(0, HG_DFU_MAGIC_UF2); NVIC_SystemReset(); }
  enterUf2Dfu();
  for (;;) {}
}
// 0.9.17 the wearer's power-off (double press, «Απενεργοποίηση;», one press). Plan D.5 order, every step bounded: EVENTS POWER_OFF
// (BLE given 1.5 s to send it), the message + falling clicks, the log flushed (<= 5 s), CLEAN in the journal (the wake is not a fault), off.
static void pwrOffNow(uint8_t src) {
  pwrPrompt = false;
  evLog("POWER OFF by %s", src == 1 ? "the wearer (double press + confirm)" : "USB");
  ecoEvent(HG_EV_POWER_OFF, src);
  screenWake(5000); gfx->fillScreen(C_BLACK); textBlock(HG_TXT_PWR_OFF, 90, 190);
  hapPost(HG_HP_OFF);
  uint32_t t0 = millis();
  while (millis() - t0 < 1500u) { wdtFeed(); if (bleOn) hgBleService(); delay(20); }   // pattern plays (hgui), the EVENTS frame goes out
  flushAll(); while (wrBusy && millis() - t0 < 6500u) { wdtFeed(); delay(10); }      // the log first (<= 5 s)
  bgAppend(hg_bg_mark(HG_BG_T_CLEAN));              // the wake that follows is not a fault
  hgSystemOff("power-off by the wearer");
}
// the rest rung: REST in the journal FIRST (the next boot starts at SAFE even if this one dies here), service screen, one Warning pattern, off
static void bgRest() {
  bgAppend(hg_bg_mark(HG_BG_T_REST));
  outf(CH_USB, "# BOOTGUARD REST: %u resets in a row before 60 s up -> service screen, Warning pattern, System OFF. A button press starts SAFE mode.\n",
       (unsigned)BGD.level);
  if (gfxUp) { gfx->fillScreen(C_BLACK); drawWarning(120, 82, 120, C_ORANGE); textBlock(HG_BG_TXT_SERVICE, 150, 250); screenWake(SCREEN_ON_MS); }
  vibrate(HAP_COOL);                                // "Warning" (C.4): three long pulses
  uint32_t t0 = millis();
  while (millis() - t0 < 4000u) { wdtFeed(); serviceMotor(); delay(20); }
  hgSystemOff("boot guard rest");
}
// safe and minimal: InternalFS erased raw (NVMC, SoftDevice off) before Bluefruit mounts it, so no littlefs code can assert on it
static void bgIfsErase() {
  CPS(CP_S_IFSERASE);
  bool ok = true;
  for (uint32_t i = 0; i < IFS_PAGES; i++) { ok = nvPageErase(IFS_ADDR + i * 4096u) && ok; wdtFeed(); }
  evLog("BOOTGUARD %s: InternalFS erased raw before BLE: %s (the profile comes back from the RAM copy if there is one; twin, family name, "
        "routine, day plan start fresh)", hg_bg_mode_name(BGD.mode), ok ? "ok" : "FAILED");
}
// bench "fault loop N": the next N boots crash here (a real hard fault), after every rung's start-up
static void bgInjectIfArmed() {
  if (!bgFloop) return;
  NI.floop = (uint8_t)(bgFloop - 1u);
  CP(CP_F_INJECT);
  outf(CH_USB, "# FAULT loop: hard fault now (%u more boot(s) will crash after this one)\n", (unsigned)NI.floop); delay(30);
  NI.magic3 = HG_NI_MAGIC3; NI.rcode = HG_BG_RC_INJECT;
  __builtin_trap();                                 // HardFault -> the core's handler soft-resets
}
static void bgService(uint32_t now) {               // app loop: HEALTHY at 60 s, STABLE at 10 min (journal + RAM copy)
  if (!bgHealthy && now >= 60000u) {
    bgHealthy = true; NI.bg.healthy = 1;
    bool ok = bgAppend(hg_bg_mark(HG_BG_T_HEALTHY));
    evLog("BOOTGUARD healthy t_ms=%lu mode=%s journal=%s: the ladder starts again at 0", (unsigned long)now, hg_bg_mode_name(BGD.mode), ok ? "ok" : "FAILED");
  }
  if (!bgStable && now >= 600000u) {
    bgStable = true; NI.bg.stable = 1;
    bool ok = bgAppend(hg_bg_mark(HG_BG_T_STABLE));
    evLog("BOOTGUARD stable t_ms=%lu journal=%s: slow-fault count cleared", (unsigned long)now, ok ? "ok" : "FAILED");
  }
}
static void printBgStat(uint8_t ch) {
  static hg_bg_scan_t s;
  hg_bg_scan((const uint32_t*)BG_PAGE, HG_BG_PAGE_WORDS, &s);   // 4 KB of memory-mapped flash
  replyf(ch, "# STAT bootguard: class=%s level=%u mode=%s slow=%u healthy=%d stable=%d dead_stage=%s storage=%s ble=%s ifs=%s journal=%d/%d words corrupt=%d writes=%lu fails=%lu\n",
         hg_bg_class_name(bgClass), BGD.level, hg_bg_mode_name(BGD.mode), BGD.slow, (int)bgHealthy, (int)bgStable, BG_STAGE[bgDead & 3],
         BGP.storage_off ? "off" : "on", bleOn ? "on" : "off", BGP.ifs_off ? "off" : BGP.ifs_erase ? "erased" : "on",
         s.used, HG_BG_PAGE_WORDS, s.corrupt, (unsigned long)bgWrites, (unsigned long)bgWriteFails);
  replyf(ch, "# STAT supervisor: app_silent_max=%lu ms (reset at %u) writer_job_max=%lu ms writer_stuck=%d tick_gap_max=%lu ms ticks=%lu\n",
         (unsigned long)SUP.max_app_age, (unsigned)HG_SUP_APP_MS, (unsigned long)SUP.max_writer_age, (int)wrStuck, (unsigned long)SUP.max_tick_gap,
         (unsigned long)SUP.ticks);
  char l[192]; int n = snprintf(l, sizeof l, "# STAT ledger (%u boots on the journal page):", (unsigned)s.boots);
  for (int c = 0; c < HG_BG_RST_COUNT; c++) if (s.by_cls[c]) {
    if (n > 150) { replyf(ch, "%s\n", l); n = snprintf(l, sizeof l, "# STAT ledger ..."); }
    n += snprintf(l + n, sizeof l - n, " %s=%u", hg_bg_class_name(c), (unsigned)s.by_cls[c]);
  }
  replyf(ch, "%s\n", l);
  for (int k = 0; k < s.nlast; k++) {
    char up[16]; upText(up, sizeof up, s.last[k].upc);
    replyf(ch, "# STAT reset -%d: %s (the boot before: up %s, last checkpoint %s) -> level %u %s\n", k + 1, hg_bg_class_name(s.last[k].cls), up,
           s.last[k].cp == HG_BG_CP_UNKNOWN ? "?" : cpName(s.last[k].cp), s.last[k].level, hg_bg_mode_name(hg_bg_mode_of(s.last[k].level)));
  }
}

// =====================================================================
// commands (USB serial and BLE UART, one per line)
// =====================================================================
static void printUiStat(uint8_t ch) {               // 0.9.17 `ui` (also in stat)
  replyf(ch, "# STAT ui: task=%s presses=%lu press_to_motor_ms last=%lu max=%lu (from the first low sample; + up to 20 ms poll) events_dropped=%lu/%lu queue=%u i2c_lock_fails=%lu ui_stack_free=%lu B\n",
         uiTaskOn ? "hgui" : "inline", (unsigned long)uiPresses, (unsigned long)p2bLast, (unsigned long)p2bMax, (unsigned long)uiOutDrops,
         (unsigned long)uiInDrops, UI.qdrop, (unsigned long)i2cLockFails, uiTask ? (unsigned long)uxTaskGetStackHighWaterMark(uiTask) * 4u : 0ul);
  replyf(ch, "# STAT haptics: drv=%d playing=%s patterns=%lu dropped=%lu preempted=%lu overlay_ticks=%lu fails=%lu drv_reinits=%lu go_fails=%lu soft_now=%d (lowbat=%d pof=%d vbat=%.2f)\n",
         (int)hasDrv, hg_hp_active(&HP) ? hg_hp_pat(HP.id)->name : "-", (unsigned long)HP.played, (unsigned long)HP.dropped, (unsigned long)HP.preempts,
         (unsigned long)HP.overlays, (unsigned long)HP.fails, (unsigned long)drvReinits, (unsigned long)drvGoFails, (int)hapSoftNow(), (int)lowBatMode, (int)pofHold, vbat);
  replyf(ch, "# STAT power: prompts=%lu refused=%lu last_refusal=%s prompt_closed=%lu blocked_now=%u boot=%s%s  live=%d base=%.2f d=%+.2f\n",
         (unsigned long)pwrPrompts, (unsigned long)pwrRefusals, pwrLastWhy, (unsigned long)pwrCancels, hg_ui_off_blocked(&UI, millis()),
         bgClass == HG_RST_WAKE ? "woke from System OFF by " : hg_bg_class_name(bgClass),
         bgClass == HG_RST_WAKE ? ((resetReason & POWER_RESETREAS_VBUS_Msk) ? "USB" : (resetReason & POWER_RESETREAS_OFF_Msk) ? "the button" : "?") : "",
         (int)liveDemo, liveBase, liveD);
  replyf(ch, "# STAT ladder: state=%s step=%u remind=%lu done=%lu worked=%lu not_worked=%lu escalated=%lu no_response=%lu responsive=%lu\n",
         hg_ld_state_name(LD.state), LD.step, (unsigned long)LD.n_remind, (unsigned long)LD.n_done, (unsigned long)LD.n_worked,
         (unsigned long)LD.n_not_worked, (unsigned long)LD.n_esc, (unsigned long)LD.n_noresp, (unsigned long)LD.n_resp);
  replyf(ch, "# STAT gauge: %s dot=%d lines water=%.2f cool=%.2f danger=%.2f%s  raise=%s axis=%c%c wakes=%lu\n",
         hg_ga_colour(gaStep)->name, gaPos, GL.line_w, GL.line_c, GL.line_d, gaForce < HG_GA_STEPS ? " (bench override on)" : "",
         raiseOn ? "on" : "off", RZ.sign > 0 ? '+' : '-', "xyz"[RZ.axis], (unsigned long)raiseWakes);
}
static void printStat(uint8_t ch) {
  uint32_t up = millis() / 1000;
  replyf(ch, "# STAT fw=%s boot=%lu reset=%s(0x%08lx) up=%luh%02lum%02lus rot=%u\n", HG_FW_VERSION, (unsigned long)bootCount,
         resetName(resetReason), (unsigned long)resetReason, (unsigned long)(up / 3600), (unsigned long)(up / 60 % 60), (unsigned long)(up % 60), scrRot);
  replyf(ch, "# STAT resets: watchdog=%lu power/brownout=%lu (since first use) quick_boots=%u bootloop_hold=%d\n",
         (unsigned long)bootf.wdt_resets, (unsigned long)bootf.other_resets, quickBoots, bootLoop);
  replyf(ch, "# STAT last reset: %s rr=0x%08lx %s\n", resetName(resetReason), (unsigned long)resetReason, bootWhy);   // 0.9.14
  replyf(ch, "# STAT log writer: jobs=%lu busy=%d last_ms=%lu max_ms=%lu kicks_while_busy=%lu wrlog_drops=%lu slow_calls=%lu failed_calls=%lu last_rc=%ld(%s) ev_file=%s %lu B rotations=%lu pruned=%lu\n",
         (unsigned long)wrJobs, (int)wrBusy, (unsigned long)wrLastMs, (unsigned long)wrMaxMs, (unsigned long)wrSkips, (unsigned long)wrLogDrops,
         (unsigned long)fsSlowN, (unsigned long)fsFailN, (long)fsLastRc, hg_heal_fid_name(fsLastRcFid), evPath, (unsigned long)evBytes,
         (unsigned long)evRotations, (unsigned long)evPruned);
  if (fsSlowLast[0]) replyf(ch, "# STAT last FS_SLOW: %s\n", fsSlowLast);
  replyf(ch, "# STAT flash sr1=0x%02x sr2=0x%02x protect=%s io: reads=%lu progs=%lu erases=%lu\n", flashSr1, flashSr2,
         flashSrCleared ? "WAS SET, cleared at boot" : ((flashSr1 & 0x7C) || (flashSr2 & 0x40)) ? "SET" : "none",
         (unsigned long)ioRd, (unsigned long)ioPr, (unsigned long)ioEr);
  replyf(ch, "# STAT flash io errors: read=%lu prog=%lu erase=%lu (not_blank_after_erase=%lu) ready_timeouts=%lu xfer_timeouts=%lu wake_retries=%lu wake_fails=%lu last=%c@%lu ms deep_power_down=never\n",
         (unsigned long)flashRdErr, (unsigned long)flashPrErr, (unsigned long)flashErErr, (unsigned long)flashEraseVerifyFails,
         (unsigned long)flashRdyTimeouts, (unsigned long)flashXferTimeouts, (unsigned long)flashWakeRetries, (unsigned long)flashWakeFails,
         flashErrLastOp ? (char)flashErrLastOp : '-', (unsigned long)flashErrLastMs);   // 0.9.15
  { TaskHandle_t th = xTimerGetTimerDaemonTaskHandle();   // 0.9.16: the app runs in its own 12 KB task (hgapp), not in the core's 4 KB loop task
    replyf(ch, "# STAT stack_free_min: app=%lu writer=%lu timer=%lu B (of %lu / 6144 / 1024)\n", (unsigned long)uxTaskGetStackHighWaterMark(NULL) * 4u,
           wrTask ? (unsigned long)uxTaskGetStackHighWaterMark(wrTask) * 4u : 0ul, th ? (unsigned long)uxTaskGetStackHighWaterMark(th) * 4u : 0ul,
           (unsigned long)(appTask ? HG_APP_STACK_WORDS * 4u : 4096u)); }
  printBgStat(ch);
  printUiStat(ch);
  replyf(ch, "# STAT boot: class=%s fault=%d wdt_running_at_setup=%d marker_src=%s chain=%u vbat_skipped_during_buzz=%lu vbat_single_lows_ignored=%lu\n",
         hg_reset_name(rstClass), hg_reset_is_fault(rstClass), (int)wdtSurvived,
         mkSrc == HG_MK_SRC_GPREGRET2 ? "gpregret2" : mkSrc == HG_MK_SRC_NOINIT ? "noinit-copy" : "none", guardCount,
         (unsigned long)vbatF.skipped, (unsigned long)vbatF.low_rejected);   // 0.9.15
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
  printHealStat(ch);
  if (fsState == FS_OK && wrBusy) replyf(ch, "# STAT files: (the log writer is busy for %lu ms now - the file list is skipped, loop() is not blocked)\n", (unsigned long)(millis() - fsOpT0C[0]));
  else if (fsState == FS_OK) {
    listLog();
    uint32_t fb = freeBlocks();
    replyf(ch, "# STAT free=%lu bytes (%lu of %lu blocks)%s\n", (unsigned long)fb * 4096u, (unsigned long)fb, (unsigned long)logCfg.block_count, fsFull ? " FULL" : "");
    for (int i = 0; i < ringN; i++) replyf(ch, "# STAT   /log/%s %lu\n", ringNames[i], (unsigned long)ringFiles[i].size);
    flashSleep();
  }
  guardianStat(ch);
  if (rawActive) replyf(ch, "# STAT raw active path=%s samples=%lu left=%lus\n", rawPath, (unsigned long)rawSamples, (unsigned long)((rawEndMs - millis()) / 1000));
}
static void printHealStat(uint8_t ch) {
  replyf(ch, "# FS_HEAL gen=%u events=%s quiet=%d streak=%u post_format=%u disabled=%u formats=%u faults=%lu heals=%lu quarantined=%lu last=%s:%s guarded=%lu ev_failed_bytes=%lu quiet_dropped=%lu saves=%lu\n",
         HS.gen, evPath, (int)fsQuiet, HS.streak, HS.post_format, HS.disabled, HS.formats, (unsigned long)HS.faults, (unsigned long)HS.heals,
         (unsigned long)HS.quarantined, hg_heal_cause_name(HS.last_cause), hg_heal_fid_name(HS.last_fid), (unsigned long)fsGuarded,
         (unsigned long)evDroppedFailed, (unsigned long)quietDroppedRecs, (unsigned long)healSaves);
  for (int i = 0; i < HG_HEAL_QMAX; i++) if (HS.q[i][0]) replyf(ch, "# FS_HEAL   quarantined %s\n", HS.q[i]);
  replyf(ch, "# FS_HEAL slowest call: log %lu ms (%s), InternalFS %lu ms (%s); hung = no I/O %u ms or > %u ms; chain count=%u class=%s\n",
         (unsigned long)fsMaxMs[0], hg_heal_fid_name(fsMaxFid[0]), (unsigned long)fsMaxMs[1], hg_heal_fid_name(fsMaxFid[1]),
         (unsigned)HG_FS_DEADLINE_MS, (unsigned)HG_FS_TOTAL_MS, guardCount, guardCount ? (hg_heal_fid_is_ifs(guardPrevFid) ? "ifs" : "log") : "-");
  replyf(ch, "# FS_HEAL ifs off=%d healed_last=%s heals=%u flash_events=%lu flash_errors=%lu retries=%lu verify_fails=%lu save_fails=%lu\n",
         (int)ifsBad, hg_heal_fid_name(HS.ifs_healed), HS.ifs_heals, (unsigned long)ifsFlashEvents, (unsigned long)ifsFlashErrors,
         (unsigned long)ifsRetries, (unsigned long)ifsVerifyFails, (unsigned long)ifsSaveFails);
}
// 0.9.15 bench fault injection (plan E.2 subset), USB only, inert until "fault arm" (not kept across a reset)
static bool faultArmed = false;
static void faultCommand(int argc, char** argv, uint8_t ch) {
  if (ch != CH_USB) { replyf(ch, "# FAULT usb only\n"); return; }
  if (argc < 2) { replyf(ch, "# FAULT arm | hang-fs | flash-sleep | hang-app | hardfault | assert | loop <1-6>   (armed=%d)\n", (int)faultArmed); return; }
  if (eqi(argv[1], "arm")) { faultArmed = true; replyf(ch, "# FAULT armed (until the next reset)\n"); return; }
  if (!faultArmed) { replyf(ch, "# FAULT not armed: type  fault arm  first\n"); return; }
  if (wrBusy) { replyf(ch, "# BUSY: the log writer is on a slow flash write, try again in a few seconds\n"); return; }
  if (eqi(argv[1], "hang-fs")) {
    replyf(ch, "# FAULT hang-fs: a guarded log call that does no flash I/O. Expect '# FS_HEAL DEADLINE' in ~4 s, then a boot with "
               "reset=FS-GUARD and NOT a watchdog reset after it. Counts as one FS-HEAL fault (a 2nd within 10 min re-formats the log area)\n");
    Serial.flush();
    FsGuard g(HG_FID_OTHER);
    for (;;) delay(10);                             // no flash I/O: the deadline timer resets the band at 4 s
  }
  if (eqi(argv[1], "flash-sleep")) {
    if (fsState != FS_OK) { replyf(ch, "# FAULT flash-sleep: storage %s\n", FS_NAME[fsState]); return; }
    uint32_t r0 = flashWakeRetries, rt0 = flashRdyTimeouts;
    { FsGuard g(HG_FID_OTHER); if (flashWake()) qspiTr.runCommand(0xB9); }   // chip into deep power-down; the driver still thinks it is awake
    replyf(ch, "# FAULT flash-sleep: chip put to deep power-down behind the driver (wake_retries=%lu ready_timeouts=%lu). The next log "
               "write must recover by itself: no reset, no FS_SLOW rc=-5; check  stat  (flash io errors line) after the next minute\n",
           (unsigned long)r0, (unsigned long)rt0);
    return;
  }
  // 0.9.16 (plan E.2): the boot guard's own faults
  if (eqi(argv[1], "hang-app")) {
    replyf(ch, "# FAULT hang-app: the app task stops checking in. Expect a reset in ~5 s and '# BOOTGUARD class=SUPERVISOR' on the next boot "
               "(not WATCHDOG). The log area is not touched.\n");
    delay(50);
    for (;;) {}                                     // no delay, no check-in: only the supervisor (timer task) can end this
  }
  if (eqi(argv[1], "hardfault")) {
    replyf(ch, "# FAULT hardfault: a real hard fault now. Expect '# BOOTGUARD class=CRASH' on the next boot. The log area is not touched.\n");
    delay(50); __builtin_trap();
  }
  if (eqi(argv[1], "assert")) {
    replyf(ch, "# FAULT assert: an assert outside any file call. Expect '# BOOTGUARD class=ASSERT' and NO FS_HEAL marker (plan A-24).\n");
    delay(50); __assert_func(__FILE__, __LINE__, __func__, "fault assert");
  }
  if (eqi(argv[1], "loop")) {
    int nl = argc >= 3 ? atoi(argv[2]) : 0;
    if (nl < 1 || nl > 6) { replyf(ch, "# FAULT loop <1-6>: the next N boots crash at start-up\n"); return; }
    if (nl >= 3 && !(argc >= 4 && strcmp(argv[3], "YES") == 0)) {
      replyf(ch, "# FAULT loop %d reaches SAFE mode, which ERASES InternalFS (twin, family name, routine, day plan; the profile comes back from RAM). "
                 "Type  fault loop %d YES  to do it. fault loop 2 is safe (it stops at CAREFUL: no log for one boot).\n", nl, nl);
      return;
    }
    replyf(ch, "# FAULT loop %d: reboot now, then %d boot(s) crash in a row. Expect the BOOTGUARD lines to walk the rungs%s\n", nl, nl,
           nl >= 6 ? " and the band to switch itself OFF; a button press brings it back in SAFE mode" : "");
    delay(50);
    NI.floop = (uint8_t)nl; bgSoftReset(HG_BG_RC_REBOOT);   // a commanded reset: not a fault, the ladder starts at 0
  }
  replyf(ch, "# FAULT unknown: %s\n", argv[1]);
}
// [FLASH-EASY] LIVE demo (display only). Good contact = T1 read and 28-41 C (on the skin); the baseline = the mean of the first 20 such
// seconds after `live on` (T1 itself is read every 5 s, so the shade moves in 5 s steps). The screen is kept on.
static void liveService(uint32_t now) {
  liveNext = now + 1000u;
  bool ok = hasSkin && t1C == t1C && t1C >= 28.0f && t1C <= 41.0f;
  if (liveBase != liveBase) {
    if (ok) { liveAcc += t1C; liveN++; } else { liveAcc = 0.0f; liveN = 0; }   // 20 s IN A ROW of good contact
    if (liveN >= 20) { liveBase = liveAcc / (float)liveN; evLog("LIVE baseline %.2f C (20 s of good contact)", liveBase); }
  }
  liveD = (liveBase == liveBase && ok) ? t1C - liveBase : (liveBase == liveBase ? liveD : NAN);
  screenWake(SCREEN_ON_MS);                         // never sleeps while LIVE is on (battery does not matter for the demo)
}
static void liveCommand(int argc, char** argv, uint8_t ch) {
  if (argc >= 2 && (eqi(argv[1], "on") || eqi(argv[1], "off"))) {
    bool on = eqi(argv[1], "on");
    if (on && !liveDemo) { liveBase = liveD = NAN; liveAcc = 0.0f; liveN = 0; liveNext = 0; }
    liveDemo = on; GM.valid = false;
    evLog("LIVE demo %s (gauge = skin T1 vs baseline; the engine is unchanged)", on ? "on" : "off");
    if (on) { uiPage = UI_MAIN; screenWake(SCREEN_ON_MS); }
    uiDraw(true);
  }
  replyf(ch, "# LIVE demo=%d base=%.2f d=%+.2f T1=%.2f (gauge: 0 green, +1 yellow, +2 orange, +3 C red; baseline after 20 s of contact)\n",
         (int)liveDemo, liveBase, liveD, t1C);
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
    "#   live on|off          LIVE demo: the gauge colour follows the real skin temperature (vs the first 20 s), screen on\n",
    "#   hex on|off           1 Hz hex lines on USB (BLE always streams; was `live on|off` before 0.9.17-demo-b7u)\n",
    "#   screen | buzz        wake the screen 15 s | test vibration\n",
    "#   vib <1-123> [ms] | vib <name>   0.9.17: one DRV2605L effect (repeated for ms) | a pattern: tick yes cue watch cool urgent help worked question off on\n",
    "#   ui                   0.9.17: press-to-motor latency, haptics, ladder, gauge, wrist raise\n",
    "#   gauge <0-4> | gauge auto     0.9.17: show a gauge colour (green..red) for the bench | back to the forecast\n",
    "#   raise | raise on|off | raise axis <x|y|z> <+|->   0.9.17: wrist raise (the face axis now, wakes)\n",
    "#   flip | flip 0|2      screen image 180 deg (toggle / set; saved, reply # FLIP rot=<n>)\n",
    "#   ladder water|cool|danger|off  0.9.17 bench (USB): start the action ladder as if DRINK / COOL / Danger were shown | reset it\n",
    "#   state | ring <n>     guardian state now | last n minutes of STATUS frames (hex)\n",
    "#   profile <age> <sex 0/1> <bmi> <med bits>   the wearer (saved; e.g. profile 78 0 26 0)\n",
    "#   log on|off           1 Hz debug records on USB + BLE UART\n",
    "#   screen diag          the sensor page for 15 s\n",
    "#   nudge <id>           show a nudge now (1 brief 2 last-cool 4 water 5 air 6 a/c 7 evening 8 leave-hot)\n",
    "#   famsg <1-3>          family message (1 calls you, 2 is coming, 3 saw it) | famname <name> | famname -\n",
    "#   routine <wake hh:mm> <bed hh:mm> | routine off   stated routine for the planner\n",
    "#   events | fcdemo      the event ring | load a DEMO heat-day forecast\n",
    "#   score                0.9.9 alert scorecard (sent / held back per reason / acknowledged / missed / time to ack) + EVENTS SCORE\n",
    "#   dayplan <day> <kind> <place> <uh> <um> <sh> <sm> <dir> <hf> <ht> <peak> <hw>   add a Her Day item | dayplan <day> clear | dayplan\n",
    "#   visit <arrive|leave> <place>   a VISIT from her phone | homeout <home|out|off>   simulate the home/out state (N8)\n",
    "#   erase YES            delete every log file (USB only)\n",
    "#   format YES           re-create the file system: only when stat says CORRUPT or DISABLED (USB only)\n",
    "#   fsformat             re-format the LOG area now (USB only; also accepted in the first 3 s after boot)\n",
    "#   fsheal | fsheal reset   FS-HEAL state (events generation, quarantined files, streaks) | storage back on (USB only)\n",
    "#   rmold                remove the legacy events.txt / events2.txt (USB only; they are never opened otherwise)\n",
    "#   fault arm | fault hang-fs | fault flash-sleep   0.9.15 bench fault injection (USB only)\n",
    "#   fault hang-app | fault hardfault | fault assert | fault loop <1-6>   0.9.16 boot guard faults (USB only, after fault arm)\n",
    "#   pwroff               0.9.16: System OFF now (USB only, after fault arm); press the button to turn on\n",
    "#   uf2 | dfu            reboot into the UF2 bootloader: the XIAO-SENSE drive appears, copy a .uf2 onto it (USB only; no double tap)\n",
    "#   replay [s] | replay stop   DEMO: a SIMULATED heat episode (110 min) through the real engine, s seconds per minute (2)\n",
    "#   replay noresp [s]    DEMO: the same episode, she never presses: the real ladder -> repeat -> no-response note (family SMS)\n",
  };
  for (auto s : H) replyf(ch, "%s", s);
}
static bool eqi(const char* a, const char* b) { return strcasecmp(a, b) == 0; }
static void handleCommand(char* line, uint8_t ch) {
  char* argv[14]; int argc = 0;                    // 0.9.8: 14 (dayplan <day> + 11 item fields needs 13)
  for (char* t = strtok(line, " \t\r"); t && argc < 14; t = strtok(NULL, " \t\r")) argv[argc++] = t;
  if (!argc) return;
  const char* src = (ch == CH_USB) ? "usb" : "ble";
  if (eqi(argv[0], "help") || eqi(argv[0], "?")) printHelp(ch);
  else if (eqi(argv[0], "rmold")) {               // remove the legacy (0.9.6-0.9.9, possibly corrupt) events logs, USB only
    if (ch != CH_USB) { replyf(ch, "# RMOLD usb only\n"); return; }
    if (fsState != FS_OK) { replyf(ch, "# RMOLD: storage %s\n", FS_NAME[fsState]); return; }
    if (wrBusy) { replyf(ch, "# BUSY: the log writer is on a slow flash write, try again in a few seconds\n"); return; }
    static const char* OLD[2] = { "/log/events.txt", "/log/events2.txt" };
    for (int i = 0; i < 2; i++) {
      if (hg_heal_is_quarantined(&HS, OLD[i])) { outf(CH_USB, "# RMOLD %s skipped (a remove of it died before)\n", OLD[i]); continue; }
      strncpy(HS.pending, OLD[i], HG_HEAL_PATH - 1); healSave();   // dies inside -> next boot quarantines it for good
      outf(CH_USB, "# RMOLD %s start\n", OLD[i]); Serial.flush();
      bool rc = fsRemove(OLD[i], HG_FID_HEAL);
      HS.pending[0] = 0; healSave();
      outf(CH_USB, "# RMOLD %s rc=%d\n", OLD[i], (int)rc); Serial.flush();
    }
    flashSleep();
  }
  else if (eqi(argv[0], "fsformat")) {           // 0.9.11: same as the boot escape, any time (USB only)
    if (ch != CH_USB) { replyf(ch, "# FSFORMAT usb only\n"); return; }
    if (fsState == FS_NO_FLASH || fsState == FS_BGOFF) { replyf(ch, "# FSFORMAT: storage %s\n", FS_NAME[fsState]); return; }
    if (wrBusy) { replyf(ch, "# BUSY: the log writer is on a slow flash write, try again in a few seconds\n"); return; }
    dumpStop("STOPPED by fsformat"); rawStop("fsformat");
    hg_heal_reset(&HS); guardCount = 0; NI.mk.gc = 0; fsQuiet = false; healFormat("usb fsformat");
    if (fsState == FS_OK) { bootf.boot_count = bootCount; bootf.quick_boots = 0; bootSave(); newHourFile(); flushAll(); }
    replyf(ch, "# FS_HEAL formatted storage=%s\n", FS_NAME[fsState]);
  }
  else if (eqi(argv[0], "fsheal")) {             // FS-HEAL state; "fsheal reset" (USB only) switches storage back on
    if (argc >= 2 && eqi(argv[1], "reset")) {
      if (ch != CH_USB) { replyf(ch, "# FS_HEAL reset: usb only\n"); return; }
      hg_heal_reset(&HS); healSave();
      replyf(ch, "# FS_HEAL reset: streaks cleared, storage on at the next boot (gen=%u kept)\n", HS.gen);
      return;
    }
    printHealStat(ch);
  }
  else if (eqi(argv[0], "stat")) printStat(ch);
  else if (eqi(argv[0], "time") && argc < 2) replyf(ch, "# TIME needs the unix time: time <unix>  (Mac Terminal: date +%%s)\n");
  else if (eqi(argv[0], "time")) {
    uint32_t u = strtoul(argv[1], NULL, 10);
    if (u < 1700000000UL || u > 4000000000UL) { replyf(ch, "# TIME rejected: %s (expect unix seconds, e.g. 1763280000)\n", argv[1]); return; }
    timeSyncGen++;                                 // 0.9.6: re-anchor the minute boundary, like the BLE TIME path
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
  else if (eqi(argv[0], "hex") && argc >= 2) { liveUsb = eqi(argv[1], "on"); replyf(ch, "# HEX usb=%d\n", liveUsb); }   // [FLASH-EASY] (was `live`)
  else if (eqi(argv[0], "live")) liveCommand(argc, argv, ch);   // [FLASH-EASY] the LIVE demo
  else if (eqi(argv[0], "flip")) {                // [SCREEN-FLIP] flip = toggle 0/2, flip 0 | flip 2 = set; applied now, saved
    if (argc >= 2 && (!strcmp(argv[1], "0") || !strcmp(argv[1], "2"))) scrRot = (uint8_t)(argv[1][0] - '0');
    else if (argc >= 2) { replyf(ch, "# FLIP rejected: use flip | flip 0 | flip 2\n"); return; }
    else scrRot = scrRot ? 0 : 2;
    bool saved = scrRotSave();
    if (gfxUp) { gfx->setRotation(scrRot); gfx->fillScreen(C_BLACK); }
    GM.valid = false; screenWake(SCREEN_ON_MS); uiDraw(true);   // the page she was on, redrawn whole in the new rotation
    evLog("SCREEN rotation %u by %s (saved=%d)", scrRot, src, (int)saved);
    replyf(ch, "# FLIP rot=%u%s\n", scrRot, saved ? "" : " (not saved: InternalFS off or write failed; RAM only until reboot)");
  }
  else if (eqi(argv[0], "screen")) { uiPage = (argc >= 2 && eqi(argv[1], "diag")) ? UI_DIAG : UI_MAIN; screenWake(SCREEN_ON_MS); uiDraw(true); }
  else if (eqi(argv[0], "buzz")) hapPost(HG_HP_BUZZ);
  else if (eqi(argv[0], "vib")) {                   // 0.9.17 bench: vib <effect 1-123> [ms] | vib <pattern name>
    int id = argc >= 2 ? hg_hp_find(argv[1]) : 0; long eff = argc >= 2 ? strtol(argv[1], NULL, 10) : 0;
    if (id) { hapPost((uint8_t)id); replyf(ch, "# VIB pattern %s (priority %u)\n", hg_hp_pat(id)->name, hg_hp_pat(id)->prio); }
    else if (eff >= 1 && eff <= 123) { long ms = argc >= 3 ? strtol(argv[2], NULL, 10) : 0; if (ms < 0) ms = 0; if (ms > 10000) ms = 10000;
      hapRaw((uint8_t)eff, (uint16_t)ms); replyf(ch, "# VIB effect %ld%s%ld ms (DRV2605L library, today's strength)\n", eff, ms ? " repeated for " : " once ", ms); }
    else replyf(ch, "# VIB: vib <1-123> [ms] | vib tick|yes|cue|watch|cool|urgent|help|worked|question|off|on|buzz\n");
  }
  else if (eqi(argv[0], "ui")) printUiStat(ch);
  else if (eqi(argv[0], "flashdiag")) {
    if (wrBusy) { replyf(ch, "# BUSY: the log writer is on a slow flash write, try again in a few seconds\n"); return; }
    flashDiag(ch); flashVerify = true;              // 0.9.15: the next log call re-checks the chip
  }
  else if (eqi(argv[0], "fault")) faultCommand(argc, argv, ch);
  else if (eqi(argv[0], "pwroff")) {               // 0.9.16 test of hgSystemOff (plan F 0.9.16: "used by rest and the USB pwroff test only")
    if (ch != CH_USB || !faultArmed) { replyf(ch, "# PWROFF: USB only, after  fault arm\n"); return; }
    flushAll(); uint32_t t0 = millis(); while (wrBusy && millis() - t0 < 5000u) { wdtFeed(); delay(10); }   // the log first (<= 5 s)
    bgAppend(hg_bg_mark(HG_BG_T_CLEAN));           // the wake that follows is not a fault
    hgSystemOff("pwroff command");
  }
  else if (eqi(argv[0], "uf2") || eqi(argv[0], "dfu")) {   // [FLASH-EASY] 0.9.17-demo-b7u: the bootloader without the double tap
    if (ch != CH_USB) { replyf(ch, "# UF2: USB only\n"); return; }
    if (erasing) { replyf(ch, "# BUSY: erase in progress, try again when it ends\n"); return; }
    dumpStop("STOPPED by uf2"); rawStop("uf2");
    replyf(ch, "# UF2: rebooting into the UF2 bootloader (drive XIAO-SENSE)\n");
    evLog("UF2 reboot into the UF2 bootloader by usb");
    uint32_t t0 = millis();                         // the log as before pwroff (<= 6 s, the app checks in all along)
    while (wrBusy && millis() - t0 < 5000u) { wdtFeed(); delay(10); }   // a job already running ends first,
    flushAll(); while (wrBusy && millis() - t0 < 6000u) { wdtFeed(); delay(10); }   // then the last records + this line
    bgAppend(hg_bg_mark(HG_BG_T_CLEAN));            // the journal: this boot ended on purpose
    Serial.flush(); t0 = millis(); while (millis() - t0 < 200u) { wdtFeed(); delay(10); }   // USB sends the reply
    hgEnterUf2();
  }
  else if (eqi(argv[0], "erase")) {
    if (argc < 2 || strcmp(argv[1], "YES") != 0) { replyf(ch, "# ERASE: type  erase YES  to delete every log file\n"); return; }
    if (ch != CH_USB) { replyf(ch, "# ERASE only over USB\n"); return; }
    if (fsState != FS_OK) { replyf(ch, "# ERASE: storage %s\n", FS_NAME[fsState]); return; }
    if (wrBusy) { replyf(ch, "# BUSY: the log writer is on a slow flash write, try again in a few seconds\n"); return; }
    dumpStop("STOPPED by erase"); rawStop("erase");
    listLog();
    eraseN = 0;
    for (int i = 0; i < ringN && eraseN < HG_RING_MAX_FILES; i++) if (ringFiles[i].kind != 'b') snprintf(dumpList[eraseN++], 24, "/log/%.15s", ringNames[i]);
    eraseI = 0; erasing = true;                // one file per loop pass: no long stall near the watchdog (T6a m8)
    replyf(ch, "# ERASE started: %u files\n", eraseN);
  }
  else if (eqi(argv[0], "format")) {
    if (argc < 2 || strcmp(argv[1], "YES") != 0) { replyf(ch, "# FORMAT: type  format YES  (destroys all logs)\n"); return; }
    if (ch != CH_USB) { replyf(ch, "# FORMAT only over USB\n"); return; }
    if (fsState == FS_NO_FLASH || fsState == FS_BGOFF) { replyf(ch, "# FORMAT: storage %s\n", FS_NAME[fsState]); return; }
    if (fsState == FS_OK) { replyf(ch, "# FORMAT refused: storage is OK (use erase YES to clear logs)\n"); return; }
    if (wrBusy) { replyf(ch, "# BUSY: the log writer is on a slow flash write, try again in a few seconds\n"); return; }
    dumpStop("STOPPED by format"); rawStop("format");
    { FsGuard g(HG_FID_FORMAT); logFS.end(); logFS.format(); fsState = logFS.begin() ? FS_OK : FS_CORRUPT; }
    strcpy(fsMsg, fsState == FS_OK ? "formatted by command" : "format failed");
    if (fsState == FS_OK) {
      { FsGuard g(HG_FID_MOUNT); logFS.mkdir("/log"); }
      hg_heal_reset(&HS); memset(HS.q, 0, sizeof HS.q); HS.dump_path[0] = 0; evPathUpdate(); healSave();   // fresh area: nothing quarantined
      fsQuiet = false; bootf.boot_count = bootCount; bootSave(); newHourFile();
    }
    replyf(ch, "# FORMAT %s\n", FS_NAME[fsState]);
    flashSleep();
  }
  else if (guardianCommand(argc, argv, ch)) {}
  else replyf(ch, "# unknown command: %s  (type help)\n", argv[0]);
}
static void eraseService() {
  if (!erasing) return;
  if (eraseI < eraseN) { fsRemove(dumpList[eraseI++], HG_FID_RING); return; }
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
  while (bleOn && bleuart.available()) {
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
  Bluefruit.configPrphBandwidth(BANDWIDTH_LOW);    // MTU 23, small buffers (R4 A1)
  Bluefruit.begin(HG_MAX_LINKS, 0);                // 0.9.8: 2 phones at once (her phone + the family phone), no central role
#if HG_DCDC
  sd_power_dcdc_mode_set(NRF_POWER_DCDC_ENABLE);   // R4 A6: the core does not enable it
#endif
  Bluefruit.setTxPower(0);
  Bluefruit.setName("HeatGuardian");
  bledis.setManufacturer("Heat Guardian");
  bledis.setModel("Band A 09_guardian");
  bledis.setFirmwareRev(HG_FW_VERSION " " HG2_NN_VERSION);
  bledis.begin();
  bleuart.begin();
  hgBleBegin();                                    // HG service: STATUS / CMD / INFO
  blebas.begin(); blebas.write(batteryPct(vbat));
  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(hgSvc);
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 1636);     // 20 ms for 30 s, then 1022.5 ms (units of 0.625 ms)
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Periph.setConnectCallback(hgOnConnect);
  Bluefruit.Periph.setDisconnectCallback(hgOnDisconnect);
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
// 0.9.16 (plan A-11 / B.1): the application runs in its own task "hgapp" with a 12 KB static stack (the core's loop task has 4 KB and
// 0.9.15 measured 1.3 KB left). The core's loop task only creates it and then suspends itself.
static StaticTask_t appTcb; static StackType_t appStack[HG_APP_STACK_WORDS];
static bool appInline = false;                     // (no task: the old way, in the core's loop task)
static void appSetup(); static void appLoop();
static void appTaskFn(void*) { appSetup(); for (;;) { appLoop(); yield(); } }   // yield(): the core's loop flushes USB CDC there
void setup() {
  // 0.9.15 (plan A-01) FIRST statement: a soft reset (FS guard, crash, upload) does NOT stop the watchdog. The last boot's 8 s
  // keeps counting through the bootloader; 0.9.14 first fed it after a 3 s Serial wait (margin ~0 after an FS-guard reset).
  wdtSurvived = NRF_WDT->RUNSTATUS & 1u;
  if (wdtSurvived) wdtFeed();
  appTask = xTaskCreateStatic(appTaskFn, "hgapp", HG_APP_STACK_WORDS, NULL, TASK_PRIO_LOW, appStack, &appTcb);
  if (!appTask) { appInline = true; appSetup(); }
}
static void appSetup() {
  resetReason = readResetReason();                 // the core's init() saved and cleared RESETREAS (T6a M1)
  fsMtx = xSemaphoreCreateRecursiveMutex();        // 0.9.14: QSPI log calls from two tasks never interleave
  i2cMtx = xSemaphoreCreateMutex();                // 0.9.17: TWIM0 shared by hgapp (sensors) and hgui (the motor)
  if (!healMtx) healMtx = xSemaphoreCreateRecursiveMutex();   // 0.9.16: every raw-page write (heal state, boot journal)
  niValid = NI.magic == HG_NI_MAGIC;               // 0.9.13: what the last boot left in .hg_noinit
  if (niValid) { niLastCp = NI.cp < CP_COUNT ? NI.cp : 0; niLastMs = NI.cp_ms; niBoots = NI.boots; niEscDone = NI.esc_done; }
  else { memset(&NI, 0, sizeof NI); NI.magic = HG_NI_MAGIC; }
  niExtValid = niValid && NI.magic2 == HG_NI_MAGIC2;
  NI.magic2 = HG_NI_MAGIC2;
  bgNiValid = niExtValid && NI.magic3 == HG_NI_MAGIC3;   // 0.9.16: the boot-guard RAM copy of the last boot + its reset code
  if (bgNiValid) { bgRcode = NI.rcode; bgRarg = NI.rarg; bgFloop = NI.floop > 6 ? 0 : NI.floop; }
  else { memset(&NI.bg, 0, sizeof NI.bg); NI.rcode = NI.rarg = NI.floop = 0; memset(NI.prof, 0, sizeof NI.prof); }
  NI.boots++; NI.esc_done = 0; CP(CP_S_START);
  // 0.9.10 FS-HEAL: did the last boot die inside a guarded FS call? 0.9.15: the marker is copied into .hg_noinit HERE, before
  // anything can wait, and GPREGRET2 is cleared only after the heal state that counts it is saved (below). A watchdog or pin
  // reset in between clears GPREGRET2 but not the RAM copy, so the ladder rung is never lost (0.9.14 cleared it right here).
  healMarkerReg = hg_mk_pick(gpregret2Read(), &NI.mk, niExtValid, &mkSrc);
  uint8_t mkC = 0, mkF = 0, mkN = 0, mkIb = 0;
  bool mkOk = hg_heal_marker_decode(healMarkerReg, &mkC, &mkF, &mkN, &mkIb);
  if (mkOk) ifsBad = mkIb;                         // ifs_bad = InternalFS was already switched off in this chain
  hg_mk_chain(healMarkerReg, &NI.mk, niExtValid, &guardCount, &guardPrevFid);   // the chain survives a watchdog reset too
  NI.mk.gc = guardCount; NI.mk.gfid = guardPrevFid;
  wdtStart(8000);                                  // from here on a hang resets the board (already running: just fed)
  // 0.9.16 SUPERVISOR from here on (plan D.4): the 250 ms tick is the only feeder of the watchdog; wdtFeed() = a check-in.
  // (It also checks the FS deadline, so it runs before ANY guarded call, as the 0.9.10 timer did.)
  wdtFeed(); fsDogTimer.begin(250, fsDogCb);
  supOn = fsDogTimer.start();                      // no timer = the app keeps feeding the watchdog itself (wdtFeed)
  pinMode(VBAT_ENABLE, OUTPUT); digitalWrite(VBAT_ENABLE, LOW);   // review rule: P0.14 LOW
  pinMode(LCD_BL, OUTPUT); digitalWrite(LCD_BL, LOW);
  pinMode(PIN_BTN, INPUT_PULLUP);
  pinMode(PIN_NCHG, INPUT_PULLUP);
  vbat = readVbat();                               // VBAT before anything else (R4 A8.1)

  // FS-HEAL state (noinit copy, else the reserved flash page) + this boot's decisions: no file system involved
  CPS(CP_S_HEAL);
  healLoad();
  bool ifsFault = mkOk && hg_heal_fid_is_ifs(mkF) && !ifsBad;
  uint8_t ifsPrev = healStateValid ? HS.ifs_healed : 0;
  hg_heal_begin(&HS, &HB, healStateValid, healMarkerReg, hg_heal_crc32(HG_BUILD_ID, sizeof HG_BUILD_ID - 1));
  fsGuardReset = HB.marker;
  rstClass = hg_reset_classify(resetReason, HB.marker, HB.new_build);   // 0.9.15: needs the marker and the build id
  // 0.9.16 BOOT GUARD: the ladder decision + STARTED in the journal, before anything that can fail
  bgBoot();

  // screen FIRST (plan F 0.9.16: screen and motor before storage): splash within ~0.5 s of the reset, also without USB
  CPS(CP_S_SCREEN);
  SPI.setPins(SPI_DUMMY_MISO, LCD_SCK, LCD_MOSI);  // MISO = dead D9 (never read); CS is D1, driven by the GFX bus
  bool busOk = bus->begin(8000000, SPI_MODE0);     // SPI mode 0 fix (04c)
  bool gfxOk = gfx->begin(GFX_SKIP_DATABUS_BEGIN);
  gfx->setRotation(scrRot);                        // [SCREEN-FLIP] 0 here (InternalFS is not up yet); the saved value is applied after guardianBoot()
  screenOn = true; gfxUp = true;                   // gfx->begin() leaves the panel awake
  bgSplash();

  CP(CP_S_SERIAL);
  Serial.begin(115200);
  // 0.9.15 (A-01 / A-22): wait for a terminal only with USB power (the wearer has none), and feed the watchdog inside
  if (vbusPresent()) while (!Serial && millis() < 3000) { wdtFeed(); delay(10); }
  wdtFeed();
  if (!busOk) outf(CH_USB, "# bus->begin() failed\n");
  if (!gfxOk) outf(CH_USB, "# gfx->begin() failed\n");

  // I2C sensors + the haptic driver (bounded, hg_i2c.c), before storage: the alert path is up before any file system call
  CPS(CP_S_SENSORS);
  i2cPins();
  if (!i2cLinesHigh()) { hg_i2c_bus_clear(); delay(1); }
  i2cBusOkAtBoot = i2cLinesHigh();
  hg_i2c_begin(5, 4);                              // SCL P0.05 (D5), SDA P0.04 (D4), 100 kHz
  hg_ppg_init(&hrDet);
  if (i2cBusOkAtBoot) for (int d = 0; d < DEV_N; d++) *devFlag(d) = probeDev(d);
  if (hasPpg) ppgEnable(false);                    // 0.9.16: off until storage is up (the FIFO is cleared when it is switched on below)

  outf(CH_USB, "\n# Heat Guardian %s  reset=%s(0x%08lx)  vbat=%.3f V\n", HG_FW_VERSION, resetName(resetReason),
       (unsigned long)resetReason, vbat);
  if (rstClass == HG_RST_WATCHDOG && niValid)
  { outf(CH_USB, "# WDT last boot hung after checkpoint %s at t_ms=%lu (boots since power-on %lu)\n", CP_NAME[niLastCp], (unsigned long)niLastMs, (unsigned long)niBoots);
    snprintf(bootWhy, sizeof bootWhy, "watchdog: hung after checkpoint %s at t_ms=%lu", CP_NAME[niLastCp], (unsigned long)niLastMs); }
  else if (rstClass == HG_RST_WATCHDOG)
    outf(CH_USB, "# WDT last boot hung (no checkpoint: RAM did not survive)\n");
  outf(CH_USB, "# BOOT0915 class=%s fault=%d wdt_running_at_setup=%d marker=0x%02x src=%s chain=%u\n", hg_reset_name(rstClass),
       hg_reset_is_fault(rstClass), (int)wdtSurvived, healMarkerReg,
       mkSrc == HG_MK_SRC_GPREGRET2 ? "gpregret2" : mkSrc == HG_MK_SRC_NOINIT ? "noinit-copy" : "none", guardCount);
  { char up[16]; upText(up, sizeof up, bgPrevUpc);
    char task[16] = ""; if (bgClass == HG_BG_RST_SUPERVISOR || bgClass == HG_BG_RST_STACK) snprintf(task, sizeof task, "(task %s)", BG_TASK[bgRarg < 5 ? bgRarg : 0]);
    outf(CH_USB, "# BOOTGUARD class=%s%s level=%u mode=%s slow=%u prev_up=%s prev_cp=%s dead_stage=%s journal=%s(%d words) ram_copy=%d\n",
         hg_bg_class_name(bgClass), task, BGD.level, hg_bg_mode_name(BGD.mode), BGD.slow, up, bgPrevCp == HG_BG_CP_UNKNOWN ? "?" : cpName(bgPrevCp),
         BG_STAGE[bgDead & 3], bgStartedOk ? "ok" : "WRITE-FAILED", BGS.used + (bgStartedOk ? 1 : 0), (int)bgNiValid); }
  if (BGD.mode != HG_BG_NORMAL)
    outf(CH_USB, "# BOOTGUARD %s: storage=%s ble=%s internalfs=%s (screen, button, motor, sensors, guardian: on)\n", hg_bg_mode_name(BGD.mode),
         BGP.storage_off ? "off" : "on", BGP.ble_off ? "off" : "on", BGP.ifs_off ? "off" : BGP.ifs_erase ? "erased" : "on");
  if (BGP.rest) bgRest();                          // never returns: System OFF
  vibrate(PAT_PWRUP);                              // plan C.4 power-up pattern (a soft tick on a low battery)
  hg_rz_init(&RZ, 2, 1);                           // 0.9.17 wrist raise: face = +z (console `raise axis` if the board sits the other way)
  uiStart(bgClass == HG_RST_WAKE);                 // 0.9.17: hgui owns the button + motor from here (the wake press is not a command)
  if (bgClass == HG_RST_WAKE) evLog("POWER wake from System OFF by %s (rr=0x%08lx)", (resetReason & POWER_RESETREAS_VBUS_Msk) ? "USB plugged in" :
                                    (resetReason & POWER_RESETREAS_OFF_Msk) ? "the button" : "?", (unsigned long)resetReason);   // [FLASH-EASY]

  // InternalFS heal ladder (0.9.12) - skipped when the boot guard keeps InternalFS out of this boot
  CPS(CP_S_IFS);
  if (BGP.ifs_off || BGP.ifs_erase) ifsBad = true; // safe / minimal: no InternalFS call of ours (safe re-enables it after the erase)
  else if (ifsFault) ifsHealBoot(mkF, mkN, mkF == HG_FID_IFS_HEAL ? 0 : ifsPrev);   // 0.9.12 InternalFS ladder
  if (healIfsHealed) { HS.ifs_healed = healIfsHealed == 0xFF ? 0 : healIfsHealed; if (HS.ifs_heals < 255) HS.ifs_heals++; }
  if (HB.marker) healSave();                       // the streak saved (noinit + flash page) before any QSPI call ...
  hg_mk_consumed(&NI.mk);                          // ... and only then the marker is consumed (0.9.15)
  if (gpregret2Read()) gpregret2Write(0);
  if (HB.new_build && !ifsBad) {                   // 0.9.13 upgrade: the 0.9.12 heal state file on InternalFS is not used any more
    bool had, rc = false; { FsGuard g(HG_FID_IFS_HEAL); InternalFS.begin(); had = InternalFS.exists("/fsheal.bin"); if (had) rc = InternalFS.remove("/fsheal.bin"); }
    if (had) evLog("FS_HEAL removed the old InternalFS /fsheal.bin: %s (an assert here -> next boot formats InternalFS, profile kept)", rc ? "ok" : "failed");
  }
  // 0.9.11 emergency escape: within the first 3 s, "fsformat" on USB formats the log area before anything touches it
  CPS(CP_S_ESC);
  if (Serial && niEscDone && !(resetReason & POWER_RESETREAS_RESETPIN_Msk)) {
    outf(CH_USB, "# FS_HEAL format escape skipped: the last boot already formatted (press reset to allow it again)\n");
  } else if (Serial && !BGP.storage_off) {
    char eb[24]; uint8_t en = 0;
    while (millis() < 3000 && !usbFsFormat) {
      while (Serial.available() && !usbFsFormat) {
        char ch = Serial.read();
        if (ch == '\n' || ch == '\r') { eb[en] = 0; if (strcmp(eb, "fsformat") == 0) usbFsFormat = true;
          else if (strcmp(eb, "ifsformat") == 0) usbIfsFormat = true;
          else if (en) outf(CH_USB, "# BOOTING t_ms=%lu: '%s' not run (this window only takes fsformat / ifsformat); type it again after '# ready'\n",
                            (unsigned long)millis(), eb);   // 0.9.15: never a silent empty reply
          en = 0; }
        else if (en < sizeof eb - 1) eb[en++] = ch;
      }
      wdtFeed(); delay(5);
    }
    if (usbFsFormat) { outf(CH_USB, "# FS_HEAL fsformat received\n"); Serial.flush(); NI.esc_done = 1; }
    if (usbIfsFormat) NI.esc_done = 1;
  }
  if (usbIfsFormat && !BGP.ifs_off && !BGP.ifs_erase) {
    CPS(CP_F_IFS);                              // 0.9.13 escape: "ifsformat" = InternalFS ladder format now (profile kept)
    ifsBad = false; outf(CH_USB, "# FS_HEAL ifsformat received\n");
    ifsHealBoot(HG_FID_IFS_HEAL, 2, 0); HS.ifs_healed = 0; healSave();
    outf(CH_USB, "# FS_HEAL ifs formatted\n"); Serial.flush();
  }
  if (HB.marker) snprintf(bootWhy, sizeof bootWhy, "fs-guard: %s in fid=%s (count %u)", hg_heal_cause_name(HB.cause), hg_heal_fid_name(HB.fid), HB.count);
  else if (!bootWhy[0]) snprintf(bootWhy, sizeof bootWhy, "%s", rstClass == HG_RST_WATCHDOG ? "watchdog: no checkpoint (RAM lost)" :
                                 bgClass >= HG_BG_RST_SUPERVISOR ? hg_bg_class_name(bgClass) : "no fault recorded");
  if (HB.marker) outf(CH_USB, "# FS_HEAL last boot died in a guarded FS call: cause=%s fid=%s%s%s%s count=%u%s (gpregret2=0x%02x)%s\n",
                      hg_heal_cause_name(HB.cause), hg_heal_fid_name(HB.fid), hg_heal_fid_is_ifs(HB.fid) ? " (InternalFS " : "",
                      hg_heal_ifs_files(HB.fid), hg_heal_fid_is_ifs(HB.fid) ? ")" : "", HB.count, HB.ifs_bad ? " ifs_bad" : "", healMarkerReg,
                      HB.fid == HG_FID_NONE ? " -> counted only (0.9.16: fid none never touches the log area)" :
                      HB.disable ? " -> storage OFF this boot" : HB.format ? " -> re-format the log area now" :
                      HB.ifs_action == HG_IFS_REMOVE ? " -> quarantine that InternalFS file" : HB.ifs_action == HG_IFS_FORMAT ? " -> format InternalFS (profile kept)" :
                      HB.ifs_action == HG_IFS_OFF ? " -> InternalFS off this boot" : "");

  // 1. recording and console (the QSPI log: careful and above leave it out)
  bootQspi[0] = NRF_QSPI->ENABLE; bootQspi[1] = NRF_QSPI->PSEL.SCK; bootQspi[2] = NRF_QSPI->PSEL.CSN; bootQspi[3] = NRF_QSPI->PSEL.IO0;
  CPS(CP_S_STORAGE);
  if (BGP.storage_off) { fsState = FS_BGOFF; snprintf(fsMsg, sizeof fsMsg, "not started: boot guard %s", hg_bg_mode_name(BGD.mode)); }
  else storageInit();
  if (BGP.ifs_erase) { bgIfsErase(); if (!BGP.ifs_off) ifsBad = false; }   // safe: erased raw, then Bluefruit formats it fresh
  CPS(CP_S_BLE);
  if (BGP.ble_off) { bleOn = false; evLog("BOOTGUARD %s: BLE not started (the last boot died in it): local alerts only", hg_bg_mode_name(BGD.mode)); }
  else bleSetup();
  CPS(CP_S_FLUSH);
  lowBatMode = (vbat == vbat) && vbat > 2.5f && vbat < VBAT_CHARGE_ME && !charging();
  evLog("BOOT boot=%lu t_ms=%lu fw=%s reset=%s rr=0x%08lx vbat=%.3f lowbat=%d quick_boots=%u bootloop=%d storage=%s(%s) jedec=%06lx",
        (unsigned long)bootCount, (unsigned long)millis(), HG_FW_VERSION, resetName(resetReason), (unsigned long)resetReason, vbat,
        lowBatMode, quickBoots, bootLoop, FS_NAME[fsState], fsMsg, (unsigned long)flashJedec);
  evLog("BOOTGUARD boot=%lu class=%s level=%u mode=%s slow=%u prev_cp=%s dead_stage=%s journal=%s storage=%s ble=%s internalfs=%s",
        (unsigned long)bootCount, hg_bg_class_name(bgClass), BGD.level, hg_bg_mode_name(BGD.mode), BGD.slow,
        bgPrevCp == HG_BG_CP_UNKNOWN ? "?" : cpName(bgPrevCp), BG_STAGE[bgDead & 3], bgStartedOk ? "ok" : "WRITE-FAILED",
        BGP.storage_off ? "off" : "on", bleOn ? "on" : "off", ifsBad ? "off" : "on");
  {
    char mk[32] = "none"; if (HB.marker) snprintf(mk, sizeof mk, "%s:%s:count%u%s", hg_heal_cause_name(HB.cause), hg_heal_fid_name(HB.fid), HB.count, HB.ifs_bad ? ":ifs" : "");
    char qb[48] = ""; if (healPrevQuick != 0xFFFFFFFFu) snprintf(qb, sizeof qb, " quick_boots_reset_from=%lu", (unsigned long)healPrevQuick);
    evLog("FS_HEAL boot=%lu marker=%s bootloop=%d quiet=%d state=%s gen=%u events=%s streak=%u formats=%u storage=%s legacy=%s%s",
          (unsigned long)bootCount, mk, (int)bootLoop, (int)fsQuiet, HB.state_new ? "new" : "loaded", HS.gen, evPath, HS.streak, HS.formats,
          fsState == FS_OK ? "OK" : FS_NAME[fsState],
          legacyEvents == 3 ? "events.txt+events2.txt(kept,never-opened)" : legacyEvents == 2 ? "events2.txt(kept,never-opened)" :
          legacyEvents == 1 ? "events.txt(kept,never-opened)" : "none", qb);
  }
  bootHourFile();
  queueMarker(HG_M_BOOT, (uint16_t)bootCount, "boot");
  wrStart();                                        // 0.9.14: the log writer task; from here on loop() never waits on a log write
  TR("# TRACE %lu before flushAll (handed to the writer task=%d)\n", (unsigned long)millis(), (int)wrRunning);
  trFlush = true;
  flushAll();                                      // BOOT line + file header on flash now, before any sensor traffic
  trFlush = false;
  TR("# TRACE %lu after flushAll (kick)\n", (unsigned long)millis());
  if (hasPpg) ppgEnable(!lowBatMode);              // also clears the FIFO filled during setup
  evLog("SENSORS t_ms=%lu bus=%s skin=%d ref=%d sht=%d imu=%d imu_lp=%d ppg=%d drv=%d i2c_timeouts=%lu",
        (unsigned long)millis(), i2cBusOkAtBoot ? "ok" : "STUCK-LOW", hasSkin, hasRef, hasSht, hasImu, imuLowPower, hasPpg, hasDrv,
        (unsigned long)hg_i2c_stats.timeouts);

  CPS(CP_S_GUARDIAN);
  guardianBoot();                                   // CRC check, profile, Body Twin file, guardian init
  bgInjectIfArmed();                                // bench "fault loop N" only
  CPS(CP_S_UI);
  scrRotLoad();                                     // [SCREEN-FLIP] the saved rotation (InternalFS is up now), before the first real screen
  if (scrRot) { gfx->setRotation(scrRot); gfx->fillScreen(C_BLACK); GM.valid = false; }
  screenWake(SCREEN_ON_MS);
  uiDraw(true);
  setupMs = millis(); setupDone = true;
  outf(CH_USB, "# ready in %lu ms (app task stack %lu B). Type help.\n", (unsigned long)setupMs, (unsigned long)(appTask ? HG_APP_STACK_WORDS * 4u : 4096u));
}

void loop() {                                       // 0.9.16: the core's loop task has nothing left to do
  if (appInline) { appLoop(); return; }
  vTaskSuspend(NULL);
}
static void appLoop() {
  static uint32_t nextImu = 0, nextSec = 0, nextTmp = 500, tmpReadAt = 0, nextSht = 1000, shtReadAt = 0;
  static uint32_t nextVbat = 10000, nextProbe = 60000, nextStatus = 10000, nextDraw = 0, nextPpg = 0;
  static bool tmpPending = false, shtPending = false, tmpA = false, tmpB = false;
  wdtFeed(); CP(CP_L_TOP);                          // 0.9.16: the app's check-in (the supervisor feeds the watchdog)
  wrLogDrain();                                     // 0.9.14: lines from the log writer task
  uint32_t now = millis();
  if (nextSec == 0) nextSec = (now / 1000 + 1) * 1000;

  // MAX30102 FIFO every 100 ms (~10 samples per burst; the FIFO holds 32 = 320 ms)
  CP(CP_L_PPG);
  if ((int32_t)(now - nextPpg) >= 0) { nextPpg = now + 100; ppgService(moving); }
  CP(CP_L_IMU);

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
      if (m > accPeak) accPeak = m;
      if (raiseOn && !liveDemo && hg_rz_sample(&RZ, x, y, z, now)) {   // [FLASH-EASY] LIVE: the screen is on anyway   // 0.9.17 wrist raise (owner decision Nov 19 18:31): wake the screen 8 s
        raiseWakes++;
        if (!screenOn && modelOk) { uiPage = UI_MAIN; screenWake(RAISE_ON_MS); uiDraw(true); }
      }
    }
  }

  CP(CP_L_TMP);
  // TMP117 one-shot every 5 s (not within 2 s of a buzz), read 200 ms later
  if (!tmpPending && (int32_t)(now - nextTmp) >= 0 && !recentlyBuzzed()) {
    nextTmp = now + TMP_PERIOD_MS;
    // 0.9.6: triggers count too (devResult), so an unplugged TMP117 is marked lost instead of feeding its last value forever
    tmpA = hasSkin && devResult(DEV_SKIN, tmpTrigger(0x48));
    tmpB = hasRef && devResult(DEV_REF, tmpTrigger(0x49));
    if (!hasSkin) t1C = NAN;
    if (!hasRef) t2C = NAN;
    if (tmpA || tmpB) { tmpPending = true; tmpReadAt = now + TMP_CONV_MS; }
  }
  if (tmpPending && (int32_t)(now - tmpReadAt) >= 0) {
    tmpPending = false;
    // a failed read keeps the last value; 3 failures in a row mark the sensor missing (T6a m7)
    if (tmpA && hasSkin && !devResult(DEV_SKIN, tmpRead(0x48, &t1C)) && !hasSkin) t1C = NAN;
    if (tmpB && hasRef && !devResult(DEV_REF, tmpRead(0x49, &t2C)) && !hasRef) t2C = NAN;
  }
  // SHTC3 every 10 s
  if (hasSht && !shtPending && (int32_t)(now - nextSht) >= 0 && !recentlyBuzzed()) {
    nextSht = now + SHT_PERIOD_MS;
    if (devResult(DEV_SHT, shtTrigger())) { shtPending = true; shtReadAt = now + SHT_CONV_MS; }   // 0.9.6: a dropped SHTC3 is marked lost
    else if (!hasSht) tairC = rhPct = NAN;
  }
  if (shtPending && (int32_t)(now - shtReadAt) >= 0) {
    shtPending = false;
    if (!devResult(DEV_SHT, shtRead()) && !hasSht) tairC = rhPct = NAN;
  }

  CP(CP_L_BTN);
  uiAppService(now);                                // 0.9.17: button events from hgui (the tick was already felt), context, backlight
  CP(CP_L_CMD);
  serviceCommands();
  CP(CP_L_DUMP);
  dumpService();
  eraseService();
  rawUsbService();
  CP(CP_L_BLEU);
  bleService();
  CP(CP_L_REC);

  // 1 Hz record
  while ((int32_t)(now - nextSec) >= 0) {
    uint32_t tick = nextSec;
    nextSec += 1000;
    if (now - tick >= 1000) continue;            // stalled > 1 s: leave a gap (the parser reports it)
    secondStats();
    accSumD = accSumD2 = accX = accY = accZ = 0; accN = 0;
    guardianSecond(tick);                          // minute boundary FIRST (this second opens the new minute), PPG duty, haptics
    emitSecond(tick);
    accImpact = false; accPeak = 0;
    bool flushNow = (tick % 60000u == 0) || tick == 10000u || tick == 30000u;   // minute records are written every 10 min (HG_MIN_FLUSH_EVERY)
    // red LED 1 s of every 4 s for the DC-ratio contact check
    if (hasPpg && ppgEnabled) {
      uint32_t s = tick / 1000;
      if (redOn && redN) redDc = redSum / redN;
      ppgSetRed((s % 4) == 0);
    }
    if (rawActive && (int32_t)(now - rawEndMs) >= 0) rawStop("done");
    if (rawActive && rawBufLen >= 10 * sizeof rawBlock) { rawFlush(); flashSleep(); }
    if (flushNow) { CP(CP_L_FLUSH); flushAll(false); CP(CP_L_REC); }   // once a minute (or if a stall filled the buffer)
  }

  if (DM.on) demoService(millis());                 // [FW-DEMO] replay warm-up slices / one simulated minute per step
  CP(CP_L_HGBLE);
  hgBleService();                                   // CMD queue, STATUS notify, DEBUG stream
  CP(CP_L_VBAT);
  // battery every 10 s; low-battery mode with hysteresis
  if ((int32_t)(now - nextVbat) >= 0) {
    nextVbat = now + 10000;
    // 0.9.15 (plan A-14): never sampled while the motor runs or < 2 s after (a sag under load is not the cell), and low-battery
    // mode latches only on HG_VBAT_LOW_N (3) low readings in a row (0.9.14: one sagged sample during a buzz latched it)
    bool chg = charging(), buzz = recentlyBuzzed();
    float v = buzz ? NAN : readVbat();
    if (v == v) vbat = v;
    int vs = hg_vbat_step(&vbatF, v, buzz, chg, lowBatMode, VBAT_PPG_OFF);
    if (vs == HG_VBAT_SKIP) nextVbat = now + 1000;   // try again in 1 s
    if (vs == HG_VBAT_ENTER_LOW) {
      lowBatMode = true; ppgEnable(false); rawStop("low battery");
      evLog("LOWBAT ON t_ms=%lu vbat=%.3f", (unsigned long)now, vbat);
      screenWake(5000);
    } else if (lowBatMode && (chg || (vbat == vbat && vbat >= VBAT_RESUME))) {
      lowBatMode = false; if (hasPpg) { ppgEnable(true); ppgSetRed(false); }
      evLog("LOWBAT OFF t_ms=%lu vbat=%.3f chg=%d", (unsigned long)now, vbat, chg);
    }
    if (bleOn) blebas.write(batteryPct(vbat));
    pofPoll();
  }

  CP(CP_L_PROBE);
  // re-probe sensors that went missing (loose Qwiic plug), once a minute
  if ((int32_t)(now - nextProbe) >= 0) {
    nextProbe = now + 60000;
    if (!i2cLinesHigh()) { I2cLock l; hg_i2c_recover(); }   // SDA/SCL held low: TWIM off, 9-clock clear, TWIM on (T6a n4)
    if (i2cLinesHigh()) {
      for (int d = 0; d < DEV_N; d++) if (!*devFlag(d) && !(d == DEV_DRV && uiTaskOn) && probeDev(d)) {   // 0.9.17: hgui re-inits the motor on demand
        *devFlag(d) = true; devFails[d] = 0;
        if (d == DEV_PPG) ppgEnable(!lowBatMode);
        evLog("SENSOR BACK %s t_ms=%lu", DEV_NAME[d], (unsigned long)now);
      }
    }
    static bool quickCleared = false;              // 10 min of uptime = not a boot loop (one boot.bin write)
    if (!quickCleared && now >= 10u * 60u * 1000u && !wrBusy) {   // 0.9.14: never while the writer works (bootSave is a write)
      quickCleared = true;
      if (fsState == FS_OK && bootf.quick_boots) { bootf.quick_boots = 0; bootSave(); flashSleep(); }
      guardCount = 0; guardPrevFid = 0; NI.mk.gc = 0; NI.mk.gfid = 0;   // 10 min up = the guard-reset chain is over (RAM copy too)
      if (hg_heal_stable(&HS, fsState == FS_OK)) { healSave(); evLog("FS_HEAL stable t_ms=%lu: streak cleared", (unsigned long)now); }
      if (fsQuiet) {                               // FS-HEAL quiet boot over: logging resumes (a new s-file), held events written now
        fsQuiet = false;
        evLog("FS_HEAL quiet end t_ms=%lu dropped_records=%lu events=%s", (unsigned long)now, (unsigned long)quietDroppedRecs, evPath);
        if (sfileAtQuietEnd) { sfileAtQuietEnd = false; wantNewFile = true; }   // the writer starts it
        flushAll();
      }
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

  if (liveDemo && (int32_t)(now - liveNext) >= 0) liveService(now);   // [FLASH-EASY] LIVE demo, 1 Hz
  CP(CP_L_SCREEN);
  // screen
  if (screenOn) {
    if (demoScreenHold()) screenOffAt = now + SCREEN_ON_MS;   // [REPLAY-SCREEN] on for the whole replay; sleeps SCREEN_ON_MS after `#R end` / stop
    if ((int32_t)(now - screenOffAt) >= 0 && !motorBusy && !uiAlert() && !uiToastHold && !flashUntil) screenSleep();   // 0.9.6: not under a held toast
    else if ((int32_t)(now - nextDraw) >= 0) { nextDraw = now + 1000; uiDraw(false); }
  }

  CP(CP_L_END);
  bgService(now);                                   // 0.9.16: HEALTHY at 60 s, STABLE at 10 min
  if (NI.esc_done && now > 20000u) NI.esc_done = 0;   // the escape-format boot got going: the escape is allowed again
  delay(10);  // FreeRTOS tickless idle -> System ON sleep between passes
}
