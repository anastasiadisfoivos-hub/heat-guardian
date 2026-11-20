"""v7-cover SIMPLE: python3 build_cover_simple.py
   -> final/screen_cover_simple.stl (window face down, bed at z 0), final/screen_cover_simple.png, final/COVER_SIMPLE_CHECKS.txt
   The same cover as screen_cover_corner (outline, fit, window + bezel lip, USB-C cut-out, reset notch, grip ribs) with the
   plunger, tower, sleeve, depth stop and wire slot removed: a plain 4.2 chamfered through-hole at the corner button position.
   The bare switch is glued under the plate by hand; the finger presses its actuator directly."""
import os, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "parts"))
import numpy as np, trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import params as P
import brain as B
import screen_cover as C
import fragility
from geo import to_trimesh
from render import _shade
import build_cover as BC

FIN = f"{ROOT}/final"
POS = "corner"
LOG = BC.LOG


def say(s):
    BC.say(s)


def main():
    cov = C.build(POS, simple=True)
    bx, by = C.btn_xy(POS)
    pod = B.build()
    boards, wires = B.twin()
    sw = C.switch_twin_simple(POS)
    say(f"v7-cover SIMPLE: hole at interior ({bx:.2f}, {by:.2f}); plate {C.PLATE_T:.2f} (glass z {C.Z_GLASS:.2f} -> top z {C.Z_TOP:.2f})")
    say(f"   hole {P.COVER_SIMPLE_HOLE_D} round through + {P.COVER_SIMPLE_HOLE_CHAMFER} x 45 deg outer chamfer ({P.COVER_SIMPLE_HOLE_D + 2 * P.COVER_SIMPLE_HOLE_CHAMFER:.1f} at the face)")
    say("   inside recess " + (f"{P.COVER_SIMPLE_RECESS} sq x {P.COVER_SIMPLE_RECESS_DEPTH}" if C.SIMPLE_RECESS else
        f"SKIPPED: plate {C.PLATE_T:.2f} - {P.COVER_SIMPLE_RECESS_DEPTH} deep = {C.PLATE_T - P.COVER_SIMPLE_RECESS_DEPTH:.2f} < {P.COVER_SIMPLE_MIN_PLATE} min"))
    say(f"   hole centre from the cover's OUTER edges: {bx - (C.X0 - C.SK):.2f} from the hand-side (USB-C) edge, {(C.X1 + C.SK) - bx:.2f} from the elbow-side edge, "
        f"{(C.Y1 + C.SK) - by:.2f} from the +Y edge below the screen, {by - (C.Y0 - C.SK):.2f} from the -Y edge; window edge to hole centre {by - (C.WIN_C[1] + C.WIN_L / 2):.2f}")
    tip = C.Z_GLASS + (P.COVER_SIMPLE_RECESS_DEPTH if C.SIMPLE_RECESS else 0) + P.BTN_PLUNGER
    say(f"   switch glued flat under the plate: actuator top z {tip:.2f} = {tip - C.Z_TOP:.2f} proud of the face (+/-0.2); body bottom z {tip - P.BTN_PLUNGER - P.BTN_BODY_H:.2f}")
    say(f"   cover x pod: {(cov ^ pod).volume():.3f} mm3")
    for b in boards:
        v = (cov ^ b.solid).volume()
        say(f"   cover x {b.name}: {v:.3f} mm3" + ("" if v < 1e-3 else "  <-- OVERLAP"))
        v = (sw.solid ^ b.solid).volume()
        if v > 1e-3:
            say(f"   switch x {b.name}: {v:.2f} mm3  <-- OVERLAP")
    say(f"   switch (+ legs/joint envelope) x cover: {(sw.solid ^ cov).volume():.3f} mm3; x pod: {(sw.solid ^ pod).volume():.3f} mm3")
    for w in wires:
        v = (sw.solid ^ w.solid).volume()
        if v > 1e-3:
            say(f"   switch x wire {w.name} (twin's nominal route): {v:.1f} mm3")
    pm = BC.export("screen_cover_simple", cov, True)
    vol = pm.volume
    # rough print estimate (no slicer here): a 1.2-wall part is ~all perimeters/skin, so ~85% of solid; ~3.5 mm3/s average on small parts
    say(f"   estimate (no slicer in this env): ~{vol / 1000 * 1.24 * 0.85:.1f} g PLA, ~{vol * 0.85 / 3.5 / 60:.0f} min at 0.2 layers - check in the slicer")
    good, lines = fragility.check("screen_cover_simple", f"{FIN}/screen_cover_simple.stl", verbose=False)
    for l in lines:
        say("fragility " + l)

    # picture: isometric face view + inside view
    fig = plt.figure(figsize=(15, 7), dpi=120)
    tc = to_trimesh(cov)
    v, f = trimesh.remesh.subdivide_to_size(tc.vertices, tc.faces, 1.2)
    tc = trimesh.Trimesh(v, f, process=False)
    swt = to_trimesh(sw.part("body") + sw.part("plunger"))
    v2, f2 = trimesh.remesh.subdivide_to_size(swt.vertices, swt.faces, 1.0)
    swt = trimesh.Trimesh(v2, f2, process=False)
    for i, (el, az, lab, with_sw) in enumerate(((38, -52, "face (as worn): 4.2 hole, 0.6 chamfer, below the screen at the elbow-side corner", False),
                                                (-48, -52, "inside: plain hole (no recess: the plate is 1.2), switch shown glued in place (dark)", True))):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d", proj_type="ortho")
        ax.view_init(elev=el, azim=az)
        meshes = [(tc, (0.35, 0.62, 0.78))] + ([(swt, (0.15, 0.15, 0.18))] if with_sw else [])
        tris = np.concatenate([m.vertices[m.faces] for m, _ in meshes])
        cols = np.concatenate([_shade(m, c) for m, c in meshes])
        ax.add_collection3d(Poly3DCollection(tris, facecolors=cols, edgecolors="none", linewidths=0))
        lo, hi = tc.bounds[0], tc.bounds[1]
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2]); ax.set_box_aspect(tuple(hi - lo)); ax.set_axis_off()
        ax.set_title(lab, fontsize=10)
    fig.suptitle("v7-cover SIMPLE screen_cover_simple - no plunger, no tower: the bare tactile switch is glued under the hole and pressed directly", fontsize=11)
    fig.savefig(f"{FIN}/screen_cover_simple.png", bbox_inches="tight"); plt.close(fig)
    say("RESULT: " + ("PASS" if good else "FAIL"))
    open(f"{FIN}/COVER_SIMPLE_CHECKS.txt", "w").write("\n".join(LOG) + "\n")
    return good


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
