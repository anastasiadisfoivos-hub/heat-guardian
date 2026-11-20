#!/usr/bin/env python3
"""T5: C vs Python on random SCRIPTED-core sequences (logic layer only, dense alarms).  python3 sc_diff.py N"""
import sys, json, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
bad = 0; mins = 0; first = []; states = np.zeros(9, int); fam = 0
for i in range(N):
    prof, rows, calm = sc.rand_script(i)
    c = sc.run_c(prof, rows, calm); p = sc.run_py(prof, rows, calm)
    mins += len(rows)
    for t, (a, b) in enumerate(zip(c, p)):
        d = [k for k in sc.OUT if (np.float32(a[k]) != np.float32(b[k]) if k == "a_base" else a[k] != b[k])]
        if d:
            bad += 1
            if len(first) < 10: first.append((i, t, [(k, a[k], b[k]) for k in d]))
        states[a["state"]] += 1
    fam += sum(1 for t in range(1, len(c)) if c[t]["family_alert"] and not c[t - 1]["family_alert"])
r = dict(sequences=N, minutes=mins, mismatch_minutes=bad, first=first, state_minutes=states.tolist(), family_onsets=fam)
json.dump(r, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "sc_diff.json"), "w"), indent=1, default=str)
print(json.dumps(r, default=str)[:3000])
