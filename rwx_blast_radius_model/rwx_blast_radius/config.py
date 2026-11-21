"""Track configuration for RWX Blast Radius.

The RWX practice board tolerates probing (100 submissions/hour), so the local
case count can stay modest; the headline is culprit-finding accuracy (the site's
one worked example: "accuracy on the same 100 test cases").
"""
from __future__ import annotations

from dataclasses import dataclass

from buildathon_core import DEFAULT_N, DEV_SEED, HIDDEN_SEED


@dataclass(frozen=True)
class RWXConfig:
    n: int = DEFAULT_N
    dev_seed: int = DEV_SEED
    hidden_seed: int = HIDDEN_SEED
    # The published metric ranks on culprit accuracy; impact F1 rides along as a
    # second measured scalar so neither task is lost.
    headline_metric: str = "accuracy"
    baseline_name: str = "v0 latest / run-all"
