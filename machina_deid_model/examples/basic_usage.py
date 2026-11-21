"""Basic usage: score the Machina CAD De-ID ladder through the shared harness.

    python machina_deid_model/examples/basic_usage.py [--n N]
"""
from __future__ import annotations

import argparse

from buildathon_core import Harness, get_track, render_report

import machina_deid  # noqa: F401  (registers the track)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    args = ap.parse_args()

    report = Harness(n=args.n).run(get_track("machina_deid"))
    print(render_report(report))
    best = report.best
    print(f"best hidden pass rate: {best.hidden.headline:.0%} ({best.solution.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
