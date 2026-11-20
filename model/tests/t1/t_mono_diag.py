"""Diagnose the dry (20 % RH) ADL monotonicity violations above 30 C: rerun 30 vs 31 C with module constants patched
in-process (builder files untouched): A_COF 1.0 -> 0.2 (Ji), and features without 'circadian'/'hydration'."""
import sys, json
sys.path.insert(0, "/home/claude/hg_ai/sim")
import numpy as np, pandas as pd
import velders.body as B
S = set(json.load(open("/home/claude/hg_ai/model/sealed_hg2.json"))["sealed_sim_person_ids"])
df = pd.read_parquet("/home/claude/hg_ai/sim/data/persons.parquet"); df = df[~df.person_id.isin(S)]
P = {c: df[c].values for c in df.columns if df[c].dtype != object}
met = np.maximum(1.37 * P["met_adl_mult"], 1.22)
def dcore(T, feats=B.ALL_FEATURES, rec=False):
    b = B.TwoNodeOlder(P, features=feats, minute_of_day0=120)
    for t in range(360):
        b.step(dict(t_db=22.0, rh=45.0, met=np.minimum(0.86 * P["met_rest_mult"], 1.08), clo=0.4, minute_of_day=120 + t))
    c0 = b.t_core.copy(); ws = []; msw = []
    for t in range(480):
        o = b.step(dict(t_db=float(T), rh=20.0, met=met, clo=0.4, minute_of_day=480 + t)); ws.append(o["w"]); msw.append(o["m_sweat"])
    return b.t_core - c0, np.mean(msw, 0), b.t_skin
out = {}
d30, s30, k30 = dcore(30); d31, s31, k31 = dcore(31)
bad = (d31 - d30) < -1e-6
out["baseline"] = dict(n_bad=int(bad.sum()), worst=float((d31 - d30).min()),
                       bad_mean_sweat_30_31=[float(s30[bad].mean()), float(s31[bad].mean())],
                       bad_mean_skin_node_30_31=[float(k30[bad].mean()), float(k31[bad].mean())],
                       bad_mean_thr_sw_skin=float(P["thr_sw_skin"][bad].mean()), all_mean_thr_sw_skin=float(P["thr_sw_skin"].mean()))
B.A_COF = 0.2
d30b, *_ = dcore(30); d31b, *_ = dcore(31)
out["A_COF_0.2"] = dict(n_bad=int(((d31b - d30b) < -1e-6).sum()), worst=float((d31b - d30b).min()))
B.A_COF = 1.0
f = tuple(x for x in B.ALL_FEATURES if x not in ("circadian", "hydration"))
d30c, *_ = dcore(30, f); d31c, *_ = dcore(31, f)
out["no_circadian_no_hydration"] = dict(n_bad=int(((d31c - d30c) < -1e-6).sum()), worst=float((d31c - d30c).min()))
print(json.dumps(out, indent=1)); json.dump(out, open("/home/claude/hg_ai/tests/t1/out/mono_diag.json", "w"), indent=1)
