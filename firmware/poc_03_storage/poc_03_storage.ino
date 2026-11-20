// =====================================================================
// Heat Guardian R4 PoC 03: non-volatile storage of Body Twin + routine profile
// ---------------------------------------------------------------------
// Uses InternalFileSystem (LittleFS on the nRF52840's own flash, 28 KB at
// 0xED000-0xF4000, 128-byte blocks) from the Seeed/Adafruit core.
// One file "/twin.bin" holds a versioned, CRC-checked struct. Save/load are
// each ~15 lines. Compare with poc_00_minimal for the flash cost.
//
// NOTE: Bluefruit stores BLE bonds in the SAME filesystem (/adafruit/bond_prph),
// so never InternalFS.format() in the product firmware: it erases the pairing.
// =====================================================================
#include <Adafruit_TinyUSB.h>
#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>
using namespace Adafruit_LittleFS_Namespace;

// ---- what the band must remember across resets and empty batteries -------
struct __attribute__((packed)) BodyTwin {
  float   core_offset_c;     // personal offset of the core estimate, °C
  float   hr_core_slope;     // °C per bpm above resting
  float   resting_hr;        // bpm, learned over the first days
  float   sweat_capacity;    // 0..1, relative to the population model
  float   skin_ref_gain;     // heat-flux calibration of the two TMP117s
  uint16_t days_learned;     // how many days of wear went into the above
};
struct __attribute__((packed)) RoutineProfile {
  uint8_t  wake_min_of_day[7];   // usual wake time per weekday, in 10-min steps (0..143)
  uint8_t  sleep_min_of_day[7];
  uint8_t  activity_by_hour[24]; // typical motion counts per hour, 0..255
  uint8_t  outings_by_hour[24];  // probability of being out, 0..255
};
struct __attribute__((packed)) TwinFile {
  uint32_t magic;        // 'HGTW'
  uint16_t version;      // bump when the layout changes
  uint16_t length;       // sizeof(TwinFile)
  BodyTwin twin;
  RoutineProfile routine;
  uint32_t save_count;   // for the wear log
  uint32_t crc32;        // over everything above
};
static const uint32_t TWIN_MAGIC = 0x57544748u;  // "HGTW" little-endian
static const uint16_t TWIN_VERSION = 1;
static const char* TWIN_PATH = "/twin.bin";

static uint32_t crc32(const void* p, size_t n) {
  const uint8_t* b = (const uint8_t*)p; uint32_t c = ~0u;
  while (n--) { c ^= *b++; for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u))); }
  return ~c;
}

// ---- the save/load pair -----------------------------------------------------
static bool twinSave(TwinFile& tf) {
  tf.magic = TWIN_MAGIC; tf.version = TWIN_VERSION; tf.length = sizeof(TwinFile);
  tf.save_count++;
  tf.crc32 = crc32(&tf, sizeof(TwinFile) - sizeof(uint32_t));
  File f(InternalFS);
  if (!f.open(TWIN_PATH, FILE_O_WRITE)) return false;
  f.seek(0); f.truncate(0);                     // FILE_O_WRITE appends; make it overwrite
  size_t n = f.write((const uint8_t*)&tf, sizeof(TwinFile));
  f.close();
  return n == sizeof(TwinFile);
}

static bool twinLoad(TwinFile& tf) {
  File f(InternalFS);
  if (!f.open(TWIN_PATH, FILE_O_READ)) return false;
  size_t n = f.read((uint8_t*)&tf, sizeof(TwinFile));
  f.close();
  if (n != sizeof(TwinFile) || tf.magic != TWIN_MAGIC || tf.version != TWIN_VERSION) return false;
  return tf.crc32 == crc32(&tf, sizeof(TwinFile) - sizeof(uint32_t));
}

static void twinDefaults(TwinFile& tf) {
  memset(&tf, 0, sizeof tf);
  tf.twin.core_offset_c = 0.0f; tf.twin.hr_core_slope = 0.0f;
  tf.twin.resting_hr = 65.0f;  tf.twin.sweat_capacity = 0.7f; tf.twin.skin_ref_gain = 1.0f;
  for (int d = 0; d < 7; d++) { tf.routine.wake_min_of_day[d] = 42; tf.routine.sleep_min_of_day[d] = 138; }  // 07:00, 23:00
}

TwinFile twin;

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) delay(10);
  Serial.println("Heat Guardian R4 PoC 03: InternalFS save/load");
  InternalFS.begin();                           // mounts; formats only if the FS is unreadable
  if (twinLoad(twin)) {
    Serial.print("loaded /twin.bin, save_count="); Serial.print(twin.save_count);
    Serial.print(" resting_hr="); Serial.println(twin.twin.resting_hr, 1);
  } else {
    Serial.println("no valid /twin.bin: writing defaults");
    twinDefaults(twin);
    Serial.println(twinSave(twin) ? "saved" : "SAVE FAILED");
  }
  Serial.print("sizeof(TwinFile) = "); Serial.println(sizeof(TwinFile));   // 102 B -> one 128 B block
}

void loop() {
  // In the product: save once a day (after the night-time Body Twin update) and
  // after a routine-profile change. NOT every minute. See R4 section 3 for wear.
  delay(60000);
  twin.twin.resting_hr += 0.1f;
  Serial.println(twinSave(twin) ? "periodic save OK" : "periodic save FAILED");
}
