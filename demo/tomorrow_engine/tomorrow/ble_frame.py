"""BLE frames phone -> band for the Tomorrow plan (R4 A5 opcodes 0x11, 0x14; ARCHITECTURE §6).

Every CMD frame is EXACTLY 20 bytes: byte 0 = opcode, byte 19 = CRC-8 over bytes 0..18.

CRC-8: polynomial 0x07, init 0x00, no reflection, no final XOR (CRC-8/SMBUS); check("123456789") = 0xF4.

0x11 FORECAST chunk (4 chunks, hours 6k..6k+5 in chunk k):
    off 0      u8  0x11
    off 1..18  6 x { i8 T_in degC (rounded, clamped -128..127), u8 RH_in % (0..100), u8 flags }
    off 19     u8  CRC-8
    flags: bit0 heat-day, bit1 night-heat, bit2 safe-hour, bits3-4 chunk index k (0..3, the same in
           all six flag bytes of a chunk), bits5-7 = 0.
    RESOLVED CONFLICT: R4 A5 lists "u8 chunk, u8 total, 18 B" as a 20-B body *plus* opcode and CRC
    = 22 B, which breaks the 20-B rule of the same section. The chunk index therefore lives in flag
    bits 3-4 and the total is fixed at 4 (24 h). Reported in REPORT_TOMORROW.md.

0x14 SAFE_HOURS:
    off 0      u8  0x14
    off 1..3   24-bit bitmap, little-endian: bit h (h = 0..23) of the u24 = hours[h].safe
    off 4      u8  plan id (day-of-year of the plan date, mod 256)
    off 5..18  14 B ASCII tag, NUL-padded: "<date> <home class>" (e.g. "2026-07-14 B"), plus " C" when the plan
               was made from a stale cached forecast (>= 20 h old; R3 §5 "forecast from last night")
    off 19     u8  CRC-8
"""
from __future__ import annotations

OP_FORECAST = 0x11
OP_SAFE_HOURS = 0x14
FRAME_LEN = 20
N_CHUNKS = 4


def crc8(data: bytes, poly: int = 0x07, init: int = 0x00) -> int:
    c = init
    for b in data:
        c ^= b
        for _ in range(8):
            c = ((c << 1) ^ poly) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c


def _seal(body: bytes) -> bytes:
    assert len(body) == FRAME_LEN - 1
    return body + bytes([crc8(body)])


def _i8(x: float) -> int:
    v = int(round(float(x)))
    v = max(-128, min(127, v))
    return v & 0xFF


def hour_flags(plan: dict, h: int) -> int:
    hr = plan["hours"][h]
    f = (1 if plan["heat_day"] else 0) | (2 if plan["night_heat"] else 0) | (4 if hr["safe"] else 0)
    return f | ((h // 6) << 3)


def forecast_chunks(plan: dict) -> list[bytes]:
    hours = plan["hours"]
    assert len(hours) == 24
    frames = []
    for k in range(N_CHUNKS):
        body = bytearray([OP_FORECAST])
        for h in range(6 * k, 6 * k + 6):
            body += bytes([_i8(hours[h]["t_in"]), max(0, min(100, int(round(hours[h]["rh_in"])))), hour_flags(plan, h)])
        frames.append(_seal(bytes(body)))
    return frames


def safe_bitmap(plan: dict) -> int:
    return sum(1 << h for h, hr in enumerate(plan["hours"]) if hr["safe"])


def plan_id(date_str: str) -> int:
    import datetime as _dt
    return _dt.date.fromisoformat(date_str).timetuple().tm_yday & 0xFF


def safe_hours_frame(plan: dict, tag: str | None = None) -> bytes:
    bm = safe_bitmap(plan)
    if tag is None:
        tag = plan["date"] + " " + plan.get("home_class", "") + (" C" if plan.get("stale_forecast") else "")
    t = tag.encode("ascii", "replace")[:14].ljust(14, b"\x00")
    body = bytes([OP_SAFE_HOURS]) + bm.to_bytes(3, "little") + bytes([plan_id(plan["date"])]) + t
    return _seal(body)


# ---- decoders (mirror of what B5's C parser must do; used by the tests) ------------------
def decode_forecast(frames: list[bytes]) -> dict:
    out = [None] * 24
    for fr in frames:
        if len(fr) != FRAME_LEN or fr[0] != OP_FORECAST or crc8(fr[:19]) != fr[19]:
            raise ValueError("bad 0x11 frame")
        k = (fr[3] >> 3) & 0x3
        for j in range(6):
            t, rh, fl = fr[1 + 3 * j: 4 + 3 * j]
            if (fl >> 3) & 0x3 != k:
                raise ValueError("inconsistent chunk index")
            out[6 * k + j] = {"t_in": t - 256 if t > 127 else t, "rh_in": rh,
                              "heat_day": bool(fl & 1), "night_heat": bool(fl & 2), "safe": bool(fl & 4)}
    return {"hours": out}


def decode_safe_hours(fr: bytes) -> dict:
    if len(fr) != FRAME_LEN or fr[0] != OP_SAFE_HOURS or crc8(fr[:19]) != fr[19]:
        raise ValueError("bad 0x14 frame")
    bm = int.from_bytes(fr[1:4], "little")
    return {"bitmap": bm, "safe": [bool(bm >> h & 1) for h in range(24)], "plan_id": fr[4],
            "tag": fr[5:19].rstrip(b"\x00").decode("ascii")}
