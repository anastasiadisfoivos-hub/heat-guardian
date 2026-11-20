# Heat Guardian app — DESIGN.md (authoritative, Nov 16 2026)

Approved by Foivos in Figma: https://www.figma.com/design/PvSgiQ0sC6OeOLWU3n4lOo
(frames "Today — v2 minimal glass (EN)" and section "Today — state tones" are the reference;
v1 "Σήμερα — iPhone" is superseded). Where a skill or habit conflicts with this file, this file wins.

## 1. One app, two twin modes
First launch asks one question: «I wear the band» (Elder mode) / «I'm family» (Family mode).
Same codebase, same BLE layer, same design language; two personalities. Mode switch hidden in Settings.
- Family mode language: ENGLISH by default (Greek toggle kept via Strings.swift).
- Elder mode language: GREEK by default (English toggle).
- Demo reality: both phones on the stand next to the band; remote relay (internet) = roadmap, say so in
  Settings › About in one line.

## 2. Principles
1. Minimal: one message per screen; remove anything that isn't needed in the moment.
2. Fully native iOS 26 Liquid Glass: controls and cards float as glass over a living colour field.
   Use `.glassEffect(...)`, `GlassEffectContainer`, `.buttonStyle(.glass / .glassProminent)`, the system
   TabView (it becomes the floating glass tab bar automatically; use tab-bar minimize behaviour), SF Symbols
   with `.symbolEffect`, `.sensoryFeedback`, `.contentTransition(.numericText())`, Swift Charts.
   No custom fake-glass when a system API exists.
3. The background IS the status: a soft colour field that shifts with heat/danger level (section 4),
   animated smoothly (≥0.8 s ease) between states. Never a flat white page.
4. Typography: SF Pro (system). Large Title for the state word, generous whitespace, Dynamic Type everywhere,
   no text below 13 pt. Two weights in body (regular/semibold); state word bold.
5. Accessibility: VoiceOver labels on every control, contrast ≥ 4.5:1 on text over the colour field
   (darken text, never lighten), Reduce Motion → crossfade only, Reduce Transparency → solid surfaces.

## 3. Palette F "Santorini guard" (tokens)
brand/primary #003F88 · brand/health #13A89E · brand/soft #E3F1F8 · brand/warm #F9C74F ·
bg/page #F2F6FA · surface #FFFFFF · text/primary #0B1B2B · text/secondary #5B6B7B · hairline #DCE4EC ·
state/ok #13A89E · state/water #2F80ED · state/heat #F08A24 · state/danger #E5484D · state/offline #9AA5B1.
Spacing 4/8/12/16/24/32; radii: card 26, pill capsule, orb circle.
Put them in an asset catalog / Theme.swift with light + dark variants (dark: deepen the field, keep hue).

## 4. State tones (background colour field = two blurred blobs + vertical gradient, top → near-white)
| State (Tone) | top | mid | blob 1 | blob 2 | accent | title (EN / GR) |
|---|---|---|---|---|---|---|
| ok | #CCF0EB | #DBEBFA | #13A89E | #003F88 | #13A89E | All good / Όλα καλά |
| heat day (watch) | #FFF1DC | #FDF3E6 | #F9C74F | #F08A24 | #E07B12 | Hot day / Ζεστή μέρα |
| water (drink) | #FFE6CF | #FCEBDD | #F08A24 | #2F80ED | #2F80ED | Drink water / Ώρα για νερό |
| danger / check | #FFD9CC | #FBE1DA | #F0612A | #E5484D | #D9480F | Too hot / Πολλή ζέστη |
| help | #FFD1D3 | #FCDDDE | #E5484D | #B4232A | #C62828 | She needs help / Βοήθεια |
| offline | #E7EBEF | #EEF1F4 | #9AA5B1 | #C3CBD3 | #6B7785 | No connection / Χωρίς σύνδεση |
Blobs: ~420 pt and ~320 pt circles, blur ~120, opacity 0.45 / 0.35, top-left and top-right.
Danger/help: state word in the accent colour; help turns the "next" card solid accent with white text.

## 5. Family mode screens (4 system tabs: Today · Tomorrow · History · Settings; only the selected tab label shows)
TODAY (reference = Figma): glass pill top-left "● Maria" (live dot = connected), glass circle call button
top-right (tel: link to her number from Settings); centre: 132 pt glass orb with the state SF Symbol
(shield.checkmark / sun.max / drop / exclamationmark.triangle / antenna.radiowaves.left.and.right.slash),
state word (44 pt bold), one subtitle line (room temp + trend arrow · pulse, or the reason line),
prevention dots (5 dots, filled = done) + "prevention 3/5"; one glass "Next" card (icon, title, small
origin line, time); "TODAY" caption + 3–6 quiet log rows (icon, text, time; no boxes, no dividers);
"See all" → History. HELP state: "Next" card becomes solid red «Call her now» + «I'm coming» glass button.
TOMORROW: same colour field for tomorrow's worst state; title "Tomorrow" + one-line verdict
("Heat wave day 2 · safe out 06–10"); Swift Charts area/line of her indoor °C by hour with 28 °C and 30 °C
soft bands, safe hours as a teal band, planned nudges as small SF Symbol markers on the curve;
under the chart a short list of the planned nudges (time + text). "On her band ✓ 21:04" status line.
HISTORY: list of days, each a glass row: date, one-line summary «4/5 ✓ · 3 water · 0 warnings», state dot;
tap → that day's full log (same row style as Today).
SETTINGS: system Form with glass where natural: Family name (shown on her band), Her profile (age, sex,
BMI), Medicines (plain checkboxes), Routine (wake, bed, nap, 2 out windows, A/C), Home type
(floor + old/insulated → class A–D), Notifications (evening summary on), Connection, Diagnostics, Mode
switch, About (one honest line: alerts reach you when your phone is near her band; remote = roadmap).
ALERT (full screen, HELP/DANGER): help colour field, big orb with warning symbol, «Maria pressed HELP · 14:52»,
two big buttons: «Call her» (.glassProminent, tel:) and «I'm coming» (.glass), small «Seen» text button.
These send FAMILY_ACK/FAMILY_MSG exactly as the backend view-models do.

## 6. Elder mode screens (Greek; designed for 75+: huge, one thing, nothing to configure)
Single screen, no tab bar. Same colour field per state. Top: big clock (60 pt) + date.
Centre: orb + state word 40 pt + one Greek sentence of guidance («Πιείτε ένα ποτήρι νερό»).
If a nudge is open: one huge glass button «Έγινε ✓» (min 64 pt tall) → NUDGE_DONE via the same path the band
uses: CMD 0x1A ELDER_ACTION (action 2 + nudge id) — layout in /home/claude/wt_b12/fw/09_guardian/ECOSYSTEM_SPEC.md
once BAND-ECO writes it ([0]=0x1A, [1]=action 1 HELP / 2 NUDGE_DONE / 3 HELP_CANCEL / 4 IM_OK, [2]=nudge id, CRC-8 at [19]).
Bottom: one huge red capsule button «ΒΟΗΘΕΙΑ» (min 80 pt tall, long-press 1.5 s with a filling ring,
strong haptic) → CMD 0x1A action 1 (the band then raises HELP exactly like its own long press and emits the
EVENTS frame, so the family phone sees it). A second long-press while HELP is active asks «Ακύρωση;» → action 3.
An open «Είστε καλά;» CHECK shows a huge «Είμαι καλά» button → action 4.
Below it, small: «Η Μαρία σας καλεί» family messages appear as a large card when they arrive.
Settings reachable only via a hidden long-press on the clock (for the family to set up).

## 7. Motion
State change: background field crossfade 0.8–1.2 s; orb symbol `.contentTransition(.symbolEffect(.replace))`;
state word `.contentTransition(.opacity)`; danger/help orb `.symbolEffect(.pulse)` gentle; numbers
`.numericText()`. Haptics: success on «Έγινε ✓», warning on state worsening, error pattern on HELP.

## 8. Do not
No custom tab bar, no fake blur where `.glassEffect` exists, no third-party UI libs, no web skills,
no emoji in UI, no text over the colour field below 4.5:1, no Greek/English mixed on one screen.
