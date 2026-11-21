"""Basic usage: score the RWX ladder through the shared harness.

    python rwx_blast_radius_model/examples/basic_usage.py [--n N]
"""
from __future__ import annotations

import argparse

from buildathon_core import Harness, render_report

import rwx_blast_radius  # noqa: F401  (registers the track)
from buildathon_core import get_track


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    args = ap.parse_args()

    report = Harness(n=args.n).run(get_track("rwx_blast_radius"))
    print(render_report(report))
    best = report.best
    print(f"best hidden accuracy: {best.hidden.headline:.0%} ({best.solution.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
