"""Feature-builder proofs (SIMULATION data, DEV persons only):
 1. lane-by-lane bitwise equality of FeatureState (vectorised) with B5's scalar reference HG2.step (guardian/py);
 2. minute-by-minute single-lane run == lock-step multi-lane batch (statefulness, no cross-lane leakage);
 3. causality: perturbing minute t+1.. never changes features at <= t.
Run: cd /home/claude/hg_ai && python3 -m model.hg2.tests_features"""
import json, sys
import numpy as np
from .common import RUNS, dev_person_ids, assert_no_sealed, MODEL
from .simio import iter_persons, persons_table, profile_of
from . import features as FT

F = np.float32
REF = FT.REF


def twin_for(p, nb=None):
    tw = dict(rest_hr=float(p["hr_rest"]) + 1.5, k_person=0.12, core_offset=0.0, c_bodyheat=0.15,
              t1_night_base=[np.nan] * 24 if nb is None else nb)
    return tw


def main(n_persons=3, minutes=1440 * 2):
    ids = dev_person_ids()[:n_persons]
    assert_no_sealed(ids)
    P = persons_table()
    _, dfs = next(iter_persons(ids, batch=n_persons))
    nb = [float(33.0 + 0.1 * h) if h % 3 else np.nan for h in range(24)]
    res = {}
    # --- (1) vs B5 scalar
    class W:  # identity "weights" object so B5's HG2 runs its feature path only
        members = []; xm = np.zeros(32, F); xs = np.ones(32, F); ym = np.zeros(3, F); ys = np.ones(3, F)
        stub = True; cut38 = F(1e9); cut385 = F(1e9); crc = 0; nout = 6
    REF.ensemble = lambda z, Wt: (np.zeros(6, F), np.zeros(6, F), [F(0)] * 3)
    maxdiff = 0; nmis = 0; nrows = 0
    lanes = []
    for pid, df in zip(ids, dfs):
        df = df.iloc[:minutes]
        p = P.loc[pid]; prof = profile_of(p); tw = twin_for(p, nb)
        cols = FT.sim_cols(df)
        mine = FT.build_features(df, tw, prof)
        h = REF.HG2(prof, tw, W)
        ref = np.empty_like(mine)
        refv12 = []
        for t in range(len(df)):
            i = {k: cols[c][t, 0] for k, c in (("t1", "t1"), ("t2", "t2"), ("tair", "tair"), ("rh", "rh"), ("hr", "hr"), ("pi", "pi"), ("astd", "astd"))}
            i.update(hrq=int(cols["hrq"][t, 0]), worn=int(cols["worn"][t, 0]), mod=int(cols["mod"][t, 0]))
            o, aux = h.step(i); ref[t] = aux["x"]; refv12.append((aux["v12_est"], aux["v12_z"]))
        eq = (mine == ref) | (np.isnan(mine) & np.isnan(ref))
        nmis += int((~eq).sum()); nrows += len(df)
        d = np.nanmax(np.abs(mine.astype(np.float64) - ref.astype(np.float64)))
        maxdiff = max(maxdiff, float(d))
        if (~eq).any():
            r, c = np.argwhere(~eq)[0]; print("MISMATCH person", pid, "minute", r, FT.NAMES[c], mine[r, c], ref[r, c])
        lanes.append((pid, prof, tw, cols, mine))
    res["vs_B5_scalar"] = dict(persons=ids, minutes=nrows, mismatching_values=nmis, max_abs_diff=maxdiff)
    # --- (2) batch == single
    T = min(len(l[3]["t1"]) for l in lanes)
    cols = {k: np.concatenate([l[3][k][:T] for l in lanes], 1) for k in lanes[0][3]}
    prof = {k: np.array([l[1][k] for l in lanes]) for k in lanes[0][1]}
    tw = {k: np.array([l[2][k] for l in lanes]) for k in lanes[0][2]}
    X, aux, idx = FT.run_lanes(cols, prof, tw)
    nb_mis = 0
    for j, l in enumerate(lanes):
        a = X[idx[:, 1] == j]; b = l[4][:T]
        nb_mis += int((~((a == b) | (np.isnan(a) & np.isnan(b)))).sum())
    res["batch_vs_single"] = dict(mismatching_values=nb_mis)
    # --- (3) causality: scramble the future after minute t0
    t0 = 700; c2 = {k: v.copy() for k, v in cols.items()}
    rng = np.random.default_rng(1)
    for k in ("t1", "t2", "tair", "rh", "hr", "pi", "astd"): c2[k][t0 + 1:] = c2[k][t0 + 1:] + rng.normal(0, 3, c2[k][t0 + 1:].shape).astype(F)
    X2, _, idx2 = FT.run_lanes(c2, prof, tw)
    past = idx[:, 0] <= t0
    a, b = X[past], X2[idx2[:, 0] <= t0]
    res["causality"] = dict(t0=t0, changed_past_values=int((~((a == b) | (np.isnan(a) & np.isnan(b)))).sum()),
                            changed_future_values=int((X[~past] != X2[idx2[:, 0] > t0]).sum()))
    res["pass"] = res["vs_B5_scalar"]["mismatching_values"] == 0 and nb_mis == 0 and res["causality"]["changed_past_values"] == 0
    print(json.dumps(res, indent=1))
    json.dump(res, open(RUNS + "/results_features_tests.json", "w"), indent=1)
    return res


if __name__ == "__main__":
    r = main()
    sys.exit(0 if r["pass"] else 1)
