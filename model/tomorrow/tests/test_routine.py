"""B4 <-> B5 routine-profile contract: B5 owns the format (guardian/c/hg_routine.h, STABLE FORMAT v1, 650 B)."""
import os
import shutil
import subprocess

import numpy as np
import pytest

from tomorrow.routine import RoutineTemplate, pack_band_profile, PROFILE_BYTES

HERE = os.path.dirname(os.path.abspath(__file__))
G = "/home/claude/hg_ai/guardian/c"
VEC = os.path.join(HERE, "routine_vector_b5.hex")


def vector():
    with open(VEC) as f:
        return bytes.fromhex(f.read().strip())


def test_header_says_650():
    with open(os.path.join(G, "hg_routine.h")) as f:
        h = f.read()
    assert "#define HG_ROUTINE_PACK_BYTES 650" in h and "typedef struct { float n, mean, m2; } hg_welford_t;" in h
    assert PROFILE_BYTES == 650


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not available")
def test_vector_is_b5_packer_output():
    """Rebuild the shared vector with B5's OWN C packer and compare byte for byte."""
    os.makedirs(os.path.join(HERE, "c", "build"), exist_ok=True)
    exe = os.path.join(HERE, "c", "build", "mrv")
    subprocess.run(["gcc", "-std=c99", "-Wall", "-I" + G, "-o", exe, os.path.join(HERE, "c", "make_routine_vector.c"),
                    os.path.join(G, "hg_routine.c"), os.path.join(G, "hg_util.c"), os.path.join(G, "hg_tables.c"), "-lm"],
                   check=True, capture_output=True)
    out = subprocess.run([exe], check=True, capture_output=True, text=True).stdout.strip()
    assert bytes.fromhex(out) == vector()


def test_decode_b5_vector():
    t = RoutineTemplate.from_band(vector())
    am = t.active_minutes
    assert np.isnan(am[3]), "hour 3 has n = 2 < 3: not learned"
    assert am[9] == pytest.approx(42.0) and am[7] == pytest.approx(20.0) and am[0] == pytest.approx(0.5)
    assert t.wake_minute == 435                      # median of wake_hist {420,425,430,435,440,445,450}
    assert t.bed_minute == 1380
    assert t.met[9] == pytest.approx(1.37) and t.met[0] == pytest.approx(0.7)
    assert t.max_quiet[0] == 60 and t.max_quiet[12] == 45
    assert "10 days learned" in t.source


def test_python_packer_matches_layout():
    b = pack_band_profile(np.full(24, 12.0), wake_hist=[450], sleep_valid=1)
    assert len(b) == 650 and b[:3] == b"RT\x01"
    RoutineTemplate.from_band(b)


@pytest.mark.parametrize("mutate", ["short", "magic", "xor"])
def test_bad_profile_rejected(mutate):
    b = bytearray(vector())
    if mutate == "short":
        b = b[:576]
    elif mutate == "magic":
        b[2] = 2
    else:
        b[100] ^= 0xFF
    with pytest.raises(ValueError):
        RoutineTemplate.from_band(bytes(b))
