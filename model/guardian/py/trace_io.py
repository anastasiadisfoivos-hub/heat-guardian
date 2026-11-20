"""Replay CSV I/O shared by run_traces.py, tests/make_traces.py and eval_fa.py.
Input row format (one minute) = guardian/c/host_test.c replay():
  mod,t1,t2,tair,rh,hr,hrq,pi,astd,apeak,dc,flat,button,charging,vbat,ble,force_worn,cmd, t1_5s x12, t2_5s x12, tair_5s x12, z x12 [,expect]
Header lines: #PROFILE,age,sex_m,bmi,flags  #TWIN,rest_hr,k,offset,c,nb0..nb23  #FORECAST,<144 hex chars>
"""
import os, subprocess, math
import numpy as np
from hg_guardian_py import Guardian, F, isnan

HERE = os.path.dirname(os.path.abspath(__file__))
C_DIR = os.path.join(HERE, "..", "c")
HOST = os.environ.get("HG_HOST", os.path.join(C_DIR, "build", "host_test"))
SCALARS = ["mod", "t1", "t2", "tair", "rh", "hr", "hrq", "pi", "astd", "apeak", "dc", "flat", "button", "charging", "vbat", "ble", "force_worn", "cmd"]
OUTCOLS = (["row", "state", "level", "family_alert", "alarm_id", "check_reason", "check_min", "haptic", "screen", "worn", "home_out",
            "routine_score", "why", "tiers", "routine_req", "imok_resp_min", "notify_not_worn",
            "core_now", "core_20", "sd_now", "f20_eff", "logit_p38", "logit_p385", "strain", "kf", "core_flux", "core_30",
            "flux_valid", "hr_valid", "valid", "v12_est", "v12_f20", "v12_z", "t_air_corr", "env_run", "env_dose", "status"]
           + ["x%d" % i for i in range(32)] + ["nn%d" % i for i in range(6)] + ["nsd%d" % i for i in range(6)] + ["night_heat", "nudge"])
INTCOLS = OUTCOLS[:17] + ["flux_valid", "hr_valid", "valid", "env_run", "env_dose", "night_heat", "nudge"]

def default_profile(): return dict(age=75.0, sex_m=0.0, bmi=26.0, med_flags=0)
def default_twin(): return dict(rest_hr=70.0, k_person=0.12, core_offset=0.0, c_bodyheat=0.15, t1_night_base=[float("nan")] * 24)

def minute(mod=0xFFFF, t1=float("nan"), t2=float("nan"), tair=float("nan"), rh=float("nan"), hr=float("nan"), hrq=4,
           pi=float("nan"), astd=0.0, apeak=1.0, dc=0, flat=0, button=0, charging=0, vbat=4.0, ble=-1, force_worn=0xFF, cmd=None,
           t1_5s=None, t2_5s=None, tair_5s=None, zang=None, forecast=None, expect=-1):
    m = dict(mod=mod, t1=t1, t2=t2, tair=tair, rh=rh, hr=hr, hrq=hrq, pi=pi, astd=astd, apeak=apeak, dc=dc, flat=flat, button=button,
             charging=charging, vbat=vbat, ble=ble, force_worn=force_worn, cmd=cmd, expect=expect)
    m["t1_5s"] = list(t1_5s) if t1_5s is not None else [t1] * 12
    m["t2_5s"] = list(t2_5s) if t2_5s is not None else [t2] * 12
    m["tair_5s"] = list(tair_5s) if tair_5s is not None else [tair] * 12
    m["zang"] = list(zang) if zang is not None else [float("nan")] * 12
    m["forecast"] = forecast
    return m

def _f(v):
    v = float(v)
    return "nan" if v != v else repr(float(np.float32(v)))

def write_csv(path, minutes, profile, twin, forecast=None, with_expect=False):
    with open(path, "w") as f:
        f.write("#PROFILE,%s,%s,%s,%d\n" % (_f(profile["age"]), _f(profile["sex_m"]), _f(profile["bmi"]), profile["med_flags"]))
        f.write("#TWIN," + ",".join(_f(twin[k]) for k in ("rest_hr", "k_person", "core_offset", "c_bodyheat"))
                + "," + ",".join(_f(v) for v in twin.get("t1_night_base", [float("nan")] * 24)) + "\n")
        if forecast is not None: f.write("#FORECAST,%s\n" % bytes(forecast).hex())
        f.write(",".join(SCALARS) + ",arrays..." + (",expect" if with_expect else "") + "\n")
        for m in minutes:
            vals = []
            for k in SCALARS:
                v = m[k]
                if k == "cmd": vals.append(v.hex() if v else "-")
                elif k in ("mod", "hrq", "dc", "flat", "button", "charging", "ble", "force_worn"): vals.append(str(int(v)))
                else: vals.append(_f(v))
            for k in ("t1_5s", "t2_5s", "tair_5s", "zang"): vals += [_f(v) for v in m[k]]
            if with_expect: vals += [str(int(m.get("expect", -1))), str(int(m.get("expect_worn", -1)))]
            f.write(",".join(vals) + "\n")

def run_c(inp, outp):
    subprocess.check_call([HOST, "replay", inp, outp])
    rows = []
    for line in open(outp):
        p = line.rstrip("\n").split(",")
        d = {}
        for k, v in zip(OUTCOLS, p):
            if k == "status": d[k] = v
            elif k in INTCOLS: d[k] = int(v)
            else: d[k] = float(v)
        rows.append(d)
    return rows

def run_py(minutes, profile, twin, forecast=None):
    g = Guardian(profile, twin)
    from hg_guardian_py import crc8
    fcbuf = bytearray(72) if forecast is None else bytearray(forecast); have = forecast is not None; mask = 0
    outs = []
    for m in minutes:
        if m["cmd"]:
            b = m["cmd"]
            if b[0] == 0x11 and len(b) >= 20 and crc8(b[:19]) == b[19]:
                ch = (b[3] >> 3) & 3
                if all(((b[3 + 3 * k] >> 3) & 3) == ch and not (b[3 + 3 * k] & 0xE0) for k in range(6)):
                    for k in range(6):
                        hh = ch * 6 + k; fcbuf[3 * hh] = b[1 + 3 * k]; fcbuf[3 * hh + 1] = b[2 + 3 * k]; fcbuf[3 * hh + 2] = b[3 + 3 * k] & 7
                    mask |= 1 << ch
                    if mask == 15: have = True
            else: g.cmd(b)
        mm = dict(m); mm["forecast"] = bytes(fcbuf) if have else None
        o = g.step(mm)
        outs.append(o)
    return outs

STATE_KEYS = ["state", "level", "family_alert", "alarm_id", "check_reason", "check_min", "haptic", "screen", "worn", "home_out",
              "routine_score", "why", "tiers", "routine_req", "imok_resp_min", "notify_not_worn", "night_heat", "nudge", "flux_valid", "hr_valid", "valid", "status"]
FLOAT_KEYS = ["core_now", "core_20", "core_30", "sd_now", "f20_eff", "strain", "kf", "core_flux", "logit_p38", "logit_p385"]

def compare(c_rows, py_outs):
    """returns dict: n, state_mismatch (count of minutes where any STATE_KEY differs), first mismatch, max float diffs."""
    n = min(len(c_rows), len(py_outs)); bad = 0; first = None
    fmax = {k: 0.0 for k in FLOAT_KEYS}; xmax = 0.0; nnmax = 0.0; auxmax = 0.0
    for i in range(n):
        c, p = c_rows[i], py_outs[i]
        pk = dict(p); pk["status"] = p["status"]
        diff = [k for k in STATE_KEYS if (c[k] != (pk.get(k) if k != "flux_valid" and k != "hr_valid" and k != "valid" else pk["core_" + k]))]
        if diff:
            bad += 1
            if first is None: first = (i, diff, {k: c[k] for k in diff}, {k: (pk.get(k) if k in pk else pk.get("core_" + k)) for k in diff})
        for k in FLOAT_KEYS:
            a, b = c[k], float(p[k] if k in p else p["core_" + k])
            if (a != a) != (b != b): fmax[k] = float("inf")
            elif a == a: fmax[k] = max(fmax[k], abs(a - b))
        ax = p["aux"]["x"]
        for j in range(32):
            a, b = c["x%d" % j], float(ax[j])
            if (a != a) != (b != b): xmax = float("inf")
            elif a == a: xmax = max(xmax, abs(a - b))
        for j in range(6): nnmax = max(nnmax, abs(c["nn%d" % j] - float(p["aux"]["nn_mean"][j])), abs(c["nsd%d" % j] - float(p["aux"]["nn_sd"][j])))
        for k in ("v12_est", "v12_f20", "v12_z", "t_air_corr"):
            a, b = c[k], float(p["aux"][k])
            if a == a and b == b: auxmax = max(auxmax, abs(a - b))
            elif (a != a) != (b != b): auxmax = float("inf")
    return dict(n=n, len_c=len(c_rows), len_py=len(py_outs), state_mismatch=bad, first=first, fmax=fmax, xmax=xmax, nnmax=nnmax, auxmax=auxmax)
