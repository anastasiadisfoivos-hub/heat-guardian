"""Manager rule (B4-fix2): never instruct an action during the wearer's sleep window."""
import os

import numpy as np

from tomorrow import advice_gr as A, plan, demo
from tomorrow.routine import RoutineTemplate

HERE = os.path.dirname(os.path.abspath(__file__))
HOURS = [{"h": h, "advice": "OK", "safe": 8 <= h < 18} for h in range(24)]


def mins(at):
    hh, mm = at.split(":")
    return int(hh) * 60 + int(mm)


def build(win_h, sleep=(1380, 420), close=450):
    sched = []
    lines, ids = A.build(HOURS, False, True, win_h, False, [], sleep_window=sleep, close_minute=close, schedule=sched)
    return ids, sched


def test_hour_outside_sleep_uses_timed_string():
    ids, sched = build(21)
    assert "NIGHT_HEAT_T" in ids and "OPEN_AT_BEDTIME" not in ids
    assert sched[0] == {"id": "NIGHT_HEAT_T", "at": "21:00"}


def test_hour_inside_sleep_becomes_bedtime_plus_morning_close():
    for h in (23, 0, 1, 5):
        ids, sched = build(h)
        assert "NIGHT_HEAT_T" not in ids and ids[-2:] == ["OPEN_AT_BEDTIME", "CLOSE_MORNING"], (h, ids)
        assert [s["at"] for s in sched] == ["22:30", "07:30"]


def test_learned_sleep_window_from_band_profile():
    """A band window of 00:30-06:00 makes 23:00 an awake hour -> the timed string is allowed."""
    ids, _ = build(23, sleep=(30, 360))
    assert "NIGHT_HEAT_T" in ids
    with open(os.path.join(HERE, "routine_vector_b5.hex")) as f:
        rt = RoutineTemplate.from_band(bytes.fromhex(f.read().strip()))
    assert plan.sleep_window_of(rt) == (1380, 435)
    assert plan.sleep_window_of(RoutineTemplate.default()) == (1380, 420)       # default 23:00-07:00


def test_no_instruction_inside_sleep_window_demo_and_random():
    rng = np.random.default_rng(7)
    cases = [(demo.demo_forecast(), demo.DEMO_DATE)]
    for k in range(3):
        tmin = float(rng.uniform(22, 29))
        cases.append((demo.synthetic_forecast([(23, 32)] * 7 + [(tmin, tmin + rng.uniform(8, 14))] * 4, "2026-07-01"),
                      "2026-07-11"))
    for fc, d in cases:
        p = plan.make_plan(fc, d, "B")
        bed, wake = (mins(x) for x in p["details"]["sleep_window"])
        for s in p["details"]["advice_schedule"]:
            assert not A.in_window(mins(s["at"]), bed, wake), (s, p["details"]["sleep_window"])
        if "OPEN_AT_BEDTIME" in p["details"]["advice_ids"]:
            assert "CLOSE_MORNING" in p["details"]["advice_ids"]


def test_morning_close_rule():
    t_in = np.full(13, 30.0)
    t_out = np.r_[np.full(9, 27.0), np.full(4, 32.0)]          # outdoor overtakes the room at 09:00
    assert plan.morning_close_minute(t_out, t_in, 420) == 480   # 1 h before -> 08:00
    t_out2 = np.r_[np.full(5, 27.0), np.full(8, 32.0)]          # overtakes at 05:00 (asleep) -> at wake
    assert plan.morning_close_minute(t_out2, t_in, 420) == 420


def test_new_strings_fit_and_unapproved():
    for i in ("OPEN_AT_BEDTIME", "CLOSE_MORNING"):
        assert A.fits(A.T(i)) and A.STRINGS[i]["approved"] is False
