"""Scheduled re-fetch inside `owin serve`: schedule parsing, next-run times, one run at a time, errors recorded,
the /healthz block, and a run that moves no headline number. No network: Tavily is stubbed."""
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from owin import recheck, refetch, server, tavily, tokenfactory as tf
from owin.datause import observations, registry


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    for k in ("TAVILY_API_KEY", "TOKEN_FACTORY_API_KEY", "OWIN_STATE_DIR", refetch.ENV):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OWIN_ENV_FILE", str(tmp_path / "no.env"))
    monkeypatch.setattr(tf, "LEDGER", tmp_path / "usage.jsonl")
    monkeypatch.setattr(refetch, "_active", None)
    recheck.reset()
    yield
    recheck.reset()


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


# Parsing

@pytest.mark.parametrize("text,kind,secs", [("6h", "interval", 21600), ("30m", "interval", 1800), ("1m", "interval", 60),
                                            ("24h", "interval", 86400), (" 90S ", "interval", 90), ("1d", "interval", 86400),
                                            ("off", "off", 0), ("OFF", "off", 0)])
def test_parse_intervals_and_off(text, kind, secs):
    s = refetch.parse(text)
    assert s.kind == kind and s.seconds == secs


def test_parse_daily():
    s = refetch.parse("daily@6:05")
    assert (s.kind, s.hour, s.minute, s.text) == ("daily", 6, 5, "daily@06:05")


@pytest.mark.parametrize("bad", ["", "6", "6x", "30s", "daily@24:00", "daily@06:60", "daily@6", "hourly", "-5m", "1.5h"])
def test_parse_rejects_bad_values(bad):
    with pytest.raises(ValueError):
        refetch.parse(bad)


def test_defaults_off_without_a_key_and_daily_with_one():
    assert refetch.resolve(key_present=False) == (refetch.OFF, None)
    s, w = refetch.resolve(key_present=True)
    assert s.text == "daily@06:00" and w is None


def test_flag_beats_env_and_a_bad_value_runs_off_with_a_message(monkeypatch):
    monkeypatch.setenv(refetch.ENV, "6h")
    assert refetch.resolve(key_present=True)[0].text == "6h"
    assert refetch.resolve("30m", key_present=True)[0].text == "30m"
    monkeypatch.setenv(refetch.ENV, "every tuesday")
    s, w = refetch.resolve(key_present=True)
    assert s == refetch.OFF and "unknown re-fetch schedule" in w and "off" in w


def test_a_schedule_without_a_key_warns():
    s, w = refetch.resolve("6h", key_present=False)
    assert s.kind == "interval" and "no Tavily key" in w


# Next run

def test_next_run_interval_counts_from_the_last_start():
    s = refetch.parse("6h")
    now = utc(2026, 10, 30, 12, 0)
    assert refetch.next_run(s, now) == utc(2026, 10, 30, 18, 0)
    assert refetch.next_run(s, now, last_start=utc(2026, 10, 30, 11, 0)) == utc(2026, 10, 30, 17, 0)


def test_next_run_daily_today_or_tomorrow():
    s = refetch.parse("daily@06:00")
    assert refetch.next_run(s, utc(2026, 10, 30, 5, 59)) == utc(2026, 10, 30, 6, 0)
    assert refetch.next_run(s, utc(2026, 10, 30, 6, 0)) == utc(2026, 10, 31, 6, 0)
    assert refetch.next_run(s, utc(2026, 12, 31, 23, 0)) == utc(2027, 1, 1, 6, 0)
    assert refetch.next_run(refetch.OFF, utc(2026, 10, 30)) is None


# Scheduler

class FakeClock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, secs):
        self.t += timedelta(seconds=secs)
        return False  # a wait() that is never stopped


def test_scheduler_runs_at_each_due_time_on_a_fake_clock():
    clock = FakeClock(utc(2026, 10, 30, 0, 0))
    calls = []
    sch = refetch.Scheduler(refetch.parse("6h"), clock=clock,
                            refresh=lambda: calls.append(clock()) or {"summary": "5 pages, 5 unchanged, 0 changed"})

    def wait(secs):
        clock.advance(secs)
        if len(calls) >= 3:
            sch.stop()
            return True
        return False
    sch.loop(wait)
    assert calls == [utc(2026, 10, 30, 6), utc(2026, 10, 30, 12), utc(2026, 10, 30, 18)]
    st = sch.status()
    assert st["last_result"] == "5 pages, 5 unchanged, 0 changed" and st["last_run"] == "2026-10-30T18:00:00Z"
    assert st["next_run"] == "2026-10-31T00:00:00Z" and st["schedule"] == "6h"


def test_scheduler_daily_runs_at_the_utc_time():
    clock = FakeClock(utc(2026, 10, 30, 13, 0))
    calls = []
    sch = refetch.Scheduler(refetch.parse("daily@06:00"), clock=clock, refresh=lambda: calls.append(clock()) or {"summary": "ok"})

    def wait(secs):
        clock.advance(secs)
        if len(calls) >= 2:
            sch.stop()
            return True
        return False
    sch.loop(wait)
    assert calls == [utc(2026, 10, 31, 6), utc(2026, 11, 1, 6)]


def test_no_overlapping_runs():
    gate, entered = threading.Event(), threading.Event()
    n = {"runs": 0}

    def slow():
        n["runs"] += 1
        entered.set()
        gate.wait(5)
        return {"summary": "done"}
    sch = refetch.Scheduler(refetch.parse("1m"), refresh=slow)
    t = threading.Thread(target=sch.tick)
    t.start()
    assert entered.wait(5)
    assert sch.status()["running"] is True
    assert sch.tick() is False  # a second run while the first is in progress is skipped
    gate.set()
    t.join(5)
    assert n["runs"] == 1 and sch.skipped == 1 and sch.status()["running"] is False


def test_an_exception_is_recorded_not_raised():
    def boom():
        raise RuntimeError("tavily down")
    sch = refetch.Scheduler(refetch.parse("1m"), refresh=boom)
    assert sch.tick() is True
    st = sch.status()
    assert st["last_result"] == "error: RuntimeError: tavily down" and st["last_run"] and st["next_run"]


def test_the_thread_runs_a_short_interval_for_real():
    calls = []
    sch = refetch.Scheduler(refetch.Schedule("interval", "50ms", seconds=0.05),
                            refresh=lambda: calls.append(time.time()) or {"summary": "ok"})
    sch.POLL_S = 0.01
    sch.start()
    deadline = time.time() + 3
    while len(calls) < 3 and time.time() < deadline:
        time.sleep(0.01)
    sch.stop()
    sch.thread.join(2)
    assert len(calls) >= 3 and not sch.thread.is_alive()


def test_off_starts_no_thread():
    sch = refetch.Scheduler(refetch.OFF).start()
    assert sch.thread is None and sch.status()["next_run"] is None


# The refresh itself

def _stub_tavily(monkeypatch, drop_all=False):
    monkeypatch.setattr(tavily, "api_key", lambda: "tvly-test")
    pages = {v["url"]: k for k, v in registry.load_catalog()["pages"].items()}
    calls = []

    def fetch(url, depth="basic", key=None):
        calls.append((pages[url], depth))
        quotes = [] if drop_all else list(observations.page_quotes(pages[url]).values())
        return tavily.Fetched(url, "Vendor documentation\n\n" + "\n\n".join(quotes) + "\n", "tavily", "2026-10-30T06:00:00Z", 0.2)
    monkeypatch.setattr(tavily, "extract", fetch)
    return calls


def test_refresh_fetches_each_watched_page_once_and_keeps_results_in_memory(monkeypatch):
    calls = _stub_tavily(monkeypatch)
    before = server.selective_summary(), registry.load(), json.loads(server.handle("/api/score", {})[2])
    res = refetch.refresh_pages()
    pages = refetch.watched_pages()
    assert sorted(p for p, _ in calls) == sorted(pages) and all(d == "basic" for _, d in calls)
    assert res["pages"] == len(pages) == res["unchanged"] + res["changed"] and res["failed"] == 0
    assert res["summary"].startswith(f"{len(pages)} pages, ") and res["stored"] == "process"
    obs = observations.load()
    for p in pages:
        assert obs["pages"][p]["observations"][-1]["observed_at"].startswith("2026-10-30T06:00")
        assert "scheduled re-fetch" in obs["pages"][p]["observations"][-1]["method"]
    # The recorded headline, the registry and the Nemotron readings do not move.
    assert (server.selective_summary(), registry.load(), json.loads(server.handle("/api/score", {})[2])) == before
    ledger = [json.loads(x) for x in tf.LEDGER.read_text().splitlines()]
    assert len(ledger) == len(pages) and all(x["purpose"].startswith("refetch:") for x in ledger)


def test_refresh_writes_to_the_state_dir_when_set(monkeypatch, tmp_path):
    monkeypatch.setenv("OWIN_STATE_DIR", str(tmp_path / "state"))
    _stub_tavily(monkeypatch)
    res = refetch.refresh_pages()
    assert res["stored"] == "state_dir" and (tmp_path / "state" / observations.OBS_REL).exists()


def test_a_second_run_reports_pages_unchanged(monkeypatch):
    _stub_tavily(monkeypatch)
    refetch.refresh_pages()
    res = refetch.refresh_pages()
    assert res["unchanged"] == res["pages"] and res["changed"] == 0


def test_refresh_without_a_key_is_recorded_as_an_error_and_makes_no_request(monkeypatch):
    monkeypatch.setattr(tavily, "extract", lambda *a, **k: pytest.fail("no request without a key"))
    sch = refetch.Scheduler(refetch.parse("1m"))
    sch.tick()
    assert sch.status()["last_result"] == "error: RuntimeError: no Tavily key on this server"


# /healthz

def test_healthz_shows_off_with_no_key():
    h = json.loads(server.handle("/healthz", {})[2])
    assert h["refetch"]["schedule"] == "off" and h["refetch"]["next_run"] is None and h["refetch"]["last_run"] is None


def test_healthz_shows_the_running_scheduler(monkeypatch):
    monkeypatch.setenv(refetch.ENV, "6h")
    monkeypatch.setattr(tavily, "api_key", lambda: "tvly-test")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-SECRET-VALUE")
    sch = refetch.Scheduler(refetch.parse("6h"), refresh=lambda: {"summary": "5 pages, 4 unchanged, 1 changed"})
    monkeypatch.setattr(refetch, "_active", sch)
    sch.tick()
    body = server.handle("/healthz", {})[2]
    r = json.loads(body)["refetch"]
    assert r["schedule"] == "6h" and r["last_result"] == "5 pages, 4 unchanged, 1 changed"
    assert r["next_run"].endswith("Z") and r["last_run"].endswith("Z") and "SECRET" not in body


def test_healthz_defaults_to_daily_with_a_key(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-x")
    assert json.loads(server.handle("/healthz", {})[2])["refetch"]["schedule"] == "daily@06:00"


def test_serve_flag_is_wired(monkeypatch):
    from owin import cli
    seen = {}
    monkeypatch.setattr(server, "serve", lambda host, port, sched=None: seen.update(sched=sched))
    cli.main(["serve", "--refetch", "30m", "--port", "1"])
    assert seen["sched"] == "30m"
