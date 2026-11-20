# What is still not known (v6.1)

Everything a datasheet, a CAD file or one of your photos could settle is settled (see `SOURCES.md`). What is left can only be read
off **your own parts**. A ruler, a pencil and your phone are enough. Ranked by how much each answer changes the print.

## 1. How tightly your wires bend (v6: most urgent)

- **Why:** v6 is laid out so no wire bundle bends tighter than `WIRE_BEND_R` = 8 mm (a guess) and the lone blue screen wire no tighter
  than `WIRE_BEND_R_SINGLE` = 4 mm (a guess). The brain pod's width, the screen-cable run and every turn come from these.
- **How:** take spare pieces of your 28AWG hook-up wire, as in the harness: (a) a bundle of 4 with a solder joint and a hot-glue blob
  at one end, (b) one loose wire. Bend each gently round a pencil (8 mm dia = 4 mm radius), a marker (~15 mm dia), a glue stick
  (~20 mm dia). The smallest one it follows without forcing, kinking or springing hard back = its diameter / 2.
- **Put the numbers in:** `WIRE_BEND_R`, `WIRE_BEND_R_SINGLE`, then `python3 build.py`. Smaller -> the brain pod gets narrower
  (5 mm: 3 mm narrower). Larger than 8 -> the build flags the turns that no longer fit; send me the number.
- **v6.1:** the heart island is gone; in the skin island every bundle bends at 8 mm or more (the Cs are 12 and 14). Only hop 5 (a
  flat 4-wire ribbon C, R 4.4) and TMP117 #1's two single GND tails (R 4) use `WIRE_BEND_R_SINGLE`: check a flat ribbon of 4 wires too.

## 2. Wire runs: the few numbers still missing (v6.1: your measured lengths are in)

- **Which screen wire is the 25 mm one.** If it is the blue (to the D0..D6 row), it is 3 mm short of the 28 it needs.
- **Hop 2 and the button pair:** the twin needs 45.3 (hop 2) and 33.6 (button); your shortest are 45 and 34.5. Measure those exact
  wires again, pad to pad, pulled straight.
- **Hop 5:** which of the 4 wires are the 20 mm ones (each one gets +5 mm), and whether the 4 lie flat side by side (a ribbon).
- **TMP117 #1's two GND tails:** never measured; the twin uses ~15 mm each.
- **Put the numbers in:** `HOP*_LEN`, `BAT_LEN_M`, `BTN_LEN_M`, `LCD_LEN_M` in `params.py`, then `python3 build.py`. The Cs and the hop 6
  jog re-solve themselves; the wire table says what still needs a splice.

## 3. Screen plug: which pin goes to which XIAO pad

- **Why:** v6 re-solders the 8 screen wires at the XIAO end, short and pointing up into the plug. The twin assumes the plug's pins
  run in the same order as the XIAO's 5V/GND/3V3/D10/D9/D8/D7 pads, and that the blue wire is at the end of the plug nearest the
  elbow and goes to a D0..D6 pad (modelled on D6).
- **How:** one photo of the plug end straight from above, wires visible, and tell me which colour goes to which pad.

## 4. Which XIAO pads the HELP button uses

- **Why:** the twin lands the button pair on D5 (+ GND) from the open floor. Another pad moves the landing point by 2.54 mm per pad.

## 5. TMP117 #1: height of everything on its chip side

- **Why:** the chip only touches the skin if nothing else on that side is taller than 0.6 mm.
- **Now in the model:** header joints 3.0 mm (from your tin photo), the new GND joints on the socket tab pads 2.0 mm (a pure guess, no photo yet).
- **How:** board chip-up on the desk, phone exactly side-on, ruler standing behind it. One photo of each long side.
- **Put the numbers in:** `TMP1_BLOB_H`, `TMP1_TAB_BLOB_H`.
- **Also tell me:** are the GND wires on the tab pads at one short end or at both, and which way do they run from there?

## 6. MAX30102: does the board sit flat in its seat?

- **Why:** the positions of its parts were read from one photo (± 0.4 mm). The seat touches the board in only three part-free places.
- **How:** after printing, drop the board in sensor-down and press each corner. If it rocks, tell me which corner is high.
- **Also:** look through the window from the skin side. The whole black chip must show (window 6.6 × 4.3 mm). If it is cut off on one side, tell me which.

## 7. MAX30102: solder points on the back

- **Why:** v6.1 no longer stacks the ICM over it, so this only matters for the press foot. Low priority.
- **Now in the model:** 0.6 mm (a guess; no photo shows the back side-on).
- **How:** side-on photo of the board, sensor down.
- **Put the number in:** `MAX_BACK_H`.

## 8. Your USB-C cable plug

- **Now in the model:** the largest plug the USB specification allows (12.35 × 6.5 mm). The tunnel through the brain pod's hand wall is 13.55 × 7.7 mm (v6: the plug goes about 4 mm into the wall).
- **How:** ruler across the plastic part right behind the metal tip. Only matters if yours is wider than 13.5 mm.

## 9. Wrist shape

- **Why:** it sets how deep the curved undersides are. It does not matter for the flat-bottom prints.
- **Now in the model:** width ÷ thickness = 1.35 (a guess).
- **How:** two photos of your wrist where the band sits, ruler across it: once from above (width), once from the side (thickness).
- **Put the number in:** `WRIST_ASPECT`.

## 9. Battery: length and lead corner

- **Length:** your cell is longer than the 31.1 mm v3 cradle. v4 makes the cradle 33.1 mm. The twin assumes the cell is 31.6 mm (a guess).
- **Lead corner:** your photo d8ea4884 shows the leads at one corner of the protection-board end. The cradle has relief at both corners.
- **How:** photo of the cell from above next to a ruler. Then set `BAT_L_REAL` and `BAT_LEAD_CORNER`.

## 10. Foam pad

- v4 needs **2.8 mm** of foam between the battery and the screen standoff (v3: 0.8), because the screen sits 1.2 mm higher.
- Two layers of 1 mm foam tape. If you only have thicker foam, tell me its thickness.

## Settled in v3 and v4, no longer on this list

- MAX30102 size, pad edge, holes and chip position (photos).
- XIAO and DRV2605L board thickness, and which side their wires leave.
- Screen socket position and size, standoff diameter.
- USB-C plug size (specification), wire thickness, button body height.
- v4: free wire per hop ~30 mm (your estimate), the screen cable ~30 mm (measured), the battery cradle was too short, the motor cup fits.
- v4.1: glue + wires under the XIAO ~2 mm (you, ruler): the XIAO stands 2.5 mm up on corner rests.
