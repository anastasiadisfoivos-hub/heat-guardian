"""Session/event scoring on HTT-DEV, copied from /home/claude/hgmodel/s09_danger_probability.py (episodes, sess_stats,
choose) and common.py (first_run) so hg2 is scored by exactly the code that produced the v1.2 numbers.
False alarm = an alarm episode (>= 2 consecutive minutes, gaps < 10 min merged) after whose onset the real core does
not reach the event threshold within 60 min. Warned = an episode active in [event - 45, event + 10] min.
Young adults 18-33, chamber walk, DEV."""
import numpy as np


def first_run(mask, k=2):
    run = 0
    for i, v in enumerate(mask):
        run = run + 1 if v else 0
        if run >= k: return i - k + 1
    return None


def episodes(mask, k=2, merge_gap=10):
    m = np.concatenate([[0], mask.astype(np.int8), [0]]); d = np.diff(m)
    st = np.where(d == 1)[0]; en = np.where(d == -1)[0] - 1
    eps = []
    for a, b in zip(st, en):
        if b - a + 1 >= k:
            if eps and a - eps[-1][1] < merge_gap: eps[-1] = (eps[-1][0], b)
            else: eps.append((a, b))
    return eps


def sess_stats(yy, ev, mask, thr, pre=45, post=10, hz=60):
    eps = episodes(mask)
    det, lead = 0, np.nan
    if ev is not None:
        for a, b in eps:
            if a <= ev + post and b >= ev - pre:
                det, lead = 1, ev - a; break
    fa = sum(1 for a, b in eps if not yy[a: a + hz + 1].max() >= thr)
    return det, lead, fa, len(eps)


class Sessions:
    def __init__(s, core, subj, sess):
        s.keys, s.rows, s.y, s.subj = [], [], [], []
        key = np.array([str(a) + "|" + str(b) for a, b in zip(subj, sess)])
        _, first = np.unique(key, return_index=True)
        for k in key[np.sort(first)]:
            r = np.where(key == k)[0]; yy = np.nan_to_num(core[r], nan=-1)
            s.keys.append(k); s.rows.append(r); s.y.append(yy); s.subj.append(subj[r[0]])
        s.subj = np.array(s.subj)
        s.ev = {thr: [first_run(yy >= thr) for yy in s.y] for thr in (38.0, 38.5)}

    def table(s, masks_fn, ncut, thr):
        """masks_fn(session_index, cut_index) -> bool mask. returns arrays [n_sess, ncut] det, lead, fa + hours, has_event"""
        n = len(s.keys); det = np.zeros((n, ncut)); lead = np.full((n, ncut), np.nan); fa = np.zeros((n, ncut))
        for i in range(n):
            for c in range(ncut):
                d, l, f, _ = sess_stats(s.y[i], s.ev[thr][i], masks_fn(i, c), thr)
                det[i, c], lead[i, c], fa[i, c] = d, l, f
        hours = np.array([len(y) / 60 for y in s.y]); has = np.array([e is not None for e in s.ev[thr]])
        return det, lead, fa, hours, has


def pick_cut(det, fa, hours, has, sel, cuts, fa_max):
    """REPORT choose(): highest sensitivity with FA/h <= fa_max over sessions `sel`; ties -> higher cut; none -> max cut"""
    sens = det[sel].sum(0) / max(has[sel].sum(), 1); fah = fa[sel].sum(0) / hours[sel].sum()
    ok = np.where(fah <= fa_max)[0]
    if not len(ok): return len(cuts) - 1
    best = ok[np.lexsort((-np.array(cuts)[ok], -sens[ok]))][0]
    return int(best)


def aggregate(det, lead, fa, hours, has, subj, boot=1000, seed=7):
    """det/lead/fa per session (chosen cut already applied). 95 % ranges by resampling SUBJECTS."""
    ev = int(has.sum()); d = int(det[has].sum()); L = lead[has & (det > 0)]
    out = dict(events=ev, detected=d, sensitivity=100 * d / max(ev, 1), false_alarms=int(fa.sum()), hours=float(hours.sum()),
               fa_per_h=float(fa.sum() / hours.sum()),
               lead_median=float(np.median(L)) if len(L) else None,
               lead_middle_half=[float(np.percentile(L, 25)), float(np.percentile(L, 75))] if len(L) else None)
    rng = np.random.default_rng(seed); us = np.unique(subj); S = []; FAH = []
    idx = {u: np.where(subj == u)[0] for u in us}
    for _ in range(boot):
        r = np.concatenate([idx[u] for u in rng.choice(us, len(us))])
        S.append(100 * det[r][has[r]].sum() / max(has[r].sum(), 1)); FAH.append(fa[r].sum() / hours[r].sum())
    out["sensitivity_95"] = [float(np.percentile(S, 2.5)), float(np.percentile(S, 97.5))]
    out["fa_per_h_95"] = [float(np.percentile(FAH, 2.5)), float(np.percentile(FAH, 97.5))]
    return out
