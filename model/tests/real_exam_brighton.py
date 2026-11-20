#!/usr/bin/env python3
"""Heat Guardian - PRE-REGISTERED REAL older-adult exam #1: Brighton / Waldock (65-76 y, 35 C / 50 % RH). Decision M18.

Written Nov 12 2026 by agent REAL-EXAM, BEFORE any sealed row was read. The metrics, input mapping and pass lines below are
fixed now. A FAIL is a finding with a written why, never a reason to change this file. RUN ONCE, by the manager, at the
freeze tag M19.5 names (freeze-5), after SEALED-SIM-3.

  exam (ONCE)  : python3 -I tests/real_exam_brighton.py --tag <freeze-tag>
  DEV dry run  : python3 -I tests/real_exam_brighton.py --tag <freeze-tag> --dry-run-dev
                 (participant P1 only; never opens a sealed sheet; never reads or writes the DONE file)

SOURCE  /home/claude/hgdata/raw/older_brighton_adl_waldock/R1848_Eastbourne_Heat_Stress_Waldock.xlsx
  Waldock KAM, Hayes M, Watt PW, Maxwell NS, Public Health 2021, doi:10.1016/j.puhe.2021.01.016; data doi:10.17033/DATA.00000107.
  LICENCE CC BY-ND 3.0: no derived data file is written or committed. Output = one results JSON of summary numbers
  (MAE, counts, rates; per-session summaries), never a per-minute or per-sample table.
  10 people aged 65-76 (sex not in the file). 3 sessions each (Control, Water, Menthol): enter a ~35.5 C / ~51 % RH chamber,
  30 min seated rest, a cognitive test, 30 min cycling at a fixed power, a cognitive test. Every 5 min: rectal T, ear T, HR,
  chest/bicep/quadriceps/calf skin, ambient T/RH/WBGT. Whole-file rectal max 38.34 C (R5 marginal, DEV knowledge).
SPLIT (model/sealed_real_older.json, M18): DEV = sheet P1 + the summary sheets (seen by R5). SEALED = sheets P2..P10.
  In --dry-run-dev the code opens the workbook with openpyxl read_only and iterates ONLY the sheets 'P1' and
  'Participant characteristics'; the sealed sheet objects are never iterated.

GUARDS (in order, before any sealed sheet is iterated)
  G1 seal: canonical string "BRIGHTON:" + ",".join(P..) + "|HEATIN:" + ",".join(sealed macIDs) hashes to canonical_sha256,
     and SHA-256(xlsx) == brighton_xlsx_sha256.
  G2 guardian: tag --tag exists; the guardian is loaded FROM THE TAG (git archive guardian/py + model/export/hg2_weights.json)
     and SHA-256(hg2_weights.json) equals the value in that tag's guardian/FROZEN.txt; non-stub weights.
     Exam mode also asserts `git diff --quiet <tag> -- guardian/c guardian/py model/export` (working tree = tag) and that
     this script is committed unchanged (git diff --quiet HEAD -- this file). Dry run only reports the diff status.
  G3 exam mode: refuse (exit 2) if tests/real_exam_brighton_DONE.json exists; write it FIRST (time, tag, git HEAD, hashes,
     script SHA-256, status=started), then read P2..P10 and score; results are added to the same file at the end. A crash
     after G3 still spends the exam.

INPUT MAPPING (Brighton -> band minute inputs; as honest as the data allow; every choice is a caveat on every number)
  Time axis per session (elapsed min; 0 = entering the chamber): a row with Time 0 (or labelled 'pre entering the chamber')
    -> 0; rest rows 5..30 -> 5..30; the cognitive test after rest (Time empty) -> 35; exercise rows k -> 35 + k (40..65);
    the final cognitive test -> 70. ASSUMPTION: the test lasts 5 min (not in the file; shifts lead times by up to +-5 min).
  hr      = HR column (lab monitor, not wrist PPG), hrq = 4 when 30..220 bpm, else missing.
  t1      = BICEP skin (the site closest to the wrist/forearm; chest/quads/calf are further). It is upper-arm skin, not wrist
            skin under a strap: T1-like only. t2 = missing -> heat flux INVALID every minute (flux_valid = 0).
  tair/rh = measured ambient T / RH of the row. Plausibility: T 10..45 C, RH 15..95 % (the file has typos such as RH 5.2),
            rectal 35..42, HR 30..220, bicep 25..40; an implausible or empty value is missing and the last valid value is
            held (none yet -> missing).
  motion  = no accelerometer: a_std = 0.05 g in a minute whose 5-min interval ends at a sample with Power > 0 (cycling,
            elapsed 36..65; the HTT replay convention for exercise) else 0.01 g
            (seated: between the band's STILL 0.002 and ACTIVE 0.02 g). apeak 1.0 g, z-angle missing.
  contact = forced worn (force_worn = 2, as the HTT replay): this exam scores core and alarms, not the contact check.
            PPG DC 110000 (on skin), PI missing, no button presses, BLE unknown, time of day unknown (mod = 0xFFFF:
            routine and the day-window DRINK path are off, as in every HTT replay), no forecast.
  profile = age and BMI from 'Participant characteristics'; sex unknown -> sex_m = 0.5 (KF reads it as female); no
            medication flags. Twin = population default (rest_hr 70, k 0.12, offset 0, c_bodyheat 0.15).
  5 min -> 1 min resampling, PRIMARY = causal HOLD (minute t uses the last sample with elapsed <= t; the band never sees the
    future). SECONDARY (reported, no verdict) = LINEAR interpolation between samples (non-causal, up to 4 min look-ahead).
  Pre-roll: 30 min before elapsed 0 replaying the first row (the wearer has the band on before entering), so the 5-min valid
    gate and the 20-min donning blank are passed at elapsed 0. Pre-roll minutes are never scored.
  The DRINK personal-relative line needs a learned calm baseline (days) and a known time of day -> it cannot fire here;
    the absolute v1.2 DRINK path (heat context: room >= 30 C is true in the chamber), env/PSU paths, COOL and DANGER can.

PRE-REGISTERED METRICS (scored at the original 5-min reference samples with a rectal value, elapsed 0..70; never at
interpolated rectal values)
  M1 core MAE and bias (estimate - rectal), pooled over reference samples, 95 % CI by participant bootstrap
     (2000 resamples, seed 20261115), for: (a) hg2 core_now (the displayed core), (b) v1.2 alone (aux v12_est = the frozen
     v1.2 Kalman + linear correction inside the guardian, same inputs). Also per session (summary numbers only), and a
     SECONDARY in-chamber-only figure (elapsed 0..65, i.e. without the final cognitive test row, which in some sessions is
     recorded after leaving the chamber); no verdict on the secondary figure.
  M2 displayed-range coverage: share of samples with |rectal - core_now| <= half, half = max(1.645 * max(sd_now, HG_SD_FLOOR),
     HG_RANGE_HALF_REAL_EFF) = the REAL widths shown on the screen (FROZEN.txt [B2-fix]). Also the NN-sd-only width
     (1.645 * max(sd_now, floor)), reported.
  M3 alarms vs rectal, per tier displayed (DRINK = level >= 1, COOL = level >= 2, DANGER = level >= 3), each against
     rectal >= 38.0 and >= 38.5 events. Definitions copied from model/hg2/htt_eval_lib.py (the v1.2/hg2 HTT scoring):
     episode = >= 2 consecutive minutes, gaps < 10 min merged; event = first reference sample >= threshold in a session;
     detected = an episode active in [event - 45, event + 10]; lead = event - episode onset (min);
     false alarm = an episode after whose onset no reference sample within 60 min reaches the tier's anchor
     (DRINK -> 38.0, COOL -> 38.5, DANGER -> 38.5; as the HTT acceptance rows). Episodes whose 60-min window runs past the
     session end and are not confirmed count as false AND are reported as "censored". Exposure hours = sum over sessions of
     (last reference elapsed - 0) / 60.
PRE-REGISTERED PASS LINES (primary = HOLD resampling; verdicts PASS / FAIL / N/A)
  B1 hg2 core_now MAE <= 0.35 C                          (1.4 x the young-adult sealed v1.2 MAE 0.25 C; design line)
  B2 |hg2 bias| <= 0.20 C                                (M1.3: the total threshold lowering is capped at 0.20 C)
  B3 v1.2-alone MAE <= 0.35 C                            (same line, tests the HR-only anchor on 65+)
  B4 displayed-range coverage >= 80 %                    (nominal 90 %; sealed set-1 coverage was 85.0 %)
  B5 DRINK sensitivity to rectal >= 38.0 events >= 70 %  (N/A if fewer than 5 events)
  B6 COOL and DANGER sensitivity to >= 38.5 events       (no verdict: the file never reaches 38.5 C; counts reported)
  B7 false alarms per exposure hour: DRINK <= 0.15, COOL <= 0.10, DANGER <= 0.10 (the v1.2 budgets in FROZEN.txt)
CANNOT CLAIM: danger detection in 65+ (no sample >= 38.5 C); wrist-PPG HR or wrist skin (lab HR, bicep skin); heat flux
  (no reference sensor); daylong passive heat; n = 9 healthy active volunteers, 1-h sessions.
"""
import argparse, datetime, hashlib, importlib, io, json, os, subprocess, sys, tarfile, tempfile

import numpy as np

REPO = "/home/claude/hg_ai"
SEAL = os.path.join(REPO, "model/sealed_real_older.json")
XLSX = "/home/claude/hgdata/raw/older_brighton_adl_waldock/R1848_Eastbourne_Heat_Stress_Waldock.xlsx"
DONE = os.path.join(REPO, "tests/real_exam_brighton_DONE.json")
OUT_DIR = os.path.join(REPO, "tests/out")
DEV_SHEETS = ["P1"]
PREROLL = 30
BOOT_N, BOOT_SEED = 2000, 20261115
PASS = dict(mae=0.35, bias=0.20, cover=80.0, drink_sens=70.0, drink_min_events=5, fa=dict(drink=0.15, cool=0.10, danger=0.10))
ANCHOR = dict(drink=38.0, cool=38.5, danger=38.5)
TIERS = dict(drink=1, cool=2, danger=3)
COLS = {"time": 1, "power": 2, "rectal": 3, "hr": 5, "bicep": 7, "amb_t": 15, "amb_rh": 16}
HEADER = {1: "time (min)", 2: "power (w)", 3: "core rectal", 5: "hr", 7: "bicep (°c)", 15: "amb temp (°c)", 16: "amb rh%"}


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


# ------------------------------------------------------------------ guards
def check_seal(seal):
    canon = "BRIGHTON:" + ",".join(seal["real_older_exam_brighton_participants"]) + "|HEATIN:" + ",".join(seal["heatin_sealed_watch_macIDs"])
    if hashlib.sha256(canon.encode()).hexdigest() != seal["canonical_sha256"]:
        die("seal canonical SHA-256 mismatch (model/sealed_real_older.json changed)")
    x = sha256_file(XLSX)
    if x != seal["brighton_xlsx_sha256"]:
        die("Brighton xlsx SHA-256 %s != seal %s" % (x, seal["brighton_xlsx_sha256"]))
    return x


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
    rc_head, head = git("rev-parse", tag + "^{commit}")
    return hg, tio, W, dict(tag=tag, tag_commit=head.decode().strip(), weights_sha256=want, weights_version=W.version, nn_crc=W.crc)


def tree_equals_tag(tag):
    r = subprocess.run(["git", "-C", REPO, "diff", "--quiet", tag, "--", "guardian/c", "guardian/py", "model/export"])
    return r.returncode == 0


# ------------------------------------------------------------------ data
def num(v, lo, hi):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return np.nan
    return f if (np.isfinite(f) and lo <= f <= hi) else np.nan


def read_profiles(wb):
    prof = {}
    for r in wb["Participant characteristics"].iter_rows(values_only=True):
        if r and isinstance(r[0], (int, float)) and r[1] is not None:
            age, h, m = float(r[1]), float(r[2]), float(r[3])
            prof["P%d" % int(r[0])] = dict(age=age, sex_m=0.5, bmi=m / (h * h), med_flags=0)
    return prof


def parse_sheet(ws):
    """-> list of sessions, each: dict(name, rows=[dict(el, power, rectal, hr, bicep, amb_t, amb_rh)])"""
    rows = list(ws.iter_rows(values_only=True))
    sessions = []
    i = 0
    names = ["Control", "Water", "Menthol"]
    while i < len(rows):
        r = rows[i]
        if r and len(r) > 16 and isinstance(r[1], str) and r[1].strip().lower() == "time (min)":
            for c, want in HEADER.items():
                got = (r[c] or "").strip().lower() if isinstance(r[c], str) else ""
                if got != want:
                    raise SystemExit("unexpected header in %s col %d: %r (want %r)" % (ws.title, c, got, want))
            phase = "rest"
            sess = []
            j = i + 1
            while j < len(rows):
                d = rows[j]
                if not d or all(v is None for v in d[:17]) or (len(d) > 1 and isinstance(d[1], str)):
                    break
                d = list(d) + [None] * (20 - len(d))
                lab = (d[0] or "").strip().lower() if isinstance(d[0], str) else ""
                t = d[COLS["time"]]
                if lab.startswith("exercise"):
                    phase = "ex"
                if isinstance(t, (int, float)):
                    el = float(t) if phase == "rest" else 35.0 + float(t)   # rest k -> k; exercise k -> 35 + k
                elif phase == "rest":
                    el, phase = 35.0, "test"                                 # cognitive test after rest
                else:
                    el = 70.0                                                # final cognitive test
                sess.append(dict(el=el, power=num(d[COLS["power"]], 0, 1000), rectal=num(d[COLS["rectal"]], 35, 42),
                                 hr=num(d[COLS["hr"]], 30, 220), bicep=num(d[COLS["bicep"]], 25, 40),
                                 amb_t=num(d[COLS["amb_t"]], 10, 45), amb_rh=num(d[COLS["amb_rh"]], 15, 95)))
                j += 1
            els = [s["el"] for s in sess]
            if els != sorted(els) or len(set(els)) != len(els):
                raise SystemExit("non-monotone time axis in %s session %d: %s" % (ws.title, len(sessions) + 1, els))
            sessions.append(dict(name=names[len(sessions)] if len(sessions) < 3 else "S%d" % (len(sessions) + 1), rows=sess))
            i = j
        else:
            i += 1
    return sessions


def minutes_for(sess, mode, tio):
    """band minute inputs from -PREROLL to the last elapsed sample (inclusive), plus the minute index of elapsed 0"""
    rows = sess["rows"]
    el = np.array([r["el"] for r in rows])
    end = int(el.max())

    def held(key):
        out, last = [], np.nan
        for r in rows:
            v = r[key]
            if np.isfinite(v):
                last = v
            out.append(last)
        return np.array(out)

    series = {k: held(k) for k in ("hr", "bicep", "amb_t", "amb_rh")}
    raw = {k: np.array([r[k] for r in rows]) for k in ("hr", "bicep", "amb_t", "amb_rh")}
    power = np.array([r["power"] for r in rows])

    def value(k, t):
        if t <= el[0]:
            v = raw[k][0]
            return v if np.isfinite(v) else np.nan
        i = int(np.searchsorted(el, t, side="right") - 1)
        if mode == "hold" or i >= len(el) - 1 or t == el[i]:
            return series[k][i]
        a, b = series[k][i], raw[k][i + 1]
        if not np.isfinite(b):
            return a
        if not np.isfinite(a):
            return np.nan
        return a + (b - a) * (t - el[i]) / (el[i + 1] - el[i])

    mins = []
    for t in range(-PREROLL, end + 1):
        nxt = int(np.searchsorted(el, t, side="left"))               # first sample with elapsed >= t
        cyc = t > el[0] and nxt < len(el) and np.isfinite(power[nxt]) and power[nxt] > 0
        hr = value("hr", t)
        mins.append(tio.minute(mod=0xFFFF, t1=value("bicep", t), t2=float("nan"), tair=value("amb_t", t), rh=value("amb_rh", t),
                               hr=hr, hrq=4 if np.isfinite(hr) else 0, pi=float("nan"), astd=0.05 if cyc else 0.01, apeak=1.0,
                               dc=110000, force_worn=2, vbat=4.0))
    return mins, PREROLL, end


# ------------------------------------------------------------------ scoring (htt_eval_lib definitions)
def episodes(mask, k=2, merge_gap=10):
    m = np.concatenate([[0], mask.astype(np.int8), [0]]); d = np.diff(m)
    st = np.where(d == 1)[0]; en = np.where(d == -1)[0] - 1
    eps = []
    for a, b in zip(st, en):
        if b - a + 1 >= k:
            if eps and a - eps[-1][1] < merge_gap:
                eps[-1] = (eps[-1][0], b)
            else:
                eps.append((a, b))
    return eps


def run_session(hg, tio, W, prof, sess, mode):
    mins, off, end = minutes_for(sess, mode, tio)
    g = hg.Guardian(prof, tio.default_twin(), W)
    floor, real = float(hg.K("HG_SD_FLOOR")), float(hg.K("HG_RANGE_HALF_REAL_EFF"))
    lev, core, v12, sdn = [], [], [], []
    for m in mins:
        o = g.step(m)
        lev.append(int(o["level"])); core.append(float(o["core_now"])); v12.append(float(o["aux"]["v12_est"]))
        sdn.append(float(o.get("core_sd_now", o.get("sd_now", np.nan))))
    lev = np.array(lev[off:]); core = np.array(core[off:]); v12 = np.array(v12[off:]); sdn = np.array(sdn[off:])
    refs = [(int(r["el"]), r["rectal"]) for r in sess["rows"] if np.isfinite(r["rectal"]) and 0 <= r["el"] <= end]
    samp = []
    for t, y in refs:
        sd = max(sdn[t], floor) if np.isfinite(sdn[t]) else floor
        samp.append(dict(t=t, y=y, hg2=core[t], v12=v12[t], half_real=max(1.645 * sd, real), half_nn=1.645 * sd))
    tl, yl = np.array([s["t"] for s in samp]), np.array([s["y"] for s in samp])
    alarms = {}
    for tier, k in TIERS.items():
        eps = episodes(lev >= k)
        res = {}
        for thr in (38.0, 38.5):
            hit = np.where(yl >= thr)[0]
            ev = int(tl[hit[0]]) if len(hit) else None
            det, lead = 0, None
            if ev is not None:
                for a, b in eps:
                    if a <= ev + 10 and b >= ev - 45:
                        det, lead = 1, ev - a
                        break
            res["%.1f" % thr] = dict(event=ev, detected=det, lead_min=lead)
        fa = cens = 0
        for a, b in eps:
            w = yl[(tl >= a) & (tl <= a + 60)]
            if not (len(w) and w.max() >= ANCHOR[tier]):
                fa += 1
                if a + 60 > end:
                    cens += 1
        res.update(episodes=len(eps), false_alarms=fa, censored=cens, onsets=[int(a) for a, b in eps])
        alarms[tier] = res
    return dict(samples=samp, alarms=alarms, hours=end / 60.0)


def boot_ci(per_part, stat, rng):
    keys = sorted(per_part)
    if len(keys) < 2:
        return None
    vals = []
    for _ in range(BOOT_N):
        pick = rng.choice(len(keys), len(keys), replace=True)
        e = np.concatenate([per_part[keys[i]] for i in pick])
        vals.append(stat(e))
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def summarise(results, label):
    """results: {pid: {session_name: run_session output}}"""
    rng = np.random.default_rng(BOOT_SEED)
    out = dict(label=label)
    for est in ("hg2", "v12"):
        per = {p: np.array([s[est] - s["y"] for sess in r.values() for s in sess["samples"]]) for p, r in results.items()}
        e = np.concatenate(list(per.values()))
        out[est] = dict(n_samples=int(len(e)), mae=float(np.mean(np.abs(e))), bias=float(np.mean(e)),
                        mae_ci95=boot_ci(per, lambda x: np.mean(np.abs(x)), rng), bias_ci95=boot_ci(per, np.mean, rng),
                        per_session={"%s/%s" % (p, sn): dict(mae=float(np.mean(np.abs([s[est] - s["y"] for s in ss["samples"]]))),
                                                            bias=float(np.mean([s[est] - s["y"] for s in ss["samples"]])),
                                                            n=len(ss["samples"]))
                                     for p, r in results.items() for sn, ss in r.items() if ss["samples"]})
        e65 = np.array([s[est] - s["y"] for r in results.values() for sess in r.values() for s in sess["samples"] if s["t"] <= 65])
        out[est]["in_chamber_0_65"] = dict(n_samples=int(len(e65)), mae=float(np.mean(np.abs(e65))), bias=float(np.mean(e65)))
    allS = [s for r in results.values() for sess in r.values() for s in sess["samples"]]
    out["coverage_real_pct"] = 100.0 * np.mean([abs(s["y"] - s["hg2"]) <= s["half_real"] for s in allS])
    out["coverage_nn_sd_only_pct"] = 100.0 * np.mean([abs(s["y"] - s["hg2"]) <= s["half_nn"] for s in allS])
    out["half_real_median"] = float(np.median([s["half_real"] for s in allS]))
    out["rectal_max"] = float(max(s["y"] for s in allS))
    hours = sum(sess["hours"] for r in results.values() for sess in r.values())
    out["exposure_hours"] = hours
    out["sessions"] = sum(len(r) for r in results.values())
    al = {}
    for tier in TIERS:
        a = dict(episodes=0, false_alarms=0, censored=0)
        for thr in ("38.0", "38.5"):
            evs = [(sess["alarms"][tier][thr]) for r in results.values() for sess in r.values()]
            n_ev = sum(1 for x in evs if x["event"] is not None)
            det = sum(x["detected"] for x in evs if x["event"] is not None)
            leads = [x["lead_min"] for x in evs if x["event"] is not None and x["detected"]]
            a["vs_" + thr] = dict(events=n_ev, detected=det, sensitivity_pct=(100.0 * det / n_ev) if n_ev else None,
                                  lead_median_min=float(np.median(leads)) if leads else None, leads=leads)
        for r in results.values():
            for sess in r.values():
                for k in ("episodes", "false_alarms", "censored"):
                    a[k] += sess["alarms"][tier][k]
        a["false_alarms_per_h"] = a["false_alarms"] / hours if hours else None
        al[tier] = a
    out["alarms"] = al
    return out


def verdicts(s):
    v = {}
    v["B1_hg2_mae"] = "PASS" if s["hg2"]["mae"] <= PASS["mae"] else "FAIL"
    v["B2_hg2_bias"] = "PASS" if abs(s["hg2"]["bias"]) <= PASS["bias"] else "FAIL"
    v["B3_v12_mae"] = "PASS" if s["v12"]["mae"] <= PASS["mae"] else "FAIL"
    v["B4_coverage"] = "PASS" if s["coverage_real_pct"] >= PASS["cover"] else "FAIL"
    d = s["alarms"]["drink"]["vs_38.0"]
    v["B5_drink_sens"] = "N/A (%d events < %d)" % (d["events"], PASS["drink_min_events"]) if d["events"] < PASS["drink_min_events"] else \
        ("PASS" if d["sensitivity_pct"] >= PASS["drink_sens"] else "FAIL")
    v["B6_cool_danger_385"] = "NO VERDICT (pre-registered): events %d" % s["alarms"]["danger"]["vs_38.5"]["events"]
    for tier in TIERS:
        v["B7_fa_%s" % tier] = "PASS" if s["alarms"][tier]["false_alarms_per_h"] <= PASS["fa"][tier] else "FAIL"
    return v


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tag", required=True, help="frozen guardian tag, e.g. hg2-freeze-5")
    ap.add_argument("--dry-run-dev", action="store_true", help="DEV only (P1); never touches the DONE file")
    a = ap.parse_args()
    dry = a.dry_run_dev
    if not dry and os.path.exists(DONE):
        die("the Brighton exam has already run (%s exists)" % DONE, 2)
    seal = json.load(open(SEAL))
    xsha = check_seal(seal)
    sealed = list(seal["real_older_exam_brighton_participants"])
    assert not set(DEV_SHEETS) & set(sealed)
    same = tree_equals_tag(a.tag)
    me = os.path.relpath(os.path.abspath(__file__), REPO)
    if not dry:
        if not same:
            die("working tree differs from %s in guardian/c guardian/py model/export" % a.tag)
        if subprocess.run(["git", "-C", REPO, "diff", "--quiet", "HEAD", "--", me]).returncode != 0 or \
                git("ls-files", "--error-unmatch", me)[0] != 0:
            die("%s is not committed unchanged" % me)
    tmp = tempfile.mkdtemp(prefix="realexam_b_")
    hg, tio, W, ginfo = load_guardian_from_tag(a.tag, tmp)
    ginfo["working_tree_equals_tag"] = same
    rc, head = git("rev-parse", "HEAD")
    rec = dict(exam="REAL-EXAM Brighton v1", mode="DEV dry run (P1 only)" if dry else "SEALED (P2..P10)",
               started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), git_head=head.decode().strip(), guardian=ginfo,
               xlsx_sha256=xsha, seal_canonical_sha256=seal["canonical_sha256"], script_sha256=sha256_file(os.path.abspath(__file__)),
               participants=DEV_SHEETS if dry else sealed, status="started")
    if not dry:
        with open(DONE, "x") as f:
            json.dump(rec, f, indent=1)
    import openpyxl
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    profiles = read_profiles(wb)
    parts = DEV_SHEETS if dry else sealed
    parsed = {p: parse_sheet(wb[p]) for p in parts}
    res = {}
    for mode in ("hold", "linear"):
        results = {}
        for p in parts:
            results[p] = {s["name"]: run_session(hg, tio, W, profiles[p], s, mode) for s in parsed[p]}
        res[mode] = summarise(results, ("DEV " if dry else "SEALED ") + mode)
    rec["results"] = res
    rec["verdicts_primary_hold"] = verdicts(res["hold"])
    rec["verdicts_secondary_linear_no_verdict"] = verdicts(res["linear"])
    rec["status"] = "complete"
    rec["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rec["label"] = ("DEV (participant P1, seen by R5) - NOT an exam result" if dry else
                    "REAL older adults 65-76, n = 9, 35 C chamber, lab HR, bicep skin, 5-min reference")
    os.makedirs(OUT_DIR, exist_ok=True)
    outp = os.path.join(OUT_DIR, "real_exam_brighton_%s.json" % ("DEV" if dry else "SEALED"))
    js = json.dumps(rec, indent=1, default=lambda o: float(o) if isinstance(o, np.floating) else int(o))
    with open(outp, "w") as f:
        f.write(js)
    if not dry:
        with open(DONE, "w") as f:
            f.write(js)
    h = res["hold"]
    print("[%s] tag %s  sessions %d  samples %d  hours %.2f  rectal max %.2f" % (rec["mode"], a.tag, h["sessions"], h["hg2"]["n_samples"],
                                                                                h["exposure_hours"], h["rectal_max"]))
    for m in ("hold", "linear"):
        r = res[m]
        print(" %-6s hg2 MAE %.3f bias %+.3f | v1.2 MAE %.3f bias %+.3f | cover REAL %.1f %% (NN-sd %.1f %%) | 0..65: hg2 %.3f v1.2 %.3f" % (
            m, r["hg2"]["mae"], r["hg2"]["bias"], r["v12"]["mae"], r["v12"]["bias"], r["coverage_real_pct"], r["coverage_nn_sd_only_pct"],
            r["hg2"]["in_chamber_0_65"]["mae"], r["v12"]["in_chamber_0_65"]["mae"]))
        for t, x in r["alarms"].items():
            print("        %-6s ep %d FA %d (%.2f/h, censored %d) | vs38.0 %d/%d lead %s | vs38.5 %d/%d" % (
                t, x["episodes"], x["false_alarms"], x["false_alarms_per_h"], x["censored"], x["vs_38.0"]["detected"],
                x["vs_38.0"]["events"], x["vs_38.0"]["lead_median_min"], x["vs_38.5"]["detected"], x["vs_38.5"]["events"]))
    print(" verdicts (hold):", rec["verdicts_primary_hold"])
    print(" wrote", outp, "" if dry else "and " + DONE)


if __name__ == "__main__":
    main()
