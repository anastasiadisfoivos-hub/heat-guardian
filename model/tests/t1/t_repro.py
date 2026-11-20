"""T1 reproducibility + batch invariance (SIMULATION). Dev persons only (no sealed person is simulated).
1) person A simulated alone with the builder's simulate_chunk -> quantise -> compare column bytes to minutes_dev_v2 row group.
2) person A simulated in a chunk with dev person B -> must equal (1) byte for byte (own seed stream, no cross-person coupling).
3) run (1) twice -> identical."""
import sys, json, hashlib, time
sys.path.insert(0, "/home/claude/hg_ai/sim")
import numpy as np, pandas as pd, pyarrow.parquet as pq
from velders.population import simulate_chunk, quantise
S = set(json.load(open("/home/claude/hg_ai/model/sealed_hg2.json"))["sealed_sim_person_ids"])
persons = pd.read_parquet("/home/claude/hg_ai/sim/data/persons.parquet")
dev_ids = [i for i in persons.person_id if i not in S]
A, B = dev_ids[0], dev_ids[7]
rows = {r["person_id"]: r for r in persons.to_dict("records")}
pf = pq.ParquetFile("/home/claude/hg_ai/sim/data/minutes_dev_v2.parquet")
# find row group of A (row groups are written in person order)
rg = None
for g in range(pf.num_row_groups):
    if int(pf.read_row_group(g, columns=["person_id"]).column(0)[0].as_py()) == A:
        rg = g; break
stored = pf.read_row_group(rg).to_pandas()
def h(df):
    return {c: hashlib.sha256(np.ascontiguousarray(df[c].values).tobytes()).hexdigest()[:16] for c in df.columns}
t0 = time.time()
r1 = quantise(simulate_chunk(([rows[A]], 10))[0][1]); t1 = time.time() - t0
r1b = quantise(simulate_chunk(([rows[A]], 10))[0][1])
r2 = quantise([x for x in simulate_chunk(([rows[B], rows[A]], 10)) if x[0] == A][0][1])
hs, h1, h1b, h2 = h(stored), h(r1), h(r1b), h(r2)
res = dict(person=int(A), row_group=rg, sec_per_person=round(t1, 1),
           cols_differ_stored_vs_rerun=[c for c in hs if hs[c] != h1.get(c)],
           cols_differ_rerun_vs_rerun=[c for c in h1 if h1[c] != h1b[c]],
           cols_differ_alone_vs_batched=[c for c in h1 if h1[c] != h2[c]],
           dtypes_equal=bool((stored.dtypes == r1.dtypes).all()), n_rows=(len(stored), len(r1)))
for c in res["cols_differ_stored_vs_rerun"][:10]:
    a, b = stored[c].values.astype(float), r1[c].values.astype(float)
    res.setdefault("maxdiff", {})[c] = float(np.nanmax(np.abs(a - b)))
print(json.dumps(res, indent=1))
json.dump(res, open("/home/claude/hg_ai/tests/t1/out/repro.json", "w"), indent=1)
