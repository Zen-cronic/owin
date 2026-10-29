"""The Nemotron ladder on the pre-registered split, and the pre-registered escalation (`owin eval ladder`).

Every arm is the same protocol as the headline: prompt v3, three readings per page, the verbatim gate and the
selective rule (owin/datause/selective.py). Only the model changes. The escalation is the one rule written down
in eval/datause/escalation-preregistration.json before any arm ran:

  A cell that Super's three readings send to a person is answered automatically only when Nemotron Ultra's
  successful readings of the same page (at least 2) agree unanimously AND that value is one Super's readings
  gave. Otherwise the cell stays with the person. Cells Super answers on its own are never re-opened.

Recomputed keyless from recorded run files (eval/datause/ladder.json lists them). The headline stays the
pre-registered Super result; the escalation is reported as its own line.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from . import evaluate as dv, selective
from .schema import SCORED_FIELDS

ROOT = dv.ROOT
PREREG = ROOT / "eval" / "datause" / "escalation-preregistration.json"
LADDER = ROOT / "eval" / "datause" / "ladder.json"
SPLIT = "v3fresh"


def _runs() -> dict[str, Path]:
    """Arm name -> run file. Super is the headline run; the other arms are listed in eval/datause/ladder.json."""
    arms = {"super": dv.headline_runs()[0]}
    if LADDER.exists():
        arms |= {k: ROOT / v for k, v in json.loads(LADDER.read_text())["arms"].items()}
    return arms


def _cost_latency(path: Path) -> dict:
    d = json.loads(Path(path).read_text())
    calls = d["calls"]
    lat = sorted(c["latency_s"] for c in calls if not c["error"]) or [0.0]
    return {"model": d["model"], "readings": len(calls), "errored_abstained": sum(1 for c in calls if c["error"]),
            "cost_usd": round(sum(c["cost_usd"] for c in calls), 4),
            "cost_per_reading_usd": round(sum(c["cost_usd"] for c in calls) / len(calls), 5),
            "mean_latency_s": round(statistics.mean(lat), 2), "p95_latency_s": lat[int(0.95 * (len(lat) - 1))]}


def arm(path: Path) -> dict:
    r = selective.evaluate([path], split=SPLIT)
    neg = selective.evaluate([path], split=SPLIT, kinds=("negative",))
    return {"run_file": str(Path(path).resolve().relative_to(ROOT)), **_cost_latency(path),
            "auto_answered": r["auto_answered"], "auto_correct": r["auto_correct"], "auto_precision": r["auto_precision"],
            "sent_to_confirm": r["sent_to_confirm"], "confident_misses": len(r["auto_misses"]),
            "auto_misses": r["auto_misses"], "negatives": neg["auto_correct"]}


def escalate(super_path: Path, ultra_path: Path) -> dict:
    """Apply the pre-registered escalation cell by cell, from the two recorded runs."""
    corpus, sup = selective._gated([super_path])
    _, ult = selective._gated([ultra_path])
    cells = []
    for iid, runs in sorted(sup.items()):
        it = corpus[iid]
        if it["split"] != SPLIT or it["kind"] == "negative":
            continue
        for f in SCORED_FIELDS:
            s = selective.agreement(runs, f)
            gold = it["gold"][f]
            if s["state"] == "auto":
                cells.append({"item": iid, "field": f, "by": "super", "value": s["value"], "gold": gold})
                continue
            u = selective.agreement(ult.get(iid, []), f)
            super_values = [o["value"] for o in s["options"] if not o["no_terms"]]
            if u["state"] == "auto" and u["value"] in super_values:
                cells.append({"item": iid, "field": f, "by": "ultra", "value": u["value"], "gold": gold,
                              "super_split": s["runs_agreeing"], "ultra": u["runs_agreeing"]})
            else:
                cells.append({"item": iid, "field": f, "by": "person", "value": None, "gold": gold,
                              "super_split": s["runs_agreeing"], "ultra": u["runs_agreeing"],
                              "ultra_value": u["value"] if u["state"] == "auto" else None})
    auto = [c for c in cells if c["by"] != "person"]
    right = [c for c in auto if c["value"] == c["gold"]]
    by_ultra = [c for c in cells if c["by"] == "ultra"]
    return {"cells": len(cells), "auto_answered": f"{len(auto)}/{len(cells)}", "auto_correct": f"{len(right)}/{len(auto)}",
            "sent_to_person": len(cells) - len(auto),
            "resolved_by_ultra": f"{sum(c['value'] == c['gold'] for c in by_ultra)}/{len(by_ultra)}",
            "confident_misses": [{k: c[k] for k in ("item", "field", "by", "value", "gold")} for c in auto if c["value"] != c["gold"]],
            "ultra_cells": by_ultra, "still_with_person": [c for c in cells if c["by"] == "person"]}


def report() -> dict:
    runs = _runs()
    arms = {name: arm(p) for name, p in runs.items()}
    out = {"split": SPLIT, "protocol": "prompt v3, 3 readings per page, verbatim gate, selective rule; only the model changes",
           "preregistration": str(PREREG.relative_to(ROOT)), "arms": arms}
    if "ultra" in runs:
        esc = escalate(runs["super"], runs["ultra"])
        pre = json.loads(PREREG.read_text())
        sup, ult = arms["super"], arms["ultra"]
        items = {c["item"] for c in esc["ultra_cells"] + esc["still_with_person"]}
        ucalls = [c for c in json.loads(runs["ultra"].read_text())["calls"] if c["id"] in items]
        esc["features_escalated"] = len(items)
        esc["extra_cost_usd"] = round(sum(c["cost_usd"] for c in ucalls), 4)
        esc["extra_cost_per_feature_usd"] = round(esc["extra_cost_usd"] / len(items), 4) if items else 0.0
        esc["adopted"] = (esc["sent_to_person"] < sup["sent_to_confirm"]
                          and len(esc["confident_misses"]) <= sup["confident_misses"])
        esc["bar"] = pre["adoption_bar"]
        out["escalation"] = esc
        right = lambda a: int(a["auto_correct"].split("/")[0])
        out["retraction"] = {"condition": pre["retraction_condition"],
                             "triggered": right(ult) > right(sup) and ult["confident_misses"] <= sup["confident_misses"]}
    if "nano" in runs:
        out["cascade_nano_first"] = cascade(runs["nano"], runs["super"])
    return out


def cascade(nano_path: Path, super_path: Path) -> dict:
    """The pre-registered cascade (reported, decides nothing): a feature whose three Nano readings are unanimous on
    all three scored fields takes Nano's values; any other feature goes to Super's three readings and the rule."""
    corpus, nano = selective._gated([nano_path])
    _, sup = selective._gated([super_path])
    ncost = {}
    for c in json.loads(Path(nano_path).read_text())["calls"]:
        ncost[c["id"]] = ncost.get(c["id"], 0.0) + c["cost_usd"]
    scost = {}
    for c in json.loads(Path(super_path).read_text())["calls"]:
        scost[c["id"]] = scost.get(c["id"], 0.0) + c["cost_usd"]
    cells, cost, by_nano = [], 0.0, 0
    feats = [i for i in sorted(sup) if corpus[i]["split"] == SPLIT and corpus[i]["kind"] != "negative"]
    for iid in feats:
        na = {f: selective.agreement(nano.get(iid, []), f) for f in SCORED_FIELDS}
        cost += ncost.get(iid, 0.0)
        if all(a["state"] == "auto" for a in na.values()):
            by_nano += 1
            cells += [{"item": iid, "field": f, "by": "nano", "value": a["value"], "gold": corpus[iid]["gold"][f]} for f, a in na.items()]
            continue
        cost += scost.get(iid, 0.0)
        for f in SCORED_FIELDS:
            a = selective.agreement(sup[iid], f)
            cells.append({"item": iid, "field": f, "by": "super" if a["state"] == "auto" else "person",
                          "value": a["value"], "gold": corpus[iid]["gold"][f]})
    auto = [c for c in cells if c["by"] != "person"]
    right = [c for c in auto if c["value"] == c["gold"]]
    return {"features": len(feats), "decided_by_nano": by_nano, "auto_answered": f"{len(auto)}/{len(cells)}",
            "auto_correct": f"{len(right)}/{len(auto)}", "sent_to_person": len(cells) - len(auto),
            "confident_misses": [{k: c[k] for k in ("item", "field", "by", "value", "gold")} for c in auto if c["value"] != c["gold"]],
            "cost_per_feature_usd": round(cost / len(feats), 5) if feats else None,
            "super_cost_per_feature_usd": round(sum(scost.get(i, 0.0) for i in feats) / len(feats), 5) if feats else None}


def record(arms: dict[str, Path], disclosures: list[str] | None = None) -> Path:
    """List the scored run file per arm (one run each, per the pre-registration) in eval/datause/ladder.json."""
    pre = json.loads(PREREG.read_text())
    LADDER.write_text(json.dumps({
        "disclosures": disclosures or [],
        "_about": "The one scored run per arm (eval/datause/escalation-preregistration.json, one_run_rule). Every run_at "
                  "is later than the pre-registration's written_at; tests/test_ladder.py checks it.",
        "preregistration_written_at": pre["written_at"],
        "arms": {k: str(Path(v).resolve().relative_to(ROOT)) for k, v in sorted(arms.items())}}, indent=1) + "\n")
    return LADDER


def brief(rep: dict) -> dict:
    keep = ("model", "auto_answered", "auto_correct", "sent_to_confirm", "confident_misses", "negatives",
            "cost_per_reading_usd", "mean_latency_s", "errored_abstained")
    b = {"split": rep["split"], "arms": {k: {x: v[x] for x in keep} for k, v in rep["arms"].items()}}
    if "escalation" in rep:
        e = rep["escalation"]
        b["escalation"] = {k: e[k] for k in ("auto_answered", "auto_correct", "sent_to_person", "resolved_by_ultra",
                                             "confident_misses", "features_escalated", "extra_cost_per_feature_usd", "adopted")}
        b["retraction_triggered"] = rep["retraction"]["triggered"]
    if "cascade_nano_first" in rep:
        b["cascade_nano_first"] = {k: v for k, v in rep["cascade_nano_first"].items() if k != "confident_misses"} | {
            "confident_misses": len(rep["cascade_nano_first"]["confident_misses"])}
    return b
