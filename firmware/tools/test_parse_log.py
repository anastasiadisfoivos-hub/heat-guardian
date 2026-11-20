#!/usr/bin/env python3
"""Tests for parse_log.py (acceptance 3 of brief B6 Part A). Run: python3 test_parse_log.py
1. Python unpack == the C packer on 32 vectors from test_record.c (record_vectors.json).
2. SIMULATED 10-min stream -> 600 rows, 0 CRC errors, 0 gaps, markers/time/boot decoded.
3. 5 record lines deleted -> 595 rows and a gap report of exactly 5 gaps / 5 missing seconds.
4. one corrupted hex digit -> 1 CRC error, that record dropped.
5. Serial-Monitor timestamps in front of every line do not matter.
6. binary hour file (+ header record) parses to the same 600 rows; dumpmin section -> 10 minute rows.
7. raw quarter lines reassemble into 100-sample blocks; a missing quarter drops only that block.
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parse_log  # noqa: E402
import sim_stream  # noqa: E402

fails = 0


def check(cond, msg):
    global fails
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        fails += 1


def run(paths, tmp, name):
    out = os.path.join(tmp, name + ".parquet")
    p, df, gaps = parse_log.main(paths + ["-o", out])
    return p, df, gaps


def main():
    tmp = tempfile.mkdtemp(prefix="hg08_")
    # 1. C vectors
    vec_path = os.path.join(HERE, "record_vectors.json")
    if not os.path.exists(vec_path):
        subprocess.check_call(["gcc", "-std=c99", "-O2", "-I" + os.path.join(HERE, "..", "08_logger"),
                               os.path.join(HERE, "test_record.c"), "-o", os.path.join(tmp, "tr")])
        subprocess.check_call([os.path.join(tmp, "tr"), vec_path])
    v = json.load(open(vec_path))
    check(parse_log.crc8(b"123456789") == v["crc8_check_123456789"] == 0xF4, "crc8 check value 0xF4 matches C")
    bad = 0
    for r in v["records"]:
        f, ok, ver = parse_log.unpack_record(bytes.fromhex(r["hex"]))
        exp = (r["t_ms"], r["t1"], r["t2"], r["tair"], r["rh"], r["hr"], r["hr_q"], r["pi"], r["astd"], r["zangle_c100"],
               r["flags"], r["marker"], r["dc8"], r["aux"], r["astd_min"])
        if not ok or tuple(f) != exp or ver != r["ver"]:
            bad += 1
        if ver == 2:
            if parse_log.pack_record(*exp).hex() != r["hex"]:
                bad += 1
        elif parse_log.pack_record_v1(*exp[:9], exp[9] // 100, *exp[10:14]).hex() != r["hex"]:
            bad += 1
    nv1 = sum(r["ver"] == 1 for r in v["records"])
    check(bad == 0 and nv1 > 0, f"Python pack/unpack == C hg_rec_pack/unpack on {len(v['records'])} vectors, {nv1} of them v1 ({bad} mismatches)")

    # 2. clean 10-minute stream
    cap = os.path.join(tmp, "sim.txt")
    sim_stream.main(["--seconds", "600", "-o", cap, "--dumpmin", "--bin", os.path.join(tmp, "s0042.bin"), "--raw", "5"])
    p, df, gaps = run([cap], tmp, "clean")
    sec = df[~df["is_minute"]]
    check(len(sec) == 600, f"600 one-hertz rows (got {len(sec)})")
    check(p.crc_errors == 0, f"0 CRC errors (got {p.crc_errors})")
    check(len(gaps) == 1 and gaps[0]["gaps"] == 0, f"no gaps (got {[g['gaps'] for g in gaps]})")
    check(set(sec["boot"]) == {3}, f"boot decoded = 3 (got {set(sec['boot'])})")
    check(sec["unix_s"].notna().all(), "unix time attached to every row (TIME sync, back-dated before the sync)")
    first = sec.iloc[0]
    check(abs(first["unix_s"] - (1763287200 - (20 * 1000 - 400) / 1000.0)) < 1e-6, f"unix of the first row back-computed ({first['unix_s']})")
    names = list(df[df["marker"] > 0]["marker_name"])
    check(names[:5] == ["boot", "time", "donned", "button", "oral"], f"markers decoded in order ({names})")
    oral = df[df["marker"] == 7]["marker_value"].iloc[0]
    check(abs(oral - 36.71) < 1e-9, f"oral reading value 36.71 (got {oral})")
    check(sec["T2"].isna().all() and sec["T1"].notna().all(), "T2 absent -> NaN, T1 present")
    for c in ["T1", "T2", "T_air_meas", "RH_meas", "HR_meas", "hr_quality", "PI", "a_std_g", "zangle_deg", "button", "charging", "marker"]:
        if c not in df.columns:
            check(False, f"column {c} present")
    check(all(c in df.columns for c in ["T1", "T2", "T_air_meas", "RH_meas", "HR_meas", "hr_quality", "PI", "a_std_g",
                                         "zangle_deg", "button", "charging", "marker"]), "B1 sensor-model column names present")
    mins = df[df["is_minute"]]
    check(len(mins) == 10 or len(mins) == 11, f"dumpmin section -> minute rows (got {len(mins)})")
    check(mins["vbat"].notna().all(), "minute rows carry VBAT")
    check((sec["zangle_deg"] * 100 % 100 != 0).any() and (sec["fmt"] == 2).all(), "v2: z-angle at 0.01 deg (fractional degrees present), fmt 2")
    plain = mins[~mins["marker"].isin(list(parse_log.MIN_AUX_MARKERS))]
    check(len(plain) >= 8 and plain["a_std_min_g"].notna().all() and sec["a_std_min_g"].isna().all(),
          f"v2 minute rows carry the whole-minute a_std (a_std_min_g; {len(mins) - len(plain)} boot/oral minutes keep their marker value instead); 1 Hz rows NaN")
    # old (v1, 1.1.1) and new (v2) records in one file: both parse
    binm = os.path.join(tmp, "s0001.bin")
    old = [parse_log.pack_record_v1(1000 * k, t1=3300, zangle=-12, astd=25) for k in range(1, 6)]
    old_min = parse_log.pack_record_v1(60000, t1=3300, zangle=-12, flags=parse_log.F_MINUTE | parse_log.F_MARKER, marker=7, aux=3671, dc8=200)
    new = [parse_log.pack_record(1000 * k, t1=3301, zangle_c100=-1234, astd=25) for k in range(6, 11)]
    new_min = parse_log.pack_record(120000, t1=3301, zangle_c100=-1234, flags=parse_log.F_MINUTE, dc8=200, astd_min=31)
    open(binm, "wb").write(parse_log.pack_record_v1(5, flags=parse_log.F_MARKER, marker=12, aux=9) + b"".join(old) + old_min + b"".join(new) + new_min)
    pm, dm, _ = run([binm], tmp, "mixed")
    o, n = dm[dm["fmt"] == 1], dm[dm["fmt"] == 2]
    check(pm.crc_errors == 0 and len(o) == 6 and len(n) == 6 and set(dm["boot"]) == {9}, f"v1 + v2 records in one file: 0 CRC errors, 6 + 6 rows, boot 9 (got {len(o)} + {len(n)}, {pm.crc_errors})")
    check((o["zangle_deg"] == -12.0).all() and (n["zangle_deg"] == -12.34).all(), "z: v1 whole degrees, v2 0.01 deg")
    om = o[o["is_minute"]].iloc[0]; nm = n[n["is_minute"]].iloc[0]
    check(abs(om["marker_value"] - 36.71) < 1e-9 and np.isnan(om["a_std_min_g"]) and abs(nm["a_std_min_g"] - 0.0031) < 1e-12,
          "v1 minute keeps its oral value; v2 minute carries a_std_min 0.0031 g")
    check(len(p.raw_blocks) == 5 and all(b[3] == 100 for b in p.raw_blocks), f"5 raw blocks of 100 samples (got {len(p.raw_blocks)})")

    # 3. delete 5 non-adjacent record lines
    lines = open(cap).read().splitlines()
    rec_idx = [i for i, l in enumerate(lines) if parse_log.REC_RE.fullmatch(l)]
    drop = {rec_idx[k] for k in (50, 150, 250, 350, 450)}
    cap5 = os.path.join(tmp, "sim_minus5.txt")
    open(cap5, "w").write("\n".join(l for i, l in enumerate(lines) if i not in drop) + "\n")
    p5, df5, g5 = run([cap5], tmp, "minus5")
    sec5 = df5[~df5["is_minute"]]
    check(len(sec5) == 595, f"595 rows after deleting 5 lines (got {len(sec5)})")
    check(g5[0]["gaps"] == 5 and g5[0]["missing_s"] == 5, f"gap report: 5 gaps, 5 s missing (got {g5[0]['gaps']}, {g5[0]['missing_s']})")

    # 4. corrupt one hex digit
    capc = os.path.join(tmp, "sim_corrupt.txt")
    lc = list(lines)
    i = rec_idx[123]
    lc[i] = lc[i][:10] + ("0" if lc[i][10] != "0" else "1") + lc[i][11:]
    open(capc, "w").write("\n".join(lc) + "\n")
    pc, dfc, gc = run([capc], tmp, "corrupt")
    check(pc.crc_errors == 1 and len(dfc[~dfc["is_minute"]]) == 599 and gc[0]["gaps"] == 1, f"1 corrupted line -> 1 CRC error, row dropped, 1 gap (got {pc.crc_errors})")

    # 5. Serial Monitor timestamps
    capt = os.path.join(tmp, "sim_ts.txt")
    open(capt, "w").write("\n".join(f"10:{(k // 60) % 60:02d}:{k % 60:02d}.123 -> {l}" for k, l in enumerate(lines)) + "\n")
    pt, dft, gt = run([capt], tmp, "ts")
    check(len(dft[~dft["is_minute"]]) == 600 and pt.crc_errors == 0, "timestamped capture parses identically")

    # 6. binary file + dedupe with the live capture
    pb, dfb, gb = run([os.path.join(tmp, "s0042.bin")], tmp, "bin")
    check(len(dfb) == 600 and pb.crc_errors == 0, f"binary hour file -> 600 rows (got {len(dfb)})")
    check(set(dfb["boot"]) == {3}, "binary file: boot from its header record")
    pbb, dfbb, _ = run([os.path.join(tmp, "s0042.bin"), cap], tmp, "both")
    check(len(dfbb[~dfbb["is_minute"]]) == 600, f"live + binary of the same seconds de-duplicate to 600 (got {len(dfbb[~dfbb['is_minute']])})")

    # 6b. hour file appended across a reset (since [B6a-fix]): a second header record mid-file
    b1 = [parse_log.pack_record(1000 * k + 500, t1=3300) for k in range(1, 11)]
    b2 = [parse_log.pack_record(1000 * k + 700, t1=3310) for k in range(1, 6)]
    binp = os.path.join(tmp, "s0050.bin")
    open(binp, "wb").write(parse_log.pack_record(10, flags=parse_log.F_MARKER, marker=12, aux=7) + b"".join(b1) +
                           parse_log.pack_record(20, flags=parse_log.F_MARKER, marker=12, aux=8) + b"".join(b2))
    pa, dfa, ga = run([binp], tmp, "append")
    check(list(dfa.groupby("boot").size()) == [10, 5] and sorted(set(dfa["boot"])) == [7, 8],
          f"appended file: rows split by boot 7 (10) / 8 (5) (got {dict(dfa.groupby('boot').size())})")
    check(all(g["gaps"] == 0 for g in ga), "appended file: no false gaps across the reset")

    # 7. raw quarter lost
    lr = [l for l in lines if not l.startswith("R2") or l != next(x for x in lines if x.startswith("R2"))]
    capr = os.path.join(tmp, "sim_raw.txt")
    open(capr, "w").write("\n".join(lr) + "\n")
    pr, _, _ = run([capr], tmp, "raw")
    check(len(pr.raw_blocks) == 4, f"one raw quarter missing -> that block dropped, 4 kept (got {len(pr.raw_blocks)})")

    # 8. 0.9.10 FS-HEAL: events_<gen>.txt copied off the band is read as an events log (legacy names too), junk names are not
    for nm in ("events_3.txt", "events2.txt", "events.txt"):
        evp = os.path.join(tmp, nm)
        open(evp, "w").write("BOOT boot=9 t_ms=10\nTIME boot=9 t_ms=5000 unix=1763280000\n")
        pe = parse_log.Parser()
        pe.parse(evp)
        check(pe.time_syncs.get(9) == [(5000, 1763280000)], f"{nm}: parsed as an events log (TIME sync found)")
    check(parse_log.EVENTS_GEN_RE.fullmatch("events_12.txt") and not parse_log.EVENTS_GEN_RE.fullmatch("events_0.txt")
          and not parse_log.EVENTS_GEN_RE.fullmatch("events_x.txt"), "events_<gen>.txt name pattern (gen >= 1)")

    print("TEST_PARSE_LOG:", "FAIL" if fails else "PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
