"""Text normalisation shared by extraction, the verbatim-quote gate and the diff.

Every comparison against source text goes through `match_form`, so markdown
emphasis (`**Objection**`), link syntax, curly quotes and whitespace never cause
a false "not verbatim" or a false diff.
"""
from __future__ import annotations

import hashlib
import html
import re
from html.parser import HTMLParser

_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_AUTOLINK = re.compile(r"<(https?://[^>]+|mailto:[^>]+)>")
_ANCHOR = re.compile(r"\[#\]\(#[^)]*\)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.M)
_EMPH = re.compile(r"[*_`]+")
_ESC = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|>~])")
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}.*$", re.M)
_QUOTES = {"“": '"', "”": '"', "‘": "'", "’": "'", " ": " ",
           "–": "-", "—": "-", "​": ""}


def strip_markdown(text: str) -> str:
    """Remove markdown syntax but keep the words, line structure and numbers."""
    t = _ANCHOR.sub("", text)
    t = _LINK.sub(r"\1", t)
    t = _AUTOLINK.sub(r"\1", t)
    t = _ESC.sub(r"\1", t)
    t = _TABLE_RULE.sub("", t)
    t = _HEADING.sub("", t)
    t = _EMPH.sub("", t)
    return t


def unify_chars(text: str) -> str:
    for a, b in _QUOTES.items():
        text = text.replace(a, b)
    return text


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def match_form(text: str) -> str:
    """Canonical form for verbatim checks: no markdown, plain quotes, one space, lower case."""
    return squash(unify_chars(strip_markdown(text))).lower()


def is_verbatim(quote: str, source: str) -> bool:
    q = match_form(quote or "")
    return len(q) >= 20 and q in match_form(source)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _TextOnly(HTMLParser):
    BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "tr", "section", "br", "table", "ul", "ol"}
    SKIP = {"script", "style", "svg", "noscript", "head"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(raw_html: str) -> str:
    """Stdlib HTML to plain text (used for archived snapshots, e.g. web.archive.org id_ captures)."""
    p = _TextOnly()
    p.feed(raw_html)
    t = html.unescape("".join(p.out))
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", t)
    return t.strip()
