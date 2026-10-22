"""Evidence typing: what kind of thing on the vendor's page a cited quote is.

Every citation is one of:
  sentence    running text; shown as a quote
  table_row   a row (or one cell) of a table on the page; shown as a key/value table with the cell that
              answers the question highlighted, never as flattened table text
  list_entry  one item of a bulleted or numbered list

The type and the table header come from the page captures (fixtures/raw/, gitignored), so they are computed
once by `owin pack evidence` and committed as data/datause/evidence.json, keyed by quote id. At runtime the
pack only looks quotes up (no raw pages needed, so the deployed image carries none). A quote that is not in
the index is typed from its own shape. Display only: no rule reads any of this.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .observations import quote_id

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "data" / "datause" / "evidence.json"
TAVILY_RAW = ROOT / "fixtures" / "raw" / "datause-tavily"

# Which column (or cell) answers which question. Matched against header names first, then cell text.
FIELD_KEYS = {
    "zdr": ("zdr", "zero data retention"),
    "retention_days": ("retention", "retain", "days"),
    "used_for_training": ("training", "train"),
    "third_party_access": ("third", "sub-processor", "subprocessor"),
    "region": ("region", "residency"),
}
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_LIST = re.compile(r"^\s*(?:[*+-]|\d+[.)])\s+")


def compact(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _LINK.sub(r"\1", s or "").lower())


def clean_cell(s: str) -> str:
    s = _LINK.sub(r"\1", s).replace("`", "").replace("**", "")
    return re.sub(r"\s+", " ", s).strip()


def split_row(line: str) -> list[str]:
    return [clean_cell(c) for c in line.strip().strip("|").split("|")]


def tables(md: str) -> list[tuple[list[str], list[list[str]]]]:
    """Markdown pipe tables: (header, rows)."""
    lines = md.splitlines()
    out = []
    i = 0
    while i < len(lines) - 1:
        if lines[i].lstrip().startswith("|") and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            header = split_row(lines[i])
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append(split_row(lines[j]))
                j += 1
            out.append((header, rows))
            i = j
        else:
            i += 1
    return out


def _match_table(q: str, md: str) -> dict | None:
    cq = compact(q)
    if len(cq) < 8:
        return None
    best = None
    for header, rows in tables(md):
        for row in rows:
            cells = [compact(c) for c in row]
            # One cell holds the whole quote (a sentence inside a table cell).
            for k, c in enumerate(cells):
                if cq and cq in c and (best is None or best[0] < 1):
                    best = (1, header, row, k)
            if cq in "".join(cells):
                covered = sum(1 for c in cells if c and c in cq)
                if covered >= 2 and (best is None or best[0] < 2 + covered):
                    best = (2 + covered, header, row, None)
    if not best:
        return None
    _, header, row, cell = best
    n = max(len(header), len(row))
    header = (header + [""] * n)[:n]
    row = (row + [""] * n)[:n]
    return {"kind": "table_row", "header": header, "cells": row, "quote_cell": cell}


def _match_list(q: str, md: str) -> dict | None:
    cq = compact(q)
    if len(cq) < 8:
        return None
    for line in md.splitlines():
        if _LIST.match(line) and cq in compact(line):
            return {"kind": "list_entry", "text": clean_cell(_LIST.sub("", line))}
    return None


def classify_on_page(q: str, md: str) -> dict:
    return _match_table(q, md) or _match_list(q, md) or {"kind": "sentence"}


def from_shape(q: str) -> dict:
    """No page to look at: type the quote from its own shape."""
    if q.count("|") >= 2:
        cells = [clean_cell(c) for c in q.strip().strip("|").split("|")]
        return {"kind": "table_row", "header": [""] * len(cells), "cells": cells, "quote_cell": None}
    lines = [l.strip() for l in q.splitlines() if l.strip()]
    if len(lines) >= 3 and max(len(l) for l in lines) < 80:
        return {"kind": "table_row", "header": [""] * len(lines), "cells": [clean_cell(l) for l in lines], "quote_cell": None}
    if _LIST.match(q):
        return {"kind": "list_entry", "text": clean_cell(_LIST.sub("", q))}
    return {"kind": "sentence"}


def _hit(ev: dict, field: str | None) -> int | None:
    """The cell that answers the question: the cell holding a sentence quote, else the column for the field."""
    if ev.get("quote_cell") is not None:
        return ev["quote_cell"]
    keys = FIELD_KEYS.get(field or "", ())
    for k, h in enumerate(ev["header"]):
        if any(x in h.lower() for x in keys):
            return k
    for k, c in enumerate(ev["cells"]):
        if k and any(x in c.lower() for x in keys):
            return k
    return None


@lru_cache(maxsize=1)
def _index() -> dict:
    return json.loads(INDEX.read_text())["quotes"] if INDEX.exists() else {}


def for_quote(q: str, field: str | None = None) -> dict | None:
    """Typed evidence for a quote, ready to render. None for an empty quote."""
    if not q:
        return None
    ev = _index().get(quote_id(q)) or from_shape(q)
    if ev["kind"] == "sentence":
        return {"kind": "sentence", "text": q.strip()}
    if ev["kind"] == "list_entry":
        return {"kind": "list_entry", "text": ev["text"]}
    hit = _hit(ev, field)
    rows = [{"key": h or None, "value": c, "match": k == hit} for k, (h, c) in enumerate(zip(ev["header"], ev["cells"]))
            if c or h]
    return {"kind": "table_row", "row_label": ev["cells"][0] if ev["cells"] else None, "rows": rows,
            "match_key": ev["header"][hit] if hit is not None and ev["header"][hit] else None}


def _registry_quotes(reg: dict) -> list[tuple[str, str]]:
    """(page, quote) for every quote the pack can show."""
    out = []
    for e in reg.values():
        page = e["page"]
        for k, v in (e.get("terms") or {}).items():
            if k.endswith("_quote") and v:
                out.append((page, v))
        for v in ((e.get("live_check") or {}).get("quotes") or {}).values():
            if v:
                out.append((page, v))
        for a in (e.get("field_agreement") or {}).values():
            for o in a.get("options", []):
                if o.get("quote"):
                    out.append((page, o["quote"]))
    return out


def build_index() -> Path:
    """Type every registry quote against the Tavily capture of its page. Needs fixtures/raw/ (local only)."""
    from . import registry
    reg = registry.load()
    quotes, missing = {}, set()
    for page, q in _registry_quotes(reg):
        p = TAVILY_RAW / f"{page}.md"
        if not p.exists():
            missing.add(page)
            continue
        ev = classify_on_page(q, p.read_text())
        quotes[quote_id(q)] = {**ev, "page": page}
    out = {"_about": "Evidence type per quote id (sentence | table_row | list_entry), built by `owin pack evidence` "
                     "from the Tavily captures. Display only; no rule reads it.",
           "pages_missing": sorted(missing), "quotes": dict(sorted(quotes.items()))}
    INDEX.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    _index.cache_clear()
    return INDEX


def list_entry(name: str, kind: str, before: dict | None, after: dict | None, fields: list[str] | None) -> dict:
    """A sub-processor list entry as key/value rows; the changed cells are the matched ones."""
    cells = after or before or {}
    rows = []
    for f in ("services", "purpose", "locations"):
        if f not in cells:
            continue
        changed = kind == "changed" and f in (fields or [])
        rows.append({"key": f.capitalize(), "value": cells.get(f) or "", "match": changed,
                     "was": (before or {}).get(f) if changed else None})
    return {"kind": "list_entry_table", "entity": name, "change": kind, "rows": rows}
