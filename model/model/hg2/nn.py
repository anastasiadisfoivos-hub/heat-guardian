"""From-scratch numpy MLP 32 -> 24 -> 16 -> 6 (ReLU), Adam, mixed loss (ARCH 4.2): Huber (delta 0.3 C) on the three
temperatures, BCE-with-logits on the two event outputs, Huber (delta 1) on strain. NaN targets are masked.
No torch: the network is 1,294 parameters; numpy float32 trains it in seconds per epoch on 2 CPUs.
Layout W[out, in] = the C layout (hg2_step.c dense(): w = W + o*n_in)."""
import numpy as np

F = np.float32
SHAPES = [(24, 32), (24,), (16, 24), (16,), (9, 16), (9,)]
N_OUT = 9          # 6 task outputs + 3 sd heads (M6.2) for core now/+20/+30
EPS_V = 1e-3       # aleatoric variance = v^2 + EPS_V (normalised units): no expf on the band (ARCH 4.5), sqrtf only
LOSS_W = np.array([1.0, 1.0, 1.0, 0.5, 0.5, 0.05, 0, 0, 0], F)


def init(rng):
    P = []
    for sh in SHAPES:
        if len(sh) == 2: P.append((rng.standard_normal(sh) * np.sqrt(2.0 / sh[1])).astype(F))
        else: P.append(np.zeros(sh, F))
    return P


def forward(P, z):
    W1, b1, W2, b2, W3, b3 = P
    a1 = z @ W1.T + b1; h1 = np.maximum(a1, 0)
    a2 = h1 @ W2.T + b2; h2 = np.maximum(a2, 0)
    y = h2 @ W3.T + b3
    return y, (z, a1, h1, a2, h2)


def loss_grad(y, t, w, delta_n):
    """y,t: [B,6] (t normalised for 0..2, 0/1 for 3..4, raw for 5); w: [B] row weights. returns loss, dL/dy"""
    m = ~np.isnan(t); tt = np.where(m, t, 0)
    g = np.zeros_like(y); L = np.zeros(6)        # outputs 6..8 (sd heads) get no gradient here: fitted by fit_var
    for j in (0, 1, 2, 5):
        d = (y[:, j] - tt[:, j]); dl = delta_n[j]
        a = np.abs(d); l = np.where(a <= dl, 0.5 * d * d, dl * (a - 0.5 * dl))
        gg = np.where(a <= dl, d, dl * np.sign(d))
        L[j] = (l * w * m[:, j]).sum(); g[:, j] = gg * w * m[:, j]
    for j in (3, 4):
        s = 1 / (1 + np.exp(-np.clip(y[:, j], -30, 30)))
        l = np.logaddexp(0, y[:, j]) - tt[:, j] * y[:, j]
        L[j] = (l * w * m[:, j]).sum(); g[:, j] = (s - tt[:, j]) * w * m[:, j]
    wsum = max(w.sum(), 1e-9)
    return float((L * LOSS_W[:6]).sum() / wsum), (g * LOSS_W[None, :] / wsum).astype(F), L / wsum


def backward(P, cache, gy):
    W1, b1, W2, b2, W3, b3 = P; z, a1, h1, a2, h2 = cache
    gW3 = gy.T @ h2; gb3 = gy.sum(0)
    gh2 = gy @ W3; ga2 = gh2 * (a2 > 0)
    gW2 = ga2.T @ h1; gb2 = ga2.sum(0)
    gh1 = ga2 @ W2; ga1 = gh1 * (a1 > 0)
    gW1 = ga1.T @ z; gb1 = ga1.sum(0)
    return [gW1, gb1, gW2, gb2, gW3, gb3]


class Adam:
    def __init__(s, P, lr=1e-3, b1=0.9, b2=0.999, eps=1e-8, wd=1e-5):
        s.m = [np.zeros_like(p) for p in P]; s.v = [np.zeros_like(p) for p in P]; s.t = 0
        s.lr, s.b1, s.b2, s.eps, s.wd = lr, b1, b2, eps, wd

    def step(s, P, G):
        s.t += 1
        for i, (p, g) in enumerate(zip(P, G)):
            if p.ndim == 2: g = g + s.wd * p
            s.m[i] = s.b1 * s.m[i] + (1 - s.b1) * g; s.v[i] = s.b2 * s.v[i] + (1 - s.b2) * g * g
            mh = s.m[i] / (1 - s.b1 ** s.t); vh = s.v[i] / (1 - s.b2 ** s.t)
            p -= (s.lr * mh / (np.sqrt(vh) + s.eps)).astype(F)


TAU = 0.90        # pinball level of the sd head (chosen on ES-fit persons, train.main_var)
LIK = "quantile"  # likelihood of the stage-2 sd heads; sd is still the standard deviation (exported formula unchanged)


def fit_var(P, Z, T, b2, steps=300, bs=4096, lr=3e-3, rng=None, resid=None):
    """M6.2 stage 2: Gaussian NLL for the sd heads only (rows 6..8 of the last layer), hidden layers + means frozen.
    sigma^2 = v^2 + EPS_V + b2, b2 = between-member variance of the means on the same rows (fixed), so the head learns
    the residual variance the ensemble disagreement does not explain. Fitted on EARLY-STOPPING persons (out-of-sample for
    the means, never calibration persons)."""
    rng = rng or np.random.default_rng(0)
    W3, b3 = P[4], P[5]
    _, cache = forward(P, Z[:1]); 
    h2 = np.concatenate([forward(P, Z[i:i + 65536])[1][4] for i in range(0, len(Z), 65536)])
    mu = h2 @ W3[:3].T + b3[:3]
    W = W3[6:9].copy(); b = b3[6:9].copy()
    m = [np.zeros_like(W), np.zeros_like(b)]; v_ = [np.zeros_like(W), np.zeros_like(b)]; t = 0
    for _ in range(steps):
        i = rng.integers(0, len(Z), bs); h = h2[i]
        r2 = (mu[i] - T[i, :3]) ** 2 if resid is None else resid[i] ** 2      # resid: cross-fitted OOF residuals (M6.2)
        ok = np.isfinite(r2)
        v = h @ W.T + b; s2 = v * v + EPS_V + b2[i]
        if LIK == "quantile":  # pinball loss: 1.645*s is the conditional 90 % quantile of |e| (heavy-tailed errors)
            sg = np.sqrt(s2); ae = np.sqrt(np.nan_to_num(r2)); q = 1.645 * sg
            g_s2 = np.where(ok, ((ae < q).astype(F) - TAU) * 1.645 / (2 * sg), 0) / bs
        elif LIK == "laplace":   # Laplace with variance s2 (scale s/sqrt2): NLL = log s + sqrt2 |e| / s  (errors are heavy-tailed)
            sg = np.sqrt(s2); ae = np.sqrt(np.nan_to_num(r2))
            g_s2 = np.where(ok, (1 / sg - np.sqrt(2) * ae / s2) / (2 * sg), 0) / bs
        else:
            g_s2 = np.where(ok, 0.5 * (1 / s2 - np.nan_to_num(r2) / (s2 * s2)), 0) / bs
        gv = g_s2 * 2 * v
        gW = gv.T @ h; gb = gv.sum(0); t += 1
        for k, (p_, g_) in enumerate(((W, gW), (b, gb))):
            m[k] = 0.9 * m[k] + 0.1 * g_; v_[k] = 0.999 * v_[k] + 0.001 * g_ * g_
            p_ -= (lr * (m[k] / (1 - 0.9 ** t)) / (np.sqrt(v_[k] / (1 - 0.999 ** t)) + 1e-8)).astype(F)
    W3[6:9] = W; b3[6:9] = b
    return P


def normalise_x(X, xm, xs):
    z = (X - xm) / xs
    return np.where(np.isfinite(z), z, F(0)).astype(F)     # [B2-fix] NaN and +-inf -> z = 0


def norm_targets(Y, ym, ys):
    T = Y.astype(F).copy()
    T[:, :3] = (T[:, :3] - ym) / ys
    return T


def predict(P, Z, bs=65536):
    return np.concatenate([forward(P, Z[i:i + bs])[0] for i in range(0, len(Z), bs)]) if len(Z) else np.zeros((0, N_OUT), F)
