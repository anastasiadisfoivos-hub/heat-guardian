#!/usr/bin/env python3
"""B1-v5 / B2b - Virtual Elders vs Brighton/Waldock (65-76 y, 35 C / 51 % RH chamber). SIMULATION vs REAL.

Manager decision (Nov 13, after the freeze-5 exam): Brighton is SPENT as an exam and ALL sheets P1..P10 may be used as
CALIBRATION data; Brighton numbers can never again be claimed as held-out for any later version.
Licence CC BY-ND 3.0: this tool keeps every derived table in memory and writes only summary numbers
(sim/data/brighton_calib_<tag>.json is NOT written; results go to stdout / the caller).

Protocol (per participant x session, Control session primary: Water/Menthol add cold drinking / menthol, not modelled):
  pre-chamber spin-up 60 min at 24 C / 40 % seated (row 0 is 'pre entering the chamber'), core then set to the measured
  rectal at elapsed 0; chamber air = measured row values (held); 30 min seated rest (1.0 met), 5-min cognitive test
  (1.1 met), 30 min cycling at the sheet's power: heat production M - W = 1.0 met + P (1/0.22 - 1) / A_D W/m2 (delta efficiency 0.22,
  older adults 0.20-0.25 - ASSUMPTION; the external work P leaves the body and is not heat), clo 0.35 (shorts/T-shirt, ASSUMPTION), v 0.2 m/s, circadian off (time unknown),
  acclim 0 (UK volunteers), no medication. The final (post-test) row is not scored (sometimes outside the chamber).
Physiology vectors: DEV persons only (sealed set-1 ids excluded by protocols.dev_persons_df), MATCHED to the cohort
  (age <= 78, frailty < 0.5, no medication flags): each participant is simulated with every matched vector (his/her
  own mass / A_D / age / measured resting HR), scored on the matched-cohort mean.
Targets (product relevance first): REST phase 0-30 min (passive heat = the product's premise): rectal change 5->30, mean HR 10-30 min minus the pre-chamber HR (= the sim's hr_rest),
  mean skin (4-site Ramanathan, sheet column Tskin) level; CYCLING 30-65 min: rectal change; WHOLE SESSION: sweat
  (pre-post nude mass, Control, urine/drink not given -> upper bound of sweat). HR during cycling is OUT of the sim's
  domain (HR model built for <= 2.2 met ADL; the met term would add > 100 bpm) and is reported only.
"""
import os, sys
import numpy as np

REPO = "/home/claude/hg_ai"
sys.path.insert(0, os.path.join(REPO, "sim")); sys.path.insert(0, os.path.join(REPO, "tests"))
XLSX = "/home/claude/hgdata/raw/older_brighton_adl_waldock/R1848_Eastbourne_Heat_Stress_Waldock.xlsx"
C = dict(time=1, power=2, rectal=3, hr=5, chest=6, bicep=7, quad=8, calf=9, tskin=10, amb_t=15, amb_rh=16)


def num(v, lo, hi):
    try: f = float(v)
    except (TypeError, ValueError): return np.nan
    return f if np.isfinite(f) and lo <= f <= hi else np.nan


def load_brighton():
    import openpyxl
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    prof = {}
    for r in wb["Participant characteristics"].iter_rows(values_only=True):
        if r and isinstance(r[0], (int, float)) and r[1] is not None:
            prof["P%d" % int(r[0])] = dict(age=float(r[1]), height=float(r[2]), mass=float(r[3]), A_D=float(r[4]))
    out = []
    for p in ["P%d" % i for i in range(1, 11)]:
        rows = list(wb[p].iter_rows(values_only=True)); names = ["Control", "Water", "Menthol"]; k = 0; i = 0; mass_pp = []
        while i < len(rows):
            r = rows[i]
            if r and len(r) > 4 and isinstance(r[1], str) and r[1].strip().lower() == "pre body mass":
                mass_pp.append((num(r[2], 30, 150), num(r[4], 30, 150)))
            if r and len(r) > 16 and isinstance(r[1], str) and r[1].strip().lower() == "time (min)":
                phase, sess, j = "rest", [], i + 1
                while j < len(rows):
                    d = rows[j]
                    if not d or all(v is None for v in d[:17]) or (len(d) > 1 and isinstance(d[1], str)): break
                    d = list(d) + [None] * 20; lab = (d[0] or "").strip().lower() if isinstance(d[0], str) else ""
                    t = d[C["time"]]
                    if lab.startswith("exercise"): phase = "ex"
                    if isinstance(t, (int, float)): el = float(t) if phase == "rest" else 35.0 + float(t)
                    elif phase == "rest": el, phase = 35.0, "test"
                    else: el = 70.0
                    sess.append(dict(el=el, power=num(d[C["power"]], 0, 1000), rectal=num(d[C["rectal"]], 35, 42), hr=num(d[C["hr"]], 30, 220),
                                     tskin=num(d[C["tskin"]], 25, 40), bicep=num(d[C["bicep"]], 25, 40),
                                     amb_t=num(d[C["amb_t"]], 10, 45), amb_rh=num(d[C["amb_rh"]], 15, 95)))
                    j += 1
                mp = mass_pp[-1] if mass_pp else (np.nan, np.nan)
                out.append(dict(pid=p, session=names[k] if k < 3 else "S%d" % k, rows=sess, prof=prof[p], mass_pre=mp[0], mass_post=mp[1]))
                k += 1; i = j
            else:
                i += 1
    return out


def matched_vectors(max_n=80):
    from velders.protocols import dev_persons_df
    df = dev_persons_df()
    meds = df[[c for c in df.columns if c.startswith("med_") and c != "med_none"]].sum(1)
    m = df[(df.age <= 78) & (df.frailty < 0.5) & (meds == 0)]
    m = m.iloc[:: max(1, len(m) // max_n)][:max_n]
    return {c: m[c].values for c in m.columns if m[c].dtype != object}


def at(rows, key, t, default):
    """value held from the last row with el <= t (causal hold), else default"""
    v = default
    for r in rows:
        if r["el"] <= t and np.isfinite(r[key]): v = r[key]
    return v


def simulate(sessions, V, adj=None, features=None):
    """vectorised: every session x every matched vector in one TwoNodeOlder. adj: v5 adjustment dict (body.V5 keys)."""
    from velders import body as B
    feats = tuple(f for f in (features or B.ALL_FEATURES) if f not in ("circadian", "medication", "acclim"))
    nS, nV = len(sessions), len(V["age"]); n = nS * nV
    person = {k: np.tile(np.asarray(v, float), nS) for k, v in V.items() if k in B.JI_DEFAULTS}
    person["acclim"] = np.zeros(n)
    for k in ("mass_kg", "A_D"): person[k] = np.repeat([s["prof"]["mass" if k == "mass_kg" else "A_D"] for s in sessions], nV).astype(float)
    hr0 = np.array([next((r["hr"] for r in s["rows"] if np.isfinite(r["hr"])), 70.0) for s in sessions])   # pre-chamber row (24-26 C)
    person["hr_rest"] = np.repeat(hr0, nV).astype(float)
    old = dict(getattr(B, "V5", {}) or {}); oldc = {}
    if adj is not None:
        B.V5 = dict(adj)                       # lowercase = person-parameter adjustments, uppercase = v5 constants
        for k, v in adj.items():
            if k.isupper() and hasattr(B, k): oldc[k] = getattr(B, k); setattr(B, k, v)   # module constants (sweeps)
    try:
        body = B.TwoNodeOlder(person, features=feats)
        env0 = dict(t_db=24.0, rh=40.0, v_air=0.1, met=1.0, clo=0.35, drink_mL=0.0)
        for _ in range(60): body.step(env0)
        body.t_core = np.repeat([s["rows"][0]["rectal"] if np.isfinite(s["rows"][0]["rectal"]) else 36.8 for s in sessions], nV).astype(float)
        # each participant's own pre-chamber state is his/her HR reference: core reference = measured pre-chamber rectal,
        # hr_rest re-based so the simulated pre-chamber HR equals the measured one (the met/ambient terms are kept)
        body.t_ref_neutral = body.t_core.copy()
        o = body.step(env0); body.t_core = np.repeat([s["rows"][0]["rectal"] if np.isfinite(s["rows"][0]["rectal"]) else 36.8 for s in sessions], nV).astype(float)
        body.p["hr_rest"] = body.p["hr_rest"] - (o["HR"] - person["hr_rest"])
        T = 66; rec = {k: np.zeros((T, n)) for k in ("T_core", "T_skin", "HR", "m_sweat")}
        A = person["A_D"]
        for t in range(T):
            ta = np.repeat([at(s["rows"], "amb_t", max(t, 5), 35.3) for s in sessions], nV)
            rh = np.repeat([at(s["rows"], "amb_rh", max(t, 5), 51.0) for s in sessions], nV)
            pw = np.repeat([next((r["power"] for r in s["rows"] if r["el"] >= t and r["el"] > 35), 0.0) if t > 35 else 0.0 for s in sessions], nV)
            pw = np.nan_to_num(pw)
            met = np.where(t > 35, 1.0 + pw * (1.0 / 0.22 - 1.0) / A / 58.2, np.where(t > 30, 1.1, 1.0))   # heat = M - external work
            o = body.step(dict(t_db=ta, rh=rh, v_air=0.2, met=met, clo=0.35, drink_mL=0.0))
            for k in rec: rec[k][t] = o[k]
        sw = rec["m_sweat"].sum(0) / 60.0 * A / 1000.0      # kg over 66 min
        ds = B.v5_skin_offsets(np.tile(V["seed"], nS))[0]   # v5 skin-core coupling (zeros in v4)
        rec["T_skin"] = rec["T_skin"] - ds[None, :]
    finally:
        B.V5 = old
        for k, v in oldc.items(): setattr(B, k, v)
    sh = lambda a: a.reshape(a.shape[0], nS, nV) if a.ndim == 2 else a.reshape(nS, nV)
    return {k: sh(v) for k, v in rec.items()}, sh(sw)


def score(sessions, sim, sweat, which=("Control",)):
    """per-session measured vs matched-cohort mean simulated; returns dict of mean errors (sim - real) and real/sim means"""
    E = {k: [] for k in ("rest_d_rectal", "ex_d_rectal", "rest_d_hr", "skin_rest_mean", "skin_ex_mean", "rectal_mae", "sweat_kg", "ex_d_hr")}
    R = {k: [] for k in E}; Sm = {k: [] for k in E}
    for i, s in enumerate(sessions):
        if s["session"] not in which: continue
        rows = {int(r["el"]): r for r in s["rows"]}
        def g(t, k): return rows[t][k] if t in rows else np.nan
        Tc, Ts, HR = sim["T_core"][:, i].mean(1), sim["T_skin"][:, i].mean(1), sim["HR"][:, i].mean(1)
        pairs = {
            "rest_d_rectal": (g(30, "rectal") - g(5, "rectal"), Tc[30] - Tc[5]),
            "ex_d_rectal": (g(65, "rectal") - g(35, "rectal"), Tc[65] - Tc[35]),
            "rest_d_hr": (np.nanmean([g(t, "hr") for t in (10, 15, 20, 25, 30)]) - g(0, "hr"), np.mean(HR[[10, 15, 20, 25, 30]]) - g(0, "hr")),
            "ex_d_hr": (g(65, "hr") - g(35, "hr"), HR[65] - HR[35]),
            "skin_rest_mean": (np.nanmean([g(t, "tskin") for t in (10, 15, 20, 25, 30)]), np.mean(Ts[[10, 15, 20, 25, 30]])),
            "skin_ex_mean": (np.nanmean([g(t, "tskin") for t in (45, 50, 55, 60, 65)]), np.mean(Ts[[45, 50, 55, 60, 65]])),
        }
        ts = [t for t in rows if 5 <= t <= 65 and np.isfinite(rows[t]["rectal"])]
        pairs["rectal_mae"] = (0.0, np.mean([abs(Tc[t] - rows[t]["rectal"]) for t in ts]))
        if np.isfinite(s["mass_pre"]) and np.isfinite(s["mass_post"]) and s["session"] == "Control":
            pairs["sweat_kg"] = (s["mass_pre"] - s["mass_post"], float(sweat[i].mean()))
        for k, (r, m) in pairs.items():
            if np.isfinite(r) and np.isfinite(m): R[k].append(r); Sm[k].append(m); E[k].append(m - r)
    f = lambda a: round(float(np.mean(a)), 3) if len(a) else None
    return {k: dict(n=len(E[k]), real=f(R[k]), sim=f(Sm[k]), err=f(E[k]), mae=f(np.abs(E[k]))) for k in E}


if __name__ == "__main__":
    S = load_brighton(); V = matched_vectors()
    print("sessions", len(S), "matched DEV vectors", len(V["age"]), file=sys.stderr)
    import json
    from velders import body as B
    res = {}
    for tag, adj in (("v4", {}), ("v5", dict(B.V5_FROZEN))):
        sim, sw = simulate(S, V, adj)
        r = score(S, sim, sw)
        C = [i for i, s in enumerate(S) if s["session"] == "Control"]
        for nm, ts in (("rest", [20, 25, 30]), ("cyc", [55, 60, 65])):
            g = (sim["T_core"][ts] - sim["T_skin"][ts]).mean(0)[C]
            r["core_minus_skin_%s_between_person_sd" % nm] = round(float(g.std(1).mean()), 3)
        res[tag] = r
    for i in (0,):
        pass
    real = {}
    for nm, ts in (("rest", (20, 25, 30)), ("cyc", (55, 60, 65))):
        g = []
        for s in S:
            if s["session"] != "Control": continue
            rr = {int(x["el"]): x for x in s["rows"]}
            g.append(np.nanmean([rr[t]["rectal"] for t in ts]) - np.nanmean([rr[t]["tskin"] for t in ts]))
        real["core_minus_skin_%s_between_person_sd" % nm] = round(float(np.std(g, ddof=1)), 3)
    res["real"] = real
    print(json.dumps(res, indent=1))
