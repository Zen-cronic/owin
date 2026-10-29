"""Recheck one endpoint's vendor page now: the one sponsor call a visitor can trigger.

`POST /api/recheck {"endpoint": "/api/crm-sync"}` and `owin recheck /api/crm-sync` both run `run()`:

1. With a Tavily key: one `extract` (basic depth) of the page that documents the endpoint's feature. If that copy
   would mark a quoted sentence gone that the last trusted capture still had, one re-fetch at advanced depth
   (the same caution as the sweep's stale-source rule: never trust a worse copy at first sight); the copy with
   more of the quoted sentences wins.
2. The observation (time, hash, which quoted sentences are present) is appended to the page's evidence history:
   the state dir when OWIN_STATE_DIR is set, else this process's memory.
3. The pack is rebuilt through the same rules as every other request (owin/datause/pack.py), and the endpoint's
   state is reported. No new rule, no new parser, no page text kept.

Without a key the call answers `{"ok": false, "mode": "demo"}` and makes no request.
Guards: a per-process daily cap (OWIN_RECHECK_DAILY_CAP, default 200), a 60 s cooldown per endpoint, one ledger
line per Tavily call (ledger/usage.jsonl, the same file as the Token Factory calls).
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

from . import tavily, tokenfactory as tf
from .datause import observations as obsmod, pack, registry
from .textnorm import sha256

COOLDOWN_S = 60
DEFAULT_DAILY_CAP = 200
# Tavily bills `extract` per request for up to five URLs: 1 credit at basic depth, 2 at advanced.
CREDITS = {"basic": 1, "advanced": 2}
METHOD = "tavily extract (no query, extract_depth={depth}, format=markdown) via POST /api/recheck"

_lock = threading.Lock()
_calls = {"day": None, "n": 0}
_last_by_endpoint: dict[str, float] = {}


def daily_cap() -> int:
    try:
        return max(0, int(os.environ.get("OWIN_RECHECK_DAILY_CAP", DEFAULT_DAILY_CAP)))
    except ValueError:
        return DEFAULT_DAILY_CAP


def reset() -> None:
    """Forget the per-process counters and the in-memory observations (tests)."""
    with _lock:
        _calls.update({"day": None, "n": 0})
        _last_by_endpoint.clear()
    obsmod.clear_live()


def resolve(endpoint: str, manifest: dict | None = None) -> dict:
    """The endpoint's feature, the page it is documented on and that page's URL, from the committed catalog."""
    m = manifest or pack.load_demo()
    ep = next((e for e in m["endpoints"] if e.get("path") == endpoint), None)
    if ep is None:
        raise KeyError(f"no endpoint {endpoint!r} in the stack; known: {[e['path'] for e in m['endpoints']]}")
    cat = registry.load_catalog()
    feat = cat["features"].get(ep["feature"])
    if feat is None:
        raise KeyError(f"unknown feature id {ep['feature']!r} for {endpoint}")
    page = feat["page"]
    return {"endpoint": endpoint, "feature": ep["feature"], "page": page, "url": cat["pages"][page]["url"],
            "manifest": m}


def _guard(endpoint: str, now: float) -> tuple[int, dict] | None:
    """The daily cap and the per-endpoint cooldown. Counts a call only when it is allowed."""
    day = time.strftime("%Y-%m-%d", time.gmtime(now))
    with _lock:
        if _calls["day"] != day:
            _calls.update({"day": day, "n": 0})
        if _calls["n"] >= daily_cap():
            return 429, {"ok": False, "mode": "live",
                         "reason": f"daily cap reached ({daily_cap()} rechecks per day on this server); try again tomorrow"}
        since = now - _last_by_endpoint.get(endpoint, -1e9)
        if since < COOLDOWN_S:
            wait = int(COOLDOWN_S - since) + 1
            return 429, {"ok": False, "mode": "live", "retry_after_s": wait,
                         "reason": f"{endpoint} was rechecked {int(since)} s ago; wait {wait} s"}
        _calls["n"] += 1
        _last_by_endpoint[endpoint] = now
    return None


def _present(o: dict) -> tuple[int, int]:
    qp = o.get("quotes_present") or {}
    return sum(1 for v in qp.values() if v), len(qp)


def _observe(page: str, url: str, f: tavily.Fetched, depth: str) -> dict:
    rec = {"fetched_at": f.retrieved, "method": METHOD.format(depth=depth), "url": url,
           "sha256": sha256(f.content), "chars": len(f.content)}
    return {**obsmod._datause_obs(page, rec, f.content, "tavily"), "depth": depth, "latency_s": f.latency_s}


def _endpoint_cells(p: dict, endpoint: str) -> dict[str, dict]:
    out = {}
    for a in p["answers"]:
        c = next((c for c in a["cells"] if c["endpoint"] == endpoint), None)
        if c is not None:
            out[a["id"]] = {"verdict": c["verdict"], "stale": bool(c.get("stale")), "presence": c.get("quote_presence"),
                            "value": c["value_label"], "badge": a["badge"]}
    return out


def _state(cells: dict[str, dict]) -> str:
    """The endpoint's own state: the most severe of its cells, in the pack's badge vocabulary."""
    states = set()
    for c in cells.values():
        if c["verdict"] == "contradicts":
            states.add("not_true")
        if c["stale"]:
            states.add("stale")
        if c["verdict"] == "confirm":
            states.add("confirm")
        if c["verdict"] == "held":
            states.add("held_unspecified")
    return next((s for s in pack.SEVERITY if s in states), "still_true")


def _day(ts: str | None) -> str:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%b %-d") if ts else "?"


def _sentence(prev: dict | None, o: dict) -> str:
    n, total = _present(o)
    every = "the quoted sentence is" if total == 1 else f"all {total} quoted sentences are"
    some = f"{n} of {total} quoted sentences"
    if prev is None:
        return f"First capture of this page; {some} on it."
    when = _day(prev.get("observed_at"))
    if prev.get("sha256") == o.get("sha256"):
        return f"Page unchanged since {when}; " + (f"{every} still on it." if n == total else f"{some} on it.")
    if n == total:
        return f"Page text differs from the {when} capture; {every} still on it."
    gone = "the quoted sentence is" if total == 1 else f"{total - n} of {total} quoted sentences are"
    return f"Page changed since {when}; {gone} no longer on it."


def run(endpoint: str, *, manifest: dict | None = None, now: float | None = None, fetch=None) -> tuple[int, dict]:
    """(HTTP status, body). `fetch(url, depth)` defaults to tavily.extract; tests pass a stub."""
    now = time.time() if now is None else now
    try:
        r = resolve(endpoint, manifest)
    except KeyError as e:
        return 400, {"ok": False, "error": str(e)}
    if not tavily.api_key():
        return 200, {"ok": False, "mode": "demo", "reason": "no key on this server"}
    if (g := _guard(endpoint, now)) is not None:
        return g
    fetch = fetch or (lambda url, depth: tavily.extract(url, depth=depth))
    page, url = r["page"], r["url"]
    obs_before = obsmod.load()
    po = (obs_before["pages"].get(page) or {}).get("observations", [])
    prev = next((o for o in reversed(po) if not o.get("held")), None)
    t0 = time.time()
    credits, error, o = 0, None, None
    f = fetch(url, "basic")
    credits += CREDITS["basic"]
    if f.content:
        o = _observe(page, url, f, "basic")
        lost = [q for q, v in (prev or {}).get("quotes_present", {}).items() if v and not o["quotes_present"].get(q)]
        if lost:  # a worse copy at first sight: look once more, harder, before recording the loss
            g2 = fetch(url, "advanced")
            credits += CREDITS["advanced"]
            if g2.content:
                o2 = _observe(page, url, g2, "advanced")
                if _present(o2)[0] >= _present(o)[0]:
                    o = o2
    else:
        error = f.error or "tavily returned no content"
    tf.log_usage(f"recheck:{endpoint}", model="tavily/extract", latency_s=round(time.time() - t0, 2), error=error,
                 credits=credits, page=page)
    if o is None:
        return 502, {"ok": False, "mode": "live", "reason": error, "credits_used": credits, "endpoint": endpoint, "page": page}
    before = _endpoint_cells(pack.build(r["manifest"], obs=obs_before), endpoint)
    obsmod.append_live(page, o)
    after = _endpoint_cells(pack.build(r["manifest"]), endpoint)
    return 200, {"ok": True, "mode": "live", "checked_at": o["observed_at"], "changed": before != after,
                 "state": _state(after), "observation": _sentence(prev, o), "credits_used": credits,
                 "endpoint": endpoint, "feature": r["feature"], "page": page, "source_url": url,
                 "page_seen_before": prev.get("observed_at") if prev else None, "depth": o["depth"],
                 "stored": "state_dir" if obsmod.live_persisted() else "process",
                 "answers": {q: {"badge": c["badge"], "verdict": c["verdict"]} for q, c in after.items()}}
