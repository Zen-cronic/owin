"""The product UI routes: static files, the swap-control catalog and the per-page watch status."""
import json

from owin import server, webui


def test_root_serves_the_app_and_debug_moves():
    code, ctype, body = server.handle("/", {})
    assert code == 200 and ctype.startswith("text/html") and 'src="/app.js"' in body
    for path, kind in (("/app.js", "javascript"), ("/app.css", "css")):
        code, ctype, _ = server.handle(path, {})
        assert code == 200 and kind in ctype
    assert "Owin debug" in server.handle("/debug", {})[2]


def test_static_route_is_an_allowlist():
    assert server.handle("/../pyproject.toml", {})[0] == 404
    assert server.handle("/web/app.js", {})[0] == 404


def test_catalog_lists_every_feature_with_provider():
    code, _, body = server.handle("/api/catalog", {})
    feats = {f["id"]: f for f in json.loads(body)["features"]}
    assert code == 200 and {"anthropic-mcp-connector", "anthropic-messages", "openai-embeddings"} <= set(feats)
    assert feats["openai-embeddings"]["provider_display"] == "OpenAI"


def test_watch_holds_the_stale_tavily_copy_of_the_openai_list():
    pages = {p["page"]: p for p in webui.watch()["pages"]}
    o = pages["openai-subprocessors"]
    assert o["status"] == "held_copy" and "July 9, 2026" in o["note"] and o["trusted_last_updated"] == "October 14, 2026"
    assert pages["anthropic-mcp-connector"]["status"] == "watching"


def test_client_code_carries_no_secrets():
    for name in ("index.html", "app.js", "app.css", "judge.html", "judge.js"):
        text = (webui.WEB / name).read_text()
        for needle in ("tvly-", "sk-", "nvapi-", "TAVILY_API_KEY", "Bearer "):
            assert needle not in text, (name, needle)


def test_judge_page_and_selective_api():
    code, ctype, body = server.handle("/judge", {})
    assert code == 200 and ctype.startswith("text/html") and 'src="/judge.js"' in body
    for path in ("/", "/?set=/api/crm-sync=anthropic-messages", "/?set=/api/crm-sync=thin-anthropic-rate-limits"):
        assert f'href="{path}"' in body
    assert server.handle("/judge.js", {})[0] == 200
    code, _, body = server.handle("/api/selective", {})
    s = json.loads(body)["selective"]
    assert code == 200 and (s["auto_answered"], s["auto_correct"], s["sent_to_confirm"]) == ("27/33", "26/27", 6)


def test_judge_copy_rules():
    text = (webui.WEB / "judge.html").read_text().lower() + (webui.WEB / "judge.js").read_text().lower()
    assert "compliant" not in text and "open source" not in text and "open-weight" in text
    assert "not legal advice" in text


def test_repo_docs_are_an_allowlist():
    assert server.handle("/README.md", {})[0] == 200
    assert server.handle("/pyproject.toml", {})[0] == 404
