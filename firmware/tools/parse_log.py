#!/usr/bin/env python3
"""Heat Guardian 08_logger: parse wear-test recordings into a table.

Reads any mix of
  * text captures of the USB serial / BLE UART stream (live 1 Hz lines, "dump"/"dumpmin" output,
    with or without Arduino Serial Monitor timestamps in front of each line),
  * binary record files copied off the band (/log/sNNNN.bin, /log/min.bin: 24-byte records),
  * events.txt / events2.txt / events_<gen>.txt (0.9.10 FS-HEAL),
and writes one parquet (or CSV) with the column names the Virtual Elders sensor model uses
(T1, T2, T_air_meas, RH_meas, HR_meas, hr_quality, PI, a_std_g, zangle_deg, button, charging, marker)
plus the bookkeeping columns. Every record's CRC-8 is verified; gaps in the 1 Hz stream are reported.

Record layout: fw/08_logger/log_format.h (24 bytes, little-endian, CRC-8 poly 0x07 over bytes 0..22). Format v2 (1.1.2+)
stores CRC ^ 0xFD and carries the z-angle in 0.01 deg and, in minute records, the whole-minute a_std (column
a_std_min_g, = the 09 guardian's input); v1 files (1.1.1) parse as before (a_std_min_g NaN). Column fmt = 1 or 2.

Usage:
  python3 parse_log.py capture.txt [more files...] -o wear.parquet [--report gaps.md] [--raw-out raw.parquet]
"""
import argparse
import os
import re
import struct
import sys

import numpy as np
import pandas as pd

REC_SIZE = 24
REC_STRUCT = struct.Struct("<IhhhBBBHHbBBBH")   # v1: 23 bytes, then the CRC byte
REC_V2 = struct.Struct("<IhhhBBBHHhBBH")         # v2: ..., 12 marker|hr_q<<4, ..., 17-18 z x100, 19 flags, 20 dc8, 21-22 aux
assert REC_STRUCT.size == 23 and REC_V2.size == 23
V2_XOR = 0xFD
T_ABSENT = 0x7FFF
RAW_BLOCK = 308          # u32 t_first_ms, u16 n, u16 fs, 100 x 3 B big-endian IR
MARK_NAMES = ["none", "donned", "loose", "off", "shower", "out", "home", "oral", "help", "button",
              "boot", "time", "file", "guardian"]
M_GUARDIAN = 13   # 09_guardian: per-minute guardian record (fw/09_guardian/hg_fw.c hg_fw_pack_grec)
F_BUTTON, F_CHARGING, F_BLE, F_IMPACT, F_MARKER, F_TIME, F_MINUTE, F_LOWBAT = (1 << i for i in range(8))
M_ORAL, M_BOOT, M_FILE = 7, 10, 12
MIN_AUX_MARKERS = (M_ORAL, M_BOOT, M_FILE)   # v2 minute records keep these markers' value in bytes 21-22 (no a_std_min then)

REC_RE = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F]{48})(?![0-9a-fA-F])")
RAW_RE = re.compile(r"(?:^|\s)R([0-3])([0-9a-fA-F]{154})(?![0-9a-fA-F])")
FILE_RE = re.compile(r"#\s*FILE\s+(\S+)\s+size=(\d+)")
EVENTS_GEN_RE = re.compile(r"events_[1-9][0-9]{0,4}\.txt")   # 0.9.10 FS-HEAL: one events log per heal generation
END_RE = re.compile(r"#\s*END\s+(\S+)")
TIME_RE = re.compile(r"TIME boot=(\d+) t_ms=(\d+) unix=(\d+)")
BOOT_RE = re.compile(r"\bboot=(\d+)")


def crc8(data: bytes) -> int:
    """CRC-8/SMBUS: poly 0x07, init 0, no reflection (same as hg_crc8 in log_format.h)."""
    c = 0
    for b in data:
        c ^= b
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c


def pack_record(t_ms, t1=T_ABSENT, t2=T_ABSENT, tair=T_ABSENT, rh=255, hr=0, hr_q=255, pi=0, astd=0,
                zangle_c100=0, flags=0, marker=0, dc8=0, aux=0, astd_min=0xFFFF) -> bytes:
    """Python twin of hg_rec_pack (format v2; used by sim_stream.py and the tests). Minute records carry astd_min
    in bytes 21-22, 1 Hz records aux."""
    mq = (marker & 15) | ((15 if hr_q > 14 else hr_q) << 4)
    body = REC_V2.pack(t_ms & 0xFFFFFFFF, t1, t2, tair, rh, hr, mq, pi, astd, zangle_c100, flags, dc8,
                       astd_min if (flags & F_MINUTE and marker not in MIN_AUX_MARKERS) else aux)
    return body + bytes([crc8(body) ^ V2_XOR])


def pack_record_v1(t_ms, t1=T_ABSENT, t2=T_ABSENT, tair=T_ABSENT, rh=255, hr=0, hr_q=255, pi=0, astd=0,
                   zangle=0, flags=0, marker=0, dc8=0, aux=0) -> bytes:
    """the 1.1.1 packer (format v1, z in whole degrees), for the compatibility tests"""
    body = REC_STRUCT.pack(t_ms & 0xFFFFFFFF, t1, t2, tair, rh, hr, hr_q, pi, astd, zangle, flags, marker, dc8, aux)
    return body + bytes([crc8(body)])


def decode_grec(b: bytes):
    """09_guardian guardian record (marker 13): state, screen, core, sd, f20, tiers... or None if not one / bad CRC."""
    if len(b) != 24 or b[19] != M_GUARDIAN or crc8(b[:23]) != b[23]:
        return None
    u16 = lambda o: b[o] | (b[o + 1] << 8)
    return dict(t_ms=struct.unpack("<I", b[0:4])[0], g_core_c=(u16(4) / 100.0 if u16(4) else np.nan),
                g_sd_c=(np.nan if b[6] == 255 else b[6] / 100.0), g_f20_c=(u16(7) / 100.0 if u16(7) else np.nan),
                g_state=b[9], g_level=b[10] & 15, g_tiers=b[10] >> 4, g_worn=b[11] & 3, g_home_out=(b[11] >> 2) & 3,
                g_night_heat=(b[11] >> 4) & 1, g_nudge=(b[11] >> 5) & 1, g_family=(b[11] >> 6) & 1, g_why=b[12],
                g_routine=b[13], g_check_reason=b[14], g_screen=b[15], g_haptic=b[16] & 15, g_hr_valid=(b[16] >> 4) & 1,
                g_flux_valid=(b[16] >> 5) & 1, g_valid=(b[16] >> 6) & 1, g_check_min=b[17],
                g_strain=(np.nan if b[20] == 255 else b[20] / 20.0), g_minute_counter=u16(21))


def unpack_record(b: bytes):
    """-> (fields, ok, ver). fields = (t_ms, t1, t2, tair, rh, hr, hr_q, pi, astd, zangle_c100, flags, marker, dc8, aux,
    astd_min) in v2 units for both versions (v1: z x 100, astd_min 0xFFFF). ok = the CRC matches v1 or v2."""
    c = crc8(b[:23])
    if c == b[23]:
        t, t1, t2, ta, rh, hr, q, pi, astd, z, fl, mk, dc8, aux = REC_STRUCT.unpack(b[:23])
        return (t, t1, t2, ta, rh, hr, q, pi, astd, z * 100, fl, mk, dc8, aux, 0xFFFF), True, 1
    t, t1, t2, ta, rh, hr, mq, pi, astd, z, fl, dc8, slot = REC_V2.unpack(b[:23])
    q = mq >> 4
    q = 255 if q == 15 else q
    aux, amin = (0, slot) if (fl & F_MINUTE and (mq & 15) not in MIN_AUX_MARKERS) else (slot, 0xFFFF)
    return (t, t1, t2, ta, rh, hr, q, pi, astd, z, fl, mq & 15, dc8, aux, amin), (c ^ V2_XOR) == b[23], 2


class Parser:
    def __init__(self):
        self.rows = []
        self.grows = []             # 09 guardian records
        self.raw_blocks = []        # (source, boot, t_first_ms, n, fs, samples)
        self.time_syncs = {}        # boot -> list of (t_ms, unix)
        self.crc_errors = 0
        self.crc_error_examples = []
        self.lines = 0
        self.unparsed = 0

    # ---------------------------------------------------------------- records
    def add_record(self, b: bytes, source: str, file: str, ctx: dict):
        if len(b) == 24 and b[19] == M_GUARDIAN and crc8(b[:23]) == b[23]:   # 09_guardian minute record: its own table
            g = decode_grec(b)
            g.update(source=source, file=file, boot=ctx.get("boot", -1))
            self.grows.append(g)
            return
        f, ok, ver = unpack_record(b)
        t_ms, t1, t2, tair, rh, hr, hr_q, pi, astd, zc, flags, marker, dc8, aux, amin = f
        if not ok:
            self.crc_errors += 1
            if len(self.crc_error_examples) < 10:
                self.crc_error_examples.append(f"{source}:{file}: {b.hex()}")
            return
        is_min = bool(flags & F_MINUTE)
        if marker in (M_BOOT, M_FILE):
            ctx["boot"] = aux
        self.rows.append(dict(
            source=source, file=file, boot=ctx.get("boot", -1), t_ms=t_ms, is_minute=is_min, fmt=ver,
            T1=np.nan if t1 == T_ABSENT else t1 / 100.0,
            T2=np.nan if t2 == T_ABSENT else t2 / 100.0,
            T_air_meas=np.nan if tair == T_ABSENT else tair / 100.0,
            RH_meas=np.nan if rh == 255 else float(rh),
            HR_meas=np.nan if hr == 0 else float(hr),
            hr_quality=np.nan if hr_q == 255 else float(hr_q),
            PI=pi / 100.0,
            a_std_g=np.nan if astd == 0xFFFF else astd / 1e4,
            a_std_min_g=np.nan if amin == 0xFFFF else amin / 1e4,
            zangle_deg=zc / 100.0,
            button=int(bool(flags & F_BUTTON)), charging=int(bool(flags & F_CHARGING)),
            ble=int(bool(flags & F_BLE)), impact=int(bool(flags & F_IMPACT)),
            marker_present=int(bool(flags & F_MARKER)), time_valid=int(bool(flags & F_TIME)),
            low_batt_mode=int(bool(flags & F_LOWBAT)),
            marker=marker, marker_name=MARK_NAMES[marker] if marker < len(MARK_NAMES) else "?",
            marker_value=(aux / 100.0 if marker == M_ORAL else (float(aux) if marker in (M_BOOT, M_FILE) else np.nan)),
            ir_dc=np.nan if is_min else dc8 * 1024.0,
            red_dc=np.nan if marker in (M_ORAL, M_BOOT, M_FILE) or aux == 0 or (is_min and (marker or ver == 2)) else aux * 4.0,
            vbat=(2.0 + dc8 / 100.0) if (is_min and dc8) else np.nan,
        ))

    # ---------------------------------------------------------------- inputs
    def parse_text(self, path: str):
        source = os.path.basename(path)
        live_ctx = {"boot": -1}
        file_ctx = None
        cur_file = None
        raw_parts = {}              # (file or live) -> [quarters]
        with open(path, "r", errors="replace") as fh:
            for line in fh:
                self.lines += 1
                s = line.strip()
                if not s:
                    continue
                m = FILE_RE.search(s)
                if m:
                    cur_file = m.group(1)
                    file_ctx = {"boot": -1}
                    continue
                if END_RE.search(s):
                    cur_file, file_ctx = None, None
                    continue
                if "#" in s or s.startswith("E "):
                    t = TIME_RE.search(s)
                    if t:
                        self.time_syncs.setdefault(int(t.group(1)), []).append((int(t.group(2)), int(t.group(3))))
                    if "#" in s and cur_file is None:     # live comment lines carry boot=N
                        bm = BOOT_RE.search(s)
                        if bm:
                            live_ctx["boot"] = int(bm.group(1))
                    continue
                r = RAW_RE.search(s)
                if r:
                    key = cur_file or "live"
                    q, data = int(r.group(1)), bytes.fromhex(r.group(2))
                    parts = raw_parts.setdefault(key, [])
                    if q == 0:
                        parts.clear()
                    if len(parts) == q:
                        parts.append(data)
                    else:
                        parts.clear()   # out of order: drop this block
                    if len(parts) == 4:
                        self._raw_block(b"".join(parts), source + ":" + key, (file_ctx or live_ctx).get("boot", -1))
                        parts.clear()
                    continue
                m = REC_RE.search(s)
                if m:
                    ctx = file_ctx if cur_file else live_ctx
                    self.add_record(bytes.fromhex(m.group(1)), "dump" if cur_file else "live",
                                    cur_file or source, ctx)
                    continue
                self.unparsed += 1

    def _raw_block(self, blk: bytes, source: str, boot: int):
        t0, n, fs = struct.unpack("<IHH", blk[:8])
        n = min(n, 100)
        ir = [int.from_bytes(blk[8 + 3 * i: 11 + 3 * i], "big") for i in range(n)]
        self.raw_blocks.append((source, boot, t0, n, fs, ir))

    def parse_bin(self, path: str):
        name = os.path.basename(path)
        data = open(path, "rb").read()
        if name.startswith("r") and name.endswith(".bin") and name != "min.bin":
            for i in range(0, len(data) - RAW_BLOCK + 1, RAW_BLOCK):
                self._raw_block(data[i:i + RAW_BLOCK], name, -1)
            return
        ctx = {"boot": -1}
        if len(data) % REC_SIZE:
            print(f"warning: {name}: {len(data)} bytes is not a multiple of 24 (trailing {len(data) % REC_SIZE} B ignored)")
        for i in range(0, len(data) - REC_SIZE + 1, REC_SIZE):
            self.add_record(data[i:i + REC_SIZE], "bin", name, ctx)

    def parse_events(self, path: str):
        with open(path, "r", errors="replace") as fh:
            for line in fh:
                t = TIME_RE.search(line)
                if t:
                    self.time_syncs.setdefault(int(t.group(1)), []).append((int(t.group(2)), int(t.group(3))))

    def parse(self, path: str):
        base = os.path.basename(path)
        if base.endswith(".bin"):
            self.parse_bin(path)
        elif base in ("events.txt", "events2.txt") or EVENTS_GEN_RE.fullmatch(base):   # 0.9.8: events2.txt; 0.9.10 FS-HEAL: events_<gen>.txt
            self.parse_events(path)
        else:
            self.parse_text(path)

    # ---------------------------------------------------------------- output
    def table(self) -> pd.DataFrame:
        cols = ["source", "file", "boot", "t_ms", "is_minute", "unix_s", "time_utc", "T1", "T2", "T_air_meas",
                "RH_meas", "HR_meas", "hr_quality", "PI", "a_std_g", "a_std_min_g", "zangle_deg", "button", "charging", "ble",
                "impact", "marker_present", "time_valid", "low_batt_mode", "marker", "marker_name",
                "marker_value", "ir_dc", "red_dc", "vbat", "fmt"]
        if not self.rows:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(self.rows)
        # one row per (boot, t_ms, is_minute): the same record can arrive live and in a dump
        df["_pri"] = df["source"].map({"bin": 0, "dump": 1, "live": 2})
        df = df.sort_values(["boot", "is_minute", "t_ms", "_pri"]).drop_duplicates(["boot", "t_ms", "is_minute", "marker"], keep="first")
        df = df.drop(columns="_pri")
        # file-header records (marker 12) are bookkeeping, not samples
        df = df[df["marker"] != M_FILE].copy()
        unix = np.full(len(df), np.nan)
        for boot, syncs in self.time_syncs.items():
            t_sync, u_sync = syncs[-1]      # latest sync of that boot wins (millis() is continuous within a boot)
            m = (df["boot"] == boot).to_numpy()
            unix[m] = u_sync + (df["t_ms"].to_numpy()[m] - t_sync) / 1000.0
        df["unix_s"] = unix
        df["time_utc"] = pd.to_datetime(df["unix_s"], unit="s", utc=True)
        return df[cols].reset_index(drop=True)

    def raw_table(self) -> pd.DataFrame:
        rows = []
        for source, boot, t0, n, fs, ir in self.raw_blocks:
            step = 1000.0 / fs if fs else 10.0
            for i, v in enumerate(ir):
                rows.append((source, boot, t0 + i * step, v))
        return pd.DataFrame(rows, columns=["source", "boot", "t_ms", "ir"])


def gap_report(df: pd.DataFrame, max_list=20):
    """1 Hz continuity per boot: a gap = consecutive records more than 1.5 s apart."""
    out = []
    sec = df[~df["is_minute"]]
    for boot, g in sec.groupby("boot"):
        t = np.sort(g["t_ms"].to_numpy(dtype=np.int64))
        if len(t) == 0:
            continue
        d = np.diff(t)
        idx = np.where(d > 1500)[0]
        missing = int(np.sum(np.round(d[idx] / 1000.0) - 1))
        span = (t[-1] - t[0]) / 1000.0 + 1
        out.append(dict(boot=int(boot), records=int(len(t)), first_t_ms=int(t[0]), last_t_ms=int(t[-1]),
                        gaps=int(len(idx)), missing_s=missing, coverage_pct=100.0 * len(t) / span if span > 0 else 100.0,
                        gap_list=[(int(t[i]), int(t[i + 1]), int(round(d[i] / 1000.0) - 1)) for i in idx[:max_list]]))
    return out


def summarize(p: Parser, df: pd.DataFrame, gaps) -> str:
    lines = []
    sec, mins = df[~df["is_minute"]], df[df["is_minute"]]
    lines.append(f"records: {len(sec)} x 1 Hz, {len(mins)} x 1-min summaries; CRC errors: {p.crc_errors}; "
                 f"unparsed lines: {p.unparsed}; raw blocks: {len(p.raw_blocks)}")
    for g in gaps:
        lines.append(f"boot {g['boot']}: {g['records']} records, t_ms {g['first_t_ms']}..{g['last_t_ms']}, "
                     f"{g['gaps']} gaps, {g['missing_s']} s missing, coverage {g['coverage_pct']:.2f} %")
        for a, b, n in g["gap_list"]:
            lines.append(f"    gap after t_ms={a}: next t_ms={b} ({n} s missing)")
    if len(sec):
        lines.append("sensor availability (1 Hz): " + ", ".join(
            f"{c} {100.0 * sec[c].notna().mean():.1f}%" for c in ["T1", "T2", "T_air_meas", "RH_meas", "HR_meas", "a_std_g"]))
        q = sec["hr_quality"].value_counts(dropna=False).sort_index()
        lines.append("hr_quality counts: " + ", ".join(f"{k}: {v}" for k, v in q.items()))
    mk = df[(df["marker"] > 0)]
    if len(mk):
        lines.append("markers: " + ", ".join(f"{r.marker_name}@{r.t_ms}" for r in mk.itertuples()))
    vb = mins["vbat"].dropna()
    if len(vb):
        lines.append(f"battery (minute records): {vb.iloc[0]:.2f} V -> {vb.iloc[-1]:.2f} V over {len(vb)} min")
    if p.time_syncs:
        lines.append("time syncs: " + ", ".join(f"boot {b}: unix {s[-1][1]} at t_ms {s[-1][0]}" for b, s in p.time_syncs.items()))
    else:
        lines.append("time syncs: none (unix_s is empty; send 'time <unix>' on the band)")
    if p.crc_error_examples:
        lines.append("CRC error examples: " + "; ".join(p.crc_error_examples[:3]))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", default="wear_log.parquet", help=".parquet or .csv")
    ap.add_argument("--report", help="write the summary + gap report to this file")
    ap.add_argument("--raw-out", help="write raw IR samples (from raw captures) to this parquet/csv")
    ap.add_argument("--guardian-out", help="09_guardian: write the per-minute guardian records to this parquet/csv")
    a = ap.parse_args(argv)
    p = Parser()
    for path in a.inputs:
        p.parse(path)
    df = p.table()
    gaps = gap_report(df)
    text = summarize(p, df, gaps)
    print(text)
    if a.out.endswith(".csv"):
        df.to_csv(a.out, index=False)
    else:
        df.to_parquet(a.out, index=False)
    print(f"wrote {len(df)} rows to {a.out}")
    if a.raw_out and p.raw_blocks:
        rt = p.raw_table()
        rt.to_csv(a.raw_out, index=False) if a.raw_out.endswith(".csv") else rt.to_parquet(a.raw_out, index=False)
        print(f"wrote {len(rt)} raw samples to {a.raw_out}")
    if a.guardian_out and p.grows:
        gd = pd.DataFrame(p.grows).drop_duplicates(["boot", "t_ms"])
        gd.to_csv(a.guardian_out, index=False) if a.guardian_out.endswith(".csv") else gd.to_parquet(a.guardian_out, index=False)
        print(f"wrote {len(gd)} guardian minutes to {a.guardian_out}")
    if a.report:
        with open(a.report, "w") as fh:
            fh.write(text + "\n")
    return p, df, gaps


if __name__ == "__main__":
    main()
