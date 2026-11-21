"""The published metric (Recall@20 and MRR@20) plus a ScoreCard wrapper.

* Recall@K: fraction of cases whose true next item appears in the top-K.
* MRR@K: mean reciprocal rank of the true next item within the top-K.

The raw ``score`` function is kept identical to the original ``bench.py`` so
results do not move; ``recommend_card`` adapts it to the shared ``ScoreCard``
contract, with Recall@20 as the headline and both scalars kept in ``metrics`` so
MRR is never lost.
"""
from __future__ import annotations

from typing import Callable

from buildathon_core import ScoreCard


def score(recommend, cases, k: int = 20) -> tuple[float, float]:
    hit, mrr = 0, 0.0
    for prefix, truth in cases:
        recs = list(recommend(prefix))[:k]
        if truth in recs:
            hit += 1
            mrr += 1.0 / (recs.index(truth) + 1)
    return hit / len(cases), mrr / len(cases)


def recommend_card(recommend: Callable, cases, k: int = 20) -> ScoreCard:
    """Score a ``recommend(prefix)`` function and return a ScoreCard.

    Headline is Recall@K (the metric the board ranks on); MRR@K rides along as a
    second measured scalar.
    """
    recall, mrr = score(recommend, cases, k)
    return ScoreCard(headline=recall, metrics={"recall": recall, "mrr": mrr})
