"""[B3-M9] Decision M9.5: Guardian design-A calm-f20 baseline persisted in the Twin file. Fails on c4ceac4, passes after.
Run: python3 /home/claude/hg_ai/twin/tests/test_m9.py"""
import os
import struct
import sys
import zlib

import numpy as np

TW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, TW)
import hg_twin as H  # noqa: E402
from hg_twin import BodyTwin  # noqa: E402

res = []


def check(name, ok, detail=""):
    res.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def resign(b):
    b = bytearray(b); b[-4:] = struct.pack("<I", zlib.crc32(bytes(b[:-4])) & 0xFFFFFFFF); return bytes(b)


try:
    t = BodyTwin(); t.set_calm(37.12, 5)
    blob = t.to_bytes(bytes(650), 3)
    t2, r, sc, ok = BodyTwin.from_bytes(blob)
    check("M9.5 calm f20 + count survive pack/unpack", ok and abs(float(t2.calm_f20) - 37.12) < 1e-5 and t2.calm_n == 5)
    check("M9.5 file with B5's 650-B routine = 864 B <= 900 (v4, B5-v7: +8 B Exception block)", len(blob) == 864, f"{len(blob)} B")
    check("M9.5 round trip byte-identical", t2.to_bytes(r, sc) == blob)
    t = BodyTwin(); t.set_calm(39.0, 2); a = (float(t.calm_f20), t.calm_n)
    t.set_calm(float("nan"), 4); b = (t.calm_f20, t.calm_n)
    t.set_calm(37.0, 0); c = (t.calm_f20, t.calm_n)
    check("M9.5 setter clamps to [36.8, 37.7]; NaN or n=0 -> empty", abs(a[0] - 37.7) < 1e-6 and a[1] == 2 and np.isnan(b[0]) and b[1] == 0 and np.isnan(c[0]) and c[1] == 0)
    off = H.CALM_OFFSET
    for nm, (v, n) in {"n>0 with NaN": (float("nan"), 3), "n>0 out of bounds": (38.5, 3), "n=0 with a value": (37.0, 0)}.items():
        bb = bytearray(BodyTwin().to_bytes(b"", 0)); bb[off:off + 5] = struct.pack("<fB", v, n)
        _, _, _, ok = BodyTwin.from_bytes(resign(bb))
        check(f"M9.5 inconsistent calm block rejected ({nm})", not ok)
    # v2 file (no calm block) still loads, calm empty -> migration
    t = BodyTwin(); t.params["rest_hr"] = np.float32(61.0)
    v3 = bytearray(t.to_bytes(b"\x01\x02", 9))
    v2 = v3[:off] + v3[off + 13:]   # v4 -> v2: drop calm (5 B) + Exception (8 B) blocks
    struct.pack_into("<IHH", v2, 0, H.MAGIC, 2, len(v2))
    t2, r, sc, ok = BodyTwin.from_bytes(resign(v2))
    check("M9.5 version-2 file still accepted, calm empty", ok and t2.params["rest_hr"] == np.float32(61.0) and t2.calm_n == 0 and r == b"\x01\x02" and sc == 9)
    t = BodyTwin(); t.set_calm(37.3, 7); t.nightly_update(); t.nightly_update()
    check("M9.5 calm untouched by nightly Twin updates (owned by the Guardian)", abs(float(t.calm_f20) - 37.3) < 1e-5 and t.calm_n == 7)
    # B5-v7 (manager item 2): Exception sums persisted (v4), C == Python layout, corrupt blocks rejected, v3 migrates
    eo = off + 5
    t = BodyTwin(); t.set_exc(4321.25, 123.5); t.set_calm(37.25, 3); blob = t.to_bytes(bytes(650), 11)
    t2, r, sc, ok = BodyTwin.from_bytes(blob)
    check("B5-v7 Exception sums survive pack/unpack (864 B)", ok and len(blob) == 864 and t2.get_exc() == (np.float32(4321.25), np.float32(123.5), 1) and sc == 11)
    for nm, (x, y) in {"NaN": (float("nan"), 1.0), "inf": (1.0, float("inf")), "sxx<0": (-1.0, 0.0), "sxx>1e7": (2e7, 0.0), "sxy<-1e7": (1.0, -2e7)}.items():
        bb = bytearray(BodyTwin().to_bytes(b"", 0)); bb[eo:eo + 8] = struct.pack("<ff", x, y)
        t2, _, _, ok = BodyTwin.from_bytes(resign(bb))
        tt = BodyTwin(); tt.set_exc(x, y)
        check(f"B5-v7 corrupt Exception block rejected + setter empties ({nm})", not ok and tt.get_exc()[2] == 0 and tt.exc_sxx == 0)
    t = BodyTwin(); t.set_calm(37.4, 6); t.set_exc(99.0, 9.0); t.params["rest_hr"] = np.float32(63.0)
    v4 = bytearray(t.to_bytes(b"\x03\x04\x05", 5)); v3b = v4[:eo] + v4[eo + 8:]
    struct.pack_into("<IHH", v3b, 0, H.MAGIC, 3, len(v3b))
    t2, r, sc, ok = BodyTwin.from_bytes(resign(v3b))
    check("B5-v7 version-3 file still accepted: calm kept, Exception empty", ok and t2.calm_n == 6 and t2.get_exc()[2] == 0 and r == b"\x03\x04\x05" and sc == 5)
    bb = bytearray(blob); bb[eo + 2] ^= 0x40
    check("B5-v7 CRC covers the Exception block", not BodyTwin.from_bytes(bytes(bb))[3])
except AttributeError as e:
    check("M9.5 calm API present", False, str(e)[:80])

print(f"RESULT: {sum(res)} pass, {len(res) - sum(res)} fail"); sys.exit(0 if all(res) else 1)
