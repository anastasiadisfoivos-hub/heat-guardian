#!/usr/bin/env python3
"""B6b acceptance 6: the dashboard's JavaScript decoder (fw/tools/hg_ble.js) == B5's Python unpacker
(guardian/py/hg_guardian_py.status_unpack, imported read-only) on STATUS frames recorded from the frozen C guardian
(fw/tools/test_fw.c run through hg_fw.c), and the dashboard's phone->band encoders == B5's cmd_frame().
Also checks the 09 guardian log record (marker 13) decoded by parse_log.py against the C values.
  python3 fw/tools/test_dashboard.py frames.txt
"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(R, "guardian", "py")); sys.path.insert(0, os.path.join(R, "model", "guardian", "py")); sys.path.insert(0, HERE)  # public layout
from hg_guardian_py import status_unpack, cmd_frame   # noqa: E402
import parse_log                                       # noqa: E402

frames_path = sys.argv[1]
S, G = [], []
for line in open(frames_path):
    p = line.split()
    if p[0] == "S": S.append(p[1])
    elif p[0] == "G": G.append((p[1], [int(x) for x in p[2:]]))
js = r"""
const H = require(process.argv[1]); const fs = require('fs');
const inp = JSON.parse(fs.readFileSync(0, 'utf8'));
const out = { status: inp.status.map(h => H.decodeStatus(H.fromHex(h))),
  time: H.toHex(H.cmdTime(1763287200, 8)), ack: H.toHex(H.cmdFamilyAck(1, 0x00012345)), ack3: H.toHex(H.cmdFamilyAck(3, 0x2345)), dbg: H.toHex(H.cmdDebug(60)),
  crc: H.crc8(Buffer.from('123456789'), 9) };
process.stdout.write(JSON.stringify(out));
"""
res = subprocess.run(["node", "-e", js, os.path.join(HERE, "hg_ble.js")], input=json.dumps({"status": S}), capture_output=True, text=True)
if res.returncode:
    print(res.stderr); sys.exit("node failed")
out = json.loads(res.stdout)
fails = 0
def check(ok, msg):
    global fails
    print(("PASS  " if ok else "FAIL  ") + msg); fails += 0 if ok else 1
bad = 0; states = set()
for h, d in zip(S, out["status"]):
    ref = status_unpack(bytes.fromhex(h))
    d2 = {k: v for k, v in d.items() if k != "state"}
    for k, v in ref.items():
        a = d2.get(k)
        if (a is None) != (v is None) or (a is not None and (abs(a - v) > 1e-9 if isinstance(v, float) else a != v)):
            bad += 1; print("  mismatch", h, k, a, v); break
    states.add(d["state"])
check(len(S) > 100 and bad == 0, f"dashboard decodeStatus == B5 status_unpack on {len(S)} recorded frames (states seen: {sorted(states)})")
check(out["time"] == cmd_frame(0x10, unix_s=1763287200, tz_q=8).hex(), "TIME frame == B5 cmd_frame(0x10)")
check(out["ack"] == cmd_frame(0x12, ack_type=1, alarm_id=0x00012345).hex(), "FAMILY_ACK frame == B5 cmd_frame(0x12)")
check(out["ack3"] == cmd_frame(0x12, ack_type=3, alarm_id=0x2345).hex(), "Cancel-HELP frame (ack type 3, 16-bit alarm id) == B5 cmd_frame(0x12, type 3)")
check(out["crc"] == 0xF4 and out["dbg"][-2:] == "%02x" % parse_log.crc8(bytes.fromhex(out["dbg"][:-2])), "CRC-8 check value + DEBUG frame CRC")
# plan.json frames from B4 are forwarded as-is: their CRCs must verify
v = json.load(open(os.path.join(R, "tomorrow", "tests", "ble_vectors.json")))
ok = all(parse_log.crc8(bytes.fromhex(h)[:19]) == bytes.fromhex(h)[19] for h in v["forecast_chunks_hex"] + [v["safe_hours_hex"]])
check(ok, "B4 forecast + safe-hours frames (tomorrow/tests/ble_vectors.json) carry valid CRCs (what the dashboard forwards)")
# guardian record via parse_log
gb = 0
for h, (st, scr, core100, tiers, worn) in G:
    g = parse_log.decode_grec(bytes.fromhex(h))
    if not g or g["g_state"] != st or g["g_screen"] != scr or g["g_tiers"] != tiers or g["g_worn"] != worn or (core100 and abs(g["g_core_c"] * 100 - core100) > 1):
        gb += 1
check(len(G) > 100 and gb == 0, f"parse_log.decode_grec == C guardian values on {len(G)} records")
print("TEST_DASHBOARD:", "FAIL" if fails else "PASS"); sys.exit(1 if fails else 0)
