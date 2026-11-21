"""The two published metrics, plus thin wrappers that return ScoreCards.

* culprit: accuracy over N cases (the site's worked example metric).
* impact: mean F1 over N cases, with the exact-match rate reported alongside.

The raw ``score_culprit`` / ``score_impact`` functions are kept identical to the
original ``bench.py`` so results do not move; ``culprit_card`` / ``impact_card``
adapt them to the shared ``ScoreCard`` contract.
"""
from __future__ import annotations

from typing import Callable

from buildathon_core import ScoreCard


def score_culprit(solve, cases) -> float:
    return sum(solve(c) == truth for c, truth in cases) / len(cases)


def score_impact(solve, cases) -> tuple[float, float]:
    """Return (mean F1, exact-match rate)."""
    f1s, exact = [], 0
    for c, truth in cases:
        pred, t = set(solve(c)), set(truth)
        if pred == t:
            exact += 1
        if not pred and not t:
            f1s.append(1.0)
            continue
        tp = len(pred & t)
        p = tp / len(pred) if pred else 0.0
        r = tp / len(t) if t else 0.0
        f1s.append(2 * p * r / (p + r) if p + r else 0.0)
    return sum(f1s) / len(f1s), exact / len(cases)


def culprit_card(solve: Callable, cases) -> ScoreCard:
    acc = score_culprit(solve, cases)
    return ScoreCard(headline=acc, metrics={"accuracy": acc})


def impact_card(solve: Callable, cases) -> ScoreCard:
    f1, exact = score_impact(solve, cases)
    return ScoreCard(headline=f1, metrics={"f1": f1, "exact": exact})
