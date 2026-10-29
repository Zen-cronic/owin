"""Feature terms registry for the answer pack: data/datause/registry.json.

Each feature's DataUseTerms come from recorded Nemotron runs, never from a hand-typed value:
- a feature in the scored A1 corpus uses the consensus of the A1 headline run (`origin: a1_recorded`, measured);
- a feature outside the corpus uses a Tavily-fed extraction run (`origin: tavily_extraction`, measured=false).
Every feature in the demo stack is also re-extracted from its Tavily capture (`live_check`). When that
live check disagrees with the recorded value on a field, the answer pack holds that field.

Selective answering (`field_agreement`): per answer field that a rule reads, the pack auto-answers only when
at least 2 runs succeeded and every successful run agrees (an errored run abstains; owin/datause/selective.py). The runs used are the 3 on the latest capture of the page
(the Tavily live check) when they exist, else the recorded A1 runs. A unanimous live value that differs from
the recorded value is also a disagreement. Anything else is `confirm`: held for a person, with each value
and its quote.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from .. import config, tokenfactory as tf
from ..textnorm import sha256
from . import evaluate as dv
from .extract import PROMPT_VERSION, extract
from .schema import QUOTE_OF, SCORED_FIELDS
from .selective import agreement

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "datause"
CATALOG = DATA / "catalog.json"
REGISTRY = DATA / "registry.json"
LIVE_RUNS = ROOT / "eval" / "datause" / "registry-runs"
TAVILY_RAW = ROOT / "fixtures" / "raw" / "datause-tavily"
ANSWER_FIELDS = tuple(QUOTE_OF)  # retention_days, used_for_training, zdr, region, third_party_access
UNSCORED_ANSWER_FIELDS = ("region", "third_party_access")
# Fields a pack rule reads. Region is free text and never decides, so it is never auto or confirm.
DECIDING_FIELDS = ("retention_days", "used_for_training", "zdr", "third_party_access")


def field_agreement(runs: list[dict | None], recorded: dict | None, basis: str) -> dict:
    out = {}
    for f in DECIDING_FIELDS:
        a = agreement(runs, f)
        if a["state"] == "auto" and recorded is not None and f in SCORED_FIELDS and recorded.get(f) != a["value"]:
            a = {**a, "state": "confirm", "value": None, "disagrees_with_recorded": recorded.get(f),
                 "options": a["options"] + [{"value": recorded.get(f), "no_terms": False, "runs": "recorded",
                                             "quote": recorded.get(QUOTE_OF[f], "")}]}
        out[f] = {**a, "basis": basis}
    return out


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text())


def _key(terms: dict) -> str:
    return json.dumps({k: terms.get(k) for k in SCORED_FIELDS}, sort_keys=True)


def consensus(calls: list[dict]) -> tuple[dict | None, str]:
    """Majority over runs on the scored fields; prefer a status=ok run inside the majority. None if no majority."""
    ok = [c for c in calls if c.get("terms")]
    votes = Counter(_key(c["terms"]) for c in ok)
    if not votes:
        return None, f"0/{len(calls)}"
    top, n = votes.most_common(1)[0]
    if n * 2 <= len(calls):
        return None, f"{n}/{len(calls)}"
    group = [c for c in ok if _key(c["terms"]) == top]
    chosen = next((c for c in group if c["terms"]["status"] == "ok"), group[0])
    terms = dict(chosen["terms"])
    # Answer fields outside the scored three still need their own majority, else they are held.
    for f in UNSCORED_ANSWER_FIELDS:
        fv = Counter(c["terms"].get(f) for c in ok)
        val, m = fv.most_common(1)[0]
        if m * 2 <= len(calls):
            val = "unspecified"
        if val != terms.get(f):
            src = next((c["terms"] for c in ok if c["terms"].get(f) == val), None)
            terms[f] = val
            terms[QUOTE_OF[f]] = src[QUOTE_OF[f]] if src else ""
    return {**chosen, "terms": terms}, f"{n}/{len(calls)}"


def extract_live(feature_ids: list[str], runs: int = 3, workers: int = 6, out_dir: Path | None = None) -> Path:
    """Nemotron reads each feature's Tavily capture `runs` times. Records every call (no page text) under
    eval/datause/registry-runs/ (or `out_dir`: the state dir when a job runs in the image)."""
    cat = load_catalog()
    man = json.loads((ROOT / "fixtures" / "manifest.json").read_text()).get("datause_tavily", {})
    jobs = []
    for fid in feature_ids:
        f = cat["features"][fid]
        p = TAVILY_RAW / f"{f['page']}.md"
        if not p.exists():
            raise SystemExit(f"no Tavily capture for {f['page']}; run `owin pack refresh` first")
        jobs += [(fid, f, p.read_text(), k) for k in range(runs)]

    def one(job):
        fid, f, text, k = job
        vendor = cat["providers"][f["provider"]]["display"]
        e = extract(fid, vendor, f["feature"], text, purpose="pack-registry")
        return {"id": fid, "run": k, "page": f["page"], "page_source_kind": man.get(f["page"], {}).get("source_kind"),
                "page_fetched_at": man.get(f["page"], {}).get("fetched_at"), **asdict(e)}

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        calls = list(ex.map(one, jobs))
    out = {"run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "model": tf.SUPER, "runs_per_item": runs,
           "prompt_version": PROMPT_VERSION, "input": "Tavily extract captures (fixtures/raw/datause-tavily/)",
           "wall_s": round(time.time() - t0, 1), "calls": calls}
    out_dir = out_dir or LIVE_RUNS
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{time.strftime('%Y%m%dT%H%M%S')}-tavily-{tf.SUPER.split('/')[-1]}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return path


def _entry_terms(t: dict) -> dict:
    keep = list(ANSWER_FIELDS) + list(QUOTE_OF.values()) + ["retention_condition", "verbatim", "status", "hold_reasons",
                                                            "model_claimed"]
    return {k: t.get(k) for k in keep}


def _rel(p: Path) -> str:
    """A run file's path relative to the repo, or to the state dir when a job wrote it there."""
    p = Path(p).resolve()
    for base in (ROOT, config.state_dir()):
        if base and p.is_relative_to(base.resolve()):
            return str(p.relative_to(base.resolve()))
    return str(p)


def export(live_runs: list[Path] | None = None) -> Path:
    cat = load_catalog()
    corpus = {i["id"]: i for i in dv.load_corpus()}
    a1_files = dv.registry_runs()
    a1 = {}
    for p in a1_files:
        for c in json.loads(Path(p).read_text())["calls"]:
            a1.setdefault(c["id"], []).append((str(Path(p).resolve().relative_to(ROOT)), c))
    live_files = live_runs if live_runs is not None else sorted(LIVE_RUNS.glob("*.json"))[-1:]
    live, live_meta = {}, {}
    for p in live_files:
        d = json.loads(Path(p).read_text())
        for c in d["calls"]:
            live.setdefault(c["id"], []).append(c)
            live_meta[c["id"]] = {"run_file": _rel(p), "model": d["model"],
                                  "prompt_version": d["prompt_version"], "page_fetched_at": c.get("page_fetched_at"),
                                  "page_source_kind": c.get("page_source_kind")}
    feats = {}
    for fid, f in cat["features"].items():
        page = cat["pages"][f["page"]]
        entry = {"feature_id": fid, "provider": f["provider"], "label": f["label"], "page": f["page"],
                 "source_url": page["url"], "corpus_id": f["corpus_id"], "inherits": f.get("inherits", {})}
        lv, lv_agree = consensus(live.get(fid, [])) if fid in live else (None, None)
        if f["corpus_id"] and f["corpus_id"] in a1:
            calls = a1[f["corpus_id"]]
            chosen, agree = consensus([c for _, c in calls])
            run_file = next((rf for rf, c in calls if chosen and c["run"] == chosen["run"]), calls[0][0])
            it = corpus[f["corpus_id"]]
            rd = json.loads((ROOT / run_file).read_text())
            entry |= {"origin": "a1_recorded", "measured": True, "run_file": run_file, "runs_agreeing": agree,
                      "model": rd["model"], "prompt_version": rd.get("prompt_version", "v1"),
                      "captured_at": it["fetched_at"], "capture_kind": "urllib", "source_sha256": it["source_sha256"],
                      "terms": _entry_terms(chosen["terms"]) if chosen else None}
        elif lv is not None:
            m = live_meta[fid]
            entry |= {"origin": "tavily_extraction", "measured": False, "run_file": m["run_file"], "runs_agreeing": lv_agree,
                      "model": m["model"], "prompt_version": m["prompt_version"], "captured_at": m["page_fetched_at"],
                      "capture_kind": m["page_source_kind"], "source_sha256": lv["source_sha256"], "terms": _entry_terms(lv["terms"])}
        else:
            entry |= {"origin": "none", "measured": False, "terms": None, "runs_agreeing": lv_agree or "0/0"}
        if fid in live:
            entry["field_agreement"] = field_agreement([c.get("terms") for c in live[fid]], entry.get("terms"),
                                                       f"{len(live[fid])} runs on the latest capture ({live_meta[fid]['page_source_kind']})")
        elif f["corpus_id"] and f["corpus_id"] in a1:
            entry["field_agreement"] = field_agreement([c.get("terms") for _, c in a1[f["corpus_id"]]], None,
                                                       f"{len(a1[f['corpus_id']])} recorded A1 runs")
        else:
            entry["field_agreement"] = {}
        if fid in live:
            base = entry.get("terms") or {}
            entry["live_check"] = {
                **live_meta[fid], "runs_agreeing": lv_agree,
                "values": {k: lv["terms"].get(k) for k in ANSWER_FIELDS} if lv else None,
                "quotes": {k: lv["terms"].get(QUOTE_OF[k]) for k in ANSWER_FIELDS} if lv else None,
                "agrees": {k: bool(lv) and lv["terms"].get(k) == base.get(k) for k in SCORED_FIELDS},
            }
        feats[fid] = entry
    out = {"_about": "Exported by `owin pack registry` from recorded runs only. The answer pack reads structured fields "
                     "from here; quotes are display evidence and never decide an answer.",
           "a1_run_files": [_rel(p) for p in a1_files], "live_run_files": [_rel(p) for p in live_files],
           "features": feats}
    # The committed file when no state dir is set; the state dir's copy (what the endpoint serves) when one is.
    return config.write_atomic("data/datause/registry.json", json.dumps(out, indent=1, ensure_ascii=False) + "\n")


def load() -> dict:
    return json.loads(config.read_path("data/datause/registry.json").read_text())["features"]


def source_digest(text: str) -> str:
    return sha256(text)
