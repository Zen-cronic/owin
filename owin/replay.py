"""The seeded real replay: OpenAI's sub-processor list, 2026-06-02 vs 2026-10-14 (both Wayback captures).

Labelled as a real historical change. The demo company is fictional and labelled too.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from . import decide, drafts, terms as terms_reg
from .entities import Snapshot

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "fixtures" / "snapshots"
COMPANY = ROOT / "fixtures" / "demo" / "company.json"

REPLAYS = {
    "openai-2026-10-14": {
        "vendor": "openai",
        "before": "openai-list-20260708.json",
        "after": "openai-list-20261021.json",
        "label": ("REAL HISTORICAL CHANGE: OpenAI sub-processor list, 'Last updated June 2, 2026' (Wayback capture "
                  "2026-07-08) vs 'Last updated October 14, 2026' (Wayback capture 2026-10-21). Demo company is fictional."),
    },
}


_WORDS = {1: "one", 2: "two", 3: "three", 5: "five", 7: "seven", 10: "ten", 14: "fourteen", 15: "fifteen", 20: "twenty",
          30: "thirty", 45: "forty-five", 60: "sixty", 90: "ninety"}


def load_company(promise_days: int | None = None) -> dict:
    c = json.loads(COMPANY.read_text())
    own = c["own_dpa"]
    if promise_days is not None:
        own["notice_days"] = promise_days
    n = own["notice_days"]
    own["promise_quote"] = own["promise_template"].format(words=_WORDS.get(n, str(n)), n=n)
    return c


def load_snapshot(name: str) -> Snapshot:
    return Snapshot.from_dict(json.loads((SNAP / name).read_text()))


def run(replay_id: str = "openai-2026-10-14", *, as_of: datetime | None = None, promise_days: int | None = None,
        terms_override: dict | None = None, after_override: Snapshot | None = None, decision: str | None = None,
        decided_by: dict | None = None, company: dict | None = None) -> dict:
    spec = REPLAYS[replay_id]
    company = company or load_company(promise_days)
    before = load_snapshot(spec["before"])
    after = after_override or load_snapshot(spec["after"])
    vcfg = next(v for v in company["vendors"] if v["vendor"] == spec["vendor"])
    entry = terms_override or terms_reg.load(spec["vendor"])
    # Default "as of" = when the after snapshot was taken, so the replay is deterministic.
    as_of = as_of or datetime.fromisoformat(after.retrieved.replace("Z", "+00:00"))
    ev = decide.evaluate(company, vcfg, entry, before, after, as_of, promise_days=promise_days)
    ev["replay"] = {"id": replay_id, "label": spec["label"], "company_label": company.get("_label")}
    today = as_of.astimezone(timezone.utc).date()
    ev["drafts"] = drafts.build_all(ev, company, today)
    if ev["drafts"]:
        ev["workflow_state"] = "drafted"
    if decision:
        promise = company["own_dpa"]["promise_quote"]
        rec = decide.decision_record(ev, decision, decided_by or {"name": company["owner"]["name"], "role": company["owner"]["role"]},
                                     as_of, your_promise_quote=promise)
        ev["decision_record"] = rec
        ev["workflow_state"] = decision
    return ev
