"""Assembly renders: printed parts + the digital twin (boards, sockets, glue blobs, wires) in one picture.
All triangles go into ONE depth-sorted collection so nearer things hide farther ones correctly."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.patches import Patch
from matplotlib.collections import PolyCollection

LIGHT = np.array([0.35, -0.45, 0.82])
LIGHT = LIGHT / np.linalg.norm(LIGHT)
COL = {  # twin colours by solid key
    "pcb": (0.10, 0.38, 0.22), "socket": (0.93, 0.89, 0.78), "chip": (0.08, 0.08, 0.08), "smd": (0.45, 0.42, 0.36),
    "blob": (0.98, 0.78, 0.25), "solder": (0.75, 0.75, 0.78), "usb": (0.80, 0.80, 0.83), "glass": (0.12, 0.14, 0.20),
    "standoff": (0.85, 0.65, 0.20), "plug": (0.95, 0.95, 0.95), "cell": (0.78, 0.80, 0.84), "body": (0.15, 0.15, 0.15),
    "plunger": (0.15, 0.15, 0.15), "legs": (0.7, 0.7, 0.7), "motor": (0.72, 0.72, 0.75), "foam": (0.25, 0.25, 0.25),
}
PCB_COL = {"XIAO nRF52840": (0.12, 0.12, 0.13), "DRV2605L": (0.75, 0.12, 0.12), "LCD 1.69in": (0.10, 0.25, 0.65),
           "MAX30102": (0.10, 0.55, 0.25), "USB-C plug": (0.3, 0.3, 0.32)}
WIRE_COLS = ["#d62728", "#1f77b4", "#9467bd", "#ff7f0e", "#e377c2", "#17becf", "#bcbd22", "#8c564b"]
PRINT_COL = (0.55, 0.72, 0.85)


def _tris(m):
    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3]
    f = np.asarray(mesh.tri_verts)
    return v[f]


def _shade(tris, base):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(n, axis=1)
    n = n / np.maximum(ln, 1e-12)[:, None]
    k = 0.45 + 0.55 * np.clip(np.abs(n @ LIGHT), 0, 1)
    return np.clip(np.outer(k, base[:3]), 0, 1)


def render_scene(items, path, view=(28, -58), title="", legend=None, clip=None, figsize=(11, 8), dpi=130, note="", zoom=1.0):
    """items: list of (Manifold, rgb or rgba).  clip: (normal, offset) -> keep the half-space n.x <= offset."""
    T, C = [], []
    for m, col in items:
        if clip is not None:
            m = m.trim_by_plane([-c for c in clip[0]], -clip[1])
        if m.is_empty():
            continue
        t = _tris(m)
        if not len(t):
            continue
        rgb = _shade(t, np.array(col[:3], float))
        a = col[3] if len(col) > 3 else 1.0
        T.append(t)
        C.append(np.hstack([rgb, np.full((len(t), 1), a)]))
    T, C = np.vstack(T), np.vstack(C)
    fig = plt.figure(figsize=figsize, dpi=dpi)
    ax = fig.add_subplot(111, projection="3d", proj_type="ortho")
    ax.view_init(elev=view[0], azim=view[1])
    ax.add_collection3d(Poly3DCollection(T, facecolors=C, edgecolors="none", linewidths=0))
    lo, hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(tuple(np.maximum(hi - lo, 1e-3)), zoom=zoom)
    ax.set_axis_off()
    ax.set_title(title, fontsize=10)
    if legend:
        ax.legend(handles=[Patch(color=c, label=l) for l, c in legend], loc="lower left", fontsize=7, ncol=2, frameon=False,
                  bbox_to_anchor=(0.0, -0.02))
    if note:
        fig.text(0.5, 0.01, note, fontsize=7, ha="center")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def render_flat(items, path, look="top", title="", legend=None, clip=None, figsize=(13, 9), dpi=140, note="", labels=None, marks=None,
                paths=None, texts=None, hlines=None):
    """paths: [(xy array, colour, label, (tx, ty))] drawn on top (v6 wire runs);  texts: [(x, y, text, colour)];
    hlines: [(z, x0, x1, text)] dimension lines for side views."""
    """True-scale flat view (no perspective, fills the page): look = 'top' (from +Z) or 'side' (from -Y)."""
    T, C = [], []
    for m, col in items:
        if clip is not None:
            m = m.trim_by_plane([-c for c in clip[0]], -clip[1])
        if m.is_empty():
            continue
        t = _tris(m)
        if len(t):
            T.append(t)
            C.append(_shade(t, np.array(col[:3], float)))
    T, C = np.vstack(T), np.vstack(C)
    cen = T.mean(axis=1)
    if look == "top":
        order, P2 = np.argsort(cen[:, 2]), T[:, :, [0, 1]]
    elif look == "bottom":                       # seen from the skin side: X is mirrored
        order, P2 = np.argsort(-cen[:, 2]), T[:, :, [0, 1]] * np.array([-1.0, 1.0])
    elif look == "elbow":                        # v4.3: seen from outside the elbow end (+X): right = +Y, up = +Z
        order, P2 = np.argsort(cen[:, 0]), T[:, :, [1, 2]]
    elif look == "hand":                         # v4.3: seen from outside the hand end (-X): right = -Y, up = +Z
        order, P2 = np.argsort(-cen[:, 0]), T[:, :, [1, 2]] * np.array([-1.0, 1.0])
    else:
        order, P2 = np.argsort(-cen[:, 1]), T[:, :, [0, 2]]
    P2, C = P2[order], C[order]
    w, h = np.ptp(P2[:, :, 0]), np.ptp(P2[:, :, 1])
    if look not in ("top", "bottom"):
        figsize = (figsize[0], max(3.2, figsize[0] * h / w + 1.6))
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.add_collection(PolyCollection(P2, facecolors=C, edgecolors=C, linewidths=0.15))
    ax.set_xlim(P2[:, :, 0].min() - 1, P2[:, :, 0].max() + 1)
    ax.set_ylim(P2[:, :, 1].min() - 1, P2[:, :, 1].max() + 1)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title(title, fontsize=10)
    sx = -1.0 if look == "bottom" else 1.0
    for mk in (marks or []):                      # outline boxes (x, y in the part frame): (x0, y0, x1, y1[, colour, linestyle])
        x0, y0, x1, y1 = mk[:4]
        xs = [sx * x0, sx * x1, sx * x1, sx * x0, sx * x0]
        ax.plot(xs, [y0, y0, y1, y1, y0], color=mk[4] if len(mk) > 4 else "red", ls=mk[5] if len(mk) > 5 else "-", lw=2.0, zorder=8)
    for (x, y, tx, ty, txt) in (labels or []):    # red callouts
        ax.annotate(txt, xy=(sx * x, y), xytext=(sx * tx, ty), color="red", fontsize=10, fontweight="bold",
                    ha="center", arrowprops=dict(arrowstyle="->", color="red", lw=1.8))
    for xy, col, lab, txy in (paths or []):
        xy = np.asarray(xy)
        ax.plot(sx * xy[:, 0], xy[:, 1], color=col, lw=2.6, solid_capstyle="round", zorder=5)
        if lab:
            ax.annotate(lab, xy=(sx * xy[len(xy) // 2, 0], xy[len(xy) // 2, 1]), xytext=(sx * txy[0], txy[1]), color=col, fontsize=7.5,
                        fontweight="bold", ha="center", arrowprops=dict(arrowstyle="-", color=col, lw=0.8), zorder=6)
    for x, y, t, col in (texts or []):
        ax.text(sx * x, y, t, color=col, fontsize=8.5, fontweight="bold", ha="center", va="center", zorder=7)
    xr = P2[:, :, 0].max() + 2
    ty = -1e9
    for z, x0, x1, t in sorted(hlines or [], key=lambda h: h[0]):
        ty = max(z, ty + 2.6)                      # stagger the labels so they never overlap
        ax.plot([x0, x1], [z, z], color="#444", lw=0.8, ls="--", zorder=6)
        ax.plot([x1, xr, xr + 4], [z, z, ty], color="#999", lw=0.5, ls=":", zorder=6)
        ax.text(xr + 4.5, ty, t, fontsize=7.5, va="center", ha="left", color="#222", zorder=7)
    if hlines:
        ax.set_ylim(ax.get_ylim()[0], max(ax.get_ylim()[1], ty + 2))
    pts_all = [np.asarray(p[3]) for p in (paths or []) if p[2]] + [np.array(t[:2]) for t in (texts or [])]
    if pts_all:
        pa = np.vstack(pts_all)
        ax.set_xlim(min(ax.get_xlim()[0], (sx * pa[:, 0]).min() - 12), max(ax.get_xlim()[1], (sx * pa[:, 0]).max() + 12))
        ax.set_ylim(min(ax.get_ylim()[0], pa[:, 1].min() - 3), max(ax.get_ylim()[1], pa[:, 1].max() + 3))
    if hlines:
        ax.set_xlim(ax.get_xlim()[0], ax.get_xlim()[1] + 48)
    if labels:
        ys = [l[3] for l in labels]
        ax.set_ylim(min(ax.get_ylim()[0], min(ys) - 3), max(ax.get_ylim()[1], max(ys) + 3))
        xt = [sx * l[2] for l in labels]
        ax.set_xlim(min(ax.get_xlim()[0], min(xt) - 14), max(ax.get_xlim()[1], max(xt) + 14))
    # 10 mm scale bar
    x0, y0 = P2[:, :, 0].min(), P2[:, :, 1].min() - 0.6
    ax.plot([x0, x0 + 10], [y0, y0], color="k", lw=2)
    ax.text(x0 + 5, y0 - 0.3, "10 mm", ha="center", va="top", fontsize=7)
    if legend:
        fig.legend(handles=[Patch(color=c, label=l) for l, c in legend], loc="lower center", fontsize=7, ncol=3, frameon=False)
    if note:
        fig.text(0.5, 0.005 if not legend else 0.0, note, fontsize=7, ha="center")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def twin_items(boards, wires, wire_col_start=0):
    """-> (render items, legend entries) for a list of placed boards and wires."""
    items, legend = [], []
    for b in boards:
        for k, m in b.solids:
            col = COL.get(k, (0.5, 0.5, 0.5))
            if k == "pcb":
                col = PCB_COL.get(b.name.split(" #")[0], (0.07, 0.07, 0.09) if "MAX" not in b.name else PCB_COL["MAX30102"])
            if k == "plug" and b.name == "USB-C plug":
                col = PCB_COL["USB-C plug"]
            items.append((m, col))
    for i, w in enumerate(wires):
        c = matplotlib.colors.to_rgb(WIRE_COLS[(i + wire_col_start) % len(WIRE_COLS)])
        items.append((w.solid, c))
        legend.append((f"{w.name}  ({w.length:.0f} mm drawn)", c))
    return items, legend
