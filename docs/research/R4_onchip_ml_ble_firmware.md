# R4 — On-chip ML, BLE and firmware feasibility (Seeed XIAO nRF52840, Seeed nRF52 core 1.1.13)

Research agent R4, 12 Nov 2026. Everything marked **MEASURED** was compiled in this workspace with
`arduino-cli compile --fqbn Seeeduino:nrf52:xiaonRF52840` (same core and libraries as the bench
tests) or run on the host with gcc. Nothing was run on the board: the cycle counts are estimates
from the generated ARM assembly, with the DWT cycle counter wired into the sketches so Foivos can
print the real numbers in one upload. **SIMULATION** marks results from synthetic signals.

Proof-of-concept folders (all compile; none touch 00–07):

| Folder | What it proves | Flash B | Static RAM B |
|---|---|---:|---:|
| `/home/claude/hg_ai/fw/poc_00_minimal` | baseline: USB Serial only | 44,940 | 7,240 |
| `/home/claude/hg_ai/fw/poc_01_ble_cost` | 07_all_parts + Bluefruit BLE UART + battery service + advertising | 180,768 | 15,016 |
| `/home/claude/hg_ai/fw/poc_02_nn` | plain-C MLP + 5-member ensemble + int8 member + CRC, host-verified against numpy | 77,924 | 7,240 |
| `/home/claude/hg_ai/fw/poc_03_storage` | InternalFS (LittleFS) save/load of a CRC-checked Body Twin file | 71,688 | 11,596 |
| `/home/claude/hg_ai/fw/poc_04_wdt` | NRF_WDT watchdog + reset-reason logging | 43,412 | 7,152 |
| `/home/claude/hg_ai/fw/poc_05_hr` | streaming wrist HR detector with quality gate, host-tested on synthetic PPG | 50,860 | 7,848 |
| `/home/claude/hg_ai/fw/poc_06_everything` | **all of the above in one build** (07 + MAX30102 + BLE + NN + storage + WDT + HR) | **216,312 (26.7 %)** | **15,548** |

Reference: 07_all_parts re-compiled here = **107,968 B flash / 8,080 B RAM** (matches the brief).
"Maximum is 811,008 bytes" is the application region 0x26000–0xED000 of the 1 MB flash: MBR + S140
SoftDevice 7.3.0 occupy the first 152 KB, LittleFS 28 KB at 0xED000, bootloader 48 KB at 0xF4000
(linker script `nrf52840_s140_v7.ld` and `InternalFileSystem.cpp` in the core). RAM: the app gets
237,568 B of the 256 KB; the SoftDevice reserves the first 24 KB (RAM origin 0x20006000).

---

## Part A

### A1. Flash/RAM budget: what BLE costs (MEASURED)

poc_01 is a verbatim copy of 07_all_parts with four things added: `#include <bluefruit.h>`,
`BLEUart` (Nordic UART Service), `BLEBas` (Battery Service 0x180F), advertising (20 ms fast for
30 s, then 1000 ms), and one `bleuart.write()` of the sensor line per second.

| Build | Flash | RAM (static) |
|---|---:|---:|
| 07_all_parts | 107,968 | 8,080 |
| 07 + BLE (poc_01) | 180,768 | 15,016 |
| **BLE cost** | **+72,800 B (9.0 % of 811 KB)** | **+6,936 B** |

Where the 72.8 KB goes (linker map of poc_06, `/tmp/.../mapsize.py` output): Bluefruit52Lib +
nRFCrypto 44.4 KB, **LittleFS + InternalFS 25.5 KB (Bluefruit pulls it in for bond storage even if
you never pair)**, the rest is libc/FreeRTOS code that the BLE task newly references. Consequence
for A3: once BLE is in the build, the filesystem is free.

RAM beyond the static 6.9 KB: Bluefruit creates two FreeRTOS tasks from the heap, `BLE`
(`CFG_BLE_TASK_STACKSIZE` = 256×5 words = 5,120 B) and `SOC` (200 words = 800 B)
(`Bluefruit52Lib/src/bluefruit.cpp` lines 44–49). Budget ~13 KB total for BLE. The SoftDevice's own
24 KB is outside the app region and already subtracted from the 237,568 figure.

Config used (keeps RAM small): `Bluefruit.configPrphBandwidth(BANDWIDTH_LOW)` (ATT MTU 23, minimum
event length), `Bluefruit.begin(1, 0)` (one peripheral link, no central), `setTxPower(0)`.

### A2. Tiny NN inference in plain C on the Cortex-M4F (MEASURED size, host-verified maths)

Files: `/home/claude/hg_ai/fw/poc_02_nn/hg_nn.c`, `hg_nn.h`, generated `hg_weights.c/.h`,
`export_weights.py`, `host/host_test.c`. Network: 24 → 32 → 16 → 3, ReLU, float32; ensemble of 5.

**Sizes (MEASURED with arm-none-eabi-size on the compiled objects):**

| Item | Bytes | Note |
|---|---:|---|
| MACs per member | 1,328 | 24·32 + 32·16 + 16·3 |
| Parameters per member | 1,379 | + biases 32+16+3 |
| float32 weights, 1 member | 5,516 | |
| **float32 weights, 5-member ensemble** | **27,580** (+120 B member table) | `.rodata` in flash, 0 B RAM |
| int8 weights + int32 biases, 1 member | 1,532 | 3.6× smaller |
| int8 ensemble (extrapolated) | 7,660 | |
| inference code (forward 1,308 + ensemble 400 + int8 672 + CRC 628) | 3,008 | `.text` |
| **NN total in the build (poc_02 − poc_00)** | **32,984 B flash, 0 B static RAM** | stack: 192 B per forward, +60 B ensemble |

**Correctness (MEASURED on host):** `gcc -O2 -I. -Ihost host/host_test.c hg_nn.c hg_weights.c -lm`
→ C forward == numpy forward to ≤ 3.6e-7 on 4 test vectors, ensemble mean/std match, CRC-32 of the
flash weights matches the exporter's (0xB280AD57). The int8 member (per-tensor symmetric weights,
per-layer activation scales from a 256-sample calibration set, Q0.31 requantisation like
TFLite-Micro) lands within 0.03–0.15 of the float output on outputs of magnitude ~1, i.e. 3–10 %
error with random weights. Two lessons recorded in the exporter: (1) a naive fixed activation grid
saturated (errors 0.4–0.8) — int8 needs calibrated per-layer scales; (2) `static const` weight
arrays in a header included by two translation units were **emitted twice** (27.6 → 55 KB) — the
header must declare `extern`, one generated `.c` defines.

**Cycles per inference (ESTIMATE from the generated assembly, to be confirmed with the DWT counter
that poc_02 prints every second):** GCC with `-mfpu=fpv4-sp-d16 -mfloat-abi=hard` (the core's
`platform.txt`) fully unrolled layer 1, keeping all 24 inputs in s0–s25 and emitting one
`vldr` + one `vfma.f32` per MAC with the accumulator in s15 (disassembly of `hg_nn.c.o`). On the
Cortex-M4 FPU `VMUL`/`VADD`/`VLDR` issue in 1 cycle but `VFMA`/`VMLA` take 3 cycles, and "arithmetic
instructions take one cycle longer if the next instruction consumes their result" (ARM Cortex-M4
TRM DDI0439B §7.2.3, mirrored at
[cse.scu.edu Cortex-M4 Instruction Timing](https://www.cse.scu.edu/~dlewis/book3/docs/Cortex-M4%20Instruction%20Timing.pdf);
the "vfma takes 3 cycles" statement is also quoted in the
[ARM community thread 46511](https://community.arm.com/support-forums/f/architectures-and-processors-forum/46511/vfma-instruction-timings-on-arm-cortex-m4)).
So the brief's "one FMAC ≈ 1 cycle" is the *throughput of independent* FMAs; our dependent
accumulator chain costs ~4–5 cycles per MAC.

| | MACs | cycles @4–5/MAC + overhead | time @64 MHz |
|---|---:|---:|---:|
| 1 member | 1,328 | ~5.7k–7.0k | **90–110 µs** |
| 5-member ensemble | 6,640 | ~29k–35k | **0.45–0.55 ms** |
| idealised 1 MAC/cycle | 6,640 | 6,640 | 0.10 ms |

Two caveats that only the board can settle: the weights are read from flash over the data bus
(the nRF52 instruction cache does not cover data; "executing code from flash will have a wait state
penalty on the nRF52 series", nRF52840 PS v1.1 §2 and §4.3.8), and the core leaves `ICACHECNF`
disabled. If the printed number exceeds 1 ms: (a) enable the I-cache
(`NRF_NVMC->ICACHECNF = NVMC_ICACHECNF_CACHEEN_Enabled << NVMC_ICACHECNF_CACHEEN_Pos`), (b) split
the dot product over two accumulators (breaks the dependency chain, ~2× faster), (c) copy the
27.6 KB of weights into RAM at boot (zero wait states; we have 220 KB spare). The int8 path does
**not** buy time on this chip in plain C (`ldrsb`+`mla` ≈ same cycles; SIMD `SMLAD` would need
CMSIS-NN-style packing); it buys flash only.

**TFLite Micro: not needed.** The whole runtime we need is 3 KB of C above. What we lose by not
using TFLM/LiteRT-Micro: the operator library (conv/pool/LSTM/softmax etc. would have to be
hand-written, each ~50 lines), the flatbuffer model format (model swap without recompiling), and
the built-in quantisation tooling. What we gain: no C++ interpreter (TFLM core is 16 KB on a
Cortex-M3 per Google's docs, cited in `mcu_ml_ble.md` §3; real Arduino builds are 50–100 KB), no
tensor arena to size, no op-resolver debugging, deterministic timing, and a CRC-checked model
that the reviewer can diff against the training log. If Core Sense ends up as a GRU or a tiny 1-D
CNN, that is still 100–200 lines of the same style of C.

**Recommended weight-export format** (implemented in `export_weights.py`):
- `hg_weights.h` (generated): `#define HG_NN_IN 24 / HG_NN_H1 32 / HG_NN_H2 16 / HG_NN_OUT 3 / HG_NN_ENS 5`,
  `#define HG_NN_CRC32 0x…`, `#define HG_NN_VERSION "…"`, int8 scales/multipliers, and
  `extern const float W1_0[32][24]; extern const float b1_0[32]; …` plus
  `extern const hg_nn_member_t HG_NN_MEMBERS[HG_NN_ENS];`
- `hg_weights.c` (generated): the definitions, row-major `W[out][in]`, `%.8e` floats.
- The CRC-32 (zlib polynomial) is computed over the little-endian float32 bytes in the exporter and
  re-computed by `hg_nn_check_crc()` at boot (bitwise, no table). The band prints
  `NN r4-poc-random-42 crc OK` and the phone can read HG_NN_VERSION over BLE.
- `host/hg_test_vectors.h` + `host_test.c`: 4 inputs with expected outputs, so `make test` proves
  C == Python before every upload. Add this to the code-freeze checklist (A8).
- Feature scaling (z-score means/stds) must be exported the same way, as `HG_NN_X_MEAN[24]`,
  `HG_NN_X_STD[24]`, and the output de-normalisation; the Core Sense agent owns those names.

The C file (`hg_nn.c`, verbatim):

```c
/* Heat Guardian R4 PoC: plain-C MLP inference. See hg_nn.h. */
#include "hg_nn.h"
#include <math.h>
#include <string.h>

/* y[n_out] = relu?(W[n_out][n_in] . x + b). W is row-major, as the exporter writes it. */
static inline void dense(const float *W, const float *b, const float *x,
                         float *y, int n_in, int n_out, int relu)
{
  for (int o = 0; o < n_out; o++) {
    const float *w = W + (size_t)o * n_in;
    float acc = b[o];
    /* 4-way unrolled so the compiler emits back-to-back vfma.f32 on the M4F */
    int i = 0;
    for (; i + 4 <= n_in; i += 4) {
      acc += w[i] * x[i];
      acc += w[i + 1] * x[i + 1];
      acc += w[i + 2] * x[i + 2];
      acc += w[i + 3] * x[i + 3];
    }
    for (; i < n_in; i++) acc += w[i] * x[i];
    y[o] = (relu && acc < 0.0f) ? 0.0f : acc;
  }
}

void hg_nn_forward(const hg_nn_member_t *m, const float *x, float *y)
{
  float h1[HG_NN_H1], h2[HG_NN_H2];
  dense(m->W1, m->b1, x,  h1, HG_NN_IN, HG_NN_H1, 1);
  dense(m->W2, m->b2, h1, h2, HG_NN_H1, HG_NN_H2, 1);
  dense(m->W3, m->b3, h2, y,  HG_NN_H2, HG_NN_OUT, 0);
}

void hg_nn_ensemble(const float *x, float *mean, float *std)
{
  float ys[HG_NN_ENS][HG_NN_OUT];
  for (int k = 0; k < HG_NN_ENS; k++) hg_nn_forward(&HG_NN_MEMBERS[k], x, ys[k]);
  for (int o = 0; o < HG_NN_OUT; o++) {
    float s = 0.0f, s2 = 0.0f;
    for (int k = 0; k < HG_NN_ENS; k++) { s += ys[k][o]; s2 += ys[k][o] * ys[k][o]; }
    float mu = s / HG_NN_ENS;
    float var = s2 / HG_NN_ENS - mu * mu;
    mean[o] = mu;
    std[o]  = var > 0.0f ? sqrtf(var) : 0.0f;
  }
}

/* ---- int8 path (member 0): acc = sum(int8 w * int8 x) + b_q ; y_q = sat8((acc * M) >> (31 + S)) */
static inline int8_t requant(int32_t acc, int32_t M, int S, int relu)
{
  int64_t p = (int64_t)acc * M;                 /* smull on the M4: 1 instruction */
  int32_t r = (int32_t)(p >> (31 + S));
  if (relu && r < 0) r = 0;
  if (r > 127) r = 127;
  if (r < -128) r = -128;
  return (int8_t)r;
}
static inline void dense_i8(const int8_t *W, const int32_t *b, const int8_t *x,
                            int8_t *y, int n_in, int n_out, int32_t M, int S, int relu)
{
  for (int o = 0; o < n_out; o++) {
    const int8_t *w = W + (size_t)o * n_in;
    int32_t acc = b[o];
    for (int i = 0; i < n_in; i++) acc += (int32_t)w[i] * (int32_t)x[i];
    y[o] = requant(acc, M, S, relu);
  }
}
void hg_nn_forward_i8_0(const int8_t *x_q, int8_t *y_q)
{
  int8_t h1[HG_NN_H1], h2[HG_NN_H2];
  dense_i8(&W1q_0[0][0], b1q_0, x_q, h1, HG_NN_IN, HG_NN_H1, HG_NN_M1_0, HG_NN_S1_0, 1);
  dense_i8(&W2q_0[0][0], b2q_0, h1,  h2, HG_NN_H1, HG_NN_H2, HG_NN_M2_0, HG_NN_S2_0, 1);
  dense_i8(&W3q_0[0][0], b3q_0, h2,  y_q, HG_NN_H2, HG_NN_OUT, HG_NN_M3_0, HG_NN_S3_0, 0);
}

/* ---- CRC-32 over the weight bytes (bitwise, no table: 0 B of flash for a table) */
static uint32_t crc32_update(uint32_t crc, const void *p, size_t n)
{
  const uint8_t *b = (const uint8_t *)p;
  crc = ~crc;
  while (n--) {
    crc ^= *b++;
    for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
  }
  return ~crc;
}
int hg_nn_check_crc(void)
{
  uint32_t c = 0;
  for (int k = 0; k < HG_NN_ENS; k++) {
    const hg_nn_member_t *m = &HG_NN_MEMBERS[k];
    c = crc32_update(c, m->W1, sizeof(float) * HG_NN_H1 * HG_NN_IN);
    c = crc32_update(c, m->b1, sizeof(float) * HG_NN_H1);
    c = crc32_update(c, m->W2, sizeof(float) * HG_NN_H2 * HG_NN_H1);
    c = crc32_update(c, m->b2, sizeof(float) * HG_NN_H2);
    c = crc32_update(c, m->W3, sizeof(float) * HG_NN_OUT * HG_NN_H2);
    c = crc32_update(c, m->b3, sizeof(float) * HG_NN_OUT);
  }
  return c == HG_NN_CRC32;
}
```

### A3. Non-volatile storage for Body Twin + routine profile (MEASURED size; API read from the core)

**What the core offers.** `InternalFileSystem` (library folder is spelled `InternalFileSytem`) is
LittleFS on the chip's own flash: **28 KB at 0xED000–0xF4000 (7 pages of 4 KB), 128-byte logical
blocks**, API = `Adafruit_LittleFS` `File` (open/read/write/seek/truncate/close, `exists`, `mkdir`,
`remove`, `format`) — `InternalFileSystem.cpp`/`.h` and
`Adafruit_LittleFS_File.h` in the core. Direct NVMC is also reachable (`flash_nrf5x_write/read/erase`
in `InternalFileSytem/src/flash/flash_nrf5x.h`, and raw `sd_flash_page_erase/sd_flash_write` through
the SoftDevice), but there is no reason to use it: the FS gives you wear-levelled, power-fail-safe
files for ~0 B extra once BLE is linked.

**Flash cost:** standalone +26,748 B / +4,356 B RAM (poc_03 vs poc_00). The 4 KB RAM is the driver's
page cache (`_cache_buffer[FLASH_CACHE_SIZE]` in `flash_nrf5x.c`). **Incremental cost with BLE
present: ~0** — Bluefruit already links the same library for `/adafruit/bond_prph` (bonding.cpp
line 91), which is why poc_06 (everything) is only 35.5 KB above poc_01 (07 + BLE) although it adds
33 KB of NN plus storage, PPG, the MAX3010x driver and the watchdog.

**Minimal save/load** (poc_03; the full version has a versioned header, magic, length and CRC-32):

```cpp
#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>
using namespace Adafruit_LittleFS_Namespace;

struct __attribute__((packed)) TwinFile {
  uint32_t magic; uint16_t version, length;
  BodyTwin twin;            // 5 floats + days_learned           (22 B)
  RoutineProfile routine;   // wake/sleep per weekday, 24 h activity + outings (62 B)
  uint32_t save_count, crc32;
};                           // 102 B -> one 128 B LittleFS block

static bool twinSave(TwinFile& tf) {
  tf.magic = TWIN_MAGIC; tf.version = TWIN_VERSION; tf.length = sizeof tf; tf.save_count++;
  tf.crc32 = crc32(&tf, sizeof tf - sizeof(uint32_t));
  File f(InternalFS);
  if (!f.open("/twin.bin", FILE_O_WRITE)) return false;
  f.seek(0); f.truncate(0);                 // FILE_O_WRITE appends; make it overwrite
  size_t n = f.write((const uint8_t*)&tf, sizeof tf); f.close();
  return n == sizeof tf;
}
static bool twinLoad(TwinFile& tf) {
  File f(InternalFS);
  if (!f.open("/twin.bin", FILE_O_READ)) return false;
  size_t n = f.read((uint8_t*)&tf, sizeof tf); f.close();
  return n == sizeof tf && tf.magic == TWIN_MAGIC && tf.version == TWIN_VERSION
      && tf.crc32 == crc32(&tf, sizeof tf - sizeof(uint32_t));
}
// setup(): InternalFS.begin(); if (!twinLoad(twin)) { twinDefaults(twin); twinSave(twin); }
```

**Wear.** nRF52840 flash: **10,000 erase cycles per page**, a 32-bit word may be written twice
between erases, t_ERASEPAGE ≈ 85 ms, t_WRITE ≈ 41 µs per word (nRF52840 PS v1.1 table 4.3.10.1,
[SparkFun mirror](https://cdn.sparkfun.com/assets/d/2/6/2/6/nRF52840_PS_v1.1.pdf)). The core's
driver erases a **whole 4 KB page through `sd_flash_page_erase()` every time its one-page cache
moves** (`fal_erase` in `flash_nrf5x.c`), so one file save ≈ 2–4 page erases (data + LittleFS
metadata), and LittleFS's 128-byte "blocks" cannot spread wear below page granularity. Arithmetic:
7 pages × 10,000 = 70,000 page-erases; at 4 erases per save, **~17,500 saves**. Save once a day
after the night-time Body Twin update plus on each routine-profile change (≤ 5/day) → ~10 years.
Saving every minute (5,760 erases/day) would exhaust the region in ~12 days — never do it. The
1-minute log belongs in RAM (a 1,440 × 20 B = 29 KB ring, we have the RAM) and, if it must survive
a reset, in the 2 MB QSPI flash via the core's `ExternalFileSystem` (it is the bootloader's
UF2 drive; also the thing that must be put in deep power-down for low sleep current, A6).
Rules: never `InternalFS.format()` in product code (it erases the BLE bonds); a page erase stalls
the CPU for up to ~85 ms, so save while the MAX30102 FIFO (32 samples = 320 ms at 100 sps) can absorb
it, and never inside the 1 Hz sensor read; the SoftDevice schedules flash ops around radio events,
so a save during a BLE connection can take tens of ms longer (that is what the semaphore in
`fal_erase` waits for).

### A4. Timekeeping without GPS (read from the core; crystal from datasheets)

**What runs the clock.** The XIAO variant declares `USE_LFXO` ("Board uses 32khz crystal for LF",
`variants/Seeed_XIAO_nRF52840/variant.h` line 7) and Bluefruit hands the SoftDevice
`NRF_CLOCK_LF_SRC_XTAL` with `NRF_CLOCK_LF_ACCURACY_20_PPM` (`bluefruit.cpp` lines 293–300). FreeRTOS
ticks from **RTC1** at 1024 Hz with tickless idle (`FreeRTOSConfig.h`: `configTICK_RATE_HZ 1024`,
`configUSE_TICKLESS_IDLE 1`, `xPortSysTickHandler RTC1_IRQHandler`); the SoftDevice owns RTC0;
**RTC2 is free** (nRF52840 PS §6.22, three 24-bit RTC instances). `millis()` =
`xTaskGetTickCount() × 1000 / 1024` computed in 64 bit then truncated to `uint32_t`
(`delay.c`, `rtos.h`), so it **wraps every 2^32 ms = 49.7 days**; it keeps counting through
`delay()`/tickless sleep (System ON), and is lost only in System OFF or on reset.

**Drift.** A 32.768 kHz tuning-fork crystal is ±20 ppm at 25 °C with a parabolic temperature
coefficient of −0.034 ± 0.006 ppm/°C² around a 25 °C turnover and ±3 ppm/year aging (CTS TF32
datasheet, [ctscorp.com](https://www.ctscorp.com/Files/DataSheets/Passives/FCP/Crystals/crystals-TF32-datasheet.pdf);
Seeed does not publish the XIAO's crystal part, so this is the class figure). On a wrist the crystal
sits at ~30–35 °C: −0.034 × 10² ≈ −3.4 ppm. Worst case ≈ 25 ppm ≈ **2.2 s/day**. One time sync per
day keeps the band within a few seconds; the routine model needs minutes. Without the crystal the
chip's RC is ±500 ppm = 43 s/day (nRF52840 PS §5.4.2.4), still fine for routines but then BLE
timing windows widen; the XIAO has the crystal, so this is moot.

**Pattern** (uptime + offset; records written before the first sync are re-stamped by the phone):

```cpp
static uint32_t epochAtSync = 0, msAtSync = 0;  static bool timeValid = false;
static uint32_t bootCount;                        // from InternalFS, ++ at each boot

void timeSync(uint32_t unixSeconds) {             // called from the BLE 0x10 TIME command
  epochAtSync = unixSeconds; msAtSync = millis(); timeValid = true;
}
uint32_t nowUnix() {                              // wrap-safe for < 49.7 days between syncs
  return timeValid ? epochAtSync + (millis() - msAtSync) / 1000u : 0;
}
uint16_t minuteOfDayLocal(int8_t tzQuarterHours) {
  return timeValid ? ((nowUnix() + tzQuarterHours * 900) / 60) % 1440 : 0xFFFF;  // 0xFFFF = unknown
}
```

Phone side: on every connection (and once a day) write `[0x10][uint32 unix][int8 tz/15 min]`; the
band answers with its `nowUnix()` so the phone can log the drift it corrected (a free measurement
of the crystal for the report). **Battery-off/reset:** RESETREAS tells you why (A8); the time is
invalid until the next sync, the screen shows "—:—", the Guardian Loop keeps working on minutes-
since-boot and flags "routine detector degraded" in the BLE frame (bit `synced` = 0). Store
`{epochAtSync, uptime at save, bootCount}` only when a sync happens (≤ 1 write/day, A3), never
periodically. Do **not** use System OFF (`sd_power_system_off`) anywhere in the product loop: it
stops the RTC and the only wake is a pin/reset; tickless System ON sleep costs ~3 µA more and keeps
time (nRF52840 product brief: System ON with RTC ≈ 1.5–3 µA, cited in `mcu_ml_ble.md` §1).

### A5. BLE design

**BLEUart vs custom GATT.** Both ship in Bluefruit52Lib and compile to the same size (±1 KB). NUS
(`BLEUart`, UUID 6E400001-B5A3-F393-E0A9-E50E24DCCA9E) is a byte stream: framing, sync and
re-assembly are ours, but every phone tool (nRF Connect, Adafruit Bluefruit app, Web Bluetooth
"Web Serial"-style demos) already speaks it. A custom service (`BLEService` + `BLECharacteristic`,
as in the `custom_hrm` example) gives message semantics: one Notify characteristic = one 20-byte
status frame, one Write characteristic = one command. **Recommendation: custom service for the
product, with the standard Battery Service (0x180F) and Device Information Service (0x180A,
firmware revision = `HG_NN_VERSION` + git hash) beside it; keep `BLEUart` only as a debug console.**
poc_01/06 use `BLEUart` because the brief asked to measure that library; switching is 30 lines.

Service `HG`: base UUID `7A4E0000-9F3C-4C0B-8E2A-5B1D0C0FFEE0`
(random, generate the real one once with `uuidgen` and freeze it):

| Char | UUID short | Props | Payload |
|---|---|---|---|
| STATUS | 7A4E0001 | Notify (+Read) | 20-byte frame below, 1/min, plus immediately on state change |
| CMD | 7A4E0002 | Write / Write-no-response | phone→band commands below, ≤ 20 B each |
| INFO | 7A4E0003 | Read | 20 B: fw version, NN CRC, boot count, reset reason, twin save_count |

**Band → phone STATUS frame, 20 bytes little-endian** (fits the 23-byte default ATT MTU so Web
Bluetooth and iOS need no MTU negotiation):

| Off | Type | Field | Encoding |
|---:|---|---|---|
| 0 | u8 | frame type / version | 0x01 |
| 1 | u8 | state + flags | bits 0–2 state (0 OK, 1 drink, 2 cool, 3 danger, 4 I'm-OK, 5 battery); bit 3 contact OK; bit 4 time synced; bit 5 charging; bit 6 home(1)/out(0); bit 7 PPG valid |
| 2 | u16 | core estimate | °C × 100 (3712 = 37.12) |
| 4 | u8 | core 90 % half-range | °C × 100 (0–2.55 °C) |
| 5 | u8 | HR | bpm, 0 = none |
| 6 | u8 | HR quality | 0 no skin, 1 loose, 2 motion, 3 irregular, 4 OK (hg_ppg) |
| 7 | i16 | skin T | °C × 100 |
| 9 | i16 | reference T | °C × 100 |
| 11 | i16 | air T | °C × 100 |
| 13 | u8 | RH | % |
| 14 | u8 | battery | % (and bit 5 of byte 1 for charging) |
| 15 | u8 | routine score | 0–255 (255 = fully on-routine) |
| 16 | u8 | activity | motion counts in the last minute, saturating |
| 17 | u16 | minute counter | minutes since boot mod 65536 (sequence number; detects gaps) |
| 19 | u8 | CRC-8 | poly 0x07 over bytes 0–18 |

**Phone → band CMD** (first byte = opcode, last byte = CRC-8):

| Op | Name | Bytes | Body |
|---|---|---:|---|
| 0x10 | TIME | 7 | u32 unix seconds, i8 timezone in quarter hours |
| 0x11 | FORECAST chunk | 20 | u8 chunk 0–3, u8 total 4, then 6 hours × (i8 T °C, u8 RH %, u8 flag) = 18 B; band assembles 24 × 3 = 72 B; flag bits: 0 heat-day, 1 night-heat, 2 safe-hour |
| 0x12 | FAMILY_ACK | 7 | u8 ack type (1 family notified, 2 family replied, 3 cancelled), u32 alarm id |
| 0x13 | PROFILE | 7 | u8 field id (0 core offset, 1 HR-core slope, 2 resting HR, 3 sweat capacity, 4 skin-ref gain, 10–16 wake time per weekday…), f32 value |
| 0x14 | SAFE_HOURS | 20 | 24-bit bitmap of "safe" hours + u8 plan id + ASCII tag; band shows «Ώρες για έξοδο» |
| 0x1F | DEBUG | ≤ 20 | ask for the last N minute records (stream on BLEUart) |

Writes above 20 B are avoided on purpose: Chrome negotiates the MTU itself and `writeValue()`
caps at 512 B, iOS negotiates 185/247 automatically, Android must ask (`requestMtu`); a 20-byte
rule works everywhere with zero negotiation.

**Web Bluetooth demo (Chrome on a laptop, no app).** Supported in Chrome on **macOS, Windows 10+,
ChromeOS and Android**; Linux needs `chrome://flags/#experimental-web-platform-features`; **not
available in Safari or any browser on iOS** ([Chrome developers: Communicating with Bluetooth
devices over JavaScript](https://developer.chrome.com/docs/capabilities/bluetooth)). The page must
be served from a secure context (HTTPS, or `http://localhost`, which is fine for the demo: a
single HTML file served with `python3 -m http.server`), and `requestDevice()` "must be triggered by
a user gesture" (a click). Minimal client:

```js
const SVC = '7a4e0000-9f3c-4c0b-8e2a-5b1d0c0ffee0';      // lower-case 128-bit UUIDs
const STATUS = '7a4e0001-9f3c-4c0b-8e2a-5b1d0c0ffee0', CMD = '7a4e0002-9f3c-4c0b-8e2a-5b1d0c0ffee0';
button.onclick = async () => {
  const dev = await navigator.bluetooth.requestDevice({
    filters: [{ namePrefix: 'HeatGuardian' }], optionalServices: [SVC, 'battery_service'] });
  const srv = await (await dev.gatt.connect()).getPrimaryService(SVC);
  const status = await srv.getCharacteristic(STATUS);
  await status.startNotifications();
  status.addEventListener('characteristicvaluechanged', e => {
    const v = e.target.value;                              // DataView, little-endian
    const core = v.getUint16(2, true) / 100, hr = v.getUint8(5), q = v.getUint8(6);
    draw(core, hr, q, v.getUint8(1) & 7);
  });
  const cmd = await srv.getCharacteristic(CMD);
  const t = new DataView(new ArrayBuffer(7));             // 0x10 TIME
  t.setUint8(0, 0x10); t.setUint32(1, Math.floor(Date.now() / 1000), true); t.setInt8(5, 8); t.setUint8(6, crc8(t, 6));
  await cmd.writeValue(t.buffer);
};
```

The same page can `fetch()` Open-Meteo for the forecast and push the four 0x11 chunks, i.e. the
Tomorrow Engine can run in the browser for the demo. With `BLEUart` instead of the custom service,
replace the UUIDs by the NUS ones (TX notify 6E400003…, RX write 6E400002…) — the Bluefruit
`bleuart` example is exactly that.

**Android app (one paragraph).** Scan with `BluetoothLeScanner` filtered on the HG service UUID,
`device.connectGatt(ctx, false, callback)`, discover services, enable notifications with
`setCharacteristicNotification()` plus a write of `ENABLE_NOTIFICATION_VALUE` to the CCCD
(0x2902), write commands with `writeCharacteristic()`
([BluetoothGatt reference](https://developer.android.com/reference/android/bluetooth/BluetoothGatt)).
Android 12+ needs the runtime permissions `BLUETOOTH_SCAN` and `BLUETOOTH_CONNECT`
([Bluetooth permissions](https://developer.android.com/about/versions/12/features/bluetooth-permissions)).
To keep the link alive when the app is not visible, Google's guidance is "there is no restriction
on keeping a connection open in the background, but the connection is closed if your process is
killed"; use a `CompanionDeviceService` with `startObservingDevicePresence()` or a foreground
service of type `connectedDevice`
([BLE in the background](https://developer.android.com/develop/connectivity/bluetooth/ble/background)).
A `flutter_blue_plus`/`flutter_reactive_ble` app does the same in Dart (`mcu_ml_ble.md` §7).

**iOS app (one paragraph).** CoreBluetooth: `CBCentralManager.scanForPeripherals(withServices:
[HG])`, `connect`, `discoverServices`, `setNotifyValue(true, for: status)`, `writeValue(_, for:
cmd, type: .withoutResponse)`. Background: add the `bluetooth-central` background mode and
implement state preservation/restoration so iOS relaunches the app on a notification. iOS imposes
connection-parameter rules the band must respect or the request is rejected: interval ≥ 15 ms in
multiples of 15 ms, `Interval Max × (Slave Latency + 1) ≤ 2 s`, slave latency ≤ 30, supervision
timeout 2–6 s, and advertising at 20 ms for 30 s then exactly one of 152.5 / 211.25 / 318.75 /
417.5 / 546.25 / 760 / 852.5 / **1022.5** / 1285 ms (Apple QA1931,
[developer.apple.com](https://developer.apple.com/library/archive/qa/qa1931/_index.html)). A
"1 s" interval is therefore not literally allowed; the compliant choice closest to it is
**interval min 975 ms, max 990 ms, slave latency 1, supervision timeout 6 s** (both multiples of
15 ms; 990 × (1+1) = 1.98 s ≤ 2 s; 1.98 × 3 = 5.94 s < 6 s) and slow advertising at **1022.5 ms**
(Bluefruit `Advertising.setInterval(32, 1636)` in 0.625 ms units; fast 20 ms for the first 30 s).
iOS exposes Current Time Service to accessories, but the explicit 0x10 write
is simpler and works identically on Android and in Chrome.

**Power of advertising vs connected (Nordic numbers).** Nordic's Online Power Profiler for the
nRF52840 (LDO, 20-byte payload, 0 dBm) gives **20.24 µC per connectable advertising event** and
**8.43 µC per connection event**, idle 3.1 µA, LF-clock calibration 1.0 µA (only with the RC
oscillator) — quoted in
[DevZone 63521](https://devzone.nordicsemi.com/f/nordic-q-a/63521/nrf52840-battery-life-estimation/259197).
Scaling the per-event charge to our intervals:

| Mode | Average current |
|---|---:|
| advertising @ 40 ms (OPP figure) | 454 µA |
| advertising @ 1022.5 ms | 20.24/1.0225 + 3.1 ≈ **23 µA** |
| connected @ 40 ms (OPP figure) | 215 µA |
| connected @ 100 ms (what a phone app in the foreground often forces) | ≈ 87 µA |
| connected @ 990 ms, 1 notify/min | 8.43/0.99 + 3.1 ≈ **12 µA** |
| connected @ 990 ms, latency 1 (band may skip every other event) | ≈ **8 µA** |

Conclusion: BLE is a rounding error in the budget as long as the connection interval stays near
1 s; the risk is the phone forcing 30–100 ms while its app is open (0.2–0.7 mA), so the band
should re-request its parameters after connection (`Bluefruit.Periph.setConnInterval(780, 792)`
in 1.25 ms units; Bluefruit applies it with `requestConnectionParameter`). The datasheet TX/RX
peaks (6.4 mA at 0 dBm, 6.3 mA RX, DC/DC on) are in `power.md` §1.

### A6. Power: the final loop against the 250 mAh LP601730

Inputs: `power.md` §1–6 (measured XIAO floors 2.4–5.4 µA with QSPI deep-power-down, 23 µA without;
MAX30102 600 µA AFE; TMP117/SHT one-shot arithmetic; DRV2605L 4 µA standby), `PRODUCT_BRIEF.md` §7
("≈ 4.0 mA ≈ 96 mAh/day" for the CircuitPython version; LCD 25 mA at full backlight; vibration
2 min/day), Nordic OPP (A5), and two datasheets fetched for this pass:
**ICM-20649**: 6-axis low-noise mode **3.21 mA**, gyro-only low-power 1.23 mA, **accelerometer-only
low-power mode 68.9 µA at 102.3 Hz**, full-chip sleep 8 µA
([TDK DS-000192, SparkFun mirror](https://cdn.sparkfun.com/assets/7/e/5/f/1/ICM-20649_datasheet.pdf),
table 3.3); **Akyga LP601730**: 3.7 V, 250 mAh, 30 × 17 × 6 mm, 6.39 g, PCM, no electrical
thresholds published ([akyga.com product page](https://www.akyga.com/products/893-li-po-battery-lp601730-akyga-aky0384-3-7v-250mah-pcm-jst-2-pin-connector-150mm.html)).

Two findings before the table. **(1) The Adafruit ICM20X library's `begin_I2C()` leaves the IMU in
6-axis mode (gyro on) — 3.2 mA, i.e. 77 mAh/day, more than everything else combined.** 07 does this
today. The band needs accel-only low-power at 25–50 Hz with the gyro off (`imu.setGyroRateDivisor`
is not enough; write `PWR_MGMT_2` to disable the gyro and `LP_CONFIG` for duty-cycled accel) → ~30–70
µA. **(2) "Screen at 60 %" cannot mean always on**: 60 % of ~25 mA ≈ 15 mA ≈ 360 mAh/day. The
product brief's 15 min/day (wrist-raise, button, alerts) is the only version that fits; the panel
must go to SLPIN (0x10) with the backlight GPIO driven LOW (not PWM at 0 %, which keeps the PWM
peripheral and the 16 MHz clock running) between those windows.

**Final loop, duty-cycled (ESTIMATE):**

| Load | Arithmetic | Average |
|---|---|---:|
| XIAO floor: LDO + nRF System ON + LFXO + RTC, QSPI in deep power-down (0xB9) | measured (power.md) | 0.005 mA |
| …without the QSPI command (today's core default) | measured 23 µA | (+0.018) |
| CPU: 100 Hz PPG FIFO reads over I2C at 400 kHz in 32-sample bursts + hg_ppg + 1 Hz sensors + screen refresh | ~3 % awake × 3.3 mA while PPG on | 0.10 mA × PPG duty |
| CPU: NN ensemble 1/min | 0.55 ms × 3.3 mA / 60 s | 0.00003 mA |
| MAX30102 IR-only, 100 sps, LED 6 mA × 411 µs (0.25 mA) + AFE 0.6 mA + module LDOs 0.08 | 0.93 mA when on; **duty 25 % (30 s every 2 min)** | 0.23 mA |
| ICM-20649 accel-only low-power, 25–50 Hz, gyro off | datasheet | 0.05 mA |
| TMP117 × 2 one-shot 8× avg, 1/min; SHTC3 1/min | power.md arithmetic | 0.001 mA |
| BLE connected @ 990 ms, 1 notify/min (or advertising @ 1022.5 ms when alone) | A5 | 0.015 mA |
| Screen: 15 min/day at 60 % backlight (≈ 15 mA) + panel; SLPIN otherwise (~0.05 mA est.) | 15 × 15/1440 + 0.05 | 0.21 mA |
| Haptics: 2 min/day at 80 mA + DRV2605L standby 4 µA | brief §7 | 0.12 mA |
| Battery divider (P0.14 LOW) | measured | 0.002 mA |
| Breakout-board regulators and pull-ups (TMP117 × 2, SHTC3/ICM, DRV2605L) | brief §7 estimate | 0.20 mA |
| **Sum** | | **≈ 0.96 mA** |
| **+20 % margin** | | **≈ 1.15 mA ≈ 28 mAh/day** |

Battery life with 85 % usable capacity (PCM cut-off, LDO dropout): **250 × 0.85 / 1.15 ≈ 185 h ≈
7.7 days**. Sensitivities (same table, one change each): PPG continuous → +0.75 mA → 1.9 mA →
**4.7 days**; gyro left on (07 default) → +3.2 mA → 4.3 mA → **2.0 days**; screen always on at 60 %
→ +15 mA → **14 hours**; all three mistakes → **12 hours**. So "> 2 days" needs exactly four
things, in order of importance: screen off between interactions, gyro off / accel low-power,
PPG duty-cycled (or adaptive: continuous only when skin T or HR trend rises), QSPI deep power-down.
The CircuitPython figure in the product brief (3 mA MCU) does not apply to the Arduino build.

**Sleep strategy on this core.** There is nothing to write: every `delay()` in `loop()` blocks the
FreeRTOS task, the idle task runs tickless and calls `sd_app_evt_wait()`
(`port_cmsis_systick.c` line 203, `wiring.c` `waitForEvent()`), and the chip is in System ON sleep
at single-digit µA until RTC1, the SoftDevice or a GPIO wakes it. What breaks it: busy-polling
(`while (!done) {}`), `Serial` waits without a timeout, PWM left running, the IMU/PPG left in
high-power modes, and peripherals on the 3V3 rail. Loop shape: PPG samples arrive in the MAX30102
FIFO (32 deep) so `delay(250)` between `ppg.check()` bursts is safe; everything else is 1 Hz or
slower. Add `sd_power_dcdc_mode_set(NRF_POWER_DCDC_ENABLE)` after `Bluefruit.begin()` (the core does
not enable the DC/DC; the Seeed forum measurements in power.md were taken with it on; it cuts
radio/CPU current ~25 %). Measure with the UT131B in series with BAT+ after each change, as the
brief already says; the forum evidence (power.md §2) is that real boards land 2–10× above the
datasheet sum until each drain is found.

**Brown-out and the battery** are in A8.

### A7. MAX30102 HR on the wrist

**What the SparkFun library's `heartRate.h` does** (read from `heartRate.cpp`): Maxim's PBA example
in int16 arithmetic — a 1-pole DC estimator with α = 1/16 per sample, a 23-tap symmetric FIR
low-pass, then a **zero-crossing detector** with an absolute amplitude gate (peak-to-peak between
**20 and 1000 counts**). No refractory period, no inter-beat-interval validation, no signal-quality
output, global state (one sensor only). At the 100 sps that test 06 uses, α = 1/16 puts the DC
tracker's corner at f_s·α/2π ≈ 1.0 Hz, so it attenuates a 60 bpm pulse by ~3 dB and lets baseline
wander through (it was written for 25–50 sps); the 20–1000-count gate is in raw ADC units, so it
depends on LED current and perfusion (wrist AC at 110 k counts DC and 0.3 % PI is ~330 counts p-p:
inside the gate, but a looser band or lower LED current falls out of it silently, and motion that
exceeds 1000 counts is simply dropped rather than flagged). Test 06 saw "avg ~71–87 BPM, jumpy" on
a finger; on the wrist it will be worse. **Verdict: replace it.** It is fine for the bench.

**Implemented replacement** (`/home/claude/hg_ai/fw/poc_05_hr/hg_ppg.c`, 150 lines, streaming,
one call per IR sample at 50 or 100 sps):

```
push(ir, now_ms):
  dc += (ir - dc) / (1.5 s · fs)                       # DC tracker; dc < 20 000 counts -> NO_SKIN (test 06: 1,200 bare vs 110,000 on skin)
  y  = biquad2(biquad1(ir - dc))                       # Butterworth band-pass 0.5–4 Hz (30–240 bpm), coefficients from scipy (host/make_coeffs.py)
  env_hi = max(y, env_hi·decay); env_lo = min(y, env_lo·decay)   # 2 s envelope
  PI = 100 · (env_hi - env_lo) / dc                    # perfusion index, %
  if y[-1] is a local max and y[-1] > 0.5·env_hi and now - last_peak >= 300 ms:   # refractory = 200 bpm cap
      ibi = now - last_beat
      if ibi > 2000 ms: restart rhythm from this beat   # lost track (e.g. after an artefact inflated the envelope)
      elif |ibi - median(last 8 ibi)| > 30 %: reject; after 4 consecutive rejects accept the new rhythm (rest -> walking step)
      else: accept; push ibi into the 8-deep history; push timestamp into the 10 s window
  every beat / every second: HR = 60000 / median(IBIs in the last 10 s), needs >= 5 beats; CV = std/mean of those IBIs
  quality: NO_SKIN | LOW_PI (PI < 0.05 %: loose band) | MOTION (IMU still-flag says moving, or PI > 2 % at the wrist, or PI > 3x its 30 s baseline)
         | IRREGULAR (HR unavailable or CV > 25 %) | OK
```

**Cost:** 1,448 B flash, `sizeof(hg_ppg_t)` = 244 B RAM, no raw buffer (MEASURED). Per sample: two
biquads (10 MAC) + envelope + comparisons ≈ 60–100 cycles; the window median runs once per beat
(≤ 40 values, insertion sort ≈ 2 k cycles) → ≈ 0.02 % of the CPU at 100 sps. poc_05 prints the real
cycles/sample from the DWT.

**SIMULATION result** (`host/host_test.c`, synthetic PPG = pulse + 2nd harmonic + wander + noise +
artefacts, 20 s segments, judged on the last 8 s):

| Segment | HR (true) | Q_OK | Verdict |
|---|---|---|---|
| A clean 72 bpm, PI 0.5 % | 72.3 (72) | 91 % (first 2 s settle) | pass |
| B + baseline wander + white noise | 71.5 (72) | 100 % | pass |
| C step to 110 bpm, PI 0.3 %, DC step | 109.1 (110) | 100 % | pass (failed twice during development: IBI gate locked onto the old rhythm, then "lost track" froze the clock — both fixed and now covered by the test) |
| D 1.5 Hz motion artefact 10× pulse | — | 0 %, flagged MOTION | pass, **but only because of the PI-plausibility gate; without a gate it reported a confident 89.6 bpm** — on the band the IMU still-flag (`hg_ppg_set_motion`) is the authority |
| E loose band, PI 0.02 % | — | flagged LOW_PI | pass |
| F nothing on the window | — | flagged NO_SKIN | pass |

This proves the logic, not wrist performance: the synthetic signal has no real motion spectra,
no skin-tone or temperature effects, and the thresholds (PI 0.05 % / 2 %, CV 25 %) are first
guesses to be set on recorded data from Foivos's wrist and from the HTT PPG-less data we do not
have. Record 10 minutes of raw IR at 100 sps (sit, stand, walk, type) through the BLEUart debug
channel before trusting any threshold; the contact self-check (BRIEF item 7) should fuse this
quality word with the skin-vs-reference delta and the IMU.

### A8. Watchdog, brown-out and code-freeze practice

**Watchdog** (`/home/claude/hg_ai/fw/poc_04_wdt`, compiles, ~100 B): the nRF52840 WDT counts down
on the 32.768 kHz LFCLK, `timeout = (CRV + 1) / 32768`, is reloaded by writing 0x6E524635 to an
enabled RR[n], "cannot be reconfigured once started", keeps running in sleep and under the
debugger unless CONFIG says pause, and a TIMEOUT always resets the chip (nRF52840 PS v1.1 §6.36).
The SoftDevice does not touch it.

```cpp
#include <nrf_wdt.h>
static void wdtStart(uint32_t timeout_ms) {
  NRF_WDT->CONFIG = (WDT_CONFIG_HALT_Pause << WDT_CONFIG_HALT_Pos)     // pause when a debugger halts us
                  | (WDT_CONFIG_SLEEP_Run << WDT_CONFIG_SLEEP_Pos);    // keep counting in sleep: a hung sleep must reset
  NRF_WDT->CRV  = (uint32_t)(((uint64_t)timeout_ms * 32768u) / 1000u) - 1u;
  NRF_WDT->RREN = WDT_RREN_RR0_Msk;
  NRF_WDT->TASKS_START = 1;
}
static inline void wdtFeed(void) { NRF_WDT->RR[0] = WDT_RR_RR_Reload; }   // only from loop(), after every subsystem reported OK
// setup(): uint32_t rr = NRF_POWER->RESETREAS; NRF_POWER->RESETREAS = 0xFFFFFFFF;  // read + clear FIRST
//          if (rr & POWER_RESETREAS_DOG_Msk) log "watchdog reset" to InternalFS (counter, uptime, last state)
//          ... init ...; wdtStart(8000);
```

Rules: timeout = 4–8× the longest honest loop (8 s here); feed only in `loop()`, never from a
timer or ISR; count watchdog resets in the INFO characteristic so the demo can prove "0 resets in
72 h"; an 85 ms page erase and a 3 s `Serial` wait are both far below 8 s.

**Brown-out at 3.3 V with the LP601730.** The nRF52840 runs from 1.7 to 5.5 V and in normal-voltage
mode has a power-fail comparator (POF) with thresholds 1.7–2.8 V on VDD (POFCON THRESHOLD
V17…V28, V_POF,NV 1.7–2.8 V; nRF52840 PS v1.1 §5.3.1.6, brown-out reset §5.3.6.6). Below the
threshold it raises POFWARN and "will prevent the NVMC from performing write operations to the
flash" — free protection against a half-written Body Twin file. But the XIAO feeds the nRF from
its 3.3 V LDO, so the chip itself is the last thing to fail. What fails first as the cell sags: the LDO drops out below
~3.4–3.5 V input and the 3V3 rail follows VBAT; **the MAX30102's VLED is specified 3.1–5.0 V**
(datasheet, power.md §1), so below ~3.2 V the LED current regulation degrades and HR quietly gets
worse; the screen (2.8–3.3 V) dims; the DRV2605L (2–5.2 V) still runs; the PCM finally cuts at its
(unpublished) 2.5–3.0 V. The dangerous event is **IR sag under the 85 mA ERM start + 15 mA LED
pulses + 6 mA radio on a cold or nearly empty cell**: a 0.2–0.3 V dip can drop the rail below the
LDO's output, reset the chip, which re-runs `enterState(ST_OK, true)` → motor → sag → reset: a boot
loop that looks like "the band keeps restarting". Mitigations, all cheap:
1. Read VBAT (P0.31, divider enabled by P0.14 LOW) **before** anything else in `setup()`; if
   < 3.45 V boot into "charge me" mode: no motor, backlight ≤ 20 %, no PPG, BLE advertising only.
2. In the loop: VBAT < 3.5 V → cap motor effects to the soft tick and backlight to 50 % (the
   existing BL_MOTOR_MAX rule is the same idea); < 3.35 V → ST_BATTERY state and stop PPG.
3. Set POFCON to V28 and handle POFWARN (early-warning interrupt, no reset) by flushing InternalFS
   and killing the motor; it costs nothing and catches the case where the rail is already gone.
4. `RESETREAS == 0` after boot means power-on/brown-out: count it with the watchdog resets.
5. Average all 1-minute temperatures from readings taken > 2 s after a buzz (self-heating, power.md
   §7), and flag "charging" so the phone ignores temperatures while VBUS is present.

**Code-freeze practice for the demo build.**
- Debug level 0 (`-DCFG_DEBUG=0`, the core's default); every `while (!Serial)` bounded (07 does
  3 s); no `Serial.print` inside the 100 Hz path.
- `#define HG_FW_VERSION "1.0.0+<git-sha>"` printed at boot, in DIS firmware revision and in INFO;
  weights CRC checked at boot (A2) and the version pinned in the report.
- Build once with `arduino-cli compile --export-binaries`, keep the `.uf2`, flash it by double-tap
  reset + drag (SETUP.md §2.6); do not rebuild on the demo day.
- Watchdog on; a 72 h soak with the Serial log on the Mac; reset counters must read 0.
- `host_test` for the NN and the PPG detector green before the build; `git tag demo-freeze`.
- Pairing: none for the demo (Just Works adds nothing for a laptop demo; bonds live in InternalFS
  and survive re-flashing, so clear them with `Bluefruit.Periph.clearBonds()` once if a phone
  misbehaves).
- Known behaviours to leave alone: SPI mode 0 fix, I2C high-drive after every `begin()`, no
  `analogRead` on D4/D5 (SETUP.md lessons).

---

## Part B — Feasibility verdict (one page)

**Yes: items 1–8 of the BRIEF's AI list fit this chip with room to spare — measured, not
estimated, for the parts that exist.** The all-in-one build (07 + MAX30102 + BLE + 5-member NN +
storage + watchdog + HR detector) is **216,312 B = 26.7 % of the 811 KB application flash and
15.5 KB static RAM** (≈ 25 KB with the FreeRTOS task stacks) out of 237.5 KB. The ensemble
inference is ~0.5 ms on paper (1 ms budget) and runs once a minute; the HR detector is 0.02 % CPU.
The remaining unbuilt logic (nowcast, routine detector, alarms, Body Twin update, contact check)
is estimated at ~10 KB, giving **≈ 226 KB ≈ 28 %**, under the 30 % line with three levers in hand
(int8 weights −20 KB, drop USB serial in release −19 KB flash / −3.4 KB RAM, replace Arduino_GFX
by a minimal ST7789 driver −20 KB).

| Module (BRIEF item) | Flash | RAM | Status |
|---|---:|---:|---|
| 07_all_parts base: screen + Greek font, sensors, haptics, USB serial | 107,968 | 8,080 | measured |
| BLE: Bluefruit (incl. LittleFS it drags in, nRFCrypto), UART + battery + adv (5, 4) | 72,800 | 6,936 + ~6 KB stacks | measured |
| Core Sense NN, 5-member ensemble 24-32-16-3 float32 + CRC (2, 6, 8) | 32,984 | 0 static, 0.3 KB stack | measured |
| MAX3010x driver + hg_ppg wrist HR with quality word (5, 7) | 4,044 | 244 | measured |
| Body Twin + routine profile storage, InternalFS (3) | ~0 incremental (25.5 KB if BLE were absent) | 4.3 KB (shared with BLE bonds) | measured |
| Watchdog + reset-reason log (8) | ~0.1 KB | 8 | measured |
| **Measured total (poc_06_everything)** | **216,312 (26.7 %)** | **15,548 static** | compiles |
| Guardian Loop: 20–30 min nowcast (port of `heat_guardian_band.c` Kalman + correction) (5) | ~3 KB | 0.2 KB | estimate, C port already exists in hgmodel |
| Routine anomaly detector: per-hour Welford mean/var × 7 weekdays + z-score (5) | ~2 KB | 24 × 7 × 2 floats = 1.3 KB (or 24 × 2 = 0.2 KB without weekdays) | estimate |
| Two-tier calibrated alarms + «Είστε καλά;» button flow + family-alert state machine (5) | ~2 KB | 0.1 KB | estimate |
| Body Twin online update: 4-parameter SGD/EMA once a night (3) | ~1 KB | 0.1 KB | estimate |
| Tomorrow Engine on the band: store 24 × 3 B forecast + safe-hours bitmap, show plan (4) | ~1 KB | 0.1 KB | estimate (engine itself runs on phone/laptop) |
| Contact self-check: skin−ref delta + PPG quality + IMU (7) | ~0.5 KB | 0.05 KB | estimate |
| 1-minute record ring, 24 h × 20 B (for the demo's history and BLE resync) | 0 | 28.8 KB | estimate, fits easily |
| **Projected total** | **≈ 226 KB ≈ 28 %** | **≈ 55 KB of 237 KB** | |

Timing budget per minute: NN ensemble 0.45–0.55 ms (estimate; DWT print in poc_02 will replace it),
Kalman nowcast < 0.1 ms, routine/alarm logic < 0.1 ms, PPG 100 Hz ≈ 1 ms/s. All far inside the 1 ms
/ inference and the 1 Hz loop.

**What is not proven and must be measured on the board (in this order):**
1. **Cycles/inference** — upload poc_02; expected 90–110 µs per member, 0.45–0.55 ms ensemble; if
   > 1 ms, enable ICACHE / split accumulators / copy weights to RAM (A2).
2. **Average current** — the budget (A6) says 1.15 mA ≈ 7.7 days only if the IMU gyro is off, the
   screen sleeps, PPG is duty-cycled and the QSPI flash is in deep power-down; today's 07 has none
   of these and the IMU alone is 3.2 mA. Measure with the UT131B after each change.
3. **BLE on this board** — poc_01 compiles; it has never advertised. Flash it and connect with nRF
   Connect (Android) or the Chrome page (A5) before building the phone side.
4. **Wrist PPG thresholds** — the detector passes a synthetic test; its PI/CV thresholds are guesses
   until 10 minutes of raw wrist IR are recorded (A7).
5. **SoftDevice RAM warning** — `Bluefruit.begin()` prints a RAM-start warning if the SD config
   needs more than the linker's 24 KB; with `BANDWIDTH_LOW`, 1 link, no central it should not.

**Open risks.** The phone may force a 30–100 ms connection interval while its app is open
(0.2–0.7 mA; re-request 975–990 ms). InternalFS is shared with BLE bonds (never format; ≤ 5 saves
a day). A rejected brown-out boot loop on a weak cell is the most likely "mysterious restart" at
the demo (A8 rules 1–2 prevent it). int8 gives 3.6× smaller weights but 3–10 % output error with
per-tensor scales; float32 fits, so stay float32 unless flash is needed.

---

### Sources

Core files read: `~/.arduino15/packages/Seeeduino/hardware/nrf52/1.1.13/` — `boards.txt`,
`platform.txt`, `cores/nRF5/linker/nrf52840_s140_v7.ld`, `cores/nRF5/delay.c`, `rtos.h`,
`wiring.c`, `freertos/config/FreeRTOSConfig.h`, `freertos/portable/CMSIS/nrf52/port_cmsis_systick.c`,
`variants/Seeed_XIAO_nRF52840/variant.h`, `libraries/Bluefruit52Lib/src/bluefruit.cpp`,
`libraries/Bluefruit52Lib/src/utility/bonding.cpp`, `libraries/InternalFileSytem/src/*`,
`libraries/Adafruit_LittleFS/src/Adafruit_LittleFS_File.h`;
`~/Arduino/libraries/SparkFun_MAX3010x_Pulse_and_Proximity_Sensor_Library/src/heartRate.cpp`.
Earlier research cited: `/home/claude/research_notes/Heat Guardian band hardware/mcu_ml_ble.md`
(§1 chip currents, §3 TFLM/emlearn, §5 OPP numbers and custom service, §7 phone frameworks) and
`power.md` (§1 sensor currents, §2 hidden drains, §6 budget method, §7 self-heating);
`/home/claude/hg_product/PRODUCT_BRIEF.md` §7.

External:
- ARM Cortex-M4 TRM r0p1 (DDI0439B) FPU timing, mirrored as
  [Cortex-M4 Instruction Timing](https://www.cse.scu.edu/~dlewis/book3/docs/Cortex-M4%20Instruction%20Timing.pdf);
  [ARM community: vfma timings on Cortex-M4](https://community.arm.com/support-forums/f/architectures-and-processors-forum/46511/vfma-instruction-timings-on-arm-cortex-m4)
- nRF52840 Product Specification v1.1 (§2 CPU/wait states, §4.3.8 cache, §4.3.10.1 flash
  programming, §5.3.1.6 POF and §5.3.6.6 brown-out reset, §5.4.2.4 LFXO, §6.22 RTC, §6.36 WDT):
  [cdn.sparkfun.com nRF52840_PS_v1.1.pdf](https://cdn.sparkfun.com/assets/d/2/6/2/6/nRF52840_PS_v1.1.pdf)
- Nordic Online Power Profiler figures: [DevZone 63521](https://devzone.nordicsemi.com/f/nordic-q-a/63521/nrf52840-battery-life-estimation/259197);
  1 s advertising measurement thread: [DevZone 122135](https://devzone.nordicsemi.com/f/nordic-q-a/122135/current-consumption-for-ble-nrf52840/538911)
- Web Bluetooth: [developer.chrome.com/docs/capabilities/bluetooth](https://developer.chrome.com/docs/capabilities/bluetooth)
- Android: [BluetoothGatt](https://developer.android.com/reference/android/bluetooth/BluetoothGatt),
  [Bluetooth permissions (Android 12)](https://developer.android.com/about/versions/12/features/bluetooth-permissions),
  [BLE in the background](https://developer.android.com/develop/connectivity/bluetooth/ble/background)
- iOS: [Apple QA1931 BLE advertising and connection parameters](https://developer.apple.com/library/archive/qa/qa1931/_index.html)
- Crystal: [CTS TF32 32.768 kHz datasheet](https://www.ctscorp.com/Files/DataSheets/Passives/FCP/Crystals/crystals-TF32-datasheet.pdf)
- IMU: [TDK ICM-20649 datasheet DS-000192](https://cdn.sparkfun.com/assets/7/e/5/f/1/ICM-20649_datasheet.pdf)
- Battery: [Akyga LP601730 / AKY0384](https://www.akyga.com/products/893-li-po-battery-lp601730-akyga-aky0384-3-7v-250mah-pcm-jst-2-pin-connector-150mm.html)
- Board: [Zephyr XIAO BLE board page](https://docs.zephyrproject.org/latest/boards/seeed/xiao_ble/doc/index.html)
  (bootloader, QSPI flash; no crystal spec published)
- MAX30102 datasheet and the rest of the sensor figures: as cited in `power.md` §1.
