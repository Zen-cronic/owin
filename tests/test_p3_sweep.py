import json

import pytest

from owin import sweep, tavily
from owin.entities import entity_key, html_tables, entities_from_tables, linked_rows, parse_any, vanta_cards

CARDS = """[Skip to navigation](https://trust.example.com/#nav)
# Welcome to the Example Trust Center
Subscribe to updates Ask a question
## Subprocessors
![Image 2: Logo](https://trust.example.com/logos/a)
Google Cloud Platform
•
Cloud infrastructure
Worldwide
Products: All Products
1-10 of 2
All subprocessors

Google Cloud Platform

Products: All Products

Cloud infrastructure

Worldwide

cloud.google.com

Stripe

Product: Billing only [More Information](https://x.example)

Billing

United States
"""

TABLE = """Last updated: October 14, 2026

| **Entity Name** | **Product** | **Location of Processing** | **Purpose of Processing** |
| --- | --- | --- | --- |
| Cloudflare, Ltd. | API | United States | CDN |
| Microsoft Corporation | API | Canada Ireland | Cloud infrastructure |
"""


def entry(tmp_path, content, vendor="acme", name="acme.txt"):
    p = tmp_path / name
    p.write_text(content)
    return {"vendor": vendor, "display": vendor.title(), "list_url": f"https://{vendor}.example/subprocessors",
            "watch_mode": "table", "fixture": str(p)}


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("OWIN_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("OWIN_ENV_FILE", str(tmp_path / "no.env"))


# Normalisation: boilerplate never produces a diff

def test_cards_parse_both_layouts_and_collapse_the_pager_duplicate():
    ents = vanta_cards(CARDS)
    assert [e.name for e in ents] == ["Google Cloud Platform", "Stripe"]
    assert ents[1].services == "Billing only"


def test_entity_key_ignores_suffix_and_punctuation():
    assert entity_key("Cloudflare, Ltd.") == entity_key("**Cloudflare**") == entity_key("cloudflare inc")


def test_boilerplate_only_change_is_no_change(tmp_path):
    e = entry(tmp_path, TABLE)
    assert sweep.sweep_one(e, live=False)["state"] == "watching"
    noisy = ("[Skip to content](#main)\nCookie banner: we use cookies\n" + TABLE.replace("| Cloudflare, Ltd. |", "|  **Cloudflare, Ltd.**   |")
             + "\n\nFooter (c) 2026 [Privacy](https://x)\n")
    (tmp_path / "acme.txt").write_text(noisy)
    r = sweep.sweep_one(e, live=False)
    assert r["state"] == "no_change" and "no live re-fetch" in r["reason"]


def test_added_entity_and_location_are_changes(tmp_path):
    e = entry(tmp_path, TABLE)
    sweep.sweep_one(e, live=False)
    (tmp_path / "acme.txt").write_text(TABLE.replace("Canada Ireland", "Canada Ireland Malaysia")
                                       + "| Baseten Labs Inc. | API | United States | Model inference |\n")
    r = sweep.sweep_one(e, live=False)
    assert r["state"] == "changed" and r["material"] == 2  # Baseten added + Microsoft in Malaysia
    assert {c["entity"] for c in r["changes"]} == {"Baseten Labs Inc.", "Microsoft Corporation"}


def test_stale_source_is_held_and_does_not_overwrite(tmp_path):
    e = entry(tmp_path, TABLE)
    sweep.sweep_one(e, live=False)
    (tmp_path / "acme.txt").write_text(TABLE.replace("October 14, 2026", "July 9, 2026").replace("| Cloudflare, Ltd. | API | United States | CDN |\n", ""))
    r = sweep.sweep_one(e, live=False)
    assert r["state"] == "stale_source" and r["held"]
    state = json.loads((tmp_path / "state" / "acme.json").read_text())
    assert state["last_updated"] == "October 14, 2026" and len(state["entities"]) == 2


def test_not_watchable_and_date_only(tmp_path):
    assert sweep.sweep_one(entry(tmp_path, "## Subprocessors\n\n(loading…)\n", "jsy"), live=False)["state"] == "not_watchable"
    d = entry(tmp_path, "Updated October 12, 2026\n[PDF](https://x/a.pdf)\n", "pdfco", "pdfco.txt")
    assert sweep.sweep_one(d, live=False)["state"] == "watching"
    (tmp_path / "pdfco.txt").write_text("Updated October 20, 2026\n[PDF](https://x/b.pdf)\n")
    assert sweep.sweep_one(d, live=False)["state"] == "date_only_changed"


# Tavily: live path re-fetches before "no change"; no key -> labelled fixture

def test_live_no_change_requires_a_refetch(tmp_path, monkeypatch):
    e = entry(tmp_path, TABLE)
    monkeypatch.setattr(tavily, "api_key", lambda: "tvly-test")
    calls = []
    monkeypatch.setattr(tavily, "extract", lambda url, depth="basic", key=None: (calls.append(depth),
                        tavily.Fetched(url, TABLE, "tavily", "2026-10-21T00:00:00Z"))[1])
    assert sweep.sweep_one(e)["state"] == "watching"
    r = sweep.sweep_one(e)
    assert r["state"] == "no_change" and r["refetched"] and r["source_kind"] == "tavily"
    assert calls == ["basic", "basic", "advanced"]


def test_refetch_can_reveal_a_change_the_cache_hid(tmp_path, monkeypatch):
    e = entry(tmp_path, TABLE)
    monkeypatch.setattr(tavily, "api_key", lambda: "tvly-test")
    monkeypatch.setattr(tavily, "extract", lambda url, depth="basic", key=None: tavily.Fetched(url, TABLE, "tavily", "t"))
    sweep.sweep_one(e)
    fresh = TABLE + "| Groq, Inc. | API | United States | Model inference |\n"
    r = sweep.sweep_one(e, refetch=lambda en: tavily.Fetched(en["list_url"], fresh, "tavily", "t"))
    assert r["state"] == "changed" and r["refetched"]


def test_no_key_uses_labelled_fixture_or_unfetched(tmp_path):
    f = tavily.fetch(entry(tmp_path, TABLE))
    assert f.source_kind == "fixture" and f.content
    g = tavily.fetch({"vendor": "x", "list_url": "https://x.example", "fixture": None})
    assert g.source_kind == "unfetched" and "TAVILY_API_KEY" in g.error
    assert tavily.extract("https://x.example").source_kind == "unfetched"  # no network without a key


def test_extract_sends_no_query(monkeypatch):
    seen = {}

    def fake_post(path, body, key, timeout=60):
        seen.update(path=path, body=body)
        return {"results": [{"url": body["urls"][0], "raw_content": "x"}]}
    monkeypatch.setattr(tavily, "_post", fake_post)
    assert tavily.extract("https://a.example", key="k").source_kind == "tavily"
    assert seen["path"] == "/extract" and "query" not in seen["body"]


# Parsers and index

def test_html_tables_collapse_duplicates():
    html = ("<table><tr><th>Entity Name</th><th>Location</th></tr><tr><td>A Inc.</td><td>US<br/>CA</td></tr></table>"
            "<table><tr><th>Entity Name</th><th>Location</th></tr><tr><td>A, Inc</td><td>US</td></tr></table>")
    ents = entities_from_tables(html_tables(html))
    assert len(ents) == 1 and ents[0].locations == "US; CA"


def test_linked_rows_merge_sections():
    md = "**Cloud**\n[Google LLC](https://policies.google.com/privacy)Data Cloud US\n**Pipeline**\n[Google LLC](https://policies.google.com/privacy)Data Pipeline US\n"
    ents = linked_rows(md)
    assert len(ents) == 1 and "Pipeline" in ents[0].purpose
    assert parse_any(md)[2] == "linked_rows"


def test_index_is_a_25_to_40_vendor_seed_list():
    idx = sweep.load_index()
    assert 25 <= len(idx) <= 40 and len({v["vendor"] for v in idx}) == len(idx)
    assert all(v["list_url"].startswith("https://") for v in idx)


def test_full_sweep_without_key_reports_unfetched_honestly():
    out = sweep.run(live=True)
    assert out["tavily_key_present"] is False
    assert all(r["state"] != "changed" or r["source_kind"] != "unfetched" for r in out["rows"])
    assert out["vendors"] == len(sweep.load_index())
