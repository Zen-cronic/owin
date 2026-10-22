"""Nemotron reads one vendor page for one AI feature; code validates every asserted field.

Reuses the P1 machinery: `tokenfactory.chat`, `extract.parse_json`, `textnorm`.
"""
from __future__ import annotations

import re

from .. import tokenfactory as tf
from ..extract import Extraction, parse_json
from ..textnorm import is_verbatim, sha256, strip_markdown
from .schema import QUOTE_OF, SchemaError, DataUseTerms, asserted, coerce

MAX_CHARS = 40000
_KEYS = (r"retain|retention|retained", r"train|improve", r"zero data retention|\bZDR\b", r"abuse monitoring|logs?\b",
         r"region|residency|geograph|located", r"\bdays?\b|years?\b|until deleted")

PROMPT_VERSION = "v2"
# v1 (frozen for the 2026-10-21T21:08 headline run) is recorded in git history; v2 = repair attempt 1.
PROMPT = """You are a privacy analyst filling in the AI section of a security questionnaire. Below is text from ONE vendor documentation page.
Answer ONLY from this text, for this feature: {feature} (vendor: {vendor}).

Return STRICT JSON only, no prose, no code fences, with exactly these keys:
{"retention_days": int or null, "retention_condition": str, "retention_quote": str,
 "used_for_training": "yes"|"no"|"opt_in"|"opt_out"|"unspecified", "training_quote": str,
 "zdr": "available"|"not_available"|"excluded"|"unspecified", "zdr_quote": str,
 "region": str, "region_quote": str,
 "third_party_access": "yes"|"no"|"unspecified", "third_party_quote": str}

Rules:
- retention_days: the longest stated period, in days, that the vendor keeps customer content (prompts, outputs, files) from THIS feature by default (without zero data retention). Abuse-monitoring and reliability logs count. Ignore exceptions for content flagged as violating policy, legal holds and specific models, unless the feature itself is that case. Use 0 if the text says the content is not retained by default. Use null if content is kept until the customer deletes it, if no number is stated, or if the text does not cover this feature. Convert years to days (x 365). Count only prompts, outputs, files and session content, not metadata, scores or classifier results. If any of this feature's content is kept until the customer deletes it, retention_days is null even when a shorter log period is also stated. retention_condition: a few words (e.g. "until deleted", "abuse logs 30 days").
- used_for_training: "yes" = the text says the content is used to train or improve models and gives no opt-out; "opt_out" = used by default, customer can opt out; "opt_in" = not used unless the customer opts in, shares data, or gives permission (wording such as "unless you opt in", "without your permission or instruction", "without your express permission" means "opt_in", not "no"); "no" = not used, with no opt-in route mentioned. Vendor-wide training statements apply to every feature of that API unless the text says otherwise, and a general "not used unless you opt in" statement makes the answer "opt_in" even when a table cell says "No"; "unspecified" = the text does not say.
- zdr: "available" = the text says zero data retention (or a named control under which the vendor stores no prompts/outputs, such as "modified abuse monitoring") can apply to THIS feature, including on request or approval; "excluded" = the text says THIS feature is not covered by, not eligible for, or cannot be used under ZDR (an eligibility table marking the feature "No" counts; so does a feature that is disabled or rejected under ZDR, or whose storage cannot be turned off); "not_available" = only when the vendor says it offers no ZDR for any feature at all; "unspecified" = the text does not say for this feature. A link or a pointer to another page is NOT an answer: use "unspecified".
- region: where content is processed or stored, as stated; "unspecified" if not stated. third_party_access: whether parties other than the vendor (e.g. the underlying model provider, human reviewers outside the vendor) can see the content; "unspecified" if not stated.
- A single table cell such as "No" is not a quote: quote the whole table row (endpoint name plus its cells, as they appear) or the sentence.
- Every *_quote must be copied VERBATIM, character for character, from the text: the one sentence (or table row) that justifies the field. No ellipsis, no paraphrase. Use "" when the field is null or "unspecified".
- If the text does not cover this feature's data handling at all, return null and "unspecified" everywhere. Never answer from general knowledge about the vendor.

TEXT:
<<<
{text}
>>>"""


def _feature_tokens(feature: str) -> list[str]:
    toks = re.findall(r"/[\w/.\-]+|\b[A-Z][\w\-]{2,}\b", feature)
    return [t for t in toks if t.lower() not in {"api", "the", "and"}]


def select_text(text: str, feature: str) -> tuple[str, str]:
    """Whole page if it fits; else keyword and feature-name paragraphs (plus neighbours) in page order."""
    if len(text) <= MAX_CHARS:
        return text, "whole"
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    ftoks = [re.escape(t) for t in _feature_tokens(feature)]

    def score(p: str) -> int:
        s = sum(bool(re.search(rx, p, re.I)) for rx in _KEYS)
        return s + (3 if ftoks and re.search("|".join(ftoks), p) else 0)

    chosen, total = set(), 0
    for i in sorted(range(len(paras)), key=lambda i: -score(paras[i])):
        if score(paras[i]) < 1:
            break
        for j in (i - 1, i, i + 1):
            if 0 <= j < len(paras) and j not in chosen and total + len(paras[j]) <= MAX_CHARS:
                chosen.add(j)
                total += len(paras[j]) + 2
    return "\n\n".join(paras[i] for i in sorted(chosen)), "keyword-windows"


_NULL = {"retention_days": None, "used_for_training": "unspecified", "zdr": "unspecified", "region": "unspecified",
         "third_party_access": "unspecified"}


def validate(t: DataUseTerms, source: str) -> DataUseTerms:
    """Downgrade every asserted field whose justifying quote is not verbatim in the page."""
    reasons, claimed, verb = [], {}, {}
    for f, q in QUOTE_OF.items():
        quote = getattr(t, q)
        verb[f] = bool(quote) and is_verbatim(quote, source)
        if asserted(t, f) and not verb[f]:
            claimed[f] = getattr(t, f)
            setattr(t, f, _NULL[f])
            reasons.append(f"{f}: {'no quote' if not quote else 'quote not verbatim'}; answer withheld")
    t.verbatim, t.model_claimed, t.hold_reasons = verb, claimed, reasons
    any_answer = any(asserted(t, f) for f in QUOTE_OF)
    t.status = "partial" if reasons else ("ok" if any_answer else "no_terms")
    return t


def extract(item_id: str, vendor: str, feature: str, source: str, *, model: str = tf.SUPER,
            purpose: str = "datause") -> Extraction:
    clean = strip_markdown(source)
    text, mode = select_text(clean, feature)
    prompt = PROMPT.replace("{feature}", feature).replace("{vendor}", vendor).replace("{text}", text)
    c = tf.chat(prompt, model=model, purpose=f"{purpose}:{item_id}", max_tokens=8000)
    terms, err = None, c.error
    if not err:
        parsed = parse_json(c.content)
        if parsed is None:
            err = "unparseable JSON" + (" (truncated: finish_reason=length)" if c.finish_reason == "length" else "")
        else:
            try:
                terms = validate(coerce(parsed), source).to_dict()
            except SchemaError as e:
                err = f"schema: {e}"
    return Extraction(item_id, model, sha256(source), mode, len(text), c.latency_s, c.prompt_tokens,
                      c.completion_tokens, c.cost_usd, c.finish_reason, terms, err,
                      "" if terms else (c.content or "")[:400])
