"""[B3-M4] Decision M4 (arch/DECISIONS.md) regression tests. Fail on commit 06bd7e9, pass after.
Run: python3 /home/claude/hg_ai/twin/tests/test_m4.py"""
import os
import sys

import numpy as np

TW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, TW)
import hg_twin as H  # noqa: E402
from hg_twin import BodyTwin  # noqa: E402

res = []


def check(name, ok, detail=""):
    res.append(ok); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def minute(t, tier, tod=600):
    t.ingest_minute(dict(t1_c=34.0, t2_c=31.5, t_air_c=24.0, hr_bpm=60, a_std_g=0.001, worn=2, minute_of_day=tod,
                         asleep=0, location=0, hr_valid=1, tier_on=tier))


def reading(t, t_read=37.0, core_now=36.6):
    t.ingest_reading(t_read, 0, 34.0, 2.5, core_now, 1)
    return t.commit_reading()


# M4.2 beta = 0.25 default
t = BodyTwin(); minute(t, 0); reading(t)
off = float(t.params["core_offset"])
exp = 0.25 * (37.0 + (H.ORAL_TO_CORE if getattr(H, "READING_MODE", 0) == 1 else 0.0) - 36.6) if hasattr(H, "ORAL_TO_CORE") else 0.1
check("M4.2 default beta 0.25: offset = 0.25 x (reading - core_now)", abs(off - exp) < 1e-6, f"offset={off:.4f}")

# M4.3 default = display-only: a flux-valid reading never moves the capped gap gain
t = BodyTwin(); minute(t, 0); reading(t)
check("M4.3 display-only default: capped gap gain (k_person) unchanged by a reading", t.params["k_person"] == np.float32(0.12),
      f"k={float(t.params['k_person']):.4f}")
# M4.3 sourced mode: reading converted oral -> core before learning
ok = hasattr(H, "ORAL_TO_CORE") and hasattr(H, "READING_MODE_SOURCED")
if ok:
    t = BodyTwin(reading_mode=H.READING_MODE_SOURCED); minute(t, 0); reading(t)
    kexp = 0.12 + 0.5 * ((37.0 + H.ORAL_TO_CORE - 34.0) / 2.5 - 0.12)
    ok = abs(float(t.params["k_person"]) - min(kexp, 0.40)) < 1e-5 and abs(float(t.params["core_offset"]) - 0.25 * (37.0 + H.ORAL_TO_CORE - 36.6)) < 1e-5
check("M4.3 sourced mode: oral->core offset applied before the gap-gain and offset rules", ok)

# M4.4 / F10: ignored during any alarm tier and for 30 min after
t = BodyTwin(); minute(t, 1); c = reading(t)
check("M4.4 reading during an alarm tier ignored", c == 0 and float(t.params["core_offset"]) == 0.0)
t = BodyTwin(); minute(t, 1)
for _ in range(29):
    minute(t, 0)
c = reading(t)
check("M4.4 reading 29 min after the tier ended ignored", c == 0 and float(t.params["core_offset"]) == 0.0)
minute(t, 0); minute(t, 0)
c = reading(t)
check("M4.4 reading 31 min after the tier ended accepted", c == 1 and float(t.params["core_offset"]) != 0.0)
# pending reading committed at the nightly update is also blocked during the hold-off
t = BodyTwin(); minute(t, 1); t.ingest_reading(37.0, 0, 34.0, 2.5, 36.6, 1); t.nightly_update()
check("M4.4 pending reading at nightly update during hold-off ignored", float(t.params["core_offset"]) == 0.0)

# M4.1 rename
src = open(os.path.join(TW, "c", "hg_twin.h")).read() + open(os.path.join(TW, "hg_twin.py")).read()
check("M4.1 'capped gap gain' naming in C header and Python", src.count("capped gap gain") >= 2 and "flux constant" not in src)

print(f"RESULT: {sum(res)} pass, {len(res) - sum(res)} fail"); sys.exit(0 if all(res) else 1)
