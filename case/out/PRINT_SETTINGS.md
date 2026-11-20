# Print settings: Creality K1C, PETG, 0.4 mm nozzle (v3 profile, v7.0 FINAL parts)

Run `python3 build.py` first. It rebuilds every STL and stops if the digital twin finds a collision.

## Which files

| Folder | What | Supports | Skin side |
|---|---|---|---|
| `out/stl_flat/` | flat undersides, like a watch back | **none** | smooth (build-plate face) |
| `out/stl/` | undersides curved to your wrist | build plate only | rough (printed on supports) |

**Print the flat set first.** It is the fit test and the nicer surface on skin. See `RIGIDITY.md` for the reasons. The frame is the same in both.

`out/stl/helpers_*.stl` are small helper pieces for gluing. They are for later, not for the first print.

## Bed: smooth PEI plate + glue stick

- **Put a thin, even layer of glue stick on the smooth PEI plate before every PETG print.**
- For PETG the glue is a **release layer**, not an adhesive. PETG can bond to bare smooth PEI so hard that it tears pieces out of the plate when you remove the part.
- Wipe the plate with a damp cloth between prints and put a fresh layer on. Do not use IPA on the glue layer.
- Let the bed cool to about 35 °C before you take parts off. Flex the plate; do not pry with a blade.

## Base profile (all parts)

Start from Creality Print's "Generic PETG" profile for the K1C with the 0.4 mm nozzle, then change these:

| Setting | Value | Why |
|---|---|---|
| Nozzle temp | 240 °C (first layer 245 °C) | PETG range is 230–250 °C |
| Bed temp | 75 °C | smooth PEI **with glue stick** (see above) |
| Layer height | 0.2 mm (first layer 0.2 mm) | The model's heights are multiples of 0.1–0.2 |
| Walls (perimeters) | **4** | Every 1.5 mm wall, every 1.2 mm rib and every locating pin comes out solid. The coupon pins snapped when they were hollow |
| Top / bottom layers | 6 / 6 | Every floor is 1.2 mm (6 layers) in v7.0: solid all the way through |
| Infill | 25 %, gyroid | |
| Outer wall speed | 80 mm/s | PETG strings if you go faster |
| Inner wall / infill speed | 150 / 200 mm/s | |
| Part cooling fan | 40 % (100 % on bridges) | Clean bridges, layers still stick |
| Retraction | 0.8 mm at 40 mm/s | Less stringing between the small posts |
| Seam | Aligned, on the rear | |
| "Detect thin walls" | ON | harmless; v7.0 has nothing under 1.2 mm except the two skin seats |
| Z-hop | 0.2 mm | Keeps the nozzle from knocking the pins over |

Printer side, as you already do for PETG: **Stable mode / 50 % speed, lid closed.** The speeds in the table are the slicer's values; the 50 % setting scales them down.

## Per part: flat set (`out/stl_flat/`)

The STL files are already turned the right way up for printing.

| Part | Size on the bed (mm) | On the bed | Supports | Brim | PETG |
|---|---|---|---|---|---|
| `brain_pod.stl` (tray) | 35.1 × 67.6 × 12.9 | skin side down | none | no | ~7 g |
| `brain_frame.stl` (cover) | 35.1 × 60.6 × 10.1 | window face down (as exported) | none | no | ~4.5 g |
| `power_pod.stl` (tray) | 43.6 × 62.9 × 8.8 | skin side down | none | no | ~6.5 g |
| `power_lid.stl` | 40.6 × 55.9 × 3.7 | top face down (as exported) | none | no | ~5.5 g |
| `island_skin.stl` | 89.8 × 48.9 × 12.1 | skin side down | none | no | ~10 g |
| `island_shelf.stl` | 26.4 × 19.5 × 4.2 | shelf plate down (as exported) | none | no | ~0.8 g |
| `island_air.stl` | - | **do not print** (not used since v6.8) | - | - | - |

### Plates (v7.0)

All six fit on one K1C plate (220 × 220), but print **two plates** so one failure does not cost everything and the small parts string less:

| Plate | Parts | PETG | Time (estimate, Stable mode) |
|---|---|---|---|
| 1 (first: it has the fixes that matter) | `island_skin` + `island_shelf` | ~11 g | ~1 h 15 min |
| 2 | `brain_pod` + `brain_frame` + `power_pod` + `power_lid` | ~23 g | ~2 h 15 min |

Total about **3.5 h** (roughly 3-4 h; 26.5 cm3, ~34 g). This is an estimate from the volume, not a slicer result: the slicer's
number is the real one. Start plate 1, dry fit the sensors on it (ASSEMBLY.md lines 6-11) while plate 2 prints.

## Per part: curved set (`out/stl/`)

| Part | Size on the bed (mm) | On the bed | Supports | Brim | PETG |
|---|---|---|---|---|---|
| `brain_pod.stl` (tray) | 35.1 × 55.2 × 23.9 | skin side down | **build plate only**, tree | 5 mm | ~10 g |
| `brain_frame.stl` | 34.9 × 48.0 × 6.9 | window face down | none | no | ~2.5 g |
| `power_pod.stl` (tray) | 43.6 × 62.9 × 24.5 | skin side down | **build plate only**, tree | 5 mm | ~14 g |
| `power_lid.stl` | 40.4 × 55.7 × 6.6 | top face down | none | no | ~4 g |
| `island_skin.stl` | 88.4 × 48.9 × 19.7 | skin side down | **build plate only**, tree | 5 mm | ~14.5 g |
| `island_shelf.stl` (v6.8) | 26.9 × 20.3 × 4.0 | shelf plate down (same file shape as the flat set) | none | no | ~0.7 g |
| `island_air.stl` | not used since v6.8 | - | - | - | - |

For the supported undersides, these give the least rough surface:

| Setting | Value |
|---|---|
| Support top Z distance | 0.2 mm |
| Support interface layers | 3, interface spacing 0.2 mm |
| Support / object XY distance | 0.4 mm |

Then wet-sand the skin side (240 grit, then 400).

## Helper pieces (later)

| File | Pieces | On the bed | Supports |
|---|---|---|---|
| `helpers_jigs.stl` | 2 press feet + 1 slot spacer | as exported | none |
| `helpers_saddles.stl` | 4 wire saddles | as exported | none |

## Bridges to watch

These print over air between two walls. Keep the fan at 100 % on bridges.

| Part | Bridge | Span |
|---|---|---|
| Skin island | the plate over the strap slot (solid 1.2 mm in v7.0, 45° haunches at both ends; TMP117 #2's blocks stand on it) | 26.8 mm |
| Skin island | the two side walls over the GND-tail channels (wall on one end, pillar on the other) | 9.3 mm |
| Brain pod | the top of the USB-C tunnel in the hand wall | 14.6 mm |
| Power lid | the finger dish (0.5 mm above the bed, round the square hole) | 9 mm |
| All parts | the tops of the big wire openings: none, they are open from the top (the frame / lid bridges them) | - |
| Air island | the two guard bars on top | 23 mm |
| Air island | the tops of the side openings | 21–23 mm |

## Check after printing

- The MAX30102 window is clean. On the curved set, also its raised ring: trim support nubs with a knife, but do not cut the ring.
- The openings under TMP117 #1 are open all the way through, and the two GND-tail channels at its short ends are clear.
- Every locating pin is there and upright (v7.0: 2 on the ICM bosses, 2 on TMP117 #2's blocks, 2 on the shelf, 2 for the DRV). Push boards on straight down, never sideways.
- The plate over the strap slot has no sagging strings underneath (cut them off: the strap tongue must slide in).
- The two keys on the back ledge are whole, and the shelf's two holes are open.
- The strap slot is open from the back wall in. A 3 mm neoprene tongue slides in over TMP117 #1's place.
- The skin island's bay, its two tongue walls and every wire opening are free of strings. A sharp string can cut wire insulation.
- A USB-C cable goes fully into the XIAO through the hand-wall tunnel, with the frame on.
- The power lid's square hole and the finger dish are clean.
- The frame and the lid push onto their trays by hand. If it is too tight, scrape the tray's top edge lightly; do not force it.
