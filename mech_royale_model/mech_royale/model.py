"""MechRoyaleModel: the TrackSpec for the Builders Mech Royale track.

Mech Royale is a *competitive* track: you submit a bot and it is scored by how
well it places against a field of other bots over many seeded matches. The
ladder is ``solvers.ALL`` (random -> chase -> camp -> zone-focus -> survivor ->
one-step lookahead). Each rung is played against ``solvers.STRONG_FIELD`` (the
better bots, including ones that also appear on the ladder) -- exactly the strong
field ``run.py`` reports against.

``evaluate`` plays every rung over ``n`` matches with ``dev_seed`` and again with
a *different* ``hidden_seed`` (the hidden seed stands in for unseen match
schedules). The ScoreCard headline is the top-2 rate (run.py's metric); mean
points and win rate ride along so neither diagnostic is lost.

``run`` is the uniform life-cycle entry (plan + score + render) every model
exposes; direct access to the bots is via ``solvers``.
"""
from __future__ import annotations

from buildathon_core import (
    Solution,
    SolutionResult,
    TrackReport,
    register_track,
)

from . import solvers
from .config import MechRoyaleConfig
from .evaluation import score_candidate

# Ladder descriptions, aligned with solvers.ALL (weakest first).
_DESCRIPTIONS = {
    "v0 random": "move or shoot at random. The board's Baseline row.",
    "v1 chase and shoot nearest": "chase the nearest enemy and fire whenever one is in range.",
    "v1b camp the centre": "walk to the middle, then shoot the nearest enemy in range.",
    "v2 zone-aware, focus weakest": "never leave the next zone; focus the target you are most likely to finish.",
    "v3 survivor: avoid fights, finish kills": "let others trade damage; stay in the zone, finish cheap kills, duel only in the endgame.",
    "v4 one-step lookahead on expected damage": "score every action by expected damage dealt minus expected damage taken, caution dropping as enemies die.",
}


class MechRoyaleModel:
    """TrackSpec implementation for Builders Mech Royale."""

    name = "mech_royale"

    def __init__(self, config: MechRoyaleConfig | None = None) -> None:
        self.config = config or MechRoyaleConfig()
        self.metric_name = self.config.headline_metric
        self.baseline_name = self.config.baseline_name

    @property
    def ladder(self) -> list[Solution]:
        return [Solution(name, _DESCRIPTIONS.get(name, "")) for name, _ in solvers.ALL]

    # ---- direct API (used by tests, examples and the CLI) ----
    def bot(self, *, level: int = -1):
        """The bot callable at a ladder rung."""
        return solvers.ALL[level][1]

    def score_bot(self, bot, *, n: int, seed: int, field=None):
        """Score a single bot against a field (defaults to the strong field)."""
        return score_candidate(bot, field if field is not None else solvers.STRONG_FIELD, n, seed)

    # ---- uniform life-cycle entry ----
    def evaluate(self, *, n: int, dev_seed: int, hidden_seed: int) -> TrackReport:
        field = solvers.STRONG_FIELD
        report = TrackReport(
            track=self.name, metric_name=self.metric_name, n_cases=n,
            dev_seed=dev_seed, hidden_seed=hidden_seed, baseline_name=self.baseline_name,
            notes="Headline is the hidden top-2 rate against the strong field; mean "
                  "points and win rate ride along. The hidden seed stands in for "
                  "unseen match schedules.",
        )
        for name, bot in solvers.ALL:
            dev = score_candidate(bot, field, n, dev_seed)
            hid = score_candidate(bot, field, n, hidden_seed)
            report.results.append(SolutionResult(Solution(name, _DESCRIPTIONS.get(name, "")), dev, hid))
        return report

    def run(self, *, n: int | None = None, dev_seed: int | None = None,
            hidden_seed: int | None = None) -> TrackReport:
        c = self.config
        return self.evaluate(n=n or c.n, dev_seed=dev_seed or c.dev_seed,
                             hidden_seed=hidden_seed or c.hidden_seed).finalize()

    run_sync = run


# Register on import so the harness and quality gate discover the track by name.
MODEL = register_track(MechRoyaleModel())
