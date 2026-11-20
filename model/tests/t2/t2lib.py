"""Tester's own hg2 reference (independent of model/hg2): weights parsed from model/export/hg2_weights.c, float64 forward,
M6 sd rule as documented in hg2_weights.h: sd = sqrt(mean_k(v_k^2 + EPS_V) + between-member var of the means) * Y_STD."""
import re
import numpy as np
ROOT = "/home/claude/hg_ai"; EXP = ROOT + "/model/export"
F = np.float32
_SH = [(24, 32), (24,), (16, 24), (16,), (9, 16), (9,)]; _N = ["W1", "b1", "W2", "b2", "W3", "b3"]


def load_weights():
    src = open(EXP + "/hg2_weights.c").read(); arr = {}
    for m in re.finditer(r"const float (\w+?)((?:\[\w+\])+) = (\{.*?\});", src, re.S):
        arr[m.group(1)] = np.array([F(float(v)) for v in re.findall(r"[-+]?\d\.\d+e[-+]\d+", m.group(3))], F)
    Ms = [[arr["%s_%d" % (n, k)].reshape(sh).astype(np.float64) for n, sh in zip(_N, _SH)] for k in range(5)]
    return dict(M=Ms, xm=arr["HG2_X_MEAN"], xs=arr["HG2_X_STD"], ym=arr["HG2_Y_MEAN"].astype(np.float64), ys=arr["HG2_Y_STD"].astype(np.float64))


def zscore(W, X):
    X = np.asarray(X, F)
    return np.where(np.isnan(X), F(0), ((X - W["xm"]).astype(F) / W["xs"]).astype(F)).astype(np.float64)


def members(W, Z):
    out = []
    for W1, b1, W2, b2, W3, b3 in W["M"]:
        h1 = np.maximum(Z @ W1.T + b1, 0); h2 = np.maximum(h1 @ W2.T + b2, 0); out.append(h2 @ W3.T + b3)
    return np.stack(out)


def ens(W, X, bs=200000):
    """X raw [n,32] -> dict core_now/20/30, sd_now/20/30 (M6 total), btw_now, lp38, lp385, strain"""
    parts = []
    for i in range(0, len(X), bs):
        Y = members(W, zscore(W, X[i:i + bs])); mu = Y.mean(0)
        core = mu[:, :3] * W["ys"] + W["ym"]
        sd = np.sqrt((Y[:, :, 6:9] ** 2 + 1e-3).mean(0) + Y[:, :, :3].var(0)) * W["ys"]
        btw = Y[:, :, :3].std(0) * W["ys"]
        parts.append(np.column_stack([core, sd, btw, mu[:, 3], mu[:, 4], np.clip(mu[:, 5], 0, 10)]))
    A = np.concatenate(parts)
    k = ["core_now", "core_20", "core_30", "sd_now", "sd_20", "sd_30", "btw_now", "btw_20", "btw_30", "lp38", "lp385", "strain"]
    return {n: A[:, j] for j, n in enumerate(k)}


def flux_off(X):
    X = X.copy(); X[:, 3] = 0; X[:, 4] = 0; X[:, 5] = 0; X[:, 25] = X[:, 0]; return X
