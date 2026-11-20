#!/usr/bin/env python3
"""Self-test of tests/wear_exam.py on SYNTHETIC logs only (no real data exists before Nov 16).

  python3 wear/selftest/selftest.py [WORK_DIR]

1. Refusals: no --data; real exam without the `wear-freeze` tag; synthetic --done-out inside wear/.
2. A plain fw/tools/sim_stream.py capture (2 h bench stream) runs end to end (mostly N/A, no crash).
3. make_synth_wear.py (3-day protocol, same packer) -> dev phase -> exam phase; checks that the exam recovers
   what the generator put in: c = 0.15, 4/4 loose episodes, sleep windows within 10 min, the injected watchdog
   reset is a FAIL, oral sessions inside the range, and that a second run refuses.
Writes nothing inside wear/: all outputs go to WORK_DIR (default: a temp dir).
"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
EXAM = os.path.join(REPO, "tests", "wear_exam.py")


def run(*a):
    r = subprocess.run([sys.executable] + list(a), capture_output=True, text=True, cwd=REPO)
    return r.returncode, r.stdout + r.stderr


def main():
    work = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="wear_selftest_")
    os.makedirs(work, exist_ok=True)
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + msg)
        ok &= bool(cond)

    rc, out = run(EXAM)
    check(rc == 2 and "--data is required" in out, "refuses without --data")
    syn = os.path.join(work, "synth")
    rc, out = run(os.path.join(HERE, "make_synth_wear.py"), syn)
    check(rc == 0, "synthetic 3-day capture generated: " + out.strip()[-120:])
    rc, out = run(EXAM, "--data", syn)
    has_tag = subprocess.run(["git", "-C", REPO, "rev-parse", "-q", "--verify", "refs/tags/wear-freeze"], capture_output=True).returncode == 0
    if not has_tag:
        check(rc == 2 and "wear-freeze" in out, "real exam refuses before the wear-freeze tag exists")
    check(not os.path.exists(os.path.join(REPO, "wear", "WEAR_EXAM_DONE.json")) or has_tag, "no real DONE file was written")
    rc, out = run(EXAM, "--data", syn, "--synthetic", "--done-out", os.path.join(REPO, "wear", "x.json"))
    check(rc == 2 and "must not be inside wear/" in out, "synthetic output refused inside wear/")
    raw = os.path.join(work, "raw_sim")
    os.makedirs(raw, exist_ok=True)
    run(os.path.join(REPO, "fw", "tools", "sim_stream.py"), "--seconds", "7200", "--with-ref", "--dumpmin", "-o", os.path.join(raw, "live.txt"))
    rc, out = run(EXAM, "--data", raw, "--synthetic", "--done-out", os.path.join(work, "raw_out", "DONE.json"))
    check(rc == 0, "plain sim_stream.py capture runs end to end")
    rc, out = run(EXAM, "--data", syn, "--phase", "dev", "--synthetic", "--done-out", os.path.join(work, "out", "DONE.json"))
    check(rc == 0, "dev phase runs")
    dev = json.load(open(os.path.join(work, "out", "DEV_THRESHOLDS_synthetic.json")))["thresholds"]
    check(abs(dev["c_bodyheat"] - 0.15) < 0.02, f"dev c_bodyheat recovered ({dev['c_bodyheat']:.3f} vs 0.15 generated)")
    done = os.path.join(work, "out", "DONE.json")
    rc, out = run(EXAM, "--data", syn, "--synthetic", "--done-out", done)
    check(rc == 0 and os.path.exists(done), "exam phase runs: " + out.strip().splitlines()[-1][:110])
    d = json.load(open(done))
    rows = {}
    for r in d["main"]["rows"] + d["firmware"]:
        rows.setdefault(r["id"], []).append(r)
    check(d["dev_thresholds"]["thresholds"] == dev, "exam re-derives the same day-1 thresholds as the dev phase")
    check(rows["B3"][0]["value"] == "4/4", "4 of 4 exam loose episodes detected (generator: 2 per exam day)")
    check(all(abs(r["value"]["onset_err_min"]) <= 10 and abs(r["value"]["wake_err_min"]) <= 10 for r in rows["D1"]), "HDCZA within 10 min on both exam nights")
    check(rows["G1"][0]["verdict"] == "FAIL" and rows["G1"][0]["value"] == 1, "injected watchdog reset is reported as a FAIL")
    check(rows["F1"][0]["value"]["n"] == 6, "6 exam oral sessions found (pairs averaged)")
    check(rows["A3"][0]["verdict"] == "CONSISTENT", "room tests give c in range")
    check(d["integrity"]["diary_unmatched_press_codes"] == 0 and d["integrity"]["presses_without_diary"] == 1,
          "diary matching: all diary presses matched, the one press without a diary line found")
    check(d["integrity"]["markers_per_day"]["3"]["6"] == 1, "diary HOME fallback (press + diary line) acts as marker 6")
    check(len(d["relatives"]) == 1 and d["relatives"][0]["age"] == 78.0, "relative session separated (age 78)")
    rc, out = run(EXAM, "--data", syn, "--synthetic", "--done-out", done)
    check(rc == 2 and "runs once" in out, "second exam run refuses")
    print("SELFTEST", "OK" if ok else "FAILED", "| work dir:", work)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
