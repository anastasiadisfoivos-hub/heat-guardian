#!/usr/bin/env python3
"""Writes ios/HeatGuardianTests/herday_vectors_app.json from HERDAY_SPEC.md §4 / §6 using the Python mirror
(tools/mirror_frames.py). The XCTest (HerDayTests.swift), tools/LinuxCheck.swift (Swift, run on Linux) and
mirror_frames.py all check their implementation against this one file.

    python3 -I ios/tools/gen_herday_vectors.py
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mirror_frames as M  # noqa: E402

IOS = os.path.dirname(HERE)
OUT = os.path.join(IOS, "HeatGuardianTests", "herday_vectors_app.json")

MARKET, CHURCH, WALK, PHARMACY, CAFE, DOCTOR, OTHER = 1, 2, 3, 4, 5, 6, 7


def item(day, kind, place=0, usual=None, suggested=None, direction=None, hot_from=0, hot_to=0, peak_c=None, heatwave_day=0):
    return dict(day=day, kind=kind, place=place, usual=usual, suggested=suggested, direction=direction,
                hot_from=hot_from, hot_to=hot_to, peak_c=peak_c, heatwave_day=heatwave_day)


def plan(t_out, t_in, heat_day=True, night_heat=False, wave_day=None, advice=None, date="2026-07-15"):
    hs = []
    for h in range(24):
        a = advice[h] if advice else ("AVOID" if (t_out[h] is not None and t_out[h] >= 32) else ("SHORT" if (t_out[h] is not None and t_out[h] >= 30) else "OK"))
        hs.append(dict(h=h, t_out=t_out[h], t_in=t_in[h], rh_in=40, advice=a, safe=a == "OK" and 7 <= h < 21))
    return dict(date=date, heat_day=heat_day, night_heat=night_heat, wave_day=wave_day, hours=hs)


def r1(x): return math.floor(x * 10 + 0.5) / 10


# HerDayDemo.swift tOutDay2 (Athens heat-wave day 2, constructed)
DAY2 = [28.6, 28.2, 27.9, 27.6, 27.4, 27.5, 27.9, 28.4, 28.9, 29.5, 30.6, 32.0,
        33.4, 34.8, 35.9, 36.4, 36.0, 35.0, 33.6, 32.1, 30.7, 29.4, 28.9, 28.6]
DAY2_IN = [r1(x) for x in M.indoor_sim(DAY2 + DAY2, "B")[-24:]]


def engine_cases():
    cases = []

    def case(name, p, outings, bed, day):
        r = M.hd_compute(p, outings, bed, day)
        cases.append(dict(name=name, plan=p, outings=outings, bed=bed, day=day,
                          expect=dict(hot=r["hot"], collisions=r["collisions"], air_open=r["air_open"],
                                      heatwave_day=r["heatwave_day"], items=r["items"],
                                      frames_hex=[M.hx(f) for f in M.day_plan_frames(r["items"], day)],
                                      brief=M.hd_brief(r["items"], day == 1))))
        return r

    # 1. the demo's tomorrow: market + café collide (go before 09:30 / 09:00), the 21:15 walk does not
    r = case("demo tomorrow (heat-wave day 2)", plan(DAY2, DAY2_IN, night_heat=max(DAY2_IN) >= 28, wave_day=2),
             [dict(place=MARKET, start=620, duration=30), dict(place=CAFE, start=1080, duration=60),
              dict(place=WALK, start=1275, duration=40)], 23 * 60 + 30, 1)
    assert r["items"][0]["suggested"] == 570 and r["items"][0]["direction"] == 1, r["items"]
    assert M.hd_brief(r["items"], True) == "Αύριο: αγορά πριν τις 09:30"

    # 2. direction 2: hot from 06:00 to 14:00, so no slot >= 07:00 ends before it -> after 14:30
    t = [26] * 6 + [31] * 8 + [29] * 10
    case("direction 2 (after the window)", plan(t, [27] * 24, wave_day=1), [dict(place=MARKET, start=600, duration=45)], 23 * 60, 0)

    # 3. no slot at all: hot all day -> collision kept, no OUTING_SHIFT, heat-wave item only
    case("no safe slot", plan([33] * 24, [31] * 24, wave_day=3), [dict(place=CHURCH, start=540, duration=60)], 23 * 60, 1)

    # 4. an earlier hot hour blocks the latest slot; long outing falls through to direction 2 with a midnight bed
    t = [25] * 7 + [30] + [27, 28] + [31] * 10 + [27] * 4
    case("earlier hot hour (1 h outing)", plan(t, [28] * 24), [dict(place=DOCTOR, start=720, duration=60)], 23 * 60, 1)
    case("earlier hot hour (150 min, bed 00:00)", plan(t, [28] * 24), [dict(place=WALK, start=720, duration=150)], 0, 1)
    case("earlier hot hour (150 min, bed 23:00)", plan(t, [28] * 24), [dict(place=WALK, start=720, duration=150)], 23 * 60, 1)

    # 5. AIR_OPEN: hot day, outdoor drops below indoor - 1 at 20:00; a mild day gets none
    t = [24] * 10 + [31] * 8 + [29, 29.5, 27, 26, 25, 24]
    case("air open 20:00", plan(t, [29.0] * 24, wave_day=1), [], 23 * 60, 1)
    case("mild day: no air, no heat-wave", plan([22] * 24, [24] * 24, heat_day=False), [dict(place=MARKET, start=600, duration=30)], 23 * 60, 1)

    # 6. AVOID marks an hour hot without t_out; t_out missing elsewhere; outing at the window end does not collide
    adv = ["OK"] * 12 + ["AVOID"] * 4 + ["OK"] * 8
    case("AVOID without t_out", plan([None] * 24, [27] * 24, heat_day=False, advice=adv),
         [dict(place=PHARMACY, start=780, duration=20), dict(place=CAFE, start=960, duration=30)], 23 * 60, 0)

    # 7. more than 6 collisions: 4 shifts + AIR + heat-wave (cap 6)
    t = [24] * 8 + [33] * 12 + [26] * 4
    outs = [dict(place=p, start=600 + 60 * i, duration=20) for i, p in enumerate([MARKET, CHURCH, WALK, PHARMACY, CAFE, DOCTOR, OTHER])]
    case("cap 6 items", plan(t, [29] * 24, wave_day=5), outs, 23 * 60, 1)

    # 8. overlap rule (Foivos, Nov 18): an outing collides when ANY part of [start, start + duration) is in a hot
    #    window, not only its start. 09:40 + 30 min reaches into the 10:00 window; 09:30 + 30 min ends at 10:00 (no).
    case("overlap: starts before the window", plan(DAY2, DAY2_IN, wave_day=2),
         [dict(place=MARKET, start=580, duration=30), dict(place=PHARMACY, start=570, duration=30)], 23 * 60, 1)
    #    an evening walk that starts in the cool after the window does not collide; one that starts before its end does
    case("overlap: ends exactly at the start / starts at the end", plan(DAY2, DAY2_IN, wave_day=2),
         [dict(place=WALK, start=1260, duration=40), dict(place=CAFE, start=1230, duration=45)], 23 * 60, 1)
    #    demo «hotter tomorrow» (heat-wave day 3, hot 08:00-19:00): church 08:30 (75 min) goes AFTER, market / café before
    D3 = [29.8, 29.4, 29.0, 28.7, 28.5, 28.6, 29.1, 29.7, 30.5, 31.6, 32.9, 34.1,
          35.3, 36.4, 37.1, 37.3, 36.4, 34.2, 31.3, 29.8, 29.0, 28.6, 28.3, 28.0]
    D3_IN = [r1(x) for x in M.indoor_sim(D3 + D3, "B")[-24:]]
    r = case("demo hotter tomorrow (heat-wave day 3): go after", plan(D3, D3_IN, night_heat=max(D3_IN) >= 28, wave_day=3),
             [dict(place=MARKET, start=620, duration=30), dict(place=CHURCH, start=510, duration=75),
              dict(place=CAFE, start=1080, duration=60), dict(place=WALK, start=1275, duration=40)], 23 * 60 + 30, 1)
    assert M.hd_brief(r["items"], True) == "Αύριο: εκκλησία μετά τις 19:30", r["items"]

    # 9. home outings are ignored
    case("home ignored", plan([31] * 24, [29] * 24, wave_day=1), [dict(place=0, start=600, duration=60)], 23 * 60, 1)
    return cases


def routine_cases():
    cases = []

    def case(name, samples, weekday):
        cases.append(dict(name=name, samples=samples, weekday=weekday, expect=M.rm_outings(samples, weekday)))

    mk = [dict(place=MARKET, weekday=wd, start=st, duration=du) for wd, st, du in
          [(2, 615, 30), (3, 625, 40), (4, 618, 30), (5, 630, 35), (6, 610, None), (7, 622, 30)]]
    case("daily market (6 weekdays) applies on Sunday", mk, 1)
    ch = [dict(place=CHURCH, weekday=1, start=510, duration=75), dict(place=CHURCH, weekday=1, start=520, duration=80)]
    case("church on Sundays: Sunday", ch, 1)
    case("church on Sundays: Monday", ch, 2)
    case("church once is not a habit", ch[:1], 1)
    walks = [dict(place=WALK, weekday=wd, start=st, duration=40) for wd in (2, 3, 4, 5) for st in (480, 1260)]
    case("morning and evening walks are two outings", walks, 3)
    case("no duration -> 60 min; clamp", [dict(place=CAFE, weekday=4, start=1080, duration=None),
                                         dict(place=CAFE, weekday=4, start=1090, duration=None),
                                         dict(place=DOCTOR, weekday=4, start=600, duration=5),
                                         dict(place=DOCTOR, weekday=4, start=610, duration=7)], 4)
    return cases


def main():
    dp = []
    for it, idx, n in [
        (item(1, 1, MARKET, 620, 570, 1, 10, 21, 36), 1, 3),
        (item(1, 1, CAFE, 1080, 540, 1, 10, 21, 35), 2, 3),
        (item(1, 2, suggested=1200), 3, 3),
        (item(0, 3, heatwave_day=2), 1, 1),
        (item(0, 1, WALK, None, 1290, 2, 14, 21, None), 1, 2),
        (item(1, 1, CHURCH, 510, 420, 1, 8, 24, 31), 6, 6),        # hot to 24 (until midnight) is allowed
        (item(1, 1, OTHER, 1439, 0, 2, 0, 1, 0), 1, 1),
    ]:
        dp.append(dict(item=it, index=idx, n=n, hex=M.hx(M.cmd_day_plan(it, idx, n))))
    bad = [
        dict(item=item(2, 3, heatwave_day=1), index=1, n=1, why="day 2", swift=True),
        dict(item=item(1, 3, heatwave_day=1), index=2, n=1, why="index > n", swift=True),
        dict(item=item(1, 3, heatwave_day=1), index=1, n=7, why="n > 6", swift=True),
        dict(item=item(1, 3, heatwave_day=1), index=0, n=1, why="index 0 with n 1", swift=True),
        dict(item=item(1, 1, MARKET, 1440, 570, 1, 10, 21), index=1, n=1, why="usual 24:00", swift=True),
        dict(item=item(1, 1, MARKET, 620, None, 1, 10, 21), index=1, n=1, why="kind 1 without suggestion", swift=True),
        dict(item=item(1, 3, heatwave_day=32), index=1, n=1, why="heat-wave day 32", swift=True),
        dict(item=item(1, 1, MARKET, 620, 570, 1, 15, 12), index=1, n=1, why="hot from > to", swift=True),
        dict(item=item(1, 0), index=1, n=1, why="kind 0", swift=False),
        dict(item=item(1, 4), index=1, n=1, why="kind 4", swift=False),
        dict(item=item(1, 1, 8, 620, 570, 1, 10, 21), index=1, n=1, why="place 8", swift=False),
    ]
    vis = [dict(edge=e, place=p, unix=u, hex=M.hx(M.cmd_visit(e, p, u))) for e, p, u in
           [(1, MARKET, 1789462320), (2, MARKET, 1789464120), (1, 0, 1789464600), (2, 0, 0), (1, OTHER, 0xFFFFFFFF)]]
    ev = []
    for seq, boot, unix, e, p, vu in [(41, 7, 1789462330, 1, MARKET, 1789462320), (42, 7, 1789464125, 2, MARKET, 1789464120),
                                      (65535, 65535, 0, 1, CAFE, 1789459000), (3, 1, 1789464600, 1, 0, 1789464600)]:
        ev.append(dict(seq=seq, boot=boot, unix=unix, edge=e, place=p, visit_unix=vu,
                       hex=M.hx(M.encode_event(M.visit_event(seq, boot, unix, e, p, vu)))))
    pi = []
    for seq, it in [(50, item(1, 1, MARKET, 620, 570, 1, 10, 21)), (51, item(1, 1, CAFE, 1080, 540, 1, 10, 21)),
                    (52, item(1, 2, suggested=1200)), (53, item(1, 3, heatwave_day=2)),
                    (54, item(0, 1, WALK, None, 1290, 2, 14, 21)), (55, item(0, 3, heatwave_day=31)),
                    (56, item(1, 1, CHURCH, 510, 420, 1, 8, 24))]:
        pi.append(dict(seq=seq, boot=7, unix=1789488000, item=it,
                       hex=M.hx(M.encode_event(M.plan_item_event(seq, 7, 1789488000, it)))))
    V = dict(note="App-side Her Day vectors produced by ios/tools/gen_herday_vectors.py (Python mirror of EcoFrames.swift "
                  "/ HerDay.swift / HerDayRoutine.swift) from HERDAY_SPEC.md §4/§6. Not the firmware's: compare with "
                  "fw/09_guardian/herday_vectors.json. Times are minutes of day; null = n/a (0xFF 0xFF / 0xFF on the wire). "
                  "Unused fields of kind 2/3 are 0. hot_to may be 24 (exclusive end at midnight), as band 0.9.8 accepts.",
             day_plan=dp, day_plan_clear=[dict(day=d, hex=M.hx(M.cmd_day_plan_clear(d))) for d in (0, 1)],
             day_plan_bad=bad, visit=vis, events_visit=ev, events_plan_item=pi,
             engine=engine_cases(), routine=routine_cases())
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(V, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("wrote", OUT, "engine cases", len(V["engine"]), "routine cases", len(V["routine"]))


if __name__ == "__main__":
    main()
