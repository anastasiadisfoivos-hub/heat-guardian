"""B1 unit/property tests (ARCHITECTURE §9 row B1). SIMULATION. Run: cd /home/claude/hg_ai/sim && python3 -m pytest -q tests"""
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from velders.body import TwoNodeOlder, p_sat_torr, MET_CLAMP
from velders.protocols import load_persons, meade, person_met
from velders.sensors import BandSensors, person_noise

PERSONS = "/home/claude/hg_ai/sim/data/persons.parquet"
SEALED = "/home/claude/hg_ai/model/sealed_hg2.json"


def test_persons_sha_matches_seal():
    h = hashlib.sha256(open(PERSONS, "rb").read()).hexdigest()
    assert h == json.load(open(SEALED))["persons_parquet_sha256"]


def test_persons_distributions():
    df = pd.read_parquet(PERSONS)
    assert len(df) == 500 and df.person_id.is_unique
    assert df.age.between(65, 85).all() and df.omega_max.between(0.31, 0.57).all()
    assert df.kappa_core.between(14, 30).all() and (df.split == "").all()


@pytest.mark.parametrize("tdb,met,rh", [(t, m, 45.0) for t in (26, 31, 36) for m in (0.86, 1.37)] + [(44, 0.86, 30.0), (44, 1.37, 30.0), (36, 0.95, 45.0)])
def test_agreement_with_pythermalcomfort(tdb, met, rh):
    from pythermalcomfort.models import two_nodes_gagge_ji
    vp = rh * p_sat_torr(tdb) / 100
    r = two_nodes_gagge_ji(tdb=tdb, tr=tdb, v=0.1, met=met, clo=0.4, vapor_pressure=vp, body_surface_area=1.84,
                           position="sitting", acclimatized=False, body_weight=73.2, length_time_simulation=480)
    b = TwoNodeOlder(dict(mass_kg=73.2, A_D=1.84), features=(), ji_init=True, compute_ref=False)
    for _ in range(480):
        o = b.step(dict(t_db=tdb, rh=rh, v_air=0.1, met=met, clo=0.4, standing=False))
    assert abs(r.t_core[-1] - o["T_core"][0]) <= 0.05
    assert abs(r.t_skin[-1] - o["T_skin"][0]) <= 0.3


def test_energy_balance_closes():
    P = load_persons(idx=slice(0, 50))
    b = TwoNodeOlder(P, minute_of_day0=600)
    for i in range(300):
        hc0 = 0.97 * (b.alfa * b.t_skin + (1 - b.alfa) * b.t_core) * b.p["mass_kg"]
        a0 = b.alfa.copy()
        o = b.step(dict(t_db=34.0 + 4 * np.sin(i / 30), rh=40.0, met=1.37 if i % 60 < 20 else 0.86, clo=0.4, minute_of_day=600 + i))
        hc1 = 0.97 * (a0 * o["T_skin_node"] + (1 - a0) * o["T_core"]) * b.p["mass_kg"]
        assert np.max(np.abs((hc1 - hc0) * 60 / b.p["A_D"] - o["storage"])) < 1.0


def test_monotone_core_rise_in_tdb_heat():
    P = load_persons(idx=slice(0, 60))
    for met in (0.86, 1.37):
        prev = None
        for T in range(30, 41, 2):
            d = meade(P, T, met=met, hours=8)["dcore"]
            if prev is not None:
                assert np.all(d >= prev - 1e-6), (met, T)
            prev = d


@pytest.mark.xfail(strict=True, reason="Below 30 C a few persons (<= 7/500) show <= 0.025 C LOWER core at the warmer room: crossing their "
                   "vasoconstriction threshold (33.25 C skin) releases shell insulation, a genuine two-node (Gagge-Ji) property; see VALIDATION MONO")
def test_monotone_core_rise_in_tdb_cool_range():
    P = load_persons()
    for met in (0.86, 1.37):
        prev = None
        for T in range(22, 31, 2):
            d = meade(P, T, met=met, hours=8)["dcore"]
            if prev is not None:
                assert np.all(d >= prev - 1e-6), (met, T)
            prev = d


def test_met_never_in_1p1_1p2_band():
    P = load_persons()
    for m in MET_CLAMP:
        v = person_met(P, m)
        assert not np.any((v > 1.1) & (v < 1.2))


def _sensor_run(Ta, minutes, worn=2, h_out=8.0, n=30):
    P = load_persons(idx=slice(0, n))
    b = TwoNodeOlder(P, minute_of_day0=600)
    nz = [person_noise(int(s), minutes) for s in P["seed"]]
    bs = BandSensors(P, {k: np.stack([z[k] for z in nz], 1) for k in nz[0]})
    outs = []
    for t in range(minutes):
        Tt = Ta(t) if callable(Ta) else Ta
        o = b.step(dict(t_db=Tt, rh=40.0, met=person_met(P, 0.86), clo=0.4, minute_of_day=600 + t))
        w = worn(t) if callable(worn) else worn
        s = bs.step(dict(T_core=o["T_core"], s_skbf=o["s_skbf"], T_air=np.full(n, Tt), RH_air=np.full(n, 40.0), HR_true=o["HR"],
                         m_sweat=o["m_sweat"], deficit_pct=o["deficit_pct"]),
                    dict(worn=np.full(n, w), h_out=np.full(n, h_out), r_gap=np.full(n, 0.03), sun_dT=np.zeros(n), flash=np.zeros(n),
                         asleep=np.zeros(n), rh_wet=np.zeros(n), a_std_true=np.full(n, 0.005), act_class=np.full(n, 2),
                         zangle_true=np.zeros(n), slip=np.zeros(n)))
        outs.append((o, s))
    return outs


def test_sensor_first_order_lag_after_room_step():
    outs = _sensor_run(lambda t: 26.0 if t < 120 else 31.0, 200)
    t1 = np.array([s["T1_true"] for _, s in outs])
    step = t1[199] - t1[119]
    frac5 = (t1[124] - t1[119]) / step      # 5 min after the step: partially followed (tau 3-5 min + body)
    assert 0.2 < np.median(frac5) < 0.95


def test_flux_collapses_in_hot_room_and_is_large_in_cool_room():
    hot = _sensor_run(37.0, 240)[-1][1]
    cool = _sensor_run(24.0, 240)[-1][1]   # 20-22 C can exceed 5 C for some persons (R2 §2.2 itself: 5.2 C at 20 C), see VALIDATION R2-dT-cool
    assert np.all(hot["T1_true"] - hot["T2_true"] <= 0.6)
    assert np.all((cool["T1_true"] - cool["T2_true"] >= 2.0) & (cool["T1_true"] - cool["T2_true"] <= 5.0))


@pytest.mark.xfail(strict=True, reason="R2 §6.5 asks dT <= 0.6 C at T_air >= 34 C for every elder, but R2's own §6.1 physical model "
                   "(D_axial 0.3-0.8 + 0.08-0.2*(Tc-Ta)*(1-s), R_total ~0.22) gives dT 0.7-1.2 C at 34-35 C; the bound holds from ~36-37.5 C. "
                   "Conflict inside R2, reported in VALIDATION.md row R2-dT34; physics kept.")
def test_dT_le_0p6_at_34C_every_person():
    s = _sensor_run(34.0, 240)[-1][1]
    assert np.all(s["T1_true"] - s["T2_true"] <= 0.6)


def test_loose_band_moves_T1_dT_PI_together():
    worn = _sensor_run(25.0, 180)[-1][1]
    loose = _sensor_run(25.0, 180, worn=lambda t: 2 if t < 120 else 1)[-1][1]
    assert np.all(loose["T1_true"] < worn["T1_true"])
    assert np.all(loose["T1_true"] - loose["T2_true"] < worn["T1_true"] - worn["T2_true"])
    assert np.nanmedian(loose["PI"]) < np.nanmedian(worn["PI"])


def test_random_persons_random_scenarios_properties():
    from velders.population import simulate_chunk
    from velders.protocols import dev_persons_df
    rows = dev_persons_df().sample(4, random_state=3).to_dict("records")
    res = simulate_chunk((rows, 3))
    for pid, m, ev, ppg, types, reg in res:
        truth = ["T_core", "T_skin_mean", "T_deep_wrist", "HR_true", "deficit_pct", "T_in", "met"]
        assert not m[truth].isna().any().any()
        assert m.T_core.between(35, 41).all()
        w = (m.worn_truth == 2) & (m.sun_on_lid == 0) & (m.T_in < m.T_core) & ((m.location == 0) | (m.T_out < m.T_core))
        assert ((m.T1 <= m.T_core + 0.11)[w]).mean() > 0.999
        assert m.HR_meas[m.worn_truth == 0].isna().all()


def _timeline(i):
    from velders.protocols import dev_persons_df
    from velders.scenarios import build_person, env_arrays
    r = dev_persons_df().iloc[i].to_dict()
    tl, mins, _ = build_person(r, 10, int(r["seed"]))
    return r, tl, mins, env_arrays(r, tl, mins)


@pytest.mark.parametrize("i", [0, 7, 33, 120])
def test_every_stored_day_has_a_night_in_the_bedroom(i):
    """Round 3 (tester B1): every stored day (1..10) has >= 5 h asleep, in the bedroom, at sleep met and bed clo."""
    r, tl, mins, e = _timeline(i)
    for d in range(1, 11):
        sl = slice(d * 1440 + 120, d * 1440 + 4 * 60)      # 02:00-04:00: in bed (asleep or awake-in-bed bouts)
        asleep = tl.asleep[d * 1440:(d + 1) * 1440]
        assert asleep.sum() >= 300, (i, d)
        assert np.all(tl.room[sl] == 1), (i, d)
        night = tl.asleep[sl] > 0
        assert night.mean() > 0.6, (i, d)
        assert np.all(e["met"][sl][night] <= 0.8)
        assert np.all(e["clo"][sl][night] >= 0.35)


def test_s3_night_heat_reaches_the_sleeper():
    """S3: on heat-wave nights the sleeping person is exposed to the (warmer) bedroom air."""
    from velders.protocols import dev_persons_df
    df = dev_persons_df()
    for i in range(30):
        r, tl, mins, e = _timeline(i)
        if tl.regime == "S2":
            d = [k for k, t in enumerate(tl.day_types) if t.startswith("S2")][2]
            sl = slice(d * 1440, d * 1440 + 5 * 60)
            assert np.allclose(e["t_db"][sl][tl.asleep[sl] > 0], mins["t_bed"][sl][tl.asleep[sl] > 0])
            assert np.all(mins["t_bed"][sl] > mins["t_in"][sl])
            return
    pytest.fail("no S2 person in the first 30 dev persons")


def test_s9_late_wake_day_carries_its_signal():
    """S9 late-wake anomaly: asleep (still, in bed) until >= 11:00 on the anomaly day, no chores before it."""
    found = 0
    for i in range(200):
        r, tl, mins, e = _timeline(i)
        for typ, d, a, b in tl.events:
            if typ == "anomaly" and a == d * 1440:      # late-wake kind starts at midnight
                sl = slice(d * 1440 + 5 * 60, d * 1440 + 11 * 60)
                assert tl.asleep[sl].mean() > 0.75
                assert e["act_class"][sl].max() <= 1
                found += 1
        if found >= 2:
            return
    assert found >= 1


def test_sleep_a_std_below_still_threshold():
    """Round 3 (B3): asleep worn minutes have no tremor -> a_std mostly <= 0.002 g (noise floor 1.4 mg)."""
    from velders.population import simulate_chunk
    from velders.protocols import dev_persons_df
    res = simulate_chunk((dev_persons_df().iloc[:3].to_dict("records"), 2))
    m = pd.concat([x[1] for x in res])
    s = (m.asleep == 1) & (m.worn_truth == 2)
    print("asleep a_std quantiles", m.a_std_g[s].quantile([0.1, 0.5, 0.9]).round(5).tolist(), "frac <= 0.002", (m.a_std_g[s] <= 0.002).mean())
    assert m.a_std_g[s].median() <= 0.0017 and (m.a_std_g[s] <= 0.002).mean() > 0.8
