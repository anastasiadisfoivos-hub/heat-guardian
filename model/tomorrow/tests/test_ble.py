"""BLE frames (R4 A5 opcodes 0x11, 0x14; B4 acceptance 4). B5's C must pass crc8_vectors.json and
ble_vectors.json (written by tests/make_vectors.py)."""
import json
import os

from tomorrow import ble_frame as bf, plan, demo

HERE = os.path.dirname(__file__)


def crc8_table_driven(data: bytes) -> int:
    """Independent implementation (256-entry table) to cross-check the bitwise one."""
    tab = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
        tab.append(c)
    c = 0
    for b in data:
        c = tab[c ^ b]
    return c


def test_crc8_vectors():
    with open(os.path.join(HERE, "crc8_vectors.json")) as f:
        v = json.load(f)
    assert len(v["vectors"]) == 10
    names = {x["name"] for x in v["vectors"]}
    assert {"all_zero_19", "all_ff_19", "check_123456789"} <= names
    for x in v["vectors"]:
        d = bytes.fromhex(x["data_hex"])
        assert bf.crc8(d) == x["crc"] == crc8_table_driven(d), x["name"]
    assert bf.crc8(b"123456789") == 0xF4          # published CRC-8/SMBUS check value


def demo_plan():
    return plan.make_plan(demo.demo_forecast(), demo.DEMO_DATE, "B")


def test_forecast_chunks_layout():
    p = demo_plan()
    fr = bf.forecast_chunks(p)
    assert len(fr) == 4 and all(len(f) == 20 for f in fr)
    for k, f in enumerate(fr):
        assert f[0] == 0x11 and f[19] == bf.crc8(f[:19])
        for j in range(6):
            h = 6 * k + j
            t, rh, fl = f[1 + 3 * j], f[2 + 3 * j], f[3 + 3 * j]
            hr = p["hours"][h]
            assert (t - 256 if t > 127 else t) == int(round(hr["t_in"]))
            assert rh == hr["rh_in"]
            assert fl & 1 == int(p["heat_day"]) and (fl >> 1) & 1 == int(p["night_heat"])
            assert (fl >> 2) & 1 == int(hr["safe"]) and (fl >> 3) & 3 == k and fl >> 5 == 0
    dec = bf.decode_forecast(fr)
    assert [d["safe"] for d in dec["hours"]] == [h["safe"] for h in p["hours"]]


def test_safe_hours_frame():
    p = demo_plan()
    f = bf.safe_hours_frame(p)
    assert len(f) == 20 and f[0] == 0x14 and f[19] == bf.crc8(f[:19])
    d = bf.decode_safe_hours(f)
    assert d["bitmap"] == p["safe_hours_bitmap"]
    for h in range(24):
        assert d["safe"][h] == p["hours"][h]["safe"] == (p["hours"][h]["advice"] == "OK" and p["details"]["is_day"][h] == 1)
    assert d["tag"] == "2026-07-14 B" and d["plan_id"] == 195


def test_bad_crc_rejected():
    p = demo_plan()
    f = bytearray(bf.safe_hours_frame(p)); f[5] ^= 1
    try:
        bf.decode_safe_hours(bytes(f))
    except ValueError:
        return
    raise AssertionError("bad CRC accepted")


def test_plan_hex_matches_frames():
    p = demo_plan()
    assert p["ble"]["forecast_chunks_hex"] == [x.hex() for x in bf.forecast_chunks(p)]
    assert p["ble"]["safe_hours_hex"] == bf.safe_hours_frame(p).hex()


def test_ble_vectors_file_current():
    """ble_vectors.json (the file B5 tests its C parser against) decodes to what it claims."""
    with open(os.path.join(HERE, "ble_vectors.json")) as f:
        v = json.load(f)
    fr = [bytes.fromhex(x) for x in v["forecast_chunks_hex"]]
    dec = bf.decode_forecast(fr)
    assert dec["hours"] == v["decoded_hours"]
    s = bf.decode_safe_hours(bytes.fromhex(v["safe_hours_hex"]))
    assert s["bitmap"] == v["safe_hours_bitmap"] and s["tag"] == v["tag"] and s["plan_id"] == v["plan_id"]
