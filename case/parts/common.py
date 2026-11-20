"""Shared features: forearm-curved skin skirt + glue/stitch flanges, MAX30102 seat,
strain-relief tie posts, locating posts. Skin plane = Z 0 on the part centreline (Y = 0)."""
import math
from geo import box, cbox, cyl, cyl_x, rbox, union, sagitta
import params as P

WARN = []


def skin_skirt(x0, x1, W, R):
    """Material below Z 0 that follows the forearm (axis along X). Returns (skirt, forearm)."""
    if not P.SKIN_CURVE:
        return None, None
    half = W / 2 + P.FLANGE_W
    sag = sagitta(R, half) + 0.2
    arm = cyl_x(x0 - 5, x1 + 5, 0, -R, 2 * R)
    skirt = rbox(x0, -W / 2, -sag, x1, W / 2, 0.3, P.CORNER_R) - arm
    return skirt, arm


def flanges(x0, x1, W, R):
    """Flat-ish glue/stitch flanges on both Y sides, following the skin curve."""
    fx0, fx1 = x0 + 2.0, x1 - 2.0
    out = []
    holes = []
    n = max(2, int((fx1 - fx0) // 4.5))
    for s in (-1, 1):
        y_in, y_out = s * (W / 2 - 1.0), s * (W / 2 + P.FLANGE_W)
        yc = s * (W / 2 + P.FLANGE_W / 2 + 0.3)
        if P.SKIN_CURVE:
            ring = cyl_x(fx0, fx1, 0, -R, 2 * (R + P.FLANGE_T)) - cyl_x(fx0 - 1, fx1 + 1, 0, -R, 2 * R)
            out.append(ring ^ box(fx0, y_in, -40, fx1, y_out, 2.0))
            zc = -R + math.sqrt(max(R * R - yc * yc, 0))
        else:
            out.append(box(fx0, y_in, 0, fx1, y_out, P.FLANGE_T))
            zc = 0
        for i in range(n):
            x = fx0 + 2.0 + i * (fx1 - fx0 - 4.0) / max(n - 1, 1)
            holes.append(cyl(x, yc, zc - 5, zc + 5, P.STITCH_HOLE_D, seg=16))
    return union(out), union(holes)


def tie_post(x, y, outward, z_top=3.0):
    """External strain-relief anchor: a small block with a post to loop/tie/glue the bundle.
    outward = +1 (post sits at +X of the wall) or -1."""
    bw = P.TIE_POST_D + 2.4
    xc = x + outward * bw / 2
    blk = cbox(xc, y, 0, bw, 6.0, z_top)
    post = cyl(xc, y, z_top, z_top + 3.0, P.TIE_POST_D, seg=24)
    cap = cyl(xc, y, z_top + 3.0, z_top + 3.6, P.TIE_POST_D + 1.2, seg=24)  # keeps the loop on
    return union([blk, post, cap])


POSTS = []      # v7.0 registry for the fragility check: (label, pin_d, pin_h, boss_d, boss_h)


def locating_post(x, y, z_seat, hole_d, base_d=4.0, pcb_t=None, shrink=0.0, foot=0.0, pin=True, z_base=0.0, label="post"):
    """v7.0 board boss: a wide FLAT-TOPPED boss up to the board seat (the board rests on the flat top, nothing wedges in the hole)
    + a short straight pin through the board hole (pin = hole - PIN_UNDERSIZE - shrink, height PIN_MAX_H above the seat, tip
    chamfered 0.5 as a lead-in, a 0.2 root fillet that stays inside the hole).  foot > 0: the boss flares out 45 deg over its
    lowest `foot` mm (from z_base).  pin=False: a plain rest boss (no pin).
    (v6.x: a 45 deg centring cone from 3.0 mm down to the pin - printed in 0.2 layers it was wider than the 2.5 hole and the
    board rode up on it; with two posts it also allowed NO error in the hole spacing.)"""
    pin_d = hole_d - P.PIN_UNDERSIZE - shrink
    parts = [cyl(x, y, z_base, z_seat, base_d, seg=40)]
    if foot > 0:
        parts.append(cyl(x, y, z_base, z_base + foot, base_d + 2 * foot, base_d, seg=40))
    if pin:
        tip = 0.5
        z_top = z_seat + P.PIN_MAX_H
        rf = max(0.0, min(0.2, (hole_d - pin_d - 0.2) / 2))     # root fillet (radial), always inside the hole
        if rf > 0.02:
            parts.append(cyl(x, y, z_seat - 0.01, z_seat + rf, pin_d + 2 * rf, pin_d, seg=32))
        parts.append(cyl(x, y, z_seat - 0.01, z_top - tip, pin_d, seg=32))
        parts.append(cyl(x, y, z_top - tip - 0.001, z_top, pin_d, pin_d - 2 * tip * 0.6, seg=32))
        assert pin_d <= hole_d - 0.4 + 1e-9 and P.PIN_MAX_H <= 2 * pin_d, (label, pin_d)
    POSTS.append((label, pin_d if pin else None, P.PIN_MAX_H if pin else 0.0, base_d, z_seat - z_base))
    return union(parts)


def leadin(x0, y0, x1, y1, z_top, ch=0.6, sides="xXyY"):
    """v7.0 lead-in chamfer CUT for a rectangular seat (x0..x1, y0..y1): widens the opening by `ch` at z_top, tapering to the
    seat size `ch` below it, on the chosen sides (x = the x0 side, X = x1, y = y0, Y = y1).  Subtract it."""
    from manifold3d import Manifold
    ex = [ch if k in sides else 0.0 for k in "xyXY"]
    lo = box(x0, y0, z_top - ch, x1, y1, z_top - ch + 0.01)
    hi = box(x0 - ex[0], y0 - ex[1], z_top, x1 + ex[2], y1 + ex[3], z_top + 0.02)
    return Manifold.hull(lo + hi)


def max_seat(cx, cy, wire_side=-1):
    """MAX30102 seat. Board MAX_L along X, MAX_W along Y, sensor side down (skin = -Z).
    The wire/pad row is on the long edge at wire_side (-1 = -Y). Two blind sockets (for pressed-in metal pins)
    sit under the board's two holes; the board also rests on the sockets' pillars.
    Returns (add, cut, ring, info). Z 0 = skin plane (floor outer face)."""
    c = P.CLEAR
    zf = P.MAX_CHIP_RECESS + P.MAX_COMP_H           # PCB sensor face height
    ztop = zf + P.MAX_PCB_T
    sl, sw = P.MAX_L + 2 * c, P.MAX_W + 2 * c
    ol, ow = sl + 2 * 1.2, sw + 2 * 1.2
    relief_bottom = P.POCKET_FLOOR_MIN
    cap_limit = zf - relief_bottom - 0.1
    if cap_limit < P.MAX_COMP_H:
        WARN.append(f"MAX30102: parts OUTSIDE the window may be at most {cap_limit:.2f} mm tall "
                    f"(estimate {P.MAX_COMP_H}). If caps sit next to the chip, widen MAX_WIN_L/W to include them "
                    f"or raise MAX_CHIP_RECESS.")
    add = [cbox(cx, cy, 0, ol, ow, ztop + 0.6)]
    cut = [cbox(cx, cy, zf, sl, sw, ztop + 5),                                              # PCB pocket
           cbox(cx, cy, relief_bottom, sl - 2 * P.MAX_RIM, sw - 2 * P.MAX_RIM, zf + 0.01)]   # parts relief
    # wire edge (long edge): blob relief 3.5 below the PCB face + open side for the flat wire exit
    ye = cy + wire_side * sw / 2
    cut.append(box(cx - sl / 2, ye - wire_side * P.MAX_BLOB_STRIP, zf - P.MAX_BLOB_RELIEF,
                   cx + sl / 2, ye + wire_side * 2.0, ztop + 5))
    blob_past_skin = P.MAX_BLOB_H - zf
    if blob_past_skin > 0:
        WARN.append(f"MAX30102: the {P.MAX_BLOB_H} mm glue blobs at the wire edge reach {blob_past_skin:.1f} mm past "
                    f"the skin plane (the relief there is open to the skin). Flatten them to <= {zf:.1f} mm.")
    # pin sockets under the two holes (pillars from the floor up to the PCB face)
    hs = -wire_side if P.MAX_HOLE_EDGE == "opposite_wires" else wire_side
    hy = cy + hs * (P.MAX_W / 2 - P.MAX_HOLE_IN_LONG)
    depth = min(P.MAX_PIN_SOCKET_DEPTH, zf - P.POCKET_FLOOR_MIN)
    pillars, sockets = [], []
    for sx in (-1, 1):
        hx = cx + sx * (P.MAX_L / 2 - P.MAX_HOLE_IN_SHORT)
        pillars.append(cyl(hx, hy, 0, zf, P.MAX_PIN_SOCKET_D + 1.6, seg=24))
        sockets.append(cyl(hx, hy, zf - depth, zf + 0.01, P.MAX_PIN_SOCKET_D, seg=16))
    # window + light ring on the optical chip
    wx, wy = cx + P.MAX_CHIP_X, cy + hs * P.MAX_CHIP_Y
    cut.append(cbox(wx, wy, -5, P.MAX_WIN_L, P.MAX_WIN_W, zf + 0.01))
    ring = (cbox(wx, wy, -P.RING_H, P.MAX_WIN_L + 2 * P.RING_W, P.MAX_WIN_W + 2 * P.RING_W, 0.01)
            - cbox(wx, wy, -5, P.MAX_WIN_L, P.MAX_WIN_W, 5))
    info = dict(max_pcb_face=round(zf, 2), max_chip_behind_skin=P.MAX_CHIP_RECESS,
                max_chip_behind_ring_tip=round(P.MAX_CHIP_RECESS + P.RING_H, 2), max_seat_top=round(ztop + 0.6, 2),
                max_seat_outer=(round(ol, 2), round(ow, 2)), max_pin_socket_depth=round(depth, 2))
    # pillars are added after the cuts by the caller via the returned 'add' (pillars - sockets are inside 'ring')
    return union(add), union(cut), union([ring, union(pillars) - union(sockets)]), info
