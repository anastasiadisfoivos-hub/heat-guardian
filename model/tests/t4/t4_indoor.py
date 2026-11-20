"""T4 — indoor model sanity vs R3 §1.6 (i)-(iii), with MY OWN re-implementation of the R3 equations
(explicit Euler, exactly as printed in R3 §1.6) and my own lag/ratio code on the real Bath series.

Run: python3 /home/claude/hg_ai/tests/t4/t4_indoor.py   -> prints JSON, writes out/indoor.json
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/claude/hg_ai")
from tomorrow import indoor, demo  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BATH = "/home/claude/hgdata/raw/22_bath_elderly_homes/ExternalWeatherSummer.csv"


def r3_euler(t_out, S, p, t_slow0):
    """R3 §1.6 verbatim: T_slow[t+1] = T_slow + (1/tau_s)(T_out + dT - T_slow);
    T_fast[t+1] = T_fast + (1/tau_f)(g_f (T_out - T_slow + dT) + g_sun S/100 - T_fast)."""
    ts, tf = t_slow0, 0.0
    out = np.empty(len(t_out))
    for i, (to, s) in enumerate(zip(t_out, S)):
        out[i] = ts + tf
        ts_n = ts + (to + p.dT_home - ts) / p.tau_s
        tf_n = tf + (p.g_f * (to - ts + p.dT_home) + p.g_sun * s / 100.0 - tf) / p.tau_f
        ts, tf = ts_n, tf_n
    return out


def series(days):
    t = np.concatenate([demo._temp_profile(a, b) for a, b in days])
    return t, np.tile(demo._shortwave(), len(days))


def wave_metrics(ti, nd):
    ti = ti[-nd * 24:]
    d = ti.reshape(nd, 24)
    return {"night_min_00_07": [round(float(x), 2) for x in d[:, :8].min(1)],
            "daily_mean": [round(float(x), 2) for x in d.mean(1)],
            "daily_max": [round(float(x), 2) for x in d.max(1)],
            "frac_gt30": round(float((ti > 30).mean()), 3),
            "creep_daily_mean_K_per_day": [round(float(x), 2) for x in np.diff(d.mean(1))]}


def my_lag_ratio(tin, tout):
    """Lag: argmax over 0..12 h of Pearson r between de-trended outdoor(t-l) and indoor(t); anomalies =
    value minus centred 24-h moving average (numpy convolution, not pandas). Ratio: mean daily range ratio."""
    k = np.ones(24) / 24
    def anom(x):
        m = np.convolve(x, k, mode="same")
        a = x - m
        a[:12] = np.nan; a[-12:] = np.nan
        return a
    ai, ao = anom(tin), anom(tout)
    best, lag = -2, None
    for l in range(13):
        x = ai[l:]; y = ao[:len(ao) - l]
        ok = ~(np.isnan(x) | np.isnan(y))
        r = np.corrcoef(x[ok], y[ok])[0, 1]
        if r > best:
            best, lag = r, l
    nd = len(tin) // 24
    A = tin[:nd * 24].reshape(nd, 24); B = tout[:nd * 24].reshape(nd, 24)
    return lag, float(np.mean(np.ptp(A, 1)) / np.mean(np.ptp(B, 1)))


def bath_longest_run():
    rows = [l.strip().lstrip("﻿").split(",") for l in open(BATH, encoding="utf-8")]
    t = pd.to_datetime([r[0] for r in rows], utc=True)
    v = np.array([float(r[1]) for r in rows])
    s = pd.Series(v, index=t).sort_index()
    s = s[~s.index.duplicated()]
    full = s.reindex(pd.date_range(s.index[0], s.index[-1], freq="h"))
    isn = full.isna().to_numpy()
    best, cur, st = (0, 0), None, None
    for i, x in enumerate(np.r_[isn, True]):
        if not x and st is None:
            st = i
        if x and st is not None:
            if i - st > best[1] - best[0]:
                best = (st, i)
            st = None
    return full.to_numpy()[best[0]:best[1]], best[1] - best[0]


def main():
    R = {}
    # --- (i) S2 week: Tmin 27 / Tmax 40, 5 days, preceded by 4 ordinary S1 days (23/32) -------------
    t, S = series([(23, 32)] * 4 + [(27, 40)] * 5)
    for cls in "ABCD":
        p = indoor.CLASSES[cls]
        t0 = float(np.mean(t[:24]) + p.dT_home)
        b = indoor.simulate(t, S, home_class=cls)["t_in"]
        e = r3_euler(t, S, p, t0)
        R["S2_after_S1_" + cls] = {"builder": wave_metrics(b, 5), "r3_euler": wave_metrics(e, 5),
                                   "max_abs_diff_builder_vs_r3_euler": round(float(np.abs(b - e).max()), 2)}
    # C - B on several statistics (brief: "class C is 1.5-2.5 degC above class B")
    b, c = R["S2_after_S1_B"]["builder"], R["S2_after_S1_C"]["builder"]
    R["C_minus_B"] = {k: [round(x - y, 2) for x, y in zip(c[k], b[k])] for k in ("night_min_00_07", "daily_mean", "daily_max")}
    # --- the plan path: make_plan feeds the forecast from its first hour with t_slow0 = equilibrium of day 1
    t2, S2 = series([(27, 40)] * 5)
    for cls in "BC":
        b2 = indoor.simulate(t2, S2, home_class=cls)["t_in"]
        R["S2_cold_start_equilibrium_" + cls] = wave_metrics(b2, 5)
    # --- the demo exactly as plan.make_plan sees it (4 x 28/41 days), class B and C
    fc = demo.demo_forecast()
    H = fc.hourly
    for cls in "BCD":
        r = indoor.simulate(H["temperature_2m"].to_numpy(), H["shortwave_radiation"].to_numpy(), home_class=cls)
        R["demo_" + cls] = wave_metrics(r["t_in"][:96], 4)
    # demo with a realistic spin-up: 7 ordinary days 23/32 then the 4 hot days
    t3, S3 = series([(23, 32)] * 7 + [(28, 41)] * 4)
    R["demo_after_7_S1_days_B"] = wave_metrics(indoor.simulate(t3, S3, home_class="B")["t_in"], 4)
    # equilibrium arithmetic for the steady demo: mean T_out + dT_home
    R["demo_outdoor_daily_mean"] = round(float(H["temperature_2m"].to_numpy()[:24].mean()), 2)
    # --- (ii) Bath class A, real external series ------------------------------------------------------
    o, n = bath_longest_run()
    a = indoor.simulate(o, home_class="A")["t_in"]
    lag, ratio = my_lag_ratio(a[48:], o[48:])
    R["bath_A"] = {"hours": int(n), "lag_h": lag, "ratio": round(ratio, 3)}
    # sensitivity: does the R3 Euler form also pass?
    pA = indoor.CLASSES["A"]
    e = r3_euler(o, np.zeros(len(o)), pA, float(o[:24].mean() + pA.dT_home))
    lag2, ratio2 = my_lag_ratio(e[48:], o[48:])
    R["bath_A_r3_euler"] = {"lag_h": lag2, "ratio": round(ratio2, 3)}
    # --- (iii) Zuurbier: +3.5 degC over the first 5 days of a warm week (class B, 18/26 -> 24/34) ----------
    t4, S4 = series([(16, 24)] * 10 + [(22, 32)] * 5)
    for cls in "AB":
        z = indoor.simulate(t4, S4, home_class=cls, t_slow0=float(np.mean(t4[:24]) + indoor.CLASSES[cls].dT_home))["t_in"]
        R["zuurbier_5day_rise_" + cls] = round(float(z[14 * 24:15 * 24].mean() - z[9 * 24:10 * 24].mean()), 2)
    # --- RH sanity: indoor RH at demo peak
    r = indoor.simulate(H["temperature_2m"].to_numpy(), H["shortwave_radiation"].to_numpy(),
                        H["relative_humidity_2m"].to_numpy(), home_class="B")
    R["demo_B_rh_in_range"] = [round(float(r["rh_in"][72:96].min()), 1), round(float(r["rh_in"][72:96].max()), 1)]
    # --- nonsense inputs
    for name, arr in {"nan_in_tout": np.r_[np.full(10, 30.0), np.nan, np.full(13, 30.0)],
                      "minus40": np.full(24, -40.0), "plus60": np.full(24, 60.0), "empty": np.array([])}.items():
        try:
            x = indoor.simulate(arr, home_class="B")["t_in"]
            R["nonsense_" + name] = "ok, nan=%d, range %s" % (int(np.isnan(x).sum()),
                                                             (round(float(np.nanmin(x)), 1), round(float(np.nanmax(x)), 1)) if len(x) and not np.isnan(x).all() else None)
        except Exception as ex:
            R["nonsense_" + name] = "raises %s: %s" % (type(ex).__name__, str(ex)[:60])
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    json.dump(R, open(os.path.join(HERE, "out", "indoor.json"), "w"), indent=1)
    print(json.dumps(R, indent=1))


if __name__ == "__main__":
    main()
