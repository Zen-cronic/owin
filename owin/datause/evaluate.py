"""Measurement harness for AI data-use terms per feature (`owin eval run|score|audit --corpus datause`).

`run`   calls Nemotron on each corpus item N times; records every call (no source text) in eval/datause/runs/.
`score` recomputes everything from recorded runs with no API key. With fixtures/raw/datause/ present it
        re-validates every quote against the page (after markdown stripping); otherwise it uses the
        recorded validation and says so.
`audit` writes eval/datause/label-audit.md: every label with the sentence that justifies it.
"""
from __future__ import annotations

import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from .. import tokenfactory as tf
from ..textnorm import sha256
from . import baseline
from .extract import PROMPT_VERSION, extract, validate
from .schema import LABEL_RULES, QUOTE_OF, SCORED_FIELDS, DataUseTerms

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "eval" / "datause"
CORPUS = DIR / "corpus.json"
RUNS = DIR / "runs"
HEADLINE = DIR / "headline.json"
AUDIT = DIR / "label-audit.md"
ACCEPT_POSITIVE_SHARE = 0.80
ACCEPT_NEGATIVE_SHARE = 0.75


def load_corpus() -> list[dict]:
    return json.loads(CORPUS.read_text())["items"]


def _source(item: dict) -> str | None:
    p = ROOT / item["file"]
    return p.read_text() if p.exists() else None


def run(runs: int = 3, model: str = tf.SUPER, only: list[str] | None = None, split: str | None = None,
        workers: int = 6) -> Path:
    items = [i for i in load_corpus() if (not only or i["id"] in only) and (not split or i["split"] == split)]
    missing = sorted({i["source"] for i in items if _source(i) is None})
    if missing:
        raise SystemExit(f"missing fixtures for {missing}; fetch them (see fixtures/datause-manifest.json)")

    def one(job):
        item, k = job
        e = extract(item["id"], item["vendor"], item["feature"], _source(item), model=model, purpose="eval-datause")
        return {"id": item["id"], "run": k, **asdict(e)}

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        calls = list(ex.map(one, [(i, k) for i in items for k in range(runs)]))
    out = {"run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "model": model, "runs_per_item": runs, "split": split or "all", "prompt_version": PROMPT_VERSION,
           "wall_s": round(time.time() - t0, 1), "corpus_sha256": sha256(CORPUS.read_text()), "calls": calls}
    RUNS.mkdir(parents=True, exist_ok=True)
    path = RUNS / f"{time.strftime('%Y%m%dT%H%M%S')}-{split or 'all'}-{model.split('/')[-1]}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return path


def _recheck(terms: dict | None, source: str | None) -> dict | None:
    """Re-run validation from the model's own claims (restoring any field validation withheld)."""
    if not terms or source is None:
        return terms
    raw = {k: terms[k] for k in DataUseTerms.__dataclass_fields__ if k in terms and k not in
           ("verbatim", "status", "hold_reasons", "model_claimed")}
    raw.update(terms.get("model_claimed") or {})
    return validate(DataUseTerms(**raw), source).to_dict()


def _model_raw(terms: dict | None) -> dict | None:
    if not terms:
        return None
    return {**{k: terms.get(k) for k in SCORED_FIELDS}, **(terms.get("model_claimed") or {})}


def _exact(vals: dict | None, gold: dict) -> bool:
    return bool(vals) and all(vals.get(k) == gold[k] for k in SCORED_FIELDS)


def _p95(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(0.95 * (len(xs) - 1)))] if xs else 0.0


def _frac(a: int, b: int) -> str:
    return f"{a}/{b}"


def score(paths: Path | Sequence[Path] | None = None) -> dict:
    paths = [paths] if isinstance(paths, (str, Path)) else list(paths or headline_runs())
    datas = [json.loads(Path(p).read_text()) for p in paths]
    corpus = {i["id"]: i for i in load_corpus()}
    sources = {i["id"]: _source(i) for i in corpus.values()}
    rechecked = all(s is not None for s in sources.values())
    calls = [c for d in datas for c in d["calls"] if c["id"] in corpus]
    per: dict[str, list] = {}
    for c in calls:
        it = corpus[c["id"]]
        t = _recheck(c["terms"], sources[c["id"]])
        c["_sys"] = t
        c["_exact"] = _exact(t, it["gold"])
        c["_raw_exact"] = _exact(_model_raw(t), it["gold"])
        per.setdefault(c["id"], []).append(c)
    items = {}
    for iid, rs in per.items():
        it = corpus[iid]
        n_ok = sum(r["_exact"] for r in rs)
        sysvals = [{k: (r["_sys"] or {}).get(k) for k in SCORED_FIELDS} if r["_sys"] else {"error": r["error"]} for r in rs]
        items[iid] = {
            "kind": it["kind"], "split": it["split"], "vendor": it["vendor"], "feature": it["feature"],
            "gold": it["gold"], "runs": sysvals, "exact_runs": n_ok, "n_runs": len(rs),
            "majority_exact": n_ok * 2 > len(rs),
            "raw_model_exact_runs": sum(r["_raw_exact"] for r in rs),
            "consistent": len({json.dumps(v, sort_keys=True) for v in sysvals}) == 1,
            "withheld_fields": sorted({f for r in rs if r["_sys"] for f in (r["_sys"].get("model_claimed") or {})}),
            "mismatched_fields": sorted({k for r in rs if r["_sys"] for k in SCORED_FIELDS if r["_sys"].get(k) != it["gold"][k]}),
            "third_party_runs_exact": sum(bool(r["_sys"]) and r["_sys"].get("third_party_access") == it["secondary"]["third_party_access"] for r in rs),
            "errors": [r["error"] for r in rs if r["error"]],
        }
    pos = {k: v for k, v in items.items() if v["kind"] != "negative"}
    neg = {k: v for k, v in items.items() if v["kind"] == "negative"}

    def split_line(group: dict, split: str) -> dict:
        g = {k: v for k, v in group.items() if v["split"] == split}
        return {"items_exact_majority": _frac(sum(v["majority_exact"] for v in g.values()), len(g)),
                "runs_exact": _frac(sum(v["exact_runs"] for v in g.values()), sum(v["n_runs"] for v in g.values()))}

    field_acc = {f: _frac(sum(bool(r["_sys"]) and r["_sys"].get(f) == corpus[r["id"]]["gold"][f] for r in calls if corpus[r["id"]]["kind"] != "negative"),
                          sum(corpus[r["id"]]["kind"] != "negative" for r in calls)) for f in SCORED_FIELDS}
    ok = [c for c in calls if c["_exact"]]
    total_cost = sum(c["cost_usd"] for c in calls)
    base = baseline_score(set(items))
    pos_ok = sum(v["majority_exact"] for v in pos.values())
    neg_ok = sum(v["majority_exact"] for v in neg.values())
    accept = {
        "rule": f"positive items exact (majority of runs) >= {ACCEPT_POSITIVE_SHARE:.0%} AND negative controls held >= {ACCEPT_NEGATIVE_SHARE:.0%}",
        "positive_items_exact": _frac(pos_ok, len(pos)),
        "negative_items_held": _frac(neg_ok, len(neg)),
        "passed": bool(pos) and pos_ok / len(pos) >= ACCEPT_POSITIVE_SHARE and bool(neg) and neg_ok / len(neg) >= ACCEPT_NEGATIVE_SHARE,
    }
    for c in calls:
        for k in ("_sys", "_exact", "_raw_exact"):
            c.pop(k, None)
    return {
        "corpus": "datause",
        "run_files": [str(Path(p).resolve().relative_to(ROOT)) for p in paths],
        "model": datas[0]["model"],
        "prompt_versions": sorted({d.get("prompt_version", "v1") for d in datas}),
        "quotes_rechecked_against_source": rechecked,
        "acceptance": accept,
        "headline": {
            "positive_items_exact_majority": _frac(pos_ok, len(pos)),
            "positive_runs_exact": _frac(sum(v["exact_runs"] for v in pos.values()), sum(v["n_runs"] for v in pos.values())),
            "tuned": split_line(pos, "tuned"),
            "heldout": split_line(pos, "heldout"),
            "fresh_heldout": split_line(pos, "fresh"),
            "negative_items_held": _frac(neg_ok, len(neg)),
            "negative_runs_held": _frac(sum(v["exact_runs"] for v in neg.values()), sum(v["n_runs"] for v in neg.values())),
            "raw_model_positive_runs_exact": _frac(sum(v["raw_model_exact_runs"] for v in pos.values()), sum(v["n_runs"] for v in pos.values())),
            "consistent_items": _frac(sum(v["consistent"] for v in items.values()), len(items)),
            "field_accuracy_positive_runs": field_acc,
            "baseline_positive_items_exact": _frac(base["positive_exact"], base["positives"]) if base else "n/a (fixtures missing)",
            "baseline_heldout_items_exact": _frac(base["heldout_exact"], base["heldout"]) if base else "n/a",
            "baseline_fresh_items_exact": _frac(base["fresh_exact"], base["fresh"]) if base else "n/a",
            "baseline_negatives_held": _frac(base["negatives_held"], base["negatives"]) if base else "n/a",
            "baseline_field_accuracy": base["field_accuracy"] if base else "n/a",
        },
        "per_successful_run": {
            "successful_runs": len(ok), "total_calls": len(calls),
            "errors": sum(bool(c["error"]) for c in calls),
            "mean_latency_s": round(statistics.mean(c["latency_s"] for c in ok), 2) if ok else None,
            "p95_latency_s": _p95([c["latency_s"] for c in ok]),
            "cost_per_successful_run_usd": round(total_cost / len(ok), 5) if ok else None,
            "total_cost_usd": round(total_cost, 5),
            "tokens_in": sum(c["prompt_tokens"] for c in calls), "tokens_out": sum(c["completion_tokens"] for c in calls),
        },
        "items": items,
        "baseline": base,
    }


def baseline_score(ids: set[str] | None = None) -> dict | None:
    """Baseline over the same items as the scored runs (all corpus items when ids is None)."""
    out, acc = {}, {f: 0 for f in SCORED_FIELDS}
    n = {"positives": 0, "positive_exact": 0, "heldout": 0, "heldout_exact": 0, "fresh": 0, "fresh_exact": 0,
         "negatives": 0, "negatives_held": 0}
    for it in load_corpus():
        if ids is not None and it["id"] not in ids:
            continue
        src = _source(it)
        if src is None:
            return None
        t = baseline.extract(src, it["feature"]).scored()
        hit = _exact(t, it["gold"])
        out[it["id"]] = {**t, "exact": hit}
        if it["kind"] == "negative":
            n["negatives"] += 1
            n["negatives_held"] += hit
            continue
        n["positives"] += 1
        n["positive_exact"] += hit
        if it["split"] in ("heldout", "fresh"):
            n[it["split"]] += 1
            n[f"{it['split']}_exact"] += hit
        for f in SCORED_FIELDS:
            acc[f] += t[f] == it["gold"][f]
    return {**n, "field_accuracy": {f: _frac(v, n["positives"]) for f, v in acc.items()}, "items": out,
            "rule": "keyword sentences, feature-named sentences first (see owin/datause/baseline.py)",
            "caveat": "rules written after reading the tuned split; it does not read table rows as a unit"}


def headline_runs() -> list[Path]:
    if HEADLINE.exists():
        return [ROOT / f for f in json.loads(HEADLINE.read_text())["run_files"]]
    files = sorted(RUNS.glob("*.json"))
    if not files:
        raise SystemExit("no recorded runs in eval/datause/runs/; run `owin eval run --corpus datause` first")
    return [files[-1]]


# Recorded after scoring. Labels were NOT changed after any model run; these are disclosed instead.
POST_RUN_TENSIONS = [
    ("openai-*", "OpenAI's own table has a 'Data used for training: No' column while its prose says 'unless you explicitly opt in'. "
                 "The label rule says opt_in; a model answering 'no' is giving the table's answer. Both mean 'not used by default'."),
    ("anthropic-code-execution", "Labelled 30 (container data). The page also says files that code execution creates in the Files API "
                                 "persist, and the 'until deleted -> null' rule would then give null, which is what v2 answered."),
    ("gemini-logs", "Labelled 55 (logs). The page also says datasets built from logs have no set retention; v2 answered null."),
    ("groq-batch", "Labelled excluded because batch is disabled under ZDR; Groq's table says 'Yes (feature disabled)'. The model "
                   "answers available. Judgment call."),
    ("mistral-batch, mistral-chat-completions", "opt_out rests on 'Training opt-out controls whether eligible data may be used'; "
                                                "weak evidence, the model often answers unspecified."),
]


# Labels changed AFTER a recorded model run (each item also carries label_history). Disclosed, with the pre-change
# score kept in eval/datause/v2-before-relabel-score.json.
RELABELS = [
    ("together-serverless", "used_for_training opt_in -> opt_out (2026-10-21, A3). Together: 'By default, Together stores the "
                            "prompts you send and the responses models return, and may use them for product improvements.' "
                            "Storage can be turned off (ZDR). 'Data sharing for training other models is opt-in' is a narrower "
                            "use. Rule: the broadest use that is on by default decides. The v2 prompt was not changed and the "
                            "model answered opt_in 3/3, so this item now fails: v2 drops from 24/30 to 23/30."),
]


def write_audit() -> Path:
    """Human-auditable labels: each field, its label, and the exact sentence that justifies it."""
    lines = ["# Label audit: AI data-use terms per feature", "",
             "Generated by `owin eval audit --corpus datause` from `eval/datause/corpus.json`. Every quoted sentence is",
             "verbatim in the fetched page (checked by `tests/test_a1_datause.py` when `fixtures/raw/datause/` is present).",
             "Labelled 2026-10-21 by the build agent (one labeller, not independent). An empty sentence means the page",
             "says nothing on that field, which is why the label is null or unspecified.", "", "## Rules", ""]
    lines += [f"- **{k}**: {v}" for k, v in LABEL_RULES.items()]
    for it in load_corpus():
        g, s = it["gold"], it["secondary"]
        lines += ["", f"## {it['id']} ({it['kind']}, split {it['split']})", "",
                  f"{it['vendor']}: {it['feature']}. Source: <{it['url']}>, fetched {it['fetched_at']}, text sha256 `{it['source_sha256'][:16]}`.", "",
                  "| field | label | justifying sentence (verbatim) |", "|---|---|---|"]
        rows = [("retention_days", g["retention_days"], "retention"), ("used_for_training", g["used_for_training"], "training"),
                ("zdr", g["zdr"], "zdr"), ("region (not scored)", s["region"], "region"),
                ("third_party_access (not scored)", s["third_party_access"], "third_party")]
        for name, val, ev in rows:
            sent = (it["evidence"].get(ev) or "").replace("|", "\\|")
            lines.append(f"| {name} | `{json.dumps(val, ensure_ascii=False)}` | {sent or '(page silent)'} |")
        if s.get("retention_condition"):
            lines += ["", f"Retention condition: {s['retention_condition']}."]
        if it.get("label_note"):
            lines += ["", f"Note: {it['label_note']}"]
    lines += ["", "## Labels changed after a model run", ""]
    lines += [f"- **{k}**: {v}" for k, v in RELABELS]
    lines += ["", "## Label-rule tensions found after scoring (labels unchanged)", ""]
    lines += [f"- **{k}**: {v}" for k, v in POST_RUN_TENSIONS]
    AUDIT.write_text("\n".join(lines) + "\n")
    return AUDIT
