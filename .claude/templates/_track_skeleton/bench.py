"""Benchmark for <TRACK NAME> (<SPONSOR>).

Copy this folder to practice/<track_slug>/ (or tracks/<track_slug>/) and fill in the
three TODOs. Keep the interface identical so run.py works unchanged:

    load_cases()           -> list[(case, truth)]   every labelled example we have
    split(cases)           -> (dev, holdout)        holdout mimics the HIDDEN test set
    score(solve, cases)    -> float                 THE metric, exactly as the brief states it

Rule zero: `score` must reproduce the official metric EXACTLY (same K, same averaging,
same tie/empty handling). Submit the baseline once and confirm your local number matches
the board. If they disagree, the scorer is wrong — fix it before optimizing anything.

Pure standard library only, so it runs anywhere the grader fleet might.
"""
from __future__ import annotations

import random

SEED = 1  # fixed so every run is reproducible; never tune against a moving split


def load_cases() -> list[tuple[object, object]]:
    """TODO(1): load the REAL labelled data from the starter kit.

    Return a list of (case, truth). `case` is whatever the solver receives; `truth` is
    what a perfect solver would output. Shape them exactly like the grader feeds them.
    """
    raise NotImplementedError("load the real starter-kit data here")


def split(cases: list, holdout_frac: float = 0.3):
    """TODO(2): build a holdout that looks like the HIDDEN set, not just a random slice.

    The default below is a seeded random split. OVERRIDE IT whenever the data has order:
      - time series / sessions / logs  -> TIME split: train on earlier, hold out the latest.
        A random split leaks future information and makes local scores lie.
      - grouped data (users, repos, files) -> GROUP split: no group in both halves.
    If local says "better" but the board says "worse", this function is the usual culprit.
    """
    rng = random.Random(SEED)
    shuffled = cases[:]
    rng.shuffle(shuffled)
    cut = int(len(shuffled) * (1 - holdout_frac))
    return shuffled[:cut], shuffled[cut:]


def score(solve, cases) -> float:
    """TODO(3): the official metric. Higher must mean better (negate a loss if needed).

    Replace this accuracy placeholder with the brief's exact metric, e.g. Recall@K,
    MRR@K, mean F1, pass-rate over a multi-condition check, or placement.
    """
    if not cases:
        return 0.0
    return sum(solve(c) == t for c, t in cases) / len(cases)
