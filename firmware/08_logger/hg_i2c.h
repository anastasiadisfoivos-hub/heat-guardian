/* Heat Guardian 08_logger: bounded I2C master on TWIM0 (replaces Wire, T6a finding M2).
 * Wire_nRF52.cpp waits for TWIM events in unbounded while() loops, so a sensor holding SCL or SDA
 * low (a half-in Qwiic plug, SETUP.md) hangs the loop until the watchdog resets the board, and then
 * hangs setup() again. Every transfer here has a deadline; on a timeout the transfer is stopped, the
 * peripheral is disabled, the bus is cleared (9 SCL pulses + STOP) and the call returns HG_I2C_TIMEOUT.
 * Plain C so the timeout logic is host-tested with a mock peripheral (fw/tools/test_i2c.c).
 */
#ifndef HG_I2C_H
#define HG_I2C_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

enum { HG_I2C_OK = 0, HG_I2C_NACK = 1, HG_I2C_TIMEOUT = 2, HG_I2C_ARG = 3 };
#define HG_I2C_MAX 64

typedef struct {
  uint32_t ok, nack, timeouts, bus_clears;
  uint32_t last_us;           /* duration of the last transfer */
} hg_i2c_stats_t;
extern hg_i2c_stats_t hg_i2c_stats;

/* provided by the platform (sketch on the band, the test on the host) */
uint32_t hg_i2c_micros(void);
void     hg_i2c_bus_clear(void);  /* bit-bang 9 SCL pulses + STOP, then hand the pins back to TWIM */
void     hg_i2c_poll_hook(void);  /* called while waiting; no-op on the band, the mock on the host */

void hg_i2c_begin(uint32_t scl_pin, uint32_t sda_pin);   /* pins already configured by the caller */
void hg_i2c_recover(void);   /* TWIM off, bus clear, TWIM on: for a bus found stuck between transfers */
int  hg_i2c_write(uint8_t addr, const uint8_t *tx, uint8_t ntx);
int  hg_i2c_read(uint8_t addr, uint8_t *rx, uint8_t nrx);
int  hg_i2c_write_read(uint8_t addr, const uint8_t *tx, uint8_t ntx, uint8_t *rx, uint8_t nrx);

#ifdef __cplusplus
}
#endif
#endif
