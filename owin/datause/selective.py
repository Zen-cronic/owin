"""Selective answering: Owin answers a field on its own only when every extraction run agrees on it.

One cell = one (feature, scored field). A cell is `auto` when at least 2 runs succeeded and every successful
run returns the same value for that field after the verbatim-quote gate. A run that errored or returned no
terms abstains (it neither agrees nor disagrees). Every other cell is
`confirm`: held for a person, shown with the differing values and their quotes. The rule reads only the
gated structured values, never model prose; the pack (owin/datause/pack.py) uses the same `agreement` function.

`owin eval selective --corpus datause [--split v3fresh]` recomputes the numbers from recorded runs, keyless:
auto-answered cells, correct among them (split into answers that carry an asserted value with the page's verbatim
sentence and correct "not stated" answers on pages that say nothing), cells sent to confirm, how often the majority
value would have been right on the confirm cells and on every cell (what a "just take the majority" system would
have shipped), the distinct pages, and the vendor families the split adds to the corpus.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Sequence

from . import evaluate as dv
from .schema import QUOTE_OF, SCORED_FIELDS

_MISSING = "__no_terms__"


MIN_READINGS = 2


def agreement(runs: Sequence[dict | None], field: str) -> dict:
    """Per-field agreement over gated run terms. Decides auto vs confirm.

    An errored run (None, or no terms) abstains: it is neither a vote for nor against any value. A cell is
    `auto` only when at least MIN_READINGS runs succeeded and every successful reading gives the same value.
    """
    ok = [t for t in runs if t]
    failed = len(runs) - len(ok)
    vals = [t.get(field, _MISSING) for t in ok]
    votes = Counter(json.dumps(v) for v in vals)
    top, n = votes.most_common(1)[0] if votes else (json.dumps(_MISSING), 0)
    unanimous = len(ok) >= MIN_READINGS and n == len(ok) and json.loads(top) != _MISSING
    majority = json.loads(top) if n * 2 > len(ok) and json.loads(top) != _MISSING else _MISSING
    seen, options = set(), []
    for t, v in zip(ok, vals):
        k = json.dumps(v)
        if k in seen:
            continue
        seen.add(k)
        options.append({"value": None if v == _MISSING else v, "no_terms": v == _MISSING,
                        "runs": votes[k], "quote": t.get(QUOTE_OF.get(field, ""), "")})
    return {"state": "auto" if unanimous else "confirm", "runs_agreeing": f"{n}/{len(ok)}",
            "readings_ok": len(ok), "readings_failed": failed, "readings_total": len(runs),
            "value": json.loads(top) if unanimous else None,
            "majority": None if majority == _MISSING else majority, "has_majority": majority != _MISSING,
            "options": options}


def _gated(paths: Sequence[Path]) -> tuple[dict, dict[str, list]]:
    corpus = {i["id"]: i for i in dv.load_corpus()}
    per: dict[str, list] = {}
    for p in paths:
        for c in json.loads(Path(p).read_text())["calls"]:
            if c["id"] in corpus:
                per.setdefault(c["id"], []).append(dv._recheck(c["terms"], dv._source(corpus[c["id"]])))
    return corpus, per


def evaluate(paths: Sequence[Path], split: str | None = None, kinds: tuple[str, ...] = ("heldout", "tuned"),
             exclude_split: str | None = None) -> dict:
    corpus, per = _gated(paths)
    cells = []
    for iid, runs in sorted(per.items()):
        it = corpus[iid]
        if it["kind"] not in kinds or (split and it["split"] != split) or (exclude_split and it["split"] == exclude_split):
            continue
        for f in SCORED_FIELDS:
            a = agreement(runs, f)
            gold = it["gold"][f]
            cells.append({"item": iid, "vendor": it["vendor"], "url": it["url"], "field": f, "gold": gold, **a,
                          "correct": a["state"] == "auto" and a["value"] == gold,
                          # An asserted value (anything but null / "unspecified") carries the page's verbatim sentence;
                          # a correct "not stated" is a page that says nothing on the field, read as saying nothing.
                          "asserted": a["state"] == "auto" and a["value"] not in (None, "unspecified"),
                          "majority_right": a["has_majority"] and a["majority"] == gold})
    auto = [c for c in cells if c["state"] == "auto"]
    conf = [c for c in cells if c["state"] == "confirm"]
    ok = [c for c in auto if c["correct"]]
    return {
        "cells": len(cells), "items": len({c["item"] for c in cells}), "vendors": len({c["vendor"] for c in cells}),
        "pages": len({c["url"] for c in cells}),
        "auto_answered": f"{len(auto)}/{len(cells)}", "auto_correct": f"{len(ok)}/{len(auto)}",
        "auto_precision": round(len(ok) / len(auto), 4) if auto else None,
        "correct_with_sentence": sum(c["asserted"] for c in ok), "correct_not_stated": sum(not c["asserted"] for c in ok),
        "sent_to_confirm": len(conf),
        "confirm_majority_right": f"{sum(c['majority_right'] for c in conf)}/{len(conf)}",
        "all_cells_majority_right": f"{sum(c['majority_right'] for c in cells)}/{len(cells)}",
        "auto_misses": [{k: c[k] for k in ("item", "field", "value", "gold")} for c in auto if not c["correct"]],
        "confirm_cells": [{k: c[k] for k in ("item", "field", "runs_agreeing", "majority", "gold", "majority_right")} |
                          {"values": [o["value"] for o in c["options"]]} for c in conf],
    }


FOOTNOTES = {
    ("openrouter-inference-zdr", "retention_days"):
        "Self-disclosed label error: the page says prompts are not retained unless you opt in to logging, so the label "
        "should be 0; v3 answered 0 on 3/3 runs. The label is kept as pre-registered, so this counts as a miss.",
}


def vendor_family(vendor: str) -> str:
    """'Google Cloud (Vertex AI / Gemini Enterprise Agent Platform)' and 'Google Cloud' are one vendor family."""
    return vendor.split(" (")[0].strip().lower()


def vendors_new(split: str | None, kinds: tuple[str, ...] = ("heldout", "tuned")) -> int:
    """Vendor families in `split` that appear nowhere else in the corpus (all when split is None)."""
    corpus = dv.load_corpus()
    inside = {vendor_family(i["vendor"]) for i in corpus if i["kind"] in kinds and (not split or i["split"] == split)}
    if not split:
        return len(inside)
    outside = {vendor_family(i["vendor"]) for i in corpus if i["split"] != split}
    return len(inside - outside)


def report(split: str = "v3fresh", files: Sequence[Path] | None = None) -> dict:
    """The headline (pre-registered split, prompt v3) plus clearly labelled non-clean references."""
    head_files = list(files) if files else dv.headline_runs()
    head = evaluate(head_files, split=split or None)
    head["vendors_new"] = vendors_new(split or None)
    misses = [{**m, "footnote": FOOTNOTES.get((m["item"], m["field"]))} for m in head["auto_misses"]]
    out = {
        "rule": "a cell (feature x scored field) is auto-answered only when at least 2 runs succeeded and every "
                "successful run agrees on that field after the verbatim-quote gate (an errored run abstains); "
                "otherwise it is sent to a person to confirm",
        "split": split or "all", "run_files": [str(Path(p).resolve().relative_to(dv.ROOT)) for p in head_files],
        "quotes_rechecked_against_source": all(dv._source(i) is not None for i in dv.load_corpus()),
        "headline": {**head, "auto_misses": misses},
        "negative_controls": evaluate(head_files, split=split or None, kinds=("negative",)),
    }
    if not files and split == "v3fresh":
        out["reference_not_clean"] = {
            "_about": "older items; v2's misses on them informed prompt v3, so these are NOT clean tests",
            "v3_old": {k: v for k, v in evaluate(dv.reference_runs(), exclude_split="v3fresh").items()
                       if k not in ("confirm_cells",)},
            "v2_old": {k: v for k, v in evaluate(dv._headline_key("previous_headline_runs"), exclude_split="v3fresh").items()
                       if k not in ("confirm_cells",)},
        }
    return out


def brief(rep: dict) -> dict:
    h = rep["headline"]
    return {"split": rep["split"], "cells": h["cells"], "items": h["items"], "vendors": h["vendors"],
            "vendors_new": h["vendors_new"], "pages": h["pages"],
            "auto_answered": h["auto_answered"], "auto_correct": h["auto_correct"],
            "with_sentence": h["correct_with_sentence"], "not_stated": h["correct_not_stated"],
            "sent_to_confirm": h["sent_to_confirm"], "confirm_majority_right": h["confirm_majority_right"],
            "all_cells_majority_right": h["all_cells_majority_right"],
            "auto_misses": h["auto_misses"],
            "reference_not_clean": {k: {x: v[x] for x in ("auto_answered", "auto_correct", "sent_to_confirm")}
                                    for k, v in (rep.get("reference_not_clean") or {}).items() if k != "_about"}}
