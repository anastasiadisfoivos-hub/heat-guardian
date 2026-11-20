"""Shared paths, seal guard and data hashing for the hg2 (Core Sense) pipeline. Everything trained on Virtual Elders
data is SIMULATION; everything on HTT is "young adults 18-33, chamber walk, DEV".

Hard rules (ARCHITECTURE 3.2 rule 5, B2 brief):
 - every script that touches data calls `sealed()` and `assert_no_sealed(ids)` on its train/val index;
 - minutes_sealed*.parquet is never opened by any function here (only minutes_dev.parquet is ever read);
 - the 5 sealed office subjects are never loaded.
"""
import hashlib, json, os

ROOT = "/home/claude/hg_ai"
MODEL = os.path.join(ROOT, "model")
SIM = os.path.join(ROOT, "sim", "data")
# Run selection (M2/M3): HG2_SIMVER = v1 (PROVISIONAL pipeline debug) | v2 (frozen training simulator, M3, default);
# HG2_HRAUG = 1 applies the M3.2 HR-rise augmentation U(0.6, 1.0) to training views. Every artefact path carries the tag.
SIMVER = os.environ.get("HG2_SIMVER", "v2"); assert SIMVER in ("v1", "v2", "v3", "v4", "v5")
HRAUG = os.environ.get("HG2_HRAUG", "1") == "1"
TAG = SIMVER + ("aug" if HRAUG else "")
SFX = "" if SIMVER == "v1" else "_" + SIMVER
MIN_DEV = os.path.join(SIM, "minutes_dev%s.parquet" % SFX)       # the ONLY minutes file B2 ever opens
SCENARIOS = os.path.join(SIM, ("scenarios_dev%s.parquet" if SIMVER in ("v3", "v4", "v5") else "scenarios%s.parquet") % SFX)
PERSONS = os.path.join(SIM, "persons.parquet")
SEAL = os.path.join(MODEL, "sealed_hg2.json")
CACHE = os.path.join(MODEL, "cache", TAG)
RUNS = os.path.join(MODEL, "runs", TAG)          # members, train_log, results of this run (committed)
EXPORT = os.path.join(MODEL, "export")
os.makedirs(RUNS, exist_ok=True)
GUARD_PY = os.path.join(ROOT, "guardian", "py")
SEED = 20261112
LABEL_SIM = ("SIMULATION (Virtual Elders v1, PROVISIONAL per M2)" if SIMVER == "v1" else
             "SIMULATION (Virtual Elders %s; known too-tolerant at humid rest, bed rest, and HR)" % SIMVER
             + (" - PIPELINE DEBUG ONLY: v2 stores no night sleep" if SIMVER == "v2" else ""))
LABEL_HTT = "young adults 18-33, chamber walk, DEV"


def sealed():
    j = json.load(open(SEAL))
    return dict(sim=set(int(x) for x in j["sealed_sim_person_ids"]), office=set(str(x) for x in j["sealed_office_subject_ids"]),
                persons_sha=j["persons_parquet_sha256"])


def assert_no_sealed(sim_ids=(), office_ids=()):
    s = sealed()
    assert not set(int(x) for x in sim_ids) & s["sim"], "sealed SIM person in a train/val index"
    assert not set(str(x) for x in office_ids) & s["office"], "sealed OFFICE subject in a train/val index"


def sha256_file(path, _cache={}):
    st = os.stat(path); key = (path, st.st_size, st.st_mtime)
    if key in _cache: return _cache[key]
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""): h.update(b)
    _cache[key] = h.hexdigest(); return _cache[key]


def data_provenance():
    """SHA-256 of the training data (M2.1), recorded in every artefact."""
    assert "sealed" not in os.path.basename(MIN_DEV)
    s = sealed()
    p_sha = sha256_file(PERSONS)
    assert p_sha == s["persons_sha"], "persons.parquet changed since the seal"
    return dict(minutes_dev_file=os.path.basename(MIN_DEV), minutes_dev_sha256=sha256_file(MIN_DEV), persons_sha256=p_sha, run_tag=TAG,
                sim_version=SIMVER + {"v1": " (PROVISIONAL, M2)", "v2": " (M3; NOT FIT for final: no night sleep stored, pipeline debug only)",
                                         "v3": " (M6 iteration)", "v4": " (FINAL training sim, M8)",
                                         "v5": " (B1-v5 @ f055fcb: v4 + per-person skin-core coupling fitted on Brighton, DECISIONS M20)"}[SIMVER], hr_rise_augmentation=HRAUG,
                htt_db="/home/claude/hgdata/heat_guardian_train.sqlite dataset 1 (all 65 = DEV for hg2)")


def dev_person_ids():
    import pandas as pd
    p = pd.read_parquet(PERSONS, columns=["person_id"])
    ids = sorted(set(int(x) for x in p.person_id) - sealed()["sim"])
    assert len(ids) == 400
    assert_no_sealed(ids)
    return ids


def val_person_ids():
    """M5.2: the 100 SIM-DEV CALIBRATION persons (never trained on, never used for early stopping); also the SIM-DEV
    evaluation set (conformal coverage on them is cross-fitted by person folds). Drawn once with the project seed."""
    import numpy as np
    ids = dev_person_ids()
    v = sorted(int(x) for x in np.random.default_rng(SEED + 2).choice(ids, 100, replace=False))
    assert_no_sealed(v)
    return v


def es_person_ids():
    """30 of the 300 training-side persons: early-stopping monitor only (no gradient)"""
    import numpy as np
    rest = [i for i in dev_person_ids() if i not in set(val_person_ids())]
    e = sorted(int(x) for x in np.random.default_rng(SEED + 3).choice(rest, 30, replace=False))
    assert_no_sealed(e)
    return e
