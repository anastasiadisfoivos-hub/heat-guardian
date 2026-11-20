"""v6.1 SKIN ISLAND (replaces the v4 heart island): the sensor end of the chain, laid out round your MEASURED wires.
Nothing stacked except TMP117 #2 over #1 (through the 3 mm neoprene, as you asked).  Seen from above, hand end left:

   +Y  [ front wall (low) ............ hop 6 leaves straight through a big top-open opening -> air island ..............]
       [ BAY (the labyrinth): hop 3 and hop 4 each lie in ONE wide C (radius >= WIRE_BEND_R) round a low tongue wall;     ]
       [ hop 2 comes in along the ICM's pad row from the hand wall; hop 5 is a small upright C at the TMP pad edge          ]
       [ ICM-20649 (pads -> bay) | MAX30102 sensor down (pads -> bay) | TMP117 #1 chip down, slot, TMP117 #2 chip up        ]
   -Y  [ back wall: the strap tongue enters the slot from here (blind slot)                                                ]

A C between two neighbouring pad rows takes ANY length from the straight chord to more than a half circle, so hop 3 (51) and
hop 4 (50) fit exactly as they are: the C just gets rounder.  Glue at each C's apex and at each pad row."""
import math
import numpy as np
from geo import box, cbox, cyl, rbox, union
import params as P
import twin as T
from common import skin_skirt, flanges, locating_post, leadin
from manifold3d import Manifold

c = P.CLEAR
cb = P.CLEAR + getattr(P, "BOARD_FIT_PLUS", 0.0)     # v6.9: board-locating walls / pockets (owner: v6.8 seats too tight) 0.3 -> 0.7
PSH = getattr(P, "PIN_SHRINK_ISLAND", 0.0)           # v6.9: printed pins into board holes 0.3 thinner (2.1 -> 1.8)
MC = cb + P.MAX_POCKET_LOOSE                         # v6.2: MAX pocket clearance (+0.2 per side after the tight dry fit; v6.9 +0.4 more)
# ---------------------------------------------------------------- plan (interior coordinates: x from the hand wall, y from the back wall)
ICM_X0 = c                                           # (v6.9: the hand wall gets a 0.4 rebate at the ICM instead: hop 2 keeps its length)
ICM_X1 = ICM_X0 + P.ADA_L
G1 = max(2.6, cb + P.RIB_T + MC)                     # ICM | MAX: shelf hand rib (cb off the ICM) + the MAX pocket clearance
MAX_X0 = ICM_X1 + G1
MAX_X1 = MAX_X0 + P.MAX_L
RIBH = P.MIN_T + P.SHELF_REBATE                      # v7.0: hand-side stack wall 2.4: 1.2 left beside the 1.2 shelf rebate (v6.9: 0.9)
RIBE = 1.6                                           # v7.0: elbow-side stack wall (v6.9: 1.2; it bridges the GND-tail channel)
G2 = max(6.0 + P.MAX_POCKET_LOOSE, P.MAX_RIM + MC + cb + RIBH + 3.2)   # MAX | TMP stack: 1.0 wall + GND-tail channel 3.2 + stack side wall
TX0 = MAX_X1 + G2
TX1 = TX0 + P.TMP_L
G3 = 6.4                                             # elbow-end GND tail
XI = TX1 + G3
Y_E = cb + P.ADA_W                                    # the common pad-edge line (ICM, MAX, TMP117 pads all face +Y, the bay)
MAX_Y0 = Y_E - P.MAX_W

# ---------------------------------------------------------------- heights
Z_ICM = P.FLOOR + 0.6 + P.GAP                        # ICM PCB bottom (its solder points are underneath)
Z_MF_OPT = P.MAX_CHIP_RECESS + P.MAX_COMP_H          # where the MAX face would sit with low joints (v6.1: 2.1)
# v6.2: the existing joints + glue on the sensor side (BLOB_H) must clear the flush light-shield plate under them
BACK = P.MAX_WIRE_SIDE == "back"                     # v6.3: MAX wires re-soldered on the back: the sensor side is clean
Z_MF = Z_MF_OPT if BACK else max(Z_MF_OPT, P.MAX_SHIELD_T + P.MAX_BLOB_H + P.MAX_BLOB_CLEAR)  # MAX PCB sensor face (first pass)


def skin_z(yp):
    """z of the skin surface at part-frame y (0 on the flat set; the wrist curve on the curved set)"""
    if not P.SKIN_CURVE:
        return 0.0
    R = P.SKIN_R_TOP
    return -R + math.sqrt(max(R * R - yp * yp, 0.0))

Z_MB = Z_MF + P.MAX_PCB_T
Z_T1F = P.TMP_CHIP_H - P.TMP_CHIP_PROUD              # TMP117 #1 chip-side face
Z_T1B = Z_T1F + P.PCB_T
Z_SLOT1 = Z_T1B + P.STRAP_SLOT_W
PLATE_T = P.TMP2_PLATE_T if P.AIR_ON_TOP else 1.8
Z_T2 = Z_SLOT1 + PLATE_T                             # plate top (TMP117 #2 seat)
if P.AIR_ON_TOP:
    # v6.6: TMP117 #2 faces chip DOWN like #1, straight above it (pads aligned: hop 5 goes straight up); its sockets drop into
    # pockets through the plate and stop 0.3 above the strap; parts elsewhere clear the plate by 0.3
    # v6.9: #2 keeps its soldered wires: joints + glue TMP2_BLOB_CHIP_H under it and its sockets sit in BLIND relief pockets
    # (a 0.4 floor stays over the strap slot so the plate's first layers bridge rib to rib) with 0.3 under them
    _zr = Z_SLOT1 + getattr(P, "TMP2_POCKET_FLOOR", 0.0) + getattr(P, "TMP2_RELIEF_GAP", 0.3)
    Z_T2F = max(_zr + P.STEMMA_H, _zr + getattr(P, "TMP2_BLOB_CHIP_H", P.BLOB_H), Z_T2 + 0.3 + 1.4)   # #2 chip-side face
    Z_T2BK = Z_T2F + P.PCB_T                                                # #2 back face (its joints + glue on top)
    Z_T2CH = Z_T2F - P.TMP_CHIP_H                                           # #2 chip face: lands on the chip rest
    Z_SB = Z_T2BK + 0.6 + P.AIR_GAP_OVER_T2                                 # SHTC3 board bottom
    Z_SH_W = Z_SB + P.PCB_T + P.BLOB_H / 2                                  # SHTC3 joints (component side, on top)
BAY_FLOOR = P.BAY_FLOOR  # v7.0: 1.2 (v6: 0.8)                                      # bay floor (4 layers): the bundles sit low; glue recesses leave 0.6
Z_BUN = BAY_FLOOR + P.BUNDLE_D / 2
Z_WALL = 5.0                                         # low outer walls (the bay is open from above)
Z_ICM_W = Z_ICM + P.PCB_T + P.BLOB_H / 2             # wires leave the ICM's top-side joints here
Z_T2_W = (Z_T2F - getattr(P, "TMP2_BLOB_CHIP_H", P.BLOB_H) / 2) if P.AIR_ON_TOP else (Z_T2 + P.PCB_T + P.BLOB_H / 2)

# pad-group fronts (where each bundle meets a pad row)
Y0 = Y_E + 1.5
A_ICM = (ICM_X0 + P.ADA_L / 2, Y0, Z_ICM_W)
Z_MAX_W = Z_MB + P.MAX_BLOB_H / 2 if BACK else Z_BUN   # v6.3: the MAX wires leave its back-side joints toward the bay
A_MAX = (MAX_X0 + P.MAX_L / 2, Y0, Z_MAX_W)
A_TMP = (TX0 + P.TMP_L / 2, Y0, Z_BUN)
TAIL_ICM = 12.7 / 2 / 2 + 1.5                        # average fan per wire from the bundle to a pad (half of the half-span) + joint
TAIL_MAX = 15.24 / 2 / 2 + 1.5
TAIL_TMP = 12.7 / 2 / 2 + 1.5


def c_arc(a, b, s, n=40):
    """Circular C in plan from a to b (both on y = a[1]), bulging +Y, of length s.  -> (points, R, apex_y, half-angle)."""
    d = b[0] - a[0]
    s = math.sqrt(max(s * s - (b[2] - a[2]) ** 2, d * d * 1.0002))   # the C ramps between the two pad heights: plan length
    k = s / d
    lo, hi = 1e-4, math.pi - 1e-3                    # solve x / sin x = k  (x = half the turned angle)
    if k <= 1.0:
        k = 1.0001
    for _ in range(80):
        m = (lo + hi) / 2
        if m / math.sin(m) < k:
            lo = m
        else:
            hi = m
    x = (lo + hi) / 2
    R = d / (2 * math.sin(x))
    cx, cy = (a[0] + b[0]) / 2, a[1] - R * math.cos(x)
    pts = []
    for i in range(n + 1):
        t = math.pi / 2 + x - 2 * x * i / n
        z = a[2] + (b[2] - a[2]) * i / n
        pts.append((cx + R * math.cos(t), cy + R * math.sin(t), z))
    return pts, R, cy + R, x


S3 = P.HOP3_LEN[0] - TAIL_ICM - TAIL_MAX             # length the hop-3 C has to take up
S4 = P.HOP4_LEN[0] - TAIL_MAX - TAIL_TMP
ARC3, R3, APEX3, X3 = c_arc(A_ICM, A_MAX, S3)
ARC4, R4, APEX4, X4 = c_arc(A_MAX, A_TMP, S4)
YI = max(APEX3, APEX4) + P.BUNDLE_D / 2 + 1.0
W = YI + 2 * P.WALL
L = XI + 2 * P.WALL
OFF = np.array([-XI / 2, -YI / 2, 0.0])
if BACK:
    # v6.4: clean sensor side -> drop the board until the optical chip is MAX_CHIP_PROUD past the LOCAL skin surface; the taller
    # factory parts get their own pockets (blind where a 0.4 floor fits under them, else through the skin face)
    CHIP_YP = Y_E - (P.MAX_W / 2 + P.MAX_CHIP_Y) + OFF[1]
    Z_SK = skin_z(CHIP_YP)
    Z_MF = Z_SK + P.MAX_CHIP_H - P.MAX_CHIP_PROUD
    Z_MB = Z_MF + P.MAX_PCB_T
    Z_MAX_W = Z_MB + P.MAX_BLOB_H / 2
    A_MAX = (MAX_X0 + P.MAX_L / 2, Y0, Z_MAX_W)
    ARC3, R3, APEX3, X3 = c_arc(A_ICM, A_MAX, S3)
    ARC4, R4, APEX4, X4 = c_arc(A_MAX, A_TMP, S4)
    assert max(APEX3, APEX4) + P.BUNDLE_D / 2 + 0.9 <= YI
else:
    Z_SK = 0.0
Y_H2 = Y_E + P.BLOB_OVER + c + P.BUNDLE_D / 2        # hop 2 runs along the ICM's pad row
X_H6 = A_TMP[0] + 3.0                                 # hop 6 leaves TMP117 #2 straight toward +Y
# hop 5: upright C at the TMP pad edge, as a flat 4-wire ribbon (each wire bends on its own)
Z5_A, Z5_B = BAY_FLOOR + 0.6, Z_T2_W
R5 = (Z5_B - Z5_A) / 2
X_H5 = A_TMP[0] - 3.0
OPEN_HAND = (Y_H2 - P.OPEN_W / 2, min(Y_H2 + P.OPEN_W / 2, YI))
OPEN_FRONT = (X_H6 - P.OPEN_W / 2, X_H6 + P.OPEN_W / 2)
TONGUES = [((A_ICM[0] + A_MAX[0]) / 2, APEX3), ((A_MAX[0] + A_TMP[0]) / 2, APEX4)]
GLUE = [("skin: hop 3 apex", ((A_ICM[0] + A_MAX[0]) / 2 - 3, APEX3 - 2.2, (A_ICM[0] + A_MAX[0]) / 2 + 3, APEX3 + 0.8)),
        ("skin: hop 4 apex", ((A_MAX[0] + A_TMP[0]) / 2 - 3, APEX4 - 2.2, (A_MAX[0] + A_TMP[0]) / 2 + 3, APEX4 + 0.8)),
        ("skin: hop 2 entry", (0.4, Y_H2 - 1.6, 4.0, Y_H2 + 1.6))]
REPORT = {}


def _boards():
    icm = T.ada_board("icm20649", name="ICM-20649").place(T.xf((ICM_X1, Y_E, Z_ICM), rot=180))
    mx = T.max30102().place(T.xf((MAX_X0, Y_E, Z_MB), flip=True))
    t1 = T.ada_board("tmp117", sockets=not P.TMP1_SOCKETS_REMOVED, wire_side="top" if P.TMP1_WIRE_SIDE == "chip" else "bottom",
                     blob_h=P.TMP1_BLOB_H, name="TMP117 #1 (skin)", tab_wires=P.TMP1_GND_AT_TABS).place(T.xf((TX0, Y_E, Z_T1B), flip=True))
    if P.AIR_ON_TOP:      # v6.6: chip down, straight above #1 (same orientation, pads aligned)
        t2 = T.ada_board("tmp117", name="TMP117 #2 (reference)", blob_h=getattr(P, "TMP2_BLOB_CHIP_H", None),
                         back_blob_h=getattr(P, "TMP2_BLOB_BACK_H", None), hole_dx=getattr(P, "TMP2_HOLE_DX", None)).place(T.xf((TX0, Y_E, Z_T2BK), flip=True))
    else:
        t2 = T.ada_board("tmp117", name="TMP117 #2 (reference)").place(T.xf((TX1, Y_E, Z_T2), rot=180))
    return icm, mx, t1, t2


def _foot(m, mg):
    b = m.bounding_box()
    return b[0] - mg, b[1] - mg, b[3] + mg, b[4] + mg


def _rs_x(y0, y1, x0, x1, z0, z1, r):
    m = rbox(y0, z0, 0, y1, z1, abs(x1 - x0), r)
    M = np.array([[0, 0, 1.0, min(x0, x1)], [1.0, 0, 0, 0], [0, 1.0, 0, 0]])
    return m.transform(M)


def _rs_y(x0, x1, y0, y1, z0, z1, r):
    m = rbox(x0, z0, 0, x1, z1, abs(y1 - y0), r)
    return m.rotate([90, 0, 0]).translate([0, max(y0, y1), 0])


def openings():
    o = [_rs_x(OPEN_HAND[0], OPEN_HAND[1], -P.WALL - 3, 0.01, BAY_FLOOR, 99, P.OPEN_R)]
    if OPEN_FRONT is not None:
        o.append(_rs_y(OPEN_FRONT[0], OPEN_FRONT[1], YI - 0.01, YI + P.WALL + 3, BAY_FLOOR, 99, P.OPEN_R))
    return union(o)


def build():
    Rk = P.SKIN_R_TOP
    icm, mx, t1, t2 = _boards()
    body = rbox(-P.WALL, -P.WALL, 0, XI + P.WALL, YI + P.WALL, Z_WALL, P.CORNER_R)
    body = body - box(0, 0, P.FLOOR, XI, YI, 99)
    body = body - box(0, Y_E + 0.01, BAY_FLOOR, XI, YI, 99)                      # thin bay floor
    if cb > c:    # v6.9: top-open rebate in the hand wall along the ICM's edge: 0.7 clear (wall 1.5 -> 1.1 there)
        body = body - box(-min(cb - c, P.WALL - P.MIN_T), Y_E - P.ADA_W - cb + 1.2, Z_ICM - 0.3, 0.01, Y_E + 0.01, 99)   # v7.0: 0.3 deep, 1.2 wall stays
    add, cut = [], []
    # ---- ICM: four locating pins in its corner holes
    # v7.0: flat-topped bosses under all four holes, pins only in the two BACK holes (away from the pad row and its wires): the board
    # goes on with its wires attached, back edge first, without levering on anything
    for hx, hy in P.ADA_HOLES:
        p = icm.loc((hx, hy, 0))
        add.append(locating_post(p[0], p[1], Z_ICM, P.ADA_HOLE_D, base_d=3.6, shrink=PSH, pin=hy > 8, z_base=P.FLOOR - 0.01,
                                 label="ICM-20649 " + ("back pin" if hy > 8 else "front rest")))
    # ---- MAX30102 seat (v4 seat, turned: pad edge toward the bay, open there)
    # v6.2: board pocket +0.2 per side (MC); the joints + glue strip gets a straight-edged relief open to the skin side,
    # closed flush by the light-shield plate (or black tape) in a 0.6 recess - see shield_rect()
    my0 = MAX_Y0 - MC
    add.append(box(MAX_X0 - MC - P.MAX_RIM, my0 - P.MAX_RIM, 0, MAX_X1 + MC + P.MAX_RIM, Y_E + 0.01, Z_MF))
    add.append(box(MAX_X0 - MC - P.MAX_RIM, my0 - P.MAX_RIM, 0, MAX_X1 + MC + P.MAX_RIM, Y_E, Z_MB - 0.2)
               - box(MAX_X0 - MC, my0, -1, MAX_X1 + MC, Y_E + 5, 99))

    def lrect(x0, y0, x1, y1, z0, z1):
        a, b = mx.loc((x0, y0, 0)), mx.loc((x1, y1, 0))
        return box(a[0], a[1], z0, b[0], b[1], z1)
    z_rel = Z_MF - P.MAX_LOW_PARTS_H if BACK else max(P.MAX_SHIELD_T + P.POCKET_FLOOR_MIN, Z_MF - P.MAX_COMP_H - 0.3)
    relief = lrect(0.5, -0.01, P.MAX_L + MC, P.MAX_W + MC, z_rel, Z_MF + 0.01)                  # under the sensor-side parts
    if not BACK:
        cut.append(_blob_cut(mx))                                                               # v6.2: joints + glue open to the skin side
    pads = union([lrect(-MC, 11.0, 2.7, P.MAX_W + MC, 0, Z_MF), lrect(P.MAX_L - 2.7, 11.0, P.MAX_L + MC, P.MAX_W + MC, 0, Z_MF),
                  lrect(P.MAX_L - 2.5, 8.9, P.MAX_L + MC, 11.0, 0, Z_MF)])
    cut.append(relief - pads)
    cut.append(box(MAX_X0 - MC, my0, Z_MF, MAX_X1 + MC, Y_E + 0.01, 99))      # v7.0: the 1.2 floor never stands above the MAX face (curved set)
    for k in ("h0", "h1"):
        h = mx.pt(k)
        dep = min(P.MAX_PIN_SOCKET_DEPTH, Z_MF - skin_z(h[1] + OFF[1]) - P.MAX_BLIND_FLOOR_MIN)
        cut.append(cyl(h[0], h[1], Z_MF - dep, Z_MF + 0.01, P.MAX_PIN_SOCKET_D, seg=16))
    body = body - box(TX0 - cb, 0, Z_T1F, TX1 + cb, Y_E + 0.01, 99)              # TMP117 #1 sits on a 0.6 floor
    # ---- TMP stack: 0.6 floor under TMP117 #1, two side walls carry the plate over the strap slot, TMP117 #2 on two pins
    add.append(box(TX0 - cb - 0.01, 0, 0, TX1 + cb + 0.01, Y_E, Z_T1F))
    for xa, xb in ((TX0 - cb - RIBH, TX0 - cb), (TX1 + cb, TX1 + cb + RIBE)):
        add.append(box(xa, -0.01, 0, xb, Y_E - 2.0, Z_T2))
    # plate (bridge over the slot); v6.9: ends flush with the side-wall ends (v6.8: 1.5 mm further, a cantilever off the bridge)
    add.append(box(TX0 - cb - RIBH, -0.01, Z_SLOT1, TX1 + cb + RIBE, Y_E - getattr(P, "TMP2_PLATE_FRONT", 0.5), Z_T2))
    if P.AIR_ON_TOP:
        add += t2_supports(t2)    # v7.0: back blocks + pins (20.0 apart, owner), chip pedestal, front anti-tip rests
    else:
        for hx, hy in (P.ADA_HOLES[1], P.ADA_HOLES[2]):
            p = t2.loc((hx, hy, 0))
            add.append(locating_post(p[0], p[1], Z_T2, P.ADA_HOLE_D, base_d=3.4) ^ box(p[0] - 3, p[1] - 3, Z_SLOT1 + 0.01, p[0] + 3, p[1] + 3, 99))
    add.append(box(TX0 - cb - RIBH, -P.WALL, 0, TX1 + cb + RIBE, 0.01, Z_T2))   # back wall up to the plate behind the stack
    # ---- labyrinth tongues: low walls the two Cs wrap round
    for x, apex in TONGUES:
        add.append(box(x - P.LAB_WALL_T / 2, Y_E + 2.5, 0, x + P.LAB_WALL_T / 2, apex - 6.5, BAY_FLOOR + P.LAB_WALL_H))
    body = body + union(add) - union(cut)
    if P.AIR_ON_TOP:
        if P.TMP2_POCKET_FLOOR < PLATE_T - 1e-6:
            body = body - t2_relief()      # v6.9 blind relief pockets (v7.0: none - the plate is solid, #2 stands higher)
        # v6.6 hop-5 wire slot: full width at the two pad edges, floor to top, open from above, rounded ends
        body = body - rbox(TX0 - cb, Y_E - 0.01, -20, TX1 + cb, Y_E + P.HOP5_EDGE_GAP + 1.6, 99, P.OPEN_R)
        body = body - box(TX0 - cb, Y_E - 0.01, -20, TX1 + cb, Y_E + 1.0, 99)      # v7.0: square corners at the pad edge (the rounded ones left 0.05 mm cusps)
        # cage feet: 0.4 keyed recesses in the plate / back-wall top (v6.8: not with the SHTC3 shelf - the cage is not used)
        if not SHELF:
            body = body - union([box(x0 - 0.15, y0 - 0.15, Z_T2 - 0.4, x1 + 0.15, y1 + 0.15, Z_T2 + 0.01) for x0, y0, x1, y1 in cage_feet()])
    else:
        sx0, sy0, sx1, sy1 = _foot(t2.part("solder"), 0.5)
        body = body - box(sx0, sy0, Z_T2 - 0.7, sx1, sy1, Z_T2 + 0.01)
    # stack side walls: low notches for TMP117 #1's short-end GND tails
    for xa, xb in ((TX0 - cb - RIBH - 3.2, TX0 + 0.01), (TX1 - 0.01, TX1 + cb + RIBE + 3.2)):
        body = body - box(xa, Y_E - 13.6, -20, xb, Y_E + 0.01, Z_T1B + 0.4)      # tail channel, open to the skin like v4
    if cb > c:    # v6.9: a pillar under each side wall's front end (the wall bridged the tail channel from ONE end: 11.6 mm cantilever)
        for xa, xb in ((TX0 - cb - RIBH, TX0 - cb), (TX1 + cb, TX1 + cb + RIBE)):
            body = body + box(xa, Y_E - 4.3, 0, xb, Y_E - 2.3, Z_T1B + 1.0)
        # v7.0: tie TMP117 #1's 0.6 floor to those two pillars.  Its two front corner tabs hung on 1.35 mm necks between the joint
        # windows; now each is welded to a pillar that stands on the bed under a side wall (the GND tails pass outside the pillars)
        for xa, xb in ((TX0 - cb - 0.01, TX0 + 0.02), (TX1 - 0.02, TX1 + cb + 0.01)):
            body = body + box(xa, Y_E - 4.3, 0, xb, Y_E - 2.3, Z_T1F)
    # (v7.0: no glue recesses in the bay floor - they left 0.6 mm)
    body = body - openings()
    body = body - box(TX0 - cb, -P.WALL - 1, Z_T1B, TX1 + cb, Y_E - 2.5, Z_SLOT1)   # blind strap slot, open at the back wall
    hn = P.SLOT_HAUNCH    # v7.0: 45 deg haunches in the slot's two upper corners
    for xw, sg in ((TX0 - cb, 1), (TX1 + cb, -1)):
        body = body + Manifold.hull(box(xw - sg * 0.01, -P.WALL, Z_SLOT1 - hn, xw + sg * 0.01, Y_E - 2.5, Z_SLOT1 + 0.01)
                                    + box(xw - sg * 0.01, -P.WALL, Z_SLOT1 - 0.01, xw + sg * hn, Y_E - 2.5, Z_SLOT1 + 0.01))
    if SHELF:     # v6.8: seats for the drop-in SHTC3 shelf (back wall + hand rib + elbow rebate), elbow stops on #2's plate
        body = body + union(shelf_seats()) - shelf_rebate() - union(max_glue_wells())
        # v7.0 lead-ins: the MAX pocket's low elbow rim, and the SHTC3's elbow stops
        body = body - (leadin(MAX_X0 - MC, MAX_Y0 - MC, MAX_X1 + MC, Y_E, Z_MB - 0.2, 0.5, sides="X") - box(-99, -99, -9, MAX_X1 + MC, 999, 99))
        body = body - (leadin(X_HLIP, -5, X_STOP, Y_E - 4.6, Z_LIP, P.SEAT_CHAMFER, sides="X") ^ box(X_STOP - 1, SY0, 0, X_STOP + P.SHELF_LIP_T, Y_E - 4.6, 99))
    body = body.translate(list(OFF))
    skirt, arm = skin_skirt(-L / 2, L / 2, W, Rk)
    fl, holes = flanges(-L / 2, L / 2, W, Rk)
    body = union([body, fl] + ([skirt] if skirt is not None else [])) - holes
    if not P.AIR_ON_TOP:   # +Y stitch flange notched where the old side air island sat (gone in v6.6)
        xa = X_H6_EXIT + OFF[0]
        body = body - box(xa - 15.5, W / 2 + 0.01, -40, xa + 15.5, W / 2 + P.FLANGE_W + 2, 6.0)
    # ---- skin-side openings: MAX window (v6.2: plus the flush shield recess), TMP117 #1 chip window + windows under its chip-side parts
    thru = []
    ch = mx.pt("chip")
    WE = 0.04     # v6.9: window 0.02 wider per side so its edge never lands exactly on a part-pocket face (non-manifold edge)
    win = cbox(ch[0] + OFF[0], ch[1] + OFF[1], -20, P.MAX_WIN_L + WE, P.MAX_WIN_W + WE, Z_MF + 0.01)
    thru.append(win)
    for k, m in t1.solids:
        if k in ("chip", "smd", "socket", "blob", "solder") and m.bounding_box()[2] < Z_T1F - 0.01:
            mg = P.TMP_WIN_MARGIN if k == "chip" else 0.4
            x0, y0, x1, y1 = _foot(m, mg)
            thru.append(box(x0 + OFF[0], y0 + OFF[1], -20, x1 + OFF[0], y1 + OFF[1], Z_T1F + 0.01))
    if BACK:                                                    # v6.4: the part pockets reach into the skin skirt too
        thru += [pk.translate(list(OFF)) for _, pk, _ in part_pockets(mx)] + [pk.translate(list(OFF)) for pk in pocket_bridges(mx)]
    body = body - union(thru)
    if not BACK:
        body = body - _recess()                                                 # v6.2: flush recess for the light shield
    elif P.SKIN_CURVE:                                                          # v6.3: closed skin side, light-seal lip round the window
        ring = cbox(ch[0] + OFF[0], ch[1] + OFF[1], Z_SK - P.MAX_SEAL_LIP_H, P.MAX_WIN_L + WE + 2 * P.RING_W, P.MAX_WIN_W + WE + 2 * P.RING_W, 0.3) - \
            cbox(ch[0] + OFF[0], ch[1] + OFF[1], -20, P.MAX_WIN_L + WE, P.MAX_WIN_W + WE, 20)
        body = body + (ring - union([pk.translate(list(OFF)) for _, pk, _ in part_pockets(mx)] + [pk.translate(list(OFF)) for pk in pocket_bridges(mx)]))
    REPORT.update(interior=f"{XI:.1f} x {YI:.1f}", hop3_C=f"R {R3:.1f}, apex {APEX3 - Y0:.1f} into the bay",
                  hop4_C=f"R {R4:.1f}, apex {APEX4 - Y0:.1f}", hop5_C=(f"straight up round the pad edges, {H5_LEN:.1f} mm" if P.AIR_ON_TOP else f"R {R5:.1f} (flat ribbon)"), strap_tongue_max_width=round(P.TMP_L + 2 * cb, 1),
                  **({"hop6_loop": f"R {R6:.1f}", "tmp2": f"chip down {Z_T2F:.2f}-{Z_T2BK:.2f}, chip on its rest at {Z_T2CH:.2f}"} if P.AIR_ON_TOP else {}))
    body = body - openings().translate(list(OFF))
    # v7.0: a pillar left standing free between through pockets under the MAX (curved set) is not printable: keep the one real body
    pcs = sorted(body.decompose(), key=lambda q: -q.volume())
    assert all(q.volume() < 10.0 for q in pcs[1:]), "island_skin fell apart"
    return pcs[0]


def part_pockets(mx):
    """v6.4: one close pocket per tall sensor-side part (interior frame). -> [(label, pocket, through?)]"""
    out = []
    k = P.MAX_PART_CLEAR
    for lab, x0, y0, x1, y1, h in P.MAX_PARTS:
        if h <= P.MAX_LOW_PARTS_H:
            continue
        a, b = mx.loc((x0, y0, 0)), mx.loc((x1, y1, 0))
        X0, X1, Y0_, Y1_ = min(a[0], b[0]) - k, max(a[0], b[0]) + k, min(a[1], b[1]) - k, max(a[1], b[1]) + k
        zs = max(skin_z(Y0_ + OFF[1]), skin_z(Y1_ + OFF[1]), skin_z(0.0) if Y0_ + OFF[1] < 0 < Y1_ + OFF[1] else -99)
        zf = Z_MF - h - P.MAX_PART_GAP
        thru = zf - zs < P.MAX_BLIND_FLOOR_MIN - 1e-6
        out.append((lab, box(X0, Y0_, -20 if thru else zf, X1, Y1_, Z_MF + 0.01), thru))
    return out


def pocket_bridges(mx, wmin=1.2):
    """v6.9: the walls left between two neighbouring MAX part pockets (or a pocket and the window) thinner than 0.8 mm cannot be
    printed (0.1-0.6 slivers since v6.4): open the gap down to the shallower of the two floors.  Interior frame."""
    items = [(pk.bounding_box(), ) for _, pk, _ in part_pockets(mx)]
    wx0, wy0, wx1, wy1 = _win_rect()
    items.append(((wx0, wy0, -20.0, wx1, wy1, Z_MF + 0.01),))
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            A, B = items[i][0], items[j][0]
            zb = max(A[2], B[2])
            for ax in (0, 1):
                o = 1 - ax
                lo, hi = max(A[o], B[o]), min(A[o + 3], B[o + 3])
                if hi - lo <= 0:
                    continue
                g0, g1 = (A[ax + 3], B[ax]) if A[ax + 3] <= B[ax] else (B[ax + 3], A[ax])
                if 0 < g1 - g0 < wmin:
                    q = [0, 0, 0, 0]
                    q[ax], q[ax + 2], q[o], q[o + 2] = g0 - 0.01, g1 + 0.01, lo, hi
                    out.append(box(q[0], q[1], zb, q[2], q[3], Z_MF + 0.01))
    return out


def _blob_rect():
    """interior-frame rect of the MAX joints + glue strip, + MAX_BLOB_CLEAR (straight edges)"""
    k = P.MAX_BLOB_CLEAR
    return (MAX_X0 + 0.3 - k, Y_E - P.MAX_BLOB_STRIP - k, MAX_X1 - 0.3 + k, Y_E + P.BLOB_OVER + k)


def _blob_cut(mx=None):
    x0, y0, x1, y1 = _blob_rect()
    return box(x0, y0, -20, x1, y1, Z_MF + 0.01)


def _win_rect():
    ch = _boards()[1].pt("chip")
    return (ch[0] - P.MAX_WIN_L / 2, ch[1] - P.MAX_WIN_W / 2, ch[0] + P.MAX_WIN_L / 2, ch[1] + P.MAX_WIN_W / 2)


def shield_rect():
    """interior-frame recess for the light-shield plate: covers the joints relief and the window, + a ledge all round"""
    b, w, e = _blob_rect(), _win_rect(), P.MAX_SHIELD_LEDGE
    return (min(b[0], w[0]) - e, min(b[1], w[1]) - e, max(b[2], w[2]) + e, max(b[3], w[3]) + e)


def _recess(shrink=0.0, z0=-20.0):
    """part frame: the shield recess. Flat set: a 0.6 deep pocket. Curved set: a 0.6 shell that follows the skin curve, so the flat
    printed plate bends into it and ends flush with the curved underside."""
    from geo import cyl_x
    x0, y0, x1, y1 = shield_rect()
    pr = box(x0 + OFF[0] + shrink, y0 + OFF[1] + shrink, z0, x1 + OFF[0] - shrink, y1 + OFF[1] - shrink, 20)
    if not P.SKIN_CURVE:
        return pr ^ box(-200, -200, -20, 200, 200, P.MAX_SHIELD_T)
    R = P.SKIN_R_TOP
    return pr ^ cyl_x(-200, 200, 0, -R, 2 * (R + P.MAX_SHIELD_T))


def build_shield(in_place=True):
    """the 0.6 mm light-shield plate (max_shield.stl): solid except the optical window.  in_place -> island frame, skin side at z 0"""
    x0, y0, x1, y1 = shield_rect()
    f = P.MAX_SHIELD_FIT
    wx0, wy0, wx1, wy1 = _win_rect()
    win = box(wx0 + OFF[0], wy0 + OFF[1], -20, wx1 + OFF[0], wy1 + OFF[1], 20)
    if in_place and P.SKIN_CURVE:                     # as it sits in the curved set: bent to the skin curve
        from geo import cyl_x
        return _recess(f) - cyl_x(-200, 200, 0, -P.SKIN_R_TOP, 2 * P.SKIN_R_TOP) - win
    plate = (box(x0 + f, y0 + f, 0, x1 - f, y1 - f, P.MAX_SHIELD_T) - box(wx0, wy0, -1, wx1, wy1, 2)).translate(list(OFF))
    if not in_place:
        bb = plate.bounding_box()
        plate = plate.translate([-(bb[0] + bb[3]) / 2, -(bb[1] + bb[4]) / 2, 0])
    return plate


def _at(p):
    return (p[0] + OFF[0], p[1] + OFF[1], p[2])


def twin():
    def mv(b):
        M = b.M.copy()
        M[:, 3] += OFF
        return T.Placed(b.name, [(k, m.translate(list(OFF))) for k, m in b.solids], M, b._pts)
    icm, mx, t1, t2 = [mv(b) for b in _boards()]
    extra = [mv(_sht())] if SHELF else []
    raw = dict(r=0)
    wires = [
        T.Wire("hop 3 ICM -> MAX30102 (C in the bay)", [_at(p) for p in ARC3], ends=["ICM-20649", "MAX30102"], **raw),
        T.Wire("hop 4 MAX30102 -> TMP117 #1 (C in the bay)", [_at(p) for p in ARC4], ends=["MAX30102", "TMP117 #1 (skin)"], **raw),
        (T.Wire("hop 5 TMP117 #1 -> #2 (straight up at the pad edges, flat ribbon)", [_at(p) for p in H5_PTS], d=1.2, r=P.HOP5_BEND_R,
                ends=["TMP117 #1 (skin)", "TMP117 #2 (reference)"]) if P.AIR_ON_TOP else
         T.Wire("hop 5 TMP117 #1 -> #2 (upright C, flat ribbon)",
                [_at((X_H5, Y_E + 1.0 + R5 * math.sin(f), (Z5_A + Z5_B) / 2 - R5 * math.cos(f))) for f in np.linspace(0, math.pi, 30)],
                d=1.2, ends=["TMP117 #1 (skin)", "TMP117 #2 (reference)"], **raw)),
    ]
    if P.TMP1_GND_AT_TABS:
        for i, (xt, xo) in enumerate(((TX0 + 1.28, TX0 - cb - RIBH - 1.8), (TX1 - 1.28, TX1 + cb + RIBE + 1.8))):
            wires.append(T.Wire(f"TMP117 #1 GND tail, {'hand' if i == 0 else 'elbow'} end (1 wire)",
                                [_at((xt, Y_E - 8.89, Z_T1F - 0.2)), _at((xo, Y_E - 8.89, Z_T1F + 0.6)), _at((xo, Y_E + 2.5, Z_BUN))],
                                d=P.WIRE_D, r=P.WIRE_BEND_R_SINGLE, ends=["TMP117 #1 (skin)"]))
    return [icm, mx, t1, t2] + extra, wires


def pad_zones():
    z = []
    if BACK:      # v6.3: joints + glue on the MAX back: >= BLOB_H + 0.5 free over the pad strip, 5 mm pad room toward the bay
        z.append(("MAX30102 back-side joints + wire room", box(MAX_X0 + 0.3, Y_E - P.MAX_BLOB_STRIP - 0.5, Z_MB + 0.01, MAX_X1 - 0.3,
                                                              Y_E + P.PAD_ROOM, Z_MB + P.MAX_BACK_ROOM_H).translate(list(OFF))))
    for lab, x0, x1 in (("ICM-20649 pad row", ICM_X0 + 5.0, ICM_X0 + 20.4), ("MAX30102 pad row (bay side)", MAX_X0 + 1.0, MAX_X1 - 1.0),
                        ("TMP117 pad rows", TX0 + 5.0, TX0 + 20.4)):
        z.append((lab, box(x0, Y_E + c, BAY_FLOOR, x1, Y_E + P.PAD_ROOM, Z_WALL).translate(list(OFF))))
    if P.AIR_ON_TOP:  # v6.9: TMP117 #2 fitted with its wires soldered: joint relief, R4 wire exit, glue ring round the outline
        z += [(lab, m.translate(list(OFF))) for lab, m in t2_zones()]
    if SHELF:     # v6.8: the SHTC3's pad row faces the bay, over it: joints + glue + wire room in front of it
        z.append(("SHTC3 pad row (on the shelf, over the bay)", box(SX1 - 20.4, SY1 + c, Z_SHB + P.PCB_T + 0.01, SX1 - 5.0, SY1 + P.PAD_ROOM,
                                                                   Z_SHB + P.PCB_T + P.BLOB_H + 0.5).translate(list(OFF))))
    return z


H2_END = (ICM_X0 + 6.35 - 0.6, Y_H2, Z_ICM_W)
H6_START = (X_H6, Y_E + 1.0, Z_T2_W)


def h6_points(shift, z_end=None):
    """hop 6 inside the skin island: up off TMP117 #2's pads, ONE jog toward the hand end at Z ~10 (over the bay, clear of every
    pad room), out through the front opening.  shift = how far it jogs (takes up the spare length).  Interior coords."""
    z = Z_T2_W
    z1 = z if z_end is None else z_end
    yj = Y_E + 1.0 + P.WIRE_BEND_R
    xe = X_H6 - shift
    return [(X_H6, Y_E + 1.0, z), (X_H6, yj, (z + z1) / 2), (xe, yj, z1)]
SECTION_Y = Y_E - 8.89 + OFF[1]


def _h6_len(shift):
    import island_air as A
    pts = h6_points(shift, A.Z_ENT)
    xe = pts[-1][0]
    y_in = YI + P.WALL + P.GAP_AIR_MIN
    pts += [(xe, y_in - 1.0, A.Z_ENT), (xe, y_in + A.BU0 - 0.2, A.Z_ENT)]
    return T.Wire("h6", pts, r=P.WIRE_BEND_R).length


H6_TAILS = (12.7 / 4 + 1.5) + 4.0


def _solve_h6():
    target = P.HOP6_LEN[0] - P.HOP_SLACK - H6_TAILS
    lo, hi = 2 * P.WIRE_BEND_R + 0.05, 75.0
    if _h6_len(lo) >= target:
        return lo
    for _ in range(40):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if _h6_len(m) < target else (lo, m)
    return (lo + hi) / 2


if P.AIR_ON_TOP:
    # v6.6 hop 5: from #1's chip-side joints out past the pad edge, straight up, back in onto #2's chip-side joints (pads aligned)
    _yp, _yo = Y_E - P.ADA_PAD_Y, Y_E + P.HOP5_EDGE_GAP
    _za, _zb = Z_T1F - 0.5, Z_T2F - 0.5
    H5_PTS = [(X_H5, _yp, _za), (X_H5, _yo, _za), (X_H5, _yo, _zb), (X_H5, _yp, _zb)]
    H5_LEN = T.Wire("h5", H5_PTS, d=1.2, r=P.HOP5_BEND_R).length + 2 * 1.0           # + 1 mm into each joint
    # v6.6 hop 6: ONE loop (a C of > 180 deg, radius >= 8) standing in front of the stack, from #2's pads (below) up to the
    # SHTC3's pads (above, AIR_DX toward the elbow end); the loop length is solved so hop 6 uses exactly its 60 mm
    H6_TAILS = (12.7 / 4 + 1.5) + 4.0
    H6_A = np.array([X_H6, Y_E + 1.5, Z_T2_W])
    H6_B = np.array([X_H6 + P.AIR_DX, Y_E + 1.5, Z_SH_W])

    def c_arc3(a, b, s, n=60):
        """C of length s from a to b in the plane of (b - a) and +Y, bulging +Y"""
        dv = b - a
        D = float(np.linalg.norm(dv))
        u = dv / D
        w = np.array([0.0, 1.0, 0.0]) - u * u[1]
        w = w / np.linalg.norm(w)
        k = max(s / D, 1.0001)
        lo, hi = 1e-4, math.pi - 1e-4
        for _ in range(80):
            m = (lo + hi) / 2
            lo, hi = (m, hi) if m / math.sin(m) < k else (lo, m)
        x = (lo + hi) / 2
        Rr = D / (2 * math.sin(x))
        mid = (a + b) / 2
        pts = []
        for i in range(n + 1):
            t = math.pi / 2 + x - 2 * x * i / n
            q = -Rr * math.cos(x) + Rr * math.sin(t)
            pts.append(tuple(mid + u * (-Rr * math.cos(t)) + w * q))
        return pts, Rr
    H6_PTS, R6 = c_arc3(H6_A, H6_B, P.HOP6_LEN[0] - P.HOP_SLACK - H6_TAILS)
    H6_SHIFT = 0.0
    X_H6_EXIT = X_H6
    OPEN_FRONT = None
else:
    H6_SHIFT = _solve_h6()
    X_H6_EXIT = X_H6 - H6_SHIFT
    OPEN_FRONT = (X_H6_EXIT - P.OPEN_W / 2, X_H6_EXIT + P.OPEN_W / 2)


T2_SOCK_MG = 0.4 + getattr(P, "BOARD_FIT_PLUS", 0.0)     # v6.9: #2 socket pockets 0.4 -> 0.8 per side (fit)


def t2_blob_rect(k=0.0):
    """interior plan rect of #2's chip-side joints + glue (+k per side)"""
    b = [m.bounding_box() for kk, m in _boards()[3].solids if kk == "blob" and m.bounding_box()[2] < Z_T2F - 0.01][0]
    return b[0] - k, b[1] - k, b[3] + k, b[4] + k, b[2]


def t2_relief():
    """v6.9: BLIND pockets in the plate under #2's sockets (+0.8 per side) and under its chip-side joints + glue (+0.5 per side),
    floor TMP2_POCKET_FLOOR over the strap slot, TMP2_RELIEF_GAP under the parts; open toward the bay (hop-5 slot)"""
    zf = Z_SLOT1 + P.TMP2_POCKET_FLOOR
    out = []
    for k, m in _boards()[3].solids:
        if k == "socket" and m.bounding_box()[2] < Z_T2 + 0.3:
            x0, y0, x1, y1 = _foot(m, T2_SOCK_MG)
            out.append(box(x0, y0, zf, x1, y1, Z_T2 + 0.01))
    x0, y0, x1, y1, _ = t2_blob_rect(P.TMP2_RELIEF_CLEAR)
    out.append(box(x0, y0, zf, x1, y1 + 3, Z_T2 + 0.01))
    return union(out)


def t2_hole_x():
    """v7.0: #2's two back-hole centres along the board (local x): centred, TMP2_HOLE_DX apart (owner: 20.0; Adafruit file: 20.32)"""
    d = getattr(P, "TMP2_HOLE_DX", P.ADA_HOLE_DX)
    return (P.ADA_L / 2 - d / 2, P.ADA_L / 2 + d / 2)


def t2_supports(t2):
    """v7.0 TMP117 #2 seat on the solid plate (interior coords).  Nothing slender:
    - two BACK BLOCKS (4.4 wide, tied into the back wall, from the plate up to #2's chip-side face) each with one 1.8 pin;
    - a CHIP PEDESTAL: 1.8 x 1.8 at the chip face, flaring 45 deg down to the plate (the chip lies flat on it, as in v6.9);
    - two FRONT RESTS at the front corners, 0.15 under the board face: the board cannot be tipped forward when the pad edge is
      pressed (glue, wires), but the chip rest + back blocks alone set its height."""
    out = []
    w = P.TMP2_BLOCK_W / 2
    for hx in t2_hole_x():
        p = t2.loc((hx, P.ADA_HOLES[2][1], 0))
        xa, xb = (TX0 - cb, p[0] + w) if hx < P.ADA_L / 2 else (p[0] - w, TX1 + cb)      # out to the board's short edge line (+ cb)
        yf = p[1] + 1.5                                  # front face 1.5 past the pin axis: clear of #2's LED and sockets
        out.append(box(xa, -P.WALL, Z_T2 - 0.01, xb, yf, Z_T2F))
        out.append(locating_post(p[0], p[1], Z_T2F, P.ADA_HOLE_D, base_d=2 * w, shrink=PSH, z_base=Z_T2F - 0.5, label="TMP117 #2 back pin")
                   ^ box(xa, -P.WALL, 0, xb, yf, 99))
    ch = t2.part("chip").bounding_box()
    cx, cy = (ch[0] + ch[3]) / 2, (ch[1] + ch[4]) / 2
    s, h = P.TMP2_CHIP_REST, Z_T2CH - Z_T2
    out.append(Manifold.hull(cbox(cx, cy, Z_T2 - 0.01, s + 2 * h, s + 2 * h, Z_T2) + cbox(cx, cy, Z_T2CH - 0.01, s, s, Z_T2CH)))
    zr = Z_T2F - P.TMP2_FRONT_REST_GAP
    ya, yb = Y_E - 4.6, Y_E - P.TMP2_PLATE_FRONT
    out.append(box(TX0 - cb, ya, Z_T2 - 0.01, TX0 + 4.0, yb, zr))
    out.append(box(TX1 - 4.0, ya, Z_T2 - 0.01, TX1 + cb + RIBE, yb, zr))
    return out


SIDE_X0 = TX0 - cb - RIBH


def t2_zones():
    """v6.9 rule-2 zones for #2 (interior coords): must be free of printed parts and of other boards"""
    x0, y0, x1, y1, zb = t2_blob_rect()
    k = P.TMP2_RELIEF_GAP
    o = P.TMP2_OUTLINE_CLEAR
    ring = box(TX0 - o, Y_E - P.ADA_W - o, Z_T2F, TX1 + o, Y_E + o, Z_T2BK) - box(TX0, Y_E - P.ADA_W, Z_T2F - 1, TX1, Y_E, Z_T2BK + 1)
    return [("TMP117 #2 chip-side joints + glue relief (3.0 + 0.3)", box(x0 - k, y0 - k, zb - k, x1 + k, Y_E, Z_T2F - 0.01)),
            ("TMP117 #2 wire exit (R4 room, both sides)", box(x0, Y_E + c, zb - k, x1, Y_E + P.BLOB_OVER + P.TMP2_EXIT_R + 0.5,
                                                               Z_T2BK + P.TMP2_BLOB_BACK_H + 0.5)),
            ("TMP117 #2 back-side joints + glue (2.5 + 0.5 free)", box(x0, y0, Z_T2BK + 0.01, x1, Y_E + P.BLOB_OVER, Z_T2BK + P.TMP2_BLOB_BACK_H + 0.5)),
            (f"TMP117 #2 glue ring {o:.1f} round the outline", ring)]


def cage_feet():
    """v6.6: the SHTC3 cage's four feet (interior coords), all outside TMP117 #2's footprint: on the plate's end strips / back wall"""
    lx, ly = P.CAGE_LEG
    xs = (TX0 - c - lx, TX1 + c)
    ys = (-P.WALL + 0.2, Y_E - 0.6 - ly)
    return [(x, y, x + lx, y + ly) for x in xs for y in ys]


# ================================================================ v6.8: the SHTC3 on a drop-in SHELF over the MAX30102
# Owner: the SHTC3 sits on ONE upper floor shared with TMP117 #2 (same level, side by side), over the MAX area.  The shelf TOP is
# TMP117 #2's plate top (Z_T2); the shelf is a separate drop-in part (island_shelf.stl) because the MAX30102 (pins, pockets under it)
# can only go in from above - a shelf printed onto the island would close its seat.  It rests on three seats: the back wall (raised to
# the shelf underside, two locating pegs), a 1.2 rib at the hand end (in the ICM | MAX gap) and a rebate in the top of TMP117 #2's side
# wall.  Over the MAX's back-side joints + glue the shelf is cut away (the wire channel); the SHTC3 rides 1.0 mm above the shelf on four
# posts at its holes (pins through), sensor up, pads toward the bay, lips with vent slots on the back and hand sides, stops on #2's
# plate at the elbow side, open toward the bay for its wires (hop 6).
SHELF = P.AIR_ON_TOP and getattr(P, "SHTC3_SHELF", False)
if SHELF:
    Z_SH1 = Z_T2                                         # shelf top = TMP117 #2's plate top
    Z_SH0 = Z_SH1 - P.SHELF_T                            # shelf underside (= top of its seats)
    Z_SHB = Z_SH1 + P.SHELF_STANDOFF                     # SHTC3 board bottom
    Z_SHW = Z_SHB + P.PCB_T + P.BLOB_H / 2               # SHTC3 pad-row joints (component side, up)
    Z_LIP = Z_SH1 + P.SHELF_LIP_H
    X_STOP = TX0 - cb                                    # elbow stop inner face (TMP117 #1's pocket line)
    SX1 = X_STOP - P.SHTC3_FIT                           # SHTC3 board, elbow end
    SX0 = SX1 - P.ADA_L
    SY1 = Y_E                                            # pad edge on the common pad-edge line, toward the bay
    SY0 = SY1 - P.ADA_W
    X_HLIP = SX0 - P.SHTC3_FIT                           # hand lip inner face
    SIDE_X = TX0 - cb - RIBH                             # TMP117 #2 side wall, hand face
    XS0 = X_HLIP - P.SHELF_LIP_T                         # shelf outline
    XS1 = SIDE_X + P.SHELF_REBATE - P.SHELF_FIT
    YS0 = -P.WALL
    YS1 = Y_E - 0.5
    Y_SIDE1 = Y_E - 2.0                                  # side wall ends here (the plate alone beyond)
    RIB = (ICM_X1 + cb, ICM_X1 + cb + P.RIB_T)           # hand rib, in the ICM | MAX gap (v6.9: cb off the ICM, was 0.3)
    KEYS_X = (SX0 + 7.0, SX1 - 7.0)
    # MAX joints + glue (back side) and the wire channel cut out of the shelf over them (between the two front posts)
    MAX_J_TOP = Z_MB + P.MAX_BLOB_H
    CH = (SX1 - 22.86 + 1.7 + 0.5, Y_E - P.MAX_BLOB_STRIP - 0.5, SX1 - 2.54 - 1.7 - 0.5)

    def _sht():
        return T.ada_board("shtc3", name="SHTC3").place(T.xf((SX1, SY1, Z_SHB), rot=180))

    def _icm_sock():
        """the ICM's elbow-end STEMMA socket (stands 6.5 above the skin, under the shelf's hand corner) + GAP, plan rect"""
        bbs = [m.bounding_box() for k, m in _boards()[0].solids if k == "socket"]
        b = max(bbs, key=lambda q: q[3])
        return b[0] - P.GAP, b[1] - P.GAP, b[3] + P.GAP, b[4] + P.GAP, b[5]

    def _t2_pockets():
        """y ranges of TMP117 #2's socket pockets in the plate (the elbow stops stay out of them)"""
        t2 = _boards()[3]
        return [(m.bounding_box()[1] - T2_SOCK_MG - P.GAP, m.bounding_box()[4] + T2_SOCK_MG + P.GAP) for k, m in t2.solids
                if k == "socket" and m.bounding_box()[0] < TX0 + 8]

    def _segs(a, b, holes):
        """[a, b] minus the hole intervals -> list of (lo, hi), pieces < 1.5 dropped"""
        out = [(a, b)]
        for h0, h1 in holes:
            nxt = []
            for lo, hi in out:
                if h1 <= lo or h0 >= hi:
                    nxt.append((lo, hi))
                else:
                    if h0 > lo:
                        nxt.append((lo, h0))
                    if h1 < hi:
                        nxt.append((h1, hi))
            out = nxt
        return [(lo, hi) for lo, hi in out if hi - lo >= 1.5]

    def _vents(a, b, keep=()):
        """vent slot intervals along a lip from a to b (slot width / pitch SHELF_VENT), not within 1 mm of the keep positions"""
        w, p = P.SHELF_VENT
        out, t = [], a + 2.0
        while t + w <= b - 2.0:
            if all(abs(t + w / 2 - k) > w / 2 + 1.0 for k in keep):
                out.append((t, t + w))
            t += p
        return out

    Y_LEDGE = MAX_Y0 - MC - P.MAX_RIM + 0.01             # v7.0: the back wall is widened inward to the MAX pocket's back rim (a 4 mm ledge)
    KEY_Y = (0.6, 0.6 + P.SHELF_KEY[1])                  # keys stand on the ledge, inside the back wall line

    def shelf_seats():
        """island_skin additions (interior coords): back wall up to the shelf underside, widened inward into a ledge over the MAX
        area with 2 sturdy keys (v7.0), hand rib, elbow stops on #2's plate"""
        kx, ky, kh = P.SHELF_KEY
        add = [box(XS0 - 0.5, -P.WALL, 0, SIDE_X + 0.01, 0.0, Z_SH0),
               box(RIB[0], -0.01, 0, SIDE_X + 0.01, Y_LEDGE, Z_SH0),
               box(RIB[0], -0.01, 0, RIB[1], Y_SIDE1, Z_SH0)]
        for x in KEYS_X:
            add.append(box(x - kx / 2, KEY_Y[0], Z_SH0 - 0.01, x + kx / 2, KEY_Y[1], Z_SH0 + min(kh, P.SHELF_T)))
        for y0, y1 in _segs(SY0, SY1 - 4.6, _t2_pockets()):     # (the front rest of #2 carries on as the stop from Y_E - 4.6)
            add.append(box(X_STOP, y0, Z_T2 - 0.01, X_STOP + P.SHELF_LIP_T, y1, Z_LIP))
        return add

    def max_glue_wells():
        """v7.0: two glue wells at the MAX30102's back corners (over its two pin holes, far from the optical window): 3 x 1.3 notches
        in the back ledge from the board's back face up - the glue dot goes here and nowhere else on the MAX"""
        return [box(xa, MAX_Y0 - MC - 1.3, Z_MB - 0.2, xa + 3.2, MAX_Y0 - MC + 0.01, 99) for xa in (MAX_X0 - MC + 0.4, MAX_X1 + MC - 3.6)]

    def shelf_rebate():
        return box(SIDE_X - 0.01, -P.WALL - 1, Z_SH0, SIDE_X + P.SHELF_REBATE, Y_SIDE1, Z_T2 + 1)

    def build_shelf():
        """island_shelf.stl, interior coords (as it sits in the island): plate + lips + 4 posts with pins.  Prints plate-down, no supports."""
        f = P.SHELF_FIT
        kx, ky, kh = P.SHELF_KEY
        sx0, sy0, sx1, sy1, _ = _icm_sock()
        fp = box(XS0, YS0, 0, XS1, YS1, 50)                                                # plate footprint (tall): posts are clipped to it
        fp = fp - box(SIDE_X - f, Y_SIDE1 - f, -9, XS1 + 1, YS1 + 1, 99)                    # beside the rebate's end: stop at the side wall
        fp = fp - box(XS0 - 1, sy0, -9, sx1, sy1, 99)                                      # ICM socket corner
        fp = fp - box(CH[0], CH[1], -9, CH[2], YS1 + 1, 99)                                # wire channel over the MAX joints
        plate = fp ^ box(XS0 - 1, YS0 - 1, Z_SH0, XS1 + 1, YS1 + 1, Z_SH1)
        lips = [box(XS0, YS0, Z_SH1 - 0.01, XS1 - 0.6, 0.0, Z_LIP),                        # back lip (on the back wall)
                box(XS0, 0.0 - 0.01, Z_SH1 - 0.01, X_HLIP, YS1, Z_LIP)]                     # hand lip
        # v6.9: beside the ICM socket the hand lip would be only ~0.7 mm thick: drop it there (the other lip pieces locate the SHTC3)
        lips = union(lips) - box(XS0 - 1, sy0, -9, (X_HLIP + 0.01) if X_HLIP - sx1 < P.MIN_T else sx1, sy1, 99)
        vx = _vents(XS0, XS1 - 0.6, keep=KEYS_X)
        vy = _vents(0.0, YS1)
        # v6.9: vents cut right through the lips (v6.8 left a 0.3 mm skin on the inside: too thin to print, and it closed the vents)
        lips = lips - union([box(a, YS0 - 1, Z_SH1, b, 0.0 + 0.01, 99) for a, b in vx] +
                            [box(XS0 - 1, a, Z_SH1, X_HLIP + 0.01, b, 99) for a, b in vy])
        posts = []
        sht = _sht()
        for hx, hy in P.ADA_HOLES:     # v7.0: flat bosses under all four holes, pins only in the two BACK holes (lip side, away from the wires)
            q = sht.loc((hx, hy, 0))
            posts.append(locating_post(q[0], q[1], Z_SHB, P.ADA_HOLE_D, base_d=3.6, shrink=PSH, pin=hy > 8, z_base=Z_SH1 - 0.01,
                                       label="SHTC3 " + ("back pin" if hy > 8 else "front rest")) ^ fp)
        body = union([plate, lips] + posts)
        body = body - (leadin(X_HLIP, 0.0, X_STOP + 5, YS1 + 5, Z_LIP, P.SEAT_CHAMFER, sides="xy") - box(X_HLIP, 0.0, -9, 999, 999, 99))   # v7.0 lead-in, lips only
        for x in KEYS_X:     # v7.0: key holes right through the plate (key + SHELF_FIT per side): >= 1.5 of plate stays behind each hole
            body = body - box(x - kx / 2 - f, KEY_Y[0] - f, -9, x + kx / 2 + f, KEY_Y[1] + f, Z_SH1 + 0.01)
        ch = sht.pt("chip")
        keep = cbox(ch[0], ch[1], Z_SHB + P.PCB_T, P.SHTC3_OPEN, P.SHTC3_OPEN, 99)
        assert (body ^ keep).volume() < 1e-6, "something covers the SHTC3 opening"
        return body

    def c_arc_tilt(a, b, s, tilt_deg, n=60):
        """C of length s from a to b, bulging toward (0, cos t, sin t) (t = tilt up from flat over the bay)"""
        dv = b - a
        D = float(np.linalg.norm(dv))
        u = dv / D
        t = math.radians(tilt_deg)
        w = np.array([0.0, math.cos(t), math.sin(t)])
        w = w - u * (u @ w)
        w = w / np.linalg.norm(w)
        k = max(s / D, 1.0001)
        lo, hi = 1e-4, math.pi - 1e-4
        for _ in range(80):
            m = (lo + hi) / 2
            lo, hi = (m, hi) if m / math.sin(m) < k else (lo, m)
        x = (lo + hi) / 2
        Rr = D / (2 * math.sin(x))
        mid = (a + b) / 2
        pts = []
        for i in range(n + 1):
            tt = math.pi / 2 + x - 2 * x * i / n
            q = -Rr * math.cos(x) + Rr * math.sin(tt)
            pts.append(tuple(mid + u * (-Rr * math.cos(tt)) + w * q))
        return pts, Rr

    # hop 6 (60 mm): from TMP117 #2's pads (chip side, below #2) to the SHTC3's pads (on top, bay side), ONE C over the bay
    _sw = _sht().pt("wire")
    H6_A = np.array([X_H6, Y_E + 1.5, Z_T2_W])
    H6_B = np.array([_sw[0], Y_E + 1.5, Z_SHW])
    H6_PTS, R6 = c_arc_tilt(H6_A, H6_B, P.HOP6_LEN[0] - P.HOP_SLACK - H6_TAILS, P.H6_TILT)
