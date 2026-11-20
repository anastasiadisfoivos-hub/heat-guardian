# Heat Guardian — iPhone app (her phone = THE TOWER)

**Owner decision Nov 19 2026: the app runs on HER phone and does exactly three jobs.**

1. **SETUP** (first launch): language (Greek default) → pair the band → her name → age → sex → medicines (optional)
   → wake / bed time → 1–3 family contacts (name + mobile + optional email). One question per screen, text ≥ 22 pt,
   buttons ≥ 64 pt (`Views/Setup/SetupView.swift`).
2. **THE TOWER**: keeps the Bluetooth link to the band in the background (bluetooth-central background mode + state
   restoration + automatic re-connect), still sends tomorrow's forecast / Her Day plan to the band, and turns band
   alerts into **SMS to the family** through Twilio (or DRY-RUN without an account). Her screen shows only: band
   connected yes / no, today's balance colour (green … red, the band's own colours) with its reason, and ΒΟΗΘΕΙΑ
   (`Views/Tower/TowerHomeView.swift`, `Model/Tower/`).
3. **HISTORY + REPORT**: her days (alerts, what she did, whether it worked, which SMS went) and the doctor's PDF,
   sent by email to the family or the share sheet (WhatsApp / Messages). An SMS cannot carry a PDF.

The family dashboard (4 tabs) is no longer the product: it is kept for the competition behind
**Settings › «Demo: family view»**. The clock-driven generic nudges (shutters, windows / air, A/C, clock-based water)
are removed, as on band 0.9.17.

SwiftUI, **iOS 26+ (Xcode 26)**, iPhone only, no third-party packages. Band ↔ app contract:
`fw/09_guardian/ECOSYSTEM_SPEC.md` (EVENTS 0004, CMD 0x16–0x1C; band 0.9.17 ladder EVENTS 14–21 in §5f).

## The Tower: SMS to the family (beginner steps)

### What sends an SMS (exact texts in `Model/Tower/SMSText.swift`, Greek by default)

| Band event | Family gets |
|---|---|
| HELP held (EVENTS 5, or HELP on her phone) | SMS at once: «Μαρία: ΖΗΤΗΣΕ ΒΟΗΘΕΙΑ από το βραχιόλι στις 14:52. Τηλεφωνήστε της τώρα.» |
| HELP cancelled after a HELP SMS | «Μαρία: ακύρωσε τη βοήθεια στις 14:55. Ένα τηλεφώνημα θα την ησυχάσει.» |
| LD_ESCALATED 1 (Danger line) | «Μαρία: ΚΙΝΔΥΝΟΣ από τη ζέστη στις 14:03. Το σώμα της ζεσταίνεται πολύ. Τηλεφωνήστε της τώρα.» |
| LD_ESCALATED 2 (still heating after cooling down) | «Μαρία: το νερό δεν βοήθησε, πήγε σε πιο δροσερό μέρος. Συνεχίζει να ζεσταίνεται (14:44). Τηλεφωνήστε της τώρα.» |
| Family alert in STATUS (CHECK not answered) | «Μαρία: δεν απάντησε στο βραχιόλι στις 14:03 ενώ κάνει ζέστη. Τηλεφωνήστε της τώρα.» |
| LD_NOTE 1 water did not help | «Notes by SMS» on (default): «Μαρία: το νερό δεν βοήθησε (14:22). Το βραχιόλι της είπε να πάει σε πιο δροσερό μέρος.» |
| LD_NOTE 2 no response | «Notes by SMS» on: «Μαρία: δεν απάντησε στην υπενθύμιση να πιει νερό (14:20). Ίσως ένα τηλεφώνημα.» |
| LD_NOTE 3 she pressed during escalation | «Μαρία: πάτησε το κουμπί στις 14:46, σας βλέπει. Η ζέστη συνεχίζεται: η ειδοποίηση μένει.» |
| LD_WORKED 3 after a danger SMS | «Μαρία: σταμάτησε να ζεσταίνεται (15:10). Μείνετε σε επαφή μαζί της.» |
| Reminder / done / worked (water, cooler place), power off, battery, motor | History only |
| Band disconnected | In the app only; Settings can turn on an SMS after 60 min |

No SMS storms: the same message to the same person at most once per 10 min (HELP / danger) or 30 min (others), at most
6 SMS an hour per person (HELP / danger always go, hard cap 20), offline → retried after 30 s, 1, 2, 4 … up to 15 min,
8 attempts, given up after 3 h. Everything is listed in **Settings › Family (SMS) › Alert tower › SMS outbox**.

### Step 1 — Try it without an account (DRY-RUN)

With no Twilio credentials the app is in **DRY-RUN**: every SMS is built and shown in the outbox exactly as it would be
sent, marked «Δοκιμή: θα στελνόταν», and nothing leaves the phone. Demo events (SIMULATION) are always dry-run.

1. Open Settings on her screen: **press and hold the «Βραχιόλι συνδεδεμένο» pill for 2 seconds**.
2. **Οικογένεια (SMS)**: check the 1–3 contacts from Setup (or add them).
3. **Πύργος ειδοποιήσεων (SMS)** → **«Επίδειξη: …»** plays a band ladder (water did not help → still heating → she
   presses → settled) through the real decoder → open **Εξερχόμενα SMS** to see the texts.

### Step 2 — Paste the Twilio credentials (to really send)

1. Make an account at twilio.com, buy (or use the trial) phone number. On a trial account Twilio only sends to
   numbers you verified in its console.
2. In the Twilio Console home page copy the **Account SID** (starts with `AC`) and the **Auth Token**.
3. On her iPhone: Settings (hold the pill 2 s) → **Οικογένεια (SMS)** → **Πύργος ειδοποιήσεων (SMS)** → paste
   **Account SID**, **Auth Token**, and your Twilio number in **Αριθμός αποστολέα (From)** (e.g. `+15551234567`) →
   **Αποθήκευση στο Keychain**. The status line turns to **ΕΝΕΡΓΟ**.
4. Tap **Στείλτε δοκιμαστικό SMS**: every contact gets «Heat Guardian: δοκιμαστικό μήνυμα για Μαρία. Οι ειδοποιήσεις
   λειτουργούν.» Check the outbox says «Στάλθηκε».

The credentials live only in this iPhone's Keychain (this device only, readable after the first unlock so SMS go
while the phone is locked). They are never in the code, never shown again, never logged, never in git.
**«Διαγραφή λογαριασμού»** removes them and returns to DRY-RUN.

### Step 3 — The background capability (must be on)

The Tower only works if iOS lets the app keep Bluetooth in the background. In Xcode: blue **HeatGuardian** project →
**TARGETS › HeatGuardian** → **Signing & Capabilities**. You must see **Background Modes** with **Uses Bluetooth LE
accessories** ticked (the project sets it in `Info.plist`: `UIBackgroundModes = bluetooth-central`). If the section is
missing: **+ Capability** → **Background Modes** → tick **Uses Bluetooth LE accessories**.

On her phone: keep Bluetooth on, leave the app running (locking the phone is fine). **Do not swipe the app away** in
the app switcher: iOS then stops background Bluetooth for it until she opens it again. After a phone restart, open the
app once.

---

## Before Nov 19: the family app (now «Demo: family view»)


The family's phone for the Heat Guardian band (a heat-stress band for people 65+). It shows how the wearer is doing
and raises a full-screen alert when the band asks for the family.

SwiftUI, **iOS 26+ (Xcode 26)**, iPhone only, no third-party packages. Greek by default, English in Settings.
Band ↔ app contract: `fw/09_guardian/ECOSYSTEM_SPEC.md` (EVENTS 0004, CMD 0x16–0x19). The screens are placeholder UI over
one view-model per tab (`HeatGuardian/ViewModels/`); the visual design is built on top of them.

| Tab | What it shows (view-model) |
|---|---|
| **Σήμερα / Today** | her state (same colour / word as the band), the reason line, last update or «Χωρίς σύνδεση» + last sync; the day log: nudges (upcoming / shown / done ✓ time / missed), warnings, «Είμαι καλά», HELP / cancel, family messages, each marked «βραχιόλι» or «εσείς» (`TodayViewModel`) |
| **Αύριο / Tomorrow** | tomorrow only: indoor °C by hour for HER home class, 28 / 30 °C bands, safe hours, the planned nudges, advice; sent to the band by itself on connect (`TomorrowViewModel`) |
| **Ιστορικό / History** | past days, each with «4/5 ✓ · 3 νερό · 0 προειδοποιήσεις» and its log (`HistoryViewModel`) |
| **Ρυθμίσεις / Settings** | your name on the band (0x18), her profile + medicines, her routine and home (0x19), evening summary, connection, demo, diagnostics (`SettingsViewModel`) |

**Alert:** when the band raises a family alert (CHECK not answered), HELP or DANGER, the app takes over the whole screen
with a chime, vibration and a notification. «Σας καλώ» = FAMILY_ACK 2 + FAMILY_MSG 1 (and the dialler if
you saved a number), «Έρχομαι» = FAMILY_MSG 2, «Το είδα» = FAMILY_MSG 3. The same three are actions on the lock-screen
notification. Other notifications: two missed reminders in a row (gentle, once a day) and the 20:30 evening summary
(on by default, Settings). Everything else is only in the log.

**Two modes (DESIGN.md, before Nov 19).** First launch used to ask «I wear the band» / «I'm family»; since Nov 19 it is
Setup, then her screen, and the four tabs above are the «Demo: family view» toggle in Settings; in Elder mode Settings opens with a 2-second press
on the clock. The UI is iOS 26 Liquid Glass over a colour field that shows the state (`Views/`, `RESEARCH_UI.md`).

**For screenshots in the Simulator** (no Bluetooth there), launch arguments:

| Argument | Values |
|---|---|
| `-HGMode` | `elder` = her screen (the Tower), `family` = the family demo view (both skip Setup; `-HGOnboarding YES` shows Setup) |
| `-HGDemo YES -HGDemoAt 900` | start the demo recording and seek it |
| `-HGTab` | `today`, `tomorrow`, `history`, `settings` (Family) |
| `-HGState` | `ok`, `heat`, `water`, `danger`, `check`, `help`, `offline` (forces the screen state) |
| `-HGAlert` | `help`, `danger`, `family` (Family: the full-screen alert, sample) |
| `-HGFamilyMsg` | `1`, `2`, `3` (Elder: the family message card) |
| `-HGLang` | `el`, `en` (default: Family English, Elder Greek) |
| `-HGFit` | `checking`, `ok`, `loose`, `off`, `charging`, `noLink` (Elder: the fit check open in that fixed state) |
| `-HGFitMock YES` | Elder: the fit check's FILMING MOCK (checking 10 s → «Σφίξτε λίγο το λουράκι» → tap «Έλεγχος ξανά» → checking 10 s → «Εφαρμογή OK ✓» → home). Never used while a real band is connected; shows the ΠΡΟΣΟΜΟΙΩΣΗ badge. In the app: Settings › Demo › start, close Settings, tap «Έλεγχος εφαρμογής». |

Example: `xcrun simctl launch --terminate-running-process booted gr.heatguardian.family -HGMode family -HGDemo YES -HGDemoAt 900 -HGTab today -HGState help`
then `xcrun simctl io booted screenshot today_help.png`. Every screen also has `#Preview`s for its key states.

What it does not claim: body temperature is an estimate from the wrist, always shown with its range. No fall detection.
Not a medical device. Anything simulated says **ΠΡΟΣΟΜΟΙΩΣΗ / SIMULATION** on screen.

---

## Run it on your iPhone (first time, about 15 minutes)

You need: a Mac with **Xcode 26** (free, from the Mac App Store), your iPhone (iOS 26 or newer) and its USB cable,
and your normal Apple ID. You do not need a paid developer account.

### Step 1 — Open the project

In Terminal, go to the `ios` folder of the repository (branch `ios-app`). For example:

```
cd ~/heat-guardian/ios
```

Then open the project:

```
open HeatGuardian.xcodeproj
```

Xcode opens. If it asks to "Trust and Open", click it.

### Step 2 — Sign with your Apple ID

1. In the left column click the blue **HeatGuardian** project icon at the very top.
2. In the middle, under **TARGETS**, click **HeatGuardian**.
3. Open the **Signing & Capabilities** tab.
4. Leave **Automatically manage signing** ticked.
5. **Team** → **Add an Account…** → sign in with your Apple ID → then pick **"Your Name (Personal Team)"**.
6. If Xcode shows a red error about the bundle identifier ("not available"), change **Bundle Identifier** to something
   only you use, for example `gr.heatguardian.family.foivos`, and press Enter.
7. The project asks for **no** extra capabilities: a free Personal Team cannot sign Time Sensitive Notifications, so
   the app has no entitlements file and its alerts are normal (active) notifications that respect Focus / Do Not
   Disturb. With a paid team you can add **+ Capability** → **Time Sensitive Notifications** and set
   `interruptionLevel = .timeSensitive` in `App/AlertFX.swift`.

### Step 3 — Prepare the iPhone

1. Plug the iPhone into the Mac. On the iPhone tap **Trust** and enter your passcode.
2. Turn on **Developer Mode**: iPhone **Settings › Privacy & Security › Developer Mode** → on → the iPhone restarts →
   after the restart confirm **Turn On**. (The switch appears only after the iPhone has been plugged into Xcode once.
   If you don't see it, do Step 4 once, then come back.)

### Step 4 — Run

1. At the top of Xcode, next to the ▶ button, pick your **iPhone** as the run destination (not a simulator).
2. Press **▶ Run** (or ⌘R). The first build takes a minute.
3. The first time, the iPhone may say **"Untrusted Developer"**. Open iPhone **Settings › General › VPN & Device
   Management**, tap your Apple ID, tap **Trust**. Then press ▶ in Xcode again.
4. The app opens. Allow **Notifications** (so alerts sound when the phone is locked) and **Bluetooth**.

**Free signing lasts 7 days.** After 7 days the app stops opening: plug the iPhone in and press ▶ again (nothing else
to do). A paid Apple Developer account (99 €/year) makes it last a year.

### Step 5 — Connect the band

1. Keep the band near the iPhone.
2. In the app: **Ρυθμίσεις › Σύνδεση** (or the Connect button on the Now tab).
3. Firmware **0.9.4 / 0.9.6** (the demo bands): no code, no button presses — it just connects. Do **not** press the
   button 5 times: during a «Είστε καλά;» CHECK a press answers "I'm OK".
   Firmware **0.9.5 only** (Bluetooth security branch): first press the band's button **5 times quickly** (pairing
   window, 3 minutes; a brand-new band is open for its first 10 minutes anyway); the iPhone then asks **"Bluetooth
   Pairing Request"** with a code field — type the **6 digits shown on the band** → Pair.
   Once connected, the app reads the firmware version (Ρυθμίσεις › Διαγνωστικά shows e.g. `fw 0.9.4`) and its
   connect text follows it.
4. The Now tab fills in. If the link drops, the big state turns grey and says «Χωρίς σύνδεση» with the last known state. The app re-connects by itself later, also in the background. It sends the clock and time zone
   to the band on every connection.

If pairing is refused (0.9.5 only): wrong code, or the window closed. Press the band's button 5 times quickly and connect again.
If you cleared the band's phones (`bonds clear YES`), also remove HeatGuardian from iPhone **Settings › Bluetooth**
(ⓘ › Forget This Device).

---

## Demo mode — for filming

The band does not need to be on a wrist. Demo mode plays the dashboard's recordings through the **same decoder** as
the real band, and every screen says **ΠΡΟΣΟΜΟΙΩΣΗ**.

1. **Ρυθμίσεις › Έναρξη επίδειξης** (or "Δοκιμή χωρίς βραχιόλι" on the Now tab).
   It starts the heat-wave day of virtual person 398 at 13:00, at 60× (one minute per second):
   COOL from about 13:30, DANGER 14:00, **family alert at 14:03** — about one minute after you start.
2. On the Now tab, the small bar at the top: ⏸ / ▶, and ☰ for the controls: speed **1× / 10× / 60×**, a scrubber,
   «Λίγο πριν την ειδοποίηση» (jump to 13:57), «Πρωί», and **«Ειδοποίηση τώρα (για γύρισμα)»** — the alert screen
   at once, from the recording's real alert frame.
3. The other recording is the HTT1 heat-chamber session (real data, a 31-year-old in a 40 °C chamber); it is labelled so.
4. In demo mode, commands (acknowledgements, plan, profile) are **not sent to a band**: they appear in
   Settings › Διαγνωστικά, marked ΠΡΟΣΟΜΟΙΩΣΗ. A real band's alert always wins over a demo alert.
5. **Ρυθμίσεις › Τέλος επίδειξης** returns to the live band.

Tips for the video: Dark or Light both work (iPhone Settings › Display). The alert chime plays even with the silent
switch on while the app is open. To record the screen, add **Screen Recording** to Control Center, or record the
Simulator (demo mode works in the Simulator; Bluetooth does not):

```
xcrun simctl io booted recordVideo ~/Desktop/heat-guardian-demo.mov
```

(Press Ctrl-C in Terminal to stop.)

---

## Her Day (her routine × tomorrow's heat) — band 0.9.8

Spec: `HERDAY_SPEC.md` (shared). The band only speaks where her usual day **collides** with the heat, plus when to air
the flat. Two phones, two jobs:

- **Her phone (Elder mode)** learns where she goes with iOS **Visits** (Core Location, "Always"). Each new place is typed
  once with an Apple Maps point-of-interest search near it (market, church, walk/park, pharmacy, café, doctor, other);
  home = the place with the most night-time dwell over 14 days, or «Εδώ είναι το σπίτι». **Coordinates stay on her
  phone** (`visits.json`); the band and the family get only the place **type** and the **time** (CMD 0x1C VISIT, queued
  while the band is away). Honest note: the type lookup is an Apple Maps request, so Apple sees that one point once per
  new place, as with any map search. From her visits the app learns her usual day (median start / length per place and
  weekday over 4 weeks; ≥ 4 weekdays = a daily habit), lays it over the hourly forecast and sends **DAY_PLAN** (0x1B):
  tomorrow's from 18:00, today's at the first connection of the day. Her screen shows the evening / morning card
  «Αύριο: αγορά πριν τις 09:30» with «Εντάξει» (closes the band's brief if it is open: ELDER_ACTION 2 + nudge 7 / 1).
- **The family phone** shows **Her Day** on Tomorrow (and today's on Today): outside / house heat strip by hour, her usual
  outings as place symbols, collisions marked, the band's suggestions, and afterwards whether she followed them —
  all rebuilt from the band's PLAN_ITEM / VISIT events, so it shows what the band holds. Today's status line:
  "At the market since 10:52" / "Home since 12:05".

Settings (on her phone; open with a long press on the clock): **Τα μέρη της** — location on/off and the permission
state, «Εδώ είναι το σπίτι», the learned places (change a place's kind, swipe to delete), «Διαγραφή όλων των μερών».

**Demo (no Bluetooth, no location, works in the Simulator)**: start the demo as usual. Two weeks of her scripted visits
and two constructed Athens heat-wave days (today = day 1, tomorrow = day 2, labelled SIMULATION) make the market
(10:20) and the café (18:00) collide tomorrow; the 21:15 walk does not. At 13:00 today's status line and «followed»
show; **Demo controls › «Her Day: evening 20:00»** jumps to the evening, when tomorrow's plan is on the (simulated)
band and the Elder screen shows «Αύριο: αγορά πριν τις 09:30». Launch-argument recipe for screenshots:
`-HGDemo YES -HGDemoAt 1200 -HGMode family -HGTab tomorrow` (or `-HGMode elder`).

**Location in the Simulator**: the first time Elder mode is chosen iOS asks for location — pick «Allow While Using App»,
then (when asked again) «Change to Always Allowed». To give the Simulator a position: **Features › Location ›
Custom Location…** (e.g. 37.9715, 23.7257), then «Εδώ είναι το σπίτι» in Settings works. The Simulator does **not**
produce real Visits (they come from the phone's own motion and dwell detection), so use the demo there; real visits
need an iPhone carried around for a few days. If location was denied: iPhone Settings › Heat Guardian › Location.

---

## Band 0.9.9: alert quality, «Back to normal» (ECOSYSTEM_SPEC 5e)

The app decodes the three new EVENTS types (older types unchanged; any type it does not know is still ignored):
**11 ALERT_HELD** (what was held back and why), **12 ALL_CLEAR** (an episode ended: length, family called) and
**13 SCORE** (the band's scorecard, 3 pages, counters since boot). Checked byte for byte against vectors made with the
band's own packers (`tools/fw_alert_vectors.c` -> `HeatGuardianTests/alert_vectors_fw.json`).

- **Back to normal**: a quiet «Back to normal» row in the day log and, for 2 hours, the Today subtitle
  "Back to normal 15:20 · 42 min" (Elder screen: «Πάλι όλα καλά, από τις 15:20.» for an hour). Never a sound or a
  notification. It also closes a DANGER / unanswered-CHECK takeover on this phone (a HELP she pressed stays up).
- **Alert quality** card (Family › History, top): this week sent / held back / acknowledged / missed, the hold-back
  reasons in plain words, average time to answer. From the band's scorecard when it has one (per boot, the daily
  difference), plus the log for the hours since; from the log alone on 0.9.8.
- Demo: a week of scorecard snapshots, today's scripted hold-backs (shower, settled by itself, one sign only, weak
  pulse signal) and an ALL_CLEAR whenever the recording returns to OK — all labelled SIMULATION.

## Her body in heat + the heat report for the doctor (PDF made on the phone)

**Rescoped (Foivos, Nov 18): a HEALTH TRACK of her body in heat, in the app and as the core of the PDF.**
Family › History › **«Her body in heat»** (native Swift Charts) and the PDF draw ONE model (`Model/HeatReport.swift`,
analysis in `Model/HeatBody.swift`) from the per-day records of every live STATUS minute (`Model/ReportLedger.swift`,
5-minute means, 31 days, `report_days.json`, complete file protection):

1. **Wrist skin temperature** per day (min / mean / max) and a 24 h profile of the hottest day, next to the air at home,
   the air outside and humidity — always labelled "wrist skin temperature", never body temperature.
2. **Heart response to heat**: hourly daytime pulse (quiet hours, episodes and walking left out) against the air,
   fitted pulse = a + b·max(0, air − 26 °C) -> "≈ b bpm per °C above 26 °C", with her normal (median quiet daytime pulse
   at ≤ 26 °C) and her resting pulse per day.
3. **Recovery**: after each episode, minutes from the peak until her pulse is back within 5 bpm of what the air alone
   explains for her (the fitted line) and her wrist skin within 0.3 °C of its expected value; the trend over the period.
4. **Alerts table**: each DRINK / COOL / CHECK alert with the sensors at that moment (air, humidity, wrist skin, pulse),
   what she did in the next 30 min, and the recovery.
5. **Sleep** (estimated from wrist stillness) and **movement** on hot vs normal days.
6. **Her heat reaction in plain words** (e.g. "In heat her heart rises above her normal: about +3.0 bpm for each °C…",
   "After a heat episode she recovers in about 55 min…"), each with a confidence (how much data it rests on).

Core body temperature: never printed by default. `HeatReportBuilder.SHOW_TWIN_ESTIMATE` (one constant, default
`false`) adds a Body Twin section: the band model's core-temperature estimate per day, titled "MODEL ESTIMATE (Body
Twin), not measured" with a red "switched on by the team" box.

PDF (`Views/Report/HeatReportPDF.swift`, UIGraphicsPDFRenderer, A4, 7 pages): cover + disclaimer (Greek AND English)
+ her heat reaction + at a glance · wrist skin, air, humidity · heart and recovery · alerts table · day by day + hours
of heat at home · sleep and movement (+ the twin section when switched on) · LAST: questions for the doctor, her
medicines ("ask your doctor whether this matters in heat"), privacy. Made on the phone, shared only through the share
sheet (Report screen: consent the first time, 7 / 14 / 30 days, name on / off, language). Elder mode can turn the
report off. Demo: a constructed month fed minute by minute through the real ledger, SIMULATION on every page.

Linux sample: `HG_REPORT_JSON=/tmp/report.json ios/tools/linux_xctest/run.sh` writes the model (also `_el` and `_twin`),
then `python3 -I ios/tools/report_mirror.py /tmp/report.json report.pdf` draws it with the same block / chart / table
drawing (Liberation Sans instead of SF Pro). The phone's own PDF and the Swift Charts screen need Xcode / an iPhone.

## Her Day changes (Nov 18)

- An outing now collides when ANY part of it — start to start + her typical length — overlaps a hot window, not only
  when it starts inside one. "Go before" stays the latest safe start in 15-min steps; frames are unchanged.
- Demo controls › **«Her Day: hotter tomorrow ("go after")»** swaps tomorrow for heat-wave day 3 (hot from 08:00):
  church 08:30 cannot end before the heat if it starts at 07:00 or later, so the band suggests «εκκλησία μετά τις 19:30»
  while the market and the café still go before. (With the rule "before first", a "go after" only appears on a day that
  is already hot early in the morning.)

---

## Wearer profile

**Ρυθμίσεις › Ο άνθρωπός σας** — name and phone (used by «Θα τηλεφωνήσω»), age, sex, BMI, medicines, resting heart rate,
and today's thermometer reading (display only: it narrows the shown range, it does not change the alarms).

«Αποστολή στο βραχιόλι» sends:
- PROFILE frames (0x13): field 2 = resting heart rate (40–100), field 0 = thermometer reading (if typed, 34–42 °C),
  field 5 = medicine bits (1 beta-blocker, 2 diuretic, 4 low-sweat drug, 8 ACE/ARB, 16 other HR-limiting drug /
  pacemaker). Note: firmware 0.9.5 (Bluetooth security) refuses field 5 — on that firmware the medicines arrive through
  the console line below;
- the line `profile <age> <sex> <bmi> <meds>` to the band's console (Nordic UART), when the band offers it.
  If it does not, type the line shown under the section in the band's Serial Monitor over USB.

---

## Check it

Tower checks (no network in any test): `HeatGuardianTests/TowerTests.swift` — the band's 0.9.17 ladder frames
(`ladder_vectors_fw.json`, made by `tools/fw_ladder_vectors.c` from the band's own ladder + packer, commit a486805),
unknown types ignored, SMS texts el / en, the routing table, the outbox (dedupe, rate limit, backoff, expiry), the
Twilio request (URL, form body, Basic auth) and the engine with a fake HTTP client.

- In Xcode: **Product › Test** (⌘U) runs `HeatGuardianTests` (frame decoder and command encoders against the dashboard's
  test vectors, on an iPhone Simulator).
- Without a Mac, from the repository root:

```
python3 -I ios/tools/mirror_frames.py
```

```
python3 ios/tools/check_xcodeproj.py
```

Her Day vectors are generated by `python3 -I ios/tools/gen_herday_vectors.py` (from the Python mirror) and checked by
the mirror, by `HerDayTests` and against the band's own `herday_vectors_fw.json` (copy of fw/09_guardian/herday_vectors.json).
With a Linux Swift toolchain on PATH, two more checks: `ios/tools/linux_typecheck/run.sh` type-checks ALL app files
against API stubs (incl. CoreLocation / MapKit), and `ios/tools/linux_xctest/run.sh` RUNS the XCTests of the non-UI code.

`mirror_frames.py` is a line-by-line Python mirror of `Frames.swift` run on the same vectors; `check_xcodeproj.py`
checks the project file's structure (needs `pip install pbxproj openstep_parser`). `tools/LinuxCheck.swift` compiles
the non-UI Swift with a Linux Swift toolchain and runs the same checks (the command is at the top of the file).

If Xcode refuses to open the project file, regenerate it with XcodeGen (`project.yml` describes the same project):

```
brew install xcodegen
```

```
cd ios && xcodegen
```

---

## Files

| Path | What |
|---|---|
| `HeatGuardian/BLE/Frames.swift` | STATUS / INFO decoders, TIME / FAMILY_ACK / PROFILE / CONSENT / FORECAST / SAFE_HOURS encoders (port of `dashboard/js/hgframes.js`, layout `guardian/c/hg_frames.h`) |
| `HeatGuardian/BLE/BandLink.swift` | CoreBluetooth: scan, connect, pairing, subscribe, TIME on connect, serialised writes, background re-connect |
| `HeatGuardian/Model/AppModel.swift` | the one ingest path (live + demo), family-alert rule, acks, plan/profile sending, history |
| `HeatGuardian/Model/Replay.swift` | recordings + the demo player (1× / 10× / 60×) |
| `HeatGuardian/Model/Plan.swift`, `Week.swift`, `Strings.swift` | Tomorrow plan, weekly trends, Greek / English text |
| `HeatGuardian/BLE/EcoFrames.swift` | EVENTS decoder, CMD 0x16–0x1A, and Her Day: 0x1B DAY_PLAN, 0x1C VISIT, EVENTS 9 VISIT / 10 PLAN_ITEM, place types |
| `HeatGuardian/Model/HerDay.swift`, `HerDayRoutine.swift`, `HerDayBand.swift`, `HerDayDemo.swift` | Her Day engine, routine model + home rule + POI mapping, what the band holds (from its events), the demo |
| `HeatGuardian/Model/Visits.swift`, `VisitMonitor.swift`, `AppModel+HerDay.swift` | her on-device visit store + VISIT queue, Core Location Visits + MapKit lookup, sending / demo glue |
| `HeatGuardian/Model/AlertQuality.swift`, `AppModel+Quality.swift` | band 0.9.9 alert quality: the week's card, «Back to normal», demo events |
| `HeatGuardian/Model/ReportLedger.swift`, `HeatBody.swift`, `HeatReport.swift`, `HeatReportDemo.swift`, `Medications.swift`, `AppModel+Report.swift`; `Views/Report/` | her body in heat + the doctor's report: 5-min day records, analysis, model (blocks, chart / table specs), demo month, medicines, PDF renderer, Swift Charts screen, report screen |
| `HeatGuardian/Views/*` | Now, Alert, Tomorrow, Week, Settings, the 24 h chart; Her Day: `Family/HerDaySection.swift`, `Elder/HerDayCard.swift`, `Elder/PlacesSection.swift` |
| `HeatGuardian/Resources/` | `plan.json`, `sim_heatwave.json`, `htt_chamber.json` (copies from `dashboard/`), `chime.wav` |
| `HeatGuardianTests/` | XCTest + the vector files |
| `HeatGuardian/Model/Tower/` | THE TOWER: `LadderEvents` (EVENTS 14–21), `SMSText`, `SMSRouting`, `Outbox`, `Twilio`, `TowerKeychain`, `TowerEngine`, `DayStory` (history), `Balance`; glue `Model/AppModel+Tower.swift` |
| `HeatGuardian/Views/Setup/`, `Views/Tower/` | Setup; her screen, history, Settings › Tower + outbox + family contacts; `Views/Report/MailView.swift` |
| `tools/` | project generator + checker, Python mirror, Linux Swift check, HTML mock renderer |
| `shots/mock_*.png` | **HTML mocks** of the screens (not screenshots of the app) |
