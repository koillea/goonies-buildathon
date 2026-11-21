"""Basic usage: score the Mech Royale bot ladder through the shared harness.

    python mech_royale_model/examples/basic_usage.py [--n N]

``--n`` is the number of matches per cell. The tournament is stochastic, so a
small ``n`` is noisy but fast; the default is modest so the example runs quickly.
"""
from __future__ import annotations

import argparse

from buildathon_core import Harness, get_track, render_report

import mech_royale  # noqa: F401  (registers the track)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50, help="matches per cell")
    args = ap.parse_args()

    report = Harness(n=args.n).run(get_track("mech_royale"))
    print(render_report(report))
    best = report.best
    print(f"best hidden top-2 rate: {best.hidden.headline:.0%} ({best.solution.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
