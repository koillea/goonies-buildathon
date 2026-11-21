"""The ladder climbs: the strongest bot out-places the weakest on hidden matches."""
from __future__ import annotations

from mech_royale import solvers
from mech_royale.evaluation import score_candidate
from mech_royale.model import MechRoyaleModel

# Matches per cell for the comparison tests. Small so the suite runs in a few
# seconds; the top-2 gap (random ~12% vs lookahead ~47% vs the strong field) is
# wide enough to clear match-sampling noise at a fixed seed.
N = 30
SEED = 9001


def test_strong_bot_beats_random_on_hidden_top2():
    field = solvers.STRONG_FIELD
    weak = score_candidate(solvers.b_random, field, N, SEED)
    strong = score_candidate(solvers.v4_lookahead, field, N, SEED)
    # Generous margin: the true gap is ~35 points; require at least 10.
    assert strong.headline >= weak.headline + 0.10


def test_smart_rungs_beat_random_on_hidden():
    # The three modelling rungs each clear the random baseline by a wide margin.
    # (Their order relative to one another is noisy at small n, so we do not
    # assert a single winner here -- only the climb above random.)
    field = solvers.STRONG_FIELD
    rnd = score_candidate(solvers.b_random, field, N, SEED).headline
    for bot in (solvers.v2_zone_focus, solvers.v3_survivor, solvers.v4_lookahead):
        assert score_candidate(bot, field, N, SEED).headline >= rnd + 0.10


def test_evaluate_reports_the_three_measures(model: MechRoyaleModel):
    report = model.run(n=10)
    hidden = report.results[-1].hidden.metrics
    assert set(hidden) == {"top2_rate", "mean_points", "win_rate"}
    # Rates are probabilities; mean points is a non-negative placement score.
    assert 0.0 <= hidden["top2_rate"] <= 1.0
    assert 0.0 <= hidden["win_rate"] <= 1.0
    assert hidden["mean_points"] >= 0.0


def test_ladder_has_six_rungs(model: MechRoyaleModel):
    assert len(model.ladder) == 6
    assert model.ladder[0].name == "v0 random"
