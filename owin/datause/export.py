"""Answer pack exports: CSV, print-ready HTML (light print tokens, A4) and a read-only share JSON.

The buyer-facing exports (HTML, share JSON) carry the answers, the per-endpoint vendor sentences, sources
and as-of times. The catch, the actions and "Fix" never appear in them (docs/design/brief.md).
"""
from __future__ import annotations

import csv
import html
import io

from ..textnorm import sha256

CSV_COLUMNS = ["question_number", "question", "stated_answer", "status", "endpoint", "feature", "provider", "vendor_value",
               "endpoint_verdict", "quote", "source_url", "fetched_at", "as_of", "stale"]


def to_csv(pack: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for a in pack["answers"]:
        for c in a["cells"]:
            w.writerow([a["number"], a["question"], a["stated"].get("text", ""), a["badge"], c["endpoint"], c["feature"],
                        c["provider"], c["value_label"], c["verdict"], c["quote"], c["source_url"], c["fetched_at"] or "",
                        a["as_of"] or "", "yes" if c.get("stale") else ""])
    return buf.getvalue()


def to_share(pack: dict) -> dict:
    """Read-only buyer view for the live link. No catch, no actions, no fix, no internal reasons."""
    answers = []
    for a in pack["answers"]:
        answers.append({
            "number": a["number"], "question": a["question"], "answer": a["stated"].get("text", ""),
            "status": a["badge"], "status_label": a["badge_label"], "as_of": a["as_of"], "as_of_local": a["as_of_local"],
            "changes": [{"text": a["answer"]}] if a["badge"] == "stale" else [],
            "endpoints": [{"endpoint": c["endpoint"], "provider": c["provider"], "vendor_says": c["value_label"],
                           "quote": c["quote"], "quote_display": c.get("quote_display") or c["quote"],
                           "source_url": c["source_url"], "source_label": c["source_label"],
                           "fetched_at": c["fetched_at"], "fetched_at_local": c["fetched_at_local"]} for c in a["cells"]],
        })
    body = {"type": "owin.answer_pack.share", "version": 1, "readonly": True, "company": pack["company"],
            "label": pack["label"], "pack_id": pack["pack_id"], "as_of": pack["as_of"], "as_of_local": pack["as_of_local"],
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
.badge { font-size: 13px; font-weight: 600; white-space: nowrap; display: inline-flex; gap: 6px; align-items: center; }
.badge.not_true { background: var(--act); color: var(--ink); padding: 1px 6px; border-radius: 3px; }
.badge.stale { border: 1px solid var(--ink); padding: 0 6px; border-radius: 3px; }
.badge.held_unspecified { color: var(--muted); }
.body { margin-left: 44px; }
section.q.not_true .body { border: 1px solid var(--ink); border-radius: 4px; padding: 12px; }
section.q.stale .body { border-left: 2px solid var(--ink); padding-left: 12px; }
.answer { margin: 8px 0; }
.change { margin: 6px 0; font-size: 13.5px; }
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

_ICON = {"still_true": '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M2.5 7.5l3 3 6-7" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
         "not_true": '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M7 1.8l5.6 10H1.4z M7 5.5v3 M7 10v.6" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>',
         "held_unspecified": '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="5.3" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M4.5 7h5" stroke="currentColor" stroke-width="1.4"/></svg>',
         "stale": '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M11.5 6.5A4.5 4.5 0 1 0 10 10.2 M11.5 2.8v3.7H7.8" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>'}


def _e(s) -> str:
    return html.escape("" if s is None else str(s))


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
           f"pack <span class=\"mono\">{_e(pack['pack_id'])}</span></p>",
           f"<p class=\"label\">{_e(pack['label'])}</p>", "</header>"]
    by_num = {a["number"]: a for a in share["answers"]}
    for num in sorted(by_num):
        a = by_num[num]
        out.append(f"<section class=\"q {a['status']}\"><div class=\"qhead\"><span class=\"num\">{_e(num)}</span>"
                   f"<h2>{_e(a['question'])}</h2><span class=\"badge {a['status']}\">{_ICON[a['status']]}{_e(a['status_label'])}</span></div>")
        out.append("<div class=\"body\">")
        out.append(f"<p class=\"answer\">{_e(a['answer'])}</p>")
        for ch in a["changes"]:
            out.append(f"<p class=\"change\">{_e(ch['text'])}</p>")
        out.append("<table><thead><tr><th>Endpoint</th><th>Vendor page says</th><th>Vendor sentence</th></tr></thead><tbody>")
        for c in a["endpoints"]:
            quote = f"<blockquote>“{_e(c['quote_display'])}”</blockquote>" if c["quote"] else "<span class=\"src\">The vendor's page does not say.</span>"
            src = (f"<div class=\"src\"><a href=\"{_e(c['source_url'])}\">{_e(c['source_label'])} ↗</a> · fetched "
                   f"{_e(c['fetched_at_local'])}</div>")
            out.append(f"<tr><td class=\"ep\">{_e(c['endpoint'])}</td><td>{_e(c['vendor_says'])}</td><td>{quote}{src}</td></tr>")
        out.append("</tbody></table></div></section>")
    out.append(f"<footer>Every sentence above is quoted verbatim from the vendor's own page, with its link and fetch time. "
               f"Statuses are computed by code from structured fields, never from model prose. Read-only share id "
               f"<span class=\"mono\">{_e(share['share_id'])}</span>.</footer>")
    out.append("</main></body></html>")
    return "\n".join(out) + "\n"
