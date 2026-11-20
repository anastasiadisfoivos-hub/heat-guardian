"""T4 — CRC-8 vectors (independent implementation) and 0x11/0x14 frames vs ARCHITECTURE §6 / R4 A5,
and against B5's C parser (guardian/c/hg_frames.c compiled read-only into tests/t4/build/t4_b5_driver).

Run: python3 /home/claude/hg_ai/tests/t4/t4_crc_frames.py      (prints a JSON summary, writes out/crc_frames.json)
"""
import json
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/home/claude/hg_ai")
from tomorrow import ble_frame as bf, plan, demo  # noqa: E402

DRIVER = os.path.join(HERE, "build", "t4_b5_driver")
VEC = "/home/claude/hg_ai/tomorrow/tests/crc8_vectors.json"
BLEV = "/home/claude/hg_ai/tomorrow/tests/ble_vectors.json"


def crc8_gf2(data: bytes) -> int:
    """Independent CRC-8: remainder of M(x)*x^8 mod P(x), P = x^8+x^2+x+1 (0x107), by long division on
    one big integer (no shifting register, no table) — a different algorithm from the builder's."""
    if not data:
        return 0
    m = int.from_bytes(data, "big") << 8
    P = 0x107
    while m.bit_length() > 8:
        m ^= P << (m.bit_length() - 9)
    return m


def c_driver(lines):
    r = subprocess.run([DRIVER], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True)
    return r.stdout.strip().splitlines()


def main():
    res = {}
    v = json.load(open(VEC))
    vecs = v["vectors"]
    names = [x["name"] for x in vecs]
    res["n_vectors"] = len(vecs)
    res["has_all_zero"] = any(set(bytes.fromhex(x["data_hex"])) == {0} and len(x["data_hex"]) > 0 for x in vecs)
    res["has_all_ff"] = any(set(bytes.fromhex(x["data_hex"])) == {0xFF} for x in vecs)
    res["check_value_123456789"] = hex(crc8_gf2(b"123456789"))
    bad_vec = [x["name"] for x in vecs if crc8_gf2(bytes.fromhex(x["data_hex"])) != x["crc"]
               or int(x["crc_hex"], 16) != x["crc"]]
    res["vectors_wrong_vs_independent"] = bad_vec
    # random agreement: builder python vs independent vs B5 C
    rnd = random.Random(20261112)
    datas = [bytes(rnd.randrange(256) for _ in range(rnd.randrange(0, 40))) for _ in range(3000)]
    datas += [bytes.fromhex(x["data_hex"]) for x in vecs]
    out = c_driver(["C " + d.hex() for d in datas])
    c_vals = [int(l.split()[1], 16) for l in out]
    res["crc_py_vs_indep_mismatch"] = sum(bf.crc8(d) != crc8_gf2(d) for d in datas)
    res["crc_C_vs_indep_mismatch"] = sum(c != crc8_gf2(d) for c, d in zip(c_vals, datas))
    res["crc_inputs_tested"] = len(datas)

    # frames from the demo plan
    p = plan.make_plan(demo.demo_forecast(), demo.DEMO_DATE, "B")
    fr = bf.forecast_chunks(p)
    sf = bf.safe_hours_frame(p)
    res["frame_lengths"] = [len(x) for x in fr] + [len(sf)]
    # my own decoder per B4 documented layout (flags bit0 heat, bit1 night, bit2 safe, bits3-4 chunk)
    per_hour = []
    for k, f in enumerate(fr):
        assert f[0] == 0x11 and crc8_gf2(f[:19]) == f[19]
        for j in range(6):
            t, rh, fl = f[1 + 3 * j], f[2 + 3 * j], f[3 + 3 * j]
            h = 6 * k + j
            hr = p["hours"][h]
            per_hour.append(((t ^ 0x80) - 0x80 == int(round(hr["t_in"])), rh == hr["rh_in"],
                             bool(fl & 4) == hr["safe"], bool(fl & 1) == p["heat_day"], bool(fl & 2) == p["night_heat"]))
    res["own_decode_all_fields_match"] = all(all(x) for x in per_hour)
    bm = int.from_bytes(sf[1:4], "little")
    res["bitmap_bits_eq_safe"] = all(bool(bm >> h & 1) == p["hours"][h]["safe"] == (p["hours"][h]["advice"] == "OK")
                                    for h in range(24))
    res["bitmap_eq_plan_field"] = bm == p["safe_hours_bitmap"]
    res["sf_crc_ok"] = crc8_gf2(sf[:19]) == sf[19]

    # B5 C parser on B4 frames
    def b5_parse(frames):
        lines = ["R"] + ["P " + x.hex() for x in frames]
        return c_driver(lines)[1:]
    out = b5_parse(fr)
    res["b5_parse_demo_chunks"] = [" ".join(l.split()[1:6]) for l in out]
    last = out[-1]
    data = bytes.fromhex(last.split("data=")[1])
    mism = []
    for h in range(24):
        t, rh, fl = data[3 * h], data[3 * h + 1], data[3 * h + 2]
        hr = p["hours"][h]
        if (t ^ 0x80) - 0x80 != int(round(hr["t_in"])) or rh != hr["rh_in"] or bool(fl & 4) != hr["safe"]:
            mism.append(h)
    res["b5_hours_mismatching_b4_plan"] = mism
    # same on the shared ble_vectors.json (the file B5's host_test claims to decode)
    bv = json.load(open(BLEV))
    out2 = b5_parse([bytes.fromhex(x) for x in bv["forecast_chunks_hex"]])
    res["b5_parse_ble_vectors"] = [" ".join(l.split()[1:6]) for l in out2]
    # does B5 decode a frame with chunk index in bits 4-5 (its own documented layout)?
    alt = []
    for k, f in enumerate(fr):
        b = bytearray(f)
        for j in range(6):
            b[3 + 3 * j] = (b[3 + 3 * j] & 0x07) | (k << 4)
        b[19] = crc8_gf2(bytes(b[:19]))
        alt.append(bytes(b))
    out3 = b5_parse(alt)
    res["b5_parse_if_chunk_in_bits4_5"] = [" ".join(l.split()[1:6]) for l in out3]
    out4 = c_driver(["P " + sf.hex()])
    res["b5_parse_safe_hours"] = out4[0].split(" data=")[0]
    # 0x14 corrupted CRC must be rejected
    bad = bytearray(sf); bad[2] ^= 0x01
    res["b5_rejects_bad_crc_0x14"] = c_driver(["P " + bytes(bad).hex()])[0].split()[1]

    # nonsense inputs to the encoder
    import copy
    q = copy.deepcopy(p)
    q["hours"][0]["t_in"] = float("nan")
    try:
        bf.forecast_chunks(q); res["encoder_nan_t_in"] = "accepted"
    except Exception as e:
        res["encoder_nan_t_in"] = "raises %s" % type(e).__name__
    q = copy.deepcopy(p); q["hours"][0]["t_in"] = -5.4; q["hours"][1]["t_in"] = 200
    f0 = bf.forecast_chunks(q)[0]
    res["encoder_neg_and_200"] = [(f0[1] ^ 0x80) - 0x80, (f0[4] ^ 0x80) - 0x80]
    q = copy.deepcopy(p); q["date"] = "2026-07-14"; q["home_class"] = "Β"   # Greek capital Beta
    res["tag_non_ascii"] = bf.safe_hours_frame(q)[5:19].rstrip(b"\0").decode("ascii")
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, "out", "crc_frames.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
