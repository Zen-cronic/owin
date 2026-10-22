"""Sub-processor entity tables: parse (HTML or markdown), normalise, diff.

The diff compares normalised entity keys and cells, never raw page text, so
boilerplate, chrome, pagers, link syntax and whitespace never produce a change.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser

from .textnorm import squash, strip_markdown, unify_chars

_SUFFIX = re.compile(r"\b(inc|llc|ltd|limited|corp|corporation|co|gmbh|sa|sas|bv|plc|pty|ag|l\.?l\.?c)\b\.?", re.I)
_NOISE = re.compile(r"\(opens in a new window\)|⁠|\*+")


def clean_cell(s: str) -> str:
    s = squash(_NOISE.sub("", unify_chars(strip_markdown(s))))
    s = re.sub(r"\s*;\s*(;\s*)*", "; ", s)
    return s.strip(" ,;")


def cell_values(s: str) -> list[str]:
    """Split a cell into values. HTML <br> boundaries survive as ';'. Tavily markdown loses them, so fall back to words."""
    parts = [p.strip() for p in s.split(";")] if ";" in s else s.split()
    return [p for p in parts if p]


def entity_key(name: str) -> str:
    n = clean_cell(name).lower()
    n = re.sub(r"\(.*?\)", "", n)
    n = _SUFFIX.sub("", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return squash(n)


@dataclass
class Entity:
    name: str
    key: str
    services: str = ""
    locations: str = ""
    purpose: str = ""
    section: str = ""

    def cells(self) -> dict:
        return {"services": self.services, "locations": self.locations, "purpose": self.purpose}


@dataclass
class Snapshot:
    vendor: str
    source_url: str
    retrieved: str
    source_kind: str  # "archive" | "tavily" | "fixture" | "live"
    last_updated: str | None
    entities: list[Entity] = field(default_factory=list)
    content_sha256: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Snapshot":
        d = dict(d)
        d["entities"] = [Entity(**e) for e in d.get("entities", [])]
        return Snapshot(**d)


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
            self.depth += 1
        elif tag == "tr" and self.depth:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []
        elif tag == "br" and self.cell is not None:
            self.cell.append("; ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append("".join(self.cell))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.tables[-1].append(self.row)
            self.row = None
        elif tag == "table" and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def html_tables(raw_html: str) -> list[list[list[str]]]:
    p = _Tables()
    p.feed(raw_html)
    return [[[clean_cell(c) for c in r] for r in t] for t in p.tables]


def markdown_tables(md: str) -> list[list[list[str]]]:
    tables, cur = [], []
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [clean_cell(c) for c in re.split(r"(?<!\\)\|", s[1:-1])]
            if all(re.fullmatch(r":?-{3,}:?", c) or c == "" for c in cells):
                continue
            cur.append(cells)
        elif cur:
            tables.append(cur)
            cur = []
    if cur:
        tables.append(cur)
    return tables


def _header_index(header: list[str]) -> dict[str, int]:
    idx = {}
    for i, h in enumerate(h.lower() for h in header):
        if "name" in h or h in ("entity", "sub-processor", "subprocessor", "vendor", "company"):
            idx.setdefault("name", i)
        elif "service" in h or "product" in h:
            idx.setdefault("services", i)
        elif "location" in h or "country" in h or "region" in h:
            idx.setdefault("locations", i)
        elif "purpose" in h or "function" in h or "activit" in h or "description" in h:
            idx.setdefault("purpose", i)
        elif "parent" in h:
            idx.setdefault("parent", i)
    return idx


def entities_from_tables(tables: list[list[list[str]]], sections: list[str] | None = None) -> list[Entity]:
    out: dict[str, Entity] = {}
    for ti, t in enumerate(tables):
        hdr_row = next((i for i, r in enumerate(t) if "name" in _header_index(r)), None)
        if hdr_row is None:
            continue
        idx = _header_index(t[hdr_row])
        for r in t[hdr_row + 1:]:
            if len(r) <= idx["name"]:
                continue
            name = r[idx["name"]]
            key = entity_key(name)
            if not key or key in out:
                continue  # duplicate tables (e.g. a pager widget above the full list) collapse here
            get = lambda f: r[idx[f]] if f in idx and idx[f] < len(r) else ""
            purpose = get("purpose")
            if not purpose and "parent" in idx:
                purpose = "Vendor affiliate" + (f" (parent: {get('parent')})" if get("parent") else "")
            out[key] = Entity(name=name, key=key, services=get("services"), locations=get("locations"),
                              purpose=purpose, section=(sections[ti] if sections and ti < len(sections) else f"table{ti + 1}"))
    return list(out.values())


_LAST = re.compile(r"(?:last\s+updated|updated|effective(?:\s+date)?)\s*:?\s*@?([A-Z][a-z]+\.? \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2})", re.I)


def last_updated(text: str) -> str | None:
    m = _LAST.search(unify_chars(strip_markdown(text)))
    return m.group(1) if m else None


def parse(content: str, *, is_html: bool) -> tuple[list[Entity], str | None]:
    if is_html:
        from .textnorm import html_to_text
        return entities_from_tables(html_tables(content)), last_updated(html_to_text(content))
    return entities_from_tables(markdown_tables(content)), last_updated(content)


@dataclass
class EntityChange:
    kind: str  # "added" | "removed" | "changed"
    key: str
    name: str
    before: dict | None
    after: dict | None
    changed_fields: list[str] = field(default_factory=list)
    added_values: dict = field(default_factory=dict)


def _cell_norm(s: str) -> str:
    return " ".join(sorted(set(re.sub(r"[^a-z0-9 ]+", " ", s.lower()).split())))


def diff(before: Snapshot, after: Snapshot) -> list[EntityChange]:
    b = {e.key: e for e in before.entities}
    a = {e.key: e for e in after.entities}
    out = []
    for k in sorted(a.keys() - b.keys()):
        out.append(EntityChange("added", k, a[k].name, None, a[k].cells()))
    for k in sorted(b.keys() - a.keys()):
        out.append(EntityChange("removed", k, b[k].name, b[k].cells(), None))
    for k in sorted(a.keys() & b.keys()):
        fields = [f for f in ("services", "locations", "purpose")
                  if _cell_norm(getattr(a[k], f)) != _cell_norm(getattr(b[k], f))]
        if fields:
            added = {}
            for f in fields:
                before_vals = {v.lower() for v in cell_values(getattr(b[k], f))}
                new = [v for v in cell_values(getattr(a[k], f)) if v.lower() not in before_vals]
                if new:
                    added[f] = new
            out.append(EntityChange("changed", k, a[k].name, b[k].cells(), a[k].cells(), fields, added))
    return out
