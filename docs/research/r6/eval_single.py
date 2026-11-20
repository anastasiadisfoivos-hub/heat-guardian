#!/usr/bin/env python3
"""R6 E3b: single-signal minute AUC for 'core >= 38.5 within 30 min' - SIMULATION DEV (110 persons, days 2-10, worn)."""
import json, numpy as np
from common import *; import feats
from eval3 import ew
from eval1 import auc
out = {}
for hk in ("raw", "sc"):
    S = {}
    for p in IDX["persons"]:
        d, X, ok, y = feats.build(p, hk); a = np.minimum(np.nan_to_num(d["a_std_g"]), 0.30); f20 = X["f20"]
        sig = dict(f20_instant=f20, E60_slow_level=ew(f20, 60), jump_E10_minus_E60=ew(f20, 10) - ew(f20, 60), mass_dose=X["dose"], wind_A30_minus_A120=ew(a, 30) - ew(a, 120),
                   recovery_failure_rec=X["rec"], her_units_rel=X["rel"], her_units_z=X["z"], thermal_exception_rT=X["rT"], cardiac_exception_rH=X["rH"], v12_z=X["v12z"], env_dose=X["env"])
        for k, v in sig.items(): S.setdefault(k, []).append(v[ok])
        S.setdefault("y", []).append(y[ok])
    y = np.concatenate(S.pop("y")); out[hk] = {k: float(auc(np.concatenate(v), y)) for k, v in S.items()}
    print(hk, {k: round(v, 3) for k, v in out[hk].items()})
json.dump(out, open(HERE + "/out_single.json", "w"), indent=1)
