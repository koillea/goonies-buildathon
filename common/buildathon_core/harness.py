"""The one place a track is scored and rendered.

``Harness.run(spec)`` calls the track's ``evaluate`` (dev + hidden), finalizes
statuses, and renders the same markdown table shape every track's ``RESULTS.md``
uses. This is the ``run.py`` logic every ``practice/<folder>`` repeated, lifted
into the shared core -- the equivalent of his ``examples/enterprise_pipeline.py``
being the single wiring every model composes through.
"""
from __future__ import annotations

from .config import DEFAULT_N, DEV_SEED, HIDDEN_SEED
from .contracts import Status, TrackReport
from .protocols import TrackSpec
from .telemetry import Tracer

_STATUS_MARK = {
    Status.BASELINE: "baseline",
    Status.BEATS_BASELINE: "beats",
    Status.BELOW_BASELINE: "below",
    Status.BEST: "**best**",
}


class Harness:
    """Scores a track on dev and a different-seed hidden split, then renders it."""

    def __init__(self, *, n: int = DEFAULT_N, dev_seed: int = DEV_SEED,
                 hidden_seed: int = HIDDEN_SEED) -> None:
        self.n = n
        self.dev_seed = dev_seed
        self.hidden_seed = hidden_seed
        self.tracer = Tracer()

    def run(self, spec: TrackSpec) -> TrackReport:
        with self.tracer.span(spec.name):
            report = spec.evaluate(n=self.n, dev_seed=self.dev_seed,
                                   hidden_seed=self.hidden_seed)
        return report.finalize()


def render_report(report: TrackReport) -> str:
    """One markdown document for a track's RESULTS.md."""
    metric_cols = _metric_columns(report)
    header = ["Approach", *[f"Dev {m}" for m in metric_cols],
              *[f"Hidden {m}" for m in metric_cols], "Generalizes", "Status"]
    lines = [
        f"# {report.track} (practice) - results",
        "",
        f"{report.n_cases} dev cases (seed {report.dev_seed}) and "
        f"{report.n_cases} hidden cases (seed {report.hidden_seed}). "
        f"Headline metric: **{report.metric_name}** (higher is better). "
        "Synthetic data; the real task format is unknown.",
        "",
    ]
    if report.notes:
        lines += [report.notes, ""]
    lines += ["| " + " | ".join(header) + " |",
              "|" + "|".join("---" for _ in header) + "|"]
    for r in report.results:
        row = [r.solution.name]
        row += [_fmt(r.dev.metrics.get(m)) for m in metric_cols]
        row += [_fmt(r.hidden.metrics.get(m)) for m in metric_cols]
        row += ["yes" if r.generalizes else "NO", _STATUS_MARK[r.status]]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def _metric_columns(report: TrackReport) -> list[str]:
    cols: list[str] = []
    for r in report.results:
        for m in r.hidden.metrics:
            if m not in cols:
                cols.append(m)
    return cols or ["score"]


def _fmt(v: float | None) -> str:
    if v is None:
        return "-"
    if 0.0 <= v <= 1.0:
        return f"{v:.3f}"
    return f"{v:.2f}"
