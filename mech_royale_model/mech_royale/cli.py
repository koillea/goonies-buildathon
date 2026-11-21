"""``python -m mech_royale`` -- score the bot ladder on dev + hidden, offline.

Everything is pure stdlib on seeded synthetic matches, so the CLI is always
offline; ``--offline`` is accepted for parity with the reference repo's CLIs and
is a no-op here. ``--n`` is the number of matches per cell (the tournament is
stochastic); keep it modest for a quick run, raise it for a steadier headline.
"""
from __future__ import annotations

import argparse
import json

from buildathon_core import Harness, render_report

from .config import MechRoyaleConfig
from .model import MODEL


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mech_royale",
                                description="Builders Mech Royale practice harness.")
    c = MechRoyaleConfig()
    p.add_argument("--n", type=int, default=c.n, help="matches per cell")
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
