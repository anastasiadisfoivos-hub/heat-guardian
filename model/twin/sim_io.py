"""SIM-DEV access for the Body Twin evaluations. SIMULATION data (Virtual Elders, B1).

Rules enforced here:
  * refuses to run without model/sealed_hg2.json (the seal must exist before any sim minute is read);
  * reads minutes_all.parquet (or minutes_dev.parquet) ROW GROUP BY ROW GROUP and skips a row group whose
    person_id statistics touch a sealed id BEFORE its data is read -> sealed rows are never loaded;
  * asserts that no sealed id reaches the caller.
"""
import json
import os

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

SIM = "/home/claude/hg_ai/sim/data"
SEAL = "/home/claude/hg_ai/model/sealed_hg2.json"


class SealMissing(RuntimeError):
    pass


def sealed_sim_ids():
    if not os.path.exists(SEAL):
        raise SealMissing(f"{SEAL} does not exist: the seal has not run, no sim minute may be read")
    js = json.load(open(SEAL))
    ids = None
    for k in ("sealed_sim_person_ids", "sealed_sim_ids", "sim_ids", "sealed_sim", "sim", "SIM"):
        if k in js:
            ids = js[k]; break
    if ids is None and isinstance(js.get("sealed"), dict):
        for k in ("sim", "SIM", "sim_ids"):
            if k in js["sealed"]:
                ids = js["sealed"][k]; break
    if ids is None:
        raise SealMissing(f"cannot find the sealed SIM id list in {SEAL} (keys: {list(js)})")
    ids = {int(x) for x in ids}
    assert len(ids) == 100, f"expected 100 sealed sim persons, found {len(ids)}"
    return ids


def minutes_path(path=None):
    """explicit path (e.g. sim/data/minutes_dev_v2.parquet) or the default dev file."""
    if path:
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        if "sealed" in os.path.basename(path):
            raise PermissionError("refusing to open a sealed minutes file: " + path)
        return path
    for n in ("minutes_dev.parquet", "minutes_all.parquet"):
        p = os.path.join(SIM, n)
        if os.path.exists(p):
            return p
    return None


def load_persons():
    return pd.read_parquet(os.path.join(SIM, "persons.parquet"))


def load_dev_persons():
    sealed = sealed_sim_ids()
    ids = [int(i) for i in load_persons().person_id if int(i) not in sealed]
    assert not set(ids) & sealed
    return ids


class DevMinutes:
    """Row-group index of the minutes file restricted to DEV persons."""

    def __init__(self, columns=None, path=None):
        self.sealed = sealed_sim_ids()
        p = minutes_path(path)
        if p is None:
            raise FileNotFoundError("no minutes parquet in sim/data yet")
        self.pf = pq.ParquetFile(p)
        names = self.pf.schema_arrow.names
        self.columns = [c for c in columns if c in names] if columns else None
        self.missing = [c for c in (columns or []) if c not in names]
        pid_col = names.index("person_id")
        self.groups = {}
        for g in range(self.pf.num_row_groups):
            st = self.pf.metadata.row_group(g).column(pid_col).statistics
            if st is None or not st.has_min_max:
                continue        # cannot prove it is not sealed -> never read it
            lo, hi = int(st.min), int(st.max)
            if any(lo <= s <= hi for s in self.sealed):
                continue        # touches a sealed id -> never read it
            for pid in range(lo, hi + 1):
                self.groups.setdefault(pid, []).append(g)

    def persons(self):
        return sorted(self.groups)

    def person(self, pid):
        pid = int(pid)
        assert pid not in self.sealed, "sealed person requested"
        gs = self.groups.get(pid)
        if not gs:
            return None
        df = self.pf.read_row_groups(gs, columns=self.columns).to_pandas()
        df = df[df.person_id == pid]
        assert not set(df.person_id.unique()) & self.sealed
        sort = [c for c in ("day", "minute_of_day") if c in df] or ["t_min"]
        return df.sort_values(sort).reset_index(drop=True)
