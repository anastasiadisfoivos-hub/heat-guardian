# Virtual Elders v5 — validation against Brighton (B1-v5, Nov 13 2026) — SIMULATION vs REAL

**Status: v5 CODE FROZEN at the commit that adds this file. No v5 data has been generated.** The manager seals SEALED-SIM-4 before any v5 generation (SEALED-SIM-3 was sealed against v4 and is not used for v5).

**Data rule (manager, Nov 13):** Brighton/Waldock (10 people aged 65–76, 35 °C / 51 % RH, 30 min rest, then 30 min cycling) was spent as an exam on hg2-freeze-5. All sheets P1–P10 are now **calibration** data. **No Brighton number may ever again be claimed as held-out for any later version.** CC BY-ND 3.0: only summary numbers appear here. The tool `sim/tools/brighton_calib.py` keeps every derived table in memory.

## How it was compared
- **Persons:** the participants' own mass, A_D and pre-chamber HR, each run with 76 matched DEV physiology vectors. Matched means age ≤ 78, frailty < 0.5 and no medication. Sealed set-1 ids are excluded, and no SEALED-SIM set was read.
- **Protocol:** each participant's own Control session (air held from the measured rows, the sheet's cycling power), simulated minute by minute. Sessions: Control, n = 10.
- **Protocol assumptions, attached to every number:**
  - Rest at 1.0 met and the cognitive test at 1.1 met.
  - Cycling heat production = 1.0 met + P(1/0.22 − 1)/A_D. This assumes a delta efficiency of 0.22, and the external work is not counted as heat.
  - Clothing 0.35 clo, air speed 0.2 m/s.
  - Circadian, acclimatisation and medication switched off.
  - A 60-min pre-chamber spin-up at 24 °C. Core is then set to the measured rectal, and the HR reference is re-based to the measured pre-chamber HR.

## v4 vs v5 on Brighton (Control, n = 10; error = sim − real)
| Target | Real | v4 sim (err) | v5 sim (err) | Verdict |
|---|---|---|---|---|
| Rest 5→30 min rectal change | +0.01 °C | +0.14 (+0.13) | same | Within protocol uncertainty: at a rest met of 0.86 instead of 1.0 the error is +0.06, at 1.15 it is +0.21. Not identifiable, so no physics change. |
| Rest HR (10–30 min mean − pre-chamber) | +2.9 bpm | +4.7 (+1.7) | same | PASS (the v4 HR model is fine at rest) |
| Rest 4-site mean skin (10–30 min) | 34.91 °C | 34.77 (−0.14) | 34.80 (−0.12) | PASS |
| **Between-person SD of rectal − mean skin, rest** | **0.43 °C** | **0.26** | **0.45** | **v4 too uniform; v5 fitted** |
| **Same, cycling** | **0.48 °C** | **0.29** | **0.43** | **v5 fitted** |
| Cycling 35→65 min rectal change | +0.52 °C | +1.67 (+1.15) | same | **FAIL** (out of domain, see below) |
| Cycling mean skin | 35.91 °C | 36.72 (+0.81) | 36.75 | FAIL (same cause) |
| Session sweat (pre−post nude mass) | 0.57 kg | 0.24 (−0.32) | same | FAIL (same cause; the real figure is an upper bound) |
| Cycling HR change | +41 bpm | +84 | same | Out of domain: the met term of the HR model was built for ADL ≤ 2.2 met |

## What changed in v5 (and why only this)
**One change: per-person skin–core coupling heterogeneity.** The v4 body heats like the real cohort at rest within protocol uncertainty (rows 1–3). What v4 gets wrong is how **uniform** the skin–core gap is between people:
- Real: SD 0.43 °C at rest and 0.48 °C cycling.
- v4: SD 0.26 / 0.29 °C.
- At the wrist the problem is worse. On SIM-DEV, v4's insulated T1 sits at core − 0.82 °C with an IQR of only 0.25 °C at 34–36.5 °C air (model/runs/b2b/diagnosis.json).

That near-perfect skin thermometer is what the network learned to trust (gain 0.53 °C per °C of T1, 0.05 °C per 10 bpm). The B2b diagnosis names it as the mechanism of the sealed low reading.

**How v5 applies the change.** Each person gets offsets drawn from their own seed, on a new random stream (7), so v4 streams are untouched. Both are clipped at ±3 SD.
- **d_skin ~ N(0, 0.36 °C).** Real SD minus ~0.06 °C thermistor noise, minus the v4 spread: an extra 0.34 at rest and 0.39 cycling, so 0.36 °C. Subtracted from T_skin_mean, T1 and T2.
- **d_wrist ~ N(0, 0.35 °C).** A single site spreads more than a 4-site mean: Brighton rectal − bicep has SD 0.48 / 0.62 °C, against 0.43 / 0.48 °C for the mean. This term is added to T1 and T2 only, so the total extra T1 spread is 0.50 °C.
- T1 and T2 move together, so the heat-flux dT and every v4 flux property are unchanged. `tests/test_body.py` passes under v5; it failed when the offset was put on T_deep, and that variant was rejected.
- The energy balance is unchanged. V5_FROZEN has no person-parameter keys, so every VALIDATION.md row computed with TwoNodeOlder alone (V1–V30: PSU limits, Meade, Kenny, …) is **identical by construction**. The sensor and agreement rows need v5 minutes, so they are re-run after the SEALED-SIM-4 seal.
- Physiological basis: regional and individual differences in skin vasomotor control in older adults (Inoue 1998, doi:10.1007/s004210050467; Holowatz & Kenney 2010, doi:10.1152/japplphysiol.00338.2010). Subcutaneous fat also varies: Brighton skinfold sums run 38.6–61.2 mm.

**Switch.** `HG_SIM_VERSION=v5` selects v5. With the variable unset, the code is v4 and the offsets are zero (`tests/test_v5.py`).

## Tried and NOT adopted (bounded, literature-supported, but not supported by Brighton)
- **Sweat core threshold −0.2 °C** (Inoue 1991/1999: older core threshold equals the young one) **combined with vasodilation gain ×2** (Millyard 2020: 2–3× below young, 40–60 vs 30). Rest core error went from +0.13 to +0.10 (inside the met uncertainty), but rest skin error worsened from −0.14 to −0.40. Rejected.
- **HR ambient time constant 5–120 min.** Once the reference is re-based to the pre-chamber HR, the error is +1.7 bpm at the v4 value of 5 min. No change.
- **Wettedness frame 1.6 → 2.0/5.0, regulatory sweat cap ×2, vasodilation ×2 and SkBF_max ×1.5.** These reduce the cycling rise error from +1.15 to about +0.9 °C at best, and they would break the PSU limit fits (V12/V13). Rejected.

## Known v5 failure, with its why
The simulated body heats about 3× too fast during cycling at 4–7 met. Even with every evaporative cap removed, the cycling rise error stays around +0.9 to +1.0 °C. Sweat production is about half of the measured mass loss. The two-node "core" also has no rectal lag and no working-muscle compartment.

This is outside the simulator's design domain. Virtual Elders scenarios are indoor daily living at 0.7–2.2 met (`body.MET_CLAMP`), and the product's premise is passive heat. It does **not** affect the regime in which the band is trained and used. It **does** mean Virtual Elders must not be used for exertional heat in older adults. Fixing it would need a three-compartment model (core / muscle / skin); that is not done.
