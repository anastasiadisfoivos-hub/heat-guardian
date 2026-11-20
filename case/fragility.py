"""v7.0 FRAGILITY CHECK - fails the build if a printed part has anything that can break while it is glued and fitted.
Runs on the PRINT files (out/stl_flat/*.stl, print orientation, bed at z 0):

 1. THIN PROBE   - samples the whole surface, shoots a ray straight into the material and measures the distance to the opposite
                   (parallel) face.  Anything under MIN_T (1.2 mm: walls, floors, webs, ribs, lips) fails, except inside the
                   listed exception boxes (each with its own floor limit and a written reason).
 2. SLENDER POST - slices the part every 0.2 mm, follows every free-standing island (post, pin, lip, tongue; < 8 mm long) upward and
                   fails if any stretch of it is taller than 2 x its own width.

python3 fragility.py            -> report for all printed parts (exit 1 on a failure)"""
import os, sys
import numpy as np, trimesh

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "parts"))
PRINTED = ["brain_pod", "brain_frame", "power_pod", "power_lid", "island_skin", "island_shelf"]
TOL = 0.015


def exceptions(part):
    """[(label, (x0, y0, z0, x1, y1, z1) in print coordinates, lowest allowed thickness, reason)]"""
    import params as P
    if part != "island_skin":
        return []
    import island_skin as S
    ox, oy = S.OFF[0], S.OFF[1]
    return [
        ("TMP117 #1 seat floor", (S.TX0 - S.cb - 0.1 + ox, -0.1 + oy, -0.1, S.TX1 + S.cb + 0.1 + ox, S.Y_E + 0.1 + oy, S.Z_T1F + 0.1), 0.6,
         "0.6 mm: the chip is 0.8 mm tall and must stand 0.2 mm past the skin face, so the board face is 0.6 above the bed. A full sheet "
         "printed on the bed, joined to the back wall and (v7.0) to the two front pillars; it is only ever pressed flat against the bed / the skin."),
        ("MAX30102 pocket floor", (S.MAX_X0 - S.MC - P.MAX_RIM - 0.1 + ox, S.MAX_Y0 - S.MC - 0.1 + oy, -0.1, S.MAX_X1 + S.MC + P.MAX_RIM + 0.1 + ox,
                                   S.Y_E + 0.1 + oy, S.Z_MF + 0.1), 0.8,
         "0.8-1.05 mm: the optical chip is 1.55 mm tall and stands 0.05 mm past the skin face, so the board face is 1.5 above the bed; "
         "1.05 under the board, 0.8 under the 0.6 mm resistors and under the two pin sockets. Printed on the bed, carries no load."),
    ]


def thin_probe(mesh, limit, exc, n=160000, seed=1):
    pts, fid = trimesh.sample.sample_surface(mesh, n, seed=seed)
    nrm = mesh.face_normals[fid]
    o = pts - nrm * 1e-3
    loc, ray, tri = mesh.ray.intersects_location(o, -nrm, multiple_hits=False)
    t = np.full(len(pts), np.inf)
    t[ray] = np.linalg.norm(loc - o[ray], axis=1)
    par = np.zeros(len(pts), bool)
    par[ray] = np.abs((mesh.face_normals[tri] * nrm[ray]).sum(1)) > 0.9      # opposite face parallel: a real wall / floor, not a chamfer
    thin = (t < limit - TOL) & (t > 0.03) & par
    mid = pts - nrm * (np.where(np.isfinite(t), t, 0.0)[:, None] / 2)
    used = {}
    bad = thin.copy()
    for lab, b, lim, _ in exc:
        ins = np.all((mid >= np.array(b[:3])) & (mid <= np.array(b[3:])), axis=1)
        ok = ins & thin & (t >= lim - TOL)
        bad &= ~ok
        if ok.any():
            used[lab] = (float(t[ok].min()), int(ok.sum()))
    cells = {}
    for p, tt in zip(pts[bad], t[bad]):
        k = tuple(np.floor(p / 2.0).astype(int))
        c = cells.setdefault(k, [0, 9.0, p])
        c[0] += 1
        if tt < c[1]:
            c[1], c[2] = tt, p
    fails = [(cnt, tmin, p) for cnt, tmin, p in cells.values() if cnt >= 4]
    return sorted(fails, key=lambda c: -c[0]), used, float(t[par & (t > 0.03)].min())


def slender(mesh, dz=0.2, max_len=8.0, ratio=2.0):
    """free-standing islands in the slices, followed upward; -> [(w, run height, z0, (x, y))] where a stretch is taller than ratio x w"""
    from shapely.geometry import Polygon
    z0, z1 = mesh.bounds[0][2], mesh.bounds[1][2]
    cols, done = [], []
    for z in np.arange(z0 + dz / 2, z1, dz):
        sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        polys = []
        if sec is not None:
            p2, T = sec.to_2D()
            from shapely.affinity import affine_transform
            for pg in p2.polygons_full:
                if pg is None or pg.area < 0.05:
                    continue
                pg = affine_transform(pg, [T[0, 0], T[0, 1], T[1, 0], T[1, 1], T[0, 3], T[1, 3]])     # slice frame -> print coordinates
                r = pg.minimum_rotated_rectangle
                xs, ys = r.exterior.coords.xy
                e = sorted([np.hypot(xs[1] - xs[0], ys[1] - ys[0]), np.hypot(xs[2] - xs[1], ys[2] - ys[1])])
                if e[1] < max_len:
                    polys.append((pg, e[0], (float(pg.centroid.x), float(pg.centroid.y))))
        nxt = []
        for pg, w, cxy in polys:
            hit = None
            for col in cols:
                if col["poly"].intersects(pg) and col["poly"].intersection(pg).area > 0.5 * min(col["poly"].area, pg.area):
                    hit = col
                    break
            if hit is not None and not hit.get("taken"):
                hit["taken"] = True
                hit["poly"] = pg
                hit["ws"].append(w)
                nxt.append(hit)
            else:
                nxt.append(dict(poly=pg, ws=[w], z0=z - dz / 2, xy=cxy))
        done += [c for c in cols if not c.get("taken")]
        for c in nxt:
            c.pop("taken", None)
        cols = nxt
    out = []
    for c in done + cols:
        ws = np.array(c["ws"])
        worst = None
        for w in sorted(set(np.round(ws, 2))):
            m = ws <= w * 1.1
            run = best = 0
            for v in m:
                run = run + 1 if v else 0
                best = max(best, run)
            h = best * dz
            if h > ratio * w + dz + 1e-6 and (worst is None or h / w > worst[1] / worst[0]):
                worst = (float(w), float(h))
        if worst:
            out.append((worst[0], worst[1], c["z0"], c["xy"]))
    return out


def check(part, path=None, verbose=True):
    import params as P
    path = path or f"{ROOT}/out/stl_flat/{part}.stl"
    mesh = trimesh.load(path)
    exc = exceptions(part)
    fails, used, tmin = thin_probe(mesh, P.MIN_T, exc)
    sl = slender(mesh)
    lines = [f"{part}: thinnest wall/floor found {tmin:.2f} mm; {len(fails)} thin spot(s) under {P.MIN_T}; {len(sl)} slender post(s)"]
    for lab, (t, n) in used.items():
        lines.append(f"   exception in use: {lab}: thinnest {t:.2f} mm")
    for cnt, t, p in fails[:12]:
        lines.append(f"   THIN {t:.2f} mm near x {p[0]:.1f} y {p[1]:.1f} z {p[2]:.1f} (print coordinates, {cnt} samples)")
    for w, h, z, xy in sl:
        lines.append(f"   SLENDER {w:.2f} wide x {h:.1f} tall, from z {z:.1f} at x {xy[0]:.1f} y {xy[1]:.1f}")
    if verbose:
        print("\n".join(lines))
    return (len(fails) + len(sl)) == 0, lines


def main(parts=PRINTED):
    ok, out = True, ["FRAGILITY CHECK (v7.0): nothing under 1.2 mm, no post taller than 2 x its width - print files in out/stl_flat/"]
    for p in parts:
        good, lines = check(p)
        ok &= good
        out += lines
    out.append("EXCEPTIONS (the only features under 1.2 mm, by design):")
    for p in parts:
        for lab, _, lim, why in exceptions(p):
            out.append(f" - {p} / {lab} (>= {lim} mm): {why}")
    out.append("RESULT: " + ("PASS" if ok else "FAIL"))
    with open(f"{ROOT}/out/FRAGILITY.txt", "w") as f:
        f.write("\n".join(out) + "\n")
    print(out[-1])
    return ok


if __name__ == "__main__":
    os.environ.setdefault("HG_FLAT", "1")
    sys.exit(0 if main(sys.argv[1:] or PRINTED) else 1)
