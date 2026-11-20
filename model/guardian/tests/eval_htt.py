#!/usr/bin/env python3
"""Default build on the 104 HTT dev sessions (52 dev people; spent-sealed 13 excluded), REAL young-adult data, HR only.
DRINK = any DRINK-or-higher tier on the band (level >= 1); event = clean core >= 38.0 C; warned = alarm in [event-45, event+10];
false alarm = episode whose core never reaches 38.0 within max(end, onset+45) - hgmodel/common.event_detection (REPORT s5)."""
import json, os, sys, tempfile
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "py")); sys.path.insert(0, "/home/claude/hgmodel")
import run_traces, trace_io, common
binary = sys.argv[1] if len(sys.argv) > 1 else None
if binary: trace_io.HOST = binary
sess = run_traces.htt_sessions(); raw = {f"{s['subject']}_s{s['session']}": s for s in common.load_htt()[0]}
rows = []
with tempfile.TemporaryDirectory() as d:
    for name, prof, tw, mins in sess:
        trace_io.write_csv(d + "/i.csv", mins, prof, tw); c = trace_io.run_c(d + "/i.csv", d + "/o.csv")
        s = raw[name]
        rows.append(pd.DataFrame(dict(subject=s["subject"], session=s["session"], core=s["core"], drink=[r["level"] >= 1 for r in c],
                                      cool=[r["level"] >= 2 for r in c], danger=[r["level"] >= 3 for r in c])))
df = pd.concat(rows, ignore_index=True)
out = {}
for tier, thr in (("drink", 38.0), ("cool", 38.5), ("danger", 38.5)):
    r = common.event_detection(df, None, thr, None, mask_col=tier)
    out[tier] = {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v) for k, v in r.items()}
print(json.dumps(out, indent=1)); json.dump(out, open(os.path.join(HERE, "out", "eval_htt_%s.json" % (sys.argv[2] if len(sys.argv) > 2 else "default")), "w"), indent=1)
