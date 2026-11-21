"""Proves all four tracks register and run through the one harness.

The analog of his examples/tests/ that proves the enterprise pipeline wiring.
"""
from __future__ import annotations

# Importing registers each track.
import databricks_shopping  # noqa: F401
import machina_deid  # noqa: F401
import mech_royale  # noqa: F401
import rwx_blast_radius  # noqa: F401
from buildathon_core import Harness, Status, all_tracks, render_report, track_names

EXPECTED = {"rwx_blast_radius", "databricks_shopping", "machina_deid", "mech_royale"}


def test_all_four_tracks_registered():
    assert EXPECTED <= set(track_names())


def test_every_track_runs_and_renders():
    harness = Harness(n=8)
    for spec in all_tracks():
        if spec.name not in EXPECTED:
            continue
        report = harness.run(spec)
        assert report.results, f"{spec.name} produced no results"
        assert report.best is not None
        md = render_report(report)
        assert f"{spec.name} (practice) - results" in md


def test_each_track_has_a_baseline_and_a_best():
    harness = Harness(n=8)
    for spec in all_tracks():
        if spec.name not in EXPECTED:
            continue
        report = harness.run(spec)
        statuses = {r.status for r in report.results}
        assert Status.BEST in statuses
        # a baseline row exists (the first rung, or the named baseline)
        assert report.baseline is not None
