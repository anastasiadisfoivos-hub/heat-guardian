#!/usr/bin/env python3
"""R6 E6b: guard against 'a long walk alone fires Danger' - SIMULATION DEV, same CV and operating rule as final_danger.py.
 G0 = Momentum/Marble as in final_danger;  G1 = wind term clipped: A30, A120 enter only as wind = clip(A30 - A120, 0, 0.025);
 G2 = G1 + hard gate: the score counts only while E60 >= 37.8 C and D > 0 ('wind can only push a marble that is already heavy').
Also reports how often each variant fires on COOL days: Danger episodes whose room air stayed < 28 C in the previous 60 min."""
import json, numpy as np
from common import *; from rules import *; import feats
from eval3 import ew
from final_danger import cv_scores, pick, summ, per_person
P = IDX["persons"]; folds = [[p for p in P if p % 2 == 0], [p for p in P if p % 2 == 1]]; out = {}
for hk in ("raw", "sc"):
    B = {p: feats.build(p, hk) for p in P}; data = {p: B[p][0] for p in P}
    def F(p, v):
        d, X, ok, y = B[p]; f20 = X["f20"]; a = np.minimum(np.nan_to_num(d["a_std_g"]), 0.30); E60 = ew(f20, 60); A30, A120 = ew(a, 30), ew(a, 120)
        if v == "G0": return np.column_stack([E60 - 37.5, ew(f20, 10) - E60, A30, A120, X["dose"]]), None
        return np.column_stack([E60 - 37.5, ew(f20, 10) - E60, np.clip(A30 - A120, 0, 0.025), X["dose"]]), ((E60 >= 37.8) & (X["dose"] > 0) if v == "G2" else None)
    for v in ("G0", "G1", "G2"):
        FF = {}; G = {}
        for p in P: FF[p], G[p] = F(p, v)
        sc, W = cv_scores(P, B, FF, folds)
        if v == "G2":
            for p in P: sc[p] = np.where(G[p], sc[p], -1e9)
        th, r, rows = pick(sc, B, data, P, 6.0); cool = 0; tot = 0
        for p in P:
            fire = run_min(sc[p] >= th, 5); ta = B[p][1]["tair"]
            for o in episodes(fire): tot += 1; cool += np.nanmax(ta[max(0, o - 60):o + 1]) < 28.0
        print("%s %s: all %.2f  S2 %d/%d = %.2f  lead %s  strict FA %.1f/mo  empty %.1f/mo | episodes in rooms < 28 C: %d of %d | weights %s" % (
            hk, v, r["sens"], r["hit_S2"], r["n_S2"], r["sens_S2"], r["lead"], r["fa_month"], r["empty_month"], cool, tot, np.round(np.mean(W, 0), 3).tolist()), flush=True)
        out["%s|%s" % (hk, v)] = dict(r, cut=th, weights=np.mean(W, 0).tolist(), cool_room_episodes=int(cool), episodes=int(tot))
json.dump(out, open(HERE + "/out_guard.json", "w"), indent=1, default=float)
