"""Seal the hg2 exam sets. Runs ONCE (ARCHITECTURE §3.2). Written and run by the manager.

SEALED-SIM:    100 of 500 Virtual Elders persons, stratified frailty tercile x medication group.
SEALED-OFFICE: 5 of 19 office subjects (hgdata dataset 16), uniform.
Refuses to run if model/sealed_hg2.json exists (exit 2). No overwrite flag.
"""
import hashlib, json, os, sqlite3, sys, datetime
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "model", "sealed_hg2.json")
PERSONS = os.path.join(ROOT, "sim", "data", "persons.parquet")
DB = "/home/claude/hgdata/heat_guardian_train.sqlite"
SEED = 20261112

if os.path.exists(OUT):
    print("sealed_hg2.json already exists: refusing to re-seal.", file=sys.stderr)
    sys.exit(2)

persons_sha = hashlib.sha256(open(PERSONS, "rb").read()).hexdigest()
p = pd.read_parquet(PERSONS)
assert len(p) == 500 and p.person_id.is_unique

rng = np.random.default_rng(SEED)
p["frail_t"] = pd.qcut(p.frailty, 3, labels=[0, 1, 2]).astype(int)
bb = (p.med_bb_nonsel == 1) | (p.med_bb_sel == 1)
p["med_g"] = np.where(p.med_none == 1, "none", np.where(bb, "bb", "other"))

# proportional allocation of 100 across 9 strata, largest remainder
strata = p.groupby(["frail_t", "med_g"]).person_id.apply(list)
quota = strata.apply(len) / len(p) * 100
alloc = np.floor(quota).astype(int)
rem = 100 - alloc.sum()
for k in (quota - alloc).sort_values(ascending=False).index[:rem]:
    alloc[k] += 1
assert alloc.sum() == 100 and (alloc >= 1).all(), alloc

sealed = []
for k in sorted(strata.index):
    ids = sorted(strata[k])
    sealed += [int(x) for x in rng.choice(ids, size=alloc[k], replace=False)]
sealed = sorted(sealed)

con = sqlite3.connect(DB)
office = sorted(r[0] for r in con.execute("select subject_id from subjects where dataset_id=16"))
assert len(office) == 19, office
office_sealed = sorted(str(x) for x in rng.choice(office, size=5, replace=False))

canon = "SIM:" + ",".join(map(str, sealed)) + "|OFFICE:" + ",".join(office_sealed)
rec = {
    "seed": SEED,
    "sealed_sim_person_ids": sealed,
    "sealed_office_subject_ids": office_sealed,
    "canonical_string_sha256": hashlib.sha256(canon.encode()).hexdigest(),
    "persons_parquet_sha256": persons_sha,
    "strata_allocation": {f"frail{a}_{b}": int(v) for (a, b), v in alloc.items()},
    "sealed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "sealed_by": "manager (seal_hg2.py, run once)",
}
with open(OUT, "x") as f:
    json.dump(rec, f, indent=2)
print(json.dumps({k: rec[k] for k in ("canonical_string_sha256", "persons_parquet_sha256", "strata_allocation")}, indent=2))
print("sealed SIM n =", len(sealed), " OFFICE =", office_sealed)
