#!/usr/bin/env python3
"""SYNTHETIC 3-day wear-test capture for the wear_exam.py self-test. NOT DATA, NOT EVIDENCE.

Built on fw/tools/sim_stream.py: the same record packer (sim_stream.pack_record = parse_log.pack_record, the
Python twin of hg_rec_pack) and the same text formats as 08_logger (48-hex record lines, '# ...' lines, dump
sections '# FILE ... # END', 'E ' event lines). sim_stream itself emits a 10-min bench capture; this script
drives the same packer through the wear protocol (wear/PROTOCOL.md): donning, loose tests, room tests,
shower, charging + dumps, out/home, walks, hot room, fan, sleep, oral sessions, one watchdog reset, a 3-hour
hole in the 1 Hz files, and a short older-relative session. The physics is a crude first-order caricature
(numbers from R2 §2.2/§6 only so the exam's code paths are exercised).

  python3 wear/selftest/make_synth_wear.py OUT_DIR [--seed 1]
"""
import argparse, math, os, random, sys
import datetime as dt
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "fw", "tools"))
import sim_stream                                              # noqa: E402  (format source of truth)
from sim_stream import pack_record, T_ABSENT, F_CHARGING, F_MARKER, F_TIME, F_MINUTE, F_BUTTON  # noqa: E402

TZ = ZoneInfo("Europe/Athens")
F_IMPACT = 0x08
_T = []
for i in range(256):
    c = i
    for _ in range(8):
        c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    _T.append(c)


def fast_pack(*a, **k):
    """pack_record with a table CRC (identical bytes; checked against sim_stream.pack_record below)"""
    from parse_log import REC_STRUCT
    t_ms, t1, t2, tair, rh, hr, hq, pi, astd, z, flags, marker, dc8, aux = a
    body = REC_STRUCT.pack(t_ms & 0xFFFFFFFF, t1, t2, tair, rh, hr, hq, pi, astd, z, flags, marker, dc8, aux)
    c = 0
    for b in body:
        c = _T[c ^ b]
    return body + bytes([c])


def L(day, hhmm):
    """local Athens time on Nov <day> 2026 -> unix seconds"""
    h, m = map(int, hhmm.split(":"))
    return int(dt.datetime(2026, 11, day, h, m, tzinfo=TZ).timestamp())


def build_schedule():
    S = []   # (unix, kind, arg)
    S += [(L(16, "15:20"), "boot", ("POWER-ON/BROWN-OUT", 7)), (L(16, "15:21"), "time", None), (L(16, "15:30"), "mark", 1)]
    for day in (16, 17, 18):
        first = day == 16
        if not first:
            S += [(L(day, "06:50") + (day - 17) * 300, "press", "WAKE"), (L(day, "06:51"), "act", "rest"),
                  (L(day, "07:00"), "oral", 36.45 + 0.05 * (day - 16)), (L(day, "07:02"), "oral", 36.5 + 0.05 * (day - 16)),
                  (L(day, "07:04"), "pulse", None), (L(day, "07:20"), "dump", 4), (L(day, "07:40"), "mark", 5),
                  (L(day, "07:40") + 20, "press", "WALK_START"), (L(day, "07:40") + 40, "loc", "out_walk"),
                  (L(day, "07:56"), "press", "WALK_END"), (L(day, "07:56") + 10, "loc", "school"),
                  (L(day, "10:00"), "press", "SPORT_START"), (L(day, "10:00") + 5, "act", "active"),
                  (L(day, "10:45"), "press", "SPORT_END"), (L(day, "10:45") + 5, "act", "rest"),
                  (L(day, "14:10"), "press", "WALK_START"), (L(day, "14:10") + 5, "loc", "out_walk"),
                  (L(day, "14:30"), "press", "WALK_END"),
                  (L(day, "14:32"), "mark", 6) if day != 18 else (L(day, "14:32"), "press", "HOME"),   # Wed: diary fallback
                  (L(day, "14:32") + 5, "loc", "home"),
                  (L(day, "15:30"), "mark", 3), (L(day, "15:45"), "mark", 1)]
            if day == 18:
                S += [(L(18, "12:05"), "impact", None)]
        else:
            S += [(L(16, "17:00"), "mark", 5), (L(16, "17:01"), "press", "WALK_START"), (L(16, "17:01") + 5, "loc", "out_walk"),
                  (L(16, "17:30"), "press", "WALK_END"), (L(16, "17:32"), "mark", 6), (L(16, "17:32") + 5, "loc", "home"),
                  (L(16, "18:00"), "mark", 3), (L(16, "18:15"), "mark", 1)]
        S += [(L(day, "16:30"), "oral", 36.7 + 0.03 * (day - 16)), (L(day, "16:32"), "oral", 36.75), (L(day, "16:34"), "pulse", None)]
        if not first:
            S += [(L(day, "17:00"), "press", "HOT_START"), (L(day, "17:00") + 5, "loc", "hot"),
                  (L(day, "17:30"), "press", "HOT_END"), (L(day, "17:30") + 5, "loc", "home"),
                  (L(day, "18:00"), "press", "FAN_START"), (L(day, "18:00") + 5, "loc", "fan"),
                  (L(day, "18:15"), "press", "FAN_END"), (L(day, "18:15") + 5, "loc", "home"),
                  (L(day, "21:00"), "mark", 2), (L(day, "21:10"), "mark", 1)]
        S += [(L(day, "18:50"), "mark", 2), (L(day, "19:00"), "mark", 1),
              (L(day, "19:30"), "press", "MEAL_START"), (L(day, "19:55"), "press", "MEAL_END"),
              (L(day, "20:00"), "mark", 3), (L(day, "20:00") + 30, "charge", 1), (L(day, "20:30"), "dump", 5),
              (L(day, "22:00"), "charge", 0), (L(day, "22:02"), "mark", 1),
              (L(day, "22:20"), "oral", 36.6), (L(day, "22:22"), "oral", 36.62), (L(day, "22:24"), "pulse", None),
              (L(day, "22:30"), "mark", 4), (L(day, "22:45"), "mark", 1),
              (L(day, "23:10") + (day - 16) * 600, "press", "SLEEP"), (L(day, "23:11") + (day - 16) * 600, "act", "sleep")]
    S += [(L(18, "03:10"), "boot", ("WATCHDOG", 8))]                 # time lost until the 07:20 dump resyncs it
    S += [(L(18, "07:19"), "time", None)]
    S += [(L(19, "06:45"), "press", "WAKE"), (L(19, "06:46"), "act", "rest"), (L(19, "07:00"), "oral", 36.55),
          (L(19, "07:02"), "oral", 36.6), (L(19, "07:04"), "pulse", None), (L(19, "07:20"), "dump", 4),
          (L(19, "07:40"), "mark", 5), (L(19, "07:41"), "loc", "school"), (L(19, "13:00"), "mark", 6), (L(19, "13:00") + 5, "loc", "home"),
          (L(19, "13:30"), "mark", 3),
          (L(19, "14:00"), "relative", 78), (L(19, "14:01"), "mark", 1), (L(19, "14:40"), "mark", 2), (L(19, "14:50"), "mark", 1),
          (L(19, "16:30"), "mark", 3), (L(19, "16:31"), "relative_end", None), (L(19, "16:40"), "dump", 5), (L(19, "16:45"), "end", None)]
    S.sort(key=lambda x: x[0])
    return S


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    rnd = random.Random(a.seed)
    # sanity: the fast packer equals sim_stream's packer
    for k in range(50):
        args = (k * 1000, 3300 + k, 3000, 2200, 45, 70, 4, 120, 30, -10, F_TIME, 0, 107, 5000)
        assert fast_pack(*args) == pack_record(*args), "packer mismatch"
    S = build_schedule()
    t_start, t_end = S[0][0], [s[0] for s in S if s[1] == "end"][0]
    st = dict(worn=0, act="rest", loc="home", charging=0, relative=False)
    T1, T2, TA = 21.0, 21.0, 21.0
    vbat = 4.12
    boot, boot_t0 = None, None
    time_valid = False
    events, hour_files, minute_recs, diary = [], {}, [], []
    seq = [10]
    cur_file = {}
    minacc = {}
    si = 0
    pending = []      # markers to put into the next record
    zs, zt = -10.0, 0
    hr_true = 70.0
    dumped_upto = {}  # file -> True once dumped
    out_text = {}
    hole = (L(17, "09:00"), L(17, "12:00"))     # 1 Hz files of these hours deleted before a dump (test min.bin fallback)

    def ev(line):
        events.append(line)

    def tms(u):
        return int((u - boot_t0) * 1000) + 2840

    def flush_minute(key):
        rows = minacc.pop(key)
        b, m0 = key
        n = len(rows)
        ok = sorted(r[5] for r in rows if r[6] == 4 and r[5] > 0)
        if len(ok) >= 5:
            hr, q = ok[len(ok) // 2], 4
        else:
            qs = [r[6] for r in rows if r[6] <= 4]
            q = max(set(qs), key=qs.count) if qs else 255
            hr = 0
        fl = F_MINUTE
        for r in rows:
            fl |= r[10] & (F_BUTTON | F_CHARGING | F_IMPACT)
        fl |= rows[-1][10] & F_TIME
        mk = next(((r[11], r[13]) for r in rows if r[11] and r[11] != 12), (0, 0))
        if mk[0]:
            fl |= F_MARKER
        mean = lambda i: sum(r[i] for r in rows) / n
        t2s = [r[2] for r in rows if r[2] != T_ABSENT]
        minute_recs.append(fast_pack(m0, int(round(mean(1))), int(round(sum(t2s) / len(t2s))) if t2s else T_ABSENT,
                                     int(round(mean(3))), int(round(mean(4))), hr, q, int(round(mean(7))),
                                     int(round(mean(8))), int(round(mean(9))), fl, mk[0], int(round((vbat - 2.0) * 100)), mk[1]))

    def do_dump(u):
        lines = [f"# DUMP START mode=new files={len(hour_files)} boot={boot} t_ms={tms(u)} unix={int(u) if time_valid else 0}",
                 "# FILE /log/events.txt size=%d" % sum(len(e) + 1 for e in events)]
        lines += ["E " + e for e in events]
        lines.append("# END /log/events.txt")
        for name in sorted(hour_files):
            if dumped_upto.get(name):
                continue
            recs, u0, u1 = hour_files[name]
            if u0 < hole[1] and u1 > hole[0] and u1 < u:
                if name not in dumped_upto:
                    ev(f"DELETE {name} size={24 * len(recs)} UNDUMPED")
                dumped_upto[name] = True
                continue
            lines.append(f"# FILE {name} size={24 * len(recs)}")
            lines += [r.hex() for r in recs]
            lines.append(f"# END {name} bytes={24 * len(recs)}")
            if u1 < u - 5:
                dumped_upto[name] = True
        lines.append(f"# FILE /log/min.bin size={24 * len(minute_recs)}")
        lines += [r.hex() for r in minute_recs]
        lines.append("# END /log/min.bin")
        lines.append("# DUMP DONE files=%d" % len(hour_files))
        loc = dt.datetime.fromtimestamp(u, TZ).strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(a.out, f"dumpnew_{loc}.txt"), "w") as f:
            f.write("\n".join(lines) + "\n")

    u = t_start
    while u < t_end:
        while si < len(S) and S[si][0] <= u:
            _, kind, arg = S[si]
            si += 1
            if kind == "boot":
                for key in list(minacc):
                    flush_minute(key)
                boot, boot_t0, time_valid = arg[1], u, False
                ev(f"BOOT boot={boot} t_ms=2311 fw=08-logger-1.1.1 reset={arg[0]} rr=0x0 vbat={vbat:.3f} lowbat=0 quick_boots=0 bootloop=0 storage=OK(mounted) jedec=c84015")
                pending.append((10, boot))
            elif kind == "time":
                time_valid = True
                ev(f"TIME boot={boot} t_ms={tms(u)} unix={u} src=usb")
                pending.append((11, 0))
            elif kind == "mark":
                m = arg
                st["worn"] = {1: 2, 2: 1, 3: 0, 4: 0}.get(m, st["worn"])
                if m == 5: st["loc"] = "out_walk"
                if m == 6: st["loc"] = "home"
                ev(f"MARK boot={boot} t_ms={tms(u)} m={m} name=x v=0 src=usb unix={u if time_valid else 0}")
                pending.append((m, 0))
            elif kind == "press":
                ev(f"MARK boot={boot} t_ms={tms(u)} m=9 name=button v=0 src=button unix={u if time_valid else 0}")
                pending.append((9, 0))
                if arg != "MEAL_END" or u < L(18, "00:00"):        # one press left without a diary line (tests matching)
                    diary.append((u + rnd.randint(-180, 180), arg, ""))
            elif kind == "oral":
                v = int(round(arg * 100))
                ev(f"MARK boot={boot} t_ms={tms(u)} m=7 name=oral v={v} src=usb unix={u if time_valid else 0}")
                pending.append((7, v))
            elif kind == "pulse":
                diary.append((u, "PULSE", str(int(round(hr_true + rnd.gauss(0, 2))))))
            elif kind == "act":
                st["act"] = arg
            elif kind == "loc":
                st["loc"] = arg
            elif kind == "charge":
                st["charging"] = arg
            elif kind == "impact":
                st["impact"] = u
            elif kind == "relative":
                st["relative"] = True
                diary.append((u, "RELATIVE_START", str(arg)))
            elif kind == "relative_end":
                st["relative"] = False
                diary.append((u, "RELATIVE_END", ""))
            elif kind == "dump":
                st["dump_until"] = u + 180
                do_dump(u)
        # ---------------- physics (1 s)
        hour = dt.datetime.fromtimestamp(u, TZ).hour
        loc, act, worn = st["loc"], st["act"], st["worn"]
        if loc == "out_walk":
            env, act_now = 15.5, "walk"
        elif loc == "school":
            env, act_now = 20.5, act if act != "sleep" else "rest"
        elif loc == "hot":
            env, act_now = 28.0, "rest"
        else:
            env, act_now = (20.0 if act == "sleep" else 21.5), act
        usb = st["charging"] or u < st.get("dump_until", 0)
        if worn and not usb:
            t1ss = (34.2 if act_now == "sleep" else 33.6 + 0.12 * (env - 21.5) - (0.8 if act_now == "walk" else 0.0)) - (1.0 if worn == 1 else 0.0)
            if st["relative"]:
                t1ss -= 0.6
            r = 0.38 if worn == 2 else 0.22
            if loc == "fan":
                r, t1ss = 0.48, t1ss - 0.3
            t2ss = t1ss - r * (t1ss - env)
            c = 0.15 if worn == 2 else 0.10
            tass = env + c * (T1 - env) + (1.0 if act_now == "sleep" else 0.0)
            tau1, tau2 = 420.0, 360.0
        else:
            t1ss = t2ss = tass = env
            tau1, tau2 = 180.0, 240.0
        T1 += (t1ss - T1) / tau1 + rnd.gauss(0, 0.004)
        T2 += (t2ss - T2) / tau2 + rnd.gauss(0, 0.004)
        TA += (tass - TA) / 90.0 + rnd.gauss(0, 0.01)
        hr_true = {"sleep": 58, "rest": 70, "active": 88, "walk": 104}[act_now] + (6 if loc == "hot" else 0) + (4 if st["relative"] else 0)
        if not worn or usb:
            q, hr, pi, dc = 0, 0, 2, 1200
        else:
            p = rnd.random()
            if worn == 1:
                q = 4 if p < 0.3 else (1 if p < 0.8 else 3)
                pi, dc = 4, 140000
            elif act_now == "walk":
                q = 4 if p < 0.1 else 2
                pi, dc = 90, 108000
            elif act_now == "active":
                q = 4 if p < 0.35 else 2
                pi, dc = 100, 110000
            else:
                q = 4 if p < (0.62 if st["relative"] else 0.82) else 3
                pi, dc = (180 if loc == "hot" else 120), 110000
            hr = int(round(hr_true + rnd.gauss(0, 2))) if q == 4 else 0
        # motion
        if not worn or usb:
            astd, z = 0.0005 + abs(rnd.gauss(0, 0.0001)), 88
        elif act_now == "sleep":
            astd = 0.0012 + abs(rnd.gauss(0, 0.0002))
            if rnd.random() < 1 / 2400:
                zs = max(-80, min(80, zs + rnd.choice([-1, 1]) * rnd.uniform(25, 50)))
                astd = 0.06
            zs = float(round(zs))          # lying still: the 5-s median sits inside one 1-degree log step
            z = zs + rnd.gauss(0, 0.15)
        elif act_now == "walk":
            astd, z = 0.12 + abs(rnd.gauss(0, 0.03)), -20 + 15 * math.sin(u / 2.0)
        else:
            astd = (0.04 if act_now == "active" else 0.006) * math.exp(rnd.gauss(0, 0.4))
            zs = max(-70, min(70, zs + rnd.gauss(0, 0.6)))
            z = zs
        if st.get("impact") and 0 <= u - st["impact"] < 2:
            astd = 0.5
        flags = (F_TIME if time_valid else 0) | (F_CHARGING if usb else 0) | (F_IMPACT if st.get("impact") and u == st["impact"] else 0)
        vbat += (0.35 / 3600 if usb else -0.011 / 3600)
        vbat = min(vbat, 4.15)
        marker, aux = 0, int(rnd.uniform(20000, 24000) / 4)
        if pending:
            marker, v = pending.pop(0)
            flags |= F_MARKER | (F_BUTTON if marker == 9 else 0)
            aux = v if marker in (7, 10) else aux
        t = tms(u)
        rec_args = (t, int(round(T1 * 100)), int(round(T2 * 100)), int(round(TA * 100)),
                    max(0, min(100, int(round(45 + rnd.gauss(0, 0.6) + (20 if loc == "out_walk" else 0))))),
                    max(0, min(255, hr)), q, pi, max(0, min(65534, int(round(astd * 1e4)))), max(-90, min(90, int(round(z)))),
                    flags, marker, max(0, min(255, dc // 1024)), aux)
        b = fast_pack(*rec_args)
        hidx = t // 3600000
        key = (boot, hidx)
        if key not in cur_file:
            name = "/log/s%04d.bin" % seq[0]
            seq[0] += 1
            cur_file[key] = name
            hour_files[name] = [[fast_pack(t - 450, T_ABSENT, T_ABSENT, T_ABSENT, 255, 0, 255, 0, 0, 0, F_MARKER, 12, 0, boot)], u, u]
        hf = hour_files[cur_file[key]]
        hf[0].append(b)
        hf[2] = u
        mk = (boot, t // 60000 * 60000)
        for k_ in [k for k in minacc if k != mk]:
            flush_minute(k_)
        minacc.setdefault(mk, []).append(rec_args)
        u += 1
    for k_ in list(minacc):
        flush_minute(k_)
    with open(os.path.join(a.out, "diary.csv"), "w") as f:
        f.write("date,time,code,value,note\n")
        for ut, code, val in sorted(diary):
            d = dt.datetime.fromtimestamp(ut, TZ)
            note = "\"grandmother, female\"" if code == "RELATIVE_START" else ""
            f.write(f"{d:%Y-%m-%d},{d:%H:%M},{code},{val},{note}\n")
    print(f"SYNTHETIC wear capture -> {a.out}: {sum(len(v[0]) for v in hour_files.values())} 1 Hz records, "
          f"{len(minute_recs)} minute records, {len(events)} events, {len(diary)} diary lines")


if __name__ == "__main__":
    main()
