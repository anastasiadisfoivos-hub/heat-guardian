"""T1 physics property tests on the builder's TwoNodeOlder / BandSensors with MY OWN random scenarios (SIMULATION).
Persons: random DEV persons from persons.parquet (sealed ids excluded). Scenarios: per-person random piecewise-constant
environments (T_db 18-46 C, RH 10-90 %, v 0.1-1.5, met from the clamp list x person multiplier as the builder does,
clo 0.3-0.6, random drinks), 2 days, all features on.
Checks per step: finite outputs; core 35-41; w in [0, w_max]; s_skbf in [0,1]; m_sweat, E_sk >= 0; HR <= HR_max;
energy closure with the step-lagged evaporation: storage_k = M_k(returned) - E_res_k - C_res_k - Q_sens_k - E_sk_{k-1} (returned E_sk is the value used in the NEXT step);
also the naive same-step closure (what a user of the returned dict would compute)."""
import sys, json
sys.path.insert(0, "/home/claude/hg_ai/sim")
import numpy as np, pandas as pd
from velders.body import TwoNodeOlder, MET_CLAMP
from velders.protocols import person_met
S = set(json.load(open("/home/claude/hg_ai/model/sealed_hg2.json"))["sealed_sim_person_ids"])
df = pd.read_parquet("/home/claude/hg_ai/sim/data/persons.parquet")
df = df[~df.person_id.isin(S)]
rng = np.random.default_rng(777)
pick = df.sample(60, random_state=7)
P = {c: pick[c].values for c in pick.columns if pick[c].dtype != object}
n = len(pick); T = 2 * 1440
def piecewise(lo, hi, choices=None):
    out = np.empty((T, n)); t = 0
    while t < T:
        L = int(rng.integers(30, 180))
        out[t:t + L] = rng.choice(choices, n) if choices is not None else rng.uniform(lo, hi, n)
        t += L
    return out
tdb = piecewise(18, 40); rh = piecewise(10, 70); v = piecewise(None, None, np.array([0.1, 0.1, 0.3, 1.5]))
metb = piecewise(None, None, np.array(MET_CLAMP)); clo = piecewise(None, None, np.array([0.3, 0.4, 0.5, 0.6]))
drink = np.where(rng.uniform(size=(T, n)) < 0.01, 200.0, 0.0)
met = np.where(metb >= 1.2, np.maximum(metb * P["met_adl_mult"], 1.22), np.minimum(metb * P["met_rest_mult"], 1.08))
b = TwoNodeOlder(P, minute_of_day0=0)
viol = dict(nonfinite=0, core_out=0, w_out=0, s_out=0, neg_sweat=0, neg_esk=0, hr_over_max=0, hr_below_40=0)
e_lag, e_naive, core_rng = 0.0, 0.0, [99, -99]
prev = None
for t in range(T):
    o = b.step(dict(t_db=tdb[t], rh=rh[t], v_air=v[t], met=met[t], clo=clo[t], drink_mL=drink[t], minute_of_day=t % 1440))
    for k in ("T_core", "T_skin", "w", "s_skbf", "m_sweat", "HR", "E_sk", "Q_sens", "M", "storage", "deficit_pct"):
        viol["nonfinite"] += int((~np.isfinite(o[k])).sum())
    tc = o["T_core"]; core_rng = [min(core_rng[0], tc.min()), max(core_rng[1], tc.max())]
    viol["core_out"] += int(((tc < 35) | (tc > 41)).sum())
    viol["w_out"] += int(((o["w"] < -1e-12) | (o["w"] > o["w_max"] + 1e-9)).sum())
    viol["s_out"] += int(((o["s_skbf"] < 0) | (o["s_skbf"] > 1)).sum())
    viol["neg_sweat"] += int((o["m_sweat"] < -1e-12).sum()); viol["neg_esk"] += int((o["E_sk"] < -1e-12).sum())
    viol["hr_over_max"] += int((o["HR"] > P["hr_max"] + 1e-9).sum()); viol["hr_below_40"] += int((o["HR"] < 40).sum())
    if prev is not None:
        r = o["M"] - o["E_res"] - o["C_res"] - o["Q_sens"] - prev["E_sk"] - o["storage"]
        e_lag = max(e_lag, float(np.abs(r).max()))
        r2 = o["M"] - o["E_res"] - o["C_res"] - o["Q_sens"] - o["E_sk"] - o["storage"]
        e_naive = max(e_naive, float(np.abs(r2).max()))
    prev = {k: np.array(o[k]) for k in ("M", "E_sk")}
res = dict(persons=n, minutes=T, violations=viol, core_range=[float(x) for x in core_rng],
           energy_residual_lagged_Wm2=e_lag, energy_residual_same_step_Wm2=e_naive)
print(json.dumps(res, indent=1)); json.dump(res, open("/home/claude/hg_ai/tests/t1/out/physics_props_library_range.json", "w"), indent=1)
