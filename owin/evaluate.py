"""Measurement harness: the README's line-one number.

`run`   calls Nemotron on every corpus item N times and records each call (no source text) in eval/runs/.
`score` recomputes quality / latency / cost per successful run from a recorded run file. It needs no
        API key. If fixtures/raw/ is present it re-checks every quote against the source; otherwise it
        uses the recorded verbatim result and says so.
"""
from __future__ import annotations

import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from . import baseline, tokenfactory as tf
from .extract import extract, validate
from .schema import SCORED_FIELDS, WindowTerms
from .textnorm import sha256

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "eval" / "corpus.json"
RUNS = ROOT / "eval" / "runs"


def load_corpus() -> list[dict]:
    return json.loads(CORPUS.read_text())["items"]


def _source(item: dict) -> str | None:
    p = ROOT / item["file"]
    return p.read_text() if p.exists() else None


def run(runs: int = 3, model: str = tf.SUPER, only: list[str] | None = None, workers: int = 6) -> Path:
    items = [i for i in load_corpus() if only is None or i["id"] in only]
    missing = [i["id"] for i in items if _source(i) is None]
    if missing:
        raise SystemExit(f"missing fixtures for {missing}; see fixtures/manifest.json for URLs")
    jobs = [(i, k) for i in items for k in range(runs)]

    def one(job):
        item, k = job
        e = extract(item["id"], _source(item), model=model, purpose="eval")
        return {"id": item["id"], "run": k, **asdict(e)}

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        calls = list(ex.map(one, jobs))
    out = {"run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "model": model, "runs_per_item": runs,
           "wall_s": round(time.time() - t0, 1), "corpus_sha256": sha256(CORPUS.read_text()), "calls": calls}
    RUNS.mkdir(parents=True, exist_ok=True)
    path = RUNS / f"{time.strftime('%Y%m%dT%H%M%S')}-{model.split('/')[-1]}.json"
    path.write_text(json.dumps(out, indent=1))
    return path


def is_exact(terms: dict | None, gold: dict) -> bool:
    if not terms:
        return False
    if any(terms.get(k) != gold[k] for k in SCORED_FIELDS):
        return False
    if gold["window_type"] == "none":
        return terms.get("status") == "held"
    return bool(terms.get("quote_verbatim"))


def _recheck(terms: dict | None, source: str | None) -> dict | None:
    if not terms or source is None:
        return terms
    t = WindowTerms(**{k: terms[k] for k in WindowTerms.__dataclass_fields__ if k in terms})
    return validate(t, source).to_dict()


def _p95(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(0.95 * (len(xs) - 1)))] if xs else 0.0


def score(path: Path | Sequence[Path] | None = None) -> dict:
    """Score one recorded run file, or several merged (e.g. the tuned set and the held-out set)."""
    paths = [path] if isinstance(path, (str, Path)) else list(path or [latest_run()])
    datas = [json.loads(Path(p).read_text()) for p in paths]
    data = {"run_at": ",".join(d["run_at"] for d in datas), "model": datas[0]["model"],
            "calls": [c for d in datas for c in d["calls"]]}
    path = paths[0]
    corpus = {i["id"]: i for i in load_corpus()}
    sources = {k: _source(v) for k, v in corpus.items()}
    rechecked = all(s is not None for s in sources.values())
    per: dict[str, dict] = {}
    for c in data["calls"]:
        item = corpus[c["id"]]
        terms = _recheck(c["terms"], sources.get(c["id"]))
        c["_exact"] = is_exact(terms, item["gold"])
        c["_terms"] = terms
        per.setdefault(c["id"], {"kind": item["kind"], "gold": item["gold"], "runs": []})["runs"].append(c)
    vendors = {}
    for vid, v in per.items():
        n_exact = sum(r["_exact"] for r in v["runs"])
        vals = [json.dumps({k: (r["_terms"] or {}).get(k) for k in SCORED_FIELDS}, sort_keys=True) if r["_terms"] else "ERR"
                for r in v["runs"]]
        vendors[vid] = {
            "kind": v["kind"],
            "gold_window": [v["gold"]["window_type"], v["gold"]["window_days"]],
            "runs_window": [[(r["_terms"] or {}).get("window_type"), (r["_terms"] or {}).get("window_days")] if r["_terms"] else ["ERR", r["error"]]
                            for r in v["runs"]],
            "exact_runs": n_exact,
            "n_runs": len(v["runs"]),
            "majority_exact": n_exact * 2 > len(v["runs"]),
            "consistent": len(set(vals)) == 1,
            "quote_verbatim_runs": sum(bool((r["_terms"] or {}).get("quote_verbatim")) for r in v["runs"]),
            "mismatched_fields": sorted({k for r in v["runs"] if r["_terms"] for k in SCORED_FIELDS
                                         if r["_terms"].get(k) != v["gold"][k]}),
        }
    calls = data["calls"]
    for c in calls:
        c.pop("_terms", None)
    ok = [c for c in calls if c["_exact"]]
    total_cost = sum(c["cost_usd"] for c in calls)
    lab = {k: v for k, v in vendors.items() if v["kind"] == "labelled"}
    neg = {k: v for k, v in vendors.items() if v["kind"] == "negative"}
    held = {k: v for k, v in vendors.items() if v["kind"] == "heldout"}
    base = baseline_score()
    result = {
        "run_files": [str(Path(p).resolve().relative_to(ROOT)) for p in paths],
        "run_at": data["run_at"],
        "model": data["model"],
        "quotes_rechecked_against_source": rechecked,
        "headline": {
            "labelled_vendors_exact_majority": f"{sum(v['majority_exact'] for v in lab.values())}/{len(lab)}",
            "labelled_runs_exact": f"{sum(v['exact_runs'] for v in lab.values())}/{sum(v['n_runs'] for v in lab.values())}",
            "heldout_vendors_exact_majority": f"{sum(v['majority_exact'] for v in held.values())}/{len(held)}",
            "heldout_runs_exact": f"{sum(v['exact_runs'] for v in held.values())}/{sum(v['n_runs'] for v in held.values())}",
            "negative_controls_held": f"{sum(v['exact_runs'] for v in neg.values())}/{sum(v['n_runs'] for v in neg.values())}",
            "consistent_vendors": f"{sum(v['consistent'] for v in lab.values())}/{len(lab)}",
            "baseline_regex_exact": f"{base['exact']}/{base['n']}" if base else "n/a (fixtures missing)",
            "baseline_regex_heldout_exact": f"{base['heldout_exact']}/{base['heldout']}" if base else "n/a",
            "baseline_regex_window_only_exact": (f"{sum(v['window_only_exact'] for k, v in base['vendors'].items() if corpus[k]['kind'] != 'negative')}"
                                                 f"/{base['n'] + base['heldout']}") if base else "n/a",
            "baseline_regex_negatives_held": f"{base['negatives_held']}/{base['negatives']}" if base else "n/a",
        },
        "per_successful_run": {
            "successful_runs": len(ok),
            "total_calls": len(calls),
            "mean_latency_s": round(statistics.mean(c["latency_s"] for c in ok), 2) if ok else None,
            "p95_latency_s": _p95([c["latency_s"] for c in ok]),
            "cost_per_successful_run_usd": round(total_cost / len(ok), 5) if ok else None,
            "total_cost_usd": round(total_cost, 5),
            "tokens_in": sum(c["prompt_tokens"] for c in calls),
            "tokens_out": sum(c["completion_tokens"] for c in calls),
        },
        "vendors": vendors,
        "baseline": base,
    }
    return result


def baseline_score() -> dict | None:
    out, n, exact, neg_n, neg_held, ho_n, ho_exact = {}, 0, 0, 0, 0, 0, 0
    for item in load_corpus():
        src = _source(item)
        if src is None:
            return None
        t = baseline.extract(src).to_dict()
        hit = all(t[k] == item["gold"][k] for k in SCORED_FIELDS)
        days_hit = t["window_type"] == item["gold"]["window_type"] and t["window_days"] == item["gold"]["window_days"]
        out[item["id"]] = {"window": [t["window_type"], t["window_days"]], "exact": hit, "window_only_exact": days_hit}
        if item["kind"] == "labelled":
            n += 1
            exact += hit
        elif item["kind"] == "heldout":
            ho_n += 1
            ho_exact += hit
        else:
            neg_n += 1
            neg_held += hit
    return {"n": n, "exact": exact, "negatives": neg_n, "negatives_held": neg_held, "heldout": ho_n, "heldout_exact": ho_exact, "vendors": out,
            "caveat": "rule written after reading these 10 clauses, so it is tuned to this corpus",
            "rule": "first sentence with 'object' + 'N days', else first sub-processor sentence with 'N days'"}


def headline_runs() -> list[Path]:
    """The recorded runs the README headline is computed from (eval/headline.json), else the latest run."""
    h = ROOT / "eval" / "headline.json"
    if h.exists():
        return [ROOT / f for f in json.loads(h.read_text())["run_files"]]
    return [latest_run()]


def latest_run() -> Path:
    files = sorted(RUNS.glob("*.json"))
    if not files:
        raise SystemExit("no recorded runs in eval/runs/; run `owin eval run` first")
    return files[-1]
