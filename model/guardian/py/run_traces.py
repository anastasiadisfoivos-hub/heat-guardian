#!/usr/bin/env python3
"""Replay traces through the C build (host_test replay) and the Python mirror and compare minute by minute.
  python3 run_traces.py htt        104 HTT dev sessions (dataset 1, 52 dev people; the 13 spent-sealed people excluded)
  python3 run_traces.py crafted    50 CRAFTED synthetic person-days (trace_gen.py)
  python3 run_traces.py sim        SIM-DEV person-days from B1 (sim/data/minutes_dev.parquet), 50 person-days, if present
Writes ../tests/out/run_traces_<set>.json. HTT rows: HR + session air only -> T1 absent (NaN), contact forced worn,
a_std 0.05 g (walking protocol; HTT has no accelerometer), time unknown (routine off)."""
import json, os, sys, tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_io import minute, write_csv, run_c, run_py, compare, default_twin
import trace_gen

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "tests", "out")

def htt_sessions():
    sys.path.insert(0, "/home/claude/hgmodel")
    import common
    sessions, subj = common.load_htt()
    sealed = set(json.load(open("/home/claude/hgmodel/sealed_split.json"))["sealed_subjects"])
    dev = [s for s in sessions if s["subject"] not in sealed]
    assert not set(s["subject"] for s in dev) & sealed
    res = []
    for s in dev:
        p = subj.loc[s["subject"]]
        rest = float(p.resting_hr) if np.isfinite(p.resting_hr) else 70.0
        prof = dict(age=float(p.age), sex_m=1.0 if p.sex == "M" else 0.0, bmi=float(p.bmi), med_flags=0)
        tw = default_twin(); tw["rest_hr"] = rest
        mins = [minute(mod=0xFFFF, tair=s["amb"], rh=s["rh"], hr=float(h), hrq=4, astd=0.05, apeak=1.2, force_worn=2, vbat=4.0)
                for h in s["hr"]]
        res.append(("%s_s%s" % (s["subject"], s["session"]), prof, tw, mins))
    return res

def crafted_sets(n=50):
    res = []; scen = ["ordinary", "ordinary", "heat", "cool", "ordinary"]
    for k in range(n // 5):
        p = trace_gen.person(1000 + k)
        for d, sc in enumerate(scen):
            res.append(("crafted_p%d_d%d_%s" % (k, d, sc), p["profile"], p["twin"], trace_gen.days(p, 1, sc, seed=d)))
    return res

def main(which):
    os.makedirs(OUT, exist_ok=True)
    sets = htt_sessions() if which == "htt" else crafted_sets() if which == "crafted" else None
    if sets is None:
        import sim_adapter
        sets = sim_adapter.sim_sets(50)
    tot = dict(sets=len(sets), minutes=0, state_mismatch=0, fmax={}, xmax=0.0, nnmax=0.0, auxmax=0.0, firsts=[])
    with tempfile.TemporaryDirectory() as d:
        for name, prof, tw, mins in sets:
            ci, co = os.path.join(d, "in.csv"), os.path.join(d, "out.csv")
            write_csv(ci, mins, prof, tw)
            c = run_c(ci, co); p = run_py(mins, prof, tw)
            r = compare(c, p)
            assert r["len_c"] == r["len_py"] == len(mins), (name, r["len_c"], r["len_py"], len(mins))
            tot["minutes"] += r["n"]; tot["state_mismatch"] += r["state_mismatch"]
            for k, v in r["fmax"].items(): tot["fmax"][k] = max(tot["fmax"].get(k, 0.0), v)
            for k in ("xmax", "nnmax", "auxmax"): tot[k] = max(tot[k], r[k])
            if r["first"] and len(tot["firsts"]) < 5: tot["firsts"].append([name, str(r["first"])])
    tot["state_agreement_pct"] = 100.0 * (1 - tot["state_mismatch"] / max(tot["minutes"], 1))
    json.dump(tot, open(os.path.join(OUT, "run_traces_%s.json" % which), "w"), indent=1, default=float)
    print(json.dumps(tot, indent=1, default=float))
    return tot

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "htt")
