# [B4] Tomorrow Engine — delivery report (written by the manager from B4's final message)

Status: works end-to-end offline and on a cached live forecast; 28 tests pass + 1 expected failure with diagnosed why (~35 s). Commit 77e910a. Files: tomorrow/{plan.json, schema.json, cli.py, tests/, cache/ (README.md)}. `pip install -e tomorrow` once so `python -I -m tomorrow` resolves.

Open-Meteo: the single live call → 429, one retry → reset, no more calls. Cache seeded from R3's Nov 12 sample (fetched_at approximate).

Demo (constructed Athens day, "Maria, 78", class B, velders physics): 02–06 OK, 08–23 AVOID; 12:00–18:00 7/7 AVOID; heat-day + night-heat flags on, wave day 4; ~2 s. OK hours shown from 05:00 (B4's choice) so «Ώρες για έξοδο: 05:00–07:00» appears. Live Nov 13 plan: all OK, no flags.

Indoor sanity: heat-wave week class B night minima 30.3–33.9 °C, 100 % hours > 30 °C; class C +1.9–2.5 °C over B on night minimum (+3.7 on daily mean; only the night minimum asserted); class A on real Bath series: lag 4 h, ratio 0.22; 24 °C day all OK; fan no benefit at 36 °C.

Expected failure: fan at 31 °C helps only 0.06 °C (needs ≥ 0.15) because the two-node gives +0.5 °C rise where the study measured +1.1 → calibration item for B1.

Frames: 20-byte CRC-8 vectors pass (check value 0xF4). R4's 0x11 forecast frame needs 22 B, not 20 → chunk index moved into flag bits 3–4; B5 must decode against tests/ble_vectors.json.

Decisions/conflicts: (1) hot-indoors escalation additionally requires room ≥ 26 °C (a cooking hour at 24 °C pushed core over threshold). (2) ARCH sweat cap ×0.75 at rest overheats (+1.3–2.3 °C at 36 °C vs +0.9 measured) → not used in the stub; relayed to B1. (3) R3's class-B offset applied to daily mean not night minimum → class B likely 1–3 °C hot in long waves. (4) indoor RH ratio 0.69 makes air dry → understates strain. (5) Four new Greek strings need Foivos's approval.

Open risks: no Athens indoor data; velders still changing.
