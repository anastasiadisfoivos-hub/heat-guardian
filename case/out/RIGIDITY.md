# Rigidity and print-quality review (v3)

> **v6.1:** the heart island is replaced by the skin island (`island_skin.stl`). The heart-island rows below are history. The skin
> island: 1.8 mm plate over the strap slot (as before), 0.8 mm bay floor (the wires lie on it), 0.6 mm floor under TMP117 #1, 0.4 mm
> under the MAX30102's parts, 2.5 mm tongue walls 1.2 mm thick, big top-open wire openings bridged by nothing (the neoprene and the
> walls either side carry the load). Handle it by its back wall and end walls, not by the bay floor. The brain pod's elbow opening is now
> open to the top too (no lintel): the frame bridges it.

> **v6 note:** the rows below about the 'Pod' were written for the v4 single pod. The v6 brain and power pods use the same wall (1.5),
> floor (1.0, 0.8 under the cell, 0.6 under the motor), rib (1.2) and pin rules. New in v6: the power lid's switch pocket walls are
> 0.8 mm (they only locate: the press goes into the printed bar under the switch and the floor), and the brain pod's elbow wall has a
> 30 mm wide opening below a 4 mm lintel that carries the screen's edge.

Every printed part was checked feature by feature, and `thin.py` probed the finished STL files for thin material (it shoots a ray into the part from 60,000 points on its surface and measures the distance to the other side).

Rules used: outer walls ≥ 1.5 mm, ribs ≥ 0.8 mm (2 perimeters), load-carrying ribs ≥ 1.2 mm, floors ≥ 1.0 mm where the design allows it, no upright post thinner than 3 mm.

## What was weak, and what changed

| Part | Feature | v2 | v3 | Why |
|---|---|---|---|---|
| Pod | Floor under the battery | 0.4 mm | 0.8 mm | Two layers under a Li-Po was too thin. With the curved underside it is about 1 mm or more almost everywhere. Costs 0.4 mm of pod height. |
| Pod | Floor under the XIAO | 0.6 mm | 1.0 mm | Free: the battery stack sets the height. |
| Pod | XIAO end stops (take the push of the USB plug) | 0.8 mm thick | 1.6 mm | A 20 N plug push bends them across the layer lines: about 50 MPa at 0.8 mm (PETG layers part at 25–35), about 12 MPa at 1.6 mm. |
| Pod | Button backstop | 1.4 mm thick | 2.4 mm + a sloped gusset | It takes every button press, also across the layers. |
| Pod | Rib between trunk and battery, rib at the battery's lead end | 0.8 mm | 1.2 mm | Free-standing, 32 mm long, and the trunk's snap lips sit on it. |
| Pod | USB-C slot in the wall | square bottom corners | R 1.0 mm corners | Sharp inside corners start cracks when the plug is wiggled. |
| Frame | Cut-out for the USB plug | square top corners | R 1.5 mm corners | Same reason; this is where a press-fitted ring would split. |
| Frame | Fit on the tray | 0.15 mm per side | 0.20 mm per side | 0.2 is the value your coupon showed "fits by hand". 0.15 risked splitting the 1.2 mm skirt. |
| Heart island | Plate over the strap slot | 1.3 mm, 0.6 mm left under TMP117 #2's solder pocket | 1.8 mm, 1.1 mm left | 0.6 mm was three sagging bridge layers over an 18 mm span. Costs 0.5 mm of height on that stack (still lower than the pod). |
| Heart island | MAX30102 seat | rim on three sides | two corner pads + one ledge | The real board has parts right up to its edges; the old rim would have lifted it 1.6 mm. |
| Heart island | MAX30102 rim height | 0.5 mm above the board | 0.2 mm below the board's back | It stood under the ICM's solder points, and wires can now leave over it. |
| Heart island | ICM-20649 mounts | 3 pins + 1 rest | 2 pins + 2 rests | A full post no longer fits beside the wider MAX30102. Two pins still locate the board fully. |
| Heart island | TMP117 #1 side stop | one, mid-edge | two, at the corners | The old one stood where the new GND wires leave. |
| All | Strain-relief posts | 2.0 mm | 3.0 mm | A 2 mm upright post snaps along a layer line when you pull a wire round it. |
| Pod, heart island | Stitch flanges | 1.2 mm | 1.6 mm | Stitch holes tear out less easily. |

## Checked and left as it is

- **Outer walls** 1.5 mm, corner radius 2 mm: fine.
- **Locating pins** 2.1 mm with a 0.6 mm root cone, 2 mm tall: this is the size your coupon proved. Keep 4 walls so they print solid.
- **Snap lips** in the cable grooves are 0.5–0.6 mm on purpose: they have to flex.
- **Motor floor** 0.6 mm at the centreline: on purpose, so the buzz reaches the wrist. The curved underside adds 1.4 mm there anyway.
- **Stitch flanges and strap load:** the flanges lie flat on the bed, so the strap pulls along the layers, not across them. The strap itself passes through the heart island and presses TMP117 #1 down; nothing printed is pulled apart by it.
- **Air island pillars** are L-shaped corners 3 mm wide, 9 mm tall: stiff enough for a part that carries only one board.

## Thin spots that remain, and why

| Where | Thickness | Why it stays |
|---|---|---|
| Heart island, floor under the MAX30102's parts | 0.4 mm (2 layers) | The 1.6 mm capacitors need this room. A thicker floor would push the optical chip further from the skin (now 0.55 mm). The curved underside thickens it away from the centreline. |
| Heart island, floor under TMP117 #1 | 0.6 mm (3 layers) | The chip is 0.8 mm tall and must stand 0.2 mm proud. |
| Heart island, lane floor where the MAX30102 → TMP117 #1 wires cross | 0.4 mm | Those wires must stay below the board faces. The two side walls carry the load there. |
| Heart island, stitch flange | notched 13 mm on each side | Opening for the GND wires at TMP117 #1's short ends. Five holes remain ahead of each notch and one or two behind. |

Handle the heart island by its side walls, not by its floor.

## Supports and the surface that touches the skin

- **Curved set (`out/stl/`):** the undersides follow the wrist, so they hang over the bed and print on supports. A supported PETG surface is rough. It would need sanding (240 then 400 grit, wet) before it sits on skin.
- **Flat set (`out/stl_flat/`):** every underside is flat, like a watch back. No supports at all, and the skin side is the smooth face from the build plate. The heart island's raised light ring is left out here (the flat face is the seal) so the part lies flat on the bed.
- **Recommendation:** print the flat set first. It is the fit test and it is the better skin surface. Print the curved set only if the flat parts rock on your wrist. Both sets pass the collision check.
- The frame prints window-face down in both sets: no supports, and the visible face is smooth.

## Overhangs and bridges (both sets)

| Part | Feature | Span | Note |
|---|---|---|---|
| Heart island | divider over TMP117 #1's pad edge | 18 mm | bridges between its two legs |
| Heart island | plate over the strap slot | 18 mm | now 1.8 mm thick |
| Heart island | lane wall windows | 3.4 mm | short bridges |
| Air island | two guard bars, tops of the side openings | 21–23 mm | fan at 100 % on bridges |
| Pod | lip above the USB plug recess | 0.45 mm deep | prints without help |

Pin tips are cones and the snap lips are chamfered underneath, so nothing else needs support.

## Re-run the check

```
python3 build.py
python3 thin.py 0.79
```
