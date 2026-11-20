# Wear test checklist (print me) — Mon 16 to Thu 19 Nov

Tick each box and write the time next to it. Press = one short button press + a diary line. Never press long.

| When | What | Mon 16 | Tue 17 | Wed 18 | Thu 19 |
|---|---|---|---|---|---|
| Out of bed | press + `WAKE` | — | ☐ __:__ | ☐ __:__ | ☐ __:__ |
| 07:00 | oral ×2 (`mark oral 36.xx`, 2 min apart) + `PULSE` | — | ☐ | ☐ | ☐ |
| Before leaving | USB in → `dumpnew` → `time` → unplug | — | ☐ | ☐ | ☐ |
| Leaving home | `mark 5` (or press + `OUT`) | — | ☐ | ☐ | ☐ |
| PE | off `mark 3` / on `mark 1`, or press + `SPORT_START/END` | — | ☐ | ☐ | ☐ |
| Back home | `mark 6` (or press + `HOME`) | ☐ __:__ | ☐ | ☐ | ☐ |
| Start (Mon only) | flash, `stat`, `time`, put on, `mark 1` | ☐ __:__ | — | — | — |
| ~15:30 | room test: `mark 3`, 15 min on the table, `mark 1`, then 60 min at home | ☐ | ☐ | ☐ | — |
| 16:30 | oral ×2 + `PULSE` | ☐ | ☐ | ☐ | — |
| Afternoon | usual walk only (no extra exercise): `mark 5`, press `WALK_START` … `WALK_END`, `mark 6` | ☐ | ☐ | ☐ | — |
| If it happens | warm moment in normal life (no heater on purpose): press `HOT_START` … `HOT_END` | ☐ | ☐ | ☐ | — |
| Afternoon | fan 10–15 min: press `FAN_START` … `FAN_END` | ☐ | ☐ | ☐ | — |
| Afternoon | loose test 1 (sitting): `mark 2`, 10 min, `mark 1` | ☐ | ☐ | ☐ | — |
| Evening | loose test 2 (moving): `mark 2`, 10 min, `mark 1` | ☐ | ☐ | ☐ | — |
| Meals | press `MEAL_START` / `MEAL_END` | ☐ | ☐ | ☐ | — |
| ~20:00 | off `mark 3`, charge, `dumpnew`, `time`, shower while charging | ☐ | ☐ | ☐ | — |
| ~22:00 | vbat ≥ 4.1 V → put on, `mark 1`, stay home 1 h | ☐ | ☐ | ☐ | — |
| 22:15 | oral ×2 + `PULSE` | ☐ | ☐ | ☐ | — |
| Lights off | press + `SLEEP` | ☐ __:__ | ☐ __:__ | ☐ __:__ | — |
| Before bed | type the day into `diary.csv` | ☐ | ☐ | ☐ | — |
| After school (Thu) | full `dump`, check `diary.csv`, send the folder | — | — | — | ☐ |

**Oral reading:** 15 min no food, drink, gum or brushing · sit 5 min · tip far back under the tongue, lips closed, nose breathing · wait for the beep · `mark oral <number>` · again after 2 min · pulse 60 s.

**Commands (Mac, from `~/Downloads/wear_test`):** `python3 ~/Downloads/tools/capture.py dumpnew` · `python3 ~/Downloads/tools/capture.py time` · `python3 ~/Downloads/tools/capture.py cmd "mark 1"`. Phone: UART app → HeatGuardian → send `mark 5`.

**If:** screen says Time NOT SET → run `time` soon, `NOTE restarted` · forgot a label → `NOTE` with the real time, no late mark · band hot or skin red → take it off, `NOTE`, tell Claude.

> Ημέρα 1 (Δευτ.–Τρίτη μεσημέρι) = εξάσκηση· ημέρες 2–3 = εξέταση. Ίδια πράγματα κάθε μέρα. Ό,τι ξεχάσεις, γράψ' το ως NOTE.

**Only you wear the band. Nothing done on purpose to heat you up.** (Fair rules, research/R8.)
