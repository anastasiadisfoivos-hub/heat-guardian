"""Heat Guardian - Stage 1 sensor structure, v4 (pod re-laid round the REAL soldered harness, 17 Nov 23:00 fit test). EVERY dimension lives here.

Tags:  DATASHEET = from a maker drawing / CAD / datasheet -> see out/SOURCES.md (file kept in vendor/)
       MEASURED  = measured on the real hardware by the user (overrides any datasheet)
       PHOTO     = read off the user's photos (ruler in frame or scaled from a known part)
       ASSUMED   = a guess -> see out/MEASURE_NEXT.md, measure and update here
       DESIGN    = a design choice (change freely)
After editing, run:  python3 build.py
Axes on the wrist: X = along the forearm (hand -> elbow), Y = across the wrist,
Z = away from the skin (skin = Z 0 on each part's centreline). Parts are modelled skin-side down.
"""
import math
import os

# ---------------------------------------------------------------- printer / process
NOZZLE = 0.4            # DESIGN   K1C stock nozzle
LAYER = 0.2             # DESIGN
CLEAR = 0.3             # MEASURED coupon: 0.2 slot fits by hand; +0.1 because a 4-sided pocket grips tighter
PIN_UNDERSIZE = 0.4     # MEASURED coupon: pin dia = hole dia - 0.4
PIN_MAX_H = 2.0         # MEASURED coupon: taller pins snapped -> max 2 mm above the seat
PIN_ROOT = 0.6          # MEASURED coupon: >= 0.6 mm cone at the pin root, printed solid
WALL = 1.5              # DESIGN   outer wall
MIN_FEAT = 0.8          # DESIGN   thinnest printed rib/wall (2 perimeters)
RIB_T = 1.2             # DESIGN   free-standing ribs that carry load (3 perimeters) - v3 rigidity review
FLOOR = 1.0             # DESIGN   general floor under boards
POCKET_FLOOR_MIN = 0.4  # DESIGN   thinnest blind floor (2 layers)
CORNER_R = 2.0          # DESIGN   outer corner radius
GAP = 0.3               # DESIGN   smallest air gap kept between two things that must not touch (twin check)

# ---------------------------------------------------------------- wrist
WRIST_CIRC = 162.0      # MEASURED (user, where the band sits)
WRIST_ASPECT = 1.35     # ASSUMED  wrist width / wrist thickness (oval cross-section)


def _ellipse_axes(circ, aspect):
    """Half-axes (a = half width, b = half thickness) of an oval with this circumference."""
    b = circ / (2 * math.pi)
    for _ in range(60):
        a = aspect * b
        c = math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))
        b *= circ / c
    return aspect * b, b


WRIST_A, WRIST_B = _ellipse_axes(WRIST_CIRC, WRIST_ASPECT)
SKIN_R_TOP = WRIST_A ** 2 / WRIST_B     # curvature radius on top of the wrist (derived)
SKIN_R_SIDE = WRIST_B ** 2 / WRIST_A    # curvature radius on the side (derived)


def skin_radius_at(arc):
    """Curvature radius of the wrist oval at `arc` mm round the wrist from the top centre."""
    t, s, dt = 0.0, 0.0, 1e-3
    while s < arc and t < math.pi / 2:
        s += math.hypot(WRIST_A * math.cos(t), WRIST_B * math.sin(t)) * dt
        t += dt
    return (WRIST_A ** 2 * math.cos(t) ** 2 + WRIST_B ** 2 * math.sin(t) ** 2) ** 1.5 / (WRIST_A * WRIST_B)
SKIN_CURVE = os.environ.get("HG_FLAT") != "1"   # DESIGN   True = undersides follow the wrist (need supports, rougher on the skin).
                        #          False = FLAT BOTTOMS like a watch back: no supports, smooth PEI finish on the skin.
                        #          build.py always writes both: out/stl/ (curved) and out/stl_flat/ (flat)

# ---------------------------------------------------------------- wires (the I2C daisy chain is already cut + soldered)
BUNDLE_D = 3.0          # PHOTO    4 x 1.0 mm wires: 2.4 mm packed tight, 3.0 mm loosely gathered (derived from WIRE_D)
WIRE_D = 1.0            # PHOTO    8026e80d: hook-up wire printed "28AWG", 1.0 mm outer dia (scaled from the 1.25 mm socket pitch)
BLOB_H = 2.5            # PHOTO    20478993 / a3b94cbc: glue + joints stand 1.7-3 mm above a pad row (loose wire loops above that are not modelled)
BLOB_STRIP = 4.6        # PHOTO    glue-blob strip width, measured in from the pad edge of a board
BLOB_OVER = 1.0         # PHOTO    glue squeezes this far out past the board edge
# hop = one 4-wire link of the chain.  v4: you measured ~30 mm of free wire per hop (17 Nov 23:00: "3 cm", "all hops about
# the same").  "Free" = from where the wire leaves the hot glue at one board to where it reaches the next board.
HOP_LEN_XIAO_DRV = 30.0  # MEASURED (approx.)
HOP_LEN_DRV_ICM = 30.0   # MEASURED (approx.)  (crosses the pod -> heart-island gap)
HOP_LEN_ICM_MAX = 30.0   # MEASURED (approx.)
HOP_LEN_MAX_TMP1 = 30.0  # MEASURED (approx.)
HOP_LEN_TMP1_TMP2 = 30.0 # MEASURED (approx.)
HOP_LEN_TMP2_SHT = 30.0  # MEASURED (approx.)  (crosses the heart-island -> air-island gap)
HOP_SLACK = 5.0         # DESIGN   spare length left in a gap-crossing hop for wrist flex
GAP_MIN = 8.0           # DESIGN   smallest gap between two parts (neoprene hinge + strain posts)
GAP_AIR_MIN = 8.0       # DESIGN   heart island -> air island (v3: 10; v4 = GAP_MIN so the 30 mm hop reaches)
GAP_AIR_MAX = 12.0      # DESIGN   the air island never sits further than this from the heart island
                        #          (spare wire is stowed in the cavity under the SHTC3)
# The air island sits BESIDE the heart island, round the outer side of the forearm (v1 had it in line, 56 mm longer).

# ---------------------------------------------------------------- curved cable guides (user's own idea, kept from v1)
CABLE_BEND_R = 4.0      # DESIGN   min bend radius of every guide centreline (>= 4)
CABLE_CH_W = 3.5        # DESIGN   groove width (4-wire bundle)
CABLE_CH_D = 2.5        # DESIGN   groove depth
CABLE_WALL = 0.8        # DESIGN   groove side walls
CABLE_LIP = 0.5         # DESIGN   snap-lip overhang into the groove (wires press past it)
CABLE_LIP_LEN = 1.6     # DESIGN
CABLE_LIP_PITCH = 8.0   # DESIGN   one lip every 8 mm, alternating sides
EXIT_FLARE = 1.5        # DESIGN   exit opening widens by this per side toward the outside
EXIT_FILLET_R = 1.2     # DESIGN   fillet on every exit edge (protects the insulation)
EXIT_COLLAR = 1.6       # DESIGN   local wall thickening at each exit
TIE_POST_D = 3.0        # DESIGN   strain-relief post dia (v2: 2.0 - a 2 mm upright post snaps along a layer line)
WIRE_CH_W, WIRE_CH_D = 3.5, 2.5   # DESIGN (coupon)

# ---------------------------------------------------------------- strap attachment
STRAP_SLOT_W = 3.4      # DESIGN   slot height for the 3 mm neoprene strap
FLANGE_W = 5.0          # DESIGN   glue/stitch flange width
FLANGE_T = 1.6          # DESIGN   8 layers (v2: 1.2) - stitch holes tear out less easily
STITCH_HOLE_D = 1.2     # DESIGN
NEOPRENE_T = 3.0        # MEASURED-PLAN  strap thickness = insulation between TMP117 #1 and #2 (user's Nov 16 plan)

# ---------------------------------------------------------------- Adafruit STEMMA QT breakouts (ICM-20649 #4464, TMP117 #4821, SHTC3 #4636)
# local board frame = the Eagle .brd frame: x 0..25.4 (long edge), y 0..17.78, z 0 = PCB bottom, parts on +z
PCB_T = 1.6             # DATASHEET  Adafruit 4636 STL: PCB 1.57 (Adafruit standard 1.6)
ADA_L, ADA_W = 25.4, 17.78          # DATASHEET  Eagle outline (all three boards)
TMP_L, TMP_W = 25.4, 17.78          # DATASHEET  Eagle outline (product page says 25.5 x 17.7)
ADA_CORNER_R = 2.54                 # DATASHEET  Eagle outline arcs
ADA_HOLES = [(2.54, 2.54), (22.86, 2.54), (2.54, 15.24), (22.86, 15.24)]   # DATASHEET  Eagle
ADA_HOLE_DX, ADA_HOLE_DY = 20.32, 12.7   # DATASHEET
ADA_HOLE_D = 2.5                    # DATASHEET  Eagle MOUNTINGHOLE_2.5
ADA_PAD_Y = 2.54                    # DATASHEET  header row centre, in from the long edge y = 0
ADA_PAD_X0, ADA_PAD_PITCH = 6.35, 2.54   # DATASHEET  first pad (6-pin rows), pitch
STEMMA_X = (0.19, 5.14)             # DATASHEET  4636 STL: socket body x-range at the x = 0 end (mirrored at the other end)
STEMMA_Y = (5.89, 11.89)            # DATASHEET  4636 STL
STEMMA_H = 2.96                     # DATASHEET  4636 STL (JST SM04B-SRSS-TB 2.95)
ADA_PARTS_H = 1.0                   # DATASHEET  4636 STL: tallest small part (0805 cap) above the PCB
ADA_PARTS_BOX = (5.0, 4.4, 20.4, 14.2)   # DATASHEET  Eagle: x0,y0,x1,y1 holding every small part between the sockets
TMP_CHIP_XY = (12.7, 8.89)          # DATASHEET  Eagle X1
TMP_CHIP = 2.0                      # DATASHEET  WSON 2 x 2
TMP_CHIP_H = 0.8                    # DATASHEET  TI WSON max 0.8
SHT_CHIP_XY = (12.7, 8.89)          # DATASHEET  Eagle X1
SHT_CHIP = 2.0                      # DATASHEET
SHT_CHIP_H = 0.76                   # DATASHEET  4636 STL
ICM_CHIP_XY = (12.76, 8.19)         # DATASHEET  Eagle U$7
ICM_CHIP, ICM_CHIP_H = 3.0, 0.9     # DATASHEET  QFN 3 x 3 x 0.9
ADA_WIRE_SIDE = "top"               # PHOTO    wires + glue sit on the COMPONENT side of every Adafruit board
TMP1_SOCKETS_REMOVED = True         # MEASURED you, 17 Nov 20:25: both STEMMA sockets are now off TMP117 #1 (skin one)
TMP1_GND_AT_TABS = True             # MEASURED you, 17 Nov 20:25: the header GND pad ripped off; GND is now soldered to the flat pads of the
                                    #          removed sockets' metal tabs -> wires also leave BOTH SHORT ENDS of TMP117 #1
TMP_TAB_PADS = [(1.28, 6.09), (1.28, 11.69)]   # DATASHEET  Eagle CONN4 MT2 / MT1 (net GND), 1.8 x 1.2 pads; mirrored at the other end (CONN3)
TMP1_TAB_BLOB_H = 2.0               # ASSUMED  height of those new joints on the chip side (no photo yet)
TMP1_WIRE_SIDE = "chip"             # PHOTO    "chip" = as soldered today (joints on the chip side, toward the skin)
                                    #          "back" = after re-soldering TMP117 #1 from the back (closes the floor slot)
TMP1_BLOB_H = 3.0                   # PHOTO    e46642bd / a3b94cbc: TMP117 #1 chip-side joints AS THEY ARE TODAY (a flat tin rests on them and tilts)
TMP_CHIP_PROUD = 0.2                # DESIGN   TMP117 #1 chip stands this far past the skin plane (it must touch)
TMP_WIN_MARGIN = 0.8                # DESIGN   skin window = chip + this per side
SHTC3_OPEN = 4.0                    # DESIGN   clear area over the SHTC3 chip (never cover)
AIR_STANDOFF = 6.0                  # DESIGN   SHTC3 board bottom above the skin (>= 5)

# ---------------------------------------------------------------- SparkFun DRV2605L ROB-14538 v20 (local = Eagle frame, 20.32 square)
DRV_S = 20.32                       # DATASHEET  Eagle outline
DRV_PCB_T = 1.6                     # PHOTO      1791b8ab: board edge 1.6 (scaled from the 2.54 mm pad pitch); no SparkFun file states it
DRV_HOLES = [(2.54, 17.78), (17.78, 17.78)]  # DATASHEET  Eagle
DRV_HOLE_D = 3.3                    # DATASHEET  Eagle 3.302
DRV_JP1 = [(1.27, 1.27 + 2.54 * i) for i in range(6)]   # DATASHEET  GND VCC SDA SCL IN EN (6 pads, x = 1.27)
DRV_JP2 = [(19.05, 8.89), (19.05, 6.35)]                # DATASHEET  motor O-, O+
DRV_PARTS_BOX = (6.5, 5.5, 15.2, 15.6)                  # DATASHEET  Eagle: chip + caps + resistors + jumper
DRV_PARTS_H = 1.1                   # DATASHEET  VSSOP-10 max height
DRV_WIRE_SIDE = "bottom"            # PHOTO      1791b8ab: the wires are soldered on the BACK (the side printed "I2C ADDR 0x5A")

# ---------------------------------------------------------------- coin ERM motor ROB-08449
MOTOR_D, MOTOR_T = 10.0, 3.4        # DATASHEET  Yuesui B1034.FL45-00-015
MOTOR_ADH = 0.15                    # DATASHEET  adhesive
MOTOR_LEAD_LEN = 45.0               # DATASHEET  AWG32 leads 45 +/- 2
MOTOR_FLOOR = 0.6                   # DESIGN     thin floor under the motor (buzz reaches the wrist)
MOTOR_LEAD_NOTCH_W = 3.0            # MEASURED   coupon (2.0 was too tight)
MOTOR_LEAD_NOTCH_D = 3.3            # MEASURED   coupon

# ---------------------------------------------------------------- Seeed XIAO nRF52840 (plain).  local: x = toward USB, y = left when USB is up (D0..D6 side), origin = board centre, z 0 = PCB bottom
XIAO_L, XIAO_W = 20.96, 17.78       # DATASHEET  Seeed dimensioning DXF
XIAO_PCB_T = 1.25                   # DATASHEET  Seeed STEP v15: board faces at -0.25 and +1.00
XIAO_USB_W, XIAO_USB_H, XIAO_USB_LEN = 8.94, 3.26, 7.35   # DATASHEET  Seeed STEP/KiCad (16-pin USB-C receptacle)
XIAO_USB_OVERHANG = 1.45            # DATASHEET  Seeed KiCad: receptacle tip past the PCB edge
XIAO_SHIELD = (-9.0, -5.3, 3.6, 5.3)   # DATASHEET  Seeed STEP: RF can 12.6 x 10.6 (x0,y0,x1,y1)
XIAO_SHIELD_H = 2.0                 # DATASHEET  Seeed STEP
XIAO_RESET_XY = (8.57, 5.71)        # DATASHEET  Seeed KiCad K1
XIAO_RESET_H = 0.55                 # DATASHEET  2.6 x 1.6 x 0.53 switch
XIAO_BAT_PADS = [(0.32, 4.44), (2.22, 4.44)]   # DATASHEET  Seeed KiCad BAT0 (+), GND0 (-) on the BOTTOM
XIAO_PAD_Y, XIAO_PAD_X0, XIAO_PAD_PITCH = 7.62, 7.62, 2.54    # DATASHEET  7 castellated pads per long edge
XIAO_WIRE_SIDE = "edge"             # PHOTO      b09c09de / b59e1f1e: wires are soldered on TOP of the castellated pads and leave SIDEWAYS
                                    #            past both long edges (heat-shrunk, ~2 mm thick); only the battery leads are underneath (1c7cb16f)
XIAO_UNDER_CLEAR = 2.5              # MEASURED +0.5 margin  v4.1: you measured the underside glue + wires at ~2 mm (ruler, approx.);
                                    #            the XIAO stands this high on 4 corner rests so they never touch the floor
XIAO_UNDER_BLOB = 2.0               # MEASURED (approx.)  twin envelope of that underside glue/joints (0.5 mm left to the floor)
XIAO_BASEMENT = XIAO_UNDER_CLEAR    # (v3/v4: 1.7) floor -> PCB bottom; the battery leads (2 x 1.3) also run in here
XIAO_REST_L = 1.25                  # DESIGN     corner rests: contact length along the board (>= 1.2), only on the bare corner strips
                                    #            beyond the castellated pads (|x| > 8.9) - clear of BAT/GND (centre) and NFC1/NFC2 (x -8.89,
                                    #            |y| 3.3-6.2) on the back (Seeed "Bottom Key coordinates", vendor/seeed/Bottom-pad-positioning.zip)
XIAO_SIDE_EXTRA = 1.5               # MEASURED-FIT v4.2: you asked to move the wall on the XIAO's battery side (your left, seen from the skin side)
                                    #            'a bit, not much' outward -> the battery-side inner wall (cradle rib) moves +1.5 mm, the shell grows 1.5 mm
MOTOR_WALL_OPEN_W = 23.0            # MEASURED-FIT v4.2: you asked for a 2.3 cm opening in the elbow wall behind the motor cup (spliced DRV wires)
XIAO_SIDE_GAP = 2.0                 # PHOTO      b09c09de: room past each long edge for the sideways wires to fold up (was 0.8 - too little)
XIAO_TOP_BLOB = 2.0                 # PHOTO      b09c09de: solder + heat-shrunk wire on top of the pads
# v4 harness (photos 8dd4193b, d8ea4884, 997f4a98): the 8-wire screen cable reaches the XIAO over its USB-C END; 7 wires land on the
# 5V/GND/3V3/D10..D7 row, ONE (blue) crosses to the D0..D6 row; all hot-glued there.  Hop 1 and the battery leads leave the XIAO's
# FAR end (away from the USB-C), glued along the board.  -> the XIAO's USB-C points the same way as the screen socket's mouth.
XIAO_USB_WALL = "hand"              # PHOTO-DERIVED  v4: USB-C through the HAND-END wall (v3: the y- side wall)
LCD_XIAO_DY = 7.0                   # DESIGN     screen centreline sits this far toward the 5V/GND/3V3 row from the XIAO axis, so the cable
                                    #            folds down BESIDE the USB-C receptacle (receptacle half-width 4.47 + 0.4 + cable radius 1.6 + 0.5)

# ---------------------------------------------------------------- USB-C cable plug (must seat fully)
USBC_PLUG_W, USBC_PLUG_H = 12.35, 6.5   # DATASHEET  USB Type-C spec R2.0 Fig. 3-3 (p. 47): "12.35 MAX" (section A-A), "6.5 MAX" (section C-C)
USBC_PLUG_LEN = 35.0                # DATASHEET  USB Type-C spec R2.0 Fig. 3-3 (p. 46): overmould reference length (35); your cable is ~19 (b59e1f1e)
USBC_PLUG_GAP = 0.6                 # DESIGN     clearance kept round the overmould
USBC_OPEN_GAP = 0.35                # DESIGN     wall opening = receptacle + this per side

# ---------------------------------------------------------------- Waveshare 1.69in LCD module.  local: u across (31.5), v along (39), origin = PCB centre, z 0 = PCB BACK face, glass at -z ... see twin.py
LCD_W, LCD_L = 31.5, 39.0           # DATASHEET  2D drawing: PCB
LCD_PCB_R = 5.0                     # DATASHEET  corner radius (5.0 / 5.5)
LCD_PCB_T = 1.64                    # DATASHEET  STEP: board 1.60 (faces -0.24 / -1.84) + 0.04 glue line; 1.64 + 1.76 = drawing 3.40
LCD_LCM_W, LCD_LCM_L = 30.07, 37.43 # DATASHEET  glass/backlight unit
LCD_LCM_T = 1.76                    # DATASHEET  STEP
LCD_AA_W, LCD_AA_L = 27.97, 32.63   # DATASHEET  active area
LCD_AA_R = 5.0                      # DATASHEET
LCD_AA_OFF_V = 1.30                 # DATASHEET  active area sits 1.30 toward the "top" (away from the FPC tail): (3.70 - 1.10) / 2
LCD_STANDOFF_XY = (12.15, 15.9)     # DATASHEET  4 x M2 brass standoffs on the back: 24.30 x 31.80 rectangle
LCD_STANDOFF_H = 2.5                # DATASHEET  5.90 - 3.40
LCD_STANDOFF_D = 3.8                # PHOTO      8026e80d: barrel 3.8 (STEP models 3.5; the larger value is kept as the envelope)
LCD_SOCKET_W, LCD_SOCKET_L = 14.75, 5.05 # DATASHEET  STEP solid: 8-pin 1.25 mm side-entry socket incl. tabs and solder tails (photo 8026e80d agrees)
LCD_SOCKET_V = -4.50                # DATASHEET  STEP: socket centre 4.50 from the PCB centre, toward the FPC tail (side from the 2D drawing)
LCD_SOCKET_H = 3.7                  # DATASHEET  STEP 3.66 / drawing 7.1 - 3.40
LCD_PLUG_W, LCD_PLUG_OUT = 11.4, 3.0     # PHOTO    8026e80d: plug housing 11.2 wide, sticks 2.3-3.0 out of the socket mouth
LCD_TAILS = 0.0                     # DATASHEET  the STEP socket length already includes the solder tails
LCD_PARTS_BOX = (-9.5, 2.0, 9.5, 9.5)    # DATASHEET  drawing (scaled): TXB0108 + regulator + passives (u0,v0,u1,v1)
LCD_PARTS_H = 1.2                   # DATASHEET  STEP: tallest back-side part ends 1.20 below the board (TSSOP-20)
LCD_CABLE_LEN = 30.0                # MEASURED  you, 17 Nov 23:00: ~3 cm of free wire from the socket to where the wires reach the XIAO
LCD_LIP_T = 1.0                     # DESIGN     frame lip over the glass edge
LCD_WIN_MARGIN = 0.4                # DESIGN     window = active area + this per side
LCD_EDGE_REST = 1.2                 # DESIGN     the LCD PCB overlaps the tray's -Y and -X wall tops by this much
FRAME_WALL = 1.2                    # DESIGN
FRAME_SKIRT = 2.5                   # DESIGN     skirt overlap down over the tray walls
FRAME_FIT = 0.2                     # MEASURED   coupon: 0.2 per side "fits by hand" (v2 0.15 risked splitting the 1.2 mm skirt at its corners)
FOAM_T = 0.8                        # DESIGN     (v3) foam tape; v4 needs ~2.0 under the standoff (two layers) because of POD_EXTRA_H
POD_EXTRA_H = 1.2                   # MEASURED-FIT  you, 17 Nov: "more room inside" for wires + glue under the screen -> the LCD seat
                                    #          (wall tops, post, foam) is raised 1.2 mm; floor, walls, frame fit and skin side unchanged

# ---------------------------------------------------------------- battery Akyga LP601730
BAT_L, BAT_W, BAT_T = 30.5, 17.5, 6.5   # DATASHEET  MAX size (nominal 30 x 17 x 6.0); PCM is inside the length (photo)
BAT_CLEAR = 0.3                     # DESIGN     per side round the max size
BAT_FLOOR = 0.8                     # DESIGN     floor under the cell: 4 layers (v2: 0.4 = 2 layers, too thin under a Li-Po)
BAT_LEAD_D = 1.3                    # DATASHEET  26 AWG UL1007 (Akyga drawing items 50/60)
BAT_LEAD_LEN = 30.0                 # MEASURED  (approx.) "all hops about the same": ~30 mm free
BAT_LEN_MARGIN = 2.0                # MEASURED-FIT  v3 cradle (30.5 + 2 x 0.3 = 31.1) was "a tiny bit too short" with the PCM end and
                                    #          lead bulge -> +2.0 (>= the +1.5 asked).  Cradle now 33.1 long.
BAT_L_REAL = 31.6                   # ASSUMED  twin length of YOUR cell incl. PCM end + lead bulge: longer than the 31.1 cradle (fit test);
                                    #          photo d8ea4884 cannot give the length (the cell lies half under the DRV, steep angle)
BAT_LEAD_CORNER = 1.8               # PHOTO    d8ea4884: red/black leave at ONE CORNER of the PCM end (centre ~1.8 in from the long side),
                                    #          not the middle.  Which corner is unknown -> the cradle has relief at BOTH corners

# ---------------------------------------------------------------- tactile switch (HELP / screen button), v4.3: the REAL switch
BTN_S = 5.0                         # MEASURED (v4.3, +/-0.2, no calipers) body 5.0 x 5.0
BTN_BODY_H = 3.0                    # MEASURED body height along the push axis (v4.3b: vertical)
BTN_TOTAL_H = 6.5                   # MEASURED body + plunger
BTN_PLUNGER = BTN_TOTAL_H - BTN_BODY_H   # (derived) plunger stands 3.5 above the body
BTN_CAP_D = 2.5                     # MEASURED round plunger
BTN_CLEAR = 0.2                     # DESIGN   per side round the body and the plunger (user-approved; tighter than CLEAR)
BTN_POCKET = BTN_S + 2 * BTN_CLEAR  # (derived) 5.4 square, 4-sided, depth = BTN_BODY_H
BTN_HOLE_D = BTN_CAP_D + 2 * BTN_CLEAR   # (derived) 2.9 plunger bore
BTN_LEAD_N = 2                      # MEASURED 2 hook-up wires (WIRE_D each), soldered on the legs underneath/side
BTN_JOINT_ROOM = BLOB_H             # DESIGN   glue + joint room UNDER the body (2.5), between the legs; never on the cell
BTN_SINK = 0.3                      # DESIGN   plunger top sits this far BELOW the guard ring top (never proud)
BTN_RING_ID, BTN_RING_OD = 6.0, 9.0 # DESIGN   guard ring round the plunger (a fingertip reaches ~0.6 mm into a 6 mm bore)
BTN_RING_FILLET = 0.2               # DESIGN   fillet on the ring's outer and inner top edges (the ring is only 0.4 proud)
BTN_PLAY = 0.2                      # DESIGN   switch body top -> cap ceiling (switch is trapped, not squeezed)
# v4.3b: the switch lies FLAT ON TOP OF THE BATTERY end, plunger UP through the frame top.  Two small drop-in prints:
#   SEAT = corner bridge on two wall ledges (elbow + battery-side wall): the press goes into the walls, the cell takes none
#   CAP  = 4-sided pocket round the body + ceiling with the plunger bore + guard ring that pokes up through the frame lip
BTN_SEAT_T = RIB_T                  # DESIGN   seat (bridge) plate thickness, load-carrying
BTN_BAR = 1.6                       # DESIGN   bar across the seat window under the bare centre of the switch's bottom
BTN_LEDGE = 0.7                     # DESIGN   ledge notch depth in the two walls (leaves 0.8 = MIN_FEAT of the 1.5 wall)
BTN_SEAT_FIT = 0.2                  # MEASURED coupon: 0.2 slot fits by hand (seat in its ledge notches)
BTN_CAP_WALL = 0.8                  # DESIGN   cap pocket walls (MIN_FEAT; they only locate, the seat takes the push)
BTN_FLANGE = 10.6                   # DESIGN   cap flange (square) under the frame lip: the frame holds cap + switch + seat down
BTN_RING_HOLE_FIT = 0.3             # DESIGN   radial gap, guard ring <-> its hole in the frame lip

# ---------------------------------------------------------------- v4.3 hand-wall cable window (screen cable bend, beside the USB-C)
LCD_CABLE_D = 3.2                   # PHOTO    8 x 1.0 mm wires, loosely gathered (same envelope as the twin since v4)
HAND_WIN_FLAT = 1.0                 # DESIGN   extra width: the gathered bundle flattens in the bend
HAND_WIN_RIB = RIB_T                # DESIGN   wall kept between the USB-C opening and the window (measured at the chamfered faces)
HAND_WIN_EDGE = 0.5                 # DESIGN   45 deg edge break on both faces (EXIT_FILLET_R 1.2 does not fit a 1.5 wall twice)

# ---------------------------------------------------------------- MAX30102 clone "RCWL-0531" (green).  local: x along the long edge, y 0 = PAD/WIRE edge, holes at the far edge, z 0 = PCB back, sensor at +z
MAX_L = 18.1                        # PHOTO     db9b86ad (ruler along the hole edge: 18.0-18.2) and 73fbbcdb (scaled from the 2.54 mm pad pitch: 18.1)
MAX_W = 13.9                        # PHOTO     73fbbcdb, scaled from the pad pitch (13.8-14.0). NOT 12.7: the shop text copies Maxim's reference board
MAX_PCB_T = 1.2                     # PHOTO     6c47371a: edge 1.15-1.2 (scaled from the 1.6 mm tantalum caps)
MAX_WIRE_EDGE = "long"              # PHOTO     the 7-pad row VIN SCL SDA INT IRD RD GND runs along an 18.1 mm edge (6c1bd174, a72308c7)
MAX_HOLE_EDGE = "opposite_wires"    # PHOTO     the 2 holes are on the long edge opposite the pads
MAX_HOLE_IN_LONG = 1.4              # PHOTO     73fbbcdb: hole centres 1.3-1.45 in from the hole edge
MAX_HOLE_IN_SHORT = 1.43            # PHOTO     holes are 15.24 apart (in line with pads 1 and 7), centred: (18.1 - 15.24) / 2
MAX_HOLE_D = 1.4                    # PHOTO     db9b86ad / 73fbbcdb: 1.3-1.5 (v2 said 1.0)
MAX_PAD_IN = 1.4                    # PHOTO     73fbbcdb: pad row centre, in from the pad edge
MAX_PIN_SOCKET_D = 1.0              # DESIGN    blind socket for a pressed-in metal pin (cut paperclip) - no printed pins on the MAX
MAX_PIN_SOCKET_DEPTH = 1.5          # DESIGN
MAX_CHIP_X = 1.45                   # PHOTO     73fbbcdb / 6c1bd174 / a72308c7: optical chip centre is 1.4-1.8 off the board centre, toward the GND end
MAX_CHIP_Y = -0.6                   # PHOTO     ... and 0.35-1.1 toward the pad edge (+ = toward the hole edge)
MAX_CHIP_L, MAX_CHIP_W = 5.6, 3.3   # DATASHEET MAX30102 14-pin OLGA package 5.6 x 3.3 x 1.55 (Analog Devices product page)
MAX_CHIP_H = 1.55                   # DATASHEET MAX30102 package height
MAX_COMP_H = 1.6                    # MEASURED  you: sensor-side parts 1.5-1.7 (the 3 yellow tantalum caps "106C" are the tallest)
# sensor-side parts, PHOTO 73fbbcdb (+/-0.4): (label, x0, y0, x1, y1, height); x from the VIN end, y from the pad edge
MAX_PARTS = [("tantalum GND end x2", 14.2, 5.1, 18.0, 8.4, 1.6), ("tantalum VIN end", 1.4, 3.6, 4.9, 5.2, 1.6),
             ("0603", 1.6, 5.5, 3.3, 6.6, 0.9), ("SOT-23-5", 0.85, 7.5, 3.9, 10.3, 1.3), ("0603", 4.1, 7.7, 5.1, 9.9, 0.9),
             ("3 x 0603 resistors", 6.2, 3.75, 7.1, 12.0, 0.6), ("SOT-23 + passives", 7.8, 10.6, 11.3, 13.3, 1.2),
             ("2 x 0603", 12.7, 11.0, 15.0, 12.95, 0.9)]
MAX_WIN_L = MAX_CHIP_L + 1.0        # DESIGN    +0.5 per side: the chip position comes from photos
MAX_WIN_W = MAX_CHIP_W + 1.0        # DESIGN
MAX_CHIP_RECESS = 0.5               # DESIGN    board face = this + MAX_COMP_H above the skin plane: keeps a 0.4 mm floor under the 1.6 mm caps.
                                    #           The chip itself is 1.55 tall, so its face ends 0.55 behind the skin plane
MAX_BLOB_H = 2.0                    # MEASURED-PLAN  glue blobs ~3 mm today; user trims them to <= 2 mm
MAX_BLOB_STRIP = 3.5                # PHOTO     blob strip width in from the pad edge
MAX_BLOB_RELIEF = 3.5               # DESIGN    (v1 name) relief depth below the PCB face
MAX_BACK_H = 0.6                    # ASSUMED   solder points on the back (cannot be seen in any photo)
MAX_RIM = 0.8                       # DESIGN    seat rim under the PCB edges
RING_W = 0.8                        # DESIGN    light-seal ring wall
RING_H = 0.8                        # DESIGN    ring protrusion into the skin

# ---------------------------------------------------------------- coupon (v1, unchanged)
COUPON_CLEARS = [0.2, 0.3, 0.4, 0.5]  # DESIGN

# ================================================================= v6: TWO PODS, WIRE-FIRST (18 Nov: the v4.x single pod failed in your
# hands - too many parts in one small box, and the real 28AWG wires (1.0 mm, stiff, solder joints + hot-glue blobs) could not make the
# tight bends, grooves and stacked routes the twin assumed).  Band order from the hand: BRAIN POD | POWER POD | HEART ISLAND (+ AIR
# ISLAND beside it).  Every crossing wire runs straight across a neoprene gap.
WIRE_BEND_R = 8.0           # ASSUMED  smallest bend radius of ANY wire bundle (and of the 8 screen wires).  MEASURE IT (MEASURE_NEXT 1)
WIRE_BEND_R_SINGLE = 4.0    # ASSUMED  one lone 1.0 mm wire on its own (only the screen's blue wire uses it).  MEASURE IT
PAD_ROOM = 5.0              # DESIGN   clear floor in front of every board edge that carries solder pads (joints + glue + wire exit)
WIRE_ROOM_H = 4.0           # DESIGN   free height kept above boards where wires run, and in every wire room
SCREEN_FREE_H = 6.0         # DESIGN   free height under the screen board where its 8-wire cable + plug land
SCREEN_WIRE_ANGLE = 60.0    # DESIGN   the 7 screen wires leave their XIAO castellations rising at this angle, pointing inward (re-solder)
XIAO_SHIFT = 2.5            # DESIGN   XIAO moved this far in from the hand wall (centres its 5V row under the screen plug);
                            #          the USB-C plug reaches it through a plug-size tunnel in the hand wall
BAT_LEAD_ROOM = 3.0         # DESIGN   open floor between the battery's lead end and the power pod's hand wall
POD_GAP = GAP_MIN           # DESIGN   neoprene hinge between two parts, measured between their frame / lid skirts
LID_T = 1.2                 # DESIGN   power pod lid plate (6 layers)
LID_SKIRT = 2.0             # DESIGN   lid skirt overlap down over the power pod walls
OPEN_R = 2.0                # DESIGN   corner fillet of every wire opening in a wall (big, rounded, insulation-safe)
GLUE_DEPTH = 0.4            # DESIGN   glue zones = 0.4 mm keyed recesses in the floor (hot glue grips, you see where it goes)
BTN_LEAD_LEN = 30.0         # ASSUMED  free length of the HELP button's 2 wires today (never measured - MEASURE_NEXT 1)

# ================================================================= v6.1: your MEASURED free wire lengths, pad to pad (18 Nov), min / normal
HOP1_LEN = (50.0, 60.0)     # MEASURED  XIAO -> DRV2605L, 4 wires: 50-60 each
HOP2_LEN = (45.0, 60.0)     # MEASURED  DRV -> ICM: shortest 45, the rest ~60
BAT_LEN_M = (45.0, 45.0)    # MEASURED  battery leads -> XIAO
BTN_LEN_M = (34.5, 34.5)    # MEASURED  HELP button -> XIAO
LCD_LEN_M = (25.0, 50.0)    # MEASURED  screen plug -> XIAO: shortest 25, normal 45-50
HOP3_LEN = (51.0, 51.0)     # MEASURED  ICM -> MAX30102
HOP4_LEN = (50.0, 50.0)     # MEASURED  MAX30102 -> TMP117 #1
HOP5_LEN = (20.0, 30.0)     # MEASURED  TMP117 #1 -> #2: shortest 20, normal 30
HOP6_LEN = (60.0, 60.0)     # MEASURED  TMP117 #2 -> SHTC3
HOP_LEN_XIAO_DRV, HOP_LEN_DRV_ICM, HOP_LEN_ICM_MAX = HOP1_LEN[0], HOP2_LEN[0], HOP3_LEN[0]
HOP_LEN_MAX_TMP1, HOP_LEN_TMP1_TMP2, HOP_LEN_TMP2_SHT = HOP4_LEN[0], HOP5_LEN[0], HOP6_LEN[0]
BAT_LEAD_LEN, BTN_LEAD_LEN, LCD_CABLE_LEN = BAT_LEN_M[0], BTN_LEN_M[0], LCD_LEN_M[1]
BAT_LEAD_ROOM = 1.5         # DESIGN   (v6: 3.0) the cell's lead end closer to the hand wall: hop 1 + hop 2 must span the power pod
OPEN_W = 16.0               # DESIGN   every wire opening: bundle 3 + 2 x (WIRE_BEND_R - 1.5) = 16 wide, floor to the top, open from above
LAB_WALL_H = 2.5            # DESIGN   labyrinth / tongue walls: low, just enough to hold a meander's shape
LAB_WALL_T = 1.2            # DESIGN

# ---------------------------------------------------------------- v6.2: MAX30102 pocket after the user's v6.1 dry fit (wires stay on the SENSOR side)
MAX_WIRE_SIDE = "back"     # v6.3 MEASURED-PLAN  the user re-solders the MAX wires on the BACK (away from the skin); "sensor" = v6.2 pocket + shield
MAX_FRONT_FILLET = 0.0     # MEASURED  v6.4: after the back-side re-solder the sensor side is flat (factory parts only)
MAX_BACK_ROOM_H = 3.0      # DESIGN    free height over the MAX back (joints + glue BLOB_H 2.5 + 0.5)
MAX_SEAL_LIP_H = 0.6       # DESIGN    raised light-seal lip round the window, curved set only (the flat set's flat face is the seal)
MAX_BLOB_H = 2.5           # MEASURED  v6.1 dry fit: joints + glue on the sensor side stand ~2.5 mm off the board (was planned 2.0 after trimming)
MAX_BLOB_STRIP = 4.6       # MEASURED  ... and reach ~4.6 mm in from the pad edge (was 3.5)
MAX_BLOB_CLEAR = 0.3       # DESIGN    all round the joints + glue, in the relief
MAX_POCKET_LOOSE = 0.2     # MEASURED  v6.1 dry fit: the board pocket was tight -> +0.2 per side on top of CLEAR
MAX_SHIELD_T = 0.6         # DESIGN    printed light-shield plate (max_shield.stl) that closes the skin side flush; black tape works too
MAX_SHIELD_LEDGE = 1.2     # DESIGN    the plate's recess reaches this far past the open area on every side (glue / tape ledge)
MAX_SHIELD_FIT = 0.15      # DESIGN    plate outline smaller than its recess by this per side

# ---------------------------------------------------------------- v6.4: MAX30102 optical chip at the skin
MAX_CHIP_PROUD = 0.05      # DESIGN    chip face this far past the local skin surface (target 0..0.1)
MAX_LOW_PARTS_H = 0.45     # DESIGN    general room under the board for unlisted tiny parts; taller parts get their own pockets
MAX_PART_CLEAR = 0.4       # DESIGN    per side round each part pocket: the part positions come from photos (+/- 0.4)
MAX_PART_GAP = 0.15        # DESIGN    under a part in a blind pocket

# ---------------------------------------------------------------- v6.5: screen cable NOT re-soldered -> wire garage in the brain pod
LCD_GARAGE = True          # MEASURED  user keeps the 45-50 mm screen wires: the spare goes into a garage on the 5V-row (+Y) side
LCD_GARAGE_LEN = (45.0, 50.0)   # MEASURED  free length of the 7 wires to the 5V row (blue: shortest 25, routed on its own)
LCD_GARAGE_FLOOR_Z = 1.7   # DESIGN    wire centre where the fold's lower leg lies on the garage floor (floor 1.0 + wire radius)
LCD_GARAGE_MARGIN = 0.3    # DESIGN    garage end wall beyond the fold at the LONGEST wire
SLEEVE_D = 4.0             # MEASURED-PLAN  user photo: heat-shrunk splice sleeves on hop 1 and the battery leads, ~3-4 mm dia
SLEEVE_L = 30.0            # MEASURED-PLAN  ... ~20-30 mm long, rigid: modelled as a straight rod, never inside the brain pod
SLEEVE_END_ROOM = 2.0      # DESIGN    straight wire kept past each sleeve end (before the next bend / the cell / the pad fan)

# ---------------------------------------------------------------- v6.6: TMP117 #2 straight above #1, the SHTC3 cage stacked on top
AIR_ON_TOP = True          # MEASURED-PLAN  user dry fit: hop-5 wires only reach with #2 straight above #1; the SHTC3 rides on top
TMP2_PLATE_T = 1.2         # DESIGN    plate between the strap slot and TMP117 #2 (was 1.8): shortest hop 5
TMP2_SOCKET_THRU = True    # DESIGN    #2 faces chip DOWN like #1 (pads straight above #1's): its two sockets drop into pockets through the plate
HOP5_EDGE_GAP = 0.9        # DESIGN    hop-5 wires go straight up this far outside the two pad edges
HOP5_BEND_R = 1.0          # MEASURED-PLAN  user: the 4 wires wrap round the board edges straight up (validated by his dry fit)
AIR_GAP_OVER_T2 = 3.0      # DESIGN    still air between TMP117 #2 (top of its solder points) and the SHTC3 board
AIR_DX = 4.5               # DESIGN    SHTC3 sits this far toward the elbow end of TMP117 #2: lets hop 6 make ONE >= R8 loop
CAGE_LEG = (2.4, 3.0)      # DESIGN    cage legs (x, y)
CAGE_RING_T = 1.2          # DESIGN    ring under the SHTC3 edges (carries its 4 locating pins)
CAGE_RING_W = 4.2          # DESIGN    ring width under the board edges (the holes are 2.54 in)
AIR_POCKET_CLEAR = 0.5     # MEASURED  user: the SHTC3 did not fit the old air island -> its pocket is the outline + 0.5 per side
AIR_PAD_ROOM = 3.5         # DESIGN    extra room past the SHTC3 pad edge for the 4 joints + glue blobs (BLOB_H 2.5), wires straight down

# ---------------------------------------------------------------- v6.7: brain frame (cover) from the user's fit of the printed v6.5 pod
FRAME_SKIRT_EXTRA = 3.0    # MEASURED  user: the cover must reach 2 mm further down (+1 mm margin)
USBC_OPEN_PLUS = 0.5       # MEASURED  user: USB-C opening 1.0 mm bigger in width and height (0.5 per side), pod tunnel + cover
FRAME_STOP_W = 1.2         # DESIGN    stop ledges / blocks inside the cover that land on the pod rim

# ---------------------------------------------------------------- v6.7.2: power lid HELP switch = simple square through-hole
BTN_SQ_HOLE = BTN_S + 2 * 0.3   # MEASURED-PLAN  user: the wired switch did not fit the pocket -> 5.6 x 5.6 through-hole, he glues it
BTN_HOLE_CHAMFER = 0.4     # DESIGN    top edge chamfer of the square hole
BTN_DISH_D, BTN_DISH_DEPTH = 9.0, 0.5   # DESIGN    shallow finger dish round the hole (plunger stays below the lid top)
BTN_CLEAR_BOX = 9.0        # DESIGN    nothing from the lid inside 9 x 9 round the hole, down to the pod floor

# ---------------------------------------------------------------- v6.8: the SHTC3 on a drop-in SHELF over the MAX30102 (owner: same level as TMP117 #2)
SHTC3_SHELF = True         # MEASURED-PLAN  owner: SHTC3 moves off the TMP117 #2 cage onto a shelf over the MAX, side by side with #2
SHELF_T = 1.0              # DESIGN    shelf plate (5 layers); its TOP = TMP117 #2's plate top (one upper floor), underside 1.0 lower
SHELF_FIT = 0.15           # DESIGN    drop-in shelf: per side against its seats in the island (back wall, hand rib, elbow rebate)
SHELF_REBATE = 0.7         # DESIGN    the shelf's elbow edge sits in a 0.7 x 1.0 rebate cut into the top of TMP117 #2's side wall
SHTC3_FIT = 0.3            # DESIGN    SHTC3 seat = outline + this per side (lips / stops)
SHELF_LIP_T = 1.2          # DESIGN    lips (3 perimeters)
SHELF_LIP_H = 1.7          # DESIGN    lip top above the shelf top: 0.36 under TMP117 #2's board edge at the elbow stop
SHELF_STANDOFF = 1.0       # DESIGN    still air between the shelf top and the SHTC3 board (4 posts at its holes, pins through)
SHELF_VENT = (2.0, 4.0)    # DESIGN    vent slots in the lips: width, pitch (air flows under the SHTC3 from the back and hand sides)
SHELF_KEY = (1.2, 0.8, 0.7)   # DESIGN  two locating pegs on the back-wall top (x, y, height); shelf holes +0.2 per side
H6_TILT = 45.0             # DESIGN    hop-6 loop leans this many degrees up from flat over the bay (0 = lies flat toward +Y)

# ---------------------------------------------------------------- v6.9: TMP117 #2 fitted with its wires ALREADY soldered (no re-solder) + owner fit feedback
TMP2_BLOB_CHIP_H = 3.0     # MEASURED-PLAN  owner: #2's joints + glue stand up to 3.0 mm on the CHIP side (faces down onto the plate)
TMP2_BLOB_BACK_H = 2.5     # MEASURED-PLAN  ... and up to 2.5 mm on the other side (faces up, open air)
TMP2_RELIEF_CLEAR = 0.5    # DESIGN    per side round #2's joints + glue and its sockets, in the relief pockets in the plate
TMP2_RELIEF_GAP = 0.3      # DESIGN    under #2's joints + glue / sockets, above the pocket floor
TMP2_POCKET_FLOOR = 0.4    # DESIGN    blind pocket floor (2 layers) left over the strap slot: the plate's first layers bridge rib to rib
TMP2_OUTLINE_CLEAR = 0.6   # DESIGN    free ring round #2's board outline at board height (glue at the edges)
TMP2_EXIT_R = 4.0          # DESIGN    wire exit room in front of #2's pad edge: one R4 single-wire bend (WIRE_BEND_R_SINGLE)
TMP2_CHIP_REST = 1.8       # DESIGN    square chip rest on the plate under #2's chip (chip 2.0): the chip lands flat on it, no air gap
TMP2_PLATE_FRONT = 2.0     # DESIGN    plate ends this far behind the pad edge, flush with the side-wall ends (no bridge cantilever)
BOARD_FIT_PLUS = 0.4       # MEASURED  owner v6.8 print: "columns a tiny bit too close, the sensor couldn't sit" -> every board-locating
                           #           wall / lip / stop / socket pocket in island_skin + island_shelf +0.4 per side over the v6.8 fit
PIN_SHRINK_ISLAND = 0.3    # MEASURED  ... and every printed pin into a board hole 0.3 thinner (2.1 -> 1.8 for the 2.5 holes)
SHTC3_FIT = 0.3 + BOARD_FIT_PLUS   # v6.9: SHTC3 seat = outline + 0.7 per side (v6.8: 0.3)

# ================================================================= v7.0 FINAL EDITION (19 Nov): nothing thin, robust seats, verified boards
# Rule: no printed wall / floor / web / rib under MIN_T = 1.2 mm.  The only exceptions are the two skin-contact seats whose height is
# fixed by a chip that must touch the skin (listed in build.py FRAGILITY_EXCEPTIONS and in out/WARNINGS.txt).
MIN_T = 1.2                # DESIGN    thinnest printed feature anywhere (build.py fails below this)
MIN_T_FORCED = 0.8         # DESIGN    absolute minimum where geometry forces it and nothing loads it
FLOOR = 1.2                # DESIGN    (v6: 1.0) general floor, 6 layers
BAT_FLOOR = 1.2            # DESIGN    (v6: 0.8)
MOTOR_FLOOR = 1.2          # DESIGN    (v6: 0.6) the ERM shakes the whole pod; 1.2 PETG still carries the buzz
BAY_FLOOR = 1.2            # DESIGN    (v6: 0.8) skin island bay floor
GLUE_DEPTH = 0.0           # DESIGN    (v6: 0.4) no recesses in the floors any more (they left 0.6 mm); glue points are in ASSEMBLY.md
LCD_LIP_T = 1.2            # DESIGN    (v6: 1.0) frame lip over the glass edge
LID_T = 1.7                # DESIGN    (v6: 1.2) power lid plate: 1.2 stays under the 0.5 finger dish (was 0.7)
MAX_RIM = 1.2              # DESIGN    (v6: 0.8) walls round the MAX30102 pocket
LAB_WALL_H = 2.4           # DESIGN    (v6: 2.5) tongue walls: height <= 2 x thickness
FRAME_FIT = 0.3            # DESIGN    (v6: 0.2) brain cover / power lid over the pod walls: sliding fit 0.3 per side (PETG), glued
XIAO_FIT = 0.4             # DESIGN    XIAO between its corner lips: drop-in 0.4 per side (v6: 0.3)
# TMP117 #2 on its two posts
TMP2_HOLE_DX = 20.0        # MEASURED  owner, 19 Nov: hole centre to hole centre on HIS TMP117 #2 = 20.0 mm (ruler).  Adafruit's Eagle file
                           #           says 20.32; the owner's number wins.  Pins 1.8 in 2.5 holes, no centring cone: any spacing 19.3..20.7 drops on
TMP2_POCKET_FLOOR = TMP2_PLATE_T   # v7.0: NO pockets in the plate (v6.9: 0.3-0.4 floors that broke): the plate is a solid 1.2 everywhere and
                           #           #2 stands 0.8 higher on two back blocks + a chip pedestal + two front anti-tip rests
TMP2_FRONT_REST_GAP = 0.15 # DESIGN    front anti-tip rests end this far under #2's board face: the chip rest + back blocks set the height
TMP2_BLOCK_W = 4.4         # DESIGN    back blocks under #2's back holes (tied into the back wall), x width
SLOT_HAUNCH = 1.0          # DESIGN    45 deg haunches in the strap slot's two upper corners (plate bridge anchored, no sharp inside corner)
# shelf
SHELF_T = 1.2              # DESIGN    (v6.8: 1.0)
SHELF_FIT = 0.4            # DESIGN    (v6.8: 0.15) drop-in: 0.4 per side
SHELF_REBATE = 1.2         # DESIGN    (v6.8: 0.7) with the 0.4 fit the shelf still bears 0.8 on the rebate; 1.2 of wall stays beside it
SHELF_KEY = (3.0, 1.5, 1.2)   # DESIGN (v6.8: 1.2 x 0.8 x 0.7 pegs) two sturdy keys on a widened back ledge; shelf holes + SHELF_FIT per side
SEAT_CHAMFER = 0.6         # DESIGN    lead-in chamfer on board seats
MAX_BACK_ROOM_H = 2.9      # DESIGN    (v6.3: 3.0) free height over the MAX back under the 1.2 shelf: joints + glue 2.5 + 0.4 (flat set)
MAX_PIN_SOCKET_DEPTH = 0.6 # DESIGN    (v6: 1.1 effective) blind pin sockets under the MAX holes: 0.8 floor stays under them
MAX_PART_GAP = 0.1         # DESIGN    (v6.4: 0.15) under a part in a blind pocket
MAX_BLIND_FLOOR_MIN = 0.8  # DESIGN    a MAX part pocket is blind only if >= 0.8 floor stays under it, else it goes through the skin face
                           #           (v6.4: 0.4 - two 0.45 skins; they are now through pockets like their four neighbours)

# ================================================================= v7-cover (20 Nov): REMOVABLE screen cover with the button in it
# A new top cover for the brain pod ("screen island"), printed in PLA.  It replaces brain_frame: same outline, window, stops, USB-C
# cut-out and reset notch (so it fits the printed v7.0 brain pod), but it is NOT glued: grip ribs inside the skirt hold it by
# friction.  The HELP / screen button moves from the power lid into this cover, BELOW the screen (owner, 20 Nov): the same wired
# 5 x 5 tactile switch (BTN_* above) sits in a sleeve that hangs from the cover, under a printed captive plunger.
COVER_FIT = FRAME_FIT          # MEASURED  0.3 per side: the printed v7.0 brain_frame slides over the printed pod with this
COVER_WALL = FRAME_WALL        # DESIGN    1.2 skirt
COVER_GRIP_GAP = 0.1           # DESIGN    nominal gap left at the grip ribs (rib height = COVER_FIT - this = 0.2).  The coupon's 0.2 slot
                               #           "fits by hand", 0.15 risked splitting a skirt at its corners -> ribs only at mid-wall, where the
                               #           skirt flexes.  Too tight: scrape the ribs.  Too loose: lower this to 0.05 or 0.0 and reprint
COVER_GRIP_W = 1.6             # DESIGN    rib width along the wall (half-round)
COVER_WIN_CHAMFER = 0.4        # DESIGN    45 deg chamfer on the window's outer edge (bed side: also hides the first-layer squash)
COVER_BTN_POS = "centre"       # OWNER     "centre" = below the screen, centred (as asked).  "corner" = below the screen, elbow-side
                               #           corner, beside the screen-wire garage instead of in the middle of it (see screen_cover.py)
COVER_BTN_X = None             # DESIGN    button centre, pod interior coordinates (0,0 = inside corner hand wall / -Y wall); None =
COVER_BTN_Y = None             #           derived from COVER_BTN_POS.  Set both to override
COVER_BTN_CAP_D = 8.0          # DESIGN    printed plunger: the part the thumb feels
COVER_BTN_PROUD = 1.8          # DESIGN    cap stands this far above the cover face when it rests on the switch (2.4 when hanging at its stop)
COVER_BTN_CAP_CHAMFER = 0.6    # DESIGN    cap top edge
COVER_BTN_HOLE_GAP = 0.25      # DESIGN    radial gap cap <-> hole in the cover
COVER_BTN_FLARE = 1.0          # DESIGN    45 deg flare under the cover plate: the plunger cannot come out through the hole
COVER_BTN_FLANGE_T = 1.2       # DESIGN    cylinder below the flare (guides in the well)
COVER_BTN_WELL_GAP = 0.3       # DESIGN    radial gap flange <-> well
COVER_BTN_FLOAT = 0.6          # DESIGN    free play of the plunger between its stop and the switch (0.5-0.8 asked): never preloads the switch
COVER_BTN_PRESS_ROOM = 0.6     # DESIGN    room under the flange for the press (switch travel ~0.25 + margin)
COVER_BTN_STEM_D = 3.4         # DESIGN    plunger nose that meets the switch's 2.5 plunger
COVER_BTN_STEM_L = 0.5         # DESIGN
COVER_BTN_THROAT_D = 4.2       # DESIGN    hole in the depth stop: the switch's 2.5 plunger passes, its 5 x 5 body top does not
COVER_BTN_THROAT_T = 0.4       # DESIGN
COVER_BTN_SLEEVE = BTN_SQ_HOLE # MEASURED-PLAN  5.6 x 5.6: the square hole the wired switch fits in on the v7.0 power lid
COVER_BTN_SLEEVE_DEPTH = 2.0   # DESIGN    sleeve round the top 2 mm of the 3 mm body (the lid's hole was 1.7 deep): legs + joints stay below
COVER_BTN_WIRE_SLOT = 2.6      # DESIGN    slot in the sleeve wall facing the XIAO: the two button wires leave through it
LID_PLUG_FIT = 0.1             # DESIGN    per side: plug for the old 5.6 x 5.6 switch hole in the power lid (push fit / one glue dot)
# ---- v7-cover SIMPLE (20 Nov): the owner's printed corner cover - "the button doesn't fit through".  Simplest cover: no plunger, no
# tower/sleeve/depth stop/wire slot.  A plain round through-hole at the corner variant's button position; the bare tactile switch is
# glued under the plate by hand, its 2.5 actuator pokes up through the hole and the finger presses it directly.
COVER_SIMPLE_HOLE_D = 4.2          # OWNER     2.5 actuator (+/-0.2) + clearance
COVER_SIMPLE_HOLE_CHAMFER = 0.6    # OWNER     45 deg on the outer edge: the fingertip reaches the actuator
COVER_SIMPLE_RECESS = 5.8          # OWNER     square locating recess for the 5 x 5 body, inside face ...
COVER_SIMPLE_RECESS_DEPTH = 1.0    # OWNER     ... 1.0 deep, only if >= COVER_SIMPLE_MIN_PLATE of plate stays
COVER_SIMPLE_MIN_PLATE = 0.8       # OWNER
