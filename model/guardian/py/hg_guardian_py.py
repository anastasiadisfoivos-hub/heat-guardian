"""Python mirror of guardian/c (hg_util, hg_kf, hg2_step, hg_contact, hg_homeout, hg_routine, hg_guardian, hg_frames).
Float32 operation for operation (numpy float32 scalars, same evaluation order as the C), so the per-minute state can be
compared with the C build bit for bit. Constants are loaded as the exact float32 bits the C compiler produced
(py/hg_consts.json from gen_consts.py; tables from hg_tables.json; stub weights from hg2_stub_weights.json).
B2: this file is the reference for the ARCH 4.1 feature semantics (class HG2, method step) until features.py exists.
"""
import json, os, math, struct
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
F = np.float32
NAN = F(np.nan)
np.seterr(all="ignore")

def _hx(h): return np.frombuffer(bytes.fromhex(h), "<f4")[0]
_CF = "hg_consts_stub.json" if os.environ.get("HG_WEIGHTS") == "stub" else "hg_consts.json"   # constants of the matching C build
_C = {k: np.frombuffer(bytes.fromhex(v), ">f4")[0].astype(np.float32) for k, v in json.load(open(os.path.join(HERE, _CF))).items()}  # C printed the u32 (big-endian hex)
def K(name): return _C[name]
def KI(name): return int(round(float(_C[name])))
def KA(name, n): return [_C["%s[%d]" % (name, i)] for i in range(n)]
_T = json.load(open(os.path.join(HERE, "hg_tables.json")))
PSAT = [_hx(h) for h in _T["psat"]]; SIG = [_hx(h) for h in _T["sig"]]; LNM = [_hx(h) for h in _T["lnm"]]
SINT = [_hx(h) for h in _T["sintod"]]; LN2 = K("HG_LN2")
A5, A15, A45, A30 = K("HG_EWM_A5"), K("HG_EWM_A15"), K("HG_EWM_A45"), K("HG_EWM_A30")

# M7 compile flags of the C build this mirror must match (set before constructing a Guardian)
FLAGS = dict(design=4, delta=None, m7r=1)   # M9 defaults (= C default build)   # design: HG_DRINK_DESIGN; delta: HG_A_DELTA (None = cfg default); m7r: HG_M7_ROUTINE
def isnan(x): return x != x
def popcount(v): return bin(v).count("1")

# ------------------------------------------------------------------ hg_util
def lerp_tab(tab, n, pos):
    i = int(pos) if not isnan(pos) else 0
    if pos < 0: i = 0
    if i > n - 2: i = n - 2
    fr = F(pos - F(i))
    return F(tab[i] + F(F(tab[i + 1] - tab[i]) * fr))
def psat(t):
    pos = F(F(t) - F(20)); i = int(pos) if not isnan(pos) else 0
    if pos < 0: i = 0
    if i > 23: i = 23
    fr = F(pos - F(i)); a, b, c = PSAT[i], PSAT[i + 1], PSAT[i + 2]
    return F(F(a + F(fr * F(b - a))) + F(F(F(fr * F(fr - F(1))) * F(0.5)) * F(F(c - b) - F(b - a))))
def pa_kpa(t, rh): return F(F(F(rh) * F(0.01)) * psat(t))
def sigmoid_lut(z):
    if z <= -8: return SIG[0]
    if z >= 8: return SIG[32]
    return lerp_tab(SIG, 33, F(F(z + F(8)) * F(2)))
def ln1p(x):
    if not (x > 0): return F(0)
    y = F(F(1) + F(x)); e = 0
    while y >= 2 and e < 64: y = F(y * F(0.5)); e += 1
    return F(F(F(e) * LN2) + lerp_tab(LNM, 33, F(F(y - F(1)) * F(32))))
def sin_tod(m):
    m = m % 1440; i = m // 15; fr = F(F(m % 15) / F(15))
    return F(SINT[i] + F(F(SINT[i + 1] - SINT[i]) * fr))
def cos_tod(m): return sin_tod((m % 1440) + 360)
def clampf(x, lo, hi): return lo if x < lo else (hi if x > hi else x)
def guard(v, lo, hi):   # [B2-fix] hg2_guard_f: out of range / NaN / inf -> NAN
    v = F(v); return v if (v >= F(lo) and v <= F(hi)) else NAN
def gclamp(x, lo, hi):  # [B2-fix] hg2_clampf (NaN -> lo)
    lo, hi = F(lo), F(hi); return lo if not (x >= lo) else (hi if x > hi else x)

# ------------------------------------------------------------------ hg_kf (v1.2 port)
KF_A, KF_G, KF_B0, KF_B1, KF_B2, KF_S = K("HG_KF_A"), K("HG_KF_GAMMA"), K("HG_KF_B0"), K("HG_KF_B1"), K("HG_KF_B2"), K("HG_KF_SIGMA")
NOWI, F20I = K("HG_NOW_INTERCEPT"), K("HG_F20_INTERCEPT")
NOWC, F20C = KA("HG_NOW_COEF", 14), KA("HG_F20_COEF", 14)
DGB, DGW, SDC = K("HG_DG_B"), KA("HG_DG_W", 7), KA("HG_SD_C", 4)

class KF:
    def __init__(s, age, male, bmi, rest_hr, flags):
        s.age, s.sex_m, s.bmi, s.rest_hr, s.flags = F(age), F(1 if male else 0), F(bmi), F(rest_hr), flags
        s.hrmax = F(K("HG_HRMAX_BB_A") - F(K("HG_HRMAX_B") * s.age)) if flags & 1 else F(K("HG_HRMAX_A") - F(K("HG_HRMAX_B") * s.age))
        s.ct, s.v = K("HG_KF_CT0"), K("HG_KF_V0")
        s.e5 = s.e15 = s.e45 = s.rest_hr
        s.hrbuf = []; s.kfring = [F(0)] * 16; s.estring = [F(0)] * 11
        s.started_k = s.started_e = False; s.ki = s.ei = 0; s.w60 = 0; s.last_hr = s.rest_hr
        s.rh_clamp = True   # M1.2
    @staticmethod
    def med3(b):
        if len(b) == 1: return b[0]
        if len(b) == 2: return F(F(0.5) * F(b[0] + b[1]))
        a, c, d = b
        if a > c: a, c = c, a
        if c > d: c = d
        return a if a > c else c
    def step(s, hr, amb, rh):
        hr = F(hr); amb = F(amb); rh = F(rh)
        if not (hr >= 30 and hr <= 220): hr = s.last_hr
        s.last_hr = hr
        ctp = F(KF_A * s.ct); vp = F(F(F(KF_A * KF_A) * s.v) + F(KF_G * KF_G))
        c = F(F(F(F(2) * KF_B2) * ctp) + KF_B1)
        k = F(F(vp * c) / F(F(F(c * c) * vp) + F(KF_S * KF_S)))
        hrp = F(F(F(F(KF_B2 * ctp) * ctp) + F(KF_B1 * ctp)) + KF_B0)
        s.ct = F(ctp + F(k * F(F(hr - F(s.rest_hr - F(70))) - hrp)))
        s.v = F(F(F(1) - F(k * c)) * vp)
        if len(s.hrbuf) < 3: s.hrbuf.append(hr)
        else: s.hrbuf = [s.hrbuf[1], s.hrbuf[2], hr]
        s.e5 = F(s.e5 + F(A5 * F(hr - s.e5))); s.e15 = F(s.e15 + F(A15 * F(hr - s.e15))); s.e45 = F(s.e45 + F(A45 * F(hr - s.e45)))
        if not s.started_k: s.kfring = [s.ct] * 16; s.started_k = True
        s.kfring[s.ki] = s.ct; kf15 = s.kfring[(s.ki + 1) % 16]; s.ki = (s.ki + 1) % 16
        amin, amax = K("HG_AGE_MIN"), K("HG_AGE_MAX")
        age_c = amin if s.age < amin else (amax if s.age > amax else s.age)
        x = [F(0)] * 14
        x[0] = KF.med3(s.hrbuf); x[1] = s.e5; x[2] = s.e15; x[3] = s.e45
        x[4] = F(s.e5 - s.rest_hr); x[5] = F(F(s.e5 - s.rest_hr) / F(s.hrmax - s.rest_hr)); x[6] = F(s.e5 - s.e45)
        rh_lin = rh   # M1.2: RH clamped to the v1.2 training range inside the linear correction only
        if s.rh_clamp: rh_lin = K("HG_KF_RH_MIN") if rh < K("HG_KF_RH_MIN") else (K("HG_KF_RH_MAX") if rh > K("HG_KF_RH_MAX") else rh)
        x[7] = amb; x[8] = rh_lin; x[9] = age_c; x[10] = s.sex_m; x[11] = s.bmi; x[12] = s.ct; x[13] = F(s.ct - kf15)
        est = F(s.ct + NOWI); f20 = F(s.ct + F20I)
        for i in range(14):
            est = F(est + F(NOWC[i] * x[i])); f20 = F(f20 + F(F20C[i] * x[i]))
        sh = K("HG_OLDER_DANGER_SHIFT") if s.age >= 65 else F(0)
        es = F(est + sh); fs = F(f20 + sh)
        if not s.started_e: s.estring = [es] * 11; s.started_e = True
        s.estring[s.ei] = es; est10 = s.estring[(s.ei + 1) % 11]; s.ei = (s.ei + 1) % 11
        s.w60 = ((s.w60 << 1) | (1 if fs >= K("HG_T_DRINK_WATER") else 0)) & ((1 << 60) - 1)
        warn60 = F(F(popcount(s.w60)) / F(60))
        d = [es, F(fs - es), F(es - est10), warn60, x[4], x[5], amb]
        z = DGB
        for i in range(7): z = F(z + F(DGW[i] * d[i]))
        sd = F(F(1.2533141) * F(F(F(SDC[0] + F(SDC[1] * est)) + F(SDC[2] * x[5])) + F(SDC[3] * warn60)))
        return dict(est=est, f20=f20, z=z, sd=(F(0.08) if sd < F(0.08) else sd), kf=s.ct, hr_reserve=x[5], warn60=warn60)

class V12Tiers:
    """port of the v1.2 tier logic (comparison harness only)"""
    def __init__(t, age, f):
        m = K("HG_OLDER_WATCH_MARGIN") if age >= 65 else F(0)
        t.m_drink = m; t.m_cool = m
        if f & (2 | 8): t.m_drink = F(t.m_drink + K("HG_DIURETIC_DRINK_MARGIN"))
        if f & 4: t.m_drink = F(t.m_drink + K("HG_LOW_SWEAT_WATCH_MARGIN")); t.m_cool = F(t.m_cool + K("HG_LOW_SWEAT_WATCH_MARGIN"))
        if f & 1: t.m_drink = F(t.m_drink + K("HG_BB_WATCH_MARGIN")); t.m_cool = F(t.m_cool + K("HG_BB_WATCH_MARGIN"))
        older = age >= 65 or f != 0
        t.lim_a = K("HG_LIM_OLD_A") if older else K("HG_LIM_YOUNG_A"); t.lim_b = K("HG_LIM_OLD_B") if older else K("HG_LIM_YOUNG_B")
        t.r = [0, 0, 0]; t.on = [0, 0, 0]; t.off = [0, 0, 0]; t.env_run = t.env_dose = t.still_run = t.cool_min = 0; t.cool_ack = 0

# ------------------------------------------------------------------ tiers helper (v1.2 tier())
class Tier:
    def __init__(t): t.run = 0; t.on = 0; t.off = 0
    def step(t, cond, k=2):
        t.run = min(t.run + 1, 255) if cond else 0
        if t.run >= k: t.on = 1; t.off = 0
        elif t.on:
            if cond: t.off = 0
            else:
                t.off += 1
                if t.off >= KI("HG_HOLD_MIN"): t.on = 0
        return t.on

# ------------------------------------------------------------------ hg2
B2_EXPORT = "/home/claude/hg_ai/model/export/hg2_weights.json"
def default_weights_path():
    """same rule as c/Makefile: B2's trained export wins when it exists, else the STUB"""
    if os.environ.get("HG_WEIGHTS") == "stub": return os.path.join(HERE, "hg2_stub_weights.json")
    return B2_EXPORT if os.path.exists(os.path.join(os.path.dirname(B2_EXPORT), "hg2_weights.h")) else os.path.join(HERE, "hg2_stub_weights.json")
class Weights:
    def __init__(w, path=None):
        j = json.load(open(path or default_weights_path()))
        nout = len(bytes.fromhex(j["members"][0][5])) // 4          # 6 (stub / M5) or 9 (M11: + 3 sd heads)
        shapes = [(24, 32), (24,), (16, 24), (16,), (nout, 16), (nout,)]
        w.members = [[np.frombuffer(bytes.fromhex(h), "<f4").reshape(sh).astype(F) for h, sh in zip(m, shapes)] for m in j["members"]]
        w.nout = nout
        w.xm = np.frombuffer(bytes.fromhex(j["xm"]), "<f4"); w.xs = np.frombuffer(bytes.fromhex(j["xs"]), "<f4")
        w.ym = np.frombuffer(bytes.fromhex(j["ym"]), "<f4"); w.ys = np.frombuffer(bytes.fromhex(j["ys"]), "<f4")
        w.stub = bool(j.get("stub", True)); w.cut38 = F(j.get("cut38", 1.0e9)); w.cut385 = F(j.get("cut385", 1.0e9)); w.crc = j["crc32"]
        w.version = j.get("version", "stub")
WEIGHTS = None
def _dense(W, b, x, relu):
    P = (W * x[None, :]).astype(F)            # exact float32 products
    acc = b.astype(F).copy()
    for i in range(W.shape[1]): acc = (acc + P[:, i]).astype(F)   # sequential accumulation, same order as the C loop
    if relu: acc = np.where(acc < 0, F(0), acc).astype(F)
    return acc
def ensemble(z, W):
    n = W.nout; s = np.zeros(n, F); s2 = np.zeros(n, F); a = [F(0), F(0), F(0)]
    for m in W.members:
        h1 = _dense(m[0], m[1], z, True); h2 = _dense(m[2], m[3], h1, True); y = _dense(m[4], m[5], h2, False)
        s = (s + y).astype(F); s2 = (s2 + (y * y).astype(F)).astype(F)
        if n == 9:
            for o in range(3): a[o] = F(a[o] + F(F(y[6 + o] * y[6 + o]) + K("HG2_EPS_V_EFF")))
    mu = (s / F(5)).astype(F); var = ((s2 / F(5)).astype(F) - (mu * mu).astype(F)).astype(F)
    sd = np.where(var > 0, np.sqrt(np.maximum(var, F(0))).astype(F), F(0)).astype(F)
    ale = [F(x / F(5)) for x in a]
    return mu, sd, ale

class HG2:
    def __init__(s, prof, twin, weights=None):
        global WEIGHTS
        if weights is None:
            if WEIGHTS is None: WEIGHTS = Weights()
            weights = WEIGHTS
        s.W = weights
        s.kf = KF(prof["age"], prof["sex_m"] > 0.5, prof["bmi"], twin["rest_hr"], prof["med_flags"])
        s.age, s.sex_m, s.bmi, s.hrmax, s.med_flags = F(prof["age"]), F(prof["sex_m"]), F(prof["bmi"]), s.kf.hrmax, prof["med_flags"]
        s.older_env = prof["age"] >= 65 or prof["med_flags"] != 0
        s.set_twin(twin)
        s.hr_last = F(twin["rest_hr"]); s.hr_e5 = s.hr_last; s.hr_e45 = s.hr_last; s.act_e30 = F(0)
        s.t1_last = s.tair_last = s.rh_last = NAN
        s.ring_t1 = [NAN] * 16; s.ring_tair = [NAN] * 16; s.ring_dt = [F(0)] * 11
        s.act_hist = 0; s.min_since_active = 0; s.min_since_don = 0; s.env_run = 0; s.env_dose = 0
        s.hr_age = 0; s.hr_q_hist = 0; s.ri16 = 0; s.ri11 = 0; s.started = False; s.last_worn = 0
    def set_twin(s, tw):
        s.rest_hr, s.k_person, s.core_offset, s.c_bodyheat = F(tw["rest_hr"]), F(tw["k_person"]), F(tw["core_offset"]), F(tw["c_bodyheat"])
        nb = tw.get("t1_night_base", [np.nan] * 24); s.t1nb = []
        for b in nb:
            b = F(b)
            s.t1nb.append(int(math.floor(F(F(b * F(100)) + F(0.5)))) if (b == b and b > 0 and b < 60) else None)
        s.kf.rest_hr = s.rest_hr
    def step(s, i):
        """i: dict t1,t2,tair,rh,hr,hrq,pi,astd,worn,mod. Returns (out, aux)."""
        x = [F(0)] * 32
        worn = i["worn"]
        if worn == 2:
            if s.last_worn != 2: s.min_since_don = 0
            elif s.min_since_don < 60: s.min_since_don += 1
        else: s.min_since_don = 0
        s.last_worn = worn
        t1in, t2, ta_in, rh_in = guard(i["t1"], -40, 85), guard(i["t2"], -40, 85), guard(i["tair"], -40, 85), guard(i["rh"], 0, 100)   # [B2-fix]
        if worn != 0 and not isnan(t1in): s.t1_last = t1in
        t1 = s.t1_last; t1ok = not isnan(t1)
        if not isnan(ta_in): s.tair_last = ta_in
        if not isnan(rh_in): s.rh_last = rh_in
        traw, rh = s.tair_last, s.rh_last
        tair = traw
        if not isnan(traw) and t1ok: tair = F(traw - F(s.c_bodyheat * F(t1 - traw)))
        tairok = not isnan(tair)
        flux_valid = (worn == 2 and t1ok and not isnan(t2) and tairok and F(t1 - t2) > F(0.15) and tair < F(t1 - F(0.5))
                      and s.min_since_don >= KI("HG_DON_BLANK_MIN"))
        dT = F(t1 - t2) if flux_valid else F(0)
        if not s.started:
            s.ring_t1 = [t1] * 16; s.ring_tair = [tair] * 16; s.ring_dt = [dT] * 11; s.started = True
        s.ring_t1[s.ri16] = t1; s.ring_tair[s.ri16] = tair; s.ring_dt[s.ri11] = dT
        t1_5, t1_15 = s.ring_t1[(s.ri16 + 11) % 16], s.ring_t1[(s.ri16 + 1) % 16]
        ta_15, dt_10 = s.ring_tair[(s.ri16 + 1) % 16], s.ring_dt[(s.ri11 + 1) % 11]
        s.ri16 = (s.ri16 + 1) % 16; s.ri11 = (s.ri11 + 1) % 11
        x[0] = t1
        x[1] = F(t1 - t1_5) if (t1ok and not isnan(t1_5)) else F(0)
        x[2] = F(t1 - t1_15) if (t1ok and not isnan(t1_15)) else F(0)
        x[3] = dT; x[4] = F(dT - dt_10) if flux_valid else F(0); x[5] = F(1) if flux_valid else F(0)
        x[6] = tair; x[7] = F(tair - ta_15) if (tairok and not isnan(ta_15)) else F(0); x[8] = rh
        x[9] = F(t1 - tair) if (t1ok and tairok) else NAN
        hr_in = F(i["hr"]); hr_in = hr_in if np.isfinite(hr_in) else NAN   # [B2-fix]
        hr_good = i["hrq"] == 4 and hr_in >= 30 and hr_in <= 220
        if hr_good: s.hr_last = hr_in; s.hr_age = 0
        elif s.hr_age < 255: s.hr_age += 1
        s.hr_q_hist = ((s.hr_q_hist << 1) | (1 if hr_good else 0)) & 0x1F
        hr_valid = popcount(s.hr_q_hist) >= 3
        hr = s.hr_last
        s.hr_e5 = F(s.hr_e5 + F(A5 * F(hr - s.hr_e5))); s.hr_e45 = F(s.hr_e45 + F(A45 * F(hr - s.hr_e45)))
        x[10] = hr; x[11] = s.hr_e5; x[12] = s.hr_e45; x[13] = F(hr - s.rest_hr)
        x[14] = F(F(hr - s.rest_hr) / F(s.hrmax - s.rest_hr)); x[15] = F(1) if hr_valid else F(0)
        pi = guard(i["pi"], 0, 100); x[16] = ln1p(pi) if not isnan(pi) else F(0)
        astd = guard(i["astd"], 0, 16); astd = F(0) if isnan(astd) else astd
        act = ln1p(F(F(100) * astd))
        s.act_e30 = F(s.act_e30 + F(A30 * F(act - s.act_e30)))
        active = astd > K("HG_ACTIVE_G")
        if active: s.min_since_active = 0
        elif s.min_since_active < 240: s.min_since_active += 1
        s.act_hist = ((s.act_hist << 1) | (1 if active else 0)) & 0xFFFFFFFF
        active30 = popcount(s.act_hist & 0x3FFFFFFF)
        x[17] = act; x[18] = s.act_e30; x[19] = F(F(s.min_since_active) / F(240))
        ko = s.kf.step(hr_in if hr_good else NAN, tair if tairok else F(25), rh if not isnan(rh) else F(50))
        x[20] = ko["kf"]
        above = False; above_old = False; pa = NAN; lim = NAN
        if tairok and not isnan(rh):
            if active30 >= KI("HG_ENV_ACT_MIN"): ao, bo = K("HG_LIM_OLD_ADL_A"), K("HG_LIM_OLD_ADL_B")
            else: ao, bo = K("HG_LIM_OLD_REST_A"), K("HG_LIM_OLD_REST_B")
            if not s.older_env: a, b = K("HG_LIM_YOUNG_A"), K("HG_LIM_YOUNG_B")
            else: a, b = ao, bo
            pa = pa_kpa(tair, rh); lim = F(a + F(b * tair)); above = pa >= lim
            above_old = pa >= F(ao + F(bo * tair))   # M12
        s.env_run = (s.env_run + 1 if s.env_run < 30000 else s.env_run) if above else 0
        if above:
            if s.env_dose < KI("HG_ENV_DOSE_CAP"): s.env_dose += 1
        elif s.env_dose > 0: s.env_dose -= 1
        x[21] = F(F(s.env_dose) / F(240)); x[22] = F(F(s.min_since_don) / F(60))
        mod = i["mod"]; tknown = mod < 1440
        x[23] = sin_tod(mod) if tknown else F(0); x[24] = cos_tod(mod) if tknown else F(0)
        core_flux = t1
        if flux_valid: core_flux = clampf(F(t1 + F(s.k_person * dT)), t1, F(t1 + F(2.5)))
        x[25] = core_flux
        t1a = F(0)
        if tknown and t1ok:
            b = s.t1nb[mod // 60]
            if b is not None: t1a = F(t1 - F(F(b) / F(100)))
        x[26] = t1a
        x[27] = F(s.age / F(100)); x[28] = s.sex_m; x[29] = F(s.bmi / F(30))
        x[30] = F(1) if s.med_flags & 1 else F(0); x[31] = F(1) if s.med_flags & 4 else F(0)
        xa = np.array(x, F)
        with np.errstate(invalid="ignore", over="ignore"):
            z = np.where(np.isnan(xa), F(0), ((xa - s.W.xm).astype(F) / s.W.xs).astype(F)).astype(F)
            z = np.where(np.isfinite(z), z, F(0)).astype(F)   # [B2-fix] z guard
        mean, sd, ale = ensemble(z, s.W)
        off = s.core_offset
        o = {}
        if s.W.stub:
            o["core_now"] = F(ko["est"] + off); o["core_20"] = F(ko["f20"] + off); o["core_30"] = F(ko["f20"] + off)
            o["sd_now"] = ko["sd"]; o["sd_20"] = F(0); o["sd_30"] = F(0); o["logit_p38"] = F(-100); o["logit_p385"] = F(-100)
            T0, TM = K("HG_PSI_T0"), K("HG_PSI_TMAX")
            psi = F(F(F(F(5) * F(ko["est"] - T0)) / F(TM - T0)) + F(F(F(5) * F(hr - s.rest_hr)) / F(s.hrmax - s.rest_hr)))
            o["strain"] = clampf(psi, F(0), F(10))
        else:
            ym, ys = s.W.ym, s.W.ys
            o["core_now"] = F(F(F(mean[0] * ys[0]) + ym[0]) + off); o["core_20"] = F(F(F(mean[1] * ys[1]) + ym[1]) + off)
            o["core_30"] = F(F(F(mean[2] * ys[2]) + ym[2]) + off)
            if s.W.nout == 9:   # M11 sd rule
                tot = [F(np.sqrt(F(ale[o] + F(sd[o] * sd[o])))) for o in range(3)]
            else: tot = [sd[0], sd[1], sd[2]]
            o["sd_now"] = F(tot[0] * ys[0]); o["sd_20"] = F(tot[1] * ys[1]); o["sd_30"] = F(tot[2] * ys[2])
            o["logit_p38"] = mean[3]; o["logit_p385"] = mean[4]; o["strain"] = clampf(mean[5], F(0), F(10))
            for k_, lo_, hi_ in (("core_now", 30, 45), ("core_20", 30, 45), ("core_30", 30, 45), ("sd_now", 0, 3), ("sd_20", 0, 3),
                                 ("sd_30", 0, 3), ("logit_p38", -100, 100), ("logit_p385", -100, 100)):
                o[k_] = gclamp(o[k_], lo_, hi_)   # [B2-fix] bounded outputs
        if not s.W.stub and KI("HG_B2B"):   # B2b AR (model/b2b/residual.py; C: hg2_step.c, hg_guardian_cfg.h HG_AR_*)
            w = F(1) if (t1ok and tairok and worn == 2 and s.min_since_don >= KI("HG_DON_BLANK_MIN")) else F(0)
            if w > 0:
                n_ = KI("HG_AR_ENV_N"); EA, EL, EH = KA("HG_AR_ENV_AIR", n_), KA("HG_AR_ENV_LO", n_), KA("HG_AR_ENV_HI", n_)
                a_ = EA[0] if tair < EA[0] else (EA[n_ - 1] if tair > EA[n_ - 1] else tair); lo_, hi_ = EL[n_ - 1], EH[n_ - 1]
                for k in range(n_ - 1):
                    if a_ <= EA[k + 1]:
                        f_ = F(F(a_ - EA[k]) / F(EA[k + 1] - EA[k]))
                        lo_ = F(EL[k] + F(f_ * F(EL[k + 1] - EL[k]))); hi_ = F(EH[k] + F(f_ * F(EH[k + 1] - EH[k]))); break
                d_ = F(t1 - tair); ov = F(lo_ - d_)
                if F(d_ - hi_) > ov: ov = F(d_ - hi_)
                if ov < 0: ov = F(0)
                w = F(w * clampf(F(F(1) - F(ov / K("HG_AR_RAMP"))), F(0), F(1)))
            if x[14] > K("HG_OOD_RESERVE") or x[10] > K("HG_OOD_HR"): w = F(0)
            rd, ru = K("HG_AR_R_DOWN"), K("HG_AR_R_UP")
            nn0, nn1, nn2 = F(o["core_now"] - off), F(o["core_20"] - off), F(o["core_30"] - off)
            r0 = clampf(F(nn0 - ko["est"]), -rd, ru); r1 = clampf(F(nn1 - ko["f20"]), -rd, ru); r2 = clampf(F(nn2 - ko["f20"]), -rd, ru)
            ar1 = gclamp(F(ko["f20"] + F(w * r1)), 30, 45)
            o["core_now"] = F(gclamp(F(ko["est"] + F(w * r0)), 30, 45) + off); o["core_20"] = F(ar1 + off)
            o["core_30"] = F(gclamp(F(ko["f20"] + F(w * r2)), 30, 45) + off)
            s.ar_c20 = ar1; s.ar_w = w
        else:
            s.ar_c20 = None
        o["f20_eff"] = o["core_20"]; o["f30_eff"] = o["core_30"]   # M5.1
        o["kf"] = ko["kf"]; o["core_flux"] = core_flux if flux_valid else NAN
        o["flux_valid"] = int(flux_valid); o["hr_valid"] = int(hr_valid)
        o["valid"] = int(worn == 2 and s.min_since_don >= KI("HG_DON_VALID_MIN"))
        o["why"] = ((1 if above else 0) | (2 if s.env_dose >= KI("HG_ENV_COOL_DOSE_MIN") else 0)
                    | (8 if ko["z"] >= K("HG_DG_LOGIT_CUT_V12") else 0) | (16 if o["f20_eff"] >= K("HG_T_DRINK") else 0)
                    | (32 if (o["logit_p38"] >= s.W.cut38 or o["logit_p385"] >= s.W.cut385) else 0))
        c20n = ko["f20"] if s.W.stub else gclamp(F(F(mean[1] * s.W.ys[1]) + s.W.ym[1]), 30, 45)   # M4.3 (+ [B2-fix] clamp)
        if s.ar_c20 is not None: c20n = s.ar_c20   # B2b AR
        aux = dict(core20_noff=c20n, x=xa, nn_mean=mean[:6], nn_sd=sd[:6], v12_est=ko["est"], v12_f20=ko["f20"], v12_z=ko["z"], v12_sd=ko["sd"],
                   t_air_corr=tair, env_run=s.env_run, env_dose=s.env_dose, env_above=int(above), env_above_old=int(above_old), active=int(active),
                   still=int(astd <= K("HG_STILL_G")), active30=active30)
        return o, aux

# ------------------------------------------------------------------ hg_contact
class Contact:
    R = 120
    def __init__(c):
        c.t1 = [NAN] * 120; c.t2 = [NAN] * 120; c.ta = [NAN] * 120; c.ratio = [NAN] * 30
        c.t1_ref = NAN; c.dc = [0, 0, 0]; c.ri = 0; c.n5 = 0; c.rti = 0; c.out = 0; c.cand = 0; c.cand_run = 0; c.latch = 0; c.reason = 0
    def mean12(c, r, back):
        s = F(0); n = 0
        for k in range(12):
            v = r[(c.ri - 1 - back - k + 480) % 120]
            if not isnan(v): s = F(s + v); n += 1
        return F(s / F(n)) if n else NAN
    def at(c, r, back): return r[(c.ri - 1 - back + 480) % 120]
    @staticmethod
    def median30(v):
        a = sorted(x for x in v if not isnan(x)); n = len(a)
        if n == 0: return NAN
        return a[n // 2] if n & 1 else F(F(0.5) * F(a[n // 2 - 1] + a[n // 2]))
    def step(c, t1s, t2s, tas, pi, ppg_q, dc, astd, flat, charging):
        for k in range(12):
            c.t1[c.ri] = F(t1s[k]); c.t2[c.ri] = F(t2s[k]) if t2s is not None else NAN; c.ta[c.ri] = F(tas[k]); c.ri = (c.ri + 1) % 120
        if c.n5 < 1000: c.n5 += 12
        t1m, t2m, tam = c.mean12(c.t1, 0), c.mean12(c.t2, 0), c.mean12(c.ta, 0)
        t1ok, t2ok, taok = not isnan(t1m), not isnan(t2m), not isnan(tam)
        hot = taok and tam >= K("HG_CT_HOT_C"); thermal = t1ok and taok and not hot
        c.dc = [dc, c.dc[0], c.dc[1]]
        r_now = NAN
        if thermal and t2ok and F(t1m - tam) > K("HG_CT_RATIO_DEN_MIN"): r_now = F(F(t1m - t2m) / F(t1m - tam))
        r_med = Contact.median30(c.ratio)
        c.ratio[c.rti] = r_now; c.rti = (c.rti + 1) % 30
        nratio = sum(1 for v in c.ratio if not isnan(v))
        reason = 128 if hot else 0; cand = 2; off = False
        if charging: off = True; reason |= 1
        if dc != 0 and dc < KI("HG_CT_DC_NOSKIN"): off = True; reason |= 2
        if flat >= KI("HG_CT_FLAT_MIN"):
            t1_10 = c.mean12(c.t1, 108) if c.n5 >= 120 else NAN
            falling = t1ok and not isnan(t1_10) and t1m < F(t1_10 - K("HG_CT_FALL_C"))
            if hot or falling: off = True; reason |= 4
        if thermal and tam < K("HG_CT_OFF_TAIR_MAX"):
            nr = K("HG_CT_OFF_NEAR_C")
            if t2ok:
                if abs(F(t1m - t2m)) < K("HG_CT_OFF_DT_C") and abs(F(t1m - tam)) <= nr and abs(F(t2m - tam)) <= nr: off = True; reason |= 8
            elif abs(F(t1m - tam)) <= nr: off = True; reason |= 8
        if off: cand = 0; c.latch = 0
        else:
            loose = False
            if thermal and c.n5 >= 24 + 3:
                now = F(0); anow = F(0); n = na = 0
                for k in range(3):
                    v, a = c.at(c.t1, k), c.at(c.ta, k)
                    if not isnan(v): now = F(now + v); n += 1
                    if not isnan(a): anow = F(anow + a); na += 1
                if n and na:
                    now = F(now / F(n)); anow = F(anow / F(na))
                    mx = F(-1000); amx = NAN
                    for k in range(3, 3 + 24):
                        v = c.at(c.t1, k)
                        if not isnan(v) and v > mx: mx = v; amx = c.at(c.ta, k)
                    drop = F(now - mx)
                    if mx > -999 and not isnan(amx) and drop <= K("HG_CT_STEP_C") and F(anow - amx) > F(K("HG_CT_AIR_MATCH") * drop):
                        loose = True; reason |= 16
                        if not c.latch: c.latch = 1; c.t1_ref = mx
            if c.latch:
                if (not thermal) or (t1ok and t1m >= F(c.t1_ref - K("HG_CT_RECOVER_C"))): c.latch = 0
                else: loose = True; reason |= 16
            if (not isnan(r_now)) and nratio >= KI("HG_CT_RATIO_MINN") and not isnan(r_med) and r_med > 0 and r_now < F(K("HG_CT_RATIO_DROP") * r_med):
                loose = True; reason |= 32
            pi = F(pi)
            if (not isnan(pi)) and pi < K("HG_CT_PI_LOOSE") and dc != 0 and c.dc[2] != 0 and F(dc) > F(K("HG_CT_DC_RISE") * F(c.dc[2])):
                loose = True; reason |= 64
            cand = 1 if loose else 2
        c.reason = reason
        if charging: c.out = 0; c.cand = 0; c.cand_run = 0; return c.out
        if cand == c.out: c.cand_run = 0; c.cand = cand
        else:
            if cand == c.cand: c.cand_run += 1
            else: c.cand = cand; c.cand_run = 1
            if c.cand_run >= KI("HG_CT_HYST_MIN"): c.out = cand; c.cand_run = 0
        return c.out

# ------------------------------------------------------------------ hg_homeout
def abs_humidity(t, rh): return F(F(F(2166.79) * pa_kpa(t, rh)) / F(F(t) + F(273.15)))
class HomeOut:
    def __init__(h):
        h.ta_stable = NAN; h.ah_stable = NAN; h.ta_hist = [NAN] * 6; h.score = 0; h.lost_min = 0; h.transit_min = 0
        h.state = 0; h.hi = 0; h.hn = 0; h.have_stable = 0; h.prior = [64] * 24; h.last_hour = 0xFF; h.out_min_hour = 0; h.mins_hour = 0
    def step(h, tair, rh, walking_min, ble, hour, fc):
        tair = F(tair); rh = F(rh); tok, rok = not isnan(tair), not isnan(rh)
        t5 = h.ta_hist[h.hi]; h.ta_hist[h.hi] = tair; h.hi = (h.hi + 1) % 6
        if h.hn < 6: h.hn += 1
        ah = abs_humidity(tair, rh) if (tok and rok) else NAN
        pts = 0
        if tok and h.have_stable:
            d = abs(F(tair - h.ta_stable))
            if d >= K("HG_HO_DT_C2"): pts += 5
            elif d >= K("HG_HO_DT_C1"): pts += 3
        if not isnan(ah) and h.have_stable and not isnan(h.ah_stable) and abs(F(ah - h.ah_stable)) >= K("HG_HO_DAH"): pts += 2
        if walking_min >= 3: pts += 2
        if ble == 0: h.lost_min = min(h.lost_min + 1, 60000) if h.lost_min < 60000 else h.lost_min
        else: h.lost_min = 0
        if ble == 0 and h.lost_min > 5: pts += 4
        elif ble == 1: pts += 1
        elif ble == 2: pts -= 2
        if hour < 24:
            if h.prior[hour] >= 128: pts += 1
            elif h.prior[hour] < 32: pts -= 1
        if fc is not None and hour < 24 and tok:
            tin = F(struct.unpack("b", bytes([fc[3 * hour]]))[0])
            if abs(F(tair - tin)) <= K("HG_HO_FC_NEAR_C"): pts -= 5
        if walking_min == 0 and pts <= 0: pts -= 1
        sc = h.score - int(math.trunc(h.score / 8)) + pts
        sc = max(-20, min(40, sc)); h.score = sc
        if h.state == 0:
            if walking_min >= 2 and sc >= 4: h.state = 1; h.transit_min = 0
        elif h.state == 1:
            h.transit_min += 1
            if sc >= 12: h.state = 2
            elif sc <= 0 or h.transit_min > 15: h.state = 0
        else:
            if sc < 8: h.state = 1; h.transit_min = 0
        if h.state == 0 and tok and h.hn >= 6 and not isnan(t5) and abs(F(tair - t5)) < K("HG_HO_STABLE_DT"):
            if not h.have_stable: h.ta_stable = tair; h.ah_stable = ah; h.have_stable = 1
            else:
                a = K("HG_HO_STABLE_A")
                h.ta_stable = F(h.ta_stable + F(a * F(tair - h.ta_stable)))
                if not isnan(ah): h.ah_stable = ah if isnan(h.ah_stable) else F(h.ah_stable + F(a * F(ah - h.ah_stable)))
        if hour < 24:
            if h.last_hour < 24 and hour != h.last_hour and h.mins_hour >= 30:
                frac = (255 * h.out_min_hour) // h.mins_hour
                h.prior[h.last_hour] = (h.prior[h.last_hour] * 7 + frac) // 8
            if hour != h.last_hour: h.out_min_hour = 0; h.mins_hour = 0; h.last_hour = hour
            if h.mins_hour < 255: h.mins_hour += 1
            if h.state == 2 and h.out_min_hour < 255: h.out_min_hour += 1
        return h.state

# ------------------------------------------------------------------ hg_routine
class Welford:
    __slots__ = ("n", "mean", "m2")
    def __init__(w): w.n = F(0); w.mean = F(0); w.m2 = F(0)
    def add(w, x):
        cap = F(KI("HG_RT_WELFORD_NCAP")); x = F(x)
        if w.n < cap: w.n = F(w.n + F(1))
        else: w.m2 = F(w.m2 * F(F(cap - F(1)) / cap))
        d = F(x - w.mean); w.mean = F(w.mean + F(d / w.n)); w.m2 = F(w.m2 + F(d * F(x - w.mean)))
    def sd(w): return F(np.sqrt(F(w.m2 / F(w.n - F(1))))) if w.n >= 2 else F(0)

def in_window(m, on, off): return (on <= m < off) if on <= off else (m >= on or m < off)
class Routine:
    def __init__(r):
        r.am = [Welford() for _ in range(24)]; r.q = [Welford() for _ in range(24)]; r.maxq = [0] * 24
        r.med5 = [255] * 288; r.med5_ok = [0] * 288; r.dz = []; r.last_z = NAN; r.wake_hist = [0] * 7
        r.sleep_on = KI("HG_RT_SLEEP_DEF_ON"); r.sleep_off = KI("HG_RT_SLEEP_DEF_OFF")
        r.qrun = 0; r.q_hour_max = 0; r.last_mod = 0xFFFF; r.act10 = 0; r.sleep_valid = 0; r.n_wake = 0; r.wake_i = 0
        r.days_learned = 0; r.block_ok = 0; r.block_idx = 0xFFFF; r.cur_hour = 0xFF; r.act_in_hour = 0; r.hour_minutes = 0
        r.hour_clean = 0; r.last_hour_act = 0; r.awake_today = 0; r.impact_pending = 0; r.score = 255; r.hdcza_thr = 0
        r.prev_asleep = 0; r.night_worn = 0; r.imp_still = 0   # T5 D5, M19-impact
    def median_wake(r):
        if r.n_wake == 0: return KI("HG_RT_W_DEFAULT")
        a = sorted(r.wake_hist[:r.n_wake]); return a[(r.n_wake - 1) // 2]
    def noon(r):
        order = [(c + 144) % 288 for c in range(288)]
        nok = sum(r.med5_ok[b] for b in order)
        if nok < KI("HG_HDCZA_MIN_WORN"): return
        k = (nok * 10 + 99) // 100
        vals = sorted(r.med5[b] for b in order if r.med5_ok[b]); p10 = vals[k - 1]
        thr = max(13, min(50, 15 * p10)); r.hdcza_thr = thr
        fl = [1 if (r.med5_ok[b] and r.med5[b] < thr) else 0 for b in order]
        c = 0
        while c < 288:
            if not fl[c]: c += 1; continue
            e = c
            while e < 288 and fl[e]: e += 1
            if e - c <= 6:
                for i in range(c, e): fl[i] = 0
            c = e
        c = 0
        while c < 288:
            if fl[c]: c += 1; continue
            e = c
            while e < 288 and not fl[e]: e += 1
            if c > 0 and e < 288 and (e - c) < 12:
                for i in range(c, e): fl[i] = 1
            c = e
        best, bs, c = 0, -1, 0
        while c < 288:
            if not fl[c]: c += 1; continue
            e = c
            while e < 288 and fl[e]: e += 1
            if e - c > best: best, bs = e - c, c
            c = e
        if bs < 0: return
        r.sleep_on = (((bs + 144) % 288) * 5) % 1440; r.sleep_off = (((bs + best + 144) % 288) * 5) % 1440; r.sleep_valid = 1
        r.wake_hist[r.wake_i] = r.sleep_off; r.wake_i = (r.wake_i + 1) % 7
        if r.n_wake < 7: r.n_wake += 1
        if r.days_learned < 255: r.days_learned += 1
    def step(r, mod, astd, zang, worn, frozen, heat_day, t_in, cool_on, impact, button=0):
        out = dict(req=0, asleep=0, thr=0, wake_deadline=0)
        if mod >= 1440:
            out["routine_score"] = 255; out["q"] = r.qrun; r.last_z = NAN; r.dz = []; r.block_ok = 0; r.block_idx = 0xFFFF
            r.cur_hour = 0xFF; r.impact_pending = 0; r.imp_still = 0; r.last_mod = 0xFFFF; return out
        worn = worn == 2
        astd = F(astd); astd = F(0) if isnan(astd) else astd
        active = astd > K("HG_ACTIVE_G"); still = astd <= K("HG_STILL_G")
        if r.last_mod != 0xFFFF and mod < r.last_mod and r.last_mod - mod >= KI("HG_MIDNIGHT_MIN_STEP"): r.awake_today = 0   # T5 m1
        if r.last_mod != 0xFFFF and r.last_mod < 720 and mod >= 720: r.noon()
        bi = mod // 5
        if bi != r.block_idx: r.block_idx = bi; r.dz = []; r.block_ok = 1
        if (not worn) or zang is None: r.block_ok = 0; r.last_z = NAN
        else:
            for z in zang:
                z = F(z)
                if not isnan(z) and not isnan(r.last_z) and len(r.dz) < 60:
                    d = F(F(abs(F(z - r.last_z)) * F(100)) + F(0.5))
                    r.dz.append(255 if d >= 255 else int(math.floor(d)))
                r.last_z = z
        if mod % 5 == 4:
            if r.block_ok and len(r.dz) >= 30:
                a = sorted(r.dz); r.med5[bi] = a[(len(a) - 1) // 2]; r.med5_ok[bi] = 1
            else: r.med5[bi] = 255; r.med5_ok[bi] = 0
            r.dz = []; r.block_ok = 0
        asleep = in_window(mod, r.sleep_on, r.sleep_off)
        if asleep and not r.prev_asleep: r.night_worn = 0   # T5 D5
        if asleep and worn and r.night_worn < 1440: r.night_worn += 1
        r.prev_asleep = 1 if asleep else 0
        quiet_off = asleep   # M9.3: M7.3 (ii) removed
        if active or quiet_off: r.qrun = 0
        elif worn and r.qrun < 1440: r.qrun += 1
        h = mod // 60
        if h != r.cur_hour:
            if r.cur_hour < 24 and r.hour_clean and r.hour_minutes >= 60:
                r.am[r.cur_hour].add(r.act_in_hour); r.q[r.cur_hour].add(r.q_hour_max)
                if r.q_hour_max > r.maxq[r.cur_hour]: r.maxq[r.cur_hour] = r.q_hour_max
            if r.cur_hour < 24:
                w = r.am[r.cur_hour]; sc = 255
                if (r.hour_minutes >= 60 and w.n >= KI("HG_RT_LEARN_DAYS") and w.mean >= K("HG_RT_ACTIVE_HOUR_MIN")
                        and not in_window(r.cur_hour * 60 + 30, r.sleep_on, r.sleep_off)):
                    sd = w.sd()
                    if sd < K("HG_RT_SD_FLOOR_AM"): sd = K("HG_RT_SD_FLOOR_AM")
                    zz = F(F(w.mean - F(r.act_in_hour)) / sd)
                    if zz > 0:
                        p = F(F(64) * zz); sc = 0 if p >= 255 else 255 - int(p)
                r.score = sc; r.last_hour_act = r.act_in_hour
            r.cur_hour = h; r.act_in_hour = 0; r.hour_minutes = 0; r.hour_clean = 1; r.q_hour_max = 0
        if r.hour_minutes < 255: r.hour_minutes += 1
        if active and r.act_in_hour < 255: r.act_in_hour += 1
        if r.qrun > r.q_hour_max: r.q_hour_max = r.qrun
        if (not worn) or frozen: r.hour_clean = 0
        r.act10 = ((r.act10 << 1) | (1 if active else 0)) & 0x3FF
        W = r.median_wake(); frm = W - KI("HG_RT_WAKE_LOOKBACK")
        if mod >= (0 if frm < 0 else frm) and popcount(r.act10) >= KI("HG_RT_WAKE_ACT"): r.awake_today = 1
        req = 0
        if worn:
            t_in = F(t_in)
            heat = ((not isnan(t_in)) and t_in >= K("HG_RT_HEAT_TIN")) or bool(cool_on)
            if not quiet_off:
                thr = -1
                if r.am[h].n >= KI("HG_RT_LEARN_DAYS"):
                    B = [60, 75, 90, 75, 60]
                    for d in range(-2, 3):
                        hh = (h + d + 24) % 24
                        if r.am[hh].n < KI("HG_RT_LEARN_DAYS"): continue
                        b = B[d + 2] // 2 if heat else B[d + 2]
                        thr = max(thr, r.maxq[hh] + b)
                else: thr = 90 if heat else 180
                out["thr"] = thr
                if r.qrun > thr: req |= 1
            D = W + (60 if heat_day else 120); D = min(D, 600); out["wake_deadline"] = D
            win = r.sleep_off - r.sleep_on if r.sleep_off >= r.sleep_on else 1440 - r.sleep_on + r.sleep_off
            night_seen = 100 * r.night_worn >= KI("HG_RT_NOWAKE_WORN_PCT") * win   # T5 D5
            if mod >= D and mod < 720 and not r.awake_today and night_seen: req |= 2
        if r.impact_pending:   # M19-impact rule (d): N still minutes, no press
            if (not worn) or (not still) or button: r.impact_pending = 0; r.imp_still = 0
            else:
                r.imp_still += 1
                if r.imp_still >= KI("HG_IMPACT_STILL_MIN"): req |= 4; r.impact_pending = 0; r.imp_still = 0
        if impact and worn: r.impact_pending = 1; r.imp_still = 0
        if req: r.hour_clean = 0
        r.last_mod = mod
        out.update(req=req, routine_score=r.score, asleep=int(asleep), q=r.qrun)
        return out

# ------------------------------------------------------------------ hg_frames
def crc8(b):
    c = 0
    for x in b:
        c ^= x
        for _ in range(8): c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c
def _rnd100(x): return int(math.floor(F(F(F(x) * F(100)) + F(0.5))))
def _i16c(t):
    t = F(t)
    if isnan(t) or t < -300 or t > 300: return 0x8000
    return _rnd100(t) & 0xFFFF
def _u8c(v, scale):
    v = F(v)
    if isnan(v) or v <= 0: return 0
    x = F(F(v * F(scale)) + F(0.5)); return 255 if x >= 255 else int(x)
def status_pack(s):
    o = bytearray(20)
    o[0] = 0x01 | (0x10 if s["family_pending"] else 0) | (0x20 if s["not_worn"] else 0)
    o[1] = (s["state_code"] & 7) | (8 if s["contact_ok"] else 0) | (16 if s["time_synced"] else 0) | (32 if s["charging"] else 0) \
        | (64 if s["home"] else 0) | (128 if s["ppg_valid"] else 0)
    c = 0 if isnan(F(s["core_c"])) else _rnd100(s["core_c"]); c = max(0, min(65535, c)); o[2:4] = struct.pack("<H", c)
    o[4] = _u8c(s["half_range_c"], 100); o[5] = _u8c(s["hr_bpm"], 1); o[6] = s["hr_q"]
    o[7:9] = struct.pack("<H", _i16c(s["t1_c"])); o[9:11] = struct.pack("<H", _i16c(s["t2_c"])); o[11:13] = struct.pack("<H", _i16c(s["tair_c"]))
    o[13] = 255 if isnan(F(s["rh_pct"])) else _u8c(s["rh_pct"], 1); o[14] = s["battery_pct"]
    if s["family_pending"]: o[15:17] = struct.pack("<H", s["alarm_id16"])
    else: o[15] = s["routine_score"]; o[16] = s["activity"]
    o[17:19] = struct.pack("<H", s["minute_counter"] & 0xFFFF); o[19] = crc8(o[:19])
    return bytes(o)
def status_unpack(b):
    """Phone-side decoder (also the round-trip test of hg_status_pack)."""
    assert len(b) == 20 and crc8(b[:19]) == b[19], "bad STATUS crc"
    i16 = lambda o: struct.unpack("<h", b[o:o + 2])[0]
    fam = bool(b[0] & 0x10)
    d = dict(version=b[0] & 0x0F, family_pending=fam, not_worn=bool(b[0] & 0x20), state_code=b[1] & 7, contact_ok=bool(b[1] & 8),
             time_synced=bool(b[1] & 16), charging=bool(b[1] & 32), home=bool(b[1] & 64), ppg_valid=bool(b[1] & 128),
             core_c=struct.unpack("<H", b[2:4])[0] / 100, half_range_c=b[4] / 100, hr_bpm=b[5], hr_q=b[6],
             t1_c=None if i16(7) == -32768 else i16(7) / 100, t2_c=None if i16(9) == -32768 else i16(9) / 100,
             tair_c=None if i16(11) == -32768 else i16(11) / 100, rh_pct=None if b[13] == 255 else b[13], battery_pct=b[14],
             minute_counter=struct.unpack("<H", b[17:19])[0])
    if fam: d["alarm_id16"] = struct.unpack("<H", b[15:17])[0]
    else: d["routine_score"] = b[15]; d["activity"] = b[16]
    return d
def cmd_frame(op, **kw):
    """Phone-side encoders (reference for B4's ble_frame.py)."""
    if op == 0x10: b = bytes([0x10]) + struct.pack("<Ib", kw["unix_s"], kw.get("tz_q", 8))
    elif op == 0x12: b = bytes([0x12, kw["ack_type"]]) + struct.pack("<I", kw["alarm_id"])
    elif op == 0x13: b = bytes([0x13, kw["field"]]) + struct.pack("<f", kw["value"])
    elif op == 0x11:
        ch = kw["chunk"]; b = bytes([0x11])
        for (t, rh, fl) in kw["hours"]: b += struct.pack("<bBB", t, rh, (fl & 7) | (ch << 3))
    elif op == 0x14:
        tag = kw.get("tag", "").encode("ascii")[:14].ljust(14, b"\0")
        b = bytes([0x14]) + struct.pack("<I", kw["bitmap"])[:3] + bytes([kw.get("plan_id", 0)]) + tag
    else: raise ValueError(op)
    return b + bytes([crc8(b)])

# ------------------------------------------------------------------ hg_guardian
CODE = [0, 1, 2, 6, 3, 4, 0, 5, 7]
class Guardian:
    def __init__(g, prof, twin, weights=None):
        g.prof = dict(prof); g.twin = dict(twin)
        g.hg2 = HG2(prof, twin, weights); g.ct = Contact(); g.ho = HomeOut(); g.rt = Routine()
        g.margins()
        g.ta_ring = [NAN] * 16; g.who_hist = 0; g.alarm_seq = 0; g.alarm_id = 0; g.help_id = 0
        g.drink, g.cool, g.danger, g.cool_p = Tier(), Tier(), Tier(), Tier()
        g.strain_run = g.still_run = g.cool_min = g.hr_bad_run = g.ac_latch = g.notworn_min = g.snooze = g.minute_counter = 0
        g.walk_run = 0; g.cool_ack = 0; g.level = 0; g.check_active = 0; g.check_cause = 0; g.check_t = 0; g.family_sent = 0
        g.family_pending = 0; g.help = 0; g.last_state = 0; g.tai = 0; g.started = 0; g.last_cause = 0; g.nudge_done = 0
        g.last_mod = 0xFFFF; g.reading_today = 0
        g.pd_cool_run = 0; g.pd_i = 0; g.pd_n = 0; g.pd_ring = [F(0)] * (KI("HG_PD_SLOPE_MIN") + 1)   # M13
        g.pdv_ring = [F(0)] * (KI("HG_PD_SLOPE_MIN") + 1)   # T5 D2: protected (v1.2) f20 ring
        g.mb_e10 = g.mb_e60 = g.mb_a30 = g.mb_a120 = g.mb_d = F(0); g.mb_age = 0; g.mb_warm = 255; g.mb_run = 0; g.mb_started = 0   # M19 Marble
        g.x_ring = [0] * KI("HG_X_W_N"); g.x_i = 0; g.x_wq = 0; g.x_prev = 0; g.drink_shown = 0; g.x_since = 65535; g.x_last = F(-9)   # M19 Exception
        g.x_c = g.x_sxx = g.x_sxy = g.x_dww = g.x_dwd = g.x_dw = F(0); g.x_dref = K("HG_X_DREF0")
        g.sf_t1 = K("HG_SF_T1_OFF"); g.sf_ta = K("HG_SF_TA_OFF"); g.sf_run = 0; g.x_warm = 255   # B5-v7
        g.a_hist = [0] * 100; g.a_n = 0; g.a_base = F(0); g.a_base_n = 0; g.b_prev_drink = 0; g.b_since = 65535; g.b_left = 0; g.b_last_f20 = F(0)
    def margins(g):
        prof = g.prof
        m = K("HG_M_OLDER") if prof["age"] >= 65 else F(0); g.m_drink = m; g.m_cool = m; f = prof["med_flags"]
        if f & (2 | 8): g.m_drink = F(g.m_drink + K("HG_M_DIURETIC_DRINK"))
        if f & 4: g.m_drink = F(g.m_drink + K("HG_M_LOW_SWEAT")); g.m_cool = F(g.m_cool + K("HG_M_LOW_SWEAT"))
        if f & 1: g.m_drink = F(g.m_drink + K("HG_M_BETA_BLOCKER")); g.m_cool = F(g.m_cool + K("HG_M_BETA_BLOCKER"))
    def new_alarm(g):
        g.alarm_seq += 1; return ((g.alarm_seq << 16) | (g.minute_counter & 0xFFFF)) & 0xFFFFFFFF
    def cmd(g, frame):
        """apply a raw CMD frame (only FAMILY_ACK / PROFILE fields 2 and 4 act here, as in hg_guardian_cmd)"""
        if len(frame) < 7 or crc8(frame[:6]) != frame[6]: return 0
        if frame[0] == 0x12:
            t = frame[1]; aid = struct.unpack("<I", frame[2:6])[0]; ch = 0
            if t < 1 or t > 3: return 0
            if g.family_pending and (aid == g.alarm_id or (aid & 0xFFFF) == (g.alarm_id & 0xFFFF)): g.family_pending = 0; ch = 1
            if g.help and t == 3 and (aid == g.help_id or (aid & 0xFFFF) == (g.help_id & 0xFFFF)): g.help = 0; ch = 1
            return ch
        if frame[0] == 0x13:
            fid = frame[1]; v = F(struct.unpack("<f", frame[2:6])[0])
            if isnan(v): return 0
            if fid == 0 and K("HG_READING_MIN_C") <= v <= K("HG_READING_MAX_C"): g.reading_today = 1; return 1   # M5.2
            if fid == 2 and 40 <= v <= 100: g.twin["rest_hr"] = v; g.hg2.set_twin(g.twin); return 1
            if fid == 4 and 0 <= v <= F(0.4): g.twin["c_bodyheat"] = v; g.hg2.set_twin(g.twin); return 1
            if fid == 5 and 0 <= v <= 31 and v == F(int(v)): g.prof["med_flags"] = int(v); g.margins(); return 1   # B5-v7
        return 0
    def step(g, m):
        """m: dict with keys of the replay CSV (see run_traces.py). Returns out dict."""
        m = dict(m)   # [B2-fix] input guards, once, as hg_guardian_step
        for k_, lo_, hi_ in (("t1", -40, 85), ("t2", -40, 85), ("tair", -40, 85), ("rh", 0, 100), ("pi", 0, 100), ("astd", 0, 16)):
            m[k_] = guard(m[k_], lo_, hi_)
        hr_ = F(m["hr"]); m["hr"] = hr_ if np.isfinite(hr_) else NAN
        for k_ in ("t1_5s", "t2_5s", "tair_5s"):
            if m.get(k_) is not None: m[k_] = [guard(v_, -40, 85) for v_ in m[k_]]
        g.minute_counter = (g.minute_counter + 1) & 0xFFFF
        mod = m["mod"]; tknown = mod < 1440
        ctw = g.ct.step(m["t1_5s"], m["t2_5s"], m["tair_5s"], m["pi"], m["hrq"], m["dc"], m["astd"], m["flat"], m["charging"])
        worn = m["force_worn"] if m["force_worn"] != 0xFF else ctw
        core, aux = g.hg2.step(dict(t1=m["t1"], t2=m["t2"], tair=m["tair"], rh=m["rh"], hr=m["hr"], hrq=m["hrq"], pi=m["pi"],
                                    astd=m["astd"], worn=worn, mod=mod))
        tin = aux["t_air_corr"]
        astd = F(m["astd"]); astd = F(0) if isnan(astd) else astd
        g.walk_run = min(g.walk_run + 1, 255) if astd >= K("HG_WALK_G") else 0
        hour = mod // 60 if tknown else 0xFF
        fc = m.get("forecast")
        ho = g.ho.step(tin, g.hg2.rh_last, g.walk_run, m["ble"], hour, fc)
        if not g.started: g.ta_ring = [tin] * 16; g.started = 1
        g.ta_ring[g.tai] = tin; ta15 = g.ta_ring[(g.tai + 1) % 16]; g.tai = (g.tai + 1) % 16
        if ho == 0 and not isnan(tin) and not isnan(ta15) and F(ta15 - tin) >= K("HG_AC_STEP_C"): g.ac_latch = KI("HG_AC_LATCH_MIN")
        elif g.ac_latch > 0: g.ac_latch -= 1
        imok = 0; imok_resp = 0xFF
        if m["button"] == 2 and not g.help:
            g.help = 1; g.help_id = g.new_alarm(); g.alarm_id = g.help_id; g.family_pending = 1; g.check_active = 0; g.check_cause = 0
        thermal_ok = core["valid"] and g.hg2.min_since_don >= KI("HG_DON_BLANK_MIN")
        # B5-v7: skin-floor EWMAs, every minute (skin-floor Danger, DRINK skin context, skin DRINK)
        t1in = F(m["t1"]) if (worn != 0 and not isnan(F(m["t1"]))) else K("HG_SF_T1_OFF")
        tain = K("HG_SF_TA_OFF") if isnan(tin) else tin
        g.sf_t1 = F(g.sf_t1 + F(K("HG_SF_A30") * F(t1in - g.sf_t1)))
        g.sf_ta = F(g.sf_ta + F(K("HG_SF_A60") * F(tain - g.sf_ta)))
        midnight = tknown and g.last_mod < 1440 and mod < g.last_mod and g.last_mod - mod >= KI("HG_MIDNIGHT_MIN_STEP")   # T5 m1
        if midnight: g.reading_today = 0     # M5.2
        g.last_mod = mod
        unc = F(0)
        calibrated = False   # M4.3 default (display-only readings); HG_TWIN_READING_MODE=1 is C-only
        f20_v12 = aux["v12_f20"]   # M4.3: no display offset
        ood = aux["x"][14] > K("HG_OOD_RESERVE") or aux["x"][10] > K("HG_OOD_HR")   # M11.3
        f20a = f20_v12 if (ood and f20_v12 > aux["core20_noff"]) else aux["core20_noff"]
        if thermal_ok and not calibrated:
            if KI("HG_UNC_CONST_MODE"):   # M11.4
                lc_ = K("HG_UNC_LOWER_CONST"); unc = lc_ if lc_ < K("HG_UNC_MAX") else K("HG_UNC_MAX")
            else:
                h = F(F(F(K("HG_UNC_Z") * K("HG_UNC_SD_SCALE_EFF")) * core["sd_20"]) - K("HG_UNC_HALF_CAL_EFF"))
                unc = K("HG_UNC_MAX") if h > K("HG_UNC_MAX") else (h if h > 0 else F(0))
        who_cond = False
        if not isnan(tin):
            night = tknown and (mod >= KI("HG_WHO_NIGHT_START") or mod < KI("HG_WHO_NIGHT_END"))
            who_cond = tin >= (K("HG_WHO_NIGHT_C") if night else K("HG_WHO_DAY_C"))
        g.who_hist = ((g.who_hist << 1) | (1 if who_cond else 0)) & ((1 << 45) - 1)
        who = popcount(g.who_hist) >= 30 and g.ac_latch == 0
        night_known = tknown and (mod >= KI("HG_WHO_NIGHT_START") or mod < KI("HG_WHO_NIGHT_END"))
        night_heat = bool(who and night_known)                                   # M1.1
        if tknown and 720 <= mod < KI("HG_WHO_NIGHT_START"): g.nudge_done = 0
        nudge = 0
        if night_heat and not g.nudge_done and worn != 0: nudge = 1; g.nudge_done = 1
        cap = K("HG_M_TOTAL_CAP")                                                # M1.3
        low_d = F(g.m_drink + unc); low_c = F(g.m_cool + unc)
        if low_d > cap: low_d = cap
        if low_c > cap: low_c = cap
        if FLAGS["design"] in (1, 3, 4):   # M7 A (+ M19 Exception = design 4)
            if midnight:
                if g.a_n >= KI("HG_A_MIN_CALM"):
                    cum = 0; i = 0
                    for i in range(100):
                        cum += g.a_hist[i]
                        if 2 * cum >= g.a_n: break
                    med = F(K("HG_A_HIST_T0") + F(K("HG_A_HIST_BIN") * F(F(i) + F(0.5))))
                    b = F(g.a_base + F(K("HG_A_EMA") * F(med - g.a_base))) if g.a_base_n else med
                    g.a_base = K("HG_A_BASE_MIN") if b < K("HG_A_BASE_MIN") else (K("HG_A_BASE_MAX") if b > K("HG_A_BASE_MAX") else b)
                    g.a_base_n = min(g.a_base_n + 1, 255)
                g.a_hist = [0] * 100; g.a_n = 0
                if FLAGS["design"] == 4:   # M19 Exception DRINK nightly fold
                    if g.a_base_n > 0:
                        dsxy = F(g.x_dwd - F(F(g.a_base - g.x_dref) * g.x_dw))
                        g.x_sxx = F(F(K("HG_X_DECAY") * g.x_sxx) + g.x_dww); g.x_sxy = F(F(K("HG_X_DECAY") * g.x_sxy) + dsxy)
                    if g.x_sxx > K("HG_X_SXX_MIN"):
                        c = F(g.x_sxy / g.x_sxx); g.x_c = F(0) if c < 0 else (K("HG_X_C_MAX") if c > K("HG_X_C_MAX") else c)
                    else: g.x_c = F(0)
                    g.x_dww = g.x_dwd = g.x_dw = F(0); g.x_dref = g.a_base if g.a_base_n > 0 else K("HG_X_DREF0")
            if tknown and KI("HG_A_DAY_START") <= mod < KI("HG_A_DAY_END") and worn == 2 and thermal_ok and not aux["active"] and g.level == 0:
                pos = F(F(f20a - K("HG_A_HIST_T0")) / K("HG_A_HIST_BIN"))
                if pos >= 0 and pos < 100 and g.a_n < 65535: g.a_hist[int(pos)] += 1; g.a_n += 1
            delta = F(FLAGS["delta"]) if FLAGS["delta"] is not None else K("HG_A_DELTA")
            low_a = unc if unc < K("HG_M_TOTAL_CAP") else K("HG_M_TOTAL_CAP")   # M11.2
            heat_ctx = (not KI("HG_V12_CTX")) or (not isnan(tin) and tin >= K("HG_V12_CTX_C")) or bool(aux["env_above_old"]) or ood   # M12
            c_v12_drink = bool(core["valid"]) and heat_ctx and f20_v12 >= F(K("HG_T_DRINK") - low_a)
            if FLAGS["design"] == 4:   # M19 Exception DRINK
                aq = K("HG_MB_ACLIP") if astd > K("HG_MB_ACLIP") else astd
                q = int(F(F(aq / K("HG_X_W_STEP")) + F(0.5)))
                g.x_wq = g.x_wq - g.x_ring[g.x_i] + q; g.x_ring[g.x_i] = q; g.x_i = (g.x_i + 1) % KI("HG_X_W_N")
                w30 = F(F(g.x_wq) * K("HG_X_W_STEP"))
                xd = F(FLAGS["delta"]) if FLAGS["delta"] is not None else K("HG_X_DELTA")
                g.x_warm = 0 if ((not isnan(tin)) and tin >= K("HG_X_CTX_C")) else min(g.x_warm + 1, 255)   # B5-v7 heat context
                x_ctx = ((not (K("HG_X_CTX_C") > 0)) or g.x_warm <= KI("HG_X_CTX_WIN")) and ((not (K("HG_X_SKIN_C") > 0)) or g.sf_t1 >= K("HG_X_SKIN_C"))
                c_body1 = c_v12_drink or (x_ctx and thermal_ok and g.a_base_n > 0 and F(F(f20a - g.a_base) - F(g.x_c * w30)) >= F(xd - low_a))
            else:
                c_body1 = c_v12_drink or (thermal_ok and g.a_base_n > 0 and F(f20a - g.a_base) >= F(delta - low_a))
        else:
            c_v12_drink = False
            c_body1 = thermal_ok and f20a >= F(K("HG_T_DRINK") - low_d)
        c_nn38 = thermal_ok and core["logit_p38"] >= g.hg2.W.cut38
        env1 = (aux["env_run"] >= 10 or aux["env_dose"] >= 10) or (K("HG_SF_DRINK_C") > 0 and worn == 2 and thermal_ok
                                                                and g.sf_ta >= K("HG_SF_TA_C") and g.sf_t1 >= K("HG_SF_DRINK_C"))   # B5-v7 skin DRINK
        c_body2 = thermal_ok and f20a >= F(K("HG_T_COOL") - low_c)
        env2 = aux["env_dose"] >= 97
        g.hr_bad_run = 0 if core["hr_valid"] else min(g.hr_bad_run + 1, 65535)
        lg = g.hr_bad_run <= 5 and core["valid"] and aux["v12_z"] >= K("HG_DG_LOGIT_CUT_V12")
        nn385 = thermal_ok and core["logit_p385"] >= g.hg2.W.cut385
        beh = False; pers = False
        NR = KI("HG_PD_SLOPE_MIN") + 1   # M13 f20 ring, every minute
        g.pd_ring[g.pd_i] = f20a; g.pdv_ring[g.pd_i] = f20_v12; g.pd_i = (g.pd_i + 1) % NR
        f20_old = g.pd_ring[g.pd_i]; f20v_old = g.pdv_ring[g.pd_i]
        if g.pd_n < NR: g.pd_n += 1
        marble = False; cool_transit = False
        if KI("HG_MARBLE"):   # M19 Marble Danger state, every minute
            xin = f20a if (worn != 0 and not isnan(f20a)) else K("HG_MB_F20_OFF")
            ain = K("HG_MB_ACLIP") if astd > K("HG_MB_ACLIP") else astd
            if not g.mb_started: g.mb_e10 = g.mb_e60 = xin; g.mb_a30 = g.mb_a120 = ain; g.mb_d = F(0); g.mb_started = 1
            g.mb_e10 = F(g.mb_e10 + F(K("HG_MB_A10") * F(xin - g.mb_e10)))
            g.mb_e60 = F(g.mb_e60 + F(K("HG_MB_A60") * F(xin - g.mb_e60)))
            g.mb_a30 = F(g.mb_a30 + F(K("HG_MB_A30") * F(ain - g.mb_a30)))
            g.mb_a120 = F(g.mb_a120 + F(K("HG_MB_A120") * F(ain - g.mb_a120)))
            g.mb_d = F(F(g.mb_d * K("HG_MB_DKEEP")) + (F(xin - K("HG_MB_KNEE")) if xin > K("HG_MB_KNEE") else F(0)))
            g.mb_warm = 0 if ((not isnan(tin)) and tin >= K("HG_MB_WARM_C")) else min(g.mb_warm + 1, 255)
            g.mb_age = min(g.mb_age + 1, 65535)
            armed = thermal_ok and g.mb_age >= KI("HG_MB_ARM_MIN") and g.mb_warm <= KI("HG_MB_WARM_WIN") \
                and ((not (K("HG_MB_SKIN_C") > 0)) or g.sf_t1 >= K("HG_MB_SKIN_C"))   # B5-v7 skin arming
            sc_ = K("HG_MB_W0")
            sc_ = F(sc_ + F(K("HG_MB_WL") * F(g.mb_e60 - K("HG_MB_LREF"))))
            jr = F(g.mb_e10 - g.mb_e60)
            if KI("HG_MB_JUMP_RISE") and not (jr > 0): jr = F(0)   # M19b: a falling forecast never raises s
            sc_ = F(sc_ + F(K("HG_MB_WJ") * jr))
            sc_ = F(sc_ + F(K("HG_MB_WB") * g.mb_a30))
            sc_ = F(sc_ + F(K("HG_MB_WS") * g.mb_a120))
            sc_ = F(sc_ + F(K("HG_MB_WD") * g.mb_d))
            g.mb_run = min(g.mb_run + 1, 255) if (armed and sc_ >= K("HG_MB_CUT")) else 0
            marble = g.mb_run >= KI("HG_MB_RUN_MIN")
        sfloor = False
        if KI("HG_SF"):   # B5-v7 skin-floor Danger (HR-free)
            hrb = (g.prof["med_flags"] & (1 | KI("HG_MEDF_HRB"))) != 0
            cut = F(K("HG_SF_T1_C") - K("HG_SF_HRB_DT")) if hrb else K("HG_SF_T1_C")
            g.sf_run = min(g.sf_run + 1, 255) if (worn == 2 and thermal_ok and g.sf_ta >= K("HG_SF_TA_C") and g.sf_t1 >= cut) else 0
            sfloor = g.sf_run >= KI("HG_SF_RUN_MIN")
        if worn != 0:
            g.strain_run = min(g.strain_run + 1, 65535) if (thermal_ok and core["strain"] >= K("HG_STRAIN_COOL")) else 0
            strain10 = g.strain_run >= 10
            g.drink.step(c_body1 or c_nn38 or env1)   # M1.1: WHO removed
            w2 = g.cool.step(c_body2 or env2 or strain10)
            g.still_run = min(g.still_run + 1, 65535) if aux["still"] else 0
            mc = g.m_cool if g.m_cool < K("HG_M_TOTAL_CAP") else K("HG_M_TOTAL_CAP")   # M3.1 shadow v1.2 Go-cool tier
            g.pd_cool_run = min(g.pd_cool_run + 1, 65535) if g.cool.on else 0   # M13 Danger by persistence
            run_ok = bool(KI("HG_PD") and g.cool.on and g.pd_cool_run >= KI("HG_PD_COOL_MIN") and g.pd_n >= NR)   # T5 D2
            slope_v = (not isnan(f20_v12)) and (not isnan(f20v_old)) and F(f20_v12 - f20v_old) >= -K("HG_PD_SLOPE_EPS_V12")
            pers_prot = run_ok and slope_v and (aux["env_above"] or (core["valid"] and aux["v12_z"] >= K("HG_PD_V12_Z")))
            slope_nn = (not isnan(f20a)) and (not isnan(f20_old)) and F(f20a - f20_old) >= 0
            pers = bool(pers_prot or (run_ok and slope_nn and thermal_ok and core["logit_p385"] >= K("HG_PD_NN_LOGIT")))
            c_v12 = thermal_ok and aux["v12_f20"] >= F(K("HG_T_COOL") - mc)   # M4.3: no display offset
            wp = g.cool_p.step(c_v12 or env2)
            if wp:
                g.cool_min = min(g.cool_min + 1, 65535)
                if m["button"]: g.cool_ack = 1
            else: g.cool_min = 0; g.cool_ack = 0
            beh = bool(wp and g.cool_min >= 10 and g.still_run >= 10 and not g.cool_ack)
            g.danger.step(lg or nn385 or beh or pers or marble or sfloor)
            pers = bool(pers or marble or sfloor)   # cause: DANGER (B5-v7: + skin floor)
            dshow = g.drink.on
            if FLAGS["design"] == 4:   # M19 settled rule (NN-only starts only)
                if dshow and not g.x_prev:
                    if g.x_since < KI("HG_X_SETTLE_MIN") and f20a < F(g.x_last + K("HG_X_RISE_C")) and not (c_v12_drink or env1): dshow = 0
                    elif not isnan(f20a): g.x_last = f20a   # a NaN f20 never enters the settled state (D1)
                g.x_since = 0 if dshow else min(g.x_since + 1, 65535)
                g.x_prev = 1 if dshow else 0
            g.drink_shown = 1 if dshow else 0
            target = 3 if g.danger.on else 2 if g.cool.on else 1 if dshow else 0
            g.level = g.level + 1 if target > g.level else target
            cool_transit = bool(KI("HG_COOL_TRANSIT") and g.level == 2 and target == 3)   # M19b stepping stone
        if FLAGS["design"] == 4 and tknown and KI("HG_A_DAY_START") <= mod < KI("HG_A_DAY_END") and worn == 2 and thermal_ok and g.level < 2 \
                and not isnan(tin) and tin < K("HG_X_CALM_TIN") and not isnan(f20a):   # M19 Exception learning (calm rooms)
            g.x_dww = F(g.x_dww + F(w30 * w30)); g.x_dwd = F(g.x_dwd + F(w30 * F(f20a - g.x_dref))); g.x_dw = F(g.x_dw + w30)
        heat_day = (fc[3 * hour + 2] & 1) if (fc is not None and tknown) else 0
        impact = (not isnan(F(m["apeak"]))) and F(m["apeak"]) >= K("HG_IMPACT_G")
        frozen = bool(g.cool.on or g.danger.on or g.check_active) if FLAGS["m7r"] else bool(g.drink.on or g.cool.on or g.danger.on)
        ro = g.rt.step(mod, m["astd"], m.get("zang"), worn, frozen, heat_day, tin,
                       g.cool.on, impact, 1 if m["button"] else 0)
        cause = 0
        if g.level == 3: cause |= (1 if (lg or nn385 or pers) else 0) | (2 if beh else 0)
        if g.level == 3 and not (cause & 3): cause |= g.last_cause if g.last_cause else 1
        if ro["req"] & 1: cause |= 4
        if ro["req"] & 2: cause |= 8
        if ro["req"] & 4: cause |= 16
        g.last_cause = (cause & 3) if g.level == 3 else 0
        hap = 0
        if g.snooze > 0: g.snooze -= 1
        check_off = bool(g.check_active and worn == 0)   # T5 D4: a running CHECK keeps counting with the band off
        if not g.help and (worn != 0 or g.check_active):
            if g.check_active:
                keep = g.check_cause if check_off else (cause | (16 if ((g.check_cause & 16) and not aux["active"]) else 0))
                g.check_cause |= keep
                if not (keep & 0x1F): g.check_active = 0; g.check_cause = 0
                elif m["button"] == 1 and not check_off:
                    imok = 1; imok_resp = g.check_t; g.check_active = 0; g.check_cause = 0; g.snooze = 15
                else:
                    g.check_t = min(g.check_t + 1, 255)
                    fmin = 5 if (g.check_cause & 3) else (5 if (g.check_cause & 16) else 10)
                    if g.check_t in (2, 5): hap = 3
                    if not g.family_sent and g.check_t >= fmin:
                        g.family_sent = 1; g.family_pending = 1; g.alarm_id = g.new_alarm(); hap = 3
            elif cause and g.snooze == 0:
                g.check_active = 1; g.check_cause = cause; g.check_t = 0; g.family_sent = 0; hap = 3
        if FLAGS["design"] in (2, 3):   # M7 B
            if g.b_left > 0: g.b_left -= 1
            if g.b_since < 65535: g.b_since += 1
            if g.level == 1 and worn != 0:
                onset = (not g.b_prev_drink) and g.b_since >= KI("HG_B_REFRACTORY_MIN")
                rising = g.b_since >= KI("HG_B_NUDGE_MIN") and f20a >= F(g.b_last_f20 + K("HG_B_RISE_C"))
                if onset or rising: g.b_left = KI("HG_B_NUDGE_MIN"); g.b_since = 0; g.b_last_f20 = f20a
            g.b_prev_drink = 1 if g.level >= 1 else 0
        g.notworn_min = min(g.notworn_min + 1, 65535) if worn == 0 else 0
        vbat = F(m["vbat"])
        if g.help: st, scr = 8, 10
        elif imok: st, scr = 5, 6
        elif g.check_active: st = 4 if (g.check_cause & 3) else 3; scr = 7 if worn == 0 else (5 if g.family_sent else 4)   # T5 D4
        elif g.notworn_min >= 10: st, scr = 6, 7
        elif g.level == 3 or cool_transit: st, scr = 4, 3   # M19b: transit = Danger flow, silent
        elif g.level == 2: st, scr = 2, 2
        elif g.level == 1 and (FLAGS["design"] not in (2, 3) or g.b_left > 0): st, scr = 1, 1
        elif (not isnan(vbat)) and vbat < K("HG_VBAT_LOW"): st, scr = 7, 9
        else: st, scr = 0, (11 if nudge else (8 if worn == 1 else 0))
        if hap == 0 and st != g.last_state:
            if st == 1 and g.last_state == 0: hap = 1
            elif st == 2 and g.last_state < 2: hap = 2
            elif st == 8: hap = 3
            elif st == 5: hap = 4
        if hap == 0 and nudge and st == 0: hap = 4
        if hap and (not isnan(vbat)) and vbat < K("HG_VBAT_SOFT"): hap = 5
        g.last_state = st
        out = dict(state=st, level=g.level, family_alert=g.family_pending, alarm_id=g.alarm_id,
                   check_reason=g.check_cause if g.check_active else 0, check_min=g.check_t if g.check_active else 0xFF,
                   haptic=hap, screen=scr, routine_score=ro["routine_score"], home_out=ho, worn=worn,
                   why=(core["why"] | (4 if beh else 0) | (128 if who else 0) | (64 if unc > 0 else 0)), notify_not_worn=int(g.notworn_min >= 30),
                   tiers=g.drink_shown | (g.cool.on << 1) | (g.danger.on << 2), routine_req=ro["req"], imok_resp_min=imok_resp, night_heat=int(night_heat), nudge=nudge)
        out.update({"core_" + k if not k.startswith("core") else k: v for k, v in core.items()})
        out["aux"] = aux
        code = g.level if st == 6 else CODE[st]
        b = F(0) if isnan(vbat) else F(F(F(F(vbat - K("HG_VBAT_EMPTY")) / F(K("HG_VBAT_FULL") - K("HG_VBAT_EMPTY"))) * F(100)) + F(0.5))
        bp = int(0 if b <= 0 else (100 if b >= 100 else b))
        a = F(F(astd * F(1000)) + F(0.5)); act = 255 if a >= 255 else int(a)
        sdn = core["sd_now"]
        ss = dict(state_code=code, contact_ok=worn == 2, time_synced=tknown, charging=m["charging"], home=ho == 0,
                  ppg_valid=core["hr_valid"], family_pending=g.family_pending, not_worn=st == 6,
                  core_c=core["core_now"] if core["valid"] else NAN,
                  half_range_c=max(F(F(1.645) * (sdn if sdn > K("HG_SD_FLOOR") else K("HG_SD_FLOOR"))), K("HG_RANGE_HALF_REAL_EFF")),   # [B2-fix]
                  hr_bpm=m["hr"] if (m["hrq"] == 4 and m["hr"] >= 30 and m["hr"] <= 220) else NAN, hr_q=m["hrq"], t1_c=m["t1"], t2_c=m["t2"], tair_c=m["tair"], rh_pct=m["rh"],
                  battery_pct=bp, routine_score=ro["routine_score"], activity=act, minute_counter=g.minute_counter,
                  alarm_id16=g.alarm_id & 0xFFFF)
        out["status"] = status_pack(ss).hex()
        return out
