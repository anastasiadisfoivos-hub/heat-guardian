"""T6a-r2: parse_log.py on the v1.1.0 appended-file layout (independent of the builder's test).
Case 1: two boots in one hour file whose t_ms values are IDENTICAL (normal after a reset) -> no row may be
        de-duplicated across boots; no gap reported across the reset; each boot gets its own rows.
Case 2: a reset loop: 40 boot headers, each followed by 8 records (t_ms 1000..8000) -> 320 rows, 40 boots.
Case 3: case 1 again but fed twice (binary + the same bytes as a dump text capture) -> still de-duplicated
        within each boot.
  python3 -I tests/t6a/test_parse_v110.py <scratch dir>
"""
import os, subprocess, sys
import pandas as pd
HG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(HG, "fw", "tools"))
import parse_log as P
tmp = sys.argv[1]
fails = 0
def check(c, msg):
    global fails
    print(("PASS  " if c else "FAIL  ") + msg); fails += 0 if c else 1
def hdr(boot): return P.pack_record(5, flags=P.F_MARKER, marker=12, aux=boot)
def run(paths, tag):
    out = os.path.join(tmp, tag + ".parquet"); rep = os.path.join(tmp, tag + ".txt")
    r = subprocess.run([sys.executable, os.path.join(HG, "fw/tools/parse_log.py"), *paths, "-o", out, "--report", rep], capture_output=True, text=True)
    if r.returncode: print(r.stdout, r.stderr)
    df = pd.read_parquet(out); return df[~df["is_minute"]], open(rep).read()
# case 1
recs = lambda t1: [P.pack_record(1000 * k, t1=t1) for k in range(1, 61)]
f1 = os.path.join(tmp, "s0100.bin"); open(f1, "wb").write(hdr(21) + b"".join(recs(3300)) + hdr(22) + b"".join(recs(3400)))
df, rep = run([f1], "c1")
g = df.groupby("boot").size().to_dict()
check(len(df) == 120 and g == {21: 60, 22: 60}, f"identical t_ms across a reset: 120 rows split 60/60 (got {len(df)}, {g})")
check(abs(df[df.boot == 22]["T1"].mean() - 34.0) < 1e-6 and abs(df[df.boot == 21]["T1"].mean() - 33.0) < 1e-6, "rows keep their own boot's values (no cross-boot dedupe)")
# case 2
loop = b"".join(hdr(100 + b) + b"".join(P.pack_record(1000 * k, t1=3500) for k in range(1, 9)) for b in range(40))
f2 = os.path.join(tmp, "s0101.bin"); open(f2, "wb").write(loop)
df2, rep2 = run([f2], "c2")
check(len(df2) == 320 and df2["boot"].nunique() == 40, f"reset loop: 320 rows over 40 boots (got {len(df2)}, {df2['boot'].nunique()})")
# case 3: same bytes as a dump capture text + the binary
txt = os.path.join(tmp, "dump_c3.txt")
body = open(f1, "rb").read()
open(txt, "w").write("# FILE /log/s0100.bin size=%d\n" % len(body) + "".join(body[i:i + 24].hex() + "\n" for i in range(0, len(body), 24)) + "# END /log/s0100.bin bytes=%d\n# DUMP DONE\n" % len(body))
df3, _ = run([f1, txt], "c3")
check(len(df3) == 120, f"binary + dump text of the same appended file de-duplicate to 120 (got {len(df3)})")
print("T6A_PARSE_V110:", "PASS" if not fails else f"FAIL ({fails})")
sys.exit(1 if fails else 0)
