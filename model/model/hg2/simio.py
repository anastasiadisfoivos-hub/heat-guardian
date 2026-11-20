"""Streaming reader for SIM-DEV minutes (row group = one person). Opens ONLY minutes_dev.parquet. SIMULATION."""
import numpy as np, pandas as pd, pyarrow.parquet as pq
from .common import MIN_DEV, PERSONS, assert_no_sealed, sealed

COLS_IN = ["person_id", "day", "minute_of_day", "t_min", "T1", "T2", "T_air_meas", "RH_meas", "HR_meas", "hr_quality", "PI",
           "a_std_g", "worn_truth"]
COLS_TRUTH = ["T_core", "ev38_30", "ev385_30", "strain_psi", "T_in", "location", "activity_class", "flux_valid_truth", "HR_true"]


def _rg_map(pf):
    m = {}
    for i in range(pf.metadata.num_row_groups):
        st = pf.metadata.row_group(i).column(0).statistics
        assert st.min == st.max, "row group holds more than one person"
        m[int(st.min)] = i
    return m


def persons_table():
    p = pd.read_parquet(PERSONS).set_index("person_id")
    return p


def profile_of(p):
    """persons.parquet row -> hg2 profile (HG_MED_* bits: 1 beta-blocker, 2 diuretic, 4 low-sweat, 8 ACE/ARB)"""
    f = (1 if (p["med_bb_nonsel"] or p["med_bb_sel"]) else 0) | (2 if p["med_diuretic"] else 0) \
        | (4 if p["med_antichol"] else 0) | (8 if p["med_ace_arb"] else 0)
    return dict(age=float(p["age"]), sex_m=float(p["sex_m"]), bmi=float(p["bmi"]), med_flags=int(f))


def iter_persons(ids, columns=COLS_IN + COLS_TRUTH, batch=40):
    """yields (ids_batch, list of per-person DataFrames sorted by t_min)"""
    ids = [int(i) for i in ids]
    assert_no_sealed(ids)
    pf = pq.ParquetFile(MIN_DEV)
    rg = _rg_map(pf)
    assert not set(rg) & sealed()["sim"], "minutes_dev contains a sealed person"
    for k in range(0, len(ids), batch):
        b = ids[k:k + batch]
        t = pf.read_row_groups([rg[i] for i in b], columns=columns).to_pandas()
        out = [t[t.person_id == i].sort_values("t_min").reset_index(drop=True) for i in b]
        del t
        yield b, out
