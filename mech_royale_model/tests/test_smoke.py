"""Smoke: the package imports, registers, and scores end to end."""
from __future__ import annotations

from buildathon_core import Harness, get_track

import mech_royale  # noqa: F401  (import registers the track)


def test_registered():
    spec = get_track("mech_royale")
    assert spec.metric_name == "top2_rate"
    assert spec.baseline_name == "v0 random"


def test_harness_runs_small():
    report = Harness(n=10).run(get_track("mech_royale"))
    assert len(report.results) == 6
    assert report.best is not None
    # Every rung carries the three measured scalars.
    assert set(report.results[-1].hidden.metrics) == {"top2_rate", "mean_points", "win_rate"}
