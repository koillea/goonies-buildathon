"""DatabricksShoppingModel: the TrackSpec for the Shopping Sessions track.

Shopping Sessions is a *fit-then-recommend* track: the solvers fit on a training
split of session clickstream, then recommend the next item for the prefix of an
unseen session. The ladder is the full weak->strong climb the original ``run.py``
reported (v0..v6), including the two tuned rungs (v4, v6) that grid-search their
knobs on a **time-based split inside the training data** -- never on hidden.

Its ScoreCard carries Recall@20 (the headline) plus MRR@20 so the ranking metric
and the rank-quality metric are both kept.

``run`` / ``run_sync`` is the uniform life-cycle entry (fit + score + render) the
other models expose; ``build_recommender`` is direct access to the ladder.
"""
from __future__ import annotations

import random

from buildathon_core import (
    Solution,
    SolutionResult,
    TrackReport,
    register_track,
)

from . import solvers
from .config import DatabricksShoppingConfig
from .data import WEEKS, World, build_train, eval_set
from .evaluation import recommend_card, score

# Rungs, weakest first. Each entry: (name, description). The recommenders are
# built in this same order inside ``evaluate``; nothing that scored is dropped.
_RUNGS = [
    ("v0 all-time popularity",
     "most-frequent items over all of training. The board's Baseline row."),
    ("v1 recent popularity (time-decayed)",
     "weight recent weeks more; popularity drifts, so recency helps a little."),
    ("v2 next-item bigram + popularity fill",
     "what usually comes right after the last item; fall back to recent popularity."),
    ("v3 session co-visitation, recency-weighted",
     "symmetric co-occurrence over a window from every item in the session."),
    ("v4 v3 tuned on a time split",
     "grid-search v3's knobs on the latest train week, then refit on everything."),
    ("v5 hybrid: bigram + earlier items + revisit bonus",
     "directional next-item counts from the last item, weaker votes from earlier "
     "items, plus a bonus for items already seen (revisits happen ~14% of the time)."),
    ("v6 v5 tuned on a time split",
     "grid-search the hybrid's knobs on the latest train week, then refit."),
]


class DatabricksShoppingModel:
    """TrackSpec implementation for Databricks Shopping Sessions."""

    name = "databricks_shopping"

    def __init__(self, config: DatabricksShoppingConfig | None = None) -> None:
        self.config = config or DatabricksShoppingConfig()
        self.metric_name = self.config.headline_metric
        self.baseline_name = self.config.baseline_name

    @property
    def ladder(self) -> list[Solution]:
        return [Solution(name, desc) for name, desc in _RUNGS]

    # ---- direct API (used by tests, examples and the CLI) ----
    def build_recommender(self, train, *, level: int = -1, validate=None):
        """Build the recommender for one ladder rung from ``train``.

        Levels 4 and 6 are the tuned rungs and need a ``validate(build)->score``
        callable (a time-based split inside the training data).
        """
        lvl = level if level >= 0 else len(_RUNGS) - 1
        if lvl == 0:
            return solvers.v0_global_popularity(train)
        if lvl == 1:
            return solvers.v1_recent_popularity(train)
        if lvl == 2:
            return solvers.v2_next_item_bigram(train)
        if lvl == 3:
            return solvers.v3_covisit_session(train)
        if lvl == 4:
            if validate is None:
                raise ValueError("level 4 (tuned) needs a validate callable")
            return solvers.v4_tuned(train, validate)[0]
        if lvl == 5:
            return solvers.v5_hybrid(train)
        if lvl == 6:
            if validate is None:
                raise ValueError("level 6 (tuned) needs a validate callable")
            return solvers.v6_hybrid_tuned(train, validate)[0]
        raise IndexError(f"no ladder rung at level {level}")

    # ---- uniform life-cycle entry ----
    def evaluate(self, *, n: int, dev_seed: int, hidden_seed: int) -> TrackReport:
        c = self.config
        per_week = max(c.per_week_factor * n, c.per_week_factor)

        world = World(c.world_seed)
        train = build_train(world, c.world_seed, per_week)
        dev = eval_set(world, dev_seed, n)
        hidden = eval_set(world, hidden_seed, n)

        # Tune on a time-based split INSIDE train (last train week = validation),
        # exactly as the original run.py -- never on the hidden set.
        last = WEEKS - 2
        fit = [(w, s) for w, s in train if w < last]
        r = random.Random(3)
        val = []
        for w, s in train:
            if w == last and len(s) >= 2 and len(val) < c.val_cap:
                k = r.randint(1, len(s) - 1)
                val.append((s[:k], s[k][0]))

        def validate(build):
            return score(build(fit), val, k=c.k)[1]  # maximise validation MRR@K

        # Build each rung's recommender, in ladder order.
        recs = [
            solvers.v0_global_popularity(train),
            solvers.v1_recent_popularity(train),
            solvers.v2_next_item_bigram(train),
            solvers.v3_covisit_session(train),
        ]
        rec4, cfg4, val4 = solvers.v4_tuned(train, validate)
        recs.append(rec4)
        recs.append(solvers.v5_hybrid(train))
        rec6, cfg6, val6 = solvers.v6_hybrid_tuned(train, validate)
        recs.append(rec6)

        notes = (f"v4 chose `{cfg4}` (validation MRR@{c.k} {val4:.3f}); "
                 f"v6 chose `{cfg6}` (validation MRR@{c.k} {val6:.3f}). "
                 "Databricks allows 2 submissions/hour, so this dev-vs-hidden "
                 "split (and the time-based split v4/v6 tune on) is the only way "
                 "to iterate -- never tune on the leaderboard.")

        report = TrackReport(
            track=self.name, metric_name=self.metric_name, n_cases=n,
            dev_seed=dev_seed, hidden_seed=hidden_seed, baseline_name=self.baseline_name,
            notes=notes,
        )
        for (name, desc), rec in zip(_RUNGS, recs):
            dev_card = recommend_card(rec, dev, k=c.k)
            hid_card = recommend_card(rec, hidden, k=c.k)
            report.results.append(SolutionResult(Solution(name, desc), dev_card, hid_card))
        return report

    def run(self, *, n: int | None = None, dev_seed: int | None = None,
            hidden_seed: int | None = None) -> TrackReport:
        c = self.config
        return self.evaluate(n=n or c.n, dev_seed=dev_seed or c.dev_seed,
                             hidden_seed=hidden_seed or c.hidden_seed).finalize()

    run_sync = run


# Register on import so the harness and quality gate discover the track by name.
MODEL = register_track(DatabricksShoppingModel())
