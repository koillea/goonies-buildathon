"""Smoke: the package imports, registers, and scores end to end."""
from __future__ import annotations

from buildathon_core import Harness, get_track

import rwx_blast_radius  # noqa: F401  (import registers the track)


def test_registered():
    spec = get_track("rwx_blast_radius")
    assert spec.metric_name == "accuracy"


def test_harness_runs_small():
    report = Harness(n=8).run(get_track("rwx_blast_radius"))
    assert len(report.results) == 5
    assert report.best is not None
