"""V2 convention check (SIMULATION): builder's own meade() + thirst policy on DEV healthy cohort; raw end-minus-start rise
of each arm vs the builder's 'minus the 22 C arm' contrast; plus the no-drinking sensitivity."""
import sys, json
sys.path.insert(0, "/home/claude/hg_ai/sim")
import numpy as np, pandas as pd
from velders.protocols import meade
from velders.validate import thirst_policy_factory
S = set(json.load(open("/home/claude/hg_ai/model/sealed_hg2.json"))["sealed_sim_person_ids"])
df = pd.read_parquet("/home/claude/hg_ai/sim/data/persons.parquet"); df = df[(~df.person_id.isin(S)) & (df.frailty < 1 / 3)]
P = {c: df[c].values for c in df.columns if df[c].dtype != object}
out = {"n": len(df)}
for drink in (True, False):
    R = {T: meade(P, T, drink_policy=thirst_policy_factory(P) if drink else None) for T in (22, 26, 31, 36)}
    out[f"drink={drink}"] = dict(raw_rise={T: round(float(R[T]["dcore"].mean()), 3) for T in R},
                                 contrast_vs_22={T: round(float((R[T]["dcore"] - R[22]["dcore"]).mean()), 3) for T in (26, 31, 36)},
                                 core_at_0800=round(float(R[22]["c0"].mean()), 3))
print(json.dumps(out, indent=1)); json.dump(out, open("/home/claude/hg_ai/tests/t1/out/v2_convention.json", "w"), indent=1)
