"""Claims ledger: every number and factual claim in README.md and the UI, with the command or file it comes from.

`owin facts write` regenerates FACTS.md from this list. `tests/test_facts.py` recomputes every fact, fails on
drift, checks that FACTS.md is current, and checks that the README and the /judge page carry each quoted text.
All facts recompute keyless from committed files (recorded runs, registry, observations).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FACTS_MD = ROOT / "FACTS.md"


@lru_cache(maxsize=None)
def _sel() -> dict:
    from .datause import selective
    return selective.report("v3fresh")


@lru_cache(maxsize=None)
def _score() -> dict:
    from .datause import evaluate as dv
    return dv.score(dv.headline_runs())


@lru_cache(maxsize=None)
def _pack(*sets: str) -> dict:
    from .datause import pack
    m = pack.load_demo()
    for s in sets:
        p, _, f = s.partition("=")
        m = pack.set_feature(m, p, f)
    return pack.build(m)


@lru_cache(maxsize=None)
def _dpa() -> dict:
    from . import evaluate
    return evaluate.score(evaluate.headline_runs())


def _json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text())


def _cell(p: dict, qid: str, ep: str) -> dict:
    a = next(a for a in p["answers"] if a["id"] == qid)
    return next(c for c in a["cells"] if c["endpoint"] == ep)


def _mean_cost() -> float:
    ps = _score()["per_successful_run"]
    return round(ps["total_cost_usd"] / ps["total_calls"], 4)


SEL = "owin eval selective --corpus datause --split v3fresh"
SCORE = "owin eval score --corpus datause --brief"
PACK = "owin pack build --format brief"

# (id, claim as written, expected value, source, compute)
FACTS = [
    ("sel.auto", "Answers Owin filled on its own on split v3fresh (every successful reading agrees, at least 2)", "27/33", SEL,
     lambda: _sel()["headline"]["auto_answered"]),
    ("sel.correct", "Correct among the auto-filled answers", "26/27", SEL, lambda: _sel()["headline"]["auto_correct"]),
    ("sel.confirm", "Answers sent to a person to confirm", 6, SEL, lambda: _sel()["headline"]["sent_to_confirm"]),
    ("sel.majority", "Confirm cells where the majority reading would have been right", "2/6", SEL,
     lambda: _sel()["headline"]["confirm_majority_right"]),
    ("sel.vendors", "AI vendors in v3fresh positives", 7, SEL, lambda: _sel()["headline"]["vendors"]),
    ("sel.items", "Features (vendor pages) in v3fresh positives", 11, SEL, lambda: _sel()["headline"]["items"]),
    ("sel.miss", "The one confident miss (self-disclosed label error, kept per pre-registration)",
     "openrouter-inference-zdr retention_days", SEL,
     lambda: " ".join((_sel()["headline"]["auto_misses"][0]["item"], _sel()["headline"]["auto_misses"][0]["field"]))),
    ("sel.neg", "Negative-control cells auto-answered correctly (page says nothing; Owin answers 'not stated')", "6/6", SEL,
     lambda: _sel()["negative_controls"]["auto_correct"]),
    ("sel.ref.v3old", "Reference, NOT clean: v3 on the older items, auto / correct", "80/90, 77/80", SEL,
     lambda: f"{_sel()['reference_not_clean']['v3_old']['auto_answered']}, {_sel()['reference_not_clean']['v3_old']['auto_correct']}"),
    ("sel.ref.v2old", "Reference, NOT clean: v2 on the older items, auto / correct", "77/90, 72/77", SEL,
     lambda: f"{_sel()['reference_not_clean']['v2_old']['auto_answered']}, {_sel()['reference_not_clean']['v2_old']['auto_correct']}"),
    ("v3.items", "Pre-registered v3 on v3fresh: items with all three fields exact (majority of runs)", "7/11", SCORE,
     lambda: _score()["headline"]["v3fresh"]["items_exact_majority"]),
    ("v3.neg", "v3fresh negatives held", "2/2", SCORE, lambda: _score()["headline"]["v3fresh"]["negative_items_held"]),
    ("v3.base", "Keyword baseline on v3fresh, items exact", "4/11", SCORE, lambda: _score()["headline"]["v3fresh"]["baseline_items_exact"]),
    ("v3.base.neg", "Keyword baseline on v3fresh, negatives held", "0/2", SCORE,
     lambda: _score()["headline"]["v3fresh"]["baseline_negatives_held"]),
    ("v3.passed", "v3 passed its pre-registered 80% bar", False, SCORE, lambda: _score()["acceptance_v3fresh"]["passed"]),
    ("v2.old", "Prompt v2 on the older 30 features (after one disclosed relabel)", "23/30", "eval/datause/v2-score.json",
     lambda: _json("eval/datause/v2-score.json")["headline"]["positive_items_exact_majority"]),
    ("v1.prereg", "Pre-registered prompt v1, first 24 features (failed)", "16/24", "eval/datause/preregistered-v1-score.json",
     lambda: _json("eval/datause/preregistered-v1-score.json")["acceptance"]["positive_items_exact"]),
    ("cost.call", "Mean Token Factory cost per reading, v3fresh (USD)", 0.0029, SCORE, _mean_cost),
    ("cost.feature", "Cost to answer one endpoint (3 readings, USD)", 0.0088, SCORE, lambda: round(3 * _score()["per_successful_run"]["total_cost_usd"] / _score()["per_successful_run"]["total_calls"], 4)),
    ("lat.mean", "Mean latency per reading, exactly-right runs (s)", 8.81, SCORE, lambda: _score()["per_successful_run"]["mean_latency_s"]),
    ("lat.p95", "p95 latency per reading (s)", 15.86, SCORE, lambda: _score()["per_successful_run"]["p95_latency_s"]),
    ("model", "Model", "nvidia/nemotron-3-super-120b-a12b", SCORE, lambda: _score()["model"]),
    ("demo.q03", "Demo: answer 3 (ZDR) is not true for /api/crm-sync", "not_true", PACK,
     lambda: next(a for a in _pack()["answers"] if a["id"] == "Q03")["badge"]),
    ("demo.quote", "Demo: the vendor sentence behind answer 3", "The MCP connector is not covered by ZDR arrangements.", PACK,
     lambda: _pack()["catch"]["quote"]),
    ("demo.q05", "Demo: answer 5 is stale", "stale", PACK, lambda: next(a for a in _pack()["answers"] if a["id"] == "Q05")["badge"]),
    ("demo.list", "OpenAI sub-processor list dates (before, after)", "June 2, 2026 -> October 14, 2026", PACK,
     lambda: (lambda e: f"{e['before']['last_updated']} -> {e['after']['last_updated']}")(
         next(a for a in _pack()["answers"] if a["id"] == "Q05")["stale_events"][0])),
    ("demo.cloudflare", "OpenAI CHANGED Cloudflare's entry (not added)", "changed", PACK,
     lambda: "changed" if "Cloudflare, Ltd." in next(a for a in _pack()["answers"] if a["id"] == "Q05")["stale_events"][0]["changed"] else "?"),
    ("demo.oai", "OpenAI ADDED OAI International", "added", PACK,
     lambda: "added" if "OAI International, Inc." in next(a for a in _pack()["answers"] if a["id"] == "Q05")["stale_events"][0]["added"] else "?"),
    ("demo.swap", "Change one input: /api/crm-sync -> Anthropic Messages makes answer 3 still true", "still_true",
     PACK + " --set /api/crm-sync=anthropic-messages",
     lambda: next(a for a in _pack("/api/crm-sync=anthropic-messages")["answers"] if a["id"] == "Q03")["badge"]),
    ("demo.thin", "Thin evidence: every vendor field for /api/crm-sync is held, none invented", "held,held,held,held",
     PACK + " --set /api/crm-sync=thin-anthropic-rate-limits",
     lambda: ",".join(_cell(_pack("/api/crm-sync=thin-anthropic-rate-limits"), q, "/api/crm-sync")["verdict"] for q in ("Q01", "Q02", "Q03", "Q04"))),
    ("demo.confirm", "Confirm example: answer 5's /api/embed cell when it calls OpenAI Responses (the v3 readings of OpenAI's page split 2 to 1 on third-party access; answer 5 itself stays Stale because OpenAI's list changed)", "confirm, 2/3",
     PACK + " --set /api/embed=openai-responses",
     lambda: (lambda c: f"{c['verdict']}, {c['confirm']['runs_agreeing']}")(_cell(_pack("/api/embed=openai-responses"), "Q05", "/api/embed"))),
    ("demo.v3", "The pack's readings use the headline's prompt version (every registry entry and live check)", "v3",
     "owin pack registry", lambda: ",".join(sorted({str(e.get("prompt_version")) for e in _json("data/datause/registry.json")["features"].values()} |
                                                  {str(e["live_check"]["prompt_version"]) for e in _json("data/datause/registry.json")["features"].values() if e.get("live_check")}))),
    ("demo.region", "Region never decides: answer 4 is held", "held_unspecified", PACK,
     lambda: next(a for a in _pack()["answers"] if a["id"] == "Q04")["badge"]),
    ("dpa.items", "Earlier subject (objection windows): DPAs exact, tuned + held-out", "10/10 + 7/7", "owin eval score --brief",
     lambda: f"{_dpa()['headline']['labelled_vendors_exact_majority']} + {_dpa()['headline']['heldout_vendors_exact_majority']}"),
]


def check() -> list[tuple[str, object, object]]:
    """Every fact whose recomputed value differs from the ledger: (id, expected, actual)."""
    bad = []
    for fid, _, expected, _, fn in FACTS:
        actual = fn()
        if actual != expected:
            bad.append((fid, expected, actual))
    return bad


def render() -> str:
    lines = ["# FACTS: the claims ledger", "",
             "Every number and factual claim in `README.md` and on the `/judge` page, with the command or file that",
             "produces it. Generated by `owin facts write` from `owin/facts.py`; `tests/test_facts.py` recomputes each",
             "value keyless from committed files and fails if any drifts. Run `owin facts check` to see the same.", "",
             "| id | claim | value | source |", "|---|---|---|---|"]
    for fid, claim, expected, source, _ in FACTS:
        v = json.dumps(expected) if not isinstance(expected, str) else expected
        lines.append(f"| `{fid}` | {claim} | **{v}** | `{source}` |")
    lines += ["", "## Qualitative claims and where they are enforced", "",
              "| claim | enforced by |", "|---|---|",
              "| Code, not the model, decides every answer; quotes and stated text are never read by a rule | `tests/test_a3_pack.py` ::test_model_and_stated_prose_cannot_change_any_badge |",
              "| An answer is auto-filled only when at least 2 readings succeeded and every successful reading agrees (an errored reading abstains); otherwise Confirm | `tests/test_selective.py` |",
              "| Every asserted value carries a verbatim sentence from the vendor's page | `owin/datause/extract.py::validate`, `tests/test_a1_datause.py` |",
              "| Region text never decides an answer | `tests/test_a3_pack.py::test_region_is_never_computed_from_vendor_free_text` |",
              "| Tavily `extract` fetches the evidence pages; an older copy is held, never used | `data/datause/observations.json`, `tests/test_ui.py::test_watch_holds_the_stale_tavily_copy_of_the_openai_list` |",
              "| Lumen Notes and its settings are fictional; vendor sentences, links and fetch times are real | `fixtures/demo/stack.json` `_label` |",
              "| Copy rules: no compliance claims, Nemotron described as open-weight, not legal advice | `tests/test_facts.py::test_copy_rules` |", ""]
    return "\n".join(lines)


def write() -> Path:
    FACTS_MD.write_text(render())
    return FACTS_MD
