"""The protocols a track implements so the harness can drive it.

Composition through protocols, not imports: the harness never imports a track
package; a track registers a ``TrackSpec`` and the harness consumes it. This is
the same "one contract, swappable implementations" rule his ``pipeline_core``
enforces with its ``Retriever``/``Verifier``/``Executor``/``ResponseCache``
protocols.
"""
from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable

from .contracts import ScoreCard, Solution, TrackReport

# A Solver turns one case into a prediction. Its shape is the track's own
# (a commit id, a ranked item list, a de-identified file, a bot policy), so the
# type is deliberately opaque here.
Solver = Callable[[Any], Any]


@runtime_checkable
class TrackSpec(Protocol):
    """One buildathon track: a metric, a weak->strong ladder, and a way to score it.

    A track owns its data generator, its scorer and its ladder internally
    (they differ wildly between tracks); it exposes only this uniform surface.
    ``evaluate`` is the single method the harness calls.
    """

    name: str
    metric_name: str          # the published metric, higher-is-better (e.g. "accuracy")
    baseline_name: str        # which ladder rung is the board's "Baseline row"

    @property
    def ladder(self) -> list[Solution]:
        """The approaches, weakest first -- kept so none is ever lost."""
        ...

    def evaluate(self, *, n: int, dev_seed: int, hidden_seed: int) -> TrackReport:
        """Score every rung on a dev split and a different-seed hidden split."""
        ...


class Metric(Protocol):
    """A scorer: run a solver over cases, return a uniform ScoreCard."""

    name: str

    def score(self, solver: Solver, cases: list[Any]) -> ScoreCard:
        ...
