#!/usr/bin/env python3
"""B2b - Brighton P1 (DEV) alarm replay through two C host builds (freeze-5 and the scratch AR build), scored with the
pre-registered exam's own episode / false-alarm definitions (tests/real_exam_brighton.py). P1 has no rectal >= 38.0
sample, so only unconfirmed alarms per exposure hour can be reported. usage: python3 -m model.b2b.evaluate_alarms_p1 name=bin ..."""
import json, os, sys, tempfile
import numpy as np
from . import devdata as D
import trace_io as tio


def main():
    import real_exam_brighton as RB, openpyxl
    D.assert_tree_is_freeze5()
    bins = dict(a.split("=", 1) for a in sys.argv[1:])
    wb = openpyxl.load_workbook(RB.XLSX, read_only=True, data_only=True)
    prof = RB.read_profiles(wb)["P1"]
    out = {}
    with tempfile.TemporaryDirectory() as td:
        for nm, b in bins.items():
            tio.HOST = b; tot = {k: [0, 0] for k in RB.TIERS}; hours = 0.0
            for sess in RB.parse_sheet(wb["P1"]):
                mins, off, end = RB.minutes_for(sess, "hold", tio)
                tio.write_csv(td + "/i.csv", mins, prof, tio.default_twin())
                lev = np.array([r["level"] for r in tio.run_c(td + "/i.csv", td + "/o.csv")])[off:]
                refs = [(int(r["el"]), r["rectal"]) for r in sess["rows"] if np.isfinite(r["rectal"]) and 0 <= r["el"] <= end]
                tl = np.array([a for a, _ in refs]); yl = np.array([y for _, y in refs])
                for tier, k in RB.TIERS.items():
                    eps = RB.episodes(lev >= k)
                    fa = sum(1 for a, _ in eps if not ((yl[(tl >= a) & (tl <= a + 60)] >= RB.ANCHOR[tier]).any()))
                    tot[tier][0] += len(eps); tot[tier][1] += fa
                hours += end / 60.0
            out[nm] = {t: dict(episodes=e, unconfirmed=f, per_h=round(f / hours, 3)) for t, (e, f) in tot.items()}
            out[nm]["hours"] = round(hours, 2)
    json.dump(out, open(os.path.join(D.RUNS, "alarms_p1.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
