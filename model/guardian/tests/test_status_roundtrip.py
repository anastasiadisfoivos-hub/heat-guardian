#!/usr/bin/env python3
"""Acceptance 7: STATUS frames packed by the C build round-trip through the Python (phone-side) unpacker.
Replays one CRAFTED person-day + one HTT session through host_test and decodes every minute's frame."""
import os, sys, tempfile, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "py"))
import trace_gen, trace_io
from hg_guardian_py import status_unpack
CODE = {0: 0, 1: 1, 2: 2, 3: 6, 4: 3, 5: 4, 7: 5, 8: 7}
p = trace_gen.person(1003); mins = trace_gen.days(p, 1, "heat", seed=1)
bad = n = 0
with tempfile.TemporaryDirectory() as d:
    trace_io.write_csv(d + "/i.csv", mins, p["profile"], p["twin"])
    rows = trace_io.run_c(d + "/i.csv", d + "/o.csv")
for m, r in zip(mins, rows):
    s = status_unpack(bytes.fromhex(r["status"])); n += 1
    ok = s["minute_counter"] == r["row"] + 1 and s["contact_ok"] == (r["worn"] == 2) and s["time_synced"]
    ok &= (s["state_code"] == CODE[r["state"]]) if r["state"] != 6 else s["not_worn"]
    ok &= s["family_pending"] == bool(r["family_alert"])
    ok &= (abs(s["core_c"] - r["core_now"]) <= 0.0051) if r["valid"] else s["core_c"] == 0
    ok &= s["t1_c"] is not None and abs(s["t1_c"] - m["t1"]) <= 0.0051 and abs(s["tair_c"] - m["tair"]) <= 0.0051
    ok &= s["routine_score"] == r["routine_score"] if not s["family_pending"] else s["alarm_id16"] == (r["alarm_id"] & 0xFFFF)
    if not ok: bad += 1
print("%s STATUS round-trip C -> Python unpacker: %d frames, %d bad" % ("PASS" if bad == 0 else "FAIL", n, bad))
# corrupted frames must be rejected
import random
fr = bytearray(bytes.fromhex(rows[100]["status"])); fr[5] ^= 0x40
try: status_unpack(bytes(fr)); print("FAIL corrupted frame accepted")
except AssertionError: print("PASS corrupted STATUS frame rejected by CRC")
sys.exit(1 if bad else 0)
