"""hg2 training (ARCH 4.4 steps 1-3). PROVISIONAL: sim v1 (M2.1); the final run repeats this on sim v2.
  python3 -m model.hg2.train --seed k        (k = 1..5; member k-1; seed 5 = robust member, flux channel always off)
     step 1 pretrain on SIM-DEV view (k-1), bootstrap over persons, Adam lr 1e-3, batch 4096, 30 epochs,
            early stopping on the 40-person SIM-DEV validation subset (never SEALED-SIM)
     step 3 fine-tune on HTT-DEV (65 people, 130 sessions), 10 epochs at lr 1e-4, 25 % of every batch SIM, real rows x2
  python3 -m model.hg2.train --loso          nested-ready leave-one-subject-out fine-tunes on HTT-DEV for all 5 members
                                             (pretrained weights reused: pretraining never sees HTT) -> cache/htt_oof.npz
Every artefact records the SHA-256 of minutes_dev.parquet (M2.1). Logs: model/train_log.json."""
import argparse, json, os, time, zlib
import numpy as np
from .common import RUNS, CACHE, MODEL, SEED, data_provenance, assert_no_sealed, sealed, LABEL_SIM, LABEL_HTT
from . import nn, features as FT, data_htt
from .simio import persons_table

F = np.float32
MEM = os.path.join(RUNS, "members")
LOG = os.path.join(RUNS, "train_log.json")
NORM = os.path.join(CACHE, "norm.json")
DELTA = np.array([0.3, 0.3, 0.3, 0, 0, 1.0])


def load_view(v):
    d = np.load(os.path.join(CACHE, "sim_%s.npz" % v))
    return d["X"], d["Y"], d["M"]


def check_index(M):
    ids = np.unique(M[:, 0]).astype(int)
    assert_no_sealed(ids)
    return ids


def norm():
    if os.path.exists(NORM): return {k: np.array(v, F) for k, v in json.load(open(NORM)).items() if k in ("xm", "xs", "ym", "ys")}
    Xs = []; Ys = []
    for v in ("v0", "v1", "v2", "v3"):
        X, Y, M = load_view(v); check_index(M); Xs.append(X[::4]); Ys.append(Y[::4])
    X = np.concatenate(Xs).astype(np.float64); Y = np.concatenate(Ys).astype(np.float64)
    xm = np.nanmean(X, 0); xs = np.nanstd(X, 0); xs = np.where(xs < 1e-3, 1.0, xs)
    ym = np.nanmean(Y[:, :3], 0); ys = np.nanstd(Y[:, :3], 0)
    d = dict(xm=xm.astype(F).tolist(), xs=xs.astype(F).tolist(), ym=ym.astype(F).tolist(), ys=ys.astype(F).tolist(),
             note="computed on SIM-DEV train views 0-3 (every 4th kept row); NaN features -> z = 0", provenance=data_provenance())
    json.dump(d, open(NORM, "w"), indent=1)
    return {k: np.array(d[k], F) for k in ("xm", "xs", "ym", "ys")}


def flux_off(X):
    """feature-level 'flux_valid forced 0' (dT, dT_d10, flux_valid = 0; core_flux = t1)"""
    X = X.copy(); X[:, 3] = 0; X[:, 4] = 0; X[:, 5] = 0; X[:, 25] = X[:, 0]
    return X


PROFILE_Z = [27, 29]          # age, bmi: jittered so the net cannot key on a person's exact profile (person memorisation)


def augment(z, rng, sd_prof=0.5, sd_all=0.03):
    z = z + rng.normal(0, sd_all, z.shape).astype(F)
    z[:, PROFILE_Z] += rng.normal(0, sd_prof, (len(z), len(PROFILE_Z))).astype(F)
    return z


MONO = [(14, 0.10), (20, 0.20)]   # (feature, raw step): hr_reserve, kf  -- REPORT 5b sign rule on the Danger logits
MONO_LAMBDA = 2.0


def mono_grads(P, z, N, nsub=1024, rng=None):
    """hinge penalty lam * mean(relu(y(z) - y(z + step))) on logit outputs 3, 4 for each MONO feature: the event logits
    may not fall when hr_reserve or the Kalman anchor rises (a negative weight on the estimate was rejected as unsafe)."""
    if len(z) > nsub: z = z[rng.integers(0, len(z), nsub)] if rng is not None else z[:nsub]
    y0, c0 = nn.forward(P, z); G = None; pen = 0.0
    for j, h in MONO:
        z1 = z.copy(); z1[:, j] += F(h / N["xs"][j])
        y1, c1 = nn.forward(P, z1)
        d = y0[:, 3:5] - y1[:, 3:5]; act = (d > 0).astype(F); pen += float((d * act).mean())
        g0 = np.zeros_like(y0); g1 = np.zeros_like(y1)
        g0[:, 3:5] = MONO_LAMBDA * act / (len(z) * 2); g1[:, 3:5] = -MONO_LAMBDA * act / (len(z) * 2)
        ga = nn.backward(P, c0, g0); gb = nn.backward(P, c1, g1)
        gg = [a + b for a, b in zip(ga, gb)]; G = gg if G is None else [a + b for a, b in zip(G, gg)]
    return G, pen


def crc_of(P, crc=0):
    for a in P: crc = zlib.crc32(np.ascontiguousarray(a, "<f4").tobytes(), crc)
    return crc


def htt_rows(N):
    lanes = data_htt.load(noise=True)
    feats = data_htt.features(lanes)
    X = np.concatenate([f[0] for f in feats]); Y = np.concatenate([data_htt.targets(l) for l in lanes])
    subj = np.concatenate([[l["subject"]] * len(l["hr"]) for l in lanes]); sess = np.concatenate([[l["session"]] * len(l["hr"]) for l in lanes])
    aux = {k: np.concatenate([f[1][k] for f in feats]) for k in ("v12_est", "v12_f20", "v12_z", "v12_sd")}
    assert_no_sealed(office_ids=[])  # HTT is not part of the hg2 seal; office subjects never loaded here
    return dict(Z=nn.normalise_x(X, N["xm"], N["xs"]), X=X, T=nn.norm_targets(Y, N["ym"], N["ys"]), Y=Y, subj=subj, sess=sess, aux=aux)


def evaluate(P, Z, T, w=None):
    y = nn.predict(P, Z)
    l, _, parts = nn.loss_grad(y, T, np.ones(len(Z), F) if w is None else w, DELTA_N)
    return l, parts, y


MIXES = {  # M6.1: member k over-weights (x MIX_W) the persons of one body hypothesis; every member still sees every person/scenario
    1: ("kappa_core", "low"),    # HR rises little per degC of core (blunted heart): HR under-reads strain
    2: ("kappa_core", "high"),   # HR rises a lot per degC
    3: ("a_axial", "high"),      # large wrist axial drop: insulated T1 sits far below core
    4: ("circ_mesor", "high"),   # high personal core baseline (the per-person offset the sealed v1 errors were made of)
    5: ("frail_or_bb", "high"),  # frail or beta-blocked (blunted HR + weak thermoregulation); also the flux-off robust member
}
MIX_W = 2


def mix_weights(k, ids):
    P = persons_table().loc[list(ids)]
    if MIXES[k][0] == "frail_or_bb":
        hit = (P.frailty >= P.frailty.median()) | (P.med_bb_nonsel == 1) | (P.med_bb_sel == 1)
    else:
        v = P[MIXES[k][0]]; hit = v <= v.median() if MIXES[k][1] == "low" else v > v.median()
    return {int(i): (MIX_W if h else 1) for i, h in zip(P.index, hit)}


OOF = None
AUX_W = 0.1


def load_oof(N):
    global OOF
    f = os.path.join(CACHE, "oof_resid.npz")
    if not os.path.exists(f): OOF = None; return
    o = np.load(f); X, Y, M = load_view("v0"); check_index(M)
    OOF = (nn.normalise_x(X[o["rows"]], N["xm"], N["xs"]), o["R"].astype(F))


def pretrain(k, N, log, epochs=30, bs=4096, lr=1e-3, patience=6):
    view = "v%d" % (k - 1)
    X, Y, M = load_view(view); ids = check_index(M)
    Xv, Yv, Mv = load_view("es"); vids = check_index(Mv)          # early stopping on the 30 ES persons (M5.2 split)
    if k == 5: Xv = flux_off(Xv)                                       # robust member is validated as it will run
    assert not set(ids) & set(vids), "validation persons in training"
    rng = np.random.default_rng(SEED + 100 * k)
    mult = mix_weights(k, ids)                                         # M6.1 body-hypothesis person mix
    pid = M[:, 0].astype(int)
    rows = np.concatenate([np.repeat(np.where(pid == i)[0], c) for i, c in mult.items()])
    Z = nn.normalise_x(X, N["xm"], N["xs"]); T = nn.norm_targets(Y, N["ym"], N["ys"])
    Zv = nn.normalise_x(Xv, N["xm"], N["xs"]); Tv = nn.norm_targets(Yv, N["ym"], N["ys"])
    P = nn.init(rng); opt = nn.Adam(P, lr=lr)
    best = (1e9, None, -1); ep_log = []
    for ep in range(epochs):
        t0 = time.time(); perm = rng.permutation(rows); tl = 0; nb = 0
        for i in range(0, len(perm) - bs + 1, bs):
            b = perm[i:i + bs]
            y, cache = nn.forward(P, augment(Z[b], rng))
            l, gy, _ = nn.loss_grad(y, T[b], np.ones(len(b), F), DELTA_N)
            nn_g = nn.backward(P, cache, gy); mg, _ = mono_grads(P, Z[b], N, rng=rng)
            G = [a + c for a, c in zip(nn_g, mg)]
            if OOF is not None:                                   # M6.2 auxiliary: shape the trunk for out-of-person error
                j = rng.integers(0, len(OOF[0]), 1024); y2, c2 = nn.forward(P, OOF[0][j]); r2 = OOF[1][j] ** 2
                v = y2[:, 6:9]; s2 = v * v + nn.EPS_V; ok = np.isfinite(r2)
                g2 = np.zeros_like(y2); g2[:, 6:9] = np.where(ok, AUX_W * 0.5 * (1 / s2 - np.nan_to_num(r2) / (s2 * s2)) * 2 * v, 0) / len(j)
                G = [a + c for a, c in zip(G, nn.backward(P, c2, g2))]
            opt.step(P, G); tl += l; nb += 1
        vl, parts, yv = evaluate(P, Zv, Tv)
        mae = [float(np.nanmean(np.abs((yv[:, j] * N["ys"][j] + N["ym"][j]) - Yv[:, j]))) for j in range(3)]
        ep_log.append(dict(epoch=ep + 1, train_loss=tl / max(nb, 1), val_loss=vl, val_parts=[float(x) for x in parts],
                           val_mae_now_20_30=mae, sec=time.time() - t0))
        print("[m%d pre] ep %2d train %.4f val %.4f MAE %.3f/%.3f/%.3f parts %s (%.0fs)" % (k, ep + 1, tl / max(nb, 1), vl, *mae,
              " ".join("%.3f" % x for x in parts), time.time() - t0), flush=True)
        if vl < best[0]: best = (vl, [p.copy() for p in P], ep + 1)
        elif ep + 1 - best[2] >= patience: break
    log["pretrain"] = dict(view=view, n_rows=int(len(rows)), n_persons_unique=len(mult), mix=MIXES[k], mix_weight=MIX_W,
                           n_persons_overweighted=int(sum(1 for v in mult.values() if v > 1)), best_epoch=best[2], epochs=ep_log,
                           label=LABEL_SIM)
    return best[1]


def finetune(P0, k, H, N, sim, rows_htt, epochs=10, bs_real=128, bs_sim=43, lr=1e-4, log=None, seed_off=0):
    """step 3. rows_htt: indices into H (the fine-tuning subjects). sim: (Z, T) of the member's SIM view"""
    rng = np.random.default_rng(SEED + 1000 * k + seed_off)
    P = [p.copy() for p in P0]; opt = nn.Adam(P, lr=lr)
    Zs, Ts = sim; ep_log = []
    for ep in range(epochs):
        perm = rng.permutation(rows_htt); tl = 0; nb = 0
        for i in range(0, len(perm), bs_real):
            b = perm[i:i + bs_real]; s = rng.integers(0, len(Zs), bs_sim)
            z = np.concatenate([H["Z"][b], Zs[s]]); t = np.concatenate([H["T"][b], Ts[s]])
            w = np.concatenate([np.full(len(b), 2.0, F), np.ones(len(s), F)])   # real rows x2
            y, cache = nn.forward(P, z); l, gy, _ = nn.loss_grad(y, t, w, DELTA_N)
            mg, _ = mono_grads(P, z, N, rng=rng)
            opt.step(P, [a + c for a, c in zip(nn.backward(P, cache, gy), mg)]); tl += l; nb += 1
        if log is not None:
            y = nn.predict(P, H["Z"][rows_htt])
            mae = float(np.nanmean(np.abs(y[:, 0] * N["ys"][0] + N["ym"][0] - H["Y"][rows_htt, 0])))
            ep_log.append(dict(epoch=ep + 1, loss=tl / max(nb, 1), htt_train_mae_now=mae))
    if log is not None: log["finetune"] = dict(epochs=ep_log, n_htt_rows=int(len(rows_htt)), label=LABEL_HTT, sim_share=0.25, real_weight=2)
    return P


def load_member(k):
    d = np.load(os.path.join(MEM, "member_%d.npz" % k))
    return [d["pre_%d" % i] for i in range(6)], [d["ft_%d" % i] for i in range(6)]


def update_log(k, entry):
    L = json.load(open(LOG)) if os.path.exists(LOG) else {}
    L.setdefault("members", {})[str(k)] = entry
    L["provenance"] = data_provenance(); L["label"] = "PROVISIONAL (sim v1, M2) - " + LABEL_SIM + " + HTT fine-tune (" + LABEL_HTT + ")"
    if all(os.path.exists(os.path.join(MEM, "member_%d.npz" % j)) for j in range(1, 6)):
        crc = 0
        for j in range(1, 6): crc = crc_of(load_member(j)[1], crc)
        L["ensemble_crc32"] = "0x%08X" % crc
        L["ensemble_crc_note"] = "zlib CRC-32 over float32 LE bytes, members 1..5 in order, W1 b1 W2 b2 W3 b3 (== HG2_NN_CRC32)"
    json.dump(L, open(LOG, "w"), indent=1)


def main_member(k):
    global DELTA_N
    N = norm(); DELTA_N = DELTA / np.array([N["ys"][0], N["ys"][1], N["ys"][2], 1, 1, 1])
    t0 = time.time(); log = dict(seed=k, robust_flux_off=(k == 5), provenance=data_provenance())
    load_oof(N); log["sd_aux_loss"] = dict(on=OOF is not None, weight=AUX_W)
    P0 = pretrain(k, N, log)
    H = htt_rows(N)
    X, Y, M = load_view("v%d" % (k - 1)); check_index(M)
    sim = (nn.normalise_x(X, N["xm"], N["xs"]), nn.norm_targets(Y, N["ym"], N["ys"]))
    P = finetune(P0, k, H, N, sim, np.arange(len(H["Z"])), log=log)
    os.makedirs(MEM, exist_ok=True)
    np.savez(os.path.join(MEM, "member_%d.npz" % k), **{"pre_%d" % i: p for i, p in enumerate(P0)}, **{"ft_%d" % i: p for i, p in enumerate(P)})
    log["crc32_member"] = "0x%08X" % crc_of(P); log["minutes"] = (time.time() - t0) / 60
    update_log(k, log)
    print("member %d done in %.1f min, CRC %s" % (k, log["minutes"], log["crc32_member"]))


def es_split(M):
    """30 ES persons: first 20 fit the sd heads (stage 2), last 10 = the ONLY monitor used for iterating on M6 targets
    (the 100 calibration persons are never used for any choice)"""
    ids = sorted(np.unique(M[:, 0]).astype(int)); return ids[:20], ids[20:]


def es_rows(N, n=60000):
    X, Y, M = load_view("es"); check_index(M)
    fit_ids, _ = es_split(M); cand = np.where(np.isin(M[:, 0].astype(int), fit_ids))[0]
    r = np.random.default_rng(SEED + 9).choice(cand, min(n, len(cand)), replace=False)
    return nn.normalise_x(X[r], N["xm"], N["xs"]), nn.norm_targets(Y[r], N["ym"], N["ys"])


def fit_vars(Ps, Zes, Tes, seed=0):
    """M6.2 stage 2 for a set of 5 members (in place): between-member variance of the means on ES rows, then each
    member's sd heads by Gaussian NLL on the remainder"""
    mus = np.stack([nn.predict(P, Zes)[:, :3] for P in Ps]); b2 = mus.var(0)
    nn.TAU = json.load(open(LOG))["members"]["1"]["sd_head_tau"]["tau"]          # same tau as the final ensemble
    for j, P in enumerate(Ps): nn.fit_var(P, Zes, Tes, b2, steps=3000, lr=1e-2, rng=np.random.default_rng(SEED + 31 * j + seed))
    return Ps


def main_oof(nfold=5, epochs=12):
    """Cross-fitted residuals for the sd heads: 5 person folds of the 270 gradient persons; a mean model trained on 4/5
    (member-1 recipe, uniform mix) predicts the held-out 1/5. Gives out-of-person residuals for ~all training rows, so the
    sd heads learn the error a NEW person will have (fitting them on in-sample residuals made them anti-informative)."""
    global DELTA_N
    N = norm(); DELTA_N = DELTA / np.array([N["ys"][0], N["ys"][1], N["ys"][2], 1, 1, 1])
    X, Y, M = load_view("v0"); ids = check_index(M); pid = M[:, 0].astype(int)
    Z = nn.normalise_x(X, N["xm"], N["xs"]); T = nn.norm_targets(Y, N["ym"], N["ys"])
    f = dict(zip(ids, np.random.default_rng(SEED + 404).permutation(len(ids)) % nfold)); fold = np.array([f[i] for i in pid])
    R = np.full((len(Z), 3), np.nan, F)
    for k in range(nfold):
        P = oof_model(Z[fold != k], T[fold != k], N, epochs, k)
        R[fold == k] = nn.predict(P, Z[fold == k])[:, :3] - T[fold == k, :3]
        print("oof fold %d" % k, flush=True)
    r = np.random.default_rng(SEED + 405).choice(len(Z), 250000, replace=False)
    np.savez(os.path.join(CACHE, "oof_resid.npz"), rows=r, R=R[r])


def oof_model(Z, T, N, epochs, k, bs=4096, lr=1e-3):
    rng = np.random.default_rng(SEED + 500 + k); P = nn.init(rng); opt = nn.Adam(P, lr=lr)
    for ep in range(epochs):
        perm = rng.permutation(len(Z))
        for i in range(0, len(perm) - bs + 1, bs):
            b = perm[i:i + bs]; y, cache = nn.forward(P, augment(Z[b], rng)); l, gy, _ = nn.loss_grad(y, T[b], np.ones(len(b), F), DELTA_N)
            opt.step(P, nn.backward(P, cache, gy))
    return P


TAU_LOG = {}


def main_var():
    global DELTA_N
    N = norm()
    Ps = [load_member(k) for k in range(1, 6)]
    # trunk already shaped by the cross-fitted auxiliary loss; the linear sd heads are calibrated on the residuals of THIS
    # ensemble on the 20 ES-fit persons (out-of-person for every member), so the variance scale matches new wearers
    Zr, Tr = es_rows(N, 100000)
    mus = np.stack([nn.predict(P[1], Zr)[:, :3] for P in Ps]); b2 = mus.var(0); mu = mus.mean(0); e = np.abs(mu - Tr[:, :3])
    # tau: the pinball level whose TOTAL sd (with the between-member part) covers 90 % on the ES-fit persons themselves
    # (rows where member disagreement alone exceeds the needed width cannot shrink, so tau = 0.90 over-covers)
    best = None
    for tau in (0.90, 0.87, 0.84, 0.81, 0.78, 0.75, 0.72, 0.69, 0.66):
        nn.TAU = tau; Q = [[p.copy() for p in P[1]] for P in Ps]
        for j, P in enumerate(Q): nn.fit_var(P, Zr, Tr, b2, steps=3000, lr=1e-2, rng=np.random.default_rng(SEED + 31 * j))
        raw = np.stack([nn.predict(P, Zr) for P in Q]); sd = np.sqrt((raw[:, :, 6:9] ** 2 + nn.EPS_V).mean(0) + b2)
        cov = float(np.nanmean(e[:, 0] <= 1.645 * sd[:, 0]))
        print("tau %.2f ES-fit coverage %.3f" % (tau, cov))
        if best is None or abs(cov - 0.90) < abs(best[1] - 0.90): best = (tau, cov, Q)
        if cov <= 0.90: break
    for P, Qm in zip(Ps, best[2]): P[1][4][:] = Qm[4]; P[1][5][:] = Qm[5]
    TAU_LOG.update(tau=best[0], es_fit_coverage=best[1])
    for k, (P0, P) in enumerate(Ps, 1):
        np.savez(os.path.join(MEM, "member_%d.npz" % k), **{"pre_%d" % i: p for i, p in enumerate(P0)}, **{"ft_%d" % i: p for i, p in enumerate(P)})
        L = json.load(open(LOG)); L["members"][str(k)]["crc32_member"] = "0x%08X" % crc_of(P)
        L["members"][str(k)]["sd_head_tau"] = dict(TAU_LOG)
        L["members"][str(k)]["sd_heads"] = "trunk: auxiliary NLL on cross-fitted out-of-person residuals (270 persons); heads: Gaussian NLL on the ensemble's own residuals on the 20 ES-fit persons (M6.2)"; json.dump(L, open(LOG, "w"), indent=1)
        update_log(k, L["members"][str(k)])
    print("sd heads fitted; ensemble CRC", json.load(open(LOG)).get("ensemble_crc32"))


def main_loso():
    """65 folds x 5 members: fine-tune from each member's pretrained weights without the left-out subject"""
    global DELTA_N
    N = norm(); DELTA_N = DELTA / np.array([N["ys"][0], N["ys"][1], N["ys"][2], 1, 1, 1])
    H = htt_rows(N); subs = sorted(set(H["subj"]))
    out = np.full((5, len(H["Z"]), nn.N_OUT), np.nan, F)
    t0 = time.time(); Zes, Tes = es_rows(N, 30000)
    P0s = [load_member(k)[0] for k in range(1, 6)]; sims = []
    for k in range(1, 6):
        X, Y, M = load_view("v%d" % (k - 1)); check_index(M)
        r = np.random.default_rng(SEED + k).choice(len(X), 200000, replace=False)
        sims.append((nn.normalise_x(X[r], N["xm"], N["xs"]), nn.norm_targets(Y[r], N["ym"], N["ys"]))); del X, Y, M
    for fi, s in enumerate(subs):                                  # fold-outer: the 5 members + sd heads of one fold
        tr = np.where(H["subj"] != s)[0]; te = np.where(H["subj"] == s)[0]
        assert not set(H["subj"][tr]) & {s}
        Ps = [finetune(P0s[k - 1], k, H, N, sims[k - 1], tr, seed_off=fi + 1) for k in range(1, 6)]
        fit_vars(Ps, Zes, Tes, seed=fi + 1)
        for k in range(5): out[k, te] = nn.predict(Ps[k], H["Z"][te])
        if fi % 10 == 0: print("loso fold %d/%d (%.1f min)" % (fi + 1, len(subs), (time.time() - t0) / 60), flush=True)
    np.savez(os.path.join(CACHE, "htt_oof.npz"), raw=out, Y=H["Y"], subj=H["subj"], sess=H["sess"], X=H["X"],
             **{"aux_" + k: v for k, v in H["aux"].items()}, ym=N["ym"], ys=N["ys"])
    # also the pretrained-only (no HTT) ensemble on HTT, for the sim-to-real statement
    pre = np.stack([nn.predict(load_member(k)[0], H["Z"]) for k in range(1, 6)])
    np.save(os.path.join(CACHE, "htt_pretrain_only.npy"), pre)
    L = json.load(open(LOG)) if os.path.exists(LOG) else {}
    L["loso"] = dict(folds=len(subs), members=5, minutes=(time.time() - t0) / 60, provenance=data_provenance(), label=LABEL_HTT)
    json.dump(L, open(LOG, "w"), indent=1)


if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("--seed", type=int); a.add_argument("--loso", action="store_true")
    a.add_argument("--var", action="store_true"); a.add_argument("--oof", action="store_true")
    o = a.parse_args()
    assert sealed()["sim"]  # seal must exist
    if o.loso: main_loso()
    elif o.var: main_var()
    elif o.oof: main_oof()
    else:
        assert o.seed in (1, 2, 3, 4, 5); main_member(o.seed)
