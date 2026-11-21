"""Shared fixtures for buildathon_core tests: a tiny fake track."""
from __future__ import annotations

import pytest

from buildathon_core import ScoreCard, Solution, SolutionResult, TrackReport, register_track


class FakeTrack:
    """A minimal TrackSpec: two rungs, a headline that improves on the second."""

    name = "fake_track"
    metric_name = "accuracy"
    baseline_name = "v0 baseline"

    @property
    def ladder(self) -> list[Solution]:
        return [Solution("v0 baseline", "predict nothing"),
                Solution("v1 better", "predict the obvious thing")]

    def evaluate(self, *, n: int, dev_seed: int, hidden_seed: int) -> TrackReport:
        report = TrackReport(track=self.name, metric_name=self.metric_name, n_cases=n,
                             dev_seed=dev_seed, hidden_seed=hidden_seed,
                             baseline_name=self.baseline_name)
        report.results = [
            SolutionResult(Solution("v0 baseline"),
                           ScoreCard(0.30, {"accuracy": 0.30}),
                           ScoreCard(0.31, {"accuracy": 0.31})),
            SolutionResult(Solution("v1 better"),
                           ScoreCard(0.80, {"accuracy": 0.80}),
                           ScoreCard(0.78, {"accuracy": 0.78})),
        ]
        return report


@pytest.fixture
def fake_track() -> FakeTrack:
    spec = FakeTrack()
    register_track(spec)
    return spec
