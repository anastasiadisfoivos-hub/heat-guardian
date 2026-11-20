# Heat Guardian wear test — protocol (Mon Nov 16 to Thu Nov 19 morning)

**Who:** Foivos (the author), school days. **Only Foivos wears the band** (see *Fair rules* below).
**What the band runs:** `08_logger` only. It records once a second. It gives **no alarms**. The alarms are replayed later on a computer by `tests/wear_exam.py`, which was written and frozen **before** the test.
**Why the labels matter:** every number of the exam is scored against your `mark` commands, button presses and diary. A missing label costs more than a missing hour of data.

> Στα ελληνικά: Το βραχιόλι μόνο καταγράφει. Ό,τι σημαδεύεις (mark, κουμπί, ημερολόγιο) είναι αυτό με το οποίο βαθμολογείται το τεστ.

**Fair rules (ISEF/EUCYS, research/R8):** this test is a student testing his own invention on himself only, with no health hazard and **no deliberate change to his body** (no heater on purpose, no extra exercise, no heat exposure). Under those conditions no ethics-board (IRB) approval is needed. Keep it that way: nobody else wears the band, and nothing is done to make him hotter. Before Mon 16: this protocol dated, a one-page risk assessment signed by a teacher and a parent, and the diary kept as a dated lab notebook.

Files in this folder: `PROTOCOL.md` (this), `CHECKLIST.md` (print it, 1 page), `diary_template.csv` (copy to `diary.csv`), `DEV_VS_EXAM.md` (what day 1 sets and days 2–3 score).

---

## The three days

| Wear day | From → to | Role |
|---|---|---|
| Day 1 | Mon 16 (after school) → Tue 17 12:00 | **Practice and tuning.** Do everything exactly as on the other days. |
| Day 2 | Tue 17 12:00 → Wed 18 12:00 | **Exam** |
| Day 3 | Wed 18 12:00 → Thu 19 12:00 | **Exam** |

Each wear day runs noon to noon, so each one holds one night.

> Ημέρα 1 = εξάσκηση/ρύθμιση, ημέρες 2–3 = εξέταση. Κάνε τα ίδια ακριβώς πράγματα και τις τρεις μέρες.

---

## What you need

- The band with `08_logger` flashed (`fw/08_logger/README.md`, steps 1–6).
- USB-C **data** cable and the Mac, with the `tools` folder in Downloads and `pyserial` installed.
- A **clinical digital oral thermometer** (±0.1 °C; not a kitchen thermometer). The same one every time.
- Your phone with a BLE UART app (nRF Connect or Bluefruit Connect), to send `mark` when away from the Mac.
- This protocol's checklist on paper, and a pen. Or a note on your phone.
- Optional: a room thermometer; a fan.

> Χρειάζεσαι: βραχιόλι, καλώδιο, Mac, ιατρικό θερμόμετρο στόματος, κινητό με εφαρμογή UART, χαρτί για ημερολόγιο.

---

## Step 1 — Monday after school: start

1. Flash and check the band with `fw/08_logger/README.md` steps 1–6. Every sensor in `stat` must show 1.
2. Make one folder for the whole test and go into it (all dumps will land there):

```
mkdir -p ~/Downloads/wear_test
```

```
cd ~/Downloads/wear_test
```

3. Set the band's clock (close the Arduino Serial Monitor first):

```
python3 ~/Downloads/tools/capture.py time
```

4. Put the band on your **non-dominant wrist**, sensor touching the skin, snug: it must not slide when you shake your hand. Use this wrist and this position for all three days.
5. Mark it:

```
python3 ~/Downloads/tools/capture.py cmd "mark 1"
```

6. Unplug. Write the start time on the checklist.

> Βήμα 1: Φλασάρισμα, ρύθμιση ώρας, φόρεμα στο μη κυρίαρχο χέρι, `mark 1`, αποσύνδεση.

---

## Step 2 — How to label events

There are three ways to put a label in the recording. Use whichever you can at that moment.

| Way | How | Use it for |
|---|---|---|
| `mark` command | Mac: `python3 ~/Downloads/tools/capture.py cmd "mark 5"`. Phone: open the UART app, connect to **HeatGuardian**, send `mark 5` | donned, loose, off, shower, out, home, oral |
| Button press | One **short** press of the band's button, then write the time and the code in the diary | sleep, wake, meals, walk, hot room, fan, sport |
| Diary only | Write the line, no press | pulse, room thermometer, notes |

**The `mark` numbers**

| Mark | When |
|---|---|
| `mark 1` | you just put the band on (also after re-tightening a loose band) |
| `mark 2` | you loosened it on purpose (loose test) |
| `mark 3` | you just took it off (charging, room test, sport) |
| `mark 4` | you took it off for a shower |
| `mark 5` | you leave home |
| `mark 6` | you are back home |
| `mark oral 36.85` | an oral thermometer reading, with your number |

**Diary codes that need a button press** (press first, then write the line): `SLEEP` `WAKE` `MEAL_START` `MEAL_END` `WALK_START` `WALK_END` `HOT_START` `HOT_END` `FAN_START` `FAN_END` `SPORT_START` `SPORT_END`.
**If you could not type a mark** (hands full at the door, no phone in PE): press the button and write `OUT`, `HOME`, `OFF` or `DONNED` instead.
**Never press long (2 s)**: that is the HELP marker.
Keep at least **1 minute** between two labels.

> Βήμα 2: `mark` για φόρεμα/βγάλσιμο/χαλάρωμα/έξω/σπίτι/θερμόμετρο· σύντομο πάτημα κουμπιού + γραμμή στο ημερολόγιο για ύπνο, ξύπνημα, φαγητό, περπάτημα, ζεστό δωμάτιο, ανεμιστήρα, γυμναστική.

---

## Step 3 — Oral thermometer reading (exact procedure)

Three sessions a day: **07:00**, **16:30**, **22:15**. Each session = two readings, 2 minutes apart, then a pulse count.

1. Nothing to eat or drink, no gum, no tooth brushing for **15 min** before (30 min after a hot or cold drink or after sport).
2. Sit still for 5 min (afternoon and evening: you have been sitting for about 30 min).
3. Tip under the tongue, far back to one side. Close your lips. Breathe through the nose. Do not talk.
4. Wait for the beep. Read the number.
5. Send it: `mark oral 36.85` (your number; `36,85` also works). The band answers `stored 36.85 C`.
6. Wait 2 minutes. Repeat 3–5 for the second reading.
7. Count your pulse for **60 seconds** on the other wrist (or the neck). Write `PULSE` with the number in the diary.

The exam compares these readings with the range the band would have shown. It is **not** a test of core temperature (the mouth is not the core).

> Βήμα 3: 3 φορές τη μέρα, δύο μετρήσεις με 2 λεπτά διαφορά, `mark oral` με τον αριθμό, μετά σφυγμοί 60 δευτ. στο ημερολόγιο.

---

## Step 4 — Every morning (Tue, Wed, Thu)

1. When you get out of bed: **press** the button, write `WAKE`.
2. 07:00: oral session (Step 3), before breakfast.
3. Plug the USB in (the band can stay on your wrist; the band notes USB by itself). Pull the new data, then set the clock:

```
cd ~/Downloads/wear_test
```

```
python3 ~/Downloads/tools/capture.py dumpnew
```

```
python3 ~/Downloads/tools/capture.py time
```

4. Unplug. Check the screen (one press): `Log OK`, `Time set`.
5. Leaving home: `mark 5` from your phone (or press + `OUT`).

> Βήμα 4: Κουμπί + WAKE, θερμόμετρο 07:00, dumpnew και time από το Mac, `mark 5` φεύγοντας.

---

## Step 5 — School

Nothing to do. Keep the band on and under your sleeve.
If you take it off for PE: `mark 3` (or press + `OFF`), and `mark 1` (or press + `DONNED`) when it is back on. If you do sport with it on: press + `SPORT_START` / `SPORT_END`.

> Βήμα 5: Στο σχολείο τίποτα. Αν το βγάλεις στη γυμναστική, σημείωσέ το.

---

## Step 6 — Every afternoon at home (Mon to Wed)

Do them in this order if you can (times are a guide). Keep at least 10 min between two activities.

1. **Arrive (about 15:00):** `mark 6`. Sit in one room for 30 min.
2. **Room test (about 15:30, once a day):** take the band off, `mark 3`, lay it on the table face up, away from sun, heater and laptop. Do not touch it for **15 min**. Put it back on, tighten, `mark 1`. Then **stay home with the band on for 60 min** (no loose test, no walk in that hour; sitting or moving around the house is fine).
3. **Oral session at 16:30** (Step 3).
4. **Your usual walk** (only if you walk anyway that day, e.g. home from school or an errand; never extra exercise for the test): `mark 5` at the door, press + `WALK_START` when you start walking briskly, press + `WALK_END` when you stop, `mark 6` back home.
5. **Warm moments that happen anyway** (no heater on purpose, nothing done to heat you up): if you are somewhere warm as part of normal life (kitchen while dinner is being cooked, a warm classroom or bus), press + `HOT_START` and `HOT_END`. If you have a room thermometer, write `ROOM` with its reading. If it does not happen, skip it.
6. **Fan, 10–15 min** (skip if no fan): sit in front of a fan on medium. Press + `FAN_START`, press + `FAN_END`.
7. **Loose test, twice** (once sitting, once doing light things around the house): loosen the strap by two holes, so it can turn and slide a little. `mark 2`. Leave it loose **10 min**. Tighten it back, `mark 1`.
8. **Meals at home:** press + `MEAL_START`, press + `MEAL_END`.

> Βήμα 6: Τεστ δωματίου 15΄ και μετά μία ώρα στο σπίτι με το βραχιόλι, θερμόμετρο 16:30, ο συνηθισμένος σου περίπατος (όχι επιπλέον άσκηση), ζεστές στιγμές μόνο αν συμβούν φυσικά (όχι καλοριφέρ επίτηδες), ανεμιστήρας, δύο φορές χαλαρό λουράκι για 10΄, κουμπί στα γεύματα.

---

## Step 7 — Every evening (Mon to Wed)

1. **About 20:00, charge and pull data:** take the band off, `mark 3`, plug the USB in, and run:

```
cd ~/Downloads/wear_test
```

```
python3 ~/Downloads/tools/capture.py dumpnew
```

```
python3 ~/Downloads/tools/capture.py time
```

   Leave it charging on the desk (a hard surface, where you can see it; never in bed, never under a pillow) until `stat` shows `vbat` 4.1 V or more, about 2 hours. **Shower while it charges** (then no extra mark is needed).
2. **About 22:00, put it back on:** tighten, `mark 1`. Stay home with it on (this hour measures how fast the sensor warms up).
3. **Oral session at 22:15** (Step 3).
4. **Lights off:** press + `SLEEP`. Sleep with the band on.
5. Type today's paper diary into `~/Downloads/wear_test/diary.csv` (format: `diary_template.csv`).

If you shower at another time: take the band off, `mark 4`; dry your wrist, wait 5 min, put it back on, `mark 1`.

> Βήμα 7: `mark 3`, φόρτιση και dumpnew από τις 20:00 (ντους όσο φορτίζει), `mark 1` στις 22:00, θερμόμετρο 22:15, κουμπί + SLEEP, πέρασμα ημερολογίου.

---

## Step 8 — Thursday Nov 19: finish

1. Morning as in Step 4 (WAKE, 07:00 oral, dumpnew, time).
2. After school, a full final pull:

```
cd ~/Downloads/wear_test
```

```
python3 ~/Downloads/tools/capture.py dump
```

3. Check that `diary.csv` is complete. Send the whole `wear_test` folder to Claude. **Do not run any analysis yourself.** The manager tags `wear-freeze` before the data are opened.

> Βήμα 8: Πέμπτη πρωί όπως πάντα· μετά το σχολείο πλήρες `dump`, έλεγχος ημερολογίου, αποστολή φακέλου.

---

## Step 9 — Older relative: NOT in this test

A second person wearing the band is human-participant research that needs ethics (IRB) approval **before** any data are collected; approval cannot be given afterwards (research/R8). This step is postponed until a proper protocol has been approved. Do not put the band on anyone else.

> Βήμα 9: Όχι σε αυτό το τεστ. Κανείς άλλος δεν φοράει το βραχιόλι μέχρι να υπάρξει έγκριση δεοντολογίας.

---

## Problems

| You see | Do this |
|---|---|
| Screen says `Time NOT SET` (the band restarted) | at the next chance: `python3 ~/Downloads/tools/capture.py time`. Write `NOTE restarted` in the diary |
| You forgot a mark | write the real time and what happened as a `NOTE`. Do not send a late mark |
| A label went wrong (wrong number) | send nothing more; write a `NOTE` with the time and the correct meaning |
| Band hot, swollen, smells, or skin red or itchy | take it off, unplug it, write a `NOTE`, tell Claude. Your skin comes first |
| Fever or feeling ill | keep wearing if you are fine with it, and write `NOTE fever` with the time. Do not take paracetamol before an oral reading without noting it |
| `capture.py` says `No band found` | close the Arduino Serial Monitor; replug the cable; try again |

> Προβλήματα: αν χαθεί η ώρα, `time`· ό,τι ξεχάσεις, γράψ' το ως NOTE· αν ζεσταθεί το βραχιόλι ή ερεθιστεί το δέρμα, βγάλ' το.
