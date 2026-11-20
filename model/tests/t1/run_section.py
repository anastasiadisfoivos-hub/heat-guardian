"""T1: regenerate one VALIDATION section with the builder's own code, WITHOUT overwriting the
builder's validation_rows.json (ROWS_PATH redirected to tests/t1/out/). SIMULATION.
usage: python3 -I run_section.py <section>"""
import sys, time, json, os
sys.path.insert(0, "/home/claude/hg_ai/sim")
import velders.validate as V
sec = sys.argv[1]
V.ROWS_PATH = f"/home/claude/hg_ai/tests/t1/out/rows_{sec}.json"
t0 = time.time()
V.main(["--section", sec])
print(f"[T1] section {sec} took {time.time()-t0:.0f} s")
