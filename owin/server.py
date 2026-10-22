"""Minimal JSON API and unstyled debug page. The real UI is designed separately (docs/design/).

GET /api/replay?promise_days=10&as_of=now&decision=accepted  ->  replay event JSON (docs/CONTRACT.md)
GET /api/score                                                ->  measurement headline (recomputed)
GET /                                                         ->  debug page
Stateless per request, on a ThreadingHTTPServer, so concurrent judges do not block each other.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import evaluate, replay

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
    if path == "/":
        return 200, "text/html; charset=utf-8", PAGE
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
    if path == "/api/score":
        res = evaluate.score(evaluate.headline_runs())
        return 200, "application/json", json.dumps({k: res[k] for k in ("headline", "per_successful_run", "quotes_rechecked_against_source")})
    return 404, "application/json", json.dumps({"error": "not found"})


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        code, ctype, body = handle(u.path, parse_qs(u.query))
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):  # access log without query strings
        pass


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    ThreadingHTTPServer((host, port), Handler).serve_forever()
