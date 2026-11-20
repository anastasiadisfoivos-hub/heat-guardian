/* [FW-DEMO] 09_guardian 0.9.16-demo: heat-episode REPLAY (console `replay [s]` / `replay stop`). Plain C, host-tested
 * (fw/tools/test_demo.c, run_host_tests.sh 8i).
 *
 * Only the INPUT is simulated: a per-minute trace of what the band's sensors would read during a simulated heat episode
 * (sim/velders, fw/tools/make_demo_trace.py -> hg_demo_trace.h). This file turns it into the same 1 Hz hg_fw_sec_t the
 * sensing layer gives hg_fw_second(); the frozen guardian, the alert layer and the planner then decide everything.
 *
 * Replay = a fresh guardian state (profile 75 y / female / BMI 26 / no medicines, default twin), a QUIET warm-up (HG_DEMO_WARM
 * minutes of a calm day/night at 25 C, the same recipe as the staged scenes in test_alerts.c, so the guardian's baselines are
 * armed as on a band worn for a while; then the trace's hidden pre-roll, the simulated morning), then the visible trace.
 * The warm-up and every replayed minute use a simulated clock (minute of day, day 20000, 60 000 ms per minute), so the
 * band's output is a pure function of the trace: the host test prints exactly what the band will show.
 */
#ifndef HG_FW_DEMO_H
#define HG_FW_DEMO_H
#include <stdint.h>
#include "hg_fw.h"
#include "hg_fw_alert.h"
#include "hg_fw_eco.h"
#ifdef __cplusplus
extern "C" {
#endif

typedef struct { int16_t t1, t2, ta, rh, hr, pi, astd, z, core; uint8_t q; } hg_demo_row_t;
#define HG_DEMO_NOHR   (-32768)
#ifndef HG_DEMO_WARM
#define HG_DEMO_WARM   1440       /* calm warm-up minutes before the pre-roll (fw/tools/test_demo.c explains the choice) */
#endif
#define HG_DEMO_DAY0   20000      /* simulated local day of the episode */
#define HG_DEMO_SEED   12345u     /* per-second noise generator seed */

extern const hg_demo_row_t *const hg_demo_trace;
extern const uint16_t hg_demo_n;          /* visible replayed minutes (k = 0 .. n-1) */
extern const uint16_t hg_demo_pre;        /* hidden pre-roll rows (k = -pre .. -1) */
int32_t hg_demo_first(void);              /* first warm-up minute k = -(HG_DEMO_WARM + pre) */
extern const uint16_t hg_demo_start_mod;  /* local minute of day of trace row 0 */

/* minute k of the replay: k < -pre = calm warm-up, -pre .. -1 = hidden pre-roll, 0 .. n-1 = visible trace */
uint16_t hg_demo_mod(int32_t k);
int32_t  hg_demo_day(int32_t k);
uint32_t hg_demo_ms(int32_t k);           /* simulated millis() at the start of minute k (first warm-up minute = 0 ms) */
/* second `sec` (0..59) of minute k as the sensing layer would give it; *rng advances (both host and band call this in the
 * same order, so the noise is the same); ppg_on = hg_fw_ppg_on(fw, sec), as on the band */
void hg_demo_sec(int32_t k, uint8_t sec, uint8_t ppg_on, uint32_t *rng, hg_fw_sec_t *q);
const hg_demo_row_t *hg_demo_row(int32_t k);   /* clamped to the trace (k < -pre -> the first pre-roll row) */
/* the simulated minute context (no charger, 3.9 V, BLE bucket 2, no forecast) */
void hg_demo_ctx(int32_t k, hg_fw_ctx_t *c);

/* one QUIET warm-up minute: 60 seconds -> hg_fw_minute -> hg_al_minute -> planner, nothing else (no log, no screen,
 * no haptic, no event, no twin save). Used by the band (warm-up) and by the host test (warm-up). */
typedef struct { hg_fw_t *fw; hg_guardian_t *g; hg2_twin_t *tw; hg_twin_acc_t *acc; hg_al_t *al; hg_plan_t *pl; uint32_t rng; } hg_demo_st_t;
/* the fresh demo state: default twin, guardian with the demo profile (75 y, female, BMI 26, no medicines), glue, alert
 * layer, planner; s->rng = HG_DEMO_SEED. The pointers in s must be set. */
void hg_demo_init(hg_demo_st_t *s);
void hg_demo_feed_minute(hg_demo_st_t *s, int32_t k);    /* the 60 seconds of minute k only */
void hg_demo_quiet_minute(hg_demo_st_t *s, int32_t k);   /* feed + the minute */
/* [DEMO-NORESP] 0.9.17-demo-b7n: `replay noresp [s]` = the same simulated episode, but she never presses (the band ignores
 * short presses while it runs), so the real ladder takes its own no-press path: reminder -> 10-min repeat -> LD_NOTE 2
 * "no response" (the phone's family SMS). Nothing here decides: the frozen engine and hg_fw_ladder.c do.
 * Every ladder EVENTS frame (types 17-21) sent during ANY replay (`replay` and `replay noresp`) carries the SIMULATION marker in frame byte 18
 * (x[7] = HG_DEMO_X7_SIM; the ladder leaves x[6..7] at 0), so a phone can tell a replayed escalation from a real one. */
#define HG_DEMO_X7_SIM 0xD5u
/* the Virtual Elder of the embedded trace (hg_demo_trace.h header: velders draw_one person pid 90862, seed 20351974; b7s: 90416;
 * run_host_tests 8i checks the header still says so) */
#define HG_DEMO_ELDER "velders-pid90862"
void hg_demo_mark_x(uint8_t type, uint8_t x[8]);   /* ladder types 17-21: x[7] = HG_DEMO_X7_SIM; other types untouched */
/* the planner input the band builds in demo mode (planIn() with no forecast, seed, day plan or console overrides) */
void hg_demo_plan_in(const hg_demo_st_t *s, int32_t k, hg_plan_in_t *in);

#ifdef __cplusplus
}
#endif
#endif
