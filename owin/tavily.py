"""Tavily client: `extract` with NO query (full page, diffable).

TAVILY_API_KEY comes from the environment or OWIN_ENV_FILE (../.env). Without a
key, `fetch` falls back to the recorded fixture and labels the result
source_kind="fixture". It never pretends a fixture is live.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = os.environ.get("OWIN_TAVILY_URL", "https://api.tavily.com")


def api_key() -> str | None:
    k = os.environ.get("TAVILY_API_KEY")
    if k:
        return k
    env = Path(os.environ.get("OWIN_ENV_FILE", ROOT.parent / ".env"))
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("TAVILY_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


@dataclass
class Fetched:
    url: str
    content: str | None
    source_kind: str  # "tavily" | "fixture" | "unfetched"
    retrieved: str
    latency_s: float = 0.0
    error: str | None = None


def _post(path: str, body: dict, key: str, timeout: float = 60) -> dict:
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def extract(url: str, *, depth: str = "basic", key: str | None = None) -> Fetched:
    key = key or api_key()
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if not key:
        return Fetched(url, None, "unfetched", now, error="TAVILY_API_KEY not set")
    t0 = time.time()
    try:
        d = _post("/extract", {"urls": [url], "extract_depth": depth, "format": "markdown"}, key)
    except urllib.error.HTTPError as e:  # the status only; the body could echo request details
        return Fetched(url, None, "unfetched", now, round(time.time() - t0, 2), f"tavily HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError) as e:
        return Fetched(url, None, "unfetched", now, round(time.time() - t0, 2), f"tavily {type(e).__name__}")
    res = (d.get("results") or [{}])[0]
    content = res.get("raw_content")
    if content:
        return Fetched(url, content, "tavily", now, round(time.time() - t0, 2))
    failed = (d.get("failed_results") or [{}])[0]
    why = failed.get("error") if isinstance(failed, dict) else None
    return Fetched(url, None, "unfetched", now, round(time.time() - t0, 2),
                   "tavily returned no content" + (f": {str(why)[:120]}" if why else ""))


def fetch(entry: dict, *, live: bool = True) -> Fetched:
    """Live Tavily when a key exists and live=True, else the recorded fixture (labelled).

    The reason for an unfetched result is the real one: a failed live call reports the Tavily
    error, not "no key" (the P3 Pinecone row said "no TAVILY_API_KEY" while the key was present).
    """
    live_err = None
    if live and api_key():
        f = extract(entry["list_url"])
        if f.content:
            return f
        live_err = f.error
    fx = entry.get("fixture")
    if fx and (ROOT / fx).exists():
        p = ROOT / fx
        return Fetched(entry["list_url"], p.read_text(), "fixture",
                       time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(p.stat().st_mtime)),
                       error=f"live fetch failed ({live_err}); using recorded fixture" if live_err else None)
    if live_err:
        reason = f"live Tavily fetch failed: {live_err}; no recorded fixture"
    elif live:
        reason = "no TAVILY_API_KEY and no recorded fixture"
    else:
        reason = "live fetch disabled (--no-live) and no recorded fixture"
    return Fetched(entry["list_url"], None, "unfetched", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), error=reason)
