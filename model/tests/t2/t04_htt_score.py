"""T2-04b independent HTT-DEV LOSO scorer (young adults 18-33, chamber walk, DEV). Own code for episodes / false alarms /
nested cut choice (REPORT 5 definitions), applied to an htt_oof.npz (builder's, or the tester's re-run).
Run: python3 tests/t2/t04_htt_score.py [path/to/htt_oof.npz]"""
import json, sys
import numpy as np
P = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/hg_ai/model/cache/v4aug/htt_oof.npz"
d = np.load(P, allow_pickle=True); raw = d["raw"].astype(np.float64); Y = d["Y"].astype(np.float64); subj = d["subj"]; sess = d["sess"]
ym, ys = d["ym"].astype(np.float64), d["ys"].astype(np.float64)
mu = raw.mean(0); core = mu[:, :3] * ys + ym
sd = np.sqrt((raw[:, :, 6:9] ** 2 + 1e-3).mean(0) + raw[:, :, :3].var(0)) * ys
lp38, lp385 = mu[:, 3], mu[:, 4]
v12_est, v12_f20, v12_z = d["aux_v12_est"], d["aux_v12_f20"], d["aux_v12_z"]
R = dict(file=P, label="young adults 18-33, chamber walk, DEV (LOSO)")
ok = np.isfinite(Y[:, 0])
for name, est in (("hg2", core[:, 0]), ("v12", v12_est)):
    e = np.abs(est - Y[:, 0])[ok]
    R["MAE_now_" + name] = float(e.mean()); R["within03_" + name] = float((e <= .3).mean() * 100); R["within05_" + name] = float((e <= .5).mean() * 100)
    # per-subject mean then mean (subject-weighted) as a robustness view
    R["MAE_now_subject_weighted_" + name] = float(np.mean([np.abs(est - Y[:, 0])[ok & (subj == s)].mean() for s in np.unique(subj[ok])]))
us = np.unique(subj); rng = np.random.default_rng(11); bs = []
e_h = np.abs(core[:, 0] - Y[:, 0]); e_v = np.abs(v12_est - Y[:, 0])
for _ in range(1000):
    r = np.concatenate([np.where(subj == u)[0] for u in rng.choice(us, len(us))]); m = ok[r]
    bs.append((e_h[r][m].mean(), e_h[r][m].mean() - e_v[r][m].mean()))
bs = np.array(bs); R["MAE_now_hg2_95"] = np.percentile(bs[:, 0], [2.5, 97.5]).tolist(); R["MAE_hg2_minus_v12_95"] = np.percentile(bs[:, 1], [2.5, 97.5]).tolist()
R["coverage_now_1.645sd"] = float((np.abs(core[:, 0] - Y[:, 0]) <= 1.645 * sd[:, 0])[ok].mean() * 100)
R["sd_now_median"] = float(np.median(sd[:, 0]))

# ---- sessions (order of appearance)
keys = np.array([f"{a}|{b}" for a, b in zip(subj, sess)]); _, first = np.unique(keys, return_index=True)
SES = []
for k in keys[np.sort(first)]:
    r = np.where(keys == k)[0]; SES.append((k, r, subj[r[0]]))
ssubj = np.array([s[2] for s in SES]); hours = np.array([len(s[1]) / 60 for s in SES])


def event_minute(c, thr):
    for i in range(1, len(c)):
        if c[i - 1] >= thr and c[i] >= thr: return i - 1
    return None


def episodes(mask, merge=10, k=2):
    out = []; i = 0; n = len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]: j += 1
            if j - i + 1 >= k:
                if out and i - out[-1][1] < merge: out[-1] = (out[-1][0], j)
                else: out.append((i, j))
            i = j + 1
        else: i += 1
    return out


def score(mask_full, thr):
    det = np.zeros(len(SES)); fa = np.zeros(len(SES)); lead = np.full(len(SES), np.nan); has = np.zeros(len(SES), bool)
    for si, (k, r, s) in enumerate(SES):
        c = np.nan_to_num(Y[r, 0], nan=-1.0); m = mask_full[r]; ev = event_minute(c, thr); has[si] = ev is not None
        eps = episodes(m)
        for a, b in eps:
            if ev is not None and a <= ev + 10 and b >= ev - 45 and det[si] == 0: det[si] = 1; lead[si] = ev - a
            if not (c[a:a + 61] >= thr).any(): fa[si] += 1
    return det, fa, lead, has


def summary(det, fa, lead, has):
    L = lead[has & (det > 0)]
    return dict(detected=int(det[has].sum()), events=int(has.sum()), sens=float(100 * det[has].sum() / has.sum()), fa_h=float(fa.sum() / hours.sum()),
                lead_median=float(np.median(L)) if len(L) else None)


CUTS = list(np.round(np.arange(-6, 6.01, 0.25), 2)) + [1e9]


def nested(base, score_v, thr, fa_max):
    tabs = [score(base | (np.nan_to_num(score_v, nan=-99) >= c), thr) for c in CUTS]
    D = np.zeros(len(SES)); FA = np.zeros(len(SES)); L = np.full(len(SES), np.nan); ch = []
    for s in np.unique(ssubj):
        tr = ssubj != s; best = None
        for ci, (det, fa, lead, has) in enumerate(tabs):
            f = fa[tr].sum() / hours[tr].sum(); se = det[tr & has].sum() / max((tr & has).sum(), 1)
            if f <= fa_max and (best is None or se > best[1] or (se == best[1] and CUTS[ci] > CUTS[best[0]])): best = (ci, se)
        ci = best[0] if best else len(CUTS) - 1; ch.append(CUTS[ci]); te = ~tr
        D[te], FA[te], L[te] = tabs[ci][0][te], tabs[ci][1][te], tabs[ci][2][te]
    return summary(D, FA, L, tabs[0][3]), dict(share_off=float(np.mean([c > 1e8 for c in ch])), median=float(np.median(ch)))


R["danger_v12_alone"] = summary(*score(v12_z >= -1.450010, 38.5))
R["danger_OR_nested"], R["danger_OR_cuts"] = nested(v12_z >= -1.450010, lp385, 38.5, 0.10)
R["danger_NN_alone_nested"], R["danger_NN_cuts"] = nested(np.zeros(len(Y), bool), lp385, 38.5, 0.10)
R["drink_v12_f20"] = summary(*score(v12_f20 >= 37.85, 38.0))
R["drink_hg2_core20"] = summary(*score(core[:, 1] >= 37.85, 38.0))
R["drink_hg2_core20_plus_1sd"] = summary(*score(core[:, 1] + np.minimum(sd[:, 1], .3) >= 37.85, 38.0))
R["drink_OR_nested_p38"], R["drink_cuts"] = nested(core[:, 1] >= 37.85, lp38, 38.0, 0.15)
R["cool_v12"] = summary(*score(v12_f20 >= 38.35, 38.5)); R["cool_hg2"] = summary(*score(core[:, 1] >= 38.35, 38.5))
# Drink at the SAME FA budget: lower the NN threshold until FA/h matches v1.2's, and vice versa (information)
def matched(sc, target):
    best = None
    for th in np.round(np.arange(37.6, 38.31, 0.01), 2):
        s = summary(*score(sc >= th, 38.0))
        if s["fa_h"] <= target and (best is None or s["sens"] > best[1]["sens"]): best = (float(th), s)
    return best
R["drink_hg2_core20_at_v12_FA_budget(pooled, info)"] = matched(core[:, 1], R["drink_v12_f20"]["fa_h"])
R["drink_v12_f20_at_0.15_budget(pooled, info)"] = matched(v12_f20, 0.15)
R["drink_hg2_core20_at_0.15_budget(pooled, info)"] = matched(core[:, 1], 0.15)
out = "/home/claude/hg_ai/tests/t2/out/t04_htt_score_%s.json" % ("rerun" if "tests/t2" in P else "builder")
json.dump(R, open(out, "w"), indent=1); print(json.dumps(R, indent=1))
