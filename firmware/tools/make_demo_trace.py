#!/usr/bin/env python3
"""[FW-DEMO] Heat-episode replay trace for 09_guardian 0.9.16-demo -- SIMULATION ONLY.

Runs ONE simulated older person through a hot afternoon with the project's Virtual Elders simulator (sim/velders:
Gagge-Ji two-node body + the BandSensors model of what the band's sensors would read: skin T1, reference T2, air
T/RH (SHTC3), HR + quality + PI (MAX30102), a_std / z-angle (IMU)) and writes the per-minute SENSOR readings as a
compact int16 table the firmware replays into its normal 1 Hz input path (hg_fw_second). The band's own frozen
guardian and alert layer then decide everything that happens; nothing here decides a tier.

The person is drawn fresh with velders.persons.draw_one (pid >= 90000): no persons.parquet row, no sealed file is read.

  HG_SIM_VERSION=v5 python3 -I fw/tools/make_demo_trace.py            (writes the header + the CSV below)

Outputs: fw/09_guardian/hg_demo_trace.h, fw/09_guardian/demo/heat_episode.csv
"""
import os
import sys

os.environ.setdefault("HG_SIM_VERSION", "v5")       # the model was trained on sim v5 (hg2 tag ...-simv5aug)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "sim"))

import numpy as np                                    # noqa: E402
from velders.persons import draw_one                  # noqa: E402
from velders.body import TwoNodeOlder                 # noqa: E402
from velders.sensors import BandSensors, person_noise  # noqa: E402
from velders.scenarios import ACT, ASTD, ZANG          # noqa: E402

# ------------------------------------------------------------------ scenario (edit here; every number is the INPUT)
PID0 = 90000              # fresh persons, outside the 500-person population (0..499) and its sealed split
SPIN_FROM = 6 * 60        # body + sensor spin-up from 06:00 (not replayed)
EP_START = 13 * 60        # the visible replay starts 13:00
EP_LEN = 110              # minutes shown (13:00-14:49)
PRE = 150                 # hidden pre-roll rows before 13:00 (10:30-12:59), replayed quietly after the calm warm-up
# phases, minutes from EP_START: (from, to, room T from->to, RH %, activity, fan, drink mL at 'from')
PHASES = [
    # morning in the top-floor flat (spin-up / hidden pre-roll): room climbs 27 -> 31.5 C, quiet indoor life
    (-420, -60, 27.0, 31.0, 45, "sit", 0, 0),
    (-60, 0, 31.0, 32.0, 42, "adl", 0, 0),
    # visible: calm, sitting in the warm living room
    (0, 10, 32.0, 32.5, 40, "sit", 0, 0),
    # she cooks lunch in the hot kitchen (no A/C, top floor, oven on): room 34 -> 39.5 C, busy, does not drink
    (10, 55, 34.0, 40.5, 33, "cook", 0, 0),
    # intervention 1 (13:50): she drinks a glass of water (300 mL) but keeps tidying in the hot flat
    (55, 70, 39.5, 39.0, 34, "adl", 0, 300),
    # intervention 2 (14:10): moves to the coolest room (north bedroom, shutters closed), sits under the fan, drinks again.
    # [DEMO-PICK] b7t: 26.5 -> 24.5 C (b7s: 29 -> 27.5 C), so that the episode ends (all clear) inside the 110 shown minutes
    (70, 110, 26.5, 24.5, 45, "sit", 1, 250),
]
DRINK_SPIN = {-360: 200, -240: 200, -120: 150}         # normal sipping in the morning (mL at those minutes)

TMP_LSB = 0.0078125


# [DEMO-PICK] b7t: the person is PINNED. Chosen as a SHOWCASE (not a typical person): every fresh draw pid 90000-95999 that is
# female, 73-78 y, no beta-blocker / anticholinergic (611 people; 344 of them run through this scenario on the host build of
# the firmware, b7s scenario) was scored on the band's estimate vs her true core, and the accurate ones re-run with the bedroom
# at 27->25 and 26->23.5 C; pid 90862 was the most accurate one that also gives the full press ladder (water, still heating,
# go cool, Bravo, all clear) and the no-response family alert ~13:45. Her estimate error is far below the population's.
# None of these draws is in the 500-person population (pid 0..499) or its sealed split; no sealed file is read.
DEMO_PID = 90862


def pick_person():
    p = draw_one(DEMO_PID)
    assert p["sex_m"] == 0 and 73.0 <= p["age"] <= 78.0 and not p["med_bb_nonsel"] and not p["med_bb_sel"] and not p["med_antichol"]
    return p


def pick_person_b7s():
    """b7s rule (kept for the record): female, 74-76 y, no beta-blocker / anticholinergic, mid frailty; the first matching
    pid wins (= 90416)."""
    for pid in range(PID0, PID0 + 5000):
        p = draw_one(pid)
        if (p["sex_m"] == 0 and 74.0 <= p["age"] <= 76.0 and not p["med_bb_nonsel"] and not p["med_bb_sel"]
                and not p["med_antichol"] and 0.3 <= p["frailty"] <= 0.7 and 22 <= p["bmi"] <= 30):
            return p
    raise SystemExit("no person found")


def phase_at(m):
    for ph in PHASES:
        if ph[0] <= m < ph[1]:
            return ph
    return PHASES[-1]


def main():
    P1 = pick_person()
    P = {k: np.array([v]) for k, v in P1.items() if not isinstance(v, str)}
    n_tot = EP_START + EP_LEN - SPIN_FROM
    body = TwoNodeOlder(P, minute_of_day0=float(SPIN_FROM))
    noise = person_noise(int(P1["seed"]), n_tot + 2)
    noise = {k: (v[:, None] if v.ndim == 1 else v) for k, v in noise.items()}
    sens = BandSensors(P, noise)
    rng = np.random.default_rng([int(P1["seed"]), 7])
    rows = []
    z_ar = 0.0
    for i in range(n_tot):
        mod = SPIN_FROM + i
        m = mod - EP_START
        a, b, t0, t1, rh, act, fan, drink = phase_at(m)
        frac = (m - a) / max(b - a, 1)
        t_db = t0 + (t1 - t0) * frac
        met_base = ACT[act][0]
        met = max(met_base * P1["met_adl_mult"], 1.22) if met_base >= 1.2 else min(met_base * P1["met_rest_mult"], 1.08)
        d = (drink if m == a else 0.0) + DRINK_SPIN.get(m, 0.0)
        v_air = 1.5 if fan else 0.1
        h_out = 22.0 if fan else 8.0
        o = body.step(dict(t_db=t_db, rh=rh, t_r=t_db, v_air=v_air, met=met, clo=0.4, drink_mL=d, minute_of_day=mod,
                           standing=met >= 0.95))
        mu, sd = ASTD[act]
        a_true = max(mu + sd * rng.normal(), 0.0003)
        zm, zs = ZANG[act]
        z_ar = 0.9 * z_ar + np.sqrt(1 - 0.81) * rng.normal()
        truth = dict(T_core=o["T_core"], s_skbf=o["s_skbf"], T_air=np.array([t_db]), RH_air=np.array([rh]),
                     HR_true=o["HR"], m_sweat=o["m_sweat"], deficit_pct=o["deficit_pct"])
        ctx = dict(worn=np.array([2]), h_out=np.array([h_out]), r_gap=np.array([0.0]), sun_dT=np.array([0.0]),
                   flash=np.array([0.0]), asleep=np.array([0]), rh_wet=np.array([0]), a_std_true=np.array([a_true]),
                   act_class=np.array([ACT[act][1]]), zangle_true=np.array([zm + zs * z_ar]), slip=np.array([0]))
        s = sens.step(truth, ctx)
        if m >= -PRE:
            rows.append(dict(m=m, mod=mod, t1=float(s["T1"][0]), t2=float(s["T2"][0]), ta=float(s["T_air_meas"][0]),
                             rh=float(s["RH_meas"][0]), hr=float(s["HR_meas"][0]), q=int(s["hr_quality"][0]),
                             pi=float(s["PI"][0]), astd=float(s["a_std_g"][0]), z=float(s["zangle_deg"][0]),
                             core=float(o["T_core"][0]), hr_true=float(o["HR"][0]), room=t_db, act=act, fan=fan,
                             drink=d, deficit=float(o["deficit_pct"][0])))
    write(P1, rows)


def i16(x):
    return int(max(-32767, min(32767, round(x))))


def hs(x):
    return '' if x != x else f'{x:.1f}'


def write(P1, rows):
    g9 = os.path.join(ROOT, "fw", "09_guardian")
    os.makedirs(os.path.join(g9, "demo"), exist_ok=True)
    who = (f"simulated person pid {P1['person_id']} (velders draw_one, seed {P1['seed']}): female, age {P1['age']:.1f}, "
           f"BMI {P1['bmi']:.1f}, frailty {P1['frailty']:.2f}, rest HR {P1['hr_rest']:.0f}, no beta-blocker/anticholinergic")
    with open(os.path.join(g9, "demo", "heat_episode.csv"), "w") as f:
        f.write("# SIMULATION (Virtual Elders, sim/velders, HG_SIM_VERSION=v5) -- not a real person, not real data\n")
        f.write(f"# {who}\n# generated by fw/tools/make_demo_trace.py; replayed by `replay` (firmware 0.9.16-demo)\n")
        f.write("min,clock,t1_c,t2_c,air_c,rh_pct,hr_bpm,hr_q,pi_pct,a_std_g,z_deg,| truth: core_c,hr_true,room_c,activity,fan,drink_mL,deficit_pct\n")
        for r in rows:
            f.write(f"{r['m']},{r['mod']//60:02d}:{r['mod']%60:02d},{r['t1']:.3f},{r['t2']:.3f},{r['ta']:.2f},{r['rh']:.1f},"
                    f"{hs(r['hr'])},{r['q']},{r['pi']:.3f},{r['astd']:.4f},{r['z']:.1f},|,"
                    f"{r['core']:.3f},{r['hr_true']:.1f},{r['room']:.2f},{r['act']},{r['fan']},{r['drink']:.0f},{r['deficit']:.2f}\n")
    with open(os.path.join(g9, "hg_demo_trace.h"), "w") as f:
        f.write("/* [FW-DEMO] GENERATED by fw/tools/make_demo_trace.py -- do not edit. SIMULATION, not real data.\n")
        f.write(f" * {who}.\n")
        f.write(" * Scenario: rows 0..HG_DEMO_PRE-1 = hidden pre-roll 10:30-13:00 (top-floor flat warming 30 -> 32 C); visible from 13:00:\n")
        f.write(" * calm in the 32 C living room -> 13:10 cooks in a 34->40.5 C kitchen without drinking -> 13:55 drinks 300 mL, keeps\n")
        f.write(" * tidying in the 39 C flat -> 14:10 coolest room 26.5->24.5 C with a fan, drinks 250 mL -> 14:49 end.\n")
        f.write(" * [DEMO-PICK] person pinned (DEMO_PID) as a showcase: chosen for estimate accuracy among fresh draws, see make_demo_trace.py.\n")
        f.write(" * One row per simulated minute: what the band's sensors would read (velders BandSensors), fixed point:\n")
        f.write(" * t1/t2/ta/core 0.01 C, rh 0.1 %, hr 0.1 bpm (HG_DEMO_NOHR = no reading), pi 0.001 %, astd 1e-5 g, z 0.01 deg.\n")
        f.write(" * core = the simulator's TRUE core temperature (shown in DEMO console lines only; never an input). */\n")
        f.write("#ifndef HG_DEMO_TRACE_H\n#define HG_DEMO_TRACE_H\n")
        f.write(f"#define HG_DEMO_N {len(rows) - PRE}\n#define HG_DEMO_PRE {PRE}\n#define HG_DEMO_START_MOD {EP_START}\n")
        f.write("static const hg_demo_row_t HG_DEMO_TRACE[HG_DEMO_PRE + HG_DEMO_N] = {\n")
        f.write("/*  t1    t2    ta    rh   hr    pi   astd     z  core  q */\n")
        for r in rows:
            hr = -32768 if r["hr"] != r["hr"] else i16(r["hr"] * 10)
            f.write(f"  {{ {i16(r['t1']*100)}, {i16(r['t2']*100)}, {i16(r['ta']*100)}, {i16(r['rh']*10)}, "
                    f"{'HG_DEMO_NOHR' if hr == -32768 else hr}, {i16(r['pi']*1000)}, {i16(r['astd']*1e5)}, {i16(r['z']*100)}, "
                    f"{i16(r['core']*100)}, {r['q']} }},   /* {r['mod']//60:02d}:{r['mod']%60:02d} {r['act']}{' fan' if r['fan'] else ''}"
                    f"{' drink %d mL' % r['drink'] if r['drink'] else ''} room {r['room']:.1f} */\n")
        f.write("};\n#endif\n")
    print(who)
    for r in rows[PRE::5]:
        print(f"{r['m']:3d} {r['mod']//60:02d}:{r['mod']%60:02d} room {r['room']:5.1f} t1 {r['t1']:.2f} t2 {r['t2']:.2f} air {r['ta']:.1f} "
              f"rh {r['rh']:4.0f} hr {r['hr']:5.1f} q{r['q']} core {r['core']:.2f} def {r['deficit']:.2f} {r['act']}")


if __name__ == "__main__":
    main()
