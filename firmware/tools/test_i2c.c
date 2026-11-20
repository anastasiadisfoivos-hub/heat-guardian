/* M2 regression test: every I2C transfer returns within its deadline, even when the bus hangs.
 *   gcc -std=c99 -Wall -Wextra -Werror -DHG_HOST -I. -I../08_logger test_i2c.c ../08_logger/hg_i2c.c -o /tmp/test_i2c && /tmp/test_i2c
 * A mock TWIM answers in three ways: normal (STOPPED after a few polls), NACK (ERROR, then STOPPED
 * once STOP is triggered), HUNG (SCL held low: never any event, as with a half-in Qwiic plug).
 * Part 1 runs the wait loop of the core's Wire_nRF52.cpp (while (!EVENTS_STOPPED && !EVENTS_ERROR))
 * on the HUNG bus, with a safety cap: it never returns by itself = the pre-fix behaviour (FAIL).
 * Part 2 runs hg_i2c.c: HUNG returns HG_I2C_TIMEOUT within its budget and clears the bus; the
 * next transfer on a healthy bus succeeds.
 */
#include <stdio.h>
#include <string.h>
#include "hg_i2c.h"
#include "mock_twim.h"

mock_twim_t mock_twim0;
static uint32_t fake_us = 0;
static int mode = 0, polls = 0, clears = 0, enable_at_clear = -1;   /* 0 normal, 1 nack, 2 hung */
uint32_t hg_i2c_micros(void) { return fake_us; }
void hg_i2c_bus_clear(void) { clears++; enable_at_clear = (int)mock_twim0.ENABLE; }
void hg_i2c_poll_hook(void)
{
  fake_us += 10; polls++;
  if (mode == 0 && polls == 5) { mock_twim0.RXD.AMOUNT = mock_twim0.RXD.MAXCNT; mock_twim0.EVENTS_STOPPED = 1; }
  if (mode == 1 && polls == 3) { mock_twim0.EVENTS_ERROR = 1; mock_twim0.ERRORSRC = 2; }
  if (mode == 1 && mock_twim0.TASKS_STOP) mock_twim0.EVENTS_STOPPED = 1;
}
static void arm(int m) { mode = m; polls = 0; memset(&mock_twim0, 0, sizeof mock_twim0); }

int main(void)
{
  int fails = 0;
  /* part 1: the core's Wire wait loop on a hung bus */
  arm(2); long iters = 0;
  while (!mock_twim0.EVENTS_STOPPED && !mock_twim0.EVENTS_ERROR) { hg_i2c_poll_hook(); if (++iters > 10000000L) break; }
  printf("pre-fix (Wire_nRF52.cpp wait loop), hung bus: %s after %ld polls (%.1f s of fake time, would never return)\n",
         iters > 10000000L ? "STILL WAITING" : "returned", iters, fake_us / 1e6);

  /* part 2: hg_i2c */
  hg_i2c_begin(5, 4);
  uint8_t tx[2] = {0x0F, 0}, rx[2];
  arm(0); fake_us = 0; int rc = hg_i2c_write_read(0x48, tx, 1, rx, 2);
  printf("normal transfer: rc=%d (expect 0)\n", rc); fails += rc != HG_I2C_OK;
  arm(1); fake_us = 0; rc = hg_i2c_write(0x49, tx, 1);
  printf("NACK: rc=%d (expect 1), STOP triggered=%u\n", rc, mock_twim0.TASKS_STOP); fails += rc != HG_I2C_NACK || !mock_twim0.TASKS_STOP;
  arm(2); fake_us = 0; rc = hg_i2c_write_read(0x57, tx, 1, rx, 60);
  uint32_t budget = 3000u + 200u * 62u;
  printf("hung bus: rc=%d (expect 2) after %u us (budget %u + 1000 stop wait), bus clears=%d\n", rc, fake_us, budget, clears);
  fails += rc != HG_I2C_TIMEOUT || fake_us > budget + 1100u || clears != 1 || mock_twim0.ENABLE != 6;
  arm(0); fake_us = 0; rc = hg_i2c_read(0x70, rx, 2);
  printf("next transfer after the clear: rc=%d (expect 0)\n", rc); fails += rc != HG_I2C_OK;
  printf("stats ok=%u nack=%u timeouts=%u\n", hg_i2c_stats.ok, hg_i2c_stats.nack, hg_i2c_stats.timeouts);
  fails += hg_i2c_stats.ok != 2 || hg_i2c_stats.nack != 1 || hg_i2c_stats.timeouts != 1;
  /* n4: recovering a bus found stuck between transfers must disable TWIM during the clear */
  mock_twim0.ENABLE = 6; enable_at_clear = -1; int c0 = clears;
  hg_i2c_recover();
  printf("recover: bus clear ran with TWIM ENABLE=%d (expect 0), re-enabled=%u\n", enable_at_clear, mock_twim0.ENABLE);
  fails += clears != c0 + 1 || enable_at_clear != 0 || mock_twim0.ENABLE != 6;
  printf("%s\n", fails ? "TEST_I2C: FAIL" : "TEST_I2C: PASS");
  return fails ? 1 : 0;
}
