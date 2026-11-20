"""T1: re-derive V12 (and V13/V14/V15 for free) directly from the raw PSU HEAT Excel (Zenodo 10197956),
independent of R1's database path. Pa column is mmHg; kPa = mmHg * 0.133322. Sweat SR in g/(m2 h) for V21."""
import pandas as pd, numpy as np, json
X = pd.ExcelFile("/home/claude/hgdata/raw/3_psu_heat/COMMSENV-23-1347-T Compiled Data.xlsx")
out = {}
for sh in X.sheet_names:
    raw = X.parse(sh, header=None)
    # blocks: column 0..11 older, 13..24 young; activity label rows ('MinAct'/'Rest') then header row 'Subject #'
    for side, c0 in (("older", 0), ("young", 13)):
        act = None; hdr = None
        for i in range(len(raw)):
            v = raw.iat[i, c0]
            if isinstance(v, str) and v.strip() in ("MinAct", "Rest"):
                act = v.strip(); hdr = None; continue
            if isinstance(v, str) and v.strip().startswith("Subject"):
                hdr = [str(raw.iat[i, c0 + k]).strip() for k in range(12)]; continue
            if hdr and act and pd.notna(v) and not isinstance(v, str):
                rec = {hdr[k]: raw.iat[i, c0 + k] for k in range(12)}
                out.setdefault((sh, side, act), []).append(rec)
res = {}
for (sh, side, act), recs in sorted(out.items()):
    d = pd.DataFrame(recs)
    tdb = pd.to_numeric(d["Tdb"], errors="coerce"); pa = pd.to_numeric(d["Pa"], errors="coerce")
    sr = pd.to_numeric(d["SR (g/m2/h)"], errors="coerce")
    res[f"{sh}|{side}|{act}"] = dict(n=int(pa.notna().sum()), Tdb=round(float(tdb.mean()), 2), Pa_kPa=round(float(pa.mean() * 0.133322), 3),
                                     sweat=round(float(sr.mean()), 1))
for k, v in res.items():
    print(k, v)
tgt = {"34C": 3.41, "36C": 3.21, "38C": 3.07, "40C": 2.54}
print("V12 older MinAct (ADL) Pa_crit kPa raw vs R1/B1 target:", {s: (res[f"{s}|older|MinAct"]["Pa_kPa"], t) for s, t in tgt.items()})
json.dump(res, open("/home/claude/hg_ai/tests/t1/out/psu_rederive.json", "w"), indent=1)
