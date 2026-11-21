"""Adapting to the real brief (the equivalent of his engineering_example.py).

When the real Mech Royale brief drops at kickoff, the harness does not change --
only the arena and the metric do. The three edits:

1. Replace ``data.py`` so ``play`` runs the brief's real game engine and ``evaluate``
   runs the brief's real match/scoring protocol (grid or continuous, the real
   action set, the real win condition).
2. Replace ``evaluation.py`` so ``score_candidate`` packages the brief's real
   headline metric into a ScoreCard.
3. Keep ``solvers.py`` (the bots and the ladder) and ``model.py``: re-point a bot
   at the real action set and keep the weak->strong climb.

This example runs a single bot against the strong field on a handful of matches,
using the *direct* API so it is fast and needs no full harness sweep.

    python mech_royale_model/examples/real_brief_example.py [--n N]
"""
from __future__ import annotations

import argparse

from mech_royale import solvers
from mech_royale.model import MechRoyaleModel


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20, help="matches to play (kept small so it runs fast)")
    args = ap.parse_args()

    model = MechRoyaleModel()

    # The strongest rung, scored against the strong field over a few matches.
    best_bot = model.bot(level=-1)
    card = model.score_bot(best_bot, n=args.n, seed=1)
    print(f"v4 one-step lookahead vs the strong field ({args.n} matches):")
    print(f"  top-2 rate : {card.metrics['top2_rate']:.0%}")
    print(f"  win rate   : {card.metrics['win_rate']:.0%}")
    print(f"  mean points: {card.metrics['mean_points']:.2f}")

    # The weakest rung, for contrast -- the climb the ladder buys you.
    weak = model.bot(level=0)
    weak_card = model.score_bot(weak, n=args.n, seed=1)
    print(f"\nv0 random vs the same field: top-2 rate {weak_card.metrics['top2_rate']:.0%}")

    print("\nWhen the brief drops: swap data.py (engine + scoring) + evaluation.py "
          "(metric), keep solvers.py and the ladder.")
    print(f"(strong field = {[fn.__name__ for fn in solvers.STRONG_FIELD]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
