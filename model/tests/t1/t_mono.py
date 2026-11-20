"""T1 monotonicity attack: dT_core(8 h) must be non-decreasing in T_db at fixed met. Finer grid (1 C, 22-44 C) and
three humidities (20/45/70 %), fan off; all 400 DEV persons. Reports every violation by T band. SIMULATION."""
import sys, json
sys.path.insert(0, "/home/claude/hg_ai/sim")
import numpy as np, pandas as pd
from velders.body import TwoNodeOlder
S = set(json.load(open("/home/claude/hg_ai/model/sealed_hg2.json"))["sealed_sim_person_ids"])
df = pd.read_parquet("/home/claude/hg_ai/sim/data/persons.parquet"); df = df[~df.person_id.isin(S)]
P = {c: df[c].values for c in df.columns if df[c].dtype != object}
def met_of(base):
    return np.maximum(base * P["met_adl_mult"], 1.22) if base >= 1.2 else np.minimum(base * P["met_rest_mult"], 1.08)
def dcore(T, rh, base):
    b = TwoNodeOlder(P, minute_of_day0=120)
    for t in range(360):
        b.step(dict(t_db=22.0, rh=45.0, met=met_of(0.86), clo=0.4, v_air=0.1, minute_of_day=120 + t))
    c0 = b.t_core.copy()
    for t in range(480):
        b.step(dict(t_db=float(T), rh=rh, met=met_of(base), clo=0.4, v_air=0.1, minute_of_day=480 + t))
    return b.t_core - c0
res = {}
for rh in (20.0, 45.0, 70.0):
    for base in (0.86, 1.37):
        prev = None; viol = []
        for T in range(22, 45):
            d = dcore(T, rh, base)
            if not np.all(np.isfinite(d)):
                viol.append(dict(T=T, nonfinite=int((~np.isfinite(d)).sum())))
            if prev is not None:
                step = d - prev
                bad = step < -1e-6
                if bad.any():
                    viol.append(dict(T_from=T - 1, T_to=T, n_persons=int(bad.sum()), worst=float(step.min())))
            prev = d
        res[f"rh{int(rh)}_met{base}"] = viol
        print(rh, base, viol, flush=True)
json.dump(res, open("/home/claude/hg_ai/tests/t1/out/mono.json", "w"), indent=1)
