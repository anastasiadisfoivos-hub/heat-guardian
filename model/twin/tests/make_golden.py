"""Golden nights for the C == Python check (ARCHITECTURE 5 test 4).

Writes an event stream (minutes, phone readings, room readings, nightly updates) and the Python reference's
parameters after every nightly update:
  twin/tests/golden_nights.parquet     events (all columns, float32)
  twin/tests/golden_expected.parquet   per update: changed, frozen code, 30 params, t1_n[24], t1_pre_cd[24]
  twin/tests/golden_events.csv / golden_expected.csv / golden_final.hex   same, for host_test.c

--source crafted (default): 10 crafted 24-h days (03:30 -> 03:30) covering every rule and every freeze reason.
--source sim: 10 nights from SIM-DEV persons in sim/data/minutes_dev.parquet (never sealed ids; asserted).
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/claude/hg_ai/twin")
from hg_twin import BodyTwin  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
f = np.float32
MCOLS = ["t1_c", "t2_c", "t_air_c", "rh_pct", "hr_bpm", "hr_quality", "pi_pct", "a_std_g", "worn",
         "minute_of_day", "asleep", "location", "hr_valid", "tier_on", "air_ref"]
COLS = ["kind"] + MCOLS + ["r0", "r1", "r2", "r3", "r4"]


def crafted_days(seed=20261112):
    """10 crafted days. Each day = 1440 minutes from 03:30, then one update. Day features:
    d0 normal; d1 + oral reading (flux valid); d2 + errand OUT walking with air_ref; d3 alarm at night (frozen);
    d4 band off 40 % of the night (frozen); d5 + room reading + reading without flux; d6 hot night T_air 29
    (baseline not learned at night); d7 time unknown all day (no night -> frozen); d8 NaN/inf garbage minutes;
    d9 very low HR night (bounds) + histogram saturation (long flat HR)."""
    rng = np.random.default_rng(seed)
    ev = []
    rest = 62.0
    for d in range(10):
        for i in range(1440):
            tod = (210 + i) % 1440
            asleep = 1 if (tod >= 1380 or tod < 420) else 0
            worn = 2
            tier = 0
            loc = 0
            air_ref = np.nan
            tair = 25.0 + 2.0 * np.sin(2 * np.pi * (tod - 900) / 1440) + rng.normal(0, 0.1)
            if d == 6 and asleep:
                tair = 29.0 + rng.normal(0, 0.2)
            astd = 0.001 if asleep else (0.03 if rng.random() < 0.3 else 0.0015)
            t1 = 33.5 + (0.6 if asleep else 0.0) + 0.1 * np.sin(tod / 90.0) + rng.normal(0, 0.05)
            hr = (rest - 6 if asleep else rest + 8) + rng.normal(0, 3)
            if d == 9 and asleep:
                hr = 41.2 + (0.0 if i % 7 else 0.5)
            if rng.random() < 0.2:
                hr = np.nan if rng.random() < 0.5 else hr + rng.uniform(-30, 15)
            hrq = 4 if np.isfinite(hr) else 0
            hr_valid = 1 if hrq == 4 else 0
            if d == 2 and 600 <= tod < 660:
                loc, astd, air_ref = 2, 0.05, 33.0
                tair = 33.0 + 0.2 * (t1 - 33.0) + rng.normal(0, 0.1)
            if d == 3 and 60 <= tod < 75:
                tier = 1
            if d == 4 and (tod >= 1380 or tod < 300) and tod % 3 != 0:
                worn = 0 if tod % 2 else 1
            if d == 7:
                tod = 0xFFFF
                asleep = 0
            t2 = t1 - (2.5 + rng.normal(0, 0.05))
            row = dict(kind="m", t1_c=t1, t2_c=t2, t_air_c=tair, rh_pct=45.0, hr_bpm=hr, hr_quality=hrq, pi_pct=0.8,
                       a_std_g=astd, worn=worn, minute_of_day=tod, asleep=asleep, location=loc, hr_valid=hr_valid,
                       tier_on=tier, air_ref=air_ref)
            if d == 8 and 1000 <= i < 1400:      # stuck clock at 03:20 (T3 F2): 400 qualifying minutes in one hour
                row.update(minute_of_day=200, t1_c=33.0 + rng.normal(0, 0.05), t_air_c=24.0, a_std_g=0.001, worn=2)
            elif d == 8 and i % 11 == 0:
                bad = [np.nan, np.inf, -np.inf, 1e30, -1e30]
                for c in ("t1_c", "t_air_c", "hr_bpm", "a_std_g", "air_ref"):
                    row[c] = bad[rng.integers(len(bad))]
                row["worn"] = int(rng.integers(0, 256)); row["asleep"] = int(rng.integers(0, 256))
                row["minute_of_day"] = int(rng.integers(0, 65536))
            ev.append(row)
            if d == 1 and tod == 570:
                ev.append(dict(kind="r", r0=37.05, r1=33.6, r2=2.4, r3=36.9, r4=1))   # k_obs 1.44 -> clamps at the bound
            if d == 0 and tod == 560:
                ev.append(dict(kind="r", r0=36.4, r1=35.4, r2=4.0, r3=36.3, r4=1))    # k_obs 0.25 -> K 0.185 interior (T3 F6)
            if d == 6 and tod == 600:
                ev.append(dict(kind="r", r0=36.7, r1=35.6, r2=3.0, r3=36.6, r4=1))    # interior from the bound
            if d == 5 and tod == 600:
                ev.append(dict(kind="q", r0=24.6, r1=25.4, r2=33.4))
                ev.append(dict(kind="r", r0=36.6, r1=33.5, r2=np.nan, r3=36.95, r4=0))
            if d == 9 and tod == 540:
                ev.append(dict(kind="r", r0=39.9, r1=30.0, r2=0.51, r3=34.2, r4=1))  # extreme -> clamps
        ev.append(dict(kind="u"))
    return ev


def sim_days(n_nights=10, minutes=None):
    """10 nights from SIM-DEV persons: one 24-h block (day 1 03:30 -> day 2 03:30) from each of the first 10 DEV
    persons. Band-side flags from simulator truth (worn_truth, asleep, location); hr_valid = OK in >= 3 of 5 min."""
    from sim_io import DevMinutes, sealed_sim_ids  # refuses to run without the seal
    sealed = sealed_sim_ids()
    dm = DevMinutes(["person_id", "day", "minute_of_day", "T1", "T2", "T_air_meas", "RH_meas", "HR_meas", "hr_quality",
                     "PI", "a_std_g", "worn_truth", "asleep", "location"], path=minutes)
    ids = [p for p in dm.persons() if p not in sealed][:n_nights]
    assert not set(ids) & sealed
    ev = []
    for pid in ids:
        m = dm.person(pid)
        days = sorted(m.day.unique())
        m = m[((m.day == days[1]) & (m.minute_of_day >= 210)) | ((m.day == days[2]) & (m.minute_of_day < 210))]
        q = (m.hr_quality.values == 4).astype(int)
        hv = (np.convolve(q, np.ones(5, int))[:len(q)] >= 3).astype(int)
        for k, r in enumerate(m.itertuples(index=False)):
            hr = r.HR_meas if r.hr_quality == 4 else np.nan
            ev.append(dict(kind="m", t1_c=r.T1, t2_c=r.T2, t_air_c=r.T_air_meas, rh_pct=r.RH_meas, hr_bpm=hr,
                           hr_quality=int(r.hr_quality), pi_pct=r.PI, a_std_g=r.a_std_g, worn=int(r.worn_truth),
                           minute_of_day=int(r.minute_of_day), asleep=int(r.asleep), location=int(r.location),
                           hr_valid=int(hv[k]), tier_on=0, air_ref=np.nan))
        ev.append(dict(kind="u"))
    return ev


def run(ev, k_rule=0, reading_mode=0):
    tw = BodyTwin(k_rule=k_rule, reading_mode=reading_mode)
    exp = []
    for e in ev:
        k = e["kind"]
        if k == "m":
            tw.ingest_minute({c: e[c] for c in MCOLS})
        elif k == "r":
            tw.ingest_reading(e["r0"], 0, e["r1"], e["r2"], e["r3"], int(e["r4"]))
            tw.commit_reading()
        elif k == "q":
            tw.ingest_room_reading(e["r0"], e["r1"], e["r2"])
        elif k == "u":
            ch = tw.nightly_update()
            exp.append([tw.changed_flag(ch), tw.last_frozen] + tw.params_vector() +
                       [int(x) for x in tw.t1_n] + [int(x) for x in tw.t1_pre_cd])
    return tw, exp


def to_frame(ev):
    df = pd.DataFrame(ev).reindex(columns=COLS)
    for c in COLS[1:]:
        if c in ("worn", "minute_of_day", "asleep", "location", "hr_valid", "tier_on", "hr_quality"):
            df[c] = df[c].fillna(0).astype(np.int64)
        else:
            df[c] = df[c].astype(np.float32)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="crafted", choices=["crafted", "sim"])
    ap.add_argument("--minutes", default="/home/claude/hg_ai/sim/data/minutes_dev.parquet")
    ap.add_argument("--k-rule", type=int, default=0, help="0 spec, 1 K_eff (bound 1.5), 2 K off (C: -DHG_TWIN_K_RULE)")
    ap.add_argument("--reading-mode", type=int, default=0, help="0 display-only (default), 1 sourced (C: -DHG_TWIN_READING_MODE)")
    ap.add_argument("--prefix", default="golden", help="output file prefix (golden = crafted set used by host_test)")
    a = ap.parse_args()
    ev = crafted_days() if a.source == "crafted" else sim_days(minutes=a.minutes)
    df = to_frame(ev)
    # replay from the float32 frame so Python sees exactly what C sees
    ev32 = df.to_dict("records")
    tw, exp = run(ev32, a.k_rule, a.reading_mode)
    pcols = ["changed", "frozen", "rest_hr", "k_person", "core_offset", "c_bodyheat"] + \
        [f"t1_base_{h}" for h in range(24)] + ["days_learned"] + [f"t1_n_{h}" for h in range(24)] + [f"t1_pre_{h}" for h in range(24)]
    ex = pd.DataFrame(exp, columns=pcols)
    df.to_parquet(os.path.join(HERE, f"{a.prefix}_nights.parquet"))
    ex.to_parquet(os.path.join(HERE, f"{a.prefix}_expected.parquet"))
    with open(os.path.join(HERE, f"{a.prefix}_events.csv"), "w") as fh:
        for r in df.itertuples(index=False):
            vals = []
            for c, v in zip(COLS[1:], r[1:]):
                if isinstance(v, (float, np.floating)):
                    vals.append(repr(float(v)) if np.isfinite(v) else ("nan" if np.isnan(v) else ("inf" if v > 0 else "-inf")))
                else:
                    vals.append(str(int(v)))
            fh.write(r.kind + "," + ",".join(vals) + "\n")
    with open(os.path.join(HERE, f"{a.prefix}_expected.csv"), "w") as fh:
        for row in exp:
            fh.write(",".join("nan" if (isinstance(v, float) and np.isnan(v)) else repr(v) for v in row) + "\n")
    rout = bytes(range(256)) * 2 + bytes(112)    # 624-B stand-in routine blob (576 + 48 B, ARCHITECTURE 7.1)
    tw.set_calm(37.21, 4)                          # Guardian calm block (M9.5) exercised in the byte comparison
    tw.set_exc(1234.5, -56.25)                     # B5-v7: Guardian Exception block (v4) exercised in the byte comparison
    blob = tw.to_bytes(rout, save_count=10)
    open(os.path.join(HERE, f"{a.prefix}_final.hex"), "w").write(blob.hex() + "\n")
    print(f"source={a.source} events={len(df)} updates={len(exp)} file={len(blob)} B")
    print(ex[["changed", "frozen", "rest_hr", "k_person", "core_offset", "c_bodyheat", "days_learned"]].to_string())


if __name__ == "__main__":
    main()
