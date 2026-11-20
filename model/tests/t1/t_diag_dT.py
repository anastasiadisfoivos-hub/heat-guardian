"""Diagnose (a) dT > 0.6 at home T_in >= 38 C, (b) T1 > T_core + 0.11 with air < core and no sun (SIMULATION)."""
import numpy as np, pandas as pd, pyarrow.parquet as pq, collections, json
pf = pq.ParquetFile("/home/claude/hg_ai/sim/data/minutes_dev_v2.parquet")
ca, cb = collections.Counter(), collections.Counter()
exa = []
for g in range(0, pf.num_row_groups, 4):
    df = pf.read_row_group(g).to_pandas()
    w2 = df.worn_truth.values == 2
    worn = df.worn_truth.values
    loc = df.location.values; sun = df.sun_on_lid.values > 0
    dT = (df.T1 - df.T2).values; tc = df.T_core.values; Tin = df.T_in.values
    air = np.where(loc == 0, Tin, df.T_out.values)
    n = len(df)
    def recent(mask, k=40):
        out = np.zeros(n, bool)
        idx = np.nonzero(mask)[0]
        for i in idx:
            out[i + 1:i + 1 + k] = True
        return out
    don = recent((worn[1:] > 0) & (worn[:-1] == 0)) if n else None
    don = np.concatenate([[False], don[:-1]]) if n else don
    locchg = recent(np.diff(loc) != 0); locchg = np.concatenate([[False], locchg[:-1]])
    sunrec = recent(sun, 30)
    loose_rec = recent(worn == 1, 30)
    tin_jump = np.concatenate([[0], np.abs(np.diff(Tin))]) > 0.5
    tinj = recent(tin_jump, 30)
    a = w2 & (loc == 0) & ~sun & (Tin >= 38) & (dT > 0.6)
    for i in np.nonzero(a)[0]:
        key = ("donning<40min" if don[i] else "") + ("|loc_change<40min" if locchg[i] else "") + ("|sun<30min" if sunrec[i] else "") + ("|loose<30min" if loose_rec[i] else "") + ("|Tin_jump<30min" if tinj[i] else "")
        ca[key or "none"] += 1
        if not key and len(exa) < 3:
            exa.append(dict(pid=int(df.person_id.iloc[0]), t=int(df.t_min.iloc[i]), dT=float(dT[i]), Tin=float(Tin[i]), fan=int(df.fan.iloc[i])))
    b = w2 & ~sun & (air < tc - 0.5) & (df.T1.values > tc + 0.11)
    for i in np.nonzero(b)[0]:
        key = ("sun<30min" if sunrec[i] else "") + ("|loc_change<40min" if locchg[i] else "") + ("|donning<40min" if don[i] else "")
        cb[key or "none"] += 1
print("dT>0.6 at home Tin>=38, worn, no sun -- context:", dict(ca), exa)
print("T1>Tc+0.11 with air<Tc-0.5, no sun -- context:", dict(cb))
