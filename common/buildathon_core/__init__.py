"""buildathon_core: the shared contract every track sits on.

Mirrors the role of ``pipeline_core`` in the reference repo
(prebuilt-ai-technique-models): one result contract, a protocol a track
implements, a registry, a harness that scores dev-vs-hidden and renders the
table. Pure Python standard library only.
"""
from __future__ import annotations

from .config import DEFAULT_N, DEV_SEED, HIDDEN_SEED
from .contracts import (
    ScoreCard,
    Solution,
    SolutionResult,
    Status,
    TrackReport,
)
from .harness import Harness, render_report
from .protocols import Metric, Solver, TrackSpec
from .registry import all_tracks, get_track, register_track, track_names
from .telemetry import Tracer

__all__ = [
    "DEFAULT_N",
    "DEV_SEED",
    "HIDDEN_SEED",
    "ScoreCard",
    "Solution",
    "SolutionResult",
    "Status",
    "TrackReport",
    "Harness",
    "render_report",
    "Metric",
    "Solver",
    "TrackSpec",
    "all_tracks",
    "get_track",
    "register_track",
    "track_names",
    "Tracer",
]
