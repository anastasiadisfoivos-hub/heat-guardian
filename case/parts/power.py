"""v6.1 POWER POD (middle of the band): LiPo cell, DRV2605L on its coin-motor cup, HELP button.  Re-laid round your MEASURED
wires: hop 1 (XIAO -> DRV, 50-60) and hop 2 (DRV -> ICM, 45-60) together must span this pod, so it is short along the forearm
(34.6 mm inside) and the parts sit side by side across it.  Seen from above, hand end left, interior coordinates:

   +Y  [ LiPo cell, lead end at the HAND wall (leads straight out)                                           ]
       [ rib                                                                                                    ]
       [ LANE = the 5 mm pad room in front of the DRV's 6 pads: hop 1 in from the hand wall, hop 2 out of the elbow wall ]
       [ HELP button bay |  DRV2605L on the motor cup (6-pad row up, toward the lane)                          ]
   -Y  [                 |  5 mm pad room in front of the motor pads                                            ]

Nothing is stacked on a board.  Wires leave through big top-open openings (OPEN_W wide, floor to lid).  The lid carries the
switch pocket, plunger bore and finger dish."""
import math
import numpy as np
from manifold3d import Manifold
from geo import box, cbox, cyl, rbox, union
import params as P
import twin as T
from common import skin_skirt, flanges, locating_post

c = P.CLEAR

# ---------------------------------------------------------------- plan (interior coordinates)
BAT_LEN = P.BAT_L + 2 * P.BAT_CLEAR + P.BAT_LEN_MARGIN       # 33.1 cradle (v4 fit test)
BAT_WID = P.BAT_W + 2 * P.BAT_CLEAR                          # 18.1
BAT_X0 = P.BAT_LEAD_ROOM
BAT_X1 = BAT_X0 + BAT_LEN
XI = BAT_X1
DRV_Y0 = P.PAD_ROOM + c                                      # motor-pad edge (JP2), 5 mm pad room under it
DRV_Y1 = DRV_Y0 + P.DRV_S                                    # 6-pad edge (JP1), toward the lane
DRV_X1 = XI - c
DRV_X0 = DRV_X1 - P.DRV_S                                    # DRV at the elbow end: hop 2 short; hop 1 runs the lane to it
Y_H1 = DRV_Y1 + P.BLOB_OVER + c + P.BUNDLE_D / 2             # hop 1 / hop 2 bundle centre in the lane
LANE_Y1 = DRV_Y1 + P.PAD_ROOM
RIB_Y0 = max(Y_H1 + P.BUNDLE_D / 2 + c, LANE_Y1)
BAT_Y0 = RIB_Y0 + P.RIB_T
BAT_Y1 = BAT_Y0 + BAT_WID
YI = BAT_Y1
OX, OY = XI + 2 * P.WALL, YI + 2 * P.WALL
OFF = np.array([-XI / 2, -YI / 2, 0.0])
MOTOR_C = (DRV_X0 + P.DRV_S / 2, DRV_Y0 + P.DRV_S / 2)
CUP_D = P.MOTOR_D + 2 * c + 2.4
Y_BAT = BAT_Y0 + P.BAT_CLEAR + P.BAT_LEAD_CORNER            # leads leave the lead end at its LANE-side corner (flip the cell)
TUBE = P.BTN_POCKET / 2 + P.BTN_CAP_WALL
BTN_C = (0.8 + TUBE, Y_H1 - 8.4)                             # HELP bay beside the DRV, below the lane (sets the brain's crossing order)
Y_BTN = BTN_C[1]
assert BTN_C[0] + TUBE + 0.5 <= DRV_X0 - P.BLOB_OVER, "button pocket would touch the DRV"
assert BTN_C[1] + TUBE <= DRV_Y1 + P.BLOB_OVER

# ---------------------------------------------------------------- heights
Z_DRV = P.MOTOR_FLOOR + P.MOTOR_T + P.MOTOR_ADH + P.GAP      # DRV PCB bottom = motor cup rim
Z_DRV_TOP = Z_DRV + P.DRV_PCB_T + P.DRV_PARTS_H
Z_BAT_TOP = P.BAT_FLOOR + P.BAT_T
Z_BTN0 = P.FLOOR + P.BTN_JOINT_ROOM
Z_BTN1 = Z_BTN0 + P.BTN_BODY_H
Z_TIP = Z_BTN1 + P.BTN_PLUNGER
Z_TOP = Z_TIP + P.BTN_SINK
Z_LID0 = Z_TOP - P.LID_T
Z_WALL = Z_LID0
assert Z_LID0 - max(Z_BAT_TOP, Z_DRV_TOP) >= P.GAP + 0.3
Z_LANE = P.FLOOR + P.BUNDLE_D / 2
Z_BAT_LEAD = P.BAT_FLOOR + P.BAT_T / 2
Z_BTN_W = P.FLOOR + 1.3


def _span(ys):
    """merge OPEN_W-wide openings centred on ys into intervals, clamped to the interior"""
    iv = sorted([(y - P.OPEN_W / 2, y + P.OPEN_W / 2) for y in ys])
    out = [list(iv[0])]
    for a, b in iv[1:]:
        if a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(max(a, 0.0), min(b, YI)) for a, b in out]


OPEN_HAND = _span([Y_BTN, Y_H1, Y_BAT])                      # hand wall: button pair, hop 1, battery leads
OPEN_ELBOW = _span([Y_H1])                                   # elbow wall: hop 2
GLUE = [("power: hand-wall bundles", (0.4, Y_H1 - 1.6, BAT_X0 - 0.2 + 3.0, Y_H1 + 1.6)),
        ("power: lane at the DRV pads", (DRV_X0 - 6.0, Y_H1 - 1.6, DRV_X0 - 1.0, Y_H1 + 1.6)),
        ("power: elbow-wall bundle", (XI - 4.5, Y_H1 - 1.6, XI - 0.6, Y_H1 + 1.6))]
assert Z_LID0 - P.FLOOR >= P.WIRE_ROOM_H


def _rs(y0, y1, x0, x1, z0, z1, r):
    m = rbox(y0, z0, 0, y1, z1, abs(x1 - x0), r)
    M = np.array([[0, 0, 1.0, min(x0, x1)], [1.0, 0, 0, 0], [0, 1.0, 0, 0]])
    return m.transform(M)


def openings():
    """Top-open slots, OPEN_W (or merged) wide, floor to the wall top; lower corners R OPEN_R; the lid bridges the top."""
    cuts = [_rs(a, b, -P.WALL - 3, 0.01, P.FLOOR, 99, P.OPEN_R) for a, b in OPEN_HAND]
    cuts += [_rs(a, b, XI - 0.01, XI + P.WALL + 3, P.FLOOR, 99, P.OPEN_R) for a, b in OPEN_ELBOW]
    return union(cuts)


def strain_posts():
    out = []
    for x, s, ys in ((-P.WALL, -1, [OPEN_HAND[0][0] - 2.4]), (XI + P.WALL, 1, [OPEN_ELBOW[0][0] - 2.4])):
        for y in ys:
            if y < 2.0:
                continue
            out.append(box(x - s * 0.2, y - 1.6, 0, x + s * 2.6, y + 1.6, 2.0))
            out.append(cyl(x + s * 1.5, y, 1.99, 5.0, P.TIE_POST_D, seg=24))
    return union(out)


def build():
    Rk = P.SKIN_R_TOP
    outer = rbox(-P.WALL, -P.WALL, 0, XI + P.WALL, YI + P.WALL, Z_WALL, P.CORNER_R)
    body = outer - box(0, 0, P.FLOOR, XI, YI, 99)
    add, cut = [], []
    # battery cradle: thin floor, lane-side rib, end rib at the elbow wall side is the wall itself
    cut.append(box(BAT_X0, BAT_Y0, P.BAT_FLOOR, BAT_X1, BAT_Y1, P.FLOOR + 0.01))
    rib_z = P.BAT_FLOOR + 4.6
    add.append(box(BAT_X0 + 2.0, RIB_Y0, 0, XI, BAT_Y0, rib_z))
    # DRV: motor cup (= rest ring) + two locating pins in its two holes
    mc = MOTOR_C
    add.append(cyl(mc[0], mc[1], P.FLOOR - 0.01, Z_DRV, CUP_D))
    for hx, hy in P.DRV_HOLES:                                  # local (x, y) -> pod (DRV_X0 + y, DRV_Y1 - x)
        add.append(locating_post(DRV_X0 + hy, DRV_Y1 - hx, Z_DRV, P.DRV_HOLE_D, base_d=4.6, foot=1.2, z_base=P.FLOOR - 0.01, label="DRV2605L pin"))   # v7.0: flared foot, flat top
    bx, by = BTN_C
    add.append(box(bx - P.BTN_S / 2 + 0.6, by - P.BTN_BAR / 2, 0, bx + P.BTN_S / 2 - 0.6, by + P.BTN_BAR / 2, Z_BTN0))
    body = body - union(cut) + union(add)
    body = body - cyl(mc[0], mc[1], P.MOTOR_FLOOR, 99, P.MOTOR_D + 2 * c)
    body = body - cyl(mc[0], mc[1], Z_DRV - 0.3, Z_DRV + 0.01, P.MOTOR_D + 2 * c, P.MOTOR_D + 2 * c + 0.6)      # v7.0 lead-in on the cup rim
    nw = P.MOTOR_LEAD_NOTCH_W / 2
    jx = DRV_X0 + (P.DRV_JP2[0][1] + P.DRV_JP2[1][1]) / 2
    body = body - box(jx - nw, mc[1] - P.MOTOR_D / 2 - 3.0, Z_DRV - P.MOTOR_LEAD_NOTCH_D, jx + nw, mc[1], Z_DRV + 1)
    if P.GLUE_DEPTH > 0:
        body = body - union([box(x0, y0, P.FLOOR - P.GLUE_DEPTH, x1, y1, P.FLOOR + 0.01) for _, (x0, y0, x1, y1) in GLUE])
    body = body - openings() + strain_posts() - openings()
    body = body.translate(list(OFF))
    skirt, arm = skin_skirt(-OX / 2, OX / 2, OY, Rk)
    fl, hl = flanges(-OX / 2, OX / 2, OY, Rk)
    body = union([body, fl] + ([skirt] if skirt is not None else [])) - hl
    return body - openings().translate(list(OFF))


def _skirt_leadin(x0, y0, x1, y1, z0, ch=0.5):
    """v7.0: 45 deg lead-in on the inner bottom edge of a lid / cover skirt, so it finds the pod walls by itself"""
    f, r = P.FRAME_FIT, P.CORNER_R + P.FRAME_FIT
    return Manifold.hull(rbox(x0 - f - ch, y0 - f - ch, z0 - 0.01, x1 + f + ch, y1 + f + ch, z0, r + ch)
                         + rbox(x0 - f, y0 - f, z0 + ch, x1 + f, y1 + f, z0 + ch + 0.01, r))


def build_lid():
    """Lid: press-fits over the walls, flat plate on top (bridges every opening), the HELP switch pocket hangs from it,
    plunger bore 2.9, 6 mm finger dish.  Battery and DRV hold-down ribs.  Printed plate-down: no supports."""
    sk = P.FRAME_FIT + P.FRAME_WALL
    x0, y0, x1, y1 = -P.WALL, -P.WALL, XI + P.WALL, YI + P.WALL
    z0 = Z_WALL - P.LID_SKIRT
    outer = rbox(x0 - sk, y0 - sk, z0, x1 + sk, y1 + sk, Z_TOP, P.CORNER_R + sk)
    hollow = rbox(x0 - P.FRAME_FIT, y0 - P.FRAME_FIT, z0 - 1, x1 + P.FRAME_FIT, y1 + P.FRAME_FIT, Z_LID0, P.CORNER_R + P.FRAME_FIT)
    body = outer - hollow - _skirt_leadin(x0, y0, x1, y1, z0)
    bx, by = BTN_C
    # v6.7.2: the wired switch (solder + glue on its legs) did not fit the pocket: a plain square through-hole instead, top edge
    # chamfered, a shallow finger dish round it; the user glues the switch in.  Nothing hangs from the lid round it.
    h = P.BTN_SQ_HOLE / 2
    ch = P.BTN_HOLE_CHAMFER
    hole = box(bx - h, by - h, Z_LID0 - 1, bx + h, by + h, Z_TOP + 1)
    cham = Manifold.hull(box(bx - h, by - h, Z_TOP - P.BTN_DISH_DEPTH - ch, bx + h, by + h, Z_TOP - P.BTN_DISH_DEPTH - ch + 0.01)
                         + box(bx - h - ch, by - h - ch, Z_TOP - P.BTN_DISH_DEPTH - 0.01, bx + h + ch, by + h + ch, Z_TOP - P.BTN_DISH_DEPTH))
    dish = cyl(bx, by, Z_TOP - P.BTN_DISH_DEPTH, Z_TOP + 1, P.BTN_DISH_D, seg=64)
    body = body - hole - cham - dish
    rb = Z_BAT_TOP + 0.4
    for xr in (BAT_X0 + 7.0, BAT_X1 - 7.0):
        body = body + box(xr, BAT_Y0 + 2.0, rb, xr + 1.2, BAT_Y1 - 2.0, Z_LID0 + 0.01)
    rd = Z_DRV + P.DRV_PCB_T + 0.3
    body = body + box(DRV_X0 + 16.0, DRV_Y1 - 15.4, rd, DRV_X0 + 19.6, DRV_Y1 - 4.9, Z_LID0 + 0.01)
    cb = P.BTN_CLEAR_BOX / 2                                    # v6.7.2: keep 9 x 9 round the hole free of anything under the lid
    body = body - box(bx - cb, by - cb, -20, bx + cb, by + cb, Z_LID0 - 0.001)
    # skirt cut where the wide openings are (the plate still bridges them)
    for a, b in OPEN_HAND:
        body = body - box(x0 - sk - 1, a, z0 - 1, x0 + 0.01, b, Z_LID0 - 0.01)
    for a, b in OPEN_ELBOW:
        body = body - box(x1 - 0.01, a, z0 - 1, x1 + sk + 1, b, Z_LID0 - 0.01)
    return body.translate(list(OFF))


# ---------------------------------------------------------------- digital twin
def _at(x, y, z):
    return (x + OFF[0], y + OFF[1], z)


def twin():
    drv = T.drv_board().place(T.xf(_at(DRV_X0, DRV_Y1, Z_DRV), rot=-90))          # JP1 -> +Y (lane), GND end at the hand side
    mot = T.motor().place(T.xf(_at(MOTOR_C[0], MOTOR_C[1], P.MOTOR_FLOOR)))
    bat = T.battery().place(T.xf(_at(BAT_X0 + 0.2, (BAT_Y0 + BAT_Y1) / 2, P.BAT_FLOOR)))
    btn = T.button().place(T.xf(_at(BTN_C[0], BTN_C[1], Z_BTN0)))
    boards = [drv, mot, bat, btn]

    def W(name, pts, **k):
        return T.Wire(name, [_at(*p) for p in pts], **k)
    j2 = [(DRV_X0 + y, DRV_Y1 - x) for x, y in P.DRV_JP2]
    jx = DRV_X0 + (P.DRV_JP2[0][1] + P.DRV_JP2[1][1]) / 2
    wires = [W("motor leads (2 x AWG32)", [(jx, MOTOR_C[1] - P.MOTOR_D / 2 + 1.2, Z_DRV - 1.7), (jx, j2[0][1] + 1.6, Z_DRV - 1.7),
                                          (jx, j2[0][1] + 0.3, Z_DRV - 0.9)], d=0.8, r=1.2, ends=["motor", "DRV2605L"])]
    return boards, wires


def pad_zones():
    return [("DRV2605L 6-pad row (JP1): the lane", box(DRV_X0, DRV_Y1 + c, P.FLOOR, DRV_X0 + 15.3, LANE_Y1 - 0.01, Z_DRV).translate(list(OFF))),
            ("DRV2605L motor pads (JP2)", box(DRV_X0 + 4.0, DRV_Y0 - P.PAD_ROOM + 0.01, P.FLOOR, DRV_X0 + 11.3, DRV_Y0 - c, Z_DRV).translate(list(OFF)))]


H1_END = (DRV_X0 + 1.27 - 0.6, Y_H1, Z_LANE)                  # hop 1 bundle ends at the GND pad, then fans along the 4 I2C pads
H2_START = (DRV_X0 + 8.89 + 0.6, Y_H1, Z_LANE)
DRV_TAIL = (7.62 + (Y_H1 - (DRV_Y1 - 1.27))) / 2              # average fan per wire (the GND->SCL span is shared by the two hops)
BAT_LEAD = (BAT_X0 + 0.2, Y_BAT, Z_BAT_LEAD)
BTN_W = (BTN_C[0] - P.BTN_S / 2 - 0.9, BTN_C[1], Z_BTN_W)
REPORT = dict(interior=f"{XI:.1f} x {YI:.1f}", lid_top=round(Z_TOP, 2), lane=f"{P.PAD_ROOM} mm wide, {Z_LID0 - P.FLOOR:.1f} mm free height")
