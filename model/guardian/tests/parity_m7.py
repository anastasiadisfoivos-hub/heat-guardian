#!/usr/bin/env python3
"""C == Python for every M7 flag build (HG_DRINK_DESIGN 0..3 x HG_M7_ROUTINE 0/1) on CRAFTED multi-day weeks."""
import os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "py"))
import hg_guardian_py as H, trace_io, trace_gen
bad = 0
for d in (0, 1, 2, 3, 4):
    for r in (0, 1):
        trace_io.HOST = os.path.join(HERE, "..", "c", "build", ("hts_d%d_r%d" if os.environ.get("HG_WEIGHTS") == "stub" else "ht_d%d_r%d") % (d, r)); H.FLAGS.update(design=d, delta=None, m7r=r)
        tot = mm = 0; nud = 0
        with tempfile.TemporaryDirectory() as dd:
            for k, sc, n in ((4001, "ordinary", 6), (4002, "heat", 4)):
                p = trace_gen.person(k); mins = trace_gen.days(p, n, sc, seed=9)
                trace_io.write_csv(dd + "/i.csv", mins, p["profile"], p["twin"])
                c = trace_io.run_c(dd + "/i.csv", dd + "/o.csv"); py = trace_io.run_py(mins, p["profile"], p["twin"])
                res = trace_io.compare(c, py); tot += res["n"]; mm += res["state_mismatch"]
                nud += sum(1 for i in range(1, len(c)) if c[i]["state"] == 1 and c[i - 1]["state"] != 1)
                if res["first"] and mm: print("   first:", str(res["first"])[:300])
        print("design %d m7r %d: %d minutes, %d state mismatches, %d DRINK onsets" % (d, r, tot, mm, nud)); bad += mm
sys.exit(1 if bad else 0)
