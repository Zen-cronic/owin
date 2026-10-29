"""Minimal JSON API and unstyled debug page. The real UI is designed separately (docs/design/).

GET /api/replay?promise_days=10&as_of=now&decision=accepted  ->  replay event JSON (docs/CONTRACT.md)
GET /api/score                                                ->  P1 DPA measurement headline (recomputed)
GET /api/selective                                            ->  the line-one number, recomputed keyless from recorded runs
GET /judge                                                    ->  judge start page (owin/web/judge.html)
GET /README.md, /FACTS.md                                     ->  the repo's README and claims ledger, as plain text
GET /api/pack?set=/api/crm-sync=anthropic-messages&format=json|brief|share|csv|html  ->  answer pack (A3)
POST /api/pack  (body: a stack manifest, docs/CONTRACT.md)    ->  answer pack for that stack
GET /pack/print                                               ->  print-ready HTML (save as PDF)
GET /                                                         ->  the answer screen (owin/web/, owin/webui.py)
GET /api/catalog, /api/watch                                  ->  features for the swap control; per-page watch status
GET /debug                                                    ->  unstyled replay debug page
POST /api/recheck  (body: {"endpoint": "/api/crm-sync"})      ->  re-fetch that endpoint's vendor page through Tavily now
                                                                  and rerun the rules (owin/recheck.py; demo answer without a key)
GET /healthz                                                  ->  liveness + mode (demo | live), no secrets
Stateless per request, on a ThreadingHTTPServer, so concurrent judges do not block each other. The only request
that calls a paid API is POST /api/recheck: Tavily `extract` when a Tavily key is set (capped, cooled down,
ledgered), and three Nemotron Super readings on Token Factory when a quoted sentence is gone and a Token Factory
key is set (daily budget, breaker, 45 s deadline; the readings can only hand fields to a person).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import os

from . import config, evaluate, replay, webui

PAGE = """<!doctype html><meta charset="utf-8"><title>Owin debug</title>
<h1>Owin debug page (unstyled)</h1>
<p>Real historical change, fictional demo company. Change one input and the deadlines and drafts recompute.</p>
<form onsubmit="go();return false">Your promised customer notice (days): <input id=p value=30 size=3>
 As of: <select id=a><option value="">snapshot time</option><option value=now>now</option></select>
 <button>Recompute</button></form>
<h2 id=h></h2><pre id=o></pre>
<script>
async function go(){const r=await fetch('/api/replay?promise_days='+p.value+'&as_of='+a.value);const j=await r.json();
h.textContent=j.headline?j.headline.text:j.watch_state;
o.textContent=JSON.stringify({watch_state:j.watch_state,workflow_state:j.workflow_state,flags:j.flags,actions:j.actions,
 clock:j.clock,your_notice:j.your_notice,label:j.replay&&j.replay.label},null,1)+'\\n\\n'+
 (j.drafts&&j.drafts.customer_notices?j.drafts.customer_notices[0].body:'');}
go();
</script>"""


def handle(path: str, qs: dict) -> tuple[int, str, str]:
    q = {k: v[0] for k, v in qs.items()}
    if path == "/healthz":
        return 200, "application/json", json.dumps(healthz())
    if path == "/debug":
        return 200, "text/html; charset=utf-8", PAGE
    if (st := webui.static(path)) is not None:
        return st
    if path == "/api/catalog":
        return 200, "application/json", json.dumps(webui.catalog())
    if path == "/api/watch":
        return 200, "application/json", json.dumps(webui.watch())
    if path == "/api/replay":
        try:
            pd = int(q["promise_days"]) if q.get("promise_days") else None
            if pd is not None and not 0 < pd <= 365:
                raise ValueError("promise_days must be 1..365")
            as_of = datetime.now(timezone.utc) if q.get("as_of") == "now" else (
                datetime.fromisoformat(q["as_of"]) if q.get("as_of") else None)
            ev = replay.run(q.get("id", "openai-2026-10-14"), promise_days=pd, as_of=as_of, decision=q.get("decision") or None)
        except (ValueError, KeyError) as e:
            return 400, "application/json", json.dumps({"error": str(e)})
        return 200, "application/json", json.dumps(ev, default=str)
    if path in ("/api/pack", "/pack/print"):
        return pack_response(None, qs, html_default=path == "/pack/print")
    if path == "/api/selective":
        return 200, "application/json", json.dumps(selective_summary())
    if path == "/api/score":
        res = evaluate.score(evaluate.headline_runs())
        return 200, "application/json", json.dumps({k: res[k] for k in ("headline", "per_successful_run", "quotes_rechecked_against_source")})
    if path == "/api/recheck":
        return 405, "application/json", json.dumps({"error": 'POST a JSON body {"endpoint": "/api/crm-sync"}'})
    return 404, "application/json", json.dumps({"error": "not found"})


def handle_post(path: str, raw: bytes, qs: dict) -> tuple[int, str, str]:
    """POST /api/pack (a stack manifest) and POST /api/recheck ({"endpoint": ...}); everything else is 404."""
    if path not in ("/api/pack", "/api/recheck"):
        return 404, "application/json", json.dumps({"error": "not found"})
    if len(raw) > MAX_BODY:
        return 413, "application/json", json.dumps({"error": "body too large"})
    try:
        m = json.loads(raw or b"null")
    except json.JSONDecodeError:
        return 400, "application/json", json.dumps({"error": "invalid JSON"})
    if path == "/api/pack":
        if not isinstance(m, dict):
            return 400, "application/json", json.dumps({"error": "body must be a JSON stack manifest"})
        return pack_response(m, qs)
    from . import recheck
    ep = m.get("endpoint") if isinstance(m, dict) else None
    if not isinstance(ep, str) or not ep:
        return 400, "application/json", json.dumps({"error": 'body must be {"endpoint": "<endpoint path>"}'})
    code, body = recheck.run(ep)
    return code, "application/json", json.dumps(body)


def healthz() -> dict:
    """Liveness for the platform and the smoke test. Reports which keys exist, never their values."""
    from .datause import registry
    ok = bool(registry.load())
    return {"ok": ok, "mode": config.mode(), "keys": config.keys_present(),
            "state_dir": config.state_dir() is not None,
            "serving": "recorded runs and committed captures; only POST /api/recheck calls a paid API: Tavily extract when "
                       "its key is set, plus Nemotron re-reading on Token Factory when a quoted sentence is gone and its key is set"}


def selective_summary() -> dict:
    """The README's line one plus the per-item headline, cost and latency, all from recorded runs (no key)."""
    from .datause import evaluate as dv, selective
    rep = selective.report("v3fresh")
    sc = dv.score(dv.headline_runs())
    v3 = sc["headline"]["v3fresh"]
    h = rep["headline"]
    return {"type": "owin.selective", "selective": selective.brief(rep), "run_files": rep["run_files"],
            "quotes_rechecked_against_source": rep["quotes_rechecked_against_source"],
            "majority_all_cells": h["all_cells_majority_right"],
            "correct_with_sentence": h["correct_with_sentence"], "correct_not_stated": h["correct_not_stated"],
            "pages": h["pages"], "vendors_new": h["vendors_new"],
            "items_exact_majority": v3["items_exact_majority"], "negative_items_held": v3["negative_items_held"],
            "baseline_items_exact": v3["baseline_items_exact"], "model": sc["model"],
            "per_call": {"calls": sc["per_successful_run"]["total_calls"], "total_cost_usd": sc["per_successful_run"]["total_cost_usd"],
                         "mean_cost_usd": round(sc["per_successful_run"]["total_cost_usd"] / sc["per_successful_run"]["total_calls"], 5),
                         "cost_per_exact_run_usd": sc["per_successful_run"]["cost_per_successful_run_usd"],
                         "mean_latency_s_exact_runs": sc["per_successful_run"]["mean_latency_s"],
                         "p95_latency_s_exact_runs": sc["per_successful_run"]["p95_latency_s"]},
            "recompute": "owin eval selective --corpus datause --split v3fresh",
            "ladder": _ladder_brief()}


def _ladder_brief() -> dict | None:
    """The Nemotron ladder and the pre-registered Ultra escalation, recomputed from recorded runs (additive field)."""
    from .datause import ladder
    try:
        return {**ladder.brief(ladder.report()), "recompute": "owin eval ladder --corpus datause --brief"}
    except (FileNotFoundError, KeyError):
        return None


PACK_TYPES = {"json": "application/json", "brief": "application/json", "share": "application/json",
              "csv": "text/csv; charset=utf-8", "html": "text/html; charset=utf-8"}
MAX_BODY = 64_000


def pack_response(manifest: dict | None, qs: dict, *, html_default: bool = False) -> tuple[int, str, str]:
    from .datause import export, pack
    fmt = (qs.get("format") or ["html" if html_default else "json"])[0]
    if fmt not in PACK_TYPES:
        return 400, "application/json", json.dumps({"error": f"format must be one of {sorted(PACK_TYPES)}"})
    try:
        m = manifest or pack.load_demo()
        for s in qs.get("set", []):
            p, _, feat = s.partition("=")
            m = pack.set_feature(m, p, feat)
        p = pack.build(m)
    except (pack.PackError, KeyError, TypeError, ValueError) as e:
        return 400, "application/json", json.dumps({"error": str(e)})
    body = {"json": lambda: json.dumps(p, default=str), "brief": lambda: json.dumps(pack.brief(p)),
            "share": lambda: json.dumps(export.to_share(p)), "csv": lambda: export.to_csv(p),
            "html": lambda: export.to_html(p)}[fmt]()
    return 200, PACK_TYPES[fmt], body


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            code, ctype, body = 413, "application/json", json.dumps({"error": "body too large"})
        else:
            code, ctype, body = handle_post(u.path, self.rfile.read(n), parse_qs(u.query))
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        code, ctype, body = handle(u.path, parse_qs(u.query))
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Owin-Mode", config.mode())
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self):
        u = urlparse(self.path)
        code, ctype, body = handle(u.path, parse_qs(u.query))
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body.encode())))
        self.end_headers()

    def log_message(self, fmt, *args):  # access log without query strings
        pass


class Server(ThreadingHTTPServer):
    daemon_threads = True  # one thread per request; a slow client never blocks another judge
    request_queue_size = 64


def serve(host: str | None = None, port: int | None = None) -> None:
    host = host or os.environ.get("OWIN_HOST", "127.0.0.1")
    port = int(port or os.environ.get("PORT", 8787))
    Server((host, port), Handler).serve_forever()
