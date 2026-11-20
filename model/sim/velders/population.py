"""Population run: persons -> minute data (SIMULATION). Called by velders.run.

Routing: sealed person ids are read from /home/claude/hg_ai/model/sealed_hg2.json (written once by
the manager's seal script; this package never decides the split). Sealed persons go to
*_sealed.parquet, all others to *_dev.parquet. Every person's scenario, sensor noise and IMU draws
come from that person's own seed (seed + id, streams 1/2/3), so the batching and the split never
change a person's data.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .body import TwoNodeOlder
from .sensors import BandSensors, person_noise
from .scenarios import build_person, env_arrays, ASTD, ZANG, ACT_NAMES, EVENT_TYPES, MPD

SEALED_JSON = "/home/claude/hg_ai/model/sealed_hg2.json"
PERSONS_SHA = "eb9ad75e3b52caebffa3c7f61a90caffd41d950e64e41ccc0276b0f09e4b5aca"
CHUNK = 25

TRUTH_COLS = ["T_core", "T_skin_mean", "T_deep_wrist", "s_skbf", "m_sweat", "w", "deficit_pct", "HR_true", "met",
              "T_in", "RH_in", "T_out", "location", "activity_class", "asleep", "fan", "clo", "drink_mL",
              "sun_on_lid", "worn_truth"]
SENSOR_COLS = ["T1", "T2", "T_air_meas", "RH_meas", "HR_meas", "hr_quality", "PI", "a_std_g", "zangle_deg",
               "flux_valid_truth"]
LABEL_COLS = ["ev38_30", "ev385_30", "strain_psi"]
INT_COLS = {"location", "activity_class", "asleep", "fan", "sun_on_lid", "worn_truth", "hr_quality",
            "flux_valid_truth", "ev38_30", "ev385_30", "day", "minute_of_day", "person_id"}


def thirst_threshold(P):
    """% body-mass deficit that triggers a drink (blunted thirst, R1 §2.4 Phillips 1984; frailty
    x(1-0.5 f); ACE/ARB blunt thirst further, R1 §5). Young-adult reference ~0.5 %."""
    drive = P["thirst_factor"] * (1 - 0.5 * P["frailty"]) * np.where(P["med_ace_arb"] > 0, 0.8, 1.0)
    return 0.5 / drive


def imu_truth(P_row, act, still, seed):
    rng = np.random.default_rng([seed, 3])
    n = act.shape[0]
    mu = np.array([ASTD[k][0] for k in ACT_NAMES])[act]
    sd = np.array([ASTD[k][1] for k in ACT_NAMES])[act]
    a = np.maximum(mu + sd * rng.normal(size=n), 0.0003)
    a = np.where(still > 0, 0.0004, a)
    zm = np.array([ZANG[k][0] for k in ACT_NAMES])[act]
    zs = np.array([ZANG[k][1] for k in ACT_NAMES])[act]
    # posture persists within a bout: AR(1) around the activity mean
    e = rng.normal(size=n)
    z = np.empty(n)
    acc = 0.0
    for i in range(n):
        acc = 0.9 * acc + np.sqrt(1 - 0.81) * e[i]
        z[i] = zm[i] + zs[i] * acc
    return a.astype(np.float32), np.clip(z, -89, 89).astype(np.float32)


def simulate_chunk(args):
    rows, days = args            # rows: list of person dicts
    n = len(rows)
    D = days + 1
    T = D * MPD
    P = {k: np.array([r[k] for r in rows]) for k in rows[0] if not isinstance(rows[0][k], str)}
    tls, envs, minss, noises, imus = [], [], [], [], []
    for r in rows:
        tl, mins, _ = build_person(r, days, int(r["seed"]))
        tls.append(tl); minss.append(mins); envs.append(env_arrays(r, tl, mins))
        noises.append(person_noise(int(r["seed"]), T))
        imus.append(imu_truth(r, tl.act, tl.still, int(r["seed"])))
    stack = lambda key: np.stack([e[key] for e in envs], 1)
    E = {k: stack(k) for k in envs[0]}
    TL = {k: np.stack([getattr(t, k) for t in tls], 1) for k in ("loc", "room", "asleep", "fan", "sun", "drink", "extra_loss",
                                                                 "worn", "r_gap", "flash", "rh_wet", "slip")}
    M = {k: np.stack([m[k] for m in minss], 1) for k in ("t_in", "rh_in", "t_out", "s_rad", "t_bed")}
    NZ = {k: np.stack([z[k] for z in noises], 1) for k in noises[0]}
    A_TRUE = np.stack([x[0] for x in imus], 1)
    Z_TRUE = np.stack([x[1] for x in imus], 1)
    sun_lid = (TL["sun"] > 0) & (M["s_rad"] > 200)
    sun_dT = np.where(sun_lid, E["sun_dT"], 0.0)

    body = TwoNodeOlder(P, minute_of_day0=0.0)
    sens = BandSensors(P, NZ)
    from .body import v5_skin_offsets
    d_skin = v5_skin_offsets(P["seed"])[0]          # v5 skin-core coupling (zeros in v4)
    thr = thirst_threshold(P)
    refr = np.zeros(n)
    out = {c: np.empty((T, n), np.float32) for c in TRUTH_COLS + SENSOR_COLS + ["drift", "min_since_don"]}
    for t in range(T):
        mod = t % MPD
        awake = TL["asleep"][t] == 0
        defp = np.maximum(body.deficit_g, 0) / (P["mass_kg"] * 1000.0) * 100.0
        thirsty = awake & (defp > thr) & (refr <= 0)
        drink = TL["drink"][t] + np.where(thirsty, 150.0, 0.0)
        refr = np.where(thirsty, 30.0, refr - 1)
        env = dict(t_db=E["t_db"][t], rh=E["rh"][t], t_r=E["t_r"][t], v_air=E["v_air"][t], met=E["met"][t],
                   clo=E["clo"][t], drink_mL=drink, extra_water_loss_g=TL["extra_loss"][t], minute_of_day=mod,
                   standing=E["met"][t] >= 0.95)
        o = body.step(env)
        truth = dict(T_core=o["T_core"], s_skbf=o["s_skbf"], T_air=E["t_db"][t], RH_air=E["rh"][t], HR_true=o["HR"],
                     m_sweat=o["m_sweat"], deficit_pct=o["deficit_pct"])
        ctx = dict(worn=TL["worn"][t], h_out=E["h_out"][t], r_gap=TL["r_gap"][t], sun_dT=sun_dT[t], flash=TL["flash"][t],
                   asleep=TL["asleep"][t], rh_wet=TL["rh_wet"][t], a_std_true=A_TRUE[t], act_class=E["act_class"][t],
                   zangle_true=Z_TRUE[t], slip=TL["slip"][t])
        s = sens.step(truth, ctx)
        row = out
        row["T_core"][t] = o["T_core"]; row["T_skin_mean"][t] = o["T_skin"] - d_skin; row["T_deep_wrist"][t] = s["T_deep_wrist"]
        row["s_skbf"][t] = o["s_skbf"]; row["m_sweat"][t] = o["m_sweat"]; row["w"][t] = o["w"]
        row["deficit_pct"][t] = o["deficit_pct"]; row["HR_true"][t] = o["HR"]; row["met"][t] = E["met"][t]
        row["drift"][t] = o["drift"]; row["drink_mL"][t] = drink; row["min_since_don"][t] = s["min_since_don"]
        for k in SENSOR_COLS:
            row[k][t] = s[k]
    # T_in / RH_in = the air the person is in (bedroom, living room, outdoors, AC place) -- round 3, tester F14
    out["T_in"] = E["t_db"].astype(np.float32)
    out["RH_in"] = E["rh"].astype(np.float32)
    out["T_out"] = M["t_out"]
    out["location"] = TL["loc"]; out["activity_class"] = E["act_class"]; out["asleep"] = TL["asleep"]
    out["fan"] = TL["fan"]; out["clo"] = E["clo"]; out["sun_on_lid"] = sun_lid.astype(np.int8); out["worn_truth"] = TL["worn"]
    # labels
    Tc = np.round(out["T_core"].astype(np.float64), 3)     # labels from the stored (0.001 C) core, tester F13
    fut = np.full_like(Tc, -np.inf)
    # max over (t, t+30]
    pad = np.vstack([Tc[1:], np.full((30, n), -np.inf)])
    from numpy.lib.stride_tricks import sliding_window_view
    win = sliding_window_view(pad, 30, axis=0)[:T]
    fut = win.max(-1)
    out["ev38_30"] = (fut >= 38.0).astype(np.int8)
    out["ev385_30"] = (fut >= 38.5).astype(np.int8)
    rest = P["hr_rest"][None, :]
    hrmax = P["hr_max"][None, :]
    psi = 5 * (Tc - 36.9) / (39.5 - 36.9) + 5 * (out["HR_true"] - rest) / (hrmax - rest)
    out["strain_psi"] = np.clip(psi, 0, 10).astype(np.float32)

    results = []
    for j, r in enumerate(rows):
        pid = int(r["person_id"])
        sl = slice(MPD, T)           # drop spin-up day 0
        df = pd.DataFrame({"person_id": np.full(T - MPD, pid, np.int16),
                           "day": (np.arange(MPD, T) // MPD).astype(np.int16),
                           "minute_of_day": (np.arange(MPD, T) % MPD).astype(np.int16),
                           "t_min": np.arange(T - MPD, dtype=np.int32)})
        for c in TRUTH_COLS + SENSOR_COLS + LABEL_COLS:
            v = out[c][sl, j]
            df[c] = v.astype(np.int8) if c in INT_COLS else v.astype(np.float32)
        ev = events_for(pid, tls[j], out, j, MPD, T)
        ppg = ppg_for(r, df, tls[j], int(r["seed"]))
        results.append((pid, df, ev, ppg, tls[j].day_types[1:], tls[j].regime))
    return results


def _runs(mask):
    m = np.concatenate([[0], mask.astype(np.int8), [0]])
    d = np.diff(m)
    return np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]


def events_for(pid, tl, out, j, o, T):
    ev = []
    for typ, d, a, b in tl.events:
        if d >= 1:
            ev.append((pid, d, typ, a - o, b - o))
    tc = out["T_core"][o:T, j]
    for thr, name in ((38.0, "core38"), (38.5, "core385")):
        s, e = _runs(tc >= thr)
        for a, b in zip(s, e):
            ev.append((pid, int((a + o) // MPD), name, int(a), int(b)))
    # truth HR drift onset: cardiovascular drift term first exceeds 5 bpm (per episode)
    dr = out["drift"][o:T, j]
    s, e = _runs(dr > 5.0)
    for a, b in zip(s, e):
        ev.append((pid, int((a + o) // MPD), "hr_drift_onset", int(a), int(b)))
    # core inflection: 15-min slope > 0.1 C/h above the slope of the preceding 30 min, sustained 30 min, core > 37.3
    rate = np.zeros_like(tc); rate[15:] = (tc[15:] - tc[:-15]) * 4.0
    base = np.zeros_like(tc); base[45:] = (tc[15:-30] - tc[:-45]) * 2.0
    m = (rate > np.maximum(base, 0) + 0.1) & (tc > 37.3)
    s, e = _runs(m)
    for a, b in zip(s, e):
        if b - a >= 30:
            ev.append((pid, int((a + o) // MPD), "core_inflection", int(a), int(b)))
    return ev


def ppg_for(r, df, tl, seed, frac=0.02):
    """1-Hz PPG summaries for ~2 % of minutes: the minutes around every band-event boundary
    (loose / off / shower, +-5 min) first, then random minutes, capped at 2 %."""
    rng = np.random.default_rng([seed, 4])
    n = len(df)
    worn = df["worn_truth"].values
    chg = np.nonzero(np.diff(worn.astype(int)) != 0)[0]
    sel = set()
    for c in chg:
        sel.update(range(max(0, c - 5), min(n, c + 6)))
    sel = sorted(sel)
    cap = int(frac * n)
    if len(sel) > cap:
        sel = sorted(rng.choice(sel, cap, replace=False).tolist())
    extra = cap - len(sel)
    if extra > 0:
        pool = np.setdiff1d(np.arange(n), sel)
        sel = sorted(sel + rng.choice(pool, extra, replace=False).tolist())
    sel = np.array(sel, int)
    k = len(sel)
    hr = df["HR_meas"].values[sel]
    hr_t = np.where(np.isnan(hr), df["HR_true" if "HR_true" in df else "HR_meas"].values[sel], hr)
    pi = np.nan_to_num(df["PI"].values[sel], nan=0.0)
    w = worn[sel]
    a = df["a_std_g"].values[sel]
    sec = np.arange(60)
    dc = np.where(w[:, None] == 0, rng.uniform(2000, 15000, (k, 1)), rng.uniform(50000, 110000, (k, 1))) * (1 + 0.01 * rng.normal(size=(k, 60)))
    ac = dc * pi[:, None] / 100.0 * (1 + 0.1 * rng.normal(size=(k, 60)))
    motion = np.abs(a[:, None] * (1 + 0.3 * rng.normal(size=(k, 60))))
    phase = rng.uniform(0, 1, (k, 1)) + np.cumsum(np.repeat(hr_t[:, None] / 60.0, 60, 1), 1)
    beat = np.diff(np.floor(np.concatenate([phase[:, :1] - hr_t[:, None] / 60.0, phase], 1)), axis=1)
    beat = np.where(w[:, None] == 0, 0, beat)
    drop = rng.uniform(size=(k, 60)) < np.clip(0.05 + 2 * motion, 0, 0.8)
    beat = np.where(drop, 0, beat)
    return pd.DataFrame({"person_id": np.repeat(df["person_id"].values[sel], 60),
                         "t_min": np.repeat(df["t_min"].values[sel], 60).astype(np.int32),
                         "sec": np.tile(sec, k).astype(np.int8),
                         "ir_dc": dc.ravel().astype(np.float32), "ir_ac": ac.ravel().astype(np.float32),
                         "motion_g": motion.ravel().astype(np.float32), "beat": beat.ravel().astype(np.int8),
                         "worn_truth": np.repeat(w, 60).astype(np.int8)})


DECIMALS = {"a_std_g": 5, "motion_g": 5, "ir_ac": 1, "ir_dc": 0}


def quantise(df):
    """Store floats at fixed resolution (0.001 by default; 1e-5 g for accelerations) so zstd can compress the
    noise digits away (690 MB -> ~260 MB). 0.001 C is 8x finer than the TMP117 LSB (0.0078 C)."""
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == np.float32:
            df[c] = np.round(df[c].astype(np.float64), DECIMALS.get(c, 3)).astype(np.float32)
    return df


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run_population(a, t0):
    out = a.out
    pp = os.path.join(out, "persons.parquet")
    assert _sha(pp) == PERSONS_SHA, "persons.parquet differs from the sealed SHA-256 -- refusing to run"
    sealed = set(json.load(open(SEALED_JSON))["sealed_sim_person_ids"])
    df = pd.read_parquet(pp)
    if getattr(a, "dev_only", False):   # B2b-v5: DEV persons only; no sealed id of any set is simulated
        allsealed = set(sealed)
        for fn in ("sealed_hg2_set2.json", "sealed_hg2_set3.json", "sealed_hg2_set4.json"):
            pth = os.path.join(os.path.dirname(SEALED_JSON), fn)
            if os.path.exists(pth):
                for v in json.load(open(pth)).values():
                    if isinstance(v, list) and v and all(isinstance(x, int) for x in v): allsealed |= set(v)
        df = df[~df.person_id.isin(allsealed)].reset_index(drop=True)
        assert not set(df.person_id) & allsealed
    if a.first:
        df = df.iloc[:a.first]
    rows = df.to_dict("records")
    chunks = [(rows[i:i + CHUNK], a.days) for i in range(0, len(rows), CHUNK)]
    writers, schemas = {}, {}
    ev_all = {"dev": [], "sealed": []}
    meta = {b"label": b"SIMULATION", b"generator": b"velders " + __import__("velders").__version__.encode()}

    def write(kind, split, frame):
        key = (kind, split)
        frame = quantise(frame)
        tbl = pa.Table.from_pandas(frame, preserve_index=False)
        if key not in writers:
            path = os.path.join(out, f"{kind}_{split}{a.suffix}.parquet")
            writers[key] = pq.ParquetWriter(path, tbl.schema.with_metadata(meta), compression="zstd", compression_level=9)
        writers[key].write_table(tbl.replace_schema_metadata(meta))

    regimes = []
    with Pool(a.workers) as pool:
        for k, res in enumerate(pool.imap(simulate_chunk, chunks)):
            for pid, mdf, ev, ppg, dtypes, reg in res:
                split = "sealed" if pid in sealed else "dev"
                write("minutes", split, mdf)
                write("ppg_1hz", split, ppg)
                ev_all[split].extend(ev)
                regimes.append((pid, split, reg, ",".join(dtypes)))
            print(f"chunk {k + 1}/{len(chunks)} done, {time.time() - t0:.0f} s", flush=True)
    for w in writers.values():
        w.close()
    for split, ev in ev_all.items():
        if getattr(a, "dev_only", False) and split == "sealed": continue
        e = pd.DataFrame(ev, columns=["person_id", "day", "type", "t_start", "t_end"])
        e = e.sort_values(["person_id", "t_start", "type"], kind="mergesort").reset_index(drop=True)
        e["person_id"] = e["person_id"].astype(np.int16); e["day"] = e["day"].astype(np.int16)
        e["t_start"] = e["t_start"].astype(np.int32); e["t_end"] = e["t_end"].astype(np.int32)
        pq.write_table(pa.Table.from_pandas(e, preserve_index=False).replace_schema_metadata(meta),
                       os.path.join(out, f"events_{split}{a.suffix}.parquet"), compression="zstd")
    sc = pd.DataFrame(regimes, columns=["person_id", "split", "regime", "day_types_1_to_N"])
    for split in (("dev",) if getattr(a, "dev_only", False) else ("dev", "sealed")):      # split files (tester F9)
        pq.write_table(pa.Table.from_pandas(sc[sc.split == split].reset_index(drop=True), preserve_index=False).replace_schema_metadata(meta),
                       os.path.join(out, f"scenarios_{split}{a.suffix}.parquet"), compression="zstd")
    for f in sorted(os.listdir(out)):
        if f.endswith(".parquet"):
            p = os.path.join(out, f)
            print(f"{f}\t{os.path.getsize(p) / 1e6:.1f} MB\tsha256 {_sha(p)}")
    if not a.suffix:
        write_readme(out)
    print(f"total {time.time() - t0:.0f} s")


README = """# Virtual Elders data — SIMULATION

**Everything in this folder is SIMULATION.** Generated by `velders` (numpy Gagge-Ji two-node model for 65-85 y with
literature-prior parameters, R1/R2/R3 of /home/claude/hg_ai/research). No 65+ time series exists anywhere in this
project; these data prove nothing about real older adults. Validation: /home/claude/hg_ai/sim/VALIDATION.md.

Regenerate (byte-identical, ~5 min on 2 CPUs): `cd /home/claude/hg_ai/sim && python3 -I -m velders.run --n 500 --days 10 --out /home/claude/hg_ai/sim/data/ --workers 2`

## Files
- `persons.parquet` — 500 persons x every drawn parameter (ARCH §3.3). **Sealed by the manager (model/sealed_hg2.json); never rewritten.**
- `minutes_dev.parquet` / `minutes_sealed.parquet` — one row per person-minute, 10 days (spin-up day 0 dropped), one row group per person.
  Routing by `model/sealed_hg2.json` (100 sealed ids). Floats stored at 0.001 resolution (accelerations 1e-5 g).
- `ppg_1hz_dev/sealed.parquet` — 1-Hz PPG summaries for 2 % of minutes (all band-event boundaries +-5 min first, then random).
- `events_dev/sealed.parquet` — episodes: person_id, day, type, t_start, t_end (t in minutes from day 1 00:00).
- `scenarios.parquet` — per person: split, weather regime (S1 / S2), day types for days 1..10.

## Keys
person_id (int16), day (1..10), minute_of_day (0..1439), t_min (0..14399).

## Truth columns
| column | unit | meaning |
|---|---|---|
| T_core | C | two-node core temperature (circadian, hydration, medication, acclimatisation included) |
| T_skin_mean | C | reported 8-site-equivalent mean skin = skin node + 0.12 (Tc - Ts) + 1.2 max(0, w - 0.07) (V3 report fix) |
| T_deep_wrist | C | T_core - D_axial (R2 §6.1) |
| s_skbf | 0..1 | skin blood flow, log-scaled between the person's min and max |
| m_sweat | g/(h m2) | regulatory sweat produced |
| w | 0..1 | skin wettedness |
| deficit_pct | % body mass | water deficit |
| HR_true | bpm | model heart rate (rest + ambient + excess core + met + cardiovascular drift) |
| met | ASHRAE met | metabolic rate (clamp list x person multiplier, never 1.1-1.2) |
| T_in, RH_in | C, % | air the person is in when at home (living room by day, bedroom in bed; 23 C/50 % during AC respite); outdoors = T_out |
| T_out | C | outdoor air (synthetic Athens summer) |
| location | 0 home, 1 transit, 2 out | |
| activity_class | 0 sleep, 1 lying, 2 sit, 3 stand, 4 adl, 5 walk | |
| asleep, fan, sun_on_lid | 0/1 | |
| clo | clo | clothing |
| drink_mL | mL in that minute | |
| worn_truth | 0 off, 1 loose, 2 worn | |

## Sensor columns (what the band would see; R2 §6)
T1, T2 (TMP117 skin side / reference, C, quantised 0.0078 C), T_air_meas, RH_meas (SHTC3), HR_meas (bpm, **NaN = no reading**),
hr_quality (0 no skin, 1 low PI, 2 motion, 3 irregular, 4 OK), PI (%, NaN when off), a_std_g (1-min SD of |a|, g),
zangle_deg, flux_valid_truth (1 if worn, >= 20 min since donning, T1-T2 > 0.15 and T_air < T1 - 0.5, noise-free).
Sensor NaNs occur only in HR_meas and PI (intended "no reading").

## Labels
ev38_30 / ev385_30: max T_core over (t, t+30] >= 38.0 / 38.5 C. strain_psi: Moran PSI 0-10 from truth.

## Events
core38 / core385 (runs of T_core above threshold), hr_drift_onset (drift term > 5 bpm), core_inflection (15-min slope > plateau
slope + 0.1 C/h for >= 30 min with core > 37.3), anomaly (S9 ground truth), loose, off, shower, errand, nap, fan, ac_respite, heatwave_day.

## ppg_1hz columns
person_id, t_min, sec (0..59), ir_dc (counts; < 20000 when off), ir_ac (counts, = ir_dc x PI/100), motion_g, beat (beats in that second), worn_truth.

## Known limits (see VALIDATION.md)
No day-2 core escalation (V27 fails: set-point model, heat-debt term forbidden); dT can exceed 0.6 C at 34-36 C rooms (R2 conflict);
HR-drift lead inside 2-6 RH points for ~50 % of persons (V19); rest-limit too tolerant (V13/V15); frailty axis unvalidated by construction;
medication effects are young-adult literature priors.
"""


def write_readme(out):
    with open(os.path.join(out, "README.md"), "w") as f:
        f.write(README)
