"""Curved, top-open cable guides.
A guide is a centreline (waypoints, corners filleted to CABLE_BEND_R) on a floor height.
It produces: groove walls (added), the groove channel (cut, open to the top), snap lips every
CABLE_LIP_PITCH (chamfered 45 deg underneath -> printable skin-side down), and optionally a
flared, filleted exit through an X-facing outer wall + an outside strain-relief post."""
import math
import numpy as np
from shapely.geometry import LineString, Polygon, box as sbox
from shapely.ops import unary_union
from manifold3d import CrossSection, FillRule, Manifold
from geo import box, cyl, union, cyl_y
import params as P

PATHS = []   # (name, centreline xy array) - for the cable-path overlay renders


def fillet_path(pts, r):
    """Replace each interior corner of a polyline with a circular arc of centreline radius r."""
    pts = [np.array(p, float) for p in pts]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        u, v = (a - b), (c - b)
        lu, lv = np.linalg.norm(u), np.linalg.norm(v)
        u, v = u / lu, v / lv
        ang = math.acos(np.clip(u @ v, -1, 1))          # interior angle
        if abs(math.pi - ang) < 1e-6:
            out.append(b); continue
        t = r / math.tan(ang / 2)
        if t > min(lu, lv) / (1 if i in (1, len(pts) - 2) else 2) + 1e-6:
            raise ValueError(f"bend radius {r} does not fit at waypoint {b}")
        p1, p2 = b + u * t, b + v * t
        bis = (u + v) / np.linalg.norm(u + v)
        cen = b + bis * (r / math.sin(ang / 2))
        a1 = math.atan2(*(p1 - cen)[::-1]); a2 = math.atan2(*(p2 - cen)[::-1])
        da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        n = max(6, int(abs(da) / math.radians(7.5)))
        for k in range(n + 1):
            th = a1 + da * k / n
            out.append(cen + r * np.array([math.cos(th), math.sin(th)]))
    out.append(pts[-1])
    return np.array(out)


def _extrude(poly, z0, z1):
    if poly.is_empty:
        return Manifold()
    geoms = list(poly.geoms) if poly.geom_type == "MultiPolygon" else [poly]
    contours = []
    for g in geoms:
        contours.append(np.array(g.exterior.coords)[:-1])
        for h in g.interiors:
            contours.append(np.array(h.coords)[:-1])
    cs = CrossSection(contours, FillRule.EvenOdd)
    return cs.extrude(z1 - z0).translate([0, 0, z0])


def _lip(p, t, side, w, z_top):
    """Snap lip at point p, tangent t, on side (+1 left / -1 right): protrudes CABLE_LIP into the
    groove at the top, 45 deg chamfer underneath."""
    n = np.array([-t[1], t[0]]) * side
    e = w / 2
    L, lip = P.CABLE_LIP_LEN / 2, P.CABLE_LIP
    pts = []
    for s in (-L, L):
        base = p + t * s
        pts += [list(base + n * e) + [z_top], list(base + n * (e - lip)) + [z_top],
                list(base + n * (e - lip)) + [z_top - 0.4], list(base + n * e) + [z_top - 0.4 - lip],
                list(base + n * (e + 0.3)) + [z_top], list(base + n * (e + 0.3)) + [z_top - 0.4 - lip]]
    return Manifold.hull_points(np.array(pts))


def guide(name, pts, z_floor, w=None, depth=None, lips=True, z_cut_top=99):
    """Returns (add, cut). pts: waypoints in XY. Groove floor at z_floor, open to the top."""
    w = P.CABLE_CH_W if w is None else w
    depth = P.CABLE_CH_D if depth is None else depth
    cl = fillet_path(pts, P.CABLE_BEND_R)
    PATHS.append((name, cl))
    line = LineString(cl)
    groove = line.buffer(w / 2, cap_style=2, join_style=1)
    outer = line.buffer(w / 2 + P.CABLE_WALL, cap_style=2, join_style=1)
    walls = outer.difference(groove)
    z_top = z_floor + depth
    add = [_extrude(walls, z_floor - 0.5, z_top)]
    # snap lips, alternating sides, every CABLE_LIP_PITCH along the path (skip the ends)
    if lips:
        L = line.length
        k, s = 0, 1
        d = P.CABLE_LIP_PITCH / 2
        while d < L - 2.0:
            p = np.array(line.interpolate(d).coords[0])
            q = np.array(line.interpolate(min(d + 0.5, L)).coords[0])
            t = (q - p) / max(np.linalg.norm(q - p), 1e-9)
            add.append(_lip(p, t, s, w, z_top))
            s, d = -s, d + P.CABLE_LIP_PITCH
    cut = _extrude(groove, z_floor, z_cut_top)
    return union(add), cut


def flared_exit(x_wall_in, x_wall_out, yc, z_floor, w=None, z_top=None):
    """Top-open, flared opening through an X-facing wall (faces at x_wall_in / x_wall_out; the flare widens
    toward x_wall_out). The wall is thickened locally by a collar (EXIT_COLLAR) so every vertical edge can be
    filleted at EXIT_FILLET_R; the bottom outer edge is rounded too. Returns (collar_add, cut, x_outer)."""
    w = P.CABLE_CH_W if w is None else w
    s = 1 if x_wall_out > x_wall_in else -1
    f, r = P.EXIT_FLARE, P.EXIT_FILLET_R
    xo = x_wall_out + s * P.EXIT_COLLAR
    z_top = z_floor + P.CABLE_CH_D + 1.0 if z_top is None else z_top
    half = w / 2 + f + 2 * r + 1.0
    collar = box(x_wall_in, yc - half, 0, xo, yc + half, z_top)
    funnel = Polygon([(x_wall_in - s * 0.5, yc - w / 2), (x_wall_in + s * 0.6, yc - w / 2), (xo, yc - w / 2 - f),
                      (xo + s * 3, yc - w / 2 - f), (xo + s * 3, yc + w / 2 + f), (xo, yc + w / 2 + f),
                      (x_wall_in + s * 0.6, yc + w / 2), (x_wall_in - s * 0.5, yc + w / 2)])
    slab = sbox(min(x_wall_in, xo), yc - half, max(x_wall_in, xo), yc + half)
    big = sbox(min(x_wall_in, xo), yc - half - 3 * r, max(x_wall_in, xo), yc + half + 3 * r)
    mat = big.difference(funnel).buffer(-r, join_style=1).buffer(r, join_style=1).intersection(slab)  # fillet edges
    cut2d = slab.difference(mat).union(funnel)
    cut = _extrude(cut2d, z_floor, 99)
    rr = r
    edge = (box(xo - s * rr, yc - w / 2 - f - 1, z_floor - rr, xo + s * 0.01, yc + w / 2 + f + 1, z_floor + 0.01)
            - cyl_y(xo - s * rr, yc - w / 2 - f - 2, yc + w / 2 + f + 2, z_floor - rr, 2 * rr))
    return collar, union([cut, edge]), xo


def exit_post(x_wall_out, yc, z_floor, s):
    """Outside strain-relief post right after an exit: shelf top just under the groove floor,
    post offset sideways so the bundle wraps half a turn round it."""
    zt = max(z_floor - 0.2, 1.0)
    px, py = x_wall_out + s * (2.2 + P.TIE_POST_D / 2), yc + P.CABLE_CH_W / 2 + 0.8 + P.TIE_POST_D / 2
    shelf = box(x_wall_out - s * 0.5, yc - P.CABLE_CH_W / 2 - 1.5, 0, px + s * (P.TIE_POST_D / 2 + 1.2), py + P.TIE_POST_D / 2 + 1.2, zt)
    post = cyl(px, py, zt, zt + 3.0, P.TIE_POST_D, seg=24)
    cap = cyl(px, py, zt + 3.0, zt + 3.6, P.TIE_POST_D + 1.2, seg=24)
    return union([shelf, post, cap])
