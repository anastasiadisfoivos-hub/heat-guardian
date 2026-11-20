"""v6.1 part positions on the flat (unrolled) band.
Band from the hand: BRAIN POD | gap | POWER POD | gap | SKIN ISLAND, AIR ISLAND beside the skin island (round the outer side).
Assembly frame: X along the forearm (hand -> elbow), Y across, Y 0 = midway between the two pod centrelines.
Every gap is POD_GAP of free neoprene between frame / lid skirts or island faces.  Excess wire is NOT spent as band length:
it is taken up inside the parts (the skin island's C bay); only the heart->air gap round the wrist follows hop 6."""
import params as P
import brain as B, power as W, island_skin as S, island_air

SK = P.FRAME_FIT + P.FRAME_WALL


H6_TAILS = (12.7 / 4 + 1.5) + 4.0                          # fan at TMP117 #2 + at the SHTC3 pad row


def h6_wire(shift, sx, sy, ax_=None):
    """hop 6 as one wire in the assembly frame for a given jog (the air island sits in line with the exit, GAP_AIR_MIN away)."""
    import twin as T
    pts = [(p[0] + S.OFF[0] + sx, p[1] + S.OFF[1] + sy, p[2]) for p in S.h6_points(shift, island_air.Z_ENT)]
    xe = pts[-1][0]
    ay = sy + S.W / 2 + P.GAP_AIR_MIN + island_air.LU / 2
    y_in = ay - island_air.LU / 2
    pts += [(xe, y_in - 1.0, island_air.Z_ENT), (xe, y_in + island_air.BU0 - 0.2, island_air.Z_ENT)]
    return T.Wire("hop 6 TMP117 #2 -> SHTC3 (4 wires)", pts, r=P.WIRE_BEND_R, ends=["TMP117 #2 (reference)", "SHTC3"]), xe, ay


def solve_h6(sx, sy):
    """jog length so hop 6 uses exactly its measured length (the jog is the 'labyrinth' for hop 6)"""
    target = P.HOP6_LEN[0] - P.HOP_SLACK - H6_TAILS
    lo, hi = 2 * P.WIRE_BEND_R + 0.05, 75.0
    if h6_wire(lo, sx, sy)[0].length >= target:
        return lo
    for _ in range(40):
        m = (lo + hi) / 2
        if h6_wire(m, sx, sy)[0].length < target:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


def hop6_gap():
    """hop 6 = TMP117 #2 pads -> straight +Y across the bay, the front wall, the gap, into the air island's pad edge."""
    tails = (12.7 / 4 + 1.5) + 4.0
    inside = (S.YI + P.WALL - S.H6_START[1]) + (island_air.BU0 + 0.5)
    g = P.HOP6_LEN[0] - P.HOP_SLACK - tails - inside
    return max(P.GAP_AIR_MIN, g)


def positions():
    lane = 0.0
    py = lane - (W.Y_H1 + W.OFF[1])
    by = py + W.OFF[1] + W.Y_H1 - B.OFF[1] - B.Y_H1
    sy = lane - (S.Y_H2 + S.OFF[1])                          # hop 2 crosses straight into the skin island's bay
    s = -(py + by) / 2
    py, by, sy = py + s, by + s, sy + s
    bx = 0.0
    px = bx + B.OX / 2 + SK + P.POD_GAP + SK + W.OX / 2
    sx = px + W.OX / 2 + SK + P.POD_GAP + S.L / 2
    shift = S.H6_SHIFT
    if P.AIR_ON_TOP:      # v6.6: the SHTC3 cage rides on top of TMP117 #2 (same frame as the skin island)
        return dict(brain=(bx, by), power=(px, py), skin=(sx, sy), air=(sx, sy), gap_pp=P.POD_GAP, gap_ps=P.POD_GAP,
                    gap_ha=0.0, h6_shift=0.0)
    w, ax, ay = h6_wire(shift, sx, sy)
    return dict(brain=(bx, by), power=(px, py), skin=(sx, sy), air=(ax, ay), gap_pp=P.POD_GAP, gap_ps=P.POD_GAP,
                gap_ha=P.GAP_AIR_MIN, h6_shift=shift)
