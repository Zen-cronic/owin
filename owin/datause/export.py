"""Buyer report exports: CSV, print-ready HTML (light print tokens, A4) and a read-only share JSON.

The buyer-facing exports (HTML, share JSON) carry the answers, the per-endpoint vendor sentences, sources
and as-of times. The finding, the actions and "Fix" never appear in them (docs/design/brief.md). The print copy
is the document the buyer reads, so it speaks the buyer's language: the company's answers (the corrected
wording where Owin drafted one), a plain status per answer, the vendor's sentence or table row with its link
and fetch time, and nothing addressed to the person who runs Owin (no badges, no "review", no file paths).
"""
from __future__ import annotations

import csv
import html
import io
import re

from ..textnorm import sha256

CSV_COLUMNS = ["question_number", "question", "stated_answer", "status", "endpoint", "feature", "provider", "vendor_value",
               "endpoint_verdict", "quote", "source_url", "fetched_at", "as_of", "outdated"]
# The CSV is read by people, so its status and verdict columns carry words, not the API's enum codes.
VERDICT_LABEL = {"holds": "Supports the answer", "disclosed": "Disclosed exception", "contradicts": "Contradicts the answer",
                 "held": "Not stated", "confirm": "Needs review"}


def to_csv(pack: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for a in pack["answers"]:
        for c in a["cells"]:
            w.writerow([a["number"], a["question"], a["stated"].get("text", ""), a["badge_label"], c["endpoint"], c["feature"],
                        c["provider"], c["value_label"], VERDICT_LABEL.get(c["verdict"], c["verdict"]), c["quote"], c["source_url"], c["fetched_at"] or "",
                        a["as_of"] or "", "yes" if c.get("stale") else ""])
    return buf.getvalue()


# What the buyer reads for each internal state. The internal `status` enum stays in the share JSON for the app;
# the print copy shows only these words.
BUYER_STATUS = {"still_true": "Supported by the vendors' pages", "not_true": "Revised to match the vendors' pages",
                "stale": "A vendor page changed after this answer", "confirm": "Under review",
                "held_unspecified": "Company statement; the vendors' pages do not say"}
_BUYER_PHRASES = (("(your setting)", "(company setting)"), ("(not in your answer)", "(not named in this answer)"),
                  ("Readings disagree: ", "Under review: "))


def buyer_label(label: str | None) -> str:
    """The report's label without any sentence that names a file in the repository."""
    parts = re.split(r"(?<=[.!?])\s+", (label or "").strip())
    return " ".join(x for x in parts if x and not re.search(r"\b[\w.-]+/[\w./-]+\.\w+", x))


def buyer_phrase(s: str) -> str:
    for a, b in _BUYER_PHRASES:
        s = s.replace(a, b)
    return s


def _buyer_change(ev: dict, stated_at: str) -> str:
    """A stale event as a buyer-facing sentence: what changed and when, with nothing addressed to the company's own user."""
    if ev["kind"] == "list_changed":
        return (f"{ev['provider_display']} updated its sub-processor list on {ev['after']['last_updated']} "
                f"(previously {ev['before']['last_updated']}), after this answer was written ({stated_at}).")
    return f"A sentence this answer relied on changed on {ev['provider_display']}'s page after it was written ({stated_at})."


def buyer_answer(pack: dict, a: dict) -> tuple[str, str | None]:
    """(the answer text the buyer reads, a note). A contradicted answer shows the wording Owin drafted when it has
    one (the exceptions spelled out); otherwise the stated text with a note that it is being revised."""
    text = a["stated"].get("text", "")
    fix = (pack.get("catch") or {}).get("fix") if (pack.get("catch") or {}).get("question") == a["id"] else None
    if a["badge"] == "not_true" and fix and fix.get("text"):
        return fix["text"], f"Wording revised on {pack['as_of_local']} to match the vendors' pages."
    if a["badge"] == "not_true":
        return text, "This answer is being revised: one of the vendors' pages does not support it as written."
    if a["badge"] == "held_unspecified" and a["endpoints_holding"]:
        held = [c["endpoint"] for c in a["cells"] if c["verdict"] == "held"]
        return text, (f"Supported by the vendors' pages for {a['endpoints_holding']} of {a['endpoints']} endpoints; "
                      f"for {', '.join(held)} the vendor's page does not state this.")
    if a["badge"] == "held_unspecified":
        return text, "The vendors' pages do not state this; the answer rests on the company's own settings."
    return text, None


def buyer_status(a: dict) -> str:
    if a["badge"] == "held_unspecified" and a["endpoints_holding"]:
        return "Partly stated by the vendors' pages"
    return BUYER_STATUS[a["badge"]]


def to_share(pack: dict) -> dict:
    """Read-only buyer view for the live link. No finding, no actions, no fix, no internal reasons."""
    answers = []
    for a in pack["answers"]:
        text, note = buyer_answer(pack, a)
        answers.append({
            "number": a["number"], "question": a["question"], "answer": text, "note": note,
            "status": a["badge"], "status_label": a["badge_label"], "buyer_status": buyer_status(a),
            "as_of": a["as_of"], "as_of_local": a["as_of_local"],
            "changes": [{"text": _buyer_change(ev, pack["stated_at"])} for ev in a["stale_events"]] if a["badge"] == "stale" else [],
            # A cell that needs review is the startup's own step; the buyer sees only that it is pending.
            "endpoints": [{"endpoint": c["endpoint"], "provider": c["provider"],
                           "vendor_says": "Under review" if c["verdict"] == "confirm" else buyer_phrase(c["value_label"]),
                           "pending_confirmation": c["verdict"] == "confirm",
                           "quote": c["quote"], "quote_display": c.get("quote_display") or c["quote"],
                           "evidence": c.get("evidence"), "list_evidence": c.get("list_evidence") or [],
                           "source_url": c["source_url"], "source_label": c["source_label"],
                           "fetched_at": c["fetched_at"], "fetched_at_local": c["fetched_at_local"]} for c in a["cells"]],
        })
    body = {"type": "owin.answer_pack.share", "version": 1, "readonly": True, "company": pack["company"],
            "label": buyer_label(pack["label"]), "pack_id": pack["pack_id"], "as_of": pack["as_of"], "as_of_local": pack["as_of_local"],
            "answers": answers}
    body["share_id"] = sha256(repr(sorted(body.items())))[:16]
    return body


_CSS = """
@page { size: A4; margin: 14mm 14mm 16mm; }
:root { --prussian:#1B3A5E; --rule:#A4C6DE; --card:#FCFBF7; --paper:#FFFFFF; --ink:#1E1A16; --muted:#5E5A55;
        --not-true:#B3202A; --outdated:#0F6B7F; --not-stated:#5E5A55; --review:#2D3E66; --verified:#1B3A5E; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--card); color: var(--ink);
       font: 400 15px/1.5 "Atkinson Hyperlegible Next", "Atkinson Hyperlegible", "Helvetica Neue", Arial, sans-serif; }
.mono, .ep { font-family: "Atkinson Hyperlegible Mono", ui-monospace, Menlo, Consolas, monospace; }
h1, h2, .chip, .qn { font-family: Parkinsans, "Atkinson Hyperlegible Next", "Helvetica Neue", Arial, sans-serif; }
.band { background: var(--prussian); color: var(--paper); }
.band .in { max-width: 760px; margin: 0 auto; padding: 28px 24px 24px; }
.company { margin: 0 0 6px; font-size: 13px; letter-spacing: .04em; text-transform: uppercase; color: var(--rule); }
h1 { font-weight: 600; font-size: 30px; line-height: 1.15; margin: 0 0 10px; }
.asof { margin: 0; font-size: 14px; color: var(--paper); }
main { max-width: 760px; margin: 0 auto; padding: 8px 24px 32px; background: var(--paper); }
section.q { padding: 22px 0 20px; border-bottom: 1px solid var(--rule); break-inside: avoid; }
.qtop { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 4px; }
.qn { font-size: 13px; font-weight: 500; color: var(--prussian); }
.chip { display: inline-block; font-size: 12.5px; font-weight: 600; line-height: 1; padding: 6px 10px; border-radius: 4px;
        border: 1.5px solid currentColor; white-space: nowrap; }
.chip.not_true { background: var(--not-true); border-color: var(--not-true); color: var(--paper); }
.chip.stale { background: var(--outdated); border-color: var(--outdated); color: var(--paper); }
.chip.confirm { background: var(--review); border-color: var(--review); color: var(--paper); }
.chip.held_unspecified { background: var(--not-stated); border-color: var(--not-stated); color: var(--paper); }
.chip.still_true { background: var(--paper); color: var(--verified); }
h2 { font-weight: 600; font-size: 19px; line-height: 1.3; margin: 0 0 8px; color: var(--ink); }
.answer { margin: 0 0 4px; font-size: 16px; }
.note { margin: 0 0 4px; font-size: 13.5px; color: var(--muted); }
.ev { margin-top: 12px; padding: 10px 0 0 14px; border-left: 3px solid var(--rule); break-inside: avoid; }
.eps { display: flex; flex-wrap: wrap; gap: 4px 12px; margin: 0 0 6px; padding: 0; list-style: none; font-size: 13px; color: var(--prussian); }
.eps .pending { font-weight: 700; color: var(--review); }
blockquote { margin: 0 0 6px; font-size: 15px; overflow-wrap: anywhere; }
.none { margin: 0 0 6px; font-size: 14px; color: var(--muted); }
.kv { margin: 0 0 6px; font-size: 14px; }
.kv div { display: grid; grid-template-columns: minmax(0, 38%) minmax(0, 1fr); gap: 0 12px; padding: 2px 0; }
.kv dt { color: var(--muted); }
.kv dd { margin: 0; overflow-wrap: anywhere; }
.kv .hit dd { font-weight: 700; }
.was { color: var(--muted); font-weight: 400; }
.src { margin: 0; font-size: 13px; color: var(--muted); }
.src a { color: var(--prussian); }
footer { max-width: 760px; margin: 0 auto; padding: 14px 24px 28px; font-size: 12.5px; color: var(--muted); }
@media (max-width: 480px) {
  .band .in, main, footer { padding-left: 16px; padding-right: 16px; }
  h1 { font-size: 25px; }
  .kv div { grid-template-columns: 1fr; }
}
@media print {
  body, main { background: none; }
  .band { background: none; color: var(--prussian); border-bottom: 3px solid var(--prussian); }
  .band .in, main, footer { max-width: none; padding-left: 0; padding-right: 0; }
  .band .in { padding-top: 0; padding-bottom: 12px; }
  .company { color: var(--muted); }
  .asof { color: var(--ink); }
  .chip.not_true, .chip.stale, .chip.confirm, .chip.held_unspecified, .chip.still_true { background: none; }
  .chip.not_true { color: var(--not-true); } .chip.stale { color: var(--outdated); }
  .chip.confirm { color: var(--review); } .chip.held_unspecified { color: var(--not-stated); }
  .src a { color: inherit; text-decoration: none; }
  section.q, .ev { break-inside: avoid; page-break-inside: avoid; }
  h2, .qtop { break-after: avoid; }
}
"""

# The status chip on each question, in the same plain words the app uses.
CHIP_LABEL = {"not_true": "Not true", "stale": "Outdated", "confirm": "Needs review",
              "held_unspecified": "Not stated", "still_true": "Verified"}


def _e(s) -> str:
    return html.escape("" if s is None else str(s))


def _evidence_html(c: dict) -> str:
    """The vendor's evidence, verbatim: a sentence as a quote; a table row as the row's first cell plus the cell that
    answers the question; a changed list entry as its cells. Never a flattened "a · b · c" row."""
    ev = c.get("evidence")
    if c.get("list_evidence"):
        parts = []
        for e in c["list_evidence"]:
            rows = [r for r in e["rows"] if r["match"]] or e["rows"]
            body = "".join(f"<div class=\"{'hit' if r['match'] else ''}\"><dt>{_e(r['key'])}</dt><dd>{_e(r['value'])}"
                           + (f" <span class=\"was\">(was: {_e(r['was'])})</span>" if r.get("was") else "") + "</dd></div>"
                           for r in rows)
            parts.append(f"<dl class=\"kv\"><div><dt>Entry</dt><dd>{_e(e['entity'])} ({_e(e['change'])})</dd></div>{body}</dl>")
        return "".join(parts)
    if not c["quote"]:
        return ""
    if ev and ev["kind"] == "table_row":
        rows = [r for r in ev["rows"] if r["value"]]
        keep = [r for i, r in enumerate(rows) if i == 0 or r["match"]]
        body = "".join(f"<div class=\"{'hit' if r['match'] else ''}\"><dt>{_e(r['key'] or '')}</dt><dd>{_e(r['value'])}</dd></div>"
                       for r in keep)
        return f"<dl class=\"kv\">{body}</dl>"
    text = ev["text"] if ev and ev["kind"] == "list_entry" else c["quote"].strip()
    return f"<blockquote>“{_e(text)}”</blockquote>"


def _no_quote(a: dict, c: dict) -> str:
    if c.get("pending_confirmation"):
        return "Needs review by the company."
    if a["number"] == "05":
        return "No further third party is named on this page."
    return "Not stated on the vendor's page."


def _short_note(pack: dict, a: dict) -> str | None:
    """One short line under the answer, only where the chip alone would not explain it."""
    if a["status"] == "not_true" and a["note"] and a["note"].startswith("Wording revised"):
        return f"Revised on {pack['as_of_local'][:10]} to match the vendors' pages."
    if a["status"] == "not_true":
        return "Being revised: a vendor's page does not support it as written."
    return None


def to_html(pack: dict) -> str:
    """Print-ready buyer report. Open in a browser and print to PDF."""
    share = to_share(pack)
    out = ["<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
           f"<title>{_e(pack['company'])}: security review, AI and data</title>",
           "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
           "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\"><link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>",
           "<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible+Mono:wght@400;500"
           "&family=Atkinson+Hyperlegible+Next:wght@400;700&family=Parkinsans:wght@500;600&display=swap\">",
           f"<style>{_CSS}</style></head><body>",
           "<header class=\"band\"><div class=\"in\">",
           f"<p class=\"company\">{_e(pack['company'])}</p>",
           "<h1>Security review: AI and data</h1>",
           f"<p class=\"asof\">Answers as of {_e(pack['as_of_local'][:10])}. Every quote is the vendor's own text.</p>",
           "</div></header><main>"]
    by_num = {a["number"]: a for a in share["answers"]}
    for num in sorted(by_num):
        a = by_num[num]
        out.append(f"<section class=\"q\"><div class=\"qtop\"><span class=\"qn\">Question {int(num)}</span>"
                   f"<span class=\"chip {_e(a['status'])}\">{_e(CHIP_LABEL[a['status']])}</span></div>"
                   f"<h2>{_e(a['question'])}</h2><p class=\"answer\">{_e(a['answer'])}</p>")
        note = _short_note(pack, a)
        if note:
            out.append(f"<p class=\"note\">{_e(note)}</p>")
        for ch in a["changes"]:
            out.append(f"<p class=\"note\">{_e(ch['text'])}</p>")
        # Endpoints that share the same vendor evidence are listed together under one quote.
        groups: dict[str, list[dict]] = {}
        for c in a["endpoints"]:
            ev = _evidence_html(c) or f"<p class=\"none\">{_e(_no_quote(a, c))}</p>"
            groups.setdefault(ev, []).append(c)
        for ev, cells in groups.items():
            eps = "".join(f"<li class=\"ep\">{_e(c['endpoint'])}</li>" for c in cells)
            if any(c.get("pending_confirmation") for c in cells):
                eps += "<li class=\"pending\">Needs review</li>"
            srcs = {}
            for c in cells:
                srcs.setdefault((c["source_url"], c["source_label"]), (c["fetched_at_local"] or "")[:10])
            src = "<br>".join(f"<a href=\"{_e(u)}\">{_e(l)}</a> · fetched {_e(d)}" for (u, l), d in srcs.items())
            out.append(f"<div class=\"ev\"><ul class=\"eps\">{eps}</ul>{ev}<p class=\"src\">{src}</p></div>")
        out.append("</section>")
    out.append("</main>")
    out.append(f"<footer>Prepared with Owin. {_e(pack['company'])} is a demo company. "
               f"Reference <span class=\"mono\">{_e(share['share_id'][:8])}</span></footer>")
    out.append("</body></html>")
    return "\n".join(out) + "\n"
