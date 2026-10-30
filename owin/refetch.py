"""Scheduled re-fetch of the watched vendor pages, inside `owin serve` (no extra service, no dependency).

The schedule comes from `owin serve --refetch <schedule>` or OWIN_REFETCH_SCHEDULE:

  off           no scheduled re-fetch (the default when no Tavily key is present)
  6h, 30m, 90s  every interval, counted from the start of the previous run (minimum 1 minute)
  daily@HH:MM   once a day at HH:MM UTC (the default when a Tavily key is present: daily@06:00)

A bad value is logged and runs as `off`; it never stops the server.

Each run re-fetches every vendor page an answer quotes (catalog pages of kind `datause`) with the same per-page
Tavily calls as "Re-check this page" (owin/recheck.py `fetch_observe`: basic depth, one advanced look when a quoted
sentence seems gone, one ledger line per page) and appends the dated observation: into OWIN_STATE_DIR when it is
set, else this process's memory. It never touches recorded runs, the registry or the Nemotron readings, so the
headline numbers do not move. One run at a time; an exception is recorded in the status, never raised.
"""
from __future__ import annotations

import os
import re
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

ENV = "OWIN_REFETCH_SCHEDULE"
DEFAULT_WITH_KEY = "daily@06:00"
MIN_INTERVAL_S = 60
METHOD = "tavily extract (no query, extract_depth={depth}, format=markdown) via the scheduled re-fetch"
_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


@dataclass(frozen=True)
class Schedule:
    kind: str  # off | interval | daily
    text: str
    seconds: float = 0
    hour: int = 0
    minute: int = 0


OFF = Schedule("off", "off")


def parse(text: str) -> Schedule:
    """`off`, an interval (`6h`, `30m`, `90s`, `1d`) or `daily@HH:MM` (UTC). Raises ValueError otherwise."""
    t = (text or "").strip().lower()
    if t in ("off", "none", "0", "false", "no"):
        return OFF
    if m := re.fullmatch(r"(\d+)\s*([smhd])", t):
        secs = int(m.group(1)) * _UNITS[m.group(2)]
        if secs < MIN_INTERVAL_S:
            raise ValueError(f"interval {text!r} is shorter than the 1 minute minimum")
        return Schedule("interval", t.replace(" ", ""), seconds=secs)
    if m := re.fullmatch(r"daily@(\d{1,2}):(\d{2})", t):
        h, mi = int(m.group(1)), int(m.group(2))
        if h > 23 or mi > 59:
            raise ValueError(f"time in {text!r} is not a valid HH:MM (UTC)")
        return Schedule("daily", f"daily@{h:02d}:{mi:02d}", hour=h, minute=mi)
    raise ValueError(f"unknown re-fetch schedule {text!r}; use off, an interval like 6h or 30m, or daily@HH:MM (UTC)")


def resolve(value: str | None = None, *, key_present: bool | None = None) -> tuple[Schedule, str | None]:
    """The schedule to run and a warning (or None). Precedence: the --refetch flag, then OWIN_REFETCH_SCHEDULE,
    then daily@06:00 when a Tavily key is present, else off. A bad value runs as off with a warning."""
    if key_present is None:
        from . import config
        key_present = config.keys_present().get("TAVILY_API_KEY", False)
    raw = value if value is not None else os.environ.get(ENV)
    if raw is None or not raw.strip():
        return (parse(DEFAULT_WITH_KEY) if key_present else OFF), None
    try:
        s = parse(raw)
    except ValueError as e:
        return OFF, f"{e}; scheduled re-fetch is off"
    if s.kind != "off" and not key_present:
        return s, "no Tavily key on this server; scheduled runs will record 'no Tavily key' and make no request"
    return s, None


def next_run(s: Schedule, now: datetime, last_start: datetime | None = None) -> datetime | None:
    """When the next run is due. Interval: last start + interval (now + interval before the first run).
    daily@HH:MM: the next HH:MM UTC strictly after `now`."""
    if s.kind == "interval":
        base = last_start or now
        return base + timedelta(seconds=s.seconds)
    if s.kind == "daily":
        n = now.astimezone(timezone.utc)
        t = n.replace(hour=s.hour, minute=s.minute, second=0, microsecond=0)
        return t if t > n else t + timedelta(days=1)
    return None


def watched_pages() -> dict[str, str]:
    """Page id -> URL for every vendor page an answer quotes (the pages Re-check fetches)."""
    from .datause import registry
    return {pid: p["url"] for pid, p in sorted(registry.load_catalog()["pages"].items()) if p.get("kind") == "datause"}


def refresh_pages(fetch=None) -> dict:
    """Re-fetch every watched page once and append the observations. Returns counts and a one-line summary."""
    from . import recheck, tavily
    from .datause import observations as obsmod
    if not tavily.api_key():
        raise RuntimeError("no Tavily key on this server")
    fetch = fetch or (lambda url, depth: tavily.extract(url, depth=depth))
    pages = watched_pages()
    obs = obsmod.load()
    unchanged = changed = failed = credits = 0
    rows = {}
    for page, url in pages.items():
        po = (obs["pages"].get(page) or {}).get("observations", [])
        prev = next((o for o in reversed(po) if not o.get("held")), None)
        o, _text, c, err = recheck.fetch_observe(page, url, prev, fetch, purpose=f"refetch:{page}")
        credits += c
        if o is None:
            failed += 1
            rows[page] = f"failed: {err}"
            continue
        o["method"] = METHOD.format(depth=o.get("depth", "basic"))
        same = prev is not None and prev.get("sha256") == o.get("sha256")
        unchanged += same
        changed += not same
        rows[page] = "unchanged" if same else "changed"
        obsmod.append_live(page, o)
    summary = f"{len(pages)} pages, {unchanged} unchanged, {changed} changed" + (f", {failed} failed" if failed else "")
    return {"summary": summary, "pages": len(pages), "unchanged": unchanged, "changed": changed, "failed": failed,
            "credits_used": credits, "rows": rows, "stored": "state_dir" if obsmod.live_persisted() else "process"}


def _iso(t: datetime | None) -> str | None:
    return t.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z") if t else None


class Scheduler:
    """A daemon thread that waits for the next due time and runs `refresh` (default refresh_pages).
    `clock` and `wait` are injectable for tests; `wait(seconds)` returns True when the scheduler is stopped."""

    POLL_S = 30.0  # re-read the clock at least this often, so a suspended host does not skip a day

    def __init__(self, schedule: Schedule, *, refresh=None, clock=None, warning: str | None = None):
        self.schedule = schedule
        self.warning = warning
        self._refresh = refresh or refresh_pages
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._stop = threading.Event()
        self._run_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self.last_start: datetime | None = None
        self.last_run: datetime | None = None
        self.last_result: str | None = None
        self.last_error: bool = False
        self.runs = 0
        self.skipped = 0
        self.next: datetime | None = next_run(schedule, self._clock())
        self.thread: threading.Thread | None = None

    def tick(self) -> bool:
        """Run once now unless a run is already in progress (then skip). Never raises. True if it ran."""
        if not self._run_lock.acquire(blocking=False):
            with self._state_lock:
                self.skipped += 1
            return False
        try:
            start = self._clock()
            with self._state_lock:
                self.last_start = start
            try:
                res = self._refresh()
                text, err = (res.get("summary") if isinstance(res, dict) else str(res)), False
            except Exception as e:  # recorded, not raised: the server keeps serving
                text, err = f"error: {type(e).__name__}: {e}"[:300], True
            with self._state_lock:
                self.last_run, self.last_result, self.last_error = self._clock(), text, err
                self.runs += 1
                self.next = next_run(self.schedule, self._clock(), start)
            print(f"owin refetch: {text}", file=sys.stderr, flush=True)
            return True
        finally:
            self._run_lock.release()

    def loop(self, wait=None) -> None:
        wait = wait or self._stop.wait
        while not self._stop.is_set() and self.next is not None:
            remaining = (self.next - self._clock()).total_seconds()
            if remaining > 0:
                if wait(min(remaining, self.POLL_S)):
                    return
                continue
            self.tick()

    def start(self) -> "Scheduler":
        if self.schedule.kind != "off" and self.thread is None:
            self.thread = threading.Thread(target=self.loop, name="owin-refetch", daemon=True)
            self.thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> dict:
        with self._state_lock:
            out = {"schedule": self.schedule.text, "next_run": _iso(self.next), "last_run": _iso(self.last_run),
                   "last_result": self.last_result, "running": self._run_lock.locked()}
        if self.warning:
            out["warning"] = self.warning
        return out


_active: Scheduler | None = None


def start(value: str | None = None) -> Scheduler:
    """Resolve the schedule, log it, and start the scheduler thread (called by `owin serve`)."""
    global _active
    s, warning = resolve(value)
    if warning:
        print(f"owin refetch: {warning}", file=sys.stderr, flush=True)
    _active = Scheduler(s, warning=warning).start()
    print(f"owin refetch: schedule {s.text}" + (f", next run {_iso(_active.next)}" if _active.next else ""),
          file=sys.stderr, flush=True)
    return _active


def status() -> dict:
    """The /healthz `refetch` block. Without a running scheduler (a process that is not `owin serve`), the
    schedule this environment would run, not started."""
    if _active is not None:
        return _active.status()
    s, warning = resolve()
    out = {"schedule": s.text, "next_run": None, "last_run": None, "last_result": None, "running": False,
           "started": False}
    if warning:
        out["warning"] = warning
    return out
