"""B1 Virtual Elders SIM-DEV minutes -> Guardian replay minutes (ARCHITECTURE 3.3 output format). SIMULATION.
Sealed persons are excluded and asserted (ARCH 3.2 rule 5). Reads only minutes_dev_v2.parquet (frozen v2), never minutes_sealed*."""
import json, os
import numpy as np
from trace_io import minute
SIM = "/home/claude/hg_ai/sim/data"; SEAL = "/home/claude/hg_ai/model/sealed_hg2.json"

def sealed_ids():
    return set(json.load(open(SEAL))["sealed_sim_person_ids"])

def profile_of(p):
    f = (1 if (p.get("med_bb_nonsel", 0) or p.get("med_bb_sel", 0)) else 0) | (2 if p.get("med_diuretic", 0) else 0) \
        | (4 if p.get("med_antichol", 0) else 0) | (8 if p.get("med_ace_arb", 0) else 0)
    return dict(age=float(p["age"]), sex_m=float(p["sex_m"]), bmi=float(p["bmi"]), med_flags=int(f))

def person_days(max_persons=None, days=None):
    import pandas as pd, pyarrow.parquet as pq
    path = os.path.join(SIM, "minutes_dev_v4.parquet")   # v4 (the frozen v2 file was removed from sim/data); sealed files never opened
    if not os.path.exists(path): raise SystemExit("SIM-DEV not available yet: %s" % path)
    sealed = sealed_ids()
    persons = pd.read_parquet(os.path.join(SIM, "persons.parquet")).set_index("person_id")
    pf = pq.ParquetFile(path); groups = []                 # one row group per person: read only what is needed
    for i in range(pf.metadata.num_row_groups):
        pid = int(pf.metadata.row_group(i).column(0).statistics.min)
        if pid not in sealed: groups.append((pid, i))
        if max_persons is not None and len(groups) >= max_persons: break
    ids = [p for p, _ in groups]; assert not set(ids) & sealed
    df = pf.read_row_groups([i for _, i in groups]).to_pandas()
    for pid in ids:
        p = persons.loc[pid].to_dict(); prof = profile_of(p)
        tw = dict(rest_hr=70.0, k_person=0.12, core_offset=0.0, c_bodyheat=0.15, t1_night_base=[float("nan")] * 24)  # population defaults
        g = df[df.person_id == pid].sort_values("t_min")
        if days is not None: g = g[g.day.isin(days)]
        z = g.zangle_deg.values.astype(float); mins = []
        for i, r in enumerate(g.itertuples()):
            z0 = z[i - 1] if i else z[i]
            zs = list(np.linspace(z0, z[i], 13)[1:])           # 5-s angles interpolated between the 1-min values
            q = int(r.hr_quality)
            m = minute(mod=int(r.minute_of_day), t1=r.T1, t2=r.T2, tair=r.T_air_meas, rh=r.RH_meas, hr=r.HR_meas, hrq=q, pi=r.PI,
                       astd=r.a_std_g, apeak=1.0, dc=110000 if r.worn_truth != 0 else 1200, zang=zs, vbat=3.9, ble=-1)
            m["truth"] = dict(day=int(r.day), worn=int(r.worn_truth), location=int(r.location), T_in=float(r.T_in), T_core=float(r.T_core),
                              scenario=getattr(r, "scenario", None))
            mins.append(m)
        yield pid, prof, tw, mins

def sim_sets(n_person_days=50):
    out = []
    for pid, prof, tw, mins in person_days(max_persons=5):
        for d in sorted(set(m["truth"]["day"] for m in mins)):
            out.append(("sim_p%d_d%d" % (pid, d), prof, tw, [m for m in mins if m["truth"]["day"] == d]))
            if len(out) >= n_person_days: return out
    return out
