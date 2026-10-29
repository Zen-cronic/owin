"""Page observations for the answer pack: data/datause/observations.json (committed; hashes, never page text).

Every vendor page the stack relies on gets a dated list of observations. Each one records
when it was seen, how (tavily | urllib | urllib_fallback | archive), the sha256 of the captured text and:
- for a data-use page: whether each registry quote on that page is still present in that capture;
- for a sub-processor list: the entity snapshot (fixtures/snapshots/*.json) and its "Last updated" date.

`refresh` re-fetches through Tavily (stdlib fallback, labelled) and appends observations. The answer pack
only reads this file, so building a pack is deterministic and needs no network or raw captures.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from .. import config
from ..decide import parse_page_date
from ..entities import Snapshot, parse_any
from ..textnorm import is_present, match_form, sha256
from . import fetch as fetchmod
from . import registry

ROOT = Path(__file__).resolve().parents[2]
OBS_REL = "data/datause/observations.json"
OBS = ROOT / OBS_REL
SNAP = ROOT / "fixtures" / "snapshots"
MANIFEST = ROOT / "fixtures" / "manifest.json"

# Real archived captures of OpenAI's sub-processor list (built by `owin snapshots build`, used by the P2 replay).
ARCHIVED_LISTS = {"openai-subprocessors": ["openai-list-20260708.json", "openai-list-20261021.json"]}


def quote_id(q: str) -> str:
    return sha256(match_form(q))[:16]


def page_quotes(page: str) -> dict[str, str]:
    """Every registry quote that lives on this page, keyed by quote id."""
    out = {}
    for f in registry.load().values():
        t = f.get("terms") or {}
        if f["page"] != page:
            continue
        live_q = (f.get("live_check") or {}).get("quotes") or {}
        for q in [t.get(qf) for qf in ("retention_quote", "training_quote", "zdr_quote", "region_quote",
                                       "third_party_quote")] + list(live_q.values()):
            if q:
                out[quote_id(q)] = q
    return out


# Observations appended by POST /api/recheck while no OWIN_STATE_DIR is set: kept for this process only, merged
# on top of the committed file by `load`, never written into the repo.
_LIVE: dict[str, list[dict]] = {}
_LIVE_LOCK = threading.RLock()  # append_live calls load() under the lock


def load() -> dict:
    p = config.read_path(OBS_REL)
    obs = json.loads(p.read_text()) if p.exists() else {"pages": {}}
    with _LIVE_LOCK:
        for page, lst in _LIVE.items():
            for o in lst:
                _add(obs, page, dict(o))
    return obs


def live_persisted() -> bool:
    return config.state_dir() is not None


def append_live(page: str, o: dict) -> None:
    """Record one observation made at request time: into the state dir when there is one, else in memory."""
    if live_persisted():
        with _LIVE_LOCK:
            obs = load()
            _add(obs, page, o)
            obs["recorded_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            config.write_atomic(OBS_REL, json.dumps(obs, indent=1) + "\n")
        return
    with _LIVE_LOCK:
        _LIVE.setdefault(page, []).append(o)


def clear_live() -> None:
    with _LIVE_LOCK:
        _LIVE.clear()


def _add(obs: dict, page: str, o: dict) -> None:
    lst = obs["pages"].setdefault(page, {"observations": []})["observations"]
    lst[:] = [x for x in lst if not (x["observed_at"] == o["observed_at"] and x["source_kind"] == o["source_kind"])]
    lst.append(o)
    lst.sort(key=lambda x: x["observed_at"])


def _utc(ts: str) -> str:
    """'2026-10-21T20:49:39-0400' or '...Z' -> '2026-10-22T00:49:39Z'."""
    from datetime import datetime, timezone
    s = ts.replace("Z", "+00:00")
    if len(s) > 5 and s[-5] in "+-" and s[-3] != ":":
        s = s[:-2] + ":" + s[-2:]
    return datetime.fromisoformat(s).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _datause_obs(page: str, rec: dict, text: str | None, kind: str) -> dict:
    o = {"observed_at": _utc(rec["fetched_at"]), "source_kind": kind, "method": rec.get("method"), "url": rec["url"],
         "sha256": rec.get("sha256"), "chars": rec.get("chars")}
    if text is not None:
        o["quotes_present"] = {qid: is_present(q, text) for qid, q in page_quotes(page).items()}
    return o


def _list_obs(page: str, snap_file: str, *, held_reason: str | None = None) -> dict:
    s = Snapshot.from_dict(json.loads(config.read_path(f"fixtures/snapshots/{snap_file}").read_text()))
    o = {"observed_at": s.retrieved, "source_kind": s.source_kind, "url": s.source_url, "sha256": s.content_sha256,
         "snapshot": f"fixtures/snapshots/{snap_file}", "last_updated": s.last_updated, "entities": len(s.entities)}
    if held_reason:
        o["held"] = held_reason
    return o


def record(pages: list[str] | None = None) -> Path:
    """Append observations from the captures on disk (A1 urllib manifest, Tavily manifest, archived lists)."""
    cat = registry.load_catalog()
    man = json.loads(MANIFEST.read_text())
    obs = load()
    for page, meta in cat["pages"].items():
        if pages and page not in pages:
            continue
        obs["pages"].setdefault(page, {"observations": []}).update({"url": meta["url"], "kind": meta["kind"],
                                                                     "label": meta["label"], "provider": meta["provider"]})
        if meta["kind"] == "datause":
            a1 = man.get("datause", {}).get(page)
            if a1 and a1.get("sha256"):
                p = ROOT / a1["file"]
                _add(obs, page, _datause_obs(page, a1, p.read_text() if p.exists() else None, "urllib"))
            tv = man.get("datause_tavily", {}).get(page)
            if tv and tv.get("sha256"):
                p = ROOT / tv["file"]
                _add(obs, page, _datause_obs(page, tv, p.read_text() if p.exists() else None, tv["source_kind"]))
            continue
        for f in ARCHIVED_LISTS.get(page, []):
            if config.read_path(f"fixtures/snapshots/{f}").exists():
                _add(obs, page, _list_obs(page, f))
        tv = man.get("datause_tavily", {}).get(page)
        if tv and tv.get("sha256"):
            p = ROOT / tv["file"]
            if p.exists():
                ents, lu, _ = parse_any(p.read_text(), is_html=False)
                stamp = _utc(tv["fetched_at"]).replace("-", "").replace(":", "")[:8]
                name = f"{page}-tavily-{stamp}.json"
                s = Snapshot(meta["provider"], meta["url"], _utc(tv["fetched_at"]), "tavily", lu, ents, tv["sha256"])
                config.write_atomic(f"fixtures/snapshots/{name}", json.dumps(s.to_dict(), indent=1) + "\n")
            name = f"{page}-tavily-{_utc(tv['fetched_at']).replace('-', '').replace(':', '')[:8]}.json"
            if config.read_path(f"fixtures/snapshots/{name}").exists():
                cur = json.loads(config.read_path(f"fixtures/snapshots/{name}").read_text())
                newest = max((parse_page_date(x.get("last_updated")) for x in obs["pages"][page]["observations"]
                              if x.get("last_updated") and not x.get("held")), default=None)
                cd = parse_page_date(cur.get("last_updated"))
                held = (f"stale_source: Tavily served 'Last updated {cur['last_updated']}', older than an accepted capture; "
                        "held, not used as the latest" if newest and cd and cd < newest else None)
                _add(obs, page, _list_obs(page, name, held_reason=held))
    obs["_about"] = ("Recorded by `owin pack refresh`. Hashes and quote-presence only; page text stays in gitignored "
                     "fixtures/raw/. quotes_present maps a quote id (sha256 of its match form, 16 hex) to 'verbatim', "
                     "'table_insensitive' or null (gone).")
    obs["recorded_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return config.write_atomic(OBS_REL, json.dumps(obs, indent=1) + "\n")


def refresh(pages: list[str], *, fetch: bool = True) -> dict:
    """Re-fetch `pages` through Tavily (labelled stdlib fallback), then record observations."""
    cat = registry.load_catalog()
    res = {}
    if fetch:
        res = fetchmod.fetch_all_tavily({p: cat["pages"][p]["url"] for p in pages})
    record()
    return {"fetched": {p: {k: r.get(k) for k in ("source_kind", "fetched_at", "chars", "latency_s", "tavily_error", "error")}
                        for p, r in res.items() if p in pages},
            "observations": OBS_REL, "tavily_calls": len(pages) if fetch else 0}
