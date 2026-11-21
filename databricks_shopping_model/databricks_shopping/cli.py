"""`python -m databricks_shopping` -- score the ladder on dev + hidden, offline.

Everything is pure stdlib on seeded synthetic sessions, so the CLI is always
offline; ``--offline`` is accepted for parity with the reference repo's CLIs and
is a no-op here.
"""
from __future__ import annotations

import argparse
import json

from buildathon_core import Harness, render_report

from .config import DatabricksShoppingConfig
from .model import MODEL


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="databricks_shopping",
                                description="Databricks Shopping Sessions practice harness.")
    c = DatabricksShoppingConfig()
    p.add_argument("--n", type=int, default=c.n, help="eval cases per split")
    p.add_argument("--dev-seed", type=int, default=c.dev_seed)
    p.add_argument("--hidden-seed", type=int, default=c.hidden_seed)
    p.add_argument("--json", action="store_true", help="emit the report as JSON")
    p.add_argument("--offline", action="store_true", help="no-op (always offline)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = Harness(n=args.n, dev_seed=args.dev_seed, hidden_seed=args.hidden_seed).run(MODEL)
    if args.json:
        print(json.dumps({
            "track": report.track,
            "metric": report.metric_name,
            "n": report.n_cases,
            "results": [{"name": r.solution.name, "dev": r.dev.metrics,
                         "hidden": r.hidden.metrics, "status": str(r.status),
                         "generalizes": r.generalizes} for r in report.results],
        }, indent=2))
    else:
        print(render_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
