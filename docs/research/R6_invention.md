# R6 — Invention: Talzin methods on the wrist

*R6 invention agent, 12 Nov 2026. Everything measured here is **SIMULATION, DEV ONLY** (Virtual Elders v4, `minutes_dev_v4.parquet`; known too tolerant at humid rest, bed rest and HR), except section 6, which is **REAL young adults, DEV** (HTT). No `*sealed*` file was opened. The frozen build (`hg2-freeze-3`) was used read-only through its host binaries. Scripts and raw outputs: `research/r6/`.*

## 0. Verdict

Three things were asked for. One works, one works as a trade-off, one fails.

| Weak spot | What was invented | DEV result | Decision |
|---|---|---|---|
| 1. Family tier misses older bodies whose heart does not race | **Marble Danger**: Danger by *mass and wind*, not by a line. A slow level, a heat "mass" that piles up, the "wind" of ongoing movement, and a discount on sudden jumps. 5 numbers of state, armed only in heat. | Heat-wave core-38.5 events caught: **49/63 = 78 %** at **5.4–5.9 false alarms per wearer-month**, the same with raw and with HR-scaled heart rate. Frozen rule: 29/63 = 46 % at 14.2 (raw), 20/63 = 32 % at 7.6 (HR-scaled). Low-κ third (the hearts that do not race): frozen 5/37 raw and 2/37 HR-scaled; Marble 22/37 in both. On the 75 persons the network never saw: Marble 8/20 and 7/20, frozen 7/20 and 2/20. | **Adopt for the SEALED-SIM-3 exam**, replacing the M13 persistence rule. |
| 2. DRINK nags 3.7–4.0 times a day | **Exception DRINK**: compare her forecast to her own normal *for this much movement* (learned on ordinary-room days only), and stay quiet for 2 h after a nudge unless strain keeps climbing. | 4.0 → **3.0 episodes/day**, 119 → **78 min/day**, heat-wave sensitivity 93 → **89 %** (raw). HR-scaled: 3.0 → 2.0, 100 → 66 min, 90 → 87 %. | **Adopt for the exam**, with the caveat that it sits on the budget line. |
| 3. Nothing learns the per-person error (κ, mesor, axial drop) | **Personal heat-response fingerprint** from natural experiments (the leading candidate). | **Fails.** Her cardiac gain κ is recovered with correlation 0.05–0.24 by the fingerprint, 0.45–0.59 by the best simple estimator, and only 0.60–0.68 even when the true core temperature is handed to it. Her-units exceptions alone are far worse than the existing network. | **Not adopted.** Run in shadow mode on the wear test. Reasons in section 4. |

The one-sentence finding: **the family tier was weak because it judged a noisy number against a line minute by minute, not because the band lacked personal knowledge.** Momentum was the key, as in Talzin.

## 1. Talzin methods carried over

Sources: the Talzin rules in `BRIEF.md`, and Foivos's own notes on the engine. A search of past conversations returned no Talzin design chats, so nothing here comes from a transcript.

| Talzin idea | What it became on the wrist | Outcome |
|---|---|---|
| A marble has position, speed, direction, mass | The strain marble: position = slow level `E60`, mass = accumulated excess `D`, wind = movement still pushing it | Adopted (Marble Danger) |
| Momentum is the key | Slow averages and a leaky integral instead of the instantaneous forecast | Largest single gain measured |
| "Right after a sudden change a marble is less likely to change again on its own" | (a) A sudden jump of the forecast above its own slow average is *discounted* (the data chose a negative weight, same sign in every fold). (b) After a DRINK nudge, 2 h of quiet unless strain keeps rising | Adopted (both) |
| Exceptions are the signal (drift-only: what departs from its own normal motion) | DRINK fires on departure from *her usual rise for this much movement*; tested also as Danger evidence | Adopted for DRINK; rejected for Danger |
| "Calm brain": learn normal only from calm data | Her usual chore response is learned only in rooms below 30 °C | Adopted (+3 to +4 points of sensitivity at the same nagging) |
| Mass = how many sources agree | A count of agreeing paths (network, HR-only model, environment) | Tested, adds nothing measurable; mass is realised as accumulated dose instead |
| Links with event-dependent speed, shocks rippling | Her HR-per-°C link (κ) and recovery time constant | Tested, not recoverable from the wrist |
| Two calibrated tiers, sealed exams, every failure has a why | Operating point fixed by a false-alarm budget before scoring; SEALED-SIM-3 plan in section 8; every failed idea below has its diagnosed cause | Followed |

## 2. What the data said before anything was invented

Sample: 110 DEV persons = all 43 with a core-38.5 event (155 events) plus 67 calibration persons the network was not trained on. Because event persons are over-represented, false-alarm rates here are pessimistic for the whole population.

- **The dangerous events in this simulator are exertional.** 143 of 155 happen during chores or walking (mean 1.7 met, heart rate +49 bpm above rest). Only 12 happen at rest. The simulator is known to be too tolerant at humid rest, so the "resting heart that does not race" scenario is nearly absent from it. Nothing in this document proves anything about that scenario.
- **There is a long runway.** Core sits above 38.0 °C for a median of 129 minutes before it reaches 38.5 °C.
- **The event is a hairline.** Median peak is 38.57 °C and median duration 16 minutes. Between 36 % and 78 % of "false" Danger alarms happen when core is within 0.3 °C of the line. A "false" alarm at 38.4 °C is not an empty alarm, so section 5 reports both counts.
- **The network under-reads at the top.** At core ≥ 38.0 °C its error has a bias of −0.21 °C (raw) and −0.25 °C (HR-scaled), a between-person spread of 0.15 °C and a within-person spread of 0.18 °C.
- **The frozen Danger rule is dominated by trivial rules.** "Forecast ≥ 38.2 °C for 10 minutes" catches 70 % at 10.8 false alarms a month; the frozen rule catches 46 % at 14.2.
- **Perfect personal knowledge would help only a little.** Giving the forecast each person's true mean error (an oracle no band can have) moves the frontier from 40 % to 50 % at about 3 false alarms a month (HR-scaled; all events). The larger share of the problem is minute-to-minute noise.

Why the frozen rule misses, diagnosed: its evidence terms lean on heart rate (the v1.2 logit and the 38.5 logit), and it needs COOL to have been on for 20 minutes. Events whose COOL lead is under 20 minutes are caught 0–31 % of the time. With HR scaled down, COOL comes later and the evidence terms fall silent.

## 3. Idea A — Marble Danger (recommended)

### 3.1 Algorithm

Inputs each minute, all already on the band: `f20` = the forecast the tiers already use (network forecast with the frozen out-of-distribution guard), `a_std` = one-minute wrist movement, `thermal_ok`, `worn`.

State (5 floats, plus two one-byte counters):

- `E10 ← E10 + (f20 − E10)/10`, `E60 ← E60 + (f20 − E60)/60` (fast and slow level)
- `A30 ← A30 + (a − A30)/30`, `A120 ← A120 + (a − A120)/120`, with `a = min(a_std, 0.30 g)` (movement now against movement over the last two hours)
- `D ← D·(1 − 1/90) + max(0, f20 − 37.9)` (heat mass: how much excess has piled up, forgetting over about 90 minutes)

Score and rule:

- `s = w0 + wL·(E60 − 37.5) + wJ·(E10 − E60) + wB·A30 + wS·A120 + wD·D`
- **Armed** only while `thermal_ok` and there is heat context: the corrected room air was ≥ 28 °C at some minute of the last 60 (a one-byte "minutes since warm air" counter). Movement in a cool room can never fire it.
- **Marble Danger** = `s ≥ CUT` for 5 consecutive worn minutes. It then follows the existing path: «Είστε καλά;» first, family after 5 minutes without a press.
- Not worn or no forecast: feed `f20 = 36.9`, so the marble cools, and reset the run counter.

Provisional constants (fit on the 110 DEV persons, mean of raw and HR-scaled; to be refitted once on all 400 DEV persons before the freeze): `w0 = −2.43`, `wL = 3.43`, `wJ = −3.18`, `wB = 195.2`, `wS = −205.9`, `wD = 0.139`; `CUT` ≈ 4.5–4.7, set by the false-alarm budget (section 8). `wB` and `wS` nearly cancel, so the movement part is the wind: movement in the last half hour against the last two hours.

Where it sits: `Danger = v1.2 logistic OR behaviour path OR Marble`. The M13 persistence rule is removed. The v1.2 path stays because it is the only Danger evidence validated on real people.

### 3.2 Cost on the nRF52840

| Item | Cost |
|---|---|
| RAM | 5 floats + 2 bytes = 22 B |
| Flash | 7 constants + about 300 B of code |
| CPU per minute | 5 multiply-adds for the filters, 5 for the score; no `expf`, no ring buffer, no division at run time (reciprocals are constants) |
| Persistence | none (state rebuilds in two hours) |

### 3.3 Why it should work

- **Averaging beats the noise.** The within-person error of the forecast is 0.18 °C at the top, and the line is 38.5 °C against a median peak of 38.57 °C. A 60-minute average alone lifts the rule from 38 % to 59 % at ≤ 6 false alarms a month.
- **Heat mass is physiology.** Above the critical limit, older adults' core rises about 0.6–0.7 °C per hour for hours (Wolf 2023; Cottle 2022, R1 §3.2), and time to heat stroke is counted in hours of exposure (Kenney 2025). Danger is an accumulation, so an integrator is the right shape. Adding `D` lifts 60 % to 75 %.
- **Wind is heat production.** Core keeps rising while she keeps working in the heat; it falls when she stops. Movement is measured by the accelerometer, which does not depend on her heart. Wind alone has a minute AUC of 0.83 for "38.5 °C within 30 minutes".
- **It does not need a racing heart.** Measured: when every person's heart-rate rise is scaled down by 0.6–1.0, Marble catches the same 49 of 63, while the frozen rule falls from 29 to 20. In the low-κ third it catches 22 of 37 where the frozen rule catches 5 and 2. A plausible reason, not verified inside the network: in hot rooms the insulated wrist approaches a zero-heat-flux probe (R2 §1.1, §1.4), so the forecast can lean on temperature. This matters because Carrillo 2024 found heart rate and HRV discriminate a > 1 °C core rise in older adults with AUC ≤ 0.65 (R1 §2.3).
- **The negative jump weight** is Talzin's correction in numbers: a forecast that suddenly jumps above its own slow average usually falls back.

### 3.4 How it fails

- **It inherits the forecast.** If the network forecast is wrong on a real wrist, the marble is wrong. On heart-rate-only data it is off by design (`thermal_ok` is false).
- **Rest events.** 12 events at rest in DEV is too few to claim anything, and the simulator under-produces them. The PSU environmental-dose path and the behaviour path remain the defence at rest.
- **A very active wearer in a warm room.** The wind term rewards sustained movement and is not bounded. The heat-context gate stops it in cool rooms (without the gate, 5–7 of about 275 episodes happened below 28 °C), but a fit person walking for half an hour at 29 °C could fire it. The simulator has few such people. A conservative alternative was measured (wind clipped at 0.025 g, armed only while `E60 ≥ 37.8` and `D > 0`): 44/63 = 70 % at 5.0–5.2 false alarms a month and fewer empty alarms (1.8–2.0), but the low-κ third drops from 22/37 to 13–14/37. The forecast under-reads exactly those people, and the movement term is what recovers them. This is a choice for the manager; only one variant can go to the sealed exam.
- **Open loop.** In the simulator nobody reacts to COOL. In life, a wearer who sits down removes the wind and the marble cools, which is the intended behaviour, but it is untested.
- **Unseen persons.** See 5.3: sensitivity is lower on persons the network never saw.

## 4. Idea C — the personal heat-response fingerprint (leading candidate, fails)

### 4.1 What was built

Nightly, in the Body Twin slot, from daytime worn minutes with no alarm on (`research/r6/fingerprint.py`):

- Movement load `A` = 4-minute average of `a_std`; `amb = max(0, T_air − 22)`.
- Her heart line: `HR ≈ b0 + b1·A + b2·amb`. Her wrist line: `T1 ≈ c0 + c1·T_air + c2·A`.
- Exceptions: `rH = HR − line`, `rT = T1 − line`, each in her own units.
- Her gain: `G = Σ rH·rT / Σ rT²` on still minutes, the "bpm per °C of her own thermal departure".
- Coefficients carry over days with a 0.85 daily decay and shrink toward a population prior. State: two 3×3 sums and two 3-vectors, about 100 B. No `expf`.

### 4.2 Results

| Test | Result |
|---|---|
| κ recovered by the fingerprint after 3 / 5 / 7 / 9 days (truth = effective bpm per °C core) | correlation 0.05 / 0.08 / 0.07 / 0.13 (raw); 0.19 / 0.22 / 0.20 / 0.24 (HR-scaled); estimate 6 against a true 18 bpm/°C |
| κ by direct regression of resting HR on wrist T1, 7 days | correlation 0.45 (raw), 0.51 (HR-scaled); in rooms ≥ 30 °C: 0.45, 0.59; estimate 7.7 against 17.8 |
| κ by regression on the **true** core temperature (upper bound, impossible on a band) | correlation 0.60 (raw), 0.68 (HR-scaled) |
| Minute AUC for "38.5 °C within 30 min": frozen forecast | 0.95 |
| Same, her wrist exception `rT` / her heart exception `rH` / both must agree | 0.80 / 0.63 / 0.68 |
| Same, forecast minus her own calm baseline | 0.90 (worse than the absolute forecast) |
| Danger from her-units signals only, ≤ 6 false alarms a month | heat-wave events caught 38–41 % (Marble: 78 %) |
| Her-units signals added to Marble Danger, ≤ 6 a month | raw 78 → 76 % (no gain); HR-scaled 78 → 87 % (better). Not robust. |
| "Recovery failure" (resting HR above her own line after activity) | minute AUC 0.65 |

### 4.3 Why it fails

1. **Ordinary days do not excite the system.** At rest on a normal day her core barely leaves its daily rhythm, so even the true core temperature identifies κ only to a correlation of 0.6–0.7 in a week. Natural experiments are too small for this parameter.
2. **At ordinary room temperatures the wrist reports skin blood flow, not core.** The axial drop along the arm swings about 1 °C with vasomotor state (R2 §1.4), several times the core change. So "bpm per °C wrist" is attenuated by 2–3× and noisy.
3. **Heart rate during events is mostly movement.** The metabolic term is about 40 bpm at 2 met; the heat term is 10–20. Wrist movement is a coarse proxy for metabolic rate, so the heat residual is buried.
4. **The event is absolute, her units are relative.** 38.5 °C is a fixed line. A signal relative to her own baseline loses her mesor and cannot recover it without a reference reading.
5. A trap found on the way: learning "her normal" only from alarm-free minutes selects on the outcome. It did not explain the failure here, but any future fingerprint must learn from all minutes below COOL.

### 4.4 What is kept

- The fingerprint runs **in shadow mode** on the wear test (logged, never used for an alarm). Real wrists may behave better or worse than the simulator's axial-drop model, and only real data can say.
- A hypothesis worth a real-data test (R5's datasets, if any contain chores and heat for the same person): her heart-rate gain to chores predicts her heart-rate gain to heat ("chronotropic index"). In the simulator her chore gain correlates 0.47–0.55 with her true heat gain, as well as the wrist estimate does, but that link comes from how the simulated population was drawn, so the simulator cannot answer it.

## 5. Experiments on Marble Danger (SIMULATION, DEV, 2-fold cross-validation by person)

Scoring as in `eval_sim_m7.py`: an event is caught if Danger shows in [t − 45, t + 10] minutes. Episodes are onsets after 30 quiet minutes. **Strict** false alarm: core never reaches 38.5 °C within [onset − 10, onset + 60]. **Empty** false alarm: core never reaches 38.2 °C in that window. Rates are per wearer-month over all days. Operating point: the cut with the best heat-wave sensitivity whose cross-validated strict false-alarm rate is ≤ 6 a month. Intervals are person-bootstrap 95 %.

Choices made on DEV, so that nobody has to guess how much was tried: the time constants (10 / 60 / 30 / 120 / 90 min), the 37.9 °C knee and the 5-minute persistence were set once and never swept; nine feature sets were compared (5.1); three arming variants were compared (none, heat context, the conservative one of 3.4); the cut is chosen by the false-alarm budget inside cross-validation.

### 5.1 Which ingredients matter (raw HR, ≤ 6 strict false alarms a month)

| Score built from | Heat-wave events caught |
|---|---|
| Instant forecast only | 38 % |
| Slow level `E60` only | 59 % |
| Level + jump + dose, no movement | 62 % |
| Level + jump + movement, no dose | 60 % |
| **Level + jump + movement + dose (the 5 Marble states, before the heat-context gate)** | **75 %** |
| Seven-feature version with ring buffers | 81 % |
| + HR-only path and environment ("how many sources agree") | 79 % |

### 5.2 The recommended build against the frozen build

| Rule (DEV, 110 persons, 63 heat-wave events, 155 events in all) | Heat-wave events caught | All events | Median lead | Strict false alarms / wearer-month | Empty false alarms / month |
|---|---|---|---|---|---|
| Frozen freeze-3 Danger, raw HR | 29/63 = 46 % [30–65] | 46 % | 17 min | 14.2 [10.2–17.8] | 9.1 |
| Frozen without the M13 persistence rule, raw HR | 13/63 = 21 % | 21 % | 14 min | 7.9 | 5.5 |
| **Marble Danger alone, raw HR** | **49/63 = 78 % [60–95]** | 63 % | 21.5 min | **5.9 [4.5–7.4]** | 3.2 |
| **New Danger tier = v1.2 OR behaviour OR Marble, raw HR** | **51/63 = 81 % [63–98]** | 69 % | 21 min | 12.6 [9.5–15.9] | 8.1 |
| Frozen freeze-3 Danger, HR-scaled | 20/63 = 32 % [13–55] | 34 % | 19 min | 7.6 [4.8–10.6] | 4.7 |
| Frozen without the M13 persistence rule, HR-scaled | 5/63 = 8 % | 8 % | 10 min | 3.8 | 3.0 |
| **Marble Danger alone, HR-scaled** | **49/63 = 78 % [65–92]** | 64 % | 19 min | **5.4 [4.0–7.0]** | 2.7 |
| **New Danger tier, HR-scaled** | **50/63 = 79 % [68–94]** | 65 % | 19.5 min | 8.6 [6.0–11.2] | 5.2 |

The median wearer has 3 strict Marble false alarms a month (one in the ten simulated days); the frozen rule's are concentrated in fewer wearers (median 1.5 raw, 0 HR-scaled). At other budgets Marble alone catches 57–59 % at ≤ 3 a month and 89–92 % at ≤ 10 a month.

The v1.2 path that must stay (it is the real-data path) brings most of the remaining false alarms: 7.9 a month with raw HR, for 2 extra heat-wave events.

Reading: Marble alone, at well under half the frozen rule's false alarms with raw HR, catches 49 heat-wave events where the frozen rule catches 29; with HR-scaled heart rate, 49 against 20. Its sensitivity does not move when the simulator's heart-rate bias is removed. The frozen rule's does.

### 5.3 Subgroups

Marble Danger alone at the same operating point, against the frozen tier, all 155 events.

| Group | Persons / events | Marble, raw | Frozen, raw | Marble, HR-scaled | Frozen, HR-scaled |
|---|---|---|---|---|---|
| Low κ (heart rises least per °C) | 37 / 37 | 59 % at 4.5/mo | 14 % at 11.0/mo | 59 % at 3.8/mo | 5 % at 4.9/mo |
| Mid κ | 36 / 66 | 71 % at 7.1 | 64 % at 11.7 | 71 % at 7.0 | 48 % at 7.9 |
| High κ | 37 / 52 | 56 % at 6.2 | 46 % at 19.8 | 58 % at 5.5 | 35 % at 10.0 |
| Beta-blocker | 30 / 81 | 62 % at 6.3 | 52 % at 26.8 | 64 % at 6.2 | 43 % at 14.3 |
| No beta-blocker | 80 / 74 | 65 % at 5.8 | 39 % at 9.4 | 64 % at 5.1 | 23 % at 5.1 |
| Events during chores or walking | 143 events | 64 % | 46 % | 64 % | 34 % |
| Events at rest | 12 events | 50 % | 42 % | 67 % | 25 % |
| Ordinary-summer days | 69 events | 54 % | 45 % | 54 % | 38 % |
| Day before the heat wave | 11 events | 36 % | 45 % | 36 % | 36 % |
| Persons the network trained on | 35 / 135 | 67 % at 7.6 | 47 % at 23.4 | 68 % at 7.4 | 37 % at 14.1 |
| **Calibration persons (network never saw them)** | **75 / 20** | **40 % at 5.1** | 35 % at 9.9 | **35 % at 4.5** | 10 % at 4.5 |

The warning in this table: **on the 75 calibration persons the network never trained on there are only 20 events, and Marble catches 8 and 7 of them** (the frozen rule 7 and 2, at about twice the false alarms with raw HR). Most DEV events belong to persons the network trained on, so the 78 % headline is optimistic. SEALED-SIM-3 persons are all unseen; the sealed result should be expected between the calibration row and the headline. Events on the day before a heat wave are not improved (4 of 11).

## 6. Does "mass, not line" survive on real data? (REAL young adults, HTT dev, heart rate only)

HTT has no skin, air or movement channels, so only a marble-lite on the v1.2 heart-rate forecast can be tested (`E60`, `E10 − E60`, `D`, optionally a smoothed v1.2 logit), 2-fold by subject, 104 sessions, 33 events at 38.5 °C.

| Rule | Caught at the frozen tier's false-alarm rate (0.096/h) | Median lead | Caught at ≤ 0.05/h |
|---|---|---|---|
| Frozen Danger tier | 24/33 = 72.7 % | 9 min | not sweepable |
| v1.2 logit alone, smoothed | 23/33 = 69.7 % | 8 min | 42.4 % |
| Marble-lite | 24/33 = 72.7 % | 19.5 min | 45.5 % |
| Marble-lite + smoothed logit | 25/33 = 75.8 % | 19 min | 57.6 % |

Honest reading: on real data the idea is **not worse, warns about 10 minutes earlier, and holds up better at a strict budget**. With 33 events none of these differences is significant. It is DEV, young adults, chamber walking.

## 7. Idea B — Exception DRINK (recommended, on the line)

### 7.1 Algorithm

Unchanged: the v1.2 ceiling path, the environment path, COOL and DANGER. Changed: the personal-relative path and when a new episode may start.

- `W30` = sum of `min(a_std, 0.30)` over the last 30 minutes (a 30-byte ring and a running sum).
- Nightly: her usual rise per unit of movement, `c = Σ W30·(f20 − calm) / Σ W30²`, over daytime worn minutes below COOL **in rooms under 30 °C**, daily decay 0.85, clipped to [0, 0.6].
- Exception line: DRINK when `f20 − calm − c·W30 ≥ 0.24 °C` (was `f20 − calm ≥ 0.30 °C`).
- Settled rule: after a DRINK episode ends, a new one may not start for 120 minutes unless `f20` is at least 0.15 °C above its value at the last nudge.
- Cost: 30-byte ring, 6 floats, 2 of them saved with the Twin. No `expf`.

### 7.2 Results (SIMULATION, DEV, 110 persons, ordinary-summer days for nagging, 578 heat-wave core-38.0 events for sensitivity)

A Python emulation of the frozen DRINK tier agrees with the frozen binary on 99 % of minutes.

| Design | Episodes/day (median person) | Minutes/day | Heat-wave sensitivity (display) | Informed |
|---|---|---|---|---|
| Frozen binary, raw HR | 4.0 | 119 | 93 % | 95 % |
| Exception only (Δ 0.30) | 3.4 | 85 | 92 % | 93 % |
| Settled only | 3.3 | 103 | 91 % | 94 % |
| **Exception + settled (Δ 0.24)**, raw HR | **3.0** | **78** | **89 %** | **93 %** |
| Momentum gate (forecast not falling) | 4.0 | 123 | 95 % | 97 % |
| Frozen binary, HR-scaled | 3.0 | 100 | 90 % | 93 % |
| **Exception + settled (Δ 0.24)**, HR-scaled | **2.0** | **66** | **87 %** | **92 %** |

- The budget (≤ 3 a day, ≤ 90 minutes, sensitivity ≥ 85 %) is met in both heart-rate variants, at exactly 3.0 a day with raw HR. The mean wearer is still above it (3.8 a day, 140 minutes).
- Six parameter settings were looked at on DEV to draw this curve, so the chosen one is tuned on DEV. Only the sealed set can confirm it.
- Why the nagging was there: the frozen line compares a chore-time forecast with a *resting* baseline, so every chore crosses +0.30 °C. That is expected motion, not an exception.
- Failure modes: a wearer whose chores are always in a hot room never teaches the band her ordinary response (the slope stays near the prior of 0); the settled rule can hide a second, separate rise smaller than 0.15 °C.

## 8. Pre-registered test plan

### 8.1 On SIM-DEV v4 (all 400 DEV persons) — the gate to freeze

Fixed now and not to be swept: time constants 10 / 60 / 30 / 120 / 90 minutes; knee 37.9 °C; movement clip 0.30 g; heat-context gate 28 °C within 60 minutes; 5-minute persistence; armed after the first 24 h of wear (as evaluated here); scoring windows as in section 5. DRINK: Δ 0.24 °C, 30-minute movement window, calm-only learning below 30 °C, 120-minute settle, 0.15 °C override.

Fitted once: the five Marble weights, by logistic regression on DEV with raw and HR-scaled copies pooled; the cut = best heat-wave sensitivity with 2-fold cross-validated strict false alarms ≤ 6.0 per wearer-month.

| # | Acceptance on DEV (cross-validated by person) | Number |
|---|---|---|
| A1 | Marble alone, heat-wave core-38.5 events caught, raw and HR-scaled | ≥ 60 % each |
| A2 | Difference between raw and HR-scaled | ≤ 10 points |
| A3 | Marble alone, strict / empty false alarms per wearer-month | ≤ 6.0 / ≤ 3.5 |
| A4 | Low-κ third, all events | ≥ 45 % in both variants |
| A5 | Full new Danger tier (v1.2 OR behaviour OR Marble), heat-wave events, with strict false alarms ≤ 13 a month raw and ≤ 9 HR-scaled | ≥ freeze-3 + 20 points on the same persons |
| A6 | C equals Python, 0 mismatching minutes; property test: Marble can add a Danger, never remove an alarm | pass |
| A7 | HTT dev replay: Marble fires 0 times (no thermal data); Danger false alarms/h unchanged | ≤ 0.10/h |
| A8 | DRINK: ordinary-day median episodes / minutes; heat-wave sensitivity raw / HR-scaled | ≤ 3.0 / ≤ 90; ≥ 85 % / ≥ 82 % |

If A1–A5 fail, Marble is not frozen and the reason is written down. No retuning of the fixed items.

### 8.2 On SEALED-SIM-3 (ids 600–699, one run, after `hg2-freeze-4`)

| # | Sealed criterion | Pass | Reference (sealed set 2) |
|---|---|---|---|
| S1 | Family tier, heat-wave core-38.5 events, **HR-scaled** | ≥ 50 % | 4/18 = 22 % |
| S2 | Same, raw HR | ≥ 61 % | 11/18 = 61 % |
| S3 | Raw minus HR-scaled | ≤ 15 points | 39 points |
| S4 | False Danger episodes per wearer-month, mean, raw / HR-scaled | ≤ 15 / ≤ 10 | about 15 / 5.8 |
| S5 | DRINK on ordinary days, median wearer | ≤ 3.0 a day and ≤ 90 min | 3.65 a day, 143 min |
| S6 | "Drink water" heat-wave sensitivity, raw / HR-scaled | ≥ 85 % / ≥ 82 % | 93 % / 90 % |

Our own expectation, written before the exam: S1 and S3 are likely to pass; S2 is uncertain, because on DEV persons the network never saw Marble caught only 8 of 20 events. A fail on S2 with a pass on S1 would mean "robust to the heart-rate bias, but no better with raw HR", and would be reported that way.

Reported alongside, pass or fail: Wilson intervals (about 18 events gives ± 20 points), empty false alarms, events at rest listed one by one, the low-κ third, lead time, and each missed event with its diagnosed cause.

### 8.3 On the wear test (real, n = 1)

- Marble and Exception DRINK replayed on the recordings: episodes per day on ordinary days. Any Marble Danger on a healthy young wearer in November is a false alarm and gets a why.
- One staged session for the known failure mode: a room warmed to 28 °C or more and 30 minutes of brisk chores. Marble should stay silent; if it fires, the conservative variant of 3.4 is the fallback and the result is reported.
- The fingerprint in shadow mode: are `b1` (HR per movement) and the wrist line stable from day to day on a real wrist?
- A closed-loop check that the simulator cannot give: after a staged warm chore, does sitting down make the marble cool within about 30 minutes?

## 9. What cannot be claimed

- Nothing here is evidence about a real person over 65.
- Marble Danger is validated only inside the simulator that trained the forecast it reads. The real-data check in section 6 is on a different, heart-rate-only variant.
- The simulator's dangerous events are almost all exertional. Marble's benefit for a resting older person in humid heat is untested.
- "The band learns her heat response" is **not supported**. The supported personal learning stays as in M10, plus one new item if the exam passes: her usual rise during chores.

## 10. Files

| File | What it is |
|---|---|
| `r6/build_cache.py`, `r6/common.py` | 110 DEV persons replayed through the frozen freeze-3 binary, raw and HR-scaled |
| `r6/fingerprint.py`, `r6/eval1.py`, `r6/eval1b.py` | Fingerprint and the κ-recovery tests (section 4) |
| `r6/rules.py`, `r6/feats.py`, `r6/eval2.py`, `r6/eval_single.py` | Scoring harness, causal features, ingredient tests |
| `r6/eval3.py`, `r6/eval3b.py`, `r6/eval_guard.py`, `r6/final_danger.py` | Marble Danger: ablation, guards, final evaluation (`R6_VARIANT=G3` = the recommended build, `G2` = the conservative alternative, default `G0` = no gate) |
| `r6/eval_drink.py`, `r6/eval_drink_sweep.py` | DRINK emulation and trade-off curve |
| `r6/eval_htt_marble.py` | Real-data check on HTT |
| `r6/out_*.json`, `r6/logs/` | Raw results and console output behind the numbers above |

One unexplained event, for the record: the first full cache build stopped on an assertion in a worker with no message; the identical rerun completed, and all 110 files were then checked (14,400 minutes each, emulated DRINK tier agreeing with the binary on 99 % of minutes). The cause was not diagnosed.

The 227 MB replay cache is not committed. Rebuild it with `python3 build_cache.py 110` then `python3 fingerprint.py`, run from `research/r6/` (about 5 minutes on 2 cores).
