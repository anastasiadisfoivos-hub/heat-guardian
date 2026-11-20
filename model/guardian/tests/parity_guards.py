#!/usr/bin/env python3
"""[B2-fix] C == Python parity on a 600-minute trace that injects +-inf, +-1e30 and out-of-sensor-range values into every
guarded input (t1, t2, t_air, RH, PI, a_std, HR and the 5-s arrays), plus HR 150/180/200 OOD stretches. Exit 1 on any mismatch."""
import os, sys, json, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "py"))
import trace_io as T
BAD = [float("inf"), float("-inf"), 1e30, -1e30, 200.0, -100.0, float("nan")]
rng = random.Random(20261112); mins = []
for t in range(600):
    hr = 150.0 if 100 <= t < 160 else 180.0 if 160 <= t < 220 else 200.0 if 220 <= t < 280 else 85.0 + 10 * rng.random()
    m = dict(mod=(540 + t) % 1440, t1=35.0 + 0.3 * rng.random(), t2=34.0, tair=31.0 + rng.random(), rh=45.0, hr=hr, hrq=4, pi=0.6,
             astd=0.05 if t % 3 else 0.2, dc=100000, vbat=3.9, force_worn=0xFF)
    if t % 5 == 2:
        k = ["t1", "t2", "tair", "rh", "pi", "astd", "hr"][(t // 5) % 7]; m[k] = BAD[(t // 35) % 7]
    mm = T.minute(**m)
    if t % 11 == 4: mm["t1_5s"][3] = BAD[t % 7]; mm["tair_5s"][7] = BAD[(t + 3) % 7]
    mins.append(mm)
d = "/tmp/claude-0/pg"; os.makedirs(d, exist_ok=True)
T.write_csv(d + "/in.csv", mins, T.default_profile(), T.default_twin())
r = T.compare(T.run_c(d + "/in.csv", d + "/out.csv"), T.run_py(mins, T.default_profile(), T.default_twin()))
print(json.dumps(dict(n=r["n"], state_mismatch=r["state_mismatch"], first=str(r["first"]), xmax=r["xmax"], nnmax=r["nnmax"], auxmax=r["auxmax"],
                      fmax_max=max(r["fmax"].values()))))
sys.exit(0 if r["state_mismatch"] == 0 and r["n"] == 600 and max(r["fmax"].values()) <= 1e-6 and r["xmax"] <= 1e-6 else 1)
