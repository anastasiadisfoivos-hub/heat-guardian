"""v6 BRAIN POD (hand end of the band): XIAO nRF52840 on the floor, the 1.69in screen on top.  Wire-first layout.
Seen from above, hand end left, interior coordinates (0,0 = inside corner at the hand wall / -Y wall):

   +Y  [ 5V-row pad room (5 mm): the 7 screen wires rise from the 5V/GND/3V3/D10..D7 castellations, up-inward, one R8 bend each,
         into the screen plug above the XIAO                                                              ]
       [ XIAO, parts up, USB-C toward the HAND wall (plug-size tunnel), far end toward the elbow wall -> ]  far-end room -> crossing
       [ D-row pad room (5 mm)                                                                                                   ]
   -Y  [ open floor under the screen's head half: 2 screen posts, the HELP-button pair turns up (R8) onto its D pin      ] <- crossing

Screen: long side across the wrist (Y), socket mouth toward +Y, plug above the XIAO's 5V half.  It rests on the hand, elbow and
-Y wall tops and on two posts; the frame lip holds it down.  6 mm free height under it where the cable and plug land.
Crossing wires (hop 1, battery leads, button pair) leave the elbow wall straight, through two big rounded openings."""
import math
import numpy as np
from manifold3d import Manifold
from geo import box, cbox, cyl, rbox, union
import params as P
import twin as T
from common import skin_skirt, flanges, leadin

XIAO_REST = 1.25      # rest length under the board corner (bare strip beyond the castellations)
XIAO_LIP = 1.4       # v7.0 lip thickness (v6: 1.2)
POSTS_INFO = []

c = P.CLEAR
R = P.WIRE_BEND_R

# ---------------------------------------------------------------- heights (Z 0 = skin plane)
Z_XB = P.FLOOR + P.XIAO_UNDER_CLEAR                  # XIAO PCB bottom (corner rests, underside glue clear of the floor)
Z_XT = Z_XB + P.XIAO_PCB_T                           # XIAO PCB top
Z_XTOP = Z_XT + max(P.XIAO_TOP_BLOB, P.XIAO_SHIELD_H)   # pad joints / RF can
Z_USB = Z_XT + P.XIAO_USB_H / 2
Z_USB_TOP = Z_XT + P.XIAO_USB_H
Z_J = Z_XT + P.XIAO_TOP_BLOB / 2                     # where a wire leaves a castellated pad joint
Z_LCD = math.ceil((Z_XTOP + P.SCREEN_FREE_H) * 20 - 1e-6) / 20      # screen PCB back: 6 mm free over the XIAO where cable + plug land
assert Z_LCD - P.LCD_SOCKET_H >= Z_XTOP + P.GAP, "screen socket would sit on the XIAO"
Z_C = Z_LCD - P.LCD_SOCKET_H / 2 - 0.05              # screen cable centre where it leaves the plug
Z_GLASS = Z_LCD + P.LCD_PCB_T + P.LCD_LCM_T
Z_TOP = Z_GLASS + P.LCD_LIP_T
Z_WALL = Z_LCD
Z_POST = Z_LCD - P.LCD_STANDOFF_H
Z_BLUE = Z_POST - P.GAP - 0.5 - 0.45                 # blue wire height where it passes under a standoff

# ---------------------------------------------------------------- plan
XI = P.LCD_W - 2 * P.LCD_EDGE_REST                   # interior along the forearm: the screen's 31.5 side rests 1.2 on each wall
LCD_CX = XI / 2
XIAO_X0 = c + P.XIAO_SHIFT
XIAO_X1 = XIAO_X0 + P.XIAO_L
XIAO_CX = (XIAO_X0 + XIAO_X1) / 2
USB_TIP_X = XIAO_X0 - P.XIAO_USB_OVERHANG
FAR_ROOM = XI - XIAO_X1
assert FAR_ROOM >= P.PAD_ROOM, "no room for the far-end wires"
PLUG_V = P.LCD_SOCKET_V - P.LCD_SOCKET_L / 2 - P.LCD_PLUG_OUT     # plug back face (where the wires start), screen frame
PIN_X = [LCD_CX + (k - 3.5) * 1.25 for k in range(8)]             # 8 pins, 1.25 pitch; pin 7 (+X end) = blue
PAD_X = [XIAO_CX - 7.62 + 2.54 * j for j in range(7)]            # castellations from the USB end: 5V GND 3V3 D10 D9 D8 D7 (and D0..D6)


def _fits(run, a_step=0.05):
    """Each of the 7 wires: straight out of the plug, ONE bend of radius WIRE_BEND_R, straight into its castellation.
    The bend is put as LATE as it still fits (the wire stays straight over the XIAO's USB-C receptacle)."""
    sols = []
    for xp, xd in zip(PIN_X[:7], PAD_X):
        best = None
        for a in np.arange(run - 0.1, 0.3, -a_step):
            d = np.array([xd - xp, run - a, Z_J - Z_C])
            L = np.linalg.norm(d)
            th = math.acos(d[1] / L)
            t = R * math.tan(th / 2)
            if t <= a - 0.05 and t <= L - 0.05:
                best = a
                break
        if best is None:
            return None
        sols.append(best)
    return sols


RUN = next(r for r in np.arange(4.0, 30.0, 0.1) if _fits(r)) + 0.3      # plug back face -> joint, in Y (+0.3 margin)
BEND_A = _fits(RUN)
YC = max(P.LCD_L / 2 - P.LCD_EDGE_REST, P.PAD_ROOM + P.XIAO_W - 0.6 - RUN + PLUG_V)   # screen centre Y
Y_PS = YC - PLUG_V                                   # plug back face (screen v axis points to -Y: socket mouth toward +Y)
Y_JOINT = Y_PS + RUN
Y_5V = Y_JOINT + 0.6                                 # XIAO 5V-row edge
Y_D = Y_5V - P.XIAO_W                                # XIAO D-row edge
XIAO_CY = (Y_5V + Y_D) / 2
YI = Y_5V + P.PAD_ROOM


# ---------------------------------------------------------------- v6.5 wire garage: the 7 screen wires are NOT shortened
# Each wire leaves its castellation OUTWARD (+Y) and down in one straight line to the garage floor, makes ONE fold (a U standing
# in the garage: the 7 wires side by side like a flat ribbon, each bending on its own), and comes back at the plug's height
# straight into the plug's back face.  Fold radius = half the height between the floor leg and the plug: (Z_C - floor) / 2.
GAR_R = (Z_C - P.LCD_GARAGE_FLOOR_Z) / 2
GAR_ZC = (Z_C + P.LCD_GARAGE_FLOOR_Z) / 2


def _tangent(Q, yu, zc, Rr, lo, hi, sgn):
    """angle f on the fold circle whose tangent line passes through point Q=(y, z)"""
    for _ in range(60):
        f = (lo + hi) / 2
        py, pz = yu + Rr * math.sin(f), zc - Rr * math.cos(f)
        cr = (py - Q[0]) * math.sin(f) - (pz - Q[1]) * math.cos(f)
        lo, hi = (f, hi) if sgn * cr < 0 else (lo, f)
    return (lo + hi) / 2


def _fold_pts(xd, xp, yu, h=0.0, n=40):
    """joint (xd, outward) -> straight down onto the fold circle -> ONE fold up and over -> straight into the plug (xp).
    h > 0: a longer wire - the fold stands h taller (headroom past the screen edge) and the upper leg slopes gently to the plug."""
    Rr = (Z_C + h - P.LCD_GARAGE_FLOOR_Z) / 2
    zc = P.LCD_GARAGE_FLOOR_Z + Rr
    J, Q = (Y_5V + 0.6, Z_J), (Y_PS, Z_C)
    f0 = _tangent(J, yu, zc, Rr, -math.pi / 2, 0.0, 1)
    f1 = math.pi if h <= 1e-9 else _tangent(Q, yu, zc, Rr, math.pi, 1.5 * math.pi, -1)
    yz = [J] + [(yu + Rr * math.sin(f), zc - Rr * math.cos(f)) for f in np.linspace(f0, f1, n + 1)]
    y1, z1 = yz[-1]
    m = max(2, int((y1 - Y_PS) / 1.0))
    yz += [(y1 + (Y_PS - y1) * i / m, z1 + (Z_C - z1) * i / m) for i in range(1, m + 1)]
    yz = np.array(yz)
    sl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(yz, axis=0), axis=1))])
    xs = xd + (xp - xd) * sl / sl[-1]                         # the lateral shift (pad -> pin) is spread evenly along the wire
    return [(x, y, z) for x, (y, z) in zip(xs, yz)]


def _fold_len(xd, xp, yu, h=0.0):
    return T.Wire("f", _fold_pts(xd, xp, yu, h), d=P.WIRE_D, r=0).length + 1.0       # + 1.0 into the joint


def _solve_yu(target, k=3):
    lo, hi = Y_5V + 0.6 + GAR_R * 0.3, Y_5V + 60.0
    for _ in range(50):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if _fold_len(PAD_X[k], PIN_X[k], m) < target else (lo, m)
    return (lo + hi) / 2


def _solve_h(yu, target, k=3):
    lo, hi = 0.0, 12.0
    for _ in range(50):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if _fold_len(PAD_X[k], PIN_X[k], yu, m) < target else (lo, m)
    return (lo + hi) / 2


if P.LCD_GARAGE:
    GAR_YU = _solve_yu(P.LCD_GARAGE_LEN[0])                  # fold position for the shortest normal wire (45)
    # a 50 mm wire: the fold stands taller (headroom past the screen edge) AND sits a little further out, as long as its upper
    # leg still passes under the screen edge with GAP: pick the combination that needs the shortest garage
    _Z_EDGE = Z_LCD - P.GAP - P.WIRE_D / 2

    def _edge_z(yu, h, k=3):
        pp = np.array(_fold_pts(PAD_X[k], PIN_X[k], yu, h))
        up = pp[np.argmax(pp[:, 2]):]
        return float(np.interp(YC + P.LCD_L / 2, up[::-1, 1], up[::-1, 2]))
    _best = None
    for _h in np.arange(0.0, 6.01, 0.25):
        _lo, _hi = GAR_YU, GAR_YU + 10
        for _ in range(40):
            _m = (_lo + _hi) / 2
            _lo, _hi = (_m, _hi) if _fold_len(PAD_X[3], PIN_X[3], _m, _h) < P.LCD_GARAGE_LEN[1] else (_lo, _m)
        _yu = (_lo + _hi) / 2
        if _edge_z(_yu, _h) > _Z_EDGE:
            continue
        _end = _yu + (Z_C + _h - P.LCD_GARAGE_FLOOR_Z) / 2
        if _best is None or _end < _best[0]:
            _best = (_end, _yu, _h)
    _, GAR_YU_MAX, GAR_H = _best
    GAR_R_MAX = GAR_R + GAR_H / 2
    YI = max(YI, _best[0] + P.WIRE_D / 2 + P.LCD_GARAGE_MARGIN)
    GAR_LEN = [_fold_len(xd, xp, GAR_YU) for xd, xp in zip(PAD_X, PIN_X[:7])]
assert Y_D >= P.PAD_ROOM - 1e-6
OX, OY = XI + 2 * P.WALL, YI + 2 * P.WALL
OFF = np.array([-XI / 2, -YI / 2, 0.0])              # interior corner -> pod centre
SECTION_Y = XIAO_CY + OFF[1]


def _so(i):
    """LCD standoff i centre (interior coords): screen turned 180 deg (u -> -X, v -> -Y)."""
    sx, sy = P.LCD_STANDOFF_XY
    a, b = [(-1, -1), (1, -1), (-1, 1), (1, 1)][i]
    return (LCD_CX - a * sx, YC - b * sy)


SO = [_so(i) for i in range(4)]
SO_POSTS = [p for p in SO if p[1] < Y_D - 2]          # the two over the open floor get printed posts
SO_FREE = [p for p in SO if p[1] >= Y_D - 2]          # the two over the XIAO / far-end room hang free (>= GAP above whatever is below)

# ---------------------------------------------------------------- crossing wires (Y where they leave the elbow wall), set by the power pod
import power as PW                                   # noqa: E402  (power.py has no import back to brain.py)
Y_BTN = Y_D - 3.0                                    # v6.1: the button pair runs along the D-row edge (outside its corner lips)
SHIFT = Y_BTN - PW.Y_BTN                             # brain Y = power Y + SHIFT (the two pods are offset across the band)
Y_H1 = PW.Y_H1 + SHIFT                               # hop 1 leaves the XIAO's far end here (glued along the board)
Y_BAT = PW.Y_BAT + SHIFT
assert Y_D + 3.5 < Y_H1 < Y_5V - 1.5 and Y_D + 1.0 < Y_BAT < Y_5V - 3.0, (Y_H1, Y_BAT, Y_D, Y_5V)
X_BTN_END = XIAO_CX + 5.08 + 1.0                     # ... and peels into its D pad (modelled on D5)


def _span(ys):
    iv = sorted([(y - P.OPEN_W / 2, y + P.OPEN_W / 2) for y in ys])
    out = [list(iv[0])]
    for a, b in iv[1:]:
        if a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(max(a, 0.0), min(b, YI)) for a, b in out]


OPENS = _span([Y_BTN, Y_H1, Y_BAT])                  # elbow wall: big top-open opening(s), floor to the wall top
OPEN_A = OPEN_B = OPENS[0]
OPEN_Z = 99
Z_H1_IN, Z_BAT_IN, Z_BTN_IN = Z_XT + 1.5, P.FLOOR + 1.25, Z_J

# ---------------------------------------------------------------- glue zones (0.4 mm keyed recesses: put the hot glue HERE)
GLUE = [("brain: hop 1 + battery leads", (XI - 3.0, Y_H1 - 2.0, XI - 0.6, Y_BAT + 1.6)),
        ("brain: button pair", (XI - 3.0, Y_BTN - 1.6, XI - 0.6, Y_BTN + 1.6))]
if P.LCD_GARAGE:      # v6.5: glue the fold's floor leg where it lies on the garage floor, and the fold's apex against the end wall
    GLUE += [("brain: garage, fold floor leg", (PIN_X[0] - 2.0, GAR_YU - 2.5, PIN_X[6] + 2.0, GAR_YU + 0.5)),
             ("brain: garage, fold apex (end wall)", (PIN_X[0] - 2.0, YI - 2.2, PIN_X[6] + 2.0, YI - 0.2))]


def _xiao_local(x, y):
    """XIAO local (x toward USB, y = D0..D6 side) -> interior XY.  USB -> -X, D row -> -Y."""
    return (XIAO_CX - x, XIAO_CY - y)


def rslot_x(y0, y1, x0, x1, z0, z1, r):
    m = rbox(y0, z0, 0, y1, z1, abs(x1 - x0), r)
    M = np.array([[0, 0, 1.0, min(x0, x1)], [1.0, 0, 0, 0], [0, 1.0, 0, 0]])
    return m.transform(M)


RESET = _xiao_local(*P.XIAO_RESET_XY) + (Z_XT + P.XIAO_RESET_H,)
RESET_ENTRY = (-P.WALL, XIAO_CY - P.USBC_PLUG_W / 2 - P.USBC_PLUG_GAP - P.USBC_OPEN_PLUS - 0.9 - 1.6, Z_XT + 3.4)   # v7.0: 1.6 of wall between the guide and the plug tunnel


def _reset_hole():
    a, b = np.array(RESET_ENTRY), np.array(RESET)
    d = (b - a) / np.linalg.norm(b - a)
    s = Manifold.sphere(0.9, 16)
    return Manifold.hull(s.translate(list(a - d * 4.0)) + s.translate(list(a + d * 2.5)))     # only through the wall: a guide


def service_cuts():
    """USB-C plug tunnel through the hand wall (plug-size: the XIAO sits XIAO_SHIFT in from the wall) + reset-pin guide."""
    hw, hh = P.USBC_PLUG_W / 2 + P.USBC_PLUG_GAP + P.USBC_OPEN_PLUS, P.USBC_PLUG_H / 2 + P.USBC_PLUG_GAP + P.USBC_OPEN_PLUS
    tun = rslot_x(XIAO_CY - hw, XIAO_CY + hw, -P.WALL - 3, USB_TIP_X + 0.1, Z_USB - hh, Z_USB + hh, 1.5)
    return [tun, _reset_hole()]


def openings(x_in=None):
    """Big top-open opening(s) through the elbow wall (OPEN_W per run, merged), floor to the top, lower corners R OPEN_R."""
    x0 = XI - 0.01 if x_in is None else x_in
    return union([rslot_x(a, b, x0, XI + P.WALL + 3, P.FLOOR, OPEN_Z, P.OPEN_R) for a, b in OPENS])


def strain_posts():
    """Tie posts on the outside of the elbow wall, beside the openings (glue / tie a bundle to them - never wrap stiff wire round)."""
    out = []
    for y in (OPENS[0][0] - 2.4, OPENS[-1][1] + 2.4):
        x = XI + P.WALL
        out.append(box(x - 0.2, y - 1.6, 0, x + 2.6, y + 1.6, 2.0))
        out.append(cyl(x + 1.5, y, 1.99, 5.0, P.TIE_POST_D, seg=24))
    return union(out)


def build():
    Rk = P.SKIN_R_TOP
    outer = rbox(-P.WALL, -P.WALL, 0, XI + P.WALL, YI + P.WALL, Z_WALL, P.CORNER_R)
    body = outer - box(0, 0, P.FLOOR, XI, YI, 99)
    add = []
    # ---- XIAO seat, v7.0: four CORNER BLOCKS instead of the v6 1.25 mm rest columns + 1.2 mm lips.  Each block is one solid from the
    # floor: a rest under the bare board corner (|x| > 8.9 mm from the board centre, clear of every pad, joint and the BAT pads), a
    # lip outside the long edge (XIAO_FIT 0.4 per side, lead-in chamfer on top), and an END STOP past the board's short end.
    # USB end: the blocks run back INTO THE HAND WALL (the board cannot be pulled out with the cable; no glue near the USB-C).
    # Far end: the blocks reach 1.9 past the board end (the plug's push goes into them); the glue dot goes on their outer shoulder.
    xf_ = P.XIAO_FIT
    lip_z = Z_XT + 0.4
    stop_z = Z_XT - 0.2
    ch = P.SEAT_CHAMFER
    tun = P.USBC_PLUG_W / 2 + P.USBC_PLUG_GAP + P.USBC_OPEN_PLUS + 0.3     # keep-out half width round the USB-C plug tunnel
    cuts = []
    for end in ("usb", "far"):
        xr0, xr1 = (XIAO_X0 + 0.05, XIAO_X0 + 0.05 + XIAO_REST) if end == "usb" else (XIAO_X1 - 0.05 - XIAO_REST, XIAO_X1 - 0.05)
        xo0, xo1 = (-0.01, xr1) if end == "usb" else (xr0, XIAO_X1 + c + 1.6)       # block footprint along X
        for sgn, ye in ((-1, Y_D), (1, Y_5V)):
            yin = ye - sgn * 1.8                       # rest reaches 1.8 in under the board
            ylip0, ylip1 = ye + sgn * xf_, ye + sgn * (xf_ + XIAO_LIP)
            add.append(box(xo0, min(yin, ylip1), 0, xo1, max(yin, ylip1), Z_XB))                 # rest + base of the lip, one block
            add.append(box(xo0, min(ylip0, ylip1), 0, xo1, max(ylip0, ylip1), lip_z))            # lip beside the long edge
            cuts.append(leadin(xr0 - 9, min(ye, ylip0), xr1 + 9, max(ye, ylip0), lip_z, ch, sides="y" if sgn < 0 else "Y") ^
                        box(xo0 + 0.02, min(ylip0, ylip1) - 0.01, 0, xo1 + 1, max(ylip0, ylip1) + 0.01, 99))
            # end stop: past the board's short end, up to just under the board top (outside the plug tunnel at the USB end)
            ys0 = max(abs(yin - XIAO_CY), tun) if end == "usb" else abs(yin - XIAO_CY)
            xs0, xs1 = (-0.01, XIAO_X0 - xf_) if end == "usb" else (XIAO_X1 + c, XIAO_X1 + c + 1.6)
            if end == "far" and sgn > 0:
                continue                               # far end, 5V corner: no upper stop (hop 1 leaves there); the D corner takes the push
            add.append(box(xs0, XIAO_CY + sgn * ys0, 0, xs1, XIAO_CY + sgn * abs(ylip1 - XIAO_CY), stop_z if end == "far" else lip_z))
    # ---- two screen posts over the open floor, v7.0: each is tied into the -Y wall and its side wall by a solid corner gusset
    for x, y in SO_POSTS:
        add.append(cyl(x, y, 0, Z_POST, P.LCD_STANDOFF_D + 0.4, seg=32))
        xw = 0.0 if x < XI / 2 else XI
        add.append(box(min(x, xw) - 0.01, -0.01, 0, max(x, xw) + 0.01, y, Z_POST))             # fills the corner behind the post
        add.append(box(min(x, xw) - 0.01, y - 0.01, 0, max(x, xw) + 0.01, y + (P.LCD_STANDOFF_D + 0.4) / 2, Z_POST) ^
                   box(min(x, xw) - 0.01, -1, 0, max(x, xw) + 0.01, 99, Z_POST))
        POSTS_INFO.append((x, y))
    body = body + union(add) - union(cuts)
    # ---- glue zones (v7.0: GLUE_DEPTH 0 - no recesses)
    if P.GLUE_DEPTH > 0:
        body = body - union([box(x0, y0, P.FLOOR - P.GLUE_DEPTH, x1, y1, P.FLOOR + 0.01) for _, (x0, y0, x1, y1) in GLUE])
    body = body - openings() + strain_posts() - openings()
    body = body - union(service_cuts())
    body = body.translate(list(OFF))
    skirt, arm = skin_skirt(-OX / 2, OX / 2, OY, Rk)
    fl, holes = flanges(-OX / 2, OX / 2, OY, Rk)
    body = union([body, fl] + ([skirt] if skirt is not None else [])) - holes
    body = body - union(service_cuts()).translate(list(OFF)) - openings().translate(list(OFF))
    return body


def build_frame():
    """Screen frame: press-fits over the tray walls (v4 fit: FRAME_FIT, skirt, lip), lip holds the glass, a rib locates the
    screen's +Y (tail) edge, plate covers the 5V pad room.  Exported window-face down."""
    sk = P.FRAME_FIT + P.FRAME_WALL
    x0, y0, x1, y1 = -P.WALL, -P.WALL, XI + P.WALL, YI + P.WALL
    z0 = Z_WALL - P.FRAME_SKIRT - P.FRAME_SKIRT_EXTRA          # v6.7: skirt 3 mm longer
    outer = rbox(x0 - sk, y0 - sk, z0, x1 + sk, y1 + sk, Z_TOP, P.CORNER_R + sk)
    hollow = rbox(x0 - P.FRAME_FIT, y0 - P.FRAME_FIT, z0 - 1, x1 + P.FRAME_FIT, y1 + P.FRAME_FIT, Z_GLASS, P.CORNER_R + P.FRAME_FIT)
    body = outer - hollow - PW._skirt_leadin(x0, y0, x1, y1, z0)     # v7.0 lead-in on the skirt's inner edge
    ly1 = YC + P.LCD_L / 2
    zr = Z_LCD + 0.4
    body = body + box(4.0, ly1 + c, zr, XI - 4.0, ly1 + c + 1.2, Z_GLASS + 0.01)      # locates the screen's tail edge
    wl, ww = P.LCD_AA_L + 2 * P.LCD_WIN_MARGIN, P.LCD_AA_W + 2 * P.LCD_WIN_MARGIN
    cx, cy = LCD_CX, YC - P.LCD_AA_OFF_V                                               # active area sits 1.3 toward +v (= -Y here)
    body = body - rbox(cx - ww / 2, cy - wl / 2, Z_GLASS - 1, cx + ww / 2, cy + wl / 2, Z_TOP + 1, P.LCD_AA_R)
    # v6.7 STOPS: the cover lands on the pod rim (z = Z_WALL) wherever the screen does not rest on it, so it sits level and cannot
    # sink or tilt: a ledge along the whole +Y (garage) wall, ledges on the hand / elbow walls past the screen's +Y edge, and two
    # corner blocks at the -Y corners outside the screen's rounded corners.  Nothing rests on wires or on the garage fold.
    sw = P.FRAME_STOP_W
    stops = [box(x0 + 0.1, YI + 0.1, Z_WALL, x1 - 0.1, YI + P.WALL - 0.1, Z_GLASS + 0.01)]
    ys0 = YC + P.LCD_L / 2 + P.GAP + 0.2
    for xa, xb in ((x0 + 0.1, -0.1), (XI + 0.1, x1 - 0.1)):
        stops.append(box(xa, ys0, Z_WALL, xb, YI + P.WALL - 0.1, Z_GLASS + 0.01))
        stops.append(box(xa, y0 + 0.1, Z_WALL, xb, y0 + 0.1 + sw, Z_GLASS + 0.01))          # -Y corners, outside the screen's R5 corners
    body = body + union(stops)
    hw, hh = P.USBC_PLUG_W / 2 + P.USBC_PLUG_GAP + P.USBC_OPEN_PLUS, P.USBC_PLUG_H / 2 + P.USBC_PLUG_GAP + P.USBC_OPEN_PLUS
    body = body - rslot_x(XIAO_CY - hw, XIAO_CY + hw, x0 - sk - 1, x0 + 0.01, -20, Z_USB + hh, 1.5)
    rh = _reset_hole()      # v7.0: the reset-pin guide is an open-bottom notch in the skirt (the round hole left a 0.1 mm sliver at the skirt edge)
    body = body - Manifold.hull(rh + rh.translate([0, 0, -4.0]))
    # v6.7: the longer skirt is cut away over the elbow-wall opening(s) back to the old skirt line (crossing wires + sleeves pass)
    for a, b in OPENS:
        body = body - rslot_x(a, b, x1 - 0.01, x1 + sk + 1, -20, Z_WALL - P.FRAME_SKIRT, P.OPEN_R)
    return body.translate(list(OFF))


# ---------------------------------------------------------------- digital twin
def _at(x, y, z):
    return (x + OFF[0], y + OFF[1], z)


def twin():
    """Every real part in the brain pod (pod-centred frame).  Returns (boards, wires).  Crossing wires are built in assembly.py."""
    xi = T.xiao().place(T.xf(_at(XIAO_CX, XIAO_CY, Z_XB), rot=180))
    lcd = T.lcd().place(T.xf(_at(LCD_CX, YC, Z_LCD), rot=180))
    plug = T.usb_plug().place(T.xf(_at(USB_TIP_X, XIAO_CY, Z_USB), rot=180))
    boards = [xi, lcd, plug]

    def W(name, pts, **k):
        return T.Wire(name, [_at(*p) for p in pts], **k)
    ends = ["LCD 1.69in", "XIAO nRF52840"]
    names = ["5V", "GND", "3V3", "D10", "D9", "D8", "D7"]
    wires = []
    for k, (xp, xd, a) in enumerate(zip(PIN_X[:7], PAD_X, BEND_A)):
        oth = [f"screen wire {j + 1} -> {names[j]}" for j in range(7) if j != k]
        if P.LCD_GARAGE:          # v6.5: through the wire garage (one fold), full length kept
            wires.append(W(f"screen wire {k + 1} -> {names[k]} (garage fold, flat ribbon)", _fold_pts(xd, xp, GAR_YU), d=P.WIRE_D, r=0,
                           ends=ends + oth + [f"screen wire {j + 1} -> {names[j]} (garage fold, flat ribbon)" for j in range(7) if j != k]))
        else:
            wires.append(W(f"screen wire {k + 1} -> {names[k]}", [(xp, Y_PS, Z_C), (xp, Y_PS + a, Z_C), (xd, Y_JOINT, Z_J)],
                           d=P.WIRE_D, r=R, ends=ends + oth))
    xb = PIN_X[7]
    xd6 = XIAO_CX + 7.62
    # v6.5: shortest blue route that keeps R4 (the blue may be the 25 mm wire): tight U-turn at the plug, diagonal to D6
    ub = 2 * P.WIRE_BEND_R_SINGLE
    wires.append(W("screen wire 8 (blue) -> D6", [(xb, Y_PS, Z_C), (xb, Y_PS + P.WIRE_BEND_R_SINGLE, Z_BLUE), (xb + ub, Y_PS + P.WIRE_BEND_R_SINGLE, Z_BLUE),
                                                  (xb + ub, Y_D + 4.0, Z_BLUE - 1.0), (xd6, Y_D + 0.6, Z_J)],
                   d=P.WIRE_D, r=P.WIRE_BEND_R_SINGLE, ends=ends + ["screen wire 7 -> D7"]))
    return boards, wires


def pad_zones():
    """Clear-floor zones in front of every padded board edge: (label, box) in the pod frame."""
    x0, x1 = XIAO_CX - 8.9, XIAO_CX + 8.9
    z1 = Z_XB
    return [("XIAO 5V/GND/3V3 row", box(x0, Y_5V + c, P.FLOOR, x1, Y_5V + P.PAD_ROOM - 0.01, Z_XT).translate(list(OFF))),
            ("XIAO D0..D6 row", box(x0, Y_D - P.PAD_ROOM + 0.01, P.FLOOR, x1, Y_D - c, Z_XT).translate(list(OFF))),
            ("XIAO far end (hop 1, battery leads)", box(XIAO_X1 + c + 1.7, Y_D, P.FLOOR, XI - 0.01, Y_5V, Z_XT).translate(list(OFF)))]


REPORT = dict(interior=f"{XI:.1f} x {YI:.1f}", screen=f"PCB back at {Z_LCD:.2f} ({P.SCREEN_FREE_H} free over the XIAO top {Z_XTOP:.2f}), top {Z_TOP:.2f}",
              cable=(f"wire garage: ONE fold R {GAR_R:.1f}-{GAR_R_MAX:.1f} (flat ribbon; 45-50 mm wires), fold {GAR_YU - Y_5V:.1f} past the 5V edge, "
                     f"pod {YI - (Y_5V + P.PAD_ROOM):.1f} longer across" if P.LCD_GARAGE else
                     f"plug back face -> 5V row joint {RUN:.1f} mm in Y, one R{R:.0f} bend per wire"))
