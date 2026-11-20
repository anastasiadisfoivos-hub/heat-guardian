# Assembly: Heat Guardian stage 1, v7.0 FINAL EDITION (two pods + skin island with the SHTC3 shelf)

Built round a **digital twin**: every board, glue blob and wire is modelled, and the computer checks collisions, wire bend radii,
pad rooms, free heights and opening widths before anything is printed (`CLEARANCES.txt`). New in v7.0: it also refuses to build
anything thinner than 1.2 mm or any slender post (`FRAGILITY.txt`).

**Print:** `out/stl_flat/` - `brain_pod`, `brain_frame`, `power_pod`, `power_lid`, `island_skin`, `island_shelf` (not `island_air`).
**Pictures:** `png/v70_<part>.png` (each part as printed), `png/v70_tmp2_stack_section.png`, `png/v70_top_hole_spacing.png`.

## v7.0 assembly order: DRY FIT EVERYTHING FIRST, glue last

Hot glue only. No part is a press fit: if something needs force, stop - it is in the wrong place or a glue blob is in the way.

**A. Dry fit, no glue (about 10 minutes). Every line is a test - tick it.**

1. **Lids on the empty pods.** Brain cover onto the brain pod, power lid onto the power pod. They must slide on by hand (0.3 mm per
   side, chamfered edge) and sit level. Take them off again.
2. **USB-C.** XIAO straight down between its four corner blocks, USB-C toward the tunnel. Plug the cable in fully through the
   tunnel. The board must lie flat on all four blocks and not move when you plug / unplug. Unplug.
3. **Screen.** Lay the screen on its seat (wall tops + the two corner posts). It must lie flat without being pushed up by wires.
   Put the cover on over it: level, not rocking.
4. **Motor + DRV2605L.** Motor into its cup (do not peel the sticker yet). DRV onto the cup rim and its two pins. Flat, no rocking.
5. **Battery + button.** Cell into its cradle, lid on: the lid must close with the switch plunger in the square hole, below the lid top.
6. **ICM-20649.** Back edge first onto the two back pins, then down onto the two front rests. Flat.
7. **MAX30102.** Two paperclip pins (cut to 2 mm) into the two sockets (0.6 mm deep in v7.0: they only locate), board sensor-down onto them. Look from
   the skin side: the whole black chip shows in the window, a hair proud; the board does not rock.
8. **TMP117 #1.** Slide it in FLAT from the bay, chip down, under the plate. Do not lever on the thin floor. Chip in its window.
9. **TMP117 #2 - the one that did not fit before.** Chip down, straight above #1: back holes onto the two pins (20.0 mm apart),
   board down flat. Press lightly over the chip: it must not rock. Press the pad edge: it must not tip (front rests). Check all
   four hop-5 wires reach without pulling a pad (needs 17.5 mm, your shortest is 20).
10. **Shelf.** With the MAX and its wires in: shelf straight down, the two keys show in its two holes, hand edge on the rib, elbow
    edge in the rebate. It must lie flat and touch nothing on the MAX (look under it from the bay).
11. **SHTC3.** Sensor up, back holes onto the shelf's two pins, down onto the two front rests, between the lips and the stops.

If any line fails, do not glue. Write down which line, which side binds, and by how much.

**B. Glue, in this order. One small dot each, let it set (30 s) before the next part.**

12. Neoprene: glue / stitch the flanges of the brain pod, power pod and skin island to the strap with 8 mm of free neoprene between
    the brain cover's skirt and the power lid's skirt, and between the power lid's skirt and the skin island.
13. **Power pod:** motor (its own sticker) -> DRV2605L (glue: the two pin tips) -> hop 2 out of the elbow opening, hop 1 out of the hand
    opening (glue: one dot on the floor 3 mm inside each opening, on the wire insulation, never on a splice sleeve) -> cell (no glue)
    -> switch (glue it the way you did on the v6.7.2 lid, at the square hole: body only, nothing on the plunger) -> lid (glue: two dots inside the
    skirt on the long sides, away from the openings).
14. **Brain pod:** crossing wires in through the elbow opening (glue: one dot on the floor 3 mm inside the opening) -> XIAO (glue:
    ONLY on the two far-end corner blocks, away from the USB-C; none at the USB end, none near the reset button) -> screen wires
    into the garage (glue: one dot on the garage floor under the fold's lower leg, one where the fold touches the end wall) ->
    screen on its seat (no glue; the cover holds it) -> cover (glue: two dots inside the skirt on the long sides).
15. **Skin island:** ICM (glue: the two back pin tips) -> MAX pins + MAX (glue: ONLY in the two glue wells at its back corners) ->
    TMP117 #1 (glue: one dot at each front corner, on the tab where the floor meets the pillar; nothing near the chip window) ->
    strap tongue into the slot -> TMP117 #2 (glue: the two pin tips, then a dot at each back corner in the 0.6 mm gap; NEVER under the
    chip or on the pedestal) -> hop 2 / hop 3 / hop 4 into the bay (glue: one dot at each C's apex and one at the hop-2 entry, on the
    bay floor) -> hop 5 straight up -> shelf (glue: one dot on each key, through the holes) -> SHTC3 (glue: the two pin tips; nothing
    on the sensor) -> hop 6 as one C over the bay.

## Where the glue goes, board by board

| Board | Glue here | Never here |
|---|---|---|
| XIAO | the two far-end corner blocks (shoulder beside the board corner) | USB-C end, reset button, the castellated pad rows |
| Screen | none (the cover holds it); wires: garage floor + end wall | glass, the plug |
| DRV2605L | tips of its two pins | the motor, the 'I2C PU' jumper |
| Battery | none | anywhere on the cell |
| HELP switch | as on the v6.7.2 lid, at the square hole: body only | the plunger, the dish |
| ICM-20649 | tips of the two back pins | the chip |
| MAX30102 | the two glue wells at its back corners (over the pin holes) | sensor face, window, pad-edge side, its back joints under the shelf |
| TMP117 #1 | front corners, on the floor tabs at the two pillars | chip, chip window |
| TMP117 #2 | tips of the two pins, back corners in the 0.6 mm edge gap | chip, chip pedestal, under the board |
| Shelf | the two keys (through the holes) | the MAX under it |
| SHTC3 | tips of the two pins | the sensor, the vents |

## What changed in v7.0 (final edition: nothing redesigned, everything made unbreakable)

- **The two things that broke are gone.** The plate under TMP117 #2 had pockets with 0.3-0.4 mm floors (two socket pockets + the
  joint relief). The plate is now a **solid 1.2 mm**; #2 stands 0.8 mm higher instead (board 10.1-11.7 mm above the skin), on two
  **back blocks** tied into the back wall, a **chip pedestal** with a 45 degree flare, and two **front rests** 0.15 mm under its front corners.
- **TMP117 #2's pins are 20.0 mm apart** (your measurement; they were 20.32 from Adafruit's file). All pins are now straight 1.8 mm
  pins on a **flat seat**: the old centring cone was wider than the hole when printed in 0.2 mm layers and held the board up, and with
  two cones any error in the spacing jammed. 1.8 mm pins in 2.5 mm holes accept 19.3-20.7 mm.
- **No floor, wall, web or lip under 1.2 mm** (was 0.4-1.0 in many places): pod floors 1.0 -> 1.2, battery floor 0.8 -> 1.2, motor
  floor 0.6 -> 1.2, bay floor 0.8 -> 1.2, MAX pocket walls 0.8 -> 1.2, shelf 1.0 -> 1.2, cover lip 1.0 -> 1.2, power lid 1.2 -> 1.7
  (1.2 left under the dish, was 0.7), wall beside the shelf rebate 0.9 -> 1.2, ICM hand wall 1.1 -> 1.2. The 0.4 mm glue recesses
  in the floors are removed. Two listed exceptions: the floor under TMP117 #1 (0.6) and under the MAX30102 (0.8-1.05); see `FRAGILITY.txt`.
- **TMP117 #1's floor is tied to two pillars** at its front corners (its corner tabs hung on 1.35 mm necks).
- **Fewer, sturdier posts.** ICM and SHTC3: four flat bosses, pins only in the two back holes (away from the wires). DRV posts
  4.2 -> 4.6 mm with a flared foot. XIAO: four solid corner blocks instead of 1.25 mm columns, two of them part of the hand wall.
  Screen posts are tied into the pod corners. Shelf pegs 1.2 x 0.8 -> keys 3.0 x 1.5 on a 4 mm wide ledge.
- **Lead-in chamfers** on the XIAO lips, SHTC3 lips and stops, MAX rim, motor cup, pin tips, and the cover / lid skirts.
- **Fits:** cover and lid 0.2 -> 0.3 mm per side; shelf 0.15 -> 0.4; XIAO 0.3 -> 0.4. Board seats in the island keep v6.9's 0.7.
- Sizes: brain pod 35.1 x 60.6 x 17.6, power pod 40.6 x 55.9 x 10.5, skin island 89.8 x 38.9 x 14.2, shelf 26.4 x 19.5 x 4.2.
  Band 181.5 mm (v6.9: 179.7). **Where the older sections below disagree with this one, this one is right.**

## What changed in v6.9 (TMP117 #2 fitted with its wires soldered; looser board seats)

- **No re-solder on TMP117 #2.** It goes in with its wires exactly as they are. Room was made for joints + glue up to **3.0 mm**
  on the chip side (the side that faces down) and **2.5 mm** on the other side:
  - under its pad row, a **relief pocket** in the plate, 16.9 x 3.1 mm (plus open toward the bay), the joints + glue get 0.5 mm all
    round and 0.3 mm under them. The pocket is blind: a 0.4 mm floor stays over the strap slot, so the strap never touches a joint.
  - its two sockets sit in blind pockets 6.55 x 7.6 mm (0.8 mm round each socket), 0.3 mm above the pocket floor.
  - the back-side joints + glue stand in open air (top at 13.4 mm above the skin).
  - in front of the pad edge there is at least 5.5 mm of open air at #2's height for the wires to leave and bend (R4).
  - 0.6 mm free all round the board outline, so you can put glue at the edges.
- **The chip lies flat.** A 1.8 x 1.8 mm **chip rest** stands on the plate right under #2's chip. The chip sits on it with no air gap,
  and the board rests on 3 points: its two posts and the chip rest. #2 is 0.44 mm higher than in v6.8 (board 9.3-10.9 mm above
  the skin). Hop 5 needs 16.7 mm instead of 16.3; your wires are 20-30.
- **Board seats looser** (your v6.8 print: the columns were a little too close, the sensor could not sit). Every wall, lip, stop
  and socket pocket that locates a board in the skin island and on the shelf is now 0.4 mm wider per side. Every printed pin
  that goes into a board hole is 0.3 mm thinner: 2.1 mm became **1.8 mm**. The SHTC3 seat on the shelf is now 26.8 mm long
  (v6.8: 26.0) and has 0.7 mm at the back (v6.8: 0.3).

  | Board seat | v6.8 | v6.9 |
  |---|---|---|
  | SHTC3 on the shelf: hand lip to elbow stops | 26.0 | 26.8 |
  | SHTC3 on the shelf: back lip to board | 0.3 | 0.7 |
  | SHTC3 pins (4) | 2.1 | 1.8 |
  | TMP117 #2 pins (2) | 2.1 | 1.8 |
  | TMP117 #2 socket pockets | 5.75 x 6.8 (0.4/side) | 6.55 x 7.6 (0.8/side) |
  | TMP117 #1 pocket between the side walls (also the strap slot) | 26.0 | 26.8 |
  | TMP117 #1 back wall gap | 0.3 | 0.7 |
  | ICM-20649 pins (4) | 2.1 | 1.8 |
  | ICM-20649 to the hand wall / back wall / shelf rib | 0.3 / 0.3 / 0.3 | 0.7 / 0.7 / 0.7 |
  | MAX30102 board pocket (along x across) | 20.0 x 13.2 (0.5/side) | 20.8 x 13.6 (0.9/side) |

  The MAX30102's paperclip pin sockets (metal pins) and the shelf's own fit in the island (0.15) are unchanged.
- **Print fixes** (island_skin, island_shelf; your print settings are unchanged):
  - the plate under #2 had through-holes, so its bridge ended in mid-air. The pockets are blind now, so the first layers bridge
    rib to rib.
  - the plate's 1.5 mm cantilever past the side walls is gone.
  - the side walls bridged the GND-tail channels from one end only (11.6 mm). They now have a pillar at the front end.
  - the 0.5 mm wall left beside the shelf rebate is now 0.9 mm (the hand-side wall is 1.6 mm thick).
  - 0.1 to 0.6 mm slivers between the MAX30102 part pockets are opened.
  - on the shelf, the vents were cut right through the lips: v6.8 left a 0.3 mm skin that also closed them.
  - the shelf's 0.15 mm slivers round the two peg holes are fixed. The holes are blind from below now, with a small tab outside.
  - the thin lip piece next to the ICM socket is removed.
- The skin island is 1.4 mm longer and 0.4 mm wider. The band is now 179.7 mm. The brain pod, power pod and their lids are unchanged.
- Pictures: `png/v69_tmp2_gap_cutaway.png` has three sections: across the wrist through #2's chip, along the chip line, and along
  the pad row. `png/v69_tmp2_gap_top.png` is the top view, with the relief pocket, the wire-exit room and the glue ring marked.

## What changed in v6.8 (SHTC3 shelf over the MAX30102; button on D2)

- The **SHTC3 moves off the cage on TMP117 #2** onto a new **drop-in shelf** (`stl/island_shelf.stl`) over the MAX30102. The shelf
  is on the **same upper floor as TMP117 #2**: its top is at 6.8 mm above the skin, exactly TMP117 #2's plate top. The SHTC3 and
  TMP117 #2 sit side by side up there.
- The shelf is a separate part because the MAX30102 (paperclip pins, part pockets under it) can only go in from above: a shelf
  printed onto the island would close its seat. It drops in after the MAX, the ICM and hops 3 / 4 are in.
- It rests on three seats in the island: the **back wall** (now 5.8 mm tall over the MAX area, with two small locating pegs), a
  1.2 mm **rib at the hand end** (in the gap between the ICM and the MAX) and a 0.7 mm **rebate** in the top of TMP117 #2's side
  wall. Nothing presses on the MAX: the shelf underside is 3.6 mm above the MAX's back (3.1 on the flat set) and 1.1 mm above its
  joints + glue (0.6 flat). Over the middle of the MAX's pad row the shelf is cut away: the **wire channel** (red dashed in
  `png/v68_top.png`), so the MAX wires leave into the bay exactly as before.
- **SHTC3 seat:** 25.4 x 17.8 board + 0.3 mm per side, on 4 posts with pins at its holes (1.0 mm of still air between the shelf and
  the board). Lips on the back and hand sides (with vent slots), stops on TMP117 #2's plate at the elbow side, **open toward the
  bay** for its wires. Sensor face **up**, nothing over it.
- **Hop 6** (60 mm) is now ONE C over the bay from TMP117 #2's pads to the SHTC3's pads, leaning 45 degrees up (top about 21 mm
  above the skin).
- The old air-island cage (`stl/island_air.stl`) is **not used** any more (still built, do not print it).
- **HELP button:** it is wired **D2 -> GND** (D5 is SCL). See `WARNINGS.txt` item 9 about the button pair's length to D2.
- Pictures: `png/v68_outside.png`, `png/v68_cutaway.png` (sections across and along), `png/v68_top.png`.

## What changed in v6.7 (brain cover)

- The cover's skirt reaches 3 mm further down (5.5 mm overlap), cut away over the elbow opening so the crossing wires still pass.
- Stops inside the cover land on the pod rim where the screen does not rest on it: along the whole garage-side wall, on the hand and
  elbow walls past the screen's edge, and two blocks in the -Y corners. The cover sits level and cannot sink or tilt.
- USB-C opening 1.0 mm bigger each way (14.5 x 8.7 mm, rounded), through the pod wall and the cover skirt, centred on the port.
- Picture: `png/v67_brain_cover.png`.

## What changed in v6.6 (TMP117 #2 straight above #1, SHTC3 on top)

- TMP117 #2 sits **straight above #1, chip down like #1**, pads aligned: hop 5 goes straight up round the two pad edges through a
  full-width slot (floor to top, open from above). It needs **16.3 mm** per wire incl. the joints.
- The **air island is now a vented cage on top of TMP117 #2** (no more side island, no flange notch): the SHTC3 sits
  3 mm over #2 in still air, open on all four sides and on top. Its pocket is the board + 0.5 mm per
  side with 3.5 mm more at the pad edge for the joints + glue; it drops straight in.
- Hop 6 (60 mm) makes ONE loop (radius ~9) standing in front of the stack, up to the SHTC3.
- Stack height at that end: cage top 19.0 mm, hop-6 loop top 22.0 mm.
- Picture: `png/v66_skin_air.png`.

## What changed in v6.5 (screen wires kept long: wire garage)

- The 8 screen wires are NOT re-soldered. The brain pod grows 12.4 mm across the wrist on the 5V-row side: a **wire garage**.
- The 7 wires to the 5V row lie side by side like a flat ribbon, go out of the castellations away from the XIAO, make ONE fold in
  the garage (radius ~4.7 for 45 mm wires, ~5.7 for 50 mm) and come back at plug height into the plug. The screen seat is unchanged
  and the screen rests flat with clearance over everything.
- The blue wire takes the shortest route (tight U-turn at the plug, diagonal to D6): 25.7 mm. A 25 mm blue reaches with a slightly
  tighter first turn (see `WARNINGS.txt`).
- **Splice sleeves** (hop 1, battery leads) never sit inside the brain pod: each lies straight across the gap through the big
  openings. Lanes: hop 1 about 21 mm, battery leads about 11 mm (the cell fills the power pod). A longer sleeve gets a short new piece
  of heat-shrink over just the joint (no soldering). See `WARNINGS.txt`.
- Both XIAO pad rows keep 5 mm of clear floor and 11.75 mm of free height under the screen. The brain pod height is unchanged (17.15).
- Pictures: `png/v65_brain_pod.png` (both pods from above with the garage and the sleeve lanes; section through the fold with the
  screen resting) and `png/v65_side.png`.

## What changed in v6.4 (MAX30102 chip at the skin)

- With the sensor side now flat, the board drops so the optical chip stands **0.05 mm past the skin** (v6.3: 0.55 mm back).
- Each tall factory part gets its own close pocket. Four of them (tantalum caps, SOT-23) go through the skin face, so those parts show
  there with a 0.4 mm gap round them. The tantalum caps stand ~0.1 mm past the skin, like the chip.
- Light: if the PPG is noisy in daylight, one strip of black electrical tape over the MAX area (window cut out) or black nail
  varnish in the gaps closes them.
- Picture: `png/v64_skin_island.png` (top, skin side, section through the chip).

## What changed in v6.3 (MAX30102 re-soldered on its back)

- You re-solder the MAX30102's 7 wires on its **back** (away from the skin), with clean pads on the sensor side (`WARNINGS.txt`).
- (v6.3 had the skin side under the MAX closed except the window; v6.4 adds the part pockets above.) No shield plate.
- On the back: room for joints + glue up to 2.5 mm tall, 3 mm free height, 5 mm pad room toward the bay; hops 3 and 4 leave from there.
- The board pocket stays 0.2 mm per side looser than v6.1.

## What changed from v6 (v6.1)

- **Your measured wire lengths** (`params.py`, `HOP*_LEN`, `BAT_LEN_M`, `BTN_LEN_M`, `LCD_LEN_M`) are now the input. Goal: no re-soldering.
  Result: every chain wire is used **as it is**, except the screen cable (re-soldered at the XIAO as in v6, unavoidable) and the
  20 mm wire(s) of hop 5 (+5 mm splice). See `WARNINGS.txt`.
- **Spare wire is taken up inside the parts, not as band length.** The skin island has an open bay (the "labyrinth"): hop 3 and hop 4
  each lie in ONE wide C (radius 12 and 14, i.e. over the 8 mm rule) round a low 2.5 mm tongue wall, hop 6 makes one 25 mm jog
  (two 8 mm turns) over the bay. A C between two pad rows takes any length from the straight line to more than a half circle, so
  each run just gets rounder: no coil, no tight loop. Glue points (orange) at each C's apex and at each entry.
- **The heart island is replaced by the skin island**: ICM-20649, MAX30102 and the TMP117 pair in one row, all pad edges facing the
  bay, nothing stacked except TMP117 #2 over #1 through the strap. Its old 4 mm bundle bends are gone: every bundle bends at 8 mm or
  more. Only hop 5 (a flat 4-wire ribbon, R 4.4) and TMP117 #1's two single GND tails (R 4) use the single-wire rule.
- **Big wire openings** wherever a run leaves or enters (red, O1..O6 in the pictures): 16-30 mm wide, full height from the floor,
  open from the top so the wire drops in, R2 edges. The frame / lid / plate bridges the top of each.
- The **power pod is shorter** (34.6 mm inside) so that hop 1 + hop 2 (your shortest hop 2 is 45) span it.

## Pictures to open first

- `png/v61_overview_top.png`: the whole band from above, every run drawn with the length it needs and what you have, openings labelled.
- `png/v61_skin_island.png`: the skin island and air island: the two Cs, hop 5, hop 6's jog, the openings.
- `png/v61_brain_pod.png`, `png/v61_power_pod.png`: the pods open, labelled.
- `png/v61_side.png`: the band from the side, with every height.
- `png/v61_iso.png`, `png/v61_iso_open.png`: 3-D views, closed and open.
- `WARNINGS.txt`: **the re-solder / splice jobs and the wire table.** Do these first.

## The band, from the hand end

| Part | Size (mm) along forearm x across x tall | What is in it |
|---|---|---|
| Brain pod | 34.9 x 60.4 x 17.2 (incl. the 12.4 mm wire garage) | XIAO on the floor, screen on top, USB-C at the hand end |
| gap | 8 | neoprene hinge: hop 1, battery leads, button pair cross here, through O1 / O2 |
| Power pod | 40.4 x 55.7 x 10.3 | LiPo cell, DRV2605L on the motor cup, HELP button in the lid |
| gap | 8 | neoprene hinge: hop 2 crosses here, through O3 / O4 |
| Skin island | 88.4 x 38.9 x 13.4 (TMP117 #2's back-side joints + glue) | ICM-20649, MAX30102 (sensor down), TMP117 #1 (chip down) + #2, the wire bay |
| SHTC3 shelf | 26.9 x 20.3 x 4.0 (drop-in, v6.8; v6.9 seat 0.7 per side) | SHTC3 over the MAX30102, level with TMP117 #2 |

Total length along the forearm **179.7 mm** (v6.8: 178.3, v6.1: 178.1) (v6: 174.9, v4.3: 117.2); width across the wrist 77.9 mm. The band did not get shorter
because nothing is stacked any more: the three sensor boards lie side by side, each with 5 mm of clear floor in front of its pads.
Getting back to ~117 would need the ICM stacked over another board again (the v4 problem).

## Directions used here

- **Hand end / elbow end:** along your forearm. The brain pod is at the hand end.
- **Bay side:** in the skin island, the side where all the pad edges point (toward the air island). **Back wall:** the other side.
- **Lane:** in the power pod, the open strip between the DRV2605L and the cell rib.
- **Skin side:** the underside. **Outer side:** the top.

## Glue rules (read first)

**Allowed:** small hot-glue dots on the back of a board, on a wire joint or on a wire bundle.

**Never put glue on:** TMP117 #2's chip or its chip rest (v6.9: the chip must touch the rest); the MAX30102 sensor face, its window or its light ring; either TMP117 chip; the SHTC3 sensor; the battery;
the MAX30102's back-side joints under the SHTC3 shelf (the shelf must lie on its seats, not on glue).

v7.0: there are no glue recesses in the floors any more. The glue points are in the table at the top of this file.

## Before you start

1. Do every job in `WARNINGS.txt` (measure the bend radius, re-solder the screen cable at the XIAO, splice hop 5's 20 mm wire(s),
   re-measure the hop 2 and button wires).
2. Lay the chain flat on the desk in band order: screen + XIAO, LiPo + button, DRV2605L + motor, ICM-20649, MAX30102, TMP117 #1, TMP117 #2, SHTC3.
3. Have ready: the glue gun, a toothpick, two 2.5 mm pieces of paperclip (MAX30102 pins).

## 1. Neoprene first

Glue / stitch the four parts' flanges to the neoprene **with the gaps already right**: 8 mm of free neoprene between the brain
frame's skirt and the power lid's skirt, and between the power lid's skirt and the skin island (v6.8: no air island).
The wires go in afterwards and drop into the openings from above.

## 2. Power pod (do it before the brain pod: its wires go on into the brain pod)

Open `png/v61_power_pod.png`. Hand end left.

1. **Motor.** Peel its sticker, press it flat into the round cup. Its two thin leads go into the notch.
2. **DRV2605L.** Lower it onto the cup at the elbow end, pads toward the lane. Your wires are on its back and come out into the lane.
3. **Hop 2.** From the DRV's pads, straight along the lane and out of the elbow-wall opening (O3). Glue dot in the elbow glue zone.
4. **Hop 1.** From the DRV's pads, straight along the lane and out of the hand-wall opening (O2). Glue dot in the lane glue zone.
5. **LiPo cell.** Beyond the rib, lead end at the hand wall, leads at the **lane-side corner** (turn the cell over if needed). The
   leads go straight out of O2. Do not glue the cell.
6. **HELP button.** The switch sits in the hand-end corner by the DRV; its two wires go straight out of O2 at floor level.
7. **Lid.** Press it on. Its pocket comes down over the switch; the plunger sits just below the lid top in a 6 mm finger dish. Its two
   ribs hold the cell down; a third rib holds the DRV.

## 3. Brain pod

Open `png/v61_brain_pod.png`. Hand end left.

1. **Crossing wires in.** Hop 1, the battery leads and the button pair drop into the one big elbow-wall opening (O1, 30 mm wide).
   Each crosses the gap straight. Glue dots in the two glue zones inside the elbow wall.
2. **Battery leads** run under the XIAO's far end to its BAT pads. **Hop 1** ends at the XIAO's far end. The **button pair** runs
   along the XIAO's D-row edge to **D2** (the other wire to GND). Not D5: D5 is SCL.
3. **XIAO.** Parts up, USB-C toward the hand wall, onto its 4 corner rests. Plug a USB-C cable in through the tunnel: it must go in
   all the way. Unplug it.
4. **Screen cable (wire garage).** The 7 wires to the 5V row: from the castellations straight out and down onto the garage
   floor, side by side; ONE fold up and back toward the XIAO; then straight over the XIAO at plug height into the plug. Glue the
   floor leg in the orange zone and the fold's far end against the end wall. The blue wire: tight U-turn right at the plug, then
   diagonally down to its D pad. Lower the screen face up onto its seat: it must rest flat; nothing pushes it up.
5. **Frame.** Press it on over the walls. Plug the USB-C cable in again to check it still seats fully.

Brain pod height **17.15 mm**: the screen board back sits 6.0 mm clear over the XIAO's top.

## 4. Skin island

Open `png/v61_skin_island.png`. Hand end left, bay at the top of the picture, back wall at the bottom.

1. **ICM-20649, parts up**, pads toward the bay, on its four bosses at the hand end (v7.0: pins in the two back holes only).
2. **MAX30102 pins.** Press the two paperclip pins into the two blind holes in the MAX30102 seat.
3. **MAX30102, sensor side down** (wires already re-soldered on its back), pads toward the bay, holes onto the pins. Its back-side
   joints and wires face up and point at the bay. Look from the skin side: the whole black chip shows in the window, a hair proud, and the board sits flat on its three pads (no part touching a pocket edge). One glue dot on
   the back of the board, at a corner (not on the joints' strip).
4. **TMP117 #1, chip down** (sockets snipped, chip-side joints flattened: WARNINGS), pads toward the bay, onto its 0.6 mm floor at the
   elbow end. The chip must show in its window and stand a hair proud. Its two GND tails leave through the side channels at its short
   ends (single wires, one gentle turn each).
5. **Strap.** The 3 mm neoprene strap tongue goes into the slot over TMP117 #1 from the back wall (slot takes a tongue up to 26.8 mm wide).
6. **TMP117 #2, chip DOWN** (like #1), pads toward the bay, straight above #1, **with its wires still soldered** (v6.9: no
   re-solder). v7.0: the plate is solid; its sockets and the joints + glue on its pad row hang free over it, and its back holes go onto the two pins. The **chip must lie flat on the chip rest**: press lightly over the chip. The board must not rock. If
   it rocks, a joint or glue blob on the chip side is taller than 3.0 mm: trim the glue, not the joint. Glue **only at the board edges**
   (the 0.6 mm gap round it) **or on the joints**. Never put glue under the chip or on the chip rest. Lead its wires out over the pad
   edge toward the bay without kinking them.
7. **Hop 2** comes in through the hand-wall opening (O4) and lies along the ICM's pad row. Glue dot at the entry.
8. **Hop 3 (ICM -> MAX30102, 51 mm):** lay it in from above as ONE wide C round the first tongue wall (R about 12). Glue dot at the apex.
9. **Hop 4 (MAX30102 -> TMP117 #1, 50 mm):** ONE wide C round the second tongue wall (R about 14). Glue dot at the apex.
10. **Hop 5 (TMP117 #1 -> #2):** each wire straight up from its pad on #1, round the edge, onto the same pad on #2, in the slot.
11. **SHTC3 shelf (v6.8).** Check first: the MAX30102 is in and glued, its wires and hops 3 / 4 lie in the bay. Lower the shelf
    (orange in the pictures; lips up) straight down over the MAX: its back edge onto the back wall (v7.0: the two keys show in its two
    holes), its hand edge onto the rib beside the ICM, its elbow edge into the rebate at TMP117 #2's side wall. The cut-out
    (wire channel) sits over the MAX's joints. It must lie flat and touch nothing on the MAX: look under it from the bay side. One
    glue dot on each key.
12. **SHTC3:** sensor (parts) **up**, pads toward the bay, back holes onto the shelf's two pins. It drops in between the back lip, the
    hand lip and the two stops on #2's plate. No glue on the sensor; one dot on a pin if it is loose.
13. **Hop 6 (TMP117 #2 -> SHTC3, 60 mm):** ONE C over the bay, from #2's pads (under #2) to the SHTC3's pads, leaning up (about
    45 degrees). Nothing may cover the middle of the SHTC3.

If a C comes out a little rounder or flatter than the picture, that is fine: that is where the spare length goes.

## 5. Air island

v6.8: there is no air island any more. The SHTC3 is on the shelf (steps 11-13 above); `island_air.stl` (the v6.6 cage) is not used.
Read the SHTC3 self-heating note in `WARNINGS.txt` before trusting its numbers.

## 6. Changing the numbers

If you measure different wire lengths or a different bend radius, put them in `params.py` (`HOP*_LEN`, `BAT_LEN_M`, `BTN_LEN_M`,
`LCD_LEN_M`, `WIRE_BEND_R`, `WIRE_BEND_R_SINGLE`) and run `python3 build.py`. The Cs and the hop 6 jog re-solve to the new lengths,
and the wire table and pictures update; the build stops if a bend, a pad room, a height or an opening breaks the rules.

## 7. Helper pieces (print later)

Separate small prints (`stl/helpers_*.stl`). None is needed for the first fit test. (v6.1: the wall clips are dropped: they fitted the
old heart island.)

| Piece | File | How many | What it does |
|---|---|---|---|
| Press foot, Adafruit | `helpers_jigs.stl` | 1 | Plate on four tube feet that stand on the hole corners of an ICM-20649, TMP117 or SHTC3 board, clear of parts |
| Press foot, MAX30102 | `helpers_jigs.stl` | 1 | Flat pusher for the back of the MAX30102, with a groove over its solder points |
| Slot spacer | `helpers_jigs.stl` | 1 | Tongue that holds TMP117 #1 flat while the glue sets (made for the v4 slot; the v6.1 slot is wider, so it is loose sideways) |
| Wire saddle | `helpers_saddles.stl` | 4 | Small bridge glued over a bundle just outside an opening |
