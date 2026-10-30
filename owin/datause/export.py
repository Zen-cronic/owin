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
@page { size: A4; margin: 16mm 14mm; }
:root { --bg:#FFFFFF; --surface:#F4F3EE; --ink:#111111; --muted:#5E605C; --line:#D9D8D2; --edge:#8A8C88; --act:#FFD21F; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 400 14.5px/1.5 Archivo, "Helvetica Neue", Arial, sans-serif; }
main { max-width: 760px; margin: 0 auto; padding: 28px 16px; }
.mono, .num, code { font-family: "IBM Plex Mono", ui-monospace, Menlo, monospace; }
header { border-bottom: 1px solid var(--line); padding-bottom: 16px; margin-bottom: 12px; }
h1 { font: 600 28px/1.22 Archivo, "Helvetica Neue", Arial, sans-serif; margin: 0 0 4px; }
.meta { color: var(--muted); font-size: 13px; margin: 0; }
.label { color: var(--muted); font-size: 12.5px; margin-top: 8px; }
section.q { border-top: 1px solid var(--line); padding: 16px 0; break-inside: avoid; }
.qhead { display: grid; grid-template-columns: 32px 1fr auto; gap: 0 12px; align-items: baseline; }
.num { color: var(--muted); font-size: 14px; }
h2 { font: 600 17px/1.35 Archivo, "Helvetica Neue", Arial, sans-serif; margin: 0; }
.status { color: var(--muted); font-size: 12.5px; white-space: nowrap; }
.body { margin-left: 44px; }
.answer { margin: 8px 0; font-size: 15px; }
.note, .change { margin: 4px 0 6px; font-size: 13px; color: var(--muted); }
.kv { margin: 0; font-size: 13px; border-left: 2px solid var(--edge); padding-left: 8px; }
.kv div { display: grid; grid-template-columns: minmax(90px, 40%) 1fr; gap: 0 8px; }
.kv dt { color: var(--muted); font-weight: 400; }
.kv dd { margin: 0; }
.kv .hit dd { font-weight: 600; }
.kv .hit dt::after { content: " ◂"; color: var(--muted); }
table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }
th, td { text-align: left; vertical-align: top; padding: 6px 8px 6px 0; border-top: 1px solid var(--line); }
th { color: var(--muted); font-weight: 500; font-size: 12.5px; }
td.ep { white-space: nowrap; font-family: "IBM Plex Mono", ui-monospace, Menlo, monospace; }
blockquote { margin: 0; padding-left: 8px; border-left: 2px solid var(--edge); font-size: 14px; }
.src { color: var(--muted); font-size: 12.5px; white-space: nowrap; }
.src a { color: var(--muted); text-decoration: none; }
footer { border-top: 1px solid var(--line); margin-top: 16px; padding-top: 12px; color: var(--muted); font-size: 12.5px; }
@media print { main { padding: 0; } a { color: inherit; } }
"""

def _e(s) -> str:
    return html.escape("" if s is None else str(s))


def _evidence_html(c: dict) -> str:
    """The vendor's evidence as the buyer should see it: a sentence as a quote, a table row as key/value rows with
    the answering cell marked, a changed list entry as its cells. Never a flattened "a · b · c" row."""
    ev = c.get("evidence")
    if c.get("list_evidence"):
        parts = []
        for e in c["list_evidence"]:
            rows = "".join(f"<div class=\"{'hit' if r['match'] else ''}\"><dt>{_e(r['key'])}</dt><dd>{_e(r['value'])}"
                           + (f" <span class=\"src\">(was: {_e(r['was'])})</span>" if r.get("was") else "") + "</dd></div>"
                           for r in e["rows"])
            parts.append(f"<dl class=\"kv\"><div><dt>Entry</dt><dd>{_e(e['entity'])} ({_e(e['change'])})</dd></div>{rows}</dl>")
        return "".join(parts)
    if not c["quote"]:
        return ""
    if ev and ev["kind"] == "table_row":
        rows = "".join(f"<div class=\"{'hit' if r['match'] else ''}\"><dt>{_e(r['key'] or '')}</dt><dd>{_e(r['value'])}</dd></div>"
                       for r in ev["rows"] if r["value"])
        return f"<dl class=\"kv\">{rows}</dl>"
    text = ev["text"] if ev and ev["kind"] == "list_entry" else c["quote"].strip()
    return f"<blockquote>“{_e(text)}”</blockquote>"


def to_html(pack: dict) -> str:
    """Print-ready buyer document (light print variant). Open in a browser and print to PDF."""
    share = to_share(pack)
    out = ["<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
           f"<title>{_e(pack['company'])}: security review, AI and data</title>",
           "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
           "<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap\">",
           f"<style>{_CSS}</style></head><body><main>",
           "<header>", f"<h1>Security review: AI and data</h1>",
           f"<p class=\"meta\">{_e(pack['company'])} · answers as of <span class=\"mono\">{_e(pack['as_of_local'])}</span> · "
           f"reference <span class=\"mono\">{_e(pack['pack_id'])}</span></p>",
           f"<p class=\"label\">{_e(share['label'])}</p>", "</header>"]
    by_num = {a["number"]: a for a in share["answers"]}
    for num in sorted(by_num):
        a = by_num[num]
        out.append(f"<section class=\"q\"><div class=\"qhead\"><span class=\"num\">{_e(num)}</span>"
                   f"<h2>{_e(a['question'])}</h2><span class=\"status\">{_e(a['buyer_status'])}</span></div>")
        out.append("<div class=\"body\">")
        out.append(f"<p class=\"answer\">{_e(a['answer'])}</p>")
        if a.get("note"):
            out.append(f"<p class=\"note\">{_e(a['note'])}</p>")
        for ch in a["changes"]:
            out.append(f"<p class=\"change\">{_e(ch['text'])}</p>")
        out.append("<table><thead><tr><th>Endpoint</th><th>Vendor page says</th><th>On the vendor's page</th></tr></thead><tbody>")
        for c in a["endpoints"]:
            ev = _evidence_html(c)
            if not ev:
                ev = ("<span class=\"src\">Pending the company's review.</span>" if c.get("pending_confirmation") else
                      "<span class=\"src\">The page does not state this.</span>" if c["vendor_says"].startswith("Page does not say") else
                      "<span class=\"src\">No further third party is named on this page.</span>" if a["number"] == "05" else
                      "<span class=\"src\">See the vendor's page.</span>")
            src = (f"<div class=\"src\"><a href=\"{_e(c['source_url'])}\">{_e(c['source_label'])}</a> · fetched "
                   f"{_e(c['fetched_at_local'])}</div>")
            out.append(f"<tr><td class=\"ep\">{_e(c['endpoint'])}</td><td>{_e(c['vendor_says'])}</td><td>{ev}{src}</td></tr>")
        out.append("</tbody></table></div></section>")
    out.append(f"<footer>Every quotation and table row above is taken verbatim from the vendor's own page, with its link and the "
               f"time it was fetched. Prepared with Owin. Read-only share id <span class=\"mono\">{_e(share['share_id'])}</span>.</footer>")
    out.append("</main></body></html>")
    return "\n".join(out) + "\n"
