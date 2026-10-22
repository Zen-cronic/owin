"""Minimal Nebius Token Factory client (OpenAI-compatible chat completions).

The API key is read at call time from TOKEN_FACTORY_API_KEY, or from the file
named by OWIN_ENV_FILE (default: ../.env next to the repo). It is never logged,
printed or written. Every call appends one usage line to ledger/usage.jsonl.
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


def cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pi, po = PRICE.get(model, (0.0, 0.0))
    return prompt_tokens / 1e6 * pi + completion_tokens / 1e6 * po


def chat(prompt: str, *, model: str = SUPER, purpose: str = "", temperature: float = 0.2,
         max_tokens: int = 8000, timeout: float = 600) -> Completion:
    body = {"model": model, "temperature": temperature, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + api_key(), "Content-Type": "application/json"})
    t0 = time.time()
    data, err = None, None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.load(r)
            err = None
            break
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}"
            if e.code not in (429, 500, 502, 503, 504):
                break
        except Exception as e:  # timeouts, resets
            err = type(e).__name__
        time.sleep(4 * (attempt + 1))
    latency = round(time.time() - t0, 2)
    if data is None:
        c = Completion(model, "", None, 0, 0, latency, 0.0, err)
    else:
        u = data.get("usage") or {}
        pt, ct = int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0)
        ch = data["choices"][0]
        c = Completion(model, ch["message"].get("content") or "", ch.get("finish_reason"),
                       pt, ct, latency, round(cost(model, pt, ct), 6))
    _log(c, purpose)
    return c


def _log(c: Completion, purpose: str) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "purpose": purpose, "model": c.model,
                            "prompt_tokens": c.prompt_tokens, "completion_tokens": c.completion_tokens,
                            "cost_usd": c.cost_usd, "latency_s": c.latency_s, "error": c.error}) + "\n")


def ledger_total() -> float:
    if not LEDGER.exists():
        return 0.0
    return round(sum(json.loads(l)["cost_usd"] for l in LEDGER.read_text().splitlines() if l.strip()), 6)
