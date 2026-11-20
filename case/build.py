"""One command: python3 build.py [part ...]
   -> out/stl/*.stl (undersides curved to the wrist), out/stl_flat/*.stl (flat undersides, no supports),
      out/png/*.png (each part + the assembly digital twin), out/SIZES.txt, out/CLEARANCES.txt, out/WARNINGS.txt
   The build stops if the digital twin finds an interference in either variant, or (v7.0) if fragility.py finds a wall / floor under
   1.2 mm or a slender post in a print file (out/FRAGILITY.txt)."""
import sys, os, importlib, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "parts"))
from geo import to_trimesh
import guides

PARTS = ["coupon", "cable_guide_test", "brain_pod", "brain_frame", "power_pod", "power_lid", "island_skin", "island_shelf", "island_air"]
REAL = ["brain_pod", "brain_frame", "power_pod", "power_lid", "island_skin", "island_shelf", "island_air"]
ROOT = os.path.dirname(os.path.abspath(__file__))
FLAT = os.environ.get("HG_FLAT") == "1"


def main(names):
    stl = f"{ROOT}/out/stl_flat" if FLAT else f"{ROOT}/out/stl"
    os.makedirs(stl, exist_ok=True); os.makedirs(f"{ROOT}/out/png", exist_ok=True)
    if not FLAT:
        from render import render_all, render_cables
    lines = []
    for n in names:
        mod = importlib.import_module(n)
        guides.PATHS.clear()
        m = mod.build()
        paths = list(guides.PATHS)
        tm = to_trimesh(m)
        rot = getattr(mod, "PRINT_ROT", [180, 0, 0] if getattr(mod, "PRINT_FLIP", False) else None)
        pm = to_trimesh(m.rotate(rot)) if rot else tm
        # v6.7.1: every STL is ONE connected solid, starting at the bed.  Zero-volume sliver shells (CSG coplanar leftovers, no
        # material) are dropped so the slicer does not report them as floating regions; any real second body stops the build.
        import trimesh, io
        pm = pm.copy()
        pm.merge_vertices()
        pm.update_faces(pm.nondegenerate_faces(height=1e-5))
        pm.remove_unreferenced_vertices()
        comps = pm.split(only_watertight=False)
        real = [b for b in comps if abs(b.volume) > 0.5]
        assert len(real) == 1, f"{n}: {len(real)} separate bodies (floating regions) - every printed part must be ONE connected solid"
        pm = real[0]
        pm.apply_translation([0, 0, -pm.bounds[0][2]])
        chk = trimesh.load(io.BytesIO(pm.export(file_type="stl")), file_type="stl")
        assert len(chk.split(only_watertight=False)) == 1 and chk.is_watertight, f"{n}: exported STL is not one closed body"
        pm.export(f"{stl}/{n}.stl")   # STL in print orientation
        assert tm.is_watertight, f"{n} is not watertight"
        d = tm.bounds[1] - tm.bounds[0]
        info = getattr(mod, "REPORT", {})
        lines.append(f"{n}: {d[0]:.1f} x {d[1]:.1f} x {d[2]:.1f} mm, volume {tm.volume/1000:.2f} cm3, watertight={tm.is_watertight} {info}")
        if not FLAT:
            bb = m.bounding_box()
            mid = getattr(mod, "SECTION_Y", (bb[1] + bb[4]) / 2)
            half = to_trimesh(m.trim_by_plane([0, 1, 0], mid))
            render_all(tm, n, f"{ROOT}/out/png", half=half)
            if n == "cable_guide_test":
                render_cables(tm, n, f"{ROOT}/out/png", paths)
        print(lines[-1])
    if FLAT:
        import assembly
        groups, cross, pos = assembly.layout()
        bad = assembly.check(groups, cross)[1] + assembly.rule_checks(groups, cross)[1]
        print(f"FLAT-BOTTOM variant: {bad} interference(s)")
        with open(f"{ROOT}/out/SIZES_FLAT.txt", "w") as f:
            f.write("FLAT-BOTTOM VARIANT (out/stl_flat/): no supports, smooth underside\n" + "\n".join(lines) + f"\ninterferences: {bad}\n")
        assert bad == 0, "the flat-bottom variant has interferences"
        import fragility                                 # v7.0: nothing under 1.2 mm, no slender posts (out/FRAGILITY.txt)
        assert fragility.main(), "FRAGILITY CHECK FAILED - see out/FRAGILITY.txt (a wall / floor under 1.2 mm or a slender post)"
        return
    if names == PARTS:
        import assembly, warnings_v6
        bad, twin_lines = assembly.main()[:2]
        with open(f"{ROOT}/out/SIZES.txt", "w") as f:
            f.write("PRINTED PARTS (bounding box incl. curved skin skirt, stitch flanges and strain posts)\n")
            f.write("\n".join(lines) + "\n" + "\n".join(twin_lines) + "\n")
        warn = warnings_v6.collect()
        with open(f"{ROOT}/out/WARNINGS.txt", "w") as f:
            f.write("\n".join(warn) + "\n")
        print(f"{len(warn)} hardware actions / warnings -> out/WARNINGS.txt")
        assert bad == 0, "the digital twin found interferences or wire-rule failures - see out/CLEARANCES.txt"
        import helpers                                   # separate helper pieces (for later, not tonight's print)
        for n, f in helpers.SETS.items():
            tm = to_trimesh(f())
            assert tm.is_watertight, f"{n} is not watertight"
            tm.export(f"{stl}/{n}.stl")
            render_all(tm, n, f"{ROOT}/out/png")
            d = tm.bounds[1] - tm.bounds[0]
            print(f"{n}: {d[0]:.1f} x {d[1]:.1f} x {d[2]:.1f} mm, volume {tm.volume/1000:.2f} cm3")
        # (v6.1: the wall clips were for the v4 heart island and are no longer built)
        r = subprocess.run([sys.executable, os.path.abspath(__file__)] + REAL, env=dict(os.environ, HG_FLAT="1"))
        assert r.returncode == 0, "the flat-bottom variant failed"


if __name__ == "__main__":
    names = sys.argv[1:] or [p for p in PARTS if os.path.exists(f"{ROOT}/parts/{p}.py")]
    main(names)
