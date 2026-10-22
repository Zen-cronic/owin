"""Provenance for gitignored raw fixtures: URL, fetch method, size and sha256 (committed as fixtures/manifest.json).

Raw vendor text is not redistributed. A fresh clone can re-fetch each URL, and the
sha256 says whether it got the same bytes the recorded runs were scored against.
"""
from __future__ import annotations

import json
from pathlib import Path

from .evaluate import ROOT, load_corpus
from .textnorm import sha256

MANIFEST = ROOT / "fixtures" / "manifest.json"
S1_TAVILY = {"vercel", "supabase", "mistral", "anthropic", "nebius", "stripe", "nvidia", "aws", "google",
             "neg-openai-live", "neg-anthropic-list"}


def method(item: dict) -> str:
    if item["id"] in S1_TAVILY:
        return "tavily_extract (no query), raw_content, 2026-10-21 (spike S1)"
    if "web.archive.org" in item["url"]:
        return "curl web.archive.org id_ capture + owin.textnorm.html_to_text, 2026-10-21"
    return "curl (browser UA) + owin.textnorm.html_to_text, 2026-10-21"


def build() -> dict:
    out = {}
    for item in load_corpus():
        p = ROOT / item["file"]
        entry = {"url": item["url"], "file": item["file"], "method": method(item), "kind": item["kind"]}
        if p.exists():
            t = p.read_text()
            entry |= {"chars": len(t), "sha256": sha256(t)}
        out[item["id"]] = entry
    return out


def write() -> Path:
    old = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    new = build()
    for k, v in new.items():  # keep recorded hashes when the raw file is absent locally
        if "sha256" not in v and k in old:
            v |= {kk: old[k][kk] for kk in ("chars", "sha256") if kk in old[k]}
    if "datause" in old:  # Pivot A provenance, written by owin.datause.fetch
        new["datause"] = old["datause"]
    MANIFEST.write_text(json.dumps(new, indent=1) + "\n")
    return MANIFEST
