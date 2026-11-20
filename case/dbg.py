"""Debug helper: which twin solid overlaps which printed part, and where.  python3 dbg.py"""
import sys, os
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [ROOT, os.path.join(ROOT, "parts")]
import assembly
groups = assembly.layout()[0]   # (v6: crossing wires are checked in assembly.check)
for name, parts, boards, wires, off in groups:
    for pn, pm in parts:
        for b in boards:
            for k, m in b.solids:
                x = m ^ pm
                if x.volume() > 0.005:
                    bb = x.bounding_box()
                    print(f"{name}: {b.name}[{k}] x {pn}: {x.volume():.2f} mm3  local box x {bb[0]-off[0]:.2f}..{bb[3]-off[0]:.2f} y {bb[1]-off[1]:.2f}..{bb[4]-off[1]:.2f} z {bb[2]:.2f}..{bb[5]:.2f}")
        for w in wires:
            x = w.solid ^ pm
            if x.volume() > 0.005:
                bb = x.bounding_box()
                print(f"{name}: {w.name} x {pn}: {x.volume():.2f} mm3  local box x {bb[0]-off[0]:.2f}..{bb[3]-off[0]:.2f} y {bb[1]-off[1]:.2f}..{bb[4]-off[1]:.2f} z {bb[2]:.2f}..{bb[5]:.2f}")
