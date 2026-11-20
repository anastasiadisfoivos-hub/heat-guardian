"""T1 defect D1 reproduction: night sleep is never written after day 0 (SIMULATION).
(a) stored dev data: fraction asleep / in bedroom between 01:00 and 05:00 per stored day;
(b) builder's build_person for a dev person: asleep minutes per day incl. spin-up day 0;
(c) the arithmetic: night is written as _set(o + prev_bed, o + W_) with prev_bed ~ 1380 (yesterday's bed time,
    minutes from YESTERDAY's midnight) and W_ ~ 420 -> start > end -> no-op for every d >= 1."""
import sys, json
sys.path.insert(0, "/home/claude/hg_ai/sim")
import numpy as np, pandas as pd, pyarrow.parquet as pq
from velders.scenarios import build_person, env_arrays, ACT_IDX
pf = pq.ParquetFile("/home/claude/hg_ai/sim/data/minutes_dev_v2.parquet")
tot = night = asl = cls_sleep = 0; met_night = []; drink_night = 0.0
for g in range(0, pf.num_row_groups, 2):
    d = pf.read_row_group(g, columns=["minute_of_day", "asleep", "activity_class", "met", "drink_mL"]).to_pandas()
    m = d.minute_of_day.between(60, 299)
    night += int(m.sum()); asl += int(d.asleep[m].sum()); cls_sleep += int((d.activity_class[m] == 0).sum())
    met_night.append(float(d.met[m].mean())); drink_night += float(d.drink_mL[m].sum())
res = dict(stored_frac_asleep_01_05h=asl / night, stored_frac_class_sleep_01_05h=cls_sleep / night,
           stored_mean_met_01_05h=float(np.mean(met_night)), stored_drink_mL_per_person_night_01_05h=drink_night / (200 * 10))
persons = pd.read_parquet("/home/claude/hg_ai/sim/data/persons.parquet")
r = persons[persons.person_id == 6].to_dict("records")[0]
tl, mins, _ = build_person(r, 10, int(r["seed"]))
res["build_person_pid6_asleep_min_per_day"] = [int(tl.asleep[k * 1440:(k + 1) * 1440].sum()) for k in range(11)]
res["build_person_pid6_bedroom_min_per_day"] = [int((tl.room[k * 1440:(k + 1) * 1440] == 1).sum()) for k in range(11)]
res["build_person_pid6_night_act_01_05h_day3"] = sorted(set(tl.act[3 * 1440 + 60:3 * 1440 + 300].tolist()))
res["ACT_IDX_sit"] = ACT_IDX["sit"]
print(json.dumps(res, indent=1)); json.dump(res, open("/home/claude/hg_ai/tests/t1/out/sleep_bug.json", "w"), indent=1)
