"""owin CLI. Every command prints JSON to stdout (the stable contract in docs/CONTRACT.md)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import evaluate, tokenfactory as tf


def _print(obj) -> None:
    json.dump(obj, sys.stdout, indent=1, default=str)
    sys.stdout.write("\n")


def cmd_eval(a) -> int:
    if a.corpus == "datause":
        return cmd_eval_datause(a)
    if a.action == "audit":
        print("audit is only defined for --corpus datause", file=sys.stderr)
        return 2
    if a.action == "run":
        spent = tf.ledger_total()
        if spent >= a.budget:
            print(f"budget cap reached: ledger total ${spent:.4f} >= ${a.budget}", file=sys.stderr)
            return 2
        path = evaluate.run(runs=a.runs, model=a.model, only=a.only.split(",") if a.only else None)
        res = evaluate.score(path)
    else:
        res = evaluate.score([Path(f) for f in a.file.split(",")] if a.file else evaluate.headline_runs())
    if a.brief:
        res = {k: res[k] for k in ("run_files", "model", "quotes_rechecked_against_source", "headline", "per_successful_run")}
    _print(res)
    return 0


def cmd_eval_datause(a) -> int:
    from .datause import evaluate as dv
    if a.action == "audit":
        _print({"wrote": str(dv.write_audit().relative_to(dv.ROOT))})
        return 0
    if a.action == "run":
        spent = tf.ledger_total()
        if spent >= a.budget:
            print(f"budget cap reached: ledger total ${spent:.4f} >= ${a.budget}", file=sys.stderr)
            return 2
        path = dv.run(runs=a.runs, model=a.model, only=a.only.split(",") if a.only else None, split=a.split or None)
        res = dv.score(path)
    else:
        res = dv.score([Path(f) for f in a.file.split(",")] if a.file else dv.headline_runs())
    if a.brief:
        res = {k: res[k] for k in ("corpus", "run_files", "model", "prompt_versions", "quotes_rechecked_against_source", "acceptance",
                                   "acceptance_v3fresh", "headline", "per_successful_run")}
    _print(res)
    return 0


def cmd_fixtures(a) -> int:
    from . import fixtures
    _print({"wrote": str(fixtures.write().relative_to(fixtures.ROOT))})
    return 0


def cmd_replay(a) -> int:
    from datetime import datetime, timezone
    from . import replay
    as_of = datetime.now(timezone.utc) if a.as_of == "now" else (datetime.fromisoformat(a.as_of) if a.as_of else None)
    who = {"name": a.who, "role": a.role} if a.who else None
    ev = replay.run(a.id, as_of=as_of, promise_days=a.promise_days, decision=a.decide or None, decided_by=who)
    if a.brief:
        ev = {k: ev.get(k) for k in ("replay", "watch_state", "workflow_state", "headline", "flags", "actions", "clock",
                                     "your_notice", "affected_customers", "decision_record")}
    _print(ev)
    return 0


def cmd_terms(a) -> int:
    from . import terms
    _print({"wrote": [str(p.relative_to(terms.ROOT)) for p in terms.export()]})
    return 0


def cmd_snapshots(a) -> int:
    from . import snapshots
    _print({"wrote": [str(p.relative_to(snapshots.ROOT)) for p in snapshots.build()]})
    return 0


def cmd_sweep(a) -> int:
    from pathlib import Path
    from . import sweep
    if a.seed_archive:
        from . import replay
        sweep.seed(replay.load_snapshot(a.seed_archive))
    out = sweep.run(live=a.live, only=a.only.split(",") if a.only else None, record=Path(a.record) if a.record else None)
    if a.brief:
        out = {**{k: v for k, v in out.items() if k != "rows"},
               "rows": [{k: r.get(k) for k in ("vendor", "state", "source_kind", "entities", "last_updated", "reason")} for r in out["rows"]]}
    _print(out)
    return 0


def _pack_manifest(a) -> dict:
    from .datause import pack
    m = json.loads(Path(a.stack).read_text()) if a.stack else pack.load_demo()
    for s in a.set or []:
        path, _, feature = s.partition("=")
        m = pack.set_feature(m, path, feature)
    return m


def cmd_pack(a) -> int:
    from .datause import export, observations, pack, registry
    if a.action == "refresh":
        cat = registry.load_catalog()
        pages = a.pages.split(",") if a.pages else sorted(cat["pages"])
        _print(observations.refresh(pages, fetch=a.fetch))
        return 0
    if a.action == "registry":
        _print({"wrote": str(registry.export().relative_to(registry.ROOT))})
        return 0
    if a.action == "extract":
        spent = tf.ledger_total()
        if spent >= a.budget:
            print(f"budget cap reached: ledger total ${spent:.4f} >= ${a.budget}", file=sys.stderr)
            return 2
        feats = a.features.split(",") if a.features else sorted({e["feature"] for e in pack.load_demo()["endpoints"]})
        p = registry.extract_live(feats, runs=a.runs)
        _print({"wrote": str(p.relative_to(registry.ROOT)), "ledger_total_usd": round(tf.ledger_total(), 4)})
        return 0
    try:
        p = pack.build(_pack_manifest(a))
    except pack.PackError as e:
        print(f"pack: {e}", file=sys.stderr)
        return 2
    fmt = a.format
    if fmt in ("csv", "html"):
        text = export.to_csv(p) if fmt == "csv" else export.to_html(p)
    else:
        obj = {"json": p, "brief": pack.brief(p), "share": export.to_share(p)}[fmt]
        text = json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n"
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text)
        _print({"wrote": a.out, "format": fmt, "pack_id": p["pack_id"], "badges": {x["id"]: x["badge"] for x in p["answers"]}})
    else:
        sys.stdout.write(text)
    return 0


def cmd_serve(a) -> int:
    from . import server
    print(f"Owin debug server on http://{a.host}:{a.port}/", file=sys.stderr)
    server.serve(a.host, a.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="owin")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eval", help="measurement harness")
    e.add_argument("action", choices=["run", "score", "audit"])
    e.add_argument("--corpus", choices=["dpa", "datause"], default="dpa",
                   help="dpa = P1 sub-processor objection windows; datause = AI data-use terms per feature")
    e.add_argument("--split", choices=["", "tuned", "heldout", "fresh", "v3fresh"], default="", help="datause: run one split only")
    e.add_argument("--runs", type=int, default=3)
    e.add_argument("--model", default=tf.SUPER)
    e.add_argument("--only", default="")
    e.add_argument("--file", default="", help="comma-separated recorded run files (default: eval/headline.json)")
    e.add_argument("--budget", type=float, default=3.0, help="refuse to run when the usage ledger total reaches this (USD)")
    e.add_argument("--brief", action="store_true")
    e.set_defaults(fn=cmd_eval)
    fx = sub.add_parser("fixtures", help="fixture provenance")
    fx.add_argument("action", choices=["manifest"])
    fx.set_defaults(fn=cmd_fixtures)
    r = sub.add_parser("replay", help="seeded real historical change")
    r.add_argument("--id", default="openai-2026-10-14")
    r.add_argument("--promise-days", type=int, default=None, help="change one input: your promised customer notice")
    r.add_argument("--as-of", default="", help="ISO time or 'now' (default: the after-snapshot time)")
    r.add_argument("--decide", choices=["accepted", "objected", "dismissed"], default="")
    r.add_argument("--who", default="")
    r.add_argument("--role", default="privacy owner")
    r.add_argument("--brief", action="store_true")
    r.set_defaults(fn=cmd_replay)
    t = sub.add_parser("terms", help="vendor terms registry")
    t.add_argument("action", choices=["export"])
    t.set_defaults(fn=cmd_terms)
    sn = sub.add_parser("snapshots", help="entity snapshots from raw captures")
    sn.add_argument("action", choices=["build"])
    sn.set_defaults(fn=cmd_snapshots)
    sw = sub.add_parser("sweep", help="sweep the vendor index (Tavily, else labelled fixtures)")
    sw.add_argument("--live", action=argparse.BooleanOptionalAction, default=True)
    sw.add_argument("--only", default="")
    sw.add_argument("--record", default="", help="write the sweep result to this JSON path")
    sw.add_argument("--seed-archive", default="", help="accept a fixtures/snapshots/*.json as the baseline first")
    sw.add_argument("--brief", action="store_true")
    sw.set_defaults(fn=cmd_sweep)
    pk = sub.add_parser("pack", help="security-review answer pack (AI and data section), per endpoint")
    pk.add_argument("action", choices=["build", "refresh", "registry", "extract"],
                    help="build = compute the pack (no network); refresh = re-fetch pages via Tavily and record observations; "
                         "registry = export data/datause/registry.json from recorded runs; extract = Nemotron on Tavily captures")
    pk.add_argument("--stack", default="", help="stack manifest JSON (default: fixtures/demo/stack.json)")
    pk.add_argument("--set", action="append", metavar="PATH=FEATURE", help="change one input, e.g. /api/crm-sync=anthropic-messages")
    pk.add_argument("--format", choices=["json", "brief", "csv", "html", "share"], default="json")
    pk.add_argument("--out", default="")
    pk.add_argument("--pages", default="", help="refresh: comma-separated page ids (default: every catalog page)")
    pk.add_argument("--fetch", action=argparse.BooleanOptionalAction, default=True, help="refresh: --no-fetch records from captures on disk")
    pk.add_argument("--features", default="", help="extract: feature ids (default: the demo stack)")
    pk.add_argument("--runs", type=int, default=3)
    pk.add_argument("--budget", type=float, default=3.0)
    pk.set_defaults(fn=cmd_pack)
    sv = sub.add_parser("serve", help="JSON API + debug page")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8787)
    sv.set_defaults(fn=cmd_serve)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
