// =====================================================================
// Heat Guardian R4 PoC 04: hardware watchdog (NRF_WDT) for a demo device
// ---------------------------------------------------------------------
// The nRF52840 WDT runs from the 32.768 kHz LFCLK, keeps running in System ON
// sleep (and, with SLEEP=1, while the CPU sleeps), cannot be stopped once
// started, and a timeout resets the whole chip (nRF52840 PS v1.x §6.36).
// The SoftDevice does not touch the WDT, so the app owns it.
//
// Pattern: start it at the end of setup() with a timeout that is a few times
// the longest honest loop (here 8 s), and reload ("feed") it ONLY from the main
// loop after every subsystem reported healthy. Never feed it from a timer ISR:
// that defeats the purpose.
// =====================================================================
#include <Adafruit_TinyUSB.h>
#include <nrf_wdt.h>

static void wdtStart(uint32_t timeout_ms) {
  NRF_WDT->CONFIG = (WDT_CONFIG_HALT_Pause << WDT_CONFIG_HALT_Pos) |   // pause when a debugger halts the CPU
                    (WDT_CONFIG_SLEEP_Run << WDT_CONFIG_SLEEP_Pos);    // keep counting in sleep (we WANT a hung sleep to reset)
  NRF_WDT->CRV = (uint32_t)(((uint64_t)timeout_ms * 32768u) / 1000u) - 1u;  // CRV in LFCLK ticks
  NRF_WDT->RREN = WDT_RREN_RR0_Msk;                                     // one reload register
  NRF_WDT->TASKS_START = 1;
}
static inline void wdtFeed(void) { NRF_WDT->RR[0] = WDT_RR_RR_Reload; }  // 0x6E524635

static bool resetWasWatchdog;

void setup() {
  // Read and clear the reset reason FIRST, before anything else touches it.
  uint32_t rr = NRF_POWER->RESETREAS;
  NRF_POWER->RESETREAS = 0xFFFFFFFF;          // write 1 to clear
  resetWasWatchdog = rr & POWER_RESETREAS_DOG_Msk;

  Serial.begin(115200);
  while (!Serial && millis() < 3000) delay(10);
  Serial.println("Heat Guardian R4 PoC 04: watchdog");
  Serial.print("RESETREAS=0x"); Serial.print(rr, HEX);
  if (resetWasWatchdog) Serial.println("  <- the WATCHDOG reset us (log this to InternalFS in the product)");
  else if (rr & POWER_RESETREAS_RESETPIN_Msk) Serial.println("  <- reset pin");
  else if (rr & POWER_RESETREAS_SREQ_Msk) Serial.println("  <- software reset (USB upload)");
  else Serial.println("  <- power-on / brown-out (RESETREAS=0)");

  wdtStart(8000);                              // 8 s: longest honest loop is ~1 s
  Serial.println("WDT started: 8 s. Type 'h' to simulate a hang.");
}

void loop() {
  static uint32_t n = 0;
  // ... sensors, inference, screen, BLE ...
  if (Serial.available() && Serial.read() == 'h') {
    Serial.println("hanging on purpose; expect a reset in ~8 s");
    Serial.flush();
    while (true) { }                           // the WDT will fire
  }
  wdtFeed();                                   // only here, once per healthy loop
  if (++n % 1000 == 0) { Serial.print("alive "); Serial.println(millis() / 1000); }
  delay(1);
}
