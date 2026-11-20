"""v7-cover SCREEN COVER for the printed v7.0 brain pod: removable (friction ribs, no glue), screen window, the button in the cover.

Built on parts/brain.py (every pod dimension comes from there).  Interior coordinates as in brain.py: (0,0) = inside corner at the
hand wall / -Y wall, X toward the elbow, Y across the wrist, Z 0 = skin plane.  The screen's FPC-tail edge is at +Y, so "below the
screen" = the +Y strip of the cover (32 x 18 mm), which lies over the screen-wire garage.

Section through the button (assembled, cover face up):

      cap (8 dia, 1.8 proud)                 <- thumb
   ===#####===  cover plate 1.2              the cap goes through a 8.5 hole
      /###\\     45 deg flare + flange        cannot come out through the hole; 0.6 float under the plate
     | well |   well 10.6 dia                guides the flange
      \\   /     45 deg cone (prints without support, the cover is printed face down)
       |n|      plunger nose -> switch plunger (2.5 dia, 3.5 long) through the 4.2 throat
      [body]    depth stop on the switch's body top; 5.6 x 5.6 sleeve round the top 2 mm of the body
       legs     legs, joints, glue: free below the sleeve; the two wires leave through the slot facing the XIAO

The press goes plunger -> switch -> hot glue at the sleeve mouth -> cover -> pod rim (the same glued-in-a-square-hole mounting the
switch had on the v7.0 power lid).  Nothing rests on the screen board, the XIAO or the wires.
Parts: build() = cover (print face down), build_plunger() = plunger (print cap down), build_lid_plug() / build_lid_nohole() = what
to do with the old switch hole in the power lid."""
import math
import numpy as np
from manifold3d import Manifold
from geo import box, cyl, rbox, union
import params as P
import twin as T
import brain as B
import power as PW

c = P.CLEAR
XI, YI, OFF = B.XI, B.YI, B.OFF
Z_WALL, Z_GLASS, Z_TOP = B.Z_WALL, B.Z_GLASS, B.Z_TOP
SK = P.COVER_FIT + P.COVER_WALL
X0, Y0, X1, Y1 = -P.WALL, -P.WALL, XI + P.WALL, YI + P.WALL          # pod outer walls
Z0 = Z_WALL - P.FRAME_SKIRT - P.FRAME_SKIRT_EXTRA                     # skirt bottom (as brain_frame: 5.5 over the walls)

# ---------------------------------------------------------------- window (as brain_frame)
WIN_W, WIN_L = P.LCD_AA_W + 2 * P.LCD_WIN_MARGIN, P.LCD_AA_L + 2 * P.LCD_WIN_MARGIN
WIN_C = (B.LCD_CX, B.YC - P.LCD_AA_OFF_V)
LCD_Y1 = B.YC + P.LCD_L / 2                                           # screen board's tail (+Y) edge

# ---------------------------------------------------------------- button stack (Z, assembled)
R_CAP = P.COVER_BTN_CAP_D / 2
R_HOLE = R_CAP + P.COVER_BTN_HOLE_GAP
R_FL = R_CAP + P.COVER_BTN_FLARE
R_WELL = R_FL + P.COVER_BTN_WELL_GAP
R_OUT = R_WELL + P.MIN_T + 0.05       # + 0.05: the faceted circle keeps 1.2
TAPER_DROP = 0.8                       # the tower's outer taper starts this far below the cone's top: the cone wall stays >= 1.2 thick
R_THR = P.COVER_BTN_THROAT_D / 2
Z_J_STOP = Z_GLASS + P.COVER_BTN_HOLE_GAP          # cap/flare junction when the flare sits in the hole's inner edge (plunger hanging)
Z_J = Z_J_STOP - P.COVER_BTN_FLOAT                 # ... when the plunger rests on the switch
Z_FL0 = Z_J - P.COVER_BTN_FLARE                    # flare bottom
Z_FB = Z_FL0 - P.COVER_BTN_FLANGE_T                # flange bottom
Z_NOSE = Z_FB - P.COVER_BTN_STEM_L                 # plunger nose = switch plunger tip
Z_BODY1 = Z_NOSE - P.BTN_PLUNGER                   # switch body top = depth stop
Z_BODY0 = Z_BODY1 - P.BTN_BODY_H
Z_MOUTH = Z_BODY1 - P.COVER_BTN_SLEEVE_DEPTH
Z_WELL0 = Z_FB - P.COVER_BTN_PRESS_ROOM            # well floor = top of the cone
Z_CONE0 = Z_BODY1 + P.COVER_BTN_THROAT_T
CONE_ANGLE = math.degrees(math.atan2(R_WELL - R_THR, Z_WELL0 - Z_CONE0))      # from vertical; <= 50 prints without support
assert Z_CONE0 - TAPER_DROP >= Z_MOUTH
assert CONE_ANGLE <= 50.0, f"button cone overhang {CONE_ANGLE:.1f} deg"
CAP_LEN = Z_TOP + P.COVER_BTN_PROUD - Z_J
BTN_H = Z_NOSE - P.FLOOR                           # switch plunger tip above the pod floor (the task's button_h)
SLV = P.COVER_BTN_SLEEVE / 2
SLV_O = SLV + P.MIN_T


def btn_xy(pos=None):
    """button centre (interior).  centre: under the middle of the screen, midway in the strip.  corner: elbow-side end of the strip,
    as far from the screen-wire ribbon as the pod wall allows."""
    if P.COVER_BTN_X is not None and P.COVER_BTN_Y is not None:
        return (P.COVER_BTN_X, P.COVER_BTN_Y)
    pos = pos or P.COVER_BTN_POS
    y = (LCD_Y1 + c + P.MIN_T + YI) / 2                       # between the screen's locating rib and the +Y wall
    if pos == "centre":
        return (B.LCD_CX, y)
    r12 = R_OUT if Z_WELL0 - TAPER_DROP <= Z_WALL else R_OUT - (R_OUT - SLV_O) * (Z_WELL0 - TAPER_DROP - Z_WALL) / (Z_WELL0 - Z_CONE0)   # tower half-width at the pod rim
    return (XI - P.GAP - r12, y)


def _tower(bx, by):
    """(solid, cavity) of the button tower hanging from the plate"""
    sq = lambda h, z: box(bx - h, by - h, z, bx + h, by + h, z + 0.01)
    zt = Z_WELL0 - TAPER_DROP
    solid = union([cyl(bx, by, zt, Z_GLASS + 0.01, 2 * R_OUT, seg=96),
                   Manifold.hull(cyl(bx, by, zt - 0.01, zt, 2 * R_OUT, seg=96) + sq(SLV_O, Z_CONE0 - TAPER_DROP)),
                   box(bx - SLV_O, by - SLV_O, Z_MOUTH, bx + SLV_O, by + SLV_O, Z_CONE0 + 0.01)])
    cav = union([cyl(bx, by, Z_WELL0, Z_GLASS, 2 * R_WELL, seg=96),
                 cyl(bx, by, Z_CONE0, Z_WELL0 + 0.01, 2 * R_THR, 2 * R_WELL, seg=96),
                 cyl(bx, by, Z_BODY1 - 0.01, Z_CONE0 + 0.01, 2 * R_THR, seg=48),
                 box(bx - SLV, by - SLV, Z_MOUTH - 1, bx + SLV, by + SLV, Z_BODY1),
                 box(bx - P.COVER_BTN_WIRE_SLOT / 2, by - SLV_O - 1, Z_MOUTH - 1, bx + P.COVER_BTN_WIRE_SLOT / 2, by, Z_BODY1)])
    return solid, cav


PLATE_T = Z_TOP - Z_GLASS
SIMPLE_RECESS = PLATE_T - P.COVER_SIMPLE_RECESS_DEPTH >= P.COVER_SIMPLE_MIN_PLATE - 1e-9     # False with the 1.2 plate: skipped


def simple_hole(bx, by):
    """v7-cover SIMPLE: 4.2 round through-hole, 0.6 x 45 deg chamfer on the outer edge, optional square recess on the inside"""
    d, ch = P.COVER_SIMPLE_HOLE_D, P.COVER_SIMPLE_HOLE_CHAMFER
    h = cyl(bx, by, Z_GLASS - 1, Z_TOP + 1, d, seg=96) + cyl(bx, by, Z_TOP - ch, Z_TOP + 0.01, d, d + 2 * ch + 0.02, seg=96)
    if SIMPLE_RECESS:
        r = P.COVER_SIMPLE_RECESS / 2
        h = h + box(bx - r, by - r, Z_GLASS - 1, bx + r, by + r, Z_GLASS + P.COVER_SIMPLE_RECESS_DEPTH)
    return h


def switch_twin_simple(pos="corner"):
    """the bare switch glued under the plate: body top on the plate underside, actuator up through the hole"""
    bx, by = btn_xy(pos)
    zb = (Z_GLASS + (P.COVER_SIMPLE_RECESS_DEPTH if SIMPLE_RECESS else 0.0)) - P.BTN_BODY_H
    return T.button().place(T.xf((bx + OFF[0], by + OFF[1], zb)))


def _ribs():
    """grip ribs: half-round vertical ribs inside the skirt, at mid-wall only, opposite each other"""
    h = P.COVER_FIT - P.COVER_GRIP_GAP
    w = P.COVER_GRIP_W
    zt = Z_WALL - 0.3
    zb = Z0 + 1.0                                                     # above the lead-in chamfer
    out = []

    def rib(x, y, nx, ny):
        # a flattened cylinder: w wide along the wall, h proud of the skirt's inner face
        m = Manifold.cylinder(zt - zb, 0.5, 0.5, 32).scale([w if ny else 2 * h, w if nx else 2 * h, 1.0])
        out.append(m.translate([x, y, zb]))
    ya, yb = 4.0, (LCD_Y1 + YI) / 2
    for y in (ya, yb):
        rib(X0 - P.COVER_FIT, y, 1, 0)
        rib(X1 + P.COVER_FIT, y, 1, 0)
    for x in (XI * 0.28, XI * 0.72):
        rib(x, Y0 - P.COVER_FIT, 0, 1)
        rib(x, Y1 + P.COVER_FIT, 0, 1)
    return union(out)


def build(pos=None, simple=False):
    """simple=True: v7-cover SIMPLE - no tower/plunger, a plain chamfered through-hole (+ an inside recess if the plate allows)"""
    bx, by = btn_xy(pos)
    f = P.COVER_FIT
    outer = rbox(X0 - SK, Y0 - SK, Z0, X1 + SK, Y1 + SK, Z_TOP, P.CORNER_R + SK)
    hollow = rbox(X0 - f, Y0 - f, Z0 - 1, X1 + f, Y1 + f, Z_GLASS, P.CORNER_R + f)
    body = outer - hollow - PW._skirt_leadin(X0, Y0, X1, Y1, Z0)
    body = body + (_ribs() ^ outer)
    # screen: tail-edge locating rib, window with a small bezel lip over the glass edge
    body = body + box(4.0, LCD_Y1 + c, B.Z_LCD + 0.4, XI - 4.0, LCD_Y1 + c + P.MIN_T, Z_GLASS + 0.01)
    cx, cy = WIN_C
    win = rbox(cx - WIN_W / 2, cy - WIN_L / 2, Z_GLASS - 1, cx + WIN_W / 2, cy + WIN_L / 2, Z_TOP + 1, P.LCD_AA_R)
    ch = P.COVER_WIN_CHAMFER
    win += Manifold.hull(rbox(cx - WIN_W / 2, cy - WIN_L / 2, Z_TOP - ch, cx + WIN_W / 2, cy + WIN_L / 2, Z_TOP - ch + 0.01, P.LCD_AA_R) +
                         rbox(cx - WIN_W / 2 - ch, cy - WIN_L / 2 - ch, Z_TOP, cx + WIN_W / 2 + ch, cy + WIN_L / 2 + ch, Z_TOP + 0.01, P.LCD_AA_R + ch))
    body = body - win
    # stops on the pod rim (as brain_frame v6.7): the cover sits level and cannot sink
    sw = P.FRAME_STOP_W
    stops = [box(X0 + 0.1, YI + 0.1, Z_WALL, X1 - 0.1, YI + P.WALL - 0.1, Z_GLASS + 0.01)]
    ys0 = LCD_Y1 + P.GAP + 0.2
    for xa, xb in ((X0 + 0.1, -0.1), (XI + 0.1, X1 - 0.1)):
        stops.append(box(xa, ys0, Z_WALL, xb, YI + P.WALL - 0.1, Z_GLASS + 0.01))
        stops.append(box(xa, Y0 + 0.1, Z_WALL, xb, Y0 + 0.1 + sw, Z_GLASS + 0.01))
    body = body + union(stops)
    # button tower + the hole for the cap (outer edge chamfered 0.3)
    if simple:
        body = body - simple_hole(bx, by)
    else:
        solid, cav = _tower(bx, by)
        hole = cyl(bx, by, Z_GLASS - 1, Z_TOP + 1, 2 * R_HOLE, seg=96) + cyl(bx, by, Z_TOP - 0.3, Z_TOP + 0.01, 2 * R_HOLE, 2 * R_HOLE + 0.6, seg=96)
        body = body + solid - cav - hole
    # USB-C plug cut-out and reset-pin notch in the hand-side skirt (as brain_frame v7.0), elbow-side skirt cut over the wire opening
    hw, hh = P.USBC_PLUG_W / 2 + P.USBC_PLUG_GAP + P.USBC_OPEN_PLUS, P.USBC_PLUG_H / 2 + P.USBC_PLUG_GAP + P.USBC_OPEN_PLUS
    body = body - B.rslot_x(B.XIAO_CY - hw, B.XIAO_CY + hw, X0 - SK - 1, X0 + 0.01, -20, B.Z_USB + hh, 1.5)
    rh = B._reset_hole()
    body = body - Manifold.hull(rh + rh.translate([0, 0, -4.0]))
    for a, b in B.OPENS:
        body = body - B.rslot_x(a, b, X1 - 0.01, X1 + SK + 1, -20, Z_WALL - P.FRAME_SKIRT, P.OPEN_R)
    return body.translate(list(OFF))


def build_plunger(assembled=False, pos=None):
    """captive plunger.  Print orientation: cap face on the bed (z 0), nose up.  assembled=True: in place, resting on the switch."""
    cc = P.COVER_BTN_CAP_CHAMFER
    z1 = CAP_LEN
    z2 = z1 + P.COVER_BTN_FLARE
    z3 = z2 + P.COVER_BTN_FLANGE_T
    m = union([cyl(0, 0, 0, cc, 2 * (R_CAP - cc), 2 * R_CAP, seg=96), cyl(0, 0, cc, z1, 2 * R_CAP, seg=96),
               cyl(0, 0, z1, z2, 2 * R_CAP, 2 * R_FL, seg=96), cyl(0, 0, z2, z3, 2 * R_FL, seg=96),
               cyl(0, 0, z3, z3 + P.COVER_BTN_STEM_L, P.COVER_BTN_STEM_D, seg=48)])
    if not assembled:
        return m
    bx, by = btn_xy(pos)
    return m.rotate([180, 0, 0]).translate([bx + OFF[0], by + OFF[1], Z_TOP + P.COVER_BTN_PROUD])


def switch_twin(pos=None):
    """the real switch in its sleeve (pod-centred frame), plunger up"""
    bx, by = btn_xy(pos)
    return T.button().place(T.xf((bx + OFF[0], by + OFF[1], Z_BODY0)))


# ---------------------------------------------------------------- power lid: the old 5.6 x 5.6 switch hole
def build_lid_plug():
    """plug for the old switch hole: a disc that fills the finger dish + a square peg.  Print disc down."""
    d = P.BTN_DISH_D - 0.4
    s = P.BTN_SQ_HOLE / 2 - P.LID_PLUG_FIT
    peg = P.LID_T - P.BTN_DISH_DEPTH
    return cyl(0, 0, 0, P.BTN_DISH_DEPTH, d, seg=64) + box(-s, -s, P.BTN_DISH_DEPTH - 0.01, s, s, P.BTN_DISH_DEPTH + peg)


def build_lid_nohole():
    """v7.0 power lid with the switch hole, its chamfer and the finger dish filled: a plain closed plate"""
    bx, by = PW.BTN_C
    fill = cyl(bx, by, PW.Z_LID0, PW.Z_TOP, P.BTN_DISH_D + 0.4, seg=64).translate(list(PW.OFF))
    return PW.build_lid() + fill


PRINT_FLIP = True
REPORT = dict(note="print window face down, no supports", button=f"centre {btn_xy()[0]:.2f}, {btn_xy()[1]:.2f} (interior), "
              f"switch plunger tip {BTN_H:.2f} above the pod floor, cone {CONE_ANGLE:.1f} deg")
