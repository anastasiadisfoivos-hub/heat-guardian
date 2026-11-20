"""T4 — Open-Meteo fetch / cache / 429 logic with a MOCK (the live API is never called).

Run: cd /tmp && unshare -rn python3 -m pytest -q /home/claude/hg_ai/tests/t4/test_t4_openmeteo.py
(unshare -rn = no network namespace at all; the autouse fixture also fails any urlopen that is not mocked.)
"""
import http.client
import io
import json
import shutil
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, "/home/claude/hg_ai")
from tomorrow import openmeteo as om, cli, plan  # noqa: E402

SAMPLE = "/home/claude/hg_ai/research/openmeteo_sample.json"
R3_URL = open("/home/claude/hg_ai/research/openmeteo_url.txt").readline().strip()
NOW = datetime(2026, 11, 12, 21, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_net(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("REAL urlopen reached")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: (_ for _ in ()).throw(AssertionError("socket")))


def sample():
    return json.load(open(SAMPLE))


class Resp(io.BytesIO):
    status = 200
    def __enter__(self): return self
    def __exit__(self, *a): return False


class Mock:
    def __init__(self, script):
        self.script, self.urls, self.timeouts = list(script), [], []

    def __call__(self, req, timeout=None):
        self.urls.append(req.full_url); self.timeouts.append(timeout)
        o = self.script.pop(0)
        if isinstance(o, int):
            raise urllib.error.HTTPError(req.full_url, o, "limit", None, None)
        if isinstance(o, BaseException):
            raise o
        if isinstance(o, bytes):
            return Resp(o)
        return Resp(json.dumps(o).encode())


def seed(tmp, fetched_at):
    raw = sample(); raw["fetched_at"] = fetched_at
    p = om.cache_path(37.98, 23.73, str(tmp))
    json.dump(raw, open(p, "w"))
    return p


def test_url_exact_r3():
    assert om.build_url(37.98, 23.73) == R3_URL


def test_fresh_cache_no_call(tmp_path):
    seed(tmp_path, (NOW - timedelta(hours=19.99)).isoformat())
    m, s = Mock([]), []
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW, _urlopen=m, _sleep=s.append)
    assert m.urls == [] and s == [] and fc.source == "cache"


def test_stale_200_writes_cache_one_call(tmp_path):
    seed(tmp_path, (NOW - timedelta(hours=20.01)).isoformat())
    m, s = Mock([sample()]), []
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW, _urlopen=m, _sleep=s.append)
    assert m.urls == [R3_URL] and s == [] and fc.source == "open-meteo"
    c = json.load(open(om.cache_path(37.98, 23.73, str(tmp_path))))
    assert c["fetched_at"] == NOW.isoformat(timespec="seconds")


@pytest.mark.parametrize("script", [[429, 429, 429, 429, 429], [500, 503, 200], [urllib.error.URLError("x"), 429]])
def test_failure_exactly_two_calls_one_60s_sleep(tmp_path, script):
    seed(tmp_path, (NOW - timedelta(hours=30)).isoformat())
    m, s = Mock(script), []
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW, _urlopen=m, _sleep=s.append)
    assert len(m.urls) == 2 and s == [60.0]
    assert fc.source == "cache" and fc.forecast_age_h == pytest.approx(30.0)


def test_retry_success(tmp_path):
    m, s = Mock([429, sample()]), []
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW, _urlopen=m, _sleep=s.append)
    assert len(m.urls) == 2 and s == [60.0] and fc.source == "open-meteo"


def test_error_json_body_counts_as_failure(tmp_path):
    seed(tmp_path, (NOW - timedelta(hours=30)).isoformat())
    m, s = Mock([{"error": True, "reason": "x"}, b"{not json"]), []
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW, _urlopen=m, _sleep=s.append)
    assert fc.source == "cache" and len(m.urls) == 2


def test_incomplete_read_falls_back_to_cache(tmp_path):
    """A truncated body raises http.client.IncompleteRead (an HTTPException, NOT an OSError/URLError).
    Expected by the brief: 'on any HTTP error ... use the cache'."""
    seed(tmp_path, (NOW - timedelta(hours=30)).isoformat())
    m, s = Mock([http.client.IncompleteRead(b"{", 10), http.client.IncompleteRead(b"{", 10)]), []
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW, _urlopen=m, _sleep=s.append)
    assert fc.source == "cache"


def test_null_tail_parsed():
    fc = om.parse(sample(), "cache", NOW.isoformat(), NOW)
    assert len(fc.hourly) == 429 and not fc.hourly["temperature_2m"].isna().any()


def test_null_inside_target_day_plan_finite(tmp_path):
    raw = sample()
    t = raw["hourly"]["time"]
    i = t.index("2026-11-13T12:00")
    for k in ("temperature_2m", "relative_humidity_2m", "apparent_temperature", "shortwave_radiation", "is_day"):
        raw["hourly"][k][i] = None; raw["hourly"][k][i + 1] = None
    fc = om.parse(raw, "cache", NOW.isoformat(), NOW)
    p = plan.make_plan(fc, "2026-11-13", "B")
    cli.validate(p)
    assert all(h["t_in"] == h["t_in"] for h in p["hours"])


def _cli(tmp_path, monkeypatch, script, extra=()):
    m = Mock(script)
    monkeypatch.setattr(urllib.request, "urlopen", m)
    monkeypatch.setattr(om.time, "sleep", lambda s: m.urls.append("SLEEP %g" % s))
    out = tmp_path / "plan.json"
    rc = cli.main(["--cache-dir", str(tmp_path), "--out", str(out), "--date", "2026-11-14", *extra])
    return rc, json.load(open(out)), m


def test_cli_429_plan_source_cache(tmp_path, monkeypatch):
    """Acceptance 5 end-to-end through cli.main (not plan.make_plan)."""
    seed(tmp_path, (datetime.now(timezone.utc) - timedelta(hours=26)).isoformat())
    rc, p, m = _cli(tmp_path, monkeypatch, [429, 429])
    assert rc == 0 and p["source"] == "cache" and p["forecast_age_h"] == pytest.approx(26.0, abs=0.1)
    assert m.urls == [R3_URL, "SLEEP 60", R3_URL]


def test_cli_future_fetched_at(tmp_path, monkeypatch):
    """Clock skew / hand-seeded cache: fetched_at 2 h in the future. Expect: either a refetch or a valid plan."""
    seed(tmp_path, (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat())
    rc, p, m = _cli(tmp_path, monkeypatch, [])
    assert p["forecast_age_h"] >= 0


def test_cli_stale_cache_tells_wearer(tmp_path, monkeypatch):
    """R3 §5: on a failed call the band should say 'forecast from last night'. Look for ANY marker of
    staleness in what reaches the wearer (advice_gr) or the band (0x14 tag)."""
    seed(tmp_path, (datetime.now(timezone.utc) - timedelta(hours=26)).isoformat())
    rc, p, m = _cli(tmp_path, monkeypatch, [429, 429])
    tag = bytes.fromhex(p["ble"]["safe_hours_hex"])[5:19]
    assert any("χθες" in s or "προηγ" in s or "βράδυ" in s for s in p["advice_gr"]) or b"C" in tag[11:]


def test_cli_cache_older_than_horizon(tmp_path, monkeypatch):
    """A 20-day-old cache (phone off for weeks) + 429: what happens?"""
    seed(tmp_path, (datetime.now(timezone.utc) - timedelta(days=20)).isoformat())
    m = Mock([429, 429])
    monkeypatch.setattr(urllib.request, "urlopen", m)
    monkeypatch.setattr(om.time, "sleep", lambda s: None)
    rc = cli.main(["--cache-dir", str(tmp_path), "--out", str(tmp_path / "p.json"), "--date", "2026-12-05"])
    assert rc != 0 or (tmp_path / "p.json").exists()


def test_repeated_invocations_after_failure_do_not_hammer(tmp_path):
    """'One call per night': after a failed night, a second/third invocation the same night (cron retry, user
    re-run, phone app reopened) should not call again. No 'last attempt' is persisted, so each run makes 2 calls."""
    seed(tmp_path, (NOW - timedelta(hours=30)).isoformat())
    m = Mock([429] * 10)
    for k in range(3):
        om.fetch(37.98, 23.73, str(tmp_path), now=NOW + timedelta(minutes=10 * k), _urlopen=m, _sleep=lambda s: None)
    assert len(m.urls) <= 2, "%d calls in 20 min" % len(m.urls)
