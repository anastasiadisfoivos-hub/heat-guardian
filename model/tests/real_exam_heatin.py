#!/usr/bin/env python3
"""Heat Guardian - PRE-REGISTERED REAL older-adult exam #2: HeatIN Montreal 2025 (wrist watch at home, all summer). M18.

Written Nov 12 2026 by agent REAL-EXAM, BEFORE any sealed watch row was read. The input mapping, metrics and pass lines below
are fixed now; the four numeric mapping anchors were set on the DEV watches only (stated with each). A FAIL is a finding with a
written why, never a reason to change this file. RUN ONCE, by the manager, at the freeze tag M19.5 names (freeze-5).

  exam (ONCE)  : python3 -I tests/real_exam_heatin.py --tag <freeze-tag>
  DEV dry run  : python3 -I tests/real_exam_heatin.py --tag <freeze-tag> --dry-run-dev [--max-watches N]
                 (DEV watches only; never reads or writes the DONE file)

SOURCE  /home/claude/hgdata/raw/older_heatin_montreal/ (Borealis doi:10.5683/SP3/DYSESG, depositor L. Souilla, Universite de
  Montreal; protocol OSF 10.17605/OSF.IO/ZN8QE; CC BY 4.0, cite the dataset). Bangle.js 2 watches worn by tenants of Montreal
  social housing (protocol: age >= 50; ages NOT in the deposit -> never call them "65+"), summer 2025.
  summer_2025_smartwatch_data.SLIM.csv.gz: one row per watch-minute: unix, tz (s), charging, steps, hr, hr_conf (0-100),
  baro_temp (BMP280 inside the watch case, "near-wrist temperature"), acc_min/max/avg (|a| in g), macID.
  summer_2025_indoor_environment.SLIM.csv.gz: ~1/min per ROOM NODE (SHT85 / SHT41 air T and RH), node macIDs.
SPLIT (model/sealed_real_older.json, M18, seed 20261115): SEALED = heatin_sealed_watch_macIDs (17 watches), DEV = the other 18.
  The watch file interleaves watches, so it is streamed line by line: the macID is cut from the line's end
  (line.rsplit(",", 3)) and a line whose macID is not in the selected set is DISCARDED BEFORE any other field is split
  or converted. --dry-run-dev selects the DEV set only. Nothing is copied to disk.

THE WATCH-TO-ROOM KEY PROBLEM (R5 2.1 problem 3) - PRE-REGISTERED HANDLING
  The deposit has no key between watch macIDs and room-node macIDs. Tried on DEV only: correlate each watch's hourly
  baro_temp while on the charger (a watch on a charger sits in the room) with every node's hourly air T. Result: the best
  node's r was < 0.80 for 12 of 18 DEV watches, and 5 of the other 6 had a runner-up node within 0.10 in r (rooms share the
  Montreal weather): at most 1 of 18 matched unambiguously. No reliable match exists, so rooms are NOT matched:
  VARIANT A (PRIMARY, verdicts): room air T/RH MISSING every minute. The air-dependent paths (PSU env line, WHO, M12 heat
    context for the v1.2 DRINK ceiling, the routine heat coupling, any room-armed path such as M19 Marble) cannot fire; the
    exam scores the body/motion/contact/routine paths.
  VARIANT B (SECONDARY, reported with the same lines, no verdict): air T/RH = the MEDIAN over all HeatIN room nodes in that
    minute (a "typical apartment in these buildings" proxy, NOT her room), held up to 10 min. It shows what the air-armed
    paths do on real hot Montreal days; its alarm counts are not her room's.

INPUT MAPPING (watch minute -> band minute; every choice is a caveat)
  Rows with unix < 1.7e9 (clock never set, ~1970) are dropped; duplicate minutes keep the first row. Local minute of day
    = (unix + tz) // 60 mod 1440 (tz missing -> -14400). Local day = (unix + tz) // 86400.
  Gaps of 1..120 missing minutes are replayed as off-wrist minutes (charging analog, no sensor values) so the guardian's
    clocks run; longer gaps are jumped (the band is treated as powered down; state kept) and not counted as exposure.
  charging -> the contact check's charging input (worn = 0, as on the band).
  hr      = hr when 30..220 bpm; hrq = 4 (good) when hr_conf >= 70, else 1 (present, low quality); no hr -> hrq 0.
            Anchor 70 set on DEV: on the charger (no skin) the watch still reports an "HR" 93 % of minutes; hr_conf >= 70
            accepts 6.3 % of those and 42 % of off-charger minutes.
  t1      = baro_temp: a sensor inside the watch case, a relative of the band's REFERENCE sensor, not skin. t2 missing ->
            heat flux INVALID every minute.
  a_std   = piecewise-linear map of the per-minute |a| range r = acc_max - acc_min (g), anchors set on DEV watches:
            r <= 0.355 (median r on the charger = still)          -> 0 .. 0.002 g (band STILL floor)
            0.355 < r <= 0.714 (99th pct on the charger)          -> 0.002 .. 0.02 g (band ACTIVE threshold)
            0.714 < r <= 1.07 (median r in minutes with steps > 0) -> 0.02 .. 0.05 g (band WALK)
            r > 1.07 -> 0.05 + 0.05 (r - 1.07);  steps >= 10 in the minute -> at least 0.05 g;  missing -> 0.
  apeak   = acc_max (g) (impact rule >= 2 g); z-angle missing (HDCZA sleep detection cannot learn: the routine uses the
            default sleep window 22:00-08:00 and default wake 08:00 all summer).
  PPG DC  = 0 (unknown: the deposit has no PPG DC; the "no skin" PPG rule cannot fire), PI missing, flat 0, BLE unknown,
            no forecast (heat_day 0), vbat 4.0 V, no button presses (every CHECK runs to its family step: family counts are
            "a CHECK nobody answered", an upper bound).
  profile = trace_io.default_profile() of the tag (age 75, female, BMI 26, no medication flags; real ages unknown);
            twin = trace_io.default_twin() (rest_hr 70). Every watch starts a fresh guardian at its first row.

PRE-REGISTERED METRICS (per watch, then median and mean over watches with >= 7 wearer-days)
  wearer-day = local day with >= 600 minutes in which the guardian's own contact output is worn != 0.
  Rates count events on wearer-days only (events on other days are reported separately).
  Episode/onset = >= 2 consecutive minutes, re-entry < 10 min after the previous episode's end merged (htt_eval_lib).
  E1 DRINK (level >= 1) onsets per wearer-day and DRINK minutes per wearer-day.
  E2 COOL (level >= 2) onsets per wearer-week.  E3 DANGER (level >= 3) onsets per wearer-month (30.4 days).
  E4 CHECK starts (check_reason 0 -> non-zero) per wearer-week, all causes and by cause bit: 1 thermal Danger,
     2 behaviour (COOL + still), 4 routine quiet run, 8 NO-WAKE, 16 impact + stillness. Family alerts (rising edges) per
     wearer-month.
  E5 path tallies at each tier onset: the guardian's `why` bits (1 env-above, 2 env-dose, 4 behaviour, 8 v1.2 Danger z,
     16 f20 >= DRINK line, 32 NN logit, 64 uncertainty lowering, 128 WHO) and, for DRINK, approximate labels
     (v1.2 absolute: aux v12_f20 >= HG_T_DRINK - HG_M_TOTAL_CAP; env: env_run or env_dose >= 10; else "other").
  E6 routine/no-wake: NO-WAKE CHECKs per wearer-week, share of wearer-days with a NO-WAKE CHECK, quiet-run CHECKs per week.
  E7 contact self-check: among off-charger minutes, share called worn / loose / off; loose episodes per wearer-day;
     share of worn-called minutes inside a >= 60-min run with no HR value ("suspect worn": likely off-wrist on a table).
  Every alarm here is UNCONFIRMED, not false: there is no core reference (oral `temp` is a raw probe value, R5).
PRE-REGISTERED PASS LINES (VARIANT A, median watch; DECISIONS M1.4 / M9.2 / M15 budgets)
  H1 DRINK <= 3 onsets per wearer-day AND <= 90 DRINK minutes per wearer-day        (M9.2)
  H2 COOL <= 1 onset per wearer-week                                               (M1.4)
  H3 DANGER <= 1 onset per wearer-month                                            (M15, read on the median wearer)
  H4 CHECK starts, all causes, <= 1 per wearer-week                                (M1.4)
  E5-E7 and variant B: descriptive, no verdict (no ground truth for contact or wake; B is a proxy room).
CANNOT CLAIM: sensitivity (no core reference); our sensors (different PPG, a case thermometer not skin T1, no flux, no PPG DC);
  ages (>= 50 by protocol); her own room air (no key); button behaviour (none recorded).
"""
import argparse, datetime, gzip, hashlib, importlib, io, json, multiprocessing as mp, os, subprocess, sys, tarfile, tempfile
from collections import Counter, defaultdict

import numpy as np

REPO = "/home/claude/hg_ai"
SEAL = os.path.join(REPO, "model/sealed_real_older.json")
RAW = "/home/claude/hgdata/raw/older_heatin_montreal"
WATCH = os.path.join(RAW, "summer_2025_smartwatch_data.SLIM.csv.gz")
ENV = os.path.join(RAW, "summer_2025_indoor_environment.SLIM.csv.gz")
ENV_SHA = "76f5b8a79c63e4f0fc4e4e3f1a47a04ee7391149fd473719e2a44975a47ed247"   # README_SOURCE.md (R5)
DONE = os.path.join(REPO, "tests/real_exam_heatin_DONE.json")
OUT_DIR = os.path.join(REPO, "tests/out")
UNIX_MIN = 1.7e9
GAP_FILL_MAX = 120
HRCONF_GOOD = 70
R_STILL, R_ACT, R_WALK = 0.355, 0.714, 1.07
WEARER_DAY_MIN = 600
MIN_WEARER_DAYS = 7
PASS = dict(drink_day=3.0, drink_min_day=90.0, cool_week=1.0, danger_month=1.0, check_week=1.0)
WHY = {1: "env_above", 2: "env_dose", 4: "behaviour", 8: "v12_danger_z", 16: "f20_ge_drink", 32: "nn_logit", 64: "unc_lowering", 128: "who"}
CAUSE = {1: "thermal_danger", 2: "behaviour", 4: "quiet_run", 8: "no_wake", 16: "impact"}
TIERS = dict(drink=1, cool=2, danger=3)

HG = TIO = WG = None          # set in the parent before the pool forks
PROXY = None                  # variant B: (minute array, T array, RH array)


def die(msg, code=1):
    print("REFUSED: " + msg, file=sys.stderr)
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


def check_seal(seal):
    canon = "BRIGHTON:" + ",".join(seal["real_older_exam_brighton_participants"]) + "|HEATIN:" + ",".join(seal["heatin_sealed_watch_macIDs"])
    if hashlib.sha256(canon.encode()).hexdigest() != seal["canonical_sha256"]:
        die("seal canonical SHA-256 mismatch (model/sealed_real_older.json changed)")
    w = sha256_file(WATCH)
    if w != seal["heatin_watch_file_sha256"]:
        die("watch file SHA-256 %s != seal" % w)
    e = sha256_file(ENV)
    if e != ENV_SHA:
        die("environment file SHA-256 %s != README_SOURCE.md" % e)
    if set(seal["heatin_sealed_watch_macIDs"]) & set(seal["heatin_dev_watch_macIDs"]):
        die("seal: DEV and SEALED watch sets overlap")
    return w, e


def load_guardian_from_tag(tag, tmp):
    rc, _ = git("rev-parse", "-q", "--verify", "refs/tags/" + tag)
    if rc != 0:
        die("tag %s does not exist" % tag)
    rc, frozen = git("show", "%s:guardian/FROZEN.txt" % tag)
    if rc != 0:
        die("cannot read guardian/FROZEN.txt at %s" % tag)
    want = None
    for line in frozen.decode(errors="replace").splitlines():
        if "sha256 hg2_weights.json" in line:
            want = line.split("hg2_weights.json")[1].split()[0]
    if not want:
        die("no hg2_weights.json SHA-256 in FROZEN.txt at %s" % tag)
    rc, tar = git("archive", "--format=tar", tag, "guardian/py", "model/export/hg2_weights.json")
    if rc != 0:
        die("git archive %s failed" % tag)
    tarfile.open(fileobj=io.BytesIO(tar)).extractall(tmp, filter="data")
    wpath = os.path.join(tmp, "model/export/hg2_weights.json")
    if sha256_file(wpath) != want:
        die("weights SHA-256 at %s differs from its FROZEN.txt" % tag)
    sys.path.insert(0, os.path.join(tmp, "guardian/py"))
    os.environ.pop("HG_WEIGHTS", None)
    hg = importlib.import_module("hg_guardian_py")
    tio = importlib.import_module("trace_io")
    W = hg.Weights(wpath)
    if W.stub:
        die("weights at %s are the stub" % tag)
    _, head = git("rev-parse", tag + "^{commit}")
    return hg, tio, W, dict(tag=tag, tag_commit=head.decode().strip(), weights_sha256=want, weights_version=W.version, nn_crc=W.crc)


def tree_equals_tag(tag):
    return subprocess.run(["git", "-C", REPO, "diff", "--quiet", tag, "--", "guardian/c", "guardian/py", "model/export"]).returncode == 0


# ------------------------------------------------------------------ data
def fnum(s):
    try:
        return float(s)
    except ValueError:
        return np.nan


def stream_watches(ids):
    """{macID: dict of numpy arrays}; lines of other watches are discarded on their macID before any other field is read"""
    cols = defaultdict(list)
    with gzip.open(WATCH, "rt") as f:
        head = f.readline().rstrip("\n").split(",")
        assert head == ["unix", "tz", "charging", "steps", "hr", "hr_conf", "baro_temp", "baro_press", "acc_min", "acc_max", "acc_avg",
                        "acc_sum", "macID", "bt_bpm", "bt_contact"], head
        for line in f:
            parts = line.rstrip("\n").rsplit(",", 3)
            if len(parts) != 4 or parts[1] not in ids:
                continue
            v = parts[0].split(",")
            if len(v) != 12:
                continue
            cols[parts[1]].append((fnum(v[0]), fnum(v[1]), 1.0 if v[2].strip().lower() == "true" else 0.0, fnum(v[3]), fnum(v[4]),
                                   fnum(v[5]), fnum(v[6]), fnum(v[8]), fnum(v[9])))
    out = {}
    for m, rows in cols.items():
        a = np.array(rows, dtype=np.float64)
        out[m] = dict(unix=a[:, 0], tz=a[:, 1], charging=a[:, 2], steps=a[:, 3], hr=a[:, 4], conf=a[:, 5], baro=a[:, 6],
                      amin=a[:, 7], amax=a[:, 8])
    return out


def build_proxy_air():
    import pandas as pd
    cols = ["unix", "macID", "sensors.SHT85.temp", "sensors.SHT85.rh", "sensors.SHT41.temp", "sensors.SHT41.rh"]
    parts = []
    for ch in pd.read_csv(ENV, usecols=cols, chunksize=500000):
        t = ch["sensors.SHT85.temp"].where(ch["sensors.SHT85.temp"].notna(), ch["sensors.SHT41.temp"])
        rh = ch["sensors.SHT85.rh"].where(ch["sensors.SHT85.rh"].notna(), ch["sensors.SHT41.rh"])
        d = pd.DataFrame(dict(minute=(ch.unix // 60), node=ch.macID, T=t.where((t >= 5) & (t <= 45)), RH=rh.where((rh >= 1) & (rh <= 100))))
        parts.append(d[(ch.unix >= UNIX_MIN) & d["T"].notna()])
    e = pd.concat(parts)
    per = e.groupby(["minute", "node"])[["T", "RH"]].mean().reset_index()
    med = per.groupby("minute")[["T", "RH"]].median()
    return med.index.values.astype(np.int64), med["T"].values, med["RH"].values, int(e.node.nunique())


def astd_map(r, steps):
    if not np.isfinite(r):
        a = 0.0
    elif r <= R_STILL:
        a = 0.002 * max(r, 0.0) / R_STILL
    elif r <= R_ACT:
        a = 0.002 + (r - R_STILL) / (R_ACT - R_STILL) * 0.018
    elif r <= R_WALK:
        a = 0.02 + (r - R_ACT) / (R_WALK - R_ACT) * 0.03
    else:
        a = 0.05 + 0.05 * (r - R_WALK)
    if np.isfinite(steps) and steps >= 10:
        a = max(a, 0.05)
    return min(a, 16.0)


# ------------------------------------------------------------------ replay one watch
def replay(args):
    mac, d, variant = args
    hg, tio = HG, TIO
    ok = d["unix"] >= UNIX_MIN
    d = {k: v[ok] for k, v in d.items()}
    M = (d["unix"] // 60).astype(np.int64)
    order = np.argsort(M, kind="stable")
    d = {k: v[order] for k, v in d.items()}
    M = M[order]
    keep = np.concatenate([[True], np.diff(M) > 0]) if len(M) else np.zeros(0, bool)
    d = {k: v[keep] for k, v in d.items()}
    M = M[keep]
    tz = np.where(np.isfinite(d["tz"]), d["tz"], -14400.0).astype(np.int64) // 60
    if variant == "B":
        pm, pt, prh = PROXY
        idx = np.searchsorted(pm, M, side="right") - 1
        fresh = (idx >= 0) & (M - pm[np.clip(idx, 0, None)] <= 10)
        airT = np.where(fresh, pt[np.clip(idx, 0, None)], np.nan)
        airRH = np.where(fresh, prh[np.clip(idx, 0, None)], np.nan)
    else:
        airT = np.full(len(M), np.nan); airRH = np.full(len(M), np.nan)

    g = hg.Guardian(tio.default_profile(), tio.default_twin(), WG)
    t_drink, t_cap = float(hg.K("HG_T_DRINK")), float(hg.K("HG_M_TOTAL_CAP"))
    day = defaultdict(lambda: Counter())
    paths = {t: Counter() for t in TIERS}
    tier_state = {t: dict(run=0, start=None, last_end=None) for t in TIERS}
    prev = dict(check=0, family=0, worn=None, st=None)
    nohr_run = 0
    worn_runbuf = []        # worn-called minutes waiting to learn whether their no-HR run reaches 60
    jumps = 0
    nan = float("nan")

    def step(minute_abs, tzm, inp, offch, hr_present):
        nonlocal nohr_run, worn_runbuf
        L = minute_abs + tzm
        mod = int(L % 1440); dy = int(L // 1440)
        inp["mod"] = mod
        o = g.step(inp)
        c = day[dy]
        c["minutes"] += 1
        worn = int(o["worn"]); lev = int(o["level"]); st = int(o["state"])
        if worn != 0:
            c["worn_min"] += 1
        if offch:
            c["offch_min"] += 1
            c["offch_worn%d" % worn] += 1
        if worn == 1 and prev["worn"] != 1:
            c["loose_ep"] += 1
        if st == 6 and prev["st"] != 6:
            c["notworn_screen"] += 1
        prev["worn"] = worn; prev["st"] = st
        # suspect worn: worn-called minutes inside a >= 60-min run without any HR value
        if hr_present or not offch:
            nohr_run = 0; worn_runbuf = []
        else:
            nohr_run += 1
            if worn != 0:
                worn_runbuf.append(dy)
            if nohr_run == 60:
                for x in worn_runbuf:
                    day[x]["suspect_worn"] += 1
                worn_runbuf = []
            elif nohr_run > 60 and worn != 0:
                c["suspect_worn"] += 1; worn_runbuf = []
        if lev >= 1:
            c["drink_min"] += 1
        if np.isfinite(inp["tair"]) and inp["tair"] >= 30.0:
            c["proxy_ge30_min"] += 1
        for t, k in TIERS.items():
            s = tier_state[t]
            if lev >= k:
                if s["run"] == 0:
                    s["start"] = minute_abs
                s["run"] += 1
                if s["run"] == 2:
                    if s["last_end"] is None or s["start"] - s["last_end"] >= 10:
                        c[t] += 1
                        why = int(o["why"])
                        for b, nm in WHY.items():
                            if why & b:
                                paths[t][nm] += 1
                        if t == "drink":
                            ax = o["aux"]
                            lab = []
                            if float(ax.get("v12_f20", nan)) >= t_drink - t_cap:
                                lab.append("v12_abs")
                            if ax.get("env_run", 0) >= 10 or ax.get("env_dose", 0) >= 10:
                                lab.append("env")
                            paths[t]["label:" + ("+".join(lab) if lab else "other")] += 1
                        if t == "danger":
                            paths[t]["check_reason:%d" % int(o["check_reason"])] += 1
                if s["run"] >= 2:
                    s["last_end"] = minute_abs
            else:
                s["run"] = 0
        cr = int(o["check_reason"])
        if cr and not prev["check"]:
            c["check"] += 1
            for b, nm in CAUSE.items():
                if cr & b:
                    c["check_" + nm] += 1
        prev["check"] = cr
        fa = int(o["family_alert"])
        if fa and not prev["family"]:
            c["family"] += 1
        prev["family"] = fa

    n = len(M)
    for i in range(n):
        if i:
            gap = int(M[i] - M[i - 1] - 1)
            if 1 <= gap <= GAP_FILL_MAX:
                for k in range(1, gap + 1):
                    step(int(M[i - 1] + k), int(tz[i - 1]),
                         tio.minute(t1=nan, tair=nan, rh=nan, hr=nan, hrq=0, astd=0.0, apeak=1.0, dc=0, charging=1, vbat=4.0), False, False)
            elif gap > GAP_FILL_MAX:
                jumps += 1
        hr = d["hr"][i]
        hr_ok = np.isfinite(hr) and 30 <= hr <= 220
        q = (4 if (np.isfinite(d["conf"][i]) and d["conf"][i] >= HRCONF_GOOD) else 1) if hr_ok else 0
        rng = d["amax"][i] - d["amin"][i]
        amax = d["amax"][i]
        inp = tio.minute(t1=float(d["baro"][i]), t2=nan, tair=float(airT[i]), rh=float(airRH[i]), hr=float(hr) if hr_ok else nan, hrq=q,
                         pi=nan, astd=astd_map(rng, d["steps"][i]), apeak=float(amax) if np.isfinite(amax) else 1.0, dc=0,
                         charging=int(d["charging"][i]), vbat=4.0)
        step(int(M[i]), int(tz[i]), inp, d["charging"][i] == 0, hr_ok)
    return mac, variant, dict(days={int(k): dict(v) for k, v in day.items()}, paths={t: dict(c) for t, c in paths.items()},
                              rows=int(n), jumps=jumps)


# ------------------------------------------------------------------ summarise
def per_watch(res):
    days = res["days"]
    wd = [k for k, c in days.items() if c.get("worn_min", 0) >= WEARER_DAY_MIN]
    tot = Counter()
    for k in wd:
        tot.update(days[k])
    other = Counter()
    for k, c in days.items():
        if k not in wd:
            other.update(c)
    n = len(wd)
    r = dict(wearer_days=n, rows=res["rows"], jumps=res["jumps"], days_with_data=len(days))
    if n:
        r.update(drink_per_day=tot["drink"] / n, drink_min_per_day=tot["drink_min"] / n, cool_per_week=7 * tot["cool"] / n,
                 danger_per_month=30.4 * tot["danger"] / n, check_per_week=7 * tot["check"] / n,
                 family_per_month=30.4 * tot["family"] / n,
                 nowake_per_week=7 * tot["check_no_wake"] / n, quiet_run_per_week=7 * tot["check_quiet_run"] / n,
                 impact_per_week=7 * tot["check_impact"] / n,
                 thermal_check_per_week=7 * tot["check_thermal_danger"] / n, behaviour_check_per_week=7 * tot["check_behaviour"] / n,
                 nowake_day_share=sum(1 for k in wd if days[k].get("check_no_wake", 0)) / n,
                 loose_ep_per_day=tot["loose_ep"] / n)
        hot = [k for k in wd if days[k].get("proxy_ge30_min", 0) >= 60]
        if hot:
            r["proxy_hot_days"] = len(hot)
            r["drink_per_hot_day"] = sum(days[k].get("drink", 0) for k in hot) / len(hot)
    oc = sum(c.get("offch_min", 0) for c in days.values())
    if oc:
        r.update(offcharger_minutes=oc, offch_called_worn_pct=100 * sum(c.get("offch_worn2", 0) for c in days.values()) / oc,
                 offch_called_loose_pct=100 * sum(c.get("offch_worn1", 0) for c in days.values()) / oc,
                 offch_called_off_pct=100 * sum(c.get("offch_worn0", 0) for c in days.values()) / oc)
    wm = sum(c.get("worn_min", 0) for c in days.values())
    if wm:
        r["suspect_worn_pct_of_worn"] = 100 * sum(c.get("suspect_worn", 0) for c in days.values()) / wm
    r["events_on_non_wearer_days"] = {k: other[k] for k in ("drink", "cool", "danger", "check", "family") if other[k]}
    r["counts_on_wearer_days"] = {k: tot[k] for k in ("drink", "cool", "danger", "check", "family", "check_no_wake", "check_quiet_run",
                                                      "check_impact", "check_thermal_danger", "check_behaviour") if tot[k]}
    return r


def aggregate(watches, paths):
    el = {m: w for m, w in watches.items() if w["wearer_days"] >= MIN_WEARER_DAYS}
    out = dict(watches_total=len(watches), watches_scored=len(el), wearer_days=sum(w["wearer_days"] for w in el.values()))
    keys = ["drink_per_day", "drink_min_per_day", "cool_per_week", "danger_per_month", "check_per_week", "family_per_month",
            "nowake_per_week", "quiet_run_per_week", "impact_per_week", "thermal_check_per_week", "behaviour_check_per_week",
            "nowake_day_share", "loose_ep_per_day", "offch_called_worn_pct", "offch_called_loose_pct", "offch_called_off_pct",
            "suspect_worn_pct_of_worn", "drink_per_hot_day"]
    for k in keys:
        v = [w[k] for w in el.values() if k in w]
        if v:
            out[k] = dict(median=float(np.median(v)), mean=float(np.mean(v)), p90=float(np.percentile(v, 90)), n=len(v))
    tp = {t: Counter() for t in TIERS}
    for m in el:
        for t in TIERS:
            tp[t].update(paths[m].get(t, {}))
    out["paths_at_onset"] = {t: dict(c) for t, c in tp.items()}
    return out


def verdicts(a):
    def med(k):
        return a[k]["median"] if k in a else None
    v = {}
    if not a["watches_scored"]:
        return {"all": "N/A (no watch with >= %d wearer-days)" % MIN_WEARER_DAYS}
    v["H1_drink"] = "PASS" if (med("drink_per_day") <= PASS["drink_day"] and med("drink_min_per_day") <= PASS["drink_min_day"]) else "FAIL"
    v["H2_cool"] = "PASS" if med("cool_per_week") <= PASS["cool_week"] else "FAIL"
    v["H3_danger"] = "PASS" if med("danger_per_month") <= PASS["danger_month"] else "FAIL"
    v["H4_check"] = "PASS" if med("check_per_week") <= PASS["check_week"] else "FAIL"
    return v


def main():
    global HG, TIO, WG, PROXY
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tag", required=True)
    ap.add_argument("--dry-run-dev", action="store_true")
    ap.add_argument("--max-watches", type=int, default=None, help="dry run only: first N DEV watches (timing tests)")
    ap.add_argument("--procs", type=int, default=2)
    a = ap.parse_args()
    dry = a.dry_run_dev
    if a.max_watches and not dry:
        die("--max-watches is for the dry run only")
    if not dry and os.path.exists(DONE):
        die("the HeatIN exam has already run (%s exists)" % DONE, 2)
    seal = json.load(open(SEAL))
    wsha, esha = check_seal(seal)
    same = tree_equals_tag(a.tag)
    me = os.path.relpath(os.path.abspath(__file__), REPO)
    if not dry:
        if not same:
            die("working tree differs from %s in guardian/c guardian/py model/export" % a.tag)
        if subprocess.run(["git", "-C", REPO, "diff", "--quiet", "HEAD", "--", me]).returncode != 0 or \
                git("ls-files", "--error-unmatch", me)[0] != 0:
            die("%s is not committed unchanged" % me)
    tmp = tempfile.mkdtemp(prefix="realexam_h_")
    HG, TIO, WG, ginfo = load_guardian_from_tag(a.tag, tmp)
    ginfo["working_tree_equals_tag"] = same
    ids = sorted(seal["heatin_dev_watch_macIDs"] if dry else seal["heatin_sealed_watch_macIDs"])
    if a.max_watches:
        ids = ids[:a.max_watches]
    _, head = git("rev-parse", "HEAD")
    rec = dict(exam="REAL-EXAM HeatIN v1", mode="DEV dry run (DEV watches)" if dry else "SEALED (sealed watches)",
               started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), git_head=head.decode().strip(), guardian=ginfo,
               watch_file_sha256=wsha, env_file_sha256=esha, seal_canonical_sha256=seal["canonical_sha256"],
               script_sha256=sha256_file(os.path.abspath(__file__)), watches=ids, status="started")
    if not dry:
        with open(DONE, "x") as f:
            json.dump(rec, f, indent=1)
    pm, pt, prh, nnodes = build_proxy_air()
    PROXY = (pm, pt, prh)
    rec["proxy_air"] = dict(nodes=nnodes, minutes=int(len(pm)), median_T=float(np.median(pt)))
    data = stream_watches(set(ids))
    assert set(data) <= set(ids)
    tasks = [(m, data[m], v) for v in ("A", "B") for m in ids if m in data]
    ctx = mp.get_context("fork")
    with ctx.Pool(a.procs) as pool:
        outs = pool.map(replay, tasks, chunksize=1)
    del data
    res = {}
    for v in ("A", "B"):
        watches = {m: per_watch(r) for m, vv, r in outs if vv == v}
        paths = {m: r["paths"] for m, vv, r in outs if vv == v}
        agg = aggregate(watches, paths)
        res[v] = dict(aggregate=agg, verdicts=verdicts(agg), per_watch=watches)
    rec["results"] = dict(A_primary_room_air_missing=res["A"], B_secondary_proxy_building_air_no_verdict=res["B"])
    rec["status"] = "complete"
    rec["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rec["label"] = ("DEV (HeatIN DEV watches) - NOT an exam result" if dry else
                    "REAL older adults (>= 50 by protocol) at home, Montreal summer 2025, Bangle.js 2 watch; alarms UNCONFIRMED")
    os.makedirs(OUT_DIR, exist_ok=True)
    outp = os.path.join(OUT_DIR, "real_exam_heatin_%s.json" % ("DEV" if dry else "SEALED"))
    js = json.dumps(rec, indent=1, default=lambda o: float(o) if isinstance(o, np.floating) else int(o))
    with open(outp, "w") as f:
        f.write(js)
    if not dry:
        with open(DONE, "w") as f:
            f.write(js)
    print("[%s] tag %s" % (rec["mode"], a.tag))
    for v in ("A", "B"):
        ag = res[v]["aggregate"]
        print(" variant %s: watches %d scored (>= %d wearer-days) of %d, wearer-days %d" % (v, ag["watches_scored"], MIN_WEARER_DAYS,
                                                                                         ag["watches_total"], ag["wearer_days"]))
        for k in ("drink_per_day", "drink_min_per_day", "cool_per_week", "danger_per_month", "check_per_week", "family_per_month",
                  "nowake_per_week", "quiet_run_per_week", "impact_per_week", "thermal_check_per_week", "behaviour_check_per_week",
                  "nowake_day_share", "loose_ep_per_day", "offch_called_worn_pct", "offch_called_loose_pct", "suspect_worn_pct_of_worn",
                  "drink_per_hot_day"):
            if k in ag:
                print("   %-26s median %8.3f  mean %8.3f  p90 %8.3f  (n %d)" % (k, ag[k]["median"], ag[k]["mean"], ag[k]["p90"], ag[k]["n"]))
        print("   paths:", json.dumps(ag["paths_at_onset"]))
        print("   verdicts:", res[v]["verdicts"])
    print(" wrote", outp, "" if dry else "and " + DONE)


if __name__ == "__main__":
    main()
