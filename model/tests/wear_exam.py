#!/usr/bin/env python3
"""Heat Guardian — PRE-REGISTERED wear-test exam (Nov 16-18 2026, 08_logger recordings).

Written on Nov 12 2026, BEFORE any wear data exists. Frozen by the manager's git tag `wear-freeze`.
After the tag, this file, its thresholds and its pass criteria do not change. Protocol: wear/PROTOCOL.md.
What is SET on day 1 vs SCORED on days 2-3: wear/DEV_VS_EXAM.md.

WHAT IT CAN AND CANNOT PROVE (ARCHITECTURE §2)
  Can: that the band's sensors behave as the simulator assumes; that the contact self-check, home/out and
  routine/sleep logic fire correctly on labelled events; the real false-alarm/CHECK rate of the frozen guardian
  on ordinary days; battery hours; resets.
  Cannot: core-temperature accuracy (oral thermometer is not core; no heat stress), anything about older adults
  (main wearer is 17; relative sessions are short, n = 1, not in heat). Every number is labelled REAL, n = 1,
  wearer age stated. A synthetic test run is labelled SYNTHETIC and proves only that the code runs.

USAGE
  python3 tests/wear_exam.py --data DIR [--phase exam|dev|inspect]
     DIR holds every capture of the test: dump_*.txt / live_*.txt from fw/tools/capture.py, any *.bin copied off
     the band, events.txt, and diary.csv (wear/diary_template.csv format). Sub-folders are read too.
  --phase inspect : data integrity only (coverage, boots, markers per day, diary matching). No sensor outcome.
                    May be run any number of times (to fix diary typos BEFORE the exam).
  --phase dev     : reads ONLY day-1 rows (rows from later days are dropped before any computation) and
                    writes wear/DEV_THRESHOLDS.json. May be run any number of times; its rules are fixed below.
  --phase exam    : (default) the exam. Runs ONCE: refuses if wear/WEAR_EXAM_DONE.json exists; refuses unless the
                    tag `wear-freeze` exists and this file is byte-identical to its copy in that tag; loads and checks
                    the data, then writes the DONE file (inputs' SHA-256, git HEAD) BEFORE any scoring, then scores
                    and completes the same file. A crash after that point still spends the exam.
                    It re-derives the day-1 thresholds with the dev code and, if wear/DEV_THRESHOLDS.json exists,
                    asserts they are identical (nobody hand-edited them).
  --synthetic --done-out PATH : self-test on SYNTHETIC logs only (wear/selftest/); skips the git/tag checks,
                    writes PATH (must not be inside wear/), never wear/WEAR_EXAM_DONE.json.
  Refuses to run without --data.

DATA -> MINUTES (same mapping as fw/09_guardian/hg_fw.c, the code that will run on the band)
  Records: fw/08_logger/log_format.h, parsed by fw/tools/parse_log.py (CRC-8 checked; duplicates across dumps
  removed). Unix time per boot from that boot's TIME sync (a boot never synced is "unanchored" and dropped).
  Local time = Europe/Athens. One wall-clock minute = the 1 Hz seconds inside it; if fewer than 30 seconds exist,
  the band's own 1-minute summary (min.bin) is used instead (5-s arrays = the minute mean, z interpolated).
  T1/T2/T_air/RH/PI = means; HR = median of seconds with quality OK if >= 3 such seconds, else no reading with
  the most frequent quality (OK -> 3); a_std = mean of the per-second a_std (the 08 minute definition; NOTE: the
  09 firmware computes a whole-minute std, which is >= this value, see DEV_VS_EXAM.md risk R1); 5-s samples =
  seconds 4, 9, ..., 59 of the minute; apeak = 2 g if any impact flag; PPG DC = median IR DC of PPG-on seconds;
  flat-still run as hg_fw.c (still and |median z| >= 75 deg); charging = any charging flag; BLE bucket = -1
  (unknown: 08 logs no RSSI, and the wearer's phone travels with him); button = 0 (button presses are labels in
  this test, not answers to a CHECK).

DAYS (noon-to-noon "wear days", so each holds one night)
  t0 = first `donned` marker outside a relative session. DEV_END = the first local 12:00 at least 12 h after t0.
  Day 1 = [start, DEV_END) = DEV (tuning).  Day 2 = [DEV_END, +24 h), Day 3 = [+24 h, +48 h) = EXAM (scored).
  Later rows are ignored. Relative sessions (diary RELATIVE_START..RELATIVE_END) are removed from the main
  wearer's data and analysed on their own, descriptively, never used for tuning.

LABELS (ground truth)
  Markers (button / `mark`): 1 donned, 2 loose, 3 off, 4 shower(off), 5 out, 6 home, 7 oral <degC>, 9 press.
  Contact truth: before the first donned = off; 1 -> worn; 2 -> loose; 3/4 -> off; charging flag -> off.
  Location truth: 5 -> out, 6 -> home (start = home).
  Diary codes needing a press are matched to the nearest unused press (marker 9) within +-10 min; unmatched
  entries keep the diary time (flagged). Fallback: diary OUT / HOME / OFF / DONNED (press + diary line, for when
  a `mark` could not be typed) act as markers 5 / 6 / 3 / 1 unless a real marker of that kind is within 10 min. Intervals: SLEEP..WAKE, WALK_START..END, HOT_START..END,
  FAN_START..END, MEAL_START..END, SPORT_START..END. PULSE <bpm> = 60-s manual radial count.
  Oral sessions = oral readings within 10 min of each other, averaged (one value per session).
  Transition minutes excluded from per-minute contact scores: the first 10 min after an off/shower mark,
  the first 5 min after a donned/loose mark.

PRE-REGISTERED ANALYSES AND CRITERIA (scored on EXAM days 2-3 unless stated; verdicts PASS/FAIL for the band,
CONSISTENT/MISMATCH for "does the simulator's assumption hold", N/A when the data needed are missing.
A FAIL or MISMATCH is a finding, never a reason to change this file; each one needs a written why.)
 (a) Sensor behaviour vs simulator assumptions (sim/velders/sensors.py, R2):
   A1 donning transient: per donning after >= 10 min off with the next 60 min worn and at home, minutes until
      T1 is within 5 % of its step (plateau = mean T1 at minutes 50-60). Sim: median 23 min (20-30, R2 §2.3).
      CONSISTENT if median in [15, 35] min with n >= 2. Also: guardian donning blank (20 min) covers p90?
   A2 dT = T1 - T2 across the foam: worn >= 30 min since donning, home, a_std < 0.02 g, not in HOT/FAN, room
      temperature T_room = (T_air_meas - c*T1)/(1 - c) with c = c_dev, in 20-26 C. Sim/R2 §2.2: 2-5 C.
      CONSISTENT if the median dT is in [2, 5] C; ratio dT/(T1 - T_room) median in [0.25, 0.50] (R2 §5: 0.3-0.45).
      Direction checks: dT lower in HOT minutes than the same day's baseline; higher in FAN minutes (R2 §2.4).
      N/A if T2 is not fitted.
   A3 SHTC3 body-heat coefficient c: per "room test" (off episode 12-60 min, at home, not charging, after >= 20
      min worn): c = (T_air,on - T_air,off)/(T1,on - T_air,off); on = last 10 worn min, off = off-minutes 10-15.
      Sim: c ~ U(0.05, 0.30) (R2 §6.2). CONSISTENT if the exam median is in [0.05, 0.30].
      A3b: room-temperature prediction with c_dev at exam room tests: |error| <= 0.5 C on every test -> PASS.
   A4 PPG valid-minute rate (>= 3 OK seconds): rest = awake, worn >= 20 min since donning, home, a_std < 0.02,
      not charging. Sim/R2 §6.3: 75-90 % at rest. CONSISTENT if >= 75 %. Sleep: reported. Walking (WALK
      intervals): reported; the simulator assumes ~0 % (quality "motion" whenever moving).
      A4b: band HR (median of OK seconds within +-2 min) vs manual PULSE: MAE <= 5 bpm (sigma 3 bpm, R2 §6.3)
      -> CONSISTENT, n >= 3.
   A5 loose-band signature per LOOSE episode: dT1 (last 5 loose min - 5 min before), d(dT), PI ratio, |dz| at
      onset. Sim (VALIDATION R2-loose): T1 -0.35 C, dT -0.24 C, PI x0.42; R2 §5: -0.5..-2 C step.
      CONSISTENT if median dT1 < 0 and median PI ratio < 1.
 (b) Contact self-check (frozen hg_contact inside the frozen guardian) vs labels, 3x3 confusion matrix:
   B1 off minutes (not charging) detected off >= 90 % -> PASS.   B2 worn minutes called off <= 1 % -> PASS.
   B3 LOOSE episodes with >= 1 loose/off minute in [mark, mark + 12 min] >= 50 % -> PASS (low bar: the loose
      rule has no published validation).   B4 worn minutes called loose <= 2 % -> PASS.
   B5 every charging minute is off -> PASS.  The dev-set contact thresholds are scored the same way.
 (c) Home/out (frozen hg_homeout, all DESIGN thresholds) vs out/home marks:
   C1 trips (OUT label >= 15 min) reaching TRANSIT or OUT at least once >= 50 % -> PASS.
   C2 home-labelled worn minutes called OUT <= 5 % -> PASS.   C3 per-minute agreement: reported.
 (d) Sleep window and routine profile:
   D1 frozen HDCZA (hg_routine) window computed at the noon closing each exam night vs diary SLEEP/WAKE:
      |onset error| <= 60 min AND |wake error| <= 60 min, per night -> PASS (van Hees 2018 vs diary: MAE 40/30).
   D2 the same with the dev-set HDCZA multiplier (own implementation of the identical algorithm).
   D3 in-bed minutes (exam nights, SLEEP+15 .. WAKE-15) with a_std <= STILL_G_dev >= 90 % -> PASS; frozen 0.002 g
      reported. Awake still runs >= 10 min per worn awake hour: reported (verification §4e: 0.017-0.08/h).
   D4 routine profile after 3 days (descriptive): hours learned (n >= 3), active minutes per hour, max quiet
      runs, IS/IV/RA over the 3 days (Van Someren; < 5 days = less accurate, Posner 2021).
 (e) Frozen guardian (tag hg2-freeze-3, guardian/py mirror, weights SHA-256 asserted against FROZEN.txt) replayed
     on the real minutes, profile = wearer (young, healthy) and default twin: per day and per path
     DRINK onsets/minutes, COOL, DANGER, CHECK starts by reason, family flags, NOT_WORN screens, nudges.
     November, no heat exposure, healthy wearer: every thermal alarm is FALSE.
   E1 DRINK <= 3 onsets and <= 90 min on each exam day (M9.2 budget) -> PASS.
   E2 COOL = 0 and DANGER = 0 on the exam days -> PASS.
   E3 CHECK starts <= 1 in total over the 2 exam days (budget <= 1 per wearer-week, M1.4) -> PASS. Family flags
      are reported beside it: the replay never presses the button, so every CHECK that is not cleared by
      movement becomes a would-be family call (5 min thermal/behaviour/impact, 10 min routine).
   E4 dev-variant replay (day-1 thresholds patched in): same three criteria, reported beside the frozen ones.
   E5 profile swap (age 75, no medication): reported, not scored ("what the elder profile does on these signals").
 (f) Oral reading vs displayed range: per exam-day oral session with core valid, inside if
     |oral - core_now| <= half-range shown (max(1.645 sd, 0.578 C REAL) ~ +-0.6 C).
   F1 coverage >= 80 % with n >= 4 sessions -> PASS (else N/A). Bias, MAE, Wilson 95 % CI, thermometer
      repeatability (pairs) reported. This is NOT a core-accuracy claim: oral is not core.
 (g) Firmware and battery (whole recording):
   G1 watchdog resets = 0 (whole recording) -> PASS.  G1b power-on/brown-out, lockup or reset-pin boots inside the
      wear period = 0 -> PASS (uploads are "SOFTWARE(upload)" and do not count).
   G2 CRC errors = 0 -> PASS.   G3 minute coverage of the wear period >= 99 %.
   G4 no LOWBAT event -> PASS; battery V/h slope on battery, measured longest span, hours 4.10 -> 3.50 V
      (EXTRAPOLATED, linear; LiPo is not linear).
   G5 unanchored minutes (boot never time-synced) <= 1 % -> PASS.  G6 T1/T_air/RH/a_std present in >= 99 % of
      worn seconds -> PASS (T2 and PPG reported).

DEV RULES (day 1 only; deterministic; the exam recomputes them)
  STILL_G_dev  = 95th pct of a_std over night-1 in-bed minutes (SLEEP+15..WAKE-15), rounded UP to 0.0005 g,
                 clamped [0.001, 0.010]; fallback frozen 0.002 if < 120 in-bed minutes.
  ACTIVE_G_dev = smallest of {0.005, 0.0075, 0.01, 0.015, 0.02, 0.03} g that keeps >= 97 % of night-1 in-bed
                 minutes non-active; fallback frozen 0.02.
  WALK_G_dev   = 10th pct of a_std over day-1 WALK minutes, rounded DOWN to 0.005 g, clamped [0.02, 0.10];
                 fallback frozen 0.05 if < 10 walk minutes.
  HDCZA_MULT_dev = the one of {10, 15, 20} minimising |onset err| + |wake err| on night 1; ties -> 15 (published);
                 fallback 15 if the night-1 window has < 200 worn 5-min blocks.
  Contact grid (STEP_C {-0.3,-0.5,-0.8} x RATIO_DROP {0.6,0.7,0.8} x OFF_NEAR_C {1.0,1.5}) maximising
                 (loose+off minutes detected not-worn) - 3 x (worn minutes detected not-worn) on day 1; ties ->
                 frozen values. Needs >= 1 loose episode, else frozen.
  c_dev        = median c of day-1 room tests, clamped [0, 0.4]; fallback 0.15 (twin default).
  rest_HR_dev  = 10th pct of valid in-bed minute HR on night 1, clamped [40, 100]; fallback 70.
"""
import argparse, bisect, datetime as dt, glob, hashlib, importlib, io, json, math, os, subprocess, sys, tarfile, tempfile
import numpy as np
import pandas as pd

EXAM_VERSION = "wear-exam-1.0 (pre-registered Nov 12 2026)"
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
WEAR = os.path.join(REPO, "wear")
DONE = os.path.join(WEAR, "WEAR_EXAM_DONE.json")
DEV_FILE = os.path.join(WEAR, "DEV_THRESHOLDS.json")
REPORT = os.path.join(WEAR, "WEAR_EXAM_REPORT.md")
FREEZE_TAG = "hg2-freeze-3"
WEAR_TAG = "wear-freeze"
WEIGHTS_SHA = "e00eb0073ccccf2bf6bc541180b3fc0d61d2f7792e3b9997a77efe0e13768bbd"   # FROZEN.txt hg2_weights.json
TZ = "Europe/Athens"
NAN = float("nan")

# ------------------------------------------------------------------ pre-registered constants (do not edit)
CRIT = dict(
    A1_lo=15.0, A1_hi=35.0, A2_lo=2.0, A2_hi=5.0, A2r_lo=0.25, A2r_hi=0.50, A2_room=(20.0, 26.0),
    A3_lo=0.05, A3_hi=0.30, A3b_err=0.5, A4_rest=0.75, A4b_mae=5.0,
    B1=0.90, B2=0.01, B3=0.50, B4=0.02, C1=0.50, C2=0.05, D1_err=60.0, D3=0.90,
    E1_n=3, E1_min=90, E3=1, F1=0.80, F1_n=4, G3=0.99, G5=0.01, G6=0.99)
WEARER = dict(age=float(os.environ.get("HG_WEARER_AGE", "25")), sex_m=1.0, bmi=float(os.environ.get("HG_WEARER_BMI", "23")), med_flags=0)  # main wearer: set HG_WEARER_AGE / HG_WEARER_BMI; the published default is a generic young adult
ELDER_SWAP = dict(age=75.0, sex_m=1.0, bmi=26.0, med_flags=0)      # E5 profile swap
PRESS_CODES = {"SLEEP", "WAKE", "MEAL_START", "MEAL_END", "WALK_START", "WALK_END", "HOT_START", "HOT_END",
               "FAN_START", "FAN_END", "SPORT_START", "SPORT_END", "OUT", "HOME", "OFF", "DONNED"}
FALLBACK = {"OUT": 5, "HOME": 6, "OFF": 3, "DONNED": 1}     # press + diary line when a `mark` could not be typed
INTERVALS = {"SLEEP": "WAKE", "WALK_START": "WALK_END", "HOT_START": "HOT_END", "FAN_START": "FAN_END",
             "MEAL_START": "MEAL_END", "SPORT_START": "SPORT_END"}
MATCH_S = 600            # diary <-> press matching window
FROZEN_STILL, FROZEN_ACTIVE, FROZEN_WALK = 0.002, 0.02, 0.05
FROZEN_CT = dict(HG_CT_STEP_C=-0.5, HG_CT_RATIO_DROP=0.7, HG_CT_OFF_NEAR_C=1.0)


def die(msg, code=2):
    print("REFUSING: " + msg, file=sys.stderr)
    sys.exit(code)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git(*a):
    r = subprocess.run(["git", "-C", REPO] + list(a), capture_output=True)
    return r.returncode, r.stdout


# ------------------------------------------------------------------ frozen guardian (from the tag, not the working tree)
def load_frozen_guardian(tmp):
    rc, tar = git("archive", "--format=tar", FREEZE_TAG, "guardian/py", "model/export/hg2_weights.json")
    if rc != 0:
        die("cannot read tag %s from git" % FREEZE_TAG)
    tarfile.open(fileobj=io.BytesIO(tar)).extractall(tmp, filter="data")
    wpath = os.path.join(tmp, "model/export/hg2_weights.json")
    if sha256_file(wpath) != WEIGHTS_SHA:
        die("frozen weights SHA-256 differs from FROZEN.txt")
    sys.path.insert(0, os.path.join(tmp, "guardian/py"))
    os.environ.pop("HG_WEIGHTS", None)
    hg = importlib.import_module("hg_guardian_py")
    W = hg.Weights(wpath)
    if W.stub:
        die("frozen weights are the stub")
    return hg, W


# ------------------------------------------------------------------ loading
def load_parse_log():
    sys.path.insert(0, os.path.join(REPO, "fw", "tools"))
    return importlib.import_module("parse_log")


def find_inputs(d):
    fs = []
    for root, _, names in os.walk(d):
        for n in sorted(names):
            p = os.path.join(root, n)
            if n.endswith((".txt", ".bin", ".log", ".csv")):
                fs.append(p)
    return sorted(fs)


def scan_events(paths):
    """MARK / BOOT / LOWBAT / SENSOR / DELETE lines from live '#' lines and dumped 'E ' lines, deduplicated."""
    seen, ev = set(), []
    for p in paths:
        if not p.endswith((".txt", ".log")) or os.path.basename(p).lower().startswith("diary"):
            continue
        with open(p, errors="replace") as f:
            for line in f:
                s = line.strip()
                if not (s.startswith("E ") or s.startswith("#") or "# " in s[:40]):
                    continue
                body = s[s.find("#") + 1:].strip() if not s.startswith("E ") else s[2:].strip()
                for key in ("MARK boot=", "BOOT boot=", "LOWBAT ON", "LOWBAT OFF", "SENSOR LOST", "SENSOR BACK",
                            "UNDUMPED", "RING HOLD"):
                    i = body.find(key)
                    if i >= 0 and (i == 0 or key == "UNDUMPED"):
                        if body not in seen:
                            seen.add(body)
                            kv = {}
                            for tok in body.split():
                                if "=" in tok:
                                    k, v = tok.split("=", 1)
                                    kv[k] = v
                            ev.append(dict(kind=key.split()[0], text=body, **kv))
                        break
    return ev


def load_diary(paths):
    rows = []
    for p in paths:
        if os.path.basename(p).lower().startswith("diary") and p.endswith(".csv"):
            d = pd.read_csv(p, dtype=str, comment="#").fillna("")
            d.columns = [c.strip().lower() for c in d.columns]
            for r in d.itertuples():
                if not r.code.strip():
                    continue
                t = pd.Timestamp(r.date.strip() + " " + r.time.strip()).tz_localize(TZ)
                rows.append(dict(unix=t.timestamp(), code=r.code.strip().upper(), value=r.value.strip(), note=r.note.strip()))
    return sorted(rows, key=lambda r: r["unix"])


def load_recording(data_dir, pl):
    paths = find_inputs(data_dir)
    if not paths:
        die("no capture files in %s" % data_dir)
    p = pl.Parser()
    for f in paths:
        b = os.path.basename(f).lower()
        if b.startswith("diary") or b.endswith(".csv"):
            continue
        p.parse(f)
    df = p.table()
    ev = scan_events(paths)
    diary = load_diary(paths)
    syncs = {int(b): s[-1] for b, s in p.time_syncs.items()}
    return dict(paths=paths, df=df, events=ev, diary=diary, syncs=syncs, crc_errors=p.crc_errors,
                sha={os.path.relpath(f, data_dir): sha256_file(f) for f in paths})


# ------------------------------------------------------------------ markers and labels
def collect_markers(rec):
    syncs = rec["syncs"]
    out = []
    for e in rec["events"]:
        if e["kind"] != "MARK":
            continue
        m = int(e.get("m", 0))
        if not 1 <= m <= 9:
            continue
        b, tms = int(e.get("boot", -1)), int(e.get("t_ms", 0))
        u = NAN
        if b in syncs:
            ts, us = syncs[b]
            u = us + (tms - ts) / 1000.0
        elif int(e.get("unix", 0)) > 1.7e9:
            u = float(e["unix"])
        if u == u:
            out.append(dict(unix=u, m=m, v=int(e.get("v", 0)), src="event"))
    df = rec["df"]
    mk = df[(df.marker >= 1) & (df.marker <= 9) & df.unix_s.notna()]
    for r in mk.itertuples():
        if not any(o["m"] == r.marker and abs(o["unix"] - r.unix_s) < 75 for o in out):
            out.append(dict(unix=float(r.unix_s), m=int(r.marker), v=int(round((r.marker_value or 0) * 100)) if r.marker == 7 and r.marker_value == r.marker_value else 0, src="record"))
    out.sort(key=lambda o: o["unix"])
    # collapse duplicates (same marker within 3 s)
    res = []
    for o in out:
        if res and res[-1]["m"] == o["m"] and abs(res[-1]["unix"] - o["unix"]) < 3:
            continue
        res.append(o)
    return res


def match_diary(diary, markers):
    presses = [o for o in markers if o["m"] == 9]
    used = set()
    out, unmatched = [], 0
    for d in diary:
        e = dict(d)
        e["matched"] = False
        if d["code"] in PRESS_CODES:
            best, bi = None, None
            for i, pr in enumerate(presses):
                if i in used:
                    continue
                dd = abs(pr["unix"] - d["unix"])
                if dd <= MATCH_S and (best is None or dd < best):
                    best, bi = dd, i
            if bi is not None:
                used.add(bi)
                e["unix"] = presses[bi]["unix"]
                e["matched"] = True
            else:
                unmatched += 1
        out.append(e)
    out.sort(key=lambda r: r["unix"])
    return out, unmatched, len(presses) - len(used)


def intervals(diary, start_code, end_code):
    iv, open_t = [], None
    for d in diary:
        if d["code"] == start_code:
            open_t = d["unix"]
        elif d["code"] == end_code and open_t is not None:
            if d["unix"] > open_t:
                iv.append((open_t, d["unix"]))
            open_t = None
    return iv


def in_iv(u, iv):
    return any(a <= u < b for a, b in iv)


def relative_windows(diary, markers):
    """RELATIVE_START value=<age> .. RELATIVE_END (diary, no press)"""
    out, cur = [], None
    for d in diary:
        if d["code"] == "RELATIVE_START":
            cur = (d["unix"], float(d["value"]) if d["value"] else 75.0, d.get("note", ""))
        elif d["code"] == "RELATIVE_END" and cur:
            out.append(dict(start=cur[0] - 300, end=d["unix"] + 300, age=cur[1], note=cur[2]))
            cur = None
    return out


# ------------------------------------------------------------------ minutes (hg_fw.c mapping)
def local_mod(unix_min):
    t = pd.to_datetime(np.asarray(unix_min) * 60, unit="s", utc=True).tz_convert(TZ)
    return np.asarray(t.hour * 60 + t.minute, dtype=int)


def build_minutes(rec):
    df = rec["df"]
    sec = df[(~df.is_minute) & df.unix_s.notna()].copy()
    mins = df[(df.is_minute) & df.unix_s.notna()].copy()
    rows = {}
    if len(sec):
        sec["minute"] = np.floor(sec.unix_s / 60).astype(np.int64)
        sec["s"] = (np.floor(sec.unix_s).astype(np.int64) % 60)
        sec = sec.sort_values("unix_s")
        for mnt, g in sec.groupby("minute", sort=True):
            q = g.hr_quality.to_numpy()
            ok = (q == 4) & g.HR_meas.notna().to_numpy() & (g.HR_meas.to_numpy() >= 30) & (g.HR_meas.to_numpy() <= 220)
            nok = int(ok.sum())
            if nok >= 3:
                hr, hq = float(np.sort(g.HR_meas.to_numpy()[ok])[nok // 2]), 4
            else:
                qq = q[~np.isnan(q)]
                if len(qq):
                    vals, cnt = np.unique(qq.astype(int), return_counts=True)
                    best = int(vals[np.argmax(cnt)])
                    hr, hq = NAN, (3 if best == 4 else best)
                else:
                    hr, hq = NAN, 0
            ppg_on = ~np.isnan(q)
            arr = {}
            for col, key in (("T1", "t1_5s"), ("T2", "t2_5s"), ("T_air_meas", "tair_5s"), ("zangle_deg", "zang")):
                a = [NAN] * 12
                for s, v in zip(g.s.to_numpy(), g[col].to_numpy()):
                    if s % 5 == 4:
                        a[s // 5] = float(v)
                arr[key] = a
            astd = g.a_std_g.to_numpy()
            dcv = g.ir_dc.to_numpy()[ppg_on]
            dcv = dcv[~np.isnan(dcv)]
            rows[int(mnt)] = dict(minute=int(mnt), src="1hz", n_sec=len(g), boot=int(g.boot.iloc[-1]),
                                  t1=g.T1.mean(), t2=g.T2.mean(), tair=g.T_air_meas.mean(), rh=g.RH_meas.mean(),
                                  hr=hr, hrq=hq, n_ok=nok, n_ppg=int(ppg_on.sum()),
                                  pi=float(np.nanmean(g.PI.to_numpy()[ppg_on])) if ppg_on.any() else NAN,
                                  astd=float(np.nanmean(astd)) if np.isfinite(astd).any() else NAN,
                                  apeak=2.0 if g.impact.any() else 1.0,
                                  dc=int(np.median(dcv)) if len(dcv) else 0,
                                  charging=int(g.charging.any()), lowbat=int(g.low_batt_mode.any()), vbat=NAN, **arr)
    if len(mins):
        mins["minute"] = np.floor((mins.unix_s + 30) / 60).astype(np.int64)
        prevz = None
        for r in mins.sort_values("unix_s").itertuples():
            mnt = int(r.minute)
            if mnt in rows and rows[mnt]["n_sec"] >= 30:
                rows[mnt]["vbat"] = r.vbat
                if rows[mnt]["charging"] == 0 and r.charging:
                    rows[mnt]["charging"] = 1
                prevz = r.zangle_deg
                continue
            z0 = prevz if prevz is not None else r.zangle_deg
            zs = list(np.linspace(z0, r.zangle_deg, 13)[1:])
            prevz = r.zangle_deg
            rows[mnt] = dict(minute=mnt, src="min", n_sec=0, boot=int(r.boot), t1=r.T1, t2=r.T2, tair=r.T_air_meas,
                             rh=r.RH_meas, hr=r.HR_meas if r.hr_quality == 4 else NAN,
                             hrq=int(r.hr_quality) if r.hr_quality == r.hr_quality else 0, n_ok=5 if r.hr_quality == 4 else 0,
                             n_ppg=60 if r.hr_quality == r.hr_quality else 0, pi=r.PI, astd=r.a_std_g,
                             apeak=2.0 if r.impact else 1.0, dc=0, charging=int(r.charging), lowbat=int(r.low_batt_mode),
                             vbat=r.vbat, t1_5s=[r.T1] * 12, t2_5s=[r.T2] * 12, tair_5s=[r.T_air_meas] * 12, zang=zs)
    M = pd.DataFrame(sorted(rows.values(), key=lambda r: r["minute"]))
    if len(M):
        M["mod"] = local_mod(M.minute.to_numpy())
        M["vbat"] = M.vbat.ffill().bfill()
    return M


def flat_runs(M, still_g):
    out, run = [], 0
    for z, a in zip(M.zang, M.astd):
        zz = [v for v in z if v == v]
        zmed = float(np.sort(zz)[len(zz) // 2]) if zz else NAN
        still = a == a and a <= still_g
        run = min(run + 1, 255) if (still and zmed == zmed and abs(zmed) >= 75.0) else 0
        out.append(run)
    return out


def label_minutes(M, markers, diary, extra_off=None):
    """per-minute truth: contact (0 off,1 loose,2 worn), location (0 home, 2 out), and transition-exclusion flag"""
    u = (M.minute.to_numpy() * 60 + 30).astype(float)
    contact = np.zeros(len(M), int); loc = np.zeros(len(M), int); excl = np.zeros(len(M), bool)
    since_don = np.full(len(M), 9999.0)
    ev = sorted(markers, key=lambda o: o["unix"])
    c, l, last_change, last_kind, don_t = 0, 0, -1e18, None, -1e18
    j = 0
    for i, t in enumerate(u):
        while j < len(ev) and ev[j]["unix"] <= t:
            m = ev[j]["m"]
            if m == 1: c, last_change, last_kind, don_t = 2, ev[j]["unix"], "don", ev[j]["unix"]
            elif m == 2: c, last_change, last_kind = 1, ev[j]["unix"], "loose"
            elif m in (3, 4): c, last_change, last_kind = 0, ev[j]["unix"], "off"
            elif m == 5: l = 2
            elif m == 6: l = 0
            j += 1
        cc = 0 if M.charging.iat[i] else c
        contact[i] = cc; loc[i] = l
        win = 600 if last_kind == "off" else 300
        excl[i] = (t - last_change) < win
        since_don[i] = (t - don_t) / 60.0 if c >= 1 else 9999.0
    M = M.copy()
    M["truth_contact"], M["truth_loc"], M["trans_excl"], M["min_since_don"] = contact, loc, excl, since_don
    for a, b in INTERVALS.items():
        iv = intervals(diary, a, b)
        M["in_" + a.split("_")[0].lower()] = [in_iv(t, iv) for t in u]
    return M


# ------------------------------------------------------------------ guardian replay
class Patch:
    """swap frozen constants in the mirror's table during one sub-step (the C build would recompile them)"""
    def __init__(self, hg, values):
        self.hg, self.values, self.old = hg, values, {}

    def __enter__(self):
        for k, v in self.values.items():
            self.old[k] = self.hg._C[k]
            self.hg._C[k] = np.float32(v)

    def __exit__(self, *a):
        for k, v in self.old.items():
            self.hg._C[k] = v


def wrap_step(obj, hg, values):
    if not values:
        return
    orig = obj.step

    def step(*a, **k):
        with Patch(hg, values):
            return orig(*a, **k)
    obj.step = step


def replay(hg, W, M, profile, twin, dev=None):
    g = hg.Guardian(profile, twin, W)
    glob_patch = {}
    if dev:
        glob_patch = dict(HG_STILL_G=dev["STILL_G"], HG_WALK_G=dev["WALK_G"])
        wrap_step(g.rt, hg, dict(HG_ACTIVE_G=dev["ACTIVE_G"]))
        wrap_step(g.ct, hg, {k: dev["contact"][k] for k in FROZEN_CT})
    flats = flat_runs(M, dev["STILL_G"] if dev else FROZEN_STILL)
    out, sleepwin = [], []
    last_days = 0
    with Patch(hg, glob_patch):
        for i, r in enumerate(M.itertuples()):
            m = dict(mod=int(r.mod), t1=r.t1, t2=r.t2, tair=r.tair, rh=r.rh, hr=r.hr, hrq=int(r.hrq), pi=r.pi,
                     astd=r.astd, apeak=r.apeak, dc=int(r.dc), flat=int(flats[i]), button=0, charging=int(r.charging),
                     vbat=r.vbat if r.vbat == r.vbat else 3.9, ble=-1, force_worn=0xFF, cmd=None,
                     t1_5s=list(r.t1_5s), t2_5s=list(r.t2_5s), tair_5s=list(r.tair_5s), zang=list(r.zang), forecast=None)
            o = g.step(m)
            sd = float(o["core_sd_now"])
            half = max(1.645 * max(sd, float(hg.K("HG_SD_FLOOR"))), float(hg.K("HG_RANGE_HALF_REAL_EFF")))
            out.append(dict(minute=r.minute, state=o["state"], level=o["level"], family=o["family_alert"],
                            check_min=o["check_min"], check_reason=o["check_reason"], worn=o["worn"], home_out=o["home_out"],
                            core_now=float(o["core_now"]), core_valid=int(o["core_valid"]), half=half, sd_now=sd, why=o["why"],
                            nudge=o["nudge"], screen=o["screen"], routine_req=o["routine_req"], tiers=o["tiers"]))
            if g.rt.days_learned != last_days:
                last_days = g.rt.days_learned
                sleepwin.append(dict(minute=int(r.minute), on=int(g.rt.sleep_on), off=int(g.rt.sleep_off),
                                     thr=int(g.rt.hdcza_thr)))
    prof = dict(am=[dict(n=float(w.n), mean=float(w.mean)) for w in g.rt.am], maxq=[int(v) for v in g.rt.maxq],
                days_learned=int(g.rt.days_learned))
    return pd.DataFrame(out), sleepwin, prof


def count_events(R, day_of):
    ev = []
    pl, pf, pcm = 0, 0, 0xFF
    for r in R.itertuples():
        d = day_of(r.minute)
        if r.level >= 1 and pl < 1: ev.append((d, "DRINK", r.minute, r.why))
        if r.level >= 2 and pl < 2: ev.append((d, "COOL", r.minute, r.why))
        if r.level >= 3 and pl < 3: ev.append((d, "DANGER", r.minute, r.why))
        if r.check_min == 0 and pcm != 0: ev.append((d, "CHECK", r.minute, r.check_reason))
        if r.family and not pf: ev.append((d, "FAMILY", r.minute, 0))
        if r.nudge: ev.append((d, "NUDGE", r.minute, 0))
        pl, pf, pcm = r.level, r.family, r.check_min
    return ev


def per_day_counts(R, ev, day_of, days=(1, 2, 3)):
    days_arr = np.array([day_of(m) for m in R.minute])
    out = {}
    for d in days:
        e = [x for x in ev if x[0] == d]
        sel = days_arr == d
        reasons = {}
        for x in e:
            if x[1] == "CHECK":
                for bit, nm in ((1, "thermal_danger"), (2, "behaviour"), (4, "routine_quiet"), (8, "no_wake"), (16, "impact")):
                    if x[3] & bit:
                        reasons[nm] = reasons.get(nm, 0) + 1
        out[d] = dict(minutes=int(sel.sum()), drink=sum(1 for x in e if x[1] == "DRINK"),
                      drink_min=int((R.level.to_numpy()[sel] >= 1).sum()), cool=sum(1 for x in e if x[1] == "COOL"),
                      danger=sum(1 for x in e if x[1] == "DANGER"), check=sum(1 for x in e if x[1] == "CHECK"),
                      check_reasons=reasons, family=sum(1 for x in e if x[1] == "FAMILY"),
                      nudge=sum(1 for x in e if x[1] == "NUDGE"),
                      not_worn_screen_min=int((R.screen.to_numpy()[sel] == 7).sum()),
                      core_valid_min=int(R.core_valid.to_numpy()[sel].sum()))
    return out


# ------------------------------------------------------------------ analyses
def pct(x, q):
    x = np.asarray([v for v in x if v == v], float)
    return float(np.percentile(x, q)) if len(x) else NAN


def med(x):
    return pct(x, 50)


def wilson(k, n, z=1.96):
    if n == 0:
        return (NAN, NAN)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def row(id_, what, value, criterion, verdict, sim="", detail=None):
    return dict(id=id_, what=what, value=value, criterion=criterion, verdict=verdict, sim_assumption=sim,
                detail=detail if detail is not None else {}, why="" if verdict in ("FAIL", "MISMATCH") else None)


def donnings(M, markers, sel_days, day_of):
    res = []
    don = [o for o in markers if o["m"] == 1]
    offs = [o for o in markers if o["m"] in (3, 4, 2)]
    idx = {m: i for i, m in enumerate(M.minute)}
    for o in don:
        prev = [x for x in offs if x["unix"] < o["unix"]]
        if not prev or prev[-1]["m"] == 2 or o["unix"] - prev[-1]["unix"] < 600:
            continue
        m0 = int(o["unix"] // 60) + 1
        if day_of(m0) not in sel_days:
            continue
        seg = [idx.get(m0 + k) for k in range(61)]
        if any(s is None for s in seg):
            continue
        sub = M.iloc[seg]
        if (sub.truth_contact != 2).any() or (sub.truth_loc != 0).any() or sub.t1.isna().any():
            continue
        t1 = sub.t1.to_numpy()
        plateau = t1[50:61].mean()
        if abs(t1[50] - t1[60]) > 0.3:
            continue
        step = plateau - t1[0]
        if abs(step) < 0.5:
            continue
        k = np.nonzero(np.abs(t1 - plateau) <= 0.05 * abs(step))[0]
        res.append(dict(minute=m0, day=day_of(m0), t95_min=int(k[0]) if len(k) else 60, step_c=float(step)))
    return res


def room_tests(M, markers, sel_days, day_of):
    res = []
    idx = {m: i for i, m in enumerate(M.minute)}
    ev = sorted(markers, key=lambda o: o["unix"])
    for i, o in enumerate(ev):
        if o["m"] != 3:
            continue
        nxt = next((x for x in ev[i + 1:] if x["m"] in (1, 2, 4)), None)
        if nxt is None:
            continue
        dur = (nxt["unix"] - o["unix"]) / 60
        if not 12 <= dur <= 60:
            continue
        m_off = int(o["unix"] // 60)
        if day_of(m_off) not in sel_days:
            continue
        on = [idx.get(m_off - k) for k in range(1, 11)]
        off = [idx.get(m_off + k) for k in range(10, 16)]
        pre = [idx.get(m_off - k) for k in range(1, 21)]
        if any(s is None for s in on + off) or any(s is None for s in pre):
            continue
        Mon, Moff, Mpre = M.iloc[on], M.iloc[off], M.iloc[pre]
        if (Mpre.truth_contact != 2).any() or (Mpre.truth_loc != 0).any() or Moff.charging.any() or (Moff.truth_loc != 0).any():
            continue
        ta_on, t1_on, ta_off = Mon.tair.mean(), Mon.t1.mean(), Moff.tair.mean()
        if not (t1_on - ta_off) > 1.0:
            continue
        res.append(dict(minute=m_off, day=day_of(m_off), c=float((ta_on - ta_off) / (t1_on - ta_off)),
                        t_room_off=float(ta_off), t1_on=float(t1_on), tair_on=float(ta_on)))
    return res


def hdcza(M, worn, start_min, end_min, mult):
    """identical algorithm to hg_routine noon() (R3 §3.2 / GGIR), float degrees; window [start_min, end_min)"""
    sel = (M.minute >= start_min) & (M.minute < end_min)
    blocks = {}
    lastz = NAN
    for r, w in zip(M[sel].itertuples(), worn[sel.to_numpy()]):
        b = (r.minute - start_min) // 5
        if b not in blocks:
            blocks[b] = dict(dz=[], ok=True)
        if w != 2:
            blocks[b]["ok"] = False
            lastz = NAN
            continue
        for z in r.zang:
            if z == z and lastz == lastz:
                blocks[b]["dz"].append(abs(z - lastz))
            lastz = z
    nb = (end_min - start_min) // 5
    med5 = np.full(nb, np.nan)
    for b, v in blocks.items():
        if 0 <= b < nb and v["ok"] and len(v["dz"]) >= 30:
            med5[b] = np.median(v["dz"])
    ok = ~np.isnan(med5)
    if ok.sum() < 200 * nb / 288:
        return None
    p10 = np.sort(med5[ok])[int(math.ceil(ok.sum() * 10 / 100)) - 1]
    thr = min(0.50, max(0.13, mult * p10))
    fl = (ok & (med5 < thr)).astype(int)
    c = 0
    while c < nb:
        if not fl[c]:
            c += 1; continue
        e = c
        while e < nb and fl[e]: e += 1
        if e - c <= 6: fl[c:e] = 0
        c = e
    c = 0
    while c < nb:
        if fl[c]:
            c += 1; continue
        e = c
        while e < nb and not fl[e]: e += 1
        if c > 0 and e < nb and (e - c) < 12: fl[c:e] = 1
        c = e
    best, bs, c = 0, -1, 0
    while c < nb:
        if not fl[c]:
            c += 1; continue
        e = c
        while e < nb and fl[e]: e += 1
        if e - c > best: best, bs = e - c, c
        c = e
    if bs < 0:
        return None
    return (start_min + bs * 5, start_min + (bs + best) * 5)


def circ_err(est_min_of_day, true_unix):
    """signed error in minutes between an estimated local minute-of-day and a true event time"""
    tm = int(local_mod([int(true_unix // 60)])[0])
    d = (est_min_of_day - tm + 720) % 1440 - 720
    return float(d)


def contact_only(hg, M, dev_ct, still_g):
    """frozen hg_contact on its own (fast), optionally with patched thresholds"""
    c = hg.Contact()
    flats = flat_runs(M, still_g)
    out = []
    with Patch(hg, dev_ct or {}):
        for i, r in enumerate(M.itertuples()):
            out.append(c.step(list(r.t1_5s), list(r.t2_5s), list(r.tair_5s), r.pi, int(r.hrq), int(r.dc), r.astd,
                              int(flats[i]), int(r.charging)))
    return np.array(out)


def contact_scores(M, worn, sel, markers, day_of, days):
    tc = M.truth_contact.to_numpy()
    ex = M.trans_excl.to_numpy()
    ch = M.charging.to_numpy().astype(bool)
    s = sel & ~ex
    cm = np.zeros((3, 3), int)
    for t, w in zip(tc[s], worn[s]):
        cm[t, w] += 1
    off_nc = s & (tc == 0) & ~ch
    worn_m = s & (tc == 2)
    idx = {m: i for i, m in enumerate(M.minute)}
    eps = []
    for o in markers:
        if o["m"] == 2 and day_of(int(o["unix"] // 60)) in days:
            m0 = int(o["unix"] // 60)
            ii = [idx[m0 + k] for k in range(0, 13) if (m0 + k) in idx]
            eps.append(dict(minute=m0, detected=bool(ii) and bool((worn[ii] != 2).any())))
    return dict(confusion_truth_rows_off_loose_worn=cm.tolist(),
                off_sens=float((worn[off_nc] == 0).mean()) if off_nc.any() else NAN, n_off=int(off_nc.sum()),
                worn_as_off=float((worn[worn_m] == 0).mean()) if worn_m.any() else NAN,
                worn_as_loose=float((worn[worn_m] == 1).mean()) if worn_m.any() else NAN, n_worn=int(worn_m.sum()),
                loose_eps=eps, loose_detected=sum(e["detected"] for e in eps), n_loose=len(eps),
                charging_off=float((worn[sel & ch] == 0).mean()) if (sel & ch).any() else NAN)


def derive_dev(hg, M, markers, diary, day_of):
    """DEV RULES (docstring). M already restricted to day 1."""
    dev = dict(basis={})
    sleeps = intervals(diary, "SLEEP", "WAKE")
    sleeps1 = [(a, b) for a, b in sleeps if day_of(int(b // 60)) == 1 or day_of(int(a // 60)) == 1]
    u = (M.minute.to_numpy() * 60 + 30).astype(float)
    worn = M.truth_contact.to_numpy() == 2
    inbed = np.array([any(a + 900 <= t < b - 900 for a, b in sleeps1) for t in u]) & worn & ~M.charging.to_numpy().astype(bool)
    a = M.astd.to_numpy()
    ab = a[inbed & np.isfinite(a)]
    if len(ab) >= 120:
        v = math.ceil(np.percentile(ab, 95) / 0.0005) * 0.0005
        dev["STILL_G"] = float(min(0.010, max(0.001, round(v, 6))))
    else:
        dev["STILL_G"] = FROZEN_STILL
    dev["basis"]["STILL_G"] = dict(n_inbed_min=int(len(ab)), p95=pct(ab, 95), frozen_share_le_0002=float((ab <= 0.002).mean()) if len(ab) else NAN)
    dev["ACTIVE_G"] = FROZEN_ACTIVE
    if len(ab) >= 120:
        for cand in (0.005, 0.0075, 0.01, 0.015, 0.02, 0.03):
            if (ab <= cand).mean() >= 0.97:
                dev["ACTIVE_G"] = cand
                break
    walk = M.in_walk.to_numpy() & worn & np.isfinite(a)
    if walk.sum() >= 10:
        dev["WALK_G"] = float(min(0.10, max(0.02, math.floor(np.percentile(a[walk], 10) / 0.005) * 0.005)))
    else:
        dev["WALK_G"] = FROZEN_WALK
    dev["basis"]["WALK_G"] = dict(n_walk_min=int(walk.sum()), p10=pct(a[walk], 10))
    # HDCZA multiplier on night 1
    dev["HDCZA_MULT"] = 15
    best = None
    if sleeps1:
        a0, b0 = sleeps1[0]
        noon = int(b0 // 60)
        # the noon-to-noon window that contains the night: end at the first local 12:00 after the wake
        mod = int(local_mod([noon])[0])
        end = noon + ((720 - mod) % 1440)
        res = {}
        for mult in (10, 15, 20):
            w = hdcza(M, M.truth_contact.to_numpy(), end - 1440, end, mult)
            if w is not None:
                res[mult] = abs(circ_err(int(local_mod([w[0]])[0]), a0)) + abs(circ_err(int(local_mod([w[1]])[0]), b0))
        if res:
            bestv = min(res.values())
            dev["HDCZA_MULT"] = 15 if res.get(15) == bestv else min(k for k, v in res.items() if v == bestv)
        dev["basis"]["HDCZA_MULT"] = {str(k): v for k, v in res.items()}
    # contact grid
    loose_n = sum(1 for o in markers if o["m"] == 2)
    dev["contact"] = dict(FROZEN_CT)
    grid = []
    if loose_n >= 1:
        tc = M.truth_contact.to_numpy(); ex = M.trans_excl.to_numpy()
        for st in (-0.3, -0.5, -0.8):
            for rd in (0.6, 0.7, 0.8):
                for on in (1.0, 1.5):
                    ct = dict(HG_CT_STEP_C=st, HG_CT_RATIO_DROP=rd, HG_CT_OFF_NEAR_C=on)
                    w = contact_only(hg, M, ct, dev["STILL_G"])
                    J = int(((w != 2) & (tc != 2) & ~ex).sum()) - 3 * int(((w != 2) & (tc == 2) & ~ex).sum())
                    grid.append((J, ct == FROZEN_CT, ct))
        bestJ = max(g[0] for g in grid)
        cands = [g for g in grid if g[0] == bestJ]
        dev["contact"] = next((g[2] for g in cands if g[1]), cands[0][2])
        dev["basis"]["contact"] = dict(n_loose_episodes=loose_n, best_J=bestJ,
                                       frozen_J=next(g[0] for g in grid if g[1]))
    # c and rest HR
    rt = room_tests(M, markers, (1,), day_of)
    dev["c_bodyheat"] = float(min(0.4, max(0.0, med([r["c"] for r in rt])))) if rt else 0.15
    dev["basis"]["c_bodyheat"] = dict(n_tests=len(rt), values=[r["c"] for r in rt])
    hrb = M.hr.to_numpy()[inbed & (M.hrq.to_numpy() == 4)]
    dev["rest_hr"] = float(min(100, max(40, np.percentile(hrb, 10)))) if len(hrb) >= 30 else 70.0
    dev["basis"]["rest_hr"] = dict(n=int(len(hrb)))
    return dev


def analyse(hg, W, M, markers, diary, day_of, dev, exam_days, profile, label):
    res = dict(label=label, rows=[])
    R = res["rows"]
    u = (M.minute.to_numpy() * 60 + 30).astype(float)
    days = np.array([day_of(m) for m in M.minute])
    sel = np.isin(days, exam_days)
    sleeps = intervals(diary, "SLEEP", "WAKE")
    awake = ~np.array([in_iv(t, sleeps) for t in u])
    worn_t = M.truth_contact.to_numpy() == 2
    home = M.truth_loc.to_numpy() == 0
    a = M.astd.to_numpy()
    c_dev = dev["c_bodyheat"]
    # ---------------- (e) replays first (contact/home-out outputs are reused)
    twin = dict(rest_hr=70.0, k_person=0.12, core_offset=0.0, c_bodyheat=0.15, t1_night_base=[NAN] * 24)
    Rf, sw_f, prof_f = replay(hg, W, M, profile, twin)
    evf = count_events(Rf, day_of)
    twin_d = dict(twin, rest_hr=dev["rest_hr"], c_bodyheat=c_dev)
    Rd, sw_d, _ = replay(hg, W, M, profile, twin_d, dev=dev)
    evd = count_events(Rd, day_of)
    Re, _, _ = replay(hg, W, M, ELDER_SWAP, twin)
    eve = count_events(Re, day_of)
    alld = sorted(set(int(d) for d in days if d > 0))
    res["replay_frozen"] = per_day_counts(Rf, evf, day_of, alld)
    res["replay_dev"] = per_day_counts(Rd, evd, day_of, alld)
    res["replay_elder_swap"] = per_day_counts(Re, eve, day_of, alld)

    def ctx(minute):
        i = int(np.searchsorted(M.minute.to_numpy(), minute))
        i = min(i, len(M) - 1)
        r = M.iloc[i]
        t = pd.Timestamp(minute * 60, unit="s", tz="UTC").tz_convert(TZ)
        near = [d for d in diary if abs(d["unix"] - minute * 60) < 3600]
        return dict(local=t.strftime("%Y-%m-%d %H:%M"), t1=r.t1, tair=r.tair, hr=r.hr, astd=r.astd,
                    truth_contact=int(r.truth_contact), truth_loc=int(r.truth_loc),
                    diary_within_1h=[(pd.Timestamp(d["unix"], unit="s", tz="UTC").tz_convert(TZ).strftime("%H:%M"), d["code"]) for d in near])
    res["alarm_events_frozen"] = [dict(day=e[0], kind=e[1], why_or_reason=int(e[3]), **ctx(e[2])) for e in evf if e[0] in exam_days or e[0] == 1]
    for nm, cnt in (("frozen", res["replay_frozen"]), ("dev-variant", res["replay_dev"])):
        ex = [cnt[d] for d in exam_days if d in cnt]
        if not ex:
            continue
        e1 = all(c["drink"] <= CRIT["E1_n"] and c["drink_min"] <= CRIT["E1_min"] for c in ex)
        e2 = all(c["cool"] == 0 and c["danger"] == 0 for c in ex)
        nchk = sum(c["check"] for c in ex)
        tag = "E" if nm == "frozen" else "E4"
        R.append(row(tag + "1" if nm == "frozen" else "E4-1", f"{nm}: DRINK per exam day", [(c["drink"], c["drink_min"]) for c in ex],
                     "<= 3 onsets and <= 90 min each day", "PASS" if e1 else "FAIL"))
        R.append(row(tag + "2" if nm == "frozen" else "E4-2", f"{nm}: COOL / DANGER onsets on exam days",
                     [(c["cool"], c["danger"]) for c in ex], "all 0", "PASS" if e2 else "FAIL"))
        R.append(row(tag + "3" if nm == "frozen" else "E4-3", f"{nm}: CHECK starts, exam days total", nchk,
                     "<= 1", "PASS" if nchk <= CRIT["E3"] else "FAIL",
                     detail=dict(reasons=[c["check_reasons"] for c in ex], would_be_family_no_press=[c["family"] for c in ex])))
    # ---------------- (a) sensors
    dons = donnings(M, markers, exam_days, day_of)
    t95 = [d["t95_min"] for d in dons]
    v = med(t95)
    R.append(row("A1", "donning transient, minutes to 95 % of the T1 step", dict(median=v, p90=pct(t95, 90), n=len(t95)),
                 "median in [15, 35] min, n >= 2", "N/A" if len(t95) < 2 else ("CONSISTENT" if CRIT["A1_lo"] <= v <= CRIT["A1_hi"] else "MISMATCH"),
                 "20-30 min (sim median 23, R2 §2.3)", dons))
    t2ok = M.t2.notna().to_numpy()
    troom = (M.tair.to_numpy() - c_dev * M.t1.to_numpy()) / (1 - c_dev)
    base = sel & worn_t & home & (M.min_since_don.to_numpy() >= 30) & (a < 0.02) & ~M.in_hot.to_numpy() & ~M.in_fan.to_numpy() & t2ok & ~M.charging.to_numpy().astype(bool)
    dT = M.t1.to_numpy() - M.t2.to_numpy()
    rng = base & (troom >= CRIT["A2_room"][0]) & (troom <= CRIT["A2_room"][1])
    if t2ok[sel].mean() < 0.5 if sel.any() else True:
        R.append(row("A2", "dT across the foam", "T2 absent", "-", "N/A", "2-5 C in 20-26 C rooms (R2 §2.2)"))
    else:
        mdT = med(dT[rng]); ratio = med(dT[rng] / (M.t1.to_numpy()[rng] - troom[rng]))
        bins = {}
        for lo in range(14, 36, 2):
            b = base & (troom >= lo) & (troom < lo + 2)
            if b.sum() >= 10:
                bins[f"{lo}-{lo + 2}"] = dict(n=int(b.sum()), dT=med(dT[b]))
        R.append(row("A2", "median dT = T1 - T2 in 20-26 C rooms", dict(dT=mdT, n=int(rng.sum()), bins=bins),
                     "[2, 5] C", "N/A" if rng.sum() < 30 else ("CONSISTENT" if CRIT["A2_lo"] <= mdT <= CRIT["A2_hi"] else "MISMATCH"),
                     "2-5 C (sim 24 C: 3.2-4.6, 26 C: 2.7-4.0)"))
        R.append(row("A2r", "median dT / (T1 - T_room)", ratio, "[0.25, 0.50]",
                     "N/A" if rng.sum() < 30 else ("CONSISTENT" if CRIT["A2r_lo"] <= ratio <= CRIT["A2r_hi"] else "MISMATCH"), "0.3-0.45 (R2 §5)"))
        for nm, flag, sign in (("HOT", M.in_hot.to_numpy(), -1), ("FAN", M.in_fan.to_numpy(), +1)):
            f = sel & worn_t & flag & t2ok & (M.min_since_don.to_numpy() >= 30)
            if f.sum() >= 5 and rng.sum() >= 30:
                d = med(dT[f]) - mdT
                R.append(row("A2-" + nm, f"dT in {nm} minutes minus baseline", d, "< 0" if sign < 0 else "> 0",
                             "CONSISTENT" if d * sign > 0 else "MISMATCH", "hot room collapses dT; fan raises it (R2 §2.2, §2.4)"))
            else:
                R.append(row("A2-" + nm, f"dT in {nm} minutes minus baseline", None, "n >= 5 min", "N/A"))
    rt_ex = room_tests(M, markers, exam_days, day_of)
    cs = [r["c"] for r in rt_ex]
    R.append(row("A3", "SHTC3 body-heat coefficient c (room tests)", dict(median=med(cs), values=cs, c_dev=c_dev),
                 "median in [0.05, 0.30]", "N/A" if not cs else ("CONSISTENT" if CRIT["A3_lo"] <= med(cs) <= CRIT["A3_hi"] else "MISMATCH"),
                 "c ~ U(0.05, 0.30) (R2 §6.2)", rt_ex))
    errs = [(r["tair_on"] - c_dev * r["t1_on"]) / (1 - c_dev) - r["t_room_off"] for r in rt_ex]
    R.append(row("A3b", "room temperature predicted with c_dev at exam room tests", errs, "|error| <= 0.5 C every test",
                 "N/A" if not errs else ("PASS" if all(abs(e) <= CRIT["A3b_err"] for e in errs) else "FAIL")))
    valid = (M.hrq.to_numpy() == 4)
    rest = sel & awake & worn_t & home & (M.min_since_don.to_numpy() >= 20) & (a < 0.02) & ~M.charging.to_numpy().astype(bool) & (M.n_ppg.to_numpy() > 0)
    sleepm = sel & ~awake & worn_t
    walkm = sel & worn_t & M.in_walk.to_numpy()
    vr = float(valid[rest].mean()) if rest.any() else NAN
    nppg = M.n_ppg.to_numpy().astype(float)
    okshare = float(M.n_ok.to_numpy()[rest & (M.src.to_numpy() == "1hz")].sum() / max(1.0, nppg[rest & (M.src.to_numpy() == "1hz")].sum()))
    R.append(row("A4", "PPG valid-minute rate at rest", dict(rest=vr, n_rest=int(rest.sum()), ok_second_share_rest=okshare,
                 sleep=float(valid[sleepm].mean()) if sleepm.any() else NAN, walking=float(valid[walkm].mean()) if walkm.any() else NAN,
                 n_walk=int(walkm.sum())), ">= 0.75 at rest", "N/A" if rest.sum() < 60 else ("CONSISTENT" if vr >= CRIT["A4_rest"] else "MISMATCH"),
                 "rest 75-90 % valid; walking ~0 % (sim quality 'motion')"))
    pulses = [d for d in diary if d["code"] == "PULSE" and d["value"] and day_of(int(d["unix"] // 60)) in exam_days]
    perr = []
    for p in pulses:
        m0 = int(p["unix"] // 60)
        w = M[(M.minute >= m0 - 2) & (M.minute <= m0 + 2) & (M.hrq == 4)]
        if len(w):
            perr.append(float(w.hr.median()) - float(p["value"]))
    mae = float(np.mean(np.abs(perr))) if perr else NAN
    R.append(row("A4b", "band HR vs manual 60-s pulse", dict(mae=mae, errors=perr, n_pulses=len(pulses)), "MAE <= 5 bpm, n >= 3",
                 "N/A" if len(perr) < 3 else ("CONSISTENT" if mae <= CRIT["A4b_mae"] else "MISMATCH"), "sigma 3 bpm at rest (R2 §6.3)"))
    sig = []
    idx = {m: i for i, m in enumerate(M.minute)}
    for o in markers:
        if o["m"] != 2:
            continue
        m0 = int(o["unix"] // 60)
        if day_of(m0) not in exam_days:
            continue
        nxt = next((x for x in markers if x["unix"] > o["unix"] and x["m"] in (1, 3, 4)), None)
        m1 = int(nxt["unix"] // 60) if nxt else m0 + 10
        bef = [idx.get(m0 - k) for k in range(1, 6)]
        lo = [idx.get(m1 - k) for k in range(1, 6)]
        if any(s is None for s in bef + lo):
            continue
        B, L = M.iloc[bef], M.iloc[lo]
        on = [idx.get(m0 + k) for k in (-1, 0, 1)]
        zz = [z for s in on if s is not None for z in M.zang.iat[s] if z == z]
        sig.append(dict(minute=m0, dT1=float(L.t1.mean() - B.t1.mean()),
                        d_dT=float((L.t1 - L.t2).mean() - (B.t1 - B.t2).mean()) if B.t2.notna().any() else NAN,
                        pi_ratio=float(L.pi.mean() / B.pi.mean()) if B.pi.mean() > 0 else NAN,
                        z_range_onset=float(max(zz) - min(zz)) if zz else NAN))
    md1, mpi = med([s["dT1"] for s in sig]), med([s["pi_ratio"] for s in sig])
    R.append(row("A5", "loose-band signature", dict(median_dT1=md1, median_d_dT=med([s["d_dT"] for s in sig]), median_PI_ratio=mpi, n=len(sig)),
                 "median dT1 < 0 and PI ratio < 1", "N/A" if not sig else ("CONSISTENT" if md1 < 0 and mpi < 1 else "MISMATCH"),
                 "T1 -0.35 C, dT -0.24 C, PI x0.42 (sim); -0.5..-2 C step (R2 §5)", sig))
    # ---------------- (b) contact
    for nm, w in (("frozen", Rf.worn.to_numpy()), ("dev", Rd.worn.to_numpy())):
        s = contact_scores(M, w, sel, markers, day_of, exam_days)
        p = "B" if nm == "frozen" else "B-dev"
        R.append(row(p + "1", f"{nm}: off minutes detected off (not charging)", s["off_sens"], ">= 0.90",
                     "N/A" if s["n_off"] < 10 else ("PASS" if s["off_sens"] >= CRIT["B1"] else "FAIL"), detail=s["confusion_truth_rows_off_loose_worn"]))
        R.append(row(p + "2", f"{nm}: worn minutes called off", s["worn_as_off"], "<= 0.01",
                     "N/A" if s["n_worn"] < 60 else ("PASS" if s["worn_as_off"] <= CRIT["B2"] else "FAIL")))
        fr = s["loose_detected"] / s["n_loose"] if s["n_loose"] else NAN
        R.append(row(p + "3", f"{nm}: LOOSE episodes detected", f"{s['loose_detected']}/{s['n_loose']}", ">= 50 %",
                     "N/A" if not s["n_loose"] else ("PASS" if fr >= CRIT["B3"] else "FAIL"), detail=s["loose_eps"]))
        R.append(row(p + "4", f"{nm}: worn minutes called loose", s["worn_as_loose"], "<= 0.02",
                     "N/A" if s["n_worn"] < 60 else ("PASS" if s["worn_as_loose"] <= CRIT["B4"] else "FAIL")))
        R.append(row(p + "5", f"{nm}: charging minutes called off", s["charging_off"], "= 1.0",
                     "N/A" if s["charging_off"] != s["charging_off"] else ("PASS" if s["charging_off"] == 1.0 else "FAIL")))
    # ---------------- (c) home / out
    ho = Rf.home_out.to_numpy()
    tl = M.truth_loc.to_numpy()
    trips, cur = [], None
    for i in range(len(M)):
        if tl[i] == 2 and cur is None: cur = i
        if tl[i] != 2 and cur is not None: trips.append((cur, i)); cur = None
    if cur is not None: trips.append((cur, len(M)))
    trips = [(i, j) for i, j in trips if sel[i] and (M.minute.iat[j - 1] - M.minute.iat[i]) >= 15]
    hit = [bool((ho[i:j] >= 1).any()) for i, j in trips]
    R.append(row("C1", "OUT trips >= 15 min reaching TRANSIT/OUT", f"{sum(hit)}/{len(hit)}", ">= 50 %",
                 "N/A" if not hit else ("PASS" if sum(hit) / len(hit) >= CRIT["C1"] else "FAIL"), "DESIGN thresholds, BLE unknown"))
    hm = sel & worn_t & (tl == 0)
    fo = float((ho[hm] == 2).mean()) if hm.any() else NAN
    R.append(row("C2", "home minutes called OUT", fo, "<= 0.05", "N/A" if hm.sum() < 60 else ("PASS" if fo <= CRIT["C2"] else "FAIL")))
    agr = sel & worn_t
    R.append(row("C3", "per-minute agreement HOME vs not-HOME", float(((ho[agr] == 0) == (tl[agr] == 0)).mean()) if agr.any() else NAN, "reported", "INFO"))
    # ---------------- (d) sleep and routine
    for nm, sw in (("frozen", sw_f),):
        for (a0, b0) in sleeps:
            dn = day_of(int(b0 // 60))
            if dn not in exam_days:
                continue
            wake_m = int(b0 // 60)
            noon_after = wake_m + ((720 - int(local_mod([wake_m])[0])) % 1440)
            snap = next((s for s in sw if noon_after <= s["minute"] <= noon_after + 5), None)
            if snap is None:
                R.append(row("D1", f"{nm} HDCZA night ending day {dn}", None, "window computed", "FAIL",
                             detail="no HDCZA window at that noon (< 200 worn blocks or no inactive block)"))
                continue
            eo, ew = circ_err(snap["on"], a0), circ_err(snap["off"], b0)
            ok = abs(eo) <= CRIT["D1_err"] and abs(ew) <= CRIT["D1_err"]
            R.append(row("D1", f"{nm} HDCZA sleep window, night ending day {dn}", dict(onset_err_min=eo, wake_err_min=ew, thr_cdeg=snap["thr"]),
                         "|errors| <= 60 min", "PASS" if ok else "FAIL", "van Hees 2018 MAE 40/30 min vs diary"))
    for (a0, b0) in sleeps:
        dn = day_of(int(b0 // 60))
        if dn not in exam_days:
            continue
        wake_m = int(b0 // 60)
        end = wake_m + ((720 - int(local_mod([wake_m])[0])) % 1440)
        w = hdcza(M, Rd.worn.to_numpy(), end - 1440, end, dev["HDCZA_MULT"])
        if w is None:
            R.append(row("D2", f"dev HDCZA (mult {dev['HDCZA_MULT']}), night ending day {dn}", None, "window", "FAIL", detail="too few worn blocks"))
            continue
        eo, ew = circ_err(int(local_mod([w[0]])[0]), a0), circ_err(int(local_mod([w[1]])[0]), b0)
        R.append(row("D2", f"dev HDCZA (mult {dev['HDCZA_MULT']}), night ending day {dn}", dict(onset_err_min=eo, wake_err_min=ew),
                     "|errors| <= 60 min", "PASS" if abs(eo) <= 60 and abs(ew) <= 60 else "FAIL"))
    inbed = np.array([any(x + 900 <= t < y - 900 for x, y in sleeps) for t in u]) & sel & worn_t & np.isfinite(a)
    sd_ = float((a[inbed] <= dev["STILL_G"]).mean()) if inbed.any() else NAN
    R.append(row("D3", "in-bed minutes still at STILL_G_dev", dict(share=sd_, still_g_dev=dev["STILL_G"], share_frozen_0002=float((a[inbed] <= FROZEN_STILL).mean()) if inbed.any() else NAN,
                 n=int(inbed.sum())), ">= 0.90", "N/A" if inbed.sum() < 120 else ("PASS" if sd_ >= CRIT["D3"] else "FAIL"),
                 "asleep a_std median 1.6 mg, 86 % <= 2 mg (sim v3)"))
    aw = sel & awake & worn_t & np.isfinite(a)
    runs, r_ = 0, 0
    for s_ in (a <= dev["STILL_G"]) & aw:
        r_ = r_ + 1 if s_ else 0
        if r_ == 10: runs += 1
    R.append(row("D3b", "awake still runs >= 10 min per worn awake hour", runs / max(aw.sum() / 60, 1e-9) if aw.any() else NAN,
                 "reported (verification §4e: 0.017-0.08/h)", "INFO"))
    # routine profile and IS / IV / RA (all days, hourly active minutes from a_std > ACTIVE)
    act = (a > FROZEN_ACTIVE).astype(float)
    hrs = pd.DataFrame(dict(h=(M.minute.to_numpy() // 60), act=act, w=worn_t.astype(float)))
    hh = hrs[hrs.w > 0].groupby("h").act.mean()
    isiv = {}
    if len(hh) >= 48:
        x = hh.to_numpy(); hod = (hh.index.to_numpy() * 60 // 60)
        hod = np.asarray(local_mod(hh.index.to_numpy() * 60) // 60)
        prof = pd.Series(x).groupby(hod).mean()
        n, p_ = len(x), len(prof)
        isiv["IS"] = float(n * ((prof - x.mean()) ** 2).sum() / (p_ * ((x - x.mean()) ** 2).sum())) if x.var() > 0 else NAN
        isiv["IV"] = float(n * (np.diff(x) ** 2).sum() / ((n - 1) * ((x - x.mean()) ** 2).sum())) if x.var() > 0 else NAN
        roll = pd.Series(prof.reindex(range(24)).fillna(0).to_numpy())
        ext = pd.concat([roll, roll])
        m10 = max(ext.iloc[i:i + 10].mean() for i in range(24)); l5 = min(ext.iloc[i:i + 5].mean() for i in range(24))
        isiv["RA"] = float((m10 - l5) / (m10 + l5)) if (m10 + l5) > 0 else NAN
    R.append(row("D4", "routine profile after the recording", dict(days_learned=prof_f["days_learned"],
                 hours_with_3_days=sum(1 for x in prof_f["am"] if x["n"] >= 3), active_min_mean_by_hour=[round(x["mean"], 1) for x in prof_f["am"]],
                 max_quiet_by_hour=prof_f["maxq"], **isiv), "descriptive (3 days < 5 recommended, Posner 2021)", "INFO"))
    # ---------------- (f) oral vs displayed range
    orals = [o for o in markers if o["m"] == 7 and o["v"] > 0]
    sess = []
    for o in orals:
        if sess and o["unix"] - sess[-1][-1]["unix"] <= 600:
            sess[-1].append(o)
        else:
            sess.append([o])
    rep = [abs(s[0]["v"] - s[1]["v"]) / 100 for s in sess if len(s) >= 2]
    rf = []
    Rm = Rf.set_index("minute")
    for s in sess:
        m0 = int(s[0]["unix"] // 60)
        if day_of(m0) not in exam_days:
            continue
        val = np.mean([x["v"] for x in s]) / 100
        for k in (0, -1, 1):
            if (m0 + k) in Rm.index and Rm.at[m0 + k, "core_valid"]:
                rr = Rm.loc[m0 + k]
                rf.append(dict(minute=m0, oral=val, core_now=float(rr.core_now), half=float(rr.half),
                               inside=bool(abs(val - rr.core_now) <= rr.half)))
                break
    k_in = sum(x["inside"] for x in rf)
    R.append(row("F1", "oral session inside the displayed range", dict(inside=k_in, n=len(rf), wilson95=wilson(k_in, len(rf)),
                 bias_oral_minus_core=float(np.mean([x["oral"] - x["core_now"] for x in rf])) if rf else NAN,
                 mae=float(np.mean([abs(x["oral"] - x["core_now"]) for x in rf])) if rf else NAN,
                 thermometer_repeat_mean_abs_diff=float(np.mean(rep)) if rep else NAN, sessions=rf),
                 ">= 80 %, n >= 4", "N/A" if len(rf) < CRIT["F1_n"] else ("PASS" if k_in / len(rf) >= CRIT["F1"] else "FAIL"),
                 "range +-0.58 C (REAL HTT width); oral is not core"))
    return res


def firmware_checks(rec, M, wear_start_min, wear_end_min):
    R = []
    boots = [e for e in rec["events"] if e["kind"] == "BOOT"]
    for b in boots:   # boot start in unix from that boot's TIME sync (None = never synced)
        s = rec["syncs"].get(int(b.get("boot", -1)))
        b["unix0"] = (s[1] - s[0] / 1000.0) if s else None
    wd = [b for b in boots if b.get("reset") == "WATCHDOG"]
    R.append(row("G1", "watchdog resets (whole recording)", len(wd), "= 0", "PASS" if not wd else "FAIL",
                 detail=[dict(boot=b.get("boot"), reset=b.get("reset"), unix0=b["unix0"]) for b in boots]))
    inwin = [b for b in boots if b["unix0"] is None or wear_start_min * 60 <= b["unix0"] < wear_end_min * 60]
    bad = [b for b in inwin if b.get("reset") in ("POWER-ON/BROWN-OUT", "LOCKUP", "RESET-PIN")]
    R.append(row("G1b", "unexplained resets inside the wear period (power-on/brown-out, lockup, pin)", len(bad), "= 0 (each one needs a why)",
                 "PASS" if not bad else "FAIL", detail=[dict(boot=b.get("boot"), reset=b.get("reset"), synced=b["unix0"] is not None) for b in inwin]))
    R.append(row("G2", "CRC errors", rec["crc_errors"], "= 0", "PASS" if rec["crc_errors"] == 0 else "FAIL"))
    span = M[(M.minute >= wear_start_min) & (M.minute < wear_end_min)]
    n_wall = max(1, wear_end_min - wear_start_min)
    cov = len(span) / n_wall
    gaps = []
    mm = span.minute.to_numpy()
    for i in np.nonzero(np.diff(mm) > 1)[0]:
        gaps.append(dict(after=pd.Timestamp(int(mm[i]) * 60, unit="s", tz="UTC").tz_convert(TZ).strftime("%m-%d %H:%M"), missing_min=int(mm[i + 1] - mm[i] - 1)))
    R.append(row("G3", "minute coverage of the wear period", dict(coverage=cov, from_1hz=float((span.src == "1hz").mean()) if len(span) else NAN, gaps=gaps[:30]),
                 ">= 0.99", "PASS" if cov >= CRIT["G3"] else "FAIL"))
    low = [e for e in rec["events"] if e["kind"] == "LOWBAT" and "ON" in e["text"]]
    # battery: on-battery segments from minute vbat
    vb = M[["minute", "vbat", "charging"]].dropna()
    segs, cur = [], []
    for r in vb.itertuples():
        if r.charging or (cur and r.minute - cur[-1][0] > 5):
            if len(cur) >= 120: segs.append(cur)
            cur = []
        if not r.charging:
            cur.append((r.minute, r.vbat))
    if len(cur) >= 120: segs.append(cur)
    slopes = []
    for s in segs:
        t = np.array([x[0] for x in s]) / 60.0; v = np.array([x[1] for x in s])
        slopes.append(float(np.polyfit(t, v, 1)[0]))
    sl = med(slopes)
    longest = max((len(s) / 60 for s in segs), default=0.0)
    R.append(row("G4", "battery", dict(lowbat_events=len(low), slope_v_per_h=sl, n_segments=len(segs),
                 longest_on_battery_h=longest, hours_4p10_to_3p50_EXTRAPOLATED=(0.60 / -sl) if sl == sl and sl < 0 else NAN),
                 "no LOWBAT event", "PASS" if not low else "FAIL", "estimate 2.5-3.5 days (README, not measured)"))
    df = rec["df"]
    allsec = df[~df.is_minute]
    un = allsec.unix_s.isna().mean() if len(allsec) else (df.unix_s.isna().mean() if len(df) else NAN)
    R.append(row("G5", "unanchored records (boot never time-synced)", float(un), "<= 0.01", "PASS" if un <= CRIT["G5"] else "FAIL"))
    ws = allsec[(allsec.charging == 0) & allsec.unix_s.notna()]
    av = {c: float(ws[c].notna().mean()) if len(ws) else NAN for c in ("T1", "T2", "T_air_meas", "RH_meas", "a_std_g", "hr_quality")}
    req = [av[c] for c in ("T1", "T_air_meas", "RH_meas", "a_std_g")]
    R.append(row("G6", "sensor availability (not-charging seconds)", av, "T1/T_air/RH/a_std >= 0.99",
                 "N/A" if not len(ws) else ("PASS" if min(req) >= CRIT["G6"] else "FAIL")))
    lost = [e["text"] for e in rec["events"] if e["kind"] == "SENSOR"]
    R.append(row("G7", "sensor lost/back events", lost[:20], "reported", "INFO"))
    und = [e["text"] for e in rec["events"] if e["kind"] == "UNDUMPED"]
    R.append(row("G8", "1 Hz hours deleted before a dump", len(und), "reported", "INFO"))
    return R


# ------------------------------------------------------------------ main
def make_day_of(dev_end_min):
    def day_of(minute):
        d = minute - dev_end_min
        if d < 0: return 1
        if d < 1440: return 2
        if d < 2880: return 3
        return 0
    return day_of


def first_noon_after(unix, min_hours=12):
    t = pd.Timestamp(unix + min_hours * 3600, unit="s", tz="UTC").tz_convert(TZ)
    n = t.normalize() + pd.Timedelta(hours=12)
    if n < t:
        n += pd.Timedelta(days=1)
    return int(n.timestamp() // 60)


def to_jsonable(o):
    if isinstance(o, dict): return {str(k): to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [to_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o); return None if f != f else round(f, 5)
    if isinstance(o, (np.bool_,)): return bool(o)
    return o


def write_report(path, out):
    L = [f"# Wear exam report — {out['label']}", "", f"{EXAM_VERSION}. Generated {out['finished_utc']}. "
         f"Main wearer: age {WEARER['age']:.0f} (REAL, n = 1, not in heat; no claim about older adults or core accuracy).", ""]
    L.append(f"Days: DEV ends {out['windows']['dev_end_local']}; exam days 2-3 end {out['windows']['exam_end_local']}.")
    L.append("")
    L.append("| id | what | value | criterion | verdict |")
    L.append("|---|---|---|---|---|")
    for r in out["main"]["rows"] + out["firmware"]:
        v = json.dumps(to_jsonable(r["value"]), ensure_ascii=False)
        v = v if len(v) < 160 else v[:157] + "..."
        L.append(f"| {r['id']} | {r['what']} | {v} | {r['criterion']} | **{r['verdict']}** |")
    L.append("")
    L.append("Every FAIL / MISMATCH needs a written why (fill `why` in the DONE file's copy in reports/, never edit this exam).")
    L.append("")
    L.append("## Frozen guardian, per day (day 1 = DEV, days 2-3 = EXAM)")
    L.append("")
    L.append("| replay | day | DRINK | DRINK min | COOL | DANGER | CHECK | reasons | family | nudges |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for nm in ("replay_frozen", "replay_dev", "replay_elder_swap"):
        for d, c in out["main"][nm].items():
            L.append(f"| {nm[7:]} | {d} | {c['drink']} | {c['drink_min']} | {c['cool']} | {c['danger']} | {c['check']} | {c['check_reasons']} | {c['family']} | {c['nudge']} |")
    if out.get("relatives"):
        L.append("")
        L.append("## Older relative sessions (descriptive; n = 1; not in heat; not used for tuning)")
        for rr in out["relatives"]:
            L.append(f"- age {rr['age']}: {json.dumps(to_jsonable(rr['summary']), ensure_ascii=False)}")
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="pre-registered wear exam (see docstring)")
    ap.add_argument("--data", help="folder with every capture + diary.csv of the wear test")
    ap.add_argument("--phase", choices=["exam", "dev", "inspect"], default="exam")
    ap.add_argument("--synthetic", action="store_true", help="self-test on SYNTHETIC logs (no git checks)")
    ap.add_argument("--done-out", help="--synthetic only: where to write the DONE json (not inside wear/)")
    a = ap.parse_args(argv)
    if not a.data:
        die("--data is required (the folder with the wear-test captures)")
    if not os.path.isdir(a.data):
        die("--data %s is not a folder" % a.data)
    label = "SYNTHETIC (code self-test, not evidence)" if a.synthetic else "REAL wear test, n = 1"
    done_path = DONE
    if a.synthetic:
        if a.phase == "exam":
            if not a.done_out:
                die("--synthetic exam needs --done-out")
            if os.path.abspath(a.done_out).startswith(WEAR + os.sep):
                die("--done-out must not be inside wear/ (that place is reserved for the real exam)")
            done_path = os.path.abspath(a.done_out)
    elif a.phase == "exam":
        if os.path.exists(DONE):
            die("the wear exam has already run (%s exists)" % DONE)
        rc, _ = git("rev-parse", "-q", "--verify", "refs/tags/" + WEAR_TAG)
        if rc != 0:
            die("tag %s does not exist: freeze the protocol and this exam BEFORE scoring" % WEAR_TAG)
        rc, blob = git("show", "%s:tests/wear_exam.py" % WEAR_TAG)
        if rc != 0 or blob != open(os.path.abspath(__file__), "rb").read():
            die("tests/wear_exam.py differs from its copy in tag %s" % WEAR_TAG)
    if a.phase == "exam" and os.path.exists(done_path):
        die("%s exists: the exam runs once" % done_path)
    pl = load_parse_log()
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    rec = load_recording(a.data, pl)
    markers_all = collect_markers(rec)
    diary_all, unmatched, spare = match_diary(rec["diary"], markers_all)
    for d in diary_all:
        m = FALLBACK.get(d["code"])
        if m and not any(o["m"] == m and abs(o["unix"] - d["unix"]) <= MATCH_S for o in markers_all):
            markers_all.append(dict(unix=d["unix"], m=m, v=0, src="diary"))
    markers_all.sort(key=lambda o: o["unix"])
    rels = relative_windows(diary_all, markers_all)
    M_all = build_minutes(rec)
    if not len(M_all):
        die("no anchored minutes (was the clock ever set with `time`?)")
    in_rel = lambda unix: any(r["start"] <= unix < r["end"] for r in rels)
    markers = [o for o in markers_all if not in_rel(o["unix"])]
    diary = [d for d in diary_all if not in_rel(d["unix"])]
    dons = [o for o in markers if o["m"] == 1]
    if not dons:
        die("no `donned` marker: cannot place day 1")
    dev_end = first_noon_after(dons[0]["unix"])
    day_of = make_day_of(dev_end)
    M = M_all[[not in_rel(m * 60 + 30) for m in M_all.minute]].reset_index(drop=True)
    M = label_minutes(M, markers, diary)
    wstart, wend = int(dons[0]["unix"] // 60), min(dev_end + 2880, int(M.minute.max()) + 1)
    windows = dict(dev_end_local=str(pd.Timestamp(dev_end * 60, unit="s", tz="UTC").tz_convert(TZ)),
                   exam_end_local=str(pd.Timestamp((dev_end + 2880) * 60, unit="s", tz="UTC").tz_convert(TZ)),
                   first_donned_local=str(pd.Timestamp(dons[0]["unix"], unit="s", tz="UTC").tz_convert(TZ)))
    integ = dict(minutes=len(M), from_1hz=float((M.src == "1hz").mean()), boots=sorted(set(int(b) for b in M.boot)),
                 markers_per_day={d: {str(m): sum(1 for o in markers if o["m"] == m and day_of(int(o["unix"] // 60)) == d) for m in range(1, 10)} for d in (1, 2, 3)},
                 diary_entries=len(diary), diary_unmatched_press_codes=unmatched, presses_without_diary=spare,
                 relative_sessions=len(rels), crc_errors=rec["crc_errors"])
    if a.phase == "inspect":
        print(json.dumps(to_jsonable(dict(windows=windows, integrity=integ)), indent=1))
        return 0
    if a.phase == "exam":
        # data are loaded and the day windows placed; nothing has been scored yet. From here on the exam is spent.
        head = git("rev-parse", "HEAD")[1].decode().strip()
        os.makedirs(os.path.dirname(done_path), exist_ok=True)
        with open(done_path, "w") as f:
            json.dump(dict(exam=EXAM_VERSION, label=label, started_utc=started, git_head=head, input_sha256=rec["sha"],
                           parse_log_sha256=sha256_file(os.path.join(REPO, "fw/tools/parse_log.py")),
                           wear_exam_sha256=sha256_file(os.path.abspath(__file__)), windows=windows, integrity=to_jsonable(integ),
                           status="STARTED"), f, indent=1)
    with tempfile.TemporaryDirectory() as tmp:
        hg, W = load_frozen_guardian(tmp)
        M1 = M[[day_of(m) == 1 for m in M.minute]].reset_index(drop=True)
        dev = derive_dev(hg, M1, [o for o in markers if day_of(int(o["unix"] // 60)) == 1],
                         [d for d in diary if day_of(int(d["unix"] // 60)) == 1], day_of)
        dev_j = to_jsonable(dict(exam=EXAM_VERSION, label=label, windows=windows, thresholds={k: v for k, v in dev.items() if k != "basis"},
                                 basis=dev["basis"]))
        if a.phase == "dev":
            out = DEV_FILE if not a.synthetic else os.path.join(os.path.dirname(os.path.abspath(a.done_out or os.path.join(a.data, "x"))), "DEV_THRESHOLDS_synthetic.json")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w") as f:
                json.dump(dev_j, f, indent=1)
            print(json.dumps(dev_j, indent=1)); print("wrote", out)
            return 0
        if not a.synthetic and os.path.exists(DEV_FILE):
            prev = json.load(open(DEV_FILE))
            if prev.get("thresholds") != dev_j["thresholds"]:
                d = json.load(open(done_path)); d["status"] = "ABORTED: DEV_THRESHOLDS.json differs from the day-1 derivation"
                json.dump(d, open(done_path, "w"), indent=1)
                die("wear/DEV_THRESHOLDS.json differs from what day 1 gives (hand-edited?). Exam spent; see DONE file.")
        main_res = analyse(hg, W, M, markers, diary, day_of, dev, (2, 3), WEARER, label)
        fw = firmware_checks(rec, M_all, wstart, wend)
        relres = []
        for r in rels:
            Mr = M_all[(M_all.minute * 60 + 30 >= r["start"]) & (M_all.minute * 60 + 30 < r["end"])].reset_index(drop=True)
            mk = [o for o in markers_all if r["start"] <= o["unix"] < r["end"]]
            dr = [d for d in diary_all if r["start"] <= d["unix"] < r["end"]]
            if len(Mr) < 30 or not mk:
                relres.append(dict(age=r["age"], summary="too short / no markers")); continue
            Mr = label_minutes(Mr, mk, dr)
            one = lambda m: 2
            prof = dict(age=float(r["age"]), sex_m=1.0 if "male" in r["note"].lower() and "female" not in r["note"].lower() else 0.0, bmi=26.0, med_flags=0)
            rr = analyse(hg, W, Mr, mk, dr, one, dict(dev, c_bodyheat=dev["c_bodyheat"]), (2,), prof, "RELATIVE, n = 1, descriptive")
            keep = {x["id"]: dict(value=x["value"], verdict=x["verdict"]) for x in rr["rows"] if x["id"] in ("A1", "A2", "A2r", "A4", "A5", "B1", "B3", "E1", "E2", "E3")}
            relres.append(dict(age=r["age"], hours=len(Mr) / 60, summary=dict(rows=keep, alarms=rr["replay_frozen"])))
    out = dict(exam=EXAM_VERSION, label=label, started_utc=started, finished_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
               git_head=git("rev-parse", "HEAD")[1].decode().strip(), input_sha256=rec["sha"], windows=windows, integrity=integ,
               dev_thresholds=dev_j, main=main_res, firmware=fw, relatives=relres, criteria=CRIT, status="DONE")
    out = to_jsonable(out)
    with open(done_path, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    rp = REPORT if not a.synthetic else os.path.splitext(done_path)[0] + "_REPORT.md"
    write_report(rp, out)
    nv = {}
    for r in out["main"]["rows"] + out["firmware"]:
        nv[r["verdict"]] = nv.get(r["verdict"], 0) + 1
    print(f"{label}: verdicts {nv}; wrote {done_path} and {rp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
