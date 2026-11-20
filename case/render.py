"""PNG renders with matplotlib (no GPU needed): iso, top, bottom, section."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

LIGHT = np.array([0.4, -0.5, 0.75])
LIGHT = LIGHT / np.linalg.norm(LIGHT)
VIEWS = {"iso": (28, -55), "top": (90, -90), "bottom": (-90, -90)}


def _shade(tm, base=(0.35, 0.62, 0.78), zsign=0):
    n = tm.face_normals
    k = 0.35 + 0.65 * np.clip(np.abs(n @ LIGHT), 0, 1)
    if zsign:  # top/bottom views: height-coded so pockets read as darker
        z = tm.triangles_center[:, 2]
        zn = (z - z.min()) / max(np.ptp(z), 1e-6)
        zn = zn if zsign > 0 else 1 - zn
        k = 0.25 + 0.75 * (0.25 * k + 0.75 * zn)
    return np.clip(np.outer(k, base), 0, 1)


def _draw(ax, tm, title, base=(0.35, 0.62, 0.78), zsign=0):
    tris = tm.vertices[tm.faces]
    pc = Poly3DCollection(tris, facecolors=_shade(tm, base, zsign), edgecolors="none", linewidths=0)
    ax.add_collection3d(pc)
    lo, hi = tm.bounds
    d = np.maximum(hi - lo, 1e-3)
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(tuple(d))
    ax.set_axis_off()
    ax.set_title(title, fontsize=10)


def render_all(tm, name, outdir, note="", half=None):
    import trimesh
    paths = []
    dims = tm.bounds[1] - tm.bounds[0]
    sub = f"{dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm (X along forearm, Z away from skin)"
    for v, (el, az) in VIEWS.items():
        fig = plt.figure(figsize=(8, 6), dpi=120)
        ax = fig.add_subplot(111, projection="3d", proj_type="ortho")
        ax.view_init(elev=el, azim=az)
        _draw(ax, tm, f"{name} - {v}\n{sub}", zsign={"top": 1, "bottom": -1}.get(v, 0))
        if note:
            fig.text(0.02, 0.02, note, fontsize=7)
        p = f"{outdir}/{name}_{v}.png"
        fig.savefig(p, bbox_inches="tight"); plt.close(fig); paths.append(p)
    # section: cut at the middle of Y, look from -Y at the cut face
    mid = (tm.bounds[0][1] + tm.bounds[1][1]) / 2
    if half is None:
        half = tm
    fig = plt.figure(figsize=(10, 5), dpi=120)
    ax = fig.add_subplot(111, projection="3d", proj_type="ortho")
    ax.view_init(elev=22, azim=-80)
    _draw(ax, half, f"{name} - section at mid-width (cut face toward you)", base=(0.85, 0.55, 0.35))
    p = f"{outdir}/{name}_section.png"
    fig.savefig(p, bbox_inches="tight"); plt.close(fig); paths.append(p)
    return paths


def render_cables(tm, name, outdir, paths):
    """Top view with every cable guide centreline drawn on top (red), labelled."""
    if not paths:
        return None
    fig = plt.figure(figsize=(9, 7), dpi=120)
    ax = fig.add_subplot(111, projection="3d", proj_type="ortho")
    ax.view_init(elev=90, azim=-90)
    dims = tm.bounds[1] - tm.bounds[0]
    _draw(ax, tm, f"{name} - cable paths from above (coloured line = wire bundle route, dot = where the path starts)", zsign=1)
    z = tm.bounds[1][2] + 0.5
    cols = ["#d62728", "#ff7f0e", "#9467bd", "#e377c2"]
    for i, (label, cl) in enumerate(paths):
        col = cols[i % len(cols)]
        ax.plot(cl[:, 0], cl[:, 1], [z] * len(cl), color=col, lw=3, zorder=10)
        ax.scatter([cl[0, 0]], [cl[0, 1]], [z], color=col, s=40, zorder=11)
        fig.text(0.05, 0.06 + 0.035 * i, "- " + label, color=col, fontsize=8)
    p = f"{outdir}/{name}_cables.png"
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p
