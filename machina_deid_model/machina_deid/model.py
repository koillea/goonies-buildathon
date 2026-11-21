"""MachinaDeidModel: the TrackSpec for the Machina CAD De-ID track.

One task on synthetic STEP files: strip every identifier while keeping the file
valid and the geometry unchanged. The ladder (v0..v5) climbs out of the two
opposite failure modes -- leak and destroy -- to a schema allowlist and a
seed-and-propagate redactor that both pass. Its ScoreCard carries the **pass
rate** (the headline) plus the full breakdown (leak / broken / lost) and a
harmless-label ``retained`` proxy, so no failure mode is ever hidden.

``run`` is the uniform life-cycle entry (score dev + hidden, then finalize) the
other models expose; direct access to a single de-identifier is via ``solve``.
"""
from __future__ import annotations

from buildathon_core import (
    Solution,
    SolutionResult,
    TrackReport,
    register_track,
)

from . import solvers
from .config import MachinaDeidConfig
from .data import dataset
from .evaluation import deid_card

# Human-readable descriptions keyed by ladder-rung name (names come verbatim
# from solvers.ALL; the baseline is "v0 do nothing").
_DESCRIPTIONS = {
    "v0 do nothing":
        "pass the file through untouched. The board's Baseline row -- every identifier leaks.",
    "v1 scrub header only":
        "blank the header strings only; identifiers still leak into labels, comments and escapes.",
    "v2 + person / organization / product records, comments":
        "also blank PERSON / ORGANIZATION / PRODUCT records and comments; leaks survive in geometry labels and \\X2\\ escapes.",
    "v3 blank every string":
        "blank every data-section string: no leaks, but it destroys the schema name and units -- the opposite failure.",
    "v4 blank all except schema records and safe properties":
        "allowlist: blank everything except schema/unit records and known-safe keys. Passes, but drops harmless labels too.",
    "v5 learn identity tokens, remove them everywhere":
        "seed-and-propagate: learn the file's own identity tokens, remove exactly those everywhere (decoding \\X2\\), keep harmless strings.",
}


class MachinaDeidModel:
    """TrackSpec implementation for Machina CAD De-ID."""

    name = "machina_deid"

    def __init__(self, config: MachinaDeidConfig | None = None) -> None:
        self.config = config or MachinaDeidConfig()
        self.metric_name = self.config.headline_metric
        self.baseline_name = self.config.baseline_name

    @property
    def ladder(self) -> list[Solution]:
        return [Solution(name, _DESCRIPTIONS.get(name, "")) for name, _ in solvers.ALL]

    # ---- direct API (used by tests, examples and the CLI) ----
    def solve(self, text: str, *, level: int = -1) -> str:
        """Run one de-identifier (default: the strongest) on a STEP file."""
        return solvers.ALL[level][1](text)

    # ---- uniform life-cycle entry ----
    def evaluate(self, *, n: int, dev_seed: int, hidden_seed: int) -> TrackReport:
        dev = dataset(n, dev_seed)
        hid = dataset(n, hidden_seed)

        report = TrackReport(
            track=self.name, metric_name=self.metric_name, n_cases=n,
            dev_seed=dev_seed, hidden_seed=hidden_seed, baseline_name=self.baseline_name,
            notes="Headline is the file pass rate (parses + geometry unchanged + "
                  "no leak + required data kept). leak / broken / lost and the "
                  "harmless-label retained rate ride along so both failure modes show.",
        )
        for name, fn in solvers.ALL:
            report.results.append(SolutionResult(
                Solution(name, _DESCRIPTIONS.get(name, "")),
                deid_card(fn, dev), deid_card(fn, hid)))
        return report

    def run(self, *, n: int | None = None, dev_seed: int | None = None,
            hidden_seed: int | None = None) -> TrackReport:
        c = self.config
        return self.evaluate(n=n or c.n, dev_seed=dev_seed or c.dev_seed,
                             hidden_seed=hidden_seed or c.hidden_seed).finalize()

    run_sync = run


# Register on import so the harness and quality gate discover the track by name.
MODEL = register_track(MachinaDeidModel())
