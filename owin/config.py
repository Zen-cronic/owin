"""Runtime configuration, from environment variables only (the container contract in DEPLOY.md).

  TOKEN_FACTORY_API_KEY  Nebius Token Factory key. New extractions (`owin pack extract`, `owin eval run`, `owin job daily`)
                         and, on a served endpoint, Nemotron re-reading inside `POST /api/recheck` when a quoted
                         sentence is gone (OWIN_RECHECK_READ_BUDGET_USD per UTC day, default $0.25).
  TAVILY_API_KEY         Tavily key. Needed for re-fetching pages (`owin pack refresh`, `owin sweep --live`, `owin job daily`)
                         and, on a served endpoint, for `POST /api/recheck` (capped; owin/recheck.py).
  OWIN_STATE_DIR         Optional writable directory (a mounted bucket in production). When set, refreshed
                         observations and list snapshots are written there and read from there first; the
                         committed files under data/ and fixtures/snapshots/ are the fallback. Unset: the app
                         serves the committed, recorded state only.
  OWIN_REFETCH_SCHEDULE  Scheduled re-fetch of the watched vendor pages inside `owin serve` (owin/refetch.py): off,
                         an interval (6h, 30m) or daily@HH:MM UTC. Default daily@06:00 with a Tavily key, else off.
  PORT / OWIN_HOST       Where `owin serve` binds (defaults 8787 / 127.0.0.1; the image sets 0.0.0.0:8080).

Serving a page never calls a paid API: every page and every GET is computed from recorded runs and committed
captures, so the app works with no keys at all (demo mode) and several people can use it at once. The one
exception is `POST /api/recheck`, which makes one Tavily call per request when a key is set, and three Nemotron
readings when a quoted sentence is gone and a Token Factory key is set. Outside requests, the scheduled re-fetch
(OWIN_REFETCH_SCHEDULE) makes the same Tavily `extract` calls, one per watched page per run.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def state_dir() -> Path | None:
    v = os.environ.get("OWIN_STATE_DIR")
    return Path(v) if v else None


def read_path(rel: str) -> Path:
    """The state-dir copy of a repo-relative file when one exists, else the committed file."""
    sd = state_dir()
    if sd is not None and (sd / rel).exists():
        return sd / rel
    return ROOT / rel


def write_path(rel: str) -> Path:
    sd = state_dir()
    p = (sd / rel) if sd is not None else (ROOT / rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write_atomic(rel: str, text: str) -> Path:
    """Write via a temp file and rename, so a reader (a judge's request) never sees half a file."""
    p = write_path(rel)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=f".{p.name}.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, p)
    return p


def keys_present() -> dict[str, bool]:
    """Which keys are available, by the same rule the clients use (environment, else the
    OWIN_ENV_FILE / ../.env line). Never returns a value."""
    names = ("TOKEN_FACTORY_API_KEY", "TAVILY_API_KEY")
    found = {k: bool(os.environ.get(k)) for k in names}
    env = Path(os.environ.get("OWIN_ENV_FILE", ROOT.parent / ".env"))
    if env.is_file():
        for line in env.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() in names and value.strip():
                found[key.strip()] = True
    return found


def mode() -> str:
    """'demo' = no keys: recorded runs and committed captures only. 'live' = keys present for refresh jobs."""
    return "live" if any(keys_present().values()) else "demo"
