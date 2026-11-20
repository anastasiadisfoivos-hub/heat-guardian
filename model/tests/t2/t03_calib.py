"""T2-03 re-derive SIM-DEV calibration-person metrics with the tester's own forward (t2lib) from the exported weights.
Run: cd /home/claude/hg_ai && python3 tests/t2/t03_calib.py     (SIMULATION, Virtual Elders v4, 100 calibration persons)
Also spot-checks that the cached targets equal minutes_dev_v4.parquet truth for 2 calibration persons."""
import json, sys
import numpy as np, pandas as pd, pyarrow.parquet as pq
sys.path.insert(0, "/home/claude/hg_ai/tests/t2")
from t2lib import load_weights, ens, ROOT
from sklearn.metrics import roc_auc_score
W = load_weights(); R = {"label": "SIMULATION (Virtual Elders v4) - 100 SIM-DEV calibration persons"}
meta = json.load(open(ROOT + "/model/cache/v4aug/sim_meta.json")); mc = meta["meta_cols"]
P = pd.read_parquet(ROOT + "/sim/data/persons.parquet").set_index("person_id")
seal = set(json.load(open(ROOT + "/model/sealed_hg2.json"))["sealed_sim_person_ids"])
dev = sorted(set(P.index) - seal)
edges_dev = np.quantile(P.loc[dev, "kappa_core"].values, [1 / 3, 2 / 3])
R["kappa_edges_builder_all500"] = meta["kappa_tercile_edges"]; R["kappa_edges_dev400_only"] = edges_dev.tolist()


def boot_person(vals, pid, fn, B=500, seed=1):
    us = np.unique(pid); ix = {u: np.where(pid == u)[0] for u in us}; rng = np.random.default_rng(seed); o = []
    for _ in range(B):
        r = np.concatenate([ix[u] for u in rng.choice(us, len(us))]); o.append(fn(r))
    return [float(np.percentile(o, 2.5)), float(np.percentile(o, 97.5))]


def metrics(view):
    d = np.load(ROOT + "/model/cache/v4aug/sim_%s.npz" % view); X, Y, M = d["X"], d["Y"].astype(np.float64), d["M"]
    col = lambda n: M[:, mc.index(n)]
    pid = col("pid").astype(int); assert not set(pid) & seal and len(set(pid)) == 100
    E = ens(W, X); out = dict(n_rows=int(len(X)))
    for j, h in enumerate(("now", "20", "30")):
        m = np.isfinite(Y[:, j]); e = np.abs(E["core_" + h] - Y[:, j]); sd = E["sd_" + h]
        cov = e <= 1.645 * sd
        out["MAE_" + h] = float(np.nanmean(e[m])); out["MAE_%s_95_person_boot" % h] = boot_person(e, pid, lambda r: np.nanmean(e[r][m[r]]))
        out["coverage_%s_pct" % h] = float(cov[m].mean() * 100)
        out["coverage_%s_95_person_boot" % h] = boot_person(cov, pid, lambda r: cov[r][m[r]].mean() * 100)
        out["coverage_%s_floor008_pct" % h] = float((e <= 1.645 * np.maximum(sd, 0.08))[m].mean() * 100)
        pp = np.array([cov[m & (pid == p)].mean() for p in np.unique(pid)])
        out["coverage_%s_per_person" % h] = dict(median=float(np.median(pp) * 100), p10=float(np.percentile(pp, 10) * 100), min=float(pp.min() * 100),
                                              share_persons_below_80=float((pp < 0.8).mean() * 100), share_persons_above_98=float((pp > 0.98).mean() * 100))
    e = np.abs(E["core_now"] - Y[:, 0]); sd = E["sd_now"]
    for nm, q in (("quintile", 0.2), ("decile", 0.1)):
        lo, hi = np.quantile(sd, [q, 1 - q]); out["informativeness_" + nm] = float(e[sd >= hi].mean() / e[sd <= lo].mean())
    out["informativeness_quintile_95_person_boot"] = boot_person(e, pid, lambda r: (lambda s, ee: ee[s >= np.quantile(s, .8)].mean() / ee[s <= np.quantile(s, .2)].mean())(sd[r], e[r]))
    out["spearman_sd_abs_err"] = float(pd.Series(sd).corr(pd.Series(e), method="spearman"))
    # person-level: does a person's mean sd track a person's MAE?
    g = pd.DataFrame(dict(p=pid, e=e, s=sd)).groupby("p").mean(); out["spearman_person_mean_sd_vs_person_MAE"] = float(g.s.corr(g.e, method="spearman"))
    out["btw_share_of_var_now"] = float(np.mean(E["btw_now"] ** 2) / np.mean(sd ** 2))
    out["sd_now_quantiles_5_50_95"] = np.quantile(sd, [.05, .5, .95]).tolist()
    for j, nm in ((3, "p38"), (4, "p385")):
        m = np.isfinite(Y[:, j]); out["AUC_" + nm] = float(roc_auc_score(Y[m, j], E["lp" + nm[1:]][m])); out["prev_" + nm] = float(Y[m, j].mean())
    kap = P.loc[pid, "kappa_core"].values
    for tag, edges in (("builder_edges", meta["kappa_tercile_edges"]), ("dev_edges", edges_dev)):
        t = np.searchsorted(edges, kap)
        out["MAE_by_kappa_" + tag] = {"T%d" % (k + 1): [float(np.nanmean(np.abs(E["core_" + h] - Y[:, j])[t == k])) for j, h in enumerate(("now", "20", "30"))] for k in range(3)}
    out["MAE_now_by_daytype"] = {str(k): float(np.mean(e[col("daytype") == k])) for k in range(4)}
    out["v12_est_MAE_now_same_rows"] = float(np.nanmean(np.abs(col("v12_est") - Y[:, 0])))
    # conformal q90 of |e| no reading (should equal HG2_CONF_HALF_UNCAL for view val)
    r = np.sort(e); out["q90_abs_err_now"] = float(r[min(len(r) - 1, int(np.ceil((len(r) + 1) * .9)) - 1)])
    return out, (X, Y, M, E)


R["val"], pack = metrics("val")
R["valaug_HRscaled"], _ = metrics("valaug")
cl = json.load(open(ROOT + "/model/runs/v4aug/results_eval_hg2.json"))["sim_dev_val"]
R["builder_claims"] = dict(coverage_no_floor=cl["coverage_1.645sd_no_floor_pct"], informativeness=cl["sd_informative"], overall=cl["overall"],
                           AUC_p385=cl["AUC_p385"], label=cl["label"])
# truth spot check vs parquet (calibration persons only, minutes_dev_v4)
X, Y, M, E = pack; pid = M[:, mc.index("pid")].astype(int); tmin = M[:, mc.index("t_min")].astype(int)
pf = pq.ParquetFile(ROOT + "/sim/data/minutes_dev_v4.parquet"); rg = {}
for i in range(pf.metadata.num_row_groups): rg[int(pf.metadata.row_group(i).column(0).statistics.min)] = i
sc = {}
for p in sorted(set(pid))[:2]:
    assert p not in seal
    t = pf.read_row_group(rg[p], columns=["person_id", "t_min", "T_core"]).to_pandas().set_index("t_min")
    s = pid == p; sc[int(p)] = dict(rows=int(s.sum()), max_abs_core_now=float(np.abs(t.loc[tmin[s], "T_core"].values - Y[s, 0]).max()),
                                     max_abs_core_30=float(np.nanmax(np.abs(t.reindex(tmin[s] + 30)["T_core"].values - Y[s, 2]))))
R["truth_spot_check"] = sc
json.dump(R, open(ROOT + "/tests/t2/out/t03_calib.json", "w"), indent=1)
print(json.dumps(R, indent=1))
