"""Virtual Elders population run (SIMULATION).

python -I -m velders.run --n 500 --days 10 --out /home/claude/hg_ai/sim/data/ --workers 2

Writes persons.parquet, minutes_all.parquet (one row group per person), ppg_1hz_all.parquet,
events_all.parquet and README.md. Never decides the dev/sealed split. Prints sha256 of every file.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import SEED
from .persons import draw_persons


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def write_persons(n: int, out: str, seed: int = SEED) -> str:
    df = draw_persons(n, seed)
    path = os.path.join(out, "persons.parquet")
    table = pa.Table.from_pandas(df, preserve_index=False)
    table = table.replace_schema_metadata({b"label": b"SIMULATION", b"generator": b"velders.persons.draw_persons",
                                           b"seed": str(seed).encode(), b"n": str(n).encode()})
    pq.write_table(table, path, compression="zstd")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--out", default="/home/claude/hg_ai/sim/data/")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--persons-only", action="store_true")
    ap.add_argument("--suffix", default="", help='e.g. "_v2": writes minutes_dev_v2.parquet etc. (v1 files kept)')
    ap.add_argument("--dev-only", action="store_true", help="simulate DEV persons only (every sealed id of sets 1-4 skipped)")
    ap.add_argument("--first", type=int, default=0, help="debug: only simulate the first k persons")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    pp = os.path.join(a.out, "persons.parquet")
    if not os.path.exists(pp):
        # first ever run only; after the seal (model/sealed_hg2.json) persons.parquet is never rewritten
        pp = write_persons(a.n, a.out, a.seed)
    print(f"persons.parquet sha256 {sha256(pp)} (not rewritten)")
    if a.persons_only:
        return 0
    from .population import run_population
    run_population(a, t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
