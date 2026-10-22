"""Deterministic decision layer. Code, not the model, decides.

It reads only structured fields: WindowTerms from the registry, the entity diff and
the company profile. No model prose is read here. Any rule it cannot resolve falls
to the safe state (held, or the earlier deadline), and every assumption is listed.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .entities import EntityChange, Snapshot, diff

WATCH_STATES = ("watching", "no_change", "changed", "affects_you", "countdown", "window_closed",
                "exit_only", "held", "not_watchable")
WORKFLOW_STATES = ("pending", "drafted", "accepted", "objected", "dismissed")
DECISIONS = ("accepted", "objected", "dismissed")
VERSION = "owin-decide/1"


def parse_page_date(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b. %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            pass
    return None


def add_days(start: date, n: int, unit: str) -> date:
    if unit == "business":
        d, left = start, n
        while left:
            d += timedelta(days=1)
            if d.weekday() < 5:
                left -= 1
        return d
    return start + timedelta(days=n)


def end_of_day_earliest(d: date, tz_names: list[str]) -> datetime:
    """23:59:59 on day d in each zone; the earliest instant wins (the earlier-deadline rule)."""
    return min(datetime.combine(d, time(23, 59, 59), ZoneInfo(z)) for z in tz_names).astimezone(timezone.utc)


def local_label(dt: datetime, tz: str) -> str:
    loc = dt.astimezone(ZoneInfo(tz))
    return loc.strftime("%Y-%m-%d %H:%M ") + (loc.tzname() or tz)


_PLACE = re.compile(r"^[A-Z][A-Za-z.'\- ]{1,40}$")


def _is_place(v: str) -> bool:
    return bool(_PLACE.match(v)) and len(v.split()) <= 4 and "processing" not in v.lower()


@dataclass
class Classified:
    material: list[dict] = field(default_factory=list)
    other: list[dict] = field(default_factory=list)


def classify(changes: list[EntityChange], products_used: list[str]) -> Classified:
    """Material = a new entity, or a new processing location, on a service the company uses."""
    out = Classified()
    used = {p.lower() for p in products_used}

    def uses(cells: dict | None) -> bool:
        svc = (cells or {}).get("services", "")
        return not svc or not used or any(u in svc.lower() for u in used)

    for c in changes:
        row = {"kind": c.kind, "entity": c.name, "key": c.key, "before": c.before, "after": c.after,
               "changed_fields": c.changed_fields, "added_values": c.added_values}
        if c.kind == "added" and uses(c.after):
            row["why"] = "new sub-processor"
            out.material.append(row)
        elif c.kind == "changed" and uses(c.after) and [v for v in c.added_values.get("locations", []) if _is_place(v)]:
            row["new_locations"] = [v for v in c.added_values["locations"] if _is_place(v)]
            row["why"] = "new processing location"
            out.material.append(row)
        else:
            row["why"] = {"removed": "removed (page update only)", "added": "new entity on a service you do not use"}.get(
                c.kind, "wording or scope change (page update only)")
            out.other.append(row)
    return out


def clock(terms: dict, vendor_cfg: dict, after: Snapshot, notice_received: date | None) -> dict:
    """Pick the clock start. Every candidate is listed and the earliest wins."""
    cands = []
    page = parse_page_date(after.last_updated)
    seen = datetime.fromisoformat(after.retrieved.replace("Z", "+00:00")).date()
    if terms.get("clock_start") == "page_update":
        if page:
            cands.append((page, f"page 'Last updated {after.last_updated}' (the clause runs from the page update)"))
    else:
        if notice_received:
            cands.append((notice_received, "notice received by email"))
        if page:
            cands.append((page, f"vendor page says 'Last updated {after.last_updated}': notice may have gone out that day"))
    cands.append((seen, "first seen by Owin in a snapshot"))
    start, basis = min(cands, key=lambda c: c[0])
    assumptions = [f"clock starts {start.isoformat()}: {basis} (earliest of {len(cands)} candidate(s))"]
    if not vendor_cfg.get("subscribed_to_notices"):
        assumptions.append("not subscribed to this vendor's notices: the clock may have started without an email reaching you")
    return {"start_date": start.isoformat(), "basis": basis,
            "candidates": [{"date": d.isoformat(), "basis": b} for d, b in cands], "assumptions": assumptions}


def evaluate(company: dict, vendor_cfg: dict, terms_entry: dict, before: Snapshot, after: Snapshot,
             as_of: datetime, *, promise_days: int | None = None, notice_received: date | None = None,
             vendor_tz: str = "UTC") -> dict:
    terms = terms_entry["terms"]
    tz = company["timezone"]
    own = company["own_dpa"]
    promise = own["notice_days"] if promise_days is None else promise_days
    as_of = as_of.astimezone(timezone.utc)
    ev = {
        "vendor": vendor_cfg["vendor"], "vendor_display": vendor_cfg.get("display", vendor_cfg["vendor"]),
        "as_of": as_of.isoformat(), "as_of_local": local_label(as_of, tz),
        "watch_state": "watching", "workflow_state": "pending",
        "headline": None, "flags": [], "actions": [], "assumptions": [],
        "changes": {"material": [], "other": []},
        "vendor_terms": {**terms, "source_url": terms_entry.get("source_url"), "model": terms_entry.get("model"),
                         "quote_sha256": terms_entry.get("quote_sha256"), "runs_agreeing": terms_entry.get("runs_agreeing")},
        "clock": None, "your_notice": None, "affected_customers": [],
        "evidence": {s: {"url": x.source_url, "retrieved": x.retrieved, "last_updated": x.last_updated,
                         "source_kind": x.source_kind, "content_sha256": x.content_sha256, "entities": len(x.entities)}
                     for s, x in (("before", before), ("after", after))},
    }
    if not after.entities:
        ev["watch_state"] = "not_watchable"
        ev["actions"] = ["The vendor's list did not come back as a table (JS widget or gated page). Watch its DPA or update feed instead."]
        return ev
    changes = diff(before, after)
    if not changes:
        ev["watch_state"] = "no_change"
        ev["actions"] = ["Nothing to do. Entity table unchanged between the two snapshots."]
        return ev
    cl = classify(changes, vendor_cfg.get("products_used", []))
    ev["changes"] = {"material": cl.material, "other": cl.other}
    if not cl.material:
        ev["watch_state"] = "changed"
        ev["actions"] = ["Page changed, but nothing new touches your data (removals or wording only). Optionally refresh your sub-processor page."]
        return ev

    flowdown = own.get("flowdown") == "lists_vendor_subprocessors"
    feats = set(vendor_cfg.get("features", []))
    affected = [c for c in company["customers"] if feats & set(c.get("features", []))] if flowdown else []
    ev["affected_customers"] = [{"id": c["id"], "name": c["name"], "contact": c["contact"], "region": c.get("region")}
                                for c in affected]
    ev["watch_state"] = "affects_you"
    if not flowdown:
        ev["flags"].append({"code": "vendor_only_flowdown", "message": "Your DPA lists vendors only, so this change may not need a customer notice. Check before dismissing."})

    if terms.get("status") != "ok":
        ev["watch_state"] = "held"
        ev["flags"].append({"code": "thin_evidence", "message": "No verbatim objection clause from this vendor's DPA: "
                            + "; ".join(terms.get("hold_reasons") or ["unverified"]) + ". No deadline is shown."})
        ev["actions"] = [f"Read {ev['vendor_display']}'s DPA and confirm the objection terms before deciding.",
                         f"{len(affected)} of your customers may need notice under your own DPA."]
        return ev

    c = clock(terms, vendor_cfg, after, notice_received)
    ev["assumptions"] += c["assumptions"]
    start = date.fromisoformat(c["start_date"])
    if terms["window_type"] == "exit_only":
        ev["watch_state"] = "exit_only"
        ev["clock"] = {**c, "vendor_deadline_date": None, "days_left": None, "closed": None}
        ev["your_notice"] = {"promise_days": promise, "due_date": start.isoformat(), "late": start < as_of.astimezone(ZoneInfo(tz)).date(),
                             "inversion": True, "slack_days": None,
                             "why": "the vendor sets no objection deadline, so its engagement date is unknown: notify now"}
        ev["flags"].append({"code": "exit_only", "message": "This vendor offers no objection window, only exit (terminate, stop using, move Region)."})
    else:
        n, unit = terms["window_days"], terms["unit"]
        if unit == "unspecified":
            ev["assumptions"].append("day unit unspecified: counted calendar days (earlier than business days)")
        if unit == "business":
            ev["assumptions"].append("business days skip Saturdays and Sundays; public holidays are not modelled")
        due = add_days(start, n, "business" if unit == "business" else "calendar")
        zones = [tz, vendor_tz]
        at = end_of_day_earliest(due, zones)
        ev["assumptions"].append(f"deadline is 23:59:59 on {due.isoformat()} in the earlier of {', '.join(zones)}")
        today = as_of.astimezone(ZoneInfo(tz)).date()
        closed = as_of > at
        days_left = 0 if closed else (at.astimezone(ZoneInfo(tz)).date() - today).days
        ev["clock"] = {**c, "window_days": n, "unit": unit, "vendor_deadline_date": due.isoformat(),
                       "vendor_deadline_at": at.isoformat(), "vendor_deadline_local": local_label(at, tz),
                       "days_left": days_left, "closed": closed}
        # Your own promise: notice to your customers before the new sub-processor can start,
        # assumed no earlier than the end of the vendor's objection window.
        notice_due = due - timedelta(days=promise)
        ev["your_notice"] = {"promise_days": promise, "due_date": notice_due.isoformat(),
                             "days_left": (notice_due - today).days, "late": notice_due < today,
                             "slack_days": n - promise, "inversion": promise > n,
                             "why": f"your DPA promises {promise} days' notice; {ev['vendor_display']} may engage after its {n}-day window ends {due.isoformat()}"}
        ev["assumptions"].append("assumes the vendor does not start the new sub-processor before its objection window ends")
        ev["watch_state"] = "window_closed" if closed else "countdown"
        if terms.get("deemed_consent_if_silent"):
            ev["flags"].append({"code": "deemed_consent", "message": f"Silence counts as consent after {due.isoformat()}."})
    yn = ev["your_notice"]
    if yn["inversion"]:
        ev["flags"].append({"code": "notice_inversion", "message": f"You promised your customers {promise} days' notice, more than "
                            f"{ev['vendor_display']} gives you ({terms.get('window_days') or 'no window'}). You cannot pass the change on in time."})
    if yn["late"]:
        ev["flags"].append({"code": "customer_notice_late", "message": f"Your {promise}-day customer notice was due {yn['due_date']}."})
    if not vendor_cfg.get("subscribed_to_notices"):
        ev["flags"].append({"code": "unsubscribed", "message": f"You are not subscribed to {ev['vendor_display']}'s sub-processor notices."})
    new_locs = sorted({l for m in cl.material for l in m.get("new_locations", [])})
    if new_locs:
        qc = [c["name"] for c in affected if (c.get("region") or "").lower() in ("quebec", "québec")]
        msg = "New processing locations: " + ", ".join(new_locs) + "."
        if qc:
            msg += f" Quebec customers ({', '.join(qc)}): consider a Law 25 s.17 transfer assessment."
        ev["flags"].append({"code": "new_location", "message": msg})

    k = len(affected)
    if ev["watch_state"] == "countdown":
        ev["headline"] = {"days_to_object": ev["clock"]["days_left"], "customers_to_warn": k,
                          "text": f"{ev['clock']['days_left']} days to object · {k} customers to warn"}
    elif ev["watch_state"] == "window_closed":
        ev["headline"] = {"days_to_object": 0, "customers_to_warn": k,
                          "text": f"Objection window closed {ev['clock']['vendor_deadline_date']} · {k} customers to warn"}
    else:
        ev["headline"] = {"days_to_object": None, "customers_to_warn": k, "text": f"No objection window · {k} customers to warn"}
    ev["actions"] = [
        f"Accept and notify (default): send the drafted notice to {k} customers"
        + (f" (due {yn['due_date']}, {'LATE' if yn['late'] else str(yn.get('days_left')) + ' days left'})" if yn.get("due_date") else ""),
        "Publish the updated sub-processor page and file the decision record.",
    ]
    if ev["watch_state"] == "countdown":
        ev["actions"].append(f"Or object (rare): send the drafted objection before {ev['clock']['vendor_deadline_local']}.")
    return ev


def decision_record(ev: dict, decision: str, who: dict, at: datetime, note: str = "", your_promise_quote: str = "") -> dict:
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}")
    if ev["watch_state"] in ("no_change", "not_watchable", "watching"):
        raise ValueError(f"nothing to decide in state {ev['watch_state']}")
    body = {
        "type": "owin.decision_record", "version": VERSION,
        "decided_at": at.astimezone(timezone.utc).isoformat(), "decided_by": who, "decision": decision, "note": note,
        "vendor": ev["vendor"], "watch_state_at_decision": ev["watch_state"],
        "change": [{"entity": m["entity"], "kind": m["kind"], "why": m["why"], "new_locations": m.get("new_locations", [])}
                   for m in ev["changes"]["material"]],
        "vendor_clause": {"quote": ev["vendor_terms"].get("quote"), "quote_sha256": ev["vendor_terms"].get("quote_sha256"),
                          "source_url": ev["vendor_terms"].get("source_url"), "window_days": ev["vendor_terms"].get("window_days"),
                          "window_type": ev["vendor_terms"].get("window_type")},
        "your_clause": {"quote": your_promise_quote,
                        "quote_sha256": hashlib.sha256(your_promise_quote.encode()).hexdigest() if your_promise_quote else None},
        "deadlines": {"vendor_objection": (ev.get("clock") or {}).get("vendor_deadline_date"),
                      "customer_notice": (ev.get("your_notice") or {}).get("due_date")},
        "customers_notified": [c["id"] for c in ev["affected_customers"]] if decision == "accepted" else [],
        "evidence": ev["evidence"], "assumptions": ev["assumptions"], "flags": [f["code"] for f in ev["flags"]],
    }
    body["record_id"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]
    return body
