"""T1: builder's own psu() protocol at 34 C Rest: how many persons' detected P_a,crit lie at/above saturation (RH >= 100 %)?
And: 3 h at 34 C / 100 % RH rest -- is the core still compensable (rise rate in last hour)? SIMULATION, DEV healthy cohort."""
import sys, json
sys.path.insert(0, "/home/claude/hg_ai/sim")
import numpy as np, pandas as pd
from velders.protocols import psu, person_met
from velders.body import TwoNodeOlder, p_sat_torr
S = set(json.load(open("/home/claude/hg_ai/model/sealed_hg2.json"))["sealed_sim_person_ids"])
df = pd.read_parquet("/home/claude/hg_ai/sim/data/persons.parquet"); df = df[(~df.person_id.isin(S)) & (df.frailty < 1 / 3)]
P = {c: df[c].values for c in df.columns if df[c].dtype != object}
out = {}
for T in (34, 36):
    r = psu(P, "humid", T, "rest")
    psat = p_sat_torr(T) * 0.133322
    pc = r["Pa_crit_kPa"]
    out[f"rest_{T}C"] = dict(n=len(pc), mean_Pa_crit=float(np.nanmean(pc)), p_sat_kPa=float(psat),
                             frac_ge_saturation=float(np.mean(pc >= psat)), frac_no_inflection=float(np.mean(np.isnan(pc))),
                             max_RH_in_protocol=float(100 * r["pa"].max() / p_sat_torr(T)))
b = TwoNodeOlder(P, minute_of_day0=9 * 60); core = []
for t in range(180):
    o = b.step(dict(t_db=34.0, rh=100.0, met=person_met(P, 0.86), clo=0.4, v_air=0.2, minute_of_day=9 * 60 + t)); core.append(o["T_core"])
core = np.array(core)
out["rest_34C_RH100_3h"] = dict(rate_last_hour_C_per_h_median=float(np.median(core[-1] - core[-61])),
                                frac_rate_below_0p15=float(np.mean((core[-1] - core[-61]) < 0.15)))
print(json.dumps(out, indent=1)); json.dump(out, open("/home/claude/hg_ai/tests/t1/out/psu_supersat.json", "w"), indent=1)
