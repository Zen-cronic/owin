"""The public AI data-use page (/trust): served from the allowlist, built in the browser from the same answers the
app shows (/api/pack), one card per endpoint, plain status words, no slanted arrows, and no demo label up top."""
import re

from owin import server, webui
from owin.datause import pack

HTML = (webui.WEB / "trust.html").read_text()
JS = (webui.WEB / "trust.js").read_text()
CSS = (webui.WEB / "trust.css").read_text()


def test_trust_route_serves_the_page_and_its_assets():
    code, ctype, body = server.handle("/trust", {})
    assert code == 200 and ctype.startswith("text/html")
    assert 'href="/trust.css"' in body and 'src="/trust.js"' in body
    assert 'rel="icon"' in body and "/img/logo-dark" in body
    assert 'href="/app"' in body and 'href="/judge"' in body
    for path, kind in (("/trust.css", "css"), ("/trust.js", "javascript")):
        code, ctype, _ = server.handle(path, {})
        assert code == 200 and kind in ctype


def test_page_reads_the_same_answers_the_app_shows():
    assert 'fetch("/api/pack")' in JS and "quote_display" in JS and "fetched_at_local" in JS and "source_url" in JS
    code, _, _ = server.handle("/api/pack", {})
    assert code == 200


def test_every_endpoint_has_five_answers_with_vendor_evidence():
    p = pack.build()
    paths = [e["path"] for e in p["stack"]["endpoints"]]
    assert paths == ["/api/crm-sync", "/api/summarize", "/api/digest", "/api/embed"]
    assert len(p["answers"]) == 5
    for a in p["answers"]:
        assert {c["endpoint"] for c in a["cells"]} == set(paths)
        for c in a["cells"]:
            assert c["source_url"].startswith("https://") and c["fetched_at_local"].endswith(("EDT", "EST"))
    # The not-true row shows the vendor's own sentence, taken from the vendor page as recorded.
    zdr = next(a for a in p["answers"] if a["field"] == "zdr")
    bad = next(c for c in zdr["cells"] if c["verdict"] == "contradicts")
    assert bad["endpoint"] == "/api/crm-sync" and "not covered by ZDR" in bad["quote_display"]


def test_plain_status_words_and_copy_rules():
    for word in ("Not true", "Outdated", "Needs review", "Not stated", "Verified"):
        assert word in JS and word in HTML
    for src in (HTML, JS, CSS):
        assert not re.search("↗|↘|⤴|&#8599;|&#x2197;|\\\\2197|\\\\u2197", src)
        assert "rotate(" not in src or src is CSS
    assert "Inter" not in CSS
    header = HTML.split("<main", 1)[0] + HTML.split("<main", 1)[1].split("</section>", 1)[0]
    assert "fictional" not in header.lower() and "invented" not in header.lower()
    assert "invented for this demo" in HTML.split("<footer", 1)[1]
