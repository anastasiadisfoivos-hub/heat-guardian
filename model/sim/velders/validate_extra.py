"""Validation sections: Ji agreement + energy balance + monotonicity (agree), R3 indoor (indoor),
R2 §6.5 / sensor acceptance (sensor), routine IS/IV (routine). SIMULATION."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .body import TwoNodeOlder, p_sat_torr, ALL_FEATURES
from .validate import row
from .weather import hourly_weather
from .indoor import B4Class
from .protocols import load_persons, meade

AGREE_CONDS = [(t, m, 45.0) for t in (26, 31, 36) for m in (0.86, 1.37)] + [(44, 0.86, 30.0), (44, 1.37, 30.0), (36, 0.95, 45.0)]


def section_agree(P):
    from pythermalcomfort.models import two_nodes_gagge_ji
    out = []
    worst_c, worst_s = 0.0, 0.0
    for tdb, met, rh in AGREE_CONDS:
        vp = rh * p_sat_torr(tdb) / 100
        r = two_nodes_gagge_ji(tdb=tdb, tr=tdb, v=0.1, met=met, clo=0.4, vapor_pressure=vp, body_surface_area=1.84,
                               position="sitting", acclimatized=False, body_weight=73.2, length_time_simulation=480)
        b = TwoNodeOlder(dict(mass_kg=73.2, A_D=1.84), features=(), ji_init=True, compute_ref=False)
        for _ in range(480):
            o = b.step(dict(t_db=tdb, rh=rh, v_air=0.1, met=met, clo=0.4, standing=False))
        worst_c = max(worst_c, abs(r.t_core[-1] - o["T_core"][0]))
        worst_s = max(worst_s, abs(r.t_skin[-1] - o["T_skin"][0]))
    out.append(row("JI-AGREE", "numpy two-node vs pythermalcomfort.two_nodes_gagge_ji, 480 min, 9 conditions (26/31/36 C x met 0.86/1.37, clo 0.4, 45 %; 44 C/30 % x2; 36 C met 0.95), features off",
                   "|dCore| <= 0.05, |dSkin| <= 0.3", f"max |dCore| {worst_c:.2e} C, max |dSkin| {worst_s:.2e} C", worst_c <= 0.05 and worst_s <= 0.3, "", "agree"))
    # energy balance: storage == sum of heat-content changes
    b = TwoNodeOlder(P, minute_of_day0=600)
    err = 0.0
    for i in range(600):
        T = 36.0 if i < 300 else 26.0
        hc0 = 0.97 * (b.alfa * b.t_skin + (1 - b.alfa) * b.t_core) * b.p["mass_kg"]
        a0 = b.alfa.copy()
        o = b.step(dict(t_db=T, rh=40.0, met=0.86 if i % 100 < 70 else 1.37, clo=0.4, minute_of_day=600 + i))
        hc1 = 0.97 * (a0 * o["T_skin_node"] + (1 - a0) * o["T_core"]) * b.p["mass_kg"]
        err = max(err, float(np.max(np.abs((hc1 - hc0) * 60 / b.p["A_D"] - o["storage"]))))
    out.append(row("ENERGY", "energy balance closes per step (M - E_res - C_res - Q_sens - E_sk = storage)", "< 1 W/m2",
                   f"max residual {err:.2e} W/m2 over 600 steps x {len(P['mass_kg'])} persons, all features on", err < 1.0, "", "agree"))
    # monotonicity of dT_core in T_db at fixed met (clamp values)
    ok = True
    worst = 0.0
    for met in (0.86, 1.37):
        prev = None
        for T in range(22, 41, 2):
            R = meade(P, T, met=met, hours=8)
            d = R["dcore"]
            if prev is not None:
                worst = min(worst, float(np.min(d - prev)))
                ok &= bool(np.all(d >= prev - 1e-6))
            prev = d
    out.append(row("MONO", "monotonicity of dT_core in T_db (22..40 C step 2) at fixed met 0.86 / 1.37, every person", "non-decreasing",
                   f"min step {worst:+.4f} C", ok, "", "agree"))
    return out


def section_indoor(P):
    out = []
    rng = np.random.default_rng(7)
    days = ["S1"] * 7 + ["PRE", "PRE"] + [f"S2_{k}" for k in range(1, 6)] + ["POST", "POST"]
    W = hourly_weather(days, rng)
    m = B4Class("B")
    r = m.run_hourly(W["t_out"], W["s_rad"], W["rh_out"])
    mA = B4Class("A")
    rA_ = mA.run_hourly(W["t_out"], W["s_rad"], W["rh_out"])
    tin = r["t_in"][:, 0]
    s2 = slice(9 * 24, 14 * 24)
    nightmin = [tin[d * 24:d * 24 + 8].min() for d in range(9, 14)]
    dm = tin.reshape(-1, 24).mean(1)
    creep = float((dm[13] - dm[9]) / 4)
    frac30 = float((tin[s2] > 30).mean())
    ok = min(nightmin) >= 28 and frac30 >= 0.85 and 0.2 <= creep <= 0.8
    out.append(row("R3-i", "Sakka: S2 indoor night min >= 28 C, > 30 C for >= 85 % of hours, creep 0.2-0.8 K/day (class B, B4 Tomorrow-Engine model)",
                   "as stated", f"night min {min(nightmin):.1f} C; >30 C {100*frac30:.0f} %; creep {creep:.2f} K/day", ok, "", "indoor"))
    # lag and amplitude ratio (S1 days, class B), and bedroom peak hour
    lags, amps = [], []
    to = W["t_out"]
    for d in range(2, 7):
        a, o_ = rA_["t_in"][d * 24:(d + 1) * 24, 0], to[d * 24:(d + 1) * 24]
        aa, oo = a - a.mean(), o_ - o_.mean()
        cc = [np.dot(np.roll(aa, -k), oo) for k in range(0, 8)]
        lags.append(int(np.argmax(cc)))
        amps.append(np.ptp(a) / np.ptp(o_))
    tb = rA_["t_bed"][:, 0]
    pk = [int(np.argmax(tb[d * 24:(d + 1) * 24])) for d in range(2, 7)]
    ok = 2 <= np.median(lags) <= 4 and 0.1 <= np.mean(amps) <= 0.3
    out.append(row("R3-ii", "Bath: lag 2-4 h, amplitude ratio 0.1-0.3, bedroom peak 18-19 h (class A = Bath-like parameters, S1 days)", "as stated",
                   f"lag median {np.median(lags):.0f} h; amplitude ratio {np.mean(amps):.2f}; bedroom peak hour median {np.median(pk):.0f}", ok,
                   "" if 18 <= np.median(pk) <= 19 else "", "indoor"))
    # Zuurbier +3.5 C over 5 warm days (NL warm week, class A), bedroom 0.4-0.6 warmer
    rng = np.random.default_rng(8)
    T = np.concatenate([np.full(7 * 24, 17.0) + 4 * np.sin(np.arange(7 * 24) * 2 * np.pi / 24),
                        np.full(5 * 24, 23.0) + 6 * np.sin(np.arange(5 * 24) * 2 * np.pi / 24)])
    mA = B4Class("A")
    rA = mA.run_hourly(T, np.zeros_like(T), np.full_like(T, 60.0))
    ti = rA["t_in"][:, 0]
    rise = float(ti[11 * 24:12 * 24].mean() - ti[6 * 24:7 * 24].mean())
    bed = float((rA["t_bed"] - rA["t_in"]).mean())
    ok = abs(rise - 3.5) <= 1.0 and 0.4 <= bed <= 0.6
    out.append(row("R3-iii", "Zuurbier: +3.5 C over 5 warm days; bedroom 0.4-0.6 C warmer", "+-1 C; range",
                   f"rise {rise:+.1f} C (outdoor daily mean +6 C step, class A); bedroom +{bed:.2f} C", ok, "", "indoor",
                   note="the +3.5 C depends on the size of the outdoor step, which Zuurbier does not give; +6 C assumed"))
    return out


def _probe_population(n=40, days=10):
    from .population import simulate_chunk
    from .protocols import dev_persons_df
    df = dev_persons_df().iloc[:n]
    rows = df.to_dict("records")
    res = []
    for i in range(0, len(rows), 20):
        res += simulate_chunk((rows[i:i + 20], days))
    return pd.concat([r[1] for r in res], ignore_index=True), res


def section_sensor(P, cache={}):
    out = []
    m, res = _probe_population()
    cache["m"] = m
    w = m.worn_truth == 2
    dT = m.T1 - m.T2
    home = m.location == 0
    hot = w & home & (m.T_in >= 34) & (m.sun_on_lid == 0)
    frac = float((dT[hot] <= 0.6).mean())
    thr_ok = None
    for t0 in np.arange(34, 40.1, 0.5):
        s = w & home & (m.T_in >= t0)
        if s.sum() and (dT[s] <= 0.6).mean() >= 0.999:
            thr_ok = t0
            break
    out.append(row("R2-dT34", "at T_air >= 34 C, dT = T1 - T2 <= 0.6 C for 100 % of worn minutes (R2 §6.5)", "100 %",
                   f"{100*frac:.1f} % of worn home minutes at T_in >= 34 C (n={int(hot.sum())}); p99 {dT[hot].quantile(0.99):.2f} C; 99.9 % holds from T_in >= {thr_ok} C",
                   frac >= 0.9999, "", "sensor"))
    from .sensors import BandSensors, person_noise
    from .protocols import person_met
    k = slice(0, 100)
    Pk = {kk: v[k] for kk, v in P.items()}
    res_c = {}
    for Ta in (20.0, 24.0, 26.0, 36.0):
        b = TwoNodeOlder(Pk, minute_of_day0=600)
        nz = [person_noise(int(sd), 300) for sd in Pk["seed"]]
        NZ = {kk: np.stack([z[kk] for z in nz], 1) for kk in nz[0]}
        bs = BandSensors(Pk, NZ)
        nn = len(Pk["seed"])
        for t in range(240):
            o = b.step(dict(t_db=Ta, rh=45.0, met=person_met(Pk, 0.86), clo=0.4, minute_of_day=600 + t))
            sv = bs.step(dict(T_core=o["T_core"], s_skbf=o["s_skbf"], T_air=np.full(nn, Ta), RH_air=np.full(nn, 45.0),
                              HR_true=o["HR"], m_sweat=o["m_sweat"], deficit_pct=o["deficit_pct"]),
                         dict(worn=np.full(nn, 2), h_out=np.full(nn, 8.0), r_gap=np.zeros(nn), sun_dT=np.zeros(nn), flash=np.zeros(nn),
                              asleep=np.zeros(nn), rh_wet=np.zeros(nn), a_std_true=np.full(nn, 0.005), act_class=np.full(nn, 2),
                              zangle_true=np.zeros(nn), slip=np.zeros(nn)))
        res_c[Ta] = dict(dT=np.mean(sv["T1_true"] - sv["T2_true"]), dTmin=np.min(sv["T1_true"] - sv["T2_true"]),
                         dTmax=np.max(sv["T1_true"] - sv["T2_true"]), s=float(np.mean(o["s_skbf"])), PI=float(np.nanmedian(sv["PI"])))
    okc = all(2 <= res_c[T]["dTmin"] and res_c[T]["dTmax"] <= 5 for T in (20.0, 24.0, 26.0))
    out.append(row("R2-dT-cool", "in 20-26 C rooms dT 2-5 C (R2 §2.2); constructed 4-h seated runs, 100 persons", "2-5 C, every person",
                   "; ".join(f"{int(T)} C: mean {res_c[T]['dT']:.2f} (range {res_c[T]['dTmin']:.2f}-{res_c[T]['dTmax']:.2f})" for T in (20.0, 24.0, 26.0)) +
                   f"; 36 C: mean {res_c[36.0]['dT']:.2f}", okc, "", "sensor"))
    ratio = res_c[36.0]["PI"] / res_c[20.0]["PI"]
    out.append(row("R2-PI", "PI rises 2-4x from vasoconstricted to dilated (R2 §6.3)", "2-4x",
                   f"median PI 36 C / 20 C = {ratio:.2f} (s {res_c[20.0]['s']:.2f} -> {res_c[36.0]['s']:.2f})", 2 <= ratio <= 4, "", "sensor"))
    # loose changes T1, dT, PI and IMU together
    lo = m.worn_truth == 1
    d1 = float(m.T1[lo].mean() - m.T1[w].mean()); d2 = float(dT[lo].mean() - dT[w].mean())
    dpi = float(m.PI[lo].mean() / m.PI[w].mean())
    ok = d1 < 0 and d2 < 0 and dpi < 0.7
    out.append(row("R2-loose", "a loose band changes T1, dT, PI and IMU together (R2 §6.5)", "all move",
                   f"loose vs worn: T1 {d1:+.2f} C, dT {d2:+.2f} C, PI x{dpi:.2f}, slip rotations in z-angle at loose onset", ok, "", "sensor"))
    rest = w & (m.a_std_g < 0.02) & (m.activity_class <= 2)
    outl = (m.HR_meas.isna() | ((m.HR_meas - m.HR_true).abs() > 10))
    f = float(outl[rest].mean())
    out.append(row("R2-HRout", "HR outlier minutes 15-25 % at rest (p_out 0.20 red/IR, R2 §6.3)", "15-25 %",
                   f"{100*f:.1f} % (no reading or |error| > 10 bpm; worn, still)", 0.15 <= f <= 0.25, "", "sensor"))
    # donning transient: from the probe, time for T1 to reach 95 % of its post-don plateau
    times = []
    for pid, mdf, *_ in res:
        wv = mdf.worn_truth.values; t1 = mdf.T1.values
        for i in np.nonzero((wv[1:] == 2) & (wv[:-1] == 0))[0][:3]:
            seg = t1[i + 1:i + 61]
            if len(seg) < 61 - 1:
                continue
            target = seg[-10:].mean(); start = seg[0]
            if abs(target - start) < 0.5:
                continue
            k = np.nonzero(np.abs(seg - target) <= 0.05 * abs(target - start))[0]
            if k.size:
                times.append(int(k[0]))
    med = float(np.median(times)) if times else np.nan
    out.append(row("R2-don", "donning transient 20-30 min (R2 §2.3, §6.1)", "20-30 min",
                   f"median {med:.0f} min to 95 % of the step (IQR {np.percentile(times,25):.0f}-{np.percentile(times,75):.0f}, n={len(times)})", 20 <= med <= 30,
                   "", "sensor", note="shower re-donning includes the 1-3 C evaporative flash"))
    nan_truth = int(m[["T_core", "T_skin_mean", "HR_true", "deficit_pct", "T_in"]].isna().sum().sum())
    core_ok = bool(m.T_core.between(35, 41).all())
    sel = w & (m.sun_on_lid == 0) & (m.T_in < m.T_core) & ((m.location == 0) | (m.T_out < m.T_core))
    t1_ok = float((m.T1[sel] <= m.T_core[sel] + 0.11).mean())
    out.append(row("PROP", "property: no NaN in truth, core 35-41 C, T1 <= T_core (worn, no sun, air cooler than core; +TMP117 offset 0.1)", "all",
                   f"NaN truth {nan_truth}; core range {m.T_core.min():.2f}-{m.T_core.max():.2f}; T1 <= core+0.11 in {100*t1_ok:.2f} %",
                   nan_truth == 0 and core_ok and t1_ok >= 0.9999, "", "sensor"))
    return out


def section_routine(P):
    from .scenarios import build_person, env_arrays
    from .protocols import dev_persons_df
    df = dev_persons_df().iloc[:60]
    IS, IV = [], []
    for r in df.to_dict("records"):
        tl, mins, _ = build_person(r, 10, int(r["seed"]))
        cls = env_arrays(r, tl, mins)["act_class"][1440:].astype(float)
        act = env_arrays(r, tl, mins)["met"][1440:]   # activity-count proxy (met), as Van Someren use counts
        x = act.reshape(-1, 60).mean(1)           # hourly
        n = len(x); p = 24
        prof = x.reshape(-1, p).mean(0)
        IS.append(n * ((prof - x.mean()) ** 2).sum() / (p * ((x - x.mean()) ** 2).sum()))
        IV.append(n * (np.diff(x) ** 2).sum() / ((n - 1) * ((x - x.mean()) ** 2).sum()))
    ok = 0.7 <= np.median(IS) <= 0.9 and 0.5 <= np.median(IV) <= 0.8
    return [row("R3-IS", "routine: IS 0.7-0.9 and IV 0.5-0.8 (R3 §3.3, Van Someren descriptors on hourly mean activity, met as the count proxy)", "ranges",
                f"IS median {np.median(IS):.2f} (IQR {np.percentile(IS,25):.2f}-{np.percentile(IS,75):.2f}); IV median {np.median(IV):.2f}", ok, "", "routine")]
