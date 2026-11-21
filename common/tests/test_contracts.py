"""Unit tests for the result contract."""
from __future__ import annotations

from buildathon_core import ScoreCard, Solution, SolutionResult, Status, TrackReport


def test_scorecard_backfills_metrics():
    sc = ScoreCard(0.5)
    assert sc.metrics == {"score": 0.5}


def test_generalizes_absolute_and_relative():
    close = SolutionResult(Solution("a"), ScoreCard(0.70), ScoreCard(0.69))
    assert close.generalizes
    far = SolutionResult(Solution("b"), ScoreCard(0.70), ScoreCard(0.40))
    assert not far.generalizes
    small = SolutionResult(Solution("c"), ScoreCard(0.02), ScoreCard(0.05))
    assert small.generalizes  # within 0.05 absolute even though relative is huge


def test_finalize_assigns_statuses():
    report = TrackReport("t", "accuracy", 10, 1, 9001, baseline_name="v0")
    report.results = [
        SolutionResult(Solution("v0"), ScoreCard(0.3), ScoreCard(0.3)),
        SolutionResult(Solution("v1"), ScoreCard(0.5), ScoreCard(0.45)),
        SolutionResult(Solution("v2"), ScoreCard(0.2), ScoreCard(0.1)),
    ]
    report.finalize()
    by = {r.solution.name: r.status for r in report.results}
    assert by["v0"] == Status.BASELINE
    assert by["v1"] == Status.BEST            # best hidden
    assert by["v2"] == Status.BELOW_BASELINE  # below the baseline


def test_best_and_baseline_lookup():
    report = TrackReport("t", "f1", 10, 1, 9001, baseline_name="v0")
    report.results = [
        SolutionResult(Solution("v0"), ScoreCard(0.3), ScoreCard(0.3)),
        SolutionResult(Solution("v1"), ScoreCard(0.9), ScoreCard(0.8)),
    ]
    assert report.baseline.solution.name == "v0"
    assert report.best.solution.name == "v1"
