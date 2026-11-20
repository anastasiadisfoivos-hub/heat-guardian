#!/usr/bin/env python3
"""Convert B4's shared vectors (tomorrow/tests/crc8_vectors.json, ble_vectors.json) into flat text the C host test reads.
Run before `make test` (the Makefile test target does it)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); T = "/home/claude/hg_ai/tomorrow/tests"
with open(os.path.join(HERE, "crc8_vectors.txt"), "w") as f:
    f.write("313233343536373839 f4\n")
    if os.path.exists(os.path.join(T, "crc8_vectors.json")):
        for v in json.load(open(os.path.join(T, "crc8_vectors.json")))["vectors"]:
            f.write("%s %s\n" % (v["data_hex"] or "-", v["crc_hex"]))
with open(os.path.join(HERE, "ble_vectors.txt"), "w") as f:
    if os.path.exists(os.path.join(T, "ble_vectors.json")):
        d = json.load(open(os.path.join(T, "ble_vectors.json")))
        for h in d["forecast_chunks_hex"]: f.write("F %s\n" % h)
        for k, hr in enumerate(d["decoded_hours"]):
            fl = (1 if hr["heat_day"] else 0) | (2 if hr["night_heat"] else 0) | (4 if hr["safe"] else 0)
            f.write("H %d %d %d %d\n" % (k, hr["t_in"], hr["rh_in"], fl))
        f.write("S %s %d %d %s\n" % (d["safe_hours_hex"], d["safe_hours_bitmap"], d["plan_id"], d["tag"].replace(" ", "_")))
print("vectors written")
