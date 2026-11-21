"""Adapting to the real brief (the equivalent of his engineering_example.py).

When the real RWX brief drops at kickoff, the harness does not change -- only the
data loader and the metric do. This example shows the three edits, using the
direct solver API on a single hand-built case so it runs with no RNG:

1. Replace ``data.py`` so a "case" is the brief's real repo + commit batch.
2. Replace ``evaluation.py`` so the metric matches the brief exactly.
3. Keep ``solvers.py`` (the dependency-graph modelling) and the ladder.

    python rwx_blast_radius_model/examples/real_brief_example.py [--n N]
"""
from __future__ import annotations

import argparse

from rwx_blast_radius.model import RWXBlastRadiusModel

# A single case shaped like the real task: files, a batch of commits, a CI log.
CASE = {
    "files": {
        "pkg/__init__.py": "",
        "pkg/rates.py": "def price(x, y=0):\n    return x\n",
        "pkg/report.py": "from pkg.rates import price\n\ndef render(x, y=0):\n    return x\n",
        "tests/test_rates.py": "from pkg.rates import price\n\ndef test_price():\n    assert price(1) == 1\n",
    },
    "commits": [
        {"id": "c0", "changes": {"pkg/report.py": "from pkg.rates import price\n# doc\n"}},
        {"id": "c1", "changes": {"pkg/rates.py": "def price(x, y, z):\n    return x\n"}},
    ],
    "log": "FAILED tests/test_rates.py\nTypeError: price() missing 1 required positional argument: 'z'\n",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1, help="ignored; kept for harness parity")
    ap.parse_args()

    model = RWXBlastRadiusModel()
    print("culprit (v4 full graph + semantic diff):", model.solve_culprit(CASE, level=4))
    # For impact, a change touching pkg/rates.py must re-run the test that imports it.
    impact_case = {"files": CASE["files"], "tests": ["tests/test_rates.py"],
                   "changed": ["pkg/rates.py"]}
    print("impact (v4):", model.solve_impact(impact_case, level=4))
    print("\nWhen the brief drops: swap data.py + evaluation.py, keep solvers.py and the ladder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
