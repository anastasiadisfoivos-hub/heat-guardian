"""T2-05 flux-permutation and sign/monotonicity attacks (SIMULATION, 100 calibration persons, exported weights, own forward).
Run: python3 tests/t2/t05_flux_sign.py"""
import json, sys
import numpy as np
sys.path.insert(0, "/home/claude/hg_ai/tests/t2")
from t2lib import load_weights, ens, flux_off, ROOT
W = load_weights(); meta = json.load(open(ROOT + "/model/cache/v4aug/sim_meta.json")); mc = meta["meta_cols"]
d = np.load(ROOT + "/model/cache/v4aug/sim_val.npz"); X, Y, M = d["X"], d["Y"], d["M"]
tin = M[:, mc.index("T_in")]; tair = X[:, 6]; fv = X[:, 5] == 1
R = {"label": "SIMULATION (Virtual Elders v4), 100 calibration persons"}
E0 = ens(W, X); E1 = ens(W, flux_off(X)); dl = np.abs(E1["core_now"] - E0["core_now"]); d20 = np.abs(E1["core_20"] - E0["core_20"])
perm = {}
for nm, s in (("T_in>=37", tin >= 37), ("T_in 34-37", (tin >= 34) & (tin < 37)), ("T_in>=34", tin >= 34),
              ("band t_air>=37", tair >= 37), ("band t_air 34-37", (tair >= 34) & (tair < 37)), ("band t_air>=34 (ARCH wording)", tair >= 34),
              ("all minutes", np.ones(len(X), bool)), ("all flux_valid minutes", fv)):
    if not s.any(): perm[nm] = None; continue
    perm[nm] = dict(n=int(s.sum()), share_flux_valid_before_pct=float(fv[s].mean() * 100), share_le_030_pct=float((dl[s] <= .3).mean() * 100),
                    p99=float(np.percentile(dl[s], 99)), max=float(dl[s].max()),
                    p99_on_flux_valid_rows=float(np.percentile(dl[s & fv], 99)) if (s & fv).any() else None,
                    share_le_030_on_flux_valid_rows=float((dl[s & fv] <= .3).mean() * 100) if (s & fv).any() else None,
                    core20_p99=float(np.percentile(d20[s], 99)), passes_99pct=bool((dl[s] <= .3).mean() >= .99))
R["flux_permutation"] = perm
# harder attack: in heat, transplant flux features from flux-valid rows (shuffle) into rows of the same regime
rng = np.random.default_rng(5); s = np.where(tin >= 34)[0]; donors = np.where(fv & (tin >= 30))[0]
Xs = X[s].copy(); pick = rng.choice(donors, len(s)); Xs[:, [3, 4, 5]] = X[pick][:, [3, 4, 5]]; Xs[:, 25] = Xs[:, 0] + (X[pick, 25] - X[pick, 0])
Es = ens(W, Xs); ds = np.abs(Es["core_now"] - E0["core_now"][s])
R["flux_transplant_T_in>=34"] = dict(n=int(len(s)), donors_T_in_ge_30=int(len(donors)), share_le_030=float((ds <= .3).mean() * 100), p99=float(np.percentile(ds, 99)), max=float(ds.max()),
                                     note="flux features copied from flux-valid rows at T_in>=30: how much would a spurious flux reading in heat move core_now")
# sign checks (10,000 random rows) -- as in the brief, single-feature finite differences
r = rng.choice(len(X), 10000, replace=False); Xr = X[r]; base = ens(W, Xr)
sg = {}
for nm, j, h in (("hr_reserve", 14, 0.05), ("kf", 20, 0.10)):
    Xp = Xr.copy(); Xp[:, j] += h; Ep = ens(W, Xp)
    for out in ("lp385", "lp38", "core_now", "core_20"):
        g = (Ep[out] - base[out]) / h
        sg["%s->%s" % (nm, out)] = dict(mean=float(g.mean()), share_negative_pct=float((g < 0).mean() * 100), min=float(g.min()))
# physically consistent HR step: +5 bpm on hr, hr_ewm5 (+0.906 = 5*(1-0.8187)... use full 5), hr_above_rest, hr_reserve
Xp = Xr.copy(); hrmax_minus_rest = (Xr[:, 13] / np.where(np.abs(Xr[:, 14]) > 1e-6, Xr[:, 14], np.nan))
Xp[:, 10] += 5; Xp[:, 11] += 5; Xp[:, 13] += 5; Xp[:, 14] += 5 / np.nan_to_num(hrmax_minus_rest, nan=80.0)
Ep = ens(W, Xp)
for out in ("lp385", "lp38", "core_now", "core_20"):
    g = Ep[out] - base[out]; sg["hr+5bpm(coherent)->" + out] = dict(mean=float(g.mean()), share_negative_pct=float((g < 0).mean() * 100), min=float(g.min()))
R["sign_checks"] = sg
# monotone sweep of kf 36.5..39.5 on 1,000 rows: largest drop of logit_p385 along the sweep
rr = r[:1000]; grid = np.linspace(36.5, 39.5, 31); L = []
for v in grid:
    Xg = X[rr].copy(); Xg[:, 20] = v; L.append(ens(W, Xg)["lp385"])
L = np.array(L); drops = np.maximum.accumulate(L, 0) - L
R["kf_sweep_36.5_39.5"] = dict(rows=1000, share_rows_any_drop_gt_0_1=float((drops.max(0) > .1).mean() * 100),
                               share_rows_any_drop_gt_0_5=float((drops.max(0) > .5).mean() * 100), max_drop=float(drops.max()))
grid = np.linspace(0, 1.0, 21); L = []
for v in grid:
    Xg = X[rr].copy(); Xg[:, 14] = v; L.append(ens(W, Xg)["lp385"])
L = np.array(L); drops = np.maximum.accumulate(L, 0) - L
R["hr_reserve_sweep_0_1"] = dict(rows=1000, share_rows_any_drop_gt_0_1=float((drops.max(0) > .1).mean() * 100),
                                 share_rows_any_drop_gt_0_5=float((drops.max(0) > .5).mean() * 100), max_drop=float(drops.max()))
b = json.load(open(ROOT + "/model/runs/v4aug/results_eval_hg2.json"))["sim_dev_val"]
R["builder_claims"] = dict(flux_permutation=b["flux_permutation"], sign=b["sign_checks_logit_p385"])
json.dump(R, open(ROOT + "/tests/t2/out/t05_flux_sign.json", "w"), indent=1); print(json.dumps(R, indent=1))
