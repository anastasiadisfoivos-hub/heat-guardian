"""ARCHITECTURE section 5 test 1 -- SIM-DEV leave-first-days-in (B3 Body Twin).  *** SIMULATION ***

100 SIM-DEV persons (never sealed: sim_io refuses to read a sealed row group and asserts), 10 days each:
the Twin learns on days 1-3 (nightly updates at 03:30 + one phone oral reading per morning, days 1-3 only),
then keeps running (nightly updates, offset decay, no more readings); core MAE is scored on days 4-10,
Twin vs population defaults.

ESTIMATOR (stated): B2's hg2 ensemble is not exported yet, so the estimator is a PROXY -- ridge regression
on band-available features built around the v1.2 KF anchor and core_flux (ARCHITECTURE 4.1 subset):
  kf (ECTemp with rest_hr), hr_above_rest, t1, flux_valid, K*dT (= core_flux - t1), dT, t_air corrected with
  c_bodyheat, t1 - t_air, act_ewm30, sin/cos time of day, t1_anom (T1 - Twin night baseline, 0 until learned).
Two proxies are trained on OTHER SIM-DEV persons (disjoint from the 100): M_default with every Twin at its
defaults, M_twin with the Twin learning as on the band. Each is scored with its own pipeline. The displayed
core = model + core_offset (offset learned only from readings, never from the model's own output).

Band-side signals that come from other modules are taken from simulator truth and labelled as such:
worn (hg_contact) = worn_truth, asleep (HDCZA) = asleep, location (hg_homeout) = location; alarm-tier proxy
for the learning freeze = proxy estimate >= 37.65 degC (Drink 37.85 - older margin 0.20).
Oral reading = T_core + N(0, 0.2) (assumes the phone converts oral to core-equivalent; see --oral-bias).

Variants: A Twin + readings; B Twin without readings (rest HR + baseline only); C flux channel absent
(T2 = NAN for everyone, both proxies retrained; the K rule must never fire); D A with an uncorrected oral
bias of -0.3 degC (sensitivity).
Acceptance (B3 brief): median per-person gain >= 0.05 degC; >= 0.10 on the top quartile of |K_true - 0.12|
or |a_axial - 0.55|; no person worse by > 0.03; C not worse than defaults.

Run: python3 eval_sim.py [--n-eval 100 --n-train 120 --jobs 2]       (needs sim/data minutes + sealed_hg2.json)
     python3 eval_sim.py --smoke     (harness self-test on synthetic frames; numbers are meaningless, never reported)
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/claude/hg_ai/twin")
from hg_twin import BodyTwin  # noqa: E402

OUT = "/home/claude/hg_ai/twin/results"
COLS = ["person_id", "day", "minute_of_day", "t_min", "T_core", "location", "asleep", "worn_truth", "activity_class",
        "T1", "T2", "T_air_meas", "HR_meas", "hr_quality", "a_std_g", "T_out", "T_in"]
FEATS = ["kf", "hr_above_rest", "t1", "fv", "kdt", "dT", "t_air", "t1_minus_air", "act_ewm30", "sin_tod", "cos_tod", "t1_anom"]
KF = dict(gamma=0.022, b0=-7887.1, b1=384.4286, b2=-4.5714, sigma=18.88, ct0=37.1)
A_EWM5 = 1 - math.exp(-1 / 5.0)
A_EWM30 = 1 - math.exp(-1 / 30.0)
TIER_PROXY = 37.65
READ_SD = 0.2
UPDATE_TOD = 210


def run_person(df, mode, model=None, flux=True, readings=True, oral_bias=0.0, seed=0, learn_days=3, k_rule=0, beta=None,
               reading_mode=0, read_sd=None):
    """mode 'default' (Twin frozen at defaults) or 'twin'. Returns (feature frame, twin, log)."""
    rng = np.random.default_rng(seed)
    tw = BodyTwin(k_rule=k_rule, beta=beta, reading_mode=reading_mode)
    rsd = READ_SD if read_sd is None else read_sd
    days = sorted(df.day.unique())
    learn = set(days[:learn_days])
    n = len(df)
    T1 = df.T1.values.astype(float); T2 = df.T2.values.astype(float) if flux else np.full(n, np.nan)
    TM = df.T_air_meas.values.astype(float); HR = df.HR_meas.values.astype(float)
    HQ = df.hr_quality.values.astype(int); AS = df.a_std_g.values.astype(float)
    WORN = df.worn_truth.values.astype(int); TOD = df.minute_of_day.values.astype(int)
    ASL = df.asleep.values.astype(int); LOC = df.location.values.astype(int); DAY = df.day.values
    TC = df.T_core.values.astype(float)
    X = np.zeros((n, len(FEATS))); EST = np.full(n, np.nan); SDON = np.zeros(n, int)
    ct, v = KF["ct0"], 0.0
    e5 = None; act30 = 0.0
    q_hist = []; t1r = []; dtr = []
    since_don = 0; read_day = set(); log = []
    SAME = np.zeros(n, bool); read_at = {}
    for i in range(n):
        p = tw.params
        rest = float(p["rest_hr"]); K = float(p["k_person"]); c = float(p["c_bodyheat"]); off = float(p["core_offset"])
        worn = WORN[i]
        since_don = since_don + 1 if worn == 2 else 0
        t1 = T1[i]; tm = TM[i]; t2 = T2[i]
        tair = tm - c * (t1 - tm) if np.isfinite(tm) and np.isfinite(t1) else tm
        fv = int(np.isfinite(t2) and np.isfinite(t1) and (t1 - t2 > 0.15) and np.isfinite(tair) and (tair < t1 - 0.5)
                 and since_don >= 20 and worn == 2)
        dT = (t1 - t2) if fv else 0.0
        kdt = min(max(K * dT, 0.0), 2.5) if fv else 0.0
        hr = HR[i] if HQ[i] == 4 and np.isfinite(HR[i]) else np.nan
        q_hist.append(HQ[i] == 4); q_hist = q_hist[-5:]
        hr_valid = int(sum(q_hist) >= 3)
        # ECTemp with the personal resting HR (v1.2: hr - (rest - 70))
        ctp, vp = ct, v + KF["gamma"] ** 2
        if np.isfinite(hr):
            cc = 2 * KF["b2"] * ctp + KF["b1"]
            k = vp * cc / (cc * cc * vp + KF["sigma"] ** 2)
            ct = ctp + k * ((hr - (rest - 70.0)) - (KF["b2"] * ctp ** 2 + KF["b1"] * ctp + KF["b0"]))
            v = (1 - k * cc) * vp
            e5 = hr if e5 is None else e5 + A_EWM5 * (hr - e5)
        else:
            ct, v = ctp, vp
        e5v = rest if e5 is None else e5
        a = AS[i] if np.isfinite(AS[i]) else 0.0
        act30 += A_EWM30 * (math.log1p(100 * a) - act30)
        h = TOD[i] // 60
        base = p["t1_night_base"][h]
        t1a = (t1 - float(base)) if np.isfinite(base) and np.isfinite(t1) else 0.0
        x = (ct, e5v - rest, t1, fv, kdt, dT, tair, t1 - tair, act30,
             math.sin(2 * math.pi * TOD[i] / 1440), math.cos(2 * math.pi * TOD[i] / 1440), t1a)
        X[i] = x; SDON[i] = since_don
        tier = 0
        if model is not None:
            EST[i] = model(np.asarray(x)) + off
            tier = int(EST[i] >= TIER_PROXY)
        if mode == "twin":
            tw.ingest_minute(dict(t1_c=t1, t2_c=t2, t_air_c=tm, hr_bpm=hr, hr_quality=HQ[i], a_std_g=AS[i], worn=worn,
                                  minute_of_day=TOD[i], asleep=ASL[i], location=LOC[i], hr_valid=hr_valid, tier_on=tier,
                                  air_ref=np.nan))
        t1r.append(t1); dtr.append(t1 - t2 if np.isfinite(t2) else np.nan); t1r = t1r[-5:]; dtr = dtr[-5:]
        # one phone oral reading per learning morning, after >= 30 still/seated minutes at home, flux valid.
        # The opportunity is found in both modes (so the same-day minutes are identical); only 'twin' applies it.
        if (DAY[i] in learn and DAY[i] not in read_day and 540 <= TOD[i] <= 720 and worn == 2
                and since_don >= 30 and LOC[i] == 0 and np.all(AS[max(0, i - 30):i + 1] < 0.02)
                and np.isfinite(TC[i])):
            t5 = float(np.nanmean(t1r)); d5 = float(np.nanmean(dtr)) if np.isfinite(dtr).any() else np.nan
            if (fv and np.isfinite(d5) and d5 >= 0.5) or not flux:
                read_day.add(DAY[i]); read_at[DAY[i]] = i
                t_read = TC[i] + rng.normal(0, rsd) + oral_bias
                if mode == "twin" and readings:
                    core_now = EST[i] if model is not None else np.nan
                    k_before = float(p["k_person"])
                    tw.ingest_reading(t_read, i, t5, d5, core_now, fv)
                    tw.commit_reading()
                    log.append(dict(day=DAY[i], tod=TOD[i], t_read=t_read, k_before=k_before, k_after=float(tw.params["k_person"]),
                                    off_after=float(tw.params["core_offset"]), fv=fv))
        if mode == "twin" and TOD[i] == UPDATE_TOD:
            ch = tw.nightly_update()
            log.append(dict(day=DAY[i], update=1, frozen=ch.get("frozen", ""), rest=float(tw.params["rest_hr"])))
    for d, i0 in read_at.items():
        SAME[i0 + 1:] |= (DAY[i0 + 1:] == d)
    F = pd.DataFrame(X, columns=FEATS)
    F["T_core"] = TC; F["est"] = EST; F["day"] = DAY; F["worn"] = WORN; F["since_don"] = SDON
    F["score"] = (~F.day.isin(learn)) & (F.worn == 2) & (F.since_don >= 20) & np.isfinite(F.T_core)
    F["sameday"] = SAME & (F.worn == 2).values & (F.since_don >= 20).values & np.isfinite(F.T_core).values
    return F, tw, log


def fit_ridge(frames, alpha=1.0, step=3):
    Z = pd.concat([f.iloc[::step] for f in frames], ignore_index=True)
    Z = Z[(Z.worn == 2) & (Z.since_don >= 20) & np.isfinite(Z.T_core)]
    A = Z[FEATS].values; y = Z.T_core.values
    mu, sd = A.mean(0), A.std(0) + 1e-9
    An = (A - mu) / sd
    w = np.linalg.solve(An.T @ An + alpha * np.eye(len(FEATS)), An.T @ (y - y.mean()))
    b = y.mean()
    wr = w / sd; br = b - mu @ wr
    return lambda x: float(x @ wr + br)


def _job(args):
    pid, df, mode, model, flux, readings, oral_bias, k_rule, beta = args[:9]
    rmode, rsd = (args[9], args[10]) if len(args) > 9 else (0, None)
    F, tw, log = run_person(df, mode, model, flux, readings, oral_bias, seed=int(pid) * 7 + 1, k_rule=k_rule, beta=beta,
                            reading_mode=rmode, read_sd=rsd)
    return pid, F, tw.params_vector(), log


def run_many(jobs, n_jobs):
    if n_jobs <= 1:
        return [_job(j) for j in jobs]
    from joblib import Parallel, delayed
    return Parallel(n_jobs=n_jobs, backend="loky")(delayed(_job)(j) for j in jobs)


def mae(F, col="score"):
    s = F[F[col]]
    return float(np.abs(s.est - s.T_core).mean()) if len(s) else np.nan


def smoke_frames(n_persons=6, days=10, seed=3):
    """Synthetic minute frames with the minutes_all column names -- harness test only (meaningless numbers)."""
    rng = np.random.default_rng(seed); out = {}; prow = []
    for pid in range(n_persons):
        K_true = rng.uniform(0.12, 0.3); off = rng.normal(0, 0.3); rest = rng.uniform(55, 80)
        t = np.arange(days * 1440); tod = t % 1440
        asleep = ((tod >= 1380) | (tod < 420)).astype(int)
        tin = 27 + 2 * np.sin(2 * np.pi * (tod - 900) / 1440)
        tc = 36.9 + off + 0.3 * np.sin(2 * np.pi * (tod - 1000) / 1440) + rng.normal(0, 0.02, len(t))
        dT = np.clip(0.25 * (tc - tin), 0.2, None)
        t1 = tc - K_true * dT * 4 + rng.normal(0, 0.05, len(t)); t2 = t1 - dT
        hr = rest + 20 * (tc - 36.9) - 6 * asleep + rng.normal(0, 3, len(t))
        df = pd.DataFrame(dict(person_id=pid, day=t // 1440, minute_of_day=tod, t_min=t, T_core=tc, location=0, asleep=asleep,
                               worn_truth=2, activity_class=2, T1=t1, T2=t2, T_air_meas=tin + 0.15 * (t1 - tin), HR_meas=hr,
                               hr_quality=4, a_std_g=np.where(asleep, 0.001, 0.0015), T_out=tin + 3, T_in=tin))
        out[pid] = df; prow.append(dict(person_id=pid, K_true=K_true, a_axial=0.55, kappa_core=20.0))
    return out, pd.DataFrame(prow)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-eval", type=int, default=100)
    ap.add_argument("--n-train", type=int, default=120)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--minutes", default="/home/claude/hg_ai/sim/data/minutes_dev_v3.parquet",
                    help="DEV minutes file (sim v3 has night sleep; v2 minutes_dev.parquet does not)")
    ap.add_argument("--variants", default="ALL")
    a = ap.parse_args()
    t0 = time.time()
    if a.smoke:
        frames, persons = smoke_frames()
        ids = sorted(frames); ev_ids, tr_ids = ids[:3], ids[3:]
        get = frames.__getitem__
    else:
        from sim_io import DevMinutes, load_persons, sealed_sim_ids
        sealed = sealed_sim_ids()
        dm = DevMinutes(COLS, path=a.minutes)
        if dm.missing:
            print("missing columns in minutes file:", dm.missing)
        dev = [p for p in dm.persons() if p not in sealed]
        assert not set(dev) & sealed
        r = np.random.default_rng(20261112 + 3)
        perm = list(r.permutation(dev))
        ev_ids = sorted(int(x) for x in perm[:a.n_eval]); tr_ids = sorted(int(x) for x in perm[a.n_eval:a.n_eval + a.n_train])
        assert not (set(ev_ids) | set(tr_ids)) & sealed, "sealed person in the Twin evaluation"
        persons = load_persons(); persons = persons[persons.person_id.isin(ev_ids + tr_ids)]
        cache = {}

        def get(pid):
            if pid not in cache:
                cache[pid] = dm.person(pid)
            return cache[pid]
        for pid in ev_ids + tr_ids:
            get(pid)
        print(f"loaded {len(cache)} DEV persons in {time.time() - t0:.0f} s")
    # name: (flux, readings, true oral bias, gap-gain rule, beta, reading mode, reading SD). M4 defaults: beta 0.25,
    # display-only. Oral reading model: T_core - 0.14 + N(0, 0.37) (Rajbhandary 2021 bias / SD); S36 uses the
    # Smith 2003 bias (-0.36) to show the cost of a wrong sourced correction; A0 = core-equivalent reading (old protocol).
    spec = {"A": (True, True, -0.14, 0, None, 0, 0.37), "S": (True, True, -0.14, 0, None, 1, 0.37),
            "S36": (True, True, -0.36, 0, None, 1, 0.37), "A0": (True, True, 0.0, 0, None, 0, 0.2),
            "B": (True, False, 0.0, 0, None, 0, None), "C": (False, True, -0.14, 0, None, 0, 0.37)}
    variants = [v for v in a.variants.split(",") if v]
    if a.variants == "ALL":
        variants = list(spec)
    res = {"label": "SIMULATION (Virtual Elders, SIM-DEV persons only)" + (" -- SMOKE TEST, MEANINGLESS" if a.smoke else ""),
           "estimator": "PROXY ridge on KF anchor + core_flux + T1/air features (B2 hg2 not exported)",
           "minutes_file": None if a.smoke else a.minutes,
           "variant_key": "A display-only (M4 default, beta 0.25, oral -0.14+-0.37); S sourced (+0.14 correction); "
                          "S36 sourced but true bias -0.36; A0 display-only with core-equivalent readings (SD 0.2); "
                          "B no readings; C T2 absent",
           "n_eval": len(ev_ids), "n_train": len(tr_ids), "variants": {}}
    models = {}
    need = {(spec[v][0], spec[v][3], spec[v][5]) for v in variants}
    for flux in sorted({x[0] for x in need}, reverse=True):
        trd = run_many([(p, get(p), "default", None, flux, False, 0.0, 0, None) for p in tr_ids], a.jobs)
        models[(flux, "default")] = fit_ridge([x[1] for x in trd])
        for rule, rm in sorted({(r, m) for f, r, m in need if f == flux}):
            trt = run_many([(p, get(p), "twin", None, flux, True, -0.14, rule, None, rm, 0.37) for p in tr_ids], a.jobs)
            models[(flux, rule, rm)] = fit_ridge([x[1] for x in trt])
        print(f"trained proxies flux={flux} ({time.time() - t0:.0f} s)", flush=True)
    per = []
    base_cache = {}
    for vname in variants:
        flux, readings, bias, rule, bta, rmode, rsd = spec[vname]
        if flux not in base_cache:
            out_d = run_many([(p, get(p), "default", models[(flux, "default")], flux, False, 0.0, 0, None) for p in ev_ids], a.jobs)
            base_cache[flux] = {r[0]: (mae(r[1]), mae(r[1], "sameday")) for r in out_d}
        out = run_many([(p, get(p), "twin", models[(flux, rule, rmode)], flux, readings, bias, rule, bta, rmode, rsd) for p in ev_ids], a.jobs)
        rows = []
        for pid, F, pv, log in out:
            m_tw = mae(F); m_d, s_d = base_cache[flux][pid]; s_tw = mae(F, "sameday")
            kmoves = sum(1 for l in log if "k_after" in l and l["k_after"] != l["k_before"])
            nread = sum(1 for l in log if "t_read" in l)
            rows.append(dict(variant=vname, person_id=pid, mae_default=m_d, mae_twin=m_tw, gain=m_d - m_tw,
                             sameday_gain=s_d - s_tw if np.isfinite(s_d) and np.isfinite(s_tw) else np.nan,
                             rest_hr=pv[0], k_person=pv[1], core_offset=pv[2], c_bodyheat=pv[3],
                             base_learned_h=int(np.isfinite(pv[4:28]).sum()), readings=nread, k_moves=kmoves))
        R = pd.DataFrame(rows).merge(persons, on="person_id", how="left", suffixes=("", "_true"))
        per.append(R)
        g = R.gain
        qK = R[(R.K_true - 0.12).abs() >= (R.K_true - 0.12).abs().quantile(0.75)]
        qa = R[(R.a_axial - 0.55).abs() >= (R.a_axial - 0.55).abs().quantile(0.75)]
        terc = pd.qcut(R.kappa_core, 3, labels=["low", "mid", "high"]) if "kappa_core" in R and R.kappa_core.nunique() > 3 else None
        bt = np.random.default_rng(1)
        bs = [np.median(g.values[bt.integers(0, len(g), len(g))]) for _ in range(2000)]
        sg = R.sameday_gain.dropna()
        v = dict(median_gain=float(g.median()), median_gain_ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                 mean_gain=float(g.mean()), worst_gain=float(g.min()), n_worse_0_03=int((g < -0.03).sum()),
                 improved_pct=float((g > 0).mean() * 100), mae_default_median=float(R.mae_default.median()),
                 mae_twin_median=float(R.mae_twin.median()), topq_absK_median_gain=float(qK.gain.median()),
                 topq_absaxial_median_gain=float(qa.gain.median()), k_moves_total=int(R.k_moves.sum()),
                 readings_total=int(R.readings.sum()), persons_with_reading=int((R.readings > 0).sum()),
                 k_final_median=float(R.k_person.median()), k_at_upper_bound_pct=float((R.k_person >= (1.4999 if rule == 1 else 0.3999)).mean() * 100),
                 sameday_gain_mean=float(sg.mean()) if len(sg) else None, sameday_gain_median=float(sg.median()) if len(sg) else None,
                 rest_hr_vs_true_median_abs=float((R.rest_hr - R.hr_rest).abs().median()) if "hr_rest" in R else None,
                 base_hours_learned_median=float(R.base_learned_h.median()))
        if terc is not None:
            v["median_gain_by_kappa_tercile"] = {str(k): float(x) for k, x in R.groupby(terc, observed=True).gain.median().items()}
        if vname == "C":
            v["K_rule_never_fired"] = bool(R.k_moves.sum() == 0)
        res["variants"][vname] = v
        print(vname, json.dumps(v), f"({time.time() - t0:.0f} s)", flush=True)
    A = res["variants"].get("A")
    if A:
        res["acceptance"] = dict(median_gain_ge_0_05=A["median_gain"] >= 0.05,
                                 topq_ge_0_10=max(A["topq_absK_median_gain"], A["topq_absaxial_median_gain"]) >= 0.10,
                                 no_person_worse_0_03=A["n_worse_0_03"] == 0,
                                 flux_absent_not_worse=(res["variants"]["C"]["median_gain"] >= 0 and res["variants"]["C"]["K_rule_never_fired"]) if "C" in res["variants"] else None)
    res["runtime_s"] = round(time.time() - t0)
    os.makedirs(OUT, exist_ok=True)
    tag = "smoke_" if a.smoke else ""
    sfx = "" if a.smoke else ("_" + os.path.basename(a.minutes).split("_")[-1].replace(".parquet", "") if "_v" in os.path.basename(a.minutes) else "")
    pd.concat(per).to_csv(f"{OUT}/{tag}sim_per_person{sfx}.csv", index=False)
    json.dump(res, open(f"{OUT}/{tag}sim_eval{sfx}.json", "w"), indent=1, default=float)
    print(json.dumps(res.get("acceptance", {}), indent=1))


if __name__ == "__main__":
    main()
