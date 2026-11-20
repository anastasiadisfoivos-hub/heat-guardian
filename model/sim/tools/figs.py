"""Figures for VALIDATION.md (SIMULATION). python3 -I /home/claude/hg_ai/sim/tools/figs.py"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from velders.protocols import load_persons, meade, psu
from velders.validate import healthy, thirst_policy_factory

FIG = "/home/claude/hg_ai/sim/figs/"
P = healthy(load_persons())

# 1. Meade 2024 8-h curves
fig, ax = plt.subplots(2, 2, figsize=(10, 7))
tg = {26: dict(core=0.2, skin=32.9, hr=62, sw=26), 31: dict(core=0.7, skin=34.9, hr=69, sw=31), 36: dict(core=0.9, skin=35.9, hr=74, sw=80)}
R22 = meade(P, 22, drink_policy=thirst_policy_factory(P))
t = np.arange(480) / 60
for T, c in zip((26, 31, 36), ("tab:green", "tab:orange", "tab:red")):
    R = meade(P, T, drink_policy=thirst_policy_factory(P))
    ax[0, 0].plot(t, (R["T_core"] - R["c0"]).mean(1) - (R22["T_core"] - R22["c0"]).mean(1), c=c, label=f"{T} C")
    ax[0, 0].errorbar(8, tg[T]["core"], yerr=0.15, fmt="o", c=c)
    ax[0, 1].plot(t, R["T_skin"].mean(1), c=c); ax[0, 1].errorbar(8, tg[T]["skin"], yerr=0.5, fmt="o", c=c)
    ax[1, 0].plot(t, R["HR"].mean(1) - R22["HR"][-60:].mean() + 60, c=c); ax[1, 0].errorbar(8, tg[T]["hr"], yerr=3, fmt="o", c=c)
    ax[1, 1].plot(t, (R["E_sk"] / 0.68).mean(1), c=c); ax[1, 1].errorbar(8, tg[T]["sw"], yerr=15, fmt="o", c=c)
for a, l in zip(ax.ravel(), ("core rise vs 22 C arm (C)", "mean skin (C)", "HR (60 + change, bpm)", "skin water loss g/(h m2)")):
    a.set_title(l); a.set_xlabel("h")
ax[0, 0].legend()
fig.suptitle("SIMULATION - Virtual Elders vs Meade 2024 (dots = targets +- tolerance), healthy tercile n=%d" % len(P["seed"]))
fig.tight_layout(); fig.savefig(FIG + "meade2024_8h.png", dpi=110); plt.close(fig)

# 2. one S2 week for one person
m = pd.read_parquet("/home/claude/hg_ai/sim/data/minutes_dev.parquet", filters=[("person_id", "==", 0)])
x = m.t_min / 1440 + 1
fig, ax = plt.subplots(5, 1, figsize=(12, 11), sharex=True)
ax[0].plot(x, m.T_in, label="T_in (room)"); ax[0].plot(x, m.T_out, label="T_out", alpha=0.6); ax[0].legend(); ax[0].set_ylabel("C")
ax[1].plot(x, m.T_core, c="tab:red"); ax[1].axhline(38, ls="--", c="k", lw=0.8); ax[1].set_ylabel("T_core C")
ax[2].plot(x, m.HR_meas, ".", ms=1, alpha=0.4, label="HR_meas"); ax[2].plot(x, m.HR_true, lw=0.8, c="k", label="HR_true"); ax[2].legend(); ax[2].set_ylabel("bpm")
ax[3].plot(x, m.T1, lw=0.8, label="T1"); ax[3].plot(x, m.T1 - m.T2, lw=0.8, label="dT = T1-T2"); ax[3].legend(); ax[3].set_ylabel("C")
ax[4].plot(x, m.PI, lw=0.6); ax[4].set_ylabel("PI %"); ax[4].set_xlabel("day")
fig.suptitle("SIMULATION - person 0, 10 days (" + ("heat wave" if m.T_out.max() > 37 else "ordinary") + ")")
fig.tight_layout(); fig.savefig(FIG + "s2_week_person0.png", dpi=110); plt.close(fig)

# 3. PSU critical-limit cloud
fig, ax = plt.subplots(figsize=(8, 6))
meas = {"older ADL": ([34, 36, 38, 40, 42.9, 40.3], [3.41, 3.21, 3.07, 2.54, 1.60, 2.13]),
        "older Rest": ([34, 36, 38, 40, 46.1, 44.1], [3.53, 3.52, 3.57, 2.88, 1.60, 2.13])}
for act, c in (("adl", "tab:red"), ("rest", "tab:blue")):
    Ts, Ps = [], []
    for T in (34, 36, 38, 40):
        r = psu(P, "humid", T, act); Ts += list(r["T_crit"]); Ps += list(r["Pa_crit_kPa"])
    for pa in (12, 16):
        r = psu(P, "dry", pa, act); Ts += list(r["T_crit"]); Ps += list(r["Pa_crit_kPa"])
    ax.scatter(Ts, Ps, s=6, alpha=0.3, c=c, label=f"SIM older {act.upper()}")
    k = "older ADL" if act == "adl" else "older Rest"
    ax.plot(*meas[k], "s", c=c, mec="k", ms=9, label=f"PSU measured {k}")
for T in (36, 40):
    r = psu(P, "humid", T, "adl", young=True)
    ax.scatter(r["T_crit"], r["Pa_crit_kPa"], s=6, c="tab:green", alpha=0.3, label="SIM young twin ADL" if T == 36 else None)
ax.set_xlabel("T_db,crit (C)"); ax.set_ylabel("P_a,crit (kPa)"); ax.legend(fontsize=8)
ax.set_title("SIMULATION - critical environmental limits (PSU HEAT protocol)")
fig.tight_layout(); fig.savefig(FIG + "psu_critical_cloud.png", dpi=110); plt.close(fig)
print("figures written")
