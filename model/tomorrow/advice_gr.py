"""Greek strings for the wearer. ALL texts live in strings_el.json (id, text, kind, source/reason, approved)
so Foivos can approve them in one go. Rule R3 §6.1: name the room/action, never the person's vulnerability.

Fit rule (manager B4-fix, R3 §6.2): every wearer-facing string fits 2 lines at ~35-40 px on the 240 px
screen. Font = u8g2_font_10x20_t_greek (the firmware's), monospace 10 px advance, drawn x2 = 20 px per
character; 224 px usable (8 px margins) -> 11 characters per line, greedy word wrap, <= 2 lines.
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "strings_el.json"), encoding="utf-8") as _f:
    STRINGS = {s["id"]: s for s in json.load(_f)["strings"]}

CHAR_PX, SCALE, USABLE_PX, MAX_LINES = 10, 2, 224, 2
MAX_CHARS = USABLE_PX // (CHAR_PX * SCALE)          # 11


def T(i: str) -> str:
    return STRINGS[i]["text"]


HEAT_DAY = T("HEAT_DAY"); SAFE_HOURS_T = T("SAFE_HOURS_T"); SAFE_HOURS_LABEL = T("SAFE_HOURS_LABEL")
NO_SAFE_HOURS = T("NO_SAFE_HOURS"); DRINK_PLENTY = T("DRINK_PLENTY"); DRINK_NOW = T("DRINK_NOW")
GO_COOL = T("GO_COOL"); GO_COOLER_ROOM = GO_COOL; SHOWER = T("SHOWER"); SHOWER_COMPRESS = SHOWER
ARE_YOU_OK = T("ARE_YOU_OK"); NIGHT_HEAT_T = T("NIGHT_HEAT_T"); NIGHT_HEAT_CLOSED = T("NIGHT_CLOSED")
MOVE_ERRAND_T = T("MOVE_ERRAND_T"); STALE_FORECAST = T("STALE_FORECAST")
OPEN_WINDOWS_EVENING = T("OPEN_WINDOWS_EVENING"); HOUSE_WILL_REACH_T = T("HOUSE_WILL_REACH_T")   # retired

# worst-case fillers for templates (used by the fit test)
WORST = {"ranges": "06:00-08:00", "hh": "22", "usual": "18:00", "t": "39", "good": "06:00"}


def wrap(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if len(t) <= max_chars:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fits(text: str) -> bool:
    ls = wrap(text)
    return len(ls) <= MAX_LINES and all(len(l) <= MAX_CHARS for l in ls)


def hour_ranges(flags) -> list[tuple[int, int]]:
    """Contiguous True runs as (start_h, end_h_exclusive)."""
    out, s = [], None
    for h, f in enumerate(list(flags) + [False]):
        if f and s is None:
            s = h
        if not f and s is not None:
            out.append((s, h)); s = None
    return out


BEDTIME_LEAD_MIN = 30      # the bedtime instruction is shown 30 min before the sleep window starts (design)


def in_window(minute: int, start: int, end: int) -> bool:
    """minute of day inside [start, end), wrapping midnight."""
    return start <= minute < end if start < end else (minute >= start or minute < end)


def build(plan_hours: list[dict], heat_day: bool, night_heat: bool, window_hour: int | None,
          indoor_cross: bool, errand_hours: list[int], stale: bool = False,
          sleep_window: tuple[int, int] = (1380, 420), close_minute: int | None = None,
          schedule: list | None = None) -> tuple[list[str], list[str]]:
    """Return (advice lines, their string ids). safe already excludes dark hours (plan.py).
    Manager rule (B4-fix2): never instruct an action inside the sleep window [bed, wake). The window advice is
    «Ανοίξτε στις hh:00» only when hh:00 is outside the sleep window; otherwise «Ανοίξτε τα παράθυρα» at
    bedtime plus «Κλείστε παράθυρα» in the morning (close_minute). ``schedule`` (if given) receives
    {"id", "at"} entries for every timed instruction so tests can check them."""
    lines, ids = [], []
    sched = schedule if schedule is not None else []

    def add(i, at=None, **kw):
        s = T(i).format(**kw) if kw else T(i)
        assert fits(s), "string %s does not fit the screen: %r" % (i, s)
        if s not in lines:
            lines.append(s); ids.append(i)
            if at is not None:
                sched.append({"id": i, "at": "%02d:%02d" % divmod(int(at) % 1440, 60)})

    if stale:
        add("STALE_FORECAST")
    if heat_day:
        add("HEAT_DAY")
    rngs = hour_ranges([h["safe"] for h in plan_hours])
    if rngs:
        a, b = rngs[0]
        add("SAFE_HOURS_T", ranges="%02d:00-%02d:00" % (a, b))
    else:
        add("NO_SAFE_HOURS")
    if heat_day:
        add("DRINK_PLENTY")
    adv = {h["h"]: h["advice"] for h in plan_hours}
    for u in errand_hours:                       # one line only: the first usual errand hour in AVOID
        if adv.get(u) == "AVOID":
            add("MOVE_ERRAND_T", usual="%02d:00" % u)
            break
    if night_heat:
        bed, wake = sleep_window
        if window_hour is not None and not in_window(window_hour * 60, bed, wake):
            add("NIGHT_HEAT_T", at=window_hour * 60, hh="%02d" % window_hour)
            if close_minute is not None:
                add("CLOSE_MORNING", at=close_minute)
        elif window_hour is not None:
            add("OPEN_AT_BEDTIME", at=(bed - BEDTIME_LEAD_MIN) % 1440)
            if close_minute is not None:
                add("CLOSE_MORNING", at=close_minute)
        else:
            add("NIGHT_CLOSED")
    if indoor_cross:
        add("GO_COOL")
        add("SHOWER")
    return lines, ids
