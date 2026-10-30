"""Sweep the vendor index: fetch (Tavily, or a labelled fixture), normalise to an entity table, diff with the last accepted snapshot.

Per-vendor states: watching (first baseline), no_change, changed, stale_source (held),
not_watchable, date_only_changed, unfetched. Rules:
- The diff runs on normalised entity tables, never raw text, so page chrome is ignored.
- Before declaring no_change on a live result, Owin re-fetches once (advanced depth),
  because Tavily may serve a cached copy.
- If the fetched page's "Last updated" date is OLDER than the accepted snapshot's, the
  source is stale: hold, and never overwrite the newer state.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from pathlib import Path

from . import tavily
from .decide import classify, parse_page_date
from .entities import Snapshot, diff, parse_any
from .textnorm import sha256

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "index" / "vendors.json"


def state_dir() -> Path:
    return Path(os.environ.get("OWIN_STATE_DIR", ROOT / "var" / "state"))


def load_index() -> list[dict]:
    return json.loads(INDEX.read_text())["vendors"]


def _prev(vendor: str) -> Snapshot | None:
    p = state_dir() / f"{vendor}.json"
    return Snapshot.from_dict(json.loads(p.read_text())) if p.exists() else None


def _save(s: Snapshot) -> None:
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{s.vendor}.json").write_text(json.dumps(s.to_dict(), indent=1))


def seed(snapshot: Snapshot) -> None:
    """Accept a snapshot as the baseline (e.g. an archived capture)."""
    _save(snapshot)


def _snap(entry: dict, f: tavily.Fetched) -> tuple[Snapshot, str]:
    ents, lu, parser = parse_any(f.content or "", is_html=(f.content or "").lstrip().startswith("<"))
    return Snapshot(entry["vendor"], f.url, f.retrieved, f.source_kind, lu, ents, sha256(f.content or "")), parser


def sweep_one(entry: dict, *, live: bool = True, refetch=None) -> dict:
    f = tavily.fetch(entry, live=live)
    row = {"vendor": entry["vendor"], "display": entry["display"], "list_url": entry["list_url"],
           "source_kind": f.source_kind, "retrieved": f.retrieved, "latency_s": f.latency_s, "refetched": False}
    if not f.content:
        return {**row, "state": "unfetched", "reason": f.error}
    cur, parser = _snap(entry, f)
    prev = _prev(entry["vendor"])
    row |= {"parser": parser, "entities": len(cur.entities), "last_updated": cur.last_updated,
            "prev_last_updated": prev.last_updated if prev else None}
    if not cur.entities:
        if prev and cur.last_updated and prev.last_updated and cur.last_updated != prev.last_updated:
            _save(cur)
            return {**row, "state": "date_only_changed", "reason": f"'Last updated' moved {prev.last_updated} -> {cur.last_updated}; the list itself is not diffable (review by hand)"}
        if cur.last_updated and not prev:
            _save(cur)
            return {**row, "state": "watching", "reason": "date only: no entity table, watching the 'Last updated' date"}
        if cur.last_updated:
            return {**row, "state": "no_change", "reason": "date only, unchanged"}
        return {**row, "state": "not_watchable", "reason": "no entity table and no date (JS widget or gated page)"}
    if prev is None:
        _save(cur)
        return {**row, "state": "watching", "reason": "first snapshot accepted as baseline"}
    pd, cd = parse_page_date(prev.last_updated), parse_page_date(cur.last_updated)
    if pd and cd and cd < pd:
        return {**row, "state": "stale_source", "held": True,
                "reason": f"fetched page says 'Last updated {cur.last_updated}', older than the accepted snapshot ({prev.last_updated}); likely a cached copy. Set aside; state not overwritten."}
    changes = diff(prev, cur)
    if not changes and f.source_kind == "tavily":
        g = (refetch or (lambda e: tavily.extract(e["list_url"], depth="advanced")))(entry)
        row["refetched"] = True
        if g.content:
            cur2, _ = _snap(entry, g)
            changes = diff(prev, cur2)
            if changes:
                cur = cur2
    if not changes:
        return {**row, "state": "no_change",
                "reason": "entity table identical" + ("" if f.source_kind == "tavily" else f" (source: {f.source_kind}; no live re-fetch)")}
    cl = classify(changes, [])
    _save(cur)
    return {**row, "state": "changed", "material": len(cl.material),
            "changes": [{k: c[k] for k in ("kind", "entity", "why")} | ({"new_locations": c["new_locations"]} if c.get("new_locations") else {})
                        for c in cl.material + cl.other]}


def run(*, live: bool = True, only: list[str] | None = None, record: Path | None = None) -> dict:
    t0 = time.time()
    rows = []
    for e in load_index():
        if only and e["vendor"] not in only:
            continue
        no_source = not e.get("fixture") and not (live and tavily.api_key())
        if e["watch_mode"] in ("dpa_only", "list_in_dpa_appendix", "list_in_dpa_annex") or no_source:
            unverified = e["watch_mode"].startswith("unverified")
            why = ("no TAVILY_API_KEY and no recorded fixture" if not tavily.api_key()
                   else "live fetch disabled (--no-live) and no recorded fixture")
            rows.append({"vendor": e["vendor"], "display": e["display"], "list_url": e["list_url"],
                         "state": "unfetched" if unverified else "not_watchable",
                         "reason": why if unverified else f"watch_mode={e['watch_mode']}: watch the DPA itself"})
            continue
        rows.append(sweep_one(e, live=live))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    out = {"run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tavily_key_present": bool(tavily.api_key()),
           "live_requested": live, "vendors": len(rows), "counts": counts, "wall_s": round(time.time() - t0, 2), "rows": rows}
    if record:
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps(out, indent=1) + "\n")
    return out
