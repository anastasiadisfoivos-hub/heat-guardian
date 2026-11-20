#!/usr/bin/env python3
"""B2b parity: the C AR patch (scratch build, -DHG_B2B=1; guardian/c itself is NOT changed) vs the Python reference
model/b2b/residual.py, fed with the frozen build's own per-minute x / NN / v1.2 outputs. DEV traces only: Brighton P1
(3 sessions) + 3 SIM-DEV v4 calibration person-days. usage: python3 -m model.b2b.parity <freeze5_binary> <ar_binary> [R_up]"""
import json, os, sys, tempfile
import numpy as np
from . import devdata as D, residual as AR
import trace_io as tio
R_UP = None


def run(binary, path, outp):
    tio.HOST = binary
    return tio.run_c(path, outp)


def main():
    global R_UP
    b0, b1 = sys.argv[1], sys.argv[2]
    R_UP = np.float32(sys.argv[3]) if len(sys.argv) > 3 else None
    D.assert_tree_is_freeze5()
    from sim_adapter import person_days
    sims = []
    for pid, prof, tw, mins in person_days(max_persons=3, days=[3]):
        sims.append(("sim%d/d3" % pid, prof, tw, mins))
    worst = 0.0; n = 0; diffs = {}
    with tempfile.TemporaryDirectory() as td:
        cases = []
        import real_exam_brighton as RB, openpyxl
        wb = openpyxl.load_workbook(RB.XLSX, read_only=True, data_only=True)
        prof = RB.read_profiles(wb)["P1"]
        for sess in RB.parse_sheet(wb["P1"]):
            mins, off, end = RB.minutes_for(sess, "hold", tio); cases.append(("P1/" + sess["name"], prof, tio.default_twin(), mins))
        cases += sims
        for name, prof, tw, mins in cases:
            tio.write_csv(td + "/i.csv", mins, prof, tw)
            o0 = run(b0, td + "/i.csv", td + "/o0.csv"); o1 = run(b1, td + "/i.csv", td + "/o1.csv")
            X = np.array([[r["x%d" % i] for i in range(32)] for r in o0], np.float32)
            nn0 = np.array([r["core_now"] for r in o0], np.float32)
            nn1 = np.array([r["core_20"] for r in o0], np.float32)
            v12 = np.array([r["v12_est"] for r in o0], np.float32); v12f = np.array([r["v12_f20"] for r in o0], np.float32)
            worn = np.array([r["worn"] for r in o0])
            a, b, w = AR.from_features(X, v12, v12f, nn0, nn1, worn=worn, R_up=R_UP)
            c0 = np.array([r["core_now"] for r in o1], np.float32); c1 = np.array([r["core_20"] for r in o1], np.float32)
            d = max(float(np.nanmax(abs(a - c0))), float(np.nanmax(abs(b - c1))))
            lv = int(np.sum(np.array([r["level"] for r in o0]) != np.array([r["level"] for r in o1])))
            diffs[name] = dict(minutes=len(o0), max_abs_diff_C=d, mean_w=float(np.mean(w)), level_changes_vs_freeze5=lv)
            worst = max(worst, d); n += len(o0)
    out = dict(minutes=n, worst_abs_diff_C=worst, per_trace=diffs, verdict="PASS" if worst <= 1e-4 else "FAIL")
    os.makedirs(D.RUNS, exist_ok=True)
    json.dump(out, open(os.path.join(D.RUNS, "parity%s.json" % ("" if R_UP is None else "_asym")), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
