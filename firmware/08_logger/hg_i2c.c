/* Heat Guardian 08_logger: bounded I2C master on TWIM0. See hg_i2c.h. */
#include "hg_nofastmath.h"   /* FIRST: the core builds with -Ofast; NaN must stay NaN */
#include "hg_i2c.h"
#include <string.h>
#ifdef HG_HOST
#include "mock_twim.h"          /* fw/tools: a struct with the TWIM register names */
#else
#include "nrf.h"
#endif

hg_i2c_stats_t hg_i2c_stats;
static uint32_t s_scl, s_sda;
static uint8_t s_tx[HG_I2C_MAX], s_rx[HG_I2C_MAX];   /* EasyDMA needs RAM buffers */

static void twim_enable(void)
{
  NRF_TWIM0->ENABLE = 0;
  NRF_TWIM0->PSEL.SCL = s_scl;
  NRF_TWIM0->PSEL.SDA = s_sda;
  NRF_TWIM0->FREQUENCY = TWIM_FREQUENCY_FREQUENCY_K100;
  NRF_TWIM0->SHORTS = 0;
  NRF_TWIM0->INTENCLR = 0xFFFFFFFFu;     /* polled, no IRQ */
  NRF_TWIM0->ENABLE = TWIM_ENABLE_ENABLE_Enabled << TWIM_ENABLE_ENABLE_Pos;
}

void hg_i2c_begin(uint32_t scl_pin, uint32_t sda_pin)
{
  s_scl = scl_pin; s_sda = sda_pin;
  memset(&hg_i2c_stats, 0, sizeof hg_i2c_stats);
  twim_enable();
}

void hg_i2c_recover(void)
{
  NRF_TWIM0->ENABLE = 0;          /* while enabled, TWIM owns the pins and GPIO toggling never reaches them */
  hg_i2c_bus_clear();
  hg_i2c_stats.bus_clears++;
  twim_enable();
}

static void clear_events(void)
{
  NRF_TWIM0->EVENTS_STOPPED = 0; NRF_TWIM0->EVENTS_ERROR = 0;
  NRF_TWIM0->EVENTS_LASTTX = 0; NRF_TWIM0->EVENTS_LASTRX = 0;
  NRF_TWIM0->ERRORSRC = NRF_TWIM0->ERRORSRC;    /* write 1 to clear */
}

/* wait for STOPPED with a deadline; on ERROR trigger STOP (the TWIM does not stop by itself) */
static int wait_done(uint32_t t0, uint32_t budget_us)
{
  int err = 0;
  for (;;) {
    hg_i2c_poll_hook();
    if (NRF_TWIM0->EVENTS_ERROR && !err) { err = 1; NRF_TWIM0->EVENTS_ERROR = 0; NRF_TWIM0->TASKS_STOP = 1; }
    if (NRF_TWIM0->EVENTS_STOPPED) break;
    if ((uint32_t)(hg_i2c_micros() - t0) > budget_us) {
      /* hung: SCL or SDA held low. Stop, give it 1 ms, then reset the peripheral and clear the bus. */
      NRF_TWIM0->TASKS_STOP = 1;
      uint32_t t1 = hg_i2c_micros();
      while (!NRF_TWIM0->EVENTS_STOPPED && (uint32_t)(hg_i2c_micros() - t1) < 1000u) hg_i2c_poll_hook();
      NRF_TWIM0->ENABLE = 0;
      hg_i2c_bus_clear();
      hg_i2c_stats.bus_clears++;
      twim_enable();
      hg_i2c_stats.timeouts++;
      return HG_I2C_TIMEOUT;
    }
  }
  NRF_TWIM0->SHORTS = 0;
  uint32_t src = NRF_TWIM0->ERRORSRC;
  NRF_TWIM0->ERRORSRC = src;
  if (err || src) { hg_i2c_stats.nack++; return HG_I2C_NACK; }
  hg_i2c_stats.ok++;
  return HG_I2C_OK;
}

static int xfer(uint8_t addr, const uint8_t *tx, uint8_t ntx, uint8_t *rx, uint8_t nrx)
{
  if (ntx > HG_I2C_MAX || nrx > HG_I2C_MAX || (ntx == 0 && nrx == 0)) return HG_I2C_ARG;
  if (ntx) memcpy(s_tx, tx, ntx);
  /* 100 kHz = ~90 us per byte; budget 3 ms + 200 us per byte (a 60-byte FIFO read: 15.6 ms) */
  uint32_t budget = 3000u + 200u * (uint32_t)(ntx + nrx + 1);
  uint32_t t0 = hg_i2c_micros();
  clear_events();
  NRF_TWIM0->ADDRESS = addr;
  NRF_TWIM0->TXD.PTR = (uint32_t)(uintptr_t)s_tx; NRF_TWIM0->TXD.MAXCNT = ntx;
  NRF_TWIM0->RXD.PTR = (uint32_t)(uintptr_t)s_rx; NRF_TWIM0->RXD.MAXCNT = nrx;
  if (ntx && nrx) {
    NRF_TWIM0->SHORTS = TWIM_SHORTS_LASTTX_STARTRX_Msk | TWIM_SHORTS_LASTRX_STOP_Msk;
    NRF_TWIM0->TASKS_STARTTX = 1;
  } else if (ntx) {
    NRF_TWIM0->SHORTS = TWIM_SHORTS_LASTTX_STOP_Msk;
    NRF_TWIM0->TASKS_STARTTX = 1;
  } else {
    NRF_TWIM0->SHORTS = TWIM_SHORTS_LASTRX_STOP_Msk;
    NRF_TWIM0->TASKS_STARTRX = 1;
  }
  int rc = wait_done(t0, budget);
  hg_i2c_stats.last_us = hg_i2c_micros() - t0;
  if (rc == HG_I2C_OK && nrx) {
    if (NRF_TWIM0->RXD.AMOUNT != nrx) { hg_i2c_stats.nack++; hg_i2c_stats.ok--; return HG_I2C_NACK; }
    memcpy(rx, s_rx, nrx);
  }
  return rc;
}

int hg_i2c_write(uint8_t addr, const uint8_t *tx, uint8_t ntx) { return xfer(addr, tx, ntx, 0, 0); }
int hg_i2c_read(uint8_t addr, uint8_t *rx, uint8_t nrx) { return xfer(addr, 0, 0, rx, nrx); }
int hg_i2c_write_read(uint8_t addr, const uint8_t *tx, uint8_t ntx, uint8_t *rx, uint8_t nrx) { return xfer(addr, tx, ntx, rx, nrx); }
