"""The Token Factory client on a request path: bounded attempts, Retry-After, no sleep after the last attempt,
reasoning tokens recorded, a circuit breaker, and a per-UTC-day spend window. No network: urlopen is stubbed."""
import io
import json
import urllib.error

import pytest

from owin import tokenfactory as tf

OK = {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
      "usage": {"prompt_tokens": 100, "completion_tokens": 60, "completion_tokens_details": {"reasoning_tokens": 46}}}


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http(code, retry_after=None):
    h = {"Retry-After": str(retry_after)} if retry_after is not None else {}
    return urllib.error.HTTPError(tf.URL, code, "err", h, None)


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("TOKEN_FACTORY_API_KEY", "sk-test")
    monkeypatch.setattr(tf, "LEDGER", tmp_path / "usage.jsonl")
    tf.reset_breaker()
    sleeps = []
    monkeypatch.setattr(tf.time, "sleep", lambda s: sleeps.append(s))
    yield sleeps
    tf.reset_breaker()


def _transport(monkeypatch, outcomes):
    """Each outcome is an exception to raise or a dict to return; records every request body."""
    bodies = []

    def urlopen(req, timeout):
        bodies.append((json.loads(req.data), timeout))
        o = outcomes.pop(0)
        if isinstance(o, BaseException):
            raise o
        return _Resp(json.dumps(o).encode())
    monkeypatch.setattr(tf.urllib.request, "urlopen", urlopen)
    return bodies


def test_no_sleep_after_the_last_attempt(monkeypatch, isolated):
    _transport(monkeypatch, [_http(503), _http(503), _http(503)])
    c = tf.chat("hi", purpose="t")
    assert c.error == "HTTP 503" and c.attempts == 3
    assert isolated == [4.0, 8.0]  # two waits between three attempts; none after the third


def test_request_path_settings_bound_the_wait(monkeypatch, isolated):
    bodies = _transport(monkeypatch, [TimeoutError(), TimeoutError()])
    c = tf.chat("hi", purpose="t", timeout=45, attempts=2)
    assert c.error == "TimeoutError" and c.attempts == 2
    assert [t for _, t in bodies] == [45, 45] and isolated == [4.0]


def test_retry_after_is_honoured_and_capped(monkeypatch, isolated):
    _transport(monkeypatch, [_http(429, 2), _http(429, 999), OK])
    c = tf.chat("hi", purpose="t")
    assert c.error is None and c.attempts == 3 and isolated == [2.0, tf.MAX_RETRY_AFTER_S]


def test_overloaded_529_is_retried(monkeypatch, isolated):
    _transport(monkeypatch, [_http(529), OK])
    c = tf.chat("hi", purpose="t")
    assert c.error is None and c.attempts == 2


def test_a_client_error_is_not_retried(monkeypatch, isolated):
    _transport(monkeypatch, [_http(401)])
    assert tf.chat("hi", purpose="t").attempts == 1 and isolated == []


def test_reasoning_switch_and_reasoning_tokens_are_recorded(monkeypatch):
    bodies = _transport(monkeypatch, [OK, OK])
    c = tf.chat("hi", purpose="t")
    assert "chat_template_kwargs" not in bodies[0][0]  # default: the model's own setting (every recorded run)
    assert c.reasoning_tokens == 46
    tf.chat("hi", purpose="t", thinking=False)
    assert bodies[1][0]["chat_template_kwargs"] == {"enable_thinking": False}
    lines = [json.loads(l) for l in tf.LEDGER.read_text().splitlines()]
    assert lines[0]["reasoning_tokens"] == 46 and "thinking" not in lines[0] and lines[1]["thinking"] is False


def test_breaker_opens_after_consecutive_failures_and_a_success_closes_it(monkeypatch):
    _transport(monkeypatch, [_http(503)] * 3 + [OK])
    for _ in range(3):
        tf.chat("hi", purpose="t", attempts=1)
    assert not tf.available()
    assert tf.available(now=tf.time.time() + tf.BREAKER_OPEN_S + 1)  # it closes on its own
    tf.chat("hi", purpose="t", attempts=1)
    assert tf.available()


def test_spent_today_counts_only_the_current_utc_day_and_purpose(monkeypatch):
    tf.LEDGER.write_text("\n".join(json.dumps(r) for r in [
        {"ts": "2026-10-29T10:00:00-0400", "purpose": "recheck-read:/api/x", "cost_usd": 0.01},
        {"ts": "2026-10-29T21:30:00-0400", "purpose": "pack-registry:y", "cost_usd": 0.02},  # 01:30 UTC on the 30th
        {"ts": "2026-10-28T10:00:00-0400", "purpose": "recheck-read:/api/x", "cost_usd": 5.0},
        {"cost_usd": 9.0},  # no timestamp: not counted in a day window
    ]) + "\n")
    noon_utc_29 = 1793275200.0  # 2026-10-29T12:00:00Z
    assert tf.spent_today(now=noon_utc_29) == 0.01
    assert tf.spent_today("pack-registry", now=noon_utc_29 + 86400) == 0.02
    assert tf.ledger_total() == pytest.approx(14.03)
