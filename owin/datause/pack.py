"""The security-review answer pack (A3): the AI-and-data section of a buyer questionnaire, per endpoint.

Inputs: a stack manifest (endpoint -> feature id from data/datause/catalog.json), the startup's own
settings, and its stated answers (each a display `text` plus a structured `claim`).
Evidence: data/datause/registry.json (structured fields from recorded Nemotron runs) and
data/datause/observations.json (dated captures: hashes, quote presence, list snapshots).

The trust split: code computes every verdict and badge from enums, integers and booleans only
(`used_for_training`, `retention_days`, `zdr`, `third_party_access`, the `verbatim` flags, the stated
`claim`, the settings, and observation hashes/entity diffs). Quotes, retention conditions, region text and
the stated `text` are copied to the output as evidence and never read by a rule.

Badges (per question, most severe wins):
  not_true          an endpoint's vendor field contradicts the stated claim
  stale             a page the answer relies on changed after the answer was written
                    (sub-processor list entity diff since `stated_at`, or the quote is gone from the latest
                    capture and the extraction on that capture does not reproduce the value)
  held_unspecified  an endpoint's vendor page does not say (or a needed setting is missing); never a guess
  still_true        every endpoint supports the claim
"""
from __future__ import annotations

import copy
import json
from datetime import date, datetime, timezone
from pathlib import Path

from ..decide import local_label, parse_page_date
from ..entities import Snapshot, diff
from ..textnorm import sha256
from . import observations as obsmod, registry

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "fixtures" / "demo" / "stack.json"
TZ = "America/Toronto"

QUESTIONS = [
    ("Q01", "01", "Is our data used to train AI models?", "used_for_training"),
    ("Q02", "02", "How long do AI providers retain our data?", "retention_days"),
    ("Q03", "03", "Do you have zero data retention with your AI providers?", "zdr"),
    ("Q04", "04", "Where is our data processed?", "region"),
    ("Q05", "05", "Which AI providers see our data?", "third_party_access"),
]
QUOTE_FIELD = {"used_for_training": "training_quote", "retention_days": "retention_quote", "zdr": "zdr_quote",
               "region": "region_quote", "third_party_access": "third_party_quote"}
SEVERITY = ["not_true", "stale", "held_unspecified", "still_true"]
BADGE_LABEL = {"not_true": "Not true", "stale": "Stale", "held_unspecified": "Held · unspecified", "still_true": "Still true"}
NULL = {"retention_days": None, "used_for_training": "unspecified", "zdr": "unspecified", "region": "unspecified",
        "third_party_access": "unspecified"}


class PackError(ValueError):
    pass


def load_demo() -> dict:
    return json.loads(DEMO.read_text())


def set_feature(manifest: dict, path: str, feature: str) -> dict:
    """The "change one input" path: point one endpoint at another feature id."""
    m = copy.deepcopy(manifest)
    hit = [e for e in m["endpoints"] if e["path"] == path]
    if not hit:
        raise PackError(f"no endpoint {path!r} in the stack")
    hit[0]["feature"] = feature
    return m


def _utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def _local(s: str | None) -> str | None:
    return local_label(_utc(s), TZ) if s else None


# Evidence

def _value(entry: dict, f: str, reg: dict) -> tuple[object, dict, str | None]:
    """The field value a rule may use, the entry it came from, and an inherited-from feature id.

    A field counts only when the A1 gate marked its quote verbatim; anything else is the null value.
    """
    t = entry.get("terms") or {}
    v = t.get(f, NULL[f])
    ok = v not in (None, "unspecified") and bool((t.get("verbatim") or {}).get(f))
    if ok:
        return v, entry, None
    parent = (entry.get("inherits") or {}).get(f)
    if parent and parent in reg:
        pt = reg[parent].get("terms") or {}
        pv = pt.get(f, NULL[f])
        if pv not in (None, "unspecified") and bool((pt.get("verbatim") or {}).get(f)):
            return pv, reg[parent], parent
    return NULL[f], entry, None


def _latest(page_obs: list[dict]) -> dict | None:
    good = [o for o in page_obs if not o.get("held")]
    return good[-1] if good else None


def _basis(page_obs: list[dict], stated_at: date) -> dict | None:
    """The last trusted capture on or before the day the answer was written."""
    good = [o for o in page_obs if not o.get("held") and _utc(o["observed_at"]).date() <= stated_at]
    return good[-1] if good else None


def _quote_evidence(src: dict, f: str, page_obs: list[dict]) -> dict:
    """Which sentence to show, and whether it is still on the latest capture of the page."""
    t = src.get("terms") or {}
    quote = t.get(QUOTE_FIELD[f]) or ""
    latest = _latest(page_obs)
    out = {"quote": quote, "quote_from": src.get("capture_kind"), "stale": None}
    if not quote or latest is None or "quotes_present" not in latest:
        return out
    if obsmod.quote_id(quote) not in latest["quotes_present"]:
        return {**out, "presence": "unchecked"}  # never compared with that capture: no evidence of a change
    lc = src.get("live_check") or {}
    lq = (lc.get("quotes") or {}).get(f)
    pres = latest["quotes_present"].get(obsmod.quote_id(quote))
    if pres == "verbatim" or (pres and not (lc.get("values") and lc["values"].get(f) == t.get(f) and lq
                                            and latest["quotes_present"].get(obsmod.quote_id(lq)) == "verbatim")):
        out["presence"] = pres
        return out
    if lc.get("values") and lc["values"].get(f) == t.get(f) and lq and latest["quotes_present"].get(obsmod.quote_id(lq)):
        return {**out, "quote": lq, "quote_from": latest["source_kind"], "presence": latest["quotes_present"][obsmod.quote_id(lq)],
                "reanchored": f"the {src.get('capture_kind')} sentence renders differently in the {latest['source_kind']} "
                              "capture; the extraction on that capture gives the same value, so its sentence is shown"}
    out["stale"] = {"kind": "quote_gone", "page_seen": latest["observed_at"],
                    "text": f"The sentence this answer relied on is no longer on the page (checked {_local(latest['observed_at'])})."}
    return out


def _list_change(page: str, obs: dict, stated_at: date) -> dict | None:
    """Sub-processor list entity diff between the capture in effect when the answer was written and the latest."""
    po = (obs["pages"].get(page) or {}).get("observations", [])
    b, l = _basis(po, stated_at), _latest(po)
    if not b or not l or b is l or not b.get("snapshot") or not l.get("snapshot"):
        return None
    sb = Snapshot.from_dict(json.loads((ROOT / b["snapshot"]).read_text()))
    sl = Snapshot.from_dict(json.loads((ROOT / l["snapshot"]).read_text()))
    ch = diff(sb, sl)
    if not ch:
        return None
    added = [c.name for c in ch if c.kind == "added"]
    removed = [c.name for c in ch if c.kind == "removed"]
    changed = [c.name for c in ch if c.kind == "changed"]
    cf = next((c for c in ch if c.kind == "changed" and c.key == "cloudflare"), None) or next(
        (c for c in ch if c.kind in ("changed", "added")), None)
    return {"kind": "list_changed", "page": page, "before": {k: b.get(k) for k in ("observed_at", "last_updated", "url", "source_kind", "sha256")},
            "after": {k: l.get(k) for k in ("observed_at", "last_updated", "url", "source_kind", "sha256")},
            "added": added, "removed": removed, "changed": changed,
            "example": {"entity": cf.name, "kind": cf.kind, "fields": cf.changed_fields,
                        "after_cells": cf.after} if cf else None,
            "held_observations": [{k: o.get(k) for k in ("observed_at", "source_kind", "last_updated", "held")} for o in po if o.get("held")]}


def quote_display(q: str) -> str:
    """A markdown table row reads as its cells joined by ' · '. Display only; `quote` stays verbatim."""
    if q.count("|") < 2:
        return q
    cells = [c.strip().strip("`") for c in q.strip().strip("|").split("|")]
    return " · ".join(c for c in cells if c)


# Rules, one per question. Each returns (verdict, value_label, reason). Verdicts: holds | disclosed | contradicts | held.

def _rule_training(v, claim, ep, settings):
    want = claim.get("training")
    if want not in ("not_used", "used"):
        return "held", "No stated claim", "the stated answer has no structured training claim"
    label = {"no": "Not used", "opt_in": "Not used unless you opt in", "opt_out": "Used unless you opt out",
             "yes": "Used", "unspecified": "Page does not say"}[v]
    if v == "unspecified":
        return "held", label, "the vendor's page does not say"
    not_used = v in ("no", "opt_in")
    return ("holds" if not_used == (want == "not_used") else "contradicts"), label, None


def _rule_retention(v, claim, ep, settings, *, zdr=None):
    cap = claim.get("max_retention_days")
    if not isinstance(cap, int):
        return "held", "No stated claim", "the stated answer has no structured retention claim"
    zdr_on = zdr == "available" and settings.get("zdr_enabled", {}).get(ep["provider"]) is True
    if zdr_on:
        if v == 0:
            return "holds", "Not retained", None
        return "holds", "Not retained under ZDR" + (f" ({v} days without)" if isinstance(v, int) else ""), None
    if v is None:
        return "held", "No period stated", "the vendor's page states no retention period for this feature"
    label = "Not retained" if v == 0 else f"{v} days"
    return ("holds" if v <= cap else "contradicts"), label, None


def _rule_zdr(v, claim, ep, settings):
    if claim.get("zdr") is not True:
        return ("holds" if claim.get("zdr") is False else "held"), {"available": "ZDR available", "excluded": "Not covered by ZDR",
                "not_available": "No ZDR offered", "unspecified": "Page does not say"}[v], None
    if ep["path"] in (claim.get("exceptions") or []):
        return "disclosed", {"available": "ZDR available (listed as an exception)", "excluded": "Not covered by ZDR (disclosed exception)",
                             "not_available": "No ZDR offered (disclosed exception)", "unspecified": "Page does not say (disclosed exception)"}[v], None
    if v in ("excluded", "not_available"):
        return "contradicts", "Not covered by ZDR" if v == "excluded" else "No ZDR offered", None
    if v == "unspecified":
        return "held", "Page does not say", "the vendor's page does not say whether ZDR covers this feature"
    enabled = settings.get("zdr_enabled", {}).get(ep["provider"])
    if enabled is True:
        return "holds", "ZDR (your setting)", None
    if enabled is False:
        return "contradicts", "ZDR available, not enabled (your setting)", None
    return "held", "ZDR available", "confirm your ZDR agreement with this provider"


def _rule_region(v, claim, ep, settings):
    # Region on vendor pages is free text, so no rule reads it. Only the startup's own setting can answer.
    mine = settings.get("region", {}).get(ep["provider"])
    regions = claim.get("regions") or []
    if mine:
        return ("holds" if mine in regions else "contradicts"), f"{mine} (your setting)", None
    return "held", "Region stated on the page (see quote)" if v != "unspecified" else "Page does not say", \
        "the vendor's page does not state a default region; confirm your settings"


def _rule_third_party(v, claim, ep, settings):
    providers = claim.get("providers") or []
    name = ep["provider_display"]
    if ep["provider"] not in providers:
        return "contradicts", f"{name} (not in your answer)", None
    if v == "yes" and not claim.get("includes_subprocessors"):
        return "contradicts", f"{name} and its sub-processors", None
    return "holds", name + (" and its sub-processors" if v == "yes" else ""), None


RULES = {"used_for_training": _rule_training, "retention_days": _rule_retention, "zdr": _rule_zdr,
         "region": _rule_region, "third_party_access": _rule_third_party}


def _sentence(qid: str, badge: str, cells: list[dict], stated: dict, stale: list[dict], stated_at: str) -> str:
    n = len(cells)
    bad = [c["endpoint"] for c in cells if c["verdict"] == "contradicts"]
    held = [c["endpoint"] for c in cells if c["verdict"] == "held"]
    ok = n - len(bad) - len(held)
    if badge == "not_true":
        return f"You answer “{stated['text']}” That holds for {ok} of {n} endpoints, not for {', '.join(bad)}."
    if badge == "stale":
        s = stale[0]
        if s["kind"] == "list_changed":
            return (f"{s['provider_display']} updated its sub-processor list on {s['after']['last_updated']} "
                    f"(was {s['before']['last_updated']}), after this answer was written ({stated_at}). Review the change.")
        return f"A sentence this answer relies on changed on {s['provider_display']}'s page after it was written. Review the change."
    if badge == "held_unspecified" and not ok:
        return ("The vendor pages do not say for any of your endpoints, so Owin does not answer this question. "
                "Confirm your settings.")
    if badge == "held_unspecified":
        return (f"Holds for {ok} of {n} endpoints. The vendor's page does not say for {', '.join(held)}, so Owin does not answer "
                "for it. Confirm your settings.")
    return f"Holds on all {n} endpoints."


def build(manifest: dict | None = None, *, reg: dict | None = None, obs: dict | None = None) -> dict:
    manifest = manifest or load_demo()
    reg = reg if reg is not None else registry.load()
    obs = obs if obs is not None else obsmod.load()
    cat = registry.load_catalog()
    stated = manifest["stated"]
    try:
        stated_at = date.fromisoformat(stated["stated_at"])
    except (KeyError, ValueError) as e:
        raise PackError(f"stated.stated_at must be YYYY-MM-DD ({e})")
    settings = manifest.get("settings") or {}
    if not manifest.get("endpoints"):
        raise PackError("the stack has no endpoints")
    eps = []
    for e in manifest["endpoints"]:
        f = reg.get(e.get("feature"))
        if f is None:
            raise PackError(f"unknown feature id {e.get('feature')!r} for {e.get('path')}; known: {sorted(reg)}")
        eps.append({"path": e["path"], "feature": e["feature"], "provider": f["provider"],
                    "provider_display": cat["providers"][f["provider"]]["display"], "label": f["label"],
                    "short": cat["features"].get(e["feature"], {}).get("short", f["label"]),
                    "purpose": e.get("purpose", "")})

    # Q05 also relies on each provider's sub-processor list.
    list_changes = {}
    for p in sorted({e["provider"] for e in eps}):
        page = cat["providers"][p].get("subprocessor_page")
        ch = _list_change(page, obs, stated_at) if page else None
        if ch:
            list_changes[p] = {**ch, "provider": p, "provider_display": cat["providers"][p]["display"]}

    answers = []
    for qid, num, question, field in QUESTIONS:
        st = stated["answers"].get(qid) or {"text": "", "claim": {}}
        claim = st.get("claim") or {}
        cells, stale = [], []
        for ep in eps:
            entry = reg[ep["feature"]]
            v, src, inherited = _value(entry, field, reg)
            if field == "retention_days":
                zv, _, _ = _value(entry, "zdr", reg)
                verdict, label, reason = _rule_retention(v, claim, ep, settings, zdr=zv)
            else:
                verdict, label, reason = RULES[field](v, claim, ep, settings)
            page = src["page"]
            po = (obs["pages"].get(page) or {}).get("observations", [])
            latest = _latest(po)
            ev = _quote_evidence(src, field, po) if v not in (None, "unspecified") or field == "retention_days" else {"quote": "", "stale": None}
            cell = {"endpoint": ep["path"], "feature": ep["feature"], "feature_label": ep["label"], "feature_short": ep["short"],
                    "provider": ep["provider"],
                    "vendor_value": v, "value_label": label, "verdict": verdict, "reason": reason,
                    "quote": ev.get("quote") or "", "quote_display": quote_display(ev.get("quote") or ""),
                    "quote_presence": ev.get("presence"), "reanchored": ev.get("reanchored"),
                    "source_label": cat["pages"][page]["label"], "source_url": src["source_url"],
                    "fetched_at": latest["observed_at"] if latest else src.get("captured_at"),
                    "fetched_at_local": _local(latest["observed_at"]) if latest else None,
                    "fetched_via": latest["source_kind"] if latest else src.get("capture_kind"),
                    "inherited_from": inherited, "measured": src.get("measured"), "origin": src.get("origin")}
            if ev.get("stale"):
                stale.append({**ev["stale"], "endpoint": ep["path"], "provider_display": ep["provider_display"]})
                cell["stale"] = True
            if field == "third_party_access" and ep["provider"] in list_changes:
                stale.append({**list_changes[ep["provider"]], "endpoint": ep["path"]})
                cell["stale"] = True
                lc = list_changes[ep["provider"]]
                cell["list_source"] = {"label": cat["pages"][lc["page"]]["label"], "url": cat["pages"][lc["page"]]["url"],
                                       "last_updated": lc["after"]["last_updated"], "was": lc["before"]["last_updated"],
                                       "captured": lc["after"]["url"]}
            cells.append(cell)
        verdicts = {c["verdict"] for c in cells}
        if "contradicts" in verdicts:
            badge = "not_true"
        elif stale:
            badge = "stale"
        elif "held" in verdicts:
            badge = "held_unspecified"
        else:
            badge = "still_true"
        seen = [c["fetched_at"] for c in cells if c["fetched_at"]] + [s["after"]["observed_at"] for s in stale if s.get("after")]
        as_of = max(seen) if seen else None
        dedup_stale, keys = [], set()
        for s in stale:
            k = (s["kind"], s.get("page"), s["endpoint"])
            if k not in keys:
                keys.add(k)
                dedup_stale.append(s)
        answers.append({"id": qid, "number": num, "question": question, "field": field, "stated": st, "badge": badge,
                        "badge_label": BADGE_LABEL[badge], "answer": _sentence(qid, badge, cells, st, dedup_stale, stated["stated_at"]),
                        "as_of": as_of, "as_of_local": _local(as_of), "cells": cells, "stale_events": dedup_stale,
                        "endpoints_holding": sum(c["verdict"] in ("holds", "disclosed") for c in cells),
                        "endpoints": len(cells)})

    order = sorted(answers, key=lambda a: (SEVERITY.index(a["badge"]), a["number"]))
    counts = {b: sum(a["badge"] == b for a in answers) for b in SEVERITY}
    catch = _catch(answers, stated)
    pages = sorted({c["source_url"] for a in answers for c in a["cells"]} |
                   {cat["pages"][cat["providers"][e["provider"]]["subprocessor_page"]]["url"] for e in eps})
    last_checked = max((o["observed_at"] for p in obs["pages"].values() for o in p.get("observations", [])
                        if o.get("source_kind") in ("tavily", "urllib_fallback")), default=None)
    digest_in = json.dumps({"manifest": manifest, "reg": {e["feature"]: reg[e["feature"]] for e in eps},
                            "obs": obs.get("pages")}, sort_keys=True, default=str)
    return {
        "type": "owin.answer_pack", "version": 1, "pack_id": sha256(digest_in)[:16],
        "company": manifest.get("company"), "label": manifest.get("_label"),
        "stated_at": stated["stated_at"], "stated_source": stated.get("source"),
        "as_of": max((a["as_of"] for a in answers if a["as_of"]), default=None),
        "as_of_local": _local(max((a["as_of"] for a in answers if a["as_of"]), default=None)),
        "stack": {"endpoints": eps, "providers": sorted({e["provider"] for e in eps})},
        "counts": counts, "headline": _headline(counts, catch, answers, eps),
        "catch": catch, "answers": answers, "order": [a["id"] for a in order],
        "watch": {"pages": pages, "pages_watched": len(pages), "last_checked": last_checked,
                  "last_checked_local": _local(last_checked)},
        "settings": settings,
        "provenance": {"registry": "data/datause/registry.json", "observations": "data/datause/observations.json",
                       "rules": "owin/datause/pack.py (code only; quotes and stated text are never read by a rule)"},
    }


def _headline(counts: dict, catch: dict | None, answers: list[dict], eps: list[dict]) -> dict:
    if counts["not_true"]:
        kicker = f"{counts['not_true']} not true" + (f" · {counts['stale']} stale" if counts["stale"] else "")
    elif counts["stale"]:
        kicker = f"{counts['stale']} stale"
    else:
        kicker = None
    if catch:
        text = catch["sentence"]
    elif counts["stale"] or counts["held_unspecified"]:
        text = f"No answer is contradicted by your {len(eps)} endpoints; {counts['stale']} stale, {counts['held_unspecified']} held."
    else:
        text = f"All {len(answers)} answers hold for your {len(eps)} endpoints."
    return {"kicker": kicker, "text": text}


_CATCH_TEXT = {
    "zdr": "Your trust page says “zero data retention”, but {path} calls {label}, which is outside ZDR.",
    "used_for_training": "Your trust page says your data is not used for training, but {path} calls {label}, whose page says otherwise.",
    "retention_days": "Your trust page caps retention, but {path} calls {label}, which keeps data longer.",
    "region": "Your stated region does not match your setting for {path}.",
    "third_party_access": "Your answer leaves out who sees data sent by {path} ({label}).",
}


def _catch(answers: list[dict], stated: dict) -> dict | None:
    for a in answers:  # questionnaire order: the first failing answer leads
        if a["badge"] != "not_true":
            continue
        c = next(c for c in a["cells"] if c["verdict"] == "contradicts")
        fix = None
        if a["field"] == "zdr":
            ex = sorted(set((a["stated"].get("claim") or {}).get("exceptions") or []) |
                        {x["endpoint"] for x in a["cells"] if x["verdict"] == "contradicts"})
            fix = {"claim": {**a["stated"]["claim"], "exceptions": ex},
                   "text": "Yes, except: " + "; ".join(f"{x['endpoint']} ({x['feature_label']}, {x['value_label'].lower()})"
                                                       for x in a["cells"] if x["endpoint"] in ex) + "."}
        others = sum(x["badge"] == "not_true" for x in answers)
        return {"question": a["id"], "number": a["number"], "endpoint": c["endpoint"], "feature": c["feature"],
                "sentence": _CATCH_TEXT[a["field"]].format(path=c["endpoint"], label=c["feature_short"]),
                "quote": c["quote"], "source_url": c["source_url"], "source_label": c["source_label"],
                "fetched_at": c["fetched_at"], "fetched_at_local": c["fetched_at_local"],
                "primary": f"Fix answer {int(a['number'])}", "secondary": "Draft trust-page change",
                "not_true_answers": others, "fix": fix}
    return None


def brief(pack: dict) -> dict:
    return {"pack_id": pack["pack_id"], "as_of_local": pack["as_of_local"], "headline": pack["headline"],
            "counts": pack["counts"],
            "badges": {a["id"]: a["badge"] for a in pack["answers"]},
            "catch": {k: pack["catch"][k] for k in ("question", "endpoint", "sentence", "quote", "source_url", "fetched_at_local")}
            if pack["catch"] else None,
            "answers": [{"id": a["id"], "badge": a["badge"], "answer": a["answer"],
                         "cells": {c["endpoint"]: c["value_label"] for c in a["cells"]}} for a in pack["answers"]]}
