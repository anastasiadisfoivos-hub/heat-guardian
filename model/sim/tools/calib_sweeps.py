"""Calibration sweeps that set the tuned constants in velders/body.py (SIMULATION). Each sweep prints the
validation rows it was chosen on; the chosen value and the reason are recorded in VALIDATION.md.
DEV persons only (velders.protocols.load_persons is dev-only).

  python3 -I tools/calib_sweeps.py omega    # OMEGA_FRAME x OMEGA_REST_FACTOR -> V2/V4/V12/V13/V15 (chosen 1.6 x 0.85)
  python3 -I tools/calib_sweeps.py acclim   # ACCLIM_THR_SHIFT x ACCLIM_OMEGA_GAIN -> V30 (chosen 0.9 x 0.5)
  python3 -I tools/calib_sweeps.py skin     # SKIN_REPORT_OFFSET_K/W: feasible set for V3 (chosen 0.12 / 1.2)
  python3 -I tools/calib_sweeps.py drift    # DRIFT_THR x DRIFT_RATE -> V19 (chosen 0.94 x 5)
  python3 -I tools/calib_sweeps.py acof     # A_COF -> V14 (chosen 1.0; Ji 0.2)
Constants set by inspection, not by a sweep: HC_FLOOR 2.5 (low end of R1 §1.5 indoor range), CIRC_* (R1 §3.3 qualitative
"nadir attenuated"; values are design choices), lid sun excess 3 + 15 S/900 C (R2 §2.2 lid 45-60 C)."""
import itertools
import sys

import numpy as np

import velders.body as B
from velders.protocols import load_persons, meade
from velders.validate import section_rest, section_limits, section_multiday, healthy

KEEP = {"omega": {"V2", "V4", "V12", "V13", "V15"}, "acclim": {"V30"}, "drift": {"V19", "V4"}, "acof": {"V14", "V12"}}


def show(rows, keep):
    for r in rows:
        if r["id"] in keep:
            print("   ", r["id"], r["result"], r["value"][:120], flush=True)


def main(which):
    P = load_persons()
    if which == "omega":
        for fr, rf in itertools.product((1.5, 1.6, 1.8), (0.75, 0.85, 1.0)):
            B.OMEGA_FRAME, B.OMEGA_REST_FACTOR = fr, rf
            print("OMEGA_FRAME", fr, "REST", rf); show(section_rest(P) + section_limits(P), KEEP["omega"])
    elif which == "acclim":
        for th, g in ((0.3, 0.25), (0.6, 0.4), (0.9, 0.5)):
            B.ACCLIM_THR_SHIFT, B.ACCLIM_OMEGA_GAIN = th, g
            print("ACCLIM", th, g); show(section_multiday(P), KEEP["acclim"])
    elif which == "skin":
        Ph = healthy(P)
        B.SKIN_REPORT_OFFSET_K = 0.0; B.SKIN_REPORT_OFFSET_W = 0.0
        tg = {22: 31.7, 26: 32.9, 31: 34.9, 36: 35.9}
        nodes, gaps, ws = {}, {}, {}
        for T in tg:
            R = meade(Ph, T)
            nodes[T] = float(R["T_skin"][-60:].mean()); gaps[T] = float((R["T_core"][-60:] - R["T_skin"][-60:]).mean()); ws[T] = float(R["w"][-60:].mean())
        print("node", nodes, "gap", gaps, "w", ws)
        for k, w in itertools.product(np.arange(0, 0.31, 0.02), np.arange(0, 2.01, 0.2)):
            v = {T: nodes[T] + k * gaps[T] + w * max(ws[T] - 0.07, 0) for T in tg}
            if all(abs(v[T] - tg[T]) <= 0.5 for T in tg):
                print(f"   feasible k={k:.2f} w={w:.1f}", {T: round(x, 2) for T, x in v.items()})
    elif which == "drift":
        for th, r in itertools.product((0.85, 0.9, 0.94, 0.98), (2.5, 5, 10, 20)):
            B.DRIFT_THR, B.DRIFT_RATE = th, r
            print("DRIFT", th, r); show(section_limits(P), {"V19"})
    elif which == "acof":
        for a in (0.2, 0.6, 1.0):
            B.A_COF = a
            print("A_COF", a); show(section_limits(P), KEEP["acof"])


if __name__ == "__main__":
    main(sys.argv[1])
