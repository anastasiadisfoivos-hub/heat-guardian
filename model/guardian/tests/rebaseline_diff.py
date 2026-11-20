#!/usr/bin/env python3
"""M5.5: diff of crafted-trace expectations before (stub weights = v1.2 anchor, D7) and after (B2 export + M5) with the reason
per trace, measured on the signals. usage: rebaseline_diff.py <old_traces_dir> <new_traces_dir>  -> prints + writes REBASELINE_M5.txt"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "py"))
from hg_guardian_py import Guardian, K
NAMES = ["OK", "DRINK", "COOL", "CHECK", "DANGER", "IMOK", "NOT_WORN", "BATTERY", "HELP"]
def load(p):
    prof = twin = None; rows = []
    for l in open(p):
        q = l.rstrip("\n").split(",")
        if q[0] == "#PROFILE": prof = dict(age=float(q[1]), sex_m=float(q[2]), bmi=float(q[3]), med_flags=int(q[4]))
        elif q[0] == "#TWIN": twin = dict(rest_hr=float(q[1]), k_person=float(q[2]), core_offset=float(q[3]), c_bodyheat=float(q[4]),
                                          t1_night_base=[float(x) for x in q[5:29]])
        elif q[0] not in ("mod",) and not q[0].startswith("#"): rows.append(q)
    return prof, twin, rows
def onsets(e):
    out = []; p = None
    for i, v in enumerate(e):
        if v != p and v >= 0: out.append("%s@%d" % (NAMES[v], i)); p = v
    return " ".join(out)
old_d, new_d = sys.argv[1], sys.argv[2]
lines = [os.environ.get("HG_REBASE_TITLE", "M5.5 re-baseline of crafted traces: expectations from STUB (v1.2 f20, D7 '+1 sd' = 0) -> B2 export hg2-20261112-26393fc-simv2aug + M5.1/M5.2"), ""]
for fn in sorted(os.listdir(new_d)):
    if not fn.endswith(".csv"): continue
    po = os.path.join(old_d, fn)
    if not os.path.exists(po): lines.append("%s: NEW trace" % fn); continue
    _, _, ro = load(po); prof, twin, rn = load(os.path.join(new_d, fn))
    eo = [int(r[-2]) for r in ro]; en = [int(r[-2]) for r in rn]
    ch = sum(1 for a, b in zip(eo, en) if a != b)
    if ch == 0: continue
    # replay the inputs through the mirror (B2 weights) to measure what moved the expectation
    from trace_io import minute
    S = ["mod", "t1", "t2", "tair", "rh", "hr", "hrq", "pi", "astd", "apeak", "dc", "flat", "button", "charging", "vbat", "ble", "force_worn", "cmd"]
    g = Guardian(prof, twin); dnn = []; uncm = 0; valid = 0
    for r in rn:
        m = {k: (r[i] if k == "cmd" else (int(r[i]) if k in ("mod", "hrq", "dc", "flat", "button", "charging", "ble", "force_worn") else float(r[i]))) for i, k in enumerate(S)}
        m["cmd"] = None if m["cmd"] == "-" else bytes.fromhex(m["cmd"])
        v = [float(x) for x in r[18:66]]; m.update(t1_5s=v[0:12], t2_5s=v[12:24], tair_5s=v[24:36], zang=v[36:48], forecast=None)
        o = g.step(m)
        if o["core_valid"] and g.hg2.min_since_don >= 20:
            valid += 1; dnn.append(float(o["core_f20_eff"]) - float(o["aux"]["v12_f20"] + np.float32(twin["core_offset"])))
            if o["why"] & 64: uncm += 1
    dnn = np.array(dnn)
    lines += ["%s: %d of %d minutes changed" % (fn, ch, len(en)),
              "   old: " + onsets(eo), "   new: " + onsets(en),
              "   why: " + os.environ.get("HG_REBASE_WHY", "tiers now read B2's NN core_20 (M5.1, no +sd) instead of the stub's v1.2 f20") + ": tiers' f20 - v1.2 f20 on thermal-valid minutes "
              "median %+.3f C (p10 %+.3f, p90 %+.3f); M5.2 uncalibrated lowering active %d of %d of them (sd scale %.2f, h_cal %.2f PROVISIONAL)"
              % (np.median(dnn), np.percentile(dnn, 10), np.percentile(dnn, 90), uncm, valid, float(K("HG_UNC_SD_SCALE_EFF")), float(K("HG_UNC_HALF_CAL_EFF")))
              + ("; behaviour path armed only by the v1.2 shadow Go-cool (M3.1), so its DANGER onset moves with the v1.2 f20, not the NN" if "behaviour" in fn else ""), ""]
open(os.path.join(new_d, os.environ.get("HG_REBASE_NAME", "REBASELINE_M5.txt")), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
