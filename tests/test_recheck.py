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
