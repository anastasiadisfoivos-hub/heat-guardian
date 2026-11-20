"""AIR ISLAND (v4, digital twin; v4: the wire enters at board height straight onto the pad edge - no floor lane - so the
30 mm hop from TMP117 #2 reaches.  Island 4.1 mm shorter across the wrist.) - end of the chain, beside the heart island on the outer side of the forearm,
far from the battery.  SHTC3 held >= 5 mm off the skin on 4 locating posts inside an open cage: big vents on
every side, open top with two guard bars over the board's socket ends (never over the sensor), solid floor so
skin heat and sweat do not rise into it.  The cavity under the board is the slack bay for spare wire.
Built in (u, v) coordinates: u = into the island from the entry wall, v = across; then turned so the entry wall
faces the heart island (-Y) and the board's long axis lies along the forearm (X)."""
import numpy as np
from geo import box, cbox, cyl, rbox, union
import params as P
import twin as T
from common import skin_skirt, flanges, locating_post, tie_post
from guides import guide, flared_exit, exit_post
import guides

c = P.CLEAR
e = c                                           # CLEAR is per side (as on the coupon)
UI = P.BLOB_OVER + c + P.ADA_W + c                # glue overhang at the pad edge + 17.78 board (v3 also had a 5.1 mm floor lane)
VI = P.ADA_L + 2 * c                             # 25.4 along v
LU, WV = UI + 2 * P.WALL, VI + 2 * P.WALL
Z_BOARD = P.AIR_STANDOFF
Z_GUARD0 = Z_BOARD + P.PCB_T + P.STEMMA_H + 0.4
Z_TOP = Z_GUARD0 + 1.2
BU0 = P.WALL + P.BLOB_OVER + c                   # board pad edge
Z_ENT = Z_BOARD + P.PCB_T + P.BLOB_H / 2         # the bundle comes in level with the pad-edge joints, through the end vent
EV = 0.0                                         # entry in line with the pad-edge centre
M_FINAL = T.xf((EV, -LU / 2, 0), rot=90)         # (u, v) -> island frame: X = EV - v, Y = u - LU/2   (entry at X = 0)
REPORT = {}


def _turn(m):
    return m.transform(M_FINAL)


def _board():
    return T.ada_board("shtc3", name="SHTC3").place(T.xf((BU0, P.ADA_L / 2, Z_BOARD), rot=-90))


def _path():
    return [(-P.EXIT_COLLAR - 3.0, EV, Z_ENT), (BU0 - 0.2, EV, Z_ENT)]


def build():
    import spacing
    R = P.skin_radius_at(abs(spacing.positions()["air"][1]))   # wrist curvature where the island actually sits (v6 frame: Y 0 = heart island)
    sht = _board()
    outer = rbox(0, -WV / 2, 0, LU, WV / 2, Z_TOP, P.CORNER_R)
    body = outer - box(P.WALL, -VI / 2, P.FLOOR, LU - P.WALL, VI / 2, 99)
    pil = 3.0
    vents = [box(pil, -WV / 2 - 1, P.FLOOR + 0.8, LU - pil, WV / 2 + 1, Z_GUARD0),
             box(-1, -WV / 2 + pil, P.FLOOR + P.CABLE_CH_D + 1.2, LU + 1, WV / 2 - pil, Z_GUARD0)]
    top_open = box(P.WALL, -VI / 2 + 3.5, Z_GUARD0 - 0.01, LU - P.WALL, VI / 2 - 3.5, 99)
    body = body - union(vents) - top_open
    for s in (-1, 1):   # guard bars over the board's short ends (sockets), never over the sensor
        body = body + box(P.WALL - 0.01, s * VI / 2, Z_GUARD0, LU - P.WALL + 0.01, s * (VI / 2 - 3.5), Z_TOP)
    for hx, hy in P.ADA_HOLES:
        p = sht.loc((hx, hy, 0))
        body = body + locating_post(p[0], p[1], Z_BOARD, P.ADA_HOLE_D)
    guides.PATHS.clear()
    assert Z_ENT + P.BUNDLE_D / 2 + 0.3 < Z_GUARD0 and Z_ENT - P.BUNDLE_D / 2 > P.FLOOR + P.CABLE_CH_D + 1.2, "entry not inside the end vent"
    body = body + tie_post(0, EV + 11.2, -1, z_top=Z_ENT - 3.0)    # strain post beside the entry (glue the bundle to it)
    # v6.1: big top-open entry (OPEN_W wide, from the floor up): the hop-6 bundle drops in from above, never threaded
    hw = min(P.OPEN_W / 2, VI / 2 - 3.6)
    body = body - box(-5, EV - hw, P.FLOOR, P.WALL + 0.01, EV + hw, 99)
    ch = sht.pt("chip")
    keep = cbox(ch[0], ch[1], Z_BOARD + P.PCB_T, P.SHTC3_OPEN, P.SHTC3_OPEN, 99)
    assert (body ^ keep).volume() < 1e-6, "something covers the SHTC3 opening"
    body = _turn(body)
    skirt, arm = skin_skirt(EV - WV / 2, EV + WV / 2, LU, R)     # no flanges here: tie/stitch round the 4 corner pillars
    if skirt is not None:
        body = body + skirt
    import math
    REPORT.update(skin_radius=round(R, 1), foot=round(R - math.sqrt(max(R * R - (LU / 2) ** 2, 0)), 1) if P.SKIN_CURVE else 0, board_bottom_above_skin=Z_BOARD, guard_bars_z=round(Z_GUARD0, 1), slack_bay=f"{P.ADA_W:.0f} x {P.ADA_L:.0f} x {Z_BOARD - P.FLOOR:.0f} mm under the board")
    return body


def twin():
    sht = _board()
    w = T.Wire("hop 6 TMP117 #2 -> SHTC3, air-island part", _path(), ends=["SHTC3"])
    b = T.Placed(sht.name, [(k, m.transform(M_FINAL)) for k, m in sht.solids], M_FINAL, {})
    return [b], [w.moved(M_FINAL)]


SECTION_Y = 0.0


# ================================================================ v6.6: the SHTC3 rides ON TOP of TMP117 #2 (vented cage)
if P.AIR_ON_TOP:
    import island_skin as S
    _GZ = 0.0

    def _sx():
        """SHTC3 footprint (interior coords of the skin island): AIR_DX toward the elbow end of TMP117 #2"""
        x0 = S.TX0 + P.AIR_DX
        return x0, Y0_B, x0 + P.ADA_L, S.Y_E

    Y0_B = S.Y_E - P.ADA_W
    Z_GUARD0 = S.Z_SB + P.PCB_T + P.STEMMA_H + 0.4
    Z_TOP = Z_GUARD0                                  # corner posts protect the sockets' height; nothing over the board
    Z_ENT = S.Z_SH_W

    def _board():
        return T.ada_board("shtc3", name="SHTC3").place(T.xf((S.TX1 + P.AIR_DX, S.Y_E, S.Z_SB), rot=180))

    def _cage():
        """legs (keyed into the plate) -> ring under the SHTC3's edges (4 locating pins) -> 4 corner posts -> 2 guard bars over the
        socket ends.  Open on all four sides between the legs: the SHTC3 reads room air, >= AIR_GAP_OVER_T2 of still air under it."""
        bx0, by0, bx1, by1 = _sx()
        feet = S.cage_feet()
        zr0 = S.Z_SB - P.CAGE_RING_T
        parts = [box(x0, y0, S.Z_T2 - 0.4, x1, y1, zr0 + 0.01) for x0, y0, x1, y1 in feet]
        rx0 = min(f[0] for f in feet)
        rx1 = max(bx1 + c, max(f[2] for f in feet))
        ry0 = min(f[1] for f in feet)
        ring = box(rx0, ry0, zr0, rx1, by1, S.Z_SB) - box(bx0 + P.CAGE_RING_W, by0 + P.CAGE_RING_W, zr0 - 1, bx1 - P.CAGE_RING_W, by1 - P.CAGE_RING_W, 99)
        ring = ring - box(min(f[2] for f in feet) + 0.01, ry0 - 1, zr0 - 1, bx0 + P.CAGE_RING_W - 0.01, by0 + 0.01, 99)   # trim the hand-end back corner
        sht = _board()
        sx0, sy0, sx1, sy1 = S._foot(sht.part("solder"), 0.3)        # the SHTC3's solder points under its pad row
        ring = ring - box(sx0, sy0, zr0 - 1, sx1, sy1 + 2, 99)
        parts.append(ring)
        for hx, hy in P.ADA_HOLES:
            q = sht.loc((hx, hy, 0))
            parts.append(locating_post(q[0], q[1], S.Z_SB, P.ADA_HOLE_D, base_d=3.4) ^ box(q[0] - 3, q[1] - 3, zr0 + 0.01, q[0] + 3, q[1] + 3, 99))
        pw, k = 1.6, P.AIR_POCKET_CLEAR
        for x0 in (bx0 - k - pw, bx1 + k):              # 4 corner posts OUTSIDE the pocket (board outline + 0.5 per side)
            for y0 in (by0 - k - pw, by1 - pw):
                parts.append(box(x0, y0, zr0, x0 + pw, y0 + pw, Z_TOP))
                # v6.7.1: tie each post into the ring under the board's edge band (it floated before) - a solid bracket at ring
                # height, below the board seat, so the post grows out of the ring when printed from the feet up
                xin = bx0 + P.CAGE_RING_W - 0.5 if x0 < bx0 else bx1 - P.CAGE_RING_W + 0.5
                yin = by0 + P.CAGE_RING_W - 0.5 if y0 < by0 else by1 - P.CAGE_RING_W + 0.5
                parts.append(box(min(x0, xin), min(y0, yin), zr0, max(x0 + pw, xin), max(y0 + pw, yin), S.Z_SB))
        # v6.6: no guard bars over the board any more - the SHTC3 (wires + glue on) drops straight in from the top
        body = union(parts)
        ch = sht.pt("chip")
        keep = cbox(ch[0], ch[1], S.Z_SB + P.PCB_T, P.SHTC3_OPEN, P.SHTC3_OPEN, 99)
        assert (body ^ keep).volume() < 1e-6, "something covers the SHTC3 opening"
        # drop-in check: the pocket (outline + AIR_POCKET_CLEAR) is free from the board seat up, and the pad edge has
        # AIR_PAD_ROOM more for the joints + glue blobs with the wires going straight down that side
        pocket = rbox(bx0 - k, by0 - k, S.Z_SB + 0.01, bx1 + k, by1 + P.AIR_PAD_ROOM, 99, P.ADA_CORNER_R)
        pins = union([cyl(*sht.loc((hx, hy, 0))[:2], S.Z_SB - 0.5, 99, P.ADA_HOLE_D + 0.2, seg=24) for hx, hy in P.ADA_HOLES])
        assert ((body - pins) ^ pocket).volume() < 1e-6, "the SHTC3 cannot drop in from the top"
        return body

    def build():
        body = _cage().translate(list(S.OFF))
        bx0, by0, bx1, by1 = _sx()
        REPORT.clear()
        REPORT.update(mount="keyed feet on TMP117 #2's plate (glue)", shtc3_bottom=round(S.Z_SB, 2),
                      still_air_over_tmp2=P.AIR_GAP_OVER_T2, top=round(Z_TOP, 2), vents="open on 4 sides and on top (drop-in)",
                      pocket=f"{P.ADA_L:.1f} x {P.ADA_W:.1f} + {P.AIR_POCKET_CLEAR} per side, + {P.AIR_PAD_ROOM} at the pad edge")
        return body

    def twin():
        sht = _board()
        b = T.Placed(sht.name, [(k, m.translate(list(S.OFF))) for k, m in sht.solids], sht.M.copy(), {})
        b.M[:, 3] += S.OFF
        return [b], []

    _bb = None

    def _dims():
        b = _cage().bounding_box()
        return b[3] - b[0], b[4] - b[1]
    WV, LU = _dims()
    PRINT_FLIP = False
    PRINT_DROP = True          # STL starts at the bed (the feet), not at its height on the band
