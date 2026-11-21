"""RWXBlastRadiusModel: the TrackSpec for the RWX Blast Radius track.

RWX is two tasks on the same synthetic repos (culprit-finding, test-impact). The
ladders climb in lock-step (both have v0..v4, each level adding the same modelling
insight), so one rung pairs the culprit solver and the impact solver at that
level. Its ScoreCard carries culprit **accuracy** (the headline), plus impact
**f1** and **exact** so the second task is never hidden.

``run`` / ``run_sync`` is the uniform life-cycle entry (plan + score + render)
the other models expose; ``decompose``-style direct access is via ``solvers``.
"""
from __future__ import annotations

from buildathon_core import (
    ScoreCard,
    Solution,
    SolutionResult,
    TrackReport,
    register_track,
)

from . import solvers
from .config import RWXConfig
from .data import dataset
from .evaluation import score_culprit, score_impact

# Rungs, paired by level. Each entry: (name, description, culprit_solver, impact_solver).
_RUNGS = [
    ("v0 latest / run-all",
     "name the latest commit; re-run every test. The board's Baseline row.",
     solvers.culprit_v0_latest, solvers.impact_v0_all),
    ("v1 surface text / name match",
     "trust the log text and test-name conventions -- fragile on hidden data.",
     solvers.culprit_v1_log_file, solvers.impact_v1_name_match),
    ("v2 static import cone",
     "follow the failing test's static import closure.",
     solvers.culprit_v2_import_cone, solvers.impact_v2_static),
    ("v3 symbol from error + re-exports",
     "use the symbol named in the error; add package __init__ re-exports.",
     solvers.culprit_v3_symbol, solvers.impact_v3_packages),
    ("v4 full graph + semantic diff",
     "model dynamic imports and data-file reads; ignore comment-only diffs.",
     solvers.culprit_v4_semantic_cone, solvers.impact_v4_full),
]


class RWXBlastRadiusModel:
    """TrackSpec implementation for RWX Blast Radius."""

    name = "rwx_blast_radius"

    def __init__(self, config: RWXConfig | None = None) -> None:
        self.config = config or RWXConfig()
        self.metric_name = self.config.headline_metric
        self.baseline_name = self.config.baseline_name

    @property
    def ladder(self) -> list[Solution]:
        return [Solution(name, desc) for name, desc, _, _ in _RUNGS]

    # ---- direct API (used by tests, examples and the CLI) ----
    def solve_culprit(self, case, *, level: int = -1):
        return _RUNGS[level][2](case)

    def solve_impact(self, case, *, level: int = -1):
        return _RUNGS[level][3](case)

    # ---- uniform life-cycle entry ----
    def evaluate(self, *, n: int, dev_seed: int, hidden_seed: int) -> TrackReport:
        cul_dev = dataset("culprit", n, dev_seed)
        cul_hid = dataset("culprit", n, hidden_seed)
        imp_dev = dataset("impact", n, dev_seed)
        imp_hid = dataset("impact", n, hidden_seed)

        report = TrackReport(
            track=self.name, metric_name=self.metric_name, n_cases=n,
            dev_seed=dev_seed, hidden_seed=hidden_seed, baseline_name=self.baseline_name,
            notes="Headline is culprit-finding accuracy; impact F1 and exact-match "
                  "ride along as the second task's measures.",
        )
        for name, desc, cul, imp in _RUNGS:
            dev_f1, dev_exact = score_impact(imp, imp_dev)
            hid_f1, hid_exact = score_impact(imp, imp_hid)
            dev = ScoreCard(headline=score_culprit(cul, cul_dev),
                            metrics={"accuracy": score_culprit(cul, cul_dev),
                                     "f1": dev_f1, "exact": dev_exact})
            hid = ScoreCard(headline=score_culprit(cul, cul_hid),
                            metrics={"accuracy": score_culprit(cul, cul_hid),
                                     "f1": hid_f1, "exact": hid_exact})
            report.results.append(SolutionResult(Solution(name, desc), dev, hid))
        return report

    def run(self, *, n: int | None = None, dev_seed: int | None = None,
            hidden_seed: int | None = None) -> TrackReport:
        c = self.config
        return self.evaluate(n=n or c.n, dev_seed=dev_seed or c.dev_seed,
                             hidden_seed=hidden_seed or c.hidden_seed).finalize()

    run_sync = run


# Register on import so the harness and quality gate discover the track by name.
MODEL = register_track(RWXBlastRadiusModel())
