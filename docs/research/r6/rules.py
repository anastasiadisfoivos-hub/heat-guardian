"""R6 rule-level harness - SIMULATION DEV. Event-level Danger scoring identical in spirit to eval_sim_m7.py:
event (core385 start t) is CAUGHT if the candidate fires in [t-45, t+10]. Alarm episodes = onsets after >= 30 quiet minutes.
An episode is FALSE if true core never reaches 38.5 in [onset-10, onset+60]. Rates per wearer-month over ALL worn person-days (and S1 days)."""
import numpy as np
from common import *
def episodes(fire, gap=30):
    idx = np.where(fire)[0]
    if len(idx) == 0: return np.array([], int)
    keep = np.concatenate([[True], np.diff(idx) > gap]); return idx[keep]
def score(fires, data, hk=None):
    """fires: dict pid -> bool array. data: dict pid -> loaded d. Returns dict of metrics."""
    caught = []; cls = []; lead = []; fa = []; fa_s1 = []; days = []; days_s1 = []; near = 0; nfa = 0
    for pid, fire in fires.items():
        d = data[pid]; t0 = d["t0"]; tc = d["T_core"]; n = len(tc)
        for (ts, te, day) in events(pid, "core385"):
            i = ts - t0; a = max(0, i - 45); b = min(n, i + 11); w = np.where(fire[a:b])[0]
            caught.append(len(w) > 0); cls.append(d["types"][day - 1][:2]); lead.append(i - (a + w[0]) if len(w) else np.nan)
        on = episodes(fire); f = 0; f1 = 0
        for o in on:
            pk = tc[max(0, o - 10):min(n, o + 61)].max()
            if pk < 38.5:
                f += 1; nfa += 1; near += pk >= 38.2
                if d["types"][int(d["day"][o]) - 1] == "S1": f1 += 1
        fa.append(f); days.append(10); fa_s1.append(f1); days_s1.append(sum(t == "S1" for t in d["types"]))
    caught = np.array(caught); cls = np.array(cls); fa = np.array(fa, float); fa_s1 = np.array(fa_s1, float); ds1 = np.array(days_s1, float)
    m1 = ds1 > 0
    return dict(sens=float(caught.mean()), sens_S2=float(caught[cls == "S2"].mean()), n=int(len(caught)), n_S2=int((cls == "S2").sum()),
                lead=float(np.nanmedian(lead)) if np.isfinite(lead).any() else np.nan,
                fa_month=float(30 * fa.sum() / (10 * len(fa))), fa_month_median=float(np.median(30 * fa / 10)),
                fa_month_S1=float(30 * fa_s1[m1].sum() / ds1[m1].sum()), near_share=float(near / max(nfa, 1)), persons_with_fa=float((fa > 0).mean()))
def run_min(cond, k):
    """True where cond has held for >= k consecutive minutes."""
    c = np.asarray(cond, bool); r = np.zeros(len(c), int); s = 0
    for i in range(len(c)): s = s + 1 if c[i] else 0; r[i] = s
    return r >= k
