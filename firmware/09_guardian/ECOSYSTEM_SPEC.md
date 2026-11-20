# Heat Guardian ecosystem spec v1 (band 0.9.7 + iPhone app), demo = phone nearby

Owner: Foivos. Status: DRAFT, needs his OK on the Greek strings (section 6). Band side built as firmware 0.9.7 (branch b12-ecosystem); final frame layouts in 5c. "Her Day" (HERDAY_SPEC.md) built as band 0.9.8 (branch b13-herday): see 5d. Alert quality built as band 0.9.9 (branch b14-alerts): see 5e.
Scope: one system on two devices over Bluetooth. No internet, no cloud (roadmap: home relay).
Hard rules: the FROZEN engine (frozen/, fz_*.c, hg_cmd_parse) is not changed; new opcodes are parsed
in the firmware layer BEFORE the frozen parser. Board B pins: never use D0 / D9.

## 1. The five rules
1. One truth: band and app show the same state, the same Greek phrase, the same icon/colour.
2. Every action echoes: a press on the band appears in the app; a family tap appears on the band.
3. Band = sense, guide, one-press answers. App = plan, history, family. No duplicate jobs.
4. Never breaks apart: the band runs the whole day alone, keeps an event log, and the app catches up
   on reconnect (nothing lost, nothing shown as live that is not live).
5. Same design language on both: icon set {check, drop, house, shutters, window, sun-clock, warning,
   phone}, colours {green OK, blue water, orange heat, red danger, grey offline}.

## 2. Prevention loop (new, firmware layer "planner", runs once a minute after guardianMinute())
Inputs already on the band: the 24-h forecast buffer from the Tomorrow Engine (per hour: indoor T_in,
RH_in, flags heat-day / night-heat / safe-hour), safe-hours bitmap, local clock, guardian state, room
temperature now (SHTC3), sleep window (twin/routine).

Nudges (each at most once per day unless stated):
| id | when | screen | haptic |
|---|---|---|---|
| N1 BRIEF | first wake-up press after 07:00, or 08:30, on a heat-day | «Σήμερα ζέστη. Βγείτε πριν τις HH:00» (HH = end of the first safe window) or «Σήμερα ζέστη. Μείνετε μέσα» if none | soft |
| N2 LAST_COOL | 30 min before the morning safe window ends, heat-day | «Τελευταία δροσερή ώρα για έξοδο» | soft |
| N3 SHUTTERS | between 09:00 and 13:00, the first hour where forecast T_in will reach ≥ 28 °C within the next 2 h | «Κλείστε τα παντζούρια» | soft |
| N4 WATER | during hours with forecast T_in ≥ 28 °C or room ≥ 28 °C, every 90 min awake; max 4/day | «Ώρα για ένα ποτήρι νερό» | soft double |
| N5 AIR | 21:30 on a night-heat day (or room ≥ 27 °C at 21:30) | «Ανοίξτε τα παράθυρα να δροσίσει» | soft |
Without a forecast only N4 (room-based) runs.

Caps and priority (must hold):
- Max 6 nudges per day in total; at least 60 min between nudges; none inside the sleep window.
- Guardian warnings (DRINK, COOL, CHECK, DANGER, HELP, NOT_WORN, BATTERY) always win: no nudge while one
  is active; a nudge on screen is replaced by a warning immediately.
- A short press on a nudge screen = DONE (✓ toast «Μπράβο ✓», 3 s). If a CHECK is open, a press is
  "I'm OK" first (existing rule) and never counted as nudge DONE.
- Nudge screen stays up to 10 min, then MISSED (no repeat of the same nudge that day except N4).
- A N4 DONE resets the N4 90-min timer.

## 3. Main face (always-on view when no warning/nudge)
- Big clock HH:MM (centre), date line «Τρι 17 Νοε».
- Status ring around the clock in the state colour (green OK / orange heat-day / red danger).
- Bottom row: room °C + trend arrow (↑ / → / ↓ from the last 30 min, ±0.5 °C), battery %.
- Next-hours line under the clock when a forecast exists: «Από 14:00 πολλή ζέστη» (first forecast hour
  ≥ 30 °C later today) or «Δροσερό απόγευμα» / nothing.
- Short press when awake cycles MAIN → PLAN (safe hours) → MAIN. A wake press only wakes (0.9.6 rule).

## 4. Warnings explain themselves
Under each DRINK/COOL/CHECK/DANGER screen one reason line from FW.last_out.why (+ room °C):
| why bit | line |
|---|---|
| ENV_LIMIT | «Πολλή ζέστη στο σπίτι NN°» |
| TIME_IN_HEAT | «Πολλές ώρες στη ζέστη» |
| BODY / NN / DANGER_P | «Το σώμα ζεσταίνεται» |
| NO_RESPONSE_G | «Δεν απαντήσατε» |
| UNCERTAIN only | no line |
Priority if several bits: BODY/NN/DANGER_P > ENV_LIMIT > TIME_IN_HEAT.

## 5. Echo between devices (BLE)
New characteristic EVENTS (UUID HG_UUID("0004"), read + notify), 20-byte frames, CRC-8 like STATUS:
[0]=0x03 version 1 | [1-2] u16 seq (monotonic per boot, wraps) | [3-4] u16 boot_count | [5-8] u32 unix
(0 if clock not set) | [9] type | [10] id/arg | [11-18] reserved 0 | [19] crc8.
Types: 1 NUDGE_SHOWN(id) 2 NUDGE_DONE(id) 3 NUDGE_MISSED(id) 4 IM_OK 5 HELP 6 HELP_CANCEL
7 FAMILY_MSG_SHOWN(arg) 8 WARN_SHOWN(state).
Band keeps the last 64 events in a RAM ring (also written to events.txt as today).
New CMD opcodes (firmware layer, before hg_cmd_parse; 20-byte frames, CRC-8 as existing CMDs):
- 0x16 SYNC_EVENTS: [1-2] u16 since_seq, [3-4] u16 boot_count → band re-notifies all ring events after
  since_seq for that boot (all of them if boot differs).
- 0x17 FAMILY_MSG: [1] msg 1 «Σας καλεί η {name}» 2 «Έρχεται η {name}» 3 «Η {name} είδε το μήνυμα ✓»;
  band shows it 60 s with a soft tick, logs FAMILY_MSG_SHOWN.
- 0x18 FAMILY_NAME: [1..14] UTF-8 name (max 14 bytes, NUL padded), saved to flash; default «οικογένεια».
After HELP or DANGER family alert: when the app sends FAMILY_ACK, the band shows
«Η οικογένεια ειδοποιήθηκε ✓» (from the existing ack path).

App side:
- On connect: TIME, then SYNC_EVENTS(last seq seen, boot) → merges events into a Today timeline.
- Today tab = the day's plan (from the same Tomorrow plan it sent) with each nudge: upcoming / shown /
  done ✓ (time) / missed. Same icons and Greek phrases as the band.
- Alert screen buttons: «Σας καλώ» → FAMILY_ACK 2 + FAMILY_MSG 1; «Έρχομαι» → FAMILY_MSG 2.
- Settings: family member name → FAMILY_NAME.
- Offline: grey hero «Χωρίς σύνδεση», last sync time; on reconnect catch up silently, then live.

## 5b. Optional profile: medicines + routine (Foivos, Nov 16)
Purpose: let the system start useful on day 1 instead of waiting days to learn her.
Everything is OPTIONAL; empty = learn from scratch as today.
- Medicines (already supported, PROFILE field 5): beta-blocker, diuretic, low-sweat drugs
  (anticholinergic / antipsychotic / antihistamine), ACE/ARB, other HR-limiting / pacemaker.
  Plain-language checkboxes in Greek, no drug names required.
- Routine (new): usual wake time, bedtime, afternoon nap (from-to), usual time(s) out of the house
  (up to 2 windows), A/C at home yes/no, home type (ground floor / middle / top floor, old / insulated
  -> Tomorrow Engine home class A–D).
- New CMD 0x19 ROUTINE_SEED (firmware layer): wake hh:mm, bed hh:mm, nap from/to, out1 from/to,
  out2 from/to, ac flag. Stored in flash.
- Where it is used (no frozen-engine change, sealed results stay valid):
  * planner: nudge times follow her day (brief at her wake time, no nudge in her nap / sleep, "last cool
    hour to go out" aligned to her usual out window, A/C nudge «Ανάψτε το κλιματιστικό» if ac = yes);
  * app: Tomorrow simulation uses her routine + home class instead of defaults;
  * learned routine (Body Twin) still learns on its own; where the band has learned ≥ 3 days, the learned
    times win over the stated ones and the app shows «Το βραχιόλι έμαθε: ξυπνάτε ~07:10».
- NOT done now: seeding the frozen routine learner itself (would change tested engine behaviour; needs a
  new sealed exam first).

## 5c. FINAL FRAME LAYOUTS (band 0.9.7, implemented; test vectors: fw/09_guardian/eco_vectors.json)
All frames are exactly 20 bytes, little-endian; byte 19 = CRC-8 (poly 0x07, init 0x00, no reflection, no final xor;
check("123456789") = 0xF4) over bytes 0..18 - the same function as STATUS and the existing CMDs. New CMD opcodes are parsed
by the firmware layer BEFORE the frozen hg_cmd_parse (which answers ERR_OP for them); 0x10-0x14 and 0x1F are unchanged.
Replies on the BLE UART / USB console: `# CMD ok op=0x16` or `# CMD error <rc> op=..` (rc -1 short, -2 CRC, -4 field).

EVENTS (characteristic HG_UUID("0004") = 0c760004-038b-46d5-8532-954dd1c5e01d, read + notify)
| byte | field |
|---|---|
| 0 | 0x03 (version 1 of this frame) |
| 1-2 | u16 seq: 1, 2, ... per boot; wraps 0xFFFF -> 1 (0 is never used: "nothing seen") |
| 3-4 | u16 boot_count (low 16 bits; same value as INFO) |
| 5-8 | u32 unix seconds UTC (0 = band clock not set) |
| 9 | type: 1 NUDGE_SHOWN, 2 NUDGE_DONE, 3 NUDGE_MISSED, 4 IM_OK, 5 HELP, 6 HELP_CANCEL, 7 FAMILY_MSG_SHOWN, 8 WARN_SHOWN (0.9.8: 9 VISIT, 10 PLAN_ITEM, see 5d; 0.9.9: 11 ALERT_HELD, 12 ALL_CLEAR, 13 SCORE, see 5e) |
| 10 | arg: nudge id (types 1-3); source 1 band button / 2 phone (types 4, 5, 6); msg 1-3 (type 7); guardian state HG_ST_* (type 8: 1 DRINK 2 COOL 3 CHECK 4 DANGER 6 NOT_WORN 7 BATTERY 8 HELP) |
| 11-18 | 0 (types 1-8; payload of types 9 and 10, see 5d) |
| 19 | CRC-8 |
Nudge ids: 1 BRIEF, 2 LAST_COOL, 3 SHUTTERS (removed in 0.9.8, id never reused), 4 WATER, 5 AIR, 6 AC («Ανάψτε το κλιματιστικό», 5b), 7 EVENING_BRIEF, 8 LEAVE_HOT (0.9.8).
The read value is always the newest event. The ring keeps the last 64 events (RAM; each one is also a line
`EVT seq=.. type=.. <NAME> arg=.. unix=..` in events.txt). After a connect the band notifies only new events (<= 2 per loop
pass, in seq order); the app catches up with SYNC_EVENTS. A NUDGE_MISSED is logged when a nudge times out (10 min) and when
a warning / HELP replaces it.

| op | name | bytes 1..18 |
|---|---|---|
| 0x16 | SYNC_EVENTS | [1-2] u16 since_seq, [3-4] u16 boot_count, [5-18] 0. Band re-notifies every ring event after since_seq (since_seq 0 = all). If boot_count differs from the band's: all of the ring. |
| 0x17 | FAMILY_MSG | [1] msg 1 «{name}: σας καλεί», 2 «{name}: έρχεται», 3 «{name}: είδε το μήνυμα ✓»; [2-18] 0. Shown 60 s (phone icon) with a soft tick, logs FAMILY_MSG_SHOWN; a press closes it. msg 0 or > 3 = field error. |
| 0x18 | FAMILY_NAME | [1-14] UTF-8 name, NUL padded (max 14 bytes; must be well-formed UTF-8, no control chars, nothing after the first NUL); [15-18] 0. Empty = default «οικογένεια». Saved in /famname.bin next to /profile.bin. |
| 0x19 | ROUTINE_SEED | [1] wake_h [2] wake_m [3] bed_h [4] bed_m [5] nap_from_h [6] nap_from_m [7] nap_to_h [8] nap_to_m [9] out1_from_h [10] out1_from_m [11] out1_to_h [12] out1_to_m [13] out2_from_h [14] out2_from_m [15] out2_to_h [16] out2_to_m [17] flags (bit0 A/C at home, bits 1-7 = 0; 0xFF = not stated) [18] 0. Each h/m pair: h 0-23, m 0-59, or 0xFF 0xFF = not set (a half-set pair is a field error). Saved in /routine.bin; used ONLY by the planner. |
| 0x1A | ELDER_ACTION | [1] action, [2] nudge id (action 2 only, 1-6; 1-8 from 0.9.8), [3-18] 0. The elder-mode phone app presses the band button for her; each action takes the band's own path and emits the same EVENTS frame with arg 2 = phone. 1 HELP = a 2-s long press (marker help, toast, haptics); ignored if HELP is already active (never a cancel). 2 NUDGE_DONE = a press on that nudge's screen; ignored unless that nudge is open. 3 HELP_CANCEL = the band's second long press (frozen ack-type-3 path). 4 IM_OK = a short press answering an open CHECK; ignored otherwise. Action 0 or > 4 = field error. |

Planner details as built (sections 2 and 5b):
- Clock unknown -> no nudge. The forecast buffer is read by local hour, exactly as the guardian reads it.
- Sleep window for "no nudge": learned routine when the Body Twin has >= 3 days, else the stated bed/wake (0x19), else a
  learned window with fewer days, else 22:00-08:00 (the routine module's default). Stated nap = no nudge.
- N1 BRIEF: first short press after her wake time (learned >= 3 days, else stated, else 07:00), or automatically at wake
  time + 90 min (default 08:30), before 12:00, heat-day only. A press proves she is awake, so the press path ignores the
  sleep window. HH = end of the first safe window that has not ended yet (SAFE_HOURS bitmap, else forecast flag bit 2).
- N2 LAST_COOL: 30 min before the end of the first safe window that starts before 12:00 (fires in [end-30, end-5) min).
  5b alignment: skipped when her stated outing (out1/out2) lies wholly inside that safe window (she already goes out cool).
- N3 SHUTTERS 09:00-13:00 when forecast T_in >= 28 C this hour or in the next 2 h. N6 AC (5b, A/C stated yes): first hot
  hour (forecast T_in or room >= 28 C). N5 AIR 21:30-22:15 on night-heat (or room >= 27 C). N4 WATER: hot hour, every 90 min
  from the last WATER shown or DONE, max 4/day. Without a forecast only N4 (room) runs.
- Priority in one minute: N1 > N2 > N3 > N6 > N5 > N4. On a night-heat day the 6th daily slot is kept for N5 AIR (unless
  21:30 falls in her sleep window), so four WATERs cannot starve the evening nudge.
- The frozen guardian's own bedtime nudge («Δροσίστε το δωμάτιο») counts for the 60-min spacing.
- A nudge keeps the screen on 2 min (battery); it stays active (shown again on any wake) until 10 min, then MISSED.
- Planner counters live in RAM: a reboot starts a fresh day count.

## 5d. HER DAY, as built (band 0.9.8; spec: HERDAY_SPEC.md; test vectors: fw/09_guardian/herday_vectors.json)
HERDAY_SPEC.md (shared, Nov 17) is the source of truth for the idea, the place types, the frames and the app side. This section lists
only what the band does where the spec left room. Same frame rules as 5c (20 B, CRC-8 at byte 19, parsed by the firmware layer
BEFORE the frozen hg_cmd_parse, which answers ERR_OP for 0x1B/0x1C; replies `# CMD ok op=0x1b` / `# CMD error <rc> op=..`).

CMD 0x1B DAY_PLAN, field errors (rc -4), beyond the spec's list (day > 1, kind 0 or > 3, place > 7, h > 23, m > 59, index > n, n > 6):
- every h/m pair (usual 6-7, suggested 8-9) is h 0-23 + m 0-59, or 0xFF 0xFF; a half-set pair is an error (as 0x19).
- hot window: from_h 0-23; to_h is EXCLUSIVE so it may be 24 (= until midnight); 25+ is an error. Kind 1: from_h <= to_h (equal = no window).
- index 0 is allowed only with n 0 (= clear the day; the item bytes are then ignored).
- kind 1 needs direction 1 or 2 and a suggested time; kind 2 needs a suggested time (nothing to say otherwise).
- kind 3: heat-wave day 0-31 (5 bits in the PLAN_ITEM echo).
- bytes 15-18 are not checked. Fields a kind does not use are stored and echoed as 0 (kind 1 usual 0xFF 0xFF stays n/a).
Store: a staged set per day; it RESTARTS when n changes or an index arrives twice; the stored day is replaced only when every index
1..n has arrived (so index == n with a gap does not commit). Today and tomorrow are independent. /dayplan.bin (148 B: magic,
version, local day index, 2 x (n + 6 x 11 B), CRC-32) is written on every commit and every roll. The plan belongs to the band's
local day: at local midnight tomorrow becomes today and tomorrow is empty; a jump of 2+ days empties both; a plan that arrives
before the clock is set belongs to the first day the clock shows. A half-received set is dropped at midnight.
Echo: on every commit the band logs one EVENTS type 10 per stored item of that day. A clear (n 0) commits an empty day and logs
nothing (gap: the app cannot see a clear from another phone; it can rely on its own sends). peak_c is not echoed (no room).

CMD 0x1C VISIT: event 1/2 and place 0-7 are checked (field error otherwise); bytes 7-18 are not checked. Each one is logged as EVENTS
type 9 (arg place, [11] event, [12-15] the visit's u32 unix; the frame's own [5-8] is when the band logged it).
A LEAVE from home starts N8 only when it is "fresh": band clock set and |band now - visit unix| <= 10 min (a VISIT queued while
disconnected is history). An ARRIVE at home counts as "at home" for the N8 re-arm until the next LEAVE / ARRIVE elsewhere.

EVENTS layout of the new types (version byte stays 0x03):
| byte | type 9 VISIT | type 10 PLAN_ITEM |
|---|---|---|
| 10 | place type | kind |
| 11 | 1 arrive / 2 leave | place |
| 12-15 | u32 unix of the visit | usual_h, usual_m, sugg_h, sugg_m |
| 16-17 | 0 | hot_from_h, hot_to_h |
| 18 | 0 | day (bit 0) \| direction << 1 (bits 1-2) \| heatwave_day << 3 (bits 3-7) |

Planner (0.9.8), on top of "Planner details as built":
- Priority in one minute: N8 (own path) > N1 > N2 > N6 > N5 > N7 > N4. N3 SHUTTERS is gone.
- N1: also fires on a day whose plan has a kind-1 item when the forecast does not flag a heat-day (same times, same press rule).
  Text = the kind-1 item with the earliest usual time (else suggested time); HH:MM = its suggested time. Otherwise 0.9.7 text.
- N5 AIR with a kind-2 item today: [suggested, +45 min), no forecast or night-heat flag needed; else 0.9.7 (21:30-22:15).
- N7 EVENING_BRIEF: window [bedtime - 60, bedtime) with bedtime = learned (>= 3 days) > stated 0x19 > 22:00 (so 21:00 by default);
  an after-midnight bedtime gives 23:00, a bedtime before 19:00 gives 18:00. Text from tomorrow's earliest kind-1 item, else the
  kind-3 line. AIR wins: while an AIR is still due tonight and N7 now would block it by the 60-min spacing, N7 waits (on a night-heat
  day with the default 22:00 bedtime and no kind-2 item this means no N7 that evening). Icon: sun-clock.
- Reserve: the last daily slots are kept for the evening nudges still due tonight (N5 AIR on a night-heat / kind-2 day, N7 when
  tomorrow has kind 1/3), so WATER etc. cannot starve them. N8 ignores the reserve (it only needs count < 6).
- N8 LEAVE_HOT: "leave" = the frozen home/out state goes HOME -> TRANSIT or OUT (minute step), or a fresh VISIT LEAVE from home.
  A leave disarms N8 whether or not it fires (one outing = one chance); it re-arms after >= 30 min at home (band HOME or a VISIT
  ARRIVE home), measured on the local clock. After a leave, N8 stays eligible for 10 min: it fires the first minute in which it is
  hot (a kind-1 hot window of today's plan, or a heat-day hour that is not safe per SAFE_HOURS / forecast flag; a kind-3 day without
  any safe-hours information counts only its kind-1 windows), no warning is on, she is not in her sleep window, N8 < 2 today and
  nudges < 6 today. It replaces an open lower nudge (that one is MISSED) and restarts the 60-min spacing for the others. Icon: orange drop.
- A nudge that shows N7/N8 (console `nudge 7|8`) needs no caps; `nudge 7` is refused without a tomorrow plan.
- Counters (N8 today, armed, home-since) live in RAM like the others; the day plan itself survives a reboot (/dayplan.bin).
BLE: `Bluefruit.begin(2, 0)` (2 peripheral links, BANDWIDTH_LOW). Advertising restarts after a connect / disconnect while fewer than
2 phones are connected. STATUS and EVENTS are notified to every connected phone; each link has its own EVENTS cursor, and SYNC_EVENTS
re-sends only to the phone that asked (a USB `frame` SYNC applies to all). The home/out input uses the strongest connected phone's RSSI.
The console / BLE UART replies still go to the most recent link.

## 5e. ALERT QUALITY, as built (band 0.9.9; hg_fw_alert.c/.h; host test fw/tools/test_alerts.c; scenes fw/09_guardian/scenes)
Source: the research report "Heat Guardian band app ecosystem" (ranked list 1-5) and its alert_quality notes. The layer reads the frozen
guardian's minute output and decides only what the band DOES: buzz, wake the screen, log WARN_SHOWN, start a planner nudge. The frozen
state, the STATUS frame, the screen content when she looks, and the frozen CHECK / family path are unchanged.

What changes for the app (STATUS and frames 1-10 are unchanged; version byte stays 0x03, unknown types must be ignored):
- WARN_SHOWN (type 8) for DRINK (1) and COOL (2) is now logged when the band actually SHOWS it (persisted, valid input), not at the frozen
  onset. STATUS can say DRINK / COOL a few minutes before (or without) a WARN_SHOWN: the app shows that as "watching" ("Παρακολουθούμε"),
  not as an alert. CHECK / DANGER / HELP / NOT_WORN / BATTERY WARN_SHOWN are unchanged.
- New EVENTS types (bytes 11-18; unused bytes 0):

| byte | type 11 ALERT_HELD | type 12 ALL_CLEAR | type 13 SCORE (arg = page) |
|---|---|---|---|
| 10 | what: 1 DRINK, 2 COOL, 3 NUDGE, 4 BEDTIME (frozen «Δροσίστε το δωμάτιο» tip) | peak: 1 DRINK, 2 COOL, 3 CHECK / DANGER | page 0, 1, 2 |
| 11 | reason: 1 NOT_WORN 2 LOOSE 3 SKIN (implausible) 4 PPG (poor pulse signal) 5 SHOWER 6 SUN 7 PERSIST (self-corrected) 8 REPEAT (same episode) 9 ONE_EVIDENCE | episode minutes, u16 LE (11-12) | page 0: sent NUDGE, DRINK, COOL, COOL_SOFT, CHECK, FAMILY, ALL_CLEAR, BEDTIME (u8 each, saturating, since boot) |
| 12 | nudge id (what 3) or HG_ST_* state (what 1/2) | (cont.) | page 1: held back per reason 1-8 |
| 13 | 0 | 1 = the family was called in this episode | page 2: [11] held ONE_EVIDENCE [12] acknowledged [13] missed [14] thermal CHECKs with one kind of evidence (audit) [15-16] avg time to acknowledge s, u16 [17-18] max s, u16 |
| 14 | 0 | 1 = shown with a soft tick | |

  ALERT_HELD: one per alert per hold (not per minute), max 16 frames a day (the events2.txt line and counter are always kept).
  ALL_CLEAR: one per shown episode, when it ends; the family app shows "Back to normal (HH:MM), N min" and closes the alert.
  SCORE: on the console `score` and at local midnight (counters since boot; the app keeps the daily difference).
- Band screen «Πάλι όλα καλά» (green check circle, 10 s) with the ALL_CLEAR. Needs Foivos's OK (section 6).

Rules and numbers (DESIGN unless a source is named; set again on the wear test, never to make a rate pass):
| rule | value | why |
|---|---|---|
| validity: worn | frozen hg_contact worn == 2 (1 loose / 0 off = UNKNOWN) | half of the remaining hospital alarms came from a removed sensor (Welch 2011, report rank 1) |
| validity: skin plausible | 28.0-40.5 °C | outside it the skin sensor is not on a wrist |
| validity: pulse | quality < 3 (no skin, low PI, motion) in >= 3 of the last 5 min = UNKNOWN for DRINK, and pulse not counted as body evidence; "irregular" (3) is NOT poor (atrial fibrillation, ~10 % at 80+, as the frozen contact rule) | Fitbit analyses only clean windows (report section 2) |
| validity: shower | RH >= 80 % after a >= 20 %RH rise within 5 min AND a >= 1.0 °C skin step; until RH < 70 %, then 15 min drying; 45 min at most | report rank 1 ("sudden humidity jumps"); both conditions so humid weather alone never hides an alert; UNTESTED guess, bounded |
| validity: sun on the sensor | air sensor +4 °C within 5 min while the skin moved <= 1 °C and the outward (REF, else air) sensor >= 1.5 °C over skin; until < 1 °C (45 min at most), then 10 min cool-down | report rank 1 ("air sensor heats much faster than skin"); UNTESTED guess, bounded. Effect: DRINK waits, the air is not counted as exposure, the planner gets no room value |
| what UNKNOWN blocks | DRINK: any bit. COOL: off / loose / skin / shower (sun and pulse only remove evidence). Nudges: off / skin / shower (an open nudge is not cancelled). Bedtime tip buzz: off / skin / shower | "unknown, never high" |
| hold bound | DRINK 60 min, COOL 30 min of continuous hold while the frozen tier stays on -> shown, logged `hold limit` | a guess must never hide a real tier for good |
| persistence | DRINK 5, COOL 3 consecutive valid minutes of the frozen state; a minute counts only if f20 >= f20 at the run start - 0.05 °C (else the count restarts); a normal minute resets; backstop: shown after 15 / 10 valid frozen minutes even if f20 wobbles | "for example 5" (report rank 2); 70.7 % of alarms self-correct within 60 s (BMC Nursing 2016); a 15-s delay removed 60-70 % (Welch); heat strain builds over tens of minutes. The frozen tier already debounces 2 min and holds 10 min, so the f20 condition is what filters a short excursion |
| CHECK / DANGER persistence | 0 (pass through) | the frozen guardian already debounces (2 min, Marble 5 min) and its CHECK runs the family timer: delaying the question would shorten her time to answer |
| hysteresis | a shown episode is latched (no repeat buzz; `REPEAT` logged); ends after 10 calm valid minutes AND f20 <= f20 when shown - 0.20 °C, or after 60 calm minutes | "enter at one level, leave at a lower one" (report rank 2); 0.20 °C = twice the frozen uncertainty lowering (0.10) |
| two kinds of evidence | EXPOSURE = trusted air >= 28 °C at some minute of the last 60 (= the frozen Marble heat gate HG_MB_WARM_C), or frozen ENV_LIMIT / TIME_IN_HEAT with trusted air, or a forecast heat-day hour. BODY = frozen BODY / NN / DANGER_P reasons, or strain >= 5, or pulse >= Body Twin resting + 15 bpm while still (a_std <= 0.05 g) in >= 3 of 5 min | pulse alone cannot pick out strained older adults (Carrillo 2024); Apple Vitals notifies only when several metrics agree (report rank 5). +15 bpm and strain 5 are DESIGN |
| COOL with one kind | both: full COOL pattern. Exposure only: soft tick (nudge strength). Body only: held (it has nothing to act on: she is not in heat), 30 min at most, then soft. A soft COOL is upgraded once to the full pattern if both later agree | "either alone = nudge at most" |
| CHECK with one kind | NOT held. Counted in `check_one_evidence_audit` and logged | the frozen CHECK starts the family timer (5 / 10 min); holding the question would let the family be called before she was asked |
| speak on change | one buzz per episode start or worsening (DRINK -> COOL; CHECK as the frozen guardian gives it, incl. its re-asks at 2 and 5 min = the ladder before the family call). Easing or a frozen state change into OK / DRINK / COOL does not wake the screen | UCSF: alarm at onset and termination (report rank 4) |
| all-clear | when a shown episode ends: «Πάλι όλα καλά» 10 s + ALL_CLEAR; soft tick only if it reached COOL / thermal CHECK or the family was called | Kenzen's all-clear; caregivers want to know what happened after (report rank 4) |
| scorecard | sent per type, held back per reason, acknowledged (nudge DONE + I'm OK on a CHECK), missed (nudge MISSED + unanswered CHECK -> family), time to acknowledge (avg / max s), unknown minutes | report rank 3 and section 6 |
| planner room value | the lowest trusted air value of the last 5 minutes (NaN if any is untrusted / missing) | persistence for the room-based nudges (N4, N5 room rule, N6) |

Staged scenes (fw/09_guardian/scenes/*.csv; minute keyframes, linear between rows; columns min, skin, REF, air, RH, pulse, pulse quality,
PI, a_std, z-angle, button; header `expect=` = the interruptions in order). Replayed after a calm 24-h warm-up through the real path
(hg_fw -> frozen guardian -> rules layer -> planner). The app and the demo video can play the same files.
| scene | expected | 0.9.8 | 0.9.9 |
|---|---|---|---|
| shower (20 min, 27.5 °C flat) | none | 2 (WATER nudge, DRINK) | 0 (nudge PERSIST, DRINK SHOWER) |
| band on a table 3 h | none | 0 | 0 |
| brisk walk 60 min at 17 °C | none | 2 (DRINK, COOL) | 0 (DRINK PPG, COOL ONE_EVIDENCE) |
| sun on the sensor 45 min, 26 °C room | none | 1 (WATER nudge) | 0 (nudge PERSIST, then room untrusted) |
| slow build-up, hot flat 29 -> 37 °C over 6 h | WATER, DRINK, CHECK, family, all-clear | WATER x2, DRINK, CHECK (+2 re-asks), family | same + all-clear; DRINK 4 min later than the frozen onset |
| fast build-up, 37 °C flat, CHECK answered | COOL, CHECK, all-clear | WATER, DRINK, COOL, CHECK | COOL (2 min after the frozen onset), CHECK (same minute), all-clear |
These are SYNTHETIC traces made to look like the scenes, not recordings: they prove the rules do what is written, not that the signatures
match a real shower or real sun. Record each scene on the band (events2.txt + `score`) before quoting numbers.

## 5f. UI ENGINE + ACTION LADDER, as built (band 0.9.17; hg_fw_ui.c, hg_fw_ladder.c; host tests fw/tools/test_ui.c, test_ladder.c)

New EVENTS types (frame layout unchanged, version byte 0x03). Apps before 0.9.17 drop unknown types (iOS `EventLog.fromBand`:
`guard let k = e.kind else { return nil }`, checked on ios-app-ui, ios-app-herday, ios-app-report): nothing breaks, but the family
sees types 17-21 only once the app decodes them. Payload x = bytes 11-18: [11-12] i16 f20 x100 (INT16_MIN = unknown),
[13-14] i16 reference f20 x100, [15-16] u16 extra, [17-18] 0.

| type | name | arg | x | when |
|---|---|---|---|---|
| 14 | POWER_OFF | 1 wearer (double press + confirm), 2 USB | 0 | before System OFF |
| 15 | BATT_CRITICAL | - | - | reserved for 0.9.18 |
| 16 | HAPTIC_LOST | HG_HP_* pattern id | 0 | the motor could not play it (re-init failed); the screen flashed instead |
| 17 | LD_REMIND | 1 water, 2 cooler place | f20; [15] 0 first / 1 the 10-min repeat | a reminder is shown |
| 18 | LD_DONE | step | f20 at the press; [15-16] minutes since the reminder | she pressed "done": the 20-min check starts |
| 19 | LD_WORKED | 1 water, 2 cooler place, 3 after an escalation | f20, reference | the forecast stopped rising (+0.05 C at most in 20 min) |
| 20 | LD_ESCALATED | 1 Danger line, 2 still heating after cooling down | f20, reference | family alert |
| 21 | LD_NOTE | 1 water did not help, 2 no response to a reminder, 3 responsive (escalation) | f20, reference; [15-16] step | quiet family note |

Button (owner decision Nov 19 17:29): press < 1.2 s; hold 3 s = HELP (a second 3-s hold cancels, locked for the first 10 s);
double press (2nd press within 700 ms of the 1st release) = «Απενεργοποίηση;», one press confirms (not a press starting < 700 ms
after the prompt), 5 s without input closes it, refused during HELP, any alert / reminder / CHECK / nudge / family message, and
for 10 min after a HELP; 1.2-3.0 s = nothing. The band shows only Her Day timing advice (N1 with a plan outing, N7, N8) and the
body-based alerts: N2 / N4 / N5 / N6 and the frozen bedtime tip are no longer shown (owner decision Nov 19 18:04).

## 6. Greek strings needing Foivos's OK
All strings in sections 2, 3, 4, 5 (quoted «…»), and the Her Day strings of HERDAY_SPEC.md 5 as built: «Αύριο: {place} πριν τις HH:MM»,
«Αύριο: {place} μετά τις HH:MM», «Αύριο: καύσωνας, μέρα N», «Σήμερα: {place} πριν/μετά τις HH:MM», «Έξω κάνει ζέστη. Πάρτε νερό.»;
place words αγορά, εκκλησία, βόλτα, φαρμακείο, καφενείο, γιατρό, έξοδο (place 0 home and 7 other both read «έξοδο»). 0.9.9: the all-clear «Πάλι όλα καλά».

## 7. Out of scope tonight
Internet relay, accounts, BLE security changes (b7-ble-sec), any engine/threshold change.
