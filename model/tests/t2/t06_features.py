"""T2-06 feature parity: model/hg2/features.FeatureState vs guardian/py/hg_guardian_py.HG2 (B5 mirror) on 3 DEV persons x 1 day,
plus an independent from-the-spec recomputation (ARCH 4.1) of the features that the spec defines unambiguously, plus a
10-day replay of one calibration person vs the cached training/eval rows (sim_val.npz).  SIMULATION.
Run: cd /home/claude/hg_ai && HG2_SIMVER=v4 HG2_HRAUG=1 python3 tests/t2/t06_features.py"""
import json, os, sys
sys.path.insert(0, "/home/claude/hg_ai"); sys.path.insert(0, "/home/claude/hg_ai/tests/t2")
os.environ["HG2_SIMVER"] = "v4"; os.environ["HG2_HRAUG"] = "1"
import numpy as np
from model.hg2 import features as FT, common as C
from model.hg2.simio import iter_persons, persons_table, profile_of
from model.hg2.build_sim import nominal_twin, day_types
import hg_guardian_py as REF
from t2lib import load_weights, ens
F = np.float32; R = {}
SPEC = ["t1", "t1_d5", "t1_d15", "dT", "dT_d10", "flux_valid", "t_air", "t_air_d15", "rh", "t1_minus_air", "hr", "hr_ewm5", "hr_ewm45",
        "hr_above_rest", "hr_reserve", "hr_valid", "log_pi", "act", "act_ewm30", "min_since_active", "kf", "heat_dose", "min_since_don",
        "sin_tod", "cos_tod", "core_flux", "t1_anom", "age", "sex_m", "bmi", "bb_flag", "low_sweat_flag"]   # ARCH 4.1 table, typed by the tester
R["names_equal_ARCH_4.1"] = FT.NAMES == SPEC
P = persons_table(); DT = day_types(); cal = C.val_person_ids(); trn = [i for i in C.dev_person_ids() if i not in set(cal) and i not in set(C.es_person_ids())]
pick = [cal[5], cal[17], trn[3]]; C.assert_no_sealed(pick)
_, dfs = next(iter_persons(pick, batch=3))
Wt = REF.Weights(); Wm = load_weights()
par = {}; spec_err = {}
for j, (pid, df) in enumerate(zip(pick, dfs)):
    day = 1 + int(np.argmax(np.array(DT[pid]) == 3)); g = df[df.day == day].reset_index(drop=True)
    p = P.loc[pid]; prof = profile_of(p); tw = nominal_twin(p, df, np.random.default_rng(C.SEED + 7000 + pid))
    tw["t1_night_base"] = [float(v) for v in tw["t1_night_base"]]
    cols = {k_: v_.copy() for k_, v_ in FT.sim_cols(g).items()}
    if j == 2:   # third person: inject band-off, NaN HR runs, time unknown block, T2 missing block (exercise the missing rules)
        cols["worn"][300:340] = 0; cols["worn"][340:360] = 1; cols["hr"][500:530] = np.nan; cols["mod"][800:900] = 0xFFFF; cols["t2"][1000:1100] = np.nan
    mine = FT.build_features(g.assign(**{k_: cols[c_][:, 0] for k_, c_ in (("worn_truth", "worn"), ("HR_meas", "hr"), ("minute_of_day", "mod"), ("T2", "t2"))}), tw, prof)
    h = REF.HG2(prof, tw, Wt); ref = np.empty_like(mine); outs = []
    for t in range(len(g)):
        i = dict(t1=cols["t1"][t, 0], t2=cols["t2"][t, 0], tair=cols["tair"][t, 0], rh=cols["rh"][t, 0], hr=cols["hr"][t, 0], pi=cols["pi"][t, 0],
                 astd=cols["astd"][t, 0], hrq=int(cols["hrq"][t, 0]), worn=int(cols["worn"][t, 0]), mod=int(cols["mod"][t, 0]))
        o, aux = h.step(i); ref[t] = aux["x"]; outs.append(o)
    eq = (mine == ref) | (np.isnan(mine) & np.isnan(ref))
    bad = {SPEC[c]: int((~eq[:, c]).sum()) for c in range(32) if (~eq[:, c]).any()}
    Em = ens(Wm, ref)
    par[int(pid)] = dict(day=day, minutes=len(g), mismatching_values=int((~eq).sum()), mismatching_features=bad,
                         ref_out_core_now_vs_tester_forward_maxabs=float(np.nanmax(np.abs(np.array([o["core_now"] for o in outs]) - Em["core_now"]))),
                         ref_out_sd_now_vs_tester_forward_maxabs=float(np.nanmax(np.abs(np.array([o["sd_now"] for o in outs]) - Em["sd_now"]))))
    # ---- independent spec recomputation (float64, from raw columns, own state machine)
    t1r, t2r, tar, rhr, hrr, hq, pir, ar, wr, mod = (cols[k][:, 0].astype(float) for k in ("t1", "t2", "tair", "rh", "hr", "hrq", "pi", "astd", "worn", "mod"))
    n = len(g); X = np.full((n, 32), np.nan); last_t1 = np.nan; last_ta = np.nan; last_rh = np.nan; msd = 0; lw = 0; hr_last = tw["rest_hr"]
    e5 = e45 = tw["rest_hr"]; a30 = 0.0; msa = 0; t1h = []; tah = []; dth = []
    hrmax = (164.0 if prof["med_flags"] & 1 else 208.0) - 0.7 * prof["age"]
    for t in range(n):
        if wr[t] == 2: msd = 0 if lw != 2 else min(msd + 1, 60)
        else: msd = 0
        lw = wr[t]
        if wr[t] != 0 and t1r[t] == t1r[t]: last_t1 = t1r[t]
        if tar[t] == tar[t]: last_ta = tar[t]
        if rhr[t] == rhr[t]: last_rh = rhr[t]
        ta = last_ta - 0.15 * (last_t1 - last_ta)
        fvv = wr[t] == 2 and t2r[t] == t2r[t] and (last_t1 - t2r[t]) > 0.15 and ta < last_t1 - 0.5 and msd >= 20
        dT = last_t1 - t2r[t] if fvv else 0.0
        t1h.append(last_t1); tah.append(ta); dth.append(dT)
        back = lambda hh, k: hh[max(0, len(hh) - 1 - k)]
        X[t, 0] = last_t1; X[t, 1] = last_t1 - back(t1h, 5); X[t, 2] = last_t1 - back(t1h, 15); X[t, 3] = dT
        X[t, 4] = dT - back(dth, 10) if fvv else 0.0; X[t, 5] = float(fvv); X[t, 6] = ta; X[t, 7] = ta - back(tah, 15); X[t, 8] = last_rh
        X[t, 9] = last_t1 - ta
        good = hq[t] == 4 and 30 <= hrr[t] <= 220
        if good: hr_last = hrr[t]
        e5 += 0.1813 * (hr_last - e5); e45 += 0.0220 * (hr_last - e45)
        X[t, 10] = hr_last; X[t, 11] = e5; X[t, 12] = e45; X[t, 13] = hr_last - tw["rest_hr"]; X[t, 14] = (hr_last - tw["rest_hr"]) / (hrmax - tw["rest_hr"])
        X[t, 16] = np.log1p(pir[t]) if pir[t] == pir[t] else 0.0
        a = ar[t] if ar[t] == ar[t] else 0.0; act = np.log1p(100 * a); a30 += 0.0328 * (act - a30)
        msa = 0 if a > 0.02 else min(msa + 1, 240)
        X[t, 17] = act; X[t, 18] = a30; X[t, 19] = msa / 240; X[t, 22] = msd / 60
        tk = mod[t] < 1440
        X[t, 23] = np.sin(2 * np.pi * mod[t] / 1440) if tk else 0.0; X[t, 24] = np.cos(2 * np.pi * mod[t] / 1440) if tk else 0.0
        X[t, 25] = min(max(last_t1 + tw["k_person"] * dT, last_t1), last_t1 + 2.5) if fvv else last_t1
        X[t, 27] = prof["age"] / 100; X[t, 28] = prof["sex_m"]; X[t, 29] = prof["bmi"] / 30; X[t, 30] = float(prof["med_flags"] & 1 != 0); X[t, 31] = float(prof["med_flags"] & 4 != 0)
    cmp = {}
    for c in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 22, 23, 24, 25, 27, 28, 29, 30, 31]:
        cmp[SPEC[c]] = float(np.nanmax(np.abs(X[:, c] - mine[:, c].astype(float))))
    spec_err[int(pid)] = cmp
R["parity_vs_B5_mirror"] = par; R["spec_recompute_maxabs"] = spec_err
# ---- 10-day replay of one calibration person vs the cached rows (builder's cache == features on raw data?)
d = np.load(C.CACHE + "/sim_val.npz"); mc = json.load(open(C.CACHE + "/sim_meta.json"))["meta_cols"]
pid = pick[0]; sel = d["M"][:, 0] == pid; tm = d["M"][sel, mc.index("t_min")].astype(int); Xc = d["X"][sel]
df = dfs[0]; p = P.loc[pid]; prof = profile_of(p); tw = nominal_twin(p, df, np.random.default_rng(C.SEED + 7000 + pid))
cols = FT.sim_cols(df); tw0 = dict(tw); tw0["t1_night_base"] = np.full(24, np.nan)
st = FT.FeatureState(prof, tw0, 1); Xall = np.empty((len(df), 32), F)
for t in range(len(df)):
    if t == 4 * 1440: st.set_twin(tw)
    Xall[t] = st.step(*(cols[k][t] for k in ("t1", "t2", "tair", "rh", "hr", "hrq", "pi", "astd", "worn", "mod")))[0][0]
idx = np.searchsorted(df.t_min.values, tm); A = Xall[idx]
eq = (A == Xc) | (np.isnan(A) & np.isnan(Xc))
R["cache_replay"] = dict(person=int(pid), cached_rows=int(sel.sum()), mismatching_values=int((~eq).sum()))
json.dump(R, open("/home/claude/hg_ai/tests/t2/out/t06_features.json", "w"), indent=1); print(json.dumps(R, indent=1))
