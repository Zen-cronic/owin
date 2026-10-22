"""Vendor terms registry: data/terms/<vendor>.json, exported from recorded Nemotron extraction runs.

The decision layer reads vendor windows only from here, never from a hand-typed
number. Each entry keeps the model, the run file and the hashes of the source and
the quote.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .evaluate import ROOT, headline_runs, load_corpus
from .schema import SCORED_FIELDS
from .textnorm import match_form, sha256

TERMS = ROOT / "data" / "terms"


def export(runs: list[Path] | None = None) -> list[Path]:
    corpus = {i["id"]: i for i in load_corpus()}
    by_id: dict[str, list[tuple[str, dict]]] = {}
    model = None
    for p in runs or headline_runs():
        d = json.loads(Path(p).read_text())
        model = d["model"]
        for c in d["calls"]:
            by_id.setdefault(c["id"], []).append((str(Path(p).resolve().relative_to(ROOT)), c))
    TERMS.mkdir(parents=True, exist_ok=True)
    out = []
    for vid, calls in by_id.items():
        ok = [(f, c) for f, c in calls if c.get("terms")]
        # Consensus over runs on the scored fields; a vendor with no majority is held.
        votes = Counter(json.dumps({k: c["terms"][k] for k in SCORED_FIELDS}, sort_keys=True) for _, c in ok)
        top, n = votes.most_common(1)[0] if votes else (None, 0)
        chosen = next(((f, c) for f, c in ok if json.dumps({k: c["terms"][k] for k in SCORED_FIELDS}, sort_keys=True) == top
                       and c["terms"]["status"] == "ok"), None) or next(((f, c) for f, c in ok
                       if json.dumps({k: c["terms"][k] for k in SCORED_FIELDS}, sort_keys=True) == top), (None, None))
        f, c = chosen
        terms = dict(c["terms"]) if c else {"window_type": "none", "status": "held", "hold_reasons": ["no parseable run"]}
        if n * 2 <= len(calls):
            terms["status"] = "held"
            terms.setdefault("hold_reasons", []).append(f"no majority across {len(calls)} runs")
        item = corpus.get(vid, {})
        entry = {"vendor": vid, "kind": item.get("kind"), "source_url": item.get("url"), "model": model,
                 "run_file": f, "runs_agreeing": f"{n}/{len(calls)}",
                 "source_sha256": c["source_sha256"] if c else None,
                 "quote_sha256": sha256(match_form(terms.get("quote", ""))) if terms.get("quote") else None,
                 "terms": terms}
        path = TERMS / f"{vid}.json"
        path.write_text(json.dumps(entry, indent=1) + "\n")
        out.append(path)
    return out


def load(vendor: str) -> dict:
    p = TERMS / f"{vendor}.json"
    if not p.exists():
        return {"vendor": vendor, "terms": {"window_type": "none", "status": "held",
                                             "hold_reasons": ["no measured extraction for this vendor"]}}
    return json.loads(p.read_text())
