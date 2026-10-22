"""Credible non-model baseline: the field's default "find 'within N days' near 'object'" rule.

This is what a keyword monitor (or a person skimming with Ctrl-F) does. It uses
the same input text as the model and the same fixed schema, so the comparison
is like for like.
"""
from __future__ import annotations

import re

from .schema import WindowTerms
from .textnorm import squash, strip_markdown, unify_chars

_WORDNUM = {"five": 5, "seven": 7, "ten": 10, "fourteen": 14, "fifteen": 15, "thirty": 30, "sixty": 60, "ninety": 90}
_DAYS = re.compile(r"(?:(\d{1,3})|\b(" + "|".join(_WORDNUM) + r")\b)(?:\s*\(\d{1,3}\))?\s*(calendar|business)?\s*days?", re.I)
_SENT = re.compile(r"(?<=[.;])\s+")


def extract(source: str) -> WindowTerms:
    text = squash(unify_chars(strip_markdown(source)))
    sentences = _SENT.split(text)
    for s in sentences:
        if re.search(r"object", s, re.I) and re.search(r"sub-?processor", " ".join(sentences), re.I):
            m = _DAYS.search(s)
            if m:
                n = int(m.group(1)) if m.group(1) else _WORDNUM[m.group(2).lower()]
                unit = (m.group(3) or "unspecified").lower()
                return WindowTerms("window", n, unit, "notice", "", "", bool(re.search(r"deemed", s, re.I)), s,
                                   quote_verbatim=True, status="ok")
    # No "object ... N days" sentence: fall back to any sub-processor notice period (the usual Ctrl-F answer).
    for s in sentences:
        if re.search(r"sub-?processor", s, re.I):
            m = _DAYS.search(s)
            if m:
                n = int(m.group(1)) if m.group(1) else _WORDNUM[m.group(2).lower()]
                return WindowTerms("window", n, (m.group(3) or "unspecified").lower(), "notice", "", "", False, s,
                                   quote_verbatim=True, status="ok")
    return WindowTerms("none", None, "n/a", "n/a", "", "", False, "", status="held",
                       hold_reasons=["no match"])
