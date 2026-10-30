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


def test_background_loop_is_served_with_byte_ranges():
    import http.client
    import threading
    names = re.findall(r'data-(?:av1|h264)="/img/([a-z0-9-]+\.mp4)"', ABOUT)
    assert len(names) == 2
    for n in names:
        code, ctype, body = server.handle(f"/img/{n}", {})
        assert code == 200 and ctype == "video/mp4" and body[4:8] == b"ftyp", n
    assert server.byte_range("bytes=0-99", 1000) == (0, 99) and server.byte_range("bytes=900-", 1000) == (900, 999)
    assert server.byte_range("bytes=-100", 1000) == (900, 999) and server.byte_range("bytes=0-5000", 1000) == (0, 999)
    for bad in (None, "bytes=5-1", "bytes=a-b", "items=0-1", "bytes=0-1,4-5", "bytes=2000-"):
        assert server.byte_range(bad, 1000) is None, bad
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
        conn.request("GET", f"/img/{names[0]}", headers={"Range": "bytes=0-1023"})
        r = conn.getresponse()
        assert r.status == 206 and r.getheader("Accept-Ranges") == "bytes" and len(r.read()) == 1024
        assert r.getheader("Content-Range").startswith("bytes 0-1023/")
        conn.request("GET", "/about")
        r = conn.getresponse()
        assert r.status == 200 and b'class="loop"' in r.read()
    finally:
        srv.shutdown()


def test_loop_plays_only_with_motion_and_has_the_still_as_poster():
    v = re.search(r"<video[^>]*>", ABOUT).group(0)
    for attr in ("muted", "loop", "playsinline", 'preload="none"', 'aria-hidden="true"', 'poster="/img/about-hero-1800.webp"'):
        assert attr in v, attr
    assert "src=" not in v.replace("data-av1", "").replace("data-h264", "")  # sources are attached by the script, never without motion
    assert "html:not(.motion) .loop{display:none}" in CSS and "v.pause()" in JS


def test_stamps_are_never_tilted():
    assert "rotate(" not in CSS


def test_image_route_is_an_allowlist():
    for path in ("/img/../about.html", "/img/", "/img/nope.avif", "/img/about-hero-2000.png", "/web/img/about-hero-2000.avif",
                 "/img/..%2fabout.html", "/about.html"):
        assert server.handle(path, {})[0] == 404, path


def test_stills_and_loops_stay_small():
    sizes = {name: (webui.WEB / name).stat().st_size for name, _ in webui.IMAGES.values()}
    assert 0 < sum(v for k, v in sizes.items() if not k.endswith(".mp4")) < 2_000_000
    assert 0 < sum(v for k, v in sizes.items() if k.endswith(".mp4")) < 4_000_000


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
    assert "fictional company" not in TEXT


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
    for href in ('href="/judge"', 'href="/app"', 'href="https://github.com/Zen-cronic/owin"'):
        assert href in ABOUT, href
    assert "no login, no key" not in ABOUT


def test_about_client_code_carries_no_secrets():
    for name, text in (("about.html", ABOUT), ("about.css", CSS), ("about.js", JS)):
        for needle in ("tvly-", "nvapi-", "TAVILY_API_KEY", "FAL_API_KEY", "Bearer "):
            assert needle not in text, (name, needle)


def test_palette_is_the_answer_screens():
    app = (webui.WEB / "app.css").read_text()
    tok = lambda text, name: re.search(rf"{re.escape(name)}:(#[0-9A-Fa-f]{{6}})", text).group(1).upper()  # noqa: E731
    same = ("--field", "--frame", "--act", "--rule-cyan", "--stamp-stale", "--stamp-confirm",
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


def test_logo_and_icons_are_served_and_linked_on_every_page():
    for path, kind in (("/img/favicon.ico", "image/x-icon"), ("/img/favicon.svg", "image/svg+xml"),
                       ("/img/apple-touch-icon.png", "image/png"), ("/img/logo.svg", "image/svg+xml"),
                       ("/img/logo-dark.svg", "image/svg+xml"), ("/img/social-card.png", "image/png")):
        code, ctype, body = server.handle(path, {})
        assert code == 200 and ctype == kind and isinstance(body, bytes) and body, path
    for page in ("index.html", "judge.html", "about.html"):
        html = (webui.WEB / page).read_text()
        assert '<link rel="icon" href="/img/favicon.ico" sizes="32x32">' in html, page
        assert '<link rel="icon" href="/img/favicon.svg" type="image/svg+xml">' in html, page
        assert '<link rel="apple-touch-icon" href="/img/apple-touch-icon.png">' in html, page
    assert 'src="/img/logo-dark-small.svg" alt="Owin"' in ABOUT and 'src="/img/logo-dark.svg" alt="Owin"' in ABOUT
    assert '<a class="word" href="/about" aria-label="Owin">' in ABOUT
    for path in ("/img/logo.SVG", "/img/favicon.gif", "/img/../README.md"):
        assert server.handle(path, {})[0] == 404, path
