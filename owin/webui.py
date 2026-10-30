"""The product UI: static files in owin/web/, plus two read-only JSON helpers it binds to.

GET /                 ->  owin/web/index.html (the answer screen; binds to /api/pack)
GET /app.css, /app.js ->  static assets (also /theme-c1.css, the look)
GET /api/catalog      ->  the features an endpoint can be switched to (the "change one input" control)
GET /api/watch        ->  per vendor page: what Owin can watch on it, from data/datause/observations.json
GET /about            ->  owin/web/about.html (the product page; /about.css, /about.js, its stills and loops under /img/)

No keys, no network: everything here reads committed files. The UI never sees a secret.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
WEB = Path(__file__).resolve().parent / "web"
STATIC = {"/": ("about.html", "text/html; charset=utf-8"),
          "/app": ("index.html", "text/html; charset=utf-8"),
          "/app.css": ("app.css", "text/css; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/judge": ("judge.html", "text/html; charset=utf-8"),
          "/judge.js": ("judge.js", "text/javascript; charset=utf-8"),
          "/about": ("about.html", "text/html; charset=utf-8"),
          "/about.css": ("about.css", "text/css; charset=utf-8"),
          "/about.js": ("about.js", "text/javascript; charset=utf-8"),
          "/theme-c1.css": ("theme-c1.css", "text/css; charset=utf-8")}
# The product page's stills and background loops, served as bytes. The allowlist is the files in owin/web/img/ whose
# names match, read once at import, so a request path is only ever looked up, never joined onto the filesystem.
IMAGE_TYPES = {".avif": "image/avif", ".webp": "image/webp", ".mp4": "video/mp4",
               ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon"}  # the last three: logo and icons
IMAGES = {f"/img/{f.name}": (f"img/{f.name}", IMAGE_TYPES[f.suffix])
          for f in sorted((WEB / "img").glob("*")) if f.suffix in IMAGE_TYPES and re.fullmatch(r"[a-z0-9-]+\.(avif|webp|mp4|png|svg|ico)", f.name)}
DOCS = {"/README.md": "README.md", "/FACTS.md": "FACTS.md"}  # repo-root docs, served read-only as plain text
ET = ZoneInfo("America/New_York")


def static(path: str) -> tuple[int, str, str | bytes] | None:
    if path in IMAGES:
        name, ctype = IMAGES[path]
        return 200, ctype, (WEB / name).read_bytes()
    if path in DOCS:
        f = ROOT / DOCS[path]
        return (200, "text/plain; charset=utf-8", f.read_text(encoding="utf-8")) if f.exists() else None
    if path not in STATIC:
        return None
    name, ctype = STATIC[path]
    return 200, ctype, (WEB / name).read_text(encoding="utf-8")


def _load(rel: str) -> dict:
    from . import config
    return json.loads(config.read_path(rel).read_text(encoding="utf-8"))


def catalog() -> dict:
    c = _load("data/datause/catalog.json")
    providers = c.get("providers", {})
    feats = [{"id": k, "provider": v["provider"], "label": v["label"], "short": v.get("short", v["label"]),
              "provider_display": (providers.get(v["provider"]) or {}).get("display", v["provider"].capitalize())
              if isinstance(providers, dict) else v["provider"].capitalize()}
             for k, v in c["features"].items()]
    return {"type": "owin.catalog", "features": feats}


def _local(iso: str | None) -> str | None:
    if not iso:
        return None
    t = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ET)
    return t.strftime("%Y-%m-%d %H:%M ") + (t.tzname() or "ET")


def watch() -> dict:
    """What Owin can diff on each page. Rules read structured observation fields only.

    - unreachable: no trusted capture of the page exists.
    - not_watchable: the latest trusted capture has nothing stable to compare (a list page without an
      entity snapshot, or a terms page whose quotes were never checked and whose text length is unknown).
    - held_copy: the latest fetch was held (for example Tavily served an older "Last updated"); the last
      trusted capture is used instead.
    - watching: otherwise. `first_copy` is true while only one trusted capture exists.
    """
    c = _load("data/datause/catalog.json")
    obs = _load("data/datause/observations.json").get("pages", {})
    out = []
    for pid, page in c["pages"].items():
        po = (obs.get(pid) or {}).get("observations", [])
        good = [o for o in po if not o.get("held")]
        latest_any = po[-1] if po else None
        latest = good[-1] if good else None
        if latest is None:
            status, note = "unreachable", "No copy of this page has been fetched yet."
        elif page["kind"] == "subprocessor_list" and not latest.get("snapshot"):
            status, note = "not_watchable", "We can't diff this page (no stable text)."
        elif page["kind"] != "subprocessor_list" and not latest.get("quotes_present") and not latest.get("chars"):
            status, note = "not_watchable", "We can't diff this page (no stable text)."
        elif latest_any is not latest and latest_any.get("held"):
            status = "held_copy"
            note = (f"The latest fetch served an older copy (“Last updated {latest_any.get('last_updated')}”). "
                    f"Owin set it aside and keeps the {latest.get('last_updated') or 'previous'} copy.")
        else:
            status, note = "watching", None
        out.append({"page": pid, "url": page["url"], "label": page["label"], "kind": page["kind"],
                    "provider": page["provider"], "status": status, "note": note,
                    "first_copy": len(good) == 1,
                    "last_checked": latest_any and latest_any.get("observed_at"),
                    "last_checked_local": _local(latest_any and latest_any.get("observed_at")),
                    "trusted_at": latest and latest.get("observed_at"),
                    "trusted_last_updated": latest and latest.get("last_updated")})
    return {"type": "owin.watch", "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pages": out}
