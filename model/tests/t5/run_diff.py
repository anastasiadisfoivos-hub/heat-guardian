#!/usr/bin/env python3
"""T5 - C (replay through my own out-of-tree host builds) vs Python mirror, and C -O2 vs C -Ofast, on MY random sequences.
  python3 run_diff.py N [workers]     -> tests/t5/out/diff_random.json
Strict compare: every integer output equal, STATUS bytes equal, every float bit-equal as float32 (NaN == NaN).
Builds used (tests/t5/build, made by build.sh): host_O2 (= guardian/c Makefile flags), host_Ofast (-Ofast -ffast-math)."""
import json, os, sys, subprocess, tempfile, time
import numpy as np
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, "/home/claude/hg_ai/guardian/py")
from trace_io import write_csv, run_py, OUTCOLS
import gen_random

BUILDS = {"O2": os.path.join(HERE, "build", "host_O2"), "Ofast": os.path.join(HERE, "build", "host_Ofast"),
          "Ofast_nofinite": os.path.join(HERE, "build", "host_Ofast_nofinite")}
EXTRA = [b for b in os.environ.get("T5_EXTRA", "").split(",") if b]      # e.g. only_hg_util,only_hg_kf (bisection runs)
for b in EXTRA: BUILDS[b] = os.path.join(HERE, "build", "host_" + b)
NO_PY = os.environ.get("T5_NO_PY") == "1"
INTC = OUTCOLS[1:17] + ["flux_valid", "hr_valid", "valid", "env_run", "env_dose", "night_heat", "nudge"]
PYMAP = {"sd_now": "core_sd_now", "f20_eff": "core_f20_eff", "logit_p38": "core_logit_p38", "logit_p385": "core_logit_p385",
         "strain": "core_strain", "kf": "core_kf", "flux_valid": "core_flux_valid", "hr_valid": "core_hr_valid", "valid": "core_valid"}
FLOATC = [c for c in OUTCOLS if c not in INTC and c not in ("status", "row")]

def read_c(path):
    rows = []
    for line in open(path):
        p = line.rstrip("\n").split(",")
        if len(p) != len(OUTCOLS): break          # truncated last line of a crashed run
        rows.append(dict(zip(OUTCOLS, p)))
    return rows

def pyval(o, k):
    if k in ("v12_est", "v12_f20", "v12_z", "t_air_corr", "env_run", "env_dose"): return o["aux"][k]
    if k.startswith("x") and k[1:].isdigit(): return o["aux"]["x"][int(k[1:])]
    if k.startswith("nn") and k[2:].isdigit(): return o["aux"]["nn_mean"][int(k[2:])]
    if k.startswith("nsd"): return o["aux"]["nn_sd"][int(k[3:])]
    return o[PYMAP.get(k, k)]

def feq(a, b):
    a = np.float32(float(a)); b = np.float32(float(b))
    return (a != a and b != b) or a == b

def cmp_rows(A, B, b_is_py):
    """returns (n_int_mismatch_minutes, n_float_mismatch_minutes, max_abs_float_diff, first)"""
    ni = nf = 0; mx = 0.0; first = None
    for i, (a, b) in enumerate(zip(A, B)):
        di = []; df = []
        for k in INTC + ["status"]:
            av = a[k]; bv = pyval(b, k) if b_is_py else b[k]
            if k == "status": same = av == bv
            else: same = int(av) == int(bv)
            if not same: di.append((k, av, bv))
        for k in FLOATC:
            av = a[k]; bv = pyval(b, k) if b_is_py else b[k]
            if not feq(av, bv):
                df.append(k); fa, fb = float(av), float(bv)
                d = abs(fa - fb) if (fa == fa and fb == fb) else float("inf")
                mx = max(mx, d)
        if di: ni += 1
        if df: nf += 1
        if (di or df) and first is None: first = dict(row=i, ints=di[:6], floats=df[:8])
    return ni, nf, mx, first

def one(i):
    name, prof, twin, mins = gen_random.seq(i)
    res = dict(name=name, n=len(mins))
    with tempfile.TemporaryDirectory() as d:
        ci = os.path.join(d, "in.csv"); write_csv(ci, mins, prof, twin)
        outs = {}
        for b, exe in BUILDS.items():
            co = os.path.join(d, "out_%s.csv" % b)
            rc = subprocess.run([exe, "replay", ci, co], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
            outs[b] = read_c(co) if os.path.exists(co) else []
            res["rc_" + b] = rc
        py = None if NO_PY else run_py(mins, prof, twin)
    assert len(outs["O2"]) == len(mins) and res["rc_O2"] == 0, name
    if py is not None:
        assert len(py) == len(mins)
        res["py"] = cmp_rows(outs["O2"], py, True)
    else: res["py"] = (0, 0, 0.0, None)
    for b in BUILDS:
        if b == "O2": continue
        r = cmp_rows(outs["O2"], outs[b], False)
        res[b] = (r[0] + (len(mins) - len(outs[b])), r[1], r[2], r[3] or (dict(crash_rc=res["rc_" + b], rows=len(outs[b])) if res["rc_" + b] else None))
        res["states_" + b] = np.bincount([int(x["state"]) for x in outs[b]], minlength=9).tolist()
        res["drink_" + b] = sum(1 for x in outs[b] if int(x["tiers"]) & 1)
    st = [int(r["state"]) for r in outs["O2"]]
    res["states"] = np.bincount(st, minlength=9).tolist()
    res["drink_O2"] = sum(1 for x in outs["O2"] if int(x["tiers"]) & 1)
    res["fam"] = sum(1 for k in range(1, len(st)) if int(outs["O2"][k]["family_alert"]) and not int(outs["O2"][k - 1]["family_alert"]))
    return res

def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    W = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    t0 = time.time()
    with Pool(W) as p: rs = p.map(one, range(start, start + N), chunksize=8)
    tot = dict(sequences=len(rs), minutes=sum(r["n"] for r in rs), seconds=round(time.time() - t0, 1))
    for key in ["py"] + [b for b in BUILDS if b != "O2"]:
        tot[key] = dict(seq_with_int_mismatch=sum(1 for r in rs if r[key][0]), int_mismatch_minutes=sum(r[key][0] for r in rs),
                        seq_with_float_mismatch=sum(1 for r in rs if r[key][1]), float_mismatch_minutes=sum(r[key][1] for r in rs),
                        max_float_diff=max(r[key][2] for r in rs),
                        firsts=[[r["name"], r[key][3]] for r in rs if r[key][3]][:12])
    tot["state_minutes_O2"] = np.sum([r["states"] for r in rs], axis=0).tolist()
    for b in BUILDS:
        if b != "O2":
            tot["state_minutes_" + b] = np.sum([r["states_" + b] for r in rs], axis=0).tolist()
            tot["crashed_seq_" + b] = sum(1 for r in rs if r["rc_" + b] != 0)
        tot["drink_tier_minutes_" + b] = sum(r["drink_" + b] for r in rs)
    tot["family_onsets_O2"] = sum(r["fam"] for r in rs)
    tot["state_names"] = ["OK", "DRINK", "COOL", "CHECK", "DANGER", "IMOK", "NOT_WORN", "BATTERY", "HELP"]
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    out = os.path.join(HERE, "out", "diff_random_%d_%d%s.json" % (start, N, os.environ.get("T5_TAG", "")))
    json.dump(tot, open(out, "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in tot.items()}, indent=1, default=str)[:6000])

if __name__ == "__main__":
    main()
