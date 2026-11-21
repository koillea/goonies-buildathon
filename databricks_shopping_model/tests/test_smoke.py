"""Smoke: the package imports, registers, and scores end to end."""
from __future__ import annotations

from buildathon_core import Harness, get_track

import databricks_shopping  # noqa: F401  (import registers the track)


def test_registered():
    spec = get_track("databricks_shopping")
    assert spec.metric_name == "recall@20"
    assert spec.baseline_name == "v0 all-time popularity"


def test_harness_runs_small():
    report = Harness(n=10).run(get_track("databricks_shopping"))
    assert len(report.results) == 7
    assert report.best is not None
