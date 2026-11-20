# [B3] Body Twin — delivery report (written by the manager from B3's final message; B3 could not create .md files)

Status: Python reference + C99 + host tests DONE (commit 39a6106). Sim evaluation PENDING (needs sim DEV minutes).

Files: twin/hg_twin.py, twin/c/{hg_twin.h,hg_twin.c,host_test.c,Makefile}, twin/tests/{make_golden.py,test_twin.py,golden_*}, twin/eval_htt.py, twin/eval_sim.py, twin/sim_io.py (never loads a sealed row group). Numbers: twin/results/htt_eval.json.

Results (to be re-verified by the tester):
1. C == Python bit-exact on 10 crafted golden nights (29 parameters); 825 B packed file byte-identical, CRC matches zlib; every single-bit flip / truncation rejected → defaults; 10,000-minute NaN/inf fuzz never breaks bounds; offset half-life exact; K never moves without a reading + valid flux. Accumulator 240 B (limit 256). Code 4,344 B on Cortex-M4F, no exp/log/pow/malloc. Builds against B5 hg2_step.h (make test-hg2).
2. HTT dev, minutes >= 30: learned resting HR +0.001 °C (CI −0.007..+0.008) — passes, changes nothing. One same-day reading: +0.008/+0.009/+0.013 °C over 3 noise draws — the 0.01–0.05 target FAILS on 2 of 3. Why: REPORT's +0.030 included minutes 0–29 (from minute 0: +0.020–0.025), and fixed β 0.35 over-corrects; best β 0.25 gives +0.0135.
3. HTT has no resting minutes at session start → used each person's measured resting HR.

Deviations/risks: extra API (alarm tier, air reference, commit reading); pack/unpack carry accumulator + save_count; 72 B learning state in file → routine profile must be ≤ 699 B; c_bodyheat unlearnable without a reference air sensor; oral readings run below core (bias into K/offset unless corrected); PPG outliers pull the night HR floor down; no night skin baseline learned during a heat wave.

Pending: `cd twin && python3 eval_sim.py --jobs 2`, then `python3 tests/make_golden.py --source sim && make -C c test`.
