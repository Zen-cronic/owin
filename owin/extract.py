"""Nemotron reads the clause; code validates it.

The model only proposes WindowTerms. `validate` decides whether the decision
layer may use them: the quote must appear verbatim (after markdown stripping)
in the source, and "none" always holds the vendor.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from . import tokenfactory as tf
from .schema import SchemaError, WindowTerms, coerce
from .textnorm import is_verbatim, sha256, strip_markdown

MAX_CHARS = 24000
_KEY = re.compile(r"sub-?processor|object", re.I)

PROMPT = """You are a contracts analyst. Below is text from a vendor's Data Processing Addendum (DPA) or sub-processor terms.
Find the provision about the CUSTOMER objecting to a NEW sub-processor (not data-subject objections, not audit objections).

Return STRICT JSON only, no prose, no code fences, with exactly these keys:
{"window_type": "window"|"exit_only"|"none", "window_days": int or null, "unit": "calendar"|"business"|"unspecified"|"n/a", "clock_start": "notice"|"page_update"|"other"|"n/a", "clock_start_text": str, "remedy": str, "deemed_consent_if_silent": bool, "quote": str}

Rules:
- window_type = "window" when the text gives the customer a stated number of days within which to object, including objecting by terminating. If the text says the customer may object "within that period" after a stated advance-notice period, that notice period is the window.
- window_type = "exit_only" when the text addresses objecting to new sub-processors but sets NO deadline for the objection; the customer's only options are to terminate, stop using the service, or move data. An advance-notice period ALONE is not an objection window.
- window_type = "none" when the text contains no provision about objecting to new sub-processors (for example the text is only headings, a list of companies, or unrelated terms). Never guess from general knowledge.
- window_days = the number of days for "window"; null otherwise.
- unit = "calendar" or "business" only if the text says so explicitly; otherwise "unspecified". Use "n/a" when there is no window.
- clock_start = what starts the clock: "notice" (the vendor's notice or the customer receiving it), "page_update" (an update of a web page or list), "other", or "n/a" when there is no window. clock_start_text = the triggering event in a few words.
- remedy = what the customer can do if the objection is not resolved, in a few words.
- deemed_consent_if_silent = true only if the text says the customer is deemed to consent/approve/accept when it does not object (or terminate) in time.
- quote = the sentence from the text that states the window (or, for "exit_only", the sentence listing the options), copied VERBATIM, character for character, with no ellipsis. Use "" for "none".

TEXT:
<<<
{text}
>>>"""


def select_text(text: str) -> tuple[str, str]:
    """Whole document if small; else the paragraphs around keyword hits, kept in document order."""
    if len(text) <= MAX_CHARS:
        return text, "whole"
    paras = [p for p in re.split(r"\n\s*\n|\n(?=\s*[-*|#]|\s*\d+\.)", text) if p.strip()]

    def clip(p: str) -> str:
        if len(p) <= 3000:
            return p
        m = _KEY.search(p)
        c = m.start() if m else 0
        return p[max(0, c - 1500): c + 1500]

    def score(p: str) -> int:
        return sum(bool(re.search(rx, p, re.I)) for rx in (r"sub-?processor", r"object", r"\bdays?\b"))

    chosen: set[int] = set()
    total = 0
    for i in sorted(range(len(paras)), key=lambda i: -score(paras[i])):
        if score(paras[i]) == 0:
            break
        for j in (i - 1, i, i + 1):
            if 0 <= j < len(paras) and j not in chosen:
                piece = clip(paras[j])
                if total + len(piece) > MAX_CHARS:
                    continue
                chosen.add(j)
                total += len(piece) + 2
    return "\n\n".join(clip(paras[i]) for i in sorted(chosen)), "keyword-windows"


def parse_json(content: str) -> dict | None:
    c = re.sub(r"^```(?:json)?|```$", "", (content or "").strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", c, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def validate(terms: WindowTerms, source: str) -> WindowTerms:
    reasons = []
    if terms.window_type == "none":
        reasons.append("no objection provision found in the fetched text")
        terms.quote_verbatim = False
    else:
        terms.quote_verbatim = is_verbatim(terms.quote, source)
        if not terms.quote_verbatim:
            reasons.append("quote not found verbatim in source")
    terms.hold_reasons = reasons
    terms.status = "held" if reasons else "ok"
    return terms


@dataclass
class Extraction:
    vendor: str
    model: str
    source_sha256: str
    input_mode: str
    input_chars: int
    latency_s: float
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    finish_reason: str | None
    terms: dict | None
    error: str | None = None
    raw_head: str = ""
    extra: dict = field(default_factory=dict)


def extract(vendor: str, source: str, *, model: str = tf.SUPER, purpose: str = "extract") -> Extraction:
    clean = strip_markdown(source)
    text, mode = select_text(clean)
    c = tf.chat(PROMPT.replace("{text}", text), model=model, purpose=f"{purpose}:{vendor}")
    terms, err = None, c.error
    if not err:
        parsed = parse_json(c.content)
        if parsed is None:
            err = "unparseable JSON"
        else:
            try:
                terms = validate(coerce(parsed), source).to_dict()
            except SchemaError as e:
                err = f"schema: {e}"
    return Extraction(vendor, model, sha256(source), mode, len(text), c.latency_s, c.prompt_tokens,
                      c.completion_tokens, c.cost_usd, c.finish_reason, terms, err,
                      "" if terms else (c.content or "")[:400])
