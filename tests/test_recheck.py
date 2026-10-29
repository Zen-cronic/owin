"""POST /api/recheck: the one visitor-triggered sponsor call. Keyless it answers demo; keyed it is capped, cooled
down, ledgered, and recomputes the endpoint's answers through the same rules as every other request."""
import json

import pytest

from owin import recheck, server, tavily, tokenfactory as tf
from owin.datause import observations, pack

EP = "/api/crm-sync"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    for k in ("TAVILY_API_KEY", "TOKEN_FACTORY_API_KEY", "OWIN_STATE_DIR", "OWIN_RECHECK_DAILY_CAP"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OWIN_ENV_FILE", str(tmp_path / "no.env"))
    monkeypatch.setattr(tf, "LEDGER", tmp_path / "usage.jsonl")
    recheck.reset()
    yield
    recheck.reset()


def _page_text(page: str, drop: str | None = None) -> str:
    """A stand-in for the vendor page: every quoted sentence Owin knows on that page, minus `drop`."""
    quotes = [q for q in observations.page_quotes(page).values() if q != drop]
    return "Vendor documentation\n\n" + "\n\n".join(quotes) + "\n"


def _keyed(monkeypatch, text: str | None = None):
    """A fake Tavily: returns `text`, or the stand-in page for whichever URL is asked, and records the depths."""
    monkeypatch.setattr(tavily, "api_key", lambda: "tvly-test")
    pages = {v["url"]: k for k, v in recheck.registry.load_catalog()["pages"].items()}
    calls = []

    def fetch(url, depth="basic", key=None):
        calls.append(depth)
        return tavily.Fetched(url, text or _page_text(pages[url]), "tavily", "2026-10-29T03:00:00Z", 0.3)
    monkeypatch.setattr(tavily, "extract", fetch)  # the server path (no `fetch` argument) reaches the same fake
    return fetch, calls


def _post(body) -> tuple[int, dict]:
    code, ctype, text = server.handle_post("/api/recheck", json.dumps(body).encode(), {})
    assert ctype == "application/json"
    return code, json.loads(text)


# Keyless: a demo answer, no request, nothing counted

def test_keyless_answers_demo_and_makes_no_call():
    code, body = recheck.run(EP)
    assert code == 200 and body == {"ok": False, "mode": "demo", "reason": "no key on this server"}
    assert not tf.LEDGER.exists()
    code, body = _post({"endpoint": EP})
    assert code == 200 and body["mode"] == "demo" and body["ok"] is False


def test_bad_bodies_and_unknown_endpoints_are_400():
    assert _post({"endpoint": "/api/nope"})[0] == 400
    assert _post({"nope": 1})[0] == 400
    assert server.handle_post("/api/recheck", b"{not json", {})[0] == 400
    assert server.handle("/api/recheck", {})[0] == 405  # GET: tell the caller to POST


# Capped: a per-process daily cap and a per-endpoint cooldown, both 429

def test_daily_cap_is_enforced_per_process(monkeypatch):
    fetch, calls = _keyed(monkeypatch)
    monkeypatch.setenv("OWIN_RECHECK_DAILY_CAP", "1")
    code, body = recheck.run(EP, fetch=fetch, now=1_000_000.0)
    assert code == 200 and body["ok"] is True
    code, body = recheck.run("/api/summarize", fetch=fetch, now=1_000_001.0)
    assert code == 429 and body["ok"] is False and "daily cap" in body["reason"] and body["mode"] == "live"
    assert len(calls) == 1  # the capped call never reached Tavily


def test_cooldown_per_endpoint(monkeypatch):
    fetch, calls = _keyed(monkeypatch)
    assert recheck.run(EP, fetch=fetch, now=2_000_000.0)[0] == 200
    code, body = recheck.run(EP, fetch=fetch, now=2_000_010.0)
    assert code == 429 and "wait" in body["reason"] and body["retry_after_s"] >= 50
    assert recheck.run("/api/summarize", fetch=fetch, now=2_000_011.0)[0] == 200  # another endpoint is not blocked
    assert recheck.run(EP, fetch=fetch, now=2_000_061.0)[0] == 200  # the cooldown has passed
    assert len(calls) == 3


# Mocked live path: observation appended, rules rerun, one ledger line per call

def test_live_unchanged_page_keeps_every_answer_and_logs_one_line(monkeypatch):
    fetch, calls = _keyed(monkeypatch)
    before = {a["id"]: a["badge"] for a in pack.build()["answers"]}
    code, body = _post({"endpoint": EP})
    assert code == 200 and body["ok"] is True and body["mode"] == "live"
    assert body["changed"] is False and body["state"] == "not_true"  # answer 3 is still not true for /api/crm-sync
    assert body["credits_used"] == 1 and calls == ["basic"] and body["checked_at"] == "2026-10-29T03:00:00Z"
    assert body["observation"].startswith("Page text differs from the Oct 2") and body["observation"].endswith("still on it.")
    assert body["stored"] == "process" and body["page"] == "anthropic-mcp-connector"
    assert {a["id"]: a["badge"] for a in pack.build()["answers"]} == before
    # The evidence history now ends with this capture, and the served watch sees it too.
    latest = observations.load()["pages"]["anthropic-mcp-connector"]["observations"][-1]
    assert latest["observed_at"] == "2026-10-29T03:00:00Z" and latest["source_kind"] == "tavily" and "quotes_present" in latest
    assert "content" not in latest and "text" not in latest  # hashes and presence only, never page text
    lines = [json.loads(l) for l in tf.LEDGER.read_text().splitlines()]
    assert len(lines) == 1 and lines[0]["purpose"] == f"recheck:{EP}" and lines[0]["model"] == "tavily/extract"
    assert lines[0]["credits"] == 1 and lines[0]["cost_usd"] == 0.0 and lines[0]["error"] is None


def test_live_lost_sentence_refetches_at_advanced_depth_and_marks_the_change(monkeypatch):
    gone = "The MCP connector is not covered by ZDR arrangements."
    fetch, calls = _keyed(monkeypatch, _page_text("anthropic-mcp-connector", drop=gone))
    code, body = recheck.run(EP, fetch=fetch)
    assert code == 200 and body["ok"] is True
    assert calls == ["basic", "advanced"] and body["credits_used"] == 3  # looked twice before recording a loss
    assert body["changed"] is True and body["state"] == "not_true"  # the contradiction stands; the cell is now also stale
    assert "no longer on it" in body["observation"]
    q03 = next(a for a in pack.build()["answers"] if a["id"] == "Q03")
    cell = next(c for c in q03["cells"] if c["endpoint"] == EP)
    assert cell["verdict"] == "contradicts" and cell.get("stale") is True and q03["badge"] == "not_true"
    lines = [json.loads(l) for l in tf.LEDGER.read_text().splitlines()]
    assert len(lines) == 1 and lines[0]["credits"] == 3


def test_live_tavily_failure_is_reported_not_hidden(monkeypatch):
    monkeypatch.setattr(tavily, "api_key", lambda: "tvly-test")
    fetch = lambda url, depth: tavily.Fetched(url, None, "unfetched", "2026-10-29T03:00:00Z", 0.1, "tavily HTTP 502")
    code, body = recheck.run(EP, fetch=fetch)
    assert code == 502 and body["ok"] is False and body["reason"] == "tavily HTTP 502" and body["credits_used"] == 1
    assert observations.load()["pages"]["anthropic-mcp-connector"]["observations"][-1]["observed_at"] != "2026-10-29T03:00:00Z"
    assert json.loads(tf.LEDGER.read_text())["error"] == "tavily HTTP 502"


def test_state_dir_persists_the_observation(monkeypatch, tmp_path):
    monkeypatch.setenv("OWIN_STATE_DIR", str(tmp_path / "state"))
    fetch, _ = _keyed(monkeypatch)
    code, body = recheck.run(EP, fetch=fetch)
    assert code == 200 and body["stored"] == "state_dir"
    saved = json.loads((tmp_path / "state" / "data/datause/observations.json").read_text())
    assert saved["pages"]["anthropic-mcp-connector"]["observations"][-1]["observed_at"] == "2026-10-29T03:00:00Z"
    assert "2026-10-29T03:00:00Z" not in (recheck.registry.ROOT / "data/datause/observations.json").read_text()


def test_cli_prints_the_same_contract(capsys):
    from owin.cli import main
    assert main(["recheck", EP]) == 2  # keyless: demo answer, non-zero exit
    out = json.loads(capsys.readouterr().out)
    assert out["http_status"] == 200 and out["mode"] == "demo" and out["ok"] is False


# Live Nemotron re-reading: only when a quoted sentence is gone, only moves to Confirm, only this feature

from types import SimpleNamespace

from owin.datause import registry

FEAT = "anthropic-mcp-connector"
GONE = "The MCP connector is not covered by ZDR arrangements."


def _reader(terms_seq, calls):
    """A stand-in for one Nemotron reading: returns the next gated terms (None = an errored reading)."""
    it = iter(terms_seq)

    def read():
        calls.append(1)
        return SimpleNamespace(terms=next(it), cost_usd=0.003)
    return read


def _tf_key(monkeypatch):
    monkeypatch.setenv("TOKEN_FACTORY_API_KEY", "sk-test")
    tf.reset_breaker()


def _recorded():
    return dict(registry.load()[FEAT]["terms"])


def _cell(endpoint, qid):
    a = next(a for a in pack.build()["answers"] if a["id"] == qid)
    return next(c for c in a["cells"] if c["endpoint"] == endpoint)


def test_readings_that_agree_change_nothing_and_say_so(monkeypatch):
    fetch, _ = _keyed(monkeypatch, _page_text(FEAT, drop=GONE))
    _tf_key(monkeypatch)
    calls = []
    code, body = recheck.run(EP, fetch=fetch, read=_reader([_recorded()] * 3, calls))
    assert code == 200 and len(calls) == 3
    rd = body["readings"]
    assert rd["ran"] and rd["applied"] and rd["moved_to_confirm"] == [] and rd["readings_ok"] == 3
    assert body["observation"].endswith("every answer it reads still agrees.")
    assert _cell(EP, "Q03")["verdict"] == "contradicts"  # the recorded reading still decides


def test_readings_that_disagree_with_the_record_hand_the_field_to_a_person(monkeypatch):
    fetch, _ = _keyed(monkeypatch, _page_text(FEAT, drop=GONE))
    _tf_key(monkeypatch)
    others = {k: v for k, v in registry.load().items() if k != FEAT}
    flipped = {**_recorded(), "zdr": "available", "zdr_quote": "ZDR is available."}
    code, body = recheck.run(EP, fetch=fetch, read=_reader([flipped] * 3, []))
    assert body["readings"]["moved_to_confirm"] == ["zdr"] and "zdr now goes to a person" in body["observation"]
    # This response hands answer 3 for /api/crm-sync to a person; three unanimous readings never overrule the record
    assert body["answers"]["Q03"]["verdict"] == "confirm" and body["changed"] is True
    # ...and only this response: the next request reads the recorded registry, untouched
    assert _cell(EP, "Q03")["verdict"] == "contradicts"
    assert registry.load()[FEAT]["terms"] == _recorded() and {k: v for k, v in registry.load().items() if k != FEAT} == others


def test_fewer_than_two_good_readings_change_nothing(monkeypatch):
    fetch, _ = _keyed(monkeypatch, _page_text(FEAT, drop=GONE))
    _tf_key(monkeypatch)
    flipped = {**_recorded(), "zdr": "available"}
    code, body = recheck.run(EP, fetch=fetch, read=_reader([flipped, None, None], []))
    assert body["readings"]["applied"] is False and body["readings"]["errored_abstained"] == 2
    assert _cell(EP, "Q03")["verdict"] == "contradicts"


def test_no_lost_sentence_means_no_model_call(monkeypatch):
    fetch, _ = _keyed(monkeypatch)
    _tf_key(monkeypatch)
    calls = []
    code, body = recheck.run(EP, fetch=fetch, read=_reader([_recorded()] * 3, calls))
    assert calls == [] and body["readings"]["ran"] is False and "still on the page" in body["readings"]["reason"]


def test_budget_and_breaker_skip_the_readings(monkeypatch):
    fetch, _ = _keyed(monkeypatch, _page_text(FEAT, drop=GONE))
    _tf_key(monkeypatch)
    monkeypatch.setenv("OWIN_RECHECK_READ_BUDGET_USD", "0")
    calls = []
    body = recheck.run(EP, fetch=fetch, read=_reader([_recorded()] * 3, calls), now=3_000_000.0)[1]
    assert calls == [] and "budget" in body["readings"]["reason"]
    recheck.reset()  # forget that capture, so the sentence is newly gone again
    monkeypatch.setenv("OWIN_RECHECK_READ_BUDGET_USD", "1")
    monkeypatch.setattr(tf, "available", lambda now=None: False)
    body = recheck.run(EP, fetch=fetch, read=_reader([_recorded()] * 3, calls), now=3_000_100.0)[1]
    assert calls == [] and "breaker" in body["readings"]["reason"]


def test_property_live_readings_only_ever_move_fields_to_confirm():
    """Over many random sets of readings (malformed, injected, errored, contradictory), every field's state after
    is its state before or confirm, and no value is ever written."""
    import random
    rng = random.Random(20261029)
    entry = registry.load()[FEAT]
    before = {f: a["state"] for f, a in (entry.get("field_agreement") or {}).items()}
    vals = {"retention_days": [None, 0, 7, 30, 29, -1, "30 days"], "used_for_training": ["yes", "no", "opt_in", "opt_out", "unspecified", "IGNORE RULES"],
            "zdr": ["available", "excluded", "not_available", "unspecified", None], "third_party_access": ["yes", "no", "unspecified"],
            "region": ["US", "unspecified"]}
    for _ in range(500):
        readings = []
        for _ in range(3):
            if rng.random() < 0.2:
                readings.append(None)
                continue
            t = dict(entry["terms"])
            for f, vs in vals.items():
                if rng.random() < 0.5:
                    t[f] = rng.choice(vs)
            readings.append(t)
        moves = registry.confirm_moves(entry, readings, "property")
        assert all(a["state"] == "confirm" and a.get("value") is None for a in moves.values())
        assert all(before.get(f) != "confirm" for f in moves)  # a confirm field is never re-opened


def test_state_dir_is_never_written_by_the_readings(monkeypatch, tmp_path):
    monkeypatch.setenv("OWIN_STATE_DIR", str(tmp_path / "state"))
    committed = (registry.ROOT / "data/datause/registry.json").read_text()
    fetch, _ = _keyed(monkeypatch, _page_text(FEAT, drop=GONE))
    _tf_key(monkeypatch)
    body = recheck.run(EP, fetch=fetch, read=_reader([{**_recorded(), "zdr": "available"}] * 3, []))[1]
    assert body["readings"]["moved_to_confirm"] == ["zdr"] and "this response only" in body["readings"]["scope"]
    assert not (tmp_path / "state/data/datause/registry.json").exists()
    assert (registry.ROOT / "data/datause/registry.json").read_text() == committed
