#!/usr/bin/env python3
"""Emit a SIMULATED 08_logger USB-serial capture (no board in this workspace).

The lines have exactly the firmware's formats (08_logger.ino): 48-hex 1 Hz record lines, '#' comment
lines (boot banner, "# S ..." status every 10 s, "# TIME ...", "# MARK ..."), optional raw 'R' quarter
lines, and optionally a 'dumpmin' section ("# FILE /log/min.bin" ... "# END"). Values are plausible
bench numbers, not measurements. Every record is packed by parse_log.pack_record (the Python twin of
hg_rec_pack, itself checked against the C code by test_parse_log.py).

  python3 sim_stream.py --seconds 600 -o sim_capture.txt [--with-ref] [--raw 20] [--dumpmin] [--bin s0001.bin]
"""
import argparse
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_log import pack_record, T_ABSENT, F_CHARGING, F_BLE, F_MARKER, F_TIME, F_MINUTE, F_BUTTON  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=600)
    ap.add_argument("-o", "--out", default="sim_capture.txt")
    ap.add_argument("--seed", type=int, default=20261116)
    ap.add_argument("--boot", type=int, default=3)
    ap.add_argument("--with-ref", action="store_true", help="simulate the second TMP117 (0x49) as present")
    ap.add_argument("--raw", type=int, default=0, help="also emit N seconds of raw 'R' lines at the start")
    ap.add_argument("--dumpmin", action="store_true", help="append a dumpmin section with the minute records")
    ap.add_argument("--bin", help="also write the 1 Hz records as a binary hour file (like /log/sNNNN.bin)")
    ap.add_argument("--unix0", type=int, default=1763287200, help="unix time sent with 'time' (default 2025-11-16 10:00 UTC)")
    a = ap.parse_args(argv)
    rnd = random.Random(a.seed)
    out = []
    t0 = 2840                       # first second tick after a ~2.8 s boot
    out.append(f"# Heat Guardian 08-logger-1.0.0  reset=POWER-ON/BROWN-OUT(0x00000000)  vbat=4.081 V")
    out.append(f"# BOOT boot={a.boot} t_ms=2311 fw=08-logger-1.0.0 reset=POWER-ON/BROWN-OUT rr=0x00000000 vbat=4.081 lowbat=0 "
               f"storage=OK(mounted) skin=1 ref={int(a.with_ref)} sht=1 imu=1 imu_lp=1 ppg=1 drv=1")
    out.append(f"# FILE boot={a.boot} t_ms=2390 path=/log/s0042.bin free_blocks=401")
    out.append("# ready in 2402 ms. Type help.")
    recs, mins = [], []
    vbat = 4.081
    t1 = 30.2
    acc = {}
    sync_at = 20
    for k in range(a.seconds):
        t = t0 + 1000 * k
        # donning transient: T1 approaches 33.4 with tau ~ 4 min
        t1 += (33.4 - t1) / 240.0 + rnd.gauss(0, 0.004)
        t2 = t1 - 2.6 + rnd.gauss(0, 0.004)
        tair = 24.1 + 0.3 * math.sin(k / 300.0) + rnd.gauss(0, 0.02)
        rh = 45 + int(round(rnd.gauss(0, 0.6)))
        moving = rnd.random() < 0.15
        hr_q = 2 if moving else (4 if rnd.random() < 0.85 else 3)
        hr = int(round(70 + 4 * math.sin(k / 90.0) + rnd.gauss(0, 1.5))) if hr_q >= 3 else (0 if rnd.random() < 0.5 else 92)
        pi = int(round(rnd.uniform(35, 65)))
        astd = int(round((rnd.uniform(0.02, 0.08) if moving else rnd.uniform(0.0004, 0.003)) * 1e4))
        z = int(round((-12 + rnd.gauss(0, 2)) * 100))     # 0.01 deg (log format v2)
        flags = F_BLE if k > 30 else 0
        marker, aux = 0, int(rnd.uniform(20000, 24000) / 4)
        if k == 0:
            marker, aux = 10, a.boot
        if k >= sync_at:
            flags |= F_TIME
        if k == sync_at:
            marker = 11
            out.append(f"# TIME boot={a.boot} t_ms={t - 400} unix={a.unix0} src=usb")
        if k == 45:
            marker = 1
            out.append(f"# MARK boot={a.boot} t_ms={t - 300} m=1 name=donned v=0 src=usb unix={a.unix0 + 25}")
        if k == 300:
            marker, flags = 9, flags | F_BUTTON
            out.append(f"# MARK boot={a.boot} t_ms={t - 600} m=9 name=button v=0 src=button unix={a.unix0 + 280}")
        if k == 420:
            marker, aux = 7, 3671
            out.append(f"# MARK boot={a.boot} t_ms={t - 500} m=7 name=oral v=3671 src=usb unix={a.unix0 + 400}")
        if marker:
            flags |= F_MARKER
        b = pack_record(t, int(round(t1 * 100)), int(round(t2 * 100)) if a.with_ref else T_ABSENT,
                        int(round(tair * 100)), rh, hr, hr_q, pi, astd, z, flags, marker, 105, aux)
        recs.append(b)
        out.append(b.hex())
        if k % 10 == 9:
            out.append(f"# S boot={a.boot} t_ms={t + 7} T1={t1:.2f} T2={'%.2f' % t2 if a.with_ref else 'nan'} Tair={tair:.2f} "
                       f"RH={rh} HR={hr} q={hr_q} PI={pi / 100:.2f} a={astd / 1e4:.4f} z={z / 100:.2f} bat={vbat:.2f} log=OK stack_free=2412")
        if a.raw and k < a.raw:     # raw lines interleave with the 1 Hz lines exactly as on the band
            blk = bytearray(308)
            blk[0:4] = (t - 1000).to_bytes(4, "little"); blk[4:6] = (100).to_bytes(2, "little"); blk[6:8] = (100).to_bytes(2, "little")
            for i in range(100):
                ir = int(110000 + 600 * math.sin(2 * math.pi * 1.17 * (k + i / 100.0)) + rnd.gauss(0, 30))
                blk[8 + 3 * i: 11 + 3 * i] = ir.to_bytes(3, "big")
            for q in range(4):
                out.append(f"R{q}{blk[77 * q:77 * (q + 1)].hex()}")
        # minute summary (as the firmware's minuteClose)
        m0 = t // 60000 * 60000
        acc.setdefault(m0, []).append((t1, t2, tair, rh, hr, hr_q, pi, astd, z, flags, marker, aux))
        vbat -= 0.00004
    for m0, rows in sorted(acc.items()):
        hrs = sorted(r[4] for r in rows if r[5] == 4 and r[4] > 0)
        hr, q = (hrs[len(hrs) // 2], 4) if len(hrs) >= 5 else (0, 2)
        fl = F_MINUTE
        for r in rows:
            fl |= r[9] & (F_BLE | F_BUTTON | F_CHARGING)
        if rows[-1][9] & F_TIME:
            fl |= F_TIME
        mk = next(((r[10], r[11]) for r in rows if r[10]), (0, 0))   # first marker of the minute, as minuteAdd()
        if mk[0]:
            fl |= F_MARKER
        mins.append(pack_record(m0, int(round(100 * sum(r[0] for r in rows) / len(rows))),
                                int(round(100 * sum(r[1] for r in rows) / len(rows))) if a.with_ref else T_ABSENT,
                                int(round(100 * sum(r[2] for r in rows) / len(rows))), int(round(sum(r[3] for r in rows) / len(rows))),
                                hr, q, int(round(sum(r[6] for r in rows) / len(rows))), int(round(sum(r[7] for r in rows) / len(rows))),
                                int(round(sum(r[8] for r in rows) / len(rows))), fl, mk[0], int(round((vbat - 2.0) * 100)), mk[1],
                                astd_min=int(round(math.sqrt(sum(r[7] ** 2 for r in rows) / len(rows))))))   # SIMULATED whole-minute a_std
    if a.dumpmin:
        out.append(f"# DUMP START files=1 boot={a.boot} t_ms={t0 + 1000 * a.seconds} unix={a.unix0 + a.seconds}")
        out.append(f"# FILE /log/min.bin size={24 * len(mins)}")
        out.extend(m.hex() for m in mins)
        out.append(f"# END /log/min.bin bytes={24 * len(mins)}")
        out.append("# DUMP DONE")
    with open(a.out, "w") as fh:
        fh.write("\n".join(out) + "\n")
    if a.bin:
        with open(a.bin, "wb") as fh:
            fh.write(pack_record(t0 - 450, flags=F_MARKER, marker=12, aux=a.boot))   # file header record
            fh.write(b"".join(recs))
    print(f"SIMULATED stream: {len(recs)} records, {len(mins)} minute records -> {a.out}" + (f", {a.bin}" if a.bin else ""))
    return recs, mins


if __name__ == "__main__":
    main()
