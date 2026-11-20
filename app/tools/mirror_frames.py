#!/usr/bin/env python3
"""Python mirror of ios/HeatGuardian/BLE/Frames.swift (+ Plan.slot / safeRanges), translated line by line, run on
the same vectors the XCTest uses. Proves the Swift byte offsets / bit masks / rounding rules without a Swift compiler.

    python3 -I ios/tools/mirror_frames.py

Each function below names the Swift function it mirrors; keep them in step when Frames.swift changes.
"""
import unicodedata
import json, math, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
IOS = os.path.dirname(HERE)
ROOT = os.path.dirname(IOS)
STATE_NAMES = ["OK", "DRINK", "COOL", "DANGER", "IMOK", "BATTERY", "CHECK", "HELP"]


def crc8(b, count=None):                       # Frames.crc8
    n = len(b) if count is None else count
    c = 0
    for i in range(n):
        c ^= b[i]
        for _ in range(8):
            c = (((c << 1) ^ 0x07) if (c & 0x80) else (c << 1)) & 0xFF   # UInt8 << drops the high bit
    return c


class FrameError(Exception):
    pass


def decode_status(b):                          # Frames.decodeStatus(_ b: [UInt8])
    if len(b) != 20: raise FrameError("len")
    if crc8(b, 19) != b[19]: raise FrameError("crc")
    if (b[0] & 0x0F) != 1: raise FrameError("version")   # the fw's all-zero seed frame passes CRC-8 but is version 0
    u16 = lambda o: b[o] | (b[o + 1] << 8)
    def i16(o):
        v = u16(o); return v - 0x10000 if v >= 0x8000 else v
    def t(o):
        v = i16(o); return None if v == -32768 else v / 100.0
    fam = (b[0] & 0x10) != 0
    d = dict(version=b[0] & 0x0F, familyPending=fam, notWorn=(b[0] & 0x20) != 0,
             stateCode=b[1] & 7, contactOK=(b[1] & 8) != 0, timeSynced=(b[1] & 16) != 0,
             charging=(b[1] & 32) != 0, home=(b[1] & 64) != 0, ppgValid=(b[1] & 128) != 0,
             coreC=u16(2) / 100.0, halfRangeC=b[4] / 100.0, hrBpm=b[5], hrQ=b[6],
             t1C=t(7), t2C=t(9), tairC=t(11), rhPct=None if b[13] == 255 else b[13], batteryPct=b[14],
             minuteCounter=u16(17), alarmId16=None, routineScore=None, activity=None)
    if fam: d["alarmId16"] = u16(15)
    else: d["routineScore"] = b[15]; d["activity"] = b[16]
    return d


# JS / B5 key  ->  Swift property
KEYMAP = dict(version="version", family_pending="familyPending", not_worn="notWorn", state_code="stateCode",
              contact_ok="contactOK", time_synced="timeSynced", charging="charging", home="home", ppg_valid="ppgValid",
              core_c="coreC", half_range_c="halfRangeC", hr_bpm="hrBpm", hr_q="hrQ", t1_c="t1C", t2_c="t2C",
              tair_c="tairC", rh_pct="rhPct", battery_pct="batteryPct", minute_counter="minuteCounter",
              alarm_id16="alarmId16", routine_score="routineScore", activity="activity")


def is_empty_status(b): return len(b) == 20 and all(x == 0 for x in b)   # Frames.isEmptyStatus


def bcd_version(v):   # Frames.bcdVersion: one BCD byte up to 0.9.9 (0x0099), two BCD bytes from 0.9.10 (0x0917 = 0.9.17)
    bcd = lambda b: ((b >> 4) & 0xF) * 10 + (b & 0xF)
    hi, lo = (v >> 8) & 0xFF, v & 0xFF
    return "0.%d.%d" % ((lo >> 4) & 0xF, lo & 0xF) if hi == 0 else "0.%d.%d" % (bcd(hi), bcd(lo))


def seal(a): return list(a) + [crc8(a)]        # Frames.seal
def le32(v): return [v & 255, (v >> 8) & 255, (v >> 16) & 255, (v >> 24) & 255]   # Frames.le32
def cmd_time(unix_s, tz_q): return seal([0x10] + le32(unix_s) + [tz_q & 0xFF])  # UInt8(truncatingIfNeeded:)
def cmd_family_ack(t, aid): return seal([0x12, t] + le32(aid))
def cmd_profile(field, value):                 # Float(value).bitPattern, little-endian
    bits = struct.unpack("<I", struct.pack("<f", value))[0]
    return seal([0x13, field] + le32(bits))
def cmd_consent(bits): return seal([0x15, bits & 7])


def py_round(x):                               # Frames.pyRound: .toNearestOrEven
    return int(round(x))                       # Python's round() is half-to-even == .toNearestOrEven


def hour_flags(plan, h):                       # Frames.hourFlags
    hr = plan["hours"][h]; f = 0
    if plan["heat_day"]: f |= 1
    if plan["night_heat"]: f |= 2
    if hr["safe"]: f |= 4
    f |= (h // 6) << 3
    return f


def forecast_chunks(plan):                     # Frames.forecastChunks
    assert len(plan["hours"]) == 24
    out = []
    for k in range(4):
        body = [0x11]
        for h in range(6 * k, 6 * k + 6):
            t = max(-128, min(127, py_round(plan["hours"][h]["t_in"])))
            rh = max(0, min(100, py_round(plan["hours"][h]["rh_in"])))
            body += [t & 0xFF, rh, hour_flags(plan, h)]
        out.append(seal(body))
    return out


def safe_bitmap(plan):
    b = 0
    for i, h in enumerate(plan["hours"]):
        if h["safe"] and i < 32: b |= 1 << i
    return b


def plan_id(date_str):                         # Frames.planId (manual day-of-year)
    y, m, d = (int(x) for x in date_str.split("-"))
    leap = (y % 4 == 0 and y % 100 != 0) or y % 400 == 0
    md = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return (d + sum(md[: m - 1])) & 255


def utf16_units(s):
    e = s.encode("utf-16-le"); return [e[i] | (e[i + 1] << 8) for i in range(0, len(e), 2)]


def safe_hours_frame(plan, tag=None):          # Frames.safeHoursFrame
    tg = tag if tag is not None else plan["date"] + " " + (plan.get("home_class") or "") + (" C" if plan.get("stale_forecast") else "")
    bm = safe_bitmap(plan)
    body = [0x14, bm & 255, (bm >> 8) & 255, (bm >> 16) & 255, plan_id(plan["date"])]
    u = utf16_units(tg)
    for i in range(14):
        c = u[i] if i < len(u) else 0
        body.append(63 if c > 127 else c)
    return seal(body)


def safe_ranges(hours):                        # Plan.safeRanges
    out, s, n = [], None, len(hours)
    for i, h in enumerate(hours):
        if h["safe"] and s is None: s = i
        if (not h["safe"] or i == n - 1) and s is not None:
            e = n if (h["safe"] and i == n - 1) else i
            out.append("%02d:00–%02d:00" % (s, e)); s = None
    return out


def hx(b): return bytes(b).hex()


# ---------------------------------------------------------------- ecosystem (EcoFrames.swift, Indoor.swift, NudgePlanner.swift)
EVENTS_TAG = 0x03


def decode_event(b):                           # Frames.decodeEvent
    if len(b) != 20: raise FrameError("len")
    if crc8(b, 19) != b[19]: raise FrameError("crc")
    if b[0] != EVENTS_TAG: raise FrameError("tag")
    return dict(seq=b[1] | (b[2] << 8), boot=b[3] | (b[4] << 8),
                unix=b[5] | (b[6] << 8) | (b[7] << 16) | (b[8] << 24), kind=b[9], arg=b[10], ext=list(b[11:19]))


def encode_event(e):                           # Frames.encodeEvent
    b = [0] * 19
    b[0] = EVENTS_TAG
    b[1] = e["seq"] & 255; b[2] = (e["seq"] >> 8) & 255
    b[3] = e["boot"] & 255; b[4] = (e["boot"] >> 8) & 255
    b[5:9] = le32(e["unix"])
    b[9] = e["kind"] & 255; b[10] = e["arg"] & 255
    for i, x in enumerate(e.get("ext", [])[:8]): b[11 + i] = x
    return seal(b)


def frame20(op, payload):                      # Frames.frame20
    b = [op] + list(payload[:18])
    while len(b) < 19: b.append(0)
    return seal(b)


def cmd_sync_events(since_seq, boot):          # Frames.cmdSyncEvents
    return frame20(0x16, [since_seq & 255, (since_seq >> 8) & 255, boot & 255, (boot >> 8) & 255])


def cmd_family_msg(msg): return frame20(0x17, [msg])   # Frames.cmdFamilyMsg


def family_name_bytes(name):                   # Frames.familyNameBytes (whole characters only, max 14 bytes)
    out = []
    for ch in name.strip():
        if unicodedata.category(ch) == "Cc": continue   # fw rejects control characters
        u = list(ch.encode("utf-8"))
        if len(out) + len(u) > 14: break
        out += u
    return out


def cmd_elder_action(action, nudge=0):           # Frames.cmdElderAction
    return frame20(0x1A, [action, (nudge & 255) if action == 2 else 0])


def cmd_family_name(name): return frame20(0x18, family_name_bytes(name))   # Frames.cmdFamilyName


def cmd_routine_seed(wake, bed, nap_from, nap_to, o1f, o1t, o2f, o2t, ac):  # Frames.cmdRoutineSeed
    def hm(m):
        if m is None or m < 0 or m >= 1440: return [0xFF, 0xFF]
        return [m // 60, m % 60]
    p = []
    for t in (wake, bed, nap_from, nap_to, o1f, o1t, o2f, o2t): p += hm(t)
    p.append(0xFF if ac is None else (1 if ac else 0))   # flags: bit0 A/C, 0xFF = not stated
    return frame20(0x19, p)


INDOOR = {"A": (36.0, 4.5, 3.0, 0.15, False), "B": (72.0, 3.0, 3.0, 0.25, True),
          "C": (36.0, 4.0, 2.0, 0.30, True), "D": (96.0, 1.5, 5.0, 0.10, True)}


def indoor_sim(t_out, cls):                    # Indoor.simulate
    tau_s, dT, tau_f, g_f, amin = INDOOR[cls]
    n = len(t_out)
    ks = 1.0 - math.exp(-1.0 / tau_s); kf = 1.0 - math.exp(-1.0 / tau_f)
    ref = [min(t_out[max(0, i - 23):i + 1]) for i in range(n)] if amin else list(t_out)
    first = t_out[:24]
    ts = (min(first) if amin else sum(first) / len(first)) + dT
    tf = 0.0; out = []
    for i in range(n):
        out.append(ts + tf)
        target = g_f * (t_out[i] - ref[i]) if amin else g_f * (t_out[i] - ts + dT)
        ts += ks * (ref[i] + dT - ts)
        tf += kf * (target - tf)
    return out


def indoor_adjust(plan, cls):                  # Indoor.adjust -> list of t_in
    frm = plan.get("home_class") or "B"
    outs = [h["t_out"] for h in plan["hours"]]
    a, b = indoor_sim(outs, cls), indoor_sim(outs, frm)
    return [round((h["t_in"] + a[i] - b[i]) * 10) / 10 for i, h in enumerate(plan["hours"])]


def eco_checks(check, rd):
    V = rd(os.path.join(IOS, "HeatGuardianTests/eco_vectors_app.json"))
    for v in V["events"]:
        d = decode_event(list(bytes.fromhex(v["hex"])))
        check(all(d[k] == v[k] for k in ("seq", "boot", "unix", "kind", "arg")), "EVENT decode " + v["hex"])
        check(hx(encode_event(v)) == v["hex"], "EVENT encode " + v["hex"])
    for h in V["events_bad"]:
        try: decode_event(list(bytes.fromhex(h))); check(False, "bad event accepted " + h)
        except FrameError: check(True, "")
    for v in V["sync_events"]: check(hx(cmd_sync_events(v["since_seq"], v["boot"])) == v["hex"], "SYNC " + v["hex"])
    for v in V["family_msg"]: check(hx(cmd_family_msg(v["msg"])) == v["hex"], "FAMILY_MSG " + v["hex"])
    for v in V["family_name"]:
        check(hx(cmd_family_name(v["name"])) == v["hex"], "FAMILY_NAME " + v["name"])
        check(len(family_name_bytes(v["name"])) == v["bytes"], "FAMILY_NAME bytes " + v["name"])
    for v in V["routine_seed"]:
        a = v["args"]
        check(hx(cmd_routine_seed(a["wake"], a["bed"], a["nap_from"], a["nap_to"], a["out1_from"], a["out1_to"],
                                  a["out2_from"], a["out2_to"], a["ac"])) == v["hex"], "ROUTINE_SEED " + v["hex"])
    for v in V["elder_action"]: check(hx(cmd_elder_action(v["action"], v["nudge"])) == v["hex"], "ELDER_ACTION " + v["hex"])
    for f in V["events"] + [{"hex": x["hex"]} for x in V["sync_events"] + V["family_msg"] + V["family_name"] + V["routine_seed"] + V["elder_action"]]:
        check(len(bytes.fromhex(f["hex"])) == 20, "20-byte frame " + f["hex"])
    # Indoor.swift == tomorrow/indoor.py (same class, no sun, default start) on the bundled plan's t_out
    P = rd(os.path.join(IOS, "HeatGuardian/Resources/plan.json"))
    outs = [h["t_out"] for h in P["hours"]]
    try:
        sys.path.insert(0, ROOT)
        from tomorrow import indoor as ref_indoor
        for c in "ABCD":
            r = list(ref_indoor.simulate(outs, home_class=c)["t_in"])
            m = indoor_sim(outs, c)
            check(max(abs(x - y) for x, y in zip(r, m)) < 1e-9, "Indoor.simulate class %s == tomorrow/indoor.py" % c)
    except ImportError as e:
        print("skip indoor reference (%s)" % e)
    for v in V["indoor_adjust"]:
        check(indoor_adjust(P, v["cls"]) == v["t_in"], "Indoor.adjust bundled plan -> " + v["cls"])
    check(indoor_adjust(P, "B") == [h["t_in"] for h in P["hours"]] or P.get("home_class") != "B", "same class = unchanged")
    return V


def hm_str(s):                                  # "07:10" -> 430, None -> None
    if s is None: return None
    h, m = s.split(":"); return int(h) * 60 + int(m)


def fw_checks(check, rd):
    """The firmware's own vectors (fw/09_guardian/eco_vectors.json, copied to HeatGuardianTests/eco_vectors_fw.json):
    the band is the source of truth for every byte layout. Prints MATCH / MISMATCH per frame."""
    F = rd(os.path.join(IOS, "HeatGuardianTests/eco_vectors_fw.json"))
    res = {}
    def rec(name, ok, what):
        check(ok, "FW " + name + " " + what)
        res[name] = res.get(name, True) and ok
    check(crc8(list(b"123456789")) == int(F["crc8_check"]["crc8"], 16), "FW crc8 check value")
    for e in F["events"] + [F["event_clock_not_set"]]:
        d = decode_event(list(bytes.fromhex(e["hex"])))
        ok = (d["seq"], d["boot"], d["unix"], d["kind"], d["arg"]) == (e["seq"], e["boot_count"], e["unix"], e["type"], e["arg"])
        ok = ok and hx(encode_event({"seq": e["seq"], "boot": e["boot_count"], "unix": e["unix"], "kind": e["type"], "arg": e["arg"]})) == e["hex"]
        rec("EVENTS", ok, e["hex"])
    for c in F["commands"]:
        op, h = c["op"], c["hex"]
        if op == "0x16": got = cmd_sync_events(c["since_seq"], c["boot_count"]); name = "0x16 SYNC_EVENTS"
        elif op == "0x17": got = cmd_family_msg(c["msg"]); name = "0x17 FAMILY_MSG"
        elif op == "0x18": got = cmd_family_name(c["utf8"]); name = "0x18 FAMILY_NAME"
        elif op == "0x19":
            def win(w): return (None, None) if w is None else tuple(hm_str(x) for x in w.split("-"))
            n, o1, o2 = win(c["nap"]), win(c["out1"]), win(c["out2"])
            got = cmd_routine_seed(hm_str(c["wake"]), hm_str(c["bed"]), n[0], n[1], o1[0], o1[1], o2[0], o2[1], c["ac_at_home"])
            name = "0x19 ROUTINE_SEED"
        elif op == "0x1A": got = cmd_elder_action(c["action"], c["nudge_id"]); name = "0x1A ELDER_ACTION"
        else: continue
        rec(name, hx(got) == h, h)
    for k in sorted(res): print("  fw vectors %-18s %s" % (k, "MATCH" if res[k] else "MISMATCH"))



# ---------------------------------------------------------------- Her Day (EcoFrames.swift "Her Day" section,
# HerDay.swift, HerDayRoutine.swift RoutineModel core) — HERDAY_SPEC.md §4 / §6
UNSET = 0xFF
DAY_PLAN_MAX = 6


def hm_bytes(m):                                # Frames.hmBytes
    return [UNSET, UNSET] if m is None else [m // 60, m % 60]


def valid_hm(m): return m is None or 0 <= m < 1440


def cmd_day_plan(it, index, n):                 # Frames.cmdDayPlan (raises FrameError like the Swift throws)
    if it["day"] not in (0, 1): raise FrameError("day")
    if not (1 <= n <= DAY_PLAN_MAX and 1 <= index <= n): raise FrameError("index")
    if not (valid_hm(it.get("usual")) and valid_hm(it.get("suggested"))): raise FrameError("time")
    if it["kind"] not in (1, 2, 3): raise FrameError("kind")
    p = [0] * 18
    p[0] = it["day"]; p[1] = index; p[2] = n; p[3] = it["kind"]
    if it["kind"] == 1:
        if it.get("suggested") is None or it.get("direction") is None: raise FrameError("kind 1 needs a suggestion")
        if not (0 <= it["hot_from"] <= 23 and it["hot_to"] <= 24 and it["hot_from"] <= it["hot_to"]): raise FrameError("hot window")
        if not (0 <= it["place"] <= 7) or it["direction"] not in (1, 2): raise FrameError("place/direction")
        p[4] = it["place"]
        p[5:7] = hm_bytes(it.get("usual"))
        p[7:9] = hm_bytes(it["suggested"])
        p[9] = it["direction"]
        p[10] = it["hot_from"]; p[11] = it["hot_to"]
        p[12] = UNSET if it.get("peak_c") is None else max(0, min(254, it["peak_c"]))
    elif it["kind"] == 2:
        if it.get("suggested") is None: raise FrameError("kind 2 needs a time")
        p[7:9] = hm_bytes(it["suggested"])
    else:
        if not (0 <= it.get("heatwave_day", 0) <= 31): raise FrameError("heat-wave day")
        p[13] = it["heatwave_day"]
    return frame20(0x1B, p)


def cmd_day_plan_clear(day): return frame20(0x1B, [day & 1, 0, 0])    # Frames.cmdDayPlanClear


def day_plan_frames(items, day):                # Frames.dayPlanFrames
    its = items[:DAY_PLAN_MAX]
    if not its: return [cmd_day_plan_clear(day)]
    return [cmd_day_plan(dict(it, day=day), i + 1, len(its)) for i, it in enumerate(its)]


def cmd_visit(edge, place, unix): return frame20(0x1C, [edge, place] + le32(unix))   # Frames.cmdVisit


def visit_event(seq, boot, unix, edge, place, vunix):   # Frames.visitEvent
    return dict(seq=seq, boot=boot, unix=unix, kind=9, arg=place, ext=[edge] + le32(vunix) + [0, 0, 0])


def plan_item_event(seq, boot, unix, it):       # Frames.planItemEvent
    x = [0] * 8
    if it["kind"] == 1:
        x[0] = it["place"]; x[1:3] = hm_bytes(it.get("usual")); x[5] = it["hot_from"]; x[6] = min(24, it["hot_to"])
    if it["kind"] != 3: x[3:5] = hm_bytes(it.get("suggested"))
    d = (it.get("direction") or 0) if it["kind"] == 1 else 0
    hw = min(31, it.get("heatwave_day", 0)) if it["kind"] == 3 else 0
    x[7] = (it["day"] & 1) | ((d & 3) << 1) | ((hw & 31) << 3)
    return dict(seq=seq, boot=boot, unix=unix, kind=10, arg=it["kind"], ext=x)


def event_visit(e):                             # BandEvent.visit
    x = e["ext"]
    if e["kind"] != 9 or not (0 <= e["arg"] <= 7) or x[0] not in (1, 2): return None
    return dict(edge=x[0], place=e["arg"], unix=x[1] | (x[2] << 8) | (x[3] << 16) | (x[4] << 24))


def event_plan_item(e):                         # BandEvent.planItem
    if e["kind"] != 10 or e["arg"] not in (1, 2, 3): return None
    b = e["ext"]; k = e["arg"]; packed = b[7]

    def hm(h, m):
        if h == UNSET and m == UNSET: return (True, None)
        if h > 23 or m > 59: return (False, None)
        return (True, h * 60 + m)
    it = dict(day=packed & 1, kind=k, place=0, usual=None, suggested=None, direction=None, hot_from=0, hot_to=0,
              peak_c=None, heatwave_day=0)
    if k == 1:
        ok_u, u = hm(b[1], b[2]); ok_s, s_ = hm(b[3], b[4]); d = (packed >> 1) & 3
        if not (0 <= b[0] <= 7 and ok_u and ok_s and s_ is not None and d in (1, 2) and b[5] <= 23 and b[6] <= 24): return None
        it.update(place=b[0], usual=u, suggested=s_, direction=d, hot_from=b[5], hot_to=b[6])
    elif k == 2:
        ok_s, s_ = hm(b[3], b[4])
        if not ok_s or s_ is None: return None
        it.update(suggested=s_)
    else:
        it.update(heatwave_day=packed >> 3)
    return it


HOT_C, WARM_IN_C, EARLIEST, GAP_AFTER, STEP, AIR_FROM = 30.0, 28.0, 7 * 60, 30, 15, 18


def hd_hot_hours(plan):                         # HerDay.hotHours
    return [(h.get("t_out") is not None and h["t_out"] >= HOT_C) or h.get("advice") == "AVOID" for h in plan["hours"]]


def hd_hot_windows(hot):                        # HerDay.hotWindows
    out, s = [], None
    for i in range(len(hot) + 1):
        on = i < len(hot) and hot[i]
        if on and s is None: s = i
        if not on and s is not None: out.append((s, i)); s = None
    return out


def hd_slot_cool(start, dur, hot):              # HerDay.slotIsCool
    if start < 0 or start + dur > 1440: return False
    last = (start + max(1, dur) - 1) // 60
    return not any(h < len(hot) and hot[h] for h in range(start // 60, last + 1))


def hd_floor_step(m): return (m // STEP) * STEP if m >= 0 else -(((-m) + STEP - 1) // STEP) * STEP
def hd_ceil_step(m): return ((m + STEP - 1) // STEP) * STEP
def hd_bed_axis(bed): return bed + 1440 if bed < 720 else bed


def hd_suggest(o, w, hot, bed):                 # HerDay.suggest
    dur = max(1, o["duration"])
    t = hd_floor_step(w[0] * 60 - dur)
    while t >= EARLIEST:
        if hd_slot_cool(t, dur, hot): return (t, 1)
        t -= STEP
    limit = min(hd_bed_axis(bed) - 60, 1440)
    t = hd_ceil_step(w[1] * 60 + GAP_AFTER)
    while t + dur <= limit:
        if hd_slot_cool(t, dur, hot): return (t, 2)
        t += STEP
    return None


def hd_round_c(x): return int(math.floor(x + 0.5))   # HerDay.roundC


def hd_peak(plan, start, dur):                  # HerDay.peak
    a, b = start // 60, min(23, (start + max(1, dur) - 1) // 60)
    hs = plan["hours"]
    if a > b or a >= len(hs): return None
    ts = [hs[h]["t_out"] for h in range(a, b + 1) if h < len(hs) and hs[h].get("t_out") is not None]
    return hd_round_c(max(ts)) if ts else None


def hd_air_open(plan):                          # HerDay.airOpen
    hs = plan["hours"]
    matters = plan["heat_day"] or plan["night_heat"] or max(h["t_in"] for h in hs) >= WARM_IN_C
    if not matters or len(hs) != 24: return None
    for h in range(AIR_FROM, 24):
        if hs[h].get("t_out") is not None and hs[h]["t_out"] < hs[h]["t_in"] - 1.0: return h * 60
    return None


def hd_compute(plan, outings, bed, day):        # HerDay.compute
    hot = hd_hot_hours(plan); wins = hd_hot_windows(hot)
    outs = sorted([o for o in outings if o["place"] != 0], key=lambda o: (o["start"], o["place"]))
    cols = []
    for o in outs:
        w = next((w for w in wins if o["start"] < w[1] * 60 and o["start"] + max(1, o["duration"]) > w[0] * 60), None)   # HotWindow.overlaps
        if w is None: continue
        s = hd_suggest(o, w, hot, bed)
        cols.append(dict(place=o["place"], start=o["start"], window=list(w), peak_c=hd_peak(plan, o["start"], o["duration"]),
                         suggested=s[0] if s else None, direction=s[1] if s else None))
    air = hd_air_open(plan)
    wave = min(31, max(1, plan.get("wave_day") or 1)) if plan["heat_day"] else None
    tail = []
    if air is not None: tail.append(dict(day=day, kind=2, place=0, usual=None, suggested=air, direction=None, hot_from=0, hot_to=0, peak_c=None, heatwave_day=0))
    if wave is not None: tail.append(dict(day=day, kind=3, place=0, usual=None, suggested=None, direction=None, hot_from=0, hot_to=0, peak_c=None, heatwave_day=wave))
    shifts = [dict(day=day, kind=1, place=c["place"], usual=c["start"], suggested=c["suggested"], direction=c["direction"],
                   hot_from=c["window"][0], hot_to=c["window"][1], peak_c=c["peak_c"], heatwave_day=0)
              for c in cols if c["suggested"] is not None]
    items = shifts[:DAY_PLAN_MAX - len(tail)] + tail
    return dict(hot=[list(w) for w in wins], collisions=cols, air_open=air, heatwave_day=wave, items=items)


BAND_WORD = ["έξοδο", "αγορά", "εκκλησία", "βόλτα", "φαρμακείο", "καφενείο", "γιατρό", "έξοδο"]


def hd_brief(items, tomorrow):                  # HerDay.briefSentence
    head = "Αύριο: " if tomorrow else "Σήμερα: "
    ks = [i for i in items if i["kind"] == 1]
    if ks:
        k = min(ks, key=lambda i: 9999 if i["usual"] is None else i["usual"])
        if k["suggested"] is not None and k["direction"] is not None:
            return head + BAND_WORD[k["place"]] + (" πριν τις " if k["direction"] == 1 else " μετά τις ") + "%02d:%02d" % (k["suggested"] // 60 % 24, k["suggested"] % 60)
    w = next((i for i in items if i["kind"] == 3), None)
    if tomorrow and w: return "Αύριο: καύσωνας, μέρα %d" % w["heatwave_day"]
    return None


def rm_median(xs):                              # RoutineModel.median
    s = sorted(xs); n = len(s)
    if n == 0: return 0
    if n % 2: return s[n // 2]
    a = s[n // 2 - 1] + s[n // 2]
    return a // 2 if a >= 0 else -((-a + 1) // 2)


def rm_outings(ss, weekday):                    # RoutineModel.outings (core)
    out = []
    for place in range(1, 8):
        xs = sorted([s for s in ss if s["place"] == place], key=lambda s: (s["start"], s["weekday"]))
        if not xs: continue
        clusters = [[xs[0]]]
        for s in xs[1:]:
            if s["start"] - clusters[-1][-1]["start"] > 180: clusters.append([s])
            else: clusters[-1].append(s)
        for c in clusters:
            daily = len(set(s["weekday"] for s in c)) >= 4
            use = c if daily else [s for s in c if s["weekday"] == weekday]
            if len(use) < 2: continue
            durs = [s["duration"] for s in use if s.get("duration") is not None]
            dur = 60 if not durs else max(15, min(240, rm_median(durs)))
            out.append(dict(place=place, start=rm_median([s["start"] for s in use]), duration=dur, daily=daily, count=len(use)))
    return sorted(out, key=lambda o: (o["start"], o["place"]))


def item_eq(a, b):
    keys = ("day", "kind", "place", "usual", "suggested", "direction", "hot_from", "hot_to", "peak_c", "heatwave_day")
    return all(a.get(k) == b.get(k) for k in keys)


def herday_checks(check, rd):
    V = rd(os.path.join(IOS, "HeatGuardianTests/herday_vectors_app.json"))
    for v in V["day_plan"]:
        check(hx(cmd_day_plan(v["item"], v["index"], v["n"])) == v["hex"], "DAY_PLAN " + v["hex"])
    for v in V["day_plan_clear"]: check(hx(cmd_day_plan_clear(v["day"])) == v["hex"], "DAY_PLAN clear " + v["hex"])
    for v in V["day_plan_bad"]:
        try: cmd_day_plan(v["item"], v["index"], v["n"]); check(False, "bad DAY_PLAN accepted " + v["why"])
        except FrameError: check(True, "")
    for v in V["visit"]: check(hx(cmd_visit(v["edge"], v["place"], v["unix"])) == v["hex"], "VISIT " + v["hex"])
    for v in V["events_visit"]:
        e = decode_event(list(bytes.fromhex(v["hex"])))
        vv = event_visit(e)
        check(vv == dict(edge=v["edge"], place=v["place"], unix=v["visit_unix"]) and e["seq"] == v["seq"] and e["unix"] == v["unix"], "EVENT VISIT " + v["hex"])
        check(hx(encode_event(visit_event(v["seq"], v["boot"], v["unix"], v["edge"], v["place"], v["visit_unix"]))) == v["hex"], "EVENT VISIT enc " + v["hex"])
    for v in V["events_plan_item"]:
        e = decode_event(list(bytes.fromhex(v["hex"])))
        want = dict(v["item"], peak_c=None)
        check(item_eq(event_plan_item(e), want), "EVENT PLAN_ITEM dec " + v["hex"])
        check(hx(encode_event(plan_item_event(v["seq"], v["boot"], v["unix"], v["item"]))) == v["hex"], "EVENT PLAN_ITEM enc " + v["hex"])
    for c in V["engine"]:
        r = hd_compute(c["plan"], c["outings"], c["bed"], c["day"])
        x = c["expect"]
        check(r["hot"] == x["hot"], c["name"] + " hot windows")
        check(r["air_open"] == x["air_open"] and r["heatwave_day"] == x["heatwave_day"], c["name"] + " air/heatwave")
        check([(k["place"], k["start"], k["suggested"], k["direction"], k["peak_c"]) for k in r["collisions"]]
              == [(k["place"], k["start"], k["suggested"], k["direction"], k["peak_c"]) for k in x["collisions"]], c["name"] + " collisions")
        check(len(r["items"]) == len(x["items"]) and all(item_eq(a, b) for a, b in zip(r["items"], x["items"])), c["name"] + " items")
        check([hx(f) for f in day_plan_frames(r["items"], c["day"])] == x["frames_hex"], c["name"] + " frames")
        check(hd_brief(r["items"], c["day"] == 1) == x["brief"], c["name"] + " brief")
    for c in V["routine"]:
        got = rm_outings(c["samples"], c["weekday"])
        check(got == c["expect"], c["name"] + " routine %r" % got)
    return V


def herday_fw_checks(check):
    """fw/09_guardian/herday_vectors.json (band 0.9.8, from the firmware encoders; copied to
    HeatGuardianTests/herday_vectors_fw.json): byte for byte against this mirror. Prints MATCH / MISMATCH per group."""
    p = os.path.join(IOS, "HeatGuardianTests/herday_vectors_fw.json")
    if not os.path.exists(p):
        print("  herday fw vectors: not present"); return None
    F = json.load(open(p, encoding="utf-8"))
    res = {}
    def rec(name, ok, what):
        check(ok, "FW HERDAY " + name + " " + what)
        res[name] = res.get(name, True) and ok
    def hm(pair, kind_uses=True):
        if not kind_uses: return None
        return None if pair == [255, 255] else pair[0] * 60 + pair[1]
    def fw_item(v):
        k = v["kind"]
        return dict(day=v["day"], kind=k, place=v["place"], usual=hm(v["usual"], k == 1), suggested=hm(v["suggested"], k in (1, 2)),
                    direction=v["direction"] if k == 1 else None, hot_from=v["hot"][0], hot_to=v["hot"][1],
                    peak_c=(None if v["peak_c"] == 255 else v["peak_c"]) if k == 1 else None, heatwave_day=v["heatwave_day"])
    rec("crc8", crc8(list(b"123456789")) == int(F["crc8_check"]["crc8"], 16), "check value")
    for v in F["day_plan"]:
        if v["n"] == 0: got = cmd_day_plan_clear(v["day"])
        else: got = cmd_day_plan(fw_item(v), v["index"], v["n"])
        rec("0x1B DAY_PLAN", hx(got) == v["hex"], v["hex"] + " got " + hx(got))
    # the band's field-error frames: every one the app's types can express must be refused by the app's encoder
    for v in F["day_plan_field_errors"]:
        b = list(bytes.fromhex(v["hex"]))
        if (b[6] != 0xFF) != (b[7] != 0xFF) or b[9] > 59 or b[7] > 59:     # half-set pair / minute 60: no such minute of day
            rec("0x1B field errors", True, ""); continue
        it = dict(day=b[1], kind=b[4], place=b[5], usual=None if b[6] == 0xFF else b[6] * 60 + b[7],
                  suggested=b[8] * 60 + b[9], direction=b[10] or None, hot_from=b[11], hot_to=b[12], peak_c=b[13], heatwave_day=b[14])
        try: cmd_day_plan(it, b[2], b[3]); rec("0x1B field errors", False, v["error"])
        except FrameError: rec("0x1B field errors", True, "")
    for v in F["visit"]:
        rec("0x1C VISIT", hx(cmd_visit(v["event"], v["place"], v["unix"])) == v["hex"], v["hex"])
    for v in F["events"]:
        e = decode_event(list(bytes.fromhex(v["hex"])))
        ok = e["seq"] == v["seq"] and e["boot"] == v["boot_count"] and e["unix"] == v["unix"] and e["kind"] == v["type"]
        if v["type"] == 9:
            vv = event_visit(e)
            ok = ok and vv == dict(edge=v["byte11_event"], place=v["arg_place"], unix=v["bytes12_15_visit_unix"])
            ok = ok and hx(encode_event(visit_event(v["seq"], v["boot_count"], v["unix"], v["byte11_event"], v["arg_place"], v["bytes12_15_visit_unix"]))) == v["hex"]
            rec("EVENTS 9 VISIT", ok, v["hex"])
        elif v["type"] == 10:
            it = event_plan_item(e)
            k = v["arg_kind"]
            want = dict(day=v["byte18_day"], kind=k, place=v["place"], usual=hm(v["usual"], k == 1), suggested=hm(v["suggested"], k in (1, 2)),
                        direction=v["byte18_direction"] or None, hot_from=v["hot"][0], hot_to=v["hot"][1], peak_c=None,
                        heatwave_day=v["byte18_heatwave_day"])
            ok = ok and it is not None and item_eq(it, want)
            ok = ok and hx(encode_event(plan_item_event(v["seq"], v["boot_count"], v["unix"], want))) == v["hex"]
            rec("EVENTS 10 PLAN_ITEM", ok, v["hex"])
        else:
            ok = ok and e["arg"] == v["nudge_id"] and hx(encode_event(e)) == v["hex"]
            rec("EVENTS nudge 7/8", ok, v["hex"])
    for v in F["elder_action_new_ids"]:
        rec("0x1A ELDER_ACTION 7/8", hx(cmd_elder_action(v["action"], v["nudge_id"])) == v["hex"], v["hex"])
    T = F["band_texts"]
    mk = lambda place, s_, d, day=1: dict(day=day, kind=1, place=place, usual=600, suggested=s_, direction=d, hot_from=10, hot_to=20, peak_c=None, heatwave_day=0)
    rec("band texts", hd_brief([mk(1, 570, 1)], True) == T["N7_kind1_before"], "N7 before")
    rec("band texts", hd_brief([mk(5, 1260, 2)], True) == T["N7_kind1_after"], "N7 after")
    rec("band texts", hd_brief([dict(day=1, kind=3, place=0, usual=None, suggested=None, direction=None, hot_from=0, hot_to=0, peak_c=None, heatwave_day=2)], True) == T["N7_kind3_only"], "N7 kind 3")
    rec("band texts", hd_brief([mk(3, 1260, 2, 0)], False) == T["N1_kind1"], "N1")
    rec("band texts", BAND_WORD == T["place_words"], "place words")
    for k in sorted(res): print("  herday fw vectors %-22s %s" % (k, "MATCH" if res[k] else "MISMATCH"))
    return res

# ---------------------------------------------------------------- alert quality (EcoFrames.swift "Alert quality" section,
# band 0.9.9, ECOSYSTEM_SPEC 5e): EVENTS 11 ALERT_HELD, 12 ALL_CLEAR, 13 SCORE
KNOWN_EVENT_TYPES = set(range(1, 14))          # BandEvent.Kind; anything else is ignored by the app (LogEntry.fromBand -> nil)


def alert_held_event(seq, boot, unix, what, reason, arg):   # Frames.alertHeldEvent
    return dict(seq=seq, boot=boot, unix=unix, kind=11, arg=what, ext=[reason, arg & 255, 0, 0, 0, 0, 0, 0])


def all_clear_event(seq, boot, unix, peak, minutes, family, tick):   # Frames.allClearEvent
    mn = max(0, min(65535, minutes))
    return dict(seq=seq, boot=boot, unix=unix, kind=12, arg=peak, ext=[mn & 255, mn >> 8, 1 if family else 0, 1 if tick else 0, 0, 0, 0, 0])


def score_event(seq, boot, unix, page, values):   # Frames.scoreEvent
    return dict(seq=seq, boot=boot, unix=unix, kind=13, arg=page, ext=[max(0, min(255, v)) for v in values[:8]] + [0] * (8 - len(values[:8])))


def event_alert_held(e):                        # BandEvent.alertHeld
    if e["kind"] != 11 or not 1 <= e["arg"] <= 5 or not 1 <= e["ext"][0] <= 9: return None
    return dict(what=e["arg"], reason=e["ext"][0], arg=e["ext"][1])


def event_all_clear(e):                         # BandEvent.allClear
    if e["kind"] != 12: return None
    x = e["ext"]
    return dict(peak=e["arg"], minutes=x[0] | (x[1] << 8), family=x[2] != 0, tick=x[3] != 0)


def event_score_page(e):                        # BandEvent.scorePage
    if e["kind"] != 13 or not 0 <= e["arg"] <= 2: return None
    return dict(page=e["arg"], values=list(e["ext"]))


def alert_fw_checks(check):
    """HeatGuardianTests/alert_vectors_fw.json: made by tools/fw_alert_vectors.c with the band's own 0.9.9 packers."""
    p = os.path.join(IOS, "HeatGuardianTests/alert_vectors_fw.json")
    F = json.load(open(p, encoding="utf-8"))
    res = {}
    def rec(name, ok, what):
        check(ok, "FW ALERT " + name + " " + what)
        res[name] = res.get(name, True) and ok
    for v in F["events"]:
        e = decode_event(list(bytes.fromhex(v["hex"])))
        ok = e["seq"] == v["seq"] and e["boot"] == v["boot"] and e["unix"] == v["unix"] and e["kind"] == v["type"] and e["arg"] == v["arg"]
        if v["type"] == 11:
            h = event_alert_held(e)
            ok = ok and h == dict(what=v["what"], reason=v["reason"], arg=v["held_arg"])
            ok = ok and hx(encode_event(alert_held_event(v["seq"], v["boot"], v["unix"], v["what"], v["reason"], v["held_arg"]))) == v["hex"]
            rec("EVENTS 11 ALERT_HELD", ok, v["hex"])
        elif v["type"] == 12:
            c = event_all_clear(e)
            ok = ok and c == dict(peak=v["peak"], minutes=v["minutes"], family=v["family"] == 1, tick=v["tick"] == 1)
            ok = ok and hx(encode_event(all_clear_event(v["seq"], v["boot"], v["unix"], v["peak"], v["minutes"], v["family"], v["tick"]))) == v["hex"]
            rec("EVENTS 12 ALL_CLEAR", ok, v["hex"])
        else:
            sp = event_score_page(e)
            ok = ok and sp == dict(page=v["page"], values=v["x"])
            ok = ok and hx(encode_event(score_event(v["seq"], v["boot"], v["unix"], v["page"], v["x"]))) == v["hex"]
            rec("EVENTS 13 SCORE", ok, v["hex"])
    # unknown types (14, 255) still decode as frames but are not kinds the app knows: ignored
    for t in (14, 255):
        b = list(bytes.fromhex(F["events"][0]["hex"])); b[9] = t; b[19] = crc8(b, 19)
        e = decode_event(b)
        rec("unknown type ignored", e["kind"] == t and t not in KNOWN_EVENT_TYPES, "type %d" % t)
    for k in sorted(res): print("  alert fw vectors %-22s %s" % (k, "MATCH" if res[k] else "MISMATCH"))
    return res


def main():
    ok = bad = 0
    def check(c, msg):
        nonlocal ok, bad
        if c: ok += 1
        else: bad += 1; print("FAIL", msg)
    rd = lambda p: json.load(open(p, encoding="utf-8"))
    check(crc8(list(b"123456789")) == 0xF4, "crc check value")
    for v in rd(os.path.join(ROOT, "tomorrow/tests/crc8_vectors.json"))["vectors"]:
        check(crc8(list(bytes.fromhex(v["data_hex"]))) == v["crc"], "crc8 " + v["name"])
    SV = rd(os.path.join(IOS, "HeatGuardianTests/status_vectors.json"))
    for v in SV["status"]:
        d = decode_status(list(bytes.fromhex(v["hex"])))
        for k, e in v["expect"].items():
            g = d[KEYMAP[k]]
            good = (g is None and e is None) if (g is None or e is None) else (abs(g - e) < 1e-9 if isinstance(e, (int, float)) and not isinstance(e, bool) else g == e)
            check(good, "%s %s got %r want %r" % (v["hex"], k, g, e))
        # Swift sets exactly the optional trio the JS sets: alarm id XOR routine/activity
        check((d["alarmId16"] is not None) == d["familyPending"] and (d["routineScore"] is None) == d["familyPending"], "optional trio " + v["hex"])
    for h in SV["status_corrupt"]:
        try: decode_status(list(bytes.fromhex(h))); check(False, "corrupt accepted " + h)
        except FrameError: check(True, "")
    try: decode_status(list(bytes.fromhex(SV["status"][0]["hex"][:38]))); check(False, "short accepted")
    except FrameError: check(True, "")
    # the firmware's seed value: 20 zero bytes pass CRC-8 (crc8 of zeros == 0) but must not decode as a reading
    z = [0] * 20
    check(crc8(z, 19) == 0 and is_empty_status(z), "zero seed frame passes CRC and is detected as empty")
    try: decode_status(z); check(False, "zero seed frame accepted")
    except FrameError: check(True, "")
    # a CRC-valid frame with version 2 is refused; the same frame with version 1 decodes
    v2 = list(bytes.fromhex(SV["status"][0]["hex"])); v2[0] = (v2[0] & 0xF0) | 2; v2[19] = crc8(v2, 19)
    try: decode_status(v2); check(False, "version 2 accepted")
    except FrameError: check(True, "")
    check(not is_empty_status(list(bytes.fromhex(SV["status"][0]["hex"]))), "real frame is not empty")
    check(bcd_version(0x0094) == "0.9.4" and bcd_version(0x0096) == "0.9.6" and bcd_version(0x0095) == "0.9.5"
          and bcd_version(0x0910) == "0.9.10" and bcd_version(0x0917) == "0.9.17", "fw BCD text")
    C = SV["cmd"]
    for v in C["time"]: check(hx(cmd_time(v["unix_s"], v["tz_q"])) == v["hex"], "TIME " + v["hex"])
    for v in C["family_ack"]: check(hx(cmd_family_ack(v["ack_type"], v["alarm_id"])) == v["hex"], "ACK " + v["hex"])
    for v in C["profile"]: check(hx(cmd_profile(v["field"], v["value"])) == v["hex"], "PROFILE " + v["hex"])
    check(hx(cmd_consent(3)) == "15031f", "CONSENT 0x03 == fw README example 15031f")
    BV = rd(os.path.join(IOS, "HeatGuardianTests/forecast_vectors.json"))
    check([hx(c) for c in forecast_chunks(BV["plan"])] == BV["forecast_chunks_hex"], "0x11 tomorrow vectors")
    check(hx(safe_hours_frame(BV["plan"])) == BV["safe_hours_hex"], "0x14 tomorrow vectors")
    check(safe_bitmap(BV["plan"]) == BV["safe_hours_bitmap"] and plan_id(BV["plan"]["date"]) == BV["plan_id"], "bitmap / plan id")
    P = rd(os.path.join(IOS, "HeatGuardian/Resources/plan.json"))
    check([hx(c) for c in forecast_chunks(P)] == P["ble"]["forecast_chunks_hex"], "0x11 bundled plan.json")
    check(hx(safe_hours_frame(P)) == P["ble"]["safe_hours_hex"], "0x14 bundled plan.json")
    G = [l.split() for l in open(os.path.join(ROOT, "guardian/tests/ble_vectors.txt")).read().strip().splitlines()]
    Gf = [x[1] for x in G if x[0] == "F"]
    Gh = [x for x in G if x[0] == "H"]
    plan = {"date": "2026-07-14", "heat_day": bool(int(Gh[0][4]) & 1), "night_heat": bool(int(Gh[0][4]) & 2),
            "hours": [{"h": int(x[1]), "t_in": float(x[2]), "rh_in": float(x[3]), "safe": bool(int(x[4]) & 4)} for x in Gh]}
    check([hx(c) for c in forecast_chunks(plan)] == Gf, "0x11 == guardian/tests/ble_vectors.txt F lines")
    # every bundled replay frame decodes
    n = 0
    for f in ("sim_heatwave.json", "htt_chamber.json"):
        R = rd(os.path.join(IOS, "HeatGuardian/Resources", f))
        for h in R["status"]: decode_status(list(bytes.fromhex(h))); n += 1
        fam = [i for i, h in enumerate(R["status"]) if decode_status(list(bytes.fromhex(h)))["familyPending"]]
        ev = [e["i"] for e in R["events"] if e["kind"] == "family_alert"]
        check(all(i in fam for i in ev), f + " family_alert events are family-pending frames")
    check(n == 1440 + 121, "replay frame count %d" % n)
    print("ranges bundled plan:", safe_ranges(P["hours"]) or "none")
    n_before = ok
    eco_checks(check, rd)
    fw_checks(check, rd)
    print("ecosystem checks: %d" % (ok - n_before))
    n_before = ok
    herday_checks(check, rd)
    print("her day checks: %d" % (ok - n_before))
    herday_fw_checks(check)
    n_before = ok
    alert_fw_checks(check)
    print("alert quality checks: %d" % (ok - n_before))
    print("mirror_frames: %d passed, %d failed (%d replay frames decoded)" % (ok, bad, n))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
