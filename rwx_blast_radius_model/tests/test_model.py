"""The ladder climbs, and the strongest solvers get the fixture right."""
from __future__ import annotations

from rwx_blast_radius.evaluation import score_culprit, score_impact
from rwx_blast_radius.model import RWXBlastRadiusModel

from .rwx_fixtures import CULPRIT_CASE, CULPRIT_TRUTH


def test_strong_solvers_find_the_culprit(model: RWXBlastRadiusModel):
    # v3 (symbol from error) and v4 (semantic cone) must pin the breaking commit.
    assert model.solve_culprit(CULPRIT_CASE, level=3) == CULPRIT_TRUTH
    assert model.solve_culprit(CULPRIT_CASE, level=4) == CULPRIT_TRUTH


def test_culprit_accuracy_improves_with_level(culprit_cases):
    m = RWXBlastRadiusModel()
    from rwx_blast_radius import solvers
    acc = [score_culprit(fn, culprit_cases) for _, fn in solvers.CULPRIT]
    assert acc[-1] >= acc[0]           # strongest beats weakest
    assert acc[-1] >= 0.8              # full graph should be strong on synthetic data


def test_impact_full_beats_runall_on_f1(impact_cases):
    from rwx_blast_radius import solvers
    f1_all, _ = score_impact(solvers.impact_v0_all, impact_cases)
    f1_full, _ = score_impact(solvers.impact_v4_full, impact_cases)
    assert f1_full >= f1_all


def test_evaluate_reports_both_tasks(model: RWXBlastRadiusModel):
    report = model.run(n=8)
    hidden = report.results[-1].hidden.metrics
    assert set(hidden) == {"accuracy", "f1", "exact"}
