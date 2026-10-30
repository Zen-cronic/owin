"""The product page (/about): served from the allowlist with its stills as bytes, its numbers equal to the claims
ledger, its catch equal to the demo pack, its palette equal to the answer screen's, and the start page's copy rules."""
import json
import re

from owin import facts, server, webui

ABOUT = (webui.WEB / "about.html").read_text()
CSS = (webui.WEB / "about.css").read_text()
JS = (webui.WEB / "about.js").read_text()
TEXT = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", ABOUT))


def _f(fid):
    return next(f[2] for f in facts.FACTS if f[0] == fid)


def test_about_route_serves_the_page_and_its_assets():
    code, ctype, body = server.handle("/about", {})
    assert code == 200 and ctype.startswith("text/html")
    assert 'href="/about.css"' in body and 'src="/about.js"' in body
    for path, kind in (("/about.css", "css"), ("/about.js", "javascript")):
        code, ctype, _ = server.handle(path, {})
        assert code == 200 and kind in ctype


def test_every_still_the_page_names_is_served_as_bytes():
    names = set(re.findall(r"/img/([a-z0-9-]+\.(?:avif|webp))", ABOUT))
    assert names and {n.rsplit(".", 1)[1] for n in names} == {"avif", "webp"}
    for n in names:
        code, ctype, body = server.handle(f"/img/{n}", {})
        assert code == 200 and isinstance(body, bytes) and len(body) > 1000, n
        if n.endswith(".avif"):
            assert ctype == "image/avif" and body[4:12] == b"ftypavif", n
        else:
            assert ctype == "image/webp" and body[:4] == b"RIFF" and body[8:12] == b"WEBP", n


def test_image_route_is_an_allowlist():
    for path in ("/img/../about.html", "/img/", "/img/nope.avif", "/img/about-hero-2000.png", "/web/img/about-hero-2000.avif",
                 "/img/..%2fabout.html", "/about.html"):
        assert server.handle(path, {})[0] == 404, path


def test_stills_stay_small():
    total = sum((webui.WEB / name).stat().st_size for name, _ in webui.IMAGES.values())
    assert 0 < total < 2_000_000


def test_numbers_on_the_page_are_the_ledger():
    auto, cells = _f("sel.auto").split("/")
    right, _ = _f("sel.correct").split("/")
    maj = _f("sel.majority").split("/")[0]
    assert f'data-k="auto_answered">{auto}<span class="sl">/</span>{cells}<' in ABOUT
    assert f'data-k="auto_correct">{right}<span class="sl">/</span>{auto}<' in ABOUT
    assert f'data-k="sent_to_confirm">{_f("sel.confirm")}<' in ABOUT
    assert f"On {_f('sel.vendors')} AI vendors, {_f('sel.vendors_new')} of them new to Owin" in TEXT
    assert f"{_f('sel.items')} features on {_f('sel.pages')} pages" in TEXT
    assert f"On the {_f('sel.confirm')} answers it handed over, a majority vote would have been right only {maj} times" in TEXT
    assert f"moves the score by {_f('sel.swing')} points" in TEXT
    assert "/api/selective" in JS  # the plates are refreshed from the server's recomputation on load


def test_the_catch_is_the_demo_pack():
    catch = json.loads(server.handle("/api/pack", {"format": ["brief"]})[2])["catch"]
    assert catch["question"] == "Q03" and catch["endpoint"] == "/api/crm-sync"
    assert f"“{catch['quote']}”" in TEXT and f"fetched {catch['fetched_at_local']}" in TEXT
    stated = json.loads((facts.ROOT / "fixtures/demo/stack.json").read_text())["stated"]["answers"]["Q03"]["text"]
    assert f"“{stated}”" in TEXT
    assert "Lumen Notes is a fictional company" in TEXT


def test_founder_line_is_the_start_pages_line_verbatim():
    judge = (webui.WEB / "judge.html").read_text()
    line = re.search(r'<h1 id="story-h"[^>]*>(.*?)</h1>', judge).group(1)
    assert f'<p class="ink" id="ink">{line}</p>' in ABOUT


def test_about_copy_rules():
    low = (ABOUT + JS).lower()
    assert "compliant" not in low and "open source" not in low and "open-source" not in low
    assert "open-weight" in low and "not legal advice" in low
    assert not re.search(r"added cloudflare", low)


def test_about_calls_to_action():
    for href in ('href="/judge"', 'href="/"', 'href="https://github.com/Zen-cronic/owin"'):
        assert href in ABOUT, href
    assert "Try it: no login, no key" in ABOUT


def test_about_client_code_carries_no_secrets():
    for name, text in (("about.html", ABOUT), ("about.css", CSS), ("about.js", JS)):
        for needle in ("tvly-", "nvapi-", "TAVILY_API_KEY", "FAL_API_KEY", "Bearer "):
            assert needle not in text, (name, needle)


def test_palette_is_the_answer_screens():
    app = (webui.WEB / "app.css").read_text()
    tok = lambda text, name: re.search(rf"{re.escape(name)}:(#[0-9A-Fa-f]{{6}})", text).group(1).upper()  # noqa: E731
    same = ("--field", "--frame", "--act", "--act-hover", "--rule-cyan", "--stamp-stale", "--stamp-confirm",
            "--stamp-held", "--ink", "--muted", "--cite", "--on-field", "--on-field-muted")
    for name in same:
        assert tok(CSS, name) == tok(app, name), name
    for mine, theirs in (("--stock", "--bg"), ("--field-deep", "--board"), ("--ruled", "--line")):
        assert tok(CSS, mine) == tok(app, theirs), mine


def test_without_motion_nothing_is_hidden():
    # Motion is opt-in: html.motion is set only when the reader has no reduced-motion preference, and every rule that
    # hides or offsets content for an entrance is scoped under it, so no script or reduced motion reads complete.
    assert "prefers-reduced-motion: no-preference" in ABOUT
    rules = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", rules):
        if re.search(r"opacity:0(?![.\d])", body):
            for sel in selector.split(","):
                sel = sel.strip()
                if sel in ("from", "to") or re.fullmatch(r"[\d.]+%", sel):
                    continue  # a keyframe step; its animation is only applied under .motion
                assert sel.startswith(".motion"), sel
