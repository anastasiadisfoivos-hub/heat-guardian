#!/usr/bin/env python3
"""C == Python on WHOLE 10-day SIM-DEV v4 persons (SIMULATION, DEV only), raw and HR-scaled - the only parity set long enough to arm
M19 Marble Danger (24 h) and to run Exception DRINK's nightly learning. Full compare (trace_io.compare: every state/integer output,
float outputs, features, NN, v1.2 aux). Persons: the first N DEV persons with a core-38.5 event.
usage: parity_sim_long.py [N]   exit 1 on any mismatch"""
import json, os, sys
import numpy as np, pandas as pd, pyarrow.parquet as pq
HERE = os.path.dirname(os.path.abspath(__file__)); G = os.path.dirname(HERE); ROOT = os.path.dirname(G)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(G, "py"))
import trace_io as T
from sealed_exam_system import minutes_of, COLS
from sim_adapter import profile_of, sealed_ids
SIM = os.path.join(ROOT, "sim", "data")

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    V = os.environ.get("HG_SIM_VERSION", "v4")   # B5-v7: v5 option (SIM-DEV v5, DEV only)
    E = pd.read_parquet(os.path.join(SIM, "events_dev_%s.parquet" % V)); ev = sorted(set(E[E.type == "core385"].person_id))
    assert not set(ev) & sealed_ids()
    pf = pq.ParquetFile(os.path.join(SIM, "minutes_dev_%s.parquet" % V))
    rg = {int(pf.metadata.row_group(i).column(0).statistics.min): i for i in range(pf.metadata.num_row_groups)}
    P = pd.read_parquet(os.path.join(SIM, "persons.parquet")).set_index("person_id")
    tw = dict(rest_hr=70.0, k_person=0.12, core_offset=0.0, c_bodyheat=0.15, t1_night_base=[float("nan")] * 24)
    bad = 0; tot = 0; out = []
    d = "/tmp/claude-0/psl"; os.makedirs(d, exist_ok=True)
    sel = [int(x) for x in os.environ["HG_PIDS"].split(",")] if os.environ.get("HG_PIDS") else ev[:n]   # B5-v7: explicit DEV persons
    assert not set(sel) & sealed_ids()
    for pid in sel:
        g = pf.read_row_group(rg[pid], columns=COLS).to_pandas().sort_values("t_min").reset_index(drop=True)
        prof = profile_of(P.loc[pid].to_dict()); rest = float(P.loc[pid, "hr_rest"])
        hr0 = g.HR_meas.values.astype(float); hr1 = rest + np.random.default_rng(20261112 + pid).uniform(0.6, 1.0) * (hr0 - rest)
        for hk, hr in (("raw", hr0), ("scaled", hr1)):
            mins = minutes_of(g, hr); T.write_csv(d + "/i.csv", mins, prof, tw)
            r = T.compare(T.run_c(d + "/i.csv", d + "/o.csv"), T.run_py(mins, prof, tw))
            danger = None
            out.append(dict(pid=pid, hr=hk, n=r["n"], state_mismatch=r["state_mismatch"], fmax=max(r["fmax"].values()), xmax=r["xmax"], first=str(r["first"])))
            bad += r["state_mismatch"] + (r["n"] != len(mins)); tot += r["n"]
            print(out[-1], flush=True)
    print("persons %d, minutes %d, mismatching minutes %d" % (len(sel), tot, bad))
    json.dump(out, open(os.path.join(HERE, "out", "parity_sim_long%s%s.json" % ("" if V == "v4" else "_" + V, "_pids" if os.environ.get("HG_PIDS") else "")), "w"), indent=1)
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
