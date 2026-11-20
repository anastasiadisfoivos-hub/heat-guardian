HEAT GUARDIAN: SIMULATION MONITOR (SIM-STAGE)
=============================================

What it is: one page for the WAICY film. You click "Simulate heat episode"; the page sends `replay` to the REAL
band; the band's own firmware runs the simulated 74-year-old woman (Virtual Elders pid 90862, firmware 0.9.17-demo-b7g) through its real engine, and
the page draws what the band reports: her core temperature, the band's estimate and 20-min forecast, the band's
gauge colour, and the action ladder step by step. The page never makes up a value: it only draws what the band
sent, and it only smooths the line between two minutes the band already reported.


ON THE MAC (Chrome)
-------------------
1. Bluetooth on (menu bar). The band needs no pairing: its characteristics are open.
2. Open Terminal, go to this folder and start a small local web server (Chrome only allows Bluetooth and USB
   pages on https or on localhost):

       cd /path/to/sim_stage        (the folder with index.html)
       python3 -m http.server 8765

3. In Chrome open:   http://localhost:8765
4. Click "Connect band" and pick "HeatGuardian" in Chrome's list. The status bar (bottom left) shows a green
   square: "Band connected (Bluetooth)". If the band goes out of reach the square blinks amber and the page reconnects
   by itself.
5. Optional: tick "She doesn't respond" (sends `replay noresp`: nobody presses, the real ladder
   takes its no-response path: reminder, repeat, family alert). Leave it off for `replay`: then YOU press the band's button when the band
   asks, on camera.
6. Pick the speed (seconds per simulated minute; 2 = 110 simulated minutes in 3 min 40 s).
7. Click "Simulate heat episode". "Stop" sends `replay stop` (the band goes back to live).
   Full screen: View > Enter Full Screen (or Cmd+Ctrl+F).

The iPhone app can stay connected (the band takes 2 Bluetooth links; firmware 0.9.17-demo-b7n sends the text
lines to every connected link and asks for a fast link while the replay runs). Needs the band on b7n: older
firmware refuses `replay noresp` and the page says so.

What the page reads over Bluetooth (b7n, one line per simulated minute, the events right after it):
  #R k=29 t=13:29 c=37.42 f=37.70 sc=37.75 st=DRINK lv=1 ld=remind rm=water ga=yellow dot=4 fam=0 nr=0 b=0
  #E k=29 fam=0 ev=WARN_SHOWN.1,LD_REMIND.1
c = the band's estimate, f = its 20-min forecast, sc = the simulated true core. The left pane shows these lines
as they arrive. On a slow link the band skips some #R lines (never the #E lines); the chart then draws a
straight line between the minutes it did get.

[DEMO-PICK, b7t] The person is a SHOWCASE pick: Virtual Elder pid 90862 was chosen (from 611 fresh draws, 344 scored) because
the band's estimate follows her true core closely (this run: 0.06 C off on average). The grey line under the two
accuracy lines gives the population number for honesty: across 100 other simulated elders the model never trained on,
0.23 C (estimate) and 0.29 C (20-min prediction) off on average (wt_b15/model/runs/b2b_v5aug/eval_v5.json, v5_AR;
model/REPORT_B2b.md). b7t timings: water 13:25, (press 13:31) still heating + go cool 13:51, again 14:01, (press 14:10)
Bravo 14:30, all clear 14:46; noresp: water 13:25, again 13:35, family alerted 13:45 (90 s at 2 s/min), all clear 14:46
(no go-cool step in noresp: the band never shows COOL for her).

EVIDENCE corner (bottom right): live link + seconds since the band's last message (real link only; "Preview - not
connected" in preview), the firmware string the band reports (Device Information / STAT), the firmware commit and the
frozen model hash baked in by tools/build.py (the commit is shown only when the band's string equals the build's), the
Virtual Elder pid from `#R start el=`, the wall clock, and a QR + URL of the source repo when REPO_URL in tools/build.py
is set (empty = hidden; the shots 1-8 were made with a dummy URL: HG_REPO_URL=https://github.com/example/heat-guardian).

How close the band is (right, two plain lines): computed only from the lines above. "Estimate ... off on
average" = mean of |c - sc| over the minutes received; "20-minute prediction ... off on average" = mean of
|f printed 20 simulated minutes earlier - sc now| (from 13:20 on). A dash = not enough data yet.

USB instead of Bluetooth: click "USB instead", pick the cu.usbmodem port. With USB the page gets the full
per-minute line (her simulated true core + the band's estimate + the forecast every minute), so the chart is
equivalent on USB (the long `# DEMO` lines). ONLY ONE PROGRAM CAN HOLD THE USB PORT: quit band_cmd / screen / the Arduino serial monitor
in the terminal first, or Chrome cannot open it (and vice versa). Bluetooth has no such conflict: the terminal
can keep the USB port while the page uses Bluetooth.

Rehearsal without the band: "Preview without band" plays the recorded Bluetooth output of the same replay
(made by the host build of the b7n firmware, see below), with the band's timing. The tick box picks the
recording where she presses (13:31 and 14:10) or the one where nobody presses. An orange "PREVIEW" tag shows in
the top bar while previewing; crop it or use the live band for the final take.
Jump to a moment (for inserts):  http://localhost:8765/?preview=1&seek=53          (53 = minute 13:53)
                                 http://localhost:8765/?preview=1&seek=45&noresp=1 (13:45: family alerted)


FILES
-----
index.html                   the page (self-contained: CSS, JS, parser and both Bluetooth recordings inline; system fonts)
transcript_ble_press.txt     recorded Bluetooth output (b7n), `replay 2`, she presses after 13:31 and after 14:10
transcript_ble_noresp.txt    recorded Bluetooth output (b7n), `replay noresp 2`, nobody presses
transcript_press.txt         the same two runs as the USB `# DEMO` stream (fallback; used by the tests)
transcript_noresp.txt
shots/                       screenshots at 1920x1080
tools/core.js                the parser + state + accuracy (inlined into index.html by tools/build.py)
tools/index.template.html    the page source; `python3 tools/build.py` rebuilds index.html
tools/sim_emit.c             the host program that made the transcripts: the band's replay code (hg_fw_demo.c, hg_fw.c,
                             the frozen guardian, alert layer, planner, ladder, gauge of 09-guardian-0.9.17-demo-b7n,
                             commit 8947e2c) printing the band's own line formats (demoStart / demoLine / evLog)
tools/test_parser.js         `node tools/test_parser.js`: the page's parser over all four transcripts + a thinned link
tools/shots.py               the Playwright screenshots

Rebuild the transcripts (from the firmware repo at 8947e2c):
  cd fw/09_guardian && gcc -std=c99 -O2 -I. <sim_stage>/tools/sim_emit.c hg_fw_demo.c hg_fw.c hg_fw_eco.c \
     hg_fw_alert.c hg_fw_ladder.c hg_fw_ui.c fz_*.c -lm -o /tmp/sim_emit
  /tmp/sim_emit 2 "31,70" ble 0 > transcript_ble_press.txt ;  /tmp/sim_emit 2 "" ble 1 > transcript_ble_noresp.txt
  /tmp/sim_emit 2 "31,70" usb 0 > transcript_press.txt     ;  /tmp/sim_emit 2 "" usb 1 > transcript_noresp.txt
(USB EVT lines carry unix=1795000000 + replay seconds: on the band they carry its real clock. Nothing reads them.
 The recording assumes a fast link, so it has every #R line.)


TOMORROW (button "Tomorrow" in the top bar)
-------------------------------------------
[RELEASE-G] Three steps on top: 1 the band collected her measurements (7 SIMULATED days of wear for pid 90862, Virtual
Elders simulator), 2 the Body Twin learned her body (the real twin/hg_twin.py, minute by minute, nightly update 03:30;
tools/make_twin_week.py -> twin_week.json, inlined by build.py, and tomorrow_engine/twin_learned_pid90862.json),
3 tomorrow's real weather -> her day. Learned: resting HR 70 -> 60.8 bpm in 7 nights (the twin's definition = 10th
percentile of her still sleeping HR + 5; the same on the simulator's TRUE HR = 62.4 bpm; her drawn awake seated rest is
67.5 bpm, a different quantity); temperature offset stays 0.0 (no thermometer reading in the week); the night wrist
baseline was not learned (every night the air was >= 28 C). Step 3 says so in orange while tomorrow_plan.json was made
with another twin: the plan in this folder is still the pid 90416 plan (its Open-Meteo cache was gone, no fetch here);
./make_tomorrow.command on the Mac remakes it with twin_learned_pid90862.json (the default now).
The plan: Virtual Elder pid 90862 + her learned twin run through TOMORROW'S REAL weather forecast for a hot city
(default Alice Springs, Australia), by the Tomorrow Engine (B4, physics unchanged). The page reads
./tomorrow_plan.json; without it, it says to run make_tomorrow.command. SIMULATION, not a medical prediction.
Weather data by Open-Meteo.com.

Make or refresh the plan on the Mac (Terminal, in this folder; first run installs numpy/pandas/jsonschema
into ~/.hgtomorrow, about a minute; needs python3 3.9+, the macOS one is fine):

       ./make_tomorrow.command
       ./make_tomorrow.command --city durban          (also asuncion, brisbane, perth, adelaide, cordoba)
       ./make_tomorrow.command --lat -25.26 --lon -57.58 --name "Asuncion" --country Paraguay

It ends with one line: "OK  tomorrow_plan.json written: ...". Reload the page and click Tomorrow.
Direct link: http://localhost:8765/?view=tomorrow

What is on the panel (all from the plan): the city, the date, Open-Meteo's forecast high; risky hours = the
engine's AVOID hours (shaded); best time to go out = the engine's first run of safe hours; outside = the
forecast's hourly temperature; her body temperature at home = the engine's core_indoor (highest minute of each
hour, drawn mid-hour); the first three Greek lines the band would show (engine strings) with English under them.

Choices made by tomorrow_engine/run_city.py (a thin wrapper; it changes no physics):
  home class C (top floor / under the roof): closest of the engine's four classes to a single-storey house
  under a sun-heated roof; no air conditioning (the engine has none); a fan (her drawn profile has one);
  urban heat offset 0/0 (the forecast grid cell is the town itself, as the engine does for central Athens);
  forecast asked in the city's local time (timezone=auto) instead of Europe/Athens;
  if api.open-meteo.com answers 429, the same forecast from previous-runs-api.open-meteo.com.
Known limits: the indoor model and the heat-day threshold (Baccini 2008) were set for Athens homes and people;
the indoor model starts settled 2 days before (no carried-over state the first time), which under-warms slow
homes (B, D) in a building heat wave; dry desert air is made even drier indoors (engine's AH ratio), which
understates strain.

Files: make_tomorrow.command, tomorrow_engine/ (tomorrow/ = the engine package without tests or cache;
velders/ = the body model it prefers; twin_learned_pid90862.json = the default (her profile + the learned twin;
sweat capacity 0.44 = engine default, not learnable on the band); twin_pid90862.json / twin_pid90416.json = drawn
profiles (--pid 90416 for the old person); run_city.py; requirements.txt), tomorrow_plan.json (the last plan made).
