"""The ladder climbs: the strongest de-identifier passes, the v0 no-op leaks."""
from __future__ import annotations

from machina_deid import solvers
from machina_deid.evaluation import score
from machina_deid.model import MachinaDeidModel


def test_strongest_passes_and_noop_leaks(dev_cases):
    # v5 (seed-and-propagate) de-identifies every file; v0 (no-op) leaks on every file.
    strongest = score(solvers.v5_seed_and_propagate, dev_cases)
    noop = score(solvers.v0_noop, dev_cases)
    assert strongest["pass"] >= 0.99          # strongest reaches ~1.0 pass rate
    assert noop["pass"] <= 0.01               # baseline passes almost nothing
    assert noop["leak"] >= 0.99               # ... because it leaks


def test_leak_and_broken_rates_behave(dev_cases):
    # v0 no-op: leaks but never corrupts the file.
    noop = score(solvers.v0_noop, dev_cases)
    assert noop["leak"] >= 0.99
    assert noop["broken"] == 0.0
    # v3 blank-everything: the opposite failure -- no leak, but it loses needed data.
    blank = score(solvers.v3_blank_everything, dev_cases)
    assert blank["leak"] == 0.0
    assert blank["lost"] >= 0.99
    assert blank["pass"] == 0.0


def test_pass_rate_improves_from_baseline_to_best(dev_cases):
    rates = [score(fn, dev_cases)["pass"] for _, fn in solvers.ALL]
    assert rates[-1] >= rates[0]              # strongest beats weakest
    assert rates[-1] >= 0.99                  # full de-identifier should pass on synthetic data


def test_evaluate_reports_full_breakdown(model: MachinaDeidModel):
    report = model.run(n=8)
    hidden = report.results[-1].hidden.metrics
    assert set(hidden) == {"pass_rate", "leak", "broken", "lost", "retained"}


def test_strongest_generalizes_dev_to_hidden(model: MachinaDeidModel):
    report = model.run(n=12)
    best = report.best
    assert best.generalizes
