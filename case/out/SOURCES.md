# Sources: where every twin dimension comes from (v4, 17 Nov)

Each number in `params.py` carries one tag:

- **DATASHEET**: read from a maker's CAD file, drawing, datasheet or specification. The file is in `vendor/`.
- **MEASURED**: measured or reported by you on the real parts. These override everything else.
- **PHOTO**: read off one of your photos (file name given). Accuracy is about ± 0.3 mm unless stated.
- **ASSUMED**: a guess that no source can settle. All of them are listed in `MEASURE_NEXT.md`.
- **DESIGN**: a design choice.

Your photos are in `/mnt/user-data/attachments/e71ad7ae-f4d8-54ae-9f33-a806866f608a/`. File names below are shortened to their first 8 characters.

## What changed in v6 (18 Nov: the v4.x pod failed in your hands)

No new datasheet numbers. New rules and design choices, all in `params.py` (v6 block at the end):

| Number | Value | Tag | Why |
|---|---|---|---|
| `WIRE_BEND_R` | 8 mm | ASSUMED | smallest bend radius of any wire bundle (your 28AWG, 1.0 mm, stiff, joints + glue). Measure it |
| `WIRE_BEND_R_SINGLE` | 4 mm | ASSUMED | one lone wire (only the screen's blue). Measure it |
| `PAD_ROOM` | 5 mm | DESIGN | clear floor in front of every padded board edge |
| `WIRE_ROOM_H` | 4 mm | DESIGN | free height in wire rooms / above boards where wires run |
| `SCREEN_FREE_H` | 6 mm | DESIGN | free height under the screen where its cable + plug land |
| `SCREEN_WIRE_ANGLE` | 60 deg | DESIGN | the 7 screen wires leave their castellations rising, pointing inward (re-solder) |
| `XIAO_SHIFT` | 2.5 mm | DESIGN | XIAO moved in from the hand wall so its 5V row is centred under the plug; plug tunnel in the wall |
| `BAT_LEAD_ROOM` | 3 mm | DESIGN | open floor between the cell's lead end and the power pod's hand wall |
| `POD_GAP` | 8 mm | DESIGN | free neoprene between parts (= `GAP_MIN`) |
| `BTN_LEAD_LEN` | 30 mm | ASSUMED | the HELP button's two wires were never measured |
| `HOP2_ISLAND_Y` (spacing.py) | 5 mm | DESIGN | hop 2 lands on the ICM's pad row near its +Y end (v4: 1) |

## What changed in v4 (fit test and harness photos, 17 Nov 23:00)

Photos: `8dd4193b`, `d8ea4884`, `997f4a98` (the real soldered harness).

| Number | v3 | v4 | Tag | Source |
|---|---|---|---|---|
| Free wire per hop (all six) | 50 (guess) | 30 | MEASURED (approx.) | your report: "3 cm", "all hops about the same" |
| Screen cable, socket to XIAO | 50 (plan) | 30 | MEASURED | your report |
| Battery leads | 50 (plan) | 30 | MEASURED (approx.) | your report |
| Battery cradle length | 31.1 | 33.1 | MEASURED-FIT | v3 cradle "a tiny bit too short"; +2.0 (asked: at least +1.5) |
| Battery length in the twin | 30.5 | 31.6 | ASSUMED | longer than 31.1 (fit test); the photo cannot give it |
| Battery lead exit | middle of the end | one corner | PHOTO | `d8ea4884`; which corner is unknown, so relief at both |
| XIAO USB-C wall | y- side wall | hand-end wall | PHOTO-DERIVED | `8dd4193b`, `997f4a98`: the cable reaches the XIAO over its USB-C end |
| Screen cable landing | XIAO far end | 5V/GND/3V3 row at the USB-C end; blue to the D0..D6 row | PHOTO | `8dd4193b` |
| Screen offset from the XIAO axis | – | 7.0 toward the 5V/GND/3V3 row | DESIGN | so the cable folds down beside the USB-C receptacle |
| Hop 1 + battery leads leave the XIAO | sideways / under | far end (hop 1 at the battery-side corner) | PHOTO | `d8ea4884`, `997f4a98` |
| Room under the screen | – | +1.2 | MEASURED-FIT | your request: "about 1 mm or a bit more" |
| Motor cup | – | unchanged | MEASURED-FIT | "fits well" |
| Frame fit to the tray | 0.2 per side | unchanged | MEASURED-FIT | "presses on and holds" |

## What changed in v3

| Number | v2 | v3 | Tag | Source |
|---|---|---|---|---|
| MAX30102 board length | 19.0 | 18.1 | PHOTO | `db9b86ad` (ruler), `73fbbcdb` (pad pitch) |
| MAX30102 board width | 12.7 (assumed) | 13.9 | PHOTO | `73fbbcdb` (pad pitch) |
| MAX30102 hole diameter | 1.0 | 1.4 | PHOTO | `db9b86ad`, `73fbbcdb` |
| MAX30102 hole position | 1.7 / 1.5 in | 1.4 / 1.43 in, 15.24 apart | PHOTO | `73fbbcdb` |
| MAX30102 chip position | board centre (assumed) | 1.45 toward GND end, 0.6 toward pads | PHOTO | `73fbbcdb`, `6c1bd174`, `a72308c7` |
| MAX30102 chip height | 1.6 (as "parts") | 1.55 | DATASHEET | Analog Devices MAX30102 package |
| MAX30102 sensor-side parts | one block | 8 parts placed one by one | PHOTO | `73fbbcdb` |
| XIAO board thickness | 1.2 (assumed) | 1.25 | DATASHEET | Seeed STEP v15 |
| XIAO wire exit | underside | sideways from both pad rows, on top | PHOTO | `b09c09de`, `b59e1f1e` |
| XIAO side room | 0.8 (assumed) | 2.0 | PHOTO | `b09c09de` |
| XIAO top solder + wire | 1.0 (assumed) | 2.0 | PHOTO | `b09c09de` |
| DRV2605L board thickness | 1.6 (assumed) | 1.6 | PHOTO | `1791b8ab` |
| DRV2605L wire side | top (assumed) | back | PHOTO | `1791b8ab` |
| LCD socket size | 15.0 × 4.7 (scaled) | 14.75 × 5.05 | DATASHEET | Waveshare STEP |
| LCD socket position | 4.85 from centre (scaled) | 4.50 | DATASHEET | Waveshare STEP |
| LCD standoff diameter | 4.0 (assumed) | 3.8 | PHOTO | `8026e80d` (STEP says 3.5) |
| LCD back-side part height | 1.2 (assumed) | 1.2 | DATASHEET | Waveshare STEP |
| LCD plug | 11.6 wide, 3.5 out | 11.4 wide, 3.0 out | PHOTO | `8026e80d` |
| USB-C plug section | 12.35 × 6.5 (from memory) | 12.35 × 6.5 | DATASHEET | USB Type-C spec R2.0, Fig. 3-3 |
| USB-C plug length | 22 (assumed) | 35 | DATASHEET | USB Type-C spec R2.0, Fig. 3-3 |
| Button body height | 5.0 (assumed) | 3.4 | DATASHEET | Omron B3F drawing |
| Button plunger | 2.0 (assumed) | 6.0 | PHOTO | `1c7cb16f`, `b59e1f1e` |
| Button plunger diameter | 3.5 (assumed) | 3.5 | DATASHEET | Omron B3F drawing |
| Hook-up wire diameter | 1.0 (assumed) | 1.0 | PHOTO | `8026e80d` |
| Joint + glue height on a pad row | 2.0 (assumed) | 2.5 | PHOTO | `20478993`, `a3b94cbc` |
| TMP117 #1 joint height (as it is) | 2.0 (assumed, "after trimming") | 3.0 | PHOTO | `e46642bd`, `a3b94cbc` |
| TMP117 #1 sockets | planned off | off | MEASURED | your report, 17 Nov 20:25 |
| TMP117 #1 GND joints | header pad | socket tab pads at both short ends | MEASURED + DATASHEET | your report + Adafruit Eagle file |

## Adafruit ICM-20649 (#4464), TMP117 (#4821), SHTC3 (#4636)

| Source | File in `vendor/adafruit/` |
|---|---|
| https://github.com/adafruit/Adafruit-ICM20649-PCB (Eagle board) | `Adaruit_ICM20649.brd` |
| https://github.com/adafruit/Adafruit-TMP117-PCB (Eagle board) | `Adafruit_TMP117.brd` |
| https://github.com/adafruit/Adafruit-SHTC3-PCB (Eagle board) | `Adafruit_SHTC3.brd` |
| https://github.com/adafruit/Adafruit_CAD_Parts, folder `4636 SHTC3` (3-D model) | `4636_SHTC3.stl` |

- Outline 25.40 × 17.78 mm, corner radius 2.54. Four holes, 2.5 mm, on a 20.32 × 12.70 mm rectangle. Header row 2.54 mm in from one long edge.
- Board 1.57 mm thick. STEMMA QT sockets 4.95 × 6.0 × 2.96 mm (from the STL).
- TMP117 chip at the board centre, 2 × 2 × 0.8 mm. SHTC3 2 × 2 × 0.76 mm. ICM-20649 at (12.76, 8.19), 3 × 3 × 0.9 mm.
- **New in v3:** the two flat pads that hold each socket's metal tabs (Eagle `CONN3` / `CONN4`, pads `MT1` / `MT2`, net GND). They are 1.8 × 1.2 mm, centred 1.28 mm in from each short edge, at 6.09 and 11.69 mm from the header edge. Your GND wires are on these now.
- Spot check done in v3: the outline, the hole part (`MOUNTINGHOLE_2.5_PLATED`) and the chip position were read again from `Adafruit_TMP117.brd`. They match.

## SparkFun DRV2605L ROB-14538, board v20

- https://cdn.sparkfun.com/assets/2/9/d/9/3/Haptic_Motor_Driver_DRV2605L_v20_1.zip → `vendor/sparkfun/z/Haptic_Motor_Driver_DRV2605L_v20.brd`
- Outline 20.32 × 20.32 mm. Two 3.30 mm holes. 6-pad header on one edge, 2-pad motor header on the opposite edge.
- **Board thickness:** no SparkFun file states it. The Eagle file has no thickness, and SparkFun's own forum page lists several thicknesses without naming a default (https://community.sparkfun.com/t/can-you-do-xyz-thickness-copper-weight-solder-mask-color/312). So it is read from your photo `1791b8ab`: the board edge is 1.6 mm, scaled from the 2.54 mm pad pitch. Tag PHOTO.
- **Wire side:** photo `1791b8ab` shows your wires soldered on the back (the side printed "I2C ADDR 0x5A").

## Coin motor SparkFun ROB-08449

- https://cdn.sparkfun.com/datasheets/Robotics/B1034.FL45-00-015.pdf → `vendor/sparkfun/motor.pdf`
- 10 mm diameter × 3.4 mm, plus 0.15 mm adhesive. Leads AWG32, 45 ± 2 mm. Spot check done in v3: the title block reads "10 Dia × 3.4 T".

## Seeed XIAO nRF52840 (plain)

| Source (all linked from https://wiki.seeedstudio.com/XIAO_BLE/) | File |
|---|---|
| `XIAO-nRF52840-DXF.zip` | `vendor/seeed/XIAO-nRF52840-DXF.zip` |
| `Bottom-pad-positioning.zip` | `vendor/seeed/Bottom-pad-positioning.zip` |
| `seeed-studio-xiao-nrf52840-3d-model.zip` (STEP "XIAO-nRF52840 v15") | `vendor/seeed/seeed-studio-xiao-nrf52840-3d-model.zip` |
| KiCad project `...V1.1-KiCad-Project-260105.zip` (read in v2, not stored) | – |

- Outline 20.96 × 17.78 mm. 7 castellated pads per long edge at 2.54 mm pitch.
- **Board thickness 1.25 mm:** in the STEP, the board's two large flat faces are at −0.25 and +1.00 mm. Seeed publishes no thickness anywhere else (the "XIAO Series SOM" PDF gives none for this board).
- RF can 12.6 × 10.6 × 2.0 mm (STEP: top face 2.0 above the board).
- USB-C receptacle 8.94 wide × 7.35 long × 3.26 tall, tip 1.45 mm past the board edge (KiCad). The STEP shows its top 3.21 above the board. The two agree within 0.05; the larger value is used.
- Reset button and BAT pads: positions from the KiCad file (unchanged from v2).
- **Wire exit:** photos `b09c09de` and `b59e1f1e` show your wires soldered on top of the castellated pads and leaving sideways, each in a heat-shrink sleeve about 2 mm thick. Only the battery leads are underneath (`1c7cb16f`).

## Waveshare 1.69inch LCD Module

- https://files.waveshare.com/upload/4/41/1.69inch_LCD_Module_2Ddrawing.pdf → `vendor/waveshare/1.69inch_LCD_Module_2Ddrawing.pdf`
- https://files.waveshare.com/wiki/1.69inch%20LCD%20Module/1_69inch-lcd-module.stp → `vendor/waveshare/1_69inch-lcd-module.stp`

From the drawing (dimensioned): board 31.50 × 39.00, glass 30.07 × 37.43, active area 27.97 × 32.63, standoffs on 24.30 × 31.80, thicknesses 3.40 / 5.90 / 7.1.

From the STEP (read solid by solid in v3):

- Board faces at −0.24 and −1.84: the board is **1.60 mm**. Glass unit 1.76 mm. With the 0.04 mm glue line this gives the drawing's 3.40.
- Socket solid: **14.75 × 5.05 × 3.66 mm**, on the centreline, its centre **4.50 mm** from the board centre. Which end it is nearer to (the cable-tail end) and which way its mouth faces come from the drawing. Photo `8026e80d` agrees: body 12.3 mm, 15.6 mm over the tabs, body + tails 5.1 mm.
- Standoffs: 3.5 mm diameter, ending 2.5 mm below the board.
- Tallest back-side part ends 1.20 mm below the board.

Two sources disagree:

- **Standoff diameter:** STEP 3.5 mm, photo `8026e80d` 3.8 mm. The photo value is used because a larger standoff is the safer envelope, and the STEP's standoffs are plain placeholders.
- **Glass length:** drawing 37.43 ± 0.1, STEP 37.93. The drawing is used because it is a toleranced dimension.

## MAX30102 clone "RCWL-0531" (green board marked U1708-2)

No maker drawing exists. Searched and found nothing usable:

- The shop page and a second reseller (https://crcibernetica.com/max30102-pulse-rate-sensor-and-oximeter-rcwl0531) say 12.7 × 12.7 mm. That figure is copied from Maxim's MAXREFDES117 reference board. It cannot be right: seven pads at 2.54 mm pitch are already 15.24 mm wide.
- Other MAX30102 boards (21 × 16 mm, 14 × 14 mm with 5 pins) are different boards.
- No KiCad, EasyEDA, GitHub or GrabCAD model of this board was found.

So every number comes from your photos, using the 2.54 mm pad pitch or the ruler as the scale:

| Number | Value | Photo | How |
|---|---|---|---|
| Length | 18.1 mm | `db9b86ad` | ruler along the hole edge reads 18.0–18.2 |
| Length | 18.1 mm | `73fbbcdb` | 7 pads span 15.24 mm → scale → board edge to edge |
| Width | 13.9 mm | `73fbbcdb` | same scale: 13.8–14.0 |
| Pad row | along the 18.1 mm edge, 1.4 mm in | `73fbbcdb`, `6c1bd174`, `a72308c7` | labels VIN SCL SDA INT IRD RD GND |
| Holes | 1.4 mm, on the opposite long edge, 15.24 mm apart, 1.4 mm in | `73fbbcdb`, `db9b86ad` | in line with pads 1 and 7 |
| Chip | 1.45 mm toward the GND end, 0.6 mm toward the pads | three photos | readings 1.4 / 1.4 / 1.8 and 0.35 / 0.55 / 1.1 |
| Board thickness | 1.2 mm | `6c47371a` | scaled from a 1.6 mm capacitor |
| Other parts | 8 boxes in `params.MAX_PARTS` | `73fbbcdb` | ± 0.4 mm |
| Wires | on the sensor side, along the pad edge | `a72308c7` | |

- Chip package 5.6 × 3.3 × 1.55 mm: MAX30102 product data (https://www.analog.com/en/products/max30102.html, cited in `PARTS_REFERENCE.md`). The datasheet PDF could not be downloaded in this session (the server dropped the connection), so it is not in `vendor/`.
- Your earlier ruler reading was 19.0 ± 0.5. Two photos now give 18.1. The photos are used, and the seat has 0.3 mm of clearance per side.

## Battery Akyga LP601730 (AKY0384)

- https://www.akyga.com/app_products_attachments/product-cards/symbol/AKY0384/code/en → `vendor/akyga/aky0384.pdf`
- Maximum size 30.5 × 17.5 × 6.5 mm (table, page 2). The drawing on page 5 gives 30 ± 0.4, 17 ± 0.4, 6.0 ± 0.2. The maximum is used, because a cell swells with age.
- Leads: 26 AWG UL1007 (drawing items 50 and 60), 150 mm. They leave the protection-board end, one each side of the middle. The drawing is marked "not in scale", so their exact spacing is not known.

## Button (6 × 6 tactile switch from the 420-piece kit)

- https://omronfs.omron.com/en_US/ecb/products/pdf/en-b3f.pdf → `vendor/omron/en-b3f.pdf`
- The kit part is a generic copy of the Omron B3F. From the Omron drawing: body 6 × 6 mm, **3.4 mm** from the leg face to the top of the cover, plunger **3.5 mm** diameter, legs 3.5 mm long.
- Plunger length depends on which height you picked from the kit. Photos `1c7cb16f` and `b59e1f1e` show a long plunger, 5–7 mm. 6.0 is used. This one is still worth measuring.

## USB-C cable plug

- USB Type-C Cable and Connector Specification, Release 2.0, August 2019 → `vendor/usbif/USB_Type-C_Spec_R2.0_Aug2019.pdf` (from https://www.usb.org/sites/default/files/USB%20Type-C%20Spec%20R2.0%20-%20August%202019.pdf)
- **Section 3.2.1, Figure 3-3 "USB Full-Featured Type-C Plug Interface Dimensions"**, page 47: plug body **12.35 MAX** wide (section A-A) and **6.5 MAX** thick (section C-C). Page 46: body reference length (35), metal shell exposed at least 6.51.
- **Section 3.10.3, Figure 3-80**, page 136: keep at least 0.05 mm between the product surface and the plug body so the plug seats fully.
- Your own cable looks about 12.5–13 mm wide in photo `b59e1f1e` (rough reading). The opening is 13.55 × 7.7 mm.

## Wire

- Photo `8026e80d`: the blue hook-up wire is printed "…28AWG". Scaled from the socket's 1.25 mm pin pitch it is 1.0 mm thick, and so are the screen cable's wires.
- Four of them make a bundle 2.4 mm across when packed tight. 3.0 mm is used for a loosely gathered bundle.

## Measured or reported by you

- Wrist circumference 162 mm.
- Printer clearance 0.3 mm. Locating pins: hole − 0.4 mm, at most 2 mm tall, 0.6 mm root cone, solid. A 0.2 mm slot fits by hand.
- Motor lead notch 3.0 × 3.3 mm.
- MAX30102 sensor-side parts 1.5–1.7 mm tall.
- 17 Nov 20:25: TMP117 #1 has no sockets any more, and its GND wires are on the socket tab pads.

## Looked for and not found

- A drawing of the RCWL-0531 board (see above).
- SparkFun's board thickness in any SparkFun file.
- The JST / Molex drawing of the screen's 8-pin socket: jst-mfg.com refused the download. The STEP and the photo are used instead.
- A sourced figure for the wrist's width-to-thickness ratio. It stays ASSUMED.

## v6.1: measured wire lengths (you, pad to pad, free length)

| Run | Measured (mm) | In `params.py` |
|---|---|---|
| Hop 1 XIAO -> DRV2605L | 50-60 | `HOP1_LEN` |
| Hop 2 DRV2605L -> ICM-20649 | shortest 45, rest ~60 | `HOP2_LEN` |
| Battery leads | 45 | `BAT_LEN_M` |
| HELP button pair | 34.5 | `BTN_LEN_M` |
| Screen cable | shortest 25, normal 45-50 | `LCD_LEN_M` |
| Hop 3 ICM -> MAX30102 | 51 | `HOP3_LEN` |
| Hop 4 MAX30102 -> TMP117 #1 | 50 | `HOP4_LEN` |
| Hop 5 TMP117 #1 -> #2 | shortest 20, normal 30 | `HOP5_LEN` |
| Hop 6 TMP117 #2 -> SHTC3 | 60 | `HOP6_LEN` |

Still guesses: `WIRE_BEND_R` 8, `WIRE_BEND_R_SINGLE` 4, the TMP117 #1 GND tail lengths (~15), the screen pin order.

## v7.0 verification pass (19 Nov 2026): every board against the maker's mechanical data

Rule used: the owner's measurement wins, then the maker's data. "file" = the maker's CAD file stored in `vendor/` and read again today.

| Board | Dimension | Model value | Verified value | Source | Result |
|---|---|---|---|---|---|
| Adafruit TMP117 #4821 | outline | 25.40 x 17.78, corner R 2.54 | 25.40 x 17.78 (page: 25.5 x 17.7 x 4.6) | Eagle `Adafruit_TMP117.brd` layer 20; adafruit.com/product/4821 | OK |
| Adafruit TMP117 #4821 | mounting holes | 4 x dia 2.5 at (2.54 / 22.86, 2.54 / 15.24) = 20.32 x 12.70 | same | Eagle: 4 x `MOUNTINGHOLE_2.5_PLATED` | OK for #1 |
| **TMP117 #2 (owner's board)** | hole centre to centre, long way | was 20.32 | **20.0 (owner, ruler, 19 Nov)** | owner's measurement | **CHANGED: pins 20.0 apart**; 1.8 pins in 2.5 holes accept 19.3-20.7, so a 20.32 board also fits |
| Adafruit TMP117 #4821 | header row | 6 pads, pitch 2.54, centred x 12.7, y 2.54 | same (JP1 `1X06_ROUND_70` at 12.7, 2.54) | Eagle | OK |
| Adafruit TMP117 #4821 | chip | 2 x 2 x 0.8 at (12.7, 8.89) | X1 WSON-6 at (12.7, 8.89); height 0.8 max | Eagle; TI WSON drawing (not re-fetched) | OK |
| Adafruit TMP117 #4821 | STEMMA QT sockets | body x 0.19-5.14, y 5.89-11.89, h 2.96 | CONN4 at x 2.667, CONN3 at x 22.733, y 8.89 | Eagle (position); body size from the SHTC3 STL | OK (body size taken from the SHTC3 model: same JST SH part) |
| Adafruit SHTC3 #4636 | outline / holes | 25.40 x 17.78; 20.32 x 12.70, dia 2.5 | same | Eagle `Adafruit_SHTC3.brd` | OK |
| Adafruit SHTC3 #4636 | header row / chip | 5 pads at (12.7, 2.54); chip (12.7, 8.89) | JP2 `1X05_ROUND_70` at (12.7, 2.54); X1 at (12.7, 8.89) | Eagle | OK |
| Adafruit ICM-20649 #4464 | outline / holes | 25.40 x 17.78; 20.32 x 12.70, dia 2.5 | same | Eagle `Adaruit_ICM20649.brd` | OK |
| Adafruit ICM-20649 #4464 | header rows | one 6-pad row at y 2.54 | JP3 at (12.7, 2.54) AND a second row JP2 at (12.7, 15.24) | Eagle | model has only the wired row; the second row is bare holes between the back bosses (first pad 1.1 mm from a boss) - nothing to change |
| Adafruit ICM-20649 #4464 | STEMMA QT sockets | as TMP117 (x 0.19-5.14) | CONN4 at x 2.54, CONN3 at x 22.86 (0.13 further out than on the TMP117 / SHTC3) | Eagle | 0.13 mm off, inside the 0.3 mm gap kept round it; not changed |
| Seeed XIAO nRF52840 (Sense) | outline | 20.96 x 17.78 | "21 x 17.8 mm"; the Sense DXF and the plain DXF have identical extents | wiki.seeedstudio.com/XIAO_BLE; `XIAO-nRF52840-Sense-DXF.zip` fetched today vs `vendor/seeed/XIAO-nRF52840-DXF.zip` | OK |
| Seeed XIAO nRF52840 (Sense) | castellated pads | 7 per long edge, pitch 2.54 | same | DXF / KiCad (read in v2) | OK (not re-read today) |
| Seeed XIAO nRF52840 (Sense) | board thickness, USB-C, RF can, reset | 1.25; 8.94 x 7.35 x 3.26, tip 1.45 past the edge; 12.6 x 10.6 x 2.0; (8.57, 5.71) | as stored (STEP v15 / KiCad) | `vendor/seeed/` (not re-fetched today) | OK as stored |
| Seeed XIAO nRF52840 **Sense** | microphone + IMU on top | not modelled | - | - | **UNVERIFIED**: the twin is the plain board. They are on the top side, where 6 mm is free; no seat touches them |
| SparkFun DRV2605L ROB-14538 | outline | 20.32 x 20.32 | same | Eagle `Haptic_Motor_Driver_DRV2605L_v20.brd` layer 20 | OK |
| SparkFun DRV2605L ROB-14538 | mounting holes | 2 x dia 3.3 at (2.54, 17.78), (17.78, 17.78) = 15.24 apart | STAND-OFF at those points, drill 3.302 | Eagle | OK |
| SparkFun DRV2605L ROB-14538 | pad rows | JP1 6 pads at x 1.27 from y 1.27; JP2 at (19.05, 8.89 / 6.35) | JP1 `1X06` at (1.27, 1.27) R90; JP2 `1X02` at (19.05, 8.89) R270 | Eagle | OK |
| SparkFun DRV2605L ROB-14538 | board thickness | 1.6 | not published | photo | UNVERIFIED (as before) |
| Waveshare 1.69in LCD Module | PCB / active area | 31.5 x 39.0; 27.97 x 32.63 | 31.50 x 39.00; 27.972 x 32.634 | waveshare.com/1.69inch-lcd-module.htm (today) | OK |
| Waveshare 1.69in LCD Module | standoffs, socket, heights | 24.30 x 31.80; socket 14.75 x 5.05 at 4.50; 3.40 / 5.90 / 7.1 | as stored | `vendor/waveshare/` 2D drawing + STEP (the wiki page did not load today) | OK as stored |
| MAX30102 clone "RCWL-0531" | outline, holes, chip position | 18.1 x 13.9; holes dia 1.4, 15.24 apart; chip 1.45 / 0.6 off centre | no maker drawing exists | scaled from the owner's photos | **UNVERIFIED** (pocket 0.9 per side, loose metal pins, window +0.5 per side) |
| MAX30102 chip | package | 5.6 x 3.3 x 1.55 | same | Analog Devices (as stored) | OK as stored |
| LiPo Akyga LP601730 | max size | 30.5 x 17.5 x 6.5 | as stored | `vendor/akyga/aky0384.pdf` | OK as stored; cradle is +2.0 long after the owner's fit |
| Tactile switch | body / plunger | 5.0 x 5.0 x 3.0; dia 2.5; 6.5 total | owner, +/- 0.2, no calipers | owner | MEASURED |
| Coin motor ROB-08449 | size | dia 10 x 3.4 | as stored | `vendor/sparkfun/motor.pdf` | OK as stored |
