// =====================================================================
// RETIRED (0.9.6, Nov 16 2026): kept for history only. 09_guardian.ino is now the hand-maintained source and
// this file is NOT kept in sync with it (e.g. it still has the profile med limit 31; the .ino has 15, plus all the
// 0.9.6 fixes). Do not run fw/tools/make_09.py: it would regenerate the .ino with the screen on the dead D0/D9.
// =====================================================================
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
static bool everConnected = false; static uint16_t bleConn = BLE_CONN_HANDLE_INVALID;
static uint32_t lastMinuteTick = 0, timeSyncGen = 0; static uint8_t lastState = 0xFF, lastScreen = 0xFF;

// ---------------------------------------------------------------- local time
static int32_t localSecs() { return timeValid ? (int32_t)nowUnix() + (int32_t)tzQ * 900 : -1; }
static uint16_t localMod() { int32_t s = localSecs(); return s < 0 ? 0xFFFF : (uint16_t)((s / 60) % 1440); }
static int32_t localDay() { int32_t s = localSecs(); return s < 0 ? -1 : s / 86400; }

// ---------------------------------------------------------------- 1 Hz -> hg_fw
static void fwSecond(const hg_rec_t*) {
  hg_fw_sec_t s;
  s.t1_c = hasSkin ? t1C : NAN; s.t2_c = hasRef ? t2C : NAN; s.tair_c = hasSht ? tairC : NAN; s.rh_pct = hasSht ? rhPct : NAN;
  s.ppg_on = (uint8_t)(hasPpg && ppgEnabled);
  s.hr_bpm = hrDet.hr_bpm > 0 ? hrDet.hr_bpm : NAN; s.hr_q = hrDet.quality; s.pi_pct = hrDet.pi_pct;
  s.ppg_dc = hrDet.dc > 0 ? (uint32_t)hrDet.dc : 0;
  s.a_mean = secAMean; s.a_m2 = secAM2; s.a_n = secAN; s.a_peak_g = accPeak; s.zangle_deg = secAN >= 3 ? zMed / 100.0f : NAN;   // IMU lost -> NaN, not the stale z (T6b m9)
  hg_fw_second(&FW, &s);
}

// ---------------------------------------------------------------- 07's icons (copied unchanged by make_09.py)
@@07_ICONS@@

// ---------------------------------------------------------------- screens
enum { UI_MAIN = 0, UI_PLAN = 1, UI_DIAG = 2, UI_TOAST = 3 };
static uint8_t uiPage = UI_MAIN, uiToastScr = 0, uiDrawnScr = 0xFF, uiDrawnPage = 0xFF; static uint32_t uiToastUntil = 0;
static bool helpCancelled = false;      // HELP cancelled on the band or by the phone: until the next minute step shows it
static bool uiAlert() {   // keep the screen on while the wearer must act
  uint8_t st = FW.last_out.state;
  if (st == HG_ST_HELP && (helpCancelled || !G.help)) return false;
  return modelOk && FW.minutes && (st == HG_ST_CHECK || st == HG_ST_DANGER || st == HG_ST_HELP);
}
static void textBlock(const char* txt, int y0, int y1) {   // centred, word-wrapped Greek text, largest size that fits
  gfx->setFont(u8g2_font_10x20_t_greek); gfx->setUTF8Print(true); gfx->setTextColor(C_WHITE);
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
      for (int l = 0; l <= nl; l++) { int w = utf8Len(lines[l]) * 10 * size; gfx->setCursor((240 - w) / 2, ytop + (l + 1) * lineH - 4 * size); gfx->print(lines[l]); }
      gfx->setTextSize(1);
      return;
    }
  }
}
static void drawIcon(uint8_t scr) {
  const int cx = 120, cy = 82, s = 120;
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
static void uiDraw(bool full) {
  if (!screenOn) return;
  if (!modelOk) {   // ARCH B6b acceptance 2: CRC failure -> stay on the error screen
    if (full || uiDrawnPage != 0xEE) { gfx->fillScreen(C_BLACK); drawWarning(120, 82, 120, C_RED);
      textBlock("\xce\xa3\xcf\x86\xce\xac\xce\xbb\xce\xbc\xce\xb1 \xce\xbc\xce\xbf\xce\xbd\xcf\x84\xce\xad\xce\xbb\xce\xbf\xcf\x85", 150, 250); uiDrawnPage = 0xEE; }   // Σφάλμα μοντέλου
    return;
  }
  uint8_t page = uiPage, scr = FW.minutes ? FW.last_out.screen : HG_SCR_OK;
  if (scr == HG_SCR_HELP && (helpCancelled || !G.help)) scr = HG_SCR_OK;   // cancelled HELP: no stale HELP screen
  if (uiToastUntil && (int32_t)(millis() - uiToastUntil) < 0) { page = UI_TOAST; scr = uiToastScr; } else uiToastUntil = 0;
  if (uiAlert()) page = UI_MAIN;
  if (page == UI_DIAG) { if (full || uiDrawnPage != UI_DIAG) gfx->fillScreen(C_BLACK); uiDrawnPage = UI_DIAG; drawDiag(); return; }
  if (page == UI_PLAN) { if (full || uiDrawnPage != UI_PLAN) drawPlan(); uiDrawnPage = UI_PLAN; return; }
  if (full || uiDrawnPage != page || uiDrawnScr != scr) {
    gfx->fillScreen(C_BLACK); drawIcon(scr); textBlock(hg_screen_text(scr), 150, 250);
    uiDrawnScr = scr; uiDrawnPage = page;
  }
  static uint32_t lastFoot = 0;
  if (full || millis() - lastFoot > 30000) { lastFoot = millis(); drawFooter(); }
}
static void uiToast(uint8_t scr, uint32_t ms) { uiToastScr = scr; uiToastUntil = millis() + ms; screenWake(SCREEN_ON_MS); uiDraw(true); }

// ---------------------------------------------------------------- haptics (HG_HAP_* from the guardian, R3 6.3)
static const uint8_t HAP_WATCH[8] = { 15, WAIT10MS(40), 15, 0 };                                  // 2 long pulses (750 ms, 400 ms gap)
static const uint8_t HAP_COOL[8]  = { 15, WAIT10MS(30), 15, WAIT10MS(30), 15, 0 };                // 3 long pulses, repeated once after 10 s
static const uint8_t HAP_CHECK[8] = { 16, WAIT10MS(100), 16, WAIT10MS(100), 16, WAIT10MS(100), 16, 0 };   // 1 s on / 1 s off ...
static const uint8_t* hapPat = NULL; static uint8_t hapLeft = 0; static uint32_t hapNext = 0, hapGap = 0;
static void hapticStart(uint8_t id) {
  switch (id) {
    case HG_HAP_WATCH: hapPat = HAP_WATCH; hapLeft = 1; hapGap = 0; break;
    case HG_HAP_COOL:  hapPat = HAP_COOL;  hapLeft = 2; hapGap = 10000; break;
    case HG_HAP_CHECK: hapPat = HAP_CHECK; hapLeft = 4; hapGap = 500; break;    // ... 4 x 7 s + gaps = ~30 s
    case HG_HAP_TICK: case HG_HAP_SOFT: hapPat = PAT_SOFT; hapLeft = 1; hapGap = 0; break;
    default: hapLeft = 0; return;
  }
  hapNext = millis();
}
static void hapticService() {
  if (!hapLeft || motorBusy || (int32_t)(millis() - hapNext) < 0) return;
  vibrate(hapPat); hapLeft--;
  hapNext = millis() + hapGap + 8000u * (hapPat == HAP_CHECK);   // next run after this one has played
  if (hapPat != HAP_CHECK) hapNext = millis() + hapGap + 3000u;
}

// ---------------------------------------------------------------- button
static bool helpCancel(const char* src) {   // accidental HELP: a 2nd long press (band) or ack type 3 (phone) cancels it
  if (FW.button == 2) { FW.button = 0; evLog("HELP cancelled before the guardian saw it src=%s", src); helpCancelled = false; return true; }
  if (!G.help) return false;
  hg_cmd_t c; memset(&c, 0, sizeof c); c.op = HG_CMD_FAMILY_ACK; c.ack_type = 3; c.alarm_id = G.help_id;
  int ch = hg_guardian_cmd(&G, &c);                 // frozen A7.2 rule: HELP latched until ack type 3 (also clears its family flag)
  evLog("HELP cancelled src=%s alarm=%lu changed=%d family=%u", src, (unsigned long)c.alarm_id, ch, G.family_pending);
  helpCancelled = true;                             // uiAlert() off -> normal brightness at the next wake/toast
  return ch != 0;
}
static void uiButton(uint8_t kind) {
  uint8_t st = FW.last_out.state;
  if (kind == 2 && (FW.button == 2 || G.help)) {    // HELP already asked: this long press cancels it
    helpCancel("button"); vibrate(PAT_SOFT); uiToast(HG_SCR_OK, 5000); return;
  }
  hg_fw_button(&FW, kind);                          // latched: the guardian sees it at the minute boundary
  if (kind == 2) { helpCancelled = false; vibrate(PAT_LONG); uiToast(HG_SCR_HELP, 15000); return; }
  if (st == HG_ST_CHECK) { vibrate(PAT_SOFT); uiToast(HG_SCR_IMOK, 10000); return; }   // "I'm OK" only answers a CHECK (T6b m15)
  vibrate(PAT_SOFT);
  if (!screenOn) { uiPage = UI_MAIN; screenWake(SCREEN_ON_MS); uiDraw(true); return; }
  uiPage = (uiPage == UI_MAIN && haveSafe) ? UI_PLAN : UI_MAIN;
  screenWake(SCREEN_ON_MS); uiDraw(true);
}

// ---------------------------------------------------------------- Body Twin + profile files (InternalFS)
struct ProfileFile { uint32_t magic; float age, sex_m, bmi; uint8_t med, pad[3]; uint32_t crc; };
static bool profileLoad() {
  ProfileFile pf; File f(InternalFS); bool ok = false;
  if (f.open("/profile.bin", FILE_O_READ)) { ok = f.read((uint8_t*)&pf, sizeof pf) == sizeof pf; f.close(); }
  if (!ok || pf.magic != 0x46525048u || pf.crc != crc32b(&pf, sizeof pf - 4)) return false;
  if (!(pf.age >= 1 && pf.age <= 120 && pf.bmi >= 10 && pf.bmi <= 60)) return false;
  PROF.age = pf.age; PROF.sex_m = pf.sex_m; PROF.bmi = pf.bmi; PROF.med_flags = pf.med; return true;
}
static bool profileSave() {
  ProfileFile pf; memset(&pf, 0, sizeof pf);
  pf.magic = 0x46525048u; pf.age = PROF.age; pf.sex_m = PROF.sex_m; pf.bmi = PROF.bmi; pf.med = PROF.med_flags; pf.crc = crc32b(&pf, sizeof pf - 4);
  File f(InternalFS); if (!f.open("/profile.bin", FILE_O_WRITE)) return false;
  f.seek(0); f.truncate(0); bool ok = f.write((const uint8_t*)&pf, sizeof pf) == sizeof pf; f.close(); return ok;
}
static void infoUpdate();
static bool twinSave(const char* why) {   // only from the nightly hook or a PROFILE write (B6b acceptance 3); never format
  static uint8_t buf[HG_FW_TWIN_BUF];
  int n = hg_fw_twin_pack(&G, &TW, &TACC, twinSaveCount + 1, buf, sizeof buf);
  bool ok = false;
  if (n > 0) { File f(InternalFS); if (f.open("/twin.bin", FILE_O_WRITE)) { f.seek(0); f.truncate(0); ok = f.write(buf, n) == (size_t)n; f.close(); } }
  if (ok) { twinSaveCount++; twinSavesBoot++; }
  evLog("TWIN SAVE why=%s ok=%d bytes=%d save_count=%lu rest_hr=%.1f days=%u", why, ok, n, (unsigned long)twinSaveCount, TW.rest_hr, TW.days_learned);
  infoUpdate();
  return ok;
}
static void twinLoadAndInit() {
  static uint8_t buf[HG_FW_TWIN_BUF]; int n = 0;
  File f(InternalFS);
  if (f.open("/twin.bin", FILE_O_READ)) { n = f.read(buf, sizeof buf); f.close(); }
  twinLoadRc = hg_fw_twin_load(&G, &PROF, &TW, &TACC, n > 0 ? buf : NULL, (uint16_t)(n > 0 ? n : 0), &twinSaveCount);
}

// ---------------------------------------------------------------- BLE HG service (R4 A5; UUID base frozen with uuidgen, README)
#define HG_UUID(x) "0c76" x "-038b-46d5-8532-954dd1c5e01d"
BLEService        hgSvc(HG_UUID("0000"));
BLECharacteristic hgStatus(HG_UUID("0001")), hgCmd(HG_UUID("0002")), hgInfo(HG_UUID("0003"));
static volatile uint8_t cmdQ[4][20]; static volatile uint8_t cmdLen[4]; static volatile uint8_t cmdHead = 0, cmdTail = 0;
static uint16_t debugLeft = 0; static uint8_t debugCh = 0;
static void hgCmdCb(uint16_t, BLECharacteristic*, uint8_t* data, uint16_t len) {   // BLE task: copy only
  uint8_t nh = (cmdHead + 1) & 3; if (nh == cmdTail) return;
  if (len > 20) len = 20;
  for (uint16_t i = 0; i < len; i++) cmdQ[cmdHead][i] = data[i];
  cmdLen[cmdHead] = (uint8_t)len; cmdHead = nh;
}
static void hgOnConnect(uint16_t conn) {
  everConnected = true; bleConn = conn;
  BLEConnection* c = Bluefruit.Connection(conn);
  if (c) { c->monitorRssi(); c->requestConnectionParameter(792, 1, 600); }   // 990 ms, latency 1, 6 s (R4 A5, Apple QA1931)
}
static void hgOnDisconnect(uint16_t, uint8_t) { bleConn = BLE_CONN_HANDLE_INVALID; }
static int8_t bleBucket() {
  if (!Bluefruit.connected()) return everConnected ? 0 : -1;
  BLEConnection* c = Bluefruit.Connection(bleConn);
  int8_t r = c ? c->getRssi() : 0;
  return (r != 0 && r > -75) ? 2 : 1;
}
static void infoUpdate() {
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
  uint8_t z[20] = {0}; hgStatus.write(z, 20);
  Bluefruit.Periph.setConnInterval(780, 792);      // 975-990 ms preferred
  Bluefruit.Periph.setConnSlaveLatency(1);
  Bluefruit.Periph.setConnSupervisionTimeout(600); // 6 s
}
static void statusPublish(const uint8_t st[20]) {
  hgStatus.write(st, 20);
  if (Bluefruit.connected() && hgStatus.notifyEnabled()) hgStatus.notify(st, 20);
}
static void handleFrame(const uint8_t* p, uint8_t n, uint8_t ch) {
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
      bool helpBefore = G.help;
      int changed = hg_guardian_cmd(&G, &c);
      if (helpBefore && !G.help) { helpCancelled = true; evLog("HELP cancelled src=phone"); if (screenOn) { screenWake(SCREEN_ON_MS); uiDraw(true); } }
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
static void hgBleService() {
  while (cmdTail != cmdHead) {
    uint8_t b[20]; uint8_t n = cmdLen[cmdTail];
    for (uint8_t i = 0; i < n; i++) b[i] = cmdQ[cmdTail][i];
    cmdTail = (cmdTail + 1) & 3;
    handleFrame(b, n, CH_BLE);
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
  sd_power_pof_enable(1);
  sd_power_pof_threshold_set(NRF_POWER_THRESHOLD_V28);
  bool prof = profileLoad();
  twinLoadAndInit();
  hg_forecast_init(&FC);
  hg_fw_init(&FW);
  infoUpdate();
  evLog("GUARDIAN boot=%lu nn=%s crc=%s(0x%08lx) profile=%s(age %.0f sex_m %.0f bmi %.1f med %u) twin=%s(rc %d, saves %lu, rest_hr %.1f, days %u, calm_n %u)",
        (unsigned long)bootCount, HG2_NN_VERSION, modelOk ? "OK" : "MISMATCH", (unsigned long)HG2_NN_CRC32, prof ? "file" : "default",
        PROF.age, PROF.sex_m, PROF.bmi, PROF.med_flags, twinLoadRc == 0 ? "loaded" : "defaults", twinLoadRc, (unsigned long)twinSaveCount,
        TW.rest_hr, TW.days_learned, G.a_base_n);
}
static void guardianMinute(uint32_t tick) {
  lastMinuteTick = tick;
  hg_fw_ctx_t c;
  c.minute_of_day = localMod(); c.local_day = localDay(); c.charging = (uint8_t)charging(); c.vbat = vbat;
  c.ble_bucket = bleBucket(); c.forecast72 = FC.complete ? FC.data : NULL; c.has_forecast = FC.complete;
  if (!modelOk) {                                  // refuse to run on wrong weights (acceptance 2), but keep logging the inputs
    uint8_t rin[24]; hg_fw_minute_inputs(&FW, &c, tick, rin);
    if ((size_t)minN + 1u <= sizeof minBuf / HG_REC_SIZE) { memcpy(minBuf + minN * HG_REC_SIZE, rin, 24); minN++; } else recsLost++;
    return;
  }
  hg_fw_act_t a;
  hg_fw_minute(&FW, &G, &TW, &TACC, &c, tick, &a);
  helpCancelled = false;                            // the new STATUS already shows the cancelled HELP
  const hg_minute_out_t* o = &FW.last_out;
  if ((size_t)minN + 2u <= sizeof minBuf / HG_REC_SIZE) { memcpy(minBuf + minN * HG_REC_SIZE, a.rec_in, 24); memcpy(minBuf + (minN + 1) * HG_REC_SIZE, a.rec_g, 24); minN += 2; }
  else recsLost += 2;
  if (a.nightly) evLog("NIGHTLY twin update day=%ld mod=%u rest_hr=%.1f days=%u frozen=%u", (long)c.local_day, c.minute_of_day, TW.rest_hr, TW.days_learned, TACC.last_frozen);
  if (a.save_twin) twinSave("nightly");
  statusPublish(o->status);
  if (o->state != lastState || o->screen != lastScreen) {
    evLog("STATE %u screen %u level %u tiers %u core %.2f sd %.2f f20 %.2f why 0x%02x worn %u check %u family %u",
          o->state, o->screen, o->level, o->tiers, o->core.core_now, o->core.sd_now, o->core.f20_eff, o->why, o->worn, o->check_reason, o->family_alert);
    if (lastState != 0xFF || o->state != HG_ST_OK) { uiPage = UI_MAIN; screenWake(SCREEN_ON_MS); }
    lastState = o->state; lastScreen = o->screen;
    uiDraw(true);
  }
  if (o->haptic != HG_HAP_NONE) hapticStart(o->haptic);
}
static void guardianSecond(uint32_t tick) {
  // minute boundary: the local clock's minute when the time is known, else 60 s of uptime
  static uint32_t lastIdx = 0xFFFFFFFFu; static uint32_t lastGen = 0;
  int32_t ls = localSecs();
  uint32_t idx = ls >= 0 ? (uint32_t)ls / 60u : tick / 60000u;
  uint8_t sec = (uint8_t)(ls >= 0 ? (uint32_t)ls % 60u : (tick / 1000u) % 60u);
  if (lastIdx == 0xFFFFFFFFu || lastGen != timeSyncGen) { lastIdx = idx; lastGen = timeSyncGen; }   // TIME sync: re-anchor, no extra partial minute (T6b m3)
  if (idx != lastIdx) { lastIdx = idx; guardianMinute(tick); }
  // PPG: first 30 s of every minute, continuous while a tier / alert is on (hg_fw.h explains why not 30 s / 2 min)
  bool want = hasPpg && !lowBatMode && (rawActive || hg_fw_ppg_on(&FW, sec));
  if (hasPpg && !lowBatMode && want != ppgEnabled) { ppgEnable(want); if (want) { hg_ppg_init(&hrDet); ppgSetRed(false); } }
  hapticService();
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
  replyf(ch, "# STAT ble bucket=%d forecast=%s safe_hours=%s(0x%06lx) ppg_on=%d pof_hold=%d\n", bleBucket(), FC.complete ? "yes" : "no",
         haveSafe ? "yes" : "no", (unsigned long)safeBitmap, ppgEnabled, pofHold);
}
static bool guardianCommand(int argc, char** argv, uint8_t ch) {
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
  if (eqi(argv[0], "profile")) {
    if (argc < 5) { replyf(ch, "# PROFILE now age=%.0f sex_m=%.0f bmi=%.1f med=%u; set: profile <age> <sex_m 0/1> <bmi> <med bits 1 BB 2 diu 4 low-sweat 8 ACE 16 other HR-limiting (B5-v7)>\n", PROF.age, PROF.sex_m, PROF.bmi, PROF.med_flags); return true; }
    float age = atof(argv[1]), sx = atof(argv[2]), bmi = atof(argv[3]); int med = atoi(argv[4]);
    if (!(age >= 1 && age <= 120 && (sx == 0 || sx == 1) && bmi >= 10 && bmi <= 60 && med >= 0 && med <= 31)) { replyf(ch, "# PROFILE rejected\n"); return true; }
    PROF.age = age; PROF.sex_m = sx; PROF.bmi = bmi; PROF.med_flags = (uint8_t)med;
    hg_fw_apply_profile(&G, &PROF);                 // profile constants only: alarms, CHECK, HELP, tiers and learning untouched
    bool ok = profileSave();
    evLog("PROFILE age=%.0f sex_m=%.0f bmi=%.1f med=%u saved=%d (applied without restart; state %u help %u family %u kept)", age, sx, bmi, med, ok, FW.last_out.state, G.help, G.family_pending);
    replyf(ch, "# PROFILE saved=%d\n", ok); return true;
  }
  return false;
}
