"""The data contract every track shares.

His repo (prebuilt-ai-technique-models) binds six LLM pipeline models to one
``TaskRequest``/``TaskResult`` contract validated with pydantic. This repo
mirrors that idea for *buildathon tracks*: heterogeneous internals (a classifier,
a fit-then-recommend recommender, an invariant-preserving transform, a
competitive tournament) all report a single, uniform result so one harness can
score them, compare them on a dev-vs-hidden split, and render one table.

**Deviation from his core:** pure Python standard library only (dataclasses +
enum, no pydantic). The buildathon scorer fleet runs untrusted code in a minimal
sandbox, so every track in this repo keeps the "stdlib only" invariant the
PLAYBOOK requires. The shape of the contract is his; the dependency surface is
smaller on purpose.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class Status(enum.Enum):
    """Where a solution's hidden score sits relative to the track baseline.

    Mirrors the ``SUCCESS``/``PARTIAL``/``NEEDS_REVIEW``/``FAILED`` status enum
    his models branch on, specialised for a scoreboard buildathon.
    """

    BASELINE = "BASELINE"            # the baseline row itself
    BEATS_BASELINE = "BEATS_BASELINE"
    BELOW_BASELINE = "BELOW_BASELINE"
    BEST = "BEST"                    # best hidden score in the ladder

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@dataclass(frozen=True)
class ScoreCard:
    """A single solution's score on a single split.

    ``headline`` is the one number the track's published metric ranks on
    (higher is better). ``metrics`` carries every named scalar the track
    measures (e.g. recall and MRR, or F1 and exact-match) so diagnostics are
    never lost. ``extras`` holds non-scalar audit data (timings, counts).
    """

    headline: float
    metrics: dict[str, float] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # headline must always be present in metrics under the track's metric name
        if not self.metrics:
            object.__setattr__(self, "metrics", {"score": self.headline})


@dataclass(frozen=True)
class Solution:
    """One rung of the weak->strong ladder: a named, described approach."""

    name: str
    description: str = ""


@dataclass
class SolutionResult:
    """A solution scored on both splits."""

    solution: Solution
    dev: ScoreCard
    hidden: ScoreCard
    status: Status = Status.BELOW_BASELINE

    @property
    def generalizes(self) -> bool:
        """Dev and hidden agreeing is the signal a change is real, not overfit.

        True when the hidden headline is within 20% (relative) of dev, or both
        are within 0.05 absolute -- the "dev and hidden scores agree" check the
        PLAYBOOK makes the gate for every submission.
        """
        d, h = self.dev.headline, self.hidden.headline
        if abs(d - h) <= 0.05:
            return True
        denom = abs(d) or 1e-9
        return abs(d - h) / denom <= 0.20


@dataclass
class TrackReport:
    """Every solution scored, plus the metadata needed to render a results table."""

    track: str
    metric_name: str
    n_cases: int
    dev_seed: int
    hidden_seed: int
    results: list[SolutionResult] = field(default_factory=list)
    baseline_name: str | None = None
    notes: str = ""

    @property
    def best(self) -> SolutionResult | None:
        return max(self.results, key=lambda r: r.hidden.headline, default=None)

    @property
    def baseline(self) -> SolutionResult | None:
        for r in self.results:
            if r.solution.name == self.baseline_name:
                return r
        return self.results[0] if self.results else None

    def finalize(self) -> "TrackReport":
        """Assign each result a status relative to the baseline and the best row."""
        base = self.baseline
        base_hidden = base.hidden.headline if base else float("-inf")
        best = self.best
        for r in self.results:
            if base is not None and r.solution.name == base.solution.name:
                r.status = Status.BASELINE
            elif r.hidden.headline >= base_hidden:
                r.status = Status.BEATS_BASELINE
            else:
                r.status = Status.BELOW_BASELINE
        if best is not None:
            best.status = Status.BEST
        return self
