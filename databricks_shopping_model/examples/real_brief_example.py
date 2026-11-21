"""Adapting to the real brief (the equivalent of his engineering_example.py).

When the real Databricks "Shopping Sessions" brief drops at kickoff, the harness
does not change -- only the data loader and the metric do. This example shows the
three edits, fitting the strongest *untuned* rung (v5 hybrid) on a tiny
hand-built training log so it runs instantly with no grid search:

1. Replace ``data.py`` so ``train`` is the brief's real session logs and a case
   is a real ``(prefix, next_item)`` from a later time period.
2. Replace ``evaluation.py`` so the metric matches the brief exactly (watch for
   separate click / cart / order weighting, or next-basket instead of next-item).
3. Keep ``solvers.py`` (directional co-occurrence + recency + revisit bonus) and
   the ladder -- that structure is what transfers to real clickstream.

    python databricks_shopping_model/examples/real_brief_example.py [--n N]
"""
from __future__ import annotations

import argparse

from databricks_shopping.model import DatabricksShoppingModel

# A tiny training log shaped like the real task: (week, [(item, event_type), ...]).
# Shoppers who view item 1 then usually go to item 2; item 10 often follows 2.
TRAIN = [
    (0, [(1, "view"), (2, "view"), (10, "cart")]),
    (0, [(1, "view"), (2, "view"), (2, "view")]),
    (1, [(1, "view"), (2, "cart"), (10, "purchase")]),
    (1, [(3, "view"), (4, "view")]),
    (1, [(1, "view"), (2, "view"), (10, "view")]),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1, help="ignored; kept for harness parity")
    ap.parse_args()

    model = DatabricksShoppingModel()
    recommend = model.build_recommender(TRAIN, level=5)  # v5 hybrid, no tuning needed

    prefix = [(1, "view"), (2, "view")]
    top5 = recommend(prefix)[:5]
    print("session so far:", [i for i, _ in prefix])
    print("v5 hybrid top-5 next items:", top5)
    print("\nWhen the brief drops: swap data.py + evaluation.py, "
          "keep solvers.py and the ladder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
