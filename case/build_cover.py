"""v7-cover: python3 build_cover.py
   -> final/screen_cover.stl (+ _corner variant), cover_plunger.stl, power_lid_plug.stl, power_lid_nohole.stl (print orientation,
      bed at z 0), final/screen_cover_iso.png, final/screen_cover_section.png, final/COVER_CHECKS.txt
   Checks: one closed body per STL, fragility.py (nothing under 1.2 mm, no slender post), fit against the v7.0 brain pod and the
   digital twin (screen, XIAO, USB plug, screen wires, the switch in its sleeve)."""
import os, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "parts"))
import numpy as np, trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from manifold3d import Manifold
from geo import to_trimesh, box
import params as P
import brain as B
import screen_cover as C
import fragility
from render import _draw, _shade
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

FIN = f"{ROOT}/final"
PLA = 1.24
LOG = []


def say(s):
    print(s); LOG.append(s)


def export(name, m, flip):
    pm = to_trimesh(m.rotate([180, 0, 0]) if flip else m)
    pm.merge_vertices()
    pm.update_faces(pm.nondegenerate_faces(height=1e-5))
    pm.remove_unreferenced_vertices()
    real = [b for b in pm.split(only_watertight=False) if abs(b.volume) > 0.5]
    assert len(real) == 1, f"{name}: {len(real)} bodies"
    pm = real[0]
    pm.apply_translation([-pm.bounds[:, 0].mean(), -pm.bounds[:, 1].mean(), -pm.bounds[0][2]])
    assert pm.is_watertight, name
    pm.export(f"{FIN}/{name}.stl")
    d = pm.bounds[1] - pm.bounds[0]
    say(f"{name}.stl: {d[0]:.1f} x {d[1]:.1f} x {d[2]:.1f} mm on the bed, {pm.volume / 1000:.2f} cm3, ~{pm.volume / 1000 * PLA:.1f} g PLA solid, one closed body")
    return pm


def fit(pos):
    """cover vs the printed pod and everything in it"""
    cov = C.build(pos)
    pod = B.build()
    boards, wires = B.twin()
    sw = C.switch_twin(pos)
    plg = C.build_plunger(True, pos)
    say(f"--- fit check, button '{pos}' at interior ({C.btn_xy(pos)[0]:.2f}, {C.btn_xy(pos)[1]:.2f})")
    say(f"   cover x pod overlap: {(cov ^ pod).volume():.3f} mm3 (grip ribs keep {P.COVER_GRIP_GAP} nominal gap: must be 0)")
    for b in boards:
        v = (cov ^ b.solid).volume()
        say(f"   cover x {b.name}: {v:.3f} mm3" + ("" if v < 1e-3 else "  <-- OVERLAP"))
    say(f"   cover x switch: {(cov ^ sw.solid).volume():.3f} mm3; plunger x cover: {(cov ^ plg).volume():.3f} mm3; plunger x switch: {(plg ^ sw.solid).volume():.3f} mm3")
    grown = cov + C._tower(*C.btn_xy(pos))[1].translate(list(C.OFF)) + sw.solid      # tower incl. its cavity + the switch with its joints
    for w in wires:
        v = (grown ^ w.solid).volume()
        if v > 1e-3:
            lo, hi = (grown ^ w.solid).bounding_box()[:3], (grown ^ w.solid).bounding_box()[3:]
            say(f"   WIRE CLASH (twin's nominal route): {w.name}: {v:.1f} mm3, z {lo[2]:.1f}-{hi[2]:.1f}")
    for b in boards:
        v = (sw.solid ^ b.solid).volume()
        if v > 1e-3:
            say(f"   switch x {b.name}: {v:.2f} mm3  <-- OVERLAP")
    say(f"   switch + joints x pod: {(sw.solid ^ pod).volume():.3f} mm3; lowest point of the joint envelope z {sw.solid.bounding_box()[2]:.2f} (pod floor {P.FLOOR})")
    return cov, pod, boards, wires, sw, plg


def pictures(cov, pod, boards, sw, plg):
    # 1. isometric: the cover with the plunger in it, as worn
    fig = plt.figure(figsize=(15, 7), dpi=120)
    for i, (el, az, lab) in enumerate(((34, -52, "from the hand side (USB-C cut-out, reset notch)"), (34, 128, "from the elbow side (wire opening)"))):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d", proj_type="ortho")
        ax.view_init(elev=el, azim=az)
        tc, tp_ = to_trimesh(cov), to_trimesh(plg)
        wx, wy = C.WIN_C[0] + C.OFF[0], C.WIN_C[1] + C.OFF[1]
        scr = to_trimesh(box(wx - C.WIN_W / 2 - 0.3, wy - C.WIN_L / 2 - 0.3, C.Z_GLASS - 0.3, wx + C.WIN_W / 2 + 0.3, wy + C.WIN_L / 2 + 0.3, C.Z_GLASS - 0.05))

        def fine(tm):                      # small triangles, so matplotlib's per-triangle depth sort is right
            v, f = trimesh.remesh.subdivide_to_size(tm.vertices, tm.faces, 1.5)
            return trimesh.Trimesh(v, f, process=False)
        tc, tp_, scr = fine(tc), fine(tp_), fine(scr)
        tris = np.concatenate([tm.vertices[tm.faces] for tm in (tc, tp_, scr)])       # ONE collection: depth-sorted per triangle
        cols = np.concatenate([_shade(tc, (0.35, 0.62, 0.78)), _shade(tp_, (0.95, 0.55, 0.2)), _shade(scr, (0.15, 0.15, 0.18))])
        ax.add_collection3d(Poly3DCollection(tris, facecolors=cols, edgecolors="none", linewidths=0))
        lo, hi = tc.bounds[0], np.maximum(tc.bounds[1], tp_.bounds[1])
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2]); ax.set_box_aspect(tuple(hi - lo)); ax.set_axis_off()
        ax.set_title(lab, fontsize=10)
    d = to_trimesh(cov).bounds[1] - to_trimesh(cov).bounds[0]
    fig.suptitle(f"v7-cover screen_cover (blue) + plunger (orange), screen behind the window (dark)  -  {d[0]:.1f} x {d[1]:.1f} x {d[2]:.1f} mm\n"
                 f"window {C.WIN_W:.2f} x {C.WIN_L:.2f} R{P.LCD_AA_R:.0f}, button {P.COVER_BTN_CAP_D:.0f} mm dia, {P.COVER_BTN_PROUD} proud, below the screen, centred", fontsize=11)
    fig.savefig(f"{FIN}/screen_cover_iso.png", bbox_inches="tight"); plt.close(fig)

    # 2. section through the plunger: plane x = button centre, seen from the hand side (Y across the wrist to the right, Z up)
    bx = C.btn_xy()[0] + C.OFF[0]
    M = np.array([[0, 1.0, 0, 0], [0, 0, 1.0, 0], [1.0, 0, 0, 0]])              # (x, y, z) -> (y, z, x)

    def polys(m):
        return m.transform(M).slice(bx).to_polygons()
    fig, ax = plt.subplots(figsize=(15, 8), dpi=120)
    items = [(pod, "#9aa3ad", "brain pod (printed v7.0)"), (cov, "#3f8fc0", "screen cover"), (plg, "#f08a24", "plunger (resting on the switch)"),
             (sw.part("body") + sw.part("plunger"), "#2b2b2b", "tactile switch 5 x 5 x 3 + 3.5 plunger"), (sw.part("blob") + sw.part("legs"), "#c9b458", "legs + joints + glue envelope (2.5)")]
    for b in boards:
        items.append((b.solid, "#7fbf7f" if "LCD" in b.name else "#b5d6a0", b.name))
    for m, col, lab in items:
        first = True
        for pg in polys(m):
            ax.fill(pg[:, 0], pg[:, 1], color=col, lw=0, label=lab if first else None, zorder=2 if col in ("#3f8fc0", "#f08a24", "#2b2b2b") else 1)
            first = False
    oy = C.OFF[1]
    by = C.btn_xy()[1] + oy

    def note(txt, xy, xt):
        ax.annotate(txt, xy=xy, xytext=xt, fontsize=8, arrowprops=dict(arrowstyle="-", lw=0.6), va="center")
    note(f"cap {P.COVER_BTN_CAP_D:.0f} dia, {P.COVER_BTN_PROUD} proud", (by, C.Z_TOP + P.COVER_BTN_PROUD), (by + 13, 20.3))
    note(f"45 deg flare = stop; float {P.COVER_BTN_FLOAT}", (by + C.R_FL - 0.3, C.Z_J - 0.5), (by + 13, 15.4))
    note(f"well {2 * C.R_WELL:.1f} dia", (by + C.R_WELL, C.Z_FB), (by + 13, 13.9))
    note(f"cone {C.CONE_ANGLE:.0f} deg (no support)", (by + 3.2, (C.Z_WELL0 + C.Z_CONE0) / 2), (by + 13, 10.9))
    note(f"depth stop on the body top (z {C.Z_BODY1:.2f})", (by + 2.4, C.Z_BODY1 + 0.2), (by + 13, 9.4))
    note(f"sleeve {P.COVER_BTN_SLEEVE:.1f} sq x {P.COVER_BTN_SLEEVE_DEPTH:.0f}; hot glue at its mouth", (by + C.SLV + 0.6, C.Z_MOUTH), (by + 13, 6.4))
    note("wire slot toward the XIAO (D7 + GND)", (by - C.SLV - 0.6, C.Z_MOUTH + 0.8), (by - 26, C.Z_MOUTH - 2.6))
    note("screen glass under the bezel lip", (C.LCD_Y1 + oy - 3, C.Z_GLASS - 0.5), (by - 26, C.Z_TOP + 3.2))
    note("cover stop on the pod rim", (C.YI + oy + 0.7, C.Z_WALL + 1.5), (by + 13, 12.4))
    ax.set_aspect("equal"); ax.set_xlim(by - 30, by + 36); ax.set_ylim(-1, C.Z_TOP + 5)
    ax.set_xlabel("Y across the wrist (mm, pod centre = 0)   -   screen side <- | -> pod's lower edge"); ax.set_ylabel("Z above the skin plane (mm)")
    ax.legend(loc="lower left", fontsize=8, ncol=2)
    ax.set_title(f"v7-cover: section through the button (plane along Y at the button centre, x = {bx:+.2f})\n"
                 f"plunger -> switch plunger tip at z {C.Z_NOSE:.2f} ({C.BTN_H:.2f} above the pod floor); the screen wires of the garage are NOT drawn: see COVER_CHECKS.txt", fontsize=10)
    ax.grid(lw=0.3, alpha=0.5)
    fig.savefig(f"{FIN}/screen_cover_section.png", bbox_inches="tight"); plt.close(fig)


def main():
    os.makedirs(FIN, exist_ok=True)
    say(f"v7-cover.  pod outer {C.X1 - C.X0:.2f} x {C.Y1 - C.Y0:.2f}, rim z {C.Z_WALL:.2f}; cover inner {C.X1 - C.X0 + 2 * P.COVER_FIT:.2f} x {C.Y1 - C.Y0 + 2 * P.COVER_FIT:.2f}; "
        f"glass z {C.Z_GLASS:.2f}, cover top z {C.Z_TOP:.2f}, skirt bottom z {C.Z0:.2f}")
    say(f"button stack z: cap top {C.Z_TOP + P.COVER_BTN_PROUD:.2f} / junction {C.Z_J:.2f} / flange bottom {C.Z_FB:.2f} / nose = switch tip {C.Z_NOSE:.2f} / "
        f"body top {C.Z_BODY1:.2f} / sleeve mouth {C.Z_MOUTH:.2f} / body bottom {C.Z_BODY0:.2f}; cone {C.CONE_ANGLE:.1f} deg")
    cov, pod, boards, wires, sw, plg = fit("centre")
    fit("corner")
    export("screen_cover", cov, True)
    export("screen_cover_corner", C.build("corner"), True)
    export("cover_plunger", C.build_plunger(), False)
    export("power_lid_plug", C.build_lid_plug(), False)
    export("power_lid_nohole", C.build_lid_nohole(), True)
    ok = True
    for n in ("screen_cover", "screen_cover_corner", "cover_plunger", "power_lid_nohole"):
        good, lines = fragility.check(n, f"{FIN}/{n}.stl", verbose=False)
        ok &= good
        for l in lines:
            say("fragility " + l)
    say("fragility power_lid_plug: not checked - a 0.5 mm disc + 1.2 peg that only fills a hole (carries no load)")
    pictures(cov, pod, boards, sw, plg)
    say("RESULT: " + ("PASS" if ok else "FAIL"))
    open(f"{FIN}/COVER_CHECKS.txt", "w").write("\n".join(LOG) + "\n")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
