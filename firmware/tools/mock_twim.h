/* Host mock of the nRF52840 TWIM register block, just the fields hg_i2c.c uses (fw/tools/test_i2c.c). */
#include <stdint.h>
typedef struct {
  volatile uint32_t TASKS_STARTRX, TASKS_STARTTX, TASKS_STOP;
  volatile uint32_t EVENTS_STOPPED, EVENTS_ERROR, EVENTS_LASTTX, EVENTS_LASTRX;
  volatile uint32_t SHORTS, INTENCLR, ERRORSRC, ENABLE, FREQUENCY, ADDRESS;
  struct { volatile uint32_t SCL, SDA; } PSEL;
  struct { volatile uint64_t PTR; volatile uint32_t MAXCNT, AMOUNT; } RXD, TXD;
} mock_twim_t;
extern mock_twim_t mock_twim0;
#define NRF_TWIM0 (&mock_twim0)
#define TWIM_FREQUENCY_FREQUENCY_K100 0x01980000UL
#define TWIM_ENABLE_ENABLE_Enabled 6UL
#define TWIM_ENABLE_ENABLE_Pos 0
#define TWIM_SHORTS_LASTTX_STARTRX_Msk (1UL << 7)
#define TWIM_SHORTS_LASTTX_STOP_Msk (1UL << 9)
#define TWIM_SHORTS_LASTRX_STOP_Msk (1UL << 12)
