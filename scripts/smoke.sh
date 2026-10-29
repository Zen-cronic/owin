#!/usr/bin/env bash
# Post-deploy smoke test: every judge-facing route answers 200 on the deployment itself (no login redirect),
# /healthz reports ok, and several judges at once are served.
# Usage: scripts/smoke.sh https://<endpoint-url>  [bearer-token, only if the endpoint was created with --auth token]
set -euo pipefail
BASE="${1:?usage: scripts/smoke.sh <base-url> [token]}"
BASE="${BASE%/}"
AUTH=()
if [ -n "${2:-}" ]; then AUTH=(-H "Authorization: Bearer $2"); fi
fail=0

check() {  # path, expected content-type prefix
  local path="$1" want="$2" out code eff ctype
  out=$(curl -sS -L --max-time 20 ${AUTH[@]+"${AUTH[@]}"} -o /dev/null -w '%{http_code} %{url_effective} %{content_type}' "$BASE$path") || { echo "FAIL $path (curl error)"; fail=1; return; }
  read -r code eff ctype <<<"$out"
  if [ "$code" != "200" ]; then echo "FAIL $path -> HTTP $code"; fail=1; return; fi
  case "$eff" in "$BASE"*) ;; *) echo "FAIL $path redirected off the deployment to $eff (login wall?)"; fail=1; return;; esac
  case "$ctype" in "$want"*) ;; *) echo "FAIL $path content-type $ctype (want $want)"; fail=1; return;; esac
  echo "ok   $path  $code  $ctype"
}

check /healthz        application/json
check /               text/html
check /judge          text/html
check /api/selective  application/json
check /api/pack       application/json
check /pack/print     text/html
check /app.js         text/javascript
check /api/catalog    application/json

# POST /api/recheck answers the contract with or without a key: 200 and a JSON body with ok and mode.
rc=$(curl -sS --max-time 60 ${AUTH[@]+"${AUTH[@]}"} -X POST -H 'Content-Type: application/json' -d '{"endpoint": "/api/crm-sync"}' "$BASE/api/recheck")
python3 - "$rc" <<'PY' || fail=1
import json, sys
r = json.loads(sys.argv[1])
assert "ok" in r and r.get("mode") in ("demo", "live"), f"recheck contract: {r}"
print(f"ok   /api/recheck mode={r['mode']} ok={r['ok']}" + (f" state={r.get('state')} credits={r.get('credits_used')}" if r["ok"] else ""))
PY

health=$(curl -sS --max-time 10 ${AUTH[@]+"${AUTH[@]}"} "$BASE/healthz")
python3 - "$health" <<'PY' || fail=1
import json, sys
h = json.loads(sys.argv[1])
assert h.get("ok") is True, f"healthz not ok: {h}"
print(f"ok   healthz mode={h.get('mode')} state_dir={h.get('state_dir')} keys={h.get('keys')}")
PY

num=$(curl -sS --max-time 20 ${AUTH[@]+"${AUTH[@]}"} "$BASE/api/selective")
python3 - "$num" <<'PY' || fail=1
import json, sys
s = json.loads(sys.argv[1])["selective"]
assert s["auto_answered"] and s["auto_correct"], s
print(f"ok   line-one number recomputed: {s['auto_answered']} auto, {s['auto_correct']} correct, {s['sent_to_confirm']} to confirm")
PY

# Several judges at once: 12 concurrent pack builds must all return 200.
codes=$(for i in $(seq 1 12); do curl -s -o /dev/null -w '%{http_code}\n' --max-time 30 ${AUTH[@]+"${AUTH[@]}"} "$BASE/api/pack?set=/api/crm-sync=anthropic-messages" & done; wait)
bad=$(printf '%s\n' "$codes" | grep -vc '^200$' || true)
if [ "$bad" != "0" ]; then echo "FAIL concurrent: $bad of 12 not 200"; fail=1; else echo "ok   12 concurrent /api/pack requests all 200"; fi

if [ "$fail" = 0 ]; then echo "SMOKE PASS $BASE"; else echo "SMOKE FAIL $BASE"; exit 1; fi
