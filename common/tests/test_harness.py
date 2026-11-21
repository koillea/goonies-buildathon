"""The harness scores a track and renders a stable table."""
from __future__ import annotations

from buildathon_core import Harness, Status, get_track, render_report, track_names


def test_harness_runs_and_finalizes(fake_track):
    report = Harness(n=5).run(fake_track)
    assert report.track == "fake_track"
    assert report.n_cases == 5
    best = report.best
    assert best.solution.name == "v1 better"
    assert best.status == Status.BEST


def test_registry_roundtrip(fake_track):
    assert "fake_track" in track_names()
    assert get_track("fake_track") is fake_track


def test_render_report_has_columns_and_rows(fake_track):
    report = Harness(n=5).run(fake_track)
    md = render_report(report)
    assert "# fake_track (practice) - results" in md
    assert "Dev accuracy" in md and "Hidden accuracy" in md
    assert "Generalizes" in md
    assert "v0 baseline" in md and "v1 better" in md
    assert "**best**" in md
