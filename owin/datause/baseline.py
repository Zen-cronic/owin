"""Credible non-model baseline: the keyword reading a reviewer does with Ctrl-F.

Same input page and same schema as the model. It prefers sentences that name the
feature (its endpoint path or product word), then falls back to the whole page.
Rules (written from the tuned split only):
  retention  first retention sentence with "N days / N-day / N years" -> N; "not retained" -> 0; else null
  training   first train/improve sentence that also mentions data/content/prompts: "opt out" -> opt_out; "opt in / permission / unless" -> opt_in;
             a negation -> no; otherwise yes; no sentence -> unspecified
  zdr        first "zero data retention / ZDR" sentence: a negation ("not covered", "does not apply",
             "not eligible", "not available") -> excluded; otherwise available; none -> unspecified
"""
from __future__ import annotations

import re

from ..textnorm import squash, strip_markdown, unify_chars
from .extract import _feature_tokens
from .schema import DataUseTerms

_SENT = re.compile(r"(?<=[.;:!?])\s+|\n+")
_NUM = re.compile(r"\b(\d{1,4})[ -]?(days?|day|years?)\b", re.I)
_RET = re.compile(r"retain|retention|\bstor(e|es|ed|age)\b|\bdeleted?\b|\blog(s|ged)?\b", re.I)
_TRAIN = re.compile(r"\btrain(s|ed|ing)?\b|\bimprove", re.I)
_DATA = re.compile(r"data|content|prompt|input|output|completion", re.I)
_ZDR = re.compile(r"zero data retention|\bZDR\b", re.I)
_NEG = re.compile(r"\bnot\b|n't\b|\bnever\b|\bno\b", re.I)
_ZNEG = re.compile(r"not covered|does not apply|not eligible|not available|not zdr|isn't covered|outside", re.I)


def _sentences(source: str) -> list[str]:
    text = unify_chars(strip_markdown(source))
    return [squash(s) for s in _SENT.split(text) if len(squash(s)) > 15]


def _ordered(sents: list[str], feature: str) -> list[str]:
    toks = _feature_tokens(feature)
    if not toks:
        return sents
    rx = re.compile("|".join(re.escape(t) for t in toks))
    return [s for s in sents if rx.search(s)] + [s for s in sents if not rx.search(s)]


def extract(source: str, feature: str) -> DataUseTerms:
    sents = _ordered(_sentences(source), feature)
    rd, rq = None, ""
    for s in sents:
        if _RET.search(s):
            m = _NUM.search(s)
            if m:
                n = int(m.group(1))
                rd, rq = (n * 365 if m.group(2).lower().startswith("year") else n), s
                break
            if re.search(r"not (be )?retain|does not retain|not stored", s, re.I):
                rd, rq = 0, s
                break
    tr, tq = "unspecified", ""
    for s in sents:
        if _TRAIN.search(s) and _DATA.search(s):
            tq = s
            if re.search(r"opt[ -]?out", s, re.I):
                tr = "opt_out"
            elif re.search(r"opt[ -]?in|permission|unless", s, re.I):
                tr = "opt_in"
            elif _NEG.search(s):
                tr = "no"
            else:
                tr = "yes"
            break
    z, zq = "unspecified", ""
    for s in sents:
        if _ZDR.search(s):
            z, zq = ("excluded" if _ZNEG.search(s) else "available"), s
            break
    t = DataUseTerms(rd, "", rq, tr, tq, z, zq, "unspecified", "", "unspecified", "")
    t.status = "ok" if (rd is not None or tr != "unspecified" or z != "unspecified") else "no_terms"
    return t
