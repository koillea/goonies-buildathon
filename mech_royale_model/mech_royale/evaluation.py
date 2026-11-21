"""The published metric, plus a thin wrapper that returns a ScoreCard.

The raw ``data.evaluate`` is kept identical to the original ``bench.py`` so
results do not move: it plays a candidate over many seeded matches against a
field and returns ``(mean points, win rate, top-2 rate)``. ``score_candidate``
adapts that tuple to the shared ``ScoreCard`` contract, with the top-2 rate as
the headline (what ``run.py`` ranks on) and mean points and win rate riding
along as the secondary measures so nothing is lost.
"""
from __future__ import annotations

from typing import Callable, Sequence

from buildathon_core import ScoreCard

from . import data


def score_candidate(candidate: Callable, field: Sequence[Callable],
                    n_matches: int, seed: int) -> ScoreCard:
    """Run ``data.evaluate`` and package the result as a ScoreCard.

    Headline is the top-2 rate (run.py's ranking metric); ``metrics`` also carries
    the mean placement points and the win rate.
    """
    mean_points, win_rate, top2_rate = data.evaluate(candidate, list(field), n_matches, seed)
    return ScoreCard(
        headline=top2_rate,
        metrics={"top2_rate": top2_rate, "mean_points": mean_points, "win_rate": win_rate},
    )
