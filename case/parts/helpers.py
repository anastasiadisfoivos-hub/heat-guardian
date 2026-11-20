"""HELPER PIECES (v3) - separate small prints for LATER, not part of tonight's print.  They hold a board flat and square
while hot glue sets, clip a board down onto its pins, and clamp a wire bundle where it leaves an island.
  helpers_clips    4 x wall clip A (ICM-20649 corners, heart island) + 4 x wall clip B (TMP117 #2 corners)
  helpers_jigs     press foot for the Adafruit boards, press foot for the MAX30102, spacer for the strap slot (TMP117 #1)
  helpers_saddles  4 x wire saddle (glue one over each bundle just outside an island exit)
Every piece is drawn the way it lies on the bed (no supports)."""
import numpy as np
from manifold3d import CrossSection, FillRule
from geo import box, cbox, cyl, union
import params as P
import island_heart as H

CLIP_W = 4.0            # DESIGN  clip width along the wall
CLIP_T = 1.4            # DESIGN  clip thickness
CLIP_TAB = 1.4          # DESIGN  how far the tab reaches in over the board (stops short of the pin tip in the board's hole)
CLIP_FIT = 0.2          # MEASURED coupon: 0.2 slot fits by hand


def wall_clip(drop, leg, wall=P.WALL):
    """C-clip that rides on a wall top and presses a board corner down.  drop = wall top - board top (+ = board lower).
    Drawn lying on its side (the C profile on the bed): the layers run round the C, so the hook cannot split."""
    a = wall + CLIP_FIT
    prof = [(a + CLIP_T, -leg), (a + CLIP_T, CLIP_T), (-P.CLEAR - CLIP_TAB, CLIP_T), (-P.CLEAR - CLIP_TAB, -drop),
            (-0.1, -drop), (-0.1, 0.0), (a, 0.0), (a, -leg)]
    return CrossSection([np.array(prof)], FillRule.Positive).extrude(CLIP_W)


def clips():
    da = H.Z_WALL_A - H.Z_ICM_TOP                        # ICM: board top is below the wall top
    db = (H.Z_T2 + 1.4) - (H.Z_T2 + P.PCB_T)              # TMP117 #2: board top is above its low end walls
    out = [wall_clip(da, 3.5).translate([i * 9.0, 0, 0]) for i in range(4)]
    out += [wall_clip(db, 3.0).translate([i * 9.0, 9.0, 0]) for i in range(4)]
    return union(out)


def press_foot_ada():
    """Plate on four tube feet that stand on the four hole corners of an Adafruit board (clear of sockets, parts and pin tips).
    Lay it on the board, put a rubber band round island + foot, glue, wait.  Drawn plate-down."""
    h = P.STEMMA_H + 0.5
    plate = box(0, 0, 0, P.ADA_L, P.ADA_W, 1.6) - cbox(P.ADA_L / 2, P.ADA_W / 2, -1, 9.0, 9.0, 3)   # window: never cover a sensor
    feet = union([cyl(x, y, 1.59, 1.6 + h, 4.2, seg=32) - cyl(x, y, 1.0, 9, 2.8, seg=24) for x, y in P.ADA_HOLES])
    return plate + feet


def press_foot_max():
    """Flat pusher for the back of the MAX30102 (relief over its solder points along the pad edge).  Drawn relief-up."""
    h = P.MAX_BLOB_H + 0.5 if getattr(P, "MAX_WIRE_SIDE", "sensor") == "back" else 0.9   # v6.2: the back carries the joints + glue
    t = h + 2.1
    return box(0, 0, 0, P.MAX_L, P.MAX_W, t) - box(-1, -1, t - h, P.MAX_L + 1, P.MAX_BLOB_STRIP + 0.5, t + 1)


def slot_spacer():
    """Tongue that slides into the strap slot and holds TMP117 #1 flat on the floor while its glue sets.  Drawn groove-up."""
    t = P.STRAP_SLOT_W - 0.2
    wx = (H.B_X1 - H.B_X0) - 2 * P.CLEAR - 0.4
    m = box(0, 0, 0, wx, H.W + 8.0, t)
    return m - box(1.0, -1, t - 0.8, 4.4, H.W + 9, t + 1)        # groove over the solder points of the pad row


def jigs():
    return union([press_foot_ada(), press_foot_max().translate([30, 0, 0]), slot_spacer().translate([52, 0, 0])])


def saddle():
    w, h, wall, ln, foot = P.CABLE_CH_W + 0.1, P.BUNDLE_D - 0.2, 1.2, 5.0, 3.0
    arch = box(-w / 2 - wall, 0, 0, w / 2 + wall, ln, h + wall) - box(-w / 2, -1, -1, w / 2, ln + 1, h)
    feet = union([box(s * (w / 2 + wall), 0, 0, s * (w / 2 + wall + foot), ln, 1.2) for s in (-1, 1)])
    return arch + feet


def saddles():
    return union([saddle().translate([i * 14.0, 0, 0]) for i in range(4)])


SETS = {"helpers_jigs": jigs, "helpers_saddles": saddles}     # v6.1: wall clips dropped (they fitted the v4 heart island)


def fit_check():
    """Each clip, placed on the heart island with the boards in, must not cut into a board, a wire or the print."""
    T = __import__("twin")
    body = H.build()
    boards, wires = H.twin()
    things = [body] + [b.solid for b in boards] + [w.solid for w in wires]
    bad = []

    def place(clip, x, s, z_wall):       # profile (u, v) -> island (y, z); u = 0 at the wall's inner face, pointing outward
        m = clip.rotate([90, 0, 90])     # extrusion -> X, u -> Y, v -> Z
        if s < 0:
            m = m.mirror([0, 1, 0])
        return m.translate([x, s * H.HB, z_wall])
    spots = [("A", wall_clip(H.Z_WALL_A - H.Z_ICM_TOP, 3.5), x, s, H.Z_WALL_A) for x in (H.IX0 + 1.0, H.IX1 - 4.6) for s in (-1, 1)]
    spots += [("B", wall_clip(-0.2, 3.0), x, s, H.Z_T2 + 1.4) for x in (H.TX0 + 0.6, H.TX1 - 4.6) for s in (-1, 1)]
    for name, c, x, s, z in spots:
        m = place(c, x, s, z)
        v = max((m ^ t).volume() for t in things)
        if v > 0.02:
            bad.append((name, round(x, 1), s, round(v, 2)))
    return bad
