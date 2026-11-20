"""B2b DEV data access (DEV ONLY). Never opens Brighton P2..P10, HeatIN sealed watches, SEALED-SIM sets or sealed office subjects.

  brighton_p1()  -> per-session minute tables from the FROZEN Python guardian (hg2-freeze-5 == working tree, asserted),
                    Brighton sheet P1 only (DEV, M18). Uses the pre-registered exam script's own parser / input mapping
                    (tests/real_exam_brighton.py: parse_sheet, minutes_for) so the DEV mapping is the exam mapping.
                    CC BY-ND 3.0: results stay in memory; nothing derived is written to disk except summary numbers.
  htt_oof()      -> HTT-DEV (65 young adults, real pill core, lab HR), NN LEAVE-ONE-SUBJECT-OUT predictions
                    (model/cache/v4aug/htt_oof.npz, B2 --loso) + the frozen v1.2 anchor; thermal inputs masked (HTT has none).
  sim_val()      -> SIM-DEV v4 calibration persons (100, never trained on; model/cache/v4aug/sim_val.npz) with the
                    DEPLOYED ensemble's per-member outputs recomputed from the cached raw features.
"""
import json, os, subprocess, sys
import numpy as np

REPO = "/home/claude/hg_ai"
TAG = os.environ.get("B2B_TAG", "v4aug")           # v4aug = the freeze-5 analysis (default), v5aug = the B2b-v5 retrain
CACHE = os.path.join(REPO, "model/cache", TAG)
RUNS = os.path.join(REPO, "model/runs", "b2b" if TAG == "v4aug" else "b2b_" + TAG)
WJSON = os.path.join(REPO, "model/export/hg2_weights.json")
F = np.float32
sys.path.insert(0, os.path.join(REPO, "guardian/py"))
sys.path.insert(0, os.path.join(REPO, "tests"))

SEALED_BRIGHTON = {"P%d" % i for i in range(2, 11)}


def assert_tree_is_freeze5():
    if TAG != "v4aug": return          # B2b-v5: the working tree carries the v5 export, by design
    r = subprocess.run(["git", "-C", REPO, "diff", "--quiet", "hg2-freeze-5", "--", "guardian/c", "guardian/py", "model/export"])
    assert r.returncode == 0, "guardian/model export differ from hg2-freeze-5"


class Ens:
    """deployed ensemble in float32/numpy, vectorised (same weights as guardian/py Weights)."""

    def __init__(self, path=WJSON):
        import hg_guardian_py as hg
        self.W = hg.Weights(path)

    def members(self, X):
        """X raw features [n,32] (NaN allowed) -> per-member outputs [5,n,9] in normalised space"""
        W = self.W
        z = np.where(np.isnan(X), 0, (X - W.xm) / W.xs).astype(F)
        z = np.where(np.isfinite(z), z, 0).astype(F)
        out = []
        for m in W.members:
            h1 = np.maximum(z @ m[0].T + m[1], 0); h2 = np.maximum(h1 @ m[2].T + m[3], 0); out.append(h2 @ m[4].T + m[5])
        return np.stack(out).astype(F)

    def core(self, R, k=0):
        """per-member raw [5,n,9] -> per-member core (degC) for output k (0 now, 1 f20, 2 f30)"""
        return R[..., k] * self.W.ys[k] + self.W.ym[k]

    def sd_total(self, R, k=0):
        """M11 sd rule: sqrt(mean_k(v^2 + eps) + between-member var) * Y_STD (degC)"""
        import hg_guardian_py as hg
        mu = R[..., k].mean(0); var = (R[..., k] ** 2).mean(0) - mu ** 2
        ale = (R[..., 6 + k] ** 2 + hg.K("HG2_EPS_V_EFF")).mean(0)
        return np.sqrt(ale + np.maximum(var, 0)) * self.W.ys[k], np.sqrt(np.maximum(var, 0)) * self.W.ys[k]


def brighton_p1(mode="hold", mutate=None, sheets=("P1",)):
    """list of session dicts: name, t (elapsed min, 0..end), X [n,32], core_now, core20_noff, v12_est, v12_f20, sd_now, level,
    rectal reference samples (t_ref, y_ref), profile. mutate(minute_dict, t) may alter inputs (counterfactuals)."""
    assert_tree_is_freeze5()
    import openpyxl, hg_guardian_py as hg, trace_io as tio
    import real_exam_brighton as RB
    W = hg.Weights(WJSON)
    wb = openpyxl.load_workbook(RB.XLSX, read_only=True, data_only=True)
    profs = RB.read_profiles(wb)
    if TAG == "v4aug":
        assert not set(sheets) & SEALED_BRIGHTON      # freeze-5 analysis: DEV sheet only
    # B2b-v5: Brighton is spent; P1..P10 are CALIBRATION data (manager, Nov 13) - never reported as held-out
    out = []
    for sh, sess in [(sh, x) for sh in sheets for x in RB.parse_sheet(wb[sh])]:
        prof = profs[sh]
        mins, off, end = RB.minutes_for(sess, mode, tio)
        if mutate is not None:
            for j, m in enumerate(mins): mutate(m, j - off)
        g = hg.Guardian(prof, tio.default_twin(), W)
        rec = {k: [] for k in ("core_now", "core20", "v12_est", "v12_f20", "sd_now", "level", "x", "nn_now", "nn20")}
        for m in mins:
            o = g.step(m)
            rec["core_now"].append(float(o["core_now"])); rec["core20"].append(float(o["aux"]["core20_noff"]))
            rec["v12_est"].append(float(o["aux"]["v12_est"])); rec["v12_f20"].append(float(o["aux"]["v12_f20"]))
            rec["sd_now"].append(float(o["core_sd_now"])); rec["level"].append(int(o["level"])); rec["x"].append(np.array(o["aux"]["x"], F))
            nm = o["aux"]["nn_mean"]   # raw ensemble (normalised) -> the NN's own core, before the AR anchor
            rec["nn_now"].append(float(nm[0] * W.ys[0] + W.ym[0])); rec["nn20"].append(float(nm[1] * W.ys[1] + W.ym[1]))
        d = {k: np.array(v)[off:] for k, v in rec.items()}
        d["X"] = d.pop("x")
        refs = [(int(r["el"]), r["rectal"]) for r in sess["rows"] if np.isfinite(r["rectal"]) and 0 <= r["el"] <= end]
        d.update(name=sh + "/" + sess["name"], sheet=sh, t=np.arange(0, end + 1), t_ref=np.array([a for a, b in refs]), y_ref=np.array([b for a, b in refs]),
                 bicep=np.array([r["bicep"] for r in sess["rows"]]), rows=sess["rows"], prof=prof, mins=mins[off:])
        out.append(d)
    return out


def htt_oof():
    h = np.load(os.path.join(CACHE, "htt_oof.npz"), allow_pickle=True)
    R = h["raw"]                                   # [5, n, 9] LOSO members, normalised
    ys, ym = h["ys"], h["ym"]
    core = R[..., 0] * ys[0] + ym[0]; c20 = R[..., 1] * ys[1] + ym[1]
    return dict(R=R, core_m=core, c20_m=c20, nn=core.mean(0), nn20=c20.mean(0), spread=core.std(0), y=h["Y"][:, 0], y20=h["Y"][:, 1],
                v12=h["aux_v12_est"], v12_f20=h["aux_v12_f20"], v12_sd=h["aux_v12_sd"], subj=h["subj"], sess=h["sess"], X=h["X"],
                ys=ys, ym=ym)


def sim_val(stride=1, ens=None):
    d = np.load(os.path.join(CACHE, "sim_val.npz"))
    X, Y, M = d["X"][::stride], d["Y"][::stride], d["M"][::stride]
    meta = json.load(open(os.path.join(CACHE, "sim_meta.json")))
    ids = set(meta["val_ids"])
    pid = M[:, 0].astype(int)
    assert set(np.unique(pid)) <= ids, "sim_val rows outside the 100 calibration persons"
    from sim_adapter import sealed_ids          # the same exclusion every DEV eval uses (set-1 id list only; sets 2/3 are ids 500+)
    assert not (set(np.unique(pid)) & sealed_ids()), "a sealed SIM person in the DEV calibration rows"
    assert pid.max() < 500
    ens = ens or Ens()
    R = np.concatenate([ens.members(X[i:i + 200000]) for i in range(0, len(X), 200000)], 1)
    cols = meta["meta_cols"]
    return dict(X=X, Y=Y, M={c: M[:, i] for i, c in enumerate(cols)}, R=R, ens=ens, pid=pid)
