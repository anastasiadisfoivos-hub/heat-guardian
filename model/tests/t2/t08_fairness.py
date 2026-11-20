"""T2-08 is "NN beats v1.2 at the same FA budget" (M11 / m5.gain_test) a fair comparison?  SIMULATION, Virtual Elders v4,
100 calibration persons, exported weights + tester forward, own episode/FA scorer (REPORT 5 definitions).
 (a) reproduce the builder's procedure: v1.2 rule FIXED at 37.85 - margin, NN threshold offset tuned per person fold (5 folds)
     with FA/h <= v1.2's FA/h on the other folds;
 (b) symmetric: give v1.2 the SAME offset grid and the SAME nested tuning, at the same budgets (0.10, 0.15, 0.17, v1.2 default);
 (c) same on the HR-scaled view (M3.2: real older hearts rise less) where v1.2's sim-HR bias is removed.
Run: python3 tests/t2/t08_fairness.py"""
import json, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/hg_ai/tests/t2")
from t2lib import load_weights, ens, ROOT
W = load_weights(); meta = json.load(open(ROOT + "/model/cache/v4aug/sim_meta.json")); mc = meta["meta_cols"]
P = pd.read_parquet(ROOT + "/sim/data/persons.parquet").set_index("person_id")
SEED = 20261112
OFFS = [float(x) for x in np.round(np.arange(-0.6, 0.61, 0.05), 2)] + [9.0]


def margin(age, bb, low, diu_ace):
    md = 0.20 if age >= 65 else 0.0
    if diu_ace: md += 0.10
    if low: md += 0.10
    if bb: md += 0.10
    return min(md, 0.20)


def sessions(view):
    d = np.load(ROOT + "/model/cache/v4aug/sim_%s.npz" % view); X, Y, M = d["X"], d["Y"], d["M"]
    col = lambda n: M[:, mc.index(n)]
    E = ens(W, X); pid = col("pid").astype(int); t = col("t_min").astype(int); dt = col("daytype").astype(int)
    md = np.array([margin(P.loc[p, "age"], bool(P.loc[p, "med_bb_nonsel"] or P.loc[p, "med_bb_sel"]), bool(P.loc[p, "med_antichol"]),
                          bool(P.loc[p, "med_diuretic"] or P.loc[p, "med_ace_arb"])) for p in np.unique(pid)])
    mdd = dict(zip(np.unique(pid), md))
    key = pid * 100 + t // 1440; S = {}
    for cls in range(4):
        sel = dt == cls; ks = np.unique(key[sel]); arr = {n: np.full((len(ks), 1440), np.nan) for n in ("core", "v12", "nn", "z", "lp")}
        pos = {k: i for i, k in enumerate(ks)}; r = np.where(sel)[0]; i = np.array([pos[k] for k in key[r]]); m = t[r] % 1440
        arr["core"][i, m] = Y[r, 0]; arr["v12"][i, m] = col("v12_f20")[r]; arr["nn"][i, m] = E["core_20"][r]; arr["z"][i, m] = col("v12_z")[r]; arr["lp"][i, m] = E["lp385"][r]
        arr["subj"] = ks // 100; arr["md"] = np.array([mdd[s] for s in ks // 100]); S[cls] = arr
    return S


def fut_max(c, h=60):
    # max of c[a .. a+h]
    s = pd.DataFrame(c[:, ::-1].T).rolling(h + 1, min_periods=1).max().values.T[:, ::-1]
    return s


def score(mask, core, thr, fm):
    """mask, core [n,1440]; returns det, fa, has per session"""
    n = len(mask); det = np.zeros(n); fa = np.zeros(n); has = np.zeros(n, bool)
    c = np.nan_to_num(core, nan=-1)
    two = (c[:, :-1] >= thr) & (c[:, 1:] >= thr)
    for s in range(n):
        ev = np.flatnonzero(two[s]); ev = ev[0] if len(ev) else None; has[s] = ev is not None
        m = np.r_[0, mask[s].astype(np.int8), 0]; dd = np.diff(m); st = np.flatnonzero(dd == 1); en = np.flatnonzero(dd == -1) - 1
        eps = []
        for a, b in zip(st, en):
            if b - a + 1 >= 2:
                if eps and a - eps[-1][1] < 10: eps[-1] = (eps[-1][0], b)
                else: eps.append((a, b))
        for a, b in eps:
            if ev is not None and det[s] == 0 and a <= ev + 10 and b >= ev - 45: det[s] = 1
            if not fm[s, a] >= thr: fa[s] += 1
    return det, fa, has


def nested(rule_fn, grid, S, thr, budget_fn, nfold=5):
    core = S["core"]; fm = fut_max(np.nan_to_num(core, nan=-1)); subj = S["subj"]; hours = 24.0
    tabs = [score(rule_fn(g), core, thr, fm) for g in grid]
    us = np.unique(subj); f = dict(zip(us, np.random.default_rng(SEED + 77).permutation(len(us)) % nfold)); fold = np.array([f[x] for x in subj])
    D = np.zeros(len(subj)); FA = np.zeros(len(subj)); has = tabs[0][2]; chosen = []
    for k in range(nfold):
        tr = fold != k; B = budget_fn(tr); best = None
        for gi, (det, fa, _) in enumerate(tabs):
            fah = fa[tr].sum() / (tr.sum() * hours); se = det[tr & has].sum() / max((tr & has).sum(), 1)
            if fah <= B + 1e-12 and (best is None or se > best[1] or (se == best[1] and grid[gi] > grid[best[0]])): best = (gi, se)
        gi = best[0] if best else len(grid) - 1; chosen.append(grid[gi]); D[~tr] = tabs[gi][0][~tr]; FA[~tr] = tabs[gi][1][~tr]
    return dict(sens=float(100 * D[has].sum() / max(has.sum(), 1)), events=int(has.sum()), fa_h=float(FA.sum() / (len(subj) * hours)), chosen=chosen)


def fixed(mask, S, thr):
    core = S["core"]; fm = fut_max(np.nan_to_num(core, nan=-1)); det, fa, has = score(mask, core, thr, fm)
    return dict(sens=float(100 * det[has].sum() / max(has.sum(), 1)), events=int(has.sum()), fa_h=float(fa.sum() / (len(det) * 24.0))), (det, fa, has)


R = {"label": "SIMULATION (Virtual Elders v4) 100 calibration persons"}
names = {0: "S1 ordinary", 1: "PRE", 2: "POST", 3: "S2 heat wave"}
for view in ("val", "valaug"):
    S_all = sessions(view); RV = {}
    for cls, S in S_all.items():
        md = S["md"][:, None]; thr = 38.0
        v12 = np.nan_to_num(S["v12"], nan=-99); nn_ = np.nan_to_num(S["nn"], nan=-99)
        base, (bd, bf, bh) = fixed(v12 >= 37.85 - md, S, thr)
        fold_budget = lambda tr: bf[tr].sum() / (tr.sum() * 24.0)
        out = dict(v12_fixed=base, nn_fixed_37_85=fixed(nn_ >= 37.85 - md, S, thr)[0])
        out["builder_procedure_nn_tuned_at_v12_budget"] = nested(lambda g: nn_ >= 37.85 - md + g, OFFS, S, thr, fold_budget)
        out["symmetric_v12_tuned_at_v12_budget"] = nested(lambda g: v12 >= 37.85 - md + g, OFFS, S, thr, fold_budget)
        for B in (0.10, 0.15, 0.17):
            out["matched_budget_%.2f" % B] = dict(nn=nested(lambda g: nn_ >= 37.85 - md + g, OFFS, S, thr, lambda tr: B),
                                                  v12=nested(lambda g: v12 >= 37.85 - md + g, OFFS, S, thr, lambda tr: B))
        RV[names[cls]] = out
        print(view, names[cls], json.dumps({k: (v if "matched" not in k else {kk: (vv["sens"], round(vv["fa_h"], 3)) for kk, vv in v.items()}) for k, v in out.items()}), flush=True)
    R[view] = RV
b = json.load(open(ROOT + "/model/runs/v4aug/results_m5.json"))["m6_4_nn_vs_v12_same_budget"]
R["builder_claims_drink"] = {k: dict(v12=(v["Drink"]["v12"]["sensitivity"], v["Drink"]["v12"]["fa_per_h"]), nn=(v["Drink"]["nn_same_budget"]["sensitivity"], v["Drink"]["nn_same_budget"]["fa_per_h"]))
                             for k, v in b.items() if isinstance(v, dict) and "Drink" in v}
json.dump(R, open(ROOT + "/tests/t2/out/t08_fairness.json", "w"), indent=1)
