"""Tiny CSG helper layer over manifold3d (the same kernel OpenSCAD uses).
All units mm. Z is up as printed unless a part says otherwise."""
import math
import numpy as np
from manifold3d import Manifold, CrossSection

SEG = 48  # circle segments


def box(x0, y0, z0, x1, y1, z1):
    """Axis-aligned box from two corners (order-independent)."""
    lo = [min(x0, x1), min(y0, y1), min(z0, z1)]
    hi = [max(x0, x1), max(y0, y1), max(z0, z1)]
    return Manifold.cube([hi[i] - lo[i] for i in range(3)]).translate(lo)


def cbox(cx, cy, z0, sx, sy, z1):
    """Box centred on (cx, cy) in XY, spanning z0..z1."""
    return box(cx - sx / 2, cy - sy / 2, z0, cx + sx / 2, cy + sy / 2, z1)


def cyl(cx, cy, z0, z1, d, d_top=None, seg=SEG):
    """Vertical cylinder (or cone if d_top given)."""
    r0 = d / 2
    r1 = (d_top / 2) if d_top is not None else r0
    return Manifold.cylinder(z1 - z0, r0, r1, seg).translate([cx, cy, z0])


def cyl_x(x0, x1, cy, cz, d, seg=192):
    """Cylinder whose axis runs along X (the forearm axis)."""
    return Manifold.cylinder(x1 - x0, d / 2, d / 2, seg).rotate([0, 90, 0]).translate([x0, cy, cz])


def cyl_y(cx, y0, y1, cz, d, seg=SEG):
    return Manifold.cylinder(y1 - y0, d / 2, d / 2, seg).rotate([-90, 0, 0]).translate([cx, y0, cz])


def rbox(x0, y0, z0, x1, y1, z1, r):
    """Box with vertical edges rounded to radius r."""
    sx, sy = abs(x1 - x0), abs(y1 - y0)
    r = min(r, sx / 2 - 0.01, sy / 2 - 0.01)
    cs = CrossSection.square([sx - 2 * r, sy - 2 * r]).offset(r, __import__("manifold3d").JoinType.Round, 2.0, SEG)
    return cs.extrude(abs(z1 - z0)).translate([min(x0, x1) + r, min(y0, y1) + r, min(z0, z1)])


def rslot_y(x0, x1, y0, y1, z0, z1, r):
    """Box running along Y whose four X-Z corners are rounded to radius r (for openings through a Y-facing wall)."""
    m = rbox(x0, z0, 0, x1, z1, abs(y1 - y0), r)          # rounded in (x, z), extruded along +z
    return m.rotate([90, 0, 0]).translate([0, max(y0, y1), 0])


def union(parts):
    parts = [p for p in parts if p is not None]
    return Manifold.batch_boolean(parts, __import__('manifold3d').OpType.Add) if parts else Manifold()


def dots(x, y, z, n, pitch=1.8, d=1.1, h=0.6):
    """n small bumps in a row = a printed 'label' (count the dots)."""
    return union([cyl(x + i * pitch, y, z, z + h, d, seg=16) for i in range(n)])


def skin_cut(x0, x1, width, z_contact, radius, center_y=0.0):
    """Concave forearm surface: returns the forearm cylinder (axis along X)
    whose top touches z = z_contact at y = center_y. Subtract it from a skirt."""
    return cyl_x(x0 - 1, x1 + 1, center_y, z_contact - radius, 2 * radius)


def sagitta(radius, half_width):
    if half_width >= radius:
        return radius
    return radius - math.sqrt(radius ** 2 - half_width ** 2)


def to_trimesh(m):
    import trimesh
    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3]
    f = np.asarray(mesh.tri_verts)
    return trimesh.Trimesh(vertices=v, faces=f, process=False)


def export_stl(m, path):
    tm = to_trimesh(m)
    tm.export(path)
    return tm


def size(m):
    b = m.bounding_box()
    return (b[3] - b[0], b[4] - b[1], b[5] - b[2])
