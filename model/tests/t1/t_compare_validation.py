"""Compare T1-regenerated rows (tests/t1/out/rows_<section>.json) to the builder's VALIDATION.csv."""
import json, glob, csv
tab = {r["id"]: r for r in csv.DictReader(open("/home/claude/hg_ai/sim/VALIDATION.csv"))}
mine = {}
for f in glob.glob("/home/claude/hg_ai/tests/t1/out/rows_*.json"):
    for s, rs in json.load(open(f)).items():
        for r in rs:
            mine[r["id"]] = r
out = []
for k in tab:
    a, b = tab[k], mine.get(k)
    if b is None:
        out.append((k, "NOT REGENERATED", "", "")); continue
    st = "match" if (a["value"] == b["value"] and a["result"] == b["result"]) else "MISMATCH"
    out.append((k, st, a["result"] + " | " + a["value"], b["result"] + " | " + b["value"]))
extra = sorted(set(mine) - set(tab))
for o in out:
    if o[1] != "match":
        print(o[0], o[1]); print("   table:", o[2]); print("   regen:", o[3])
print("matched", sum(o[1] == "match" for o in out), "/", len(out), "extra:", extra)
json.dump(out, open("/home/claude/hg_ai/tests/t1/out/compare_validation.json", "w"), indent=1)
