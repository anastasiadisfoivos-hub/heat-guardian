#!/usr/bin/env python3
"""T5 M3.1 property on the scripted-core harness: "the NN can only lower thresholds / add alarms, never remove a
protected-path alarm". Pairs of runs with IDENTICAL protected inputs (v1.2 f20/z, env flags/counters, heat context, HR,
buttons, worn, time) and DIFFERENT NN outputs:  B = NN silenced (f20 30 C, logits -100, strain 0),  A = random NN.
Unlike the builder's host_test property_nn_monotone (whose hook rewrites hg2_out_t.core_20/f20_eff, which the default build's
tiers never read - they read aux.core20_noff, hg_guardian.c:159), the NN f20 here is the value the tiers actually use.
Checks per minute: tiers_B subset of tiers_A; level_B <= level_A; a family flag raised in B is pending in A (or A is in HELP).
  python3 m31.py N -> out/m31.json"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc
F = np.float32

def script(i):
    rng = np.random.default_rng(31000 + i)
    n = int(rng.integers(60, 400)); mod = int(rng.integers(780, 1200))
    v12 = rng.uniform(37.0, 38.6); z = rng.uniform(-4, 0); ta = rng.uniform(26, 40); ea = int(rng.integers(0, 2)); hrv = 1
    nn = rng.uniform(37.0, 38.8); l385 = rng.uniform(-4, 1); strain = rng.uniform(0, 9); worn = 2; wl = 0; astd = 0.01
    A, B = [], []
    for t in range(n):
        v12 += rng.normal(0, 0.03); z += rng.normal(0, 0.15); ta += rng.normal(0, 0.1)
        nn += rng.normal(-0.002, 0.03); l385 += rng.normal(0, 0.3); strain += rng.normal(0, 0.3)
        if rng.random() < 0.03: ea = 1 - ea
        if rng.random() < 0.02: hrv = 1 - hrv
        if rng.random() < 0.1: astd = float(rng.choice([0.001, 0.01, 0.05]))
        if wl <= 0 and rng.random() < 0.005: worn = int(rng.choice([0, 1])); wl = int(rng.integers(2, 20))
        if wl > 0: wl -= 1
        else: worn = 2
        b = 1 if rng.random() < 0.03 else 0
        x10 = float(rng.uniform(60, 120)); x14 = float(rng.uniform(0, 0.7))
        common = dict(mod=mod, button=b, worn=worn, astd=astd, hr_valid=hrv, v12f20=float(F(v12)), v12z=float(F(z)), tair=float(F(ta)),
                      ea=ea, eao=ea, x10=x10, x14=x14)
        A.append(sc.row(core20=float(F(nn)), l38=-100.0, l385=float(F(l385)), strain=float(F(min(max(strain, 0), 10))), sd20=0.1, **common))
        B.append(sc.row(core20=30.0, l38=-100.0, l385=-100.0, strain=0.0, sd20=0.0, **common))
        mod = (mod + 1) % 1440
    return sc.env_counters(A), sc.env_counters(B)

if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    prof = dict(age=75.0, sex_m=0.0, bmi=26.0, med_flags=0)
    v = dict(tier=0, level=0, family=0); ex = {}; mins = 0; protB = 0; famB = 0; seqs = set()
    for i in range(N):
        A, B = script(i)
        ca, cb = sc.run_c(prof, A), sc.run_c(prof, B); mins += len(A)
        for t, (a, b) in enumerate(zip(ca, cb)):
            if b["tiers"]: protB += 1
            fb = b["family_alert"] and not (t and cb[t - 1]["family_alert"])
            if fb: famB += 1
            if b["tiers"] & ~a["tiers"]:
                v["tier"] += 1; seqs.add(i); ex.setdefault("tier", (i, t, a["tiers"], b["tiers"], A[t]["core20"], A[t - 10]["core20"] if t >= 10 else None))
            if b["level"] > a["level"]: v["level"] += 1; ex.setdefault("level", (i, t, a["level"], b["level"]))
            if fb and not (a["family_alert"] or a["help"]): v["family"] += 1; seqs.add(i); ex.setdefault("family", (i, t))
    r = dict(pairs=N, minutes=mins, minutes_with_protected_tier=protB, family_flags_B=famB, violations=v, sequences_with_violation=len(seqs), examples=ex)
    json.dump(r, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "m31.json"), "w"), indent=1, default=str)
    print(json.dumps(r, indent=1, default=str))
