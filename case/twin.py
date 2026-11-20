"""DIGITAL TWIN of the real hardware: every board as a solid with its real components, sockets, glue/solder
blobs and wire exits, plus wire bundles as swept tubes.  All numbers come from params.py (DATASHEET / MEASURED /
PHOTO / ASSUMED).  Each builder returns a Board in its own local frame; place() puts it in a part's frame."""
import math
import numpy as np
from manifold3d import Manifold
from geo import box, cbox, cyl, rbox, union
import params as P


# ------------------------------------------------------------------ placement
def xf(at=(0, 0, 0), rot=0, flip=False, centre=(0, 0, 0)):
    """3x4 matrix: move `centre` to the origin, optionally flip face-down (180 deg about X), rotate about Z by
    `rot` degrees, then translate to `at`."""
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
    F = np.diag([1.0, -1.0, -1.0]) if flip else np.eye(3)
    A = R @ F
    t = np.array(at, float) - A @ np.array(centre, float)
    return np.hstack([A, t.reshape(3, 1)])


def tp(M, p):
    """transform a point"""
    p = np.array(p, float)
    return M[:, :3] @ p + M[:, 3]


class Board:
    def __init__(self, name, solids, pts=None):
        self.name, self.solids, self.pts = name, solids, pts or {}

    def place(self, M, name=None):
        return Placed(name or self.name, [(k, m.transform(M)) for k, m in self.solids], M, self.pts)


class Placed:
    def __init__(self, name, solids, M, pts):
        self.name, self.solids, self.M, self._pts = name, solids, M, pts
        self.solid = union([m for _, m in solids])

    def pt(self, key):
        return tp(self.M, self._pts[key])

    def loc(self, p):
        return tp(self.M, p)

    def part(self, key):
        return union([m for k, m in self.solids if k == key])


# ------------------------------------------------------------------ Adafruit STEMMA QT boards
# small parts per board, from the Eagle .brd:  (label, cx, cy, sx, sy, h)
ADA_PARTS = {
    "tmp117": [("chip", 12.7, 8.89, 2.0, 2.0, P.TMP_CHIP_H), ("C1 0603", 12.7, 10.8, 1.6, 0.8, 0.8),
               ("C2 0805", 7.24, 5.59, 2.0, 1.25, 1.0), ("R3 pack", 17.91, 9.02, 1.6, 3.2, 0.5),
               ("R1 0603", 6.86, 11.68, 0.8, 1.6, 0.5), ("LED", 3.56, 12.57, 0.8, 1.6, 0.7)],
    "shtc3": [("chip", 12.7, 8.89, 2.0, 2.0, P.SHT_CHIP_H), ("U2 reg", 7.87, 9.53, 3.0, 3.0, 1.4),
              ("C2", 7.62, 6.1, 2.0, 1.25, 1.0), ("C3", 8.0, 12.83, 2.0, 1.25, 1.0), ("C1", 11.05, 5.59, 1.6, 0.8, 0.8),
              ("R3 pack", 17.53, 11.43, 3.2, 1.6, 0.5), ("Q2", 17.08, 6.1, 1.3, 2.1, 1.1), ("LED", 3.56, 12.57, 0.8, 1.6, 0.7)],
    "icm20649": [("chip", 12.76, 8.19, 3.0, 3.0, P.ICM_CHIP_H), ("U3 reg", 7.7, 7.87, 3.0, 3.0, 1.4),
                 ("C5", 7.34, 4.93, 2.0, 1.25, 1.0), ("C6", 5.59, 12.5, 1.25, 2.0, 1.0), ("R3 pack", 17.55, 11.56, 3.2, 1.6, 0.5),
                 ("R1 pack", 8.38, 11.43, 3.2, 1.6, 0.5), ("Q2", 18.25, 7.54, 2.1, 1.3, 1.1), ("D2", 12.5, 10.99, 2.6, 1.4, 1.0),
                 ("LED", 3.49, 12.51, 0.8, 1.6, 0.7)],
}
ADA_PADS = {"tmp117": 6, "icm20649": 6, "shtc3": 5}


def ada_board(kind, sockets=True, wire_side="top", blob_h=None, name=None, tab_wires=False, back_blob_h=None, hole_dx=None):
    """ICM-20649 / TMP117 / SHTC3.  Local frame = Eagle: x 0..25.4, y 0..17.78 (pad row at y = 2.54), z 0 = PCB bottom."""
    t = P.PCB_T
    blob_h = P.BLOB_H if blob_h is None else blob_h
    pcb = rbox(0, 0, 0, P.ADA_L, P.ADA_W, t, P.ADA_CORNER_R)
    holes = P.ADA_HOLES if hole_dx is None else [(P.ADA_L / 2 + sg * hole_dx / 2, y) for y in (2.54, 15.24) for sg in (-1, 1)]   # v7.0: owner-measured spacing
    pcb = pcb - union([cyl(x, y, -1, t + 1, P.ADA_HOLE_D, seg=24) for x, y in holes])
    out = [("pcb", pcb)]
    if sockets:
        for x0, x1 in (P.STEMMA_X, (P.ADA_L - P.STEMMA_X[1], P.ADA_L - P.STEMMA_X[0])):
            out.append(("socket", box(x0, P.STEMMA_Y[0], t, x1, P.STEMMA_Y[1], t + P.STEMMA_H)))
    for lab, cx, cy, sx, sy, h in ADA_PARTS[kind]:
        out.append(("chip" if lab == "chip" else "smd", cbox(cx, cy, t, sx, sy, t + h)))
    n = ADA_PADS[kind]
    px0 = 12.7 - (n - 1) * 2.54 / 2 - 1.6
    px1 = 12.7 + (n - 1) * 2.54 / 2 + 1.6
    if wire_side == "top":       # wires + glue on the component side, solder points underneath
        out.append(("blob", box(px0, -P.BLOB_OVER, t, px1, P.BLOB_STRIP, t + blob_h)))
        if back_blob_h:  # v6.9: joints + glue on the other side too (TMP117 #2, wires kept as soldered)
            out.append(("blob", box(px0, -P.BLOB_OVER, -back_blob_h, px1, P.BLOB_STRIP, 0)))
        else:
            out.append(("solder", box(px0, 1.4, -0.6, px1, 3.7, 0)))
    else:
        out.append(("blob", box(px0, -P.BLOB_OVER, -blob_h, px1, P.BLOB_STRIP, 0)))
        out.append(("solder", box(px0, 1.4, t, px1, 3.7, t + 0.6)))
    if tab_wires:      # GND soldered to the removed sockets' tab pads (component side), wires leaving over both short ends
        ys = [p[1] for p in P.TMP_TAB_PADS]
        for x0, x1 in ((-P.BLOB_OVER, 2.6), (P.ADA_L - 2.6, P.ADA_L + P.BLOB_OVER)):
            out.append(("blob", box(x0, min(ys) - 1.1, t, x1, max(ys) + 1.1, t + P.TMP1_TAB_BLOB_H)))
    zt = t + blob_h / 2 if wire_side == "top" else -blob_h / 2
    pts = dict(tab0=(P.TMP_TAB_PADS[0][0], sum(p[1] for p in P.TMP_TAB_PADS) / 2, t + 0.4),
               tab1=(P.ADA_L - P.TMP_TAB_PADS[0][0], sum(p[1] for p in P.TMP_TAB_PADS) / 2, t + 0.4),
               centre=(P.ADA_L / 2, P.ADA_W / 2, t / 2), wire=(12.7, -P.BLOB_OVER, zt), pad=(12.7, P.ADA_PAD_Y, zt),
               chip=(ADA_PARTS[kind][0][1], ADA_PARTS[kind][0][2], t + ADA_PARTS[kind][0][5]))
    return Board(name or kind, out, pts)


ADA_C = (P.ADA_L / 2, P.ADA_W / 2, 0)


# ------------------------------------------------------------------ SparkFun DRV2605L + coin motor
def drv_board():
    """Local = Eagle: 20.32 square, JP1 (6 pads) along x = 1.27, JP2 (motor) at x = 19.05, holes at y = 17.78."""
    t, s = P.DRV_PCB_T, P.DRV_S
    pcb = box(0, 0, 0, s, s, t) - union([cyl(x, y, -1, t + 1, P.DRV_HOLE_D, seg=32) for x, y in P.DRV_HOLES])
    x0, y0, x1, y1 = P.DRV_PARTS_BOX
    top = P.DRV_WIRE_SIDE == "top"
    zb0, zb1 = (t, t + P.BLOB_H) if top else (-P.BLOB_H, 0)
    zs0, zs1 = (-0.6, 0) if top else (t, t + 0.6)
    out = [("pcb", pcb), ("smd", box(x0, y0, t, x1, y1, t + P.DRV_PARTS_H)),
           ("blob", box(-P.BLOB_OVER, 0.0, zb0, 2.9, 15.3, zb1)), ("solder", box(0.2, 0.2, zs0, 2.4, 15.0, zs1)),
           ("blob", box(17.6, 5.0, zb0 if top else zb1 - 1.5, s + 0.6, 10.3, zb0 + 1.5 if top else zb1)), ("solder", box(18.0, 5.3, zs0, 20.1, 10.0, zs1))]
    zt = (zb0 + zb1) / 2
    return Board("DRV2605L", out, dict(jp1=(-P.BLOB_OVER, 7.62, zt), jp2=(s + 0.6, 7.62, zt), centre=(s / 2, s / 2, t / 2)))


def motor():
    return Board("motor", [("motor", cyl(0, 0, 0, P.MOTOR_T + P.MOTOR_ADH, P.MOTOR_D, seg=48))])


# ------------------------------------------------------------------ Seeed XIAO nRF52840
def xiao():
    """Local: origin = board centre, x toward the USB end, y = D0..D6 side, z 0 = PCB bottom, parts on +z."""
    t = P.XIAO_PCB_T
    hl, hw = P.XIAO_L / 2, P.XIAO_W / 2
    tip = hl + P.XIAO_USB_OVERHANG
    sx0, sy0, sx1, sy1 = P.XIAO_SHIELD
    rx, ry = P.XIAO_RESET_XY
    out = [("pcb", rbox(-hl, -hw, 0, hl, hw, t, 1.2)),
           ("usb", box(tip - P.XIAO_USB_LEN, -P.XIAO_USB_W / 2, t, tip, P.XIAO_USB_W / 2, t + P.XIAO_USB_H)),
           ("smd", box(sx0, sy0, t, sx1, sy1, t + P.XIAO_SHIELD_H)),
           ("smd", box(-9.6, -6.3, t, 9.6, 6.3, t + 0.6)),
           ("smd", cbox(rx, ry, t, 2.6, 1.6, t + P.XIAO_RESET_H))]
    for s in (-1, 1):   # castellated pad rows (photo b09c09de): solder + heat-shrunk wires on TOP of the pads, leaving sideways
        ya, yb = s * (P.XIAO_PAD_Y - 1.1), s * (hw + P.XIAO_SIDE_GAP * 0.75)
        out.append(("blob", box(-8.9, ya, t, 8.9, yb, t + P.XIAO_TOP_BLOB)))
        out.append(("solder", box(-8.9, s * (P.XIAO_PAD_Y - 0.6), -0.3, 8.9, s * (hw + 0.3), 0)))   # solder wicked to the underside
    ub = getattr(P, "XIAO_UNDER_BLOB", 0.0)
    if ub > 0:          # v4.1: glue + wire joints on the underside (envelope, ASSUMED height), between the corner rests
        out.append(("blob", box(-8.9, -6.9, -ub, 8.9, 6.9, 0)))
    bx = [p[0] for p in P.XIAO_BAT_PADS]
    out.append(("blob", box(min(bx) - 1.3, P.XIAO_BAT_PADS[0][1] - 1.3, -1.5, max(bx) + 1.3, P.XIAO_BAT_PADS[0][1] + 1.3, 0)))
    pts = dict(usb=(tip, 0, t + P.XIAO_USB_H / 2), reset=(rx, ry, t + P.XIAO_RESET_H),
               bat=(sum(bx) / 2, P.XIAO_BAT_PADS[0][1], -0.75), centre=(0, 0, t / 2))
    return Board("XIAO nRF52840", out, pts)


def usb_plug():
    """USB-C cable plug overmould, fully seated: front face at the receptacle tip (x = 0), body toward +x."""
    return Board("USB-C plug", [("plug", box(0.05, -P.USBC_PLUG_W / 2, -P.USBC_PLUG_H / 2, P.USBC_PLUG_LEN, P.USBC_PLUG_W / 2,
                                             P.USBC_PLUG_H / 2))])


# ------------------------------------------------------------------ Waveshare 1.69in LCD module
def lcd():
    """Local: origin = PCB centre, x = u (31.5 across), y = v (39 along; +v = away from the FPC tail / socket mouth),
    z 0 = PCB BACK face; glass toward +z; standoffs, socket, plug and parts toward -z."""
    t = P.LCD_PCB_T
    out = [("pcb", rbox(-P.LCD_W / 2, -P.LCD_L / 2, 0, P.LCD_W / 2, P.LCD_L / 2, t, P.LCD_PCB_R)),
           ("glass", rbox(-P.LCD_LCM_W / 2, -P.LCD_LCM_L / 2, t, P.LCD_LCM_W / 2, P.LCD_LCM_L / 2, t + P.LCD_LCM_T, 4.0))]
    sx, sy = P.LCD_STANDOFF_XY
    for a in (-1, 1):
        for b in (-1, 1):
            out.append(("standoff", cyl(a * sx, b * sy, -P.LCD_STANDOFF_H, 0, P.LCD_STANDOFF_D, seg=32)))
    v = P.LCD_SOCKET_V
    out.append(("socket", cbox(0, v, -P.LCD_SOCKET_H, P.LCD_SOCKET_W, P.LCD_SOCKET_L, 0)))
    if P.LCD_TAILS > 0:
        out.append(("socket", cbox(0, v + P.LCD_SOCKET_L / 2 + P.LCD_TAILS / 2, -0.7, 10.0, P.LCD_TAILS, 0)))
    mouth = v - P.LCD_SOCKET_L / 2
    out.append(("plug", box(-P.LCD_PLUG_W / 2, mouth - P.LCD_PLUG_OUT, -P.LCD_SOCKET_H + 0.3, P.LCD_PLUG_W / 2, mouth, -0.4)))
    u0, v0, u1, v1 = P.LCD_PARTS_BOX
    out.append(("smd", box(u0, v0, -P.LCD_PARTS_H, u1, v1, 0)))
    pts = dict(wire=(0, mouth - P.LCD_PLUG_OUT, -P.LCD_SOCKET_H / 2 - 0.05), aa=(0, P.LCD_AA_OFF_V, t + P.LCD_LCM_T),
               centre=(0, 0, 0))
    for i, (a, b) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
        pts[f"so{i}"] = (a * sx, b * sy, -P.LCD_STANDOFF_H)
    return Board("LCD 1.69in", out, pts)


# ------------------------------------------------------------------ battery, button
def battery():
    """Envelope. Local: x 0..L (leads leave the x = 0 end at one corner), y centred, z 0 = bottom."""
    L = getattr(P, "BAT_L_REAL", P.BAT_L)      # v4: your cell is longer than the datasheet max (fit test)
    k = getattr(P, "BAT_LEAD_CORNER", 0.0)
    return Board("battery LP601730", [("cell", box(0, -P.BAT_W / 2, 0, L, P.BAT_W / 2, P.BAT_T))],
                 dict(lead=(0, -P.BAT_W / 2 + k, P.BAT_T / 2), lead_far=(0, P.BAT_W / 2 - k, P.BAT_T / 2)))


def button():
    """v4.3b measured 5 x 5 tactile switch lying FLAT, plunger UP.  Local: body z 0..BODY_H, centred in x and y, plunger on +z.
    Under the body: glue + joint envelope BTN_JOINT_ROOM deep, minus a channel along x for the seat's bar (the centre of the
    switch's bottom is bare plastic; the legs and joints sit either side of it)."""
    s, h, j = P.BTN_S, P.BTN_BODY_H, P.BTN_JOINT_ROOM
    ch = P.BTN_BAR / 2 + P.GAP
    blob = box(-s / 2, -s / 2, -j, s / 2, s / 2, 0) - box(-s / 2 - 1, -ch, -j - 1, s / 2 + 1, ch, 0.01)
    legs = union([box(a * (s / 2 - 0.6) - 0.2, b * (s / 2 - 0.6), -j + 0.3, a * (s / 2 - 0.6) + 0.2, b * (s / 2 - 0.2), 0)
                  for a in (-1, 1) for b in (-1, 1)])
    return Board("button", [("body", box(-s / 2, -s / 2, 0, s / 2, s / 2, h)),
                            ("plunger", Manifold.cylinder(P.BTN_PLUNGER, P.BTN_CAP_D / 2, P.BTN_CAP_D / 2, 24).translate([0, 0, h])),
                            ("legs", legs), ("blob", blob)],
                 dict(wire=(-0.5, s / 2 - 0.5, -1.4), tip=(0, 0, h + P.BTN_PLUNGER)))


# ------------------------------------------------------------------ MAX30102 clone
def max30102():
    """Local: x 0 = VIN end .. MAX_L = GND end (long edge), y 0 = pad/wire edge .. MAX_W (hole edge), z 0 = PCB back,
    sensor parts at +z.  Part positions are read off photo 73fbbcdb (see params.MAX_PARTS)."""
    t = P.MAX_PCB_T
    hy = P.MAX_W - P.MAX_HOLE_IN_LONG if P.MAX_HOLE_EDGE == "opposite_wires" else P.MAX_HOLE_IN_LONG
    holes = [(P.MAX_HOLE_IN_SHORT, hy), (P.MAX_L - P.MAX_HOLE_IN_SHORT, hy)]
    pcb = box(0, 0, 0, P.MAX_L, P.MAX_W, t) - union([cyl(x, y, -1, t + 1, P.MAX_HOLE_D, seg=16) for x, y in holes])
    cx, cy = P.MAX_L / 2 + P.MAX_CHIP_X, P.MAX_W / 2 + P.MAX_CHIP_Y
    out = [("pcb", pcb), ("chip", cbox(cx, cy, t, P.MAX_CHIP_L, P.MAX_CHIP_W, t + P.MAX_CHIP_H))]
    for lab, x0, y0, x1, y1, h in P.MAX_PARTS:
        out.append(("smd", box(x0, y0, t, x1, y1, t + h)))
    if getattr(P, "MAX_WIRE_SIDE", "sensor") == "back":         # v6.2: wires, joints and glue on the back (z < 0)
        out += [("blob", box(0.3, -P.BLOB_OVER, -P.MAX_BLOB_H, P.MAX_L - 0.3, P.MAX_BLOB_STRIP, 0))]
        if P.MAX_FRONT_FILLET > 0:
            out.append(("solder", box(0.5, 0.3, t, P.MAX_L - 0.5, 2.6, t + P.MAX_FRONT_FILLET)))
        wz = -P.MAX_BLOB_H / 2
    else:
        out += [("blob", box(0.3, -P.BLOB_OVER, t, P.MAX_L - 0.3, P.MAX_BLOB_STRIP, t + P.MAX_BLOB_H)),
                ("solder", box(0.5, 0.3, -P.MAX_BACK_H, P.MAX_L - 0.5, 2.6, 0))]
        wz = t + P.MAX_BLOB_H / 2
    pts = dict(centre=(P.MAX_L / 2, P.MAX_W / 2, t / 2), wire=(P.MAX_L / 2, -P.BLOB_OVER, wz),
               chip=(cx, cy, t + P.MAX_CHIP_H), h0=(holes[0][0], holes[0][1], t), h1=(holes[1][0], holes[1][1], t))
    return Board("MAX30102", out, pts)


MAX_C = (P.MAX_L / 2, P.MAX_W / 2, 0)


# ------------------------------------------------------------------ wire bundles
def fillet3d(pts, r):
    """Round every interior corner of a 3-D polyline with an arc of radius r (shrinks r locally only if it cannot fit;
    returns (points, smallest radius used))."""
    pts = [np.array(p, float) for p in pts]
    out, rmin = [pts[0]], 1e9
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        u, v = a - b, c - b
        lu, lv = np.linalg.norm(u), np.linalg.norm(v)
        u, v = u / lu, v / lv
        ang = math.acos(float(np.clip(u @ v, -1, 1)))
        if abs(math.pi - ang) < 1e-4:
            out.append(b)
            continue
        lim_u = lu if i == 1 else lu / 2
        lim_v = lv if i == len(pts) - 2 else lv / 2
        t = min(r / math.tan(ang / 2), lim_u, lim_v)
        rr = t * math.tan(ang / 2)
        rmin = min(rmin, rr)
        bis = (u + v) / np.linalg.norm(u + v)
        cen = b + bis * (rr / math.sin(ang / 2))
        p1, p2 = b + u * t, b + v * t
        e1, e2 = (p1 - cen) / rr, (p2 - cen) / rr
        tot = math.acos(float(np.clip(e1 @ e2, -1, 1)))
        n = max(4, int(tot / math.radians(12)))
        for k in range(n + 1):
            w = k / n
            d = (math.sin((1 - w) * tot) * e1 + math.sin(w * tot) * e2) / math.sin(tot)
            out.append(cen + rr * d)
    out.append(pts[-1])
    return np.array(out), (rmin if rmin < 1e8 else float("inf"))


def path_radius(path):
    """Smallest bend radius along a polyline (circumradius of every 3 consecutive points; straight runs ignored)."""
    p = np.asarray(path, float)
    rmin = float("inf")
    for a, b, c in zip(p[:-2], p[1:-1], p[2:]):
        ab, bc, ca = np.linalg.norm(b - a), np.linalg.norm(c - b), np.linalg.norm(a - c)
        area2 = np.linalg.norm(np.cross(b - a, c - a))
        if area2 < 1e-6 * max(ab * bc, 1e-9):
            continue
        rmin = min(rmin, ab * bc * ca / (2 * area2))
    return rmin


class Wire:
    def __init__(self, name, pts, d=None, r=None, ends=(), note=""):
        self.name, self.d, self.note = name, (P.BUNDLE_D if d is None else d), note
        if r == 0:                      # v6.1: the path is already smooth (a designed C / arc): no filleting
            self.path = np.array(pts, float)
            self.rmin = path_radius(self.path)
        else:
            self.path, self.rmin = fillet3d(pts, P.CABLE_BEND_R if r is None else r)
        self.length = float(np.sum(np.linalg.norm(np.diff(self.path, axis=0), axis=1)))
        self.ends = set(ends)          # names of the boards it is soldered to (contact there is not a clash)
        sph = Manifold.sphere(self.d / 2, 10)
        segs = [Manifold.hull(sph.translate(list(self.path[i])) + sph.translate(list(self.path[i + 1])))
                for i in range(len(self.path) - 1)]
        self.solid = union(segs)

    def moved(self, M):
        w = Wire.__new__(Wire)
        w.__dict__.update(self.__dict__)
        w.solid = self.solid.transform(M)
        w.path = np.array([tp(M, p) for p in self.path])
        return w
