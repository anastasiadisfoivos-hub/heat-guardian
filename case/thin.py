"""Wall-thickness probe for the printed parts: samples the surface, shoots a ray straight into the material and
measures how far it is to the other side.  python3 thin.py [limit_mm]  -> clusters of thin spots per part."""
import sys, os
import numpy as np, trimesh
ROOT = os.path.dirname(os.path.abspath(__file__))


def probe(path, limit=0.79, n=60000):
    m = trimesh.load(path)
    pts, fid = trimesh.sample.sample_surface(m, n, seed=1)
    nrm = m.face_normals[fid]
    o = pts - nrm * 1e-3
    loc, ray, tri = m.ray.intersects_location(o, -nrm, multiple_hits=False)
    t = np.full(len(pts), np.inf)
    t[ray] = np.linalg.norm(loc - o[ray], axis=1)
    thin = (t < limit) & (t > 0.05)
    # ignore chamfer / cone tips: opposite face must be roughly parallel
    back = np.zeros(len(pts), bool)
    back[ray] = np.abs((m.face_normals[tri] * nrm[ray]).sum(1)) > 0.9
    thin &= back
    P, T = pts[thin], t[thin]
    cells = {}
    for p, tt in zip(P, T):
        k = tuple(np.floor(p / 4.0).astype(int))
        c = cells.setdefault(k, [0, 9, p])
        c[0] += 1
        if tt < c[1]:
            c[1], c[2] = tt, p
    return sorted(cells.values(), key=lambda c: -c[0]), thin.mean()


if __name__ == "__main__":
    lim = float(sys.argv[1]) if len(sys.argv) > 1 else 0.79
    for n in ("brain_pod", "brain_frame", "power_pod", "power_lid", "island_skin", "island_air"):
        cl, frac = probe(f"{ROOT}/out/stl/{n}.stl", lim)
        print(f"{n}: {frac * 100:.1f}% of the surface is thinner than {lim} mm")
        for cnt, tmin, p in cl[:14]:
            if cnt >= 6:
                print(f"   {cnt:5d} samples, thinnest {tmin:.2f} mm near x {p[0]:.1f} y {p[1]:.1f} z {p[2]:.1f} (STL / print coordinates)")
