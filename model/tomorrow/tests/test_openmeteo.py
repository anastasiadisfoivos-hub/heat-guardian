"""Open-Meteo fetch/cache rules (ARCHITECTURE §6, B4 brief): mocked HTTP only."""
import io
import json
import os
import urllib.error
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from tomorrow import openmeteo as om

SAMPLE = "/home/claude/hg_ai/research/openmeteo_sample.json"
NOW = datetime(2026, 11, 12, 20, 0, tzinfo=timezone.utc)


def sample():
    with open(SAMPLE, encoding="utf-8") as f:
        return json.load(f)


class FakeResp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Truncated(FakeResp):
    def read(self, *a):
        import http.client
        raise http.client.IncompleteRead(b"{\"hourly\": {", 5000)


class Server:
    """Mock urlopen: replies from a script of outcomes; records every call."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, req, timeout=None):
        self.calls.append(req.full_url)
        o = self.outcomes.pop(0)
        if isinstance(o, int):
            raise urllib.error.HTTPError(req.full_url, o, "Hourly API request limit exceeded", None, None)
        if o == "TRUNCATED":
            return Truncated(b"")
        return FakeResp(json.dumps(o).encode())


class Sleeps(list):
    def __call__(self, s):
        self.append(s)


def test_url_is_r3_url():
    with open("/home/claude/hg_ai/research/openmeteo_url.txt") as f:
        r3 = f.readline().strip()
    assert om.build_url(37.98, 23.73) == r3


def test_200_writes_cache(tmp_path):
    srv, sl = Server([sample()]), Sleeps()
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW, _urlopen=srv, _sleep=sl)
    assert fc.source == "open-meteo" and len(srv.calls) == 1 and sl == []
    p = om.cache_path(37.98, 23.73, str(tmp_path))
    assert os.path.basename(p) == "openmeteo_37.98_23.73.json"
    with open(p) as f:
        c = json.load(f)
    assert c["fetched_at"] == "2026-11-12T20:00:00+00:00" and "hourly" in c
    assert fc.forecast_age_h == 0.0


def test_fresh_cache_means_no_call(tmp_path):
    om.fetch(37.98, 23.73, str(tmp_path), now=NOW, _urlopen=Server([sample()]), _sleep=Sleeps())
    srv = Server([])                      # any call would pop from an empty list and fail
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW + timedelta(hours=19.9), _urlopen=srv, _sleep=Sleeps())
    assert srv.calls == [] and fc.source == "cache" and fc.forecast_age_h == pytest.approx(19.9)


def test_429_uses_cache_one_retry_no_loop(tmp_path):
    om.fetch(37.98, 23.73, str(tmp_path), now=NOW, _urlopen=Server([sample()]), _sleep=Sleeps())
    srv, sl = Server([429, 429, 429, 429]), Sleeps()
    later = NOW + timedelta(hours=26)
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=later, _urlopen=srv, _sleep=sl)
    assert len(srv.calls) == 2, "exactly one retry"
    assert sl == [60.0], "one 60-s wait before the retry"
    assert fc.source == "cache" and fc.forecast_age_h == pytest.approx(26.0)
    assert any("429" in n for n in fc.notes)


def test_429_then_200_on_retry(tmp_path):
    srv, sl = Server([429, sample()]), Sleeps()
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW, _urlopen=srv, _sleep=sl)
    assert fc.source == "open-meteo" and len(srv.calls) == 2 and sl == [60.0]


def test_429_without_cache_raises(tmp_path):
    with pytest.raises(om.ForecastUnavailable):
        om.fetch(37.98, 23.73, str(tmp_path), now=NOW, _urlopen=Server([429, 429]), _sleep=Sleeps())


def test_null_tail_handled():
    raw = sample()
    assert raw["hourly"]["temperature_2m"][-3:] == [None, None, None]
    fc = om.parse(raw, "cache", "2026-11-10T18:00:00+00:00", NOW)
    assert len(fc.hourly) == 432 - 3
    assert not fc.hourly["temperature_2m"].isna().any()
    assert any("3 trailing null" in n for n in fc.notes)
    assert np.isnan(fc.daily["temperature_2m_max"].iloc[-1])
    day = fc.day("2026-11-13")
    assert len(day) == 24 and not day.isna().any().any()


def test_plan_from_mock_429_has_source_cache(tmp_path):
    """Acceptance 5: with mocked 429 the plan still appears with source 'cache'."""
    from tomorrow import plan, cli
    om.fetch(37.98, 23.73, str(tmp_path), now=NOW, _urlopen=Server([sample()]), _sleep=Sleeps())
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW + timedelta(hours=30), _urlopen=Server([429, 429]),
                  _sleep=Sleeps())
    p = plan.make_plan(fc, "2026-11-14", "B")
    cli.validate(p)
    assert p["source"] == "cache" and p["forecast_age_h"] == pytest.approx(30.0)
    assert p["attribution"] == "Weather data by Open-Meteo.com" and "SIMULATION" in p["labels"]


def _seed(tmp_path, when=NOW):
    om.fetch(37.98, 23.73, str(tmp_path), now=when, _urlopen=Server([sample()]), _sleep=Sleeps())


def test_truncated_body_uses_cache(tmp_path):
    _seed(tmp_path)
    srv = Server(["TRUNCATED", "TRUNCATED"])
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW + timedelta(hours=25), _urlopen=srv, _sleep=Sleeps())
    assert fc.source == "cache" and len(srv.calls) == 2
    assert any("IncompleteRead" in n for n in fc.notes)


def test_future_fetched_at_is_stale_not_fresh(tmp_path):
    p = om.cache_path(37.98, 23.73, str(tmp_path))
    raw = sample(); raw["fetched_at"] = (NOW + timedelta(days=3)).isoformat()
    with open(p, "w") as f:
        json.dump(raw, f)
    srv = Server([sample()])
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW, _urlopen=srv, _sleep=Sleeps())
    assert len(srv.calls) == 1 and fc.source == "open-meteo" and fc.forecast_age_h == 0.0
    # and when the refetch fails, the age is clamped >= 0 (schema minimum 0)
    raw["fetched_at"] = (NOW + timedelta(days=3)).isoformat()
    with open(p, "w") as f:
        json.dump(raw, f)
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW + timedelta(hours=21), _urlopen=Server([429, 429]), _sleep=Sleeps())
    assert fc.forecast_age_h >= 0


def test_no_extra_calls_after_a_failed_night(tmp_path):
    """T4 F6(iii): 3 invocations in 20 min after a failure made 6 calls; now 2 (one attempt + one retry)."""
    _seed(tmp_path)
    total = 0
    for k in range(3):
        srv = Server([429, 429, 429, 429])
        fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW + timedelta(hours=25, minutes=10 * k), _urlopen=srv,
                      _sleep=Sleeps())
        total += len(srv.calls)
        assert fc.source == "cache"
    assert total == 2
    assert os.path.exists(om.attempt_path(37.98, 23.73, str(tmp_path)))
    srv = Server([sample()])                       # next night (> 20 h after the failed attempt): one call again
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW + timedelta(hours=46), _urlopen=srv, _sleep=Sleeps())
    assert len(srv.calls) == 1 and fc.source == "open-meteo"


def test_stale_forecast_labelled(tmp_path):
    from tomorrow import plan
    _seed(tmp_path)
    fc = om.fetch(37.98, 23.73, str(tmp_path), now=NOW + timedelta(hours=40), _urlopen=Server([429, 429]),
                  _sleep=Sleeps())
    p = plan.make_plan(fc, "2026-11-15", "B")
    assert any(l.startswith("STALE FORECAST") for l in p["labels"]) and "STALE_FORECAST" in p["details"]["advice_ids"]
    from tomorrow import ble_frame
    assert ble_frame.decode_safe_hours(bytes.fromhex(p["ble"]["safe_hours_hex"]))["tag"].endswith(" C")


def test_cache_older_than_horizon_cli_exits_cleanly(tmp_path, capsys):
    from tomorrow import cli
    _seed(tmp_path, datetime.now(timezone.utc))
    rc = cli.main(["--cache-dir", str(tmp_path), "--date", "2027-01-30", "--out", str(tmp_path / "p.json")])
    assert rc == 3 and "NO PLAN" in capsys.readouterr().err
