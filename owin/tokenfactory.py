"""Minimal Nebius Token Factory client (OpenAI-compatible chat completions).

The API key is read at call time from TOKEN_FACTORY_API_KEY, or from the file
named by OWIN_ENV_FILE (default: ../.env next to the repo). It is never logged,
printed or written. Every call appends one usage line to ledger/usage.jsonl.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = os.environ.get("OWIN_TF_URL", "https://api.tokenfactory.nebius.com/v1/chat/completions")
SUPER = "nvidia/nemotron-3-super-120b-a12b"
ULTRA = "nvidia/Nemotron-3-Ultra-550b-a55b"
# USD per million input/output tokens (Token Factory list prices used in the S2 spike, 2026-10-21).
PRICE = {SUPER: (0.30, 0.90), ULTRA: (1.00, 3.00)}
LEDGER = Path(os.environ.get("OWIN_LEDGER", ROOT / "ledger" / "usage.jsonl"))


class MissingKey(RuntimeError):
    pass


def api_key() -> str:
    k = os.environ.get("TOKEN_FACTORY_API_KEY")
    if k:
        return k
    env = Path(os.environ.get("OWIN_ENV_FILE", ROOT.parent / ".env"))
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("TOKEN_FACTORY_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise MissingKey("TOKEN_FACTORY_API_KEY not set (env or OWIN_ENV_FILE)")


@dataclass
class Completion:
    model: str
    content: str
    finish_reason: str | None
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    cost_usd: float
    error: str | None = None
    reasoning_tokens: int = 0  # part of completion_tokens the model spent thinking (usage.completion_tokens_details)
    attempts: int = 1


def cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pi, po = PRICE.get(model, (0.0, 0.0))
    return prompt_tokens / 1e6 * pi + completion_tokens / 1e6 * po


RETRIABLE = (429, 500, 502, 503, 504, 529)  # 529: Token Factory 'overloaded' (seen 2026-10-29)
MAX_RETRY_AFTER_S = 30.0

# Circuit breaker for callers on a request path (POST /api/recheck): after BREAKER_FAILURES consecutive failed
# calls, `available()` is False for BREAKER_OPEN_S, so a judge's click does not wait on an outage it cannot fix.
# Batch commands (eval, job) ignore it; every call, batch or not, updates it.
BREAKER_FAILURES = 3
BREAKER_OPEN_S = 120.0
_breaker = {"failures": 0, "open_until": 0.0}
_breaker_lock = threading.Lock()


def available(now: float | None = None) -> bool:
    with _breaker_lock:
        return (time.time() if now is None else now) >= _breaker["open_until"]


def _record(ok: bool) -> None:
    with _breaker_lock:
        if ok:
            _breaker.update(failures=0, open_until=0.0)
            return
        _breaker["failures"] += 1
        if _breaker["failures"] >= BREAKER_FAILURES:
            _breaker["open_until"] = time.time() + BREAKER_OPEN_S


def reset_breaker() -> None:
    with _breaker_lock:
        _breaker.update(failures=0, open_until=0.0)


def _retry_after(e: urllib.error.HTTPError) -> float | None:
    try:
        v = float((e.headers or {}).get("Retry-After"))
    except (TypeError, ValueError):
        return None
    return max(0.0, min(v, MAX_RETRY_AFTER_S))


def chat(prompt: str, *, model: str = SUPER, purpose: str = "", temperature: float = 0.2,
         max_tokens: int = 8000, timeout: float = 600, attempts: int = 3, thinking: bool | None = None) -> Completion:
    """One chat completion. `timeout` is per attempt; `attempts` counts every try (retries only on 429/5xx,
    timeouts and resets), honouring Retry-After (capped at 30 s) and never sleeping after the last attempt.
    `thinking=False` turns Nemotron's reasoning off (`chat_template_kwargs.enable_thinking`); None keeps the
    model default (on), which every recorded headline run used."""
    body = {"model": model, "temperature": temperature, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]}
    if thinking is not None:
        body["chat_template_kwargs"] = {"enable_thinking": bool(thinking)}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + api_key(), "Content-Type": "application/json"})
    t0 = time.time()
    data, err, n = None, None, 0
    for attempt in range(max(1, attempts)):
        n = attempt + 1
        wait = 4.0 * (attempt + 1)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.load(r)
            err = None
            break
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}"
            if e.code not in RETRIABLE:
                break
            wait = _retry_after(e) if _retry_after(e) is not None else wait
        except Exception as e:  # timeouts, resets
            err = type(e).__name__
        if attempt + 1 < attempts:
            time.sleep(wait)
    latency = round(time.time() - t0, 2)
    if data is None:
        c = Completion(model, "", None, 0, 0, latency, 0.0, err, attempts=n)
    else:
        u = data.get("usage") or {}
        pt, ct = int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0)
        rt = int(((u.get("completion_tokens_details") or {}).get("reasoning_tokens")) or 0)
        ch = data["choices"][0]
        c = Completion(model, ch["message"].get("content") or "", ch.get("finish_reason"),
                       pt, ct, latency, round(cost(model, pt, ct), 6), reasoning_tokens=rt, attempts=n)
    _record(c.error is None)
    _log(c, purpose, thinking)
    return c


def _log(c: Completion, purpose: str, thinking: bool | None = None) -> None:
    extra = {"reasoning_tokens": c.reasoning_tokens, "attempts": c.attempts}
    if thinking is not None:
        extra["thinking"] = thinking
    log_usage(purpose, model=c.model, prompt_tokens=c.prompt_tokens, completion_tokens=c.completion_tokens,
              cost_usd=c.cost_usd, latency_s=c.latency_s, error=c.error, **extra)


def log_usage(purpose: str, *, model: str, latency_s: float, error: str | None = None, cost_usd: float = 0.0,
              prompt_tokens: int = 0, completion_tokens: int = 0, **extra) -> None:
    """One line per paid call (Token Factory, or a Tavily call made at request time), never a key or page text."""
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "purpose": purpose, "model": model,
                            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                            "cost_usd": cost_usd, "latency_s": latency_s, "error": error, **extra}) + "\n")


def ledger_total() -> float:
    """Every dollar the ledger records (the lifetime cap that `owin eval run` and `owin pack extract` check)."""
    if not LEDGER.exists():
        return 0.0
    return round(sum(json.loads(l)["cost_usd"] for l in LEDGER.read_text().splitlines() if l.strip()), 6)


def spent_today(prefix: str = "", now: float | None = None) -> float:
    """Token Factory dollars recorded in the current UTC day, optionally only for purposes starting with `prefix`:
    the daily cap that the scheduled job (`owin job daily`) and the live recheck path check. A cumulative total
    would make a scheduled job stop for good once the project's lifetime spend reached its cap."""
    if not LEDGER.exists():
        return 0.0
    from datetime import datetime, timezone
    day = datetime.fromtimestamp(time.time() if now is None else now, timezone.utc).date()
    total = 0.0
    for line in LEDGER.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        try:
            ts = datetime.strptime(r["ts"], "%Y-%m-%dT%H:%M:%S%z")
        except (KeyError, ValueError):
            continue
        if ts.astimezone(timezone.utc).date() == day and str(r.get("purpose", "")).startswith(prefix):
            total += float(r.get("cost_usd") or 0.0)
    return round(total, 6)
