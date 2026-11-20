"""T1 sensor cross-consistency (R2 6.5 with M2.5 regime), my own constructed truth, all 400 DEV persons' sensor constants.
Steady state (240 min) at fixed truth; compares fan (h_out 22) vs no fan (h_out 8), loose (r_gap 0.03) vs worn;
dT <= 0.6 at T_air >= 38 for every person at core 36.8-39.2 and s 0-1; dT monotone non-increasing in T_air. SIMULATION."""
import sys, json
sys.path.insert(0, "/home/claude/hg_ai/sim")
import numpy as np, pandas as pd
from velders.sensors import BandSensors, person_noise
S = set(json.load(open("/home/claude/hg_ai/model/sealed_hg2.json"))["sealed_sim_person_ids"])
df = pd.read_parquet("/home/claude/hg_ai/sim/data/persons.parquet"); df = df[~df.person_id.isin(S)]
P = {c: df[c].values for c in df.columns if df[c].dtype != object}
n = len(df)
NZ0 = {k: np.zeros((300, n)) if np.asarray(v).dtype != bool else np.zeros((300 // 60 + 2, n), bool)
       for k, v in person_noise(1, 300).items()}
NZ0["u_out"] = np.ones((300, n)); NZ0["u_wet"] = np.ones((300, n))     # noise-free, no outliers, no wet island
def steady(Ta, Tc, s, h_out=8.0, worn=2, r_gap=0.0, minutes=240):
    bs = BandSensors(P, NZ0)
    for t in range(minutes):
        o = bs.step(dict(T_core=np.full(n, Tc), s_skbf=np.full(n, s), T_air=np.full(n, Ta), RH_air=np.full(n, 45.0), HR_true=np.full(n, 70.0),
                         m_sweat=np.full(n, 20.0), deficit_pct=np.zeros(n)),
                    dict(worn=np.full(n, worn), h_out=np.full(n, h_out), r_gap=np.full(n, r_gap), sun_dT=np.zeros(n), flash=np.zeros(n),
                         asleep=np.zeros(n), rh_wet=np.zeros(n), a_std_true=np.full(n, 0.005), act_class=np.full(n, 2),
                         zangle_true=np.zeros(n), slip=np.zeros(n)))
    o = dict(o); o["dT"] = o["T1_true"] - o["T2_true"]; o["contam"] = o["T_air_meas"] - Ta - P["sht_T_off"]
    return o
res = {}
# fan episode
fan_ok = {}
for Ta in (26.0, 30.0, 32.0):
    a, f = steady(Ta, 37.0, 0.4), steady(Ta, 37.0, 0.4, h_out=22.0)
    fan_ok[Ta] = dict(T1_lower=float(np.mean(f["T1_true"] < a["T1_true"])), dT_higher=float(np.mean(f["dT"] > a["dT"])),
                      contam_lower=float(np.mean(f["contam"] < a["contam"])), mean_dT_change=float((f["dT"] - a["dT"]).mean()))
res["fan_episode_fraction_of_persons"] = fan_ok
# loose
lo, wo = steady(25.0, 37.0, 0.3, worn=1, r_gap=0.03), steady(25.0, 37.0, 0.3)
res["loose_vs_worn_fraction_of_persons"] = dict(T1_lower=float(np.mean(lo["T1_true"] < wo["T1_true"])), dT_lower=float(np.mean(lo["dT"] < wo["dT"])),
                                                PI_lower=float(np.mean(lo["PI"] < wo["PI"])))
# dT at >= 38 C, every person, core and s grid
worst = -9
for Ta in (38.0, 39.0, 40.0, 42.0):
    for Tc in (36.8, 37.5, 38.5, 39.2):
        for s in (0.0, 0.5, 1.0):
            worst = max(worst, float(steady(Ta, Tc, s, minutes=120)["dT"].max()))
res["max_dT_at_Tair_ge_38_every_person"] = worst
w34 = max(float(steady(34.0, Tc, s, minutes=120)["dT"].max()) for Tc in (37.0, 37.8) for s in (0.0, 0.6))
res["max_dT_at_Tair_34"] = w34
# monotone in T_air
prev = None; mono_bad = 0
for Ta in np.arange(20, 42, 1.0):
    d = steady(Ta, 37.3, 0.5, minutes=120)["dT"]
    if prev is not None:
        mono_bad += int((d > prev + 1e-9).sum())
    prev = d
res["dT_increase_steps_when_T_air_rises"] = mono_bad
print(json.dumps(res, indent=1)); json.dump(res, open("/home/claude/hg_ai/tests/t1/out/sensor_consistency.json", "w"), indent=1)
