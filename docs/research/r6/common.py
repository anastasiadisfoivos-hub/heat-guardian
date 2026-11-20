"""R6 shared helpers - SIMULATION, DEV ONLY. Reads only research/r6/cache (built from minutes_dev_v4) + DEV rows of persons/events/scenarios."""
import json, os
import numpy as np, pandas as pd
ROOT = "/home/claude/hg_ai"; SIM = ROOT + "/sim/data"; HERE = os.path.dirname(os.path.abspath(__file__))
IDX = json.load(open(HERE + "/cache/index.json"))
SCEN = pd.read_parquet(SIM + "/scenarios_dev_v4.parquet").set_index("person_id")
_DEV = set(SCEN.index)
PERS = pd.read_parquet(SIM + "/persons.parquet"); PERS = PERS[PERS.person_id.isin(_DEV)].set_index("person_id")   # DEV rows only
EVT = pd.read_parquet(SIM + "/events_dev_v4.parquet")
def load(pid):
    d = dict(np.load("%s/cache/p%d.npz" % (HERE, pid))); d["pid"] = pid
    d["types"] = SCEN.loc[pid, "day_types_1_to_N"].split(","); d["t0"] = int(d["t_min"][0]); return d
def events(pid, typ):
    e = EVT[(EVT.person_id == pid) & (EVT.type == typ)]; return list(zip(e.t_start.astype(int), e.t_end.astype(int), e.day.astype(int)))
def onsets(x):
    x = np.asarray(x, bool); return x & ~np.concatenate([[False], x[:-1]])
