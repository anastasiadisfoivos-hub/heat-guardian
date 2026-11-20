"""ARCHITECTURE section 5 test 2 -- HTT dev, leave-first-session-in (B3 Body Twin).

Data: HTT (dataset 1), all 65 people = DEV for hg2 (ARCHITECTURE 3.1; the v1 sealed 13 are spent).
Labelled: REAL DATA, YOUNG ADULTS (18-33) WALKING IN A HOT CHAMBER, DEV (not a sealed number).

Estimator: the v1.2 band estimator (ECTemp Kalman + ridge residual on the 14 FEATS_HYB features), trained
leave-one-subject-out (LOSO) exactly as hgmodel/s02_personalisation.py. B2's hg2 is not exported yet.

For every person with two sessions, each session is scored once with the OTHER session as the learning
session ("session 1 learns, session 2 scored", both orders):
  D    defaults: rest_hr = 70 (Twin default) everywhere
  R1   Twin rest_hr after ONE nightly update: 70 + 0.3*(x - 70)
  Rinf Twin rest_hr converged (x), what the band reaches after ~7 nights (0.7^7 = 0.08 of the gap left)
  x = the person's resting HR measured at rest outside the sessions (HTT subject sheet, what the Twin's
      night floor + 5 bpm stands in for). The brief's "first 5 resting minutes of session 1" do not exist
      in HTT: every session starts walking (median HR over minutes 0-4 is ~100 bpm, see diagnostic F5 below).
  F5   DIAGNOSTIC: x = median HR of the learning session's minutes 0-4 (exercise-contaminated), converged
  C1   Rinf + one same-session oral reading at the start of the scored session (first clean pill value in
       minutes 0-5 + N(0, 0.2 degC)), applied through BodyTwin.commit_reading (beta 0.35, flux_valid = 0 so
       K is never touched); 3 noise draws (seeds 11, 12, 13)
Scored minutes: minute >= 30 of the scored session with a clean pill value (as s02).
Acceptance (B3 brief): R not worse than D by > 0.01 degC; C1 gain 0.01-0.05 degC (REPORT 5b: +0.030).
"""
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/claude/hgmodel")
sys.path.insert(0, "/home/claude/hg_ai/twin")
from common import load_htt, session_features, FEATS_HYB  # noqa: E402
from sklearn.linear_model import Ridge  # noqa: E402
from hg_twin import BodyTwin  # noqa: E402

OUT = "/home/claude/hg_ai/twin/results"
EVAL_FROM = 30
POP = 70.0
DRAWS = [11, 12, 13]
NOISE = 0.2


def build(sessions, subj, rest_of):
    rows = []
    for k, s in enumerate(sessions):
        prof = subj.loc[s["subject"]]
        rest = rest_of[k]
        f = session_features(s, prof, rest, ct0=None, kf_offset=rest - POP)
        f["sess_idx"] = k
        rows.append(f)
    return pd.concat(rows, ignore_index=True)


def loso_hybrid(df):
    pred = np.full(len(df), np.nan)
    ok = np.isfinite(df.core.values)
    X = df[FEATS_HYB].values; y = (df.core - df.kf).values
    for s in df.subject.unique():
        te = (df.subject == s).values
        tr = ~te & ok
        m = Ridge(alpha=1.0).fit(X[tr], y[tr])
        pred[te] = df.kf.values[te] + m.predict(X[te])
    return pred


def per_subject_mae(df, p, from_min=EVAL_FROM):
    ev = (df.minute >= from_min).values & np.isfinite(df.core.values)
    e = pd.DataFrame({"subject": df.subject.values[ev], "ae": np.abs(p[ev] - df.core.values[ev])})
    return e.groupby("subject").ae.mean()


def boot(diff, n=2000, seed=1):
    r = np.random.default_rng(seed); v = diff.values
    b = [v[r.integers(0, len(v), len(v))].mean() for _ in range(n)]
    return float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def main():
    sessions, subj = load_htt()
    by = {}
    for k, s in enumerate(sessions):
        by.setdefault(s["subject"], []).append(k)
    two = {p: ks for p, ks in by.items() if len(ks) == 2}
    keep = [k for ks in two.values() for k in ks]
    sessions = [sessions[k] for k in keep]
    other = {}
    for i, s in enumerate(sessions):
        other[i] = [j for j, t in enumerate(sessions) if t["subject"] == s["subject"] and j != i][0]
    x5 = [float(np.nanmedian(s["hr"][:5])) for s in sessions]
    xr = [float(subj.loc[s["subject"]].resting_hr) for s in sessions]
    rest_twin_1 = {}; rest_twin_inf = {}
    rest_f5 = {i: float(np.clip(x5[other[i]], 40, 100)) for i in range(len(sessions))}
    for i in range(len(sessions)):
        tw = BodyTwin()
        x = np.float32(xr[i] if np.isfinite(xr[i]) else 70.0)
        # one nightly step of the Twin rule with the seated value (the +5 sleep->seated term is not added)
        r1 = tw.params["rest_hr"] + np.float32(0.3) * (x - tw.params["rest_hr"])
        rest_twin_1[i] = float(np.clip(r1, 40, 100)); rest_twin_inf[i] = float(np.clip(x, 40, 100))
    variants = {"D": {i: POP for i in range(len(sessions))}, "R1": rest_twin_1, "Rinf": rest_twin_inf, "F5": rest_f5}
    frames, preds, mae = {}, {}, {}
    for v, ro in variants.items():
        d = build(sessions, subj, ro); frames[v] = d; preds[v] = loso_hybrid(d); mae[v] = per_subject_mae(d, preds[v])
    # C1: same-session reading on top of Rinf
    d = frames["Rinf"]; p = preds["Rinf"]
    c1 = []; c1g = []; c1_all = []
    offs_all = []; n_gated = []
    for seed in DRAWS:
        rng = np.random.default_rng(seed)
        pc = p.copy(); pg = p.copy(); ng = 0
        for i in range(len(sessions)):
            rows = np.where(d.sess_idx.values == i)[0]
            g = d.iloc[rows]
            cand = np.where((g.minute.values <= 5) & np.isfinite(g.core.values))[0]
            if not len(cand):
                continue
            j = cand[0]
            reading = float(g.core.values[j] + rng.normal(0, NOISE))
            tw = BodyTwin()
            tw.ingest_reading(reading, 0, np.nan, np.nan, float(p[rows[j]]), 0)
            tw.commit_reading()
            off = float(tw.params["core_offset"]); offs_all.append(off)
            assert tw.params["k_person"] == np.float32(0.12)
            pc[rows] = p[rows] + off
            # POST-HOC DIAGNOSTIC (not the spec rule): reject a reading > 1.0 degC from the estimate
            if abs(reading - float(p[rows[j]])) <= 1.0:
                pg[rows] = p[rows] + off
            else:
                ng += 1
        c1.append(per_subject_mae(d, pc)); c1g.append(per_subject_mae(d, pg)); n_gated.append(ng)
        c1_all.append(float((per_subject_mae(d, p, 0) - per_subject_mae(d, pc, 0)).mean()))
    base = mae["D"]
    res = {"label": "REAL DATA, HTT young adults (18-33) walking in a hot chamber, DEV (not sealed)",
           "n_people": int(len(base)), "n_sessions": len(sessions),
           "excluded_people_single_session": sorted(p for p, ks in by.items() if len(ks) != 2),
           "estimator": "v1.2 ECTemp Kalman + LOSO ridge residual (FEATS_HYB); hg2 not yet exported",
           "MAE": {}, "gain_vs_D": {}}
    for v in ("D", "R1", "Rinf", "F5"):
        res["MAE"][v] = float(mae[v].mean())
    for v in ("R1", "Rinf", "F5"):
        g = base - mae[v]
        res["gain_vs_D"][v] = dict(mean=float(g.mean()), ci95=boot(g), improved_pct=float((g > 0).mean() * 100),
                                   worst=float(g.min()))
    gains = [base - c for c in c1]
    res["MAE"]["C1"] = [float(c.mean()) for c in c1]
    res["gain_vs_D"]["C1"] = dict(mean_per_draw=[float(g.mean()) for g in gains],
                                  ci95_per_draw=[boot(g) for g in gains],
                                  improved_pct_per_draw=[float((g > 0).mean() * 100) for g in gains])
    res["POSTHOC_C1_gate_1degC"] = dict(note="post-hoc diagnostic after seeing the C1 result; not the implemented rule",
                                        sessions_rejected_per_draw=n_gated,
                                        gain_vs_D_per_draw=[float((base - c).mean()) for c in c1g],
                                        ci95_per_draw=[boot(base - c) for c in c1g])
    # DIAGNOSTIC: gain vs beta (draw 11), to show whether 0.35 is the limiting choice
    rng = np.random.default_rng(DRAWS[0]); sweep = {}
    rd = {}
    for i in range(len(sessions)):
        rows = np.where(d.sess_idx.values == i)[0]; g = d.iloc[rows]
        cand = np.where((g.minute.values <= 5) & np.isfinite(g.core.values))[0]
        if len(cand):
            rd[i] = (rows, float(g.core.values[cand[0]] + rng.normal(0, NOISE)) - float(p[rows[cand[0]]]))
    for beta in (0.1, 0.17, 0.25, 0.35, 0.5):
        pb = p.copy()
        for i, (rows, r0) in rd.items():
            pb[rows] = p[rows] + float(np.clip(beta * r0, -0.8, 0.8))
        sweep[str(beta)] = float((mae["Rinf"] - per_subject_mae(d, pb)).mean())
    res["DIAG_C1_gain_vs_Rinf_by_beta_draw11"] = sweep
    res["DIAG_C1_gain_vs_Rinf_scoring_all_minutes_from_0"] = dict(
        note="REPORT 5b (s10) scored every minute incl. minutes 0-29; this protocol scores minute >= 30",
        gain_per_draw=c1_all)
    gr = mae["Rinf"]
    res["gain_C1_vs_Rinf"] = [float((gr - c).mean()) for c in c1]
    res["offset_applied_degC"] = dict(median_abs=float(np.median(np.abs(offs_all))), max_abs=float(np.max(np.abs(offs_all))))
    res["rest_hr_learned"] = dict(median=float(np.median(list(rest_twin_inf.values()))),
                                  p10=float(np.percentile(list(rest_twin_inf.values()), 10)),
                                  p90=float(np.percentile(list(rest_twin_inf.values()), 90)))
    acc_r = all(res["gain_vs_D"][v]["mean"] >= -0.01 for v in ("R1", "Rinf"))
    acc_c = all(0.01 <= g <= 0.05 for g in res["gain_vs_D"]["C1"]["mean_per_draw"])
    res["acceptance"] = dict(rest_not_worse_than_minus_0_01=acc_r, c1_gain_in_0_01_0_05=acc_c)
    import os
    os.makedirs(OUT, exist_ok=True)
    res["first5_hr_median_bpm"] = float(np.median(x5))
    tab = pd.DataFrame({"D": mae["D"], "R1": mae["R1"], "Rinf": mae["Rinf"], "F5": mae["F5"], **{f"C1_{s}": c for s, c in zip(DRAWS, c1)}})
    tab.to_csv(f"{OUT}/htt_per_person.csv")
    json.dump(res, open(f"{OUT}/htt_eval.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
