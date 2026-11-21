"""Track configuration for Builders Mech Royale.

The Builders board allows 4 submissions/hour -- more generous than Databricks or
Machina (2/hour), tighter than RWX (100/hour) -- so we can afford a few probes
but still trust a local validation set over the leaderboard. The tournament is
stochastic, so ``n`` is the number of matches per cell: raise it for a steadier
headline, lower it in tests so runs finish in seconds. The headline is the
hidden top-2 rate against the strong field (what ``run.py`` ranks on); mean
points and win rate ride along as secondary measures.
"""
from __future__ import annotations

from dataclasses import dataclass

from buildathon_core import DEFAULT_N, DEV_SEED, HIDDEN_SEED


@dataclass(frozen=True)
class MechRoyaleConfig:
    n: int = DEFAULT_N          # matches per cell (the tournament is stochastic)
    dev_seed: int = DEV_SEED
    hidden_seed: int = HIDDEN_SEED
    headline_metric: str = "top2_rate"
    baseline_name: str = "v0 random"
