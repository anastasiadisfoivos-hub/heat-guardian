"""T1: confirm the direction of the M3 bias claims with my OWN protocol code (only TwoNodeOlder is the builder's).
Cohort: DEV persons (sealed excluded), frailty < 1/3 (the builder's 'healthy' analogue), n reported. SIMULATION.
B-HR  (V4): 6 h at 22 C then 8 h at 22 or 36 C / 45 % seated; HR change and core change vs the 22 C arm;
            HR-per-core slope vs Meade 2024 (+14 bpm for +0.9 C -> 15.6 bpm/C).
B-REST(V13): 34 C rest, P_a ramp 12 mmHg + 1 mmHg / 5 min after 120 min at 12 mmHg; MY inflection rule: first minute the core
            exceeds its own linear extrapolation (fit over the 30 min before the ramp) by 0.2 C; P_a there vs PSU 3.53 kPa.
B-BED (V7): 8 h lying (met 0.82 and 0.70) clo 0.6 at 31 C vs 22 C, from 08:00 after 6 h at 22 C; peak rise and ABSOLUTE peak
            vs O'Connor 2026 (peak 37.8 C, +1.1)."""
import sys, json
sys.path.insert(0, "/home/claude/hg_ai/sim")
import numpy as np, pandas as pd
from velders.body import TwoNodeOlder, p_sat_torr
S = set(json.load(open("/home/claude/hg_ai/model/sealed_hg2.json"))["sealed_sim_person_ids"])
df = pd.read_parquet("/home/claude/hg_ai/sim/data/persons.parquet")
df = df[(~df.person_id.isin(S)) & (df.frailty < 1 / 3)]
P = {c: df[c].values for c in df.columns if df[c].dtype != object}
n = len(df)
def rest_met(base):
    return np.minimum(base * P["met_rest_mult"], 1.08)
def run(T, rh, met, clo=0.4, hours=8, v=0.1):
    b = TwoNodeOlder(P, minute_of_day0=120)
    for t in range(360):
        b.step(dict(t_db=22.0, rh=45.0, met=rest_met(0.86), clo=0.4, v_air=0.1, minute_of_day=120 + t))
    c0 = b.t_core.copy(); core, hr = [], []
    for t in range(hours * 60):
        o = b.step(dict(t_db=T, rh=rh, met=met, clo=clo, v_air=v, minute_of_day=480 + t))
        core.append(o["T_core"]); hr.append(o["HR"])
    return c0, np.array(core), np.array(hr)
res = {"n_cohort": int(n)}
c0, c22, h22 = run(22.0, 45.0, rest_met(0.86)); _, c36, h36 = run(36.0, 45.0, rest_met(0.86))
dHR = h36[-60:].mean(0) - h22[-60:].mean(0); dC = c36[-1] - c22[-1]
res["HR"] = dict(dHR_36_vs_22_mean=float(dHR.mean()), target_dHR=14.0, dCore_36_vs_22=float(dC.mean()), target_dCore=0.9,
                 slope_bpm_per_C_sim=float(dHR.mean() / dC.mean()), slope_meade=14 / 0.9,
                 implied_core_read_from_real_14bpm=float(14.0 / (dHR.mean() / dC.mean())),
                 core_0800_mean=float(c0.mean()))
# rest humid ramp at 34 C
b = TwoNodeOlder(P, minute_of_day0=7 * 60)
met = rest_met(0.86); core, pa_h = [], []
for i in range(120 + 400):
    pa = 12.0 + (max(0, i - 120) // 5 if i >= 120 else 0)
    o = b.step(dict(t_db=34.0, rh=100 * pa / p_sat_torr(34.0), met=met, clo=0.4, v_air=0.2, minute_of_day=7 * 60 + i))
    core.append(o["T_core"]); pa_h.append(pa)
core = np.array(core); pa_h = np.array(pa_h)
x = np.arange(90, 120); pc = []
for j in range(n):
    a, c = np.polyfit(x, core[90:120, j], 1)
    dev = core[120:, j] - (a * np.arange(120, core.shape[0]) + c)
    k = np.nonzero(dev > 0.2)[0]
    pc.append(pa_h[120 + k[0]] * 0.133322 if k.size else np.nan)
pc = np.array(pc)
res["REST34"] = dict(Pa_crit_kPa_mean=float(np.nanmean(pc)), frac_no_inflection=float(np.isnan(pc).mean()), target=3.53,
                     builder_value=4.70)
# bed rest
for metv in (0.82, 0.70):
    m = rest_met(metv)
    c0, a22, _ = run(22.0, 45.0, m, clo=0.6); _, a31, _ = run(31.0, 45.0, m, clo=0.6)
    res[f"BED_met{metv}"] = dict(peak_rise_31=float((a31.max(0) - c0).mean()), peak_rise_22=float((a22.max(0) - c0).mean()),
                                 rise_31_minus_22=float(((a31.max(0) - c0) - (a22.max(0) - c0)).mean()),
                                 abs_peak_31=float(a31.max(0).mean()), target_abs_peak=37.8, target_rise=1.1)
print(json.dumps(res, indent=1)); json.dump(res, open("/home/claude/hg_ai/tests/t1/out/m3_bias.json", "w"), indent=1)
