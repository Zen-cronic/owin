"""Build committed entity snapshots (fixtures/snapshots/*.json) from gitignored raw captures."""
from __future__ import annotations

import json
from pathlib import Path

from .entities import Snapshot, parse
from .textnorm import sha256

ROOT = Path(__file__).resolve().parent.parent

# raw file, snapshot file, vendor, source URL, retrieved (UTC), source kind
ARCHIVED = [
    ("openai-list-wayback-20260708120959.html", "openai-list-20260708.json", "openai",
     "https://web.archive.org/web/20260708120959/https://openai.com/policies/sub-processor-list/", "2026-07-08T12:09:59Z", "archive"),
    ("openai-list-wayback-20261021154629.html", "openai-list-20261021.json", "openai",
     "https://web.archive.org/web/20261021154629/https://openai.com/policies/sub-processor-list/", "2026-10-21T15:46:29Z", "archive"),
]


def build() -> list[Path]:
    out = []
    for raw, snap, vendor, url, retrieved, kind in ARCHIVED:
        p = ROOT / "fixtures" / "raw" / raw
        if not p.exists():
            continue
        content = p.read_text()
        ents, lu = parse(content, is_html=raw.endswith(".html"))
        s = Snapshot(vendor, url, retrieved, kind, lu, ents, sha256(content))
        dst = ROOT / "fixtures" / "snapshots" / snap
        dst.write_text(json.dumps(s.to_dict(), indent=1) + "\n")
        out.append(dst)
    return out
