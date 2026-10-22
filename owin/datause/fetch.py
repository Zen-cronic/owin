"""Fetch vendor documentation pages for the data-use corpus (stdlib, browser UA, cookie jar).

Raw HTML and its plain-text form go to fixtures/raw/datause/ (gitignored, not redistributed).
Provenance (URL, final URL, fetch time, method, sha256 of the text) goes to the
"datause" section of fixtures/manifest.json, which is committed. A fresh clone re-fetches and
compares hashes to know whether it is scoring the same bytes.
"""
from __future__ import annotations

import http.cookiejar
import json
import time
import urllib.request
from pathlib import Path

from ..textnorm import html_to_text, sha256

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "fixtures" / "raw" / "datause"
MANIFEST = ROOT / "fixtures" / "manifest.json"
SECTION = "datause"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")
METHOD = "urllib GET (browser UA, cookie jar) + owin.textnorm.html_to_text"


def fetch(source_id: str, url: str, timeout: float = 30) -> dict:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", UA), ("Accept-Language", "en-US,en;q=0.9")]
    last = None
    for _ in range(3):  # Google dev sites bounce through an auth probe once, then serve with the cookie
        with opener.open(url, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            last = r.geturl()
        if "accounts.google.com" not in last and "oauth2" not in last:
            break
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{source_id}.html").write_text(body)
    text = html_to_text(body)
    (RAW / f"{source_id}.txt").write_text(text)
    return {"url": url, "final_url": last, "file": f"fixtures/raw/datause/{source_id}.txt",
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "method": METHOD,
            "html_bytes": len(body), "chars": len(text), "sha256": sha256(text)}


def fetch_all(sources: dict[str, str], only: list[str] | None = None) -> dict:
    whole = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    man = whole.setdefault(SECTION, {})
    for sid, url in sources.items():
        if only and sid not in only:
            continue
        try:
            man[sid] = fetch(sid, url)
        except Exception as e:  # recorded, not hidden
            man[sid] = {"url": url, "error": f"{type(e).__name__}: {e}"[:200],
                        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    whole[SECTION] = dict(sorted(man.items()))
    MANIFEST.write_text(json.dumps(whole, indent=1) + "\n")
    return man


# Tavily path (A3). Tavily `extract` with NO query returns the whole page as markdown, so it is diffable and
# every quote can be re-checked against it. The stdlib fetcher above stays as the labelled fallback.
RAW_TAVILY = ROOT / "fixtures" / "raw" / "datause-tavily"
SECTION_TAVILY = "datause_tavily"
METHOD_TAVILY = "tavily extract (no query, extract_depth=basic, format=markdown)"
METHOD_FALLBACK = "FALLBACK " + METHOD


def fetch_tavily(source_id: str, url: str, *, depth: str = "basic") -> dict:
    """One page through Tavily; on failure, the stdlib fetcher, labelled as a fallback. Never logs the key."""
    from .. import tavily
    f = tavily.extract(url, depth=depth)
    RAW_TAVILY.mkdir(parents=True, exist_ok=True)
    if f.content:
        (RAW_TAVILY / f"{source_id}.md").write_text(f.content)
        return {"url": url, "file": f"fixtures/raw/datause-tavily/{source_id}.md", "fetched_at": f.retrieved,
                "method": METHOD_TAVILY.replace("basic", depth), "source_kind": "tavily", "latency_s": f.latency_s,
                "chars": len(f.content), "sha256": sha256(f.content), "tavily_error": None}
    rec = fetch(source_id, url)
    text = (RAW / f"{source_id}.txt").read_text()
    (RAW_TAVILY / f"{source_id}.md").write_text(text)
    return {**rec, "file": f"fixtures/raw/datause-tavily/{source_id}.md", "method": METHOD_FALLBACK,
            "source_kind": "urllib_fallback", "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tavily_error": f.error}


def fetch_all_tavily(sources: dict[str, str]) -> dict:
    whole = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    man = whole.setdefault(SECTION_TAVILY, {})
    for sid, url in sources.items():
        try:
            man[sid] = fetch_tavily(sid, url)
        except Exception as e:  # recorded, not hidden
            man[sid] = {"url": url, "error": f"{type(e).__name__}: {e}"[:200], "source_kind": "unfetched",
                        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    whole[SECTION_TAVILY] = dict(sorted(man.items()))
    MANIFEST.write_text(json.dumps(whole, indent=1) + "\n")
    return man
