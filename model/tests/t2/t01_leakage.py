"""T2-01 leakage attack on model/hg2 (B2). Run: cd /home/claude/hg_ai && HG2_SIMVER=v4 HG2_HRAUG=1 python3 tests/t2/t01_leakage.py
Never opens minutes_sealed*/events_sealed*/ppg_1hz_sealed* (the file-open tracer below would itself abort if anything did).
 A. every cached index (cache/v4aug/sim_*.npz M[:,0], htt_oof subjects) vs sealed_hg2.json
 B. calibration (100) / ES (30) / gradient (270) disjointness; no calibration id in any training view
 C. seal integrity: canonical-string SHA, persons.parquet SHA, minutes_dev_v4 row-group ids (footer stats only)
 D. file-open tracer while running every loader the pipeline uses (no 'sealed' path but sealed_hg2.json; SQL only dataset 1)
 E. patched seal: a seal that includes a DEV person must make the loaders raise
"""
import builtins, hashlib, io, json, os, sqlite3, sys, tempfile
sys.path.insert(0, "/home/claude/hg_ai")
os.environ.setdefault("HG2_SIMVER", "v4"); os.environ.setdefault("HG2_HRAUG", "1")
import numpy as np, pyarrow.parquet as pq

OPENED, SQL = [], []
_open = builtins.open
_ioopen = io.open


def _trace(p):
    s = str(p)
    OPENED.append(s)
    b = os.path.basename(s)
    if "sealed" in b and b != "sealed_hg2.json":
        raise RuntimeError("SEALED FILE OPENED: " + s)


def topen(f, *a, **k):
    if isinstance(f, (str, bytes, os.PathLike)): _trace(f)
    return _open(f, *a, **k)


builtins.open = topen; io.open = topen
_pf_init = pq.ParquetFile.__init__


def pf_init(self, source, *a, **k):
    if isinstance(source, (str, os.PathLike)): _trace(source)
    return _pf_init(self, source, *a, **k)


pq.ParquetFile.__init__ = pf_init
_rt = pq.read_table


def rt(source, *a, **k):
    if isinstance(source, (str, os.PathLike)): _trace(source)
    return _rt(source, *a, **k)


pq.read_table = rt
_conn = sqlite3.connect


def tconn(*a, **k):
    _trace(a[0] if a else k.get("database"))
    c = _conn(*a, **k); c.set_trace_callback(lambda q: SQL.append(q)); return c


sqlite3.connect = tconn

from model.hg2 import common as C  # noqa
R = {}
S = C.sealed()
seal_j = json.load(_open(C.SEAL))
canon = "SIM:" + ",".join(str(i) for i in sorted(seal_j["sealed_sim_person_ids"])) + "|OFFICE:" + ",".join(sorted(seal_j["sealed_office_subject_ids"]))
R["C_canonical_sha_ok"] = hashlib.sha256(canon.encode()).hexdigest() == seal_j["canonical_string_sha256"]
R["C_persons_sha_ok"] = C.sha256_file(C.PERSONS) == seal_j["persons_parquet_sha256"]
R["C_n_sealed"] = [len(S["sim"]), len(S["office"])]
pf = pq.ParquetFile(C.MIN_DEV)
rg_ids = set()
for i in range(pf.metadata.num_row_groups):
    st = pf.metadata.row_group(i).column(0).statistics; assert st.min == st.max; rg_ids.add(int(st.min))
R["C_minutes_dev_v4_persons"] = len(rg_ids); R["C_minutes_dev_v4_sealed_overlap"] = sorted(rg_ids & S["sim"])
R["C_minutes_dev_v4_sha"] = C.sha256_file(C.MIN_DEV)

# A/B: cache indices
meta = json.load(_open(os.path.join(C.CACHE, "sim_meta.json")))
cal, es, tr = set(meta["val_ids"]), set(meta["es_ids"]), set(meta["train_ids"])
R["B_sizes_cal_es_train"] = [len(cal), len(es), len(tr)]
R["B_disjoint"] = not (cal & es) and not (cal & tr) and not (es & tr)
R["B_cal_equals_val_person_ids"] = sorted(cal) == C.val_person_ids()
R["B_es_equals_es_person_ids"] = sorted(es) == C.es_person_ids()
R["B_union_is_400_dev"] = sorted(cal | es | tr) == C.dev_person_ids()
views = {}
for v in ("v0", "v1", "v2", "v3", "v4", "es", "val", "valaug"):
    M = np.load(os.path.join(C.CACHE, "sim_%s.npz" % v))["M"]; ids = set(np.unique(M[:, 0]).astype(int).tolist())
    views[v] = dict(n_persons=len(ids), sealed_overlap=len(ids & S["sim"]), calibration_overlap=len(ids & cal), es_overlap=len(ids & es))
R["A_cache_views"] = views
o = np.load(os.path.join(C.CACHE, "oof_resid.npz")); R["A_oof_resid_rows_from_view"] = "v0 (train persons only)"
h = np.load(os.path.join(C.CACHE, "htt_oof.npz"), allow_pickle=True)
R["A_htt_subjects"] = int(len(np.unique(h["subj"]))); R["A_htt_subject_prefix"] = sorted(set(str(s)[:3] for s in h["subj"]))

# D: run every loader with the tracer
OPENED.clear(); SQL.clear()
from model.hg2 import simio, build_sim, data_htt, train  # noqa
ids = C.dev_person_ids(); C.val_person_ids(); C.es_person_ids(); C.data_provenance()
build_sim.day_types(); simio.persons_table()
bids, dfs = next(simio.iter_persons(ids[:2], batch=2))
lanes = data_htt.load(noise=True)
for v in ("v0", "es", "val"): train.check_index(train.load_view(v)[2])
R["D_files_opened"] = sorted(set(os.path.relpath(p, "/home/claude") if p.startswith("/") else p for p in OPENED))
R["D_sql_statements"] = [q.strip().replace("\n", " ")[:160] for q in SQL]
R["D_sql_only_dataset1"] = all(("dataset_id = 1" in q) for q in SQL if q.strip().upper().startswith("SELECT"))
R["D_no_sealed_file_opened"] = not any(("sealed" in os.path.basename(p) and not p.endswith("sealed_hg2.json")) for p in OPENED)

# E: patched seal (DEV person 0 and calibration person cal[0] declared sealed) -> loaders must raise
patched = dict(seal_j); extra = sorted({ids[0], sorted(cal)[0], sorted(tr)[0]})
patched["sealed_sim_person_ids"] = sorted(set(seal_j["sealed_sim_person_ids"]) | set(extra))
tmp = tempfile.NamedTemporaryFile("w", suffix="_patched_seal.json", delete=False); json.dump(patched, tmp); tmp.close()
C.SEAL = tmp.name
E = {}
def expect_raise(name, fn):
    try: fn(); E[name] = "NO RAISE (defect)"
    except AssertionError as e: E[name] = "AssertionError: " + str(e)[:80]
expect_raise("dev_person_ids", C.dev_person_ids)
expect_raise("iter_persons([1]) (row-group guard)", lambda: next(simio.iter_persons([ids[1]], batch=1)))
expect_raise("iter_persons([dev0])", lambda: next(simio.iter_persons([ids[0]], batch=1)))
expect_raise("train.check_index(val view M)", lambda: train.check_index(train.load_view("val")[2]))
expect_raise("train.check_index(v0 view M)", lambda: train.check_index(train.load_view("v0")[2]))
expect_raise("assert_no_sealed(cal ids)", lambda: C.assert_no_sealed(sorted(cal)))
R["E_patched_seal_extra_ids"] = extra; R["E_patched_seal_results"] = E
os.unlink(tmp.name)
json.dump(R, _open("/home/claude/hg_ai/tests/t2/out/t01_leakage.json", "w"), indent=1)
print(json.dumps(R, indent=1))
