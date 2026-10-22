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


def cmd_fixtures(a) -> int:
    from . import fixtures
    _print({"wrote": str(fixtures.write().relative_to(fixtures.ROOT))})
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="owin")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eval", help="measurement harness")
    e.add_argument("action", choices=["run", "score"])
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
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
