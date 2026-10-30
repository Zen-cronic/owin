"""Plain status names: every word a person reads is a standard one (Not true, Outdated, Needs review, Not stated,
Verified). The badge codes in the API (`stale`, `confirm`, `held_unspecified`, `still_true`) never change; only the
words shown for them do."""
import re

import pytest

from owin import server, webui
from owin.datause import export, pack

PAGES = ("/", "/judge", "/about")
LABELS = {"not_true": "Not true", "stale": "Outdated", "confirm": "Needs review", "held_unspecified": "Not stated",
          "still_true": "Verified"}
# Words the pages used to show, and must not show again. The pictured "rubber stamp" in the /about stills' alt text
# is an object in the photograph, not a status name, so it is the one use of "stamp" allowed.
OLD = re.compile(r"(?i)\bheld\b|\bstale\b|still true|\bconfirm\b|\bstamps?\b|the catch|\bpacks?\b|unspecified")
APP_JS = (webui.WEB / "app.js").read_text()


def _readable(html: str) -> str:
    """The text a reader meets: visible text plus the aria-label, title, alt and placeholder attributes."""
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    attrs = re.findall(r'(?:aria-label|title|alt|placeholder)="([^"]*)"', body)
    return re.sub(r"\s+", " ", " ".join([re.sub(r"<[^>]+>", " ", body), *attrs]))


@pytest.mark.parametrize("path", PAGES)
def test_pages_show_no_old_status_words(path):
    code, _, body = server.handle(path, {})
    assert code == 200
    hits = [m.group(0) for m in OLD.finditer(_readable(body).replace("rubber stamp", ""))]
    assert not hits, (path, hits)


def _table(name: str) -> str:
    m = re.search(rf"const {name} = (\{{.*?\}});", APP_JS, flags=re.S)
    assert m, name
    return m.group(1)


def test_app_label_tables_use_the_plain_words():
    label = dict(re.findall(r"(\w+): '([^']*)'", _table("LABEL")))
    assert label == LABELS
    word = dict(re.findall(r"(\w+): '([^']*)'", _table("WORD")))
    assert word == {k: v.lower() for k, v in LABELS.items()}
    chip = dict(re.findall(r"(\w+): \{[^}]*word: '([^']*)'", _table("CHIP")))
    assert chip == {"contradicts": "Not true", "stale": "Outdated", "confirm": "Needs review", "held": "Not stated"}
    rows = re.search(r"const rows = (\[\[.*?\]\])", APP_JS).group(1)
    assert dict(re.findall(r"\['(\w+)', '([^']*)'\]", rows)) == LABELS


def test_app_code_shows_no_old_status_words():
    code = re.sub(r"/\*.*?\*/", "", re.sub(r"(?m)^\s*//.*$", "", APP_JS), flags=re.S)
    # Capitalised, these are only ever display text; the badge codes are lower case.
    assert not re.findall(r"\b(?:Stale|Held|Confirm|Still true|Stamps?)\b", code)
    # The prose built around the counts.
    for phrase in ("still true", "to confirm", "} stale", "} held", "goes Stale", "answer pack"):
        assert phrase not in code, phrase


def test_python_display_tables_use_the_plain_words():
    assert pack.BADGE_LABEL == LABELS
    for text in (*export.BUYER_STATUS.values(), *export.VERDICT_LABEL.values()):
        assert not OLD.search(text), text


@pytest.mark.parametrize("sets", [(), ("/api/crm-sync=anthropic-messages",), ("/api/crm-sync=thin-anthropic-rate-limits",),
                                  ("/api/embed=openai-responses",)])
def test_computed_sentences_use_the_plain_words(sets):
    m = pack.load_demo()
    for s in sets:
        p, _, f = s.partition("=")
        m = pack.set_feature(m, p, f)
    p = pack.build(m)
    shown = [p["headline"]["text"], p["headline"]["kicker"] or "", *(a["answer"] for a in p["answers"]),
             *(a["badge_label"] for a in p["answers"])]
    for text in shown:
        # "Confirm your settings." is a plain instruction, not a status name.
        assert not OLD.search(text.replace("Confirm your settings", "")), text
    assert {a["badge_label"] for a in p["answers"]} <= set(LABELS.values())
