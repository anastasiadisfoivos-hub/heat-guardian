"""T1 leakage checks (SIMULATION). Reads ONLY the person_id column of the sealed files."""
import json, hashlib
import numpy as np, pandas as pd, pyarrow.parquet as pq
D = "/home/claude/hg_ai/sim/data/"
S = json.load(open("/home/claude/hg_ai/model/sealed_hg2.json"))
sealed = set(S["sealed_sim_person_ids"])
res = {}
persons = pd.read_parquet(D + "persons.parquet")
res["n_persons"] = len(persons); res["n_sealed"] = len(sealed)
res["persons_sha_matches_seal"] = hashlib.sha256(open(D+"persons.parquet","rb").read()).hexdigest() == S["persons_parquet_sha256"]
res["seed_eq_base_plus_id"] = bool((persons.seed == 20261112 + persons.person_id).all())
res["seed_unique"] = bool(persons.seed.is_unique)
res["persons_split_column_values"] = sorted(map(str, persons["split"].unique()))
for suf in ("", "_v2"):
    for kind in ("minutes", "ppg_1hz", "events"):
        dev = set(pq.read_table(D + f"{kind}_dev{suf}.parquet", columns=["person_id"]).column(0).to_numpy().tolist())
        sea = set(pq.read_table(D + f"{kind}_sealed{suf}.parquet", columns=["person_id"]).column(0).to_numpy().tolist())
        res[f"{kind}{suf}"] = dict(n_dev_ids=len(dev), n_sealed_ids=len(sea), sealed_in_dev=sorted(dev & sealed),
                                   sealed_file_eq_seal=sea == sealed if kind != "events" else sea <= sealed,
                                   dev_union_sealed_is_all=(dev | sea) == set(persons.person_id) if kind != "events" else None)
sc = pd.read_parquet(D + "scenarios_v2.parquet")
res["scenarios_v2_has_sealed_rows"] = int(sc.person_id.isin(sealed).sum())
res["scenarios_v2_split_labels_match_seal"] = bool(((sc.split == "sealed") == sc.person_id.isin(sealed)).all())
# Row-group layout: one row group per person in dev
pf = pq.ParquetFile(D + "minutes_dev_v2.parquet")
res["minutes_dev_v2_row_groups"] = pf.num_row_groups
res["minutes_dev_v2_rows"] = pf.metadata.num_rows
res["minutes_dev_v2_schema_metadata_label"] = (pf.schema_arrow.metadata or {}).get(b"label", b"").decode()
print(json.dumps(res, indent=1, default=str))
json.dump(res, open("/home/claude/hg_ai/tests/t1/out/leakage.json", "w"), indent=1, default=str)
