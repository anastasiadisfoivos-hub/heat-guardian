"""T2-04c fair HTT comparison: hg2 LOSO vs v1.2 on the 13 people v1.2 never saw (v1 sealed split, spent; used ONLY as a split
membership, never to pick anything) and on the 52 it was fit on. young adults 18-33, chamber walk, DEV.
Run: python3 tests/t2/t04c_v12_fair.py [htt_oof.npz]"""
import json, sys
import numpy as np
P = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/hg_ai/model/cache/v4aug/htt_oof.npz"
d = np.load(P, allow_pickle=True); raw = d["raw"].astype(float); Y = d["Y"].astype(float); subj = d["subj"]
core = raw.mean(0)[:, 0] * float(d["ys"][0]) + float(d["ym"][0])
v1s = set(json.load(open("/home/claude/hgmodel/sealed_split.json"))["sealed_subjects"])
ok = np.isfinite(Y[:, 0]); R = {}
for nm, sel in (("13_unseen_by_v12", np.isin(subj, list(v1s))), ("52_v12_fit", ~np.isin(subj, list(v1s)))):
    m = ok & sel; us = np.unique(subj[m]); eh = np.abs(core - Y[:, 0]); ev = np.abs(d["aux_v12_est"] - Y[:, 0])
    rng = np.random.default_rng(3); b = []
    for _ in range(2000):
        r = np.concatenate([np.where(m & (subj == u))[0] for u in rng.choice(us, len(us))]); b.append(eh[r].mean() - ev[r].mean())
    R[nm] = dict(n_subj=len(us), mae_hg2=float(eh[m].mean()), mae_v12=float(ev[m].mean()), diff_95=np.percentile(b, [2.5, 97.5]).tolist(),
                 within05_hg2=float((eh[m] <= .5).mean() * 100), within05_v12=float((ev[m] <= .5).mean() * 100))
print(json.dumps(R, indent=1)); json.dump(R, open("/home/claude/hg_ai/tests/t2/out/t04c_v12_fair.json", "w"), indent=1)
