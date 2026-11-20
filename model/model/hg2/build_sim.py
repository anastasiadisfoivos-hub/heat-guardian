"""Build the SIM-DEV feature cache (SIMULATION). Streams minutes_dev.parquet by row groups, runs FeatureState over
lanes = persons x views in lock-step, keeps a minute subsample.

Views (ARCH 4.3 members differ by sensor-noise re-draw; 4.4 step 2 domain randomisation, applied per person-view to the
RAW inputs because the features are stateful):
  view 0..3: randomised (TMP117 pair offset N(0,0.02), SHTC3 offset N(0,0.3) C / N(0,2) %, extra HR outliers at a
             rate U(0,0.12) on top of the sim's own ~0.15-0.25, flux channel off (T2 = NaN) with p = 0.3, Twin
             c_bodyheat re-draw, time unknown p = 0.1, ~1 extra 2-min band-off per day (20-min donning blank),
             Twin rest_hr / K / night baseline drawn between "population default" and "learned").
  view 4:    as 0..3 but flux channel ALWAYS off (robust member 4).
  val:       40 validation persons, nominal protocol (no extra randomisation; Twin = learned-like, see nominal_twin).
Usage: python3 -m model.hg2.build_sim [--stride 6] [--val-stride 2]
"""
import argparse, json, os, time
import numpy as np, pandas as pd
from .common import CACHE, SCENARIOS, HRAUG, SEED, dev_person_ids, val_person_ids, es_person_ids, assert_no_sealed, data_provenance, SIM
from .simio import iter_persons, persons_table, profile_of
from . import features as FT

F = np.float32
DAYT = {"S1": 0, "PRE": 1, "POST": 2}  # S2_k -> 3


def day_types():
    s = pd.read_parquet(SCENARIOS).set_index("person_id")
    out = {}
    for pid, r in s.iterrows():
        out[int(pid)] = [DAYT.get(d, 3) for d in r.day_types_1_to_N.split(",")]
    return out


def night_baseline(df, days=(1, 2, 3, 4)):
    """Twin t1_night_base learned from the first days (ARCH 5: hours with >= 20 worn still minutes at T_air < 28)."""
    g = df[df.day.isin(days) & (df.worn_truth == 2) & (df.a_std_g <= 0.002) & (df.T_air_meas < 28)]
    g = g.assign(h=g.minute_of_day // 60)
    hd = g.groupby(["h", "day"]).T1.agg(["mean", "size"])
    hd = hd[hd["size"] >= 20]
    nb = np.full(24, np.nan)
    for h, x in hd.groupby(level=0):
        if len(x) >= 3: nb[h] = float(x["mean"].mean())
    return nb


def nominal_twin(p, df, rng):
    return dict(rest_hr=float(np.clip(p["hr_rest"] + rng.normal(0, 3), 40, 100)), k_person=0.12, core_offset=0.0,
                c_bodyheat=0.15, t1_night_base=night_baseline(df))


def random_twin(p, df, rng):
    rest = 70.0 if rng.random() < 0.2 else float(np.clip(p["hr_rest"] + rng.normal(0, 4), 40, 100))
    k = 0.12 if rng.random() < 0.5 else float(np.clip(p["K_true"] * (1 + rng.normal(0, 0.15)), 0.03, 0.40))
    c = 0.15 if rng.random() < 0.5 else float(np.clip(p["c_bodyheat"] + rng.normal(0, 0.03), 0, 0.4))
    nb = night_baseline(df) if rng.random() < 0.6 else np.full(24, np.nan)
    return dict(rest_hr=rest, k_person=k, core_offset=0.0, c_bodyheat=c, t1_night_base=nb)


def randomise(cols, rng, flux_off):
    c = {k: v.copy() for k, v in cols.items()}
    T = len(c["t1"])
    if flux_off: c["t2"][:] = np.nan
    else: c["t2"] += F(rng.normal(0, 0.02))
    c["tair"] += F(rng.normal(0, 0.3)); c["rh"] = np.clip(c["rh"] + F(rng.normal(0, 2)), 0, 100).astype(F)
    r = rng.uniform(0, 0.12); m = rng.random(T) < r; half = rng.random(T) < 0.5
    c["hr"] = np.where(m & half, c["hr"] + rng.uniform(-30, 15, T).astype(F), c["hr"]).astype(F)
    c["hr"] = np.where(m & ~half, np.nan, c["hr"]).astype(F); c["hrq"] = np.where(m & ~half, 1, c["hrq"])
    if rng.random() < 0.1: c["mod"][:] = 0xFFFF
    for t0 in rng.integers(0, T - 3, size=T // 1440):
        c["worn"][t0:t0 + 2] = 0
    return c


def hr_aug(cols, Y, df, p, f):
    """M3.2: scale the person's HR rise above rest by f ~ U(0.6, 1.0) (toward the measured 74 bpm at 36 C rest, V4).
    Applied to the band's HR_meas and, consistently, to the strain target (Moran PSI from HR_true')."""
    rest = float(p["hr_rest"]); hrmax = float(p["hr_max"])
    c = dict(cols); hr = cols["hr"]
    c["hr"] = (hr - (1 - f) * np.maximum(hr - rest, 0)).astype(F)
    hrt = df.HR_true.values.astype(np.float64); hrt2 = hrt - (1 - f) * np.maximum(hrt - rest, 0)
    Y = Y.copy(); tc = df.T_core.values.astype(np.float64)
    Y[:, 5] = np.clip(5 * (tc - 36.9) / (39.5 - 36.9) + 5 * (hrt2 - rest) / (hrmax - rest), 0, 10).astype(F)
    return c, Y


def person_cols(df):
    return {k: v[:, 0] for k, v in FT.sim_cols(df).items()}


def run(stride, val_stride, batch):
    prov = data_provenance()
    ids = dev_person_ids(); val = val_person_ids(); es = es_person_ids()
    train = [i for i in ids if i not in set(val) and i not in set(es)]
    assert not (set(train) & set(val)) and not (set(train) & set(es)) and not (set(es) & set(val)) and len(train) == 270
    assert_no_sealed(ids); assert_no_sealed(val); assert_no_sealed(train)
    P = persons_table(); DT = day_types()
    kap = P.loc[ids, "kappa_core"]; terc = np.quantile(P.kappa_core.values, [1 / 3, 2 / 3])  # tercile edges over all 500 params (no outcome)
    os.makedirs(CACHE, exist_ok=True)
    store = {v: dict(X=[], Y=[], M=[]) for v in ["v0", "v1", "v2", "v3", "v4", "val", "valaug", "es"]}
    t_start = time.time()
    for bi, (bids, dfs) in enumerate(iter_persons(ids, batch=batch)):
        lanes = []  # (view, pid, cols, twin, prof, Y, dfmeta)
        for pid, df in zip(bids, dfs):
            assert len(df) == 14400 and (np.diff(df.t_min.values) == 1).all()
            p = P.loc[pid]; prof = profile_of(p); base = person_cols(df); Y = FT.build_targets(df)
            meta = np.stack([np.full(len(df), pid), df.t_min.values, df.T_in.values, df.location.values, df.activity_class.values,
                             np.array(DT[pid])[df.day.values - 1], np.full(len(df), np.searchsorted(terc, p.kappa_core)),
                             df.flux_valid_truth.values, df.HR_true.values], 1).astype(np.float32)
            if pid in set(val):
                rng = np.random.default_rng(SEED + 7000 + pid)
                tw = nominal_twin(p, df, rng)
                lanes.append(("val", pid, base, tw, prof, Y, meta))
                fa = np.random.default_rng(SEED + 7500 + pid).uniform(0.6, 1.0)          # evaluation copy with M3.2 HR scaling
                ca, Ya = hr_aug(base, Y, df, p, fa)
                lanes.append(("valaug", pid, ca, tw, prof, Ya, meta))
            elif pid in set(es):
                rng = np.random.default_rng(SEED + 7000 + pid); c, Ye = base, Y
                if HRAUG: c, Ye = hr_aug(base, Y, df, p, np.random.default_rng(SEED + 7500 + pid).uniform(0.6, 1.0))
                lanes.append(("es", pid, c, nominal_twin(p, df, rng), prof, Ye, meta))
            else:
                for v in range(5):
                    rng = np.random.default_rng(SEED + 1000 * (v + 1) + pid)
                    fo = (v == 4) or (rng.random() < 0.3)
                    c = randomise(base, rng, fo); tw = random_twin(p, df, rng); Yv = Y
                    if HRAUG: c, Yv = hr_aug(c, Y, df, p, rng.uniform(0.6, 1.0))
                    lanes.append(("v%d" % v, pid, c, tw, prof, Yv, meta))
        T = 14400; N = len(lanes)
        cols = {k: np.stack([l[2][k] for l in lanes], 1) for k in lanes[0][2]}
        prof = {k: np.array([l[4][k] for l in lanes]) for k in lanes[0][4]}
        tw0 = {k: np.array([l[3][k] for l in lanes]) for k in ("rest_hr", "k_person", "core_offset", "c_bodyheat")}
        tw0["t1_night_base"] = np.full((N, 24), np.nan)
        tw1 = dict(tw0); tw1["t1_night_base"] = np.stack([l[3]["t1_night_base"] for l in lanes])
        upd = {4 * 1440: (tw1, np.arange(N))}     # baseline learned on days 1-4, applied from day 5 (causal)
        keep = np.zeros((T, N), bool)
        for j, l in enumerate(lanes):
            isval = l[0].startswith("val") or l[0] == "es"
            s = 1 if l[0] == "val" else (val_stride if isval else stride)   # calibration set at full minute resolution (tier tests)
            ph = (l[1] * 7 + int(l[0][-1]) * 3 if not isval else 0) % s
            keep[ph:T - 30:s, j] = True
        X, aux, idx = FT.run_lanes(cols, prof, tw0, upd, keep)
        ok = aux["valid"]
        X, idx = X[ok], idx[ok]
        auxk = {k: v[ok] for k, v in aux.items()}
        for j, l in enumerate(lanes):
            sel = idx[:, 1] == j; t = idx[sel, 0]
            st = store[l[0]]
            st["X"].append(X[sel]); st["Y"].append(l[5][t])
            m = np.concatenate([l[6][t], np.stack([auxk["v12_est"][sel], auxk["v12_f20"][sel], auxk["v12_z"][sel]], 1)], 1)
            st["M"].append(m.astype(np.float32))
        print("batch %d: %d lanes, %.0f s" % (bi, N, time.time() - t_start), flush=True)
    meta_cols = ["pid", "t_min", "T_in", "location", "activity", "daytype", "kappa_t", "flux_valid_truth", "HR_true", "v12_est", "v12_f20", "v12_z"]
    for v, st in store.items():
        np.savez(os.path.join(CACHE, "sim_%s.npz" % v), X=np.concatenate(st["X"]), Y=np.concatenate(st["Y"]), M=np.concatenate(st["M"]))
    json.dump(dict(provenance=prov, stride=stride, val_stride=val_stride, train_ids=train, val_ids=val, es_ids=es,
                   split_note="M5.2: 270 gradient + 30 early-stopping (= 300 training side) / 100 calibration+evaluation persons", meta_cols=meta_cols,
                   kappa_tercile_edges=[float(x) for x in terc], daytype_codes=dict(S1=0, PRE=1, POST=2, S2=3),
                   features=FT.NAMES, targets=FT.TARGETS, label="SIMULATION"),
              open(os.path.join(CACHE, "sim_meta.json"), "w"), indent=1)
    print("done", {v: int(sum(len(x) for x in st["X"])) for v, st in store.items()})


if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("--stride", type=int, default=6); a.add_argument("--val-stride", type=int, default=2)
    a.add_argument("--batch", type=int, default=50)
    o = a.parse_args(); run(o.stride, o.val_stride, o.batch)
