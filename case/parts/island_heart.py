"""HEART / SKIN ISLAND (v2, digital twin) - right after the pod, top of the wrist just above the wrist bone.
Seen from the side (X = toward the elbow):

        [ ICM-20649 face up, pads at the HAND edge ]      [ TMP117 #2 chip up, pads at the ELBOW edge ] [groove ->] air island
        [   MAX30102 sensor down, pads -> lane     ] lane [ ====== 3 mm neoprene strap slot ========= ] [  block  ]
   skin [   window + light ring                    ]      [ TMP117 #1 chip down (touches the skin), pads -> lane ]

Stack A: MAX30102 on the floor (window + raised light ring, two blind sockets for pressed-in metal pins),
         ICM-20649 rigid on 3 locating pins + 1 rest above it.  The wires from the pod land straight on the ICM pads.
Lane   : every hop that changes level does it here (ICM -> MAX drops in, MAX -> TMP117 #1 crosses, #1 -> #2 rises);
         spare wire is folded into this lane.
Stack B: TMP117 #1 chip-down on a 0.6 mm floor (chip stands 0.2 mm proud in its skin window), the strap slot,
         a plate, TMP117 #2 chip-up on 2 pins.  TMP117 #2 -> air island leaves through the elbow-end groove.
Each hop crosses a board width, so the 50 mm wires are used up instead of having to be stuffed somewhere."""
import numpy as np
from geo import box, cbox, cyl, rbox, union
import params as P
import twin as T
from common import skin_skirt, flanges, locating_post, tie_post
from guides import flared_exit, exit_post, _lip

c = P.CLEAR
e = c                                           # CLEAR is per side (as on the coupon)
# ---------------------------------------------------------------- plan (X from the hand-end face, Y centred)
IX0 = 0.5 + e                                   # ICM PCB hand edge (overhangs the low hand wall)
IX1 = IX0 + P.ADA_W
A_X1 = IX1 + e
MAX_X1 = IX1                                    # MAX pad edge (same line as the ICM's lane edge)
MAX_X0 = MAX_X1 - P.MAX_W
MAX_DY = 1.4                                    # MAX shifted in Y so two of the ICM posts clear it
LANE_W, DIV_T = 4.5, 2.0
LANE_XC = A_X1 + LANE_W / 2
L1_X1 = A_X1 + LANE_W                           # lane, then the divider (strap-slot side wall / plate support)
B_X0 = L1_X1 + DIV_T
TX0 = B_X0 + e                                  # TMP PCBs
TX1 = TX0 + P.TMP_W
B_X1 = TX1 + e
G_W = P.CABLE_CH_W                              # elbow-end groove (TMP117 #2 -> air island)
G_XC = B_X1 + G_W / 2
L = B_X1 + G_W + P.EXIT_FLARE + P.WALL
HB = P.ADA_L / 2 + c                            # half board zone (Y)
W = 2 * HB + 2 * P.WALL

# ---------------------------------------------------------------- heights
Z_MF = P.MAX_CHIP_RECESS + P.MAX_COMP_H         # MAX PCB sensor face
Z_MB = Z_MF + P.MAX_PCB_T                       # MAX PCB back
Z_ICM = Z_MB + P.MAX_BACK_H + P.GAP             # ICM PCB bottom
Z_ICM_TOP = Z_ICM + P.PCB_T
Z_WALL_A = Z_ICM_TOP + 0.6
Z_T1F = P.TMP_CHIP_H - P.TMP_CHIP_PROUD         # TMP117 #1 chip-side face (= floor thickness there)
Z_T1B = Z_T1F + P.PCB_T                         # TMP117 #1 back = strap slot floor
Z_SLOT1 = Z_T1B + P.STRAP_SLOT_W
T1_BACK = P.TMP1_WIRE_SIDE != "chip"            # TMP117 #1 re-soldered from the back: its joints sit in the slot's first 5 mm
Z_DIV0 = Z_T1B + (P.TMP1_BLOB_H + P.GAP if T1_BACK else 0.0)     # underside of the divider
TONGUE = (TX1 + e) - (TX0 + P.BLOB_STRIP + 0.5) if T1_BACK else (B_X1 - B_X0)   # widest strap tongue that fits
PLATE_T = 1.8                                   # bridge over the strap slot (v2: 1.3). 0.7 blind pocket under TMP117 #2's solder points
                                                # now leaves 1.1 mm (v2 left 0.6 = 3 sagging bridge layers over an 18 mm span)
Z_T2 = Z_SLOT1 + PLATE_T                        # TMP117 #2 PCB bottom
Z_G = Z_T2 + P.PCB_T - 0.4                      # groove floor (wires leave TMP117 #2's top side)
Z_TOP = Z_G + P.CABLE_CH_D + 0.6
Z_OVER_ICM = Z_ICM_TOP + 1.4 + P.GAP + P.BUNDLE_D / 2      # bundle centre crossing over the ICM's parts
Z_OVER_ICM3 = Z_ICM_TOP + 1.1 + P.GAP + P.BUNDLE_D / 2    # v4: hop 3 crosses at Y -3.5, where the tallest ICM part is Q2 (1.1)
Z_OVER_T2 = Z_T2 + P.PCB_T + P.ADA_PARTS_H + P.GAP + P.BUNDLE_D / 2
MAX_YC = MAX_DY
REPORT = {}


def _boards():
    icm = T.ada_board("icm20649", name="ICM-20649").place(T.xf((IX0, P.ADA_L / 2, Z_ICM), rot=-90))
    mx = T.max30102().place(T.xf((MAX_X1, MAX_YC + P.MAX_L / 2, Z_MB), rot=-90, flip=True))
    t1 = T.ada_board("tmp117", sockets=not P.TMP1_SOCKETS_REMOVED, wire_side="top" if P.TMP1_WIRE_SIDE == "chip" else "bottom",
                     blob_h=P.TMP1_BLOB_H, name="TMP117 #1 (skin)", tab_wires=P.TMP1_GND_AT_TABS).place(T.xf((TX0, -P.ADA_L / 2, Z_T1B), rot=90, flip=True))
    t2 = T.ada_board("tmp117", name="TMP117 #2 (reference)").place(T.xf((TX1, -P.ADA_L / 2, Z_T2), rot=90))
    return icm, mx, t1, t2


def _foot(m, margin):
    """XY bounding rectangle of a placed solid, grown by margin."""
    b = m.bounding_box()
    return b[0] - margin, b[1] - margin, b[3] + margin, b[4] + margin


def build():
    R = P.SKIN_R_TOP
    icm, mx, t1, t2 = _boards()
    add, cut = [], []
    # ---- shell: floor + side walls round stack A and the lane, hand wall low (the ICM overhangs it)
    body = rbox(0, -W / 2, 0, L, W / 2, Z_WALL_A, P.CORNER_R)
    body = body - box(P.WALL, -HB, P.FLOOR, L1_X1, HB, 99)                    # stack A + lane cavity
    body = body - box(-1, -W, Z_ICM - 0.5, P.WALL + 0.01, W, 99)              # low hand wall
    body = body - box(L1_X1 - 0.01, -W, Z_T1F, L + 1, W, 99)                  # everything from the divider on is built below
    # ---- MAX30102 seat: solid block up to the PCB face, parts relief, rim on 3 sides (pad edge open to the lane)
    my0, my1 = MAX_YC - P.MAX_L / 2 - e, MAX_YC + P.MAX_L / 2 + e
    add.append(box(MAX_X0 - e - P.MAX_RIM, my0 - P.MAX_RIM, 0, MAX_X1 - P.MAX_BLOB_STRIP - 0.3, my1 + P.MAX_RIM, Z_MF))
    rim = box(MAX_X0 - e - P.MAX_RIM, my0 - P.MAX_RIM, 0, MAX_X1 + e, my1 + P.MAX_RIM, Z_MB - 0.2) - \
        box(MAX_X0 - e, my0, -1, MAX_X1 + 5, my1, 99)
    add.append(rim)
    def lrect(x0, y0, x1, y1, z0, z1):                                        # rectangle in MAX-board coordinates -> island box
        a, b = mx.loc((x0, y0, 0)), mx.loc((x1, y1, 0))
        return box(a[0], a[1], z0, b[0], b[1], z1)
    # relief under the sensor-side parts (they cover almost the whole face: photo 73fbbcdb).  The board rests on
    # a 0.5 mm ledge along its VIN end and on two solid corner pads under its holes (the only part-free areas).
    relief = lrect(0.5, P.MAX_BLOB_STRIP - 0.25, P.MAX_L + e, P.MAX_W + e, P.POCKET_FLOOR_MIN, Z_MF + 0.01)
    pads = union([lrect(-e, 11.0, 2.7, P.MAX_W + e, 0, Z_MF), lrect(P.MAX_L - 2.7, 11.0, P.MAX_L + e, P.MAX_W + e, 0, Z_MF),
                  lrect(P.MAX_L - 2.5, 8.9, P.MAX_L + e, 11.0, 0, Z_MF)])
    cut.append(relief - pads)
    for k in ("h0", "h1"):                                                    # blind sockets for the two metal pins
        h = mx.pt(k)
        cut.append(cyl(h[0], h[1], Z_MF - P.MAX_PIN_SOCKET_DEPTH, Z_MF + 0.01, P.MAX_PIN_SOCKET_D, seg=16))
    # ---- ICM-20649: 3 locating pins + 1 rest
    posts = []
    for hx, hy in P.ADA_HOLES:
        p = icm.loc((hx, hy, 0))
        over_max = p[0] + 1.7 + e > MAX_X0 - e and my0 - 1.7 - e < p[1] < my1 + 1.7 + e    # a full post would hit the MAX board
        if over_max and p[0] > MAX_X0:
            posts.append(box(p[0] - 1.6, my1 + P.MAX_RIM + 0.05, 0, p[0] + 1.6, HB, Z_ICM))      # rest instead of a pin
        elif over_max:
            posts.append(box(0, p[1] - 1.6, 0, MAX_X0 - e - P.MAX_RIM + 0.01, p[1] + 1.6, Z_ICM))  # rest on the hand side of the MAX seat
        else:
            posts.append(locating_post(p[0], p[1], Z_ICM, P.ADA_HOLE_D, base_d=3.4))
    add += posts
    # ---- divider (strap-slot hand wall, plate support) standing on two legs so TMP117 #1's pad edge passes under it
    add.append(box(L1_X1, -W / 2, Z_DIV0, B_X0, W / 2, Z_T2 + 0.8))
    for s in (-1, 1):
        add.append(box(L1_X1, s * 9.2, 0, B_X0, s * W / 2, Z_DIV0 + 0.01))
    # ---- elbow block: strap-slot elbow wall, plate support, carries the exit groove
    add.append(box(B_X1, -W / 2, 0, L, W / 2, Z_TOP))
    # ---- plate over the strap slot + low end walls + 2 pins for TMP117 #2
    plate = box(B_X0 - 0.01, -W / 2, Z_SLOT1, B_X1 + 0.01, W / 2, Z_T2)
    add.append(plate)
    for s in (-1, 1):
        add.append(box(B_X0, s * HB, Z_T2 - 0.01, B_X1, s * W / 2, Z_T2 + 1.4))
    for hx, hy in (P.ADA_HOLES[1], P.ADA_HOLES[2]):
        p = t2.loc((hx, hy, 0))
        add.append(locating_post(p[0], p[1], Z_T2, P.ADA_HOLE_D, base_d=3.4) ^ box(p[0] - 3, p[1] - 3, Z_SLOT1 + 0.01, p[0] + 3, p[1] + 3, 99))
    # ---- TMP117 #1 floor (0.6) with one side stop; it slides in sideways through the strap slot
    add.append(box(B_X0 - 0.01, -W / 2, 0, B_X1 + 0.01, W / 2, Z_T1F))
    for xa, xb in ((TX0 + 0.3, TX0 + 3.3), (TX1 - 3.3, TX1 - 0.3)):          # two corner stops (v2: one in the middle, exactly where
        add.append(box(xa, -HB - 0.8, 0, xb, -HB, Z_T1F + 1.3))              # the new short-end GND wires leave)
    body = body + union(add)
    # blind relief in the plate under TMP117 #2's solder points (a through hole would spoil the bridge)
    sx0, sy0, sx1, sy1 = _foot(t2.part("solder"), 0.5)
    cut.append(box(sx0, sy0, Z_T2 - 0.7, sx1, sy1, Z_T2 + 0.01))
    # ---- exit groove along the elbow block (top-open, toward +Y) + flared exit through the +Y face + strain post
    cut.append(box(G_XC - G_W / 2, -HB + 2.0, Z_G, G_XC + G_W / 2, W, 99))
    cut.append(box(B_X1 - 0.01, -8.6, Z_T2 + P.PCB_T - 0.2, G_XC, 8.6, 99))                    # TMP117 #2's glue overhang
    col, ec, xo = flared_exit(0, P.WALL, 0, Z_G, z_top=Z_TOP)

    def turn(m):
        return m.rotate([0, 0, 90]).translate([G_XC, W / 2 - P.WALL, 0])
    body = body + (turn(col) ^ box(B_X1, -W, 0, L, 2 * W, 99))      # (the strain post for this hop is on the air island)
    cut.append(turn(ec))
    lips = [_lip(np.array([G_XC, y]), np.array([0.0, 1.0]), sd, G_W, Z_TOP) for y, sd in ((-4.0, -1), (4.5, -1), (10.5, -1))]
    # ---- hand-end tie post (wrap the pod bundle once round it)
    body = body + tie_post(0, -HB + 5.0, -1, z_top=3.0)
    # ---- v3 wire room on every edge (notches, not bigger pockets)
    for s in (-1, 1):
        # ICM short ends: notch in each side wall at its socket, from just under the board to the top
        cut.append(box(IX0 + P.STEMMA_Y[0] - 1.0, s * (HB - 0.01), Z_ICM - 0.4, IX0 + P.STEMMA_Y[1] + 1.0, s * (W / 2 + 1), 99))
        # lane: a window through each side wall (wires can enter / leave the lane sideways)
        cut.append(box(LANE_XC - 1.7, s * (HB - 0.01), P.FLOOR + 0.6, LANE_XC + 1.7, s * (W / 2 + 1), P.FLOOR + 3.0))
    # TMP117 #1 elbow edge: relief channel along the foot of the elbow block, open at both sides
    cut.append(box(B_X1 - 0.01, -W, Z_T1F, B_X1 + 1.6, W, Z_T1B + 0.5))
    # divider underside: two notches so wires on the back of TMP117 #1 can pass from the strap slot into the lane
    for s in (-1, 1):
        cut.append(box(L1_X1 - 0.01, s * 6.0 - 1.5, Z_DIV0 - 0.01, B_X0 + 0.01, s * 6.0 + 1.5, Z_DIV0 + 1.3))
    body = body - union(cut) + union(lips)

    skirt, arm = skin_skirt(0, L, W, R)
    fl, holes = flanges(0, L, W, R)
    body = union([body, fl] + ([skirt] if skirt is not None else [])) - holes
    # v6: notch in the +Y stitch flange where the air island's strain-post block sits (it overlapped the FLAT flange in v4 too;
    # the v6 twin now checks printed part against printed part).  Nothing else in the island changes.
    body = body - box(G_XC - 7.0 - 4.2, W / 2 + 0.01, -40, G_XC - 7.0 + 4.2, W / 2 + P.FLANGE_W + 2, 6.0)
    # ---- skin-side openings (cut through floor AND skirt)
    thru = []
    ch = mx.pt("chip")
    wl, ww = P.MAX_WIN_W, P.MAX_WIN_L                                         # chip long axis lies along Y here
    win = cbox(ch[0], ch[1], -20, wl, ww, Z_MF + 0.01)
    thru.append(win)
    bx0, by0, bx1, by1 = _foot(mx.part("blob"), 0.3)                          # MAX glue strip: open to the skin
    thru.append(box(bx0, by0, -20, bx1, by1, Z_MF + 0.01))
    for k, m in t1.solids:                                                    # TMP117 #1: every chip-side part gets a window
        if k in ("chip", "smd", "socket", "blob", "solder") and m.bounding_box()[2] < Z_T1F - 0.01:
            mg = P.TMP_WIN_MARGIN if k == "chip" else 0.4
            x0, y0, x1, y1 = _foot(m, mg)
            if max(abs(y0), abs(y1)) > HB:                                    # short-end joints: open right out through the side
                y0, y1 = (y0, W) if y1 > 0 else (-W, y1)                      # (also notches the stitch flange there)
                thru.append(box(x0 - P.CABLE_BEND_R - 0.5, HB if y1 > 0 else -W, -20, x1, W if y1 > 0 else -HB, Z_T1B))  # room to turn
                thru.append(box(x0, HB if y1 > 0 else -W, -20, x1, W if y1 > 0 else -HB, Z_T1B))
            thru.append(box(x0, y0, -20, x1, y1, Z_T1F + 0.01))
    # lane floor: thin where the MAX -> TMP117 #1 wires cross it
    thru.append(box(A_X1 - 0.3, -7.0, P.POCKET_FLOOR_MIN, B_X0 - 1.0, 9.5, P.FLOOR + 0.01))
    body = body - union(thru)
    body = body - box(B_X0 - 0.01, -W, Z_T1B, B_X1 + 0.01, W, Z_SLOT1)        # strap slot stays clear, both sides
    # ---- light ring round the MAX window (pressed into the skin)
    ring = cbox(ch[0], ch[1], -P.RING_H, wl + 2 * P.RING_W, ww + 2 * P.RING_W, 0.3) - cbox(ch[0], ch[1], -20, wl, ww, 20)
    if P.SKIN_CURVE:                                                          # flat-bottom variant: no ring, the flat face is the seal
        body = body + (ring - box(bx0, by0, -20, bx1, by1, 20))              # (and the part can lie flat on the bed); the ring never
                                                                              # closes the glue-strip opening
    REPORT.update(max_pcb_face=round(Z_MF, 2), max_chip_behind_skin=P.MAX_CHIP_RECESS, icm_seat=round(Z_ICM, 2),
                  tmp1_face=round(Z_T1F, 2), slot=f"{Z_T1B:.1f}-{Z_SLOT1:.1f}", tmp2_seat=round(Z_T2, 2),
                  strap_tongue_max_width=round(TONGUE, 1), lane=f"{LANE_W} x {2 * HB:.0f} mm")
    return body


def twin():
    icm, mx, t1, t2 = _boards()
    lane_x = A_X1 + LANE_W / 2
    iw, mw, w1, w2 = icm.pt("pad"), mx.pt("wire"), t1.pt("wire"), t2.pt("pad")
    wires = [
        T.Wire("hop 2 DRV -> ICM, island part", [(-6.0, 1.0, iw[2]), (iw[0] - 0.5, 1.0, iw[2])], ends=["ICM-20649"]),
        T.Wire("hop 3 ICM -> MAX30102", [(iw[0] + 1.0, -3.5, Z_OVER_ICM3), (IX1 + 1.0, -3.5, Z_OVER_ICM3), (lane_x, -3.5, P.FLOOR + 1.6)],
               ends=["ICM-20649", "MAX30102"]),
        T.Wire("hop 4 MAX30102 -> TMP117 #1 (flat, 4 single wires)", [(mw[0] - 0.2, 1.0, 1.05), (w1[0] + 0.2, 0.5, w1[2] if T1_BACK else 1.05)], d=1.2,
               ends=["MAX30102", "TMP117 #1 (skin)"]),
        T.Wire("hop 5 TMP117 #1 -> #2", [(lane_x + 0.35, 4.0, P.FLOOR + 1.6), (lane_x + 0.35, 4.0, Z_OVER_T2), (w2[0] - 1.0, 4.0, Z_OVER_T2)],
               ends=["TMP117 #1 (skin)", "TMP117 #2 (reference)"]),
        T.Wire("hop 6 TMP117 #2 -> SHTC3, heart-island part", [(G_XC, 5.0, Z_G + P.BUNDLE_D / 2), (G_XC, W / 2 + P.EXIT_COLLAR + 3.0, Z_G + P.BUNDLE_D / 2)],
               ends=["TMP117 #2 (reference)"]),
    ]
    if P.TMP1_GND_AT_TABS:      # GND tails from the tab pads: out over the short end, back along the outside, in through the lane window
        zo = P.FLOOR + 1.8
        for i, k in enumerate(("tab0", "tab1")):
            p = t1.pt(k)
            s = 1 if p[1] > 0 else -1
            wires.append(T.Wire(f"TMP117 #1 GND tail, short end {'+Y' if s > 0 else '-Y'} (1 wire)",
                                [(p[0], p[1], 0.2), (p[0], s * (W / 2 + 2.6), zo), (LANE_XC, s * (W / 2 + 2.6), zo), (LANE_XC, s * 9.5, zo)],
                                d=P.WIRE_D, ends=["TMP117 #1 (skin)"]))
    return [icm, mx, t1, t2], wires


SECTION_Y = MAX_YC
