# [IOS-APP] progress log

Native SwiftUI family app for the Heat Guardian band. Branch `ios-app`, everything under `ios/`.

- 13:20 UTC — Frames.swift (port of dashboard/js/hgframes.js) + Plan.swift; Python mirror `ios/tools/mirror_frames.py`
  passes 802 checks (status vectors, corrupt frames, TIME/ACK/PROFILE/CONSENT, 0x11/0x14 vs tomorrow + guardian vectors,
  all 1561 replay frames). No Swift compiler in this container (none installed; toolchain too big for the 1.7 GB disk).
- 13:40 UTC — All SwiftUI sources written (Now / Alert / Tomorrow / Week / Settings / Demo controls), BandLink (CoreBluetooth),
  DemoPlayer, AlertFX (chime + haptics + local notification), Info.plist, assets, XCTest, generated xcodeproj
  (`tools/gen_xcodeproj.py`, structural check `tools/check_xcodeproj.py` OK, parses with mod-pbxproj + openstep_parser).
- 13:50 UTC — Got a real Swift 6.0.3 Linux compiler (streamed subset of the toolchain, deleted afterwards for disk).
  COMPILED + RAN the non-UI code (Frames, Plan, Replay+DemoPlayer, Week, Strings): `tools/LinuxCheck.swift` 291/291.
  The SwiftUI / CoreBluetooth / UIKit files cannot be compiled on Linux — they are reviewed by hand only.
- HTML mocks rendered to shots/mock_*.png (layout mocks, NOT simulator screenshots).
- 14:00 UTC — ALL 16 app files type-check (Swift 6.0.3, Swift 5 mode) against hand-written API stubs of SwiftUI / UIKit /
  CoreBluetooth / AVFoundation / UserNotifications (`tools/linux_typecheck/run.sh`); FramesTests.swift type-checks against
  the model module. Stubs approximate Apple's API, so Xcode remains the real test. Toolchain deleted afterwards (disk).
- Shared scheme + workspace in the xcodeproj; README with beginner Xcode steps and demo/filming guide; app icon.

## [APP-HERDAY] Her Day — Nov 17 2026 (branch `ios-app-herday`)
- Frames: CMD 0x1B DAY_PLAN / 0x1C VISIT encoders, EVENTS type 9 VISIT / 10 PLAN_ITEM decoders (EcoFrames.swift) + Python
  mirror; `HeatGuardianTests/herday_vectors_app.json` (generated, `tools/gen_herday_vectors.py`).
- Cross-check against the band's `fw/09_guardian/herday_vectors.json` (0.9.8, copied as `herday_vectors_fw.json`):
  first run found ONE mismatch — the app clamped a hot window ending at midnight to to_h 23; band 0.9.8 accepts 24.
  Fixed (now 24), plus the band's extra field rules (kind 1 from <= to, heat-wave day 0-31). Now all groups MATCH
  (DAY_PLAN, field errors, VISIT, EVENTS 9 / 10 / nudges 7-8, ELDER_ACTION 7/8, band texts, place words).
- Engine (HerDay.swift), routine model / home rule / POI mapping (HerDayRoutine.swift), band-plan rebuild
  (HerDayBand.swift), on-device visit store + VISIT queue (Visits.swift), Core Location Visits + MapKit (VisitMonitor.swift),
  sending + demo (AppModel+HerDay.swift), family timeline (HerDaySection + HerDayDisplay), Elder card, Settings › places.
- Checks: `python3 -I tools/mirror_frames.py` (all pass, incl. Her Day + fw vectors), `tools/linux_xctest/run.sh` RUNS
  HerDayTests + EcoFramesTests + FramesTests on Linux (Swift 6.0.3), `tools/linux_typecheck/run.sh` type-checks all
  app files (stubs extended for CoreLocation / MapKit), `tools/check_xcodeproj.py` OK.
- NOT run: nothing ran in Xcode, the iOS Simulator or on an iPhone (no macOS here). Core Location / MapKit behaviour,
  the Always-permission flow, real CLVisit delivery, BLE with band 0.9.8, and the SwiftUI layout are untested.

## [APP-REPORT] Nov 18 2026 (branch `ios-app-report`)
- Her Day: overlap rule (engine + Python mirror + vectors + tests); demo «hotter tomorrow» shows "go after" (church 19:30).
- Band 0.9.9 EVENTS 11/12/13 decoded (Swift + mirror) and checked against the band's own packers (fw_alert_vectors.c);
  «Back to normal» row / quiet status (Family + Elder), all-clear closes a DANGER/CHECK takeover, Alert quality card.
- Heat report for the doctor: ReportLedger (per-day aggregates, no core estimate), HeatReport model + builder,
  HeatReportPDF (UIKit), ReportView (consent, period, share sheet), medicines list in Settings, Elder on/off, demo month;
  report_mirror.py renders the sample PDF on Linux from the Swift model's JSON.
- Checks: linux_xctest 37 tests pass (incl. AlertQualityTests, ReportTests), mirror_frames 1122 pass, LinuxCheck 291,
  linux_typecheck 71 files, check_xcodeproj OK. NOT run: Xcode, Simulator, iPhone (UIGraphicsPDFRenderer output,
  ShareLink, layouts).
- RESCOPE (Nov 18): the report is now a health track of her body in heat (HeatBody analysis, 5-min ledger series,
  "Her body in heat" screen with Swift Charts, PDF 7 pages with questions last, SHOW_TWIN_ESTIMATE default false).
  Generic ChartSpec / TableSpec drawn identically by the PDF renderer and report_mirror.py. 39 XCTests pass.

## [APP-TOWER] Nov 19 2026 (branch `ios-app-tower`) — owner decision: the app is HER phone, three jobs
- SETUP (`Views/Setup/SetupView.swift`): language (Greek default) → pair → name → age → sex → medicines → wake / bed →
  1–3 contacts (name, mobile → E.164, optional email) → done; one question per screen, ≥ 22 pt text, ≥ 64 pt targets.
- THE TOWER (`Model/Tower/`, `AppModel+Tower.swift`): band 0.9.17 EVENTS 14–21 decoded (`LadderEvents.swift`), checked
  byte for byte against the band's own ladder + packer (`tools/fw_ladder_vectors.c` → `ladder_vectors_fw.json`, rebuilt
  from fw commit a486805 = identical); unknown types / args ignored + logged (Settings › Diagnostics). Routing table
  (`SMSRouting.swift`), SMS texts el / en (`SMSText.swift`), outbox state machine (dedupe 10 / 30 min, 6 / h per number,
  urgent cap 20 / h, backoff 30 s → 15 min, 8 attempts, 3 h expiry, crash recovery), Twilio REST request + transport,
  DRY-RUN without credentials (demo always dry-run), credentials in the Keychain (after-first-unlock, this device only),
  test SMS, retries pumped on every live STATUS frame (background wake) and a 20 s timer. HELP on her phone → SMS from
  the phone at once (deduped with the band's echo). Her screen (`Views/Tower/TowerHomeView.swift`): connected pill
  (2-s press = Settings), balance gauge in the band's 5 colours + dot, reason line, «Μπράβο, δροσίζεστε» /
  «Ακόμα ζεσταίνεστε» from the ladder, ΒΟΗΘΕΙΑ, «Ιστορικό και αναφορά».
- HISTORY + REPORT (`DayStory.swift`, `TowerHistoryView.swift`): per day, reminders with "pressed done / worked / did
  not help / no response", escalations, HELP, SMS recipients; report emailed via MFMailComposeViewController to the
  contacts' emails or shared (`MailView.swift`); "an SMS cannot carry a PDF" in the UI.
- Removed / simplified: generic clock nudges (`plannedNudges` → []), the first-launch mode question (→ Setup), the mode
  picker (→ «Demo: family view» toggle; the family tabs stay for the competition).
- Checks: linux_xctest 55 tests pass (TowerTests 16 new; AlertQualityTests' "unknown type" example moved from 14 to 22),
  linux_typecheck 90 app files (stubs extended: Security, MessageUI, List, SecureField, wheel DatePicker,
  UIViewControllerRepresentable), mirror_frames 1122, LinuxCheck 291, check_xcodeproj OK (regenerated).
- NOT run: Xcode, Simulator, iPhone. Untested: background BLE over hours, state restoration after an iOS relaunch, real
  Twilio delivery, Keychain on device, MFMailComposeViewController, all SwiftUI layouts.

## [APP-GAUGE] Nov 19 2026 (branch `ios-app-tower`) — band 0.9.18 live gauge + battery
- EVENTS 22 GAUGE (`BandGauge`, `Model/Tower/Balance.swift`): step 0-4 / 0xFF grey, dot −10..+10, why, reminder,
  f20 (0x8000 unknown). A LIVE frame: `ingestEvent` takes it before the store, `EventStore.addBand` refuses it too —
  never a row, never moves the SYNC cursor (not even on a new boot count). Her gauge shows exactly the band's step + dot
  (`Balance.display`); no GAUGE frame for 3 min, older firmware, demo, HELP on screen or a preview override → the old
  STATUS-derived tier. `BalanceGauge` takes the dot as a value (no visual change).
- EVENTS 23 BATT_LOW, 15 BATT_CRITICAL, POWER_OFF arg 3 (battery mV in bytes 11-12) in `LadderEvents.swift`.
  BATT_CRITICAL / POWER_OFF 3 → ONE SMS (note priority, dedupe key "battery", normal rate limits) «<Name>: η μπαταρία
  του βραχιολιού τελείωσε (HH:MM). Δεν προστατεύεται μέχρι να φορτιστεί.» / English; in-app only when it reaches the
  phone > 30 min late (SYNC after a recharge). BATT_LOW → History only. History: «Χαμηλή μπαταρία: φορτίστε απόψε» and
  one «Η μπαταρία τελείωσε» row (the POWER_OFF 3 a second later folds into it).
- Vectors: `HeatGuardianTests/gauge_vectors_fw.json` = copy of fw/09_guardian/gauge_vectors.json (fw commit 106b751);
  all 8 GAUGE + 3 battery frames decode and re-encode byte for byte (TowerTests).
- Data-loss fix: `ReportLedger` wrote with complete file protection, which fails while the phone is locked (where the
  band's frames wake the app) and made a locked launch start empty and later overwrite the month. Now "complete until
  first user authentication" (like tower.json) and a file that exists but cannot be read is never overwritten (re-read +
  merge first). ReportTests covers both (simulated unreadable file; real data protection needs an iPhone).
- Checks: linux_xctest 61 tests pass (+6), linux_typecheck 90 app files, mirror_frames 1122, LinuxCheck 291,
  check_xcodeproj OK (regenerated: 9 test resources).
- Needs an iPhone: GAUGE notifications from a real 0.9.18 band (and that a READ of EVENTS after one is the ring event),
  the 3-min fallback on screen, a locked-phone background write of report_days.json, the battery SMS end to end.

## [APP-FIT] Nov 20 2026 (branch `ios-app-fit`) — fit check «Έλεγχος εφαρμογής»
- What BLE carries (frozen hg_frames.c / hg_guardian.c / hg_contact.c, fw 0.9.18 106b751 = b17-demo c473185 for these files):
  STATUS byte 1 bit 3 contact_ok = worn == 2; byte 0 bit 5 not_worn = NOT_WORN state (worn == 0 for >= 10 min, not
  during HELP / IMOK / CHECK); byte 1 bit 5 charging (forces worn 0 at once). worn 1 (loose) is NOT sent: loose and
  "off for < 10 min" both read contact_ok 0 / not_worn 0. The app says «Σφίξτε λίγο το λουράκι» only for that
  combination after a 180-s window (2-min hysteresis + 1 frame/min), from a frame decided after the check started.
- `Model/FitCheck.swift` (verdict, auto-show rule, FILMING MOCK script), `Model/Strings+Fit.swift`,
  `Views/Tower/FitCheckView.swift` (full-screen, solid card under the text: key word 40 pt bold, line 26 pt, green
  #05524A 9.1:1 / amber #6B3500 9.8:1 / text 17.4:1 on white; dark #9AF0E0 12.2:1 / #FFD199 11.4:1 on #16222E;
  BigGlassButton 72 pt). Her home: «Έλεγχος εφαρμογής» button; opens by itself on the first STATUS after a REAL band
  connects with contact not good (not on the charger, not over HELP / Settings / History, not for 12 h after an OK).
  OK closes it after 4 s. `-HGFit <state>`, `-HGFitMock YES`; demo mode + no real band = mock.
- Checks: linux_xctest 66 tests pass (FitCheckTests 5 new), linux_typecheck 93 app files, mirror_frames 1122,
  check_xcodeproj OK (regenerated). NOT run: Xcode, Simulator, iPhone (no macOS here).

## [APP-FINISH] Nov 20 — complete against band 0.9.17-demo-b7 (fw 430c58b)
- BLE contract re-checked field by field (STATUS, INFO, EVENTS 1-21, CMD 0x10-0x14 / 0x16-0x1C); ladder + alert vectors
  regenerated from 430c58b = byte-identical. This build sends no EVENTS 22 GAUGE / 23 BATT_LOW (0.9.18): her gauge uses
  the STATUS tier fallback. Fix: INFO fw_version 0x0917 read as "9.1.7" -> "0.9.17" (two-byte BCD from 0.9.10).
- BandLink: HELP / family replies / SYNC / TIME jump the write queue (~1 s per write at the band's interval); a failed
  connect or a GATT error on a live link keeps the pending reconnect instead of stopping at "failed".
- Tower: the band ring replayed on the first-ever SYNC (events from before this phone was the Tower) = History only.
- Time Sensitive Notifications entitlement removed (free Personal Team cannot sign it): alerts are .active.
- MKMapItem.placemark (deprecated iOS 26) -> MKMapItem.location. AppFinishTests (6); 72 tests pass on Linux. Xcode not run.
