#!/usr/bin/env python3
"""T5 D1 acceptance: the same guardian/c sources built with the Makefile flags (-O2 -ffp-contract=off) and with the band's
fast-math flags (-Ofast -ffast-math) must give IDENTICAL replay output (every column, byte for byte) on
  - every crafted trace (tests/traces/*.csv),
  - all HTT dev sessions (py/run_traces.htt_sessions()),
  - N of T5's random sequences (tests/t5/gen_random.py: NaN / +-inf / 1e30 / out-of-range on every field, clock jumps, ...).
usage: fastmath_check.py [N_RANDOM] [SRC_DIR]     (SRC_DIR default guardian/c; pass an exported old tree to see "before")
exit 1 on any difference or crash."""
import os, subprocess, sys, tempfile, filecmp, glob
HERE = os.path.dirname(os.path.abspath(__file__)); G = os.path.dirname(HERE); ROOT = os.path.dirname(G)
sys.path.insert(0, os.path.join(G, "py"))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
SRC = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(G, "c")
W = os.path.join(ROOT, "model", "export")
FILES = ["host_test.c", "hg_util.c", "hg_tables.c", "hg_kf.c", "hg2_step.c", "hg_contact.c", "hg_homeout.c", "hg_routine.c", "hg_frames.c", "hg_guardian.c"]
FLAGS = {"O2": ["-O2", "-ffp-contract=off"], "Ofast": ["-Ofast", "-ffast-math"]}

def build(d):
    bins = {}
    for k, fl in FLAGS.items():
        b = os.path.join(d, "host_" + k)
        subprocess.check_call(["gcc", "-std=c99", "-fsingle-precision-constant", "-w"] + fl + ["-I" + SRC, "-I" + W]
                              + [os.path.join(SRC, f) for f in FILES] + [os.path.join(W, "hg2_weights.c"), "-lm", "-o", b])
        bins[k] = b
    return bins

def main():
    import trace_io, run_traces
    with tempfile.TemporaryDirectory() as d:
        bins = build(d); inputs = sorted(glob.glob(os.path.join(G, "tests", "traces", "trace_*.csv")))
        for j, (name, prof, tw, mins) in enumerate(run_traces.htt_sessions()):
            p = os.path.join(d, "htt_%03d.csv" % j); trace_io.write_csv(p, mins, prof, tw); inputs.append(p)
        t5 = os.path.join(ROOT, "tests", "t5")
        if N and os.path.exists(os.path.join(t5, "gen_random.py")):
            sys.path.insert(0, t5); import gen_random
            for i in range(N):
                name, prof, tw, mins = gen_random.seq(i); p = os.path.join(d, "rnd_%05d.csv" % i)
                trace_io.write_csv(p, mins, prof, tw); inputs.append(p)
        bad = crash = 0; first = None
        for p in inputs:
            outs = {}
            for k, b in bins.items():
                o = os.path.join(d, os.path.basename(p) + "." + k + ".out"); rc = subprocess.run([b, "replay", p, o], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
                if rc != 0: crash += 1
                outs[k] = o
            if not (os.path.exists(outs["O2"]) and os.path.exists(outs["Ofast"]) and filecmp.cmp(outs["O2"], outs["Ofast"], shallow=False)):
                bad += 1; first = first or os.path.basename(p)
        print("sources %s: %d inputs (crafted %d, HTT + random %d): %d differ between -O2 and -Ofast -ffast-math, %d crashed runs%s"
              % (SRC, len(inputs), len(glob.glob(os.path.join(G, "tests", "traces", "trace_*.csv"))), len(inputs) - len(glob.glob(os.path.join(G, "tests", "traces", "trace_*.csv"))),
                 bad, crash, (", first: " + first) if first else ""))
        sys.exit(1 if bad or crash else 0)

if __name__ == "__main__":
    main()
