"""Evidence typing: every citation says whether it is a sentence, a table row or a list entry."""
import json

from owin import webui
from owin.datause import evidence, pack, registry

DEMO_PATHS = [[], [("/api/crm-sync", "anthropic-messages")],
              [("/api/crm-sync", "anthropic-messages"), ("/api/embed", "openai-responses")],
              [("/api/crm-sync", "thin-anthropic-rate-limits")]]


def _build(sets):
    m = pack.load_demo()
    for a, b in sets:
        m = pack.set_feature(m, a, b)
    return pack.build(m)


def test_every_cited_quote_is_typed():
    for sets in DEMO_PATHS:
        for a in _build(sets)["answers"]:
            for c in a["cells"]:
                if c["quote"]:
                    assert c["evidence"]["kind"] in ("sentence", "table_row", "list_entry"), (a["id"], c["endpoint"])
                for o in (c.get("confirm") or {}).get("options", []):
                    if o["quote"]:
                        assert o["evidence"]["kind"] in ("sentence", "table_row", "list_entry")


def test_table_evidence_is_key_value_with_the_answering_cell_marked():
    p = _build(DEMO_PATHS[0])
    c = next(c for c in next(a for a in p["answers"] if a["id"] == "Q03")["cells"] if c["endpoint"] == "/api/embed")
    ev = c["evidence"]  # OpenAI's endpoint table row for /v1/embeddings, cited for ZDR
    assert ev["kind"] == "table_row" and ev["match_key"] == "Zero Data Retention eligible"
    hit = [r for r in ev["rows"] if r["match"]]
    assert len(hit) == 1 and hit[0]["value"].startswith("Yes")
    assert all(r["key"] for r in ev["rows"])  # header names from the page, not flattened text
    # The same row cited for retention marks the retention cell instead.
    c2 = next(c for c in next(a for a in p["answers"] if a["id"] == "Q02")["cells"] if c["endpoint"] == "/api/embed")
    assert c2["evidence"]["match_key"] == "Abuse monitoring retention"


def test_flattened_table_text_resolves_to_its_row():
    q = registry.load()["anthropic-messages"]["terms"]["zdr_quote"]  # Anthropic's ZDR table row, flattened by the capture
    assert q.startswith("Messages API/v1/messagesYesYes")
    ev = evidence.for_quote(q, "zdr")
    assert ev["kind"] == "table_row" and ev["match_key"] == "ZDR eligible"


def test_shape_fallback_without_the_index():
    assert evidence.from_shape("| a | b | c |")["kind"] == "table_row"
    assert evidence.from_shape("- one item")["kind"] == "list_entry"
    assert evidence.from_shape("A plain sentence.")["kind"] == "sentence"


def test_q05_cites_the_changed_list_entries_never_a_feature_sentence():
    for sets in DEMO_PATHS:
        q5 = next(a for a in _build(sets)["answers"] if a["id"] == "Q05")
        entries = [e for c in q5["cells"] for e in (c.get("list_evidence") or [])]
        cf = next(e for e in entries if e["entity"] == "Cloudflare, Ltd.")
        assert cf["change"] == "changed"
        assert any(r["match"] and "Cloudflare Regional Services" in r["value"] for r in cf["rows"])
        assert any(e["entity"] == "OAI International, Inc." and e["change"] == "added" for e in entries)
        assert "MCP servers" not in json.dumps(entries)


def test_ui_renders_typed_evidence_and_a_solid_confirm_box():
    js, css = (webui.WEB / "app.js").read_text(), (webui.WEB / "app.css").read_text()
    assert "evidenceView" in js and "listEntryView" in js and "table" in js
    box = css[css.index(".confirm-box{"):].split("}")[0]
    assert "solid" in box and "dashed" not in box
    assert "underline dashed" not in css and "underline dotted" not in css
    html = (webui.WEB / "judge.html").read_text()
    assert 'class="cmd"' in html and "white-space:nowrap" in css[css.index("code.cmd"):].split("}")[0]
