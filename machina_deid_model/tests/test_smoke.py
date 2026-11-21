"""Smoke: the package imports, registers, and scores end to end."""
from __future__ import annotations

from buildathon_core import Harness, get_track

import machina_deid  # noqa: F401  (import registers the track)


def test_registered():
    spec = get_track("machina_deid")
    assert spec.metric_name == "pass_rate"
    assert spec.baseline_name == "v0 do nothing"


def test_harness_runs_small():
    report = Harness(n=6).run(get_track("machina_deid"))
    assert len(report.results) == 6
    assert report.best is not None
