# [B5] Guardian Loop wave 1 — delivery report (written by the manager from B5's final message)

Commits 912e230, 85a2dc5, 84666ba. `make -C guardian/c test` → 54 PASS / 0 FAIL. Paths: guardian/{c,py,tests,fw_check}.
- 0x11 bits 3–4 decoder + test vs tomorrow/tests/ble_vectors.json (4 chunks, 24 h, 0x14) in 85a2dc5, 0 mismatches.
- Routine profile byte layout v1 (650 B, stable) documented in c/hg_routine.h; fits B3's 699 B.
- C vs Python mirror: state identical 100 % of minutes on 104 HTT dev sessions (11,195 min), 50 crafted days, 3 crafted multi-day runs (float diffs ~5e-8).
- hg_kf vs v1.2 heat_guardian_band.c: estimate/f20 diff 0 on all 104; logit diff 2e-7; state 100 %. 20 synthetic older/med sessions: 1/4,800 minutes differs in a reason flag only.
- 30 traces from §7.2 rows + 12 properties over 10,000 random sequences pass.
- Sizes (updated at hg2-freeze-4, T5 m8): hg2 state 488 B, guardian 3,816 B (ARM, arm-none-eabi-gcc 9.2.1); ARM stack of hg_guardian_step 1,632 B (792 + hg2_step_aux 728 + hg_kf_step 112, -O2; host 1,776 B); libm: floorf, sqrtf only.
- poc_06 + guardian (hg2-freeze-4 sources): 269,784 B (33 %) flash; guardian code without weights ~24 KB at -O2 (~29.7 KB at -Ofast).

Findings (no threshold changed by B5): (1) WHO 24 °C night rule turns DRINK on every night in a 26 °C bedroom. (2) v1.2 fit on RH 38–60 %; below ~35 % a resting 75-y woman's f20 crosses DRINK (37.84 at 20 %). (3) older + medication margins leave 0–0.2 °C between resting f20 and DRINK; crafted ordinary week → DRINK ~19 h/day (crafted only).
Not done: SIM-DEV rates (no B1 minutes yet); office scripts written, not run; NN/uncertainty rows wait for B2; no board timing; B2 must match py/hg_guardian_py.py features; AC evidence, impact window, home/out scoring are designer choices (no published numbers); Magnus table quadratic interpolation.
