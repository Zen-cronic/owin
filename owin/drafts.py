"""Drafts, filled from structured fields with verbatim clause quotes. A person reviews and sends every one.

The templates are deterministic, so a judge can diff two runs. No model writes
text that reaches a customer.
"""
from __future__ import annotations

from datetime import date

from .textnorm import squash, strip_markdown


def _q(s: str) -> str:
    return squash(strip_markdown(s or ""))


def _change_lines(ev: dict) -> list[str]:
    out = []
    for m in ev["changes"]["material"]:
        if m["kind"] == "added":
            a = m.get("after") or {}
            out.append(f"- New sub-processor: {m['entity']} ({a.get('purpose') or 'purpose not stated'}; "
                       f"location: {a.get('locations') or 'not stated'})")
        else:
            out.append(f"- New processing location for {m['entity']}: {', '.join(m.get('new_locations', []))}")
    return out


def customer_notice(ev: dict, company: dict, customer: dict) -> dict:
    own = company["own_dpa"]
    v = ev["vendor_display"]
    yn = ev["your_notice"] or {}
    earliest = (ev.get("clock") or {}).get("vendor_deadline_date")
    body = "\n".join([
        f"Hello {customer['name']} team,",
        "",
        f"This is notice of a change to the sub-processors that {company['name']} uses to process your personal data.",
        f"{v} (used for: {next(x['purpose'] for x in company['vendors'] if x['vendor'] == ev['vendor'])}) "
        f"updated its sub-processor list (its page says \"Last updated {ev['evidence']['after']['last_updated']}\"):",
        "",
        *_change_lines(ev),
        "",
        "Our DPA with you says:",
        f"> {_q(own['promise_quote'])}",
        "",
        (f"The earliest these changes can apply to your data is {earliest}." if earliest else
         "The vendor has not given a date for these changes."),
        f"If you object, reply to {company['owner']['email']} with your reasons and we will work with you in good faith.",
        f"Our current sub-processor list: {company['public_subprocessor_page']}",
        "",
        "Best,",
        f"{company['owner']['name']}, {company['owner']['role']}, {company['name']}",
    ])
    return {"kind": "customer_notice", "to": customer["contact"], "customer_id": customer["id"],
            "subject": f"{company['name']}: sub-processor change notice ({v})", "body": body,
            "send_by": yn.get("due_date"), "late": yn.get("late"), "status": "draft"}


def subprocessor_page(ev: dict, company: dict, today: date) -> dict:
    rows = [f"| {x['display']} | {x['purpose']} | {x['location']} | {', '.join(x['data_categories'])} |" for x in company["vendors"]]
    downstream = [f"| {m['entity']} | {(m.get('after') or {}).get('purpose') or '—'} | "
                  f"{(m.get('after') or {}).get('locations') or '—'} | via {ev['vendor_display']} |"
                  for m in ev["changes"]["material"] if m["kind"] == "added"]
    locs = [f"- {m['entity']} (via {ev['vendor_display']}) now also processes in: {', '.join(m['new_locations'])}"
            for m in ev["changes"]["material"] if m.get("new_locations")]
    md = "\n".join([
        f"# {company['name']} sub-processors", "",
        f"Last updated: {today.strftime('%B %-d, %Y')}", "",
        "| Sub-processor | Purpose | Location | Data |", "|---|---|---|---|", *rows, "",
        f"## Sub-processors of our sub-processors (changes since the last update)", "",
        "| Entity | Purpose | Location | Relationship |", "|---|---|---|---|", *(downstream or ["| — | — | — | — |"]), "",
        *(locs and ["## New processing locations", "", *locs, ""] or []),
        "## Change log", "",
        f"- {today.isoformat()}: {ev['vendor_display']} updated its sub-processor list "
        f"({ev['evidence']['after']['url']}). Customers notified: {len(ev['affected_customers'])}.",
    ])
    return {"kind": "subprocessor_page", "markdown": md, "status": "draft"}


def objection(ev: dict, company: dict, contact: str) -> dict:
    vt = ev["vendor_terms"]
    cl = ev.get("clock") or {}
    body = "\n".join([
        f"To the {ev['vendor_display']} privacy team,", "",
        f"{company['name']} objects to the following sub-processor change, posted on your sub-processor list "
        f"(\"Last updated {ev['evidence']['after']['last_updated']}\"):", "",
        *_change_lines(ev), "",
        "We are writing under your Data Processing Addendum, which says:",
        f"> {_q(vt.get('quote', ''))}", "",
        f"Our reasons: [state the data-protection grounds; the clause requires reasonable grounds].",
        "Please confirm receipt and propose an alternative or remedy.", "",
        "Best,", f"{company['owner']['name']}, {company['owner']['role']}, {company['name']}",
    ])
    return {"kind": "objection", "to": contact, "subject": f"Objection to new sub-processor ({company['name']})",
            "body": body, "send_by": cl.get("vendor_deadline_local"), "status": "draft",
            "note": "A remedy is often exit only. A person decides and sends. This is not legal advice."}


def build_all(ev: dict, company: dict, today: date) -> dict:
    if ev["watch_state"] not in ("countdown", "window_closed", "exit_only"):
        return {}
    vcfg = next(x for x in company["vendors"] if x["vendor"] == ev["vendor"])
    customers = {c["id"]: c for c in company["customers"]}
    out = {"customer_notices": [customer_notice(ev, company, customers[a["id"]]) for a in ev["affected_customers"]],
           "subprocessor_page": subprocessor_page(ev, company, today)}
    if ev["watch_state"] == "countdown":
        out["objection"] = objection(ev, company, vcfg.get("privacy_contact", ""))
    return out
