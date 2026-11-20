"""Approaches for <TRACK NAME>, weakest to strongest.

Discipline:
  - v0 is the dumbest thing that produces a valid answer (majority / most popular /
    return-everything). It gets a row on the board and sanity-checks the scorer.
  - Add ONE idea per version. Never edit a version that has already scored — add a new
    one, so you can always fall back and so the ladder shows what each idea was worth.
  - Each function takes one `case` and returns a prediction in the grader's format.
"""
from __future__ import annotations


def v0_baseline(case):
    """Dumbest valid answer. TODO: e.g. the majority class / most popular item."""
    raise NotImplementedError


# def v1_<idea>(case):
#     """One new idea on top of v0. State the idea and the assumption it relies on."""
#     ...


# Ordered weakest -> strongest. run.py scores every entry. Append; never reorder/delete.
SOLUTIONS = [
    ("v0 baseline", v0_baseline),
]
