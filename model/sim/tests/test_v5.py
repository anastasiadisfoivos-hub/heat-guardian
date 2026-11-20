"""Virtual Elders v5 (B1-v5) switch tests: v4 unchanged when off, v5 offsets deterministic with the frozen SDs. DEV seeds only."""
import importlib, os, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); SIM = os.path.dirname(HERE)
sys.path.insert(0, SIM)


def _offsets(version):
    code = ("import numpy as np, json; from velders import body as B; from velders.protocols import dev_persons_df; "
            "s = dev_persons_df().seed.values; a, b = B.v5_skin_offsets(s); print(json.dumps([B.V5 != {}, float(np.std(a)), float(np.std(b)), "
            "float(np.abs(a).max()), float(a[:3].sum())]))")
    env = dict(os.environ, HG_SIM_VERSION=version)
    out = subprocess.run([sys.executable, "-c", code], cwd=SIM, env=env, capture_output=True, text=True, check=True).stdout
    import json
    return json.loads(out)


def test_v4_default_has_no_offsets():
    on, sa, sb, mx, _ = _offsets("v4")
    assert not on and sa == 0.0 and sb == 0.0


def test_v5_offsets_frozen_sd_and_deterministic():
    on, sa, sb, mx, s3 = _offsets("v5")
    assert on
    assert abs(sa - 0.36) < 0.04 and abs(sb - 0.35) < 0.04
    assert mx <= 3.0 * 0.36 + 1e-9
    assert s3 == _offsets("v5")[4]


def test_v5_body_physics_unchanged():
    """V5_FROZEN has no lowercase (person-parameter) keys: the energy balance of TwoNodeOlder is the v4 one"""
    from velders import body as B
    assert not [k for k in B.V5_FROZEN if not k.isupper()]
